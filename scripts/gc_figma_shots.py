"""Screens of gangsta-casino for the layout-spec board (Figma), via headless
Chrome + CDP: every state of the spec is set up by calling the page's own
globals, then captured. Usage: python scripts/gc_figma_shots.py <out_dir> [base_url]"""
import asyncio, base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websockets

OUT = sys.argv[1]; BASE = sys.argv[2] if len(sys.argv) > 2 else 'http://localhost:4199'
os.makedirs(OUT, exist_ok=True)
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
VIEWS = {'h': (1932, 940), 'v': (780, 1416)}

GRID_WIN = "[['common_1','common_2','common_2','rare_blue','common_3'],['common_2','common_2','common_3','common_4','common_1'],['rare_green','common_4','common_2','common_1','scatter']]"
LW = "[{payline:4,positions:[{row:0,col:0},{row:1,col:1},{row:2,col:2}]},{payline:1,positions:[{row:1,col:0},{row:1,col:1},{row:1,col:2}]}]"
STATES = {
    '01_general': ("await applyGrid([['rare_purple','common_2','common_3','rare_yellow','common_1'],['common_4','wild','rare_blue','common_1','common_2'],['common_3','rare_green','common_4','scatter','wof']]);", 0.8),
    '02_highlight': (f"await applyGrid({GRID_WIN}); const lw={LW}; playWinCells(lw.flatMap(w=>w.positions), lw, []);", 1.6),
    '03_total_win': (f"await applyGrid({GRID_WIN}); const lw={LW}; playWinCells(lw.flatMap(w=>w.positions), lw, []); showInlineWinAmount(23400);", 1.2),
    '04_combination_win': (f"await applyGrid({GRID_WIN}); const lw={LW}; currentLineWins=lw; playWinCells(lw[1].positions, [lw[1]], []); showInlineWinAmount(11000);", 1.2),
    '05_buy_button': ("document.getElementById('buyBonusBtn').classList.add('is-hover');", 0.5),
    '06_buy_dialog': ("openBuyDialog(4785000);", 7.0),
    '07_big_win': ("playPopup('bigWin', 1234500, 60000);", 2.6),
    '08_fs_win': ("playPopup('bonusSpinsWin', 10, 60000);", 2.2),
    '09_fs_total_win': ("playPopup('bonusSpinsTotalWin', 2345000, 60000);", 2.2),
    '10_fs_mode': ("applyModeScreen('freespins'); setFreeSpinsCounter(7); await demoMultipliers();", 2.4),
    '08b_fs_screen': ("showBonusScreen(10);", 3.6),
    '00_feature_screen': ("showFeatureScreen();", 3.6),
    '11_multiplier_base': ("await demoMultipliers();", 2.4),
}

async def cdp(ws, method, params=None, _id=[0]):
    _id[0] += 1; i = _id[0]
    await ws.send(json.dumps({'id': i, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(await ws.recv())
        if m.get('id') == i:
            if 'error' in m: raise RuntimeError(m['error'])
            return m.get('result', {})

async def shoot(port, view, name, js, settle):
    w, h = VIEWS[view]
    tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/new?about:blank', timeout=10) if False else urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT'), timeout=10))
    async with websockets.connect(tabs['webSocketDebuggerUrl'], max_size=None) as ws:
        await cdp(ws, 'Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': False})
        await cdp(ws, 'Page.enable')
        await cdp(ws, 'Page.navigate', {'url': f'{BASE}/gangsta-casino.html?nofs&dev=0&shot={time.time()}'})
        # wait for the preloader to finish and the scene to come up
        for _ in range(120):
            r = await cdp(ws, 'Runtime.evaluate', {'expression': "!document.getElementById('preloader') && document.getElementById('screen').classList.contains('has-spine-scene')", 'returnByValue': True})
            if r['result'].get('value'): break
            await asyncio.sleep(0.5)
        await asyncio.sleep(2.0)
        await cdp(ws, 'Runtime.evaluate', {'expression': "document.querySelectorAll('.to-catalog-btn').forEach(e => e.style.display = 'none')"})
        if js:
            r = await cdp(ws, 'Runtime.evaluate', {'expression': f"(async () => {{ {js} }})()", 'awaitPromise': True, 'returnByValue': True})
            if 'exceptionDetails' in r: print('  js error', name, r['exceptionDetails'].get('exception', {}).get('description'))
        await asyncio.sleep(settle)
        shot = await cdp(ws, 'Page.captureScreenshot', {'format': 'png'})
        open(os.path.join(OUT, f'{name}_{view}.png'), 'wb').write(base64.b64decode(shot['data']))
        print('ok', name, view)
    urllib.request.urlopen(f'http://127.0.0.1:{port}/json/close/{tabs["id"]}', timeout=10)

async def main():
    port = 9333
    prof = tempfile.mkdtemp(prefix='gcshot-')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={prof}',
                             '--hide-scrollbars', '--autoplay-policy=no-user-gesture-required', '--use-angle=swiftshader',
                             '--enable-unsafe-swiftshader', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1); break
            except Exception: await asyncio.sleep(0.2)
        only = set(os.environ.get('ONLY', '').split(',')) - {''}
        for name, (js, settle) in STATES.items():
            if only and name not in only: continue
            for view in VIEWS:
                if name == '03_total_win' and view == 'h': pass
                await shoot(port, view, name, js, settle)
    finally:
        proc.terminate()

asyncio.run(main())
