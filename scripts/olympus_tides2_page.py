"""Olympus Thunder · Tides 2 — page for the client-feedback iteration (2026-11).

    python scripts/olympus_tides2_page.py   ->  front/olympus-thunder-tides2.html

Built from front/olympus-thunder.html; layout/look live in css/olympus-thunder-tides2.css (hand-written).
Art in img/olympus-thunder/tides2/ (scripts/olympus_tides2_art.py). Bonus art (FS sky, titles, cards,
wheel) stays the Tides set — the bonus screen is not part of this iteration.
Demo switches (presentation): ?under=glass|solid  ?low=gems|letters  ?title=1|2|3
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "front"
V = 1          # art cache-bust
CSS_V = 38
T = "img/olympus-thunder/tides2/"
OLD = "img/olympus-thunder/tides/"

h = (FRONT / "olympus-thunder.html").read_text()
h = re.sub(r"<title>.*?</title>", "<title>Olympus Thunder · Tides 2</title>", h)
h = re.sub(r'(<link rel="stylesheet" href="css/olympus-thunder\.css\?v=\d+">)',
           lambda m: m.group(1) + f'\n<link rel="stylesheet" href="css/olympus-thunder-tides2.css?v={CSS_V}">'
           '\n<link rel="preconnect" href="https://fonts.googleapis.com">'
           '\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Marcellus+SC&family=Forum&display=swap">',
           h, count=1)
body = (f'<body data-game-id="olympus-thunder" data-var="tides2" data-under="glass" data-low="gems" data-title="1" '
        f'data-sky="tides2/sky.jpg?v={V}|tides2/sky_mob_b.jpg?v={V}" data-sky-fs="tides/sky_fs.jpg?v=2|tides/sky_fs_mob.jpg?v=2" '
        f'data-temple="none" data-frame="none" data-symbols="{T}symbols/" data-symbols-v="{V}" '
        f'data-titles="{OLD}titles/" data-cards="{OLD}ui/" data-hero="tides2/hero.webp?v={V}" data-num-prefix="×" '
        f'data-spine-zeus="off" data-spine-logo="off" data-spine-symbols="off" data-spine-bg="off">'
        """
<script>
  // presentation switches (read before the game scripts build the board)
  (function () {
    var q = new URLSearchParams(location.search), b = document.body.dataset;
    if (q.get('under')) b.under = q.get('under');
    if (q.get('title')) b.title = q.get('title');
    var bgm = q.get('bgm'); if (bgm === '0' || bgm === 'a' || bgm === 'b') b.sky = 'tides2/sky.jpg?v=""" + str(V) + """|tides2/sky_mob' + (bgm === '0' ? '' : '_' + bgm) + '.jpg?v=""" + str(V) + """';
    if (q.get('clean')) b.clean = '1';
    if (q.get('shot')) { b.clean = '1'; document.head.insertAdjacentHTML('beforeend', '<style>#access-gate,#preloader,.to-catalog-btn{display:none!important}</style>'); }
    if (q.get('low') === 'letters') { b.low = 'letters'; b.symbols = '""" + T + """symbols_letters/'; }
    if (q.get('hero') === 'b') b.hero = 'tides2/hero_b.webp?v=""" + str(V) + """';
  })();
  window.OT_I18N = { 'ВЫИГРЫШ ДО': 'UP TO', 'ВЫИГРЫШ БОНУСА': 'BONUS WIN', 'ВЫИГРЫШ СЕРИИ': 'SERIES WIN',
    'ВЫИГРЫШ': 'WIN', 'С УЧЁТОМ КОЛЕЦ': 'WITH SCATTERS', 'МАКСИМАЛЬНЫЙ ВЫИГРЫШ': 'MAX WIN' };
</script>""")
h = re.sub(r"<body[^>]*>", lambda m: body, h, count=1)

# drifting storm clouds + a sky flash layer, over the sky, under the stage
h = h.replace('<canvas class="layer spine-fx spine-fx--back"',
              '<div class="layer clouds" aria-hidden="true">'
              + "".join(f'<img class="cloud cloud--{i}" src="{T}clouds/cloud{i}.webp?v={V}" alt="">' for i in (1, 2, 3, 4))
              + '</div>\n    <div class="layer sky-bolt" aria-hidden="true"></div>\n    <canvas class="layer spine-fx spine-fx--back"', 1)

# frame garland: glow spots on the frame cracks light up one after another (calm, no strobing)
SPOTS = [(8, 0), (36, 0), (64, 0), (92, 0), (100, 30), (100, 70), (92, 100), (64, 100), (36, 100), (8, 100), (0, 70), (0, 30)]
h = h.replace('<div class="board__fx" id="boardFx"></div>', '<div class="board__fx" id="boardFx"></div>\n        <div class="garland" aria-hidden="true">'
              + "".join(f'<i style="left:{x}%;top:{y}%;animation-delay:{i * 0.45:.2f}s"></i>' for i, (x, y) in enumerate(SPOTS)) + '</div>', 1)

# zeus glow layer of the v1 rig is not used
h = re.sub(r'<img class="zeus__glow"[^>]*>', "", h)

# logo = live text (fonts to choose from), localisable
h = re.sub(r'<img class="obj logo"[^>]*>',
           '<div class="obj logo" id="logo"><span class="logo__a">OLYMPUS</span><span class="logo__b">THUNDER</span></div>', h, count=1)

# jackpots: one light plate, dark text, lightning bolts per tier (1 mini .. 4 grand)
BOLT = '<i class="bolt"></i>'
def jp(tier, n, val):
    return (f'<div class="jp" data-tier="{tier}"><img src="{T}ui/plate_light.webp?v={V}" alt="">'
            f'<span class="jp__bolts">{BOLT * n}</span><span class="jp__name">{tier.upper()}</span>'
            f'<span class="jp__val">{val}</span></div>')
h = re.sub(r'<div class="obj jackpots" id="jackpots">.*?\n      </div>',
           '<div class="obj jackpots" id="jackpots">\n        ' + "\n        ".join(
               [jp("grand", 4, "1 000×"), jp("major", 3, "250×"), jp("minor", 2, "50×"), jp("mini", 1, "20×")])
           + '\n      </div>', h, count=1, flags=re.S)

# win plate (cascade counter / "UP TO 10,000×") — dark plate, English, text is its own layer
h = re.sub(r'<div class="obj win-plate" id="winPlate">.*?\n      </div>',
           f'<div class="obj win-plate" id="winPlate">\n        <img src="{T}ui/plate_dark.webp?v={V}" alt="">\n'
           '        <span class="win-plate__win"><span class="win-plate__label" id="winPlateLabel">UP TO 10,000×</span>\n'
           '        <span class="win-plate__value" id="winPlateValue"></span></span>\n      </div>', h, count=1, flags=re.S)

h = h.replace("ОБЩИЙ<br>МНОЖИТЕЛЬ", "TOTAL<br>MULTIPLIER")
# remaining tides art (bonus screen pieces, buy button placeholder until the client's UI-kit button)
h = h.replace('img/olympus-thunder/ui/', OLD + 'ui/').replace('img/olympus-thunder/titles/', OLD + 'titles/') \
     .replace('img/olympus-thunder/wheel/', OLD + 'wheel/')
h = re.sub(r'(src="img/olympus-thunder/tides/[^"?]+)"', r'\1?v=2"', h)
h = re.sub(r'<div class="preloader__logo" id="preloaderLogo">.*?</div>',
           '<div class="preloader__logo" id="preloaderLogo"><div class="logo logo--pre"><span class="logo__a">OLYMPUS</span><span class="logo__b">THUNDER</span></div></div>',
           h, count=1, flags=re.S)

# Buy Bonus lives in the bar menu (client): first item of the flyout, opens the same buy window
h = h.replace('<div class="v3-menu__flyout" id="v3Flyout">',
              '<div class="v3-menu__flyout" id="v3Flyout">\n            <button class="ui-icon-btn v3-btn v3-btn--buy" id="v3BuyBtn" type="button" aria-label="Buy Bonus">'
              '<svg viewBox="0 0 24 24"><path d="M5 8.2h14l-1.2 11.6a1.6 1.6 0 0 1-1.6 1.4H7.8a1.6 1.6 0 0 1-1.6-1.4L5 8.2Z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/>'
              '<path d="M9 8.2V7a3 3 0 0 1 6 0v1.2" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>'
              '<path d="M12.9 10.6 9.8 15h2.3l-1 3.4 3.3-4.6h-2.3l.8-3.2Z" fill="currentColor"/></svg></button>', 1)
h = h.replace("</body>", """<script>
  document.getElementById('v3BuyBtn').addEventListener('click', function () {
    var m = document.getElementById('v3MenuBtn');
    if (m.getAttribute('aria-expanded') === 'true') m.click();   // close the flyout
    document.getElementById('buyBtn').click();                     // same handler as the old Buy Bonus button
  });
</script>
</body>""", 1)

# presentation switches
h = h.replace('<div class="screen" id="screen"', """<div class="demo-switch" id="demoSwitch">
    <button class="demo-switch__toggle" id="demoToggle" type="button" title="Hide / show switches">⚙</button>
    <div><b>Underlay</b><button data-k="under" data-v="glass">Glass</button><button data-k="under" data-v="solid">Solid</button></div>
    <div><b>Low</b><button data-k="low" data-v="gems">Gems</button><button data-k="low" data-v="letters">Letters</button></div>
    <div><b>Title</b><button data-k="title" data-v="1">1</button><button data-k="title" data-v="2">2</button><button data-k="title" data-v="3">3</button></div>
    <div><b>Zeus</b><button data-k="hero" data-v="a">A</button><button data-k="hero" data-v="b">B</button></div>
    <div><b>Mob BG</b><button data-k="bgm" data-v="0">Base</button><button data-k="bgm" data-v="a">A</button><button data-k="bgm" data-v="b">B</button></div>
  </div>
  <div class="screen" id="screen\"""", 1)
h = h.replace("</body>", """<script>
  (function () {
    var b = document.body.dataset, q = new URLSearchParams(location.search);
    var cur = { under: b.under, low: b.low, title: b.title, hero: q.get('hero') === 'b' ? 'b' : 'a', bgm: q.get('bgm') || 'b' };
    var box = document.getElementById('demoSwitch');
    function paint() { box.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', cur[x.dataset.k] === x.dataset.v); }); }
    box.addEventListener('click', function (e) {
      var x = e.target.closest('button'); if (!x) return;
      cur[x.dataset.k] = x.dataset.v;
      q.set(x.dataset.k, x.dataset.v); history.replaceState(null, '', '?' + q);
      if (x.dataset.k === 'low' || x.dataset.k === 'hero' || x.dataset.k === 'bgm') { location.reload(); return; }  // symbol set / hero are read at start
      b[x.dataset.k] = x.dataset.v; paint();
    });
    paint();
    // the switch panel can be collapsed to the gear (remembered per browser)
    var tg = document.getElementById('demoToggle');
    function setCollapsed(c) { box.classList.toggle('is-collapsed', c); try { localStorage.setItem('ot2Switches', c ? 'off' : 'on'); } catch (e) {} }
    try { setCollapsed(localStorage.getItem('ot2Switches') === 'off'); } catch (e) {}
    tg.addEventListener('click', function (e) { e.stopPropagation(); setCollapsed(!box.classList.contains('is-collapsed')); });

    // portrait: the logo is exactly as wide as the GRAND plate — fit the font to its box
    var logo = document.getElementById('logo');
    function fitLogo() {
      logo.style.fontSize = '';
      if (!matchMedia('(orientation: portrait)').matches) return;
      var main = logo.querySelector('.logo__b'), want = logo.clientWidth, have = main.scrollWidth;
      if (want && have) logo.style.fontSize = (parseFloat(getComputedStyle(logo).fontSize) * want / have) + 'px';
    }
    (document.fonts ? document.fonts.ready : Promise.resolve()).then(fitLogo);
    addEventListener('resize', fitLogo);
    new MutationObserver(function () { setTimeout(fitLogo, 60); setTimeout(fitLogo, 600); }).observe(document.body, { attributes: true, attributeFilter: ['data-title'] });
  })();
</script>
</body>""", 1)

(FRONT / "olympus-thunder-tides2.html").write_text(h)
print("ok", len(h))
