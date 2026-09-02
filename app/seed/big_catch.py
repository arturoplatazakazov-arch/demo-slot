"""Seed data for the "big-catch" demo game (front/big-catch.html under this repo).

Механика — Amy's Fruit Farm (app/seed/amys_fruit_farm.py): 5x3 line pay,
11 линий, скаттерные фриспины, bonus buy. РАСШИРЯЮЩЕГОСЯ ВАЙЛДА, в отличие от
родителя, тут нет (продукт: «здесь нет такой механики, только маленький
вайлд») — вайлд просто подставляется в линию. Числа взяты
с app/seed/uniqorn_scandal.py (та же механика на PNG-подаче) с одной
поправкой: у этой игры ЧЕТЫРЕ дорогих символа вместо трёх — в макете четыре
рыбы на медальонах и четыре рыбацкие вещи без медальона. Суммарный вес
высокого тира тот же (1767), просто разбит на четыре части вместо трёх, так
что общий вес барабана остался 10400, скаттер — ровно 7% дро, а низкий тир
не тронут вовсе. То есть частота и стоимость тиров те же, что у обкатанной
игры, и подмена художественная, а не математическая.

Коды символов и row-major ориентация сетки — фиксированный контракт с
фронтом (SYMBOL_CODES в front/js/big-catch/slot.js), не переименовывать.
Пейтейблы, веса и раскладка линий — плейсхолдерная математика (не под RTP),
ровно как в app/seed/amys_fruit_farm.py.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "big-catch"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Рыбалка на большой улов: расширяющийся Wild и фриспины на подводном дне"
CATALOG_COVER_PATH = "img/big-catch/img/cover.jpg"
CATALOG_PLAY_URL = "big-catch.html"

# 3 rows x 5 reels. 11 линий — тот же набор, что у Amy's Fruit Farm; форма
# линии рисуется клиентом SVG-полилинией по выигравшим ячейкам, но набор
# оставлен идентичным, чтобы математика совпадала.
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
# бонус). Total 10400 — как у uniqorn-scandal.
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 728, _SCATTER_PAYS, 1),
    # ВНИМАНИЕ: 93 достался от родителя, где вес занижали специально —
    # expanding_wild разворачивал выпавший вайлд в целый барабан, и его вклад
    # в RTP был куда выше сырого веса. Расширения тут больше нет, значит и
    # обоснование для такого низкого веса отпало: вайлд выпадает меньше чем в
    # 1% дро и как линейный символ почти не работает. Не трогаю здесь, потому
    # что любое изменение веса ломает либо сумму 10400, либо ровно 7% у
    # скаттера — это решение продукта и симулятора шестого этапа, а не
    # побочный эффект снятия фичи.
    ("wild", SymbolType.WILD.value, "high", 93, _WILD_PAYS, 1),
    # Высокий тир: 620 + 465 + 372 + 310 = 1767 — та же сумма, что у трёх
    # дорогих символов родителя (744 + 558 + 465), просто на четверых.
    ("marlin", SymbolType.REGULAR.value, "high", 620, _HIGH_TIER_PAYS, None),
    ("pike", SymbolType.REGULAR.value, "high", 465, _HIGH_TIER_PAYS, None),
    ("bass", SymbolType.REGULAR.value, "high", 372, _HIGH_TIER_PAYS, None),
    ("puffer", SymbolType.REGULAR.value, "high", 310, _HIGH_TIER_PAYS, None),
    # Низкий тир — веса a/k/q/j родителя один в один.
    ("tacklebox", SymbolType.REGULAR.value, "low", 2232, _LOW_TIER_PAYS, None),
    ("hat", SymbolType.REGULAR.value, "low", 2046, _LOW_TIER_PAYS, None),
    ("lure", SymbolType.REGULAR.value, "low", 1860, _LOW_TIER_PAYS, None),
    ("bobber", SymbolType.REGULAR.value, "low", 1674, _LOW_TIER_PAYS, None),
]

# Shown in the in-game paytable (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    "scatter": "Fishing Spot",
    "wild": "Big Catch",
    "marlin": "Marlin",
    "pike": "Pike",
    "bass": "Bass",
    "puffer": "Pufferfish",
    "tacklebox": "Tackle Box",
    "hat": "Fisherman Hat",
    "lure": "Lure",
    "bobber": "Bobber",
}

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Big Catch",
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
            name=_SYMBOL_NAMES.get(code, code.title()),
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=pays,
            max_per_reel=max_per_reel,
            display_order=order,
            # Descriptive only — движок на это поле не смотрит.
            wild_subtype=WildSubtype.STANDARD.value if code == "wild" else None,
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
    # Расширяющегося вайлда у этой игры нет. Строка всё же заводится, но
    # ВЫКЛЮЧЕННОЙ, а не выкидывается совсем: реконсиляция сида умеет
    # создавать и обновлять feature_configs, но не удалять (см. docstring в
    # app/seed/_runner.py), и на уже засеянной базе — например на локальной
    # дев-БД или на проде — просто убранная из файла фича осталась бы
    # включённой навсегда. С enabled=False реестр фич её пропускает
    # (app/features/registry.py), и свежая база с уже засеянной сходятся.
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.EXPANDING_WILD.value,
        enabled=False,
        params={},
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
