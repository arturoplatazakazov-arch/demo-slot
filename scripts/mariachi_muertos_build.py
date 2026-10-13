"""Mariachi Muertos: raw ChatGPT generations -> game assets.

Sources (not committed): front/img/mariachi-muertos/src/gpt/*.webp — saved by
hand from ChatGPT, every sheet drawn on flat black. Writes
front/img/mariachi-muertos/{img,symbols,fx}/ in the same names and canvas sizes
as uniqorn-bad-santa (the CSS layout is inherited from it), and prints the
measured empty-panel bounds of every plate for the CSS.

Needs opencv + rembg (not in the app's venv):
    uv venv <scratch>/rig && uv pip install --python <scratch>/rig/bin/python "rembg[cpu]" opencv-python-headless
    <scratch>/rig/bin/python scripts/mariachi_muertos_build.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "front/img/mariachi-muertos"
GPT = BASE / "src/gpt"
IMG, SYM, FX = BASE / "img", BASE / "symbols", BASE / "fx"
CELL = 360


def _open(name: str) -> Image.Image | None:
    for ext in ("webp", "png", "jpg"):
        p = GPT / f"{name}.{ext}"
        if p.exists():
            return Image.open(p).convert("RGB")
    return None


# --- black-plate keying ------------------------------------------------------

def key_black(im: Image.Image, thr: int = 30) -> Image.Image:
    """Transparent where the pixel is near-black AND connected to the image
    border, so dark paint inside the art (panels, eye sockets) survives. The
    rim of the kept region fades by brightness for an anti-aliased edge."""
    rgb = np.asarray(im.convert("RGB"))
    h, w = rgb.shape[:2]
    mx = rgb.max(axis=2)
    dark = (mx < thr).astype(np.uint8)
    # Label the dark regions; any that touches the border is background.
    n, lab = cv2.connectedComponents(dark, connectivity=4)
    # Label 0 is the non-dark pixels; every other label touching the border is background.
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    # Soft rim: pixels within 3px of the background ramp by brightness.
    near = cv2.dilate(bg.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~bg
    ramp = np.clip((mx.astype(np.int32) - 8) * 6, 0, 255).astype(np.uint8)
    alpha = np.where(near, np.minimum(alpha, ramp), alpha)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def key_glow(im: Image.Image) -> Image.Image:
    """For light-on-black art (flames, sparks, glows): alpha = brightness and
    the colour un-premultiplied, so it composites like an additive sprite."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    a = rgb.max(axis=2)
    safe = np.maximum(a, 1)[..., None]
    col = np.clip(rgb * 255.0 / safe, 0, 255)
    return Image.fromarray(np.dstack([col, a]).astype(np.uint8), "RGBA")


def items(im: Image.Image, thr: int = 30, min_area: int = 2500, close: int = 3,
          big_area: int = 8000) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
    """The separate drawings on a black sheet, row-major: (bbox, full-sheet
    mask). Big blobs are drawings; small detached bits (a flower, a leaf, a
    spark) join the nearest big one, so tightly packed sheets still split."""
    mx = np.asarray(im.convert("RGB")).max(axis=2)
    m = (mx >= thr).astype(np.uint8)
    if close > 1:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, connectivity=8)
    big = [i for i in range(1, n) if stats[i, 4] >= big_area]
    owner = {i: i for i in big}
    for i in range(1, n):
        if i in owner or stats[i, 4] < 20 or not big:
            continue
        owner[i] = min(big, key=lambda j: np.hypot(*(cent[i] - cent[j])))
    out = []
    for b in big:
        mask = np.isin(lab, [i for i, o in owner.items() if o == b])
        ys, xs = np.nonzero(mask)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        if (box[2] - box[0]) * (box[3] - box[1]) >= min_area:
            out.append((box, mask))
    out.sort(key=lambda it: (it[0][1] + it[0][3]) / 2)
    rows: list[list] = []
    for it in out:
        b = it[0]
        cy = (b[1] + b[3]) / 2
        if rows and abs(cy - rows[-1][0]) < (b[3] - b[1]) * 0.45:
            rows[-1][1].append(it)
        else:
            rows.append([cy, [it]])
    return [it for _, r in rows for it in sorted(r, key=lambda it: it[0][0])]


def _cut(im: Image.Image, box, mask: np.ndarray, pad: int = 6, glow: bool = False) -> Image.Image:
    """Crop one drawing, keyed off black, with its neighbours masked out."""
    bx = _pad(box, pad, *im.size)
    k = key_glow(im.crop(bx)) if glow else key_black(im.crop(bx))
    mk = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8))[bx[1]:bx[3], bx[0]:bx[2]]
    a = np.asarray(k)[..., 3] * (mk > 0)
    k.putalpha(Image.fromarray(a.astype(np.uint8)))
    return k


def _trim(im: Image.Image) -> Image.Image:
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def _quant(im: Image.Image, colors: int = 240) -> Image.Image:
    return im.quantize(colors, method=Image.Quantize.FASTOCTREE)


def _fit(im: Image.Image, w: int, h: int, fill: float = 0.94) -> Image.Image:
    im = _trim(im)
    s = min(w * fill / im.width, h * fill / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", (w, h))
    out.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def _pad(box, pad, w, h):
    x0, y0, x1, y1 = box
    return max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)


def _sheet(name: str, expect: int, **kw) -> list[Image.Image] | None:
    im = _open(name)
    if im is None:
        print("skip", name, "(no source)")
        return None
    found = items(im, **kw)
    if len(found) != expect:
        print(f"!! {name}: found {len(found)} items, expected {expect}: {[b for b, _ in found]}")
    return [_cut(im, b, m) for b, m in found]


# --- outputs -----------------------------------------------------------------

def symbols() -> None:
    SYM.mkdir(parents=True, exist_ok=True)
    got = _sheet("symbols_sheet", 8)
    if got:
        # Row 1: sombrero, maracas, tequila, pinata; row 2: A K Q J.
        codes = ["hp_yellow", "hp_red", "hp_green", "hp_blue", "lp_blue", "lp_green", "lp_red", "lp_yellow"]
        for code, im in zip(codes, got):
            fill = 0.84 if code.startswith("lp_") else 0.95
            _quant(_fit(im, CELL, CELL, fill)).save(SYM / f"{code}.png", optimize=True)
            print("symbol", code)
    got = _sheet("specials_sheet", 7)
    if got:
        codes = ["wild", "scatter", "bomb", "x2", "x3", "x5", "x7"]
        for code, im in zip(codes, got):
            fill = 0.86 if code[0] == "x" else 0.97
            _quant(_fit(im, CELL, CELL, fill)).save(SYM / f"{code}.png", optimize=True)
            print("symbol", code)


def fill_holes(im: Image.Image, k: int = 41) -> Image.Image:
    """Re-opaque a plate's dark panel where the black keying leaked into it
    through a thin gap in the rim: close the silhouette, fill what the border
    can't reach."""
    rgba = np.asarray(im).copy()
    sil = cv2.morphologyEx((rgba[..., 3] > 128).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    inv = (1 - sil).astype(np.uint8)
    n, lab = cv2.connectedComponents(inv, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = np.isin(lab, list(border))
    rgba[..., 3][~outside] = 255
    return Image.fromarray(rgba, "RGBA")


def _panel(im: Image.Image) -> str:
    """Empty dark panel bounds as CSS inset percentages (top right bottom left):
    flood the dark pixels connected to the plate's centre."""
    rgba = np.asarray(im)
    h, w = rgba.shape[:2]
    mx = rgba[..., :3].max(axis=2)
    cy, cx = h // 2, w // 2
    ref = int(mx[cy - 3:cy + 4, cx - 3:cx + 4].mean())
    m = ((np.abs(mx.astype(int) - ref) < 40) & (rgba[..., 3] > 200)).astype(np.uint8)
    n, lab = cv2.connectedComponents(m, connectivity=4)
    ys, xs = np.nonzero(lab == lab[cy, cx])
    # Trim 4% so text never kisses the carved rim.
    t, b, l, r = ys.min(), ys.max(), xs.min(), xs.max()
    dy, dx = (b - t) * 0.04, (r - l) * 0.03
    return (f"{(t + dy) / h * 100:.1f}% {(w - r + dx) / w * 100:.1f}% "
            f"{(h - b + dy) / h * 100:.1f}% {(l + dx) / w * 100:.1f}%")


def ui() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    got = _sheet("ui_sheet", 6)
    if got:
        # buy-bonus disc, free-spins plaque, multiplier plaque, 3 win banners.
        names = ["buy_bonus", "plate_fs", "plate_multi", "popup_plate", "popup_plate_mega", "popup_plate_epic"]
        for name, im in zip(names, got):
            im = _trim(fill_holes(im))
            if im.width > 1000:
                s = 1000 / im.width
                im = im.resize((1000, round(im.height * s)), Image.LANCZOS)
            _quant(im).save(IMG / f"{name}.png", optimize=True)
            print("ui", name, im.size, "panel inset:", _panel(im))

    logo = _open("logo")
    if logo is not None:
        im = _trim(key_black(logo))
        im = im.resize((900, round(im.height * 900 / im.width)), Image.LANCZOS)
        _quant(im).save(IMG / "logo.png", optimize=True)
        print("logo", im.size)


def backgrounds() -> None:
    for name, size in [("bg_base", (2300, 1119)), ("bg_bonus", (2300, 1119)),
                       ("bg_base_mob", (900, 1634)), ("bg_bonus_mob", (900, 1634))]:
        im = _open(name)
        if im is None:
            continue
        # Cover-fit to the bad-santa canvas (same layout), keep the centre.
        s = max(size[0] / im.width, size[1] / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x, y = (im.width - size[0]) // 2, (im.height - size[1]) // 2
        im.crop((x, y, x + size[0], y + size[1])).save(IMG / f"{name}.jpg", quality=84, optimize=True, progressive=True)
        print("bg", name)
    cover = _open("cover")
    if cover is not None:
        s = max(1280 / cover.width, 720 / cover.height)
        cover = cover.resize((round(cover.width * s), round(cover.height * s)), Image.LANCZOS)
        y = (cover.height - 720) // 2
        cover = cover.crop((0, y, 1280, y + 720)).convert("RGBA")
        logo = Image.open(IMG / "logo.png").convert("RGBA") if (IMG / "logo.png").exists() else None
        if logo is not None:
            lw = 520
            logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
            cover.alpha_composite(logo, (40, 720 - logo.height - 30))
        cover.convert("RGB").save(IMG / "cover.jpg", quality=86, optimize=True)
        print("cover")


def cover() -> None:
    """Catalog cover 1280x720: night bonus street + the mariachi + the logo
    (ChatGPT kept failing on a dedicated cover, and this matches the game)."""
    bg = _open("bg_bonus")
    if bg is None or not (IMG / "hero.png").exists() or not (IMG / "logo.png").exists():
        return
    s = max(1280 / bg.width, 720 / bg.height)
    bg = bg.resize((round(bg.width * s), round(bg.height * s)), Image.LANCZOS)
    x, y = (bg.width - 1280) // 2, (bg.height - 720) // 2
    out = bg.crop((x, y, x + 1280, y + 720)).convert("RGBA")
    hero = Image.open(IMG / "hero.png").convert("RGBA")
    hero = hero.resize((round(hero.width * 700 / hero.height), 700), Image.LANCZOS)
    out.alpha_composite(hero, (1280 - hero.width - 40, 720 - hero.height + 40))
    logo = Image.open(IMG / "logo.png").convert("RGBA")
    logo = logo.resize((640, round(logo.height * 640 / logo.width)), Image.LANCZOS)
    out.alpha_composite(logo, (50, (720 - logo.height) // 2))
    out.convert("RGB").save(IMG / "cover.jpg", quality=86, optimize=True)
    print("cover")


def hero() -> None:
    im = _open("hero")
    if im is None:
        return
    from rembg import new_session, remove
    cut = remove(im, session=new_session("birefnet-general"))
    cut = _trim(cut.convert("RGBA"))
    cut = cut.resize((round(cut.width * 928 / cut.height), 928), Image.LANCZOS)
    _quant(cut, 250).save(IMG / "hero.png", optimize=True)
    print("hero", cut.size)


def frame() -> None:
    """9-slice the generated frame so its opening equals the grid exactly:
    desktop 1206x919 with the hole at (119,130) 968x660, mobile 825x711 with
    the hole at (82,89) 662x534 (the bad-santa layout this CSS inherits)."""
    src = _open("frame")
    if src is None:
        return
    im = _trim(key_black(src))
    # The black opening is not connected to the border: clear it from the centre.
    rgba = np.asarray(im).copy()
    dark = (rgba[..., :3].max(axis=2) < 30).astype(np.uint8)
    n, lab = cv2.connectedComponents(dark, connectivity=4)
    hole = lab == lab[rgba.shape[0] // 2, rgba.shape[1] // 2]
    rgba[..., 3][hole] = 0
    im = Image.fromarray(rgba, "RGBA")
    a = rgba[..., 3]
    h, w = a.shape
    # Opening = the transparent run around the centre.
    cy, cx = h // 2, w // 2
    row, col = a[cy], a[:, cx]
    l = cx - np.argmax(row[:cx][::-1] > 128)
    r = cx + np.argmax(row[cx:] > 128)
    t = cy - np.argmax(col[:cy][::-1] > 128)
    b = cy + np.argmax(col[cy:] > 128)
    print("frame src", im.size, "opening", (l, t, r, b))
    # Ornament zones in source px (trimmed art): the corner skull clusters reach
    # well past the opening's edge, and the top medallion / bottom candles sit
    # centred. Those zones keep their proportions; only the plain diamond-carved
    # stretches between them absorb the size change.
    cx = w // 2
    c1, c2 = min(w // 2 - 200, 310), max(w // 2 + 200, w - 310)
    m0, m1 = cx - 150, cx + 150
    ct, cb = min(t + 90, h // 2 - 50), max(b - 90, h // 2 + 50)
    for name, (W, H, ox, oy, ow, oh) in {
        "frame_desk": (1206, 919, 119, 130, 968, 660),
        "frame_mob": (825, 711, 82, 89, 662, 534),
    }.items():
        # One uniform scale so the rail thickness fits the target insets.
        s = min(ox / l, oy / t, (W - ox - ow) / (w - r), (H - oy - oh) / (h - b))
        # x: [0,c1] fixed | [c1,m0] stretch | [m0,m1] fixed | [m1,c2] stretch | [c2,w] fixed
        xa = ox - l * s
        xe = ox + ow - (r - c2) * s
        span = xe - (xa + c1 * s)
        cw = (m1 - m0) * s
        side = (span - cw) / 2
        xs_src = [0, c1, m0, m1, c2, w]
        xs_dst = [xa, xa + c1 * s, xa + c1 * s + side, xa + c1 * s + side + cw, xe, xe + (w - c2) * s]
        # y: [0,ct] fixed | [ct,cb] stretch | [cb,h] fixed
        ya = oy - t * s
        ye = oy + oh - (b - cb) * s
        ys_src = [0, ct, cb, h]
        ys_dst = [ya, ya + ct * s, ye, ye + (h - cb) * s]
        if side <= 0 or ys_dst[2] <= ys_dst[1]:
            print(f"!! {name}: ornament zones don't fit (side={side:.0f})")
        out = Image.new("RGBA", (W, H))
        for i in range(5):
            for j in range(3):
                piece = im.crop((xs_src[i], ys_src[j], xs_src[i + 1], ys_src[j + 1]))
                x0, x1 = round(xs_dst[i]), round(xs_dst[i + 1])
                y0, y1 = round(ys_dst[j]), round(ys_dst[j + 1])
                if x1 <= x0 or y1 <= y0 or piece.width == 0 or piece.height == 0:
                    continue
                out.alpha_composite(piece.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
        # Belt and braces: nothing of the art may intrude into the grid rect.
        hole = Image.new("L", (ow, oh), 0)
        out.paste(Image.new("RGBA", (ow, oh), (0, 0, 0, 0)), (ox, oy), None)
        _quant(out).save(IMG / f"{name}.png", optimize=True)
        print("frame", name, f"scale {s:.3f}, plain rails {side / max(1, (m0 - c1) * s):.2f}x")


def fx() -> None:
    im = _open("fx_sheet")
    if im is None:
        return
    FX.mkdir(parents=True, exist_ok=True)
    found = items(im, close=5, big_area=1500)
    names = ["marigold_1", "marigold_2", "marigold_3", "petal_1", "petal_2", "petal_3",
             "coin_1", "coin_2", "flame_1", "flame_2", "glow", "spark_1", "spark_2",
             "flag_pink", "flag_green", "flag_teal", "skull"]
    if len(found) != len(names):
        print(f"!! fx: found {len(found)} items: {[b for b, _ in found]}")
    glow = {"flame_1", "flame_2", "glow", "spark_1", "spark_2"}
    for name, (box, mask) in zip(names, found):
        k = _trim(_cut(im, box, mask, pad=14, glow=name in glow))
        if max(k.size) > 220:
            s = 220 / max(k.size)
            k = k.resize((round(k.width * s), round(k.height * s)), Image.LANCZOS)
        k.save(FX / f"{name}.png", optimize=True)
        print("fx", name, k.size)


if __name__ == "__main__":
    steps = {"symbols": symbols, "ui": ui, "bg": backgrounds, "hero": hero, "frame": frame, "fx": fx,
             "cover": cover}
    for step in sys.argv[1:] or steps:
        steps[step]()
