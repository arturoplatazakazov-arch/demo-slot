"""Seed data for the "amys-fruit-farm" demo game (front/ under this repo).

Symbol codes, the popup key set, and the row-major grid orientation are a
fixed contract with the already-built frontend (front/js/slot.js) — do not
rename them. Paytable numbers, reel weights, and the payline layout below
are placeholder game math (industry-typical shapes, not RTP-tuned) — the
stage 6 simulator is what actually validates RTP against a target; treat
these as a starting point to iterate on, not final numbers.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed import backfill_catalog_fields

GAME_CODE = "amys-fruit-farm"
CATALOG_BADGE = "Farm"
CATALOG_DESCRIPTION = "Классический слот с бонусной игрой на ферме"
CATALOG_COVER_PATH = "img/amys-fruit-farm/img/logo_AmysFruitFarm-hero.jpg"
CATALOG_PLAY_URL = "index.html"

# 3 rows x 5 reels, industry-typical 20-line set. row index: 0=top, 1=mid, 2=bottom.
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

# code -> (symbol_type, tier, reel_weight (same on all 5 reels), paytable, max_per_reel)
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    # At most 1 scatter per reel (so at most 5 on screen) — was piggybacked
    # on free_spins.params.max_per_reel, now a generic per-symbol field.
    ("scatter", SymbolType.SCATTER.value, "low", 3, _SCATTER_PAYS, 1),
    # Weight dropped from 3 -> 1: the expanding_wild feature (see FeatureConfig
    # below) turns one drawn wild into a full 3-symbol reel, so its effective
    # frequency/impact on RTP is much higher than a plain line-pay symbol at
    # the same weight would be. Still a placeholder — re-tune with the
    # stage-6 simulator, not by hand.
    ("wild", SymbolType.WILD.value, "high", 1, _WILD_PAYS, None),
    ("duck", SymbolType.REGULAR.value, "high", 8, _HIGH_TIER_PAYS, None),
    ("cow", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None),
    ("dog", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None),
    ("watermelon", SymbolType.REGULAR.value, "low", 24, _LOW_TIER_PAYS, None),
    ("corn", SymbolType.REGULAR.value, "low", 22, _LOW_TIER_PAYS, None),
    ("blueberry", SymbolType.REGULAR.value, "low", 20, _LOW_TIER_PAYS, None),
    ("strawberry", SymbolType.REGULAR.value, "low", 18, _LOW_TIER_PAYS, None),
    ("pear", SymbolType.REGULAR.value, "low", 16, _LOW_TIER_PAYS, None),
]

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Amy's Fruit Farm",
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
            name=code.capitalize(),
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=pays,
            max_per_reel=max_per_reel,
            display_order=order,
            # Descriptive only — the expanding_wild feature (below) keys off
            # its own trigger_symbol_code param, not this field.
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
        params={"buy_id": "free_spins_buy", "cost_multiplier": 100, "target_feature_id": "free_spins"},
        display_order=1,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.EXPANDING_WILD.value,
        enabled=True,
        params={"trigger_symbol_code": "wild", "walk_enabled": True, "walk_direction": "right"},
        display_order=2,
    )

    return game, config


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience: this game's seed keeps getting tuned in place while
    iterating (reel weights, feature params) — without this, an already-
    seeded dev DB would silently keep serving whatever values existed on
    first boot no matter how this file changes afterward (see
    app/seed/east_discovery.py, which this mirrors — it hit exactly this
    once). Reconciles mutable fields on existing rows in place (matched by
    code/feature_type), but never removes rows and never touches paylines
    (static)."""
    _, fresh = build_game_config()

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
    for feature_config in config.feature_configs:
        f = fresh_features.get(feature_config.feature_type)
        if f is None:
            continue
        feature_config.enabled = f.enabled
        feature_config.params = f.params
        feature_config.display_order = f.display_order


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
