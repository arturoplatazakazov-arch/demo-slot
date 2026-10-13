"""Volt Coins: cut the game's art out of the two flat AI mockups.

The client approved the direction of two flat ChatGPT mockups (landscape +
portrait, front/img/volt-coins/src/ref_{desk,mob}.png) and fal.ai was locked,
so every layer the game needs is cut from those two pictures here, with plain
numpy + PIL (no cv2 in the project venv):

  symbols/<code>.png   the nine cells of the portrait mockup (the bigger ones),
                       keyed off the near-black cell: alpha = how far a pixel
                       rises above the cell's own median border colour, colour
                       un-blended against it. Then the client's notes:
                       low symbols drawn smaller (hierarchy), bell pushed to
                       brass and the ingot muted so the COIN stays the one
                       saturated gold on the field.
  img/frame.png        the portrait mockup's cabinet frame, window punched out.
  img/logo.png         the landscape logo, segmented by colour (gold / blue /
                       highlights), outline grown back, specks dropped, (TM)
                       removed.
  img/bg_{desk,mob}.jpg the mockups with logo/plates/reels filled away (masked
                       pyramid fill — it all sits under DOM anyway), Tesla
                       coils switched OFF (their blue rings dimmed: idle state
                       per the client), then the whole plate dimmed, blurred and
                       vignetted to ~35-40% of the reels' brightness.
  img/cover.jpg        catalog cover: bg + frame + symbols + logo.

Geometry of every cut lives in the constants below; slot.css mirrors FRAME_*.

    .venv/bin/python scripts/volt_coins_art.py
"""

import collections
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'volt-coins')
SRC = os.path.join(ROOT, 'src')
IMG = os.path.join(ROOT, 'img')
SYM = os.path.join(ROOT, 'symbols')

# Portrait mockup: reel window and the gold grid lines between cells.
MOB_XS = [85, 339, 593, 847]
MOB_YS = [554, 756, 958, 1160]
CELL_CODES = [['seven', 'diamond', 'bell'], ['ingot', 'wild', 'coin'], ['bar', 'star', 'horseshoe']]

# Symbol canvas = cell aspect (window 762x606 / 3x3 -> 1.26).
SYM_W, SYM_H = 320, 254
# Share of the canvas a symbol's alpha box may fill (hierarchy per GDD).
FILL = {
    'wild': 0.95, 'coin': 0.95, 'seven': 0.92, 'diamond': 0.92, 'ingot': 0.92, 'bell': 0.9,
    'bar': 0.8, 'star': 0.8, 'horseshoe': 0.8,
}

# Portrait frame: outer box and the window inside it (mockup px).
FRAME_BOX = (36, 512, 906, 1206)
FRAME_WIN = (85, 560, 851, 1164)
FRAME_CHAMFER = 16

LOGO_BOX = (570, 18, 1240, 152)
# Hand-traced hull of the wordmark (mockup px): colour alone also catches the
# background's lightning streaks and the top of the GRAND plate under the V.
LOGO_HULL = [(576, 46), (700, 42), (752, 20), (790, 40), (1212, 46), (1214, 138),
             (790, 140), (742, 156), (704, 140), (664, 140), (650, 150), (634, 150)]

# Areas each mockup paints that the game draws itself (filled away).
DESK_HOLES = [(560, 14, 1250, 160), (455, 140, 1340, 250), (498, 238, 1300, 822)]
MOB_HOLES = [(150, 222, 795, 362), (14, 375, 915, 500), (30, 505, 912, 1212)]
# Tesla coil, landscape mockup's left one: symmetric about COIL_CX, half-width
# per height (mockup px), plus the "on" ring round its head. Cut out as its own
# layer (img/coil.png, switched off) and removed from both backgrounds — the
# client wants the plate layered (bg / door / coils / glow), and a baked coil
# sits wherever the cover crop puts it (off-screen on 16:9).
COIL_CX = 205
COIL_PROFILE = [(196, 70), (212, 92), (240, 92), (262, 40), (336, 40), (340, 66), (374, 68),
                (380, 58), (478, 58), (484, 74), (518, 74), (524, 108), (560, 112), (566, 126),
                (598, 128), (604, 138), (698, 140), (706, 150), (714, 150)]
COIL_RING = (223, 129, 40)  # cy, rx, ry
COIL_BOX = (COIL_CX - 152, 178, COIL_CX + 152, 716)
DESK_COIL_CXS = [205, 1598]
MOB_COIL_HOLES = [(30, 130, 225, 395), (712, 130, 905, 395)]


def arr(im):
    return np.asarray(im).astype(np.float32)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------
# symbols

def key_cell(src, box):
    c = arr(src.crop(box))
    ring = np.concatenate([c[:6].reshape(-1, 3), c[-6:].reshape(-1, 3),
                           c[:, :6].reshape(-1, 3), c[:, -6:].reshape(-1, 3)])
    bg = np.median(ring, 0)
    d = np.clip(c - bg, 0, None).max(2)
    a = np.clip((d - 14) / 60, 0, 1)
    a = a * a * (3 - 2 * a)
    am = np.maximum(a, 1e-3)[..., None]
    col = np.clip((c - (1 - am) * bg) / am, 0, 255)
    return to_im(np.dstack([col, a * 255]))


def trim(im, thr=10):
    a = np.asarray(im.getchannel('A'))
    ys, xs = np.where(a > thr)
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def recolor(im, code):
    rgb, a = im.convert('RGB'), im.getchannel('A')
    if code == 'bell':
        # brass instead of coin-gold: warmer, a touch less saturated
        r, g, b = rgb.split()
        g = g.point(lambda v: v * 0.88)
        b = b.point(lambda v: v * 0.8)
        rgb = ImageEnhance.Color(Image.merge('RGB', (r, g, b))).enhance(0.85)
    elif code == 'ingot':
        rgb = ImageEnhance.Color(rgb).enhance(0.78)
    elif code in ('bar', 'star', 'horseshoe'):
        # low symbols: flatter (less contrast), per the GDD hierarchy
        rgb = ImageEnhance.Contrast(rgb).enhance(0.9)
    out = rgb.convert('RGBA')
    out.putalpha(a)
    return out


def build_symbols(mob):
    os.makedirs(SYM, exist_ok=True)
    for ri in range(3):
        for ci in range(3):
            code = CELL_CODES[ri][ci]
            ins = 7
            box = (MOB_XS[ci] + ins, MOB_YS[ri] + ins, MOB_XS[ci + 1] - ins, MOB_YS[ri + 1] - ins)
            im = recolor(trim(key_cell(mob, box)), code)
            k = min(SYM_W * FILL[code] / im.width, SYM_H * FILL[code] / im.height)
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
            im = im.filter(ImageFilter.UnsharpMask(1.2, 40, 2))
            canvas = Image.new('RGBA', (SYM_W, SYM_H))
            canvas.alpha_composite(im, ((SYM_W - im.width) // 2, (SYM_H - im.height) // 2))
            canvas.save(os.path.join(SYM, f'{code}.png'), optimize=True)
    print('symbols ok')


# --------------------------------------------------------------------------
# frame

def build_frame(mob):
    x0, y0, x1, y1 = FRAME_BOX
    im = mob.crop(FRAME_BOX).convert('RGBA')
    w, h = im.size
    m = Image.new('L', (w * 4, h * 4))
    d = ImageDraw.Draw(m)
    c = FRAME_CHAMFER * 4
    W, H = w * 4, h * 4
    d.polygon([(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)], fill=255)
    wx0, wy0, wx1, wy1 = [(v - o) * 4 for v, o in zip(FRAME_WIN, (x0, y0, x0, y0))]
    d.rectangle([wx0, wy0, wx1, wy1], fill=0)
    m = m.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    im.putalpha(m)
    im.save(os.path.join(IMG, 'frame.png'), optimize=True)
    print('frame', im.size, 'window in frame px',
          (FRAME_WIN[0] - x0, FRAME_WIN[1] - y0, FRAME_WIN[2] - x0, FRAME_WIN[3] - y0))


# --------------------------------------------------------------------------
# logo

def components(mask, min_area):
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    keep = np.zeros((h, w), bool)
    n = 0
    for sy, sx in zip(*np.nonzero(mask)):
        if lab[sy, sx]:
            continue
        n += 1
        q = collections.deque([(sy, sx)])
        lab[sy, sx] = n
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = n
                    q.append((ny, nx))
        if len(pts) >= min_area:
            ys, xs = zip(*pts)
            keep[list(ys), list(xs)] = True
    return keep


def fill_holes(mask):
    h, w = mask.shape
    outside = np.zeros_like(mask)
    q = collections.deque()
    for y in range(h):
        for x in (0, w - 1):
            if not mask[y, x]:
                outside[y, x] = True
                q.append((y, x))
    for x in range(w):
        for y in (0, h - 1):
            if not mask[y, x] and not outside[y, x]:
                outside[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True
                q.append((ny, nx))
    return ~outside


def build_logo(desk):
    c = arr(desk.crop(LOGO_BOX))
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    core = ((r > 120) & (g > 70) & (r - b > 50)) | (c.max(2) > 200) | ((b > 140) & (b - r > 40))
    m = Image.fromarray(core.astype(np.uint8) * 255).filter(ImageFilter.MedianFilter(3))
    m = m.filter(ImageFilter.MaxFilter(9))
    mk = np.asarray(m) > 0
    mk[:44, 615:] = False  # the (TM) mark
    hull = Image.new('L', mk.shape[::-1])
    ImageDraw.Draw(hull).polygon([(x - LOGO_BOX[0], y - LOGO_BOX[1]) for x, y in LOGO_HULL], fill=255)
    mk &= np.asarray(hull) > 0
    mk = components(mk, 1500)
    mk = fill_holes(mk)
    m = Image.fromarray(mk.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.1))
    im = to_im(np.dstack([c, np.asarray(m, np.float32)]))
    im = trim(im, 6)
    im.save(os.path.join(IMG, 'logo.png'), optimize=True)
    print('logo', im.size)


# --------------------------------------------------------------------------
# backgrounds

def pyramid_fill(a, hole):
    """Fill `hole` (bool HxW) from its surroundings: masked 2x pooling down to
    a coarse level, then every hole pixel takes the upsampled coarse value."""
    a = a.copy()
    w = (~hole).astype(np.float32)
    levels = [(a * w[..., None], w)]
    while min(levels[-1][1].shape) > 4:
        s, ww = levels[-1]
        h2, w2 = ww.shape[0] // 2 * 2, ww.shape[1] // 2 * 2
        s = s[:h2, :w2]
        ww = ww[:h2, :w2]
        s = s.reshape(h2 // 2, 2, w2 // 2, 2, 3).sum((1, 3))
        ww = ww.reshape(h2 // 2, 2, w2 // 2, 2).sum((1, 3))
        levels.append((s, ww))
    est = None
    for s, ww in reversed(levels):
        cur = s / np.maximum(ww, 1e-6)[..., None]
        if est is not None:
            up = np.asarray(to_im(est).resize((cur.shape[1], cur.shape[0]), Image.BILINEAR), np.float32)
            cur = np.where((ww > 0.5)[..., None], cur, up)
        est = cur
    full = np.asarray(to_im(est).resize((a.shape[1], a.shape[0]), Image.BILINEAR), np.float32)
    a[hole] = full[hole]
    return a


def coil_mask(size, cx, dy=0, k=1.0, grow=0):
    """Coil silhouette at centre x `cx` on a canvas of `size` (supersampled)."""
    ss = 4
    m = Image.new('L', (size[0] * ss, size[1] * ss))
    d = ImageDraw.Draw(m)
    pts_l, pts_r = [], []
    for y, hw in COIL_PROFILE:
        yy = (y * k + dy) * ss
        pts_r.append(((cx + (hw + grow) * k) * ss, yy))
        pts_l.append(((cx - (hw + grow) * k) * ss, yy))
    d.polygon(pts_r + pts_l[::-1], fill=255)
    cy, rx, ry = COIL_RING
    d.ellipse([(cx - (rx + grow) * k) * ss, (cy * k + dy - ry - grow) * ss,
               (cx + (rx + grow) * k) * ss, (cy * k + dy + ry + grow) * ss], fill=255)
    return m.resize(size, Image.LANCZOS)


def build_coil(desk):
    x0, y0, x1, y1 = COIL_BOX
    a = arr(desk)
    a = coils_off(a, [COIL_BOX])
    crop = to_im(a).crop(COIL_BOX)
    m = coil_mask(desk.size, COIL_CX).crop(COIL_BOX).filter(ImageFilter.GaussianBlur(1.2))
    # fade the floor-light under the base
    fade = np.ones((y1 - y0, 1), np.float32)
    fade[-14:, 0] = np.linspace(1, 0, 14)
    m = Image.fromarray((np.asarray(m, np.float32) * fade).astype(np.uint8))
    out = crop.convert('RGBA')
    out.putalpha(m)
    out.save(os.path.join(IMG, 'coil.png'), optimize=True)
    print('coil', out.size)


def coils_off(a, boxes):
    for x0, y0, x1, y1 in boxes:
        sub = a[y0:y1, x0:x1]
        r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
        glow = np.clip((b - np.maximum(r, g) * 0.75 - 40) / 90, 0, 1)
        glow = np.asarray(Image.fromarray((glow * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)),
                          np.float32) / 255
        lum = sub.mean(2, keepdims=True)
        steel = np.concatenate([lum * 0.35, lum * 0.4, lum * 0.5], 2)
        a[y0:y1, x0:x1] = sub * (1 - glow[..., None]) + steel * glow[..., None]
    return a


def grade(a, dim, blur):
    im = to_im(a).filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im, np.float32) * dim
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    v = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h * 0.45) / (h / 2)) ** 2
    vig = np.clip(1.05 - 0.45 * v, 0.35, 1)[..., None]
    a = a * vig
    # cool the shadows a touch toward the GDD indigo
    a[..., 2] = a[..., 2] * 1.06 + 4
    return a


def build_bg(src, holes, coil_cxs, name, dim):
    a = arr(src)
    hole = np.zeros(a.shape[:2], bool)
    for x0, y0, x1, y1 in holes:
        hole[y0:y1, x0:x1] = True
    for cx in coil_cxs:
        hole |= np.asarray(coil_mask(src.size, cx, grow=14)) > 20
    a = pyramid_fill(a, hole)
    a = grade(a, dim, 2.2)
    to_im(a).save(os.path.join(IMG, f'{name}.jpg'), quality=86, optimize=True, progressive=True)
    print(name, src.size)


def build_cover():
    """Catalog cover = the landscape game screen in idle, composed at the
    1920x1040 design-canvas coordinates css/volt-coins.css uses."""
    W, H = 1920, 1040
    bg = Image.open(os.path.join(IMG, 'bg_desk.jpg'))
    k = max(W / bg.width, H / bg.height)
    bg = bg.resize((round(bg.width * k), round(bg.height * k)), Image.LANCZOS)
    canvas = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W,
                      (bg.height - H) // 2 + H)).convert('RGBA')
    coil = Image.open(os.path.join(IMG, 'coil.png')).resize((336, 641), Image.LANCZOS)
    canvas.alpha_composite(coil, (53, 286))
    canvas.alpha_composite(coil.transpose(Image.FLIP_LEFT_RIGHT), (1531, 286))
    cw, ch = 220, 174  # cell; symbol PNGs are 1.5x
    wx, wy = 627, 270
    canvas.alpha_composite(Image.new('RGBA', (cw * 3, ch * 3), (6, 10, 34, 255)), (wx, wy))
    for ri in range(3):
        for ci in range(3):
            sym = Image.open(os.path.join(SYM, CELL_CODES[ri][ci] + '.png')).resize((cw, ch), Image.LANCZOS)
            canvas.alpha_composite(sym, (wx + ci * cw, wy + ri * ch))
    frame = Image.open(os.path.join(IMG, 'frame.png')).resize((750, 598), Image.LANCZOS)
    canvas.alpha_composite(frame, (585, 229))
    logo = Image.open(os.path.join(IMG, 'logo.png')).resize((760, 217), Image.LANCZOS)
    canvas.alpha_composite(logo, ((W - 760) // 2, 20))
    canvas = canvas.crop((0, 20, W, 900)).convert('RGB')
    canvas.resize((960, 440), Image.LANCZOS).save(os.path.join(IMG, 'cover.jpg'), quality=85, optimize=True)
    print('cover ok')


# --------------------------------------------------------------------------
# v2 (2026-10-13, art-director pass): symbols, logo and coil re-generated in
# fal (nano-banana-pro/edit, the v1 cut-outs as reference) on pure black with
# room for the whole glow — the v1 cuts had their glow sliced flat by the
# mockup's cell edges and dirty shadow halos from the keying. Sources (2K gen
# + birefnet mask) live in art/volt-coins-src/, outside front/ so they never
# ship. Alpha = max(birefnet body mask, luminance key of the glow).

GEN = os.path.join(os.path.dirname(__file__), '..', 'art', 'volt-coins-src')
SYM_SCALE = 1.5  # symbol PNGs are 1.5x the 320x254 cell units (retina)


# Metal tone matching for the coin states (hue degrees, sat x, value x), only
# on warm metal pixels — the gold value coin came out coppery, next to the
# bronze MINI it read as the same coin. Targets the base coin (hue ~35).
TONE = {'coin_value': (5.0, 1.12, 1.08), 'coin_major': (2.5, 1.08, 1.05)}


def tone(rgb_im, dh, ks, kv):
    hsv = np.asarray(rgb_im.convert('HSV')).astype(np.float32)
    h, s_, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    warm = (h < 60 * 255 / 360) & (s_ > 40)
    h[warm] = np.clip(h[warm] + dh * 255 / 360, 0, 255)
    s_[warm] = np.clip(s_[warm] * ks, 0, 255)
    v[warm] = np.clip(v[warm] * kv, 0, 255)
    return Image.fromarray(np.dstack([h, s_, v]).astype(np.uint8), 'HSV').convert('RGB')


def glow_cut(name, glow_lo=6, glow_span=110):
    rgb_im = Image.open(os.path.join(GEN, name + '.jpg')).convert('RGB')
    if name in TONE:
        rgb_im = tone(rgb_im, *TONE[name])
    m = Image.open(os.path.join(GEN, name + '_mask.png')).convert('L')
    if m.size != rgb_im.size:
        m = m.resize(rgb_im.size, Image.LANCZOS)
    rgb = arr(rgb_im)
    m = np.asarray(m, np.float32) / 255
    g = np.clip((rgb.max(2) - glow_lo) / glow_span, 0, 1) ** 0.9
    a = np.maximum(m, g)
    unp = np.clip(rgb / np.maximum(a, 1e-3)[..., None], 0, 255)
    col = rgb * m[..., None] + unp * (1 - m[..., None])
    return to_im(np.dstack([col, a * 255])), m


def body_box(m, thr=0.5):
    ys, xs = np.where(m > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


# Share of the cell the solid body (alpha > 200) takes along its larger
# relative axis — the hierarchy: wild/coin biggest, highs next, lows smallest.
BODY = {
    'wild': 0.86, 'coin': 0.86, 'ingot': 0.74, 'seven': 0.8, 'diamond': 0.66, 'bell': 0.64,
    'horseshoe': 0.62, 'star': 0.62, 'bar': 0.58,
    # Hold & Win coin states: empty enamel centre, the client prints xN / tier name
    'coin_value': 0.86, 'coin_mini': 0.86, 'coin_minor': 0.86, 'coin_major': 0.86,
}
COIN_STATES = ['coin_value', 'coin_mini', 'coin_minor', 'coin_major']


def build_symbols_v2():
    os.makedirs(SYM, exist_ok=True)
    W, H = round(SYM_W * SYM_SCALE), round(SYM_H * SYM_SCALE)

    def place(im, k, cx, cy):
        big = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        canvas = Image.new('RGBA', (W, H))
        canvas.alpha_composite(big, (round(W / 2 - cx * k), round(H / 2 - cy * k)))
        return canvas

    for code in [c for row in CELL_CODES for c in row] + COIN_STATES:
        im, _ = glow_cut(code)
        a = np.asarray(im.getchannel('A'))
        ys, xs = np.where(a > 200)
        bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        # cap by the VISIBLE glow (alpha > 40); its faint tail beyond that is
        # faded out towards the cell edge below instead of being sliced
        gx0, gy0, gx1, gy1 = trim_box(im, 40)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        k = BODY[code] / max((bx1 - bx0) / W, (by1 - by0) / H)
        k = min(k, (W / 2 - 1) / max(cx - gx0, gx1 - cx), (H / 2 - 1) / max(cy - gy0, gy1 - cy))
        tile = place(im, k, cx, cy)
        yy, xx = np.mgrid[0:H, 0:W]
        edge = np.minimum.reduce([xx, W - 1 - xx, yy, H - 1 - yy]).astype(np.float32)
        fade = np.clip(edge / 22, 0, 1)
        fade = fade * fade * (3 - 2 * fade)
        al = np.asarray(tile.getchannel('A'), np.float32) * fade
        tile.putalpha(Image.fromarray(al.astype(np.uint8)))
        tile.save(os.path.join(SYM, f'{code}.png'), optimize=True)
    print('symbols v2 ok', (W, H))


def trim_box(im, thr=6):
    a = np.asarray(im.getchannel('A'))
    ys, xs = np.where(a > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def build_logo_v2(width=1240):
    im, _ = glow_cut('logo', glow_lo=8, glow_span=120)
    im = im.crop(trim_box(im, 4))
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(os.path.join(IMG, 'logo.png'), optimize=True)
    # where the bolt in the O is (fx/logo crackles there)
    c = arr(im)
    hot = (c[..., 2] > 225) & (c[..., 1] > 200) & (c[..., 0] < 200) & (c[..., 3] > 200)
    ys, xs = np.where(hot[:, : im.width // 3])
    print('logo v2', im.size, 'bolt', round(xs.mean()), round(ys.mean()))


def build_coil_v2(height=1080):
    im, m = glow_cut('coil', glow_lo=10, glow_span=60)
    # the coil is "off": no glow wanted, only the body + its soft edge
    a = np.minimum(np.asarray(im.getchannel('A'), np.float32),
                   np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)), np.float32))
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    im = im.crop(trim_box(im, 4))
    im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    im.save(os.path.join(IMG, 'coil.png'), optimize=True)
    al = np.asarray(im.getchannel('A')) > 128
    rows = al.sum(1)
    top = int(np.argmax(rows > 0))
    ring_row = top + int(np.argmax(rows[top: top + height // 5]))
    print('coil v2', im.size, 'ring row', ring_row, 'ring half-width', rows[ring_row] // 2)


def main():
    os.makedirs(IMG, exist_ok=True)
    desk = Image.open(os.path.join(SRC, 'ref_desk.png')).convert('RGB')
    mob = Image.open(os.path.join(SRC, 'ref_mob.png')).convert('RGB')
    build_symbols_v2()
    build_frame(mob)
    build_logo_v2()
    build_coil_v2()
    build_bg(desk, DESK_HOLES, DESK_COIL_CXS, 'bg_desk', 0.5)
    build_bg(mob, MOB_HOLES + MOB_COIL_HOLES, [], 'bg_mob', 0.5)
    build_cover()


if __name__ == '__main__':
    main()
