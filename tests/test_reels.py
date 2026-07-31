from collections import Counter

import pytest

from app.engine.reels import collapse_and_refill, spin_reels, weighted_pick
from app.engine.rng import SecureRNG
from app.engine.types import PositionDraw, ReelSetConfig, SpinGrid, SymbolDef
from tests.fakes import FakeRNG


# --- weighted_pick: exact behaviour with a controlled RNG -----------------


def test_weighted_pick_rejects_all_zero_weights():
    with pytest.raises(ValueError):
        weighted_pick([0, 0, 0], FakeRNG([0]))


def test_weighted_pick_boundaries():
    weights = [3, 0, 5]  # cumulative: [0,3) -> idx0, [3,3) -> idx1 (never), [3,8) -> idx2
    assert weighted_pick(weights, FakeRNG([0]))[0] == 0
    assert weighted_pick(weights, FakeRNG([2]))[0] == 0
    assert weighted_pick(weights, FakeRNG([3]))[0] == 2
    assert weighted_pick(weights, FakeRNG([7]))[0] == 2


def test_weighted_pick_returns_raw_value_and_total():
    index, raw, total = weighted_pick([1, 1, 1], FakeRNG([1]))
    assert (index, raw, total) == (1, 1, 3)


# --- spin_reels: grid shape and proof -------------------------------------


def _simple_config(num_reels=5, num_rows=3):
    symbols = [
        SymbolDef(code="A", symbol_type="regular", weights=[1] * num_reels),
        SymbolDef(code="B", symbol_type="regular", weights=[1] * num_reels),
    ]
    return ReelSetConfig(num_reels=num_reels, num_rows=num_rows, symbols=symbols)


def test_spin_reels_produces_correct_grid_shape():
    grid = spin_reels(_simple_config(), SecureRNG())
    assert len(grid.reels) == 5
    assert all(len(column) == 3 for column in grid.reels)
    assert len(grid.draws) == 15


def test_spin_reels_rejects_empty_symbol_list():
    config = ReelSetConfig(num_reels=5, num_rows=3, symbols=[])
    with pytest.raises(ValueError):
        spin_reels(config, SecureRNG())


def test_zero_weight_symbol_never_appears():
    symbols = [
        SymbolDef(code="ALWAYS", symbol_type="regular", weights=[1, 1, 1, 1, 1]),
        SymbolDef(code="NEVER", symbol_type="regular", weights=[0, 0, 0, 0, 0]),
    ]
    config = ReelSetConfig(num_reels=5, num_rows=3, symbols=symbols)
    rng = SecureRNG()
    for _ in range(500):
        grid = spin_reels(config, rng)
        for column in grid.reels:
            assert "NEVER" not in column


def test_spin_reels_draw_proof_is_consistent_with_grid():
    grid = spin_reels(_simple_config(), SecureRNG())
    for draw in grid.draws:
        assert grid.reels[draw.reel][draw.row] == draw.symbol_code
        assert 0 <= draw.raw_value < draw.total_weight


# --- statistical distribution check ---------------------------------------


def test_symbol_distribution_matches_configured_weights():
    # Skewed weights on a single reel/row so we can check the empirical
    # split against the configured ratio without exact-equality flakiness.
    symbols = [
        SymbolDef(code="COMMON", symbol_type="regular", weights=[9]),
        SymbolDef(code="RARE", symbol_type="regular", weights=[1]),
    ]
    config = ReelSetConfig(num_reels=1, num_rows=1, symbols=symbols)
    rng = SecureRNG()

    draws = 50_000
    counts = Counter()
    for _ in range(draws):
        grid = spin_reels(config, rng)
        counts[grid.reels[0][0]] += 1

    expected_common = draws * 0.9
    se = (draws * 0.9 * 0.1) ** 0.5
    assert abs(counts["COMMON"] - expected_common) < 6 * se


# --- collapse_and_refill: avalanche gravity/refill (app/engine/avalanche.py) ---


def _one_reel_config(num_rows: int, code: str = "A") -> ReelSetConfig:
    return ReelSetConfig(num_reels=1, num_rows=num_rows, symbols=[SymbolDef(code=code, symbol_type="regular", weights=[1])])


def test_collapse_and_refill_gravity_preserves_survivor_order():
    # Rows 0 and 2 removed -> survivors ("keep1", "keep3") drop to the
    # bottom in their original top-to-bottom order, new symbols fill the top.
    grid = SpinGrid(reels=[["rm0", "keep1", "rm2", "keep3"]], draws=[])
    config = ReelSetConfig(num_reels=1, num_rows=4, symbols=[SymbolDef(code="A", symbol_type="regular", weights=[1])])
    result = collapse_and_refill(grid, config, FakeRNG([0, 0]), removed={(0, 0), (0, 2)})
    assert result.reels[0] == ["A", "A", "keep1", "keep3"]


def test_collapse_and_refill_leaves_untouched_reels_alone():
    symbols = [SymbolDef(code="x", symbol_type="regular", weights=[1, 1]), SymbolDef(code="y", symbol_type="regular", weights=[1, 1])]
    grid = SpinGrid(reels=[["x", "x"], ["y", "y"]], draws=[])
    config = ReelSetConfig(num_reels=2, num_rows=2, symbols=symbols)
    result = collapse_and_refill(grid, config, FakeRNG([0, 0]), removed={(0, 0), (0, 1)})
    assert result.reels[1] == ["y", "y"]


def test_collapse_and_refill_appends_new_draws_to_existing_audit_trail():
    original_draw = PositionDraw(reel=0, row=0, raw_value=0, total_weight=1, symbol_code="x")
    grid = SpinGrid(reels=[["x"]], draws=[original_draw])
    result = collapse_and_refill(grid, _one_reel_config(1, "x"), FakeRNG([0]), removed={(0, 0)})
    assert result.draws[0] is original_draw
    assert len(result.draws) == 2
    assert result.draws[1].reel == 0
    assert result.draws[1].row == 0
    assert result.draws[1].symbol_code == "x"


def test_collapse_and_refill_ignores_positions_not_present_on_the_reel():
    grid = SpinGrid(reels=[["x", "x"]], draws=[])
    # (0, 99) isn't a real position on a 2-row reel — should be a no-op, not a crash.
    result = collapse_and_refill(grid, _one_reel_config(2, "x"), FakeRNG([]), removed={(0, 99)})
    assert result.reels[0] == ["x", "x"]
    assert result.draws == []


def test_collapse_and_refill_removing_every_cell_redraws_the_whole_reel():
    grid = SpinGrid(reels=[["x", "x", "x"]], draws=[])
    result = collapse_and_refill(
        grid, _one_reel_config(3, "y"), FakeRNG([0, 0, 0]), removed={(0, 0), (0, 1), (0, 2)}
    )
    assert result.reels[0] == ["y", "y", "y"]
    assert len(result.draws) == 3
