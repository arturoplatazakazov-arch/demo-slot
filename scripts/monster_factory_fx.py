"""Monster Factory: in-game Spine FX generated in code (the house FX pack).

Same pipeline as scripts/ice_spin_deluxe_fx.py / gold_of_baku_fx.py (their Fx
class, image helpers and software preview are reused). Skeletons into
front/img/monster-factory/fx/, each authored in the pixel space of the DOM
element js/monster-factory/spine-fx.js anchors it to, so CSS stays the only
source of layout truth:

  bg_desk / bg_mob  design-canvas px (1932x940 / 780x1416, anchored to #stage).
                    `idle` (8s): lamp light cones, goo bubbles rising off the
                    side vats, welding sparks, drifting dust. `bonus` (8s): the
                    purple lab — lightning arcs over the side machinery, violet
                    bubbles, flicker flashes.
  frame_desk/_mob   frame_*.png px. Outer halo, light sweep through the painted
                    steel, glints on the bolts, the four signal lamps blinking,
                    hazard-yellow comets running round the reel window. `idle`
                    (4s) and `win` (1.2s).
  logo              logo.png px — gold_of_baku_fx.build_logo as is: the logo +
                    shadow, halo, sweep, glints, rays. `idle` (4s), `win` (1.2s).
  symbols           one 124x124 symbol box (= the img inside a cell on both
                    layouts). One 0.7s clip per symbol code (= slot.js
                    WIN_PULSE_MS), starting and ending on the static tile:
                    monsters hop, letters jiggle, wild slams, scatter swings,
                    goo cores spin; halo, rays, ring, sparks, light sweep.
  burst             grid px (968x660): goo-eye coin fountain + star burst for a
                    win under the popup threshold. `win` (1.6s).
  shower            1000x1000 screen box: coin rain for the win popups. `start`
                    (2s, coins enter from the top) and `rain` (2s loop).

Every slot an animation touches starts transparent in the setup pose.

    .venv/bin/python scripts/monster_factory_fx.py [names...] [--preview DIR]
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
    Fx, bolt, bright_points, cone, glow_dot, highlight, in_cubic_ease, linear_ease, render,
    ring, rrect_frame, star4, strips, sym_motion, tint,
)
import gold_of_baku_fx  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'monster-factory')
ART = os.path.join(ROOT, 'img')
SYM = os.path.join(ROOT, 'symbols')
OUT = os.path.join(ROOT, 'fx')

GOLD = (255, 204, 96)
ORANGE = (255, 150, 40)
HAZARD = (255, 206, 40)
GOO = [(120, 255, 70), (190, 90, 255), (255, 150, 40), (70, 170, 255)]
VIOLET = (180, 110, 255)

DESIGN = {'bg_desk': (1932, 940), 'bg_mob': (780, 1416)}
GRID = (968, 660)  # desktop reel grid; the mobile one (662x534) is close enough in aspect
SYMBOL_BOX = 124

# Must match scripts/monster_factory_ui.py's frames: (png, opening x, y, w, h).
FRAMES = {
    'frame_desk': ('frame_desk.png', 62, 74, 968, 660),
    'frame_mob': ('frame_mob.png', 46, 58, 662, 534),
}


def frac(x):
    return x - math.floor(x)


class MFx(Fx):
    def __init__(self, name, w, h, res, clips, quantize=False):
        super().__init__(name, w, h, res, clips, quantize)
        self.out_dir = OUT


# --------------------------------------------------------------------------
# images

def eye_coin(size=128):
    """Gold coin embossed with the factory's one-eyed monster face."""
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
            lit = clamp(0.62 - 0.38 * (dx + dy) / 1.4)
            if r > 0.84:
                k = 0.55 + 0.45 * clamp(1 - (r - 0.84) / 0.14) * lit
            elif r > 0.78:
                k = 0.42
            else:
                k = 0.66 + 0.34 * lit
            px[x, y] = (int(255 * min(1, k * 1.05)), int(196 * k + 22), int(56 * k), 255)
    d = ImageDraw.Draw(out)
    emb = (176, 96, 12, 255)
    # head blob with two little horns, one big eye
    d.ellipse([c - S * 0.3, c - S * 0.24, c + S * 0.3, c + S * 0.34], fill=emb)
    d.polygon([(c - S * 0.26, c - S * 0.12), (c - S * 0.3, c - S * 0.36), (c - S * 0.12, c - S * 0.2)], fill=emb)
    d.polygon([(c + S * 0.26, c - S * 0.12), (c + S * 0.3, c - S * 0.36), (c + S * 0.12, c - S * 0.2)], fill=emb)
    d.ellipse([c - S * 0.14, c - S * 0.1, c + S * 0.14, c + S * 0.16], fill=(255, 238, 168, 255))
    d.ellipse([c - S * 0.06, c - S * 0.02, c + S * 0.06, c + S * 0.1], fill=(120, 50, 6, 255))
    d.arc([c - S * 0.16, c + S * 0.08, c + S * 0.16, c + S * 0.28], 20, 160, fill=(255, 238, 168, 255), width=S // 40)
    sp = Image.new('L', (S, S))
    ImageDraw.Draw(sp).ellipse([S * 0.2, S * 0.14, S * 0.56, S * 0.4], fill=120)
    sp = sp.filter(ImageFilter.GaussianBlur(S * 0.05))
    white = Image.new('RGBA', (S, S), (255, 255, 255, 0))
    white.putalpha(ImageChops.multiply(sp, out.getchannel('A')))
    out.alpha_composite(white)
    return out.resize((size, size), Image.LANCZOS)


def bubble(size=96, col=(120, 255, 70)):
    """A glossy goo bubble: coloured rim, clear-ish body, white specular."""
    S = size * 4
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    a = Image.new('L', (S, S))
    d = ImageDraw.Draw(a)
    d.ellipse([S * 0.08, S * 0.08, S * 0.92, S * 0.92], fill=110)
    d.ellipse([S * 0.16, S * 0.16, S * 0.84, S * 0.84], fill=50)
    a = a.filter(ImageFilter.GaussianBlur(S * 0.03))
    body = Image.new('RGBA', (S, S), col + (0,))
    body.putalpha(a)
    out.alpha_composite(body)
    sp = Image.new('L', (S, S))
    ImageDraw.Draw(sp).ellipse([S * 0.26, S * 0.2, S * 0.48, S * 0.38], fill=230)
    sp = sp.filter(ImageFilter.GaussianBlur(S * 0.02))
    w = Image.new('RGBA', (S, S), (255, 255, 255, 0))
    w.putalpha(sp)
    out.alpha_composite(w)
    return out.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------
# backgrounds

def build_bg(name):
    W, H = DESIGN[name]
    mob = name == 'bg_mob'
    spread = 1.6 if not mob else 1.25
    P = 8.0
    sk = MFx(name, W, H, 0.7, {'idle': P, 'bonus': P})
    rnd = random.Random(name)

    def both(target, prop, idle_fn, bonus_fn):
        sk.anim('idle', target, prop, idle_fn)
        sk.anim('bonus', target, prop, bonus_fn)

    zero = lambda t: 0.0  # noqa: E731

    # back glow: warm in the factory, violet in the lab
    sk.image('glow', soft_glow(512))
    sk.res_of['glow'] = 0.25
    sk.hidden_slot('warm', 'root', 'glow', 'ff8a2a', w=W * 1.3, h=H * 1.1, y=-H * 0.1, blend='additive')
    sk.hidden_slot('cold', 'root', 'glow', 'a050ff', w=W * 1.3, h=H * 1.1, y=-H * 0.1, blend='additive')
    both('warm', 'alpha', lambda t: 0.16 + 0.1 * (1 - math.cos(2 * math.pi * t / 4)) / 2, zero)
    both('cold', 'alpha', zero, lambda t: 0.2 + 0.12 * (1 - math.cos(2 * math.pi * t / 4)) / 2)

    # light cones from the two ceiling lamps
    sk.image('cone', cone(256, 512, (255, 220, 160)))
    sk.res_of['cone'] = 0.4
    for i, fx in enumerate((-0.27, 0.27) if not mob else (-0.3, 0.3)):
        b = sk.bone(f'cone{i}', x=fx * W, y=H * 0.5)
        sk.hidden_slot(f'cone{i}', b, 'cone', w=W * (0.26 if not mob else 0.5), h=H * (0.95 if not mob else 0.7),
                       y=-H * (0.475 if not mob else 0.35), blend='additive')
        ph = rnd.random()
        # old lamps: steady with the odd flicker
        def flick(t, ph=ph, base=0.18):
            u = frac(t / P + ph)
            dip = 0.6 if 0.42 < u < 0.44 or 0.46 < u < 0.47 else 1.0
            return base * dip * (0.9 + 0.1 * math.sin(2 * math.pi * 3 * t / P))
        both(f'cone{i}', 'alpha', flick, lambda t, ph=ph: flick(t, ph, 0.12))
        sk.anim('idle', b, 'rotate', lambda t, ph=ph: 2.5 * math.sin(2 * math.pi * (t / P + ph)))
        sk.anim('bonus', b, 'rotate', lambda t, ph=ph: 2.5 * math.sin(2 * math.pi * (t / P + ph)))

    # goo bubbles rising off the vats on both sides
    for ci, col in enumerate(GOO):
        sk.image(f'bub{ci}', bubble(96, col))
        sk.image(f'bdot{ci}', glow_dot(64, core=0.28, col=col))
    sk.image('bubv', bubble(96, VIOLET))
    bot, top = -H * 0.55, H * 0.35
    span = top - bot
    for i in range(44):
        side = -1 if i % 2 else 1
        # the vats stand at the screen edges: 0-14% / 86-100% of the width
        x0 = side * rnd.uniform(0.36, 0.49) * W
        if mob:
            x0 = side * rnd.uniform(0.3, 0.49) * W
        k = rnd.choice((1, 1, 2))
        ph0 = rnd.random()
        sway = rnd.uniform(8, 26)
        sph = rnd.random()
        size = rnd.uniform(20, 52) * (1 if not mob else 0.8)
        ci = i % 4
        b = sk.bone(f'b{i}', x=x0, y=bot)
        dot = i % 3 == 0
        sk.hidden_slot(f'b{i}', b, f'bdot{ci}' if dot else f'bub{ci}', w=size, blend='additive' if dot else None)
        sk.hidden_slot(f'bv{i}', b, 'bubv', w=size)

        def pos(t, x0=x0, k=k, ph0=ph0, sway=sway, sph=sph):
            p = frac(k * t / P + ph0)
            return (x0 + sway * math.sin(2 * math.pi * (3 * t / P + sph)), bot + span * p)

        def al(t, k=k, ph0=ph0, amax=0.85):
            p = frac(k * t / P + ph0)
            return amax * clamp(min(p, 1 - p) / 0.1)
        sk.anim('idle', b, 'translate', pos)
        sk.anim('bonus', b, 'translate', pos)
        both(f'b{i}', 'alpha', al, (lambda t, al=al: al(t) * 0.45) if ci != 1 else al)
        both(f'bv{i}', 'alpha', zero, (lambda t, al=al: al(t) * 0.7) if ci != 1 else zero)

    # welding sparks: short gravity showers from two points under the roof
    sk.image('spk', spark(96, 18))
    for si, (t0, fx, fy) in enumerate(((0.8, -0.2, 0.36), (3.4, 0.24, 0.32), (5.9, -0.05, 0.4))):
        if mob:
            fx, fy = fx * 1.3, fy * 0.7
        for k in range(12):
            a = math.radians(rnd.uniform(200, 340))
            v = rnd.uniform(0.12, 0.3) * H
            name_ = f's{si}_{k}'
            b = sk.bone(name_, x=fx * W, y=fy * H, rot=math.degrees(a))
            sk.hidden_slot(name_, b, 'spk', 'ffcc66', w=40, h=10, blend='additive')
            LIFE = 0.9

            def spos(t, t0=t0, a=a, v=v, x=fx * W, y=fy * H):
                u = clamp((t - t0) / LIFE)
                return (x + math.cos(a) * v * u, y + math.sin(a) * v * u - H * 0.35 * u * u)

            def sal(t, t0=t0):
                if not t0 <= t <= t0 + LIFE:
                    return 0.0
                return (1 - (t - t0) / LIFE) ** 1.3
            sk.anim('idle', b, 'translate', spos)
            both(name_, 'alpha', sal, lambda t, sal=sal: sal(t) * 0.5)

    # drifting dust in the light
    sk.image('dust', glow_dot(48, core=0.4, col=(255, 220, 170)))
    for i in range(26):
        x0 = rnd.uniform(-0.5, 0.5) * W * spread
        y0 = rnd.uniform(-0.45, 0.45) * H
        amp = rnd.uniform(0.01, 0.04) * W
        ph = rnd.random()
        b = sk.bone(f'd{i}', x=x0, y=y0)
        sk.hidden_slot(f'd{i}', b, 'dust', w=rnd.uniform(8, 18), blend='additive')
        mv = (lambda t, x0=x0, y0=y0, amp=amp, ph=ph:
              (x0 + amp * math.sin(2 * math.pi * (t / P + ph)), y0 + amp * 0.6 * math.cos(2 * math.pi * (2 * t / P + ph))))
        sk.anim('idle', b, 'translate', mv)
        sk.anim('bonus', b, 'translate', mv)
        both(f'd{i}', 'alpha', lambda t, ph=ph: 0.25 + 0.3 * pulse(t, P / 2, ph, 2), lambda t, ph=ph: 0.15 * pulse(t, P / 2, ph, 2))

    # lab lightning (bonus only): four bolt shapes flicker over the side machinery
    for j in range(4):
        sk.image(f'bolt{j}', bolt(512, 128, 31 + j))
        sk.res_of[f'bolt{j}'] = 0.6
    sk.image('flash', soft_glow(256))
    sk.res_of['flash'] = 0.4
    strikes = [(0.5, -0.43, 0.42, -70), (1.9, 0.44, 0.38, -110), (3.3, -0.4, 0.2, -80),
               (4.6, 0.41, 0.3, -100), (6.2, -0.45, 0.35, -60), (7.1, 0.43, 0.1, -95)]
    for k, (t0, fx, fy, ang) in enumerate(strikes):
        x = fx * W * (1.0 if not mob else 0.9)
        y = fy * H
        b = sk.bone(f'L{k}', x=x, y=y, rot=ang)
        L = H * (0.42 if not mob else 0.3)
        for j in range(4):
            sk.hidden_slot(f'L{k}_{j}', b, f'bolt{j}', 'd8b8ff', w=L, h=L * 0.25, x=L / 2, blend='additive')
            DUR = 0.36

            def bal(t, t0=t0, j=j):
                if not t0 <= t <= t0 + DUR:
                    return 0.0
                frame = int((t - t0) / 0.06) % 4
                return (1.0 if frame == j else 0.0) * (1 - (t - t0) / DUR * 0.5)
            both(f'L{k}_{j}', 'alpha', zero, bal)
        fb = sk.bone(f'LF{k}', x=x, y=y - L * 0.4)
        sk.hidden_slot(f'LF{k}', fb, 'flash', 'b070ff', w=W * (0.35 if not mob else 0.7), blend='additive')
        both(f'LF{k}', 'alpha', zero, lambda t, t0=t0: 0.0 if not t0 <= t <= t0 + 0.5 else 0.55 * math.exp(-6 * (t - t0)))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# frame (frame png pixel space)

def build_frame(name):
    png, ox, oy, gw, gh = FRAMES[name]
    frame = Image.open(os.path.join(ART, png)).convert('RGBA')
    CW, CH = frame.size
    L, T, R, B = ox, oy, ox + gw, oy + gh
    scale = gw / 968

    def xy(ix, iy):
        return ix - CW / 2, CH / 2 - iy

    sk = MFx(name, CW, CH, 0.85, {'idle': 4.0, 'win': 1.2})

    al = frame.getchannel('A')
    pad = 60
    big = Image.new('L', (CW + 2 * pad, CH + 2 * pad))
    big.paste(al, (pad, pad))
    blur = big.filter(ImageFilter.GaussianBlur(26)).point(lambda v: min(255, int(v * 1.7)))
    inner = Image.new('L', big.size)
    inner.paste(al.point(lambda v: int(v * 0.8)), (pad, pad))
    halo = Image.new('RGBA', big.size, (255, 150, 50, 0))
    halo.putalpha(ImageChops.subtract(blur, inner))
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.45
    sk.hidden_slot('halo', 'root', 'halo', w=CW + 2 * pad, blend='additive')

    ew, eh = int(R - L), int(B - T)
    sk.image('edge', rrect_frame(ew, eh, 14, 6, 10))
    sk.res_of['edge'] = 0.6
    ex, ey = xy((L + R) / 2, (T + B) / 2)
    sk.hidden_slot('edge', 'root', 'edge', 'ffc04a', w=ew + 60, x=ex, y=ey, blend='additive')

    hl = highlight(frame, gamma=1.4, gain=1.3)
    sweep = []
    for i, (im, x0, x1) in enumerate(strips(hl, 18)):
        r = f'sweep{i}'
        sk.image(r, im)
        sk.res_of[r] = 0.5
        sk.hidden_slot(r, 'root', r, w=x1 - x0, x=xy((x0 + x1) / 2, 0)[0], blend='additive')
        sweep.append((r, (x0 + x1) / 2))

    sk.image('glint', star4(192, col=(255, 240, 200)))
    pts = bright_points(frame, 14, region=lambda X, Y: not (T - 20 < Y < B + 20 and L - 20 < X < R + 20),
                        seed=4, lum_min=205)
    glints = []
    for gi, (X, Y) in enumerate(pts):
        b = sk.bone(f'g{gi}', x=xy(X, Y)[0], y=xy(X, Y)[1])
        sk.hidden_slot(f'g{gi}', b, 'glint', w=80 * scale, blend='additive')
        glints.append(b)

    # the four signal lamps on the top rail (same formula as monster_factory_ui.py)
    lamp_cols = ['5aff6a', 'ffaa28', 'ff4a3c', '50beff']
    sk.image('lamp', glow_dot(128, core=0.3, col=(255, 255, 255)))
    lamps = []
    for i, col in enumerate(lamp_cols):
        X = ox + gw * (0.5 / 4 + i / 4) + gw / 8 * (1 if i % 2 else -1) * 0.5
        Y = oy * 0.5
        b = sk.bone(f'lamp{i}', x=xy(X, Y)[0], y=xy(X, Y)[1])
        sk.hidden_slot(f'lamp{i}', b, 'lamp', col, w=70 * scale, blend='additive')
        lamps.append((b, f'lamp{i}', i))

    per = 2 * (R - L) + 2 * (B - T)
    o = 4

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

    sk.image('dot', glow_dot(128, core=0.26, col=HAZARD))
    TRAIL = 7
    comets = []
    for c in range(4):
        for k in range(TRAIL):
            name_ = f'c{c}_{k}'
            b = sk.bone(name_, x=perim(c / 4)[0], y=perim(c / 4)[1])
            sk.hidden_slot(name_, b, 'dot', w=(60 - 6 * k) * scale + 8, blend='additive')
            comets.append((b, name_, c, k))

    def sweep_fn(cx, t0, dur, peak, sigma):
        def f(t):
            if not t0 <= t <= t0 + dur:
                return 0.0
            sx = lerp(-260, CW + 260, in_out_sine((t - t0) / dur))
            return peak * math.exp(-((cx - sx) / sigma) ** 2)
        return f

    sk.anim('idle', 'halo', 'alpha', lambda t: 0.22 + 0.16 * (1 - math.cos(2 * math.pi * t / 4)) / 2)
    sk.anim('win', 'halo', 'alpha', lambda t: 0.5 + 0.45 * (1 - math.cos(2 * math.pi * t / 0.4)) / 2)
    sk.anim('idle', 'edge', 'alpha', lambda t: 0.0)
    sk.anim('win', 'edge', 'alpha', lambda t: 0.35 + 0.3 * (1 + math.cos(2 * math.pi * t / 0.4)) / 2)
    for r, cx in sweep:
        sk.anim('idle', r, 'alpha', sweep_fn(cx, 1.2, 1.3, 0.55, 120))
        sk.anim('win', r, 'alpha', sweep_fn(cx, 0.05, 0.8, 0.9, 150))
    rnd = random.Random(9)
    for gi, b in enumerate(glints):
        ph, ph2 = rnd.random(), rnd.random()
        sk.anim('idle', f'g{gi}', 'alpha', lambda t, ph=ph: pulse(t, 2.0, ph, 10))
        sk.anim('win', f'g{gi}', 'alpha', lambda t, ph=ph2: pulse(t, 0.6, ph, 6))
        sk.anim('idle', b, 'scale', lambda t, ph=ph: (0.3 + 0.9 * pulse(t, 2.0, ph, 6),) * 2)
        sk.anim('win', b, 'scale', lambda t, ph=ph2: (0.4 + 1.1 * pulse(t, 0.6, ph, 4),) * 2)
        sk.anim('idle', b, 'rotate', lambda t: 90 * t / 4)
        sk.anim('win', b, 'rotate', lambda t: 90 * t / 1.2)
    for b, sl, i in lamps:
        # idle: each lamp blinks on its own beat; win: all chase fast
        sk.anim('idle', sl, 'alpha', lambda t, i=i: 0.35 + 0.65 * pulse(t, 4.0 / (1 + i % 2), i / 4, 4))
        sk.anim('win', sl, 'alpha', lambda t, i=i: 0.3 + 0.7 * pulse(t, 0.4, i / 4, 6))
        sk.anim('win', b, 'scale', lambda t, i=i: (1 + 0.5 * pulse(t, 0.4, i / 4, 6),) * 2)
    lag = 0.012
    for b, name_, c, k in comets:
        on_idle = c % 2 == 0
        sk.anim('idle', b, 'translate', lambda t, c=c, k=k: perim(c / 4 + t / 4 - k * lag))
        sk.anim('win', b, 'translate', lambda t, c=c, k=k: perim(c / 4 + t / 1.2 - k * lag * 1.6))
        fade = (1 - k / TRAIL) ** 1.3
        sk.anim('idle', name_, 'alpha', lambda t, f=fade, on=on_idle: f * 0.75 if on else 0.0)
        sk.anim('win', name_, 'alpha', lambda t, f=fade: f)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# logo — the Baku logo FX is generic (reads logo.png, nothing game-specific)

def build_logo():
    return gold_of_baku_fx.build_logo({}, ART, OUT)


# --------------------------------------------------------------------------
# symbols (one 124x124 symbol box)

SYMBOLS = {
    # code: (fill of the box, glow colour, motion kind)
    'hp_red': (0.98, (255, 80, 50), 'hop'),
    'hp_yellow': (0.98, (255, 214, 40), 'hop'),
    'hp_green': (0.98, (120, 255, 60), 'hop'),
    'hp_blue': (0.98, (60, 160, 255), 'hop'),
    'lp_red': (0.9, (255, 80, 50), 'jiggle'),
    'lp_green': (0.9, (120, 255, 60), 'jiggle'),
    'lp_blue': (0.9, (60, 160, 255), 'jiggle'),
    'lp_yellow': (0.9, (255, 214, 40), 'jiggle'),
    'wild': (0.98, (140, 255, 70), 'slam'),
    'scatter': (0.98, (190, 90, 255), 'swing'),
    'bomb': (0.95, (255, 120, 40), 'stretch'),
    'x2': (0.94, (120, 255, 60), 'spin'),
    'x3': (0.94, (60, 170, 255), 'spin'),
    'x5': (0.94, (190, 90, 255), 'spin'),
    'x7': (0.94, (255, 110, 40), 'spin'),
}
SYM_DUR = 0.7  # = slot.js WIN_PULSE_MS
MOTION_SPEED = 1.1 / SYM_DUR  # sym_motion is authored for a 1.1s clip


def build_symbols():
    S = SYMBOL_BOX
    sk = MFx('symbols', S, S, 1.0, {code: SYM_DUR for code in SYMBOLS}, quantize=True)
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.5
    sk.image('rays', rays(512, n=14))
    sk.res_of['rays'] = 0.6
    sk.image('ring', ring(256))
    sk.image('spark', star4(128))
    sk.image('dot', glow_dot(64, core=0.3, col=(255, 245, 225)))
    rnd = random.Random(21)
    for code, (symf, col, kind) in SYMBOLS.items():
        im = Image.open(os.path.join(SYM, f'{code}.png')).convert('RGBA')
        # the static img is object-fit:contain of the whole 360 canvas in the
        # 124 box, so the skeleton draws the whole canvas at S x S too —
        # transparent padding included — to land exactly on the DOM tile
        w = h = S * 1.0
        k = S / im.width
        hexcol = '%02x%02x%02x' % col
        sk.image(code, im)
        sk.res_of[code] = 2.0  # ~250px of a 360 canvas: crisp enough at 2x
        flash = Image.new('RGBA', im.size, (255, 255, 255, 0))
        flash.putalpha(im.getchannel('A'))
        sk.image(f'{code}_flash', flash)
        sk.res_of[f'{code}_flash'] = 0.5

        C = code
        fx = sk.bone(f'{C}_fx')
        sk.hidden_slot(f'{C}_halo', fx, 'halo', hexcol, w=S * 1.6, h=S * 1.6, blend='additive')
        sk.hidden_slot(f'{C}_rays', fx, 'rays', hexcol, w=S * 2.0, blend='additive')
        rb = sk.bone(f'{C}_rb')
        sk.hidden_slot(f'{C}_ring', rb, 'ring', hexcol, w=S * 0.95, blend='additive')
        piv = h * 0.3 if kind == 'swing' else (-h * 0.3 if kind == 'hop' else 0)
        sb = sk.bone(f'{C}_sym', y=piv)
        sk.hidden_slot(f'{C}_img', sb, code, w=w, y=-piv)
        hl = highlight(im, gamma=1.2, gain=1.5)
        sweep = []
        for i, (sim, x0, x1) in enumerate(strips(hl, 14)):
            r = f'{C}_sw{i}'
            sk.image(r, sim)
            sk.res_of[r] = 0.5
            sk.hidden_slot(r, sb, r, w=(x1 - x0) * k, x=((x0 + x1) / 2 - im.width / 2) * k, y=-piv, blend='additive')
            sweep.append((r, (x0 + x1) / 2 * k))
        sk.hidden_slot(f'{C}_flash', sb, f'{C}_flash', w=w, y=-piv, blend='additive')
        sparks = []
        for i in range(7):
            a = 2 * math.pi * i / 7 + rnd.uniform(-0.3, 0.3)
            b = sk.bone(f'{C}_sp{i}')
            sk.hidden_slot(f'{C}_sp{i}', b, 'spark' if i % 2 == 0 else 'dot', hexcol if i % 3 == 0 else 'ffffff',
                           w=rnd.uniform(26, 42), blend='additive')
            sparks.append((b, f'{C}_sp{i}', a, rnd.uniform(0.75, 1.1), rnd.uniform(0, 0.06)))

        def mo(t, kind=kind):
            return sym_motion(kind, t * MOTION_SPEED)
        D = SYM_DUR
        sk.anim(C, f'{C}_img', 'alpha', lambda t: 1.0)
        sk.anim(C, sb, 'scale', lambda t, mo=mo: mo(t)[:2])
        sk.anim(C, sb, 'rotate', lambda t, mo=mo: mo(t)[2])
        sk.anim(C, sb, 'translate', lambda t, mo=mo, piv=piv: (0, piv + mo(t)[3] * S / 254))
        sk.anim(C, f'{C}_flash', 'alpha', lambda t: seg(t, 0, 0.05, 0, 0.8) if t < 0.05 else 0.8 * math.exp(-12 * (t - 0.05)))
        for r, cx in sweep:
            sk.anim(C, r, 'alpha', lambda t, cx=cx: 0.0 if not 0.08 <= t <= 0.45 else
                    0.85 * math.exp(-((cx - lerp(-40, w + 40, in_out_sine((t - 0.08) / 0.37))) / 40) ** 2))
        big = 1.25 if kind == 'slam' else 1.0
        sk.anim(C, f'{C}_halo', 'alpha', lambda t, big=big: seg(t, 0, 0.08, 0, 0.85 * big) if t < 0.08 else seg(t, 0.08, D, 0.85 * big, 0, in_out_sine))
        sk.anim(C, fx, 'scale', lambda t: (seg(t, 0, 0.14, 0.5, 1.15, out_back) if t < 0.14 else seg(t, 0.14, D, 1.15, 0.9),) * 2)
        sk.anim(C, f'{C}_rays', 'alpha', lambda t, big=big: seg(t, 0, 0.1, 0, 0.7 * big) if t < 0.1 else seg(t, 0.1, D, 0.7 * big, 0, in_out_sine))
        sk.anim(C, fx, 'rotate', lambda t: -45 * t / D)
        t0 = 0.12 if kind == 'slam' else 0.03
        sk.anim(C, f'{C}_ring', 'alpha', lambda t, t0=t0: 0.0 if t < t0 else seg(t, t0, t0 + 0.35, 1, 0))
        sk.anim(C, rb, 'scale', lambda t, t0=t0, big=big: (seg(t, t0, t0 + 0.35, 0.3, 1.9 * big),) * 2)
        for b, sl, a, dist, delay in sparks:
            def sp_pos(t, a=a, dist=dist, delay=delay):
                u = clamp((t - 0.04 - delay) / 0.5)
                d = (S * 0.3 + S * 0.42 * dist * out_cubic(u))
                spin = a + 1.2 * u
                return (math.cos(spin) * d, math.sin(spin) * d)
            sk.anim(C, b, 'translate', sp_pos)
            sk.anim(C, sl, 'alpha', lambda t, delay=delay: 0.0 if t < 0.04 + delay else seg(t, 0.04 + delay, 0.62 + delay, 1, 0, in_cubic_ease))
            sk.anim(C, b, 'scale', lambda t, delay=delay: (0.4 + 0.9 * pulse(t - delay, 0.25, 0.0, 2),) * 2)
            sk.anim(C, b, 'rotate', lambda t: 260 * t)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# coins

def coin_flip(t, spd, ph):
    v = math.cos(2 * math.pi * (spd * t + ph))
    return v if abs(v) > 0.06 else (0.06 if v >= 0 else -0.06)


def build_burst():
    RW, RH = GRID
    D = 1.6
    sk = MFx('burst', RW, RH, 1.0, {'win': D})
    rnd = random.Random(31)
    sk.image('coin', eye_coin(128))
    sk.image('star', gold_of_baku_fx.star8(96))
    sk.image('flash', tint(soft_glow(256), GOLD))
    sk.res_of['flash'] = 0.4
    sk.image('ring', ring(256, col=(255, 226, 150)))
    for ci, col in enumerate(GOO):
        sk.image(f'goo{ci}', bubble(96, col))

    sk.hidden_slot('flash', 'root', 'flash', w=RW * 0.9, h=RH * 1.1, blend='additive')
    sk.anim('win', 'flash', 'alpha', lambda t: seg(t, 0, 0.08, 0, 0.45) if t < 0.08 else 0.45 * math.exp(-4 * (t - 0.08)))
    rb = sk.bone('ring')
    sk.hidden_slot('ring', rb, 'ring', w=RH * 0.9, blend='additive')
    sk.anim('win', 'ring', 'alpha', lambda t: seg(t, 0, 0.6, 1, 0))
    sk.anim('win', rb, 'scale', lambda t: (seg(t, 0, 0.6, 0.3, 2.6),) * 2)

    for i in range(16):
        a = 2 * math.pi * i / 16 + rnd.uniform(-0.12, 0.12)
        dist = RH * rnd.uniform(0.55, 0.85)
        b = sk.bone(f'st{i}')
        sk.hidden_slot(f'st{i}', b, 'star' if i % 2 else f'goo{i % 4}', w=rnd.uniform(30, 52), blend='additive' if i % 2 else None)
        sk.anim('win', b, 'translate', lambda t, a=a, dist=dist: (math.cos(a) * dist * 1.4 * out_cubic(clamp(t / 0.8)),
                                                                   math.sin(a) * dist * out_cubic(clamp(t / 0.8))))
        sk.anim('win', b, 'rotate', lambda t: 300 * t)
        sk.anim('win', f'st{i}', 'alpha', lambda t: seg(t, 0.1, 1.0, 1, 0, in_cubic_ease) if t > 0.1 else 1.0)

    G = RH * 3.2
    for i in range(14):
        side = -1 if i % 2 else 1
        vx = side * rnd.uniform(0.55, 1.0) * RW * 0.55
        vy = rnd.uniform(0.9, 1.25) * RH * 1.55
        delay = rnd.uniform(0, 0.18)
        spd, ph = rnd.uniform(1.6, 2.6), rnd.random()
        sz = rnd.uniform(64, 92)
        x0 = side * RW * 0.22
        b = sk.bone(f'cn{i}', x=x0, y=-RH * 0.1)

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


def build_shower():
    S = 1000.0
    P = 2.0
    sk = MFx('shower', S, S, 1.0, {'start': P, 'rain': P})
    rnd = random.Random(77)
    sk.image('coin', eye_coin(128))
    sk.image('star', gold_of_baku_fx.star8(96))
    sk.image('dot', glow_dot(64, core=0.3, col=GOLD))
    for ci, col in enumerate(GOO):
        sk.image(f'goo{ci}', bubble(96, col))
    top, bot = S * 0.95, -S * 0.95
    span = top - bot

    def entered(t, k, ph):
        return t >= (1 - ph) / k * P - 1e-6

    for i in range(64):
        x0 = rnd.uniform(-0.92, 0.92) * S
        k = rnd.choice((1, 1, 2))
        ph = rnd.random()
        spd, fph = rnd.uniform(1.2, 2.4), rnd.random()
        sway = rnd.uniform(10, 40)
        goo = i % 5 == 0
        sz = rnd.uniform(50, 90) if not goo else rnd.uniform(28, 50)
        rot0 = rnd.uniform(-25, 25)
        b = sk.bone(f'c{i}', x=x0, y=top, rot=rot0)
        sk.hidden_slot(f'c{i}', b, f'goo{i % 4}' if goo else 'coin', w=sz)

        def pos(t, x0=x0, k=k, ph=ph, sway=sway):
            p = frac(k * t / P + ph)
            return (x0 + sway * math.sin(2 * math.pi * (t / P + ph)), top - span * p)
        for clip in ('start', 'rain'):
            sk.anim(clip, b, 'translate', pos)
            if not goo:
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
    args = list(sys.argv[1:])
    preview = None
    if '--preview' in args:
        i = args.index('--preview')
        preview = args[i + 1]
        del args[i:i + 2]
        os.makedirs(preview, exist_ok=True)
    only = set(args)

    def want(k):
        return not only or k in only
    built = {}
    if want('bg'):
        built['bg_desk'] = build_bg('bg_desk')
        built['bg_mob'] = build_bg('bg_mob')
    if want('frame'):
        built['frame_desk'] = build_frame('frame_desk')
        built['frame_mob'] = build_frame('frame_mob')
    if want('logo'):
        built['logo'] = build_logo()
    if want('symbols'):
        built['symbols'] = build_symbols()
    if want('burst'):
        built['burst'] = build_burst()
    if want('shower'):
        built['shower'] = build_shower()
    if not preview:
        return
    under_img = {
        'frame_desk': Image.open(os.path.join(ART, 'frame_desk.png')),
        'frame_mob': Image.open(os.path.join(ART, 'frame_mob.png')),
        'logo': Image.open(os.path.join(ART, 'logo.png')),
        'bg_desk': Image.open(os.path.join(ART, 'bg_base.jpg')),
        'bg_mob': Image.open(os.path.join(ART, 'bg_base_mob.jpg')),
    }
    for name, sk in built.items():
        for clip, dur in sk.durs.items():
            if name == 'symbols' and clip not in ('hp_red', 'lp_blue', 'wild', 'scatter', 'x5'):
                continue
            under = under_img.get(name)
            if name.startswith('bg') and clip == 'bonus':
                under = Image.open(os.path.join(ART, 'bg_bonus.jpg' if name == 'bg_desk' else 'bg_bonus_mob.jpg'))
            box = (-sk.w / 2, -sk.h / 2, sk.w, sk.h)
            pw = 800 if sk.w >= sk.h else 500
            frames = [render(sk, clip, dur * k / 6, (pw, int(pw * sk.h / sk.w)), under=under,
                             under_box=box if under is not None else None) for k in range(6)]
            sheet = Image.new('RGB', (pw * 3, frames[0].height * 2))
            for k, f in enumerate(frames):
                sheet.paste(f.convert('RGB'), ((k % 3) * pw, (k // 3) * f.height))
            sheet.save(os.path.join(preview, f'{name}_{clip}.jpg'), quality=80)


if __name__ == '__main__':
    main()
