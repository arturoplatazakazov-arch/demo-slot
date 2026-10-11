"""Neon Reels — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Same idea as Gangsta Casino's pfs/bfs exports: a full-screen skeleton authored
on the game's design canvas (origin = canvas centre, 1 unit = 1 design px,
y up), `intro` (3s) -> `idle` (4s loop, first idle frame == last intro frame).
Four variants: feature/bonus x desk (1932x940) / mob (780x1416). The game's
background is NOT in the skeleton — the DOM layer under the canvas shows the
game's own bg jpg with object-fit: cover, so any aspect ratio is covered.

Every animated property is written as a python function of time, sampled at
30 fps and then thinned (a key is dropped when linear interpolation between its
neighbours reproduces it), so motion is authored like code, not keyframes.

Usage (sources are kept, gitignored, in assets_src_backup_20260728/neon-reels-screens/,
along with the psd-tools scripts that cut them out of the PSB):
  S=assets_src_backup_20260728/neon-reels-screens
  python scripts/neon_reels_screens.py $S/layers $S/fx $S/fonts front/img/neon-reels/screens
Needs Pillow only.

layers_dir — PNG layers cut from Neon_Reels_3x5_slot.psb (smart-object sources):
  geisha, samurai, logo, fs_plate, fs_input, t_free, t_spins, coin,
  wild_hi, skatter_hi, x100_coin_hi
fx_dir     — glow_soft.png, spark.png, flare_star.png (generic white fx)
fonts_dir  — luckiest.ttf, baloo.ttf (converted from front/fonts woff2)
"""

import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FPS = 30
INTRO = 3.0
IDLE = 4.0

LAYERS, FX, FONTS, OUT = sys.argv[1:5]


# --------------------------------------------------------------------------
# easing / timing helpers

def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def lerp(a, b, t):
    return a + (b - a) * t


def out_cubic(t):
    return 1 - (1 - t) ** 3


def out_back(t, s=1.9):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def in_out_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2


def seg(t, t0, t1, v0, v1, ease=out_cubic):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    return lerp(v0, v1, ease((t - t0) / (t1 - t0)))


def wave(t, period, phase=0.0):
    """sin over the loop, 0 at t=0 when phase=0."""
    return math.sin(2 * math.pi * (t / period + phase))


def flicker(t, t0, pattern=((0, 0), (0.04, 1), (0.08, 0.15), (0.13, 0.9), (0.18, 0.25), (0.23, 1))):
    """Neon tube ignition: stepwise on/off right after t0, 1 afterwards."""
    if t < t0:
        return 0.0
    dt = t - t0
    val = 0.0
    for at, v in pattern:
        if dt >= at:
            val = v
    return val


# --------------------------------------------------------------------------
# image building

def load(name):
    im = Image.open(os.path.join(LAYERS, name + '.png')).convert('RGBA')
    return im.crop(im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox())


def fx(name):
    return Image.open(os.path.join(FX, name + '.png')).convert('RGBA')


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)


def trim(im, pad=0):
    bb = im.getchannel('A').getbbox()
    im = im.crop(bb)
    if pad:
        c = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad))
        c.paste(im, (pad, pad))
        im = c
    return im


def vgrad(size, stops):
    w, h = size
    g = Image.new('RGBA', (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            (t0, c0), (t1, c1) = stops[i], stops[i + 1]
            if t0 <= t <= t1:
                k = (t - t0) / max(1e-6, t1 - t0)
                g.putpixel((0, y), tuple(int(lerp(c0[j], c1[j], k)) for j in range(4)))
                break
    return g.resize((w, h))


def hexc(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


GOLD = [(0, hexc('fff6b8')), (0.45, hexc('ffc928')), (1, hexc('ff7a00'))]
CYAN = [(0, hexc('e9ffff')), (0.5, hexc('5ff4ff')), (1, hexc('1aa8ff'))]
WHITE = [(0, hexc('ffffff')), (1, hexc('dff6ff'))]


def text_img(text, fnt, size, fill=GOLD, stroke='2a0638', stroke_w=None, glow='ff3fd0',
             glow_r=None, slant=0.12, track=0):
    f = font(fnt, size)
    stroke_w = stroke_w if stroke_w is not None else max(2, size // 9)
    glow_r = glow_r if glow_r is not None else max(4, size // 5)
    pad = stroke_w + glow_r * 3 + 10
    # measure with tracking
    widths = [f.getbbox(ch)[2] if ch != ' ' else size * 0.32 for ch in text]
    w = int(sum(widths) + track * (len(text) - 1)) + pad * 2
    h = int(size * 1.35) + pad * 2
    mask = Image.new('L', (w, h))
    smask = Image.new('L', (w, h))
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x = pad
    for ch, cw in zip(text, widths):
        d.text((x, pad), ch, font=f, fill=255)
        ds.text((x, pad), ch, font=f, fill=255, stroke_width=stroke_w, stroke_fill=255)
        x += cw + track
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(glow_r))
        gl = gl.point(lambda a: min(255, int(a * 1.6)))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    out.paste(Image.new('RGBA', (w, h), hexc(stroke)), (0, 0), smask)
    bb = mask.getbbox()
    grad = vgrad((w, bb[3] - bb[1]), fill)
    fill_im = Image.new('RGBA', (w, h))
    fill_im.paste(grad, (0, bb[1]))
    out.paste(fill_im, (0, 0), mask)
    if slant:
        out = out.transform(out.size, Image.AFFINE, (1, slant, -slant * h / 2, 0, 1, 0), Image.BICUBIC)
    return trim(out)


def octagon(w, h, c):
    return [(c, 0), (w - c, 0), (w, c), (w, h - c), (w - c, h), (c, h), (0, h - c), (0, c)]


def inset(pts, w, h, k):
    cx, cy = w / 2, h / 2
    return [(cx + (x - cx) * (1 - 2 * k / w), cy + (y - cy) * (1 - 2 * k / h)) for x, y in pts]


def neon_panel(w, h, outer='ff2fd0', inner='35e8ff', fill_top='1b0d3d', fill_bot='0a0620', alpha=235):
    """Chamfered neon card (body) + its additive glow layer, both w x h + pad."""
    pad = 40
    W, H = w + 2 * pad, h + 2 * pad
    c = int(min(w, h) * 0.12)
    pts = [(x + pad, y + pad) for x, y in octagon(w, h, c)]
    body = Image.new('RGBA', (W, H))
    m = Image.new('L', (W, H))
    ImageDraw.Draw(m).polygon(pts, fill=255)
    g = vgrad((W, H), [(0, hexc(fill_top, alpha)), (1, hexc(fill_bot, alpha))])
    body.paste(g, (0, 0), m)
    # faint inner grid, synthwave style
    grid = Image.new('L', (W, H))
    gd = ImageDraw.Draw(grid)
    for gy in range(pad, H - pad, 22):
        gd.line([(pad, gy), (W - pad, gy)], fill=22)
    for gx in range(pad, W - pad, 22):
        gd.line([(gx, pad), (gx, H - pad)], fill=22)
    grid = ImageChops.multiply(grid, m)
    body.paste(Image.new('RGBA', (W, H), hexc('8a5cff')), (0, 0), grid)
    lines = Image.new('RGBA', (W, H))
    ld = ImageDraw.Draw(lines)
    ld.line(pts + [pts[0]], fill=hexc(outer), width=6, joint='curve')
    ip = [(x + pad, y + pad) for x, y in inset(octagon(w, h, c), w, h, 11)]
    ld.line(ip + [ip[0]], fill=hexc(inner), width=3, joint='curve')
    body.alpha_composite(lines)
    # glow = blurred lines, bright core
    glow = lines.filter(ImageFilter.GaussianBlur(9))
    glow2 = lines.filter(ImageFilter.GaussianBlur(3))
    glow.alpha_composite(glow2)
    a = glow.getchannel('A').point(lambda v: min(255, int(v * 1.8)))
    glow.putalpha(a)
    return body, glow


def neon_ribbon(w, h, top='ff4fd8', bot='8a1bd6', edge='ffd6fb'):
    pad = 24
    W, H = w + 2 * pad, h + 2 * pad
    c = h // 2
    pts = [(x + pad, y + pad) for x, y in [(c, 0), (w - c, 0), (w, h / 2), (w - c, h), (c, h), (0, h / 2)]]
    m = Image.new('L', (W, H))
    ImageDraw.Draw(m).polygon(pts, fill=255)
    im = Image.new('RGBA', (W, H))
    halo = m.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.8))
    im.paste(Image.new('RGBA', (W, H), hexc('ff2fd0')), (0, 0), halo)
    im.paste(vgrad((W, H), [(0, hexc(top)), (1, hexc(bot))]), (0, 0), m)
    ImageDraw.Draw(im).line(pts + [pts[0]], fill=hexc(edge), width=3)
    return im


def petal(w=46, h=30, col='ff8fcf'):
    im = Image.new('RGBA', (w * 4, h * 4))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, w * 4 - 1, h * 4 - 1], fill=hexc(col))
    d.ellipse([w * 4 * 0.12, h * 4 * 0.25, w * 4 * 0.7, h * 4 * 0.75], fill=hexc('ffc4e6'))
    d.polygon([(w * 4 - 1, h * 2 - 14), (w * 4 - 34, h * 2), (w * 4 - 1, h * 2 + 14)], fill=(0, 0, 0, 0))
    return im.resize((w, h), Image.LANCZOS)


def rays(size, n=16, col=(255, 255, 255)):
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    cx = cy = big / 2
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + 2 * math.pi / n * 0.42
        d.polygon([(cx, cy), (cx + big * math.cos(a0), cy + big * math.sin(a0)),
                   (cx + big * math.cos(a1), cy + big * math.sin(a1))], fill=255)
    m = m.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(size / 140))
    # radial falloff
    fall = Image.radial_gradient('L').resize((size, size))  # 0 centre -> 255 edge
    fall = fall.point(lambda v: int(255 * clamp(1 - v / 200) ** 1.6))
    m = ImageChops.multiply(m, fall)
    im = Image.new('RGBA', (size, size), col + (0,))
    im.putalpha(m)
    return im


def beam(w, h, col):
    """Spotlight cone, apex on top."""
    m = Image.new('L', (w * 2, h))
    d = ImageDraw.Draw(m)
    d.polygon([(w - 6, 0), (w + 6, 0), (w * 2, h), (0, h)], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w / 6))
    fade = vgrad((w * 2, h), [(0, (0, 0, 0, 255)), (0.7, (0, 0, 0, 110)), (1, (0, 0, 0, 0))]).getchannel('A')
    m = ImageChops.multiply(m, fade)
    im = Image.new('RGBA', (w * 2, h), hexc(col, 0))
    im.putalpha(m)
    return im


def flash_of(im, k=1.0):
    """White silhouette (for additive flashes)."""
    a = im.getchannel('A').point(lambda v: int(v * k))
    out = Image.new('RGBA', im.size, (255, 255, 255, 0))
    out.putalpha(a)
    return out


# --------------------------------------------------------------------------
# skeleton builder

class Skel:
    def __init__(self, name, w, h, res):
        self.name, self.w, self.h, self.res = name, w, h, res
        self.bones = [{'name': 'root'}]
        self.slots = []
        self.atts = {}
        self.images = {}  # region -> PIL image (source, resized at pack time)
        self.need = {}  # region -> max (w, h) units used
        self.anims = {'intro': {'bones': {}, 'slots': {}}, 'idle': {'bones': {}, 'slots': {}}}
        self._bone_names = {'root'}

    def image(self, region, im):
        self.images[region] = im

    def bone(self, name, parent='root', x=0, y=0, rot=0, sx=1, sy=1):
        assert name not in self._bone_names, name
        b = {'name': name, 'parent': parent}
        if x:
            b['x'] = round(x, 2)
        if y:
            b['y'] = round(y, 2)
        if rot:
            b['rotation'] = round(rot, 2)
        if sx != 1:
            b['scaleX'] = sx
        if sy != 1:
            b['scaleY'] = sy
        self.bones.append(b)
        self._bone_names.add(name)
        return name

    def slot(self, name, bone, region, w=None, h=None, x=0, y=0, rot=0, blend=None, color=None):
        """Region attachment sized w (or h) in units, aspect from the image."""
        im = self.images[region]
        if w is None and h is None:
            w, h = im.width, im.height
        elif h is None:
            h = w * im.height / im.width
        elif w is None:
            w = h * im.width / im.height
        s = {'name': name, 'bone': bone, 'attachment': region}
        if blend:
            s['blend'] = blend
        if color:
            s['color'] = color
        self.slots.append(s)
        att = {'x': round(x, 2), 'y': round(y, 2), 'width': round(w, 2), 'height': round(h, 2)}
        if rot:
            att['rotation'] = rot
        self.atts[name] = {region: att}
        pw, ph = self.need.get(region, (0, 0))
        self.need[region] = (max(pw, w), max(ph, h))
        return name

    # -- timelines (sampled) --
    def _sample(self, fn, dur):
        n = int(round(dur * FPS))
        return [(k / FPS, fn(k / FPS)) for k in range(n + 1)]

    @staticmethod
    def _thin(samples, tol):
        def vals(v):
            return v if isinstance(v, tuple) else (v,)

        out = [samples[0]]
        i = 0
        n = len(samples)
        while i < n - 1:
            j = i + 1
            while j + 1 < n:
                t0, v0 = samples[i]
                t1, v1 = samples[j + 1]
                ok = True
                for k in range(i + 1, j + 1):
                    tk, vk = samples[k]
                    f = (tk - t0) / (t1 - t0)
                    for a, b, c in zip(vals(v0), vals(v1), vals(vk)):
                        if abs(lerp(a, b, f) - c) > tol:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
                j += 1
            out.append(samples[j])
            i = j
        # a constant timeline keeps just its first key
        if all(vals(v) == vals(out[0][1]) for _, v in out):
            out = out[:1]
        return out

    def anim(self, which, target, prop, fn):
        dur = INTRO if which == 'intro' else IDLE
        tol = {'translate': 0.25, 'scale': 0.0015, 'rotate': 0.08, 'alpha': 0.004}[prop]
        keys = self._thin(self._sample(fn, dur), tol)
        rows = []
        for t, v in keys:
            r = {}
            if t:
                r['time'] = round(t, 4)
            if prop in ('translate', 'scale'):
                r['x'], r['y'] = round(v[0], 4), round(v[1], 4)
            elif prop == 'alpha':
                r['value'] = round(clamp(v), 4)
            else:
                r['value'] = round(v, 3)
            rows.append(r)
        if prop == 'alpha':
            self.anims[which]['slots'].setdefault(target, {})['alpha'] = rows
        else:
            self.anims[which]['bones'].setdefault(target, {})[prop] = rows

    def both(self, target, prop, intro_fn, idle_fn):
        self.anim('intro', target, prop, intro_fn)
        self.anim('idle', target, prop, idle_fn)

    # -- output --
    def write(self):
        out = os.path.join(OUT, self.name)
        os.makedirs(out, exist_ok=True)
        # resize every region to its largest on-screen use x res
        regions = {}
        for r, im in self.images.items():
            if r not in self.need:
                continue
            w, h = self.need[r]
            tw = max(2, min(im.width, int(math.ceil(w * self.res))))
            th = max(2, int(round(tw * im.height / im.width)))
            regions[r] = im.resize((tw, th), Image.LANCZOS) if (tw, th) != im.size else im
        pages = pack(regions)
        atlas_lines = []
        for pi, (page, placed) in enumerate(pages):
            fname = 'animation.png' if pi == 0 else f'animation{pi + 1}.png'
            premultiply(page).save(os.path.join(out, fname), optimize=True)
            if atlas_lines:
                atlas_lines.append('')  # pages are separated by a blank line
            atlas_lines += [fname, f'size:{page.width},{page.height}', 'filter:Linear,Linear', 'pma:true']
            for r, (x, y, w, h) in placed.items():
                atlas_lines += [r, f'bounds:{x},{y},{w},{h}']
        with open(os.path.join(out, 'animation.atlas'), 'w') as f:
            f.write('\n'.join(atlas_lines) + '\n')
        data = {
            'skeleton': {'hash': self.name, 'spine': '4.1.24', 'x': -self.w / 2, 'y': -self.h / 2,
                         'width': self.w, 'height': self.h, 'fps': FPS, 'images': './images/'},
            'bones': self.bones,
            'slots': self.slots,
            'skins': [{'name': 'default', 'attachments': self.atts}],
            'animations': self.anims,
        }
        with open(os.path.join(out, 'animation.json'), 'w') as f:
            json.dump(data, f, separators=(',', ':'))
        print(self.name, 'bones', len(self.bones), 'slots', len(self.slots),
              'pages', [p.size for p, _ in pages])


def premultiply(im):
    r, g, b, a = im.split()
    r = ImageChops.multiply(r, a)
    g = ImageChops.multiply(g, a)
    b = ImageChops.multiply(b, a)
    return Image.merge('RGBA', (r, g, b, a))


def pack(regions, max_w=2048, max_h=2048, gap=2):
    """Shelf packer, tallest first; spills onto extra pages."""
    items = sorted(regions.items(), key=lambda kv: (-kv[1].height, -kv[1].width))
    pages = []
    while items:
        placed, left = {}, []
        x = y = shelf_h = 0
        used_w = used_h = 0
        for r, im in items:
            w, h = im.size
            if x + w > max_w:
                x, y, shelf_h = 0, y + shelf_h + gap, 0
            if y + h > max_h or w > max_w:
                left.append((r, im))
                continue
            placed[r] = (x, y, w, h)
            x += w + gap
            shelf_h = max(shelf_h, h)
            used_w, used_h = max(used_w, x), max(used_h, y + h)
        if not placed:
            raise SystemExit(f'region too big: {left[0][0]}')
        page = Image.new('RGBA', (used_w, used_h))
        for r, (px, py, w, h) in placed.items():
            page.paste(regions[r], (px, py))
        pages.append((page, placed))
        items = left
    return pages


# --------------------------------------------------------------------------
# shared art

ART = {
    'geisha': load('geisha'),
    'samurai': load('samurai'),
    'logo': load('logo'),
    'emblem': load('fs_plate'),
    'counter': load('fs_input'),
    't_free': load('t_free'),
    't_spins': load('t_spins'),
    'coin': load('coin'),
    'scatter': load('skatter_hi'),
    'wild': load('wild_hi'),
    'coinx': load('x100_coin_hi'),
    'glow': fx('glow_soft'),
    'spark': fx('spark'),
    'star': fx('flare_star'),
    'petal': petal(),
    'rays': rays(900),
    'beam': beam(220, 900, 'ffffff'),
}
ART['logo_flash'] = flash_of(ART['logo'], 0.85)
for k in ('scatter', 'wild', 'coinx', 'emblem'):
    ART[k + '_flash'] = flash_of(ART[k], 0.8)

CARDS = [
    ('scatter', 'FREE SPINS', '3+ SCATTERS'),
    ('wild', 'WILD', 'SUBSTITUTES ALL'),
    ('coinx', 'COIN MULTIPLIER', 'UP TO x100'),
]


def add_common(sk, keys):
    for k in keys:
        sk.image(k, ART[k])


def petals(sk, parent, count, area, seed, size=1.0, intro_from=1.4):
    """Falling sakura petals, seamless over the idle loop."""
    import random
    rnd = random.Random(seed)
    x0, x1, ytop, ybot = area
    for i in range(count):
        b = sk.bone(f'petal{i}', parent)
        sc = size * rnd.uniform(0.6, 1.15)
        sk.slot(f'petal{i}', b, 'petal', w=46 * sc)
        px = rnd.uniform(x0, x1)
        drift = rnd.uniform(-160, 60)
        sway = rnd.uniform(18, 40)
        ph = i / count + rnd.uniform(-0.04, 0.04)
        spin = rnd.choice([-1, 1]) * rnd.uniform(140, 300)

        def pos(tau, px=px, drift=drift, sway=sway, ph=ph):
            u = ((tau / IDLE) + ph) % 1.0
            return (px + drift * u + sway * math.sin(2 * math.pi * (u * 2 + ph)),
                    lerp(ytop, ybot, u))

        def alpha(tau, ph=ph):
            u = ((tau / IDLE) + ph) % 1.0
            return clamp(u / 0.08) * clamp((1 - u) / 0.1) * 0.9

        def rot(tau, ph=ph, spin=spin):
            u = ((tau / IDLE) + ph) % 1.0
            return spin * u

        env = lambda t: clamp((t - intro_from) / 0.8)
        sk.both(b, 'translate', lambda t, pos=pos: pos(t - INTRO), lambda t, pos=pos: pos(t))
        sk.both(b, 'rotate', lambda t, rot=rot: rot(t - INTRO), lambda t, rot=rot: rot(t))
        sk.both(f'petal{i}', 'alpha', lambda t, a=alpha: a(t - INTRO) * env(t), lambda t, a=alpha: a(t))


def stars(sk, parent, spots, seed):
    import random
    rnd = random.Random(seed)
    for i, (x, y, s) in enumerate(spots):
        b = sk.bone(f'star{i}', parent, x, y)
        sk.slot(f'star{i}', b, 'star', w=128 * s, blend='additive', color='ffd6ffff')
        ph = rnd.random()

        def tw(t, ph=ph):
            v = math.sin(math.pi * (((t / IDLE) * 2 + ph) % 1.0)) ** 6
            return v

        sk.both(b, 'scale', lambda t, tw=tw: (0.2, 0.2) if t < 2.4 else ((0.2 + 0.8 * tw(t - INTRO + IDLE)),) * 2,
                lambda t, tw=tw: (0.2 + 0.8 * tw(t),) * 2)
        sk.both(b, 'rotate', lambda t: 0, lambda t: 90 * t / IDLE)
        sk.both(f'star{i}', 'alpha', lambda t, tw=tw: clamp((t - 2.4) / 0.4) * tw(t - INTRO + IDLE),
                lambda t, tw=tw: tw(t))


def sparks(sk, parent, prefix, t0, n, radius, color, seed):
    import random
    rnd = random.Random(seed)
    for i in range(n):
        ang = 360 * i / n + rnd.uniform(-12, 12)
        r = radius * rnd.uniform(0.75, 1.2)
        b = sk.bone(f'{prefix}{i}', parent, rot=ang)
        sk.slot(f'{prefix}{i}', b, 'spark', w=34, blend='additive', color=color)
        rad = math.radians(ang)
        dur = rnd.uniform(0.4, 0.6)

        def tr(t, rad=rad, r=r, dur=dur):
            k = seg(t, t0, t0 + dur, 0, 1, out_cubic)
            return (math.cos(rad) * r * k, math.sin(rad) * r * k)

        sk.both(b, 'translate', tr, lambda t, tr=tr: tr(INTRO))
        sk.both(b, 'scale', lambda t, dur=dur: (seg(t, t0, t0 + dur, 2.2, 0.6), 1), lambda t: (0.6, 1))
        sk.both(f'{prefix}{i}', 'alpha',
                lambda t, dur=dur: 0 if t < t0 else seg(t, t0 + dur * 0.35, t0 + dur, 1, 0, lambda u: u),
                lambda t: 0)


def text_slot(sk, region, im, bone, w=None, h=None, x=0, y=0):
    sk.image(region, im)
    return sk.slot(region, bone, region, w=w, h=h, x=x, y=y)


def character(sk, name, region, x, bottom, h=None, w=None, from_x=0, t0=0.15, phase=0.0, flip=False):
    b = sk.bone(name + '_b', 'main', x, bottom, sx=-1 if flip else 1)
    im = ART[region]
    if h is None:
        h = w * im.height / im.width
    sk.slot(name, b, region, h=h, y=h / 2)
    sx0 = -1 if flip else 1
    sk.both(b, 'translate', lambda t: (seg(t, t0, t0 + 0.7, from_x, 0), 0), lambda t: (0, 0))
    sk.both(b, 'scale', lambda t: (1, 1),
            lambda t: (1 + 0.004 * wave(t, IDLE / 2, phase), 1 + 0.013 * wave(t, IDLE / 2, phase)))
    sk.both(name, 'alpha', lambda t: seg(t, t0, t0 + 0.35, 0, 1, lambda u: u), lambda t: 1)


def logo(sk, x, y, w, t0=0.45):
    b = sk.bone('logo_b', 'main', x, y)
    im = ART['logo']
    h = w * im.height / im.width
    sk.slot('logo_glow', b, 'glow', w=w * 1.5, h=h * 1.6, blend='additive', color='ff3fd0b0')
    sk.slot('logo', b, 'logo', w=w)
    sk.slot('logo_flash', b, 'logo_flash', w=w, blend='additive')
    sk.both(b, 'translate', lambda t: (0, seg(t, t0, t0 + 0.55, 140, 0, out_back)), lambda t: (0, 0))
    sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.55, 1.5, 1, out_back),) * 2,
            lambda t: (1 + 0.025 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.both('logo', 'alpha', lambda t: flicker(t, t0 + 0.05), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: 0 if t < t0 + 0.5 else seg(t, t0 + 0.5, t0 + 0.95, 1, 0),
            lambda t: 0.18 * max(0.0, math.sin(2 * math.pi * (t / IDLE))) ** 8)
    sk.both('logo_glow', 'alpha', lambda t: seg(t, t0 + 0.4, t0 + 0.9, 0, 1),
            lambda t: 0.75 + 0.25 * math.cos(2 * math.pi * t / 2))
    return b


def tap_text(sk, text, x, y, w):
    im = text_img(text, 'luckiest', 72, fill=WHITE, stroke='12052a', glow='35e8ff', slant=0)
    sk.image('t_tap', im)
    b = sk.bone('tap_b', 'main', x, y)
    sk.slot('tap', b, 't_tap', w=w)
    sk.both(b, 'scale', lambda t: (seg(t, 2.25, 2.7, 0.7, 1, out_back),) * 2,
            lambda t: (1 + 0.03 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.both('tap', 'alpha', lambda t: seg(t, 2.25, 2.55, 0, 1, lambda u: u),
            lambda t: 0.55 + 0.45 * math.cos(2 * math.pi * t / 2))


# --------------------------------------------------------------------------
# FEATURE screen

def feature(variant):
    desk = variant == 'desk'
    W, H = (1932, 940) if desk else (780, 1416)
    sk = Skel(f'feature_{variant}', W, H, 1.3 if desk else 1.15)
    add_common(sk, ['geisha', 'samurai', 'logo', 'logo_flash', 'glow', 'spark', 'star', 'petal',
                    'scatter', 'wild', 'coinx', 'scatter_flash', 'wild_flash', 'coinx_flash'])
    sk.bone('main')
    if desk:
        L = dict(logo=(0, 328, 450), card_y=14, card_x=340, panel=(300, 310), icon=(225, 38),
                 sub=(-100, 38), rib=(-170, 340, 68), cap=44, tap=(0, -345, 430),
                 geisha=(-700, -470, 830), samurai=(640, -470, 680),
                 petal_area=(-1000, 1000, 560, -560), stars=[(-300, 420, 0.5), (285, 255, 0.4),
                                                             (-170, 190, 0.35), (510, 160, 0.45), (-505, -60, 0.4)])
    else:
        L = dict(logo=(0, 565, 520), card_y=255, card_x=258, panel=(236, 255), icon=(176, 32),
                 sub=(-82, 28), rib=(-142, 252, 56), cap=32, tap=(0, -615, 470),
                 geisha=(-200, -708, 800), samurai=(175, -708, 610),
                 petal_area=(-430, 430, 780, -780), stars=[(-240, 660, 0.45), (230, 470, 0.4),
                                                           (-130, 395, 0.35), (370, 400, 0.4), (-370, 120, 0.35)])
    # characters behind everything else
    character(sk, 'samurai', 'samurai', L['samurai'][0], L['samurai'][1], w=L['samurai'][2],
              from_x=520 if desk else 420, t0=0.3, phase=0.25)
    character(sk, 'geisha', 'geisha', L['geisha'][0], L['geisha'][1], h=L['geisha'][2],
              from_x=-520 if desk else -420, t0=0.15)
    logo(sk, *L['logo'])

    pw, ph = L['panel']
    body, glow = neon_panel(int(pw * sk.res), int(ph * sk.res))
    pad_u = 40 / sk.res
    sk.image('panel', body)
    sk.image('panel_glow', glow)
    rw, rh = L['rib'][1], L['rib'][2]
    sk.image('ribbon', neon_ribbon(int(rw * sk.res), int(rh * sk.res)))
    rib_pad = 24 / sk.res
    for i, (icon, title, sub) in enumerate(CARDS):
        tc = 1.0 + 0.22 * i
        cx = (i - 1) * L['card_x']
        cb = sk.bone(f'card{i}', 'main', cx, L['card_y'])
        sk.slot(f'panel{i}', cb, 'panel', w=pw + 2 * pad_u, h=ph + 2 * pad_u)
        sk.slot(f'pglow{i}', cb, 'panel_glow', w=pw + 2 * pad_u, h=ph + 2 * pad_u, blend='additive')
        ib = sk.bone(f'icon{i}', cb, 0, L['icon'][1])
        sk.slot(f'iglow{i}', ib, 'glow', w=L['icon'][0] * 1.3, blend='additive', color='7a3cffaa')
        sk.slot(f'icon{i}', ib, icon, w=L['icon'][0] if icon != 'coinx' else L['icon'][0] * 0.88)
        sk.slot(f'iflash{i}', ib, icon + '_flash', w=L['icon'][0] if icon != 'coinx' else L['icon'][0] * 0.88,
                blend='additive')
        sb = sk.bone(f'sub{i}', cb, 0, L['sub'][0])
        sim = text_img(sub, 'luckiest', 64, fill=CYAN, stroke='0b0420', glow='1a6bff', slant=0.06)
        sk.image(f't_sub{i}', sim)
        sk.slot(f'sub{i}', sb, f't_sub{i}', h=L['sub'][1], w=min(pw * 0.86, L['sub'][1] * sim.width / sim.height))
        rb = sk.bone(f'rib{i}', cb, 0, L['rib'][0])
        sk.slot(f'rib{i}', rb, 'ribbon', w=rw + 2 * rib_pad, h=rh + 2 * rib_pad)
        cim = text_img(title, 'luckiest', 80, fill=GOLD, stroke='2a0638', glow=None, slant=0.08)
        sk.image(f't_cap{i}', cim)
        cap_h = L['cap']
        cap_w = min(rw * 0.8, cap_h * cim.width / cim.height)
        sk.slot(f'cap{i}', rb, f't_cap{i}', w=cap_w, y=2)

        # intro: card pops, neon border ignites, ribbon slides in, icon flashes
        sk.both(cb, 'scale', lambda t, tc=tc: (seg(t, tc, tc + 0.45, 0.2, 1, out_back),) * 2,
                lambda t: (1, 1))
        sk.both(cb, 'translate',
                lambda t, tc=tc: (0, seg(t, tc, tc + 0.45, -120, 0, out_back)),
                lambda t, i=i: (0, 7 * wave(t, IDLE, i / 3)))
        appear = lambda t, tc=tc: seg(t, tc, tc + 0.18, 0, 1, lambda u: u)
        for s in (f'panel{i}', f'icon{i}', f'sub{i}'):
            sk.both(s, 'alpha', appear, lambda t: 1)
        sk.both(f'pglow{i}', 'alpha', lambda t, tc=tc: flicker(t, tc + 0.1),
                lambda t, i=i: 0.7 + 0.3 * math.cos(2 * math.pi * (t / 2))
                if not (1.2 + i * 0.9 < t < 1.2 + i * 0.9 + 0.25) else
                flicker(t, 1.2 + i * 0.9, ((0, 0.2), (0.05, 1), (0.1, 0.35), (0.16, 1))))
        sk.both(f'iglow{i}', 'alpha', lambda t, tc=tc: seg(t, tc + 0.2, tc + 0.6, 0, 1),
                lambda t, i=i: 0.75 + 0.25 * math.cos(2 * math.pi * (t / IDLE * 2 + 0)))
        sk.both(f'iflash{i}', 'alpha', lambda t, tc=tc: 0 if t < tc + 0.3 else seg(t, tc + 0.3, tc + 0.7, 0.6, 0),
                lambda t, i=i: 0.5 * max(0.0, math.sin(2 * math.pi * (t / IDLE - 0.15 - i * 0.22) * 1.0)) ** 16)
        sk.both(ib, 'scale', lambda t: (1, 1), lambda t, i=i: (1 + 0.035 * (1 - math.cos(2 * math.pi * (t / 2))) / 2,) * 2)
        if icon == 'wild':
            sk.both(ib, 'rotate', lambda t: 0, lambda t: 3 * wave(t, IDLE))
        sk.both(rb, 'translate', lambda t, tc=tc: (0, seg(t, tc + 0.25, tc + 0.6, -40, 0, out_back)),
                lambda t: (0, 0))
        sk.both(rb, 'scale', lambda t, tc=tc: (seg(t, tc + 0.25, tc + 0.6, 0.3, 1, out_back), 1), lambda t: (1, 1))
        for s in (f'rib{i}', f'cap{i}'):
            sk.both(s, 'alpha', lambda t, tc=tc: seg(t, tc + 0.25, tc + 0.4, 0, 1, lambda u: u), lambda t: 1)
        sparks(sk, cb, f'spk{i}_', tc + 0.12, 9, (pw * 0.75) if desk else pw * 0.7,
               ['ff6fe0ff', '6ff3ffff', 'ffd36aff'][i], seed=10 + i)

    petals(sk, 'main', 12 if desk else 9, L['petal_area'], seed=7, size=1.0 if desk else 0.9)
    stars(sk, 'main', L['stars'], seed=3)
    tap_text(sk, 'TAP TO CONTINUE', *L['tap'])
    sk.write()


# --------------------------------------------------------------------------
# BONUS screen

def bonus(variant):
    desk = variant == 'desk'
    W, H = (1932, 940) if desk else (780, 1416)
    sk = Skel(f'bonus_{variant}', W, H, 1.3 if desk else 1.15)
    add_common(sk, ['geisha', 'samurai', 'logo', 'logo_flash', 'glow', 'spark', 'star', 'petal',
                    'emblem', 'emblem_flash', 'counter', 't_free', 't_spins', 'coin', 'rays', 'beam'])
    sk.bone('main')
    if desk:
        L = dict(logo=(0, 360, 340), title_y=205, free=(-148, 250), spins=(150, 300), rays=(0, 10, 980),
                 emblem=(0, -20, 375), counter=(0, -252, 300), tap=(0, -392, 380),
                 geisha=(700, -470, 860), samurai=(-660, -470, 760),
                 beams=[(-640, 470, -14), (-260, 470, -6), (260, 470, 6), (640, 470, 14)], beam_h=900,
                 coins=[(-330, 120, 0.55), (-400, -60, 0.7), (-300, -230, 0.5), (330, 150, 0.6),
                        (400, -40, 0.5), (310, -220, 0.65), (-210, 260, 0.4), (215, 270, 0.42)],
                 petal_area=(-1000, 1000, 560, -560))
    else:
        L = dict(logo=(0, 595, 400), title_y=432, free=(-132, 225), spins=(122, 270), rays=(0, 170, 820),
                 emblem=(0, 160, 410), counter=(0, -118, 290), tap=(0, -300, 380),
                 geisha=(225, -708, 650), samurai=(-175, -708, 540),
                 beams=[(-300, 708, -10), (300, 708, 10)], beam_h=1200,
                 coins=[(-270, 290, 0.5), (-300, 90, 0.6), (-240, -40, 0.45), (275, 300, 0.55),
                        (300, 80, 0.45), (250, -30, 0.6)],
                 petal_area=(-430, 430, 780, -780))
    # spotlight beams swinging from the ceiling
    for i, (bx, by, ang) in enumerate(L['beams']):
        b = sk.bone(f'beam{i}', 'main', bx, by, rot=ang)
        sk.slot(f'beam{i}', b, 'beam', h=L['beam_h'], y=-L['beam_h'] / 2, blend='additive',
                color=['ff4fd8ff', '4fe8ffff'][i % 2])
        on = 0.12 + 0.12 * i
        sk.both(b, 'rotate', lambda t: 0, lambda t, i=i: 7 * wave(t, IDLE, i * 0.25))
        sk.both(f'beam{i}', 'alpha', lambda t, on=on: 0.42 * flicker(t, on),
                lambda t, i=i: 0.34 + 0.08 * math.cos(2 * math.pi * (t / 1.0)))
    character(sk, 'samurai', 'samurai', L['samurai'][0], L['samurai'][1], w=L['samurai'][2],
              from_x=-520 if desk else -420, t0=0.35, phase=0.25)
    character(sk, 'geisha', 'geisha', L['geisha'][0], L['geisha'][1], h=L['geisha'][2],
              from_x=520 if desk else 420, t0=0.2, flip=True)

    # rays + glow behind the emblem
    rx, ry, rs = L['rays']
    rb = sk.bone('rays_b', 'main', rx, ry)
    sk.slot('halo', rb, 'glow', w=rs * 0.95, blend='additive', color='c23cffd0')
    sk.slot('rays', rb, 'rays', w=rs, blend='additive', color='ff7ae6aa')
    sk.slot('rays2', rb, 'rays', w=rs * 0.8, blend='additive', color='7ae8ff66')
    sk.both(rb, 'scale', lambda t: (seg(t, 0.9, 1.5, 0.2, 1, out_back),) * 2,
            lambda t: (1 + 0.03 * (1 - math.cos(2 * math.pi * t / 1.0)) / 2,) * 2)
    for s, a in (('halo', 1), ('rays', 1), ('rays2', 1)):
        sk.both(s, 'alpha', lambda t: seg(t, 0.9, 1.4, 0, 1, lambda u: u), lambda t: 1)
    # rays turn one 16-fold step per loop -> seamless
    sk.anim('intro', 'rays_b', 'rotate', lambda t: 22.5 * (t - INTRO) / IDLE)
    sk.anim('idle', 'rays_b', 'rotate', lambda t: 22.5 * t / IDLE)

    # flying coins (burst out from the emblem, then float)
    ex, ey, eh = L['emblem']
    for i, (cx, cy, s) in enumerate(L['coins']):
        b = sk.bone(f'coin{i}', 'main', cx, cy)
        sk.slot(f'coin{i}', b, 'coin', w=172 * s)
        t0 = 1.3 + 0.05 * i
        sk.both(b, 'translate',
                lambda t, cx=cx, cy=cy, t0=t0: (seg(t, t0, t0 + 0.6, ex - cx, 0), seg(t, t0, t0 + 0.6, ey - cy, 0)),
                lambda t, i=i: (0, 10 * wave(t, IDLE / 2, i * 0.17)))
        sk.both(b, 'rotate', lambda t, i=i, t0=t0: seg(t, t0, t0 + 0.6, 220 * (1 if i % 2 else -1), 0),
                lambda t, i=i: 8 * wave(t, IDLE, i * 0.31))
        sk.both(b, 'scale', lambda t, t0=t0: (seg(t, t0, t0 + 0.6, 0.2, 1),) * 2,
                lambda t, i=i: (1 + 0.04 * wave(t, IDLE / 2, i * 0.17), 1))
        sk.both(f'coin{i}', 'alpha', lambda t, t0=t0: seg(t, t0, t0 + 0.1, 0, 1, lambda u: u), lambda t: 1)

    # emblem (the neon dragon "free spins" plaque)
    eb = sk.bone('emblem_b', 'main', ex, ey)
    sk.slot('emblem', eb, 'emblem', h=eh)
    sk.slot('emblem_flash', eb, 'emblem_flash', h=eh, blend='additive')
    sk.both(eb, 'translate', lambda t: (0, seg(t, 0.8, 1.35, -260, 0, out_back)),
            lambda t: (0, 6 * wave(t, IDLE / 2)))
    sk.both(eb, 'scale', lambda t: (seg(t, 0.8, 1.35, 0.4, 1, out_back),) * 2,
            lambda t: (1 + 0.012 * (1 - math.cos(2 * math.pi * t / 1.0)) / 2,) * 2)
    sk.both('emblem', 'alpha', lambda t: seg(t, 0.8, 0.95, 0, 1, lambda u: u), lambda t: 1)
    sk.both('emblem_flash', 'alpha', lambda t: 0 if t < 1.3 else seg(t, 1.3, 1.75, 0.85, 0),
            lambda t: 0.22 * max(0.0, math.sin(2 * math.pi * (t / IDLE - 0.1))) ** 12)

    # title FREE / SPINS slamming in from both sides
    ty = L['title_y']
    fb = sk.bone('free_b', 'main', L['free'][0], ty)
    sk.slot('t_free', fb, 't_free', w=L['free'][1])
    spb = sk.bone('spins_b', 'main', L['spins'][0], ty)
    sk.slot('t_spins', spb, 't_spins', w=L['spins'][1])
    for b, x, dx, t0, s in ((fb, L['free'][0], -500, 1.05, 't_free'), (spb, L['spins'][0], 500, 1.15, 't_spins')):
        sk.both(b, 'translate', lambda t, dx=dx, t0=t0: (seg(t, t0, t0 + 0.4, dx, 0, out_back), 0),
                lambda t: (0, 0))
        sk.both(b, 'scale', lambda t: (1, 1),
                lambda t, t0=t0: (1 + 0.03 * (1 - math.cos(2 * math.pi * (t / 1.0 - (t0 - 1.05)))) / 2,) * 2)
        sk.both(s, 'alpha', lambda t, t0=t0: seg(t, t0, t0 + 0.12, 0, 1, lambda u: u), lambda t: 1)
    sparks(sk, 'main', 'tspk', 1.5, 12, 380 if desk else 300, 'ffd36aff', seed=31)

    # counter plate (the DOM draws the real spin count over bone "count")
    cx, cy, cw = L['counter']
    cb = sk.bone('counter_b', 'main', cx, cy)
    sk.slot('counter', cb, 'counter', w=cw)
    sk.bone('count', cb, 0, 2)
    sk.both(cb, 'scale', lambda t: (seg(t, 1.45, 1.85, 0.2, 1, out_back),) * 2,
            lambda t: (1 + 0.02 * (1 - math.cos(2 * math.pi * t / 1.0)) / 2,) * 2)
    sk.both('counter', 'alpha', lambda t: seg(t, 1.45, 1.6, 0, 1, lambda u: u), lambda t: 1)
    sparks(sk, cb, 'cspk', 1.95, 10, cw * 0.75, '6ff3ffff', seed=41)

    logo(sk, *L['logo'], t0=0.5)
    petals(sk, 'main', 12 if desk else 9, L['petal_area'], seed=17, size=1.0 if desk else 0.9)
    tap_text(sk, 'TAP TO START', *L['tap'])
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        feature(v)
        bonus(v)
