"""Ice Spin Deluxe: in-game Spine FX generated in code (spine_screen_kit).

Five skeletons into front/img/ice-spin-deluxe/fx/:

  bg_desk / bg_mob  behind the stage: aurora ribbons, casino searchlights,
                    snowfall, twinkles, bokeh. Clip `idle` (8s loop).
  frame             over cabinet.png (authored in its pixel space): chasing
                    marquee bulbs round the three windows, outer ice halo, a
                    light sweep masked by the frame's own highlights, glints on
                    the crystals. Clips `idle` (4s) and `win` (1.2s).
  logo              the logo itself plus shadow, halo, sweep, glints, rays.
                    Clips `idle` (4s) and `win` (1.2s).
  winlines          the five paylines, each its own colour: beam drawn in from
                    the left, lightning, comets, a burst + glowing frame on each
                    cell. Clips `line{n}_in` (0.7s) and `line{n}_loop` (1.2s).

Every slot that an animation touches starts transparent in the setup pose, so a
fresh instance shows nothing until a clip is played.

    python3 scripts/ice_spin_deluxe_fx.py [--preview DIR]
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from spine_screen_kit import (  # noqa: E402
    FPS, Skel, clamp, hexc, in_out_sine, lerp, out_back, out_cubic, pack, premultiply,
    pulse, rays, seg, soft_glow, spark, trim, wave,
)
import json  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'ice-spin-deluxe')
ART = os.path.join(ROOT, 'img')
OUT = os.path.join(ROOT, 'fx')

ICE = (127, 224, 255)
VIOLET = (170, 120, 255)


def frac(x):
    return x - math.floor(x)


# --------------------------------------------------------------------------
# kit extension: named clips of any length, optional quantisation

class Fx(Skel):
    def __init__(self, name, w, h, res, clips, quantize=False):
        super().__init__(name, w, h, res, OUT)
        self.durs = dict(clips)
        self.anims = {k: {'bones': {}, 'slots': {}} for k in clips}
        self.quantize = quantize

    def anim(self, which, target, prop, fn):
        self.idle = self.durs[which]
        super().anim(which, target, prop, fn)

    def hidden_slot(self, name, bone, region, color='ffffff', **kw):
        return self.slot(name, bone, region, color=color + '00', **kw)

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
            page = premultiply(page)
            if self.quantize:
                page = page.quantize(256, Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
            page.save(os.path.join(out, fname), optimize=True)
            atlas += [fname, f'size:{page.width},{page.height}', 'filter:Linear,Linear', 'pma:true']
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

def tint(im, rgb):
    out = Image.new('RGBA', im.size, rgb + (0,))
    out.putalpha(im.getchannel('A'))
    return out


def glow_dot(size, core=0.18, col=ICE):
    """Soft coloured halo with a hot white core (a casino bulb / snow dot)."""
    halo = tint(soft_glow(size), col)
    c = int(size * core)
    hot = soft_glow(c * 2).resize((c * 2, c * 2))
    out = halo.copy()
    out.alpha_composite(hot, ((size - 2 * c) // 2, (size - 2 * c) // 2))
    return out


def star4(size, col=(255, 255, 255), thin=0.035, glow=True):
    """Four-point lens flare: two long thin streaks + a round core."""
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    c = big / 2
    t = big * thin
    for horiz in (True, False):
        pts = ([(0, c), (c, c - t), (big, c), (c, c + t)] if horiz
               else [(c, 0), (c + t, c), (c, big), (c - t, c)])
        d.polygon(pts, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(big / 160)).resize((size, size), Image.LANCZOS)
    if glow:
        g = soft_glow(size).getchannel('A').point(lambda v: int(v * 0.85))
        hot = soft_glow(size // 3).getchannel('A')
        core = Image.new('L', (size, size))
        core.paste(hot, (size // 3, size // 3))
        m = ImageChops.lighter(ImageChops.lighter(m, g.point(lambda v: v // 3)), core)
    out = Image.new('RGBA', (size, size), col + (0,))
    out.putalpha(m)
    return out


def ring(size, thick=0.07, col=(255, 255, 255)):
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    pad = big * 0.12
    d.ellipse([pad, pad, big - pad, big - pad], outline=255, width=int(big * thick))
    m = m.filter(ImageFilter.GaussianBlur(big * 0.02)).resize((size, size), Image.LANCZOS)
    m2 = m.filter(ImageFilter.GaussianBlur(size * 0.04))
    m = ImageChops.lighter(m, m2.point(lambda v: min(255, v * 2)))
    out = Image.new('RGBA', (size, size), col + (0,))
    out.putalpha(m)
    return out


def hband(w, h, sigma=0.22, taper=0.06, core_white=0.0, col=(255, 255, 255)):
    """Horizontal beam: gaussian across, tapered at both ends."""
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


def bolt(w, h, seed):
    rnd = random.Random(seed)
    sc = 2
    m = Image.new('L', (w * sc, h * sc))
    d = ImageDraw.Draw(m)
    n = 34
    pts = []
    y = 0.0
    for i in range(n + 1):
        y = clamp(y + rnd.uniform(-0.55, 0.55), -1, 1) * 0.85
        taper = math.sin(math.pi * i / n) ** 0.5
        pts.append((i / n * w * sc, h * sc / 2 + y * h * sc * 0.36 * taper))
    d.line(pts, fill=255, width=5 * sc, joint='curve')
    for _ in range(5):  # side forks
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
    return out


def rrect_frame(w, h, r, line, blur):
    pad = int(blur * 3)
    m = Image.new('L', (w + 2 * pad, h + 2 * pad))
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, pad + w, pad + h], r, outline=255, width=line)
    g = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, v * 3))
    a = ImageChops.lighter(m, g)
    out = Image.new('RGBA', m.size, (255, 255, 255, 0))
    out.putalpha(a)
    return out


def shard(w=36, h=80):
    m = Image.new('RGBA', (w * 2, h * 2))
    d = ImageDraw.Draw(m)
    d.polygon([(w, 0), (w * 2 - 2, h), (w, h * 2 - 1), (2, h)], fill=(220, 245, 255, 255))
    d.polygon([(w, 0), (w * 2 - 2, h), (w, h)], fill=(255, 255, 255, 255))
    m = m.resize((w, h), Image.LANCZOS)
    g = m.getchannel('A').filter(ImageFilter.GaussianBlur(3))
    out = Image.new('RGBA', (w + 16, h + 16), ICE + (0,))
    out.putalpha(Image.new('L', out.size))
    halo = Image.new('RGBA', out.size, ICE + (0,))
    ga = Image.new('L', out.size)
    ga.paste(g, (8, 8))
    halo.putalpha(ga)
    out.alpha_composite(halo)
    out.alpha_composite(m, (8, 8))
    return out


def crystal(size):
    """Six-armed snow crystal."""
    big = size * 4
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    c = big / 2
    for k in range(6):
        a = math.pi / 3 * k
        ex, ey = c + math.cos(a) * c * 0.92, c + math.sin(a) * c * 0.92
        d.line([(c, c), (ex, ey)], fill=255, width=big // 18)
        for f in (0.45, 0.68):
            bx, by = c + math.cos(a) * c * f, c + math.sin(a) * c * f
            for s in (-1, 1):
                b = a + s * math.pi / 4
                d.line([(bx, by), (bx + math.cos(b) * c * 0.22, by + math.sin(b) * c * 0.22)],
                       fill=255, width=big // 26)
    m = m.resize((size, size), Image.LANCZOS)
    g = m.filter(ImageFilter.GaussianBlur(size / 14))
    a = ImageChops.lighter(m, g.point(lambda v: min(255, v * 2)))
    out = Image.new('RGBA', (size, size), (235, 250, 255, 0))
    out.putalpha(a)
    return out


def ribbon(w, h, seed, c0, c1):
    """Aurora curtain: wavy band, colour sliding along x, vertical streaks."""
    rnd = random.Random(seed)
    a = Image.new('L', (w, h))
    px = a.load()
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    for x in range(w):
        u = x / w
        yc = h * (0.5 + 0.18 * math.sin(6.28 * (u * 1.3) + ph[0]) + 0.08 * math.sin(6.28 * u * 3.1 + ph[1]))
        th = h * (0.13 + 0.07 * math.sin(6.28 * u * 2.2 + ph[2]))
        streak = 0.65 + 0.35 * math.sin(u * 140 + ph[1]) * math.sin(u * 37)
        edge = clamp(min(u, 1 - u) / 0.18) ** 1.5
        for y in range(h):
            dy = (y - yc) / th
            # curtain: sharp lower edge, long fade upward
            v = math.exp(-dy * dy * 2.5) if dy > 0 else math.exp(-dy * dy * 0.35)
            px[x, y] = int(255 * v * streak * edge)
    fade = Image.new('L', (1, h))
    for y in range(h):
        fade.putpixel((0, y), int(255 * math.sin(math.pi * y / (h - 1)) ** 0.8))
    a = ImageChops.multiply(a.filter(ImageFilter.GaussianBlur(3)), fade.resize((w, h)))
    grad = Image.new('RGBA', (w, 1))
    for x in range(w):
        grad.putpixel((x, 0), tuple(int(lerp(c0[j], c1[j], x / w)) for j in range(3)) + (255,))
    out = grad.resize((w, h))
    out.putalpha(a)
    return out


def cone(w, h, col):
    """Searchlight: apex at the bottom centre, opening upward."""
    a = Image.new('L', (w, h))
    px = a.load()
    for y in range(h):
        v = 1 - y / h  # 0 at the bottom (apex) -> 1 at the top
        half = 0.04 + 0.46 * v
        for x in range(w):
            u = abs(x / w - 0.5) / half
            if u < 1:
                px[x, y] = int(255 * (1 - u * u) ** 1.6 * (1 - v) ** 0.55 * clamp(v / 0.04))
    a = a.filter(ImageFilter.GaussianBlur(w / 60))
    out = Image.new('RGBA', (w, h), col + (0,))
    out.putalpha(a)
    return out


def highlight(im, gamma=1.6, gain=1.25):
    """White silhouette weighted by how bright the art already is there — a
    sweep over it lights the ice edges and lettering, not the flat fills."""
    lum = im.convert('RGB').convert('L').point(lambda v: int(255 * clamp((v / 255) ** gamma * gain)))
    a = ImageChops.multiply(lum, im.getchannel('A'))
    out = Image.new('RGBA', im.size, (255, 255, 255, 0))
    out.putalpha(a)
    return out


def strips(im, n):
    """Cut `im` into n vertical strips; returns [(image, x0, x1)]."""
    out = []
    for i in range(n):
        x0, x1 = round(im.width * i / n), round(im.width * (i + 1) / n)
        out.append((im.crop((x0, 0, x1, im.height)), x0, x1))
    return out


def bright_points(im, n, region=None, seed=1, lum_min=225):
    """Spread-out bright, opaque pixels (farthest-point sampling)."""
    small = im.resize((im.width // 4, im.height // 4))
    rgb = small.convert('RGB').convert('L').load()
    al = small.getchannel('A').load()
    cand = []
    for y in range(small.height):
        for x in range(small.width):
            if rgb[x, y] >= lum_min and al[x, y] > 230:
                X, Y = x * 4 + 2, y * 4 + 2
                if region is None or region(X, Y):
                    cand.append((X, Y))
    rnd = random.Random(seed)
    if not cand:
        return []
    pts = [rnd.choice(cand)]
    while len(pts) < n:
        best = max(cand, key=lambda p: min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in pts))
        pts.append(best)
    return pts


# --------------------------------------------------------------------------
# frame (cabinet pixel space, 1672x941)

CAB_W, CAB_H = 1672, 941
WINDOWS = [(269, 608), (665, 1003), (1060, 1398)]
WIN_Y = (180, 877)


def cab_xy(ix, iy):
    return ix - CAB_W / 2, CAB_H / 2 - iy


def build_frame():
    cab = Image.open(os.path.join(ART, 'cabinet.png')).convert('RGBA')
    sk = Fx('frame', CAB_W, CAB_H, 0.85, {'idle': 4.0, 'win': 1.2})

    # outer halo: blurred silhouette minus the frame itself
    al = cab.getchannel('A')
    pad = 60
    big = Image.new('L', (CAB_W + 2 * pad, CAB_H + 2 * pad))
    big.paste(al, (pad, pad))
    blur = big.filter(ImageFilter.GaussianBlur(26)).point(lambda v: min(255, int(v * 1.7)))
    inner = Image.new('L', big.size)
    inner.paste(al.point(lambda v: int(v * 0.8)), (pad, pad))
    halo_a = ImageChops.subtract(blur, inner)
    halo = Image.new('RGBA', big.size, ICE + (0,))
    halo.putalpha(halo_a)
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.45
    sk.hidden_slot('halo', 'root', 'halo', w=CAB_W + 2 * pad, blend='additive')

    # light sweep, sliced
    hl = highlight(cab)
    N = 18
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, N)):
        r = f'sweep{i}'
        sk.image(r, im)
        x, _ = cab_xy((x0 + x1) / 2, CAB_H / 2)
        sk.hidden_slot(r, 'root', r, w=x1 - x0, x=x, blend='additive')
        sweep.append((r, (x0 + x1) / 2))

    # marquee bulbs round each window, on the bevel just outside the hole
    sk.image('bulb', glow_dot(128, core=0.28, col=ICE))
    sk.image('bulbv', glow_dot(128, core=0.28, col=VIOLET))
    bulbs = []
    step = 52
    off = 12
    for wi, (x0, x1) in enumerate(WINDOWS):
        L, R, T, B = x0 - off, x1 + off, WIN_Y[0] - off, WIN_Y[1] + off
        per = 2 * (R - L) + 2 * (B - T)
        n = int(round(per / step))
        for k in range(n):
            s = per * k / n
            if s < R - L:
                p = (L + s, T)
            elif s < (R - L) + (B - T):
                p = (R, T + s - (R - L))
            elif s < 2 * (R - L) + (B - T):
                p = (R - (s - (R - L) - (B - T)), B)
            else:
                p = (L, B - (s - 2 * (R - L) - (B - T)))
            name = f'b{wi}_{k}'
            x, y = cab_xy(*p)
            sk.hidden_slot(name, 'root', 'bulbv' if k % 2 else 'bulb', w=84, x=x, y=y, blend='additive')
            bulbs.append((name, wi, k, n))

    # glints on the crystals
    sk.image('glint', star4(192))
    pts = bright_points(cab, 16, region=lambda X, Y: not (WIN_Y[0] - 20 < Y < WIN_Y[1] + 20
                                                         and WINDOWS[0][0] - 30 < X < WINDOWS[2][1] + 30), seed=4)
    glints = []
    for gi, (X, Y) in enumerate(pts):
        b = sk.bone(f'g{gi}', x=cab_xy(X, Y)[0], y=cab_xy(X, Y)[1])
        sk.hidden_slot(f'g{gi}', b, 'glint', w=110, blend='additive')
        glints.append((b, gi))

    # --- idle (4s)
    sk.anim('idle', 'halo', 'alpha', lambda t: 0.38 + 0.18 * (1 - math.cos(2 * math.pi * t / 4)) / 2)
    sk.anim('win', 'halo', 'alpha', lambda t: 0.55 + 0.45 * (1 - math.cos(2 * math.pi * t / 0.3)) / 2)

    def sweep_fn(cx, t0, dur, peak, sigma=110):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-260, CAB_W + 260, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f

    for r, cx in sweep:
        sk.anim('idle', r, 'alpha', sweep_fn(cx, 1.0, 1.1, 0.75))
        sk.anim('win', r, 'alpha', sweep_fn(cx, 0.05, 0.75, 1.0, 140))

    for name, wi, k, n in bulbs:
        d = 1 if wi != 1 else -1  # middle window chases the other way

        def idle_b(t, k=k, n=n, d=d):
            s = frac(d * k / n * 4 - t / 2.0)
            return 0.16 + 0.84 * max(0.0, math.cos(2 * math.pi * s)) ** 6

        def win_b(t, k=k, n=n, d=d):
            blink = (1 - math.cos(2 * math.pi * (t / 0.3 + 0.5 * (k % 2)))) / 2
            chase = max(0.0, math.cos(2 * math.pi * frac(d * k / n * 3 - t / 0.6))) ** 8
            return clamp(0.25 + 0.6 * blink + 0.5 * chase)
        sk.anim('idle', name, 'alpha', idle_b)
        sk.anim('win', name, 'alpha', win_b)

    rnd = random.Random(9)
    for b, gi in glints:
        ph = rnd.random()
        ph2 = rnd.random()

        def ia(t, ph=ph):
            return pulse(t, 2.0, ph, sharp=10)

        def wa(t, ph=ph2):
            return pulse(t, 0.6, ph, sharp=6)
        sk.anim('idle', gi and f'g{gi}' or 'g0', 'alpha', ia)
        sk.anim('win', f'g{gi}', 'alpha', wa)
        sk.anim('idle', b, 'scale', lambda t, ph=ph: (0.3 + 0.9 * pulse(t, 2.0, ph, 6),) * 2)
        sk.anim('win', b, 'scale', lambda t, ph=ph2: (0.4 + 1.1 * pulse(t, 0.6, ph, 4),) * 2)
        sk.anim('idle', b, 'rotate', lambda t: 90 * t / 4)
        sk.anim('win', b, 'rotate', lambda t: 90 * t / 1.2)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# logo (logo.png pixel space, 1637x528)

def build_logo():
    logo = Image.open(os.path.join(ART, 'logo.png')).convert('RGBA')
    W, H = logo.size
    sk = Fx('logo', W, H, 0.8, {'idle': 4.0, 'win': 1.2})

    sk.image('halo', tint(soft_glow(512), ICE))
    sk.res_of['halo'] = 0.25
    sk.image('rays', rays(1024, n=18, col=(200, 240, 255)))
    sk.res_of['rays'] = 0.5
    sh = Image.new('RGBA', (W + 120, H + 120), (0, 0, 20, 0))
    a = Image.new('L', sh.size)
    a.paste(logo.getchannel('A'), (60, 60))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.85)))
    sk.image('shadow', sh)
    sk.res_of['shadow'] = 0.4
    sk.image('logo', logo)
    flash = Image.new('RGBA', logo.size, (230, 248, 255, 0))
    flash.putalpha(logo.getchannel('A'))
    sk.image('flash', flash)
    sk.res_of['flash'] = 0.5

    sk.bone('fxback')
    sk.bone('logo')
    sk.hidden_slot('halo', 'fxback', 'halo', w=W * 1.25, h=H * 2.2, blend='additive')
    sk.hidden_slot('rays', 'fxback', 'rays', w=W * 1.1, blend='additive')
    sk.slot('shadow', 'logo', 'shadow', w=W + 120, y=-16, color='ffffffb0')
    sk.slot('logo', 'logo', 'logo', w=W)
    hl = highlight(logo, gamma=1.3, gain=1.4)
    N = 16
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, N)):
        r = f'sw{i}'
        sk.image(r, im)
        sk.hidden_slot(r, 'logo', r, w=x1 - x0, x=(x0 + x1) / 2 - W / 2, blend='additive')
        sweep.append((r, (x0 + x1) / 2))
    sk.hidden_slot('flash', 'logo', 'flash', w=W, blend='additive')

    sk.image('glint', star4(192))
    pts = bright_points(logo, 7, seed=3, lum_min=235)
    for gi, (X, Y) in enumerate(pts):
        sk.bone(f'g{gi}', parent='logo', x=X - W / 2, y=H / 2 - Y)
        sk.hidden_slot(f'g{gi}', f'g{gi}', 'glint', w=150, blend='additive')

    # idle
    sk.anim('idle', 'logo', 'scale', lambda t: (1 + 0.018 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.anim('idle', 'halo', 'alpha', lambda t: 0.22 + 0.12 * (1 - math.cos(2 * math.pi * t / 4)) / 2)
    sk.anim('idle', 'rays', 'alpha', lambda t: 0.0)
    sk.anim('idle', 'fxback', 'rotate', lambda t: 0.0)
    sk.anim('idle', 'flash', 'alpha', lambda t: 0.0)

    def sweep_fn(cx, t0, dur, peak, sigma):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-200, W + 200, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f
    for r, cx in sweep:
        sk.anim('idle', r, 'alpha', sweep_fn(cx, 0.4, 1.0, 0.95, 120))
        sk.anim('win', r, 'alpha', sweep_fn(cx, 0.1, 0.6, 1.0, 150))
    rnd = random.Random(5)
    for gi in range(len(pts)):
        ph, ph2 = rnd.random(), rnd.random()
        sk.anim('idle', f'g{gi}', 'alpha', lambda t, ph=ph: pulse(t, 2.0, ph, 10))
        sk.anim('idle', f'g{gi}', 'scale', lambda t, ph=ph: (0.3 + 0.9 * pulse(t, 2.0, ph, 6),) * 2)
        sk.anim('idle', f'g{gi}', 'rotate', lambda t: 90 * t / 4)
        sk.anim('win', f'g{gi}', 'alpha', lambda t, ph=ph2: pulse(t, 0.6, ph, 5))
        sk.anim('win', f'g{gi}', 'scale', lambda t, ph=ph2: (0.4 + 1.2 * pulse(t, 0.6, ph, 4),) * 2)
        sk.anim('win', f'g{gi}', 'rotate', lambda t: 90 * t / 1.2)

    # win: punch, flash, rays
    def punch(t):
        if t < 0.12:
            return 1 + 0.12 * out_cubic(t / 0.12)
        u = t - 0.12
        return 1 + 0.12 * math.exp(-6 * u) * math.cos(16 * u)
    sk.anim('win', 'logo', 'scale', lambda t: (punch(t),) * 2)
    sk.anim('win', 'flash', 'alpha', lambda t: 0.85 * math.exp(-9 * t) if t > 0.02 else 0.85 * t / 0.02)
    sk.anim('win', 'halo', 'alpha', lambda t: 0.45 + 0.4 * math.exp(-4 * t))
    sk.anim('win', 'rays', 'alpha', lambda t: 0.4 + 0.25 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2)
    sk.anim('win', 'fxback', 'rotate', lambda t: -20 * t / 1.2)  # 18 rays -> 20deg = one ray step
    sk.write()
    return sk


# --------------------------------------------------------------------------
# background (stage space)

def build_bg(name, W, H, spread):
    sk = Fx(name, W, H, 0.7, {'idle': 8.0})
    P = 8.0
    rnd = random.Random(name)

    sk.image('glow', tint(soft_glow(512), (60, 120, 255)))
    sk.res_of['glow'] = 0.25
    sk.hidden_slot('backglow', 'root', 'glow', w=W * 1.3, h=H * 1.1, y=H * 0.05, blend='additive')
    sk.anim('idle', 'backglow', 'alpha', lambda t: 0.32 + 0.16 * (1 - math.cos(2 * math.pi * t / 4)) / 2)

    # aurora
    cols = [((90, 230, 255), (150, 110, 255)), ((150, 110, 255), (80, 200, 255)), ((60, 255, 210), (90, 150, 255))]
    for i, (c0, c1) in enumerate(cols):
        r = f'aur{i}'
        sk.image(r, ribbon(900, 300, i * 7 + 1, c0, c1))
        sk.res_of[r] = 0.45
        y0 = H * (0.30 - 0.07 * i)
        b = sk.bone(r, y=y0)
        sk.hidden_slot(r, b, r, w=W * spread * 1.2, h=H * 0.42, blend='additive')
        sk.anim('idle', r, 'alpha', lambda t, i=i: 0.30 + 0.18 * (1 - math.cos(2 * math.pi * (t / P * (1 + i % 2) + i * 0.3))) / 2)
        sk.anim('idle', b, 'translate', lambda t, i=i, y0=y0: (W * 0.05 * math.sin(2 * math.pi * (t / P + i / 3)), y0 + H * 0.02 * math.sin(2 * math.pi * (2 * t / P + i / 5))))
        sk.anim('idle', b, 'scale', lambda t, i=i: (1.0, 1 + 0.12 * math.sin(2 * math.pi * (t / P + i / 4))))

    # searchlights
    for side, col in ((-1, (120, 220, 255)), (1, (180, 130, 255))):
        r = f'spot{side}'
        sk.image(r, cone(256, 700, col))
        sk.res_of[r] = 0.5
        bx, by = side * W * spread * 0.36, -H * 0.62
        b = sk.bone(r, x=bx, y=by)
        sk.hidden_slot(r, b, r, w=H * 0.55, h=H * 1.5, y=H * 0.75, blend='additive')
        sk.anim('idle', b, 'rotate', lambda t, side=side: side * 14 + 16 * math.sin(2 * math.pi * (t / P + (0.25 if side > 0 else 0))))
        sk.anim('idle', r, 'alpha', lambda t, side=side: 0.28 + 0.10 * math.sin(2 * math.pi * (2 * t / P + side * 0.2)))

    # bokeh
    sk.image('bokeh', tint(soft_glow(128), (140, 200, 255)))
    sk.image('bokehv', tint(soft_glow(128), (170, 120, 255)))
    for i in range(12):
        x0 = rnd.uniform(-0.5, 0.5) * W * spread
        y0 = rnd.uniform(-0.5, 0.5) * H
        sz = rnd.uniform(0.06, 0.16) * min(W, H) * 1.4
        b = sk.bone(f'bk{i}', x=x0, y=y0)
        sk.hidden_slot(f'bk{i}', b, 'bokehv' if i % 3 == 0 else 'bokeh', w=sz, blend='additive')
        k = rnd.choice((1, 1, 2))
        ph = rnd.random()
        amp = rnd.uniform(0.02, 0.05) * W
        sk.anim('idle', b, 'translate', lambda t, x0=x0, y0=y0, k=k, ph=ph, amp=amp:
                (x0 + amp * math.sin(2 * math.pi * (k * t / P + ph)), y0 + amp * math.cos(2 * math.pi * (t / P + ph))))
        sk.anim('idle', f'bk{i}', 'alpha', lambda t, ph=ph: 0.10 + 0.12 * (1 - math.cos(2 * math.pi * (t / P * 2 + ph))) / 2)

    # twinkles
    sk.image('twinkle', star4(128))
    for i in range(30):
        x = rnd.uniform(-0.5, 0.5) * W * spread
        y = rnd.uniform(-0.1, 0.5) * H if i % 4 else rnd.uniform(-0.5, 0.5) * H
        b = sk.bone(f'tw{i}', x=x, y=y)
        sk.hidden_slot(f'tw{i}', b, 'twinkle', w=rnd.uniform(26, 60), blend='additive')
        ph = rnd.random()
        per = P / rnd.choice((2, 4, 4, 8))
        sk.anim('idle', f'tw{i}', 'alpha', lambda t, ph=ph, per=per: pulse(t, per, ph, 6))
        sk.anim('idle', b, 'scale', lambda t, ph=ph, per=per: (0.4 + 0.8 * pulse(t, per, ph, 4),) * 2)

    # snow
    sk.image('dot', glow_dot(64, core=0.3, col=(220, 240, 255)))
    sk.image('crystal', crystal(96))
    top, bot = H * 0.62, -H * 0.62
    span = top - bot
    for i in range(80):
        cr = i % 5 == 0
        x0 = rnd.uniform(-0.5, 0.5) * W * spread
        k = rnd.choice((1, 1, 2)) if not cr else 1
        ph0 = rnd.random()
        sway = rnd.uniform(10, 40)
        m = rnd.choice((1, 2))
        sph = rnd.random()
        size = rnd.uniform(22, 40) if cr else rnd.uniform(8, 24)
        amax = rnd.uniform(0.45, 0.9)
        b = sk.bone(f's{i}', x=x0, y=top)
        sk.hidden_slot(f's{i}', b, 'crystal' if cr else 'dot', w=size, blend='additive')

        def pos(t, x0=x0, k=k, ph0=ph0, sway=sway, m=m, sph=sph):
            p = frac(k * t / P + ph0)
            return (x0 + sway * math.sin(2 * math.pi * (m * t / P + sph)), top - span * p)

        def al(t, k=k, ph0=ph0, amax=amax):
            p = frac(k * t / P + ph0)
            return amax * clamp(min(p, 1 - p) / 0.08)
        sk.anim('idle', b, 'translate', pos)
        sk.anim('idle', f's{i}', 'alpha', al)
        if cr:
            sk.anim('idle', b, 'rotate', lambda t, d=rnd.choice((-1, 1)): d * 60 * t / P)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# win lines (reel-block space; same proportions on both layouts)

RW, RH = 1037, 640
COL_X = [(0.15045 - 0.5) * RW, 0.0, (0.84955 - 0.5) * RW]
ROW_Y = [RH / 3, 0.0, -RH / 3]
CELL_W, CELL_H = 0.3009 * RW, RH / 3
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
    head = glow_dot(256, core=0.22, col=(255, 255, 255))
    sk.image('head', head)
    comet = spark(256, 40)
    sk.image('comet', comet)
    sk.image('ring', ring(256))
    sk.image('flare', star4(256, thin=0.025))
    fw, fh = int(CELL_W * 0.96), int(CELL_H * 0.94)
    sk.image('cframe', rrect_frame(fw, fh, 26, 6, 9))
    sk.image('shard', shard())
    sk.image('cglow', soft_glow(256))
    sk.res_of['cglow'] = 0.4

    for n, rows in enumerate(PAYLINES, start=1):
        col = LINE_COLS[n - 1]
        pts = [(COL_X[c], ROW_Y[r]) for c, r in enumerate(rows)]
        (x0, y0), (x2, y2) = pts[0], pts[2]
        ang = math.atan2(y2 - y0, x2 - x0)
        ux, uy = math.cos(ang), math.sin(ang)
        ext = 0.16 * RW / max(abs(ux), 0.5) * abs(ux) if abs(uy) > 0.01 else 0.17 * RW
        sx, sy = x0 - ux * ext, y0 - uy * ext
        ex, ey = x2 + ux * ext, y2 + uy * ext
        L = math.hypot(ex - sx, ey - sy)
        cell_u = [math.hypot(px - sx, py - sy) / L for px, py in pts]

        P = f'L{n}'
        beam = sk.bone(f'{P}beam', x=sx, y=sy, rot=math.degrees(ang))
        sk.hidden_slot(f'{P}glow', beam, 'bglow', col, w=L, h=120, x=L / 2, blend='additive')
        for j in range(3):
            sk.hidden_slot(f'{P}bolt{j}', beam, f'bolt{j}', col, w=L, h=100, x=L / 2, blend='additive')
        sk.hidden_slot(f'{P}core', beam, 'bcore', w=L, h=22, x=L / 2, blend='additive')

        # cells: glow, frame, ring, flare, shards
        cells = []
        for ci, (px, py) in enumerate(pts):
            C = f'{P}c{ci}'
            cb = sk.bone(C, x=px, y=py)
            sk.hidden_slot(f'{C}glow', cb, 'cglow', col, w=CELL_W * 1.25, h=CELL_H * 1.35, blend='additive')
            fb = sk.bone(f'{C}f', parent=cb)
            sk.hidden_slot(f'{C}frame', fb, 'cframe', col, w=fw + 54, blend='additive')
            rb = sk.bone(f'{C}r', parent=cb)
            sk.hidden_slot(f'{C}ring', rb, 'ring', col, w=CELL_H * 1.1, blend='additive')
            shards = []
            for s in range(7):
                a = 2 * math.pi * (s + 0.3 * ci) / 7
                sb = sk.bone(f'{C}s{s}', parent=cb, rot=math.degrees(a) - 90)
                sk.hidden_slot(f'{C}s{s}', sb, 'shard', w=22, blend='additive')
                shards.append((sb, a))
            flb = sk.bone(f'{C}fl', parent=cb)
            sk.hidden_slot(f'{C}flare', flb, 'flare', w=CELL_H * 1.2, blend='additive')
            cells.append((C, cb, fb, rb, flb, shards))

        heads = []
        hb = sk.bone(f'{P}head', x=sx, y=sy)
        sk.hidden_slot(f'{P}head', hb, 'head', w=150, blend='additive')
        for k in range(2):
            cbn = sk.bone(f'{P}comet{k}', x=sx, y=sy, rot=math.degrees(ang))
            sk.hidden_slot(f'{P}comet{k}', cbn, 'comet', w=170, h=34, blend='additive')
            heads.append(cbn)

        INN, LP = f'line{n}_in', f'line{n}_loop'
        DRAW = 0.32

        def tip(t):
            return out_cubic(clamp(t / DRAW)) if t < DRAW else 1.0

        def at(u):  # time the tip reaches fraction u
            lo, hi = 0.0, DRAW
            for _ in range(30):
                mid = (lo + hi) / 2
                if tip(mid) < u:
                    lo = mid
                else:
                    hi = mid
            return hi

        # loop-start values (in must end on them)
        def g_loop(t):
            return 0.72 + 0.2 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2

        def sy_loop(t):
            return 1 + 0.18 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2

        sk.anim(INN, beam, 'scale', lambda t: (max(0.001, tip(t)), 1.25 - 0.25 * clamp(t / 0.5)))
        sk.anim(LP, beam, 'scale', lambda t: (1.0, sy_loop(t)))
        sk.anim(INN, f'{P}glow', 'alpha', lambda t: seg(t, 0, 0.12, 0, 1) if t < 0.4 else seg(t, 0.4, IN, 1, g_loop(0)))
        sk.anim(LP, f'{P}glow', 'alpha', g_loop)
        sk.anim(INN, f'{P}core', 'alpha', lambda t: seg(t, 0, 0.08, 0, 1))
        sk.anim(LP, f'{P}core', 'alpha', lambda t: 0.85 + 0.15 * math.cos(2 * math.pi * t / 0.3))

        for j in range(3):
            def bolt_a(t, j=j, base=0.0):
                return 1.0 if int(t / 0.1 + 0.001) % 3 == j else 0.2
            sk.anim(INN, f'{P}bolt{j}', 'alpha', lambda t, j=j: bolt_a(t, j) * clamp((t - 0.15) / 0.2) if t > 0.15 else 0.0)
            sk.anim(LP, f'{P}bolt{j}', 'alpha', lambda t, j=j: bolt_a(t, j) * (clamp(t / 0.0001) if False else 1.0))

        # head flare rides the tip
        sk.anim(INN, hb, 'translate', lambda t: (sx + (ex - sx) * tip(t), sy + (ey - sy) * tip(t)))
        sk.anim(INN, f'{P}head', 'alpha', lambda t: seg(t, 0, 0.05, 0, 1) if t < DRAW else seg(t, DRAW, DRAW + 0.2, 1, 0))
        sk.anim(INN, hb, 'scale', lambda t: (1 + 0.5 * math.sin(t * 40) * 0.2 + (0.6 if t > DRAW else 0) * seg(t, DRAW, DRAW + 0.2, 1, 0, linear_ease),) * 2)
        sk.anim(LP, hb, 'translate', lambda t: (ex, ey))
        sk.anim(LP, f'{P}head', 'alpha', lambda t: 0.0)
        sk.anim(LP, hb, 'scale', lambda t: (1.0, 1.0))

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

        for ci, (C, cb, fb, rb, flb, shards) in enumerate(cells):
            tk = at(cell_u[ci])

            def fr_loop(t):
                return 0.75 + 0.25 * math.cos(2 * math.pi * t / 0.6)

            def fl_loop_s(t):
                return 0.75 + 0.12 * math.cos(2 * math.pi * t / 0.6)

            sk.anim(INN, f'{C}glow', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.1, 0, 0.9) if t < tk + 0.2 else seg(t, tk + 0.2, IN, 0.9, 0.45))
            sk.anim(LP, f'{C}glow', 'alpha', lambda t: 0.45 + 0.2 * math.cos(2 * math.pi * t / 0.6) * 0 + 0.0 + 0.2 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2 - 0.2)
            sk.anim(INN, f'{C}frame', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.12, 0, 1) if t < tk + 0.12 else seg(t, tk + 0.12, IN, 1, fr_loop(0)))
            sk.anim(LP, f'{C}frame', 'alpha', fr_loop)
            sk.anim(INN, fb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.3, 1.18, 1.0),) * 2)
            sk.anim(LP, fb, 'scale', lambda t: (1 + 0.025 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2,) * 2)

            sk.anim(INN, f'{C}ring', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.42, 1, 0))
            sk.anim(INN, rb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.42, 0.25, 1.7),) * 2)

            def ring_loop_a(t):
                return seg(t, 0, 0.6, 0.55, 0, linear_ease) if t < 0.6 else seg(t, 0.6, 1.2, 0.55, 0, linear_ease)

            def ring_loop_s(t):
                return seg(t % 0.6, 0, 0.6, 0.5, 1.5, out_cubic)
            sk.anim(LP, f'{C}ring', 'alpha', ring_loop_a)
            sk.anim(LP, rb, 'scale', lambda t: (ring_loop_s(t),) * 2)

            sk.anim(INN, f'{C}flare', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.05, 0, 1) if t < tk + 0.15 else seg(t, tk + 0.15, IN, 1, 0.6))
            sk.anim(INN, flb, 'scale', lambda t, tk=tk: (0.01 if t < tk else (seg(t, tk, tk + 0.18, 0.1, 1.6, out_back) if t < tk + 0.18 else seg(t, tk + 0.18, IN, 1.6, fl_loop_s(0))),) * 2)
            sk.anim(INN, flb, 'rotate', lambda t, tk=tk: 0.0 if t < tk else -45 * seg(t, tk, IN, 1, 0))
            sk.anim(LP, f'{C}flare', 'alpha', lambda t: 0.6 + 0.25 * math.cos(2 * math.pi * t / 0.6))
            sk.anim(LP, flb, 'scale', lambda t: (fl_loop_s(t),) * 2)
            sk.anim(LP, flb, 'rotate', lambda t: -90 * t / LOOP)

            for s, (sb, a) in enumerate(shards):
                dist = 150 + 30 * (s % 3)

                def sh_pos(t, tk=tk, a=a, dist=dist):
                    d = 0 if t < tk else dist * out_cubic(clamp((t - tk) / 0.45))
                    return (math.cos(a) * d, math.sin(a) * d)
                sk.anim(INN, sb, 'translate', sh_pos)
                sk.anim(INN, f'{C}s{s}', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.45, 1, 0, in_cubic_ease))
                sk.anim(LP, f'{C}s{s}', 'alpha', lambda t: 0.0)
                sk.anim(LP, sb, 'translate', lambda t: (0.0, 0.0))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# symbols (cell space): one clip per symbol code, 1.1s, ends on the rest pose

SYMBOLS = {
    # code: (sym fraction from CSS, glow colour, motion)
    'cherry': (0.9, (255, 70, 90), 'hop'),
    'plum': (0.9, (190, 90, 255), 'hop'),
    'lemon': (0.9, (255, 230, 70), 'hop'),
    'orange': (0.9, (255, 150, 40), 'hop'),
    'grape': (0.9, (90, 140, 255), 'jiggle'),
    'bell': (0.98, (255, 205, 60), 'swing'),
    'star': (1.0, (255, 220, 80), 'spin'),
    'bar': (0.96, (120, 210, 255), 'stretch'),
    'seven': (1.0, (70, 200, 255), 'slam'),
}
SYM_DUR = 1.1


def sym_motion(kind, t):
    """(sx, sy, rot, dy) of the symbol bone at time t; rest = (1, 1, 0, 0)."""
    def settle(t0, amp, freq=15, damp=7):
        u = t - t0
        return amp * math.exp(-damp * u) * math.cos(freq * u) if u > 0 else amp
    if kind == 'hop':
        if t < 0.08:  # crouch
            k = out_cubic(t / 0.08)
            return 1 + 0.14 * k, 1 - 0.16 * k, 0, -8 * k
        if t < 0.34:  # jump, stretched
            u = (t - 0.08) / 0.26
            h = math.sin(math.pi * u)
            return 1.14 + 0.1 * h - 0.14 * u, 1.16 * h + (1 - h) * 0.95, 6 * math.sin(2 * math.pi * u), 34 * h
        if t < 0.42:  # land squash
            k = math.sin(math.pi * (t - 0.34) / 0.08)
            return 1.1 + 0.12 * k, 1.1 - 0.2 * k, 0, -4 * k
        e = settle(0.42, 0.1)
        return 1 + e, 1 + e, 0, 0
    if kind == 'jiggle':
        if t < 0.1:
            k = out_cubic(t / 0.1)
            return 1 + 0.2 * k, 1 + 0.2 * k, 0, 0
        u = t - 0.1
        w = 0.2 * math.exp(-4.5 * u)
        return 1 + w + 0.09 * math.exp(-4 * u) * math.sin(26 * u), 1 + w - 0.09 * math.exp(-4 * u) * math.sin(26 * u), 0, 0
    if kind == 'swing':
        s = 1 + 0.2 * (out_cubic(clamp(t / 0.1)) if t < 0.1 else math.exp(-5 * (t - 0.1)))
        return s, s, 24 * math.exp(-3.6 * t) * math.sin(13 * t), 0
    if kind == 'spin':
        s = 1 + 0.32 * math.sin(math.pi * clamp(t / 0.5)) + (settle(0.5, 0.0) if t > 0.5 else 0)
        rot = -360 * out_cubic(clamp(t / 0.55))
        return s, s, rot, 10 * math.sin(math.pi * clamp(t / 0.5))
    if kind == 'stretch':
        if t < 0.12:
            k = out_cubic(t / 0.12)
            return 1 + 0.3 * k, 1 + 0.06 * k, 0, 0
        e = math.exp(-6 * (t - 0.12)) * math.cos(16 * (t - 0.12))
        return 1 + 0.3 * e, 1 + 0.06 * e, 0, 0
    if kind == 'slam':
        if t < 0.1:  # wind up big
            k = out_cubic(t / 0.1)
            return 1 + 0.4 * k, 1 + 0.4 * k, 0, 0
        if t < 0.18:  # slam down
            k = (t - 0.1) / 0.08
            return 1.4 - 0.5 * k, 1.4 - 0.62 * k, 0, 0
        e = settle(0.18, 0.15, 18, 5.5)
        shake = 5 * math.exp(-6 * (t - 0.18)) * math.sin(70 * t)
        return 1 + 0.12 - 0.12 * clamp((t - 0.18) / 0.5) + e - 0.15 * math.exp(-5.5 * 0) * 0, 1 + 0.12 - 0.12 * clamp((t - 0.18) / 0.5) + e, shake, 0
    return 1, 1, 0, 0


def build_symbols():
    CW, CH = CELL_W, CELL_H
    sk = Fx('symbols', CW, CH, 1.0, {code: SYM_DUR for code in SYMBOLS})
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.5
    sk.image('rays', rays(512, n=14))
    sk.res_of['rays'] = 0.6
    sk.image('ring', ring(256))
    sk.image('spark', star4(128))
    sk.image('dot', glow_dot(64, core=0.3, col=(230, 245, 255)))
    rnd = random.Random(21)
    for code, (symf, col, kind) in SYMBOLS.items():
        im = Image.open(os.path.join(ROOT, 'symbols', f'{code}.png')).convert('RGBA')
        k = min(CW * symf / im.width, CH * symf / im.height)
        w, h = im.width * k, im.height * k
        hexcol = '%02x%02x%02x' % col
        sk.image(code, im)
        sk.res_of[code] = 2.0  # full source res: the DOM tile it replaces is sharp
        flash = Image.new('RGBA', im.size, (255, 255, 255, 0))
        flash.putalpha(im.getchannel('A'))
        sk.image(f'{code}_flash', flash)
        sk.res_of[f'{code}_flash'] = 0.5

        C = code
        fx = sk.bone(f'{C}_fx')
        sk.hidden_slot(f'{C}_halo', fx, 'halo', hexcol, w=CW * 1.25, h=CH * 1.6, blend='additive')
        sk.hidden_slot(f'{C}_rays', fx, 'rays', hexcol, w=CH * 2.1, blend='additive')
        rb = sk.bone(f'{C}_rb')
        sk.hidden_slot(f'{C}_ring', rb, 'ring', 'e8f8ff', w=CH * 1.0, blend='additive')
        # bell swings from its handle: pivot at the top of the art
        piv = h * 0.42 if kind == 'swing' else 0
        sb = sk.bone(f'{C}_sym', y=piv)
        sk.hidden_slot(f'{C}_img', sb, code, w=w, y=-piv)
        hl = highlight(im, gamma=1.2, gain=1.5)
        N = 16
        sweep = []
        for i, (sim, x0, x1) in enumerate(strips(hl, N)):
            r = f'{C}_sw{i}'
            sk.image(r, sim)
            sk.res_of[r] = 0.8
            sk.hidden_slot(r, sb, r, w=(x1 - x0) * k, x=((x0 + x1) / 2 - im.width / 2) * k, y=-piv, blend='additive')
            sweep.append((r, (x0 + x1) / 2 * k))
        sk.hidden_slot(f'{C}_flash', sb, f'{C}_flash', w=w, y=-piv, blend='additive')
        sparks = []
        for i in range(7):
            a = 2 * math.pi * i / 7 + rnd.uniform(-0.3, 0.3)
            b = sk.bone(f'{C}_sp{i}')
            sk.hidden_slot(f'{C}_sp{i}', b, 'spark' if i % 2 == 0 else 'dot', 'ffffff', w=rnd.uniform(34, 56), blend='additive')
            sparks.append((b, f'{C}_sp{i}', a, rnd.uniform(0.75, 1.1), rnd.uniform(0, 0.08)))

        sk.anim(C, f'{C}_img', 'alpha', lambda t: 1.0)
        sk.anim(C, sb, 'scale', lambda t, kind=kind: sym_motion(kind, t)[:2])
        sk.anim(C, sb, 'rotate', lambda t, kind=kind: sym_motion(kind, t)[2])
        sk.anim(C, sb, 'translate', lambda t, kind=kind, piv=piv: (0, piv + sym_motion(kind, t)[3]))
        sk.anim(C, f'{C}_flash', 'alpha', lambda t: seg(t, 0, 0.06, 0, 0.85) if t < 0.06 else 0.85 * math.exp(-11 * (t - 0.06)))
        for r, cx in sweep:
            sk.anim(C, r, 'alpha', lambda t, cx=cx: 0.0 if not 0.12 <= t <= 0.62 else
                    0.9 * math.exp(-((cx - lerp(-60, w + 60, in_out_sine((t - 0.12) / 0.5))) / 70) ** 2))
        big = 1.25 if kind == 'slam' else 1.0
        sk.anim(C, f'{C}_halo', 'alpha', lambda t, big=big: seg(t, 0, 0.1, 0, 0.9 * big) if t < 0.1 else seg(t, 0.1, SYM_DUR, 0.9 * big, 0, in_out_sine))
        sk.anim(C, fx, 'scale', lambda t: (seg(t, 0, 0.2, 0.5, 1.15, out_back) if t < 0.2 else seg(t, 0.2, SYM_DUR, 1.15, 0.9),) * 2)
        sk.anim(C, f'{C}_rays', 'alpha', lambda t, big=big: seg(t, 0, 0.12, 0, 0.75 * big) if t < 0.12 else seg(t, 0.12, SYM_DUR, 0.75 * big, 0, in_out_sine))
        sk.anim(C, fx, 'rotate', lambda t: -50 * t / SYM_DUR)
        t0 = 0.18 if kind == 'slam' else 0.04
        sk.anim(C, f'{C}_ring', 'alpha', lambda t, t0=t0: 0.0 if t < t0 else seg(t, t0, t0 + 0.45, 1, 0))
        sk.anim(C, rb, 'scale', lambda t, t0=t0, big=big: (seg(t, t0, t0 + 0.45, 0.3, 1.9 * big),) * 2)
        for b, sl, a, dist, delay in sparks:
            def sp_pos(t, a=a, dist=dist, delay=delay):
                u = clamp((t - 0.05 - delay) / 0.7)
                d = (CH * 0.35 + CH * 0.45 * dist * out_cubic(u))
                spin = a + 1.2 * u
                return (math.cos(spin) * d * 1.3, math.sin(spin) * d)
            sk.anim(C, b, 'translate', sp_pos)
            sk.anim(C, sl, 'alpha', lambda t, delay=delay: 0.0 if t < 0.05 + delay else seg(t, 0.05 + delay, 0.85 + delay, 1, 0, in_cubic_ease))
            sk.anim(C, b, 'scale', lambda t, delay=delay: (0.4 + 0.9 * pulse(t - delay, 0.35, 0.0, 2),) * 2)
            sk.anim(C, b, 'rotate', lambda t: 180 * t)
    sk.write()
    return sk


def linear_ease(t):
    return t


def in_cubic_ease(t):
    return t ** 3


# --------------------------------------------------------------------------
# software preview (checks layout/timing; the built-in browser can't draw WebGL)

def render(sk, clip, t, size, under=None, under_box=None):
    """Draw skeleton `sk` at time t of `clip`; canvas `size` px covers the
    skeleton bounds. `under` is an optional image placed at `under_box`
    (x, y, w, h in skeleton units, y up)."""
    data = sk.data
    W, H = size
    sc = W / sk.w
    canvas = Image.new('RGBA', size, (6, 8, 30, 255))
    if under is not None:
        bx, by, bw, bh = under_box
        u = under.convert('RGBA').resize((int(bw * sc), int(bh * sc)))
        canvas.alpha_composite(u, (int((bx + sk.w / 2) * sc), int((sk.h / 2 - by - bh) * sc)))
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
        sx *= b.get('scaleX', 1)
        sy *= b.get('scaleY', 1)
        x, y = b.get('x', 0) + tx, b.get('y', 0) + ty
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        m = (c * sx, -s * sy, x, s * sx, c * sy, y)
        if 'parent' in b:
            p = world[b['parent']]
            m = (p[0] * m[0] + p[1] * m[3], p[0] * m[1] + p[1] * m[4], p[0] * m[2] + p[1] * m[5] + p[2],
                 p[3] * m[0] + p[4] * m[3], p[3] * m[1] + p[4] * m[4], p[3] * m[2] + p[4] * m[5] + p[5])
        world[b['name']] = m
    add = Image.new('RGBA', size, (0, 0, 0, 0))
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
        # image px -> attachment local -> bone world -> canvas px
        aw, ah = att['width'], att['height']
        ar = math.radians(att.get('rotation', 0))
        ca, sa = math.cos(ar), math.sin(ar)
        kx, ky = aw / im.width, -ah / im.height
        A = (ca * kx, -sa * ky, att['x'] - (ca * aw / 2 - sa * ah / 2) * 1 + 0,
             sa * kx, ca * ky, att['y'] + 0)
        # local (u,v) = rot * (px*kx - aw/2, py*ky + ah/2) + (ax, ay)
        lx0, ly0 = -aw / 2, ah / 2
        A = (ca * kx, -sa * ky, ca * lx0 - sa * ly0 + att['x'],
             sa * kx, ca * ky, sa * lx0 + ca * ly0 + att['y'])
        Mw = (m[0] * A[0] + m[1] * A[3], m[0] * A[1] + m[1] * A[4], m[0] * A[2] + m[1] * A[5] + m[2],
              m[3] * A[0] + m[4] * A[3], m[3] * A[1] + m[4] * A[4], m[3] * A[2] + m[4] * A[5] + m[5])
        C = (sc * Mw[0], sc * Mw[1], sc * Mw[2] + W / 2, -sc * Mw[3], -sc * Mw[4], -sc * Mw[5] + H / 2)
        det = C[0] * C[4] - C[1] * C[3]
        if abs(det) < 1e-9:
            continue
        inv = (C[4] / det, -C[1] / det, (C[1] * C[5] - C[4] * C[2]) / det,
               -C[3] / det, C[0] / det, (C[3] * C[2] - C[0] * C[5]) / det)
        layer = im.transform(size, Image.AFFINE, inv, Image.BILINEAR)
        r, g, b_, al = layer.split()
        if tintc != (255, 255, 255):
            r = r.point(lambda v, k=tintc[0]: v * k // 255)
            g = g.point(lambda v, k=tintc[1]: v * k // 255)
            b_ = b_.point(lambda v, k=tintc[2]: v * k // 255)
        al = al.point(lambda v, a=a: int(v * a))
        layer = Image.merge('RGBA', (r, g, b_, al))
        if s.get('blend') == 'additive':
            pm = premultiply(layer)
            add = ImageChops.add(add, pm)
            canvas = Image.alpha_composite(canvas, Image.new('RGBA', size, (0, 0, 0, 0)))
            base = canvas.convert('RGB')
            base = ImageChops.add(base, pm.convert('RGB'))
            canvas = base.convert('RGBA')
        else:
            canvas.alpha_composite(layer)
    return canvas


def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
        os.makedirs(preview, exist_ok=True)
    only = [a for a in sys.argv[1:] if not a.startswith('--') and a != preview]
    built = {}
    if not only or 'frame' in only:
        built['frame'] = build_frame()
    if not only or 'logo' in only:
        built['logo'] = build_logo()
    if not only or 'bg' in only:
        built['bg_desk'] = build_bg('bg_desk', 1600, 1000, 1.6)
        built['bg_mob'] = build_bg('bg_mob', 780, 1080, 1.4)
    if not only or 'winlines' in only:
        built['winlines'] = build_winlines()
    if not only or 'symbols' in only:
        built['symbols'] = build_symbols()
    if not preview:
        return
    cab = Image.open(os.path.join(ART, 'cabinet.png'))
    logo = Image.open(os.path.join(ART, 'logo.png'))
    bg = Image.open(os.path.join(ART, 'bg_base.jpg'))
    cover = Image.open(os.path.join(ART, 'cover.jpg'))
    for name, sk in built.items():
        for clip, dur in sk.durs.items():
            if name == 'winlines' and not clip.startswith(('line1', 'line4')):
                continue
            if name == 'symbols' and clip not in ('cherry', 'bell', 'star', 'seven'):
                continue
            frames = [render(sk, clip, dur * k / 6, (800, int(800 * sk.h / sk.w)),
                             under={'frame': cab, 'logo': logo, 'bg_desk': bg}.get(name),
                             under_box={'frame': (-CAB_W / 2, -CAB_H / 2, CAB_W, CAB_H),
                                        'logo': (-sk.w / 2, -sk.h / 2, sk.w, sk.h),
                                        'bg_desk': (-sk.w / 2, -sk.h / 2, sk.w, sk.h)}.get(name))
                      for k in range(6)]
            sheet = Image.new('RGB', (800 * 2, frames[0].height * 3))
            for k, f in enumerate(frames):
                sheet.paste(f.convert('RGB'), ((k % 2) * 800, (k // 2) * f.height))
            sheet.save(os.path.join(preview, f'{name}_{clip}.jpg'), quality=82)


if __name__ == '__main__':
    main()
