"""Gangsta Casino multiplier — the designer's new art (Desk_Gangsta_Slot_F.psb:
icons/coin and Popup's/multiplier, cut into assets_src/gangsta-casino-multiplier)
as two generated Spine 4.1 skeletons, value overlays kept separate (skins):

multiplier       — the reel symbol, 200x200 tile around the cell centre.
                   landing (0.7 s): the empty chip lands, the value flips in;
                   win (1.3 s): pulse + wobble, gold glow and a ring.
                   Rest pose = chip with its value (= static.png).
multiplier_plate — the "MULTIPLIER" plate on chains (UI).
                   idle (4 s loop): a slow sway on the chains;
                   update (0.6 s): the value pops (new total), a flash.
                   The value is text drawn by the game at bone `value`.
Chip value = skin val_2 / val_3 / val_5 / val_7 / val_9 (setSkinByName).

Usage: python scripts/gc_multiplier_spine.py <assets_dir> <out_root>
"""
import json, os, sys
import numpy as np
from PIL import Image

A, OUT_ROOT = sys.argv[1], sys.argv[2]
VALUES = [2, 3, 5, 7, 9]
CELL = (474 + 4 * 197 + 98.5, 141 + 2 * 200 + 100)   # PSB centre of the cell the coin sits in
COIN_BOX = (1279, 567, 1437, 723)
VAL_BOX = {2: (1316, 611, 1399, 669), 3: (1315, 610, 1403, 672), 5: (1316, 609, 1400, 674), 7: (1314, 607, 1398, 668), 9: (1316, 612, 1400, 672)}
PLATE_BOX = (1485, -27, 1788, 229)
PVAL_BOX = {2: (1595, 149, 1678, 207), 3: (1593, 149, 1681, 211), 5: (1593, 148, 1677, 213), 7: (1592, 147, 1676, 208), 9: (1593, 151, 1677, 211)}

def ease(t0, v0, t1, v1, k=0.42):
    d = t1 - t0
    return [round(t0 + d * k, 4), v0, round(t1 - d * k, 4), v1]

def keys(pts, kind):
    out = []
    for i, (t, *v) in enumerate(pts):
        k = {'time': round(t, 4)}
        if kind == 'rotate': k['value'] = v[0]
        else: k['x'], k['y'] = v[0], v[1]
        if i + 1 < len(pts):
            t1, *v1 = pts[i + 1]
            k['curve'] = sum((ease(t, a, t1, b) for a, b in zip(v, v1)), [])
        out.append(k)
    return out

def rgba(rgb, pts):
    out, ch = [], [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    for i, (t, a) in enumerate(pts):
        k = {'time': round(t, 4), 'color': f'{rgb}{round(a * 255):02x}'}
        if i + 1 < len(pts):
            t1, a1 = pts[i + 1]; c = ease(t, a, t1, a1)
            k['curve'] = sum(([c[0], round(v, 4), c[2], round(v, 4)] for v in ch), []) + c
        out.append(k)
    return out

def radial(size, power=2.0):
    y, x = np.mgrid[0:size, 0:size]; r = np.hypot(x - size / 2 + .5, y - size / 2 + .5) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** power
    im = np.zeros((size, size, 4), np.uint8); im[..., :3] = 255; im[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(im)

def ring(size, width=0.12):
    y, x = np.mgrid[0:size, 0:size]; r = np.hypot(x - size / 2 + .5, y - size / 2 + .5) / (size / 2)
    a = np.exp(-((r - 0.85) / width) ** 2) * (r < 1)
    im = np.zeros((size, size, 4), np.uint8); im[..., :3] = 255; im[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(im)

def write_atlas(out, tiles):
    pw = sum(im.width + 2 for _, im in tiles); ph = max(im.height for _, im in tiles)
    page = Image.new('RGBA', (pw, ph)); x = 0
    lines = ['animation.png', f'size:{pw},{ph}', 'filter:Linear,Linear']
    for n, im in tiles:
        page.paste(im, (x, 0)); lines += [n, f'bounds:{x},0,{im.width},{im.height}']; x += im.width + 2
    page.save(os.path.join(out, 'animation.png'), optimize=True)
    open(os.path.join(out, 'animation.atlas'), 'w').write('\n'.join(lines) + '\n')

def centre(box, origin, canvas_left=-100.0, canvas_top=100.0):
    """PSB box -> skeleton coords (y up) around origin, snapped so the image's
    left / top edges land on whole pixels of the static canvas (else the
    skeleton draws half a pixel off the static and looks soft)."""
    w, h = box[2] - box[0], box[3] - box[1]
    cx = (box[0] + box[2]) / 2 - origin[0]
    cy = origin[1] - (box[1] + box[3]) / 2
    cx = round(cx - w / 2 - canvas_left) + canvas_left + w / 2
    cy = canvas_top - round(canvas_top - (cy + h / 2)) - h / 2
    return cx, cy

def skins_for(slot, src_prefix, boxes, origin, bone_xy, canvas_left=-100.0, canvas_top=100.0):
    out = []
    for v in VALUES:
        x, y = centre(boxes[v], origin, canvas_left, canvas_top)
        im = Image.open(os.path.join(A, f'{src_prefix}_x{v}.png'))
        out.append({'name': f'val_{v}', 'attachments': {slot: {'value': {
            'name': f'value_x{v}', 'x': round(x - bone_xy[0], 2), 'y': round(y - bone_xy[1], 2), 'width': im.width, 'height': im.height}}}})
    return out

# ---- the reel symbol -----------------------------------------------------------
def symbol():
    out = os.path.join(OUT_ROOT, 'multiplier'); os.makedirs(out, exist_ok=True)
    coin = Image.open(os.path.join(A, 'coin_coin.png')).convert('RGBA')
    vals = {v: Image.open(os.path.join(A, f'coin_x{v}.png')).convert('RGBA') for v in VALUES}
    tiles = [('coin', coin)] + [(f'value_x{v}', vals[v]) for v in VALUES] + [('glow', radial(128, 1.6)), ('ring', ring(128))]
    write_atlas(out, tiles)
    cx, cy = centre(COIN_BOX, CELL)
    vx, vy = centre(VAL_BOX[3], CELL)
    bones = [{'name': 'root'}, {'name': 'chip', 'parent': 'root', 'x': cx, 'y': cy},
             {'name': 'value', 'parent': 'chip', 'x': round(vx - cx, 2), 'y': round(vy - cy, 2)},
             {'name': 'fx', 'parent': 'root', 'x': cx, 'y': cy}]
    slots = [{'name': 'glow', 'bone': 'fx', 'attachment': 'glow', 'color': 'ffc84600', 'blend': 'additive'},
             {'name': 'coin', 'bone': 'chip', 'attachment': 'coin'},
             {'name': 'value', 'bone': 'value', 'attachment': 'value'},
             {'name': 'flash', 'bone': 'value', 'attachment': 'glow', 'color': 'fff4d200', 'blend': 'additive'},
             {'name': 'ring', 'bone': 'fx', 'attachment': 'ring', 'color': 'ffd25a00', 'blend': 'additive'}]
    skin = {'coin': {'coin': {'width': coin.width, 'height': coin.height}},
            'glow': {'glow': {'width': 260, 'height': 260}}, 'ring': {'ring': {'width': 190, 'height': 190}},
            'flash': {'glow': {'width': 120, 'height': 120}}}
    vb = (vx, vy)
    extra = skins_for('value', 'coin', VAL_BOX, CELL, vb)
    # the default skin carries x3 too, so the skeleton shows a value without a skin
    skin['value'] = {'value': dict(extra[1]['attachments']['value']['value'])}
    landing = {'bones': {
        'chip': {'scale': keys([(0, 1, 1), (0.08, 1.06, 0.92), (0.2, 0.97, 1.03), (0.32, 1, 1), (0.7, 1, 1)], 'scale')},
        'value': {'scale': keys([(0, 0, 0), (0.15, 0, 1), (0.42, 1.28, 1.28), (0.58, 0.95, 0.95), (0.7, 1, 1)], 'scale')}},
        'slots': {'flash': {'rgba': rgba('fff4d2', [(0, 0), (0.15, 0), (0.32, 0.85), (0.7, 0)])},
                  'value': {'rgba': rgba('ffffff', [(0, 0), (0.15, 0), (0.25, 1), (0.7, 1)])}}}
    win = {'bones': {
        'chip': {'scale': keys([(0, 1, 1), (0.25, 1.12, 1.12), (0.55, 0.98, 0.98), (0.8, 1.03, 1.03), (1.3, 1, 1)], 'scale'),
                 'rotate': keys([(0, 0), (0.2, 6), (0.45, -5), (0.7, 2.5), (0.95, 0), (1.3, 0)], 'rotate')},
        'value': {'scale': keys([(0, 1, 1), (0.15, 1, 1), (0.45, 1.3, 1.3), (0.75, 1, 1), (1.3, 1, 1)], 'scale')},
        'fx': {'scale': keys([(0, 1, 1), (0.3, 1.15, 1.15), (1.3, 1, 1)], 'scale')}},
        'slots': {'glow': {'rgba': rgba('ffc846', [(0, 0), (0.3, 0.75), (0.9, 0.35), (1.3, 0)])},
                  'flash': {'rgba': rgba('fff4d2', [(0, 0), (0.4, 0.7), (0.9, 0)])},
                  'ring': {'rgba': rgba('ffd25a', [(0, 0), (0.15, 0.9), (0.8, 0), (1.3, 0)])}}}
    win['bones']['ringb'] = {}
    # ring expands with its own scale on the fx bone already; give it a separate growth
    win['bones'].pop('ringb')
    J = {'skeleton': {'spine': '4.1.24', 'x': -100, 'y': -100, 'width': 200, 'height': 200},
         'bones': bones, 'slots': slots, 'skins': [{'name': 'default', 'attachments': skin}] + extra,
         'animations': {'landing': landing, 'win': win}}
    json.dump(J, open(os.path.join(out, 'animation.json'), 'w'), separators=(',', ':'))
    # static: the 200x200 tile, chip + x3 as laid out in the PSB
    st = Image.new('RGBA', (200, 200))
    st.alpha_composite(coin, (int(round(100 + cx - coin.width / 2)), int(round(100 - cy - coin.height / 2))))
    st.alpha_composite(vals[3], (round(100 + vx - vals[3].width / 2), round(100 - vy - vals[3].height / 2)))
    st.save(os.path.join(out, 'static.png'), optimize=True)
    print('multiplier ok')

# ---- the UI plate --------------------------------------------------------------
# The value is TEXT drawn by the game (free-spins totals add up: x17, x33 …), so
# the skeleton only carries the plate and an empty bone `value` at the centre of
# the plate's window (scale pops in `update`; text follows the bone).
def plate():
    out = os.path.join(OUT_ROOT, 'multiplier_plate'); os.makedirs(out, exist_ok=True)
    pl = Image.open(os.path.join(A, 'mult_multiplier.png')).convert('RGBA')
    write_atlas(out, [('plate', pl), ('glow', radial(128, 1.6))])
    W, H = pl.size
    origin = ((PLATE_BOX[0] + PLATE_BOX[2]) / 2, (PLATE_BOX[1] + PLATE_BOX[3]) / 2)
    top = (0, H / 2)                                     # sway pivot: where the chains hang from
    # window centre = centre of the value art boxes (they all share it)
    vx, vy = centre(PVAL_BOX[3], origin, -W / 2, H / 2)
    bones = [{'name': 'root'}, {'name': 'hang', 'parent': 'root', 'x': top[0], 'y': top[1]},
             {'name': 'value', 'parent': 'hang', 'x': round(vx - top[0], 2), 'y': round(vy - top[1], 2)}]
    slots = [{'name': 'plate', 'bone': 'hang', 'attachment': 'plate'},
             {'name': 'flash', 'bone': 'value', 'attachment': 'glow', 'color': 'fff0be00', 'blend': 'additive'}]
    skin = {'plate': {'plate': {'x': 0, 'y': -H / 2, 'width': W, 'height': H}},
            'flash': {'glow': {'width': 200, 'height': 140}}}
    idle = {'bones': {'hang': {'rotate': keys([(0, 0), (1.0, 1.2), (2.0, 0), (3.0, -1.2), (4.0, 0)], 'rotate')}}}
    update = {'bones': {
        'value': {'scale': keys([(0, 1, 1), (0.12, 0.6, 0.6), (0.3, 1.25, 1.25), (0.45, 0.96, 0.96), (0.6, 1, 1)], 'scale')},
        'hang': {'scale': keys([(0, 1, 1), (0.2, 1.05, 1.05), (0.6, 1, 1)], 'scale')}},
        'slots': {'flash': {'rgba': rgba('fff0be', [(0, 0), (0.25, 0.9), (0.6, 0)])}}}
    J = {'skeleton': {'spine': '4.1.24', 'x': -W / 2, 'y': -H / 2, 'width': W, 'height': H},
         'bones': bones, 'slots': slots, 'skins': [{'name': 'default', 'attachments': skin}],
         'animations': {'idle': idle, 'update': update}}
    json.dump(J, open(os.path.join(out, 'animation.json'), 'w'), separators=(',', ':'))
    pl.save(os.path.join(out, 'static.png'), optimize=True)   # the plate without a value
    h = PVAL_BOX[3][3] - PVAL_BOX[3][1]
    json.dump({'value': {'text': 'x17', 'box': [200, h]}}, open(os.path.join(out, 'text_marks.json'), 'w'), indent=1)
    print('multiplier_plate ok')

symbol(); plate()
