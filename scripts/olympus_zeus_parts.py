"""Olympus Thunder · Tides 2 — cut the pseudo-3D Zeus into clean rig layers.

    ~/.venvs/art/bin/python scripts/olympus_zeus_parts.py [RAW_S_DIR] [OUT_DIR]

Every source is a ChatGPT EDIT of the same hero frame (same 1199x1312 canvas; aligned here by a small
integer shift found on a shared region), so the layers re-assemble without seams:
  hero.png          original (arms, bolt, energy ball)
  zeus_nobolt.png   same, lightning erased            -> arms / hands (clean skin, no glow)
  zeus_noarms2.png  same, arms erased                 -> HEAD (hair/beard never covered by an arm)
  zeus_headless.png armless AND headless              -> BODY (neck stump, clasp, straps, cloak)
  zeus_upperarm2.png right forearm erased (optional)  -> clean upper arm with a rounded elbow
  zeus_blink.png / zeus_shout.png  face edits         -> head_blink / head_shout (face area only)
Effects (bolt, energy ball) = original minus nobolt, gated to electric colours.
Writes OUT_DIR/p_<layer>.png (+ check.jpg overlay).
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter, binary_opening, binary_closing, binary_fill_holes, label

RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/ot2-work/raw/S')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser('~/ot2-work/rig')
os.makedirs(OUT, exist_ok=True)


def load(n):
    return np.array(Image.open(os.path.join(RAW, f'{n}.png')).convert('RGBA')).astype(float)


def shift(a, dx, dy):
    return np.roll(np.roll(a, dy, 0), dx, 1)


def align(ref, mov, region, r=6):
    ys, xs = region
    pr = ref[ys, xs, :3] * ref[ys, xs, 3:] / 255
    best = min(((np.abs(pr - (lambda m: m[ys, xs, :3] * m[ys, xs, 3:] / 255)(shift(mov, dx, dy))).mean(), dx, dy)
                for dx, dy in itertools.product(range(-r, r + 1), range(-r, r + 1))))
    print('  align', best)
    return shift(mov, best[1], best[2])


def matte_white(a):
    """ChatGPT sometimes returns a white background instead of alpha: flood the near-white border."""
    if a[..., 3].min() < 250:
        return a
    white = (a[..., :3].min(-1) > 238)
    lab, _ = label(white)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    a = a.copy()
    a[..., 3] = np.where(bg, 0, 255)
    a[..., 3] = gaussian_filter(a[..., 3], 0.8)
    return a


H0 = load('hero')
H, W = H0.shape[:2]
NB = align(H0, load('zeus_nobolt'), (slice(250, 480), slice(560, 820)))
NA = align(H0, load('zeus_noarms2'), (slice(250, 480), slice(560, 820)))
HL = align(NA, load('zeus_headless'), (slice(720, 1000), slice(430, 760)))
BL = align(NB, matte_white(load('zeus_blink')), (slice(150, 250), slice(560, 800)))
SH = align(NB, matte_white(load('zeus_shout')), (slice(120, 260), slice(480, 900)))
UA = None
if os.path.exists(os.path.join(RAW, 'zeus_upperarm2.png')):
    UA = align(NB, matte_white(load('zeus_upperarm2')), (slice(700, 1000), slice(430, 760)))


def poly(pts, feather=1.5):
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    if feather:
        m = m.filter(ImageFilter.GaussianBlur(feather))
    return np.array(m) / 255.0


def layer(src, m):
    out = src.copy()
    out[..., 3] = src[..., 3] * np.clip(m, 0, 1)
    return out


def save(name, a):
    Image.fromarray(np.uint8(np.clip(a, 0, 255))).save(os.path.join(OUT, f'p_{name}.png'))


POLY = {
    'r_upper': [(250, 550), (170, 570), (60, 600), (22, 650), (28, 720), (80, 775), (170, 795), (300, 800), (335, 800),
                (375, 760), (400, 680), (412, 600), (395, 565), (330, 555)],
    'r_fore': [(15, 660), (8, 560), (35, 470), (100, 375), (170, 300), (200, 240), (260, 222), (332, 245), (368, 295),
               (366, 352), (330, 397), (270, 428), (228, 472), (230, 560), (208, 628), (140, 662), (70, 680)],
    'bolt_zone': [(0, 720), (0, 250), (250, 30), (720, 0), (720, 70), (560, 200), (450, 235), (385, 300), (300, 420),
                  (245, 520), (130, 720)],
    'l_fore': [(855, 1150), (866, 1030), (888, 955), (905, 880), (960, 850), (1060, 812), (1150, 800), (1178, 850),
               (1168, 980), (1160, 1100), (1120, 1152), (990, 1162)],
    'orb_zone': [(800, 960), (790, 760), (900, 640), (1000, 600), (1150, 610), (1150, 760), (1120, 820), (1040, 830),
                 (960, 860), (905, 880), (890, 955)],
    # face area that blink / shout may replace (eyes, brows, nose, mouth inside the beard)
    'face': [(600, 250), (700, 225), (800, 240), (830, 300), (820, 400), (790, 470), (720, 500), (650, 480),
             (610, 420), (590, 330)],
    'head_zone': [(430, 560), (330, 480), (318, 330), (420, 225), (540, 165), (680, 150), (810, 185), (890, 280),
                  (945, 420), (955, 520), (905, 565), (860, 600), (800, 645), (700, 660), (620, 620), (560, 575), (500, 565)],
    'eyes': [(610, 275), (700, 255), (800, 268), (805, 330), (700, 345), (615, 335)],
}

# ---- body: armless + headless ----
save('body', HL)

# ---- head: where the armless image has the head and the headless one does not ----
pre = lambda a: a[..., :3] * a[..., 3:] / 255  # noqa: E731
d = np.abs(pre(NA) - pre(HL)).max(-1)
m = (d > 30) & (NA[..., 3] > 30)
m &= poly(POLY['head_zone'], 0) > 0.5           # only head, hair and beard (the shoulders were redrawn too)
m = binary_closing(binary_opening(m, iterations=2), iterations=8)
m = binary_fill_holes(m)
lab, n = label(m)
sizes = np.bincount(lab.ravel())
sizes[0] = 0
m = lab == sizes.argmax()
# drop cloak blue and strap gold that the edit also repainted around the shoulders (hair/beard are light)
r0, g0, b0 = NA[..., 0], NA[..., 1], NA[..., 2]
cloak = (r0 < 95) & (b0 > 110) & (g0 < 130)
gold = (r0 > 170) & (g0 > 120) & (b0 < 95) & (np.arange(H)[:, None] > 430)
m &= ~(cloak | gold)
m = binary_opening(m, iterations=1)
hm = gaussian_filter(m.astype(float), 1.2)
head = layer(NA, hm)
save('head', head)
# face variants: the head with the face area replaced (soft edge)
for nm, src, zone in (('head_blink', BL, 'eyes'), ('head_shout', SH, 'face')):
    fm = poly(POLY[zone], 10) * hm
    v = head.copy()
    v[..., :3] = head[..., :3] * (1 - fm[..., None]) + src[..., :3] * fm[..., None]
    save(nm, v)

# ---- arms from the bolt-free edit ----
if UA is not None:
    # clean upper arm: what the forearm-less edit keeps inside the upper-arm zone, grown to its rounded elbow
    u0, u1, u2 = UA[..., 0], UA[..., 1], UA[..., 2]
    tunic = (np.minimum(np.minimum(u0, u1), u2) > 185) & (np.max(UA[..., :3], -1) - np.min(UA[..., :3], -1) < 45)
    blue = (u0 < 95) & (u2 > 110)
    keep = binary_opening(~(tunic | blue), iterations=2)
    save('r_upper', layer(UA, poly(POLY['r_upper']) * gaussian_filter(keep.astype(float), 1.0)))
else:
    save('r_upper', layer(NB, poly(POLY['r_upper'])))
save('r_fore', layer(NB, poly(POLY['r_fore'])))
save('l_fore', layer(NB, poly(POLY['l_fore'])))

# ---- effects: original minus bolt-free, electric colours only ----
diff = np.clip((np.abs(pre(H0) - pre(NB)).max(-1) - 18) / 70, 0, 1)
r_, g_, b_ = H0[..., 0], H0[..., 1], H0[..., 2]
elec = np.clip((b_ - r_ - 10) / 50, 0, 1)
core = np.clip((np.minimum(np.minimum(r_, g_), b_) - 200) / 40, 0, 1) * (b_ >= r_ - 6)
gate = (H0[..., :3].sum(-1) > 300) * np.maximum(elec, core)
for nm, zone in (('bolt', 'bolt_zone'), ('orb', 'orb_zone')):
    g2 = gate.copy()
    if nm == 'bolt':   # over the fist keep only the white-hot core, not the cyan rim light on the skin
        from scipy.ndimage import maximum_filter
        f = gaussian_filter(maximum_filter(poly(POLY['r_fore'], 0), 25), 4)
        g2 = gate * (1 - f) + core * f
    al = gaussian_filter(diff * g2, 1.6) * poly(POLY[zone], 6) * (H0[..., 3] / 255)
    al *= np.clip(gaussian_filter((g2 > 0.3).astype(float), 1.0) * 1.5, 0, 1)   # no alpha bleeding onto dark skin edges
    fx = H0.copy()
    fx[..., 3] = np.clip(al, 0, 1) * 255
    save(nm, fx)

# ---- check: re-assemble in rig order over grey ----
order = ['body', 'l_fore', 'orb', 'head', 'r_upper', 'r_fore', 'bolt']
comp = Image.new('RGBA', (W, H), (60, 60, 68, 255))
for nm in order:
    comp.alpha_composite(Image.open(os.path.join(OUT, f'p_{nm}.png')))
comp = comp.convert('RGB')
comp.thumbnail((700, 800))
comp.save(os.path.join(OUT, 'check.jpg'), quality=88)
print('ok', OUT)
