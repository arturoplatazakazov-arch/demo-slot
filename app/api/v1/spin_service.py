"""Spin orchestration: wires app.engine + app.features together for one
request. This is API-layer glue, not engine/feature logic — it converts
persisted config to engine dataclasses, runs a spin, applies whichever
bonus feature fired, updates balance/session state, and persists the
append-only SpinRecord (TZ §11).

This module owns the line-pay paths and dispatches games with an enabled
"avalanche" FeatureConfig row to spin_avalanche.py. The pieces every path
shares live next door: loaders.py (session/config/bet), bonus_buy.py
(purchase validation), response_builders.py (schema mapping),
spin_persistence.py (settlement write-back) and
app/services/free_spins_round.py (round state lifecycle)."""

import dataclasses
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import schemas
from app.api.v1.bonus_buy import prepare_feature_buy
from app.api.v1.loaders import find_feature_config, load_active_config, resolve_spin_bet
from app.api.v1.response_builders import (
    coin_multiplier_out,
    count_wins_out,
    free_spins_feature_out,
    hold_and_win_out,
    line_wins_out,
    multiplier_wilds_out,
    wheel_of_fortune_out,
)
from app.api.v1.spin_avalanche import run_avalanche_feature_buy, run_avalanche_spin
from app.api.v1.spin_tumble import run_tumble_buy, run_tumble_spin
from app.api.v1.spin_persistence import commit_spin
from app.engine.reels import spin_reels, weighted_pick
from app.engine.rng import RNGProvider
from app.engine.types import ReelSetConfig, WinEvaluation
from app.engine.wins import evaluate_count_wins, evaluate_spin
from app.features import default_registry
from app.features.base import FeatureContext
from app.models.session import Session
from app.services import free_spins_round
from app.services.config_adapter import symbol_tiers, to_paylines, to_reel_set_config
from app.services.grid_format import to_frontend_grid, winning_cells
from app.services.popups import select_popup
from app.services.spin_features import apply_expanding_wild, apply_reel_caps


async def run_spin(
    db: AsyncSession,
    session: Session,
    requested_bet_amount: int,
    rng: RNGProvider,
    force_positions: dict[str, list[tuple[int, int]]] | None = None,
) -> schemas.SpinResponse:
    game_config = await load_active_config(db, session.game_id)
    reel_set = to_reel_set_config(game_config)

    tumble_config = find_feature_config(game_config, "scatter_tumble")
    if tumble_config is not None:
        return await run_tumble_spin(db, session, game_config, requested_bet_amount, rng, tumble_config)

    avalanche_config = find_feature_config(game_config, "avalanche")
    if avalanche_config is not None:
        return await run_avalanche_spin(
            db, session, game_config, reel_set, requested_bet_amount, rng, avalanche_config
        )

    paylines = to_paylines(game_config)
    tiers = symbol_tiers(game_config)

    state = dict(session.state)
    bet_amount, was_in_free_spins = resolve_spin_bet(
        game_config, state, requested_bet_amount, len(paylines)
    )

    free_spins_feature = default_registry.get("free_spins")
    free_spins_config = find_feature_config(game_config, "free_spins")
    fs_params = free_spins_config.params if free_spins_config is not None else {}

    # Neon Joker Spins (GDD-02 §4.1): the round spins its own weight set —
    # only the symbols named in reel_weight_overrides change.
    if was_in_free_spins and fs_params.get("reel_weight_overrides"):
        reel_set = with_weight_overrides(reel_set, fs_params["reel_weight_overrides"])

    grid = spin_reels(reel_set, rng)
    grid = apply_reel_caps(grid, reel_set, rng)

    # Dev-only override (see /dev/force-hold-and-win): forces specific
    # symbols onto an otherwise-real, otherwise-normally-drawn grid, so
    # everything downstream (evaluate_spin, expanding_wild, hold_and_win's
    # own is_triggered/execute) runs exactly as it would for a natural spin —
    # no bonus-buy cost, no bypassed feature logic, just a rigged draw.
    if force_positions:
        for symbol_code, positions in force_positions.items():
            for reel, row in positions:
                grid.reels[reel][row] = symbol_code

    wild_config = find_feature_config(game_config, "expanding_wild")
    # Savannah Kings (GDD-03 §5.2.4): scatters and paws a lion expands over
    # still count — keep the grid as it landed for count pays, triggers and
    # the client (which draws the expansions from wild_events on top of it).
    landed_grid = None
    if wild_config is not None and wild_config.params.get("triggers_before_expand"):
        landed_grid = dataclasses.replace(grid, reels=[list(column) for column in grid.reels])
    wild_events = apply_expanding_wild(grid, wild_config, state, rng, Decimal(bet_amount), reel_set)

    bet_per_line = Decimal(bet_amount) / Decimal(len(paylines))
    evaluation = evaluate_spin(grid, reel_set.symbols, paylines, bet_per_line, Decimal(bet_amount))
    if landed_grid is not None:
        evaluation = dataclasses.replace(
            evaluation, count_wins=evaluate_count_wins(landed_grid, reel_set.symbols, Decimal(bet_amount))
        )

    ctx = FeatureContext(
        session_state=state,
        rng=rng,
        bet_amount=Decimal(bet_amount),
        symbols=reel_set.symbols,
        grid=landed_grid or grid,
        win_evaluation=evaluation,
        is_bonus_buy=False,
    )

    # coin_multiplier needs evaluation.line_pay_total (via ctx.win_evaluation)
    # before spin_win can be finalized, so it runs right here rather than
    # alongside the other feature checks below.
    coin_feature = default_registry.get("coin_multiplier")
    coin_config = find_feature_config(game_config, "coin_multiplier")
    coin_bonus = Decimal(0)
    coin_details = None
    if coin_feature is not None and coin_config is not None and coin_feature.is_triggered(ctx, coin_config.params):
        coin_result = coin_feature.execute(ctx, coin_config.params)
        coin_bonus = coin_result.win_amount
        coin_details = coin_result.details
        ctx.coin_values = coin_details["coin_positions"]

    # multiplier_wild is the same shape as coin_multiplier — it needs the line
    # wins to already exist and returns the DELTA over them (see the module
    # docstring), so it runs here rather than with the trigger features below.
    wild_multiplier_feature = default_registry.get("multiplier_wild")
    wild_multiplier_config = find_feature_config(game_config, "multiplier_wild")
    wild_multiplier_bonus = Decimal(0)
    wild_multiplier_details = None
    if (
        wild_multiplier_feature is not None
        and wild_multiplier_config is not None
        and wild_multiplier_feature.is_triggered(ctx, wild_multiplier_config.params)
    ):
        wild_multiplier_result = wild_multiplier_feature.execute(ctx, wild_multiplier_config.params)
        wild_multiplier_bonus = wild_multiplier_result.win_amount
        wild_multiplier_details = wild_multiplier_result.details

    multiplier = free_spins_round.win_multiplier(state, was_in_free_spins)
    spin_win = (evaluation.total_win + coin_bonus + wild_multiplier_bonus) * multiplier

    triggered_now = False
    trigger_result = None
    if free_spins_feature is not None and free_spins_config is not None:
        if free_spins_feature.is_triggered(ctx, free_spins_config.params):
            trigger_result = free_spins_feature.execute(ctx, free_spins_config.params)
            state.update(trigger_result.state_patch)
            triggered_now = True
            if not was_in_free_spins:
                free_spins_round.enter_round(state, bet_amount)

    # Wheel of Fortune: N+ wheel symbols open a wheel that pays either a cash
    # multiplier or entry into the free-spins round (app/features/
    # wheel_of_fortune.py). Resolved fully server-side here; the client only
    # animates the drum onto the segment this picked.
    #
    # Sits AFTER the scatter trigger above on purpose: a spin can land both,
    # and awarding the wheel's spins through the same free_spins module means
    # the two merge into one round (its execute() adds to whatever
    # free_spins_remaining already holds) instead of racing each other.
    wheel_feature = default_registry.get("wheel_of_fortune")
    wheel_config = find_feature_config(game_config, "wheel_of_fortune")
    wheel_result = None
    if (
        wheel_feature is not None
        and wheel_config is not None
        and wheel_feature.is_triggered(ctx, wheel_config.params)
    ):
        wheel_result = wheel_feature.execute(ctx, wheel_config.params)
        # Unmultiplied by any free-spins win_multiplier — the wheel prize is
        # already scaled by the full bet, same convention as Hold & Win below.
        spin_win += wheel_result.win_amount
        if wheel_result.details.get("prize_type") == "free_spins" and free_spins_feature is not None and free_spins_config is not None:
            wheel_spins_result = free_spins_feature.execute(ctx, free_spins_config.params)
            state.update(wheel_spins_result.state_patch)
            # Report the wheel's award through the same `feature` field a
            # scatter trigger uses, so the client's existing bonus-entry path
            # handles both. Keeps the LATER result: it already folded in any
            # spins the scatter trigger just granted (execute() sums onto
            # free_spins_remaining), so it's the accurate total.
            trigger_result = wheel_spins_result
            triggered_now = True
            if not was_in_free_spins:
                free_spins_round.enter_round(state, bet_amount)

    # Hold & Win resolves entirely in this one call (see hold_and_win.py) —
    # its payout is on top of whatever the triggering spin itself won,
    # unmultiplied by any free-spins win_multiplier (it's already scaled by
    # the full bet amount, not a per-line amount).
    hold_and_win_feature = default_registry.get("hold_and_win")
    hold_and_win_config = find_feature_config(game_config, "hold_and_win")
    hold_and_win_result = None
    if (
        hold_and_win_feature is not None
        and hold_and_win_config is not None
        and hold_and_win_feature.is_triggered(ctx, hold_and_win_config.params)
    ):
        hold_and_win_result = hold_and_win_feature.execute(ctx, hold_and_win_config.params)
        spin_win += hold_and_win_result.win_amount

    spin_win, max_win_reached = free_spins_round.apply_cap(
        state, spin_win, bet_amount, fs_params.get("round_max_win_multiplier"),
        was_in_free_spins, triggered_now and not was_in_free_spins,
    )
    if max_win_reached and not was_in_free_spins:
        triggered_now = False
        trigger_result = None

    round_status = free_spins_round.settle(state, spin_win, was_in_free_spins)

    popup = select_popup(
        line_wins=evaluation.line_wins,
        total_win=spin_win,
        tiers=tiers,
        # The spin that *triggers* free spins gets a bonusSpinsWin popup too
        # (product decision — announces the bonus and its spin count), not
        # the base-game big/mega/epic tier popup.
        in_free_spins=was_in_free_spins or triggered_now,
        free_spins_remaining_after=round_status.remaining_after,
        free_spins_round_total_win=round_status.round_total_win,
        spins_awarded=trigger_result.details.get("spins_awarded") if trigger_result else None,
    )

    feature_out = free_spins_feature_out(
        triggered_now=triggered_now,
        was_in_free_spins=was_in_free_spins,
        trigger_result=trigger_result,
        remaining_after=round_status.remaining_after,
        round_total_win=round_status.round_total_win,
    )

    balance_before = Decimal(str(session.balance))
    balance_after = balance_before + spin_win if was_in_free_spins else balance_before - bet_amount + spin_win

    win_breakdown: dict[str, object] = {
        "line_pay": str(evaluation.line_pay_total),
        "count_pay": str(evaluation.count_pay_total),
    }
    features_triggered = [feature_out.type] if feature_out and feature_out.triggered else []
    if wild_events:
        win_breakdown["wild_events"] = wild_events
        features_triggered.append("expanding_wild")
    if wild_multiplier_details is not None:
        win_breakdown["multiplier_wild"] = wild_multiplier_details
        # "triggered" means it actually paid, not merely that wilds drew their
        # values this spin (which happens on every spin with a wild present).
        if wild_multiplier_details["applied"]:
            features_triggered.append("multiplier_wild")
    if coin_details is not None:
        win_breakdown["coin_multiplier"] = coin_details
        # "triggered" here means it actually paid out, not merely that coin
        # values were drawn/shown this spin (which now happens on every spin
        # with a coin present — see coin_multiplier.py).
        if coin_details["applied"]:
            features_triggered.append("coin_multiplier")
    if hold_and_win_result is not None:
        win_breakdown["hold_and_win"] = hold_and_win_result.details
        features_triggered.append("hold_and_win")
    if wheel_result is not None:
        win_breakdown["wheel_of_fortune"] = wheel_result.details
        features_triggered.append("wheel_of_fortune")

    await commit_spin(
        db,
        session,
        game_config_id=game_config.id,
        bet_amount=bet_amount,
        state=state,
        grid=grid,
        win_amount=spin_win,
        win_breakdown=win_breakdown,
        features_triggered=features_triggered,
        balance_before=balance_before,
        balance_after=balance_after,
    )

    return schemas.SpinResponse(
        grid=to_frontend_grid(landed_grid or grid),
        winning_cells=[
            schemas.WinningCellOut(**c)
            for c in winning_cells(grid, evaluation.line_wins, evaluation.count_wins)
        ],
        wild_events=[schemas.WildEventOut(**e) for e in wild_events],
        line_wins=line_wins_out(evaluation.line_wins),
        count_wins=count_wins_out(evaluation.count_wins),
        total_win=int(spin_win),
        balance=int(balance_after),
        feature=feature_out,
        popup=schemas.PopupOut(**popup) if popup else None,
        coin_multiplier=coin_multiplier_out(coin_details),
        multiplier_wilds=multiplier_wilds_out(wild_multiplier_details),
        hold_and_win=hold_and_win_out(hold_and_win_result),
        wheel_of_fortune=wheel_of_fortune_out(wheel_result),
        max_win_reached=max_win_reached,
    )


def with_weight_overrides(reel_set: ReelSetConfig, overrides: dict[str, int | list[int]]) -> ReelSetConfig:
    """The same reel set with the named symbols re-weighted — free-spins
    weight sets and the bought Hold & Win spin. A plain number applies to
    every reel; a list is per reel (Savannah Kings' FS lion: 0 on reels 1
    and 5, where it never lands)."""
    def reweighted(weight: int | list[int]) -> list[int]:
        if isinstance(weight, list):
            return [int(w) for w in weight]
        return [int(weight)] * reel_set.num_reels

    return dataclasses.replace(
        reel_set,
        symbols=[
            dataclasses.replace(sym, weights=reweighted(overrides[sym.code]))
            if sym.code in overrides else sym
            for sym in reel_set.symbols
        ],
    )


async def run_feature_buy(
    db: AsyncSession, session: Session, feature_id: str, requested_bet_amount: int, rng: RNGProvider
) -> schemas.SpinResponse:
    game_config = await load_active_config(db, session.game_id)
    reel_set = to_reel_set_config(game_config)

    tumble_config = find_feature_config(game_config, "scatter_tumble")
    if tumble_config is not None:
        return await run_tumble_buy(db, session, game_config, feature_id, requested_bet_amount, rng, tumble_config)

    avalanche_config = find_feature_config(game_config, "avalanche")
    if avalanche_config is not None:
        return await run_avalanche_feature_buy(
            db, session, game_config, reel_set, feature_id, requested_bet_amount, rng, avalanche_config
        )

    paylines = to_paylines(game_config)

    state = dict(session.state)
    balance_before = Decimal(str(session.balance))
    plan = prepare_feature_buy(
        game_config, state, feature_id, requested_bet_amount, len(paylines), balance_before
    )
    bet_amount = plan.bet_amount

    # The purchase still spins real reels (TZ: server-authoritative, no fake
    # results) — the player can win on this spin in addition to the
    # guaranteed feature entry, matching the "response как у /spin" contract.
    hw_params = plan.target_config.params if plan.target_feature_id == "hold_and_win" else {}
    product = plan.product
    # Neon Joker Spins (GDD-02 §7): the purchase spin draws on the base
    # weights with buy_exclude_symbols (the scatter) removed, redrawn until it
    # shows at least buy_min_coins coins — a real, server-drawn grid that
    # opens the round on its own coins. Savannah Kings sets the same key per
    # product (GDD-03 §6.4.3: no paws on a Free Spins buy, no masks on a
    # Jackpot Chance buy — a purchase never opens the other feature).
    buy_exclude = product.get("buy_exclude_symbols") or hw_params.get("buy_exclude_symbols")
    if buy_exclude:
        reel_set = with_weight_overrides(reel_set, {code: 0 for code in buy_exclude})
    min_coins = int(hw_params.get("buy_min_coins") or 0)
    coin_code = hw_params.get("trigger_symbol_code", "coin")
    for _ in range(100_000):
        grid = spin_reels(reel_set, rng)
        grid = apply_reel_caps(grid, reel_set, rng)
        if sum(column.count(coin_code) for column in grid.reels) >= min_coins:
            break

    # Volt Coins (product): a bought Hold & Win lands its own trigger — the
    # coin line from `buy_coin_line` (row index per reel) — so the player
    # sees the line that "won" the round, exactly like a natural trigger.
    buy_line = hw_params.get("buy_coin_line")
    if buy_line:
        coin_code = hw_params.get("trigger_symbol_code", "coin")
        for reel_index, row_index in enumerate(buy_line):
            grid.reels[reel_index][row_index] = coin_code

    # Savannah Kings: the purchase spin shows its own trigger — `count` of
    # `symbol` on distinct reels picked from `reels`, at random rows — so the
    # player sees the masks/paws that "won" the feature.
    buy_force = product.get("buy_force")
    if buy_force:
        candidate_reels = list(buy_force["reels"])
        for _ in range(int(buy_force.get("count", len(candidate_reels)))):
            index, _, _ = weighted_pick([1] * len(candidate_reels), rng)
            reel_index = candidate_reels.pop(index)
            row_index, _, _ = weighted_pick([1] * reel_set.num_rows, rng)
            grid.reels[reel_index][row_index] = buy_force["symbol"]

    wild_config = find_feature_config(game_config, "expanding_wild")
    wild_events = apply_expanding_wild(
        grid, wild_config, state, rng, Decimal(bet_amount), reel_set, is_bonus_buy=True
    )

    bet_per_line = Decimal(bet_amount) / Decimal(len(paylines))
    evaluation = evaluate_spin(grid, reel_set.symbols, paylines, bet_per_line, Decimal(bet_amount))
    # GDD-02 §7: line wins of the purchase spin are not paid (nor shown).
    if hw_params.get("buy_pay_lines", True) is False:
        evaluation = evaluate_spin(grid, reel_set.symbols, [], bet_per_line, Decimal(bet_amount))
    # GDD-03 §6.4.3: the purchase spin pays nothing at all — no lines and no
    # scatter pay for the masks it shows.
    if product.get("buy_pay_spin", True) is False:
        evaluation = WinEvaluation(line_wins=(), count_wins=())
    spin_win = evaluation.total_win

    ctx = FeatureContext(
        session_state=state,
        rng=rng,
        bet_amount=Decimal(bet_amount),
        symbols=reel_set.symbols,
        grid=grid,
        win_evaluation=evaluation,
        is_bonus_buy=True,
    )
    # Games whose round starts from the coins' base-game faces
    # (initial_from_base_coins — Volt Coins) need those faces drawn on the
    # bought spin too; nobody else runs coin_multiplier on a buy.
    coin_details = None
    if hw_params.get("initial_from_base_coins"):
        coin_feature = default_registry.get("coin_multiplier")
        coin_config = find_feature_config(game_config, "coin_multiplier")
        if coin_feature is not None and coin_config is not None and coin_feature.is_triggered(ctx, coin_config.params):
            coin_result = coin_feature.execute(ctx, coin_config.params)
            coin_details = coin_result.details
            ctx.coin_values = coin_details["coin_positions"]
            spin_win += coin_result.win_amount
    # Forced entry: bonus_buy bypasses is_triggered (that's the point of
    # paying for it) and calls execute() directly, without also running the
    # natural scatter-trigger check — avoids double-awarding spins if the
    # purchase spin happens to land 3+ scatters on its own.
    result = plan.target_feature.execute(ctx, plan.target_config.params)
    state.update(result.state_patch)

    # Hold & Win resolves entirely in this one call (no state carried to a
    # future spin, unlike free_spins) — its payout is added to this spin's
    # own win right away, and the response carries a HoldAndWinOut (like a
    # natural trigger would) instead of the generic FeatureOut used below.
    is_hold_and_win = plan.target_feature_id == "hold_and_win"
    is_wheel = plan.target_feature_id == "wheel_of_fortune"
    hold_and_win_result = result if is_hold_and_win else None
    wheel_result = result if is_wheel else None
    max_win_reached = False
    if is_hold_and_win or is_wheel:
        spin_win += result.win_amount
        # The cap counts from the bet, not the purchase price (GDD-02 §7.7).
        fs_config = find_feature_config(game_config, "free_spins")
        spin_win, max_win_reached = free_spins_round.apply_cap(
            state, spin_win, bet_amount,
            fs_config.params.get("round_max_win_multiplier") if fs_config is not None else None,
            False, False,
        )
    else:
        free_spins_round.enter_round(state, bet_amount)

    balance_after = balance_before - plan.cost + spin_win

    win_breakdown: dict[str, object] = {
        "line_pay": str(evaluation.line_pay_total),
        "count_pay": str(evaluation.count_pay_total),
    }
    features_triggered = [plan.target_feature_id]
    if wild_events:
        win_breakdown["wild_events"] = wild_events
        features_triggered.append("expanding_wild")
    if hold_and_win_result is not None:
        win_breakdown["hold_and_win"] = hold_and_win_result.details
    if wheel_result is not None:
        win_breakdown["wheel_of_fortune"] = wheel_result.details

    await commit_spin(
        db,
        session,
        game_config_id=game_config.id,
        bet_amount=bet_amount,
        state=state,
        grid=grid,
        win_amount=spin_win,
        win_breakdown=win_breakdown,
        features_triggered=features_triggered,
        balance_before=balance_before,
        balance_after=balance_after,
        is_bonus_buy=True,
        feature_buy_id=feature_id,
    )

    feature_out = None
    popup = None
    if not is_hold_and_win and not is_wheel:
        feature_out = schemas.FeatureOut(
            type=plan.target_feature_id,
            triggered=True,
            spins_awarded=result.details.get("spins_awarded"),
            spins_remaining=int(state.get("free_spins_remaining", 0)),
            total_win=0,
        )
        popup = schemas.PopupOut(type="buyFreeSpins", amount=int(plan.cost))

    return schemas.SpinResponse(
        grid=to_frontend_grid(grid),
        winning_cells=[
            schemas.WinningCellOut(**c)
            for c in winning_cells(grid, evaluation.line_wins, evaluation.count_wins)
        ],
        wild_events=[schemas.WildEventOut(**e) for e in wild_events],
        line_wins=line_wins_out(evaluation.line_wins),
        count_wins=count_wins_out(evaluation.count_wins),
        total_win=int(spin_win),
        balance=int(balance_after),
        feature=feature_out,
        popup=popup,
        coin_multiplier=coin_multiplier_out(coin_details),
        hold_and_win=hold_and_win_out(hold_and_win_result),
        wheel_of_fortune=wheel_of_fortune_out(wheel_result),
        max_win_reached=max_win_reached,
    )
