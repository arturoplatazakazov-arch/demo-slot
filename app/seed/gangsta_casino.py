"""Seed data for the "gangsta-casino" game (front/gangsta-casino.html).

Art: the designer's PSB "Desk_Gangsta_Slot_OUT" (Miami/Vice: pool terrace in
the base game, neon strip club in the bonus) plus the "Элементы" symbol cuts.
Mechanics are Dirty Money / MAFIA's, one to one (product: «механика как у игры
Дёрти Мани») — app/seed/dirty_money_mafia.py: 5x3, expanding +
walking wild, scatter free spins, bonus buy.
The delivery is cut for exactly that mechanic set: 4 common (weapons), 4 rare
(characters), wild (small tile + reel-height art), scatter, wof.

2026-10-20 (product): no Wheel of Fortune any more — the same `wof` chip is a
MULTIPLIER symbol now (coin_multiplier, no collector): every one that lands
draws a value; in the base game a spin with a line win pays its line total x
the sum of the multipliers on screen. In free spins every landed multiplier
adds to a round multiplier (starts x1, kept to the end of the round) that
multiplies every winning spin's line pay (round_sticky). Scatter pays are
never multiplied. RTP: scripts/gangsta_casino_rtp.py.

Symbol codes == the art filenames in front/img/gangsta-casino/symbols/ and are
a fixed contract with front/js/gangsta-casino/slot.js's SYMBOL_ART.

Differences from the donor, both dictated by the art:
  * rare_purple takes rare_red's place (and its weight) — that's the purple
    girl, the same character as the wild, so she sits at the top of the tier.
  * the wheel has 14 segments, not 8: the delivered wheel art
    (Анимации/wheel_of_fortune) is a 14-sector drum. Weights are the donor's
    distribution spread over 14 slots — same ~4% free-spins share and almost
    the same expected multiplier (3.65x vs 3.57x bet).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType, WildSubtype
from app.seed._runner import CatalogMeta, get_or_seed
# Lines are Amy's Fruit Farm's 11 shapes, not Dirty Money's 20 (product,
# 2026-10-16: «линии как в Эмми, тут всего 11 линий»).
from app.seed.amys_fruit_farm import PAYLINES

GAME_CODE = "gangsta-casino"
CATALOG_BADGE = "Wheel of Fortune"
CATALOG_DESCRIPTION = "Неоновый Майами, золотые узи и колесо фортуны."
CATALOG_COVER_PATH = "img/gangsta-casino/cover.jpg"
CATALOG_PLAY_URL = "gangsta-casino.html"

# Multiplier symbol: reel weight (of ~117 per reel) and the value table.
MULTIPLIER_WEIGHT = 3
# the designer's value art (Desk_Gangsta_Slot_F.psb): x2 / x3 / x5 / x7 / x9
MULTIPLIER_VALUE_WEIGHTS: dict[str, int] = {"2": 36, "3": 25, "5": 19, "7": 12, "9": 8}

# A bought round averages ~82x the bet (scripts/gangsta_casino_rtp.py) ->
# x86 keeps the buy at ~96 %.
BUY_COST_MULTIPLIER = 86

# Free spins: the multiplier lands more often (the round multiplier is the
# point of the round).
FS_MULTIPLIER_WEIGHT = 10
FS_WEIGHT_OVERRIDES = {"wof": FS_MULTIPLIER_WEIGHT}

COIN_MULTIPLIER_PARAMS = {
    "coin_symbol_code": "wof",
    "collector_symbol_code": "wof",
    "requires_collector": False,
    "value_weights": MULTIPLIER_VALUE_WEIGHTS,
    "round_accumulate": True,
    "round_sticky": True,
}

_MULTIPLIER_PAYS: dict[str, float] = {}
# Line pays x bet per line. Dirty Money's placeholder table x2.1 — tuned with
# the multiplier (scripts/gangsta_casino_rtp.py, 1M spins: RTP ~96.2 %, base
# ~71 %, free spins ~25 %, FS ~1 in 320).
_COMMON_PAYS = {"3": 4.2, "4": 10.5, "5": 21}
_RARE_PAYS = {"3": 21, "4": 52.5, "5": 105}
_WILD_PAYS = {"3": 42, "4": 126, "5": 315}
_SCATTER_PAYS = {"3": 2, "4": 10, "5": 50}

# code -> (name, symbol_type, tier, reel_weight (all 5 reels), paytable, max_per_reel)
_SYMBOLS: list[tuple[str, str, str, str, int, dict, int | None]] = [
    ("scatter", "Scatter", SymbolType.SCATTER.value, "low", 3, _SCATTER_PAYS, 1),
    ("wof", "Multiplier", SymbolType.BONUS.value, "high", MULTIPLIER_WEIGHT, _MULTIPLIER_PAYS, 1),
    ("wild", "Wild", SymbolType.WILD.value, "high", 1, _WILD_PAYS, 1),
    ("rare_purple", "Queen", SymbolType.REGULAR.value, "high", 5, _RARE_PAYS, None),
    ("rare_yellow", "Diva", SymbolType.REGULAR.value, "high", 6, _RARE_PAYS, None),
    ("rare_blue", "Boss", SymbolType.REGULAR.value, "high", 7, _RARE_PAYS, None),
    ("rare_green", "Hustler", SymbolType.REGULAR.value, "high", 8, _RARE_PAYS, None),
    ("common_2", "Golden Uzi", SymbolType.REGULAR.value, "low", 18, _COMMON_PAYS, None),
    ("common_4", "Pink Glock", SymbolType.REGULAR.value, "low", 20, _COMMON_PAYS, None),
    ("common_3", "Knuckles", SymbolType.REGULAR.value, "low", 22, _COMMON_PAYS, None),
    ("common_1", "Bat", SymbolType.REGULAR.value, "low", 24, _COMMON_PAYS, None),
]

NUM_REELS = 5
NUM_ROWS = 3

BET_STEPS = [5500, 13750, 27500, 55000, 137500, 275000]  # кратно 11 линиям (см. PAYLINES)


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for this game's v1 config."""
    game = Game(
        code=GAME_CODE, name="Gangsta Casino",
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
        notes="Multiplier math, RTP ~96 % (scripts/gangsta_casino_rtp.py).",
    )

    for order, (code, name, symbol_type, tier, weight, pays, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=[weight] * NUM_REELS,
            paytable=pays,
            max_per_reel=max_per_reel,
            display_order=order,
            wild_subtype=WildSubtype.EXPANDING.value if code == "wild" else None,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.FREE_SPINS.value,
        enabled=True,
        params={
            "trigger_symbol_code": "scatter",
            "trigger_count": 3,
            "spins_awarded": 10,
            "spins_awarded_by_count": {"3": 10, "4": 15, "5": 20},
            "retrigger_enabled": True,
            "win_multiplier": 1,
            "reel_weight_overrides": FS_WEIGHT_OVERRIDES,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
        params={
            "products": [
                {"buy_id": "free_spins_buy", "cost_multiplier": BUY_COST_MULTIPLIER, "target_feature_id": "free_spins"},
            ],
        },
        display_order=1,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.EXPANDING_WILD.value,
        enabled=True,
        params={
            "trigger_symbol_code": "wild",
            "walk_enabled": True,
            "walk_direction": "right",
            "expand_chance": 0.5,
            "walk_chance": 0.5,
        },
        display_order=2,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.COIN_MULTIPLIER.value,
        enabled=True,
        params=COIN_MULTIPLIER_PARAMS,
        display_order=3,
    )
    # The wheel is gone (2026-10-20). sync_config_from_seed never deletes a
    # feature row the seed stops listing, so it is kept here DISABLED — that
    # is what switches it off in already-seeded databases (dev, Railway).
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.WHEEL_OF_FORTUNE.value,
        enabled=False,
        params={"trigger_symbol_code": "wof", "trigger_count": 3, "segments": []},
        display_order=4,
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
