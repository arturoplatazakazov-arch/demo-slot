"""Headless check for front/gangsta-casino-anim-test.html: for every card,
static tile vs first / last frame of each clip — pixel shift (best offset)
and mean difference. Usage: python scripts/gc_anim_check.py <out_dir> [pack]"""
import asyncio, base64, io, json, os, subprocess, sys, tempfile, time, urllib.request
import numpy as np, websockets
from PIL import Image

OUT = sys.argv[1]; PACK = sys.argv[2] if len(sys.argv) > 2 else 'export'
os.makedirs(OUT, exist_ok=True)
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

async def cdp(ws, method, params=None, _id=[0]):
    _id[0] += 1; i = _id[0]
    await ws.send(json.dumps({'id': i, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(await ws.recv())
        if m.get('id') == i:
            if 'error' in m: raise RuntimeError(m['error'])
            return m.get('result', {})

async def ev(ws, e):
    r = await cdp(ws, 'Runtime.evaluate', {'expression': e, 'awaitPromise': True, 'returnByValue': True})
    if 'exceptionDetails' in r: raise RuntimeError(r['exceptionDetails'])
    return r['result'].get('value')

async def shot(ws):
    d = await cdp(ws, 'Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(d['data']))).convert('RGB')).astype(np.float32)

def best_shift(a, b, r=6):
    best = (1e9, 0, 0)
    ga, gb = a.mean(2), b.mean(2)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            sa = ga[r + dy:ga.shape[0] - r + dy, r + dx:ga.shape[1] - r + dx]
            sb = gb[r:gb.shape[0] - r, r:gb.shape[1] - r]
            e = np.abs(sa - sb).mean()
            if e < best[0]: best = (e, dx, dy)
    return best

async def main():
    port = 9335
    prof = tempfile.mkdtemp(prefix='gcanim-')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={prof}', '--hide-scrollbars',
                             '--use-angle=swiftshader', '--enable-unsafe-swiftshader', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1); break
            except Exception: await asyncio.sleep(0.2)
        tab = json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT')))
        async with websockets.connect(tab['webSocketDebuggerUrl'], max_size=None) as ws:
            await cdp(ws, 'Emulation.setDeviceMetricsOverride', {'width': 1800, 'height': 2400, 'deviceScaleFactor': 1, 'mobile': False})
            await cdp(ws, 'Page.navigate', {'url': f'http://localhost:4199/gangsta-casino-anim-test.html?t={time.time()}'})
            await asyncio.sleep(3)
            if PACK != 'export':
                await ev(ws, f"document.querySelector('[data-pack={PACK}]').click()")
            await asyncio.sleep(4)
            await ev(ws, "document.getElementById('optCross').click()")  # crosshair off for the pixel compare
            await asyncio.sleep(0.3)
            n = await ev(ws, 'cards.length')
            rects = await ev(ws, "cards.map(c => { const r = c.cell.getBoundingClientRect(); return [r.left, r.top, r.width, r.height, c.code, c.cell.querySelector('img').getAttribute('src').split('/').pop()]; })")
            clips = await ev(ws, "Promise.all(cards.map(c => c.res.then(r => [...c.card.querySelectorAll('.frames option')].map(o => o.value))))")
            base = await shot(ws)
            results = []
            maxk = max(len(c) for c in clips)
            for k in range(maxk):
                for last in (False, True):
                    await ev(ws, f"Promise.all(cards.map((c, i) => {{ const o = [...c.card.querySelectorAll('.frames option')]; return o[{k}] ? freeze(c, o[{k}].value, {str(last).lower()}) : null; }}))")
                    await asyncio.sleep(0.6)
                    img = await shot(ws)
                    for i, (x, y, w, h, code, st) in enumerate(rects):
                        if k >= len(clips[i]): continue
                        x, y, w, h = int(x), int(y), int(w), int(h)
                        a, b = img[y:y + h, x:x + w], base[y:y + h, x:x + w]
                        e, dx, dy = best_shift(a, b)
                        e0 = np.abs(a.mean(2) - b.mean(2)).mean()
                        results.append({'card': i, 'code': code, 'static': st, 'clip': clips[i][k], 'frame': 'last' if last else 'first',
                                        'diff': round(float(e0), 2), 'best_dx': dx, 'best_dy': dy, 'diff_at_best': round(float(e), 2)})
                        if not last and k == 0:
                            Image.fromarray(np.concatenate([b, a], 1).astype(np.uint8)).save(os.path.join(OUT, f'{PACK}_{i:02d}_{code}.png'))
            await ev(ws, "cards.forEach(stopCard)")
        json.dump(results, open(os.path.join(OUT, f'{PACK}_check.json'), 'w'), indent=1, ensure_ascii=False)
        for r in results:
            print(f"{r['card']:2d} {r['code']:12s} {r['static']:14s} {r['clip']:10s} {r['frame']:5s} diff {r['diff']:6.2f}  best shift ({r['best_dx']:+d},{r['best_dy']:+d}) -> {r['diff_at_best']:.2f}")
    finally:
        proc.terminate()

asyncio.run(main())
