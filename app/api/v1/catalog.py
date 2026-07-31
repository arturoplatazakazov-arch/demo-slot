"""Public catalog listing for front/games.html — every Game that has an
ACTIVE GameConfig (i.e. actually published/playable), so a slot built and
published via the slot-builder wizard (app/api/admin/builder.py's
publish-live route) shows up automatically without hand-editing games.html.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.api.v1.schemas import CatalogEntryOut, SymbolArtOut
from app.models.config import GameConfig
from app.models.enums import GameConfigStatus
from app.models.game import Game

router = APIRouter()


@router.get("/catalog", response_model=list[CatalogEntryOut])
async def list_catalog(db: AsyncSession = Depends(get_db)) -> list[CatalogEntryOut]:
    result = await db.execute(
        select(Game)
        .join(GameConfig, GameConfig.game_id == Game.id)
        .where(GameConfig.status == GameConfigStatus.ACTIVE.value)
        .distinct()
        .order_by(Game.created_at)
    )
    return [
        CatalogEntryOut(
            code=game.code,
            name=game.name,
            catalog_badge=game.catalog_badge,
            catalog_description=game.catalog_description,
            catalog_cover_path=game.catalog_cover_path,
            catalog_play_url=game.catalog_play_url,
        )
        for game in result.scalars().all()
    ]


@router.get("/config/{code}/symbols", response_model=list[SymbolArtOut])
async def list_symbol_art(code: str, db: AsyncSession = Depends(get_db)) -> list[SymbolArtOut]:
    """code -> builder asset id for the ACTIVE config's symbols, for
    front/play.html's generic renderer to resolve into real image URLs via
    the builder manifest's assets.images (image_ref is a builder asset id,
    not a path — see Symbol.image_ref's docstring)."""
    result = await db.execute(
        select(GameConfig)
        .join(Game, Game.id == GameConfig.game_id)
        .where(Game.code == code, GameConfig.status == GameConfigStatus.ACTIVE.value)
        .options(selectinload(GameConfig.symbols))
    )
    config = result.scalars().first()
    if config is None:
        raise HTTPException(status_code=404, detail=f"no active config for game '{code}'")
    return [SymbolArtOut(code=s.code, image_ref=s.image_ref) for s in config.symbols]
