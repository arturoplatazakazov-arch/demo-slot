"""Seed data for the "mr-president-unicorn" demo game
(front/mr-president-unicorn.html under this repo).

Cloned from app/seed/wild_western_story.py: identical mechanics (5x3 line pay,
11 paylines, expanding wild, scatter free spins, bonus buy) and deliberately
identical math — the same reel weights, paytables and feature params, only the
symbol codes are this theme's. Keeping the numbers byte-identical means the
frontend swap is provably art-only; retune here once the stage 6 simulator has
something to say about this game specifically.

Symbol codes and the row-major grid orientation are a fixed contract with the
already-built frontend (front/js/mr-president-unicorn/slot.js's SYMBOL_CODES) —
do not rename them. Paytable numbers, reel weights, and the payline layout
below are placeholder game math (industry-typical shapes, not RTP-tuned, same
convention as app/seed/amys_fruit_farm.py / app/seed/east_discovery.py) — the
stage 6 simulator is what actually validates RTP against a target; treat these
as a starting point.

Mechanics — line-pay + scatter free spins + expanding wild only:
- `wild` expands+walks probabilistically, same params as app/seed/
  east_discovery.py's expanding_wild config (the frontend mechanic explicitly
  mirrors East Discovery's — see celebrateExpandedWild's comment there).
- No BONUS symbol type here (no coin/collector_tiger) — no hold_and_win or
  coin_multiplier feature configs, unlike East Discovery.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed import backfill_catalog_fields

GAME_CODE = "mr-president-unicorn"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Сатирический слот в Овальном кабинете: расширяющийся Wild и фриспины по ядерной кнопке"
CATALOG_COVER_PATH = "img/mr-president-unicorn/img/cover.jpg"
CATALOG_PLAY_URL = "mr-president-unicorn.html"

# 3 rows x 5 reels.
# 11 линий — тот же набор, что у Wild Western. Этой игре форма линии не нужна
# для арта (клиент рисует её SVG-полилинией прямо по выигравшим ячейкам, см.
# showWinLine), но набор оставлен идентичным, чтобы математика совпадала.
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
    # Same weights as the western original's wolf / whiskey / gun respectively.
    ("burger", SymbolType.REGULAR.value, "high", 744, _HIGH_TIER_PAYS, None),
    ("money", SymbolType.REGULAR.value, "high", 558, _HIGH_TIER_PAYS, None),
    ("toilet", SymbolType.REGULAR.value, "high", 465, _HIGH_TIER_PAYS, None),
    ("a", SymbolType.REGULAR.value, "low", 2232, _LOW_TIER_PAYS, None),
    ("k", SymbolType.REGULAR.value, "low", 2046, _LOW_TIER_PAYS, None),
    ("q", SymbolType.REGULAR.value, "low", 1860, _LOW_TIER_PAYS, None),
    ("j", SymbolType.REGULAR.value, "low", 1674, _LOW_TIER_PAYS, None),
]

# Shown in the in-game paytable (gameState.symbols -> renderInfoPopupContent).
_SYMBOL_NAMES = {
    "scatter": "Nuclear Button",
    "wild": "Mr. President",
    "burger": "Burger",
    "money": "Dollars",
    "toilet": "Golden Toilet",
    "a": "A", "k": "K", "q": "Q", "j": "J",
}

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Mr. President Unicorn",
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


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience: this game's seed keeps getting tuned in place while
    iterating (reel weights, feature params, max_per_reel caps, ...), but
    get_or_seed_active_config below only *creates* the row once — without
    this, an already-seeded dev DB would silently keep serving whatever
    values (and rows) existed on first boot no matter how this file changes
    afterward (see app/seed/east_discovery.py, which hit exactly this once).
    Reconciles mutable fields on existing rows in place (matched by
    code/feature_type) and inserts any feature_configs the seed script has
    gained since — but never removes rows, and never touches paylines
    (static)."""
    _, fresh = build_game_config()

    # Пейлайны теперь тоже реконсилируются (исторически «never touches
    # paylines»): сокращение набора 20 -> 11 (см. комментарий у PAYLINES)
    # должно доехать до уже засеянных БД — локальной и Railway — без ручной
    # миграции. Сопоставление по index; лишние строки удаляет каскад
    # delete-orphan на GameConfig.paylines.
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
