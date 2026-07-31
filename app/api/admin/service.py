"""Admin config editing + simulation orchestration (TZ §8.2). Draft/publish
workflow: GameConfig is immutable once ACTIVE/ARCHIVED (app/models/config.py),
so tuning weights/paytables/caps happens on a DRAFT version — cloned from
the current active config — which the admin can simulate against as many
times as they like before publishing it (flips it to ACTIVE, archives the
previous active config)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin import schemas
from app.api.admin.builder_config import AUTO_NOTE_PREFIX, generate_default_config
from app.models.config import FeatureConfig, GameConfig, Payline, Symbol
from app.models.enums import GameConfigStatus
from app.models.game import Game
from app.models.simulation import SimulationRun
from app.simulator import FastRNG, simulate_game_config

_CONFIG_LOAD_OPTIONS = (
    selectinload(GameConfig.symbols),
    selectinload(GameConfig.paylines),
    selectinload(GameConfig.feature_configs),
)


async def _get_game(db: AsyncSession, game_code: str) -> Game:
    result = await db.execute(select(Game).where(Game.code == game_code))
    game = result.scalars().first()
    if game is None:
        raise HTTPException(status_code=404, detail=f"game '{game_code}' not found")
    return game


async def list_configs(db: AsyncSession, game_code: str) -> list[GameConfig]:
    game = await _get_game(db, game_code)
    result = await db.execute(
        select(GameConfig).where(GameConfig.game_id == game.id).order_by(GameConfig.version.desc())
    )
    return list(result.scalars().all())


async def get_config(db: AsyncSession, config_id: uuid.UUID) -> GameConfig:
    result = await db.execute(
        select(GameConfig).where(GameConfig.id == config_id).options(*_CONFIG_LOAD_OPTIONS)
    )
    config = result.scalars().first()
    if config is None:
        raise HTTPException(status_code=404, detail="config not found")
    return config


async def get_or_create_draft(db: AsyncSession, game_code: str) -> GameConfig:
    """Returns the game's existing draft if there is one (editing continues
    on it rather than piling up a new draft per click), otherwise clones the
    current active config into a fresh draft version to start from."""
    game = await _get_game(db, game_code)

    existing_draft = await db.execute(
        select(GameConfig)
        .where(GameConfig.game_id == game.id, GameConfig.status == GameConfigStatus.DRAFT.value)
        .options(*_CONFIG_LOAD_OPTIONS)
    )
    draft = existing_draft.scalars().first()
    if draft is not None:
        return draft

    active_result = await db.execute(
        select(GameConfig)
        .where(GameConfig.game_id == game.id, GameConfig.status == GameConfigStatus.ACTIVE.value)
        .options(*_CONFIG_LOAD_OPTIONS)
    )
    active = active_result.scalars().first()
    if active is None:
        raise HTTPException(status_code=409, detail="no active config to clone a draft from")

    max_version_result = await db.execute(
        select(GameConfig.version).where(GameConfig.game_id == game.id).order_by(GameConfig.version.desc())
    )
    next_version = (max_version_result.scalars().first() or 0) + 1

    new_config = GameConfig(
        game_id=active.game_id,
        version=next_version,
        status=GameConfigStatus.DRAFT.value,
        num_reels=active.num_reels,
        num_rows=active.num_rows,
        target_rtp=active.target_rtp,
        min_bet=active.min_bet,
        max_bet=active.max_bet,
        bet_step=active.bet_step,
        bet_steps=active.bet_steps,
        notes=f"Draft cloned from v{active.version} for tuning.",
    )
    for s in active.symbols:
        Symbol(
            game_config=new_config, code=s.code, name=s.name, symbol_type=s.symbol_type,
            wild_subtype=s.wild_subtype, reel_weights=list(s.reel_weights), paytable=dict(s.paytable),
            max_per_reel=s.max_per_reel, tier=s.tier, display_order=s.display_order,
        )
    for p in active.paylines:
        Payline(game_config=new_config, index=p.index, positions=list(p.positions))
    for fc in active.feature_configs:
        FeatureConfig(
            game_config=new_config, feature_type=fc.feature_type, enabled=fc.enabled,
            params=dict(fc.params), display_order=fc.display_order,
        )

    db.add(new_config)
    await db.commit()
    return await get_config(db, new_config.id)


async def generate_config_from_builder(
    db: AsyncSession, game_code: str, reels: int, rows: int, mechanics: list[str],
    symbol_assets: list[dict] | None = None,
) -> GameConfig:
    """Materializes a real `GameConfig` from the slot-builder wizard's Stage 3
    selections (app/api/admin/builder_config.py) — the step that turns a
    Builder draft into an actually simulatable/playable game. Safe to call
    again after mechanics/grid change *as long as* nothing has touched the
    result since: only replaces a config that is still our own untouched
    auto-generated draft (checked via the AUTO_NOTE_PREFIX marker in
    `notes`), never something published or hand-edited via `update_symbols`."""
    game = await _get_game(db, game_code)

    existing_result = await db.execute(select(GameConfig).where(GameConfig.game_id == game.id))
    existing = existing_result.scalars().all()
    if existing:
        only_config = existing[0]
        is_our_untouched_draft = (
            len(existing) == 1
            and only_config.status == GameConfigStatus.DRAFT.value
            and (only_config.notes or "").startswith(AUTO_NOTE_PREFIX)
        )
        if not is_our_untouched_draft:
            raise HTTPException(
                status_code=409,
                detail="a game config already exists for this game — edit it via the config editor instead of regenerating",
            )
        await db.delete(only_config)
        await db.flush()

    config = generate_default_config(game, reels, rows, mechanics, symbol_assets)
    db.add(config)
    await db.commit()
    return await get_config(db, config.id)


async def update_symbols(
    db: AsyncSession, config_id: uuid.UUID, updates: schemas.UpdateSymbolsRequest
) -> GameConfig:
    config = await get_config(db, config_id)
    if config.status != GameConfigStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="only a draft config can be edited — create/use a draft first")

    symbols_by_id = {s.id: s for s in config.symbols}
    for update in updates.symbols:
        symbol = symbols_by_id.get(update.id)
        if symbol is None:
            raise HTTPException(status_code=404, detail=f"symbol {update.id} not found on this config")
        if len(update.reel_weights) != config.num_reels:
            raise HTTPException(
                status_code=400,
                detail=f"symbol {symbol.code}: reel_weights must have {config.num_reels} entries",
            )
        if any(w < 0 for w in update.reel_weights):
            raise HTTPException(status_code=400, detail=f"symbol {symbol.code}: reel_weights must be >= 0")
        if update.max_per_reel is not None and update.max_per_reel < 0:
            raise HTTPException(status_code=400, detail=f"symbol {symbol.code}: max_per_reel must be >= 0")
        symbol.reel_weights = list(update.reel_weights)
        symbol.paytable = dict(update.paytable)
        symbol.max_per_reel = update.max_per_reel
        symbol.image_ref = update.image_ref

    await db.commit()
    return await get_config(db, config_id)


async def run_and_record_simulation(
    db: AsyncSession, config_id: uuid.UUID, request: schemas.SimulateRequest
) -> SimulationRun:
    config = await get_config(db, config_id)
    rng = FastRNG(seed=request.seed)
    bet_amount = Decimal(request.bet_amount) if request.bet_amount is not None else None

    started_at = datetime.now(timezone.utc)
    report = simulate_game_config(config, num_spins=request.num_spins, rng=rng, bet_amount=bet_amount)
    completed_at = datetime.now(timezone.utc)

    run = SimulationRun(
        game_config_id=config.id,
        num_spins=request.num_spins,
        status="completed",
        params={"seed": request.seed, "bet_amount": request.bet_amount},
        results=report.to_dict(),
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def list_simulations(db: AsyncSession, config_id: uuid.UUID, limit: int = 20) -> list[SimulationRun]:
    await get_config(db, config_id)  # 404s if the config doesn't exist
    result = await db.execute(
        select(SimulationRun)
        .where(SimulationRun.game_config_id == config_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def publish_config(db: AsyncSession, config_id: uuid.UUID) -> tuple[GameConfig, uuid.UUID | None]:
    config = await get_config(db, config_id)
    if config.status != GameConfigStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="only a draft config can be published")

    archived_id: uuid.UUID | None = None
    active_result = await db.execute(
        select(GameConfig).where(
            GameConfig.game_id == config.game_id, GameConfig.status == GameConfigStatus.ACTIVE.value
        )
    )
    current_active = active_result.scalars().first()
    if current_active is not None:
        current_active.status = GameConfigStatus.ARCHIVED.value
        archived_id = current_active.id

    config.status = GameConfigStatus.ACTIVE.value
    await db.commit()
    return await get_config(db, config_id), archived_id
