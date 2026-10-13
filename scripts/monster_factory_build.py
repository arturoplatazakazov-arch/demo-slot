"""Monster Factory art pipeline: ChatGPT-generated sources -> game assets.

Sources live in front/img/monster-factory/src/ (gitignored, the raw downloads
from the ChatGPT chats). Everything the game loads is written next to it:

    symbols/<code>.png   360x360, content normalised into a common box
    img/*.png|jpg        backgrounds, hero, popups, frame, plates, logo, cover

    python scripts/monster_factory_build.py            # everything available
    python scripts/monster_factory_build.py symbols    # one group

Sheets are cut at their transparent gutters (alpha projection), never at fixed
coordinates, so a regenerated sheet with slightly different spacing still cuts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "front/img/monster-factory"
SRC = BASE / "src"
SYM = BASE / "symbols"
IMG = BASE / "img"

ALPHA_T = 8  # webp re-encode leaves faint AA noise below this
SYMBOL_CANVAS = 360


def load(name: str) -> Image.Image:
    for ext in (".png", ".webp", ".jpg", ".jpeg"):
        p = SRC / f"{name}{ext}"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(name)


def has(name: str) -> bool:
    return any((SRC / f"{name}{ext}").exists() for ext in (".png", ".webp", ".jpg", ".jpeg"))


def clean_alpha(im: Image.Image) -> Image.Image:
    a = np.array(im)
    a[..., 3][a[..., 3] < ALPHA_T] = 0
    return Image.fromarray(a)


def bbox(im: Image.Image) -> tuple[int, int, int, int]:
    return clean_alpha(im).getchannel("A").getbbox()


def runs(mask: np.ndarray, min_gap: int = 15) -> list[tuple[int, int]]:
    """Filled spans of a 1-D occupancy mask, merging gaps narrower than min_gap."""
    spans, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            spans.append([start, i])
            start = None
    if start is not None:
        spans.append([start, len(mask)])
    merged: list[list[int]] = []
    for s in spans:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [tuple(s) for s in merged]


def split_grid(im: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    """Cut a sheet into cols x rows pieces at the widest transparent gutters."""
    a = np.array(clean_alpha(im).getchannel("A")) > 0
    W, H = im.size

    def cuts(occ: np.ndarray, n: int, length: int) -> list[int]:
        if n == 1:
            return [0, length]
        spans = runs(occ)
        gaps = [(spans[i + 1][0] - spans[i][1], (spans[i][1] + spans[i + 1][0]) // 2) for i in range(len(spans) - 1)]
        gaps.sort(reverse=True)
        mids = sorted(m for _, m in gaps[: n - 1])
        if len(mids) < n - 1:  # pieces touch: fall back to even split
            mids = [length * (i + 1) // n for i in range(n - 1)]
        return [0, *mids, length]

    xs = cuts(a.any(0), cols, W)
    pieces = []
    for r in range(rows):
        for c in range(cols):
            col_strip = a[:, xs[c]:xs[c + 1]]
            ys = cuts(col_strip.any(1), rows, H)
            box = (xs[c], ys[r], xs[c + 1], ys[r + 1])
            p = im.crop(box)
            pieces.append(p.crop(bbox(p)))
    return pieces


def fit_symbol(piece: Image.Image, box: int, dy: int = 0) -> Image.Image:
    """Scale content to fit `box` px (longest side) and centre it on the canvas."""
    w, h = piece.size
    s = box / max(w, h)
    piece = piece.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    out = Image.new("RGBA", (SYMBOL_CANVAS, SYMBOL_CANVAS), (0, 0, 0, 0))
    out.alpha_composite(piece, ((SYMBOL_CANVAS - piece.width) // 2, (SYMBOL_CANVAS - piece.height) // 2 + dy))
    return out


def save_png(im: Image.Image, path: Path, colors: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if colors:
        im = im.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
    im.save(path, optimize=True)
    print(f"  {path.relative_to(ROOT)} {Image.open(path).size}")


def save_jpg(im: Image.Image, path: Path, size: tuple[int, int] | None = None) -> None:
    im = im.convert("RGB")
    if size:
        im = im.resize(size, Image.LANCZOS)
    im.save(path, quality=86, optimize=True, progressive=True)
    print(f"  {path.relative_to(ROOT)} {im.size}")


def trim(im: Image.Image, pad: int = 0) -> Image.Image:
    l, t, r, b = bbox(im)
    return im.crop((max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad)))


def resize_h(im: Image.Image, h: int) -> Image.Image:
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def resize_w(im: Image.Image, w: int) -> Image.Image:
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


# --- groups -------------------------------------------------------------------

def build_symbols() -> None:
    print("symbols")
    hp = split_grid(load("sheet_hp"), 2, 2)
    for code, p in zip(["hp_red", "hp_yellow", "hp_green", "hp_blue"], hp):
        save_png(fit_symbol(p, 340), SYM / f"{code}.png")
    # J red / Q green / K blue / A yellow — the colours match the hp monsters.
    letters = split_grid(load("sheet_letters"), 2, 2)
    for code, p in zip(["lp_red", "lp_green", "lp_blue", "lp_yellow"], letters):
        save_png(fit_symbol(p, 300), SYM / f"{code}.png")
    specials = split_grid(load("sheet_specials"), 3, 1)
    for code, p, box in zip(["wild", "scatter", "bomb"], specials, [340, 340, 320]):
        save_png(fit_symbol(p, box), SYM / f"{code}.png")
    mults = split_grid(load("sheet_multipliers"), 2, 2)
    for code, p in zip(["x2", "x3", "x5", "x7"], mults):
        save_png(fit_symbol(p, 320), SYM / f"{code}.png")


def build_backgrounds() -> None:
    print("backgrounds")
    for name, size in [("bg_base", None), ("bg_bonus", None),
                       ("bg_base_mob", None), ("bg_bonus_mob", None)]:
        if has(name):
            save_jpg(load(name), IMG / f"{name}.jpg", size)


def build_characters() -> None:
    print("hero + popups")
    # WebP q88: indistinguishable from the PNG at ~1/5 of the weight.
    if has("hero"):
        resize_h(trim(load("hero")), 900).save(IMG / "hero.webp", quality=88, method=6)
        print("  img/hero.webp")
    for name in ["popup_big", "popup_mega", "popup_epic", "popup_freespins"]:
        if has(name):
            resize_w(trim(load(name), 4), 820).save(IMG / f"{name}.webp", quality=88, method=6)
            print(f"  img/{name}.webp")


def build_ui() -> None:
    print("ui")
    for name, w in [("logo", 760), ("buy_bonus", 520), ("plate_counter", 480), ("plate_amount", 900)]:
        if has(name):
            save_png(resize_w(trim(load(name), 2), w), IMG / f"{name}.png")


def build_cover() -> None:
    print("cover")
    if not has("cover_art"):
        return
    cover = load("cover_art").convert("RGB").resize((1280, 720), Image.LANCZOS).convert("RGBA")
    if (IMG / "logo.png").exists():
        logo = Image.open(IMG / "logo.png").convert("RGBA")
        logo = resize_w(logo, 520)
        cover.alpha_composite(logo, ((1280 - logo.width) // 2, 720 - logo.height - 18))
    save_jpg(cover, IMG / "cover.jpg")


GROUPS = {
    "symbols": build_symbols,
    "backgrounds": build_backgrounds,
    "characters": build_characters,
    "ui": build_ui,
    "cover": build_cover,
}

if __name__ == "__main__":
    for g in sys.argv[1:] or list(GROUPS):
        GROUPS[g]()
