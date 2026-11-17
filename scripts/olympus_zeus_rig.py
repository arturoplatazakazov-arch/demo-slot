"""Olympus Thunder · Tides 2 — pseudo-3D Zeus rig (Spine 4.1, built in code).

    ~/.venvs/art/bin/python scripts/olympus_zeus_rig.py [PARTS_DIR]

Parts (PARTS_DIR, default ~/ot2-work/rig, made by its parts.py):
  p_body.png   — the SAME Zeus with both arms erased (ChatGPT edit of the hero, aligned to it)
  p_r_upper / p_r_fore / p_bolt — raised right arm (viewer's left) cut from the original hero
  p_l_fore / p_orb               — lower left arm with the energy ball
All parts share the hero canvas (1199x1312), so they re-assemble pixel-exactly.

Pseudo-3D: the body is ONE weighted mesh; the head is split into a front layer (face, beard
centre) and a back layer (hair rim) by weights on head_f / head_b, the torso into chest_f / chest_b —
moving front and back by different amounts reads as a turn. Arms are rigid regions on a bone chain.

Clips: idle (loop), windup, throw (event 'release' = the moment the bolt leaves the fist; the lab /
game draws the flying lightning itself from the bolt bone to the targets), charge (orb hand),
turn (debug sweep).
Output: front/img/olympus-thunder/tides2/zeus_rig/animation.{json,atlas,webp}  (PMA)
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from olympus_spine_lib import Rig, clamp, smooth, seg, keys, loop_sin, out_cubic, in_cubic, in_out, out_back  # noqa: E402

PARTS = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/ot2-work/rig')
OUT = os.path.join(os.path.dirname(__file__), '..', 'front/img/olympus-thunder/tides2')
W, H = 1199, 1312
S = 0.5           # skeleton units per image px (rig is 600x656 units; textures keep full res)


def sk(x, y):
    """image px -> skeleton units (origin = image centre, y up)."""
    return ((x - W / 2) * S, (H / 2 - y) * S)


def load(n):
    return Image.open(os.path.join(PARTS, f'p_{n}.png')).convert('RGBA')


def crop(im):
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 4)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    return im.crop((x0, y0, x1, y1)), (x0 + x1) / 2, (y0 + y1) / 2


def sstep(a, b, v):
    return smooth((v - a) / (b - a)) if b != a else float(v >= a)


rig = Rig('zeus_rig', W * S, H * S, OUT, res=1 / S)

# ---------------------------------------------------------------- bones ----
J = {  # joints in hero image px
    'hips': (560, 1090), 'chest': (560, 760), 'head': (650, 520), 'beard': (690, 470),
    'r_shoulder': (300, 585), 'r_elbow': (70, 655), 'r_fist': (285, 330), 'bolt': (285, 330),
    'l_elbow': (900, 1090), 'orb': (1010, 850), 'cloak_l': (240, 800), 'cloak_r': (900, 700),
}
rig.bone_at('hips', 'root', *sk(*J['hips']))
rig.bone_at('chest', 'hips', *sk(*J['chest']))
rig.bone_at('chest_f', 'chest', *sk(*J['chest']))
rig.bone_at('chest_b', 'chest', *sk(*J['chest']))
rig.bone_at('head', 'chest', *sk(*J['head']))
rig.bone_at('head_f', 'head', *sk(*J['head']))
rig.bone_at('head_b', 'head', *sk(*J['head']))
rig.bone_at('beard', 'head_f', *sk(*J['beard']))
rig.bone_at('cloak_l', 'hips', *sk(*J['cloak_l']))
rig.bone_at('cloak_r', 'chest', *sk(*J['cloak_r']))
rig.bone_at('r_shoulder', 'chest_f', *sk(*J['r_shoulder']))
rig.bone_at('r_elbow', 'r_shoulder', *sk(*J['r_elbow']))
rig.bone_at('r_fist', 'r_elbow', *sk(*J['r_fist']))
rig.bone_at('bolt', 'r_fist', *sk(*J['bolt']))
rig.bone_at('l_elbow', 'chest_f', *sk(*J['l_elbow']))
rig.bone_at('orb', 'l_elbow', *sk(*J['orb']))
rig.bone_at('bolt_tip', 'r_fist', *sk(330, 250))   # where the thrown lightning starts: just above the fist (lab reads it)


def world_xy(bone):
    m = rig.world(bone)
    return m[0, 2], m[1, 2]


# ----------------------------------------------------------- body mesh -----
def weights(px, py):
    """skeleton (px,py) -> [(bone, w)]: hips/chest blend, head with front/back depth, beard, cloak."""
    x = px / S + W / 2
    y = H / 2 - py / S
    ws = []
    head = (1 - sstep(470, 570, y)) * (sstep(380, 470, x))
    torso = 1 - head
    chest = torso * (1 - sstep(820, 990, y))
    hips = torso - chest
    # cloak flaps swing from their own bones
    cl = hips * sstep(330, 120, x) * sstep(820, 1000, y) + chest * sstep(300, 90, x) * sstep(700, 880, y)
    cr = torso * sstep(880, 1060, x) * sstep(620, 760, y) * (1 - sstep(1150, 1260, y))
    chest -= min(chest, cr) if chest > 0 else 0
    hips -= min(hips, cl)
    # torso depth: centre (clasp, straps) front, sides back
    cf = chest * (1 - sstep(130, 300, abs(x - 560)))
    cb = chest - cf
    # head depth: face + beard centre front, hair rim back
    dx, dy = (x - 690) / 190, (y - 380) / 230
    face = head * clamp(1.25 - math.hypot(dx, dy))
    beard = face * sstep(440, 560, y) * (1 - sstep(140, 230, abs(x - 700)))
    face -= beard
    back = head - face - beard
    for b, w in (('hips', hips), ('chest_f', cf), ('chest_b', cb), ('cloak_l', cl), ('cloak_r', cr),
                 ('head_f', face), ('head_b', back), ('beard', beard)):
        if w > 1e-3:
            ws.append((b, w))
    return ws or [('hips', 1.0)]


body, bcx, bcy = crop(load('body'))
rig.image('body', body)
cx, cy = sk(bcx, bcy)
rig.mesh_grid('body', 'body', cx, cy, body.width * S, body.height * S, weights, nx=20, ny=22, bone='hips')

# ------------------------------------------------------------- arms --------
def part(slot, bone, name, blend=None):
    im, pcx, pcy = crop(load(name))
    rig.image(name, im)
    wx, wy = sk(pcx, pcy)
    bx, by = world_xy(bone)
    rig.region(slot, bone, name, x=wx - bx, y=wy - by, w=im.width * S, h=im.height * S, blend=blend)


part('l_fore', 'l_elbow', 'l_fore')
part('orb', 'orb', 'orb')
im_o = load('orb')
o_im, o_x, o_y = crop(im_o)
rig.image('orb_glow', o_im)
ox, oy = sk(o_x, o_y); obx, oby = world_xy('orb')
rig.region('orb_glow', 'orb', 'orb_glow', x=ox - obx, y=oy - oby, w=o_im.width * S, h=o_im.height * S, blend='additive')
part('r_upper', 'r_shoulder', 'r_upper')
part('r_fore', 'r_elbow', 'r_fore')
part('bolt', 'bolt', 'bolt')
# bright copies for the glow pulses (additive)
im_b = load('bolt')
rig.image('bolt_glow', crop(im_b)[0])
bx, by = world_xy('bolt')
c_im, c_x, c_y = crop(im_b)
gx, gy = sk(c_x, c_y)
rig.region('bolt_glow', 'bolt', 'bolt_glow', x=gx - bx, y=gy - by, w=c_im.width * S, h=c_im.height * S, blend='additive')
rig.event('release')

# ---------------------------------------------------------- animations -----
TAU = 2 * math.pi


def breathe(a, period=4.0, k=1.0):
    a.bone('chest', 'scale', lambda t: (1 + 0.006 * k * math.sin(TAU * t / period), 1 + 0.012 * k * math.sin(TAU * t / period)))
    a.bone('head', 'rotate', lambda t: 1.2 * k * math.sin(TAU * t / period + 0.8))
    a.bone('beard', 'rotate', lambda t: 2.2 * k * math.sin(TAU * t / period + 1.6))
    a.bone('cloak_l', 'rotate', lambda t: 1.6 * k * math.sin(TAU * t / period + 0.4))
    a.bone('cloak_r', 'rotate', lambda t: -1.4 * k * math.sin(TAU * t / period + 1.1))


# idle: breathing, arms float, bolt burns like a candle, orb pulses (4 s loop)
a = rig.anim('idle', 4.0)
breathe(a)
a.bone('r_shoulder', 'rotate', lambda t: 1.8 * math.sin(TAU * t / 4 + 0.3))
a.bone('r_elbow', 'rotate', lambda t: 2.5 * math.sin(TAU * t / 4 + 0.9))
a.bone('l_elbow', 'rotate', lambda t: 1.5 * math.sin(TAU * t / 4 + 2.0))
a.bone('orb', 'scale', lambda t: 1 + 0.05 * math.sin(TAU * t / 1.0))
a.rgba('bolt_glow', lambda t: 0.25 + 0.2 * (0.5 + 0.5 * math.sin(TAU * t / 0.5)) * (0.6 + 0.4 * math.sin(TAU * t / 1.3)))
a.rgba('orb_glow', lambda t: 0.2 + 0.25 * (0.5 + 0.5 * math.sin(TAU * t / 0.5)))


def turn(a, fn):
    """pseudo-3D turn: fn(t) in -1..1 (+ = toward the slot on the right)."""
    a.bone('head_f', 'translate', lambda t: (10 * fn(t), -1.5 * abs(fn(t))))
    a.bone('head_b', 'translate', lambda t: (-5 * fn(t), 0))
    a.bone('chest_f', 'translate', lambda t: (6 * fn(t), 0))
    a.bone('chest_b', 'translate', lambda t: (-3 * fn(t), 0))
    a.bone('head', 'rotate', lambda t: -3 * fn(t))


# throw: wind-up (0-0.5), whip (0.5-0.68, release at 0.6), follow-through, recover (to 1.8)
T_REL = 0.60
a = rig.anim('throw', 1.8)
breathe(a, k=0.5)
a.bone('r_shoulder', 'rotate', lambda t: keys(t, [(0, 0), (0.45, -12), (0.62, 6), (0.9, 4), (1.8, 0)]))
# foreshortening = depth: arm goes back (shorter) on the wind-up, comes at the viewer (longer) on the whip
a.bone('r_shoulder', 'scale', lambda t: (keys(t, [(0, 1), (0.45, 0.9), (0.62, 1.07), (0.95, 1.03), (1.8, 1)]), 1))
a.bone('r_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 34), (0.52, 26), (0.62, -24), (0.9, -20), (1.8, 0)]))
a.bone('r_elbow', 'scale', lambda t: (keys(t, [(0, 1), (0.45, 0.93), (0.62, 1.08), (0.95, 1.04), (1.8, 1)]),) * 2)
a.bone('r_fist', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 14), (0.62, -16), (1.0, -10), (1.8, 0)]))
a.bone('chest', 'rotate', lambda t: keys(t, [(0, 0), (0.45, 2.5), (0.66, -3.5), (1.8, 0)]))
a.bone('hips', 'translate', lambda t: (keys(t, [(0, 0), (0.45, -6), (0.66, 9), (1.8, 0)]), 0))
turn(a, lambda t: keys(t, [(0, 0), (0.4, -0.6), (0.66, 1.0), (1.2, 0.8), (1.8, 0)]))
a.bone('l_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.45, -4), (0.7, 6), (1.8, 0)]))
a.rgba('bolt', lambda t: 1.0 if t < T_REL else (0.0 if t < 1.25 else smooth((t - 1.25) / 0.35)))
a.rgba('bolt_glow', lambda t: (0.3 + 0.7 * smooth(t / 0.5)) if t < T_REL else (0.0 if t < 1.25 else 0.3 * smooth((t - 1.25) / 0.35)))
a.event('release', T_REL)

# charge: the orb hand lifts and the orb swells (for "Zeus charges a multiplier")
a = rig.anim('charge', 1.2)
breathe(a, k=0.5)
a.bone('l_elbow', 'rotate', lambda t: keys(t, [(0, 0), (0.5, 9), (0.8, 7), (1.2, 0)]))
a.bone('orb', 'scale', lambda t: keys(t, [(0, 1), (0.5, 1.35), (0.8, 1.2), (1.2, 1)], out_back))
a.rgba('orb_glow', lambda t: 0.2 + 0.8 * math.sin(math.pi * clamp(t / 1.2)))
turn(a, lambda t: keys(t, [(0, 0), (0.5, 0.5), (1.2, 0)]))

# turn: debug sweep for the lab slider (2 s: -1 -> +1)
a = rig.anim('turn', 2.0)
turn(a, lambda t: -1 + t)

rig.write(max_page=2048, webp=True)
meta = {'release': T_REL, 'size': [W * S, H * S]}
json.dump(meta, open(os.path.join(OUT, 'zeus_rig', 'meta.json'), 'w'))
