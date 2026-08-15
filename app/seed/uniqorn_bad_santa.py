"""Seed data for the "uniqorn-bad-santa" demo game (front/uniqorn-bad-santa.html
— "Uniqorn Bad Santa", a Christmas-themed avalanche slot).

Mechanically a 1:1 clone of app/seed/sugar_galaxy.py — the repo's
avalanche/cascade engine (app/engine/avalanche.py), not line-pay — because
that is exactly what was asked for ("механика такая же как в шугар гелекси").
Only the symbol set, the catalog metadata and the art behind them are new:

- 6 reels x 5 rows (30 cells), count-pay by tier ("8+ of one symbol anywhere"),
  no Payline rows at all.
- WILD substitutes into whichever REGULAR symbol has the most positions on the
  grid and has no paytable of its own; SCATTER is trigger-only.
- x2/x3/x5/x7 are multiplier tokens (SymbolType.BONUS, Symbol.multiplier_value):
  every token on the board sums into a winning cascade step's multiplier and is
  swept up with the win.
- "bomb" (a Santa-hatted cartoon bomb) is the bomb symbol (Symbol.is_bomb):
  detonates its own cell plus its whole row and column, no payout of its own.
- Symbol codes match front/js/uniqorn-bad-santa/slot.js's SYMBOL_CODES and the
  PNG file names under front/img/uniqorn-bad-santa/symbols/ 1:1.
- Placeholder math throughout (reel weights, paytable tiers), inherited from
  sugar-galaxy — not RTP-tuned (and the simulator still can't run the avalanche
  mechanic, so it can't validate this game either way).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType

GAME_CODE = "uniqorn-bad-santa"
GAME_NAME = "Uniqorn Bad Santa"
CATALOG_BADGE = "Avalanche"
CATALOG_DESCRIPTION = "Новогодний каскадный слот: похмельный Санта-единорог, бомбы-хлопушки и ёлочные множители"
CATALOG_COVER_PATH = "img/uniqorn-bad-santa/img/cover.jpg"
CATALOG_PLAY_URL = "uniqorn-bad-santa.html"

NUM_REELS = 6
NUM_ROWS = 5

# Tiered count-pay paytables: key = the lowest count that tier pays at (the top
# key is open-ended, "this count or more"). See app/engine/avalanche.py:_best_tier.
_LOW_TIER_PAYS = {"8": 0.5, "10": 1, "12": 2, "15": 5}
_HIGH_TIER_PAYS = {"8": 1, "10": 2.5, "12": 5, "15": 15}
# scatter/wild/token/bomb pay nothing through a tier of their own — trigger-only,
# substitute-only or modifier-only.
_NO_PAYS: dict[str, float] = {}

# code -> (symbol_type, tier, reel_weight (same on all 6 reels), paytable, multiplier_value, is_bomb)
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None, bool]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 2, _NO_PAYS, None, False),
    ("wild", SymbolType.WILD.value, "high", 2, _NO_PAYS, None, False),
    # High pays — the party loot, one per colour (product: the tiers must read
    # apart by richness, the symbols within a tier by colour).
    ("hp_yellow", SymbolType.REGULAR.value, "high", 4, _HIGH_TIER_PAYS, None, False),
    ("hp_red", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None, False),
    ("hp_green", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None, False),
    ("hp_blue", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None, False),
    # Low pays — the same four colours, plainer art.
    ("lp_blue", SymbolType.REGULAR.value, "low", 14, _LOW_TIER_PAYS, None, False),
    ("lp_red", SymbolType.REGULAR.value, "low", 13, _LOW_TIER_PAYS, None, False),
    ("lp_green", SymbolType.REGULAR.value, "low", 12, _LOW_TIER_PAYS, None, False),
    ("lp_yellow", SymbolType.REGULAR.value, "low", 11, _LOW_TIER_PAYS, None, False),
    # Multiplier baubles — rarer the bigger the value.
    ("x2", SymbolType.BONUS.value, "low", 3, _NO_PAYS, 2, False),
    ("x3", SymbolType.BONUS.value, "low", 2, _NO_PAYS, 3, False),
    ("x5", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 5, False),
    ("x7", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 7, False),
    # The bomb — clears its row + column, pays nothing itself.
    ("bomb", SymbolType.BONUS.value, "low", 1, _NO_PAYS, None, True),
]

# Human-readable names for the paytable popup (session-start's `symbols`).
_SYMBOL_NAMES = {
    "scatter": "Scatter",
    "wild": "Bad Santa Wild",
    "hp_yellow": "Holiday Spirit",
    "hp_red": "Too Many Gifts",
    "hp_green": "Popped Champagne",
    "hp_blue": "Frozen Cocktail",
    "lp_blue": "Ice Crystal",
    "lp_red": "Candy Canes",
    "lp_green": "Pine Wreath",
    "lp_yellow": "Jingle Bell",
    "x2": "x2 Bauble",
    "x3": "x3 Bauble",
    "x5": "x5 Bauble",
    "x7": "x7 Bauble",
    "bomb": "Santa Bomb",
}

BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


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
        notes="Seed config — placeholder math cloned from sugar-galaxy, not RTP-validated.",
    )

    for order, (code, symbol_type, tier, weight, pays, multiplier_value, is_bomb) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=_SYMBOL_NAMES.get(code, code.replace("_", " ").title()),
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=pays,
            multiplier_value=multiplier_value,
            is_bomb=is_bomb,
            display_order=order,
        )

    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.AVALANCHE.value,
        enabled=True,
        params={
            # Win-multiplier trail applied per cascade step (index clamped to the
            # last entry once it runs out). Multiplier baubles add on top of this.
            "multiplier_steps": [1, 2, 3, 5],
            "max_cascades": 20,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.FREE_SPINS.value,
        enabled=True,
        params={
            "trigger_symbol_code": "scatter",
            "trigger_count": 3,
            "spins_awarded": 7,
            "retrigger_enabled": True,
            "win_multiplier": 1,
        },
        display_order=1,
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
        display_order=2,
    )

    return game, config


def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Dev convenience, same shape as sugar_galaxy.py's own _sync_from_seed:
    reconciles mutable fields on an already-seeded dev DB's rows in place,
    inserts any feature_configs or symbols the seed has gained since, but never
    removes rows."""
    _, fresh = build_game_config()

    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in config.symbols:
        f = fresh_symbols.get(symbol.code)
        if f is None:
            # Orphaned from an earlier seed revision (the pre-colour-pass symbol
            # set) — zero its weights so it can never draw again, AND empty its
            # paytable: the info popup is built from session-start's `symbols`,
            # so a retired code with pays still on it kept showing up in the
            # paytable behind a 404'd image. Spin history is left untouched.
            symbol.reel_weights = [0] * len(symbol.reel_weights)
            symbol.paytable = {}
            continue
        symbol.reel_weights = f.reel_weights
        symbol.paytable = f.paytable
        symbol.tier = f.tier
        symbol.name = f.name
        symbol.multiplier_value = f.multiplier_value
        symbol.is_bomb = f.is_bomb
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

    existing_codes = {s.code for s in config.symbols}
    for order, (code, symbol_type, tier, weight, pays, multiplier_value, is_bomb) in enumerate(_SYMBOLS):
        if code in existing_codes:
            continue
        db.add(
            Symbol(
                game_config=config,
                code=code,
                name=_SYMBOL_NAMES.get(code, code.replace("_", " ").title()),
                symbol_type=symbol_type,
                tier=tier,
                reel_weights=[weight] * NUM_REELS,
                paytable=pays,
                multiplier_value=multiplier_value,
                is_bomb=is_bomb,
                display_order=order,
            )
        )


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Idempotent: return the active config for the demo game, creating the game
    + seed config on first call (dev/test convenience, same as the other seeds)."""
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
        # This seed is the source of truth for the catalog card too (the same
        # overwrite sugar-galaxy does — backfill_catalog_fields only writes when
        # the badge is still None, so it cannot fix a half-filled row).
        game = config.game
        game.name = GAME_NAME
        game.catalog_badge = CATALOG_BADGE
        game.catalog_description = CATALOG_DESCRIPTION
        game.catalog_cover_path = CATALOG_COVER_PATH
        game.catalog_play_url = CATALOG_PLAY_URL
        await db.commit()
        return config

    _, config = build_game_config()
    db.add(config)
    await db.commit()
    return config
