"""static.png for the exported screens: the skeleton's resting frame (idle,
t=0) rendered 1:1 at its box with a transparent background, via
front/spine-static-render.html in headless Chrome. Run after gc_spine_export.py
with the static server on :4199. Usage: python scripts/gc_spine_static.py"""
import asyncio, base64, json, os, subprocess, tempfile, time, urllib.request
import websockets

DST = os.path.join(os.path.dirname(__file__), '..', 'front', 'spine-export', 'gangsta-casino')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

async def cdp(ws, method, params=None, _id=[0]):
    _id[0] += 1; i = _id[0]
    await ws.send(json.dumps({'id': i, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(await ws.recv())
        if m.get('id') == i:
            if 'error' in m: raise RuntimeError(m['error'])
            return m.get('result', {})

async def main():
    rep = json.load(open(os.path.join(DST, 'report.json')))
    import sys
    only = sys.argv[1:]
    jobs = {k: v for k, v in rep['_scene'].items() if (k in only if only else v['static'] == 'render')}
    out_dir = os.environ.get('OUT_DIR')
    port = 9341
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={tempfile.mkdtemp()}',
                             '--hide-scrollbars', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1); break
            except Exception: await asyncio.sleep(0.2)
        for name, v in jobs.items():
            x, y, w, h = v['box']
            tab = json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT')))
            async with websockets.connect(tab['webSocketDebuggerUrl'], max_size=None) as ws:
                await cdp(ws, 'Emulation.setDeviceMetricsOverride', {'width': int(w), 'height': int(h), 'deviceScaleFactor': 1, 'mobile': False})
                await cdp(ws, 'Emulation.setDefaultBackgroundColorOverride', {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
                pma = '1' if v['pma'] else '0'
                await cdp(ws, 'Page.navigate', {'url': f'http://localhost:4199/spine-static-render.html?folder=spine-export/gangsta-casino/{v.get('folder', name)}&skeleton={v.get('skeleton', '')}&pma={pma}&clip=idle&t=0&box={x},{y},{w},{h}&_={time.time()}'})
                for _ in range(60):
                    r = await cdp(ws, 'Runtime.evaluate', {'expression': 'window.ready', 'awaitPromise': True, 'returnByValue': True})
                    if r.get('result', {}).get('value'): break
                    await asyncio.sleep(0.5)
                await asyncio.sleep(1.0)
                shot = await cdp(ws, 'Page.captureScreenshot', {'format': 'png'})
                open(os.path.join(out_dir, name + '.png') if out_dir else (os.path.join(DST, v['folder'], f"{v['skeleton']}_static.png") if v.get('skeleton') else os.path.join(DST, name, 'static.png')), 'wb').write(base64.b64decode(shot['data']))
                print('static', name, int(w), 'x', int(h))
            urllib.request.urlopen(f'http://127.0.0.1:{port}/json/close/{tab["id"]}')
    finally:
        proc.terminate()

asyncio.run(main())
