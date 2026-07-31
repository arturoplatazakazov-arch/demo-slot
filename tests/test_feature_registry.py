from dataclasses import dataclass

from app.features import default_registry
from app.features.registry import FeatureRegistry


@dataclass
class FakeFeatureConfig:
    feature_type: str
    enabled: bool
    params: dict


def test_default_registry_has_all_five_stage_one_features():
    expected = {"free_spins", "hold_and_win", "bonus_buy", "gamble", "jackpot"}
    assert expected <= set(default_registry.all_feature_ids())


def test_active_features_skips_disabled_and_unknown_types():
    registry = default_registry  # engine never hardcodes the feature list — it asks the registry
    configs = [
        FakeFeatureConfig(feature_type="free_spins", enabled=True, params={"trigger_count": 3}),
        FakeFeatureConfig(feature_type="hold_and_win", enabled=False, params={}),
        FakeFeatureConfig(feature_type="not_a_real_feature", enabled=True, params={}),
    ]
    active = registry.active_features(configs)

    assert len(active) == 1
    assert active[0].feature.feature_id == "free_spins"
    assert active[0].params == {"trigger_count": 3}


def test_registering_a_custom_feature_without_touching_the_core():
    from app.features.base import BonusFeature, FeatureResult

    class NoopFeature(BonusFeature):
        feature_id = "noop"

        def is_triggered(self, spin_result, config):
            return False

        def execute(self, game_state, config):
            return FeatureResult(feature_id=self.feature_id, triggered=False)

        def get_config_schema(self):
            return {"type": "object", "properties": {}}

    registry = FeatureRegistry()  # a fresh registry, not the shared default
    registry.register(NoopFeature())
    assert registry.get("noop") is not None
    assert registry.get("does_not_exist") is None
