"""Seed data for the "caesars-fortune" demo game
(front/caesars-fortune.html under this repo).

Римский слот по макету дизайнера («на верстку», сент. 2026). Механика —
Wild Western Story (app/seed/wild_western_story.py): 5x3 line pay, 11 линий,
РАСШИРЯЮЩИЙСЯ вайлд, скаттерные фриспины, bonus buy x100.

Числа взяты у app/seed/gangsta_city.py — той же механики, но уже с ЧЕТЫРЬМЯ
дорогими символами, как здесь (в макете четыре римских портрета в цветных
рамках). То есть вес высокого тира родителя (744 + 558 + 465 = 1767) уже
разбит там на 620 + 465 + 372 + 310: общий вес барабана остаётся 10400, а
скаттер — ровно 7% всех дро. Значит частота скаттера, длина бонуса и доля
дорогих символов совпадают с обкатанной игрой, а не подобраны заново на глаз.

Коды символов и row-major ориентация сетки — фиксированный контракт с фронтом
(SYMBOL_CODES в front/js/caesars-fortune/slot.js), не переименовывать.
Пейтейблы, веса и раскладка линий — плейсхолдерная математика (не под RTP),
ровно как у родителя: RTP по этой игре скажет симулятор шестого этапа.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "caesars-fortune"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Золото Рима: Wild на весь барабан и фриспины за Колизей"
CATALOG_COVER_PATH = "img/caesars-fortune/img/cover.jpg"
CATALOG_PLAY_URL = "caesars-fortune.html"

# 3 rows x 5 reels. 11 линий — тот же набор, что у Wild Western Story. Форму
# линии клиент рисует SVG-полилинией по выигравшим ячейкам, но набор оставлен
# идентичным, чтобы математика совпадала с родителем.
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

_LOW_TIER_PAYS = {"3": 2, "4": 5, "5": 10}
_HIGH_TIER_PAYS = {"3": 10, "4": 25, "5": 50}
_WILD_PAYS = {"3": 20, "4": 60, "5": 150}
_SCATTER_PAYS = {"3": 2, "4": 10, "5": 50}

# code -> (symbol_type, tier, reel_weight (same on all 5 reels), paytable, max_per_reel)
# Скаттер = ровно 7% всех дро (продукт, авг 2026; 10% давал бесконечный
# бонус). Триггер ~раз в 18 спинов, ветвление ретриггеров 0.58 — конечный
# бонус длиной ~x2.4.
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 728, _SCATTER_PAYS, 1),
    # Вес занижен намеренно: expanding_wild разворачивает выпавший вайлд в
    # целый барабан (в половине случаев — см. expand_chance ниже), поэтому его
    # реальный вклад в RTP много больше сырого веса. Cap 1/барабан — соглашение
    # продукта: не больше одного вайлда, расширенного или нет, на барабан.
    ("wild", SymbolType.WILD.value, "high", 93, _WILD_PAYS, 1),
    # Четыре портрета из макета: центурион в красной рамке, патриций в
    # фиолетовой, императрица в зелёной, цезарь в синей. Веса — доли высокого
    # тира родителя (см. шапку файла), цезарь самый редкий.
    ("centurion", SymbolType.REGULAR.value, "high", 620, _HIGH_TIER_PAYS, None),
    ("patrician", SymbolType.REGULAR.value, "high", 465, _HIGH_TIER_PAYS, None),
    ("empress", SymbolType.REGULAR.value, "high", 372, _HIGH_TIER_PAYS, None),
    ("caesar", SymbolType.REGULAR.value, "high", 310, _HIGH_TIER_PAYS, None),
    # Младшие — римский реквизит вместо букв A/K/Q/J: меч, шлем, амфора, венок.
    ("sword", SymbolType.REGULAR.value, "low", 2232, _LOW_TIER_PAYS, None),
    ("helmet", SymbolType.REGULAR.value, "low", 2046, _LOW_TIER_PAYS, None),
    ("amphora", SymbolType.REGULAR.value, "low", 1860, _LOW_TIER_PAYS, None),
    ("wreath", SymbolType.REGULAR.value, "low", 1674, _LOW_TIER_PAYS, None),
]

# Показывается в игровом пейтейбле (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    "scatter": "Colosseum",
    "wild": "Caesar's Wild",
    "centurion": "Centurion",
    "patrician": "Patrician",
    "empress": "Empress",
    "caesar": "Caesar",
    "sword": "Gladius",
    "helmet": "Helmet",
    "amphora": "Amphora",
    "wreath": "Laurel Wreath",
}

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Caesar's Fortune",
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
        notes="Seed config — placeholder math, not RTP-validated (stage 6 pending).",
    )

    for order, (code, symbol_type, tier, weight, pays, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=_SYMBOL_NAMES.get(code, code.replace("_", " ").title()),
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=pays,
            max_per_reel=max_per_reel,
            display_order=order,
            # Описательное поле: expanding_wild смотрит на свой
            # trigger_symbol_code, а не сюда.
            wild_subtype=WildSubtype.EXPANDING.value if code == "wild" else None,
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
            "spins_awarded": 10,  # запасное значение; реальные выдачи — в таблице ниже
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
        feature_type=FeatureType.EXPANDING_WILD.value,
        enabled=True,
        params={
            "trigger_symbol_code": "wild",
            "walk_enabled": True,
            "walk_direction": "right",
            "expand_chance": 0.5,
            "walk_chance": 0.5,
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
