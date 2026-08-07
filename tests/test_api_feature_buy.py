_RAW_PEAR = 11000
_RAW_SCATTER = 0


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "amys-fruit-farm"})
    return response.json()["session_id"]


async def test_buy_free_spins_charges_cost_and_grants_the_feature(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_PEAR] * 15)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": 5500},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["popup"] == {"type": "buyFreeSpins", "amount": 550_000}  # cost = 100 x bet(5500)
    assert body["feature"] == {
        "type": "free_spins", "triggered": True,
        # No scatters land on this all-pear forced grid, so the count-based
        # award table doesn't apply — falls back to the flat spins_awarded (10).
        "spins_awarded": 10, "spins_remaining": 10, "total_win": 0, "multiplier": None,
    }
    # 1,000,000 start - 550,000 cost + this spin's own win
    assert body["balance"] == 1_000_000 - 550_000 + body["total_win"]

    state = await api_client.get(f"/api/v1/session/{session_id}/state")
    assert state.json()["active_feature"]["spins_remaining"] == 10


async def test_buy_free_spins_rejects_insufficient_balance(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_PEAR] * 15)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": 13750},
    )
    assert response.status_code == 400


async def test_buy_free_spins_rejects_unknown_feature_id(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_PEAR] * 15)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "not_a_real_product", "bet_amount": 5500},
    )
    assert response.status_code == 404


async def test_buy_free_spins_blocked_while_a_round_is_already_active(api_client, set_rng):
    session_id = await _start_session(api_client)

    trigger_draws = [
        _RAW_SCATTER, _RAW_PEAR, _RAW_PEAR,
        _RAW_SCATTER, _RAW_PEAR, _RAW_PEAR,
        _RAW_SCATTER, _RAW_PEAR, _RAW_PEAR,
        _RAW_PEAR, _RAW_PEAR, _RAW_PEAR,
        _RAW_PEAR, _RAW_PEAR, _RAW_PEAR,
    ]
    set_rng(trigger_draws)
    await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": 55000})

    set_rng([_RAW_PEAR] * 15)
    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": 5500},
    )
    assert response.status_code == 400


async def test_gamble_endpoint_is_a_documented_stub(api_client):
    response = await api_client.post("/api/v1/gamble", json={})
    assert response.status_code == 501
