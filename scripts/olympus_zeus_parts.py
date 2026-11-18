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


def defringe(a):
    """semi-transparent edge pixels take the colour of the opaque pixels next to them (no light/dark halo)"""
    al = a[..., 3] / 255.0
    solid = (al > 0.85).astype(float)
    num = np.stack([gaussian_filter(a[..., c] * solid, 2.0) for c in range(3)], -1)
    den = gaussian_filter(solid, 2.0)[..., None]
    fill = np.where(den > 1e-3, num / np.maximum(den, 1e-3), a[..., :3])
    edge = ((al > 0) & (al <= 0.85))[..., None]
    out = a.copy()
    out[..., :3] = np.where(edge, fill, a[..., :3])
    return out


def save(name, a, clean=True):
    if clean:
        a = defringe(a)
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
cloak = ((r0 < 95) & (b0 > 110) & (g0 < 130)) | ((b0 - r0 > 40) & (NA[..., :3].mean(-1) < 150))   # incl. dark navy folds
gold = (r0 > 170) & (g0 > 120) & (b0 < 95) & (np.arange(H)[:, None] > 430)
m &= ~(cloak | gold)
m = binary_opening(m, iterations=2)
lab_m, _ = label(m)
sz_m = np.bincount(lab_m.ravel()); sz_m[0] = 0
m = lab_m == sz_m.argmax()                       # one piece: no loose crumbs along the beard / collar
m = binary_fill_holes(binary_closing(m, iterations=3))
# neck skin between the beard strands belongs to the body's neck, not to the moving head
sk0, sk1, sk2 = NA[..., 0], NA[..., 1], NA[..., 2]
neck_skin = (sk0 > 120) & (sk0 > sk1 + 10) & (sk1 > sk2) & (sk0 - sk2 > 45) & (np.arange(H)[:, None] > 470)
neck_skin &= ~(poly(POLY['face'], 0) > 0.5)
m &= ~binary_opening(neck_skin, iterations=1)
lab_m2, _ = label(m)
sz_m2 = np.bincount(lab_m2.ravel()); sz_m2[0] = 0
m = lab_m2 == sz_m2.argmax()
hm = gaussian_filter(m.astype(float), 1.2)
# outer hair edge: where nothing of the body is behind the head, keep the painting's own soft alpha
from scipy.ndimage import maximum_filter
zone_h = poly(POLY['head_zone'], 0) > 0.5
free = (HL[..., 3] < 20) & zone_h & (maximum_filter(m, 25))
hm = np.where(free, 1.0, hm)
head = layer(NA, hm)
save('head', head)
# face variants: the head with the face area replaced (soft edge)
for nm, src, zone in (('head_blink', BL, 'eyes'), ('head_shout', SH, 'face')):
    fm = poly(POLY[zone], 10) * hm
    v = head.copy()
    v[..., :3] = head[..., :3] * (1 - fm[..., None]) + src[..., :3] * fm[..., None]
    save(nm, v)

# ---- straps over the right shoulder, cut from the body: drawn ABOVE the upper arm so its root hides under them ----
STRAP = [(215, 470), (505, 535), (548, 598), (510, 660), (452, 780), (392, 905), (330, 895), (392, 760), (440, 640),
         (380, 592), (225, 565)]
h0, h1, h2 = HL[..., 0], HL[..., 1], HL[..., 2]
sgm = (h0 > 120) & (h1 > 80) & (h2 < 140) & (h0 - h2 > 45) & (poly(STRAP, 0) > 0.5)
sgm = binary_closing(binary_opening(sgm, iterations=1), iterations=3)
from scipy.ndimage import binary_dilation as _bd
sgm = _bd(sgm, iterations=2) & (poly(STRAP, 0) > 0.5) & (HL[..., 3] > 128)     # keep the strap's dark rim
lab_s, _ = label(sgm)
sz_s = np.bincount(lab_s.ravel()); sz_s[0] = 0
sgm = np.isin(lab_s, np.where(sz_s > 800)[0])
# the patch is taken from the ORIGINAL (bolt-free) image: its strap sits exactly on the original arm
n0_, n1_, n2_ = NB[..., 0], NB[..., 1], NB[..., 2]
ngold = (n0_ > 15) & (n2_ < 0.18 * n0_ + 3) & (poly(STRAP, 0) > 0.5)   # gold: b/r < .12, skin: b/r > .29
ngold = _bd(binary_closing(binary_opening(ngold, iterations=1), iterations=1), iterations=1) & (NB[..., 3] > 128)
lab_n, _ = label(ngold)
sz_n = np.bincount(lab_n.ravel()); sz_n[0] = 0
ngold = np.isin(lab_n, np.where(sz_n > 800)[0])
sgm = ngold
save('strap', layer(NB, gaussian_filter(ngold.astype(float), 1.0)))

save('l_fore', layer(NB, poly(POLY['l_fore'])))
# ---- RIGHT ARM v6: a cut-out puppet, one rigid piece per joint, clothing on top of the joints ----
#   r_upper  shoulder -> elbow (skin only; under the bracer the hidden top of the arm is painted in)
#   r_bracer the gold bracer = forearm (pivot at the elbow); its bottom rim hides the elbow joint
#   r_fist   fist + wrist that continues INTO the bracer (drawn under it; the bracer's top rim hides the wrist)
#   strap    shoulder + diagonal straps (on the torso) drawn over the upper arm's root
#   body     under the whole arm: the ARMLESS edit (cloak / tunic), so a moving arm uncovers clothing, not a hole
import cv2
from scipy.ndimage import binary_dilation as _bd2, distance_transform_edt
yy, xx = np.mgrid[0:H, 0:W]


def diffuse_fill(rgb, known, sigmas=(2, 5, 10, 20, 40, 80)):
    """unknown pixels <- smooth continuation of the known colours (multi-scale normalised convolution)"""
    out = rgb.copy()
    k = known.astype(float)
    filled = known.copy()
    for s in sigmas:
        num = np.stack([gaussian_filter(rgb[..., c] * k, s) for c in range(3)], -1)
        den = gaussian_filter(k, s)
        take = (~filled) & (den > 0.03)
        est = num / np.maximum(den, 1e-6)[..., None]
        out[take] = est[take]
        filled |= take
    return out


def biggest(m):
    lab_, _ = label(m)
    sz = np.bincount(lab_.ravel()); sz[0] = 0
    return lab_ == sz.argmax()


r_, g_, b_ = NB[..., 0], NB[..., 1], NB[..., 2]
gold_px = (r_ > 15) & (b_ < 0.18 * r_ + 3) & (NB[..., 3] > 100)
skin_px = (r_ > 40) & (r_ > g_ + 10) & (g_ > b_) & (b_ >= 0.24 * r_) & (NB[..., 3] > 200)

# -- bracer
BRACER = [(132, 350), (165, 343), (205, 356), (234, 395), (238, 440), (232, 520), (234, 600), (206, 626), (140, 643),
          (80, 641), (34, 624), (10, 596), (12, 555), (45, 490), (90, 420), (118, 375)]
bz = poly(BRACER, 0) > 0.5
br = binary_closing(gold_px & bz, iterations=3)
br = binary_fill_holes(br) & bz
br &= ~(binary_opening(skin_px, iterations=2) & (yy < 455))          # the top opening shows the wrist (fist layer)
br = binary_opening(biggest(br), iterations=1)
bracer = NB.copy()
bracer[..., 3] = gaussian_filter(br.astype(float), 0.8) * 255
save('r_bracer', bracer)

# -- upper arm
UP = [(255, 545), (300, 528), (380, 538), (455, 560), (484, 600), (462, 660), (430, 715), (380, 760), (330, 800),
      (300, 812), (250, 808), (150, 798), (40, 778), (0, 728), (0, 560), (120, 530), (230, 525)]
FILL = [(268, 547), (215, 556), (150, 568), (90, 583), (45, 600), (24, 624), (17, 660), (24, 700), (120, 700), (300, 660), (300, 540)]
upz = poly(UP, 0) > 0.5
under = _bd2(br, iterations=2) & upz
rim = _bd2(br, iterations=7) & (NB[..., :3].mean(-1) < 95) & upz          # bracer's dark outline / contact shadow on the skin                                   # hidden behind the bracer
fillz = (poly(FILL, 0) > 0.5) & under
blue_px = (b_ > r_ + 10) & (b_ > 90)                                  # cloak below the arm stays on the body
vis = (NB[..., 3] > 8) & upz & ~under & ~blue_px
known = vis & ~_bd2(gold_px, iterations=3) & (NB[..., 3] > 200) & ~rim
rgb = diffuse_fill(NB[..., :3], known)
hole_ = ~known
sm = np.stack([gaussian_filter(rgb[..., c], 7) for c in range(3)], -1)     # no ring steps from the fill scales
fb = np.clip(distance_transform_edt(hole_) / 6.0, 0, 1)[..., None]
rgb = np.where(known[..., None], NB[..., :3], rgb * (1 - fb) + sm * fb)
sil = vis | fillz
# painted part: round the limb — darker toward its outline, as the visible biceps is
d = distance_transform_edt(binary_fill_holes(sil))
shade = 0.74 + 0.26 * np.clip(d / 30.0, 0, 1)
rgb = np.where(fillz[..., None], rgb * shade[..., None], rgb)
alpha = np.where(vis, NB[..., 3] / 255.0, 0.0)
alpha = np.maximum(alpha, gaussian_filter(fillz.astype(float), 1.0) * (binary_fill_holes(sil)))
alpha *= gaussian_filter(biggest(alpha > 0.5).astype(float), 0.7) > 0.02   # no loose bracer flecks
# root: fades out over ~60 px toward the shoulder pivot — the body keeps the original skin there, so a few
# degrees of shoulder rotation slide skin over the same skin (no cut line on the chest)
PIV = np.array([405.0, 625.0]); AX = np.array([-0.985, 0.17])
u = (xx - PIV[0]) * AX[0] + (yy - PIV[1]) * AX[1]
root_w = np.clip((u - 10) / 60.0, 0, 1)
root_w = root_w * root_w * (3 - 2 * root_w)
alpha_full = alpha.copy()
alpha = alpha * root_w
# the root ends 8 px UNDER the shoulder strap's lower edge (the strap layer covers the cut)
strap_top = ngold & (yy < 640)
low = np.where(strap_top, yy, -1).max(0)
alpha = np.where((yy < low[None, :] - 8) & (low[None, :] > 0) & (xx > 240), 0, alpha)
up_img = NB.copy()
up_img[..., :3] = rgb
up_img[..., 3] = np.clip(alpha, 0, 1) * 255
save('r_upper', up_img)

# -- fist (+ wrist under the bracer)
FIST = [(138, 335), (160, 282), (200, 240), (260, 220), (334, 243), (372, 295), (370, 352), (334, 400), (272, 432),
        (234, 447), (205, 430), (170, 398)]
WRIST = [(136, 340), (210, 380), (234, 418), (228, 495), (150, 478), (118, 425)]
fz = poly(FIST, 0) > 0.5
from scipy.ndimage import binary_erosion as _be
wz = (poly(WRIST, 0) > 0.5) & _be(bz, iterations=7)          # stays inside the bracer
fvis = fz & (NB[..., 3] > 8) & ~br
fknown = fvis & ~_bd2(gold_px, iterations=2) & (NB[..., 3] > 200)
frgb = diffuse_fill(NB[..., :3], fknown)
frgb = np.where(fknown[..., None], NB[..., :3], frgb)
fal = np.where(fvis, NB[..., 3] / 255.0, 0.0)
fal = np.maximum(fal, gaussian_filter((wz | (fz & br)).astype(float), 1.0))
fist = NB.copy()
fist[..., :3] = frgb
fist[..., 3] = np.clip(fal, 0, 1) * 255
save('r_fist', fist)

# -- body: the original with head swap (as before) but the whole right arm replaced by the armless edit
body = NB.copy()
R = _bd2(hm > 0.05, iterations=6)
hr_, hg_, hb_ = HL[..., 0], HL[..., 1], HL[..., 2]
sat = np.max(HL[..., :3], -1) - np.min(HL[..., :3], -1)
is_skin = (hr_ > 110) & (hr_ > hg_ + 10) & (hg_ > hb_) & (hr_ - hb_ > 40)
is_cloak = (hb_ - hr_ > 40) & (sat > 60)
is_gold = (hr_ > 130) & (hg_ > 90) & (hb_ < 130) & (hr_ - hb_ > 55)
is_white = (np.minimum(np.minimum(hr_, hg_), hb_) > 200)
smudge = R & ~(is_skin | is_cloak | is_gold | is_white) & (HL[..., 3] > 100)
hl_rgb = cv2.inpaint(np.ascontiguousarray(np.clip(HL[..., :3], 0, 255).astype(np.uint8)), np.uint8(_bd2(smudge, iterations=2)) * 255, 8, cv2.INPAINT_TELEA)
HLc = HL.copy(); HLc[..., :3] = hl_rgb
ring = _bd2(R, iterations=40) & ~R & (poly(POLY['head_zone'], 0) > 0.5)
nlum = NB[..., :3].mean(-1)
nsat = np.max(NB[..., :3], -1) - np.min(NB[..., :3], -1)
strands = ring & (nsat < 55) & (nlum > 140) & (NB[..., 3] > 100)
nb_rgb = cv2.inpaint(np.ascontiguousarray(np.clip(NB[..., :3], 0, 255).astype(np.uint8)), np.uint8(_bd2(strands, iterations=2)) * 255, 8, cv2.INPAINT_TELEA)
body[..., :3] = nb_rgb
hmask = gaussian_filter(R.astype(float), 1.5)
body[..., :3] = body[..., :3] * (1 - hmask[..., None]) + HLc[..., :3] * hmask[..., None]
body[..., 3] = body[..., 3] * (1 - hmask) + HLc[..., 3] * hmask
# armless edit, its electric-cyan rim light toned down to the cloak's royal blue
NAc = NA.copy()
n0, n1, n2 = NA[..., 0], NA[..., 1], NA[..., 2]
cy = np.clip((n1 - n0 - 40) / 80.0, 0, 1) * np.clip((n2 - 120) / 80.0, 0, 1)
blue = np.array([28, 58, 170], float) * (0.55 + 0.45 * np.clip(NA[..., :3].mean(-1) / 200.0, 0, 1))[..., None]
NAc[..., :3] = NA[..., :3] * (1 - cy[..., None] * 0.85) + blue * cy[..., None] * 0.85
armz = br | (fist[..., 3] > 10) | (poly(BRACER, 0) > 0.5) | (poly(FIST, 0) > 0.5)
armz = _bd2(armz, iterations=10) & ~R
am = np.maximum(gaussian_filter(armz.astype(float), 2.0), np.clip(alpha_full * root_w / 0.97, 0, 1) * (gaussian_filter(_bd2(alpha_full > 0.02, iterations=6).astype(float), 2.0)))
am = np.where(upz & (root_w > 0.99), np.maximum(am, gaussian_filter(_bd2(alpha_full > 0.02, iterations=6).astype(float), 2.0)), am)
body[..., :3] = body[..., :3] * (1 - am[..., None]) + NAc[..., :3] * am[..., None]
body[..., 3] = body[..., 3] * (1 - am) + NAc[..., 3] * am
save('body', body)
# fingers in FRONT of the plasma ball (the palm stays behind it)
FING = [(888, 965), (893, 880), (960, 848), (1060, 810), (1150, 798), (1180, 850), (1172, 930), (1100, 938), (1020, 944), (950, 955)]
k0, k1, k2 = NB[..., 0], NB[..., 1], NB[..., 2]
skin = (k0 > 110) & (k0 > k1 + 8) & (k1 > k2) & (k0 - k2 > 35)          # fingers only, not the cloak behind them
skin = binary_closing(binary_opening(skin, iterations=1), iterations=2)
HAND = [(880, 1000), (888, 880), (960, 845), (1060, 808), (1150, 795), (1182, 850), (1172, 980), (1150, 1050), (1060, 1075), (960, 1070)]
fa = poly(POLY['l_fore']) * poly(HAND, 3) * gaussian_filter(skin.astype(float), 1.0) * (NB[..., 3] / 255)
solid_f = binary_opening(fa > 0.35, iterations=3)                   # no 1-2 px threads along the polygon edge
lab_f, _ = label(solid_f)
sz_f = np.bincount(lab_f.ravel()); sz_f[0] = 0
solid_f = np.isin(lab_f, np.where(sz_f > 400)[0])
save('l_fingers', layer(NB, gaussian_filter(solid_f.astype(float), 1.0)))

# ---- effects: original minus bolt-free, electric colours only ----
diff = np.clip((np.abs(pre(H0) - pre(NB)).max(-1) - 18) / 70, 0, 1)
r_, g_, b_ = H0[..., 0], H0[..., 1], H0[..., 2]
elec = np.clip((b_ - r_ - 10) / 50, 0, 1)
core = np.clip((np.minimum(np.minimum(r_, g_), b_) - 200) / 40, 0, 1) * (b_ >= r_ - 6)
gate = (H0[..., :3].sum(-1) > 300) * np.maximum(elec, core)
# clean bolt: the original's white-hot core (smoothed) + painted cyan glow
coremask = (np.minimum(np.minimum(r_, g_), b_) > 205) & (H0[..., 3] > 200) & (poly(POLY['bolt_zone'], 0) > 0.5)
coremask = binary_opening(binary_closing(coremask, iterations=2), iterations=1)
lab_, n_ = label(coremask)
sz = np.bincount(lab_.ravel()); sz[0] = 0
coremask = np.isin(lab_, np.where(sz > 60)[0])
# the top half (above the fist) is redrawn as a readable zig-zag bolt; the spike under the fist stays
B0, T0 = np.array([300.0, 262.0]), np.array([668.0, 22.0])          # base (at the fist) -> tip
ax = T0 - B0; L = np.hypot(*ax); ax /= L; nv = np.array([-ax[1], ax[0]])
ZZ = [(0.00, 0.075), (0.50, 0.125), (0.43, 0.025), (1.00, 0.0), (0.52, -0.115), (0.59, -0.012), (0.00, -0.07)]
bolt_img = Image.new('L', (W * 4, H * 4), 0)
ImageDraw.Draw(bolt_img).polygon([tuple((B0 + ax * u * L + nv * v * L) * 4) for u, v in ZZ], fill=255)
zz = np.array(bolt_img.resize((W, H), Image.LANCZOS)) / 255.0
upper = (np.arange(H)[:, None] < 300) | ((np.arange(W)[None, :] > 330) & (np.arange(H)[:, None] < 360))
low_mask = coremask & ~upper           # the original spike under the fist (drawn over the bracer, under the fist)


def bolt_layer(cm, soft=None):
    cs = np.clip((gaussian_filter(cm.astype(float), 1.0) - 0.25) / 0.5, 0, 1)
    if soft is not None:
        cs = np.maximum(cs, soft * (soft > 0.02))
    g1 = np.clip(gaussian_filter(cm.astype(float), 7) * 2.2, 0, 1)
    g2 = np.clip(gaussian_filter(cm.astype(float), 20) * 2.0, 0, 1) * 0.55
    out = np.zeros_like(H0)
    a_out = np.maximum(cs, np.maximum(g1 * 0.85, g2))
    mix = np.where(a_out > 0, cs / np.maximum(a_out, 1e-3), 0)[..., None]
    out[..., :3] = np.array([110, 215, 255], float) * (1 - mix) + np.array([245, 253, 255], float) * mix
    out[..., 3] = a_out * 255
    return out


save('bolt', bolt_layer(zz > 0.5, zz), clean=False)       # zig-zag from the fist up (behind the fist)
save('bolt_low', bolt_layer(low_mask), clean=False)
for nm, zone in (('orb', 'orb_zone'),):
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
order = ['body', 'l_fore', 'orb', 'head', 'r_upper', 'strap', 'bolt', 'r_bracer', 'bolt_low', 'r_fist']
comp = Image.new('RGBA', (W, H), (60, 60, 68, 255))
for nm in order:
    comp.alpha_composite(Image.open(os.path.join(OUT, f'p_{nm}.png')))
comp = comp.convert('RGB')
comp.thumbnail((700, 800))
comp.save(os.path.join(OUT, 'check.jpg'), quality=88)
print('ok', OUT)
