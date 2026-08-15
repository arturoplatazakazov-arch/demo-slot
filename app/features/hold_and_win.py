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
# Same roll for the collector reel in the "collector" mode below — rarer than a
# coin, since every extra collector multiplies the whole round's payout.
_DEFAULT_COLLECTOR_LAND_WEIGHTS = {"blank": 92, "coin": 8}


class HoldAndWinFeature(BonusFeature):
    """TZ §6.2: money symbols "stick" on the grid, N respins, any newly
    landed symbol resets the respin counter, payout is the sum of all locked
    values once respins run out or the grid fills.

    Defaults (industry-typical "Hold & Win" style, confirm with product):
    trigger on 6+ "COIN" symbols anywhere on the grid, 3 respins, "grand"
    is the full-grid jackpot-style top value.

    Named jackpot tiers (`jackpot_values`, e.g. Lucky Joker's MINI x25 /
    MINOR x50 / MAJOR x150 / GRAND x1000 plates) let a coin_value_weights key
    be a NAME rather than a number: the key resolves to its multiplier here,
    and every reported coin carries the key it was drawn from as `kind`, so a
    client can tell a x25 jackpot coin from a plain "25" one and show the
    right art. Games that don't set it are untouched — "grand" keeps falling
    back to `grand_value_multiplier` and every other key stays numeric.
    """

    feature_id = "hold_and_win"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.grid is None:
            return False
        trigger_code = config.get("trigger_symbol_code", "COIN")
        # "one_per_reel" (Lucky Joker, product): the round opens on ONE trigger
        # symbol on EVERY reel, not on a total count anywhere — on a 3x3 grid a
        # plain count is a much blunter instrument (3 coins stacked in one
        # column would open it just the same).
        if config.get("trigger_mode") == "one_per_reel":
            return all(trigger_code in column for column in spin_result.grid.reels)
        # "collector_and_coins" (Lucky Joker, product): a COLLECTOR on the
        # collector reel plus a coin on each of the others — the collector is
        # what opens the round, the coins are what it will collect.
        if config.get("trigger_mode") == "collector_and_coins":
            reels = spin_result.grid.reels
            collector_reel = int(config.get("collector_reel", len(reels) // 2))
            collector_code = config.get("collector_symbol_code", "collector")
            if collector_code not in reels[collector_reel]:
                return False
            return all(
                trigger_code in column
                for index, column in enumerate(reels)
                if index != collector_reel
            )
        trigger_count = config.get("trigger_count", 6)
        count = sum(column.count(trigger_code) for column in spin_result.grid.reels)
        return count >= trigger_count

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        if game_state.grid is None:
            raise ValueError("hold_and_win.execute requires a triggering grid")

        if config.get("mode") == "collector":
            return self._execute_collector(game_state, config)

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
        jackpot_values: dict[str, int] = config.get("jackpot_values") or {}
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
        # The coins already on the triggering grid (start_empty=False), each
        # with the value/kind it locked at. Reported separately from `respins`
        # because they never appear in one: without this the client has no way
        # to know what the coins it can already SEE are worth. Always empty for
        # start_empty=True rounds (East Discovery), which begin on a bare grid.
        initial: list[dict] = []
        if not start_empty:
            for reel_index, column in enumerate(game_state.grid.reels):
                for row_index, code in enumerate(column):
                    if code == trigger_code:
                        kind, value = self._draw_coin_value(
                            value_weights, grand_multiplier, game_state.rng, jackpot_values
                        )
                        locked[(reel_index, row_index)] = value
                        initial.append(
                            {"reel": reel_index, "row": row_index, "value": str(value), "kind": kind}
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
                    kind, value = self._draw_coin_value(
                        value_weights, grand_multiplier, game_state.rng, jackpot_values
                    )
                    locked[(reel_index, row_index)] = value
                    landed_this_round.append(
                        {"reel": reel_index, "row": row_index, "value": str(value), "kind": kind}
                    )
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
                            kind, value = self._draw_coin_value(
                                value_weights, grand_multiplier, game_state.rng, jackpot_values
                            )
                            locked[(reel_index, row_index)] = value
                            landed_this_round.append(
                                {"reel": reel_index, "row": row_index, "value": str(value), "kind": kind}
                            )
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
            details={
                "locked_count": len(locked),
                "full_grid": full_grid,
                "initial": initial,
                "respins": respins,
            },
        )

    def _execute_collector(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        """Lucky Joker's 3x3 round (product), different enough from the classic
        one above to be its own path:

        * the grid opens EMPTY except a single COLLECTOR, which takes the place
          of the trigger coin that landed on the collector reel (the middle one);
        * from then on that reel only ever takes collectors, and every other
          reel only ever takes coins — so a 3x3 round is 6 coin slots and 3
          collector slots, not 9 interchangeable ones;
        * a collector doesn't carry a value of its own: it COLLECTS, i.e. every
          collector on the grid is worth the sum of every coin's multiplier.
          Two collectors therefore pay that sum twice, three pay it three
          times;
        * respins run the classic way — `respin_count` of them, reset by any
          new landing, ending early when the grid fills.

        Reported through the same `details` shape as the classic round (the
        client replays `initial` + `respins` identically); collectors are just
        entries with kind="collector" and value 0.
        """
        grid = game_state.grid
        trigger_code = config.get("trigger_symbol_code", "COIN")
        collector_code = config.get("collector_symbol_code", "collector")
        collector_reel = int(config.get("collector_reel", len(grid.reels) // 2))
        respin_count = int(config.get("respin_count", 3))
        value_weights: dict[str, int] = config.get("coin_value_weights", _DEFAULT_VALUE_WEIGHTS)
        land_weights: dict[str, int] = config.get("respin_land_weights", _DEFAULT_LAND_WEIGHTS)
        collector_land_weights: dict[str, int] = config.get(
            "collector_land_weights", _DEFAULT_COLLECTOR_LAND_WEIGHTS
        )
        grand_multiplier = Decimal(str(config.get("grand_value_multiplier", 50)))
        jackpot_values: dict[str, int] = config.get("jackpot_values") or {}

        num_reels = len(grid.reels)
        num_rows = len(grid.reels[0]) if num_reels else 0
        total_positions = num_reels * num_rows

        # position -> (kind, value); a collector is (collector_code, 0).
        locked: dict[tuple[int, int], tuple[str, Decimal]] = {}
        initial: list[dict] = []

        # The round opens on the COLLECTOR that triggered it, standing exactly
        # where it landed. Falls back to a trigger coin on that reel and then
        # to the middle row (a forced dev spin, a hand-built context), so the
        # round always opens with exactly one collector.
        column = grid.reels[collector_reel]
        seed_row = next(
            (row for row, code in enumerate(column) if code == collector_code),
            next((row for row, code in enumerate(column) if code == trigger_code), num_rows // 2),
        )
        locked[(collector_reel, seed_row)] = (collector_code, Decimal(0))
        initial.append(
            {"reel": collector_reel, "row": seed_row, "value": "0", "kind": collector_code}
        )

        respins: list[dict] = []
        respins_left = respin_count
        while respins_left > 0 and len(locked) < total_positions:
            landed_this_round: list[dict] = []
            for reel_index in range(num_reels):
                is_collector_reel = reel_index == collector_reel
                weights = collector_land_weights if is_collector_reel else land_weights
                for row_index in range(num_rows):
                    if (reel_index, row_index) in locked:
                        continue
                    if not self._coin_lands(weights, game_state.rng):
                        continue
                    if is_collector_reel:
                        kind, value = collector_code, Decimal(0)
                    else:
                        kind, value = self._draw_coin_value(
                            value_weights, grand_multiplier, game_state.rng, jackpot_values
                        )
                    locked[(reel_index, row_index)] = (kind, value)
                    landed_this_round.append(
                        {"reel": reel_index, "row": row_index, "value": str(value), "kind": kind}
                    )
            respins.append({"landed": landed_this_round})
            respins_left -= 1
            if landed_this_round:
                respins_left = respin_count  # TZ §6.2: any new symbol resets the counter

        coin_total = sum((value for kind, value in locked.values() if kind != collector_code), Decimal(0))
        collector_count = sum(1 for kind, _ in locked.values() if kind == collector_code)
        total_win = coin_total * collector_count * game_state.bet_amount

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=total_win,
            state_patch={},
            details={
                "locked_count": len(locked),
                "full_grid": len(locked) == total_positions,
                "initial": initial,
                "respins": respins,
                # What the collectors ended up worth, for the client's counters
                # and for the audit log: each collector shows `coin_total`.
                "coin_total": str(coin_total),
                "collector_count": collector_count,
            },
        )

    @staticmethod
    def _draw_coin_value(
        value_weights: dict[str, int],
        grand_multiplier: Decimal,
        rng,
        jackpot_values: dict[str, int] | None = None,
    ) -> tuple[str, Decimal]:
        """Draws one coin, returning (drawn key, bet multiplier). The key is
        reported to the client as the coin's `kind` — for a numeric table
        that's just the value as a string, for a named jackpot table it's the
        tier name ("mini"/"grand"/...) and picks the coin art."""
        keys = list(value_weights.keys())
        weights = [int(value_weights[k]) for k in keys]
        index, _, _ = weighted_pick(weights, rng)
        key = keys[index]
        if jackpot_values and key in jackpot_values:
            return key, Decimal(str(jackpot_values[key]))
        if key == "grand":
            return key, grand_multiplier
        return key, Decimal(key)

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
                "trigger_mode": {
                    "type": "string",
                    "enum": ["count", "one_per_reel", "collector_and_coins"],
                    "default": "count",
                    "description": (
                        "'one_per_reel': the trigger symbol on EVERY reel. "
                        "'collector_and_coins': a collector on collector_reel plus the trigger "
                        "symbol on each of the other reels."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["classic", "collector"],
                    "default": "classic",
                    "description": (
                        "'collector': one reel takes only collectors, the rest only coins, and each "
                        "collector pays the sum of every coin's multiplier (see _execute_collector)."
                    ),
                },
                "collector_reel": {"type": "integer", "minimum": 0, "default": None},
                "collector_symbol_code": {"type": "string", "default": "collector"},
                "collector_land_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                    "default": _DEFAULT_COLLECTOR_LAND_WEIGHTS,
                },
                "jackpot_values": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 1},
                    "default": None,
                    "description": (
                        "Named jackpot tiers, name -> bet multiplier (e.g. {\"mini\": 25, \"grand\": 1000}). "
                        "A coin_value_weights key matching a name here pays that multiplier and is reported "
                        "with kind=<name> so the client can show the tier's own coin art."
                    ),
                },
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
