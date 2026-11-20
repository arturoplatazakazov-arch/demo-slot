"""Olympus Thunder · Tides 2 (client feedback iteration) — cut ChatGPT sheets into game assets.

    ~/.venvs/art/bin/python scripts/olympus_tides2_art.py RAW_DIR [jobs...]

RAW_DIR holds S/*.png (scene chat) and Y/*.png (symbols chat); pick_<name>.png overrides <name>.png.
Writes front/img/olympus-thunder/tides2/ (+ layout.json with the frame 9-slice insets).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
import os
OUT = ROOT / "front/img/olympus-thunder" / os.environ.get("OT_VAR", "tides2")   # OT_VAR=tides3 for the ref-style variant
RAW = Path(sys.argv[1])
JOBS = sys.argv[2:] or ["symbols", "frame", "bg", "clouds", "hero", "plates"]


def raw(chat, name):
    p = RAW / chat / f"pick_{name}.png"
    return Image.open(p if p.exists() else RAW / chat / f"{name}.png").convert("RGBA")


def pieces(im, n, thr=40, grow=6, rows=True, floor=0):
    """n largest alpha islands (after a small dilation) as RGBA crops, in reading order.
    Pixels of other islands are cleared; alpha below `floor` is dropped (ChatGPT haze)."""
    arr = np.array(im)
    if floor:
        arr[:, :, 3] = np.where(arr[:, :, 3] < floor, 0, arr[:, :, 3])
    a = arr[:, :, 3] > thr
    m = ndimage.binary_dilation(a, iterations=grow)
    lab, k = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, k + 1))
    keep = np.argsort(sizes)[::-1][:n] + 1
    items = []
    for i in keep:
        ys, xs = np.where((lab == i) & a)
        items.append(((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1), i))
    h = im.size[1]
    key = (lambda t: (round((t[0][1] + t[0][3]) / 2 / (h / 3)), t[0][0])) if rows else (lambda t: t[0][0])
    items.sort(key=key)
    out = []
    for (x0, y0, x1, y1), i in items:
        own = ndimage.binary_dilation(lab == i, iterations=grow * 2)
        c = arr.copy(); c[:, :, 3] = np.where(own, c[:, :, 3], 0)
        out.append(Image.fromarray(c).crop((x0, y0, x1, y1)))
    return out


def square(im, pad=0.04, size=320):
    w, h = im.size
    s = int(max(w, h) * (1 + 2 * pad))
    c = Image.new("RGBA", (s, s))
    c.alpha_composite(im, ((s - w) // 2, (s - h) // 2))
    return c.resize((size, size), Image.LANCZOS)


def save(im, rel, q=90):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if rel.endswith(".jpg"):
        im.convert("RGB").save(p, quality=q)
    else:
        im.save(p, "WEBP", quality=q, method=6)
    print("  ", rel, im.size)


def symbols():
    hp = pieces(raw("Y", "hp"), 4)
    for name, im in zip(["helmet", "lyre", "amphora", "wreath"], hp):
        for d in ("symbols", "symbols_letters"):
            save(square(im), f"{d}/{name}.webp")
    sp = pieces(raw("Y", "specials"), 3, rows=False)
    for name, im in zip(["orb", "eagle", "scatter"], sp):
        for d in ("symbols", "symbols_letters"):
            save(square(im, pad=0.02), f"{d}/{name}.webp")
    lows = ["citrine", "emerald", "ruby", "amethyst", "sapphire"]   # yellow, green, pink, white, blue
    for name, im in zip(lows, pieces(raw("Y", "lp_gems"), 5, rows=False, floor=30)):
        save(square(im, pad=0.16), f"symbols/{name}.webp")
    for name, im in zip(lows, pieces(raw("Y", "lp_letters"), 5, grow=2, rows=False, floor=45)):
        save(square(im, pad=0.12), f"symbols_letters/{name}.webp")


def frame():
    im = raw("S", "frame")
    a = np.array(im)[:, :, 3] > 60
    ys, xs = np.where(a)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    im = im.crop((x0, y0, x1, y1))
    a = np.array(im)[:, :, 3] > 60
    h, w = a.shape
    # border thickness = first transparent run from each edge along the middle lines
    def run(v):  # opaque run from the edge (skip a soft outer fringe first)
        i = int(np.argmax(v)); return i + int(np.argmax(~v[i:]))
    mid_r, mid_c = a[h // 2], a[:, w // 2]
    left, right, top, bottom = run(mid_r), run(mid_r[::-1]), run(mid_c), run(mid_c[::-1])
    # corner caps are bigger than the band: slice at the cap size
    cap = 0
    for y in range(h // 4):
        row = a[y]
        run = int(np.argmax(~row[: w // 4])) if not row[: w // 4].all() else w // 4
        cap = max(cap, run if row[0] else 0)
    s = max(left, right, top, bottom, cap) + 2
    save(im, "frame.webp", q=92)
    return {"frame": {"w": w, "h": h, "band": [top, right, bottom, left], "slice": s}}


def bg():
    d = raw("S", "bg_desk"); d = d.resize((1920, round(d.size[1] * 1920 / d.size[0])), Image.LANCZOS)
    save(d, "sky.jpg", q=86)
    m = raw("S", "bg_mob"); m = m.resize((1080, round(m.size[1] * 1080 / m.size[0])), Image.LANCZOS)
    save(m, "sky_mob.jpg", q=86)
    for k in ("a", "b"):   # mobile backgrounds with a filled lower third (client: "the bottom is empty")
        if (RAW / "S" / f"bg_mob_{k}.png").exists():
            m = raw("S", f"bg_mob_{k}"); m = m.resize((1080, round(m.size[1] * 1080 / m.size[0])), Image.LANCZOS)
            save(m, f"sky_mob_{k}.jpg", q=86)


def bands(im, n):
    """split a vertical stack at the n-1 deepest valleys of the row alpha profile"""
    a = np.array(im)[:, :, 3].astype(float)
    prof = ndimage.uniform_filter1d((a > 90).sum(1).astype(float), 15)
    h = len(prof); cuts = []
    for k in range(1, n):
        lo, hi = int(h * (k - .45) / n), int(h * (k + .45) / n)
        cuts.append(lo + int(np.argmin(prof[lo:hi])))
    ys = [0] + cuts + [h]
    out = []
    for y0, y1 in zip(ys, ys[1:]):
        c = im.crop((0, y0, im.size[0], y1)); al = np.array(c)[:, :, 3] > 8
        yy, xx = np.where(al); out.append(c.crop((xx.min(), yy.min(), xx.max() + 1, yy.max() + 1)))
    return out


def clouds():
    for i, im in enumerate(bands(raw("S", "clouds"), 4)):
        im.thumbnail((1400, 600), Image.LANCZOS)
        save(im, f"clouds/cloud{i + 1}.webp", q=86)


def hero():
    for src, out in (("hero", "hero.webp"), ("hero_b", "hero_b.webp")):
        if not (RAW / "S" / f"{src}.png").exists():
            continue
        im = raw("S", src)
        a = np.array(im)[:, :, 3] > 10
        ys, xs = np.where(a)
        im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        save(im, out, q=90)


def plates():
    for name, im in zip(["plate_light", "plate_dark"], pieces(raw("S", "plates"), 2)):
        save(im, f"ui/{name}.webp", q=92)


layout_p = OUT / "layout.json"
layout = json.loads(layout_p.read_text()) if layout_p.exists() else {}
for j in JOBS:
    print(j)
    r = globals()[j]()
    if isinstance(r, dict):
        layout.update(r)
OUT.mkdir(parents=True, exist_ok=True)
layout_p.write_text(json.dumps(layout, indent=1))
print(json.dumps(layout))
