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
)
from app.api.v1.spin_avalanche import run_avalanche_feature_buy, run_avalanche_spin
from app.api.v1.spin_persistence import commit_spin
from app.engine.reels import spin_reels
from app.engine.rng import RNGProvider
from app.engine.wins import evaluate_spin
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
    wild_events = apply_expanding_wild(grid, wild_config, state, rng, Decimal(bet_amount), reel_set)

    bet_per_line = Decimal(bet_amount) / Decimal(len(paylines))
    evaluation = evaluate_spin(grid, reel_set.symbols, paylines, bet_per_line, Decimal(bet_amount))

    ctx = FeatureContext(
        session_state=state,
        rng=rng,
        bet_amount=Decimal(bet_amount),
        symbols=reel_set.symbols,
        grid=grid,
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

    multiplier = free_spins_round.win_multiplier(state, was_in_free_spins)
    spin_win = (evaluation.total_win + coin_bonus) * multiplier

    triggered_now = False
    trigger_result = None
    if free_spins_feature is not None and free_spins_config is not None:
        if free_spins_feature.is_triggered(ctx, free_spins_config.params):
            trigger_result = free_spins_feature.execute(ctx, free_spins_config.params)
            state.update(trigger_result.state_patch)
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

    win_breakdown = {
        "line_pay": str(evaluation.line_pay_total),
        "count_pay": str(evaluation.count_pay_total),
    }
    features_triggered = [feature_out.type] if feature_out and feature_out.triggered else []
    if wild_events:
        win_breakdown["wild_events"] = wild_events
        features_triggered.append("expanding_wild")
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
        popup=schemas.PopupOut(**popup) if popup else None,
        coin_multiplier=coin_multiplier_out(coin_details),
        hold_and_win=hold_and_win_out(hold_and_win_result),
    )


async def run_feature_buy(
    db: AsyncSession, session: Session, feature_id: str, requested_bet_amount: int, rng: RNGProvider
) -> schemas.SpinResponse:
    game_config = await load_active_config(db, session.game_id)
    reel_set = to_reel_set_config(game_config)

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
    grid = spin_reels(reel_set, rng)
    grid = apply_reel_caps(grid, reel_set, rng)

    wild_config = find_feature_config(game_config, "expanding_wild")
    wild_events = apply_expanding_wild(
        grid, wild_config, state, rng, Decimal(bet_amount), reel_set, is_bonus_buy=True
    )

    bet_per_line = Decimal(bet_amount) / Decimal(len(paylines))
    evaluation = evaluate_spin(grid, reel_set.symbols, paylines, bet_per_line, Decimal(bet_amount))
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
    hold_and_win_result = result if is_hold_and_win else None
    if is_hold_and_win:
        spin_win += result.win_amount
    else:
        free_spins_round.enter_round(state, bet_amount)

    balance_after = balance_before - plan.cost + spin_win

    win_breakdown = {
        "line_pay": str(evaluation.line_pay_total),
        "count_pay": str(evaluation.count_pay_total),
    }
    features_triggered = [plan.target_feature_id]
    if wild_events:
        win_breakdown["wild_events"] = wild_events
        features_triggered.append("expanding_wild")
    if hold_and_win_result is not None:
        win_breakdown["hold_and_win"] = hold_and_win_result.details

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
    if not is_hold_and_win:
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
        hold_and_win=hold_and_win_out(hold_and_win_result),
    )
