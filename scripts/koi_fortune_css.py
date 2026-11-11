"""Koi Fortune: the four variant stylesheets, built from the Savannah Kings one.

front/css/savannah-carved.css is the donor (stage, reels, plaques, popups,
buy window, bar). Each variant gets a copy with its own art folder, symbol
masks, measured frame/plaque geometry (scripts/koi_fortune_art.py prints
them) and palette; the game's own rules (coins, Hold & Win, Ante) live in
front/css/koi-fortune.css, loaded after it.

    .venv/bin/python scripts/koi_fortune_css.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DONOR = ROOT / 'front/css/savannah-carved.css'
CODES = ['wild', 'scatter', 'coin', 'jpcoin', 'koi', 'turtle', 'lantern', 'lotus', 'a', 'k', 'q', 'j']

VARIANTS = {
    'koi-fortune-silk': {
        'frame': (0.0922, 0.1439, 0.8156, 0.7446),
        'jp': {'grand': (0.130, 0.130, 0.265, 0.115), 'major': (0.134, 0.136, 0.468, 0.175),
               'minor': (0.134, 0.134, 0.429, 0.197), 'mini': (0.144, 0.146, 0.385, 0.164)},
        'palette': '''
:root {
  --glass: linear-gradient(180deg, rgba(70, 12, 14, 0.9), rgba(26, 4, 6, 0.95));
  --hairline: inset 0 1px 0 rgba(255, 220, 140, 0.55), inset 0 0 0 1.5px rgba(255, 200, 90, 0.3);
  --wine: #5a0e14;
  --reel-a: rgba(92, 16, 22, 0.86); --reel-b: rgba(30, 4, 8, 0.94); --reel-line: rgba(255, 200, 120, 0.13);
}
html, body { background: #140304; }''',
    },
    'koi-fortune-jade': {
        'frame': (0.0834, 0.1581, 0.8338, 0.7439),
        'jp': {'major': (0.099, 0.097, 0.384, 0.194), 'minor': (0.095, 0.096, 0.396, 0.195),
               'mini': (0.095, 0.096, 0.379, 0.186)},
        'palette': '''
:root {
  --glass: linear-gradient(180deg, rgba(10, 58, 40, 0.9), rgba(4, 24, 16, 0.95));
  --hairline: inset 0 1px 0 rgba(200, 255, 200, 0.5), inset 0 0 0 1.5px rgba(255, 215, 90, 0.3);
  --wine: #0e4a32; --tan: #b9d6a0;
  --reel-a: rgba(14, 74, 52, 0.86); --reel-b: rgba(4, 26, 18, 0.94); --reel-line: rgba(190, 255, 200, 0.13);
}
html, body { background: #031a10; }''',
    },
    'koi-fortune-lantern': {
        'frame': (0.1101, 0.1844, 0.7792, 0.6940),
        'jp': {'major': (0.161, 0.159, 0.483, 0.090), 'minor': (0.162, 0.179, 0.479, 0.090),
               'mini': (0.165, 0.165, 0.408, 0.100)},
        'palette': '''
:root {
  --glass: linear-gradient(180deg, rgba(24, 22, 74, 0.9), rgba(8, 8, 30, 0.95));
  --hairline: inset 0 1px 0 rgba(255, 210, 150, 0.5), inset 0 0 0 1.5px rgba(255, 170, 90, 0.3);
  --wine: #23206a; --tan: #e4b98a;
  --reel-a: rgba(28, 26, 86, 0.86); --reel-b: rgba(8, 8, 32, 0.94); --reel-line: rgba(255, 190, 120, 0.13);
}
html, body { background: #06061a; }''',
    },
    'koi-fortune-lacquer': {
        'frame': (0.1043, 0.1708, 0.7908, 0.7144),
        'jp': {},
        'palette': '''
:root {
  --glass: linear-gradient(180deg, rgba(26, 8, 10, 0.92), rgba(6, 2, 3, 0.96));
  --hairline: inset 0 1px 0 rgba(255, 120, 90, 0.5), inset 0 0 0 1.5px rgba(255, 70, 50, 0.35);
  --wine: #3a0608; --tan: #e8a08a;
  --reel-a: rgba(36, 6, 8, 0.88); --reel-b: rgba(6, 1, 2, 0.95); --reel-line: rgba(255, 90, 60, 0.14);
}
html, body { background: #050102; }''',
    },
}


def measure_jp(slug):
    """The empty value panel of each plaque: the longest run of dark opaque
    rows through the plaque's middle, then that row's dark span."""
    import numpy as np
    from PIL import Image
    out = {}
    for t in ('grand', 'major', 'minor', 'mini'):
        p = ROOT / f'front/img/{slug}/img/jp_{t}.webp'
        if not p.exists():
            continue
        im = np.asarray(Image.open(p).convert('RGBA')).astype(float)
        h, w = im.shape[:2]
        dark = (im[..., :3].mean(2) < 70) & (im[..., 3] > 200)
        rows = np.nonzero(dark[:, int(w * .4):int(w * .6)].mean(1) > 0.85)[0]
        rows = rows[rows > h * 0.25]
        if not len(rows):
            continue
        run = max(np.split(rows, np.nonzero(np.diff(rows) > 2)[0] + 1), key=len)
        cols = np.nonzero(dark[(run[0] + run[-1]) // 2])[0]
        span = max(np.split(cols, np.nonzero(np.diff(cols) > 2)[0] + 1), key=len)
        out[t] = (span[0] / w, 1 - span[-1] / w, run[0] / h, 1 - run[-1] / h)
    return out


def measure_socket(slug):
    """Centre of the RESPINS plate's empty round socket: the dark opaque
    pixels on the plate's right half."""
    import numpy as np
    from PIL import Image
    p = ROOT / f'front/img/{slug}/img/respins.webp'
    im = np.asarray(Image.open(p).convert('RGBA')).astype(float)
    h, w = im.shape[:2]
    dark = (im[..., :3].mean(2) < 60) & (im[..., 3] > 200)
    dark[:, : w // 2] = False
    # The socket is a big filled disc: an erosion drops the thin dark
    # outlines of the lettering and ornaments around it.
    from PIL import ImageFilter
    k = max(3, (h // 12) | 1)
    dark = np.asarray(Image.fromarray((dark * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(k))) > 0
    ys, xs = np.nonzero(dark)
    return (xs.mean() / w, ys.mean() / h) if len(xs) else (0.8, 0.5)


def build(slug, v):
    s = DONOR.read_text()
    s = s.replace('savannah-carved', slug)
    # symbol masks for the shine sweep: this game's codes
    masks = '\n'.join(
        f'.reel__cell[data-symbol="{c}"]::before {{ -webkit-mask-image: url(../img/{slug}/symbols/{c}.webp); '
        f'mask-image: url(../img/{slug}/symbols/{c}.webp); }}' for c in CODES)
    s = re.sub(r'(\.reel__cell\[data-symbol="[a-z]+"\]::before \{ -webkit-mask-image[^\n]*\n)+', masks + '\n', s, count=1)
    if v['frame']:
        l, t, w, h = v['frame']
        for k, val in (('l', l), ('t', t), ('w', w), ('h', h)):
            s = re.sub(rf'--frame-win-{k}: [0-9.]+;', f'--frame-win-{k}: {val:.4f};', s, count=1)
    jp = measure_jp(slug) or dict(v['jp'])
    if jp:
        med = [sorted(x[i] for x in jp.values())[len(jp) // 2] for i in range(4)]
        jp.setdefault('grand', tuple(med))
        lines = '\n'.join(f'.jp--{t} {{ --jp-l: {a:.3f}; --jp-r: {b:.3f}; --jp-t: {c:.3f}; --jp-b: {d:.3f}; }}'
                          for t, (a, b, c, d) in jp.items())
        s = re.sub(r'(\.jp--(grand|major|minor|mini) \{ --jp-l[^\n]*\n)+', lines + '\n', s, count=1)
    head = (f'/* Koi Fortune · {slug} — generated by scripts/koi_fortune_css.py from\n'
            f'   css/savannah-carved.css; edit the generator, not this file. */\n')
    sx, sy = measure_socket(slug)
    socket = f'\n.hw-respins {{ --socket-x: {sx:.3f}; --socket-y: {sy:.3f}; }}'
    return head + s + '\n/* Variant palette. */' + v['palette'] + socket + '\n'


if __name__ == '__main__':
    for slug, v in VARIANTS.items():
        out = ROOT / f'front/css/{slug}.css'
        out.write_text(build(slug, v))
        print(out.relative_to(ROOT))
