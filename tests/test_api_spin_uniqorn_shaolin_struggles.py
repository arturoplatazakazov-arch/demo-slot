"""Integration coverage for the "uniqorn-shaolin-struggles" game end-to-end
through POST /api/v1/spin — same FakeRNG/set_rng conventions as
tests/test_api_spin_lucky_joker_3h3.py, whose 3x3 Hold & Win mechanic this
game shares.

What's pinned here is what this game does DIFFERENTLY from that donor:
  * there is no scatter symbol and no free_spins feature at all, so a session
    reports no free-spins trigger and a spin can never come back with one;
  * the only bonus-buy product is the Hold & Win round itself.
Plus the parts of the shared mechanic worth re-pinning against this game's own
seed: 5 paylines (three rows + both diagonals), a COIN that multiplies a
winning LINE and pays nothing without one, and a COLLECTOR on the middle reel
that opens the round.
"""

import pytest

# Cumulative reel weights from the seed (app/seed/uniqorn_shaolin_struggles.py's
# _SYMBOLS order): noodles[0,26) bamboo[26,48) nunchaku[48,66) bucket[66,81)
# bell[81,92) dragon[92,99) pagoda[99,103) coin[103,111), total 111 — plus, on
# the MIDDLE reel only, collector[111,118) (its per-reel weights are [0, 7, 0],
# so the outer reels total 111 and every range above is unchanged there).
_RAW_NOODLES = 0
_RAW_BAMBOO = 26
_RAW_NUNCHAKU = 48
_RAW_BUCKET = 66
_RAW_BELL = 81
_RAW_DRAGON = 92
_RAW_PAGODA = 99
_RAW_COIN = 103
_RAW_COLLECTOR = 112   # middle reel only

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
_PAY_NOODLES = 8.9
_PAY_PAGODA = 229


@pytest.fixture(autouse=True)
async def _seed_game():
    """tests/conftest.py's api_client only seeds a few games explicitly; seed
    this one here rather than relying on a previous dev-server run having left
    it in the shared Postgres."""
    from app.core.db import AsyncSessionLocal
    from app.seed.uniqorn_shaolin_struggles import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start_session(api_client) -> dict:
    response = await api_client.post(
        "/api/v1/session/start", json={"game_id": "uniqorn-shaolin-struggles"}
    )
    return response.json()


async def _start_session_id(api_client) -> str:
    return (await _start_session(api_client))["session_id"]


async def _spin(api_client, session_id):
    return await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )


async def test_session_reports_no_free_spins_trigger(api_client):
    """No scatter, no free spins: the client's anticipation logic keys off this
    field, and it has to come back empty rather than pointing at a symbol the
    reels never deal."""
    body = await _start_session(api_client)
    assert body["free_spins_trigger"] is None
    codes = {symbol["code"] for symbol in body["symbols"]}
    assert codes == {
        "noodles", "bamboo", "nunchaku", "bucket", "bell", "dragon", "pagoda",
        "coin", "collector",
    }


async def test_three_matching_symbols_pay_the_row_they_landed_on(api_client, set_rng):
    session_id = await _start_session_id(api_client)
    # Reel-major (3 raw draws per reel, row 0..2): noodles across the middle
    # row, every other row deliberately mismatched so exactly one line pays.
    set_rng([
        _RAW_BAMBOO, _RAW_NOODLES, _RAW_NUNCHAKU,   # reel 0
        _RAW_BUCKET, _RAW_NOODLES, _RAW_BELL,       # reel 1
        _RAW_DRAGON, _RAW_NOODLES, _RAW_PAGODA,     # reel 2
    ])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert len(body["line_wins"]) == 1
    win = body["line_wins"][0]
    assert win["symbol"] == "noodles"
    assert win["payline"] == 1  # payline 1 is the middle row — first in the seed's list
    # No coin on the grid, so the line pays flat: a fifth of the bet per line.
    assert body["coin_multiplier"] is None
    assert body["total_win"] == _PAY_NOODLES * BET_PER_LINE
    assert body["balance"] == START_BALANCE - BET_AMOUNT + _PAY_NOODLES * BET_PER_LINE
    # Nothing here can award a bonus round — the game has none to award.
    assert body["feature"] is None


async def test_diagonal_payline_pays(api_client, set_rng):
    session_id = await _start_session_id(api_client)
    # pagoda down the top-left -> bottom-right diagonal (payline 4, [0, 1, 2]).
    set_rng([
        _RAW_PAGODA, _RAW_BAMBOO, _RAW_NUNCHAKU,    # reel 0 — pagoda on row 0
        _RAW_NOODLES, _RAW_PAGODA, _RAW_BELL,       # reel 1 — pagoda on row 1
        _RAW_DRAGON, _RAW_BAMBOO, _RAW_PAGODA,      # reel 2 — pagoda on row 2
    ])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert len(body["line_wins"]) == 1
    assert body["line_wins"][0]["symbol"] == "pagoda"
    assert body["line_wins"][0]["payline"] == 4
    assert body["total_win"] == _PAY_PAGODA * BET_PER_LINE
    # A high-tier 3-of-a-kind is the only popup this game's server can send.
    assert body["popup"]["type"] == "bigWin"


async def test_a_coin_multiplies_the_winning_line(api_client, set_rng):
    session_id = await _start_session_id(api_client)
    # noodles across the middle row + one coin parked on a losing row. Coins
    # sit on reels 0 and 1 only, so the round doesn't also open.
    set_rng([
        _RAW_COIN, _RAW_NOODLES, _RAW_NUNCHAKU,     # reel 0 — coin on row 0
        _RAW_BUCKET, _RAW_NOODLES, _RAW_BELL,       # reel 1
        _RAW_DRAGON, _RAW_NOODLES, _RAW_PAGODA,     # reel 2
    ] + [_RAW_BASE_COIN_X5])                        # the coin draws x5

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["hold_and_win"] is None             # no collector on the middle reel
    assert body["coin_multiplier"]["applied"] is True
    assert body["coin_multiplier"]["multiplier_sum"] == 5
    assert body["coin_multiplier"]["positions"] == [
        {"row": 0, "col": 0, "value": 5, "kind": "5"}
    ]
    # The whole line pay is multiplied — not the coin paying on its own.
    assert body["total_win"] == _PAY_NOODLES * BET_PER_LINE * 5


async def test_a_coin_pays_nothing_without_a_winning_line(api_client, set_rng):
    """The coin shows its value on every spin it lands (that's the tease), but
    it only ever pays by multiplying a line."""
    session_id = await _start_session_id(api_client)
    set_rng([
        _RAW_COIN, _RAW_NOODLES, _RAW_NUNCHAKU,     # reel 0
        _RAW_BUCKET, _RAW_BELL, _RAW_BAMBOO,        # reel 1 — nothing lines up
        _RAW_DRAGON, _RAW_PAGODA, _RAW_BUCKET,      # reel 2
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
    """Jackpot coins can land in the base game too — a GRAND coin multiplies
    the line by 1000, which is why its weight is 2 in 9168."""
    session_id = await _start_session_id(api_client)
    set_rng([
        _RAW_COIN, _RAW_NOODLES, _RAW_NUNCHAKU,
        _RAW_BUCKET, _RAW_NOODLES, _RAW_BELL,
        _RAW_DRAGON, _RAW_NOODLES, _RAW_PAGODA,
    ] + [_RAW_BASE_COIN_GRAND])

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["coin_multiplier"]["positions"][0]["kind"] == "grand"
    assert body["coin_multiplier"]["multiplier_sum"] == 1000
    assert body["total_win"] == _PAY_NOODLES * BET_PER_LINE * 1000


async def test_a_collector_plus_coins_on_the_outer_reels_opens_the_round(api_client, set_rng):
    session_id = await _start_session_id(api_client)
    # The trigger: a collector on the middle reel, a coin on each of the outer
    # two. A coin on the middle reel is NOT what opens it.
    grid_draws = [
        _RAW_COIN, _RAW_NOODLES, _RAW_NUNCHAKU,     # reel 0 — coin on row 0
        _RAW_BAMBOO, _RAW_COLLECTOR, _RAW_BELL,     # reel 1 — collector on row 1
        _RAW_DRAGON, _RAW_BUCKET, _RAW_COIN,        # reel 2 — coin on row 2
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
    """The collector is what opens the round; coins without one just multiply
    whatever line they land on."""
    session_id = await _start_session_id(api_client)
    set_rng([
        _RAW_COIN, _RAW_NOODLES, _RAW_NUNCHAKU,     # reel 0
        _RAW_BAMBOO, _RAW_COIN, _RAW_BELL,          # reel 1 — a COIN, not a collector
        _RAW_DRAGON, _RAW_BUCKET, _RAW_COIN,        # reel 2
    ] + [_RAW_BASE_COIN_X1] * 3)

    response = await _spin(api_client, session_id)
    assert response.status_code == 200
    body = response.json()

    assert body["hold_and_win"] is None
    assert body["coin_multiplier"]["multiplier_sum"] == 3   # the coins still drew values


async def test_buying_the_round_is_the_only_product_and_resolves_instantly(api_client, set_rng):
    """With no free-spins round in the game, hold_and_win_buy is the whole
    bonus_buy menu — and it resolves in the one call, like every other bought
    Hold & Win."""
    session_id = await _start_session_id(api_client)
    buy_bet = 10000                                  # 50x that is half the starting balance
    # The purchase spin's own reels: all bamboo (no win, no natural trigger),
    # then a round in which nothing ever lands — 8 empty cells x 3 respins.
    set_rng([_RAW_BAMBOO] * 9 + [_RAW_NOTHING_LANDS] * (8 * 3))

    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "hold_and_win_buy", "bet_amount": buy_bet},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["hold_and_win"]["triggered"] is True
    # Bought rounds open on a collector too (the feature falls back to the
    # middle row when the forced grid has none), so the client's round playback
    # has the same shape as a natural trigger's.
    assert body["hold_and_win"]["initial"] == [
        {"row": 1, "col": 1, "value": 0, "kind": "collector"}
    ]
    assert body["feature"] is None                   # nothing carries into later spins
    assert body["balance"] == START_BALANCE - 50 * buy_bet + body["total_win"]


async def test_buying_free_spins_is_not_a_product_of_this_game(api_client):
    session_id = await _start_session_id(api_client)
    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": 10000},
    )
    assert response.status_code == 404
