from decimal import Decimal

from app.engine.types import SpinGrid
from app.features.base import FeatureContext
from app.features.hold_and_win import HoldAndWinFeature
from tests.fakes import FakeRNG


def _grid(*columns):
    return SpinGrid(reels=[list(c) for c in columns], draws=[])


def test_is_triggered_on_enough_coin_symbols():
    grid = _grid(["COIN", "x"], ["COIN", "x"])
    feature = HoldAndWinFeature()
    ctx = FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid)
    assert feature.is_triggered(ctx, {"trigger_count": 2}) is True
    assert feature.is_triggered(ctx, {"trigger_count": 3}) is False


def test_execute_fills_grid_when_every_respin_lands_a_coin():
    # 2x2 grid, 2 initial coins, respins always land a coin -> grid fills.
    grid = _grid(["COIN", "x"], ["COIN", "x"])
    ctx = FeatureContext(
        session_state={}, rng=FakeRNG([0] * 20), bet_amount=Decimal("2"), grid=grid
    )
    config = {
        "respin_count": 1,
        "coin_value_weights": {"1": 1},
        "respin_land_weights": {"blank": 0, "coin": 1},
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.triggered is True
    assert result.details["full_grid"] is True
    assert result.details["locked_count"] == 4
    assert result.win_amount == Decimal(4) * Decimal(2)  # 4 locked coins x value 1 x bet 2


def test_execute_stops_after_respins_exhausted_without_new_coins():
    grid = _grid(["COIN", "x"], ["x", "x"])
    ctx = FeatureContext(
        session_state={}, rng=FakeRNG([0] * 20), bet_amount=Decimal("3"), grid=grid
    )
    config = {
        "respin_count": 2,
        "coin_value_weights": {"1": 1},
        "respin_land_weights": {"blank": 1, "coin": 0},
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.details["locked_count"] == 1
    assert result.details["full_grid"] is False
    assert result.win_amount == Decimal(1) * Decimal(3)


def test_config_schema_lists_expected_fields():
    schema = HoldAndWinFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "respin_count" in schema["properties"]


def test_start_empty_does_not_lock_trigger_positions():
    # 2 initial COIN positions would normally lock as coins (see
    # test_execute_fills_grid_when_every_respin_lands_a_coin) — start_empty
    # skips that, and with respins never landing, nothing locks at all.
    grid = _grid(["COIN", "x"], ["COIN", "x"])
    ctx = FeatureContext(session_state={}, rng=FakeRNG([0] * 20), bet_amount=Decimal("2"), grid=grid)
    config = {
        "start_empty": True,
        "respin_count": 2,
        "coin_value_weights": {"1": 1},
        "respin_land_weights": {"blank": 1, "coin": 0},
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.details["locked_count"] == 0
    assert result.win_amount == Decimal(0)
    assert result.details["respins"] == [{"landed": []}, {"landed": []}]


def test_guaranteed_coin_count_mode_ends_only_when_grid_fills():
    # East Discovery's newer mode: respin_coin_count_weights set ->
    # respin_count/land_weights are ignored entirely, and the round runs
    # until the grid fills, however many respins that takes.
    grid = _grid(["x", "x"], ["x", "x"])  # 2 reels x 2 rows = 4 cells
    rng = FakeRNG([0] * 10)
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal("1"), grid=grid)
    config = {
        "start_empty": True,
        "respin_count": 1,  # deliberately tiny — must be ignored in this mode
        "coin_value_weights": {"1": 1},
        "respin_coin_count_weights": {"2": 1},  # always lands exactly 2 new coins
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.details["full_grid"] is True
    assert result.details["locked_count"] == 4
    respins = result.details["respins"]
    assert len(respins) == 2
    assert all(len(r["landed"]) == 2 for r in respins)
    assert result.win_amount == Decimal(4) * Decimal(1)  # 4 coins x value 1 x bet 1


def test_guaranteed_coin_count_mode_supports_a_no_multiplier_value():
    grid = _grid(["x", "x"], ["x", "x"])
    rng = FakeRNG([0] * 10)
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal("5"), grid=grid)
    config = {
        "start_empty": True,
        "coin_value_weights": {"0": 1},  # every landed coin has no multiplier
        "respin_coin_count_weights": {"2": 1},
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.details["locked_count"] == 4  # still sticks to the grid
    assert result.win_amount == Decimal(0)  # but contributes nothing to the payout


def test_guaranteed_coin_count_mode_caps_count_by_remaining_empty_cells():
    grid = _grid(["x", "x", "x"])  # 1 reel x 3 rows = 3 cells
    rng = FakeRNG([0] * 8)
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal("1"), grid=grid)
    config = {
        "start_empty": True,
        "coin_value_weights": {"1": 1},
        "respin_coin_count_weights": {"2": 1},  # always wants 2, but only 1 cell is left for respin 2
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.details["full_grid"] is True
    assert result.details["locked_count"] == 3
    respins = result.details["respins"]
    assert len(respins) == 2
    assert len(respins[0]["landed"]) == 2
    assert len(respins[1]["landed"]) == 1  # capped: only 1 empty cell remained


def test_respins_log_extends_past_respin_count_when_a_late_landing_resets_it():
    # 2 reels x 1 row: (0,0) then (1,0), checked in that order each respin.
    grid = _grid(["x"], ["x"])
    # respin 1: (0,0) land-check -> blank (0); (1,0) land-check -> coin (1),
    # then its value draw (0, only key). respin 2 (counter reset to 1):
    # (0,0) land-check -> blank (0); (1,0) already locked, skipped.
    rng = FakeRNG([0, 1, 0, 0])
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal("1"), grid=grid)
    config = {
        "start_empty": True,
        "respin_count": 1,
        "coin_value_weights": {"1": 1},
        "respin_land_weights": {"blank": 1, "coin": 1},
    }
    result = HoldAndWinFeature().execute(ctx, config)

    assert result.details["locked_count"] == 1
    respins = result.details["respins"]
    assert len(respins) == 2  # exceeds respin_count=1 because respin 1's landing reset the counter
    # `kind` is the coin_value_weights key the value was drawn from — a plain
    # number here, a tier name for a game with named jackpot_values.
    assert respins[0]["landed"] == [{"reel": 1, "row": 0, "value": "1", "kind": "1"}]
    assert respins[1]["landed"] == []
