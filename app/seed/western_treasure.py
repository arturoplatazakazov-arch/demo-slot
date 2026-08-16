"""Seed data for the "western-treasure" demo game
(front/western-treasure.html under this repo).

Слот WESTERN TREASURE: арт свой (см. front/img/western-treasure/), математика
— полный набор механик Empire of Crime / app/seed/dirty_money_mafia.py: 5x3
line pay, 20 линий, расширяющийся вайлд, скаттерные фриспины, bonus buy x100
И колесо фортуны (три символа wheel открывают барабан с множителями).

Отличие от dirty-money-mafia в том, откуда взяты ВЕСА. Тот сид пришёл из
конструктора и веса там плейсхолдерные (1..24 «на глаз»); здесь взята уже
обкатанная развесовка Gangsta City / Wild Western Story — суммарный вес
барабана 10400 и скаттер ровно 7% всех дро, — и из неё вырезана доля под
новый символ колеса:

- `wheel` = 364 (3.5% дро, cap 1/барабан). При трёх рядах это ~10.1% на
  барабан, то есть триггер (3+ из 5) примерно раз в 110 спинов — колесо
  остаётся событием, а не рутиной.
- Всё, кроме скаттера, домножено на 9308/9672 ≈ 0.962, чтобы освободить эти
  364: относительные частоты вайлда, дорогих и младших не изменились, а
  скаттер так и остался 728 из 10400.

Младший тир — вестерн-реквизит (подкова / револьвер / виски / динамит), а не
карточные A/K/Q/J: буквенные младшие повторяли предыдущую игру линейки
(продукт). Веса при переименовании не трогали — это ровно те же четыре доли,
что были у букв, поэтому математика не поехала; зато `_sync_from_seed` теперь
обязан УДАЛЯТЬ символы, которых в сиде больше нет.

Коды символов и row-major ориентация сетки — фиксированный контракт с фронтом
(SYMBOL_CODES в front/js/western-treasure/slot.js), не переименовывать.
Пейтейблы — плейсхолдерная математика индустриально-типовой формы, как во всех
остальных сидах: RTP по этой игре скажет симулятор шестого этапа.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed import backfill_catalog_fields

GAME_CODE = "western-treasure"
CATALOG_BADGE = "Wheel Bonus"
CATALOG_DESCRIPTION = "Золотая лихорадка Дикого Запада: Wild на весь барабан, фриспины и колесо фортуны"
CATALOG_COVER_PATH = "img/western-treasure/img/cover.jpg"
CATALOG_PLAY_URL = "western-treasure.html"

# 3 rows x 5 reels, тот же набор 20 линий, что у Empire of Crime.
# row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1, 1, 1],
    [0, 0, 0, 0, 0],
    [2, 2, 2, 2, 2],
    [0, 1, 2, 1, 0],
    [2, 1, 0, 1, 2],
    [0, 0, 1, 0, 0],
    [2, 2, 1, 2, 2],
    [1, 0, 0, 0, 1],
    [1, 2, 2, 2, 1],
    [0, 1, 1, 1, 0],
    [2, 1, 1, 1, 2],
    [1, 0, 1, 0, 1],
    [1, 2, 1, 2, 1],
    [0, 1, 0, 1, 0],
    [2, 1, 2, 1, 2],
    [0, 2, 0, 2, 0],
    [2, 0, 2, 0, 2],
    [1, 1, 0, 1, 1],
    [1, 1, 2, 1, 1],
    [0, 2, 2, 2, 0],
]

_LOW_TIER_PAYS = {"3": 2, "4": 5, "5": 10}
_HIGH_TIER_PAYS = {"3": 10, "4": 25, "5": 50}
_WILD_PAYS = {"3": 20, "4": 60, "5": 150}
_SCATTER_PAYS = {"3": 2, "4": 10, "5": 50}
# Колесо само по себе не платит: три символа открывают барабан, и приз — это
# сам барабан (app/features/wheel_of_fortune.py). Тип BONUS, поэтому
# wins.py's count-pay его вообще не подбирает.
_WHEEL_PAYS: dict[str, float] = {}

# code -> (symbol_type, tier, reel_weight (одинаковый на всех 5 барабанах),
#          paytable, max_per_reel)
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 728, _SCATTER_PAYS, 1),
    # Cap 1/барабан по той же причине, что и у скаттера: колесу нужно 3 штуки
    # на 5 барабанов, и стопка из двух на одном барабане сделала бы триггер
    # заметно резче, чем говорит вес.
    ("wheel", SymbolType.BONUS.value, "high", 364, _WHEEL_PAYS, 1),
    # Вес намеренно низкий: expanding_wild превращает один выпавший вайлд в
    # целый барабан в половине случаев (expand_chance ниже), поэтому его
    # реальный вклад в RTP сильно выше сырого веса. Cap 1/барабан —
    # продуктовая конвенция: не больше одного вайлда на барабан,
    # расширенного или нет.
    ("wild", SymbolType.WILD.value, "high", 90, _WILD_PAYS, 1),
    ("bison", SymbolType.REGULAR.value, "high", 597, _HIGH_TIER_PAYS, None),
    ("mustang", SymbolType.REGULAR.value, "high", 448, _HIGH_TIER_PAYS, None),
    ("eagle", SymbolType.REGULAR.value, "high", 358, _HIGH_TIER_PAYS, None),
    ("wolf", SymbolType.REGULAR.value, "high", 298, _HIGH_TIER_PAYS, None),
    # Младшие — не карточные A/K/Q/J, а вестерн-реквизит (продукт: буквенные
    # младшие «слишком похожи на предыдущую игру»). Веса тех же четырёх долей,
    # что были у букв, — тир не изменился, поменялась только картинка и код.
    ("horseshoe", SymbolType.REGULAR.value, "low", 2148, _LOW_TIER_PAYS, None),
    ("revolver", SymbolType.REGULAR.value, "low", 1969, _LOW_TIER_PAYS, None),
    ("whiskey", SymbolType.REGULAR.value, "low", 1790, _LOW_TIER_PAYS, None),
    ("dynamite", SymbolType.REGULAR.value, "low", 1610, _LOW_TIER_PAYS, None),
]

# Shown in the in-game paytable (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    # Скаттер — сундук с золотом, а не звезда шерифа: звезда слишком близко
    # повторяла референс (продукт). Триггер колеса — барабан револьвера, в
    # пару к самому бонусному барабану.
    "scatter": "Treasure Chest",
    "wheel": "Revolver Drum",
    "wild": "The Gunslinger",
    "bison": "Bison",
    "mustang": "Mustang",
    "eagle": "Eagle",
    "wolf": "Wolf",
    "horseshoe": "Horseshoe",
    "revolver": "Revolver",
    "whiskey": "Whiskey",
    "dynamite": "Dynamite",
}

NUM_REELS = 5
NUM_ROWS = 3

# Кратно 20 линиям (см. PAYLINES) — валидатор loaders.validate_bet_amount
# требует, чтобы ставка делилась на число линий. Те же числа, что у
# Empire of Crime.
BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Western Treasure",
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
            # `products` list shape — buy_id должен совпадать с тем, что шлёт
            # front/js/western-treasure/app.js ("free_spins_buy").
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
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.WHEEL_OF_FORTUNE.value,
        enabled=True,
        params={
            "trigger_symbol_code": "wheel",
            "trigger_count": 3,
            # Порядок секторов — по часовой стрелке от верхнего. Клиент
            # подписывает (пустые) гнёзда барабана по этому списку, поэтому
            # набор призов — это правка конфига, а не арта. ВОСЕМЬ записей:
            # барабан колеса — это цилиндр револьвера (продукт), и у
            # сгенерированного арта ровно восемь камор, ровно через 45°
            # начиная с 12 часов (front/img/western-treasure/img/wof_drum.png).
            # Вот это число завязано на картинку — см. WOF_SEGMENT_COUNT в
            # front/js/western-treasure/slot.js. Мелкие множители расставлены
            # вперемешку с крупными, чтобы соседняя камора всегда читалась как
            # «почти повезло».
            "segments": [
                {"type": "multiplier", "value": 2, "weight": 34},
                {"type": "multiplier", "value": 5, "weight": 16},
                {"type": "multiplier", "value": 3, "weight": 26},
                {"type": "multiplier", "value": 10, "weight": 8},
                {"type": "multiplier", "value": 2, "weight": 34},
                {"type": "multiplier", "value": 8, "weight": 11},
                {"type": "free_spins", "weight": 6},
                {"type": "multiplier", "value": 25, "weight": 4},
            ],
        },
        display_order=3,
    )

    return game, config


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience: this game's seed keeps getting tuned in place while
    iterating (reel weights, feature params, max_per_reel caps, ...), but
    get_or_seed_active_config below only *creates* the row once — without
    this, an already-seeded dev DB would silently keep serving whatever
    values (and rows) existed on first boot no matter how this file changes
    afterward (see app/seed/east_discovery.py, which hit exactly this once).
    Reconciles mutable fields on existing rows in place (matched by
    code/feature_type), inserts what the seed has gained, and — unlike the
    other games' same-named helper — DELETES symbols the seed has dropped.
    That last part exists because the low tier was re-cut from card royals
    (a/k/q/j) to western props: leaving the four letter rows behind would keep
    them in the reel strips, and the game would deal codes the frontend has no
    art for. Feature configs are still never deleted (nothing to remove)."""
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
    matched_codes = set()
    for symbol in list(config.symbols):
        f = fresh_symbols.get(symbol.code)
        if f is None:
            # Same mechanism the paylines above rely on: GameConfig.symbols is
            # cascade="all, delete-orphan", so dropping the row from the
            # collection deletes it on flush. No db.execute here — this helper
            # is synchronous.
            config.symbols.remove(symbol)
            continue
        matched_codes.add(symbol.code)
        symbol.name = f.name
        symbol.symbol_type = f.symbol_type
        symbol.reel_weights = f.reel_weights
        symbol.paytable = f.paytable
        symbol.max_per_reel = f.max_per_reel
        symbol.tier = f.tier
        symbol.wild_subtype = f.wild_subtype
        symbol.display_order = f.display_order
    for code, f in fresh_symbols.items():
        if code in matched_codes:
            continue
        db.add(
            Symbol(
                game_config=config, code=f.code, name=f.name, symbol_type=f.symbol_type,
                tier=f.tier, reel_weights=f.reel_weights, paytable=f.paytable,
                max_per_reel=f.max_per_reel, display_order=f.display_order,
                wild_subtype=f.wild_subtype,
            )
        )

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
        # game_config=config alone doesn't cascade a new row into the
        # session here (config was loaded via selectinload, not freshly
        # constructed) — db.add() explicitly, or it silently never persists.
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
