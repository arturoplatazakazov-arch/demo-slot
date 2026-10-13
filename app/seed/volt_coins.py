"""Seed data for the "volt-coins" game (front/volt-coins.html).

Volt Coins — a 3x3 classic Hold & Win in a bank vault charged by two Tesla
coils (client art direction, Oct 2026). Symbol set strictly per the GDD:

  * WILD — the lightning "W" (deliberately NOT round: the client's feedback
    was that a round wild reads as a second coin). Substitutes for every
    paying symbol, pays nothing on its own line — see _PAYS;
  * COIN — the ONLY round symbol and the only bonus symbol. It lands in the
    base game already showing a face value (x1..x15 of the bet) or a jackpot
    tier (MINI/MINOR/MAJOR); THREE COINS IN A LINE (any of the 5 paylines)
    open Hold & Win;
  * seven / diamond / ingot / bell (high), bar / star / horseshoe (low).

Hold & Win is the feature's classic mode: every coin on the triggering grid
stays, with the face it showed in the base game (`initial_from_base_coins`);
every other cell respins on its own and can land only a coin, a jackpot coin
or nothing; any new coin resets the 3 respins, three empty respins end it.
Filling all nine cells pays GRAND on top of the coins (`full_grid_jackpot`) —
GRAND is never a coin face, it is only ever the 9/9 prize.

Jackpot ladder per the GDD: MINI x20, MINOR x50, MAJOR x250, GRAND x1000 —
at bet 10 that's exactly the 200 / 500 / 2 500 / 10 000 the client asked to
see on the plates. Plates are DOM text built from JACKPOT_LADDER in
front/js/volt-coins/slot.js, which mirrors JACKPOT_VALUES below.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/volt-coins/slot.js (each code == its PNG file name).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "volt-coins"
GAME_NAME = "Volt Coins"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Сейф под напряжением: катушки Теслы, монеты и Hold & Win 3x3 с джекпотом GRAND за 9/9."
CATALOG_COVER_PATH = "img/volt-coins/img/cover.jpg"
CATALOG_PLAY_URL = "volt-coins.html"

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

# bet / 5 lines must stay a whole number, and every pay below is a whole
# number of line bets, so no step loses a remainder on the way to `int`.
# 10 is the step the client's mockup values were written for (front picks it
# as the opening bet).
BET_STEPS = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]

JACKPOT_VALUES = {"mini": 20, "minor": 50, "major": 250, "grand": 1000}

# Per LINE (x bet/5). A 3-reel line is all-or-nothing, hence one "3" entry.
#
# Measured over 300k spins per seed (7 / 21 / 42 / 99), real spin_reels +
# evaluate_spin + coin_multiplier (faces) + hold_and_win on every drawn grid:
#   line pay        0.540 - 0.543
#   Hold & Win      0.403 - 0.417   (1 spin in ~100, average round ~41x,
#                                    GRAND 9/9 in ~2% of rounds)
#   TOTAL RTP       0.953 / 0.952 / 0.947 / 0.959  -> ~0.953, hit 16.7%
# The round is the knife edge: respin_land_weights coin 6 / 7 / 8 moved it
# 0.24 / 0.36 / 0.51 under the old anywhere-trigger. Re-measure after
# touching any weight (COIN_WEIGHT drives both the trigger and line pay).
_PAYS = {
    "horseshoe": {"3": 7},
    "star": {"3": 10},
    "bar": {"3": 13},
    "bell": {"3": 20},
    "ingot": {"3": 31},
    "diamond": {"3": 55},
    "seven": {"3": 140},
    # Three wilds on a line pay as the top symbol would.
    "wild": {"3": 150},
    # COIN never pays through the line engine — it only opens Hold & Win.
    "coin": {},
}

# P(coin in a cell) ~ 12.5%: three coins on one of the 5 lines (the trigger)
# then come up about once in ~100 spins, and coins are a constant presence on
# the reels — which is the point, every one of them shows its face value.
COIN_WEIGHT = 20

# Coin faces, base game AND round (the base face is the one the coin locks
# with). GRAND is never a face — it is only the 9/9 prize.
COIN_FACE_WEIGHTS = {
    "1": 300, "2": 230, "3": 150, "5": 90, "10": 40, "15": 20,
    "mini": 14, "minor": 5, "major": 1,
}

# code -> (display name, symbol type, tier, weight per reel)
_SYMBOLS: list[tuple[str, str, str, str, int]] = [
    ("horseshoe", "Подкова", SymbolType.REGULAR.value, "low", 30),
    ("star", "Звезда", SymbolType.REGULAR.value, "low", 27),
    ("bar", "BAR", SymbolType.REGULAR.value, "low", 24),
    ("bell", "Колокол", SymbolType.REGULAR.value, "high", 19),
    ("ingot", "Слиток", SymbolType.REGULAR.value, "high", 15),
    ("diamond", "Бриллиант", SymbolType.REGULAR.value, "high", 10),
    ("seven", "Семёрка", SymbolType.REGULAR.value, "high", 7),
    ("wild", "Wild", SymbolType.WILD.value, "special", 6),
    # P(coin in a cell) = 8/146 ~ 5.5% -> 3+ of nine ~ 1 spin in 85.
    ("coin", "Монета", SymbolType.BONUS.value, "special", COIN_WEIGHT),
]

# What a bought Hold & Win costs, in bets. The purchase spin lands its own
# coin line in the middle row (buy_coin_line) plus whatever other coins it
# draws, so a bought round is worth ~39x the bet including that spin's line
# pay (60k bought rounds x2 seeds: 39.7 / 38.3) — sold at the game's own RTP
# -> 40x. Mirrors BUY_BONUS_COST_MULTIPLIER
# in front/js/volt-coins/app.js (display only; the server charges this).
BONUS_BUY_COST_MULTIPLIER = 40


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
        notes=(
            "Seed config — hand-tuned 3x3 classic Hold & Win, 3 coins in a line trigger; measured "
            "RTP ~0.953 (lines 0.54 + Hold & Win 0.41), hit 16.7%, round 1 in ~100, GRAND only for 9/9."
        ),
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

    # Coins land in the base game already showing a face value or jackpot tier
    # (product). display_only: the faces never multiply a line — they are what
    # the coins lock with if three of them line up.
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.COIN_MULTIPLIER.value,
        enabled=True,
        params={
            "coin_symbol_code": "coin",
            "collector_symbol_code": "coin",
            "requires_collector": False,
            "display_only": True,
            "value_weights": COIN_FACE_WEIGHTS,
            "jackpot_values": JACKPOT_VALUES,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.HOLD_AND_WIN.value,
        enabled=True,
        params={
            "trigger_symbol_code": "coin",
            # Three coins IN A LINE (any of the 5 paylines) open the round.
            "trigger_mode": "payline",
            "trigger_lines": PAYLINES,
            "trigger_count": 3,
            "respin_count": 3,
            # Every coin on the triggering grid stays (the line and any other
            # coin), each with the face it showed in the base game.
            "start_empty": False,
            "initial_from_base_coins": True,
            # Bought round: the purchase spin lands three coins in the middle
            # row (payline 1) and the round opens from that line.
            "buy_coin_line": [1, 1, 1],
            "respin_land_weights": {"blank": 93, "coin": 7},
            # GRAND is absent on purpose: it is only the 9/9 prize below.
            "coin_value_weights": COIN_FACE_WEIGHTS,
            "jackpot_values": JACKPOT_VALUES,
            "full_grid_jackpot": "grand",
        },
        display_order=1,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
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
)


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Идемпотентный сид этой игры — вся логика в app/seed/_runner.py."""
    return await get_or_seed(
        db, game_code=GAME_CODE, build_game_config=build_game_config, catalog=_CATALOG
    )
