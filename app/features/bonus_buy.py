from decimal import Decimal

from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry


class BonusBuyFeature(BonusFeature):
    """TZ §6.2: purchase entry into another feature for a fixed price
    (X * bet). This module only computes/validates the buy-in cost; actually
    charging the balance and invoking the target feature's `execute` is
    orchestrated by the API layer (stage 5) when it sees `feature_buy_id` on
    a spin request (TZ §8.1) — kept out of this module so it stays testable
    without a session/balance.

    Separate RTP accounting for bonus-buy spins (TZ §6.2, §7) is the
    simulator's job (stage 6): it must run bonus-buy spins as their own
    cohort, not mix them into the base-game RTP.
    """

    feature_id = "bonus_buy"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        # Never triggers naturally off a spin's grid — it's an explicit
        # player purchase, not something the reels can land into.
        return False

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        cost_multiplier = Decimal(str(config.get("cost_multiplier", 100)))
        target_feature_id = config.get("target_feature_id", "free_spins")
        cost = cost_multiplier * game_state.bet_amount

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=Decimal(0),
            state_patch={},
            details={"cost": str(cost), "target_feature_id": target_feature_id},
        )

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cost_multiplier": {"type": "integer", "minimum": 1, "default": 100},
                "target_feature_id": {"type": "string", "default": "free_spins"},
            },
            "required": ["cost_multiplier", "target_feature_id"],
        }


default_registry.register(BonusBuyFeature())
