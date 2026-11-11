"""Integration coverage for "koi-fortune" (Asian Fortune brief) through the API.

Pinned here: the Ante Bet (spin costs 1.25x the bet, wins on the bet,
ignored inside free spins, refused by games without it), both purchases at
the plain bet even with the ante flag on, and the Hold & Win round opening
on the base coins' plain faces (jackpot coins only ever land on respins).
"""

import pytest

from app.seed import koi_fortune as seed
from app.seed import neon_joker_spins

BET = 200
ANTE_COST = int(BET * seed.ANTE_BET_PARAMS["cost_multiplier"])


@pytest.fixture(autouse=True)
async def _seed():
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await seed.get_or_seed_active_config(db)
        await neon_joker_spins.get_or_seed_active_config(db)


async def _start(api_client, game_id: str = seed.GAME_CODE) -> dict:
    return (await api_client.post("/api/v1/session/start", json={"game_id": game_id})).json()


async def _spin(api_client, session_id, **extra):
    return await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET, **extra})


async def test_session_start_announces_the_ante_bet(api_client):
    body = await _start(api_client)
    assert body["ante_bet"] == {"cost_multiplier": 1.25}
    assert (await _start(api_client, neon_joker_spins.GAME_CODE))["ante_bet"] is None


async def test_ante_spin_costs_a_quarter_more_and_pays_on_the_bet(api_client):
    start = await _start(api_client)
    sid, balance = start["session_id"], start["balance"]
    for _ in range(30):
        body = (await _spin(api_client, sid, ante_bet=True)).json()
        in_round = body["feature"] is not None and body["feature"]["spins_remaining"] > 0
        assert body["balance"] == balance - ANTE_COST + body["total_win"]
        balance = body["balance"]
        if in_round:
            break
    body = (await _spin(api_client, sid)).json()
    if body["feature"] is None:
        assert body["balance"] == balance - BET + body["total_win"]


async def test_game_without_ante_refuses_the_flag(api_client):
    start = await _start(api_client, neon_joker_spins.GAME_CODE)
    resp = await api_client.post(
        "/api/v1/spin", json={"session_id": start["session_id"], "bet_amount": 100, "ante_bet": True}
    )
    assert resp.status_code == 400


async def test_free_spins_ignore_the_ante_flag(api_client):
    start = await _start(api_client)
    sid = start["session_id"]
    bought = (await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": sid, "feature_id": "free_spins_buy", "bet_amount": BET, "ante_bet": True},
    )).json()
    assert bought["balance"] == start["balance"] - seed.BUY_FREE_SPINS_COST * BET + bought["total_win"]
    assert bought["feature"]["spins_awarded"] == seed.FREE_SPINS_PARAMS["spins_awarded"]
    body = (await _spin(api_client, sid, ante_bet=True)).json()
    assert body["balance"] == bought["balance"] + body["total_win"]   # a free spin is never charged


async def test_hold_and_win_purchase_at_the_plain_bet_opens_on_base_faces(api_client):
    start = await _start(api_client)
    body = (await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": start["session_id"], "feature_id": "hold_and_win_buy",
              "bet_amount": BET, "ante_bet": True},
    )).json()
    cells = [code for row in body["grid"] for code in row]
    assert cells.count("coin") >= seed.HOLD_AND_WIN_PARAMS["buy_min_coins"]
    assert "scatter" not in cells
    hw = body["hold_and_win"]
    assert hw is not None
    faces = {(c["col"], c["row"], c["kind"]) for c in body["coin_multiplier"]["positions"]}
    assert {kind for *_, kind in faces} <= set(seed.COIN_FACE_WEIGHTS)
    # The round locks the very faces the player saw on the purchase spin.
    assert {(c["col"], c["row"], c["kind"]) for c in hw["initial"]} == faces
    assert body["total_win"] == hw["total_win"]           # purchase spin lines are not paid
    assert body["balance"] == start["balance"] - seed.BUY_HOLD_AND_WIN_COST * BET + body["total_win"]
