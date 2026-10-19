"""Neon Joker Spins (+ skins A/B/C) — feature (preview) screen and two bonus
screens (Free Spins, Hold & Win) as Spine 4.1 skeletons, same contract as
scripts/volt_coins_screens.py: full-screen skeleton on the game's design canvas
(desk 1600x900 / mob 720x1280, origin = centre, 1 unit = 1 design px, y up),
`intro` (3 s) -> `idle` (4 s seamless loop). The game's background is not in
the skeleton — slot.js puts the bg under the canvas.

One generator for all four games: the art is read from each game's own asset
root (logo, mascot, Joker scatter, blank coin + bitmap glyph font, collector,
tier coins), only the theme (title gradient, glow, card rim) differs.

Copy matches app/seed/neon_joker_spins.py: 3+ Jokers anywhere = 10 free spins
(+5 on retrigger, coins land more often); 5+ coins = Hold & Win, 3 respins,
a new coin resets them, 9/9 = GRAND; the Collector gathers every plain coin.

    <venv>/bin/python scripts/neon_joker_spins_screens.py <fonts_dir> [orig a b c]
    fonts_dir: baloo.ttf, luckiest.ttf
"""

import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, out_back, out_cubic, rays, seg, soft_glow, spark, text_img, trim, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = sys.argv[1]

INTRO = 3.0
IDLE = 4.0
DESK = (1600, 900)
MOB = (720, 1280)

GAMES = {
    'orig': {'root': 'front/img/neon-joker-spins',
             'title': [(0, 'fff6c8'), (0.5, 'ffd75a'), (1, 'f5a000')], 'glow': 'ff3cac', 'ink': '2a0a3a',
             'rim': 'f5b400', 'edge': '2ce8ff', 'body': ('2a1150', '12081f'), 'rays': 'ff3cac', 'halo': '7a2cff'},
    'a': {'root': 'front/img/neon-joker-spins/skins/a',
          'title': [(0, 'ffffff'), (0.45, 'ffd2f0'), (1, 'ff3cac')], 'glow': 'ff3cac', 'ink': '1a0630',
          'rim': 'ff3cac', 'edge': '2ce8ff', 'body': ('1d0b3a', '0a0418'), 'rays': '2ce8ff', 'halo': 'ff3cac'},
    'b': {'root': 'front/img/neon-joker-spins/skins/b',
          'title': [(0, 'fffbe0'), (0.45, 'ffd75a'), (1, 'e08a00')], 'glow': 'ffb000', 'ink': '3a0848',
          'rim': 'ffd75a', 'edge': 'ff5ad0', 'body': ('4a1060', '1c0628'), 'rays': 'ffd75a', 'halo': 'c040ff'},
    'c': {'root': 'front/img/neon-joker-spins/skins/c',
          'title': [(0, 'ffffff'), (0.5, 'c9ced8'), (1, '7d8494')], 'glow': 'ff2fb4', 'ink': '0a0610',
          'rim': '9aa1ad', 'edge': 'ff2fb4', 'body': ('1c1424', '08060c'), 'rays': '2ce8ff', 'halo': 'ff2fb4'},
}


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)


def grad(stops):
    return [(k, hexc(c)) for k, c in stops]


# --------------------------------------------------------------------------
# motion helpers (idle offsets are 0 at t=0 so idle starts where intro ends)

def bob(t, amp, period=IDLE, phase=0.0):
    return amp * (wave(t, period, phase) - wave(0, period, phase))


def pop(t, t0, dur=0.55, s0=0.3):
    return seg(t, t0, t0 + dur, s0, 1.0, out_back)


def fade(t, t0, dur=0.3):
    return seg(t, t0, t0 + dur, 0.0, 1.0, out_cubic)


def uniform(fn):
    return lambda t: (fn(t),) * 2


def move(sk, bone, intro_fn, idle_fn):
    """The kit's translate is the bone's absolute position — add the setup."""
    d = next(b for b in sk.bones if b['name'] == bone)
    bx, by = d.get('x', 0), d.get('y', 0)

    def absolute(f):
        return lambda t: (bx + f(t)[0], by + f(t)[1])

    sk.both(bone, 'translate', absolute(intro_fn), absolute(idle_fn))


class Game:
    def __init__(self, key):
        self.key = key
        self.g = GAMES[key]
        self.dir = os.path.join(ROOT, self.g['root'])
        self.out = os.path.join(self.dir, 'screens')
        glyph_dir = os.path.join(ROOT, 'front/img/neon-joker-spins/glyphs')
        self.glyph_dir = os.path.join(self.dir, 'glyphs') if os.path.isdir(os.path.join(self.dir, 'glyphs')) else glyph_dir
        self.glyphs = json.load(open(os.path.join(self.glyph_dir, 'glyphs.json')))
        self.art = {}
        self._build_art()

    # --- source art -------------------------------------------------------
    def load(self, rel):
        return trim(Image.open(os.path.join(self.dir, rel)).convert('RGBA'))

    def title(self, text, size, fill=None):
        g = self.g
        return text_img(text, font('luckiest', size), grad(fill or g['title']), stroke=g['ink'],
                        stroke_w=max(3, size // 11), glow=g['glow'], glow_r=max(6, size // 5), shadow='000008')

    def lines(self, rows, size, gap=0.16):
        g = self.g
        ims = [text_img(r, font('baloo', size), grad([(0, 'ffffff'), (1, 'f0e4ff')]), stroke=g['ink'],
                        stroke_w=max(3, size // 9), glow=None, shadow='00000a') for r in rows]
        w = max(i.width for i in ims)
        step = int(size * (1 + gap))
        out = Image.new('RGBA', (w, step * (len(ims) - 1) + ims[-1].height))
        for k, im in enumerate(ims):
            out.alpha_composite(im, ((w - im.width) // 2, k * step))
        return out

    def glyph_text(self, text, cap_h):
        """The game's own bitmap number font, same metrics as slot.js setGlyphs."""
        parts = []
        for ch in text.lower():
            if ch not in self.glyphs:
                continue
            w, h = self.glyphs[ch]
            hh = cap_h * h / 116
            name = {'.': 'dot', ',': 'comma'}.get(ch, ch)
            im = Image.open(os.path.join(self.glyph_dir, name + '.webp')).convert('RGBA')
            parts.append(im.resize((max(1, round(hh * w / h)), max(1, round(hh))), Image.LANCZOS))
        overlap = int(cap_h * 0.02)
        W = sum(p.width for p in parts) - overlap * (len(parts) - 1)
        H = max(p.height for p in parts)
        out = Image.new('RGBA', (W, H))
        x = 0
        for p in parts:
            out.alpha_composite(p, (x, H - p.height))
            x += p.width - overlap
        return out

    def coin(self, label, collector=False):
        """Blank coin (or collector) with its face printed like the reels do
        (.coin-val boxes measured by neon_joker_spins_skins.py / base CSS)."""
        base = Image.open(os.path.join(self.dir, 'coins', 'collector.webp' if collector else 'blank.webp')).convert('RGBA')
        W, H = base.size
        face = self.face_box(collector)
        l, t, w, h = face
        txt = self.glyph_text(label, int(h * H))
        k = min(1.0, (w * W) / txt.width)
        txt = txt.resize((max(1, int(txt.width * k)), max(1, int(txt.height * k))), Image.LANCZOS)
        out = base.copy()
        out.alpha_composite(txt, (int(l * W + (w * W - txt.width) / 2), int(t * H + (h * H - txt.height) / 2)))
        return trim(out)

    def face_box(self, collector):
        """Value box on the coin in fractions of the 360px cell — from the
        game's CSS (.reel__cell .coin-val)."""
        css = os.path.join(ROOT, 'front/css', f'njs-skin-{self.key}.css')
        if self.key != 'orig' and os.path.exists(css):
            import re
            txt = open(css).read()
            sel = '.reel__cell[data-symbol="collector"] .coin-val' if collector else '.reel__cell .coin-val {'
            seg_ = txt[txt.index(sel):].split('}')[0]
            v = {k: float(x) / 100 for k, x in re.findall(r'(left|right|top|height): ([\d.]+)%', seg_)}
            return v['left'], v['top'], 1 - v['left'] - v['right'], v['height']
        # base game: left/right 18%, top 33%, height 30%; collector 24% / 25% / 26%
        return (0.24, 0.25, 0.52, 0.26) if collector else (0.18, 0.33, 0.64, 0.30)

    def card(self, w, h, r=30):
        g = self.g
        pad = 40
        im = Image.new('RGBA', (w + 2 * pad, h + 2 * pad))
        glow = Image.new('L', im.size)
        ImageDraw.Draw(glow).rounded_rectangle([pad, pad, pad + w, pad + h], r, fill=210)
        glow = glow.filter(ImageFilter.GaussianBlur(18))
        gl = Image.new('RGBA', im.size, hexc(g['edge'])[:3] + (0,))
        gl.putalpha(glow.point(lambda v: v // 3))
        im.alpha_composite(gl)
        top, bot = hexc(g['body'][0]), hexc(g['body'][1])
        body = Image.new('RGBA', (w, h))
        bd = ImageDraw.Draw(body)
        for y in range(h):
            k = y / h
            bd.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - k) + bot[i] * k) for i in range(3)) + (236,))
        mask = Image.new('L', (w, h))
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
        body.putalpha(mask)
        im.alpha_composite(body, (pad, pad))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + w, pad + h], r, outline=hexc(g['rim']), width=4)
        d.rounded_rectangle([pad + 7, pad + 7, pad + w - 7, pad + h - 7], r - 7, outline=hexc(g['edge'])[:3] + (170,), width=2)
        return im

    def _build_art(self):
        A = self.art
        A['logo'] = self.load('img/logo.webp')
        A['logo_flash'] = flash_of(A['logo'], 0.9)
        A['mascot'] = self.load('img/mascot.webp')
        A['joker'] = self.load('symbols/scatter.webp')
        A['glow'] = soft_glow(256)
        A['rays'] = rays(560, n=16)
        s = spark(96, 14)
        star = Image.new('RGBA', (96, 96))
        star.alpha_composite(s, (0, (96 - s.height) // 2))
        star.alpha_composite(s.rotate(90, expand=True), ((96 - s.height) // 2, 0))
        A['star'] = star
        for lab in ('2x', '5x', '10x', '3x'):
            A[f'c_{lab}'] = self.coin(lab)
        A['c_col'] = self.coin('21x', collector=True)
        for tier in ('mini', 'minor', 'major'):
            A[f'c_{tier}'] = self.load(f'coins/{tier}.webp')
        A['n_10'] = self.glyph_text('10', 200)
        A['t_fs'] = self.title('FREE SPINS', 64)
        A['t_hw'] = self.title('HOLD & WIN', 64)
        A['t_col'] = self.title('COLLECTOR', 64)
        A['d_fs'] = self.lines(['3+ JOKERS ANYWHERE', 'WIN 10 FREE SPINS', '+5 ON RETRIGGER'], 34)
        A['d_hw'] = self.lines(['5+ COINS START', '3 RESPINS', 'FILL ALL 9 = GRAND'], 34)
        A['d_col'] = self.lines(['GATHERS THE VALUE', 'OF EVERY COIN', 'ON THE GRID'], 34)
        A['tap_continue'] = self.title('TAP TO CONTINUE', 50, fill=[(0, 'ffffff'), (1, 'e8dcff')])
        A['tap_start'] = self.title('TAP TO START', 56, fill=[(0, 'ffffff'), (1, 'e8dcff')])
        A['big_fs'] = self.title('FREE SPINS', 150)
        A['big_hw'] = self.title('HOLD & WIN', 150)
        A['rules_fs'] = self.lines(['COINS LAND MORE OFTEN', '3+ JOKERS ADD +5 SPINS', 'HOLD & WIN CAN START INSIDE'], 38)
        A['rules_hw'] = self.lines(['COINS STAY · A NEW COIN RESETS 3 RESPINS',
                                    'THE COLLECTOR GATHERS ALL COIN VALUES',
                                    'FILL ALL 9 CELLS FOR GRAND'], 36)

    # --- skeleton helpers --------------------------------------------------
    def add(self, sk, *keys):
        for k in keys:
            if k not in sk.images:
                sk.image(k, self.art[k])

    def popin(self, sk, name, region, parent, x, y, w, t0, amp=6, phase=0.0, rot=0, idle_scale=None):
        self.add(sk, region)
        b = sk.bone(name, parent, x, y, rot=rot)
        sk.slot(name, b, region, w=w)
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0) if t >= t0 else 0.01),
                uniform(idle_scale or (lambda t: 1.0)))
        move(sk, b, lambda t: (0, 0), lambda t: (0, bob(t, amp, IDLE, phase)))
        sk.both(name, 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1.0)
        return b

    def logo(self, sk, x, y, w):
        self.add(sk, 'logo', 'logo_flash')
        lb = sk.bone('logo', 'root', x, y)
        sk.slot('logo', lb, 'logo', w=w)
        sk.slot('logo_flash', lb, 'logo_flash', w=w, blend='additive')
        sk.both(lb, 'scale', uniform(lambda t: pop(t, 0.1, 0.7, 0.4)), uniform(lambda t: breathe(t, IDLE, 0.02)))
        sk.both('logo', 'alpha', lambda t: fade(t, 0.1, 0.3), lambda t: 1)
        sk.both('logo_flash', 'alpha', lambda t: seg(t, 0.4, 0.9, 0.9, 0) if t >= 0.4 else 0.0,
                lambda t: 0.35 * max(0.0, math.sin(2 * math.pi * (t - 1.5) / IDLE)) ** 8)

    def mascot(self, sk, x, y_bottom, h, t0=0.25, flip=False):
        self.add(sk, 'mascot')
        m = self.art['mascot']
        w = h * m.width / m.height
        b = sk.bone('mascot', 'root', x, y_bottom + h / 2, sx=-1 if flip else 1)
        sk.slot('mascot', b, 'mascot', w=w)
        move(sk, b, lambda t: (-140 * seg(t, t0, t0 + 0.7, 1, 0), 0), lambda t: (0, bob(t, 8, IDLE)))
        sk.both(b, 'rotate', lambda t: 0, lambda t: 1.2 * (wave(t, IDLE, 0.25) - wave(0, IDLE, 0.25)))
        sk.both('mascot', 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1)

    def tap(self, sk, region, x, y, w, t0=2.2):
        self.add(sk, region)
        tb = sk.bone('tap', 'root', x, y)
        sk.slot('tap', tb, region, w=w)
        sk.both('tap', 'alpha', lambda t: fade(t, t0, 0.4),
                lambda t: 0.55 + 0.45 * (1 + math.cos(2 * math.pi * t / 2.0)) / 2)
        sk.both(tb, 'scale', uniform(lambda t: 1.0),
                uniform(lambda t: 1 + 0.03 * (1 + math.cos(2 * math.pi * t / 2.0)) / 2))

    def twinkles(self, sk, spots, seed, start=1.4):
        self.add(sk, 'star')
        rnd = random.Random(seed)
        for i, (x, y, s) in enumerate(spots):
            b = sk.bone(f'tw{i}', 'root', x, y)
            sk.slot(f'tw{i}', b, 'star', w=96 * s, blend='additive', color=self.g['edge'] + 'ff')
            ph, per = rnd.random(), rnd.choice((1.0, 2.0, 4.0))

            def blink(tau, ph=ph, per=per):
                return math.sin(math.pi * (((tau / per) + ph) % 1.0)) ** 4

            env = lambda t: clamp((t - start) / 0.6)  # noqa: E731
            sk.both(b, 'scale', uniform(lambda t, f=blink: 0.25 + 0.75 * f(t - INTRO) * env(t)),
                    uniform(lambda t, f=blink: 0.25 + 0.75 * f(t)))
            sk.both(b, 'rotate', lambda t: 90 * (t - INTRO) / IDLE, lambda t: 90 * t / IDLE)
            sk.both(f'tw{i}', 'alpha', lambda t, f=blink: f(t - INTRO) * env(t), lambda t, f=blink: f(t))

    def burst(self, sk, x, y, w, h):
        self.add(sk, 'rays', 'glow')
        rb = sk.bone('rays', 'root', x, y)
        sk.slot('rays', rb, 'rays', w=w, blend='additive', color=self.g['rays'] + 'ff')
        sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
        sk.both('rays', 'alpha', lambda t: 0.3 * fade(t, 0.2, 0.8), lambda t: 0.3)
        gb = sk.bone('halo', 'root', x, y)
        sk.slot('halo', gb, 'glow', w=w * 0.85, h=h, blend='additive', color=self.g['halo'] + 'ff')
        sk.both('halo', 'alpha', lambda t: 0.6 * fade(t, 0.1, 0.6), lambda t: 0.5 + 0.1 * math.sin(2 * math.pi * t / IDLE))

    # --- feature screen ----------------------------------------------------
    def feature(self, variant):
        W, H = DESK if variant == 'desk' else MOB
        desk = variant == 'desk'
        sk = Skel(f'feature_{variant}', W, H, 1.0, self.out, intro=INTRO, idle=IDLE)

        def P(x, y):
            return x - W / 2, H / 2 - y

        lg = self.art['logo']
        lw = min(520 if desk else 560, (170 if desk else 200) * lg.width / lg.height)  # высокие лого не лезут на карточки
        self.logo(sk, *P(W / 2 + (90 if desk else 0), 100 if desk else 130), lw)
        if desk:
            self.mascot(sk, *P(170, 880), 700)
            cw, ch, gap = 350, 540, 28
            xs = [W / 2 + 90 + (k - 1) * (cw + gap) for k in range(3)]
            ys = [520] * 3
        else:
            cw, ch = 660, 270
            xs = [W / 2] * 3
            ys = [385, 680, 975]

        for k, key in enumerate(('fs', 'hw', 'col')):
            t0 = 0.6 + 0.25 * k
            cx, cy = P(xs[k], ys[k])
            name = f'card_{key}'
            sk.image(name, self.card(cw, ch))
            cb = sk.bone(name, 'root', cx, cy)
            sk.slot(name, cb, name, w=cw + 80)
            sk.both(cb, 'scale', uniform(lambda t, t0=t0: pop(t, t0, 0.6, 0.6) if t >= t0 else 0.01),
                    uniform(lambda t: 1.0))
            move(sk, cb, lambda t, t0=t0: (0, -80 * seg(t, t0, t0 + 0.6, 1, 0)),
                 lambda t, k=k: (0, bob(t, 5, IDLE, k * 0.3)))
            sk.both(name, 'alpha', lambda t, t0=t0: fade(t, t0, 0.3), lambda t: 1)
            self.add(sk, f't_{key}', f'd_{key}')
            if desk:
                tb = sk.bone(f'{name}_t', cb, 0, ch / 2 - 62)
                sk.slot(f'{name}_t', tb, f't_{key}', w=min(cw - 40, self.art[f't_{key}'].width))
                db = sk.bone(f'{name}_d', cb, 0, -ch / 2 + 100)
                sk.slot(f'{name}_d', db, f'd_{key}', w=min(cw - 50, self.art[f'd_{key}'].width))
                ix, iy, iw = 0, 25, cw - 40
            else:
                tb = sk.bone(f'{name}_t', cb, 150, ch / 2 - 58)
                sk.slot(f'{name}_t', tb, f't_{key}', w=min(320, self.art[f't_{key}'].width))
                db = sk.bone(f'{name}_d', cb, 150, -36)
                sk.slot(f'{name}_d', db, f'd_{key}', w=min(320, self.art[f'd_{key}'].width))
                ix, iy, iw = -185, 0, 250
            for part in (f'{name}_t', f'{name}_d'):
                sk.both(part, 'alpha', lambda t, t0=t0: fade(t, t0 + 0.3, 0.3), lambda t: 1)
            il = sk.bone(f'{name}_i', cb, ix, iy)
            if key == 'fs':
                for j, (dx, dy, rot) in enumerate(((-0.3, -8, 12), (0, 12, 0), (0.3, -8, -12))):
                    self.popin(sk, f'{name}_j{j}', 'joker', il, dx * iw, dy, iw * 0.42, t0 + 0.5 + 0.12 * j,
                               amp=4, phase=j / 3, rot=rot)
            elif key == 'hw':
                for j, reg in enumerate(('c_5x', 'c_minor', 'c_10x')):
                    self.popin(sk, f'{name}_c{j}', reg, il, (j - 1) * iw * 0.32, 0 if j == 1 else -4,
                               iw * 0.36, t0 + 0.5 + 0.12 * j, amp=4, phase=j / 3)
            else:
                self.popin(sk, f'{name}_s0', 'c_2x', il, -iw * 0.33, -10, iw * 0.27, t0 + 0.5, amp=3)
                self.popin(sk, f'{name}_s1', 'c_3x', il, iw * 0.33, -10, iw * 0.27, t0 + 0.62, amp=3, phase=0.5)
                self.popin(sk, f'{name}_m', 'c_col', il, 0, 6, iw * 0.46, t0 + 0.8, amp=5,
                           idle_scale=lambda t: breathe(t, 2.0, 0.04))

        self.tap(sk, 'tap_continue', *P(W / 2 + (90 if desk else 0), H - (48 if desk else 92)),
                 self.art['tap_continue'].width * (0.75 if desk else 0.8))
        self.twinkles(sk, [(-W * 0.3, H * 0.36, 0.9), (W * 0.36, H * 0.38, 0.7), (W * 0.42, -H * 0.3, 0.8),
                           (-W * 0.05, H * 0.44, 0.5)], seed=7 if desk else 8)
        sk.write()

    # --- bonus screens -----------------------------------------------------
    def bonus(self, kind, variant):
        W, H = DESK if variant == 'desk' else MOB
        desk = variant == 'desk'
        sk = Skel(f'bonus_{kind}_{variant}', W, H, 1.0, self.out, intro=INTRO, idle=IDLE)

        def P(x, y):
            return x - W / 2, H / 2 - y

        cx = W / 2 + (110 if desk else 0)
        ty = 190 if desk else 330
        self.burst(sk, *P(cx, ty), 1200 if desk else 900, 560 if desk else 520)
        if desk:
            self.mascot(sk, *P(180, 880), 720)
        big = f'big_{kind}'
        self.add(sk, big)
        tw = 900 if desk else 680
        tb = sk.bone('title', 'root', *P(cx, ty))
        sk.slot('title', tb, big, w=tw)
        sk.both(tb, 'scale', uniform(lambda t: pop(t, 0.15, 0.7, 0.2)), uniform(lambda t: breathe(t, 2.0, 0.025)))
        sk.both('title', 'alpha', lambda t: fade(t, 0.15, 0.25), lambda t: 1)

        row_y = 430 if desk else 640
        if kind == 'fs':
            self.add(sk, 'n_10')
            nb = sk.bone('count', 'root', *P(cx, ty + (150 if desk else 140)))
            sk.slot('count', nb, 'n_10', h=130 if desk else 120)
            sk.both(nb, 'scale', uniform(lambda t: pop(t, 0.7, 0.6, 0.2) if t >= 0.7 else 0.01),
                    uniform(lambda t: breathe(t, 1.0, 0.03)))
            row_y = 520 if desk else 720
            step, cw = (230, 200) if desk else (215, 190)
            for j in range(3):
                self.popin(sk, f'j{j}', 'joker', 'root', *P(cx + (j - 1) * step, row_y), cw, 0.9 + 0.18 * j,
                           amp=6, phase=j / 3, rot=(1 - j) * 8)
            rules = 'rules_fs'
        else:
            step, cw = (240, 210) if desk else (225, 200)
            for j, reg in enumerate(('c_5x', 'c_col', 'c_minor')):
                self.popin(sk, f'c{j}', reg, 'root', *P(cx + (j - 1) * step, row_y + 40), cw * (1.15 if j == 1 else 1),
                           0.8 + 0.18 * j, amp=5, phase=j / 3,
                           idle_scale=(lambda t: breathe(t, 2.0, 0.04)) if j == 1 else None)
            rules = 'rules_hw'
        self.add(sk, rules)
        rb = sk.bone('rules', 'root', *P(cx, (700 if desk else 960) if kind == 'fs' else (690 if desk else 900)))
        sk.slot('rules', rb, rules, w=min(self.art[rules].width * (0.85 if desk else 0.8), W - 60))
        sk.both('rules', 'alpha', lambda t: fade(t, 2.0, 0.4), lambda t: 1)
        self.tap(sk, 'tap_start', *P(cx, H - (52 if desk else 130)),
                 self.art['tap_start'].width * (0.75 if desk else 0.8), t0=2.4)
        self.twinkles(sk, [(-W * 0.2, H * 0.34, 0.9), (W * 0.36, H * 0.3, 0.8), (W * 0.4, -H * 0.2, 0.6)],
                      seed=11 if desk else 12)
        sk.write()


def version_atlas_pages(root):
    """Page names in every atlas get ?v=<hash of the PNG> (Telegram caches)."""
    import hashlib
    for d in os.listdir(root):
        ap = os.path.join(root, d, 'animation.atlas')
        if not os.path.exists(ap):
            continue
        lines = open(ap).read().split('\n')
        for i, ln in enumerate(lines):
            name = ln.split('?')[0]
            if name.endswith('.png') and ':' not in name:
                ver = hashlib.md5(open(os.path.join(root, d, name), 'rb').read()).hexdigest()[:8]
                lines[i] = f'{name}?v={ver}'
        open(ap, 'w').write('\n'.join(lines))


if __name__ == '__main__':
    for key in sys.argv[2:] or list(GAMES):
        game = Game(key)
        os.makedirs(game.out, exist_ok=True)
        for v in ('desk', 'mob'):
            game.feature(v)
            game.bonus('fs', v)
            game.bonus('hw', v)
        version_atlas_pages(game.out)
        print(key, '->', game.out)
