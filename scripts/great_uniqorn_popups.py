"""Spine popups for Great Uniqorn — authored in code on scripts/spine_screen_kit.

One skeleton per popup and layout (BIG/EPIC/MEGA WIN, FREE SPINS WIN, FREE
SPINS / BONUS SPINS TOTAL WIN; `desk` and `mob`), all on the designer's popup
frame from the Figma mockup (section pop-ap, 780x1416, origin = frame centre,
1 unit = 1 mockup px, y up). Art is the designer's own layers
(front/img/great-uniqorn/src/popup_layers, exported 1x from Figma), every
main layer placed exactly where the mockup has it.

Two kinds of layers, as the product asked:

  main        hero, title, win plate (FREE SPINS WIN: the round badge) — they
              carry the popup: rays + flash behind, the hero jumps in, the
              title slams down, the plate pops; then a calm breathing loop.
  background  confetti, ribbons, bills, coins, FS tickets — they give the
              scene its depth: a burst out of the title on the intro, then an
              endless rain in three depth bands. Far = small, blurred, dimmed,
              half transparent, slow; near = big, softly blurred, fast, in
              front of everything. The mid band is the plain art.

Clips: `intro` (1.2s) -> `idle` (6s, seamless). Every rain particle's period
divides the idle length and its fall wraps while it is off screen and fully
transparent, so the loop never pops. `desk` spreads the rain over the whole
desktop screen (the popup frame there is ~1/3 of the width); `mob` keeps it
on the phone-wide frame.

The win amount is NOT in the skeleton: it is DOM text the game lays over the
plate (front/js/great-uniqorn/slot.js), so the plate stays still in `idle`.

    python3 scripts/great_uniqorn_popups.py
"""

import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, flash_of, in_out_sine, lerp, out_back, out_cubic, rays, seg, soft_glow, trim, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'front/img/great-uniqorn/src/popup_layers')
OUT = os.path.join(ROOT, 'front/img/great-uniqorn/popups')

FW, FH = 780, 1416
INTRO, IDLE = 1.2, 6.0


def X(fx):
    return fx - FW / 2


def Y(fy):
    return FH / 2 - fy


def load(name):
    return Image.open(os.path.join(SRC, f'{name}.png')).convert('RGBA')


def gold(im):
    """White ribbon -> gold ribbon: keep the shading, map it onto a gold ramp."""
    a = im.getchannel('A')
    g = ImageOps.grayscale(im.convert('RGB'))
    g = ImageEnhance.Contrast(g).enhance(1.25)
    out = ImageOps.colorize(g, black=(92, 52, 6), mid=(232, 168, 40), white=(255, 240, 170)).convert('RGBA')
    out.putalpha(a)
    return out


def blurred(im, r, dim=1.0):
    """Gaussian blur done premultiplied, so transparent edges don't pull in a
    dark fringe; `dim` darkens the colour (far particles sit in the gloom)."""
    pad = int(r * 3) + 2
    c = np.zeros((im.height + 2 * pad, im.width + 2 * pad, 4), np.float64)
    c[pad:pad + im.height, pad:pad + im.width] = np.asarray(im, np.float64)
    a = c[..., 3:] / 255
    pm = Image.fromarray(np.dstack([c[..., :3] * a, c[..., 3:]]).round().astype(np.uint8), 'RGBA')
    pm = np.asarray(pm.filter(ImageFilter.GaussianBlur(r)), np.float64)
    a = pm[..., 3:] / 255
    rgb = np.where(a > 0, pm[..., :3] / np.maximum(a, 1e-3), 0) * dim
    out = np.dstack([np.clip(rgb, 0, 255), pm[..., 3:]]).round().astype(np.uint8)
    return trim(Image.fromarray(out, 'RGBA'), pad=1, thr=1)


# --------------------------------------------------------------------------
# popups: main layers in mockup frame coords (x, y = top-left, from Figma)

POPUPS = {
    'big': dict(hero=('big_hero', 172, 140), txt=('big_txt', 31, 524), plate=('plate_blue', 76, 707),
                particles=['ribbon_red', 'ribbon_blue', 'ribbon_white', 'ribbon_red_s', 'ribbon_blue_s',
                           'ribbon_white_s'],
                tint=(255, 214, 120)),
    'epic': dict(hero=('epic_hero', 131, 166), txt=('epic_txt', 36, 531), plate=('plate_purple', 76, 707),
                 backdrop=('epic_backdrop', 0, 317),
                 particles=['bill_curl', 'bill_flat', 'coin', 'gold_ribbon', 'gold_ribbon_s', 'bill_flat'],
                 tint=(214, 150, 255)),
    'mega': dict(hero=('mega_hero', 95, 128), txt=('mega_txt', 23, 508), plate=('plate_red', 76, 707),
                 backdrop=('mega_backdrop', 0, 0),
                 particles=['bill_curl', 'bill_flat', 'coin', 'coin', 'gold_ribbon', 'gold_ribbon_s'],
                 tint=(255, 150, 110)),
    'bstotal': dict(hero=('bstotal_hero', 100, 113), txt=('bstotal_txt', 72, 550), plate=('plate_total', 76, 789),
                    particles=['ticket_a', 'ticket_b', 'ribbon_red', 'ribbon_blue', 'ribbon_white', 'ribbon_red_s'],
                    tint=(255, 214, 120)),
    'fstotal': dict(hero=('fstotal_hero', 69, 141), txt=('fstotal_txt', 94, 538), plate=('plate_total', 76, 789),
                    particles=['ticket_a', 'ticket_b', 'bill_flat', 'bill_curl', 'gold_ribbon', 'gold_ribbon_s'],
                    tint=(255, 214, 120)),
    'fswin': dict(hero=('fswin_hero', 69, 112), txt=('fswin_txt', 24, 820), plate=('fswin_badge', 238, 601),
                  particles=['ticket_a', 'ticket_b', 'gold_ribbon', 'gold_ribbon_s', 'coin'],
                  tint=(255, 214, 120)),
}

# Largest side of a particle on screen, per depth band (units).
BANDS = {
    #          size range    period  alpha  colour      blur
    'far':  dict(size=(64, 96),   period=6.0, alpha=0.55, color='aab4dcff', blur=3.2),
    'mid':  dict(size=(104, 150), period=3.0, alpha=1.0,  color=None,     blur=0),
    'near': dict(size=(190, 250), period=2.0, alpha=0.92, color=None,     blur=2.2),
}

LAYOUTS = {
    # half-width of the rain, particle counts per band, intro burst count
    'mob':  dict(span=430, far=14, mid=10, near=4, burst=16),
    'desk': dict(span=1450, far=34, mid=22, near=8, burst=22),
}

FALL_TOP, FALL_BOTTOM = 900, -900   # past the frame top/bottom (±708) + the biggest half-particle


def particle_images():
    P = {k: load(f'p_{k}') for k in ['bill_curl', 'bill_flat', 'coin', 'ticket_a', 'ticket_b', 'ribbon_blue',
                                      'ribbon_red_s', 'ribbon_white', 'ribbon_red', 'ribbon_blue_s',
                                      'ribbon_white_s']}
    P['gold_ribbon'] = gold(P['ribbon_white'])
    P['gold_ribbon_s'] = gold(P['ribbon_white_s'])
    return P


def build(pop, layout):
    cfg = POPUPS[pop]
    lay = LAYOUTS[layout]
    rnd = random.Random(f'{pop}-{layout}')
    sk = Skel(f'{pop}_{layout}', FW, FH, 1.0, OUT, intro=INTRO, idle=IDLE)
    # Soft fx survive at half resolution; the art keeps its own pixels.
    P = particle_images()

    def place(key):
        name, fx, fy = cfg[key]
        im = load(name)
        cx, cy = X(fx + im.width / 2), Y(fy + im.height / 2)
        return name, im, cx, cy

    hero_name, hero_im, hx, hy = place('hero')
    txt_name, txt_im, tx, ty = place('txt')
    plate_name, plate_im, px, py = place('plate')
    is_badge = pop == 'fswin'

    # ---- glow, rays and flash behind everything ---------------------------
    tint = cfg['tint']
    sk.image('rays', rays(1024, n=18, col=tint))
    sk.res_of['rays'] = 0.6
    glow = soft_glow(256)
    sk.image('glow', glow)
    sk.res_of['glow'] = 0.5
    light = load('light')
    sk.image('light', light)

    cy_glow = hy + 60
    sk.bone('rays', x=0, y=cy_glow)
    sk.slot('rays', 'rays', 'rays', w=1500, blend='additive', color='ffffff9a')
    # The idle loop turns the rays by exactly two ray steps (2 x 360/18), so
    # the wrap from its last frame to its first is invisible.
    sk.both('rays', 'rotate', lambda t: -8 * t, lambda t: -8 * INTRO - 40 * t / IDLE)
    sk.both('rays', 'scale', lambda t: (seg(t, 0.0, 0.6, 0.2, 1.0),) * 2,
            lambda t: (1 + 0.04 * wave(t, 3.0),) * 2)
    sk.both('rays', 'alpha', lambda t: seg(t, 0.0, 0.4, 0, 0.6), lambda t: 0.6 + 0.12 * wave(t, 2.0))

    sk.bone('glow', x=0, y=cy_glow)
    sk.slot('glow', 'glow', 'glow', w=1100, blend='additive', color='%02x%02x%02xff' % tint)
    sk.both('glow', 'alpha', lambda t: seg(t, 0.0, 0.5, 0, 0.55), lambda t: 0.55 + 0.1 * wave(t, 3.0))

    # Starburst flash on the title, peaks as the title lands.
    sk.bone('flash', x=0, y=ty)
    sk.slot('flash', 'flash', 'light', w=1100, blend='additive')
    sk.both('flash', 'scale', lambda t: (seg(t, 0.3, 0.9, 0.4, 1.25),) * 2,
            lambda t: (1.25 + 0.06 * wave(t, 2.0),) * 2)
    sk.both('flash', 'alpha',
            lambda t: seg(t, 0.3, 0.45, 0, 1.0) if t < 0.45 else seg(t, 0.45, 1.2, 1.0, 0.35),
            lambda t: 0.35 + 0.12 * wave(t, 2.0))

    # ---- particles -----------------------------------------------------------
    regions = {}

    def particle_region(key, band):
        r = f'{key}_{band}'
        if r not in regions:
            b = BANDS[band]
            im = P[key]
            if b['blur']:
                # Blur at roughly the on-screen scale, so the softness reads the
                # same whatever size the source art is.
                scale = (sum(b['size']) / 2) / max(im.size)
                small = im.resize((max(2, int(im.width * scale * 1.6)), max(2, int(im.height * scale * 1.6))),
                                  Image.LANCZOS)
                im = blurred(small, b['blur'] * 1.6, dim=0.82 if band == 'far' else 1.0)
            sk.image(r, im)
            regions[r] = im
        return r

    def add_rain(band, n, behind):
        b = BANDS[band]
        span = lay['span']
        names = []
        for i in range(n):
            key = rnd.choice(cfg['particles'])
            reg = particle_region(key, band)
            im = regions[reg]
            size = rnd.uniform(*b['size'])
            w = size if im.width >= im.height else size * im.width / im.height
            # lanes spread evenly with jitter, so the rain never clumps
            x0 = -span + (2 * span) * (i + rnd.uniform(0.15, 0.85)) / n
            period = b['period']
            phase = rnd.random()
            sway = rnd.uniform(12, 34) * (1.4 if band == 'near' else 1)
            sway_k = rnd.choice([1, 2]) * (IDLE / period)  # sway cycles per idle loop: integer
            spin = rnd.choice([-2, -1, 1, 2]) * (360 / IDLE)
            rot0 = rnd.uniform(0, 360)
            flip_k = rnd.choice([1, 2, 3])                     # tumble cycles per idle loop
            flip_ph = rnd.random()
            name = f'{band}{i}'
            bone = sk.bone(name, x=x0, y=FALL_TOP)
            sk.slot(name, bone, reg, w=w, color=b['color'])
            names.append(name)

            def g(t, intro):  # intro -> global time ending at 0 when idle starts
                return t - INTRO if intro else t

            def frac(gt, period=period, phase=phase):
                return (gt / period + phase) % 1.0

            def pos(gt, x0=x0, sway=sway, sway_k=sway_k):
                f = frac(gt)
                return (x0 + sway * math.sin(2 * math.pi * sway_k * gt / IDLE),
                        lerp(FALL_TOP, FALL_BOTTOM, f))

            def alpha(gt, intro_t=None, b=b):
                f = frac(gt)
                edge = 1.0 if 0.025 < f < 0.975 else 0.0     # hidden while it wraps (off screen)
                a = b['alpha'] * edge
                if intro_t is not None:
                    a *= seg(intro_t, 0.35, 1.0, 0, 1, ease=in_out_sine)
                return a

            def scale(gt, flip_k=flip_k, flip_ph=flip_ph):
                c = math.cos(2 * math.pi * (flip_k * gt / IDLE + flip_ph))
                return (c if abs(c) > 0.08 else math.copysign(0.08, c), 1.0)

            sk.anim('intro', bone, 'translate', lambda t, p=pos: p(g(t, True)))
            sk.anim('idle', bone, 'translate', lambda t, p=pos: p(g(t, False)))
            sk.anim('intro', bone, 'rotate', lambda t, r0=rot0, s=spin: r0 + s * g(t, True))
            sk.anim('idle', bone, 'rotate', lambda t, r0=rot0, s=spin: r0 + s * g(t, False))
            sk.anim('intro', bone, 'scale', lambda t, s=scale: s(g(t, True)))
            sk.anim('idle', bone, 'scale', lambda t, s=scale: s(g(t, False)))
            sk.anim('intro', name, 'alpha', lambda t, a=alpha: a(g(t, True), intro_t=t))
            sk.anim('idle', name, 'alpha', lambda t, a=alpha: a(g(t, False)))
        return names

    def add_burst(n):
        """Intro only: a fan of particles blown out of the title, then gone."""
        for i in range(n):
            key = rnd.choice(cfg['particles'])
            reg = particle_region(key, 'mid')
            im = regions[reg]
            size = rnd.uniform(90, 150)
            w = size if im.width >= im.height else size * im.width / im.height
            ang = math.radians(rnd.uniform(20, 160))
            speed = rnd.uniform(900, 1500) * (lay['span'] / 430) ** 0.35
            vx, vy = speed * math.cos(ang) * rnd.choice([-1, 1]) * 0.9, speed * math.sin(ang)
            grav = 2600
            t0 = 0.32 + rnd.uniform(0, 0.08)
            spin = rnd.uniform(-540, 540)
            name = f'burst{i}'
            bone = sk.bone(name, x=0, y=ty)
            sk.slot(name, bone, reg, w=w, color='ffffff00')

            def pos(t, vx=vx, vy=vy, t0=t0):
                u = max(0.0, t - t0)
                return (vx * u, ty + vy * u - grav * u * u / 2)

            sk.anim('intro', bone, 'translate', pos)
            sk.anim('intro', bone, 'rotate', lambda t, s=spin, t0=t0: s * max(0.0, t - t0))
            sk.anim('intro', bone, 'scale', lambda t, t0=t0: (seg(t, t0, t0 + 0.2, 0.3, 1.0),) * 2)
            sk.anim('intro', name, 'alpha',
                    lambda t, t0=t0: 0 if t < t0 else (seg(t, t0, t0 + 0.08, 0, 1) if t < 0.9 else seg(t, 0.9, INTRO, 1, 0)))
            sk.anim('idle', name, 'alpha', lambda t: 0)

    add_rain('far', lay['far'], behind=True)

    # ---- backdrop (oil field / stock chart) ---------------------------------
    if 'backdrop' in cfg:
        bd_name, bd_im, bx, by = place('backdrop')
        sk.image(bd_name, bd_im)
        sk.bone('backdrop', x=bx, y=by)
        sk.slot('backdrop', 'backdrop', bd_name)
        sk.both('backdrop', 'translate', lambda t: (bx, by - seg(t, 0.05, 0.7, 60, 0)),
                lambda t: (bx + 8 * wave(t, 6.0), by))
        sk.both('backdrop', 'alpha', lambda t: seg(t, 0.05, 0.5, 0, 1), lambda t: 1)

    add_rain('mid', lay['mid'], behind=True)

    # ---- hero ---------------------------------------------------------------
    # Pivot at his feet, so the breathe and the sway read as a body, not a card.
    sk.image(hero_name, hero_im)
    feet = hy - hero_im.height / 2
    sk.bone('hero', x=hx, y=feet)
    sk.slot('hero', 'hero', hero_name, y=hero_im.height / 2)
    sk.both('hero', 'translate',
            lambda t: (hx, feet - seg(t, 0.0, 0.5, 160, 0, ease=out_cubic)),
            lambda t: (hx, feet + 6 * (1 - math.cos(2 * math.pi * t / 3.0)) / 2))
    sk.both('hero', 'scale',
            lambda t: (seg(t, 0.0, 0.55, 0.7, 1.0, ease=out_back), seg(t, 0.0, 0.55, 0.7, 1.0, ease=out_back)),
            lambda t: (1 - 0.008 * (1 - math.cos(2 * math.pi * t / 3.0)) / 2,
                       1 + 0.018 * (1 - math.cos(2 * math.pi * t / 3.0)) / 2))
    sk.both('hero', 'rotate', lambda t: seg(t, 0.0, 0.55, -6, 0, ease=out_back), lambda t: 1.2 * wave(t, 6.0))
    sk.both('hero', 'alpha', lambda t: seg(t, 0.0, 0.18, 0, 1), lambda t: 1)

    def add_plate():
        # ---- plate / badge -----------------------------------------------------
        sk.image(plate_name, plate_im)
        sk.bone('plate', x=px, y=py)
        sk.slot('plate', 'plate', plate_name)
        p0, p1 = (0.42, 0.78) if not is_badge else (0.5, 0.95)
        sk.both('plate', 'scale',
                lambda t: ((seg(t, p0, p1, 0.2, 1.0, ease=out_back),) * 2) if not is_badge
                else (seg(t, p0, p1, 0.0, 1.0, ease=out_back),) * 2,
                lambda t: (1.0, 1.0))
        sk.both('plate', 'rotate', lambda t: seg(t, p0, p1, -180 if is_badge else 0, 0, ease=out_cubic), lambda t: 0)
        sk.both('plate', 'alpha', lambda t: seg(t, p0, p0 + 0.1, 0, 1), lambda t: 1)

    def add_title():
        # ---- title -------------------------------------------------------------
        sk.image(txt_name, txt_im)
        sk.bone('txt', x=tx, y=ty)
        sk.slot('txt', 'txt', txt_name)

        def slam(t):
            if t < 0.25:
                return 2.4
            if t < 0.42:
                return lerp(2.4, 0.92, ((t - 0.25) / 0.17) ** 2)       # falls onto the screen
            return seg(t, 0.42, 0.62, 0.92, 1.0, ease=out_back)         # and bounces back

        sk.both('txt', 'scale', lambda t: (slam(t),) * 2, lambda t: (1 + 0.025 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2,) * 2)
        sk.both('txt', 'alpha', lambda t: seg(t, 0.25, 0.34, 0, 1), lambda t: 1)
        # A white sheen over the title that flares on impact and once a loop.
        sk.image('txt_sheen', flash_of(txt_im))
        sk.slot('txt_sheen', 'txt', 'txt_sheen', w=txt_im.width, blend='additive')
        sk.both('txt_sheen', 'alpha',
                lambda t: 0 if t < 0.42 else seg(t, 0.42, 0.75, 0.85, 0),
                lambda t: 0.3 * max(0.0, math.sin(2 * math.pi * (t / 3.0 - 0.1))) ** 24)

    # Mockup layer order: the win plate sits OVER the title's lower edge; on
    # FREE SPINS WIN the title sits over the round badge.
    if is_badge:
        add_plate()
        add_title()
    else:
        add_title()
        add_plate()

    # ---- near rain and the burst, in front of everything --------------------
    add_burst(lay['burst'])
    add_rain('near', lay['near'], behind=False)

    sk.write()


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:]
    for pop in POPUPS:
        if only and pop not in only:
            continue
        for layout in LAYOUTS:
            build(pop, layout)
