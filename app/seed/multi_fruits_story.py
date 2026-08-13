"""Seed data for the "multi-fruits-story" game (front/multi-fruits-story.html).

Second game assembled in the slot-builder wizard (after dirty-money-mafia), and
the first 3x3 one — its BuilderDraft manifest holds the layout the frontend is
built from (see front/css/multi-fruits-story.css). The wizard published an
ACTIVE v1 config of its own, but that config is the wizard's generic
placeholder: anonymous symbol codes (low_a..high_b) that match no delivered art
folder, and bet steps derived from a stray `min_bet` (10002). This module is the
hand-written math that replaces it, keyed to the art actually uploaded
(front/img/multi-fruits-story/<code>/) — see `_sync_from_seed` for how the
existing rows get reconciled rather than a second config version published.

Symbol codes are a fixed contract with front/js/multi-fruits-story/slot.js's
SYMBOL_FOLDERS (each code == its asset folder name) — do not rename them.

Mechanics: line_pay, scatter, free_spins, bonus_buy (the wizard's own manifest
`mechanics` list) plus multiplier_wild, which the manifest doesn't know about —
it came out of the delivered wild Spine export, whose skins (x2/x3/x5/x7 plus a
plain `wild`) only make sense as a per-wild multiplier. No expanding wild: that
export ships grid-cell size only, no reel-height pose.

3 reels x 3 rows means a payline is either a 3-of-a-kind or nothing, so the
paytable has a single "3" entry per symbol — see the RTP note on _PAYS below.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType

GAME_CODE = "multi-fruits-story"
CATALOG_BADGE = "Free Spins"
CATALOG_DESCRIPTION = "Испытай удачу в волшебном саду фортуны."
CATALOG_COVER_PATH = "img/multi-fruits-story/logo_catalog.jpg"
# The builder published this game pointing at the generic manifest player
# (play.html?slug=...). Now that it has a hand-built page, point the catalog
# there instead — see _sync_catalog_fields (force-written, unlike
# app/seed/__init__.py's backfill, which only fills in NULLs).
CATALOG_PLAY_URL = "multi-fruits-story.html"

NUM_REELS = 3
NUM_ROWS = 3

# The manifest's own 3 lines: one per row. A 3x3 grid has no room for the
# zig-zag sets the 5-reel games use, and the layout draws no win-line art.
# row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
]

# Bet is split evenly across the 3 paylines (bet_per_line = bet / 3), so every
# step is a multiple of 3 — otherwise each line win carries a fractional
# remainder that the API response truncates away on its way to `int`.
BET_STEPS = [12000, 30000, 60000, 120000, 300000, 600000]

# Payouts are per LINE (multiplied by bet/3), and only a full 3-of-a-kind pays —
# a 3-reel line is all-or-nothing, so at these weights the grid pays on ~12% of
# spins and each hit has to be worth proportionally more than in the 5-reel
# games. The table is then tuned DOWN around multiplier_wild: with the average
# wild worth ~2x and roughly a third of line wins carrying one, the mechanic
# alone nearly doubles RTP (measured: 1.84 on the pre-mechanic table).
# Measured over 500k spins (scripts/simulate.py --game multi-fruits-story
# --spins 500000 --seed 7, cross-checked on seed 21): RTP 0.956, hit frequency
# 12.1%, bonus frequency 0.11%, volatility "high" (stddev ~11), top win ~2300x
# the bet. Re-run it after touching any weight, payout or variant weight.
_PAYS = {
    "limon": {"3": 5.0},
    "vinograd": {"3": 6.0},
    "grusha": {"3": 8.0},
    "klubnika": {"3": 10.0},
    "bell": {"3": 20.0},
    "diamond": {"3": 48.0},
    "777": {"3": 140.0},
    # Wild pays on its own when a line comes up wild-only (app/engine/wins.py).
    # Cut harder than the rest: a wild-only line is the one combination where
    # ALL THREE multipliers stack (up to 7*7*7), so it swings RTP and the
    # maximum win far more than its raw frequency suggests.
    "wild": {"3": 150.0},
    # Scatter is a COUNT win: 3 anywhere on the grid pays 10x the whole bet AND
    # opens the free-spins round.
    "scatter": {"3": 10.0},
}

# code -> (display name, symbol type, tier, per-reel weight, max_per_reel).
# Four fruits are the low tier, bell/diamond/777 the high one — the classic
# fruit-machine ladder, and the order the art reads in.
_SYMBOLS: list[tuple[str, str, str, str, int, int | None]] = [
    ("limon", "Лимон", SymbolType.REGULAR.value, "low", 22, None),
    ("vinograd", "Виноград", SymbolType.REGULAR.value, "low", 20, None),
    ("grusha", "Груша", SymbolType.REGULAR.value, "low", 18, None),
    ("klubnika", "Клубника", SymbolType.REGULAR.value, "low", 16, None),
    ("bell", "Колокольчик", SymbolType.REGULAR.value, "high", 12, None),
    ("diamond", "Алмаз", SymbolType.REGULAR.value, "high", 9, None),
    ("777", "777", SymbolType.REGULAR.value, "high", 6, None),
    ("wild", "Wild", SymbolType.WILD.value, "high", 4, None),
    # Capped at 1 per reel: the round needs 3 scatters across 3 reels, and
    # letting two stack on one reel would make the trigger far spikier than the
    # weight suggests (same convention as the other games).
    ("scatter", "Scatter", SymbolType.SCATTER.value, "low", 4, 1),
]


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for this game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Multi Fruits Story",
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
        notes="Seed config — hand-tuned against scripts/simulate.py, replaces the builder placeholder.",
    )

    for order, (code, name, symbol_type, tier, weight, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=_PAYS[code],
            max_per_reel=max_per_reel,
            display_order=order,
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
            # 3 reels x max 1 scatter per reel means 3 is also the maximum, so
            # the by-count table has exactly one entry and `spins_awarded` is
            # the fallback that can never be reached.
            "spins_awarded": 10,
            "spins_awarded_by_count": {"3": 10},
            "retrigger_enabled": True,
            # A 3x3 base game pays rarely; doubling wins is what makes the
            # round feel different from just "10 more spins".
            "win_multiplier": 2,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.MULTIPLIER_WILD.value,
        enabled=True,
        params={
            "wild_symbol_code": "wild",
            # Value -> weight; "1" is the "stayed a plain WILD" outcome. The
            # delivered art has exactly these four multipliers (Spine skins
            # x2/x3/x5/x7 plus `wild`), so this set is fixed by the assets —
            # only the weights are tunable. Just over half of all wilds stay
            # plain, which keeps the transform an event rather than the norm.
            "variant_weights": {"1": 55, "2": 20, "3": 13, "5": 8, "7": 4},
        },
        display_order=2,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
        # `products` list shape (not the flat one the builder wrote) so the
        # buy_id matches what the other games' frontends send —
        # front/js/multi-fruits-story/app.js posts "free_spins_buy".
        #
        # 20x the bet, NOT the wizard's default 100x (nor the 100x the other
        # seeds carry): what the purchase buys here is 10 free spins paying
        # double, i.e. ~10 * 2 * 0.94 = ~19x the bet back on average, so 100x
        # would sell a ~0.19-RTP product. 20x prices the buy at roughly the
        # base game's own RTP. It also keeps the cheapest buy (20 * 12000 =
        # 240k) inside the 1M starting balance, which 100x would not.
        params={
            "products": [
                {"buy_id": "free_spins_buy", "cost_multiplier": 20, "target_feature_id": "free_spins"},
            ],
        },
        display_order=1,
    )

    return game, config


async def _sync_catalog_fields(db: AsyncSession, game: Game) -> None:
    """The builder's publish-live route already filled this game's catalog
    fields in (unlike the hand-built games, which start out NULL), so
    app/seed/__init__.py's backfill — which bails as soon as catalog_badge is
    set — would never correct catalog_play_url from the generic
    "play.html?slug=..." player to this game's own page, nor the badge the
    wizard defaulted to the game's own name. Force-write instead.
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

    Same strictness as app/seed/dirty_money_mafia.py's namesake and for the same
    reason: the config this one lands on was generated by the slot-builder
    wizard with an entirely different symbol set (low_a..high_b), so matching by
    code alone would leave the placeholder symbols in the reel strips and the
    game would keep dealing codes the frontend has no art for. Symbols and
    paylines are made to match exactly (insert + update + delete); feature
    configs are updated/inserted (no deletes — nothing to remove).

    Safe because this game's config is a dev seed like every other one here: a
    real deploy publishes new versions through the admin API instead.
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
