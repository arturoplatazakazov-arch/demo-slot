"""RTP check for "savannah-kings" (GDD-03) through the production code.

Replays app/api/v1/spin_service.py's line-pay path without the DB: the seed's
own config (app/seed/savannah_kings.py) through to_reel_set_config,
spin_reels + apply_reel_caps, the FS weight set (with_weight_overrides),
apply_expanding_wild with masks/paws counted as they landed, evaluate_spin,
and the real FreeSpinsFeature / WheelOfFortuneFeature — natural play as
rounds (a paid spin plus every free spin it opened), then each purchase as
its own cohort.

Usage: .venv/bin/python scripts/savannah_kings_rtp.py [paid_spins] [buys] [seed]
"""

import dataclasses
import os
import sys
from collections import Counter
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.api.v1.spin_service import with_weight_overrides  # noqa: E402
from app.engine.reels import spin_reels, weighted_pick  # noqa: E402
from app.engine.wins import evaluate_count_wins, evaluate_spin  # noqa: E402
from app.features.base import FeatureContext  # noqa: E402
from app.features.free_spins import FreeSpinsFeature  # noqa: E402
from app.features.wheel_of_fortune import WheelOfFortuneFeature  # noqa: E402
from app.seed import savannah_kings as seed  # noqa: E402
from app.services.config_adapter import to_paylines, to_reel_set_config  # noqa: E402
from app.services.spin_features import apply_expanding_wild, apply_reel_caps  # noqa: E402
from app.simulator.rng import FastRNG  # noqa: E402


class _Row:
    def __init__(self, params):
        self.params = params


BET = Decimal(20)
FS = FreeSpinsFeature()
WHEEL = WheelOfFortuneFeature()
WILD_ROW = _Row(seed.EXPANDING_WILD_PARAMS)


def one_spin(base_set, fs_set, paylines, state, rng, stats):
    """One spin exactly as run_spin plays it; returns its win (x bet)."""
    in_fs = state.get('free_spins_remaining', 0) > 0
    reel_set = fs_set if in_fs else base_set
    grid = apply_reel_caps(spin_reels(reel_set, rng), reel_set, rng)
    landed = dataclasses.replace(grid, reels=[list(c) for c in grid.reels])
    apply_expanding_wild(grid, WILD_ROW, state, rng, BET, reel_set)
    ev = evaluate_spin(grid, reel_set.symbols, paylines, BET / len(paylines), BET)
    counts = evaluate_count_wins(landed, reel_set.symbols, BET)
    win = ev.line_pay_total + sum((w.win_amount for w in counts), Decimal(0))
    stats['lines_fs' if in_fs else 'lines'] += ev.line_pay_total
    stats['scatter'] += sum((w.win_amount for w in counts), Decimal(0))
    ctx = FeatureContext(session_state=state, rng=rng, bet_amount=BET, symbols=reel_set.symbols,
                         grid=landed, win_evaluation=ev, is_bonus_buy=False)
    if FS.is_triggered(ctx, seed.FREE_SPINS_PARAMS):
        res = FS.execute(ctx, seed.FREE_SPINS_PARAMS)
        if in_fs:
            stats['retriggers'] += 1
        else:
            stats['fs_rounds'] += 1
            stats['fs_spins_awarded'] += res.details['spins_awarded']
        state.update(res.state_patch)
    if WHEEL.is_triggered(ctx, seed.WHEEL_PARAMS):
        res = WHEEL.execute(ctx, seed.WHEEL_PARAMS)
        win += res.win_amount
        stats['wheel'] += res.win_amount
        stats['wheels'] += 1
        stats['tier_' + res.details['tier']] += 1
    return win / BET


def play_round(base_set, fs_set, paylines, state, rng, stats, first=None):
    """The paid spin (or a purchase's result) plus every free spin it opened,
    capped at round_max_win_multiplier."""
    cap = seed.FREE_SPINS_PARAMS['round_max_win_multiplier']
    total = first if first is not None else one_spin(base_set, fs_set, paylines, state, rng, stats)
    fs_total = Decimal(0)
    spins = 0
    while state.get('free_spins_remaining', 0) > 0 and total + fs_total < cap:
        w = one_spin(base_set, fs_set, paylines, state, rng, stats)
        state['free_spins_remaining'] -= 1
        fs_total += w
        spins += 1
    state.clear()
    return min(total + fs_total, Decimal(cap)), fs_total, spins


def main():
    paid = int(float(sys.argv[1])) if len(sys.argv) > 1 else 1_000_000
    buys = int(float(sys.argv[2])) if len(sys.argv) > 2 else 20_000
    rng = FastRNG(int(sys.argv[3]) if len(sys.argv) > 3 else 7)

    _, config = seed.build_game_config()
    base_set = to_reel_set_config(config)
    fs_set = with_weight_overrides(base_set, seed.FREE_SPINS_PARAMS['reel_weight_overrides'])
    paylines = to_paylines(config)

    stats = Counter()
    total = Decimal(0)
    hits = 0
    best = Decimal(0)
    bonus_total = Decimal(0)
    bonus_spins = 0
    buckets = Counter()
    for _ in range(paid):
        state = {}
        win, fs_total, spins = play_round(base_set, fs_set, paylines, state, rng, stats)
        total += win
        hits += win > 0
        best = max(best, win)
        bonus_total += fs_total
        bonus_spins += spins
        for edge in (0, 1, 2, 5, 10, 20, 50, 100, 250, 1000):
            if win <= edge:
                buckets[edge] += 1
                break
        else:
            buckets['1000+'] += 1

    n = Decimal(paid)
    rounds = max(1, stats['fs_rounds'])
    print(f'natural RTP {float(total / n):.4f}  (paid spins {paid:,})')
    print(f'  lines base {float(stats["lines"] / BET / n):.4f}  scatter pay {float(stats["scatter"] / BET / n):.4f}'
          f'  free spins {float(bonus_total / n):.4f}  wheels {float(stats["wheel"] / BET / n):.4f}')
    print(f'  hit {hits / paid:.3f}  FS 1/{paid / rounds:.0f}  wheel 1/{paid / max(1, stats["wheels"]):.0f}'
          f'  avg bonus {float(bonus_total) / rounds:.1f}x over {bonus_spins / rounds:.2f} spins,'
          f' retrigger {stats["retriggers"]}  best round {float(best):.0f}x')
    print('  tiers', {k[5:]: v for k, v in stats.items() if k.startswith('tier_')})
    print('  win buckets', dict(sorted(((str(k), v / paid) for k, v in buckets.items()))))

    # Purchases (GDD §6.4): the purchase spin pays nothing, so a buy is worth
    # exactly what its feature pays.
    fs_buy = Decimal(0)
    for _ in range(buys):
        state = {'free_spins_remaining': 10}
        win, _, _ = play_round(base_set, fs_set, paylines, state, rng, Counter(), first=Decimal(0))
        fs_buy += win
    wheel_buy = Decimal(0)
    for _ in range(buys * 5):
        ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal(1), symbols=base_set.symbols,
                             grid=None, is_bonus_buy=True)
        wheel_buy += WHEEL.execute(ctx, seed.WHEEL_PARAMS).win_amount
    fs_ev = float(fs_buy) / buys
    wheel_ev = float(wheel_buy) / (buys * 5)
    print(f'buy Free Spins     EV {fs_ev:.1f}x  price {seed.FREE_SPINS_BUY_COST}x -> RTP {fs_ev / seed.FREE_SPINS_BUY_COST:.4f}')
    print(f'buy Jackpot Chance EV {wheel_ev:.1f}x  price {seed.JACKPOT_CHANCE_BUY_COST}x -> RTP {wheel_ev / seed.JACKPOT_CHANCE_BUY_COST:.4f}')


if __name__ == '__main__':
    main()
