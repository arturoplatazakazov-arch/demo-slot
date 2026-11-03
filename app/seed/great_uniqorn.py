"""Seed data for the "great-uniqorn" demo game (front/great-uniqorn.html).

«Great Uniqorn» — единорог-президент в Овальном кабинете, сверстан по макету
Figma дизайнера (файл uniqorn-presedent). Механика — Amy's Fruit Farm
(app/seed/amys_fruit_farm.py): 5x3 line pay, 11 линий, скаттерные фриспины,
bonus buy. Одно отличие — вайлд: вместо расширения на барабан каждый упавший
WILD сам разыгрывает множитель, как в Multi Fruits Story
(app/features/multiplier_wild.py): остаётся простым WILD или превращается в
x2/x3/x5/x7/x9 и умножает свою линию; несколько вайлдов в одной линии
перемножаются. Набор множителей задан артом — у дизайнера ровно пять
символов x2/x3/x5/x7/x9 плюс простой WILD.

Коды символов и row-major ориентация сетки — контракт с фронтом
(SYMBOL_CODES в front/js/great-uniqorn/slot.js), не переименовывать.

Числа — от app/seed/uniqorn_scandal.py (та же механика Amy's), но два места
перетюнены под множитель:
- вес вайлда поднят с 93 до 279: у родителя он был занижен ИМЕННО из-за
  расширения (один вайлд закрывал до трёх ячеек), без расширения 0.9% дро
  почти не работал бы как линейный символ. Добавка снята с низкого тира, сумма
  10400 и ровно 7% у скаттера сохранены.
- пейтейблы урезаны против родительских под средний множитель вайлда
  (~2.4x на каждый вайлд в линии) — см. замер у _LOW_TIER_PAYS.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "great-uniqorn"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Единорог-президент: WILD превращается в множитель до x9, фриспины за бургеры"
CATALOG_COVER_PATH = "img/great-uniqorn/img/cover.jpg"
CATALOG_PLAY_URL = "great-uniqorn.html"

# 3 rows x 5 reels, тот же набор из 11 линий, что у Amy's / Uniqorn Scandal.
PAYLINES: list[list[int]] = [
    [1, 1, 1, 1, 1],
    [0, 0, 0, 0, 0],
    [2, 2, 2, 2, 2],
    [0, 1, 2, 1, 0],
    [2, 1, 0, 1, 2],
    [1, 0, 1, 0, 1],
    [1, 2, 1, 2, 1],
    [0, 1, 0, 1, 0],
    [2, 1, 2, 1, 2],
    [0, 2, 0, 2, 0],
    [2, 0, 2, 0, 2],
]

# Измерено scripts/great_uniqorn_rtp.py (симулятор app.simulator прямо по
# build_game_config, без базы), 150k спинов на сидах 7 и 21: RTP 0.957 / 0.961
# (база ~0.41, фриспины ~0.55), хит-рейт 34%, максимум ~860x ставки.
# Перезапускать после правки любого веса, выплаты или веса множителя.
_LOW_TIER_PAYS = {"3": 2, "4": 5, "5": 10}
_HIGH_TIER_PAYS = {"3": 8, "4": 20, "5": 40}
# Линия из одних вайлдов перемножает ВСЕ их множители, поэтому выплата
# вайлда лишь ненамного выше дорогого тира.
_WILD_PAYS = {"3": 10, "4": 30, "5": 75}
_SCATTER_PAYS = {"3": 2, "4": 10, "5": 50}

# code -> (symbol_type, tier, reel_weight (same on all 5 reels), paytable, max_per_reel)
# Скаттер = ровно 7% всех дро (как у всей линейки Amy's), total 10400.
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 728, _SCATTER_PAYS, 1),
    # Не больше одного вайлда на барабан — та же продуктовая конвенция, что у
    # родителя; заодно ограничивает худший случай перемножения в линии.
    ("wild", SymbolType.WILD.value, "high", 279, _WILD_PAYS, 1),
    ("jet", SymbolType.REGULAR.value, "high", 744, _HIGH_TIER_PAYS, None),
    ("docs", SymbolType.REGULAR.value, "high", 558, _HIGH_TIER_PAYS, None),
    ("hair", SymbolType.REGULAR.value, "high", 465, _HIGH_TIER_PAYS, None),
    ("a", SymbolType.REGULAR.value, "low", 2139, _LOW_TIER_PAYS, None),
    ("k", SymbolType.REGULAR.value, "low", 1953, _LOW_TIER_PAYS, None),
    ("q", SymbolType.REGULAR.value, "low", 1860, _LOW_TIER_PAYS, None),
    ("j", SymbolType.REGULAR.value, "low", 1674, _LOW_TIER_PAYS, None),
]

# Shown in the in-game paytable (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    "scatter": "Burger",
    "wild": "Great Uniqorn",
    "jet": "Air Force Uni",
    "docs": "Executive Order",
    "hair": "The Hair",
    "a": "A", "k": "K", "q": "Q", "j": "J",
}

# Value -> weight; "1" — вайлд остался простым WILD. Набор значений
# зафиксирован артом (x2/x3/x5/x7/x9), тюнить можно только веса. Половина
# вайлдов остаётся простой, чтобы превращение было событием, а не нормой.
WILD_MULTIPLIER_WEIGHTS = {"1": 50, "2": 20, "3": 13, "5": 9, "7": 5, "9": 3}

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Great Uniqorn",
        catalog_badge=CATALOG_BADGE, catalog_description=CATALOG_DESCRIPTION,
        catalog_cover_path=CATALOG_COVER_PATH, catalog_play_url=CATALOG_PLAY_URL,
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
        notes="Seed config — Amy's mechanic with multiplier wilds; RTP measured by simulator.",
    )

    for order, (code, symbol_type, tier, weight, pays, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=_SYMBOL_NAMES.get(code, code.title()),
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=pays,
            max_per_reel=max_per_reel,
            display_order=order,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.FREE_SPINS.value,
        enabled=True,
        params={
            "trigger_symbol_code": "scatter",
            "trigger_count": 3,
            "spins_awarded": 10,  # fallback only; the table below drives real awards
            "spins_awarded_by_count": {"3": 10, "4": 15, "5": 20},
            "retrigger_enabled": True,
            "win_multiplier": 1,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
        params={
            "products": [
                {"buy_id": "free_spins_buy", "cost_multiplier": 100, "target_feature_id": "free_spins"},
            ],
        },
        display_order=1,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.MULTIPLIER_WILD.value,
        enabled=True,
        params={
            "wild_symbol_code": "wild",
            "variant_weights": WILD_MULTIPLIER_WEIGHTS,
        },
        display_order=2,
    )

    return game, config


_CATALOG = CatalogMeta(
    badge=CATALOG_BADGE,
    description=CATALOG_DESCRIPTION,
    cover_path=CATALOG_COVER_PATH,
    play_url=CATALOG_PLAY_URL,
)


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Идемпотентный сид этой игры — вся логика в app/seed/_runner.py."""
    return await get_or_seed(
        db, game_code=GAME_CODE, build_game_config=build_game_config, catalog=_CATALOG
    )
