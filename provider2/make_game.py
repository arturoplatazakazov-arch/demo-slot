"""Render a Provider 2 game's page, styles, scripts and seed from
provider2/template/ (+ the numbers build_assets.py measured into
front/img/<slug>/layout.json).

    python3 provider2/make_game.py <slug> [<slug> ...]   (or: all)

Writes front/<slug>.html, front/css/<slug>.css, front/js/<slug>/{slot,app,
sound}.js, app/seed/<seed>.py, and (always, for every game) the seed
aggregator app/seed/provider2.py and tests/test_api_spin_provider2.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from games import GAMES  # noqa: E402

T = HERE / 'template'


def seed_name(slug):
    return slug.replace('-', '_')


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexs(c):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(v))) for v in c)


def mix(c, d, k):
    return tuple(a + (b - a) * k for a, b in zip(c, d))


def tokens(slug):
    g = GAMES[slug]
    lay = json.loads((ROOT / 'front/img' / slug / 'layout.json').read_text())
    f = lay['frame']
    acc, ink = rgb(g['accent']), rgb(g['ink'])
    hp, lp = g['hp'], g['lp']
    logo_w = 560
    lw, lh = lay['logo']
    layout = [
        [lp[0], hp[1], lp[1], hp[2], lp[2]],
        [hp[0], lp[3], 'scatter', lp[4], hp[3]],
        [lp[1], lp[0], hp[0], lp[3], 'wild'],
    ]
    names = {'scatter': g['scatter_name'], 'wild': g['wild_name']}
    names.update(dict(zip(hp, g['hp_names'])))
    names.update(dict(zip(lp, g['lp_names'])))
    t = {
        '__SLUG__': slug, '__NAME__': g['name'], '__SEED__': seed_name(slug),
        '__DESC__': g['desc'], '__MUSIC__': g['music'],
        '__ACCENT__': g['accent'], '__ACCENT_DARK__': hexs(mix(acc, (0, 0, 0), 0.45)),
        '__ACCENT_LIGHT__': hexs(mix(acc, (255, 255, 255), 0.45)),
        '__ACCENT_RGB__': ', '.join(str(v) for v in acc),
        '__INK__': g['ink'], '__INK_LIGHT__': hexs(mix(ink, acc, 0.35)), '__NIGHT__': g['night'],
        '__FW__': str(f['w']), '__FH__': str(f['h']), '__BL__': str(f['l']), '__BT__': str(f['t']),
        '__BR__': str(f['r']), '__BB__': str(f['b']),
        '__P_BIG__': lay['popup_insets']['big'], '__P_MEGA__': lay['popup_insets']['mega'],
        '__P_EPIC__': lay['popup_insets']['epic'], '__P_FS__': lay['popup_insets']['fs'],
        '__P_BUY__': lay['popup_insets']['buy'],
        '__LOGO_W__': str(logo_w),
        # the logo's lower 18% rests on the frame's top bar
        '__LOGO_OVERLAP__': str(round(logo_w * lh / lw * 0.18 + f['t'] * 0.35)),
        '__HERO_H__': '640',
        '__SYMBOL_CODES__': json.dumps(g['codes']).replace('"', "'").replace("','", "', '"),
        '__SYMBOL_LAYOUT__': '[\n' + ''.join(
            '  ' + json.dumps(r).replace('"', "'").replace("','", "', '") + ',\n' for r in layout) + ']',
        '__SYMBOL_NAMES__': '{\n' + ''.join(f'    "{k}": "{v}",\n' for k, v in names.items()) + '}',
    }
    for i, c in enumerate(hp):
        t[f'__HP{i}__'] = c
    for i, c in enumerate(lp):
        t[f'__LP{i}__'] = c
    return t


def render(src, toks):
    s = (T / src).read_text()
    for k in sorted(toks, key=len, reverse=True):
        s = s.replace(k, toks[k])
    left = [w for w in set(__import__('re').findall(r'__[A-Z0-9_]+__', s)) if w not in ('__init__', '__name__', '__main__')]
    assert not left, (src, left)
    return s


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make(slug):
    toks = tokens(slug)
    write(ROOT / 'front' / f'{slug}.html', render('game.html', toks))
    write(ROOT / 'front/css' / f'{slug}.css', render('game.css', toks))
    for js in ('slot.js', 'app.js', 'sound.js'):
        write(ROOT / 'front/js' / slug / js, render(js, toks))
    write(ROOT / 'app/seed' / f'{seed_name(slug)}.py', render('seed.py', toks))
    print('made', slug)


AGG = '''"""Provider 2 — the ten slots generated from provider2/ (see
provider2/make_game.py). One entry point for app/main.py so the startup list
does not grow by ten lines."""

from sqlalchemy.ext.asyncio import AsyncSession

{imports}

PROVIDER2_GAME_CODES = {codes}


async def seed_provider2(db: AsyncSession) -> None:
{calls}
'''

TEST = '''"""Integration coverage for the ten Provider 2 slots (provider2/,
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

GAMES = {games}

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
    response = await api_client.post("/api/v1/session/start", json={{"game_id": code}})
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("code", sorted(GAMES))
async def test_symbol_set_matches_the_front(api_client, code):
    body = await _start(api_client, code)
    assert {{s["code"] for s in body["symbols"]}} == set(GAMES[code])


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
    response = await api_client.post("/api/v1/spin", json={{"session_id": session_id, "bet_amount": BET_AMOUNT}})
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
    response = await api_client.post("/api/v1/spin", json={{"session_id": session_id, "bet_amount": BET_AMOUNT}})
    assert response.status_code == 200
    body = response.json()
    assert body["total_win"] > 0
    assert any(w["symbol"] == GAMES[code][2] and w["count"] == 5 for w in body["line_wins"])
'''


def make_shared():
    skip = set(filter(None, __import__('os').environ.get('P2_EXCLUDE', '').split(',')))
    slugs = [s for s in GAMES if (ROOT / 'app/seed' / f'{seed_name(s)}.py').exists() and s not in skip]
    imports = '\n'.join(
        f'from app.seed.{seed_name(s)} import get_or_seed_active_config as _seed_{seed_name(s)}' for s in slugs)
    calls = '\n'.join(f'    await _seed_{seed_name(s)}(db)' for s in slugs)
    codes = '[\n' + ''.join(f'    "{s}",\n' for s in slugs) + ']'
    write(ROOT / 'app/seed/provider2.py', AGG.format(imports=imports, codes=codes, calls=calls))
    games = '{\n' + ''.join(
        f'    "{s}": {json.dumps(GAMES[s]["codes"])},\n' for s in slugs) + '}'
    write(ROOT / 'tests/test_api_spin_provider2.py', TEST.format(games=games))


if __name__ == '__main__':
    slugs = list(GAMES) if sys.argv[1:] == ['all'] else sys.argv[1:]
    for s in slugs:
        make(s)
    make_shared()
