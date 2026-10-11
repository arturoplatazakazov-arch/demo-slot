"""Lucky Joker (3x3 Hold & Win) — feature (preview) screen + bonus screen as
Spine 4.1 skeletons.

Same contract as scripts/sugar_galaxy_screens.py: a full-screen skeleton
authored on the game's design canvas (origin = canvas centre, 1 unit = 1
design px, y up), `intro` (3s) -> `idle` (4s seamless loop, first idle frame
== last intro frame). Four variants: feature/bonus x desk (1932x940) / mob
(780x1416). The game's background is NOT in the skeleton — slot.js puts the
game's own bg PNG under the canvas (cover).

No designer pack for these screens: the art is the game's own — symbol and
coin statics, the logo, the jackpot ladder plates, and pieces cut out of the
popup atlases (purple velvet frame, counter plate, dark bar, rays, coins,
rubies) — plus texts drawn here with PIL in the game's gold / purple style.
The popup atlases are premultiplied (`pma:true`), so cut regions are
un-premultiplied before use.

Usage:
  python scripts/lucky_joker_3h3_screens.py <fonts_dir> [out_dir]

fonts_dir — luckiest.ttf, baloo.ttf, robotomono.ttf (front/fonts woff2
            converted with fontTools: TTFont(woff2).flavor = None; .save(ttf))
out_dir   — default front/img/lucky-joker-3h3/screens
"""

import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, out_back, out_cubic, pulse, rays, seg, soft_glow, spark, text_img,
    trim, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(ROOT, 'front', 'img', 'lucky-joker-3h3')
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


def art(rel):
    return trim(Image.open(os.path.join(ART_DIR, rel)).convert('RGBA'))


def unpremultiply(im):
    a = np.asarray(im.convert('RGBA')).astype(np.float32)
    al = a[..., 3:4] / 255.0
    a[..., :3] = np.where(al > 0, np.clip(a[..., :3] / np.maximum(al, 1e-3), 0, 255), 0)
    return Image.fromarray(a.astype(np.uint8))


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


def popup_region(popup, name, do_trim=True):
    """One region of a popup export, un-rotated and un-premultiplied. The
    page is always the folder's real animation.png (atlas page names in this
    delivery are not trusted)."""
    folder = os.path.join(ART_DIR, 'popups', popup)
    r = parse_atlas(os.path.join(folder, 'animation.atlas'))[name]
    page = Image.open(os.path.join(folder, 'animation.png')).convert('RGBA')
    x, y, w, h = map(int, r['bounds'].split(','))
    if r.get('rotate') in ('90', 'true'):
        im = page.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
    else:
        im = page.crop((x, y, x + w, y + h))
    im = unpremultiply(im)
    return trim(im) if do_trim else im


def logo_hd():
    """The in-game logo is 324x169 — 2x Lanczos + unsharp for the screens."""
    im = Image.open(os.path.join(ART_DIR, 'game_logo.png')).convert('RGBA')
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2.2, percent=90, threshold=2))
    rgb.putalpha(im.getchannel('A'))
    return trim(rgb)


# The buy-free-spins frame (purple velvet, gold bulb rim, fleur-de-lis crest)
# is 693x651; cards want it taller. Its side bulbs repeat every 40px between
# y=199 and y=480, so the frame is grown by tiling a 40px band out of that run
# instead of stretching the bulbs into ovals.
FRAME_BAND = (261, 301)


def card_frame(extra_bands):
    f = popup_region('buy_free_spins', 'frame', do_trim=False)
    b0, b1 = FRAME_BAND
    band = f.crop((0, b0, f.width, b1))
    out = Image.new('RGBA', (f.width, f.height + extra_bands * (b1 - b0)))
    out.paste(f.crop((0, 0, f.width, b1)), (0, 0))
    for k in range(extra_bands):
        out.paste(band, (0, b1 + k * (b1 - b0)))
    out.paste(f.crop((0, b1, f.width, f.height)), (0, b1 + extra_bands * (b1 - b0)))
    return out


GOLD = [(0, hexc('fff6c8')), (0.45, hexc('ffcf5a')), (1, hexc('e07a10'))]
PURPLE = [(0, hexc('f6d8ff')), (0.45, hexc('c46bff')), (1, hexc('7a1fc2'))]
CREAM = [(0, hexc('ffffff')), (1, hexc('fff0d2'))]
INK = '2a0510'


def title(text, size, fill=GOLD, glow='ff2fa0', stroke='3a0420'):
    return text_img(text, font('luckiest', size), fill, stroke=stroke, stroke_w=max(3, size // 9),
                    glow=glow, glow_r=max(5, size // 6), shadow='12000a')


def lines(rows, size, fill=CREAM, gap=0.06, weight=800):
    """Centered multi-line caption (each row its own stroked line)."""
    ims = [text_img(r, font('baloo', size, weight), fill, stroke=INK, stroke_w=max(3, size // 8),
                    glow=None, shadow='0a0004') for r in rows]
    w = max(i.width for i in ims)
    step = int(size * (1 + gap))
    h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


def coin_with(label):
    """The money coin (coins/empty) with its multiplier printed on it, the
    way the client draws it in game (Roboto Mono, gold over ink)."""
    coin = art('coins/empty/static.png')
    size = int(coin.width * (0.42 if len(label) <= 2 else 0.34))
    t = text_img(label, font('robotomono', size), [(0, hexc('fff4c0')), (1, hexc('ffc23a'))], stroke=INK,
                 stroke_w=max(3, size // 9), glow=None, shadow='1a0005', track=-2)
    out = coin.copy()
    out.alpha_composite(t, ((out.width - t.width) // 2, (out.height - t.height) // 2 + 2))
    return out


def star4(size=96):
    """Four-point twinkle: two crossed streaks + a hot core."""
    s = spark(size, max(6, size // 7))
    im = Image.new('RGBA', (size, size))
    im.alpha_composite(s, (0, (size - s.height) // 2))
    im.alpha_composite(s.rotate(90, expand=True), ((size - s.height) // 2, 0))
    core = soft_glow(size // 2)
    im.alpha_composite(core, (size // 4, size // 4))
    return im


def soft(im, w):
    """Blurry glow art gains nothing from full res — keep it small, stretch on screen."""
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


ART = {
    'logo': logo_hd(),
    'burst': soft(popup_region('win_free_spins', 'rays1'), 640),
    'haze': soft(popup_region('win_free_spins', 'rays2'), 420),
    'plate': popup_region('win_free_spins', 'input'),
    'bar': popup_region('big_win', 'input'),
    'goldcoin': popup_region('free-spins-total-win', 'coin_7'),
    'goldcoin2': popup_region('free-spins-total-win', 'coin_4'),
    'ruby': popup_region('epic_win', 'ruby_1'),
    'club': popup_region('epic_win', 'trefa'),
    'frame_desk': card_frame(3),
    'frame_mob': card_frame(4),
    'glow': soft_glow(256),
    'star': star4(96),
    'rays': rays(560, n=16),
    'scatter': art('scatter/static.png'),
    'wild': art('wild/static.png'),
    'joker': art('coins/joker/static.png'),
    'c_mini': art('coins/mini/static.png'),
    'c_grand': art('coins/grand/static.png'),
    'coin_x2': coin_with('x2'),
    'coin_x3': coin_with('x3'),
    'coin_x5': coin_with('x5'),
    'coin_x10': coin_with('x10'),
}
for tier in ('mini', 'minor', 'major', 'grand'):
    ART[f'jp_{tier}'] = art(f'jackpot_{tier}.png')
ART['logo_flash'] = flash_of(ART['logo'], 0.9)
ART['joker_flash'] = flash_of(ART['joker'], 0.9)
ART['scatter_flash'] = flash_of(ART['scatter'], 0.8)

# Feature cards — copy matches the seed (app/seed/lucky_joker_3h3.py):
# a coin on a winning line multiplies it (several coins add up); the joker
# collector on the middle reel + a coin on each outer reel opens Hold & Win
# (3 respins, reset on any landing, every collector takes the sum of all
# coins); jackpot coins MINI x25 .. GRAND x1000; 3 scatters = 10 free spins,
# all wins x2.
CARDS = [
    ('multi', 'MULTIPLIERS', ['COINS MULTIPLY', 'A WINNING LINE']),
    ('hw', 'HOLD & WIN', ['JOKER COLLECTS', 'EVERY COIN']),
    ('jp', 'JACKPOTS', ['UP TO x1000', 'YOUR BET']),
    ('fs', 'FREE SPINS', ['3 SCATTERS = 10', 'ALL WINS x2']),
]
for key, head, desc in CARDS:
    ART[f't_{key}'] = title(head, 60)
    ART[f'd_{key}'] = lines(desc, 40)
ART['respins'] = title('3 RESPINS', 40, fill=PURPLE, glow='ff2fa0', stroke='22001a')
ART['tap_continue'] = title('TAP TO CONTINUE', 58, fill=CREAM, glow='ff2fa0')
ART['tap_start'] = title('TAP TO START', 64, fill=CREAM, glow='ff2fa0')
ART['t_free_spins'] = title('FREE SPINS', 150)
ART['t_you_won'] = title('YOU HAVE WON', 64, fill=PURPLE, glow='ff2fa0', stroke='22001a')
ART['d_chip_x2'] = lines(['ALL WINS', 'PAY DOUBLE'], 40)
ART['d_chip_fs'] = lines(['3 SCATTERS', 'GIVE +10 SPINS'], 40)


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


def twinkles(sk, parent, spots, seed, start=1.4, tint='fff0c4ff'):
    """Additive 4-point stars blinking out of phase; seamless over IDLE."""
    rnd = random.Random(seed)
    for i, (x, y, s) in enumerate(spots):
        b = sk.bone(f'tw{i}', parent, x, y)
        sk.slot(f'tw{i}', b, 'star', w=96 * s, blend='additive', color=tint)
        ph = rnd.random()
        per = rnd.choice((1.0, 2.0, 4.0))

        def blink(tau, ph=ph, per=per):
            return math.sin(math.pi * (((tau / per) + ph) % 1.0)) ** 4

        env = lambda t: clamp((t - start) / 0.6)  # noqa: E731
        sk.both(b, 'scale', uniform(lambda t, f=blink: 0.25 + 0.75 * f(t - INTRO) * env(t)),
                uniform(lambda t, f=blink: 0.25 + 0.75 * f(t)))
        sk.both(b, 'rotate', lambda t: 90 * (t - INTRO) / IDLE, lambda t: 90 * t / IDLE)
        sk.both(f'tw{i}', 'alpha', lambda t, f=blink: f(t - INTRO) * env(t), lambda t, f=blink: f(t))


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.8, rays_w=None, rays_alpha=0.3):
    """Popup gold burst (breathing) + soft haze + slowly turning rays."""
    rw = rays_w or w * 0.9
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=rw, blend='additive', color='ffc970ff')
    # 16 rays: a 22.5deg turn per loop is seamless
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both(rb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.8, 0.4, 1.0)), uniform(lambda t: 1))
    sk.both(f'{name}_rays', 'alpha', lambda t: rays_alpha * fade(t, t0, 0.6),
            lambda t: rays_alpha * (1 - 0.3 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    hb = sk.bone(f'{name}_haze', parent, x, y)
    sk.slot(f'{name}_haze', hb, 'haze', w=w * 1.1, blend='additive', color='ff7ad8ff')
    sk.both(hb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.9, 0.5, 1.0)), uniform(lambda t: breathe(t, IDLE, 0.06)))
    sk.both(f'{name}_haze', 'alpha', lambda t: 0.45 * fade(t, t0, 0.6), lambda t: 0.45)
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, 'burst', w=w, blend='additive')
    sk.both(b, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.3, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.05)))
    # 2-fold-ish burst: a slow 30deg swing out and back keeps the loop seamless
    sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, 6, IDLE))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.5),
            lambda t: alpha * (1 - 0.18 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))


def floater(sk, name, region, parent, x, y, w, t0, amp=10, period=IDLE, phase=0.0, rot_amp=0.0,
            slide=(0, -40), alpha=1.0, rot0=0.0):
    b = sk.bone(name, parent, x, y, rot=rot0)
    sk.slot(name, b, region, w=w)

    def pos(t, idle_t):
        k = seg(t, t0, t0 + 0.8, 1.0, 0.0)
        return (slide[0] * k, slide[1] * k + bob(idle_t, amp, period, phase))

    move(sk, b, lambda t: pos(t, 0), lambda t: pos(99, t))
    if rot_amp:
        sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, rot_amp, period, phase + 0.25))  # adds to setup rot0
    sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.7, 0.5)), uniform(lambda t: 1))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.4), lambda t: alpha)
    return b


def tap_hint(sk, region, y, w):
    b = sk.bone('tap', 'root', 0, y)
    sk.slot('tap', b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: seg(t, 2.2, 2.7, 0.8, 1.0, out_back)), uniform(lambda t: breathe(t, 2.0, 0.04)))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.5),
            lambda t: 0.775 + 0.225 * math.cos(2 * math.pi * t / 2.0))


def icon(sk, name, parent, region, x, y, w, t0, idle_scale=None, idle_rot=None, idle_move=None, drop=0.0):
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(idle_scale or (lambda t: 1)))
    if idle_rot:
        sk.both(b, 'rotate', lambda t: 0, idle_rot)
    if idle_move or drop:
        move(sk, b, lambda t: (0, seg(t, t0, t0 + 0.45, drop, 0, out_back)), idle_move or (lambda t: (0, 0)))
    return b


# --------------------------------------------------------------------------
# feature (preview) screen

# Height of each card illustration at s=1; the icon group is scaled down to
# whatever room the title and caption leave on the card.
ICON_H = {'multi': 150, 'hw': 184, 'jp': 170, 'fs': 190}

def card_icons(sk, key, parent, t0, s):
    """Card illustration centred on `parent`; s = icon scale (ICON_H = its height at s=1)."""
    if key == 'multi':
        for i, (code, x, y, sz) in enumerate((('coin_x2', -112, -14, 104), ('coin_x5', 0, 18, 130),
                                              ('coin_x10', 112, -14, 104))):
            icon(sk, f'{key}_i{i}', parent, code, x * s, y * s, sz * s, t0 + 0.1 * i, drop=80 * s,
                 idle_scale=lambda t, i=i: 1 + 0.1 * pulse(t, 2.0, i * 0.15, 6),
                 idle_move=lambda t, i=i: (0, bob(t, 6 * s, 2.0, i * 0.33)))
    elif key == 'hw':
        g = sk.bone(f'{key}_glow', parent, 0, 26 * s)
        sk.slot(f'{key}_glow', g, 'glow', w=250 * s, blend='additive', color='ffb347ff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.15)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.6 * fade(t, t0), lambda t: 0.6 - 0.25 * pulse(t, 2.0, 0.0, 2))
        for i, (code, x, sz) in enumerate((('coin_x3', -112, 100), ('coin_x5', 112, 100))):
            icon(sk, f'{key}_c{i}', parent, code, x * s, 26 * s, sz * s, t0 + 0.12 * i,
                 idle_move=lambda t, i=i: (0, bob(t, 5 * s, 2.0, 0.5 * i)))
        b = icon(sk, f'{key}_j', parent, 'joker', 0, 26 * s, 132 * s, t0 + 0.3,
                 idle_scale=lambda t: 1 + 0.08 * pulse(t, 2.0, 0.0, 6),
                 idle_rot=lambda t: bob(t, 5, 2.0))
        fl = sk.slot(f'{key}_jfl', b, 'joker_flash', w=132 * s, blend='additive')
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.6, t0 + 1.0, 0.8, 0.0) if t > t0 + 0.6 else 0,
                lambda t: 0.45 * pulse(t, 2.0, 0.0, 8))
        r = sk.bone(f'{key}_r', parent, 0, -72 * s)
        sk.slot(f'{key}_r', r, 'respins', w=210 * s)
        sk.both(r, 'scale', uniform(lambda t: pop(t, t0 + 0.5, 0.5, 0.2)), uniform(lambda t: breathe(t, 2.0, 0.04)))
        sk.both(f'{key}_r', 'alpha', lambda t: fade(t, t0 + 0.5), lambda t: 1)
    elif key == 'jp':
        plates = (('jp_grand', -92, 40, 172), ('jp_major', 92, 40, 172), ('jp_minor', -92, -40, 172),
                  ('jp_mini', 92, -40, 172))
        for i, (code, x, y, sz) in enumerate(plates):
            icon(sk, f'{key}_p{i}', parent, code, x * s, y * s, sz * s, t0 + 0.1 * i,
                 idle_scale=lambda t, i=i: 1 + 0.07 * pulse(t, 4.0, i * 0.25, 8))
    elif key == 'fs':
        g = sk.bone(f'{key}_glow', parent, 0, 0)
        sk.slot(f'{key}_glow', g, 'glow', w=260 * s, blend='additive', color='ff5ad2ff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.15)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.55 * fade(t, t0), lambda t: 0.55)
        b = sk.bone(f'{key}_i0', parent)
        sk.slot(f'{key}_i0', b, 'scatter', w=185 * s)
        fl = sk.slot(f'{key}_fl', b, 'scatter_flash', w=185 * s, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)), uniform(lambda t: 1))
        move(sk, b, lambda t: (0, 0), lambda t: (0, bob(t, 8 * s, 2.0)))
        sk.both(fl, 'alpha', lambda t: 0, lambda t: 0.5 * pulse(t, 4.0, 0.5, 8))


def feature_card(sk, idx, key, x, y, frame, cw, t0, s, tscale):
    fim = ART[frame]
    ch = cw * fim.height / fim.width
    k = cw / fim.width  # frame px -> units
    c = sk.bone(f'card{idx}', 'root', x, y)
    sk.slot(f'card{idx}', c, frame, w=cw)
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -70, 0)), lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    max_w = 560 * k
    ti, di = ART[f't_{key}'], ART[f'd_{key}']
    t_w = min(ti.width * tscale, max_w)
    d_w = min(di.width * tscale * 0.95, max_w)
    t_h = t_w * ti.height / ti.width
    d_h = d_w * di.height / di.width
    t_y = ch / 2 - 145 * k - t_h / 2
    d_y = -ch / 2 + 140 * k + d_h / 2
    tb = sk.bone(f'card{idx}_t', c, 0, t_y)
    sk.slot(f'card{idx}_t', tb, f't_{key}', w=t_w)
    sk.both(f'card{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.15), lambda t: 1)

    gap_top = t_y - t_h / 2
    gap_bot = d_y + d_h / 2
    fit = min(1.0, (gap_top - gap_bot - 14) / (ICON_H[key] * s))
    ib = sk.bone(f'card{idx}_icon', c, 0, (gap_top + gap_bot) / 2, sx=round(fit, 4), sy=round(fit, 4))
    card_icons(sk, key, ib, t0 + 0.25, s)

    db = sk.bone(f'card{idx}_d', c, 0, d_y)
    sk.slot(f'card{idx}_d', db, f'd_{key}', w=d_w)
    sk.both(f'card{idx}_d', 'alpha', lambda t: fade(t, t0 + 0.3), lambda t: 1)


def build_feature(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'feature_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    frame = 'frame_desk' if variant == 'desk' else 'frame_mob'
    add_art(sk, 'logo', 'logo_flash', 'burst', 'haze', 'rays', 'glow', 'star', 'goldcoin', 'goldcoin2', 'ruby',
            'club', 'tap_continue', frame, 'coin_x2', 'coin_x3', 'coin_x5', 'coin_x10', 'joker', 'joker_flash',
            'respins', 'jp_mini', 'jp_minor', 'jp_major', 'jp_grand', 'scatter', 'scatter_flash',
            *[f't_{k}' for k, _, _ in CARDS], *[f'd_{k}' for k, _, _ in CARDS])

    if variant == 'desk':
        logo_y, logo_w = 335, 400
        cw = 440
        cards = [(-705 + 470 * i, -70) for i in range(4)]
        s, tscale = 1.0, 0.8
        tap_y, tap_w = -405, 430
        deco = [('goldcoin', 830, 330, 120, 0.1, -12), ('ruby', -840, 350, 64, 0.6, 0),
                ('goldcoin2', -620, 400, 84, 0.35, 10), ('club', 640, 420, 46, 0.8, 0)]
        spots = [(-420, 380, 0.8), (420, 400, 1.0), (-900, 300, 0.7), (900, 380, 0.6), (-250, 240, 0.5),
                 (260, 250, 0.6), (-930, -80, 0.6), (935, -140, 0.7), (0, -440, 0.5)]
    else:
        logo_y, logo_w = 565, 400
        cw = 362
        cards = [(-187, 210), (187, 210), (-187, -233), (187, -233)]
        s, tscale = 0.8, 0.66
        tap_y, tap_w = -570, 420
        deco = [('goldcoin', 315, 620, 90, 0.1, -12), ('ruby', -330, 640, 54, 0.6, 0),
                ('club', 300, 470, 40, 0.3, 0)]
        spots = [(-250, 670, 0.7), (230, 470, 0.8), (-330, 470, 0.5), (360, -10, 0.6), (-360, -470, 0.6),
                 (300, -640, 0.5), (0, 690, 0.5)]

    light_burst(sk, 'burst', 'root', 0, logo_y - 10, logo_w * 1.9, t0=0.0, alpha=0.7, rays_w=logo_w * 2.3)
    for i, (region, x, y, dw, ph_, r0) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=12, phase=ph_, rot_amp=6, rot0=r0)

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
        feature_card(sk, i, key, x, y, frame, cw, 0.75 + 0.18 * i, s, tscale)

    twinkles(sk, 'root', spots, seed=7)
    tap_hint(sk, 'tap_continue', tap_y, tap_w)
    sk.write()


# --------------------------------------------------------------------------
# bonus screen

# Counter plate (win_free_spins/input): its purple window sits below the gem
# crest — the window's centre is 61% down the trimmed region.
PLATE_WINDOW_Y = 0.61


def info_chip(sk, idx, icon_region, text, x, y, cw, t0, from_x, icon_w, ribbon=True, tscale=0.85):
    """Compact "icon + caption" group, optionally on its own dark bar of width cw."""
    c = sk.bone(f'chip{idx}', 'root', x, y)
    if ribbon:
        sk.slot(f'chip{idx}', c, 'bar', w=cw, h=cw * 0.2)
        sk.both(f'chip{idx}', 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1)
    move(sk, c, lambda t: (seg(t, t0, t0 + 0.6, from_x, 0), 0), lambda t: (0, bob(t, 4, IDLE, idx * 0.5)))
    tw_ = min(ART[text].width * tscale, cw - icon_w - 90)
    gap = 26
    total = icon_w + gap + tw_
    ib = sk.bone(f'chip{idx}_i', c, -total / 2 + icon_w / 2, 2)
    sk.slot(f'chip{idx}_i', ib, icon_region, w=icon_w)
    sk.both(ib, 'scale', uniform(lambda t: pop(t, t0 + 0.3, 0.5, 0.0)),
            uniform(lambda t: 1 + 0.1 * pulse(t, 2.0, idx * 0.25, 6)))
    sk.both(ib, 'rotate', lambda t: 0, lambda t: bob(t, 8, 2.0, idx * 0.5))
    tb = sk.bone(f'chip{idx}_t', c, total / 2 - tw_ / 2, 0)
    sk.slot(f'chip{idx}_t', tb, text, w=tw_)
    sk.both(f'chip{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.25, 0.4), lambda t: 1)


def build_bonus(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'bonus_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'burst', 'haze', 'rays', 'glow', 'star', 'plate', 'bar', 'goldcoin', 'goldcoin2', 'ruby', 'club',
            'scatter', 'scatter_flash', 'wild', 'coin_x2', 't_free_spins', 't_you_won', 'd_chip_x2', 'd_chip_fs',
            'tap_start')

    if variant == 'desk':
        won_y, title_y, title_w = 375, 240, 820
        plate_y, plate_w = 20, 400
        chips = [(-380, -230, 700, -300), (380, -230, 700, 300)]
        band = (0, -230, 1560, 150)
        chip_icon = 116
        tap_y, tap_w = -395, 420
        heroes = [('scatter', -560, 40, 250, 0.0), ('wild', 560, 40, 250, 0.5)]
        deco = [('goldcoin', 820, 300, 130, 0.1, -12), ('goldcoin2', -820, 300, 100, 0.6, 14),
                ('ruby', 760, -60, 60, 0.3, 0), ('ruby', -770, -80, 52, 0.8, 0), ('club', -680, 330, 48, 0.45, 0)]
        spots = [(-470, 330, 0.8), (480, 340, 0.9), (-880, -280, 0.7), (870, -260, 0.6), (-230, 100, 0.5),
                 (240, -70, 0.5), (0, 445, 0.5)]
        tscale = 0.85
    else:
        won_y, title_y, title_w = 610, 485, 690
        plate_y, plate_w = 205, 390
        chips = [(0, -205, 700, -420), (0, -370, 700, 420)]
        band = None
        chip_icon = 108
        tap_y, tap_w = -580, 420
        heroes = [('scatter', -230, 0, 190, 0.0), ('wild', 230, 0, 190, 0.5)]
        deco = [('goldcoin', 300, 650, 90, 0.1, -12), ('ruby', -320, 640, 50, 0.6, 0),
                ('goldcoin2', -320, 330, 70, 0.3, 14), ('club', 330, 340, 40, 0.8, 0)]
        spots = [(-300, 560, 0.6), (300, 520, 0.7), (-340, 100, 0.5), (340, 60, 0.6), (-300, -520, 0.5),
                 (300, -660, 0.5)]
        tscale = 0.82

    light_burst(sk, 'burst', 'root', 0, plate_y + 30, plate_w * 2.6, t0=0.6, alpha=0.65, rays_w=plate_w * 3.2,
                rays_alpha=0.28)

    for i, (region, x, y, dw, ph_) in enumerate(heroes):
        b = floater(sk, f'hero{i}', region, 'root', x, y, dw, 0.9 + 0.15 * i, amp=12, phase=ph_, rot_amp=4,
                    slide=(-x * 0.4, 0))
        if region == 'scatter':
            fl = sk.slot(f'hero{i}_fl', b, 'scatter_flash', w=dw, blend='additive')
            sk.both(fl, 'alpha', lambda t: 0, lambda t: 0.45 * pulse(t, 4.0, 0.25, 8))
    for i, (region, x, y, dw, ph_, r0) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=12, phase=ph_, rot_amp=7, rot0=r0)

    # "YOU HAVE WON" drops in, "FREE SPINS" slams down with a flash
    yb = sk.bone('won', 'root', 0, won_y)
    sk.slot('won', yb, 't_you_won', w=title_w * 0.5)
    move(sk, yb, lambda t: (0, seg(t, 0.2, 0.7, 50, 0)), lambda t: (0, 0))
    sk.both('won', 'alpha', lambda t: fade(t, 0.2, 0.4), lambda t: 1)

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

    # soft glow UNDER the plate (additive on top would wash the plate out)
    rg = sk.bone('plate_glow', 'root', 0, plate_y)
    sk.slot('plate_glow', rg, 'glow', w=plate_w * 1.7, blend='additive', color='ff5ad2ff')
    sk.both(rg, 'scale', uniform(lambda t: seg(t, 1.0, 1.6, 0.2, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.1)))
    sk.both('plate_glow', 'alpha', lambda t: seg(t, 1.0, 1.4, 0.0, 1.0) * (1 - 0.5 * fade(t, 1.4, 0.8)),
            lambda t: 0.5)

    # counter plate (the live spin count is a DOM overlay glued to bone "count")
    pim = ART['plate']
    ph_units = plate_w * pim.height / pim.width
    pb = sk.bone('plate', 'root', 0, plate_y)
    sk.slot('plate', pb, 'plate', w=plate_w)
    sk.bone('count', pb, 0, (0.5 - PLATE_WINDOW_Y) * ph_units)
    sk.both(pb, 'scale', uniform(lambda t: pop(t, 1.0, 0.6, 0.0)),
            uniform(lambda t: 1 + 0.05 * pulse(t, 2.0, 0.0, 6)))
    sk.both('plate', 'alpha', lambda t: fade(t, 1.0, 0.2), lambda t: 1)

    if band:
        bx, by, bw, bh = band
        rb = sk.bone('band', 'root', bx, by)
        sk.slot('band', rb, 'bar', w=bw, h=bh)
        sk.both(rb, 'scale', lambda t: (seg(t, 1.5, 2.0, 0.2, 1.0), 1), uniform(lambda t: 1))
        sk.both('band', 'alpha', lambda t: fade(t, 1.5, 0.4), lambda t: 1)
    (x0, y0, cw0, f0), (x1, y1, cw1, f1) = chips
    info_chip(sk, 0, 'coin_x2', 'd_chip_x2', x0, y0, cw0, 1.6, f0, chip_icon, ribbon=not band, tscale=tscale)
    info_chip(sk, 1, 'scatter', 'd_chip_fs', x1, y1, cw1, 1.75, f1, chip_icon, ribbon=not band, tscale=tscale)

    twinkles(sk, 'root', spots, seed=11)
    tap_hint(sk, 'tap_start', tap_y, tap_w)
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
