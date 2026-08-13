"""Integration coverage for the "dirty-money-mafia" game's Wheel of Fortune
firing end-to-end through POST /api/v1/spin — same FakeRNG/set_rng conventions
as tests/test_api_spin_east_discovery.py (deterministic forced symbols via
hand-derived reel-weight ranges)."""

# Cumulative reel weights from the seed (app/seed/dirty_money_mafia.py's
# _SYMBOLS order): scatter[0,3) wof[3,6) wild[6,7) rare_red[7,12)
# rare_yellow[12,18) rare_blue[18,25) rare_green[25,33) common_red[33,51)
# common_yellow[51,71) common_green[71,93) common_blue[93,117), total 117.
_RAW_WOF = 3
_RAW_COMMON_BLUE = 93
_RAW_COMMON_GREEN = 71

BET_AMOUNT = 100000

# The seed's wheel segments in drum order, with their weights:
# x2:30 x3:22 x4:16 x5:12 x6:8 x7:5 x8:3 free_spins:4 — total 100.
# So a raw draw of 0 lands segment 0 (x2) and 96 lands segment 7 (free spins).
_RAW_WHEEL_X2 = 0
_RAW_WHEEL_FREE_SPINS = 96


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "dirty-money-mafia"}
    )
    return response.json()["session_id"]


def _grid_draws_with_three_wof():
    """Reel-major (3 raw draws per reel, row 0..2): one wof on reels 0, 2 and
    4 — enough for the 3-symbol trigger, and within the symbol's
    max_per_reel=1 cap so no reel-cap redraw consumes extra RNG.

    The filler alternates blue/green per reel on purpose: a line win needs 3
    matching symbols from reel 0 onward, and alternating breaks every line at
    2. That keeps `total_win` equal to the wheel's own prize, so these tests
    assert the wheel's payout rather than the wheel plus an incidental
    line win."""
    return [
        _RAW_WOF, _RAW_COMMON_BLUE, _RAW_COMMON_BLUE,  # reel 0
        _RAW_COMMON_GREEN, _RAW_COMMON_GREEN, _RAW_COMMON_GREEN,  # reel 1
        _RAW_WOF, _RAW_COMMON_BLUE, _RAW_COMMON_BLUE,  # reel 2
        _RAW_COMMON_GREEN, _RAW_COMMON_GREEN, _RAW_COMMON_GREEN,  # reel 3
        _RAW_WOF, _RAW_COMMON_BLUE, _RAW_COMMON_BLUE,  # reel 4
    ]


async def test_three_wheel_symbols_open_the_wheel_and_pay_a_multiplier(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng(_grid_draws_with_three_wof() + [_RAW_WHEEL_X2])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    wheel = body["wheel_of_fortune"]
    assert wheel is not None
    assert wheel["segment_index"] == 0
    assert wheel["prize_type"] == "multiplier"
    assert wheel["multiplier"] == 2
    # Multiplier pays against the WHOLE bet, not a per-line share.
    assert wheel["win_amount"] == 2 * BET_AMOUNT

    # The wheel prize lands in the spin's total, and so in the balance.
    assert body["total_win"] == 2 * BET_AMOUNT
    assert body["balance"] == 1_000_000 - BET_AMOUNT + 2 * BET_AMOUNT

    # Segment labels go out in drum order so the client can render them onto
    # the (blank) bullet art, without their weights.
    assert [s["value"] for s in wheel["segments"]] == [2, 3, 4, 5, 6, 7, 8, None]
    assert wheel["segments"][7]["type"] == "free_spins"


async def test_wheel_free_spins_segment_opens_the_round_instead_of_paying(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng(_grid_draws_with_three_wof() + [_RAW_WHEEL_FREE_SPINS])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    wheel = body["wheel_of_fortune"]
    assert wheel["prize_type"] == "free_spins"
    assert wheel["win_amount"] == 0

    # The round is the prize: spins are awarded through the same free_spins
    # module a scatter trigger uses, so the client's existing bonus-entry path
    # (feature + bonusSpinsWin popup) carries the player in.
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_remaining"] > 0
    # No cash from the wheel itself this time.
    assert body["total_win"] == 0


async def test_two_wheel_symbols_do_not_open_the_wheel(api_client, set_rng):
    session_id = await _start_session(api_client)
    draws = _grid_draws_with_three_wof()
    draws[12] = _RAW_COMMON_BLUE  # reel 4's wof -> a plain symbol, leaving 2 wof
    set_rng(draws)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    assert response.json()["wheel_of_fortune"] is None
