"""Avalanche spin orchestration — counterpart of spin_service.py for games
with an enabled "avalanche" FeatureConfig row. Such a game has no
paylines/line-pay at all (app/engine/avalanche.py replaces evaluate_spin
entirely), so this stays a separate orchestration rather than another
branch threaded through the line-pay functions. Free spins / bonus buy
still layer on top the same way, reusing app/features/free_spins.py and the
shared round lifecycle (app/services/free_spins_round.py) unmodified."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import schemas
from app.api.v1.bonus_buy import prepare_feature_buy
from app.api.v1.loaders import find_feature_config, resolve_spin_bet
from app.api.v1.response_builders import (
    avalanche_out,
    avalanche_win_breakdown,
    free_spins_feature_out,
)
from app.api.v1.spin_persistence import commit_spin
from app.engine.avalanche import run_avalanche
from app.engine.reels import spin_reels
from app.engine.rng import RNGProvider
from app.engine.types import AvalancheResult, ReelSetConfig
from app.features import default_registry
from app.features.base import FeatureContext
from app.models.config import FeatureConfig, GameConfig
from app.models.session import Session
from app.services import free_spins_round
from app.services.grid_format import to_frontend_grid
from app.services.popups import select_avalanche_popup
from app.services.spin_features import apply_reel_caps


def _run_cascade(
    reel_set: ReelSetConfig, rng: RNGProvider, bet_amount: int, avalanche_config: FeatureConfig
) -> AvalancheResult:
    grid = spin_reels(reel_set, rng)
    grid = apply_reel_caps(grid, reel_set, rng)
    params = avalanche_config.params
    return run_avalanche(
        grid,
        reel_set,
        reel_set.symbols,
        rng,
        Decimal(bet_amount),
        multiplier_steps=params.get("multiplier_steps", [1]),
        max_cascades=params.get("max_cascades", 20),
    )


def _accumulate_token_multiplier(state: dict, avalanche_result: AvalancheResult) -> None:
    """party-of-goods only: multiplier tokens (x2/x3/x5/x7) landed *this*
    spin carry over and compound the session-wide multiplier for every
    remaining spin in the free-spins round — separate from the per-spin
    trail+token step multiplier avalanche.py already folded into
    avalanche_result.total_win (that one resets every spin; this one
    persists for the whole round, confirmed product decision)."""
    token_sum_this_spin = sum(
        token.value for step in avalanche_result.steps for token in step.tokens_consumed
    )
    if token_sum_this_spin:
        current_multiplier = Decimal(str(state.get("free_spins_multiplier", "1")))
        state["free_spins_multiplier"] = str(current_multiplier + token_sum_this_spin)


def _multiplier_for_display(state: dict) -> int:
    """Captured before free_spins_round.settle's round-end cleanup (which
    pops the key) so the final spin of a round can still report what the
    multiplier had grown to."""
    return int(Decimal(str(state.get("free_spins_multiplier", "1"))))


async def run_avalanche_spin(
    db: AsyncSession,
    session: Session,
    game_config: GameConfig,
    reel_set: ReelSetConfig,
    requested_bet_amount: int,
    rng: RNGProvider,
    avalanche_config: FeatureConfig,
) -> schemas.SpinResponse:
    """Scatter count for the free-spins trigger is read off
    `avalanche_result.final_grid` (the grid after every cascade this spin has
    resolved), not the initial grid: product, this session — a scatter that
    only appears via a cascade's own refill (not on the initial grid) must
    still be able to trigger, and a scatter already on the initial grid is
    never swept up by a cascade (see app/seed/party_of_goods.py) so it
    always survives into final_grid too — checking final_grid alone
    correctly covers both cases with one lookup. This also means
    combos/tokens always finish playing out (they resolve before final_grid
    exists) before the trigger check ever runs, which is what drives the
    frontend's win-then-scatter-then-bonus sequencing (playAvalanche in
    slot.js)."""
    state = dict(session.state)
    bet_amount, was_in_free_spins = resolve_spin_bet(game_config, state, requested_bet_amount, 0)

    free_spins_feature = default_registry.get("free_spins")
    free_spins_config = find_feature_config(game_config, "free_spins")

    avalanche_result = _run_cascade(reel_set, rng, bet_amount, avalanche_config)

    ctx = FeatureContext(
        session_state=state,
        rng=rng,
        bet_amount=Decimal(bet_amount),
        symbols=reel_set.symbols,
        grid=avalanche_result.final_grid,
        is_bonus_buy=False,
    )

    multiplier = free_spins_round.win_multiplier(state, was_in_free_spins)
    spin_win = avalanche_result.total_win * multiplier

    triggered_now = False
    trigger_result = None
    if free_spins_feature is not None and free_spins_config is not None:
        if free_spins_feature.is_triggered(ctx, free_spins_config.params):
            # Retrigger: free_spins.py's own state_patch always resets
            # free_spins_multiplier to the feature's flat win_multiplier
            # baseline (fine for other games' static multiplier) — party-
            # of-goods accumulates across the whole round instead, so a
            # retrigger must not wipe out what's already built up.
            pre_trigger_multiplier = state.get("free_spins_multiplier")
            trigger_result = free_spins_feature.execute(ctx, free_spins_config.params)
            state.update(trigger_result.state_patch)
            if was_in_free_spins:
                state["free_spins_multiplier"] = pre_trigger_multiplier
            triggered_now = True
            if not was_in_free_spins:
                free_spins_round.enter_round(state, bet_amount)

    # Applies from the triggering spin onward (see _accumulate_token_multiplier).
    if was_in_free_spins or triggered_now:
        _accumulate_token_multiplier(state, avalanche_result)

    multiplier_for_display = _multiplier_for_display(state)

    round_status = free_spins_round.settle(state, spin_win, was_in_free_spins)

    popup = select_avalanche_popup(
        total_win=spin_win,
        bet_amount=Decimal(bet_amount),
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
        multiplier=multiplier_for_display,
    )

    balance_before = Decimal(str(session.balance))
    balance_after = balance_before + spin_win if was_in_free_spins else balance_before - bet_amount + spin_win

    await commit_spin(
        db,
        session,
        game_config_id=game_config.id,
        bet_amount=bet_amount,
        state=state,
        grid=avalanche_result.final_grid,
        win_amount=spin_win,
        win_breakdown=avalanche_win_breakdown(avalanche_result),
        features_triggered=[feature_out.type] if feature_out and feature_out.triggered else [],
        balance_before=balance_before,
        balance_after=balance_after,
    )

    return schemas.SpinResponse(
        grid=to_frontend_grid(avalanche_result.initial_grid),
        winning_cells=[],
        line_wins=[],
        count_wins=[],
        total_win=int(spin_win),
        balance=int(balance_after),
        feature=feature_out,
        popup=schemas.PopupOut(**popup) if popup else None,
        avalanche=avalanche_out(avalanche_result),
    )


async def run_avalanche_feature_buy(
    db: AsyncSession,
    session: Session,
    game_config: GameConfig,
    reel_set: ReelSetConfig,
    feature_id: str,
    requested_bet_amount: int,
    rng: RNGProvider,
    avalanche_config: FeatureConfig,
) -> schemas.SpinResponse:
    """Same "buy" flow as spin_service.run_feature_buy (forced feature entry,
    real spin still runs and can win), just running the avalanche cascade
    instead of evaluate_spin."""
    state = dict(session.state)
    balance_before = Decimal(str(session.balance))
    plan = prepare_feature_buy(game_config, state, feature_id, requested_bet_amount, 0, balance_before)
    bet_amount = plan.bet_amount

    avalanche_result = _run_cascade(reel_set, rng, bet_amount, avalanche_config)
    spin_win = avalanche_result.total_win

    ctx = FeatureContext(
        session_state=state,
        rng=rng,
        bet_amount=Decimal(bet_amount),
        symbols=reel_set.symbols,
        grid=avalanche_result.initial_grid,
        is_bonus_buy=True,
    )
    # Forced entry, same as the line-pay path: bypasses is_triggered, calls
    # execute() directly.
    result = plan.target_feature.execute(ctx, plan.target_config.params)
    state.update(result.state_patch)
    free_spins_round.enter_round(state, bet_amount)

    # Same session-wide multiplier accumulation as the natural-trigger path
    # above — tokens landed on this forced-entry purchase spin still carry
    # over into the free-spins session.
    _accumulate_token_multiplier(state, avalanche_result)
    multiplier_for_display = _multiplier_for_display(state)

    balance_after = balance_before - plan.cost + spin_win

    await commit_spin(
        db,
        session,
        game_config_id=game_config.id,
        bet_amount=bet_amount,
        state=state,
        grid=avalanche_result.final_grid,
        win_amount=spin_win,
        win_breakdown=avalanche_win_breakdown(avalanche_result),
        features_triggered=[plan.target_feature_id],
        balance_before=balance_before,
        balance_after=balance_after,
        is_bonus_buy=True,
        feature_buy_id=feature_id,
    )

    return schemas.SpinResponse(
        grid=to_frontend_grid(avalanche_result.initial_grid),
        winning_cells=[],
        line_wins=[],
        count_wins=[],
        total_win=int(spin_win),
        balance=int(balance_after),
        feature=schemas.FeatureOut(
            type=plan.target_feature_id,
            triggered=True,
            spins_awarded=result.details.get("spins_awarded"),
            spins_remaining=int(state.get("free_spins_remaining", 0)),
            total_win=0,
            multiplier=multiplier_for_display,
        ),
        popup=schemas.PopupOut(type="buyFreeSpins", amount=int(plan.cost)),
        avalanche=avalanche_out(avalanche_result),
    )
