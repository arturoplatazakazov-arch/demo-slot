"""Seed data for the "miami-fruits-3" game (front/miami-fruits-3.html).

Классический фруктовый автомат 3x3 на 5 линий: три ряда и обе диагонали —
всё, на что хватает такой сетки. Продуктовое требование к этой сборке — «пока
просто линии», поэтому у игры НЕТ ни одной FeatureConfig вообще: ни скаттера,
ни фриспинов, ни вайлда, ни покупки бонуса. Линейная выплата — это дефолт
движка (app/engine/wins.py вызывается спин-сервисом, когда игра не объявила
avalanche), так что пустой список фич здесь не забывчивость, а конфигурация.

Механика и структура файла взяты у app/seed/uniqorn_shaolin_struggles.py (та же
3x3-сетка и те же 5 линий), но всё, что там приносило RTP помимо линий (монета
с множителем, Hold & Win, bonus buy), убрано — отсюда и совсем другая таблица
выплат: у донора линии приносили 0.36 из 0.95, здесь они обязаны принести всё.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/miami-fruits-3/slot.js (each code == its PNG file name) — do not
rename them.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, GameConfig, Payline, Symbol
from app.models.enums import GameConfigStatus, SymbolType
from app.seed._runner import CatalogMeta, get_or_seed

GAME_CODE = "miami-fruits-3"
GAME_NAME = "Miami Fruits 3"
CATALOG_BADGE = "Lines"
CATALOG_DESCRIPTION = "Неоновый закат Майами, три барабана и пять линий."
CATALOG_COVER_PATH = "img/miami-fruits-3/img/cover.jpg"
CATALOG_PLAY_URL = "miami-fruits-3.html"

NUM_REELS = 3
NUM_ROWS = 3

# 5 линий: три ряда плюс обе диагонали. Зеркалится в PAYLINES
# front/js/miami-fruits-3/slot.js — фронт читает их ради антиципации последнего
# барабана. row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
    [0, 1, 2],
    [2, 1, 0],
]

# Ставка делится поровну между 5 линиями (bet_per_line = bet / 5), поэтому
# каждый шаг кратен 5 — иначе каждая линия несла бы дробный остаток, который
# ответ API срезает по дороге в `int`.
BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]

# Выплата ЗА ЛИНИЮ, в единицах bet/5 — то есть «во сколько ставок целиком»
# превращается число в комментарии. Три барабана означают, что линия это либо
# три в ряд, либо ничего, поэтому колонка в пейтейбле одна.
#
# Позиции тянутся независимо и с одинаковыми весами на всех барабанах
# (app/engine/reels.spin_reels), так что RTP здесь берётся аналитически, а не
# подбором: RTP = sum_s (w_s / W)^3 * pay_s. При весах ниже сумма равна
# 0.9605 — и это ВСЯ отдача игры, других источников выплат в ней нет.
#
# Проверено Монте-Карло на 400k спинов (сиды 7 / 21 / 42 / 99): RTP
# 0.960 / 0.963 / 0.962 / 0.971, частота попадания 18.4%, волатильность ~4.0,
# максимум за спин 500x (три семёрки на одной линии). Разброс между сидами
# создаёт семёрка: серия либо ловит её, либо нет.
_PAYS = {
    "cherry": {"3": 15.0},    # 3x ставки
    "lemon": {"3": 20.0},     # 4x
    "plum": {"3": 30.0},      # 6x
    "grape": {"3": 50.0},     # 10x
    "bell": {"3": 100.0},     # 20x
    "bar": {"3": 220.0},      # 44x
    "star": {"3": 750.0},     # 150x
    "seven": {"3": 2500.0},   # 500x
}

# code -> (display name, tier, weight). Вес один на все три барабана: перекос
# между барабанами на 3x3 не даёт ничего, кроме несимметричных «почти
# выигрышей». Сумма ровно 1000, чтобы вес читался как промилле.
#
# Состав символов задан референс-листом продукта (вишня, лимон, слива,
# виноград, колокол, BAR, звезда, пылающие 777) — апельсина в наборе нет. Смена
# состава RTP не двигает: пары «вес -> выплата» остались те же, поменялось
# только то, какой символ на какой ступени стоит.
_SYMBOLS: list[tuple[str, str, str, int]] = [
    ("cherry", "Вишня", "low", 280),
    ("lemon", "Лимон", "low", 220),
    ("plum", "Слива", "low", 170),
    ("grape", "Виноград", "low", 130),
    ("bell", "Колокол", "high", 90),
    ("bar", "BAR", "high", 60),
    ("star", "Звезда", "high", 35),
    ("seven", "777", "high", 15),
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
        notes=(
            "Seed config — hand-tuned; analytic RTP 0.9605 (line pay only, no features at all), "
            "hit frequency 18.4%, volatility ~4.0, top win 500x. See the note on _PAYS."
        ),
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

    # Ни одной FeatureConfig — см. модуль-докстринг: в игре нет ничего, кроме
    # линий, и это её продуктовое определение, а не недоделка.

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
