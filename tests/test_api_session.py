async def test_start_session_returns_expected_shape(api_client):
    response = await api_client.post("/api/v1/session/start", json={"game_id": "amys-fruit-farm"})
    assert response.status_code == 200
    body = response.json()

    assert body["balance"] == 1_000_000
    assert body["currency"] == "FUN"
    assert body["bet"] == {
        "min": 10000, "max": 500000, "step": 10000, "default": 100000,
        "steps": [10000, 25000, 50000, 100000, 250000, 500000],
    }

    assert {s["code"] for s in body["symbols"]} == {
        "scatter", "wild", "duck", "watermelon", "corn", "blueberry", "strawberry", "cow", "pear", "dog",
    }
    duck = next(s for s in body["symbols"] if s["code"] == "duck")
    assert duck["symbol_type"] == "regular"
    assert duck["paytable"] == {"3": 10, "4": 25, "5": 50}

    assert body["free_spins_trigger"] == {"trigger_symbol_code": "scatter", "trigger_count": 3}


async def test_start_session_unknown_game_is_404(api_client):
    response = await api_client.post("/api/v1/session/start", json={"game_id": "does-not-exist"})
    assert response.status_code == 404


async def test_fresh_session_state_has_no_active_feature(api_client):
    start = await api_client.post("/api/v1/session/start", json={"game_id": "amys-fruit-farm"})
    session_id = start.json()["session_id"]

    state = await api_client.get(f"/api/v1/session/{session_id}/state")
    assert state.status_code == 200
    body = state.json()
    assert body["session_id"] == session_id
    assert body["balance"] == 1_000_000
    assert body["active_feature"] is None


async def test_unknown_session_state_is_404(api_client):
    response = await api_client.get("/api/v1/session/00000000-0000-0000-0000-000000000000/state")
    assert response.status_code == 404
