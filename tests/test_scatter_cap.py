from app.services.scatter_cap import cap_symbol_per_reel
from app.engine.types import PositionDraw, ReelSetConfig, SpinGrid, SymbolDef
from tests.fakes import FakeRNG

SYMBOLS = [
    SymbolDef(code="scatter", symbol_type="scatter", weights=[1, 1, 1, 1, 1]),
    SymbolDef(code="filler", symbol_type="regular", weights=[1, 1, 1, 1, 1]),
]
REEL_SET = ReelSetConfig(num_reels=5, num_rows=3, symbols=SYMBOLS)


def _grid(*columns):
    draws = [PositionDraw(reel=0, row=0, raw_value=0, total_weight=1, symbol_code="noop")]
    return SpinGrid(reels=[list(c) for c in columns], draws=draws)


def test_leaves_grid_untouched_when_within_the_cap():
    grid = _grid(
        ["scatter", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
    )
    result = cap_symbol_per_reel(grid, REEL_SET, FakeRNG([]), "scatter", max_per_reel=1)
    assert result is grid


def test_redraws_excess_occurrences_on_the_same_reel():
    grid = _grid(
        ["scatter", "scatter", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
    )
    result = cap_symbol_per_reel(grid, REEL_SET, FakeRNG([0]), "scatter", max_per_reel=1)

    reel0 = result.reels[0]
    assert reel0.count("scatter") == 1
    assert reel0[0] == "scatter"  # first occurrence kept
    assert reel0[1] == "filler"  # excess replaced, never redrawn as scatter itself
    assert len(result.draws) == len(grid.draws) + 1


def test_caps_three_occurrences_down_to_the_limit():
    grid = _grid(
        ["scatter", "scatter", "scatter"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
        ["filler", "filler", "filler"],
    )
    result = cap_symbol_per_reel(grid, REEL_SET, FakeRNG([0, 0]), "scatter", max_per_reel=1)
    assert result.reels[0].count("scatter") == 1
    assert len(result.draws) == len(grid.draws) + 2


def test_unknown_symbol_code_is_a_no_op():
    grid = _grid(["scatter", "scatter", "filler"], *[["filler"] * 3] * 4)
    result = cap_symbol_per_reel(grid, REEL_SET, FakeRNG([]), "does_not_exist", max_per_reel=1)
    assert result is grid
