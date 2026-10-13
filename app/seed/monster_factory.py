"""Seed data for the "monster-factory" demo game (front/monster-factory.html
— "Monster Factory", a fluffy-monster factory avalanche slot; theme brief from
the Cre8Pics "Beast Builders" concept, all art our own ChatGPT generation).

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
- "bomb" (a hazard-striped furry monster bomb) is the bomb symbol (Symbol.is_bomb):
  detonates its own cell plus its whole row and column, no payout of its own.
- Symbol codes match front/js/monster-factory/slot.js's SYMBOL_CODES and the
  PNG file names under front/img/monster-factory/symbols/ 1:1.
- Placeholder math throughout (reel weights, paytable tiers), inherited from
  sugar-galaxy — not RTP-tuned (and the simulator still can't run the avalanche
  mechanic, so it can't validate this game either way).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "monster-factory"
GAME_NAME = "Monster Factory"
CATALOG_BADGE = "Avalanche"
CATALOG_DESCRIPTION = "Каскадный слот на фабрике пушистых монстров: бомбы-монстры, колбы-множители и фриспины в лаборатории"
CATALOG_COVER_PATH = "img/monster-factory/img/cover.jpg"
CATALOG_PLAY_URL = "monster-factory.html"

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
    # High pays — the four monsters, one per colour.
    ("hp_yellow", SymbolType.REGULAR.value, "high", 4, _HIGH_TIER_PAYS, None, False),
    ("hp_red", SymbolType.REGULAR.value, "high", 5, _HIGH_TIER_PAYS, None, False),
    ("hp_green", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None, False),
    ("hp_blue", SymbolType.REGULAR.value, "high", 6, _HIGH_TIER_PAYS, None, False),
    # Low pays — furry J/Q/K/A in the same four colours.
    ("lp_blue", SymbolType.REGULAR.value, "low", 14, _LOW_TIER_PAYS, None, False),
    ("lp_red", SymbolType.REGULAR.value, "low", 13, _LOW_TIER_PAYS, None, False),
    ("lp_green", SymbolType.REGULAR.value, "low", 12, _LOW_TIER_PAYS, None, False),
    ("lp_yellow", SymbolType.REGULAR.value, "low", 11, _LOW_TIER_PAYS, None, False),
    # Multiplier goo cores — rarer the bigger the value.
    ("x2", SymbolType.BONUS.value, "low", 3, _NO_PAYS, 2, False),
    ("x3", SymbolType.BONUS.value, "low", 2, _NO_PAYS, 3, False),
    ("x5", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 5, False),
    ("x7", SymbolType.BONUS.value, "low", 1, _NO_PAYS, 7, False),
    # The bomb — clears its row + column, pays nothing itself.
    ("bomb", SymbolType.BONUS.value, "low", 1, _NO_PAYS, None, True),
]

# Human-readable names for the paytable popup (session-start's `symbols`).
_SYMBOL_NAMES = {
    "scatter": "Potion Rack",
    "wild": "Monster Vat Wild",
    "hp_yellow": "Sparky",
    "hp_red": "Cyclops Boss",
    "hp_green": "Sleepy Gloop",
    "hp_blue": "Doc Horns",
    "lp_blue": "K",
    "lp_red": "J",
    "lp_green": "Q",
    "lp_yellow": "A",
    "x2": "x2 Goo Core",
    "x3": "x3 Goo Core",
    "x5": "x5 Goo Core",
    "x7": "x7 Goo Core",
    "bomb": "Monster Bomb",
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
            # last entry once it runs out). Multiplier goo cores add on top of this.
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


_CATALOG = CatalogMeta(
    badge=CATALOG_BADGE,
    description=CATALOG_DESCRIPTION,
    cover_path=CATALOG_COVER_PATH,
    play_url=CATALOG_PLAY_URL,
    force=True,
    display_name=GAME_NAME,
)


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Идемпотентный сид этой игры — вся логика в app/seed/_runner.py."""
    return await get_or_seed(
        db, game_code=GAME_CODE, build_game_config=build_game_config, catalog=_CATALOG
    )
