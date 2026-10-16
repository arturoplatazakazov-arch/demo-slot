"""Volt Coins popups: cut the ChatGPT-drawn banner sheets into game assets.

Sources (art/volt-coins-src/gpt/, outside front/): banners stacked on a flat
black background, drawn in ChatGPT from the game's art direction —
  popups_wins.png     BIG WIN / MEGA WIN / EPIC WIN
  popups_round.png    HOLD & WIN / TOTAL WIN / BUY BONUS
  popups_jackpots.png MINI / MINOR / MAJOR / GRAND (2x2), when present

Black is keyed by a flood fill from the sheet border through near-black
pixels: everything the fill can't reach (the dark-indigo panels included)
stays opaque, the glow it does reach gets a luminance alpha (un-blended
against black). Each banner's EMPTY panel — where the game prints the amount
— is measured and written to front/img/volt-coins/popups/popups.json as
fractions of the banner image, so CSS places the number inside it.

    .venv/bin/python scripts/volt_coins_popups.py
"""

import collections
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..')
SRC = os.path.join(ROOT, 'art', 'volt-coins-src', 'gpt')
OUT = os.path.join(ROOT, 'front', 'img', 'volt-coins', 'popups')

SHEETS = {
    'popups_wins.png': ('rows', ['big_win', 'mega_win', 'epic_win']),
    'popups_round.png': ('rows', ['hold_and_win', 'total_win', 'buy_bonus']),
    'popups_jackpots.png': ('grid', ['jp_mini', 'jp_minor', 'jp_major', 'jp_grand']),
}
BG_MAX = 22  # a pixel this dark (max channel) can be background


def outside_mask(rgb):
    dark = rgb.max(2) <= BG_MAX
    h, w = dark.shape
    out = np.zeros_like(dark)
    q = collections.deque()
    for x in range(w):
        for y in (0, h - 1):
            if dark[y, x] and not out[y, x]:
                out[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if dark[y, x] and not out[y, x]:
                out[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and dark[ny, nx] and not out[ny, nx]:
                out[ny, nx] = True
                q.append((ny, nx))
    return out


def key(im):
    rgb = np.asarray(im.convert('RGB')).astype(np.float32)
    out = outside_mask(rgb)
    # glow outside the art: alpha from brightness (the black is the absence of light)
    lum = np.clip((rgb.max(2) - 6) / 140, 0, 1) ** 0.85
    a = np.where(out, 0.0, 1.0)
    # pixels next to the outside that are themselves glow (not the solid art)
    # also fall back to the luminance key so the edge of a glow isn't a hard line
    glowish = (~out) & (rgb.max(2) < 120)
    near = np.zeros_like(out)
    near[1:] |= out[:-1]
    near[:-1] |= out[1:]
    near[:, 1:] |= out[:, :-1]
    near[:, :-1] |= out[:, 1:]
    a = np.where(glowish & near, lum, a)
    a = np.maximum(a, np.where(out, lum, 0))
    unp = np.clip(rgb / np.maximum(a, 1e-3)[..., None], 0, 255)
    col = np.where((a >= 0.999)[..., None], rgb, unp)
    return Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8))


def split_rows(alpha, n):
    """n bands separated by the n-1 emptiest rows between the art."""
    prof = alpha.sum(1)
    h = len(prof)
    cuts = []
    for k in range(1, n):
        lo, hi = int(h * (k - 0.35) / n), int(h * (k + 0.35) / n)
        cuts.append(lo + int(np.argmin(prof[lo:hi])))
    edges = [0] + cuts + [h]
    return [(edges[i], edges[i + 1]) for i in range(n)]


def trim_box(a, thr=6):
    ys, xs = np.where(a > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def panel_box(rgba):
    """The empty indigo panel: the biggest connected blob of opaque dark-blue
    pixels in the lower part of the banner."""
    a = np.asarray(rgba).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    m = (al > 250) & (b > 40) & (b < 190) & (r < 60) & (g < 80) & (b > r + 25)
    h, w = m.shape
    seen = np.zeros_like(m)
    best = None
    for sy, sx in zip(*np.nonzero(m)):
        if seen[sy, sx]:
            continue
        q = collections.deque([(sy, sx)])
        seen[sy, sx] = True
        ys, xs = [], []
        while q:
            y, x = q.popleft()
            ys.append(y)
            xs.append(x)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if best is None or len(ys) > best[0]:
            best = (len(ys), min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    _, x0, y0, x1, y1 = best
    return {'l': round(x0 / w, 4), 't': round(y0 / h, 4), 'w': round((x1 - x0) / w, 4), 'h': round((y1 - y0) / h, 4)}


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for sheet, (layout, names) in SHEETS.items():
        p = os.path.join(SRC, sheet)
        if not os.path.exists(p):
            print('skip (not delivered yet):', sheet)
            continue
        keyed = key(Image.open(p))
        al = np.asarray(keyed.getchannel('A'))
        if layout == 'rows':
            boxes = [(0, y0, keyed.width, y1) for y0, y1 in split_rows(al, len(names))]
        else:
            H, W = al.shape
            ys = split_rows(al, 2)
            xs = split_rows(al.T, 2)
            boxes = [(x0, y0, x1, y1) for (y0, y1) in ys for (x0, x1) in xs]
        for name, box in zip(names, boxes):
            part = keyed.crop(box)
            part = part.crop(trim_box(np.asarray(part.getchannel('A'))))
            # WebP with alpha: the glow-heavy banners are ~5x lighter than PNG
            part.save(os.path.join(OUT, name + '.webp'), quality=88, method=6)
            meta[name] = {'size': part.size, 'panel': panel_box(part)}
            print(name, part.size, meta[name]['panel'])
    old = {}
    mp = os.path.join(OUT, 'popups.json')
    if os.path.exists(mp):
        old = json.load(open(mp))
    old.update(meta)
    json.dump(old, open(mp, 'w'), indent=1)


if __name__ == '__main__':
    main()
