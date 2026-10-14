"""Games removed from the project for good. Their seeds, tests and front
files are gone, but the rows they left in an existing database (Railway's
SQLite volume, a dev Postgres) would keep them in GET /api/v1/catalog with
a dead play link — so app startup drops them here.

Deletes go bottom-up and explicitly rather than relying on ON DELETE
CASCADE: SQLite doesn't enforce foreign keys unless asked, and
SpinRecord's FKs are RESTRICT (kept for the audit trail on live games).
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.builder_draft import BuilderDraft
from app.models.config import FeatureConfig, GameConfig, Payline, Symbol
from app.models.game import Game
from app.models.session import Session
from app.models.simulation import SimulationRun
from app.models.spin import SpinRecord

RETIRED_GAME_CODES = (
    "country-gold-3",
    "lucky-miami-3",
    "miami-fruits-3",
    "western-treasure",
)


async def purge_retired_games(db: AsyncSession) -> None:
    game_ids = (
        await db.execute(select(Game.id).where(Game.code.in_(RETIRED_GAME_CODES)))
    ).scalars().all()
    if not game_ids:
        return

    config_ids = select(GameConfig.id).where(GameConfig.game_id.in_(game_ids))
    session_ids = select(Session.id).where(Session.game_id.in_(game_ids))

    await db.execute(
        delete(SpinRecord).where(
            SpinRecord.game_config_id.in_(config_ids) | SpinRecord.session_id.in_(session_ids)
        )
    )
    for model in (Symbol, Payline, FeatureConfig, SimulationRun):
        await db.execute(delete(model).where(model.game_config_id.in_(config_ids)))
    await db.execute(delete(Session).where(Session.game_id.in_(game_ids)))
    await db.execute(delete(GameConfig).where(GameConfig.game_id.in_(game_ids)))
    await db.execute(delete(BuilderDraft).where(BuilderDraft.game_id.in_(game_ids)))
    await db.execute(delete(Game).where(Game.id.in_(game_ids)))
    await db.commit()
