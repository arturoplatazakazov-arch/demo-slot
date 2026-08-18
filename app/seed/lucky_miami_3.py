"""Seed data for the "lucky-miami-3" game (front/lucky-miami-3.html).

A deliberately bare 3x3 classic fruit machine built to a delivered reference
screenshot: eight symbols, five paylines, LINE PAY AND NOTHING ELSE. No wild,
no scatter, no free spins, no bonus buy — the config carries zero FeatureConfig
rows, which app/api/v1/spin_service.py handles natively (every feature there is
guarded by `find_feature_config(...) is not None`).

That makes the maths closed-form rather than something the simulator has to
discover. With three independent reels sharing one weight set, a payline is a
3-of-a-kind or nothing, so

    RTP = Σ_symbol (weight / total)³ · pay          (per line, and the bet is
                                                     split evenly across lines,
                                                     so the sum IS the game RTP)

_PAYS below is solved against that identity; scripts/simulate.py is the check,
not the search.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/lucky-miami-3/slot.js (each code == its PNG file name in
front/img/lucky-miami-3/symbols/) — do not rename them.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, GameConfig, Payline, Symbol
from app.models.enums import GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "lucky-miami-3"
GAME_NAME = "Lucky Miami 3"
CATALOG_BADGE = "Классика 3x3"
CATALOG_DESCRIPTION = "Неоновый Майами, фрукты и пять линий — классика без бонусов."
CATALOG_COVER_PATH = "img/lucky-miami-3/img/cover.jpg"
CATALOG_PLAY_URL = "lucky-miami-3.html"

NUM_REELS = 3
NUM_ROWS = 3

# 5 lines: the three rows plus both diagonals — everything a 3x3 grid holds,
# and the "ЛИНИИ 5" the reference screenshot prints in its bottom bar.
# row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
    [0, 1, 2],
    [2, 1, 0],
]

# bet_per_line = bet / 5, so every step is a multiple of 5 — otherwise each
# line win carries a fractional remainder the API response truncates on its way
# to `int` (loaders.validate_bet_amount enforces the divisibility).
BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]

# Payout per LINE, multiplied by bet/5 — so a symbol's headline "×N of the bet"
# is _PAYS / 5 (cherry 9 = 1.8x the bet, seven 5000 = 1000x, the top win).
#
# There is no way to soften the shape of a 3x3 line game: only a full
# 3-of-a-kind pays, which lands on ~16% of spins, so the average winning spin
# has to be worth ~6x the bet for the game to return anything at all. The
# weights below are deliberately skewed (cherry 10x commoner than seven) rather
# than flat — a flat reel would drop the hit rate to ~7.5% and make the game
# feel dead between wins.
#
# Closed form gives RTP 0.9557. scripts/simulate.py agrees within its own
# noise, and that noise is large: the seven alone lands ~1 spin in 11 600 and
# carries 9% of the RTP, so even a 1M-spin run has a standard error of ~0.012.
# Five runs (seeds 7/21/3/11/29, 5.5M spins total) came back 0.969, 0.968,
# 0.960, 0.956, 0.949 — mean 0.961. Hit frequency 15.8%, volatility "high"
# (stddev ~12), top win ~1000x the bet, bonus frequency 0 (there is no bonus).
# Re-run after touching any weight or payout, but trust the identity above over
# any single run.
_PAYS = {
    "cherry": {"3": 9.0},
    "lemon": {"3": 14.0},
    "plum": {"3": 25.0},
    "grape": {"3": 50.0},
    "watermelon": {"3": 135.0},
    "bell": {"3": 400.0},
    "bar": {"3": 1300.0},
    "seven": {"3": 5000.0},
}

# code -> (display name, tier, per-reel weight). All three reels share one
# weight set: on a classic fruit machine the reels are interchangeable, and it
# keeps the RTP identity above exact.
_SYMBOLS: list[tuple[str, str, str, int]] = [
    ("cherry", "Вишня", "low", 40),
    ("lemon", "Лимон", "low", 32),
    ("plum", "Слива", "low", 26),
    ("grape", "Виноград", "low", 21),
    ("watermelon", "Арбуз", "high", 15),
    ("bell", "Колокольчик", "high", 10),
    ("bar", "BAR", "high", 7),
    # Art is the classic triple 777 (three digits, the middle one in front);
    # the code stays singular because it is the PNG file name the front loads.
    ("seven", "777", "high", 4),
]


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
        notes="Seed config — line pay only, solved against the closed-form 3x3 RTP identity.",
    )

    for order, (code, name, tier, weight) in enumerate(_SYMBOLS):
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
