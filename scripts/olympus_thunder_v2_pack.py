"""Olympus Thunder v2 "Ascension": cut the hand-inked ChatGPT pack into the
variant's runtime art (front/img/olympus-thunder/v2/).

Sources: front/img/olympus-thunder/v2/src/<name>.webp (gitignored):
logo, frame, sky, sky_mob, sky_fs, sky_fs_mob, hero, sym_high, sym_low,
sym_special. Run with the scratch venv (numpy, pillow, scipy):

    python scripts/olympus_thunder_v2_pack.py [step ...]   # default: all
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from olympus_thunder_build import alpha, clean_alpha, crop, pieces, tile, trim  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "front/img/olympus-thunder/v2"
SRC = OUT / "src"
BOARD = (732, 616)  # desktop board rect in the v2 stylesheet (portrait is the same ratio)


def load(name: str) -> Image.Image:
    return Image.open(SRC / f"{name}.webp").convert("RGBA")


def save(im: Image.Image, rel: str, q: int = 90) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix == ".jpg":
        im.convert("RGB").save(p, "JPEG", quality=q, optimize=True, progressive=True)
    else:
        im.save(p, "WEBP", quality=q, alpha_quality=100, method=6)
    print(f"  v2/{rel} {im.size[0]}x{im.size[1]}")


def step_symbols() -> None:
    print("symbols")
    src = load("sym_high")
    hw, hh = src.width // 2, src.height // 2
    for code, (qx, qy) in zip(["helmet", "lyre", "amphora", "wreath"], [(0, 0), (hw, 0), (0, hh), (hw, hh)]):
        q = src.crop((qx, qy, qx + hw, qy + hh))
        save(tile(crop(q, (0, 0, hw, hh), thr=40, join=3), 0.96), f"symbols/{code}.webp")
    # Greek-letter tokens, by colour onto the five low codes:
    # A blue, B crimson, Γ green, Δ orange, Ω purple
    low = load("sym_low")
    order = ["sapphire", "ruby", "emerald", "citrine", "amethyst"]
    boxes = pieces(low, thr=40, join=4)
    assert len(boxes) == 5, boxes
    for code, b in zip(order, boxes):
        save(tile(crop(low, b, thr=40, join=4), 0.76), f"symbols/{code}.webp")
    sp = load("sym_special")
    # the eagle's bolt and the orb's sparks touch: split at the emptiest
    # columns near the thirds instead of by components
    prof = (alpha(sp) > 120).sum(axis=0).astype(float)
    cuts = [0]
    for k in (1, 2):
        lo, hi = int(sp.width * (k / 3 - 0.08)), int(sp.width * (k / 3 + 0.08))
        cuts.append(lo + int(np.argmin(prof[lo:hi])))
    cuts.append(sp.width)
    for code, x0, x1, fill in zip(["scatter", "eagle", "orb"], cuts, cuts[1:], [0.94, 1.0, 0.9]):
        part = sp.crop((x0, 0, x1, sp.height))
        save(tile(crop(part, (0, 0, part.width, part.height), thr=30, join=10), fill), f"symbols/{code}.webp")


def step_frame() -> None:
    """Key the (failed-magenta, now pale) opening out, then stretch the plain
    column shafts so the opening becomes the board's 6:5-ish ratio."""
    print("frame")
    im = load("frame")
    arr = np.asarray(im).copy()
    rgb = arr[..., :3].astype(np.int16)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    pale = (rgb.min(axis=2) > 185) | ((r > 180) & (b > 140) & (g < 160)) | (arr[..., 3] < 40)
    labels, _ = ndimage.label(pale)
    hole = labels == labels[arr.shape[0] // 2, arr.shape[1] // 2]
    hole = ndimage.binary_fill_holes(hole)
    hole = ndimage.binary_dilation(hole, iterations=3)
    # leftover pink fringe of the magenta fill along the opening
    pink = (r > 110) & (b > 70) & (g < r - 40) & (b > g + 10)
    near = ndimage.binary_dilation(hole, iterations=40)
    hole |= pink & near
    # the opening is a rectangle: clear its whole box (minus a hair for the
    # rounded inner corners) so no smear of the magenta fill survives
    ys, xs = np.where(ndimage.binary_erosion(hole, iterations=6))
    hole[ys.min() - 5:ys.max() + 6, xs.min() - 5:xs.max() + 6] = True
    arr[..., 3] = np.where(hole, 0, arr[..., 3])
    ys, xs = np.where(hole)
    hx0, hx1, hy0, hy1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    hw, hh = hx1 - hx0, hy1 - hy0
    target_h = round(hw * BOARD[1] / BOARD[0])
    im = Image.fromarray(arr)
    # stretch a band in the middle of the shafts (no ornament there)
    b0 = hy0 + int(hh * 0.30)
    b1 = hy0 + int(hh * 0.70)
    band = im.crop((0, b0, im.width, b1)).resize((im.width, (b1 - b0) + (target_h - hh)), Image.LANCZOS)
    out = Image.new("RGBA", (im.width, im.height + target_h - hh))
    out.paste(im.crop((0, 0, im.width, b0)), (0, 0))
    out.paste(band, (0, b0))
    out.paste(im.crop((0, b1, im.width, im.height)), (0, b0 + band.height))
    out = trim(clean_alpha(out))
    # re-measure the hole on the result: transparent area enclosed by the frame
    a = alpha(out) > 40
    enclosed = ndimage.binary_fill_holes(a) & ~a
    ys, xs = np.where(enclosed)
    hx0, hx1, hy0, hy1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    # inset 6px so the gold inner line overlaps the board edge a touch
    hx0, hy0, hx1, hy1 = hx0 + 6, hy0 + 6, hx1 - 6, hy1 - 6
    k = BOARD[0] / (hx1 - hx0)
    out = out.resize((round(out.width * k), round(out.height * k)), Image.LANCZOS)
    geo = {"w": out.width, "h": out.height, "left": round(hx0 * k), "top": round(hy0 * k),
           "hole_w": round((hx1 - hx0) * k), "hole_h": round((hy1 - hy0) * k)}
    save(out, "frame.webp")
    (OUT / "frame.json").write_text(json.dumps(geo))
    print("  geometry", geo)


def step_bg() -> None:
    print("backgrounds")
    for name, w in (("sky", 1920), ("sky_fs", 1920), ("sky_mob", 1152), ("sky_fs_mob", 1152)):
        im = load(name).convert("RGB")
        save(im.resize((w, round(w * im.height / im.width)), Image.LANCZOS), f"{name}.jpg", 86)


def step_hero_logo() -> None:
    print("hero + logo")
    h = trim(clean_alpha(load("hero")))
    h.thumbnail((760, 1140), Image.LANCZOS)
    save(h, "hero.webp")
    lg = trim(clean_alpha(load("logo")))
    lg.thumbnail((1000, 640), Image.LANCZOS)
    save(lg, "logo.webp")


def step_cover() -> None:
    print("cover")
    sky = load("sky_fs").convert("RGB")
    s = 720 / sky.height
    sky = sky.resize((round(sky.width * s), 720), Image.LANCZOS)
    c = sky.crop(((sky.width - 720) // 2, 0, (sky.width - 720) // 2 + 720, 720)).convert("RGBA")
    h = trim(clean_alpha(load("hero")))
    h = h.resize((round(h.width * 600 / h.height), 600), Image.LANCZOS)
    c.alpha_composite(h, (720 - h.width + 40, 130))
    lg = trim(clean_alpha(load("logo")))
    lg.thumbnail((520, 300), Image.LANCZOS)
    c.alpha_composite(lg, (24, 720 - lg.height - 24))
    c.convert("RGB").save(ROOT / "front/img/olympus-thunder/cover_v2.jpg", "JPEG", quality=86)
    print("  cover_v2.jpg")


STEPS = {"symbols": step_symbols, "frame": step_frame, "bg": step_bg, "hero": step_hero_logo, "cover": step_cover}

if __name__ == "__main__":
    for n in sys.argv[1:] or list(STEPS):
        STEPS[n]()
