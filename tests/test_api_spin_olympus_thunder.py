"""Integration coverage for "olympus-thunder" (GDD-04) through the real API:
scatter pays 8+, orbs multiplying a winning series, the free-spins trigger
with its TOTAL MULTIPLIER, and the three-SKU bonus buy.

FakeRNG feeds raw `randbelow` results. Base weights are scaled x1000 by
app/engine/scatter_tumble.py:WeightTable, cumulative in seed order:
helmet[0,4000) lyre[4000,9000) amphora[9000,15000) wreath[15000,22000)
ruby[22000,31000) amethyst[31000,41000) emerald[41000,52000)
sapphire[52000,64000) citrine[64000,77000) scatter[77000,78500)
orb[78500,79100) eagle[79100,79600). An orb draw is followed by one value
draw: 0 -> x2, 30000 -> x3. Grid draws are reel-major (reel 0 rows 0-4, ...).
"""

import pytest

HELMET, LYRE, AMPHORA, WREATH = 0, 4000, 9000, 15000
RUBY, AMETHYST, EMERALD = 22000, 31000, 41000
SCATTER, ORB, EAGLE = 77000, 78500, 79100
FS_ORB = 84100  # FS table: sapphire 14 / citrine 17 / scatter 1.1 shift the tail
ORB_X2, ORB_X3 = 0, 30000

BET = 2000
START_BALANCE = 1_000_000


@pytest.fixture(autouse=True)
async def _seed():
    from app.core.db import AsyncSessionLocal
    from app.seed.olympus_thunder import get_or_seed_active_config

    async with AsyncSessionLocal() as db:
        await get_or_seed_active_config(db)


async def _start(api_client) -> dict:
    response = await api_client.post("/api/v1/session/start", json={"game_id": "olympus-thunder"})
    assert response.status_code == 200
    return response.json()


async def _spin(api_client, session_id):
    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET})
    assert response.status_code == 200, response.text
    return response.json()


def _no_win_fill(n):
    # five regular codes round-robin: none reaches 8 within 30 cells
    codes = [LYRE, AMPHORA, WREATH, RUBY, AMETHYST]
    return [codes[i % 5] for i in range(n)]


async def test_session_start_exposes_rules(api_client):
    body = await _start(api_client)
    rules = body["game_rules"]
    assert rules["mechanic"] == "scatter_tumble"
    assert [p["buy_id"] for p in rules["bonus_buy"]["products"]] == ["free_spins", "super_free_spins", "jackpot_chance"]
    assert len(rules["jackpot"]["sectors"]) == 12


async def test_no_win(api_client, set_rng):
    session_id = (await _start(api_client))["session_id"]
    set_rng(_no_win_fill(30))
    body = await _spin(api_client, session_id)
    assert len(body["grid"]) == 5 and all(len(r) == 6 for r in body["grid"])
    assert body["tumble"]["steps"] == []
    assert body["total_win"] == 0
    assert body["balance"] == START_BALANCE - BET


async def test_eight_helmets_times_orb(api_client, set_rng):
    session_id = (await _start(api_client))["session_id"]
    # reel 0-1: 8 helmets + orb x2 on reel 1 row 3, rest of the board no-win
    initial = [HELMET] * 5 + [HELMET, HELMET, HELMET, ORB, ORB_X2] + _no_win_fill(21)
    # 8 refills (reel 0: 5 cells, reel 1: 3 cells) that cannot win
    refill = [EMERALD] * 7 + [AMETHYST]
    set_rng(initial + refill)
    body = await _spin(api_client, session_id)
    t = body["tumble"]
    assert len(t["steps"]) == 1
    assert t["steps"][0]["wins"][0]["symbol"] == "helmet"
    assert t["base_win"] == 10 * BET
    assert t["orbs"] == [{"col": 1, "row": 3, "value": 2}]  # stays put: nothing below it was removed
    assert t["applied_multiplier"] == 2
    assert body["total_win"] == 20 * BET


async def test_four_scatters_open_free_spins_and_total_multiplier(api_client, set_rng):
    session_id = (await _start(api_client))["session_id"]
    set_rng([SCATTER] * 4 + _no_win_fill(26))
    body = await _spin(api_client, session_id)
    assert body["tumble"]["scatter_win"] == 3 * BET
    assert body["feature"]["triggered"] is True
    assert body["feature"]["spins_remaining"] == 15
    assert body["total_win"] == 3 * BET

    # first free spin: 8 helmets + orb x3 -> TOTAL MULTIPLIER 1 + 3 = 4.
    # FS weights differ from base only in sapphire/citrine/scatter/orb, so the
    # helmet..amethyst ranges are unchanged; refill with emerald/amethyst.
    initial = [HELMET] * 5 + [HELMET, HELMET, HELMET, FS_ORB, ORB_X3] + _no_win_fill(21)
    set_rng(initial + [EMERALD] * 7 + [AMETHYST])
    body = await _spin(api_client, session_id)
    t = body["tumble"]
    assert t["mode"] == "fs"
    assert t["total_multiplier_before"] == 1
    assert t["total_multiplier_after"] == 4
    assert body["total_win"] == 10 * BET * 4
    assert body["feature"]["spins_remaining"] == 14
    assert body["feature"]["multiplier"] == 4
    assert body["balance"] == START_BALANCE - BET + 3 * BET + 40 * BET


async def test_buy_super_free_spins(api_client, set_rng):
    session_id = (await _start(api_client))["session_id"]
    # service spin: 30 filler draws (no scatter/eagle/orb in its table) + 4 placements
    set_rng(_no_win_fill(30) + [0, 0, 0, 0])
    response = await api_client.post(
        "/api/v1/feature/buy",
        json={"session_id": session_id, "feature_id": "super_free_spins", "bet_amount": BET},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tumble"]["service"] is True
    assert body["tumble"]["scatter_count"] == 4
    assert body["feature"]["spins_remaining"] == 15
    assert body["balance"] == START_BALANCE - 142 * BET

    # next spin is a SUPER free spin: guaranteed orb even on a no-orb board
    set_rng(_no_win_fill(30) + [0, ORB_X2])
    body = await _spin(api_client, session_id)
    assert body["tumble"]["mode"] == "super"
    assert len(body["tumble"]["orbs"]) == 1
    assert body["tumble"]["total_multiplier_after"] == 1  # losing series: orb fades


async def test_buy_unknown_sku_404(api_client):
    session_id = (await _start(api_client))["session_id"]
    response = await api_client.post(
        "/api/v1/feature/buy", json={"session_id": session_id, "feature_id": "nope", "bet_amount": BET}
    )
    assert response.status_code == 404
