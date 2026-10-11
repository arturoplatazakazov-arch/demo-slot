"""Tiny toolkit for authoring full-screen Spine 4.1 skeletons in code.

Used for slot "feature (preview)" and "bonus" screens: the skeleton is laid out
on the game's design canvas (origin = canvas centre, 1 unit = 1 design px,
y up) and has two clips, `intro` and a seamless looping `idle` (first idle
frame == last intro frame).

Every animated property is a python function of time, sampled at FPS and then
thinned (a key is dropped when linear interpolation between its neighbours
reproduces it), so motion is written like code, not keyframes. Images are
PIL images; on write() each region is resized to its largest on-screen use x
`res`, shelf-packed into 2048px atlas pages and saved premultiplied.
"""

import json
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

FPS = 30


# --------------------------------------------------------------------------
# easing / timing

def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def lerp(a, b, t):
    return a + (b - a) * t


def linear(t):
    return t


def out_cubic(t):
    return 1 - (1 - t) ** 3


def in_cubic(t):
    return t ** 3


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
    """sin over `period`, 0 at t=0 when phase=0."""
    return math.sin(2 * math.pi * (t / period + phase))


def breathe(t, period, amp):
    """1 -> 1+amp -> 1 over `period` (cosine), exactly 1 at t=0."""
    return 1 + amp * (1 - math.cos(2 * math.pi * t / period)) / 2


def pulse(t, period, phase=0.0, sharp=8):
    """Short bright blip once per period."""
    return max(0.0, math.sin(2 * math.pi * (t / period - phase))) ** sharp


# --------------------------------------------------------------------------
# image helpers

def trim(im, pad=0, thr=8):
    bb = im.getchannel('A').point(lambda a: 255 if a > thr else 0).getbbox()
    im = im.crop(bb)
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


def text_img(text, fnt, fill, stroke='3a0610', stroke_w=None, glow=None, glow_r=None,
             shadow=None, slant=0.0, track=0):
    """Gradient-filled text with stroke, optional outer glow and drop shadow."""
    size = fnt.size
    stroke_w = stroke_w if stroke_w is not None else max(2, size // 10)
    glow_r = glow_r if glow_r is not None else max(4, size // 5)
    pad = stroke_w + glow_r * 3 + 12
    widths = [fnt.getlength(ch) for ch in text]
    w = int(sum(widths) + track * (len(text) - 1)) + pad * 2
    h = int(size * 1.4) + pad * 2
    mask = Image.new('L', (w, h))
    smask = Image.new('L', (w, h))
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x = pad
    for ch, cw in zip(text, widths):
        d.text((x, pad), ch, font=fnt, fill=255)
        ds.text((x, pad), ch, font=fnt, fill=255, stroke_width=stroke_w, stroke_fill=255)
        x += cw + track
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(glow_r)).point(lambda a: min(255, int(a * 1.5)))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    if shadow:
        sh = smask.filter(ImageFilter.GaussianBlur(max(1, size // 18)))
        sh = ImageChops.offset(sh, 0, max(2, size // 14))
        out.paste(Image.new('RGBA', (w, h), hexc(shadow, 200)), (0, 0), sh)
    out.paste(Image.new('RGBA', (w, h), hexc(stroke)), (0, 0), smask)
    bb = mask.getbbox()
    grad = vgrad((w, bb[3] - bb[1]), fill)
    fill_im = Image.new('RGBA', (w, h))
    fill_im.paste(grad, (0, bb[1]))
    out.paste(fill_im, (0, 0), mask)
    if slant:
        out = out.transform(out.size, Image.AFFINE, (1, slant, -slant * h / 2, 0, 1, 0), Image.BICUBIC)
    return trim(out, thr=2)


def flash_of(im, k=1.0):
    """White silhouette of `im` (for additive flashes)."""
    a = im.getchannel('A').point(lambda v: int(v * k))
    out = Image.new('RGBA', im.size, (255, 255, 255, 0))
    out.putalpha(a)
    return out


def soft_glow(size=256):
    """White radial glow, alpha falls off smoothly to 0 at the edge."""
    g = Image.radial_gradient('L').resize((size, size))  # 0 centre -> 255 edge
    a = g.point(lambda v: int(255 * clamp(1 - v / 180) ** 2.2))
    im = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    im.putalpha(a)
    return im


def spark(w=64, h=16):
    """Horizontal white streak, hot centre."""
    m = Image.new('L', (w * 4, h * 4))
    ImageDraw.Draw(m).ellipse([0, h * 1.2, w * 4 - 1, h * 2.8], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(h * 0.5)).resize((w, h), Image.LANCZOS)
    im = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    im.putalpha(m)
    return im


def rays(size, n=16, col=(255, 255, 255), width=0.42):
    big = size * 2
    m = Image.new('L', (big, big))
    d = ImageDraw.Draw(m)
    cx = cy = big / 2
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + 2 * math.pi / n * width
        d.polygon([(cx, cy), (cx + big * math.cos(a0), cy + big * math.sin(a0)),
                   (cx + big * math.cos(a1), cy + big * math.sin(a1))], fill=255)
    m = m.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(size / 140))
    fall = Image.radial_gradient('L').resize((size, size))
    fall = fall.point(lambda v: int(255 * clamp(1 - v / 200) ** 1.6))
    m = ImageChops.multiply(m, fall)
    im = Image.new('RGBA', (size, size), col + (0,))
    im.putalpha(m)
    return im


def premultiply(im):
    r, g, b, a = im.split()
    return Image.merge('RGBA', (ImageChops.multiply(r, a), ImageChops.multiply(g, a),
                                ImageChops.multiply(b, a), a))


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
# skeleton builder

class Skel:
    TOL = {'translate': 0.25, 'scale': 0.0015, 'rotate': 0.08, 'alpha': 0.004}

    def __init__(self, name, w, h, res, out_dir, intro=3.0, idle=4.0):
        self.name, self.w, self.h, self.res, self.out_dir = name, w, h, res, out_dir
        self.intro, self.idle = intro, idle
        self.bones = [{'name': 'root'}]
        self.slots = []
        self.atts = {}
        self.images = {}
        self.res_of = {}  # region -> res override (soft fx survive a lower one)
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
        """`translate` is authored as the bone's absolute local position; Spine
        adds timeline values to the setup pose, so the setup x/y is taken off."""
        dur = self.intro if which == 'intro' else self.idle
        if prop == 'translate':
            b = next(b for b in self.bones if b['name'] == target)
            bx, by = b.get('x', 0), b.get('y', 0)
            if bx or by:
                fn = (lambda f: lambda t: (f(t)[0] - bx, f(t)[1] - by))(fn)
        keys = self._thin(self._sample(fn, dur), self.TOL[prop])
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

    def write(self):
        out = os.path.join(self.out_dir, self.name)
        os.makedirs(out, exist_ok=True)
        for f in os.listdir(out):
            if f.startswith('animation'):
                os.remove(os.path.join(out, f))
        regions = {}
        for r, im in self.images.items():
            if r not in self.need:
                continue
            w, _ = self.need[r]
            tw = max(2, min(im.width, int(math.ceil(w * self.res_of.get(r, self.res)))))
            th = max(2, int(round(tw * im.height / im.width)))
            regions[r] = im.resize((tw, th), Image.LANCZOS) if (tw, th) != im.size else im
        pages = pack(regions)
        atlas = []
        for pi, (page, placed) in enumerate(pages):
            fname = 'animation.png' if pi == 0 else f'animation{pi + 1}.png'
            # Same recompression as the rest of front/img: 256-colour octree +
            # dither keeps PMA atlases visually lossless at ~1/4 the bytes.
            page = premultiply(page).quantize(256, Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
            page.save(os.path.join(out, fname), optimize=True)
            atlas += [fname, f'size:{page.width},{page.height}', 'filter:Linear,Linear', 'pma:true']
            for r, (x, y, w, h) in placed.items():
                atlas += [r, f'bounds:{x},{y},{w},{h}']
            atlas.append('')
        with open(os.path.join(out, 'animation.atlas'), 'w') as f:
            f.write('\n'.join(atlas))
        data = {
            'skeleton': {'hash': self.name, 'spine': '4.1.24', 'x': -self.w / 2, 'y': -self.h / 2,
                         'width': self.w, 'height': self.h, 'fps': FPS},
            'bones': self.bones,
            'slots': self.slots,
            'skins': [{'name': 'default', 'attachments': self.atts}],
            'animations': self.anims,
        }
        with open(os.path.join(out, 'animation.json'), 'w') as f:
            json.dump(data, f, separators=(',', ':'))
        print(self.name, 'bones', len(self.bones), 'slots', len(self.slots),
              'pages', [p.size for p, _ in pages])
