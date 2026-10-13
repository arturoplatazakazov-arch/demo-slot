"""Spine 4.1 symbol animations for "tesla-spins", authored in code.

Builds on scripts/spine_screen_kit.py (Skel: sampled property curves, PMA atlas
packing). Output per symbol: front/img/tesla-spins/spine/<code>/animation.*
with the slot contract slot.js expects (same as gold-of-baku's artist exports):

- slot `item`   — the symbol PNG at its own pixel size, centred on the origin.
                  slot.js fits the skeleton by THIS slot's box, so the skeleton
                  lines up with the static <img> to the pixel.
- clip `win`    — 1.9s, starts and ends exactly in the setup pose (= the static
                  tile), so swapping <img> <-> skeleton is seamless.
- clip `idle`   — coin only: a looping crackle (the coin never moves).

Plus one FX-only skeleton, `zap` (clip `hit`, 1s): the strike played over a
cell when a Hold & Win coin lands — bolt from above, flash, shockwaves, sparks.

Every electric arc is a procedural midpoint-displacement bolt drawn with PIL —
four random variants per arc slot, flipped through by an attachment timeline so
the arcs flicker like real discharge instead of sliding.

Usage: .venv/bin/python scripts/tesla_spins_spine.py
"""

import math
import os
import random
import sys
import zlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from spine_screen_kit import (  # noqa: E402
    FPS, Skel, clamp, flash_of, out_back, out_cubic, rays, seg, soft_glow, spark,
)

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'tesla-spins')
SYM_DIR = os.path.join(ROOT, 'symbols')
OUT = os.path.join(ROOT, 'spine')

CODES = ['lemon', 'cherry', 'plum', 'watermelon', 'bell', 'star', 'gold', 'seven', 'coin']

# Tint of the halo per symbol: everything crackles blue-white (the theme), the
# warm metals get a copper halo so they don't turn into the wild.
HALO = {
    'lemon': (255, 220, 90), 'cherry': (255, 90, 90), 'plum': (190, 110, 255),
    'watermelon': (120, 255, 140), 'bell': (255, 170, 80), 'star': (110, 170, 255),
    'gold': (255, 200, 90), 'seven': (255, 80, 60), 'coin': (90, 170, 255),
}

WIN_DUR = 1.9
IDLE_DUR = 2.0


# --------------------------------------------------------------------------
# procedural lightning

def bolt_points(p0, p1, rough, depth, rng):
    pts = [p0, p1]
    disp = rough
    for _ in range(depth):
        nxt = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1
            off = rng.uniform(-disp, disp)
            nxt += [(mx - dy / ln * off, my + dx / ln * off), b]
        pts = nxt
        disp *= 0.55
    return pts


def draw_bolt(size, segments, core=(235, 245, 255), glow=(80, 150, 255), width=3, branches=True, seed=0):
    """`segments`: list of (p0, p1) in pixel coords of an image `size`."""
    rng = random.Random(seed)
    w, h = size
    S = 2  # supersample
    glow_l = Image.new('L', (w * S, h * S))
    core_l = Image.new('L', (w * S, h * S))
    dg, dc = ImageDraw.Draw(glow_l), ImageDraw.Draw(core_l)
    for p0, p1 in segments:
        ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        pts = bolt_points(p0, p1, ln * 0.22, 6, rng)
        sp = [(x * S, y * S) for x, y in pts]
        dg.line(sp, fill=255, width=int(width * 4 * S), joint='curve')
        dc.line(sp, fill=255, width=int(width * S), joint='curve')
        if branches:
            for _ in range(rng.randint(1, 3)):
                i = rng.randrange(2, len(pts) - 2)
                a = pts[i]
                ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0]) + rng.uniform(-1.1, 1.1)
                L = ln * rng.uniform(0.15, 0.35)
                b = (a[0] + math.cos(ang) * L, a[1] + math.sin(ang) * L)
                bp = [(x * S, y * S) for x, y in bolt_points(a, b, L * 0.25, 4, rng)]
                dg.line(bp, fill=150, width=int(width * 2.2 * S))
                dc.line(bp, fill=200, width=max(1, int(width * 0.55 * S)))
    glow_l = glow_l.filter(ImageFilter.GaussianBlur(width * 2.2 * S))
    core_l = core_l.filter(ImageFilter.GaussianBlur(0.6 * S))
    im = Image.new('RGBA', (w * S, h * S), glow + (0,))
    im.putalpha(glow_l.point(lambda v: int(v * 0.85)))
    c = Image.new('RGBA', (w * S, h * S), core + (0,))
    c.putalpha(core_l)
    im = Image.alpha_composite(im, c)
    return im.resize((w, h), Image.LANCZOS)


def halo_of(sym, col, blur):
    pad = blur * 3
    a = sym.getchannel('A')
    big = Image.new('L', (sym.width + 2 * pad, sym.height + 2 * pad))
    big.paste(a, (pad, pad))
    big = big.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(blur))
    im = Image.new('RGBA', big.size, col + (0,))
    im.putalpha(big)
    return im


# --------------------------------------------------------------------------
# Skel with named clips + attachment-swap timelines

class SymSkel(Skel):
    def __init__(self, name, w, h, out_dir, clips):
        super().__init__(name, w, h, 1.0, out_dir)
        self.clips = clips  # name -> duration
        self.anims = {c: {'bones': {}, 'slots': {}} for c in clips}

    def anim(self, which, target, prop, fn):
        # reuse the kit's sampler/thinner with this clip's own duration
        saved_intro, saved_anims = self.intro, self.anims
        self.intro = self.clips[which]
        self.anims = {'intro': saved_anims[which]}
        try:
            Skel.anim(self, 'intro', target, prop, fn)
        finally:
            self.intro, self.anims = saved_intro, saved_anims

    def variants(self, slot_name, bone, regions, w, h, x=0, y=0, rot=0, blend='additive'):
        """One slot, several region attachments of the same size (flicker frames)."""
        self.slot(slot_name, bone, regions[0], w=w, h=h, x=x, y=y, rot=rot, blend=blend)
        for r in regions[1:]:
            att = dict(self.atts[slot_name][regions[0]])
            self.atts[slot_name][r] = att
            pw, ph = self.need.get(r, (0, 0))
            self.need[r] = (max(pw, w), max(ph, h))

    def hide_in_setup(self, slot_name):
        for s in self.slots:
            if s['name'] == slot_name:
                s.pop('attachment', None)

    def flicker(self, which, slot_name, regions, on_fn, step=2, seed=0):
        """Attachment timeline: every `step` frames a random variant, or none
        while on_fn(t) is False."""
        rng = random.Random(seed)
        dur = self.clips[which]
        rows, last = [], 'x'
        n = int(round(dur * FPS))
        for k in range(0, n + 1, step):
            t = k / FPS
            name = rng.choice(regions) if on_fn(t) else None
            if name != last:
                r = {'name': name}
                if t:
                    r['time'] = round(t, 4)
                rows.append(r)
                last = name
        if last is not None:
            rows.append({'time': round(dur, 4), 'name': None})
        self.anims[which]['slots'].setdefault(slot_name, {})['attachment'] = rows


# --------------------------------------------------------------------------

# ---- art for the win clip ----------------------------------------------------

def tinted(im, col, k=1.0):
    out = Image.new('RGBA', im.size, col + (0,))
    out.putalpha(im.getchannel('A').point(lambda v: int(v * k)))
    return out


def xray_of(sym):
    """Electrocution frame: the symbol as a cyan negative with a white rim —
    the cartoon 'zapped' look, flashed for single frames."""
    rgb = sym.convert('RGB')
    lum = rgb.convert('L')
    inv = lum.point(lambda v: 255 - v)
    r = inv.point(lambda v: int(v * 0.35))
    g = inv.point(lambda v: int(70 + v * 0.7))
    b = inv.point(lambda v: 255)
    out = Image.merge('RGBA', (r, g, b, sym.getchannel('A')))
    a = sym.getchannel('A')
    rim = ImageChopsSub(a.filter(ImageFilter.MaxFilter(5)), a.filter(ImageFilter.MinFilter(5)))
    rim_im = Image.new('RGBA', sym.size, (235, 250, 255, 0))
    rim_im.putalpha(rim)
    return Image.alpha_composite(out, rim_im)


def ImageChopsSub(a, b):
    return ImageChops.subtract(a, b)


def edge_glow(sym, pad=24):
    a = sym.getchannel('A')
    big = Image.new('L', (sym.width + 2 * pad, sym.height + 2 * pad))
    big.paste(a, (pad, pad))
    edge = ImageChopsSub(big.filter(ImageFilter.MaxFilter(7)), big.filter(ImageFilter.MinFilter(3)))
    edge = edge.filter(ImageFilter.GaussianBlur(3)).point(lambda v: min(255, v * 2))
    im = Image.new('RGBA', big.size, (170, 220, 255, 0))
    im.putalpha(edge)
    return im


def ring_img(size=512, width=0.06):
    S = size * 2
    m = Image.new('L', (S, S))
    d = ImageDraw.Draw(m)
    w = int(S * width)
    d.ellipse((w, w, S - w, S - w), outline=255, width=w)
    m = m.filter(ImageFilter.GaussianBlur(S * 0.012)).resize((size, size), Image.LANCZOS)
    im = Image.new('RGBA', (size, size), (150, 205, 255, 0))
    im.putalpha(m)
    return im


def dot_img(size=48):
    g = Image.radial_gradient('L').resize((size, size))
    a = g.point(lambda v: int(255 * clamp(1 - v / 128) ** 1.8))
    im = Image.new('RGBA', (size, size), (225, 240, 255, 0))
    im.putalpha(a)
    return im


def contour_profile(sym, n=180):
    """r(theta) of the symbol silhouette around its centre (star-shaped approx)."""
    a = sym.getchannel('A').load()
    w, h = sym.size
    cx, cy = w / 2, h / 2
    prof = []
    for i in range(n):
        th = 2 * math.pi * i / n
        r_hit = 0
        r = 0
        while r < max(w, h):
            x, y = int(cx + math.cos(th) * r), int(cy + math.sin(th) * r)
            if not (0 <= x < w and 0 <= y < h):
                break
            if a[x, y] > 128:
                r_hit = r
            r += 2
        prof.append(r_hit)
    return prof


def contour_arc(sym, prof, th0, span, seed, pad=40):
    """A bolt crawling along the silhouette edge from th0 over `span` radians."""
    rng = random.Random(seed)
    w, h = sym.size
    size = (w + 2 * pad, h + 2 * pad)
    cx, cy = size[0] / 2, size[1] / 2
    n = len(prof)
    pts = []
    steps = 14
    for k in range(steps + 1):
        th = th0 + span * k / steps
        r = prof[int((th % (2 * math.pi)) / (2 * math.pi) * n) % n] + rng.uniform(-3, 9)
        pts.append((cx + math.cos(th) * r, cy + math.sin(th) * r))
    segs = list(zip(pts, pts[1:]))
    return draw_bolt(size, segs, width=2.6, branches=rng.random() < 0.6, seed=seed)


def strike_img(w, h, seed):
    """Vertical bolt from far above down into the symbol's centre."""
    size = (int(w), int(h))
    return draw_bolt(size, [((size[0] / 2 + random.Random(seed).uniform(-20, 20), 0),
                             (size[0] / 2, size[1] - 6))], width=5, seed=seed)


HIGH = {'bell', 'star', 'gold', 'seven', 'coin'}


def build_symbol(code):
    sym = Image.open(os.path.join(SYM_DIR, f'{code}.png')).convert('RGBA')
    W, H = sym.size
    R = max(W, H) / 2
    high = code in HIGH
    D = WIN_DUR
    clips = {'win': D}
    if code == 'coin':
        clips['idle'] = IDLE_DUR
    sk = SymSkel(code, W * 1.6, H * 1.6, OUT, clips)
    col = HALO[code]

    sk.image('item', sym)
    sk.image('xray', xray_of(sym))
    sk.image('flash', flash_of(sym, 1.0))
    sk.image('edge', edge_glow(sym))
    sk.image('halo', halo_of(sym, col, 18))
    sk.image('rays', rays(512, n=14, col=(150, 205, 255)))
    sk.image('ring', ring_img())
    sk.image('dot', dot_img())
    sk.image('spark', spark(64, 12))
    strikes = []
    for v in range(3):
        sk.image(f'strike{v}', strike_img(W * 0.7, H * 2.0, 900 + v))
        strikes.append(f'strike{v}')
    prof = contour_profile(sym)
    arcs = []
    for a in range(2):
        frames = []
        for v in range(5):
            seed = zlib.crc32(f'{code}/c{a}/{v}'.encode()) & 0xffff
            rng = random.Random(seed)
            reg = f'carc{a}_{v}'
            sk.image(reg, contour_arc(sym, prof, rng.uniform(0, 2 * math.pi), rng.uniform(1.4, 2.6), seed))
            frames.append(reg)
        arcs.append(frames)

    # --- rig (draw order bottom -> top)
    sk.bone('rays_b')
    sk.bone('ring1')
    sk.bone('ring2')
    sk.bone('body')
    sk.bone('fx')
    sk.slot('rays', 'rays_b', 'rays', w=R * 3.4, blend='additive')
    sk.slot('halo', 'fx', 'halo', w=sk.images['halo'].width, blend='additive')
    sk.slot('ring1', 'ring1', 'ring', w=R * 2.4, blend='additive')
    sk.slot('ring2', 'ring2', 'ring', w=R * 2.4, blend='additive')
    sk.slot('item', 'body', 'item', w=W)
    sk.slot('xray', 'body', 'xray', w=W)
    sk.hide_in_setup('xray')
    sk.slot('edge', 'body', 'edge', w=sk.images['edge'].width, blend='additive')
    sk.slot('flash', 'body', 'flash', w=W, blend='additive')
    sk.variants('strike', 'fx', strikes, w=W * 0.7, h=H * 2.0, y=H * 1.0)
    sk.hide_in_setup('strike')
    for a, frames in enumerate(arcs):
        im0 = sk.images[frames[0]]
        sk.variants(f'carc{a}', 'body', frames, w=im0.width, h=im0.height)
        sk.hide_in_setup(f'carc{a}')

    rng = random.Random(zlib.crc32(code.encode()))
    parts = []
    NP = 18 if high else 12
    for i in range(NP):
        ang = 2 * math.pi * i / NP + rng.uniform(-0.2, 0.2)
        speed = R * rng.uniform(1.5, 2.8)
        life = rng.uniform(0.45, 0.85)
        streak = i % 2 == 0
        b = sk.bone(f'p{i}', 'fx', rot=math.degrees(ang) if streak else 0)
        if streak:
            sk.slot(f'p{i}', b, 'spark', w=R * 0.28, blend='additive', color='d8ecffff')
        else:
            sk.slot(f'p{i}', b, 'dot', w=R * rng.uniform(0.07, 0.13), blend='additive', color='e6f2ffff')
        parts.append((b, ang, speed, life))

    for s_ in sk.slots:
        if s_['name'] in ('rays', 'halo', 'ring1', 'ring2', 'edge', 'flash') or s_['name'].startswith('p'):
            c = s_.get('color', 'ffffffff')
            s_['color'] = c[:6] + '00'

    # --- body: squash, pop, electrocution shake, charged hover, settle
    T_POP, T_SHAKE, T_SETTLE = 0.2, 0.55, D - 0.42

    def body_scale(t):
        if t < 0.07:
            k = t / 0.07
            return (1 + 0.08 * k, 1 - 0.1 * k)
        if t < T_POP:
            k = (t - 0.07) / (T_POP - 0.07)
            s1 = 1 + 0.28 * out_back(k, 2.2)
            sx = lerp_(1.08, s1, k)
            sy = lerp_(0.9, s1, k)
            return (sx, sy)
        if t < T_SETTLE:
            base = 1.28 + (1.18 - 1.28) * clamp((t - T_POP) / 0.35)
            p = 0.03 * math.sin((t - T_POP) * 2 * math.pi * 2.2)
            return (base + p, base + p)
        k = out_cubic(clamp((t - T_SETTLE) / (D - T_SETTLE)))
        base = 1.18 + 0.03 * math.sin((T_SETTLE - T_POP) * 2 * math.pi * 2.2)
        v = base + (1 - base) * k
        return (v, v)
    sk.anim('win', 'body', 'scale', body_scale)

    jit = random.Random(zlib.crc32(f'{code}/shake'.encode()))
    shake_r = [jit.uniform(-1, 1) for _ in range(200)]
    shake_x = [jit.uniform(-1, 1) for _ in range(200)]
    shake_y = [jit.uniform(-1, 1) for _ in range(200)]

    def env(t):
        if T_POP * 0.6 < t < T_SHAKE:
            return 1 - (t - T_POP * 0.6) / (T_SHAKE - T_POP * 0.6)
        return 0.0

    sk.anim('win', 'body', 'rotate', lambda t: 7 * env(t) * shake_r[int(t * FPS / 2) % 200])
    sk.anim('win', 'body', 'translate', lambda t: (R * 0.05 * env(t) * shake_x[int(t * FPS / 2) % 200],
                                                   R * 0.05 * env(t) * shake_y[int(t * FPS / 2) % 200]))

    # --- strike from above
    sk.flicker('win', 'strike', strikes, lambda t: 0.03 < t < 0.24 and int(t * FPS) % 5 != 3, step=1, seed=5)
    # --- flashes
    def flash_a(t):
        v = 0.95 * math.exp(-max(0, t - 0.07) * 10) if t >= 0.05 else 0
        for t0 in (0.75, 1.15):
            if t0 < t < t0 + 0.07:
                v = max(v, 0.35)
        return v if t < D - 0.3 else 0
    sk.anim('win', 'flash', 'alpha', flash_a)
    # --- zapped negative frames
    sk.flicker('win', 'xray', ['xray'],
               lambda t: (0.08 < t < 0.42 and int(t * FPS) % 4 < 2) or 0.76 < t < 0.8 or 1.16 < t < 1.2,
               step=1, seed=6)
    # --- edge + halo charge
    fl = random.Random(zlib.crc32(f'{code}/fl'.encode()))
    flick = [fl.uniform(0.55, 1.0) for _ in range(200)]

    def charged(t, peak):
        if t < 0.1:
            return 0
        a = peak * clamp((t - 0.1) / 0.08) * flick[int(t * FPS / 2) % 200]
        return a * (1 - clamp((t - (D - 0.5)) / 0.35))
    sk.anim('win', 'edge', 'alpha', lambda t: charged(t, 1.0))
    sk.anim('win', 'halo', 'alpha', lambda t: charged(t, 0.8))
    # --- shockwaves
    for bn, t0, smax in (('ring1', 0.07, 2.1), ('ring2', 0.3, 1.6)):
        sk.anim('win', bn, 'scale', lambda t, t0=t0, smax=smax: (lambda k: (0.2 + (smax - 0.2) * out_cubic(k),) * 2)(clamp((t - t0) / 0.5)))
        sk.anim('win', bn, 'alpha', lambda t, t0=t0: 0 if t < t0 or t > t0 + 0.5 else (1 - clamp((t - t0) / 0.5)) ** 1.5)
    # --- god rays behind
    peak = 0.75 if high else 0.4
    sk.anim('win', 'rays_b', 'rotate', lambda t: -40 * t / D)
    sk.anim('win', 'rays_b', 'scale', lambda t: (0.5 + 0.6 * out_cubic(clamp((t - 0.08) / 0.4)),) * 2)
    sk.anim('win', 'rays', 'alpha', lambda t: peak * clamp((t - 0.08) / 0.15) * (1 - clamp((t - (D - 0.6)) / 0.45)))
    # --- arcs crawling on the contour
    for a, frames in enumerate(arcs):
        sk.flicker('win', f'carc{a}', frames,
                   lambda t, a=a: 0.12 + a * 0.1 < t < D - 0.35 and (int(t * 30) + a * 5) % 9 < 6,
                   step=2, seed=a + 21)
    # --- particles: ballistic burst
    G = R * 5.0
    for b, ang, speed, life in parts:
        sk.anim('win', b, 'translate', lambda t, ang=ang, speed=speed: (
            math.cos(ang) * speed * max(0.0, t - 0.08),
            math.sin(ang) * speed * max(0.0, t - 0.08) - 0.5 * G * max(0.0, t - 0.08) ** 2))
        sk.anim('win', b, 'alpha', lambda t, life=life: 0 if t < 0.08 or t > 0.08 + life else
                (1 - (t - 0.08) / life) ** 0.8)

    if code == 'coin':
        I = IDLE_DUR
        sk.anim('idle', 'edge', 'alpha', lambda t: 0.45 + 0.35 * flick[int(t * FPS / 2) % 200] * 0.8)
        sk.anim('idle', 'halo', 'alpha', lambda t: 0.3 + 0.2 * (1 - math.cos(2 * math.pi * t / I)) / 2)
        for a, frames in enumerate(arcs):
            sk.flicker('idle', f'carc{a}', frames,
                       lambda t, a=a: (int(t * 30) + a * 11) % 17 < 6, step=2, seed=a + 31)
    sk.write()


def lerp_(a, b, k):
    return a + (b - a) * k


def linear_ease(t):
    return t


def build_zap():
    """FX-only skeleton played over a cell when a Hold & Win coin lands: a bolt
    strikes the cell from above, the cell flashes, two shockwaves and a burst
    of sparks. No `item` slot — the coin itself is the DOM <img> under it, so
    the skeleton is fitted by its own 400x400 box (= the cell)."""
    B = 400
    R = B / 2
    sk = SymSkel('zap', B, B, OUT, {'hit': 1.0})
    sk.image('glow', soft_glow(256))
    sk.image('ring', ring_img())
    sk.image('dot', dot_img())
    sk.image('spark', spark(64, 12))
    sk.image('rays', rays(512, n=12, col=(150, 205, 255)))
    strikes = []
    for v in range(3):
        sk.image(f'strike{v}', strike_img(B * 0.6, B * 1.9, 1300 + v))
        strikes.append(f'strike{v}')
    sk.bone('rays_b')
    sk.bone('ring1')
    sk.bone('ring2')
    sk.bone('fx')
    sk.slot('rays', 'rays_b', 'rays', w=B * 1.5, blend='additive')
    sk.slot('glow', 'fx', 'glow', w=B * 1.6, blend='additive', color='8cc8ffff')
    sk.slot('ring1', 'ring1', 'ring', w=B * 1.1, blend='additive')
    sk.slot('ring2', 'ring2', 'ring', w=B * 1.1, blend='additive')
    sk.variants('strike', 'fx', strikes, w=B * 0.6, h=B * 1.9, y=B * 0.95)
    sk.hide_in_setup('strike')
    rng = random.Random(77)
    parts = []
    for i in range(16):
        ang = 2 * math.pi * i / 16 + rng.uniform(-0.2, 0.2)
        streak = i % 2 == 0
        b = sk.bone(f'p{i}', 'fx', rot=math.degrees(ang) if streak else 0)
        if streak:
            sk.slot(f'p{i}', b, 'spark', w=R * 0.3, blend='additive', color='d8ecffff')
        else:
            sk.slot(f'p{i}', b, 'dot', w=R * rng.uniform(0.08, 0.14), blend='additive', color='e6f2ffff')
        parts.append((b, ang, R * rng.uniform(1.6, 2.8), rng.uniform(0.4, 0.75)))
    for s_ in sk.slots:
        if s_['name'] in ('rays', 'glow', 'ring1', 'ring2') or s_['name'].startswith('p'):
            c = s_.get('color', 'ffffffff')
            s_['color'] = c[:6] + '00'
    sk.flicker('hit', 'strike', strikes, lambda t: t < 0.22 and int(t * FPS) % 5 != 3, step=1, seed=9)
    sk.anim('hit', 'glow', 'alpha', lambda t: 0.95 * math.exp(-max(0, t - 0.05) * 5) if t >= 0.03 else 0)
    for bn, t0, smax in (('ring1', 0.04, 1.9), ('ring2', 0.22, 1.4)):
        sk.anim('hit', bn, 'scale', lambda t, t0=t0, smax=smax: (lambda k: (0.2 + (smax - 0.2) * out_cubic(k),) * 2)(clamp((t - t0) / 0.45)))
        sk.anim('hit', bn, 'alpha', lambda t, t0=t0: 0 if t < t0 or t > t0 + 0.45 else (1 - clamp((t - t0) / 0.45)) ** 1.5)
    sk.anim('hit', 'rays_b', 'rotate', lambda t: -30 * t)
    sk.anim('hit', 'rays', 'alpha', lambda t: 0.8 * clamp((t - 0.05) / 0.1) * (1 - clamp((t - 0.45) / 0.5)))
    G = R * 5.0
    for b, ang, speed, life in parts:
        sk.anim('hit', b, 'translate', lambda t, ang=ang, speed=speed: (
            math.cos(ang) * speed * max(0.0, t - 0.05),
            math.sin(ang) * speed * max(0.0, t - 0.05) - 0.5 * G * max(0.0, t - 0.05) ** 2))
        sk.anim('hit', b, 'alpha', lambda t, life=life: 0 if t < 0.05 or t > 0.05 + life else
                (1 - (t - 0.05) / life) ** 0.8)
    sk.write()


def main():
    for code in CODES:
        build_symbol(code)
    build_zap()


if __name__ == '__main__':
    main()
