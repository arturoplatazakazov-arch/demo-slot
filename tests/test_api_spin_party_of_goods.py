"""Integration coverage for the "party-of-goods" game — the repo's first
avalanche/cascade-mechanic game (app/engine/avalanche.py) — actually firing
end-to-end through POST /api/v1/spin. Mirrors the existing
test_api_spin_east_discovery.py's conventions (FakeRNG/set_rng, deterministic
forced symbols via hand-derived reel-weight ranges).

Cumulative reel weights from the seed (app/seed/party_of_goods.py's
_SYMBOLS order, same on all 6 reels): scatter[0,2) wild[2,4) zeus[4,8)
afrodita[8,13) cupidon[13,19) blue[19,33) green[33,46) red[46,58)
yellow[58,69) x2[69,72) x3[72,74) x5[74,75) x7[75,76), total 76. Grid draws
are reel-major (reel 0 rows 0-4, then reel 1 rows 0-4, ...), 6 reels x 5
rows = 30 cells.
"""

_RAW_SCATTER = 0
_RAW_WILD = 2
_RAW_ZEUS = 4
_RAW_AFRODITA = 8
_RAW_CUPIDON = 13
_RAW_BLUE = 19
_RAW_GREEN = 33
_RAW_RED = 46
_RAW_YELLOW = 58
_RAW_X2 = 69
_RAW_X3 = 72
_RAW_X5 = 74
_RAW_X7 = 75

VALID_SYMBOLS = {
    "scatter", "wild", "zeus", "afrodita", "cupidon",
    "blue", "green", "red", "yellow", "x2", "x3", "x5", "x7",
}

BET_AMOUNT = 100000


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "party-of-goods"})
    return response.json()["session_id"]


async def test_spin_response_shape_with_no_win(api_client, set_rng):
    session_id = await _start_session(api_client)

    # 5 symbol codes, each appearing exactly 6 times across the 30 cells —
    # every count stays below the lowest paytable threshold (8), so no
    # cascade fires at all.
    fillers = [_RAW_ZEUS, _RAW_AFRODITA, _RAW_CUPIDON, _RAW_BLUE, _RAW_GREEN]
    set_rng(fillers * 6)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["grid"]) == 5  # rows
    assert all(len(row) == 6 for row in body["grid"])  # reels
    assert all(symbol in VALID_SYMBOLS for row in body["grid"] for symbol in row)
    assert body["line_wins"] == []
    assert body["count_wins"] == []
    assert body["winning_cells"] == []
    assert body["avalanche"] == {"steps": [], "total_win": 0}
    assert body["total_win"] == 0
    assert body["feature"] is None
    assert body["balance"] == 1_000_000 - BET_AMOUNT


async def test_eight_of_a_kind_triggers_one_cascade_and_pays(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Initial grid: 8x zeus (meets its lowest tier, pays[8]=1) + 22 filler
    # cells split across 4 codes, each kept below 8 so nothing else wins on
    # this step. Then 8 refill draws (the removed zeus cells) all land "x2"
    # (a multiplier token) — never in the avalanche pay-type bucket (empty
    # paytable), so the round stops after exactly one cascade regardless.
    # NOT "scatter" here (like the rest of this file once used as a safe
    # inert filler): run_avalanche_spin now checks the free-spins trigger
    # against avalanche_result.final_grid (post-refill), so refilling
    # scatters would spuriously trigger free spins on a test that isn't
    # meant to.
    initial = (
        [_RAW_ZEUS] * 8
        + [_RAW_AFRODITA] * 6
        + [_RAW_CUPIDON] * 6
        + [_RAW_BLUE] * 5
        + [_RAW_GREEN] * 5
    )
    refill = [_RAW_X2] * 8
    set_rng(initial + refill)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["avalanche"] is not None
    assert len(body["avalanche"]["steps"]) == 1
    step = body["avalanche"]["steps"][0]
    assert step["step_multiplier"] == 1
    assert step["step_win"] == BET_AMOUNT  # zeus pays[8]=1 * bet
    assert len(step["wins"]) == 1
    assert step["wins"][0]["symbol"] == "zeus"
    assert step["wins"][0]["count"] == 8
    assert step["tokens_consumed"] == []

    assert body["total_win"] == BET_AMOUNT
    assert body["avalanche"]["total_win"] == BET_AMOUNT
    assert body["feature"] is None  # no scatter anywhere on the final grid
    assert body["balance"] == 1_000_000 - BET_AMOUNT + body["total_win"]


async def test_three_scatters_on_initial_grid_trigger_free_spins(api_client, set_rng):
    session_id = await _start_session(api_client)

    # No wild in the filler mix — wild now substitutes into whichever
    # REGULAR symbol has the most positions (app/engine/avalanche.py), so a
    # wild here would push some regular's count up; keeping it wild-free
    # guarantees every regular count stays safely below 8 on its own.
    fillers = [_RAW_ZEUS, _RAW_AFRODITA, _RAW_CUPIDON, _RAW_BLUE, _RAW_GREEN]
    initial = [_RAW_SCATTER] * 3 + (fillers * 6)[:27]
    set_rng(initial)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["avalanche"]["steps"] == []  # every filler count stays below 8
    assert body["feature"] is not None
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_awarded"] == 10
    assert body["feature"]["spins_remaining"] == 10


async def test_scatters_arriving_only_via_cascade_refill_still_trigger_free_spins(api_client, set_rng):
    """product, this session: the free-spins trigger check must not be
    limited to the initial (pre-cascade) grid — a spin with only 2 scatters
    up front, where a cascade's own refill happens to deal a 3rd (or more)
    scatter, must still open the bonus. See
    app/api/v1/spin_avalanche.py:run_avalanche_spin's switch from
    avalanche_result.initial_grid to .final_grid for the trigger context."""
    session_id = await _start_session(api_client)

    # Initial grid: 8x zeus (wins) + only 2 scatters + safe fillers (2+6+6+4+4=22).
    initial = (
        [_RAW_ZEUS] * 8
        + [_RAW_SCATTER] * 2
        + [_RAW_AFRODITA] * 6
        + [_RAW_CUPIDON] * 6
        + [_RAW_BLUE] * 4
        + [_RAW_GREEN] * 4
    )
    # 8 refill draws (the removed zeus cells): 3 more scatters land here —
    # nowhere on the *initial* grid, only via this cascade's own refill.
    # Final scatter count = 2 (initial) + 3 (refilled) = 5, well past the
    # 3+ trigger_count.
    refill = [_RAW_SCATTER] * 3 + [_RAW_X2] * 5
    set_rng(initial + refill)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["avalanche"]["steps"]) == 1  # the zeus win/refill itself
    assert body["feature"] is not None
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_awarded"] == 20  # 5 scatters -> the "5" tier
    assert body["feature"]["spins_remaining"] == 20


async def test_multiplier_tokens_sum_into_cascade_multiplier(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Initial grid: 8x zeus (wins, pays[8]=1) + 2 multiplier tokens (x3, x5)
    # sitting elsewhere + 20 filler cells kept below 8 each.
    initial = (
        [_RAW_ZEUS] * 8
        + [_RAW_X3] * 1
        + [_RAW_X5] * 1
        + [_RAW_AFRODITA] * 6
        + [_RAW_CUPIDON] * 6
        + [_RAW_BLUE] * 4
        + [_RAW_GREEN] * 4
    )
    # 10 refill draws needed (8 zeus + 2 tokens, all swept up) — all land
    # "scatter" so the round stops after this one step.
    refill = [_RAW_SCATTER] * 10
    set_rng(initial + refill)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    step = body["avalanche"]["steps"][0]
    # multiplier_steps[0]=1 (trail) + x3(3) + x5(5) = 9.
    assert step["step_multiplier"] == 9
    assert step["step_win"] == BET_AMOUNT * 9
    assert len(step["tokens_consumed"]) == 2
    assert {t["value"] for t in step["tokens_consumed"]} == {3, 5}


async def test_free_spins_session_multiplier_accumulates_across_spins(api_client, set_rng):
    """party-of-goods only (product, confirmed this session): unlike the
    base game's per-spin trail+token step multiplier (already covered
    above, resets every spin), multiplier tokens landed *during a free
    spins round* add to a session-wide accumulator that persists across
    every remaining spin in the round (never reset by a retrigger) and is
    reported on FeatureOut.multiplier — see
    app/api/v1/spin_avalanche.py:run_avalanche_spin."""
    session_id = await _start_session(api_client)

    # Trigger: 3 scatters + safe fillers, no win, no tokens on this grid.
    # No wild here — see test_three_scatters_on_initial_grid_trigger_free_spins.
    fillers = [_RAW_ZEUS, _RAW_AFRODITA, _RAW_CUPIDON, _RAW_BLUE, _RAW_GREEN]
    trigger_draws = [_RAW_SCATTER] * 3 + (fillers * 6)[:27]
    set_rng(trigger_draws)
    trigger_resp = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    trigger_body = trigger_resp.json()
    assert trigger_body["feature"]["triggered"] is True
    assert trigger_body["feature"]["spins_awarded"] == 10
    assert trigger_body["feature"]["spins_remaining"] == 10
    assert trigger_body["feature"]["multiplier"] == 1

    # Round-spin 1: 8x zeus (wins) + 1x x3 token (consumed alongside it).
    initial = (
        [_RAW_ZEUS] * 8
        + [_RAW_X3] * 1
        + [_RAW_AFRODITA] * 6
        + [_RAW_CUPIDON] * 6
        + [_RAW_BLUE] * 5
        + [_RAW_GREEN] * 4
    )
    # Not "scatter" — final_grid (post-refill) now drives the trigger check,
    # so refilling scatters here would spuriously retrigger mid-round.
    refill = [_RAW_X2] * 9  # 8 zeus + 1 token removed
    set_rng(initial + refill)
    resp1 = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": 1})
    body1 = resp1.json()
    assert body1["feature"]["spins_remaining"] == 9
    assert body1["feature"]["multiplier"] == 4  # 1 (baseline) + 3 (token)

    # Round-spin 2: no win at all — accumulator must persist unchanged, not reset.
    fillers2 = [_RAW_ZEUS, _RAW_AFRODITA, _RAW_CUPIDON, _RAW_BLUE, _RAW_GREEN]
    set_rng(fillers2 * 6)
    resp2 = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": 1})
    body2 = resp2.json()
    assert body2["feature"]["spins_remaining"] == 8
    assert body2["feature"]["multiplier"] == 4

    # Retrigger (3+ scatter again mid-round): awards +10 spins, but must NOT
    # reset the accumulator back to free_spins.py's own flat baseline.
    retrigger_draws = [_RAW_SCATTER] * 3 + (fillers * 6)[:27]
    set_rng(retrigger_draws)
    resp3 = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": 1})
    body3 = resp3.json()
    assert body3["feature"]["triggered"] is True
    assert body3["feature"]["spins_awarded"] == 10
    assert body3["feature"]["spins_remaining"] == 17  # 8 - 1 (this spin) + 10
    assert body3["feature"]["multiplier"] == 4
