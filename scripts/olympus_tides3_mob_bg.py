"""Tides 3 portrait background: lift the temple island to the Tides 2 height (dome ~0.62 H) and enlarge it 1.25x.
The lower band (from 0.58 H) is scaled about the centre and pasted higher with a soft blend into the sky.

    olympus_tides3_mob_bg.py ~/ot2-work/h3/S/bg_mob_b.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
src = Image.open(sys.argv[1]).convert("RGB").resize((1080, 1919), Image.LANCZOS)
W, H = src.size
TOP, K, Y0, FADE = 0.58, 1.25, 0.47, 0.09
band = src.crop((0, int(TOP * H), W, H))
bw, bh = int(W * K), int(band.size[1] * K)
band = band.resize((bw, bh), Image.LANCZOS).crop(((bw - W) // 2, 0, (bw - W) // 2 + W, bh))
out = src.copy()
y0 = int(Y0 * H)
band = band.crop((0, 0, W, min(bh, H - y0)))
mask = np.ones((band.size[1], W), np.float32)
f = int(FADE * H)
mask[:f] = np.linspace(0, 1, f)[:, None] ** 1.5
out.paste(band, (0, y0), Image.fromarray((mask * 255).astype(np.uint8)))
if y0 + band.size[1] < H:   # fill a sliver at the very bottom (hidden by the bar) by stretching the last rows
    rest = out.crop((0, y0 + band.size[1] - 40, W, y0 + band.size[1])).resize((W, H - y0 - band.size[1] + 40))
    out.paste(rest, (0, y0 + band.size[1] - 40))
out.save(ROOT / "front/img/olympus-thunder/tides3/sky_mob_b.jpg", quality=86)
out.save(ROOT / "front/img/olympus-thunder/tides3/sky_mob.jpg", quality=86)
print("ok", out.size)
