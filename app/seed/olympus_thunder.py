"""Seed data for "olympus-thunder" (front/olympus-thunder.html) — GDD-04
"Olympus Thunder" v0.10: a 6x5 scatter-pays tumble slot with multiplier
orbs, free spins with an accumulating TOTAL MULTIPLIER, a jackpot wheel
triggered by eagles and a three-SKU bonus buy.

The mechanic is its own engine (app/engine/scatter_tumble*.py) driven by the
single "scatter_tumble" FeatureConfig row below — every number of the GDD
lives in its params. The Symbol rows only describe the symbols for the
paytable / session start; their reel_weights are informational (base-mode
weights), the engine draws from params["weights"][mode].

Orbs are stored on the grid as "orb_<value>" (the value is rolled when the
orb lands), so there is one Symbol row per value for the client's paytable.

Math: the GDD's §4.1/§6.1 tables as written, with the free-spins orb weight
retuned for the 25.09.2026 TOTAL MULTIPLIER rule (start x1, grows and applies
only on winning series with an orb) — see scripts/olympus_thunder_rtp.py for
the simulation the numbers in `notes` come from.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Symbol
from app.models.enums import GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "olympus-thunder"
GAME_NAME = "Olympus Thunder"
CATALOG_BADGE = "Tumble"
CATALOG_DESCRIPTION = (
    "Гроза над Олимпом: выплаты за 8+ символов где угодно, каскады, сферы-множители до x100, "
    "фриспины с растущим множителем, колесо джекпотов и Buy Bonus"
)
CATALOG_COVER_PATH = "img/olympus-thunder/cover.jpg"
CATALOG_PLAY_URL = "olympus-thunder.html"

NUM_REELS = 6
NUM_ROWS = 5

# GDD §4.1 — x total bet for 8-9 / 10-11 / 12+ anywhere.
PAYTABLE = {
    "helmet": {"8": 10, "10": 25, "12": 50},
    "lyre": {"8": 2.5, "10": 10, "12": 25},
    "amphora": {"8": 2, "10": 5, "12": 15},
    "wreath": {"8": 1.5, "10": 2, "12": 12},
    "ruby": {"8": 1, "10": 1.5, "12": 10},
    "amethyst": {"8": 0.8, "10": 1.2, "12": 8},
    "emerald": {"8": 0.5, "10": 1, "12": 5},
    "sapphire": {"8": 0.4, "10": 0.9, "12": 4},
    "citrine": {"8": 0.25, "10": 0.75, "12": 2},
}

_BASE_WEIGHTS = {
    "helmet": 4, "lyre": 5, "amphora": 6, "wreath": 7,
    "ruby": 9, "amethyst": 10, "emerald": 11, "sapphire": 12, "citrine": 13,
    "scatter": 1.5, "orb": 0.6, "eagle": 0.5,
}
# FS orb weight 3.9 -> 4.6: the GDD lever for the 25.09 TOTAL MULTIPLIER rule (92.1% -> ~96%).
_FS_WEIGHTS = {**_BASE_WEIGHTS, "sapphire": 14, "citrine": 17, "scatter": 1.1, "orb": 4.6}
_SUPER_WEIGHTS = {**_FS_WEIGHTS, "orb": 7.0}

# GDD §6.1 — (value, weight of 100); mean 4.8x.
ORB_VALUES = [
    [2, 30], [3, 22], [4, 14], [5, 12], [6, 7], [8, 5], [10, 4],
    [12, 2.5], [15, 1.5], [20, 1], [25, 0.5], [50, 0.35], [100, 0.15],
]

# GDD §8 — 12 visual sectors, clockwise; sector i is centred at 15 + 30*i
# degrees from 12 o'clock (a spoke sits at 12). The order is read off the
# painted front/img/olympus-thunder/wheel.png (green / blue / violet / red =
# mini / minor / major / grand), so the art, not this list, is the source.
WHEEL_SECTORS = [
    "mini", "minor", "mini", "major", "mini", "mini",
    "grand", "minor", "mini", "minor", "mini", "major",
]

def _pairs(weights: dict) -> list[list]:
    """Weight tables are stored as ordered [code, weight] pairs: Postgres JSONB
    re-sorts object keys, and the draw order must not depend on the DB."""
    return [[code, weight] for code, weight in weights.items()]


PARAMS = {
    "paytable": PAYTABLE,
    "weights": {"base": _pairs(_BASE_WEIGHTS), "fs": _pairs(_FS_WEIGHTS), "super": _pairs(_SUPER_WEIGHTS)},
    "orb_values": ORB_VALUES,
    "scatter_pays": {"4": 3, "5": 5, "6": 100},
    "free_spins": {"trigger_count": 4, "spins": 15, "retrigger_count": 3, "retrigger_spins": 5},
    "jackpot": {
        "trigger_count": 3,
        "prizes": {"mini": 20, "minor": 50, "major": 250, "grand": 1000},
        "natural_odds": [["mini", 60], ["minor", 28], ["major", 10], ["grand", 2]],
        "buy_odds": [["mini", 76], ["minor", 17.5], ["major", 5.5], ["grand", 1]],
        "sectors": WHEEL_SECTORS,
    },
    "bonus_buy": {
        # Jurisdiction switch (GDD §9.1 / §13: buy_bonus_enabled + per-SKU).
        "enabled": True,
        # Prices re-calibrated on the 25.09 TOTAL MULTIPLIER rule (10M-spin sim,
        # scripts/olympus_thunder_rtp.py): FS 113.1x / Super 135.2x / wheel 47.8x
        # average return -> ~95.5% RTP per SKU.
        "products": [
            {"buy_id": "free_spins", "kind": "free_spins", "cost_multiplier": 118, "enabled": True},
            {"buy_id": "super_free_spins", "kind": "super_free_spins", "cost_multiplier": 142, "enabled": True},
            {"buy_id": "jackpot_chance", "kind": "jackpot", "cost_multiplier": 50, "enabled": True},
        ],
    },
    "max_win_multiplier": 10000,
}

_NAMES = {
    "helmet": "Шлем воина", "lyre": "Лира", "amphora": "Амфора", "wreath": "Лавровый венок",
    "ruby": "Красный самоцвет", "amethyst": "Фиолетовый самоцвет", "emerald": "Зелёный самоцвет",
    "sapphire": "Синий самоцвет", "citrine": "Жёлтый самоцвет",
    "scatter": "Кольцо молний", "eagle": "Орёл Зевса",
}

BET_STEPS = [2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]


# Design variants of the same game (same math, own page + art direction),
# shown together in the catalog's «Olympus Thunder» subsection:
# code -> (name, badge, description, cover, play url).
VARIANTS = {
    GAME_CODE: (GAME_NAME, CATALOG_BADGE, CATALOG_DESCRIPTION, CATALOG_COVER_PATH, CATALOG_PLAY_URL),
    "olympus-thunder-v2": (
        "Olympus Thunder · Ascension", "Вариант 2",
        "Тот же слот в стиле рисованного графического романа: храмы над облаками, "
        "мраморная рама с колоннами, Зевс справа, лестница джекпотов слева.",
        "img/olympus-thunder/cover_v2.jpg", "olympus-thunder-v2.html",
    ),
    "olympus-thunder-v3": (
        "Olympus Thunder · Noir", "Вариант 3",
        "Тот же слот в стиле чернофигурной вазописи: терракота и чёрный лак, "
        "керамическая рама с меандром, огромный множитель — главный герой экрана.",
        "img/olympus-thunder/cover_v3.jpg", "olympus-thunder-v3.html",
    ),
}


def build_game_config(code: str = GAME_CODE) -> tuple[Game, GameConfig]:
    name, badge, description, cover, play_url = VARIANTS[code]
    game = Game(
        code=code, name=name,
        catalog_badge=badge, catalog_description=description,
        catalog_cover_path=cover, catalog_play_url=play_url,
    )
    config = GameConfig(
        game=game,
        version=1,
        status=GameConfigStatus.ACTIVE.value,
        num_reels=NUM_REELS,
        num_rows=NUM_ROWS,
        target_rtp=0.96,
        min_bet=BET_STEPS[0],
        max_bet=BET_STEPS[-1],
        bet_step=BET_STEPS[0],
        bet_steps=BET_STEPS,
        notes="GDD-04 v0.10 math, FS orb weight 4.6: sim 10M spins RTP 95.8%, hit 26.2%, FS 1/295, avg bonus 113x, wheel 1/838; buys 118x/142x/50x ~95.5%.",
    )

    order = 0
    for code, tiers in PAYTABLE.items():
        Symbol(
            game_config=config, code=code, name=_NAMES[code],
            symbol_type=SymbolType.REGULAR.value,
            tier="high" if code in ("helmet", "lyre", "amphora", "wreath") else "low",
            reel_weights=[_BASE_WEIGHTS[code]] * NUM_REELS,
            paytable=tiers, display_order=order,
        )
        order += 1
    for code, symbol_type in (("scatter", SymbolType.SCATTER.value), ("eagle", SymbolType.BONUS.value)):
        Symbol(
            game_config=config, code=code, name=_NAMES[code], symbol_type=symbol_type, tier="high",
            reel_weights=[_BASE_WEIGHTS[code]] * NUM_REELS, paytable={}, display_order=order,
        )
        order += 1
    total_orb_weight = sum(w for _, w in ORB_VALUES)
    for value, weight in ORB_VALUES:
        Symbol(
            game_config=config, code=f"orb_{value}", name=f"Сфера x{value}",
            symbol_type=SymbolType.BONUS.value, tier="high",
            reel_weights=[round(_BASE_WEIGHTS["orb"] * weight / total_orb_weight, 4)] * NUM_REELS,
            paytable={}, multiplier_value=value, display_order=order,
        )
        order += 1

    FeatureConfig(
        game_config=config,
        feature_type="scatter_tumble",
        enabled=True,
        params=PARAMS,
        display_order=0,
    )
    return game, config


async def _seed(db: AsyncSession, code: str) -> GameConfig:
    name, badge, description, cover, play_url = VARIANTS[code]
    catalog = CatalogMeta(
        badge=badge, description=description, cover_path=cover, play_url=play_url,
        force=True, display_name=name,
    )
    return await get_or_seed(
        db, game_code=code, build_game_config=lambda: build_game_config(code), catalog=catalog
    )


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Идемпотентный сид этой игры и её дизайн-вариантов — логика в app/seed/_runner.py."""
    config = await _seed(db, GAME_CODE)
    for code in VARIANTS:
        if code != GAME_CODE:
            await _seed(db, code)
    return config
