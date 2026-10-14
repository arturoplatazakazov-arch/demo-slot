"""Integration coverage for the ten Provider 2 slots (provider2/,
app/seed/provider2.py): every seed boots, exposes its symbol set, and the
shared Caesar's Fortune mechanic answers through POST /api/v1/spin — a scatter
trigger opens free spins and a full middle line of the first high symbol pays.

Cumulative reel weights in the template seed's _SYMBOLS order (identical for
all ten): scatter[0,728) wild[728,821) hp0[821,1441) hp1[1441,1906)
hp2[1906,2278) hp3[2278,2588) lp0[2588,4388) lp1[4388,6068) lp2[6068,7628)
lp3[7628,9068) lp4[9068,10400). Grid draws are reel-major (reel 0 rows 0-2,
then reel 1, ...). Same FakeRNG/set_rng conventions as the other spin tests.
"""

import pytest

GAMES = {
    "rad-raiders": ["wild", "scatter", "geiger", "gasmask", "beans", "radpop", "ten", "jack", "queen", "king", "ace"],
    "jade-paws": ["wild", "scatter", "koi", "dumplings", "gong", "fan", "ten", "jack", "queen", "king", "ace"],
    "ghoul-groove": ["wild", "scatter", "discoskull", "boombox", "potion", "cocktail", "ten", "jack", "queen", "king", "ace"],
    "gummy-gold-rush": ["wild", "scatter", "sheriff", "cowgirl", "bandit", "minecart", "heart", "star", "worm", "bonbon", "crystal"],
    "whisker-noir": ["wild", "scatter", "owl", "cat", "raccoon", "bulldog", "ten", "jack", "queen", "king", "ace"],
    "cogwork-skies": ["wild", "scatter", "airship", "teslajar", "pocketwatch", "telescope", "ten", "jack", "queen", "king", "ace"],
    "bayou-bedlam": ["wild", "scatter", "catfish", "gator", "leech", "possum", "ten", "jack", "queen", "king", "ace"],
    "jaguar-eclipse": ["wild", "scatter", "toucan", "axolotl", "monkey", "serpent", "ten", "jack", "queen", "king", "ace"],
    "trident-vs-titan": ["wild", "scatter", "trident", "pegasus", "amphora", "lyre", "ten", "jack", "queen", "king", "ace"],
}

_SCATTER, _HP0, _LP0, _LP1 = 0, 821, 2588, 4388
BET_AMOUNT = 5500


@pytest.fixture(autouse=True)
async def _seed_provider2():
    from app.core.db import AsyncSessionLocal
    from app.seed.provider2 import seed_provider2

    async with AsyncSessionLocal() as db:
        await seed_provider2(db)


def _filler(col):
    """Even reels all lp0, odd reels all lp1: no line ever gets 3 in a row."""
    return [_LP0 if col % 2 == 0 else _LP1] * 3


async def _start(api_client, code):
    response = await api_client.post("/api/v1/session/start", json={"game_id": code})
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("code", sorted(GAMES))
async def test_symbol_set_matches_the_front(api_client, code):
    body = await _start(api_client, code)
    assert {s["code"] for s in body["symbols"]} == set(GAMES[code])


@pytest.mark.parametrize("code", sorted(GAMES))
async def test_three_scatters_open_free_spins(api_client, set_rng, code):
    session_id = (await _start(api_client, code))["session_id"]
    draws = []
    for col in range(5):
        reel = _filler(col)
        if col in (0, 2, 4):
            reel[0] = _SCATTER
        draws += reel
    set_rng(draws)
    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    assert response.status_code == 200
    body = response.json()
    assert body["feature"]["type"] == "free_spins"
    assert body["feature"]["spins_remaining"] == 10


@pytest.mark.parametrize("code", sorted(GAMES))
async def test_full_middle_line_of_the_top_symbol_pays(api_client, set_rng, code):
    session_id = (await _start(api_client, code))["session_id"]
    draws = []
    for col in range(5):
        reel = _filler(col)
        reel[1] = _HP0
        draws += reel
    set_rng(draws)
    response = await api_client.post("/api/v1/spin", json={"session_id": session_id, "bet_amount": BET_AMOUNT})
    assert response.status_code == 200
    body = response.json()
    assert body["total_win"] > 0
    assert any(w["symbol"] == GAMES[code][2] and w["count"] == 5 for w in body["line_wins"])
