"""RTP check for "sugar-blast" (GDD-05) — through the PRODUCTION spin code.

Calls app/api/v1/spin_service.run_spin / run_feature_buy themselves (only the
DB is stubbed: the config comes from app/seed/sugar_blast.build_game_config()
in memory and commit_spin just writes state/balance back onto a fake
session), so bombs, the FS accumulator, Super FS, the wheel, the buys and
the 10 000x cap are measured exactly as the server plays them.

Usage:
  .venv/bin/python scripts/sugar_blast_rtp.py [spins] [seed] [buys_per_sku] [procs]
Env knobs (override the seed for tuning, no edit needed):
  SB_FS_BOMB, SB_FS_WILD, SB_SUPER_BOMB, SB_SUPER_WILD, SB_SCAT
"""

import asyncio
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.api.v1 import spin_service  # noqa: E402
from app.seed import sugar_blast as seed  # noqa: E402
from app.simulator.rng import FastRNG  # noqa: E402

BET = 10000  # max bet: every pay is a whole number of cents
PRICES = {
    'free_spins_buy': seed.FREE_SPINS_BUY_COST,
    'super_free_spins_buy': seed.SUPER_FREE_SPINS_BUY_COST,
    'jackpot_chance_buy': seed.JACKPOT_CHANCE_BUY_COST,
}
BUCKETS = [(0, 0), (0, 1), (1, 2), (2, 5), (5, 10), (10, 20), (20, 50), (50, 100),
           (100, 250), (250, 1000), (1000, None)]


def _apply_env():
    fs = seed.FREE_SPINS_PARAMS
    if os.environ.get('SB_FS_BOMB'):
        fs['reel_weight_overrides']['bomb'] = int(os.environ['SB_FS_BOMB'])
    if os.environ.get('SB_FS_WILD'):
        w = int(os.environ['SB_FS_WILD'])
        fs['reel_weight_overrides']['wild'] = [0, w, w, w, 0]
    if os.environ.get('SB_SUPER_BOMB'):
        fs['super_weight_overrides']['bomb'] = int(os.environ['SB_SUPER_BOMB'])
    if os.environ.get('SB_SUPER_WILD'):
        w = int(os.environ['SB_SUPER_WILD'])
        fs['super_weight_overrides']['wild'] = [0, w, w, w, 0]
    if os.environ.get('SB_SCAT'):
        w = int(os.environ['SB_SCAT'])
        for i, row in enumerate(seed._SYMBOLS):
            if row[0] == 'scatter':
                seed._SYMBOLS[i] = (*row[:4], [w] * 5, row[5])


class FakeSession:
    def __init__(self):
        self.state = {}
        self.balance = 10 ** 15
        self.game_id = 1


def _install_stubs(config):
    async def load(_db, _gid):
        return config

    async def commit(_db, session, *, state, balance_after, **_kw):
        session.state = state
        session.balance = balance_after

    spin_service.load_active_config = load
    spin_service.commit_spin = commit


async def _play_round(sess, rng, st, first):
    """Play free spins until the round ends. `first` = the entry response.
    Returns the round's win (x bet) excluding the entry spin."""
    total = 0
    mult = 1
    spins = 0
    while sess.state.get('free_spins_remaining', 0) > 0:
        r = await spin_service.run_spin(None, sess, BET, rng)
        spins += 1
        w = r.total_win / BET
        total += w
        if r.coin_multiplier and r.coin_multiplier.round_multiplier:
            mult = r.coin_multiplier.round_multiplier
        if r.wheel_of_fortune:
            st[f'fs_wheel_{r.wheel_of_fortune.tier}'] += 1
            st['fs_wheel_pay'] += r.wheel_of_fortune.win_amount / BET
        st['fs_scatter_pay'] += sum(c.amount for c in r.count_wins) / BET
        if r.feature and r.feature.triggered:
            st['fs_retrigger'] += 1
        if r.max_win_reached:
            st['cap_hit'] += 1
    st['fs_spins'] += spins
    st['fs_mult_sum'] += mult
    if mult > 150:
        st['fs_mult_gt150'] += 1
    return total, mult


async def _natural(n, seed_no):
    rng = FastRNG(seed_no)
    sess = FakeSession()
    st = Counter()
    hist = Counter()
    max_win = 0
    for _ in range(n):
        r = await spin_service.run_spin(None, sess, BET, rng)
        w = r.total_win / BET
        scat = sum(c.amount for c in r.count_wins) / BET
        wheel = r.wheel_of_fortune.win_amount / BET if r.wheel_of_fortune else 0
        lines = w - scat - wheel
        st['base_lines'] += lines
        st['base_scatter'] += scat
        st['base_wheel'] += wheel
        if r.wheel_of_fortune:
            st[f'wheel_{r.wheel_of_fortune.tier}'] += 1
            st['wheels'] += 1
        if any(c == 'bomb' for row in r.grid for c in row):
            st['spins_with_bomb'] += 1
        round_win = w
        if r.feature and r.feature.triggered and sess.state.get('free_spins_remaining', 0) > 0:
            st['fs_triggers'] += 1
            fs_win, _ = await _play_round(sess, rng, st, r)
            st['fs_win'] += fs_win
            round_win += fs_win
        if round_win > 0:
            st['hits'] += 1
        st['sq'] += round_win * round_win
        max_win = max(max_win, round_win)
        for i, (lo, hi) in enumerate(BUCKETS):
            if (hi is None and round_win >= lo) or (lo == hi == round_win == 0) or (
                hi is not None and lo < round_win <= hi and not (lo == hi)
            ):
                hist[i] += 1
                break
    st['max_win'] = max_win
    return st, hist


async def _buys(sku, n, seed_no):
    rng = FastRNG(seed_no)
    sess = FakeSession()
    st = Counter()
    total = 0.0
    sq = 0.0
    max_win = 0
    for _ in range(n):
        r = await spin_service.run_feature_buy(None, sess, sku, BET, rng)
        w = r.total_win / BET
        if sess.state.get('free_spins_remaining', 0) > 0:
            fs, _ = await _play_round(sess, rng, st, r)
            w += fs
        total += w
        sq += w * w
        max_win = max(max_win, w)
    st['total'] = total
    st['sq'] = sq
    st['max_win'] = max_win
    return st


def _worker(args):
    kind, sku, n, seed_no = args
    _apply_env()
    _game, config = seed.build_game_config()
    _install_stubs(config)
    if kind == 'nat':
        return asyncio.run(_natural(n, seed_no))
    return asyncio.run(_buys(sku, n, seed_no))


def main():
    spins = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    seed_no = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    buys = int(sys.argv[3]) if len(sys.argv) > 3 else 50_000
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    _apply_env()
    t0 = time.time()

    jobs = []
    if spins:
        per = spins // procs
        jobs += [('nat', None, per, seed_no * 1000 + i) for i in range(procs)]
    if buys:
        per_b = buys // procs
        for sku in PRICES:
            jobs += [('buy', sku, per_b, seed_no * 7000 + hash(sku) % 997 + i) for i in range(procs)]
    with Pool(procs) as pool:
        results = pool.map(_worker, jobs, chunksize=1)

    nat = Counter()
    hist = Counter()
    max_nat = 0
    buy = {sku: Counter() for sku in PRICES}
    buy_max = {sku: 0 for sku in PRICES}
    for job, res in zip(jobs, results):
        if job[0] == 'nat':
            st, h = res
            max_nat = max(max_nat, st.pop('max_win'))
            nat.update(st)
            hist.update(h)
        else:
            buy_max[job[1]] = max(buy_max[job[1]], res.pop('max_win'))
            buy[job[1]].update(res)

    fs = seed.FREE_SPINS_PARAMS
    print(f"levers: base bomb {seed.BASE_BOMB}, scatter "
          f"{[r for r in seed._SYMBOLS if r[0] == 'scatter'][0][4][0]}, FS bomb {fs['reel_weight_overrides']['bomb']}, "
          f"FS wild {fs['reel_weight_overrides']['wild'][1]}, super bomb {fs['super_weight_overrides']['bomb']}, "
          f"super wild {fs['super_weight_overrides']['wild'][1]}")
    if spins:
        n = (spins // procs) * procs
        rtp = (nat['base_lines'] + nat['base_scatter'] + nat['base_wheel'] + nat['fs_win']) / n
        fs_wheel = nat['fs_wheel_pay']
        mean = rtp
        var = nat['sq'] / n - mean * mean
        print(f"\nNATURAL {n:,} spins")
        print(f"  RTP                {rtp * 100:6.2f} %")
        print(f"  lines x bombs      {nat['base_lines'] / n * 100:6.2f} %")
        print(f"  scatter pays       {(nat['base_scatter'] + nat['fs_scatter_pay']) / n * 100:6.2f} %  (base {nat['base_scatter'] / n * 100:.2f})")
        print(f"  free spins         {nat['fs_win'] / n * 100:6.2f} %  (incl. wheels inside FS {fs_wheel / n * 100:.2f}, FS scatter pays {nat['fs_scatter_pay'] / n * 100:.2f})")
        print(f"  jackpot wheel      {(nat['base_wheel'] + fs_wheel) / n * 100:6.2f} %  (base {nat['base_wheel'] / n * 100:.2f} + in FS {fs_wheel / n * 100:.2f})")
        print(f"  hit frequency      {nat['hits'] / n * 100:6.2f} %")
        print(f"  spins with a bomb  {nat['spins_with_bomb'] / n * 100:6.2f} %")
        trig = nat['fs_triggers'] or 1
        print(f"  FS                 1 in {n / trig:,.0f}  avg {nat['fs_win'] / trig:.1f}x  "
              f"avg final mult x{nat['fs_mult_sum'] / trig:.1f}  >x150 {nat['fs_mult_gt150'] / trig * 100:.1f} %  "
              f"avg spins {nat['fs_spins'] / trig:.1f}")
        wheels = nat['wheels'] + sum(nat[f'fs_wheel_{t}'] for t in seed.JACKPOT_VALUES)
        print(f"  jackpot wheel      1 in {n / max(wheels, 1):,.0f} spins  (base only 1 in {n / max(nat['wheels'], 1):,.0f})")
        for t in seed.JACKPOT_VALUES:
            c = nat[f'wheel_{t}'] + nat[f'fs_wheel_{t}']
            print(f"    {t:6s} 1 in {n / max(c, 1):>9,.0f}  {c * seed.JACKPOT_VALUES[t] / n * 100:.2f} %")
        print(f"  std dev            {var ** 0.5:.1f}")
        print(f"  max win            {max_nat:,.0f}x   cap hits {nat['cap_hit']}")
        print("  distribution per paid round (x bet):")
        labels = ['0', '0-1', '1-2', '2-5', '5-10', '10-20', '20-50', '50-100', '100-250', '250-1000', '1000+']
        for i, lab in enumerate(labels):
            print(f"    {lab:>9}  {hist[i] / n * 100:7.3f} %")
    if buys:
        print(f"\nBUYS {(buys // procs) * procs:,} per SKU")
        for sku, price in PRICES.items():
            b = buy[sku]
            n = (buys // procs) * procs
            avg = b['total'] / n
            sd = (b['sq'] / n - avg * avg) ** 0.5
            se = sd / n ** 0.5
            line = f"  {sku:22s} price {price:>4}x  avg {avg:7.2f}x (±{1.96 * se:.2f})  RTP {avg / price * 100:6.2f} %  fair@95.5 {avg / 0.955:6.1f}x  max {buy_max[sku]:,.0f}x"
            if 'free_spins' in sku:
                line += f"  final mult x{b['fs_mult_sum'] / n:.1f}"
            print(line)
    print(f"\n{time.time() - t0:.0f}s")


if __name__ == '__main__':
    main()
