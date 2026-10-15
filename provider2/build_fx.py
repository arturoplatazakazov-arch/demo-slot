"""Provider 2: the standard Spine FX pack of a game, generated in code.

    python3 provider2/build_fx.py <slug> [parts...] [--preview DIR]     (slug may be `all`)

Reuses the house pipeline (scripts/spine_screen_kit.py Skel, the Fx class and
image helpers of scripts/ice_spin_deluxe_fx.py, frame/logo/burst/shower of
scripts/gold_of_baku_fx.py). Writes front/img/<slug>/:

  fx/bg_desk, fx/bg_mob   design canvas (1932x940 / 780x1416, anchored to
                          #screen). `idle` 8s loop: back glow, light rays,
                          bokeh, twinkles and a themed particle field
                          (embers / bubbles / fireflies / petals / rain /
                          stars / steam / disco lights / candy sparkles).
  fx/frame                reel_frame.png px: halo, light sweep through the
                          painted frame, glints, comets round the window.
                          `idle` 4s, `win` 1.2s.
  fx/logo                 logo.png px: shadow, halo, rays, sweep, glints.
                          `idle` 4s, `win` 1.2s.
  fx/burst                reel-window space: coin fountain + stars. `win`.
  fx/shower               1000x1000 screen box: coin rain. `start`, `rain`.
  export/<code>/          one skeleton per reel symbol, 200x200 cell px,
                          centred on the tile: `idle` (3s seamless loop, starts
                          and ends on the static tile) and `win` (1.2s). The
                          wild also carries the whole-reel version (250x600):
                          `move` (grow), `idle_big`, `win_big`.
"""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(HERE))

from spine_screen_kit import (  # noqa: E402
    clamp, in_out_sine, lerp, out_back, out_cubic, pulse, rays, seg, soft_glow,
)
from ice_spin_deluxe_fx import (  # noqa: E402
    Fx, glow_dot, highlight, in_cubic_ease, render, ring, star4, strips, sym_motion, tint,
)
import gold_of_baku_fx as baku  # noqa: E402
from pset import DIR, GAMES, NAME  # noqa: E402

# frame/logo/burst/shower come from the Baku generator, whose atlases are
# unquantised; ours ship with the same 256-colour pass as the rest of front/img.
_baku_init = baku.BFx.__init__


def _baku_init_q(self, *a, **kw):
    _baku_init(self, *a, **kw)
    self.quantize = True


baku.BFx.__init__ = _baku_init_q

FRONT = ROOT / 'front' / 'img'
WIN_W, WIN_H = 958, 573
DESIGN = {'bg_desk': (1932, 940), 'bg_mob': (780, 1416)}


def frac(x):
    return x - math.floor(x)


class PFx(Fx):
    def __init__(self, name, w, h, res, clips, out):
        super().__init__(name, w, h, res, clips, quantize=True)
        self.out_dir = str(out)


def hex_rgb(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# --------------------------------------------------------------------------
# themed backgrounds

THEMES = {
    # particle: (motion, colours, count, size range, rays?)
    'embers':    ('rise',  [(255, 160, 60), (255, 214, 120)], 70, (12, 30), True),
    'petals':    ('fall',  [(255, 170, 200), (255, 220, 235)], 46, (16, 34), True),
    'disco':     ('drift', [(200, 110, 255), (90, 255, 140), (80, 200, 255)], 40, (18, 40), True),
    'sparkle':   ('rise',  [(255, 150, 210), (255, 230, 120), (140, 230, 255)], 60, (10, 26), True),
    'rain':      ('rain',  [(170, 200, 255)], 90, (30, 60), False),
    'steam':     ('rise',  [(255, 230, 190), (200, 240, 255)], 40, (40, 90), True),
    'fireflies': ('drift', [(190, 255, 90), (255, 230, 120)], 50, (12, 26), False),
    'night':     ('twinkle', [(170, 220, 255), (255, 240, 200)], 60, (14, 34), False),
}


def build_bg(name, g, out):
    W, H = DESIGN[name]
    P = 8.0
    spread = 1.5
    motion, cols, n, sizes, with_rays = THEMES[g['fx']]
    halo = g['halo']
    sk = PFx(name, W, H, 0.7, {'idle': P}, out)
    rnd = random.Random(name + g['slug'])
    baku.bg_common(sk, W, H, tuple(int(c * 0.8) for c in halo), P)

    if with_rays:
        sk.image('rays', rays(1024, n=14, col=tuple(min(255, c + 60) for c in halo), width=0.3))
        sk.res_of['rays'] = 0.25
        rb = sk.bone('rays', y=H * 0.62)
        sk.hidden_slot('rays', rb, 'rays', w=max(W, H) * 1.6, blend='additive')
        sk.anim('idle', rb, 'rotate', lambda t: 6 * math.sin(2 * math.pi * t / P))
        sk.anim('idle', 'rays', 'alpha', lambda t: 0.09 + 0.06 * (1 - math.cos(2 * math.pi * t / (P / 2))) / 2)

    sk.image('bokeh', tint(soft_glow(128), cols[0]))
    sk.image('bokeh2', tint(soft_glow(128), cols[-1]))
    baku.bokeh(sk, W, H, 10, rnd, P, spread)
    sk.image('twinkle', star4(128, col=tuple(min(255, c + 40) for c in cols[-1])))
    baku.twinkles(sk, W, H, 30 if motion == 'twinkle' else 18, rnd, P, None, -0.1, 0.55, spread)

    for ci, c in enumerate(cols):
        if motion == 'rain':
            from spine_screen_kit import spark
            im = tint(spark(96, 10), c)
        else:
            im = glow_dot(64, core=0.3 if motion != 'steam' else 0.05, col=c)
        sk.image(f'p{ci}', im)
    bot, top = -H * 0.7, H * 0.7
    span = top - bot
    for i in range(n):
        x0 = rnd.uniform(-0.5, 0.5) * W * spread
        k = rnd.choice((1, 1, 2))
        ph0 = rnd.random()
        sway = rnd.uniform(12, 60)
        m = rnd.choice((1, 2))
        sph = rnd.random()
        size = rnd.uniform(*sizes)
        amax = rnd.uniform(0.4, 0.9) * (0.5 if motion == 'steam' else 1)
        fl = rnd.choice((4, 8, 16))
        y_init = rnd.uniform(-0.45, 0.45) * H
        b = sk.bone(f'e{i}', x=x0, y=bot if motion in ('rise', 'fall', 'rain') else y_init)
        reg = f'p{i % len(cols)}'
        sk.hidden_slot(f'e{i}', b, reg, w=size, blend='additive')

        if motion == 'rise':
            def pos(t, x0=x0, k=k, ph0=ph0, sway=sway, m=m, sph=sph):
                p = frac(k * t / P + ph0)
                return (x0 + sway * math.sin(2 * math.pi * (m * t / P + sph)), bot + span * p)
        elif motion in ('fall', 'rain'):
            slant = 0.35 if motion == 'rain' else 0.0

            def pos(t, x0=x0, k=k, ph0=ph0, sway=sway, m=m, sph=sph, slant=slant):
                p = frac(k * t / P + ph0)
                sw = 0 if slant else sway * math.sin(2 * math.pi * (m * t / P + sph))
                return (x0 + sw - slant * span * p, top - span * p)
            if motion == 'rain':
                sk.anim('idle', b, 'rotate', lambda t: -71)
            else:
                sk.anim('idle', b, 'rotate', lambda t, sph=sph, m=m: 40 * math.sin(2 * math.pi * (m * t / P + sph)))
        else:  # drift / twinkle: wander around a home point
            ax, ay = rnd.uniform(30, 110), rnd.uniform(20, 80)

            def pos(t, x0=x0, y0=y_init, ax=ax, ay=ay, m=m, sph=sph, k=k):
                return (x0 + ax * math.sin(2 * math.pi * (k * t / P + sph)),
                        y0 + ay * math.sin(2 * math.pi * (m * t / P + sph * 0.7)))

        def al(t, k=k, ph0=ph0, amax=amax, fl=fl, sph=sph, motion=motion):
            if motion in ('drift', 'twinkle'):
                return amax * (0.25 + 0.75 * (0.5 + 0.5 * math.sin(2 * math.pi * (fl * t / P / 2 + sph))) ** 2)
            p = frac(k * t / P + ph0)
            flick = 0.75 + 0.25 * math.sin(2 * math.pi * (fl * t / P + sph))
            return amax * flick * clamp(min(p, 1 - p) / 0.12)
        sk.anim('idle', b, 'translate', pos)
        sk.anim('idle', f'e{i}', 'alpha', al)
    sk.write()
    return sk


# --------------------------------------------------------------------------
# symbols

def symbol_kind(g, code):
    if code == 'wild':
        return 'slam'
    if code == 'scatter':
        return 'swing'
    if code in g['hp']:
        return 'hop'
    return 'jiggle'


def add_symbol_layers(sk, prefix, im, w, h, col, piv, rnd, n_sparks=7):
    """Halo/rays/ring/sweep/flash/sparks around one image; returns bones."""
    hexcol = '%02x%02x%02x' % col
    fx = sk.bone(f'{prefix}_fx')
    sk.hidden_slot(f'{prefix}_halo', fx, 'halo', hexcol, w=w * 1.3, h=h * 1.3, blend='additive')
    sk.hidden_slot(f'{prefix}_rays', fx, 'rays', hexcol, w=max(w, h) * 1.9, blend='additive')
    rb = sk.bone(f'{prefix}_rb')
    sk.hidden_slot(f'{prefix}_ring', rb, 'ring', 'fff6e0', w=min(w, h) * 1.0, blend='additive')
    sb = sk.bone(f'{prefix}_sym', y=piv)
    sk.slot(f'{prefix}_img', sb, prefix, w=w, y=-piv)
    k = w / im.width
    hl = highlight(im, gamma=1.2, gain=1.5)
    sweep = []
    for i, (sim, x0, x1) in enumerate(strips(hl, 14)):
        r = f'{prefix}_sw{i}'
        sk.image(r, sim)
        sk.res_of[r] = 0.6
        sk.hidden_slot(r, sb, r, w=(x1 - x0) * k, x=((x0 + x1) / 2 - im.width / 2) * k, y=-piv, blend='additive')
        sweep.append((r, (x0 + x1) / 2 * k))
    flash = Image.new('RGBA', im.size, (255, 255, 255, 0))
    flash.putalpha(im.getchannel('A'))
    sk.image(f'{prefix}_flash', flash)
    sk.res_of[f'{prefix}_flash'] = 0.4
    sk.hidden_slot(f'{prefix}_flash', sb, f'{prefix}_flash', w=w, y=-piv, blend='additive')
    sparks = []
    for i in range(n_sparks):
        a = 2 * math.pi * i / n_sparks + rnd.uniform(-0.3, 0.3)
        b = sk.bone(f'{prefix}_sp{i}')
        sk.hidden_slot(f'{prefix}_sp{i}', b, 'spark' if i % 2 == 0 else 'dot', 'ffffff', w=rnd.uniform(30, 52), blend='additive')
        sparks.append((b, f'{prefix}_sp{i}', a, rnd.uniform(0.75, 1.1), rnd.uniform(0, 0.08)))
    return fx, rb, sb, sweep, sparks


def anim_win(sk, clip, prefix, kind, w, h, D, piv, fx, rb, sb, sweep, sparks, scale=1.0):
    sk.anim(clip, sb, 'scale', lambda t, kind=kind: tuple(scale * v for v in sym_motion(kind, t)[:2]))
    sk.anim(clip, sb, 'rotate', lambda t, kind=kind: sym_motion(kind, t)[2])
    sk.anim(clip, sb, 'translate', lambda t, kind=kind, piv=piv: (0, piv + sym_motion(kind, t)[3]))
    sk.anim(clip, f'{prefix}_flash', 'alpha', lambda t: seg(t, 0, 0.06, 0, 0.8) if t < 0.06 else 0.8 * math.exp(-11 * (t - 0.06)))
    for r, cx in sweep:
        sk.anim(clip, r, 'alpha', lambda t, cx=cx: 0.0 if not 0.12 <= t <= 0.62 else
                0.9 * math.exp(-((cx - lerp(-60, w + 60, in_out_sine((t - 0.12) / 0.5))) / 60) ** 2))
    big = 1.25 if kind == 'slam' else 1.0
    sk.anim(clip, f'{prefix}_halo', 'alpha', lambda t: seg(t, 0, 0.1, 0, 0.85 * big) if t < 0.1 else seg(t, 0.1, D, 0.85 * big, 0, in_out_sine))
    sk.anim(clip, fx, 'scale', lambda t: (seg(t, 0, 0.2, 0.5, 1.15, out_back) if t < 0.2 else seg(t, 0.2, D, 1.15, 0.9),) * 2)
    sk.anim(clip, f'{prefix}_rays', 'alpha', lambda t: seg(t, 0, 0.12, 0, 0.7 * big) if t < 0.12 else seg(t, 0.12, D, 0.7 * big, 0, in_out_sine))
    sk.anim(clip, fx, 'rotate', lambda t: -50 * t / D)
    t0 = 0.18 if kind == 'slam' else 0.04
    sk.anim(clip, f'{prefix}_ring', 'alpha', lambda t: 0.0 if t < t0 else seg(t, t0, t0 + 0.45, 1, 0))
    sk.anim(clip, rb, 'scale', lambda t: (seg(t, t0, t0 + 0.45, 0.3, 1.9 * big),) * 2)
    for b, sl, a, dist, delay in sparks:
        def sp_pos(t, a=a, dist=dist, delay=delay):
            u = clamp((t - 0.05 - delay) / 0.7)
            d = (min(w, h) * 0.35 + min(w, h) * 0.45 * dist * out_cubic(u))
            spin = a + 1.2 * u
            return (math.cos(spin) * d * 1.2, math.sin(spin) * d)
        sk.anim(clip, b, 'translate', sp_pos)
        sk.anim(clip, sl, 'alpha', lambda t, delay=delay: 0.0 if t < 0.05 + delay else seg(t, 0.05 + delay, 0.85 + delay, 1, 0, in_cubic_ease))
        sk.anim(clip, b, 'scale', lambda t, delay=delay: (0.4 + 0.9 * pulse(t - delay, 0.35, 0.0, 2),) * 2)
        sk.anim(clip, b, 'rotate', lambda t: 180 * t)


def anim_idle(sk, clip, prefix, w, D, sb, sweep, amp, fx=None, halo_amp=0.0, piv=0):
    sk.anim(clip, sb, 'scale', lambda t: (1 + amp * (1 - math.cos(2 * math.pi * t / D)) / 2,) * 2)
    sk.anim(clip, sb, 'translate', lambda t: (0, piv))
    sk.anim(clip, sb, 'rotate', lambda t: 0.0)
    for r, cx in sweep:
        sk.anim(clip, r, 'alpha', lambda t, cx=cx: 0.0 if not 0.9 <= t <= 1.7 else
                0.55 * math.exp(-((cx - lerp(-60, w + 60, in_out_sine((t - 0.9) / 0.8))) / 55) ** 2))
    if halo_amp:
        sk.anim(clip, f'{prefix}_halo', 'alpha', lambda t: halo_amp * (1 - math.cos(2 * math.pi * t / D)) / 2)
        sk.anim(clip, fx, 'scale', lambda t: (1.0,) * 2)


def build_symbol(g, code, out):
    src = FRONT / g['slug'] / 'symbols' / f'{code}.png'
    im = Image.open(src).convert('RGBA')
    kind = symbol_kind(g, code)
    special = code in ('wild', 'scatter')
    clips = {'idle': 3.0, 'win': 1.2}
    if code == 'wild':
        clips.update({'move': 0.6, 'idle_big': 3.0, 'win_big': 1.2})
    sk = PFx(code, 250 if code == 'wild' else 200, 600 if code == 'wild' else 200, 1.0, clips, out)
    sk.image('halo', soft_glow(256))
    sk.res_of['halo'] = 0.5
    sk.image('rays', rays(512, n=14))
    sk.res_of['rays'] = 0.5
    sk.image('ring', ring(256))
    sk.image('spark', star4(128))
    sk.image('dot', glow_dot(64, core=0.3, col=(255, 250, 230)))
    col = g['halo']
    rnd = random.Random(code + g['slug'])

    sk.image(code, im)
    sk.res_of[code] = 1.0
    piv = 200 * 0.3 if kind == 'swing' else 0
    layers = add_symbol_layers(sk, code, im, 200, 200, col, piv, rnd)
    fx, rb, sb, sweep, sparks = layers
    anim_idle(sk, 'idle', code, 200, 3.0, sb, sweep, 0.035 if special else 0.02,
              fx=fx, halo_amp=0.35 if special else 0.0, piv=piv)
    anim_win(sk, 'win', code, kind, 200, 200, 1.2, piv, *layers)

    if code == 'wild':
        bim = Image.open(FRONT / g['slug'] / 'symbols' / 'wild_big.png').convert('RGBA')
        sk.image('wildbig', bim)
        sk.res_of['wildbig'] = 2.0
        blayers = add_symbol_layers(sk, 'wildbig', bim, 250, 600, col, 0, rnd, n_sparks=10)
        bfx, brb, bsb, bsweep, bsparks = blayers
        # the small wild never shows on the big clips and vice versa: big slot
        # hidden in the setup pose (alpha keyed below), small one keyed off.
        for clip in ('idle', 'win'):
            sk.anim(clip, 'wildbig_img', 'alpha', lambda t: 0.0)
        for clip in ('move', 'idle_big', 'win_big'):
            sk.anim(clip, 'wild_img', 'alpha', lambda t: 0.0)
        sk.anim('move', 'wildbig_img', 'alpha', lambda t: seg(t, 0, 0.18, 0, 1))
        sk.anim('move', bsb, 'scale', lambda t: (seg(t, 0, 0.45, 0.6, 1.0, out_back), seg(t, 0, 0.45, 0.33, 1.0, out_back)))
        sk.anim('move', 'wildbig_flash', 'alpha', lambda t: 0.0 if t < 0.3 else 0.7 * math.exp(-8 * (t - 0.3)))
        sk.anim('move', 'wildbig_halo', 'alpha', lambda t: seg(t, 0.2, 0.6, 0, 0.6))
        sk.anim('idle_big', 'wildbig_img', 'alpha', lambda t: 1.0)
        anim_idle(sk, 'idle_big', 'wildbig', 250, 3.0, bsb, bsweep, 0.02, fx=bfx, halo_amp=0.45)
        sk.anim('win_big', 'wildbig_img', 'alpha', lambda t: 1.0)
        anim_win(sk, 'win_big', 'wildbig', 'stretch', 250, 600, 1.2, 0, *blayers)
    sk.write()
    return sk


# --------------------------------------------------------------------------

def build(slug, only, preview):
    g = GAMES[slug]
    gdir = FRONT / slug
    art = gdir / 'img'
    layout = json.loads((gdir / 'layout.json').read_text())
    f = layout['frame']
    cfg = {'win': (f['l'] / f['w'], f['t'] / f['h'], WIN_W / f['w'], WIN_H / f['h']),
           'halo': g['halo']}
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(art / 'reel_frame.png', tmp / 'cabinet.png')
    shutil.copy(art / 'logo.png', tmp / 'logo.png')
    fx_out = str(gdir / 'fx')
    built = {}

    def want(k):
        return not only or k in only
    if want('frame'):
        built['frame'] = baku.build_frame(cfg, str(tmp), fx_out)
    if want('logo'):
        built['logo'] = baku.build_logo(cfg, str(tmp), fx_out)
    if want('bg'):
        built['bg_desk'] = build_bg('bg_desk', g, fx_out)
        built['bg_mob'] = build_bg('bg_mob', g, fx_out)
    if want('burst'):
        built['burst'] = baku.build_burst(cfg, str(tmp), fx_out)
    if want('shower'):
        built['shower'] = baku.build_shower(fx_out)
    if want('symbols'):
        for code in g['codes']:
            built[f'sym_{code}'] = build_symbol(g, code, gdir / 'export')
    if preview:
        os.makedirs(preview, exist_ok=True)
        unders = {'frame': Image.open(art / 'reel_frame.png'), 'logo': Image.open(art / 'logo.png')}
        for name, sk in built.items():
            if name.startswith('sym_') and name not in ('sym_wild', 'sym_scatter', f"sym_{g['hp'][0]}"):
                continue
            for clip, dur in sk.durs.items():
                under = unders.get(name)
                box = (-sk.w / 2, -sk.h / 2, sk.w, sk.h)
                pw = 600
                frames = [render(sk, clip, dur * k / 6, (pw, int(pw * sk.h / sk.w)), under=under,
                                 under_box=box if under is not None else None) for k in range(6)]
                sheet = Image.new('RGB', (pw * 3, frames[0].height * 2), (40, 40, 40))
                for k, fr in enumerate(frames):
                    sheet.paste(fr.convert('RGB'), ((k % 3) * pw, (k // 3) * fr.height))
                sheet.save(os.path.join(preview, f'{slug}_{name}_{clip}.jpg'), quality=78)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = sys.argv[1:]
    preview = None
    if '--preview' in args:
        i = args.index('--preview')
        preview = args[i + 1]
        del args[i:i + 2]
    slugs = list(GAMES) if args[0] == 'all' else [args[0]]
    for slug in slugs:
        build(slug, args[1:], preview)


if __name__ == '__main__':
    main()
