"""Seed data for the "dirty-money-mafia" game (front/dirty-money-mafia.html).

Unlike the other six games, this one was first assembled in the slot-builder
wizard (its BuilderDraft manifest holds the layout the frontend is built from,
see front/css/dirty-money-mafia.css). The wizard published an ACTIVE v1 config
of its own, but that config is the wizard's generic placeholder: anonymous
symbol codes (low_a..high_b) that don't match any delivered art folder, 3
paylines, and bet steps derived from a stray `min_bet` (10002). This module is
the hand-written math that replaces it, keyed to the art actually uploaded
(front/img/dirty-money-mafia/<code>/) — see `_sync_from_seed` for how the
existing rows get reconciled rather than a second config version published.

Symbol codes are a fixed contract with front/js/dirty-money-mafia/slot.js's
SYMBOL_FOLDERS (each code == its asset folder name) — do not rename them.
Paytable numbers and reel weights are placeholder game math (industry-typical
shapes, not RTP-tuned — same convention as the other seeds); the stage 6
simulator is what validates RTP against a target.

Mechanics (the wizard's own manifest `mechanics` list: line_pay, scatter,
expanding_wild, free_spins, bonus_buy) — identical set to Wild Western Story,
so the feature params mirror app/seed/wild_western_story.py.

Not wired up: the delivered `WOF` (wheel-of-fortune) Spine export. The builder
layout never places it on either screen and no wheel mechanic is enabled, so
there's nothing for it to drive yet.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype

GAME_CODE = "dirty-money-mafia"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Погрузитесь в атмосферу криминального Чикаго."
CATALOG_COVER_PATH = "img/dirty-money-mafia/logo_EmpireOfCrime-hero.jpg"
# The builder published this game pointing at the generic manifest player
# (play.html?slug=...). Now that it has a hand-built page, point the catalog
# there instead — see _sync_catalog_fields (this one is force-written, unlike
# app/seed/__init__.py's backfill, which only fills in NULLs).
CATALOG_PLAY_URL = "dirty-money-mafia.html"

# 3 rows x 5 reels, same generic 20-line set as the other line-pay games.
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

_COMMON_PAYS = {"3": 2, "4": 5, "5": 10}
_RARE_PAYS = {"3": 10, "4": 25, "5": 50}
_WILD_PAYS = {"3": 20, "4": 60, "5": 150}
_SCATTER_PAYS = {"3": 2, "4": 10, "5": 50}

# The uploaded art is a 4+4 set: four "common" (low) card-suit style symbols and
# four "rare" (high) character symbols, plus wild and scatter. Display name is
# what shows in the paytable popup.
# code -> (name, symbol_type, tier, reel_weight (same on all 5 reels), paytable, max_per_reel)
_SYMBOLS: list[tuple[str, str, str, str, int, dict, int | None]] = [
    ("scatter", "Scatter", SymbolType.SCATTER.value, "low", 3, _SCATTER_PAYS, 1),
    # Weight kept low: expanding_wild turns one drawn wild into a full
    # 3-symbol reel half the time (expand_chance below), so its effective
    # impact on RTP is far above the raw weight. Capped at 1/reel — at most
    # one wild, expanded or not, per reel (product convention).
    ("wild", "Wild", SymbolType.WILD.value, "high", 1, _WILD_PAYS, 1),
    ("rare_red", "Don", SymbolType.REGULAR.value, "high", 5, _RARE_PAYS, None),
    ("rare_yellow", "Consigliere", SymbolType.REGULAR.value, "high", 6, _RARE_PAYS, None),
    ("rare_blue", "Enforcer", SymbolType.REGULAR.value, "high", 7, _RARE_PAYS, None),
    ("rare_green", "Bootlegger", SymbolType.REGULAR.value, "high", 8, _RARE_PAYS, None),
    ("common_red", "Red Chip", SymbolType.REGULAR.value, "low", 18, _COMMON_PAYS, None),
    ("common_yellow", "Gold Chip", SymbolType.REGULAR.value, "low", 20, _COMMON_PAYS, None),
    ("common_green", "Green Chip", SymbolType.REGULAR.value, "low", 22, _COMMON_PAYS, None),
    ("common_blue", "Blue Chip", SymbolType.REGULAR.value, "low", 24, _COMMON_PAYS, None),
]

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for this game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Dirty Money / MAFIA",
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

    for order, (code, name, symbol_type, tier, weight, pays, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
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
        # `products` list shape (not the flat one the builder wrote) so the
        # buy_id matches what the other games' frontends send —
        # front/js/dirty-money-mafia/app.js posts "free_spins_buy".
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


async def _sync_catalog_fields(db: AsyncSession, game: Game) -> None:
    """The builder's publish-live route already filled this game's catalog
    fields in (unlike the hand-built games, which start out NULL), so
    app/seed/__init__.py's backfill — which bails as soon as catalog_badge is
    set — would never correct catalog_play_url from the generic
    "play.html?slug=..." player to this game's own page. Force-write instead.
    """
    if (
        game.catalog_play_url == CATALOG_PLAY_URL
        and game.catalog_badge == CATALOG_BADGE
        and game.catalog_cover_path == CATALOG_COVER_PATH
    ):
        return
    game.catalog_badge = CATALOG_BADGE
    game.catalog_description = CATALOG_DESCRIPTION
    game.catalog_cover_path = CATALOG_COVER_PATH
    game.catalog_play_url = CATALOG_PLAY_URL


async def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Reconcile an existing ACTIVE config to this file.

    Stricter than the other seeds' same-named helper, which only updates rows
    matched by code and never deletes: the config this one lands on was
    generated by the slot-builder wizard with an entirely different symbol set
    (low_a..high_b) and only 3 of the 20 paylines, so matching by code alone
    would leave the placeholder symbols in the reel strips and the game would
    still deal codes the frontend has no art for. Symbols and paylines are
    therefore made to match exactly (insert + update + delete); feature
    configs are updated/inserted (no deletes — nothing to remove).

    Safe because this game's config is a dev seed like every other one here:
    a real deploy publishes new versions through the admin API instead.
    """
    _, fresh = build_game_config()

    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in list(config.symbols):
        f = fresh_symbols.pop(symbol.code, None)
        if f is None:
            await db.execute(delete(Symbol).where(Symbol.id == symbol.id))
            config.symbols.remove(symbol)
            continue
        symbol.name = f.name
        symbol.symbol_type = f.symbol_type
        symbol.reel_weights = f.reel_weights
        symbol.paytable = f.paytable
        symbol.max_per_reel = f.max_per_reel
        symbol.tier = f.tier
        symbol.wild_subtype = f.wild_subtype
        symbol.display_order = f.display_order
    for f in fresh_symbols.values():
        db.add(
            Symbol(
                game_config=config, code=f.code, name=f.name, symbol_type=f.symbol_type,
                tier=f.tier, reel_weights=f.reel_weights, paytable=f.paytable,
                max_per_reel=f.max_per_reel, display_order=f.display_order,
                wild_subtype=f.wild_subtype,
            )
        )

    fresh_paylines = {p.index: p for p in fresh.paylines}
    for payline in list(config.paylines):
        f = fresh_paylines.pop(payline.index, None)
        if f is None:
            await db.execute(delete(Payline).where(Payline.id == payline.id))
            config.paylines.remove(payline)
            continue
        payline.positions = f.positions
    for f in fresh_paylines.values():
        db.add(Payline(game_config=config, index=f.index, positions=f.positions))

    # Bet bounds too: the wizard derived them from a stray min_bet of 10002.
    config.num_reels = fresh.num_reels
    config.num_rows = fresh.num_rows
    config.min_bet = fresh.min_bet
    config.max_bet = fresh.max_bet
    config.bet_step = fresh.bet_step
    config.bet_steps = fresh.bet_steps

    fresh_features = {fc.feature_type: fc for fc in fresh.feature_configs}
    for feature_config in config.feature_configs:
        f = fresh_features.pop(feature_config.feature_type, None)
        if f is None:
            continue
        feature_config.enabled = f.enabled
        feature_config.params = f.params
        feature_config.display_order = f.display_order
    for f in fresh_features.values():
        # game_config=config alone doesn't cascade a new row into the session
        # here (config was loaded via selectinload, not freshly constructed) —
        # db.add() explicitly, or it silently never persists.
        db.add(
            FeatureConfig(
                game_config=config, feature_type=f.feature_type,
                enabled=f.enabled, params=f.params, display_order=f.display_order,
            )
        )


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Idempotent: return the active config for this game, creating the game +
    seed config on first call (dev/test convenience — a real deploy manages
    configs through the admin API)."""
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
        await _sync_from_seed(db, config)
        await _sync_catalog_fields(db, config.game)
        await db.commit()
        return config

    _, config = build_game_config()
    db.add(config)
    await db.commit()
    # expire_on_commit=False (app/core/db.py) keeps the in-memory relationship
    # collections populated during construction above — no reload needed.
    return config
