"""Seed data for the "golden-caravan" demo game (front/golden-caravan.html —
"Golden Caravan", an Egyptian treasure-hunt avalanche slot). Mechanically
identical to app/seed/sugar_galaxy.py / app/seed/party_of_goods.py — the repo's
avalanche/cascade engine (app/engine/avalanche.py), not line-pay — and a
near-1:1 port of the Sugar Galaxy seed, differing only in the symbol set and
catalog metadata:

- 6 reels x 5 rows (30 cells), same board as Sugar Galaxy / Party of Goods — an
  "8+ of one symbol anywhere" win rule needs a board this big to be reachable
  at reasonable odds. Grid comes straight from the slot-builder manifest
  (builder draft "golden-caravan": grid.reels=6, grid.rows=5).
- No Payline rows — count-pay by tier for every REGULAR/WILD symbol (see
  _LOW_TIER_PAYS/_HIGH_TIER_PAYS and app/engine/avalanche.py's tier-lookup
  docstring). SCATTER keeps an empty paytable (_NO_PAYS): trigger-only, never
  swept up by a cascade.
- Wild has no paytable of its own (_NO_PAYS) — it substitutes into whichever
  REGULAR symbol has the most positions on the grid (app/engine/avalanche.py:
  evaluate_cascade_wins).
- x2/x3/x5 are "multiplier token" symbols (SymbolType.BONUS, empty paytable,
  Symbol.multiplier_value set): whenever a cascade step has a win, every token
  on the board sums into that step's multiplier and is swept up with the win
  (app/engine/avalanche.py:run_avalanche).
- "bomb" is the bomb symbol (SymbolType.BONUS, empty paytable, Symbol.
  is_bomb=True): detonates every step it's on the grid, clearing its own cell
  plus its whole row and column, no payout of its own.
- Symbol codes match the uploaded Spine exports under
  front/img/golden-caravan/ 1:1 (common_blue.., rare_faraon.., scatter, wild,
  x2.., bomb). front/js/golden-caravan/slot.js's SYMBOL_FOLDERS maps them to
  those folder names (and to the Export/ static.png folders).
- Placeholder math throughout (reel weights, paytable tiers) — not RTP-tuned;
  same caveat as every other seed here.

The builder wizard already left an ACTIVE v1 config on this Game (placeholder
symbols low_a../high_a../boom + the three feature rows). get_or_seed_active_
config finds that config and _sync_from_seed reconciles it onto this file's
real symbol set (zeroing the orphan placeholders' weights so they never draw),
then overwrites the catalog fields to point at the bespoke golden-caravan.html
front instead of the generic builder player.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType

GAME_CODE = "golden-caravan"
CATALOG_BADGE = "Avalanche"
CATALOG_DESCRIPTION = "Охота за сокровищами Фараона! Не упусти свою удачу!"
CATALOG_COVER_PATH = "img/golden-caravan/logo_GoldenCaravan-hero.jpg"
CATALOG_PLAY_URL = "golden-caravan.html"

NUM_REELS = 6
NUM_ROWS = 5

# Tiered count-pay paytables: key = the lowest count that tier pays at (the
# top key is open-ended, "this count or more"). A count below the lowest key
# doesn't win at all. See app/engine/avalanche.py:_best_tier.
_LOW_TIER_PAYS = {"8": 0.5, "10": 1, "12": 2, "15": 5}
_HIGH_TIER_PAYS = {"8": 1, "10": 2.5, "12": 5, "15": 15}
# scatter/wild/multiplier-token/bomb symbols pay nothing through their own
# tier — trigger-only (scatter), substitute-only (wild), or modifier-only
# (x2/x3/x5, bomb).
_NO_PAYS: dict[str, float] = {}

# code -> (symbol_type, tier, reel_weight (same on all 6 reels), paytable, multiplier_value, is_bomb)
# Codes MUST match front/js/golden-caravan/slot.js's SYMBOL_FOLDERS keys.
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None, bool]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 2, _NO_PAYS, None, False),
    ("wild", SymbolType.WILD.value, "high", 2, _NO_PAYS, None, False),
    # High-pay treasures (rare Egyptian icons).
    ("rare_faraon", SymbolType.REGULAR.value, "high", 4, _HIGH_TIER_PAYS, None, False),
    ("rare_skorobei", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None, False),
    ("rare_snake", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None, False),
    # Low-pay gems (the four coloured commons).
    ("common_blue", SymbolType.REGULAR.value, "low", 13, _LOW_TIER_PAYS, None, False),
    ("common_green", SymbolType.REGULAR.value, "low", 13, _LOW_TIER_PAYS, None, False),
    ("common_red", SymbolType.REGULAR.value, "low", 12, _LOW_TIER_PAYS, None, False),
    ("common_yellow", SymbolType.REGULAR.value, "low", 11, _LOW_TIER_PAYS, None, False),
    # Multiplier tokens — rarer the bigger the value ("small common, big rare",
    # placeholder weights).
    ("x2", SymbolType.BONUS.value, "low", 3, _NO_PAYS, 2, False),
    ("x3", SymbolType.BONUS.value, "low", 2, _NO_PAYS, 3, False),
    ("x5", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 5, False),
    # "bomb" — detonates every step it lands, clearing its row+column, no
    # payout of its own. Kept rare — a pure "help clear the board" symbol.
    ("bomb", SymbolType.BONUS.value, "low", 1, _NO_PAYS, None, True),
]

BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Golden Caravan",
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
        notes="Seed config — placeholder math, not RTP-validated (run the simulator before trusting this).",
    )

    for order, (code, symbol_type, tier, weight, pays, multiplier_value, is_bomb) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=code.replace("_", " ").title(),
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
            # Win-multiplier trail applied per cascade step (index clamped to
            # the last entry once it runs out) — [1] would disable it.
            # Multiplier tokens (x2/x3/x5) add on top of this, per-step.
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
            # Award scales with how many scatters actually landed (initial
            # trigger and every retrigger use the same table).
            "spins_awarded_by_count": {"3": 8, "4": 10, "5": 12},
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
    """Dev convenience, same rationale/shape as sugar_galaxy.py's own
    _sync_from_seed: reconciles mutable fields on an already-seeded dev DB's
    rows in place, inserts any feature_configs or symbols the seed has gained
    since, but never removes rows."""
    _, fresh = build_game_config()

    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in config.symbols:
        f = fresh_symbols.get(symbol.code)
        if f is None:
            # Orphaned from the builder's placeholder pass (low_a../high_a../
            # boom) — zero its weights so it can never draw again, without
            # touching spin history.
            symbol.reel_weights = [0] * len(symbol.reel_weights)
            continue
        symbol.reel_weights = f.reel_weights
        symbol.paytable = f.paytable
        symbol.tier = f.tier
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
                name=code.replace("_", " ").title(),
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
    """Idempotent: return the active config for the demo game, creating the
    game + seed config on first call (dev/test convenience, same as the other
    seed modules)."""
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
        # The builder wizard left this Game with half-filled catalog fields
        # (play_url pointing at the generic builder player, play.html?slug=...).
        # This seed is the source of truth for the real game, so overwrite the
        # catalog fields to point at the bespoke golden-caravan.html front.
        game = config.game
        game.name = "Golden Caravan"
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
