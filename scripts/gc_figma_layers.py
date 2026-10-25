"""Assembled (layered) mockups of gangsta-casino for Figma: base + bonus
screen, desktop 1932x940 + mobile 780x1416. Each visual part of the page is
captured on its own (everything else hidden, transparent background) at its
exact place, so the board gets real layers instead of one flat screenshot.
Spine parts are swapped for their static fallbacks (has-spine-* off).
Usage: python scripts/gc_figma_layers.py <out_dir> [base_url]"""
import asyncio, base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websockets

OUT = sys.argv[1]; BASE = sys.argv[2] if len(sys.argv) > 2 else 'http://localhost:4199'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
VIEWS = {'desk': (1932, 940), 'mob': (780, 1416)}
GRID = "[['rare_purple','common_2','common_3','rare_yellow','common_1'],['common_4','wild','rare_blue','common_1','common_2'],['common_3','rare_green','common_4','scatter','wof']]"

SETUP = {
    'base': f"await applyGrid({GRID});",
    'bonus': f"applyModeScreen('freespins'); setFreeSpinsCounter(7); await applyGrid({GRID}); setMultiplierPlate(9, {{lit: true}});",
}

# name, selector — bottom to top (= DOM paint order of these parts)
COLLECT = r"""
(() => {
  const screen = document.getElementById('screen');
  screen.className = screen.className.split(' ').filter(c => !c.startsWith('has-spine')).join(' ');
  const mob = matchMedia('(orientation: portrait)').matches;
  const bonus = screen.dataset.mode === 'freespins';
  if (!mob && !bonus) screen.classList.add('has-still-people');
  document.querySelectorAll('.to-catalog-btn').forEach(e => e.remove());
  const L = [];
  const add = (name, el) => { if (!el) return; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || cs.display === 'none' || cs.visibility === 'hidden') return;
    el.dataset.iso = L.length; L.push({ name, x: r.left, y: r.top, w: r.width, h: r.height }); };
  const q = (s) => document.querySelector(s);
  add('background', mob ? q(bonus ? '.bg-mob--bonus' : '.bg-mob--base') : q('#bgLayer'));
  add('people', q('.scene-people'));
  add('frame_mob', q('.frame-mob'));
  add('reel_glass', q('#reelRig .reel-bg'));
  const cells = [...document.querySelectorAll('#reelGrid .reel__cell')].filter(c => { const r = c.getBoundingClientRect(); const g = q('#reelGrid').getBoundingClientRect(); return r.top >= g.top - 40 && r.bottom <= g.bottom + 40; });
  cells.forEach((c, i) => add(`symbol_${Math.floor(i / 1)}_${c.dataset.symbol}`, c));
  add('buy_bonus', q('#buyBonusBtn'));
  add('bonus_table_mob', q('.bonus-table-mob'));
  add('fs_counter', q('#freeSpinsCounter'));
  add('frame', q('.stage--front .frame'));
  add('logo', q(mob ? '.stage--front .logo--mob' : '.stage--front .logo--desk'));
  add('multiplier_plate', q('#multPlate'));
  add('ui_bar', q('#v3Bar'));
  return L;
})()
"""
ISO_CSS = """
html.iso, html.iso body, html.iso .screen { background: transparent !important; }
html.iso * { visibility: hidden !important; }
html.iso .iso-on, html.iso .iso-on * { visibility: visible !important; }
html.iso canvas { display: none !important; }
"""

async def cdp(ws, method, params=None, _id=[0]):
    _id[0] += 1; i = _id[0]
    await ws.send(json.dumps({'id': i, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(await ws.recv())
        if m.get('id') == i:
            if 'error' in m: raise RuntimeError(m['error'])
            return m.get('result', {})

async def ev(ws, expr):
    r = await cdp(ws, 'Runtime.evaluate', {'expression': expr, 'awaitPromise': True, 'returnByValue': True})
    if 'exceptionDetails' in r: raise RuntimeError(r['exceptionDetails'])
    return r['result'].get('value')

async def build(port, view, mode):
    W, H = VIEWS[view]
    d = os.path.join(OUT, f'{view}_{mode}'); os.makedirs(d, exist_ok=True)
    tab = json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT')))
    async with websockets.connect(tab['webSocketDebuggerUrl'], max_size=None) as ws:
        await cdp(ws, 'Emulation.setDeviceMetricsOverride', {'width': W, 'height': H, 'deviceScaleFactor': 1, 'mobile': False})
        await cdp(ws, 'Page.navigate', {'url': f'{BASE}/gangsta-casino.html?nofs&dev=0&t={time.time()}'})
        for _ in range(120):
            if await ev(ws, "!document.getElementById('preloader') && !!window.applyGrid"): break
            await asyncio.sleep(0.5)
        await asyncio.sleep(2.5)
        await ev(ws, f"(async () => {{ {SETUP[mode]} }})()")
        await asyncio.sleep(1.2)
        layers = await ev(ws, COLLECT)
        await asyncio.sleep(0.4)
        await ev(ws, f"(() => {{ const s = document.createElement('style'); s.textContent = {json.dumps(ISO_CSS)}; document.head.appendChild(s); document.documentElement.classList.add('iso'); }})()")
        await cdp(ws, 'Emulation.setDefaultBackgroundColorOverride', {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
        out = []
        for i, L in enumerate(layers):
            await ev(ws, f"document.querySelectorAll('.iso-on').forEach(e => e.classList.remove('iso-on')); document.querySelector('[data-iso=\"{i}\"]').classList.add('iso-on')")
            await asyncio.sleep(0.15)
            # clip to the frame (backgrounds are cover-scaled past it)
            x0, y0 = max(0, L['x']), max(0, L['y'])
            x1, y1 = min(W, L['x'] + L['w']), min(H, L['y'] + L['h'])
            # glow / shadows spill past the box: pad, still inside the frame
            pad = 0 if L['name'] == 'background' else 40
            x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
            shot = await cdp(ws, 'Page.captureScreenshot', {'format': 'png', 'clip': {'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0, 'scale': 1}})
            fn = f'{i:02d}_{L["name"]}.png'
            open(os.path.join(d, fn), 'wb').write(base64.b64decode(shot['data']))
            out.append({'name': L['name'], 'file': fn, 'x': round(x0), 'y': round(y0), 'w': round(x1 - x0), 'h': round(y1 - y0)})
        json.dump({'width': W, 'height': H, 'layers': out}, open(os.path.join(d, 'layers.json'), 'w'), indent=1)
        print(view, mode, len(out), 'layers')
    urllib.request.urlopen(f'http://127.0.0.1:{port}/json/close/{tab["id"]}')

async def main():
    port = 9334
    prof = tempfile.mkdtemp(prefix='gclay-')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={prof}', '--hide-scrollbars',
                             '--use-angle=swiftshader', '--enable-unsafe-swiftshader', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1); break
            except Exception: await asyncio.sleep(0.2)
        for view in VIEWS:
            for mode in SETUP:
                await build(port, view, mode)
    finally:
        proc.terminate()

asyncio.run(main())
