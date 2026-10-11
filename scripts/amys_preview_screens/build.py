# Builds the four Amy's Fruit Farm preview-screen Spine 4.1 exports
# (feature_screen_desk/mob, bonus_screen_desk/mob) from gfx/ bitmaps.
# Everything is authored in design pixels around the box centre (y up),
# setup pose = the resting layout; `intro` animates INTO setup, `idle` loops
# around it, so intro -> idle never jumps.
import os, json, math, random
import numpy as np
from PIL import Image

S = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(S, 'gfx')
OUT = '/Users/arturkasian/demo_slot/front/img/amys-fruit-farm/Screens'
FPS = 30

# --- easing ---------------------------------------------------------------------
def lin(t): return t
def out_quad(t): return 1 - (1 - t) ** 2
def in_quad(t): return t * t
def out_cubic(t): return 1 - (1 - t) ** 3
def in_out_sine(t): return -(math.cos(math.pi * t) - 1) / 2
def out_back(t, s=1.9): t -= 1; return t * t * ((s + 1) * t + s) + 1
def out_back_soft(t): return out_back(t, 1.2)
def out_elastic(t):
    if t in (0, 1): return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1

def r2(v): return round(v, 2)

class Anim:
    def __init__(self, dur):
        self.dur = dur; self.bones = {}; self.slots = {}

    def _sample(self, keys):
        """keys: [(t, value(s), ease)] -> dense [(t, values)] (linear segments kept sparse)."""
        out = []
        for i, (t, v, e) in enumerate(keys):
            v = v if isinstance(v, (tuple, list)) else (v,)
            if i == 0: out.append((t, v)); continue
            t0, v0 = out[-1]
            if e is not lin:
                n = max(2, int(round((t - t0) * FPS)))
                for k in range(1, n):
                    u = k / n; w = e(u)
                    out.append((t0 + (t - t0) * u, tuple(a + (b - a) * w for a, b in zip(v0, v))))
            out.append((t, v))
        return out

    def bone(self, b, prop, keys):
        if prop == 'scale':
            keys = [(t, v if isinstance(v, (tuple, list)) else (v, v), e) for t, v, e in keys]
        tl = self.bones.setdefault(b, {}).setdefault(prop, [])
        for t, v in self._sample(keys):
            k = {'time': r2(t)}
            if prop == 'rotate': k['value'] = r2(v[0])
            else: k['x'], k['y'] = r2(v[0]), r2(v[1] if len(v) > 1 else v[0])
            tl.append(k)

    def fn(self, b, prop, t0, t1, f):
        """Sample an arbitrary f(u in 0..1) -> value(s) at FPS."""
        n = max(2, int(round((t1 - t0) * FPS)))
        keys = [(t0 + (t1 - t0) * k / n, f(k / n), lin) for k in range(n + 1)]
        self.bone(b, prop, keys)

    def alpha(self, s, keys, rgb='ffffff'):
        tl = self.slots.setdefault(s, {}).setdefault('rgba', [])
        for t, v in self._sample(keys):
            tl.append({'time': r2(t), 'color': rgb + '%02x' % max(0, min(255, round(v[0] * 255)))})

    def attach(self, s, keys):
        tl = self.slots.setdefault(s, {}).setdefault('attachment', [])
        for t, name in keys: tl.append({'time': r2(t), 'name': name})

    def json(self):
        # make sure the clip is exactly `dur` long
        self.bones.setdefault('root', {})['rotate'] = [{'time': 0, 'value': 0}, {'time': r2(self.dur), 'value': 0}]
        out = {}
        if self.slots: out['slots'] = self.slots
        out['bones'] = self.bones
        return out

class Skel:
    def __init__(self, name, box):
        self.name, self.box = name, box
        self.bones = [{'name': 'root'}, {'name': 'main', 'parent': 'root'}]
        self.slots = []; self.skin = {}; self.images = {}; self.anims = {}

    def bone(self, name, parent='main', x=0, y=0, s=1, rot=0):
        b = {'name': name, 'parent': parent}
        if x: b['x'] = r2(x)
        if y: b['y'] = r2(y)
        sx, sy = (s, s) if not isinstance(s, tuple) else s
        if sx != 1: b['scaleX'] = round(sx, 4)
        if sy != 1: b['scaleY'] = round(sy, 4)
        if rot: b['rotation'] = r2(rot)
        self.bones.append(b); return name

    def size(self, img):
        return Image.open(os.path.join(G, img + '.png')).size

    def att(self, slot, img, x=0, y=0, scale=1, rot=0, tex=1.0):
        """Region attachment showing gfx/<img>.png at `scale`; `tex` < 1 stores it downsampled."""
        name = img
        w, h = self.size(img)
        self.images[name] = (img, tex)
        a = {'x': r2(x), 'y': r2(y), 'width': w, 'height': h}
        sx, sy = scale if isinstance(scale, tuple) else (scale, scale)
        if (sx, sy) != (1, 1): a['scaleX'], a['scaleY'] = round(sx, 4), round(sy, 4)
        if rot: a['rotation'] = rot
        self.skin.setdefault(slot, {})[name] = a
        return name

    def slot(self, name, bone, img=None, *, show=True, blend=None, alpha=1.0, rgb='ffffff', **kw):
        s = {'name': name, 'bone': bone}
        if alpha != 1 or rgb != 'ffffff': s['color'] = rgb + '%02x' % round(alpha * 255)
        if blend: s['blend'] = blend
        if img:
            an = self.att(name, img, **kw)
            if show: s['attachment'] = an
        self.slots.append(s); return name

    def anim(self, name, dur):
        a = Anim(dur); self.anims[name] = a; return a

    # -- export --------------------------------------------------------------------
    def export(self):
        d = os.path.join(OUT, self.name); os.makedirs(d, exist_ok=True)
        for f in os.listdir(d): os.remove(os.path.join(d, f))
        pages = pack(self.images, d)
        x, y, w, h = self.box
        data = {
            'skeleton': {'hash': self.name, 'spine': '4.1.24', 'x': x, 'y': y, 'width': w, 'height': h,
                         'fps': FPS, 'images': './gfx/', 'audio': ''},
            'bones': self.bones,
            'slots': self.slots,
            'skins': [{'name': 'default', 'attachments': self.skin}],
            'animations': {k: a.json() for k, a in self.anims.items()},
        }
        with open(os.path.join(d, 'animation.json'), 'w') as f: json.dump(data, f, separators=(',', ':'))
        print(self.name, 'pages', pages, 'json', os.path.getsize(os.path.join(d, 'animation.json')) // 1024, 'KB')

def premultiply(im):
    a = np.asarray(im.convert('RGBA')).astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0
    return Image.fromarray(a.round().astype(np.uint8))

def pack(images, d, max_w=2048, pad=2):
    """Opaque full-screen backgrounds go to their own JPEG page; everything else
    is shelf-packed into premultiplied PNG pages."""
    regs = []
    for name, (img, tex) in images.items():
        im = Image.open(os.path.join(G, img + '.png')).convert('RGBA')
        if tex != 1: im = im.resize((max(1, round(im.width * tex)), max(1, round(im.height * tex))), Image.LANCZOS)
        regs.append((name, img, im))
    lines, pages = [], []
    bgs = [r for r in regs if r[1].startswith('bg_')]
    rest = sorted([r for r in regs if not r[1].startswith('bg_')], key=lambda r: -r[2].height)
    for name, _, im in bgs:
        fn = 'animation_bg.jpg'
        im.convert('RGB').save(os.path.join(d, fn), quality=86, optimize=True, progressive=True)
        pages.append(fn)
        lines += [fn, f'size:{im.width},{im.height}', 'filter:Linear,Linear', 'pma:true', name,
                  f'bounds:0,0,{im.width},{im.height}', '']
    # shelf pack
    placed, x, y, shelf_h, W = [], pad, pad, 0, 0
    for name, _, im in rest:
        if x + im.width + pad > max_w: x, y, shelf_h = pad, y + shelf_h + pad, 0
        placed.append((name, im, x, y)); x += im.width + pad
        shelf_h = max(shelf_h, im.height); W = max(W, x)
    H = y + shelf_h + pad
    page = Image.new('RGBA', (W, H))
    for name, im, px, py in placed: page.paste(im, (px, py))
    fn = 'animation.png'
    premultiply(page).save(os.path.join(d, fn), optimize=True)
    pages.append(f'{fn} {W}x{H}')
    lines += [fn, f'size:{W},{H}', 'filter:Linear,Linear', 'pma:true']
    for name, im, px, py in placed: lines += [name, f'bounds:{px},{py},{im.width},{im.height}']
    with open(os.path.join(d, 'animation.atlas'), 'w') as f: f.write('\n'.join(lines) + '\n')
    return pages

# =================================================================================
# shared building blocks
# =================================================================================
def backdrop(sk, a, bg, overscan, shade=0.5):
    """bg (overscanned to cover any viewport aspect), black shade, vignette."""
    x, y, w, h = sk.box
    sk.bone('bg_b', s=overscan)
    sk.slot('bg', 'bg_b', bg)
    sk.bone('shade_b', s=(w * overscan / 8 * 1.05, h * overscan / 8 * 1.05))
    sk.slot('shade', 'shade_b', 'white', rgb='000000', alpha=shade)
    sk.bone('vig_b', s=(w * overscan / 256 * 1.02, h * overscan / 256 * 1.02))
    sk.slot('vignette', 'vig_b', 'vignette', alpha=0.85)
    # intro: shade from black, background settles from a slight zoom
    a.alpha('shade', [(0, 1, lin), (0.55, shade, out_quad)], rgb='000000')
    a.bone('bg_b', 'scale', [(0, 1.08, lin), (1.4, 1, out_cubic)])

def sparkles(sk, intro, idle, n, area, seed, rgb='ffe9a0', scale=(0.35, 0.8)):
    rnd = random.Random(seed)
    x0, y0, x1, y1 = area
    for i in range(n):
        b = sk.bone(f'spk{i}_b', x=rnd.uniform(x0, x1), y=rnd.uniform(y0, y1), s=rnd.uniform(*scale))
        s = sk.slot(f'spk{i}', b, 'sparkle', blend='additive', rgb=rgb, alpha=0)
        # each sparkle twinkles once per idle loop at its own phase
        t0 = rnd.uniform(0.05, idle.dur - 1.0); d = rnd.uniform(0.6, 0.9)
        idle.alpha(s, [(0, 0, lin), (t0, 0, lin), (t0 + d * 0.4, 1, out_quad), (t0 + d, 0, in_quad), (idle.dur, 0, lin)], rgb=rgb)
        idle.bone(b, 'scale', [(0, 0.3, lin), (t0, 0.3, lin), (t0 + d * 0.4, 1, out_quad), (t0 + d, 0.3, in_quad), (idle.dur, 0.3, lin)])
        idle.bone(b, 'rotate', [(0, 0, lin), (idle.dur, rnd.choice([-1, 1]) * 180, lin)])
        intro.alpha(s, [(0, 0, lin)], rgb=rgb)

def pop_in(a, bone, slots, t, dur=0.5, from_s=0.2, ease=out_back, dy=0):
    a.bone(bone, 'scale', [(0, from_s, lin), (t, from_s, lin), (t + dur, 1, ease)])
    if dy: a.bone(bone, 'translate', [(0, (0, dy), lin), (t, (0, dy), lin), (t + dur, (0, 0), out_cubic)])
    for s in slots:
        al = s[1] if isinstance(s, tuple) else 1
        nm = s[0] if isinstance(s, tuple) else s
        a.alpha(nm, [(0, 0, lin), (t, 0, lin), (t + dur * 0.45, al, out_quad)])

def flash(sk, a, name, bone, t, scale, rgb='fff2c0', peak=0.9, dur=0.55):
    """One-shot additive glow burst at `t` (hidden at rest)."""
    sk.slot(name, bone, 'glow', blend='additive', rgb=rgb, alpha=0, scale=scale)
    a.alpha(name, [(0, 0, lin), (t, 0, lin), (t + dur * 0.25, peak, out_quad), (t + dur, 0, in_quad)], rgb=rgb)

def fit(sk, img, max_w, max_h=10 ** 9):
    w, h = sk.size(img)
    return min(1, max_w / w, max_h / h)

# =================================================================================
# FEATURE SCREEN
# =================================================================================
FEATURES = [  # (key, icon, icon scale, title, desc)
    ('wild', 'icon_wild', 1.0, 't_wild', 'd_wild'),
    ('fs', 'icon_scatter', 1.0, 't_fs', 'd_fs'),
    ('buy', 'icon_buy', 0.7, 't_buy', 'd_buy'),
]

def feature_screen(mob):
    box = (-390, -708, 780, 1416) if mob else (-966, -470, 1932, 940)
    sk = Skel('feature_screen_' + ('mob' if mob else 'desk'), box)
    intro, idle = sk.anim('intro', 2.6), sk.anim('idle', 8.0)
    backdrop(sk, intro, 'bg_base_mob' if mob else 'bg_base_desk', 1.42 if mob else 1.32, shade=0.5)

    # --- Amy ---------------------------------------------------------------------
    ax, ascale = (-250, 0.6) if mob else (-690, 1.05)
    feet = box[1]
    sk.bone('amy_b', x=ax, y=feet, s=ascale)            # pivot at her feet
    sk.slot('amy_glow', 'amy_b', 'glow', blend='additive', rgb='ffd27a', alpha=0.35, y=420, scale=(3.2))
    sk.slot('amy', 'amy_b', 'amy_base', y=409)
    # Amy is static on purpose (product): no slide-in, no breathing.

    # --- logo ----------------------------------------------------------------------
    lx, ly, ls = (0, 585, 1.25) if mob else (180, 335, 1.12)
    sk.bone('logo_b', x=lx, y=ly, s=ls)
    sk.slot('logo_glow', 'logo_b', 'logo_glow', blend='additive', rgb='ffcf4a', alpha=0.45)
    sk.slot('logo', 'logo_b', 'logo')
    sk.slot('logo_shine', 'logo_b', 'logo_glow', blend='additive', rgb='fff6d0', alpha=0, scale=0.92)
    intro.bone('logo_b', 'translate', [(0, (0, 420), lin), (0.15, (0, 420), lin), (0.62, (0, 0), in_quad)])
    intro.bone('logo_b', 'scale', [(0, (1, 1), lin), (0.62, (1, 1), lin), (0.72, (1.12, 0.84), out_quad), (1.15, (1, 1), out_elastic)])
    intro.alpha('logo', [(0, 0, lin), (0.15, 0, lin), (0.35, 1, out_quad)])
    intro.alpha('logo_glow', [(0, 0, lin), (0.62, 0, lin), (0.75, 1, out_quad), (1.4, 0.45, in_out_sine)], rgb='ffcf4a')
    flash(sk, intro, 'logo_flash', 'logo_b', 0.62, (3.6, 1.6), peak=0.8)
    idle.bone('logo_b', 'scale', [(0, 1, lin), (2, 1.025, in_out_sine), (4, 1, in_out_sine), (6, 1.025, in_out_sine), (8, 1, in_out_sine)])
    idle.alpha('logo_glow', [(0, 0.45, lin), (2, 0.8, in_out_sine), (4, 0.45, in_out_sine), (6, 0.8, in_out_sine), (8, 0.45, in_out_sine)], rgb='ffcf4a')
    idle.alpha('logo_shine', [(0, 0, lin), (3.2, 0, lin), (3.5, 0.55, out_quad), (4.1, 0, in_quad), (8, 0, lin)], rgb='fff6d0')

    # --- feature cards ---------------------------------------------------------------
    if mob:
        rows = [340, 95, -150]
        cards = [dict(ix=-250, iy=ry, px=95, py=ry + 58, dx=95, dy=ry - 42, isc=0.85, psc=0.64, dw=440) for ry in rows]
    else:
        cards = [dict(ix=cx, iy=105, px=cx, py=-75, dx=cx, dy=-192, isc=1.0, psc=0.7, dw=400) for cx in (-240, 180, 600)]
    for i, ((key, icon, icon_s, title, desc), c) in enumerate(zip(FEATURES, cards)):
        t = 0.75 + i * 0.17
        cb = sk.bone(f'card_{key}', x=c['ix'], y=c['iy'])
        # rays + glow behind the icon
        rb = sk.bone(f'rays_{key}_b', cb, s=0.36 * c['isc'])
        sk.slot(f'rays_{key}', rb, 'rays1', blend='additive', rgb='ffd060', alpha=0.75, tex=0.5)
        sk.slot(f'rglow_{key}', cb, 'rays2', blend='additive', rgb='ffb830', alpha=0.5, scale=0.42 * c['isc'], tex=0.5)
        ib = sk.bone(f'icon_{key}_b', cb, s=icon_s * c['isc'])
        sk.slot(f'icon_{key}', ib, icon)
        flash(sk, intro, f'iflash_{key}', ib, t + 0.18, 1.5)
        pop_in(intro, ib, [f'icon_{key}'], t, 0.55)
        pop_in(intro, rb, [(f'rays_{key}', 0.75)], t + 0.1, 0.6, from_s=0.1, ease=out_cubic)
        intro.alpha(f'rays_{key}', [(0, 0, lin), (t + 0.1, 0, lin), (t + 0.5, 0.75, out_quad)], rgb='ffd060')
        intro.alpha(f'rglow_{key}', [(0, 0, lin), (t + 0.1, 0, lin), (t + 0.5, 0.5, out_quad)], rgb='ffb830')
        # plaque + title
        pb = sk.bone(f'plaque_{key}_b', x=c['px'], y=c['py'])
        sk.slot(f'plaque_{key}', pb, 'plaque', scale=c['psc'])
        sk.slot(f'title_{key}', pb, title, y=4, scale=fit(sk, title, 588 * c['psc'] * 0.84, 153 * c['psc'] * 0.62))
        pop_in(intro, pb, [f'plaque_{key}', f'title_{key}'], t + 0.18, 0.45, from_s=0.5, ease=out_back_soft)
        # description
        dimg = f'{desc}_{"mob" if mob else "desk"}'
        db = sk.bone(f'desc_{key}_b', x=c['dx'], y=c['dy'])
        sk.slot(f'desc_{key}', db, dimg, scale=fit(sk, dimg, c['dw']))
        intro.bone(db, 'translate', [(0, (0, -30), lin), (t + 0.32, (0, -30), lin), (t + 0.72, (0, 0), out_cubic)])
        intro.alpha(f'desc_{key}', [(0, 0, lin), (t + 0.32, 0, lin), (t + 0.72, 1, out_quad)])
        # idle: rays spin, icon bobs + pulses (phase-shifted per card), glow breathes
        dirn = -1 if i % 2 == 0 else 1
        idle.bone(rb, 'rotate', [(0, 0, lin), (8, dirn * 360, lin)])
        ph = i * 0.66
        idle.fn(ib, 'translate', 0, 8, lambda u, ph=ph: (0, 7 * math.sin(2 * math.pi * (u * 4 + ph / 2))))
        idle.fn(ib, 'scale', 0, 8, lambda u, ph=ph: 1 + 0.035 * max(0, math.sin(2 * math.pi * (u * 2 - ph / 2))) ** 3)
        idle.alpha(f'rglow_{key}', [(0, 0.5, lin), (2, 0.25, in_out_sine), (4, 0.5, in_out_sine), (6, 0.25, in_out_sine), (8, 0.5, in_out_sine)], rgb='ffb830')

    # --- continue prompt ---------------------------------------------------------------
    cx, cy, cimg, csc = (130, -470, 'cont_mob', 0.82) if mob else (180, -392, 'cont_desk', 0.9)
    sk.bone('cont_b', x=cx, y=cy, s=csc)
    sk.slot('cont_glow', 'cont_b', 'glow', blend='additive', rgb='ffcf4a', alpha=0.3, scale=(2.6, 0.8 if not mob else 1.2))
    sk.slot('cont', 'cont_b', cimg)
    intro.alpha('cont', [(0, 0, lin), (1.75, 0, lin), (2.2, 1, out_quad)])
    intro.alpha('cont_glow', [(0, 0, lin), (1.75, 0, lin), (2.2, 0.3, out_quad)], rgb='ffcf4a')
    intro.bone('cont_b', 'translate', [(0, (0, -25), lin), (1.75, (0, -25), lin), (2.2, (0, 0), out_cubic)])
    idle.alpha('cont', [(0, 1, lin)] + [(k * 2 + t, v, in_out_sine) for k in range(4) for (t, v) in ((1, 0.5), (2, 1))])
    idle.bone('cont_b', 'scale', [(0, 1, lin)] + [(k * 2 + t, v, in_out_sine) for k in range(4) for (t, v) in ((1, 0.97), (2, 1))])
    idle.alpha('cont_glow', [(0, 0.3, lin)] + [(k * 2 + t, v, in_out_sine) for k in range(4) for (t, v) in ((1, 0.08), (2, 0.3))], rgb='ffcf4a')

    x, y, w, h = box
    sparkles(sk, intro, idle, 16 if mob else 22, (x + 30, y + 120, x + w - 30, y + h - 40), seed=7 if mob else 3)
    sk.export()

# =================================================================================
# BONUS SCREEN
# =================================================================================
DIGIT_KERN = -0.16  # glyph images carry a thick stroke; overlap them a bit

def digit_layout(sk, digits, scale):
    ws = [sk.size('n' + d)[0] * scale for d in digits]
    step = [w * (1 + DIGIT_KERN) for w in ws]
    total = sum(step) - ws[-1] * DIGIT_KERN
    xs, x = [], -total / 2
    for w, s in zip(ws, step): xs.append(x + w / 2); x += s
    return xs

def bonus_screen(mob):
    box = (-390, -708, 780, 1416) if mob else (-966, -470, 1932, 940)
    sk = Skel('bonus_screen_' + ('mob' if mob else 'desk'), box)
    intro, idle = sk.anim('intro', 2.8), sk.anim('idle', 8.0)
    backdrop(sk, intro, 'bg_bonus_mob' if mob else 'bg_bonus_desk', 1.42 if mob else 1.32, shade=0.45)

    # --- Amy -----------------------------------------------------------------------
    ax, ascale = (-205, 0.72) if mob else (-660, 1.12)
    sk.bone('amy_b', x=ax, y=box[1], s=ascale)
    sk.slot('amy_glow', 'amy_b', 'glow', blend='additive', rgb='ffcf7a', alpha=0.35, y=360, scale=3.4)
    sk.slot('amy', 'amy_b', 'amy_bonus', y=353)
    # Amy is static on purpose (product): no slide-in, no breathing.

    # --- centre column: rays, honey frame, count -------------------------------------
    fx, fy, fs = (0, 315, 1.15) if mob else (200, 60, 1.0)
    sk.bone('frame_root', x=fx, y=fy, s=fs)
    sk.bone('rays_b', 'frame_root', y=-5, s=0.95)
    sk.slot('rays_glow', 'rays_b', 'rays2', blend='additive', rgb='ffb028', alpha=0.7, scale=0.95, tex=0.5)
    sk.slot('rays', 'rays_b', 'rays1', blend='additive', rgb='ffd25a', alpha=0.8, tex=0.5)
    sk.bone('rays2_b', 'frame_root', y=-5, s=0.75, rot=30)
    sk.slot('rays_b2', 'rays2_b', 'rays1', blend='additive', rgb='fff0b0', alpha=0.45, tex=0.5)
    sk.bone('frame_b', 'frame_root')
    sk.slot('frame', 'frame_b', 'honey_frame')
    sk.slot('t_youwon', 'frame_b', 't_youwon', y=171, scale=fit(sk, 't_youwon', 300, 52))
    sk.slot('t_freespins', 'frame_b', 't_freespins', y=-160, scale=fit(sk, 't_freespins', 300, 52))
    # count: up to three digit slots; runtime swaps attachments + x (see slot.js)
    sk.bone('number', 'frame_b', y=-6)
    dsc = 0.78
    setup = '10'
    xs = digit_layout(sk, setup, dsc)
    for k in range(3):
        b = sk.bone(f'num{k + 1}', 'number', x=xs[k] if k < len(setup) else 0)
        s = sk.slot(f'n{k + 1}', b, None)
        for d in '0123456789': sk.att(s, 'n' + d, scale=dsc)
        if k < len(setup): sk.slots[-1]['attachment'] = 'n' + setup[k]
    sk.slot('orb_flash', 'number', 'glow', blend='additive', rgb='ffe28a', alpha=0, scale=1.25)

    intro.bone('frame_b', 'scale', [(0, 0, lin), (0.25, 0, lin), (0.8, 1, out_back)])
    intro.bone('frame_b', 'rotate', [(0, -12, lin), (0.25, -12, lin), (0.9, 0, out_back_soft)])
    for s in ('frame', 't_youwon', 't_freespins'):
        intro.alpha(s, [(0, 0, lin), (0.25, 0, lin), (0.45, 1, out_quad)])
    intro.bone('rays_b', 'scale', [(0, 0, lin), (0.35, 0, lin), (1.0, 1, out_cubic)])
    intro.bone('rays_b', 'rotate', [(0, -60, lin), (0.35, -60, lin), (1.6, 0, out_cubic)])
    intro.bone('rays2_b', 'scale', [(0, 0, lin), (0.45, 0, lin), (1.1, 1, out_cubic)])
    intro.bone('rays2_b', 'rotate', [(0, 60, lin), (0.45, 60, lin), (1.7, 0, out_cubic)])
    # the count slams in after the frame lands
    intro.bone('number', 'scale', [(0, 0, lin), (0.8, 0, lin), (0.81, 2.4, lin), (1.12, 1, out_back)])
    for k in range(3): intro.alpha(f'n{k + 1}', [(0, 0, lin), (0.8, 0, lin), (0.95, 1, out_quad)])
    intro.alpha('orb_flash', [(0, 0, lin), (1.0, 0, lin), (1.08, 1, out_quad), (1.6, 0, in_quad)], rgb='ffe28a')
    flash(sk, intro, 'frame_flash', 'frame_b', 0.72, 3.2, peak=0.7, dur=0.7)

    idle.bone('rays_b', 'rotate', [(0, 0, lin), (8, -360, lin)])
    idle.bone('rays2_b', 'rotate', [(0, 0, lin), (8, 360, lin)])
    idle.alpha('rays_glow', [(0, 0.7, lin), (2, 0.45, in_out_sine), (4, 0.7, in_out_sine), (6, 0.45, in_out_sine), (8, 0.7, in_out_sine)], rgb='ffb028')
    idle.bone('frame_b', 'scale', [(0, 1, lin), (2, 1.018, in_out_sine), (4, 1, in_out_sine), (6, 1.018, in_out_sine), (8, 1, in_out_sine)])
    idle.bone('number', 'scale', [(0, 1, lin), (1.6, 1, lin), (1.8, 1.09, out_quad), (2.15, 1, in_out_sine), (5.6, 1, lin), (5.8, 1.09, out_quad), (6.15, 1, in_out_sine), (8, 1, lin)])
    idle.alpha('orb_flash', [(0, 0, lin), (1.6, 0, lin), (1.8, 0.45, out_quad), (2.4, 0, in_quad), (5.6, 0, lin), (5.8, 0.45, out_quad), (6.4, 0, in_quad), (8, 0, lin)], rgb='ffe28a')

    # --- title ---------------------------------------------------------------------
    tx, ty, tsc = (0, 642, 0.84) if mob else (200, 368, 0.8)
    sk.bone('title_b', x=tx, y=ty, s=tsc)
    sk.slot('title_glow', 'title_b', 'glow', blend='additive', rgb='ffcf4a', alpha=0.35, scale=(4.2, 1.1))
    sk.slot('title', 'title_b', 't_congrats')
    intro.bone('title_b', 'scale', [(0, 3.0, lin), (0.5, 3.0, lin), (0.78, 1, in_quad), (0.86, (1.08, 0.92), out_quad), (1.1, 1, out_back_soft)])
    intro.alpha('title', [(0, 0, lin), (0.5, 0, lin), (0.7, 1, out_quad)])
    intro.alpha('title_glow', [(0, 0, lin), (0.78, 0, lin), (0.9, 0.9, out_quad), (1.5, 0.35, in_out_sine)], rgb='ffcf4a')
    idle.bone('title_b', 'scale', [(0, 1, lin), (2, 1.03, in_out_sine), (4, 1, in_out_sine), (6, 1.03, in_out_sine), (8, 1, in_out_sine)])
    idle.alpha('title_glow', [(0, 0.35, lin), (2, 0.7, in_out_sine), (4, 0.35, in_out_sine), (6, 0.7, in_out_sine), (8, 0.35, in_out_sine)], rgb='ffcf4a')

    # --- info plaques -----------------------------------------------------------------
    if mob:
        pl = [('wild', 'icon_wild', 'b_wild', 60, -15), ('fs', 'icon_scatter', 'b_fs', 60, -135)]
        psc = 0.84
    else:
        pl = [('wild', 'icon_wild', 'b_wild', -15, -268), ('fs', 'icon_scatter', 'b_fs', 445, -268)]
        psc = 0.72
    for i, (key, icon, txt, px, py) in enumerate(pl):
        t = 1.3 + i * 0.15
        pb = sk.bone(f'pl_{key}', x=px, y=py)
        pw = 588 * psc
        sk.slot(f'plq_{key}', pb, 'plaque', scale=psc)
        sk.slot(f'plt_{key}', pb, txt, x=pw * 0.08, y=2, scale=fit(sk, txt, pw * 0.72, 153 * psc * 0.5))
        ib = sk.bone(f'pli_{key}', pb, x=-pw / 2 + 18, y=4, s=0.62 * psc / 0.72)
        sk.slot(f'pli_{key}', ib, icon)
        pop_in(intro, pb, [f'plq_{key}', f'plt_{key}'], t, 0.45, from_s=0.4, ease=out_back_soft, dy=-40)
        pop_in(intro, ib, [f'pli_{key}'], t + 0.2, 0.5, from_s=0, ease=out_back)
        ph = i * 0.5
        idle.fn(ib, 'rotate', 0, 8, lambda u, ph=ph: 6 * math.sin(2 * math.pi * (u * 2 + ph)))
        idle.fn(ib, 'scale', 0, 8, lambda u, ph=ph: 1 + 0.06 * max(0, math.sin(2 * math.pi * (u * 2 - ph))) ** 4)

    # --- start prompt ---------------------------------------------------------------
    cx, cy, cimg, csc = (175, -470, 'start_mob', 0.82) if mob else (200, -400, 'start_desk', 0.9)
    sk.bone('cont_b', x=cx, y=cy, s=csc)
    sk.slot('cont_glow', 'cont_b', 'glow', blend='additive', rgb='ffcf4a', alpha=0.3, scale=(2.4, 0.8 if not mob else 1.2))
    sk.slot('cont', 'cont_b', cimg)
    intro.alpha('cont', [(0, 0, lin), (1.9, 0, lin), (2.35, 1, out_quad)])
    intro.alpha('cont_glow', [(0, 0, lin), (1.9, 0, lin), (2.35, 0.3, out_quad)], rgb='ffcf4a')
    intro.bone('cont_b', 'translate', [(0, (0, -25), lin), (1.9, (0, -25), lin), (2.35, (0, 0), out_cubic)])
    idle.alpha('cont', [(0, 1, lin)] + [(k * 2 + t, v, in_out_sine) for k in range(4) for (t, v) in ((1, 0.5), (2, 1))])
    idle.bone('cont_b', 'scale', [(0, 1, lin)] + [(k * 2 + t, v, in_out_sine) for k in range(4) for (t, v) in ((1, 0.97), (2, 1))])
    idle.alpha('cont_glow', [(0, 0.3, lin)] + [(k * 2 + t, v, in_out_sine) for k in range(4) for (t, v) in ((1, 0.08), (2, 0.3))], rgb='ffcf4a')

    # --- coin burst out of the frame (intro) + a slow coin rain (idle) ------------------
    rnd = random.Random(11 if mob else 5)
    ncoins = 14 if mob else 18
    for i in range(ncoins):
        b = sk.bone(f'coin{i}_b', 'frame_root', s=rnd.uniform(0.75, 1.15))
        s = sk.slot(f'coin{i}', b, f'coin{i % 8 + 1}', alpha=0)
        ang = rnd.uniform(15, 165) * math.pi / 180
        v = rnd.uniform(700, 1150) * (0.85 if mob else 1)
        vx, vy = math.cos(ang) * v * (0.8 if mob else 1.25), math.sin(ang) * v
        g = 2200; t0 = 0.82 + rnd.uniform(0, 0.12); d = rnd.uniform(1.1, 1.5); spin = rnd.uniform(-540, 540)
        intro.fn(b, 'translate', t0, t0 + d, lambda u, vx=vx, vy=vy, d=d: (vx * u * d, vy * u * d - g * (u * d) ** 2 / 2))
        intro.bone(b, 'rotate', [(0, 0, lin), (t0, 0, lin), (t0 + d, spin, lin)])
        intro.alpha(s, [(0, 0, lin), (t0, 0, lin), (t0 + 0.05, 1, lin), (t0 + d * 0.7, 1, lin), (t0 + d, 0, in_quad)])
    x, y, w, h = box
    for i in range(7 if mob else 9):
        b = sk.bone(f'rain{i}_b', x=rnd.uniform(x + 40, x + w - 40), y=y + h + 60, s=rnd.uniform(0.6, 0.95))
        s = sk.slot(f'rain{i}', b, f'coin{i % 8 + 1}', alpha=0)
        t0 = rnd.uniform(0, 8 - 3.2); d = rnd.uniform(2.6, 3.2); drift = rnd.uniform(-80, 80); spin = rnd.uniform(-360, 360)
        idle.bone(b, 'translate', [(0, (0, 0), lin), (t0, (0, 0), lin), (t0 + d, (drift, -(h + 120)), in_quad), (8, (0, 0), lin)])
        idle.bone(b, 'rotate', [(0, 0, lin), (t0, 0, lin), (t0 + d, spin, lin), (8, 0, lin)])
        idle.alpha(s, [(0, 0, lin), (t0, 0, lin), (t0 + 0.01, 0.9, lin), (t0 + d, 0.9, lin), (t0 + d + 0.01, 0, lin), (8, 0, lin)])

    sparkles(sk, intro, idle, 14 if mob else 20, (x + 30, y + 100, x + w - 30, y + h - 30), seed=21 if mob else 13)
    sk.export()

if __name__ == '__main__':
    for mob in (False, True):
        feature_screen(mob)
        bonus_screen(mob)
