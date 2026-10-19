"""Spin / buy orchestration for games with an enabled "scatter_tumble"
FeatureConfig row (Olympus Thunder, GDD-04) — the scatter-pays tumble
engine in app/engine/scatter_tumble*.py.

Round state rides on the same Session.state keys as every other free-spins
game (app/services/free_spins_round.py), so session resume and the
"bet is locked during a round" rule work unchanged:
  free_spins_remaining / free_spins_total_win / free_spins_bet_amount,
  free_spins_multiplier = the round's TOTAL MULTIPLIER (starts at 1),
plus two keys of its own:
  tumble_mode       — "fs" | "super" (which weight table free spins draw from)
  tumble_round_base — what the spin / purchase that opened the round already
                      paid, in money, so the 10 000x cap covers the whole round.

Everything the client animates is in `SpinResponse.tumble` (see
`_tumble_out`); `feature` carries the usual free-spins counters.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import schemas
from app.api.v1.loaders import resolve_spin_bet, validate_bet_amount
from app.api.v1.spin_persistence import commit_spin
from app.engine.rng import RNGProvider
from app.engine.scatter_tumble_game import SpinOutcome, TumbleGame, play_base_spin, play_free_spin, play_service_spin
from app.engine.types import SpinGrid
from app.models.config import FeatureConfig, GameConfig
from app.models.session import Session
from app.services import free_spins_round


def tumble_game(game_config: GameConfig, feature: FeatureConfig) -> TumbleGame:
    return TumbleGame.from_params(feature.params, game_config.num_reels, game_config.num_rows)


def _rows(grid: list[list[str]]) -> list[list[str]]:
    """reel-major engine grid -> row-major client grid."""
    return [[grid[reel][row] for reel in range(len(grid))] for row in range(len(grid[0]))]


def _cell(reel: int, row: int) -> dict:
    return {"col": reel, "row": row}


def _money(x_bet: Decimal, bet: int) -> int:
    return int(x_bet * bet)


def _tumble_out(out: SpinOutcome, bet: int) -> dict:
    series = out.series
    return {
        "mode": out.mode,
        "service": out.service,
        "steps": [
            {
                "wins": [
                    {
                        "symbol": w.symbol,
                        "count": w.count,
                        "amount": _money(w.pay, bet),
                        "positions": [_cell(r, w_) for r, w_ in w.positions],
                    }
                    for w in step.wins
                ],
                "removed": [_cell(r, w_) for r, w_ in step.removed],
                "step_win": _money(step.pay, bet),
                "grid_after": _rows(step.grid_after),
            }
            for step in series.steps
        ],
        "base_win": _money(out.base_pay, bet),
        "orbs": [{"col": r, "row": w_, "value": v} for r, w_, v in series.orbs()],
        "orb_sum": out.orb_sum,
        "applied_multiplier": out.applied_multiplier,
        "series_win": _money(out.series_pay, bet),
        "total_multiplier_before": out.total_multiplier_before,
        "total_multiplier_after": out.total_multiplier_after,
        "scatter_count": out.scatter_count,
        "scatter_win": _money(out.scatter_pay, bet),
        "free_spins_awarded": out.fs_awarded,
        "eagle_count": out.eagle_count,
        "jackpot": (
            {"tier": out.jackpot.tier, "sector": out.jackpot.sector, "amount": _money(out.jackpot.pay, bet)}
            if out.jackpot
            else None
        ),
        "capped": out.capped,
        "spin_win": _money(out.paid, bet),
    }


def _breakdown(out: SpinOutcome, bet: int) -> dict:
    data = _tumble_out(out, bet)
    data.pop("steps")
    data["steps"] = [{"wins": [(w.symbol, w.count, str(w.pay)) for w in s.wins]} for s in out.series.steps]
    return data


def _final_grid(out: SpinOutcome) -> SpinGrid:
    return SpinGrid(reels=[list(c) for c in out.series.final], draws=[])


def _feature_out(state: dict, *, triggered: bool, awarded: int | None, multiplier: int, round_win: Decimal) -> schemas.FeatureOut:
    return schemas.FeatureOut(
        type="free_spins",
        triggered=triggered,
        spins_awarded=awarded,
        spins_remaining=int(state.get("free_spins_remaining", 0)),
        total_win=int(round_win),
        multiplier=multiplier,
    )


def _open_round(state: dict, bet: int, spins: int, mode: str, already_paid: Decimal) -> None:
    state["free_spins_remaining"] = spins
    state["free_spins_multiplier"] = "1"
    state["tumble_mode"] = mode
    state["tumble_round_base"] = str(already_paid)
    free_spins_round.enter_round(state, bet)


def _close_round(state: dict) -> None:
    for key in (*free_spins_round.STATE_KEYS, "tumble_mode", "tumble_round_base"):
        state.pop(key, None)


async def run_tumble_spin(
    db: AsyncSession,
    session: Session,
    game_config: GameConfig,
    requested_bet_amount: int,
    rng: RNGProvider,
    feature: FeatureConfig,
) -> schemas.SpinResponse:
    game = tumble_game(game_config, feature)
    state = dict(session.state)
    bet, in_round = resolve_spin_bet(game_config, state, requested_bet_amount, 0)
    balance_before = Decimal(str(session.balance))

    if not in_round:
        out = play_base_spin(game, rng)
        win = Decimal(_money(out.paid, bet))
        feature_out = None
        if out.fs_awarded:
            _open_round(state, bet, out.fs_awarded, "fs", win)
            feature_out = _feature_out(state, triggered=True, awarded=out.fs_awarded, multiplier=1, round_win=Decimal(0))
        balance_after = balance_before - bet + win
    else:
        super_mode = state.get("tumble_mode") == "super"
        total_mult = int(Decimal(str(state.get("free_spins_multiplier", "1"))))
        round_base = Decimal(str(state.get("tumble_round_base", "0")))
        round_win = Decimal(str(state.get("free_spins_total_win", "0")))
        so_far_x = (round_base + round_win) / bet
        out = play_free_spin(game, rng, super_mode=super_mode, total_multiplier=total_mult, round_so_far=so_far_x)
        win = Decimal(_money(out.paid, bet))
        round_win += win
        remaining = int(state.get("free_spins_remaining", 0)) - 1 + out.fs_awarded
        if out.capped:
            remaining = 0
        state["free_spins_remaining"] = remaining
        state["free_spins_multiplier"] = str(out.total_multiplier_after)
        state["free_spins_total_win"] = str(round_win)
        feature_out = _feature_out(
            state, triggered=bool(out.fs_awarded), awarded=out.fs_awarded or None,
            multiplier=out.total_multiplier_after, round_win=round_win,
        )
        if remaining <= 0:
            _close_round(state)
        balance_after = balance_before + win

    await commit_spin(
        db, session,
        game_config_id=game_config.id, bet_amount=bet, state=state, grid=_final_grid(out),
        win_amount=win, win_breakdown=_breakdown(out, bet),
        features_triggered=(["free_spins"] if out.fs_awarded else []) + (["jackpot"] if out.jackpot else []),
        balance_before=balance_before, balance_after=balance_after,
    )
    return schemas.SpinResponse(
        grid=_rows(out.series.initial), winning_cells=[], line_wins=[], count_wins=[],
        total_win=int(win), balance=int(balance_after), feature=feature_out,
        tumble=_tumble_out(out, bet),
    )


async def run_tumble_buy(
    db: AsyncSession,
    session: Session,
    game_config: GameConfig,
    feature_id: str,
    requested_bet_amount: int,
    rng: RNGProvider,
    feature: FeatureConfig,
) -> schemas.SpinResponse:
    """Same check order as app/api/v1/bonus_buy.py: active round 400 ->
    unknown/disabled SKU 404 -> bet 400 -> balance 400."""
    game = tumble_game(game_config, feature)
    state = dict(session.state)
    balance_before = Decimal(str(session.balance))
    if free_spins_round.is_active(state):
        raise HTTPException(status_code=400, detail="a bonus round is already active")
    product = game.product(feature_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown or disabled feature_id")
    validate_bet_amount(game_config, requested_bet_amount, 0)
    bet = requested_bet_amount
    cost = product.cost * bet
    if balance_before < cost:
        raise HTTPException(status_code=400, detail="insufficient balance for this purchase")

    out = play_service_spin(game, product, rng)
    win = Decimal(_money(out.paid, bet))  # only a bought wheel pays here
    feature_out = None
    if out.fs_awarded:
        mode = "super" if product.kind == "super_free_spins" else "fs"
        _open_round(state, bet, out.fs_awarded, mode, Decimal(0))
        feature_out = _feature_out(state, triggered=True, awarded=out.fs_awarded, multiplier=1, round_win=Decimal(0))
    balance_after = balance_before - cost + win

    await commit_spin(
        db, session,
        game_config_id=game_config.id, bet_amount=bet, state=state, grid=_final_grid(out),
        win_amount=win, win_breakdown=_breakdown(out, bet),
        features_triggered=["jackpot"] if out.jackpot else ["free_spins"],
        balance_before=balance_before, balance_after=balance_after,
        is_bonus_buy=True, feature_buy_id=feature_id,
    )
    return schemas.SpinResponse(
        grid=_rows(out.series.initial), winning_cells=[], line_wins=[], count_wins=[],
        total_win=int(win), balance=int(balance_after), feature=feature_out,
        popup=schemas.PopupOut(type="buyFreeSpins", amount=int(cost)),
        tumble={**_tumble_out(out, bet), "buy_id": product.buy_id, "buy_kind": product.kind},
    )


def tumble_rules_out(game_config: GameConfig, feature: FeatureConfig) -> dict:
    """Session-start payload the client builds its buy window, jackpot plates
    and paytable from (prices in x bet; the client multiplies by its bet)."""
    params = feature.params
    buy = params.get("bonus_buy", {})
    return {
        "mechanic": "scatter_tumble",
        "paytable": params["paytable"],
        "scatter_pays": params["scatter_pays"],
        "orb_values": [v for v, _ in params["orb_values"]],
        "free_spins": params["free_spins"],
        "jackpot": {
            "prizes": params["jackpot"]["prizes"],
            "sectors": params["jackpot"]["sectors"],
            "trigger_count": params["jackpot"]["trigger_count"],
            "natural_odds": params["jackpot"]["natural_odds"],
            "buy_odds": params["jackpot"]["buy_odds"],
        },
        "bonus_buy": {
            "enabled": bool(buy.get("enabled", True)),
            "products": [
                {"buy_id": p["buy_id"], "kind": p["kind"], "cost_multiplier": p["cost_multiplier"]}
                for p in buy.get("products", [])
                if p.get("enabled", True)
            ] if buy.get("enabled", True) else [],
        },
        "max_win_multiplier": params.get("max_win_multiplier", 10000),
    }
