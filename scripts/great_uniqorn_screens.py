"""Great Uniqorn — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Same contract as the other games' screens (scripts/multi_fruits_story_screens.py,
scripts/spine_screen_kit.py): a full-screen skeleton on the game's design canvas
(desk 1932x940 / mob 780x1416, origin = canvas centre, 1 unit = 1 design px,
y up), `intro` (3s) -> `idle` (4s seamless loop). The game background is NOT in
the skeleton — slot.js puts the game's own bg under the canvas (#featureScreen).

All art is the game's own: logo, symbols (WILD, x2..x9, burger), the designer's
popup layers (heroes, FREE SPINS WIN title, round badge, blue total plate — cut
9-slice into the info panels), the popups' bills / coins / FS tickets / ribbons
for the floating background. Texts are Luckiest Guy (titles) / Baloo 2 (captions),
gold like the designer's titles.

  feature  WILD MULTIPLIER panel (the wild cycles through x2..x9 in idle) +
           FREE SPINS panel (3 burgers, 3/4/5 -> 10/15/20) + hero + TAP TO CONTINUE
  bonus    hero, round badge (live spin count = DOM over bone `count`), the
           FREE SPINS WIN title, a line on the multipliers, TAP TO START

    python3 scripts/great_uniqorn_screens.py <fonts_dir>
    fonts_dir: luckiest.ttf + baloo.ttf (front/fonts woff2 -> ttf with fontTools)
"""

import math
import os
import random
import sys

from PIL import Image, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, flash_of, in_out_sine, lerp, out_back, out_cubic, rays, seg, soft_glow, text_img, trim, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'front/img/great-uniqorn')
LAYERS = os.path.join(IMG, 'src/popup_layers')
OUT = os.path.join(IMG, 'screens')

INTRO, IDLE = 3.0, 4.0
SIZES = {'desk': (1932, 940), 'mob': (780, 1416)}
GOLD = [(0.0, (255, 246, 196, 255)), (0.45, (255, 210, 90, 255)), (0.7, (226, 150, 30, 255)), (1.0, (255, 214, 110, 255))]
FONTS = {}


def font(kind, size):
    f = ImageFont.truetype(FONTS[kind], size)
    if kind == 'baloo':
        try:
            f.set_variation_by_name('ExtraBold')
        except Exception:
            pass
    return f


def load(path):
    return Image.open(path).convert('RGBA')


def sym(code):
    return trim(load(os.path.join(IMG, 'symbols', f'{code}.png')), pad=2)


def layer(name):
    return load(os.path.join(LAYERS, f'{name}.png'))


def title(text, size):
    return text_img(text, font('luckiest', size), GOLD, stroke='0d1d4f', stroke_w=max(3, size // 11),
                    glow='ffcf5c', glow_r=max(4, size // 6), shadow='020818')


def caption(text, size, color='ffffff'):
    c = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    return text_img(text, font('baloo', size), [(0, c + (255,)), (1, c + (255,))], stroke='0a1640',
                    stroke_w=max(2, size // 9), shadow='020818')


def nine_slice(src, w, h, cut=46):
    """Stretch the designer's blue total plate into a panel w x h (corners kept)."""
    W, H = src.size
    out = Image.new('RGBA', (w, h))
    xs = [(0, cut, 0, cut), (cut, W - cut, cut, w - cut), (W - cut, W, w - cut, w)]
    ys = [(0, cut, 0, cut), (cut, H - cut, cut, h - cut), (H - cut, H, h - cut, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            piece = src.crop((sx0, sy0, sx1, sy1)).resize((max(1, dx1 - dx0), max(1, dy1 - dy0)), Image.LANCZOS)
            out.paste(piece, (dx0, dy0))
    return out


class Screen:
    """Skel plus coordinate helpers in canvas pixels (top-left origin)."""

    def __init__(self, name, variant):
        self.w, self.h = SIZES[variant]
        self.sk = Skel(name, self.w, self.h, 1.0, OUT, intro=INTRO, idle=IDLE)
        self.rnd = random.Random(name)

    def X(self, x):
        return x - self.w / 2

    def Y(self, y):
        return self.h / 2 - y

    def place(self, name, region, im, cx, cy, w=None, blend=None, color=None, parent='root'):
        """Bone at canvas (cx, cy) with the region centred on it."""
        self.sk.image(region, im)
        bx, by = (self.X(cx), self.Y(cy)) if parent == 'root' else (cx, cy)
        self.sk.bone(name, parent=parent, x=bx, y=by)
        self.sk.slot(name, name, region, w=w, blend=blend, color=color)
        return bx, by

    def pop_in(self, name, t0, t1, bx, by, rise=0, start=0.3):
        self.sk.both(name, 'scale', lambda t: (seg(t, t0, t1, start, 1.0, ease=out_back),) * 2, lambda t: (1.0, 1.0))
        self.sk.both(name, 'alpha', lambda t: seg(t, t0, t0 + 0.15, 0, 1), lambda t: 1)
        if rise:
            self.sk.both(name, 'translate', lambda t: (bx, by - seg(t, t0, t1, rise, 0)), lambda t: (bx, by))

    def tap_hint(self, text, cy, size):
        im = caption(text, size, 'ffe7a0')
        bx, by = self.place('tap', 'tap', im, self.w / 2, cy)
        self.sk.both('tap', 'alpha', lambda t: seg(t, 2.4, 2.9, 0, 1), lambda t: 0.55 + 0.45 * (0.5 + 0.5 * math.cos(2 * math.pi * t / 2.0)))

    def floaters(self, keys, n, scale=(70, 120), alpha=0.75):
        """Bills / tickets / ribbons drifting down slowly — 4s loop, wrap off screen at alpha 0."""
        imgs = {k: layer(f'p_{k}') for k in set(keys)}
        for i in range(n):
            k = self.rnd.choice(keys)
            reg = f'fl_{k}'
            if reg not in self.sk.images:
                self.sk.image(reg, imgs[k])
            im = imgs[k]
            size = self.rnd.uniform(*scale)
            w = size if im.width >= im.height else size * im.width / im.height
            x0 = self.X(self.w * (i + self.rnd.uniform(0.1, 0.9)) / n)
            top, bot = self.h / 2 + 160, -self.h / 2 - 160
            period = self.rnd.choice([4.0, 4.0, 2.0])
            ph = self.rnd.random()
            spin = self.rnd.choice([-1, 1]) * 360 / IDLE * self.rnd.choice([1, 2])
            r0 = self.rnd.uniform(0, 360)
            flip = self.rnd.choice([1, 2])
            sway = self.rnd.uniform(15, 40)
            name = f'fl{i}'
            self.sk.bone(name, x=x0, y=top)
            self.sk.slot(name, name, reg, w=w)

            def g(t, intro):
                return t - INTRO if intro else t

            def pos(gt, x0=x0, period=period, ph=ph, sway=sway, top=top, bot=bot):
                f = (gt / period + ph) % 1.0
                return (x0 + sway * math.sin(2 * math.pi * gt / IDLE), lerp(top, bot, f))

            def al(gt, intro_t=None, period=period, ph=ph):
                f = (gt / period + ph) % 1.0
                a = alpha if 0.03 < f < 0.97 else 0.0
                if intro_t is not None:
                    a *= seg(intro_t, 0.2, 1.2, 0, 1, ease=in_out_sine)
                return a

            def sc(gt, flip=flip, ph=ph):
                c = math.cos(2 * math.pi * (flip * gt / IDLE + ph))
                return (c if abs(c) > 0.08 else math.copysign(0.08, c), 1.0)

            for which, intro in (('intro', True), ('idle', False)):
                self.sk.anim(which, name, 'translate', lambda t, intro=intro, p=pos: p(g(t, intro)))
                self.sk.anim(which, name, 'rotate', lambda t, intro=intro, r0=r0, s=spin: r0 + s * g(t, intro))
                self.sk.anim(which, name, 'scale', lambda t, intro=intro, s=sc: s(g(t, intro)))
            self.sk.anim('intro', name, 'alpha', lambda t, a=al: a(g(t, True), intro_t=t))
            self.sk.anim('idle', name, 'alpha', lambda t, a=al: a(g(t, False)))

    def glow_rays(self, cx, cy, size, tint=(255, 214, 120)):
        self.sk.image('rays', rays(1024, n=18, col=tint))
        self.sk.res_of['rays'] = 0.6
        bx, by = self.place('rays', 'rays', self.sk.images['rays'], cx, cy, w=size, blend='additive', color='ffffff88')
        self.sk.both('rays', 'rotate', lambda t: -6 * t, lambda t: -6 * INTRO - 40 * t / IDLE)
        self.sk.both('rays', 'alpha', lambda t: seg(t, 0.0, 0.8, 0, 0.5), lambda t: 0.5 + 0.1 * wave(t, 2.0))
        self.sk.image('glow', soft_glow(256))
        self.sk.res_of['glow'] = 0.5
        self.place('glow', 'glow', self.sk.images['glow'], cx, cy, w=size * 0.8, blend='additive',
                   color='%02x%02x%02xff' % tint)
        self.sk.both('glow', 'alpha', lambda t: seg(t, 0.0, 0.8, 0, 0.45), lambda t: 0.45 + 0.08 * wave(t, 4.0))


# ---------------------------------------------------------------------------
# FEATURE


def wild_panel(s, cx, cy, pw, ph, t0):
    """Panel: title, a big WILD cycling into x2..x9, the row of multipliers, captions."""
    panel = nine_slice(load(os.path.join(LAYERS + '_v1', 'plate_total.png')), pw, ph)
    pbx, pby = s.place('p1', 'panel_w', panel, cx, cy)
    s.pop_in('p1', t0, t0 + 0.5, pbx, pby, rise=60, start=0.6)
    t = title('WILD MULTIPLIER', 62 if pw > 560 else 54)
    s.place('p1_title', 'p1_title', t, cx, cy - ph / 2 + 58)
    s.pop_in('p1_title', t0 + 0.2, t0 + 0.6, s.X(cx), s.Y(cy - ph / 2 + 58))
    big = min(210, round(ph * 0.34))
    wy = cy - ph / 2 + 70 + big / 2 + 20
    s.place('w_wild', 'w_wild', sym('wild'), cx, wy, w=big)
    s.pop_in('w_wild', t0 + 0.4, t0 + 0.9, s.X(cx), s.Y(wy))
    # idle: WILD -> x2 -> x3 -> x5 -> x7 -> x9 crossfades over the wild, 4s loop
    mults = [2, 3, 5, 7, 9]
    slot_t = IDLE / (len(mults) + 1)

    def var_alpha(t, i):
        k = (t / slot_t) - (i + 1)                  # variant i's window [0,1)
        if k < -0.15 or k > 1.0:
            return 0.0
        return seg(k, -0.15, 0.05, 0, 1) if k < 0.05 else (1.0 if k < 0.85 else seg(k, 0.85, 1.0, 1, 0))

    for i, m in enumerate(mults):
        s.place(f'w_x{m}', f'w_x{m}', sym(f'x{m}'), cx, wy, w=big)
        s.sk.both(f'w_x{m}', 'alpha', lambda t: 0, lambda t, i=i: var_alpha(t, i))
        s.sk.both(f'w_x{m}', 'scale', lambda t: (1, 1),
                  lambda t, i=i: (1 + 0.08 * max(0.0, 1 - abs(t / slot_t - (i + 1)) * 6),) * 2)
    # the plain WILD fades out under whichever multiplier is showing — no
    # double silhouette mid-crossfade
    s.sk.anim('idle', 'w_wild', 'alpha', lambda t: 1.0 - max(var_alpha(t, i) for i in range(len(mults))))
    # row of multipliers
    row_y = wy + big / 2 + 70
    step = min(110, (pw - 80) / 5)
    for i, m in enumerate(mults):
        x = cx + (i - 2) * step
        s.place(f'row{m}', f'row_x{m}', sym(f'x{m}'), x, row_y, w=step * 0.95)
        s.pop_in(f'row{m}', t0 + 0.8 + i * 0.08, t0 + 1.2 + i * 0.08, s.X(x), s.Y(row_y))
    c1 = caption('EVERY WILD CAN TURN INTO A x2 – x9 MULTIPLIER', 26 if pw > 560 else 22)
    c2 = caption('MULTIPLIERS ON ONE LINE MULTIPLY TOGETHER', 26 if pw > 560 else 22, 'ffd56a')
    y1 = cy + ph / 2 - 92
    s.place('p1_c1', 'p1_c1', c1, cx, y1, w=min(c1.width, pw - 70))
    s.place('p1_c2', 'p1_c2', c2, cx, y1 + 40, w=min(c2.width, pw - 70))
    for n in ('p1_c1', 'p1_c2'):
        s.sk.both(n, 'alpha', lambda t: seg(t, t0 + 1.2, t0 + 1.6, 0, 1), lambda t: 1)


def fs_panel(s, cx, cy, pw, ph, t0):
    panel = nine_slice(load(os.path.join(LAYERS + '_v1', 'plate_total.png')), pw, ph)
    pbx, pby = s.place('p2', 'panel_f', panel, cx, cy)
    s.pop_in('p2', t0, t0 + 0.5, pbx, pby, rise=60, start=0.6)
    s.place('p2_title', 'p2_title', title('FREE SPINS', 66 if pw > 560 else 58), cx, cy - ph / 2 + 58)
    s.pop_in('p2_title', t0 + 0.2, t0 + 0.6, s.X(cx), s.Y(cy - ph / 2 + 58))
    by = cy - ph / 2 + 190
    bsz = 150 if ph > 470 else 130
    for i in range(3):
        x = cx + (i - 1) * (bsz + 14)
        s.place(f'burger{i}', 'burger', sym('scatter'), x, by, w=bsz)
        s.pop_in(f'burger{i}', t0 + 0.5 + i * 0.15, t0 + 0.9 + i * 0.15, s.X(x), s.Y(by))
        s.sk.anim('idle', f'burger{i}', 'scale',
                  lambda t, i=i: (1 + 0.06 * max(0.0, math.sin(2 * math.pi * (t / IDLE - i * 0.12))) ** 6,) * 2)
    # 3 / 4 / 5 -> 10 / 15 / 20
    ty = by + bsz / 2 + 70
    colw = (pw - 80) / 3
    for i, (k, v) in enumerate(((3, 10), (4, 15), (5, 20))):
        x = cx + (i - 1) * colw
        im = title(f'{k}  =  {v}', 44 if pw > 560 else 40)
        s.place(f'fs_row{i}', f'fs_row{i}', im, x, ty, w=min(im.width, colw - 10))
        s.pop_in(f'fs_row{i}', t0 + 1.0 + i * 0.1, t0 + 1.4 + i * 0.1, s.X(x), s.Y(ty))
    c = caption('3, 4 OR 5 BURGERS ANYWHERE START FREE SPINS', 26 if pw > 560 else 22)
    c2 = caption('MORE BURGERS DURING FREE SPINS ADD SPINS', 26 if pw > 560 else 22, 'ffd56a')
    y1 = cy + ph / 2 - 92
    s.place('p2_c1', 'p2_c1', c, cx, y1, w=min(c.width, pw - 70))
    s.place('p2_c2', 'p2_c2', c2, cx, y1 + 40, w=min(c2.width, pw - 70))
    for n in ('p2_c1', 'p2_c2'):
        s.sk.both(n, 'alpha', lambda t: seg(t, t0 + 1.4, t0 + 1.8, 0, 1), lambda t: 1)


def build_feature(variant):
    s = Screen(f'feature_{variant}', variant)
    W, H = s.w, s.h
    s.floaters(['bill_flat', 'bill_curl', 'ribbon_red', 'ribbon_blue', 'ribbon_white', 'ticket_a'],
               16 if variant == 'desk' else 10, scale=(60, 110), alpha=0.6)
    logo = trim(load(os.path.join(IMG, 'img/logo.png')), pad=2)
    if variant == 'desk':
        s.glow_rays(260, 520, 900)
        hero = layer('big_hero')
        hx, hy = 270, H - hero.height * 1.05 / 2 - 20
        s.place('hero', 'hero', hero, hx, hy, w=hero.width * 1.05)
        s.sk.both('hero', 'translate', lambda t: (s.X(hx) - seg(t, 0.0, 0.6, 260, 0), s.Y(hy)), lambda t: (s.X(hx), s.Y(hy)))
        s.sk.both('hero', 'alpha', lambda t: seg(t, 0.0, 0.3, 0, 1), lambda t: 1)
        lx, ly, lw = 1180, 92, 520
        wild_panel(s, 880, 520, 600, 580, 0.5)
        fs_panel(s, 1520, 520, 600, 580, 0.8)
        s.tap_hint('TAP TO CONTINUE', 885, 34)
    else:
        lx, ly, lw = W / 2, 110, 470
        wild_panel(s, W / 2, 500, 700, 560, 0.4)
        fs_panel(s, W / 2, 1030, 700, 470, 0.7)
        s.tap_hint('TAP TO CONTINUE', 1330, 34)
    s.place('logo', 'logo', logo, lx, ly, w=lw)
    s.sk.both('logo', 'translate', lambda t: (s.X(lx), s.Y(ly) + seg(t, 0.1, 0.7, 220, 0, ease=out_back)), lambda t: (s.X(lx), s.Y(ly)))
    s.sk.both('logo', 'alpha', lambda t: seg(t, 0.1, 0.3, 0, 1), lambda t: 1)
    s.sk.anim('idle', 'logo', 'scale', lambda t: (1 + 0.015 * (1 - math.cos(2 * math.pi * t / IDLE)) / 2,) * 2)
    s.sk.write()


# ---------------------------------------------------------------------------
# BONUS


def build_bonus(variant):
    s = Screen(f'bonus_{variant}', variant)
    W, H = s.w, s.h
    s.floaters(['ticket_a', 'ticket_b', 'bill_flat', 'coin', 'ribbon_white', 'ribbon_red'],
               20 if variant == 'desk' else 12, scale=(70, 130), alpha=0.7)
    hero = layer('fswin_hero')
    badge = layer('fswin_badge')
    ttl = layer('fswin_txt')
    line = caption('EVERY WILD CAN BECOME x2 – x9', 34, 'ffffff')
    line2 = caption('MORE BURGERS = MORE SPINS', 30, 'ffd56a')
    # FREESPINS WIN is two lines since the 2026-11-05 pack: its top stays where
    # the old one-liner's was (just under the badge's middle) and the captions
    # follow its bottom.
    tsc = 1.0
    if variant == 'desk':
        hcx, hcy, hsc = 560, 470, 0.95
        bcx, bcy = 1290, 330
        tcx, ttop = 1290, 450
        rays_at = (1290, 360)
        tap_y = 900
    else:
        # the designer's FREE SPINS WIN popup composition, as on the mockup
        hcx, hcy, hsc = 69 + 300, 112 + 436.5, 1.0
        bcx, bcy = 238 + 152.5, 601 + 145
        tcx, ttop = 24 + 366, 820
        rays_at = (390, 600)
        tap_y = 1320
    tcy = ttop + ttl.height * tsc / 2
    l1y = ttop + ttl.height * tsc + 22
    s.glow_rays(*rays_at, 1500 if variant == 'desk' else 1300)
    s.place('hero', 'hero', hero, hcx, hcy, w=hero.width * hsc)
    s.sk.both('hero', 'translate', lambda t: (s.X(hcx), s.Y(hcy) - seg(t, 0.0, 0.6, 180, 0, ease=out_cubic)), lambda t: (s.X(hcx), s.Y(hcy)))
    s.sk.both('hero', 'alpha', lambda t: seg(t, 0.0, 0.25, 0, 1), lambda t: 1)
    # badge spins in; the live count is DOM text glued to bone `count`
    s.place('badge', 'badge', badge, bcx, bcy, w=badge.width * (1.15 if variant == 'desk' else 1.0))
    s.sk.both('badge', 'scale', lambda t: (seg(t, 0.9, 1.5, 0.0, 1.0, ease=out_back),) * 2,
              lambda t: (1 + 0.02 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2,) * 2)
    s.sk.both('badge', 'rotate', lambda t: seg(t, 0.9, 1.5, -200, 0, ease=out_cubic), lambda t: 0)
    s.sk.both('badge', 'alpha', lambda t: seg(t, 0.9, 1.0, 0, 1), lambda t: 1)
    s.sk.bone('count', parent='badge', x=0, y=-4)
    # title slams down like the popups'
    s.place('title', 'title', ttl, tcx, tcy, w=ttl.width * tsc)

    def slam(t):
        if t < 0.5:
            return 2.2
        if t < 0.7:
            return lerp(2.2, 0.92, ((t - 0.5) / 0.2) ** 2)
        return seg(t, 0.7, 0.9, 0.92, 1.0, ease=out_back)
    s.sk.both('title', 'scale', lambda t: (slam(t),) * 2, lambda t: (1 + 0.02 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2,) * 2)
    s.sk.both('title', 'alpha', lambda t: seg(t, 0.5, 0.6, 0, 1), lambda t: 1)
    s.sk.image('title_sheen', flash_of(ttl))
    s.sk.slot('title_sheen', 'title', 'title_sheen', w=ttl.width * tsc, blend='additive')
    s.sk.both('title_sheen', 'alpha', lambda t: 0 if t < 0.7 else seg(t, 0.7, 1.1, 0.8, 0),
              lambda t: 0.3 * max(0.0, math.sin(2 * math.pi * (t / 4.0 - 0.1))) ** 24)
    lx = tcx
    s.place('l1', 'l1', line, lx, l1y)
    s.place('l2', 'l2', line2, lx, l1y + 46)
    for n, d in (('l1', 0), ('l2', 0.15)):
        s.sk.both(n, 'alpha', lambda t, d=d: seg(t, 1.6 + d, 2.0 + d, 0, 1), lambda t: 1)
    s.tap_hint('TAP TO START', tap_y, 36)
    s.sk.write()


if __name__ == '__main__':
    fd = sys.argv[1]
    FONTS['luckiest'] = os.path.join(fd, 'luckiest.ttf')
    FONTS['baloo'] = os.path.join(fd, 'baloo.ttf')
    os.makedirs(OUT, exist_ok=True)
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
