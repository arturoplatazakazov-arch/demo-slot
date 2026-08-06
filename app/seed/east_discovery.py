"""Seed data for the "east-discovery" demo game (front/east-discovery.html
under this repo).

Symbol codes and the row-major grid orientation are a fixed contract with the
already-built frontend (front/js/east-discovery/slot.js's SYMBOL_FOLDERS) —
do not rename them. Paytable numbers, reel weights, and the payline layout
below are placeholder game math (industry-typical shapes, not RTP-tuned, same
convention as app/seed/amys_fruit_farm.py) — the stage 6 simulator is what
actually validates RTP against a target; treat these as a starting point.

Mechanics confirmed with product (see the plan this seed shipped with):
- `coin`/`collector_tiger` are SymbolType.BONUS with an empty paytable — they
  land on the grid via the normal weighted reel draw but never pay a cent
  through the standard engine (evaluate_line_wins/evaluate_count_wins both
  skip a symbol with no matching pays entry); they're purely scanned for by
  code in app/features/coin_multiplier.py and app/features/hold_and_win.py,
  the same way expanding_wild/free_spins already locate their own trigger
  symbols — no engine changes needed for this.
- `wild` expands+walks probabilistically (50%/50%) via app/features/
  expanding_wild.py's expand_chance/walk_chance — Amy's Fruit Farm keeps
  those both at the default 1.0 (always), untouched by this game's config.
- `collector_tiger` (3+) triggers Hold & Win (app/features/hold_and_win.py,
  start_empty=True — the round begins on an empty grid, only respins award
  coins) with coin value tiers x1/x2/x5/x10/x25/x50/x100, paid out as
  sum(locked) * total_bet.
- `coin` + `collector_tiger` + a line win in the base game (or Free Spins)
  triggers app/features/coin_multiplier.py: every coin on the grid draws its
  own x1...x100 multiplier (own weight table, separate from Hold & Win's),
  summed, multiplying the spin's line-pay total.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed import backfill_catalog_fields

GAME_CODE = "east-discovery"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Hold'n'Win слот в восточной тематике"
CATALOG_COVER_PATH = "img/east-discovery/img/logo_SouthDiscovery-hero.jpg"
CATALOG_PLAY_URL = "east-discovery.html"

# 11 линий = ровно те формы, на которые есть арт Win_Lines (анимации "1".."11"
# в том же порядке). Раньше здесь был generic-набор из 20 форм: лишние 9 платили
# без анимации линии (продукт: «лишние выигрышные линии», авг 2026). Индексы в
# БД теперь 1..11 и совпадают с именами анимаций 1:1 (см. клиентский
# PAYLINE_TO_WIN_LINE_ANIMATION).
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
# coin/collector_tiger deliberately pay nothing through the standard engine —
# see the module docstring above.
_NO_PAYS: dict[str, int] = {}

# Shared x1/x2/x5/x10/x25/x50/x100 tier set (Hold & Win and the base-game
# coin_multiplier each get their own copy/weighting below, per product).
_COIN_VALUE_WEIGHTS = {"1": 40, "2": 25, "5": 15, "10": 10, "25": 6, "50": 3, "100": 1}

# Hold & Win's own coin-value table: same tiers, plus "0" — a coin that
# lands with no multiplier at all (product, this session: "они могут быть с
# множителем и без"), still sticks to the grid but contributes nothing to
# the payout. Not shared with coin_multiplier (base game), which never
# draws a "no multiplier" outcome.
_HOLD_AND_WIN_VALUE_WEIGHTS = {"0": 50, **_COIN_VALUE_WEIGHTS}

# code -> (symbol_type, tier, reel_weight (same on all 5 reels), paytable, max_per_reel)
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 3, _SCATTER_PAYS, 1),
    # Weight kept low: expanding_wild turns one drawn wild into up to a full
    # 3-symbol reel (50% of the time — see expand_chance below), so its
    # effective frequency/impact on RTP is much higher than the raw weight
    # suggests. Still a placeholder — re-tune with the stage-6 simulator.
    # Capped at 1/reel (product): at most one wild — expanded or not — per
    # reel, so a single spin can't land more than 5 total.
    ("wild", SymbolType.WILD.value, "high", 1, _WILD_PAYS, 1),
    # Trigger-only (Hold & Win) — no own paytable, capped at 1/reel like
    # scatter so "3+ anywhere" stays a meaningful, tunable trigger rate.
    ("collector_tiger", SymbolType.BONUS.value, "high", 3, _NO_PAYS, 1),
    # Multiplier-carrier (base-game coin_multiplier combo, Hold & Win money
    # symbol) — no own paytable, no cap (frequency tuned via reel weight).
    ("coin", SymbolType.BONUS.value, "low", 4, _NO_PAYS, None),
    ("rare_cat", SymbolType.REGULAR.value, "high", 8, _HIGH_TIER_PAYS, None),
    ("rare_fish", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None),
    ("rare_papirus", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None),
    ("lp_blue", SymbolType.REGULAR.value, "low", 24, _LOW_TIER_PAYS, None),
    ("lp_green", SymbolType.REGULAR.value, "low", 22, _LOW_TIER_PAYS, None),
    ("lp_pink", SymbolType.REGULAR.value, "low", 20, _LOW_TIER_PAYS, None),
    ("lp_red", SymbolType.REGULAR.value, "low", 18, _LOW_TIER_PAYS, None),
]

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="East Discovery",
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
            name=code.replace("_", " ").title(),
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
        # A game_config can only have ONE row per feature_type (DB:
        # uq_feature_type_per_config), so multiple bonus-buy products live as
        # a list here instead of one row each — see
        # bonus_buy.resolve_bonus_buy_product, which also still accepts
        # the older flat single-product shape (Amy's Fruit Farm's) for
        # backward compatibility.
        params={
            "products": [
                {"buy_id": "free_spins_buy", "cost_multiplier": 100, "target_feature_id": "free_spins"},
                {"buy_id": "hold_and_win_buy", "cost_multiplier": 100, "target_feature_id": "hold_and_win"},
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
        feature_type=FeatureType.HOLD_AND_WIN.value,
        enabled=True,
        params={
            "trigger_symbol_code": "collector_tiger",
            "trigger_count": 3,
            # Vestigial once respin_coin_count_weights is set below (that
            # mode's own termination is "grid full", not this) — kept only
            # because the schema still requires the field.
            "respin_count": 3,
            "start_empty": True,
            "coin_value_weights": _HOLD_AND_WIN_VALUE_WEIGHTS,
            # Every respin guarantees 1-3 new coins (capped by remaining
            # empty cells), weighted toward fewer — "1 чаще всего, 3 редко"
            # (product) — instead of an independent land/no-land roll per
            # cell; the round then only ends when the grid fully fills.
            "respin_coin_count_weights": {"1": 50, "2": 30, "3": 20},
        },
        display_order=3,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.COIN_MULTIPLIER.value,
        enabled=True,
        params={
            "coin_symbol_code": "coin",
            "collector_symbol_code": "collector_tiger",
            "value_weights": _COIN_VALUE_WEIGHTS,
        },
        display_order=4,
    )

    return game, config


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience: this game's seed keeps getting tuned in place while
    iterating (reel weights, feature params, max_per_reel caps, bonus-buy
    products, ...), but get_or_seed_active_config below only *creates* the
    row once — without this, an already-seeded dev DB would silently keep
    serving whatever values (and rows) existed on first boot no matter how
    this file changes afterward (bit us once already: wild's max_per_reel=1
    was added to _SYMBOLS after the game had already been seeded, so the cap
    was never actually enforced). Reconciles mutable fields on existing rows
    in place (matched by code/feature_type — at most one enabled row per
    feature_type per game_config, DB-enforced: uq_feature_type_per_config;
    multiple bonus-buy products share the one bonus_buy row's params, see
    "products" there) and inserts any feature_configs the seed script has
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
