from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_rng
from app.api.v1 import schemas
from app.api.v1.loaders import find_feature_config, load_active_config, load_session
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
    """Dev/test-only: runs a real spin (real bet, real reel draw, real RNG for
    everything else) but forces exactly as many trigger symbols onto the grid
    as the game's own hold_and_win config asks for, so the feature fires
    through its normal is_triggered()/execute() path rather than a bypassed
    bonus-buy. Costs one normal bet, not a 100x bonus-buy premium — this
    exists because the dev panel's own testing needs a way to reach Hold & Win
    on demand without fighting the demo's placeholder bonus-buy economics.

    Symbol and count come from the config (east-discovery: 3 collector_tiger,
    lucky-joker-3h3: 5 coin), and the positions are laid out one per reel
    before wrapping onto the next row — so a trigger symbol capped at
    max_per_reel=1 still lands legally as long as its count fits the grid."""
    session = await load_session(db, body.session_id)
    game_config = await load_active_config(db, session.game_id)
    hold_and_win_config = find_feature_config(game_config, "hold_and_win")

    force_positions = None
    if hold_and_win_config is not None:
        params = hold_and_win_config.params
        symbol_code = params.get("trigger_symbol_code", "collector_tiger")
        if params.get("trigger_mode") == "collector_and_coins":
            # Lucky Joker: the round wants a collector on its own reel plus a
            # trigger symbol on each of the others, so forcing N of one symbol
            # would never open it.
            collector_reel = int(params.get("collector_reel", game_config.num_reels // 2))
            collector_code = params.get("collector_symbol_code", "collector")
            force_positions = {
                collector_code: [(collector_reel, 0)],
                symbol_code: [
                    (reel, 0) for reel in range(game_config.num_reels) if reel != collector_reel
                ],
            }
        else:
            count = int(params.get("trigger_count", 3))
            count = min(count, game_config.num_reels * game_config.num_rows)
            force_positions = {
                symbol_code: [
                    (index % game_config.num_reels, index // game_config.num_reels)
                    for index in range(count)
                ]
            }

    return await run_spin(db, session, body.bet_amount, rng, force_positions=force_positions)
