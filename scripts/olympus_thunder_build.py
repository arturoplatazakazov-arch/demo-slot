"""Olympus Thunder: cut the ChatGPT (gpt-image) sheets into game assets.

Sources: front/img/olympus-thunder/src/<job>.(png|webp) (gitignored) — the
prompts are kept in scripts/olympus_thunder_gen.py. Output: the flat assets
the page uses directly (symbols, backgrounds, UI) under
front/img/olympus-thunder/, and the cut parts the Spine generator
(scripts/olympus_thunder_spine.py) rigs, under .../parts/.

    <venv with numpy, pillow, opencv-python-headless, scipy> \
        python scripts/olympus_thunder_build.py [step ...]   # default: all

Sheets are split by connected components of the alpha channel (pieces were
prompted "fully separate"), then read in rows top-to-bottom, left-to-right.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "front/img/olympus-thunder/src"
OUT = ROOT / "front/img/olympus-thunder"
PARTS = OUT / "parts"

SYMBOL_BOX = 256  # every symbol tile is a square PNG of this size


def load(name: str) -> Image.Image:
    for ext in ("png", "webp"):
        p = SRC / f"{name}.{ext}"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(name)


def save(im: Image.Image, rel: str, **kw) -> Path:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".webp":
        im.save(path, "WEBP", quality=kw.get("quality", 90), method=6)
    elif path.suffix == ".jpg":
        im.convert("RGB").save(path, "JPEG", quality=kw.get("quality", 88), optimize=True, progressive=True)
    else:
        im.save(path, optimize=True)
    print(f"  {rel:42s} {im.size[0]}x{im.size[1]}")
    return path


def alpha(im: Image.Image) -> np.ndarray:
    return np.asarray(im)[:, :, 3]


def pieces(im: Image.Image, min_area: int = 2500, thr: int = 12, join: int = 9) -> list[tuple[int, int, int, int]]:
    """Bounding boxes of the separate objects on a transparent sheet. Faint
    glow / stray specks are bridged by a small dilation (`join`) so one object
    with a detached spark still comes out as one piece; tiny islands are
    dropped. Ordered in reading order (rows by vertical overlap)."""
    mask = alpha(im) > thr
    grown = ndimage.binary_dilation(mask, iterations=join)
    labels, n = ndimage.label(grown)
    boxes = []
    for sl in ndimage.find_objects(labels):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        if mask[y0:y1, x0:x1].sum() < min_area:
            continue
        boxes.append((x0, y0, x1, y1))
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    rows: list[list] = []
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        if rows and abs(cy - rows[-1][0]) < (b[3] - b[1]) * 0.45:
            rows[-1][1].append(b)
        else:
            rows.append([cy, [b]])
    return [b for _, row in rows for b in sorted(row, key=lambda b: b[0])]


def crop(im: Image.Image, box, pad: int = 0, thr: int = 12, join: int = 9) -> Image.Image:
    """Crop and keep ONLY the main connected object inside the box (removes
    bits of a neighbour that reach into the rectangle)."""
    x0, y0, x1, y1 = box
    c = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))
    a = np.asarray(c)[:, :, 3]
    grown = ndimage.binary_dilation(a > thr, iterations=join)
    labels, n = ndimage.label(grown)
    if n > 1:
        sizes = ndimage.sum(a > thr, labels, range(1, n + 1))
        keep = labels == (int(np.argmax(sizes)) + 1)
        arr = np.asarray(c).copy()
        arr[:, :, 3] = np.where(keep, arr[:, :, 3], 0)
        c = Image.fromarray(arr)
    return trim(c)


def trim(im: Image.Image, thr: int = 6) -> Image.Image:
    a = alpha(im)
    ys, xs = np.where(a > thr)
    if not len(xs):
        return im
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def clean_alpha(im: Image.Image, floor: int = 8) -> Image.Image:
    """Kill the near-invisible haze gpt-image leaves around cut-outs (webp
    re-encoding makes it worse): alpha below `floor` -> 0."""
    arr = np.asarray(im).copy()
    a = arr[:, :, 3]
    arr[:, :, 3] = np.where(a < floor, 0, a)
    return Image.fromarray(arr)


def centroid(im: Image.Image) -> tuple[float, float]:
    a = alpha(im).astype(np.float64)
    total = a.sum() or 1
    ys, xs = np.indices(a.shape)
    return float((xs * a).sum() / total), float((ys * a).sum() / total)


def tile(im: Image.Image, fill: float, box: int = SYMBOL_BOX, optical: float = 0.6) -> Image.Image:
    """Fit a cut object into a square symbol tile: longest side = fill*box,
    centred between its bbox centre and its alpha centroid (thin spikes such
    as a crest or a bolt tip shouldn't drag the solid mass off-centre)."""
    im = trim(clean_alpha(im))
    scale = fill * box / max(im.size)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    cx, cy = centroid(im)
    dx = (im.width / 2 - cx) * optical
    dy = (im.height / 2 - cy) * optical
    out = Image.new("RGBA", (box, box))
    x = round((box - im.width) / 2 + dx)
    y = round((box - im.height) / 2 + dy)
    x = min(max(x, 0), box - im.width)
    y = min(max(y, 0), box - im.height)
    out.alpha_composite(im, (x, y))
    return out


def sheet(name: str, count: int, **kw) -> list[Image.Image]:
    im = load(name)
    boxes = pieces(im, **kw)
    if len(boxes) != count:
        raise SystemExit(f"{name}: expected {count} pieces, found {len(boxes)}: {boxes}")
    return [crop(im, b, thr=kw.get("thr", 12), join=kw.get("join", 9)) for b in boxes]


def unchecker(im: Image.Image, sat: float = 0.13, light: int = 165) -> Image.Image:
    """ChatGPT sometimes PAINTS a transparency checkerboard instead of
    returning alpha. Key it out: near-grey light pixels connected to the
    image border become transparent; a 1px feather softens the cut."""
    arr = np.asarray(im.convert("RGB")).astype(np.int16)
    mx, mn = arr.max(axis=2), arr.min(axis=2)
    greyish = ((mx - mn) <= sat * 255) & (mn >= light)
    labels, _ = ndimage.label(greyish)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    bg = np.isin(labels, list(border))
    bg = ndimage.binary_dilation(bg, iterations=1)
    a = np.where(bg, 0, 255).astype(np.uint8)
    a = np.asarray(Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8)))
    out = np.dstack([arr.astype(np.uint8), a])
    return Image.fromarray(out, "RGBA")


def luma_key(im: Image.Image) -> Image.Image:
    """FX painted on black -> straight-alpha RGBA (alpha = brightness,
    colour un-premultiplied), so it can be drawn additively or normally."""
    arr = np.asarray(im.convert("RGB")).astype(np.float32)
    a = arr.max(axis=2)
    a = np.clip((a - 10) * 255 / 245, 0, 255)
    safe = np.maximum(a, 1)[..., None] / 255
    rgb = np.clip(arr / safe, 0, 255)
    return Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")


def magenta_hole(im: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Plates were painted with a FLAT MAGENTA panel: cut it out (dilated so
    the anti-aliased pink rim goes too) and return the panel's box."""
    arr = np.asarray(im).copy()
    r, g, b = (arr[:, :, i].astype(np.int16) for i in range(3))
    pink = (r > 200) & (b > 190) & (g < 90) & (abs(r - b) < 45) & (arr[:, :, 3] > 100)
    pink = ndimage.binary_fill_holes(pink)
    pink = ndimage.binary_dilation(pink, iterations=4)
    arr[:, :, 3] = np.where(pink, 0, arr[:, :, 3])
    ys, xs = np.where(pink)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else (0, 0, 0, 0)
    return Image.fromarray(arr), box


# -- steps ---------------------------------------------------------------------

HIGH = ["helmet", "lyre", "amphora", "wreath"]
GEMS = ["ruby", "amethyst", "emerald", "sapphire", "citrine"]


# Each rare gets its own enamel colour on the shared medallion (product asked
# for rares that differ by colour): hue (deg), saturation and value scales
# for the painted navy field + its lightning veins. Gold/bronze untouched.
RARE_SHEET_COLOURED = True

RARE_ENAMEL = {
    "helmet": (352, 1.15, 1.25),   # crimson
    "lyre": (178, 1.05, 1.25),     # deep teal
    "amphora": (272, 1.1, 1.3),    # royal purple
    "wreath": (222, 1.0, 1.0),     # keep the storm-navy
}


def enamel(im: Image.Image, hue: float, sat: float, val: float) -> Image.Image:
    """Re-hue the blue enamel of a medallion symbol, keeping its shading."""
    rgba = np.asarray(im).astype(np.float32) / 255
    import colorsys  # noqa: F401  (documented choice: vectorised below)
    r, g, b = rgba[..., 0], rgba[..., 1], rgba[..., 2]
    mx, mn = rgba[..., :3].max(axis=2), rgba[..., :3].min(axis=2)
    d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s_ = d / (mx + 1e-6)
    blue = (h > 195) & (h < 255) & (s_ > 0.22) & (rgba[..., 3] > 0.05)
    blue = ndimage.binary_dilation(ndimage.binary_opening(blue, iterations=1), iterations=1)
    v = np.clip(mx * val, 0, 1)
    ss = np.clip(s_ * sat, 0, 1)
    hh = np.full_like(h, hue % 360) / 60
    i = np.floor(hh).astype(int) % 6
    f = hh - np.floor(hh)
    p_, q, t = v * (1 - ss), v * (1 - ss * f), v * (1 - ss * (1 - f))
    nr = np.choose(i, [v, q, p_, p_, t, v])
    ng = np.choose(i, [t, v, v, q, p_, p_])
    nb = np.choose(i, [p_, p_, t, v, v, q])
    out = rgba.copy()
    soft = ndimage.gaussian_filter(blue.astype(np.float32), 0.8)[..., None]
    out[..., :3] = rgba[..., :3] * (1 - soft) + np.stack([nr, ng, nb], -1) * soft
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def step_symbols() -> None:
    print("symbols")
    # rares on medallions touch each other on the sheet -> cut by quadrant
    src = load("sym_high")
    if alpha(src).min() == 255:  # painted checkerboard instead of alpha
        src = unchecker(src)
    hw, hh = src.width // 2, src.height // 2
    quads = [(0, 0), (hw, 0), (0, hh), (hw, hh)]
    for code, (qx, qy) in zip(HIGH, quads):
        q = src.crop((qx, qy, qx + hw, qy + hh))
        t_ = tile(crop(q, (0, 0, hw, hh), thr=40, join=2), 0.96)
        # the current sheet paints each rare in its own enamel colour; the
        # re-hue below was the stop-gap for the earlier all-navy sheet
        save(t_ if RARE_SHEET_COLOURED else enamel(t_, *RARE_ENAMEL[code]), f"symbols/{code}.webp")
    for code, im in zip(GEMS, sheet("sym_gems", 5)):
        # commons read smaller than rares on purpose (tier at a glance)
        save(tile(im, 0.74), f"symbols/{code}.webp")
    scatter, eagle, orb = sheet("sym_special", 3, join=1, thr=60)
    save(tile(scatter, 0.92), "symbols/scatter.webp")
    save(tile(eagle, 0.98), "symbols/eagle.webp")
    save(tile(orb, 0.86), "symbols/orb.webp")


def step_logo() -> None:
    print("logo")
    im = trim(clean_alpha(load("logo")))
    im.thumbnail((1100, 1100), Image.LANCZOS)
    save(im, "logo.webp")


def step_ui() -> None:
    import json
    print("ui")
    names = ["jp_mini", "jp_minor", "jp_major", "jp_grand", "plate_win", "medallion", "buy_button"]
    plates = sheet("ui_plates", 7, thr=40, join=3)
    holes = {}
    for name, im in zip(names, plates):
        im, box = magenta_hole(im)
        im.thumbnail((720, 720), Image.LANCZOS) if name == "plate_win" else im.thumbnail((440, 440), Image.LANCZOS)
        # re-measure the hole at the saved size
        _, box = magenta_hole(Image.fromarray(np.asarray(im)))
        a = alpha(im)
        hole = np.zeros_like(a, bool)
        # transparent pixels enclosed by the plate = the hole
        filled = ndimage.binary_fill_holes(a > 40)
        hole = filled & (a <= 40)
        ys, xs = np.where(hole)
        if len(xs):
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        holes[name] = {"w": im.width, "h": im.height, "hole": box}
        save(im, f"ui/{name}.webp")
    (OUT / "ui/holes.json").write_text(json.dumps(holes, indent=1))
    print("  holes", holes)


def step_titles() -> None:
    print("titles")
    im = unchecker(load("titles"))
    names = ["big_win", "mega_win", "epic_win", "free_spins", "super_free_spins", "jackpot"]
    # the six lines sit too close for components (glows touch): split at the
    # five emptiest rows of the solid-letter projection instead
    prof = (alpha(im) > 200).sum(axis=1).astype(float)
    prof = np.convolve(prof, np.ones(9) / 9, mode="same")
    band = im.height / 6
    cuts = [0]
    for k in range(1, 6):
        lo, hi = int(band * k - band * 0.35), int(band * k + band * 0.35)
        cuts.append(lo + int(np.argmin(prof[lo:hi])))
    cuts.append(im.height)
    lines = []
    for y0, y1 in zip(cuts, cuts[1:]):
        band_im = im.crop((0, y0, im.width, y1))
        arr = np.asarray(band_im).copy()
        rgb = arr[:, :, :3].astype(np.int16)
        # letters = saturated gold; anything farther than ~16px from them is
        # leftover checker/glow of the neighbouring line
        gold = (rgb[:, :, 0] > 150) & (rgb[:, :, 0] - rgb[:, :, 2] > 70) & (arr[:, :, 3] > 200)
        near = ndimage.binary_dilation(gold, iterations=16)
        arr[:, :, 3] = np.where(near, arr[:, :, 3], 0)
        band_im = Image.fromarray(arr)
        lines.append(crop(band_im, (0, 0, band_im.width, band_im.height), thr=60, join=40))
    def main_run(piece: Image.Image) -> Image.Image:
        # drop slivers of a neighbouring line: keep the contiguous band of
        # rows around the densest one
        arr = np.asarray(piece).astype(np.int16)
        gold = (arr[:, :, 0] > 150) & (arr[:, :, 0] - arr[:, :, 2] > 70) & (arr[:, :, 3] > 200)
        prof = gold.sum(axis=1)
        filled = prof > prof.max() * 0.06
        y = int(np.argmax(prof))
        y0 = y
        while y0 > 0 and filled[y0 - 1]:
            y0 -= 1
        y1 = y
        while y1 < len(prof) - 1 and filled[y1 + 1]:
            y1 += 1
        return trim(piece.crop((0, max(0, y0 - 10), piece.width, min(piece.height, y1 + 8))))

    lines = [main_run(p_) for p_ in lines]
    for name, piece in zip(names, lines):
        piece.thumbnail((1100, 400), Image.LANCZOS)
        save(piece, f"titles/{name}.webp")


def step_cards() -> None:
    print("buy cards")
    im = unchecker(load("buy_cards"))
    boxes = sorted(pieces(im, thr=60, join=3), key=lambda b: b[0])
    cards = [crop(im, b, thr=60, join=3) for b in boxes]
    for name, piece in zip(["free_spins", "super_free_spins", "jackpot_chance"], cards):
        piece.thumbnail((480, 720), Image.LANCZOS)
        save(piece, f"ui/card_{name}.webp")


def step_wheel() -> None:
    print("wheel")
    w = trim(clean_alpha(load("wheel")))
    w = w.resize((900, round(900 * w.height / w.width)), Image.LANCZOS)
    save(w, "wheel/wheel.webp")
    p = trim(clean_alpha(load("wheel_pointer")))
    p.thumbnail((260, 260), Image.LANCZOS)
    save(p, "wheel/pointer.webp")


def step_orb() -> None:
    print("orb parts")
    for name, piece in zip(["sphere", "arcs", "ring"], sheet("orb_parts", 3, thr=30, join=4)):
        piece.thumbnail((360, 360), Image.LANCZOS)
        piece.save(PARTS / f"orb_{name}.png") if PARTS.exists() else None
        PARTS.mkdir(parents=True, exist_ok=True)
        piece.save(PARTS / f"orb_{name}.png")
        print(f"  parts/orb_{name}.png {piece.size}")


def step_bolts() -> None:
    print("bolts")
    im = luma_key(load("fx_bolts"))
    PARTS.mkdir(parents=True, exist_ok=True)
    for i, piece in enumerate(sheet_from(im, 6, thr=40, join=6)):
        piece.thumbnail((300, 820), Image.LANCZOS)
        piece.save(PARTS / f"bolt_{i}.png")
        print(f"  parts/bolt_{i}.png {piece.size}")


def black_key(im: Image.Image, dark: int = 22) -> Image.Image:
    """Solid object painted on black: near-black pixels connected to the
    border become transparent (dark detail INSIDE the object survives)."""
    arr = np.asarray(im.convert("RGB"))
    near_black = arr.max(axis=2) <= dark
    labels, _ = ndimage.label(near_black)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    bg = np.isin(labels, list(border))
    a = np.where(bg, 0, 255).astype(np.uint8)
    a = np.asarray(Image.fromarray(a).filter(ImageFilter.GaussianBlur(1.0)))
    return Image.fromarray(np.dstack([arr, a]))


def step_fx() -> None:
    print("fx sheet")
    src = load("fx_sheet")
    glow = luma_key(src)
    solid = black_key(src)
    names = ["burst", "coin", "coin_edge", "sparkle", "ring", "debris", "leaf", "streak"]
    boxes = pieces(glow, thr=40, join=10, min_area=1500)
    if len(boxes) != 8:
        raise SystemExit(f"fx_sheet: expected 8, found {len(boxes)} {boxes}")
    PARTS.mkdir(parents=True, exist_ok=True)
    for name, b in zip(names, boxes):
        layer = solid if name in ("coin", "coin_edge", "debris", "leaf") else glow
        piece = crop(layer, b, pad=6, thr=30, join=10)
        piece.thumbnail((300, 300), Image.LANCZOS)
        piece.save(PARTS / f"fx_{name}.png")
        print(f"  parts/fx_{name}.png {piece.size}")


def step_bg() -> None:
    """Sky plates (opaque, JPEG) + the temple layer (alpha, WebP)."""
    print("backgrounds")
    def sky(name, out, width):
        im = load(name).convert("RGB")
        im = im.resize((width, round(width * im.height / im.width)), Image.LANCZOS)
        save(im, out, quality=86)
    try:
        sky("bg_sky", "bg/sky.jpg", 1920)
    except FileNotFoundError:
        # stand-in until the base desktop plate arrives: the FS plate pulled
        # back into storm navy (luminance kept, colour from a navy->gold map)
        im = load("bg_sky_fs").convert("RGB")
        g = np.asarray(im.convert("L")).astype(np.float32) / 255
        lo, mid, hi = np.array([11, 16, 38]), np.array([46, 66, 112]), np.array([255, 214, 140])
        rgb = np.where(g[..., None] < 0.55, lo + (mid - lo) * (g[..., None] / 0.55),
                       mid + (hi - mid) * np.maximum((g[..., None] - 0.55) / 0.45, 0) ** 1.6)
        im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
        im = im.resize((1920, 1280), Image.LANCZOS)
        save(im, "bg/sky.jpg", quality=86)
    sky("bg_sky_fs", "bg/sky_fs.jpg", 1920)
    sky("bg_sky_mob", "bg/sky_mob.jpg", 1152)
    sky("bg_sky_fs_mob", "bg/sky_fs_mob.jpg", 1152)
    for name, out in (("bg_temple", "bg/temple.webp"), ("bg_temple_mob", "bg/temple_mob.webp")):
        im = clean_alpha(load(name))
        im = im.resize((1920, round(1920 * im.height / im.width)) if im.width > im.height else (1152, round(1152 * im.height / im.width)), Image.LANCZOS)
        save(im, out, quality=88)
    cov = load("cover").convert("RGB").resize((720, 720), Image.LANCZOS)
    save(cov, "cover.jpg", quality=86)


def step_clouds() -> None:
    print("clouds")
    PARTS.mkdir(parents=True, exist_ok=True)
    for i, piece in enumerate(sheet("clouds", 6, thr=30, join=8)):
        piece.thumbnail((900, 500), Image.LANCZOS)
        piece.save(PARTS / f"cloud_{i}.png")
        print(f"  parts/cloud_{i}.png {piece.size}")


def _period(strip: np.ndarray, lo: int, hi: int) -> int:
    """Repeat length of a pattern along axis 1 (autocorrelation peak)."""
    x = strip - strip.mean()
    best, best_p = -1e9, lo
    for p in range(lo, min(hi, x.shape[1] // 2)):
        c = (x[:, :-p] * x[:, p:]).mean()
        if c > best:
            best, best_p = c, p
    return best_p


def _tile(seg: Image.Image, length: int) -> Image.Image:
    """Seamless band of `length` px from a horizontal segment: crop to whole
    meander periods, repeat, then resample the last few % to fit exactly."""
    g = np.asarray(seg.convert("L")).astype(np.float32)
    h = seg.height
    p = _period(g[int(h * .3):int(h * .7)], int(h * .35), int(h * 1.6))
    x0 = int(seg.width * 0.08)
    n = max(1, (seg.width - 2 * x0) // p)
    unit = seg.crop((x0, 0, x0 + n * p, h))
    reps = math.ceil(length / unit.width) + 1
    band = Image.new("RGBA", (unit.width * reps, h))
    for i in range(reps):
        band.paste(unit, (i * unit.width, 0))
    whole = round(length / p) * p or p
    band = band.crop((0, 0, whole, h))
    return band.resize((length, h), Image.LANCZOS)


def _frame(width: int, height: int, inset: int, band: int, margin: int, out: str) -> None:
    """Frame PNG of (board + 2*margin), its band's INNER edge exactly on the
    grid edge (board inset), corners + top palmette from the parts kit."""
    corner_l, horiz, vert, palm = sheet("frame_kit", 4, thr=40, join=4)
    s = band / horiz.height
    horiz = horiz.resize((round(horiz.width * s), band), Image.LANCZOS)
    vert = vert.resize((band, round(vert.height * band / vert.width)), Image.LANCZOS)
    W, H = width + 2 * margin, height + 2 * margin
    canvas = Image.new("RGBA", (W, H))
    gx0, gy0 = margin + inset, margin + inset                      # grid top-left
    gx1, gy1 = margin + width - inset, margin + height - inset     # grid bottom-right
    top = _tile(horiz, gx1 - gx0 + 2 * band)
    canvas.alpha_composite(top, (gx0 - band, gy0 - band))
    canvas.alpha_composite(top.transpose(Image.FLIP_TOP_BOTTOM), (gx0 - band, gy1))
    side = _tile(vert.rotate(90, expand=True), gy1 - gy0 + 2 * band).rotate(-90, expand=True)
    canvas.alpha_composite(side, (gx0 - band, gy0 - band))
    canvas.alpha_composite(side.transpose(Image.FLIP_LEFT_RIGHT), (gx1, gy0 - band))
    # corner block: the palmette end of the L piece, scaled with the band
    ca = alpha(corner_l) > 40
    # the arms' band thickness in the kit = rows where the far right column is opaque
    arm_rows = np.where(ca[:, -5])[0]
    arm_cols = np.where(ca[-5, :])[0]
    kit_band = (arm_rows.max() - arm_rows.min() + 1)
    cs = band / kit_band
    block_w = int(arm_cols.max() + 1 + kit_band * 0.15)
    block_h = int(arm_rows.max() + 1 + kit_band * 0.15)
    block = corner_l.crop((0, 0, min(corner_l.width, block_w), min(corner_l.height, block_h)))
    block = block.resize((round(block.width * cs), round(block.height * cs)), Image.LANCZOS)
    # where the arms' outer-left / outer-top edges sit inside the block
    ax, ay = round(arm_cols.min() * cs), round(arm_rows.min() * cs)
    bx, by = gx0 - band - ax, gy0 - band - ay
    for flip_h, flip_v in ((0, 0), (1, 0), (0, 1), (1, 1)):
        b = block
        x, y = bx, by
        if flip_h:
            b = b.transpose(Image.FLIP_LEFT_RIGHT)
            x = W - bx - b.width
        if flip_v:
            b = b.transpose(Image.FLIP_TOP_BOTTOM)
            y = H - by - b.height
        canvas.alpha_composite(b, (x, y))
    p = palm.resize((round(band * 2.6), round(band * 2.6 * palm.height / palm.width)), Image.LANCZOS)
    canvas.alpha_composite(p, ((W - p.width) // 2, gy0 - band - round(p.height * 0.62)))
    save(canvas, out)
    print(f"    grid window at ({gx0},{gy0})-({gx1},{gy1}) of {W}x{H}; css: inset -{margin}px")


def _frame2(width: int, height: int, inset: int, side: float, out: str) -> dict:
    """Frame from the second kit (src/frame_kit2: L-corner with a big
    palmette, meander bands). `side` = side band thickness in design px;
    the band inner edge sits on the grid (board inset). Returns the CSS box
    (offsets of the PNG relative to the board)."""
    im = load("frame_kit2")
    corner = crop(im, (20, 12, 565, 518), thr=60, join=3)
    horiz = crop(im, (615, 108, 1498, 281), thr=60, join=3)
    vert = crop(im, (363, 338, 521, 950), thr=60, join=3)
    k = side / 153                        # corner's vertical arm is 153 kit px
    bv, bh = 153 * k, 188 * k             # side / top band thickness
    corner = corner.resize((round(corner.width * k), round(corner.height * k)), Image.LANCZOS)
    horiz = horiz.resize((round(horiz.width * bh / horiz.height), round(bh)), Image.LANCZOS)
    vert = vert.resize((round(bv), round(vert.height * bv / vert.width)), Image.LANCZOS)
    ml, mt = round(bv + 50 * k) + 2, round(bh + 78 * k) + 2
    W, H = width + 2 * ml, height + 2 * mt
    gx0, gy0 = ml + inset, mt + inset
    gx1, gy1 = ml + width - inset, mt + height - inset
    can = Image.new("RGBA", (W, H))
    top = _tile(horiz, round(gx1 - gx0 + 2 * bv))
    can.alpha_composite(top, (round(gx0 - bv), round(gy0 - bh)))
    can.alpha_composite(top.transpose(Image.FLIP_TOP_BOTTOM), (round(gx0 - bv), gy1))
    sideb = _tile(vert.rotate(90, expand=True), round(gy1 - gy0 + 2 * bh)).rotate(-90, expand=True)
    can.alpha_composite(sideb, (round(gx0 - bv), round(gy0 - bh)))
    can.alpha_composite(sideb.transpose(Image.FLIP_LEFT_RIGHT), (gx1 + (round(bv) - sideb.width), round(gy0 - bh)))
    cx, cy = round(gx0 - bv - 50 * k), round(gy0 - bh - 78 * k)
    for fh, fv in ((0, 0), (1, 0), (0, 1), (1, 1)):
        c = corner
        x, y = cx, cy
        if fh:
            c = c.transpose(Image.FLIP_LEFT_RIGHT)
            x = W - cx - c.width
        if fv:
            c = c.transpose(Image.FLIP_TOP_BOTTOM)
            y = H - cy - c.height
        can.alpha_composite(c, (x, y))
    save(can, out)
    box = {"left": -ml, "top": -mt, "width": W, "height": H}
    print("    css box", box)
    return box


def step_frame() -> None:
    print("frame")
    _frame2(804, 678, 24, 46, "frame_desk.webp")
    _frame2(892, 752, 26, 50, "frame_mob.webp")


ZEUS_PARTS = {  # expected centre of each piece on the parts sheet (1536x1024)
    "head": (290, 190), "beard": (820, 260), "arm_r": (1170, 200), "bolt": (1450, 360),
    "torso": (330, 800), "arm_l": (740, 760), "cloak": (1180, 800),
}


def step_zeus() -> None:
    """Cut the Zeus parts sheet at native scale (the parts are mutually
    consistent; they do NOT line up with the separate full figure, so the
    pose is assembled from anatomy points in olympus_thunder_spine.py)."""
    print("zeus")
    sheet_im = load("zeus_parts")
    boxes = pieces(sheet_im, thr=40, join=6, min_area=4000)
    PARTS.mkdir(parents=True, exist_ok=True)
    for name, (ex, ey) in ZEUS_PARTS.items():
        b = min(boxes, key=lambda b: (ex - (b[0] + b[2]) / 2) ** 2 + (ey - (b[1] + b[3]) / 2) ** 2)
        im = crop(sheet_im, b, thr=40, join=6)
        im.save(PARTS / f"zeus_{name}.png")
        print(f"  parts/zeus_{name}.png {im.size}")
    load("zeus_full").save(PARTS / "zeus_full.png")


def sheet_from(im: Image.Image, count: int, **kw) -> list[Image.Image]:
    boxes = pieces(im, **kw)
    if len(boxes) != count:
        raise SystemExit(f"expected {count} pieces, found {len(boxes)}: {boxes}")
    return [crop(im, b, thr=kw.get("thr", 12), join=kw.get("join", 9)) for b in boxes]


STEPS = {
    "symbols": step_symbols, "logo": step_logo, "ui": step_ui, "titles": step_titles,
    "cards": step_cards, "wheel": step_wheel, "orb": step_orb, "bolts": step_bolts, "fx": step_fx,
    "bg": step_bg, "clouds": step_clouds, "frame": step_frame, "zeus": step_zeus,
}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(STEPS):
        STEPS[name]()
