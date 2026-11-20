"""Cut the popup title sheets into <variant>/pop/{big,mega,epic,mini,minor,major,grand}.webp.
    olympus_pop_titles.py WIN_SHEET.png JP_SHEET.png VARIANT
Titles are found as alpha islands after a strong dilation (a jackpot word and its small JACKPOT line merge)."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "front/img/olympus-thunder" / sys.argv[3] / "pop"; out.mkdir(parents=True, exist_ok=True)


def cut(sheet, names):
    """split at the len(names)-1 widest fully-empty row runs (gaps between titles are wider than the gap
    between a jackpot word and its JACKPOT line), then trim each band"""
    im = Image.open(sheet).convert("RGBA"); a = np.array(im); a[..., 3] = np.where(a[..., 3] < 14, 0, a[..., 3])
    empty = (a[..., 3] > 30).sum(1) == 0
    runs, y = [], 0
    while y < len(empty):
        if empty[y]:
            y0 = y
            while y < len(empty) and empty[y]: y += 1
            if y0 > 0 and y < len(empty): runs.append((y - y0, (y0 + y) // 2))
        else: y += 1
    cuts = sorted(c for _, c in sorted(runs, reverse=True)[:len(names) - 1])
    prof = (a[..., 3] > 30).sum(1)
    while len(cuts) < len(names) - 1:   # glow touching: split the tallest band at its thinnest row near the middle
        edges = [0] + cuts + [a.shape[0]]
        k = max(range(len(edges) - 1), key=lambda i: edges[i + 1] - edges[i]); y0, y1 = edges[k], edges[k + 1]
        lo, hi = y0 + (y1 - y0) * 3 // 10, y0 + (y1 - y0) * 7 // 10
        cuts = sorted(cuts + [lo + int(np.argmin(prof[lo:hi]))])
    for name, y0, y1 in zip(names, [0] + cuts, cuts + [a.shape[0]]):
        t = Image.fromarray(a[y0:y1]); t = t.crop(t.getbbox()); t.thumbnail((1100, 520), Image.LANCZOS)
        t.save(out / f"{name}.webp", "WEBP", quality=92, method=6); print(sys.argv[3], name, t.size)


cut(sys.argv[1], ["big", "mega", "epic"])
cut(sys.argv[2], ["mini", "minor", "major", "grand"])
