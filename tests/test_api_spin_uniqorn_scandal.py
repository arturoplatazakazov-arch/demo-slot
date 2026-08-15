"""Integration coverage for the "uniqorn-scandal" game end-to-end through
POST /api/v1/spin. Механика — Amy's Fruit Farm (line-pay + скаттерные
фриспины + расширяющийся вайлд + bonus buy), поэтому здесь пиннится проводка
именно этого сида: его набор символов, порог триггера фриспинов и то, что
вайлд расширяется на весь барабан (см. app/seed/uniqorn_scandal.py).

Те же соглашения FakeRNG/set_rng, что в tests/test_api_spin_east_discovery.py
(детерминированные символы через посчитанные вручную диапазоны весов).

Кумулятивные веса из сида (порядок _SYMBOLS, одинаковый на всех 5 барабанах):
scatter[0,728) wild[728,821) wife[821,1565) heart[1565,2123)
beer[2123,2588) a[2588,4820) k[4820,6866) q[6866,8726) j[8726,10400),
итого 10400. Сетка тянется барабан-мажорно (барабан 0 ряды 0-2, потом
барабан 1, ...), 5 барабанов x 3 ряда = 15 дро.
"""

VALID_SYMBOLS = {"scatter", "wild", "wife", "heart", "beer", "a", "k", "q", "j"}

_RAW_SCATTER = 100
_RAW_WILD = 800
_RAW_WIFE = 1000
_RAW_A = 3000
_RAW_J = 9000

BET_AMOUNT = 55000
START_BALANCE = 1_000_000


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "uniqorn-scandal"}
    )
    return response.json()["session_id"]


async def _seed(api_client) -> None:
    """conftest.api_client сеет только три игры явно — эту досеиваем сами, а не
    надеемся, что её оставил в общей БД предыдущий запуск дев-сервера."""
    from app.core.db import AsyncSessionLocal
    from app.seed.uniqorn_scandal import get_or_seed_active_config

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
    # Ни Hold & Win, ни монеточного множителя у этой игры нет.
    assert body["hold_and_win"] is None
    assert body["coin_multiplier"] is None
    # Вайлда на поле нет — расширяться нечему.
    assert body["wild_events"] == []


async def test_three_scatters_trigger_free_spins(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Ровно по одной помаде на барабанах 0, 2, 4 (уважает max_per_reel=1, так
    # что редроу по кэпу учитывать не нужно), остальное — 'j'.
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


async def test_wild_expands_over_its_whole_reel(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # Единорог-скуф падает только на барабан 2 (ряд 0), везде остальное 'a'.
    draws = [
        _RAW_A, _RAW_A, _RAW_A,        # барабан 0
        _RAW_A, _RAW_A, _RAW_A,        # барабан 1
        _RAW_WILD, _RAW_A, _RAW_A,     # барабан 2
        _RAW_A, _RAW_A, _RAW_A,        # барабан 3
        _RAW_A, _RAW_A, _RAW_A,        # барабан 4
    ]
    # expand_chance=0.5 и walk_chance=0.5 из сида — по одному weighted_pick на
    # [500, 500] каждый; raw 0 попадает в «да» оба раза (расширение, затем
    # планирование шага).
    set_rng(draws + [0, 0])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    # Барабан 2 стал вайлдом сверху донизу, поэтому каждая из 11 линий читается
    # как a/wild/a/a/a -> пятёрка 'a' на всех линиях (pays[5]=10,
    # ставка на линию = 55000/11 = 5000).
    assert all(row[2] == "wild" for row in body["grid"])
    assert body["wild_events"] == [{"reel": 2, "event": "expanded"}]
    assert len(body["line_wins"]) == 11
    assert body["total_win"] == 550_000
    assert body["balance"] == START_BALANCE - BET_AMOUNT + 550_000


async def test_buy_free_spins_charges_cost_and_enters_the_bonus(api_client, set_rng):
    await _seed(api_client)
    session_id = await _start_session(api_client)

    # cost_multiplier=100, поэтому 5500 * 100 = 550 000 списывается сразу, а
    # сам покупной спин крутится обычными барабанами (тут — все 'j', без
    # естественного выигрыша).
    bet_amount = 5500
    set_rng([_RAW_J] * 15)

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
