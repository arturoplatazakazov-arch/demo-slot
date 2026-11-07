"""Seed data for "sugar-blast" (front/sugar-blast-*.html, four art variants).

Client GDD-05 "Sugar Blast" v0.10 (game #5 of the Illuminator ladder, the
"modularity checkpoint"): built from existing modules only, no new game code.

- 5x3, 20 fixed lines — the GDD-03 line set (Savannah Kings);
- swirl lollipop (`wild`) on reels 2-4, substitutes everything but the
  scatter, the bomb and the wrapper, has no pay of its own;
- golden lollipop (`scatter`, max 1 per reel) pays 2x/5x/20x the bet for
  3/4/5 anywhere and opens 15/20/25 free spins; 3+ inside the round: +5;
- candy bomb (`bomb`) = coin_multiplier with no collector: every bomb draws
  x2..x100 (GDD §5.1 weights); a spin with a line win multiplies its LINE pay
  by the sum of all bombs (scatter and wheel pays are never multiplied);
- free spins = the GDD-04 accumulator (coin_multiplier.round_accumulate):
  TOTAL MULTIPLIER starts x1, only a WINNING spin's bombs add to it, and it
  multiplies only line wins of spins that have a bomb; never resets;
- golden wrapper (`wrapper`, reels 1/3/5, max 1 per reel): three open the
  Jackpot Wheel — 12 sectors (6 Mini, 3 Minor, 2 Major, 1 Grand), tier drawn
  by 60/28/10/2 %, bought spin by 76/17.5/5.5/1 %;
- three purchases (GDD §8.2): Free Spins, Super Free Spins (bomb weight 7.0,
  at least one bomb every spin), Jackpot Chance. The purchase spin pays
  nothing and shows only its own trigger (no bombs, no other feature);
- max win 10 000x the bet per round, purchases included (from the bet).

Weights = the GDD's "per position, out of ~74" table x10. The GDD's FS math
was simulated for the old "all bombs accumulate" rule; under the GDD-04
module the round pays far less, so FS / Super FS levers below were re-tuned
(GDD §10.2) and the buy prices re-calibrated to 95.5 %.

Deviations from the GDD numbers (scripts/sugar_blast_rtp.py, 4M spins +
200k buys per SKU, production engine + feature code):
- bomb weights exactly as the GDD (2.0 / 3.8 / 7.0) — bombs alone cannot
  lift the round (at 13.0 they crowd out payers, round ~46x), so the one
  extra lever is the wild on reels 2-4 inside the round: FS 13.0, Super 8.8;
- scatter 1.8 instead of 1.5: at 1.5 FS came 1 in 424, not 1 in ~275;
- RTP 95.7 % (+-1.2 at 95 % CI), FS 1 in 273, avg round 100x, avg final
  multiplier x24.7 (the GDD's x60 was the old "all bombs" rule);
- buys: Free Spins 102x (avg 97.4x, 95.5 %), Super Free Spins 170x
  (avg 162.6x, x44 final, 95.6 %), Jackpot Chance 50x (47.5x, 95.1 %).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "sugar-blast"
GAME_NAME = "Sugar Blast"
CATALOG_BADGE = "Candy Bombs"
CATALOG_DESCRIPTION = "Кондитерская фабрика: конфетные бомбы умножают линии, во фриспинах копится TOTAL MULTIPLIER, колесо-торт джекпотов."
CATALOG_COVER_PATH = "img/sugar-blast-forest/cover.jpg"
CATALOG_PLAY_URL = "sugar-blast-forest.html"

NUM_REELS = 5
NUM_ROWS = 3

# GDD-03 §4.1 (Savannah Kings), rows 1..3 -> 0..2.
PAYLINES: list[list[int]] = [
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
    [1, 0, 0, 0, 1], [1, 2, 2, 2, 1], [0, 0, 1, 2, 2], [2, 2, 1, 0, 0], [1, 0, 1, 2, 1],
    [1, 2, 1, 0, 1], [0, 1, 1, 1, 0], [2, 1, 1, 1, 2], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2],
    [1, 1, 0, 1, 1], [1, 1, 2, 1, 1], [0, 0, 2, 0, 0], [2, 2, 0, 2, 2], [0, 2, 0, 2, 0],
]

# 20 coins a bet: 0.20 .. 100.00.
BET_STEPS = [20, 40, 60, 100, 200, 400, 600, 1000, 2000, 4000, 6000, 10000]

JACKPOT_VALUES = {"mini": 20, "minor": 50, "major": 250, "grand": 1000}

# Per-line pays in coins (1 coin = bet / 20), GDD §4.1. Symbol codes are by
# ROLE (h1..h4 / l1..l4): the four art variants draw different sweets for
# the same role (cupcake / macaron / ...), colour and tier stay fixed.
_PAYS = {
    "h1": {"3": 20, "4": 90, "5": 450},    # cupcake — red
    "h2": {"3": 15, "4": 70, "5": 250},    # donut — purple
    "h3": {"3": 12, "4": 45, "5": 175},    # ice cream — blue
    "h4": {"3": 10, "4": 35, "5": 125},    # chocolate bar — green
    "l1": {"3": 5, "4": 18, "5": 70},      # red gummy
    "l2": {"3": 5, "4": 14, "5": 50},      # purple gummy
    "l3": {"3": 4, "4": 10, "5": 45},      # green gummy
    "l4": {"3": 4, "4": 9, "5": 35},       # blue gummy
    "wild": {},
    # Count pay x TOTAL bet, anywhere.
    "scatter": {"3": 2, "4": 5, "5": 20},
    "bomb": {},
    "wrapper": {},
}

BASE_BOMB = 20
SCATTER_W = 18

# code, name, type, tier, per-reel weights, max_per_reel
_SYMBOLS: list[tuple[str, str, str, str, list[int], int | None]] = [
    ("h1", "Кекс", SymbolType.REGULAR.value, "high", [40] * 5, None),
    ("h2", "Пончик", SymbolType.REGULAR.value, "high", [50] * 5, None),
    ("h3", "Мороженое", SymbolType.REGULAR.value, "high", [60] * 5, None),
    ("h4", "Шоколадный батончик", SymbolType.REGULAR.value, "high", [70] * 5, None),
    ("l1", "Красная мармеладка", SymbolType.REGULAR.value, "low", [90] * 5, None),
    ("l2", "Фиолетовая мармеладка", SymbolType.REGULAR.value, "low", [100] * 5, None),
    ("l3", "Зелёная мармеладка", SymbolType.REGULAR.value, "low", [110] * 5, None),
    ("l4", "Синяя мармеладка", SymbolType.REGULAR.value, "low", [120] * 5, None),
    ("wild", "Вихрь-леденец", SymbolType.WILD.value, "high", [0, 26, 26, 26, 0], None),
    ("scatter", "Золотой леденец", SymbolType.SCATTER.value, "high", [SCATTER_W] * 5, 1),
    ("bomb", "Конфетная бомба", SymbolType.BONUS.value, "high", [BASE_BOMB] * 5, None),
    ("wrapper", "Золотая обёртка", SymbolType.BONUS.value, "high", [26, 0, 26, 0, 26], 1),
]

# GDD §5.1, weights out of 100 x100. Mean 4.8x.
BOMB_VALUE_WEIGHTS = {
    "2": 3000, "3": 2200, "4": 1400, "5": 1200, "6": 700, "8": 500, "10": 400,
    "12": 250, "15": 150, "20": 100, "25": 50, "50": 35, "100": 15,
}

# Free-spins levers (GDD §10.2: bomb weight in FS + spin count; pays and
# bomb values are locked). FS_WILD: the wild on reels 2-4 inside the round.
FS_BOMB = 38
FS_WILD = 130
SUPER_BOMB = 70
SUPER_WILD = 88

FREE_SPINS_PARAMS = {
    "trigger_symbol_code": "scatter",
    "trigger_count": 3,
    "spins_awarded": 15,
    "spins_awarded_by_count": {"3": 15, "4": 20, "5": 25},
    "retrigger_enabled": True,
    "retrigger_spins": 5,
    "win_multiplier": 1,
    "reel_weight_overrides": {"bomb": FS_BOMB, "wild": [0, FS_WILD, FS_WILD, FS_WILD, 0]},
    # Bought Super Free Spins (free_spins_variant "super").
    "super_weight_overrides": {"bomb": SUPER_BOMB, "wild": [0, SUPER_WILD, SUPER_WILD, SUPER_WILD, 0]},
    "super_guarantee": {"symbol_code": "bomb", "min_count": 1},
    "round_max_win_multiplier": 10000,
}

COIN_MULTIPLIER_PARAMS = {
    "coin_symbol_code": "bomb",
    "collector_symbol_code": "bomb",
    "requires_collector": False,
    "value_weights": BOMB_VALUE_WEIGHTS,
    "round_accumulate": True,
}

# Drum order clockwise from 12 o'clock; each tier's share split evenly over
# its sectors (out of 1200): natural 60/28/10/2 %, bought 76/17.5/5.5/1 %.
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
    "trigger_symbol_code": "wrapper",
    "trigger_count": 3,
    "buy_weights_enabled": True,
    "segments": WHEEL_SEGMENTS,
}

FREE_SPINS_BUY_COST = 102
SUPER_FREE_SPINS_BUY_COST = 170
JACKPOT_CHANCE_BUY_COST = 50

_BUY_SPIN = {"buy_pay_spin": False, "buy_pay_lines": False}

BONUS_BUY_PARAMS = {
    "products": [
        {
            "buy_id": "free_spins_buy",
            "cost_multiplier": FREE_SPINS_BUY_COST,
            "target_feature_id": "free_spins",
            "buy_exclude_symbols": ["scatter", "wrapper", "bomb"],
            "buy_force": {"symbol": "scatter", "reels": [0, 1, 2, 3, 4], "count": 3},
            **_BUY_SPIN,
        },
        {
            "buy_id": "super_free_spins_buy",
            "cost_multiplier": SUPER_FREE_SPINS_BUY_COST,
            "target_feature_id": "free_spins",
            "free_spins_variant": "super",
            "buy_exclude_symbols": ["scatter", "wrapper", "bomb"],
            "buy_force": {"symbol": "scatter", "reels": [0, 1, 2, 3, 4], "count": 3},
            **_BUY_SPIN,
        },
        {
            "buy_id": "jackpot_chance_buy",
            "cost_multiplier": JACKPOT_CHANCE_BUY_COST,
            "target_feature_id": "wheel_of_fortune",
            "buy_exclude_symbols": ["scatter", "wrapper", "bomb"],
            "buy_force": {"symbol": "wrapper", "reels": [0, 2, 4], "count": 3},
            **_BUY_SPIN,
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
        notes="GDD-05 v0.10. RTP: scripts/sugar_blast_rtp.py.",
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
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config, feature_type=FeatureType.FREE_SPINS.value, enabled=True,
        params=FREE_SPINS_PARAMS, display_order=0,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.COIN_MULTIPLIER.value, enabled=True,
        params=COIN_MULTIPLIER_PARAMS, display_order=1,
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
