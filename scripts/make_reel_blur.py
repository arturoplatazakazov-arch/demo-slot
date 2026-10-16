"""Pre-blurred symbol twins for js/reel-spin.js (the Gangsta Casino spin).

For every reel symbol static of the listed games writes `<name>_blur.png`
next to it: same canvas, vertical-only gaussian (motion blur along the reel),
sigma ~3.3% of the image height — Gangsta's own twins are sigma 7 on a ~210px
tile. Alpha is premultiplied before blurring so edges don't go dark.

Symbol folders are read straight from each game's slot.js (SYMBOL_FOLDERS +
SYMBOL_STATIC_OVERRIDE), so a new symbol only needs a re-run.

    .venv/bin/python scripts/make_reel_blur.py
"""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

FRONT = Path(__file__).resolve().parent.parent / 'front'
SIGMA_FRAC = 0.033

# game slot.js -> path template ({folder}, {file})
GAMES = {
    'js/slot.js': 'img/amys-fruit-farm/Export/{folder}/{file}',
    'js/neon-reels/slot.js': 'img/neon-reels/Export/{folder}/{file}',
    'js/wild-western-story/slot.js': 'img/wild-western-story/Export/{folder}/{file}',
    'js/lucky-joker-3h3/slot.js': 'img/lucky-joker-3h3/{folder}/{file}',
    'js/multi-fruits-story/slot.js': 'img/multi-fruits-story/{folder}/{file}',
    'js/east-discovery/slot.js': 'img/east-discovery/Export/{folder}/{file}',
    'js/dirty-money-mafia/slot.js': 'img/dirty-money-mafia/{folder}/{file}',
}
PAIR = re.compile(r"""(?:^|[{,])\s*['"]?(\w+)['"]?\s*:\s*'([^']+)'""", re.M)


def js_dict(src, name):
    m = re.search(r'const ' + name + r' = \{(.*?)\n\};', src, re.S)
    return dict(PAIR.findall(m.group(1))) if m else {}


def gauss_kernel(sigma):
    r = max(1, int(round(sigma * 3)))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2 * sigma * sigma))
    return k / k.sum()


def blur_vertical(img, sigma):
    a = np.asarray(img.convert('RGBA'), dtype=np.float32) / 255.0
    alpha = a[..., 3:4]
    pre = np.concatenate([a[..., :3] * alpha, alpha], axis=2)
    k = gauss_kernel(sigma)
    r = len(k) // 2
    padded = np.pad(pre, ((r, r), (0, 0), (0, 0)))
    out = np.zeros_like(pre)
    for i, w in enumerate(k):
        out += w * padded[i:i + pre.shape[0]]
    al = out[..., 3:4]
    rgb = np.where(al > 1e-4, out[..., :3] / np.maximum(al, 1e-4), 0)
    res = np.concatenate([np.clip(rgb, 0, 1), np.clip(al, 0, 1)], axis=2)
    return Image.fromarray((res * 255 + 0.5).astype(np.uint8), 'RGBA')


def main():
    total = 0
    for js, tmpl in GAMES.items():
        src = (FRONT / js).read_text()
        folders = js_dict(src, 'SYMBOL_FOLDERS')
        overrides = js_dict(src, 'SYMBOL_STATIC_OVERRIDE')
        for code, folder in folders.items():
            path = FRONT / tmpl.format(folder=folder, file=overrides.get(code, 'static.png'))
            if not path.exists():
                print('  missing', path.relative_to(FRONT), file=sys.stderr)
                continue
            out = path.with_name(path.stem + '_blur.png')
            img = Image.open(path)
            blurred = blur_vertical(img, max(1.0, SIGMA_FRAC * img.height))
            # A blurred tile has no hard detail: 256 colours are plenty and
            # cut the files ~3x (it's only on screen mid-spin).
            blurred.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(out, optimize=True)
            total += out.stat().st_size
            print(f'{out.relative_to(FRONT)}  {img.size[0]}x{img.size[1]}  {out.stat().st_size // 1024} KB')
    print(f'total {total // 1024} KB')


if __name__ == '__main__':
    main()
