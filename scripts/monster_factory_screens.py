"""Monster Factory — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Same contract as scripts/sugar_galaxy_screens.py (same avalanche mechanic): a
full-screen skeleton authored on the game's design canvas (origin = canvas
centre, 1 unit = 1 design px, y up), `intro` (3s) -> `idle` (4s seamless
loop, first idle frame == last intro frame). Four variants: feature/bonus x
desk (1932x940) / mob (780x1416). The game's background is NOT in the
skeleton — js/monster-factory/screens.js puts bg_base / bg_bonus under the
canvas (cover) with a dark vignette.

Two empty bones are the DOM contract of screens.js:
  count — centre of the spin-counter window (bonus only; DOM number glued here)
  tap   — where the DOM "TAP TO CONTINUE" hint sits (nothing baked there)

Art is the game's own flat PNGs (symbols/*, img/logo, hero, popup_freespins,
plate_counter); steel panels, texts, lightning and sparks are drawn here with
PIL. Fonts are read straight from front/fonts/*.woff2 (Pillow opens woff2).

Usage:
  python scripts/monster_factory_screens.py [out_dir] [--preview DIR]

--preview DIR  also renders a software preview (pure PIL/numpy re-implementation
               of the bone/slot/alpha math, read back from the written json +
               PMA atlas) as contact sheets DIR/<skeleton>.jpg.
"""

import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, in_cubic, out_back, out_cubic, pulse, rays, seg, soft_glow,
    spark, text_img, trim, vgrad, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(ROOT, 'front', 'img', 'monster-factory')
FONT_DIR = os.path.join(ROOT, 'front', 'fonts')

_args = [a for a in sys.argv[1:]]
PREVIEW = None
if '--preview' in _args:
    i = _args.index('--preview')
    PREVIEW = _args[i + 1]
    del _args[i:i + 2]
OUT = _args[0] if _args else os.path.join(ART_DIR, 'screens')

INTRO = 3.0
IDLE = 4.0
DESK = (1932, 940)
MOB = (780, 1416)


# --------------------------------------------------------------------------
# source art

def font(name, size, weight=None):
    path = {'luckiest': 'luckiest-guy-latin-fe2ede07.woff2', 'baloo': 'baloo-2-latin-2245892f.woff2'}[name]
    f = ImageFont.truetype(os.path.join(FONT_DIR, path), size)
    if weight:
        f.set_variation_by_axes([weight])
    return f


def art(rel):
    return trim(Image.open(os.path.join(ART_DIR, rel)).convert('RGBA'))


GOLD = [(0, hexc('fff8c8')), (0.45, hexc('ffd23a')), (1, hexc('ff8a00'))]
LIME = [(0, hexc('f4ffd0')), (0.5, hexc('9dff3a')), (1, hexc('2fbf1a'))]
VIOLET = [(0, hexc('fbeaff')), (0.5, hexc('d58cff')), (1, hexc('9a3cff'))]
WHITE = [(0, hexc('ffffff')), (1, hexc('ffe9c8'))]


def title(text, size, fill=GOLD, glow='ff7a1a', stroke='2a1004'):
    return text_img(text, font('luckiest', size), fill, stroke=stroke, stroke_w=max(3, size // 9),
                    glow=glow, glow_r=max(5, size // 6), shadow='120600')


def lines(rows, size, fill=WHITE, gap=0.02, stroke='14183a'):
    ims = [text_img(r, font('baloo', size, 800), fill, stroke=stroke, stroke_w=max(3, size // 8),
                    glow=None, shadow='05060f') for r in rows]
    w = max(i.width for i in ims)
    step = int(size * (1 + gap))
    h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


def hazard(w, h, stripe=None):
    """Yellow/black diagonal hazard stripes (opaque)."""
    stripe = stripe or max(10, h)
    im = Image.new('RGBA', (w, h), hexc('ffc21a'))
    d = ImageDraw.Draw(im)
    for x in range(-h * 2, w + h * 2, stripe * 2):
        d.polygon([(x, h), (x + stripe, h), (x + stripe + h, 0), (x + h, 0)], fill=hexc('1a1410'))
    return im


def steel_panel(w, h, radius=34, rim=18, glow='ff8a1a', win_top='22336e', win_bot='0b1230'):
    """Orange factory-steel card: glowing rim, rivets, hazard strip, navy window."""
    pad = 34
    W, H = w + 2 * pad, h + 2 * pad
    box = [pad, pad, pad + w - 1, pad + h - 1]
    m = Image.new('L', (W, H))
    ImageDraw.Draw(m).rounded_rectangle(box, radius, fill=255)
    out = Image.new('RGBA', (W, H))
    g = Image.new('L', (W, H))
    ImageDraw.Draw(g).rounded_rectangle(box, radius, outline=255, width=14)
    out.paste(Image.new('RGBA', (W, H), hexc(glow)), (0, 0), g.filter(ImageFilter.GaussianBlur(16)))
    # steel body
    body = vgrad((W, H), [(0, hexc('ffc35a')), (0.12, hexc('f08a24')), (0.6, hexc('d2611a')), (1, hexc('8e3a0c'))])
    out.paste(body, (0, 0), m)
    # hazard strip along the bottom rim
    hz = hazard(w, rim + 4, stripe=16)
    hm = Image.new('L', (W, H))
    ImageDraw.Draw(hm).rectangle([pad, pad + h - rim - 4, pad + w, pad + h], fill=255)
    hm = ImageChops.multiply(hm, m)
    hzc = Image.new('RGBA', (W, H))
    hzc.paste(hz, (pad, pad + h - rim - 4))
    out.paste(hzc, (0, 0), hm)
    # navy window
    wb = [pad + rim, pad + rim, pad + w - 1 - rim, pad + h - 1 - rim - 8]
    wm = Image.new('L', (W, H))
    ImageDraw.Draw(wm).rounded_rectangle(wb, radius - rim // 2, fill=255)
    win = vgrad((W, H), [(0, hexc(win_top, 246)), (1, hexc(win_bot, 250))])
    out.paste(Image.new('RGBA', (W, H), hexc('2a1004')), (0, 0),
              wm.filter(ImageFilter.MaxFilter(7)))  # dark lip around the window
    out.paste(win, (0, 0), wm)
    # inner shadow at the window top + glossy sheen
    sh = Image.new('L', (W, H))
    ImageDraw.Draw(sh).rounded_rectangle([wb[0], wb[1] - 30, wb[2], wb[1] + 26], radius, fill=120)
    sh = ImageChops.multiply(sh.filter(ImageFilter.GaussianBlur(12)), wm)
    out.paste(Image.new('RGBA', (W, H), (0, 0, 0, 255)), (0, 0), sh)
    gl = Image.new('L', (W, H))
    gd = ImageDraw.Draw(gl)
    gd.polygon([(wb[0], wb[1]), (wb[0] + (wb[2] - wb[0]) * 0.55, wb[1]), (wb[0] + (wb[2] - wb[0]) * 0.25, wb[3]),
                (wb[0], wb[3])], fill=16)
    out.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(gl, wm))
    # bevel highlights on the steel
    hl = Image.new('L', (W, H))
    ImageDraw.Draw(hl).rounded_rectangle([b + (3 if i < 2 else -3) for i, b in enumerate(box)], radius - 3,
                                         outline=150, width=3)
    out.paste(Image.new('RGBA', (W, H), hexc('fff0c0')), (0, 0), hl)
    ol = Image.new('L', (W, H))
    ImageDraw.Draw(ol).rounded_rectangle(box, radius, outline=255, width=3)
    out.paste(Image.new('RGBA', (W, H), hexc('3a1606')), (0, 0), ol)
    # rivets
    rr = 6
    for cx, cy in ((pad + rim // 2 + 4, pad + rim // 2 + 4), (pad + w - rim // 2 - 5, pad + rim // 2 + 4)):
        d = ImageDraw.Draw(out)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=hexc('6a2a08'))
        d.ellipse([cx - rr + 2, cy - rr + 1, cx + rr - 2, cy + rr - 3], fill=hexc('ffd27a'))
    return out


def bolt(length, seed, branches=2):
    """Jagged lightning bolt (vertical), white core + violet glow, straight alpha."""
    rnd = random.Random(seed)
    W, H = int(length * 0.42) + 60, length + 60

    def path(x0, y0, x1, y1, n, jit):
        pts = [(x0, y0)]
        for k in range(1, n):
            f = k / n
            pts.append((lerp_(x0, x1, f) + rnd.uniform(-jit, jit), lerp_(y0, y1, f) + rnd.uniform(-jit * 0.25, jit * 0.25)))
        pts.append((x1, y1))
        return pts

    main = path(W / 2, 30, W / 2 + rnd.uniform(-W * 0.2, W * 0.2), H - 30, 11, W * 0.16)
    core, glow = Image.new('L', (W, H)), Image.new('L', (W, H))
    dc, dg = ImageDraw.Draw(core), ImageDraw.Draw(glow)
    dc.line(main, fill=255, width=5, joint='curve')
    dg.line(main, fill=255, width=18, joint='curve')
    for b in range(branches):
        i = rnd.randint(2, 7)
        x0, y0 = main[i]
        sub = path(x0, y0, x0 + rnd.choice((-1, 1)) * W * 0.32, y0 + length * 0.28, 5, W * 0.07)
        dc.line(sub, fill=200, width=3, joint='curve')
        dg.line(sub, fill=200, width=12, joint='curve')
    glow = glow.filter(ImageFilter.GaussianBlur(12))
    out = Image.new('RGBA', (W, H), hexc('b45cff', 0))
    out.putalpha(glow.point(lambda a: int(a * 0.9)))
    c = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    out.paste(c, (0, 0), core.filter(ImageFilter.GaussianBlur(1)))
    return trim(out, pad=4, thr=2)


def lerp_(a, b, t):
    return a + (b - a) * t


def blast(w=512, h=64):
    """Horizontal blast streak for the bomb's row/column clear (hot core, orange rim)."""
    core = spark(w, h)
    glow = spark(w, h).filter(ImageFilter.GaussianBlur(h * 0.12))
    out = Image.new('RGBA', (w, h), hexc('ff9a2a', 0))
    out.putalpha(glow.getchannel('A'))
    out.alpha_composite(core)
    return out


def star4(size=96):
    s = spark(size, max(6, size // 7))
    im = Image.new('RGBA', (size, size))
    im.alpha_composite(s, (0, (size - s.height) // 2))
    im.alpha_composite(s.rotate(90, expand=True), ((size - s.height) // 2, 0))
    im.alpha_composite(soft_glow(size // 2), (size // 4, size // 4))
    return im


def bubble(size=64):
    """Goo bubble: soft ring + specular dot."""
    big = size * 4
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    d.ellipse([8, 8, big - 8, big - 8], outline=255, width=big // 14)
    d.ellipse([big * 0.26, big * 0.2, big * 0.42, big * 0.36], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(big / 60)).resize((size, size), Image.LANCZOS)
    fill = Image.new('L', (size, size))
    ImageDraw.Draw(fill).ellipse([2, 2, size - 2, size - 2], fill=40)
    im = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    im.putalpha(ImageChops.lighter(m, fill))
    return im


def soft(im, w):
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


def counter_plate():
    """plate_counter.png + where its navy window centre is (fraction of height from the top)."""
    im = Image.open(os.path.join(ART_DIR, 'img', 'plate_counter.png')).convert('RGBA')
    a = np.asarray(im).astype(int)
    navy = (a[..., 2] > a[..., 0] + 20) & (a[..., 2] < 140) & (a[..., 3] > 200) & (a[..., 0] < 60)
    ys, xs = np.nonzero(navy)
    bb = im.getchannel('A').getbbox()
    win_cy = ((ys.min() + ys.max()) / 2 - bb[1]) / (bb[3] - bb[1])
    return im.crop(bb), win_cy


ART = {
    'logo': art('img/logo.png'),
    'hero': art('img/hero.webp'),
    'popup_fs': art('img/popup_freespins.webp'),
    'glow': soft_glow(256),
    'star': star4(96),
    'rays': rays(560, n=16),
    'bubble': bubble(64),
    'blast': blast(),
}
ART['plate'], PLATE_WIN_CY = counter_plate()
for code in ('x2', 'x3', 'x5', 'x7', 'bomb', 'scatter', 'wild', 'hp_red', 'hp_blue', 'hp_yellow', 'hp_green',
             'lp_blue'):
    ART[code] = art(f'symbols/{code}.png')
for k in ('logo', 'bomb', 'scatter', 'hp_red', 'popup_fs'):
    ART[k + '_flash'] = flash_of(ART[k], 0.9)
for i in range(4):
    ART[f'bolt{i}'] = bolt(420 + 60 * i, seed=31 + i, branches=2 + i % 2)

# Card copy matches the seed: 8+ of a kind anywhere pays and cascades, goo orbs
# add their multiplier, the bomb clears its row + column, 3 scatters = 7 spins.
CARDS = [
    ('cascade', 'CASCADES', ['8+ SAME SYMBOLS', 'ANYWHERE WIN,', 'NEW ONES DROP IN']),
    ('multi', 'MULTIPLIERS', ['GOO ORBS', 'x2 x3 x5 x7', 'ADD TO THE WIN']),
    ('bomb', 'MONSTER BOMB', ['BLASTS ITS', 'WHOLE ROW', 'AND COLUMN']),
    ('fs', 'FREE SPINS', ['3 SCATTERS', 'AWARD', '7 FREE SPINS']),
]
for key, head, desc in CARDS:
    ART[f't_{key}'] = title(head, 62)
    ART[f'd_{key}'] = lines(desc, 38)
ART['t_you_won'] = title('YOU WON', 76, fill=WHITE, glow='b45cff', stroke='2a0a4a')
ART['t_chip_multi'] = title('MULTIPLIERS STACK', 54, fill=GOLD, glow='b45cff', stroke='2a0a4a')
ART['d_chip_multi'] = lines(['EVERY GOO ORB ADDS UP', 'FOR THE WHOLE BONUS'], 36, stroke='1c0838')
ART['t_chip_fs'] = title('FREE SPINS', 54, fill=LIME, glow='b45cff', stroke='0e2a06')
ART['d_chip_fs'] = lines(['3 SCATTERS', 'AWARD 7 SPINS'], 36, stroke='1c0838')
ART['panel_desk'] = steel_panel(330, 520)
ART['panel_mob'] = steel_panel(352, 446, radius=30)
ART['panel_bonus'] = steel_panel(440, 470, glow='b45cff', win_top='3a1a7a', win_bot='140830')
ART['panel_bonus_mob'] = steel_panel(720, 150, radius=30, rim=16, glow='b45cff', win_top='3a1a7a',
                                     win_bot='140830')


# --------------------------------------------------------------------------
# motion helpers (idle offsets are 0 at t=0 so idle starts where intro ends)

def bob(t, amp, period=IDLE, phase=0.0):
    return amp * (wave(t, period, phase) - wave(0, period, phase))


def pop(t, t0, dur=0.55, s0=0.3):
    return seg(t, t0, t0 + dur, s0, 1.0, out_back)


def fade(t, t0, dur=0.3):
    return seg(t, t0, t0 + dur, 0.0, 1.0, out_cubic)


def move(sk, bone, intro_fn, idle_fn):
    """Translate as an OFFSET from the bone's setup position (the kit wants the
    absolute local position, so the setup x/y is added back)."""
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


def twinkles(sk, parent, spots, seed, start=1.4, tint='fff0d0ff'):
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


def bubbles(sk, parent, n, x0, x1, y0, y1, seed, tint, start=0.8):
    """Goo bubbles rising on a seamless loop (each rises once per IDLE)."""
    rnd = random.Random(seed)
    for i in range(n):
        x = rnd.uniform(x0, x1)
        ph = rnd.random()
        size = rnd.uniform(18, 46)
        drift = rnd.uniform(-30, 30)
        b = sk.bone(f'bub{i}', parent, x, y0)
        sk.slot(f'bub{i}', b, 'bubble', w=size, blend='additive', color=tint)

        def u(t, ph=ph):
            return (t / IDLE + ph) % 1.0

        def pos(t, ph=ph, drift=drift):
            k = u(t, ph)
            return (drift * k + 8 * math.sin(2 * math.pi * k * 2), (y1 - y0) * k)

        def al(t, ph=ph):
            k = u(t, ph)
            return 0.8 * min(1, k / 0.15) * min(1, (1 - k) / 0.25)

        move(sk, b, lambda t, f=pos: f(t - INTRO), lambda t, f=pos: f(t))
        sk.both(f'bub{i}', 'alpha', lambda t, f=al: f(t - INTRO) * clamp((t - start) / 0.5), al)


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.6, tint='ffb45aff', rays_alpha=0.3, rays_tint='ffd28aff'):
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=w, blend='additive', color=rays_tint)
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both(rb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.8, 0.4, 1.0)), uniform(lambda t: 1))
    sk.both(f'{name}_rays', 'alpha', lambda t: rays_alpha * fade(t, t0, 0.6),
            lambda t: rays_alpha * (1 - 0.3 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, 'glow', w=w * 0.75, blend='additive', color=tint)
    sk.both(b, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.3, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.06)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.5),
            lambda t: alpha * (1 - 0.2 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))


def logo(sk, x, y, w, t0=0.15):
    lb = sk.bone('logo', 'root', x, y)
    sk.slot('logo', lb, 'logo', w=w)
    sk.slot('logo_flash', lb, 'logo_flash', w=w, blend='additive')
    sk.both(lb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.2, 1.0, out_back)),
            uniform(lambda t: breathe(t, IDLE, 0.025)))
    move(sk, lb, lambda t: (0, 0), lambda t: (0, bob(t, 6)))
    sk.both('logo', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: seg(t, t0 + 0.45, t0 + 0.95, 0.85, 0.0) if t >= t0 + 0.45 else 0,
            lambda t: 0.35 * pulse(t, IDLE, 0.55, 10))


def hero(sk, x, y, w, t0, from_x=-260):
    """Cyclops foreman: slides in from the side, then breathes / sways (pivot at the feet)."""
    im = ART['hero']
    h = w * im.height / im.width
    b = sk.bone('hero', 'root', x, y - h / 2)  # bone at the feet
    sk.slot('hero', b, 'hero', w=w, y=h / 2)
    move(sk, b, lambda t: (seg(t, t0, t0 + 0.6, from_x, 0, out_back), 0), lambda t: (0, 0))
    sk.both(b, 'scale', lambda t: (1, 1) if t > t0 + 0.6 else (1, seg(t, t0, t0 + 0.6, 0.9, 1.0)),
            lambda t: (1 + 0.012 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2,
                       1 + 0.03 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, 2.0, IDLE, 0.25))
    sk.both('hero', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)


# --------------------------------------------------------------------------
# feature (preview) screen

def tile(sk, name, parent, code, x, y, sz):
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, code, w=sz)
    return b


def card_icons(sk, key, parent, t0, s):
    """Card illustration, centred on `parent`; s = scale (1 = ~260 units wide)."""
    if key == 'cascade':
        # 2x2 of red cyclopes: they flash, burst into green goo, a mixed set
        # drops in, sits, then the reds tumble back in (loop closes on reds).
        st, sz = 116 * s, 110 * s
        cells = [(-st / 2, st / 2), (st / 2, st / 2), (-st / 2, -st / 2), (st / 2, -st / 2)]
        splash = sk.bone(f'{key}_splash', parent)
        sk.slot(f'{key}_splash', splash, 'glow', w=330 * s, blend='additive', color='7dff3aff')
        sk.both(splash, 'scale', uniform(lambda t: 0.3),
                uniform(lambda t: seg(t, 0.7, 1.2, 0.3, 1.25) if t < 1.2 else seg(t, 1.2, 1.6, 1.25, 1.4)))
        sk.both(f'{key}_splash', 'alpha', lambda t: 0,
                lambda t: seg(t, 0.7, 0.85, 0, 0.95) if t < 0.85 else seg(t, 0.85, 1.6, 0.95, 0))
        mixed = ('hp_blue', 'hp_yellow', 'hp_green', 'lp_blue')
        for i, (cx, cy) in enumerate(cells):
            d = t0 + 0.08 * i
            # set A: reds
            a = tile(sk, f'{key}_a{i}', parent, 'hp_red', cx, cy, sz)
            fl = sk.slot(f'{key}_af{i}', a, 'hp_red_flash', w=sz, blend='additive')
            drop = 130 * s

            def a_pos_idle(t, i=i):
                dd = 3.35 + 0.06 * i
                return (0, seg(t, dd, dd + 0.45, drop, 0, out_back) if t >= dd else 0)

            def a_scale_idle(t):
                if t < 0.55:
                    return 1 + 0.08 * math.sin(math.pi * clamp(t / 0.55))
                if t < 0.9:
                    return seg(t, 0.55, 0.9, 1.0, 1.35)
                return 1.0

            def a_alpha_idle(t, i=i):
                if t < 0.65:
                    return 1
                if t < 0.9:
                    return seg(t, 0.65, 0.9, 1, 0)
                dd = 3.35 + 0.06 * i
                return 0 if t < dd else fade(t, dd, 0.22)

            move(sk, a, lambda t, d=d: (0, seg(t, d, d + 0.5, drop, 0, out_back)), a_pos_idle)
            sk.both(a, 'scale', uniform(lambda t: 1), uniform(a_scale_idle))
            sk.both(f'{key}_a{i}', 'alpha', lambda t, d=d: fade(t, d, 0.22), a_alpha_idle)
            sk.both(fl, 'alpha', lambda t: 0,
                    lambda t: 0.85 * math.sin(math.pi * clamp(t / 0.6)) ** 2 if t < 0.9 else 0)
            # set B: the replacements that fall in
            bb = tile(sk, f'{key}_b{i}', parent, mixed[i], cx, cy, sz)

            def b_pos(t, i=i):
                dd = 0.95 + 0.07 * (3 - i)
                if t < dd:
                    return (0, drop)
                if t < 3.0:
                    return (0, seg(t, dd, dd + 0.45, drop, 0, out_back))
                return (0, seg(t, 3.0, 3.35, 0, -drop * 0.6, in_cubic))

            def b_alpha(t, i=i):
                dd = 0.95 + 0.07 * (3 - i)
                if t < dd:
                    return 0
                if t < 3.0:
                    return fade(t, dd, 0.22)
                return seg(t, 3.05, 3.35, 1, 0)

            move(sk, bb, lambda t: (0, drop), b_pos)
            sk.both(f'{key}_b{i}', 'alpha', lambda t: 0, b_alpha)
    elif key == 'multi':
        g = sk.bone(f'{key}_glow', parent)
        sk.slot(f'{key}_glow', g, 'glow', w=330 * s, blend='additive', color='ffb02aff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 1.0, 0.12)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.45 * fade(t, t0), lambda t: 0.45)
        for i, code in enumerate(('x2', 'x3', 'x5', 'x7')):
            col, row = i % 2, i // 2
            b = sk.bone(f'{key}_i{i}', parent, (col - 0.5) * 124 * s, (0.5 - row) * 118 * s)
            sk.slot(f'{key}_i{i}', b, code, w=118 * s)
            gl = sk.bone(f'{key}_g{i}', b)
            # an additive glow per orb, lighting up in sequence (one per 0.5s)
            sk.slot(f'{key}_g{i}', gl, 'glow', w=170 * s, blend='additive',
                    color=('7dff3aff', '3ab4ffff', 'c45cffff', 'ff8a2aff')[i])
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.1 * i: pop(t, d, 0.45, 0.0)),
                    uniform(lambda t, i=i: 1 + 0.16 * pulse(t, 2.0, i * 0.125, sharp=6)))
            sk.both(b, 'rotate', lambda t: 0, lambda t, i=i: bob(t, 6, 2.0, i * 0.25))
            sk.both(f'{key}_g{i}', 'alpha', lambda t: 0, lambda t, i=i: 0.9 * pulse(t, 2.0, i * 0.125, sharp=6))
    elif key == 'bomb':
        # row + column blast streaks firing every 2s, bomb shakes before each
        for j, rot in enumerate((0, 90)):
            bl = sk.bone(f'{key}_bl{j}', parent, rot=rot)
            sk.slot(f'{key}_bl{j}', bl, 'blast', w=340 * s, h=70 * s, blend='additive', color='ffd060ff')

            def blx(t):
                k = (t % 2.0)
                return (seg(k, 0.55, 0.8, 0.1, 1.15), seg(k, 0.55, 0.7, 0.4, 1.0) * seg(k, 0.8, 1.2, 1.0, 0.6))

            sk.both(bl, 'scale', lambda t: (0.1, 0.4), blx)
            sk.both(f'{key}_bl{j}', 'alpha', lambda t: 0,
                    lambda t: seg(t % 2.0, 0.55, 0.62, 0, 1) if (t % 2.0) < 0.75 else seg(t % 2.0, 0.75, 1.3, 1, 0))
        g = sk.bone(f'{key}_glow', parent, 0, -6 * s)
        sk.slot(f'{key}_glow', g, 'glow', w=300 * s, blend='additive', color='ff7a1aff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)),
                uniform(lambda t: 1 + 0.3 * pulse(t, 2.0, 0.28, 3)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.6 * fade(t, t0), lambda t: 0.6 + 0.4 * pulse(t, 2.0, 0.28, 3))
        b = sk.bone(f'{key}_i0', parent)
        sk.slot(f'{key}_i0', b, 'bomb', w=190 * s)
        fl = sk.slot(f'{key}_fl', b, 'bomb_flash', w=190 * s, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)),
                uniform(lambda t: 1 + 0.1 * pulse(t, 2.0, 0.27, 6) - 0.04 * pulse(t, 2.0, 0.4, 4)))
        sk.both(b, 'rotate', lambda t: 0,
                lambda t: 7 * math.sin(2 * math.pi * t * 8) * clamp(1 - abs((t % 2.0) - 0.3) / 0.3))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.35, t0 + 0.75, 0.8, 0.0) if t > t0 + 0.35 else 0,
                lambda t: 0.6 * pulse(t, 2.0, 0.27, 6))
    elif key == 'fs':
        g = sk.bone(f'{key}_glow', parent)
        sk.slot(f'{key}_glow', g, 'glow', w=320 * s, blend='additive', color='c45cffff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.15)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.6 * fade(t, t0), lambda t: 0.6)
        for i, (x, y, r, w_) in enumerate(((-94, -4, 6, 88), (0, 4, 0, 92), (94, -4, -6, 88))):
            b = sk.bone(f'{key}_i{i}', parent, x * s, y * s, rot=r)
            sk.slot(f'{key}_i{i}', b, 'scatter', w=w_ * s)
            fl = sk.slot(f'{key}_fl{i}', b, 'scatter_flash', w=w_ * s, blend='additive')
            d = t0 + 0.12 * i
            sk.both(b, 'scale', uniform(lambda t, d=d: pop(t, d, 0.5, 0.0)), uniform(lambda t: 1))
            move(sk, b, lambda t: (0, 0), lambda t, i=i: (0, bob(t, 7 * s, 2.0, i * 0.3)))
            sk.both(fl, 'alpha', lambda t: 0, lambda t, i=i: 0.55 * pulse(t, 4.0, 0.2 + 0.12 * i, 10))


def feature_card(sk, idx, key, x, y, panel, pw, ph, t0, s, icon_k=1.0, d_max=128):
    c = sk.bone(f'card{idx}', 'root', x, y)
    sk.slot(f'card{idx}', c, panel, w=pw + 68)  # panel png carries a 34px glow pad
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -80, 0)), lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    ti, di = ART[f't_{key}'], ART[f'd_{key}']
    t_w = min(ti.width * 0.9 * s, pw - 44)
    d_w = min(pw - 50, d_max * s * di.width / di.height)
    t_y = ph * 0.5 - 62 * s
    d_y = -ph * 0.5 + 34 * s + d_w * di.height / di.width / 2
    tb = sk.bone(f'card{idx}_t', c, 0, t_y)
    sk.slot(f'card{idx}_t', tb, f't_{key}', w=t_w)
    sk.both(f'card{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.15), lambda t: 1)

    gap_top = t_y - t_w * ti.height / ti.width / 2
    gap_bot = d_y + d_w * di.height / di.width / 2
    ib = sk.bone(f'card{idx}_icon', c, 0, (gap_top + gap_bot) / 2)
    card_icons(sk, key, ib, t0 + 0.25, s * icon_k)

    db = sk.bone(f'card{idx}_d', c, 0, d_y)
    sk.slot(f'card{idx}_d', db, f'd_{key}', w=d_w)
    sk.both(f'card{idx}_d', 'alpha', lambda t: fade(t, t0 + 0.3), lambda t: 1)


def build_feature(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'feature_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'logo', 'logo_flash', 'hero', 'rays', 'glow', 'star', 'bubble', 'blast', 'hp_red', 'hp_red_flash',
            'hp_blue', 'hp_yellow', 'hp_green', 'lp_blue', 'x2', 'x3', 'x5', 'x7', 'bomb', 'bomb_flash',
            'scatter', 'scatter_flash', 'panel_desk' if variant == 'desk' else 'panel_mob',
            *[f't_{k}' for k, _, _ in CARDS], *[f'd_{k}' for k, _, _ in CARDS])

    if variant == 'desk':
        # hero in a column on the left, the 4-card block + logo to its right
        pw, ph, s, panel = 330, 520, 1.1, 'panel_desk'
        step = 352
        cards = [(-284 + step * i, -68) for i in range(4)]
        block_cx = (cards[0][0] + cards[-1][0]) / 2
        logo_xy, logo_w = (block_cx, 340), 440
        hero_xy, hero_w = (-735, -470 + 600 * 0.5 + 10), 440  # (centre x, centre y)
        tap_y = -405
        spots = [(block_cx - 380, 400, 0.8), (block_cx + 400, 390, 1.0), (-880, 380, 0.7), (900, 400, 0.6),
                 (block_cx - 300, 250, 0.5), (block_cx + 300, 260, 0.6), (-560, 120, 0.6), (930, -380, 0.6)]
        bub = (-940, 940, -470, 300)
    else:
        pw, ph, s, panel = 352, 446, 0.98, 'panel_mob'
        cards = [(-186, 245), (186, 245), (-186, -213), (186, -213)]
        logo_xy, logo_w = (0, 572), 420
        hero_xy, hero_w = (-232, -708 + 300 * 0.5 - 2 + 0), 236
        tap_y = -560
        spots = [(-300, 660, 0.7), (290, 650, 0.8), (-340, 480, 0.5), (340, 470, 0.6), (330, -470, 0.6),
                 (-20, 690, 0.5)]
        bub = (-380, 380, -708, 500)

    light_burst(sk, 'burst', 'root', logo_xy[0], logo_xy[1] - 10, logo_w * 2.1, t0=0.0, alpha=0.55)
    bubbles(sk, 'root', 14 if variant == 'desk' else 10, bub[0], bub[1], bub[2], bub[3], seed=5, tint='9dff6aff')
    hx, hy = hero_xy
    hh = hero_w * ART['hero'].height / ART['hero'].width
    hero(sk, hx, hy if variant == 'desk' else -708 + hh / 2 - 6, hero_w, 0.35, from_x=-300 if variant == 'desk' else -240)
    logo(sk, logo_xy[0], logo_xy[1], logo_w)

    for i, ((x, y), (key, _, _)) in enumerate(zip(cards, CARDS)):
        feature_card(sk, i, key, x, y, panel, pw, ph, 0.7 + 0.18 * i, s,
                     *((1.0, 128) if variant == 'desk' else (0.86, 112)))

    twinkles(sk, 'root', spots, seed=7)
    sk.bone('tap', 'root', block_cx if variant == 'desk' else 100, tap_y)
    sk.write()


# --------------------------------------------------------------------------
# bonus screen

def lightning(sk, spots, t_on=0.4):
    """Additive bolts flickering out of phase (two strikes per loop each)."""
    for i, (x, y, rot, length, ph) in enumerate(spots):
        b = sk.bone(f'bolt{i}', 'root', x, y, rot=rot)
        sk.slot(f'bolt{i}', b, f'bolt{i % 4}', h=length, blend='additive', color='e6c8ffff')

        def strike(t, ph=ph):
            k = ((t / 2.0) + ph) % 1.0
            # flash - dip - flash - fade
            if k < 0.03:
                return k / 0.03
            if k < 0.06:
                return 1 - (k - 0.03) / 0.03 * 0.7
            if k < 0.09:
                return 0.3 + (k - 0.06) / 0.03 * 0.7
            if k < 0.25:
                return 1 - (k - 0.09) / 0.16
            return 0.0

        sk.both(f'bolt{i}', 'alpha', lambda t, f=strike: f(t - INTRO) * (1 if t > t_on else 0), strike)
        sk.both(b, 'scale', lambda t: (1, 1), lambda t, ph=ph: (1 if ((t / 2.0 + ph) % 1.0) < 0.5 else -1, 1))


def build_bonus(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = Skel(f'bonus_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'rays', 'glow', 'star', 'bubble', 'popup_fs', 'popup_fs_flash', 'plate', 'x2', 'x3', 'x5', 'x7',
            'scatter', 't_you_won', 't_chip_multi', 'd_chip_multi', 't_chip_fs', 'd_chip_fs',
            'bolt0', 'bolt1', 'bolt2', 'bolt3',
            'panel_bonus' if variant == 'desk' else 'panel_bonus_mob')

    if variant == 'desk':
        won_y, won_w = 425, 280
        plate_y, plate_w = 268, 300
        art_y, art_w = -122, 466
        tap_y = -432
        chips = [(-650, -10, -1), (650, -10, 1)]
        bolts = [(-420, 230, 18, 520, 0.0), (440, 240, -16, 560, 0.45), (-860, -160, 6, 460, 0.25),
                 (870, -150, -8, 480, 0.7)]
        spots = [(-300, 420, 0.8), (300, 420, 0.9), (-900, 400, 0.7), (900, 380, 0.6), (-280, -300, 0.5),
                 (290, -320, 0.6)]
        bub = (-300, 300, -470, 200)
    else:
        won_y, won_w = 668, 250
        plate_y, plate_w = 505, 300
        art_y, art_w = 105, 540
        tap_y = -625
        chips = [(0, -300, -1), (0, -470, 1)]
        bolts = [(-300, 330, 14, 460, 0.0), (300, 300, -14, 500, 0.45), (-330, -60, 4, 380, 0.25),
                 (330, -80, -6, 400, 0.7)]
        spots = [(-300, 640, 0.6), (300, 650, 0.7), (-340, 420, 0.5), (340, 180, 0.6), (-320, -700, 0.5)]
        bub = (-300, 300, -200, 300)

    lightning(sk, bolts)
    light_burst(sk, 'burst', 'root', 0, art_y + 60, art_w * 2.3, t0=0.2, alpha=0.6, tint='c45cffff',
                rays_alpha=0.32, rays_tint='e0b0ffff')
    bubbles(sk, 'root', 10, bub[0], bub[1], bub[2], bub[3], seed=9, tint='d08cffff', start=0.6)

    # the four monsters over the goo vat ("FREE SPINS" lettering is in the art)
    ab = sk.bone('art', 'root', 0, art_y)
    sk.slot('art', ab, 'popup_fs', w=art_w)
    sk.slot('art_flash', ab, 'popup_fs_flash', w=art_w, blend='additive')

    def slam(t):
        return seg(t, 0.2, 0.62, 0.3, 1.06, out_cubic) if t < 0.62 else seg(t, 0.62, 0.9, 1.06, 1.0, out_back)

    sk.both(ab, 'scale', uniform(slam), uniform(lambda t: breathe(t, 2.0, 0.02)))
    move(sk, ab, lambda t: (0, 0), lambda t: (0, bob(t, 6)))
    sk.both('art', 'alpha', lambda t: fade(t, 0.2, 0.2), lambda t: 1)
    sk.both('art_flash', 'alpha', lambda t: seg(t, 0.62, 1.1, 0.8, 0.0) if t >= 0.62 else 0,
            lambda t: 0.25 * pulse(t, IDLE, 0.5, 10))

    # "YOU WON" + counter plate on top (the live spin count is a DOM overlay
    # glued to bone "count", the centre of the plate's navy window)
    yb = sk.bone('won', 'root', 0, won_y)
    sk.slot('won', yb, 't_you_won', w=won_w)
    move(sk, yb, lambda t: (0, seg(t, 0.8, 1.2, 50, 0)), lambda t: (0, 0))
    sk.both(yb, 'scale', uniform(lambda t: 1), uniform(lambda t: breathe(t, 2.0, 0.03)))
    sk.both('won', 'alpha', lambda t: fade(t, 0.8, 0.3), lambda t: 1)

    rg = sk.bone('plate_glow', 'root', 0, plate_y)
    sk.slot('plate_glow', rg, 'glow', w=plate_w * 2.0, blend='additive', color='ffb45aff')
    sk.both(rg, 'scale', uniform(lambda t: seg(t, 1.0, 1.6, 0.2, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.1)))
    sk.both('plate_glow', 'alpha', lambda t: seg(t, 1.0, 1.4, 0.0, 0.8), lambda t: 0.8)
    pb = sk.bone('plate', 'root', 0, plate_y)
    ph_ = plate_w * ART['plate'].height / ART['plate'].width
    sk.slot('plate', pb, 'plate', w=plate_w)
    sk.bone('count', pb, 0, ph_ * (0.5 - PLATE_WIN_CY))
    sk.both(pb, 'scale', uniform(lambda t: pop(t, 1.0, 0.6, 0.0)),
            uniform(lambda t: 1 + 0.05 * pulse(t, 2.0, 0.0, 6)))
    sk.both('plate', 'alpha', lambda t: fade(t, 1.0, 0.2), lambda t: 1)

    # info chips: steel panels with violet glow
    for idx, (cx, cy, side) in enumerate(chips):
        c = sk.bone(f'chip{idx}', 'root', cx, cy)
        t0 = 1.5 + 0.15 * idx
        if variant == 'desk':
            pw, phh, panel = 440, 470, 'panel_bonus'
        else:
            pw, phh, panel = 720, 150, 'panel_bonus_mob'
        sk.slot(f'chip{idx}', c, panel, w=pw + 68)
        move(sk, c, lambda t, side=side, t0=t0: (seg(t, t0, t0 + 0.55, side * 300, 0, out_back), 0),
             lambda t, idx=idx: (0, bob(t, 5, IDLE, idx * 0.5)))
        sk.both(f'chip{idx}', 'alpha', lambda t, t0=t0: fade(t, t0, 0.25), lambda t: 1)
        tkey, dkey = ('t_chip_multi', 'd_chip_multi') if idx == 0 else ('t_chip_fs', 'd_chip_fs')
        ti, di = ART[tkey], ART[dkey]
        if variant == 'desk':
            t_w = min(ti.width * 0.9, pw - 50)
            t_pos, i_pos, d_pos = (0, phh / 2 - 66), (0, 8), (0, -phh / 2 + 76)
            d_w = min(di.width * 0.95, pw - 60)
            icon_s = 1.0
        else:
            t_w = min(ti.width * 0.72, 360)
            d_w = min(di.width * 0.8, 360)
            t_pos, d_pos, i_pos = (160, 30), (160, -30), (-180, 4)
            icon_s = 1.0
        tb = sk.bone(f'chip{idx}_t', c, *t_pos)
        sk.slot(f'chip{idx}_t', tb, tkey, w=t_w)
        db = sk.bone(f'chip{idx}_d', c, *d_pos)
        sk.slot(f'chip{idx}_d', db, dkey, w=d_w)
        sk.both(f'chip{idx}_t', 'alpha', lambda t, t0=t0: fade(t, t0 + 0.2), lambda t: 1)
        sk.both(f'chip{idx}_d', 'alpha', lambda t, t0=t0: fade(t, t0 + 0.3), lambda t: 1)
        ib = sk.bone(f'chip{idx}_icon', c, *i_pos)
        if variant == 'mob':
            if idx == 0:
                items = [(c, -114 + 76 * k, 0, 76) for k, c in enumerate(('x2', 'x3', 'x5', 'x7'))]
            else:
                items = [('scatter', -96 + 96 * k, 0, 92) for k in range(3)]
        elif idx == 0:
            items = [('x2', -70, 64, 126), ('x3', 70, 64, 126), ('x5', -70, -64, 126), ('x7', 70, -64, 126)]
        else:
            items = [('scatter', -128 + 128 * k, 0, 122) for k in range(3)]
        for j, (code, x, y, sz) in enumerate(items):
            b = sk.bone(f'chip{idx}_i{j}', ib, x * icon_s, y * icon_s)
            sk.slot(f'chip{idx}_i{j}', b, code, w=sz * icon_s)
            d = t0 + 0.35 + 0.1 * j
            sk.both(b, 'scale', uniform(lambda t, d=d: pop(t, d, 0.45, 0.0)),
                    uniform(lambda t, j=j: 1 + 0.12 * pulse(t, 2.0, j * 0.15, 6)))
            sk.both(b, 'rotate', lambda t: 0, lambda t, j=j: bob(t, 6, 2.0, j * 0.3))
            sk.both(f'chip{idx}_i{j}', 'alpha', lambda t, d=d: fade(t, d, 0.2), lambda t: 1)

    twinkles(sk, 'root', spots, seed=11, tint='f0d8ffff')
    sk.bone('tap', 'root', 0, tap_y)
    sk.write()


# --------------------------------------------------------------------------
# software preview: re-reads the written json + PMA atlas and renders frames

def _keys_at(rows, t, n):
    if not rows:
        return None
    def val(r):
        if n == 2:
            return (r.get('x', 0), r.get('y', 0))
        return (r.get('value', 0),)
    prev = rows[0]
    if t <= prev.get('time', 0):
        return val(prev)
    for r in rows[1:]:
        rt = r.get('time', 0)
        if t <= rt:
            pt = prev.get('time', 0)
            f = (t - pt) / max(1e-9, rt - pt)
            return tuple(a + (b - a) * f for a, b in zip(val(prev), val(r)))
        prev = r
    return val(prev)


def render_frame(data, regions, anim, t, scale=0.5, bg=None):
    W, H = int(data['skeleton']['width'] * scale), int(data['skeleton']['height'] * scale)
    canvas = np.zeros((H, W, 3), np.float32)
    if bg is not None:
        canvas[:] = np.asarray(bg.resize((W, H)).convert('RGB'), np.float32) / 255
    tl = data['animations'][anim]
    world = {}
    for b in data['bones']:
        bt = tl['bones'].get(b['name'], {})
        x, y = b.get('x', 0), b.get('y', 0)
        r, sx, sy = b.get('rotation', 0), b.get('scaleX', 1), b.get('scaleY', 1)
        v = _keys_at(bt.get('translate'), t, 2)
        if v:
            x, y = x + v[0], y + v[1]
        v = _keys_at(bt.get('rotate'), t, 1)
        if v:
            r += v[0]
        v = _keys_at(bt.get('scale'), t, 2)
        if v:
            sx, sy = sx * v[0], sy * v[1]
        rr = math.radians(r)
        la, lb, lc, ld = math.cos(rr) * sx, -math.sin(rr) * sy, math.sin(rr) * sx, math.cos(rr) * sy
        if 'parent' not in b:
            world[b['name']] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, px, py = world[b['parent']]
            world[b['name']] = (pa * la + pb * lc, pa * lb + pb * ld, pc * la + pd * lc, pc * lb + pd * ld,
                                pa * x + pb * y + px, pc * x + pd * y + py)
    atts = data['skins'][0]['attachments']
    for s in data['slots']:
        alpha = 1.0
        col = s.get('color', 'ffffffff')
        cr, cg, cb, ca = (int(col[i:i + 2], 16) / 255 for i in (0, 2, 4, 6))
        st = tl['slots'].get(s['name'], {})
        v = _keys_at(st.get('alpha'), t, 1)
        alpha = v[0] if v else ca
        if alpha <= 0.003:
            continue
        reg = s['attachment']
        att = atts[s['name']][reg]
        a, b_, c, d, wx, wy = world[s['bone']]
        img = regions[reg]
        iw, ih = img.size
        aw, ah = att['width'], att['height']
        ar = math.radians(att.get('rotation', 0))
        # image px (u,v) -> attachment local -> bone world -> canvas px
        # local = R(ar) * ((u/iw - .5)*aw, (.5 - v/ih)*ah) + (ax, ay)
        m_img = np.array([[aw / iw, 0, -aw / 2], [0, -ah / ih, ah / 2], [0, 0, 1]])
        m_rot = np.array([[math.cos(ar), -math.sin(ar), att['x']], [math.sin(ar), math.cos(ar), att['y']], [0, 0, 1]])
        m_bone = np.array([[a, b_, wx], [c, d, wy], [0, 0, 1]])
        m_can = np.array([[scale, 0, W / 2], [0, -scale, H / 2], [0, 0, 1]])
        M = m_can @ m_bone @ m_rot @ m_img
        corners = M @ np.array([[0, iw, iw, 0], [0, 0, ih, ih], [1, 1, 1, 1]])
        x0, x1 = int(max(0, math.floor(corners[0].min()))), int(min(W, math.ceil(corners[0].max())))
        y0, y1 = int(max(0, math.floor(corners[1].min()))), int(min(H, math.ceil(corners[1].max())))
        if x1 <= x0 or y1 <= y0:
            continue
        if abs(np.linalg.det(M[:2, :2])) < 1e-6:
            continue
        T = np.linalg.inv(M) @ np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]])
        warped = img.transform((x1 - x0, y1 - y0), Image.AFFINE, tuple(T[:2].ravel()), Image.BILINEAR)
        src = np.asarray(warped, np.float32) / 255  # premultiplied
        rgb = src[..., :3] * np.array([cr, cg, cb], np.float32) * alpha
        sa = src[..., 3:4] * alpha
        dst = canvas[y0:y1, x0:x1]
        if s.get('blend') == 'additive':
            canvas[y0:y1, x0:x1] = np.minimum(1, dst + rgb)
        else:
            canvas[y0:y1, x0:x1] = rgb + dst * (1 - sa)
    return Image.fromarray((np.clip(canvas, 0, 1) * 255).astype(np.uint8))


def load_skeleton(folder):
    data = json.load(open(os.path.join(folder, 'animation.json')))
    regions, page = {}, None
    lines_ = open(os.path.join(folder, 'animation.atlas')).read().split('\n')
    i = 0
    while i < len(lines_):
        ln = lines_[i].strip()
        if ln.endswith('.png'):
            page = Image.open(os.path.join(folder, ln)).convert('RGBA')
        elif ln and ':' not in ln:
            x, y, w, h = map(int, lines_[i + 1].split(':')[1].split(','))
            regions[ln] = page.crop((x, y, x + w, y + h))
            i += 1
        i += 1
    return data, regions


def bg_for(name):
    kind, variant = name.split('_')
    f = {'feature': 'bg_base', 'bonus': 'bg_bonus'}[kind] + ('_mob' if variant == 'mob' else '') + '.jpg'
    im = Image.open(os.path.join(ART_DIR, 'img', f)).convert('RGB')
    W, H = DESK if variant == 'desk' else MOB
    k = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)))
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    # same darkening as screens.js (.mf-screen__shade)
    shade = Image.new('RGB', im.size, (8, 4, 14))
    return Image.blend(im, shade, 0.55)


def preview(name, out_dir):
    data, regions = load_skeleton(os.path.join(OUT, name))
    bg = bg_for(name)
    times = [('intro', t) for t in (0.3, 0.7, 1.1, 1.6, 2.2, 3.0)] + [('idle', t) for t in (0.3, 0.8, 1.2, 2.0, 3.0, 3.5)]
    sc = 0.5 if name.endswith('desk') else 0.42
    frames = [(a, t, render_frame(data, regions, a, t, sc, bg)) for a, t in times]
    fw, fh = frames[0][2].size
    cols = 3 if name.endswith('desk') else 4
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (fw + 8), rows * (fh + 28)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for k, (a, t, fr) in enumerate(frames):
        x, y = (k % cols) * (fw + 8), (k // cols) * (fh + 28)
        sheet.paste(fr, (x, y + 24))
        d.text((x + 6, y + 4), f'{name} {a} t={t:.1f}', fill=(255, 255, 0))
    os.makedirs(out_dir, exist_ok=True)
    sheet.save(os.path.join(out_dir, f'{name}.jpg'), quality=82)
    # one full-res final frame too (idle t=0 == end of intro)
    render_frame(data, regions, 'idle', 1.6, 1.0, bg).save(os.path.join(out_dir, f'{name}_full.jpg'), quality=85)


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
    if PREVIEW:
        for n in ('feature_desk', 'feature_mob', 'bonus_desk', 'bonus_mob'):
            preview(n, PREVIEW)
