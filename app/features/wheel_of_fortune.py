from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

# The wheel's segments, in the order they sit on the drum going clockwise from
# the top. The art (front/img/dirty-money-mafia/popups/WOF/WOF_baraban.png) is
# a revolver cylinder with 8 EMPTY bullet slots — no labels are baked into it,
# so this list is what the client renders onto them. Changing the prize set is
# a config edit, not an art change; only the segment COUNT is tied to the
# artwork.
#
# `type` is either "multiplier" (pays value x the total bet) or "free_spins"
# (opens the free-spins round instead of paying — the spin service hands that
# off to the free_spins module, see app/api/v1/spin_service.py).
#
# Weights are placeholder math in the same spirit as the rest of the seeds
# (nothing here is RTP-tuned yet — that's the stage 6 simulator's job): the
# small multipliers are common, x8 and the free-spins entry are the rare ones.
_DEFAULT_SEGMENTS: list[dict] = [
    {"type": "multiplier", "value": 2, "weight": 30},
    {"type": "multiplier", "value": 3, "weight": 22},
    {"type": "multiplier", "value": 4, "weight": 16},
    {"type": "multiplier", "value": 5, "weight": 12},
    {"type": "multiplier", "value": 6, "weight": 8},
    {"type": "multiplier", "value": 7, "weight": 5},
    {"type": "multiplier", "value": 8, "weight": 3},
    {"type": "free_spins", "weight": 4},
]


class WheelOfFortuneFeature(BonusFeature):
    """Wheel-of-Fortune bonus: land `trigger_count` of the wheel symbol
    anywhere on the grid and a wheel opens; one spin of it awards either a
    cash multiplier or entry into the free-spins round.

    The outcome is drawn HERE, server-side, and the client is only told which
    segment index won — it animates the drum to land on it. The client must
    never pick the prize itself.

    The multiplier pays `value x bet_amount` (the whole bet, not a per-line
    share) — same convention as hold_and_win's payouts, and it is deliberately
    NOT scaled by any active free-spins win multiplier: the wheel is its own
    self-contained prize.
    """

    feature_id = "wheel_of_fortune"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.grid is None:
            return False
        trigger_code = config.get("trigger_symbol_code", "wof")
        trigger_count = config.get("trigger_count", 3)
        count = sum(column.count(trigger_code) for column in spin_result.grid.reels)
        return count >= trigger_count

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        segments = self._segments(config)
        weights = [int(segment.get("weight", 1)) for segment in segments]
        index, raw, total = weighted_pick(weights, game_state.rng)
        segment = segments[index]

        if segment.get("type") == "free_spins":
            # No cash from the wheel itself — the free-spins round is the
            # prize. `spins_awarded` is advisory: the free_spins module owns
            # how many spins its round actually grants, so leaving it unset
            # lets that config stay the single source of truth.
            return FeatureResult(
                feature_id=self.feature_id,
                triggered=True,
                win_amount=Decimal(0),
                details={
                    "segment_index": index,
                    "prize_type": "free_spins",
                    "segments": self._public_segments(segments),
                    "raw_draw": raw,
                    "total_weight": total,
                },
            )

        multiplier = Decimal(str(segment.get("value", 1)))
        win_amount = multiplier * game_state.bet_amount
        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=win_amount,
            details={
                "segment_index": index,
                "prize_type": "multiplier",
                "multiplier": int(multiplier),
                "win_amount": str(win_amount),
                "segments": self._public_segments(segments),
                "raw_draw": raw,
                "total_weight": total,
            },
        )

    @staticmethod
    def _segments(config: dict) -> list[dict]:
        segments = config.get("segments") or _DEFAULT_SEGMENTS
        if not segments:
            raise ValueError("wheel_of_fortune needs at least one segment")
        return segments

    @staticmethod
    def _public_segments(segments: list[dict]) -> list[dict]:
        """What the client needs to label the drum: the prize on each slot, in
        drum order. Weights stay server-side — a player shouldn't be able to
        read the odds off the wire."""
        return [
            {"type": segment.get("type", "multiplier"), "value": segment.get("value")}
            for segment in segments
        ]

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "trigger_symbol_code": {"type": "string", "default": "wof"},
                "trigger_count": {"type": "integer", "minimum": 1, "default": 3},
                "segments": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["multiplier", "free_spins"]},
                            "value": {"type": "integer", "minimum": 1},
                            "weight": {"type": "integer", "minimum": 1},
                        },
                        "required": ["type", "weight"],
                    },
                },
            },
            "required": ["trigger_symbol_code", "trigger_count"],
        }


default_registry.register(WheelOfFortuneFeature())
