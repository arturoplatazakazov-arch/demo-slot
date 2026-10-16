"""Seed data for the "gangsta-casino" game (front/gangsta-casino.html).

Art: the designer's PSB "Desk_Gangsta_Slot_OUT" (Miami/Vice: pool terrace in
the base game, neon strip club in the bonus) plus the "Элементы" symbol cuts.
Mechanics are Dirty Money / MAFIA's, one to one (product: «механика как у игры
Дёрти Мани») — app/seed/dirty_money_mafia.py: 5x3, expanding +
walking wild, scatter free spins, 3x WOF -> wheel of fortune, bonus buy x100.
The delivery is cut for exactly that mechanic set: 4 common (weapons), 4 rare
(characters), wild (small tile + reel-height art), scatter, wof.

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

_WOF_PAYS: dict[str, float] = {}
_COMMON_PAYS = {"3": 2, "4": 5, "5": 10}
_RARE_PAYS = {"3": 10, "4": 25, "5": 50}
_WILD_PAYS = {"3": 20, "4": 60, "5": 150}
_SCATTER_PAYS = {"3": 2, "4": 10, "5": 50}

# code -> (name, symbol_type, tier, reel_weight (all 5 reels), paytable, max_per_reel)
_SYMBOLS: list[tuple[str, str, str, str, int, dict, int | None]] = [
    ("scatter", "Scatter", SymbolType.SCATTER.value, "low", 3, _SCATTER_PAYS, 1),
    ("wof", "Wheel of Fortune", SymbolType.BONUS.value, "high", 3, _WOF_PAYS, 1),
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

# Clockwise from 12 o'clock — front/js/gangsta-casino/slot.js labels the drum
# from the server's list, so only the COUNT (14) is tied to the artwork.
WHEEL_SEGMENTS: list[dict] = [
    {"type": "multiplier", "value": 2, "weight": 15},
    {"type": "multiplier", "value": 5, "weight": 6},
    {"type": "multiplier", "value": 3, "weight": 11},
    {"type": "multiplier", "value": 8, "weight": 3},
    {"type": "multiplier", "value": 4, "weight": 8},
    {"type": "free_spins", "weight": 2},
    {"type": "multiplier", "value": 2, "weight": 14},
    {"type": "multiplier", "value": 6, "weight": 8},
    {"type": "multiplier", "value": 3, "weight": 11},
    {"type": "multiplier", "value": 7, "weight": 5},
    {"type": "multiplier", "value": 4, "weight": 8},
    {"type": "multiplier", "value": 5, "weight": 6},
    {"type": "free_spins", "weight": 2},
    {"type": "multiplier", "value": 10, "weight": 1},
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
        notes="Seed config — Dirty Money math, placeholder (not RTP-validated).",
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
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
        params={
            "products": [
                {"buy_id": "free_spins_buy", "cost_multiplier": 100, "target_feature_id": "free_spins"},
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
        feature_type=FeatureType.WHEEL_OF_FORTUNE.value,
        enabled=True,
        params={"trigger_symbol_code": "wof", "trigger_count": 3, "segments": WHEEL_SEGMENTS},
        display_order=3,
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
