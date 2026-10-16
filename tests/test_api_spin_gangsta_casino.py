"""Integration coverage for "gangsta-casino" (Dirty Money mechanics on the
Gangsta art): the seed boots, the 14-segment wheel fires end-to-end through
POST /api/v1/spin and a wheel free-spins segment hands off to the round.
Same FakeRNG/set_rng conventions as tests/test_api_spin_dirty_money_mafia.py."""

from app.seed.gangsta_casino import WHEEL_SEGMENTS

# Cumulative reel weights in app/seed/gangsta_casino.py's _SYMBOLS order:
# scatter[0,3) wof[3,6) wild[6,7) rare_purple[7,12) rare_yellow[12,18)
# rare_blue[18,25) rare_green[25,33) common_2[33,51) common_4[51,71)
# common_3[71,93) common_1[93,117), total 117.
_RAW_WOF = 3
_RAW_COMMON_1 = 93
_RAW_COMMON_3 = 71

BET_AMOUNT = 55000

# Segment 0 is x2 (weight 15) -> raw 0. Segment 5 is the first free-spins slot:
# cumulative 15+6+11+3+8 = 43 -> raw 43.
_RAW_WHEEL_X2 = 0
_RAW_WHEEL_FREE_SPINS = 43


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "gangsta-casino"})
    assert response.status_code == 200
    return response.json()["session_id"]


def _grid_draws_with_three_wof():
    """One wof on reels 0, 2, 4; filler alternates per reel so no line wins."""
    return [
        _RAW_WOF, _RAW_COMMON_1, _RAW_COMMON_1,
        _RAW_COMMON_3, _RAW_COMMON_3, _RAW_COMMON_3,
        _RAW_WOF, _RAW_COMMON_1, _RAW_COMMON_1,
        _RAW_COMMON_3, _RAW_COMMON_3, _RAW_COMMON_3,
        _RAW_WOF, _RAW_COMMON_1, _RAW_COMMON_1,
    ]


async def test_session_start_exposes_the_gangsta_symbol_set(api_client):
    response = await api_client.post("/api/v1/session/start", json={"game_id": "gangsta-casino"})
    assert response.status_code == 200
    codes = {s["code"] for s in response.json()["symbols"]}
    # 1:1 with front/js/gangsta-casino/slot.js SYMBOL_ART.
    assert codes == {
        "scatter", "wof", "wild",
        "rare_purple", "rare_yellow", "rare_blue", "rare_green",
        "common_1", "common_2", "common_3", "common_4",
    }


async def test_three_wheel_symbols_pay_a_multiplier_off_14_segments(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng(_grid_draws_with_three_wof() + [_RAW_WHEEL_X2])

    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    assert response.status_code == 200, response.text
    body = response.json()

    wheel = body["wheel_of_fortune"]
    assert wheel["segment_index"] == 0
    assert wheel["prize_type"] == "multiplier"
    assert wheel["win_amount"] == 2 * BET_AMOUNT
    assert body["total_win"] == 2 * BET_AMOUNT
    # The client draws the drum from this list — 14 slots, like the wheel art.
    assert len(wheel["segments"]) == 14 == len(WHEEL_SEGMENTS)


async def test_wheel_free_spins_segment_opens_the_round(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng(_grid_draws_with_three_wof() + [_RAW_WHEEL_FREE_SPINS])

    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    assert response.status_code == 200
    body = response.json()

    assert body["wheel_of_fortune"]["segment_index"] == 5
    assert body["wheel_of_fortune"]["prize_type"] == "free_spins"
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["spins_remaining"] > 0
    assert body["total_win"] == 0
