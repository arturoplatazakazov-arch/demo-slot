"""Gangsta Casino win lines as a lean Spine 4.1 skeleton (generated, no editor).

One skeleton, the 11 paylines (app/seed/gangsta_casino.py PAYLINES), in reel-grid
space: 5 x 3 cells of 197 x 200 design px, origin = grid centre, y up.
Every line is a polyline through the cell centres, run a little past the
outer reels, built from straight segments (glow band + white core, both
additive, white textures tinted per line) with a round joint dot at every
bend so corners never show gaps. Only the shown line's slots carry
attachments (setup pose = nothing), so a line costs ~15 quads to draw.

Clips per line n: `line{n}_in` (draw-on, 0.36 s, keyed per segment — no
sampled timelines) and `line{n}_loop` (1.2 s: glow pulse + a comet running
along the line). A clipping rectangle (one per layout) cuts the lines at the chrome.

Usage: python scripts/gangsta_casino_winlines.py <out_dir>
"""
import json, math, os, sys
import numpy as np
from PIL import Image

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
CW, CH, COLS, ROWS = 197.0, 200.0, 5, 3
GW, GH = CW * COLS, CH * ROWS
PAYLINES = [  # app/seed/amys_fruit_farm.py PAYLINES (gangsta uses Amy's 11 lines)
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
    [1, 0, 1, 0, 1], [1, 2, 1, 2, 1], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2], [0, 2, 0, 2, 0],
    [2, 0, 2, 0, 2],
]
COLORS = ['ff3fa4', '39d5ff', 'ffc847', 'b45cff', '4dff9a']
GLOW_H, CORE_H, DOT = 72, 12, 64
IN_T, LOOP_T = 0.36, 1.2
EXT = 60.0  # run past the outer reels — the clip cuts them exactly at the chrome
# Chrome inner edge per layout, in grid-centred units (gangsta-casino.css
# .reel__grid clip boxes): desktop hole rig x 50..1077 / y 79..715 with the
# grid at (68, 97); portrait clip 1010.7 x 638.6 with the grid at (12.8, 29.3).
# The lines start and end right at the frame (product: «линии должны
# начинаться от рамки»). slot.js picks the attachment for the layout.
CLIPS = {'clip_desk': (-510.5, 318.0, 516.5, -318.0), 'clip_mob': (-505.3, 329.3, 505.4, -309.3)}

def cx(c): return -GW / 2 + CW * (c + 0.5)
def cy(r): return GH / 2 - CH * (r + 0.5)

# ---- textures (white, straight alpha) ----
def band(w, h, sigma):
    y = (np.arange(h) + 0.5) / h * 2 - 1
    a = np.exp(-(y / sigma) ** 2)
    a = np.tile(a[:, None], (1, w))
    img = np.zeros((h, w, 4), np.uint8); img[..., :3] = 255; img[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(img)
def dot(s, sigma):
    y, x = np.mgrid[0:s, 0:s]; r = np.hypot((x + 0.5) / s * 2 - 1, (y + 0.5) / s * 2 - 1)
    a = np.exp(-(r / sigma) ** 2) * (r < 1)
    img = np.zeros((s, s, 4), np.uint8); img[..., :3] = 255; img[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(img)
def comet(w, h):
    y, x = np.mgrid[0:h, 0:w]; u = (x + 0.5) / w; v = (y + 0.5) / h * 2 - 1
    a = np.exp(-(v / 0.35) ** 2) * np.clip(u, 0, 1) ** 2.2 * np.exp(-((u - 0.92) / 0.5) ** 8)
    img = np.zeros((h, w, 4), np.uint8); img[..., :3] = 255; img[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(img)
TEX = {'glow': band(64, 64, 0.5), 'core': band(64, 16, 0.55), 'dot': dot(64, 0.55), 'comet': comet(128, 32)}
x = 0; H = max(i.height for i in TEX.values()); W = sum(i.width + 2 for i in TEX.values())
page = Image.new('RGBA', (W, H)); lines = ['animation.png', f'size:{W},{H}', 'filter:Linear,Linear']
for n, im in TEX.items():
    page.paste(im, (x, 0)); lines += [n, f'bounds:{x},0,{im.width},{im.height}']; x += im.width + 2
page.save(os.path.join(OUT, 'animation.png'), optimize=True)
open(os.path.join(OUT, 'animation.atlas'), 'w').write('\n'.join(lines) + '\n')

bones = [{'name': 'root'}]; slots = []; skin = {}; anims = {}
slots.append({'name': 'clip', 'bone': 'root', 'attachment': 'clip_desk'})
skin['clip'] = {k: {'type': 'clipping', 'end': None, 'vertexCount': 4,
                    'vertices': [x0, y0, x1, y0, x1, y1, x0, y1]} for k, (x0, y0, x1, y1) in CLIPS.items()}
last_slot = None
for n, rows in enumerate(PAYLINES, start=1):
    col = COLORS[(n - 1) % len(COLORS)]
    pts = [(cx(c), cy(r)) for c, r in enumerate(rows)]
    pts = [(-GW / 2 - EXT, pts[0][1])] + pts + [(GW / 2 + EXT, pts[-1][1])]  # past the grid edge
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs]
    total = sum(lens); cum = [0]
    for L in lens: cum.append(cum[-1] + L)
    P = f'l{n}'
    ain = {'bones': {}, 'slots': {}}; aloop = {'bones': {}, 'slots': {}}
    for k, ((a, b), L) in enumerate(zip(segs, lens)):
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        bn = f'{P}s{k}'
        bones.append({'name': bn, 'parent': 'root', 'x': round(a[0], 2), 'y': round(a[1], 2), 'rotation': round(ang, 3)})
        for layer, h, alpha in (('glow', GLOW_H, 'ff'), ('core', CORE_H, 'ff')):
            sn = f'{bn}{layer}'
            tint = (col if layer == 'glow' else 'fff3dc') + alpha
            slots.append({'name': sn, 'bone': bn, 'color': tint, 'blend': 'additive'})
            skin[sn] = {sn: {'name': layer, 'x': round(L / 2, 2), 'width': round(L, 2), 'height': h}}
            t0, t1 = IN_T * cum[k] / total, IN_T * cum[k + 1] / total
            ain['slots'][sn] = {'attachment': [{'name': sn}]}
            aloop['slots'][sn] = {'attachment': [{'name': sn}]}
            if layer == 'glow':
                aloop['slots'][sn]['rgba'] = [
                    {'color': col + 'ff'},
                    {'time': 0.6, 'color': col + '99'},
                    {'time': LOOP_T, 'color': col + 'cc'}]
        ain['bones'][bn] = {'scale': [{'x': 0.001, 'y': 1, 'curve': 'stepped'} if t0 > 0 else {'x': 0.001, 'y': 1},
                                      *([{'time': round(t0, 4), 'x': 0.001, 'y': 1}] if t0 > 0 else []),
                                      {'time': round(t1, 4), 'x': 1, 'y': 1}]}
    for j, p in enumerate(pts[1:-1], start=1):  # joint dots at the bends and cell centres
        bn = f'{P}j{j}'
        bones.append({'name': bn, 'parent': 'root', 'x': round(p[0], 2), 'y': round(p[1], 2)})
        sn = f'{bn}dot'
        slots.append({'name': sn, 'bone': bn, 'color': col + 'cc', 'blend': 'additive'})
        skin[sn] = {sn: {'name': 'dot', 'width': DOT, 'height': DOT}}
        tj = round(IN_T * cum[j] / total, 4)
        ain['slots'][sn] = {'attachment': [{'time': tj, 'name': sn}]}
        aloop['slots'][sn] = {'attachment': [{'name': sn}]}
    # comet along the polyline (loop only)
    cb = f'{P}comet'
    bones.append({'name': cb, 'parent': 'root', 'x': round(pts[0][0], 2), 'y': round(pts[0][1], 2)})
    sn = f'{cb}'
    slots.append({'name': sn, 'bone': cb, 'color': 'ffffffff', 'blend': 'additive'})
    skin[sn] = {sn: {'name': 'comet', 'x': -40, 'width': 120, 'height': 30}}
    tr, ro = [], []
    for k, p in enumerate(pts):
        t = round(LOOP_T * 0.85 * cum[k] / total, 4)
        tr.append({'time': t, 'x': round(p[0] - pts[0][0], 2), 'y': round(p[1] - pts[0][1], 2)})
        if k < len(segs):
            a, b = segs[k]
            ro.append({'time': t, 'value': round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 3), 'curve': 'stepped'})
    aloop['bones'][cb] = {'translate': tr, 'rotate': ro}
    aloop['slots'][sn] = {'attachment': [{'name': sn}, {'time': round(LOOP_T * 0.85, 4), 'name': None}]}
    anims[f'line{n}_in'] = ain
    anims[f'line{n}_loop'] = aloop
    last_slot = sn
for a in skin['clip'].values(): a['end'] = last_slot
# setup pose: no attachments on line slots (clip slot keeps its own)
d = {'skeleton': {'spine': '4.1.24', 'x': -GW / 2 - 40, 'y': -GH / 2 - 20, 'width': GW + 80, 'height': GH + 40},
     'bones': bones, 'slots': slots, 'skins': [{'name': 'default', 'attachments': skin}], 'animations': anims}
json.dump(d, open(os.path.join(OUT, 'animation.json'), 'w'), separators=(',', ':'))
print('slots', len(slots), 'bones', len(bones), 'json', os.path.getsize(os.path.join(OUT, 'animation.json')))
