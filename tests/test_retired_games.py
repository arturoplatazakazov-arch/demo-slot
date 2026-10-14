"""Tests for app/seed/retired.py — startup purge of games removed from the
project, so their leftover DB rows drop out of GET /api/v1/catalog."""

from sqlalchemy import func, select

from app.models import Game, GameConfig, Symbol
from app.models.session import Session
from app.models.spin import SpinRecord
from app.seed.amys_fruit_farm import get_or_seed_active_config as get_or_seed_amys_fruit_farm
from app.seed.east_discovery import get_or_seed_active_config as get_or_seed_east_discovery
from app.seed.retired import purge_retired_games


async def _count(db, model):
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_purge_drops_retired_game_with_play_history_and_keeps_others(db_session):
    # Stand-in for a retired game: seed a real one, give it a session and a
    # spin record (the RESTRICT FKs), then rename it to a retired code.
    retired_config = await get_or_seed_amys_fruit_farm(db_session)
    kept_config = await get_or_seed_east_discovery(db_session)
    session = Session(game_id=retired_config.game_id, balance=1000)
    db_session.add(session)
    await db_session.flush()
    db_session.add(SpinRecord(
        session_id=session.id, game_config_id=retired_config.id, bet_amount=10,
        grid=[], balance_before=1000, balance_after=990,
    ))
    game = await db_session.get(Game, retired_config.game_id)
    game.code = "western-treasure"
    await db_session.commit()

    await purge_retired_games(db_session)

    codes = set((await db_session.execute(select(Game.code))).scalars().all())
    assert codes == {"east-discovery"}
    assert await _count(db_session, SpinRecord) == 0
    assert await _count(db_session, Session) == 0
    remaining_configs = (await db_session.execute(select(GameConfig.id))).scalars().all()
    assert remaining_configs == [kept_config.id]
    symbol_configs = set((await db_session.execute(select(Symbol.game_config_id))).scalars().all())
    assert symbol_configs == {kept_config.id}


async def test_purge_is_a_noop_without_retired_games(db_session):
    await get_or_seed_east_discovery(db_session)
    await purge_retired_games(db_session)
    assert await _count(db_session, Game) == 1
