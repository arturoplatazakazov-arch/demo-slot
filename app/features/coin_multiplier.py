from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

_DEFAULT_VALUE_WEIGHTS = {"1": 40, "2": 25, "5": 15, "10": 10, "25": 6, "50": 3, "100": 1}


class CoinMultiplierFeature(BonusFeature):
    """East Discovery base-game mechanic, no existing analog: every coin
    symbol on the grid always draws and displays its own random multiplier
    (own weight table — same x1...x100 tier idea as hold_and_win, but
    base-game frequency is tuned separately), on every spin a coin lands —
    that part is pure presentation/anticipation, not gated behind anything
    (product: the value has to already be showing on the coin, not only
    appear once a win happens). It only actually *pays out* — multiplying
    the spin's line-pay total (not count-pay) by the sum of every drawn
    multiplier — when a collector symbol is ALSO on the grid AND there's at
    least one line win this spin; `details["applied"]` tells the caller
    (and the frontend) which case this was, since the coin_positions/values
    are present either way.

    Unlike hold_and_win/free_spins this doesn't award its own flat payout —
    `win_amount` is the *delta* over the win evaluation's already-computed
    line_pay_total (multiplier_sum - 1), so spin_service.py can add it
    straight onto `evaluation.total_win` without double-counting the
    un-multiplied line-pay already baked in there (it's simply 0 when
    `applied` is False).
    """

    feature_id = "coin_multiplier"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.grid is None:
            return False
        coin_code = config.get("coin_symbol_code", "coin")
        return any(coin_code in column for column in spin_result.grid.reels)

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        if game_state.grid is None or game_state.win_evaluation is None:
            raise ValueError("coin_multiplier.execute requires a grid and win evaluation")

        coin_code = config.get("coin_symbol_code", "coin")
        collector_code = config.get("collector_symbol_code", "collector_tiger")
        value_weights: dict[str, int] = config.get("value_weights", _DEFAULT_VALUE_WEIGHTS)
        jackpot_values: dict[str, int] = config.get("jackpot_values") or {}
        # Lucky Joker (product): there is no collector symbol on the base-game
        # reels at all — a coin multiplies a winning line on its own. East
        # Discovery keeps the original "collector must be on the grid" rule.
        requires_collector = config.get("requires_collector", True)

        positions: list[dict] = []
        multiplier_sum = Decimal(0)
        for reel_index, column in enumerate(game_state.grid.reels):
            for row_index, code in enumerate(column):
                if code == coin_code:
                    kind, value = self._draw_multiplier(value_weights, game_state.rng, jackpot_values)
                    multiplier_sum += value
                    positions.append(
                        {"reel": reel_index, "row": row_index, "value": str(value), "kind": kind}
                    )

        line_pay_total = game_state.win_evaluation.line_pay_total
        has_collector = (
            True if not requires_collector
            else any(collector_code in column for column in game_state.grid.reels)
        )
        applied = has_collector and line_pay_total > 0
        bonus_win = line_pay_total * (multiplier_sum - 1) if applied and multiplier_sum > 0 else Decimal(0)

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=bonus_win,
            state_patch={},
            details={"coin_positions": positions, "multiplier_sum": str(multiplier_sum), "applied": applied},
        )

    @staticmethod
    def _draw_multiplier(
        value_weights: dict[str, int], rng, jackpot_values: dict[str, int] | None = None
    ) -> tuple[str, Decimal]:
        """Returns (drawn key, multiplier). A key listed in `jackpot_values`
        resolves to that tier's multiplier and is reported as the coin's
        `kind`, so a MINI/MAJOR/... coin can land in the base game and be drawn
        with its own art (Lucky Joker, product)."""
        keys = list(value_weights.keys())
        weights = [int(value_weights[k]) for k in keys]
        index, _, _ = weighted_pick(weights, rng)
        key = keys[index]
        if jackpot_values and key in jackpot_values:
            return key, Decimal(str(jackpot_values[key]))
        return key, Decimal(key)

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "coin_symbol_code": {"type": "string", "default": "coin"},
                "collector_symbol_code": {"type": "string", "default": "collector_tiger"},
                "requires_collector": {
                    "type": "boolean",
                    "default": True,
                    "description": "False: a coin multiplies a winning line with no collector on the grid.",
                },
                "value_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                    "default": _DEFAULT_VALUE_WEIGHTS,
                },
                "jackpot_values": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 1},
                    "default": None,
                    "description": "Named tiers a value_weights key can resolve to (mini/minor/major/grand).",
                },
            },
            "required": ["coin_symbol_code", "collector_symbol_code"],
        }


default_registry.register(CoinMultiplierFeature())
