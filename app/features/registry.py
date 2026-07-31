from dataclasses import dataclass
from typing import Iterable, Protocol

from app.features.base import BonusFeature


class FeatureConfigLike(Protocol):
    """Structural type for whatever carries a feature's admin config — the
    `FeatureConfig` ORM row in production, a plain object in tests."""

    feature_type: str
    enabled: bool
    params: dict


@dataclass(frozen=True)
class ActiveFeature:
    feature: BonusFeature
    params: dict


class FeatureRegistry:
    """Maps `feature_type` strings to `BonusFeature` implementations. The
    engine never hardcodes which features exist (TZ §6.1) — it asks the
    registry for whatever a game's `FeatureConfig` rows say is enabled."""

    def __init__(self) -> None:
        self._features: dict[str, BonusFeature] = {}

    def register(self, feature: BonusFeature) -> None:
        self._features[feature.feature_id] = feature

    def get(self, feature_id: str) -> BonusFeature | None:
        return self._features.get(feature_id)

    def all_feature_ids(self) -> list[str]:
        return list(self._features.keys())

    def active_features(self, feature_configs: Iterable[FeatureConfigLike]) -> list[ActiveFeature]:
        """Resolve a game's enabled `FeatureConfig` rows to their
        implementations. Unknown `feature_type` values (e.g. a config
        referencing a module that was never registered) are skipped rather
        than crashing the engine — an admin mistake shouldn't take a game
        down; surfacing that as a validation error is an admin-API concern
        (stage 5), not the registry's."""
        resolved = []
        for fc in feature_configs:
            if not fc.enabled:
                continue
            feature = self._features.get(fc.feature_type)
            if feature is None:
                continue
            resolved.append(ActiveFeature(feature=feature, params=fc.params))
        return resolved


default_registry = FeatureRegistry()
