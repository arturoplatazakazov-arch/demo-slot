"""Volt Coins: in-game Spine FX generated in code (spine_screen_kit).

Skeletons into front/img/volt-coins/fx/, each authored in the pixel space of
the DOM element it is anchored to (js/volt-coins/fx.js), so CSS stays the only
source of layout truth:

  bg_desk / bg_mob  bg_*.jpg px. The vault door behind the reels: `idle`
                    (8s, dark — only a rare light streak and a faint pass of
                    light round the door ring, per the client: "в idle только
                    редкие прострелы"), `charge` (1.6s: the ring lights up
                    segment by segment and the door turns a quarter — the
                    Hold & Win entry, no fly-in), `bonus` (3s loop).
  coil              coil.png px. Tesla coil states from the client's table:
                    `off` (7s: dark, one rare spark), `spin` (0.6s short
                    charge), `charge` (1.6s growing arcs -> anticipation),
                    `charged` (0.8s loop), `win` (1s loop), `discharge` (0.9s
                    full discharge), `bigwin` (0.6s loop of arcs at the peak).
  arc               one reusable lightning stroke from (0,0) to (1000,0) — fx.js
                    rotates/stretches it between any two points: coil -> coin,
                    coin -> jackpot plate, coil -> frame. Clip `zap` (0.5s).
                    Four bolt shapes flicker through (the client: "3-4
                    переиспользуемые формы дуги, а не покадровые секвенции").
  frame             frame.png px. LEDs, an energy chase round the border,
                    window-edge glow. `idle` (4s), `win` (1.2s), `charge`
                    (1.4s), `bonus` (2s).
  logo              logo.png px. The logo itself + bolt crackle in the O,
                    light sweep, glints. `idle` (4s), `win` (1.2s).
  winlines          reel-window px (766x604, same proportions on both layouts).
                    Five paylines drawn as electric beams INSIDE the frame
                    (client: lines are not drawn by the coils).
                    `line{n}_in` (0.7s) + `line{n}_loop` (1.2s).
  symbols           symbol-canvas px (320x254 = one cell). One clip per code,
                    1.1s, starts and ends on the static tile.

Every slot an animation touches starts transparent, so a fresh instance shows
nothing until a clip plays.

    .venv/bin/python scripts/volt_coins_fx.py [names...] [--preview DIR]
"""

import hashlib
import json
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from spine_screen_kit import (  # noqa: E402
    FPS, Skel, clamp, in_out_sine, lerp, out_back, out_cubic, pack, premultiply,
    pulse, rays, seg, soft_glow, spark,
)

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'volt-coins')
ART = os.path.join(ROOT, 'img')
SYM = os.path.join(ROOT, 'symbols')
OUT = os.path.join(ROOT, 'fx')

CYAN = (90, 210, 255)
VOLT = (170, 235, 255)
AMBER = (255, 190, 70)


def frac(x):
    return x - math.floor(x)


def lin(t):
    return t


def in_cubic(t):
    return t ** 3


# --------------------------------------------------------------------------
# kit extension: named clips of any length (same as ice_spin_deluxe_fx.Fx)

class Fx(Skel):
    def __init__(self, name, w, h, res, clips):
        super().__init__(name, w, h, res, OUT)
        self.durs = dict(clips)
        self.anims = {k: {'bones': {}, 'slots': {}} for k in clips}

    def anim(self, which, target, prop, fn):
        self.idle = self.durs[which]
        super().anim(which, target, prop, fn)

    def hidden_slot(self, name, bone, region, color='ffffff', **kw):
        return self.slot(name, bone, region, color=color + '00', **kw)

    def xy(self, ix, iy):
        """Element px (y down) -> skeleton units (centred, y up)."""
        return ix - self.w / 2, self.h / 2 - iy

    def write(self):
        out = os.path.join(self.out_dir, self.name)
        os.makedirs(out, exist_ok=True)
        for f in os.listdir(out):
            if f.startswith('animation'):
                os.remove(os.path.join(out, f))
        regions = {}
        for r, im in self.images.items():
            if r not in self.need:
                continue
            w, _ = self.need[r]
            tw = max(2, min(im.width, int(math.ceil(w * self.res_of.get(r, self.res)))))
            th = max(2, int(round(tw * im.height / im.width)))
            regions[r] = im.resize((tw, th), Image.LANCZOS) if (tw, th) != im.size else im
        pages = pack(regions)
        atlas = []
        for pi, (page, placed) in enumerate(pages):
            fname = 'animation.png' if pi == 0 else f'animation{pi + 1}.png'
            premultiply(page).save(os.path.join(out, fname), optimize=True)
            # страница с хешем содержимого: Telegram/браузер держат старый PNG
            # по тому же адресу, и после пересборки играл бы прежний арт
            with open(os.path.join(out, fname), 'rb') as pf:
                ver = hashlib.md5(pf.read()).hexdigest()[:8]
            atlas += [f'{fname}?v={ver}', f'size:{page.width},{page.height}', 'filter:Linear,Linear', 'pma:true']
            for r, (x, y, w, h) in placed.items():
                atlas += [r, f'bounds:{x},{y},{w},{h}']
            atlas.append('')
        with open(os.path.join(out, 'animation.atlas'), 'w') as f:
            f.write('\n'.join(atlas))
        self.data = {
            'skeleton': {'hash': self.name, 'spine': '4.1.24', 'x': -self.w / 2, 'y': -self.h / 2,
                         'width': self.w, 'height': self.h, 'fps': FPS},
            'bones': self.bones,
            'slots': self.slots,
            'skins': [{'name': 'default', 'attachments': self.atts}],
            'animations': self.anims,
        }
        with open(os.path.join(out, 'animation.json'), 'w') as f:
            json.dump(self.data, f, separators=(',', ':'))
        size = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out))
        print(f'{self.name}: bones {len(self.bones)} slots {len(self.slots)} '
              f'pages {[p.size for p, _ in pages]} {size / 1024:.0f}KB')


# --------------------------------------------------------------------------
# images

def edge_fade(im, frac_x=0.06, frac_y=0.12):
    """Fade alpha to zero towards the image border. Every procedural glow
    sprite goes through this: a glow that still has alpha at its border is
    drawn as a visible rectangle (the coil ring did exactly that)."""
    w, h = im.size
    fx = max(2, int(w * frac_x))
    fy = max(2, int(h * frac_y))
    xs = [clamp(min(x, w - 1 - x) / fx) for x in range(w)]
    ys = [clamp(min(y, h - 1 - y) / fy) for y in range(h)]
    row = Image.new('L', (w, 1))
    row.putdata([int(255 * (v * v * (3 - 2 * v))) for v in xs])
    col = Image.new('L', (1, h))
    col.putdata([int(255 * (v * v * (3 - 2 * v))) for v in ys])
    mask = ImageChops.multiply(row.resize((w, h)), col.resize((w, h)))
    out = im.copy()
    out.putalpha(ImageChops.multiply(im.getchannel('A'), mask))
    return out


def tint(im, rgb):
    out = Image.new('RGBA', im.size, rgb + (0,))
    out.putalpha(im.getchannel('A'))
    return out


def glow_dot(size, core=0.18, col=CYAN):
    halo = tint(soft_glow(size), col)
    c = int(size * core)
    hot = soft_glow(c * 2).resize((c * 2, c * 2))
    out = halo.copy()
    out.alpha_composite(hot, ((size - 2 * c) // 2, (size - 2 * c) // 2))
    return out


def star4(size, col=(255, 255, 255), thin=0.035):
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    c = big / 2
    t = big * thin
    d.polygon([(0, c), (c, c - t), (big, c), (c, c + t)], fill=255)
    d.polygon([(c, 0), (c + t, c), (c, big), (c - t, c)], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(big / 160)).resize((size, size), Image.LANCZOS)
    g = soft_glow(size).getchannel('A').point(lambda v: int(v * 0.3))
    core = Image.new('L', (size, size))
    core.paste(soft_glow(size // 3).getchannel('A'), (size // 3, size // 3))
    m = ImageChops.lighter(ImageChops.lighter(m, g), core)
    out = Image.new('RGBA', (size, size), col + (0,))
    out.putalpha(m)
    return edge_fade(out, 0.12, 0.12)


def ring(size, thick=0.07, col=(255, 255, 255), sy=1.0):
    """Glowing ellipse ring. The ellipse is (1 - 2*0.12) of the width wide and
    `sy` times that tall; the canvas keeps the SAME absolute padding above and
    below as at the sides, so the blur never reaches the border (with the old
    `pad * sy` a flat ring got almost no vertical room — the coil's ring glow
    showed as a rectangle)."""
    big = size * 2
    pad = big * 0.12
    eh = (big - 2 * pad) * sy
    h = int(round(eh + 2 * pad))
    m = Image.new('L', (big, h))
    d = ImageDraw.Draw(m)
    d.ellipse([pad, pad, big - pad, pad + eh], outline=255, width=max(2, int(big * thick)))
    m = m.filter(ImageFilter.GaussianBlur(big * 0.02)).resize((size, max(2, int(round(h / 2)))), Image.LANCZOS)
    m2 = m.filter(ImageFilter.GaussianBlur(size * 0.04))
    m = ImageChops.lighter(m, m2.point(lambda v: min(255, v * 2)))
    out = Image.new('RGBA', m.size, col + (0,))
    out.putalpha(m)
    return edge_fade(out, 0.04, 0.04)


def hband(w, h, sigma=0.22, taper=0.06, col=(255, 255, 255)):
    col_a = Image.new('L', (1, h))
    for y in range(h):
        v = (y - (h - 1) / 2) / (h / 2)
        col_a.putpixel((0, y), int(255 * math.exp(-(v / sigma) ** 2 / 2)))
    row = Image.new('L', (w, 1))
    for x in range(w):
        u = min(x, w - 1 - x) / (w * taper)
        row.putpixel((x, 0), int(255 * clamp(u) ** 0.8))
    a = ImageChops.multiply(col_a.resize((w, h)), row.resize((w, h)))
    out = Image.new('RGBA', (w, h), col + (0,))
    out.putalpha(a)
    return out


def bolt(w, h, seed, forks=5, rough=0.55, width=5):
    """Lightning stroke left -> right across the image, white core + glow."""
    rnd = random.Random(seed)
    sc = 2
    m = Image.new('L', (w * sc, h * sc))
    d = ImageDraw.Draw(m)
    n = 34
    pts = []
    y = 0.0
    for i in range(n + 1):
        y = clamp(y + rnd.uniform(-rough, rough), -1, 1) * 0.85
        taper = math.sin(math.pi * i / n) ** 0.5
        pts.append((i / n * w * sc, h * sc / 2 + y * h * sc * 0.36 * taper))
    d.line(pts, fill=255, width=width * sc, joint='curve')
    for _ in range(forks):
        i = rnd.randrange(3, n - 6)
        x0, y0 = pts[i]
        fork = [(x0, y0)]
        for k in range(1, 5):
            fork.append((x0 + k * w * sc / n, fork[-1][1] + rnd.uniform(-1, 1) * h * sc * 0.12))
        d.line(fork, fill=170, width=2 * sc)
    m = m.resize((w, h), Image.LANCZOS)
    glow = m.filter(ImageFilter.GaussianBlur(h * 0.08)).point(lambda v: min(255, v * 3))
    a = ImageChops.lighter(m, glow.point(lambda v: v * 2 // 3))
    out = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    out.putalpha(a)
    return edge_fade(out, 0.04, 0.1)


def rect_line(w, h, line, blur, r=8):
    pad = int(blur * 3)
    m = Image.new('L', (w + 2 * pad, h + 2 * pad))
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, pad + w, pad + h], r, outline=255, width=line)
    g = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, v * 3))
    out = Image.new('RGBA', m.size, (255, 255, 255, 0))
    out.putalpha(ImageChops.lighter(m, g))
    return out, pad


def highlight(im, gamma=1.6, gain=1.25):
    lum = im.convert('RGB').convert('L').point(lambda v: int(255 * clamp((v / 255) ** gamma * gain)))
    a = ImageChops.multiply(lum, im.getchannel('A'))
    out = Image.new('RGBA', im.size, (255, 255, 255, 0))
    out.putalpha(a)
    return out


def strips(im, n):
    out = []
    for i in range(n):
        x0, x1 = round(im.width * i / n), round(im.width * (i + 1) / n)
        out.append((im.crop((x0, 0, x1, im.height)), x0, x1))
    return out


def silhouette_halo(im, pad, blur, col, inner=0.8):
    al = im.getchannel('A')
    big = Image.new('L', (im.width + 2 * pad, im.height + 2 * pad))
    big.paste(al, (pad, pad))
    b = big.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, int(v * 1.7)))
    ins = Image.new('L', big.size)
    ins.paste(al.point(lambda v: int(v * inner)), (pad, pad))
    out = Image.new('RGBA', big.size, col + (0,))
    out.putalpha(ImageChops.subtract(b, ins))
    return out


def flicker(t, j, n=4, rate=0.07):
    """Which of n bolt shapes is lit at time t (one at a time, fast)."""
    return 1.0 if int(t / rate + 0.001) % n == j else 0.0


# --------------------------------------------------------------------------
# reusable arc: (0,0) -> (1000,0)

ARC_L, ARC_H = 1000, 140


def build_arc():
    sk = Fx('arc', ARC_L, ARC_H, 0.8, {'zap': 0.5})
    # skeleton bounds are centred on (0,0); the stroke starts at x=-500 so
    # fx.js can treat the left end as the origin by offsetting half a length.
    for j in range(4):
        sk.image(f'bolt{j}', bolt(1024, 128, 31 + j * 7, forks=6, rough=0.7))
    sk.image('glow', hband(512, 128, sigma=0.3, taper=0.03))
    sk.res_of['glow'] = 0.4
    sk.image('flare', star4(256))
    sk.image('dot', glow_dot(256, core=0.25, col=VOLT))
    beam = sk.bone('beam', x=-ARC_L / 2)
    sk.hidden_slot('glow', beam, 'glow', '5ad2ff', w=ARC_L, h=110, x=ARC_L / 2, blend='additive')
    for j in range(4):
        sk.hidden_slot(f'bolt{j}', beam, f'bolt{j}', 'bfeaff', w=ARC_L, h=ARC_H, x=ARC_L / 2, blend='additive')
    sb = sk.bone('src', x=-ARC_L / 2)
    sk.hidden_slot('src', sb, 'dot', w=150, blend='additive')
    hb = sk.bone('hit', x=ARC_L / 2)
    sk.hidden_slot('hitdot', hb, 'dot', w=220, blend='additive')
    sk.hidden_slot('hitflare', hb, 'flare', w=260, blend='additive')

    strike = 0.07

    def grow(t):
        return max(0.001, out_cubic(clamp(t / strike)))

    def life(t):
        return 1.0 if t < 0.22 else seg(t, 0.22, 0.5, 1, 0, in_out_sine)
    sk.anim('zap', beam, 'scale', lambda t: (grow(t), 1 + 0.25 * math.sin(t * 60)))
    sk.anim('zap', 'glow', 'alpha', lambda t: 0.8 * life(t))
    for j in range(4):
        sk.anim('zap', f'bolt{j}', 'alpha', lambda t, j=j: flicker(t, j, rate=0.045) * life(t))
    sk.anim('zap', 'src', 'alpha', lambda t: 0.9 * life(t))
    sk.anim('zap', 'hitdot', 'alpha', lambda t: 0.0 if t < strike else seg(t, strike, 0.5, 1, 0, out_cubic))
    sk.anim('zap', 'hitflare', 'alpha', lambda t: 0.0 if t < strike else seg(t, strike, 0.45, 1, 0))
    sk.anim('zap', hb, 'scale', lambda t: (0.01 if t < strike else seg(t, strike, 0.3, 0.3, 1.4, out_back),) * 2)
    sk.anim('zap', hb, 'rotate', lambda t: 120 * t)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# Tesla coil (coil.png px, 566x1080)

COIL_W, COIL_H = 566, 1080
COIL_RING = (283, 85, 258, 70)  # cx, cy, rx, ry  (coil px, v2 regen)


def build_coil():
    clips = {'off': 7.0, 'spin': 0.6, 'charge': 1.6, 'charged': 0.8, 'win': 1.0,
             'discharge': 0.9, 'bigwin': 0.6}
    sk = Fx('coil', COIL_W, COIL_H, 0.9, clips)
    cx, cy, rx, ry = COIL_RING
    hx, hy = sk.xy(cx, cy)

    sk.image('ringglow', ring(512, thick=0.05, col=(255, 255, 255), sy=ry / rx))
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.4
    sk.image('column', hband(512, 96, sigma=0.32, taper=0.12))
    sk.res_of['column'] = 0.5
    sk.image('flare', star4(256))
    for j in range(4):
        sk.image(f'zz{j}', bolt(512, 96, 101 + j * 13, forks=3, rough=0.8, width=4))

    head = sk.bone('head', x=hx, y=hy)
    sk.hidden_slot('halo', head, 'halo', '4fc8ff', w=rx * 3.4, h=ry * 7, blend='additive')
    sk.hidden_slot('ring', head, 'ringglow', '8fe2ff', w=rx * 2.5, blend='additive')
    sk.hidden_slot('ringhot', head, 'ringglow', 'ffffff', w=rx * 2.46, blend='additive')
    # glow down the spring (coil px y 85..300)
    col = sk.bone('column', x=0, y=sk.xy(cx, 380)[1], rot=90)
    sk.hidden_slot('column', col, 'column', '3fa8ff', w=560, h=200, blend='additive')

    # arcs: 6 sockets round the head, each with 4 flickering shapes
    sockets = []
    for i in range(6):
        ang = -20 + i * (220 / 5) if i < 6 else 0  # fan over the top
        a = math.radians(ang + 0)
        bx = hx + math.cos(math.radians(ang)) * rx * 0.55
        by = hy + abs(math.sin(math.radians(ang))) * ry * 0.4 + 6
        b = sk.bone(f'arc{i}', x=bx, y=by, rot=ang + (25 if i % 2 else -25))
        names = []
        for j in range(4):
            n = f'arc{i}_{j}'
            sk.hidden_slot(n, b, f'zz{j}', 'cdf3ff', w=280 + 45 * (i % 3), h=74, x=140, blend='additive')
            names.append(n)
        sockets.append((b, names, a))
    fb = sk.bone('flare', x=hx, y=hy + 8)
    sk.hidden_slot('flare', fb, 'flare', w=560, blend='additive')

    def arcs(clip, level_fn, rate=0.06, active=6):
        for i, (b, names, _) in enumerate(sockets):
            for j, n in enumerate(names):
                def fn(t, i=i, j=j):
                    lv = level_fn(t)
                    if i >= active or lv <= 0:
                        return 0.0
                    # sockets fire out of phase so the head always crackles
                    on = flicker(t + i * 0.023, (j + i) % 4, rate=rate)
                    gate = 1.0 if frac(t * 3.1 + i * 0.37) < 0.25 + 0.6 * lv else 0.0
                    return on * gate * lv
                sk.anim(clip, n, 'alpha', fn)

    def all_off(clip):
        for i, (b, names, _) in enumerate(sockets):
            for n in names:
                sk.anim(clip, n, 'alpha', lambda t: 0.0)

    # off: dark; one spark at ~5.2s (two coils run this out of phase)
    sk.anim('off', 'ring', 'alpha', lambda t: 0.06 + 0.04 * math.sin(2 * math.pi * t / 7.0))
    sk.anim('off', 'ringhot', 'alpha', lambda t: 0.0)
    sk.anim('off', 'halo', 'alpha', lambda t: 0.0 if not 5.15 < t < 5.6 else 0.5 * seg(t, 5.15, 5.6, 1, 0))
    sk.anim('off', 'column', 'alpha', lambda t: 0.0)
    sk.anim('off', 'flare', 'alpha', lambda t: 0.0 if not 5.15 < t < 5.5 else seg(t, 5.15, 5.5, 1, 0))
    sk.anim('off', fb, 'scale', lambda t: (0.6,) * 2)
    for i, (b, names, _) in enumerate(sockets):
        for j, n in enumerate(names):
            hit = i in (1, 4) and j == (i % 4)
            sk.anim('off', n, 'alpha', lambda t, hit=hit: 1.0 if hit and 5.15 < t < 5.42 and int(t / 0.06) % 2 == 0 else 0.0)

    # spin: ~0.5s short charge
    def spin_lv(t):
        return seg(t, 0, 0.08, 0, 1) if t < 0.08 else seg(t, 0.08, 0.6, 1, 0, in_out_sine)
    sk.anim('spin', 'ring', 'alpha', lambda t: 0.06 + 0.9 * spin_lv(t))
    sk.anim('spin', 'ringhot', 'alpha', lambda t: 0.7 * spin_lv(t))
    sk.anim('spin', 'halo', 'alpha', lambda t: 0.7 * spin_lv(t))
    sk.anim('spin', 'column', 'alpha', lambda t: 0.6 * spin_lv(t))
    sk.anim('spin', 'flare', 'alpha', lambda t: spin_lv(t))
    sk.anim('spin', fb, 'scale', lambda t: (0.5 + 0.7 * spin_lv(t),) * 2)
    arcs('spin', spin_lv, active=4)

    # charge: 1.6s ramp (anticipation), arcs grow with it
    def ch_lv(t):
        return in_out_sine(clamp(t / 1.6))
    sk.anim('charge', 'ring', 'alpha', lambda t: 0.1 + 0.85 * ch_lv(t))
    sk.anim('charge', 'ringhot', 'alpha', lambda t: 0.6 * ch_lv(t) * (0.8 + 0.2 * math.sin(t * 50)))
    sk.anim('charge', 'halo', 'alpha', lambda t: 0.75 * ch_lv(t))
    sk.anim('charge', 'column', 'alpha', lambda t: 0.75 * ch_lv(t))
    sk.anim('charge', 'flare', 'alpha', lambda t: 0.6 * ch_lv(t))
    sk.anim('charge', fb, 'scale', lambda t: (0.4 + 0.6 * ch_lv(t),) * 2)
    sk.anim('charge', fb, 'rotate', lambda t: 200 * t)
    arcs('charge', ch_lv, rate=0.05)
    for i, (b, names, _) in enumerate(sockets):
        sk.anim('charge', b, 'scale', lambda t: (0.35 + 0.75 * ch_lv(t), 1.0))

    # charged: loop at full (end state of charge)
    sk.anim('charged', 'ring', 'alpha', lambda t: 0.95)
    sk.anim('charged', 'ringhot', 'alpha', lambda t: 0.6 + 0.2 * math.sin(2 * math.pi * t / 0.2))
    sk.anim('charged', 'halo', 'alpha', lambda t: 0.75 + 0.1 * math.sin(2 * math.pi * t / 0.4))
    sk.anim('charged', 'column', 'alpha', lambda t: 0.75)
    sk.anim('charged', 'flare', 'alpha', lambda t: 0.6)
    sk.anim('charged', fb, 'scale', lambda t: (1.0,) * 2)
    sk.anim('charged', fb, 'rotate', lambda t: 320 + 200 * t)
    arcs('charged', lambda t: 1.0, rate=0.05)
    for i, (b, names, _) in enumerate(sockets):
        sk.anim('charged', b, 'scale', lambda t: (1.1, 1.0))

    # win: pulsing (1s loop)
    def win_lv(t):
        return 0.35 + 0.65 * pulse(t, 0.5, 0.0, sharp=3)
    sk.anim('win', 'ring', 'alpha', lambda t: 0.2 + 0.7 * win_lv(t))
    sk.anim('win', 'ringhot', 'alpha', lambda t: 0.5 * win_lv(t))
    sk.anim('win', 'halo', 'alpha', lambda t: 0.55 * win_lv(t))
    sk.anim('win', 'column', 'alpha', lambda t: 0.5 * win_lv(t))
    sk.anim('win', 'flare', 'alpha', lambda t: 0.4 * win_lv(t))
    sk.anim('win', fb, 'scale', lambda t: (0.6 + 0.3 * win_lv(t),) * 2)
    arcs('win', lambda t: win_lv(t) * 0.7, active=4)

    # discharge: flash at once, everything fires, then dies out
    def dis_lv(t):
        return seg(t, 0, 0.05, 0, 1) if t < 0.05 else (1.0 if t < 0.35 else seg(t, 0.35, 0.9, 1, 0, in_out_sine))
    sk.anim('discharge', 'ring', 'alpha', lambda t: dis_lv(t))
    sk.anim('discharge', 'ringhot', 'alpha', lambda t: dis_lv(t))
    sk.anim('discharge', 'halo', 'alpha', lambda t: dis_lv(t))
    sk.anim('discharge', 'column', 'alpha', lambda t: dis_lv(t))
    sk.anim('discharge', 'flare', 'alpha', lambda t: dis_lv(t))
    sk.anim('discharge', fb, 'scale', lambda t: (0.6 + 1.4 * out_cubic(clamp(t / 0.3)),) * 2)
    sk.anim('discharge', 'halo', 'alpha', lambda t: dis_lv(t))
    sk.anim('discharge', head, 'scale', lambda t: (1 + 0.15 * dis_lv(t),) * 2)
    arcs('discharge', dis_lv, rate=0.04)
    for i, (b, names, _) in enumerate(sockets):
        sk.anim('discharge', b, 'scale', lambda t: (1.0 + 0.6 * dis_lv(t), 1.2))

    # bigwin: arcs at the peak (0.6s loop)
    sk.anim('bigwin', 'ring', 'alpha', lambda t: 0.95)
    sk.anim('bigwin', 'ringhot', 'alpha', lambda t: 0.7 + 0.3 * math.sin(2 * math.pi * t / 0.15))
    sk.anim('bigwin', 'halo', 'alpha', lambda t: 0.85)
    sk.anim('bigwin', 'column', 'alpha', lambda t: 0.85)
    sk.anim('bigwin', 'flare', 'alpha', lambda t: 0.8)
    sk.anim('bigwin', fb, 'scale', lambda t: (1.1 + 0.2 * math.sin(2 * math.pi * t / 0.3),) * 2)
    sk.anim('bigwin', fb, 'rotate', lambda t: 600 * t)
    arcs('bigwin', lambda t: 1.0, rate=0.04)
    for i, (b, names, _) in enumerate(sockets):
        sk.anim('bigwin', b, 'scale', lambda t: (1.35, 1.1))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# vault door behind the reels (bg px)

DOORS = {
    # name: (bg w, bg h, door centre, ring radius)
    'bg_desk': (1798, 875, (905, 395), 520),
    'bg_mob': (931, 1690, (465, 372), 345),
}


def build_door(name):
    W, H, (dcx, dcy), R = DOORS[name]
    sk = Fx(name, W, H, 0.6, {'idle': 8.0, 'charge': 1.6, 'bonus': 3.0})
    sk.image('seg', glow_dot(128, core=0.22, col=CYAN))
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.3
    sk.image('beam', hband(512, 64, sigma=0.35, taper=0.2))
    sk.res_of['beam'] = 0.4
    sk.image('ringline', ring(1024, thick=0.012, col=(255, 255, 255)))
    sk.res_of['ringline'] = 0.7

    cx, cy = sk.xy(dcx, dcy)
    door = sk.bone('door', x=cx, y=cy)
    sk.hidden_slot('center', door, 'halo', '2a7bff', w=R * 2.2, blend='additive')
    sk.hidden_slot('ringline', door, 'ringline', '6fd3ff', w=R * 2 / 0.76, blend='additive')
    N = 40
    segs = []
    for k in range(N):
        a = 2 * math.pi * k / N
        sk.hidden_slot(f's{k}', sk.bone(f's{k}', parent=door, x=math.cos(a) * R, y=math.sin(a) * R),
                       'seg', w=R * 0.16, blend='additive')
        segs.append((f's{k}', a))

    # two diagonal light streaks ("прострелы")
    streaks = []
    for i, (ang, y0) in enumerate(((-24, H * 0.25), (18, H * 0.62))):
        b = sk.bone(f'st{i}', x=-W, y=H / 2 - y0, rot=ang)
        sk.hidden_slot(f'st{i}', b, 'beam', 'a9e4ff', w=W * 0.7, h=H * 0.05, blend='additive')
        streaks.append((b, f'st{i}', H / 2 - y0, ang))

    # --- idle: dark. A faint pass of light round the ring and two streaks.
    def ring_pass(a, t, t0, dur, peak):
        if not t0 <= t <= t0 + dur:
            return 0.0
        head = 2 * math.pi * (1 - (t - t0) / dur) + math.pi / 2
        d = (a - head) % (2 * math.pi)
        return peak * math.exp(-(d / 0.5) ** 2) * math.sin(math.pi * (t - t0) / dur)
    for n, a in segs:
        sk.anim('idle', n, 'alpha', lambda t, a=a: ring_pass(a, t, 2.0, 2.6, 0.45))
    sk.anim('idle', 'ringline', 'alpha', lambda t: 0.05 + 0.04 * math.sin(2 * math.pi * t / 8))
    sk.anim('idle', 'center', 'alpha', lambda t: 0.0)
    for i, (b, n, y, ang) in enumerate(streaks):
        t0 = 0.6 if i == 0 else 5.2

        def pos(t, t0=t0, y=y):
            u = clamp((t - t0) / 1.4)
            return (lerp(-W * 0.9, W * 0.9, in_out_sine(u)), y)
        sk.anim('idle', b, 'translate', pos)
        sk.anim('idle', n, 'alpha', lambda t, t0=t0: 0.0 if not t0 < t < t0 + 1.4 else 0.35 * math.sin(math.pi * (t - t0) / 1.4))
    sk.anim('idle', door, 'rotate', lambda t: 0.0)

    # --- charge: segments light one by one round the ring while the door
    # turns a quarter, then a flash; ends on the bonus pose.
    def lit(a, t):
        u = (a % (2 * math.pi)) / (2 * math.pi)
        tk = 0.1 + 0.9 * u
        return 0.0 if t < tk else (1.0 if t < tk + 0.12 else seg(t, tk + 0.12, 1.6, 1.0, 0.55))
    for n, a in segs:
        sk.anim('charge', n, 'alpha', lambda t, a=a: lit(a, t))
    sk.anim('charge', door, 'rotate', lambda t: -90 * in_out_sine(clamp((t - 0.1) / 1.2)))
    sk.anim('charge', 'ringline', 'alpha', lambda t: seg(t, 0, 1.0, 0.05, 0.7) if t < 1.0 else seg(t, 1.0, 1.6, 1.0, 0.45))
    sk.anim('charge', 'center', 'alpha', lambda t: 0.0 if t < 1.0 else (seg(t, 1.0, 1.1, 0, 0.9) if t < 1.1 else seg(t, 1.1, 1.6, 0.9, 0.25)))
    for b, n, y, ang in streaks:
        sk.anim('charge', n, 'alpha', lambda t: 0.0)

    # --- bonus: charged door, a brighter wave keeps running round it
    for n, a in segs:
        sk.anim('bonus', n, 'alpha', lambda t, a=a: 0.4 + 0.5 * max(0.0, math.cos(a - 2 * math.pi * t / 3.0)) ** 6)
    sk.anim('bonus', door, 'rotate', lambda t: -90 - 30 * t / 3.0)
    sk.anim('bonus', 'ringline', 'alpha', lambda t: 0.45 + 0.1 * math.sin(2 * math.pi * t / 1.5))
    sk.anim('bonus', 'center', 'alpha', lambda t: 0.25 + 0.05 * math.sin(2 * math.pi * t / 3.0))
    for b, n, y, ang in streaks:
        sk.anim('bonus', n, 'alpha', lambda t: 0.0)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# cabinet frame (frame.png px, 870x694; window (49,48)-(815,652))

FR_W, FR_H = 870, 694
WIN = (49, 48, 815, 652)
# border mid-line the energy chase runs along
CHASE = (24, 22, 842, 668)
LEDS_AMBER = [(31, 33), (283, 29), (574, 29), (832, 39), (22, 235), (835, 234), (18, 353),
              (844, 350), (22, 466), (836, 466), (14, 648), (845, 648), (285, 662), (572, 662)]
LEDS_BLUE = [(429, 25), (182, 17), (660, 17), (104, 31), (754, 31), (23, 127), (832, 128),
             (41, 310), (816, 307), (19, 578), (839, 581), (428, 660), (91, 667), (765, 667)]


def perim(u):
    """Point at fraction u along the CHASE rectangle, clockwise from top-left."""
    L, T, R, B = CHASE
    w, h = R - L, B - T
    s = (u % 1) * 2 * (w + h)
    if s < w:
        return L + s, T
    s -= w
    if s < h:
        return R, T + s
    s -= h
    if s < w:
        return R - s, B
    return L, B - (s - w)


def build_frame():
    frame = Image.open(os.path.join(ART, 'frame.png')).convert('RGBA')
    sk = Fx('frame', FR_W, FR_H, 0.8, {'idle': 4.0, 'win': 1.2, 'charge': 1.4, 'bonus': 2.0})

    halo = silhouette_halo(frame, 50, 22, CYAN)
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.4
    sk.hidden_slot('halo', 'root', 'halo', w=halo.width, blend='additive')

    wl, wt, wr, wb = WIN
    edge, pad = rect_line(wr - wl, wb - wt, 4, 7, r=4)
    sk.image('edge', edge)
    sk.hidden_slot('edge', 'root', 'edge', '7fe0ff', w=edge.width, x=sk.xy((wl + wr) / 2, 0)[0],
                   y=sk.xy(0, (wt + wb) / 2)[1], blend='additive')

    sk.image('ledA', glow_dot(128, core=0.3, col=AMBER))
    sk.image('ledB', glow_dot(128, core=0.3, col=CYAN))
    leds = []
    for i, (x, y) in enumerate(LEDS_AMBER):
        n = f'la{i}'
        sk.hidden_slot(n, 'root', 'ledA', w=70, x=sk.xy(x, y)[0], y=sk.xy(x, y)[1], blend='additive')
        leds.append((n, i * 0.37))
    for i, (x, y) in enumerate(LEDS_BLUE):
        n = f'lb{i}'
        sk.hidden_slot(n, 'root', 'ledB', w=64, x=sk.xy(x, y)[0], y=sk.xy(x, y)[1], blend='additive')
        leds.append((n, i * 0.53 + 0.2))

    # chase: two comets (each a head + 5 trailing dots)
    sk.image('dot', glow_dot(128, core=0.3, col=VOLT))
    comets = []
    for c in range(2):
        parts = []
        for k in range(6):
            b = sk.bone(f'c{c}_{k}')
            sk.hidden_slot(f'c{c}_{k}', b, 'dot', w=70 - k * 8, blend='additive')
            parts.append((b, f'c{c}_{k}', k))
        comets.append(parts)

    # sweep across the frame art
    hl = highlight(frame)
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, 16)):
        r = f'sw{i}'
        sk.image(r, im)
        sk.res_of[r] = 0.6
        sk.hidden_slot(r, 'root', r, w=x1 - x0, x=sk.xy((x0 + x1) / 2, 0)[0], blend='additive')
        sweep.append((r, (x0 + x1) / 2))

    def comet(clip, c, fn_u, fn_a):
        for b, n, k in comets[c]:
            sk.anim(clip, b, 'translate', lambda t, k=k: sk.xy(*perim(fn_u(t) - k * 0.008)))
            sk.anim(clip, n, 'alpha', lambda t, k=k: fn_a(t) * (1 - k * 0.15))

    def sweep_fn(cx, t0, dur, peak, sigma=90):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-200, FR_W + 200, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f

    # idle: calm. LEDs breathe, one slow dim comet, one sweep.
    for n, ph in leds:
        sk.anim('idle', n, 'alpha', lambda t, ph=ph: 0.25 + 0.3 * (1 + math.sin(2 * math.pi * (t / 4 + ph))) / 2)
    comet('idle', 0, lambda t: t / 4, lambda t: 0.35)
    comet('idle', 1, lambda t: 0.5, lambda t: 0.0)
    sk.anim('idle', 'halo', 'alpha', lambda t: 0.12 + 0.06 * math.sin(2 * math.pi * t / 4))
    sk.anim('idle', 'edge', 'alpha', lambda t: 0.0)
    for r, cx in sweep:
        sk.anim('idle', r, 'alpha', sweep_fn(cx, 1.4, 1.2, 0.45))

    # win: LEDs blink, two fast comets, halo pulses
    for n, ph in leds:
        sk.anim('win', n, 'alpha', lambda t, ph=ph: 0.35 + 0.65 * pulse(t + ph * 0.3, 0.3, 0.0, sharp=4))
    comet('win', 0, lambda t: t / 1.2, lambda t: 1.0)
    comet('win', 1, lambda t: 0.5 + t / 1.2, lambda t: 1.0)
    sk.anim('win', 'halo', 'alpha', lambda t: 0.3 + 0.3 * pulse(t, 0.6, 0.0, 3))
    sk.anim('win', 'edge', 'alpha', lambda t: 0.25 + 0.2 * pulse(t, 0.6, 0.0, 3))
    for r, cx in sweep:
        sk.anim('win', r, 'alpha', sweep_fn(cx, 0.05, 0.8, 0.8, 110))

    # charge (Hold & Win entry): two comets run from top centre both ways and
    # meet at the bottom, the window edge fills with charge, flash.
    def ch_u(t, d):
        return 0.5 * (CHASE[2] - CHASE[0]) / (2 * ((CHASE[2] - CHASE[0]) + (CHASE[3] - CHASE[1]))) + d * 0.5 * out_cubic(clamp(t / 0.9))
    comet('charge', 0, lambda t: ch_u(t, 1), lambda t: 1.0 if t < 0.95 else seg(t, 0.95, 1.2, 1, 0))
    comet('charge', 1, lambda t: ch_u(t, -1), lambda t: 1.0 if t < 0.95 else seg(t, 0.95, 1.2, 1, 0))
    for n, ph in leds:
        sk.anim('charge', n, 'alpha', lambda t: seg(t, 0, 0.9, 0.3, 1.0))
    sk.anim('charge', 'halo', 'alpha', lambda t: seg(t, 0, 0.9, 0.15, 0.6) if t < 0.9 else (seg(t, 0.9, 1.0, 0.6, 1.0) if t < 1.0 else seg(t, 1.0, 1.4, 1.0, 0.35)))
    sk.anim('charge', 'edge', 'alpha', lambda t: seg(t, 0.4, 1.0, 0, 1.0) if t < 1.0 else seg(t, 1.0, 1.4, 1.0, 0.55))
    for r, cx in sweep:
        sk.anim('charge', r, 'alpha', sweep_fn(cx, 0.9, 0.5, 1.0, 140))

    # bonus: charged — edge steady cyan, medium comets
    for n, ph in leds:
        sk.anim('bonus', n, 'alpha', lambda t, ph=ph: 0.5 + 0.4 * (1 + math.sin(2 * math.pi * (t / 1.0 + ph))) / 2)
    comet('bonus', 0, lambda t: t / 2.0, lambda t: 0.8)
    comet('bonus', 1, lambda t: 0.5 + t / 2.0, lambda t: 0.8)
    sk.anim('bonus', 'halo', 'alpha', lambda t: 0.35 + 0.1 * math.sin(2 * math.pi * t / 2))
    sk.anim('bonus', 'edge', 'alpha', lambda t: 0.55 + 0.15 * math.sin(2 * math.pi * t / 1.0))
    for r, cx in sweep:
        sk.anim('bonus', r, 'alpha', lambda t: 0.0)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# logo (logo.png px)

LOGO_BOLT = (297, 172)  # bolt in the O, logo.png px (v2 regen, 1240x372)


def build_logo():
    logo = Image.open(os.path.join(ART, 'logo.png')).convert('RGBA')
    W, H = logo.size
    sk = Fx('logo', W, H, 1.0, {'idle': 4.0, 'win': 1.2})
    sk.image('logo', logo)
    sk.res_of['logo'] = 1.0
    halo = silhouette_halo(logo, 60, 26, CYAN, inner=0.6)
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.25
    sk.hidden_slot('halo', 'root', 'halo', w=halo.width, blend='additive')
    sk.slot('logo', 'root', 'logo', w=W)

    hl = highlight(logo, gamma=1.3, gain=1.4)
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, 18)):
        r = f'sw{i}'
        sk.image(r, im)
        sk.res_of[r] = 0.35  # soft additive sweep: resolution doesn't show
        sk.hidden_slot(r, 'root', r, w=x1 - x0, x=sk.xy((x0 + x1) / 2, 0)[0], blend='additive')
        sweep.append((r, (x0 + x1) / 2))

    bx, by = sk.xy(*LOGO_BOLT)
    bb = sk.bone('bolt', x=bx, y=by)
    sk.image('boltglow', glow_dot(256, core=0.3, col=CYAN))
    sk.hidden_slot('boltglow', bb, 'boltglow', w=290, blend='additive')
    for j in range(4):
        sk.image(f'zz{j}', bolt(256, 64, 201 + j * 5, forks=2, rough=0.9, width=3))
    zz = []
    for i, ang in enumerate((30, 150, 260, -40)):
        b = sk.bone(f'zb{i}', parent=bb, rot=ang)
        names = []
        for j in range(4):
            n = f'z{i}_{j}'
            sk.hidden_slot(n, b, f'zz{j}', 'cdf3ff', w=175, h=46, x=95, blend='additive')
            names.append(n)
        zz.append(names)

    sk.image('glint', star4(192))
    glints = []
    for gi, (x, y) in enumerate(((150, 110), (640, 105), (900, 100), (1110, 120), (520, 250))):
        b = sk.bone(f'g{gi}', x=sk.xy(x, y)[0], y=sk.xy(x, y)[1])
        sk.hidden_slot(f'g{gi}', b, 'glint', w=150, blend='additive')
        glints.append((b, f'g{gi}', gi * 0.21))

    def sweep_fn(cx, t0, dur, peak, sigma=110):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-120, W + 120, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f

    for clip, period, sw0, swd, zrate, zlv in (('idle', 4.0, 0.8, 1.0, 0.07, 0.6), ('win', 1.2, 0.05, 0.7, 0.05, 1.0)):
        sk.anim(clip, 'logo', 'alpha', lambda t: 1.0)
        for r, cx in sweep:
            sk.anim(clip, r, 'alpha', sweep_fn(cx, sw0, swd, 0.85))
        if clip == 'idle':
            sk.anim(clip, 'halo', 'alpha', lambda t: 0.18 + 0.1 * math.sin(2 * math.pi * t / 4))
            sk.anim(clip, 'boltglow', 'alpha', lambda t: 0.45 + 0.35 * pulse(t, 2.0, 0.1, 6))
            # the bolt in the O crackles twice per loop
            for i, names in enumerate(zz):
                for j, n in enumerate(names):
                    sk.anim(clip, n, 'alpha', lambda t, i=i, j=j: flicker(t + i * 0.03, (j + i) % 4, rate=zrate) * zlv
                            if (2.6 < t < 2.95 or 3.25 < t < 3.45) else 0.0)
        else:
            sk.anim(clip, 'halo', 'alpha', lambda t: 0.35 + 0.35 * pulse(t, 0.6, 0.0, 3))
            sk.anim(clip, 'boltglow', 'alpha', lambda t: 0.6 + 0.4 * pulse(t, 0.3, 0.0, 4))
            for i, names in enumerate(zz):
                for j, n in enumerate(names):
                    sk.anim(clip, n, 'alpha', lambda t, i=i, j=j: flicker(t + i * 0.03, (j + i) % 4, rate=zrate) * zlv)
        sk.anim(clip, bb, 'scale', lambda t, p=period: (1 + 0.08 * math.sin(2 * math.pi * t / (p / 2)),) * 2)
        for b, n, ph in glints:
            sk.anim(clip, n, 'alpha', lambda t, ph=ph, p=period: pulse(t, p / 2, ph, 10))
            sk.anim(clip, b, 'scale', lambda t, ph=ph, p=period: (0.3 + 0.9 * pulse(t, p / 2, ph, 6),) * 2)
            sk.anim(clip, b, 'rotate', lambda t, p=period: 90 * t / p)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# win lines (reel-window px 766x604)

RW, RH = 766, 604
COL_X = [(c + 0.5) * RW / 3 - RW / 2 for c in range(3)]
ROW_Y = [RH / 2 - (r + 0.5) * RH / 3 for r in range(3)]
CELL_W, CELL_H = RW / 3, RH / 3
PAYLINES = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]]
LINE_COLS = ['59dcff', 'ffcf3a', 'ff5fd2', 'a77bff', '4dffaa']


def build_winlines():
    IN, LOOP = 0.7, 1.2
    clips = {}
    for n in range(1, 6):
        clips[f'line{n}_in'] = IN
        clips[f'line{n}_loop'] = LOOP
    sk = Fx('winlines', RW, RH, 1.0, clips)
    sk.image('bglow', hband(512, 128, sigma=0.26, taper=0.04))
    sk.res_of['bglow'] = 0.5
    sk.image('bcore', hband(512, 32, sigma=0.22, taper=0.02))
    sk.res_of['bcore'] = 0.5
    for j in range(3):
        sk.image(f'bolt{j}', bolt(1024, 96, j * 11 + 3))
        sk.res_of[f'bolt{j}'] = 0.8
    sk.image('head', glow_dot(256, core=0.22, col=(255, 255, 255)))
    sk.image('comet', edge_fade(spark(256, 40), 0.08, 0.2))
    sk.image('ring', ring(256))
    sk.image('flare', star4(256, thin=0.025))
    fw, fh = int(CELL_W * 0.94), int(CELL_H * 0.92)
    cfr, cpad = rect_line(fw, fh, 5, 8, r=14)
    sk.image('cframe', cfr)
    sk.image('cglow', soft_glow(256))
    sk.res_of['cglow'] = 0.4

    for n, rows in enumerate(PAYLINES, start=1):
        col = LINE_COLS[n - 1]
        pts = [(COL_X[c], ROW_Y[r]) for c, r in enumerate(rows)]
        (x0, y0), (x2, y2) = pts[0], pts[2]
        ang = math.atan2(y2 - y0, x2 - x0)
        ux, uy = math.cos(ang), math.sin(ang)
        ext = CELL_W * 0.45
        sx, sy = x0 - ux * ext, y0 - uy * ext
        ex, ey = x2 + ux * ext, y2 + uy * ext
        L = math.hypot(ex - sx, ey - sy)
        cell_u = [math.hypot(px - sx, py - sy) / L for px, py in pts]

        P = f'L{n}'
        beam = sk.bone(f'{P}beam', x=sx, y=sy, rot=math.degrees(ang))
        sk.hidden_slot(f'{P}glow', beam, 'bglow', col, w=L, h=110, x=L / 2, blend='additive')
        for j in range(3):
            sk.hidden_slot(f'{P}bolt{j}', beam, f'bolt{j}', col, w=L, h=90, x=L / 2, blend='additive')
        sk.hidden_slot(f'{P}core', beam, 'bcore', w=L, h=18, x=L / 2, blend='additive')

        cells = []
        for ci, (px, py) in enumerate(pts):
            C = f'{P}c{ci}'
            cb = sk.bone(C, x=px, y=py)
            sk.hidden_slot(f'{C}glow', cb, 'cglow', col, w=CELL_W * 1.2, h=CELL_H * 1.3, blend='additive')
            fb = sk.bone(f'{C}f', parent=cb)
            sk.hidden_slot(f'{C}frame', fb, 'cframe', col, w=cfr.width, blend='additive')
            rb = sk.bone(f'{C}r', parent=cb)
            sk.hidden_slot(f'{C}ring', rb, 'ring', col, w=CELL_H * 1.1, blend='additive')
            flb = sk.bone(f'{C}fl', parent=cb)
            sk.hidden_slot(f'{C}flare', flb, 'flare', w=CELL_H * 1.1, blend='additive')
            cells.append((C, cb, fb, rb, flb))

        hb = sk.bone(f'{P}head', x=sx, y=sy)
        sk.hidden_slot(f'{P}head', hb, 'head', w=140, blend='additive')
        heads = []
        for k in range(2):
            cbn = sk.bone(f'{P}comet{k}', x=sx, y=sy, rot=math.degrees(ang))
            sk.hidden_slot(f'{P}comet{k}', cbn, 'comet', w=160, h=32, blend='additive')
            heads.append(cbn)

        INN, LP = f'line{n}_in', f'line{n}_loop'
        DRAW = 0.32

        def tip(t):
            return out_cubic(clamp(t / DRAW)) if t < DRAW else 1.0

        def at(u):
            lo, hi = 0.0, DRAW
            for _ in range(30):
                mid = (lo + hi) / 2
                if tip(mid) < u:
                    lo = mid
                else:
                    hi = mid
            return hi

        def g_loop(t):
            return 0.7 + 0.2 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2

        sk.anim(INN, beam, 'scale', lambda t: (max(0.001, tip(t)), 1.25 - 0.25 * clamp(t / 0.5)))
        sk.anim(LP, beam, 'scale', lambda t: (1.0, 1 + 0.18 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2))
        sk.anim(INN, f'{P}glow', 'alpha', lambda t: seg(t, 0, 0.12, 0, 1) if t < 0.4 else seg(t, 0.4, IN, 1, g_loop(0)))
        sk.anim(LP, f'{P}glow', 'alpha', g_loop)
        sk.anim(INN, f'{P}core', 'alpha', lambda t: seg(t, 0, 0.08, 0, 1))
        sk.anim(LP, f'{P}core', 'alpha', lambda t: 0.85 + 0.15 * math.cos(2 * math.pi * t / 0.3))
        for j in range(3):
            sk.anim(INN, f'{P}bolt{j}', 'alpha', lambda t, j=j: (1.0 if int(t / 0.1) % 3 == j else 0.2) * clamp((t - 0.15) / 0.2) if t > 0.15 else 0.0)
            sk.anim(LP, f'{P}bolt{j}', 'alpha', lambda t, j=j: 1.0 if int(t / 0.1 + 0.001) % 3 == j else 0.2)

        sk.anim(INN, hb, 'translate', lambda t: (sx + (ex - sx) * tip(t), sy + (ey - sy) * tip(t)))
        sk.anim(INN, f'{P}head', 'alpha', lambda t: seg(t, 0, 0.05, 0, 1) if t < DRAW else seg(t, DRAW, DRAW + 0.2, 1, 0))
        sk.anim(LP, hb, 'translate', lambda t: (ex, ey))
        sk.anim(LP, f'{P}head', 'alpha', lambda t: 0.0)
        for k, cbn in enumerate(heads):
            def cpos(t, k=k):
                p = frac(t / 0.6 + k * 0.5)
                return (sx + (ex - sx) * p, sy + (ey - sy) * p)

            def calpha(t, k=k):
                p = frac(t / 0.6 + k * 0.5)
                return clamp(min(p, 1 - p) / 0.12)
            sk.anim(INN, cbn, 'translate', lambda t: (sx, sy))
            sk.anim(INN, f'{P}comet{k}', 'alpha', lambda t: 0.0)
            sk.anim(LP, cbn, 'translate', cpos)
            sk.anim(LP, f'{P}comet{k}', 'alpha', calpha)

        for ci, (C, cb, fb, rb, flb) in enumerate(cells):
            tk = at(cell_u[ci])

            def fr_loop(t):
                return 0.75 + 0.25 * math.cos(2 * math.pi * t / 0.6)
            sk.anim(INN, f'{C}glow', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.1, 0, 0.8) if t < tk + 0.2 else seg(t, tk + 0.2, IN, 0.8, 0.3))
            sk.anim(LP, f'{C}glow', 'alpha', lambda t: 0.3 + 0.15 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2)
            sk.anim(INN, f'{C}frame', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.12, 0, 1) if t < tk + 0.12 else seg(t, tk + 0.12, IN, 1, fr_loop(0)))
            sk.anim(LP, f'{C}frame', 'alpha', fr_loop)
            sk.anim(INN, fb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.3, 1.15, 1.0),) * 2)
            sk.anim(LP, fb, 'scale', lambda t: (1 + 0.02 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2,) * 2)
            sk.anim(INN, f'{C}ring', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.42, 1, 0))
            sk.anim(INN, rb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.42, 0.25, 1.6),) * 2)
            sk.anim(LP, f'{C}ring', 'alpha', lambda t: seg(t % 0.6, 0, 0.6, 0.5, 0, lin))
            sk.anim(LP, rb, 'scale', lambda t: (seg(t % 0.6, 0, 0.6, 0.5, 1.4, out_cubic),) * 2)
            sk.anim(INN, f'{C}flare', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.05, 0, 1) if t < tk + 0.15 else seg(t, tk + 0.15, IN, 1, 0.5))
            sk.anim(INN, flb, 'scale', lambda t, tk=tk: (0.01 if t < tk else (seg(t, tk, tk + 0.18, 0.1, 1.5, out_back) if t < tk + 0.18 else seg(t, tk + 0.18, IN, 1.5, 0.75)),) * 2)
            sk.anim(LP, f'{C}flare', 'alpha', lambda t: 0.5 + 0.25 * math.cos(2 * math.pi * t / 0.6))
            sk.anim(LP, flb, 'scale', lambda t: (0.75 + 0.1 * math.cos(2 * math.pi * t / 0.6),) * 2)
            sk.anim(LP, flb, 'rotate', lambda t: -90 * t / LOOP)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# symbols (one cell = the 320x254 symbol canvas)

SW, SH = 320, 254
SYMBOLS = {
    # code: (glow colour, motion, electric arcs round it)
    'horseshoe': ((200, 220, 255), 'swing', False),
    'star': ((230, 90, 255), 'spin', False),
    'bar': ((90, 170, 255), 'stretch', False),
    'bell': ((255, 190, 90), 'swing', False),
    'ingot': ((255, 200, 80), 'hop', False),
    'diamond': ((90, 230, 255), 'jiggle', False),
    'seven': ((255, 70, 60), 'slam', False),
    'wild': ((90, 190, 255), 'slam', True),
    'coin': ((110, 200, 255), 'zap', True),
}
# Монеты с номиналом (раунд / база с лицом): своя копия с запечённым номиналом
# (volt_coins_face.py = вёрстка slot.js), иначе Spine нарисовал бы пустую монету.
# slot.js играет 'coin_<key>': coin_x5, coin_mini ...
sys.path.insert(0, os.path.dirname(__file__))
from volt_coins_face import FACES, css_glow, faced_coin  # noqa: E402
for _k in FACES:
    SYMBOLS[f'coin_{_k}'] = ((110, 200, 255), 'zap', True)
COIN_SCALE = 1.1  # .reel__cell.is-coin img { scale: 1.1 }
SYM_DUR = 1.1


def sym_motion(kind, t):
    """(sx, sy, rot, dy) of the symbol bone at time t; rest = (1, 1, 0, 0)."""
    def settle(t0, amp, freq=15, damp=7):
        u = t - t0
        return amp * math.exp(-damp * u) * math.cos(freq * u) if u > 0 else amp
    if kind == 'hop':
        if t < 0.08:
            k = out_cubic(t / 0.08)
            return 1 + 0.12 * k, 1 - 0.14 * k, 0, -8 * k
        if t < 0.34:
            u = (t - 0.08) / 0.26
            h = math.sin(math.pi * u)
            return 1.12 + 0.08 * h - 0.12 * u, 1.14 * h + (1 - h) * 0.95, 5 * math.sin(2 * math.pi * u), 30 * h
        if t < 0.42:
            k = math.sin(math.pi * (t - 0.34) / 0.08)
            return 1.08 + 0.1 * k, 1.08 - 0.18 * k, 0, -4 * k
        e = settle(0.42, 0.08)
        return 1 + e, 1 + e, 0, 0
    if kind == 'jiggle':
        if t < 0.1:
            k = out_cubic(t / 0.1)
            return 1 + 0.2 * k, 1 + 0.2 * k, 0, 0
        u = t - 0.1
        w = 0.2 * math.exp(-4.5 * u)
        return 1 + w + 0.08 * math.exp(-4 * u) * math.sin(26 * u), 1 + w - 0.08 * math.exp(-4 * u) * math.sin(26 * u), 0, 0
    if kind == 'swing':
        s = 1 + 0.18 * (out_cubic(clamp(t / 0.1)) if t < 0.1 else math.exp(-5 * (t - 0.1)))
        return s, s, 20 * math.exp(-3.6 * t) * math.sin(13 * t), 0
    if kind == 'spin':
        s = 1 + 0.3 * math.sin(math.pi * clamp(t / 0.5))
        return s, s, -360 * out_cubic(clamp(t / 0.55)), 8 * math.sin(math.pi * clamp(t / 0.5))
    if kind == 'stretch':
        if t < 0.12:
            k = out_cubic(t / 0.12)
            return 1 + 0.25 * k, 1 + 0.06 * k, 0, 0
        e = math.exp(-6 * (t - 0.12)) * math.cos(16 * (t - 0.12))
        return 1 + 0.25 * e, 1 + 0.06 * e, 0, 0
    if kind == 'slam':
        if t < 0.1:
            k = out_cubic(t / 0.1)
            return 1 + 0.35 * k, 1 + 0.35 * k, 0, 0
        if t < 0.18:
            k = (t - 0.1) / 0.08
            return 1.35 - 0.45 * k, 1.35 - 0.55 * k, 0, 0
        e = settle(0.18, 0.13, 18, 5.5)
        shake = 4 * math.exp(-6 * (t - 0.18)) * math.sin(70 * t)
        base = 1 + 0.1 - 0.1 * clamp((t - 0.18) / 0.5)
        return base + e, base + e, shake, 0
    if kind == 'zap':
        # бодро, без поворота (номинал не качаем): присел -> прыжок с ростом ->
        # удар-приземление -> подскок -> пружинка в покой (последний кадр = статика)
        if t < 0.07:
            k = out_cubic(t / 0.07)
            return 1 + 0.1 * k, 1 - 0.12 * k, 0, -5 * k
        if t < 0.32:
            u = (t - 0.07) / 0.25
            h = math.sin(math.pi * u)
            s = 1 + 0.3 * h
            return s * (1.1 - 0.1 * u) - 0.04 * h, s * (0.88 + 0.12 * u) + 0.06 * h, 0, -5 * (1 - u) + 40 * h
        if t < 0.42:
            k = math.sin(math.pi * (t - 0.32) / 0.1)
            return 1 + 0.24 * k, 1 - 0.18 * k, 0, 0
        if t < 0.6:
            h = math.sin(math.pi * (t - 0.42) / 0.18)
            return 1 + 0.06 * h, 1 + 0.08 * h, 0, 12 * h
        u = t - 0.6
        e = 0.07 * math.exp(-7 * u) * math.sin(22 * u)
        return 1 + e, 1 - e, 0, 0
    if kind == 'flip':
        # the coin turns over twice on its vertical axis, rising a little
        u = in_out_sine(clamp(t / 0.8))
        s = 1 + 0.15 * math.sin(math.pi * u)
        return s * math.cos(2 * math.pi * 2 * u), s, 0, 14 * math.sin(math.pi * u)
    return 1, 1, 0, 0


def build_symbols():
    sk = Fx('symbols', SW, SH, 1.0, {code: SYM_DUR for code in SYMBOLS})
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.5
    sk.image('rays', rays(512, n=14))
    sk.res_of['rays'] = 0.6
    sk.image('ring', ring(256))
    sk.image('spark', star4(128))
    sk.image('dot', glow_dot(64, core=0.3, col=(230, 245, 255)))
    for j in range(4):
        sk.image(f'zz{j}', bolt(256, 64, 301 + j * 9, forks=2, rough=0.9, width=3))
    rnd = random.Random(21)
    for code, (col, kind, electric) in SYMBOLS.items():
        # монеты: как в DOM — CSS-свечение запечено (иначе первый/последний
        # кадр расходятся со статикой); база показывает пустую эмаль coin_value
        if code.startswith('coin_'):
            im = faced_coin(code[5:], SYM, glow=True)
        elif code == 'coin':
            im = css_glow(Image.open(os.path.join(SYM, 'coin_value.png')).convert('RGBA'))
        else:
            im = Image.open(os.path.join(SYM, f'{code}.png')).convert('RGBA')
        w, h = SW, SH
        if kind == 'zap':
            w, h = SW * COIN_SCALE, SH * COIN_SCALE
        hexcol = '%02x%02x%02x' % col
        sk.image(code, im)
        sk.res_of[code] = 1.5  # v2 symbol PNGs are 1.5x the cell units (как DOM — та же резкость)
        flash = Image.new('RGBA', im.size, (255, 255, 255, 0))
        flash.putalpha(im.getchannel('A'))
        sk.image(f'{code}_flash', flash)
        sk.res_of[f'{code}_flash'] = 0.35

        C = code
        fxb = sk.bone(f'{C}_fx')
        sk.hidden_slot(f'{C}_halo', fxb, 'halo', hexcol, w=SW * 1.2, h=SH * 1.5, blend='additive')
        sk.hidden_slot(f'{C}_rays', fxb, 'rays', hexcol, w=SH * 2.0, blend='additive')
        rb = sk.bone(f'{C}_rb')
        sk.hidden_slot(f'{C}_ring', rb, 'ring', 'e8f8ff', w=SH * 1.0, blend='additive')
        piv = h * 0.38 if kind == 'swing' else 0
        sb = sk.bone(f'{C}_sym', y=piv)
        sk.hidden_slot(f'{C}_img', sb, code, w=w, y=-piv)
        hl = highlight(im, gamma=1.2, gain=1.5)
        sweep = []
        kpx = w / im.width  # image px -> skeleton units (раньше блик был в px и ехал в 1.5 раза шире символа)
        for i, (sim, x0, x1) in enumerate(strips(hl, 14)):
            r = f'{C}_sw{i}'
            sk.image(r, sim)
            sk.res_of[r] = 0.4
            sk.hidden_slot(r, sb, r, w=(x1 - x0) * kpx, x=((x0 + x1) / 2 - im.width / 2) * kpx, y=-piv, blend='additive')
            sweep.append((r, (x0 + x1) / 2 * kpx))
        sk.hidden_slot(f'{C}_flash', sb, f'{C}_flash', w=w, y=-piv, blend='additive')
        sparks = []
        for i in range(7):
            a = 2 * math.pi * i / 7 + rnd.uniform(-0.3, 0.3)
            b = sk.bone(f'{C}_sp{i}')
            sk.hidden_slot(f'{C}_sp{i}', b, 'spark' if i % 2 == 0 else 'dot', 'ffffff', w=rnd.uniform(30, 50), blend='additive')
            sparks.append((b, f'{C}_sp{i}', a, rnd.uniform(0.75, 1.1), rnd.uniform(0, 0.08)))
        zz = []
        if electric:
            for i, ang in enumerate((20, 100, 200, 290)):
                b = sk.bone(f'{C}_zb{i}', x=math.cos(math.radians(ang)) * SH * 0.3,
                            y=math.sin(math.radians(ang)) * SH * 0.3, rot=ang)
                names = []
                for j in range(4):
                    n = f'{C}_z{i}_{j}'
                    sk.hidden_slot(n, b, f'zz{j}', 'bfeaff', w=110, h=28, x=45, blend='additive')
                    names.append(n)
                zz.append(names)

        sk.anim(C, f'{C}_img', 'alpha', lambda t: 1.0)
        sk.anim(C, sb, 'scale', lambda t, kind=kind: sym_motion(kind, t)[:2])
        sk.anim(C, sb, 'rotate', lambda t, kind=kind: sym_motion(kind, t)[2])
        sk.anim(C, sb, 'translate', lambda t, kind=kind, piv=piv: (0, piv + sym_motion(kind, t)[3]))
        sk.anim(C, f'{C}_flash', 'alpha', lambda t: seg(t, 0, 0.06, 0, 0.8) if t < 0.06 else 0.8 * math.exp(-11 * (t - 0.06)))
        for r, cx in sweep:
            sk.anim(C, r, 'alpha', lambda t, cx=cx: 0.0 if not 0.12 <= t <= 0.62 else
                    0.85 * math.exp(-((cx - lerp(-60, w + 60, in_out_sine((t - 0.12) / 0.5))) / 60) ** 2))
        big = 1.25 if kind in ('slam', 'zap') else 1.0
        sk.anim(C, f'{C}_halo', 'alpha', lambda t, big=big: seg(t, 0, 0.1, 0, 0.8 * big) if t < 0.1 else seg(t, 0.1, SYM_DUR, 0.8 * big, 0, in_out_sine))
        sk.anim(C, fxb, 'scale', lambda t: (seg(t, 0, 0.2, 0.5, 1.1, out_back) if t < 0.2 else seg(t, 0.2, SYM_DUR, 1.1, 0.9),) * 2)
        sk.anim(C, f'{C}_rays', 'alpha', lambda t, big=big: seg(t, 0, 0.12, 0, 0.6 * big) if t < 0.12 else seg(t, 0.12, SYM_DUR, 0.6 * big, 0, in_out_sine))
        sk.anim(C, fxb, 'rotate', lambda t: -50 * t / SYM_DUR)
        t0 = 0.18 if kind == 'slam' else 0.33 if kind == 'zap' else 0.04
        sk.anim(C, f'{C}_ring', 'alpha', lambda t, t0=t0: 0.0 if t < t0 else seg(t, t0, t0 + 0.45, 1, 0))
        sk.anim(C, rb, 'scale', lambda t, t0=t0, big=big: (seg(t, t0, t0 + 0.45, 0.3, 1.8 * big),) * 2)
        for b, sl, a, dist, delay in sparks:
            def sp_pos(t, a=a, dist=dist, delay=delay):
                u = clamp((t - 0.05 - delay) / 0.7)
                d = SH * 0.33 + SH * 0.42 * dist * out_cubic(u)
                spin = a + 1.2 * u
                return (math.cos(spin) * d * 1.3, math.sin(spin) * d)
            sk.anim(C, b, 'translate', sp_pos)
            sk.anim(C, sl, 'alpha', lambda t, delay=delay: 0.0 if t < 0.05 + delay else seg(t, 0.05 + delay, 0.85 + delay, 1, 0, in_cubic))
            sk.anim(C, b, 'scale', lambda t, delay=delay: (0.4 + 0.9 * pulse(t - delay, 0.35, 0.0, 2),) * 2)
            sk.anim(C, b, 'rotate', lambda t: 180 * t)
        for i, names in enumerate(zz):
            for j, n in enumerate(names):
                sk.anim(C, n, 'alpha', lambda t, i=i, j=j: flicker(t + i * 0.02, (i + j) % 4, rate=0.05)
                        * (1.0 if t < 0.7 else seg(t, 0.7, SYM_DUR, 1, 0)) if t > 0.06 else 0.0)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# software preview (layout/timing check only)

def render(sk, clip, t, size, under=None):
    data = sk.data
    W, H = size
    sc = W / sk.w
    canvas = Image.new('RGBA', size, (6, 8, 30, 255))
    if under is not None:
        canvas.alpha_composite(under.convert('RGBA').resize(size))
    anim = data['animations'][clip]

    def sample(rows, key, default):
        if not rows:
            return default
        prev = rows[0]
        for r in rows:
            if r.get('time', 0) > t:
                t0, t1 = prev.get('time', 0), r.get('time', 0)
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return tuple(lerp(prev[k], r[k], f) for k in key)
            prev = r
        return tuple(prev[k] for k in key)

    world = {}
    for b in data['bones']:
        bt = anim['bones'].get(b['name'], {})
        tx, ty = sample(bt.get('translate'), ('x', 'y'), (0, 0))
        rot = b.get('rotation', 0) + sample(bt.get('rotate'), ('value',), (0,))[0]
        sx, sy = sample(bt.get('scale'), ('x', 'y'), (1, 1))
        x, y = b.get('x', 0) + tx, b.get('y', 0) + ty
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        m = (c * sx, -s * sy, x, s * sx, c * sy, y)
        if 'parent' in b:
            p = world[b['parent']]
            m = (p[0] * m[0] + p[1] * m[3], p[0] * m[1] + p[1] * m[4], p[0] * m[2] + p[1] * m[5] + p[2],
                 p[3] * m[0] + p[4] * m[3], p[3] * m[1] + p[4] * m[4], p[3] * m[2] + p[4] * m[5] + p[5])
        world[b['name']] = m
    for s in data['slots']:
        st = anim['slots'].get(s['name'], {})
        col = s.get('color', 'ffffffff')
        a = sample(st.get('alpha'), ('value',), (int(col[6:8], 16) / 255,))[0]
        if a <= 0.01:
            continue
        reg = s['attachment']
        att = data['skins'][0]['attachments'][s['name']][reg]
        im = sk.images[reg]
        tintc = tuple(int(col[i:i + 2], 16) for i in (0, 2, 4))
        m = world[s['bone']]
        aw, ah = att['width'], att['height']
        kx, ky = aw / im.width, -ah / im.height
        lx0, ly0 = -aw / 2, ah / 2
        A = (kx, 0, lx0 + att['x'], 0, ky, ly0 + att['y'])
        Mw = (m[0] * A[0] + m[1] * A[3], m[0] * A[1] + m[1] * A[4], m[0] * A[2] + m[1] * A[5] + m[2],
              m[3] * A[0] + m[4] * A[3], m[3] * A[1] + m[4] * A[4], m[3] * A[2] + m[4] * A[5] + m[5])
        Cm = (sc * Mw[0], sc * Mw[1], sc * Mw[2] + W / 2, -sc * Mw[3], -sc * Mw[4], -sc * Mw[5] + H / 2)
        det = Cm[0] * Cm[4] - Cm[1] * Cm[3]
        if abs(det) < 1e-9:
            continue
        inv = (Cm[4] / det, -Cm[1] / det, (Cm[1] * Cm[5] - Cm[4] * Cm[2]) / det,
               -Cm[3] / det, Cm[0] / det, (Cm[3] * Cm[2] - Cm[0] * Cm[5]) / det)
        layer = im.transform(size, Image.AFFINE, inv, Image.BILINEAR)
        r, g, b_, al = layer.split()
        if tintc != (255, 255, 255):
            r = r.point(lambda v, k=tintc[0]: v * k // 255)
            g = g.point(lambda v, k=tintc[1]: v * k // 255)
            b_ = b_.point(lambda v, k=tintc[2]: v * k // 255)
        al = al.point(lambda v, a=a: int(v * a))
        layer = Image.merge('RGBA', (r, g, b_, al))
        if s.get('blend') == 'additive':
            canvas = ImageChops.add(canvas.convert('RGB'), premultiply(layer).convert('RGB')).convert('RGBA')
        else:
            canvas.alpha_composite(layer)
    return canvas


def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
        os.makedirs(preview, exist_ok=True)
    only = [a for a in sys.argv[1:] if not a.startswith('--') and a != preview]
    builders = {
        'arc': build_arc, 'coil': build_coil, 'bg_desk': lambda: build_door('bg_desk'),
        'bg_mob': lambda: build_door('bg_mob'), 'frame': build_frame, 'logo': build_logo,
        'winlines': build_winlines, 'symbols': build_symbols,
    }
    built = {k: f() for k, f in builders.items() if not only or k in only}
    if not preview:
        return
    unders = {
        'coil': Image.open(os.path.join(ART, 'coil.png')),
        'frame': Image.open(os.path.join(ART, 'frame.png')),
        'bg_desk': Image.open(os.path.join(ART, 'bg_desk.jpg')),
        'bg_mob': Image.open(os.path.join(ART, 'bg_mob.jpg')),
    }
    for name, sk in built.items():
        for clip, dur in sk.durs.items():
            if name == 'winlines' and not clip.startswith(('line1', 'line4')):
                continue
            if name == 'symbols' and clip not in ('coin', 'wild', 'bell', 'seven'):
                continue
            pw = 600 if sk.w >= sk.h else 360
            ph = int(pw * sk.h / sk.w)
            frames = [render(sk, clip, dur * k / 6, (pw, ph), under=unders.get(name)) for k in range(6)]
            sheet = Image.new('RGB', (pw * 3, ph * 2))
            for k, f in enumerate(frames):
                sheet.paste(f.convert('RGB'), ((k % 3) * pw, (k // 3) * ph))
            sheet.save(os.path.join(preview, f'{name}_{clip}.jpg'), quality=80)


if __name__ == '__main__':
    main()
