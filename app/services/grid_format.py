"""Grid/coordinate conversion between the engine's internal shape and the
frontend's contract (front/js/slot.js SYMBOL_LAYOUT): the engine stores
`SpinGrid.reels[reel_index][row_index]` (reel-major); the frontend wants
row-major, 3 rows of 5 symbols each, top to bottom."""

from typing import Sequence

from app.engine.types import CountWin, LineWin, SpinGrid


def to_frontend_grid(grid: SpinGrid) -> list[list[str]]:
    num_rows = len(grid.reels[0]) if grid.reels else 0
    return [[grid.reels[reel][row] for reel in range(len(grid.reels))] for row in range(num_rows)]


def winning_cells(
    grid: SpinGrid, line_wins: Sequence[LineWin], count_wins: Sequence[CountWin]
) -> list[dict]:
    """Union of every (reel, row) cell that contributed to a payout, as
    {"row", "col", "symbol"} — col == reel index. Deduped, since two
    paylines can cross the same cell."""
    seen: dict[tuple[int, int], str] = {}
    for win in line_wins:
        for reel, row in win.positions:
            seen[(row, reel)] = grid.reels[reel][row]
    for win in count_wins:
        for reel, row in win.positions:
            seen[(row, reel)] = grid.reels[reel][row]

    return [{"row": row, "col": col, "symbol": symbol} for (row, col), symbol in sorted(seen.items())]
