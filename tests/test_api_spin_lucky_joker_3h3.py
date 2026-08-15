"""Integration coverage for the "lucky-joker-3h3" game end-to-end through
POST /api/v1/spin — same FakeRNG/set_rng conventions as
tests/test_api_spin_multi_fruits_story.py (deterministic forced symbols via
hand-derived reel-weight ranges).

What's pinned here is this game's own 3x3 shape, which differs from every
other game in the project (product, matched against the reference Hold'n Win):
  * 5 paylines — the three rows plus both diagonals;
  * a COIN carries a multiplier and multiplies a WINNING LINE, with no
    collector needed on the grid, and pays nothing without a line;
  * a COLLECTOR on the middle reel (it lands nowhere else) plus a coin on each
    of the outer two opens Hold & Win, which runs in `collector` mode: the
    grid starts empty but for that collector, its reel only ever takes
    collectors and the outer two only coins, and every collector is worth the
    sum of all the coins.
"""

import pytest

# Cumulative reel weights from the seed (app/seed/lucky_joker_3h3.py's
# _SYMBOLS order): cherry[0,22) lemon[22,42) plum[42,60) watermelon[60,76)
# bar[76,88) bell[88,97) 777[97,102) wild[102,106) scatter[106,110)
# coin[110,118), total 118 — plus, on the MIDDLE reel only,
# collector[118,127) (its per-reel weights are [0, 9, 0], so the other two
# reels total 118 and every range above is unchanged there).
_RAW_CHERRY = 0
_RAW_LEMON = 22
_RAW_PLUM = 42
_RAW_WATERMELON = 60
_RAW_BAR = 76
_RAW_BELL = 88
_RAW_777 = 97
_RAW_WILD = 102
_RAW_SCATTER = 106
_RAW_COIN = 110
_RAW_COLLECTOR = 120   # middle reel only

# The coin mechanics draw from their own tables, one randbelow per draw. NB:
# the ranges follow the order the weights come back from Postgres in, NOT the
# order the seed writes them — FeatureConfig.params is jsonb, which reorders
# object keys (shortest first, then bytewise). weighted_pick walks the dict as
# given. (Only the enumeration order changes; every key keeps its own weight,
# so the odds are exactly what the seed configures.)
#
# coin_multiplier.value_weights, jsonb order:
#   1:[0,4600) 2:[4600,7000) 3:[7000,8200) 5:[8200,8800) 10:[8800,9000)
#   15:[9000,9080) mini:[9080,9140) grand:[9140,9142) major:[9142,9148)
#   minor:[9148,9168)
_RAW_BASE_COIN_X1 = 0
_RAW_BASE_COIN_X5 = 8200
_RAW_BASE_COIN_GRAND = 9140

# hold_and_win.respin_land_weights {blank:84, coin:16} -> jsonb order
# coin:[0,16) blank:[16,100); collector_land_weights {blank:93, coin:7} ->
# coin:[0,7) blank:[7,100). So a raw of 50 never lands anything on either reel.
_RAW_NOTHING_LANDS = 50

# A multiple of 5 (the payline count), so bet_per_line is exact.
BET_AMOUNT = 100000
BET_PER_LINE = BET_AMOUNT // 5
START_BALANCE = 1_000_000

# Line pays from the seed, per line.
_PAY_CHERRY = 5.3
_PAY_777 = 110


@pytest.fixture(autouse=True)
async def _seed_lucky_joker():
    """tests/conftest.py's api_client only seeds a few games explicitly; seed
    this one here rather than relying on a previous dev-server run having left
    it in the shared Postgres."""
    from app.core.db import AsyncSessionLocal
    from app.seed.lucky_joker_3h3 import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start_session(api_client) -> str:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "lucky-joker-3h3"}
    )
    return response.json()["session_id"]


async def _spin(api_client, session_id):
    return await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )


async def test_three_matching_symbols_pay_the_row_they_landed_on(api_client, set_rng):
    session_id = await _start_session(api_client)
    # Reel-major (3 raw draws per reel, row 0..2): cherry across the middle
    # row, every other row deliberately mismatched so exactly one line pays.
    set_rng([
        _RAW_LEMON, _RAW_CHERRY, _RAW_PLUM,        # reel 0
        _RAW_WATERMELON, _RAW_CHERRY, _RAW_BELL,   # reel 1
        _RAW_BAR, _RAW_CHERRY, _RAW_777,           # reel 2
    ])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert len(body["line_wins"]) == 1
    win = body["line_wins"][0]
    assert win["symbol"] == "cherry"
    assert win["payline"] == 1  # payline 1 is the middle row — first in the seed's list
    # No coin on the grid, so the line pays flat: a fifth of the bet per line.
    assert body["coin_multiplier"] is None
    assert body["total_win"] == _PAY_CHERRY * BET_PER_LINE
    assert body["balance"] == START_BALANCE - BET_AMOUNT + _PAY_CHERRY * BET_PER_LINE


async def test_diagonal_payline_pays(api_client, set_rng):
    """The two diagonals are what this game adds over the other 3x3 one, whose
    paylines are the three rows only."""
    session_id = await _start_session(api_client)
    # 777 down the top-left -> bottom-right diagonal (payline 4, [0, 1, 2]).
    set_rng([
        _RAW_777, _RAW_LEMON, _RAW_PLUM,           # reel 0 — 777 on row 0
        _RAW_CHERRY, _RAW_777, _RAW_BELL,          # reel 1 — 777 on row 1
        _RAW_BAR, _RAW_LEMON, _RAW_777,            # reel 2 — 777 on row 2
    ])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert len(body["line_wins"]) == 1
    assert body["line_wins"][0]["symbol"] == "777"
    assert body["line_wins"][0]["payline"] == 4
    assert body["total_win"] == _PAY_777 * BET_PER_LINE


async def test_a_coin_multiplies_the_winning_line(api_client, set_rng):
    session_id = await _start_session(api_client)
    # cherry across the middle row + one coin parked on a losing row. Coins
    # sit on reels 0 and 1 only, so the round doesn't also open.
    set_rng([
        _RAW_COIN, _RAW_CHERRY, _RAW_PLUM,         # reel 0 — coin on row 0
        _RAW_WATERMELON, _RAW_CHERRY, _RAW_BELL,   # reel 1
        _RAW_BAR, _RAW_CHERRY, _RAW_777,           # reel 2
    ] + [_RAW_BASE_COIN_X5])                       # the coin draws x5

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["hold_and_win"] is None            # no coin on reel 2
    assert body["coin_multiplier"]["applied"] is True
    assert body["coin_multiplier"]["multiplier_sum"] == 5
    assert body["coin_multiplier"]["positions"] == [
        {"row": 0, "col": 0, "value": 5, "kind": "5"}
    ]
    # The whole line pay is multiplied — not the coin paying on its own.
    assert body["total_win"] == _PAY_CHERRY * BET_PER_LINE * 5


async def test_a_coin_pays_nothing_without_a_winning_line(api_client, set_rng):
    """The coin shows its value on every spin it lands (that's the tease), but
    it only ever pays by multiplying a line."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_COIN, _RAW_CHERRY, _RAW_PLUM,         # reel 0
        _RAW_WATERMELON, _RAW_BELL, _RAW_LEMON,    # reel 1 — nothing lines up
        _RAW_BAR, _RAW_777, _RAW_WATERMELON,       # reel 2
    ] + [_RAW_BASE_COIN_X5])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["line_wins"] == []
    assert body["coin_multiplier"]["multiplier_sum"] == 5   # still shown...
    assert body["coin_multiplier"]["applied"] is False      # ...but not paid
    assert body["total_win"] == 0
    assert body["balance"] == START_BALANCE - BET_AMOUNT


async def test_a_jackpot_coin_multiplies_the_line_by_its_tier(api_client, set_rng):
    """Jackpot coins can land in the base game too (product) — a GRAND coin
    multiplies the line by 1000, which is why its weight is 2 in 9168."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_COIN, _RAW_CHERRY, _RAW_PLUM,
        _RAW_WATERMELON, _RAW_CHERRY, _RAW_BELL,
        _RAW_BAR, _RAW_CHERRY, _RAW_777,
    ] + [_RAW_BASE_COIN_GRAND])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["coin_multiplier"]["positions"][0]["kind"] == "grand"
    assert body["coin_multiplier"]["multiplier_sum"] == 1000
    assert body["total_win"] == _PAY_CHERRY * BET_PER_LINE * 1000


async def test_a_collector_plus_coins_on_the_outer_reels_opens_the_round(api_client, set_rng):
    session_id = await _start_session(api_client)
    # The trigger: a collector on the middle reel, a coin on each of the outer
    # two. A coin on the middle reel is NOT what opens it any more.
    grid_draws = [
        _RAW_COIN, _RAW_CHERRY, _RAW_PLUM,         # reel 0 — coin on row 0
        _RAW_LEMON, _RAW_COLLECTOR, _RAW_BELL,     # reel 1 — collector on row 1
        _RAW_BAR, _RAW_WATERMELON, _RAW_COIN,      # reel 2 — coin on row 2
    ]
    # Base-game coin values (2 coins, reel-major), then the round: with 8 empty
    # cells and nothing ever landing, it ends after the configured 3 respins.
    set_rng(grid_draws + [_RAW_BASE_COIN_X1] * 2 + [_RAW_NOTHING_LANDS] * (8 * 3))

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    hold_and_win = body["hold_and_win"]
    assert hold_and_win is not None
    assert hold_and_win["triggered"] is True
    # The round opens with ONE collector, standing exactly where it landed
    # (row 1 of the middle reel) — and nothing else.
    assert hold_and_win["initial"] == [
        {"row": 1, "col": 1, "value": 0, "kind": "collector"}
    ]
    assert len(hold_and_win["respins"]) == 3
    assert all(r["landed"] == [] for r in hold_and_win["respins"])
    assert hold_and_win["full_grid"] is False
    # A lone collector with no coins collected is worth nothing.
    assert hold_and_win["total_win"] == 0


async def test_coins_on_all_three_reels_alone_do_not_open_the_round(api_client, set_rng):
    """Three coins used to be the trigger; now the collector is what opens the
    round, and coins without one just multiply whatever line they land on."""
    session_id = await _start_session(api_client)
    set_rng([
        _RAW_COIN, _RAW_CHERRY, _RAW_PLUM,         # reel 0
        _RAW_LEMON, _RAW_COIN, _RAW_BELL,          # reel 1 — a COIN, not a collector
        _RAW_BAR, _RAW_WATERMELON, _RAW_COIN,      # reel 2
    ] + [_RAW_BASE_COIN_X1] * 3)

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["hold_and_win"] is None
    assert body["coin_multiplier"]["multiplier_sum"] == 3   # the coins still drew values


async def test_every_collector_is_worth_the_sum_of_the_coins(api_client, set_rng):
    """Two collectors pay the coin total twice — that's the round's whole
    shape, and the reason the collector reel lands rarer than the coin ones."""
    from decimal import Decimal

    from app.features import default_registry
    from app.features.base import FeatureContext
    from app.engine.types import SpinGrid
    from app.seed.lucky_joker_3h3 import build_game_config
    from tests.fakes import FakeRNG

    _, config = build_game_config()
    params = next(
        fc.params for fc in config.feature_configs if fc.feature_type == "hold_and_win"
    )
    # 3 reels x 3 rows, one coin per reel (the trigger); the middle one turns
    # into the round's first collector.
    grid = SpinGrid(
        reels=[
            ["coin", "cherry", "plum"],
            ["lemon", "coin", "bell"],
            ["bar", "watermelon", "coin"],
        ],
        draws=[],
    )
    # NB: this builds the config in memory, so the weight dicts keep the seed's
    # own key order (unlike the API tests above, which read them back through
    # jsonb) — {"blank": .., "coin": ..} means a LOW raw draw is "blank":
    #   coin reels      blank[0,84)  coin[84,100)
    #   collector reel  blank[0,93)  coin[93,100)
    #   coin values     "1" is first, so a value draw of 0 is x1.
    # Only the collector is locked at the start — the trigger coins do NOT
    # stick in this mode — so respin 1 walks all 8 remaining cells in
    # reel-major order (reel 0 rows 0..2, reel 1 rows 0 and 2, reel 2 rows 0..2).
    rng = FakeRNG([
        90, 0,      # (0,0) lands, draws x1
        90, 0,      # (0,1) lands, draws x1
        0,          # (0,2) nothing
        95,         # (1,0) lands a COLLECTOR (no value draw)
        0,          # (1,2) nothing
        0, 0, 0,    # reel 2 — nothing
        # That landing reset the counter, so 3 more respins run over the 5
        # cells still empty, and nothing lands in any of them.
    ] + [0] * (5 * 3))
    feature = default_registry.get("hold_and_win")
    ctx = FeatureContext(session_state={}, rng=rng, bet_amount=Decimal(BET_AMOUNT), grid=grid)
    result = feature.execute(ctx, params)

    assert result.details["collector_count"] == 2
    assert result.details["coin_total"] == "2"          # two x1 coins
    # ...so the round pays 2 x 2 = 4 times the bet, not 2.
    assert result.win_amount == Decimal(2 * 2 * BET_AMOUNT)


async def test_three_scatters_pay_and_open_the_free_spins_round(api_client, set_rng):
    session_id = await _start_session(api_client)
    # One scatter per reel (max_per_reel=1, so no reel-cap redraw consumes
    # extra RNG), on a different row each time.
    set_rng([
        _RAW_SCATTER, _RAW_LEMON, _RAW_PLUM,       # reel 0
        _RAW_BAR, _RAW_SCATTER, _RAW_CHERRY,       # reel 1
        _RAW_LEMON, _RAW_PLUM, _RAW_SCATTER,       # reel 2
    ])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    # Count win: scatters pay against the WHOLE bet, not a per-line share.
    assert len(body["count_wins"]) == 1
    assert body["count_wins"][0]["symbol"] == "scatter"
    assert body["total_win"] == 3 * BET_AMOUNT

    # ...and the same 3 scatters open the round.
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_remaining"] == 10
