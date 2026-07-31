from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

# Value a locked coin carries (no "blank" here — a symbol that already
# landed always has a real value). Multipliers are integers (confirmed: bet
# and payout multipliers are always integers, so no rounding is needed).
_DEFAULT_VALUE_WEIGHTS = {"1": 40, "2": 25, "5": 15, "10": 8, "grand": 2}
# Whether a coin lands at an empty position during a respin at all.
_DEFAULT_LAND_WEIGHTS = {"blank": 70, "coin": 30}


class HoldAndWinFeature(BonusFeature):
    """TZ §6.2: money symbols "stick" on the grid, N respins, any newly
    landed symbol resets the respin counter, payout is the sum of all locked
    values once respins run out or the grid fills.

    Defaults (industry-typical "Hold & Win" style, confirm with product):
    trigger on 6+ "COIN" symbols anywhere on the grid, 3 respins, "grand"
    is the full-grid jackpot-style top value.
    """

    feature_id = "hold_and_win"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.grid is None:
            return False
        trigger_code = config.get("trigger_symbol_code", "COIN")
        trigger_count = config.get("trigger_count", 6)
        count = sum(column.count(trigger_code) for column in spin_result.grid.reels)
        return count >= trigger_count

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        if game_state.grid is None:
            raise ValueError("hold_and_win.execute requires a triggering grid")

        trigger_code = config.get("trigger_symbol_code", "COIN")
        respin_count = config.get("respin_count", 3)
        value_weights: dict[str, int] = config.get("coin_value_weights", _DEFAULT_VALUE_WEIGHTS)
        land_weights: dict[str, int] = config.get("respin_land_weights", _DEFAULT_LAND_WEIGHTS)
        grand_multiplier = Decimal(str(config.get("grand_value_multiplier", 50)))
        # East Discovery: the trigger symbol (collector_tiger) only opens the
        # round, it isn't itself a money symbol — the grid starts empty and
        # every coin comes from a respin. Amy's-style games where the trigger
        # symbol *is* the coin keep the old default (locks trigger positions
        # as the first coins) via start_empty=False.
        start_empty = config.get("start_empty", False)
        # East Discovery's newer "guaranteed coins" mode (product, this
        # session): every respin lands a drawn count of new coins (capped by
        # however many empty cells remain) instead of an independent
        # land/no-land roll per empty cell — set, this replaces the
        # respin_count/miss-streak termination entirely, since a respin can
        # no longer land nothing: the round then only ends when the grid
        # fills. None (default) keeps the old per-cell/respin_count
        # behavior untouched (Amy's Fruit Farm keeps using that).
        coin_count_weights: dict[str, int] | None = config.get("respin_coin_count_weights")

        num_reels = len(game_state.grid.reels)
        num_rows = len(game_state.grid.reels[0]) if num_reels else 0
        total_positions = num_reels * num_rows

        locked: dict[tuple[int, int], Decimal] = {}
        if not start_empty:
            for reel_index, column in enumerate(game_state.grid.reels):
                for row_index, code in enumerate(column):
                    if code == trigger_code:
                        locked[(reel_index, row_index)] = self._draw_coin_value(
                            value_weights, grand_multiplier, game_state.rng
                        )

        # One entry per respin actually run — lets the frontend replay the
        # round respin-by-respin instead of just showing the final locked set
        # (product: "must feel like real spins").
        respins: list[dict] = []

        if coin_count_weights:
            while len(locked) < total_positions:
                empty_positions = [
                    (reel_index, row_index)
                    for reel_index in range(num_reels)
                    for row_index in range(num_rows)
                    if (reel_index, row_index) not in locked
                ]
                count = min(self._draw_coin_count(coin_count_weights, game_state.rng), len(empty_positions))
                landed_this_round: list[dict] = []
                for reel_index, row_index in self._pick_random_positions(empty_positions, count, game_state.rng):
                    value = self._draw_coin_value(value_weights, grand_multiplier, game_state.rng)
                    locked[(reel_index, row_index)] = value
                    landed_this_round.append({"reel": reel_index, "row": row_index, "value": str(value)})
                respins.append({"landed": landed_this_round})
        else:
            respins_left = respin_count
            while respins_left > 0 and len(locked) < total_positions:
                landed_this_round = []
                for reel_index in range(num_reels):
                    for row_index in range(num_rows):
                        if (reel_index, row_index) in locked:
                            continue
                        if self._coin_lands(land_weights, game_state.rng):
                            value = self._draw_coin_value(value_weights, grand_multiplier, game_state.rng)
                            locked[(reel_index, row_index)] = value
                            landed_this_round.append({"reel": reel_index, "row": row_index, "value": str(value)})
                respins.append({"landed": landed_this_round})
                respins_left -= 1
                if landed_this_round:
                    respins_left = respin_count  # TZ §6.2: any new symbol resets the counter

        full_grid = len(locked) == total_positions
        total_win = sum(locked.values(), Decimal(0)) * game_state.bet_amount

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=total_win,
            state_patch={},
            details={"locked_count": len(locked), "full_grid": full_grid, "respins": respins},
        )

    @staticmethod
    def _draw_coin_value(value_weights: dict[str, int], grand_multiplier: Decimal, rng) -> Decimal:
        keys = list(value_weights.keys())
        weights = [int(value_weights[k]) for k in keys]
        index, _, _ = weighted_pick(weights, rng)
        key = keys[index]
        return grand_multiplier if key == "grand" else Decimal(key)

    @staticmethod
    def _coin_lands(land_weights: dict[str, int], rng) -> bool:
        keys = list(land_weights.keys())
        weights = [int(land_weights[k]) for k in keys]
        index, _, _ = weighted_pick(weights, rng)
        return keys[index] == "coin"

    @staticmethod
    def _draw_coin_count(count_weights: dict[str, int], rng) -> int:
        keys = list(count_weights.keys())
        weights = [int(count_weights[k]) for k in keys]
        index, _, _ = weighted_pick(weights, rng)
        return int(keys[index])

    @staticmethod
    def _pick_random_positions(
        positions: list[tuple[int, int]], count: int, rng
    ) -> list[tuple[int, int]]:
        """Uniform pick of `count` distinct positions, no replacement —
        repeatedly draws one random remaining index and removes it (each draw
        uses the actual current pool size, so every remaining position stays
        equally likely; not a weighted pick, just an unbiased subset)."""
        remaining = list(positions)
        chosen: list[tuple[int, int]] = []
        for _ in range(count):
            index = rng.randbelow(len(remaining))
            chosen.append(remaining.pop(index))
        return chosen

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "trigger_symbol_code": {"type": "string", "default": "COIN"},
                "trigger_count": {"type": "integer", "minimum": 2, "default": 6},
                "respin_count": {"type": "integer", "minimum": 1, "default": 3},
                "coin_value_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                    "default": _DEFAULT_VALUE_WEIGHTS,
                },
                "respin_land_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                    "default": _DEFAULT_LAND_WEIGHTS,
                },
                "grand_value_multiplier": {"type": "integer", "minimum": 1, "default": 50},
                "start_empty": {
                    "type": "boolean",
                    "default": False,
                    "description": "True: round starts empty, trigger symbol doesn't itself lock as a coin.",
                },
                "respin_coin_count_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                    "default": None,
                    "description": (
                        "If set, every respin lands this many new coins (weighted count, capped by "
                        "remaining empty cells) instead of an independent land/no-land roll per empty "
                        "cell — replaces respin_count/miss-streak termination entirely; the round then "
                        "only ends when the grid fills, since a respin can no longer land nothing."
                    ),
                },
            },
            "required": ["trigger_symbol_code", "trigger_count", "respin_count"],
        }


default_registry.register(HoldAndWinFeature())
