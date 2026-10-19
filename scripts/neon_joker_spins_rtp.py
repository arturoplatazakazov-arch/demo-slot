"""RTP check for "neon-joker-spins" — the whole game through the REAL features.

scripts/simulate.py doesn't know Hold & Win, so this plays the game round by
round with the seed's own tables (app/seed/neon_joker_spins.py):
- base spin: lines (wild substitutes everything but coin/scatter, a wild-only
  line pays wild) + joker count pay + Hold & Win (HoldAndWinFeature.execute);
- 3+ jokers: 10 free spins on the FS weight set, +5 per retrigger, Hold & Win
  inside the round included;
- 2 500x cap per round (paid spin + everything it started);
- Buy Hold & Win: purchase spin without jokers redrawn to 5+ coins, line wins
  not paid -> average round and the fair price at 95.5%.

Usage: .venv/bin/python scripts/neon_joker_spins_rtp.py [spins] [seed] [buys]
"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.reels import weighted_pick  # noqa: E402
from app.features.base import FeatureContext  # noqa: E402
from app.features.hold_and_win import HoldAndWinFeature  # noqa: E402
from app.seed import neon_joker_spins as seed  # noqa: E402
from app.simulator.rng import FastRNG  # noqa: E402


class _Grid:
    def __init__(self, reels):
        self.reels = reels


CODES = [c for c, *_ in seed._SYMBOLS]
BASE_W = [w for *_, w in seed._SYMBOLS]
FS_W = [seed.FS_WEIGHT_OVERRIDES.get(c, w) for c, w in zip(CODES, BASE_W)]
BUY_W = [0 if c in seed.HOLD_AND_WIN_PARAMS['buy_exclude_symbols'] else w for c, w in zip(CODES, BASE_W)]
LINE_PAY = {c: p['3'] / 5 for c, p in seed._PAYS.items() if '3' in p and c != 'scatter'}
SCAT_PAY = {int(k): v for k, v in seed._PAYS['scatter'].items()}
NON_LINE = {'coin', 'scatter'}
CAP = seed.FREE_SPINS_PARAMS['round_max_win_multiplier']
HW = HoldAndWinFeature()
HWP = seed.HOLD_AND_WIN_PARAMS


def draw(weights, rng):
    return [[CODES[weighted_pick(weights, rng)[0]] for _ in range(3)] for _ in range(3)]


def lines_win(reels):
    win = 0.0
    for line in seed.PAYLINES:
        syms = [reels[r][row] for r, row in enumerate(line)]
        if any(s in NON_LINE for s in syms):
            continue
        rest = {s for s in syms if s != 'wild'}
        if not rest:
            win += LINE_PAY['wild']
        elif len(rest) == 1:
            win += LINE_PAY[rest.pop()]
    return win


class Stats:
    def __init__(self):
        self.k = {}

    def add(self, key, v=1):
        self.k[key] = self.k.get(key, 0) + v


def play_spin(weights, rng, st, tag):
    """One spin's own win (x bet) and whether it opens free spins."""
    reels = draw(weights, rng)
    win = lines_win(reels)
    st.add(f'{tag}_lines', win)
    jokers = sum(col.count('scatter') for col in reels)
    if jokers in SCAT_PAY:
        win += SCAT_PAY[jokers]
        st.add(f'{tag}_scatter', SCAT_PAY[jokers])
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal(1), symbols={}, grid=_Grid(reels))
    if HW.is_triggered(ctx, HWP):
        res = HW.execute(ctx, HWP)
        hw = float(res.win_amount)
        win += hw
        st.add(f'{tag}_hw', hw)
        st.add(f'{tag}_hw_n')
        coll = res.details.get('collector_total')
        if coll is not None and float(coll) > 0:
            st.add('hw_with_collector')
            st.add('collector_pay', float(coll))
        landed = res.details['initial'] + [c for r in res.details['respins'] for c in r['landed']]
        for c in landed:
            if c['kind'] in seed.JACKPOT_VALUES:
                st.add(f'jp_{c["kind"]}')
        if res.details.get('full_grid_jackpot'):
            st.add('jp_grand')
    return win, jokers >= 3


def main():
    spins = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    rng = FastRNG(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    buys = int(sys.argv[3]) if len(sys.argv) > 3 else 100_000
    st = Stats()
    total = 0.0
    hits = 0
    best = 0.0
    capped = 0
    for _ in range(spins):
        win, fs = play_spin(BASE_W, rng, st, 'base')
        if win > 0:
            hits += 1
        round_win = win
        if fs:
            st.add('fs_n')
            left = seed.FREE_SPINS_PARAMS['spins_awarded']
            while left > 0 and round_win < CAP:
                left -= 1
                w, re = play_spin(FS_W, rng, st, 'fs')
                round_win += w
                if re:
                    left += seed.FREE_SPINS_PARAMS['retrigger_spins']
                    st.add('retrigger')
            st.add('fs_pay', round_win - win)
        if round_win >= CAP:
            capped += 1
            round_win = CAP
        best = max(best, round_win)
        total += round_win

    k = st.k
    print(f'spins {spins}')
    print(f'TOTAL RTP        {total / spins:.4f}   hit {hits / spins:.3f}   best {best:.0f}x   capped {capped}')
    print(f'  base lines     {k.get("base_lines", 0) / spins:.4f}')
    print(f'  base scatter   {k.get("base_scatter", 0) / spins:.4f}')
    print(f'  base H&W       {k.get("base_hw", 0) / spins:.4f}   1/{spins / max(1, k.get("base_hw_n", 0)):.0f}'
          f'   avg {k.get("base_hw", 0) / max(1, k.get("base_hw_n", 0)):.1f}x')
    print(f'  free spins     {k.get("fs_pay", 0) / spins:.4f}   1/{spins / max(1, k.get("fs_n", 0)):.0f}'
          f'   avg {k.get("fs_pay", 0) / max(1, k.get("fs_n", 0)):.1f}x   retriggers {k.get("retrigger", 0)}')
    hw_n = k.get('base_hw_n', 0) + k.get('fs_hw_n', 0)
    print(f'  H&W in FS      n={k.get("fs_hw_n", 0)}   avg {k.get("fs_hw", 0) / max(1, k.get("fs_hw_n", 0)):.1f}x')
    print(f'  H&W overall    1/{spins / max(1, hw_n):.0f}   collector in 1/{hw_n / max(1, k.get("hw_with_collector", 0)):.1f} rounds'
          f'   collector RTP {k.get("collector_pay", 0) / spins:.4f}')
    for t in ('mini', 'minor', 'major', 'grand'):
        n = k.get(f'jp_{t}', 0)
        print(f'  {t:6s} 1/{spins / max(1, n):.0f}  rtp {n * seed.JACKPOT_VALUES[t] / spins:.4f}')

    # Buy Hold & Win
    bt = 0.0
    for _ in range(buys):
        while True:
            reels = draw(BUY_W, rng)
            if sum(col.count('coin') for col in reels) >= HWP['buy_min_coins']:
                break
        ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal(1), symbols={}, grid=_Grid(reels))
        bt += min(CAP, float(HW.execute(ctx, HWP).win_amount))
    avg = bt / buys
    print(f'BUY  avg round {avg:.2f}x  -> price @95.5% = {avg / 0.955:.1f}x   '
          f'RTP at {seed.BONUS_BUY_COST_MULTIPLIER}x = {avg / seed.BONUS_BUY_COST_MULTIPLIER:.4f}')


if __name__ == '__main__':
    main()
