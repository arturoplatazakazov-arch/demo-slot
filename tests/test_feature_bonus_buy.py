from decimal import Decimal

from app.features.base import FeatureContext
from app.features.bonus_buy import BonusBuyFeature
from tests.fakes import FakeRNG


def _ctx(bet_amount="1"):
    return FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal(bet_amount))


def test_never_triggers_naturally_from_a_spin():
    assert BonusBuyFeature().is_triggered(_ctx(), {}) is False


def test_execute_computes_cost_from_bet_and_multiplier():
    result = BonusBuyFeature().execute(_ctx(bet_amount="2"), {"cost_multiplier": 100, "target_feature_id": "free_spins"})
    assert result.triggered is True
    assert result.details["cost"] == str(Decimal(200))
    assert result.details["target_feature_id"] == "free_spins"


def test_execute_uses_default_target_feature():
    result = BonusBuyFeature().execute(_ctx(bet_amount="1"), {})
    assert result.details["target_feature_id"] == "free_spins"


def test_config_schema_lists_expected_fields():
    schema = BonusBuyFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "cost_multiplier" in schema["properties"]
