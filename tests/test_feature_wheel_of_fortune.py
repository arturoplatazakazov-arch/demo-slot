from decimal import Decimal

from app.engine.types import SpinGrid
from app.features.base import FeatureContext
from app.features.wheel_of_fortune import WheelOfFortuneFeature
from tests.fakes import FakeRNG


def _grid(*columns):
    return SpinGrid(reels=[list(c) for c in columns], draws=[])


def _ctx(grid, rng_values=(), bet="1"):
    return FeatureContext(
        session_state={}, rng=FakeRNG(list(rng_values)), bet_amount=Decimal(bet), grid=grid
    )


# Two segments with weight 1 each: raw draw 0 -> index 0, raw draw 1 -> index 1.
_TWO_SEGMENTS = {
    "segments": [
        {"type": "multiplier", "value": 5, "weight": 1},
        {"type": "free_spins", "weight": 1},
    ]
}


def test_is_triggered_on_enough_wheel_symbols():
    grid = _grid(["wof", "x"], ["x", "wof"], ["wof", "x"])
    feature = WheelOfFortuneFeature()
    ctx = _ctx(grid)
    assert feature.is_triggered(ctx, {"trigger_count": 3}) is True
    assert feature.is_triggered(ctx, {"trigger_count": 4}) is False


def test_is_triggered_counts_only_the_configured_symbol():
    grid = _grid(["scatter", "scatter"], ["scatter", "x"])
    ctx = _ctx(grid)
    assert WheelOfFortuneFeature().is_triggered(ctx, {"trigger_count": 3}) is False


def test_not_triggered_without_a_grid():
    ctx = FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=None)
    assert WheelOfFortuneFeature().is_triggered(ctx, {}) is False


def test_multiplier_segment_pays_value_times_the_whole_bet():
    ctx = _ctx(_grid(["wof"]), rng_values=[0], bet="10000")
    result = WheelOfFortuneFeature().execute(ctx, _TWO_SEGMENTS)

    assert result.triggered is True
    assert result.details["prize_type"] == "multiplier"
    assert result.details["segment_index"] == 0
    assert result.details["multiplier"] == 5
    assert result.win_amount == Decimal(5) * Decimal(10000)


def test_free_spins_segment_pays_nothing_itself():
    # The round is the prize — the spin service hands off to the free_spins
    # module, so the wheel itself must not also award cash.
    ctx = _ctx(_grid(["wof"]), rng_values=[1], bet="10000")
    result = WheelOfFortuneFeature().execute(ctx, _TWO_SEGMENTS)

    assert result.details["prize_type"] == "free_spins"
    assert result.details["segment_index"] == 1
    assert result.win_amount == Decimal(0)
    assert "multiplier" not in result.details


def test_segments_go_out_without_their_weights():
    # The client needs the labels in drum order; exposing the weights would
    # let a player read the odds straight off the wire.
    ctx = _ctx(_grid(["wof"]), rng_values=[0], bet="1")
    result = WheelOfFortuneFeature().execute(ctx, _TWO_SEGMENTS)

    assert result.details["segments"] == [
        {"type": "multiplier", "value": 5},
        {"type": "free_spins", "value": None},
    ]


def test_weights_drive_the_draw():
    # First segment carries all the weight -> every draw lands on it.
    config = {
        "segments": [
            {"type": "multiplier", "value": 2, "weight": 9},
            {"type": "multiplier", "value": 8, "weight": 1},
        ]
    }
    for raw in range(9):
        ctx = _ctx(_grid(["wof"]), rng_values=[raw], bet="1")
        assert WheelOfFortuneFeature().execute(ctx, config).details["segment_index"] == 0
    ctx = _ctx(_grid(["wof"]), rng_values=[9], bet="1")
    assert WheelOfFortuneFeature().execute(ctx, config).details["segment_index"] == 1


def test_defaults_cover_the_eight_slots_the_artwork_has():
    # The drum art has exactly 8 bullet slots; the shipped default set must
    # fill them all, or the client would label a blank slot.
    ctx = _ctx(_grid(["wof"]), rng_values=[0], bet="1")
    segments = WheelOfFortuneFeature().execute(ctx, {}).details["segments"]
    assert len(segments) == 8
    assert sum(1 for s in segments if s["type"] == "free_spins") == 1
    assert [s["value"] for s in segments if s["type"] == "multiplier"] == [2, 3, 4, 5, 6, 7, 8]
