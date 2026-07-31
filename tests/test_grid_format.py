from decimal import Decimal

from app.engine.types import CountWin, LineWin, SpinGrid
from app.services.grid_format import to_frontend_grid, winning_cells


def _grid():
    # reel-major: reels[reel][row]
    return SpinGrid(
        reels=[
            ["a0", "a1", "a2"],
            ["b0", "b1", "b2"],
            ["c0", "c1", "c2"],
            ["d0", "d1", "d2"],
            ["e0", "e1", "e2"],
        ],
        draws=[],
    )


def test_to_frontend_grid_transposes_reel_major_to_row_major():
    grid = _grid()
    result = to_frontend_grid(grid)
    assert result == [
        ["a0", "b0", "c0", "d0", "e0"],
        ["a1", "b1", "c1", "d1", "e1"],
        ["a2", "b2", "c2", "d2", "e2"],
    ]


def test_winning_cells_uses_row_col_symbol_shape():
    grid = _grid()
    line_win = LineWin(
        payline_index=1, symbol_code="a0", count=1,
        payout_multiplier=Decimal(1), win_amount=Decimal(1), positions=((0, 0),),
    )
    cells = winning_cells(grid, [line_win], [])
    assert cells == [{"row": 0, "col": 0, "symbol": "a0"}]


def test_winning_cells_dedupes_overlap_between_line_and_count_wins():
    grid = _grid()
    line_win = LineWin(
        payline_index=1, symbol_code="a0", count=1,
        payout_multiplier=Decimal(1), win_amount=Decimal(1), positions=((0, 0),),
    )
    count_win = CountWin(
        symbol_code="a0", count=1, payout_multiplier=Decimal(1), win_amount=Decimal(1),
        positions=((0, 0), (1, 1)),
    )
    cells = winning_cells(grid, [line_win], [count_win])
    assert cells == [
        {"row": 0, "col": 0, "symbol": "a0"},
        {"row": 1, "col": 1, "symbol": "b1"},
    ]
