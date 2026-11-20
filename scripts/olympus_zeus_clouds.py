"""Cut the ChatGPT cloud-bank sheet (3 banks stacked) into <variant>/zeus_clouds/c1..c3.webp — floating layers
under Zeus' waist.   olympus_zeus_clouds.py SHEET.png VARIANT"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
im = Image.open(sys.argv[1]).convert("RGBA")
out = ROOT / "front/img/olympus-thunder" / sys.argv[2] / "zeus_clouds"
out.mkdir(parents=True, exist_ok=True)
arr = np.array(im); arr[..., 3] = np.where(arr[..., 3] < 12, 0, arr[..., 3]); im = Image.fromarray(arr)
prof = ndimage.uniform_filter1d((arr[..., 3] > 60).sum(1).astype(float), 9)
h = len(prof); cuts = [int(h * (k - .3) / 3) + int(np.argmin(prof[int(h * (k - .3) / 3): int(h * (k + .3) / 3)])) for k in (1, 2)]
for i, (y0, y1) in enumerate(zip([0] + cuts, cuts + [h])):
    c = im.crop((0, y0, im.size[0], y1)); c = c.crop(c.getbbox())
    c.thumbnail((900, 300), Image.LANCZOS)
    c.save(out / f"c{i + 1}.webp", "WEBP", quality=88, method=6)
    print(sys.argv[2], i + 1, c.size)
