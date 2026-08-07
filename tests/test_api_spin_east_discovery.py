"""Integration coverage for the "east-discovery" game's three mechanics
(Hold & Win, coin_multiplier, probabilistic expanding_wild) actually firing
end-to-end through POST /api/v1/spin — see tests/test_api_spin.py for the
equivalent Amy's Fruit Farm coverage this mirrors (same FakeRNG/set_rng
conventions, deterministic forced symbols via hand-derived reel-weight
ranges)."""

VALID_SYMBOLS = {
    "scatter", "wild", "collector_tiger", "coin",
    "rare_cat", "rare_fish", "rare_papirus", "lp_blue", "lp_green", "lp_pink", "lp_red",
}

# Cumulative reel weights from the seed (app/seed/east_discovery.py's
# _SYMBOLS order): scatter[0,3) wild[3,4) collector_tiger[4,7) coin[7,11)
# rare_cat[11,19) rare_fish[19,25) rare_papirus[25,30) lp_blue[30,54)
# новые диапазоны: scatter[0,777) wild[777,870) collector[870,1149)
# coin[1149,1521) lp_blue[3288,5520) ... total 11100 (скаттер = 7% всех дро).
_RAW_LP_BLUE = 4000
_RAW_WILD = 800
_RAW_COLLECTOR = 900
_RAW_COIN = 1200

BET_AMOUNT = 55000


async def _start_session(api_client) -> str:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "east-discovery"})
    return response.json()["session_id"]


async def test_spin_response_shape_is_well_formed(api_client, set_rng):
    session_id = await _start_session(api_client)
    set_rng([_RAW_LP_BLUE] * 15)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["grid"]) == 3
    assert all(len(row) == 5 for row in body["grid"])
    assert all(symbol in VALID_SYMBOLS for row in body["grid"] for symbol in row)
    assert body["balance"] == 1_000_000 - BET_AMOUNT + body["total_win"]
    assert body["hold_and_win"] is None
    assert body["coin_multiplier"] is None


async def test_three_collector_tigers_trigger_hold_and_win(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Exactly 1 collector_tiger per reel on reels 0, 2, 4 (respects its
    # max_per_reel=1 cap — no reel-cap redraw to account for), lp_blue
    # everywhere else. Reel-major order: 3 raw draws (row0, row1, row2) per reel.
    draws = [
        _RAW_COLLECTOR, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 0
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 1
        _RAW_COLLECTOR, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 2
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 3
        _RAW_COLLECTOR, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 4
    ]
    # Hold & Win's "guaranteed coins" mode (start_empty + respin_coin_count_
    # weights): each respin draws (a) a coin count via weighted_pick over
    # {"1":50,"2":30,"3":20} (all single-char keys, so JSONB's length-then-
    # lex reorder leaves this at insertion order — raw=80 lands in "3"'s
    # cumulative range [80,100)), (b) that many position picks via a plain
    # randbelow(remaining) per pick (raw=0 -> always the next remaining
    # empty cell, in (reel, row) row-major-within-reel-major order), and (c)
    # that many value draws via weighted_pick over
    # _HOLD_AND_WIN_VALUE_WEIGHTS = {"0":50,"1":40,"2":25,"5":15,"10":10,
    # "25":6,"50":3,"100":1} (also already in JSONB order since all its
    # numeric-string keys already sort correctly by length-then-lex — raw=0
    # lands in "0", the no-multiplier bucket). 15 cells / 3 per respin = 5
    # respins to fill the grid exactly.
    respin_draws = [80, 0, 0, 0, 0, 0, 0] * 5
    set_rng(draws + respin_draws)

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    collector_count = sum(row.count("collector_tiger") for row in body["grid"])
    assert collector_count == 3
    assert body["hold_and_win"] is not None
    assert body["hold_and_win"]["triggered"] is True
    assert len(body["hold_and_win"]["respins"]) == 5
    assert all(len(r["landed"]) == 3 for r in body["hold_and_win"]["respins"])
    assert body["hold_and_win"]["full_grid"] is True
    assert body["hold_and_win"]["total_win"] == 0  # every coin landed as "0" (no multiplier)
    assert body["balance"] == 1_000_000 - BET_AMOUNT + body["total_win"]


async def test_coin_and_collector_with_a_line_win_triggers_coin_multiplier(api_client, set_rng):
    session_id = await _start_session(api_client)

    # 1 coin (reel 0) + 1 collector_tiger (reel 2, below Hold & Win's
    # trigger_count=3 so that doesn't also fire) + lp_blue filling the rest,
    # guaranteeing a line win on payline #1 (row 1, all lp_blue).
    draws = [
        _RAW_COIN, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 0
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 1
        _RAW_COLLECTOR, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 2
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 3
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 4
    ]
    # coin_multiplier draws one weighted_pick over the seed's 7-tier table
    # ({"1":40,"2":25,"5":15,"10":10,"25":6,"50":3,"100":1}, total 100) for
    # the single coin — raw 80 lands in the "10" bucket ([80,90)).
    set_rng(draws + [80])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    assert body["hold_and_win"] is None  # only 1 collector_tiger, below trigger_count=3
    assert body["coin_multiplier"] is not None
    assert body["coin_multiplier"]["multiplier_sum"] == 10
    assert body["coin_multiplier"]["positions"] == [{"row": 0, "col": 0, "value": 10}]
    assert body["coin_multiplier"]["applied"] is True
    assert len(body["line_wins"]) >= 1


async def test_coin_without_collector_still_shows_its_value_but_is_not_applied(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Same shape as above but no collector_tiger anywhere (lp_blue instead) —
    # a coin still lands and a line win still happens, but with no collector
    # on the grid the multiplier can't pay out. Per product, the coin must
    # still show its own drawn value regardless (it's not gated behind a
    # win) — only whether it *pays* is gated.
    draws = [
        _RAW_COIN, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 0
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 1
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 2
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 3
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 4
    ]
    set_rng(draws + [80])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    assert body["hold_and_win"] is None
    assert body["coin_multiplier"] is not None
    assert body["coin_multiplier"]["positions"] == [{"row": 0, "col": 0, "value": 10}]
    assert body["coin_multiplier"]["applied"] is False
    assert len(body["line_wins"]) >= 1


async def test_dev_force_hold_and_win_triggers_via_the_normal_path(api_client, set_rng):
    session_id = await _start_session(api_client)

    # All lp_blue by RNG — /dev/force-hold-and-win overrides reels 0/2/4 row 0
    # to collector_tiger *after* the normal draw, so this is really a normal
    # spin/evaluate_spin/hold_and_win.is_triggered() path underneath, just
    # with a rigged grid (no bonus-buy cost or bypassed feature.execute()).
    draws = [_RAW_LP_BLUE] * 15
    # Hold & Win's "guaranteed coins" mode — see
    # test_three_collector_tigers_trigger_hold_and_win's note on this exact
    # sequence: raw=80 always draws a count of 3, raw=0 always picks the
    # next remaining empty cell and the "0" (no-multiplier) value bucket —
    # 5 respins of 3 fills the 15-cell grid deterministically.
    set_rng(draws + [80, 0, 0, 0, 0, 0, 0] * 5)

    response = await api_client.post(
        "/api/v1/dev/force-hold-and-win", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["grid"][0][0] == "collector_tiger"
    assert body["grid"][0][2] == "collector_tiger"
    assert body["grid"][0][4] == "collector_tiger"
    assert body["hold_and_win"] is not None
    assert body["hold_and_win"]["triggered"] is True
    assert body["balance"] == 1_000_000 - BET_AMOUNT + body["total_win"]


async def test_wild_expands_and_schedules_a_walk(api_client, set_rng):
    session_id = await _start_session(api_client)

    # Wild lands only on reel 2 (row 0), lp_blue everywhere else.
    draws = [
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 0
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 1
        _RAW_WILD, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 2
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 3
        _RAW_LP_BLUE, _RAW_LP_BLUE, _RAW_LP_BLUE,  # reel 4
    ]
    # expanding_wild's expand_chance=0.5 and walk_chance=0.5 (seed config)
    # each draw one weighted_pick over [500, 500] — raw 0 hits both times
    # (expand, then advance the walk).
    set_rng(draws + [0, 0])

    response = await api_client.post(
        "/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT}
    )
    body = response.json()

    # Reel 2 (0-indexed) expanded to wild top-to-bottom; every payline now
    # runs lp_blue/wild/lp_blue/lp_blue/lp_blue -> a full 5-of-a-kind on all
    # 11 lines (pays[5]=10, bet_per_line = 55000/11 = 5000).
    assert all(row[2] == "wild" for row in body["grid"])
    assert body["wild_events"] == [{"reel": 2, "event": "expanded"}]
    assert len(body["line_wins"]) == 11
    assert body["total_win"] == 550_000
    assert body["balance"] == 1_000_000 - BET_AMOUNT + 550_000
