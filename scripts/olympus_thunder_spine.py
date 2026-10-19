"""Olympus Thunder: every Spine skeleton of the game, built in code from the
cut parts (scripts/olympus_thunder_build.py -> front/img/olympus-thunder/parts).

    <venv with numpy + pillow> python scripts/olympus_thunder_spine.py [name ...]

Skeletons (front/img/olympus-thunder/spine/<name>/animation.*):
  zeus     cut-out character rig: torso, raised arm + fist + bolt, forearm +
           hand, head with a WEIGHTED-MESH hair chain, mesh beard chain, mesh
           cloak chain, eye / bolt / palm glows. Clips: idle, orb, big_mult,
           fs, jackpot, bigwin (every action clip ends in the setup pose, the
           runtime mixes them back into idle).
  orb      multiplier sphere: core, electric shell, orbiting band, halo.
           Clips: idle, land, charge, fade.
  symbols  win clip per symbol `win_<code>` — body motion per symbol, halo,
           and a light sweep CLIPPED to the symbol's silhouette.
  fx       per-cell discharge `burst` (tumble removal).
  strike   lightning strike over the board `strike`.
  shower   coin + laurel shower `loop` for the big-win popups.
  logo     `idle`: light sweep inside the letters, crest bolt flicker.
  bg       sky life behind the temple: drifting cloud banks + distant
           lightning, `idle` (base) and `fs` (charged, purple).

Units: every skeleton's box is what its DOM anchor maps to (spine.js uses
the skeleton bounds as boundsOverride), so placements below are in the
anchor's design px.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from olympus_spine_lib import (  # noqa: E402
    Rig, bright_copy, clamp, flicker, glow_of, hull_polygon, in_out, keys, lerp, loop_sin,
    out_back, out_cubic, seg, shine_bar, smooth, soft_dot,
)

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "front/img/olympus-thunder"
PARTS = IMG / "parts"
OUT = str(IMG / "spine")


def part(name: str) -> Image.Image:
    return Image.open(PARTS / f"{name}.png").convert("RGBA")


def tint(im: Image.Image, rgb) -> Image.Image:
    arr = np.asarray(im).astype(np.float32)
    lum = arr[..., :3].mean(axis=2, keepdims=True) / 255
    arr[..., :3] = np.clip(lum * np.array(rgb, np.float32), 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def strip_marble(im: Image.Image, box) -> Image.Image:
    """Remove the marble 'joint caps' the parts were painted with (grey,
    bright, unsaturated) inside `box` (x0,y0,x1,y1 in image px)."""
    arr = np.asarray(im).copy()
    x0, y0, x1, y1 = box
    sub = arr[y0:y1, x0:x1].astype(np.int16)
    mx, mn = sub[..., :3].max(axis=2), sub[..., :3].min(axis=2)
    marble = ((mx - mn) < 38) & (mn > 120)
    from scipy import ndimage
    marble = ndimage.binary_opening(marble, iterations=2)
    marble = ndimage.binary_dilation(marble, iterations=3)
    a = arr[y0:y1, x0:x1, 3].astype(np.float32)
    soft = ndimage.gaussian_filter(marble.astype(np.float32), 1.5)
    arr[y0:y1, x0:x1, 3] = (a * (1 - np.clip(soft * 1.4, 0, 1))).astype(np.uint8)
    return Image.fromarray(arr)


# =============================================================== ZEUS ======
# Anatomy, measured on the cut parts (each part in its OWN image px, y down).
TORSO_WAIST = (317, 540)       # torso image point that is the skeleton origin
NECK = (335, 75)               # torso: where the head sits
SHOULDER_R = (75, 170)         # torso: viewer-left stump (raised arm)
ELBOW_L = (470, 360)           # torso: where the forearm emerges from the cloak
CLASP = (560, 100)             # torso: cloak clasp
HEAD_PIVOT = (390, 290)        # head image: neck
HEAD_MOUTH = (435, 215)        # head image: moustache root
EYES = [(405, 132), (468, 136)]
HAIR_CHAIN = [(330, 150), (225, 175), (125, 205), (30, 245)]   # head image
BEARD_CHAIN = [(165, 40), (190, 165), (232, 285), (300, 410)]  # beard image
ARM_R_PIVOT = (250, 470)       # arm_r image: shoulder
ARM_R_FIST = (215, 75)
ARM_L_PIVOT = (40, 355)        # arm_l image: elbow
ARM_L_HAND = (238, 92)
ARM_L_ROT = -18                # setup rotation (deg, CCW+): forearm across the chest
CLOAK_CHAIN = [(240, 75), (320, 190), (440, 250), (565, 235)]  # cloak image
CLOAK_PIVOT = CLOAK_CHAIN[0]
# Lower body (second parts sheet, src/zeus_legs): scaled so the hips' belt
# matches the torso's waist width (torso px 154..461 vs belt 124..382).
LOW_K = 307 / 258
HIPS_BELT_X = 253          # hips image: belt centre
HIPS_TOP_TORSO_Y = 528     # torso image row where the belt starts (overlaps the cuirass edge)
LEG_SPREAD = 74            # world px from the centre line to each hip joint
LEG_ROT = 9                # deg outward (feet apart, heroic stance)


def tw(p):
    """torso px -> world (y up, origin at the waist)."""
    return (p[0] - TORSO_WAIST[0], TORSO_WAIST[1] - p[1])


def chain_weights(points_world, root_bone, chain_bones, falloff, root_mask=None):
    """weights(px,py) for a mesh skinned to a chain: each chain bone gets a
    gaussian of the distance to its joint; `root_mask(px,py)` -> 0..1 pins
    part of the mesh to the root bone (a face that must not wave)."""
    def fn(px, py):
        ws = []
        for b, (bx, by) in zip(chain_bones, points_world):
            d = math.hypot(px - bx, py - by)
            ws.append((b, math.exp(-(d / falloff) ** 2)))
        total = sum(w for _, w in ws) or 1
        ws = [(b, w / total) for b, w in ws]
        pin = root_mask(px, py) if root_mask else 0
        if pin:
            ws = [(b, w * (1 - pin)) for b, w in ws] + [(root_bone, pin)]
        return ws
    return fn


def build_zeus():
    torso = strip_marble(part("zeus_torso"), (0, 60, 150, 280))
    torso = strip_marble(torso, (560, 110, 634, 260))
    arm_r = strip_marble(part("zeus_arm_r"), (190, 380, 307, 555))
    head, beard, arm_l, cloak, bolt = (part(f"zeus_{n}") for n in ("head", "beard", "arm_l", "cloak", "bolt"))

    # world positions of the pivots
    neck_w = tw(NECK)
    head_off = lambda p: (neck_w[0] + p[0] - HEAD_PIVOT[0], neck_w[1] - (p[1] - HEAD_PIVOT[1]))  # noqa: E731
    mouth_w = head_off(HEAD_MOUTH)
    beard_off = lambda p: (mouth_w[0] + p[0] - BEARD_CHAIN[0][0], mouth_w[1] - (p[1] - BEARD_CHAIN[0][1]))  # noqa: E731
    sh_w = tw(SHOULDER_R)
    el_w = tw(ELBOW_L)
    clasp_w = tw(CLASP)
    cloak_off = lambda p: (clasp_w[0] + p[0] - CLOAK_PIVOT[0], clasp_w[1] - (p[1] - CLOAK_PIVOT[1]))  # noqa: E731

    # bounding box of the assembled figure (setup pose), with headroom for the bolt
    xs = [-TORSO_WAIST[0], torso.width - TORSO_WAIST[0], sh_w[0] - ARM_R_PIVOT[0] - 120,
          cloak_off((cloak.width, 0))[0], head_off((0, 0))[0]]
    left, right = min(xs) - 20, max(xs) + 20
    top = sh_w[1] + (ARM_R_PIVOT[1] - 0) + 330
    legs = [part("zeus_leg_l"), part("zeus_leg_r")]
    hips_im = part("zeus_hips")
    cloak_tail = ImageOps.mirror(part("zeus_cloak_tail"))
    hips_h = hips_im.height * LOW_K
    joint_y = tw((0, HIPS_TOP_TORSO_Y))[1] - hips_h * 0.42
    leg_len = max(l.height for l in legs) * LOW_K
    bottom = joint_y - leg_len * math.cos(math.radians(LEG_ROT)) - 30
    left = min(left, -LEG_SPREAD - leg_len * math.sin(math.radians(LEG_ROT)) - 160, -cloak_tail.width * LOW_K * 0.9 - 60)
    W, H = right - left, top - bottom
    R = Rig("zeus", W, H, OUT, res=1.0)
    # the skeleton box must be centred on the origin for spine.js: shift
    # everything by the box centre through the root's child 'hip'
    cx, cy = (left + right) / 2, (top + bottom) / 2

    for n, im in (("torso", torso), ("arm_r", arm_r), ("head", head), ("beard", beard), ("arm_l", arm_l),
                  ("cloak", cloak), ("bolt", bolt)):
        R.image(n, im)
    R.image("bolt_glow", glow_of(bolt, (120, 220, 255), radius=18, grow=1.6))
    R.image("eye", soft_dot(64, (150, 235, 255), 1.8))
    R.image("aura", soft_dot(256, (140, 210, 255), 2.4))
    R.image("aura_gold", soft_dot(256, (255, 200, 90), 2.4))
    for i in (3, 4, 5):
        R.image(f"spark{i}", part(f"bolt_{i}"))
    R.image("flash", bright_copy(torso, 1.0))
    R.image("hips", hips_im)
    R.image("leg_l", legs[0])
    R.image("leg_r", legs[1])
    R.image("cloak_tail", cloak_tail)

    R.bone_at("hip", "root", -cx, -cy)
    R.bone_at("torso", "hip", -cx, -cy)

    def W_(p):  # world -> shifted world
        return (p[0] - cx, p[1] - cy)

    # cloak chain (behind everything)
    cw = [W_(cloak_off(p)) for p in CLOAK_CHAIN]
    R.bone_at("cloak", "torso", *cw[0])
    prev = "cloak"
    for i, p in enumerate(cw[1:], 1):
        R.bone_at(f"cloak{i}", prev, *p)
        prev = f"cloak{i}"
    # arm + fist + bolt
    shw = W_(sh_w)
    R.bone_at("arm_r", "torso", *shw)
    fist_w = (shw[0] + ARM_R_FIST[0] - ARM_R_PIVOT[0], shw[1] - (ARM_R_FIST[1] - ARM_R_PIVOT[1]))
    R.bone_at("fist", "arm_r", *fist_w)
    fore = np.array([ARM_R_FIST[0] - 40, -(ARM_R_FIST[1] - 380)], float)
    tilt = math.degrees(math.atan2(fore[0], fore[1]))  # from vertical, clockwise
    R.bone_at("bolt", "fist", *fist_w, rot=-tilt)
    # head, hair, beard, eyes
    nw = W_(neck_w)
    R.bone_at("head", "torso", *nw)
    hw = [W_(head_off(p)) for p in HAIR_CHAIN]
    R.bone_at("hair0", "head", *hw[0])
    prev = "hair0"
    for i, p in enumerate(hw[1:], 1):
        R.bone_at(f"hair{i}", prev, *p)
        prev = f"hair{i}"
    bw = [W_(beard_off(p)) for p in BEARD_CHAIN]
    R.bone_at("beard", "head", *bw[0])
    prev = "beard"
    for i, p in enumerate(bw[1:], 1):
        R.bone_at(f"beard{i}", prev, *p)
        prev = f"beard{i}"
    for i, e in enumerate(EYES):
        R.bone_at(f"eye{i}", "head", *W_(head_off(e)))
    # forearm + hand
    elw = W_(el_w)
    R.bone_at("arm_l", "torso", *elw, rot=ARM_L_ROT)
    a = math.radians(ARM_L_ROT)
    hx, hy = ARM_L_HAND[0] - ARM_L_PIVOT[0], -(ARM_L_HAND[1] - ARM_L_PIVOT[1])
    R.bone_at("hand", "arm_l", elw[0] + hx * math.cos(a) - hy * math.sin(a), elw[1] + hx * math.sin(a) + hy * math.cos(a), rot=ARM_L_ROT)
    R.bone_at("aura", "torso", *W_(tw((317, 200))))
    # lower body: the legs stand on their own bone (the feet must not slide
    # when the torso breathes / leans); the skirt rides on the torso
    R.bone_at("ground", "root", *W_((0, 0)))
    R.bone_at("leg_l", "ground", *W_((-LEG_SPREAD, joint_y)), rot=-LEG_ROT)
    R.bone_at("leg_r", "ground", *W_((LEG_SPREAD, joint_y)), rot=LEG_ROT)
    hips_top_w = tw((TORSO_WAIST[0], HIPS_TOP_TORSO_Y))
    R.bone_at("hips", "torso", *W_(hips_top_w))
    R.bone_at("cape", "torso", *W_(tw((250, 120))))

    # ---- attachments, back to front ----
    R.region("aura", "aura", "aura", w=1100, blend="additive", color="ffffff00")
    # cloak mesh: pinned at the clasp, swaying outward along the chain
    cc = W_(cloak_off((cloak.width / 2, cloak.height / 2)))
    R.mesh_grid("cloak", "cloak", cc[0], cc[1], cloak.width, cloak.height,
                chain_weights(cw, "cloak", ["cloak"] + [f"cloak{i}" for i in range(1, len(cw))], 120,
                              root_mask=lambda x, y: clamp(1 - (math.hypot(x - cw[0][0], y - cw[0][1]) / 90))),
                nx=6, ny=5, bone="cloak")
    # long cloak tail behind the legs, hanging from the back of the shoulders
    R.region("cloak_tail", "cape", "cloak_tail", x=-cloak_tail.width * LOW_K * 0.36,
             y=-cloak_tail.height * LOW_K * 0.5, w=cloak_tail.width * LOW_K)
    for side, im in (("leg_l", legs[0]), ("leg_r", legs[1])):
        R.region(side, side, side, x=0, y=-(im.height * LOW_K) / 2 + 40, w=im.width * LOW_K)
    # bolt: behind the fist, grip ~58% down its length
    grip = 0.58
    R.region("bolt_glow", "bolt", "bolt_glow", x=0, y=(grip - 0.5) * bolt.height,
             w=glow_of(bolt, radius=18).width, blend="additive", color="ffffffcc")
    R.region("bolt", "bolt", "bolt", x=0, y=(grip - 0.5) * bolt.height)
    # torso bone sits at the waist: its attachment offset is torso-space
    R.region("torso", "torso", "torso", *tw((torso.width / 2, torso.height / 2)))
    R.region("hips", "hips", "hips", x=(hips_im.width / 2 - HIPS_BELT_X) * LOW_K,
             y=-hips_h / 2, w=hips_im.width * LOW_K)
    R.region("flash", "torso", "flash", *tw((torso.width / 2, torso.height / 2)), blend="additive", color="ffffff00")
    R.region("arm_r", "arm_r", "arm_r", x=arm_r.width / 2 - ARM_R_PIVOT[0], y=-(arm_r.height / 2 - ARM_R_PIVOT[1]))
    # head mesh: face pinned to the head bone, hair waves along the chain
    hc = W_(head_off((head.width / 2, head.height / 2)))
    face_x = W_(head_off((300, 0)))[0]
    R.mesh_grid("head", "head", hc[0], hc[1], head.width, head.height,
                chain_weights(hw, "head", [f"hair{i}" for i in range(len(hw))], 85,
                              root_mask=lambda x, y: clamp((x - face_x + 40) / 80)),
                nx=8, ny=5, bone="head")
    bc = W_(beard_off((beard.width / 2, beard.height / 2)))
    R.mesh_grid("beard", "beard", bc[0], bc[1], beard.width, beard.height,
                chain_weights(bw, "beard", ["beard"] + [f"beard{i}" for i in range(1, len(bw))], 95,
                              root_mask=lambda x, y: clamp(1 - (math.hypot(x - bw[0][0], y - bw[0][1]) / 70))),
                nx=4, ny=6, bone="beard")
    for i in range(len(EYES)):
        R.region(f"eye{i}", f"eye{i}", "eye", w=46, blend="additive", color="ffffffb0")
    R.region("arm_l", "arm_l", "arm_l", x=arm_l.width / 2 - ARM_L_PIVOT[0], y=-(arm_l.height / 2 - ARM_L_PIVOT[1]))
    R.region("spark", "hand", "spark3", y=60, h=150, blend="additive", color="ffffffcc")
    R.atts["spark"]["spark4"] = dict(R.atts["spark"]["spark3"], path="spark4")
    R.atts["spark"]["spark5"] = dict(R.atts["spark"]["spark3"], path="spark5")
    R.need["spark4"] = R.need["spark5"] = R.need["spark3"]

    hair = [f"hair{i}" for i in range(len(hw))]
    beardb = ["beard"] + [f"beard{i}" for i in range(1, len(bw))]
    cloakb = ["cloak"] + [f"cloak{i}" for i in range(1, len(cw))]

    def ambient(A, dur, k=1.0, wind=1.0):
        """breathing + wind, phase-locked to `dur` so loops are seamless."""
        A.bone("hip", "translate", lambda t: (0, 3 * k * loop_sin(t, dur / 1)))
        A.bone("torso", "scale", lambda t: (1, 1 + 0.008 * k * loop_sin(t, dur, 0.1)))
        A.bone("head", "rotate", lambda t: 1.2 * k * loop_sin(t, dur, 0.3))
        for i, b in enumerate(hair):
            A.bone(b, "rotate", lambda t, i=i: (1.5 + 2.2 * i) * wind * loop_sin(t, dur / 2, -0.12 * i))
        for i, b in enumerate(beardb):
            A.bone(b, "rotate", lambda t, i=i: (0.6 + 1.1 * i) * wind * loop_sin(t, dur / 2, 0.1 - 0.13 * i))
        for i, b in enumerate(cloakb):
            A.bone(b, "rotate", lambda t, i=i: (0.8 + 1.6 * i) * wind * loop_sin(t, dur / 2, 0.25 - 0.12 * i))
        A.rgba("bolt_glow", lambda t: 0.55 + 0.45 * flicker(t, 22, 1.3))
        A.rgba("spark", lambda t: 0.25 + 0.75 * flicker(t, 30, 2.7))
        A.attach("spark", [(k_ * 0.1, f"spark{3 + (k_ % 3)}") for k_ in range(int(dur * 10))])
        for i in range(len(EYES)):
            A.rgba(f"eye{i}", lambda t: 0.55 + 0.25 * loop_sin(t, dur / 2) + 0.1 * flicker(t, 9))

    def tail_sway(A, dur, amp=3.0):
        A.bone("cape", "rotate", lambda t: amp * loop_sin(t, dur / 2, 0.3))

    A = R.anim("idle", 4.0)
    ambient(A, 4.0)
    tail_sway(A, 4.0)

    # orb landed: a short fist pump, the bolt flares, eyes flash
    A = R.anim("orb", 1.2)
    A.bone("arm_r", "rotate", lambda t: keys(t, [(0, 0), (0.18, 9), (0.42, -4), (0.75, 1.5), (1.2, 0)]))
    A.bone("fist", "rotate", lambda t: keys(t, [(0, 0), (0.18, -6), (0.5, 3), (1.2, 0)]))
    A.bone("head", "rotate", lambda t: keys(t, [(0, 0), (0.2, -3), (0.6, 1), (1.2, 0)]))
    A.bone("bolt", "scale", lambda t: (1, keys(t, [(0, 1), (0.2, 1.12), (0.5, 0.97), (1.2, 1)])))
    A.rgba("bolt_glow", lambda t: keys(t, [(0, 0.7), (0.2, 1), (1.2, 0.7)]))
    for i in range(len(EYES)):
        A.rgba(f"eye{i}", lambda t: keys(t, [(0, 0.6), (0.15, 1), (1.2, 0.6)]))
    A.rgba("spark", lambda t: 0.5 + 0.5 * flicker(t, 34))

    # big multiplier: wind-up and a HURL — the arm swings forward, torso leans
    A = R.anim("big_mult", 1.7)
    A.bone("arm_r", "rotate", lambda t: keys(t, [(0, 0), (0.35, 22), (0.55, -38), (0.85, -30), (1.3, 3), (1.7, 0)],
                                              ease=in_out))
    A.bone("fist", "rotate", lambda t: keys(t, [(0, 0), (0.35, 10), (0.55, -14), (1.7, 0)]))
    A.bone("torso", "rotate", lambda t: keys(t, [(0, 0), (0.35, 3), (0.6, -5), (1.2, -1), (1.7, 0)]))
    A.bone("hip", "translate", lambda t: (0, keys(t, [(0, 0), (0.35, -6), (0.6, 4), (1.7, 0)])))
    A.bone("head", "rotate", lambda t: keys(t, [(0, 0), (0.35, 4), (0.6, -6), (1.7, 0)]))
    for i, b in enumerate(hair):
        A.bone(b, "rotate", lambda t, i=i: keys(t, [(0, 0), (0.45, -4 - 3 * i), (0.75, 6 + 4 * i), (1.2, -2 - i), (1.7, 0)]))
    for i, b in enumerate(beardb):
        A.bone(b, "rotate", lambda t, i=i: keys(t, [(0, 0), (0.5, -3 - 2 * i), (0.8, 4 + 2 * i), (1.7, 0)]))
    for i, b in enumerate(cloakb):
        A.bone(b, "rotate", lambda t, i=i: keys(t, [(0, 0), (0.55, 5 + 3 * i), (0.9, -3 - 2 * i), (1.7, 0)]))
    A.rgba("bolt_glow", lambda t: keys(t, [(0, 0.7), (0.5, 1), (0.6, 1), (1.7, 0.7)]))
    A.bone("bolt", "scale", lambda t: (keys(t, [(0, 1), (0.55, 1.15), (1.0, 1), (1.7, 1)]), keys(t, [(0, 1), (0.55, 1.25), (1.0, 1)])))
    A.rgba("flash", lambda t: keys(t, [(0, 0), (0.55, 0), (0.62, 0.55), (1.0, 0)]))
    A.rgba("aura", lambda t: keys(t, [(0, 0), (0.55, 0), (0.62, 0.7), (1.5, 0)]))
    for i in range(len(EYES)):
        A.rgba(f"eye{i}", lambda t: keys(t, [(0, 0.6), (0.5, 1), (1.7, 0.6)]))

    # free spins / jackpot: both arms up, head thrown back, aura
    def triumph(name, dur, aura_slot_color):
        A = R.anim(name, dur)
        A.bone("arm_r", "rotate", lambda t: keys(t, [(0, 0), (0.4, -12), (0.8, -8), (1.2, -14), (dur - 0.4, -6), (dur, 0)]))
        A.bone("arm_l", "rotate", lambda t: keys(t, [(0, 0), (0.45, 38), (0.9, 30), (1.3, 40), (dur - 0.4, 12), (dur, 0)]))
        A.bone("hand", "rotate", lambda t: keys(t, [(0, 0), (0.45, -20), (dur - 0.4, -8), (dur, 0)]))
        A.bone("head", "rotate", lambda t: keys(t, [(0, 0), (0.4, 7), (1.0, 5), (dur - 0.3, 2), (dur, 0)]))
        A.bone("torso", "scale", lambda t: (1, keys(t, [(0, 1), (0.4, 1.03), (dur - 0.3, 1.01), (dur, 1)])))
        A.bone("hip", "translate", lambda t: (0, keys(t, [(0, 0), (0.4, 10), (0.8, 6), (1.2, 10), (dur, 0)])))
        for i, b in enumerate(hair):
            A.bone(b, "rotate", lambda t, i=i: (3 + 3 * i) * loop_sin(t, dur / 3, -0.15 * i) * (1 - seg(t, dur - 0.5, dur, 0, 1, smooth)))
        for i, b in enumerate(cloakb):
            A.bone(b, "rotate", lambda t, i=i: (2 + 3 * i) * loop_sin(t, dur / 3, 0.2 - 0.15 * i) * (1 - seg(t, dur - 0.5, dur, 0, 1, smooth)))
        A.rgba("aura", lambda t: (*aura_slot_color, keys(t, [(0, 0), (0.4, 0.85), (dur - 0.6, 0.6), (dur, 0)])))
        A.rgba("bolt_glow", lambda t: 0.7 + 0.3 * flicker(t, 26))
        A.rgba("spark", lambda t: 0.6 + 0.4 * flicker(t, 34))
        for i in range(len(EYES)):
            A.rgba(f"eye{i}", lambda t: keys(t, [(0, 0.6), (0.3, 1), (dur - 0.3, 1), (dur, 0.6)]))

    triumph("fs", 2.2, (0.75, 0.6, 1.0))
    triumph("jackpot", 2.2, (1.0, 0.85, 0.45))

    # big win: hearty laugh — three torso bounces, head bobs
    A = R.anim("bigwin", 2.4)
    bounce = lambda t: abs(math.sin(math.pi * t / 0.4)) * (1 - seg(t, 1.6, 2.4, 0, 1, smooth))  # noqa: E731
    A.bone("hip", "translate", lambda t: (0, 8 * bounce(t)))
    A.bone("head", "rotate", lambda t: 4 * math.sin(math.pi * t / 0.4) * (1 - seg(t, 1.6, 2.4, 0, 1, smooth)) + keys(t, [(0, 0), (0.3, 5), (2.0, 4), (2.4, 0)]))
    A.bone("arm_r", "rotate", lambda t: keys(t, [(0, 0), (0.3, -10), (2.0, -8), (2.4, 0)]))
    A.bone("arm_l", "rotate", lambda t: keys(t, [(0, 0), (0.35, 22), (2.0, 18), (2.4, 0)]))
    for i, b in enumerate(beardb):
        A.bone(b, "rotate", lambda t, i=i: (2 + 2 * i) * math.sin(math.pi * t / 0.4 - 0.6 * i) * (1 - seg(t, 1.6, 2.4, 0, 1, smooth)))
    A.rgba("aura", lambda t: (1.0, 0.85, 0.45, keys(t, [(0, 0), (0.3, 0.6), (2.0, 0.5), (2.4, 0)])))
    A.rgba("bolt_glow", lambda t: 0.7 + 0.3 * flicker(t, 26))

    R.write()
    return R


# ============================================================= GLYPHS ======
def cinzel(size: int):
    """Cinzel (the game's UI face) from the shipped woff2, bold axis."""
    import io
    from fontTools.ttLib import TTFont
    from PIL import ImageFont
    f = TTFont(ROOT / "front/fonts/cinzel-latin-30d2fd52.woff2")
    f.flavor = None
    buf = io.BytesIO()
    f.save(buf)
    buf.seek(0)
    font = ImageFont.truetype(buf, size)
    try:
        font.set_variation_by_axes([900])
    except Exception:
        pass
    return font


def glyph(ch: str, size=150) -> Image.Image:
    """One multiplier glyph: white-to-gold gradient, dark bronze stroke,
    warm outer glow — reads on the bright orb and on any background."""
    from PIL import ImageDraw, ImageFilter
    font = cinzel(size)
    pad = int(size * 0.22)
    l, t, r, b = font.getbbox(ch, stroke_width=int(size * 0.07))
    w, h = r - l + 2 * pad, b - t + 2 * pad
    mask = Image.new("L", (w, h))
    ImageDraw.Draw(mask).text((pad - l, pad - t), ch, font=font, fill=255)
    stroke = Image.new("L", (w, h))
    ImageDraw.Draw(stroke).text((pad - l, pad - t), ch, font=font, fill=255, stroke_width=int(size * 0.075), stroke_fill=255)
    grad = np.zeros((h, w, 3), np.float32)
    yy = np.linspace(0, 1, h)[:, None]
    top, mid, bot = np.array([255, 255, 240]), np.array([255, 222, 120]), np.array([235, 140, 20])
    g = np.where(yy < 0.5, top + (mid - top) * (yy / 0.5), mid + (bot - mid) * ((yy - 0.5) / 0.5))
    grad[:] = g[:, None, :] if g.ndim == 2 else g
    out = np.zeros((h, w, 4), np.float32)
    glow = np.asarray(stroke.filter(ImageFilter.GaussianBlur(size * 0.09))).astype(np.float32) / 255
    out[..., :3] = np.array([255, 120, 0])
    out[..., 3] = glow * 200
    st = np.asarray(stroke).astype(np.float32) / 255
    out[..., :3] = out[..., :3] * (1 - st[..., None]) + np.array([58, 26, 0]) * st[..., None]
    out[..., 3] = np.maximum(out[..., 3], st * 255)
    m = np.asarray(mask).astype(np.float32) / 255
    out[..., :3] = out[..., :3] * (1 - m[..., None]) + grad * m[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ================================================================ ORB ======
def build_orb():
    R = Rig("orb", 256, 256, OUT, res=1.3)
    sphere, arcs, ring = part("orb_sphere"), part("orb_arcs"), part("orb_ring")
    for n, im in (("sphere", sphere), ("arcs", arcs), ("ring", ring)):
        R.image(n, im)
    R.image("halo", glow_of(sphere, (255, 190, 60), radius=20, grow=1.1, strength=0.9))
    R.image("flash", bright_copy(sphere, 1.0))
    R.image("shock", part("fx_ring"))
    R.bone("body")
    R.bone("arcs", "body")
    R.bone("ring", "body", rot=-8)
    R.bone("shock")
    R.region("halo", "body", "halo", w=300, blend="additive", color="ffffff99")
    R.region("sphere", "body", "sphere", w=190)
    R.region("flash", "body", "flash", w=190, blend="additive", color="ffffff00")
    R.region("arcs", "arcs", "arcs", w=222, blend="additive", color="ffffffcc")
    R.region("ring", "ring", "ring", w=236)
    R.region("shock", "shock", "shock", w=256, blend="additive", color="ffffff00")
    # the value is part of the rig: layouts for "x5", "x25", "x100"; spine.js
    # fills the slots of the right layout with g_<char> attachments
    glyphs = {ch: glyph(ch) for ch in "x0123456789"}
    for ch, im in glyphs.items():
        R.image(f"g_{ch}", im)
    R.bone("num", "body", y=-2)
    digit_w = max(glyphs[d].width for d in "0123456789")
    for n, height in ((2, 118), (3, 100), (4, 84)):
        k = height / glyphs["0"].height
        widths = [glyphs["x"].width * k * 0.86] + [digit_w * k * 0.78] * (n - 1)
        total = sum(widths)
        x = -total / 2
        for i in range(n):
            cxi = x + widths[i] / 2 + (6 if i == 0 else 0)
            slot = f"n{n}_{i}"
            first = True
            for ch, im in glyphs.items():
                R.region(slot, "num", f"g_{ch}", x=cxi, y=-6 if ch == "x" else 0, h=height * (0.72 if ch == "x" else 1),
                         visible=False, add_to_existing=not first)
                first = False
            x += widths[i]

    A = R.anim("idle", 2.4)
    A.bone("body", "scale", lambda t: 1 + 0.03 * loop_sin(t, 2.4))
    A.bone("arcs", "rotate", lambda t: -360 * t / 2.4)
    A.rgba("arcs", lambda t: 0.45 + 0.55 * flicker(t, 16, 0.4))
    A.bone("ring", "scale", lambda t: (1, 1 + 0.12 * loop_sin(t, 2.4, 0.25)))
    A.bone("ring", "rotate", lambda t: 4 * loop_sin(t, 2.4))
    A.rgba("halo", lambda t: 0.5 + 0.2 * loop_sin(t, 1.2))

    A = R.anim("land", 0.55)
    A.bone("body", "scale", lambda t: lerp(1.7, 1, out_back(t / 0.4, 2.2)))
    A.rgba("flash", lambda t: keys(t, [(0, 1), (0.35, 0)]))
    A.bone("shock", "scale", lambda t: lerp(0.5, 1.9, out_cubic(t / 0.55)))
    A.rgba("shock", lambda t: keys(t, [(0, 1), (0.55, 0)]))
    A.rgba("halo", lambda t: keys(t, [(0, 1), (0.55, 0.6)]))
    A.rgba("arcs", lambda t: 0.6 + 0.4 * flicker(t, 40))

    A = R.anim("charge", 0.7)
    A.bone("body", "scale", lambda t: keys(t, [(0, 1), (0.25, 1.28), (0.5, 1.18), (0.7, 1.22)], out_cubic))
    A.rgba("flash", lambda t: keys(t, [(0, 0), (0.2, 0.8), (0.7, 0.3)]))
    A.rgba("arcs", lambda t: 0.5 + 0.5 * flicker(t, 55, 2))
    A.bone("arcs", "rotate", lambda t: -720 * t)
    A.rgba("halo", lambda t: keys(t, [(0, 0.6), (0.3, 1)]))
    A.bone("ring", "rotate", lambda t: 20 * math.sin(t * 30))

    A = R.anim("fade", 0.5)
    A.rgba("sphere", lambda t: (lerp(1, 0.45, t / 0.5), lerp(1, 0.45, t / 0.5), lerp(1, 0.5, t / 0.5), 1))
    A.rgba("arcs", lambda t: lerp(0.6, 0, t / 0.5))
    A.rgba("halo", lambda t: lerp(0.6, 0, t / 0.5))
    A.rgba("ring", lambda t: (lerp(1, 0.5, t / 0.5), lerp(1, 0.5, t / 0.5), lerp(1, 0.5, t / 0.5), 1))
    R.write()

    # static fallback / paytable tile, consistent with the rig (no band gem
    # under the number any more): halo + sphere + arcs + ring
    tile = Image.new("RGBA", (256, 256))
    halo = glow_of(sphere, (255, 190, 60), radius=20, grow=1.1, strength=0.6)
    halo = halo.resize((300, round(300 * halo.height / halo.width)))
    tile.alpha_composite(halo.crop(((300 - 256) // 2, (halo.height - 256) // 2, (300 - 256) // 2 + 256, (halo.height - 256) // 2 + 256)))
    for im, w in ((sphere, 190), (arcs, 222)):
        im2 = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
        tile.alpha_composite(im2, ((256 - im2.width) // 2, (256 - im2.height) // 2))
    r2 = ring.resize((236, round(236 * ring.height / ring.width)), Image.LANCZOS).rotate(8, expand=True, resample=Image.BICUBIC)
    tile.alpha_composite(r2, ((256 - r2.width) // 2, (256 - r2.height) // 2))
    tile.save(IMG / "symbols/orb.webp", "WEBP", quality=92, method=6)


# ============================================================ SYMBOLS ======
SYMBOL_CODES = ["helmet", "lyre", "amphora", "wreath", "ruby", "amethyst", "emerald", "sapphire", "citrine", "scatter", "eagle"]
GEMS = {"ruby", "amethyst", "emerald", "sapphire", "citrine"}
GLOW_COLOR = {
    "ruby": (255, 80, 70), "amethyst": (190, 110, 255), "emerald": (90, 255, 140), "sapphire": (90, 160, 255),
    "citrine": (255, 200, 80), "scatter": (130, 210, 255), "eagle": (255, 210, 90),
}


def build_symbols():
    R = Rig("symbols", 256, 256, OUT, res=1.0)
    R.image("shine", shine_bar())
    R.image("sparkle", part("fx_sparkle"))
    R.image("ring", part("fx_ring"))
    R.bone("body")
    R.bone("shine", "body", rot=-24)
    R.bone("sparkle", "body", x=-62, y=62)
    R.bone("ring")
    tiles = {c: Image.open(IMG / f"symbols/{c}.webp").convert("RGBA") for c in SYMBOL_CODES}
    for c, im in tiles.items():
        R.image(f"s_{c}", im)
        R.image(f"g_{c}", glow_of(im, GLOW_COLOR.get(c, (255, 214, 90)), radius=12, grow=1.3))
    R.region("ring", "ring", "ring", w=250, blend="additive", color="ffffff00")
    first = True
    for c, im in tiles.items():
        g = R.images[f"g_{c}"]
        R.region("glow", "body", f"g_{c}", w=256 * g.width / im.width, blend="additive", visible=False, add_to_existing=not first)
        first = False
    first = True
    for c in tiles:
        R.region("sym", "body", f"s_{c}", w=256, visible=False, add_to_existing=not first)
        first = False
    # one clipping polygon per symbol (its alpha hull, in skeleton units)
    R._slot("clip", "body", None)
    for c, im in tiles.items():
        poly = [(x - 128, 128 - y) for x, y in hull_polygon(im, n=22, inset=0.04)]
        flat = [round(v, 2) for p in poly for v in p]
        R.atts["clip"][f"clip_{c}"] = {"type": "clipping", "end": "shine", "vertexCount": len(poly), "vertices": flat}
    R.region("shine", "shine", "shine", w=70, h=420, blend="additive", color="ffffffd0")
    R.region("sparkle", "sparkle", "sparkle", w=120, blend="additive", color="ffffff00")

    dur = 0.76
    for c in tiles:
        A = R.anim(f"win_{c}", dur)
        A.attach("sym", [(0, f"s_{c}")]).attach("glow", [(0, f"g_{c}")]).attach("clip", [(0, f"clip_{c}")])
        A.bone("shine", "translate", lambda t: (lerp(-190, 190, in_out(t / dur)), 0))
        A.rgba("glow", lambda t: keys(t, [(0, 0), (0.18, 1), (dur, 0.55)]))
        pulse = lambda t: keys(t, [(0, 1), (0.16, 1.16), (0.34, 1.04), (0.5, 1.1), (dur, 1)], out_cubic)  # noqa: E731
        if c in GEMS:
            A.bone("body", "scale", lambda t: (pulse(t) * (1 - 0.06 * math.sin(math.pi * t / dur)), pulse(t)))
            A.bone("sparkle", "scale", lambda t: keys(t, [(0, 0), (0.2, 1.1), (0.45, 0.2), (dur, 0)]))
            A.bone("sparkle", "rotate", lambda t: -140 * t)
            A.rgba("sparkle", lambda t: keys(t, [(0, 0), (0.15, 1), (0.5, 0)]))
        elif c == "helmet":
            A.bone("body", "scale", pulse)
            A.bone("body", "rotate", lambda t: keys(t, [(0, 0), (0.18, 7), (0.4, -4), (0.6, 2), (dur, 0)]))
        elif c == "lyre":
            A.bone("body", "scale", lambda t: (pulse(t), pulse(t) * (1 + 0.04 * math.sin(t * 40) * (1 - t / dur))))
        elif c == "amphora":
            A.bone("body", "scale", pulse)
            A.bone("body", "rotate", lambda t: 7 * math.sin(t * 2 * math.pi / 0.38) * (1 - t / dur))
        elif c == "wreath":
            A.bone("body", "scale", pulse)
            A.bone("body", "rotate", lambda t: keys(t, [(0, 0), (0.3, -10), (0.6, 4), (dur, 0)]))
        elif c == "scatter":
            A.bone("body", "scale", pulse)
            A.bone("ring", "scale", lambda t: lerp(0.7, 1.25, out_cubic(t / dur)))
            A.bone("ring", "rotate", lambda t: -200 * t)
            A.rgba("ring", lambda t: keys(t, [(0, 0), (0.15, 1), (dur, 0.2)]))
        elif c == "eagle":
            A.bone("body", "scale", lambda t: (keys(t, [(0, 1), (0.16, 1.22), (0.34, 1.05), (0.5, 1.15), (dur, 1)]), pulse(t)))
            A.bone("body", "translate", lambda t: (0, keys(t, [(0, 0), (0.2, 12), (dur, 0)])))
    R.write()


# ================================================================= FX ======
def build_fx():
    R = Rig("fx", 256, 256, OUT, res=1.0)
    for n in ("burst", "ring", "debris", "streak", "sparkle"):
        R.image(n, part(f"fx_{n}"))
    R.image("dot", soft_dot(128, (200, 240, 255), 1.6))
    R.bone("burst")
    R.bone("ring")
    R.bone("streak", rot=35)
    R.region("dot", "root", "dot", w=230, blend="additive", color="ffffff00")
    R.region("burst", "burst", "burst", w=250, blend="additive", color="ffffff00")
    R.region("ring", "ring", "ring", w=250, blend="additive", color="ffffff00")
    R.region("streak", "streak", "streak", w=230, blend="additive", color="ffffff00")
    shards = [(-1, 1.2), (1.1, 0.9), (-0.9, -0.2), (0.8, -0.1), (0.1, 1.4)]
    for i, (dx, dy) in enumerate(shards):
        R.bone(f"shard{i}", rot=i * 63)
        R.region(f"shard{i}", f"shard{i}", "debris", w=70 - i * 6, color="ffffff00")
    dur = 0.5
    A = R.anim("burst", dur)
    A.rgba("dot", lambda t: keys(t, [(0, 1), (0.22, 0)]))
    A.bone("burst", "scale", lambda t: lerp(0.35, 1.35, out_cubic(t / 0.4)))
    A.bone("burst", "rotate", lambda t: 40 * t)
    A.rgba("burst", lambda t: keys(t, [(0, 1), (0.08, 1), (0.42, 0)]))
    A.bone("ring", "scale", lambda t: lerp(0.3, 1.5, out_cubic(t / dur)))
    A.rgba("ring", lambda t: keys(t, [(0, 0.9), (dur, 0)]))
    A.rgba("streak", lambda t: flicker(t, 50) * (1 - t / dur))
    A.bone("streak", "scale", lambda t: (lerp(0.6, 1.2, t / dur), 1))
    for i, (dx, dy) in enumerate(shards):
        A.bone(f"shard{i}", "translate", lambda t, dx=dx, dy=dy: (dx * 150 * out_cubic(t / dur), (dy * 120 * out_cubic(t / dur)) - 260 * (t / dur) ** 2))
        A.bone(f"shard{i}", "rotate", lambda t, i=i: (220 if i % 2 else -220) * t)
        A.rgba(f"shard{i}", lambda t: keys(t, [(0, 0), (0.04, 1), (0.3, 1), (dur, 0)]))
    R.write()


def build_strike():
    """A bolt from the sky onto the board centre (board-sized box)."""
    R = Rig("strike", 800, 700, OUT, res=0.9)
    for i in range(3):
        R.image(f"bolt{i}", part(f"bolt_{i}"))
    R.image("burst", part("fx_burst"))
    R.image("dot", soft_dot(256, (190, 235, 255), 1.4))
    R.bone("bolt", y=330)
    R.bone("impact", y=-40)
    R.region("dot", "impact", "dot", w=900, blend="additive", color="ffffff00")
    R.region("bolt", "bolt", "bolt0", y=-410, h=820, blend="additive", color="ffffff00")
    R.atts["bolt"]["bolt1"] = dict(R.atts["bolt"]["bolt0"], path="bolt1")
    R.atts["bolt"]["bolt2"] = dict(R.atts["bolt"]["bolt0"], path="bolt2")
    R.need["bolt1"] = R.need["bolt2"] = R.need["bolt0"]
    R.region("burst", "impact", "burst", w=420, blend="additive", color="ffffff00")
    dur = 0.8
    A = R.anim("strike", dur)
    A.attach("bolt", [(0, "bolt0"), (0.06, "bolt1"), (0.12, "bolt2"), (0.2, "bolt0"), (0.3, "bolt1")])
    A.rgba("bolt", lambda t: keys(t, [(0, 0), (0.03, 1), (0.1, 0.4), (0.14, 1), (0.26, 0.9), (0.45, 0)]))
    A.bone("bolt", "scale", lambda t: (1, seg(t, 0, 0.08, 0.2, 1)))
    A.rgba("dot", lambda t: keys(t, [(0, 0), (0.06, 0.9), (0.5, 0)]))
    A.rgba("burst", lambda t: keys(t, [(0, 0), (0.08, 1), (0.6, 0)]))
    A.bone("impact", "scale", lambda t: lerp(0.4, 1.3, out_cubic(t / dur)))
    R.write()


def build_shower():
    """Coins + laurel leaves raining over a big-win popup (screen box)."""
    R = Rig("shower", 1000, 1000, OUT, res=0.8)
    R.image("coin", part("fx_coin"))
    R.image("edge", part("fx_coin_edge"))
    R.image("leaf", part("fx_leaf"))
    R.image("glint", part("fx_sparkle"))
    rnd = np.random.default_rng(7)
    dur = 2.4
    for i in range(28):
        leaf = i % 5 == 4
        x = rnd.uniform(-480, 480)
        d0 = rnd.uniform(0, dur)
        speed = rnd.uniform(0.9, 1.3)
        R.bone(f"p{i}", x=x, y=560)
        if leaf:
            R.region(f"p{i}", f"p{i}", "leaf", w=rnd.uniform(60, 90))
        else:
            w = rnd.uniform(56, 86)
            R.region(f"p{i}", f"p{i}", "coin", w=w)
            R.atts[f"p{i}"]["edge"] = {"x": 0, "y": 0, "width": round(w * 0.3, 2), "height": round(w, 2)}
            R.need["edge"] = (max(R.need.get("edge", (0, 0))[0], w * 0.3), w)
        A = None
        R.__dict__.setdefault("_pp", []).append((i, leaf, d0, speed))
    R.bone("glint", y=200)
    R.region("glint", "glint", "glint", w=300, blend="additive", color="ffffff00")
    A = R.anim("loop", dur)
    for i, leaf, d0, speed in R._pp:
        def ph(t, d0=d0):
            return ((t + d0) % dur) / dur
        A.bone(f"p{i}", "translate", lambda t, ph=ph, sp=speed, i=i: (40 * math.sin(2 * math.pi * (ph(t) * 2 + i * 0.13)), -1150 * ph(t) * sp))
        A.bone(f"p{i}", "rotate", lambda t, ph=ph, i=i: (360 if i % 2 else -360) * ph(t) * (0.6 if leaf else 1))
        if not leaf:
            # spin: face -> squash -> edge -> squash -> face (in step with the fall)
            A.bone(f"p{i}", "scale", lambda t, ph=ph, i=i: (max(0.12, abs(math.cos(2 * math.pi * (ph(t) * 3 + i * 0.21)))), 1))
        # hide the wrap-around jump at the top of the cycle
        A.rgba(f"p{i}", lambda t, ph=ph: 1.0 if 0.02 < ph(t) < 0.98 else 0.0)
    A.rgba("glint", lambda t: 0.4 + 0.4 * flicker(t, 6))
    A.bone("glint", "rotate", lambda t: 30 * t)
    R.write()


# =============================================================== LOGO ======
def build_logo():
    logo = Image.open(IMG / "logo.webp").convert("RGBA")
    R = Rig("logo", logo.width, logo.height, OUT, res=1.0)
    R.image("logo", logo)
    R.image("shine", shine_bar(110, 700))
    R.image("sparkle", part("fx_sparkle"))
    R.image("glow", glow_of(logo, (255, 200, 80), radius=16, grow=1.1, strength=0.7))
    R.bone("body")
    R.bone("shine", "body", rot=-22)
    # the crest bolt sits at the top centre of the logo art
    a = np.asarray(logo)[:, :, 3]
    ys, xs = np.where(a[: logo.height // 4] > 128)
    tip = (float(np.median(xs)) - logo.width / 2, logo.height / 2 - float(ys.min()) - 20)
    R.bone("sparkle", "body", *tip)
    R.region("glow", "body", "glow", w=logo.width * R.images["glow"].width / logo.width, blend="additive", color="ffffff00")
    R.region("logo", "body", "logo")
    poly = [(x - logo.width / 2, logo.height / 2 - y) for x, y in hull_polygon(logo, n=28, inset=0.0)]
    R.clip("clip", "body", poly, "shine")
    R.region("shine", "shine", "shine", w=120, h=900, blend="additive", color="ffffffa0")
    R.region("sparkle", "sparkle", "sparkle", w=170, blend="additive", color="ffffff00")
    dur = 5.0
    A = R.anim("idle", dur)
    A.bone("shine", "translate", lambda t: (seg(t, 0.6, 1.8, -logo.width * 0.7, logo.width * 0.7, in_out), 0))
    A.bone("body", "scale", lambda t: 1 + 0.012 * loop_sin(t, dur))
    A.rgba("glow", lambda t: 0.25 + 0.2 * loop_sin(t, dur / 2) + 0.35 * keys(t, [(0, 0), (2.6, 0), (2.7, 1), (3.1, 0), (dur, 0)]))
    A.rgba("sparkle", lambda t: keys(t, [(0, 0), (2.6, 0), (2.68, 1), (3.0, 0.3), (3.2, 0), (dur, 0)]) * (0.6 + 0.4 * flicker(t, 30)))
    A.bone("sparkle", "scale", lambda t: keys(t, [(0, 0.3), (2.6, 0.3), (2.7, 1.2), (3.2, 0.3), (dur, 0.3)]))
    A.bone("sparkle", "rotate", lambda t: 25 * t)
    R.write()


# ================================================================= BG ======
def build_bg():
    """Clouds drift across the sky BEHIND the temple; far lightning forks in
    the gaps between them. Box = the 1920x1080 desktop scene."""
    R = Rig("bg", 1920, 1080, OUT, res=0.6)
    for i in range(6):
        R.image(f"cloud{i}", part(f"cloud_{i}"))
    for i in range(3):
        R.image(f"bolt{i}", part(f"bolt_{i}"))
    R.image("dot", soft_dot(256, (180, 225, 255), 1.6))
    dur = 24.0
    banks = [  # (cloud, y, width, speed px/s, start x, alpha)
        (0, 330, 1100, 14, -300, 0.75), (1, 160, 760, 22, 500, 0.55), (2, 470, 900, 10, 900, 0.6),
        (3, 250, 820, 18, -900, 0.6), (4, 560, 1000, 12, -100, 0.7), (5, 90, 600, 26, 200, 0.5),
    ]
    span = 1920 + 1200
    for k, (ci, y, w, v, x0, al) in enumerate(banks):
        R.bone(f"c{k}", x=0, y=540 - y)
        R.region(f"c{k}", f"c{k}", f"cloud{ci}", w=w, color=f"ffffff{int(al * 255):02x}")
    strikes = [(3.2, -620, 0), (3.5, -560, 1), (9.8, 520, 2), (15.1, -200, 1), (19.7, 700, 0), (20.0, 760, 2)]
    for k, (_, x, bi) in enumerate(strikes):
        R.bone(f"b{k}", x=x, y=200, rot=(-8 if k % 2 else 6))
        R.region(f"b{k}", f"b{k}", f"bolt{bi}", h=700, blend="additive", color="ffffff00")
        R.bone(f"f{k}", x=x, y=360)
        R.region(f"f{k}", f"f{k}", "dot", w=1300, blend="additive", color="ffffff00")
    # clouds must loop seamlessly: speed chosen so span/speed divides dur
    for mode, tint_rgb, freq in (("idle", (1, 1, 1), 1), ("fs", (0.85, 0.6, 1.0), 2)):
        A = R.anim(mode, dur)
        for k, (ci, y, w, v, x0, al) in enumerate(banks):
            laps = max(1, round(v * dur / span))
            A.bone(f"c{k}", "translate", lambda t, x0=x0, laps=laps: (((x0 + span * laps * t / dur + span / 2) % span) - span / 2, 0))
            A.rgba(f"c{k}", lambda t, al=al, k=k: (*tint_rgb, al * (0.85 + 0.15 * loop_sin(t, dur / 2, k * 0.2))))
        for k, (t0, x, bi) in enumerate(strikes):
            def env(t, t0=t0):
                v = 0.0
                for rep in range(freq):
                    tt = (t - t0 - rep * dur / freq) % dur
                    v = max(v, keys(tt, [(0, 0), (0.04, 1), (0.1, 0.25), (0.16, 0.95), (0.4, 0), (dur, 0)]))
                return v
            A.rgba(f"b{k}", lambda t, env=env: (*tint_rgb, env(t)))
            A.rgba(f"f{k}", lambda t, env=env: (*tint_rgb, 0.45 * env(t)))
    R.write()


def render_zeus_static():
    """PNG fallback of the setup pose (no WebGL) — composited like the rig."""
    data = json.load(open(os.path.join(OUT, "zeus/animation.json")))
    # simplest faithful fallback: rasterise via the parts with the same offsets
    # is involved; instead the full single-image Zeus is used as the fallback.
    src = ROOT / "front/img/olympus-thunder/src/zeus_fullbody.webp"
    full = Image.open(src).convert("RGBA") if src.exists() else None
    if full is not None:
        from olympus_thunder_build import clean_alpha, trim
        full = trim(clean_alpha(full))
        full.thumbnail((760, 1140), Image.LANCZOS)
        full.save(IMG / "zeus.webp", "WEBP", quality=90, method=6)
    return data


BUILDERS = {
    "zeus": build_zeus, "orb": build_orb, "symbols": build_symbols, "fx": build_fx, "strike": build_strike,
    "shower": build_shower, "logo": build_logo, "bg": build_bg,
}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(BUILDERS):
        BUILDERS[name]()
    if not sys.argv[1:] or "zeus" in sys.argv[1:]:
        render_zeus_static()
