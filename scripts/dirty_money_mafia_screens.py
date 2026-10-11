"""Dirty Money / MAFIA ("Empire of Crime") — feature (preview) screen + bonus
screen as Spine 4.1 skeletons.

Same contract as scripts/sugar_galaxy_screens.py / wild_western_story_screens.py:
a full-screen skeleton authored on the game's design canvas (origin = canvas
centre, 1 unit = 1 design px, y up), `intro` (3s) -> `idle` (4s seamless loop,
first idle frame == last intro frame). Four variants: feature/bonus x desk
(1932x940) / mob (780x1416). The game's background is NOT in the skeleton —
slot.js puts the game's own bg PNG under the canvas (cover).

No designer pack for these screens: the art is the game's own — symbol statics,
the expanded-wild region of the wild atlas (its page is wild/wild.png, not
animation.png), the logo, the reel frame (9-sliced into card panels), the
Wheel of Fortune drum/frame/pointer, the buy-bonus suitcase, and pieces cut out
of the popup atlases (light burst, red casino chip, plaque, suitcase, vault,
coins) — plus texts drawn here with PIL in the popups' gold-on-burgundy style.

Usage:
  python scripts/dirty_money_mafia_screens.py <fonts_dir> [out_dir]

fonts_dir — cinzel.ttf, baloo.ttf (front/fonts woff2 converted with
            fontTools: TTFont(woff2).flavor = None; .save(ttf))
out_dir   — default front/img/dirty-money-mafia/screens
"""

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, out_back, out_cubic, pulse, rays, seg, soft_glow, spark,
    text_img, trim, vgrad, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(ROOT, 'front', 'img', 'dirty-money-mafia')
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
    return Image.open(os.path.join(ART_DIR, rel)).convert('RGBA')


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


def atlas_region(folder, name, page_png='animation.png'):
    """One region of an export, un-rotated. `page_png` is the REAL texture —
    some exports' .atlas names a different file than the one that ships."""
    folder = os.path.join(ART_DIR, folder)
    r = parse_atlas(os.path.join(folder, 'animation.atlas'))[name]
    page = Image.open(os.path.join(folder, page_png)).convert('RGBA')
    x, y, w, h = map(int, r['bounds'].split(','))
    if r.get('rotate') in ('90', 'true'):
        im = page.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
    else:
        im = page.crop((x, y, x + w, y + h))
    return trim(im)


def popup_region(popup, name):
    return atlas_region(os.path.join('popups', popup), name)


def hd(im, k=2):
    """Lanczos upscale + unsharp for art that ships smaller than its screen use."""
    im = im.resize((im.width * k, im.height * k), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2.0, percent=80, threshold=2))
    rgb.putalpha(im.getchannel('A'))
    return rgb


def soft(im, w):
    """Blurry glow art gains nothing from full res — keep it small, stretch on screen."""
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


GOLD = [(0, hexc('fff6c6')), (0.4, hexc('ffd447')), (0.72, hexc('e8921c')), (1, hexc('a14c0c'))]
CREAM = [(0, hexc('fffaf0')), (1, hexc('f1d7a2'))]
STROKE = '2c0a07'


def title(text, size, fill=GOLD, glow='c2240f'):
    return text_img(text, font('cinzel', size, 900), fill, stroke=STROKE, stroke_w=max(3, size // 10),
                    glow=glow, glow_r=max(5, size // 6), shadow='0c0202')


def stack(ims, step):
    w = max(i.width for i in ims)
    h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


def title_lines(rows, size, **kw):
    return stack([title(r, size, **kw) for r in rows], int(size * 1.0))


def caption(rows, size, fill=CREAM):
    ims = [text_img(r, font('baloo', size, 800), fill, stroke='22060a', stroke_w=max(3, size // 8),
                    glow=None, shadow='0a0203') for r in rows]
    return stack(ims, int(size * 1.08))


def frame_panel(w, h, s=0.5):
    """Card in the reel frame's gold: Frame.png 9-sliced to w x h (incl. the
    side-arrow / bottom-diamond ornaments) over a burgundy velvet fill."""
    src = art('Frame.png')
    SW, SH = src.size
    src = src.resize((round(SW * s), round(SH * s)), Image.LANCZOS)
    sw, sh = src.size
    L, R, T, B = round(170 * s), round(170 * s), round(164 * s), round(141 * s)
    out = Image.new('RGBA', (w, h))
    # fill: under the border's centre line
    x0, y0 = round(62 * s), round(56 * s)
    x1, y1 = w - round(62 * s), h - round(32 * s)
    fill = vgrad((w, h), [(0, hexc('4e1419', 242)), (0.5, hexc('2e0b10', 244)), (1, hexc('16060a', 246))])
    spot = Image.radial_gradient('L').resize((w, h)).point(lambda v: int(70 * clamp(1 - v / 200) ** 1.4))
    fill.paste(Image.new('RGBA', (w, h), (255, 150, 70, 255)), (0, 0), spot)
    m = Image.new('L', (w, h))
    ImageDraw.Draw(m).rectangle([x0, y0, x1, y1], fill=255)
    out.paste(fill, (0, 0), m)

    def piece(box, size):
        p = src.crop(box)
        return p.resize(size, Image.LANCZOS) if p.size != size else p

    cw, ch = w - L - R, h - T - B
    lay = Image.new('RGBA', (w, h))
    ex0, ex1 = round(180 * s), round(420 * s)  # plain stretch of the long edges
    ey0, ey1 = round(180 * s), round(300 * s)
    lay.alpha_composite(piece((ex0, 0, ex1, T), (cw, T)), (L, 0))
    lay.alpha_composite(piece((ex0, sh - B, ex1, sh), (cw, B)), (L, h - B))
    lay.alpha_composite(piece((0, ey0, L, ey1), (L, ch)), (0, T))
    lay.alpha_composite(piece((sw - R, ey0, sw, ey1), (R, ch)), (w - R, T))
    lay.alpha_composite(piece((0, 0, L, T), (L, T)), (0, 0))
    lay.alpha_composite(piece((sw - R, 0, sw, T), (R, T)), (w - R, 0))
    lay.alpha_composite(piece((0, sh - B, L, sh), (L, B)), (0, h - B))
    lay.alpha_composite(piece((sw - R, sh - B, sw, sh), (R, B)), (w - R, h - B))
    # mid ornaments
    my, mh = round(379 * s), round(70 * s)
    if ch > 2 * mh + 10:
        lay.alpha_composite(piece((0, my - mh, L, my + mh), (L, 2 * mh)), (0, h // 2 - mh))
        lay.alpha_composite(piece((sw - R, my - mh, sw, my + mh), (R, 2 * mh)), (w - R, h // 2 - mh))
    mx, mw = round(581 * s), round(90 * s)
    if cw > 2 * mw + 10:
        lay.alpha_composite(piece((mx - mw, sh - B, mx + mw, sh), (2 * mw, B)), (w // 2 - mw, h - B))
    out.alpha_composite(lay)
    return out


def plaque(w, h):
    """Long burgundy plaque (buy-free-spins dialog's input bar), 3-sliced."""
    src = popup_region('buy_free_spins', 'MAFIA_BFS_input')
    k = h / src.height
    src = src.resize((round(src.width * k), h), Image.LANCZOS)
    cap = round(70 * k)
    mid = src.crop((round(120 * k), 0, round(240 * k), h)).resize((w - 2 * cap, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h))
    out.alpha_composite(mid, (cap, 0))
    out.alpha_composite(src.crop((0, 0, cap, h)), (0, 0))
    out.alpha_composite(src.crop((src.width - cap, 0, src.width, h)), (w - cap, 0))
    return out


def star4(size=96):
    s = spark(size, max(6, size // 7))
    im = Image.new('RGBA', (size, size))
    im.alpha_composite(s, (0, (size - s.height) // 2))
    im.alpha_composite(s.rotate(90, expand=True), ((size - s.height) // 2, 0))
    im.alpha_composite(soft_glow(size // 2), (size // 4, size // 4))
    return im


def open_safe():
    """Open safe stuffed with cash, from the scatter export's own pieces."""
    body = atlas_region('scatter', 'scatter_seif')
    money = atlas_region('scatter', 'scatter_seif_money')
    out = body.copy()
    out.alpha_composite(money, ((body.width - money.width) // 2 - 4, body.height - money.height - 14))
    return out


def wheel_drum():
    """WOF drum + frame composited (frame is static, drum spins as its own slot)."""
    return trim(art('popups/WOF/WOF_baraban.png')), trim(art('popups/WOF/WOF_frame.png'))


drum, wheel_frame = wheel_drum()
ART = {
    'logo': trim(hd(art('Logo.png'))),
    'burst': soft(popup_region('big_win', 'MAFIA_BW_rays1'), 720),
    'light': soft(popup_region('buy_free_spins', 'MAFIA_BFS_Light'), 600),
    'money': popup_region('big_win', 'MAFIA_BW_bg-money'),
    'case': popup_region('buy_free_spins', 'MAFIA_BFS_case'),
    'vault': popup_region('free_spins_total_win', 'MAFIA_BSTW_bg'),
    'chip': popup_region('free_spins_win', 'MAFIA_BSW_Counter_FS'),
    'coin1': popup_region('mega_win', 'MAFIA_MW_m1'),
    'coin2': popup_region('mega_win', 'MAFIA_MW_m3'),
    'big_wild': atlas_region('wild', 'wild-win-big_0', page_png='wild.png'),
    'wild': trim(art('wild/static-small.png')),
    'scatter': trim(art('scatter/static.png')),
    'safe': open_safe(),  # the scatter's own open-safe pieces, no SCATTER label
    'wof': trim(art('WOF/static.png')),
    'rare_red': trim(art('rare_red/static.png')),
    'rare_green': trim(art('rare_green/static.png')),
    'buy': trim(art('buy_bonus_button.png')),
    'drum': drum,
    'wheel_frame': wheel_frame,
    'pointer': trim(art('popups/WOF/WOF_strelka.png')),
    'glow': soft_glow(256),
    'star': star4(96),
    'rays': rays(560, n=16, col=(255, 214, 140)),
}
ART['logo_flash'] = flash_of(ART['logo'], 0.9)
ART['big_wild_flash'] = flash_of(ART['big_wild'], 0.9)
ART['scatter_flash'] = flash_of(ART['scatter'], 0.8)
ART['buy_flash'] = flash_of(ART['buy'], 0.7)
ART['chip_flash'] = flash_of(ART['chip'], 0.8)

# Feature cards — copy matches the seed (app/seed/dirty_money_mafia.py):
# expanding_wild fills its reel; 3/4/5 scatters = 10/15/20 free spins;
# 3 WOF symbols open the wheel (x2..x8 or the free-spins round);
# bonus_buy free_spins_buy costs 100x bet.
CARDS = [
    ('wild', ['EXPANDING', 'WILD'], ['WILD GROWS TO', 'FILL THE REEL']),
    ('fs', ['FREE', 'SPINS'], ['3 / 4 / 5 SCATTERS', '= 10 / 15 / 20 SPINS']),
    ('wheel', ['WHEEL OF', 'FORTUNE'], ['3 WHEEL SYMBOLS:', 'x2 - x8 OR FREE SPINS']),
    ('buy', ['BUY', 'BONUS'], ['FREE SPINS ROUND', 'FOR 100x BET']),
]
for key, head, desc in CARDS:
    ART[f't_{key}'] = title_lines(head, 50)
    ART[f'd_{key}'] = caption(desc, 34)
ART['tap_continue'] = title('TAP TO CONTINUE', 54, fill=CREAM, glow='ff7a1a')
ART['tap_start'] = title('TAP TO START', 60, fill=CREAM, glow='ff7a1a')
ART['t_free_spins'] = title('FREE SPINS', 140)
ART['t_you_won'] = title('YOU HAVE WON', 56, fill=CREAM, glow='c2240f')
ART['d_chip_wild'] = caption(['WILDS EXPAND', 'ON ANY REEL'], 36)
ART['d_chip_fs'] = caption(['3+ SCATTERS', 'ADD MORE SPINS'], 36)
ART['panel_desk'] = frame_panel(404, 470)
ART['panel_mob'] = frame_panel(356, 450)
ART['plaque_desk'] = plaque(660, 132)
ART['plaque_mob'] = plaque(680, 132)


# --------------------------------------------------------------------------
# motion helpers (all idle offsets are 0 at t=0 so idle starts where intro ends)

def bob(t, amp, period=IDLE, phase=0.0):
    return amp * (wave(t, period, phase) - wave(0, period, phase))


def pop(t, t0, dur=0.55, s0=0.3):
    return seg(t, t0, t0 + dur, s0, 1.0, out_back)


def fade(t, t0, dur=0.3):
    return seg(t, t0, t0 + dur, 0.0, 1.0, out_cubic)


def move(sk, bone, intro_fn, idle_fn):
    """Translate written as an offset from the bone's setup position."""
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


def twinkles(sk, parent, spots, seed, start=1.4, tint='ffe2a8ff'):
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


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.85, rays_w=None, rays_alpha=0.3):
    """Gold popup burst (breathing) + slowly turning rays behind it."""
    rw = rays_w or w * 0.8
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=rw, blend='additive', color='ffd08aff')
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both(rb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.8, 0.4, 1.0)), uniform(lambda t: 1))
    sk.both(f'{name}_rays', 'alpha', lambda t: rays_alpha * fade(t, t0, 0.6),
            lambda t: rays_alpha * (1 - 0.3 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, 'burst', w=w, blend='additive')
    sk.both(b, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.3, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.05)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.5),
            lambda t: alpha * (1 - 0.2 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))


def floater(sk, name, region, parent, x, y, w, t0, amp=10, period=IDLE, phase=0.0, rot_amp=0.0,
            slide=(0, -40), alpha=1.0, rot=0):
    b = sk.bone(name, parent, x, y, rot=rot)
    sk.slot(name, b, region, w=w)

    def pos(t, idle_t):
        k = seg(t, t0, t0 + 0.8, 1.0, 0.0)
        return (slide[0] * k, slide[1] * k + bob(idle_t, amp, period, phase))

    move(sk, b, lambda t: pos(t, 0), lambda t: pos(99, t))
    if rot_amp:
        sk.both(b, 'rotate', lambda t: rot, lambda t: rot + bob(t, rot_amp, period, phase + 0.25))
    sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.7, 0.5)), uniform(lambda t: 1))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.4), lambda t: alpha)
    return b


def tap_hint(sk, region, y, w):
    b = sk.bone('tap', 'root', 0, y)
    sk.slot('tap', b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: seg(t, 2.2, 2.7, 0.8, 1.0, out_back)), uniform(lambda t: breathe(t, 2.0, 0.04)))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.5),
            lambda t: 0.775 + 0.225 * math.cos(2 * math.pi * t / 2.0))


def glow_under(sk, name, parent, w, t0, tint, alpha=0.6, y=0):
    g = sk.bone(name, parent, 0, y)
    sk.slot(name, g, 'glow', w=w, blend='additive', color=tint)
    sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.12)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0), lambda t: alpha)


# --------------------------------------------------------------------------
# feature (preview) screen

def card_icons(sk, key, parent, t0, s, room):
    """Card illustration centred on `parent`; s = scale, room = available height."""
    if key == 'wild':
        h = min(room, 236 * s)
        glow_under(sk, 'wild_glow', parent, 300 * s, t0, 'ffb04aff', 0.55)
        for i, (code, x) in enumerate((('rare_red', -96), ('rare_green', 96))):
            b = sk.bone(f'wild_s{i}', parent, x * s, -h * 0.17)
            sk.slot(f'wild_s{i}', b, code, w=74 * s)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.05 * i: pop(t, d, 0.45, 0.0)), uniform(lambda t: 1))
        b = sk.bone('wild_i0', parent)
        sk.slot('wild_i0', b, 'big_wild', h=h)
        fl = sk.slot('wild_fl', b, 'big_wild_flash', h=h, blend='additive')
        # expanding: grows from a symbol-sized tile to the full reel height
        sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.4, 0.0, 1.0, out_cubic),
                                       seg(t, t0, t0 + 0.4, 0.0, 0.34, out_cubic) if t < t0 + 0.55
                                       else seg(t, t0 + 0.55, t0 + 0.95, 0.34, 1.0, out_back)),
                uniform(lambda t: 1 + 0.03 * pulse(t, 2.0, 0.0, 4)))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.95, t0 + 1.4, 0.8, 0.0) if t > t0 + 0.95 else 0,
                lambda t: 0.4 * pulse(t, 4.0, 0.5, 8))
    elif key == 'fs':
        glow_under(sk, 'fs_glow', parent, 320 * s, t0, 'ffc25aff', 0.5)
        # side safes are the bare safe (their SCATTER labels would collide with the centre one's)
        for i, (x, y, w, ph, reg) in enumerate(((-100, 6, 104, 0.0, 'safe'), (100, 6, 104, 0.5, 'safe'),
                                                 (0, -4, 156, 0.25, 'scatter'))):
            b = sk.bone(f'fs_i{i}', parent, x * s, y * s)
            sk.slot(f'fs_i{i}', b, reg, w=w * s)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.12 * i: pop(t, d, 0.5, 0.0)),
                    uniform(lambda t, i=i: 1 + 0.08 * pulse(t, 2.0, i * 0.33, 6)))
            move(sk, b, lambda t, d=t0 + 0.12 * i: (0, seg(t, d, d + 0.45, 80 * s, 0, out_back)),
                 lambda t, ph=ph: (0, bob(t, 6 * s, 2.0, ph)))
        fl = sk.slot('fs_fl', 'fs_i2', 'scatter_flash', w=156 * s, blend='additive')
        sk.both(fl, 'alpha', lambda t: 0, lambda t: 0.5 * pulse(t, 4.0, 0.6, 8))
    elif key == 'wheel':
        d = min(room, 214 * s)
        glow_under(sk, 'wh_glow', parent, d * 1.5, t0, 'ffb04aff', 0.5)
        b = sk.bone('wh', parent)
        drum_w = d * ART['drum'].width / ART['wheel_frame'].width
        dr = sk.bone('wh_drum', b)
        sk.slot('wh_drum', dr, 'drum', w=drum_w * 0.97)
        sk.slot('wh_frame', b, 'wheel_frame', w=d)
        hub = sk.bone('wh_hub', b)
        sk.slot('wh_hub', hub, 'wof', w=d * 0.36)
        sk.both(hub, 'scale', uniform(lambda t: pop(t, t0 + 0.5, 0.5, 0.0)),
                uniform(lambda t: 1 + 0.06 * pulse(t, 2.0, 0.25, 6)))
        p = sk.bone('wh_ptr', b, d * 0.5, 0)
        sk.slot('wh_ptr', p, 'pointer', h=d * 0.26)
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)), uniform(lambda t: 1))
        # spin-up in the intro, eases onto a slot; idle = one 45deg slot per loop
        sk.both(dr, 'rotate', lambda t: seg(t, t0, INTRO, 720 + 45, 0, out_cubic),
                lambda t: -45 * t / IDLE)
        sk.both(p, 'rotate', lambda t: 0, lambda t: 6 * pulse(t, 0.5, 0.0, 6))
    elif key == 'buy':
        w = min(room * 1.0, 222 * s)
        glow_under(sk, 'buy_glow', parent, w * 1.5, t0, 'ffb04aff', 0.55)
        b = sk.bone('buy_i0', parent)
        sk.slot('buy_i0', b, 'buy', w=w)
        fl = sk.slot('buy_fl', b, 'buy_flash', w=w, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)),
                uniform(lambda t: 1 + 0.05 * pulse(t, 2.0, 0.0, 4)))
        sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, 3, IDLE))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.4, t0 + 0.8, 0.7, 0.0) if t > t0 + 0.4 else 0,
                lambda t: 0.35 * pulse(t, 2.0, 0.0, 6))


def feature_card(sk, idx, key, x, y, panel, pw, ph, t0, s):
    c = sk.bone(f'card{idx}', 'root', x, y)
    sk.slot(f'card{idx}', c, panel, w=pw)
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -70, 0)), lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    ti, di = ART[f't_{key}'], ART[f'd_{key}']
    t_w = min(ti.width * 0.8 * s, pw - 70)
    d_w = min(di.width * 0.8 * s, pw - 60)
    t_h = t_w * ti.height / ti.width
    d_h = d_w * di.height / di.width
    t_y = ph * 0.5 - 34 * s - t_h / 2
    d_y = -ph * 0.5 + 40 * s + d_h / 2
    tb = sk.bone(f'card{idx}_t', c, 0, t_y)
    sk.slot(f'card{idx}_t', tb, f't_{key}', w=t_w)
    sk.both(f'card{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.15), lambda t: 1)

    gap_top = t_y - t_h / 2
    gap_bot = d_y + d_h / 2
    ib = sk.bone(f'card{idx}_icon', c, 0, (gap_top + gap_bot) / 2)
    card_icons(sk, key, ib, t0 + 0.25, s, gap_top - gap_bot - 16)

    db = sk.bone(f'card{idx}_d', c, 0, d_y)
    sk.slot(f'card{idx}_d', db, f'd_{key}', w=d_w)
    sk.both(f'card{idx}_d', 'alpha', lambda t: fade(t, t0 + 0.3), lambda t: 1)


def build_feature(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'feature_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'star', 'money', 'coin1', 'coin2', 'tap_continue',
            'big_wild', 'big_wild_flash', 'rare_red', 'rare_green', 'scatter', 'scatter_flash', 'drum',
            'wheel_frame', 'pointer', 'buy', 'buy_flash', 'safe', 'wof', 'panel_desk' if variant == 'desk' else 'panel_mob',
            *[f't_{k}' for k, _, _ in CARDS], *[f'd_{k}' for k, _, _ in CARDS])

    if variant == 'desk':
        logo_y, logo_w = 330, 600
        cards = [(-666 + 444 * i, -78) for i in range(4)]
        panel, pw, ph, s = 'panel_desk', 404, 470, 1.0
        tap_y, tap_w = -395, 420
        deco = [('money', -740, 330, 360, 0.1, 8), ('money', 740, 330, 360, 0.6, -8),
                ('coin2', -880, -380, 60, 0.3, 0), ('coin1', 900, -360, 54, 0.8, 0), ('coin2', 470, 380, 46, 0.5, 0)]
        spots = [(-430, 380, 0.8), (420, 400, 1.0), (-900, 200, 0.7), (880, 200, 0.6), (-260, 250, 0.5),
                 (270, 250, 0.6), (-920, -120, 0.6), (930, -150, 0.7), (-300, -410, 0.5), (300, -410, 0.5)]
    else:
        logo_y, logo_w = 575, 620
        cards = [(-188, 236), (188, 236), (-188, -236), (188, -236)]
        panel, pw, ph, s = 'panel_mob', 356, 450, 0.86
        tap_y, tap_w = -585, 440
        deco = [('coin2', -330, 680, 54, 0.3, 0), ('coin1', 330, 470, 48, 0.8, 0), ('coin2', -340, -650, 50, 0.5, 0),
                ('coin1', 335, -660, 46, 0.1, 0)]
        spots = [(-250, 670, 0.7), (250, 480, 0.8), (-330, 480, 0.5), (360, 0, 0.6), (-360, -10, 0.6),
                 (300, -640, 0.5), (0, 680, 0.5)]

    light_burst(sk, 'burst', 'root', 0, logo_y, logo_w * 1.9, t0=0.0, alpha=0.7, rays_w=logo_w * 1.5)
    for i, (region, x, y, dw, ph_, rot) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=10, phase=ph_, rot_amp=5, rot=rot)

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

def info_chip(sk, idx, icon, text, plaque, x, y, cw, chh, t0, from_x, icon_w, tk=0.78):
    c = sk.bone(f'chip{idx}', 'root', x, y)
    sk.slot(f'chip{idx}', c, plaque, w=cw, h=chh)
    sk.both(f'chip{idx}', 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1)
    move(sk, c, lambda t: (seg(t, t0, t0 + 0.6, from_x, 0), 0), lambda t: (0, bob(t, 4, IDLE, idx * 0.5)))
    tw_ = min(ART[text].width * tk, cw - icon_w - 150)
    gap = 26
    total = icon_w + gap + tw_
    ib = sk.bone(f'chip{idx}_i', c, -total / 2 + icon_w / 2, 4)
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
    plq = 'plaque_desk' if variant == 'desk' else 'plaque_mob'
    add_art(sk, 'burst', 'rays', 'light', 'glow', 'star', 'case', 'vault', 'money', 'coin1', 'coin2', 'chip',
            'chip_flash', 'wild', 'scatter', 't_free_spins', 't_you_won', 'd_chip_wild', 'd_chip_fs', 'tap_start', plq)

    if variant == 'desk':
        won_y, title_y, title_w = 385, 270, 820
        chip_y, chip_w = 30, 270
        case, vault = (-560, 10, 400), (570, 30, 360)
        chips = [(-370, -230, 660, -300), (370, -230, 660, 300)]
        chip_h, chip_icon, tk = 132, 96, 0.78
        tap_y, tap_w = -385, 400
        coins = [('coin2', -300, 150, 56, 0.1), ('coin1', 310, 160, 50, 0.6), ('coin2', 820, -360, 50, 0.3),
                 ('coin1', -840, -350, 52, 0.8)]
        spots = [(-480, 330, 0.8), (480, 340, 0.9), (-880, -250, 0.7), (870, -260, 0.6), (-200, 120, 0.5),
                 (210, -60, 0.5), (0, 440, 0.5)]
    else:
        won_y, title_y, title_w = 590, 478, 700
        chip_y, chip_w = 205, 290
        case, vault = (-240, 20, 270), (245, 30, 240)
        chips = [(0, -205, 680, -420), (0, -365, 680, 420)]
        chip_h, chip_icon, tk = 140, 104, 0.95
        tap_y, tap_w = -560, 420
        coins = [('coin2', -330, 320, 52, 0.1), ('coin1', 330, 350, 46, 0.6), ('coin2', -320, -650, 48, 0.3),
                 ('coin1', 320, -660, 44, 0.8)]
        spots = [(-300, 560, 0.6), (300, 520, 0.7), (-340, 140, 0.5), (340, 0, 0.6), (-300, -480, 0.5),
                 (300, -480, 0.5)]

    light_burst(sk, 'burst', 'root', 0, chip_y + 10, chip_w * 3.6, t0=0.5, alpha=0.75, rays_w=chip_w * 3.2,
                rays_alpha=0.32)

    cx, cy, cw_ = case
    floater(sk, 'case', 'case', 'root', cx, cy, cw_, 0.3, amp=8, rot_amp=2, slide=(-80, 0))
    vx, vy, vw = vault
    floater(sk, 'vault', 'vault', 'root', vx, vy, vw, 0.4, amp=8, phase=0.5, rot_amp=2, slide=(80, 0))
    for i, (region, x, y, dw, ph_) in enumerate(coins):
        floater(sk, f'coin{i}', region, 'root', x, y, dw, 0.6 + 0.12 * i, amp=12, phase=ph_, rot_amp=10)

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

    rg = sk.bone('chip_glow', 'root', 0, chip_y)
    sk.slot('chip_glow', rg, 'glow', w=chip_w * 1.9, blend='additive', color='ff5a2aff')
    sk.both(rg, 'scale', uniform(lambda t: seg(t, 1.0, 1.6, 0.2, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.1)))
    sk.both('chip_glow', 'alpha', lambda t: seg(t, 1.0, 1.4, 0.0, 1.0) * (1 - 0.4 * fade(t, 1.4, 0.8)),
            lambda t: 0.6)

    # red casino chip: the live spin count is a DOM overlay glued to bone "count"
    pb = sk.bone('chip', 'root', 0, chip_y)
    sk.slot('chip', pb, 'chip', w=chip_w)
    sk.slot('chip_flash', pb, 'chip_flash', w=chip_w, blend='additive')
    sk.bone('count', pb, 0, 0)
    # flips in like a tossed chip (x-scale through 0), then lands
    sk.both(pb, 'scale', lambda t: (seg(t, 1.0, 1.15, 0.0, 1.0) * math.cos(min(1.0, max(0.0, (t - 1.0) / 0.5)) * 4 * math.pi)
                                    if t < 1.5 else 1.0,
                                    pop(t, 1.0, 0.5, 0.2)),
            uniform(lambda t: 1 + 0.04 * pulse(t, 2.0, 0.0, 6)))
    sk.both(pb, 'rotate', lambda t: seg(t, 1.0, 1.5, -30, 0), lambda t: bob(t, 3, IDLE))
    sk.both('chip', 'alpha', lambda t: fade(t, 1.0, 0.15), lambda t: 1)
    sk.both('chip_flash', 'alpha', lambda t: seg(t, 1.5, 1.9, 0.8, 0.0) if t >= 1.5 else 0,
            lambda t: 0.3 * pulse(t, 2.0, 0.0, 8))

    (x0, y0, cw0, f0), (x1, y1, cw1, f1) = chips
    info_chip(sk, 0, 'wild', 'd_chip_wild', plq, x0, y0, cw0, chip_h, 1.6, f0, chip_icon, tk)
    info_chip(sk, 1, 'scatter', 'd_chip_fs', plq, x1, y1, cw1, chip_h, 1.75, f1, chip_icon, tk)

    twinkles(sk, 'root', spots, seed=11)
    tap_hint(sk, 'tap_start', tap_y, tap_w)
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
