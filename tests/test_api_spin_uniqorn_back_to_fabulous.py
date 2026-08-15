"""Integration coverage for the "uniqorn-back-to-fabulous" game end-to-end
through POST /api/v1/spin. Механика — стандартный line-pay движок плюс
скаттерные фриспины и coin_multiplier, поэтому здесь пиннится проводка именно
этого сида: его набор символов, порог триггера фриспинов и то, что эссенция
множит линейный выигрыш без отдельного коллектора (collector_symbol_code
указывает на неё же, см. app/seed/uniqorn_back_to_fabulous.py).

Те же соглашения FakeRNG/set_rng, что в tests/test_api_spin_east_discovery.py
(детерминированные символы через посчитанные вручную диапазоны весов).

Кумулятивные веса из сида (порядок _SYMBOLS, одинаковый на всех 5 барабанах):
scatter[0,826) wild[826,1198) essence[1198,1570) cauldron[1570,2314)
book[2314,2965) ball[2965,3523) hat[3523,3988) a[3988,6220) k[6220,8266)
q[8266,10126) j[10126,11800), итого 11800. Сетка тянется барабан-мажорно
(барабан 0 ряды 0-2, потом барабан 1, ...), 5 барабанов x 3 ряда = 15 дро.
"""

VALID_SYMBOLS = {
    "scatter", "wild", "essence",
    "cauldron", "book", "ball", "hat",
    "a", "k", "q", "j",
}

_RAW_SCATTER = 100
_RAW_ESSENCE = 1300
_RAW_CAULDRON = 1600
_RAW_A = 4000
_RAW_J = 11000

BET_AMOUNT = 55000
START_BALANCE = 1_000_000


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "uniqorn-back-to-fabulous"}
    )
    return response.json()["session_id"]


async def _seed(api_client) -> None:
    """conftest.api_client сеет только три игры явно — эту досеиваем сами, а не
    надеемся, что её оставил в общей БД предыдущий запуск дев-сервера."""
    from app.core.db import AsyncSessionLocal
    from app.seed.uniqorn_back_to_fabulous import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def test_spin_response_shape_is_well_formed(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)
    set_rng([_RAW_A] * 15)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["grid"]) == 3
    assert all(len(row) == 5 for row in body["grid"])
    assert all(symbol in VALID_SYMBOLS for row in body["grid"] for symbol in row)
    assert body["balance"] == START_BALANCE - BET_AMOUNT + body["total_win"]
    # Ни одной эссенции на поле — фича даже не триггерится.
    assert body["coin_multiplier"] is None
    # У этой игры нет ни расширяющегося вайлда, ни Hold & Win.
    assert body["wild_events"] == []
    assert body["hold_and_win"] is None


async def test_three_scatters_trigger_free_spins(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Ровно по одному скаттеру на барабанах 0, 2, 4 (уважает max_per_reel=1,
    # так что редроу по кэпу учитывать не нужно), остальное — 'j'.
    draws = [
        _RAW_SCATTER, _RAW_J, _RAW_J,  # барабан 0
        _RAW_J, _RAW_J, _RAW_J,        # барабан 1
        _RAW_SCATTER, _RAW_J, _RAW_J,  # барабан 2
        _RAW_J, _RAW_J, _RAW_J,        # барабан 3
        _RAW_SCATTER, _RAW_J, _RAW_J,  # барабан 4
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


async def test_essence_multiplies_a_line_win(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Одна эссенция (барабан 0, ряд 0) + 'a' на всех остальных ячейках: ряды 1
    # и 2 дают линейные выигрыши, а эссенция — свой множитель.
    draws = [
        _RAW_ESSENCE, _RAW_A, _RAW_A,  # барабан 0
        _RAW_A, _RAW_A, _RAW_A,        # барабан 1
        _RAW_A, _RAW_A, _RAW_A,        # барабан 2
        _RAW_A, _RAW_A, _RAW_A,        # барабан 3
        _RAW_A, _RAW_A, _RAW_A,        # барабан 4
    ]
    # coin_multiplier тянет один weighted_pick по семитировой таблице сида
    # ({"1":40,"2":25,"5":15,"10":10,"25":6,"50":3,"100":1}, итого 100) на
    # единственную эссенцию — raw 80 попадает в корзину "10" ([80,90)).
    set_rng(draws + [80])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    assert body["coin_multiplier"] is not None
    assert body["coin_multiplier"]["multiplier_sum"] == 10
    assert body["coin_multiplier"]["positions"] == [
        {"row": 0, "col": 0, "value": 10, "kind": "10"}
    ]
    # Коллектора у этой игры нет (эссенция гейтит сама себя), а линейный
    # выигрыш есть — значит множитель реально применился.
    assert body["coin_multiplier"]["applied"] is True

    line_total = sum(win["amount"] for win in body["line_wins"])
    assert line_total > 0
    assert body["total_win"] == line_total * 10
    assert body["balance"] == START_BALANCE - BET_AMOUNT + body["total_win"]


async def test_essence_without_a_line_win_shows_value_but_does_not_pay(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Барабан 1 целиком из эссенций — этого достаточно, чтобы ни одной
    # выигрышной линии не было в принципе: любая цепочка слева обязана пройти
    # через барабан 1, а собственного пейтейбла у эссенции нет, так что цепочка
    # длиной 3+ может состоять только из эссенций — но на барабане 2 их нет.
    # Презентация множителя всё равно приезжает (значения на эссенциях
    # рисуются всегда), но applied=False и выплаты нет.
    draws = [
        _RAW_ESSENCE, _RAW_CAULDRON, _RAW_J,        # барабан 0
        _RAW_ESSENCE, _RAW_ESSENCE, _RAW_ESSENCE,   # барабан 1
        _RAW_CAULDRON, _RAW_J, _RAW_CAULDRON,       # барабан 2
        _RAW_J, _RAW_CAULDRON, _RAW_J,              # барабан 3
        _RAW_CAULDRON, _RAW_J, _RAW_CAULDRON,       # барабан 4
    ]
    # Четыре эссенции — четыре дро значения (барабан-мажорно): 0 -> "1",
    # 40 -> "2", 65 -> "5", 80 -> "10".
    set_rng(draws + [0, 40, 65, 80])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    assert sum(win["amount"] for win in body["line_wins"]) == 0
    assert body["coin_multiplier"] is not None
    assert len(body["coin_multiplier"]["positions"]) == 4
    assert body["coin_multiplier"]["multiplier_sum"] == 18  # 1 + 2 + 5 + 10
    assert body["coin_multiplier"]["applied"] is False
    assert body["total_win"] == 0
    assert body["balance"] == START_BALANCE - BET_AMOUNT
