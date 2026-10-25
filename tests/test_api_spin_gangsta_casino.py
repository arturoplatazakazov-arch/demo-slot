"""Integration coverage for "gangsta-casino" (Dirty Money mechanics on the
Gangsta art, with multipliers instead of the wheel since 2026-10-20): the seed
boots, a landed multiplier multiplies a base-game line win end-to-end through
POST /api/v1/spin, and the free-spins round multiplier is sticky
(coin_multiplier round_sticky).
Same FakeRNG/set_rng conventions as tests/test_api_spin_dirty_money_mafia.py."""

from decimal import Decimal
from types import SimpleNamespace

from app.features.base import FeatureContext
from app.features.coin_multiplier import CoinMultiplierFeature
from app.seed.gangsta_casino import COIN_MULTIPLIER_PARAMS

# Cumulative reel weights in app/seed/gangsta_casino.py's _SYMBOLS order:
# scatter[0,3) wof[3,6) wild[6,7) rare_purple[7,12) rare_yellow[12,18)
# rare_blue[18,25) rare_green[25,33) common_2[33,51) common_4[51,71)
# common_3[71,93) common_1[93,117), total 117.
_RAW = {
    "wof": 3, "rare_purple": 7, "rare_yellow": 12, "rare_blue": 18, "rare_green": 25,
    "common_2": 33, "common_4": 51, "common_3": 71, "common_1": 93,
}
# Multiplier value table {"2": 50, "3": 25, ...} (total 100): raw 60 -> x3.
_RAW_VALUE_X3 = 60

BET_AMOUNT = 55000
LINE_BET = BET_AMOUNT // 11

async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "gangsta-casino"})
    assert response.status_code == 200
    return response.json()["session_id"]


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


def _grid_draws_middle_line_and_a_multiplier():
    """Reel by reel, top to bottom: common_1 x3 across the middle row is the
    only line win; one multiplier (wof) on reel 4, top row."""
    reels = [
        ["rare_purple", "common_1", "rare_yellow"],
        ["rare_blue", "common_1", "rare_green"],
        ["common_4", "common_1", "common_2"],
        ["wof", "common_4", "common_3"],
        ["common_3", "common_2", "common_4"],
    ]
    return [_RAW[code] for column in reels for code in column]


async def test_a_landed_multiplier_multiplies_the_line_win(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng(_grid_draws_middle_line_and_a_multiplier() + [_RAW_VALUE_X3])

    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    assert response.status_code == 200, response.text
    body = response.json()

    multiplier = body["coin_multiplier"]
    assert multiplier["applied"] is True
    assert multiplier["multiplier_sum"] == 3
    assert multiplier["positions"] == [{"row": 0, "col": 3, "value": 3, "kind": "3"}]
    # common_1 x3 pays 4.2 x line bet, times the x3 on screen.
    assert body["total_win"] == int(Decimal("4.2") * LINE_BET * 3)
    assert "wheel_of_fortune" not in body or body["wheel_of_fortune"] is None


def _ctx(state, reels, line_pay, rng_values):
    from tests.fakes import FakeRNG

    return FeatureContext(
        session_state=state,
        rng=FakeRNG(rng_values),
        bet_amount=Decimal(BET_AMOUNT),
        symbols=[],
        grid=SimpleNamespace(reels=reels),
        win_evaluation=SimpleNamespace(line_pay_total=Decimal(line_pay)),
    )


def test_free_spins_round_multiplier_is_sticky():
    feature = CoinMultiplierFeature()
    params = COIN_MULTIPLIER_PARAMS
    state = {"free_spins_remaining": 5, "free_spins_bomb_multiplier": "4"}
    empty = [["common_1"] * 3 for _ in range(5)]

    # No multiplier on screen, a line win: still paid at the round's x4.
    ctx = _ctx(state, empty, 100, [])
    assert feature.is_triggered(ctx, params)
    result = feature.execute(ctx, params)
    assert result.win_amount == 300
    assert result.details["round_multiplier"] == "4"

    # A multiplier lands on a spin WITHOUT a win: it still adds to the round.
    with_coin = [col[:] for col in empty]
    with_coin[2][1] = "wof"
    ctx = _ctx(state, with_coin, 0, [_RAW_VALUE_X3])
    result = feature.execute(ctx, params)
    assert result.win_amount == 0
    assert state["free_spins_bomb_multiplier"] == "7"


def test_base_game_multiplier_without_a_line_win_pays_nothing():
    feature = CoinMultiplierFeature()
    reels = [["common_1"] * 3 for _ in range(5)]
    reels[0][0] = "wof"
    result = feature.execute(_ctx({}, reels, 0, [_RAW_VALUE_X3]), COIN_MULTIPLIER_PARAMS)
    assert result.details["applied"] is False
    assert result.win_amount == 0
