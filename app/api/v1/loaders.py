"""Session/config loading and bet validation shared by every v1 route and
both spin orchestrations (spin_service.py, spin_avalanche.py)."""

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1 import schemas
from app.models.config import GameConfig
from app.models.enums import GameConfigStatus
from app.models.session import Session
from app.services import free_spins_round


async def load_session(db: AsyncSession, session_id: uuid.UUID) -> Session:
    session_obj = await db.get(Session, session_id)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session_obj


async def load_active_config(db: AsyncSession, game_id: uuid.UUID) -> GameConfig:
    result = await db.execute(
        select(GameConfig)
        .where(GameConfig.game_id == game_id, GameConfig.status == GameConfigStatus.ACTIVE.value)
        .options(
            selectinload(GameConfig.symbols),
            selectinload(GameConfig.paylines),
            selectinload(GameConfig.feature_configs),
        )
    )
    config = result.scalars().first()
    if config is None:
        raise HTTPException(status_code=409, detail="no active config for this game")
    return config


def validate_bet_amount(game_config: GameConfig, bet_amount: int, num_paylines: int) -> None:
    if game_config.bet_steps:
        allowed = {int(x) for x in game_config.bet_steps}
        if bet_amount not in allowed:
            raise HTTPException(status_code=400, detail=f"bet_amount must be one of {sorted(allowed)}")
    else:
        if not (game_config.min_bet <= bet_amount <= game_config.max_bet):
            raise HTTPException(status_code=400, detail="bet_amount out of allowed range")
        if Decimal(bet_amount) % Decimal(str(game_config.bet_step)) != 0:
            raise HTTPException(status_code=400, detail="bet_amount must be a multiple of bet_step")
    # num_paylines == 0 means this game has no payline concept at all
    # (avalanche/count-anywhere mechanic, app/engine/avalanche.py) — nothing
    # to check divisibility against.
    if num_paylines > 0 and bet_amount % num_paylines != 0:
        raise HTTPException(
            status_code=400, detail="bet_amount must be evenly divisible by the number of paylines"
        )


def resolve_spin_bet(
    game_config: GameConfig, state: dict, requested_bet_amount: int, num_paylines: int
) -> tuple[int, bool]:
    """(bet_amount, was_in_free_spins): inside a free-spins round the round's
    locked bet replays and the request's amount is ignored; outside one the
    requested bet is validated and used."""
    if free_spins_round.is_active(state):
        return free_spins_round.locked_bet_amount(state), True
    validate_bet_amount(game_config, requested_bet_amount, num_paylines)
    return requested_bet_amount, False


def _default_bet(game_config: GameConfig) -> int:
    steps = game_config.bet_steps or []
    if steps:
        return int(steps[len(steps) // 2])
    return int(game_config.min_bet)


def bet_config_out(game_config: GameConfig) -> schemas.BetConfig:
    return schemas.BetConfig(
        min=int(game_config.min_bet),
        max=int(game_config.max_bet),
        step=int(game_config.bet_step),
        default=_default_bet(game_config),
        steps=[int(x) for x in (game_config.bet_steps or [])],
    )


def find_feature_config(game_config: GameConfig, feature_type: str):
    """The enabled FeatureConfig row for `feature_type`, or None."""
    for fc in game_config.feature_configs:
        if fc.feature_type == feature_type and fc.enabled:
            return fc
    return None
