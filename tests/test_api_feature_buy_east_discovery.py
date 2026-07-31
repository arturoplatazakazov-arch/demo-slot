"""Integration coverage for East Discovery's second bonus-buy product,
hold_and_win_buy — added alongside free_spins_buy under the *same*
bonus_buy FeatureConfig row's params["products"] list (a game_config can
only have one enabled row per feature_type: uq_feature_type_per_config),
resolved via bonus_buy.resolve_bonus_buy_product. See
tests/test_api_feature_buy.py for the equivalent free_spins_buy coverage
this mirrors (same FakeRNG/set_rng conventions)."""

_RAW_LP_BLUE = 30

# cost_multiplier=100, so 10000 * 100 = 1,000,000 exactly matches the
# starting balance (same pattern as test_api_feature_buy.py's free_spins_buy
# coverage) — 100000 would need a balance 10x the default starting one.
BET_AMOUNT = 10000


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "east-discovery"})
    return response.json()["session_id"]


async def test_buy_hold_and_win_charges_cost_and_resolves_instantly(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Purchase spin's own reels: all lp_blue (no natural win, no natural
    # collector_tiger trigger — this is a forced entry via bonus_buy).
    draws = [_RAW_LP_BLUE] * 15
    # Hold & Win's "guaranteed coins" mode — see
    # test_api_spin_east_discovery.py's test_three_collector_tigers_trigger_
    # hold_and_win for the full breakdown of this exact sequence: raw=80
    # always draws a count of 3, raw=0 always picks the next remaining empty
    # cell and the "0" (no-multiplier) value bucket — 5 respins of 3 fills
    # the 15-cell grid deterministically.
    set_rng(draws + [80, 0, 0, 0, 0, 0, 0] * 5)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "hold_and_win_buy", "bet_amount": BET_AMOUNT},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["hold_and_win"] is not None
    assert body["hold_and_win"]["triggered"] is True
    assert len(body["hold_and_win"]["respins"]) == 5
    assert all(len(r["landed"]) == 3 for r in body["hold_and_win"]["respins"])
    assert body["hold_and_win"]["total_win"] == 0  # every coin landed as "0" (no multiplier)
    assert body["hold_and_win"]["full_grid"] is True
    # Unlike free_spins_buy, hold_and_win resolves in this one call — no
    # FeatureOut/spins-remaining state, no bonus-buy popup of its own (the
    # frontend's own Hold & Win sequence/popup covers the "you got it" beat).
    assert body["feature"] is None
    assert body["popup"] is None
    assert body["balance"] == 1_000_000 - 100 * BET_AMOUNT + body["total_win"]


async def test_buy_hold_and_win_rejects_insufficient_balance(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_LP_BLUE] * 15)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "hold_and_win_buy", "bet_amount": 25000},
    )
    assert response.status_code == 400


async def test_free_spins_buy_still_works_alongside_hold_and_win_buy(api_client, set_rng):
    """Both bonus-buy products share one bonus_buy FeatureConfig row
    (params["products"]) — this locks in that adding hold_and_win_buy didn't
    break the pre-existing free_spins_buy product."""
    session_id = await _start_session(api_client)
    set_rng([_RAW_LP_BLUE] * 15)

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": BET_AMOUNT},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["popup"] == {"type": "buyFreeSpins", "amount": 100 * BET_AMOUNT}
