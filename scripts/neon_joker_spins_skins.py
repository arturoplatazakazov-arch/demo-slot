"""Neon Joker Spins — three art-direction skins (A neon sign, B glossy show, C rock chrome).

Each skin is the same game (slot.js / app.js / backend untouched) with its own
art folder front/img/neon-joker-spins/skins/<x>/ (picked up through
window.NJS_ASSET_ROOT) and a generated stylesheet css/njs-skin-<x>.css that
swaps image URLs and the measured window geometry (reel window inside the frame,
value windows inside jackpot plates / buy button / coins).

Sources: ChatGPT generations with real alpha, design/neon-joker-spins-concepts/src/<x>/
    bg.png       empty scene, landscape
    symbols.png  4x3: wild coin scatter seven / bell star cherry lemon / plum grape collector blank
    ui.png       logo / 4 jackpot plates GRAND MAJOR MINOR MINI / buy button
    coins.png    3x2: mini minor major / grand cell_empty cell_locked
    frame.png    empty 3x3 reel frame, transparent window
    mascot.png   full-body Joker

Glyph font, popups and FX sprites are shared with the base game (copied).

    <venv with opencv>/bin/python scripts/neon_joker_spins_skins.py a b c
"""

from __future__ import annotations

import colorsys
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "design/neon-joker-spins-concepts/src"
BASE = ROOT / "front/img/neon-joker-spins"
CSS = ROOT / "front/css"

SYMBOLS = ["wild", "coin", "scatter", "seven", "bell", "star", "cherry", "lemon",
           "plum", "grape", "collector", "blank"]
# C: the logo's lightning tail drops onto the MAJOR crown — clear it before cutting
UI_ERASE = {"c": [(470, 440, 730, 504)]}
LOW = {"cherry", "lemon", "plum", "grape", "star"}
SHARED = ["glyphs", "popups", "fx"]


# --- cutting -----------------------------------------------------------------

def _cuts(profile: np.ndarray, parts: int) -> list[int]:
    """Cut positions between `parts` bands: the emptiest column/row near each
    expected boundary (glow never fully clears between neighbours)."""
    n = len(profile)
    p = np.convolve(profile.astype(np.float32), np.ones(9) / 9, mode="same")
    nz = np.nonzero(profile)[0]
    lo, hi = (nz[0], nz[-1]) if len(nz) else (0, n - 1)
    out = [0]
    for k in range(1, parts):
        c = lo + (hi - lo) * k / parts
        w = (hi - lo) / parts * 0.35
        a, b = int(c - w), int(c + w)
        out.append(a + int(np.argmin(p[a:b])))
    return out + [n]


def _isolate(cell: Image.Image) -> Image.Image:
    """Drop scraps of neighbouring items that leaked over the cut (glow, a
    logo's lightning): solid blobs touching the cell edge that are much smaller
    than the item, together with their soft halo."""
    a = np.array(cell.getchannel("A"))
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 100).astype(np.uint8), 8)
    if n < 3:
        return cell
    H, W = a.shape
    top = max(st[1:, cv2.CC_STAT_AREA])
    keep = np.zeros_like(a, np.uint8)
    drop = np.zeros_like(a, np.uint8)
    for k in range(1, n):
        x, y, w, h, area = st[k]
        edge = x == 0 or y == 0 or x + w >= W or y + h >= H
        (drop if edge and area < top * 0.25 else keep)[lab == k] = 1
    halo = np.ones((17, 17), np.uint8)
    kill = (cv2.dilate(drop, halo) > 0) & ~(cv2.dilate(keep, np.ones((5, 5), np.uint8)) > 0)
    a[kill] = 0
    out = cell.copy()
    out.putalpha(Image.fromarray(a))
    return out


def grid(im: Image.Image, layout: list[int]) -> list[Image.Image]:
    """Cut a sheet laid out as rows of `layout[r]` items: rows split at the
    emptiest lines, each row split into its columns the same way."""
    a = np.array(im.getchannel("A")) > 40
    ys = _cuts(a.sum(1), len(layout))
    out = []
    for r, cols in enumerate(layout):
        band = a[ys[r]:ys[r + 1]]
        xs = _cuts(band.sum(0), cols)
        for c in range(cols):
            cell = _isolate(im.crop((xs[c], ys[r], xs[c + 1], ys[r + 1])))
            bb = cell.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
            out.append(cell.crop(bb) if bb else cell)
    return out


def crop(im: Image.Image, box, pad: int = 14) -> Image.Image:
    x0, y0, x1, y1 = box
    c = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))
    bb = c.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return c.crop(bb) if bb else c


def fit(im: Image.Image, w: int, h: int, fill: float) -> Image.Image:
    s = min(w * fill / im.width, h * fill / im.height)
    r = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(r, ((w - r.width) // 2, (h - r.height) // 2), r)
    return out


def save(im: Image.Image, path: Path, q: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jpg":
        im.convert("RGB").save(path, quality=q)
    else:
        im.save(path, "WEBP", quality=q, method=6)


def blur(im: Image.Image) -> Image.Image:
    """Vertical motion-blur twin for spinning strips (reel-spin.js _blur.webp)."""
    a = np.array(im).astype(np.float32)
    k = np.zeros((31, 1), np.float32)
    k[:, 0] = 1 / 31
    return Image.fromarray(np.clip(cv2.filter2D(a, -1, k), 0, 255).astype(np.uint8), "RGBA")


def dark_window(im: Image.Image, region=(0.0, 0.0, 1.0, 1.0)) -> tuple[float, float, float, float] | None:
    """Largest dark, opaque, enclosed area inside `region` (fractions) — the empty
    value window of a plate / button / coin face. Returns l, t, w, h fractions."""
    arr = np.array(im.convert("RGBA")).astype(np.int32)
    lum = (arr[..., 0] * 3 + arr[..., 1] * 6 + arr[..., 2]) / 10
    W, H = im.size
    rx0, ry0, rx1, ry1 = int(region[0] * W), int(region[1] * H), int(region[2] * W), int(region[3] * H)
    m = np.zeros((H, W), np.uint8)
    sub = (lum[ry0:ry1, rx0:rx1] < 70) & (arr[ry0:ry1, rx0:rx1, 3] > 200)
    m[ry0:ry1, rx0:rx1] = sub.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n < 2:
        return None
    k = max(range(1, n), key=lambda i: st[i, cv2.CC_STAT_AREA])
    x, y, w, h = st[k, 0], st[k, 1], st[k, 2], st[k, 3]
    return x / W, y / H, w / W, h / H


def face(im: Image.Image) -> tuple[float, float, float, float]:
    """Flat central face of a blank coin: the region around the centre whose
    colour stays close to the centre colour."""
    arr = np.array(im.convert("RGBA")).astype(np.int32)
    H, W = arr.shape[:2]
    c = arr[H // 2 - 6:H // 2 + 6, W // 2 - 6:W // 2 + 6, :3].reshape(-1, 3).mean(0)
    d = np.abs(arr[..., :3] - c).sum(-1)
    m = ((d < 70) & (arr[..., 3] > 200)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 4)
    k = lab[H // 2, W // 2]
    if k == 0:
        return 0.3, 0.3, 0.4, 0.4
    x, y, w, h = st[k, 0], st[k, 1], st[k, 2], st[k, 3]
    return x / W, y / H, w / W, h / H


def frame_window(im: Image.Image) -> tuple[float, float, float, float]:
    """Union of the transparent holes enclosed by the frame (the 3x3 window)."""
    a = np.array(im.getchannel("A"))
    hole = (a < 60).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(hole, 4)
    H, W = a.shape
    xs, ys = [], []
    for k in range(1, n):
        x, y, w, h, area = st[k]
        if x == 0 or y == 0 or x + w >= W or y + h >= H or area < W * H * 0.004:
            continue
        xs += [x, x + w]
        ys += [y, y + h]
    if not xs:
        return 0.15, 0.15, 0.7, 0.7
    return min(xs) / W, min(ys) / H, (max(xs) - min(xs)) / W, (max(ys) - min(ys)) / H


def punch_window(im: Image.Image, win) -> Image.Image:
    """Clear the reel window (the reel strip lives under the frame): everything
    inside the window except bright divider bars becomes transparent."""
    out = im.copy()
    W, H = im.size
    l, t, w, h = win
    x0, y0, x1, y1 = int(l * W), int(t * H), int((l + w) * W), int((t + h) * H)
    a = np.array(out.getchannel("A"))
    a[y0:y1, x0:x1] = np.where(a[y0:y1, x0:x1] > 160, a[y0:y1, x0:x1], 0)
    out.putalpha(Image.fromarray(a))
    return out


# --- skins -------------------------------------------------------------------

def build(x: str) -> dict:
    src = SRC / x
    dst = BASE / "skins" / x
    for d in SHARED:
        if (dst / d).exists():
            shutil.rmtree(dst / d)
        shutil.copytree(BASE / d, dst / d)
    geo: dict = {}

    # symbols + coins built from the symbol sheet
    sheet = Image.open(src / "symbols.png").convert("RGBA")
    cut = dict(zip(SYMBOLS, grid(sheet, [4, 4, 4])))
    for n in SYMBOLS[:-1]:
        im = fit(cut[n], 360, 360, 0.84 if n in LOW else 0.92)
        save(im, dst / "symbols" / f"{n}.webp")
        save(blur(im), dst / "symbols" / f"{n}_blur.webp")
    blank = fit(cut["blank"], 360, 360, 0.92)
    save(blank, dst / "coins/blank.webp")
    coll = fit(cut["collector"], 360, 360, 0.92)
    save(coll, dst / "coins/collector.webp")
    geo["coin_face"] = face(blank)
    geo["coll_face"] = face(coll)

    # jackpot coins + cells
    if (src / "coins.png").exists():
        cs = Image.open(src / "coins.png").convert("RGBA")
        for n, c in zip(["mini", "minor", "major", "grand", "cell_empty", "cell_locked"], grid(cs, [3, 3])):
            fill = 0.98 if n.startswith("cell") else 0.92
            save(fit(c, 360, 360, fill), dst / "coins" / f"{n}.webp")
    else:
        for n in ["mini", "minor", "major", "grand", "cell_empty", "cell_locked"]:
            shutil.copy(BASE / "coins" / f"{n}.webp", dst / "coins" / f"{n}.webp")

    img = dst / "img"
    # catalog cover: the concept mockup of this direction, 900x563 like the base game
    mock = {"a": "A_neon_sign", "b": "B_glossy_show", "c": "C_rock_chrome"}[x]
    cm = Image.open(ROOT / f"design/neon-joker-spins-concepts/{mock}_base.jpg").convert("RGB")
    ch = round(cm.width * 563 / 900)
    cm = cm.crop((0, (cm.height - ch) // 2, cm.width, (cm.height - ch) // 2 + ch)).resize((900, 563), Image.LANCZOS)
    save(cm, img / "cover.jpg", 86)
    # background: cover-crop to the base game's sizes; FS = warmer, brighter twin
    bg = Image.open(src / "bg.png").convert("RGB")

    def cover(im, w, h):
        s = max(w / im.width, h / im.height)
        r = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        return r.crop(((r.width - w) // 2, (r.height - h) // 2, (r.width - w) // 2 + w, (r.height - h) // 2 + h))

    def fs(im):
        hsv = np.array(im.convert("HSV")).astype(np.int32)
        hsv[..., 0] = (hsv[..., 0] + 14) % 256
        out = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")
        return ImageEnhance.Brightness(ImageEnhance.Color(out).enhance(1.15)).enhance(1.1)

    save(cover(bg, 1672, 941), img / "bg_base.jpg", 88)
    save(cover(fs(bg), 1672, 941), img / "bg_fs.jpg", 88)
    save(cover(bg, 941, 1672), img / "bg_base_mob.jpg", 88)
    save(cover(fs(bg), 941, 1672), img / "bg_fs_mob.jpg", 88)

    # ui: logo, plates, buy
    if (src / "ui.png").exists():
        ui = Image.open(src / "ui.png").convert("RGBA")
        for box in UI_ERASE.get(x, []):  # logo scraps hanging into the plates row
            ui.paste((0, 0, 0, 0), box)
        ub = grid(ui, [1, 4, 1])
        lim, rest = ub[0], ub[1:]
        plates, bim = rest[:4], rest[4]
        lim.thumbnail((1100, 1100), Image.LANCZOS)
        save(lim, img / "logo.webp")
        geo["logo_ar"] = lim.width / lim.height
        geo["jp"] = {}
        for n, p in zip(["grand", "major", "minor", "mini"], plates):
            p.thumbnail((600, 600), Image.LANCZOS)
            save(p, img / f"jp_{n}.webp")
            geo["jp"][n] = {"ar": p.width / p.height, "win": dark_window(p, (0.05, 0.3, 0.95, 0.97))}
        bim.thumbnail((520, 520), Image.LANCZOS)
        save(bim, img / "buy_on.webp")
        off = ImageEnhance.Brightness(ImageEnhance.Color(bim).enhance(0.25)).enhance(0.6)
        off.putalpha(bim.getchannel("A"))
        save(off, img / "buy_off.webp")
        geo["buy"] = {"ar": bim.width / bim.height, "win": dark_window(bim, (0.03, 0.08, 0.97, 0.95))}

    if (src / "frame.png").exists():
        fr = Image.open(src / "frame.png").convert("RGBA")
        fr = crop(fr, fr.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox(), pad=0)
        win = frame_window(fr)
        fr = punch_window(fr, win)
        fr.thumbnail((1200, 1200), Image.LANCZOS)
        save(fr, img / "frame.webp")
        geo["frame"] = {"w": fr.width, "h": fr.height, "win": win}

    if (src / "mascot.png").exists():
        m = Image.open(src / "mascot.png").convert("RGBA")
        m = crop(m, m.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox(), pad=0)
        m.thumbnail((1500, 1500), Image.LANCZOS)
        save(m, img / "mascot.webp")
        geo["mascot_ar"] = m.width / m.height
    return geo


def css(x: str, g: dict) -> str:
    r = f"../img/neon-joker-spins/skins/{x}/img"
    L = [f"/* generated by scripts/neon_joker_spins_skins.py — skin {x.upper()} */"]
    L.append(f".bg__img--base {{ background-image: url('{r}/bg_base.jpg?v=1'); }}")
    L.append(f".bg__img--fs {{ background-image: url('{r}/bg_fs.jpg?v=1'); }}")
    jp = g.get("jp", {})
    buy = g.get("buy", {"ar": 250 / 158, "win": None})
    # --- desktop: logo over the reels, plates + buy stacked in the right column
    lw = min(500, 136 * g.get("logo_ar", 3.0))
    L.append(f".logo {{ left: {800 - lw / 2:.0f}px; top: 4px; width: {lw:.0f}px; }}")
    gap, top0, bottom = 10, 112, 772
    inv = sum((1.1 if n == "grand" else 1.0) / j["ar"] for n, j in jp.items())
    bw = 250 if buy["ar"] < 2.5 else 290
    bh = bw / buy["ar"]
    W = min(270, (bottom - top0 - bh - gap * 4) / inv) if inv else 270
    y = top0
    for n in ["grand", "major", "minor", "mini"]:
        if n not in jp:
            continue
        j = jp[n]
        w = W * (1.1 if n == "grand" else 1.0)
        win = j["win"] or (0.14, 0.45, 0.72, 0.4)
        L.append(f".jp--{n} {{ background-image: url('{r}/jp_{n}.webp?v=1'); left: {1435 - w / 2:.0f}px; top: {y:.0f}px;"
                 f" width: {w:.0f}px; height: {w / j['ar']:.0f}px;"
                 f" --win-l: {win[0]:.3f}; --win-t: {win[1]:.3f}; --win-ww: {win[2]:.3f}; --win-hh: {win[3]:.3f}; }}")
        y += w / j["ar"] + gap
    if jp:
        L.append(".jp--grand { animation: none; }")
    win = buy["win"] or (0.14, 0.6, 0.72, 0.25)
    if "win" in buy and buy["win"] is not None:
        L.append(f".buy-btn {{ background-image: url('{r}/buy_on.webp?v=1'); }}")
        L.append(f".buy-btn[disabled] {{ background-image: url('{r}/buy_off.webp?v=1'); }}")
        L.append(f".buy-btn__price {{ left: {win[0] * 100:.1f}%; top: {win[1] * 100:.1f}%; width: {win[2] * 100:.1f}%; height: {win[3] * 100:.1f}%; }}")
    L.append(f".buy-btn {{ left: {1435 - bw / 2:.0f}px; top: {y + 4:.0f}px; width: {bw}px; height: {bh:.0f}px; }}")
    L.append(f".side-panel {{ left: 1310px; top: {y + 4:.0f}px; }}")
    if "frame" in g:
        f = g["frame"]
        l, t, w, h = f["win"]
        ar = f["w"] / f["h"]
        # desktop: reel window 178..698 (рама не заходит под бар V3), centred on x 800
        L.append(":root {")
        L.append(f"  --fw-l: {l:.4f}; --fw-t: {t:.4f}; --fw-w: {w:.4f}; --fw-h: {h:.4f};")
        L.append(f"  --frame-h: {520 / h:.1f}px;")
        L.append(f"  --frame-w: calc(var(--frame-h) * {ar:.4f});")
        L.append(f"  --frame-x: calc(800px - var(--frame-w) * {l + w / 2:.4f});")
        L.append(f"  --frame-y: calc(178px - var(--frame-h) * {t:.4f});")
        L.append("}")
        L.append(f".cabinet {{ background-image: url('{r}/frame.webp?v=1'); }}")

    # --- portrait 720x1280: logo, one row of 4 plates, reels under them
    P = ["@media (orientation: portrait) {"]
    P.append(f"  .bg__img--base {{ background-image: url('{r}/bg_base_mob.jpg?v=1'); }}")
    P.append(f"  .bg__img--fs {{ background-image: url('{r}/bg_fs_mob.jpg?v=1'); }}")
    pw = min(380, 150 * g.get("logo_ar", 3.0))
    P.append(f"  .logo {{ left: {360 - pw / 2:.0f}px; top: 6px; width: {pw:.0f}px; }}")
    py = 6 + pw / g.get("logo_ar", 3.0) + 6
    cw = (720 - 16 - 3 * 6) / 4
    ph = 0
    for k, n in enumerate(["mini", "minor", "major", "grand"]):
        if n in jp:
            P.append(f"  .jp--{n} {{ left: {8 + k * (cw + 6):.0f}px; top: {py:.0f}px; width: {cw:.0f}px; height: {cw / jp[n]['ar']:.0f}px; }}")
            ph = max(ph, cw / jp[n]["ar"])
    pbw = 130
    P.append(f"  .buy-btn {{ left: 6px; top: 20px; width: {pbw}px; height: {pbw / buy['ar']:.0f}px; }}")
    P.append("  .side-panel { left: 572px; top: 20px; }")
    if "frame" in g:
        fw_px = min(610, 716 * w) / w  # рама не шире экрана
        fh_px = fw_px / ar
        wt = max(py + ph + 8 + fh_px * t, 420)
        P.append("  :root {")
        P.append(f"    --frame-w: {fw_px:.1f}px; --frame-h: {fh_px:.1f}px;")
        P.append(f"    --frame-x: {360 - fw_px * (l + w / 2):.1f}px; --frame-y: {wt - fh_px * t:.1f}px;")
        P.append(f"    --fw-l: {l:.4f}; --fw-t: {t:.4f}; --fw-w: {w:.4f}; --fw-h: {h:.4f};")
        P.append("  }")
        P.append(f"  .cabinet {{ background-image: url('{r}/frame.webp?v=1'); }}")
    P.append("}")
    L += P
    if "mascot_ar" in g:
        L.append(".mascot { left: 30px; top: 70px; height: 800px; max-width: 470px; object-fit: contain; object-position: 50% 100%; }")
    # number on the blank coin / collector face
    l, t, w, h = g["coin_face"]
    L.append(f".reel__cell .coin-val {{ left: {(l + w * 0.1) * 100:.1f}%; right: {(1 - l - w * 0.9) * 100:.1f}%;"
             f" top: {(t + h * 0.22) * 100:.1f}%; height: {h * 0.56 * 100:.1f}%; }}")
    l, t, w, h = g["coll_face"]
    L.append(f".reel__cell[data-symbol=\"collector\"] .coin-val {{ left: {(l + w * 0.12) * 100:.1f}%; right: {(1 - l - w * 0.88) * 100:.1f}%;"
             f" top: {(t + h * 0.14) * 100:.1f}%; height: {h * 0.72 * 100:.1f}%; }}")
    return "\n".join(L) + "\n"


NAMES = {"a": "A · Neon Sign", "b": "B · Glossy Show", "c": "C · Rock Chrome"}

SWITCHER = """
  <!-- Скин-сравнение: переключатель сохраняет query (?api=...). -->
  <nav class="skin-switch" id="skinSwitch">{links}</nav>
  <style>
    .skin-switch {{ position: fixed; top: 10px; left: 10px; z-index: 120; display: flex; gap: 4px;
      padding: 4px; border-radius: 999px; background: rgba(10, 4, 20, 0.8); border: 1px solid rgba(255, 255, 255, 0.18);
      font: 700 12px/1 'Baloo 2', system-ui, sans-serif; backdrop-filter: blur(4px); }}
    .skin-switch a {{ padding: 7px 11px; border-radius: 999px; color: #e8dcff; text-decoration: none; white-space: nowrap; }}
    .skin-switch a.is-on {{ background: #ffd75a; color: #2a0f00; }}
    @media (orientation: portrait) {{ .skin-switch {{ top: auto; bottom: 6px; left: 50%; transform: translateX(-50%); padding: 2px; font-size: 10px; }}
      .skin-switch a {{ padding: 4px 8px; }} .skin-switch a span {{ display: none; }} }}
  </style>
  <script>for (const a of document.querySelectorAll('#skinSwitch a')) a.search = location.search;</script>
"""


def page(x: str) -> str:
    html = (ROOT / "front/neon-joker-spins.html").read_text()
    root = f"img/neon-joker-spins/skins/{x}"
    links = "".join(
        f'<a href="neon-joker-spins-{k}.html"{" class=\"is-on\"" if k == x else ""}>{k.upper()}<span>{NAMES[k][1:]}</span></a>' for k in NAMES)
    links += '<a href="neon-joker-spins.html">Оригинал</a>'
    reps = [
        ("<title>Neon Joker Spins — demo</title>", f"<title>Neon Joker Spins {x.upper()} — demo</title>"),
        ('<link rel="stylesheet" href="css/neon-joker-spins.css?v=2">',
         f'<link rel="stylesheet" href="css/neon-joker-spins.css?v=2">\n<link rel="stylesheet" href="css/njs-skin-{x}.css?v=1">'),
        ("img/neon-joker-spins/img/logo.webp?v=2", f"{root}/img/logo.webp?v=1"),
        ("img/neon-joker-spins/img/mascot.webp?v=1", f"{root}/img/mascot.webp?v=1"),
        ("img/neon-joker-spins/coins/collector.webp?v=1", f"{root}/coins/collector.webp?v=1"),
        # без Spine-пака: он нарисован под оригинальный арт
        ('  <script src="js/neon-joker-spins/fx.js?v=1"></script>\n', ""),
        ('  <script src="js/neon-joker-spins/slot.js?v=2"></script>',
         f"  <script>window.NJS_ASSET_ROOT = '{root}'; window.NJS_SKIN = '{x}';</script>\n"
         '  <script src="js/neon-joker-spins/winlines.js?v=2"></script>\n'
         '  <script src="js/neon-joker-spins/slot.js?v=2"></script>'),
        ('  <div class="screen" id="screen">', SWITCHER.format(links=links) + '\n  <div class="screen" id="screen">'),
    ]
    for a, b in reps:
        assert a in html, a
        html = html.replace(a, b)
    return html


if __name__ == "__main__":
    for x in sys.argv[1:] or ["a", "b", "c"]:
        g = build(x)
        (CSS / f"njs-skin-{x}.css").write_text(css(x, g))
        (ROOT / f"front/neon-joker-spins-{x}.html").write_text(page(x))
        print(x, {k: v for k, v in g.items() if k != "jp"})
