# Run from ~/ot2-work/rig (writes p_*.png there); then scripts/olympus_zeus_rig.py builds the Spine rig.
"""Cut Zeus (Tides 2 hero A) into rig parts: base (armless, from ChatGPT edit) + arms/bolt/orb from the original."""
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

A = Image.open('/Users/arturkasian/ot2-work/raw/S/hero.png').convert('RGBA')
N = Image.open('/Users/arturkasian/ot2-work/raw/S/zeus_nobolt.png').convert('RGBA')   # same Zeus, no lightning (ChatGPT edit)
B = Image.open('base_aligned.png').convert('RGBA')
W, H = A.size
POLY = {
    # right arm keeps the fist; the bolt zone excludes nothing now (effects come from the difference)
    'r_upper': [(250, 550), (170, 570), (60, 600), (22, 650), (28, 720), (80, 775), (170, 795), (300, 800), (380, 815),
                (410, 760), (445, 670), (475, 590), (420, 565), (330, 555)],
    'r_fore': [(15, 660), (8, 560), (35, 470), (100, 375), (170, 300), (200, 240), (260, 222), (332, 245), (368, 295),
               (366, 352), (330, 397), (270, 428), (228, 472), (230, 560), (208, 628), (140, 662), (70, 680)],
    'bolt_zone': [(0, 720), (0, 250), (250, 30), (720, 0), (720, 70), (560, 200), (450, 235), (385, 300), (300, 420),
                  (245, 520), (130, 720)],
    'l_fore': [(855, 1150), (866, 1030), (888, 955), (905, 880), (960, 850), (1060, 812), (1150, 800), (1178, 850),
               (1168, 980), (1160, 1100), (1120, 1152), (990, 1162)],
    'orb_zone': [(800, 960), (790, 760), (900, 640), (1000, 600), (1150, 610), (1150, 760), (1120, 820), (1040, 830),
                 (960, 860), (905, 880), (890, 955)],
}
PIVOT = {'r_shoulder': (330, 600), 'r_elbow': (95, 700), 'r_fist': (285, 330), 'l_elbow': (900, 1090), 'l_palm': (1010, 900),
         'orb': (1010, 850), 'head': (690, 420), 'neck': (650, 520), 'chest': (560, 760), 'hips': (560, 1080)}


def mask(name, feather=1.5):
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).polygon(POLY[name], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather)) if feather else m


def cyan(im):
    """lightning pixels: cyan glow OR the white-hot core (bright, unsaturated, not warm like skin highlights)"""
    a = np.array(im).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    glow = (b > r + 35) & (g > r + 10) & ((r + g + b) > 330)
    core = ((r + g + b) > 660) & (b >= r - 6) & (np.max(a[..., :3], -1) - np.min(a[..., :3], -1) < 40)
    return (glow | core) & (al > 20)


def take(src, m):
    a = np.array(src).copy()
    a[..., 3] = (a[..., 3].astype(float) * (np.array(m) / 255.0)).astype(np.uint8)
    return Image.fromarray(a)


parts = {}
# effects = what the original has and the bolt-free edit does not (soft alpha from the difference)
ao, an = np.array(A).astype(float), np.array(N).astype(float)
pre_o = ao[..., :3] * ao[..., 3:] / 255
pre_n = an[..., :3] * an[..., 3:] / 255
diff = np.clip((np.abs(pre_o - pre_n).max(-1) - 18) / 70, 0, 1)
bright = (ao[..., :3].sum(-1) > 300)
r_, g_, b_ = ao[..., 0], ao[..., 1], ao[..., 2]
# only electric colours: cyan glow (blue clearly above red) or the white-hot core; never warm skin / gold
elec = np.clip((b_ - r_ - 10) / 50, 0, 1)
core = np.clip((np.minimum(np.minimum(r_, g_), b_) - 200) / 40, 0, 1) * (b_ >= r_ - 6)
bright = bright * np.maximum(elec, core)
def fx(zone):
    z = np.array(mask(zone, 6)) / 255.0
    from scipy.ndimage import gaussian_filter
    al = gaussian_filter(diff * bright, 1.6) * z * (ao[..., 3] / 255)
    arr = np.array(A).copy(); arr[..., 3] = np.uint8(np.clip(al, 0, 1) * 255)
    return Image.fromarray(arr), al
parts['bolt'], bolt_al = fx('bolt_zone')
parts['orb'], _ = fx('orb_zone')
for n in ('r_upper', 'r_fore', 'l_fore'):
    parts[n] = take(N, mask(n))
parts['body'] = B
for n, im in parts.items():
    im.save(f'p_{n}.png')
json.dump({'size': [W, H], 'pivot': PIVOT}, open('rig.json', 'w'), indent=1)

# check: recomposite and overlay
comp = Image.new('RGBA', (W, H))
for n in ('body', 'r_upper', 'l_fore', 'orb', 'r_fore', 'bolt'):
    comp.alpha_composite(parts[n])
bg = Image.new('RGBA', (W, H), (60, 60, 68, 255)); bg.alpha_composite(comp)
d = ImageDraw.Draw(bg)
cols = {'r_upper': (255, 60, 60), 'r_fore': (60, 255, 60), 'l_fore': (255, 200, 0), 'bolt_zone': (0, 200, 255), 'orb_zone': (255, 0, 255)}
for n, c in cols.items():
    d.line(POLY[n] + [POLY[n][0]], fill=c + (255,), width=3)
for k, (x, y) in PIVOT.items():
    d.ellipse((x - 8, y - 8, x + 8, y + 8), outline=(255, 255, 255, 255), width=3)
bg = bg.convert('RGB'); bg.thumbnail((900, 1000)); bg.save('/Users/arturkasian/ot2-work/prev/_parts_check.jpg')
