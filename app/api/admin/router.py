import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import schemas, service
from app.api.deps import get_db
from app.models.config import GameConfig
from app.models.simulation import SimulationRun

router = APIRouter()


def _config_summary_out(config: GameConfig) -> schemas.ConfigSummaryOut:
    return schemas.ConfigSummaryOut(
        id=config.id, game_id=config.game_id, version=config.version, status=config.status,
        target_rtp=float(config.target_rtp), notes=config.notes, created_at=config.created_at,
    )


def _config_detail_out(config: GameConfig) -> schemas.ConfigDetailOut:
    return schemas.ConfigDetailOut(
        **_config_summary_out(config).model_dump(),
        num_reels=config.num_reels,
        num_rows=config.num_rows,
        symbols=[
            schemas.SymbolOut(
                id=s.id, code=s.code, name=s.name, symbol_type=s.symbol_type,
                reel_weights=list(s.reel_weights), paytable=dict(s.paytable),
                max_per_reel=s.max_per_reel, tier=s.tier, image_ref=s.image_ref,
            )
            for s in config.symbols
        ],
    )


def _simulation_report_out(run: SimulationRun, target_rtp: float) -> schemas.SimulationReportOut:
    # run.results is SimulationReport.to_dict() — already includes num_spins
    # among the other report fields, so it alone covers everything besides
    # the run's own id/config_id/target_rtp/created_at.
    return schemas.SimulationReportOut(
        id=run.id, config_id=run.game_config_id,
        target_rtp=target_rtp, created_at=run.created_at, **run.results,
    )


@router.get("/games/{game_code}/configs", response_model=list[schemas.ConfigSummaryOut])
async def list_configs(game_code: str, db: AsyncSession = Depends(get_db)) -> list[schemas.ConfigSummaryOut]:
    configs = await service.list_configs(db, game_code)
    return [_config_summary_out(c) for c in configs]


@router.post("/games/{game_code}/draft", response_model=schemas.ConfigDetailOut)
async def create_draft(game_code: str, db: AsyncSession = Depends(get_db)) -> schemas.ConfigDetailOut:
    draft = await service.get_or_create_draft(db, game_code)
    return _config_detail_out(draft)


@router.get("/configs/{config_id}", response_model=schemas.ConfigDetailOut)
async def get_config(config_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> schemas.ConfigDetailOut:
    config = await service.get_config(db, config_id)
    return _config_detail_out(config)


@router.put("/configs/{config_id}/symbols", response_model=schemas.ConfigDetailOut)
async def update_symbols(
    config_id: uuid.UUID, body: schemas.UpdateSymbolsRequest, db: AsyncSession = Depends(get_db)
) -> schemas.ConfigDetailOut:
    config = await service.update_symbols(db, config_id, body)
    return _config_detail_out(config)


@router.post("/configs/{config_id}/simulate", response_model=schemas.SimulationReportOut)
async def simulate(
    config_id: uuid.UUID, body: schemas.SimulateRequest, db: AsyncSession = Depends(get_db)
) -> schemas.SimulationReportOut:
    config = await service.get_config(db, config_id)
    run = await service.run_and_record_simulation(db, config_id, body)
    return _simulation_report_out(run, float(config.target_rtp))


@router.get("/configs/{config_id}/simulations", response_model=list[schemas.SimulationReportOut])
async def simulation_history(
    config_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[schemas.SimulationReportOut]:
    config = await service.get_config(db, config_id)
    runs = await service.list_simulations(db, config_id)
    return [_simulation_report_out(run, float(config.target_rtp)) for run in runs]


@router.post("/configs/{config_id}/publish", response_model=schemas.PublishResponse)
async def publish(config_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> schemas.PublishResponse:
    config, archived_id = await service.publish_config(db, config_id)
    return schemas.PublishResponse(config_id=config.id, status=config.status, archived_config_id=archived_id)
