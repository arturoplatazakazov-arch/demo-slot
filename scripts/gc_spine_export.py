"""Gangsta Casino symbol Spine exports packed by the layout spec ("ТЗ на
слоты", Animation): /<symbol>/animation.atlas|json|png (+ animation-p2.png…),
Spine 4.1 runtime. The wheel/multiplier chip (wof) is left out — not ready.
Also checks every pack against the spec and writes report.json for the
test page (front/gangsta-casino-anim-test.html).
Usage: python scripts/gc_spine_export.py"""
import json, os, re, shutil

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front')
SRC = os.path.join(ROOT, 'img', 'gangsta-casino', 'spine')
DST = os.path.join(ROOT, 'spine-export', 'gangsta-casino')
SYMBOLS = ['common_1', 'common_2', 'common_3', 'common_4',
           'rare_purple', 'rare_yellow', 'rare_blue', 'rare_green', 'scatter', 'wild']
# spec: clip names and lengths per group
SPEC = {'common': {'win': 1.3}, 'rare': {'win': 1.3}, 'wild': {'win': 1.3, 'win_small': 1.3, 'win_big': 1.3, 'expand': 1.0, 'idle': None},
        'scatter': {'landing': None, 'idle': None, 'win': 1.7}}

GLOW_REST_SLOTS = {c: ('aura', 'back_glow') for c in ['common_1', 'common_2', 'common_3', 'common_4']}

def ease(t0, v0, t1, v1):
    """4.1 JSON bezier (absolute time / value) — ease in-out for one channel."""
    d = t1 - t0
    return [round(t0 + d * 0.42, 4), v0, round(t1 - d * 0.42, 4), v1]

def key2(t, x, y, nxt=None):
    k = {'time': t, 'x': x, 'y': y}
    if nxt: k['curve'] = ease(t, x, nxt[0], nxt[1]) + ease(t, y, nxt[0], nxt[2])
    return k

def scale_keys(pts):
    return [key2(t, x, y, pts[i + 1] if i + 1 < len(pts) else None) for i, (t, x, y) in enumerate(pts)]

def alpha_keys(rgb, pts):
    out = []
    for i, (t, a) in enumerate(pts):
        k = {'time': t, 'color': f'{rgb}{a:02x}'}
        if i + 1 < len(pts):
            t1, a1 = pts[i + 1]
            c = ease(t, a / 255, t1, a1 / 255)
            ch = [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            k['curve'] = sum(([c[0], round(v, 4), c[2], round(v, 4)] for v in ch), []) + c  # r, g, b flat; a eased
        out.append(k)
    return out

def add_scatter_clips(J):
    """Spec clips the delivery lacks — light, start and end in the setup pose
    (= the static), and they key only what win does not need at rest."""
    slots = {x['name']: x for x in J['slots']}
    rgb = lambda n: slots[n]['color'][:6]
    # landing 0.45 s: a quick squash on impact, a glow puff and one ring
    J['animations']['landing'] = {
        'bones': {
            'main': {'scale': scale_keys([(0, 1, 1), (0.06, 1.07, 0.9), (0.16, 0.96, 1.05), (0.27, 1.02, 0.985), (0.4, 1, 1)])},
            'ring1': {'scale': scale_keys([(0, 0.3, 0.3), (0.4, 1.7, 1.7)])},
        },
        'slots': {
            'back_glow': {'rgba': alpha_keys(rgb('back_glow'), [(0, 0), (0.08, 0x66), (0.45, 0)])},
            'ring1': {'rgba': alpha_keys(rgb('ring1'), [(0, 0), (0.06, 0x99), (0.4, 0)])},
        },
    }
    # idle 2 s loop: slow breathing, a warm G glow and one shine pass over
    # the G and the plate, three diamond twinkles
    idle_bones = {
        'main': {'scale': scale_keys([(0, 1, 1), (1.0, 1.025, 1.025), (2.0, 1, 1)])},
        'shine_g': {'translate': [{'time': 0.55, 'curve': ease(0.55, 0, 1.05, 320) + ease(0.55, 0, 1.05, 0)},
                                  {'time': 1.05, 'x': 320, 'curve': 'stepped'}, {'time': 2.0}]},
        'shine_p': {'translate': [{'time': 0.8, 'curve': ease(0.8, 0, 1.4, 460) + ease(0.8, 0, 1.4, 0)},
                                  {'time': 1.4, 'x': 460, 'curve': 'stepped'}, {'time': 2.0}]},
    }
    idle_slots = {'g_glow': {'rgba': alpha_keys(rgb('g_glow'), [(0, 0), (1.0, 0x48), (2.0, 0)])}}
    for name, t in (('diamond3', 0.25), ('diamond8', 1.15), ('diamond11', 1.6)):
        idle_bones[name] = {'scale': scale_keys([(t, 0.15, 0.15), (t + 0.12, 0.9, 0.9), (t + 0.3, 0.15, 0.15)])}
        idle_slots[name] = {'rgba': alpha_keys(rgb(name), [(t, 0), (t + 0.12, 0xff), (t + 0.3, 0)])}
    J['animations']['idle'] = {'bones': idle_bones, 'slots': idle_slots}

def rest_match_scatter(page_path, static_path):
    """Spec: setup / first / last frame == the static. The scatter's pieces
    (coin, G, plate, text) were cut from an older render of the art, so at
    rest the skeleton looked different from scatter.png. Re-colour each piece
    from the static wherever it is visible at rest (everywhere except under a
    fully opaque piece above it, which keeps its own pixels for when the G /
    the plate move). Alphas stay the pieces' own. Region placement: the
    static is the 200x200 tile around the skeleton origin (TILE_BOX)."""
    import numpy as np
    from PIL import Image
    page = np.asarray(Image.open(page_path).convert('RGBA')).astype(np.float64)
    st = np.asarray(Image.open(static_path).convert('RGBA')).astype(np.float64)
    def unpm(a):
        o = a.copy(); al = a[..., 3:4] / 255
        o[..., :3] = np.where(al > 0, a[..., :3] / np.maximum(al, 1e-6), 0)
        return o
    # name: (atlas x, y, w, h, rotated cw, static x, y) — bottom to top
    pieces = {'coin': (1539, 324, 173, 170, False, 12, 6), 'plate': (1354, 7, 183, 59, False, 8, 134),
              'g_letter': (1528, 227, 77, 95, False, 60, 34), 'text': (1492, 378, 150, 34, True, 24, 147)}
    above = {'coin': ['plate', 'g_letter', 'text'], 'plate': ['text'], 'g_letter': [], 'text': []}
    def region(name):
        px, py, w, h, rot, _, _ = pieces[name]
        r = page[py:py + (w if rot else h), px:px + (h if rot else w)]
        return np.rot90(r, 3) if rot else r
    orig = {n: unpm(region(n)) for n in pieces}
    for name, (px, py, w, h, rot, sx, sy) in pieces.items():
        cur = orig[name]
        S = st[sy:sy + h, sx:sx + w]
        cover = np.zeros((h, w))  # max alpha of the pieces drawn above, in this piece's pixels
        for up in above[name]:
            _, _, uw, uh, _, ux, uy = pieces[up]
            ox, oy = ux - sx, uy - sy
            a = orig[up][..., 3] / 255
            x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(w, ox + uw), min(h, oy + uh)
            if x1 > x0 and y1 > y0:
                cover[y0:y1, x0:x1] = np.maximum(cover[y0:y1, x0:x1], a[y0 - oy:y1 - oy, x0 - ox:x1 - ox])
        use = (cover < 0.98) & (S[..., 3] > 0)
        new = cur.copy()
        new[..., :3][use] = S[..., :3][use]
        pm = new.copy(); pm[..., :3] *= pm[..., 3:4] / 255
        if rot: pm = np.rot90(pm, 1)
        page[py:py + pm.shape[0], px:px + pm.shape[1]] = pm
    Image.fromarray(np.clip(np.round(page), 0, 255).astype(np.uint8)).save(page_path, optimize=True)

def stretch(anim, k):
    """Every key time (and the curves' time handles) x k."""
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get('time'), (int, float)): o['time'] = round(o['time'] * k, 4)
            c = o.get('curve')
            if isinstance(c, list):
                o['curve'] = [round(v * k, 4) if i % 2 == 0 else v for i, v in enumerate(c)]
            for v in o.values():
                if isinstance(v, (dict, list)): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(anim)

# Rare frames: the light running round the frame (run1_* / run2_*) sat under
# the head that breaks out above the frame (clip_top / char_top), so the head
# cut the glow with a hard edge. Draw it above everything (product).
RUN_ON_TOP = {'rare_purple', 'rare_yellow', 'rare_blue', 'rare_green'}
# spec win length per group where the delivery differs (rare: 1.5 s -> 1.3 s)
WIN_LENGTH = {'rare': 1.3, 'scatter': 1.7}
# wild (product): every win 1.3 s, expand 1 s
CLIP_LENGTH = {'wild': {'win_small': 1.3, 'win_big': 1.3, 'expand': 1.0}}
# static.png goes into every folder (product); shift = (dx, dy) px to put the
# static's centre on the skeleton origin, measured by scripts/gc_anim_check.py
# (rare_yellow's static sat 1 px higher than its animation)
STATIC_SHIFT = {'rare_yellow': (0, 1)}

def runs_on_top(J):
    run = [x for x in J['slots'] if x['name'].startswith(('run1_', 'run2_'))]
    J['slots'] = [x for x in J['slots'] if x not in run] + run
    return len(run)

# wild idle_big, simplified (product: «айдл чуть проще»): the particles go —
# comets, dust, sparks, stars, glints, light pillar, rays, rings, jewellery
# twinkles; the breathing, head sway, blink, frame / text glow and one shine
# over WILD stay.
WILD_PARTICLES = re.compile(r'^(comet\d+_\d+(_g)?|dust\d+|spark\d+|star\d+|tg\d+|pillar\d*|rays\d*|rays_[ab]'
                            r'|ring\d*|bulb\d+(_g)?|bandana|earL|earR|pendant|ting|aura|aura_tall)$')
# bones that hold the reel-height layout in idle_big (not wanted on the 1x1 wild)
WILD_LAYOUT = {'bg_b', 'f_bot', 'f_mid', 'f_top', 'gc_bl', 'gc_br', 'gc_tl', 'gc_tr', 'girl_b', 'g_mid', 'text_b'}

def simplify_wild(J):
    ib = J['animations']['idle_big']
    for part in ('bones', 'slots'):
        ib[part] = {k: v for k, v in ib.get(part, {}).items() if not WILD_PARTICLES.match(k)}
    # 1x1 idle: the same calm loop without the reel-height layout keys
    small = json.loads(json.dumps(ib))
    small['bones'] = {k: v for k, v in small['bones'].items() if k not in WILD_LAYOUT}
    J['animations']['idle'] = small

def group(code):
    return 'common' if code.startswith('common') else 'rare' if code.startswith('rare') else code

def duration(anim):
    t = 0.0
    def walk(o):
        nonlocal t
        if isinstance(o, dict):
            if isinstance(o.get('time'), (int, float)): t = max(t, o['time'])
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(anim)
    return round(t, 3)

def atlas_regions(text):
    pages, regions, cur = [], [], None
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s: cur = None; continue
        if s.endswith('.png') or s.endswith('.jpg'):
            pages.append(s); cur = s; continue
        if ':' not in s and cur: regions.append(s)
    return pages, regions

def used_names(J):
    names = set()
    for skin in J.get('skins', []):
        for slot, atts in skin.get('attachments', {}).items():
            for key, a in atts.items():
                if a.get('type') in ('clipping', 'boundingbox', 'point', 'path'): continue
                names.add(a.get('path') or a.get('name') or key)
    return names

shutil.rmtree(DST, ignore_errors=True)
report = {}
for code in SYMBOLS:
    src, dst = os.path.join(SRC, code), os.path.join(DST, code)
    os.makedirs(dst)
    J = json.load(open(os.path.join(src, 'animation.json')))
    notes = []
    if code in RUN_ON_TOP:
        n = runs_on_top(J)
        notes.append(f'свечение по рамке ({n} слотов run*) — поверх всего')
    for clip, need in CLIP_LENGTH.get(code, {}).items():
        a = J['animations'][clip]
        k = need / duration(a)
        if abs(k - 1) > 0.01:
            stretch(a, k)
            notes.append(f'{clip} {duration(a)} с (x{k:.3f})')
    if code == 'wild' and 'win' not in J['animations'] and 'win_small' in J['animations']:
        # spec name for the 1x1 wild win; win_small stays for the game
        J['animations']['win'] = json.loads(json.dumps(J['animations']['win_small']))
        notes.append('добавлен клип win = копия win_small')
    if code == 'wild':
        simplify_wild(J)
        notes.append('idle_big упрощён (без частиц), добавлен idle для маленького')
    if group(code) in WIN_LENGTH:
        w = J['animations']['win']
        need = WIN_LENGTH[group(code)]
        k = need / duration(w)
        if abs(k - 1) > 0.01:
            stretch(w, k)
            notes.append(f'win {"растянут" if k > 1 else "сжат"} до {need} с (x{k:.3f})')
    if code == 'scatter' and 'landing' not in J['animations']:
        add_scatter_clips(J)
        notes.append('добавлены клипы landing (0.45 с) и idle (2 с, цикл)')
    # spec: setup / first / last frame == the static. The weapons' glow slots
    # rest at a visible alpha — rest them at 0 (the in-between keys untouched).
    for slot in J['slots']:
        if slot.get('blend') != 'additive' or len(slot.get('color', '')) != 8 or slot['color'][6:] == '00':
            continue
        if slot['name'] not in GLOW_REST_SLOTS.get(code, ()):
            continue
        rest = slot['color']
        slot['color'] = rest[:6] + '00'
        for anim in J['animations'].values():
            keys = anim.get('slots', {}).get(slot['name'], {}).get('rgba')
            if not keys: continue
            # the first and the final key hold the resting value (setup colour)
            for k in (keys[0], keys[-1]):
                if k.get('color', '').lower() == rest.lower():
                    k['color'] = rest[:6] + '00'
        notes.append(f'свечение «{slot["name"]}» в покое = 0 (кадр 0 и последний = статик)')
    atlas = open(os.path.join(src, 'animation.atlas')).read()
    pages, regions = atlas_regions(atlas)
    # spec page names: animation.png, animation-p2.png, …
    rename = {p: ('animation.png' if i == 0 else f'animation-p{i + 1}.png') for i, p in enumerate(pages)}
    for old, new in rename.items():
        atlas = re.sub(rf'^{re.escape(old)}$', new, atlas, flags=re.M)
        shutil.copy(os.path.join(src, old), os.path.join(dst, new))
    open(os.path.join(dst, 'animation.atlas'), 'w').write(atlas)
    from PIL import Image
    statics = {'static.png': f'{code}.png'}
    if code == 'wild': statics['static_big.png'] = 'wild_big.png'
    for out_name, src_name in statics.items():
        im = Image.open(os.path.join(ROOT, 'img', 'gangsta-casino', 'symbols', src_name)).convert('RGBA')
        dx, dy = STATIC_SHIFT.get(code, (0, 0)) if out_name == 'static.png' else (0, 0)
        if dx or dy:
            moved = Image.new('RGBA', im.size); moved.paste(im, (dx, dy)); im = moved
            notes.append(f'статика сдвинута на ({dx:+d}, {dy:+d}) px — центр = центр анимации')
        im.save(os.path.join(dst, out_name), optimize=True)
    if code == 'scatter':
        rest_match_scatter(os.path.join(dst, 'animation.png'), os.path.join(ROOT, 'img', 'gangsta-casino', 'symbols', 'scatter.png'))
        notes.append('куски coin / G / плашка / текст перекрашены по статике (кадр 0 = статик)')
    json.dump(J, open(os.path.join(dst, 'animation.json'), 'w'), separators=(',', ':'))
    clips = {k: duration(v) for k, v in J['animations'].items()}
    issues = []
    for name, need in SPEC[group(code)].items():
        if name not in clips: issues.append(f'нет клипа «{name}»')
        elif need and abs(clips[name] - need) > 0.02: issues.append(f'«{name}» {clips[name]} с (ТЗ {need} с)')
    unused = sorted(set(regions) - used_names(J))
    if unused: issues.append(f'лишние картинки в атласе: {len(unused)}')
    report[code] = {'clips': clips, 'pages': list(rename.values()), 'issues': issues, 'notes': notes,
                    'spine': J['skeleton'].get('spine'), 'unused': unused}
    print(code, clips, issues, notes)
json.dump(report, open(os.path.join(DST, 'report.json'), 'w'), ensure_ascii=False, indent=1)

# ---- scene + screens (frame, logo, preview / bonus screens) -----------------
# out folder: (source folder, pma, static source, box for rendering / checking)
#   static source 'ui/…' = the designer's PNG; 'render' = the skeleton's resting
#   frame (idle, t=0) rendered by scripts/gc_spine_static.py afterwards.
FEATURE_BOX = [-966, -470, 1932, 940]
FEATURE_BOX_MOB = [-390, -708, 780, 1416]
SCENE = {
    # frames: the skeleton carries the 70 % glass the PSB static leaves out —
    # static = the rendered resting frame, so it matches 1:1
    'frame': ('scene/frame_v2', False, 'render', None),
    'frame_mob': ('scene/frame_mob_v2', False, 'render', None),
    'logo': ('scene/logo_v2', False, 'ui/logo.png', None),
    'logo_mob': ('scene/logo_mob', False, 'ui/logo_mob.png', None),
    'hero_man': ('scene/hero_man', False, 'render', None),
    'hero_woman': ('scene/hero_woman', False, 'render', None),
    'background': ('scene/background_v2', False, 'render', None),
    'background_mob': ('scene/background_mob_v3', False, 'render', None),
    # win lines (scripts/gangsta_casino_winlines.py): 11 paylines on the 5x3 grid
    'winlines': ('winlines', False, 'render', None),
    'feature_screen': ('feature_screen_v2', True, 'render', FEATURE_BOX),
    'feature_screen_mob': ('feature_screen_v2_mob', True, 'render', FEATURE_BOX_MOB),
    'bonus_screen': ('bonus_screen_v4', True, 'render', FEATURE_BOX),
    'bonus_screen_mob': ('bonus_screen_v4_mob', True, 'render', FEATURE_BOX_MOB),
}
from PIL import Image as _Image
SCENE_STATIC_SHIFT = {}
# photo pages replaced by the designer's fixed art (same 1938x1091 framing)
PHOTO_OVERRIDE = {'background': os.path.join(SRC, 'scene', 'background_v2', 'photo1_fixed.png')}

def fix_photo_mesh_bind(J, slot):
    """The photo mesh of the desktop base background was bound with some
    vertices up to 10 px off the spot their UV maps to, so even at rest the
    skyline came out wavy (the weights of a vertex summed to ~0.99, not 1). Put every vertex back on its UV position (same
    weights, bone-local offsets recomputed; bones here are unrotated root
    children). Returns the largest correction in px."""
    import math
    bones = J['bones']
    att = next(iter(J['skins'][0]['attachments'][slot].values()))
    W, H = att['width'], att['height']
    v, uv = att['vertices'], att['uvs']
    out, i, n, worst = [], 0, 0, 0.0
    while i < len(v):
        k = int(v[i]); i += 1
        infl = []
        wx = wy = 0.0
        for _ in range(k):
            bi, lx, ly, w = int(v[i]), v[i + 1], v[i + 2], v[i + 3]; i += 4
            b = bones[bi]; bx, by = b.get('x', 0), b.get('y', 0)
            wx += w * (bx + lx); wy += w * (by + ly); infl.append((bi, bx, by, w))
        tx, ty = uv[2 * n] * W - W / 2, H / 2 - uv[2 * n + 1] * H
        worst = max(worst, math.hypot(wx - tx, wy - ty))
        out.append(k)
        total = sum(w for *_, w in infl) or 1.0  # weights summed to ~0.99 here: that alone shifts a vertex ~10 px at the edges
        for bi, bx, by, w in infl:
            out += [bi, round(tx - bx, 3), round(ty - by, 3), round(w / total, 5)]
        n += 1
    att['vertices'] = out
    return worst

CHANNELS = {'rotate': ('value',), 'translatex': ('value',), 'translatey': ('value',), 'scalex': ('value',),
            'scaley': ('value',), 'translate': ('x', 'y'), 'scale': ('x', 'y')}

def rest_ends(J):
    """Heroes (product): first and last frame identical = the setup pose. Each
    bone channel keeps its motion but gets a linear correction that pins its
    start and end to rest (0 offset; x1 for scale): new = old - lerp(old(0),
    old(T)) + rest. Bezier handles are corrected at their own times."""
    for anim in J['animations'].values():
        T = duration(anim)
        for tls in anim.get('bones', {}).values():
            for kind, keys in tls.items():
                chans = CHANNELS.get(kind)
                if not chans or not keys: continue
                rest = 1.0 if kind.startswith('scale') else 0.0
                for ci, ch in enumerate(chans):
                    a = keys[0].get(ch, rest)
                    # value at T: the last key holds to the end
                    b = keys[-1].get(ch, rest)
                    corr = lambda t: a + (b - a) * (t / T if T else 0) - rest
                    for k in keys:
                        t = k.get('time', 0)
                        k[ch] = round(k.get(ch, rest) - corr(t), 4)
                        c = k.get('curve')
                        if isinstance(c, list):
                            c[ci * 4 + 1] = round(c[ci * 4 + 1] - corr(c[ci * 4]), 4)
                            c[ci * 4 + 3] = round(c[ci * 4 + 3] - corr(c[ci * 4 + 2]), 4)
                    if keys[-1].get('time', 0) < T - 1e-6:  # make the end explicit
                        keys.append({'time': T, ch: rest} if len(chans) == 1 else dict({'time': T}, **{c2: (rest if c2 == ch else keys[-1].get(c2, rest)) for c2 in chans}))

def drop_atlas_regions(atlas, names):
    """Remove regions from a libgdx atlas text; a page left empty goes too.
    Returns (atlas, [(page, x, y, w, h, rotated)] removed)."""
    out, removed = [], []
    for block in atlas.strip('\n').split('\n\n'):
        lines = block.split('\n')
        page, head, regions, cur = lines[0], [], [], None
        for ln in lines[1:]:
            if ':' in ln and cur is None: head.append(ln)
            elif ':' not in ln: cur = [ln]; regions.append(cur)
            else: cur.append(ln)
        kept = []
        for r in regions:
            if r[0].strip() in names:
                b = next((l for l in r if l.strip().startswith('bounds:')), None)
                if b:
                    x, y, w, h = (int(v) for v in b.split(':')[1].split(','))
                    removed.append((page, x, y, w, h, any('rotate' in l for l in r)))
            else:
                kept.append(r)
        if kept:
            out.append('\n'.join([page] + head + ['\n'.join(r) for r in kept]))
    return '\n\n'.join(out) + '\n', removed

FS_RANGE = range(5, 21)

def lighten_bonus_screen(J):
    """Bonus screen (product): drop the heavy club photo (and the side table
    painted on it) — beams, lamp glows, the spin counter, the heroine, logo
    and captions stay. Spin-count variants as skins fs_5 … fs_20: the three
    digit windows show `digit`, which every fs_* skin maps to its digit."""
    gone = {'bg', 'table'}
    J['slots'] = [x for x in J['slots'] if x['name'] not in gone]
    base = J['skins'][0]['attachments']
    for g in gone: base.pop(g, None)
    for anim in J['animations'].values():
        for g in gone: anim.get('slots', {}).pop(g, None)
    proto = base['dig1']['d0']
    for x in J['slots']:
        if x['name'] in ('dig1', 'dig2', 'dig3'): x['attachment'] = 'digit'
    for n in FS_RANGE:
        digits = f'{n:03d}'
        J['skins'].append({'name': f'fs_{n}', 'attachments': {
            f'dig{i + 1}': {'digit': dict(proto, name=f'digit/{d}')} for i, d in enumerate(digits)}})

def smooth_logo_idle(J):
    """Logo idle (product: smooth, not jerky): the delivery's 0.25 s keys were
    rounded to 0.01 of scale and sat 2.1 px above the setup pose, so the loop
    stepped and its first / last frame did not match the static. Rebuilt: a
    slow bob up 3 px and back + a breath of scale, ease in-out, from and to the
    setup pose; the shine pass is kept."""
    idle = J['animations']['idle']
    T = duration(idle)
    def eased(pts, chans):
        out = []
        for i, (t, *v) in enumerate(pts):
            k = {'time': t}
            k.update(dict(zip(chans, v)))
            if i + 1 < len(pts):
                t1, *v1 = pts[i + 1]; d = t1 - t
                k['curve'] = sum(([round(t + d * 0.45, 4), a, round(t1 - d * 0.45, 4), b] for a, b in zip(v, v1)), [])
            out.append(k)
        return out
    h = T / 2
    idle['bones']['main'] = {
        'translate': eased([(0, 0, 0), (h, 0, 3), (T, 0, 0)], ('x', 'y')),
        'scale': eased([(0, 1, 1), (h, 1.012, 1.012), (T, 1, 1)], ('x', 'y')),
    }
scene_report = {}
for out, (src_rel, pma, static_src, box) in SCENE.items():
    src, dst = os.path.join(SRC, src_rel), os.path.join(DST, out)
    os.makedirs(dst)
    J = json.load(open(os.path.join(src, 'animation.json')))
    atlas = open(os.path.join(src, 'animation.atlas')).read()
    pages, _ = atlas_regions(atlas)
    notes = []
    if out.startswith('logo'):
        smooth_logo_idle(J)
        notes.append('idle пересобран плавным (покачивание 3 px + дыхание), начало и конец = статик')
    if out == 'hero_woman':
        for anim in J['animations'].values():
            anim.get('bones', {}).pop('foot', None)
        notes.append('убрано качание ногой (кость foot)')
    if out.startswith('hero_'):
        rest_ends(J)
        notes.append('первый и последний кадр idle / win = поза покоя (одинаковые)')
    if out == 'winlines':
        notes.append('11 линий: line{n}_in (прорисовка 0.36 с) → line{n}_loop (1.2 с, цикл); n = номер линии из сида (1…11)')
        notes.append('сетка 5x3, клетка 197x200, (0,0) = центр сетки; клип-маска clip_desk / clip_mob по рамке')
        notes.append('несколько линий сразу — каждая на своём треке; в покое скелет пустой')
    if out.startswith('bonus_screen'):
        lighten_bonus_screen(J)
        notes.append('убраны фото клуба и столик: остались лучи, счётчик, героиня, лого и надписи')
        notes.append('скины fs_5 … fs_20 — число фриспинов на счётчике (skeleton.setSkinByName)')
    if out == 'background':
        # the top-right palm's sway dragged the houses next to it (product)
        J['animations']['idle']['bones'].pop('palm3', None)
        notes.append('убрано покачивание пальмы справа вверху (тянуло дома)')
        e = fix_photo_mesh_bind(J, 'bg')
        notes.append(f'меш фото: вершины поставлены по UV (было смещение до {e:.0f} px — волны на домах)')
    removed = []
    if out.startswith('bonus_screen'):
        atlas, removed = drop_atlas_regions(atlas, {'b_bg', 'b_left'})
        pages, _ = atlas_regions(atlas)
    for i, old in enumerate(pages):
        new = 'animation.png' if i == 0 else f'animation-p{i + 1}.png'
        atlas = re.sub(rf'^{re.escape(old)}$', new, atlas, flags=re.M)
        if old.endswith('.jpg') and out in PHOTO_OVERRIDE:
            im = _Image.open(PHOTO_OVERRIDE[out]).convert('RGB')
            w, h = (int(v) for v in re.search(rf'^{re.escape(new)}\nsize:(\d+),(\d+)', atlas, re.M).groups())
            if im.size != (w, h): im = im.resize((w, h), _Image.LANCZOS)
            im.save(os.path.join(dst, new), optimize=True)
            notes.append(f'фото заменено исправленным БГ дизайнера ({w}×{h})')
        elif old.endswith('.jpg'):
            # spec page names are .png — the opaque photo page converted losslessly
            _Image.open(os.path.join(src, old)).convert('RGB').save(os.path.join(dst, new), optimize=True)
            notes.append(f'{old} → {new} (JPG-страница фото переведена в PNG)')
        else:
            shutil.copy(os.path.join(src, old), os.path.join(dst, new))
            gaps = [r for r in removed if r[0] == old]
            if gaps:  # clear the dropped regions' pixels (smaller page)
                im = _Image.open(os.path.join(dst, new)).convert('RGBA')
                for _, x, y, w, h, rot in gaps:
                    im.paste((0, 0, 0, 0), (x, y, x + (h if rot else w), y + (w if rot else h)))
                im.save(os.path.join(dst, new), optimize=True)
    open(os.path.join(dst, 'animation.atlas'), 'w').write(atlas)
    json.dump(J, open(os.path.join(dst, 'animation.json'), 'w'), separators=(',', ':'))
    sk = J['skeleton']
    bounds = box or [sk['x'], sk['y'], sk['width'], sk['height']]
    if static_src != 'render':
        im = _Image.open(os.path.join(ROOT, 'img', 'gangsta-casino', static_src)).convert('RGBA')
        dx, dy = SCENE_STATIC_SHIFT.get(out, (0, 0))
        if dx or dy:
            moved = _Image.new('RGBA', im.size); moved.paste(im, (dx, dy)); im = moved
            notes.append(f'статика сдвинута на ({dx:+d}, {dy:+d}) px — совпадает с анимацией')
        im.save(os.path.join(dst, 'static.png'), optimize=True)
        w, h = _Image.open(os.path.join(dst, 'static.png')).size
        if (w, h) != (round(bounds[2]), round(bounds[3])):
            notes.append(f'static.png {w}×{h} = @{w / bounds[2]:.0f}x от размера в игре {bounds[2]:g}×{bounds[3]:g}')
    if out.startswith('bonus_screen'):
        notes.append('без скина цифры можно ставить и кодом: слоты dig1..dig3, вложения d0..d9')
    scene_report[out] = {'clips': {k: duration(v) for k, v in J['animations'].items()},
                         'pages': [('animation.png' if i == 0 else f'animation-p{i + 1}.png') for i in range(len(pages))],
                         'pma': pma, 'box': bounds, 'static': static_src, 'notes': notes, 'issues': []}
    print(out, scene_report[out]['clips'], notes)
# generated: bonus backgrounds (beams + the heroine's hand), desktop + portrait
import subprocess as _sp, sys as _sys
_sp.run([_sys.executable, os.path.join(os.path.dirname(__file__), 'gc_bonus_bg.py'), DST], check=True)
for out, box in (('bonus_bg', [-966, -470, 1932, 940]), ('bonus_bg_mob', [-400, -731.5, 800, 1463])):
    J = json.load(open(os.path.join(DST, out, 'animation.json')))
    scene_report[out] = {'clips': {k: duration(v) for k, v in J['animations'].items()}, 'pages': ['animation.png', 'animation-p2.png'],
                         'pma': False, 'box': box, 'static': 'render', 'issues': [],
                         'notes': ['лучи прожекторов (как в бонус-экране, лёгкие ключи)', 'рука героини с деньгами: idle покачивание, win активнее']}
# generated: popups (intro / idle / outro) from the PSB layers cut into
# assets_src/gangsta-casino-popups by scripts/gc_popups_extract.py
_sp.run([_sys.executable, os.path.join(os.path.dirname(__file__), 'gc_popups_spine.py'),
         os.path.join(os.path.dirname(__file__), '..', 'assets_src', 'gangsta-casino-popups'), DST], check=True)
POP = os.path.join(DST, 'popups')
all_marks = json.load(open(os.path.join(POP, 'text_marks.json')))
pages = sorted(x for x in os.listdir(POP) if x.startswith('animation') and x.endswith('.png'))
for slug in sorted(x[:-5] for x in os.listdir(POP) if x.endswith('.json') and x != 'text_marks.json'):
    J = json.load(open(os.path.join(POP, f'{slug}.json')))
    marks = all_marks.get(slug, {})
    scene_report[f'popup_{slug}'] = {'clips': {k: duration(v) for k, v in J['animations'].items()}, 'pages': pages,
                         'pma': False, 'box': [-966, -470, 1932, 940], 'static': 'render', 'issues': [], 'popup': True,
                         'folder': 'popups', 'skeleton': slug, 'marks': marks,
                         'notes': ['общий атлас всех попапов: popups/animation.atlas + страницы, скелет popups/' + slug + '.json',
                                   'intro → idle (цикл) → outro; последний кадр intro = первый и последний кадр idle = первый кадр outro',
                                   'сумма / число не запечены: рисует код в кости ' + ' / '.join(f'«{m}»' for m in marks) + ' (её масштаб 0→1 в intro, →0 в outro)']}

# generated: the multiplier (new art from Desk_Gangsta_Slot_F.psb) — reel symbol + UI plate
_sp.run([_sys.executable, os.path.join(os.path.dirname(__file__), 'gc_multiplier_spine.py'),
         os.path.join(os.path.dirname(__file__), '..', 'assets_src', 'gangsta-casino-multiplier'), DST], check=True)
J = json.load(open(os.path.join(DST, 'multiplier', 'animation.json')))
report['multiplier'] = {'clips': {k: duration(v) for k, v in J['animations'].items()}, 'pages': ['animation.png'], 'issues': [],
                        'spine': '4.1.24', 'unused': [],
                        'notes': ['landing 0.7 с: фишка приземляется, значение «переворачивается» внутрь; win 1.3 с',
                                  'значение = скин val_2 / val_3 / val_5 / val_7 / val_9 (в покое без скина — x3)']}
J = json.load(open(os.path.join(DST, 'multiplier_plate', 'animation.json')))
s0 = J['skeleton']
scene_report['multiplier_plate'] = {'clips': {k: duration(v) for k, v in J['animations'].items()}, 'pages': ['animation.png'],
    'pma': False, 'box': [s0['x'], s0['y'], s0['width'], s0['height']], 'static': 'ui/multiplier', 'issues': [],
    'marks': json.load(open(os.path.join(DST, 'multiplier_plate', 'text_marks.json'))),
    'notes': ['idle 4 с: плашка покачивается на цепях; update 0.6 с: значение «выпрыгивает» (новый итог)',
              'значение — ТЕКСТ (во фриспинах множители суммируются: x17, x33…): рисует код в кости «value», её масштаб пульсирует в update']}
report['_scene'] = scene_report
json.dump(report, open(os.path.join(DST, 'report.json'), 'w'), ensure_ascii=False, indent=1)

# static.png of the rendered entries (screens, frames) — needs the static
# server on :4199; without it run scripts/gc_spine_static.py by hand later
import subprocess, sys, urllib.request
try:
    urllib.request.urlopen('http://localhost:4199/spine-static-render.html', timeout=2)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'gc_spine_static.py')], check=True)
except Exception as err:
    print('static render skipped:', err)
