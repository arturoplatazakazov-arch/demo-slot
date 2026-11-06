"""Olympus Thunder — cut a ChatGPT art set (scripts/chatgpt_art pipeline) into one design variant.

    OT_VAR=sunny <venv: numpy pillow scipy> python scripts/olympus_thunder_variants_art.py [job ...]

Input : front/img/olympus-thunder/<var>/src/*.png  (hp, lp, specials, hero, frame, bg_base, bg_bonus,
        bg_mob, bg_mob_bonus, logo, jackpots, wheel, titles, ui, cards, banner — prompts in
        scripts/chatgpt_art/prompts_olympus_thunder.md)
Output: front/img/olympus-thunder/<var>/ in the layout the shared JS expects (symbols/, titles/, ui/,
        wheel/, sky*.jpg, frame.webp, hero.webp, logo.webp) + cover.jpg + layout.json (frame geometry).

Jobs: symbols hero frame sky logo jackpots wheel titles ui cards cover (default: all).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
VAR = os.environ.get("OT_VAR") or sys.exit("set OT_VAR")
OUT = ROOT / "front/img/olympus-thunder" / VAR
SRC = OUT / "src"
ALPHA_FLOOR = int(os.environ.get("OT_ALPHA_FLOOR", "0"))
LAYOUT = OUT / "layout.json"


def load(name: str) -> Image.Image:
    im = Image.open(SRC / f"{name}.png").convert("RGBA")
    if ALPHA_FLOOR:
        a = np.array(im)
        al = a[..., 3].astype(np.float32)
        al = np.clip((al - ALPHA_FLOOR) / (255 - ALPHA_FLOOR), 0, 1) * 255
        a[..., 3] = al.astype(np.uint8)
        im = Image.fromarray(a)
    return im


def save(im: Image.Image, rel: str, q: int = 88) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if rel.endswith(".jpg"):
        im.convert("RGB").save(p, "JPEG", quality=q, optimize=True, progressive=True)
    else:
        im.save(p, "WEBP", quality=q, method=6)
    a = np.array(im.convert("RGBA"))[..., 3]
    print(f"  {rel:34s} {im.size[0]}x{im.size[1]}  corners a={a[0,0]},{a[0,-1]},{a[-1,0]},{a[-1,-1]}")


def pieces(im: Image.Image, n: int, rows: int | None = None, thr: int = 60, grow: int = 6):
    """The n largest alpha islands, in reading order (row bands, then x). Other islands are erased."""
    a = np.array(im)
    mask = a[..., 3] > thr
    lab, k = ndimage.label(ndimage.binary_dilation(mask, iterations=grow))
    sizes = ndimage.sum(mask, lab, range(1, k + 1))
    keep = np.argsort(sizes)[::-1][:n] + 1
    boxes = []
    for i in keep:
        ys, xs = np.where(lab == i)
        boxes.append((i, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    if rows:
        boxes.sort(key=lambda b: (b[2] + b[4]) / 2)
        per = math.ceil(n / rows)
        bands = [sorted(boxes[r * per:(r + 1) * per], key=lambda b: b[1]) for r in range(rows)]
        boxes = [b for band in bands for b in band]
    else:
        boxes.sort(key=lambda b: ((b[2] + b[4]) / 2 // (im.height / 8), b[1]))
    out = []
    for i, x0, y0, x1, y1 in boxes:
        sub = a[y0:y1, x0:x1].copy()
        sub[..., 3] = np.where(lab[y0:y1, x0:x1] == i, sub[..., 3], 0)
        out.append(Image.fromarray(sub))
    return out


def bands(im: Image.Image, n: int, thr: int = 110) -> list[Image.Image]:
    """Split a vertical stack into n rows at the n-1 deepest valleys of the row profile (plaques and
    glows touch, so islands merge), then keep the main island of each strip (drops a neighbour's tip)."""
    a = np.array(im)
    prof = ndimage.uniform_filter1d((a[..., 3] > thr).sum(1).astype(np.float32), 9)
    H = len(prof)
    gap = H / (2.5 * n)
    nz = np.where(prof > 0.5)[0]
    lo, hi = nz.min(), nz.max()
    cand = []  # (score, y): an empty run counts once, at its middle, deeper the longer it is
    y = lo
    while y < hi:
        if prof[y] <= 0.5:
            y0 = y
            while y < hi and prof[y] <= 0.5:
                y += 1
            cand.append((-(y - y0), (y0 + y) // 2))
        else:
            if prof[y] <= prof[y - 1] and prof[y] <= prof[y + 1]:
                cand.append((prof[y], y))
            y += 1
    order = [y for _, y in sorted(cand)]
    cuts = []
    for y in order:
        if all(abs(y - c) > gap for c in cuts):
            cuts.append(int(y))
        if len(cuts) == n - 1:
            break
    edges = [0] + sorted(cuts) + [H]
    out = []
    for i in range(n):
        strip = im.crop((0, edges[i], im.width, edges[i + 1]))
        out.append(trim(pieces(strip, 1, grow=2)[0]))
    return out


def trim(im: Image.Image, thr: int = 8) -> Image.Image:
    a = np.array(im)[..., 3]
    ys, xs = np.where(a > thr)
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def square(im: Image.Image, size: int, fill: float = 0.96) -> Image.Image:
    im = trim(im)
    s = size * fill / max(im.size)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    c = Image.new("RGBA", (size, size))
    c.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return c


def fit_w(im: Image.Image, w: int) -> Image.Image:
    im = trim(im)
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def cover_crop(im: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def dark_hole(im: Image.Image, right_half: bool = False) -> list[float]:
    """Bbox (% of the image) of the dark value window of a plate: the largest dark opaque island
    (right half only for jackpot plaques, whose left half carries the tier word)."""
    a = np.array(im).astype(np.float32)
    lum = a[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
    m = (lum < 70) & (a[..., 3] > 200)
    if right_half:
        m[:, : im.width * 2 // 5] = False
    m = ndimage.binary_opening(m, iterations=2)
    lab, k = ndimage.label(m)
    if not k:
        return [20.0, 30.0, 80.0, 70.0]
    i = int(np.argmax(ndimage.sum(m, lab, range(1, k + 1)))) + 1
    ys, xs = np.where(lab == i)
    W, H = im.size
    return [round(xs.min() / W * 100, 1), round(ys.min() / H * 100, 1),
            round((xs.max() + 1) / W * 100, 1), round((ys.max() + 1) / H * 100, 1)]


def hole_put(name: str, im: Image.Image, **kw) -> None:
    d = json.loads(LAYOUT.read_text()) if LAYOUT.exists() else {}
    d.setdefault("holes", {})[name] = dark_hole(im, **kw)
    d.setdefault("ratio", {})[name] = round(im.width / im.height, 3)
    LAYOUT.write_text(json.dumps(d, indent=1))


def layout_put(key: str, val) -> None:
    d = json.loads(LAYOUT.read_text()) if LAYOUT.exists() else {}
    d[key] = val
    LAYOUT.write_text(json.dumps(d, indent=1))


# ------------------------------------------------------------------ jobs
def job_symbols():
    for names, src, rows in (
        (["helmet", "lyre", "amphora", "wreath"], "hp", 2),
        (["ruby", "amethyst", "emerald", "sapphire", "citrine"], "lp", 2),
        (["scatter", "orb", "eagle"], "specials", 1),
    ):
        ps = pieces(load(src), len(names), rows)
        for name, p in zip(names, ps):
            save(square(p, 256, 0.98 if src == "hp" else 0.92), f"symbols/{name}.webp")


def job_hero():
    save(fit_w(load("hero"), 800), "hero.webp")


def hole_of(im: Image.Image):
    """Transparent window of the frame: the alpha-free island that holds the centre."""
    a = np.array(im)[..., 3]
    free = a < 40
    lab, _ = ndimage.label(free)
    c = lab[a.shape[0] // 2, a.shape[1] // 2]
    if not c:
        sys.exit("frame centre is not transparent")
    ys, xs = np.where(lab == c)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


BOARD_RATIO = 888 / 748  # .board box (6x5 cells of 140 + 24px pad), desktop and portrait alike


def stretch_quarters(im: Image.Image, a: int, b: int, new_len: int, axis: int) -> Image.Image:
    """Grow the span [a, b) along axis (1 = y) to new_len by stretching only its outer quarters
    (plain column/bar runs near the corners); the middle half, where side ornaments sit, keeps scale."""
    L = b - a
    q = L // 4
    grow = new_len - L
    parts = [(0, a, 0), (a, a + q, grow // 2), (a + q, b - q, 0), (b - q, b, grow - grow // 2), (b, im.size[axis], 0)]
    tiles = []
    for s, e, g in parts:
        if e <= s:
            continue
        box = (0, s, im.width, e) if axis else (s, 0, e, im.height)
        t = im.crop(box)
        if g:
            t = t.resize((t.width, t.height + g) if axis else (t.width + g, t.height), Image.LANCZOS)
        tiles.append(t)
    W = im.width if axis else sum(t.width for t in tiles)
    H = sum(t.height for t in tiles) if axis else im.height
    out, o = Image.new("RGBA", (W, H)), 0
    for t in tiles:
        out.alpha_composite(t, (0, o) if axis else (o, 0))
        o += t.height if axis else t.width
    return out


def job_frame():
    im = trim(load("frame"))
    x0, y0, x1, y1 = hole_of(im)
    r = (x1 - x0) / (y1 - y0)
    if r > BOARD_RATIO * 1.01:      # window too wide: make it taller
        im = stretch_quarters(im, y0, y1, round((x1 - x0) / BOARD_RATIO), 1)
    elif r < BOARD_RATIO * 0.99:    # too tall: make it wider
        im = stretch_quarters(im, x0, x1, round((y1 - y0) * BOARD_RATIO), 0)
    x0, y0, x1, y1 = hole_of(im)
    # Board = 6x5 grid + pad. The window art maps onto the board box; the frame image is placed with
    # % offsets so one image serves desktop (804x678) and portrait (868x732) boards.
    hw, hh = x1 - x0, y1 - y0
    geo = {
        "left": float(round(-x0 / hw * 100, 2)), "top": float(round(-y0 / hh * 100, 2)),
        "width": float(round(im.width / hw * 100, 2)), "height": float(round(im.height / hh * 100, 2)),
        "hole_ratio": float(round(hw / hh, 3)),
    }
    # remove stray opaque pixels inside the window (ChatGPT sometimes leaves a faint backdrop)
    a = np.array(im)
    lab, _ = ndimage.label(a[..., 3] < 40)
    win = np.zeros(a.shape[:2], bool)
    win[y0:y1, x0:x1] = True
    a[..., 3] = np.where(win & (a[..., 3] < 90), 0, a[..., 3])
    im = Image.fromarray(a)
    s = 1100 / im.width
    save(im.resize((1100, round(im.height * s)), Image.LANCZOS), "frame.webp")
    layout_put("frame", geo)
    print("  frame geo", geo)


def job_sky():
    for src, dst, size in (("bg_base", "sky.jpg", (1920, 1280)), ("bg_bonus", "sky_fs.jpg", (1920, 1280)),
                           ("bg_mob", "sky_mob.jpg", (1152, 1728)), ("bg_mob_bonus", "sky_fs_mob.jpg", (1152, 1728))):
        if (SRC / f"{src}.png").exists():
            save(cover_crop(load(src).convert("RGB"), *size), dst, 86)


def job_logo():
    save(fit_w(load("logo"), 1100), "logo.webp")


def job_jackpots():
    for name, p in zip(["grand", "major", "minor", "mini"], bands(load("jackpots"), 4)):
        p = fit_w(p, 520)
        save(p, f"ui/jp_{name}.webp")
        hole_put(f"jp_{name}", p, right_half=True)


TIER_RGB = {"mini": ((88, 190, 96), (30, 96, 44)), "minor": ((70, 140, 235), (22, 54, 128)),
            "major": ((158, 86, 226), (70, 28, 120)), "grand": ((232, 70, 58), (118, 18, 22))}
SECTORS = ["mini", "minor", "mini", "major", "mini", "mini", "grand", "minor", "mini", "minor", "mini", "major"]


def job_wheel():
    ps = pieces(load("wheel"), 3, 1)
    ps.sort(key=lambda p: -p.width * p.height)
    rim = ps[0]
    # hub = the round one (fills ~78% of its box), pointer = the arrow (fills much less)
    fill = lambda p: (np.array(trim(p))[..., 3] > 128).mean()
    hub, ptr = sorted(ps[1:], key=fill, reverse=True)
    S = 900
    rim = square(rim, S, 1.0)
    a = np.array(rim)[..., 3]
    # inner radius of the rim: first opaque ring pixel walking from the centre
    cy = cx = S // 2
    r_in = min(next((r for r in range(10, S // 2) if a[cy, cx + r] > 128), S // 3),
               next((r for r in range(10, S // 2) if a[cy - r, cx] > 128), S // 3))
    r_in += 6
    disc = Image.new("RGBA", (S, S))
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    ang = (np.degrees(np.arctan2(xx - cx, -(yy - cy))) + 360) % 360  # clockwise from 12 o'clock
    rad = np.hypot(xx - cx, yy - cy)
    idx = (ang // 30).astype(int) % 12
    rgb = np.zeros((S, S, 3), np.float32)
    t = np.clip(rad / r_in, 0, 1)[..., None]
    for i, tier in enumerate(SECTORS):
        hi, lo = (np.array(c, np.float32) for c in TIER_RGB[tier])
        m = idx == i
        rgb[m] = (lo + (hi - lo) * (0.35 + 0.65 * t))[m]  # dark hub -> bright rim
    # gold spokes
    spoke = np.abs(((ang + 15) % 30) - 15) * np.pi / 180 * rad < 3.2
    rgb[spoke] = (255, 210, 90)
    alpha = (rad < r_in + 4).astype(np.float32) * 255
    disc = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8))
    disc.alpha_composite(rim)
    hub = square(hub, round(S * 0.24), 1.0)
    disc.alpha_composite(hub, ((S - hub.width) // 2, (S - hub.height) // 2))
    save(disc, "wheel/wheel.webp")
    save(fit_w(ptr, 152), "wheel/pointer.webp")


def job_titles():
    names = ["big_win", "mega_win", "epic_win", "free_spins", "super_free_spins", "jackpot"]
    for name, p in zip(names, bands(load("titles"), 6)):
        save(fit_w(p, 1100), f"titles/{name}.webp")


def job_ui():
    ps = pieces(load("ui"), 3, 1)
    # the wide one is the win plate; of the two round ones, left = medallion, right = buy button
    plate = max(ps, key=lambda p: p.width / p.height)
    rest = [p for p in ps if p is not plate]
    for im, name, w in ((plate, "plate_win", 720), (rest[0], "medallion", 440), (rest[1], "buy_button", 424)):
        im = fit_w(im, w)
        save(im, f"ui/{name}.webp")
        hole_put(name, im)


def job_cards():
    for name, p in zip(["card_free_spins", "card_super_free_spins", "card_jackpot_chance"], pieces(load("cards"), 3, 1)):
        p = trim(p)
        save(p.resize((round(p.width * 720 / p.height), 720), Image.LANCZOS), f"ui/{name}.webp")


def job_cover():
    src = "banner" if (SRC / "banner.png").exists() else "bg_base"
    save(cover_crop(load(src).convert("RGB"), 960, 640), "cover.jpg", 86)


JOBS = {k[4:]: v for k, v in globals().items() if k.startswith("job_")}

if __name__ == "__main__":
    todo = sys.argv[1:] or list(JOBS)
    print(f"[{VAR}]")
    for j in todo:
        try:
            JOBS[j]()
        except FileNotFoundError as e:
            print(f"  skip {j}: {e.filename}")
