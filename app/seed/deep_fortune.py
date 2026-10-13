"""Seed data for the "deep-fortune" demo game
(front/deep-fortune.html under this repo).

Механика — Amy's Fruit Farm (app/seed/amys_fruit_farm.py): 5x3 line pay,
11 линий, расширяющийся вайлд, скаттерные фриспины, bonus buy. Конкретные
числа склонированы с app/seed/mr_president_unicorn.py (та же механика, уже
поданная на PNG-арте вместо спайна, через app/seed/uniqorn_scandal.py) БАЙТ-В-БАЙТ — те же веса барабанов,
пейтейблы и параметры фич, свои тут только коды символов. Идентичные числа
означают, что подмена фронта заведомо чисто художественная; перетюнить здесь
можно будет, когда симулятор шестого этапа скажет что-то про эту игру
отдельно.

Коды символов и row-major ориентация сетки — фиксированный контракт с уже
собранным фронтом (SYMBOL_CODES в front/js/deep-fortune/slot.js), не
переименовывать. Пейтейблы, веса и раскладка линий — плейсхолдерная
математика (индустриально-типовые формы, не под RTP), ровно как в
app/seed/amys_fruit_farm.py.

Механика — line-pay + скаттерные фриспины + расширяющийся вайлд:
- `wild` (Посейдон) расширяется и шагает вероятностно, параметры те же,
  что у app/seed/east_discovery.py.
- Символов типа BONUS тут нет — ни hold_and_win, ни coin_multiplier.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "deep-fortune"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Затонувший город Посейдона: расширяющийся Wild и фриспины за жемчужины"
CATALOG_COVER_PATH = "img/deep-fortune/img/cover.jpg"
CATALOG_PLAY_URL = "deep-fortune.html"

# 3 rows x 5 reels.
# 11 линий — тот же набор, что у Amy's Fruit Farm / Mr. President. Этой игре
# форма линии не нужна для арта (клиент рисует её SVG-полилинией прямо по
# выигравшим ячейкам, см. showWinLine), но набор оставлен идентичным, чтобы
# математика совпадала.
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
# бонус: ретриггер порождал в среднем 1.38 новых фриспинов на спин).
# Вес скаттера = 7 x исходная сумма остальных, остальные умножены на 93 —
# их относительные частоты не изменились, total 10400. Триггер ~раз в 18
# спинов, ветвление ретриггеров 0.58 (конечный бонус, ~x2.4 длина).
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 728, _SCATTER_PAYS, 1),
    # Weight kept low: expanding_wild turns one drawn wild into up to a full
    # 3-symbol reel (50% of the time — see expand_chance below), so its
    # effective frequency/impact on RTP is much higher than the raw weight
    # suggests. Capped at 1/reel (product convention, same as East
    # Discovery): at most one wild — expanded or not — per reel.
    ("wild", SymbolType.WILD.value, "high", 93, _WILD_PAYS, 1),
    # Веса — те же, что у wife / heart / beer в uniqorn-scandal.
    ("siren", SymbolType.REGULAR.value, "high", 744, _HIGH_TIER_PAYS, None),
    ("nymph", SymbolType.REGULAR.value, "high", 558, _HIGH_TIER_PAYS, None),
    ("shark", SymbolType.REGULAR.value, "high", 465, _HIGH_TIER_PAYS, None),
    ("a", SymbolType.REGULAR.value, "low", 2232, _LOW_TIER_PAYS, None),
    ("k", SymbolType.REGULAR.value, "low", 2046, _LOW_TIER_PAYS, None),
    ("q", SymbolType.REGULAR.value, "low", 1860, _LOW_TIER_PAYS, None),
    ("j", SymbolType.REGULAR.value, "low", 1674, _LOW_TIER_PAYS, None),
]

# Shown in the in-game paytable (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    "scatter": "Pearl Clam",
    "wild": "Poseidon",
    "siren": "Red Siren",
    "nymph": "Sea Nymph",
    "shark": "Shark",
    "a": "A", "k": "K", "q": "Q", "j": "J",
}

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Deep Fortune",
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
            # Descriptive only — expanding_wild keys off its own
            # trigger_symbol_code param, not this field.
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
