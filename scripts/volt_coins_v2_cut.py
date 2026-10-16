"""Volt Coins v2: cut the raw gpt-image sheets (volt_coins_v2_gen.py) into game assets.

    python scripts/volt_coins_v2_cut.py

src/symbols.png      3x3 sheet  -> symbols/<code>.png (320x254, same box as v1)
src/coin_states.png  1x4 row    -> symbols/coin_{value,mini,minor,major}.png
src/cell_empty.png              -> symbols/coin_empty.png
src/plates.png       4x1 column -> img/plate_{grand,major,minor,mini}.png
src/frame|logo|coil.png         -> img/*.png (cropped to alpha)
src/bg_desk|bg_mob.png          -> img/bg_*.jpg
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "front/img/volt-coins-v2"
SRC = BASE / "src"

CELL = (320, 254)  # symbol box shared with v1 slot.js / css
SHEET = [
    ["wild", "coin", "diamond"],
    ["seven", "ingot", "bell"],
    ["bar", "star", "horseshoe"],
]
# Fill of the 254px box height (or width, whichever binds). Low symbols are
# drawn a notch smaller so they don't outweigh the high ones on the board.
FILL = {"horseshoe": 0.74, "star": 0.76, "bar": 0.76, "coin": 0.9, "wild": 0.9}
DEFAULT_FILL = 0.86

# Faint glow pixels below this alpha are ignored when computing the crop box
# (the glow itself is kept, it just doesn't push the box out).
BOX_ALPHA = 40


def alpha_box(im: Image.Image, thr: int = BOX_ALPHA) -> tuple[int, int, int, int]:
    mask = im.getchannel("A").point(lambda a: 255 if a >= thr else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("empty image")
    return box


def crop_alpha(im: Image.Image, pad: int = 6, thr: int = 8) -> Image.Image:
    l, t, r, b = alpha_box(im, thr)
    return im.crop((max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad)))


def fit_cell(im: Image.Image, fill: float) -> Image.Image:
    """Scale the solid body of `im` into CELL at `fill`, keep its glow, centre it."""
    l, t, r, b = alpha_box(im)
    bw, bh = r - l, b - t
    scale = min(CELL[0] * fill / bw, CELL[1] * fill / bh)
    big = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    cx, cy = (l + r) / 2 * scale, (t + b) / 2 * scale
    out = Image.new("RGBA", CELL, (0, 0, 0, 0))
    # paste (not alpha_composite): the canvas is empty and the offset may be negative
    out.paste(big, (round(CELL[0] / 2 - cx), round(CELL[1] / 2 - cy)))
    return out


def window_box(im: Image.Image, thr: int = 40) -> tuple[int, int, int, int]:
    """Transparent opening of a frame: scan out from the centre to the first solid pixel."""
    a = im.getchannel("A")
    cx, cy = im.width // 2, im.height // 2
    row = [a.getpixel((x, cy)) for x in range(im.width)]
    col = [a.getpixel((cx, y)) for y in range(im.height)]
    left = max(x for x in range(cx) if row[x] > thr) + 1
    right = min(x for x in range(cx, im.width) if row[x] > thr)
    top = max(y for y in range(cy) if col[y] > thr) + 1
    bottom = min(y for y in range(cy, im.height) if col[y] > thr)
    return left, top, right, bottom


def nine_slice(im: Image.Image, win_w: int, win_h: int, corner: int = 140):
    """Re-proportion a thin frame so its opening is win_w x win_h (borders kept 1:1).

    The model draws the opening ~1.5:1; the 3x3 grid of 320x254 symbols wants
    ~1.26:1. Corners (gold brackets) are copied as is, the straight runs between
    them are resampled."""
    l, t, r, b = window_box(im)
    out_w = l + win_w + (im.width - r)
    out_h = t + win_h + (im.height - b)
    out = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    c = corner
    xs_src = [(0, c), (c, im.width - c), (im.width - c, im.width)]
    ys_src = [(0, c), (c, im.height - c), (im.height - c, im.height)]
    xs_dst = [(0, c), (c, out_w - c), (out_w - c, out_w)]
    ys_dst = [(0, c), (c, out_h - c), (out_h - c, out_h)]
    for (sy0, sy1), (dy0, dy1) in zip(ys_src, ys_dst):
        for (sx0, sx1), (dx0, dx1) in zip(xs_src, xs_dst):
            part = im.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS)
            out.paste(part, (dx0, dy0))
    return out, (l, t, out_w - (im.width - r), out_h - (im.height - b))


def body_boxes(im: Image.Image, count: int, thr: int = 250, step: int = 4):
    """Bounding boxes of the `count` largest solid blobs (alpha >= thr), found by
    flood fill on a 1/step grid. The model does not lay a sheet out on an even
    grid and its glows are near-opaque, so cells are cut around the bodies."""
    small = im.getchannel("A").resize((im.width // step, im.height // step), Image.BOX)
    w, h = small.size
    px = small.load()
    seen = [[False] * w for _ in range(h)]
    blobs = []
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0][x0] or px[x0, y0] < thr:
                continue
            stack, n = [(x0, y0)], 0
            seen[y0][x0] = True
            l, t, r, b = x0, y0, x0, y0
            while stack:
                x, y = stack.pop()
                n += 1
                l, t, r, b = min(l, x), min(t, y), max(r, x), max(b, y)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny] >= thr:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            blobs.append((n, (l * step, t * step, (r + 1) * step, (b + 1) * step)))
    blobs.sort(reverse=True)
    return [box for _, box in blobs[:count]]


def reading_order(boxes, rows: int):
    """Sort boxes top-to-bottom into `rows` rows, then left-to-right."""
    boxes = sorted(boxes, key=lambda bx: (bx[1] + bx[3]) / 2)
    per = len(boxes) // rows
    out = []
    for r in range(rows):
        out += sorted(boxes[r * per:(r + 1) * per], key=lambda bx: bx[0])
    return out


def cut_body(im: Image.Image, box, margin: float = 0.16) -> Image.Image:
    """Crop around a body box plus a glow margin; anything of the neighbours
    that still falls inside is irrelevant because the margin < sheet gaps."""
    l, t, r, b = box
    m = round(max(r - l, b - t) * margin)
    return im.crop((max(0, l - m), max(0, t - m), min(im.width, r + m), min(im.height, b + m)))


def fit_body(part: Image.Image, fill: float) -> Image.Image:
    """Like fit_cell, but the body box is the opaque core, not the glow."""
    l, t, r, b = alpha_box(part, 250)
    bw, bh = r - l, b - t
    scale = min(CELL[0] * fill / bw, CELL[1] * fill / bh)
    big = part.resize((round(part.width * scale), round(part.height * scale)), Image.LANCZOS)
    cx, cy = (l + r) / 2 * scale, (t + b) / 2 * scale
    out = Image.new("RGBA", CELL, (0, 0, 0, 0))
    out.paste(big, (round(CELL[0] / 2 - cx), round(CELL[1] / 2 - cy)))
    return out


def split_grid(im: Image.Image, cols: int, rows: int):
    w, h = im.width / cols, im.height / rows
    for r in range(rows):
        for c in range(cols):
            yield r, c, im.crop((round(c * w), round(r * h), round((c + 1) * w), round((r + 1) * h)))


def save_png(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)
    print(path.relative_to(ROOT), im.size)


def main() -> None:
    sheet = Image.open(SRC / "symbols.png").convert("RGBA")
    codes = [code for row in SHEET for code in row]
    for code, box in zip(codes, reading_order(body_boxes(sheet, 9), 3)):
        save_png(fit_body(cut_body(sheet, box), FILL.get(code, DEFAULT_FILL)), BASE / "symbols" / f"{code}.png")

    states = Image.open(SRC / "coin_states.png").convert("RGBA")
    names = ["value", "mini", "minor", "major"]
    for name, box in zip(names, reading_order(body_boxes(states, 4), 1)):
        save_png(fit_body(cut_body(states, box), FILL["coin"]), BASE / "symbols" / f"coin_{name}.png")

    empty = Image.open(SRC / "cell_empty.png").convert("RGBA")
    save_png(fit_cell(empty, 0.84), BASE / "symbols" / "coin_empty.png")

    plates = Image.open(SRC / "plates.png").convert("RGBA")
    for r, _, part in split_grid(plates, 1, 4):
        name = ["grand", "major", "minor", "mini"][r]
        save_png(crop_alpha(part, pad=4, thr=BOX_ALPHA), BASE / "img" / f"plate_{name}.png")

    # Opening = 3x3 cells at the v1 frame scale (766x604, cell 255.3x201.3).
    frame = crop_alpha(Image.open(SRC / "frame.png").convert("RGBA"), pad=4)
    frame, win = nine_slice(frame, 766, 604)
    save_png(frame, BASE / "img" / "frame.png")
    print("  frame window", win, "-> borders l/t/r/b", win[0], win[1], frame.width - win[2], frame.height - win[3])

    for name in ("logo", "coil"):
        im = crop_alpha(Image.open(SRC / f"{name}.png").convert("RGBA"), pad=4)
        save_png(im, BASE / "img" / f"{name}.png")

    for name in ("bg_desk", "bg_mob"):
        out = BASE / "img" / f"{name}.jpg"
        Image.open(SRC / f"{name}.png").convert("RGB").save(out, quality=86, optimize=True)
        print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
