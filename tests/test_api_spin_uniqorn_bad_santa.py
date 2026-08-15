"""Integration coverage for the "uniqorn-bad-santa" game end-to-end through
POST /api/v1/spin. The mechanic is the repo's avalanche/cascade engine
(app/engine/avalanche.py), cloned from sugar-galaxy — so what's pinned here is
this seed's own wiring: its symbol set, its fixed 7-spin free-spins award, its
multiplier baubles and its bomb, all reached through the real API.

Same FakeRNG/set_rng conventions as tests/test_api_spin_party_of_goods.py
(deterministic forced symbols via hand-derived reel-weight ranges).

Cumulative reel weights from the seed (app/seed/uniqorn_bad_santa.py's
_SYMBOLS order, same on all 6 reels): scatter[0,2) wild[2,4) hp_yellow[4,8)
hp_red[8,13) hp_green[13,19) hp_blue[19,25) lp_blue[25,39) lp_red[39,52)
lp_green[52,64) lp_yellow[64,75) x2[75,78) x3[78,80) x5[80,81) x7[81,82)
bomb[82,83), total 83. Grid draws are reel-major (reel 0 rows 0-4, then reel 1
rows 0-4, ...), 6 reels x 5 rows = 30 cells.
"""

import pytest

_RAW_SCATTER = 0
_RAW_WILD = 2
_RAW_HP_YELLOW = 4
_RAW_HP_RED = 8
_RAW_HP_GREEN = 13
_RAW_HP_BLUE = 19
_RAW_LP_BLUE = 25
_RAW_LP_RED = 39
_RAW_LP_GREEN = 52
_RAW_LP_YELLOW = 64
_RAW_X2 = 75
_RAW_X3 = 78
_RAW_X5 = 80
_RAW_X7 = 81
_RAW_BOMB = 82

VALID_SYMBOLS = {
    "scatter", "wild",
    "hp_red", "hp_yellow", "hp_green", "hp_blue",
    "lp_red", "lp_yellow", "lp_green", "lp_blue",
    "x2", "x3", "x5", "x7", "bomb",
}

# Five REGULAR codes, no wild: a wild would substitute into whichever regular
# has the most positions and could push a count over the 8 threshold on a grid
# that is meant not to win.
FILLERS = [_RAW_HP_RED, _RAW_HP_GREEN, _RAW_HP_BLUE, _RAW_LP_BLUE, _RAW_LP_RED]

BET_AMOUNT = 100000
START_BALANCE = 1_000_000


@pytest.fixture(autouse=True)
async def _seed_uniqorn_bad_santa():
    """tests/conftest.py's api_client only seeds three games explicitly; seed
    this one here rather than relying on a previous dev-server run having left
    it in the shared Postgres."""
    from app.core.db import AsyncSessionLocal
    from app.seed.uniqorn_bad_santa import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "uniqorn-bad-santa"}
    )
    return response.json()["session_id"]


async def test_spin_response_shape_with_no_win(api_client, set_rng):
    session_id = await _start_session(api_client)

    # 5 codes, 6 cells each across the 30 — every count stays below the lowest
    # paytable threshold (8), so no cascade fires at all.
    set_rng(FILLERS * 6)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["grid"]) == 5  # rows
    assert all(len(row) == 6 for row in body["grid"])  # reels
    assert all(symbol in VALID_SYMBOLS for row in body["grid"] for symbol in row)
    assert body["line_wins"] == []  # count-pay game — no paylines at all
    assert body["avalanche"] == {"steps": [], "total_win": 0}
    assert body["total_win"] == 0
    assert body["feature"] is None
    assert body["balance"] == START_BALANCE - BET_AMOUNT


async def test_eight_of_a_kind_triggers_one_cascade_and_pays(api_client, set_rng):
    session_id = await _start_session(api_client)

    # 8x hp_yellow (its high tier's lowest key, pays[8]=1) + 22 filler cells,
    # each code kept below 8 so nothing else wins on this step.
    initial = (
        [_RAW_HP_YELLOW] * 8
        + [_RAW_HP_RED] * 6
        + [_RAW_HP_GREEN] * 6
        + [_RAW_LP_BLUE] * 5
        + [_RAW_LP_RED] * 5
    )
    # The 8 refilled cells all land x2 — a modifier with an empty paytable, so
    # it can never win and the round stops after exactly one cascade. (NOT
    # scatter: the free-spins check reads the post-refill grid, so refilling
    # scatters would spuriously open the bonus on a test that isn't about it.)
    set_rng(initial + [_RAW_X2] * 8)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["avalanche"]["steps"]) == 1
    step = body["avalanche"]["steps"][0]
    assert step["step_multiplier"] == 1  # multiplier_steps[0], no baubles swept
    assert step["step_win"] == BET_AMOUNT  # hp_yellow pays[8]=1 * bet
    assert len(step["wins"]) == 1
    assert step["wins"][0]["symbol"] == "hp_yellow"
    assert step["wins"][0]["count"] == 8
    assert step["tokens_consumed"] == []

    assert body["total_win"] == BET_AMOUNT
    assert body["balance"] == START_BALANCE - BET_AMOUNT + body["total_win"]


async def test_three_scatters_award_exactly_seven_free_spins(api_client, set_rng):
    session_id = await _start_session(api_client)

    set_rng([_RAW_SCATTER] * 3 + (FILLERS * 6)[:27])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["avalanche"]["steps"] == []  # every filler count stays below 8
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    # Flat award — this seed grants the same 7 spins on every trigger and
    # retrigger, unlike the tiered games.
    assert body["feature"]["spins_awarded"] == 7
    assert body["feature"]["spins_remaining"] == 7


async def test_multiplier_baubles_sum_into_the_cascade_multiplier(api_client, set_rng):
    session_id = await _start_session(api_client)

    # 8x hp_yellow (wins) + an x3 and an x5 bauble elsewhere on the grid; both
    # are swept up with the win and add on top of the trail multiplier.
    initial = (
        [_RAW_HP_YELLOW] * 8
        + [_RAW_X3]
        + [_RAW_X5]
        + [_RAW_HP_RED] * 6
        + [_RAW_HP_GREEN] * 6
        + [_RAW_LP_BLUE] * 4
        + [_RAW_LP_RED] * 4
    )
    set_rng(initial + [_RAW_X2] * 10)  # 8 symbols + 2 baubles cleared

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    step = response.json()["avalanche"]["steps"][0]

    # multiplier_steps[0]=1 (trail) + x3(3) + x5(5) = 9.
    assert step["step_multiplier"] == 9
    assert step["step_win"] == BET_AMOUNT * 9
    assert {t["value"] for t in step["tokens_consumed"]} == {3, 5}


async def test_bomb_detonates_only_after_the_grid_stops_paying(api_client, set_rng):
    session_id = await _start_session(api_client)

    # No win anywhere (every count below 8) but one bomb on the board: the
    # engine resolves wins first and only then lets the bomb clear its own
    # row + column, with no payout of its own.
    initial = [_RAW_BOMB] + (FILLERS * 6)[:29]
    # Refill the cleared cross with baubles so the next grid has no win either
    # and the round ends after this single detonation step.
    set_rng(initial + [_RAW_X2] * 12)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    steps = body["avalanche"]["steps"]
    assert len(steps) == 1
    step = steps[0]
    assert step["wins"] == []
    assert step["step_win"] == 0
    assert len(step["bombs_detonated"]) == 1
    detonation = step["bombs_detonated"][0]
    # Its own cell plus the rest of its row (5) and column (4) — nothing on this
    # grid is bomb-proof (no wild/scatter in the fillers).
    assert len(detonation["cleared"]) == 1 + 5 + 4
    assert body["total_win"] == 0
