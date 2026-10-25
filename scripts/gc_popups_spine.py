"""Gangsta Casino popups as generated Spine 4.1 skeletons, from the layers cut
by scripts/gc_popups_extract.py (designer's Desk_Gangsta_Slot_F.psb).

Every popup has three clips (product rules):
  intro  — builds the popup up from nothing; its LAST frame = the rest pose;
  idle   — a calm loop; its FIRST and LAST frame = the rest pose;
  outro  — starts FROM the rest pose (= idle's last frame) and takes it away.
Rest pose = setup pose = the PSB layout, so the static is the PSB popup.

Layer roles (by PSB name / group): dim (the 70 % black fill), rays (the rays
group), title (the word art), plate (the amount / count plate, the case),
deco (money, coins, the uzi …: fly in from the centre, bob in idle, fly out),
button (accept / decline). The amount ("1 000 000 USD") and the spin count
("99") are NOT baked — they are drawn by code at bones `amount` / `count`
(the type layer's centre; bone scale 0 -> 1 in intro, so text can follow it).

Usage: python scripts/gc_popups_spine.py <extract_dir> <out_root>
"""
import json, math, os, sys
from PIL import Image

SRC, OUT_ROOT = sys.argv[1], sys.argv[2]
W, H = 1932, 940
POPUPS = ['big_win', 'mega_win', 'epic_win', 'buy_free_spins', 'bonus_spins_win', 'bonus_spins_total_win']
TITLES = {'big_win', 'layer_133', 'epic_win', 'buy_free_spins', 'text', 'bonus', 'spins', 'win'}
PLATES = {'input', 'layer_156', 'case'}
BUTTONS = {'accept', 'decline'}
T_IN, T_IDLE, T_OUT = 0.9, 3.0, 0.5

def role(e):
    n, g = e['name'], e['group'].lower()
    if e['kind'] == 'solidcolorfill': return 'dim'
    if e['kind'] == 'type': return 'text'
    if 'rays' in g: return 'ray'
    if n in BUTTONS: return 'button'
    if n in TITLES: return 'title'
    if any(n.startswith(p) for p in PLATES): return 'plate'
    return 'deco'

def ease(t0, v0, t1, v1, k=0.42):
    d = t1 - t0
    return [round(t0 + d * k, 4), v0, round(t1 - d * k, 4), v1]

def chan_keys(pts, kind):
    """pts [(t, v...)] -> 4.1 timeline keys with ease handles, kind in
    rotate / translate / scale / alpha."""
    keys = []
    for i, (t, *v) in enumerate(pts):
        k = {'time': round(t, 4)}
        if kind == 'rotate': k['value'] = v[0]
        elif kind in ('translate', 'scale'): k['x'], k['y'] = v[0], v[1]
        if i + 1 < len(pts):
            t1, *v1 = pts[i + 1]
            k['curve'] = sum((ease(t, a, t1, b) for a, b in zip(v, v1)), [])
        keys.append(k)
    return keys

def rgba_keys(rgb, pts):
    out = []
    ch = [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    for i, (t, a) in enumerate(pts):
        k = {'time': round(t, 4), 'color': f'{rgb}{max(0, min(255, round(a * 255))):02x}'}
        if i + 1 < len(pts):
            t1, a1 = pts[i + 1]
            c = ease(t, a, t1, a1)
            k['curve'] = sum(([c[0], round(v, 4), c[2], round(v, 4)] for v in ch), []) + c
        out.append(k)
    return out

def pack(images, max_w=2048):
    """Shelf-pack [(name, img)] into pages <= max_w wide. -> [(page_img, [(name, x, y)])]."""
    items = sorted(images, key=lambda t: -t[1].height)
    pages, cur, x, y, row_h, page_w = [], [], 0, 0, 0, 0
    def flush():
        nonlocal cur
        if not cur: return
        pw = max(px + im.width for _, im, px, _ in cur); ph = max(py + im.height for _, im, _, py in cur)
        page = Image.new('RGBA', (pw, ph))
        for n, im, px, py in cur: page.paste(im, (px, py))
        pages.append((page, [(n, px, py, im.width, im.height) for n, im, px, py in cur]))
        cur = []
    for n, im in items:
        if x + im.width > max_w:
            x, y, row_h = 0, y + row_h + 2, 0
        if y + im.height > max_w:
            flush(); x, y, row_h = 0, 0, 0
        cur.append((n, im, x, y)); x += im.width + 2; row_h = max(row_h, im.height)
    flush()
    return pages

def build(slug):
    d = os.path.join(SRC, slug)
    layers = json.load(open(os.path.join(d, 'layout.json')))['layers']
    out = os.path.join(OUT_ROOT, f'popup_{slug}'); os.makedirs(out, exist_ok=True)
    bones, slots, skin, imgs = [{'name': 'root'}], [], {}, []
    roles, marks = {}, {}
    for e in layers:
        r = role(e); x0, y0, x1, y1 = e['bbox']
        cx, cy = (x0 + x1) / 2 - W / 2, H / 2 - (y0 + y1) / 2
        if r == 'text':
            mark = 'count' if e.get('text', '').strip().isdigit() else 'amount'
            bones.append({'name': mark, 'parent': 'root', 'x': round(cx, 2), 'y': round(cy, 2)})
            marks[mark] = {'text': e.get('text', '').strip(), 'font_size': e.get('font_size'), 'box': [x1 - x0, y1 - y0]}
            roles[mark] = 'mark'
            continue
        bn = e['name']
        if r == 'dim':
            bones.append({'name': bn, 'parent': 'root'})
            slots.append({'name': bn, 'bone': bn, 'attachment': 'black', 'color': f'000000{round(e["opacity"] * 255):02x}'})
            skin[bn] = {'black': {'width': 2600, 'height': 1600}}
            roles[bn] = r
            continue
        im = Image.open(os.path.join(d, e['file'])).convert('RGBA')
        bones.append({'name': bn, 'parent': 'root', 'x': round(cx, 2), 'y': round(cy, 2)})
        a = round(e['opacity'] * 255)
        slot = {'name': bn, 'bone': bn, 'attachment': bn}
        if a < 255: slot['color'] = f'ffffff{a:02x}'
        slots.append(slot)
        skin[bn] = {bn: {'width': im.width, 'height': im.height}}
        imgs.append((bn, im)); roles[bn] = r
    imgs.append(('black', Image.new('RGBA', (8, 8), (255, 255, 255, 255))))
    # atlas (straight alpha)
    lines = []
    for i, (page, regs) in enumerate(pack(imgs)):
        pn = 'animation.png' if i == 0 else f'animation-p{i + 1}.png'
        page.save(os.path.join(out, pn), optimize=True)
        lines += [pn, f'size:{page.width},{page.height}', 'filter:Linear,Linear']
        for n, x, y, w, h in regs: lines += [n, f'bounds:{x},{y},{w},{h}']
        lines.append('')
    open(os.path.join(out, 'animation.atlas'), 'w').write('\n'.join(lines))

    B = {b['name']: b for b in bones}
    rest_a = {s['name']: (int(s.get('color', 'ffffffff')[6:], 16) / 255, s.get('color', 'ffffffff')[:6]) for s in slots}
    intro, idle, outro = {'bones': {}, 'slots': {}}, {'bones': {}, 'slots': {}}, {'bones': {}, 'slots': {}}
    deco = [n for n, r in roles.items() if r == 'deco']
    rays = [n for n, r in roles.items() if r == 'ray']
    for n, r in roles.items():
        bx, by = B[n].get('x', 0), B[n].get('y', 0)
        a, rgb = rest_a.get(n, (1, 'ffffff'))
        ib, isl = intro['bones'].setdefault(n, {}), intro['slots']
        ob, osl = outro['bones'].setdefault(n, {}), outro['slots']
        db = idle['bones'].setdefault(n, {})
        if r == 'dim':
            isl[n] = {'rgba': rgba_keys(rgb, [(0, 0), (0.3, a), (T_IN, a)])}
            osl[n] = {'rgba': rgba_keys(rgb, [(0, a), (0.15, a), (T_OUT, 0)])}
        elif r == 'ray':
            i = rays.index(n)
            ib['scale'] = chan_keys([(0, 0.3, 0.3), (0.55, 1, 1), (T_IN, 1, 1)], 'scale')
            ib['rotate'] = chan_keys([(0, -25 + i * 18), (0.6, 0), (T_IN, 0)], 'rotate')
            isl[n] = {'rgba': rgba_keys(rgb, [(0, 0), (0.35, a), (T_IN, a)])}
            sgn = (1, -1, 1)[i % 3]
            db['rotate'] = chan_keys([(0, 0), (T_IDLE / 2, 5 * sgn), (T_IDLE, 0)], 'rotate')
            idle['slots'][n] = {'rgba': rgba_keys(rgb, [(0, a), (T_IDLE * (0.35 + 0.15 * i), a * 0.7), (T_IDLE, a)])}
            ob['scale'] = chan_keys([(0, 1, 1), (T_OUT, 1.25, 1.25)], 'scale')
            osl[n] = {'rgba': rgba_keys(rgb, [(0, a), (T_OUT * 0.8, 0), (T_OUT, 0)])}
        elif r == 'title':
            t0 = 0.12 + 0.06 * [m for m, rr in roles.items() if rr == 'title'].index(n)
            ib['scale'] = chan_keys([(0, 0, 0), (t0, 0, 0), (t0 + 0.3, 1.18, 1.18), (t0 + 0.48, 0.96, 0.96), (min(T_IN, t0 + 0.62), 1, 1), (T_IN, 1, 1)], 'scale')
            isl[n] = {'rgba': rgba_keys(rgb, [(0, 0), (t0, 0), (t0 + 0.12, a), (T_IN, a)])}
            db['scale'] = chan_keys([(0, 1, 1), (T_IDLE / 2, 1.04, 1.04), (T_IDLE, 1, 1)], 'scale')
            ob['scale'] = chan_keys([(0, 1, 1), (0.3, 1.15, 1.15), (T_OUT, 1.15, 1.15)], 'scale')
            osl[n] = {'rgba': rgba_keys(rgb, [(0, a), (0.3, 0), (T_OUT, 0)])}
        elif r in ('plate', 'mark'):
            ib['scale'] = chan_keys([(0, 0.6, 0.6), (0.3, 0.6, 0.6), (0.62, 1.06, 1.06), (0.78, 1, 1), (T_IN, 1, 1)], 'scale')
            ib['translate'] = chan_keys([(0, 0, -40), (0.3, 0, -40), (0.66, 0, 0), (T_IN, 0, 0)], 'translate')
            if r == 'plate':
                isl[n] = {'rgba': rgba_keys(rgb, [(0, 0), (0.3, 0), (0.5, a), (T_IN, a)])}
                osl[n] = {'rgba': rgba_keys(rgb, [(0, a), (0.35, 0), (T_OUT, 0)])}
            else:  # the code-drawn text follows this bone's scale: 0 = hidden
                ib['scale'] = chan_keys([(0, 0, 0), (0.42, 0, 0), (0.7, 1.08, 1.08), (0.82, 1, 1), (T_IN, 1, 1)], 'scale')
            ob['scale'] = chan_keys([(0, 1, 1), (0.35, 0.9 if r == 'plate' else 0, 0.9 if r == 'plate' else 0), (T_OUT, 0.9 if r == 'plate' else 0, 0.9 if r == 'plate' else 0)], 'scale')
        elif r == 'button':
            i = 0 if n == 'accept' else 1
            ib['scale'] = chan_keys([(0, 0.6, 0.6), (0.5 + i * 0.06, 0.6, 0.6), (0.76 + i * 0.06, 1.05, 1.05), (T_IN, 1, 1)], 'scale')
            isl[n] = {'rgba': rgba_keys(rgb, [(0, 0), (0.5 + i * 0.06, 0), (0.66 + i * 0.06, a), (T_IN, a)])}
            if n == 'accept':
                db['scale'] = chan_keys([(0, 1, 1), (T_IDLE / 2, 1.04, 1.04), (T_IDLE, 1, 1)], 'scale')
            osl[n] = {'rgba': rgba_keys(rgb, [(0, a), (0.25, 0), (T_OUT, 0)])}
        else:  # deco: from the centre out to its place; bob in idle; out on exit
            i = deco.index(n)
            st = 0.2 + 0.45 * i / max(1, len(deco) - 1)
            en = min(T_IN, st + 0.4)
            ib['translate'] = chan_keys([(0, -bx * 0.85, -by * 0.85), (st, -bx * 0.85, -by * 0.85), (en, 0, 0), (T_IN, 0, 0)], 'translate')
            ib['scale'] = chan_keys([(0, 0.2, 0.2), (st, 0.2, 0.2), (en, 1, 1), (T_IN, 1, 1)], 'scale')
            ib['rotate'] = chan_keys([(0, -40 if i % 2 else 40), (st, -40 if i % 2 else 40), (en, 0), (T_IN, 0)], 'rotate')
            isl[n] = {'rgba': rgba_keys(rgb, [(0, 0), (st, 0), (st + 0.12, a), (T_IN, a)])}
            ph = (i * 0.37) % 1
            p1, p2 = T_IDLE * (0.15 + 0.3 * ph), T_IDLE * (0.55 + 0.3 * ph)
            amp = 6 if i % 2 else -6
            db['translate'] = chan_keys([(0, 0, 0), (p1, 0, amp), (p2, 0, -amp), (T_IDLE, 0, 0)], 'translate')
            db['rotate'] = chan_keys([(0, 0), (p1, 2.5 if i % 2 else -2.5), (p2, -2.5 if i % 2 else 2.5), (T_IDLE, 0)], 'rotate')
            k = 1.6
            ob['translate'] = chan_keys([(0, 0, 0), (T_OUT * 0.85, bx * (k - 1), by * (k - 1)), (T_OUT, bx * (k - 1), by * (k - 1))], 'translate')
            osl[n] = {'rgba': rgba_keys(rgb, [(0, a), (T_OUT * 0.8, 0), (T_OUT, 0)])}
    for anim in (intro, idle, outro):
        anim['bones'] = {k: v for k, v in anim['bones'].items() if v}
    J = {'skeleton': {'spine': '4.1.24', 'x': -W / 2, 'y': -H / 2, 'width': W, 'height': H},
         'bones': bones, 'slots': slots, 'skins': [{'name': 'default', 'attachments': skin}],
         'animations': {'intro': intro, 'idle': idle, 'outro': outro}}
    json.dump(J, open(os.path.join(out, 'animation.json'), 'w'), separators=(',', ':'))
    json.dump(marks, open(os.path.join(out, 'text_marks.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'popup_{slug}', 'layers', len(imgs) - 1, 'json KB', os.path.getsize(os.path.join(out, 'animation.json')) // 1024, 'marks', list(marks))

for s in POPUPS:
    build(s)
