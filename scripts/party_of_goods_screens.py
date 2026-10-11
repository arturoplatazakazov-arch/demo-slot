"""Party Gods — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Four skeletons: feature/bonus x desk (1932x940) / mob (780x1416), each with
`intro` (3s) -> `idle` (4s seamless loop), authored on the game's design
canvas (origin = canvas centre, 1 unit = 1 design px, y up). The game's
background is NOT in the skeleton — the page shows its own bg jpg under the
canvas with object-fit: cover, so any aspect ratio is covered.

All art is the designer's: smart-object sources pulled out of
grece_5x6_slot.psb (logo, gods, symbols, laurel medallion, crimson plate,
theatre frame, doves, coin, flare), plus generated fx (glow, rays, petals,
sparks) and text rendered with the game's own fonts.

Bonus screen: bone `count` sits at the centre of the medallion's disc — the
page draws the real spin count there in the DOM, glued to the bone.

Usage:
  python scripts/party_of_goods_screens.py <so_dir> <fonts_dir> <out_dir>

so_dir    — PNGs of the PSB's smart objects, named by their layer path
            (Final__icons__zeus.png, Popups__bonus_spins_win__bg.png, ...)
fonts_dir — cinzel.ttf, luckiest.ttf (front/fonts woff2 -> ttf)
out_dir   — front/img/party-of-goods/screens
"""

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, linear, out_back, out_cubic, pulse, rays, seg,
    soft_glow, spark, text_img, trim, wave,
)

SO, FONTS, OUT = sys.argv[1:4]
INTRO, IDLE = 3.0, 4.0


def load(name):
    return trim(Image.open(os.path.join(SO, name + '.png')).convert('RGBA'))


def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)
    if weight:
        f.set_variation_by_axes([weight])
    return f


GOLD = [(0, hexc('fff7cf')), (0.45, hexc('ffd34d')), (1, hexc('c26a12'))]
CREAM = [(0, hexc('fffaf0')), (1, hexc('ffd9a8'))]
WINE = '4a0714'


def petal(w=40, h=28, col='d81c4a', hi='ff7f9e'):
    k = 4
    im = Image.new('RGBA', (w * k, h * k))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, w * k - 1, h * k - 1], fill=hexc(col))
    d.ellipse([w * k * 0.15, h * k * 0.2, w * k * 0.62, h * k * 0.62], fill=hexc(hi, 200))
    d.polygon([(w * k - 1, h * k / 2 - 16), (w * k - 40, h * k / 2), (w * k - 1, h * k / 2 + 16)], fill=(0, 0, 0, 0))
    return im.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.4))


ART = {
    'logo': load('Final__Logo__Layer_39'),
    'zeus': load('Final__icons__zeus'),
    'afrodita': load('Final__icons__afrodita'),
    'apollo': load('Final__icons__cupidonn'),
    'key': load('Final__icons__Scatter__Layer_42'),
    'bolt': load('Final__icons__bomb_flash'),
    'x2': load('Final__icons__x2'),
    'x3': load('Final__icons__x3'),
    'x5': load('Final__icons__x5'),
    'x7': load('Final__icons__x7'),
    'medal': load('Popups__bonus_spins_win__circle'),
    'plate': load('Popups__Buy_Free_Spins__input__input'),
    'theatre': load('Popups__bonus_spins_win__bg'),
    'title': load('Popups__bonus_spins_win__bonus_spins_Win'),
    'doves': load('Final__frame__pigin2'),
    'coin': load('Popups__Big_win__coin__coin'),
    'flare': load('Popups__Big_win__rays_copy__rays1'),
    'glow': soft_glow(256),
    'spark': spark(),
    'rays': rays(1000, n=18, width=0.38),
    'petal': petal(),
    'petal2': petal(col='f05a86', hi='ffc2d3'),
}
for k in ('logo', 'zeus', 'afrodita', 'apollo', 'key', 'bolt', 'x2', 'x3', 'x5', 'x7', 'theatre', 'title'):
    ART[k + '_fl'] = flash_of(ART[k], 0.85)

# The laurel medallion's red disc is not centred on the image: centre sits
# 0.071 x width above the image centre, diameter 0.62 x width.
MEDAL_DISC_DY, MEDAL_DISC_D = 0.071, 0.62
# The crimson plate's inner window: centre 0.055 x height above image centre.
PLATE_DY = 0.055


# Blurry generated fx look the same at a fraction of the resolution.
FX_RES = {'rays': 0.5, 'glow': 0.6, 'flare': 0.8}


def new_skel(name, W, H, desk):
    sk = Skel(name, W, H, 1.3 if desk else 1.5, OUT, INTRO, IDLE)
    sk.res_of = FX_RES
    return sk


def add(sk, *keys):
    for k in keys:
        sk.image(k, ART[k])


def fade_in(t0, dur=0.2):
    return lambda t: seg(t, t0, t0 + dur, 0, 1, linear)


def one(_t):
    return 1


# --------------------------------------------------------------------------
# reusable pieces

def logo(sk, x, y, w, t0=0.35):
    b = sk.bone('logo_b', 'main', x, y)
    h = w * ART['logo'].height / ART['logo'].width
    sk.slot('logo_glow', b, 'glow', w=w * 1.7, h=h * 1.9, blend='additive', color='ffb23c99')
    sk.slot('logo', b, 'logo', w=w)
    sk.slot('logo_fl', b, 'logo_fl', w=w, blend='additive')
    sk.both(b, 'translate', lambda t: (x, y + seg(t, t0, t0 + 0.6, 160, 0, out_back)), lambda t: (x, y))
    sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.6, 1.6, 1, out_back),) * 2,
            lambda t: (breathe(t, 2, 0.025),) * 2)
    sk.both('logo', 'alpha', fade_in(t0, 0.15), one)
    sk.both('logo_fl', 'alpha', lambda t: 0 if t < t0 + 0.5 else seg(t, t0 + 0.5, t0 + 1.0, 0.9, 0),
            lambda t: 0.3 * pulse(t, IDLE, 0.05, 10))
    sk.both('logo_glow', 'alpha', lambda t: seg(t, t0 + 0.4, t0 + 0.9, 0, 1),
            lambda t: 0.8 + 0.2 * math.cos(2 * math.pi * t / 2))
    sparks(sk, b, 'lspk', t0 + 0.5, 12, w * 0.6, 'ffe08aff', seed=5)


def doves(sk, x, y, w, t0=0.6):
    """The designer's dove pair, one copy each side (right copy mirrored),
    gliding in from off-screen, then hovering."""
    for side in (-1, 1):
        name = f'doves{"L" if side < 0 else "R"}'
        b = sk.bone(name + '_b', 'main', side * x, y, sx=-side)
        sk.slot(name, b, 'doves', w=w)
        ph = 0.0 if side < 0 else 0.5
        sk.both(b, 'translate',
                lambda t, s=side: (s * (x + seg(t, t0, t0 + 0.9, 420, 0, out_cubic)),
                                   y + seg(t, t0, t0 + 0.9, 120, 0, out_cubic)),
                lambda t, s=side, ph=ph: (s * (x + 6 * wave(t, IDLE, ph + 0.25)), y + 12 * wave(t, IDLE / 2, ph)))
        sk.both(b, 'rotate', lambda t, s=side: s * seg(t, t0, t0 + 0.9, -18, 0),
                lambda t, s=side, ph=ph: s * 3 * wave(t, IDLE / 2, ph + 0.2))
        sk.both(name, 'alpha', fade_in(t0, 0.3), one)


def god(sk, name, region, x, y, w, from_x, t0=0.15, phase=0.0):
    """A god medallion floating beside the content, with a gold halo."""
    b = sk.bone(name + '_b', 'main', x, y)
    sk.slot(name + '_halo', b, 'glow', w=w * 1.55, blend='additive', color='ffbf4fb0')
    sk.slot(name, b, region, w=w)
    sk.slot(name + '_fl', b, region + '_fl', w=w, blend='additive')
    sk.both(b, 'translate', lambda t: (x + seg(t, t0, t0 + 0.75, from_x, 0, out_back), y),
            lambda t: (x, y + 14 * wave(t, IDLE, phase)))
    sk.both(b, 'rotate', lambda t: seg(t, t0, t0 + 0.75, 25 if from_x < 0 else -25, 0, out_back),
            lambda t: 2.5 * wave(t, IDLE, phase + 0.25))
    sk.both(b, 'scale', lambda t: (1, 1), lambda t: (breathe(t, IDLE / 2, 0.02),) * 2)
    sk.both(name, 'alpha', fade_in(t0, 0.25), one)
    sk.both(name + '_halo', 'alpha', lambda t: seg(t, t0 + 0.3, t0 + 0.8, 0, 0.85),
            lambda t: 0.7 + 0.15 * math.cos(2 * math.pi * t / 2))
    sk.both(name + '_fl', 'alpha', lambda t: 0 if t < t0 + 0.6 else seg(t, t0 + 0.6, t0 + 1.0, 0.7, 0),
            lambda t: 0.35 * pulse(t, IDLE, 0.4 + phase, 12))


def sparks(sk, parent, prefix, t0, n, radius, color, seed):
    rnd = random.Random(seed)
    for i in range(n):
        ang = 360 * i / n + rnd.uniform(-12, 12)
        r = radius * rnd.uniform(0.75, 1.2)
        b = sk.bone(f'{prefix}{i}', parent, rot=ang)
        sk.slot(f'{prefix}{i}', b, 'spark', w=40, blend='additive', color=color)
        rad = math.radians(ang)
        dur = rnd.uniform(0.4, 0.6)

        def tr(t, rad=rad, r=r, dur=dur):
            k = seg(t, t0, t0 + dur, 0, 1, out_cubic)
            return (math.cos(rad) * r * k, math.sin(rad) * r * k)

        sk.both(b, 'translate', tr, lambda t, tr=tr: tr(INTRO))
        sk.both(b, 'scale', lambda t, dur=dur: (seg(t, t0, t0 + dur, 2.2, 0.6), 1), lambda t: (0.6, 1))
        sk.both(f'{prefix}{i}', 'alpha',
                lambda t, dur=dur: 0 if t < t0 else seg(t, t0 + dur * 0.35, t0 + dur, 1, 0, linear),
                lambda t: 0)


def petals(sk, count, area, seed, size=1.0, intro_from=1.0):
    """Rose petals drifting down, seamless over the idle loop."""
    rnd = random.Random(seed)
    x0, x1, ytop, ybot = area
    for i in range(count):
        b = sk.bone(f'petal{i}', 'main')
        sc = size * rnd.uniform(0.6, 1.2)
        sk.slot(f'petal{i}', b, 'petal' if i % 3 else 'petal2', w=40 * sc)
        px = rnd.uniform(x0, x1)
        drift = rnd.uniform(-140, 80)
        sway = rnd.uniform(18, 46)
        ph = i / count + rnd.uniform(-0.04, 0.04)
        spin = rnd.choice([-1, 1]) * rnd.uniform(160, 340)

        def u_of(tau, ph=ph):
            return ((tau / IDLE) + ph) % 1.0

        def pos(tau, px=px, drift=drift, sway=sway, ph=ph):
            u = u_of(tau)
            return (px + drift * u + sway * math.sin(2 * math.pi * (u * 2 + ph)), ytop + (ybot - ytop) * u)

        def alpha(tau):
            u = u_of(tau)
            return clamp(u / 0.08) * clamp((1 - u) / 0.1) * 0.95

        def rot(tau, spin=spin):
            return spin * u_of(tau)

        def flip(tau, ph=ph):
            return (1, 0.35 + 0.65 * abs(math.cos(2 * math.pi * (u_of(tau) * 3 + ph))))

        env = lambda t: clamp((t - intro_from) / 0.8)
        sk.both(b, 'translate', lambda t, f=pos: f(t - INTRO), lambda t, f=pos: f(t))
        sk.both(b, 'rotate', lambda t, f=rot: f(t - INTRO), lambda t, f=rot: f(t))
        sk.both(b, 'scale', lambda t, f=flip: f(t - INTRO), lambda t, f=flip: f(t))
        sk.both(f'petal{i}', 'alpha', lambda t, a=alpha: a(t - INTRO) * env(t), lambda t, a=alpha: a(t))


def twinkles(sk, spots, seed, t_on=2.2):
    """Designer's star flare blinking at fixed spots."""
    rnd = random.Random(seed)
    for i, (x, y, s) in enumerate(spots):
        b = sk.bone(f'tw{i}', 'main', x, y)
        sk.slot(f'tw{i}', b, 'flare', w=150 * s, blend='additive', color='ffe9b0ff')
        ph = rnd.random()

        def tw(t, ph=ph):
            return math.sin(math.pi * (((t / IDLE) * 2 + ph) % 1.0)) ** 6

        sk.both(b, 'scale', lambda t, f=tw: ((0.25 + 0.75 * f(t - INTRO + IDLE)),) * 2,
                lambda t, f=tw: ((0.25 + 0.75 * f(t)),) * 2)
        sk.both(b, 'rotate', lambda t: 45 * (t - INTRO) / IDLE, lambda t: 45 * t / IDLE)
        sk.both(f'tw{i}', 'alpha', lambda t, f=tw: clamp((t - t_on) / 0.4) * f(t - INTRO + IDLE),
                lambda t, f=tw: f(t))


def sunburst(sk, x, y, size, t0, color='ffc24a'):
    b = sk.bone('rays_b', 'main', x, y)
    sk.slot('halo', b, 'glow', w=size * 0.9, blend='additive', color=color + 'c0')
    sk.slot('rays', b, 'rays', w=size, blend='additive', color=color + '80')
    sk.slot('rays2', b, 'rays', w=size * 0.75, blend='additive', color='ff6a8a50')
    sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.6, 0.2, 1, out_back),) * 2,
            lambda t: (breathe(t, 2, 0.04),) * 2)
    for s in ('halo', 'rays', 'rays2'):
        sk.both(s, 'alpha', lambda t: seg(t, t0, t0 + 0.5, 0, 1, linear), one)
    # one 18-fold step per loop -> seamless
    sk.anim('intro', b, 'rotate', lambda t: 20 * (t - INTRO) / IDLE)
    sk.anim('idle', b, 'rotate', lambda t: 20 * t / IDLE)
    return b


def tap_text(sk, text, x, y, h, t0=2.3):
    im = text_img(text, font('cinzel', 80, 900), GOLD, stroke=WINE, stroke_w=7, glow='ff7a2a', glow_r=12, track=6)
    sk.image('t_tap', im)
    b = sk.bone('tap_b', 'main', x, y)
    sk.slot('tap', b, 't_tap', h=h)
    sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.45, 0.6, 1, out_back),) * 2,
            lambda t: (breathe(t, 2, 0.04),) * 2)
    sk.both('tap', 'alpha', fade_in(t0, 0.3), lambda t: 0.8 + 0.2 * math.cos(2 * math.pi * t / 2))


# --------------------------------------------------------------------------
# FEATURE screen

CARDS = [
    # icon(s), title, sub-line
    (['key'], 'FREE SPINS', '3+ SCATTERS · UP TO 20 SPINS'),
    (['x2', 'x3', 'x5', 'x7'], 'MULTIPLIERS', 'x2 x3 x5 x7 ADD UP ON A WIN'),
    (['bolt'], 'ZEUS BOLT', 'CLEARS ITS ROW & COLUMN'),
]
ICON_SIZE = {'key': ('h', 0.9), 'bolt': ('h', 0.95), 'x2': ('w', 0.8), 'x3': ('w', 0.8),
             'x5': ('w', 0.82), 'x7': ('w', 0.84)}


def card(sk, i, cx, cy, L):
    """Laurel medallion with the feature icon + crimson plate with the title +
    sub-line under it. Desk: stacked vertically. Mob: medallion left, text right."""
    icons, title, sub = CARDS[i]
    tc = 1.0 + 0.25 * i
    mw = L['medal_w']
    cb = sk.bone(f'card{i}', 'main', cx, cy)
    mb = sk.bone(f'medal{i}', cb, *L['medal_at'])
    disc_y = MEDAL_DISC_DY * mw
    sk.slot(f'mglow{i}', mb, 'glow', w=mw * 1.35, y=disc_y, blend='additive', color='ff9f3a90')
    sk.slot(f'medal{i}', mb, 'medal', w=mw)
    ib = sk.bone(f'icon{i}', mb, 0, disc_y)
    disc = MEDAL_DISC_D * mw
    for k, ic in enumerate(icons):
        axis, f = ICON_SIZE[ic]
        kw = {'w': disc * f} if axis == 'w' else {'h': disc * f}
        sk.slot(f'icon{i}_{k}', ib, ic, **kw)
        sk.slot(f'ifl{i}_{k}', ib, ic + '_fl', blend='additive', **kw)
    sk.slot(f'mfl{i}', mb, 'glow', w=disc * 1.1, y=disc_y, blend='additive', color='fff2c8ff')

    pb = sk.bone(f'plate{i}', cb, *L['plate_at'])
    pw = L['plate_w']
    ph = pw * ART['plate'].height / ART['plate'].width
    sk.slot(f'plate{i}', pb, 'plate', w=pw)
    tim = text_img(title, font('luckiest', 96), GOLD, stroke=WINE, stroke_w=8, shadow='000000')
    sk.image(f't_cap{i}', tim)
    cap_h = ph * 0.42
    cap_w = min(pw * 0.66, cap_h * tim.width / tim.height)
    sk.slot(f'cap{i}', pb, f't_cap{i}', w=cap_w, y=ph * PLATE_DY + 2)
    sim = text_img(sub, font('cinzel', 64, 800), CREAM, stroke=WINE, stroke_w=6, glow='000000', glow_r=6)
    sk.image(f't_sub{i}', sim)
    sb = sk.bone(f'sub{i}', cb, *L['sub_at'])
    sh = L['sub_h']
    sk.slot(f'sub{i}', sb, f't_sub{i}', w=min(L['sub_w'], sh * sim.width / sim.height))

    # intro: medallion spins in, icon flashes, plate unrolls, sub fades
    sk.both(mb, 'scale', lambda t: (seg(t, tc, tc + 0.5, 0.1, 1, out_back),) * 2, lambda t: (1, 1))
    sk.both(mb, 'rotate', lambda t: seg(t, tc, tc + 0.5, -200, 0, out_cubic), lambda t: 0)
    sk.both(f'medal{i}', 'alpha', fade_in(tc, 0.15), one)
    sk.both(f'mglow{i}', 'alpha', lambda t: seg(t, tc + 0.3, tc + 0.7, 0, 1),
            lambda t: 0.75 + 0.25 * math.cos(2 * math.pi * t / 2))
    sk.both(f'mfl{i}', 'alpha', lambda t: 0 if t < tc + 0.35 else seg(t, tc + 0.35, tc + 0.8, 0.9, 0),
            lambda t: 0.55 * pulse(t, IDLE, 0.12 + i * 0.22, 14))
    # idle: card gently bobs; each one takes its turn to pop (staggered)
    bob = L.get('bob', 6)
    sk.both(cb, 'translate', lambda t: (cx, cy), lambda t: (cx, cy + bob * wave(t, IDLE, i / 3)))
    turn = 0.12 + i * 0.22

    def icon_scale(t):
        return 1 + 0.12 * pulse(t, IDLE, turn, 10)

    sk.both(ib, 'scale', lambda t: (seg(t, tc + 0.25, tc + 0.6, 0.3, 1, out_back),) * 2,
            lambda t: (icon_scale(t),) * 2)
    if icons == ['bolt']:
        sk.both(ib, 'rotate', lambda t: 0, lambda t: 4 * wave(t, IDLE / 2))
    if len(icons) == 1:
        sk.both(f'icon{i}_0', 'alpha', fade_in(tc + 0.25, 0.1), one)
        sk.both(f'ifl{i}_0', 'alpha', lambda t: 0 if t < tc + 0.3 else seg(t, tc + 0.3, tc + 0.7, 1, 0),
                lambda t: 0.6 * pulse(t, IDLE, turn, 10))
    else:
        # multiplier cycle: x2 -> x3 -> x5 -> x7, one per second, white flash on each swap
        n = len(icons)
        step = IDLE / n

        def vis(t, k):
            return 1 if int((t % IDLE) // step) == k else 0

        def swap_flash(t, k):
            dt = (t % IDLE) - k * step
            return clamp(1 - dt / 0.25) if 0 <= dt < 0.25 else 0

        for k in range(n):
            sk.both(f'icon{i}_{k}', 'alpha',
                    (lambda t: fade_in(tc + 0.25, 0.1)(t)) if k == 0 else (lambda t: 0),
                    lambda t, k=k: vis(t, k))
            sk.both(f'ifl{i}_{k}', 'alpha',
                    (lambda t: 0 if t < tc + 0.3 else seg(t, tc + 0.3, tc + 0.7, 1, 0)) if k == 0 else (lambda t: 0),
                    lambda t, k=k: 0.8 * swap_flash(t, k) * vis(t, k))
        sk.anim('idle', ib, 'scale', lambda t: (1 + 0.18 * clamp(1 - ((t % step) / 0.3)) ** 2,) * 2)
    sk.both(pb, 'scale', lambda t: (seg(t, tc + 0.3, tc + 0.65, 0.2, 1, out_back), seg(t, tc + 0.3, tc + 0.5, 0.6, 1)),
            lambda t: (1, 1))
    for s in (f'plate{i}', f'cap{i}'):
        sk.both(s, 'alpha', fade_in(tc + 0.3, 0.12), one)
    sk.both(f'sub{i}', 'alpha', fade_in(tc + 0.55, 0.3), one)
    sparks(sk, ib, f'spk{i}_', tc + 0.3, 10, mw * 0.62, ['ffd36aff', 'ff8fb0ff', 'fff2c8ff'][i], seed=10 + i)


def feature(variant):
    desk = variant == 'desk'
    W, H = (1932, 940) if desk else (780, 1416)
    sk = new_skel(f'feature_{variant}', W, H, desk)
    add(sk, 'logo', 'logo_fl', 'glow', 'spark', 'rays', 'flare', 'petal', 'petal2', 'doves', 'medal', 'plate',
        'key', 'bolt', 'x2', 'x3', 'x5', 'x7', 'key_fl', 'bolt_fl', 'x2_fl', 'x3_fl', 'x5_fl', 'x7_fl')
    sk.bone('main')
    if desk:
        add(sk, 'zeus', 'afrodita', 'zeus_fl', 'afrodita_fl')
        L = dict(logo=(0, 318, 440), rays=(0, 318, 900), tag=(0, 150, 34), doves=(330, 330, 210),
                 cards=[(-400, -60), (0, -60), (400, -60)],
                 medal_w=270, medal_at=(0, 50), plate_w=340, plate_at=(0, -112), sub_at=(0, -182), sub_h=30, sub_w=390,
                 tap=(0, -400, 52), petal_area=(-1000, 1000, 520, -520),
                 twinkles=[(-560, 330, 0.7), (575, 260, 0.55), (-240, 430, 0.45), (250, 420, 0.5),
                           (-830, -320, 0.6), (830, -300, 0.6)])
        god(sk, 'zeus', 'zeus', -760, -10, 320, from_x=-500, t0=0.15)
        god(sk, 'afrodita', 'afrodita', 760, -10, 320, from_x=500, t0=0.25, phase=0.5)
    else:
        L = dict(logo=(0, 545, 540), rays=(0, 545, 900), tag=(0, 338, 30), doves=(300, 400, 170),
                 cards=[(0, 140), (0, -125), (0, -390)],
                 medal_w=250, medal_at=(-215, 0), plate_w=420, plate_at=(105, 28), sub_at=(105, -56), sub_h=28,
                 sub_w=430, bob=4,
                 tap=(0, -590, 54), petal_area=(-430, 430, 760, -760),
                 twinkles=[(-300, 660, 0.55), (300, 600, 0.5), (-330, 260, 0.4), (340, 300, 0.45),
                           (-320, -520, 0.45), (320, -560, 0.5)])

    sunburst(sk, *L['rays'], t0=0.3)
    doves(sk, *L['doves'], t0=0.55)
    logo(sk, *L['logo'], t0=0.35)

    tag = text_img('CASCADING WINS  ·  8+ ANYWHERE PAYS', font('cinzel', 64, 900), GOLD, stroke=WINE, stroke_w=6,
                   glow='000000', glow_r=8, track=3)
    sk.image('t_tag', tag)
    tb = sk.bone('tag_b', 'main', L['tag'][0], L['tag'][1])
    tag_h = L['tag'][2]
    sk.slot('tag', tb, 't_tag', w=min(W * 0.9, tag_h * tag.width / tag.height))
    sk.both(tb, 'scale', lambda t: (seg(t, 0.85, 1.25, 0.5, 1, out_back), 1), lambda t: (1, 1))
    sk.both('tag', 'alpha', fade_in(0.85, 0.3), one)

    for i, (cx, cy) in enumerate(L['cards']):
        card(sk, i, cx, cy, L)

    petals(sk, 14 if desk else 10, L['petal_area'], seed=7, size=1.0 if desk else 0.9)
    twinkles(sk, L['twinkles'], seed=3)
    tap_text(sk, 'TAP TO CONTINUE', L['tap'][0], L['tap'][1], L['tap'][2])
    sk.write()


# --------------------------------------------------------------------------
# BONUS screen

def bonus(variant):
    desk = variant == 'desk'
    W, H = (1932, 940) if desk else (780, 1416)
    sk = new_skel(f'bonus_{variant}', W, H, desk)
    add(sk, 'logo', 'logo_fl', 'glow', 'spark', 'rays', 'flare', 'petal', 'petal2', 'doves', 'medal', 'coin',
        'theatre', 'theatre_fl', 'title', 'title_fl', 'apollo', 'afrodita', 'apollo_fl', 'afrodita_fl')
    sk.bone('main')
    if desk:
        L = dict(logo=(0, 382, 250), theatre=(0, -40, 650), gods=(-650, -60, 300), doves=(470, 300, 200),
                 tap=(0, -412, 50), petal_area=(-1000, 1000, 520, -520),
                 coins=[(-410, 170, 0.5), (-460, -40, 0.62), (-400, -250, 0.48), (420, 190, 0.55),
                        (470, -20, 0.48), (410, -240, 0.6), (-300, 330, 0.36), (300, 330, 0.38)],
                 twinkles=[(-560, 330, 0.7), (575, 260, 0.55), (-830, -320, 0.6), (830, -300, 0.6),
                           (-180, 260, 0.4), (200, -330, 0.45)])
    else:
        L = dict(logo=(0, 592, 380), theatre=(0, 95, 720), gods=(-205, -432, 270), doves=(300, 440, 160),
                 tap=(0, -615, 54), petal_area=(-430, 430, 760, -760),
                 coins=[(-320, 330, 0.42), (-330, 60, 0.5), (-310, -180, 0.4), (320, 300, 0.46),
                        (335, 40, 0.4), (315, -200, 0.5)],
                 twinkles=[(-300, 660, 0.55), (300, 640, 0.5), (-320, -300, 0.4), (330, -260, 0.45),
                           (-60, -560, 0.4)])

    tx, ty, th = L['theatre']
    k = th / 634  # designer's popup: frame 664x634, title & medallion placed relative to it
    title_y, title_w = ty + 108 * k, 285 * k
    medal_y, medal_w = ty - 94 * k, 285 * k

    sunburst(sk, tx, ty + 30 * k, (1000 if desk else 900), t0=0.25)

    gx, gy, gw = L['gods']
    god(sk, 'apollo', 'apollo', gx, gy, gw, from_x=-480, t0=0.2)
    god(sk, 'afrodita', 'afrodita', -gx, gy, gw, from_x=480, t0=0.3, phase=0.5)
    doves(sk, *L['doves'], t0=0.7)

    # coins burst out of the medallion and hover (behind the theatre)
    for i, (cx, cy, s) in enumerate(L['coins']):
        b = sk.bone(f'coin{i}', 'main', cx, cy)
        sk.slot(f'coin{i}', b, 'coin', w=170 * s)
        t0 = 1.45 + 0.04 * i
        sk.both(b, 'translate',
                lambda t, cx=cx, cy=cy, t0=t0: (seg(t, t0, t0 + 0.65, tx, cx), seg(t, t0, t0 + 0.65, medal_y, cy)),
                lambda t, cx=cx, cy=cy, i=i: (cx, cy + 10 * wave(t, IDLE / 2, i * 0.17)))
        sk.both(b, 'rotate', lambda t, i=i, t0=t0: seg(t, t0, t0 + 0.65, 260 * (1 if i % 2 else -1), 0),
                lambda t, i=i: 10 * wave(t, IDLE, i * 0.31))
        sk.both(b, 'scale', lambda t, t0=t0: (seg(t, t0, t0 + 0.65, 0.2, 1),) * 2,
                lambda t, i=i: (math.cos(2 * math.pi * (t / IDLE * 2 + i * 0.13)) * 0.25 + 0.85, 1))
        sk.both(f'coin{i}', 'alpha', fade_in(t0, 0.1), one)

    # the theatre (curtained arch) rises in
    fb = sk.bone('theatre_b', 'main', tx, ty)
    sk.slot('theatre', fb, 'theatre', h=th)
    sk.slot('theatre_fl', fb, 'theatre_fl', h=th, blend='additive')
    sk.both(fb, 'translate', lambda t: (tx, ty + seg(t, 0.55, 1.15, -300, 0, out_back)),
            lambda t: (tx, ty + 4 * wave(t, IDLE / 2)))
    sk.both(fb, 'scale', lambda t: (seg(t, 0.55, 1.15, 0.5, 1, out_back),) * 2, lambda t: (1, 1))
    sk.both('theatre', 'alpha', fade_in(0.55, 0.15), one)
    sk.both('theatre_fl', 'alpha', lambda t: 0 if t < 1.0 else seg(t, 1.0, 1.4, 0.55, 0), lambda t: 0)

    # "BONUS SPINS WIN" title stamps in
    tb = sk.bone('title_b', fb, 0, title_y - ty)
    sk.slot('title_glow', tb, 'glow', w=title_w * 1.6, blend='additive', color='ffb648a0')
    sk.slot('title', tb, 'title', w=title_w)
    sk.slot('title_fl', tb, 'title_fl', w=title_w, blend='additive')
    sk.both(tb, 'scale', lambda t: (seg(t, 1.15, 1.5, 2.4, 1, out_back),) * 2,
            lambda t: (breathe(t, 1, 0.035),) * 2)
    sk.both('title', 'alpha', fade_in(1.15, 0.1), one)
    sk.both('title_fl', 'alpha', lambda t: 0 if t < 1.4 else seg(t, 1.4, 1.8, 1, 0),
            lambda t: 0.35 * pulse(t, IDLE, 0.1, 12))
    sk.both('title_glow', 'alpha', lambda t: seg(t, 1.35, 1.7, 0, 1),
            lambda t: 0.75 + 0.25 * math.cos(2 * math.pi * t / 1))
    sparks(sk, tb, 'tspk', 1.4, 14, title_w * 0.85, 'ffd36aff', seed=31)

    # laurel medallion holding the spin count (DOM draws the number over bone "count")
    mb = sk.bone('medal_b', fb, 0, medal_y - ty)
    disc_y = MEDAL_DISC_DY * medal_w
    sk.slot('medal_glow', mb, 'glow', w=medal_w * 1.4, y=disc_y, blend='additive', color='ff9f3aa0')
    sk.slot('medal', mb, 'medal', w=medal_w)
    sk.slot('medal_fl', mb, 'glow', w=MEDAL_DISC_D * medal_w * 1.1, y=disc_y, blend='additive', color='fff2c8ff')
    sk.bone('count', mb, 0, disc_y)
    sk.both(mb, 'scale', lambda t: (seg(t, 1.3, 1.75, 0.1, 1, out_back),) * 2,
            lambda t: (breathe(t, 1, 0.025),) * 2)
    sk.both(mb, 'rotate', lambda t: seg(t, 1.3, 1.75, 180, 0, out_cubic), lambda t: 0)
    sk.both('medal', 'alpha', fade_in(1.3, 0.12), one)
    sk.both('medal_glow', 'alpha', lambda t: seg(t, 1.6, 2.0, 0, 1),
            lambda t: 0.7 + 0.3 * math.cos(2 * math.pi * t / 1))
    sk.both('medal_fl', 'alpha', lambda t: 0 if t < 1.75 else seg(t, 1.75, 2.2, 1, 0),
            lambda t: 0.4 * pulse(t, 1, 0.0, 10))
    sparks(sk, mb, 'mspk', 1.8, 12, medal_w * 0.75, 'ff9fb8ff', seed=41)

    logo(sk, *L['logo'], t0=0.4)
    petals(sk, 16 if desk else 12, L['petal_area'], seed=17, size=1.0 if desk else 0.9, intro_from=0.6)
    twinkles(sk, L['twinkles'], seed=9)
    tap_text(sk, 'TAP TO START', L['tap'][0], L['tap'][1], L['tap'][2])
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        feature(v)
        bonus(v)
