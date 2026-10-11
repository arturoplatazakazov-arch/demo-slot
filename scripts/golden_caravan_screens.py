"""Golden Caravan — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Forked from scripts/sugar_galaxy_screens.py (same avalanche game, same
contract): a full-screen skeleton authored on the game's design canvas
(origin = canvas centre, 1 unit = 1 design px, y up), `intro` (3s) -> `idle`
(4s seamless loop, first idle frame == last intro frame). Four variants:
feature/bonus x desk (1932x940) / mob (780x1416). The game's background is NOT
in the skeleton — slot.js puts the game's own bg PNG under the canvas (cover).

Art is the game's own: symbol statics (Export/<folder>/static.png — note the
bomb / multiplier folders are `Bomb`, `2x`, `3x`, `5x`), logo.png, the
hieroglyph reel frame (frame.png, 9-sliced into card frames), the hero camel
(hero_base atlas) and pieces cut from the popup atlases (light bursts, flare,
blik sparkle, gold dish, winged scarabs, dark plaques). Panels / texts are
drawn here with PIL in the popups' gold-on-lapis Egyptian style (Cinzel).

Usage:
  python scripts/golden_caravan_screens.py <fonts_dir> [out_dir]

fonts_dir — cinzel.ttf (front/fonts woff2 converted with fontTools:
            TTFont(woff2).flavor = None; .save(ttf))
out_dir   — default front/img/golden-caravan/screens
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, out_back, out_cubic, pulse, rays, seg, soft_glow, text_img,
    trim, vgrad, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(ROOT, 'front', 'img', 'golden-caravan')
FONTS = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ART_DIR, 'screens')

INTRO = 3.0
IDLE = 4.0
DESK = (1932, 940)
MOB = (780, 1416)


# --------------------------------------------------------------------------
# source art

def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)
    if weight:
        f.set_variation_by_axes([weight])
    return f


STATIC_FOLDERS = {'x2': '2x', 'x3': '3x', 'x5': '5x', 'bomb': 'Bomb'}


def symbol(code):
    folder = STATIC_FOLDERS.get(code, code)
    return trim(Image.open(os.path.join(ART_DIR, 'Export', folder, 'static.png')).convert('RGBA'))


def parse_atlas(path):
    regions, page, cur = {}, None, None
    for line in open(path):
        line = line.rstrip('\n')
        if not line.strip():
            cur = None
            continue
        if ':' not in line:
            if page is None or (cur is None and line.endswith('.png')):
                page, cur = line.strip(), None
            else:
                cur = regions[line.strip()] = {}
            continue
        if cur is not None:
            k, v = (s.strip() for s in line.split(':', 1))
            cur[k] = v
    return regions


def atlas_region(folder, name):
    """One region of a top-level Spine export, un-rotated. The page is always
    the folder's own animation.png (atlas page names are not trusted)."""
    folder = os.path.join(ART_DIR, folder)
    r = parse_atlas(os.path.join(folder, 'animation.atlas'))[name]
    page = Image.open(os.path.join(folder, 'animation.png')).convert('RGBA')
    x, y, w, h = map(int, r['bounds'].split(','))
    if r.get('rotate') in ('90', 'true'):
        im = page.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
    else:
        im = page.crop((x, y, x + w, y + h))
    return trim(im)


def logo_hd():
    """The in-game logo is only 292x222 — 2x Lanczos + unsharp for the screens."""
    im = Image.open(os.path.join(ART_DIR, 'logo.png')).convert('RGBA')
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2.2, percent=90, threshold=2))
    rgb.putalpha(im.getchannel('A'))
    return trim(rgb)


GOLD = [(0, hexc('fff6c8')), (0.45, hexc('ffd36a')), (1, hexc('c9861c'))]
SAND = [(0, hexc('fffaf0')), (1, hexc('f3dcae'))]
STROKE = '3a1c06'


def title(text, size, fill=GOLD, glow='ffb43a', weight=900):
    return text_img(text, font('cinzel', size, weight), fill, stroke=STROKE, stroke_w=max(3, size // 10),
                    glow=glow, glow_r=max(5, size // 7), shadow='120700')


def lines(rows, size, fill=SAND, gap=0.12, weight=800):
    """Centered multi-line caption (each row its own stroked line)."""
    ims = [text_img(r, font('cinzel', size, weight), fill, stroke='1f0f03', stroke_w=max(3, size // 9),
                    glow=None, shadow='0a0400') for r in rows]
    w = max(i.width for i in ims)
    step = int(size * (1 + gap))
    h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


FRAME = Image.open(os.path.join(ART_DIR, 'frame.png')).convert('RGBA')


def nine_slice(src, w, h, c):
    """Stretch `src` to w x h keeping its c-px corners intact."""
    sw, sh = src.size
    out = Image.new('RGBA', (w, h))

    def put(box, dst):
        x0, y0, x1, y1 = box
        dx0, dy0, dx1, dy1 = dst
        if x1 > x0 and y1 > y0 and dx1 > dx0 and dy1 > dy0:
            out.paste(src.crop(box).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS), (dx0, dy0))

    xs, dxs = (0, c, sw - c, sw), (0, c, w - c, w)
    ys, dys = (0, c, sh - c, sh), (0, c, h - c, h)
    for i in range(3):
        for j in range(3):
            put((xs[i], ys[j], xs[i + 1], ys[j + 1]), (dxs[i], dys[j], dxs[i + 1], dys[j + 1]))
    return out


def card_panel(w, h, border=34):
    """Lapis card (the game's UI_Multy blue) inside the reel's hieroglyph
    gold frame, 9-sliced at a thinner border."""
    k = border / 60.0  # frame.png's border is ~56-63 px
    fr = FRAME.resize((round(FRAME.width * k), round(FRAME.height * k)), Image.LANCZOS)
    frame = nine_slice(fr, w, h, round(110 * k))
    out = Image.new('RGBA', (w, h))
    inset = border - 6
    body = vgrad((w, h), [(0, hexc('123a78', 245)), (0.5, hexc('0a2552', 248)), (1, hexc('06142f', 250))])
    m = Image.new('L', (w, h))
    ImageDraw.Draw(m).rectangle([inset, inset, w - inset - 1, h - inset - 1], fill=255)
    out.paste(body, (0, 0), m)
    # warm sand light falling from the top + soft inner vignette
    hl = Image.new('L', (w, h))
    ImageDraw.Draw(hl).ellipse([w * 0.05, -h * 0.35, w * 0.95, h * 0.45], fill=70)
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(w * 0.12)), m)
    out.paste(Image.new('RGBA', (w, h), hexc('ffcf7a')), (0, 0), hl)
    vg = Image.new('L', (w, h), 0)
    ImageDraw.Draw(vg).rectangle([inset, inset, w - inset - 1, h - inset - 1], outline=120, width=26)
    vg = ImageChops.multiply(vg.filter(ImageFilter.GaussianBlur(16)), m)
    out.paste(Image.new('RGBA', (w, h), hexc('020812')), (0, 0), vg)
    out.alpha_composite(frame)
    return out


def cartouche(w, h):
    """Count plaque: lapis capsule with a double gold rim (the logo's
    cartouche look), drawn at 2x and downsampled."""
    k = 2
    pad = 22
    W, H = (w + 2 * pad) * k, (h + 2 * pad) * k
    box = [pad * k, pad * k, W - pad * k - 1, H - pad * k - 1]
    r = h * k // 2
    out = Image.new('RGBA', (W, H))
    sh = Image.new('L', (W, H))
    ImageDraw.Draw(sh).rounded_rectangle(box, r, fill=200)
    out.paste(Image.new('RGBA', (W, H), hexc('140800')), (0, 6 * k), sh.filter(ImageFilter.GaussianBlur(10 * k)))
    m = Image.new('L', (W, H))
    ImageDraw.Draw(m).rounded_rectangle(box, r, fill=255)
    gold = vgrad((W, H), [(0, hexc('fff1b0')), (0.35, hexc('e7b04a')), (0.7, hexc('9a5a12')), (1, hexc('f4cf6e'))])
    out.paste(gold, (0, 0), m)
    rim = 9 * k
    inner = [box[0] + rim, box[1] + rim, box[2] - rim, box[3] - rim]
    m2 = Image.new('L', (W, H))
    ImageDraw.Draw(m2).rounded_rectangle(inner, r - rim, fill=255)
    out.paste(Image.new('RGBA', (W, H), hexc('5a2f06')), (0, 0), m2)
    rim2 = 3 * k
    inner2 = [inner[0] + rim2, inner[1] + rim2, inner[2] - rim2, inner[3] - rim2]
    m3 = Image.new('L', (W, H))
    ImageDraw.Draw(m3).rounded_rectangle(inner2, r - rim - rim2, fill=255)
    body = vgrad((W, H), [(0, hexc('1c4a94')), (0.55, hexc('0c2a5e')), (1, hexc('061634'))])
    out.paste(body, (0, 0), m3)
    hl = Image.new('L', (W, H))
    ImageDraw.Draw(hl).rounded_rectangle([inner2[0] + 8 * k, inner2[1] + 4 * k, inner2[2] - 8 * k,
                                          inner2[1] + (inner2[3] - inner2[1]) * 0.45], r // 2, fill=55)
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(6 * k)), m3)
    out.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0), hl)
    return out.resize((W // k, H // k), Image.LANCZOS)


def soft(im, w):
    """Blurry glow art gains nothing from full res — keep it small, stretch on screen."""
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


ART = {
    'logo': logo_hd(),
    'burst': soft(atlas_region('popup_bonus_spins_win', 'popup_big_win_twxt_light'), 640),
    'flare': soft(atlas_region('popup_epic_win', 'popup_epic_win_bg_light1'), 480),
    'blik': atlas_region('popup_bonus_spins_win', 'blik_heart2_png'),
    'dish': atlas_region('popup_bonus_spins_win', 'bonus_spins_win_bg'),
    'plaque': cartouche(250, 118),
    'band': atlas_region('popup_bonus_spins_total_win', 'bonus_spins_total_win_plashka'),
    'wings': atlas_region('popup_bonus_spins_win', 'bonus_spins_win_ptah'),
    'scarab': atlas_region('popup_epic_win', 'popup_epic_win_ptah'),
    'camel': atlas_region('hero_base', 'base_came'),
    'chest': trim(Image.open(os.path.join(ART_DIR, 'UI_Buybonus_button.png')).convert('RGBA')),
    'glow': soft_glow(256),
    'rays': rays(560, n=16),
}
for code in ('x2', 'x3', 'x5', 'bomb', 'scatter', 'wild', 'rare_faraon', 'rare_skorobei', 'rare_snake'):
    ART[code] = symbol(code)
ART['logo_flash'] = flash_of(ART['logo'], 0.9)
ART['bomb_flash'] = flash_of(ART['bomb'], 0.9)
ART['scatter_flash'] = flash_of(ART['scatter'], 0.8)

# Feature cards — copy matches the seed (app/seed/golden_caravan.py): 8+ of a
# kind anywhere pays and tumbles (cascade trail x1-x2-x3-x5), x2/x3/x5 tokens
# add into the step multiplier, bombs clear their row + column, 3/4/5
# scatters = 8/10/12 free spins (retriggers), bonus buy = 100x bet.
CARDS = [
    ('tumble', 'AVALANCHE', ['8+ SAME SYMBOLS', 'ANYWHERE WIN']),
    ('multi', 'MULTIPLIERS', ['x2 x3 x5 TOKENS', 'BOOST THE CASCADE']),
    ('bomb', 'BOMBS', ['CLEAR THEIR WHOLE', 'ROW AND COLUMN']),
    ('fs', 'FREE SPINS', ['3 / 4 / 5 SCATTERS', 'AWARD 8 / 10 / 12']),
]
for key, head, desc in CARDS:
    ART[f't_{key}'] = title(head, 56)
    ART[f'd_{key}'] = lines(desc, 34)
ART['tap_continue'] = title('TAP TO CONTINUE', 52, fill=SAND, glow='ffae2e')
ART['tap_start'] = title('TAP TO START', 58, fill=SAND, glow='ffae2e')
ART['t_free_spins'] = title('FREE SPINS', 140)
ART['t_you_won'] = title('YOU HAVE WON', 54, fill=SAND, glow='ff9a1f')
ART['d_buy'] = lines(['BUY BONUS', '100x BET'], 32, fill=GOLD)
ART['d_chip_multi'] = lines(['MULTIPLIERS ADD UP', 'ON EVERY CASCADE'], 36)
ART['d_chip_fs'] = lines(['SCATTERS RETRIGGER', 'UP TO +12 SPINS'], 36)
ART['panel_desk'] = card_panel(408, 448)
ART['panel_mob'] = card_panel(358, 420, border=30)


# --------------------------------------------------------------------------
# motion helpers (all idle offsets are 0 at t=0 so idle starts where intro ends)

def bob(t, amp, period=IDLE, phase=0.0):
    return amp * (wave(t, period, phase) - wave(0, period, phase))


def pop(t, t0, dur=0.55, s0=0.3):
    """Scale-in with overshoot, 1 after t0+dur."""
    return seg(t, t0, t0 + dur, s0, 1.0, out_back)


def fade(t, t0, dur=0.3):
    return seg(t, t0, t0 + dur, 0.0, 1.0, out_cubic)


def move(sk, bone, intro_fn, idle_fn):
    """Translate written as an offset from the bone's setup position (the kit
    wants the absolute local position, so the setup x/y is added back)."""
    d = next(b for b in sk.bones if b['name'] == bone)
    bx, by = d.get('x', 0), d.get('y', 0)

    def absolute(f):
        return lambda t: (bx + f(t)[0], by + f(t)[1])

    sk.both(bone, 'translate', absolute(intro_fn), absolute(idle_fn))


def uniform(fn):
    return lambda t: (fn(t),) * 2


def add_art(sk, *keys):
    for k in keys:
        sk.image(k, ART[k])


def twinkles(sk, parent, spots, seed, start=1.4, tint='fff0c8ff'):
    """Additive blik sparkles blinking out of phase; seamless over IDLE."""
    rnd = random.Random(seed)
    for i, (x, y, s) in enumerate(spots):
        b = sk.bone(f'tw{i}', parent, x, y)
        sk.slot(f'tw{i}', b, 'blik', w=150 * s, blend='additive', color=tint)
        ph = rnd.random()
        per = rnd.choice((1.0, 2.0, 4.0))

        def blink(tau, ph=ph, per=per):
            return math.sin(math.pi * (((tau / per) + ph) % 1.0)) ** 4

        env = lambda t: clamp((t - start) / 0.6)  # noqa: E731
        sk.both(b, 'scale', uniform(lambda t, f=blink: 0.25 + 0.75 * f(t - INTRO) * env(t)),
                uniform(lambda t, f=blink: 0.25 + 0.75 * f(t)))
        # 4-point sparkle: a 90deg turn per loop is seamless
        sk.both(b, 'rotate', lambda t: 90 * (t - INTRO) / IDLE, lambda t: 90 * t / IDLE)
        sk.both(f'tw{i}', 'alpha', lambda t, f=blink: f(t - INTRO) * env(t), lambda t, f=blink: f(t))


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.9, rays_w=None, rays_alpha=0.3):
    """Golden popup light burst (breathing) + slowly turning rays behind it."""
    rw = rays_w or w * 0.8
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=rw, blend='additive', color='ffd27aff')
    # 16 rays: a 22.5deg turn per loop is seamless
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both(rb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.8, 0.4, 1.0)), uniform(lambda t: 1))
    sk.both(f'{name}_rays', 'alpha', lambda t: rays_alpha * fade(t, t0, 0.6),
            lambda t: rays_alpha * (1 - 0.3 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, 'burst', w=w, blend='additive')
    sk.both(b, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.3, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.05)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.5),
            lambda t: alpha * (1 - 0.18 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))


def floater(sk, name, region, parent, x, y, w, t0, amp=10, period=IDLE, phase=0.0, rot_amp=0.0,
            slide=(0, -40), alpha=1.0):
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, region, w=w)

    def pos(t, idle_t):
        k = seg(t, t0, t0 + 0.8, 1.0, 0.0)
        return (slide[0] * k, slide[1] * k + bob(idle_t, amp, period, phase))

    move(sk, b, lambda t: pos(t, 0), lambda t: pos(99, t))
    if rot_amp:
        sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, rot_amp, period, phase + 0.25))
    sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.7, 0.5)), uniform(lambda t: 1))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.4), lambda t: alpha)
    return b


def camel(sk, x, y, w, t0, flip=False):
    """Hero camel walks in from the side and breathes (slight y-scale)."""
    b = sk.bone('camel', 'root', x, y, sx=-1 if flip else 1)
    sk.slot('camel', b, 'camel', w=w)
    from_x = (1 if flip else -1) * 260
    move(sk, b, lambda t: (seg(t, t0, t0 + 0.9, from_x, 0), 0), lambda t: (0, 0))
    sx = -1 if flip else 1
    sk.both(b, 'scale', lambda t: (sx, 1), lambda t: (sx * breathe(t, 2.0, 0.008), breathe(t, 2.0, 0.018)))
    sk.both('camel', 'alpha', lambda t: fade(t, t0, 0.5), lambda t: 1)


def tap_hint(sk, region, y, w):
    b = sk.bone('tap', 'root', 0, y)
    sk.slot('tap', b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: seg(t, 2.2, 2.7, 0.8, 1.0, out_back)), uniform(lambda t: breathe(t, 2.0, 0.04)))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.5),
            lambda t: 0.775 + 0.225 * math.cos(2 * math.pi * t / 2.0))


# --------------------------------------------------------------------------
# feature (preview) screen

def card_icons(sk, key, parent, t0, s):
    """Card illustration, centred on `parent`; s = icon scale (1 = ~170 units)."""
    if key == 'tumble':
        for i, (code, x, y, sz, ph) in enumerate((('rare_skorobei', -82, -10, 112, 0.0),
                                                  ('rare_snake', 82, -10, 112, 0.33),
                                                  ('rare_faraon', 0, 18, 128, 0.66))):
            b = sk.bone(f'{key}_i{i}', parent, x * s, y * s)
            sk.slot(f'{key}_i{i}', b, code, w=sz * s)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.1 * i: pop(t, d, 0.5, 0.0)), uniform(lambda t: 1))
            # avalanche: each tile drops in from above, then bobs
            move(sk, b, lambda t, d=t0 + 0.1 * i: (0, seg(t, d, d + 0.45, 90 * s, 0, out_back)),
                    lambda t, ph=ph: (0, bob(t, 6 * s, 2.0, ph)))
    elif key == 'multi':
        for i, (code, x, y, sz) in enumerate((('x2', -104, -18, 96), ('x3', 0, 26, 110), ('x5', 104, -18, 96))):
            b = sk.bone(f'{key}_i{i}', parent, x * s, y * s)
            sk.slot(f'{key}_i{i}', b, code, w=sz * s * 1.35)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.08 * i: pop(t, d, 0.45, 0.0)),
                    uniform(lambda t, i=i: 1 + 0.12 * pulse(t, 2.0, i * 0.15, sharp=6)))
            sk.both(b, 'rotate', lambda t: 0, lambda t, i=i: bob(t, 6, 2.0, i * 0.25))
    elif key == 'bomb':
        g = sk.bone(f'{key}_glow', parent, 0, -4 * s)
        sk.slot(f'{key}_glow', g, 'glow', w=250 * s, blend='additive', color='ff9a3cff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 1.0, 0.18)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.65 * fade(t, t0), lambda t: 0.65 - 0.3 * pulse(t, 1.0, 0.0, 2))
        b = sk.bone(f'{key}_i0', parent)
        sk.slot(f'{key}_i0', b, 'bomb', w=170 * s)
        fl = sk.slot(f'{key}_fl', b, 'bomb_flash', w=170 * s, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)),
                uniform(lambda t: 1 + 0.06 * pulse(t, 1.0, 0.0, 4)))
        # fuse jitter: quick shake in the first quarter of every second
        sk.both(b, 'rotate', lambda t: 0,
                lambda t: 5 * math.sin(2 * math.pi * t * 6) * pulse(t, 1.0, 0.0, 2))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.35, t0 + 0.75, 0.8, 0.0) if t > t0 + 0.35 else 0,
                lambda t: 0.45 * pulse(t, 1.0, 0.0, 6))
    elif key == 'fs':
        g = sk.bone(f'{key}_glow', parent, 0, 0)
        sk.slot(f'{key}_glow', g, 'glow', w=250 * s, blend='additive', color='ffc85aff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.15)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.55 * fade(t, t0), lambda t: 0.55)
        b = sk.bone(f'{key}_i0', parent)
        sk.slot(f'{key}_i0', b, 'scatter', w=200 * s)
        fl = sk.slot(f'{key}_fl', b, 'scatter_flash', w=200 * s, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)), uniform(lambda t: 1))
        move(sk, b, lambda t: (0, 0), lambda t: (0, bob(t, 8 * s, 2.0)))
        sk.both(fl, 'alpha', lambda t: 0, lambda t: 0.5 * pulse(t, 4.0, 0.5, 8))


def feature_card(sk, idx, key, x, y, panel, pw, ph, t0, s):
    c = sk.bone(f'card{idx}', 'root', x, y)
    sk.slot(f'card{idx}', c, panel, w=pw)
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -70, 0)),
            lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    ti, di = ART[f't_{key}'], ART[f'd_{key}']
    inner = pw - 2 * 34 - 24
    t_w = min(ti.width * 0.9 * s, inner)
    d_w = min(di.width * 0.85 * s, inner)
    t_y = ph * 0.5 - 70 * s
    d_y = -ph * 0.5 + 78 * s
    tb = sk.bone(f'card{idx}_t', c, 0, t_y)
    sk.slot(f'card{idx}_t', tb, f't_{key}', w=t_w)
    sk.both(f'card{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.15), lambda t: 1)

    # illustration centred in the gap between the title and the caption
    gap_top = t_y - t_w * ti.height / ti.width / 2
    gap_bot = d_y + d_w * di.height / di.width / 2
    ib = sk.bone(f'card{idx}_icon', c, 0, (gap_top + gap_bot) / 2)
    card_icons(sk, key, ib, t0 + 0.25, s)

    db = sk.bone(f'card{idx}_d', c, 0, d_y)
    sk.slot(f'card{idx}_d', db, f'd_{key}', w=d_w)
    sk.both(f'card{idx}_d', 'alpha', lambda t: fade(t, t0 + 0.3), lambda t: 1)


def build_feature(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'feature_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'blik', 'flare', 'tap_continue',
            'rare_faraon', 'rare_skorobei', 'rare_snake', 'x2', 'x3', 'x5', 'bomb', 'bomb_flash', 'scatter',
            'scatter_flash', 'panel_desk' if variant == 'desk' else 'panel_mob',
            *[f't_{k}' for k, _, _ in CARDS], *[f'd_{k}' for k, _, _ in CARDS])

    if variant == 'desk':
        logo_y, logo_w = 312, 360
        cards = [(-660 + 440 * i, -92) for i in range(4)]
        panel, pw, ph, s = 'panel_desk', 408, 448, 1.0
        tap_y, tap_w = -398, 400
        spots = [(-260, 400, 0.8), (250, 230, 0.7), (-900, -380, 0.6), (900, -390, 0.6), (-470, 180, 0.5),
                 (480, 420, 0.6)]
    else:
        logo_y, logo_w = 548, 330
        cards = [(-188, 192), (188, 192), (-188, -246), (188, -246)]
        panel, pw, ph, s = 'panel_mob', 358, 420, 0.86
        tap_y, tap_w = -560, 400
        spots = [(-240, 640, 0.6), (250, 450, 0.7), (-330, 420, 0.5), (330, 650, 0.5), (-300, -640, 0.5),
                 (300, -650, 0.5)]

    light_burst(sk, 'burst', 'root', 0, logo_y - 10, logo_w * 2.0, t0=0.0, alpha=0.45, rays_alpha=0.22)
    fb = sk.bone('flare', 'root', 0, logo_y - logo_w * 0.3)
    sk.slot('flare', fb, 'flare', w=logo_w * 2.2, blend='additive')
    sk.both(fb, 'scale', lambda t: (seg(t, 0.5, 1.1, 0.1, 1.0), 1), lambda t: (breathe(t, 2.0, 0.08), 1))
    sk.both('flare', 'alpha', lambda t: 0.6 * fade(t, 0.5, 0.4), lambda t: 0.6)

    if variant == 'desk':
        add_art(sk, 'camel', 'chest', 'd_buy')
        camel(sk, -700, 300, 400, 0.4)
        cb = floater(sk, 'chest', 'chest', 'root', 720, 330, 210, 0.55, amp=8, rot_amp=3)
        bb = sk.bone('buy', 'root', 720, 196)
        sk.slot('buy', bb, 'd_buy', w=ART['d_buy'].width * 0.9)
        sk.both('buy', 'alpha', lambda t: fade(t, 0.8, 0.4), lambda t: 1)
        _ = cb

    lb = sk.bone('logo', 'root', 0, logo_y)
    sk.slot('logo', lb, 'logo', w=logo_w)
    sk.slot('logo_flash', lb, 'logo_flash', w=logo_w, blend='additive')
    sk.both(lb, 'scale', uniform(lambda t: seg(t, 0.15, 0.85, 0.2, 1.0, out_back)),
            uniform(lambda t: breathe(t, IDLE, 0.025)))
    move(sk, lb, lambda t: (0, 0), lambda t: (0, bob(t, 6)))
    sk.both('logo', 'alpha', lambda t: fade(t, 0.15, 0.25), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: seg(t, 0.6, 1.1, 0.85, 0.0) if t >= 0.6 else 0,
            lambda t: 0.4 * pulse(t, IDLE, 0.55, 10))

    for i, ((x, y), (key, _, _)) in enumerate(zip(cards, CARDS)):
        feature_card(sk, i, key, x, y, panel, pw, ph, 0.75 + 0.18 * i, s)

    twinkles(sk, 'root', spots, seed=7)
    tap_hint(sk, 'tap_continue', tap_y, tap_w)
    sk.write()


# --------------------------------------------------------------------------
# bonus screen

def info_chip(sk, idx, icon, text, x, y, cw, t0, from_x, icon_w, ribbon=True):
    """Compact "icon + caption" group, optionally on its own dark plaque."""
    c = sk.bone(f'chip{idx}', 'root', x, y)
    if ribbon:
        sk.slot(f'chip{idx}', c, 'band', w=cw, h=150)
        sk.both(f'chip{idx}', 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1)
    move(sk, c, lambda t: (seg(t, t0, t0 + 0.6, from_x, 0), 0), lambda t: (0, bob(t, 4, IDLE, idx * 0.5)))
    tw_ = min(ART[text].width * 0.85, cw - icon_w - 110)
    gap = 26
    total = icon_w + gap + tw_
    ib = sk.bone(f'chip{idx}_i', c, -total / 2 + icon_w / 2, 2)
    sk.slot(f'chip{idx}_i', ib, icon, w=icon_w)
    sk.both(ib, 'scale', uniform(lambda t: pop(t, t0 + 0.3, 0.5, 0.0)),
            uniform(lambda t: 1 + 0.1 * pulse(t, 2.0, idx * 0.25, 6)))
    sk.both(ib, 'rotate', lambda t: 0, lambda t: bob(t, 8, 2.0, idx * 0.5))
    tb = sk.bone(f'chip{idx}_t', c, total / 2 - tw_ / 2, 0)
    sk.slot(f'chip{idx}_t', tb, text, w=tw_)
    sk.both(f'chip{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.25, 0.4), lambda t: 1)


def build_bonus(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'bonus_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'burst', 'rays', 'flare', 'glow', 'blik', 'dish', 'plaque', 'band', 'wings', 'x2', 'x3',
            'x5', 'bomb', 'scatter', 't_free_spins', 't_you_won', 'd_chip_multi', 'd_chip_fs', 'tap_start')

    if variant == 'desk':
        wings_y, wings_w = 398, 560
        title_y, title_w = 292, 800
        dish_y, dish_w = 22, 520
        chips = [(-370, -258, 700, -300), (370, -258, 700, 300)]
        band = (0, -258, 1560)
        chip_icon = 112
        tap_y, tap_w = -398, 400
        tokens = [('x2', -380, 92), ('x3', 380, 92), ('x5', -380, -60), ('bomb', 380, -60)]
        token_w = 112
        spots = [(-470, 380, 0.8), (480, 380, 0.9), (-880, -330, 0.7), (870, -330, 0.6), (-200, 140, 0.5),
                 (200, -120, 0.5)]
    else:
        wings_y, wings_w = 640, 520
        title_y, title_w = 540, 680
        dish_y, dish_w = 210, 560
        chips = [(0, -220, 740, -420), (0, -392, 740, 420)]
        band = None
        chip_icon = 104
        tap_y, tap_w = -585, 400
        tokens = [('x2', -290, 420), ('x3', 290, 420), ('x5', -290, -10), ('bomb', 290, -10)]
        token_w = 100
        spots = [(-300, 690, 0.5), (300, 690, 0.5), (-340, 230, 0.5), (340, 0, 0.6), (-300, -640, 0.5),
                 (300, -650, 0.5)]

    dish_h = dish_w * ART['dish'].height / ART['dish'].width
    plate_y = dish_y - dish_h * 0.2
    plate_w = dish_w * 0.5

    light_burst(sk, 'burst', 'root', 0, dish_y + 10, dish_w * 1.9, t0=0.6, alpha=0.4, rays_w=dish_w * 2.2,
                rays_alpha=0.2)
    fb = sk.bone('flare', 'root', 0, title_y - 10)
    sk.slot('flare', fb, 'flare', w=title_w * 1.4, blend='additive')
    sk.both(fb, 'scale', lambda t: (seg(t, 0.8, 1.3, 0.1, 1.0), 1), lambda t: (breathe(t, 2.0, 0.08), 1))
    sk.both('flare', 'alpha', lambda t: 0.55 * fade(t, 0.8, 0.4), lambda t: 0.55)

    if variant == 'desk':
        add_art(sk, 'camel')
        camel(sk, -700, -48, 380, 0.5)
        sg = sk.bone('scat_glow', 'root', 720, -40)
        sk.slot('scat_glow', sg, 'glow', w=420, blend='additive', color='ffb84aff')
        sk.both('scat_glow', 'alpha', lambda t: 0.45 * fade(t, 0.7, 0.5), lambda t: 0.45 - 0.15 * pulse(t, 2.0, 0, 2))
        floater(sk, 'scat', 'scatter', 'root', 720, -40, 300, 0.7, amp=10, rot_amp=4)

    # gold treasure dish (the bonusSpinsWin popup's own card) behind the count
    db = sk.bone('dish', 'root', 0, dish_y)
    sk.slot('dish', db, 'dish', w=dish_w)
    sk.both(db, 'scale', uniform(lambda t: pop(t, 0.5, 0.7, 0.2)), uniform(lambda t: breathe(t, IDLE, 0.015)))
    sk.both('dish', 'alpha', lambda t: fade(t, 0.5, 0.3), lambda t: 1)

    # winged scarab crest drops in, "FREE SPINS" slams down with a flash
    wb = sk.bone('wings', 'root', 0, wings_y)
    sk.slot('wings', wb, 'wings', w=wings_w)
    move(sk, wb, lambda t: (0, seg(t, 0.15, 0.7, 60, 0)), lambda t: (0, bob(t, 4)))
    sk.both(wb, 'scale', lambda t: (seg(t, 0.15, 0.7, 0.3, 1.0, out_back), 1), lambda t: (breathe(t, 2.0, 0.02), 1))
    sk.both('wings', 'alpha', lambda t: fade(t, 0.15, 0.3), lambda t: 1)

    tb = sk.bone('title', 'root', 0, title_y)
    sk.slot('title', tb, 't_free_spins', w=title_w)
    sk.image('t_free_spins_flash', flash_of(ART['t_free_spins'], 0.9))
    sk.slot('title_flash', tb, 't_free_spins_flash', w=title_w, blend='additive')

    def slam(t):
        return seg(t, 0.35, 0.8, 2.2, 0.94, out_cubic) if t < 0.8 else seg(t, 0.8, 1.05, 0.94, 1.0, out_back)

    sk.both(tb, 'scale', uniform(slam), uniform(lambda t: breathe(t, 2.0, 0.025)))
    sk.both('title', 'alpha', lambda t: fade(t, 0.35, 0.2), lambda t: 1)
    sk.both('title_flash', 'alpha', lambda t: seg(t, 0.8, 1.3, 0.9, 0.0) if t >= 0.8 else 0,
            lambda t: 0.35 * pulse(t, IDLE, 0.5, 10))

    # "YOU HAVE WON" inside the dish's upper half
    yb = sk.bone('won', 'root', 0, dish_y + dish_h * 0.13)
    sk.slot('won', yb, 't_you_won', w=dish_w * 0.6)
    move(sk, yb, lambda t: (0, seg(t, 0.9, 1.3, 30, 0)), lambda t: (0, 0))
    sk.both('won', 'alpha', lambda t: fade(t, 0.9, 0.4), lambda t: 1)

    # count plaque on the dish's lower rim (the live spin count is a DOM
    # overlay glued to bone "count")
    pb = sk.bone('plate', 'root', 0, plate_y)
    sk.slot('plate', pb, 'plaque', w=plate_w)
    sk.bone('count', pb, 0, 0)
    sk.both(pb, 'scale', uniform(lambda t: pop(t, 1.0, 0.6, 0.0)),
            uniform(lambda t: 1 + 0.05 * pulse(t, 2.0, 0.0, 6)))
    sk.both('plate', 'alpha', lambda t: fade(t, 1.0, 0.2), lambda t: 1)

    # multiplier tokens + bomb flanking the dish (pop in, then bob)
    for i, (code, x, y) in enumerate(tokens):
        b = sk.bone(f'tok{i}', 'root', x, y)
        tw = token_w * (1.2 if code == 'bomb' else 1.3)
        sk.slot(f'tok{i}', b, code, w=tw)
        d = 1.3 + 0.12 * i
        sk.both(b, 'scale', uniform(lambda t, d=d: pop(t, d, 0.5, 0.0)),
                uniform(lambda t, i=i: 1 + 0.1 * pulse(t, 2.0, i * 0.12, 6)))
        move(sk, b, lambda t, d=d, x=x: (seg(t, d, d + 0.5, -x * 0.5, 0), 0),
                lambda t, i=i: (0, bob(t, 10, 2.0, i * 0.25)))
        sk.both(b, 'rotate', lambda t: 0, lambda t, i=i: bob(t, 8, IDLE, i * 0.25))
        sk.both(f'tok{i}', 'alpha', lambda t, d=d: fade(t, d, 0.25), lambda t: 1)

    if band:
        bx, by, bw = band
        rb = sk.bone('band', 'root', bx, by)
        sk.slot('band', rb, 'band', w=bw, h=160)
        sk.both(rb, 'scale', lambda t: (seg(t, 1.5, 2.0, 0.2, 1.0), 1), uniform(lambda t: 1))
        sk.both('band', 'alpha', lambda t: fade(t, 1.5, 0.4), lambda t: 1)
    (x0, y0, cw0, f0), (x1, y1, cw1, f1) = chips
    info_chip(sk, 0, 'x5', 'd_chip_multi', x0, y0, cw0, 1.6, f0, chip_icon * 1.3, ribbon=not band)
    info_chip(sk, 1, 'scatter', 'd_chip_fs', x1, y1, cw1, 1.75, f1, chip_icon * 1.45, ribbon=not band)

    twinkles(sk, 'root', spots, seed=11)
    tap_hint(sk, 'tap_start', tap_y, tap_w)
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
