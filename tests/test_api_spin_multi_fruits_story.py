"""Integration coverage for the "multi-fruits-story" game end-to-end through
POST /api/v1/spin — same FakeRNG/set_rng conventions as
tests/test_api_spin_dirty_money_mafia.py (deterministic forced symbols via
hand-derived reel-weight ranges).

This is the project's first 3x3 game, so what's pinned here is the shape that
differs from the 5-reel ones: a payline is all-or-nothing (3 of a kind or no
win), the bet is split across 3 lines, and 3 scatters are simultaneously the
count win and the free-spins trigger.
"""

import pytest

# Cumulative reel weights from the seed (app/seed/multi_fruits_story.py's
# _SYMBOLS order): limon[0,22) vinograd[22,42) grusha[42,60) klubnika[60,76)
# bell[76,88) diamond[88,97) 777[97,103) wild[103,107) scatter[107,111),
# total 111.
_RAW_LIMON = 0
_RAW_VINOGRAD = 22
_RAW_GRUSHA = 42
_RAW_KLUBNIKA = 60
_RAW_BELL = 76
_RAW_DIAMOND = 88
_RAW_777 = 97
_RAW_WILD = 103
_RAW_SCATTER = 107

# multiplier_wild draws its variant from its OWN weight table, after the whole
# grid has been drawn: {"1": 55, "2": 20, "3": 13, "5": 8, "7": 4}, total 100 —
# so 1:[0,55) 2:[55,75) 3:[75,88) 5:[88,96) 7:[96,100). One draw per wild on the
# grid, in reel-major order (reel 0 rows 0..2, then reel 1, ...).
_RAW_X1 = 0
_RAW_X2 = 55
_RAW_X3 = 75
_RAW_X7 = 96

# A multiple of 3 (the payline count), so bet_per_line is exact.
BET_AMOUNT = 120000
BET_PER_LINE = BET_AMOUNT // 3
START_BALANCE = 1_000_000

# Line pays from the seed, per line.
_PAY_LIMON = 5
_PAY_WILD = 150


@pytest.fixture(autouse=True)
async def _seed_multi_fruits_story():
    """tests/conftest.py's api_client only seeds three games explicitly; seed
    this one here rather than relying on a previous dev-server run having left
    it in the shared Postgres."""
    from app.core.db import AsyncSessionLocal
    from app.seed.multi_fruits_story import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "multi-fruits-story"}
    )
    return response.json()["session_id"]


async def test_three_matching_symbols_pay_the_line_they_landed_on(api_client, set_rng):
    session_id = await _start_session(api_client)
    # Reel-major (3 raw draws per reel, row 0..2): limon across the middle row,
    # every other row deliberately mismatched so exactly one line pays.
    set_rng([
        _RAW_VINOGRAD, _RAW_LIMON, _RAW_GRUSHA,     # reel 0
        _RAW_KLUBNIKA, _RAW_LIMON, _RAW_BELL,       # reel 1
        _RAW_DIAMOND, _RAW_LIMON, _RAW_777,         # reel 2
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["line_wins"]) == 1
    win = body["line_wins"][0]
    assert win["symbol"] == "limon"
    assert win["count"] == 3
    # Payline 1 is the middle row ([1, 1, 1]) — first in the seed's list.
    assert win["payline"] == 1
    # A line is worth a third of the bet.
    assert body["total_win"] == _PAY_LIMON * BET_PER_LINE
    assert body["balance"] == START_BALANCE - BET_AMOUNT + _PAY_LIMON * BET_PER_LINE
    # No wild landed, so the multiplier mechanic reports nothing at all.
    assert body["multiplier_wilds"] == []


async def test_two_matching_symbols_pay_nothing(api_client, set_rng):
    """A 3-reel paytable has a single "3" entry, so a run of 2 — which pays on
    every other game in the project — is worth nothing here."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_VINOGRAD, _RAW_LIMON, _RAW_GRUSHA,     # reel 0
        _RAW_KLUBNIKA, _RAW_LIMON, _RAW_BELL,       # reel 1
        _RAW_DIAMOND, _RAW_777, _RAW_KLUBNIKA,      # reel 2 — breaks the limon run at 2
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["line_wins"] == []
    assert body["total_win"] == 0
    assert body["balance"] == START_BALANCE - BET_AMOUNT


async def test_three_scatters_pay_and_open_the_free_spins_round(api_client, set_rng):
    session_id = await _start_session(api_client)
    # One scatter per reel (max_per_reel=1, so no reel-cap redraw consumes
    # extra RNG), on a different row each time. The filler never lines up 3 in
    # a row, so `total_win` is the scatter's count win alone.
    set_rng([
        _RAW_SCATTER, _RAW_LIMON, _RAW_VINOGRAD,    # reel 0
        _RAW_GRUSHA, _RAW_SCATTER, _RAW_KLUBNIKA,   # reel 1
        _RAW_LIMON, _RAW_VINOGRAD, _RAW_SCATTER,    # reel 2
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    # Count win: scatters pay against the WHOLE bet, not a per-line share.
    assert len(body["count_wins"]) == 1
    assert body["count_wins"][0]["symbol"] == "scatter"
    assert body["total_win"] == 10 * BET_AMOUNT

    # ...and the same 3 scatters open the round.
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_remaining"] == 10


async def test_free_spins_pay_double(api_client, set_rng):
    """win_multiplier=2 applies to spins played inside the round, not to the
    triggering spin itself."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_SCATTER, _RAW_LIMON, _RAW_VINOGRAD,
        _RAW_GRUSHA, _RAW_SCATTER, _RAW_KLUBNIKA,
        _RAW_LIMON, _RAW_VINOGRAD, _RAW_SCATTER,
    ])
    await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})

    # First free spin: the same middle-row limon line as the base-game test.
    set_rng([
        _RAW_VINOGRAD, _RAW_LIMON, _RAW_GRUSHA,
        _RAW_KLUBNIKA, _RAW_LIMON, _RAW_BELL,
        _RAW_DIAMOND, _RAW_LIMON, _RAW_777,
    ])
    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["total_win"] == 2 * _PAY_LIMON * BET_PER_LINE
    assert body["feature"]["spins_remaining"] == 9


async def test_buying_the_bonus_charges_20x_and_starts_the_round(api_client, set_rng):
    session_id = await _start_session(api_client)
    # The buy spin still deals a grid; keep it winless so the balance check is
    # exactly "start minus cost".
    set_rng([
        _RAW_VINOGRAD, _RAW_LIMON, _RAW_GRUSHA,
        _RAW_KLUBNIKA, _RAW_BELL, _RAW_DIAMOND,
        _RAW_777, _RAW_KLUBNIKA, _RAW_LIMON,
    ])

    bet = 12000  # the cheapest step: 20x it is 240k, well inside the 1M balance
    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": bet},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["spins_remaining"] == 10
    assert body["total_win"] == 0
    assert body["balance"] == START_BALANCE - 20 * bet


# --- multiplier_wild --------------------------------------------------------
#
# Every wild that lands rolls x1/x2/x3/x5/x7 and multiplies the PAYLINE it sits
# on (app/features/multiplier_wild.py). What's pinned below is the scope rule:
# only lines the wild is actually part of, several wilds on one line multiply
# together, and a wild off the winning line changes nothing.


async def test_wild_multiplier_multiplies_the_line_it_lands_on(api_client, set_rng):
    session_id = await _start_session(api_client)
    # Middle row: wild + limon + limon -> pays as 3x limon. The wild rolls x2.
    set_rng([
        _RAW_VINOGRAD, _RAW_WILD, _RAW_GRUSHA,      # reel 0
        _RAW_KLUBNIKA, _RAW_LIMON, _RAW_BELL,       # reel 1
        _RAW_DIAMOND, _RAW_LIMON, _RAW_777,         # reel 2
        _RAW_X2,                                    # the wild's own variant draw
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["multiplier_wilds"] == [{"row": 1, "col": 0, "multiplier": 2}]
    # `line_wins` stays UNmultiplied — it's the raw paytable evaluation, and the
    # multiplier lands in total_win. The client relies on this split to animate
    # the base win and the multiplier separately.
    assert body["line_wins"][0]["amount"] == _PAY_LIMON * BET_PER_LINE
    assert body["total_win"] == 2 * _PAY_LIMON * BET_PER_LINE


async def test_two_wilds_on_one_line_multiply_together(api_client, set_rng):
    session_id = await _start_session(api_client)
    # Middle row: wild + wild + limon -> still pays as 3x limon, now x2 * x3.
    set_rng([
        _RAW_VINOGRAD, _RAW_WILD, _RAW_GRUSHA,
        _RAW_KLUBNIKA, _RAW_WILD, _RAW_BELL,
        _RAW_DIAMOND, _RAW_LIMON, _RAW_777,
        _RAW_X2, _RAW_X3,                           # reel-major: reel 0's, then reel 1's
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert [w["multiplier"] for w in body["multiplier_wilds"]] == [2, 3]
    assert body["total_win"] == 6 * _PAY_LIMON * BET_PER_LINE


async def test_wild_off_the_winning_line_pays_nothing_extra(api_client, set_rng):
    session_id = await _start_session(api_client)
    # limon wins on the middle row; the wild sits on the TOP row, whose own line
    # (wild + bell + diamond) never reaches 3 of a kind.
    set_rng([
        _RAW_WILD, _RAW_LIMON, _RAW_GRUSHA,
        _RAW_BELL, _RAW_LIMON, _RAW_KLUBNIKA,
        _RAW_DIAMOND, _RAW_LIMON, _RAW_777,
        _RAW_X7,                                    # the biggest multiplier — and irrelevant
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    # Still reported (the client has to draw the x7 on it) but not paid.
    assert body["multiplier_wilds"] == [{"row": 0, "col": 0, "multiplier": 7}]
    assert body["total_win"] == _PAY_LIMON * BET_PER_LINE


async def test_all_wild_line_stacks_every_multiplier(api_client, set_rng):
    session_id = await _start_session(api_client)
    # Three wilds on the middle row: the line pays as WILD itself, and all three
    # multipliers stack (x2 * x3 * x2 = x12).
    set_rng([
        _RAW_VINOGRAD, _RAW_WILD, _RAW_GRUSHA,
        _RAW_KLUBNIKA, _RAW_WILD, _RAW_BELL,
        _RAW_DIAMOND, _RAW_WILD, _RAW_777,
        _RAW_X2, _RAW_X3, _RAW_X2,
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["line_wins"][0]["symbol"] == "wild"
    assert body["total_win"] == 12 * _PAY_WILD * BET_PER_LINE


async def test_wild_that_stays_plain_reports_x1_and_pays_the_base_line(api_client, set_rng):
    """x1 is a real outcome, not the absence of one: the client still needs the
    entry to pick the `wild` Spine skin and play the reveal."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_VINOGRAD, _RAW_WILD, _RAW_GRUSHA,
        _RAW_KLUBNIKA, _RAW_LIMON, _RAW_BELL,
        _RAW_DIAMOND, _RAW_LIMON, _RAW_777,
        _RAW_X1,
    ])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["multiplier_wilds"] == [{"row": 1, "col": 0, "multiplier": 1}]
    assert body["total_win"] == _PAY_LIMON * BET_PER_LINE
