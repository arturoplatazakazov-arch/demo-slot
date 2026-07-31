"""Seed data for the "party-of-goods" demo game (front/party-of-goods.html —
branded "Party Gods" in the actual art/reference, kept as the original
internal GAME_CODE since it's already wired through tests/conftest.py). The
repo's first avalanche/cascade-mechanic game (app/engine/avalanche.py), not
line-pay. Structurally mirrors app/seed/east_discovery.py (build/sync/
get-or-seed shape), but:

- 6 reels x 5 rows (30 cells), not the other games' 5x3 — an "8+ of one
  symbol anywhere" win rule needs a bigger board to be reachable at
  reasonable odds.
- No Payline rows at all — this game has no payline concept; every REGULAR/
  WILD symbol pays by tiered count instead (see _LOW_TIER_PAYS et al. below,
  and app/engine/avalanche.py's threshold-lookup docstring for the tier
  semantics). SCATTER keeps an empty paytable (_NO_PAYS) — it only exists to
  trigger free spins, same convention as coin/collector_tiger in
  east_discovery.py, and is therefore never swept up by a cascade.
- Wild has no paytable of its own (_NO_PAYS) — it substitutes into whichever
  REGULAR symbol currently has the most positions on the grid instead
  (product, this session), so its count folds into that symbol's own tier.
  See app/engine/avalanche.py:evaluate_cascade_wins for the tie-break rule.
- x2/x3/x5/x7 are "multiplier token" symbols (SymbolType.BONUS, empty
  paytable, Symbol.multiplier_value set) — product, confirmed this session:
  they land on the grid like any other symbol and, whenever a cascade step
  has a win, every instance currently on the board sums into that step's
  multiplier and gets swept up alongside the win (see
  app/engine/avalanche.py:run_avalanche). A token that never sees a win
  before the round ends just never contributes.
- "boom" is the bomb symbol (SymbolType.BONUS, empty paytable, Symbol.
  is_bomb=True) — product, confirmed this session: it detonates every
  cascade step it's present on the grid regardless of whether anything else
  won that step, clearing its own cell plus its entire row and column, with
  no payout of its own (purely a "help clear the board" symbol).
- Placeholder math throughout (reel weights, paytable tiers, exactly like
  every other seed here) — not RTP-tuned; run the simulator
  (app/simulator/engine.py) before trusting these numbers, same as any
  other game's seed. (Also: the simulator doesn't run the avalanche
  mechanic at all yet — see app/simulator/engine.py — so it can't validate
  this game's RTP either way yet.)
- Symbol codes match the real uploaded Spine exports under
  front/img/party-of-goods/Export/ 1:1 except "yellow" (folder is "yelow",
  a typo in the delivered export — front/js/party-of-goods/slot.js's
  SYMBOL_FOLDERS maps the code to that actual folder name, same pattern
  east_discovery.py uses for lp_blue -> "lp-blue" etc).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed import backfill_catalog_fields

GAME_CODE = "party-of-goods"
CATALOG_BADGE = "Avalanche"
CATALOG_DESCRIPTION = "Каскадный слот в мире греческих богов"
CATALOG_COVER_PATH = "img/party-of-goods/img/logo_Partyofgoods-hero.jpg"
CATALOG_PLAY_URL = "party-of-goods.html"

NUM_REELS = 6
NUM_ROWS = 5

# Tiered count-pay paytables: key = the lowest count that tier pays at (the
# top key is open-ended, "this count or more"). A count below the lowest key
# doesn't win at all. See app/engine/avalanche.py:_best_tier.
_LOW_TIER_PAYS = {"8": 0.5, "10": 1, "12": 2, "15": 5}
_HIGH_TIER_PAYS = {"8": 1, "10": 2.5, "12": 5, "15": 15}
# scatter/wild/multiplier-token symbols deliberately pay nothing through their
# own tier — trigger-only (scatter), substitute-only (wild — see module
# docstring), or modifier-only (x2/x3/x5/x7), see module docstring above.
_NO_PAYS: dict[str, float] = {}

# code -> (symbol_type, tier, reel_weight (same on all 6 reels), paytable, multiplier_value, is_bomb)
_SYMBOLS: list[tuple[str, str, str, int, dict, int | None, bool]] = [
    ("scatter", SymbolType.SCATTER.value, "low", 2, _NO_PAYS, None, False),
    ("wild", SymbolType.WILD.value, "high", 2, _NO_PAYS, None, False),
    ("zeus", SymbolType.REGULAR.value, "high", 4, _HIGH_TIER_PAYS, None, False),
    ("afrodita", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None, False),
    ("cupidon", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None, False),
    ("blue", SymbolType.REGULAR.value, "low", 14, _LOW_TIER_PAYS, None, False),
    ("green", SymbolType.REGULAR.value, "low", 13, _LOW_TIER_PAYS, None, False),
    ("red", SymbolType.REGULAR.value, "low", 12, _LOW_TIER_PAYS, None, False),
    ("yellow", SymbolType.REGULAR.value, "low", 11, _LOW_TIER_PAYS, None, False),
    # Multiplier tokens — rarer the bigger the value, matching the usual
    # "small multipliers common, big ones rare" shape (placeholder weights).
    ("x2", SymbolType.BONUS.value, "low", 3, _NO_PAYS, 2, False),
    ("x3", SymbolType.BONUS.value, "low", 2, _NO_PAYS, 3, False),
    ("x5", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 5, False),
    ("x7", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 7, False),
    # "boom" — the bomb symbol (app/engine/avalanche.py): detonates every
    # step it lands, clearing its row+column, no payout of its own. Kept
    # rare — it's a pure "help clear the board" symbol, not a jackpot draw.
    ("boom", SymbolType.BONUS.value, "low", 1, _NO_PAYS, None, True),
]

BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for the demo game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Party Gods",
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
            # Win-multiplier trail applied per cascade step (index clamped
            # to the last entry once it runs out) — [1] would disable it.
            # Multiplier tokens (x2/x3/x5/x7) add on top of whatever this
            # gives, per-step (see app/engine/avalanche.py).
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
            "spins_awarded": 10,  # fallback only; the table below drives real awards
            # Standardized across all 5 games (product, this session):
            # 3 scatters -> 10 spins, 4 -> 15, 5 -> 20. Same tiering for the
            # initial trigger and any retrigger.
            "spins_awarded_by_count": {"3": 10, "4": 15, "5": 20},
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
    """Dev convenience, same rationale/shape as east_discovery.py's own
    _sync_from_seed: reconciles mutable fields on an already-seeded dev DB's
    rows in place, inserts any feature_configs the seed has gained since,
    but never removes rows."""
    _, fresh = build_game_config()

    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in config.symbols:
        f = fresh_symbols.get(symbol.code)
        if f is None:
            # Orphaned from an earlier seed revision (this game's symbol
            # codes were placeholders — cake/gift/champagne/balloon_* —
            # before the real uploaded theme replaced them entirely). Left
            # with their old non-zero reel_weights, spin_reels would keep
            # drawing them forever since it doesn't know they're
            # "deleted" — zero every reel's weight instead so they can
            # never actually land again, without touching spin history
            # that references the code.
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

    # Symbol codes changed entirely this pass (placeholder cake/gift/
    # champagne/balloon_* -> the real uploaded theme) — the loop above
    # zeroes out the old rows' weights so they stop drawing; this inserts
    # whichever brand-new codes don't have an existing row to update yet.
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
    game + seed config on first call (dev/test convenience, same as the
    other seed modules)."""
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
    return config
