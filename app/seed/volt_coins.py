"""Seed data for the "volt-coins" game (front/volt-coins.html).

Volt Coins — a 3x3 classic Hold & Win in a bank vault charged by two Tesla
coils (client art direction, Oct 2026). Symbol set strictly per the GDD:

  * WILD — the lightning "W" (deliberately NOT round: the client's feedback
    was that a round wild reads as a second coin). Substitutes for every
    paying symbol, pays nothing on its own line — see _PAYS;
  * COIN — the ONLY round symbol and the only bonus symbol. In the base game
    it lands without a face value; 3+ anywhere open Hold & Win;
  * seven / diamond / ingot / bell (high), bar / star / horseshoe (low).

Hold & Win is the feature's classic mode: the triggering coins lock with a
drawn face (x1..x15 of the bet, or a MINI/MINOR/MAJOR jackpot coin), every
empty cell respins on its own, any new coin resets the 3 respins. Filling
all nine cells pays GRAND on top of the coins (`full_grid_jackpot`) — GRAND
is never a coin face, it is only ever the 9/9 prize.

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
# Measured over 300k spins per seed (7 / 21 / 42), real spin_reels +
# evaluate_spin + hold_and_win.execute on every drawn grid:
#   line pay        0.590 - 0.601
#   Hold & Win      0.347 - 0.370   (1 spin in ~92, average round ~33x,
#                                    GRAND 9/9 in ~1.5% of rounds)
#   TOTAL RTP       0.948 / 0.956 / 0.961  -> ~0.955, hit frequency 20.6%
# The round is the knife edge: respin_land_weights coin 6 -> 0.24, 7 -> 0.36,
# 8 -> 0.51. Re-measure the whole thing after touching any weight.
_PAYS = {
    "horseshoe": {"3": 6},
    "star": {"3": 8},
    "bar": {"3": 11},
    "bell": {"3": 17},
    "ingot": {"3": 28},
    "diamond": {"3": 50},
    "seven": {"3": 125},
    # Three wilds on a line pay as the top symbol would.
    "wild": {"3": 125},
    # COIN never pays through the line engine — it only opens Hold & Win.
    "coin": {},
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
    ("coin", "Монета", SymbolType.BONUS.value, "special", 8),
]

# What a bought Hold & Win costs, in bets. A bought round runs on whatever
# coins the purchase spin itself drew (usually none), so it is worth less than
# a natural one: ~25x the bet including that spin's line pay, sold at the
# game's own RTP -> 26x. Mirrors BUY_BONUS_COST_MULTIPLIER
# in front/js/volt-coins/app.js (display only; the server charges this).
BONUS_BUY_COST_MULTIPLIER = 26


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
            "Seed config — hand-tuned 3x3 classic Hold & Win; measured RTP ~0.955 (lines 0.60 + "
            "Hold & Win 0.36), hit 20.6%, round 1 in ~92, GRAND only for 9/9."
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

    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.HOLD_AND_WIN.value,
        enabled=True,
        params={
            "trigger_symbol_code": "coin",
            "trigger_count": 3,
            "respin_count": 3,
            # The triggering coins lock as the round's first coins.
            "start_empty": False,
            "respin_land_weights": {"blank": 93, "coin": 7},
            # GRAND is absent on purpose: it is only the 9/9 prize below.
            "coin_value_weights": {
                "1": 300, "2": 230, "3": 150, "5": 90, "10": 40, "15": 20,
                "mini": 14, "minor": 5, "major": 1,
            },
            "jackpot_values": JACKPOT_VALUES,
            "full_grid_jackpot": "grand",
        },
        display_order=0,
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
        display_order=1,
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
