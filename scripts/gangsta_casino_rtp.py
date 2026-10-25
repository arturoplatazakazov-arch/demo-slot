"""RTP check for "gangsta-casino" on the real engine modules.

Mirrors app/api/v1/spin_service.py: draw + reel caps, expanding/walking wild,
11-line evaluation, coin_multiplier (multiplier symbol; base: line pay x the
sum on screen, free spins: sticky round multiplier), scatter free spins with
retriggers, round lifecycle (free_spins_round.settle). Also the bonus buy:
average value of a bought round (10 spins) vs its x100 price.

Usage: .venv/bin/python scripts/gangsta_casino_rtp.py [base_spins] [buys] [procs]
Env knobs: GC_MW (multiplier reel weight), GC_MV (value weights JSON).
"""
import json
import os
import random
import sys
from decimal import Decimal
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.seed import gangsta_casino as seed  # noqa: E402

if os.environ.get('GC_MW'):
    seed.MULTIPLIER_WEIGHT = int(os.environ['GC_MW'])
    seed._SYMBOLS = [(c, n, t, tier, seed.MULTIPLIER_WEIGHT if c == 'wof' else w, p, m)
                     for c, n, t, tier, w, p, m in seed._SYMBOLS]
if os.environ.get('GC_SW'):
    seed._SYMBOLS = [(c, n, t, tier, int(os.environ['GC_SW']) if c == 'scatter' else w, p, m)
                     for c, n, t, tier, w, p, m in seed._SYMBOLS]
if os.environ.get('GC_FSMW'):
    seed.FS_WEIGHT_OVERRIDES['wof'] = int(os.environ['GC_FSMW'])
if os.environ.get('GC_K'):  # scale every line paytable
    k = float(os.environ['GC_K'])
    for d in (seed._COMMON_PAYS, seed._RARE_PAYS, seed._WILD_PAYS):
        for key in d:
            d[key] = round(d[key] * k, 1)
if os.environ.get('GC_MV'):
    seed.COIN_MULTIPLIER_PARAMS['value_weights'] = json.loads(os.environ['GC_MV'])

from app.engine.reels import spin_reels  # noqa: E402
from app.engine.wins import evaluate_spin  # noqa: E402
from app.features import default_registry  # noqa: E402
from app.features.base import FeatureContext  # noqa: E402
from app.api.v1.spin_service import with_weight_overrides  # noqa: E402
from app.services import free_spins_round  # noqa: E402
from app.services.config_adapter import to_paylines, to_reel_set_config  # noqa: E402
from app.services.spin_features import apply_expanding_wild, apply_reel_caps  # noqa: E402

_, CFG = seed.build_game_config()
FEAT = {fc.feature_type: fc.params for fc in CFG.feature_configs}
REELS = to_reel_set_config(CFG)
FS_REELS = with_weight_overrides(REELS, FEAT['free_spins'].get('reel_weight_overrides') or {})
LINES = to_paylines(CFG)
BET = Decimal(55000)
FS = default_registry.get('free_spins')
COIN = default_registry.get('coin_multiplier')


class Rng:
    def __init__(self, seed_):
        self.r = random.Random(seed_)

    def randbelow(self, n):
        return self.r.randrange(n)


def one_spin(state, rng, forced_fs=False):
    was_fs = free_spins_round.is_active(state)
    reels = FS_REELS if was_fs else REELS
    grid = apply_reel_caps(spin_reels(reels, rng), reels, rng)
    apply_expanding_wild(grid, type('C', (), {'params': FEAT['expanding_wild'], 'enabled': True})(), state, rng, BET, reels)
    ev = evaluate_spin(grid, reels.symbols, LINES, BET / len(LINES), BET)
    ctx = FeatureContext(session_state=state, rng=rng, bet_amount=BET, symbols=reels.symbols,
                         grid=grid, win_evaluation=ev, is_bonus_buy=False)
    bonus = Decimal(0)
    if COIN.is_triggered(ctx, FEAT['coin_multiplier']):
        bonus = COIN.execute(ctx, FEAT['coin_multiplier']).win_amount
    win = (ev.total_win + bonus) * free_spins_round.win_multiplier(state, was_fs)
    trig = False
    if forced_fs or FS.is_triggered(ctx, FEAT['free_spins']):
        state.update(FS.execute(ctx, FEAT['free_spins']).state_patch)
        trig = True
        if not was_fs:
            free_spins_round.enter_round(state, int(BET))
    free_spins_round.settle(state, win, was_fs)
    return win, was_fs, trig


def run(args):
    n, seed_ = args
    rng = Rng(seed_)
    state = {}
    base = fs = Decimal(0)
    trig = done = 0
    while done < n:
        w, was_fs, t = one_spin(state, rng)
        if was_fs:
            fs += w
        else:
            done += 1
            base += w
            trig += t
    return float(base), float(fs), trig


def run_buys(args):
    n, seed_ = args
    rng = Rng(seed_)
    total = Decimal(0)
    for _ in range(n):
        state = {}
        # bought spin: forced trigger (its own line wins pay as usual)
        w, _, _ = one_spin(state, rng, forced_fs=True)
        total += w
        while free_spins_round.is_active(state):
            total += one_spin(state, rng)[0]
    return float(total)


if __name__ == '__main__':
    spins = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    buys = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else os.cpu_count()
    with Pool(procs) as pool:
        parts = pool.map(run, [(spins // procs, 1000 + i) for i in range(procs)])
        bparts = pool.map(run_buys, [(buys // procs, 9000 + i) for i in range(procs)]) if buys else []
    n = spins // procs * procs
    base = sum(p[0] for p in parts); fs = sum(p[1] for p in parts); trig = sum(p[2] for p in parts)
    wag = float(BET) * n
    print(f'spins {n}: RTP {(base + fs) / wag:.4f} (base {base / wag:.4f}, fs {fs / wag:.4f}), FS 1 in {n / max(trig, 1):.0f}')
    if buys:
        nb = buys // procs * procs
        avg = sum(bparts) / nb / float(BET)
        print(f'buys {nb}: avg round {avg:.1f}x bet -> buy RTP {avg / seed.BUY_COST_MULTIPLIER:.4f} at x{seed.BUY_COST_MULTIPLIER}')
