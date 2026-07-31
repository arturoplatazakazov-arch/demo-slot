from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game


async def backfill_catalog_fields(
    db: AsyncSession, game: Game, *, badge: str, description: str, cover_path: str, play_url: str
) -> None:
    """The 4 demo games' `get_or_seed_active_config()` only creates a fresh
    Game row the very first time it runs — on every later app start it finds
    the already-ACTIVE config and returns early, so a Game row seeded before
    front/games.html's catalog fields (app/models/game.py) existed would
    otherwise stay stuck with them all None forever. Called unconditionally
    on every seed run; only writes (and commits) when something's actually
    missing, so it's a no-op after the first backfill."""
    if game.catalog_badge is not None:
        return
    game.catalog_badge = badge
    game.catalog_description = description
    game.catalog_cover_path = cover_path
    game.catalog_play_url = play_url
    await db.commit()
