"""Volt Coins: a coin face (dark enamel + ChatGPT glyph number / tier word)
composed in Python exactly as slot.js lays it out in the DOM (makeCoinFace,
glyphRow, .coin-face.has-glyphs::before). Used where the face has to be baked
into art: the Spine win clips of faced coins (volt_coins_fx.py) and the
feature/bonus preview screens (volt_coins_screens.py).

All sizes are fractions of the symbol tile (tile = one cell, 320x254 units).
"""
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'volt-coins')
GLYPH_DIR = os.path.join(ROOT, 'glyphs')

GLYPH_GAP = 0.06       # em, slot.js GLYPH_GAP
DIGIT_TARGET = 0.36    # of cell height, slot.js makeCoinFace
WORD_TARGET = 0.3
DIGIT_MAXW = 0.56      # of cell width
WORD_MAXW = 0.8
DISC = 0.5             # enamel diameter, of cell height (CSS ::before) — tiers
DISC_VALUE = 0.53      # value coins: the v2 coin's bigger hole

# every face the seed can land (COIN_FACE_WEIGHTS): key -> (coin art, label)
FACES = {
    **{f'x{v}': ('coin_value', f'x{v}') for v in (1, 2, 3, 5, 10, 15)},
    'mini': ('coin_mini', 'mini'), 'minor': ('coin_minor', 'minor'), 'major': ('coin_major', 'major'),
}

_meta = None


def meta():
    global _meta
    if _meta is None:
        _meta = json.load(open(os.path.join(GLYPH_DIR, 'glyphs.json')))
    return _meta


def _chars(label):
    m = meta()
    return [label] if label in m else list(label)


def _em(ch):
    m = meta()
    g = m[ch]
    if len(ch) > 1:
        return 1 / (g['cb'] - g['ct'])
    d = [m[c] for c in '0123456789' if c in m]
    core = sum((x['cb'] - x['ct']) * x['h'] for x in d) / len(d)
    return g['h'] / core


def _row_width(chars):
    m = meta()
    return sum((m[c]['cr'] - m[c]['cl']) * (m[c]['w'] / m[c]['h']) * _em(c) + GLYPH_GAP for c in chars)


def enamel_disc(size, d):
    """solid #0a1236 to 82% of the radius, fading out to the edge"""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx + 0.5 - w / 2, yy + 0.5 - h / 2) / (d / 2)
    a = np.clip((1 - r) / 0.18, 0, 1) * 255
    im = Image.new('RGBA', size, (10, 18, 54, 0))
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


GLYPH_SCALE = 1.1   # .reel__cell.is-coin .coin-face__glyphs img { scale: 1.1 }
CELL_H_CSS = 174    # desktop --cell-h: the glyph glow is 10 CSS px of it


def _dom_glyph(im, tile_h):
    """One glyph as the DOM draws it: drop-shadow(0 0 10px rgba(90,190,255,.7))
    then scale 1.1 about its own centre."""
    from PIL import ImageFilter
    sigma = 10 / 2 * tile_h / CELL_H_CSS
    pad = int(sigma * 3) + 2
    big = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad))
    big.paste(im, (pad, pad))
    # outline: drop-shadow(±1.5px …) x4, rgba(6,10,36,.85), each over the result so far
    d = 1.5 * tile_h / CELL_H_CSS
    for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
        sh = Image.new('RGBA', big.size, (6, 10, 36, 0))
        al = big.getchannel('A').transform(big.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), Image.BILINEAR)
        sh.putalpha(al.point(lambda v: int(v * 0.85)))
        sh.alpha_composite(big)
        big = sh
    a = big.getchannel('A').filter(ImageFilter.GaussianBlur(sigma)).point(lambda v: int(v * 0.7))
    glow = Image.new('RGBA', big.size, (90, 190, 255, 0))
    glow.putalpha(a)
    glow.alpha_composite(big)
    k = GLYPH_SCALE
    return glow.resize((round(glow.width * k), round(glow.height * k)), Image.LANCZOS), pad


def face_layer(size, label, dom_glyph_look=True):
    """Transparent tile-sized layer: enamel + the glyph row, centred."""
    W, H = size
    m = meta()
    chars = _chars(label)
    word = len(chars) == 1 and len(chars[0]) > 1
    target = (WORD_TARGET if word else DIGIT_TARGET) * H
    maxw = (WORD_MAXW if word else DIGIT_MAXW) * W
    fs = min(target, maxw / _row_width(chars))       # px per em
    out = enamel_disc(size, (DISC if word else DISC_VALUE) * H)
    # row: 1em high, centred; every glyph's core bottom sits on the row bottom
    base = H / 2 + fs / 2
    x = W / 2 - _row_width(chars) * fs / 2
    for ch in chars:
        g = m[ch]
        h = _em(ch) * fs
        w = h * g['w'] / g['h']
        x += GLYPH_GAP / 2 * fs                       # margin-left (after the cut padding)
        im = Image.open(os.path.join(GLYPH_DIR, ch + '.webp')).convert('RGBA')
        im = im.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
        bx, by = x - g['cl'] * w, base - g['cb'] * h   # the <img> box
        if dom_glyph_look:
            im, pad = _dom_glyph(im, H)
            out.alpha_composite(im, (round(bx + w / 2 - im.width / 2), round(by + h / 2 - im.height / 2)))
        else:
            out.alpha_composite(im, (round(bx), round(by)))
        x += (g['cr'] - g['cl']) * w + GLYPH_GAP / 2 * fs
    return out


def css_glow(im, cell_px=220):
    """Bake `.reel__cell.is-coin img { filter: drop-shadow(0 0 10px
    rgba(90,190,255,.7)) }` into the tile, so a Spine copy starts and ends
    exactly like the static DOM coin. 10px of a 220px cell; CSS blur radius
    = 2 sigma."""
    from PIL import ImageFilter
    sigma = 10 / 2 * im.width / cell_px
    a = im.getchannel('A').filter(ImageFilter.GaussianBlur(sigma))
    a = a.point(lambda v: int(v * 0.7))
    sh = Image.new('RGBA', im.size, (90, 190, 255, 0))
    sh.putalpha(a)
    sh.alpha_composite(im)
    return sh


def faced_coin(key, sym_dir=os.path.join(ROOT, 'symbols'), glow=False):
    art, label = FACES[key]
    coin = Image.open(os.path.join(sym_dir, f'{art}.png')).convert('RGBA')
    out = css_glow(coin) if glow else coin.copy()
    out.alpha_composite(face_layer(coin.size, label))
    return out


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/faces.png'
    tiles = [faced_coin(k) for k in FACES]
    sheet = Image.new('RGBA', (tiles[0].width * len(tiles), tiles[0].height), (8, 12, 30, 255))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, (i * t.width, 0))
    sheet.save(out)
    print(out)
