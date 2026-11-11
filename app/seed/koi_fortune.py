"""Seed data for "koi-fortune" (working title; front/koi-fortune-*.html).

Brief: scripts/chatgpt_art/brief_asian_fortune.md — Asian / Fortune cluster,
5x3, 10 lines, koi pond + dragon, Hold & Win with 4 fixed jackpots, Free
Spins with more coins, two buys and an Ante Bet. Four art variants share
this one backend game.

- 10 fixed lines, left to right, 3..5 of a kind; WILD (dragon) substitutes
  every paying symbol, lands on reels 2-5 only, a wild-only line pays WILD;
- GONG (`scatter`, max one per reel): 3+ anywhere open 10 free spins, 3+
  inside the round add +5;
- COIN (`coin`): 6+ anywhere open Hold & Win. Base coins already show a
  plain face (coin_multiplier display_only) and lock with it
  (initial_from_base_coins); respins land plain faces or the JACKPOT COIN
  (kind mini / minor / major) — jackpot coins exist only inside the round.
  3 respins, reset by any new coin, 15/15 = GRAND on top of the coins;
- free spins run their own weight set: coins land far more often, so the
  round is mostly Hold & Win rounds (they trigger and pay inside it);
- Buy Free Spins 100x, Buy Hold & Win 60x (purchase spin without gongs,
  redrawn to 6+ coins, lines unpaid);
- Ante Bet (feature row `ante_bet`): the spin costs 1.25x the bet, wins are
  paid on the bet, base weights of gongs and coins change so both features
  trigger ~2x as often. Buys always cost the plain bet;
- max win 5 000x the bet per round (free_spins.round_max_win_multiplier).

Pays are per LINE (bet / 10). Bet steps are multiples of 20 so that both
bet / 10 and 1.25 x bet are whole cents.
RTP: scripts/koi_fortune_rtp.py (lines + Hold & Win + FS + buys + ante,
through the production feature code) — see the figures under ANTE_BET.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "koi-fortune"
GAME_NAME = "Koi Fortune"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Пруд с кои и золотой дракон: Hold & Win с четырьмя джекпотами, фриспины и Ante Bet."
CATALOG_COVER_PATH = "img/koi-fortune-silk/cover.jpg"
CATALOG_PLAY_URL = "koi-fortune-silk.html"

NUM_REELS = 5
NUM_ROWS = 3

PAYLINES: list[list[int]] = [
    [1, 1, 1, 1, 1],
    [0, 0, 0, 0, 0],
    [2, 2, 2, 2, 2],
    [0, 1, 2, 1, 0],
    [2, 1, 0, 1, 2],
    [0, 0, 1, 2, 2],
    [2, 2, 1, 0, 0],
    [1, 0, 0, 0, 1],
    [1, 2, 2, 2, 1],
    [0, 1, 1, 1, 0],
]

BET_STEPS = [20, 40, 100, 200, 400, 1000, 2000, 4000, 10000]

JACKPOT_VALUES = {"mini": 20, "minor": 50, "major": 150, "grand": 1000}

# Per-line pays (x bet / 10).
_PAYS = {
    "wild": {"3": 50.0, "4": 250.0, "5": 1000.0},
    "koi": {"3": 40.0, "4": 150.0, "5": 750.0},
    "turtle": {"3": 25.0, "4": 100.0, "5": 400.0},
    "lantern": {"3": 20.0, "4": 75.0, "5": 300.0},
    "lotus": {"3": 15.0, "4": 50.0, "5": 200.0},
    "a": {"3": 11.0, "4": 25.0, "5": 100.0},
    "k": {"3": 9.0, "4": 20.0, "5": 75.0},
    "q": {"3": 7.0, "4": 15.0, "5": 60.0},
    "j": {"3": 6.0, "4": 12.0, "5": 50.0},
    "scatter": {},
    "coin": {},
}

# code -> (name, type, tier, weight per reel). Colour code (art): lows
# A red / K blue / Q green / J purple; highs lantern red / koi blue /
# turtle green / lotus purple.
_SYMBOLS: list[tuple[str, str, str, str, list[int]]] = [
    ("j", "J", SymbolType.REGULAR.value, "low", [60, 60, 60, 60, 60]),
    ("q", "Q", SymbolType.REGULAR.value, "low", [58, 58, 58, 58, 58]),
    ("k", "K", SymbolType.REGULAR.value, "low", [54, 54, 54, 54, 54]),
    ("a", "A", SymbolType.REGULAR.value, "low", [50, 50, 50, 50, 50]),
    ("lotus", "Лотос", SymbolType.REGULAR.value, "high", [30, 30, 30, 30, 30]),
    ("lantern", "Фонарь", SymbolType.REGULAR.value, "high", [26, 26, 26, 26, 26]),
    ("turtle", "Черепаха", SymbolType.REGULAR.value, "high", [22, 22, 22, 22, 22]),
    ("koi", "Кои", SymbolType.REGULAR.value, "high", [18, 18, 18, 18, 18]),
    ("wild", "Дракон", SymbolType.WILD.value, "high", [0, 40, 40, 40, 40]),
    ("scatter", "Гонг", SymbolType.SCATTER.value, "high", [7, 7, 7, 7, 7]),
    ("coin", "Монета", SymbolType.BONUS.value, "high", [40, 40, 40, 40, 40]),
]

# Free spins weight set — only these change (coins much more often).
FS_WEIGHT_OVERRIDES = {"coin": 121}

FREE_SPINS_PARAMS = {
    "trigger_symbol_code": "scatter",
    "trigger_count": 3,
    "spins_awarded": 10,
    "retrigger_enabled": True,
    "retrigger_spins": 5,
    "win_multiplier": 1,
    "reel_weight_overrides": FS_WEIGHT_OVERRIDES,
    "round_max_win_multiplier": 5000,
}

# Base-game coin faces (x bet) — plain values only, jackpots never land here.
COIN_FACE_WEIGHTS = {"1": 200, "2": 240, "3": 200, "5": 150, "8": 90, "10": 60, "15": 30, "25": 12, "50": 3}

HOLD_AND_WIN_PARAMS = {
    "trigger_symbol_code": "coin",
    "trigger_mode": "count",
    "trigger_count": 6,
    "respin_count": 3,
    "initial_from_base_coins": True,
    # Per empty cell per respin.
    "respin_land_weights": {"blank": 932, "coin": 68},
    # Respin coins: the base faces plus the JACKPOT COIN tiers.
    "coin_value_weights": {
        **COIN_FACE_WEIGHTS,
        "mini": 55, "minor": 18, "major": 6,
    },
    "jackpot_values": JACKPOT_VALUES,
    "full_grid_jackpot": "grand",
    # Buy Hold & Win: purchase spin without gongs, redrawn to 6+ coins.
    "buy_min_coins": 6,
    "buy_exclude_symbols": ["scatter"],
    "buy_pay_lines": False,
}

COIN_MULTIPLIER_PARAMS = {
    "coin_symbol_code": "coin",
    "collector_symbol_code": "coin",
    "requires_collector": False,
    "display_only": True,
    "value_weights": COIN_FACE_WEIGHTS,
}

BUY_FREE_SPINS_COST = 100
BUY_HOLD_AND_WIN_COST = 60

# Ante Bet: spin price x1.25, these base weights instead (gong + coin).
ANTE_BET_PARAMS = {
    "cost_multiplier": 1.25,
    "weight_overrides": {"scatter": [10, 9, 9, 9, 10], "coin": [48, 47, 48, 47, 48]},
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
        notes="Asian Fortune brief. RTP: scripts/koi_fortune_rtp.py.",
    )

    for order, (code, name, symbol_type, tier, weights) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=list(weights),
            paytable=_PAYS[code],
            max_per_reel=1 if code == "scatter" else None,
            display_order=order,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config, feature_type=FeatureType.COIN_MULTIPLIER.value, enabled=True,
        params=COIN_MULTIPLIER_PARAMS, display_order=0,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.FREE_SPINS.value, enabled=True,
        params=FREE_SPINS_PARAMS, display_order=1,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.HOLD_AND_WIN.value, enabled=True,
        params=HOLD_AND_WIN_PARAMS, display_order=2,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.BONUS_BUY.value, enabled=True,
        params={
            "products": [
                {
                    "buy_id": "free_spins_buy",
                    "cost_multiplier": BUY_FREE_SPINS_COST,
                    "target_feature_id": "free_spins",
                },
                {
                    "buy_id": "hold_and_win_buy",
                    "cost_multiplier": BUY_HOLD_AND_WIN_COST,
                    "target_feature_id": "hold_and_win",
                },
            ],
        },
        display_order=3,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.ANTE_BET.value, enabled=True,
        params=ANTE_BET_PARAMS, display_order=4,
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
