"""Integration coverage for "savannah-kings" (GDD-03) through the API.

Pinned here: the lion only expands inside free spins; a mask it expands over
still counts (retrigger + scatter pay) while the client gets the grid as it
landed; both purchases (GDD §6.4) — the purchase spin shows only its own
trigger, pays nothing itself, and a bought wheel spin draws on the second
weight set.
"""

from decimal import Decimal

import pytest

from app.features.base import FeatureContext
from app.features.wheel_of_fortune import WheelOfFortuneFeature
from app.seed import savannah_kings as seed
from tests.fakes import FakeRNG

BET = 600

# Cumulative reel weights in seed order: elephant[0,40) buffalo[40,90)
# leopard[90,150) zebra[150,220) a[220,310) k[310,410) q[410,520) j[520,640),
# then wild (reels 2-4 only), scatter, paw (reels 1, 3, 5 only).
_ELEPHANT, _ZEBRA, _A, _K, _Q, _J = 0, 150, 220, 310, 410, 520
_WILD = 640
_SCATTER_R15 = 640           # reels 1 and 5: no wild before it
_SCATTER_FS_R24 = 640 + seed.FS_WILD   # reels 2-4 in free spins: after the lion


@pytest.fixture(autouse=True)
async def _seed():
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await seed.get_or_seed_active_config(db)


async def _start(api_client) -> tuple[str, int]:
    body = (await api_client.post("/api/v1/session/start", json={"game_id": "savannah-kings"})).json()
    return body["session_id"], body["balance"]


async def test_base_game_lion_stays_one_cell(api_client, set_rng):
    session_id, _ = await _start(api_client)
    set_rng([
        _K, _Q, _J,
        _WILD, _A, _ZEBRA,
        _J, _K, _Q,
        _A, _J, _K,
        _Q, _A, _J,
    ])
    body = (await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET})).json()
    assert body["wild_events"] == []
    assert body["grid"][0][1] == "wild" and body["grid"][1][1] == "a"


async def test_jackpot_chance_purchase_lands_three_paws_and_pays_the_wheel(api_client):
    session_id, balance = await _start(api_client)
    body = (await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "jackpot_chance_buy", "bet_amount": BET},
    )).json()
    grid = body["grid"]
    cells = [(r, c) for r in range(3) for c in range(5)]
    assert sorted(c for r, c in cells if grid[r][c] == "paw") == [0, 2, 4]
    assert not any(grid[r][c] == "scatter" for r, c in cells)
    wheel = body["wheel_of_fortune"]
    assert wheel["tier"] in seed.JACKPOT_VALUES
    assert wheel["win_amount"] == seed.JACKPOT_VALUES[wheel["tier"]] * BET
    assert body["total_win"] == wheel["win_amount"]   # the purchase spin itself pays nothing
    assert body["feature"] is None
    assert body["balance"] == balance - seed.JACKPOT_CHANCE_BUY_COST * BET + wheel["win_amount"]


async def test_free_spins_purchase_then_a_lion_over_a_mask_retriggers(api_client, set_rng):
    session_id, _ = await _start(api_client)
    body = (await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "free_spins_buy", "bet_amount": BET},
    )).json()
    grid = body["grid"]
    cells = [(r, c) for r in range(3) for c in range(5)]
    assert sum(grid[r][c] == "scatter" for r, c in cells) == 3
    assert not any(grid[r][c] == "paw" for r, c in cells)
    assert body["total_win"] == 0
    assert body["feature"]["spins_remaining"] == 10

    # Free spin: masks on reels 1 and 5, and on reel 2 under a lion that
    # expands over the whole reel.
    set_rng([
        _SCATTER_R15, _K, _Q,
        _WILD, _A, _SCATTER_FS_R24,
        _J, _K, _Q,
        _A, _J, _K,
        _Q, _A, _SCATTER_R15,
    ])
    body = (await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET})).json()
    assert body["wild_events"] == [{"reel": 1, "event": "expanded"}]
    assert body["grid"][2][1] == "scatter"          # the grid as it landed
    assert body["feature"]["triggered"] is True     # retrigger counted the covered mask
    assert body["feature"]["spins_awarded"] == 5
    assert body["feature"]["spins_remaining"] == 9 + 5
    scatter_pay = [w for w in body["count_wins"] if w["symbol"] == "scatter"]
    assert scatter_pay and scatter_pay[0]["amount"] == 2 * BET


def test_bought_wheel_spin_uses_the_purchase_weights():
    """Drum order starts GRAND (natural weight 24, bought 12) then MINI: the
    same raw draw 12 is still GRAND naturally but MINI when bought."""
    wheel = WheelOfFortuneFeature()

    def draw(bought):
        ctx = FeatureContext(session_state={}, rng=FakeRNG([12]), bet_amount=Decimal(1), symbols=[],
                             grid=None, is_bonus_buy=bought)
        return wheel.execute(ctx, seed.WHEEL_PARAMS).details["tier"]

    assert draw(False) == "grand"
    assert draw(True) == "mini"


def test_wheel_tier_odds_match_the_gdd():
    for key, odds in (("weight", {"mini": 60, "minor": 28, "major": 10, "grand": 2}),
                      ("buy_weight", {"mini": 76, "minor": 17.5, "major": 5.5, "grand": 1})):
        total = sum(s[key] for s in seed.WHEEL_SEGMENTS)
        for tier, pct in odds.items():
            got = sum(s[key] for s in seed.WHEEL_SEGMENTS if s["tier"] == tier) / total * 100
            assert got == pytest.approx(pct)
    assert [s["tier"] for s in seed.WHEEL_SEGMENTS].count("mini") == 6
    assert len(seed.WHEEL_SEGMENTS) == 12
