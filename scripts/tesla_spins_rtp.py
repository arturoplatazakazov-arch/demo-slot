"""RTP check for "tesla-spins" — lines + Hold & Win, run through the REAL feature.

scripts/simulate.py (app/simulator) only knows lines / free spins / wilds, so
it can't see a Hold & Win round. This script takes the seed's own tables
(app/seed/tesla_spins.py) and:

- lines: closed form, RTP_lines = Σ p_s³ · pay_s (three independent reels,
  one shared weight set, a coin breaks any line);
- Hold & Win: Monte Carlo of trigger + round, using HoldAndWinFeature.execute
  from app/features/hold_and_win.py on randomly drawn grids — so the respin
  logic, coin faces and the 9/9 GRAND are exactly production's.

Usage: .venv/bin/python scripts/tesla_spins_rtp.py [spins] [seed]
"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.reels import weighted_pick  # noqa: E402
from app.features.base import FeatureContext  # noqa: E402
from app.features.hold_and_win import HoldAndWinFeature  # noqa: E402
from app.seed import tesla_spins as seed  # noqa: E402
from app.simulator.rng import FastRNG  # noqa: E402


class _Grid:
    def __init__(self, reels):
        self.reels = reels


def main():
    spins = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
    rng = FastRNG(int(sys.argv[2]) if len(sys.argv) > 2 else 7)

    codes = [c for c, *_ in seed._SYMBOLS] + [seed.COIN_CODE]
    weights = [w for *_, w in seed._SYMBOLS] + [seed.COIN_WEIGHT]
    total = sum(weights)
    rtp_lines = sum((w / total) ** 3 * seed._PAYS[c]['3'] for c, _, _, w in seed._SYMBOLS)

    feature = HoldAndWinFeature()
    params = seed.HOLD_AND_WIN_PARAMS
    bet = Decimal(1)

    triggers = 0
    hw_total = Decimal(0)
    grands = 0
    jackpots = {}
    best = Decimal(0)
    for _ in range(spins):
        reels = [[codes[weighted_pick(weights, rng)[0]] for _ in range(3)] for _ in range(3)]
        ctx = FeatureContext(session_state={}, rng=rng, bet_amount=bet, symbols={}, grid=_Grid(reels))
        if not feature.is_triggered(ctx, params):
            continue
        triggers += 1
        res = feature.execute(ctx, params)
        hw_total += res.win_amount
        best = max(best, res.win_amount)
        if res.details.get('full_grid_jackpot'):
            grands += 1
        for coin in res.details['initial'] + [c for r in res.details['respins'] for c in r['landed']]:
            if not coin['kind'].isdigit():
                jackpots[coin['kind']] = jackpots.get(coin['kind'], 0) + 1

    rtp_hw = float(hw_total) / spins
    print(f'lines      {rtp_lines:.4f}  (closed form)')
    print(f'hold&win   {rtp_hw:.4f}  trigger 1/{spins / max(1, triggers):.0f}, '
          f'avg round {float(hw_total) / max(1, triggers):.1f}x, best {float(best):.0f}x')
    print(f'total RTP  {rtp_lines + rtp_hw:.4f}')
    print(f'grand 9/9  {grands} rounds; jackpot coins {jackpots}')


if __name__ == '__main__':
    main()
