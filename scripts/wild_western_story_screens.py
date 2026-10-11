"""Wild Western Story — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Same approach as scripts/neon_reels_screens.py: a full-screen skeleton authored
on the game's design canvas (origin = canvas centre, 1 unit = 1 design px,
y up), `intro` (2.8s) -> `idle` (4s loop, first idle frame == last intro
frame). Four variants: feature/bonus x desk (1932x940) / mob (780x1416). The
game's background is NOT in the skeleton — the DOM layer under the canvas
shows the game's own bg with object-fit: cover.

No designer pack exists for these screens, so everything is built from the
game's delivered art (logo, symbol statics, the reel frame's logs, buy-bonus
signpost, props) plus procedural FX (rays, glow, sparks, dust, muzzle flash,
bullet holes). Card/plaque panels are 9-sliced out of the reel frame
(img/Frame.png) so they read as the same carpentry as the game's frame.

Every animated property is a python function of time, sampled at 30 fps and
thinned (a key is dropped when linear interpolation reproduces it).

Usage:
  python scripts/wild_western_story_screens.py <fonts_dir> [out_dir]

fonts_dir — rye.ttf, luckiest.ttf (convert from front/fonts/*.woff2 with
            fontTools: TTFont(woff2).flavor=None; .save(ttf))
out_dir   — default front/img/wild-western-story/screens
"""

import json
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FPS = 30
INTRO = 2.8
IDLE = 4.0

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(REPO, 'front', 'img', 'wild-western-story')
FONTS = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ASSETS, 'screens')


# --------------------------------------------------------------------------
# easing / timing helpers

def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def lerp(a, b, t):
    return a + (b - a) * t


def out_cubic(t):
    return 1 - (1 - t) ** 3


def in_cubic(t):
    return t ** 3


def out_back(t, s=1.9):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def in_out_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2


def linear(t):
    return t


def seg(t, t0, t1, v0, v1, ease=out_cubic):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    return lerp(v0, v1, ease((t - t0) / (t1 - t0)))


def wave(t, period, phase=0.0):
    """sin over the loop, 0 at t=0 when phase=0."""
    return math.sin(2 * math.pi * (t / period + phase))


def bump(t, t0, dur):
    """0 -> 1 -> 0 half-sine pulse over [t0, t0+dur]."""
    if t <= t0 or t >= t0 + dur:
        return 0.0
    return math.sin(math.pi * (t - t0) / dur)


# --------------------------------------------------------------------------
# image building

def load(rel):
    im = Image.open(os.path.join(ASSETS, rel)).convert('RGBA')
    return im.crop(im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox())


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)


def trim(im, pad=0):
    im = im.crop(im.getchannel('A').getbbox())
    if pad:
        c = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad))
        c.paste(im, (pad, pad))
        im = c
    return im


def hexc(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


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


GOLD = [(0, hexc('fff6c8')), (0.42, hexc('ffd04a')), (0.7, hexc('e8931a')), (1, hexc('9c4a0c'))]
CREAM = [(0, hexc('fffaf0')), (1, hexc('f3d9a6'))]
EMBER = [(0, hexc('fff3d0')), (0.5, hexc('ffb347')), (1, hexc('e2571b'))]


def text_line(text, fnt, size, fill, stroke, stroke_w, glow, glow_r, shadow):
    f = font(fnt, size)
    pad = stroke_w + glow_r * 3 + 16
    bb = f.getbbox(text, stroke_width=stroke_w)
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    org = (pad - bb[0], pad - bb[1])
    mask, smask = Image.new('L', (w, h)), Image.new('L', (w, h))
    ImageDraw.Draw(mask).text(org, text, font=f, fill=255)
    ImageDraw.Draw(smask).text(org, text, font=f, fill=255, stroke_width=stroke_w, stroke_fill=255)
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(glow_r)).point(lambda a: min(255, int(a * 1.5)))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    if shadow:
        sh = smask.transform(smask.size, Image.AFFINE, (1, 0, 0, 0, 1, -shadow))
        out.paste(Image.new('RGBA', (w, h), (20, 8, 2, 230)), (0, 0), sh)
    out.paste(Image.new('RGBA', (w, h), hexc(stroke)), (0, 0), smask)
    mb = mask.getbbox()
    fill_im = Image.new('RGBA', (w, h))
    fill_im.paste(vgrad((w, mb[3] - mb[1]), fill), (0, mb[1]))
    out.paste(fill_im, (0, 0), mask)
    # thin top highlight on the letters, carved-gold look
    hl = ImageChops.subtract(mask, mask.transform(mask.size, Image.AFFINE, (1, 0, 0, 0, 1, -max(1, size // 28))))
    out.paste(Image.new('RGBA', (w, h), (255, 255, 240, 170)), (0, 0), hl)
    return trim(out)


def text_img(text, fnt, size, fill=GOLD, stroke='3a1806', stroke_w=None, glow=None, glow_r=None,
             shadow=None, line_gap=0.12):
    """Multi-line ('\\n') centred text block."""
    stroke_w = stroke_w if stroke_w is not None else max(2, size // 9)
    glow_r = glow_r if glow_r is not None else max(4, size // 6)
    shadow = shadow if shadow is not None else max(2, size // 14)
    lines = [text_line(t, fnt, size, fill, stroke, stroke_w, glow, glow_r, shadow) for t in text.split('\n')]
    if len(lines) == 1:
        return lines[0]
    gap = int(size * line_gap)
    w = max(l.width for l in lines)
    h = sum(l.height for l in lines) + gap * (len(lines) - 1)
    out = Image.new('RGBA', (w, h))
    y = 0
    for l in lines:
        out.alpha_composite(l, ((w - l.width) // 2, y))
        y += l.height + gap
    return out


def soft_glow(size=256):
    r = Image.radial_gradient('L').resize((size, size))  # 0 centre -> 255 edge
    a = r.point(lambda v: int(255 * clamp(1 - v / 181) ** 2.2))
    im = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    im.putalpha(a)
    return im


def spark(w=160, h=28):
    m = Image.new('L', (w, h))
    ImageDraw.Draw(m).ellipse([0, h * 0.3, w - 1, h * 0.7], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(h / 7))
    im = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    im.putalpha(m)
    return im


def flare_star(size=160):
    m = Image.new('L', (size, size))
    d = ImageDraw.Draw(m)
    c = size / 2
    for ang in (0, 90):
        a = math.radians(ang)
        dx, dy = math.cos(a) * c, math.sin(a) * c
        d.polygon([(c - dx, c - dy), (c + dy * 0.06, c - dx * 0.06), (c + dx, c + dy), (c - dy * 0.06, c + dx * 0.06)],
                  fill=255)
    m = m.filter(ImageFilter.GaussianBlur(size / 90))
    core = soft_glow(size).getchannel('A').point(lambda v: int(v * 0.9))
    m = ImageChops.lighter(m, core)
    im = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    im.putalpha(m)
    return im


def rays(size, n=16):
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    c = big / 2
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + 2 * math.pi / n * 0.45
        d.polygon([(c, c), (c + big * math.cos(a0), c + big * math.sin(a0)),
                   (c + big * math.cos(a1), c + big * math.sin(a1))], fill=255)
    m = m.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(size / 120))
    fall = Image.radial_gradient('L').resize((size, size)).point(lambda v: int(255 * clamp(1 - v / 181) ** 1.5))
    im = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    im.putalpha(ImageChops.multiply(m, fall))
    return im


def muzzle_flash(size=220):
    rnd = random.Random(5)
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    c = big / 2
    pts = []
    n = 14
    for i in range(n * 2):
        a = 2 * math.pi * i / (n * 2)
        r = c * (rnd.uniform(0.75, 1.0) if i % 2 == 0 else rnd.uniform(0.18, 0.3))
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=255)
    m = m.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(size / 70))
    core = soft_glow(size).getchannel('A')
    alpha = ImageChops.lighter(m, core)
    # white-hot core -> yellow -> orange tips
    col = Image.radial_gradient('L').resize((size, size))
    rgb = Image.merge('RGB', (col.point(lambda v: 255),
                              col.point(lambda v: int(255 - clamp(v / 160) * 120)),
                              col.point(lambda v: int(235 - clamp(v / 90) * 225))))
    im = rgb.convert('RGBA')
    im.putalpha(alpha)
    return im


def bullet_hole(size=64):
    rnd = random.Random(9)
    s = size * 4
    im = Image.new('RGBA', (s, s))
    d = ImageDraw.Draw(im)
    c = s / 2
    # splinter cracks
    for _ in range(9):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.3, 0.48) * s
        d.line([(c, c), (c + r * math.cos(a), c + r * math.sin(a))], fill=(30, 14, 5, 200), width=6)
    # torn rim: light raw wood, then the dark hole
    rim = [(c + (s * rnd.uniform(0.2, 0.25)) * math.cos(a), c + (s * rnd.uniform(0.2, 0.25)) * math.sin(a))
           for a in [2 * math.pi * k / 18 for k in range(18)]]
    d.polygon(rim, fill=(196, 140, 78, 255))
    hole = [(c + (s * rnd.uniform(0.13, 0.16)) * math.cos(a), c + (s * rnd.uniform(0.13, 0.16)) * math.sin(a))
            for a in [2 * math.pi * k / 14 for k in range(14)]]
    d.polygon(hole, fill=(12, 6, 2, 255))
    im = im.filter(ImageFilter.GaussianBlur(2))
    return im.resize((size, size), Image.LANCZOS)


def silhouette(im, k=1.0, col=(255, 255, 255)):
    """Flat-colour copy of an image's alpha (for additive flashes)."""
    out = Image.new('RGBA', im.size, col + (0,))
    out.putalpha(im.getchannel('A').point(lambda v: int(v * k)))
    return out


def log_panel(w, h, scale=0.45, fill_top='3b2212', fill_bot='1c0e06', alpha=238):
    """Card/plaque in the reel frame's carpentry: Frame.png 9-sliced to w x h
    (px), over a dark stained-wood fill with grain and a vignette."""
    src = Image.open(os.path.join(ASSETS, 'img', 'Frame.png')).convert('RGBA')
    src = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
    sw, sh = src.size
    L, R, T, B = int(200 * scale), int(185 * scale), int(150 * scale), int(214 * scale)
    out = Image.new('RGBA', (w, h))
    # inner fill sits under the logs (inset to the logs' centre lines)
    il, ir, it, ib = int(100 * scale), int(158 * scale), int(70 * scale), int(150 * scale)
    fill = vgrad((w, h), [(0, hexc(fill_top, alpha)), (1, hexc(fill_bot, alpha))])
    rnd = random.Random(w * 7 + h)
    grain = Image.new('L', (w, h))
    gd = ImageDraw.Draw(grain)
    for _ in range(int(h * 0.5)):
        y = rnd.uniform(0, h)
        gd.line([(0, y), (w, y + rnd.uniform(-6, 6))], fill=rnd.randint(8, 26), width=1)
    grain = grain.filter(ImageFilter.GaussianBlur(0.8))
    fill.paste(Image.new('RGBA', (w, h), (120, 70, 30, 255)), (0, 0), grain)
    vign = Image.radial_gradient('L').resize((w, h)).point(lambda v: int(170 * clamp((v - 90) / 110)))
    fill.paste(Image.new('RGBA', (w, h), (6, 2, 0, 255)), (0, 0), vign)
    m = Image.new('L', (w, h))
    ImageDraw.Draw(m).rectangle([il, it, w - ir, h - ib], fill=alpha)
    out.paste(fill, (0, 0), m)

    def piece(box, size):
        p = src.crop(box)
        return p.resize(size, Image.LANCZOS) if p.size != size else p

    cw, ch = w - L - R, h - T - B
    layer = Image.new('RGBA', (w, h))
    layer.alpha_composite(piece((0, 0, L, T), (L, T)), (0, 0))
    layer.alpha_composite(piece((sw - R, 0, sw, T), (R, T)), (w - R, 0))
    layer.alpha_composite(piece((0, sh - B, L, sh), (L, B)), (0, h - B))
    layer.alpha_composite(piece((sw - R, sh - B, sw, sh), (R, B)), (w - R, h - B))
    # edges come from the left 40% of the logs: the source frame has a baked
    # glow smudge in the middle of its bottom log
    ex = int(sw * 0.42)
    layer.alpha_composite(piece((L, 0, ex, T), (cw, T)), (L, 0))
    layer.alpha_composite(piece((L, sh - B, ex, sh), (cw, B)), (L, h - B))
    layer.alpha_composite(piece((0, T, L, sh - B), (L, ch)), (0, T))
    layer.alpha_composite(piece((sw - R, T, sw, sh - B), (R, ch)), (w - R, T))
    out.alpha_composite(layer)
    return out


# --------------------------------------------------------------------------
# skeleton builder

class Skel:
    def __init__(self, name, w, h, res):
        self.name, self.w, self.h, self.res = name, w, h, res
        self.bones = [{'name': 'root'}]
        self.slots = []
        self.atts = {}
        self.images = {}
        self.need = {}
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

    def _att(self, region, w, h, x, y, rot):
        im = self.images[region]
        if w is None and h is None:
            w, h = im.width / self.res, im.height / self.res
        elif h is None:
            h = w * im.height / im.width
        elif w is None:
            w = h * im.width / im.height
        att = {'x': round(x, 2), 'y': round(y, 2), 'width': round(w, 2), 'height': round(h, 2)}
        if rot:
            att['rotation'] = rot
        pw, ph = self.need.get(region, (0, 0))
        self.need[region] = (max(pw, w), max(ph, h))
        return att

    def slot(self, name, bone, region, w=None, h=None, x=0, y=0, rot=0, blend=None, color=None, show=True):
        """Region attachment sized w (or h) in units, aspect from the image."""
        s = {'name': name, 'bone': bone}
        if show:
            s['attachment'] = region
        if blend:
            s['blend'] = blend
        if color:
            s['color'] = color
        self.slots.append(s)
        self.atts[name] = {region: self._att(region, w, h, x, y, rot)}
        return name

    def extra(self, slot, region, w=None, h=None, x=0, y=0):
        """Another attachment in an existing slot (for attachment swaps)."""
        self.atts[slot][region] = self._att(region, w, h, x, y, 0)

    def swaps(self, which, slot, keys):
        self.anims[which]['slots'].setdefault(slot, {})['attachment'] = [
            ({'time': round(t, 4)} if t else {}) | {'name': n} for t, n in keys]

    # -- timelines (sampled) --
    def _sample(self, fn, dur):
        n = int(round(dur * FPS))
        return [(k / FPS, fn(k / FPS)) for k in range(n + 1)]

    @staticmethod
    def _thin(samples, tol):
        def vals(v):
            return v if isinstance(v, tuple) else (v,)

        out = [samples[0]]
        i, n = 0, len(samples)
        while i < n - 1:
            j = i + 1
            while j + 1 < n:
                t0, v0 = samples[i]
                t1, v1 = samples[j + 1]
                ok = True
                for k in range(i + 1, j + 1):
                    tk, vk = samples[k]
                    f = (tk - t0) / (t1 - t0)
                    if any(abs(lerp(a, b, f) - c) > tol for a, b, c in zip(vals(v0), vals(v1), vals(vk))):
                        ok = False
                        break
                if not ok:
                    break
                j += 1
            out.append(samples[j])
            i = j
        if all(vals(v) == vals(out[0][1]) for _, v in out):
            out = out[:1]
        return out

    def anim(self, which, target, prop, fn):
        dur = INTRO if which == 'intro' else IDLE
        tol = {'translate': 0.25, 'scale': 0.0015, 'rotate': 0.08, 'alpha': 0.004}[prop]
        keys = self._thin(self._sample(fn, dur), tol)
        rows = []
        for t, v in keys:
            r = {'time': round(t, 4)} if t else {}
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
        regions = {}
        for r, im in self.images.items():
            if r not in self.need:
                continue
            w, _ = self.need[r]
            tw = max(2, min(im.width, int(math.ceil(w * self.res))))
            th = max(2, int(round(tw * im.height / im.width)))
            regions[r] = im.resize((tw, th), Image.LANCZOS) if (tw, th) != im.size else im
        pages = pack(regions)
        atlas_lines = []
        for pi, (page, placed) in enumerate(pages):
            fname = 'animation.png' if pi == 0 else f'animation{pi + 1}.png'
            # NOT palette-quantized like the rest of front/img: the soft
            # additive FX (rays, halos, glints) live in low-alpha pixels a
            # 256-colour palette zeroes out — the rays came out banded and dim.
            premultiply(page).save(os.path.join(out, fname), optimize=True)
            if atlas_lines:
                atlas_lines.append('')
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
    return Image.merge('RGBA', (ImageChops.multiply(r, a), ImageChops.multiply(g, a), ImageChops.multiply(b, a), a))


def pack(regions, max_w=2048, max_h=2048, gap=2):
    """Shelf packer, tallest first; spills onto extra pages."""
    items = sorted(regions.items(), key=lambda kv: (-kv[1].height, -kv[1].width))
    pages = []
    while items:
        placed, left = {}, []
        x = y = shelf_h = used_w = used_h = 0
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
    'logo': load('img/logo.png'),
    'wild_big': load('Export/wild/static-big.png'),
    'wild_small': load('Export/wild/static-small.png'),
    'scatter': load('Export/scatter/static.png'),
    'wolf': load('Export/wolf/statik.png'),
    'gun': load('Export/gun/statik.png'),
    'whiskey': load('Export/whickey/static.png'),
    'buy_sign': load('img/Buy-bonus-button.png'),
    'cactus1': load('img/cactus_1.png'),
    'cactus2': load('img/cactus_2.png'),
    'glow': soft_glow(),
    'spark': spark(),
    'star': flare_star(),
    'rays': rays(1000),
    'flash': muzzle_flash(),
    'hole': bullet_hole(),
}
for k in ('logo', 'wild_big', 'wild_small', 'scatter', 'buy_sign'):
    ART[k + '_flash'] = silhouette(ART[k], 0.9, (255, 236, 190))


def add_art(sk, keys):
    for k in keys:
        sk.image(k, ART[k])


def logo_shine_frames(sk, w, n=10):
    """Diagonal glint swept across the logo, pre-masked by the logo's alpha:
    n regions (each cropped to its own band) swapped through one slot."""
    im = ART['logo']
    tw = int(math.ceil(w * sk.res))
    th = int(round(tw * im.height / im.width))
    a = im.resize((tw, th), Image.LANCZOS).getchannel('A')
    band_w = tw * 0.11
    slope = 0.35
    names = []
    for k in range(n):
        cx = lerp(-0.15, 1.15, k / (n - 1)) * tw
        band = Image.new('L', (tw, th))
        bd = ImageDraw.Draw(band)
        poly = [(cx - band_w / 2 - slope * th / 2, th), (cx + band_w / 2 - slope * th / 2, th),
                (cx + band_w / 2 + slope * th / 2, 0), (cx - band_w / 2 + slope * th / 2, 0)]
        bd.polygon(poly, fill=255)
        band = band.filter(ImageFilter.GaussianBlur(band_w / 4))
        m = ImageChops.multiply(band, a).point(lambda v: int(v * 0.85))
        bb = m.getbbox()
        if not bb:
            continue
        crop = Image.new('RGBA', (bb[2] - bb[0], bb[3] - bb[1]), (255, 248, 220, 0))
        crop.putalpha(m.crop(bb))
        name = f'logo_shine{k}'
        sk.image(name, crop)
        ux = ((bb[0] + bb[2]) / 2 - tw / 2) / sk.res
        uy = -((bb[1] + bb[3]) / 2 - th / 2) / sk.res
        names.append((name, crop.width / sk.res, crop.height / sk.res, ux, uy))
    return names


def logo(sk, x, y, w, t0=0.1, shine_at=(0.95, 0.6)):
    """Logo drop with dust-puff landing + an idle glint sweep."""
    b = sk.bone('logo_b', 'main', x, y)
    im = ART['logo']
    h = w * im.height / im.width
    sk.slot('logo_glow', b, 'glow', w=w * 1.5, h=h * 1.5, blend='additive', color='ffb44ab0')
    sk.slot('logo', b, 'logo', w=w)
    sk.slot('logo_flash', b, 'logo_flash', w=w, blend='additive')
    frames = logo_shine_frames(sk, w)
    first = frames[0]
    sk.slot('logo_shine', b, first[0], w=first[1], h=first[2], x=first[3], y=first[4], blend='additive', show=False)
    for name, fw, fh, fx, fy in frames[1:]:
        sk.extra('logo_shine', name, w=fw, h=fh, x=fx, y=fy)
    step = 0.045
    intro_shine, idle_shine = shine_at
    sk.swaps('intro', 'logo_shine', [(0, None)] + [(intro_shine + i * step, f[0]) for i, f in enumerate(frames)]
             + [(intro_shine + len(frames) * step, None)])
    sk.swaps('idle', 'logo_shine', [(0, None)] + [(idle_shine + i * step, f[0]) for i, f in enumerate(frames)]
             + [(idle_shine + len(frames) * step, None)])

    land = t0 + 0.55
    sk.both(b, 'translate', lambda t: (0, seg(t, t0, land, 420, 0, out_back)), lambda t: (0, 0))
    sk.both(b, 'scale',
            lambda t: (seg(t, t0, land, 0.7, 1, out_back) * (1 + 0.05 * bump(t, land - 0.05, 0.2)),
                       seg(t, t0, land, 0.7, 1, out_back) * (1 - 0.06 * bump(t, land - 0.05, 0.2))),
            lambda t: (1 + 0.02 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.both('logo', 'alpha', lambda t: seg(t, t0, t0 + 0.15, 0, 1, linear), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: 0 if t < land else seg(t, land, land + 0.4, 0.8, 0),
            lambda t: 0)
    sk.both('logo_glow', 'alpha', lambda t: seg(t, land, land + 0.5, 0, 1),
            lambda t: 0.75 + 0.25 * math.cos(2 * math.pi * t / 2))
    dust_puff(sk, b, 'lpuff', land, w * 0.55, -h * 0.32, seed=4)
    return b


def dust_puff(sk, parent, prefix, t0, spread, y, seed, n=10):
    """Sideways dust burst on a landing — warm soft blobs."""
    rnd = random.Random(seed)
    for i in range(n):
        side = -1 if i % 2 else 1
        b = sk.bone(f'{prefix}{i}', parent, side * spread * rnd.uniform(0.2, 0.5), y)
        sz = rnd.uniform(60, 120)
        sk.slot(f'{prefix}{i}', b, 'glow', w=sz, color='d9a066ff')
        dx = side * spread * rnd.uniform(0.5, 1.0)
        dy = rnd.uniform(-10, 40)
        dur = rnd.uniform(0.6, 0.9)
        sk.both(b, 'translate', lambda t, dx=dx, dy=dy, dur=dur: (seg(t, t0, t0 + dur, 0, dx), seg(t, t0, t0 + dur, 0, dy)),
                lambda t, dx=dx, dy=dy: (dx, dy))
        sk.both(b, 'scale', lambda t, dur=dur: (seg(t, t0, t0 + dur, 0.4, 1.6),) * 2, lambda t: (1.6, 1.6))
        sk.both(f'{prefix}{i}', 'alpha',
                lambda t, dur=dur: 0 if t < t0 else 0.55 * seg(t, t0, t0 + dur, 1, 0, linear), lambda t: 0)


def dust_motes(sk, parent, count, area, seed, intro_from=0.8):
    """Warm dust drifting up through the light, seamless over the idle loop."""
    rnd = random.Random(seed)
    x0, x1, ybot, ytop = area
    for i in range(count):
        b = sk.bone(f'mote{i}', parent)
        sz = rnd.uniform(8, 20)
        sk.slot(f'mote{i}', b, 'glow', w=sz, blend='additive', color='ffd59aff')
        px = rnd.uniform(x0, x1)
        sway = rnd.uniform(14, 40)
        ph = i / count + rnd.uniform(-0.03, 0.03)
        laps = rnd.choice([1, 1, 2])
        peak = rnd.uniform(0.45, 0.9)

        def pos(tau, px=px, sway=sway, ph=ph, laps=laps):
            u = ((tau / IDLE) * laps + ph) % 1.0
            return (px + sway * math.sin(2 * math.pi * (u + ph)), lerp(ybot, ytop, u))

        def alpha(tau, ph=ph, laps=laps, peak=peak):
            u = ((tau / IDLE) * laps + ph) % 1.0
            return peak * clamp(u / 0.15) * clamp((1 - u) / 0.2)

        env = lambda t: clamp((t - intro_from) / 0.8)
        sk.both(b, 'translate', lambda t, pos=pos: pos(t - INTRO), lambda t, pos=pos: pos(t))
        sk.both(f'mote{i}', 'alpha', lambda t, a=alpha: a(t - INTRO) * env(t), lambda t, a=alpha: a(t))


def twinkles(sk, parent, spots, seed, start=2.0):
    rnd = random.Random(seed)
    for i, (x, y, s) in enumerate(spots):
        b = sk.bone(f'tw{i}', parent, x, y)
        sk.slot(f'tw{i}', b, 'star', w=130 * s, blend='additive', color='fff0c0ff')
        ph = rnd.random()

        def tw(t, ph=ph):
            return math.sin(math.pi * (((t / IDLE) * 2 + ph) % 1.0)) ** 8

        sk.both(b, 'scale', lambda t, tw=tw: ((0.2 + 0.8 * tw(t - INTRO + IDLE)),) * 2,
                lambda t, tw=tw: (0.2 + 0.8 * tw(t),) * 2)
        sk.both(b, 'rotate', lambda t: 45 * (t - INTRO) / IDLE, lambda t: 45 * t / IDLE)
        sk.both(f'tw{i}', 'alpha', lambda t, tw=tw: clamp((t - start) / 0.4) * tw(t - INTRO + IDLE),
                lambda t, tw=tw: tw(t))


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


def sun_rays(sk, parent, x, y, size, t0, alpha=0.5, color='ffc86aff'):
    """Two counter-rotating ray fans + a halo. 16-fold fans turn one step per
    idle loop (22.5deg), so idle is seamless; intro ends where idle starts."""
    rb = sk.bone('rays_b', parent, x, y)
    sk.slot('halo', rb, 'glow', w=size * 0.85, blend='additive', color='ff9a3cc0')
    r1 = sk.bone('rays1_b', rb)
    sk.slot('rays1', r1, 'rays', w=size, blend='additive', color=color)
    r2 = sk.bone('rays2_b', rb)
    sk.slot('rays2', r2, 'rays', w=size * 0.75, blend='additive', color='fff2c8ff')
    sk.both(rb, 'scale', lambda t: (seg(t, t0, t0 + 0.7, 0.3, 1, out_back),) * 2,
            lambda t: (1 + 0.03 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.anim('intro', r1, 'rotate', lambda t: 22.5 * (t - INTRO) / IDLE)
    sk.anim('idle', r1, 'rotate', lambda t: 22.5 * t / IDLE)
    sk.anim('intro', r2, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE)
    sk.anim('idle', r2, 'rotate', lambda t: -22.5 * t / IDLE)
    for s, a in (('halo', 0.9), ('rays1', alpha), ('rays2', alpha * 0.55)):
        sk.both(s, 'alpha', lambda t, a=a: a * seg(t, t0, t0 + 0.5, 0, 1, linear),
                lambda t, a=a: a * (0.85 + 0.15 * math.cos(2 * math.pi * t / 2)))


def tap_text(sk, text, x, y, h, t0):
    im = text_img(text, 'luckiest', 72, fill=CREAM, stroke='2a1204', glow='ff9a3c', glow_r=10)
    sk.image('t_tap', im)
    b = sk.bone('tap_b', 'main', x, y)
    sk.slot('tap', b, 't_tap', h=h)
    sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.45, 0.6, 1, out_back),) * 2,
            lambda t: (1 + 0.035 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.both('tap', 'alpha', lambda t: seg(t, t0, t0 + 0.3, 0, 1, linear),
            lambda t: 0.6 + 0.4 * math.cos(2 * math.pi * t / 2))


def cacti(sk, W, H, t0, scale=1.0):
    """Corner cacti framing the bottom of the screen, sprouting in."""
    for name, region, x, w, flip in (('cactusL', 'cactus2', -W / 2 + 95 * scale, 230 * scale, False),
                                      ('cactusR', 'cactus1', W / 2 - 100 * scale, 230 * scale, False)):
        im = ART[region]
        h = w * im.height / im.width
        b = sk.bone(name + '_b', 'main', x, -H / 2)
        sk.slot(name, b, region, w=w, y=h / 2 - 6)
        sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.5, 0.8, 1, out_back), seg(t, t0, t0 + 0.5, 0.0, 1, out_back)),
                lambda t, x=x: (1, 1 + 0.012 * wave(t, IDLE / 2, 0.3 if x > 0 else 0)))
        sk.both(b, 'rotate', lambda t: 0, lambda t, x=x: 1.2 * wave(t, IDLE, 0.5 if x > 0 else 0))
        sk.both(name, 'alpha', lambda t: seg(t, t0, t0 + 0.2, 0, 1, linear), lambda t: 1)


def text_slot(sk, region, im, bone, w=None, h=None, x=0, y=0, maxw=None):
    sk.image(region, im)
    if maxw is not None:
        hh = h if h is not None else w * im.height / im.width
        if hh * im.width / im.height > maxw:
            w, h = maxw, None
    return sk.slot(region, bone, region, w=w, h=h, x=x, y=y)


# --------------------------------------------------------------------------
# FEATURE screen

CARDS = [
    ('wild', 'EXPANDING WILD', 'WILD EXPANDS TO COVER\nTHE WHOLE REEL'),
    ('scatter', 'FREE SPINS', '3+ SCATTERS AWARD\nUP TO 20 FREE SPINS'),
    ('buy', 'BUY BONUS', 'INSTANT FREE SPINS\nFOR 100X BET'),
]


def card_art(sk, kind, i, parent, cx, cy, size, desk):
    """Per-card animated art. Returns the slots visible during the intro: the
    card's fade-in drives only their INTRO alpha (their idle timelines are
    the art's own)."""
    slots = []
    ab = sk.bone(f'art{i}', parent, cx, cy)
    if kind == 'wild':
        # small wild in a cell -> grows into the reel-high wild -> back
        sw, bh = size
        sk.slot(f'wglow{i}', ab, 'glow', w=bh * 1.1, blend='additive', color='ffb347ff')
        bb = sk.bone(f'wbig{i}', ab)
        sk.slot(f'wbig{i}', bb, 'wild_big', h=bh)
        sk.slot(f'wbigf{i}', bb, 'wild_big_flash', h=bh, blend='additive')
        smb = sk.bone(f'wsmall{i}', ab)
        sk.slot(f'wsmall{i}', smb, 'wild_small', w=sw)
        sk.slot(f'wsmallf{i}', smb, 'wild_small_flash', w=sw, blend='additive')
        g0, g1, s0, s1 = 1.0, 1.4, 3.15, 3.5  # grow / shrink windows in the idle loop
        hold = lambda t: t < g0 or t >= s1
        sk.both(f'wsmall{i}', 'alpha', lambda t: 1,
                lambda t: 1 if t < g0 else (seg(t, g0, g0 + 0.15, 1, 0, linear) if t < s0 else seg(t, s0 + 0.1, s1, 0, 1, linear)))
        sk.both(smb, 'scale', lambda t: (1, 1),
                lambda t: ((1 + 0.12 * bump(t, 0.45, 0.55)) if t < g0 else seg(t, s0 + 0.1, s1, 0.7, 1, out_back),) * 2)
        sk.both(f'wsmallf{i}', 'alpha', lambda t: 0, lambda t: 0.75 * bump(t, 0.75, 0.3))
        sk.both(bb, 'scale', lambda t: (1, 0.35),
                lambda t: (1, seg(t, g0, g1, 0.35, 1, out_back) if t < s0 else seg(t, s0, s0 + 0.3, 1, 0.35, in_cubic)))
        sk.both(f'wbig{i}', 'alpha', lambda t: 0,
                lambda t: seg(t, g0, g0 + 0.12, 0, 1, linear) if t < s0 else seg(t, s0 + 0.15, s0 + 0.3, 1, 0, linear))
        sk.both(f'wbigf{i}', 'alpha', lambda t: 0, lambda t: 0 if t < g0 + 0.2 else 0.7 * seg(t, g0 + 0.2, g0 + 0.7, 1, 0))
        sk.both(f'wglow{i}', 'alpha', lambda t: 0,
                lambda t: 0 if hold(t) else 0.55 * (seg(t, g0, g1, 0, 1) if t < s0 else seg(t, s0, s1, 1, 0)))
        slots.append(f'wsmall{i}')  # wbig is hidden through the whole intro anyway
    elif kind == 'scatter':
        sw = size[0]
        if desk:
            spots = [(-sw * 1.08, 0, 1.0, 0), (0, 0, 1.0, 0), (sw * 1.08, 0, 1.0, 0)]
        else:
            spots = [(-sw * 0.62, -4, 0.82, 12), (sw * 0.62, -4, 0.82, -12), (0, 6, 1.0, 0)]
        for j, (sx, sy, sc, rot) in enumerate(spots):
            b = sk.bone(f'sc{i}_{j}', ab, sx, sy, rot=rot)
            sk.slot(f'scg{i}_{j}', b, 'glow', w=sw * sc * 1.5, blend='additive', color='5fb8ffff')
            sk.slot(f'sc{i}_{j}', b, 'scatter', w=sw * sc)
            sk.slot(f'scf{i}_{j}', b, 'scatter_flash', w=sw * sc, blend='additive')
            at = 0.5 + 0.38 * j
            sk.both(b, 'scale', lambda t: (1, 1), lambda t, at=at: (1 + 0.16 * bump(t, at, 0.4),) * 2)
            sk.both(b, 'rotate', lambda t: 0, lambda t, at=at: 7 * bump(t, at, 0.4) * math.sin(6 * math.pi * clamp((t - at) / 0.4)))
            sk.both(f'scf{i}_{j}', 'alpha', lambda t: 0, lambda t, at=at: 0.65 * bump(t, at, 0.3))
            sk.both(f'scg{i}_{j}', 'alpha', lambda t: 0, lambda t, at=at: 0.25 + 0.55 * bump(t, at, 0.5))
            slots.append(f'sc{i}_{j}')
    else:
        sh = size[1]
        im = ART['buy_sign']
        # pivot at the foot of the post: the sign wobbles like it was just planted
        b = sk.bone(f'sign{i}', ab, 0, -sh / 2)
        sk.slot(f'sgg{i}', b, 'glow', w=sh * 1.3, y=sh * 0.62, blend='additive', color='ffb347ff')
        sk.slot(f'sign{i}', b, 'buy_sign', h=sh, y=sh / 2)
        sk.slot(f'signf{i}', b, 'buy_sign_flash', h=sh, y=sh / 2, blend='additive')
        sk.both(b, 'rotate', lambda t: 0, lambda t: 2.5 * wave(t, IDLE / 2) + 6 * bump(t, 2.2, 0.5) * math.sin(4 * math.pi * clamp((t - 2.2) / 0.5)))
        sk.both(f'signf{i}', 'alpha', lambda t: 0, lambda t: 0.5 * bump(t, 2.2, 0.35))
        sk.both(f'sgg{i}', 'alpha', lambda t: 0, lambda t: 0.3 + 0.2 * math.cos(2 * math.pi * t / 2))
        slots.append(f'sign{i}')
    return ab, slots


def feature(variant):
    desk = variant == 'desk'
    W, H = (1932, 940) if desk else (780, 1416)
    sk = Skel(f'feature_{variant}', W, H, 1.25 if desk else 1.15)
    add_art(sk, ['logo', 'logo_flash', 'glow', 'spark', 'star', 'rays', 'wild_big', 'wild_big_flash',
                 'wild_small', 'wild_small_flash', 'scatter', 'scatter_flash', 'buy_sign', 'buy_sign_flash',
                 'cactus1', 'cactus2'])
    sk.bone('main')
    if desk:
        L = dict(logo=(0, 330, 400), rays=(0, 330, 1000), card_y=-70, card_dx=545, panel=(470, 520),
                 title=(0, 182, 44, 330), art=(0, 32), desc=(0, -126, 27, 330),
                 sizes={'wild': (128, 240), 'scatter': (118, 0), 'buy': (0, 236)},
                 tap=(0, -397, 48), motes=(-960, 960, -470, 470),
                 tw=[(-200, 450, 0.5), (215, 205, 0.4), (-640, 260, 0.45), (690, 280, 0.4), (-60, -340, 0.35)])
    else:
        L = dict(logo=(0, 548, 460), rays=(0, 548, 900), card_y=None, cards_y=(205, -85, -375), panel=(700, 270),
                 title=(92, 50, 42, 370), art=(-195, 22), desc=(92, -24, 25, 370),
                 sizes={'wild': (110, 215), 'scatter': (100, 0), 'buy': (0, 185)},
                 tap=(0, -600, 48), motes=(-390, 390, -708, 708),
                 tw=[(-250, 650, 0.45), (240, 430, 0.4), (-330, 380, 0.35), (330, 700, 0.35), (0, -680, 0.3)])

    sun_rays(sk, 'main', *L['rays'], t0=0.0, alpha=0.42)
    cacti(sk, W, H, 0.15, 1.0 if desk else 0.75)

    pw, ph = L['panel']
    sk.image('panel', log_panel(int(pw * sk.res), int(ph * sk.res)))
    for i, (kind, title, desc) in enumerate(CARDS):
        tc = 0.65 + 0.2 * i
        if desk:
            cx, cy = (i - 1) * L['card_dx'], L['card_y']
        else:
            cx, cy = 0, L['cards_y'][i]
        cb = sk.bone(f'card{i}', 'main', cx, cy)
        sk.slot(f'panel{i}', cb, 'panel', w=pw, h=ph)
        ax, ay = L['art']
        _, art_slots = card_art(sk, kind, i, cb, ax, ay, L['sizes'][kind], desk)
        tx, ty, th, tmax = L['title']
        tb = sk.bone(f'title{i}', cb, tx, ty)
        text_slot(sk, f't_title{i}', text_img(title, 'rye', 88, fill=GOLD, stroke='2a1204', glow='ff8a2a', glow_r=9),
                  tb, h=th, maxw=tmax)
        dx, dy, dh, dmax = L['desc']
        db = sk.bone(f'desc{i}', cb, dx, dy)
        dim = text_img(desc, 'luckiest', 56, fill=CREAM, stroke='2a1204', glow=None)
        text_slot(sk, f't_desc{i}', dim, db, h=dh * 2.3, maxw=dmax)

        # intro: the card swings down on its nail, title stamps, art pops
        side = (-1, 1, -1)[i] if desk else (1, -1, 1)[i]
        sk.both(cb, 'translate', lambda t, tc=tc: (0, seg(t, tc, tc + 0.5, 520 if desk else 260, 0, out_back)),
                lambda t, i=i: (0, 5 * wave(t, IDLE, i / 3)))
        sk.both(cb, 'rotate',
                lambda t, tc=tc, side=side: side * (seg(t, tc, tc + 0.35, 9, 0) + 3.5 * bump(t, tc + 0.35, 0.5) * math.sin(3 * math.pi * clamp((t - tc - 0.35) / 0.5))),
                lambda t, i=i: 0.6 * wave(t, IDLE, i / 3 + 0.25))
        fade = lambda t, tc=tc: seg(t, tc, tc + 0.15, 0, 1, linear)
        for s in (f'panel{i}', f't_desc{i}'):
            sk.both(s, 'alpha', fade, lambda t: 1)
        for s in art_slots:
            sk.anim('intro', s, 'alpha', fade)
        st = tc + 0.45
        sk.both(tb, 'scale', lambda t, st=st: (seg(t, st, st + 0.22, 2.0, 1, in_cubic),) * 2,
                lambda t, i=i: (1 + 0.025 * bump(t, 1.2 + 0.8 * i, 0.5),) * 2)
        sk.both(f't_title{i}', 'alpha', lambda t, st=st: seg(t, st, st + 0.12, 0, 1, linear), lambda t: 1)
        if kind != 'wild':
            sk.both(f'art{i}', 'scale', lambda t, st=st: (seg(t, st + 0.05, st + 0.45, 0.3, 1, out_back),) * 2,
                    lambda t: (1, 1))
        sparks(sk, tb, f'tspk{i}_', st + 0.2, 7, 140 if desk else 120, 'ffd36aff', seed=20 + i)

    logo(sk, *L['logo'], t0=0.1, shine_at=(1.3, 0.55))
    dust_motes(sk, 'main', 16 if desk else 12, L['motes'], seed=7)
    twinkles(sk, 'main', L['tw'], seed=3)
    tap_text(sk, 'CLICK TO CONTINUE' if desk else 'TAP TO CONTINUE', *L['tap'], t0=2.2)
    sk.write()


# --------------------------------------------------------------------------
# BONUS screen

def bonus(variant):
    desk = variant == 'desk'
    W, H = (1932, 940) if desk else (780, 1416)
    sk = Skel(f'bonus_{variant}', W, H, 1.25 if desk else 1.15)
    add_art(sk, ['logo', 'logo_flash', 'glow', 'spark', 'star', 'rays', 'flash', 'hole',
                 'wild_big', 'wild_big_flash', 'wolf', 'gun', 'whiskey'])
    # shake bone: everything hangs off it, the gunshots kick it
    sk.bone('main')
    if desk:
        L = dict(logo=(0, 350, 330), rays=(0, -20, 1150), won=(0, 196, 56), plaque=(0, -22, 420, 268),
                 title=(0, -240, 100, 720), tap=(0, -400, 48),
                 wild=(-585, -55, 640), tiles=[('wolf', 575, 95, 270, -6), ('gun', 490, -205, 200, 9),
                                               ('whiskey', 680, -215, 200, -8)],
                 holes=[(-165, 82), (170, -75), (150, 88)], motes=(-960, 960, -470, 470),
                 tw=[(-300, 250, 0.5), (300, 230, 0.45), (-230, -130, 0.4), (240, -150, 0.4), (0, 300, 0.35)])
    else:
        L = dict(logo=(0, 572, 380), rays=(0, 170, 1000), won=(0, 392, 54), plaque=(0, 205, 420, 268),
                 title=(0, -2, 100, 680), tap=(0, -640, 48),
                 wild=(-185, -385, 420), tiles=[('wolf', 160, -265, 210, -6), ('gun', 100, -478, 150, 9),
                                                ('whiskey', 250, -468, 150, -8)],
                 holes=[(-165, 82), (170, -75), (150, 88)], motes=(-390, 390, -708, 708),
                 tw=[(-300, 420, 0.45), (300, 400, 0.4), (-280, 90, 0.4), (290, 60, 0.35), (0, -160, 0.35)])
    shots = [1.2, 1.38, 1.56]

    def shake(t):
        k = sum(bump(t, s, 0.16) for s in shots) + 1.4 * bump(t, 1.82, 0.2)
        return (9 * k * math.sin(t * 97), 7 * k * math.cos(t * 83))

    sk.both('main', 'translate', shake, lambda t: (0, 0))

    sun_rays(sk, 'main', *L['rays'], t0=0.3, alpha=0.55)

    # hero wild + the pay-symbol tiles flanking the plaque
    wx, wy, wh = L['wild']
    wb = sk.bone('wild_b', 'main', wx, wy)
    sk.slot('wild_glow', wb, 'glow', w=wh * 0.95, h=wh * 1.2, blend='additive', color='ffa23cff')
    sk.slot('wild', wb, 'wild_big', h=wh)
    sk.slot('wild_flash', wb, 'wild_big_flash', h=wh, blend='additive')
    from_x = -560 if desk else -420
    sk.both(wb, 'translate', lambda t: (seg(t, 0.2, 0.8, from_x, 0, out_back), 0),
            lambda t: (0, 6 * wave(t, IDLE)))
    sk.both(wb, 'scale', lambda t: (1, 1), lambda t: (1 + 0.006 * wave(t, IDLE / 2), 1 + 0.014 * wave(t, IDLE / 2)))
    sk.both('wild', 'alpha', lambda t: seg(t, 0.2, 0.4, 0, 1, linear), lambda t: 1)
    sk.both('wild_flash', 'alpha', lambda t: 0.8 * bump(t, 0.75, 0.4),
            lambda t: 0.35 * bump(t, 2.6, 0.6))
    sk.both('wild_glow', 'alpha', lambda t: 0.6 * seg(t, 0.6, 1.1, 0, 1), lambda t: 0.45 + 0.15 * math.cos(2 * math.pi * t / 2))
    for j, (region, tx, ty, tw, rot) in enumerate(L['tiles']):
        b = sk.bone(f'tile{j}', 'main', tx, ty, rot=rot)
        sk.slot(f'tile{j}', b, region, w=tw)
        t0 = 0.35 + 0.12 * j
        sk.both(b, 'translate', lambda t, t0=t0: (seg(t, t0, t0 + 0.55, 520, 0, out_back), seg(t, t0, t0 + 0.55, 160, 0)),
                lambda t, j=j: (0, 8 * wave(t, IDLE / 2, j * 0.21)))
        sk.both(b, 'rotate', lambda t, t0=t0, j=j: seg(t, t0, t0 + 0.55, 70 * (1 if j % 2 else -1), 0),
                lambda t, j=j: 2.5 * wave(t, IDLE, j * 0.33))
        sk.both(f'tile{j}', 'alpha', lambda t, t0=t0: seg(t, t0, t0 + 0.12, 0, 1, linear), lambda t: 1)

    logo(sk, *L['logo'], t0=0.05, shine_at=(2.2, 0.55))

    # "YOU HAVE WON"
    ob = sk.bone('won_b', 'main', L['won'][0], L['won'][1])
    text_slot(sk, 't_won', text_img('YOU HAVE WON', 'luckiest', 72, fill=CREAM, stroke='2a1204', glow='ff8a2a', glow_r=10),
              ob, h=L['won'][2])
    sk.both(ob, 'scale', lambda t: (seg(t, 0.75, 1.1, 0.4, 1, out_back),) * 2, lambda t: (1, 1))
    sk.both('t_won', 'alpha', lambda t: seg(t, 0.75, 0.9, 0, 1, linear), lambda t: 1)

    # log plaque: the DOM draws the real spin count over bone "count"
    px, py, pw, ph = L['plaque']
    sk.image('plaque', log_panel(int(pw * sk.res), int(ph * sk.res), scale=0.42))
    pb = sk.bone('plaque_b', 'main', px, py)
    sk.slot('plaque_glow', pb, 'glow', w=pw * 1.6, h=ph * 1.9, blend='additive', color='ffb347ff')
    sk.slot('plaque', pb, 'plaque', w=pw, h=ph)
    sk.bone('count', pb, 0, ph * 0.06)
    sk.both(pb, 'scale', lambda t: (seg(t, 0.85, 1.2, 0.1, 1, out_back),) * 2,
            lambda t: (1 + 0.018 * (1 - math.cos(2 * math.pi * t / 1.0)) / 2,) * 2)
    sk.both('plaque', 'alpha', lambda t: seg(t, 0.85, 0.95, 0, 1, linear), lambda t: 1)
    sk.both('plaque_glow', 'alpha', lambda t: 0.5 * seg(t, 1.0, 1.4, 0, 1), lambda t: 0.4 + 0.1 * math.cos(2 * math.pi * t))

    # three gunshots into the plaque: muzzle flash, then a hole stays
    for k, ((hx, hy), st) in enumerate(zip(L['holes'], shots)):
        hb = sk.bone(f'hole{k}', 'main', px + hx, py + hy, rot=40 * k)
        sk.slot(f'hole{k}', hb, 'hole', w=66)
        sk.slot(f'flash{k}', hb, 'flash', w=200, blend='additive')
        sk.both(f'hole{k}', 'alpha', lambda t, st=st: 1 if t >= st + 0.03 else 0, lambda t: 1)
        sk.both(f'flash{k}', 'alpha', lambda t, st=st: 0 if t < st else seg(t, st, st + 0.18, 1, 0, linear), lambda t: 0)
        sk.both(hb, 'scale', lambda t, st=st: (seg(t, st, st + 0.18, 0.4, 1.3),) * 2, lambda t: (1, 1))
        sparks(sk, hb, f'hspk{k}_', st, 6, 110, 'ffd36aff', seed=50 + k)

    # FREE SPINS title stamps in after the shots
    tx, ty, th, tmax = L['title']
    tb = sk.bone('title_b', 'main', tx, ty)
    tim = text_img('FREE SPINS', 'rye', 120, fill=GOLD, stroke='2a1204', glow='ff7a1a', glow_r=14)
    text_slot(sk, 't_title', tim, tb, h=th, maxw=tmax)
    sk.image('t_title_flash', silhouette(tim, 0.9, (255, 240, 200)))
    tw_ = min(tmax, th * tim.width / tim.height)
    sk.slot('t_title_flash', tb, 't_title_flash', w=tw_, blend='additive')
    sk.both(tb, 'scale', lambda t: (seg(t, 1.82, 2.05, 2.4, 1, in_cubic),) * 2,
            lambda t: (1 + 0.03 * (1 - math.cos(2 * math.pi * t / 2)) / 2,) * 2)
    sk.both('t_title', 'alpha', lambda t: seg(t, 1.82, 1.92, 0, 1, linear), lambda t: 1)
    sk.both('t_title_flash', 'alpha', lambda t: 0 if t < 2.05 else seg(t, 2.05, 2.45, 0.9, 0),
            lambda t: 0.4 * bump(t, 1.6, 0.5))
    sparks(sk, tb, 'ttspk', 2.05, 14, 360 if desk else 300, 'ffd36aff', seed=31)
    dust_puff(sk, tb, 'tpuff', 2.05, 260, -th * 0.4, seed=8, n=8)

    dust_motes(sk, 'main', 16 if desk else 12, L['motes'], seed=17)
    twinkles(sk, 'main', L['tw'], seed=5, start=2.2)
    tap_text(sk, 'CLICK TO START' if desk else 'TAP TO START', *L['tap'], t0=2.35)
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        feature(v)
        bonus(v)
