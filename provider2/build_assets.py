"""Build the front assets of a Provider 2 game from its sorted ChatGPT art.

    python3 provider2/build_assets.py <slug> [<slug> ...]   (or: all)

Reads provider2/art/<slug>/src/*.png (written by build_mockups.py; optional
bg_base_mob / bg_bonus_mob / ui_kit appear once they are downloaded) and
writes front/img/<slug>/:

  img/   bg_base(.jpg/_mob), bg_bonus(.jpg/_mob), logo.png, reel_frame.png,
         reel_bg.jpg, hero.png, hero2.png, buy_bonus(.png/_mob), fs_counter
         (.png/_mob), popup_{big,mega,epic,bonus_spins,buy}.png, btn_yes/no,
         cover.jpg
  symbols/<code>.png  200x200 tiles (art centred, same optical size per tier)
          wild_big.png  250x600, the hero full height with the wild on him
  layout.json   measured numbers the page template needs (frame borders,
                popup text panels)

The reel window is fixed for every game: 5 x 191.6 by 3 x 191 design px (the
Caesar's Fortune grid this template comes from); the frame is rebuilt around
it with thin walls (see build_mockups.reframe).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mockups import cut_sheet, grid_cut, reframe  # noqa: E402
from pset import DIR, GAMES, NAME  # noqa: E402

FRONT = HERE.parent / 'front' / 'img'
WIN_W, WIN_H = 958, 573          # 5 x 191.6, 3 x 191
WALL = 70
FONT = '/System/Library/Fonts/Supplemental/Arial Black.ttf'


def hex_rgb(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def trim(im, thr=12):
    bb = im.getchannel('A').point(lambda v: 255 if v > thr else 0).getbbox()
    return im.crop(bb) if bb else im


def fit(im, w, h):
    k = min(w / im.width, h / im.height)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def cover(im, w, h):
    k = max(w / im.width, h / im.height)
    im = im.convert('RGB').resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def clean(im, keep=0.12, near=0.04):
    """Drop stray bits a sheet cut picks up from its neighbours (the green
    swirl under Hex Hollow's spellbook, edges of the next banner): alpha
    blobs smaller than `keep` of the main blob that do not touch the main
    blob's box (grown by `near` of its size) are erased."""
    from build_mockups import components
    k = 2
    small = im.getchannel('A').resize((max(1, im.width // k), max(1, im.height // k)), Image.BOX)
    mask = np.array(small) > 40
    comps = components(mask)
    if len(comps) < 2:
        return im
    main = max(comps)
    _, mx0, my0, mx1, my1 = main
    g = near * max(mx1 - mx0, my1 - my0)
    drop = Image.new('L', small.size, 0)
    d = ImageDraw.Draw(drop)
    lab = None
    for c in comps:
        area, x0, y0, x1, y1 = c
        if c is main or area >= main[0] * keep:
            continue
        touches = not (x1 < mx0 - g or x0 > mx1 + g or y1 < my0 - g or y0 > my1 + g)
        if touches:
            continue
        d.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], fill=255)
    if not drop.getbbox():
        return im
    drop = drop.resize(im.size, Image.NEAREST)
    a = ImageChops.subtract(im.getchannel('A'), drop)
    out = im.copy()
    out.putalpha(a)
    return trim(out, 2)


def drop_shadow(im, dy=0.035, blur=0.03, alpha=0.62):
    """`im` over a soft dark copy of its own silhouette shifted down — the
    symbols read as objects sitting on the reel, not stickers on it. Offsets
    are fractions of the image height; the canvas size is kept."""
    h = im.height
    a = im.getchannel('A').point(lambda v: int(v * alpha))
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, h * blur)))
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, int(round(h * dy))))
    out.alpha_composite(im)
    return out


def tile(im, size, fill):
    """Centre `im` in a size x size transparent tile at `fill` of the box,
    with a drop shadow baked in (statics and Spine regions share the PNG)."""
    im = fit(clean(trim(im)), size * fill, size * fill)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2 - int(size * 0.015)))
    return drop_shadow(out)


def portrait_fallback(desk: Image.Image, w=780, h=1416) -> Image.Image:
    """No phone art yet: the middle of the landscape scene over a blurred,
    darkened stretch of itself."""
    base = cover(desk, w, h).filter(ImageFilter.GaussianBlur(26))
    base = Image.blend(base, Image.new('RGB', base.size, (0, 0, 0)), 0.35)
    mid = fit(desk.convert('RGB'), w * 1.9, h)
    mid = mid.crop(((mid.width - w) // 2, 0, (mid.width + w) // 2, mid.height))
    base.paste(mid, (0, (h - mid.height) // 2))
    return base


def text(s, size, top, bot, stroke=(30, 12, 4)):
    f = ImageFont.truetype(FONT, size)
    w = int(f.getlength(s)) + size
    h = int(size * 1.5)
    m = Image.new('L', (w, h))
    ImageDraw.Draw(m).text((size // 2, size // 6), s, font=f, fill=255)
    sm = Image.new('L', (w, h))
    ImageDraw.Draw(sm).text((size // 2, size // 6), s, font=f, fill=255,
                            stroke_width=max(3, size // 9), stroke_fill=255)
    grad = Image.new('RGBA', (1, h))
    for y in range(h):
        k = y / (h - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)) + (255,))
    grad = grad.resize((w, h))
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.paste(Image.new('RGBA', (w, h), stroke + (255,)), (0, 0), sm)
    out.paste(grad, (0, 0), m)
    return trim(out)


def plate(w, h, accent, ink, radius=None):
    """Code-drawn panel: dark glossy body, accent rim, inner bevel."""
    radius = radius or min(w, h) // 5
    S = 2
    im = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rim = tuple(min(255, int(c * 1.1)) for c in accent)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius * S, fill=rim + (255,))
    d.rounded_rectangle([7 * S, 7 * S, w * S - 7 * S, h * S - 7 * S], (radius - 6) * S,
                        fill=tuple(int(c * 0.55) for c in accent) + (255,))
    d.rounded_rectangle([13 * S, 13 * S, w * S - 13 * S, h * S - 13 * S], (radius - 12) * S,
                        fill=ink + (255,))
    gl = Image.new('L', im.size)
    ImageDraw.Draw(gl).rounded_rectangle([16 * S, 16 * S, w * S - 16 * S, int(h * S * 0.45)],
                                         (radius - 14) * S, fill=46)
    im.alpha_composite(Image.new('RGBA', im.size, (255, 255, 255, 0)), (0, 0))
    white = Image.new('RGBA', im.size, (255, 255, 255, 0))
    white.putalpha(gl.filter(ImageFilter.GaussianBlur(6 * S)))
    im.alpha_composite(white)
    return im.resize((w, h), Image.LANCZOS)


def popup_plate(title_img, accent, ink, w=1000, panel_h=230, panel_img=None):
    """Title art on top, amount panel under it (the UI kit's empty plate when
    there is one, else a code-drawn one). Returns (image, panel inset as CSS
    'top right bottom left' percentages of the text box)."""
    t = fit(title_img, w * 0.96, 420)
    if panel_img is not None:
        p = fit(panel_img, w * 0.78, 260)
        mx, my = 0.14, 0.24          # keep the text off the plate's ornate rim
    else:
        p = plate(int(w * 0.62), panel_h, accent, ink)
        mx, my = 26 / p.width, 22 / p.height
    pw, ph = p.size
    overlap = int(min(40, t.height * 0.12))
    H = t.height + ph - overlap
    out = Image.new('RGBA', (w, H), (0, 0, 0, 0))
    py = t.height - overlap
    out.alpha_composite(p, ((w - pw) // 2, py))
    out.alpha_composite(t, ((w - t.width) // 2, 0))
    l, tp = (w - pw) / 2 + pw * mx, py + ph * my
    r, b = (w + pw) / 2 - pw * mx, py + ph * (1 - my)
    inset = f'{tp / H * 100:.2f}% {(w - r) / w * 100:.2f}% {(H - b) / H * 100:.2f}% {l / w * 100:.2f}%'
    return out, inset


def build(slug):
    g = GAMES[slug]
    src = DIR / 'art' / slug / 'src'
    out = FRONT / slug
    (out / 'img').mkdir(parents=True, exist_ok=True)
    (out / 'symbols').mkdir(parents=True, exist_ok=True)
    accent, accent2, ink = hex_rgb(g['accent']), hex_rgb(g['accent2']), hex_rgb(g['ink'])
    layout = {}

    def load(name):
        p = src / f'{name}.png'
        return Image.open(p).convert('RGBA') if p.exists() else None

    # --- backgrounds -------------------------------------------------------
    bgb, bgx = load('bg_base'), load('bg_bonus')
    bgx = bgx or bgb
    cover(bgb, 1932, 940).save(out / 'img/bg_base.jpg', quality=86, optimize=True)
    cover(bgx, 1932, 940).save(out / 'img/bg_bonus.jpg', quality=86, optimize=True)
    for mode, desk in (('base', bgb), ('bonus', bgx)):
        mob = load(f'bg_{mode}_mob')
        im = cover(mob, 780, 1416) if mob else portrait_fallback(desk)
        im.save(out / f'img/bg_{mode}_mob.jpg', quality=86, optimize=True)
        layout[f'mob_{mode}_art'] = bool(mob)

    # --- logo ----------------------------------------------------------------
    logo = trim(load('logo'))
    logo = fit(logo, 1100, 520)
    logo.save(out / 'img/logo.png', optimize=True)
    layout['logo'] = logo.size

    # --- frame + reel panel --------------------------------------------------
    frame = load('frame')
    if frame is not None:
        fr, (l, t, r, b) = reframe(frame, WIN_W, WIN_H, wall=WALL)
    else:  # Hex Hollow until its frame arrives: plain accent bezel
        fr = Image.new('RGBA', (WIN_W + 2 * WALL, WIN_H + 2 * WALL), (0, 0, 0, 0))
        fr.alpha_composite(plate(fr.width, fr.height, accent, ink, radius=40))
        l, t, r, b = WALL, WALL, WALL + WIN_W, WALL + WIN_H
    a = fr.getchannel('A')
    ImageDraw.Draw(a).rectangle((l + 1, t + 1, r - 2, b - 2), fill=0)
    fr.putalpha(a)
    # inner shadow: the frame casts a soft dark band onto the reels under it
    m = Image.new('L', fr.size, 255)
    ImageDraw.Draw(m).rectangle((l + 18, t + 22, r - 18, b - 14), fill=0)
    m = m.filter(ImageFilter.GaussianBlur(16))
    hole = Image.new('L', fr.size, 0)
    ImageDraw.Draw(hole).rectangle((l + 1, t + 1, r - 2, b - 2), fill=255)
    inner = Image.new('RGBA', fr.size, (0, 0, 0, 0))
    inner.putalpha(ImageChops.multiply(m, hole).point(lambda v: int(v * 0.7)))
    inner.alpha_composite(fr)
    fr = inner
    fr.save(out / 'img/reel_frame.png', optimize=True)
    layout['frame'] = {'w': fr.width, 'h': fr.height, 'l': l, 't': t,
                       'r': fr.width - r, 'b': fr.height - b}

    bg = Image.new('RGB', (982, 597))
    d = ImageDraw.Draw(bg)
    top = tuple(min(255, int(c * 1.6) + 14) for c in ink)
    for y in range(597):
        k = y / 596
        d.line([(0, y), (981, y)], fill=tuple(int(top[i] + (ink[i] * 0.6 - top[i]) * k) for i in range(3)))
    for i in range(1, 5):
        x = 12 + i * 191.6
        d.line([(x, 12), (x, 585)], fill=tuple(int(c * 0.35 + 18) for c in accent), width=2)
    vign = Image.new('L', bg.size, 0)
    ImageDraw.Draw(vign).rounded_rectangle([0, 0, 981, 596], 30, outline=255, width=60)
    bg = Image.composite(Image.new('RGB', bg.size, (0, 0, 0)), bg,
                         vign.filter(ImageFilter.GaussianBlur(40)).point(lambda v: v * 0.6))
    bg.save(out / 'img/reel_bg.jpg', quality=88)

    # --- symbols ---------------------------------------------------------------
    hp_sheet, lp_sheet = load('symbols_hp'), load('symbols_lp')
    if g.get('hp_boxes'):
        hp = [trim(hp_sheet.crop(b)) for b in g['hp_boxes']]
    else:
        hp = cut_sheet(hp_sheet)
    if len(hp) < 7:
        hp = grid_cut(hp_sheet, [4, 3])
    lp = cut_sheet(lp_sheet)
    if len(lp) != 5:
        lp = grid_cut(lp_sheet, [5])
    tiles = {}
    for code, im in zip(g['hp'], hp[:4]):
        tiles[code] = tile(im, 200, 0.9)
    tiles['wild'] = tile(hp[4], 200, 0.92)
    tiles['scatter'] = tile(hp[5], 200, 0.92)
    for code, im in zip(g['lp'], lp[:5]):
        tiles[code] = tile(im, 200, 0.82)
    for code, im in tiles.items():
        im.save(out / f'symbols/{code}.png', optimize=True)
    bonus_art = clean(trim(hp[6]))

    chars = cut_sheet(load('characters'), split_wide=False)
    # drop stray bits, keep the sheet's left-to-right order (the first figure
    # is the theme's lead character)
    biggest = max(c.width * c.height for c in chars)
    heroes = [clean(trim(c)) for c in chars if c.width * c.height > biggest * 0.25][:4]
    hero, hero2 = heroes[0], heroes[1] if len(heroes) > 1 else heroes[0]
    def grounded(h_im):
        h_im = fit(h_im, 700, 1000)
        pad = int(h_im.height * 0.05)
        c = Image.new('RGBA', (h_im.width + 2 * pad, h_im.height + pad), (0, 0, 0, 0))
        m = Image.new('L', c.size)
        ImageDraw.Draw(m).ellipse([pad + h_im.width * 0.08, h_im.height - pad * 0.6,
                                   pad + h_im.width * 0.92, h_im.height + pad * 0.7], fill=170)
        sh = Image.new('RGBA', c.size, (0, 0, 0, 0))
        sh.putalpha(m.filter(ImageFilter.GaussianBlur(pad * 0.55)))
        c.alpha_composite(sh)
        c.alpha_composite(drop_shadow(h_im, dy=0.0, blur=0.012, alpha=0.5), (pad, 0))
        return c
    grounded(hero).save(out / 'img/hero.png', optimize=True)
    grounded(hero2).save(out / 'img/hero2.png', optimize=True)

    # wild on the whole reel: hero full height, the wild tile as a badge at his feet
    big = Image.new('RGBA', (250, 600), (0, 0, 0, 0))
    badge = fit(clean(trim(hp[4])), 230, 170)
    feet = 600 - 6 - badge.height * 0.45          # hero stands behind the badge
    tall = max(heroes, key=lambda c: c.height / c.width)  # narrowest figure fits a reel best
    h_im = fit(tall, 250, feet - 8)
    # wide heroes come out short: lift them so the column reads as one figure
    big.alpha_composite(h_im, ((250 - h_im.width) // 2, int(feet - h_im.height)))
    if h_im.height < 380:  # a short (wide) hero leaves the top empty: glow column behind
        col = Image.new('RGBA', (250, 600), hex_rgb(g['accent']) + (0,))
        m = Image.new('L', (250, 600))
        ImageDraw.Draw(m).ellipse([20, 20, 230, int(feet)], fill=90)
        col.putalpha(m.filter(ImageFilter.GaussianBlur(40)))
        col.alpha_composite(big)
        big = col
    big.alpha_composite(badge, ((250 - badge.width) // 2, 600 - badge.height - 6))
    big = drop_shadow(big, dy=0.015, blur=0.012)
    big.save(out / 'symbols/wild_big.png', optimize=True)

    # --- buy bonus / free spins counter ------------------------------------
    fit(bonus_art, 260, 260).save(out / 'img/buy_bonus.png', optimize=True)
    fit(bonus_art, 300, 150).save(out / 'img/buy_bonus_mob.png', optimize=True)

    ui = load('ui_kit')
    kit = {}
    if ui is not None and g.get('ui_boxes'):
        kit = {n: clean(trim(ui.crop(b))) for n, b in g['ui_boxes'].items()}
    elif ui is not None:
        items = cut_sheet(ui, alpha_cut=160, split_wide=False, min_frac=0.008)
        names = ['big', 'mega', 'epic', 'fs', 'buy', 'plate', 'yes', 'no']
        override = g.get('ui_order')
        if override:
            names = override
        kit = {n: clean(trim(im)) for n, im in zip(names, items)}
    layout['ui_kit'] = bool(kit)

    def title(key, label):
        if key in kit:
            return kit[key]
        return text(label, 150, (255, 246, 210), accent)

    if 'fs' in kit and 'plate' in kit:
        ttl = fit(kit['fs'], 300, 170)
        pl = fit(kit['plate'], 300, 120)
        W_, H_ = 300, int((ttl.height + pl.height * 0.5) / 0.7)
        H_ = max(H_, ttl.height + pl.height)
        fs = Image.new('RGBA', (W_, H_), (0, 0, 0, 0))
        fs.alpha_composite(pl, ((W_ - pl.width) // 2, int(H_ * 0.7 - pl.height / 2)))
        fs.alpha_composite(ttl, ((W_ - ttl.width) // 2, max(0, int(H_ * 0.7 - pl.height / 2) - ttl.height + 10)))
        fs = trim(fs)
        fs.save(out / 'img/fs_counter.png', optimize=True)
        fs.save(out / 'img/fs_counter_mob.png', optimize=True)
        layout['fs_value_top'] = None
    fs_desk = plate(210, 315, accent, ink, radius=36)
    lab = fit(text('FREE', 60, (255, 250, 230), accent), 170, 80)
    lab2 = fit(text('SPINS', 60, (255, 250, 230), accent), 170, 80)
    fs_desk.alpha_composite(lab, ((210 - lab.width) // 2, 34))
    fs_desk.alpha_composite(lab2, ((210 - lab2.width) // 2, 34 + lab.height + 6))
    if 'fs' not in kit or 'plate' not in kit:
        fs_desk.save(out / 'img/fs_counter.png', optimize=True)
    fs_mob = plate(332, 116, accent, ink, radius=30)
    lab = fit(text('FREE SPINS', 60, (255, 250, 230), accent), 180, 70)
    fs_mob.alpha_composite(lab, (22, (116 - lab.height) // 2))
    if 'fs' not in kit or 'plate' not in kit:
        fs_mob.save(out / 'img/fs_counter_mob.png', optimize=True)

    insets = {}
    for key, fname, label in (('big', 'popup_big', 'BIG WIN'), ('mega', 'popup_mega', 'MEGA WIN'),
                              ('epic', 'popup_epic', 'EPIC WIN'), ('fs', 'popup_bonus_spins', 'FREE SPINS'),
                              ('buy', 'popup_buy', 'BUY BONUS')):
        im, inset = popup_plate(title(key, label), accent, ink, panel_img=kit.get('plate'))
        im.save(out / f'img/{fname}.png', optimize=True)
        insets[key] = inset
    layout['popup_insets'] = insets

    for key, glyph, col in (('yes', '✓', (60, 200, 90)), ('no', '✕', (220, 60, 60))):
        if key in kit:
            fit(kit[key], 240, 140).save(out / f'img/btn_{key}.png', optimize=True)
            continue
        btn = plate(240, 140, col, tuple(int(c * 0.45) for c in col), radius=60)
        f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 90)
        dd = ImageDraw.Draw(btn)
        dd.text((120, 66), glyph, font=f, fill=(255, 255, 255), anchor='mm')
        btn.save(out / f'img/btn_{key}.png', optimize=True)

    # --- cover ------------------------------------------------------------
    cv = cover(bgb, 960, 640).convert('RGBA')
    hx = fit(hero, 460, 600)
    cv.alpha_composite(hx, (960 - hx.width - 10, 640 - hx.height))
    lg = fit(logo, 560, 300)
    cv.alpha_composite(lg, (40, (640 - lg.height) // 2 - 40))
    cv.convert('RGB').save(out / 'img/cover.jpg', quality=86)

    # weight: popups never show wider than ~600 css px; heroes ~460. Then the
    # same 256-colour octree + dither the rest of front/img uses.
    for f in (out / 'img').glob('popup_*.png'):
        im = Image.open(f)
        if im.width > 760:
            im.resize((760, round(im.height * 760 / im.width)), Image.LANCZOS).save(f)
    for f in (out / 'img').glob('hero*.png'):
        im = Image.open(f)
        if im.height > 760:
            im.resize((round(im.width * 760 / im.height), 760), Image.LANCZOS).save(f)
    for f in list((out / 'img').glob('*.png')) + list((out / 'symbols').glob('*.png')):
        im = Image.open(f).convert('RGBA')
        q = im.quantize(256, Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
        q.save(f, optimize=True)

    (out / 'layout.json').write_text(json.dumps(layout, indent=1))
    print(slug, 'frame', layout['frame'], 'mob art', layout['mob_base_art'], 'ui', layout['ui_kit'])


if __name__ == '__main__':
    slugs = list(GAMES) if sys.argv[1:] == ['all'] else sys.argv[1:]
    for s in slugs:
        build(s)
