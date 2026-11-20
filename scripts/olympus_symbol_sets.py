"""Cut 5 premium-level symbol sets (ChatGPT sheets, 4 highs on top, 3 specials below) for the
olympus-symbol-sets.html showcase page.  Usage: olympus_symbol_sets.py ~/ot2-work/raw/sets"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "front/img/olympus-thunder/sets"
RAW = Path(sys.argv[1])
TOP = ["helmet", "lyre", "amphora", "wreath"]
BOT = ["orb", "eagle", "scatter"]


def islands(arr, n, thr=40, grow=4):
    a = arr[:, :, 3] > thr
    m = ndimage.binary_dilation(a, iterations=grow)
    lab, k = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, k + 1))
    keep = np.argsort(sizes)[::-1][:n] + 1
    out = []
    for i in keep:
        ys, xs = np.where((lab == i) & a)
        own = ndimage.binary_dilation(lab == i, iterations=grow * 2)
        c = arr.copy(); c[:, :, 3] = np.where(own, c[:, :, 3], 0)
        out.append((xs.min(), Image.fromarray(c).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))))
    return [im for _, im in sorted(out, key=lambda t: t[0])]


def valley(prof, lo, hi):
    return lo + int(np.argmin(prof[lo:hi]))


def cells(arr, n, thr=150):
    """Cut a row into n cells at the emptiest columns near the even split (glow and arcs of the
    richer sets touch their neighbours, so alpha islands merge), then trim each cell to its
    alpha box. Soft glow crossing a cut is simply clipped."""
    w = arr.shape[1]
    prof = (arr[:, :, 3] > thr).sum(0)
    cuts = [0] + [valley(prof, int(w * (k - 0.3) / n), int(w * (k + 0.3) / n)) for k in range(1, n)] + [w]
    out = []
    for x0, x1 in zip(cuts, cuts[1:]):
        c = arr[:, x0:x1]
        ys, xs = np.where(c[:, :, 3] > 12)
        out.append(Image.fromarray(c).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
    return out


def square(im, pad=0.03, size=384):
    w, h = im.size
    s = int(max(w, h) * (1 + 2 * pad))
    c = Image.new("RGBA", (s, s))
    c.alpha_composite(im, ((s - w) // 2, (s - h) // 2))
    return c.resize((size, size), Image.LANCZOS)


for t in range(1, 6):
    arr = np.array(Image.open(RAW / f"t{t}.png").convert("RGBA"))
    arr[:, :, 3] = np.where(arr[:, :, 3] < 20, 0, arr[:, :, 3])   # drop ChatGPT haze
    rows = (arr[:, :, 3] > 40).sum(1)
    h = len(rows)
    mid = h // 3 + int(np.argmin(rows[h // 3: 2 * h // 3]))     # emptiest line between the rows
    parts = cells(arr[:mid], 4) + cells(arr[mid:], 3)
    for name, im in zip(TOP + BOT, parts):
        p = OUT / f"t{t}" / f"{name}.webp"
        p.parent.mkdir(parents=True, exist_ok=True)
        square(im).save(p, "WEBP", quality=90, method=6)
        print(p.relative_to(ROOT), im.size)
