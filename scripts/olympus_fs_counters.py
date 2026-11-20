"""Bonus counter plates (free spins / win / multiplier) -> <variant>/ui/cnt_fs|cnt_win|cnt_mult.webp, all 2:1.
    olympus_fs_counters.py SHEET.png VARIANT rows|row
'rows' = 3 long plates stacked (Tides 2 art, ~5:1): each is shortened to 2:1 by keeping both end caps and the
centre with the emblem and dropping straight frame in between; 'row' = 3 plates side by side, already ~2:1."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sheet, var, mode = sys.argv[1], sys.argv[2], sys.argv[3]
im = Image.open(sheet).convert("RGBA")
a = np.array(im); a[..., 3] = np.where(a[..., 3] < 16, 0, a[..., 3]); im = Image.fromarray(a)
m = ndimage.binary_dilation(a[..., 3] > 60, iterations=6)
lab, n = ndimage.label(m); sizes = ndimage.sum(m, lab, range(1, n + 1))
keep = np.argsort(sizes)[::-1][:3] + 1
boxes = []
for i in keep:
    ys, xs = np.where((lab == i) & (a[..., 3] > 16)); boxes.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
boxes.sort(key=(lambda b: b[1]) if mode == "rows" else (lambda b: b[0]))
out = ROOT / "front/img/olympus-thunder" / var / "ui"
for name, b in zip(["cnt_fs", "cnt_win", "cnt_mult"], boxes):
    p = im.crop(b); w, h = p.size
    if w > 2.15 * h:
        c = int(0.40 * h); mid = 2 * h - 2 * c; cx = w // 2
        q = Image.new("RGBA", (2 * h, h))
        q.paste(p.crop((0, 0, c, h)), (0, 0))
        q.paste(p.crop((cx - mid // 2, 0, cx - mid // 2 + mid, h)), (c, 0))
        q.paste(p.crop((w - c, 0, w, h)), (c + mid, 0))
        p = q
    p.thumbnail((640, 360), Image.LANCZOS)
    p.save(out / f"{name}.webp", "WEBP", quality=90, method=6)
    print(var, name, p.size, round(p.size[0] / p.size[1], 2))
