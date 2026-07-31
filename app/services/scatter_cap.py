"""Reel-level cap on a symbol's appearance (product rule: at most 1 scatter
per reel, hence at most 5 on screen for a 5-reel grid).

`spin_reels` (app/engine/reels.py) draws every position independently per
reel weight — it has no notion of "at most N per reel" and TZ §4.1
explicitly allows skipping a physical reel-strip model. Rather than bolt a
same-reel exclusion rule onto the engine's per-position draw (which the
engine isn't designed for and stage 5 was told not to modify), this reduces
extra occurrences after the fact: redraw excess positions with the capped
symbol's weight zeroed out, using the same RNG and `weighted_pick` the
engine itself uses, so the result is still a legitimate weighted draw over
the remaining symbols. The proper long-term fix, if this needs to be
airtight, is a real reel-strip model in the engine — flagged as an open
item rather than done silently here.
"""

import dataclasses

from app.engine.reels import weighted_pick
from app.engine.rng import RNGProvider
from app.engine.types import PositionDraw, ReelSetConfig, SpinGrid


def cap_symbol_per_reel(
    grid: SpinGrid, reel_set: ReelSetConfig, rng: RNGProvider, symbol_code: str, max_per_reel: int
) -> SpinGrid:
    symbols_by_code = {s.code: s for s in reel_set.symbols}
    if symbol_code not in symbols_by_code:
        return grid

    new_reels: list[list[str]] = [list(column) for column in grid.reels]
    extra_draws: list[PositionDraw] = []

    for reel_index, column in enumerate(new_reels):
        positions = [row for row, code in enumerate(column) if code == symbol_code]
        if len(positions) <= max_per_reel:
            continue

        weights = [
            0 if s.code == symbol_code else s.weights[reel_index] for s in reel_set.symbols
        ]
        for row in positions[max_per_reel:]:
            chosen_index, raw_value, total_weight = weighted_pick(weights, rng)
            replacement = reel_set.symbols[chosen_index].code
            column[row] = replacement
            extra_draws.append(
                PositionDraw(
                    reel=reel_index, row=row, raw_value=raw_value, total_weight=total_weight,
                    symbol_code=replacement,
                )
            )

    if not extra_draws:
        return grid
    return dataclasses.replace(grid, reels=new_reels, draws=[*grid.draws, *extra_draws])
