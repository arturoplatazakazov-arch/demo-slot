"""Neon Joker Spins: the standard Spine FX pack, generated in code.

Same kit and conventions as scripts/volt_coins_fx.py (game #1 of the line):
spine_screen_kit skeletons, every one authored in the pixel space of the DOM
element it is anchored to (js/neon-joker-spins/fx.js), so CSS stays the only
source of layout truth. Output: front/img/neon-joker-spins/spine/<name>/.

  frame / frame_mob  frame*.webp px. Marquee bulbs (found in the art) chase,
                     magenta/cyan tubes breathe and buzz, a light sweep, the
                     window edge glows. `idle` 4s, `win` 1.2s, `charge` 1.4s
                     (Hold & Win entry), `bonus` 2s (free spins / round).
  logo               logo.webp px. Neon letters with the odd tube flicker,
                     bulbs, glints on the bells, sweep. `idle` 5s, `win` 1.2s.
  jp_<tier>          jackpot plates: `idle` (tier-paced shimmer, GRAND the
                     richest), `hit` 1.2s.
  sign_<key>         popup title signs: `in` 0.55s (power-on: flicker, pop,
                     flash) -> `idle` 2s loop (bulbs + sweep).
  symbols            360x360 = one symbol tile. One 1.1s clip per code, each
                     with its own motion; starts and ends on the static tile.
  winlines           reel-window units (560x550). `line{n}_in` / `line{n}_loop`:
                     a neon tube draws through the cells, comets run along it.
  bg_desk / bg_mob   background px. `idle` 8s (bokeh drift, slow light passes),
                     `bonus` 4s (crossing searchlights, gold confetti).
  mascot             mascot.webp px. `idle` 4s (breath, sway, finger-snap
                     spark), `cheer` 1.2s, `laugh` 1.6s.
  bigwin             1200x1200 square. `loop` 2s: rotating rays, coin rain,
                     sparkles — behind the Big/Mega/Epic popup.

    .venv/bin/python scripts/neon_joker_spins_fx.py [names...] [--preview DIR]
"""

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import volt_coins_fx as V  # noqa: E402
from spine_screen_kit import (  # noqa: E402
    clamp, in_out_sine, lerp, out_back, out_cubic, pulse, rays, seg, soft_glow, spark,
)

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'neon-joker-spins')
IMG = os.path.join(ROOT, 'img')
SYM = os.path.join(ROOT, 'symbols')
POP = os.path.join(ROOT, 'popups')
FXS = os.path.join(ROOT, 'fx')
OUT = os.path.join(ROOT, 'spine')

PINK = (255, 60, 172)
CYAN = (44, 232, 255)
GOLD = (255, 200, 70)
WARM = (255, 225, 140)


class NFx(V.Fx):
    def __init__(self, name, w, h, res, clips):
        super().__init__(name, w, h, res, clips)
        self.out_dir = OUT


def load(path):
    if not os.path.exists(path) and path.endswith('.png'):
        path = path[:-4] + '.webp'
    return Image.open(path).convert('RGBA')


def frac(x):
    return x - math.floor(x)


def hexc(rgb):
    return '%02x%02x%02x' % rgb


# --------------------------------------------------------------------------
# reading the art

def blobs(im, cond, amin, amax, limit=80):
    """Centres of small bright blobs where cond(r, g, b, a) holds — the marquee
    bulbs of a frame/sign. Pure PIL + a flood fill (the art is small)."""
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    found = []
    step = 2
    for y in range(0, h, step):
        for x in range(0, w, step):
            i = y * w + x
            if seen[i]:
                continue
            r, g, b, a = px[x, y]
            if not cond(r, g, b, a):
                continue
            stack = [(x, y)]
            seen[i] = 1
            n = sx = sy = 0
            while stack:
                cx, cy = stack.pop()
                n += 1
                sx += cx
                sy += cy
                if n > amax * 2:
                    break
                for nx, ny in ((cx + step, cy), (cx - step, cy), (cx, cy + step), (cx, cy - step)):
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if not seen[j]:
                            rr, gg, bb, aa = px[nx, ny]
                            if cond(rr, gg, bb, aa):
                                seen[j] = 1
                                stack.append((nx, ny))
            area = n * step * step
            if amin <= area <= amax:
                found.append((sx / n, sy / n, area))
    found.sort(key=lambda b: -b[2])
    return [(x, y) for x, y, _ in found[:limit]]


def is_bulb(r, g, b, a):
    return a > 200 and r > 235 and g > 200 and b < 190 and (r + g) > 2.25 * b + 230


def color_mask(im, fn, blur=0):
    """Additive layer of the pixels whose colour matches fn (neon tubes)."""
    r, g, b, a = [ch.load() for ch in im.split()]
    w, h = im.size
    m = Image.new('L', (w, h))
    mp = m.load()
    for y in range(h):
        for x in range(w):
            mp[x, y] = int(255 * fn(r[x, y], g[x, y], b[x, y])) if a[x, y] > 40 else 0
    if blur:
        m = ImageChops.lighter(m, m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, v * 2)))
    out = im.copy()
    out.putalpha(ImageChops.multiply(m, im.getchannel('A').point(lambda v: 255 if v > 40 else v * 6)))
    return out


def magenta(r, g, b):
    return clamp(((r + b) / 2 - g - 40) / 90) * clamp((r - 120) / 80)


def cyanish(r, g, b):
    return clamp(((g + b) / 2 - r - 40) / 90) * clamp((b - 120) / 80)


def small(im, k):
    return im.resize((max(2, int(im.width * k)), max(2, int(im.height * k))), Image.LANCZOS)


# --------------------------------------------------------------------------
# shared pieces

def add_bulbs(sk, pts, size, col=WARM, name='bulb'):
    sk.image(name, V.glow_dot(128, core=0.32, col=col))
    out = []
    for i, (x, y) in enumerate(pts):
        n = f'{name}{i}'
        bx, by = sk.xy(x, y)
        sk.hidden_slot(n, 'root', name, w=size, x=bx, y=by, blend='additive')
        out.append((n, x, y))
    # order round the centre for the chase
    cx, cy = sk.w / 2, sk.h / 2
    out.sort(key=lambda b: math.atan2(b[2] - cy, b[1] - cx))
    return [n for n, _, _ in out]


def add_sweep(sk, im, n=16, res=0.4, gamma=1.5, gain=1.3):
    hl = V.highlight(im, gamma=gamma, gain=gain)
    out = []
    for i, (part, x0, x1) in enumerate(V.strips(hl, n)):
        r = f'sw{i}'
        sk.image(r, part)
        sk.res_of[r] = res
        sk.hidden_slot(r, 'root', r, w=x1 - x0, x=sk.xy((x0 + x1) / 2, 0)[0], blend='additive')
        out.append((r, (x0 + x1) / 2))
    return out


def sweep_fn(W, cx, t0, dur, peak, sigma=110):
    def f(t):
        if not t0 <= t <= t0 + dur:
            return 0.0
        sx = lerp(-200, W + 200, in_out_sine((t - t0) / dur))
        return peak * math.exp(-((cx - sx) / sigma) ** 2)
    return f


def chase(i, n, t, speed, width=3, base=0.25, peak=1.0):
    """Marquee chase: a lit run of `width` bulbs travelling round the ring."""
    head = frac(t * speed) * n
    d = min((head - i) % n, (i - head) % n)
    return base + (peak - base) * clamp(1 - d / width) ** 1.5


def add_tubes(sk, im, blur=6):
    """Magenta + cyan neon tube layers (additive copies of those pixels)."""
    pink = small(color_mask(small(im, 0.5), magenta, blur), 2.0)
    cyan = small(color_mask(small(im, 0.5), cyanish, blur), 2.0)
    sk.image('tpink', pink)
    sk.image('tcyan', cyan)
    sk.res_of['tpink'] = sk.res_of['tcyan'] = 0.5
    sk.hidden_slot('tpink', 'root', 'tpink', w=sk.w, blend='additive')
    sk.hidden_slot('tcyan', 'root', 'tcyan', w=sk.w, blend='additive')


def buzz(t, seed, rate=0.05, chance=0.18):
    """Neon tube buzz: mostly on, now and then a fast dip."""
    k = int(t / rate)
    r = random.Random(seed * 1000 + k).random()
    return 0.55 if r < chance else 1.0


# --------------------------------------------------------------------------
# frame

def build_frame(name):
    src = 'frame.webp' if name == 'frame' else 'frame_mob.webp'
    im = load(os.path.join(IMG, src))
    W, H = im.size
    sk = NFx(name, W, H, 0.7, {'idle': 4.0, 'win': 1.2, 'charge': 1.4, 'bonus': 2.0})

    halo = V.silhouette_halo(small(im, 0.5), 30, 14, PINK)
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.6
    sk.hidden_slot('halo', 'root', 'halo', w=W + 120, blend='additive')
    add_tubes(sk, im)

    # window edge (cyan) — from the measured window fractions
    WIN = {'frame': (0.1889, 0.2364, 0.5820, 0.5548), 'frame_mob': (0.1176, 0.1124, 0.7630, 0.7743)}[name]
    wl, wt, ww, wh = WIN[0] * W, WIN[1] * H, WIN[2] * W, WIN[3] * H
    edge, _ = V.rect_line(int(ww), int(wh), 5, 9, r=10)
    sk.image('edge', edge)
    sk.hidden_slot('edge', 'root', 'edge', '5fe8ff', w=edge.width, x=sk.xy(wl + ww / 2, 0)[0],
                   y=sk.xy(0, wt + wh / 2)[1], blend='additive')

    pts = blobs(im, is_bulb, 60, 2600)
    bulbs = add_bulbs(sk, pts, size=max(46, min(W, H) * 0.06))
    print(f'  {name}: {len(bulbs)} bulbs')
    sweep = add_sweep(sk, im, 16, 0.4)
    nb = max(1, len(bulbs))

    clips = {
        'idle': dict(speed=0.25, width=3, base=0.25, peak=0.85, halo=(0.10, 0.06, 4.0), edge=(0.0, 0.0),
                     tubes=(0.15, 0.1), sweep=(1.6, 1.4, 0.4)),
        'win': dict(speed=1.6, width=4, base=0.35, peak=1.0, halo=(0.35, 0.25, 0.6), edge=(0.3, 0.25),
                    tubes=(0.45, 0.35), sweep=(0.05, 0.8, 0.8)),
        'bonus': dict(speed=0.9, width=5, base=0.4, peak=1.0, halo=(0.3, 0.12, 2.0), edge=(0.45, 0.15),
                      tubes=(0.35, 0.2), sweep=(0.6, 1.0, 0.5)),
    }
    for clip, c in clips.items():
        for i, n in enumerate(bulbs):
            sk.anim(clip, n, 'alpha', lambda t, i=i, c=c: chase(i, nb, t, c['speed'], c['width'], c['base'], c['peak']))
        h0, h1, hp = c['halo']
        sk.anim(clip, 'halo', 'alpha', lambda t, h0=h0, h1=h1, hp=hp: h0 + h1 * (1 + math.sin(2 * math.pi * t / hp)) / 2)
        e0, e1 = c['edge']
        sk.anim(clip, 'edge', 'alpha', lambda t, e0=e0, e1=e1, d=sk.durs[clip]: e0 + e1 * (1 + math.sin(2 * math.pi * t / d * 2)) / 2)
        t0, t1 = c['tubes']
        sk.anim(clip, 'tpink', 'alpha', lambda t, t0=t0, t1=t1, d=sk.durs[clip]: (t0 + t1 * (1 + math.sin(2 * math.pi * t / d)) / 2) * buzz(t, 3))
        sk.anim(clip, 'tcyan', 'alpha', lambda t, t0=t0, t1=t1, d=sk.durs[clip]: (t0 + t1 * (1 + math.cos(2 * math.pi * t / d)) / 2) * buzz(t, 7))
        s0, sd, sp = c['sweep']
        for r, cx in sweep:
            sk.anim(clip, r, 'alpha', sweep_fn(W, cx, s0, sd, sp))

    # charge: bulbs light up one by one round the frame, then everything flashes
    for i, n in enumerate(bulbs):
        ti = 0.9 * i / nb
        sk.anim('charge', n, 'alpha', lambda t, ti=ti: 0.15 if t < ti else (1.0 if t < 1.0 else seg(t, 1.0, 1.4, 1.0, 0.6)))
    sk.anim('charge', 'halo', 'alpha', lambda t: seg(t, 0, 0.9, 0.1, 0.5) if t < 0.9 else (seg(t, 0.9, 1.0, 0.5, 1.0) if t < 1.0 else seg(t, 1.0, 1.4, 1.0, 0.3)))
    sk.anim('charge', 'edge', 'alpha', lambda t: seg(t, 0.3, 1.0, 0, 1.0) if t < 1.0 else seg(t, 1.0, 1.4, 1.0, 0.5))
    sk.anim('charge', 'tpink', 'alpha', lambda t: seg(t, 0, 1.0, 0.2, 0.9) if t < 1.0 else seg(t, 1.0, 1.4, 0.9, 0.35))
    sk.anim('charge', 'tcyan', 'alpha', lambda t: seg(t, 0, 1.0, 0.2, 0.9) if t < 1.0 else seg(t, 1.0, 1.4, 0.9, 0.35))
    for r, cx in sweep:
        sk.anim('charge', r, 'alpha', sweep_fn(W, cx, 0.9, 0.5, 1.0, 150))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# neon signs: logo, jackpot plates, popup titles

def build_sign(name, im, clips, col=PINK, glints=6, bulb_scale=0.045, res=1.0, draw=True):
    """A sign = the art itself (drawn by the skeleton when `draw`, so the
    power-on can flicker it), halo, tube layers, its bulbs, glints, sweep."""
    W, H = im.size
    sk = NFx(name, W, H, res, clips)
    halo = V.silhouette_halo(small(im, 0.5), 30, 14, col, inner=0.6)
    sk.image('halo', halo)
    sk.res_of['halo'] = 0.5
    sk.hidden_slot('halo', 'root', 'halo', w=W + 120, blend='additive')
    if draw:
        sk.image('art', im)
        sk.res_of['art'] = 1.0
        sk.slot('art', sk.bone('pop'), 'art', w=W)
    add_tubes(sk, im, blur=4)
    pts = blobs(im, is_bulb, 30, 1800)
    bulbs = add_bulbs(sk, pts, size=max(26, min(W, H) * bulb_scale * 2.2))
    sweep = add_sweep(sk, im, 14, 0.35)
    sk.image('glint', V.star4(192))
    # glints on the brightest spots of the art
    lum = small(im, 0.25).convert('L')
    lp = lum.load()
    cand = sorted(((lp[x, y], x, y) for y in range(lum.height) for x in range(lum.width)), reverse=True)
    picks = []
    for v, x, y in cand:
        if all((x - px) ** 2 + (y - py) ** 2 > (lum.width / 6) ** 2 for px, py in picks):
            picks.append((x, y))
        if len(picks) >= glints:
            break
    gl = []
    for gi, (x, y) in enumerate(picks):
        bx, by = sk.xy(x * 4, y * 4)
        b = sk.bone(f'g{gi}', x=bx, y=by)
        sk.hidden_slot(f'g{gi}', b, 'glint', w=min(W, H) * 0.42, blend='additive')
        gl.append((b, f'g{gi}', gi / max(1, len(picks))))
    return sk, bulbs, sweep, gl


def sign_loop(sk, clip, bulbs, sweep, gl, dur, speed=0.5, halo=(0.15, 0.15), sweep_at=0.3, glint_rate=1.0):
    nb = max(1, len(bulbs))
    for i, n in enumerate(bulbs):
        sk.anim(clip, n, 'alpha', lambda t, i=i: chase(i, nb, t, speed, 3, 0.3, 1.0))
    sk.anim(clip, 'halo', 'alpha', lambda t: halo[0] + halo[1] * (1 + math.sin(2 * math.pi * t / dur)) / 2)
    sk.anim(clip, 'tpink', 'alpha', lambda t: 0.3 * buzz(t, 11, chance=0.08))
    sk.anim(clip, 'tcyan', 'alpha', lambda t: 0.3 * buzz(t + 0.4, 13, chance=0.08))
    for r, cx in sweep:
        sk.anim(clip, r, 'alpha', sweep_fn(sk.w, cx, sweep_at * dur, min(1.0, 0.5 * dur), 0.75))
    for b, n, ph in gl:
        sk.anim(clip, n, 'alpha', lambda t, ph=ph: pulse(t / dur * glint_rate, 1.0, ph, 12))
        sk.anim(clip, b, 'scale', lambda t, ph=ph: (0.2 + 0.9 * pulse(t / dur * glint_rate, 1.0, ph, 6),) * 2)
        sk.anim(clip, b, 'rotate', lambda t: 120 * t / dur)


def build_logo():
    meta = layer_json('logo')
    if meta:
        return build_logo_layered(meta)
    im = load(os.path.join(IMG, 'logo.webp'))
    sk, bulbs, sweep, gl = build_sign('logo', im, {'idle': 5.0, 'win': 1.2}, glints=6, draw=False)
    sign_loop(sk, 'idle', bulbs, sweep, gl, 5.0, speed=0.4, halo=(0.12, 0.12), sweep_at=0.35)
    sign_loop(sk, 'win', bulbs, sweep, gl, 1.2, speed=2.0, halo=(0.35, 0.3), sweep_at=0.02, glint_rate=2)
    # a «bad tube» moment in idle: the NEON/SPINS cyan letters stutter at 4.1s
    sk.anim('idle', 'tcyan', 'alpha', lambda t: (0.75 if int(t / 0.04) % 2 else 0.0) if 4.05 < t < 4.35 else 0.25 * buzz(t, 17, chance=0.05))
    sk.write()
    return sk


LAYERS = os.path.join(ROOT, 'layers')


def layer_json(name):
    import json
    p = os.path.join(LAYERS, f'{name}.json')
    return json.load(open(p)) if os.path.exists(p) else None


def build_logo_layered(meta):
    """Letter-by-letter neon logo (layers re-assembled by the build script;
    the static logo.webp is the same composite, so idle == the static art)."""
    W, H = meta['size']
    rows = meta['layers']
    sk = NFx('logo', W, H, 1.0, {'on': 1.9, 'idle': 6.0, 'win': 1.2})
    lay = {}
    order = ['plate', 'neon', 'J', 'O', 'K', 'E', 'R', 'spins', 'hat', 'bell1', 'bell2', 'bell3']
    for n in order:
        im = load(os.path.join(LAYERS, f'{n}.webp'))
        r = rows[n]
        sk.image(n, im)
        sk.res_of[n] = r['w'] / im.width
        par = 'hatb' if n.startswith('bell') else 'root'
        x, y = sk.xy(r['x'], r['y'])
        if n == 'hat':
            sk.bone('hatb', x=x, y=y - r['h'] * 0.35)
            b = sk.bone('hat_b', parent='hatb')
            sk.slot(n, b, n, w=r['w'], y=r['h'] * 0.35)
        elif par == 'hatb':
            hx, hy = sk.xy(rows['hat']['x'], rows['hat']['y'] - rows['hat']['h'] * 0.35)
            b = sk.bone(f'{n}_b', parent='hatb', x=x - hx, y=y - hy + r['h'] * 0.45)
            sk.slot(n, b, n, w=r['w'], y=-r['h'] * 0.45)
        else:
            b = sk.bone(f'{n}_b', x=x, y=y)
            sk.slot(n, b, n, w=r['w'])
        lay[n] = b
    # glow layers
    plate = load(os.path.join(LAYERS, 'plate.webp'))
    pr = rows['plate']
    k = pr['w'] / plate.width
    pts = [(pr['x'] - pr['w'] / 2 + x * k, pr['y'] - pr['h'] / 2 + y * k) for x, y in blobs(plate, is_bulb, 30, 1600)]
    bulbs = add_bulbs(sk, pts, size=max(26, pr['h'] * 0.09))
    nb = max(1, len(bulbs))
    sk.image('lglow', V.tint(soft_glow(256), (255, 200, 90)))
    sk.res_of['lglow'] = 0.3
    letters = ['J', 'O', 'K', 'E', 'R']
    for c in letters:
        sk.hidden_slot(f'{c}_glow', lay[c], 'lglow', 'ff3cac', w=rows[c]['w'] * 1.8, blend='additive')
        hl = V.highlight(load(os.path.join(LAYERS, f'{c}.webp')), gamma=1.3, gain=1.5)
        sk.image(f'{c}_hl', hl)
        sk.res_of[f'{c}_hl'] = 0.4
        sk.hidden_slot(f'{c}_hl', lay[c], f'{c}_hl', w=rows[c]['w'], blend='additive')
    neon_on = lambda t: (1.0 if int(t / 0.035) % 2 else 0.15)

    # ON (power-on): plate, bulbs, NEON buzz, letters drop one by one, SPINS, hat pops
    sk.anim('on', 'plate', 'alpha', lambda t: 0.0 if t < 0.05 else (neon_on(t) if t < 0.3 else 1.0))
    for i, n in enumerate(bulbs):
        ti = 0.2 + 0.55 * i / nb
        sk.anim('on', n, 'alpha', lambda t, ti=ti: 0.0 if t < ti else seg(t, ti, ti + 0.1, 1.0, 0.6))
    sk.anim('on', 'neon', 'alpha', lambda t: 0.0 if t < 0.45 else (neon_on(t) if t < 0.8 else 1.0))
    for i, c in enumerate(letters):
        t0 = 0.75 + 0.1 * i
        x0, y0 = sk.xy(rows[c]['x'], rows[c]['y'])
        sk.anim('on', c, 'alpha', lambda t, t0=t0: 0.0 if t < t0 else 1.0)
        sk.anim('on', lay[c], 'translate', lambda t, t0=t0, x0=x0, y0=y0: (x0, y0 + (0 if t > t0 + 0.28 else 260 * (1 - out_back(clamp((t - t0) / 0.28), 1.4)))))
        sk.anim('on', lay[c], 'scale', lambda t, t0=t0: (1.0, 1.0) if t < t0 + 0.26 else (1 + 0.18 * math.exp(-14 * (t - t0 - 0.26)), 1 - 0.14 * math.exp(-14 * (t - t0 - 0.26))))
        sk.anim('on', f'{c}_glow', 'alpha', lambda t, t0=t0: 0.0 if t < t0 + 0.24 else 0.9 * math.exp(-5 * (t - t0 - 0.24)))
        sk.anim('on', f'{c}_hl', 'alpha', lambda t, t0=t0: 0.0 if t < t0 + 0.24 else 0.7 * math.exp(-7 * (t - t0 - 0.24)))
    sk.anim('on', 'spins', 'alpha', lambda t: 0.0 if t < 1.25 else (neon_on(t) if t < 1.5 else 1.0))
    sk.anim('on', 'hat_b', 'scale', lambda t: (seg(t, 1.35, 1.7, 0.001, 1.0, out_back) if t > 1.35 else 0.001,) * 2)
    for i in range(3):
        b = lay[f'bell{i + 1}']
        sk.anim('on', f'bell{i + 1}', 'alpha', lambda t: 0.0 if t < 1.45 else 1.0)
        sk.anim('on', b, 'rotate', lambda t, i=i: spring(t, 1.55, 28 * (1 if i % 2 else -1), 10, 3))

    def bell_sway(t, i, amp=8):
        return amp * math.sin(2 * math.pi * (t / 1.6 + i * 0.27))

    # IDLE: bulbs chase, letters breathe in a wave, a sweep runs over JOKER,
    # NEON has a bad-tube moment, the hat sways and the bells swing
    for i, n in enumerate(bulbs):
        sk.anim('idle', n, 'alpha', lambda t, i=i: chase(i, nb, t, 0.35, 3, 0.35, 1.0))
    for n in ('plate', 'spins') + tuple(letters):
        sk.anim('idle', n, 'alpha', lambda t: 1.0)
    sk.anim('idle', 'neon', 'alpha', lambda t: (0.2 if int(t / 0.04) % 2 else 1.0) if 4.2 < t < 4.5 else 1.0)
    for i, c in enumerate(letters):
        x0, y0 = sk.xy(rows[c]['x'], rows[c]['y'])
        sk.anim('idle', lay[c], 'translate', lambda t, i=i, x0=x0, y0=y0: (x0, y0 + 6 * math.sin(2 * math.pi * (t / 3 - i * 0.12))))
        sk.anim('idle', lay[c], 'scale', lambda t: (1, 1))
        sk.anim('idle', f'{c}_glow', 'alpha', lambda t, i=i: 0.12 + 0.1 * (1 + math.sin(2 * math.pi * (t / 3 - i * 0.12))) / 2)
        sk.anim('idle', f'{c}_hl', 'alpha', lambda t, i=i: 0.75 * ease_hump(t, 2.0 + i * 0.1, 2.35 + i * 0.1))
    sk.anim('idle', 'hat_b', 'scale', lambda t: (1, 1))
    sk.anim('idle', 'hat_b', 'rotate', lambda t: 2.5 * math.sin(2 * math.pi * t / 3))
    for i in range(3):
        sk.anim('idle', f'bell{i + 1}', 'alpha', lambda t: 1.0)
        sk.anim('idle', lay[f'bell{i + 1}'], 'rotate', lambda t, i=i: bell_sway(t, i) - 2.5 * math.sin(2 * math.pi * (t - 0.15) / 3) * 2)

    # WIN: letters hop in a wave, flash, fast bulbs, bells jingle
    for i, n in enumerate(bulbs):
        sk.anim('win', n, 'alpha', lambda t, i=i: chase(i, nb, t, 2.0, 4, 0.4, 1.0))
    for n in ('plate', 'neon', 'spins') + tuple(letters):
        sk.anim('win', n, 'alpha', lambda t: 1.0)
    for i, c in enumerate(letters):
        x0, y0 = sk.xy(rows[c]['x'], rows[c]['y'])
        t0 = 0.08 * i
        sk.anim('win', lay[c], 'translate', lambda t, t0=t0, x0=x0, y0=y0: (x0, y0 + 40 * ease_hump(t, t0, t0 + 0.4)))
        sk.anim('win', lay[c], 'scale', lambda t, t0=t0: (1 + 0.1 * ease_hump(t, t0, t0 + 0.4),) * 2)
        sk.anim('win', f'{c}_glow', 'alpha', lambda t, t0=t0: 0.2 + 0.7 * ease_hump(t, t0, t0 + 0.45))
        sk.anim('win', f'{c}_hl', 'alpha', lambda t, t0=t0: 0.6 * ease_hump(t, t0 + 0.1, t0 + 0.5))
    sk.anim('win', 'hat_b', 'scale', lambda t: (1, 1))
    sk.anim('win', 'hat_b', 'rotate', lambda t: 6 * math.sin(2 * math.pi * t / 0.4) * (1 - t / 1.2))
    for i in range(3):
        sk.anim('win', f'bell{i + 1}', 'alpha', lambda t: 1.0)
        sk.anim('win', lay[f'bell{i + 1}'], 'rotate', lambda t, i=i: 22 * math.sin(2 * math.pi * (t / 0.3 + i * 0.3)) * (1 - t / 1.2))
    sk.write()
    return sk


def build_plate(tier):
    im = load(os.path.join(IMG, f'jp_{tier}.webp'))
    col = {'mini': CYAN, 'minor': PINK, 'major': GOLD, 'grand': (255, 235, 170)}[tier]
    idle = {'mini': 4.0, 'minor': 3.6, 'major': 3.2, 'grand': 2.4}[tier]
    sk, bulbs, sweep, gl = build_sign(f'jp_{tier}', im, {'idle': idle, 'hit': 1.2}, col=col,
                                      glints=3 if tier != 'grand' else 5, draw=False, res=0.8)
    lvl = {'mini': 0.6, 'minor': 0.7, 'major': 0.85, 'grand': 1.0}[tier]
    sign_loop(sk, 'idle', bulbs, sweep, gl, idle, speed=0.5 + lvl * 0.5, halo=(0.08 * lvl, 0.18 * lvl), sweep_at=0.5)
    sign_loop(sk, 'hit', bulbs, sweep, gl, 1.2, speed=3.0, halo=(0.6, 0.4), sweep_at=0.0, glint_rate=2)
    sk.write()
    return sk


def build_buy():
    """BUY sign: bulbs chase, tubes breathe, a sweep runs over BUY; `press`
    is the click flash (the unlit state is a separate DOM image)."""
    im = load(os.path.join(IMG, 'buy_on.webp'))
    sk, bulbs, sweep, gl = build_sign('buy', im, {'idle': 2.4, 'press': 0.5}, col=PINK, glints=3, draw=False, res=0.8)
    sign_loop(sk, 'idle', bulbs, sweep, gl, 2.4, speed=0.9, halo=(0.12, 0.2), sweep_at=0.4)
    sign_loop(sk, 'press', bulbs, sweep, gl, 0.5, speed=4.0, halo=(0.6, 0.4), sweep_at=0.0, glint_rate=2)
    sk.write()
    return sk


SIGNS = {
    'bigWin': CYAN, 'megaWin': PINK, 'epicWin': GOLD, 'freeSpins': PINK, 'holdAndWin': GOLD, 'totalWin': CYAN,
}


def build_title(key):
    im = load(os.path.join(POP, f'{key}.webp'))
    sk, bulbs, sweep, gl = build_sign(f'sign_{key}', im, {'in': 0.55, 'idle': 2.0}, col=SIGNS[key], glints=5)
    # power-on: the sign flickers on like a real neon sign, pops past full
    # size and settles; the bulbs light in a run.
    def on(t):
        if t < 0.18:
            return 1.0 if int(t / 0.03) % 2 else 0.25
        return 1.0
    sk.anim('in', 'art', 'alpha', on)
    sk.anim('in', 'pop', 'scale', lambda t: (seg(t, 0, 0.32, 0.55, 1.0, out_back),) * 2)
    sk.anim('in', 'halo', 'alpha', lambda t: seg(t, 0.15, 0.3, 0, 0.9) if t < 0.3 else seg(t, 0.3, 0.55, 0.9, 0.3))
    sk.anim('in', 'tpink', 'alpha', lambda t: 0.0 if t < 0.15 else seg(t, 0.15, 0.55, 0.8, 0.3))
    sk.anim('in', 'tcyan', 'alpha', lambda t: 0.0 if t < 0.15 else seg(t, 0.15, 0.55, 0.8, 0.3))
    nb = max(1, len(bulbs))
    for i, n in enumerate(bulbs):
        ti = 0.15 + 0.35 * i / nb
        sk.anim('in', n, 'alpha', lambda t, ti=ti: 0.0 if t < ti else 1.0)
    for r, cx in sweep:
        sk.anim('in', r, 'alpha', sweep_fn(sk.w, cx, 0.25, 0.3, 1.0, 160))
    for b, n, ph in gl:
        sk.anim('in', n, 'alpha', lambda t: 0.0)
    sk.anim('idle', 'art', 'alpha', lambda t: 1.0)
    sk.anim('idle', 'pop', 'scale', lambda t: (1 + 0.015 * math.sin(2 * math.pi * t / 1.0),) * 2)
    sign_loop(sk, 'idle', bulbs, sweep, gl, 2.0, speed=1.2, halo=(0.25, 0.2), sweep_at=0.2)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# symbols (360x360 = one tile)

SW = SH = 360
SYMBOLS = {
    # code: (glow colour, motion, extra)
    'wild': (PINK, 'slam', 'neon'),
    'seven': ((255, 70, 70), 'slam', 'rays'),
    'bell': (GOLD, 'swing', 'rays'),
    'star': (CYAN, 'spin', 'rays'),
    'cherry': ((255, 60, 80), 'hop', None),
    'lemon': ((255, 220, 60), 'jiggle', None),
    'plum': ((200, 80, 255), 'hop', None),
    'grape': ((170, 90, 255), 'jiggle', None),
    'scatter': (PINK, 'laugh', 'hearts'),
    'coin': (GOLD, 'flip', 'rays'),
}
SYM_DUR = 1.1


def sym_motion(kind, t):
    if kind == 'laugh':
        s = 1 + 0.16 * (out_cubic(clamp(t / 0.12)) if t < 0.12 else math.exp(-3 * (t - 0.12)))
        return s, s, 12 * math.exp(-2.6 * t) * math.sin(22 * t), 6 * math.sin(math.pi * clamp(t / 0.5))
    return V.sym_motion(kind, t)


def layered_symbol(sk, C, sb, meta, piv):
    """Wild / Joker scatter from their layers (layers/*.webp + json, the
    static tile is the same composite). Tile px -> units: tile is 360 = SW,
    drawn at 0.9 like every symbol."""
    k = 0.9
    rows = meta['layers']
    T = meta['size'][0]

    def place(n, parent, reg=None):
        r = rows[n]
        im = load(os.path.join(LAYERS, f'{reg or n}.webp'))
        sk.image(f'{C}_L_{reg or n}', im)
        x = (r['x'] - T / 2) * k
        y = (T / 2 - r['y']) * k - piv
        b = sk.bone(f'{C}_{n}_b', parent=parent, x=x, y=y)
        w = r['w'] * k
        if reg and reg != n:   # head variants: same box as the head
            w = r['w'] * k * im.width / load(os.path.join(LAYERS, f'{n}.webp')).width
        # hidden by default: every symbol shares one skeleton, a clip only
        # turns its own layers on
        sk.hidden_slot(f'{C}_L_{reg or n}', b, f'{C}_L_{reg or n}', w=w)
        return b

    if C == 'wild':
        bw = place('wild_w', sb)
        bt = place('wild_word', sb)
        D = SYM_DUR
        flick = lambda t: (1.0 if int(t / 0.035) % 2 else 0.25) if t < 0.22 else 1.0
        sk.anim(C, 'wild_L_wild_w', 'alpha', flick)
        sk.anim(C, bw, 'scale', lambda t: (seg(t, 0.05, 0.3, 1.0, 1.22, out_back) if t < 0.3 else seg(t, 0.3, 0.6, 1.22, 1.0),) * 2)
        sk.anim(C, bw, 'rotate', lambda t: spring(t, 0.3, 6, 18, 6))
        sk.anim(C, 'wild_L_wild_word', 'alpha', lambda t: 0.3 if t < 0.35 else ((1.0 if int(t / 0.04) % 2 else 0.3) if t < 0.55 else 1.0))
        sk.anim(C, bt, 'scale', lambda t: (seg(t, 0.4, 0.62, 0.8, 1.0, out_back) if t > 0.4 else 0.8,) * 2)
        return
    # scatter
    ring = place('ring', sb)
    head = place('head', sb)
    hv = {}
    for v in ('head_laugh', 'head_blink'):
        r = rows['head']
        im = load(os.path.join(LAYERS, f'{v}.webp'))
        base = load(os.path.join(LAYERS, 'head.webp'))
        sk.image(f'{C}_L_{v}', im)
        sk.hidden_slot(f'{C}_L_{v}', head, f'{C}_L_{v}', w=r['w'] * k * im.width / base.width)
        hv[v] = f'{C}_L_{v}'
    bells = [place(f'sbell{i}', head) for i in (1, 2, 3)]

    def clip(name, laugh_from, laugh_to, blink_at=None, ring_spin=180):
        D = sk.durs[name]
        sk.anim(name, 'scatter_L_head', 'alpha', lambda t: 0.0 if laugh_from <= t < laugh_to or (blink_at and blink_at <= t < blink_at + 0.14) else 1.0)
        sk.anim(name, hv['head_laugh'], 'alpha', lambda t: 1.0 if laugh_from <= t < laugh_to else 0.0)
        sk.anim(name, hv['head_blink'], 'alpha', lambda t: 1.0 if blink_at and blink_at <= t < blink_at + 0.14 else 0.0)
        sk.anim(name, 'scatter_L_ring', 'alpha', lambda t: 1.0)
        sk.anim(name, ring, 'rotate', lambda t: -ring_spin * out_cubic(clamp(t / D)))
        sk.anim(name, ring, 'scale', lambda t: (1 + 0.08 * ease_hump(t, 0.0, 0.5),) * 2)
        sk.anim(name, head, 'rotate', lambda t: 7 * math.sin(26 * t) * math.exp(-3 * t) if laugh_from <= t < laugh_to else 0)
        sk.anim(name, head, 'translate', lambda t: ((rows['head']['x'] - 180) * 0.9, (180 - rows['head']['y']) * 0.9 + 10 * abs(math.sin(13 * t)) * math.exp(-2 * t) * (1 if laugh_from <= t < laugh_to else 0)))
        for i, b in enumerate(bells):
            sk.anim(name, f'scatter_L_sbell{i + 1}', 'alpha', lambda t: 1.0)
            sk.anim(name, b, 'rotate', lambda t, i=i: 30 * math.sin(2 * math.pi * (t / 0.28 + i * 0.3)) * math.exp(-2.2 * t))

    clip('scatter', 0.08, 0.95, ring_spin=200)
    if 'scatter_land' in sk.durs:
        clip('scatter_land', 9, 9, blink_at=0.35, ring_spin=90)


def build_symbols():
    clips = {code: SYM_DUR for code in SYMBOLS}
    if layer_json('scatter'):
        clips['scatter_land'] = 0.9
    sk = NFx('symbols', SW, SH, 1.0, clips)
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.5
    sk.image('rays', rays(512, n=16))
    sk.res_of['rays'] = 0.6
    sk.image('ring', V.ring(256))
    sk.image('spark', V.star4(128))
    sk.image('dot', V.glow_dot(64, core=0.3, col=(255, 240, 255)))
    sk.image('heart', load(os.path.join(FXS, 'heart.webp')))
    sk.image('confetti', load(os.path.join(FXS, 'confetti.webp')))
    rnd = random.Random(7)
    for code, (col, kind, extra) in SYMBOLS.items():
        im = load(os.path.join(SYM, f'{code}.webp'))
        hexcol = hexc(col)
        sk.image(code, im)
        sk.res_of[code] = 1.0
        flash = Image.new('RGBA', im.size, (255, 255, 255, 0))
        flash.putalpha(im.getchannel('A'))
        sk.image(f'{code}_flash', flash)
        sk.res_of[f'{code}_flash'] = 0.35
        C = code
        fxb = sk.bone(f'{C}_fx')
        sk.hidden_slot(f'{C}_halo', fxb, 'halo', hexcol, w=SW * 1.25, blend='additive')
        if extra in ('rays', 'neon', 'hearts'):
            sk.hidden_slot(f'{C}_rays', fxb, 'rays', hexcol, w=SW * 1.7, blend='additive')
        rb = sk.bone(f'{C}_rb')
        sk.hidden_slot(f'{C}_ring', rb, 'ring', hexcol, w=SW * 0.9, blend='additive')
        piv = SH * 0.36 if kind == 'swing' else 0
        sb = sk.bone(f'{C}_sym', y=piv)
        meta = layer_json(code) if code in ('wild', 'scatter') else None
        if meta:
            layered_symbol(sk, C, sb, meta, piv)
        else:
            sk.hidden_slot(f'{C}_img', sb, code, w=SW * 0.9, y=-piv)
        hl = V.highlight(im, gamma=1.2, gain=1.5)
        sweep = []
        kpx = SW * 0.9 / im.width
        # layered symbols animate their own layers: a sweep / flash cut from
        # the flat tile would ghost the static face over the laughing one
        for i, (part, x0, x1) in enumerate([] if meta else V.strips(hl, 12)):
            r = f'{C}_sw{i}'
            sk.image(r, part)
            sk.res_of[r] = 0.4
            sk.hidden_slot(r, sb, r, w=(x1 - x0) * kpx, x=((x0 + x1) / 2 - im.width / 2) * kpx, y=-piv, blend='additive')
            sweep.append((r, (x0 + x1) / 2 * kpx))
        sk.hidden_slot(f'{C}_flash', sb, f'{C}_flash', w=SW * 0.9, y=-piv, blend='additive')
        parts = []
        nsp = 9 if extra in ('neon', 'hearts', 'rays') else 6
        for i in range(nsp):
            a = 2 * math.pi * i / nsp + rnd.uniform(-0.3, 0.3)
            b = sk.bone(f'{C}_sp{i}')
            reg = 'heart' if extra == 'hearts' and i % 2 == 0 else ('spark' if i % 2 == 0 else 'dot')
            if code == 'coin' and i % 3 == 0:
                reg = 'confetti'
            sk.hidden_slot(f'{C}_sp{i}', b, reg, 'ffffff', w=rnd.uniform(26, 46), blend='additive')
            parts.append((b, f'{C}_sp{i}', a, rnd.uniform(0.75, 1.1), rnd.uniform(0, 0.08)))

        W = SW * 0.9
        if not meta:
            sk.anim(C, f'{C}_img', 'alpha', lambda t: 1.0)
        sk.anim(C, sb, 'scale', lambda t, kind=kind: sym_motion(kind, t)[:2])
        sk.anim(C, sb, 'rotate', lambda t, kind=kind: sym_motion(kind, t)[2])
        sk.anim(C, sb, 'translate', lambda t, kind=kind, piv=piv: (0, piv + sym_motion(kind, t)[3]))
        sk.anim(C, f'{C}_flash', 'alpha', (lambda t: 0.0) if meta else (lambda t: seg(t, 0, 0.06, 0, 0.4) if t < 0.06 else 0.4 * math.exp(-10 * (t - 0.06))))
        for r, cx in sweep:
            sk.anim(C, r, 'alpha', lambda t, cx=cx: 0.0 if not 0.12 <= t <= 0.62 else
                    0.45 * math.exp(-((cx - lerp(-60, W + 60, in_out_sine((t - 0.12) / 0.5))) / 55) ** 2))
        big = 1.2 if kind in ('slam', 'laugh', 'flip') else 1.0
        sk.anim(C, f'{C}_halo', 'alpha', lambda t, big=big: seg(t, 0, 0.1, 0, 0.75 * big) if t < 0.1 else seg(t, 0.1, SYM_DUR, 0.75 * big, 0, in_out_sine))
        sk.anim(C, fxb, 'scale', lambda t: (seg(t, 0, 0.2, 0.5, 1.1, out_back) if t < 0.2 else seg(t, 0.2, SYM_DUR, 1.1, 0.9),) * 2)
        if extra in ('rays', 'neon', 'hearts'):
            sk.anim(C, f'{C}_rays', 'alpha', lambda t, big=big: seg(t, 0, 0.12, 0, 0.55 * big) if t < 0.12 else seg(t, 0.12, SYM_DUR, 0.55 * big, 0, in_out_sine))
        sk.anim(C, fxb, 'rotate', lambda t: -45 * t / SYM_DUR)
        t0 = 0.18 if kind == 'slam' else 0.04
        sk.anim(C, f'{C}_ring', 'alpha', lambda t, t0=t0: 0.0 if t < t0 else seg(t, t0, t0 + 0.45, 1, 0))
        sk.anim(C, rb, 'scale', lambda t, t0=t0, big=big: (seg(t, t0, t0 + 0.45, 0.3, 1.7 * big),) * 2)
        for b, sl, a, dist, delay in parts:
            def sp_pos(t, a=a, dist=dist, delay=delay):
                u = clamp((t - 0.05 - delay) / 0.7)
                d = SH * 0.3 + SH * 0.4 * dist * out_cubic(u)
                spin = a + 1.1 * u
                return (math.cos(spin) * d, math.sin(spin) * d)
            sk.anim(C, b, 'translate', sp_pos)
            sk.anim(C, sl, 'alpha', lambda t, delay=delay: 0.0 if t < 0.05 + delay else seg(t, 0.05 + delay, 0.85 + delay, 1, 0, V.in_cubic))
            sk.anim(C, b, 'scale', lambda t, delay=delay: (0.4 + 0.9 * pulse(t - delay, 0.35, 0.0, 2),) * 2)
            sk.anim(C, b, 'rotate', lambda t: 160 * t)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# win lines (reel window units)

RW, RH = 560, 550
COL_X = [(c + 0.5) * RW / 3 - RW / 2 for c in range(3)]
ROW_Y = [RH / 2 - (r + 0.5) * RH / 3 for r in range(3)]
CELL_W, CELL_H = RW / 3, RH / 3
PAYLINES = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]]
LINE_COLS = ['ff3cac', '2ce8ff', 'ffd75a', 'b77bff', '5dffb0']


def build_winlines():
    IN, LOOP = 0.6, 1.2
    clips = {}
    for n in range(1, 6):
        clips[f'line{n}_in'] = IN
        clips[f'line{n}_loop'] = LOOP
    sk = NFx('winlines', RW, RH, 1.0, clips)
    sk.image('bglow', V.hband(512, 128, sigma=0.28, taper=0.04))
    sk.res_of['bglow'] = 0.5
    sk.image('bcore', V.hband(512, 32, sigma=0.2, taper=0.02))
    sk.res_of['bcore'] = 0.5
    sk.image('head', V.glow_dot(256, core=0.22, col=(255, 255, 255)))
    sk.image('comet', V.edge_fade(spark(256, 40), 0.08, 0.2))
    sk.image('ring', V.ring(256))
    sk.image('flare', V.star4(256, thin=0.025))
    fw, fh = int(CELL_W * 0.92), int(CELL_H * 0.92)
    cfr, _ = V.rect_line(fw, fh, 5, 8, r=18)
    sk.image('cframe', cfr)
    sk.image('cglow', soft_glow(256))
    sk.res_of['cglow'] = 0.4

    for n, rows in enumerate(PAYLINES, start=1):
        col = LINE_COLS[n - 1]
        pts = [(COL_X[c], ROW_Y[r]) for c, r in enumerate(rows)]
        (x0, y0), (x2, y2) = pts[0], pts[2]
        ang = math.atan2(y2 - y0, x2 - x0)
        ux, uy = math.cos(ang), math.sin(ang)
        ext = CELL_W * 0.48
        sx, sy = x0 - ux * ext, y0 - uy * ext
        ex, ey = x2 + ux * ext, y2 + uy * ext
        L = math.hypot(ex - sx, ey - sy)
        cell_u = [math.hypot(px - sx, py - sy) / L for px, py in pts]
        P = f'L{n}'
        beam = sk.bone(f'{P}beam', x=sx, y=sy, rot=math.degrees(ang))
        sk.hidden_slot(f'{P}glow', beam, 'bglow', col, w=L, h=90, x=L / 2, blend='additive')
        sk.hidden_slot(f'{P}core', beam, 'bcore', w=L, h=14, x=L / 2, blend='additive')
        cells = []
        for ci, (px, py) in enumerate(pts):
            Cn = f'{P}c{ci}'
            cb = sk.bone(Cn, x=px, y=py)
            sk.hidden_slot(f'{Cn}glow', cb, 'cglow', col, w=CELL_W * 1.15, h=CELL_H * 1.15, blend='additive')
            fb = sk.bone(f'{Cn}f', parent=cb)
            sk.hidden_slot(f'{Cn}frame', fb, 'cframe', col, w=cfr.width, blend='additive')
            rbn = sk.bone(f'{Cn}r', parent=cb)
            sk.hidden_slot(f'{Cn}ring', rbn, 'ring', col, w=CELL_H * 1.05, blend='additive')
            flb = sk.bone(f'{Cn}fl', parent=cb)
            sk.hidden_slot(f'{Cn}flare', flb, 'flare', w=CELL_H * 1.0, blend='additive')
            cells.append((Cn, fb, rbn, flb))
        hb = sk.bone(f'{P}head', x=sx, y=sy)
        sk.hidden_slot(f'{P}head', hb, 'head', w=130, blend='additive')
        comets = []
        for k in range(2):
            cbn = sk.bone(f'{P}comet{k}', x=sx, y=sy, rot=math.degrees(ang))
            sk.hidden_slot(f'{P}comet{k}', cbn, 'comet', w=150, h=30, blend='additive')
            comets.append(cbn)
        INN, LP = f'line{n}_in', f'line{n}_loop'
        DRAW = 0.3

        def tip(t):
            return out_cubic(clamp(t / DRAW)) if t < DRAW else 1.0

        def at(u):
            lo, hi = 0.0, DRAW
            for _ in range(30):
                mid = (lo + hi) / 2
                if tip(mid) < u:
                    lo = mid
                else:
                    hi = mid
            return hi

        sk.anim(INN, beam, 'scale', lambda t: (max(0.001, tip(t)), 1.2 - 0.2 * clamp(t / 0.5)))
        sk.anim(LP, beam, 'scale', lambda t: (1.0, 1 + 0.15 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2))
        sk.anim(INN, f'{P}glow', 'alpha', lambda t: seg(t, 0, 0.1, 0, 1) if t < 0.35 else seg(t, 0.35, IN, 1, 0.75))
        sk.anim(LP, f'{P}glow', 'alpha', lambda t: 0.75 + 0.2 * (1 - math.cos(2 * math.pi * t / 0.6)) / 2)
        sk.anim(INN, f'{P}core', 'alpha', lambda t: seg(t, 0, 0.08, 0, 1))
        sk.anim(LP, f'{P}core', 'alpha', lambda t: 0.85 + 0.15 * math.cos(2 * math.pi * t / 0.3))
        sk.anim(INN, hb, 'translate', lambda t: (sx + (ex - sx) * tip(t), sy + (ey - sy) * tip(t)))
        sk.anim(INN, f'{P}head', 'alpha', lambda t: seg(t, 0, 0.05, 0, 1) if t < DRAW else seg(t, DRAW, DRAW + 0.2, 1, 0))
        sk.anim(LP, hb, 'translate', lambda t: (ex, ey))
        sk.anim(LP, f'{P}head', 'alpha', lambda t: 0.0)
        for k, cbn in enumerate(comets):
            def cpos(t, k=k):
                p = frac(t / 0.6 + k * 0.5)
                return (sx + (ex - sx) * p, sy + (ey - sy) * p)

            def calpha(t, k=k):
                p = frac(t / 0.6 + k * 0.5)
                return clamp(min(p, 1 - p) / 0.12)
            sk.anim(INN, cbn, 'translate', lambda t: (sx, sy))
            sk.anim(INN, f'{P}comet{k}', 'alpha', lambda t: 0.0)
            sk.anim(LP, cbn, 'translate', cpos)
            sk.anim(LP, f'{P}comet{k}', 'alpha', calpha)
        for ci, (Cn, fb, rbn, flb) in enumerate(cells):
            tk = at(cell_u[ci])
            sk.anim(INN, f'{Cn}glow', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.1, 0, 0.7) if t < tk + 0.2 else seg(t, tk + 0.2, IN, 0.7, 0.3))
            sk.anim(LP, f'{Cn}glow', 'alpha', lambda t: 0.3 + 0.15 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2)
            sk.anim(INN, f'{Cn}frame', 'alpha', lambda t, tk=tk: seg(t, tk, tk + 0.12, 0, 1) if t < tk + 0.12 else seg(t, tk + 0.12, IN, 1, 0.9))
            sk.anim(LP, f'{Cn}frame', 'alpha', lambda t: 0.75 + 0.25 * math.cos(2 * math.pi * t / 0.6))
            sk.anim(INN, fb, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.3, 1.15, 1.0),) * 2)
            sk.anim(LP, fb, 'scale', lambda t: (1 + 0.02 * (1 + math.cos(2 * math.pi * t / 0.6)) / 2,) * 2)
            sk.anim(INN, f'{Cn}ring', 'alpha', lambda t, tk=tk: 0.0 if t < tk else seg(t, tk, tk + 0.4, 1, 0))
            sk.anim(INN, rbn, 'scale', lambda t, tk=tk: (seg(t, tk, tk + 0.4, 0.25, 1.5),) * 2)
            sk.anim(LP, f'{Cn}ring', 'alpha', lambda t: seg(t % 0.6, 0, 0.6, 0.45, 0, V.lin))
            sk.anim(LP, rbn, 'scale', lambda t: (seg(t % 0.6, 0, 0.6, 0.5, 1.35),) * 2)
            sk.anim(INN, f'{Cn}flare', 'alpha', lambda t, tk=tk: 0.0 if t < tk else (seg(t, tk, tk + 0.05, 0, 1) if t < tk + 0.15 else seg(t, tk + 0.15, IN, 1, 0.45)))
            sk.anim(INN, flb, 'scale', lambda t, tk=tk: (0.01 if t < tk else (seg(t, tk, tk + 0.18, 0.1, 1.4, out_back) if t < tk + 0.18 else seg(t, tk + 0.18, IN, 1.4, 0.7)),) * 2)
            sk.anim(LP, f'{Cn}flare', 'alpha', lambda t: 0.45 + 0.25 * math.cos(2 * math.pi * t / 0.6))
            sk.anim(LP, flb, 'scale', lambda t: (0.7 + 0.1 * math.cos(2 * math.pi * t / 0.6),) * 2)
            sk.anim(LP, flb, 'rotate', lambda t: -90 * t / LOOP)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# background ambience (bg image px)

def build_bg(name):
    src = {'bg_desk': 'bg_base.jpg', 'bg_mob': 'bg_base_mob.jpg'}[name]
    im = Image.open(os.path.join(IMG, src))
    W, H = im.size
    sk = NFx(name, W, H, 0.5, {'idle': 8.0, 'bonus': 4.0})
    rnd = random.Random(5 if name == 'bg_desk' else 9)
    for nm, col in (('bp', PINK), ('bc', CYAN), ('bg', GOLD)):
        sk.image(nm, V.tint(soft_glow(128), col))
    bok = []
    for i in range(22):
        b = sk.bone(f'k{i}')
        reg = rnd.choice(['bp', 'bc', 'bg'])
        sk.hidden_slot(f'k{i}', b, reg, w=rnd.uniform(40, 120) * W / 1672, blend='additive')
        bok.append((b, f'k{i}', rnd.uniform(0, W), rnd.uniform(H * 0.1, H * 0.95), rnd.uniform(-30, 30), rnd.uniform(-40, -10), rnd.uniform(0, 1)))
    # slow light passes (wide soft bands)
    sk.image('band', V.hband(512, 256, sigma=0.35, taper=0.3))
    sk.res_of['band'] = 0.3
    pb = sk.bone('pass', rot=-20)
    sk.hidden_slot('pass', pb, 'band', 'ff9de0', w=W * 0.5, h=H * 1.6, blend='additive')
    # searchlights for the bonus (free spins)
    sk.image('beam', V.hband(1024, 128, sigma=0.3, taper=0.15).rotate(90, expand=True))
    sk.res_of['beam'] = 0.5
    beams = []
    for i, (x, col, ph) in enumerate(((0.12, 'ff3cac', 0.0), (0.88, '2ce8ff', 0.5), (0.3, '2ce8ff', 0.25), (0.7, 'ff3cac', 0.75))):
        b = sk.bone(f'beam{i}', x=sk.xy(W * x, H * 1.02)[0], y=sk.xy(0, H * 1.02)[1])
        sk.hidden_slot(f'beam{i}', b, 'beam', col, w=W * 0.07, h=H * 1.5, y=H * 0.75, blend='additive')
        beams.append((b, f'beam{i}', ph, 1 if x < 0.5 else -1))
    sk.image('conf', load(os.path.join(FXS, 'confetti.webp')))
    confs = []
    for i in range(18):
        b = sk.bone(f'cf{i}')
        sk.hidden_slot(f'cf{i}', b, 'conf', w=rnd.uniform(14, 26) * W / 1672, blend='additive')
        confs.append((b, f'cf{i}', rnd.uniform(0, W), rnd.uniform(0, 1), rnd.uniform(-60, 60)))

    for clip, dur in (('idle', 8.0), ('bonus', 4.0)):
        for b, n, x0, y0, dx, dy, ph in bok:
            def pos(t, x0=x0, y0=y0, dx=dx, dy=dy, ph=ph, dur=dur):
                u = frac(t / dur + ph)
                return sk.xy(x0 + dx * math.sin(2 * math.pi * u), y0 + dy * 4 * math.sin(2 * math.pi * u))
            sk.anim(clip, b, 'translate', pos)
            sk.anim(clip, n, 'alpha', lambda t, ph=ph, dur=dur: 0.15 + 0.3 * (1 + math.sin(2 * math.pi * (t / dur + ph))) / 2)
        sk.anim(clip, pb, 'translate', lambda t, dur=dur: (lerp(-W * 0.9, W * 0.9, frac(t / dur)), 0))
        sk.anim(clip, 'pass', 'alpha', lambda t, dur=dur: 0.10 * math.sin(math.pi * frac(t / dur)))
        on = clip == 'bonus'
        for b, n, ph, side in beams:
            sk.anim(clip, n, 'alpha', lambda t, on=on: 0.35 if on else 0.0)
            sk.anim(clip, b, 'rotate', lambda t, ph=ph, side=side, dur=dur: side * (18 + 16 * math.sin(2 * math.pi * (t / dur + ph))))
        for b, n, x0, ph, dx in confs:
            def cpos(t, x0=x0, ph=ph, dx=dx, dur=dur):
                u = frac(t / dur + ph)
                return sk.xy(x0 + dx * math.sin(6 * u), lerp(-40, H + 40, u))
            sk.anim(clip, b, 'translate', cpos)
            sk.anim(clip, b, 'rotate', lambda t: 360 * t)
            sk.anim(clip, n, 'alpha', lambda t, on=on: 0.8 if on else 0.0)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# mascot: a real cut-out rig from the ChatGPT parts sheet (img/../rig/*.webp,
# cut by neon_joker_spins_build.py rig()). Units = sheet px; the skeleton box
# (RIG_W x RIG_H) is what fx.js anchors to the #mascot element.

RIG = os.path.join(ROOT, 'rig')
RIG_W, RIG_H = 760, 1520
# part: pivot (part px, y down) — the joint the part rotates around
PIV = {
    'head': (205, 300), 'torso': (150, 380),
    'arm_l_up': (105, 52), 'arm_l_low': (55, 245),
    'arm_r_up': (82, 50), 'arm_r_low': (55, 250),
    # boots swapped on load (sheet drew them toe-in): left shin = the
    # toe-left boot, right shin = the toe-right one
    'leg_l_up': (85, 40), 'leg_l_low': (122, 22),
    'leg_r_up': (80, 36), 'leg_r_low': (75, 22),
    'bell_a': (61, 12), 'bell_b': (61, 12), 'bell_c': (61, 12),
}
# child joint positions in the PARENT part's px
JOINT = {
    ('torso', 'head'): (140, 18),
    ('torso', 'arm_l_up'): (52, 104), ('torso', 'arm_r_up'): (246, 108),
    ('arm_l_up', 'arm_l_low'): (118, 330), ('arm_r_up', 'arm_r_low'): (88, 250),
    ('torso', 'leg_l_up'): (100, 380), ('torso', 'leg_r_up'): (200, 380),
    ('leg_l_up', 'leg_l_low'): (62, 330), ('leg_r_up', 'leg_r_low'): (66, 330),
    ('head', 'bell_a'): (24, 222), ('head', 'bell_b'): (118, 30), ('head', 'bell_c'): (440, 232),
}
# rest pose (degrees, CCW positive, 0 = as drawn)
POSE = {
    # arms are straight segments hanging down at 0: left forearm folds up to
    # the chest for the snap, right forearm lifts the card out to the side
    'torso': 0, 'head': 3, 'arm_l_up': -18, 'arm_l_low': 168, 'arm_r_up': 22, 'arm_r_low': 120,
    'leg_l_up': -4, 'leg_l_low': 2, 'leg_r_up': 4, 'leg_r_low': -2,
    'bell_a': -20, 'bell_b': 0, 'bell_c': 20,
}
ARM_K = 0.52    # the straight-arm sheet was drawn ~1.9x the body sheet
HAND_K = 0.46
# expressions: neutral is the base head, the rest replace it per clip
FACES = ['neutral', 'blink', 'antic', 'joy', 'laugh', 'sad']
PART_SCALE = {'bell_a': 0.48, 'bell_b': 0.48, 'bell_c': 0.48,
              'arm_l_up': ARM_K, 'arm_l_low': ARM_K, 'arm_r_up': ARM_K, 'arm_r_low': ARM_K,
              'leg_l_up': 0.9, 'leg_l_low': 0.9, 'leg_r_up': 0.9, 'leg_r_low': 0.9}
# Depth order for a 3/4 view facing screen-right: the screen-LEFT side is
# the near one. Far leg, then near leg (both under the coat tails); the far
# (card) arm entirely behind the torso; head + bells; the near (snapping)
# arm last — its shoulder cap over the jacket puff, the hand in front of the
# face when it comes up to the chin.
# Boots BEHIND their own thigh: the leg goes INTO the boot, so the thigh's
# rounded end has to cover the boot's dark open cuff (drawn the other way
# round the empty boot mouth showed under every knee).
DRAW = ['leg_r_low', 'leg_r_up', 'leg_l_low', 'leg_l_up',
        'arm_r_up', 'arm_r_low', 'HANDS_R', 'torso',
        'head', 'bell_a', 'bell_b', 'bell_c',
        'arm_l_up', 'arm_l_low', 'HANDS_L']
# hand variants per side: (image, wrist end, extra rotation so the fingers
# continue the forearm). snap/card were drawn wrist-down, open/fist wrist-up.
HANDS = {
    'l': [('snap', 'hand_snap', 'bottom'), ('open', 'hand_open', 'top'), ('fist', 'hand_fist', 'top')],
    'r': [('card', 'hand_card', 'bottom'), ('open', 'hand_open', 'top')],
}


def ease_hump(t, t0, t1):
    """0 -> 1 -> 0 over [t0, t1], smooth."""
    if not t0 < t < t1:
        return 0.0
    return math.sin(math.pi * (t - t0) / (t1 - t0)) ** 2


def spring(t, t0, amp, freq=11, damp=5):
    u = t - t0
    return 0.0 if u < 0 else amp * math.exp(-damp * u) * math.sin(freq * u)


def build_mascot():
    SWAP = {'leg_l_low': 'leg_r_low', 'leg_r_low': 'leg_l_low',
            'arm_l_up': 'arm2_l_up', 'arm_l_low': 'arm2_l_low', 'arm_r_up': 'arm2_r_up', 'arm_r_low': 'arm2_r_low'}
    parts = {n: load(os.path.join(RIG, f'{SWAP.get(n, n)}.webp')) for n in PIV}

    def centre_at(im, fy):
        a = im.getchannel('A')
        y = int(im.height * fy)
        xs = [x for x in range(im.width) if a.getpixel((x, y)) > 128]
        return ((xs[0] + xs[-1]) / 2 if xs else im.width / 2), y

    # straight segments: pivots from the alpha — shoulder-cap centre, elbow /
    # wrist at the far end
    for side in ('l', 'r'):
        up, low = parts[f'arm_{side}_up'], parts[f'arm_{side}_low']
        PIV[f'arm_{side}_up'] = centre_at(up, 0.13)
        JOINT[(f'arm_{side}_up', f'arm_{side}_low')] = centre_at(up, 0.9)
        PIV[f'arm_{side}_low'] = centre_at(low, 0.07)
        JOINT[(f'arm_{side}_low', f'hand_{side}')] = centre_at(low, 0.93)
    sk = NFx('mascot', RIG_W, RIG_H, 1.0, {'idle': 6.0, 'cheer': 1.6, 'laugh': 2.0, 'bow': 2.2,
                                            'win': 1.3, 'near_win': 2.4, 'near_miss': 1.6})
    ground = -RIG_H / 2 + 24
    # hip line height above the ground: shin (pivot -> sole) + thigh (pivot -> knee)
    kl = PART_SCALE.get('leg_l_low', 1.0)
    shin = (parts['leg_l_low'].height - PIV['leg_l_low'][1]) * kl
    thigh = (JOINT[('leg_l_up', 'leg_l_low')][1] - PIV['leg_l_up'][1]) * PART_SCALE.get('leg_l_up', 1.0)
    hip_y = ground + shin + thigh - 6

    # ground shadow
    sh = V.tint(soft_glow(256), (0, 0, 0))
    sk.image('shadow', sh)
    sk.res_of['shadow'] = 0.3
    sk.slot('shadow', sk.bone('shadow', x=0, y=ground + 4), 'shadow', w=420, h=70)

    parent = {'torso': 'hip', 'head': 'torso', 'arm_l_up': 'torso', 'arm_r_up': 'torso',
              'arm_l_low': 'arm_l_up', 'arm_r_low': 'arm_r_up', 'leg_l_up': 'hip', 'leg_r_up': 'hip',
              'leg_l_low': 'leg_l_up', 'leg_r_low': 'leg_r_up', 'bell_a': 'head', 'bell_b': 'head', 'bell_c': 'head'}
    sk.bone('hip', x=0, y=hip_y)
    pos = {}

    def joint_xy(par, child):
        if par == 'hip':
            jx, jy = JOINT[('torso', child)]
            px, py = PIV['torso']
        else:
            jx, jy = JOINT[(par, child)]
            px, py = PIV[par]
        k = PART_SCALE.get('torso' if par == 'hip' else par, 1.0)
        return (jx - px) * k, -(jy - py) * k

    order = ['torso', 'leg_l_up', 'leg_r_up', 'leg_l_low', 'leg_r_low', 'head', 'arm_l_up', 'arm_r_up',
             'arm_l_low', 'arm_r_low', 'bell_a', 'bell_b', 'bell_c']
    for n in order:
        par = parent[n]
        x, y = (0, 0) if n == 'torso' else joint_xy(par, n)
        pos[n] = (x, y)
        sk.bone(n, parent=par, x=x, y=y, rot=POSE[n])
    hand_slots = {'l': [], 'r': []}
    face_slots = []
    for side in ('l', 'r'):
        fx_, fy_ = JOINT[(f'arm_{side}_low', f'hand_{side}')]
        px_, py_ = PIV[f'arm_{side}_low']
        sk.bone(f'hand_{side}', parent=f'arm_{side}_low', x=(fx_ - px_) * ARM_K, y=-(fy_ - py_) * ARM_K)
    for n in DRAW:
        if n.startswith('HANDS_'):
            side = n[-1].lower()
            for key, img, wrist in HANDS[side]:
                im = load(os.path.join(RIG, f'{img}.webp'))
                if wrist == 'bottom':
                    # drawn wrist-down: turn it so the fingers continue past
                    # the wrist like the others (baked, not an attachment
                    # rotation — the preview renderer ignores those)
                    im = im.rotate(180)
                reg = f'h{side}_{key}'
                sk.image(reg, im)
                wx, wy = centre_at(im, 0.08)
                sk.slot(reg, f'hand_{side}', reg, w=im.width * HAND_K,
                        x=(im.width / 2 - wx) * HAND_K, y=-(im.height / 2 - wy) * HAND_K)
                hand_slots[side].append((key, reg))
            continue
        im = parts[n]
        sk.image(n, im)
        k = PART_SCALE.get(n, 1.0)
        px, py = PIV[n]
        sk.slot(n, n, n, w=im.width * k, x=(im.width / 2 - px) * k, y=-(im.height / 2 - py) * k)
        if n == 'head':
            # face variants (rig/face_<name>.webp): same head, same framing,
            # only the expression differs; each is aligned to the base head
            # by its own bbox, so a slightly different crop doesn't jump
            for f in FACES:
                fp = os.path.join(RIG, f'face_{f}.webp')
                if not os.path.exists(fp):
                    continue
                fim = load(fp)
                fk = im.width / fim.width
                reg = f'face_{f}'
                sk.image(reg, fim)
                sk.hidden_slot(reg, n, reg, w=im.width * k, x=(im.width / 2 - px) * k,
                               y=-(fim.height * fk / 2 - py) * k)
                face_slots.append(f)

    # snap spark at the fingertip
    # the fingertips sit ~0.85 of the snap hand's length past the wrist,
    # straight along the hand bone (which points the way the forearm does)
    snap_len = load(os.path.join(RIG, 'hand_snap.webp')).height * HAND_K * 0.85
    sb = sk.bone('snap', parent='hand_l', x=0, y=-snap_len)
    sk.image('star', V.star4(256))
    sk.image('sring', V.ring(256))
    sk.image('sdot', V.glow_dot(64, core=0.3, col=(255, 230, 160)))
    sk.hidden_slot('snapstar', sb, 'star', 'ffd75a', w=170, blend='additive')
    rb = sk.bone('snapring', parent=sb)
    sk.hidden_slot('snapring', rb, 'sring', 'ff9de0', w=150, blend='additive')
    rnd = random.Random(3)
    sparks = []
    for i in range(8):
        b = sk.bone(f'ss{i}', parent=sb)
        sk.hidden_slot(f'ss{i}', b, 'sdot', w=rnd.uniform(14, 26), blend='additive')
        sparks.append((b, f'ss{i}', 2 * math.pi * i / 8 + rnd.uniform(-0.3, 0.3), rnd.uniform(50, 100)))

    def snap(clip, t0):
        sk.anim(clip, 'snapstar', 'alpha', lambda t: 0.0 if t < t0 else seg(t, t0, t0 + 0.45, 1, 0))
        sk.anim(clip, sb, 'scale', lambda t: (0.3 if t < t0 else seg(t, t0, t0 + 0.22, 0.3, 1.15, out_back),) * 2)
        sk.anim(clip, sb, 'rotate', lambda t: 0 if t < t0 else 160 * (t - t0))
        sk.anim(clip, 'snapring', 'alpha', lambda t: 0.0 if t < t0 else seg(t, t0, t0 + 0.4, 0.9, 0))
        sk.anim(clip, rb, 'scale', lambda t: (seg(t, t0, t0 + 0.4, 0.2, 1.6),) * 2)
        for b, n, a, d in sparks:
            sk.anim(clip, b, 'translate', lambda t, a=a, d=d: (0, 0) if t < t0 else (
                math.cos(a) * d * out_cubic(clamp((t - t0) / 0.5)), math.sin(a) * d * out_cubic(clamp((t - t0) / 0.5)) - 30 * clamp((t - t0) / 0.6) ** 2))
            sk.anim(clip, n, 'alpha', lambda t: 0.0 if t < t0 else seg(t, t0, t0 + 0.6, 1, 0))

    def faces(clip, pick):
        """pick: a face name or fn(t) -> name; 'neutral' = the base head."""
        if not face_slots:
            return
        # the generated neutral face replaces the base head too, so every
        # expression comes from the same drawing (no style jump on a switch)
        sk.anim(clip, 'head', 'alpha', lambda t: 0.0 if 'neutral' in face_slots else
                (1.0 if (pick(t) if callable(pick) else pick) == 'neutral' else 0.0))
        for f in face_slots:
            sk.anim(clip, f'face_{f}', 'alpha', lambda t, f=f: 1.0 if (pick(t) if callable(pick) else pick) == f else 0.0)

    def hands(clip, left, right='card'):
        """left/right: a key, or fn(t) -> key — which hand variant shows."""
        for side, want in (('l', left), ('r', right)):
            for key, reg in hand_slots[side]:
                sk.anim(clip, reg, 'alpha', lambda t, key=key, want=want: 1.0 if (want(t) if callable(want) else want) == key else 0.0)

    def put(clip, motion):
        """motion(t) -> dict: hip (dx, dy), rot offsets per bone, torso scale, shadow scale."""
        hx, hy = 0, hip_y
        sk.anim(clip, 'hip', 'translate', lambda t: (hx + motion(t).get('hip', (0, 0))[0], hy + motion(t).get('hip', (0, 0))[1]))
        sk.anim(clip, 'hip', 'rotate', lambda t: motion(t).get('hip_r', 0))
        sk.anim(clip, 'torso', 'scale', lambda t: motion(t).get('torso_s', (1, 1)))
        for n in POSE:
            sk.anim(clip, n, 'rotate', lambda t, n=n: motion(t).get(n, 0))
        for n in ('arm_l_up', 'arm_r_up'):
            x0, y0 = pos[n]
            sk.anim(clip, n, 'translate', lambda t, x0=x0, y0=y0: (x0, y0 + motion(t).get('shrug', 0)))
        sk.anim(clip, 'shadow', 'scale', lambda t: (1 - 0.003 * motion(t).get('hip', (0, 0))[1],) * 2)
        sk.anim(clip, 'shadow', 'alpha', lambda t: clamp(0.55 - 0.004 * motion(t).get('hip', (0, 0))[1]))

    def bells(head_rot, t, gain=1.0):
        # bells hang from the hat tips: a damped pendulum driven by how fast
        # the head turns (secondary motion), plus a tiny idle sway
        dt = 0.04
        drive = (head_rot(t) - head_rot(max(0, t - dt))) / dt
        out = {}
        for i, n in enumerate(('bell_a', 'bell_b', 'bell_c')):
            lag = 0.08 + 0.04 * i
            d2 = (head_rot(max(0, t - lag)) - head_rot(max(0, t - lag - dt))) / dt
            out[n] = gain * (-0.55 * d2 - 0.2 * drive) + 4 * math.sin(2 * math.pi * (t / 1.5 + i * 0.3))
        return out

    # idle 6s: breath, weight shift, looks at the reels, snaps, card flourish
    def head_idle(t):
        return 2.2 * math.sin(2 * math.pi * (t / 6 + 0.1)) - 7 * ease_hump(t, 1.4, 3.2) + spring(t, 4.45, 3, 14, 6)

    def idle(t):
        w = math.sin(2 * math.pi * t / 6)
        breath = math.sin(2 * math.pi * t / 3)
        m = {
            'hip': (9 * w, -3 * abs(w)),
            'hip_r': 1.2 * w,
            'torso_s': (1 - 0.004 * breath, 1 + 0.012 * breath),
            'torso': -1.2 * w + 0.6 * breath,
            'head': head_idle(t),
            'shrug': 3 * breath,
            'leg_l_up': -1.2 * w, 'leg_r_up': -1.2 * w,
            'leg_l_low': 1.5 * max(0, w), 'leg_r_low': -1.5 * max(0, -w),
            # snap: wind-up 4.1-4.38, flick at 4.4, settle
            'arm_l_low': 3 * math.sin(2 * math.pi * t / 3) - 14 * ease_hump(t, 4.0, 4.42) + spring(t, 4.42, 10, 16, 6),
            'arm_l_up': 2 * breath - 4 * ease_hump(t, 4.0, 4.42),
            'arm_r_up': 2 * math.sin(2 * math.pi * (t / 6 + 0.3)),
            'arm_r_low': 4 * math.sin(2 * math.pi * (t / 3 + 0.2)) + 10 * ease_hump(t, 0.4, 1.6),
        }
        m.update(bells(head_idle, t))
        return m
    put('idle', idle)
    hands('idle', 'snap')
    # idle: sly grin, a blink every loop, a smug look at the snap
    faces('idle', lambda t: 'blink' if 1.1 < t < 1.24 or 3.6 < t < 3.72 else ('joy' if 4.45 < t < 4.9 else 'neutral'))
    snap('idle', 4.45)

    # cheer: anticipation crouch -> jump with arms up -> land -> settle, snap
    def cheer_hip(t):
        if t < 0.22:
            return -34 * out_cubic(t / 0.22)
        if t < 0.62:
            u = (t - 0.22) / 0.4
            return -34 + (34 + 70) * math.sin(math.pi * u * 0.5) if u < 1 else 70
        if t < 0.9:
            u = (t - 0.62) / 0.28
            return 70 * (1 - u * u) - 26 * u * u
        return -26 * math.exp(-8 * (t - 0.9)) * math.cos(12 * (t - 0.9))

    def head_cheer(t):
        return 6 * ease_hump(t, 0.2, 0.9) + spring(t, 0.9, -5, 12, 5)

    def cheer(t):
        up = ease_hump(t, 0.18, 1.1)
        crouch = clamp(-cheer_hip(t) / 34)
        m = {
            'hip': (0, cheer_hip(t)),
            'torso': -3 * crouch + 2 * up,
            'torso_s': (1 + 0.02 * crouch, 1 - 0.03 * crouch + 0.03 * up),
            'head': head_cheer(t),
            # both arms thrown up, forearms straightening out of the fold
            'arm_l_up': -150 * up, 'arm_l_low': -150 * up + spring(t, 1.1, 8),
            'arm_r_up': 140 * up, 'arm_r_low': -100 * up,
            'leg_l_up': 14 * crouch - 6 * up, 'leg_l_low': -24 * crouch + 8 * up,
            'leg_r_up': -14 * crouch + 6 * up, 'leg_r_low': 24 * crouch - 8 * up,
            'shrug': 10 * up,
        }
        m.update(bells(head_cheer, t, 1.4))
        return m
    put('cheer', cheer)
    hands('cheer', lambda t: 'open' if 0.2 < t < 1.25 else 'snap')
    faces('cheer', lambda t: 'antic' if t < 0.2 else ('joy' if t < 1.3 else 'neutral'))
    snap('cheer', 0.55)

    # laugh (free spins): head thrown back, shoulders shaking, hand on hip
    def head_laugh(t):
        return 12 * ease_hump(t, 0.0, 1.8) + 4 * math.sin(26 * t) * math.exp(-1.2 * t)

    def laugh(t):
        shake = math.sin(26 * t) * math.exp(-1.0 * t)
        m = {
            'hip': (0, -6 * abs(shake)),
            'torso': 6 * ease_hump(t, 0, 1.8) + 2.5 * shake,
            'torso_s': (1, 1 + 0.015 * abs(shake)),
            'head': head_laugh(t),
            'shrug': 7 * abs(shake),
            # hand to the belly while laughing
            'arm_l_up': 14 * ease_hump(t, 0, 1.8), 'arm_l_low': -70 * ease_hump(t, 0, 1.8) + 6 * shake,
            'arm_r_up': 6 * shake, 'arm_r_low': -6 * shake,
            'leg_l_up': -2 * shake, 'leg_r_up': -2 * shake,
        }
        m.update(bells(head_laugh, t, 1.6))
        return m
    put('laugh', laugh)
    hands('laugh', lambda t: 'open' if 0.15 < t < 1.8 else 'snap')
    faces('laugh', lambda t: 'laugh' if 0.08 < t < 1.75 else 'joy')
    snap('laugh', 0.15)

    # bow (jackpot): a showman's flourish — the card arm sweeps out, he bows
    def head_bow(t):
        return -14 * ease_hump(t, 0.3, 1.9)

    def bow(t):
        b = ease_hump(t, 0.2, 1.9)
        m = {
            'hip': (-10 * b, -12 * b),
            'torso': -14 * b,
            'head': head_bow(t),
            # the card arm sweeps wide, the other hand goes to the chest
            'arm_r_up': 55 * ease_hump(t, 0.0, 1.4) - 10 * b,
            'arm_r_low': -55 * ease_hump(t, 0.0, 1.4),
            'arm_l_up': 22 * b, 'arm_l_low': -15 * b,
            'leg_l_up': 6 * b, 'leg_r_up': -8 * b, 'leg_r_low': 10 * b,
        }
        m.update(bells(head_bow, t, 1.3))
        return m
    put('bow', bow)
    hands('bow', lambda t: 'open' if 0.3 < t < 1.8 else 'snap')
    faces('bow', lambda t: 'joy' if t < 0.4 else ('blink' if t < 1.5 else 'joy'))
    snap('bow', 1.95)

    # win (a regular line win): quick pleased nod, a flick of the snapping
    # hand towards the reels, card arm pumps once
    def head_win(t):
        return 6 * ease_hump(t, 0.05, 0.35) - 4 * ease_hump(t, 0.35, 0.7) + spring(t, 0.7, 3, 12, 6)

    def win(t):
        pump = ease_hump(t, 0.1, 0.8)
        m = {
            'hip': (0, 10 * ease_hump(t, 0.1, 0.5) - 6 * ease_hump(t, 0.5, 0.9)),
            'torso': 3 * pump,
            'torso_s': (1, 1 + 0.02 * pump),
            'head': head_win(t),
            'shrug': 6 * pump,
            'arm_l_up': -20 * pump, 'arm_l_low': -22 * ease_hump(t, 0.15, 0.45) + spring(t, 0.45, 12, 15, 6),
            'arm_r_up': 30 * pump, 'arm_r_low': 25 * pump,
            'leg_l_up': -2 * pump, 'leg_r_up': 2 * pump,
        }
        m.update(bells(head_win, t, 1.3))
        return m
    put('win', win)
    hands('win', 'snap')
    faces('win', lambda t: 'joy' if t < 1.0 else 'neutral')
    snap('win', 0.45)

    # near win (loops while the last reel is anticipating): held breath, not
    # a fidget. He eases forward towards the reels and stays there: fist at
    # the chin, slow deep breathing, the head creeping closer, weight rising
    # a little onto the toes. Everything moves on one slow 2.4s cycle (the
    # loop length), no high-frequency shake — at the reels' scale any fast
    # jitter reads as twitching.
    NEAR = 2.4

    def lean_in(t):
        # first loop pass eases in from rest; the loop itself holds the lean
        return 1.0

    def head_near(t):
        breath = math.sin(2 * math.pi * t / NEAR)
        return -9 - 2.5 * breath

    def near(t):
        breath = math.sin(2 * math.pi * t / NEAR)           # slow inhale/exhale
        creep = 0.5 - 0.5 * math.cos(2 * math.pi * t / NEAR)  # 0..1..0
        m = {
            'hip': (10 + 4 * creep, -8 + 6 * creep),        # lean in, rise on the toes
            'hip_r': -2.5 - 1.0 * creep,
            'torso': -8 - 2.5 * creep,
            'torso_s': (1 - 0.006 * breath, 1 + 0.014 * breath),
            'head': head_near(t),
            'shrug': 6 + 4 * breath,
            # fist up at the chin, knuckles pressed a touch harder on the inhale
            'arm_l_up': 14 + 2 * creep, 'arm_l_low': 10 - 4 * creep,
            # card hand lowered, fingers tightening around the card
            'arm_r_up': -8 - 2 * creep, 'arm_r_low': -75 + 3 * breath,
            'leg_l_up': 2, 'leg_l_low': -2 * creep,
            'leg_r_up': -3 - 2 * creep, 'leg_r_low': 4 * creep,
        }
        m.update(bells(head_near, t, 0.35))
        return m
    put('near_win', near)
    hands('near_win', 'fist')
    faces('near_win', 'antic')

    # near miss: «эх!» — slumps, head drops, then a shrug and back to rest
    def head_miss(t):
        return -12 * ease_hump(t, 0.0, 1.1) + 6 * ease_hump(t, 0.9, 1.5)

    def miss(t):
        slump = ease_hump(t, 0.0, 1.1)
        shrug = ease_hump(t, 0.9, 1.5)
        m = {
            'hip': (0, -16 * slump),
            'torso': -5 * slump,
            'torso_s': (1 + 0.01 * slump, 1 - 0.025 * slump),
            'head': head_miss(t),
            'shrug': -10 * slump + 14 * shrug,
            # arms drop with the slump, then an open-palm shrug
            'arm_l_up': 12 * slump - 28 * shrug, 'arm_l_low': -90 * slump - 60 * shrug,
            'arm_r_up': -10 * slump + 22 * shrug, 'arm_r_low': -60 * slump + 15 * shrug,
            'leg_l_up': 4 * slump, 'leg_l_low': -6 * slump, 'leg_r_up': -4 * slump, 'leg_r_low': 6 * slump,
        }
        m.update(bells(head_miss, t, 1.1))
        return m
    put('near_miss', miss)
    hands('near_miss', lambda t: 'open' if t > 0.25 else 'fist', lambda t: 'card')
    faces('near_miss', lambda t: 'antic' if t < 0.15 else ('sad' if t < 1.35 else 'neutral'))
    sk.write()
    return sk


# --------------------------------------------------------------------------
# big win (square, behind the popup)

def build_bigwin():
    S = 1200
    sk = NFx('bigwin', S, S, 0.6, {'loop': 2.0, 'in': 0.5})
    sk.image('rays', rays(1024, n=18, col=(255, 210, 120)))
    sk.res_of['rays'] = 0.6
    sk.image('rays2', rays(1024, n=10, col=(255, 120, 220), width=0.3))
    sk.res_of['rays2'] = 0.5
    sk.image('glow', V.tint(soft_glow(256), GOLD))
    coin = load(os.path.join(ROOT, 'coins', 'blank.webp'))
    sk.image('coin', coin)
    sk.res_of['coin'] = 0.25
    sk.image('edge', load(os.path.join(FXS, 'coin_edge.webp')))
    sk.res_of['edge'] = 0.5
    sk.image('star', V.star4(128))
    sk.hidden_slot('glow', 'root', 'glow', w=S * 0.9, blend='additive')
    r1 = sk.bone('r1')
    sk.hidden_slot('rays', r1, 'rays', w=S * 1.1, blend='additive')
    r2 = sk.bone('r2')
    sk.hidden_slot('rays2', r2, 'rays2', w=S * 1.0, blend='additive')
    rnd = random.Random(12)
    coins = []
    for i in range(26):
        b = sk.bone(f'cn{i}')
        reg = 'coin' if i % 3 else 'edge'
        sk.hidden_slot(f'cn{i}', b, reg, w=rnd.uniform(46, 80), blend=None)
        coins.append((b, f'cn{i}', rnd.uniform(-S / 2, S / 2), rnd.uniform(0, 1), rnd.uniform(-80, 80), rnd.uniform(-400, 400), rnd.uniform(0.85, 1.25)))
    stars = []
    for i in range(14):
        b = sk.bone(f'st{i}', x=rnd.uniform(-S * 0.4, S * 0.4), y=rnd.uniform(-S * 0.4, S * 0.4))
        sk.hidden_slot(f'st{i}', b, 'star', w=rnd.uniform(60, 120), blend='additive')
        stars.append((b, f'st{i}', rnd.uniform(0, 1)))
    for clip in ('in', 'loop'):
        d = sk.durs[clip]
        intro = clip == 'in'
        sk.anim(clip, 'glow', 'alpha', lambda t, intro=intro: seg(t, 0, 0.3, 0, 0.6) if intro else 0.5 + 0.1 * math.sin(2 * math.pi * t / 2))
        sk.anim(clip, 'rays', 'alpha', lambda t, intro=intro: seg(t, 0, 0.4, 0, 0.55) if intro else 0.55)
        sk.anim(clip, 'rays2', 'alpha', lambda t, intro=intro: seg(t, 0, 0.4, 0, 0.35) if intro else 0.35)
        sk.anim(clip, r1, 'rotate', lambda t, intro=intro: (-10 * t if intro else -5 - 20 * t / 2))
        sk.anim(clip, r2, 'rotate', lambda t, intro=intro: (12 * t if intro else 6 + 30 * t / 2))
        sk.anim(clip, r1, 'scale', lambda t, intro=intro: (seg(t, 0, 0.5, 0.3, 1.0, out_back) if intro else 1.0,) * 2)
        for b, n, x0, ph, dx, spin, sp in coins:
            def cpos(t, x0=x0, ph=ph, dx=dx, sp=sp, intro=intro):
                if intro:
                    return (x0, S * 0.7)
                u = frac(t / 2 * sp + ph)
                return (x0 + dx * math.sin(4 * u), lerp(S * 0.6, -S * 0.6, u))
            sk.anim(clip, b, 'translate', cpos)
            sk.anim(clip, b, 'rotate', lambda t, spin=spin: spin * t)
            sk.anim(clip, b, 'scale', lambda t, ph=ph: (abs(math.cos(2 * math.pi * (t * 1.5 + ph))) * 0.8 + 0.2, 1.0))
            sk.anim(clip, n, 'alpha', lambda t, intro=intro: 0.0 if intro else 1.0)
        for b, n, ph in stars:
            sk.anim(clip, n, 'alpha', lambda t, ph=ph: pulse(t / 2, 1.0, ph, 10))
            sk.anim(clip, b, 'scale', lambda t, ph=ph: (0.2 + 0.9 * pulse(t / 2, 1.0, ph, 6),) * 2)
    sk.write()
    return sk


# --------------------------------------------------------------------------

def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
        os.makedirs(preview, exist_ok=True)
    only = [a for a in sys.argv[1:] if not a.startswith('--') and a != preview]
    builders = {
        'frame': lambda: build_frame('frame'),
        'frame_mob': lambda: build_frame('frame_mob'),
        'logo': build_logo,
        'symbols': build_symbols,
        'winlines': build_winlines,
        'bg_desk': lambda: build_bg('bg_desk'),
        'bg_mob': lambda: build_bg('bg_mob'),
        'mascot': build_mascot,
        'bigwin': build_bigwin,
        'buy': build_buy,
    }
    for tier in ('mini', 'minor', 'major', 'grand'):
        builders[f'jp_{tier}'] = lambda tier=tier: build_plate(tier)
    for key in SIGNS:
        builders[f'sign_{key}'] = lambda key=key: build_title(key)
    built = {k: f() for k, f in builders.items() if not only or k in only}
    if not preview:
        return
    for name, sk in built.items():
        for clip, dur in sk.durs.items():
            if name == 'winlines' and not clip.startswith(('line1', 'line4')):
                continue
            if name == 'symbols' and clip not in ('wild', 'scatter', 'bell', 'seven'):
                continue
            pw = 600 if sk.w >= sk.h else 360
            ph = int(pw * sk.h / sk.w)
            frames = [V.render(sk, clip, dur * k / 6, (pw, ph)) for k in range(6)]
            sheet = Image.new('RGB', (pw * 3, ph * 2))
            for k, f in enumerate(frames):
                sheet.paste(f.convert('RGB'), ((k % 3) * pw, (k // 3) * ph))
            sheet.save(os.path.join(preview, f'{name}_{clip}.jpg'), quality=80)


if __name__ == '__main__':
    main()
