"""Seed data for the "ice-spin-deluxe" game (front/ice-spin-deluxe.html).

Fourth slot in the project's 3x3 classic family (after lucky-miami-3,
miami-fruits-3 and country-gold-3) and the same deliberately bare shape:
LINE PAY AND NOTHING ELSE. No wild, no scatter, no free spins, no bonus buy —
the config carries zero FeatureConfig rows, which app/api/v1/spin_service.py
handles natively (every feature there is guarded by
`find_feature_config(...) is not None`).

New here is the dress (frozen neon casino, art delivered as one sheet) and the
symbol count: NINE symbols instead of the family's eight, because the delivered
sheet has nine — cherry joins the fruit ladder below plum.

The maths is closed-form rather than something the simulator has to discover.
With three independent reels sharing one weight set, a payline is a 3-of-a-kind
or nothing, so

    RTP = Σ_symbol (weight / total)³ · pay          (per line, and the bet is
                                                     split evenly across lines,
                                                     so the sum IS the game RTP)

The ladder below solves that identity to 0.9555 — the same RTP as the rest of
the family. The ninth symbol costs HIT RATE, not RTP: spreading the same 187
weight over nine codes instead of eight drops a line's 3-of-a-kind chance to
2.73%, i.e. ~12.9% of spins pay something against country-gold-3's ~16%. The
compensation is a longer tail — the seven pays 1300x the bet against that
game's 1000x.

scripts/simulate.py is the check, not the search, and a single run will not
agree closely: the seven lands ~1 spin in 102k and carries 6.4% of the RTP, so
even a 1M-spin run stays noisy.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/ice-spin-deluxe/slot.js (each code == its PNG file name in
front/img/ice-spin-deluxe/symbols/) — do not rename them.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, GameConfig, Payline, Symbol
from app.models.enums import GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "ice-spin-deluxe"
GAME_NAME = "Ice Spin Deluxe"
CATALOG_BADGE = "Классика 3x3"
CATALOG_DESCRIPTION = "Ледяная классика: фрукты во льду, BAR, семёрки и пять линий — без бонусов."
CATALOG_COVER_PATH = "img/ice-spin-deluxe/img/cover.jpg"
CATALOG_PLAY_URL = "ice-spin-deluxe.html"

NUM_REELS = 3
NUM_ROWS = 3

# 5 lines: the three rows plus both diagonals — everything a 3x3 grid holds.
# row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
    [0, 1, 2],
    [2, 1, 0],
]

# bet_per_line = bet / 5, so every step is a multiple of 5 — otherwise each line
# win carries a fractional remainder the API response truncates on its way to
# `int` (loaders.validate_bet_amount enforces the divisibility).
BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]

# Payout per LINE, multiplied by bet/5 — so a symbol's headline "×N of the bet"
# is _PAYS / 5 (cherry 8 = 1.6x the bet, seven 6500 = 1300x, the top win).
#
# Only a full 3-of-a-kind pays, and with nine symbols that is ~13% of spins, so
# the average winning spin has to be worth ~7x the bet for the game to return
# anything at all. The weights are deliberately skewed (cherry 11x commoner than
# seven) rather than flat — a flat reel would drop the hit rate to ~5.5% and
# make the game feel dead between wins.
_PAYS = {
    "cherry": {"3": 8.0},
    "plum": {"3": 16.0},
    "lemon": {"3": 28.0},
    "orange": {"3": 50.0},
    "grape": {"3": 95.0},
    "bell": {"3": 290.0},
    "star": {"3": 780.0},
    "bar": {"3": 2200.0},
    "seven": {"3": 6500.0},
}

# code -> (display name, tier, per-reel weight). All three reels share one weight
# set: on a classic fruit machine the reels are interchangeable, and it keeps the
# RTP identity above exact.
_SYMBOLS: list[tuple[str, str, str, int]] = [
    ("cherry", "Вишня", "low", 44),
    ("plum", "Слива", "low", 35),
    ("lemon", "Лимон", "low", 29),
    ("orange", "Апельсин", "low", 24),
    ("grape", "Ледяной виноград", "low", 20),
    ("bell", "Колокольчики", "high", 14),
    ("star", "Звёзды", "high", 10),
    ("bar", "BAR", "high", 7),
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
