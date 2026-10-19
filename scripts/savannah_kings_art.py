"""Savannah Kings art build: ChatGPT sources -> game assets.

Sources (transparent PNG/WebP straight from ChatGPT, gitignored) live in
front/img/savannah-kings/src/ under fixed names (see JOBS). Every sheet is
cut by ALPHA CONNECTED COMPONENTS, and each piece keeps only its own pixels:
whatever belongs to a neighbouring component inside the crop box is erased,
so a long tusk or a glow never drags a slice of the next symbol along.

Writes front/img/savannah-kings/{symbols,img}/ and prints the measured boxes
(frame window, plaque value panel, wheel rim) that css/savannah-kings.css
keeps in its --frame-* / --jp-* / --rim-inner variables.

    .venv/bin/python scripts/savannah_kings_art.py [job ...]
"""

import json
import os
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
# SK_SLUG picks the art variant folder (lions-reign, golden-savannah).
OUT = ROOT / 'front/img' / os.environ.get('SK_SLUG', 'savannah-kings')
SRC = OUT / 'src'
SYM = OUT / 'symbols'
IMG = OUT / 'img'

TILE = 300           # symbol canvas (shown at 184 design px -> ~1.6x)
ALPHA_FLOOR = 10     # ChatGPT leaves a faint haze around cut-outs


def load(name):
    for ext in ('png', 'webp'):
        p = SRC / f'{name}.{ext}'
        if p.exists():
            im = Image.open(p).convert('RGBA')
            a = np.array(im)
            a[..., 3][a[..., 3] < ALPHA_FLOOR] = 0
            return a
    raise FileNotFoundError(f'{name} not in {SRC}')


# --- connected components -------------------------------------------------

def components(alpha, min_frac=0.004, scale=4, thresh=60, bridge=2):
    """Label opaque blobs on a downscaled mask (BFS, 8-neighbour). `bridge`
    dilates the small mask first, so a symbol whose parts are split by a thin
    gap (a letter's counter, a tusk tip) stays one piece."""
    h, w = alpha.shape
    small = np.array(Image.fromarray(alpha).resize((w // scale, h // scale), Image.BILINEAR)) > thresh
    if bridge:
        m = Image.fromarray((small * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * bridge + 1))
        small = np.array(m) > 0
    sh, sw = small.shape
    labels = np.zeros((sh, sw), np.int32)
    n = 0
    sizes = {}
    for y in range(sh):
        for x in range(sw):
            if small[y, x] and not labels[y, x]:
                n += 1
                q = deque([(y, x)])
                labels[y, x] = n
                cnt = 0
                while q:
                    cy, cx = q.popleft()
                    cnt += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < sh and 0 <= nx < sw and small[ny, nx] and not labels[ny, nx]:
                                labels[ny, nx] = n
                                q.append((ny, nx))
                sizes[n] = cnt
    keep = [k for k, c in sizes.items() if c >= min_frac * sh * sw]
    full = np.array(Image.fromarray(labels.astype(np.int32)).resize((w, h), Image.NEAREST))
    pieces = []
    for k in keep:
        ys, xs = np.nonzero(labels == k)
        pieces.append({
            'label': k,
            'box': (xs.min() * scale, ys.min() * scale, (xs.max() + 1) * scale, (ys.max() + 1) * scale),
        })
    return full, pieces


def order(pieces, rows=None):
    """Reading order: group into rows by vertical centre, then left -> right."""
    pieces = sorted(pieces, key=lambda p: (p['box'][1] + p['box'][3]) / 2)
    if rows is None:
        return sorted(pieces, key=lambda p: ((p['box'][1] + p['box'][3]) // 2 // 200, p['box'][0]))
    out = []
    per = len(pieces) // rows
    for r in range(rows):
        out += sorted(pieces[r * per:(r + 1) * per], key=lambda p: p['box'][0])
    return out


def isolate(rgba, full_labels, piece, pad=6):
    """The piece's own pixels only, cropped tight (+pad)."""
    k = piece['label']
    own = full_labels == k
    # Soft edge pixels just outside the downscaled label still belong to us
    # unless they belong to another label.
    grown = np.array(Image.fromarray((own * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    keep = grown & ((full_labels == 0) | own)
    out = rgba.copy()
    out[..., 3] = np.where(keep, out[..., 3], 0)
    ys, xs = np.nonzero(out[..., 3] > 8)
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(out.shape[1], xs.max() + 1 + pad), min(out.shape[0], ys.max() + 1 + pad)
    return out[y0:y1, x0:x1]


def split_row(rgba, n):
    """A one-row sheet whose items touch (the mask's rays reach the lion's
    rim): cut at the emptiest column near each expected boundary, then keep
    only each slice's own main blob, so a ray tip that crossed the cut is
    dropped instead of riding along with the neighbour."""
    a = rgba[..., 3]
    col = (a > 40).sum(axis=0).astype(float)
    w = a.shape[1]
    cuts = [0]
    for i in range(1, n):
        c = w * i // n
        lo, hi = c - w // (3 * n), c + w // (3 * n)
        cuts.append(lo + int(np.argmin(col[lo:hi])))
    cuts.append(w)
    parts = []
    for x0, x1 in zip(cuts, cuts[1:]):
        part = rgba.copy()
        part[:, :x0, 3] = 0
        part[:, x1:, 3] = 0
        full, pieces = components(part[..., 3], bridge=0)
        main = max(pieces, key=lambda p: (p['box'][2] - p['box'][0]) * (p['box'][3] - p['box'][1]))
        parts.append(isolate(part, full, main))
    return parts


def split_band(rgba, n):
    """Horizontal bands at the emptiest rows, full width, no blob filtering."""
    a = rgba[..., 3]
    row = (a > 40).sum(axis=1).astype(float)
    h = a.shape[0]
    cuts = [0]
    for i in range(1, n):
        c = h * i // n
        lo, hi = c - h // (3 * n), c + h // (3 * n)
        cuts.append(lo + int(np.argmin(row[lo:hi])))
    cuts.append(h)
    out = []
    for y0, y1 in zip(cuts, cuts[1:]):
        band = rgba.copy()
        band[:y0, :, 3] = 0
        band[y1:, :, 3] = 0
        out.append(band)
    return out


def split_col(rgba, n):
    """split_row for a vertical stack (titles whose gems touch)."""
    return [np.ascontiguousarray(p.transpose(1, 0, 2)) for p in split_row(np.ascontiguousarray(rgba.transpose(1, 0, 2)), n)]


def tight(rgba, pad=4):
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    return rgba[max(0, ys.min() - pad):ys.max() + 1 + pad, max(0, xs.min() - pad):xs.max() + 1 + pad]


def fit_tile(piece, box, size=TILE):
    """Into a size x size canvas: longest side -> `box`, centred."""
    im = Image.fromarray(piece)
    s = box / max(im.size)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return canvas


def save_png(im, path, max_w=None):
    """Symbols stay PNG (js/reel-spin.js derives the _blur.png twin from the
    name); everything else in img/ is written as WebP with alpha."""
    if isinstance(im, np.ndarray):
        im = Image.fromarray(im)
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent == IMG:
        path = path.with_suffix('.webp')
        im.save(path, quality=90, method=6)
    else:
        im.save(path, optimize=True)
    print(f'  {path.relative_to(ROOT)}  {im.size}  {path.stat().st_size // 1024}K')
    return im


def save_jpg(rgba, path, max_w):
    im = Image.fromarray(rgba).convert('RGB')
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(path, quality=86, optimize=True, progressive=True)
    print(f'  {path.relative_to(ROOT)}  {im.size}  {path.stat().st_size // 1024}K')


def blur_twin(path):
    """Vertical motion-blur twin for js/reel-spin.js (premultiplied, sigma
    3.3% of the height — scripts/make_reel_blur.py's recipe)."""
    a = np.array(Image.open(path).convert('RGBA')).astype(np.float32) / 255
    rgb = a[..., :3] * a[..., 3:4]
    al = a[..., 3:4]
    sigma = 0.033 * a.shape[0]
    r = int(sigma * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    def vblur(x):
        pad = np.pad(x, ((r, r), (0, 0), (0, 0)))
        out = np.zeros_like(x)
        for i, w in enumerate(k):
            out += w * pad[i:i + x.shape[0]]
        return out
    rgb_b, al_b = vblur(rgb), vblur(al)
    col = np.where(al_b > 1e-4, rgb_b / np.maximum(al_b, 1e-4), 0)
    out = np.concatenate([col, al_b], axis=2)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(
        str(path).replace('.png', '_blur.png'), optimize=True)


# --- jobs ------------------------------------------------------------------

def job_symbols():
    """hp: elephant buffalo / leopard zebra; lp: A K / Q J; specials: wild
    scatter paw. Medallions fill the tile; letters a little smaller (low
    symbols read lighter), the lion medallion a touch larger."""
    plan = [
        ('hp', ['elephant', 'buffalo', 'leopard', 'zebra'], 2, 286),
        ('lp', ['a', 'k', 'q', 'j'], 2, 250),
        ('specials', ['wild', 'scatter', 'paw'], 1, 290),
    ]
    for src, codes, rows, box in plan:
        rgba = load(src)
        full, pieces = components(rgba[..., 3])
        pieces = order(sorted(pieces, key=lambda p: -(p['box'][2] - p['box'][0]) * (p['box'][3] - p['box'][1]))[:len(codes)], rows)
        if len(pieces) == len(codes):
            crops = [isolate(rgba, full, piece) for piece in pieces]
        else:
            # Items touch (horns, ears): cut the sheet into its grid at the
            # emptiest lines, then keep each cell's own main blob.
            cols = len(codes) // rows
            crops = []
            for band in (split_band(rgba, rows) if rows > 1 else [rgba]):
                crops += split_row(band, cols)
        for code, crop in zip(codes, crops):
            tile = fit_tile(crop, box)
            path = SYM / f'{code}.png'
            save_png(tile, path)
            blur_twin(path)


def job_wild_big():
    rgba = tight(load('wild_big'))
    save_png(rgba, IMG / 'wild_big.png', max_w=420)


def job_bg():
    for name, w in (('bg_base', 2400), ('bg_bonus', 2400), ('bg_base_mob', 1400), ('bg_bonus_mob', 1400)):
        try:
            save_jpg(load(name), IMG / f'{name}.jpg', w)
        except FileNotFoundError as e:
            print('  skip', e)


def job_logo():
    save_png(tight(load('logo')), IMG / 'logo.png', max_w=1000)


def job_frame():
    """Measure the window (transparent hole) and re-slice the frame so the
    hole is exactly 5:3 (square cells): corners keep their size, the plain
    runs between them stretch. Writes reel_frame.png with the window at
    WIN_W x WIN_H * 1.5 and prints the window fractions for the CSS."""
    rgba = tight(load('frame'), pad=0)
    h, w = rgba.shape[:2]
    a = rgba[..., 3]
    cy, cx = h // 2, w // 2
    row = a[cy] > 40
    # Top/bottom are measured a quarter in from the left: a crest hanging
    # into the window at the centre would otherwise shrink it.
    col = a[:, w // 4] > 40
    # Scan from each edge inwards: past the wall to the first clear pixel.
    # (Scanning out from the centre would stop at painted cell dividers.)
    def inner(profile):
        first = int(np.argmax(profile))
        return first + int(np.argmax(~profile[first:]))
    l = inner(row)
    r = len(row) - inner(row[::-1])
    t = inner(col)
    b = len(col) - inner(col[::-1])
    # 9-slice rows: the top band must hold the whole crest, so it ends where
    # the crest ends at the centre column, not at the rail.
    crest = inner(a[:, cx] > 40)
    print(f'  frame {w}x{h}, window x {l}..{r} y {t}..{b} ({r - l}x{b - t}, ratio {(r - l) / (b - t):.3f})')
    S = 1.5
    win_w, win_h = round(920 * S), round(552 * S)
    s = win_w / (r - l)
    # 3x3 slice around the window
    xs = [0, l, r, w]
    ys = [0, t, b, h]
    out_w = round(l * s) + win_w + round((w - r) * s)
    out_h = round(t * s) + win_h + round((h - b) * s)
    dx = [0, round(l * s), round(l * s) + win_w, out_w]
    dy = [0, round(t * s), round(t * s) + win_h, out_h]
    src = Image.fromarray(rgba)
    out = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))
    for i in range(3):
        for j in range(3):
            if i == 1 and j == 1:
                continue
            piece = src.crop((xs[j], ys[i], xs[j + 1], ys[i + 1]))
            tw, th = dx[j + 1] - dx[j], dy[i + 1] - dy[i]
            if tw > 0 and th > 0:
                out.paste(piece.resize((tw, th), Image.LANCZOS), (dx[j], dy[i]))
    # The crest's tip hanging into the window: same scale as the rails,
    # pasted over the (transparent) window top so it is not lost.
    if crest > t + 4:
        tip = src.crop((l, t, r, crest))
        tip = tip.resize((win_w, max(1, round((crest - t) * s))), Image.LANCZOS)
        out.alpha_composite(tip, (dx[1], dy[1]))
    save_png(out, IMG / 'reel_frame.png')
    print(f'  CSS: --frame-win-l: {dx[1] / out_w:.4f}; --frame-win-t: {dy[1] / out_h:.4f}; '
          f'--frame-win-w: {win_w / out_w:.4f}; --frame-win-h: {win_h / out_h:.4f};')


def job_jackpots():
    rgba = load('jackpots')
    full, pieces = components(rgba[..., 3])
    if len(pieces) >= 4:
        pieces = order(sorted(pieces, key=lambda p: -(p['box'][2] - p['box'][0]))[:4], 4)
        crops = [isolate(rgba, full, p, pad=2) for p in pieces]
    else:
        crops = split_col(rgba, 4)  # crowns touch the plaque above
    boxes = []
    for tier, im in zip(['grand', 'major', 'minor', 'mini'], crops):
        save_png(im, IMG / f'jp_{tier}.png', max_w=640)
        # The empty value panel: the longest run of dark opaque columns
        # through the middle band (the tier word's dark outline makes a
        # plain bbox start far too early), then its rows.
        lum = im[..., :3].astype(float).mean(axis=2)
        hh, ww = lum.shape
        # the value panel: darkest opaque region (relative, panels differ per tier)
        op = im[..., 3] > 200
        dark = (lum < max(60, np.percentile(lum[op], 30))) & op
        cols = list(dark[int(hh * .5):int(hh * .75)].mean(axis=0) > 0.6) + [False]
        best, start = (0, 0), None
        for x, v in enumerate(cols):
            if v and start is None:
                start = x
            if not v and start is not None:
                best = max(best, (start, x), key=lambda r: r[1] - r[0])
                start = None
        x0, x1 = best
        ys = np.nonzero(dark[:, x0 + 10:x1 - 10].mean(axis=1) > 0.6)[0]
        if x1 - x0 < ww * 0.2 or not len(ys):
            continue
        boxes.append((x0 / ww, 1 - x1 / ww, ys.min() / hh, 1 - ys.max() / hh))
        print(f'  CSS .jp--{tier} {{ --jp-l: {boxes[-1][0]:.3f}; --jp-r: {boxes[-1][1]:.3f}; '
              f'--jp-t: {boxes[-1][2]:.3f}; --jp-b: {boxes[-1][3]:.3f}; }}')
    if boxes:
        m = np.median(np.array(boxes), axis=0)
        print(f'  CSS: --jp-l: {m[0]:.3f}; --jp-r: {m[1]:.3f}; --jp-t: {m[2]:.3f}; --jp-b: {m[3]:.3f};')


def job_wheel():
    rgba = load('wheel')
    full, pieces = components(rgba[..., 3], bridge=1)
    if len(pieces) == 1:
        # Rim and hub touch side by side: blank the emptiest column between them.
        cols = (rgba[..., 3] > 20).sum(axis=0)
        w = len(cols)
        lo, hi = int(w * 0.6), int(w * 0.75)
        cut = lo + int(np.argmin(cols[lo:hi]))
        rgba = rgba.copy()
        rgba[:, cut - 6:cut + 7, 3] = 0
        full, pieces = components(rgba[..., 3], bridge=1)
    pieces = sorted(pieces, key=lambda p: -(p['box'][2] - p['box'][0]) * (p['box'][3] - p['box'][1]))[:3]
    rim = pieces[0]
    rim_im = isolate(rgba, full, rim, pad=2)
    save_png(rim_im, IMG / 'wheel_rim.png', max_w=1100)
    if len(pieces) == 3:
        small = sorted(pieces[1:], key=lambda p: p['box'][1])
        hub_im, pointer_im = (isolate(rgba, full, p) for p in small)
    else:
        # The hub's bottom gem touches the pointer: cut at the narrowest row
        # between them, then keep each half's main blob only.
        both = isolate(rgba, full, pieces[1], pad=0)
        h = both.shape[0]
        width = (both[..., 3] > 40).sum(axis=1)
        lo, hi = int(h * 0.45), int(h * 0.75)
        cut = lo + int(np.argmin(width[lo:hi]))
        halves = []
        for part in (both[:cut], both[cut:]):
            f, ps = components(part[..., 3], bridge=0, min_frac=0.01)
            main = max(ps, key=lambda p: (p['box'][2] - p['box'][0]) * (p['box'][3] - p['box'][1]))
            halves.append(isolate(part, f, main))
        hub_im, pointer_im = halves
    save_png(hub_im, IMG / 'wheel_hub.png', max_w=420)
    save_png(pointer_im, IMG / 'wheel_pointer.png', max_w=260)
    al = rim_im[..., 3]
    hh, ww = al.shape
    cy, cx = hh // 2, ww // 2
    ray = al[cy, cx:] > 160
    inner = np.argmax(ray)
    print(f'  CSS: --rim-inner: {2 * inner / ww:.3f};')


def job_titles():
    for src, names in (('titles_win', ['big', 'mega', 'epic']),
                       ('titles_more', ['freespins', 'totalwin', 'jackpot', 'buybonus'])):
        try:
            rgba = load(src)
        except FileNotFoundError as e:
            print('  skip', e)
            continue
        full, pieces = components(rgba[..., 3], bridge=6)
        if len(pieces) == len(names):
            pieces = sorted(pieces, key=lambda p: p['box'][1])
            crops = [isolate(rgba, full, p) for p in pieces]
        else:
            crops = split_col(rgba, len(names))
        for name, crop in zip(names, crops):
            save_png(crop, IMG / f'title_{name}.png', max_w=1000)


def job_panel():
    save_png(tight(load('panel')), IMG / 'panel.png', max_w=900)


def job_cards():
    rgba = load('cards')
    full, pieces = components(rgba[..., 3])
    pieces = sorted(sorted(pieces, key=lambda p: -(p['box'][2] - p['box'][0]) * (p['box'][3] - p['box'][1]))[:2],
                    key=lambda p: p['box'][0])
    for name, piece in zip(['card_fs', 'card_wheel'], pieces):
        save_png(isolate(rgba, full, piece), IMG / f'{name}.png', max_w=560)


def job_mascot():
    save_png(tight(load('mascot')), IMG / 'mascot.png', max_w=900)


def job_cover():
    im = Image.fromarray(load('cover')).convert('RGB')
    im = im.resize((960, round(im.height * 960 / im.width)), Image.LANCZOS)
    im.save(OUT / 'cover.jpg', quality=85, optimize=True, progressive=True)
    print('  cover.jpg', im.size)


JOBS = {
    'symbols': job_symbols, 'wild_big': job_wild_big, 'bg': job_bg, 'logo': job_logo,
    'frame': job_frame, 'jackpots': job_jackpots, 'wheel': job_wheel, 'titles': job_titles,
    'panel': job_panel, 'cards': job_cards, 'mascot': job_mascot, 'cover': job_cover,
}

if __name__ == '__main__':
    for name in sys.argv[1:] or JOBS:
        print(name)
        try:
            JOBS[name]()
        except FileNotFoundError as e:
            print('  skip —', e)
