"""Gold of Baku / Gold of Baku 2: in-game Spine FX generated in code.

Same pipeline as scripts/ice_spin_deluxe_fx.py (its Fx class, image helpers and
software preview are reused). Seven skeletons per game into
front/img/<game>/fx/:

  bg_desk / bg_mob  behind the stage. Clip `idle` (8s loop).
                    gold-of-baku   (bordeaux carpet): god rays, rising embers,
                                   gold twinkles, warm bokeh.
                    gold-of-baku-2 (Baku at night): star field, shooting stars,
                                   fireworks, city-light bokeh, water glints.
  frame             over cabinet.png, authored in its pixel space: outer halo,
                    light sweep through the gold, glints on the ornament,
                    comets running round the reel window. Clips `idle` (4s)
                    and `win` (1.2s).
  logo              the logo itself + shadow, halo, sweep, glints, rays.
                    Clips `idle` (4s) and `win` (1.2s).
  winlines          the five paylines (reel-window space), each its own
                    colour: beam drawn in, twisting gold ribbons, comets,
                    a burst of eight-point stars + glowing frame per cell.
                    Clips `line{n}_in` (0.7s) and `line{n}_loop` (1.2s).
  burst             reel-window space: coin fountain + star burst for a win
                    under the popup threshold. Clip `win` (1.6s).
  shower            1000x1000 screen box: gold coin rain for the BIG/MEGA/EPIC
                    popup. Clips `start` (2s, coins enter from the top) and
                    `rain` (2s loop).

Every slot an animation touches starts transparent in the setup pose.

    python3 scripts/gold_of_baku_fx.py gold-of-baku [--preview DIR]
    python3 scripts/gold_of_baku_fx.py gold-of-baku-2 [--preview DIR]
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from spine_screen_kit import (  # noqa: E402
    clamp, in_out_sine, lerp, out_back, out_cubic, pulse, rays, seg, soft_glow, spark,
)
from ice_spin_deluxe_fx import (  # noqa: E402
    Fx, bright_points, glow_dot, hband, highlight, in_cubic_ease, linear_ease, render,
    ring, rrect_frame, star4, strips, tint,
)

FRONT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img')

GOLD = (255, 204, 96)
WARM = (255, 150, 60)

GAMES = {
    'gold-of-baku': {
        # reel window as fractions of cabinet.png (= --win-l/t/w/h in the CSS)
        'win': (0.1156, 0.0701, 0.7694, 0.7943),
        'theme': 'embers',
        'halo': (255, 176, 70),
        'line_cols': ['ffd54a', 'ff4d6a', '3fe6d2', 'ff9a3c', 'c98bff'],
    },
    'gold-of-baku-2': {
        'win': (0.1118, 0.0845, 0.7776, 0.7836),
        'theme': 'night',
        'halo': (120, 190, 255),
        'line_cols': ['ffd54a', '5ec8ff', 'ff5fd2', '6dffa8', 'b58cff'],
    },
}

DESIGN = {'bg_desk': (1720, 1000), 'bg_mob': (780, 1300)}


def frac(x):
    return x - math.floor(x)


class BFx(Fx):
    def __init__(self, name, w, h, res, clips, out):
        super().__init__(name, w, h, res, clips)
        self.out_dir = out


# --------------------------------------------------------------------------
# images

def star8(size, col=(255, 236, 160), glow=True):
    """Eight-point star (two squares, 45 deg apart) — the ornament's own motif."""
    big = size * 4
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    c, r = big / 2, big * 0.3
    for a0 in (0, 45):
        pts = [(c + r * math.cos(math.radians(a0 + 45 + 90 * k)) * 1.0,
                c + r * math.sin(math.radians(a0 + 45 + 90 * k))) for k in range(4)]
        d.polygon(pts, fill=255)
    m = m.resize((size, size), Image.LANCZOS)
    if glow:
        g = m.filter(ImageFilter.GaussianBlur(size * 0.08)).point(lambda v: min(255, v * 2))
        m = ImageChops.lighter(m, g.point(lambda v: v * 3 // 4))
    out = Image.new('RGBA', (size, size), col + (0,))
    out.putalpha(m)
    hot = soft_glow(size // 2)
    out.alpha_composite(hot, (size // 4, size // 4))
    return out


def coin(size=128):
    """Gold coin with an embossed eight-point star."""
    S = size * 4
    c = S / 2
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    px = out.load()
    for y in range(S):
        for x in range(S):
            dx, dy = (x - c) / c, (y - c) / c
            r = math.hypot(dx, dy)
            if r > 0.98:
                continue
            # light from the top-left
            lit = clamp(0.62 - 0.38 * (dx + dy) / 1.4)
            if r > 0.84:  # rim
                k = 0.55 + 0.45 * clamp(1 - (r - 0.84) / 0.14) * lit
            elif r > 0.78:  # groove
                k = 0.42
            else:
                k = 0.66 + 0.34 * lit
            px[x, y] = (int(255 * min(1, k * 1.05)), int(200 * k + 20), int(70 * k), 255)
    d = ImageDraw.Draw(out)
    r = S * 0.25
    for a0 in (0, 45):
        pts = [(c + r * math.cos(math.radians(a0 + 45 + 90 * k)), c + r * math.sin(math.radians(a0 + 45 + 90 * k)))
               for k in range(4)]
        d.polygon(pts, fill=(255, 238, 168, 255), outline=(150, 92, 18, 255), width=S // 90)
    d.ellipse([c - S * 0.06, c - S * 0.06, c + S * 0.06, c + S * 0.06], fill=(196, 40, 52, 255))
    # specular
    sp = Image.new('L', (S, S))
    ImageDraw.Draw(sp).ellipse([S * 0.2, S * 0.14, S * 0.56, S * 0.4], fill=120)
    sp = sp.filter(ImageFilter.GaussianBlur(S * 0.05))
    white = Image.new('RGBA', (S, S), (255, 255, 255, 0))
    white.putalpha(ImageChops.multiply(sp, out.getchannel('A')))
    out.alpha_composite(white)
    return out.resize((size, size), Image.LANCZOS)


def wave_ribbon(w, h, periods, phase):
    sc = 2
    m = Image.new('L', (w * sc, h * sc))
    d = ImageDraw.Draw(m)
    pts = []
    for i in range(201):
        u = i / 200
        taper = math.sin(math.pi * u) ** 0.4
        y = h * sc / 2 + math.sin(2 * math.pi * (u * periods) + phase) * h * sc * 0.32 * taper
        pts.append((u * w * sc, y))
    d.line(pts, fill=255, width=4 * sc, joint='curve')
    m = m.resize((w, h), Image.LANCZOS)
    g = m.filter(ImageFilter.GaussianBlur(h * 0.07)).point(lambda v: min(255, v * 3))
    out = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    out.putalpha(ImageChops.lighter(m, g.point(lambda v: v * 2 // 3)))
    return out


# --------------------------------------------------------------------------
# frame (cabinet pixel space)

def build_frame(cfg, art, out):
    cab = Image.open(os.path.join(art, 'cabinet.png')).convert('RGBA')
    CW, CH = cab.size
    wl, wt, ww, wh = cfg['win']
    L, T, R, B = wl * CW, wt * CH, (wl + ww) * CW, (wt + wh) * CH

    def xy(ix, iy):
        return ix - CW / 2, CH / 2 - iy

    sk = BFx('frame', CW, CH, 0.85, {'idle': 4.0, 'win': 1.2}, out)

    al = cab.getchannel('A')
    pad = 60
    big = Image.new('L', (CW + 2 * pad, CH + 2 * pad))
    big.paste(al, (pad, pad))
    blur = big.filter(ImageFilter.GaussianBlur(26)).point(lambda v: min(255, int(v * 1.7)))
    inner = Image.new('L', big.size)
    inner.paste(al.point(lambda v: int(v * 0.8)), (pad, pad))
    halo = Image.new('RGBA', big.size, cfg['halo'] + (0,))
    halo.putalpha(ImageChops.subtract(blur, inner))
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.45
    sk.hidden_slot('halo', 'root', 'halo', w=CW + 2 * pad, blend='additive')

    # window edge glow (win only)
    ew, eh = int(R - L), int(B - T)
    sk.image('edge', rrect_frame(ew, eh, 14, 6, 10))
    sk.res_of['edge'] = 0.6
    ex, ey = xy((L + R) / 2, (T + B) / 2)
    sk.hidden_slot('edge', 'root', 'edge', 'ffd77a', w=ew + 60, x=ex, y=ey, blend='additive')

    hl = highlight(cab, gamma=1.4, gain=1.3)
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, 18)):
        r = f'sweep{i}'
        sk.image(r, im)
        sk.res_of[r] = 0.5
        sk.hidden_slot(r, 'root', r, w=x1 - x0, x=xy((x0 + x1) / 2, 0)[0], blend='additive')
        sweep.append((r, (x0 + x1) / 2))

    sk.image('glint', star4(192, col=(255, 240, 200)))
    pts = bright_points(cab, 16, region=lambda X, Y: not (T - 25 < Y < B + 25 and L - 25 < X < R + 25),
                        seed=4, lum_min=215)
    glints = []
    for gi, (X, Y) in enumerate(pts):
        b = sk.bone(f'g{gi}', x=xy(X, Y)[0], y=xy(X, Y)[1])
        sk.hidden_slot(f'g{gi}', b, 'glint', w=100, blend='additive')
        glints.append(b)

    # comets round the window: head + fading trail
    per = 2 * (R - L) + 2 * (B - T)
    o = 3  # on the inner bevel

    def perim(s):
        s = frac(s) * per
        w_, h_ = R - L, B - T
        if s < w_:
            p = (L + s, T - o)
        elif s < w_ + h_:
            p = (R + o, T + s - w_)
        elif s < 2 * w_ + h_:
            p = (R - (s - w_ - h_), B + o)
        else:
            p = (L - o, B - (s - 2 * w_ - h_))
        return xy(*p)

    sk.image('dot', glow_dot(128, core=0.26, col=GOLD))
    TRAIL = 7
    comets = []
    for c in range(4):
        for k in range(TRAIL):
            name = f'c{c}_{k}'
            b = sk.bone(name, x=perim(c / 4)[0], y=perim(c / 4)[1])
            sk.hidden_slot(name, b, 'dot', w=70 - 7 * k, blend='additive')
            comets.append((b, name, c, k))

    def sweep_fn(cx, t0, dur, peak, sigma):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-260, CW + 260, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f

    sk.anim('idle', 'halo', 'alpha', lambda t: 0.30 + 0.2 * (1 - math.cos(2 * math.pi * t / 4)) / 2)
    sk.anim('win', 'halo', 'alpha', lambda t: 0.55 + 0.45 * (1 - math.cos(2 * math.pi * t / 0.4)) / 2)
    sk.anim('idle', 'edge', 'alpha', lambda t: 0.0)
    sk.anim('win', 'edge', 'alpha', lambda t: 0.35 + 0.3 * (1 + math.cos(2 * math.pi * t / 0.4)) / 2)
    for r, cx in sweep:
        sk.anim('idle', r, 'alpha', sweep_fn(cx, 1.2, 1.3, 0.7, 120))
        sk.anim('win', r, 'alpha', sweep_fn(cx, 0.05, 0.8, 1.0, 150))
    rnd = random.Random(9)
    for gi, b in enumerate(glints):
        ph, ph2 = rnd.random(), rnd.random()
        sk.anim('idle', f'g{gi}', 'alpha', lambda t, ph=ph: pulse(t, 2.0, ph, 10))
        sk.anim('win', f'g{gi}', 'alpha', lambda t, ph=ph2: pulse(t, 0.6, ph, 6))
        sk.anim('idle', b, 'scale', lambda t, ph=ph: (0.3 + 0.9 * pulse(t, 2.0, ph, 6),) * 2)
        sk.anim('win', b, 'scale', lambda t, ph=ph2: (0.4 + 1.1 * pulse(t, 0.6, ph, 4),) * 2)
        sk.anim('idle', b, 'rotate', lambda t: 90 * t / 4)
        sk.anim('win', b, 'rotate', lambda t: 90 * t / 1.2)
    lag = 0.012
    for b, name, c, k in comets:
        # idle: two comets (0 and 2), one lap in 4s; win: all four, one lap in 1.2s
        on_idle = c % 2 == 0
        sk.anim('idle', b, 'translate', lambda t, c=c, k=k: perim(c / 4 + t / 4 - k * lag))
        sk.anim('win', b, 'translate', lambda t, c=c, k=k: perim(c / 4 + t / 1.2 - k * lag * 1.6))
        fade = (1 - k / TRAIL) ** 1.3
        sk.anim('idle', name, 'alpha', lambda t, f=fade, on=on_idle: f * 0.85 if on else 0.0)
        sk.anim('win', name, 'alpha', lambda t, f=fade: f)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# logo (logo.png pixel space)

def build_logo(cfg, art, out):
    logo = Image.open(os.path.join(art, 'logo.png')).convert('RGBA')
    W, H = logo.size
    sk = BFx('logo', W, H, min(0.8, 1200 / W), {'idle': 4.0, 'win': 1.2}, out)

    sk.image('halo', tint(soft_glow(512), GOLD))
    sk.res_of['halo'] = 0.25
    sk.image('rays', rays(1024, n=16, col=(255, 226, 150)))
    sk.res_of['rays'] = 0.5
    sh = Image.new('RGBA', (W + 120, H + 120), (10, 0, 0, 0))
    a = Image.new('L', sh.size)
    a.paste(logo.getchannel('A'), (60, 60))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.85)))
    sk.image('shadow', sh)
    sk.res_of['shadow'] = 0.4
    sk.image('logo', logo)
    flash = Image.new('RGBA', logo.size, (255, 246, 220, 0))
    flash.putalpha(logo.getchannel('A'))
    sk.image('flash', flash)
    sk.res_of['flash'] = 0.5

    sk.bone('fxback')
    sk.bone('logo')
    sk.hidden_slot('halo', 'fxback', 'halo', w=W * 1.2, h=H * 2.2, blend='additive')
    sk.hidden_slot('rays', 'fxback', 'rays', w=W * 0.95, blend='additive')
    sk.slot('shadow', 'logo', 'shadow', w=W + 120 * W / 1400, y=-14 * W / 1400, color='ffffffb0')
    sk.slot('logo', 'logo', 'logo', w=W)
    hl = highlight(logo, gamma=1.3, gain=1.4)
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, 16)):
        r = f'sw{i}'
        sk.image(r, im)
        sk.res_of[r] = 0.5
        sk.hidden_slot(r, 'logo', r, w=x1 - x0, x=(x0 + x1) / 2 - W / 2, blend='additive')
        sweep.append((r, (x0 + x1) / 2))
    sk.hidden_slot('flash', 'logo', 'flash', w=W, blend='additive')

    sk.image('glint', star4(192, col=(255, 240, 200)))
    pts = bright_points(logo, 7, seed=3, lum_min=230)
    for gi, (X, Y) in enumerate(pts):
        sk.bone(f'g{gi}', parent='logo', x=X - W / 2, y=H / 2 - Y)
        sk.hidden_slot(f'g{gi}', f'g{gi}', 'glint', w=150 * W / 1400, blend='additive')

    sk.anim('idle', 'logo', 'scale', lambda t: (1 + 0.018 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.anim('idle', 'halo', 'alpha', lambda t: 0.20 + 0.14 * (1 - math.cos(2 * math.pi * t / 4)) / 2)
    sk.anim('idle', 'rays', 'alpha', lambda t: 0.10 + 0.06 * (1 - math.cos(2 * math.pi * t / 4)) / 2)
    sk.anim('idle', 'fxback', 'rotate', lambda t: -22.5 * t / 4)  # 16 rays: one step per loop
    sk.anim('idle', 'flash', 'alpha', lambda t: 0.0)

    def sweep_fn(cx, t0, dur, peak, sigma):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-200, W + 200, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f
    for r, cx in sweep:
        sk.anim('idle', r, 'alpha', sweep_fn(cx, 0.4, 1.0, 0.95, 120 * W / 1400))
        sk.anim('win', r, 'alpha', sweep_fn(cx, 0.1, 0.6, 1.0, 150 * W / 1400))
    rnd = random.Random(5)
    for gi in range(len(pts)):
        ph, ph2 = rnd.random(), rnd.random()
        sk.anim('idle', f'g{gi}', 'alpha', lambda t, ph=ph: pulse(t, 2.0, ph, 10))
        sk.anim('idle', f'g{gi}', 'scale', lambda t, ph=ph: (0.3 + 0.9 * pulse(t, 2.0, ph, 6),) * 2)
        sk.anim('idle', f'g{gi}', 'rotate', lambda t: 90 * t / 4)
        sk.anim('win', f'g{gi}', 'alpha', lambda t, ph=ph2: pulse(t, 0.6, ph, 5))
        sk.anim('win', f'g{gi}', 'scale', lambda t, ph=ph2: (0.4 + 1.2 * pulse(t, 0.6, ph, 4),) * 2)
        sk.anim('win', f'g{gi}', 'rotate', lambda t: 90 * t / 1.2)

    def punch(t):
        if t < 0.12:
            return 1 + 0.12 * out_cubic(t / 0.12)
        u = t - 0.12
        return 1 + 0.12 * math.exp(-6 * u) * math.cos(16 * u)
    sk.anim('win', 'logo', 'scale', lambda t: (punch(t),) * 2)
    sk.anim('win', 'flash', 'alpha', lambda t: 0.8 * math.exp(-9 * t) if t > 0.02 else 0.8 * t / 0.02)
    sk.anim('win', 'halo', 'alpha', lambda t: 0.45 + 0.4 * math.exp(-4 * t))
    sk.anim('win', 'rays', 'alpha', lambda t: 0.4 + 0.25 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2)
    sk.anim('win', 'fxback', 'rotate', lambda t: -22.5 * t / 1.2)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# backgrounds (design-canvas space, anchored to #stage)

def bg_common(sk, W, H, col, P):
    sk.image('glow', tint(soft_glow(512), col))
    sk.res_of['glow'] = 0.25
    sk.hidden_slot('backglow', 'root', 'glow', w=W * 1.3, h=H * 1.1, y=H * 0.05, blend='additive')
    sk.anim('idle', 'backglow', 'alpha', lambda t: 0.22 + 0.14 * (1 - math.cos(2 * math.pi * t / 4)) / 2)


def twinkles(sk, W, H, n, rnd, P, col, ylo, yhi, spread, sizes=(24, 56), region='twinkle'):
    for i in range(n):
        x = rnd.uniform(-0.5, 0.5) * W * spread
        y = rnd.uniform(ylo, yhi) * H
        b = sk.bone(f'tw{i}', x=x, y=y)
        sk.hidden_slot(f'tw{i}', b, region, w=rnd.uniform(*sizes), blend='additive')
        ph = rnd.random()
        per = P / rnd.choice((2, 4, 4, 8))
        sk.anim('idle', f'tw{i}', 'alpha', lambda t, ph=ph, per=per: pulse(t, per, ph, 6))
        sk.anim('idle', b, 'scale', lambda t, ph=ph, per=per: (0.4 + 0.8 * pulse(t, per, ph, 4),) * 2)


def bokeh(sk, W, H, n, rnd, P, spread, ylo=-0.5, yhi=0.5):
    for i in range(n):
        x0 = rnd.uniform(-0.5, 0.5) * W * spread
        y0 = rnd.uniform(ylo, yhi) * H
        sz = rnd.uniform(0.06, 0.15) * min(W, H) * 1.4
        b = sk.bone(f'bk{i}', x=x0, y=y0)
        sk.hidden_slot(f'bk{i}', b, 'bokeh2' if i % 3 == 0 else 'bokeh', w=sz, blend='additive')
        k = rnd.choice((1, 1, 2))
        ph = rnd.random()
        amp = rnd.uniform(0.02, 0.05) * W
        sk.anim('idle', b, 'translate', lambda t, x0=x0, y0=y0, k=k, ph=ph, amp=amp:
                (x0 + amp * math.sin(2 * math.pi * (k * t / P + ph)), y0 + amp * math.cos(2 * math.pi * (t / P + ph))))
        sk.anim('idle', f'bk{i}', 'alpha', lambda t, ph=ph: 0.08 + 0.12 * (1 - math.cos(2 * math.pi * (t / P * 2 + ph))) / 2)


def build_bg_embers(name, out):
    W, H = DESIGN[name]
    spread = 1.5
    P = 8.0
    sk = BFx(name, W, H, 0.7, {'idle': P}, out)
    rnd = random.Random(name + 'embers')
    bg_common(sk, W, H, (200, 70, 30), P)

    # god rays from above the logo
    sk.image('rays', rays(1024, n=14, col=(255, 200, 120), width=0.3))
    sk.res_of['rays'] = 0.25
    rb = sk.bone('rays', y=H * 0.62)
    sk.hidden_slot('rays', rb, 'rays', w=max(W, H) * 1.6, blend='additive')
    sk.anim('idle', rb, 'rotate', lambda t: 6 * math.sin(2 * math.pi * t / P))
    sk.anim('idle', 'rays', 'alpha', lambda t: 0.10 + 0.07 * (1 - math.cos(2 * math.pi * t / (P / 2))) / 2)

    sk.image('bokeh', tint(soft_glow(128), (255, 170, 80)))
    sk.image('bokeh2', tint(soft_glow(128), (255, 90, 60)))
    bokeh(sk, W, H, 10, rnd, P, spread)

    sk.image('twinkle', star4(128, col=(255, 226, 160)))
    twinkles(sk, W, H, 26, rnd, P, None, -0.1, 0.55, spread)

    # embers rising from below
    sk.image('ember', glow_dot(64, core=0.3, col=(255, 160, 60)))
    sk.image('ember2', glow_dot(64, core=0.3, col=(255, 214, 120)))
    bot, top = -H * 0.7, H * 0.7
    span = top - bot
    for i in range(70):
        x0 = rnd.uniform(-0.5, 0.5) * W * spread
        k = rnd.choice((1, 1, 2))
        ph0 = rnd.random()
        sway = rnd.uniform(12, 50)
        m = rnd.choice((1, 2))
        sph = rnd.random()
        size = rnd.uniform(12, 32)
        amax = rnd.uniform(0.45, 0.95)
        fl = rnd.choice((4, 8, 16))
        b = sk.bone(f'e{i}', x=x0, y=bot)
        sk.hidden_slot(f'e{i}', b, 'ember2' if i % 3 else 'ember', w=size, blend='additive')

        def pos(t, x0=x0, k=k, ph0=ph0, sway=sway, m=m, sph=sph):
            p = frac(k * t / P + ph0)
            return (x0 + sway * math.sin(2 * math.pi * (m * t / P + sph)), bot + span * p)

        def al(t, k=k, ph0=ph0, amax=amax, fl=fl, sph=sph):
            p = frac(k * t / P + ph0)
            flick = 0.75 + 0.25 * math.sin(2 * math.pi * (fl * t / P + sph))
            return amax * flick * clamp(min(p, 1 - p) / 0.12) * (1 - 0.5 * p)
        sk.anim('idle', b, 'translate', pos)
        sk.anim('idle', f'e{i}', 'alpha', al)
    sk.write()
    return sk


def build_bg_night(name, out):
    W, H = DESIGN[name]
    mob = name == 'bg_mob'
    spread = 1.5
    P = 8.0
    sk = BFx(name, W, H, 0.7, {'idle': P}, out)
    rnd = random.Random(name + 'night')
    bg_common(sk, W, H, (50, 110, 255), P)

    sk.image('bokeh', tint(soft_glow(128), (255, 196, 90)))
    sk.image('bokeh2', tint(soft_glow(128), (110, 170, 255)))
    # city lights sit low on the skyline
    bokeh(sk, W, H, 12, rnd, P, spread, -0.35, -0.05)

    sk.image('twinkle', star4(128, col=(220, 236, 255)))
    twinkles(sk, W, H, 46, rnd, P, None, 0.05, 0.75, spread, sizes=(18, 46))

    # water glints: short horizontal flickers in the bay
    sk.image('glint', hband(128, 16, sigma=0.3, taper=0.3, col=(255, 220, 150)))
    for i in range(26):
        x = rnd.uniform(-0.5, 0.5) * W * spread
        y = -H * rnd.uniform(0.22, 0.42) if not mob else -H * rnd.uniform(0.05, 0.3)
        b = sk.bone(f'wg{i}', x=x, y=y)
        sk.hidden_slot(f'wg{i}', b, 'glint', w=rnd.uniform(30, 80), blend='additive')
        ph = rnd.random()
        per = P / rnd.choice((4, 8, 8))
        sk.anim('idle', f'wg{i}', 'alpha', lambda t, ph=ph, per=per: 0.65 * pulse(t, per, ph, 3))
        sk.anim('idle', b, 'scale', lambda t, ph=ph, per=per: (0.5 + 0.7 * pulse(t, per, ph, 2), 1.0))

    # shooting stars
    sk.image('comet', spark(256, 24))
    for i, (t0, x0, y0, ang) in enumerate(((1.4, -0.42, 0.46, -18), (5.2, 0.12, 0.52, -24))):
        if mob:
            x0, y0 = x0 * 0.9, y0 + 0.08
        b = sk.bone(f'ss{i}', x=x0 * W * spread, y=y0 * H, rot=ang + 180)
        sk.hidden_slot(f'ss{i}', b, 'comet', w=W * (0.26 if not mob else 0.42), h=10, blend='additive')
        dist = W * 0.5 * (1 if not mob else 0.8)
        dx, dy = math.cos(math.radians(ang)) * dist, math.sin(math.radians(ang)) * dist
        X0, Y0 = x0 * W * spread, y0 * H
        sk.anim('idle', b, 'translate', lambda t, t0=t0, X0=X0, Y0=Y0, dx=dx, dy=dy:
                (X0 + dx * clamp((t - t0) / 0.9), Y0 + dy * clamp((t - t0) / 0.9)))
        sk.anim('idle', f'ss{i}', 'alpha', lambda t, t0=t0: 0.0 if not t0 <= t <= t0 + 0.9 else
                math.sin(math.pi * (t - t0) / 0.9) ** 0.7)

    # fireworks
    sk.image('fspark', spark(96, 20))
    sk.image('fflash', soft_glow(256))
    sk.res_of['fflash'] = 0.4
    if mob:
        shows = [(0.6, -0.30, 0.44, 'ffd76a'), (3.3, 0.30, 0.47, 'ff6fd8'), (6.0, 0.0, 0.62, '6fd8ff')]
    else:
        shows = [(0.6, -0.44, 0.30, 'ffd76a'), (3.3, 0.45, 0.26, 'ff6fd8'), (6.0, -0.40, 0.08, '6fd8ff')]
    LIFE = 1.7
    for fi, (t0, fx, fy, col) in enumerate(shows):
        cx, cy = fx * W * (1 if mob else 1.0), fy * H
        fb = sk.bone(f'fw{fi}', x=cx, y=cy)
        sk.hidden_slot(f'fw{fi}fl', fb, 'fflash', col, w=W * (0.22 if not mob else 0.4), blend='additive')
        sk.anim('idle', f'fw{fi}fl', 'alpha', lambda t, t0=t0: 0.0 if not t0 <= t <= t0 + 0.6 else
                0.7 * math.exp(-5 * (t - t0)))
        N = 18
        R = H * (0.16 if not mob else 0.12)
        for k in range(N):
            a = 2 * math.pi * k / N + rnd.uniform(-0.1, 0.1)
            sp = rnd.uniform(0.75, 1.05)
            name_ = f'fw{fi}_{k}'
            b = sk.bone(name_, x=cx, y=cy, rot=math.degrees(a) + 180)
            sk.hidden_slot(name_, b, 'fspark', col, w=70, h=16, blend='additive')

            def fpos(t, t0=t0, a=a, sp=sp, cx=cx, cy=cy, R=R):
                u = clamp((t - t0) / LIFE)
                d = R * sp * out_cubic(min(1, u * 1.6))
                g = H * 0.07 * u * u
                return (cx + math.cos(a) * d, cy + math.sin(a) * d - g)

            sk.anim('idle', b, 'translate', fpos)
            sk.anim('idle', name_, 'alpha', lambda t, t0=t0: 0.0 if not t0 <= t <= t0 + LIFE else
                    max(0.0, 1 - (t - t0) / LIFE) ** 1.5 * (0.7 + 0.3 * math.sin(40 * t)))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# win lines (reel-window space)

def reel_dims(cfg, art):
    cab = Image.open(os.path.join(art, 'cabinet.png'))
    _, _, ww, wh = cfg['win']
    ratio = (ww * cab.width) / (wh * cab.height)
    return 1000.0, round(1000.0 / ratio, 1)


PAYLINES = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]]


def build_winlines(cfg, art, out):
    RW, RH = reel_dims(cfg, art)
    COL_X = [-RW / 3, 0.0, RW / 3]
    ROW_Y = [RH / 3, 0.0, -RH / 3]
    CELL_W, CELL_H = RW / 3, RH / 3
    IN, LOOP = 0.7, 1.2
    clips = {}
    for n in range(1, 6):
        clips[f'line{n}_in'] = IN
        clips[f'line{n}_loop'] = LOOP
    sk = BFx('winlines', RW, RH, 1.0, clips, out)

    sk.image('bglow', hband(512, 128, sigma=0.26, taper=0.04))
    sk.res_of['bglow'] = 0.5
    sk.image('bcore', hband(512, 32, sigma=0.22, taper=0.02))
    sk.res_of['bcore'] = 0.5
    for j in range(3):
        sk.image(f'wave{j}', wave_ribbon(1024, 80, 5.5, j * 2.1))
        sk.res_of[f'wave{j}'] = 0.8
    sk.image('head', glow_dot(256, core=0.22, col=(255, 255, 255)))
    sk.image('comet', spark(256, 40))
    sk.image('ring', ring(256))
    sk.image('flare', star4(256, thin=0.025))
    fw, fh = int(CELL_W * 0.94), int(CELL_H * 0.92)
    sk.image('cframe', rrect_frame(fw, fh, 22, 6, 9))
    sk.image('star', star8(96))
    sk.image('cglow', soft_glow(256))
    sk.res_of['cglow'] = 0.4

    for n, rows in enumerate(PAYLINES, start=1):
        col = cfg['line_cols'][n - 1]
        pts = [(COL_X[c], ROW_Y[r]) for c, r in enumerate(rows)]
        (x0, y0), (x2, y2) = pts[0], pts[2]
        ang = math.atan2(y2 - y0, x2 - x0)
        ux, uy = math.cos(ang), math.sin(ang)
        ext = 0.15 * RW
        sx, sy = x0 - ux * ext, y0 - uy * ext
        ex, ey = x2 + ux * ext, y2 + uy * ext
        L = math.hypot(ex - sx, ey - sy)
        cell_u = [math.hypot(px - sx, py - sy) / L for px, py in pts]

        P = f'L{n}'
        beam = sk.bone(f'{P}beam', x=sx, y=sy, rot=math.degrees(ang))
        sk.hidden_slot(f'{P}glow', beam, 'bglow', col, w=L, h=110, x=L / 2, blend='additive')
        for j in range(3):
            sk.hidden_slot(f'{P}wave{j}', beam, f'wave{j}', 'ffe7a6' if j != 1 else col, w=L, h=70, x=L / 2,
                           blend='additive')
        sk.hidden_slot(f'{P}core', beam, 'bcore', w=L, h=20, x=L / 2, blend='additive')

        cells = []
        for ci, (px, py) in enumerate(pts):
            C = f'{P}c{ci}'
            cb = sk.bone(C, x=px, y=py)
            sk.hidden_slot(f'{C}glow', cb, 'cglow', col, w=CELL_W * 1.2, h=CELL_H * 1.35, blend='additive')
            fb = sk.bone(f'{C}f', parent=cb)
            sk.hidden_slot(f'{C}frame', fb, 'cframe', col, w=fw + 54, blend='additive')
            rb = sk.bone(f'{C}r', parent=cb)
            sk.hidden_slot(f'{C}ring', rb, 'ring', col, w=CELL_H * 1.1, blend='additive')
            stars = []
            for s in range(8):
                a = 2 * math.pi * (s + 0.4 * ci) / 8
                sb = sk.bone(f'{C}s{s}', parent=cb)
                sk.hidden_slot(f'{C}s{s}', sb, 'star', w=30 + 8 * (s % 2), blend='additive')
                stars.append((sb, a))
            flb = sk.bone(f'{C}fl', parent=cb)
            sk.hidden_slot(f'{C}flare', flb, 'flare', w=CELL_H * 1.15, blend='additive')
            cells.append((C, cb, fb, rb, flb, stars))

        hb = sk.bone(f'{P}head', x=sx, y=sy)
        sk.hidden_slot(f'{P}head', hb, 'head', w=150, blend='additive')
        heads = []
        for k in range(2):
            cbn = sk.bone(f'{P}comet{k}', x=sx, y=sy, rot=math.degrees(ang))
            sk.hidden_slot(f'{P}comet{k}', cbn, 'comet', w=170, h=34, blend='additive')
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
            return 0.72 + 0.2 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2

        def sy_loop(t):
            return 1 + 0.18 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2

        sk.anim(INN, beam, 'scale', lambda t: (max(0.001, tip(t)), 1.25 - 0.25 * clamp(t / 0.5)))
        sk.anim(LP, beam, 'scale', lambda t: (1.0, sy_loop(t)))
        sk.anim(INN, f'{P}glow', 'alpha', lambda t: seg(t, 0, 0.12, 0, 1) if t < 0.4 else seg(t, 0.4, IN, 1, g_loop(0)))
        sk.anim(LP, f'{P}glow', 'alpha', g_loop)
        sk.anim(INN, f'{P}core', 'alpha', lambda t: seg(t, 0, 0.08, 0, 1))
        sk.anim(LP, f'{P}core', 'alpha', lambda t: 0.85 + 0.15 * math.cos(2 * math.pi * t / 0.3))

        # three phase-shifted waves cross-fade: reads as a twisting gold ribbon
        def wave_a(t, j):
            return 0.25 + 0.75 * (1 + math.cos(2 * math.pi * (t / 0.6 - j / 3))) / 2
        for j in range(3):
            sk.anim(INN, f'{P}wave{j}', 'alpha', lambda t, j=j: wave_a(t, j) * clamp((t - 0.12) / 0.25) * 0.9)
            sk.anim(LP, f'{P}wave{j}', 'alpha', lambda t, j=j: wave_a(t + IN, j) * 0.9)

        sk.anim(INN, hb, 'translate', lambda t: (sx + (ex - sx) * tip(t), sy + (ey - sy) * tip(t)))
        sk.anim(INN, f'{P}head', 'alpha', lambda t: seg(t, 0, 0.05, 0, 1) if t < DRAW else seg(t, DRAW, DRAW + 0.2, 1, 0))
        sk.anim(INN, hb, 'scale', lambda t: (1 + 0.1 * math.sin(t * 40) + (0.6 if t > DRAW else 0) * seg(t, DRAW, DRAW + 0.2, 1, 0, linear_ease),) * 2)
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

        for ci, (C, cb, fb, rb, flb, stars) in enumerate(cells):
            tk = at(cell_u[ci])

            def fr_loop(t):
                return 0.75 + 0.25 * math.cos(2 * math.pi * t / 0.6)

            def fl_loop_s(t):
                return 0.75 + 0.12 * math.cos(2 * math.pi * t / 0.6)

            sk.anim(INN, f'{C}glow', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.1, 0, 0.8) if t < tk + 0.2 else seg(t, tk + 0.2, IN, 0.8, 0.45))
            sk.anim(LP, f'{C}glow', 'alpha', lambda t: 0.25 + 0.2 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2)
            sk.anim(INN, f'{C}frame', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.12, 0, 1) if t < tk + 0.12 else seg(t, tk + 0.12, IN, 1, fr_loop(0)))
            sk.anim(LP, f'{C}frame', 'alpha', fr_loop)
            sk.anim(INN, fb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.3, 1.18, 1.0),) * 2)
            sk.anim(LP, fb, 'scale', lambda t: (1 + 0.025 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2,) * 2)

            sk.anim(INN, f'{C}ring', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.42, 1, 0))
            sk.anim(INN, rb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.42, 0.25, 1.7),) * 2)
            sk.anim(LP, f'{C}ring', 'alpha', lambda t: seg(t % 0.6, 0, 0.6, 0.5, 0, linear_ease))
            sk.anim(LP, rb, 'scale', lambda t: (seg(t % 0.6, 0, 0.6, 0.5, 1.5, out_cubic),) * 2)

            sk.anim(INN, f'{C}flare', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.05, 0, 1) if t < tk + 0.15 else seg(t, tk + 0.15, IN, 1, 0.55))
            sk.anim(INN, flb, 'scale', lambda t, tk=tk: (0.01 if t < tk else (seg(t, tk, tk + 0.18, 0.1, 1.5, out_back) if t < tk + 0.18 else seg(t, tk + 0.18, IN, 1.5, fl_loop_s(0))),) * 2)
            sk.anim(INN, flb, 'rotate', lambda t, tk=tk: 0.0 if t < tk else -45 * seg(t, tk, IN, 1, 0))
            sk.anim(LP, f'{C}flare', 'alpha', lambda t: 0.55 + 0.25 * math.cos(2 * math.pi * t / 0.6))
            sk.anim(LP, flb, 'scale', lambda t: (fl_loop_s(t),) * 2)
            sk.anim(LP, flb, 'rotate', lambda t: -90 * t / LOOP)

            for s, (sb, a) in enumerate(stars):
                dist = CELL_H * (0.75 + 0.18 * (s % 3))

                def st_pos(t, tk=tk, a=a, dist=dist):
                    d = 0 if t < tk else dist * out_cubic(clamp((t - tk) / 0.5))
                    return (math.cos(a) * d * 1.25, math.sin(a) * d)
                sk.anim(INN, sb, 'translate', st_pos)
                sk.anim(INN, sb, 'rotate', lambda t, tk=tk: 0.0 if t < tk else 220 * (t - tk))
                sk.anim(INN, f'{C}s{s}', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.5, 1, 0, in_cubic_ease))
                sk.anim(LP, f'{C}s{s}', 'alpha', lambda t: 0.0)
                sk.anim(LP, sb, 'translate', lambda t: (0.0, 0.0))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# coins

def coin_flip(t, spd, ph):
    """scaleX of a spinning coin; never exactly 0 (Spine dislikes it)."""
    v = math.cos(2 * math.pi * (spd * t + ph))
    return v if abs(v) > 0.06 else (0.06 if v >= 0 else -0.06)


def build_burst(cfg, art, out):
    RW, RH = reel_dims(cfg, art)
    D = 1.6
    sk = BFx('burst', RW, RH, 1.0, {'win': D}, out)
    rnd = random.Random(31)
    sk.image('coin', coin(128))
    sk.image('star', star8(96))
    sk.image('flash', tint(soft_glow(256), GOLD))
    sk.res_of['flash'] = 0.4
    sk.image('ring', ring(256, col=(255, 226, 150)))

    sk.hidden_slot('flash', 'root', 'flash', w=RW * 0.9, h=RH * 1.1, blend='additive')
    sk.anim('win', 'flash', 'alpha', lambda t: seg(t, 0, 0.08, 0, 0.5) if t < 0.08 else 0.5 * math.exp(-4 * (t - 0.08)))
    rb = sk.bone('ring')
    sk.hidden_slot('ring', rb, 'ring', w=RH * 0.9, blend='additive')
    sk.anim('win', 'ring', 'alpha', lambda t: seg(t, 0, 0.6, 1, 0))
    sk.anim('win', rb, 'scale', lambda t: (seg(t, 0, 0.6, 0.3, 2.6),) * 2)

    for i in range(16):
        a = 2 * math.pi * i / 16 + rnd.uniform(-0.12, 0.12)
        dist = RH * rnd.uniform(0.55, 0.85)
        b = sk.bone(f'st{i}')
        sk.hidden_slot(f'st{i}', b, 'star', w=rnd.uniform(34, 56), blend='additive')
        sk.anim('win', b, 'translate', lambda t, a=a, dist=dist: (math.cos(a) * dist * 1.4 * out_cubic(clamp(t / 0.8)),
                                                                   math.sin(a) * dist * out_cubic(clamp(t / 0.8))))
        sk.anim('win', b, 'rotate', lambda t: 300 * t)
        sk.anim('win', f'st{i}', 'alpha', lambda t: seg(t, 0.1, 1.0, 1, 0, in_cubic_ease) if t > 0.1 else 1.0)

    G = RH * 3.2  # gravity, units/s^2
    for i in range(14):
        # fan out to the sides: the win amount sits in the middle of the window
        side = -1 if i % 2 else 1
        vx = side * rnd.uniform(0.55, 1.0) * RW * 0.55
        vy = rnd.uniform(0.9, 1.25) * RH * 1.55
        delay = rnd.uniform(0, 0.18)
        spd, ph = rnd.uniform(1.6, 2.6), rnd.random()
        sz = rnd.uniform(70, 100)
        b = sk.bone(f'cn{i}', x=side * RW * 0.22, y=-RH * 0.1)

        x0 = side * RW * 0.22

        def cpos(t, vx=vx, vy=vy, delay=delay, x0=x0):
            u = max(0.0, t - delay)
            return (x0 + vx * u, -RH * 0.1 + vy * u - G * u * u / 2)
        sk.hidden_slot(f'cn{i}', b, 'coin', w=sz)
        sk.anim('win', b, 'translate', cpos)
        sk.anim('win', b, 'scale', lambda t, spd=spd, ph=ph: (coin_flip(t, spd, ph), 1.0))
        sk.anim('win', f'cn{i}', 'alpha', lambda t, delay=delay: 0.0 if t < delay else
                (seg(t, delay, delay + 0.06, 0, 1) if t < D - 0.3 else seg(t, D - 0.3, D, 1, 0)))
    sk.write()
    return sk


def build_shower(out):
    S = 1000.0
    P = 2.0
    sk = BFx('shower', S, S, 1.0, {'start': P, 'rain': P}, out)
    rnd = random.Random(77)
    sk.image('coin', coin(128))
    sk.image('star', star8(96))
    sk.image('dot', glow_dot(64, core=0.3, col=GOLD))
    top, bot = S * 0.95, -S * 0.95
    span = top - bot

    def entered(t, k, ph):
        # first time this particle wraps from the top: hidden in `start` before it
        return t >= (1 - ph) / k * P - 1e-6

    for i in range(60):
        x0 = rnd.uniform(-0.92, 0.92) * S
        k = rnd.choice((1, 1, 2))
        ph = rnd.random()
        spd, fph = rnd.uniform(1.2, 2.4), rnd.random()
        sway = rnd.uniform(10, 40)
        sz = rnd.uniform(50, 90)
        rot0 = rnd.uniform(-25, 25)
        b = sk.bone(f'c{i}', x=x0, y=top, rot=rot0)
        sk.hidden_slot(f'c{i}', b, 'coin', w=sz)

        def pos(t, x0=x0, k=k, ph=ph, sway=sway):
            p = frac(k * t / P + ph)
            return (x0 + sway * math.sin(2 * math.pi * (t / P + ph)), top - span * p)
        for clip in ('start', 'rain'):
            sk.anim(clip, b, 'translate', pos)
            sk.anim(clip, b, 'scale', lambda t, spd=spd, fph=fph: (coin_flip(t, spd, fph), 1.0))
        sk.anim('start', f'c{i}', 'alpha', lambda t, k=k, ph=ph: 1.0 if entered(t, k, ph) else 0.0)
        sk.anim('rain', f'c{i}', 'alpha', lambda t: 1.0)

    for i in range(30):
        x0 = rnd.uniform(-0.95, 0.95) * S
        y0 = rnd.uniform(-0.9, 0.9) * S
        b = sk.bone(f's{i}', x=x0, y=y0)
        sk.hidden_slot(f's{i}', b, 'star' if i % 2 else 'dot', w=rnd.uniform(26, 52), blend='additive')
        ph = rnd.random()
        per = P / rnd.choice((1, 2))
        for clip in ('start', 'rain'):
            sk.anim(clip, f's{i}', 'alpha', lambda t, ph=ph, per=per: pulse(t, per, ph, 5))
            sk.anim(clip, b, 'scale', lambda t, ph=ph, per=per: (0.3 + 0.9 * pulse(t, per, ph, 3),) * 2)
            sk.anim(clip, b, 'rotate', lambda t: 180 * t / P)
    sk.write()
    return sk


# --------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:]]
    preview = None
    if '--preview' in args:
        i = args.index('--preview')
        preview = args[i + 1]
        del args[i:i + 2]
        os.makedirs(preview, exist_ok=True)
    game = args[0]
    only = args[1:]
    cfg = GAMES[game]
    art = os.path.join(FRONT, game, 'img')
    out = os.path.join(FRONT, game, 'fx')
    built = {}

    def want(k):
        return not only or k in only
    if want('frame'):
        built['frame'] = build_frame(cfg, art, out)
    if want('logo'):
        built['logo'] = build_logo(cfg, art, out)
    if want('bg'):
        fn = build_bg_embers if cfg['theme'] == 'embers' else build_bg_night
        built['bg_desk'] = fn('bg_desk', out)
        built['bg_mob'] = fn('bg_mob', out)
    if want('winlines'):
        built['winlines'] = build_winlines(cfg, art, out)
    if want('burst'):
        built['burst'] = build_burst(cfg, art, out)
    if want('shower'):
        built['shower'] = build_shower(out)
    if not preview:
        return
    cab = Image.open(os.path.join(art, 'cabinet.png'))
    logo = Image.open(os.path.join(art, 'logo.png'))
    for name, sk in built.items():
        for clip, dur in sk.durs.items():
            if name == 'winlines' and not clip.startswith(('line1', 'line4')):
                continue
            under = {'frame': cab, 'logo': logo}.get(name)
            box = (-sk.w / 2, -sk.h / 2, sk.w, sk.h)
            frames = [render(sk, clip, dur * k / 6, (800, int(800 * sk.h / sk.w)), under=under,
                             under_box=box if under is not None else None) for k in range(6)]
            sheet = Image.new('RGB', (800 * 2, frames[0].height * 3))
            for k, f in enumerate(frames):
                sheet.paste(f.convert('RGB'), ((k % 2) * 800, (k // 2) * f.height))
            sheet.save(os.path.join(preview, f'{game}_{name}_{clip}.jpg'), quality=80)


if __name__ == '__main__':
    main()
