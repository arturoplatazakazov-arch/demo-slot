"""Koi Fortune: the four variant pages, built from savannah-carved.html.

    .venv/bin/python scripts/koi_fortune_pages.py

Writes front/koi-fortune-<variant>.html. The page differs from the donor in
its art folder, the three backgrounds, the medallion art (coin / jackpot
coin instead of the wheel), the Hold & Win counter on the reels, the Ante
Bet switch in the pill, and the scripts (js/koi-fortune/*).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DONOR = ROOT / 'front/savannah-carved.html'
VARIANTS = {
    'silk': ('Silk', 'a'),
    'jade': ('Jade', 'a'),
    'lantern': ('Lanterns', 'a'),
    'paper': ('Paper Craft', 'a'),
}


def rep(s, a, b):
    assert a in s, a[:80]
    return s.replace(a, b, 1)


def build(key, title, line):
    slug = f'koi-fortune-{key}'
    s = DONOR.read_text()
    s = s.replace('img/savannah-carved/', f'img/{slug}/')
    # api.js gained spin(..., extra) for the Ante flag: a cached old copy
    # would drop it silently.
    s = rep(s, 'js/api.js?v=2', 'js/api.js?v=3')
    s = rep(s, '<title>Savannah Kings · Carved</title>', f'<title>Koi Fortune · {title}</title>')
    s = rep(s, '<link rel="stylesheet" href="css/savannah-carved.css?v=3">', f'<link rel="stylesheet" href="css/{slug}.css?v=2">')
    s = rep(s, '<link rel="stylesheet" href="css/savannah-layouts.css?v=8">',
            '<link rel="stylesheet" href="css/savannah-layouts.css?v=8">\n<link rel="stylesheet" href="css/koi-fortune.css?v=5">')
    s = rep(s, '''    <!-- Day and night backgrounds both live in the DOM and cross-fade
         (GDD §3.2: the switch to night is the free-spins signal). -->
    <img class="bg bg--base" id="bgBase" alt="">
    <img class="bg bg--bonus" id="bgBonus" alt="">''', '''    <!-- Base, free-spins and Hold & Win backgrounds all live in the DOM and
         cross-fade on #screen[data-mode]. -->
    <img class="bg bg--base" id="bgBase" alt="">
    <img class="bg bg--bonus" id="bgBonus" alt="">
    <img class="bg bg--hw" id="bgHw" alt="">''')
    s = rep(s, 'alt="Savannah Kings">', 'alt="Koi Fortune">')
    # reels: the Hold & Win counter + total ride on the frame's top border
    s = rep(s, '''        <div class="reel-win" id="reelWinAmount"></div>
      </div>''', f'''        <div class="reel-win" id="reelWinAmount"></div>
        <div class="hw-panel" id="hwPanel">
          <div class="hw-respins"><img src="img/{slug}/img/respins.webp" alt="Respins"><div class="hw-respins__n" id="hwRespins"></div></div>
          <div class="hw-total"><img src="img/{slug}/img/panel.webp" alt=""><span class="hw-total__label">TOTAL</span><div class="hw-total__value" id="hwTotal"></div></div>
        </div>
      </div>''')
    # medallions: coin art instead of the wheel
    s = rep(s, f'''          <img class="medal__hub" src="img/{slug}/img/wheel_hub.webp" alt="">
          <img class="medal__rim" src="img/{slug}/img/wheel_rim.webp" alt="">''',
            f'''          <img class="medal__rim" src="img/{slug}/symbols/coin.webp" alt="">''')
    s = rep(s, f'''          <img class="medal__rim" src="img/{slug}/img/wheel_rim.webp" alt="">''',
            f'''          <img class="medal__rim" src="img/{slug}/symbols/jpcoin.webp" alt="">''')
    # Ante Bet in the pill, after the balance
    s = rep(s, '''            <span class="readout__value"><span id="balanceValue">0.00</span> <small id="currency">FUN</small></span>
          </div>''', f'''            <span class="readout__value"><span id="balanceValue">0.00</span> <small id="currency">FUN</small></span>
          </div>
          <button class="ante" id="anteBtn" type="button" aria-pressed="false" aria-label="Ante bet" hidden>
            <span class="ante__switch"><img class="ante__off" src="img/{slug}/img/ante_off.webp" alt=""><img class="ante__on" src="img/{slug}/img/ante_on.webp" alt=""></span>
            <span class="ante__text"><span class="ante__label">ANTE BET</span><span class="ante__sub">2× features · <span id="anteCost">+25%</span></span></span>
          </button>''')
    s = rep(s, 'Popups, the wheel and the buy window', 'Popups and the buy window')
    s = rep(s, 'img/reel_frame.webp"', 'img/reel_frame.webp?v=2"')
    # no wheel overlay
    a = s.index('      <div class="wheel-overlay"')
    b = s.index('      <div class="buy-overlay"')
    s = s[:a] + s[b:]
    s = rep(s, "<script>window.SK_ASSET_ROOT = 'img/savannah-carved'; window.SK_POPUP_ART = true; window.SK_WIN_LINE = 'a';</script>",
            f"<script>window.SK_ASSET_ROOT = 'img/{slug}'; window.SK_POPUP_ART = true; window.SK_WIN_LINE = '{line}';</script>")
    s = s.replace("<script>window.SK_ASSET_ROOT = 'img/savannah-carved'", f"<script>window.SK_ASSET_ROOT = 'img/{slug}'")
    s = rep(s, '<script src="js/savannah-kings/slot.js?v=11"></script>', '<script src="js/koi-fortune/slot.js?v=1"></script>')
    s = rep(s, '<script src="js/savannah-kings/app.js?v=3"></script>', '<script src="js/koi-fortune/app.js?v=1"></script>')
    bad = [l for l in s.splitlines() if 'savannah-carved' in l or 'wheel' in l.lower()]
    assert not bad, bad
    out = ROOT / f'front/{slug}.html'
    out.write_text(s)
    print(out.relative_to(ROOT))


if __name__ == '__main__':
    for key, (title, line) in VARIANTS.items():
        build(key, title, line)
