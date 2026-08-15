from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.admin import api_admin_router
from app.api.ratelimit import rate_limit_middleware
from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.seed.amys_fruit_farm import get_or_seed_active_config as get_or_seed_amys_fruit_farm
from app.seed.dirty_money_mafia import get_or_seed_active_config as get_or_seed_dirty_money_mafia
from app.seed.east_discovery import get_or_seed_active_config as get_or_seed_east_discovery
from app.seed.golden_caravan import get_or_seed_active_config as get_or_seed_golden_caravan
from app.seed.lucky_joker_3h3 import get_or_seed_active_config as get_or_seed_lucky_joker_3h3
from app.seed.mr_president_unicorn import get_or_seed_active_config as get_or_seed_mr_president_unicorn
from app.seed.multi_fruits_story import get_or_seed_active_config as get_or_seed_multi_fruits_story
from app.seed.neon_reels import get_or_seed_active_config as get_or_seed_neon_reels
from app.seed.party_of_goods import get_or_seed_active_config as get_or_seed_party_of_goods
from app.seed.sugar_galaxy import get_or_seed_active_config as get_or_seed_sugar_galaxy
from app.seed.uniqorn_bad_santa import get_or_seed_active_config as get_or_seed_uniqorn_bad_santa
from app.seed.uniqorn_back_to_fabulous import (
    get_or_seed_active_config as get_or_seed_uniqorn_back_to_fabulous,
)
from app.seed.wild_western_story import get_or_seed_active_config as get_or_seed_wild_western_story

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: make sure the demo games the frontend expects
    # ("amys-fruit-farm", "dirty-money-mafia", "east-discovery",
    # "golden-caravan", "lucky-joker-3h3", "mr-president-unicorn",
    # "multi-fruits-story", "neon-reels",
    # "party-of-goods", "sugar-galaxy", "uniqorn-back-to-fabulous", "uniqorn-bad-santa",
    # "wild-western-story") exist on boot. A real deployment manages configs
    # through the admin API, not an app-startup side effect.
    async with AsyncSessionLocal() as db:
        await get_or_seed_amys_fruit_farm(db)
        await get_or_seed_dirty_money_mafia(db)
        await get_or_seed_east_discovery(db)
        await get_or_seed_golden_caravan(db)
        await get_or_seed_lucky_joker_3h3(db)
        await get_or_seed_mr_president_unicorn(db)
        await get_or_seed_multi_fruits_story(db)
        await get_or_seed_neon_reels(db)
        await get_or_seed_party_of_goods(db)
        await get_or_seed_sugar_galaxy(db)
        await get_or_seed_uniqorn_bad_santa(db)
        await get_or_seed_uniqorn_back_to_fabulous(db)
        await get_or_seed_wild_western_story(db)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

# Rate limiter is added before CORS so CORS stays the OUTERMOST middleware:
# that way even a 429 response carries CORS headers and the browser can read it.
app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
    allow_origin_regex=settings.cors_allow_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)
app.include_router(api_admin_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
