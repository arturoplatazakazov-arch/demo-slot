"""Integration coverage for the "western-treasure" game end-to-end through
POST /api/v1/spin. Механика — полный набор Empire of Crime (line-pay по 20
линиям + скаттерные фриспины + расширяющийся вайлд + bonus buy + колесо
фортуны), поэтому здесь пиннится проводка именно этого сида: его набор
символов, порог триггера фриспинов, расширение вайлда на весь барабан и то,
что три символа колеса открывают барабан призов (см.
app/seed/western_treasure.py).

Те же соглашения FakeRNG/set_rng, что в tests/test_api_spin_gangsta_city.py
(детерминированные символы через посчитанные вручную диапазоны весов).

Кумулятивные веса из сида (порядок _SYMBOLS, одинаковый на всех 5 барабанах):
scatter[0,728) wheel[728,1092) wild[1092,1182) bison[1182,1779)
mustang[1779,2227) eagle[2227,2585) wolf[2585,2883) horseshoe[2883,5031)
revolver[5031,7000) whiskey[7000,8790) dynamite[8790,10400), итого 10400 — как
у Gangsta City, из которого взята развесовка; доля под колесо вырезана
пропорционально из всех символов кроме скаттера. Сетка тянется барабан-мажорно (барабан 0 ряды 0-2,
потом барабан 1, ...), 5 барабанов x 3 ряда = 15 дро.
"""

VALID_SYMBOLS = {
    "scatter", "wheel", "wild", "bison", "mustang", "eagle", "wolf",
    "horseshoe", "revolver", "whiskey", "dynamite",
}

_RAW_SCATTER = 100
_RAW_WHEEL = 800
_RAW_WILD = 1100
_RAW_BISON = 1500
_RAW_HORSESHOE = 3000
_RAW_DYNAMITE = 9000

# Ставка обязана делиться на 20 линий (loaders.validate_bet_amount); 100 000 —
# ставка по умолчанию из BET_STEPS, ставка на линию = 5 000.
BET_AMOUNT = 100_000
START_BALANCE = 1_000_000


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "western-treasure"}
    )
    return response.json()["session_id"]


async def _seed(api_client) -> None:
    """conftest.api_client сеет только три игры явно — эту досеиваем сами, а не
    надеемся, что её оставил в общей БД предыдущий запуск дев-сервера."""
    from app.core.db import AsyncSessionLocal
    from app.seed.western_treasure import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def test_spin_response_shape_is_well_formed(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)
    set_rng([_RAW_HORSESHOE] * 15)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["grid"]) == 3
    assert all(len(row) == 5 for row in body["grid"])
    assert all(symbol in VALID_SYMBOLS for row in body["grid"] for symbol in row)
    assert body["balance"] == START_BALANCE - BET_AMOUNT + body["total_win"]
    # Ни Hold & Win, ни монеточного множителя у этой игры нет.
    assert body["hold_and_win"] is None
    assert body["coin_multiplier"] is None
    # Ни вайлда, ни символов колеса на поле нет — расширяться и открываться нечему.
    assert body["wild_events"] == []
    assert body["wheel_of_fortune"] is None


async def test_three_scatters_trigger_free_spins(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Ровно по одной звезде шерифа на барабанах 0, 2, 4 (уважает
    # max_per_reel=1, так что редроу по кэпу учитывать не нужно), остальное — динамит.
    draws = [
        _RAW_SCATTER, _RAW_DYNAMITE, _RAW_DYNAMITE,  # барабан 0
        _RAW_DYNAMITE, _RAW_DYNAMITE, _RAW_DYNAMITE,        # барабан 1
        _RAW_SCATTER, _RAW_DYNAMITE, _RAW_DYNAMITE,  # барабан 2
        _RAW_DYNAMITE, _RAW_DYNAMITE, _RAW_DYNAMITE,        # барабан 3
        _RAW_SCATTER, _RAW_DYNAMITE, _RAW_DYNAMITE,  # барабан 4
    ]
    set_rng(draws)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    assert sum(row.count("scatter") for row in body["grid"]) == 3
    assert body["feature"] is not None
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    # spins_awarded_by_count: 3 скаттера = 10 фриспинов.
    assert body["feature"]["spins_awarded"] == 10
    assert body["balance"] == START_BALANCE - BET_AMOUNT + body["total_win"]


async def test_wild_expands_over_its_whole_reel(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Вайлд падает только на барабан 2 (ряд 0), везде остальное — подкова.
    draws = [
        _RAW_HORSESHOE, _RAW_HORSESHOE, _RAW_HORSESHOE,        # барабан 0
        _RAW_HORSESHOE, _RAW_HORSESHOE, _RAW_HORSESHOE,        # барабан 1
        _RAW_WILD, _RAW_HORSESHOE, _RAW_HORSESHOE,     # барабан 2
        _RAW_HORSESHOE, _RAW_HORSESHOE, _RAW_HORSESHOE,        # барабан 3
        _RAW_HORSESHOE, _RAW_HORSESHOE, _RAW_HORSESHOE,        # барабан 4
    ]
    # expand_chance=0.5 и walk_chance=0.5 из сида — по одному weighted_pick на
    # [500, 500] каждый; raw 0 попадает в «да» оба раза (расширение, затем
    # планирование шага).
    set_rng(draws + [0, 0])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    # Барабан 2 стал вайлдом сверху донизу, поэтому каждая из 20 линий читается
    # как подкова/wild/подкова/подкова/подкова -> пятёрка подков на всех линиях (pays[5]=10,
    # ставка на линию = 100000/20 = 5000).
    assert all(row[2] == "wild" for row in body["grid"])
    assert body["wild_events"] == [{"reel": 2, "event": "expanded"}]
    assert len(body["line_wins"]) == 20
    assert body["total_win"] == 1_000_000
    assert body["balance"] == START_BALANCE - BET_AMOUNT + 1_000_000


async def test_three_wheels_open_the_wheel_of_fortune(api_client, set_rng):
    """Единственная механика, которой нет у Gangsta City: три `wheel` (тип
    BONUS, сами по себе не платят) открывают барабан призов, и приз решает
    сервер — клиент получает только индекс сектора."""
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # По одному колесу на барабанах 0, 2, 4 (max_per_reel=1), остальное — динамит.
    draws = [
        _RAW_WHEEL, _RAW_DYNAMITE, _RAW_DYNAMITE,  # барабан 0
        _RAW_DYNAMITE, _RAW_DYNAMITE, _RAW_DYNAMITE,      # барабан 1
        _RAW_WHEEL, _RAW_DYNAMITE, _RAW_DYNAMITE,  # барабан 2
        _RAW_DYNAMITE, _RAW_DYNAMITE, _RAW_DYNAMITE,      # барабан 3
        _RAW_WHEEL, _RAW_DYNAMITE, _RAW_DYNAMITE,  # барабан 4
    ]
    # Один weighted_pick по 8 каморам (сумма весов 139); raw 0 -> камора 0,
    # то есть множитель x2.
    set_rng(draws + [0])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    assert sum(row.count("wheel") for row in body["grid"]) == 3
    wheel = body["wheel_of_fortune"]
    assert wheel is not None
    assert wheel["segment_index"] == 0
    assert wheel["prize_type"] == "multiplier"
    # Множитель платит value x ВСЮ ставку, а не долю на линию.
    assert float(wheel["win_amount"]) == 2 * BET_AMOUNT
    # Клиенту уезжает ровно 8 подписей — столько камор у арта цилиндра
    # (WOF_SEGMENT_COUNT в front/js/western-treasure/slot.js).
    assert len(wheel["segments"]) == 8
    # Веса остаются на сервере: игрок не должен читать шансы с провода.
    assert all("weight" not in segment for segment in wheel["segments"])
    # Сами символы колеса ничего не платят.
    assert body["count_wins"] == []


async def test_buy_free_spins_charges_cost_and_enters_the_bonus(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # cost_multiplier=100, поэтому 10 000 * 100 = 1 000 000 списывается сразу, а
    # сам покупной спин крутится обычными барабанами (тут — весь динамит, без
    # естественного выигрыша).
    bet_amount = 10_000
    set_rng([_RAW_DYNAMITE] * 15)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": bet_amount},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feature"] is not None
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_remaining"] > 0
    assert body["balance"] == START_BALANCE - bet_amount * 100 + body["total_win"]
