"""Seed data for "savannah-kings" (front/savannah-kings.html).

Client GDD-03 "Savannah Kings" v0.11 (game #3 of the Illuminator ladder):
5x3, 20 fixed lines, safari at sunset, a lion Wild and a Jackpot Wheel.

- Lion (`wild`) lands on reels 2-4 only, substitutes everything but the
  mask and the paw, has no pay of its own;
- Sun mask (`scatter`, max 1 per reel) pays 2x/5x/20x the bet for 3/4/5
  anywhere and opens 10/15/20 free spins; 3+ inside the round add +5;
- free spins spin their own weight set — only the lion changes (FS_WILD) —
  and every lion expands over its whole reel BEFORE lines are counted;
  masks and paws it covers still count (expanding_wild.triggers_before_expand);
- Golden paw (`paw`) lands on reels 1, 3, 5 only (max 1 per reel): three
  at once open the Jackpot Wheel — base game and free spins alike;
- the wheel shows 12 sectors (6 Mini, 3 Minor, 2 Major, 1 Grand) but the
  server draws the TIER by the GDD odds (60/28/10/2 %), spread evenly over
  that tier's sectors; a bought spin uses the second set (76/17.5/5.5/1 %);
- two purchases: Free Spins (10 spins) and Jackpot Chance (one wheel spin);
  the purchase spin pays nothing and never shows the other feature's symbol;
- max win 5 000x the bet per round (free_spins.round_max_win_multiplier).

Weights are the GDD's "per position, out of ~75" table x10. The scatter is
2.1 instead of 1.7: at 1.7 free spins came 1 in ~300 spins, not the GDD's
1 in 184 (its own simulation numbers need ~2.1). FS_WILD (the GDD's lever,
§8.2) is 7.5 instead of 8.0 — that lands RTP on the 96 % target.
Measured: scripts/savannah_kings_rtp.py (production feature code).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "savannah-kings"
GAME_NAME = "Savannah Kings"
CATALOG_BADGE = "Jackpot Wheel"
CATALOG_DESCRIPTION = "Саванна на закате: лев расширяется во фриспинах, три лапы крутят колесо джекпотов."
CATALOG_COVER_PATH = "img/savannah-kings/cover.jpg"
CATALOG_PLAY_URL = "savannah-kings.html"

NUM_REELS = 5
NUM_ROWS = 3

# GDD §4.1, rows 1..3 -> 0..2.
PAYLINES: list[list[int]] = [
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
    [1, 0, 0, 0, 1], [1, 2, 2, 2, 1], [0, 0, 1, 2, 2], [2, 2, 1, 0, 0], [1, 0, 1, 2, 1],
    [1, 2, 1, 0, 1], [0, 1, 1, 1, 0], [2, 1, 1, 1, 2], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2],
    [1, 1, 0, 1, 1], [1, 1, 2, 1, 1], [0, 0, 2, 0, 0], [2, 2, 0, 2, 2], [0, 2, 0, 2, 0],
]

# 20 coins a bet: every step divides by 20 lines. 0.20 .. 100.00.
BET_STEPS = [20, 40, 60, 100, 200, 400, 600, 1000, 2000, 4000, 6000, 10000]

JACKPOT_VALUES = {"mini": 20, "minor": 50, "major": 250, "grand": 1000}

# Per-line pays in coins (1 coin = bet / 20 = one line bet), GDD §4.3.
_PAYS = {
    "elephant": {"3": 50, "4": 200, "5": 1000},
    "buffalo": {"3": 40, "4": 150, "5": 600},
    "leopard": {"3": 30, "4": 100, "5": 400},
    "zebra": {"3": 25, "4": 80, "5": 300},
    "a": {"3": 10, "4": 40, "5": 150},
    "k": {"3": 10, "4": 30, "5": 125},
    "q": {"3": 8, "4": 25, "5": 100},
    "j": {"3": 8, "4": 20, "5": 80},
    "wild": {},
    # Count pay x TOTAL bet, any position.
    "scatter": {"3": 2, "4": 5, "5": 20},
    "paw": {},
}

# code, name, type, tier, per-reel weights, max_per_reel
_SYMBOLS: list[tuple[str, str, str, str, list[int], int | None]] = [
    ("elephant", "Слон", SymbolType.REGULAR.value, "high", [40] * 5, None),
    ("buffalo", "Буйвол", SymbolType.REGULAR.value, "high", [50] * 5, None),
    ("leopard", "Леопард", SymbolType.REGULAR.value, "high", [60] * 5, None),
    ("zebra", "Зебра", SymbolType.REGULAR.value, "high", [70] * 5, None),
    ("a", "A", SymbolType.REGULAR.value, "low", [90] * 5, None),
    ("k", "K", SymbolType.REGULAR.value, "low", [100] * 5, None),
    ("q", "Q", SymbolType.REGULAR.value, "low", [110] * 5, None),
    ("j", "J", SymbolType.REGULAR.value, "low", [120] * 5, None),
    ("wild", "Лев", SymbolType.WILD.value, "high", [0, 30, 30, 30, 0], None),
    ("scatter", "Солнце-маска", SymbolType.SCATTER.value, "high", [21] * 5, 1),
    ("paw", "Золотая лапа", SymbolType.BONUS.value, "high", [26, 0, 26, 0, 26], 1),
]

FS_WILD = 75

FREE_SPINS_PARAMS = {
    "trigger_symbol_code": "scatter",
    "trigger_count": 3,
    "spins_awarded": 10,
    "spins_awarded_by_count": {"3": 10, "4": 15, "5": 20},
    "retrigger_enabled": True,
    "retrigger_spins": 5,
    "win_multiplier": 1,
    "reel_weight_overrides": {"wild": [0, FS_WILD, FS_WILD, FS_WILD, 0]},
    "round_max_win_multiplier": 5000,
}

EXPANDING_WILD_PARAMS = {
    "trigger_symbol_code": "wild",
    "walk_enabled": False,
    "free_spins_only": True,
    "triggers_before_expand": True,
}

# Drum order, clockwise from 12 o'clock (front/js/savannah-kings/slot.js
# draws the sectors from this list). Each tier's share is split evenly over
# its sectors: natural 60/28/10/2 %, bought 76/17.5/5.5/1 % (out of 1200).
_TIER_WEIGHTS = {
    "mini": (6, 720, 912),
    "minor": (3, 336, 210),
    "major": (2, 120, 66),
    "grand": (1, 24, 12),
}
_DRUM = ["grand", "mini", "minor", "mini", "major", "mini",
         "minor", "mini", "major", "mini", "minor", "mini"]
WHEEL_SEGMENTS = [
    {
        "type": "multiplier",
        "tier": tier,
        "value": JACKPOT_VALUES[tier],
        "weight": _TIER_WEIGHTS[tier][1] // _TIER_WEIGHTS[tier][0],
        "buy_weight": _TIER_WEIGHTS[tier][2] // _TIER_WEIGHTS[tier][0],
    }
    for tier in _DRUM
]

WHEEL_PARAMS = {
    "trigger_symbol_code": "paw",
    "trigger_count": 3,
    "buy_weights_enabled": True,
    "segments": WHEEL_SEGMENTS,
}

FREE_SPINS_BUY_COST = 50
JACKPOT_CHANCE_BUY_COST = 50

BONUS_BUY_PARAMS = {
    "products": [
        {
            "buy_id": "free_spins_buy",
            "cost_multiplier": FREE_SPINS_BUY_COST,
            "target_feature_id": "free_spins",
            "buy_exclude_symbols": ["paw", "scatter"],
            "buy_force": {"symbol": "scatter", "reels": [0, 1, 2, 3, 4], "count": 3},
            "buy_pay_spin": False,
        },
        {
            "buy_id": "jackpot_chance_buy",
            "cost_multiplier": JACKPOT_CHANCE_BUY_COST,
            "target_feature_id": "wheel_of_fortune",
            "buy_exclude_symbols": ["scatter", "paw"],
            "buy_force": {"symbol": "paw", "reels": [0, 2, 4], "count": 3},
            "buy_pay_spin": False,
        },
    ],
}


def build_game_config() -> tuple[Game, GameConfig]:
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
        notes="GDD-03 v0.11. RTP: scripts/savannah_kings_rtp.py.",
    )

    for order, (code, name, symbol_type, tier, weights, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=weights,
            paytable=_PAYS[code],
            max_per_reel=max_per_reel,
            display_order=order,
            wild_subtype=WildSubtype.EXPANDING.value if code == "wild" else None,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config, feature_type=FeatureType.FREE_SPINS.value, enabled=True,
        params=FREE_SPINS_PARAMS, display_order=0,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.EXPANDING_WILD.value, enabled=True,
        params=EXPANDING_WILD_PARAMS, display_order=1,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.WHEEL_OF_FORTUNE.value, enabled=True,
        params=WHEEL_PARAMS, display_order=2,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.BONUS_BUY.value, enabled=True,
        params=BONUS_BUY_PARAMS, display_order=3,
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
