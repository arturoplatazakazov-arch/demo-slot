from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_rng
from app.api.v1 import schemas
from app.api.v1.loaders import load_session
from app.api.v1.spin_service import run_feature_buy
from app.engine.rng import RNGProvider

router = APIRouter()


@router.post("/feature/buy", response_model=schemas.SpinResponse)
async def buy_feature(
    body: schemas.FeatureBuyRequest,
    db: AsyncSession = Depends(get_db),
    rng: RNGProvider = Depends(get_rng),
) -> schemas.SpinResponse:
    session = await load_session(db, body.session_id)
    return await run_feature_buy(db, session, body.feature_id, body.bet_amount, rng)


@router.post("/gamble")
async def gamble_stub() -> None:
    """TZ §8.1 lists this endpoint; nothing in front/ calls it yet (no UI
    built for it at this stage), so it's a documented stub rather than a
    real implementation — avoids blocking the rest of stage 5 on a request
    shape (stake, guess, mode) that hasn't been confirmed. `GambleFeature`
    itself (app/features/gamble.py) is already implemented and tested; only
    the HTTP wiring is missing."""
    raise HTTPException(status_code=501, detail="gamble endpoint not implemented yet")
