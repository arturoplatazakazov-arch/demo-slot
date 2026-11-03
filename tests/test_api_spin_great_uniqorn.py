"""Integration coverage for the "great-uniqorn" game end-to-end through
POST /api/v1/spin. Механика — Amy's Fruit Farm (line-pay + скаттерные
фриспины + bonus buy), но вместо расширяющегося вайлда — multiplier_wild:
каждый упавший WILD разыгрывает x1/x2/x3/x5/x7/x9 и умножает свою линию
(см. app/seed/great_uniqorn.py). Пиннится проводка именно этого сида: набор
символов, порог фриспинов, отсутствие расширения и множитель x9, которого
нет у Multi Fruits Story.

Те же соглашения FakeRNG/set_rng, что в tests/test_api_spin_uniqorn_scandal.py.

Кумулятивные веса из сида (порядок _SYMBOLS, одинаковый на всех 5 барабанах):
scatter[0,728) wild[728,1007) jet[1007,1751) docs[1751,2309)
hair[2309,2774) a[2774,4913) k[4913,6866) q[6866,8726) j[8726,10400),
итого 10400. Сетка тянется барабан-мажорно (барабан 0 ряды 0-2, потом
барабан 1, ...), 5 барабанов x 3 ряда = 15 дро. После сетки — по одному
дро на каждый вайлд из таблицы множителей {"1": 50, "2": 20, "3": 13,
"5": 9, "7": 5, "9": 3}: 1:[0,50) 2:[50,70) 3:[70,83) 5:[83,92) 7:[92,97)
9:[97,100).
"""

VALID_SYMBOLS = {"scatter", "wild", "jet", "docs", "hair", "a", "k", "q", "j"}

_RAW_SCATTER = 100
_RAW_WILD = 800
_RAW_A = 3000
_RAW_K = 5000
_RAW_Q = 7000
_RAW_J = 9000

_RAW_X1 = 0
_RAW_X9 = 98

BET_AMOUNT = 55000
BET_PER_LINE = BET_AMOUNT // 11
_PAY_A3 = 2
START_BALANCE = 1_000_000

# Wild на барабане 0 в среднем ряду, «a» на барабанах 1-2 того же ряда:
# средняя линия = wild + a + a -> 3x «a». Ни одна другая из 11 линий на этой
# сетке не собирает трёх одинаковых (проверено по PAYLINES сида вручную).
_LINE_WIN_GRID = [
    _RAW_J, _RAW_WILD, _RAW_Q,  # барабан 0
    _RAW_K, _RAW_A, _RAW_J,     # барабан 1
    _RAW_Q, _RAW_A, _RAW_K,     # барабан 2
    _RAW_J, _RAW_K, _RAW_Q,     # барабан 3
    _RAW_K, _RAW_Q, _RAW_J,     # барабан 4
]


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "great-uniqorn"})
    return response.json()["session_id"]


async def _seed(api_client) -> None:
    """conftest.api_client сеет только три игры явно — эту досеиваем сами."""
    from app.core.db import AsyncSessionLocal
    from app.seed.great_uniqorn import get_or_seed_active_config

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
    assert body["hold_and_win"] is None
    assert body["coin_multiplier"] is None
    assert body["multiplier_wilds"] == []


async def test_wild_x9_multiplies_its_line_and_never_expands(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)
    set_rng([*_LINE_WIN_GRID, _RAW_X9])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["multiplier_wilds"] == [{"row": 1, "col": 0, "multiplier": 9}]
    # Расширения у этой игры нет: вайлд остался одной ячейкой.
    assert body["wild_events"] == []
    assert [row[0] for row in body["grid"]] == ["j", "wild", "q"]
    # line_wins — сырая оценка пейтейбла, множитель уходит в total_win.
    assert len(body["line_wins"]) == 1
    assert body["line_wins"][0]["amount"] == _PAY_A3 * BET_PER_LINE
    assert body["total_win"] == 9 * _PAY_A3 * BET_PER_LINE


async def test_plain_wild_pays_the_line_unmultiplied(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)
    set_rng([*_LINE_WIN_GRID, _RAW_X1])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    # x1 — полноценный исход «остался WILD»: клиенту он всё равно приходит.
    assert body["multiplier_wilds"] == [{"row": 1, "col": 0, "multiplier": 1}]
    assert body["total_win"] == _PAY_A3 * BET_PER_LINE


async def test_three_scatters_trigger_free_spins(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)
    # По одному бургеру на барабанах 0, 2, 4 (max_per_reel=1 соблюдён).
    set_rng([
        _RAW_SCATTER, _RAW_J, _RAW_J,
        _RAW_J, _RAW_J, _RAW_J,
        _RAW_SCATTER, _RAW_J, _RAW_J,
        _RAW_J, _RAW_J, _RAW_J,
        _RAW_SCATTER, _RAW_J, _RAW_J,
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["spins_remaining"] == 10
