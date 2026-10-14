"""Provider 2 — the ten slots generated from provider2/ (see
provider2/make_game.py). One entry point for app/main.py so the startup list
does not grow by ten lines."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.rad_raiders import get_or_seed_active_config as _seed_rad_raiders
from app.seed.jade_paws import get_or_seed_active_config as _seed_jade_paws
from app.seed.ghoul_groove import get_or_seed_active_config as _seed_ghoul_groove
from app.seed.gummy_gold_rush import get_or_seed_active_config as _seed_gummy_gold_rush
from app.seed.whisker_noir import get_or_seed_active_config as _seed_whisker_noir
from app.seed.cogwork_skies import get_or_seed_active_config as _seed_cogwork_skies
from app.seed.bayou_bedlam import get_or_seed_active_config as _seed_bayou_bedlam
from app.seed.jaguar_eclipse import get_or_seed_active_config as _seed_jaguar_eclipse
from app.seed.trident_vs_titan import get_or_seed_active_config as _seed_trident_vs_titan

PROVIDER2_GAME_CODES = [
    "rad-raiders",
    "jade-paws",
    "ghoul-groove",
    "gummy-gold-rush",
    "whisker-noir",
    "cogwork-skies",
    "bayou-bedlam",
    "jaguar-eclipse",
    "trident-vs-titan",
]


async def seed_provider2(db: AsyncSession) -> None:
    await _seed_rad_raiders(db)
    await _seed_jade_paws(db)
    await _seed_ghoul_groove(db)
    await _seed_gummy_gold_rush(db)
    await _seed_whisker_noir(db)
    await _seed_cogwork_skies(db)
    await _seed_bayou_bedlam(db)
    await _seed_jaguar_eclipse(db)
    await _seed_trident_vs_titan(db)
