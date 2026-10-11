"""Sugar Galaxy — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Same contract as Neon Reels' screens (scripts/neon_reels_screens.py): a
full-screen skeleton authored on the game's design canvas (origin = canvas
centre, 1 unit = 1 design px, y up), `intro` (3s) -> `idle` (4s seamless
loop, first idle frame == last intro frame). Four variants: feature/bonus x
desk (1932x940) / mob (780x1416). The game's background is NOT in the
skeleton — slot.js puts the game's own bg PNG under the canvas (cover).

No designer pack for these screens: the art is the game's own — symbol
statics (Export/*/static.png), the logo, and pieces cut out of the popup
atlases (light burst, galaxy, planet, crystals, counter plate, ribbon) —
plus panels / texts drawn here with PIL in the popups' purple-gold style.

Usage:
  python scripts/sugar_galaxy_screens.py <fonts_dir> [out_dir]

fonts_dir — luckiest.ttf, baloo.ttf (front/fonts woff2 converted with
            fontTools: TTFont(woff2).flavor = None; .save(ttf))
out_dir   — default front/img/sugar-galaxy/screens
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, in_out_sine, lerp, out_back, out_cubic, pulse, rays, seg,
    soft_glow, spark, text_img, trim, vgrad, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(ROOT, 'front', 'img', 'sugar-galaxy')
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


def symbol(code):
    return trim(Image.open(os.path.join(ART_DIR, 'Export', code, 'static.png')).convert('RGBA'))


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


def popup_region(popup, name):
    """One region of a popup export, un-rotated and with its whitespace restored."""
    folder = os.path.join(ART_DIR, 'Popup', popup)
    r = parse_atlas(os.path.join(folder, 'animation.atlas'))[name]
    page = Image.open(os.path.join(folder, 'animation.png')).convert('RGBA')
    x, y, w, h = map(int, r['bounds'].split(','))
    if r.get('rotate') in ('90', 'true'):
        im = page.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
    else:
        im = page.crop((x, y, x + w, y + h))
    return trim(im)


def logo_hd():
    """The in-game logo is only 251x150 — 2x Lanczos + unsharp for the screens."""
    im = Image.open(os.path.join(ART_DIR, 'logo.png')).convert('RGBA')
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2.2, percent=90, threshold=2))
    rgb.putalpha(im.getchannel('A'))
    return trim(rgb)


GOLD = [(0, hexc('fffbd0')), (0.42, hexc('ffd83a')), (1, hexc('ff8a00'))]
PINK = [(0, hexc('fff0fb')), (0.45, hexc('ff9be6')), (1, hexc('e23ab8'))]
WHITE = [(0, hexc('ffffff')), (1, hexc('efe2ff'))]


def title(text, size, fill=GOLD, glow='ff3fd0'):
    return text_img(text, font('luckiest', size), fill, stroke='3b0a63', stroke_w=max(3, size // 9),
                    glow=glow, glow_r=max(5, size // 6), shadow='14002a')


def lines(rows, size, fill=WHITE, gap=0.08, weight=800):
    """Centered multi-line caption (each row its own stroked line)."""
    ims = [text_img(r, font('baloo', size, weight), fill, stroke='2a0650', stroke_w=max(3, size // 8),
                    glow=None, shadow='12001f') for r in rows]
    w = max(i.width for i in ims)
    step = int(size * (1 + gap))
    h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


def candy_panel(w, h, radius=40):
    """Purple glass card with a glowing lilac rim, popup_counter_bg style."""
    pad = 34
    W, H = w + 2 * pad, h + 2 * pad
    box = [pad, pad, pad + w - 1, pad + h - 1]
    m = Image.new('L', (W, H))
    ImageDraw.Draw(m).rounded_rectangle(box, radius, fill=255)
    out = Image.new('RGBA', (W, H))
    # outer glow
    rim = Image.new('L', (W, H))
    ImageDraw.Draw(rim).rounded_rectangle(box, radius, outline=255, width=10)
    out.paste(Image.new('RGBA', (W, H), hexc('c45cff')), (0, 0), rim.filter(ImageFilter.GaussianBlur(14)))
    # body: vertical gradient + diagonal gloss bands
    body = vgrad((W, H), [(0, hexc('6c2fd6', 236)), (0.55, hexc('3d128c', 240)), (1, hexc('230a55', 245))])
    gloss = Image.new('L', (W, H))
    gd = ImageDraw.Draw(gloss)
    for x0, bw, a in ((-0.15, 0.22, 34), (0.22, 0.08, 22), (0.55, 0.3, 16)):
        x0, bw = x0 * W, bw * W
        gd.polygon([(x0 + H * 0.6, 0), (x0 + bw + H * 0.6, 0), (x0 + bw, H), (x0, H)], fill=a)
    body.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(gloss, m))
    out.paste(body, (0, 0), m)
    # top inner highlight
    hl = Image.new('L', (W, H))
    ImageDraw.Draw(hl).rounded_rectangle([pad + 10, pad + 8, pad + w - 11, pad + h * 0.42], radius - 10, fill=40)
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(10)), m)
    out.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0), hl)
    # crisp rim: lilac outer line + pale inner line
    line = Image.new('L', (W, H))
    ImageDraw.Draw(line).rounded_rectangle(box, radius, outline=255, width=6)
    out.paste(Image.new('RGBA', (W, H), hexc('e9c8ff')), (0, 0), line)
    line2 = Image.new('L', (W, H))
    ImageDraw.Draw(line2).rounded_rectangle([b + (5 if i < 2 else -5) for i, b in enumerate(box)],
                                             radius - 5, outline=150, width=2)
    out.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0), line2)
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
    'burst': soft(popup_region('popup_bonus_spins_win', 'popup_light'), 760),
    'galaxy': soft(popup_region('popup_bonus_spins_total_win', 'popup_universe'), 640),
    'planet': popup_region('popup_bonus_spins_total_win', 'popup_planet'),
    'ribbon': popup_region('popup_bonus_spins_total_win', 'popup_back_counter'),
    'plate': popup_region('popup_bonus_spins_win', 'popup_counter_bg'),
    'plate_frame': popup_region('popup_bonus_spins_win', 'popup_frame_counter'),
    'crystal': popup_region('popup_bonus_spins_win', 'popup_diamond3'),
    'shard': popup_region('popup_bonus_spins_win', 'popup_diamond4'),
    'glow': soft_glow(256),
    'star': star4(96),
    'rays': rays(560, n=16),
}
for code in ('x2', 'x3', 'x5', 'x7', 'bomb', 'scatter', 'wild', 'hp_red', 'hp_blue', 'hp_yellow', 'hp_green'):
    ART[code] = symbol(code)
ART['logo_flash'] = flash_of(ART['logo'], 0.9)
ART['bomb_flash'] = flash_of(ART['bomb'], 0.9)
ART['scatter_flash'] = flash_of(ART['scatter'], 0.8)

# Feature cards — copy matches the seed (app/seed/sugar_galaxy.py): 8+ of a
# kind anywhere pays and tumbles, x-tokens sum into the step multiplier,
# bombs clear their row + column, 3+ scatters = 7 free spins (retriggers).
CARDS = [
    ('tumble', 'TUMBLE WINS', ['8+ SAME SYMBOLS', 'ANYWHERE WIN']),
    ('multi', 'MULTIPLIERS', ['x2 x3 x5 x7 ADD UP', 'ON EVERY CASCADE']),
    ('bomb', 'BOMBS', ['BLAST THEIR WHOLE', 'ROW AND COLUMN']),
    ('fs', 'FREE SPINS', ['3+ SCATTERS', 'AWARD 7 SPINS']),
]
for key, head, desc in CARDS:
    ART[f't_{key}'] = title(head, 60)
    ART[f'd_{key}'] = lines(desc, 40)
ART['tap_continue'] = title('TAP TO CONTINUE', 58, fill=WHITE, glow='b44dff')
ART['tap_start'] = title('TAP TO START', 64, fill=WHITE, glow='b44dff')
ART['t_free_spins'] = title('FREE SPINS', 150)
ART['t_you_won'] = title('YOU HAVE WON', 64, fill=PINK, glow='7a2bff')
ART['d_chip_multi'] = lines(['MULTIPLIERS STACK', 'FOR THE WHOLE ROUND'], 40)
ART['d_chip_fs'] = lines(['3+ SCATTERS', 'GIVE +7 SPINS'], 40)
ART['panel_desk'] = candy_panel(400, 450)
ART['panel_mob'] = candy_panel(352, 420, radius=36)


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


def twinkles(sk, parent, spots, seed, start=1.4, tint='ffe6ffff'):
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
        # 4-point star: a 90deg turn per loop is seamless
        sk.both(b, 'rotate', lambda t: 90 * (t - INTRO) / IDLE, lambda t: 90 * t / IDLE)
        sk.both(f'tw{i}', 'alpha', lambda t, f=blink: f(t - INTRO) * env(t), lambda t, f=blink: f(t))


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.9, rays_w=None, rays_alpha=0.35):
    """popup_light burst (breathing) + slowly turning rays behind it."""
    rw = rays_w or w * 0.75
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=rw, blend='additive', color='ffc4f4ff')
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


def tap_hint(sk, region, y, w):
    b = sk.bone('tap', 'root', 0, y)
    sk.slot('tap', b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: seg(t, 2.2, 2.7, 0.8, 1.0, out_back)), uniform(lambda t: breathe(t, 2.0, 0.04)))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.5),
            lambda t: 0.775 + 0.225 * math.cos(2 * math.pi * t / 2.0))


# --------------------------------------------------------------------------
# feature (preview) screen

def card_icons(sk, key, parent, t0, s):
    """Card illustration, centred on `parent`; s = icon scale (1 = 150 units)."""
    if key == 'tumble':
        for i, (code, x, y, sz, ph) in enumerate((('hp_blue', -70, -6, 120, 0.0), ('hp_yellow', 70, -6, 120, 0.33),
                                                  ('hp_red', 0, 22, 140, 0.66))):
            b = sk.bone(f'{key}_i{i}', parent, x * s, y * s)
            sk.slot(f'{key}_i{i}', b, code, w=sz * s)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.1 * i: pop(t, d, 0.5, 0.0)), uniform(lambda t: 1))
            # tumble: each planet drops in from above, then bobs
            move(sk, b, lambda t, d=t0 + 0.1 * i: (0, seg(t, d, d + 0.45, 90 * s, 0, out_back)),
                    lambda t, ph=ph: (0, bob(t, 7 * s, 2.0, ph)))
            sk.both(b, 'rotate', lambda t: 0, lambda t, ph=ph: bob(t, 6, IDLE, ph))
    elif key == 'multi':
        for i, code in enumerate(('x2', 'x3', 'x5', 'x7')):
            col, row = i % 2, i // 2
            b = sk.bone(f'{key}_i{i}', parent, (col - 0.5) * 132 * s, (0.5 - row) * 100 * s)
            sk.slot(f'{key}_i{i}', b, code, w=(92 + 6 * i) * s)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.08 * i: pop(t, d, 0.45, 0.0)),
                    uniform(lambda t, i=i: 1 + 0.12 * pulse(t, 2.0, i * 0.12, sharp=6)))
            sk.both(b, 'rotate', lambda t: 0, lambda t, i=i: bob(t, 7, 2.0, i * 0.25))
    elif key == 'bomb':
        g = sk.bone(f'{key}_glow', parent, 0, -6 * s)
        sk.slot(f'{key}_glow', g, 'glow', w=260 * s, blend='additive', color='ff5ad2ff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 1.0, 0.18)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.7 * fade(t, t0), lambda t: 0.7 - 0.3 * pulse(t, 1.0, 0.0, 2))
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
        sk.slot(f'{key}_glow', g, 'glow', w=260 * s, blend='additive', color='5ad8ffff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.15)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.6 * fade(t, t0), lambda t: 0.6)
        b = sk.bone(f'{key}_i0', parent)
        sk.slot(f'{key}_i0', b, 'scatter', w=180 * s)
        fl = sk.slot(f'{key}_fl', b, 'scatter_flash', w=180 * s, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)), uniform(lambda t: 1))
        move(sk, b, lambda t: (0, 0), lambda t: (0, bob(t, 9 * s, 2.0)))
        sk.both(fl, 'alpha', lambda t: 0, lambda t: 0.5 * pulse(t, 4.0, 0.5, 8))


def feature_card(sk, idx, key, x, y, panel, pw, ph, t0, s):
    c = sk.bone(f'card{idx}', 'root', x, y)
    sk.slot(f'card{idx}', c, panel, w=pw + 68)  # panel png carries a 34px glow pad
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -70, 0)),
            lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    ti, di = ART[f't_{key}'], ART[f'd_{key}']
    t_w = min(ti.width * 0.92 * s, pw - 40)
    d_w = min(di.width * 0.8 * s, pw - 36)
    t_y = ph * 0.5 - 58 * s
    d_y = -ph * 0.5 + 64 * s
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
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'star', 'crystal', 'shard', 'tap_continue',
            'hp_blue', 'hp_yellow', 'hp_red', 'x2', 'x3', 'x5', 'x7', 'bomb', 'bomb_flash', 'scatter',
            'scatter_flash', 'panel_desk' if variant == 'desk' else 'panel_mob',
            *[f't_{k}' for k, _, _ in CARDS], *[f'd_{k}' for k, _, _ in CARDS])

    if variant == 'desk':
        logo_y, logo_w = 300, 470
        cards = [(-660 + 440 * i, -95) for i in range(4)]
        panel, pw, ph, s = 'panel_desk', 400, 450, 1.0
        tap_y, tap_w = -400, 430
        deco = [('crystal', 850, 320, 120, 0.1), ('shard', -860, 330, 80, 0.6), ('shard', 600, 420, 56, 0.35)]
        spots = [(-430, 380, 0.8), (420, 400, 1.0), (-900, 330, 0.7), (880, 380, 0.6), (-240, 210, 0.5),
                 (250, 220, 0.6), (-910, -60, 0.6), (930, -120, 0.7), (0, -420, 0.5)]
    else:
        logo_y, logo_w = 560, 400
        cards = [(-186, 215), (186, 215), (-186, -230), (186, -230)]
        panel, pw, ph, s = 'panel_mob', 352, 420, 0.86
        tap_y, tap_w = -540, 420
        deco = [('crystal', 320, 600, 90, 0.1), ('shard', -330, 640, 60, 0.6)]
        spots = [(-250, 660, 0.7), (230, 470, 0.8), (-330, 470, 0.5), (340, -10, 0.6), (-340, -460, 0.6),
                 (300, -620, 0.5), (0, 680, 0.5)]

    light_burst(sk, 'burst', 'root', 0, logo_y - 10, logo_w * 2.6, t0=0.0, alpha=0.75)
    for i, (region, x, y, dw, ph_) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=12, phase=ph_, rot_amp=6)

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
    """Compact "icon + caption" group, optionally on its own ribbon of width cw."""
    c = sk.bone(f'chip{idx}', 'root', x, y)
    if ribbon:
        sk.slot(f'chip{idx}', c, 'ribbon', w=cw, h=cw * 0.2)
        sk.both(f'chip{idx}', 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1)
    move(sk, c, lambda t: (seg(t, t0, t0 + 0.6, from_x, 0), 0), lambda t: (0, bob(t, 4, IDLE, idx * 0.5)))
    tw_ = min(ART[text].width * 0.85, cw - icon_w - 90)
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
    add_art(sk, 'burst', 'rays', 'galaxy', 'planet', 'crystal', 'shard', 'glow', 'star', 'ribbon', 'plate',
            'plate_frame', 'x2', 'x3', 'x5', 'x7', 'scatter', 't_free_spins', 't_you_won', 'd_chip_multi',
            'd_chip_fs', 'tap_start')

    if variant == 'desk':
        won_y, title_y, title_w = 380, 235, 860
        plate_y, plate_w = 25, 330
        chips = [(-380, -235, 700, -300), (380, -235, 700, 300)]
        band = (0, -235, 1560)  # one ribbon under both groups
        chip_icon = 120
        tap_y, tap_w = -395, 420
        planet = (-740, 210, 430)
        deco = [('crystal', 760, 260, 130, 0.1), ('shard', 640, -40, 80, 0.5), ('shard', -620, -60, 70, 0.8)]
        tokens = [('x2', -262, 85), ('x3', 262, 85), ('x5', -262, -55), ('x7', 262, -55)]
        token_w = 120
        spots = [(-480, 330, 0.8), (480, 340, 0.9), (-880, -280, 0.7), (870, -260, 0.6), (-160, 120, 0.5),
                 (170, -60, 0.5), (0, 440, 0.5)]
    else:
        won_y, title_y, title_w = 612, 480, 700
        plate_y, plate_w = 170, 330
        chips = [(0, -230, 720, -420), (0, -400, 720, 420)]
        band = None
        chip_icon = 112
        tap_y, tap_w = -590, 420
        planet = (-300, 690, 200)
        deco = [('crystal', 300, 640, 90, 0.1), ('shard', -335, -105, 60, 0.6), ('shard', 338, 180, 56, 0.3)]
        tokens = [('x2', -250, 300), ('x3', 250, 300), ('x5', -250, 60), ('x7', 250, 60)]
        token_w = 112
        spots = [(-300, 560, 0.6), (300, 520, 0.7), (-340, 140, 0.5), (340, 0, 0.6), (-300, -560, 0.5),
                 (300, -650, 0.5)]

    # galaxy + light behind the counter
    gb = sk.bone('galaxy', 'root', 0, plate_y)
    sk.slot('galaxy', gb, 'galaxy', w=plate_w * 3.0)
    sk.both(gb, 'scale', uniform(lambda t: seg(t, 0.0, 1.0, 0.4, 1.0)), uniform(lambda t: breathe(t, IDLE, 0.06)))
    sk.both(gb, 'rotate', lambda t: seg(t, 0.0, 1.2, 40, 0), lambda t: bob(t, 6))
    sk.both('galaxy', 'alpha', lambda t: 0.85 * fade(t, 0.0, 0.8), lambda t: 0.85)
    light_burst(sk, 'burst', 'root', 0, plate_y + 40, plate_w * 4.4, t0=0.6, alpha=0.7, rays_w=plate_w * 3.4,
                rays_alpha=0.3)

    px, py, pw_ = planet
    floater(sk, 'planet', 'planet', 'root', px, py, pw_, 0.3, amp=14, rot_amp=4, slide=(-60, 0))
    for i, (region, x, y, dw, ph_) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=12, phase=ph_, rot_amp=7)

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
    sk.slot('plate_glow', rg, 'glow', w=plate_w * 1.9, blend='additive', color='ff6be0ff')
    sk.both(rg, 'scale', uniform(lambda t: seg(t, 1.0, 1.6, 0.2, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.1)))
    sk.both('plate_glow', 'alpha', lambda t: seg(t, 1.0, 1.4, 0.0, 1.0) * (1 - 0.5 * fade(t, 1.4, 0.8)),
            lambda t: 0.5)

    # counter plate (the live spin count is a DOM overlay glued to bone "count")
    pb = sk.bone('plate', 'root', 0, plate_y)
    sk.slot('plate', pb, 'plate', w=plate_w * 0.87)
    sk.slot('plate_frame', pb, 'plate_frame', w=plate_w)
    sk.bone('count', pb, 0, -4)
    sk.both(pb, 'scale', uniform(lambda t: pop(t, 1.0, 0.6, 0.0)),
            uniform(lambda t: 1 + 0.05 * pulse(t, 2.0, 0.0, 6)))
    sk.both('plate', 'alpha', lambda t: fade(t, 1.0, 0.2), lambda t: 1)
    sk.both('plate_frame', 'alpha', lambda t: fade(t, 1.0, 0.2), lambda t: 1)

    # multiplier tokens orbiting the plate (pop in, then bob)
    for i, (code, x, y) in enumerate(tokens):
        b = sk.bone(f'tok{i}', 'root', x, y)
        sk.slot(f'tok{i}', b, code, w=token_w)
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
        sk.slot('band', rb, 'ribbon', w=bw, h=150)
        sk.both(rb, 'scale', lambda t: (seg(t, 1.5, 2.0, 0.2, 1.0), 1), uniform(lambda t: 1))
        sk.both('band', 'alpha', lambda t: fade(t, 1.5, 0.4), lambda t: 1)
    (x0, y0, cw0, f0), (x1, y1, cw1, f1) = chips
    info_chip(sk, 0, 'x5', 'd_chip_multi', x0, y0, cw0, 1.6, f0, chip_icon, ribbon=not band)
    info_chip(sk, 1, 'scatter', 'd_chip_fs', x1, y1, cw1, 1.75, f1, chip_icon, ribbon=not band)

    twinkles(sk, 'root', spots, seed=11)
    tap_hint(sk, 'tap_start', tap_y, tap_w)
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
