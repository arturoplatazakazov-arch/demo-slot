from typing import Iterable, Sequence

from app.engine.rng import RNGProvider
from app.engine.types import PositionDraw, ReelSetConfig, SpinGrid


def weighted_pick(weights: Sequence[int], rng: RNGProvider) -> tuple[int, int, int]:
    """Pick an index from `weights` proportionally to each weight.

    Returns (chosen_index, raw_value, total_weight) — the raw draw is kept
    so callers can log it for audit (TZ §10).
    """
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")

    raw = rng.randbelow(total)
    cumulative = 0
    for index, weight in enumerate(weights):
        cumulative += weight
        if raw < cumulative:
            return index, raw, total

    raise AssertionError("unreachable: raw draw exceeded cumulative weight")  # pragma: no cover


def spin_reels(config: ReelSetConfig, rng: RNGProvider) -> SpinGrid:
    """Generate one spin result: for every position independently, pick a
    symbol on that reel weighted by its configured reel weight (TZ §4.1).
    No physical reel-strip is modeled — positions on a reel are drawn with
    replacement, which the TZ explicitly allows ("не обязательна, если не
    потребуется имитация reel strip")."""
    if not config.symbols:
        raise ValueError("reel config has no symbols")

    reels: list[list[str]] = []
    draws: list[PositionDraw] = []

    for reel_index in range(config.num_reels):
        weights = [symbol.weights[reel_index] for symbol in config.symbols]
        column: list[str] = []
        for row_index in range(config.num_rows):
            chosen_index, raw_value, total_weight = weighted_pick(weights, rng)
            symbol_code = config.symbols[chosen_index].code
            column.append(symbol_code)
            draws.append(
                PositionDraw(
                    reel=reel_index,
                    row=row_index,
                    raw_value=raw_value,
                    total_weight=total_weight,
                    symbol_code=symbol_code,
                )
            )
        reels.append(column)

    return SpinGrid(reels=reels, draws=draws)


def collapse_and_refill(
    grid: SpinGrid, config: ReelSetConfig, rng: RNGProvider, removed: Iterable[tuple[int, int]]
) -> SpinGrid:
    """One avalanche cascade step's board update (app/engine/avalanche.py):
    per reel, drop the surviving symbols down to fill the gap left by
    `removed` (reel, row) positions — their relative top-to-bottom order is
    preserved — then draw fresh symbols, weighted the same as a normal spin
    draw, to fill the now-empty cells at the top of that reel.

    `removed` positions not actually present in `grid` are ignored (no-op),
    so a caller can pass exactly the union of this step's winning positions
    without first checking for cross-symbol overlap."""
    removed_set = set(removed)
    reels: list[list[str]] = []
    draws: list[PositionDraw] = list(grid.draws)

    for reel_index, column in enumerate(grid.reels):
        survivors = [
            code for row_index, code in enumerate(column) if (reel_index, row_index) not in removed_set
        ]
        num_missing = len(column) - len(survivors)

        weights = [symbol.weights[reel_index] for symbol in config.symbols]
        new_symbols: list[str] = []
        for row_index in range(num_missing):
            chosen_index, raw_value, total_weight = weighted_pick(weights, rng)
            symbol_code = config.symbols[chosen_index].code
            new_symbols.append(symbol_code)
            draws.append(
                PositionDraw(
                    reel=reel_index,
                    row=row_index,
                    raw_value=raw_value,
                    total_weight=total_weight,
                    symbol_code=symbol_code,
                )
            )

        reels.append(new_symbols + survivors)

    return SpinGrid(reels=reels, draws=draws)
