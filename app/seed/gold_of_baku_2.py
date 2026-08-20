"""Seed data for the "gold-of-baku-2" game (front/gold-of-baku-2.html).

A RESKIN of gold-of-baku (app/seed/gold_of_baku.py): same 3x3 classic family,
same seven symbol codes, same weights and same pays — only the art differs (a
blue dress instead of the gold one). Keep the two in sync when the maths moves;
the codes below are also the file names in front/img/gold-of-baku-2/symbols/.

Same deliberately bare shape as the rest of the family: LINE PAY AND NOTHING
ELSE. No wild, no scatter, no free spins, no bonus buy — the config carries
zero FeatureConfig rows, which app/api/v1/spin_service.py handles natively
(every feature there is guarded by `find_feature_config(...) is not None`).

The dress is azerbaijani night (Baku skyline, carpet floor, an ornament frame)
and the symbol count is SEVEN, the shortest ladder in the family, because the
delivered art has seven — tea glasses and pomegranate join the fruit ladder,
cherry/plum/lemon/star do not exist.

The maths is closed-form rather than something the simulator has to discover.
With three independent reels sharing one weight set, a payline is a 3-of-a-kind
or nothing, so

    RTP = Σ_symbol (weight / total)³ · pay          (per line, and the bet is
                                                     split evenly across lines,
                                                     so the sum IS the game RTP)

The ladder below solves that identity to 0.9555 — the same RTP as the rest of
the family. What seven symbols buy is HIT RATE: the same 144 weight over seven
codes gives a line a 4.21% chance of a 3-of-a-kind, i.e. ~19.0% of spins pay
something, against ice-spin-deluxe's ~12.9%. The price is a shorter tail — the
seven pays 900x the bet against that game's 1300x.

The bar's per-line 852 is deliberately not a round 850: it is the value that
lands the identity on 0.9555 with every other pay left round.

scripts/simulate.py is the check, not the search, and a single run will not
agree closely: the seven lands ~1 spin in 43k and carries 10% of the RTP.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/gold-of-baku-2/slot.js (each code == its PNG file name in
front/img/gold-of-baku-2/symbols/) — do not rename them.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, GameConfig, Payline, Symbol
from app.models.enums import GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "gold-of-baku-2"
GAME_NAME = "Gold of Baku 2"
CATALOG_BADGE = "Классика 3x3"
CATALOG_DESCRIPTION = "Восточная классика: гранат, чай-армуды, BAR и семёрки на пяти линиях — без бонусов."
CATALOG_COVER_PATH = "img/gold-of-baku-2/img/cover.jpg"
CATALOG_PLAY_URL = "gold-of-baku-2.html"

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
# is _PAYS / 5 (orange 7 = 1.4x the bet, seven 4500 = 900x, the top win).
#
# Only a full 3-of-a-kind pays. The weights are skewed (orange 10x commoner than
# seven) rather than flat: a flat reel would pay the same RTP but flatten the
# ladder into seven equal 2x symbols, and the game would have no top prize.
_PAYS = {
    "orange": {"3": 7.0},
    "grape": {"3": 13.0},
    "pomegranate": {"3": 24.0},
    "tea": {"3": 52.0},
    "bell": {"3": 152.0},
    "bar": {"3": 852.0},
    "seven": {"3": 4500.0},
}

# code -> (display name, tier, per-reel weight). All three reels share one weight
# set: on a classic fruit machine the reels are interchangeable, and it keeps the
# RTP identity above exact.
_SYMBOLS: list[tuple[str, str, str, int]] = [
    ("orange", "Апельсин", "low", 40),
    ("grape", "Виноград", "low", 32),
    ("pomegranate", "Гранат", "low", 26),
    ("tea", "Чай армуды", "high", 20),
    ("bell", "Колокольчики", "high", 14),
    ("bar", "BAR", "high", 8),
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
