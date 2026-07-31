import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1 import schemas
from app.api.v1.loaders import bet_config_out, load_active_config, load_session
from app.core.config import get_settings
from app.models.game import Game
from app.models.session import Session

router = APIRouter()


@router.post("/session/start", response_model=schemas.SessionStartResponse)
async def start_session(
    body: schemas.SessionStartRequest, db: AsyncSession = Depends(get_db)
) -> schemas.SessionStartResponse:
    result = await db.execute(select(Game).where(Game.code == body.game_id))
    game = result.scalars().first()
    if game is None:
        raise HTTPException(status_code=404, detail="unknown game_id")

    game_config = await load_active_config(db, game.id)
    settings = get_settings()

    session = Session(
        game_id=game.id, balance=settings.default_starting_balance, currency=settings.default_currency
    )
    db.add(session)
    await db.commit()

    free_spins_config = next(
        (fc for fc in game_config.feature_configs if fc.feature_type == "free_spins" and fc.enabled), None
    )
    free_spins_trigger = (
        schemas.FreeSpinsTriggerOut(
            trigger_symbol_code=free_spins_config.params.get("trigger_symbol_code", "scatter"),
            trigger_count=free_spins_config.params.get("trigger_count", 3),
        )
        if free_spins_config is not None
        else None
    )

    hold_and_win_config = next(
        (fc for fc in game_config.feature_configs if fc.feature_type == "hold_and_win" and fc.enabled), None
    )
    hold_and_win_trigger = (
        schemas.HoldAndWinTriggerOut(
            trigger_symbol_code=hold_and_win_config.params.get("trigger_symbol_code", "collector_tiger"),
            trigger_count=hold_and_win_config.params.get("trigger_count", 3),
        )
        if hold_and_win_config is not None
        else None
    )

    return schemas.SessionStartResponse(
        session_id=session.id,
        balance=int(session.balance),
        currency=session.currency,
        bet=bet_config_out(game_config),
        symbols=[
            schemas.PaytableSymbolOut(
                code=s.code, name=s.name, symbol_type=s.symbol_type, paytable=dict(s.paytable)
            )
            for s in game_config.symbols
        ],
        free_spins_trigger=free_spins_trigger,
        hold_and_win_trigger=hold_and_win_trigger,
    )


@router.get("/session/{session_id}/state", response_model=schemas.SessionStateResponse)
async def get_session_state(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> schemas.SessionStateResponse:
    session = await load_session(db, session_id)

    active_feature = None
    remaining = session.state.get("free_spins_remaining", 0)
    if remaining > 0:
        active_feature = schemas.ActiveFeatureState(
            type="free_spins",
            spins_remaining=int(remaining),
            total_win=int(Decimal(str(session.state.get("free_spins_total_win", "0")))),
        )

    return schemas.SessionStateResponse(
        session_id=session.id,
        balance=int(session.balance),
        currency=session.currency,
        active_feature=active_feature,
    )
