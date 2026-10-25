import sys, numpy as np
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
im = np.asarray(Image.open(src).convert('RGBA')).astype(float)
CX, CY, R_OUT, R_IN = 112.5, 93.75, 30.5, 23.5
x0, y0 = int(CX - 34), int(CY - 34)
crop = im[y0:y0 + 68, x0:x0 + 68].copy()
yy, xx = np.mgrid[0:68, 0:68]
r = np.hypot(xx + x0 + 0.5 - CX, yy + y0 + 0.5 - CY)
# hub with the G, cut round (soft 1px edge)
a_out = np.clip(R_OUT + 0.5 - r, 0, 1)
g = crop.copy(); g[..., 3] *= a_out
Image.fromarray(g.astype(np.uint8)).save(f'{out}/mult_hub_g.png')
# blank hub: the dark well filled over the letter, a soft inner shade
blank = g.copy()
t = np.clip(r / R_IN, 0, 1)
well = np.stack([58 - 30 * t, 58 - 30 * t, 64 - 32 * t], -1)
k = np.clip(R_IN + 0.5 - r, 0, 1)[..., None]
blank[..., :3] = blank[..., :3] * (1 - k) + well * k
Image.fromarray(blank.astype(np.uint8)).save(f'{out}/mult_hub_blank.png')
print('ok')
