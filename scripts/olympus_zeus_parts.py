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
ngold = (n0_ > 120) & (n1_ > 80) & (n2_ < 140) & (n0_ - n2_ > 45) & (poly(STRAP, 0) > 0.5)
ngold = _bd(binary_closing(binary_opening(ngold, iterations=1), iterations=3), iterations=3) & (NB[..., 3] > 128)
lab_n, _ = label(ngold)
sz_n = np.bincount(lab_n.ravel()); sz_n[0] = 0
ngold = np.isin(lab_n, np.where(sz_n > 800)[0])
sgm = ngold
save('strap', layer(NB, gaussian_filter(ngold.astype(float), 1.0)))

# ---- arms from the bolt-free edit ----
if UA is not None:
    # clean upper arm: what the forearm-less edit keeps inside the upper-arm zone, grown to its rounded elbow
    # upper arm = the bolt-free original inside a polygon whose top runs UNDER the shoulder strap.
    # Where the forearm polygon overlaps it (the bracer's lower end) the pixels are repainted as skin
    # from the biceps around it, inside a rounded elbow cap — no ghost bracer when the forearm turns.
    import cv2
    # the inner end now runs UNDER the shoulder strap and the diagonal strap (drawn over it as 'strap')
    up = [(205, 578), (140, 592), (60, 612), (22, 650), (28, 720), (80, 775), (170, 795), (300, 805), (360, 822),
          (398, 792), (432, 700), (470, 622), (492, 578), (420, 552), (330, 556)]
    zone = poly(up, 1.2)
    over = (poly(POLY['r_fore'], 0) > 0.5) & (zone > 0.5)
    cap = Image.new('L', (W, H), 0)
    ImageDraw.Draw(cap).ellipse((105 - 82, 612, 105 + 82, 708), fill=255)
    cap = np.array(cap) > 0
    solid = (NB[..., 3] > 200) & (zone > 0.5) & ~over          # trusted biceps skin
    base = NB[..., :3].copy()
    num = np.stack([gaussian_filter(base[..., c] * solid, 6) for c in range(3)], -1)
    den = gaussian_filter(solid.astype(float), 6)[..., None]
    base = np.where(solid[..., None], base, num / np.maximum(den, 1e-3))  # no black from transparent pixels
    hole = over | (cap & ~solid)
    rgb = cv2.inpaint(np.ascontiguousarray(np.clip(base, 0, 255).astype(np.uint8)), np.uint8(hole) * 255, 15, cv2.INPAINT_TELEA)
    arm = NB.copy()
    arm[..., :3] = np.where(hole[..., None], rgb, NB[..., :3])
    alpha = np.maximum((NB[..., 3] / 255) * ~over, cap.astype(float))
    alpha = np.where(over & ~cap, 0, alpha)
    # gold of the straps that lay on the arm -> skin (the strap layer covers this band anyway)
    a0, a1, a2 = arm[..., 0], arm[..., 1], arm[..., 2]
    sgold = (a0 > 130) & (a1 > 85) & (a2 < 130) & (a0 - a2 > 55) & (zone > 0.3) & ~over
    sgold = binary_closing(sgold, iterations=3)
    from scipy.ndimage import binary_dilation
    white = (np.minimum(np.minimum(a0, a1), a2) > 165) & (np.max(arm[..., :3], -1) - np.min(arm[..., :3], -1) < 50) & (zone > 0.3)
    sg = binary_dilation(sgold | white, iterations=3) & (zone > 0.3)
    rgb2 = cv2.inpaint(np.ascontiguousarray(np.clip(arm[..., :3], 0, 255).astype(np.uint8)), np.uint8(sg) * 255, 18, cv2.INPAINT_TELEA)
    arm[..., :3] = np.where(sg[..., None], rgb2, arm[..., :3])
    alpha = np.where(sg, np.maximum(alpha, (zone > 0.5).astype(float)), alpha)
    # the arm's top edge ends 8 px UNDER the strap's lower edge (no repainted band peeking out above it)
    strap_m = sgm & (np.arange(H)[:, None] < 640)
    ys_idx = np.arange(H)[:, None].repeat(W, 1)
    low = np.where(strap_m, ys_idx, -1).max(0)                         # strap bottom per column (-1 = none)
    above = (ys_idx < (low[None, :] - 8)) & (low[None, :] > 0)
    alpha = np.where(above & (np.arange(W)[None, :] > 200), 0, alpha)
    dark = (arm[..., :3].sum(-1) < 200) & (np.arange(H)[:, None] < 660) & (np.arange(W)[None, :] < 230)  # bracer's shadow rim above the elbow cap
    alpha = np.where(dark, 0, alpha)
    arm[..., 3] = gaussian_filter(alpha, 1.0) * 255
    save('r_upper', layer(arm, zone))
else:
    save('r_upper', layer(NB, poly(POLY['r_upper'])))
save('r_fore', layer(NB, poly(POLY['r_fore'])))
save('l_fore', layer(NB, poly(POLY['l_fore'])))

# ---- BODY v3: the ORIGINAL (bolt-free) picture with its real shoulders and upper arm, so the arm's root
# has no seam — the rig bends it as a mesh. Removed from it: the head (-> headless edit underneath the
# separate head layer) and the right forearm/fist (separate layer); the bracer's lower end is replaced by
# the skin elbow cap made above.
body = NB.copy()
from scipy.ndimage import binary_dilation as _bd2
import cv2 as _cv
# under the head layer only (grown 6 px): the headless edit's neck/collar, with its grey smudges repainted
R = _bd2(hm > 0.05, iterations=6)
lum = HL[..., :3].mean(-1)
sat = np.max(HL[..., :3], -1) - np.min(HL[..., :3], -1)
smudge = R & (sat < 40) & (lum > 50) & (lum < 215) & (HL[..., 3] > 100)
hl_rgb = _cv.inpaint(np.ascontiguousarray(np.clip(HL[..., :3], 0, 255).astype(np.uint8)), np.uint8(_bd2(smudge, iterations=2)) * 255, 8, _cv.INPAINT_TELEA)
HLc = HL.copy(); HLc[..., :3] = hl_rgb
# outside it the ORIGINAL stays (cloak over the shoulder keeps its shape); loose light hair strands of the
# original lying on the cloak/skin just outside the head are repainted from their surroundings
ring = _bd2(R, iterations=40) & ~R & (poly(POLY['head_zone'], 0) > 0.5)
nlum = NB[..., :3].mean(-1)
nsat = np.max(NB[..., :3], -1) - np.min(NB[..., :3], -1)
strands = ring & (nsat < 55) & (nlum > 140) & (NB[..., 3] > 100)
nb_rgb = _cv.inpaint(np.ascontiguousarray(np.clip(NB[..., :3], 0, 255).astype(np.uint8)), np.uint8(_bd2(strands, iterations=2)) * 255, 8, _cv.INPAINT_TELEA)
body = NB.copy(); body[..., :3] = nb_rgb
hmask = gaussian_filter(R.astype(float), 1.5)
body[..., :3] = body[..., :3] * (1 - hmask[..., None]) + HLc[..., :3] * hmask[..., None]
body[..., 3] = body[..., 3] * (1 - hmask) + HLc[..., 3] * hmask
fore = poly(POLY['r_fore'], 1.5)
cap_rgb = arm[..., :3] if UA is not None else NB[..., :3]
cap_a = (arm[..., 3] / 255.0) if UA is not None else np.zeros((H, W))
cap_a = cap_a * (np.arange(H)[:, None] > 560)                           # only the elbow end, not the fist area
body[..., :3] = body[..., :3] * (1 - fore[..., None]) + cap_rgb * fore[..., None]
body[..., 3] = body[..., 3] * (1 - fore) + cap_a * 255 * fore
save('body', body)
# fingers in FRONT of the plasma ball (the palm stays behind it)
FING = [(888, 965), (893, 880), (960, 848), (1060, 810), (1150, 798), (1180, 850), (1172, 930), (1100, 938), (1020, 944), (950, 955)]
k0, k1, k2 = NB[..., 0], NB[..., 1], NB[..., 2]
skin = (k0 > 110) & (k0 > k1 + 8) & (k1 > k2) & (k0 - k2 > 35)          # fingers only, not the cloak behind them
skin = binary_closing(binary_opening(skin, iterations=1), iterations=2)
fa = poly(POLY['l_fore']) * poly(FING, 3) * gaussian_filter(skin.astype(float), 1.0) * (NB[..., 3] / 255)
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
coremask = (coremask & ~upper) | (zz > 0.5)
cs = np.clip((gaussian_filter(coremask.astype(float), 1.0) - 0.25) / 0.5, 0, 1)
cs = np.maximum(cs, zz * (zz > 0.02))
g1 = np.clip(gaussian_filter(coremask.astype(float), 7) * 2.2, 0, 1)
g2 = np.clip(gaussian_filter(coremask.astype(float), 20) * 2.0, 0, 1) * 0.55
bolt = np.zeros_like(H0)
glow_a = np.maximum(g1 * 0.85, g2)
col = np.array([110, 215, 255], float)
white = np.array([245, 253, 255], float)
a_out = np.maximum(cs, glow_a)
mix = np.where(a_out > 0, cs / np.maximum(a_out, 1e-3), 0)[..., None]
bolt[..., :3] = col * (1 - mix) + white * mix
bolt[..., 3] = a_out * 255
save('bolt', bolt, clean=False)
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
order = ['body', 'l_fore', 'orb', 'head', 'r_upper', 'r_fore', 'bolt']
comp = Image.new('RGBA', (W, H), (60, 60, 68, 255))
for nm in order:
    comp.alpha_composite(Image.open(os.path.join(OUT, f'p_{nm}.png')))
comp = comp.convert('RGB')
comp.thumbnail((700, 800))
comp.save(os.path.join(OUT, 'check.jpg'), quality=88)
print('ok', OUT)
