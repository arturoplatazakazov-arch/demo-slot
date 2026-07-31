from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

_PENDING_LEVEL_KEY = "_pending_jackpot_level_index"


class JackpotFeature(BonusFeature):
    """TZ §6.2: fixed (multi-level) jackpot. Each level has independent odds
    expressed as `weight` out of `odds_denominator` per spin — a "mystery"
    trigger decoupled from grid symbols, since the TZ doesn't specify a
    trigger mechanism. Confirm if a jackpot *symbol* combo should drive this
    instead.

    Progressive (accumulating pool) jackpots are explicitly **out of scope**
    here: they need a persistent pool balance that grows across spins/games,
    which has no entity in TZ §9's data model. Flagging as an open item
    rather than building a partial accumulator — see end-of-stage notes.

    `is_triggered` and `execute` must be called on the *same* `FeatureContext`
    (same `session_state` dict) within one orchestration step: the level
    that hit is decided once, in `is_triggered`, and stashed in
    `session_state` for `execute` to read — this avoids drawing RNG twice
    for what must be a single, reproducible outcome.
    """

    feature_id = "jackpot"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        levels = config.get("levels", [])
        if not levels:
            return False

        denominator = config.get("odds_denominator", 10_000_000)
        weights = [int(level["weight"]) for level in levels]
        no_trigger_weight = denominator - sum(weights)
        if no_trigger_weight < 0:
            raise ValueError("jackpot level weights exceed odds_denominator")

        chosen_index, _, _ = weighted_pick(weights + [no_trigger_weight], spin_result.rng)
        if chosen_index == len(levels):
            return False

        spin_result.session_state[_PENDING_LEVEL_KEY] = chosen_index
        return True

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        levels = config.get("levels", [])
        level_index = game_state.session_state.pop(_PENDING_LEVEL_KEY, None)
        if level_index is None or level_index >= len(levels):
            return FeatureResult(feature_id=self.feature_id, triggered=False, details={"reason": "no_pending_level"})

        level = levels[level_index]
        multiplier = Decimal(str(level["value_multiplier"]))
        win_amount = multiplier * game_state.bet_amount

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=win_amount,
            state_patch={},
            details={"level_id": level.get("id"), "value_multiplier": str(multiplier)},
        )

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "odds_denominator": {"type": "integer", "minimum": 1, "default": 10_000_000},
                "levels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "weight": {"type": "integer", "minimum": 1},
                            "value_multiplier": {"type": "integer", "minimum": 1},
                        },
                        "required": ["id", "weight", "value_multiplier"],
                    },
                    "default": [
                        {"id": "mini", "weight": 500, "value_multiplier": 20},
                        {"id": "major", "weight": 20, "value_multiplier": 200},
                        {"id": "grand", "weight": 1, "value_multiplier": 5000},
                    ],
                },
            },
            "required": ["levels"],
        }


default_registry.register(JackpotFeature())
