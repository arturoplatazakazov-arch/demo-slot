"""Seed data for the "neon-reels" demo game (front/neon-reels.html under this
repo). Built to match the slot-builder manifest this game was authored in
(builder_drafts row, code "neon-reels"): a 3x5 line-pay game with scatter-
triggered free spins and a coin multiplier — mechanics ["line_pay",
"scatter", "free_spins", "coin_multiplier"].

Unlike the four hand-built demos, this game's Game row already exists (the
builder created it together with its builder_draft) but had no ACTIVE
GameConfig, so it never showed in the catalog and its sessions failed to
start ("no active config for this game"). This seed attaches a v1 config to
that existing Game row rather than creating a second one — see
get_or_seed_active_config below.

Symbol codes and the row-major grid orientation are a fixed contract with
the frontend (front/js/neon-reels/slot.js's SYMBOL_FOLDERS) — do not rename
them. Paytable numbers and reel weights are placeholder game math (industry-
typical shapes, not RTP-tuned, same convention as the other seeds) — the
stage-6 simulator is what actually validates RTP.

coin_multiplier note: east-discovery gates the coin payout on a separate
`collector_tiger` symbol landing alongside the coins. Neon Reels has no such
collector symbol in its art set, so `collector_symbol_code` is pointed at
"coin" itself — the multiplier then applies whenever a coin is on the grid
AND there's a line win this spin (coins multiply the line-pay total), which
is the self-contained "coins boost your win" reading of the mechanic. Every
coin still always draws and shows its own value regardless (presentation is
never gated — see app/features/coin_multiplier.py).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed import backfill_catalog_fields

GAME_CODE = "neon-reels"
GAME_NAME = "Neon Reels"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Неоновый киберпанк-слот с фриспинами и монетным множителем"
CATALOG_COVER_PATH = "img/neon-reels/logo_NeonReels-hero.jpg"
CATALOG_PLAY_URL = "neon-reels.html"

# 3 rows x 5 reels, same generic 20-line set the other demos use. row index: 0=top, 1=mid, 2=bottom.
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
# coin deliberately pays nothing through the standard engine — it's a pure
# multiplier carrier (see the module docstring).
_NO_PAYS: dict[str, int] = {}

# Base-game coin_multiplier value table (x1..x100 tiers, weighted toward the
# low end).
_COIN_VALUE_WEIGHTS = {"1": 40, "2": 25, "5": 15, "10": 10, "25": 6, "50": 3, "100": 1}

# code -> (symbol_type, tier, reel_weight (same on all 5 reels), paytable, max_per_reel)
# Codes MUST match front/js/neon-reels/slot.js's SYMBOL_FOLDERS keys.
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 3, _SCATTER_PAYS, 1),
    # Standard substituting wild (no expansion in this game), capped at 1/reel.
    ("wild", SymbolType.WILD.value, "high", 4, _WILD_PAYS, 1),
    # Multiplier carrier — no own paytable, frequency tuned via reel weight.
    ("coin", SymbolType.BONUS.value, "low", 4, _NO_PAYS, None),
    # High-pay themed characters.
    ("geisha", SymbolType.REGULAR.value, "high", 8, _HIGH_TIER_PAYS, None),
    ("samurai", SymbolType.REGULAR.value, "high", 7, _HIGH_TIER_PAYS, None),
    ("sensei", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None),
    ("yakudza", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None),
    # Low-pay letters.
    ("a", SymbolType.REGULAR.value, "low", 24, _LOW_TIER_PAYS, None),
    ("k", SymbolType.REGULAR.value, "low", 22, _LOW_TIER_PAYS, None),
    ("q", SymbolType.REGULAR.value, "low", 20, _LOW_TIER_PAYS, None),
    ("j", SymbolType.REGULAR.value, "low", 18, _LOW_TIER_PAYS, None),
]

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


def _populate_config(config: GameConfig) -> None:
    """Attach this game's symbols, paylines and feature configs to an
    (unpersisted) GameConfig. Split out of build_game_config so the config
    can be built against either a fresh Game or the pre-existing one."""
    for order, (code, symbol_type, tier, weight, pays, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=code.replace("_", " ").upper() if len(code) == 1 else code.replace("_", " ").title(),
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
            "coin_symbol_code": "coin",
            # No dedicated collector symbol in this art set — coins gate their
            # own payout (see the module docstring).
            "collector_symbol_code": "coin",
            "value_weights": _COIN_VALUE_WEIGHTS,
        },
        display_order=2,
    )


def _new_config(game: Game, version: int = 1) -> GameConfig:
    config = GameConfig(
        game=game,
        version=version,
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
    _populate_config(config)
    return config


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config with
    a fresh Game row — used only for the from-scratch path and by
    _sync_from_seed's diff. In practice get_or_seed_active_config attaches the
    config to the builder's pre-existing Game row instead."""
    game = Game(
        code=GAME_CODE, name=GAME_NAME,
        catalog_badge=CATALOG_BADGE, catalog_description=CATALOG_DESCRIPTION,
        catalog_cover_path=CATALOG_COVER_PATH, catalog_play_url=CATALOG_PLAY_URL,
    )
    return game, _new_config(game)


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience: reconcile mutable fields (reel weights, paytables,
    feature params) on an already-seeded config in place so re-tuning this
    file takes effect without a DB wipe. Mirrors east_discovery._sync_from_seed
    — matches symbols by code and feature_configs by feature_type, inserts any
    newly-added feature_configs, never removes rows, never touches paylines."""
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
    """Idempotent: return the active config for Neon Reels, creating it on
    first call. Attaches the config to the builder's pre-existing Game row
    (code "neon-reels") when present — creating a second Game with the same
    code would violate the unique constraint — and only falls back to
    creating the Game itself if it's somehow missing."""
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

    game = (await db.execute(select(Game).where(Game.code == GAME_CODE))).scalars().first()
    if game is not None:
        # The builder already left a DRAFT config at version 1 for this game —
        # the ACTIVE seed config goes in as the next version (uq_game_config_
        # version is per (game_id, version)), leaving that draft untouched.
        max_version = (
            await db.execute(select(func.max(GameConfig.version)).where(GameConfig.game_id == game.id))
        ).scalar()
        config = _new_config(game, (max_version or 0) + 1)
        # Catalog fields on the pre-existing (builder-created) Game row are
        # still None — set them here (backfill_catalog_fields no-ops once set).
        await backfill_catalog_fields(
            db, game, badge=CATALOG_BADGE, description=CATALOG_DESCRIPTION,
            cover_path=CATALOG_COVER_PATH, play_url=CATALOG_PLAY_URL,
        )
    else:
        game, config = build_game_config()

    db.add(config)
    await db.commit()
    return config
