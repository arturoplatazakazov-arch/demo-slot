from decimal import Decimal

from app.engine.types import SpinGrid
from app.features.base import FeatureContext
from app.features.free_spins import FreeSpinsFeature
from tests.fakes import FakeRNG


def _grid(*columns):
    return SpinGrid(reels=[list(c) for c in columns], draws=[])


def _ctx(grid=None, session_state=None):
    return FeatureContext(
        session_state=session_state if session_state is not None else {},
        rng=FakeRNG([]),
        bet_amount=Decimal("1"),
        grid=grid,
    )


def test_triggers_on_enough_scatters():
    grid = _grid(["SCAT", "x", "x"], ["SCAT", "x", "x"], ["SCAT", "x", "x"], ["x", "x", "x"], ["x", "x", "x"])
    feature = FreeSpinsFeature()
    assert feature.is_triggered(_ctx(grid=grid), {}) is True


def test_does_not_trigger_below_threshold():
    grid = _grid(["SCAT", "x", "x"], ["SCAT", "x", "x"], ["x", "x", "x"], ["x", "x", "x"], ["x", "x", "x"])
    feature = FreeSpinsFeature()
    assert feature.is_triggered(_ctx(grid=grid), {}) is False


def test_custom_trigger_symbol_and_count():
    grid = _grid(["BONUS", "x", "x"], ["BONUS", "x", "x"], ["x", "x", "x"], ["x", "x", "x"], ["x", "x", "x"])
    feature = FreeSpinsFeature()
    config = {"trigger_symbol_code": "BONUS", "trigger_count": 2}
    assert feature.is_triggered(_ctx(grid=grid), config) is True


def test_retrigger_disabled_blocks_second_trigger_while_active():
    grid = _grid(["SCAT", "x", "x"], ["SCAT", "x", "x"], ["SCAT", "x", "x"], ["x", "x", "x"], ["x", "x", "x"])
    feature = FreeSpinsFeature()
    ctx = _ctx(grid=grid, session_state={"free_spins_remaining": 5})
    assert feature.is_triggered(ctx, {"retrigger_enabled": False}) is False
    assert feature.is_triggered(ctx, {"retrigger_enabled": True}) is True


def test_execute_awards_spins_and_stacks_on_existing_remaining():
    feature = FreeSpinsFeature()
    ctx = _ctx(session_state={"free_spins_remaining": 4})
    result = feature.execute(ctx, {"spins_awarded": 10, "win_multiplier": 2})

    assert result.triggered is True
    assert result.win_amount == Decimal(0)
    assert result.state_patch["free_spins_remaining"] == 14
    assert result.state_patch["free_spins_multiplier"] == "2"
    assert result.details["spins_awarded"] == 10


def test_execute_awards_by_scatter_count_when_table_configured():
    grid = _grid(["SCAT", "x", "x"], ["SCAT", "x", "x"], ["SCAT", "x", "x"], ["SCAT", "x", "x"], ["x", "x", "x"])
    feature = FreeSpinsFeature()
    config = {"spins_awarded_by_count": {"3": 5, "4": 7, "5": 9}}

    result = feature.execute(_ctx(grid=grid), config)  # 4 scatters landed
    assert result.details["spins_awarded"] == 7
    assert result.state_patch["free_spins_remaining"] == 7


def test_execute_falls_back_to_flat_award_when_count_missing_from_table():
    grid = _grid(["SCAT", "x", "x"], ["SCAT", "x", "x"], ["SCAT", "x", "x"], ["x", "x", "x"], ["x", "x", "x"])
    feature = FreeSpinsFeature()
    config = {"spins_awarded_by_count": {"4": 7, "5": 9}, "spins_awarded": 10}

    result = feature.execute(_ctx(grid=grid), config)  # 3 scatters, not in the table
    assert result.details["spins_awarded"] == 10


def test_config_schema_lists_expected_fields():
    schema = FreeSpinsFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "trigger_count" in schema["properties"]
