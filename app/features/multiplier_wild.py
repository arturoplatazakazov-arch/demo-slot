from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

# variant -> weight. "1" is the "stayed a plain WILD" outcome and is a real
# variant, not the absence of one: the art ships a dedicated `wild` skin
# alongside x2/x3/x5/x7 precisely so the reveal beat plays either way (see
# front/js/multi-fruits-story/slot.js). Weights below are a starting point,
# tuned against scripts/simulate.py — not an industry standard.
_DEFAULT_VARIANT_WEIGHTS = {"1": 55, "2": 20, "3": 13, "5": 8, "7": 4}


class MultiplierWildFeature(BonusFeature):
    """Multi Fruits Story base mechanic: every WILD that lands rolls its own
    multiplier — it either stays a plain wild (x1) or turns into x2/x3/x5/x7 —
    and multiplies the PAYLINE it takes part in.

    Two deliberate choices, both product decisions:

    * The roll happens on every spin a wild lands, win or not, and every
      drawn value is reported in `details["wilds"]`. That's presentation, not
      payout: the client needs the value to pick the Spine skin and play the
      transform, and a wild that transformed into x7 on a dead spin still has
      to *show* x7. `details["applied"]` says whether any of it actually paid.
    * Scope is the line, not the spin. A wild only multiplies the line wins
      whose own positions include it; several wilds on one line MULTIPLY
      together (x2 and x3 on the same line = x6). Count wins (scatter) are
      never touched — they don't run along a payline at all.

    Like coin_multiplier and unlike free_spins/hold_and_win, this doesn't
    award a flat payout: `win_amount` is the DELTA over the win evaluation's
    already-computed line pay, so spin_service.py can add it straight onto
    `evaluation.total_win` without double-counting the un-multiplied line win
    baked in there. It's simply 0 when nothing qualified.
    """

    feature_id = "multiplier_wild"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.grid is None:
            return False
        wild_code = config.get("wild_symbol_code", "wild")
        return any(wild_code in column for column in spin_result.grid.reels)

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        if game_state.grid is None or game_state.win_evaluation is None:
            raise ValueError("multiplier_wild.execute requires a grid and win evaluation")

        wild_code = config.get("wild_symbol_code", "wild")
        variant_weights: dict[str, int] = config.get("variant_weights", _DEFAULT_VARIANT_WEIGHTS)

        # Draw one variant per wild on the grid, in a deterministic order
        # (reel, then row) so a given RNG sequence always reproduces.
        by_position: dict[tuple[int, int], Decimal] = {}
        wilds: list[dict] = []
        for reel_index, column in enumerate(game_state.grid.reels):
            for row_index, code in enumerate(column):
                if code != wild_code:
                    continue
                value = self._draw_multiplier(variant_weights, game_state.rng)
                by_position[(reel_index, row_index)] = value
                wilds.append({"reel": reel_index, "row": row_index, "multiplier": str(value)})

        bonus_win = Decimal(0)
        for win in game_state.win_evaluation.line_wins:
            product = Decimal(1)
            for position in win.positions:
                product *= by_position.get(position, Decimal(1))
            if product > 1:
                bonus_win += win.win_amount * (product - 1)

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=bonus_win,
            state_patch={},
            details={"wilds": wilds, "applied": bonus_win > 0},
        )

    @staticmethod
    def _draw_multiplier(variant_weights: dict[str, int], rng) -> Decimal:
        keys = list(variant_weights.keys())
        weights = [int(variant_weights[k]) for k in keys]
        index, _, _ = weighted_pick(weights, rng)
        return Decimal(keys[index])

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "wild_symbol_code": {"type": "string", "default": "wild"},
                "variant_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                    "default": _DEFAULT_VARIANT_WEIGHTS,
                    "description": 'Multiplier value -> weight. "1" means the wild stays a plain WILD.',
                },
            },
            "required": ["wild_symbol_code"],
        }


default_registry.register(MultiplierWildFeature())
