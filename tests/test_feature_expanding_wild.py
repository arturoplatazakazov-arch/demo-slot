from decimal import Decimal

from app.engine.types import SpinGrid
from app.features.base import FeatureContext
from app.features.expanding_wild import ExpandingWildFeature
from tests.fakes import FakeRNG


def _grid(*columns):
    return SpinGrid(reels=[list(c) for c in columns], draws=[])


def test_is_triggered_false_with_no_wild_and_no_carried_walker():
    grid = _grid(["a", "b", "c"], ["a", "b", "c"])
    ctx = FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid)
    assert ExpandingWildFeature().is_triggered(ctx, {}) is False


def test_is_triggered_true_when_wild_present():
    grid = _grid(["a", "wild", "c"], ["a", "b", "c"])
    ctx = FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid)
    assert ExpandingWildFeature().is_triggered(ctx, {}) is True


def test_is_triggered_true_from_carried_walker_even_without_fresh_wild():
    grid = _grid(["a", "b", "c"], ["a", "b", "c"])
    ctx = FeatureContext(
        session_state={"walking_wilds": [1]}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid
    )
    assert ExpandingWildFeature().is_triggered(ctx, {}) is True


def test_execute_expands_natural_landing_and_schedules_next_walker():
    # 3 reels x 2 rows; wild lands on reel 1 only.
    grid = _grid(["a", "b"], ["wild", "x"], ["c", "d"])
    ctx = FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid)
    result = ExpandingWildFeature().execute(ctx, {"trigger_symbol_code": "wild"})

    assert grid.reels[1] == ["wild", "wild"]
    assert result.win_amount == Decimal(0)
    assert result.state_patch == {"walking_wilds": [2]}
    assert result.details["events"] == [{"reel": 1, "event": "expanded"}]


def test_execute_walker_on_last_reel_expires_instead_of_walking_off():
    # 3 reels x 2 rows; a walker carried over sits on the last reel (index 2).
    grid = _grid(["a", "b"], ["c", "d"], ["e", "f"])
    ctx = FeatureContext(
        session_state={"walking_wilds": [2]}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid
    )
    result = ExpandingWildFeature().execute(ctx, {"trigger_symbol_code": "wild"})

    assert grid.reels[2] == ["wild", "wild"]
    assert result.state_patch == {"walking_wilds": []}
    assert result.details["events"] == [
        {"reel": 2, "event": "walked"},
        {"reel": 2, "event": "expired"},
    ]


def test_execute_walker_mid_grid_re_expands_and_advances_right():
    grid = _grid(["a", "b"], ["c", "d"], ["e", "f"])
    ctx = FeatureContext(
        session_state={"walking_wilds": [0]}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid
    )
    result = ExpandingWildFeature().execute(ctx, {"trigger_symbol_code": "wild"})

    assert grid.reels[0] == ["wild", "wild"]
    assert result.state_patch == {"walking_wilds": [1]}
    assert result.details["events"] == [{"reel": 0, "event": "walked"}]


def test_execute_respects_walk_enabled_false():
    grid = _grid(["a", "b"], ["wild", "x"], ["c", "d"])
    ctx = FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid)
    result = ExpandingWildFeature().execute(
        ctx, {"trigger_symbol_code": "wild", "walk_enabled": False}
    )

    assert result.state_patch == {"walking_wilds": []}
    assert result.details["events"] == [{"reel": 1, "event": "expanded"}]


def test_config_schema_lists_expected_fields():
    schema = ExpandingWildFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "trigger_symbol_code" in schema["properties"]


def test_execute_missed_expand_roll_leaves_grid_untouched():
    # East Discovery: expand_chance=0.5 — a miss (raw 999 >= the 500 hit
    # threshold) leaves the natural wild as a normal single-cell symbol, no
    # event, and it never becomes an active walker.
    grid = _grid(["a", "b"], ["wild", "x"], ["c", "d"])
    ctx = FeatureContext(session_state={}, rng=FakeRNG([999]), bet_amount=Decimal("1"), grid=grid)
    result = ExpandingWildFeature().execute(
        ctx, {"trigger_symbol_code": "wild", "expand_chance": 0.5}
    )

    assert grid.reels[1] == ["wild", "x"]  # unchanged, not expanded
    assert result.details["events"] == []
    assert result.state_patch == {"walking_wilds": []}


def test_execute_missed_walk_roll_keeps_walker_on_the_same_reel():
    # walk_chance=0.5 — a miss (raw 999) keeps the already-expanded walker on
    # reel 1 for another spin instead of advancing to reel 2.
    grid = _grid(["a", "b"], ["c", "d"], ["e", "f"])
    ctx = FeatureContext(
        session_state={"walking_wilds": [1]}, rng=FakeRNG([999]), bet_amount=Decimal("1"), grid=grid
    )
    result = ExpandingWildFeature().execute(
        ctx, {"trigger_symbol_code": "wild", "walk_chance": 0.5}
    )

    assert grid.reels[1] == ["wild", "wild"]  # still placed/expanded this spin
    assert result.state_patch == {"walking_wilds": [1]}  # stayed on reel 1, not 2
    assert result.details["events"] == [{"reel": 1, "event": "walked"}]


def test_execute_hit_walk_roll_from_last_reel_still_expires():
    # walk_chance=0.5 — a hit (raw 0 < the 500 threshold) tries to advance
    # off the last reel (index 2 of 3), which still expires normally.
    grid = _grid(["a", "b"], ["c", "d"], ["e", "f"])
    ctx = FeatureContext(
        session_state={"walking_wilds": [2]}, rng=FakeRNG([0]), bet_amount=Decimal("1"), grid=grid
    )
    result = ExpandingWildFeature().execute(
        ctx, {"trigger_symbol_code": "wild", "walk_chance": 0.5}
    )

    assert result.state_patch == {"walking_wilds": []}
    assert result.details["events"] == [
        {"reel": 2, "event": "walked"},
        {"reel": 2, "event": "expired"},
    ]
