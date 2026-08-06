from app.seed.amys_fruit_farm import BET_STEPS

VALID_SYMBOLS = {
    "scatter", "wild", "duck", "watermelon", "corn", "blueberry", "strawberry", "cow", "pear", "dog",
}

# Cumulative reel weights from the seed (scatter[0,3) wild[3,6) duck[6,14)
# cow[14,20) dog[20,25) watermelon[25,49) corn[49,71) blueberry[71,91)
# strawberry[91,109) pear[109,125), total 125) — used to force exact symbols
# via a deterministic FakeRNG in place of the real CSPRNG.
_RAW_DUCK = 10
_RAW_PEAR = 120
_RAW_SCATTER = 0


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "amys-fruit-farm"})
    return response.json()["session_id"]


async def test_spin_response_shape_is_well_formed(api_client):
    session_id = await _start_session(api_client)
    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": 55000}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["grid"]) == 3
    assert all(len(row) == 5 for row in body["grid"])
    assert all(symbol in VALID_SYMBOLS for row in body["grid"] for symbol in row)
    assert body["balance"] == 1_000_000 - 55_000 + body["total_win"]


async def test_spin_rejects_bet_amount_not_in_steps(api_client):
    session_id = await _start_session(api_client)
    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": 12345}
    )
    assert response.status_code == 400


async def test_spin_unknown_session_is_404(api_client):
    response = await api_client.post(
        "/api/v1/spin",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "bet_amount": BET_STEPS[0]},
    )
    assert response.status_code == 404


async def test_all_premium_symbols_trigger_epic_win_popup(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_DUCK] * 15)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": 55000}
    )
    body = response.json()

    assert all(symbol == "duck" for row in body["grid"] for symbol in row)
    assert len(body["line_wins"]) == 11
    assert all(w["symbol"] == "duck" and w["count"] == 5 and w["amount"] == 250000 for w in body["line_wins"])
    assert body["total_win"] == 2_750_000
    assert body["balance"] == 1_000_000 - 55_000 + 2_750_000
    assert body["popup"] == {"type": "epicWin", "amount": 2_750_000}
    assert body["feature"] is None


async def test_all_cheap_symbols_win_with_no_popup(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_PEAR] * 15)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": 55000}
    )
    body = response.json()

    assert all(symbol == "pear" for row in body["grid"] for symbol in row)
    assert body["total_win"] == 550_000  # 11 lines x pays[5]=10 x bet_per_line(5000)
    assert body["popup"] is None
    assert body["feature"] is None


async def test_free_spins_trigger_then_a_free_spin_does_not_charge_balance(api_client, set_rng):
    session_id = await _start_session(api_client)

    # 3 scatters on the top row (reels 0-2), pear everywhere else.
    trigger_draws = [
        _RAW_SCATTER, _RAW_PEAR, _RAW_PEAR,
        _RAW_SCATTER, _RAW_PEAR, _RAW_PEAR,
        _RAW_SCATTER, _RAW_PEAR, _RAW_PEAR,
        _RAW_PEAR, _RAW_PEAR, _RAW_PEAR,
        _RAW_PEAR, _RAW_PEAR, _RAW_PEAR,
    ]
    set_rng(trigger_draws)
    trigger_response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": 55000}
    )
    trigger_body = trigger_response.json()

    assert trigger_body["count_wins"] == [{
        "symbol": "scatter", "count": 3, "amount": 110000,
        "positions": [{"row": 0, "col": 0}, {"row": 0, "col": 1}, {"row": 0, "col": 2}],
    }]
    assert len(trigger_body["line_wins"]) == 4  # every payline that never crosses row 0 (of the 11: #1,3,7,9)
    assert trigger_body["total_win"] == 310000  # 4 x 50000 line pay + 110000 count pay
    assert trigger_body["balance"] == 1_000_000 - 55_000 + 310_000
    assert trigger_body["feature"] == {
        "type": "free_spins", "triggered": True,
        "spins_awarded": 10, "spins_remaining": 10, "total_win": 0, "multiplier": None,
    }
    # Trigger gets a bonusSpinsWin popup too (product decision), announcing
    # the bonus round — amount is the spins-awarded count, not the cash win.
    assert trigger_body["popup"] == {"type": "bonusSpinsWin", "amount": 10}

    state = await api_client.get(f"/api/v1/session/{session_id}/state")
    assert state.json()["active_feature"] == {"type": "free_spins", "spins_remaining": 10, "total_win": 0}

    # A spin during the bonus round: request bet_amount is irrelevant/ignored,
    # and balance must NOT be debited — only credited with whatever it wins.
    set_rng([_RAW_PEAR] * 15)
    free_spin_response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": 999999999}
    )
    free_body = free_spin_response.json()

    assert free_body["total_win"] == 550_000  # all 11 lines pay again
    assert free_body["balance"] == trigger_body["balance"] + 550_000  # no bet deducted
    assert free_body["feature"] == {
        "type": "free_spins", "triggered": False,
        "spins_awarded": None, "spins_remaining": 9, "total_win": 550_000, "multiplier": None,
    }
    # No (re)trigger this spin -> no bonusSpinsWin (that's not a per-spin cash
    # win popup); the plain inline win-amount display covers the 550,000.
    assert free_body["popup"] is None
