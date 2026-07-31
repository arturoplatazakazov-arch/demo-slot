from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

_COLOR_OPTIONS = ("red", "black")
_SUIT_OPTIONS = ("hearts", "diamonds", "clubs", "spades")


class GambleFeature(BonusFeature):
    """TZ §6.2: risk doubling (or quadrupling) a win by guessing a
    color/card, with a round or max-win cap.

    `execute` reads the player's stake and guess from `session_state`
    (`gamble_stake`, `gamble_guess`) — the BonusFeature interface (TZ §6.1)
    carries no request-specific arguments, so the API layer (stage 5) is
    expected to populate these from the `POST /api/v1/gamble` body before
    calling this module.
    """

    feature_id = "gamble"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        # Gamble is *offered*, not auto-fired: available whenever the last
        # spin produced a win. The round itself only runs when the player
        # explicitly calls POST /api/v1/gamble (TZ §8.1).
        if spin_result.win_evaluation is None:
            return False
        return spin_result.win_evaluation.total_win > 0

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        mode = config.get("mode", "color")
        options = _COLOR_OPTIONS if mode == "color" else _SUIT_OPTIONS
        multiplier = Decimal(2) if mode == "color" else Decimal(4)

        stake = Decimal(str(game_state.session_state.get("gamble_stake", 0)))
        guess = game_state.session_state.get("gamble_guess")

        rounds_played = game_state.session_state.get("gamble_rounds_played", 0)
        max_rounds = config.get("max_rounds")
        if max_rounds is not None and rounds_played >= max_rounds:
            return FeatureResult(
                feature_id=self.feature_id, triggered=False, details={"reason": "max_rounds_reached"}
            )

        max_win_multiplier = config.get("max_win_multiplier")
        if max_win_multiplier is not None and stake >= Decimal(str(max_win_multiplier)) * game_state.bet_amount:
            return FeatureResult(
                feature_id=self.feature_id, triggered=False, details={"reason": "max_win_reached"}
            )

        outcome_index, _, _ = weighted_pick([1] * len(options), game_state.rng)
        outcome = options[outcome_index]
        won = outcome == guess
        new_amount = stake * multiplier if won else Decimal(0)

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=new_amount,
            state_patch={"gamble_rounds_played": rounds_played + 1},
            details={"outcome": outcome, "guess": guess, "won": won, "stake": str(stake)},
        )

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["color", "suit"], "default": "color"},
                "max_rounds": {"type": "integer", "minimum": 1},
                "max_win_multiplier": {"type": "integer", "minimum": 1},
            },
            "required": ["mode"],
        }


default_registry.register(GambleFeature())
