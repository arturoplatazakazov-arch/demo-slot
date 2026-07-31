"""Integration coverage for party-of-goods' bonus_buy product
(free_spins_buy), through POST /api/v1/feature/buy — mirrors
tests/test_api_feature_buy_east_discovery.py's conventions. See
tests/test_api_spin_party_of_goods.py for the cumulative reel-weight ranges
this reuses."""

_RAW_ZEUS = 4
_RAW_AFRODITA = 8
_RAW_CUPIDON = 13
_RAW_BLUE = 19
_RAW_GREEN = 33

# cost_multiplier=100, so 10000 * 100 = 1,000,000 exactly matches the
# starting balance (same pattern as the other games' bonus-buy tests).
BET_AMOUNT = 10000


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "party-of-goods"})
    return response.json()["session_id"]


async def test_buy_free_spins_charges_cost_and_awards_spins(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Purchase spin's own reels: no win (every code below its threshold) —
    # forced entry via bonus_buy doesn't depend on a natural trigger.
    fillers = [_RAW_ZEUS, _RAW_AFRODITA, _RAW_CUPIDON, _RAW_BLUE, _RAW_GREEN]
    set_rng(fillers * 6)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": BET_AMOUNT},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    # No scatters land on this forced grid, so the count-based award table
    # doesn't apply — falls back to the flat spins_awarded (10).
    assert body["feature"]["spins_awarded"] == 10
    assert body["popup"] == {"type": "buyFreeSpins", "amount": 100 * BET_AMOUNT}
    assert body["avalanche"] is not None
    assert body["avalanche"]["steps"] == []
    assert body["balance"] == 1_000_000 - 100 * BET_AMOUNT + body["total_win"]


async def test_buy_free_spins_rejects_insufficient_balance(api_client, set_rng):
    session_id = await _start_session(api_client)
    fillers = [_RAW_ZEUS, _RAW_AFRODITA, _RAW_CUPIDON, _RAW_BLUE, _RAW_GREEN]
    set_rng(fillers * 6)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": 25000},
    )
    assert response.status_code == 400
