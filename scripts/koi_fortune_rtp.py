"""RTP check for "koi-fortune" — the whole game through the REAL features.

scripts/simulate.py doesn't know Hold & Win, so this plays the game round by
round with the seed's own tables (app/seed/koi_fortune.py):
- base spin: 10 lines (a mirror of app/engine/wins.evaluate_line_wins,
  cross-checked against it on start-up), gong cap 1 per reel like
  app/services/scatter_cap, coin faces like coin_multiplier, Hold & Win
  through HoldAndWinFeature.execute (initial_from_base_coins);
- 3+ gongs: 10 free spins on the FS weight set, +5 per retrigger, Hold & Win
  inside the round included;
- 5 000x cap per round (paid spin + everything it started);
- Ante Bet: the same game on the ante weight set, price x1.25;
- Buy Free Spins (purchase spin pays its lines, then the round) and Buy
  Hold & Win (no gongs, redrawn to 6+ coins, lines unpaid).

Usage: .venv/bin/python scripts/koi_fortune_rtp.py [spins] [seed] [buys] [procs]
"""

import bisect
import os
import random
import sys
from decimal import Decimal
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.features.base import FeatureContext  # noqa: E402
from app.features.hold_and_win import HoldAndWinFeature  # noqa: E402
from app.seed import koi_fortune as seed  # noqa: E402
from app.simulator.rng import FastRNG  # noqa: E402

NUM_REELS, NUM_ROWS = seed.NUM_REELS, seed.NUM_ROWS
CODES = [c for c, *_ in seed._SYMBOLS]
BASE = {c: list(w) for c, *_, w in seed._SYMBOLS}
WILD, SCAT, COIN = 'wild', 'scatter', 'coin'
NON_LINE = {SCAT, COIN}
PAY = {c: {int(k): v / len(seed.PAYLINES) for k, v in p.items()} for c, p in seed._PAYS.items()}
CAP = seed.FREE_SPINS_PARAMS['round_max_win_multiplier']
FSP = seed.FREE_SPINS_PARAMS
HWP = seed.HOLD_AND_WIN_PARAMS
ANTE = seed.ANTE_BET_PARAMS
HW = HoldAndWinFeature()
FACE_KEYS = list(seed.COIN_FACE_WEIGHTS)
FACE_CUM = []
_t = 0
for _k in FACE_KEYS:
    _t += seed.COIN_FACE_WEIGHTS[_k]
    FACE_CUM.append(_t)


def weights_with(overrides):
    out = {c: list(w) for c, w in BASE.items()}
    for c, v in overrides.items():
        out[c] = list(v) if isinstance(v, list) else [int(v)] * NUM_REELS
    return out


def tables(weights):
    """Per reel: (codes, cumulative, total) and the same without the gong
    (the cap's redraw table)."""
    def one(ws):
        cum, t = [], 0
        for w in ws:
            t += w
            cum.append(t)
        return cum, t
    full, noscat = [], []
    for r in range(NUM_REELS):
        ws = [weights[c][r] for c in CODES]
        full.append(one(ws))
        noscat.append(one([0 if c == SCAT else w for c, w in zip(CODES, ws)]))
    return full, noscat


SETS = {
    'base': tables(BASE),
    'fs': tables(weights_with(FSP['reel_weight_overrides'])),
    'ante': tables(weights_with(ANTE['weight_overrides'])),
    'buy_hw': tables(weights_with({c: 0 for c in HWP['buy_exclude_symbols']})),
}


def pick(cum_t, rnd):
    cum, t = cum_t
    return CODES[bisect.bisect_right(cum, rnd.randrange(t))]


def draw(set_name, rnd):
    full, noscat = SETS[set_name]
    reels = []
    for r in range(NUM_REELS):
        col = [pick(full[r], rnd) for _ in range(NUM_ROWS)]
        seen = False
        for i, c in enumerate(col):
            if c == SCAT:
                if seen:
                    col[i] = pick(noscat[r], rnd)
                seen = True
        reels.append(col)
    return reels


def lines_win(reels):
    win = 0.0
    for line in seed.PAYLINES:
        target = None
        run = 0
        for r, row in enumerate(line):
            c = reels[r][row]
            if c in NON_LINE:
                break
            if c == WILD:
                run += 1
                continue
            if target is None:
                target = c
                run += 1
            elif c == target:
                run += 1
            else:
                break
        code = target or (WILD if run else None)
        if code is not None:
            win += PAY[code].get(run, 0.0)
    return win


class _Grid:
    def __init__(self, reels):
        self.reels = reels


def faces(reels, rnd):
    out = []
    for r, col in enumerate(reels):
        for row, c in enumerate(col):
            if c == COIN:
                k = FACE_KEYS[bisect.bisect_right(FACE_CUM, rnd.randrange(FACE_CUM[-1]))]
                out.append({'reel': r, 'row': row, 'value': k, 'kind': k})
    return out


def hold_and_win(reels, rng, st, tag):
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal(1), symbols={}, grid=_Grid(reels))
    ctx.coin_values = faces(reels, rng._random)
    res = HW.execute(ctx, HWP)
    win = float(res.win_amount)
    st[f'{tag}_hw'] = st.get(f'{tag}_hw', 0) + win
    st[f'{tag}_hw_n'] = st.get(f'{tag}_hw_n', 0) + 1
    for rs in res.details['respins']:
        for c in rs['landed']:
            if c['kind'] in seed.JACKPOT_VALUES:
                st['jp_' + c['kind']] = st.get('jp_' + c['kind'], 0) + 1
    if res.details.get('full_grid_jackpot'):
        st['jp_grand'] = st.get('jp_grand', 0) + 1
    return win


def play_spin(set_name, rng, st, tag):
    """One spin's own win (x bet) and whether it opens free spins."""
    reels = draw(set_name, rng._random)
    win = lines_win(reels)
    st[f'{tag}_lines'] = st.get(f'{tag}_lines', 0) + win
    if sum(col.count(COIN) for col in reels) >= HWP['trigger_count']:
        win += hold_and_win(reels, rng, st, tag)
    return win, sum(col.count(SCAT) for col in reels) >= FSP['trigger_count']


def free_spins_round(rng, st):
    """The round's own win, capped; spins played."""
    total = 0.0
    left = FSP['spins_awarded']
    while left > 0:
        left -= 1
        w, re = play_spin('fs', rng, st, 'fs')
        total += w
        if total >= CAP:
            st['fs_capped'] = st.get('fs_capped', 0) + 1
            return float(CAP)
        if re:
            left += FSP['retrigger_spins']
            st['retrigger'] = st.get('retrigger', 0) + 1
    return total


def run_game(args):
    spins, seed_, set_name = args
    rng = FastRNG(seed_)
    st = {}
    total = hits = capped = 0
    best = 0.0
    wins = []
    for _ in range(spins):
        win, fs = play_spin(set_name, rng, st, 'base')
        if win > 0:
            hits += 1
        round_win = win
        if fs:
            st['fs_n'] = st.get('fs_n', 0) + 1
            fs_win = free_spins_round(rng, st)
            st['fs_pay'] = st.get('fs_pay', 0) + fs_win
            round_win += fs_win
        if round_win >= CAP:
            capped += 1
            round_win = CAP
        best = max(best, round_win)
        total += round_win
        if round_win >= 100:
            wins.append(round_win)
    st.update(total=total, hits=hits, capped=capped, best=best, spins=spins, big=len(wins),
              w1000=sum(1 for w in wins if w >= 1000))
    return st


def run_buys(args):
    buys, seed_, kind = args
    rng = FastRNG(seed_)
    st = {}
    total = 0.0
    best = 0.0
    sq = 0.0
    for _ in range(buys):
        if kind == 'fs':
            reels = draw('base', rng._random)
            w = lines_win(reels) + free_spins_round(rng, st)
        else:
            while True:
                reels = draw('buy_hw', rng._random)
                if sum(col.count(COIN) for col in reels) >= HWP['buy_min_coins']:
                    break
            w = min(float(CAP), hold_and_win(reels, rng, st, 'buy'))
        total += w
        sq += w * w
        best = max(best, w)
    st.update(total=total, sq=sq, best=best, n=buys)
    return st


def merge(parts):
    out = {}
    for p in parts:
        for k, v in p.items():
            out[k] = max(out.get(k, 0), v) if k == 'best' else out.get(k, 0) + v
    return out


def cross_check(n=20000):
    """lines_win must match the production evaluator exactly."""
    from app.engine.types import SpinGrid
    from app.engine.wins import evaluate_line_wins
    from app.services.config_adapter import to_paylines, to_reel_set_config
    _, cfg = seed.build_game_config()
    reel_set, paylines = to_reel_set_config(cfg), to_paylines(cfg)
    rnd = random.Random(1)
    for _ in range(n):
        reels = draw('fs', rnd)
        grid = SpinGrid(reels=reels, draws=())
        ref = sum(float(w.payout_multiplier) for w in evaluate_line_wins(grid, reel_set.symbols, paylines, Decimal(1)))
        mine = lines_win(reels) * len(seed.PAYLINES)
        assert abs(ref - mine) < 1e-9, (reels, ref, mine)


def report_game(name, k, price=1.0):
    n = k['spins']
    rtp = k['total'] / n / price
    print(f'\n== {name}: {n:,} spins, price {price}x')
    print(f'TOTAL RTP        {rtp:.4f}   hit {k["hits"] / n:.3f}   best {k["best"]:.0f}x   capped 1/{n / max(1, k["capped"]):,.0f}')
    print(f'  base lines     {k.get("base_lines", 0) / n / price:.4f}')
    hw_n = k.get('base_hw_n', 0)
    print(f'  base H&W       {k.get("base_hw", 0) / n / price:.4f}   1/{n / max(1, hw_n):.0f}   avg {k.get("base_hw", 0) / max(1, hw_n):.1f}x')
    fs_n = k.get('fs_n', 0)
    print(f'  free spins     {k.get("fs_pay", 0) / n / price:.4f}   1/{n / max(1, fs_n):.0f}   avg {k.get("fs_pay", 0) / max(1, fs_n):.1f}x'
          f'   (H&W in FS {k.get("fs_hw_n", 0) / max(1, fs_n):.2f}/round, avg {k.get("fs_hw", 0) / max(1, k.get("fs_hw_n", 0)):.1f}x;'
          f' FS lines {k.get("fs_lines", 0) / max(1, fs_n):.1f}x/round; retrig {k.get("retrigger", 0) / max(1, fs_n):.3f}/round)')
    all_hw = hw_n + k.get('fs_hw_n', 0)
    jp = '  '.join(f'{t.upper()} 1/{n / max(1, k.get("jp_" + t, 0)):,.0f}' for t in ('mini', 'minor', 'major', 'grand'))
    print(f'  jackpots       {jp}   (rounds {all_hw:,})')
    print(f'  wins >=100x 1/{n / max(1, k["big"]):,.0f}   >=1000x 1/{n / max(1, k["w1000"]):,.0f}')
    return rtp


def report_buy(name, k, price):
    n = k['n']
    avg = k['total'] / n
    sd = (k['sq'] / n - avg * avg) ** 0.5
    print(f'BUY {name:4s} {price}x: avg {avg:.2f}x  RTP {avg / price:.4f}  (±{1.96 * sd / n ** 0.5 / price:.4f})'
          f'  best {k["best"]:.0f}x  fair @95.5% = {avg / 0.955:.1f}x')


def main():
    spins = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
    s0 = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    buys = int(sys.argv[3]) if len(sys.argv) > 3 else 100_000
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else os.cpu_count() or 4
    cross_check()
    chunk = lambda total: [total // procs] * procs  # noqa: E731
    with Pool(procs) as pool:
        base = merge(pool.map(run_game, [(c, s0 * 1000 + i, 'base') for i, c in enumerate(chunk(spins))]))
        ante = merge(pool.map(run_game, [(c, s0 * 1000 + 100 + i, 'ante') for i, c in enumerate(chunk(spins))]))
        bfs = merge(pool.map(run_buys, [(c, s0 * 1000 + 200 + i, 'fs') for i, c in enumerate(chunk(buys))]))
        bhw = merge(pool.map(run_buys, [(c, s0 * 1000 + 300 + i, 'hw') for i, c in enumerate(chunk(buys))]))
    r0 = report_game('BASE GAME', base)
    r1 = report_game('ANTE BET', ante, ANTE['cost_multiplier'])
    fs_x = (base['spins'] / max(1, base.get('fs_n', 0))) / (ante['spins'] / max(1, ante.get('fs_n', 0)))
    hw_x = (base['spins'] / max(1, base.get('base_hw_n', 0))) / (ante['spins'] / max(1, ante.get('base_hw_n', 0)))
    print(f'  ante vs base: FS x{fs_x:.2f}, H&W x{hw_x:.2f}, RTP {r1 - r0:+.4f}')
    print()
    report_buy('FS', bfs, seed.BUY_FREE_SPINS_COST)
    report_buy('H&W', bhw, seed.BUY_HOLD_AND_WIN_COST)


if __name__ == '__main__':
    main()
