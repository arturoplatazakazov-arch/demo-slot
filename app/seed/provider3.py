"""provider3 slots generated from provider2/ (see
provider2/make_game.py). One entry point for app/main.py so the startup list
does not grow by ten lines."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.gladiator_gig import get_or_seed_active_config as _seed_gladiator_gig
from app.seed.pyramid_pals import get_or_seed_active_config as _seed_pyramid_pals
from app.seed.piggy_bankers import get_or_seed_active_config as _seed_piggy_bankers
from app.seed.grit_and_gold import get_or_seed_active_config as _seed_grit_and_gold
from app.seed.barnyard_bonanza import get_or_seed_active_config as _seed_barnyard_bonanza
from app.seed.stone_age_stash import get_or_seed_active_config as _seed_stone_age_stash
from app.seed.tnt_tunnels import get_or_seed_active_config as _seed_tnt_tunnels
from app.seed.vault_runners import get_or_seed_active_config as _seed_vault_runners
from app.seed.big_top_bonkers import get_or_seed_active_config as _seed_big_top_bonkers
from app.seed.parrot_plunder import get_or_seed_active_config as _seed_parrot_plunder
from app.seed.skull_harbor import get_or_seed_active_config as _seed_skull_harbor
from app.seed.sugar_rush_dj import get_or_seed_active_config as _seed_sugar_rush_dj
from app.seed.pup_fishermen import get_or_seed_active_config as _seed_pup_fishermen
from app.seed.pharaoh_hippo import get_or_seed_active_config as _seed_pharaoh_hippo
from app.seed.bison_thunder import get_or_seed_active_config as _seed_bison_thunder
from app.seed.evolve_rush import get_or_seed_active_config as _seed_evolve_rush
from app.seed.cash_kingpin import get_or_seed_active_config as _seed_cash_kingpin

PROVIDER3_GAME_CODES = [
    "gladiator-gig",
    "pyramid-pals",
    "piggy-bankers",
    "grit-and-gold",
    "barnyard-bonanza",
    "stone-age-stash",
    "tnt-tunnels",
    "vault-runners",
    "big-top-bonkers",
    "parrot-plunder",
    "skull-harbor",
    "sugar-rush-dj",
    "pup-fishermen",
    "pharaoh-hippo",
    "bison-thunder",
    "evolve-rush",
    "cash-kingpin",
]


async def seed_provider3(db: AsyncSession) -> None:
    await _seed_gladiator_gig(db)
    await _seed_pyramid_pals(db)
    await _seed_piggy_bankers(db)
    await _seed_grit_and_gold(db)
    await _seed_barnyard_bonanza(db)
    await _seed_stone_age_stash(db)
    await _seed_tnt_tunnels(db)
    await _seed_vault_runners(db)
    await _seed_big_top_bonkers(db)
    await _seed_parrot_plunder(db)
    await _seed_skull_harbor(db)
    await _seed_sugar_rush_dj(db)
    await _seed_pup_fishermen(db)
    await _seed_pharaoh_hippo(db)
    await _seed_bison_thunder(db)
    await _seed_evolve_rush(db)
    await _seed_cash_kingpin(db)
