"""Integration coverage for the "miami-fruits-3" game end-to-end through
POST /api/v1/spin — same FakeRNG/set_rng conventions as
tests/test_api_spin_multi_fruits_story.py (deterministic forced symbols via
hand-derived reel-weight ranges).

What's pinned here is what makes this game different from every other one in
the project: it has NO features at all, so line pay is the only thing that can
ever move the balance, and all FIVE of its paylines (three rows plus both
diagonals) have to be evaluated — the 3x3 game next door only has the rows.
"""

import pytest

# Cumulative reel weights from the seed (app/seed/miami_fruits_3.py's _SYMBOLS
# order): cherry[0,280) lemon[280,500) plum[500,670) grape[670,800)
# bell[800,890) bar[890,950) star[950,985) seven[985,1000), total 1000.
_RAW_CHERRY = 0
_RAW_LEMON = 280
_RAW_PLUM = 500
_RAW_GRAPE = 670
_RAW_BELL = 800
_RAW_BAR = 890
_RAW_STAR = 950
_RAW_SEVEN = 985

# A multiple of 5 (the payline count), so bet_per_line is exact.
BET_AMOUNT = 100000
BET_PER_LINE = BET_AMOUNT // 5
START_BALANCE = 1_000_000

# Line pays from the seed, per line.
_PAY_CHERRY = 15
_PAY_SEVEN = 2500


@pytest.fixture(autouse=True)
async def _seed_miami_fruits_3():
    """tests/conftest.py's api_client only seeds three games explicitly; seed
    this one here rather than relying on a previous dev-server run having left
    it in the shared Postgres."""
    from app.core.db import AsyncSessionLocal
    from app.seed.miami_fruits_3 import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "miami-fruits-3"}
    )
    return response.json()["session_id"]


async def _spin(api_client, session_id, bet=BET_AMOUNT):
    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": bet}
    )
    assert response.status_code == 200
    return response.json()


async def test_three_matching_symbols_pay_the_row_they_landed_on(api_client, set_rng):
    session_id = await _start_session(api_client)
    # Reel-major (3 raw draws per reel, row 0..2): cherry across the middle row,
    # every other row deliberately mismatched so exactly one line pays.
    set_rng([
        _RAW_LEMON, _RAW_CHERRY, _RAW_STAR,     # reel 0
        _RAW_PLUM, _RAW_CHERRY, _RAW_GRAPE,       # reel 1
        _RAW_BELL, _RAW_CHERRY, _RAW_BAR,         # reel 2
    ])

    body = await _spin(api_client, session_id)

    assert len(body["line_wins"]) == 1
    win = body["line_wins"][0]
    assert win["symbol"] == "cherry"
    assert win["count"] == 3
    # Payline 1 is the middle row ([1, 1, 1]) — first in the seed's list.
    assert win["payline"] == 1
    # A line is worth a fifth of the bet.
    assert body["total_win"] == _PAY_CHERRY * BET_PER_LINE
    assert body["balance"] == START_BALANCE - BET_AMOUNT + _PAY_CHERRY * BET_PER_LINE


async def test_two_matching_symbols_pay_nothing(api_client, set_rng):
    """A 3-reel paytable has a single "3" entry, so a run of 2 — which pays on
    every 5-reel game in the project — is worth nothing here."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_LEMON, _RAW_CHERRY, _RAW_STAR,
        _RAW_PLUM, _RAW_CHERRY, _RAW_GRAPE,
        _RAW_BELL, _RAW_BAR, _RAW_PLUM,           # reel 2 breaks the cherry run at 2
    ])

    body = await _spin(api_client, session_id)

    assert body["line_wins"] == []
    assert body["total_win"] == 0
    assert body["balance"] == START_BALANCE - BET_AMOUNT


async def test_diagonal_pays(api_client, set_rng):
    """The two diagonals are what this game has over the other 3x3 line-pay one,
    so a win that exists ONLY on a diagonal has to be paid."""
    session_id = await _start_session(api_client)
    # Top-left to bottom-right: row 0 on reel 0, row 1 on reel 1, row 2 on reel 2.
    set_rng([
        _RAW_SEVEN, _RAW_CHERRY, _RAW_STAR,     # reel 0
        _RAW_PLUM, _RAW_SEVEN, _RAW_GRAPE,        # reel 1
        _RAW_BELL, _RAW_BAR, _RAW_SEVEN,          # reel 2
    ])

    body = await _spin(api_client, session_id)

    assert len(body["line_wins"]) == 1
    win = body["line_wins"][0]
    assert win["symbol"] == "seven"
    # Payline 4 is [0, 1, 2] — fourth in the seed's list.
    assert win["payline"] == 4
    assert body["total_win"] == _PAY_SEVEN * BET_PER_LINE


async def test_full_screen_of_one_symbol_pays_all_five_lines(api_client, set_rng):
    """Every row and both diagonals are the same symbol — the top of this game's
    pay range, and the check that all five paylines are actually wired up."""
    session_id = await _start_session(api_client)
    set_rng([_RAW_CHERRY] * 9)

    body = await _spin(api_client, session_id)

    assert len(body["line_wins"]) == 5
    assert {w["payline"] for w in body["line_wins"]} == {1, 2, 3, 4, 5}
    assert body["total_win"] == 5 * _PAY_CHERRY * BET_PER_LINE


async def test_game_has_no_features_at_all(api_client, set_rng):
    """The product definition of this game: line pay and nothing else. A grid of
    nine sevens would trigger a bonus in any other game here — this one just
    pays the lines."""
    session_id = await _start_session(api_client)
    set_rng([_RAW_SEVEN] * 9)

    body = await _spin(api_client, session_id)

    assert body["feature"] is None
    assert body["total_win"] == 5 * _PAY_SEVEN * BET_PER_LINE


async def test_session_start_advertises_no_bonus_triggers(api_client):
    """session/start is where the client learns what the game can do. Both
    trigger blocks being null is the contract the paytable popup relies on —
    it's what lets the page say "линии и ничего больше" without hardcoding it."""
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "miami-fruits-3"}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["free_spins_trigger"] is None
    assert body["hold_and_win_trigger"] is None
    # Symbol order is the contract with SYMBOL_CODES in the frontend's slot.js.
    assert [s["code"] for s in body["symbols"]] == [
        "cherry", "lemon", "plum", "grape", "bell", "bar", "star", "seven",
    ]
    # Every symbol pays, and only on a full run of 3.
    assert all(list(s["paytable"]) == ["3"] for s in body["symbols"])
    # Every step divides by the 5 paylines, so no line win carries a remainder.
    assert all(step % 5 == 0 for step in body["bet"]["steps"])
