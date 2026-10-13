"""Art pipeline for the "tesla-spins" slot — everything is cut from ONE picture.

Source: front/img/tesla-spins/src/reference.jpg (1280x623, the concept shot the
user brought: a riveted steel cabinet with a 3x3 grid between two Tesla coils).
No image model is involved (fal.ai was out of credit) — the scene, the empty
cabinet and all nine symbols come out of that picture with plain PIL/numpy:

1. Empty cells. The top-left (lemon) cell is the cleanest one: its panel interior
   is rebuilt as a Coons patch from its own border ring (the lemon never touches
   the ring), and that clean cell is pasted, resized, into all nine slots.
2. Symbols. Each cell minus the clean panel = the symbol; colour distance gives a
   soft alpha, the biggest connected blob is kept, the result is trimmed and
   upscaled 2x (the source cells are only ~190px).
3. Front layer. The cabinet (frame + dividers) with every cell made transparent —
   it is drawn ABOVE the spinning strips, so the horizontal dividers hide the
   seams between rows the way the bars of a real cabinet do.

Usage: .venv/bin/python scripts/tesla_spins_art.py
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'tesla-spins')
SRC = os.path.join(ROOT, 'src', 'reference.jpg')

# Outer rect of every cell (bronze ring included), measured on the reference:
# dark-panel coverage profiles across the window + visual check of the overlay.
COLS = [(349, 537), (544, 738), (741, 935)]
ROWS = [(62, 229), (233, 396), (404, 559)]
# Window of the cabinet = union of the cells.
WIN = (COLS[0][0], ROWS[0][0], COLS[2][1], ROWS[2][1])

# Symbol code per cell [row][col], as painted in the reference.
LAYOUT = [
    ['lemon', 'seven', 'bell'],
    ['plum', 'coin', 'cherry'],
    ['gold', 'watermelon', 'star'],
]

PANEL_INSET = 12  # bronze ring + inner bevel, px from the outer cell rect


def arr(im):
    return np.asarray(im, dtype=np.float32)


def coons(border_img):
    """Rebuild the interior of `border_img` (H,W,3) from its 1px outer border."""
    h, w, _ = border_img.shape
    top, bot = border_img[0].copy(), border_img[-1].copy()
    lef, rig = border_img[:, 0].copy(), border_img[:, -1].copy()
    # Robust borders: anything brighter than the panel (a stray highlight)
    # becomes the side's median.
    for side in (top, bot, lef, rig):
        lum = side.mean(1)
        med = np.median(side, 0)
        bad = lum > np.median(lum) + 18
        side[bad] = med
        # light 1D smoothing so the patch has no streaks
        k = np.ones(41) / 41
        for c in range(3):
            side[:, c] = np.convolve(np.pad(side[:, c], 20, mode='edge'), k, 'valid')
    u = np.linspace(0, 1, w)[None, :, None]
    v = np.linspace(0, 1, h)[:, None, None]
    lc = (1 - v) * top[None] + v * bot[None]
    ld = (1 - u) * lef[:, None] + u * rig[:, None]
    c00, c10, c01, c11 = top[0], top[-1], bot[0], bot[-1]
    bl = ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11)
    return lc + ld - bl


def clean_cell(ref):
    """Lemon cell with its panel rebuilt — the template for all nine."""
    x0, x1 = COLS[0]
    y0, y1 = ROWS[0]
    cell = arr(ref.crop((x0, y0, x1 + 1, y1 + 1)))
    i = PANEL_INSET
    inner = cell[i:-i, i:-i]
    patch = coons(inner)
    # faint grain so the flat patch matches the noisy painted panel
    rng = np.random.default_rng(7)
    patch += rng.normal(0, 1.6, patch.shape[:2])[..., None]
    out = cell.copy()
    out[i:-i, i:-i] = patch
    # feather the seam between the patch and the original bevel
    m = np.zeros(cell.shape[:2], np.float32)
    m[i + 3:-i - 3, i + 3:-i - 3] = 1
    m = arr(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))) / 255
    out = cell * (1 - m[..., None]) + out * m[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def empty_scene(ref, template):
    scene = ref.copy()
    for x0, x1 in COLS:
        for y0, y1 in ROWS:
            t = template.resize((x1 - x0 + 1, y1 - y0 + 1), Image.LANCZOS)
            scene.paste(t, (x0, y0))
    # The painted wild glowed blue onto the bars around the centre cell. Pull
    # that tint back towards the steel/bronze of the rest of the cabinet.
    a = arr(scene)
    x0, y0 = COLS[1][0] - 14, ROWS[1][0] - 14
    x1, y1 = COLS[1][1] + 14, ROWS[1][1] + 14
    reg = a[y0:y1, x0:x1]
    r, g, b = reg[..., 0], reg[..., 1], reg[..., 2]
    blue = np.clip((b - np.maximum(r, g) - 25) / 60, 0, 1)
    inside = np.zeros(reg.shape[:2], bool)
    for cx0, cx1 in COLS:
        for cy0, cy1 in ROWS:
            inside[max(0, cy0 - y0):max(0, cy1 + 1 - y0), max(0, cx0 - x0):max(0, cx1 + 1 - x0)] = True
    blue[inside] = 0
    lum = reg.mean(2, keepdims=True)
    steel = np.concatenate([lum * 0.62, lum * 0.6, lum * 0.78], 2)
    reg[:] = reg * (1 - blue[..., None]) + steel * blue[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def label_largest(mask):
    """Keep connected components (4-neighbour) of `mask` that hold >= 8% of the
    biggest one — a cherry pair or a stem must survive, specks must not."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    sizes = [0]
    cur = 0
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or lab[sy, sx]:
                continue
            cur += 1
            stack = [(sy, sx)]
            lab[sy, sx] = cur
            n = 0
            while stack:
                y, x = stack.pop()
                n += 1
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        stack.append((ny, nx))
            sizes.append(n)
    if cur == 0:
        return mask
    big = max(sizes)
    keep = [i for i, s in enumerate(sizes) if i and s >= big * 0.08]
    return np.isin(lab, keep)


def fill_holes(mask):
    """Everything the outside can't reach is inside: dark seeds of the
    watermelon, the mouth of the bell, the shaded side of the plum."""
    h, w = mask.shape
    seen = np.zeros((h + 2, w + 2), bool)
    m = np.pad(mask, 1)
    stack = [(0, 0)]
    seen[0, 0] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h + 2 and 0 <= nx < w + 2 and not seen[ny, nx] and not m[ny, nx]:
                seen[ny, nx] = True
                stack.append((ny, nx))
    return ~seen[1:-1, 1:-1]


def morph(mask, size, op):
    im = Image.fromarray((mask * 255).astype(np.uint8))
    f = ImageFilter.MinFilter(size) if op == 'min' else ImageFilter.MaxFilter(size)
    return arr(im.filter(f)) > 127


# Symbols that carry thin electric arcs from the painted wild: an opening
# (erode -> dilate) strips the arcs, the symbol body survives it.
OPEN = {'seven': 7}
# Per-symbol cut threshold: the plum's shaded side is nearly panel-dark purple.
THRESH = {'plum': 34, 'star': 60}


def cut_symbol(ref, template, row, col):
    code = LAYOUT[row][col]
    x0, x1 = COLS[col]
    y0, y1 = ROWS[row]
    cell = arr(ref.crop((x0, y0, x1 + 1, y1 + 1)))
    bg = arr(template.resize((x1 - x0 + 1, y1 - y0 + 1), Image.LANCZOS))
    # Score = how much brighter OR how differently coloured than the panel.
    # A drop shadow is darker and the same hue -> scores ~0, so no halo.
    lum_c, lum_b = cell.mean(2), bg.mean(2)
    chroma = np.sqrt((((cell - lum_c[..., None]) - (bg - lum_b[..., None])) ** 2).sum(2))
    score = np.maximum(lum_c - lum_b, 0) + 1.2 * chroma
    i = 12
    score[:i], score[-i:], score[:, :i], score[:, -i:] = 0, 0, 0, 0
    if code == 'seven':
        # the painted wild's arcs crawl under the 7 — the 7 has no blue in it
        score[cell[..., 2] > cell[..., 0] + 10] = 0
    if code == 'coin':
        return cut_wild(cell, bg)
    hard = score > THRESH.get(code, 48)
    if code in OPEN:
        hard = morph(morph(hard, OPEN[code], 'min'), OPEN[code], 'max')
    hard = label_largest(hard)
    hard = fill_holes(hard)
    # soft 1-2px edge: ramp of the score, but only right next to the body
    near = morph(hard, 5, 'max')
    ramp = np.clip((score - 22) / 40, 0, 1)
    alpha = np.where(hard, 1.0, ramp * near)
    alpha = arr(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))) / 255
    alpha = np.where(morph(hard, 3, 'min'), 1.0, alpha)
    # Un-mix the panel from semi-transparent edges: c = a*fg + (1-a)*bg.
    a3 = np.clip(alpha, 0.05, 1)[..., None]
    fg = np.clip((cell - (1 - a3) * bg) / a3, 0, 255)
    fg = np.where(alpha[..., None] > 0.02, fg, 0)
    rgba = np.concatenate([fg, (alpha * 255)[..., None]], 2).astype(np.uint8)
    im = Image.fromarray(rgba, 'RGBA')
    bbox = im.getchannel('A').point(lambda v: 255 if v > 10 else 0).getbbox()
    im = im.crop(bbox)
    # 2x upscale + gentle unsharp: the reel cell is ~same size as the source
    # cell on a 1080p screen, bigger on retina.
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
    rgb.putalpha(im.getchannel('A'))
    return rgb


def cut_wild(cell, bg):
    """The wild is a copper coin with a neon bolt, sitting in a cloud of painted
    arcs. Keep the coin disc + the bolt, drop the arcs, and give it back a clean
    procedural glow (the live arcs come from the Spine clip and the coil FX)."""
    h, w, _ = cell.shape
    r, g, b = cell[..., 0], cell[..., 1], cell[..., 2]
    lum = cell.mean(2)
    copper = (r > b + 25) & (lum > 60)
    ys, xs = np.nonzero(copper)
    cy, cx = (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2
    rad = max(ys.max() - ys.min(), xs.max() - xs.min()) / 2 + 1
    yy, xx = np.mgrid[0:h, 0:w]
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= rad ** 2
    bolt = (b > 170) & (lum > 120)
    bolt = morph(morph(bolt, 3, 'min'), 3, 'max')
    bolt = label_largest(bolt)
    bolt = fill_holes(morph(bolt, 5, 'max'))
    body = fill_holes(disc | bolt)
    alpha = arr(Image.fromarray((body * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))) / 255
    fg = cell.copy()
    # pad so the new glow has room
    P = 24
    H, W = h + 2 * P, w + 2 * P
    glow_src = np.zeros((H, W), np.uint8)
    glow_src[P:P + h, P:P + w] = (bolt * 255).astype(np.uint8)
    glow = arr(Image.fromarray(glow_src).filter(ImageFilter.GaussianBlur(10))) / 255
    glow = np.clip(glow * 1.6, 0, 0.85)
    out = np.zeros((H, W, 4), np.float32)
    out[..., 0], out[..., 1], out[..., 2] = 60, 140, 255
    out[..., 3] = glow
    a = np.zeros((H, W), np.float32)
    a[P:P + h, P:P + w] = alpha
    rgb = out[..., :3].copy()
    rgb[P:P + h, P:P + w] = fg
    # composite body over glow
    A = a + glow * (1 - a)
    C = (rgb * a[..., None] + out[..., :3] * (glow * (1 - a))[..., None]) / np.clip(A, 1e-3, 1)[..., None]
    rgba = np.concatenate([C, (A * 255)[..., None]], 2).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(rgba, 'RGBA')
    im = im.crop(im.getchannel('A').point(lambda v: 255 if v > 6 else 0).getbbox())
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    rgb2 = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
    rgb2.putalpha(im.getchannel('A'))
    return rgb2


def front_layer(scene):
    """Cabinet crop with every cell punched out (with the cell's rounded corner)."""
    pad = 40
    box = (WIN[0] - pad, WIN[1] - pad, WIN[2] + pad + 1, WIN[3] + pad + 1)
    crop = scene.crop(box).convert('RGBA')
    mask = Image.new('L', crop.size, 255)
    d = ImageDraw.Draw(mask)
    for x0, x1 in COLS:
        for y0, y1 in ROWS:
            # keep the bronze ring (4px) — symbols slide UNDER it
            d.rounded_rectangle((x0 - box[0] + 4, y0 - box[1] + 4, x1 - box[0] - 4, y1 - box[1] - 4),
                                radius=9, fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(0.8))
    # outside the cabinet silhouette: transparent too (the scene under it is
    # the same picture, but the pad would otherwise cover lightning FX)
    outer = Image.new('L', crop.size, 0)
    ImageDraw.Draw(outer).rectangle((pad - 30, pad - 30, crop.width - pad + 30, crop.height - pad + 30), fill=255)
    mask = Image.fromarray(np.minimum(arr(mask), arr(outer)).astype(np.uint8))
    crop.putalpha(mask)
    return crop, box


def panel_tile(template):
    """Interior of the clean cell — painted behind the spinning strips."""
    i = PANEL_INSET - 4
    t = template.crop((i, i, template.width - i, template.height - i))
    return t


ROCKWELL = '/System/Library/Fonts/Supplemental/Rockwell.ttc'
COPPERPLATE = '/System/Library/Fonts/Supplemental/Copperplate.ttc'


def text_mask(size, text, font, xy, tracking=0):
    m = Image.new('L', size, 0)
    d = ImageDraw.Draw(m)
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (size[0] - total) / 2 if xy[0] is None else xy[0]
    for ch, cw in zip(text, widths):
        d.text((x, xy[1]), ch, font=font, fill=255)
        x += cw + tracking
    return arr(m)


def blur(a, r):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return arr(im.filter(ImageFilter.GaussianBlur(r))) / 255


def grow(a, px):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return arr(im.filter(ImageFilter.MaxFilter(px * 2 + 1))) / 255


def metal(mask, top, mid, low, bevel=7, horizon=0.56):
    """Polished metal fill: vertical 3-stop gradient with a dark 'horizon' band
    (the chrome-lettering trick) + a bevel lit from the top-left, computed from
    a height map (blurred alpha) — diffuse shading and a hard specular."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask > 0.5)
    y0, y1 = ys.min(), ys.max()
    t = np.clip((np.arange(h) - y0) / max(1, y1 - y0), 0, 1)[:, None, None]
    top, mid, low = (np.array(c, np.float32)[None, None] for c in (top, mid, low))
    col = np.where(t < horizon, top + (mid - top) * (t / horizon) ** 1.4,
                   low + (mid - low) * (1 - (t - horizon) / (1 - horizon)) ** 0.7)
    band = np.exp(-((t - horizon) ** 2) / 0.0012)
    col = col * (1 - 0.45 * band)
    hm = blur(mask, bevel)
    gy, gx = np.gradient(hm)
    nz = np.full_like(hm, 0.06)
    n = np.sqrt(gx ** 2 + gy ** 2 + nz ** 2)
    nx, ny, nz = -gx / n, -gy / n, nz / n
    L = np.array([-0.55, -0.65, 0.52])
    L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    spec = np.clip(diff, 0, 1) ** 24
    shade = 0.55 + 0.6 * diff
    out = col * shade[..., None] + 255 * spec[..., None] * 0.9
    return np.clip(out, 0, 255)


def layer(rgb, alpha):
    if np.ndim(rgb) == 1 or (isinstance(rgb, tuple)):
        rgb = np.broadcast_to(np.array(rgb, np.float32), alpha.shape + (3,))
    a = np.clip(alpha, 0, 1)[..., None] * 255
    return Image.fromarray(np.concatenate([rgb, a], 2).astype(np.uint8), 'RGBA')


def bolt_glyph(size, cx, top, bottom, width):
    """Classic zig-zag lightning glyph as a polygon."""
    m = Image.new('L', size, 0)
    hgt = bottom - top
    w = width
    pts = [
        (cx + 0.30 * w, top), (cx - 0.42 * w, top + 0.55 * hgt), (cx - 0.02 * w, top + 0.55 * hgt),
        (cx - 0.30 * w, bottom), (cx + 0.46 * w, top + 0.40 * hgt), (cx + 0.04 * w, top + 0.40 * hgt),
        (cx + 0.38 * w, top),
    ]
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return arr(m) / 255


def logo():
    """TESLA SPINS wordmark, rendered at 2x then halved.

    - TESLA: Rockwell Bold, polished copper-gold with a lit bevel, a thin hot
      inner rim, a heavy dark outline and a copper outer rim (slot-logo stack);
    - behind it a big neon lightning glyph cutting through the word;
    - SPINS: Copperplate Bold, neon-tube letters on a riveted steel plaque.
    """
    W, H = 1500, 760
    big = ImageFont.truetype(ROCKWELL, 330, index=2)
    small = ImageFont.truetype(COPPERPLATE, 128, index=2)

    tesla = text_mask((W, H), 'TESLA', big, (None, 60), tracking=6) / 255
    tesla = blur(tesla, 0.6)
    ys, xs = np.nonzero(tesla > 0.5)
    tx0, tx1, ty0, ty1 = xs.min(), xs.max(), ys.min(), ys.max()

    # SPINS plaque
    plate_h = 190
    plate_y = ty1 + 30
    spins = text_mask((W, H), 'SPINS', small, (None, plate_y + 30), tracking=46) / 255
    sys_, sxs = np.nonzero(spins > 0.5)
    px0, px1 = sxs.min() - 70, sxs.max() + 70
    plate = Image.new('L', (W, H), 0)
    ImageDraw.Draw(plate).rounded_rectangle((px0, plate_y, px1, plate_y + plate_h), radius=38, fill=255)
    plate = blur(arr(plate) / 255, 1.2)

    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    # 1. electric aura behind everything
    aura = blur(grow(tesla, 14), 40) * 0.9 + blur(plate, 30) * 0.5
    out = Image.alpha_composite(out, layer((40, 110, 255), np.clip(aura, 0, 0.85)))

    # 2. neon lightning glyph behind the word
    # two neon bolts flanking the SPINS plaque: ⚡ SPINS ⚡
    bh = plate_h * 1.45
    by = plate_y + plate_h / 2 - bh / 2
    bolt = np.maximum(bolt_glyph((W, H), px0 - 95, by, by + bh, 150),
                      bolt_glyph((W, H), px1 + 95, by, by + bh, 150))
    bolt = blur(bolt, 1.0)
    out = Image.alpha_composite(out, layer((60, 130, 255), np.clip(blur(grow(bolt, 10), 28) * 1.4, 0, 1)))
    out = Image.alpha_composite(out, layer((20, 40, 120), grow(bolt, 7)))
    bolt_col = np.zeros((H, W, 3), np.float32)
    yy = np.linspace(0, 1, H)[:, None]
    bolt_col[..., 0] = 150 + 105 * (1 - yy)
    bolt_col[..., 1] = 215 + 40 * (1 - yy)
    bolt_col[..., 2] = 255
    out = Image.alpha_composite(out, layer(bolt_col, bolt))
    core = blur(np.clip(bolt * (1 - blur(1 - bolt, 6) * 1.6), 0, 1), 2)
    out = Image.alpha_composite(out, layer((255, 255, 255), core * 0.9))

    # 3. plaque: dark steel, copper rim, rivets
    rim = grow(plate, 7)
    out = Image.alpha_composite(out, layer((25, 12, 6), grow(rim, 4)))
    out = Image.alpha_composite(out, layer(metal(rim, (255, 214, 150), (205, 120, 55), (110, 50, 20), bevel=4), rim))
    steel = metal(plate, (70, 84, 120), (36, 44, 70), (14, 18, 32), bevel=10, horizon=0.5)
    out = Image.alpha_composite(out, layer(steel, plate))
    rv = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(rv)
    for x in (px0 + 30, px1 - 30):
        for y in (plate_y + 34, plate_y + plate_h - 34):
            dr.ellipse((x - 11, y - 11, x + 11, y + 11), fill=255)
    rv = arr(rv) / 255
    out = Image.alpha_composite(out, layer(metal(rv, (255, 230, 180), (200, 130, 70), (90, 45, 20), bevel=4), rv))

    # 4. SPINS neon tubes
    out = Image.alpha_composite(out, layer((50, 130, 255), np.clip(blur(spins, 16) * 2.2, 0, 1)))
    out = Image.alpha_composite(out, layer((120, 195, 255), np.clip(blur(spins, 5) * 1.6, 0, 1)))
    inner = np.clip(spins - grow(1 - spins, 3), 0, 1)
    out = Image.alpha_composite(out, layer((235, 248, 255), spins))
    out = Image.alpha_composite(out, layer((255, 255, 255), blur(inner, 1.5)))

    # 5. TESLA metal stack
    outer = grow(tesla, 16)
    out = Image.alpha_composite(out, layer((0, 0, 0), blur(outer, 10) * 0.7))  # soft shadow
    out = Image.alpha_composite(out, layer(metal(outer, (255, 205, 140), (190, 105, 45), (90, 40, 15), bevel=5), outer))
    dark = grow(tesla, 10)
    out = Image.alpha_composite(out, layer((22, 10, 6), dark))
    hot = grow(tesla, 3)
    out = Image.alpha_composite(out, layer((255, 236, 190), hot))
    fill = metal(tesla, (255, 246, 205), (232, 160, 70), (120, 52, 18), bevel=9, horizon=0.55)
    out = Image.alpha_composite(out, layer(fill, tesla))

    # 6. a few baked electric arcs crawling over the letters
    rng = np.random.default_rng(3)
    arcs = Image.new('L', (W, H), 0)
    da = ImageDraw.Draw(arcs)
    for _ in range(5):
        x0 = rng.uniform(tx0, tx1)
        y0 = rng.uniform(ty0, ty1)
        pts = [(x0, y0)]
        for _ in range(8):
            x0 += rng.uniform(10, 34) * rng.choice([-1, 1])
            y0 += rng.uniform(-22, 22)
            pts.append((x0, y0))
        da.line(pts, fill=255, width=3)
    arcs = arr(arcs) / 255 * grow(tesla, 18)
    out = Image.alpha_composite(out, layer((90, 160, 255), np.clip(blur(arcs, 6) * 2.5, 0, 1)))
    out = Image.alpha_composite(out, layer((235, 245, 255), blur(arcs, 0.8)))

    out = out.crop(out.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox())
    return out.resize((out.width * 3 // 4, out.height * 3 // 4), Image.LANCZOS)


# ---- Hold & Win coins ----------------------------------------------------------
#
# Drawn from scratch with the same metal() shader as the logo, so the whole set
# shares one light direction. The base-game coin stays the lightning coin cut
# from the reference (symbols/coin.png); these are the LOCKED faces:
#   coins/face.png          copper coin with an empty engraved field — the
#                           client prints the multiplier (x5) on it;
#   coins/mini|minor|major  jackpot coins in their tier colour, label baked.

TIERS = {
    # rim light / mid / dark, face light / dark, label glow
    'face': ((255, 214, 150), (200, 118, 52), (96, 44, 16), (150, 82, 40), (52, 24, 10), None),
    'mini': ((200, 255, 225), (40, 190, 140), (8, 70, 52), (30, 110, 85), (6, 34, 28), (80, 255, 190)),
    'minor': ((205, 230, 255), (60, 140, 255), (12, 40, 120), (34, 76, 160), (8, 18, 52), (110, 180, 255)),
    'major': ((255, 210, 255), (200, 70, 230), (70, 10, 90), (110, 40, 140), (34, 8, 46), (240, 120, 255)),
    'grand': ((255, 240, 180), (240, 170, 40), (110, 50, 6), (170, 90, 20), (60, 26, 4), (255, 200, 80)),
}


def coin_img(tier, label=None, size=440):
    rim_l, rim_m, rim_d, face_l, face_d, glow = TIERS[tier]
    S = size
    yy, xx = np.mgrid[0:S, 0:S]
    c = (S - 1) / 2
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (S / 2)
    disc = np.clip((0.96 - r) * S / 3, 0, 1)
    face = np.clip((0.76 - r) * S / 3, 0, 1)
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    # dark outline + rim metal
    out = Image.alpha_composite(out, layer((18, 10, 6), np.clip((1.0 - r) * S / 3, 0, 1)))
    out = Image.alpha_composite(out, layer(metal(disc, rim_l, rim_m, rim_d, bevel=10, horizon=0.5), disc))
    # rivets on the rim
    rv = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(rv)
    for k in range(12):
        a = 2 * np.pi * k / 12
        x, y = c + np.cos(a) * S * 0.43, c + np.sin(a) * S * 0.43
        d.ellipse((x - S * 0.022, y - S * 0.022, x + S * 0.022, y + S * 0.022), fill=255)
    rv = arr(rv) / 255
    out = Image.alpha_composite(out, layer(metal(rv, (255, 250, 230), rim_m, rim_d, bevel=3), rv))
    # recessed face: inner shadow ring + dark radial metal
    out = Image.alpha_composite(out, layer((10, 6, 4), np.clip((0.8 - r) * S / 3, 0, 1)))
    t = np.clip(r / 0.76, 0, 1)[..., None]
    fl, fd = np.array(face_l, np.float32), np.array(face_d, np.float32)
    face_col = fl * (1 - t) + fd * t
    # brushed concentric grooves
    grooves = 0.9 + 0.1 * np.sin(r * S * 0.9)
    face_col = face_col * grooves[..., None]
    # light from top-left on the dish
    lit = np.clip(1.15 - 0.5 * ((xx - c * 0.7) ** 2 + (yy - c * 0.6) ** 2) / (S * S * 0.25), 0.6, 1.2)
    face_col = np.clip(face_col * lit[..., None], 0, 255)
    out = Image.alpha_composite(out, layer(face_col, face))
    # faint engraved bolt watermark on the plain face
    if tier == 'face':
        bolt = bolt_glyph((S, S), c, S * 0.2, S * 0.8, S * 0.42)
        out = Image.alpha_composite(out, layer((0, 0, 0), np.clip(bolt * face, 0, 1) * 0.28))
        out = Image.alpha_composite(out, layer((255, 200, 140), np.clip((bolt - np.roll(bolt, 3, 0)) * face, 0, 1) * 0.25))
    if label:
        font = ImageFont.truetype(ROCKWELL, int(S * (0.22 if len(label) <= 4 else 0.165)), index=2)
        m = text_mask((S, S), label, font, (None, S * 0.5 - S * 0.16), tracking=2) / 255
        ys, xs = np.nonzero(m > 0.5)
        dy = int(c - (ys.min() + ys.max()) / 2)
        m = np.roll(m, dy, 0)
        out = Image.alpha_composite(out, layer(glow, np.clip(blur(m, 14) * 2.0, 0, 1)))
        out = Image.alpha_composite(out, layer((14, 8, 6), grow(m, 5)))
        out = Image.alpha_composite(out, layer(metal(m, (255, 255, 245), glow, tuple(int(v * 0.45) for v in glow), bevel=4), m))
    # specular glint top-left of the rim
    glint = np.exp(-(((xx - c * 0.55) ** 2 + (yy - c * 0.45) ** 2) / (S * S * 0.004)))
    out = Image.alpha_composite(out, layer((255, 255, 255), np.clip(glint * disc * 0.6, 0, 1)))
    return out


def build_coins():
    os.makedirs(os.path.join(ROOT, 'coins'), exist_ok=True)
    coin_img('face').save(os.path.join(ROOT, 'coins', 'face.png'), optimize=True)
    for tier in ('mini', 'minor', 'major', 'grand'):
        coin_img(tier, tier.upper()).save(os.path.join(ROOT, 'coins', f'{tier}.png'), optimize=True)


SKY = 260  # px of sky added above the picture (room for the logo / portrait)


def extend_top(scene):
    """Grow the picture upward: the top rows (night sky + the tops of the two
    pipes) are stretched and blurred into a 260px band, then darkened towards
    the top so the extension reads as distance, not as a smeared copy."""
    band = scene.crop((0, 0, scene.width, 24)).resize((scene.width, SKY + 24), Image.BICUBIC)
    band = band.filter(ImageFilter.GaussianBlur(10))
    a = arr(band)
    yy = np.linspace(0, 1, a.shape[0])[:, None, None]
    a *= 0.35 + 0.65 * yy ** 1.4
    band = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    out = Image.new('RGB', (scene.width, scene.height + SKY))
    out.paste(band, (0, 0))
    # feathered seam
    m = Image.new('L', (scene.width, scene.height), 255)
    ImageDraw.Draw(m).rectangle((0, 0, scene.width, 14), fill=0)
    m = m.filter(ImageFilter.GaussianBlur(8))
    out.paste(scene, (0, SKY), m)
    return out


def coil_sprite(scene, box, flip=False):
    """One Tesla coil cut out with a soft vignette (portrait layout sets the
    coils on the cabinet's shoulders instead of beside it)."""
    c = scene.crop(box).convert('RGBA')
    w, h = c.size
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - w / 2) / (w / 2)
    ny = (yy - h * 0.42) / (h * 0.6)
    m = np.clip((1.05 - np.sqrt(nx ** 2 + ny ** 2)) * 3, 0, 1) ** 1.4
    c.putalpha(Image.fromarray((m * 255).astype(np.uint8)))
    return c.transpose(Image.FLIP_LEFT_RIGHT) if flip else c


def cover(ref, logo_im):
    w, h = 900, 470
    src = extend_top(ref).crop((0, SKY - 120, ref.width, SKY + ref.height))
    sc = src.resize((int(src.width * h / src.height), h), Image.LANCZOS)
    x = (sc.width - w) // 2
    out = sc.crop((x, 0, x + w, h)).convert('RGBA')
    lg = logo_im.copy()
    lg.thumbnail((300, 92), Image.LANCZOS)
    out.alpha_composite(lg, ((w - lg.width) // 2, 2))
    return out.convert('RGB')


def main():
    ref = Image.open(SRC).convert('RGB')
    os.makedirs(os.path.join(ROOT, 'img'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'symbols'), exist_ok=True)

    template = clean_cell(ref)
    scene = empty_scene(ref, template)
    scene.save(os.path.join(ROOT, 'img', 'scene.jpg'), quality=92)

    front, box = front_layer(scene)
    front.save(os.path.join(ROOT, 'img', 'cabinet.png'), optimize=True)
    print('cabinet box', box, front.size)

    panel_tile(template).save(os.path.join(ROOT, 'img', 'cell.jpg'), quality=92)

    for r in range(3):
        for c in range(3):
            code = LAYOUT[r][c]
            im = cut_symbol(ref, template, r, c)
            im.save(os.path.join(ROOT, 'symbols', f'{code}.png'), optimize=True)
            print(code, im.size)

    lg = logo()
    lg.save(os.path.join(ROOT, 'img', 'logo.png'), optimize=True)
    print('logo', lg.size)

    ext = extend_top(scene)
    ext.save(os.path.join(ROOT, 'img', 'scene_ext.jpg'), quality=90)
    print('scene_ext', ext.size)
    coil_sprite(scene, (60, 0, 330, 520)).save(os.path.join(ROOT, 'img', 'coil_l.png'), optimize=True)
    coil_sprite(scene, (950, 0, 1220, 520)).save(os.path.join(ROOT, 'img', 'coil_r.png'), optimize=True)
    build_coins()
    cover(ref, lg).save(os.path.join(ROOT, 'img', 'cover.jpg'), quality=88)


if __name__ == '__main__':
    main()
