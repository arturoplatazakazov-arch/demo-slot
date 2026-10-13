"""Deep Fortune: raw generations -> game assets.

Sources (not committed): front/img/deep-fortune/src/*.png (fal, gpt-image-1.5)
and front/img/deep-fortune/src/gpt/*.webp (the same model through ChatGPT,
saved by hand). Writes front/img/deep-fortune/{img,symbols}/ and prints the
measured empty-panel bounds of every plate — paste those into
front/css/deep-fortune.css (--popup-panel-*, buy/counter label positions).

    python3 scripts/deep_fortune_build.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "front/img/deep-fortune"
SRC, GPT = BASE / "src", BASE / "src/gpt"
IMG, SYM = BASE / "img", BASE / "symbols"
CELL = 360


def _open(name: str) -> Image.Image | None:
    for p in (GPT / f"{name}.webp", GPT / f"{name}.png", SRC / f"{name}.png"):
        if p.exists():
            return Image.open(p).convert("RGBA")
    return None


def _trim(im: Image.Image) -> Image.Image:
    # webp re-encoding leaves faint alpha noise around the art; ignore < 8.
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def _quant(im: Image.Image, colors: int = 224) -> Image.Image:
    return im.quantize(colors, method=Image.Quantize.FASTOCTREE)


def _fit(im: Image.Image, w: int, h: int, fill: float = 0.98) -> Image.Image:
    im = _trim(im)
    s = min(w * fill / im.width, h * fill / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", (w, h))
    out.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def symbols() -> None:
    SYM.mkdir(parents=True, exist_ok=True)
    # Letters are the low pays: a smaller fill keeps them from outweighing the
    # framed character tiles optically.
    fills = {"a": 0.84, "k": 0.84, "q": 0.84, "j": 0.84, "scatter": 0.94}
    for code in ["wild", "scatter", "siren", "nymph", "shark"]:
        im = _open(code)
        _quant(_fit(im, CELL, CELL, fills.get(code, 0.98))).save(SYM / f"{code}.png", optimize=True)
        print("symbol", code)
    letters = _open("letters")
    if letters is not None:
        # One sheet, 2x2: A K / Q J.
        w, h = letters.size
        for code, box in zip("akqj", [(0, 0, w // 2, h // 2), (w // 2, 0, w, h // 2),
                                       (0, h // 2, w // 2, h), (w // 2, h // 2, w, h)]):
            _quant(_fit(letters.crop(box), CELL, CELL, fills[code])).save(SYM / f"{code}.png", optimize=True)
            print("symbol", code)
    wild_big = _open("wild_big")
    if wild_big is not None:
        # The panel art comes out ~0.37:1, the column is exactly 1:3 — stretch
        # to fill it (a ~10% horizontal squeeze reads fine) rather than leave
        # gaps above and below the expanded reel.
        _quant(_trim(wild_big).resize((CELL, CELL * 3), Image.LANCZOS)).save(SYM / "wild_big.png", optimize=True)
        print("symbol wild_big")


def _panel(im: Image.Image) -> tuple[float, float, float, float]:
    """Empty navy panel bounds as CSS inset percentages (top right bottom left):
    flood-fill the navy pixels connected to the panel's centre."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    mask = Image.new("L", (w, h))
    px, mp = rgb.load(), mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if b > 60 and b > r + 40 and b > g + 20 and r < 90:
                mp[x, y] = 255
    # The panel centre is not always the image centre (crests on top), so
    # search down the middle column for the first navy pixel below the middle.
    cx, cy = w // 2, h // 2
    while mp[cx, cy] != 255 and cy < h - 1:
        cy += 1
    ImageDraw.floodfill(mask, (cx, cy), 128)
    x0, y0, x1, y1 = mask.point(lambda v: 255 if v == 128 else 0).getbbox()
    # Rounded corners: pull in a little so text never sits on the bevel.
    pad_x, pad_y = (x1 - x0) * 0.05, (y1 - y0) * 0.08
    return (100 * (y0 + pad_y) / h, 100 * (w - x1 + pad_x) / w,
            100 * (h - y1 + pad_y) / h, 100 * (x0 + pad_x) / w)


def ui() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    for name, max_w in [("popup_plate", 1100), ("popup_plate_mega", 1200),
                        ("popup_plate_epic", 1300), ("buy_bonus", 640), ("fs_counter", 480)]:
        im = _trim(_open(name))
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        _quant(im).save(IMG / f"{name}.png", optimize=True)
        t, r, b, l = _panel(im)
        print(f"{name} {im.width}x{im.height} panel inset: {t:.2f}% {r:.2f}% {b:.2f}% {l:.2f}%"
              f"  centre-y {(t + 100 - b) / 2:.1f}%")

    logo = _trim(_open("logo"))
    logo = logo.resize((900, round(logo.height * 900 / logo.width)), Image.LANCZOS)
    _quant(logo).save(IMG / "logo.png", optimize=True)

    hero = _trim(_open("hero"))
    for mood in ["hero", "hero_tense", "hero_cheer"]:
        src = _open(mood)
        im = _trim(src) if src is not None else hero  # pose not delivered yet
        im = im.resize((round(im.width * 929 / im.height), 929), Image.LANCZOS)
        _quant(im).save(IMG / f"{mood}.png", optimize=True)
        print(mood, "own" if src is not None else "= hero")

    for name in ["bg_base", "bg_base_mob", "bg_bonus", "bg_bonus_mob"]:
        _open(name).convert("RGB").save(IMG / f"{name}.jpg", quality=84, optimize=True, progressive=True)

    # Catalog cover 900x470: base bg + logo + mascot + Poseidon tile.
    bg = _open("bg_base").convert("RGB")
    s = 900 / bg.width
    bg = bg.resize((900, round(bg.height * s)), Image.LANCZOS)
    top = (bg.height - 470) // 3
    cover = bg.crop((0, top, 900, top + 470)).convert("RGBA")
    lg = logo.copy()
    lg.thumbnail((470, 270), Image.LANCZOS)
    hero_c = hero.copy()
    hero_c.thumbnail((300, 440), Image.LANCZOS)
    wild = _fit(_open("wild"), 250, 250)
    cover.alpha_composite(hero_c, (10, 470 - hero_c.height))
    cover.alpha_composite(wild, (900 - 265, 470 - 270))
    cover.alpha_composite(lg, ((900 - lg.width) // 2, 20))
    cover.convert("RGB").save(IMG / "cover.jpg", quality=86, optimize=True)


if __name__ == "__main__":
    symbols()
    ui()
