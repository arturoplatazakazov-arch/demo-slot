"""Volt Coins — feature (preview) screen + bonus (Hold & Win) screen as
Spine 4.1 skeletons, same contract as scripts/lucky_joker_3h3_screens.py:
a full-screen skeleton authored on the game's design canvas (origin = canvas
centre, 1 unit = 1 design px, y up), `intro` (3s) -> `idle` (4s seamless loop,
first idle frame == last intro frame). Four variants: feature/bonus x
desk (1920x1040) / mob (800x1450). The game's background is NOT in the
skeleton — slot.js puts bg_desk/bg_mob under the canvas (cover).

Art is the game's own: logo, coin states (the face value is printed here the
same way the client prints it in game), symbols, the Tesla coil, the jackpot
ladder rendered from the seed's values, and the ChatGPT-drawn popup banners
(front/img/volt-coins/popups/) when they exist — titles fall back to text
drawn here in the game's gold/cyan style.

Copy matches app/seed/volt_coins.py: coins land with a face value (x1..x15)
or MINI/MINOR/MAJOR; three coins in a line open Hold & Win; coins stay, every
other cell respins; a new coin resets 3 respins; 9/9 pays GRAND.

Usage:
  python scripts/volt_coins_screens.py <fonts_dir> [out_dir]
  fonts_dir: baloo.ttf, robotomono.ttf (front/fonts woff2 -> ttf via fontTools)
"""

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
ART_DIR = os.path.join(ROOT, 'front', 'img', 'volt-coins')
FONTS = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ART_DIR, 'screens')

INTRO = 3.0
IDLE = 4.0
DESK = (1920, 1040)
MOB = (800, 1450)

JACKPOTS = [('MINI', 20, 'e0915a'), ('MINOR', 50, 'd6dee9'), ('MAJOR', 250, 'ffc93c'), ('GRAND', 1000, 'eaf8ff')]


# --------------------------------------------------------------------------
# source art

def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def art(rel):
    return trim(Image.open(os.path.join(ART_DIR, rel)).convert('RGBA'))


def popup(name):
    p = os.path.join(ART_DIR, 'popups', name + '.webp')
    return trim(Image.open(p).convert('RGBA')) if os.path.exists(p) else None


GOLD = [(0, hexc('fff8d0')), (0.45, hexc('ffd04a')), (1, hexc('c97a10'))]
VOLT = [(0, hexc('ffffff')), (0.5, hexc('bff0ff')), (1, hexc('39b8ff'))]
CREAM = [(0, hexc('ffffff')), (1, hexc('e3f3ff'))]
INK = '070b26'


def title(text, size, fill=GOLD, glow='39b8ff', stroke=INK):
    return text_img(text, font('baloo', size, 800), fill, stroke=stroke, stroke_w=max(3, size // 10),
                    glow=glow, glow_r=max(6, size // 5), shadow='000010')


def lines(rows, size, fill=CREAM, gap=0.12):
    ims = [text_img(r, font('baloo', size, 700), fill, stroke=INK, stroke_w=max(3, size // 9),
                    glow=None, shadow='00000a') for r in rows]
    w = max(i.width for i in ims)
    step = int(size * (1 + gap))
    out = Image.new('RGBA', (w, step * (len(ims) - 1) + ims[-1].height))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


GLYPH_DIR = os.path.join(ART_DIR, 'glyphs')
USE_GLYPHS = False  # glyph faces rejected by the client (too glossy) — text faces, as in game


def glyph_label(label, core_h):
    """The face composed from the ChatGPT glyph sprites, same metrics as
    slot.js glyphRow (core-aligned baseline, glows overlapping)."""
    import json
    meta = json.load(open(os.path.join(GLYPH_DIR, 'glyphs.json')))
    chars = [label.lower()] if label.lower() in meta else list(label.lower())
    digits = [meta[c] for c in '0123456789' if c in meta]
    digit_core = sum((g['cb'] - g['ct']) * g['h'] for g in digits) / len(digits)
    parts = []
    for ch in chars:
        g = meta[ch]
        # digits and x share one scale (x stays smaller, as drawn); a word by its own core
        h = core_h * g['h'] / digit_core if len(ch) == 1 else core_h / (g['cb'] - g['ct'])
        w = h * g['w'] / g['h']
        im = Image.open(os.path.join(GLYPH_DIR, ch + '.webp')).convert('RGBA').resize((round(w), round(h)), Image.LANCZOS)
        parts.append((im, g, w, h))
    total = sum((g['cr'] - g['cl']) * w * 0.85 + w * 0.15 for _, g, w, _ in parts)
    H = max(h for _, _, _, h in parts)
    out = Image.new('RGBA', (int(total + max(w for _, _, w, _ in parts)), int(H * 1.6)))
    x = out.width / 2 - total / 2
    base = out.height / 2 + core_h / 2
    for im, g, w, h in parts:
        x -= g['cl'] * w * 0.85
        out.alpha_composite(im, (round(x), round(base - g['cb'] * h)))
        x += w - (1 - g['cr']) * w * 0.85
    return trim(out)


def coin_with(art_name, label, tier=False):
    """A blank coin state with its face on top — the game's own glyph sprites
    when present (what the reels show), else text drawn here."""
    coin = art(f'symbols/{art_name}.png')
    if USE_GLYPHS and os.path.exists(os.path.join(GLYPH_DIR, 'glyphs.json')):
        t = glyph_label(label, coin.height * (0.3 if tier else 0.36))
        k = min(1.0, coin.width * (0.8 if tier else 0.66) / t.width)
        t = t.resize((round(t.width * k), round(t.height * k)), Image.LANCZOS)
        out = coin.copy()
        out.alpha_composite(t, ((out.width - t.width) // 2, (out.height - t.height) // 2))
        return out
    size = int(coin.height * (0.15 if tier else (0.27 if len(label) <= 2 else 0.22)))
    fnt = font('baloo', size, 800) if tier else font('robotomono', size)
    t = text_img(label, fnt, [(0, hexc('fffbe0')), (1, hexc('ffd76a'))], stroke=INK,
                 stroke_w=max(3, size // 8), glow='ffc93c', glow_r=max(4, size // 5), shadow='000010', track=-2)
    out = coin.copy()
    out.alpha_composite(t, ((out.width - t.width) // 2, (out.height - t.height) // 2))
    return out


def panel(w, h, r=34, edge='39d8ff', glow=True):
    """Dark indigo glass card with a gold rim and a cyan inner light."""
    pad = 40
    im = Image.new('RGBA', (w + 2 * pad, h + 2 * pad))
    d = ImageDraw.Draw(im)
    if glow:
        g = Image.new('L', im.size)
        ImageDraw.Draw(g).rounded_rectangle([pad, pad, pad + w, pad + h], r, fill=200)
        g = g.filter(ImageFilter.GaussianBlur(18))
        glow_im = Image.new('RGBA', im.size, hexc(edge)[:3] + (0,))
        glow_im.putalpha(g.point(lambda v: v // 3))
        im.alpha_composite(glow_im)
    body = Image.new('RGBA', (w, h))
    bd = ImageDraw.Draw(body)
    for y in range(h):
        k = y / h
        c = (int(18 + 10 * (1 - k)), int(26 + 18 * (1 - k)), int(70 + 40 * (1 - k)), 236)
        bd.line([(0, y), (w, y)], fill=c)
    mask = Image.new('L', (w, h))
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    body.putalpha(mask)
    im.alpha_composite(body, (pad, pad))
    d.rounded_rectangle([pad, pad, pad + w, pad + h], r, outline=hexc('ffc93c'), width=4)
    d.rounded_rectangle([pad + 6, pad + 6, pad + w - 6, pad + h - 6], r - 6, outline=hexc(edge)[:3] + (150,), width=2)
    return im


def bolt(w, h, seed, rough=0.7, width=6):
    rnd = random.Random(seed)
    sc = 2
    m = Image.new('L', (w * sc, h * sc))
    d = ImageDraw.Draw(m)
    n = 28
    pts, y = [], 0.0
    for i in range(n + 1):
        y = clamp(y + rnd.uniform(-rough, rough), -1, 1) * 0.85
        taper = math.sin(math.pi * i / n) ** 0.5
        pts.append((i / n * w * sc, h * sc / 2 + y * h * sc * 0.34 * taper))
    d.line(pts, fill=255, width=width * sc, joint='curve')
    m = m.resize((w, h), Image.LANCZOS)
    glow = m.filter(ImageFilter.GaussianBlur(h * 0.09)).point(lambda v: min(255, v * 3))
    from PIL import ImageChops
    a = ImageChops.lighter(m, glow.point(lambda v: v * 2 // 3))
    fade = Image.new('L', (w, 1))
    fade.putdata([int(255 * clamp(min(x, w - 1 - x) / (w * 0.05))) for x in range(w)])
    a = ImageChops.multiply(a, fade.resize((w, h)))
    out = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    out.putalpha(a)
    return out


def star4(size=96):
    s = spark(size, max(6, size // 7))
    im = Image.new('RGBA', (size, size))
    im.alpha_composite(s, (0, (size - s.height) // 2))
    im.alpha_composite(s.rotate(90, expand=True), ((size - s.height) // 2, 0))
    im.alpha_composite(soft_glow(size // 2), (size // 4, size // 4))
    return im


def jackpot_plate(name, mult, col):
    """One ladder plate like the game's DOM plate: tier tab + 'x1000'."""
    w, h = 300, 120
    im = Image.new('RGBA', (w + 40, h + 50))
    d = ImageDraw.Draw(im)
    x0, y0 = 20, 34
    poly = [(x0 + 18, y0), (x0 + w - 18, y0), (x0 + w, y0 + h / 2), (x0 + w - 18, y0 + h), (x0 + 18, y0 + h), (x0, y0 + h / 2)]
    d.polygon(poly, fill=hexc(col))
    inner = [(x0 + 22, y0 + 5), (x0 + w - 22, y0 + 5), (x0 + w - 6, y0 + h / 2), (x0 + w - 22, y0 + h - 5),
             (x0 + 22, y0 + h - 5), (x0 + 6, y0 + h / 2)]
    d.polygon(inner, fill=(10, 15, 48, 255))
    tab = text_img(name, font('baloo', 30, 800), [(0, hexc('ffffff')), (1, hexc(col))], stroke=INK, stroke_w=4,
                   glow=None, shadow=None)
    d.rounded_rectangle([x0 + w / 2 - tab.width / 2 - 14, 4, x0 + w / 2 + tab.width / 2 + 14, 44], 8,
                        fill=(16, 24, 70, 255), outline=hexc(col), width=3)
    im.alpha_composite(tab, (int(x0 + w / 2 - tab.width / 2), 6))
    val = text_img(f'x{mult}', font('robotomono', 58), [(0, hexc('ffffff')), (1, hexc(col))], stroke=INK,
                   stroke_w=4, glow=col, glow_r=10, shadow=None, track=-2)
    im.alpha_composite(val, (int(x0 + w / 2 - val.width / 2), int(y0 + h / 2 - val.height / 2)))
    return trim(im)


def soft(im, w):
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


ART = {
    'logo': art('img/logo.png'),
    'coil': art('img/coil.png'),
    'glow': soft_glow(256),
    'star': star4(96),
    'rays': rays(560, n=16),
    'wild': art('symbols/wild.png'),
    'seven': art('symbols/seven.png'),
    'diamond': art('symbols/diamond.png'),
    'c_x5': coin_with('coin_value', 'x5'),
    'c_x15': coin_with('coin_value', 'x15'),
    'c_x2': coin_with('coin_value', 'x2'),
    'c_x10': coin_with('coin_value', 'x10'),
    'c_mini': coin_with('coin_mini', 'MINI', tier=True),
    'c_minor': coin_with('coin_minor', 'MINOR', tier=True),
    'c_major': coin_with('coin_major', 'MAJOR', tier=True),
    'bolt0': bolt(900, 120, 3),
    'bolt1': bolt(900, 120, 17),
    'bolt2': bolt(900, 120, 29),
    'zap0': bolt(260, 70, 5, rough=0.9, width=4),
    'zap1': bolt(260, 70, 9, rough=0.9, width=4),
}
for name, mult, col in JACKPOTS:
    ART[f'jp_{name.lower()}'] = jackpot_plate(name, mult, col)
ART['logo_flash'] = flash_of(ART['logo'], 0.9)

CARDS = [
    ('values', 'COIN VALUES', ['EVERY COIN LANDS', 'WITH A VALUE', 'OR A JACKPOT']),
    ('line', '3 IN A LINE', ['3 COINS ON A LINE', 'START', 'HOLD & WIN']),
    ('grand', 'FILL ALL 9', ['9 COINS ON THE GRID', 'WIN THE', 'GRAND JACKPOT']),
]
for key, head, desc in CARDS:
    ART[f't_{key}'] = title(head, 60)
    ART[f'd_{key}'] = lines(desc, 38)
ART['tap_continue'] = title('TAP TO CONTINUE', 56, fill=CREAM)
ART['tap_start'] = title('TAP TO START', 60, fill=CREAM)
ART['t_hw'] = popup('hold_and_win') or title('HOLD & WIN', 150)
ART['respins'] = title('RESPINS', 46, fill=VOLT, glow='39b8ff')
ART['rules'] = lines(['COINS STAY IN PLACE', 'A NEW COIN RESETS RESPINS TO 3', 'FILL ALL 9 CELLS FOR GRAND'], 40)


# --------------------------------------------------------------------------
# motion helpers (idle offsets are 0 at t=0 so idle starts where intro ends)

def bob(t, amp, period=IDLE, phase=0.0):
    return amp * (wave(t, period, phase) - wave(0, period, phase))


def pop(t, t0, dur=0.55, s0=0.3):
    return seg(t, t0, t0 + dur, s0, 1.0, out_back)


def fade(t, t0, dur=0.3):
    return seg(t, t0, t0 + dur, 0.0, 1.0, out_cubic)


def move(sk, bone, intro_fn, idle_fn):
    d = next(b for b in sk.bones if b['name'] == bone)
    bx, by = d.get('x', 0), d.get('y', 0)

    def absolute(f):
        return lambda t: (bx + f(t)[0], by + f(t)[1])

    sk.both(bone, 'translate', absolute(intro_fn), absolute(idle_fn))


def uniform(fn):
    return lambda t: (fn(t),) * 2


def add_art(sk, *keys):
    for k in keys:
        if k not in sk.images:
            sk.image(k, ART[k])


def popin(sk, name, region, parent, x, y, w, t0, amp=6, phase=0.0, alpha=1.0):
    """Scale-pop in at t0, then a gentle bob."""
    add_art(sk, region)
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: pop(t, t0) if t >= t0 else 0.01), uniform(lambda t: 1.0))
    move(sk, b, lambda t: (0, 0), lambda t: (0, bob(t, amp, IDLE, phase)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.25), lambda t: alpha)
    return b


def twinkles(sk, parent, spots, seed, start=1.4, tint='e6f7ffff'):
    add_art(sk, 'star')
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


def coil(sk, name, x, y, h, t0, flip=False):
    """The game's Tesla coil with sparks crackling off its ring (idle loop
    sparks every second, intro charges up)."""
    add_art(sk, 'coil', 'glow', 'zap0', 'zap1')
    c = ART['coil']
    w = h * c.width / c.height
    b = sk.bone(name, 'root', x, y, sx=-1 if flip else 1)
    sk.slot(name, b, 'coil', w=w)
    move(sk, b, lambda t: (0, -60 * seg(t, t0, t0 + 0.7, 1, 0)), lambda t: (0, 0))
    sk.both(name, 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1.0)
    ring_y = h / 2 - h * 85 / 1080
    hb = sk.bone(f'{name}_head', b, 0, ring_y)
    sk.slot(f'{name}_halo', hb, 'glow', w=w * 1.4, h=w * 0.7, blend='additive', color='5ac8ffff')
    charge = lambda t: seg(t, t0 + 0.6, t0 + 1.6, 0, 1)  # noqa: E731
    sk.both(f'{name}_halo', 'alpha', lambda t: 0.8 * charge(t),
            lambda t: 0.55 + 0.25 * math.sin(2 * math.pi * t / 1.0) ** 2)
    for i, ang in enumerate((20, 160, 70, 115)):
        zb = sk.bone(f'{name}_z{i}', hb, 0, 0, rot=ang)
        sk.slot(f'{name}_z{i}', zb, f'zap{i % 2}', w=w * 0.55, x=w * 0.27, blend='additive', color='cdf3ffff')

        def flick(t, i=i):
            return 1.0 if int(t / 0.08) % 4 == i % 4 and math.sin(2 * math.pi * (t / 1.0 + i * 0.25)) > 0.2 else 0.0
        sk.both(f'{name}_z{i}', 'alpha', lambda t, f=flick: f(t) * charge(t), lambda t, f=flick: f(t))


# --------------------------------------------------------------------------
# feature screen

def build_feature(variant):
    W, H = DESK if variant == 'desk' else MOB
    sk = Skel(f'feature_{variant}', W, H, 1.0, OUT, intro=INTRO, idle=IDLE)

    def P(x, y):  # design px (top-left origin) -> skeleton units
        return x - W / 2, H / 2 - y

    add_art(sk, 'logo', 'logo_flash')
    desk = variant == 'desk'
    lw = 760 if desk else 620
    lx, ly = P(W / 2, 110 if desk else 170)
    lb = sk.bone('logo', 'root', lx, ly)
    sk.slot('logo', lb, 'logo', w=lw)
    sk.slot('logo_flash', lb, 'logo_flash', w=lw, blend='additive')
    sk.both(lb, 'scale', uniform(lambda t: pop(t, 0.1, 0.7, 0.4)), uniform(lambda t: breathe(t, IDLE, 0.02)))
    sk.both('logo', 'alpha', lambda t: fade(t, 0.1, 0.3), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: seg(t, 0.4, 0.9, 0.9, 0) if t >= 0.4 else 0.0,
            lambda t: 0.35 * max(0.0, math.sin(2 * math.pi * (t - 1.5) / IDLE)) ** 8)

    if desk:
        coil(sk, 'coilL', *P(150, 640), 620, 0.2)
        coil(sk, 'coilR', *P(W - 150, 640), 620, 0.35, flip=True)
        card_w, card_h, gap = 400, 560, 30
        xs = [W / 2 + (k - 1) * (card_w + gap) for k in range(3)]
        ys = [600] * 3
    else:
        card_w, card_h = 660, 290
        xs = [W / 2] * 3
        ys = [400, 700, 1000]

    for k, (key, _, _) in enumerate(CARDS):
        t0 = 0.6 + 0.25 * k
        cx, cy = P(xs[k], ys[k])
        name = f'card_{key}'
        sk.image(name, panel(card_w, card_h))
        cb = sk.bone(name, 'root', cx, cy)
        sk.slot(name, cb, name, w=card_w + 80)
        sk.both(cb, 'scale', uniform(lambda t, t0=t0: pop(t, t0, 0.6, 0.6) if t >= t0 else 0.01),
                uniform(lambda t: 1.0))
        move(sk, cb, lambda t, t0=t0: (0, -80 * seg(t, t0, t0 + 0.6, 1, 0)), lambda t, k=k: (0, bob(t, 5, IDLE, k * 0.3)))
        sk.both(name, 'alpha', lambda t, t0=t0: fade(t, t0, 0.3), lambda t: 1)
        add_art(sk, f't_{key}', f'd_{key}')
        if desk:
            tb = sk.bone(f'{name}_t', cb, 0, card_h / 2 - 70)
            sk.slot(f'{name}_t', tb, f't_{key}', w=min(card_w - 40, ART[f't_{key}'].width))
            db = sk.bone(f'{name}_d', cb, 0, -card_h / 2 + 110)
            sk.slot(f'{name}_d', db, f'd_{key}', w=min(card_w - 60, ART[f'd_{key}'].width))
            ix, iy, iw = 0, 20, card_w - 60
        else:
            tb = sk.bone(f'{name}_t', cb, 130, card_h / 2 - 60)
            sk.slot(f'{name}_t', tb, f't_{key}', w=min(330, ART[f't_{key}'].width))
            db = sk.bone(f'{name}_d', cb, 130, -30)
            sk.slot(f'{name}_d', db, f'd_{key}', w=min(330, ART[f'd_{key}'].width))
            ix, iy, iw = -170, 0, 300
        for part in (f'{name}_t', f'{name}_d'):
            sk.both(part, 'alpha', lambda t, t0=t0: fade(t, t0 + 0.3, 0.3), lambda t: 1)
        illus = sk.bone(f'{name}_i', cb, ix, iy)
        if key == 'values':
            for j, (reg, dx, rot) in enumerate((('c_x5', -0.3, 10), ('c_mini', 0.0, 0), ('c_x15', 0.3, -10))):
                add_art(sk, reg)
                b = sk.bone(f'{name}_c{j}', illus, dx * iw, 10 if j == 1 else -6, rot=rot)
                sk.slot(f'{name}_c{j}', b, reg, w=iw * 0.42)
                tj = t0 + 0.5 + 0.12 * j
                sk.both(b, 'scale', uniform(lambda t, tj=tj: pop(t, tj) if t >= tj else 0.01),
                        uniform(lambda t, j=j: breathe(t, 2.0, 0.03) if j == 1 else 1.0))
        elif key == 'line':
            add_art(sk, 'c_x2', 'c_x10', 'c_major', 'bolt0', 'bolt1', 'bolt2')
            for j, reg in enumerate(('c_x2', 'c_major', 'c_x10')):
                b = sk.bone(f'{name}_c{j}', illus, (j - 1) * iw * 0.33, 0)
                sk.slot(f'{name}_c{j}', b, reg, w=iw * 0.34)
                tj = t0 + 0.5 + 0.12 * j
                sk.both(b, 'scale', uniform(lambda t, tj=tj: pop(t, tj) if t >= tj else 0.01), uniform(lambda t: 1.0))
            beam = sk.bone(f'{name}_beam', illus, 0, 0)
            for j in range(3):
                sk.slot(f'{name}_b{j}', beam, f'bolt{j}', w=iw * 1.05, h=iw * 0.14, blend='additive', color='9fe6ffff')

                def bolt_a(t, j=j):
                    return 1.0 if int(t / 0.09) % 3 == j else 0.15
                sk.both(f'{name}_b{j}', 'alpha', lambda t, f=bolt_a, t0=t0: f(t) * fade(t, t0 + 1.0, 0.2),
                        lambda t, f=bolt_a: f(t))
            sk.both(beam, 'scale', lambda t, t0=t0: (max(0.01, seg(t, t0 + 1.0, t0 + 1.3, 0.01, 1.0)), 1.0),
                    lambda t: (1.0, 1.0))
        else:  # grand
            for j, (nm, _, _) in enumerate(JACKPOTS):
                reg = f'jp_{nm.lower()}'
                add_art(sk, reg)
                if desk:
                    px, py, pw = (j % 2 - 0.5) * 168, 60 - (j // 2) * 120, 160
                else:
                    px, py, pw = (j % 2 - 0.5) * 150, 55 - (j // 2) * 95, 140
                b = sk.bone(f'{name}_j{j}', illus, px, py)
                sk.slot(f'{name}_j{j}', b, reg, w=pw * (1.15 if nm == 'GRAND' else 1.0))
                tj = t0 + 0.5 + 0.1 * j
                sk.both(b, 'scale', uniform(lambda t, tj=tj: pop(t, tj) if t >= tj else 0.01),
                        uniform(lambda t, j=j: breathe(t, 2.0, 0.04) if j == 3 else 1.0))

    add_art(sk, 'tap_continue')
    tx, ty = P(W / 2, H - (90 if desk else 240))
    tb = sk.bone('tap', 'root', tx, ty)
    sk.slot('tap', tb, 'tap_continue', w=ART['tap_continue'].width * (0.9 if desk else 0.8))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.4), lambda t: 0.55 + 0.45 * (1 + math.cos(2 * math.pi * t / 2.0)) / 2)
    sk.both(tb, 'scale', uniform(lambda t: 1.0), uniform(lambda t: 1 + 0.03 * (1 + math.cos(2 * math.pi * t / 2.0)) / 2))
    spots = [(-W * 0.3, H * 0.33, 0.9), (W * 0.32, H * 0.36, 0.7), (-W * 0.12, H * 0.42, 0.6), (W * 0.18, -H * 0.3, 0.8),
             (-W * 0.36, -H * 0.2, 0.6), (W * 0.4, -H * 0.05, 0.7)]
    twinkles(sk, 'root', spots, seed=7 if desk else 8)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# bonus screen (Hold & Win)

def build_bonus(variant):
    W, H = DESK if variant == 'desk' else MOB
    desk = variant == 'desk'
    sk = Skel(f'bonus_{variant}', W, H, 1.0, OUT, intro=INTRO, idle=IDLE)

    def P(x, y):
        return x - W / 2, H / 2 - y

    add_art(sk, 'rays', 'glow')
    cx, cy = P(W / 2, 260 if desk else 400)
    rb = sk.bone('rays', 'root', cx, cy)
    sk.slot('rays', rb, 'rays', w=1300 if desk else 900, blend='additive', color='5ac8ffff')
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both('rays', 'alpha', lambda t: 0.35 * fade(t, 0.2, 0.8), lambda t: 0.35)
    gb = sk.bone('halo', 'root', cx, cy)
    sk.slot('halo', gb, 'glow', w=1100 if desk else 760, h=600 if desk else 520, blend='additive', color='2f7dffff')
    sk.both('halo', 'alpha', lambda t: 0.6 * fade(t, 0.1, 0.6), lambda t: 0.5 + 0.1 * math.sin(2 * math.pi * t / IDLE))

    add_art(sk, 't_hw')
    tw = 980 if desk else 700
    tb = sk.bone('title', 'root', cx, cy)
    sk.slot('title', tb, 't_hw', w=tw)
    sk.both(tb, 'scale', uniform(lambda t: pop(t, 0.15, 0.7, 0.2)), uniform(lambda t: breathe(t, 2.0, 0.025)))
    sk.both('title', 'alpha', lambda t: fade(t, 0.15, 0.25), lambda t: 1)

    # the live respin count sits in the title banner's empty panel (ChatGPT art;
    # panel fractions from front/img/volt-coins/popups/popups.json)
    meta_p = os.path.join(ART_DIR, 'popups', 'popups.json')
    banner = None
    if os.path.exists(meta_p):
        banner = __import__('json').load(open(meta_p)).get('hold_and_win')
    if banner:
        bw, bh = banner['size']
        pn = banner['panel']
        th = tw * bh / bw
        sk.bone('count', tb, (pn['l'] + pn['w'] * 0.32 - 0.5) * tw, (0.5 - (pn['t'] + pn['h'] / 2)) * th)
        add_art(sk, 'respins')
        rsb = sk.bone('respins', tb, (pn['l'] + pn['w'] * 0.62 - 0.5) * tw, (0.5 - (pn['t'] + pn['h'] / 2)) * th)
        sk.slot('respins', rsb, 'respins', w=pn['w'] * tw * 0.42)
        sk.both('respins', 'alpha', lambda t: fade(t, 1.2, 0.25), lambda t: 1)

    if desk:
        coil(sk, 'coilL', *P(150, 640), 620, 0.2)
        coil(sk, 'coilR', *P(W - 150, 640), 620, 0.35, flip=True)

    # the coin line that opened the round, with the lightning beam across it
    lx, ly = P(W / 2, 560 if desk else 780)
    line = sk.bone('line', 'root', lx, ly)
    cw = 210 if desk else 200
    step = 250 if desk else 230
    add_art(sk, 'c_x5', 'c_mini', 'c_x15', 'bolt0', 'bolt1', 'bolt2')
    for j, reg in enumerate(('c_x5', 'c_mini', 'c_x15')):
        b = sk.bone(f'coin{j}', line, (j - 1) * step, 0)
        sk.slot(f'coin{j}', b, reg, w=cw)
        tj = 0.8 + 0.18 * j
        sk.both(b, 'scale', uniform(lambda t, tj=tj: pop(t, tj) if t >= tj else 0.01),
                uniform(lambda t, j=j: 1 + 0.03 * math.sin(2 * math.pi * (t / 2.0 + j / 3))))
    beam = sk.bone('beam', line, 0, 0)
    for j in range(3):
        sk.slot(f'beam{j}', beam, f'bolt{j}', w=step * 2.9, h=110, blend='additive', color='9fe6ffff')

        def bolt_a(t, j=j):
            return 1.0 if int(t / 0.09) % 3 == j else 0.15
        sk.both(f'beam{j}', 'alpha', lambda t, f=bolt_a: f(t) * fade(t, 1.5, 0.2), lambda t, f=bolt_a: f(t))
    sk.both(beam, 'scale', lambda t: (max(0.01, seg(t, 1.5, 1.8, 0.01, 1.0)), 1.0), lambda t: (1.0, 1.0))

    if not banner:  # fallback: own counter plate under the coin line
        sk.image('plate', panel(260 if desk else 240, 120, r=26))
        px, py = P(W / 2, 760 if desk else 1010)
        pb = sk.bone('plate', 'root', px, py)
        sk.slot('plate', pb, 'plate', w=(260 if desk else 240) + 80)
        sk.both(pb, 'scale', uniform(lambda t: pop(t, 1.6, 0.5, 0.4) if t >= 1.6 else 0.01), uniform(lambda t: 1.0))
        sk.both('plate', 'alpha', lambda t: fade(t, 1.6, 0.25), lambda t: 1)
        sk.bone('count', pb, -48, 0)
        add_art(sk, 'respins')
        rsb = sk.bone('respins', pb, 46, 0)
        sk.slot('respins', rsb, 'respins', w=150)
        sk.both('respins', 'alpha', lambda t: fade(t, 1.8, 0.25), lambda t: 1)

    add_art(sk, 'rules')
    rx, ry = P(W / 2, 790 if desk else 1060)
    rlb = sk.bone('rules', 'root', rx, ry)
    sk.slot('rules', rlb, 'rules', w=ART['rules'].width * (0.85 if desk else 0.8))
    sk.both('rules', 'alpha', lambda t: fade(t, 2.0, 0.4), lambda t: 1)

    add_art(sk, 'tap_start')
    tx, ty = P(W / 2, H - (110 if desk else 240))
    tpb = sk.bone('tap', 'root', tx, ty)
    sk.slot('tap', tpb, 'tap_start', w=ART['tap_start'].width * (0.8 if desk else 0.75))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.4, 0.4), lambda t: 0.55 + 0.45 * (1 + math.cos(2 * math.pi * t / 2.0)) / 2)
    spots = [(-W * 0.32, H * 0.3, 0.9), (W * 0.3, H * 0.34, 0.8), (-W * 0.25, -H * 0.1, 0.6), (W * 0.27, -H * 0.12, 0.7)]
    twinkles(sk, 'root', spots, seed=11 if desk else 12)
    sk.write()
    return sk


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
    print('screens ->', OUT)
