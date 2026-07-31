from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_rng
from app.api.v1 import schemas
from app.api.v1.loaders import load_session
from app.api.v1.spin_service import run_spin
from app.engine.rng import RNGProvider

router = APIRouter()


@router.post("/spin", response_model=schemas.SpinResponse)
async def spin(
    body: schemas.SpinRequest,
    db: AsyncSession = Depends(get_db),
    rng: RNGProvider = Depends(get_rng),
) -> schemas.SpinResponse:
    session = await load_session(db, body.session_id)
    return await run_spin(db, session, body.bet_amount, rng)


@router.post("/dev/force-hold-and-win", response_model=schemas.SpinResponse)
async def dev_force_hold_and_win(
    body: schemas.SpinRequest,
    db: AsyncSession = Depends(get_db),
    rng: RNGProvider = Depends(get_rng),
) -> schemas.SpinResponse:
    """Dev/test-only: runs a real spin (real bet, real reel draw, real RNG
    for everything else) but forces 3 collector_tiger onto the grid — one
    per reel, respecting its max_per_reel=1 cap — so Hold & Win triggers
    through its own normal is_triggered()/execute() path, not a bypassed
    bonus-buy. Costs one normal bet, not a 100x bonus-buy premium — this
    exists because the dev panel's own testing needs a way to reach Hold &
    Win on demand without fighting the demo's placeholder bonus-buy economics."""
    session = await load_session(db, body.session_id)
    return await run_spin(
        db, session, body.bet_amount, rng, force_positions={"collector_tiger": [(0, 0), (2, 0), (4, 0)]}
    )
