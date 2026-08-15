"""Seed data for the "uniqorn-back-to-fabulous" demo game
(front/uniqorn-back-to-fabulous.html under this repo).

Хеллоуин-слот про ведьму, превратившую единорога в муху. Механика взята с
app/seed/neon_reels.py — 5x3 line pay по 11 линиям, скаттерные фриспины и
coin_multiplier — и математика оставлена БАЙТ-В-БАЙТ той же (те же веса
барабанов, пейтейблы, параметры фич, лестница ставок): меняются только коды
символов под эту тему. Это тот же приём, что у mr_president_unicorn (клон
wild_western_story): совпадающие числа доказывают, что подмена фронта —
чисто художественная. Перетюнить можно здесь, когда по этой игре что-то
скажет симулятор шестого этапа.

Соответствие символов оригиналу (вес не менялся):
    geisha -> cauldron, samurai -> book, sensei -> ball, yakudza -> hat,
    coin -> essence, остальные коды совпадают.

coin_multiplier: выделенного символа-коллектора в этом арт-сете нет, поэтому
`collector_symbol_code` указывает на саму «эссенцию» — множитель применяется,
когда эссенция есть на поле И в этом спине была выигрышная линия (см. тот же
комментарий в app/seed/neon_reels.py). Значение на каждой эссенции рисуется
всегда, независимо от того, применился множитель или нет.

Коды символов и row-major ориентация сетки — фиксированный контракт с
фронтом (SYMBOL_CODES в front/js/uniqorn-back-to-fabulous/slot.js), не
переименовывать.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed import backfill_catalog_fields

GAME_CODE = "uniqorn-back-to-fabulous"
GAME_NAME = "Uniqorn Back to Fabulous"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Хеллоуин у ведьмы: единорог-муха, фриспины и радужная эссенция-множитель"
CATALOG_COVER_PATH = "img/uniqorn-back-to-fabulous/img/cover.jpg"
CATALOG_PLAY_URL = "uniqorn-back-to-fabulous.html"

# 3 rows x 5 reels. Тот же набор из 11 линий, что у Neon Reels — форма линии
# фронту не нужна как арт (он рисует SVG-полилинию по выигравшим ячейкам, см.
# showWinLine), но набор оставлен идентичным ради совпадения математики.
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
# essence намеренно ничего не платит через стандартный движок — это чистый
# носитель множителя (см. докстринг модуля).
_NO_PAYS: dict[str, int] = {}

# Таблица значений множителя (x1..x100, перекос в низкие тиры) — та же, что в
# neon-reels.
_COIN_VALUE_WEIGHTS = {"1": 40, "2": 25, "5": 15, "10": 10, "25": 6, "50": 3, "100": 1}

# code -> (symbol_type, tier, reel_weight (одинаковый на всех 5 барабанах),
# paytable, max_per_reel). Коды ОБЯЗАНЫ совпадать с SYMBOL_CODES фронта.
# Скаттер = ровно 7% всех дро (унаследовано из neon-reels: 10% давали
# бесконечный бонус — ретриггер порождал в среднем 1.38 новых фриспина на
# спин). Итого 11800, триггер ~раз в 18 спинов.
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 826, _SCATTER_PAYS, 1),
    # Обычный подставляющийся вайлд (без расширения), не больше одного на барабан.
    ("wild", SymbolType.WILD.value, "high", 372, _WILD_PAYS, 1),
    # Носитель множителя — своего пейтейбла нет, частота задаётся весом.
    ("essence", SymbolType.BONUS.value, "low", 372, _NO_PAYS, None),
    # Дорогие тематические символы.
    ("cauldron", SymbolType.REGULAR.value, "high", 744, _HIGH_TIER_PAYS, None),
    ("book", SymbolType.REGULAR.value, "high", 651, _HIGH_TIER_PAYS, None),
    ("ball", SymbolType.REGULAR.value, "high", 558, _HIGH_TIER_PAYS, None),
    ("hat", SymbolType.REGULAR.value, "high", 465, _HIGH_TIER_PAYS, None),
    # Дешёвые буквы.
    ("a", SymbolType.REGULAR.value, "low", 2232, _LOW_TIER_PAYS, None),
    ("k", SymbolType.REGULAR.value, "low", 2046, _LOW_TIER_PAYS, None),
    ("q", SymbolType.REGULAR.value, "low", 1860, _LOW_TIER_PAYS, None),
    ("j", SymbolType.REGULAR.value, "low", 1674, _LOW_TIER_PAYS, None),
]

# Показывается в игровом пейтейбле (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    "scatter": "Magic Dust",
    "wild": "Cursed Uniqorn",
    "essence": "Rainbow Essence",
    "cauldron": "Cauldron",
    "book": "Book of Spells",
    "ball": "Crystal Ball",
    "hat": "Witch Hat",
    "a": "A", "k": "K", "q": "Q", "j": "J",
}

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name=GAME_NAME,
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
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.COIN_MULTIPLIER.value,
        enabled=True,
        params={
            "coin_symbol_code": "essence",
            # Отдельного коллектора в арт-сете нет — эссенция гейтит саму себя
            # (см. докстринг модуля).
            "collector_symbol_code": "essence",
            "value_weights": _COIN_VALUE_WEIGHTS,
        },
        display_order=2,
    )

    return game, config


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience: reconcile mutable fields (reel weights, paytables,
    feature params, bet ladder, paylines) on an already-seeded config in place,
    so re-tuning this file takes effect without a DB wipe. Идентичен
    mr_president_unicorn._sync_from_seed — сопоставление символов по коду,
    фич по feature_type, пейлайнов по index; строки не удаляются (кроме
    лишних пейлайнов — их снимает delete-orphan)."""
    _, fresh = build_game_config()

    # Лестница ставок обязана оставаться кратной числу линий (валидатор
    # loaders.validate_bet_amount) — реконсилируем вместе с пейлайнами.
    config.min_bet = fresh.min_bet
    config.max_bet = fresh.max_bet
    config.bet_step = fresh.bet_step
    config.bet_steps = fresh.bet_steps
    fresh_paylines = {p.index: p for p in fresh.paylines}
    for payline in list(config.paylines):
        f = fresh_paylines.get(payline.index)
        if f is None:
            config.paylines.remove(payline)
        else:
            payline.positions = f.positions
    existing_indices = {p.index for p in config.paylines}
    for index, f in fresh_paylines.items():
        if index not in existing_indices:
            config.paylines.append(Payline(index=index, positions=f.positions))

    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in config.symbols:
        f = fresh_symbols.get(symbol.code)
        if f is None:
            continue
        symbol.reel_weights = f.reel_weights
        symbol.paytable = f.paytable
        symbol.max_per_reel = f.max_per_reel
        symbol.tier = f.tier
        symbol.wild_subtype = f.wild_subtype
        symbol.display_order = f.display_order

    fresh_features = {fc.feature_type: fc for fc in fresh.feature_configs}
    matched_keys = set()
    for feature_config in config.feature_configs:
        f = fresh_features.get(feature_config.feature_type)
        if f is None:
            continue
        matched_keys.add(feature_config.feature_type)
        feature_config.enabled = f.enabled
        feature_config.params = f.params
        feature_config.display_order = f.display_order

    for key, f in fresh_features.items():
        if key in matched_keys:
            continue
        # game_config=config сам по себе не каскадит новую строку в сессию
        # (config пришёл через selectinload, а не создан здесь) — нужен явный
        # db.add(), иначе строка молча не сохранится.
        db.add(
            FeatureConfig(
                game_config=config,
                feature_type=f.feature_type,
                enabled=f.enabled,
                params=f.params,
                display_order=f.display_order,
            )
        )


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Idempotent: return the active config for the demo game, creating the
    game + seed config on first call (dev/test convenience — a real deploy
    manages configs through the admin API, stage 5's other half)."""
    existing = await db.execute(
        select(GameConfig)
        .join(Game)
        .where(Game.code == GAME_CODE, GameConfig.status == GameConfigStatus.ACTIVE.value)
        .options(
            selectinload(GameConfig.symbols),
            selectinload(GameConfig.paylines),
            selectinload(GameConfig.feature_configs),
            selectinload(GameConfig.game),
        )
    )
    config = existing.scalars().first()
    if config is not None:
        _sync_from_seed(db, config)
        await backfill_catalog_fields(
            db, config.game, badge=CATALOG_BADGE, description=CATALOG_DESCRIPTION,
            cover_path=CATALOG_COVER_PATH, play_url=CATALOG_PLAY_URL,
        )
        await db.commit()
        return config

    _, config = build_game_config()
    db.add(config)
    await db.commit()
    # expire_on_commit=False (app/core/db.py) keeps the in-memory relationship
    # collections populated during construction above — no reload needed.
    return config
