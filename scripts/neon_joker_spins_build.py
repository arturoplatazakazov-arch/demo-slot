"""Neon Joker Spins: raw ChatGPT generations -> game assets.

Sources (not committed): front/img/neon-joker-spins/src/gpt/*.webp — drawn in
ChatGPT on flat black from one approved style frame (mockup_v2). Writes
front/img/neon-joker-spins/{symbols,coins,img}/.

Neon on black: everything near-black that is connected to the sheet border is
background (key_black), so dark paint INSIDE a drawing (the joker's suit, a
coin's recess) survives; the glow halo keeps a brightness ramp.

Needs opencv + rembg (not in the app's venv):
    uv venv <scratch>/rig && uv pip install --python <scratch>/rig/bin/python "rembg[cpu]" opencv-python-headless
    <scratch>/rig/bin/python scripts/neon_joker_spins_build.py
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "front/img/neon-joker-spins"
GPT = BASE / "src/gpt"
SYM, COINS, IMG = BASE / "symbols", BASE / "coins", BASE / "img"
CELL = 360


def _open(name: str) -> Image.Image | None:
    for ext in ("webp", "png", "jpg"):
        p = GPT / f"{name}.{ext}"
        if p.exists():
            return Image.open(p).convert("RGB")
    return None


def key_black(im: Image.Image, thr: int = 26) -> Image.Image:
    """Alpha from brightness for the halo, solid for the drawing body.

    Background = near-black connected to the border. Inside the background
    the halo fades by brightness (un-premultiplied, so the glow keeps its
    colour over any backdrop); everything else is opaque."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    mx = rgb.max(axis=2)
    dark = (mx < thr).astype(np.uint8)
    _, lab = cv2.connectedComponents(dark, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    # Halo zone: background plus a band around it where the glow lives.
    halo = cv2.dilate(bg.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    glow_a = np.clip((mx - 6) * 1.6, 0, 255)
    alpha = np.where(halo, glow_a, 255.0)
    alpha = np.where(bg & (mx < 10), 0, alpha)
    a = np.maximum(alpha, 1)[..., None]
    col = np.where(halo[..., None], np.clip(rgb * 255.0 / a, 0, 255), rgb)
    return Image.fromarray(np.dstack([col, alpha]).astype(np.uint8), "RGBA")


def key_glow(im: Image.Image) -> Image.Image:
    """Light-on-black overlays (cell glows): alpha = brightness, colour
    un-premultiplied — composites like an additive sprite."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    a = rgb.max(axis=2)
    col = np.clip(rgb * 255.0 / np.maximum(a, 1)[..., None], 0, 255)
    return Image.fromarray(np.dstack([col, a]).astype(np.uint8), "RGBA")


def items(im: Image.Image, thr: int = 40, big_area: int = 6000) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
    """Separate drawings on a black sheet, row-major (bbox, mask). Small
    detached bits (a spark, a leaf) join the nearest big blob."""
    mx = np.asarray(im.convert("RGB")).max(axis=2)
    m = cv2.morphologyEx((mx >= thr).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, connectivity=8)
    big = [i for i in range(1, n) if stats[i, 4] >= big_area]
    owner = {i: i for i in big}
    for i in range(1, n):
        if i in owner or stats[i, 4] < 15 or not big:
            continue
        owner[i] = min(big, key=lambda j: np.hypot(*(cent[i] - cent[j])))
    out = []
    for b in big:
        mask = np.isin(lab, [i for i, o in owner.items() if o == b])
        ys, xs = np.nonzero(mask)
        out.append(((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), mask))
    # A drawing inside another's box (lettering on a sign's dark backing) is
    # part of it, not a separate item.
    merged = True
    while merged:
        merged = False
        for i, (bi, mi) in enumerate(out):
            for j, (bj, mj) in enumerate(out):
                if i != j and bi[0] >= bj[0] - 4 and bi[1] >= bj[1] - 4 and bi[2] <= bj[2] + 4 and bi[3] <= bj[3] + 4:
                    out[j] = (bj, mj | mi)
                    out.pop(i)
                    merged = True
                    break
            if merged:
                break
    # Fill the enclosed dark parts (sign backing, plate windows) into the mask.
    filled = []
    for b, m in out:
        mm = cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8))
        h, w = mm.shape
        cv2.floodFill(mm, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 2)
        filled.append((b, (mm != 2) | m))
    out = filled
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


def _pad(box, pad, w, h):
    x0, y0, x1, y1 = box
    return max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)


def _own(found: list, shape) -> np.ndarray:
    """Which drawing owns each pixel: the nearest one (per-item distance
    transform). Cuts take only their own pixels, so a neighbour's edge or
    glow never lands in a crop even when bounding boxes overlap."""
    dist = np.stack([
        cv2.distanceTransform((~m).astype(np.uint8), cv2.DIST_L2, 5) for _, m in found
    ]) if found else np.zeros((0, *shape))
    return dist.argmin(axis=0) if found else np.zeros(shape, int)


def _cut(im: Image.Image, box, mask: np.ndarray, pad: int = 26, glow: bool = False,
         owner: np.ndarray | None = None, index: int = 0) -> Image.Image:
    bx = _pad(box, pad, *im.size)
    k = key_glow(im.crop(bx)) if glow else key_black(im.crop(bx))
    near = cv2.dilate(mask.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
    if owner is not None:
        near &= owner == index
    mk = near[bx[1]:bx[3], bx[0]:bx[2]]
    a = np.asarray(k)[..., 3].astype(np.float32) * (mk > 0)
    k.putalpha(Image.fromarray(a.astype(np.uint8)))
    return k


def _trim(im: Image.Image) -> Image.Image:
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox())


def _fit(im: Image.Image, w: int, h: int, fill: float) -> Image.Image:
    im = _trim(im)
    s = min(w * fill / im.width, h * fill / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", (w, h))
    out.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def _save(im: Image.Image, path: Path) -> None:
    """WebP q92 with alpha: ~5-8x lighter than PNG for this soft-glow art,
    no visible loss (lossless only for the small glyphs)."""
    path = path.with_suffix(".webp")
    path.parent.mkdir(parents=True, exist_ok=True)
    if "glyphs" in path.parts:
        im.save(path, lossless=True, method=6)
    else:
        im.save(path, quality=92, alpha_quality=95, method=6)
    print("wrote", path.relative_to(ROOT), im.size)


def _sheet(name: str, expect: int, thr: int = 40, glow_idx: tuple = ()) -> list[Image.Image]:
    im = _open(name)
    if im is None:
        print("skip", name)
        return []
    found = items(im, thr=thr)
    if len(found) != expect:
        print(f"!! {name}: {len(found)} items, expected {expect}: {[b for b, _ in found]}")
    owner = _own(found, np.asarray(im).shape[:2])
    return [_cut(im, b, m, glow=i in glow_idx, owner=owner, index=i) for i, (b, m) in enumerate(found)]


# Share of the cell each drawing fills — by BODY, so a symbol with a wide
# halo doesn't come out smaller than its neighbours.
FILL = {
    "wild": 0.86, "coin": 0.86, "collector": 0.9, "scatter": 0.92,
    "seven": 0.84, "bell": 0.84, "star": 0.84,
    "cherry": 0.8, "lemon": 0.8, "plum": 0.8, "grape": 0.82,
}


def symbols() -> None:
    hp = _sheet("symbols_hp", 7, thr=110)
    for code, im in zip(["wild", "coin", "collector", "scatter", "seven", "bell", "star"], hp):
        _save(_fit(im, CELL, CELL, FILL[code]), SYM / f"{code}.png")
    lp = _sheet("symbols_lp", 4)
    for code, im in zip(["cherry", "lemon", "plum", "grape"], lp):
        _save(_fit(im, CELL, CELL, FILL[code]), SYM / f"{code}.png")


def coins() -> None:
    got = _sheet("coins", 8, glow_idx=(6, 7))
    names = ["blank", "mini", "minor", "major", "grand", "collector", "cell_locked", "cell_empty"]
    for name, im in zip(names, got):
        fill = {"major": 0.98, "grand": 0.98, "collector": 0.9, "cell_locked": 1.0, "cell_empty": 1.0}.get(name, 0.86)
        _save(_fit(im, CELL, CELL, fill), COINS / f"{name}.png")



def plates() -> None:
    """Jackpot plates (tier name baked in) + the empty value window of each,
    as fractions of the trimmed plate, for the CSS."""
    got = _sheet("plates", 4, thr=60)
    for tier, im in zip(["mini", "minor", "major", "grand"], got):
        im = _trim(im)
        w = 760 if tier == "grand" else 600
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        _save(im, IMG / f"jp_{tier}.png")
        rgb = np.asarray(im)[..., :3].astype(np.int32)
        a = np.asarray(im)[..., 3]
        dark = ((rgb.max(axis=2) < 45) & (a > 200)).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=4)
        i = max(range(1, n), key=lambda k: st[k, 4])
        x, y, ww, hh = st[i, :4]
        print(f"  {tier}: size {im.size} window left {x / im.width:.3f} top {y / im.height:.3f} "
              f"w {ww / im.width:.3f} h {hh / im.height:.3f}")




def popups() -> None:
    """Popup title signs + the shared amount panel, from two well-spaced
    sheets (the first packed sheet `popups` overlapped — not used). Width
    capped at 900px; the panel's empty window goes to the console."""
    for sheet, names in (("popups_wins", ["bigWin", "megaWin", "epicWin"]),
                         ("popups_feat", ["freeSpins", "holdAndWin", "totalWin", "panel"])):
        got = _sheet(sheet, len(names), thr=60)
        for name, im in zip(names, got):
            im = _trim(im)
            k = min(1.0, 900 / im.width)
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
            _save(im, BASE / "popups" / f"{name}.png")
            if name == "panel":
                rgb = np.asarray(im)[..., :3].astype(np.int32)
                a = np.asarray(im)[..., 3]
                dark = ((rgb.max(axis=2) < 50) & (a > 200)).astype(np.uint8)
                n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=4)
                i = max(range(1, n), key=lambda q: st[q, 4])
                x, y, w, h = st[i, :4]
                print(f"  panel {im.size} window left {x / im.width:.3f} top {y / im.height:.3f} "
                      f"w {w / im.width:.3f} h {h / im.height:.3f}")



# Rig parts of the mascot (ChatGPT sheet, row-major): row 1 head + 3 bells,
# row 2 L upper arm, L forearm (snap), torso, R upper arm, R forearm (card),
# row 3 L thigh, L shin, R thigh, R shin. Sorted by geometry, not trust.
RIG_ORDER = ["head", "bell_a", "bell_b", "bell_c",
             "arm_l_up", "arm_l_low", "torso", "arm_r_up", "arm_r_low",
             "leg_l_up", "leg_l_low", "leg_r_up", "leg_r_low"]


def rig() -> None:
    im = _open("mascot_parts")
    if im is None:
        print("skip rig")
        return
    found = items(im, thr=40, big_area=1500)
    owner = _own(found, np.asarray(im).shape[:2])
    cuts = [(b, _trim(_cut(im, b, m, pad=8, owner=owner, index=i))) for i, (b, m) in enumerate(found)]
    print("rig parts", len(cuts), [b for b, _ in cuts])
    if len(cuts) != len(RIG_ORDER):
        print("!! expected", len(RIG_ORDER))
    for name, (b, part) in zip(RIG_ORDER, cuts):
        _save(part, BASE / "rig" / f"{name}.png")



ARM_ORDER = ["arm2_l_up", "arm2_l_low", "arm2_r_up", "arm2_r_low",
             "hand_snap", "hand_card", "hand_open", "hand_fist"]


def arms() -> None:
    """Straight arm segments + hands (second rig sheet), row-major."""
    im = _open("mascot_arms")
    if im is None:
        print("skip arms")
        return
    found = items(im, thr=40, big_area=1500)
    owner = _own(found, np.asarray(im).shape[:2])
    cuts = [(b, _trim(_cut(im, b, m, pad=8, owner=owner, index=i))) for i, (b, m) in enumerate(found)]
    print("arm parts", len(cuts), [b for b, _ in cuts])
    for name, (b, part) in zip(ARM_ORDER, cuts):
        _save(part, BASE / "rig" / f"{name}.png")



def _split_gold_row(im, found, parts):
    """The last item is a row of gold letters whose glows touch (JOKER):
    split it by the letters' gold bodies — each body's nearest pixels."""
    b, m = found[-1]
    rgb = np.asarray(im.convert("RGB")).astype(np.int32)
    gold = ((rgb[..., 0] > 190) & (rgb[..., 1] > 130) & (rgb[..., 2] < 120) & m).astype(np.uint8)
    gold = cv2.morphologyEx(gold, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(gold, connectivity=8)
    bodies = sorted((i for i in range(1, n)), key=lambda i: -st[i, 4])[:parts]
    bodies.sort(key=lambda i: st[i, 0])
    dist = np.stack([cv2.distanceTransform((lab != i).astype(np.uint8), cv2.DIST_L2, 5) for i in bodies])
    near = dist.argmin(axis=0)
    out = list(found[:-1])
    for k in range(len(bodies)):
        mk = m & (near == k)
        ys, xs = np.nonzero(mk)
        out.append(((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), mk))
    print(f"  split the last row into {len(bodies)} letters")
    return out


def _layers(sheet: str, names: list[str], thr: int = 40) -> dict[str, Image.Image]:
    im = _open(sheet)
    if im is None:
        print("skip", sheet)
        return {}
    found = items(im, thr=thr, big_area=800)
    if len(found) < len(names):
        found = _split_gold_row(im, found, len(names) - len(found) + 1)
    owner = _own(found, np.asarray(im).shape[:2])
    cuts = [_trim(_cut(im, b, m, pad=10, owner=owner, index=i)) for i, (b, m) in enumerate(found)]
    print(sheet, len(cuts), "layers", [c.size for c in cuts])
    if len(cuts) != len(names):
        print(f"!! {sheet}: {len(cuts)} layers, expected {len(names)}")
    out = dict(zip(names, cuts))
    for n, im_ in out.items():
        _save(im_, BASE / "layers" / f"{n}.png")
    return out


def _compose(size, placed):
    """placed: [(image, cx, cy, scale)] -> RGBA canvas, plus layout json rows."""
    out = Image.new("RGBA", size)
    rows = {}
    for name, im, cx, cy, k in placed:
        im2 = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        out.alpha_composite(im2, (round(cx - im2.width / 2), round(cy - im2.height / 2)))
        rows[name] = {"x": round(cx, 1), "y": round(cy, 1), "w": im2.width, "h": im2.height}
    return out, rows


def logo_layers() -> None:
    """Letter-by-letter logo: the sheet's layers are re-assembled into a new
    logo.webp (so static and animated logo are the same drawing) and their
    placement goes to layers/logo.json for scripts/neon_joker_spins_fx.py."""
    import json
    names = ["plate", "hat", "bell1", "bell2", "bell3", "neon", "spins", "J", "O", "K", "E", "R"]
    L = _layers("logo_layers", names)
    if len(L) != len(names):
        return
    plate = L["plate"]
    W = 1500
    k = W * 0.9 / plate.width
    pw, ph = plate.width * k, plate.height * k
    hat_h = L["hat"].height * k * 0.75
    H = round(ph + hat_h * 0.9 + 40)
    cx, py = W / 2, H - ph / 2 - 20
    letters = ["J", "O", "K", "E", "R"]
    lk = ph * 0.46 / max(L[c].height for c in letters)
    gap = -0.04 * ph
    total = sum(L[c].width * lk for c in letters) + gap * 4
    x = cx - total / 2
    placed = [("plate", plate, cx, py, k), ("hat", L["hat"], cx, py - ph / 2 - hat_h * 0.25, k * 0.75)]
    nk = ph * 0.17 / L["neon"].height
    placed.append(("neon", L["neon"], cx, py - ph * 0.29, nk))
    for c in letters:
        w = L[c].width * lk
        placed.append((c, L[c], x + w / 2, py + ph * 0.02, lk))
        x += w + gap
    sk_ = ph * 0.17 / L["spins"].height
    placed.append(("spins", L["spins"], cx, py + ph * 0.32, sk_))
    hat = L["hat"]
    hw, hh = hat.width * k * 0.75, hat.height * k * 0.75
    hy = py - ph / 2 - hat_h * 0.25
    bk = hh * 0.22 / L["bell1"].height
    for i, (fx_, fy_) in enumerate(((-0.46, 0.05), (0.0, -0.42), (0.46, 0.05))):
        placed.append((f"bell{i + 1}", L[f"bell{i + 1}"], cx + fx_ * hw, hy + fy_ * hh, bk))
    logo, rows = _compose((W, H), placed)
    _save(_trim(logo), IMG / "logo.png")
    bb = logo.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    for r in rows.values():
        r["x"] -= bb[0]
        r["y"] -= bb[1]
    (BASE / "layers" / "logo.json").write_text(json.dumps({"size": [bb[2] - bb[0], bb[3] - bb[1]], "layers": rows}))
    print("logo assembled", bb)


def symbol_layers() -> None:
    """Layered WILD and JOKER scatter: new static tiles from the same layers
    the Spine clips animate, layout in layers/wild.json / scatter.json."""
    import json
    names = ["wild_w", "wild_word", "ring", "head", "head_laugh", "head_blink", "sbell1", "sbell2", "sbell3"]
    L = _layers("symbol_layers", names)
    if len(L) != len(names):
        return
    C = CELL
    # WILD: W big, word under it
    wk = C * 0.84 / L["wild_w"].width
    wwk = C * 0.6 / L["wild_word"].width
    wild, rows = _compose((C, C), [("wild_w", L["wild_w"], C / 2, C * 0.4, wk),
                                   ("wild_word", L["wild_word"], C / 2, C * 0.74, wwk)])
    _save(wild, SYM / "wild.png")
    (BASE / "layers" / "wild.json").write_text(json.dumps({"size": [C, C], "layers": rows}))
    # SCATTER: ring, head inside, bells on the hat tips
    rk = C * 0.86 / max(L["ring"].size)
    hk = C * 0.78 / max(L["head"].size)
    hw, hh = L["head"].width * hk, L["head"].height * hk
    placed = [("ring", L["ring"], C / 2, C / 2, rk), ("head", L["head"], C / 2, C * 0.5, hk)]
    bk = C * 0.11 / L["sbell1"].height
    for i, (fx_, fy_) in enumerate(((-0.42, -0.08), (0.02, -0.46), (0.44, -0.06))):
        placed.append((f"sbell{i + 1}", L[f"sbell{i + 1}"], C / 2 + fx_ * hw, C / 2 + fy_ * hh, bk))
    sc, rows = _compose((C, C), placed)
    _save(sc, SYM / "scatter.png")
    rows["head_laugh"] = dict(rows["head"])
    rows["head_blink"] = dict(rows["head"])
    (BASE / "layers" / "scatter.json").write_text(json.dumps({"size": [C, C], "layers": rows, "head_k": hk}))



def buy() -> None:
    """BUY button, lit + unlit (disabled), and the empty price strip as
    fractions of the button for the CSS (price = bitmap font)."""
    got = _sheet("buy", 2, thr=50)
    for name, im in zip(["buy_on", "buy_off"], got):
        im = _trim(im)
        k = min(1.0, 520 / im.width)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        _save(im, IMG / f"{name}.png")
        if name == "buy_on":
            rgb = np.asarray(im)[..., :3].astype(np.int32)
            a = np.asarray(im)[..., 3]
            dark = ((rgb.max(axis=2) < 60) & (a > 200)).astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=4)
            # the price strip: the widest dark region in the lower half
            cand = [i for i in range(1, n) if st[i, 1] > im.height * 0.5 and st[i, 2] > im.width * 0.4]
            i = max(cand, key=lambda q: st[q, 4])
            x, y, w, h = st[i, :4]
            print(f"  buy {im.size} strip left {x / im.width:.3f} top {y / im.height:.3f} "
                  f"w {w / im.width:.3f} h {h / im.height:.3f}")


FX_NAMES = ["spark", "orb_pink", "orb_cyan", "confetti", "ribbon", "zap",
            "coin_edge", "burst", "ring_pink", "ring_cyan", "spade", "heart"]


def fx() -> None:
    """Additive sprites: alpha = brightness, max 256px."""
    got = _sheet("fx", 12, thr=30, glow_idx=tuple(range(12)))
    for name, im in zip(FX_NAMES, got):
        im = _trim(im)
        k = min(1.0, 256 / max(im.size))
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        _save(im, BASE / "fx" / f"{name}.png")


GLYPHS = "0123456789x.,km"


def glyphs() -> None:
    """Bitmap font for coin values / collector sums: one image per glyph, all
    on a common cap-height canvas (height 120) so the client just lines them
    up; widths go to glyphs.json."""
    im = _open("glyphs")
    if im is None:
        print("skip glyphs")
        return
    found = items(im, thr=60, big_area=300)
    # The dot and comma sit low, so the row grouping splits the last row —
    # it is one row; order it left to right.
    found = found[:10] + sorted(found[10:], key=lambda it: it[0][0])
    if len(found) != len(GLYPHS):
        print(f"!! glyphs: {len(found)} items, expected {len(GLYPHS)}")
    cap = max(b[3] - b[1] for b, _ in found[:10])
    scale = 120 / cap
    widths = {}
    for ch, (b, m) in zip(GLYPHS, found):
        # Holes (0 6 8 9) are black INSIDE the glyph — key every near-black
        # pixel, not just the border-connected ones.
        bx = _pad(b, 4, *im.size)
        crop = np.asarray(im.crop(bx)).astype(np.float32)
        a = np.clip((crop.max(axis=2) - 14) * 8, 0, 255)
        mk = cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8))[bx[1]:bx[3], bx[0]:bx[2]]
        g = _trim(Image.fromarray(np.dstack([crop, a * (mk > 0)]).astype(np.uint8), "RGBA"))
        g = g.resize((max(1, round(g.width * scale)), max(1, round(g.height * scale))), Image.LANCZOS)
        name = {".": "dot", ",": "comma"}.get(ch, ch)
        _save(g, BASE / "glyphs" / f"{name}.png")
        widths[ch] = [g.width, g.height]
    import json
    (BASE / "glyphs" / "glyphs.json").write_text(json.dumps(widths))


def frame() -> None:
    _frame("frame", "frame")
    _frame("frame_mob", "frame_mob")


def _frame(src: str, out: str) -> None:
    """Cabinet with a see-through reel window: the near-black INSIDE the
    window goes transparent (the dividers and bulbs stay), and the window box
    is printed for the CSS."""
    im = _open(src)
    if im is None:
        print("skip", src)
        return
    k = key_black(im)
    rgb = np.asarray(im).astype(np.int32)
    mx = rgb.max(axis=2)
    h, w = mx.shape
    # The window: the big enclosed dark region around the image centre.
    dark = (mx < 40).astype(np.uint8)
    _, lab = cv2.connectedComponents(dark, connectivity=4)
    c = lab[h // 2, w // 2]
    # 9 cells are separate regions split by dividers — take every dark region
    # whose bbox lies inside the cyan border and is large.
    n, lab2, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=4)
    cells = [i for i in range(1, n) if stats[i, 4] > (w * h) * 0.02 and stats[i, 0] > 0 and stats[i, 1] > 0
             and stats[i, 0] + stats[i, 2] < w and stats[i, 1] + stats[i, 3] < h]
    win = np.isin(lab2, cells)
    ys, xs = np.nonzero(win)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    print("frame cells", len(cells), "window box", box, "image", (w, h), "centre label", c)
    # Transparent inside the window; the glow of the dividers fades like a halo.
    a = np.asarray(k)[..., 3].astype(np.float32)
    x0, y0, x1, y1 = box
    inner = np.zeros_like(win)
    inner[y0:y1, x0:x1] = True
    glow = np.clip((mx - 30) * 2.2, 0, 255)
    a = np.where(inner, np.minimum(a, glow), a)
    k.putalpha(Image.fromarray(a.astype(np.uint8)))
    tx0, ty0, tx1, ty1 = k.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    k = k.crop((tx0, ty0, tx1, ty1))
    tw, th = tx1 - tx0, ty1 - ty0
    _save(k, IMG / f"{out}.png")
    print(f"{out} {k.size} WINDOW fractions: left {(x0 - tx0) / tw:.4f} top {(y0 - ty0) / th:.4f} "
          f"width {(x1 - x0) / tw:.4f} height {(y1 - y0) / th:.4f}")


def logo() -> None:
    im = _open("logo")
    if im is not None:
        _save(_trim(key_black(im)), IMG / "logo.png")


def mascot() -> None:
    im = _open("mascot")
    if im is None:
        return
    from rembg import new_session, remove
    cut = remove(im, session=new_session("birefnet-general"))
    body = np.asarray(cut)[..., 3].astype(np.float32)
    # rembg drops the neon rim glow — add it back from the luminance key.
    glow = np.asarray(key_black(im))[..., 3].astype(np.float32)
    near = cv2.dilate((body > 30).astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
    a = np.where(near, np.maximum(body, glow * 0.85), 0)
    rgb = np.asarray(key_black(im))[..., :3]
    rgb = np.where((body > 200)[..., None], np.asarray(im), rgb)
    _save(_trim(Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")), IMG / "mascot.png")


def backgrounds() -> None:
    for name in ("bg_base", "bg_fs", "bg_base_mob", "bg_fs_mob"):
        im = _open(name)
        if im is None:
            print("skip", name)
            continue
        out = IMG / f"{name}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, quality=86, optimize=True, progressive=True)
        print("wrote", out.relative_to(ROOT), im.size)


def blur() -> None:
    """Motion-blur twins for js/reel-spin.js: `<code>_blur.webp` next to each
    symbol — vertical-only gaussian, sigma 3.3% of the height (same as
    scripts/make_reel_blur.py), on premultiplied alpha so edges don't darken."""
    sigma = 0.033 * CELL
    r = int(round(sigma * 3))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2 * sigma * sigma))
    k /= k.sum()
    for f in sorted(SYM.glob("*.webp")):
        if f.stem.endswith("_blur"):
            continue
        a = np.asarray(Image.open(f).convert("RGBA")).astype(np.float32) / 255
        pm = np.dstack([a[..., :3] * a[..., 3:], a[..., 3:]])
        pad = np.pad(pm, ((r, r), (0, 0), (0, 0)), mode="constant")
        out = sum(k[i] * pad[i:i + pm.shape[0]] for i in range(len(k)))
        al = out[..., 3:]
        rgb = np.where(al > 1e-4, out[..., :3] / np.maximum(al, 1e-4), 0)
        im = Image.fromarray((np.dstack([rgb, al]) * 255).clip(0, 255).astype(np.uint8), "RGBA")
        _save(im, SYM / f"{f.stem}_blur.png")


def cover() -> None:
    """Lobby cover 900x563 (GDD §3.5): joker big on the right, neon logo on
    the left, the four jackpot plates along the bottom — all from the cut art."""
    W, H = 900, 563
    bg = Image.open(IMG / "bg_base.jpg").convert("RGBA")
    k = max(W / bg.width, H / bg.height)
    bg = bg.resize((round(bg.width * k), round(bg.height * k)), Image.LANCZOS)
    out = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    shade = Image.new("RGBA", (W, H), (18, 8, 31, 110))
    out.alpha_composite(shade)
    m = Image.open(IMG / "mascot.webp")
    m = m.resize((round(m.width * 620 / m.height), 620), Image.LANCZOS)
    out.alpha_composite(m, (W - m.width - 10, 10))
    logo = Image.open(IMG / "logo.webp")
    logo = logo.resize((520, round(logo.height * 520 / logo.width)), Image.LANCZOS)
    out.alpha_composite(logo, (30, 40))
    x = 26
    for tier in ("mini", "minor", "major", "grand"):
        p = Image.open(IMG / f"jp_{tier}.webp")
        w = 190 if tier == "grand" else 150
        p = p.resize((w, round(p.height * w / p.width)), Image.LANCZOS)
        out.alpha_composite(p, (x, H - p.height - 34))
        x += w + 6
    out.convert("RGB").save(IMG / "cover.jpg", quality=88, optimize=True, progressive=True)
    print("wrote cover.jpg")


if __name__ == "__main__":
    import sys
    parts = sys.argv[1:] or ["symbols", "coins", "glyphs", "plates", "fx", "popups", "frame", "logo", "mascot", "backgrounds", "blur", "cover"]
    for p in parts:
        globals()[p]()
