"""Olympus Thunder v3 "Noir": cut the black-figure ChatGPT pack into the
variant's runtime art (front/img/olympus-thunder/v3/).

Sources: front/img/olympus-thunder/v3/src/<name>.webp (gitignored):
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
from olympus_thunder_build import alpha, clean_alpha, crop, magenta_hole, pieces, tile, trim, unchecker  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "front/img/olympus-thunder/v3"
SRC = OUT / "src"
BOARD = (720, 600)  # v3 grid: 6x5 at --cell 120 (the opening frames the grid)


def load(name: str) -> Image.Image:
    return Image.open(SRC / f"{name}.webp").convert("RGBA")


def save(im: Image.Image, rel: str, q: int = 90) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix == ".jpg":
        im.convert("RGB").save(p, "JPEG", quality=q, optimize=True, progressive=True)
    else:
        im.save(p, "WEBP", quality=q, alpha_quality=100, method=6)
    print(f"  v3/{rel} {im.size[0]}x{im.size[1]}")


def step_symbols() -> None:
    print("symbols")
    src = load("sym_high")
    hw, hh = src.width // 2, src.height // 2
    for code, (qx, qy) in zip(["helmet", "lyre", "amphora", "wreath"], [(0, 0), (hw, 0), (0, hh), (hw, hh)]):
        q = src.crop((qx, qy, qx + hw, qy + hh))
        save(tile(crop(q, (0, 0, hw, hh), thr=40, join=3), 0.98), f"symbols/{code}.webp")
    # Greek-letter discs onto the five low codes (paytable order kept):
    # A white slip, B red slip, Γ terracotta, Δ ochre, Ω black
    low = load("sym_low")
    if alpha(low).min() == 255:
        low = unchecker(low)
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
    for code, x0, x1, fill in zip(["scatter", "eagle", "orb"], cuts, cuts[1:], [0.96, 0.98, 0.9]):
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
    c.convert("RGB").save(ROOT / "front/img/olympus-thunder/cover_v3.jpg", "JPEG", quality=86)
    print("  cover_v3.jpg")


def step_titles() -> None:
    """Six painted inscriptions, one per row: cut at the emptiest rows."""
    print("titles")
    im = load("titles")
    prof = (alpha(im) > 120).sum(axis=1).astype(float)
    prof = np.convolve(prof, np.ones(7) / 7, mode="same")
    band = im.height / 6
    cuts = [0] + [int(band * k - band * .3) + int(np.argmin(prof[int(band * k - band * .3):int(band * k + band * .3)]))
                  for k in range(1, 6)] + [im.height]
    names = ["big_win", "mega_win", "epic_win", "free_spins", "super_free_spins", "jackpot"]
    for name, y0, y1 in zip(names, cuts, cuts[1:]):
        piece = trim(clean_alpha(im.crop((0, y0, im.width, y1))))
        piece.thumbnail((1100, 400), Image.LANCZOS)
        save(piece, f"titles/{name}.webp")


def step_ui() -> None:
    """Jackpot tablets (white/ochre/red/black = mini/minor/major/grand), win
    tablet, multiplier medallion, buy disc — magenta panels cut out."""
    print("ui")
    im = load("ui_plates")
    boxes = pieces(im, thr=200, join=1, min_area=8000)
    assert len(boxes) == 7, boxes
    names = ["jp_mini", "jp_minor", "jp_major", "jp_grand", "plate_win", "medallion", "buy_button"]
    holes = {}
    for name, b in zip(names, boxes):
        piece, _ = magenta_hole(crop(im, b, thr=200, join=1))
        piece.thumbnail((720, 720) if name == "plate_win" else (440, 440), Image.LANCZOS)
        a = alpha(piece)
        enclosed = ndimage.binary_fill_holes(a > 40) & (a <= 40)
        ys, xs = np.where(enclosed)
        holes[name] = {"w": piece.width, "h": piece.height,
                       "hole": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None}
        save(piece, f"ui/{name}.webp")
    (OUT / "ui/holes.json").write_text(json.dumps(holes))
    print("  holes", holes)


STEPS = {"titles": step_titles, "ui": step_ui, "symbols": step_symbols, "frame": step_frame, "bg": step_bg, "hero": step_hero_logo, "cover": step_cover}

def fix_buy_bolt() -> None:
    """The painted bolt sits off-centre (tip in the rim at upper right):
    lift it out of the disc, give the disc a glaze-black face, and set the
    bolt back centred (by its alpha centroid) at 82% size."""
    p = OUT / "ui/buy_button.webp"
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im).copy()
    cx, cy, r = 211.5, 215.0, 139.0
    yy, xx = np.mgrid[0:im.height, 0:im.width]
    d = np.hypot(xx - cx, yy - cy)
    inside = d < r - 5
    bolt = a.copy()
    bolt[..., 3] = np.where(inside, bolt[..., 3], 0)
    bolt_im = trim(Image.fromarray(bolt))
    ring = a.copy()
    ring[..., 3] = np.where(d < r - 1, 0, ring[..., 3])
    face = np.zeros_like(a)
    t = np.clip(d / r, 0, 1)
    face[..., 0] = (34 - 18 * t).astype(np.uint8)
    face[..., 1] = (22 - 12 * t).astype(np.uint8)
    face[..., 2] = (15 - 8 * t).astype(np.uint8)
    face[..., 3] = np.where(d < r + 2, 255, 0)
    out = Image.fromarray(face)
    out.alpha_composite(Image.fromarray(ring))
    k = 0.82
    bolt_im = bolt_im.resize((round(bolt_im.width * k), round(bolt_im.height * k)), Image.LANCZOS)
    ba = np.asarray(bolt_im)[..., 3].astype(float)
    ys, xs = np.indices(ba.shape)
    bcx, bcy = (xs * ba).sum() / ba.sum(), (ys * ba).sum() / ba.sum()
    bcx = (bcx + bolt_im.width / 2) / 2
    bcy = (bcy + bolt_im.height / 2) / 2
    out.alpha_composite(bolt_im, (round(cx - bcx), round(cy - bcy)))
    out.save(p, "WEBP", quality=92, alpha_quality=100, method=6)
    print("  v3/ui/buy_button.webp re-centred")


STEPS["buybolt"] = fix_buy_bolt


def step_frame_mob() -> None:
    """Portrait frame: the painted border re-built around a wider opening
    (9-slice: corners kept, meander edges tiled by their own period) and
    drawn at 75% thickness, so a 10% bigger board still fits the screen."""
    import sys as _s
    from olympus_thunder_build import _tile
    print("frame_mob")
    src = Image.open(OUT / "frame.webp").convert("RGBA")
    geo = json.loads((OUT / "frame.json").read_text())
    L, T = geo["left"], geo["top"]
    R = src.width - L - geo["hole_w"]
    B = src.height - T - geo["hole_h"]
    s = 0.75
    hole_w, hole_h = round(900 / s), round(750 / s)
    W, H = L + hole_w + R, T + hole_h + B
    cx, cy = L + 110, T + 110          # corner boxes (palmettes)
    out = Image.new("RGBA", (W, H))
    top = src.crop((cx, 0, src.width - cx, T + 10))
    bot = src.crop((cx, src.height - B - 10, src.width - cx, src.height))
    lef = src.crop((0, cy, L + 10, src.height - cy))
    rig = src.crop((src.width - R - 10, cy, src.width, src.height - cy))
    out.alpha_composite(_tile(top, W - 2 * cx), (cx, 0))
    out.alpha_composite(_tile(bot, W - 2 * cx), (cx, H - bot.height))
    lv = _tile(lef.rotate(90, expand=True), H - 2 * cy).rotate(-90, expand=True)
    rv = _tile(rig.rotate(90, expand=True), H - 2 * cy).rotate(-90, expand=True)
    out.alpha_composite(lv, (0, cy))
    out.alpha_composite(rv, (W - rv.width, cy))
    for (x0, y0, x1, y1), (px, py) in (
        ((0, 0, cx, cy), (0, 0)),
        ((src.width - cx, 0, src.width, cy), (W - cx, 0)),
        ((0, src.height - cy, cx, src.height), (0, H - cy)),
        ((src.width - cx, src.height - cy, src.width, src.height), (W - cx, H - cy)),
    ):
        out.alpha_composite(src.crop((x0, y0, x1, y1)), (px, py))
    out = out.resize((round(W * s), round(H * s)), Image.LANCZOS)
    save(out, "frame_mob.webp")
    print("  css box: left", -round(L * s), "top", -round(T * s), "w", out.width, "h", out.height)


STEPS["frame_mob"] = step_frame_mob


if __name__ == "__main__":
    for n in sys.argv[1:] or list(STEPS):
        STEPS[n]()
