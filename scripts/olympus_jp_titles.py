"""Cut the ChatGPT jackpot-title sheets (GRAND / MAJOR / MINOR / MINI stacked) into ui/jp_<tier>.webp.

    olympus_jp_titles.py SHEET.png VARIANT      e.g. ~/ot2-work/raw/Y2/jp_titles.png tides2
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
im = Image.open(sys.argv[1]).convert("RGBA")
out = ROOT / "front/img/olympus-thunder" / sys.argv[2] / "ui"
a = np.array(im)[:, :, 3].astype(float)
prof = ndimage.uniform_filter1d((a > 90).sum(1).astype(float), 9)
h = len(prof); cuts = []
for k in range(1, 4):
    lo, hi = int(h * (k - .4) / 4), int(h * (k + .4) / 4)
    cuts.append(lo + int(np.argmin(prof[lo:hi])))
for name, y0, y1 in zip(["grand", "major", "minor", "mini"], [0] + cuts, cuts + [h]):
    c = im.crop((0, y0, im.size[0], y1)); al = np.array(c)[:, :, 3] > 10
    ys, xs = np.where(al); c = c.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    c.thumbnail((640, 200), Image.LANCZOS)
    c.save(out / f"jp_{name}.webp", "WEBP", quality=92, method=6)
    print(name, c.size, round(c.size[0] / c.size[1], 2))
