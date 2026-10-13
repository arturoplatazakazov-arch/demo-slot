"""Seed data for the "tesla-spins" game (front/tesla-spins.html).

A 3x3 Hold & Win between two Tesla coils. Five lines pay a full 3-of-a-kind
(gold-of-baku family), and the LIGHTNING COIN is the bonus symbol:

- the coin lands on any reel (it never pays on a line — it breaks one);
- 3+ coins anywhere open Hold & Win (classic mode of app/features/
  hold_and_win.py): the triggering coins lock with a drawn face, every empty
  cell respins on its own, any new coin resets the 3 respins;
- a face is a bet multiplier (x1..x15) or a jackpot coin — MINI x20,
  MINOR x50, MAJOR x200; GRAND x1000 is never a face, it is paid on top of
  the coins for filling all nine cells (`full_grid_jackpot`).

The jackpot plates on screen are DOM text from JACKPOT_LADDER in
front/js/tesla-spins/slot.js, which mirrors JACKPOT_VALUES below.

RTP is checked with scripts/tesla_spins_rtp.py (lines in closed form,
Hold & Win through the real feature) — scripts/simulate.py can't see the round.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/tesla-spins/slot.js (each code == its PNG file name in
front/img/tesla-spins/symbols/) — do not rename them.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "tesla-spins"
GAME_NAME = "Tesla Spins"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Катушки Теслы, монеты-молнии и Hold & Win 3x3: множители, джекпоты MINI/MINOR/MAJOR и GRAND за все 9 ячеек."
CATALOG_COVER_PATH = "img/tesla-spins/img/cover.jpg"
CATALOG_PLAY_URL = "tesla-spins.html"

NUM_REELS = 3
NUM_ROWS = 3

# 5 lines: the three rows plus both diagonals. row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
    [0, 1, 2],
    [2, 1, 0],
]

# bet_per_line = bet / 5, so every step is a multiple of 5.
BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]

# Payout per LINE, multiplied by bet/5 — a symbol's "×N of the bet" is
# _PAYS / 5 (lemon 1.7x … seven 374x).
#
# RTP (scripts/tesla_spins_rtp.py, 2x3M spins): lines 0.605 closed form +
# Hold & Win ~0.355 (trigger 1 in 71, average round ~25x, GRAND 9/9 about
# 1 round in 245) = ~0.96.
_PAYS = {
    "lemon": {"3": 8.5},
    "cherry": {"3": 16.0},
    "plum": {"3": 21.0},
    "watermelon": {"3": 39.0},
    "bell": {"3": 89.0},
    "star": {"3": 230.0},
    "gold": {"3": 550.0},
    "seven": {"3": 1870.0},
}

# code -> (display name, tier, per-reel weight). All three reels share one set.
_SYMBOLS: list[tuple[str, str, str, int]] = [
    ("lemon", "Лимон", "low", 40),
    ("cherry", "Вишня", "low", 34),
    ("plum", "Слива", "low", 30),
    ("watermelon", "Арбуз", "low", 26),
    ("bell", "Колокол", "high", 18),
    ("star", "Звезда", "high", 12),
    ("gold", "Слиток", "high", 7),
    ("seven", "Семёрка", "high", 4),
]

COIN_CODE = "coin"
COIN_WEIGHT = 11

JACKPOT_VALUES = {"mini": 20, "minor": 50, "major": 200, "grand": 1000}

HOLD_AND_WIN_PARAMS = {
    "trigger_symbol_code": COIN_CODE,
    "trigger_count": 3,
    "respin_count": 3,
    "coin_value_weights": {
        "1": 300, "2": 250, "3": 180, "5": 120, "10": 60, "15": 35,
        "mini": 30, "minor": 12, "major": 3,
    },
    "respin_land_weights": {"blank": 95, "coin": 5},
    "jackpot_values": JACKPOT_VALUES,
    "full_grid_jackpot": "grand",
}


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for this game's v1 config."""
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
        notes="Seed config — line pay + classic Hold & Win (3+ coins), checked with scripts/tesla_spins_rtp.py.",
    )

    Symbol(
        game_config=config,
        code=COIN_CODE,
        name="Монета-молния",
        symbol_type=SymbolType.BONUS.value,
        tier="high",
        reel_weights=[COIN_WEIGHT] * NUM_REELS,
        paytable={},
        display_order=0,
    )
    for order, (code, name, tier, weight) in enumerate(_SYMBOLS, start=1):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=SymbolType.REGULAR.value,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=_PAYS[code],
            display_order=order,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.HOLD_AND_WIN.value,
        enabled=True,
        params=HOLD_AND_WIN_PARAMS,
        display_order=0,
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
