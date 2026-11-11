"""Koi Fortune art build: ChatGPT sheets -> game assets (4 variants).

Reuses the alpha-component cutter of scripts/savannah_kings_art.py (same
recipe: every piece keeps only its own pixels). Sources live in
front/img/<slug>/src/ (scripts/chatgpt_art/build.sh copies them there):

  hp          2x2  koi turtle / lantern lotus
  lp          2x2  A K / Q J
  specials    1x4  wild scatter coin jpcoin
  glyphs      digits 0-9 x . , in rows + a last row of MINI MINOR MAJOR tags
  frame, logo, logo_wide, panel, respins (one piece each)
  jackpots    GRAND MAJOR MINOR MINI stacked
  titles      BIG MEGA EPIC FREE SPINS HOLD&WIN TOTAL WIN BUY BONUS stacked
  ante        OFF | ON
  cards       FREE SPINS | HOLD & WIN
  popups_win  BIG MEGA EPIC
  popups_jp   MINI MINOR / MAJOR GRAND
  bg_base bg_fs bg_hw (+ bg_mob_*), banner -> cover.jpg

    SK_SLUG=koi-fortune-silk .venv/bin/python scripts/koi_fortune_art.py [job ...]
"""

import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import savannah_kings_art as sk  # noqa: E402  (reads SK_SLUG at import)

IMG, SYM, OUT, ROOT = sk.IMG, sk.SYM, sk.OUT, sk.ROOT
load, components, isolate, tight, save_png, save_jpg = sk.load, sk.components, sk.isolate, sk.tight, sk.save_png, sk.save_jpg


def biggest(pieces, n):
    return sorted(pieces, key=lambda p: -(p['box'][2] - p['box'][0]) * (p['box'][3] - p['box'][1]))[:n]


def rows_of(pieces):
    """Cluster pieces into rows (vertical overlap), each row left -> right."""
    rows = []
    for p in sorted(pieces, key=lambda p: (p['box'][1] + p['box'][3]) / 2):
        cy = (p['box'][1] + p['box'][3]) / 2
        for r in rows:
            if r['y0'] <= cy <= r['y1']:
                r['items'].append(p)
                break
        else:
            rows.append({'y0': p['box'][1], 'y1': p['box'][3], 'items': [p]})
    return [sorted(r['items'], key=lambda p: p['box'][0]) for r in rows]


def cut(src, n, grid=None, bridge=2, min_frac=0.004):
    """n pieces of a sheet in reading order (grid = rows count hint)."""
    rgba = load(src)
    full, pieces = components(rgba[..., 3], min_frac=min_frac, bridge=bridge)
    if len(pieces) >= n:
        ps = [p for row in rows_of(biggest(pieces, n)) for p in row]
        return [isolate(rgba, full, p) for p in ps]
    # touching items: fall back to emptiest-line cuts
    if grid and grid[0] > 1:
        out = []
        for band in sk.split_band(rgba, grid[0]):
            out += sk.split_row(band, grid[1])
        return out
    if grid and grid[1] == 1:
        return sk.split_col(rgba, n)
    return sk.split_row(rgba, n)


def job_symbols():
    plan = [('hp', ['koi', 'turtle', 'lantern', 'lotus'], (2, 2), 286),
            ('lp', ['a', 'k', 'q', 'j'], (2, 2), 250),
            ('specials', ['wild', 'scatter', 'coin', 'jpcoin'], (1, 4), 290)]
    for src, codes, grid, box in plan:
        for code, crop in zip(codes, cut(src, len(codes), grid)):
            save_png(sk.fit_tile(crop, box), SYM / f'{code}.png')
            sk.blur_twin(SYM / f'{code}.webp')


GLYPHS = list('0123456789') + ['x', 'dot', 'comma']


def job_glyphs():
    """Coin-value digits + the MINI/MINOR/MAJOR coin tags (last row)."""
    rgba = load('glyphs')
    full, pieces = components(rgba[..., 3], min_frac=0.00005, bridge=1)
    rows = rows_of(pieces)
    tags = rows[-1]
    glyph_pieces = [p for r in rows[:-1] for p in r]
    # Two digits that touch come out as one wide blob: split it at the
    # emptiest column(s) back into digit-wide parts.
    widths = sorted(p['box'][2] - p['box'][0] for p in glyph_pieces)
    med = widths[len(widths) // 2]
    crops = []
    for p in glyph_pieces:
        crop = isolate(rgba, full, p, pad=2)
        k = round((p['box'][2] - p['box'][0]) / med)
        crops += sk.split_row(crop, k) if k >= 2 else [crop]
    print(f'  glyphs: {len(crops)} pieces, tags: {len(tags)}')
    if len(crops) != len(GLYPHS) or len(tags) != 3:
        print(f'  ! glyph sheet: expected 13 + 3 pieces, got {len(crops)} + {len(tags)} — pick another take')
        return
    # One scale for all: every digit keeps its height relative to the tallest.
    hmax = max(c.shape[0] for c in crops[:10])
    for name, crop in zip(GLYPHS, crops):
        im = Image.fromarray(crop)
        s = 120 / hmax
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        save_png(im, IMG / 'glyphs' / f'{name}.png')
    for name, p in zip(['mini', 'minor', 'major'], tags):
        save_png(isolate(rgba, full, p), IMG / f'tag_{name}.png', max_w=360)


def frame_window(a):
    """The reel window = the transparent region connected to the frame's
    centre (bbox). Scanning one row from the edge, as savannah's job_frame
    does, stops at the gap between a hanging lantern and the rail."""
    from collections import deque
    h, w = a.shape
    s = 4
    clear = np.array(Image.fromarray(a).resize((w // s, h // s), Image.BILINEAR)) < 40
    sh, sw = clear.shape
    seen = np.zeros_like(clear)
    q = deque([(sh // 2, sw // 2)])
    seen[sh // 2, sw // 2] = True
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < sh and 0 <= nx < sw and clear[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    ys, xs = np.nonzero(seen)
    # Trim the ragged inner edge: the rows/cols that are mostly clear.
    col_fill = seen.mean(axis=0)
    row_fill = seen.mean(axis=1)
    cols = np.nonzero(col_fill > col_fill.max() * 0.6)[0]
    rows = np.nonzero(row_fill > row_fill.max() * 0.6)[0]
    return cols[0] * s, (cols[-1] + 1) * s, rows[0] * s, (rows[-1] + 1) * s


def job_frame():
    """savannah's job_frame (9-slice re-proportioned to a 5:3 window) with
    the window measured by frame_window()."""
    rgba = tight(load('frame'), pad=0)
    h, w = rgba.shape[:2]
    a = rgba[..., 3]
    l, r, t, b = frame_window(a)
    print(f'  frame {w}x{h}, window x {l}..{r} y {t}..{b} ({r - l}x{b - t}, ratio {(r - l) / (b - t):.3f})')
    S = 1.5
    win_w, win_h = round(920 * S), round(552 * S)
    sx = win_w / (r - l)
    sy = win_h / (b - t)
    # Borders keep one scale (the horizontal one) so their ornament isn't
    # squashed; only the window's spans stretch.
    s = sx
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
    print(f'  (vertical stretch of the side rails x{sy / sx:.2f})')
    save_png(out, IMG / 'reel_frame.png')
    print(f'  CSS: --frame-win-l: {dx[1] / out_w:.4f}; --frame-win-t: {dy[1] / out_h:.4f}; '
          f'--frame-win-w: {win_w / out_w:.4f}; --frame-win-h: {win_h / out_h:.4f};')


def job_bg():
    for src, name, w in (('bg_base', 'bg_base', 2400), ('bg_fs', 'bg_fs', 2400), ('bg_hw', 'bg_hw', 2400),
                         ('bg_mob_base', 'bg_base_mob', 1400), ('bg_mob_fs', 'bg_fs_mob', 1400),
                         ('bg_mob_hw', 'bg_hw_mob', 1400)):
        try:
            save_jpg(load(src), IMG / f'{name}.jpg', w)
        except FileNotFoundError as e:
            print('  skip', e)


def job_single():
    for name, w in (('logo', 1000), ('logo_wide', 1400), ('panel', 900), ('respins', 700)):
        save_png(tight(load(name)), IMG / f'{name}.png', max_w=w)


def job_jackpots():
    sk.job_jackpots()


def job_titles():
    names = ['big', 'mega', 'epic', 'freespins', 'holdwin', 'totalwin', 'buybonus']
    for name, crop in zip(names, cut('titles', 7, (7, 1), bridge=6)):
        save_png(crop, IMG / f'title_{name}.png', max_w=1000)


def job_ante():
    for name, crop in zip(['ante_off', 'ante_on'], cut('ante', 2, (1, 2))):
        save_png(crop, IMG / f'{name}.png', max_w=420)


def job_cards():
    for name, crop in zip(['card_fs', 'card_hw'], cut('cards', 2, (1, 2))):
        save_png(crop, IMG / f'{name}.png', max_w=560)


def job_popups():
    for name, crop in zip(['big', 'mega', 'epic'], cut('popups_win', 3, (1, 3))):
        save_png(crop, IMG / f'popup_{name}.png', max_w=900)
    for name, crop in zip(['mini', 'minor', 'major', 'grand'], cut('popups_jp', 4, (2, 2))):
        save_png(crop, IMG / f'popup_{name}.png', max_w=900)


def job_cover():
    im = Image.fromarray(load('banner')).convert('RGB')
    im = im.resize((960, round(im.height * 960 / im.width)), Image.LANCZOS)
    im.save(OUT / 'cover.jpg', quality=85, optimize=True, progressive=True)
    print('  cover.jpg', im.size)


JOBS = {
    'symbols': job_symbols, 'glyphs': job_glyphs, 'frame': job_frame, 'bg': job_bg, 'single': job_single,
    'jackpots': job_jackpots, 'titles': job_titles, 'ante': job_ante, 'cards': job_cards,
    'popups': job_popups, 'cover': job_cover,
}

if __name__ == '__main__':
    for name in sys.argv[1:] or JOBS:
        print(name)
        try:
            JOBS[name]()
        except FileNotFoundError as e:
            print('  skip —', e)
