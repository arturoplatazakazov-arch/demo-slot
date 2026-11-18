"""Olympus Thunder · Tides 2 — pseudo-3D Zeus rig (Spine 4.1, built in code), v2.

    ~/.venvs/art/bin/python scripts/olympus_zeus_parts.py      # layers -> ~/ot2-work/rig/p_*.png
    ~/.venvs/art/bin/python scripts/olympus_zeus_rig.py [PARTS_DIR]

Layers (all on the hero's 1199x1312 canvas, so they re-assemble exactly), back to front:
  body      armless + HEADLESS torso (neck stump, clasp, straps, cloak, cloud)  — weighted mesh
  l_fore    left forearm + open hand
  plasma_*  Tesla plasma ball in the palm (generated here: halo, glass, core, 2 filament layers)
  head      head + hair + beard (never covered by an arm) — weighted mesh, attachments head /
            head_blink / head_shout share the mesh (same crop box)
  r_upper   clean upper arm with a rounded elbow;  r_fore  bracer + fist
  bolt, bolt_glow   the bolt in the fist (+ additive copy for the candle flicker)

Pseudo-3D: head mesh skinned to head_f (face, beard centre) / head_b (hair rim) + hair_l / hair_r /
beard sway bones; torso to chest_f (centre) / chest_b (sides). Turning = moving front vs back.
Clips: idle (loop, blink), throw (event 'release'), win, charge, turn (debug sweep).
Output: front/img/olympus-thunder/tides2/zeus_rig/animation.{json,atlas,webp} (+meta.json)
"""
import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from olympus_spine_lib import Rig, clamp, smooth, keys  # noqa: E402

PARTS = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/ot2-work/rig')
OUT = os.path.join(os.path.dirname(__file__), '..', 'front/img/olympus-thunder/tides2')
W, H = 1199, 1312
S = 0.5           # skeleton units per hero px (textures keep full resolution)
TAU = 2 * math.pi


def sk(x, y):
    return ((x - W / 2) * S, (H / 2 - y) * S)


def load(n):
    return Image.open(os.path.join(PARTS, f'p_{n}.png')).convert('RGBA')


def bbox(im):
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 4)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def sstep(a, b, v):
    return smooth((v - a) / (b - a)) if b != a else float(v >= a)


rig = Rig('zeus_rig', W * S, H * S, OUT, res=1 / S)

# ---------------------------------------------------------------- bones ----
J = {'hips': (560, 1090), 'chest': (560, 760), 'neck': (640, 560), 'beard': (700, 470),
     'hair_l': (420, 380), 'hair_r': (860, 420),
     'r_shoulder': (405, 625), 'r_elbow': (115, 640), 'r_wrist': (188, 405), 'r_fist': (285, 330),
     'l_elbow': (900, 1090), 'orb': (1010, 795), 'cloak_l': (240, 800), 'cloak_r': (900, 700)}
B = rig.bone_at
B('hips', 'root', *sk(*J['hips']))
B('chest', 'hips', *sk(*J['chest']))
B('chest_f', 'chest', *sk(*J['chest']))
B('chest_b', 'chest', *sk(*J['chest']))
B('head', 'chest_f', *sk(*J['neck']))
B('head_f', 'head', *sk(*J['neck']))
B('head_b', 'head', *sk(*J['neck']))
B('beard', 'head_f', *sk(*J['beard']))
B('hair_l', 'head_b', *sk(*J['hair_l']))
B('hair_r', 'head_b', *sk(*J['hair_r']))
B('cloak_l', 'hips', *sk(*J['cloak_l']))
B('cloak_r', 'chest', *sk(*J['cloak_r']))
B('r_shoulder', 'chest_f', *sk(*J['r_shoulder']))
B('r_elbow', 'r_shoulder', *sk(*J['r_elbow']))
B('r_fist', 'r_elbow', *sk(*J['r_wrist']))
B('bolt', 'r_fist', *sk(*J['r_fist']))
B('bolt_tip', 'r_fist', *sk(330, 250))         # thrown lightning starts here (the lab reads it)
B('l_elbow', 'chest_f', *sk(*J['l_elbow']))
B('orb', 'l_elbow', *sk(*J['orb']))
B('orb_f1', 'orb', *sk(*J['orb']))
B('orb_f2', 'orb', *sk(*J['orb']))


def wxy(bone):
    m = rig.world(bone)
    return m[0, 2], m[1, 2]


def img_xy(px, py):
    return px / S + W / 2, H / 2 - py / S


# ----------------------------------------------------------- body mesh -----
_ARM = None


def arm_maps():
    """soft weight maps (hero px) for the parts of the body mesh that belong to the arms"""
    global _ARM
    if _ARM is None:
        from PIL import ImageDraw as _D
        from scipy.ndimage import gaussian_filter as _g
        def m(pts, blur):
            im = Image.new('L', (W, H), 0)
            _D.Draw(im).polygon(pts, fill=255)
            return _g(np.array(im) / 255.0, blur)
        up = [(205, 578), (140, 592), (60, 612), (10, 650), (16, 730), (80, 785), (170, 800), (300, 805), (360, 815),
              (392, 780), (412, 690), (420, 612), (380, 575), (330, 560)]
        lf = [(855, 1150), (866, 1030), (888, 955), (905, 880), (960, 850), (1060, 812), (1150, 800), (1178, 850),
              (1168, 980), (1160, 1100), (1120, 1152), (990, 1162)]
        ua = m(up, 22)
        yy, xx = np.mgrid[0:H, 0:W]
        # the shoulder strap / cloak above the arm stay on the torso: no arm weight above the strap's lower edge
        ramp = np.clip((yy - 555) / 70.0, 0, 1) ** 1.5
        ramp = np.where(xx < 150, 1.0, ramp)
        _ARM = (ua * ramp, m(lf, 18))
    return _ARM


def body_w(px, py):
    x, y = img_xy(px, py)
    ua, lfa = arm_maps()
    xi, yi = int(min(max(x, 0), W - 1)), int(min(max(y, 0), H - 1))
    rs, le = 0.0, float(lfa[yi, xi])   # right arm = separate rigid parts now
    chest = 1 - sstep(820, 990, y)
    hips = 1 - chest
    cl = hips * sstep(330, 120, x) * sstep(820, 1000, y) + chest * sstep(300, 90, x) * sstep(700, 880, y) * (1 - rs)
    cr = sstep(880, 1060, x) * sstep(620, 760, y) * (1 - sstep(1150, 1260, y)) * (1 - le)
    chest = max(0.0, chest - cr)
    hips = max(0.0, hips - cl)
    cf = chest * (1 - sstep(130, 300, abs(x - 600)))
    cb = chest - cf
    rest = max(0.0, 1 - rs - le)
    ws = [(b, w * rest) for b, w in (('hips', hips), ('chest_f', cf), ('chest_b', cb), ('cloak_l', cl), ('cloak_r', cr))]
    ws += [('r_shoulder', rs), ('l_elbow', le)]
    ws = [(b, w) for b, w in ws if w > 1e-3]
    return ws or [('hips', 1.0)]


def head_w(px, py):
    x, y = img_xy(px, py)
    dx, dy = (x - 690) / 170, (y - 360) / 200
    face = clamp(1.3 - math.hypot(dx, dy))
    beard = sstep(430, 540, y) * (1 - sstep(120, 220, abs(x - 700)))
    hl = sstep(520, 380, x) * sstep(280, 420, y)
    hr = sstep(820, 920, x) * sstep(320, 460, y)
    beard = max(0.0, min(beard, 1 - hl - hr))
    face = max(0.0, face * (1 - beard))
    back = max(0.0, 1 - face - beard - hl - hr)
    ws = [(b, w) for b, w in (('head_f', face), ('head_b', back), ('beard', beard), ('hair_l', hl), ('hair_r', hr)) if w > 1e-3]
    return ws or [('head_b', 1.0)]


def mesh(slot, names, weights, nx, ny, bone, box_of=None, color=None):
    """one grid mesh for names[0]; the other names reuse it (same crop box) as alternative attachments."""
    ims = [load(n) for n in names]
    x0, y0, x1, y1 = bbox(load(box_of) if box_of else ims[0])
    for n, im in zip(names, ims):
        rig.image(n, im.crop((x0, y0, x1, y1)))
    cx, cy = sk((x0 + x1) / 2, (y0 + y1) / 2)
    w, h = (x1 - x0) * S, (y1 - y0) * S
    rig.mesh_grid(slot, names[0], cx, cy, w, h, weights, nx=nx, ny=ny, bone=bone, color=color)
    for n in names[1:]:
        att = dict(rig.atts[slot][names[0]])
        att['path'] = n
        rig.atts[slot][n] = att
        rig.need[n] = (w, h)


def region(slot, bone, name, blend=None, src=None):
    im = load(src or name)
    x0, y0, x1, y1 = bbox(im)
    rig.image(name, im.crop((x0, y0, x1, y1)))
    wx, wy = sk((x0 + x1) / 2, (y0 + y1) / 2)
    bx, by = wxy(bone)
    rig.region(slot, bone, name, x=wx - bx, y=wy - by, w=(x1 - x0) * S, h=(y1 - y0) * S, blend=blend)


# ---------------------------------------------- Tesla plasma ball (code) ----
def plasma_images(size=300, seed=7):
    rnd = random.Random(seed)
    c = size / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.hypot(xx - c, yy - c) / c

    def rgba(col, a):
        out = np.zeros((size, size, 4), np.uint8)
        out[..., :3] = col
        out[..., 3] = np.uint8(np.clip(a, 0, 1) * 255)
        return Image.fromarray(out)

    halo = rgba((120, 225, 255), np.clip(1 - r, 0, 1) ** 1.8)
    glass = rgba((170, 235, 255), np.exp(-((r - 0.62) / 0.05) ** 2) * 0.75 + (r < 0.64) * 0.18)
    core = rgba((240, 253, 255), np.clip(1 - r / 0.38, 0, 1) ** 1.2)

    def filaments(n):
        im = Image.new('RGBA', (size, size))
        d = ImageDraw.Draw(im)
        for _ in range(n):
            ang = rnd.uniform(0, TAU)
            pts = [(c, c)]
            steps = 9
            for k in range(1, steps + 1):
                rad = 0.6 * c * k / steps
                ang += rnd.uniform(-0.35, 0.35)
                pts.append((c + rad * math.cos(ang), c + rad * math.sin(ang)))
            d.line(pts, fill=(215, 248, 255, 255), width=4, joint='curve')
        glow = im.filter(ImageFilter.GaussianBlur(5))
        out = Image.alpha_composite(glow, glow)
        return Image.alpha_composite(out, im.filter(ImageFilter.GaussianBlur(0.8)))

    return {'plasma_halo': halo, 'plasma_glass': glass, 'plasma_core': core,
            'plasma_f1': filaments(7), 'plasma_f2': filaments(6)}


# ---------------------------------------------------------------- slots ----
mesh('body', ['body'], body_w, 34, 36, 'hips')    # finer grid: the shoulder / left arm bend inside it
PL = plasma_images()
D = 330 * S                                     # ball diameter (hero px * S)
for name, bone, blend in (('plasma_halo', 'orb', 'additive'), ('plasma_glass', 'orb', None), ('plasma_f1', 'orb_f1', 'additive'),
                          ('plasma_f2', 'orb_f2', 'additive'), ('plasma_core', 'orb', 'additive')):
    rig.image(name, PL[name])
    sc = 1.7 if name == 'plasma_halo' else 1.0
    rig.region(name, bone, name, x=0, y=0, w=D * sc, h=D * sc, blend=blend)
region('l_fingers', 'l_elbow', 'l_fingers')
mesh('head', ['head'], head_w, 14, 14, 'head')
# emotions = the same head mesh on a FACE slot above it, cross-faded in ~50 ms (no visible swap)
mesh('face', ['head_blink', 'head_shout'], head_w, 14, 14, 'head', box_of='head', color='ffffff00')
# right arm, one rigid piece per joint; the strap (torso) covers the shoulder root, the bracer's rims cover elbow and wrist
region('r_upper', 'r_shoulder', 'r_upper')
region('strap', 'chest_f', 'strap')
region('bolt', 'bolt', 'bolt')
region('bolt_glow', 'bolt', 'bolt_glow', blend='additive', src='bolt')
region('r_bracer', 'r_elbow', 'r_bracer')
region('bolt_low', 'bolt', 'bolt_low')
region('r_fist', 'r_fist', 'r_fist')
rig.event('release')


# ----------------------------------------------------------- animations ----
def breathe(a, period=4.0, k=1.0):
    s = lambda t, ph=0.0: math.sin(TAU * t / period + ph)  # noqa: E731
    a.bone('chest', 'scale', lambda t: (1 + 0.006 * k * s(t), 1 + 0.013 * k * s(t)))
    a.bone('beard', 'rotate', lambda t: 2.4 * k * s(t, 1.6))
    a.bone('hair_l', 'rotate', lambda t: -2.0 * k * s(t, 1.1))
    a.bone('hair_r', 'rotate', lambda t: 2.2 * k * s(t, 1.9))
    a.bone('cloak_l', 'rotate', lambda t: 1.6 * k * s(t, 0.4))
    a.bone('cloak_r', 'rotate', lambda t: -1.4 * k * s(t, 1.1))


def plasma(a, boost=lambda t: 0.0):
    a.bone('orb_f1', 'rotate', lambda t: -360 * t / 2.0)
    a.bone('orb_f2', 'rotate', lambda t: 360 * t / 1.33)
    a.bone('orb', 'scale', lambda t: 1 + 0.04 * math.sin(TAU * t / 0.8) + 0.3 * boost(t))
    a.rgba('plasma_core', lambda t: min(1.0, 0.75 + 0.12 * math.sin(TAU * t / 0.4) + 0.25 * boost(t)))
    a.rgba('plasma_halo', lambda t: min(1.0, 0.55 + 0.15 * math.sin(TAU * t / 1.0) + 0.45 * boost(t)))


def turn(a, fn):
    """pseudo-3D turn: fn(t) in -1..1 (+ = toward the slot on the right)."""
    a.bone('head_f', 'translate', lambda t: (10 * fn(t), -1.5 * abs(fn(t))))
    a.bone('head_b', 'translate', lambda t: (-5 * fn(t), 0))
    a.bone('chest_f', 'translate', lambda t: (6 * fn(t), 0))
    a.bone('chest_b', 'translate', lambda t: (-3 * fn(t), 0))


def face(a, name, t_in, t_out, fade=0.05):
    """show an emotion: fade in over `fade` s at t_in, hold, fade out by t_out (attachment set on the face slot)."""
    a.attach('face', [(0, name)])
    a.rgba('face', lambda t: smooth((t - t_in) / fade) * (1 - smooth((t - (t_out - fade)) / fade)))


# idle — 4 s loop: breathing, hair/beard/cloak sway, arms float, blink, bolt candle, plasma
a = rig.anim('idle', 4.0)
breathe(a)
plasma(a)
a.bone('head', 'rotate', lambda t: 1.3 * math.sin(TAU * t / 4 + 0.8))
a.bone('r_shoulder', 'rotate', lambda t: 1.8 * math.sin(TAU * t / 4 + 0.3))
a.bone('r_elbow', 'rotate', lambda t: 2.5 * math.sin(TAU * t / 4 + 0.9))
a.bone('l_elbow', 'rotate', lambda t: 1.5 * math.sin(TAU * t / 4 + 2.0))
a.rgba('bolt_glow', lambda t: 0.25 + 0.2 * (0.5 + 0.5 * math.sin(TAU * t / 0.5)) * (0.6 + 0.4 * math.sin(TAU * t / 1.3)))
face(a, 'head_blink', 2.6, 2.74, fade=0.035)

# throw — wind-up 0-0.45, whip 0.45-0.62 (release 0.60), follow-through, recover to 1.8
T_REL = 0.60
a = rig.anim('throw', 1.8)
breathe(a, k=0.5)
plasma(a)
a.bone('r_shoulder', 'rotate', lambda t: keys(t, [(0, 0), (0.45, -8), (0.62, 7), (0.9, 5), (1.8, 0)]))
a.bone('r_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 20), (0.52, 16), (0.62, -18), (0.9, -14), (1.8, 0)]))
a.bone('r_elbow', 'scale', lambda t: (keys(t, [(0, 1), (0.45, 0.96), (0.62, 1.04), (0.95, 1.02), (1.8, 1)]),) * 2)
a.bone('r_fist', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 18), (0.62, -20), (1.0, -12), (1.8, 0)]))
a.bone('chest', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 2.5), (0.66, -3.5), (1.8, 0)]))
a.bone('hips', 'translate', lambda t: (keys(t, [(0, 0), (0.45, -6), (0.66, 9), (1.8, 0)]), 0))
a.bone('head', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 3), (0.66, -4), (1.2, -2), (1.8, 0)]))
turn(a, lambda t: keys(t, [(0, 0), (0.4, -0.6), (0.66, 1.0), (1.2, 0.8), (1.8, 0)]))
a.bone('l_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.45, -4), (0.7, 6), (1.8, 0)]))
a.rgba('bolt_low', lambda t: 1.0 if t < T_REL else (0.0 if t < 1.25 else smooth((t - 1.25) / 0.35)))
a.rgba('bolt', lambda t: 1.0 if t < T_REL else (0.0 if t < 1.25 else smooth((t - 1.25) / 0.35)))
a.rgba('bolt_glow', lambda t: (0.3 + 0.7 * smooth(t / 0.5)) if t < T_REL else (0.0 if t < 1.25 else 0.3 * smooth((t - 1.25) / 0.35)))
face(a, 'head_shout', 0.40, 0.98, fade=0.06)
a.event('release', T_REL)

# win — triumph: fist up high, chest out, head back with a shout, plasma flares (2.2 s)
a = rig.anim('win', 2.2)
breathe(a, k=0.6)
plasma(a, lambda t: math.sin(math.pi * clamp((t - 0.2) / 1.6)))
a.bone('r_shoulder', 'rotate', lambda t: keys(t, [(0, 0), (0.35, -7), (0.55, -6), (1.6, -6), (2.2, 0)]))
a.bone('r_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.35, 16), (0.5, 13), (1.6, 13), (2.2, 0)]))
a.bone('r_fist', 'rotate', lambda t: 4 * math.sin(TAU * t / 0.35) * clamp((t - 0.5) / 0.2) * (1 - clamp((t - 1.5) / 0.3)))
a.bone('chest', 'scale', lambda t: (1, 1 + 0.03 * math.sin(math.pi * clamp(t / 2.0))))
a.bone('head', 'rotate', lambda t: keys(t, [(0, 0), (0.35, 5), (1.6, 4), (2.2, 0)]))
a.bone('l_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.4, 10), (1.6, 8), (2.2, 0)]))
a.rgba('bolt_glow', lambda t: 0.35 + 0.65 * math.sin(math.pi * clamp((t - 0.2) / 1.6)))
face(a, 'head_shout', 0.26, 1.58, fade=0.06)

# charge — the orb hand lifts, the plasma swells
a = rig.anim('charge', 1.2)
breathe(a, k=0.5)
plasma(a, lambda t: math.sin(math.pi * clamp(t / 1.2)))
a.bone('l_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.5, 9), (0.8, 7), (1.2, 0)]))
turn(a, lambda t: keys(t, [(0, 0), (0.5, 0.5), (1.2, 0)]))

# turn — debug sweep for the lab slider (2 s: -1 -> +1)
a = rig.anim('turn', 2.0)
turn(a, lambda t: -1 + t)

rig.write(max_page=2048, webp=True, lossless=True, gap=10)
json.dump({'release': T_REL, 'size': [W * S, H * S]}, open(os.path.join(OUT, 'zeus_rig', 'meta.json'), 'w'))
