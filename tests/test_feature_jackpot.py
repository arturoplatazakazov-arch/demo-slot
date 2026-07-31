from decimal import Decimal

import pytest

from app.features.base import FeatureContext
from app.features.jackpot import JackpotFeature
from tests.fakes import FakeRNG

_LEVELS = [
    {"id": "mini", "weight": 1, "value_multiplier": 20},
    {"id": "grand", "weight": 1, "value_multiplier": 1000},
]
_CONFIG = {"odds_denominator": 10, "levels": _LEVELS}


def _ctx(rng_values, session_state=None, bet_amount="1"):
    return FeatureContext(
        session_state=session_state if session_state is not None else {},
        rng=FakeRNG(rng_values),
        bet_amount=Decimal(bet_amount),
    )


def test_is_triggered_picks_a_level_and_stashes_it():
    ctx = _ctx([0])  # cumulative: mini=[0,1) -> raw 0 hits mini
    assert JackpotFeature().is_triggered(ctx, _CONFIG) is True
    assert ctx.session_state["_pending_jackpot_level_index"] == 0


def test_is_triggered_false_when_draw_lands_in_no_trigger_bucket():
    ctx = _ctx([9])  # weights [1,1,8] -> raw 9 lands in the no-trigger bucket
    assert JackpotFeature().is_triggered(ctx, _CONFIG) is False
    assert "_pending_jackpot_level_index" not in ctx.session_state


def test_is_triggered_returns_false_with_no_levels_configured():
    ctx = _ctx([])
    assert JackpotFeature().is_triggered(ctx, {"levels": []}) is False


def test_execute_pays_the_level_that_was_pending():
    ctx = _ctx([1], bet_amount="2")  # raw 1 -> cumulative mini=[0,1) grand=[1,2) -> grand
    feature = JackpotFeature()
    assert feature.is_triggered(ctx, _CONFIG) is True
    result = feature.execute(ctx, _CONFIG)

    assert result.triggered is True
    assert result.details["level_id"] == "grand"
    assert result.win_amount == Decimal(1000) * Decimal(2)
    assert "_pending_jackpot_level_index" not in ctx.session_state  # popped, no double-pay


def test_execute_without_pending_level_does_not_pay():
    ctx = _ctx([])
    result = JackpotFeature().execute(ctx, _CONFIG)
    assert result.triggered is False
    assert result.details["reason"] == "no_pending_level"


def test_weights_exceeding_denominator_is_a_config_error():
    ctx = _ctx([0])
    bad_config = {"odds_denominator": 1, "levels": _LEVELS}  # weights sum to 2 > denominator 1
    with pytest.raises(ValueError):
        JackpotFeature().is_triggered(ctx, bad_config)


def test_config_schema_lists_expected_fields():
    schema = JackpotFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "levels" in schema["properties"]
