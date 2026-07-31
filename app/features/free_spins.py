from decimal import Decimal

from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry


class FreeSpinsFeature(BonusFeature):
    """TZ §6.2: triggers on N+ scatter, awards X free spins, optional
    retrigger, optional win multiplier during the free-spins round.

    Defaults (industry-typical, TZ §14 leaves exact numbers open — confirm):
    3+ scatters, 10 free spins, retrigger allowed, no win multiplier.
    """

    feature_id = "free_spins"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.grid is None:
            return False

        trigger_code = config.get("trigger_symbol_code", "SCAT")
        trigger_count = config.get("trigger_count", 3)
        count = sum(column.count(trigger_code) for column in spin_result.grid.reels)
        if count < trigger_count:
            return False

        already_active = spin_result.session_state.get("free_spins_remaining", 0) > 0
        if already_active and not config.get("retrigger_enabled", True):
            return False
        return True

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        spins_awarded = self._spins_awarded(game_state, config)
        win_multiplier = Decimal(str(config.get("win_multiplier", 1)))
        remaining = game_state.session_state.get("free_spins_remaining", 0)
        total_remaining = remaining + spins_awarded

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=Decimal(0),  # awarding spins is not itself a cash payout
            state_patch={
                "free_spins_remaining": total_remaining,
                "free_spins_multiplier": str(win_multiplier),
            },
            details={"spins_awarded": spins_awarded, "total_remaining": total_remaining},
        )

    @staticmethod
    def _spins_awarded(game_state: FeatureContext, config: dict) -> int:
        """Award depends on how many trigger symbols actually landed on this
        spin, e.g. {"3": 5, "4": 7, "5": 9} — same table for the initial
        trigger and any retrigger. Falls back to the flat `spins_awarded`
        when `spins_awarded_by_count` isn't configured (keeps this backward
        compatible with configs/tests that only set a flat award)."""
        by_count = config.get("spins_awarded_by_count")
        if by_count and game_state.grid is not None:
            trigger_code = config.get("trigger_symbol_code", "SCAT")
            count = sum(column.count(trigger_code) for column in game_state.grid.reels)
            if str(count) in by_count:
                return by_count[str(count)]
        return config.get("spins_awarded", 10)

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "trigger_symbol_code": {"type": "string", "default": "SCAT"},
                "trigger_count": {"type": "integer", "minimum": 2, "default": 3},
                "spins_awarded": {"type": "integer", "minimum": 1, "default": 10},
                "spins_awarded_by_count": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 1},
                    "description": "Optional: match-count -> spins awarded, overrides spins_awarded when set.",
                },
                "retrigger_enabled": {"type": "boolean", "default": True},
                "win_multiplier": {"type": "integer", "minimum": 1, "default": 1},
            },
            "required": ["trigger_symbol_code", "trigger_count", "spins_awarded"],
        }


default_registry.register(FreeSpinsFeature())
