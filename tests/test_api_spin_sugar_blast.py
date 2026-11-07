"""Integration coverage for "sugar-blast" (GDD-05) through the API.

The game is config only (GDD §12), so this pins the config onto the GDD
rules: base-game bombs multiply the line pay by their sum (§5.2 example);
free spins run the GDD-04 accumulator — only a winning spin's bombs add to
TOTAL MULTIPLIER, a win without bombs pays as is (§6.2); the three
purchases (§8) land only their own trigger, pay nothing on the purchase
spin; Super Free Spins show a bomb on every spin.
"""

import pytest

from app.seed import sugar_blast as seed

BET = 600   # line pay of a 3x cupcake (20 coins) = 1x bet = 600

# Cumulative base weights in seed order: h1[0,40) h2[40,90) h3[90,150)
# h4[150,220) l1[220,310) l2[310,410) l3[410,520) l4[520,640), then wild
# (reels 2-4), scatter, bomb, wrapper (reels 1, 3, 5).
_H1, _H2, _H3, _L1, _L2, _L3, _L4 = 0, 40, 90, 220, 310, 410, 520
_BOMB_R4_BASE = 640 + 26 + seed.SCATTER_W       # reel 4: after wild + scatter
_BOMB_R5_BASE = 640 + seed.SCATTER_W            # reel 5: no wild
_BOMB_R5_FS = 640 + seed.SCATTER_W              # reel 5 in free spins too
# Bomb value draws, out of 10 000: x5 = [6600, 7800), x10 = [9000, 9400).
_X5, _X10 = 6600, 9000


@pytest.fixture(autouse=True)
async def _seed():
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await seed.get_or_seed_active_config(db)


async def _start(api_client) -> tuple[str, int]:
    body = (await api_client.post("/api/v1/session/start", json={"game_id": "sugar-blast"})).json()
    return body["session_id"], body["balance"]


async def _spin(api_client, session_id):
    return (await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET})).json()


async def _buy(api_client, session_id, feature_id):
    return (await api_client.post(
        "/api/v1/feature/buy", json={"session_id": session_id, "feature_id": feature_id, "bet_amount": BET},
    )).json()


def _cells(grid, code):
    return [(r, c) for r in range(3) for c in range(5) if grid[r][c] == code]


async def test_base_bombs_multiply_the_line_pay_by_their_sum(api_client, set_rng):
    """GDD §5.2 example: a 1x line win with bombs x5 and x10 pays 15x."""
    session_id, _ = await _start(api_client)
    set_rng([
        _L1, _H1, _L2,
        _L3, _H1, _L4,
        _H2, _H1, _H3,
        _BOMB_R4_BASE, _L2, _L3,
        _L4, _L1, _BOMB_R5_BASE,
        _X5, _X10,
    ])
    body = await _spin(api_client, session_id)
    assert [w["symbol"] for w in body["line_wins"]] == ["h1"]
    assert body["coin_multiplier"]["multiplier_sum"] == 15
    assert body["coin_multiplier"]["applied"] is True
    assert body["total_win"] == BET * 15


async def test_free_spins_accumulate_only_winning_bombs(api_client, set_rng):
    session_id, _ = await _start(api_client)
    body = await _buy(api_client, session_id, "free_spins_buy")
    grid = body["grid"]
    assert len(_cells(grid, "scatter")) == 3
    assert not _cells(grid, "wrapper") and not _cells(grid, "bomb")
    assert body["total_win"] == 0
    assert body["feature"]["spins_remaining"] == 15

    win_reels = [_L1, _H1, _L2, _L3, _H1, _L4, _H2, _H1, _H3, _L1, _L2, _L3, _L4, _L1]
    # 1) line win + bomb x5: TOTAL MULTIPLIER 1 + 5 = 6, the win x6.
    set_rng([*win_reels, _BOMB_R5_FS, _X5])
    body = await _spin(api_client, session_id)
    assert body["coin_multiplier"]["round_multiplier"] == 6
    assert body["total_win"] == BET * 6

    # 2) line win, no bomb: paid as is, the multiplier is neither applied nor changed.
    set_rng([*win_reels, _L3])
    body = await _spin(api_client, session_id)
    assert body["coin_multiplier"] is None
    assert body["total_win"] == BET

    # 3) bomb without a line win: not counted.
    no_win = [_L1, _L3, _L2, *win_reels[3:]]
    set_rng([*no_win, _BOMB_R5_FS, _X10])
    body = await _spin(api_client, session_id)
    assert body["total_win"] == 0
    assert body["coin_multiplier"]["applied"] is False
    assert body["coin_multiplier"]["round_multiplier"] == 6
    assert body["feature"]["spins_remaining"] == 12


async def test_super_free_spins_show_a_bomb_every_spin(api_client):
    session_id, balance = await _start(api_client)
    body = await _buy(api_client, session_id, "super_free_spins_buy")
    assert body["balance"] == balance - seed.SUPER_FREE_SPINS_BUY_COST * BET
    assert body["feature"]["spins_remaining"] == 15
    for _ in range(6):
        body = await _spin(api_client, session_id)
        assert _cells(body["grid"], "bomb")


async def test_jackpot_chance_lands_three_wrappers_and_pays_only_the_wheel(api_client):
    session_id, balance = await _start(api_client)
    body = await _buy(api_client, session_id, "jackpot_chance_buy")
    grid = body["grid"]
    assert sorted(c for _, c in _cells(grid, "wrapper")) == [0, 2, 4]
    assert not _cells(grid, "scatter") and not _cells(grid, "bomb")
    wheel = body["wheel_of_fortune"]
    assert wheel["win_amount"] == seed.JACKPOT_VALUES[wheel["tier"]] * BET
    assert body["total_win"] == wheel["win_amount"]
    assert body["balance"] == balance - seed.JACKPOT_CHANCE_BUY_COST * BET + wheel["win_amount"]


def test_wheel_and_bomb_tables_match_the_gdd():
    for key, odds in (("weight", {"mini": 60, "minor": 28, "major": 10, "grand": 2}),
                      ("buy_weight", {"mini": 76, "minor": 17.5, "major": 5.5, "grand": 1})):
        total = sum(s[key] for s in seed.WHEEL_SEGMENTS)
        for tier, pct in odds.items():
            got = sum(s[key] for s in seed.WHEEL_SEGMENTS if s["tier"] == tier) / total * 100
            assert got == pytest.approx(pct)
    assert len(seed.WHEEL_SEGMENTS) == 12
    weights = seed.BOMB_VALUE_WEIGHTS
    mean = sum(int(v) * w for v, w in weights.items()) / sum(weights.values())
    assert mean == pytest.approx(4.8, abs=0.05)
