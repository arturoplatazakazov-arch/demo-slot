"""Great Uniqorn — animated SCATTER symbol as a Spine 4.1 skeleton, built in code.

Inputs (designer art, kept in front/img/great-uniqorn/src/scatter/):
    exploded.webp   the burger exploded into layers on black (1254x1254)
    burger.png      the assembled burger (209x185)
    text.png        the SCATTER lettering (190x91)
The static symbol is burger x0.91 at (0,0) + text at (0,107) on a 190x198 tile;
the skeleton is authored on that tile x U units (origin = tile centre, y up),
so its setup pose is exactly the static symbol.

Clips:
    idle  2.0s loop   burger breathes, lettering + glow pulse
    land  0.6s        drop-in with squash, lettering pops
    win   2.6s        burger squashes, bursts into its layers which float
                      apart, then slam back one by one; lettering punches,
                      rays + glow + sparks behind; ends on the setup pose.

    python3 scripts/great_uniqorn_scatter_spine.py
"""

import math
import os
import random
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as nd

sys.path.insert(0, os.path.dirname(__file__))
from spine_screen_kit import (Skel, clamp, flash_of, in_cubic, lerp, out_back,  # noqa: E402
                              out_cubic, rays, seg, soft_glow, spark, trim)

ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'great-uniqorn')
SRC = os.path.join(ROOT, 'src', 'scatter')
OUT = os.path.join(ROOT, 'spine')

U = 3                     # skeleton units per tile px
TILE_W, TILE_H = 190, 198
BURGER_S = 0.91           # burger.png scale on the tile
TEXT_Y = 107              # lettering top on the tile


def X(px):
    return (px - TILE_W / 2) * U


def Y(py):
    return (TILE_H / 2 - py) * U


# --------------------------------------------------------------------------
# cut the exploded burger into layers

LAYER_NAMES = ['top_bun', 'lettuce', 'tomato', 'onion', 'cheese_bacon', 'patty', 'base']


def cut_layers():
    rgb = np.asarray(Image.open(os.path.join(SRC, 'exploded.webp')).convert('RGB')).astype(np.float32)
    mx = rgb.max(2)
    lab, n = nd.label(mx > 22)
    sizes = nd.sum(np.ones_like(mx), lab, range(1, n + 1))
    comps = [i + 1 for i in range(n) if sizes[i] > 2000]
    objs = nd.find_objects(lab)
    comps.sort(key=lambda c: objs[c - 1][0].start)
    assert len(comps) == len(LAYER_NAMES), len(comps)
    layers = {}
    for name, c in zip(LAYER_NAMES, comps):
        sl = objs[c - 1]
        y0, y1 = max(0, sl[0].start - 6), min(rgb.shape[0], sl[0].stop + 6)
        x0, x1 = max(0, sl[1].start - 6), min(rgb.shape[1], sl[1].stop + 6)
        core = nd.binary_fill_holes(lab[y0:y1, x0:x1] == c)
        near = nd.binary_dilation(core, iterations=4)
        m = mx[y0:y1, x0:x1]
        # Soft edge: colour-to-alpha against black on the rim only; the body
        # (incl. dark grill marks, filled holes) stays opaque.
        a = np.clip((m - 8) / 34, 0, 1)
        a = np.where(nd.binary_erosion(core, iterations=2), 1.0, a) * near
        col = rgb[y0:y1, x0:x1] / np.maximum(a, 1e-3)[..., None]
        col = np.clip(np.where(a[..., None] > 0, col, 0), 0, 255)
        im = Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8))
        layers[name] = (trim(im), (y0 + y1) / 2, (x0 + x1) / 2)
    return layers


# Where each layer sits in the closed stack, as the centre on the tile (px) and
# its width on the tile — tuned so the closed stack reads like burger.png.
STACK = {
    #               cx     cy    width
    'base':         (96, 124, 128),
    'patty':        (96, 112, 140),
    'cheese_bacon': (96, 103, 166),
    'onion':        (95, 89, 112),
    'tomato':       (95, 81, 126),
    'lettuce':      (97, 71, 160),
    'top_bun':      (97, 44, 132),
}
DRAW_ORDER = ['base', 'patty', 'cheese_bacon', 'onion', 'tomato', 'lettuce', 'top_bun']


class SymbolSkel(Skel):
    DUR = {'idle': 2.0, 'land': 0.6, 'win': 2.6}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.anims = {k: {'bones': {}, 'slots': {}} for k in self.DUR}

    def anim(self, which, target, prop, fn):
        keep_intro, keep_idle = self.intro, self.idle
        self.intro = self.idle = self.DUR[which]
        tmp = self.anims
        self.anims = {'intro': tmp[which], 'idle': tmp[which]}
        try:
            Skel.anim(self, 'intro', target, prop, fn)
        finally:
            self.anims = tmp
            self.intro, self.idle = keep_intro, keep_idle


def build(debug_dir=None):
    layers = cut_layers()
    burger = trim(Image.open(os.path.join(SRC, 'burger.png')).convert('RGBA'))
    burger_full = Image.open(os.path.join(SRC, 'burger.png')).convert('RGBA')
    text = Image.open(os.path.join(SRC, 'text.png')).convert('RGBA')

    if debug_dir:
        debug_stack(layers, burger_full, text, debug_dir)

    s = SymbolSkel('scatter', TILE_W * U * 2, TILE_H * U * 2, 1.0, OUT)
    s.image('burger', burger_full)
    s.image('text', text)
    s.image('text_flash', flash_of(text))
    s.image('glow', soft_glow(256))
    s.image('rays', rays(512, n=14, col=(255, 214, 120), width=0.38))
    s.image('spark', spark(96, 20))
    for name, (im, _, _) in layers.items():
        s.image(name, im)
        s.image(name + '_flash', flash_of(im))

    # ---- bones -----------------------------------------------------------
    bw, bh = burger_full.width * BURGER_S, burger_full.height * BURGER_S
    bcx, bcy = bw / 2, bh / 2          # burger centre on the tile
    pivot_y = bh * 0.86                # squash about the bun's bottom
    s.bone('fx', x=X(bcx), y=Y(bcy - 6))
    s.bone('glow', parent='fx')
    s.bone('burger', x=X(bcx), y=Y(pivot_y))
    s.bone('stack', x=X(95), y=Y(pivot_y))
    for name in DRAW_ORDER:
        cx, cy, _ = STACK[name]
        s.bone('L_' + name, parent='stack', x=(cx - 95) * U, y=(pivot_y - cy) * U)
    s.bone('text', x=X(TILE_W / 2), y=Y(TEXT_Y + text.height / 2))
    sparks = []
    rnd = random.Random(7)
    for i in range(10):
        ang = 2 * math.pi * i / 10 + rnd.uniform(-0.2, 0.2)
        sparks.append((s.bone(f'spark{i}', parent='fx', rot=math.degrees(ang)), ang, rnd.uniform(0.75, 1.15)))

    # ---- slots (draw order) ---------------------------------------------
    s.slot('rays', 'fx', 'rays', w=150 * U, blend='additive', color='ffd27aff')
    s.slot('glow', 'glow', 'glow', w=170 * U, blend='additive', color='ffb84a99')
    for b, _, _ in sparks:
        s.slot(b, b, 'spark', w=34 * U, x=34 * U, blend='additive', color='fff2c0ff')
    s.slot('burger', 'burger', 'burger', w=bw * U, y=(pivot_y - bcy) * U)
    for name in DRAW_ORDER:
        _, _, w = STACK[name]
        s.slot(name, 'L_' + name, name, w=w * U)
        s.slot(name + '_flash', 'L_' + name, name + '_flash', w=w * U, blend='additive')
    s.slot('text', 'text', 'text', w=text.width * U)
    s.slot('text_flash', 'text', 'text_flash', w=text.width * U, blend='additive')

    hidden = ['rays', 'glow'] + [b for b, _, _ in sparks] + DRAW_ORDER + \
             [n + '_flash' for n in DRAW_ORDER] + ['text_flash']

    def setup_alpha(which):
        for h in hidden:
            if h != 'glow':
                s.anim(which, h, 'alpha', lambda t: 0)

    # ---- idle (2.0s loop) --------------------------------------------------
    P = SymbolSkel.DUR['idle']
    setup_alpha('idle')
    s.anim('idle', 'glow', 'alpha', lambda t: 0.35 + 0.25 * (1 - math.cos(2 * math.pi * t / P)) / 2)
    s.anim('idle', 'burger', 'scale', lambda t: (1 + 0.018 * (1 - math.cos(2 * math.pi * t / P)) / 2,
                                                 1 + 0.03 * (1 - math.cos(2 * math.pi * t / P)) / 2))
    s.anim('idle', 'text', 'scale', lambda t: (1 + 0.025 * (1 - math.cos(2 * math.pi * (t / P - 0.18))) / 2,) * 2)
    s.anim('idle', 'text_flash', 'alpha',
           lambda t: 0.28 * max(0.0, math.sin(2 * math.pi * (t / P - 0.1))) ** 6)

    # ---- land (0.6s) ------------------------------------------------------
    setup_alpha('land')
    s.anim('land', 'glow', 'alpha', lambda t: seg(t, 0.12, 0.3, 0, 0.9) - seg(t, 0.3, 0.6, 0, 0.55))
    by = s.bones[[b['name'] for b in s.bones].index('burger')]['y']
    s.anim('land', 'burger', 'translate',
           lambda t: (X(bcx), by + (seg(t, 0, 0.14, 26 * U, 0, ease=in_cubic) if t < 0.14 else 0)))
    s.anim('land', 'burger', 'scale', lambda t: (
        1 + seg(t, 0.14, 0.22, 0, 0.12) - seg(t, 0.22, 0.5, 0, 0.12, ease=out_back),
        1 - seg(t, 0.14, 0.22, 0, 0.16) + seg(t, 0.22, 0.5, 0, 0.16, ease=out_back)))
    s.anim('land', 'text', 'scale', lambda t: (
        seg(t, 0, 0.14, 0.82, 0.82) if t < 0.14 else seg(t, 0.14, 0.46, 0.82, 1.0, ease=out_back),) * 2)
    s.anim('land', 'text_flash', 'alpha', lambda t: seg(t, 0.14, 0.2, 0, 0.7) - seg(t, 0.2, 0.5, 0, 0.7))

    # ---- win (2.6s) -------------------------------------------------------
    W = s
    T_SQ, T_SWAP, T_UP, T_HOLD, T_FALL, T_BACK = 0.0, 0.24, 0.30, 0.82, 1.32, 1.86
    setup_alpha('win')
    # anticipation squash, then the assembled burger hands over to the layers
    W.anim('win', 'burger', 'scale', lambda t: (
        1 + seg(t, 0, T_SWAP, 0, 0.1) - seg(t, T_BACK, T_BACK + 0.36, 0, 0.1, ease=out_back),
        1 - seg(t, 0, T_SWAP, 0, 0.14) + seg(t, T_BACK, T_BACK + 0.36, 0, 0.14, ease=out_back)))
    W.anim('win', 'burger', 'alpha', lambda t: 1 - seg(t, T_SWAP, T_SWAP + 0.06, 0, 1) + seg(t, T_BACK - 0.04, T_BACK + 0.04, 0, 1))
    # the stack mirrors the burger's squash while it is swapped in/out
    W.anim('win', 'stack', 'scale', lambda t: (
        1.1 - seg(t, T_SWAP, T_SWAP + 0.22, 0, 0.1, ease=out_back) + seg(t, T_BACK - 0.08, T_BACK, 0, 0.1, ease=in_cubic),
        0.86 + seg(t, T_SWAP, T_SWAP + 0.22, 0, 0.14, ease=out_back) - seg(t, T_BACK - 0.08, T_BACK, 0, 0.14, ease=in_cubic)))
    n = len(DRAW_ORDER)
    for i, name in enumerate(DRAW_ORDER):           # 0 = base ... 6 = top bun
        bone = 'L_' + name
        b = next(b for b in s.bones if b['name'] == bone)
        bx0, by0 = b.get('x', 0), b.get('y', 0)
        lift = (i ** 1.12) * 7.5 * U                 # exploded gap grows upward
        side = (-1) ** i
        t_up = T_UP + (n - 1 - i) * 0.025           # top flies first
        t_land = T_FALL + i * 0.07                  # lands bottom-up
        wob_ph = i * 0.37

        def ty(t, lift=lift, t_up=t_up, t_land=t_land, wob_ph=wob_ph, i=i):
            if t < t_up:
                return 0
            if t < T_HOLD:
                return seg(t, t_up, T_HOLD, 0, lift, ease=out_back)
            if t < t_land:
                hang = lift + 3 * U * math.sin(2 * math.pi * ((t - T_HOLD) / 0.9 + wob_ph)) * clamp((t - T_HOLD) / 0.2)
                f = clamp((t - (t_land - 0.3)) / 0.3)
                return lerp(hang, 0, in_cubic(f)) if f > 0 else hang
            # tiny bounce on impact
            k = (t - t_land) / 0.22
            return 2.5 * U * math.sin(math.pi * k) * (1 - k) if k < 1 else 0

        def tx(t, side=side, t_up=t_up, t_land=t_land, i=i):
            spread = side * (1.5 + i * 0.5) * U
            if t < t_up or t >= t_land:
                return 0
            up = seg(t, t_up, T_HOLD, 0, 1)
            down = seg(t, t_land - 0.3, t_land, 0, 1, ease=in_cubic)
            return spread * up * (1 - down)

        def rot(t, side=side, t_up=t_up, t_land=t_land, i=i, wob_ph=wob_ph):
            if t < t_up or t >= t_land:
                return 0
            amp = side * (2.5 + 0.8 * i) if i else 0
            up = seg(t, t_up, T_HOLD, 0, 1, ease=out_back)
            down = seg(t, t_land - 0.3, t_land, 0, 1, ease=in_cubic)
            wob = 1.6 * math.sin(2 * math.pi * ((t - t_up) / 0.8 + wob_ph))
            return (amp + wob * (i > 0)) * up * (1 - down)

        W.anim('win', bone, 'translate', lambda t, tx=tx, ty=ty, bx0=bx0, by0=by0: (bx0 + tx(t), by0 + ty(t)))
        W.anim('win', bone, 'rotate', rot)
        W.anim('win', name, 'alpha', lambda t: seg(t, T_SWAP, T_SWAP + 0.06, 0, 1) - seg(t, T_BACK - 0.04, T_BACK + 0.04, 0, 1))
        W.anim('win', name + '_flash', 'alpha',
               lambda t, t_land=t_land: seg(t, t_land, t_land + 0.04, 0, 0.28) - seg(t, t_land + 0.04, t_land + 0.25, 0, 0.28)
               if t < T_BACK + 0.04 else 0)

    # lettering: punch on the burst and on the final slam
    W.anim('win', 'text', 'scale', lambda t: (
        1 + seg(t, 0, T_SWAP, 0, -0.08) + seg(t, T_SWAP, T_SWAP + 0.3, 0, 0.26, ease=out_back)
        - seg(t, 0.62, 1.1, 0, 0.18) + seg(t, T_BACK - 0.04, T_BACK + 0.08, 0, 0.16)
        - seg(t, T_BACK + 0.08, T_BACK + 0.5, 0, 0.16, ease=out_back),) * 2)
    W.anim('win', 'text', 'rotate', lambda t: 4 * math.sin(2 * math.pi * (t - T_SWAP) / 0.55) * clamp((t - T_SWAP) / 0.1)
           * (1 - clamp((t - T_SWAP - 0.2) / 0.9)) if t > T_SWAP else 0)
    W.anim('win', 'text_flash', 'alpha', lambda t: seg(t, T_SWAP, T_SWAP + 0.05, 0, 0.42) - seg(t, T_SWAP + 0.05, T_SWAP + 0.4, 0, 0.42)
           + seg(t, T_BACK, T_BACK + 0.05, 0, 0.42) - seg(t, T_BACK + 0.05, T_BACK + 0.45, 0, 0.42))
    # glow + rays behind
    W.anim('win', 'glow', 'alpha', lambda t: 0.35 + seg(t, T_SWAP, T_SWAP + 0.15, 0, 0.65) - seg(t, 2.0, 2.6, 0, 0.65))
    W.anim('win', 'glow', 'scale', lambda t: (1 + seg(t, T_SWAP, T_SWAP + 0.3, 0, 0.35) - seg(t, 2.0, 2.6, 0, 0.35),) * 2)
    W.anim('win', 'rays', 'alpha', lambda t: seg(t, T_SWAP, T_SWAP + 0.25, 0, 0.75) - seg(t, 1.9, 2.5, 0, 0.75))
    W.anim('win', 'fx', 'rotate', lambda t: -40 * t / 2.6)
    W.anim('win', 'fx', 'scale', lambda t: (0.8 + seg(t, T_SWAP, T_SWAP + 0.4, 0, 0.35),) * 2)
    # spark bursts: out from the centre on the burst and on the slam
    for k, (b, ang, sp) in enumerate(sparks):
        def sp_alpha(t, k=k):
            def burst(t0):
                return seg(t, t0, t0 + 0.04, 0, 1) - seg(t, t0 + 0.12, t0 + 0.5, 0, 1)
            return burst(T_SWAP + (k % 3) * 0.02) + burst(T_BACK + (k % 4) * 0.015)

        def sp_scale(t, sp=sp):
            def run(t0):
                return seg(t, t0, t0 + 0.5, 0.3, 1.6 * sp)
            return (run(T_BACK) if t >= T_BACK else run(T_SWAP), 1)

        W.anim('win', b, 'alpha', sp_alpha)
        W.anim('win', b, 'scale', sp_scale)
    W.anim('win', 'stack', 'translate', lambda t: (X(95), Y(pivot_y)))

    s.write()


def debug_stack(layers, burger_full, text, out):
    """Closed stack vs. burger.png on the tile, side by side (x3)."""
    k = 3
    bw, bh = round(burger_full.width * BURGER_S * k), round(burger_full.height * BURGER_S * k)
    a = Image.new('RGBA', (TILE_W * k, TILE_H * k), (25, 30, 70, 255))
    a.alpha_composite(burger_full.resize((bw, bh), Image.LANCZOS), (0, 0))
    b = Image.new('RGBA', a.size, (25, 30, 70, 255))
    for name in DRAW_ORDER:
        im = layers[name][0]
        cx, cy, w = STACK[name]
        h = w * im.height / im.width
        r = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
        b.alpha_composite(r, (round((cx - w / 2) * k), round((cy - h / 2) * k)))
    for im in (a, b):
        im.alpha_composite(text.resize((TILE_W * k, text.height * k), Image.LANCZOS), (0, TEXT_Y * k))
    c = Image.new('RGBA', (a.width * 2 + 20, a.height), (0, 0, 0, 255))
    c.paste(a, (0, 0))
    c.paste(b, (a.width + 20, 0))
    c.save(os.path.join(out, 'scatter_stack_debug.png'))


if __name__ == '__main__':
    build(debug_dir=sys.argv[1] if len(sys.argv) > 1 else None)
