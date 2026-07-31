"""Spin settlement write-back shared by all four spin paths: balance/state
onto the Session row plus the append-only SpinRecord audit entry (TZ §11),
committed together."""

import dataclasses
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.types import SpinGrid
from app.models.session import Session
from app.models.spin import SpinRecord


async def commit_spin(
    db: AsyncSession,
    session: Session,
    *,
    game_config_id,
    bet_amount: int,
    state: dict,
    grid: SpinGrid,
    win_amount: Decimal,
    win_breakdown: dict,
    features_triggered: list[str],
    balance_before: Decimal,
    balance_after: Decimal,
    is_bonus_buy: bool = False,
    feature_buy_id: str | None = None,
) -> None:
    session.balance = balance_after
    session.state = state
    db.add(
        SpinRecord(
            session_id=session.id,
            game_config_id=game_config_id,
            bet_amount=bet_amount,
            is_bonus_buy=is_bonus_buy,
            feature_buy_id=feature_buy_id,
            grid=grid.reels,
            win_amount=win_amount,
            win_breakdown=win_breakdown,
            features_triggered=features_triggered,
            rng_proof={"draws": [dataclasses.asdict(d) for d in grid.draws]},
            balance_before=balance_before,
            balance_after=balance_after,
        )
    )
    await db.commit()
