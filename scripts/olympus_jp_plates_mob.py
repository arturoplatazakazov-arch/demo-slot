"""Mobile jackpot plates at their real proportions (no CSS stretching): keep both end caps of ui/plate_light.webp
untouched and fit only the marble middle — stretched for the wide GRAND plate, trimmed for the small ones.
    olympus_jp_plates_mob.py VARIANT CAP_FRACTION      -> ui/plate_mob_grand.webp (6.25:1), ui/plate_mob_small.webp (2.16:1)"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
v, capf = sys.argv[1], float(sys.argv[2])
ui = ROOT / "front/img/olympus-thunder" / v / "ui"
src = Image.open(ui / "plate_light.webp").convert("RGBA")
w, h = src.size; c = int(w * capf)
left, right, mid = src.crop((0, 0, c, h)), src.crop((w - c, 0, w, h)), src.crop((c, 0, w - c, h))
for name, ratio in (("plate_mob_grand", 600 / 96), ("plate_mob_small", 195 / 90)):
    W = round(ratio * h); m = W - 2 * c
    if m >= mid.size[0]:
        body = mid.resize((m, h), Image.LANCZOS)
    else:
        x0 = (mid.size[0] - m) // 2; body = mid.crop((x0, 0, x0 + m, h))
    # the body is laid under a little overlap and the caps fade into it (no visible seam in the marble)
    k = max(8, c // 4)
    out = Image.new("RGBA", (W, h)); out.paste(body.resize((m + 2 * k, h), Image.LANCZOS), (c - k, 0))
    import numpy as np
    for cap, x, ramp in ((left, 0, np.r_[np.ones(c - k), np.linspace(1, 0, k)]), (right, W - c, np.r_[np.linspace(0, 1, k), np.ones(c - k)])):
        ca = np.array(cap).astype(float); base = np.array(out.crop((x, 0, x + c, h))).astype(float)
        t = ramp[None, :, None]; mix = ca * t + base * (1 - t)
        mix[..., 3] = np.maximum(ca[..., 3] * ramp[None, :], base[..., 3])
        out.paste(Image.fromarray(mix.astype(np.uint8)), (x, 0))
    out.save(ui / f"{name}.webp", "WEBP", quality=92, method=6)
    print(v, name, out.size, round(W / h, 2))
