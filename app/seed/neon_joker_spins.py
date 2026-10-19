"""Seed data for "neon-joker-spins" (front/neon-joker-spins.html).

Client GDD-02 "Neon Joker Spins" v0.11 (game #2 of the Illuminator ladder):
a 3x3 classic fruits & 777 slot in retro neon with a Joker mascot.

- 5 fixed lines (3 rows + 2 diagonals), 3-of-a-kind only;
- JOKER (code `scatter`) pays anywhere by count, 3..9 = 2x..200x the bet,
  and 3+ open 10 free spins; 3+ inside the round add +5 (retrigger_spins);
- the round spins its own weight set: only COIN and the JOKER differ from
  the base (free_spins.reel_weight_overrides), coins land ~2.6x as often;
- 5+ COIN open Hold & Win (base and inside free spins), 3 respins, coin
  faces 1x..25x or MINI/MINOR/MAJOR, ONE jackpot tier per round, 9/9 = GRAND;
- a COLLECTOR can land on a respin (hold_and_win.respin_collector, share q
  inside the fill roll, max 2 per round): it locks the sum of every plain
  coin on the grid, same-respin coins included, jackpots and collectors not;
- Buy Hold & Win: a purchase spin on the base weights without jokers,
  redrawn until it shows 5+ coins; its line wins are not paid;
- max win 2 500x the bet per round (free_spins.round_max_win_multiplier).

The GDD's paytable is "x total bet"; the engine pays lines per LINE (bet/5),
so every line pay below is the GDD figure x5. Base weights are the GDD's
"out of 101" table x2 (integers), FS ones the "out of 122.5" table x2.
RTP: scripts/neon_joker_spins_rtp.py (lines + scatter + H&W + FS, through
the production feature code) — see the measured figures on HOLD_AND_WIN_PARAMS.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "neon-joker-spins"
GAME_NAME = "Neon Joker Spins"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Неоновые 777 и фрукты, Джокер-скаттер, фриспины и Коллектор в Hold & Win."
CATALOG_COVER_PATH = "img/neon-joker-spins/img/cover.jpg"
CATALOG_PLAY_URL = "neon-joker-spins.html"

NUM_REELS = 3
NUM_ROWS = 3

PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
    [0, 1, 2],
    [2, 1, 0],
]

# Multiples of 5 so bet / 5 lines is always whole.
BET_STEPS = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]

JACKPOT_VALUES = {"mini": 20, "minor": 50, "major": 250, "grand": 1000}

# Per-line pays (= GDD "x total bet" x5).
_PAYS = {
    "wild": {"3": 125.0},
    "seven": {"3": 100.0},
    "bell": {"3": 60.0},
    "star": {"3": 40.0},
    "cherry": {"3": 25.0},
    "lemon": {"3": 17.5},
    "plum": {"3": 12.5},
    "grape": {"3": 10.0},
    "coin": {},
    # Count pay x TOTAL bet, any position (GDD §4.1).
    "scatter": {"3": 2.0, "4": 5.0, "5": 10.0, "6": 20.0, "7": 50.0, "8": 100.0, "9": 200.0},
}

# code -> (name, type, tier, base weight). Base = GDD x2 (sum 202).
_SYMBOLS: list[tuple[str, str, str, str, int]] = [
    ("grape", "Виноград", SymbolType.REGULAR.value, "low", 38),
    ("plum", "Слива", SymbolType.REGULAR.value, "low", 34),
    ("lemon", "Лимон", SymbolType.REGULAR.value, "low", 29),
    ("cherry", "Вишня", SymbolType.REGULAR.value, "low", 24),
    ("star", "Звезда", SymbolType.REGULAR.value, "high", 14),
    ("bell", "Колокол", SymbolType.REGULAR.value, "high", 10),
    ("seven", "Семёрка", SymbolType.REGULAR.value, "high", 8),
    ("wild", "Wild", SymbolType.WILD.value, "high", 8),
    ("scatter", "Джокер", SymbolType.SCATTER.value, "high", 9),
    ("coin", "Монета", SymbolType.BONUS.value, "high", 28),
]

# FS weight set: GDD "out of 122.5" x2 — only these two change.
FS_WEIGHT_OVERRIDES = {"coin": 74, "scatter": 6}

FREE_SPINS_PARAMS = {
    "trigger_symbol_code": "scatter",
    "trigger_count": 3,
    "spins_awarded": 10,
    "retrigger_enabled": True,
    "retrigger_spins": 5,
    "win_multiplier": 1,
    "reel_weight_overrides": FS_WEIGHT_OVERRIDES,
    "round_max_win_multiplier": 2500,
}

HOLD_AND_WIN_PARAMS = {
    "trigger_symbol_code": "coin",
    "trigger_mode": "count",
    "trigger_count": 5,
    "respin_count": 3,
    # p_fill 3.5% per empty cell per respin (GDD-01 §5).
    "respin_land_weights": {"blank": 965, "coin": 35},
    # Coin faces, x bet. One jackpot tier per round; GRAND only for 9/9.
    "coin_value_weights": {
        "1": 240, "2": 220, "3": 170, "5": 140, "10": 74, "15": 30, "25": 12,
        "mini": 16, "minor": 6, "major": 2,
    },
    "jackpot_values": JACKPOT_VALUES,
    "one_jackpot_per_round": True,
    "full_grid_jackpot": "grand",
    # q = collector / (coin + collector) of the symbols that land on a respin.
    "respin_collector": {
        "symbol_code": "collector",
        "share_weights": {"coin": 2, "collector": 1},
        "max_per_round": 2,
    },
    # Buy Hold & Win (GDD-02 §7).
    "buy_min_coins": 5,
    "buy_exclude_symbols": ["scatter"],
    "buy_pay_lines": False,
}

BONUS_BUY_COST_MULTIPLIER = 34.5


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
        notes="GDD-02 v0.11. RTP: scripts/neon_joker_spins_rtp.py.",
    )

    for order, (code, name, symbol_type, tier, weight) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=_PAYS[code],
            max_per_reel=None,
            display_order=order,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config, feature_type=FeatureType.FREE_SPINS.value, enabled=True,
        params=FREE_SPINS_PARAMS, display_order=0,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.HOLD_AND_WIN.value, enabled=True,
        params=HOLD_AND_WIN_PARAMS, display_order=1,
    )
    FeatureConfig(
        game_config=config, feature_type=FeatureType.BONUS_BUY.value, enabled=True,
        params={
            "products": [
                {
                    "buy_id": "hold_and_win_buy",
                    "cost_multiplier": BONUS_BUY_COST_MULTIPLIER,
                    "target_feature_id": "hold_and_win",
                },
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
