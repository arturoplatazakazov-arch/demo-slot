"""Lower a bonus background by D (fraction of height): rows below A move down by D, the top band 0..A is
stretched to 0..A+D (vault / arch tops), the bottom D (floor, under the UI bar) is dropped.
Per-row remap with linear interpolation (no seam).   olympus_fs_lower.py SRC.png DST.jpg WIDTH A D"""
import sys
import numpy as np
from PIL import Image
src, dst, W, A, D = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
im = Image.open(src).convert("RGB"); im = im.resize((W, round(im.size[1] * W / im.size[0])), Image.LANCZOS)
arr = np.array(im).astype(np.float32); h = arr.shape[0]; a, d = A * h, D * h
y = np.arange(h, dtype=np.float32)
s = np.where(y < a + d, y * a / (a + d), y - d)          # source row for every output row
s0 = np.clip(np.floor(s).astype(int), 0, h - 1); s1 = np.clip(s0 + 1, 0, h - 1); t = (s - s0)[:, None, None]
out = arr[s0] * (1 - t) + arr[s1] * t
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dst, quality=86)
print(dst, arr.shape[1], h, "A", int(a), "D", int(d))
