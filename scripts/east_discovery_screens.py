"""East Discovery — feature (preview), bonus and Hold & Win screens as Spine 4.1 skeletons.

Replaces the DOM screens (front/east-discovery.html #introScreen / #bonusScreen /
#holdWinScreen) with the same contract the other games use (sugar_galaxy_screens.py,
dirty_money_mafia_screens.py): one full-screen skeleton per screen and orientation,
authored on the design canvas (origin = canvas centre, 1 unit = 1 design px, y up),
with `intro` (3s) and a seamless looping `idle` (4s, first idle frame == last intro
frame). Six skeletons: feature / bonus / holdwin x desk (1932x940) / mob (780x1416).
The background stays a DOM layer under the canvas (the game's own bg, cover).

Art is the game's own: the logo, the symbol statics, the sky-lantern counter, the buy
banner, the jade dialog panel and the sakura/coin pieces cut out of the popup atlases,
plus the two Spine heroes rendered to stills in their setup pose (scripts/spine_pose.py).

Texts come from east_discovery_texts/fitlib.py — the same code the localisation table is
measured with. Every field has ONE fixed font size (product rule 2026-11-12: the engine
never resizes plaques or fonts per language) at which EN and every translation fit the
field's box, so --lang only changes glyphs and line breaks, never the layout. --notext
drops the strings and leaves a bare bone per field (+ text_fields.json) for the engine.

Usage:
  python scripts/east_discovery_screens.py [out_dir] [--lang ru] [--notext]

out_dir — default front/img/east-discovery/screens
"""

import argparse
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'east_discovery_texts'))
from spine_screen_kit import (  # noqa: E402
    Skel, breathe, clamp, flash_of, hexc, out_back, out_cubic, pulse, rays, seg, soft_glow, spark,
    trim, vgrad, wave,
)
import spine_pose  # noqa: E402
import fitlib  # noqa: E402
from texts import LAYOUT, MOB_CARDS, CARD_KEYS  # noqa: E402

ROOT = os.path.dirname(HERE)
ART_DIR = os.path.join(ROOT, 'front', 'img', 'east-discovery')
CACHE = os.path.join(HERE, '.cache', 'east_heroes')   # rendered hero stills (not shipped)
_ap = argparse.ArgumentParser()
_ap.add_argument('out', nargs='?', default=os.path.join(ART_DIR, 'screens'))
_ap.add_argument('--lang', default='en')
_ap.add_argument('--notext', action='store_true')
_A = _ap.parse_args()
OUT, LANG, NOTEXT = _A.out, _A.lang, _A.notext
RECS = {(r['screen'], r['dev'], r['key']): r for r in fitlib.fields()}
TEXT_FIELDS = []

INTRO = 3.0
IDLE = 4.0
DESK = LAYOUT['desk']['canvas']
MOB = LAYOUT['mob']['canvas']


# --------------------------------------------------------------------------
# source art

def art(rel):
    return Image.open(os.path.join(ART_DIR, rel)).convert('RGBA')


def parse_atlas(path):
    regions, page, cur = {}, None, None
    for line in open(path):
        line = line.rstrip('\n')
        if not line.strip():
            cur = None
            continue
        if ':' not in line:
            if page is None or (cur is None and line.endswith('.png')):
                page, cur = line.strip(), None
            else:
                cur = regions[line.strip()] = {}
            continue
        if cur is not None:
            k, v = (s.strip() for s in line.split(':', 1))
            cur[k] = v
    return regions


def popup_region(popup, name):
    """One region of a popup export, un-rotated and trimmed."""
    folder = os.path.join(ART_DIR, "Popup's", popup)
    r = parse_atlas(os.path.join(folder, 'animation.atlas'))[name]
    page = Image.open(os.path.join(folder, 'animation.png')).convert('RGBA')
    x, y, w, h = map(int, r['bounds'].split(','))
    if r.get('rotate') in ('90', 'true'):
        im = page.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
    else:
        im = page.crop((x, y, x + w, y + h))
    return trim(im)


def hero(name):
    """Spine hero in its setup pose, rendered once and cached next to the export."""
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f'{name}.png')
    if not os.path.exists(p):
        spine_pose.render(os.path.join(ART_DIR, 'Export', name), p, scale=1.4)
    return Image.open(p).convert('RGBA')


def hd(im, k=2):
    """Lanczos upscale + unsharp for art that ships smaller than its screen use."""
    im = im.resize((im.width * k, im.height * k), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=2.0, percent=80, threshold=2))
    rgb.putalpha(im.getchannel('A'))
    return rgb


def soft(im, w):
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


def jade_panel(w, h, s=0.62):
    """Card panel: the buy dialog's jade board (nefrit-bg) 9-sliced to w x h, so its gold
    corners, pagoda and dragon ornaments keep their size."""
    src = popup_region('popup-buybonusspins', 'nefrit-bg 1')
    src = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    sw, sh = src.size
    L = R = round(150 * s)
    T, B = round(120 * s), round(190 * s)
    out = Image.new('RGBA', (w, h))

    def piece(box, size):
        p = src.crop(box)
        return p.resize(size, Image.LANCZOS) if p.size != size else p

    cw, ch = w - L - R, h - T - B
    mx, my = sw // 2, sh // 2
    out.alpha_composite(piece((mx - 40, my - 40, mx + 40, my + 40), (cw, ch)), (L, T))     # jade fill
    out.alpha_composite(piece((L, my - 40, sw - R, my + 40), (cw, ch)).resize((cw, ch)), (L, T))
    out.alpha_composite(piece((L, 0, sw - R, T), (cw, T)), (L, 0))
    out.alpha_composite(piece((L, sh - B, sw - R, sh), (cw, B)), (L, h - B))
    out.alpha_composite(piece((0, T, L, sh - B), (L, ch)), (0, T))
    out.alpha_composite(piece((sw - R, T, sw, sh - B), (R, ch)), (w - R, T))
    out.alpha_composite(piece((0, 0, L, T), (L, T)), (0, 0))
    out.alpha_composite(piece((sw - R, 0, sw, T), (R, T)), (w - R, 0))
    out.alpha_composite(piece((0, sh - B, L, sh), (L, B)), (0, h - B))
    out.alpha_composite(piece((sw - R, sh - B, sw, sh), (R, B)), (w - R, h - B))
    return out


def star4(size=96):
    s = spark(size, max(6, size // 7))
    im = Image.new('RGBA', (size, size))
    im.alpha_composite(s, (0, (size - s.height) // 2))
    im.alpha_composite(s.rotate(90, expand=True), ((size - s.height) // 2, 0))
    im.alpha_composite(soft_glow(size // 2), (size // 4, size // 4))
    return im


ART = {
    'logo': trim(hd(art('img/Logo_east.png'), 3)),
    'burst': soft(popup_region('popup-bigwin', 'svechenie_bigwin'), 760),
    'rays': rays(560, n=16, col=(255, 214, 140)),
    'glow': soft_glow(256),
    'star': star4(96),
    # mirrored: in the popup the branches hang from the dialog's top edge, so their cut
    # ends point outward only after a flip — in a screen corner the stem must leave the
    # frame, with the blossoms spraying toward the centre.
    'sakura_l': popup_region('popup-bigwin', 'sakura_L 1_bigwin').transpose(Image.FLIP_LEFT_RIGHT),
    'sakura_r': popup_region('popup-bigwin', 'sakura_R 1_bigwin').transpose(Image.FLIP_LEFT_RIGHT),
    'coins1': popup_region('popup-bigwin', 'coins 1_bigwin'),
    'coins2': popup_region('popup-bigwin', 'coins 2_bigwin'),
    'chest': popup_region('popup-bonusspinswin', 'chest-coins-dragon 1 (1)'),
    'bag': popup_region('popup-bonusspinswin', 'left-coins-bag 1 (1)'),
    'lantern': trim(art('img/free-spins-counter.png')),
    'banner': trim(art('img/buy-bonus-button.png')),
    'wild': trim(art('Export/wild/static_wild_big.png')),
    'scatter': trim(art('Export/scatter/static.png')),
    'tiger': trim(art('Export/collector_tiger/static.png')),
    'coin': trim(art('Export/coin/static.png')),
    'hero_base': hero('Hero_base'),
    'hero_bonus': hero('Hero_Bonus'),
}
ART['logo_flash'] = flash_of(ART['logo'], 0.9)
ART['wild_flash'] = flash_of(ART['wild'], 0.85)
ART['scatter_flash'] = flash_of(ART['scatter'], 0.8)
ART['tiger_flash'] = flash_of(ART['tiger'], 0.8)
ART['banner_flash'] = flash_of(ART['banner'], 0.7)
ART['panel_desk'] = jade_panel(*LAYOUT['desk']['card'])
ART['panel_mob'] = jade_panel(*LAYOUT['mob']['card'])


# --------------------------------------------------------------------------
# translatable text fields
#
# A field is a fixed box on the screen (the same for every language). `field()` draws the
# string of LANG at the box's one fixed font size; `place()` either attaches it or, under
# --notext, leaves the bone bare and records the box for the localisation hand-off.

def field(screen, dev, key):
    r = RECS[(screen, dev, key)]
    im, s = fitlib.block(key, LANG, r)
    return dict(rec=r, im=im, reg=f'{key}_{dev}', w=im.width * s, h=im.height * s,
                bw=r['box_w'], bh=r['box_h'])


def place(sk, slot, bone, f):
    r = f['rec']
    if NOTEXT:
        TEXT_FIELDS.append(dict(skeleton=sk.name, screen=r['screen'], device=r['dev'], key=r['key'],
                                bone=bone, slot=slot, box_w=r['box_w'], box_h=r['box_h'],
                                font_px=r['px'], en_font_px=r['en_px'], limit=r['limit'],
                                style=fitlib.FAM[fitlib.TEXTS[r['key']]['style']][0]))
        return sk.slot_empty(slot, bone)
    sk.image(f['reg'], f['im'])
    return sk.slot(slot, bone, f['reg'], w=f['w'])


# --------------------------------------------------------------------------
# motion helpers (every idle offset is 0 at t=0, so idle starts where intro ended)

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
        sk.image(k, ART[k])


def twinkles(sk, parent, spots, seed, start=1.4, tint='ffe2a8ff'):
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


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.8, rays_w=None, rays_alpha=0.3):
    rw = rays_w or w * 0.8
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=rw, blend='additive', color='ffd08aff')
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both(rb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.8, 0.4, 1.0)), uniform(lambda t: 1))
    sk.both(f'{name}_rays', 'alpha', lambda t: rays_alpha * fade(t, t0, 0.6),
            lambda t: rays_alpha * (1 - 0.3 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, 'burst', w=w, blend='additive')
    sk.both(b, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.3, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.05)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.5),
            lambda t: alpha * (1 - 0.2 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))


def floater(sk, name, region, parent, x, y, w, t0, amp=10, period=IDLE, phase=0.0, rot_amp=0.0,
            slide=(0, -40), alpha=1.0, rot=0):
    b = sk.bone(name, parent, x, y, rot=rot)
    sk.slot(name, b, region, w=w)

    def pos(t, idle_t):
        k = seg(t, t0, t0 + 0.8, 1.0, 0.0)
        return (slide[0] * k, slide[1] * k + bob(idle_t, amp, period, phase))

    move(sk, b, lambda t: pos(t, 0), lambda t: pos(99, t))
    if rot_amp:
        sk.both(b, 'rotate', lambda t: rot, lambda t: rot + bob(t, rot_amp, period, phase + 0.25))
    sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.7, 0.5)), uniform(lambda t: 1))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.4), lambda t: alpha)
    return b


def glow_under(sk, name, parent, w, t0, tint, alpha=0.6, y=0):
    g = sk.bone(name, parent, 0, y)
    sk.slot(name, g, 'glow', w=w, blend='additive', color=tint)
    sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.12)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0), lambda t: alpha)


def tap_hint(sk, screen, dev, key, y):
    b = sk.bone('tap', 'root', 0, y)
    place(sk, 'tap', b, field(screen, dev, key))
    sk.both(b, 'scale', uniform(lambda t: seg(t, 2.2, 2.7, 0.8, 1.0, out_back)),
            uniform(lambda t: breathe(t, 2.0, 0.04)))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.5),
            lambda t: 0.775 + 0.225 * math.cos(2 * math.pi * t / 2.0))


def logo_block(sk, x, y, w):
    lb = sk.bone('logo', 'root', x, y)
    sk.slot('logo', lb, 'logo', w=w)
    sk.slot('logo_flash', lb, 'logo_flash', w=w, blend='additive')
    sk.both(lb, 'scale', uniform(lambda t: seg(t, 0.15, 0.85, 0.2, 1.0, out_back)),
            uniform(lambda t: breathe(t, IDLE, 0.025)))
    move(sk, lb, lambda t: (0, 0), lambda t: (0, bob(t, 6)))
    sk.both('logo', 'alpha', lambda t: fade(t, 0.15, 0.25), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: seg(t, 0.6, 1.1, 0.85, 0.0) if t >= 0.6 else 0,
            lambda t: 0.4 * pulse(t, IDLE, 0.55, 10))
    return lb


def sakura_corners(sk, w, h, s=1.0, t0=0.3):
    """The popup atlases' sakura branches in the top corners, breathing in the breeze."""
    for i, (reg, x, rot) in enumerate((('sakura_l', -w / 2 + 150 * s, 0), ('sakura_r', w / 2 - 140 * s, 0))):
        b = floater(sk, f'sak{i}', reg, 'root', x, h / 2 - 120 * s, 330 * s, t0 + 0.1 * i,
                    amp=7, phase=0.3 * i, rot_amp=2.5, slide=(0, 30), rot=rot)
        sk.both(f'sak{i}', 'alpha', lambda t, d=t0 + 0.1 * i: 0.95 * fade(t, d, 0.5), lambda t: 0.95)
        _ = b


# --------------------------------------------------------------------------
# feature (preview) screen

def card_art(sk, key, parent, idx, t0, s, room, width):
    """Card illustration centred on `parent`; room/width = the free box above the title."""
    if key == 'wild':
        h = min(room, 320 * s)
        glow_under(sk, f'c{idx}_glow', parent, 260 * s, t0, 'ffb04aff', 0.5)
        b = sk.bone(f'c{idx}_i', parent)
        sk.slot(f'c{idx}_i', b, 'wild', h=h)
        fl = sk.slot(f'c{idx}_flash', b, 'wild_flash', h=h, blend='additive')
        # expanding: the dragon tile grows out of a symbol-sized cell
        sk.both(b, 'scale', lambda t: (seg(t, t0, t0 + 0.4, 0.0, 1.0, out_cubic),
                                       seg(t, t0, t0 + 0.4, 0.0, 0.36, out_cubic) if t < t0 + 0.55
                                       else seg(t, t0 + 0.55, t0 + 0.95, 0.36, 1.0, out_back)),
                uniform(lambda t: 1 + 0.03 * pulse(t, 2.0, 0.0, 4)))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.95, t0 + 1.4, 0.8, 0.0) if t > t0 + 0.95 else 0,
                lambda t: 0.4 * pulse(t, 4.0, 0.5, 8))
    elif key == 'fs':
        d = min(room * 0.9, 220 * s)
        glow_under(sk, f'c{idx}_glow', parent, d * 1.7, t0, 'ffc25aff', 0.5)
        b = sk.bone(f'c{idx}_i', parent, 0, d * 0.04)
        sk.slot(f'c{idx}_i', b, 'scatter', w=d)
        fl = sk.slot(f'c{idx}_flash', b, 'scatter_flash', w=d, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)),
                uniform(lambda t: 1 + 0.06 * pulse(t, 2.0, 0.25, 6)))
        move(sk, b, lambda t: (0, seg(t, t0, t0 + 0.5, 70 * s, 0, out_back)),
             lambda t: (0, bob(t, 6 * s, 2.0, 0.25)))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.55, t0 + 0.95, 0.7, 0.0) if t > t0 + 0.55 else 0,
                lambda t: 0.45 * pulse(t, 4.0, 0.6, 8))
        for j, (x, y, ph) in enumerate(((-d * 0.72, -d * 0.3, 0.0), (d * 0.72, -d * 0.3, 0.5))):
            cb = sk.bone(f'c{idx}_m{j}', parent, x, y)
            sk.slot(f'c{idx}_m{j}', cb, 'coin', w=d * 0.3)
            sk.both(cb, 'scale', uniform(lambda t, dd=t0 + 0.3 + 0.1 * j: pop(t, dd, 0.5, 0.0)), uniform(lambda t: 1))
            move(sk, cb, lambda t, dd=t0 + 0.3 + 0.1 * j: (0, seg(t, dd, dd + 0.5, -40 * s, 0, out_back)),
                 lambda t, p=ph: (0, bob(t, 7 * s, 2.0, p)))
    elif key == 'hw':
        d = min(room * 0.78, 200 * s)
        glow_under(sk, f'c{idx}_glow', parent, d * 1.8, t0, 'ffb04aff', 0.5)
        b = sk.bone(f'c{idx}_i', parent)
        sk.slot(f'c{idx}_i', b, 'tiger', w=d)
        fl = sk.slot(f'c{idx}_flash', b, 'tiger_flash', w=d, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)),
                uniform(lambda t: 1 + 0.04 * pulse(t, 2.0, 0.0, 6)))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.5, t0 + 0.9, 0.7, 0.0) if t > t0 + 0.5 else 0,
                lambda t: 0.3 * pulse(t, 2.0, 0.35, 8))
        # coins fly in around the tiger and keep orbiting gently
        for j, (ang, k) in enumerate(((205, 0.40), (335, 0.36), (265, 0.30))):
            a = math.radians(ang)
            x, y = d * 0.72 * math.cos(a), d * 0.62 * math.sin(a)
            cb = sk.bone(f'c{idx}_m{j}', parent, x, y)
            sk.slot(f'c{idx}_m{j}', cb, 'coin', w=d * k)
            sk.both(cb, 'scale', uniform(lambda t, dd=t0 + 0.35 + 0.12 * j: pop(t, dd, 0.5, 0.0)),
                    uniform(lambda t: 1))
            move(sk, cb, lambda t, dd=t0 + 0.35 + 0.12 * j: (0, seg(t, dd, dd + 0.5, -40 * s, 0, out_back)),
                 lambda t, p=j * 0.3: (0, bob(t, 7 * s, 2.0, p)))
    elif key == 'buy':
        h = min(room, 320 * s)
        glow_under(sk, f'c{idx}_glow', parent, 240 * s, t0, 'ff7a3aff', 0.5)
        b = sk.bone(f'c{idx}_i', parent)
        sk.slot(f'c{idx}_i', b, 'banner', h=h)
        fl = sk.slot(f'c{idx}_flash', b, 'banner_flash', h=h, blend='additive')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)), uniform(lambda t: 1))
        sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, 2.2, IDLE))
        sk.both(fl, 'alpha', lambda t: seg(t, t0 + 0.4, t0 + 0.8, 0.7, 0.0) if t > t0 + 0.4 else 0,
                lambda t: 0.3 * pulse(t, 2.0, 0.0, 6))
    _ = width


def feature_card(sk, dev, idx, key, x, y, t0):
    L = LAYOUT[dev]
    pw, ph = L['card']
    s = 1.0 if dev == 'desk' else 0.92
    c = sk.bone(f'card{idx}', 'root', x, y)
    sk.slot(f'card{idx}', c, 'panel_desk' if dev == 'desk' else 'panel_mob', w=pw)
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -70, 0)), lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    # text boxes are fixed: the title box sits `t_y` above the panel's bottom edge, the
    # description box `d_y` — the art gets whatever is left above them.
    tf, df = field('feature', dev, f't_{key}'), field('feature', dev, f'd_{key}')
    t_y = -ph / 2 + L['t_y'] + tf['bh'] / 2
    d_y = -ph / 2 + L['d_y'] + df['bh'] / 2
    tb = sk.bone(f'card{idx}_t', c, 0, t_y)
    place(sk, f'card{idx}_t', tb, tf)
    sk.both(f'card{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.15), lambda t: 1)
    db = sk.bone(f'card{idx}_d', c, 0, d_y)
    place(sk, f'card{idx}_d', db, df)
    sk.both(f'card{idx}_d', 'alpha', lambda t: fade(t, t0 + 0.3), lambda t: 1)

    top = ph / 2 - 32 * s
    bot = t_y + tf['bh'] / 2 + 12
    ib = sk.bone(f'card{idx}_art', c, 0, (top + bot) / 2)
    card_art(sk, key, ib, idx, t0 + 0.25, s, top - bot, pw - 60)


def build_feature(variant):
    L = LAYOUT[variant]
    w, h = L['canvas']
    sk = Skel(f'feature_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'star', 'sakura_l', 'sakura_r',
            'wild', 'wild_flash', 'scatter', 'scatter_flash', 'tiger', 'tiger_flash', 'coin',
            'banner', 'banner_flash', 'panel_desk' if variant == 'desk' else 'panel_mob')

    lx, ly, lw = L['logo']
    light_burst(sk, 'burst', 'root', lx, ly, lw * 2.0, t0=0.0, alpha=0.5, rays_w=lw * 1.6)
    sakura_corners(sk, w, h, 1.0 if variant == 'desk' else 0.78)
    logo_block(sk, lx, ly, lw)

    if variant == 'desk':
        x0, step = L['cards_x']
        cards = [(x0 + step * i, L['cards_y']) for i in range(4)]
        spots = [(-430, 300, 0.8), (430, 320, 0.9), (-900, 120, 0.7), (900, 140, 0.6),
                 (-250, -400, 0.5), (260, -400, 0.5), (0, 420, 0.5)]
    else:
        cards = MOB_CARDS
        spots = [(-300, 640, 0.7), (300, 500, 0.8), (-330, 20, 0.6), (340, -40, 0.6),
                 (-280, -620, 0.5), (300, -600, 0.5)]

    for i, ((x, y), key) in enumerate(zip(cards, CARD_KEYS)):
        feature_card(sk, variant, i, key, x, y, 0.75 + 0.18 * i)

    twinkles(sk, 'root', spots, seed=5)
    tap_hint(sk, 'feature', variant, 'tap_continue', L['tap_y'])
    sk.write()


# --------------------------------------------------------------------------
# bonus / hold&win screens

def build_bonus(variant):
    L = LAYOUT[variant]
    w, h = L['canvas']
    desk = variant == 'desk'
    sk = Skel(f'bonus_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'star', 'sakura_l', 'sakura_r',
            'lantern', 'hero_bonus', 'chest', 'bag', 'coins1', 'coins2')

    lx, ly, lw = L['logo']
    light_burst(sk, 'burst', 'root', 0, (120 if desk else 170), (1250 if desk else 760),
                t0=0.4, alpha=0.55, rays_w=(900 if desk else 620), rays_alpha=0.3)
    sakura_corners(sk, w, h, 1.0 if desk else 0.78)
    logo_block(sk, lx, ly, lw * (0.85 if desk else 0.9))

    title_y, sub_y = (190, -245) if desk else (320, -205)
    lan_y, lan_w = (-45, 215) if desk else (50, 270)

    # title
    tb = sk.bone('title', 'root', 0, title_y)
    tf = field('bonus', variant, 'b_title')
    place(sk, 'title', tb, tf)
    sk.both(tb, 'scale', uniform(lambda t: seg(t, 0.35, 0.8, 1.6, 0.96, out_cubic) if t < 0.8
                                 else seg(t, 0.8, 1.05, 0.96, 1.0, out_back)),
            uniform(lambda t: breathe(t, 2.0, 0.02)))
    sk.both('title', 'alpha', lambda t: fade(t, 0.35, 0.2), lambda t: 1)

    # sky lantern with the live spin count (DOM/engine overlay glued to bone `count`)
    glow_under(sk, 'lan_glow', 'root', lan_w * 2.4, 0.9, 'ff9a3aff', 0.55, y=lan_y)
    lb = sk.bone('lantern', 'root', 0, lan_y)
    sk.slot('lantern', lb, 'lantern', w=lan_w)
    sk.bone('count', lb, 0, -lan_w * 0.06)
    sk.both(lb, 'scale', uniform(lambda t: pop(t, 0.9, 0.6, 0.2)), uniform(lambda t: breathe(t, 2.4, 0.03)))
    move(sk, lb, lambda t: (0, seg(t, 0.9, 1.5, -90, 0, out_back)), lambda t: (0, bob(t, 10, IDLE)))
    sk.both(lb, 'rotate', lambda t: 0, lambda t: bob(t, 2, IDLE, 0.2))
    sk.both('lantern', 'alpha', lambda t: fade(t, 0.9, 0.3), lambda t: 1)

    sb = sk.bone('sub', 'root', 0, sub_y)
    place(sk, 'sub', sb, field('bonus', variant, 'b_sub'))
    sk.both(sb, 'scale', uniform(lambda t: pop(t, 1.4, 0.5, 0.6)), uniform(lambda t: 1))
    sk.both('sub', 'alpha', lambda t: fade(t, 1.4, 0.35), lambda t: 1)

    # hero + treasure props
    if desk:
        floater(sk, 'hero', 'hero_bonus', 'root', 690, -120, 330, 0.5, amp=8, rot_amp=1.2, slide=(90, 0))
        floater(sk, 'chest', 'chest', 'root', -700, -210, 330, 0.7, amp=8, phase=0.4, rot_amp=1.5, slide=(-90, 0))
        floater(sk, 'bag', 'bag', 'root', -300, -330, 210, 0.9, amp=7, phase=0.7, rot_amp=2)
        floater(sk, 'coins0', 'coins1', 'root', 330, -330, 190, 1.0, amp=9, phase=0.2, rot_amp=4)
        spots = [(-480, 300, 0.8), (480, 320, 0.9), (-860, -260, 0.7), (860, -240, 0.6), (0, 380, 0.5)]
    else:
        floater(sk, 'hero', 'hero_bonus', 'root', 190, -420, 290, 0.5, amp=8, rot_amp=1.2, slide=(70, 0))
        floater(sk, 'chest', 'chest', 'root', -200, -430, 260, 0.7, amp=8, phase=0.4, rot_amp=1.5, slide=(-70, 0))
        floater(sk, 'coins0', 'coins1', 'root', -270, 420, 170, 1.0, amp=9, phase=0.2, rot_amp=4)
        floater(sk, 'coins1_', 'coins2', 'root', 280, 400, 160, 1.1, amp=9, phase=0.6, rot_amp=4)
        spots = [(-300, 560, 0.7), (300, 520, 0.8), (-320, -120, 0.6), (330, -140, 0.6)]

    twinkles(sk, 'root', spots, seed=11)
    tap_hint(sk, 'bonus', variant, 'tap_start', L['tap_y'])
    sk.write()


def build_holdwin(variant):
    L = LAYOUT[variant]
    w, h = L['canvas']
    desk = variant == 'desk'
    sk = Skel(f'holdwin_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'star', 'sakura_l', 'sakura_r',
            'tiger', 'tiger_flash', 'coin', 'hero_base', 'bag')

    lx, ly, lw = L['logo']
    light_burst(sk, 'burst', 'root', 0, (0 if desk else 90), (1150 if desk else 720),
                t0=0.4, alpha=0.55, rays_w=(860 if desk else 600), rays_alpha=0.3)
    sakura_corners(sk, w, h, 1.0 if desk else 0.78)
    logo_block(sk, lx, ly, lw * (0.85 if desk else 0.9))

    title_y, sub_y = (165, -250) if desk else (300, -210)
    tig_y, tig_w = (-45, 260) if desk else (45, 300)

    tb = sk.bone('title', 'root', 0, title_y)
    place(sk, 'title', tb, field('holdwin', variant, 'hw_title'))
    sk.both(tb, 'scale', uniform(lambda t: seg(t, 0.35, 0.8, 1.6, 0.96, out_cubic) if t < 0.8
                                 else seg(t, 0.8, 1.05, 0.96, 1.0, out_back)),
            uniform(lambda t: breathe(t, 2.0, 0.02)))
    sk.both('title', 'alpha', lambda t: fade(t, 0.35, 0.2), lambda t: 1)

    glow_under(sk, 'tig_glow', 'root', tig_w * 2.2, 0.9, 'ffb04aff', 0.55, y=tig_y)
    tgb = sk.bone('tiger', 'root', 0, tig_y)
    sk.slot('tiger', tgb, 'tiger', w=tig_w)
    fl = sk.slot('tiger_flash', tgb, 'tiger_flash', w=tig_w, blend='additive')
    sk.both(tgb, 'scale', uniform(lambda t: pop(t, 0.9, 0.6, 0.2)),
            uniform(lambda t: 1 + 0.035 * pulse(t, 2.0, 0.0, 6)))
    move(sk, tgb, lambda t: (0, seg(t, 0.9, 1.5, -80, 0, out_back)), lambda t: (0, bob(t, 8, IDLE)))
    sk.both('tiger', 'alpha', lambda t: fade(t, 0.9, 0.3), lambda t: 1)
    sk.both(fl, 'alpha', lambda t: seg(t, 1.4, 1.9, 0.8, 0.0) if t >= 1.4 else 0,
            lambda t: 0.3 * pulse(t, 2.0, 0.35, 8))

    # coins orbit the collector: they fly in one after another, then bob in place
    for j, ang in enumerate((150, 30, 205, 335)):
        a = math.radians(ang)
        x, y = tig_w * (1.25 if desk else 1.1) * math.cos(a), tig_y + tig_w * 0.78 * math.sin(a)
        cb = sk.bone(f'coin{j}', 'root', x, y)
        sk.slot(f'coin{j}', cb, 'coin', w=tig_w * 0.36)
        t0 = 1.3 + 0.12 * j
        sk.both(cb, 'scale', uniform(lambda t, d=t0: pop(t, d, 0.5, 0.0)), uniform(lambda t: 1))
        move(sk, cb, lambda t, d=t0: (0, seg(t, d, d + 0.5, -60, 0, out_back)),
             lambda t, p=j * 0.2: (0, bob(t, 9, 2.0, p)))
        sk.both(f'coin{j}', 'alpha', lambda t, d=t0: fade(t, d, 0.3), lambda t: 1)

    sb = sk.bone('sub', 'root', 0, sub_y)
    place(sk, 'sub', sb, field('holdwin', variant, 'hw_sub'))
    sk.both(sb, 'scale', uniform(lambda t: pop(t, 1.9, 0.5, 0.6)), uniform(lambda t: 1))
    sk.both('sub', 'alpha', lambda t: fade(t, 1.9, 0.35), lambda t: 1)

    if desk:
        floater(sk, 'hero', 'hero_base', 'root', 700, -130, 330, 0.5, amp=8, rot_amp=1.2, slide=(90, 0))
        floater(sk, 'bag', 'bag', 'root', -700, -250, 300, 0.7, amp=8, phase=0.4, rot_amp=2, slide=(-90, 0))
        spots = [(-480, 300, 0.8), (480, 320, 0.9), (-860, -260, 0.7), (860, -240, 0.6), (0, 380, 0.5)]
    else:
        floater(sk, 'hero', 'hero_base', 'root', 195, -440, 280, 0.5, amp=8, rot_amp=1.2, slide=(70, 0))
        floater(sk, 'bag', 'bag', 'root', -205, -450, 250, 0.7, amp=8, phase=0.4, rot_amp=2, slide=(-70, 0))
        spots = [(-300, 560, 0.7), (300, 520, 0.8), (-320, -120, 0.6), (330, -140, 0.6)]

    twinkles(sk, 'root', spots, seed=17)
    tap_hint(sk, 'holdwin', variant, 'tap_start', L['tap_y'])
    sk.write()


if __name__ == '__main__':
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
        build_holdwin(v)
    if NOTEXT:
        with open(os.path.join(OUT, 'text_fields.json'), 'w') as f:
            json.dump(TEXT_FIELDS, f, ensure_ascii=False, indent=1)
        print('text fields', len(TEXT_FIELDS))
