"""Integration coverage for the "tesla-spins" game through POST /api/v1/spin —
same FakeRNG/set_rng conventions as tests/test_api_spin_gold_of_baku.py.

Pinned here: a plain 3-of-a-kind still pays its line; a coin breaks a line
(it is a BONUS symbol, not a wild); and a Hold & Win round's payout equals the
sum of its coin faces (x bet) plus GRAND when the grid fills — the exact sum
the client's TOTAL meter counts up to (playHoldAndWin in front/js/tesla-spins/
slot.js).
"""

import pytest

# Cumulative reel weights in the seed's symbol order (app/seed/tesla_spins.py:
# coin first, then _SYMBOLS): coin[0,11) lemon[11,51) cherry[51,85)
# plum[85,115) watermelon[115,141) bell[141,159) star[159,171) gold[171,178)
# seven[178,182), total 182.
_RAW_COIN = 0
_RAW_LEMON = 11
_RAW_CHERRY = 51
_RAW_PLUM = 85
_RAW_BELL = 141

BET_AMOUNT = 100000
BET_PER_LINE = BET_AMOUNT // 5
_PAY_LEMON = 8.5
_GRAND = 1000


@pytest.fixture(autouse=True)
async def _seed_tesla_spins():
    from app.core.db import AsyncSessionLocal
    from app.seed.tesla_spins import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "tesla-spins"})
    return response.json()["session_id"]


async def test_three_lemons_pay_the_middle_row(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_CHERRY, _RAW_LEMON, _RAW_BELL,   # reel 0
        _RAW_PLUM, _RAW_LEMON, _RAW_CHERRY,   # reel 1
        _RAW_BELL, _RAW_LEMON, _RAW_PLUM,     # reel 2
    ])
    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    body = response.json()

    assert [w["symbol"] for w in body["line_wins"]] == ["lemon"]
    assert body["line_wins"][0]["payline"] == 1
    assert body["total_win"] == int(BET_PER_LINE * _PAY_LEMON)
    assert body.get("hold_and_win") is None


async def test_a_coin_breaks_the_line(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_CHERRY, _RAW_LEMON, _RAW_BELL,
        _RAW_PLUM, _RAW_COIN, _RAW_CHERRY,
        _RAW_BELL, _RAW_LEMON, _RAW_PLUM,
    ])
    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    body = response.json()

    assert body["line_wins"] == []
    assert body["total_win"] == 0


@pytest.mark.parametrize("attempt", range(5))
async def test_hold_and_win_pays_the_sum_of_its_coins(api_client, attempt):
    session_id = await _start_session(api_client)
    response = await api_client.post(
        "/api/v1/dev/force-hold-and-win", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()
    hw = body["hold_and_win"]

    assert hw["triggered"] is True
    coins = hw["initial"] + [c for r in hw["respins"] for c in r["landed"]]
    assert len(hw["initial"]) >= 3
    cells = {(c["row"], c["col"]) for c in coins}
    assert len(cells) == len(coins)  # a cell locks once
    for c in coins:
        assert c["kind"] in {"1", "2", "3", "5", "10", "15", "mini", "minor", "major"}
    expected = sum(c["value"] for c in coins)
    if hw["full_grid"]:
        assert hw["full_grid_jackpot"] == "grand"
        expected += _GRAND
    assert hw["total_win"] == expected * BET_AMOUNT
