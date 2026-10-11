"""Multi Fruits Story — feature (preview) screen + bonus screen as Spine 4.1 skeletons.

Same contract as Sugar Galaxy's screens (scripts/sugar_galaxy_screens.py): a
full-screen skeleton on the game's design canvas (origin = canvas centre, 1 unit
= 1 design px, y up), `intro` (3s) -> `idle` (4s seamless loop, first idle frame
== last intro frame). Four variants: feature/bonus x desk (1932x940) / mob
(780x1416). The game's background is NOT in the skeleton — slot.js puts the
game's own bg PNG under the canvas (cover).

Art is the game's own: symbol statics (<code>/static.png), game-logo.png,
regions cut out of the popup atlases (light rays, gold pile, wooden plates,
green starry plate, gems, sparkles, leaf), plus PIL-drawn panels/text in the
popups' wood-and-gold style. The multiplier wilds (x2/x3/x5/x7) have no static
art — they are rendered here from the wild Spine export's setup pose with the
matching skin (`render_setup` below; a tiny region + weighted-mesh rasteriser).

Usage:
  python scripts/multi_fruits_story_screens.py <fonts_dir> [out_dir]

fonts_dir — luckiest.ttf, baloo.ttf (front/fonts woff2 converted with
            fontTools: TTFont(woff2).flavor = None; .save(ttf))
out_dir   — default front/img/multi-fruits-story/screens
"""

import json
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spine_screen_kit import (  # noqa: E402
    FPS, Skel, breathe, pack, premultiply, clamp, flash_of, hexc, out_back, out_cubic, pulse, rays, seg,
    soft_glow, spark, text_img, trim, vgrad, wave,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(ROOT, 'front', 'img', 'multi-fruits-story')

INTRO = 3.0
IDLE = 4.0
DESK = (1932, 940)
MOB = (780, 1416)

FONTS = None
OUT = None
ART = {}


# --------------------------------------------------------------------------
# Spine atlas / setup-pose helpers

def parse_atlas(path):
    """{page_png: {region: {key: value}}} — keeps track of which page a region is on."""
    pages, page, cur, expect_page = {}, None, None, True
    for line in open(path):
        line = line.rstrip('\n')
        if not line.strip():
            cur, expect_page = None, True
            continue
        if ':' not in line:
            if expect_page:
                page, cur = line.strip(), None
                pages.setdefault(page, {})
            else:
                cur = pages[page][line.strip()] = {}
            expect_page = False
            continue
        expect_page = False
        if cur is not None:
            k, v = (s.strip() for s in line.split(':', 1))
            cur[k] = v
    return pages


def atlas_regions(folder, restore=True):
    """region -> PIL image, un-rotated, whitespace restored to the original size
    (what mesh UVs / attachment sizes refer to). A single-page atlas is read from
    the folder's real animation.png whatever page name it carries (the exports
    sometimes name a stale texture)."""
    pages = parse_atlas(os.path.join(folder, 'animation.atlas'))
    out = {}
    for pname, regions in pages.items():
        path = os.path.join(folder, pname)
        if not os.path.exists(path) or len(pages) == 1:
            path = os.path.join(folder, 'animation.png')
        page = Image.open(path).convert('RGBA')
        for name, r in regions.items():
            x, y, w, h = map(int, r['bounds'].split(','))
            if r.get('rotate') in ('90', 'true'):
                im = page.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
            else:
                im = page.crop((x, y, x + w, y + h))
            if restore and 'offsets' in r:
                ox, oy, ow, oh = map(int, r['offsets'].split(','))
                full = Image.new('RGBA', (ow, oh))
                full.paste(im, (ox, oh - oy - im.height))
                im = full
            out[name] = im
    return out


def popup_region(popup, name):
    return trim(atlas_regions(os.path.join(ART_DIR, popup), restore=False)[name])


def _bone_world(bones):
    W = {}
    for b in bones:
        r = math.radians(b.get('rotation', 0))
        sx, sy = b.get('scaleX', 1), b.get('scaleY', 1)
        la, lb = math.cos(r) * sx, -math.sin(r) * sy
        lc, ld = math.sin(r) * sx, math.cos(r) * sy
        x, y = b.get('x', 0), b.get('y', 0)
        p = W.get(b.get('parent'))
        if p is None:
            W[b['name']] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, px, py = p
            W[b['name']] = (pa * la + pb * lc, pa * lb + pb * ld, pc * la + pd * lc, pc * lb + pd * ld,
                            pa * x + pb * y + px, pc * x + pd * y + py)
    return W


def _apply(m, x, y):
    a, b, c, d, tx, ty = m
    return a * x + b * y + tx, c * x + d * y + ty


def _warp_tri(canvas, src, s_pts, d_pts, blend=None, tint=None):
    """Affine-map triangle s_pts of src onto d_pts of canvas (pixel coords)."""
    (x0, y0), (x1, y1), (x2, y2) = d_pts
    (u0, v0), (u1, v1), (u2, v2) = s_pts
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(det) < 1e-6:
        return
    # dest -> src affine
    a = ((u1 - u0) * (y2 - y0) - (u2 - u0) * (y1 - y0)) / det
    b = ((u2 - u0) * (x1 - x0) - (u1 - u0) * (x2 - x0)) / det
    c = u0 - a * x0 - b * y0
    d = ((v1 - v0) * (y2 - y0) - (v2 - v0) * (y1 - y0)) / det
    e = ((v2 - v0) * (x1 - x0) - (v1 - v0) * (x2 - x0)) / det
    f = v0 - d * x0 - e * y0
    xs, ys = [p[0] for p in d_pts], [p[1] for p in d_pts]
    bx0, by0 = max(0, int(math.floor(min(xs))) - 1), max(0, int(math.floor(min(ys))) - 1)
    bx1, by1 = min(canvas.width, int(math.ceil(max(xs))) + 2), min(canvas.height, int(math.ceil(max(ys))) + 2)
    if bx1 <= bx0 or by1 <= by0:
        return
    w, h = bx1 - bx0, by1 - by0
    piece = src.transform((w, h), Image.AFFINE, (a, b, c + a * bx0 + b * by0, d, e, f + d * bx0 + e * by0),
                          Image.BILINEAR)
    m = Image.new('L', (w, h))
    # grow the triangle a hair so neighbouring triangles don't leave seams
    cx, cy = sum(xs) / 3, sum(ys) / 3
    poly = [(px + (px - cx) * 0.02 - bx0 + (0.5 if px > cx else -0.5),
             py + (py - cy) * 0.02 - by0 + (0.5 if py > cy else -0.5)) for px, py in d_pts]
    ImageDraw.Draw(m).polygon(poly, fill=255)
    if tint:
        piece = ImageChops.multiply(piece, Image.new('RGBA', piece.size, tint))
    piece.putalpha(ImageChops.multiply(piece.getchannel('A'), m))
    if blend == 'additive':
        base = canvas.crop((bx0, by0, bx1, by1))
        a_ = piece.getchannel('A')
        add = Image.merge('RGB', [ImageChops.multiply(ch, a_) for ch in piece.split()[:3]])
        rgb = ImageChops.add(base.convert('RGB'), add)
        rgb.putalpha(base.getchannel('A'))
        canvas.paste(rgb, (bx0, by0))
    else:
        canvas.alpha_composite(piece, (bx0, by0))


def render_setup(data, regions, size, origin, scale=1.0, skin=None, hide=(), skip_additive=False,
                 bg=None):
    """Rasterise a Spine skeleton's setup pose (regions + weighted/unweighted
    meshes, normal + additive blend). `origin` = canvas px of skeleton (0,0)."""
    canvas = bg.copy() if bg is not None else Image.new('RGBA', size)
    W = _bone_world(data['bones'])
    skins = {s['name']: s['attachments'] for s in data['skins']}
    default = skins.get('default', {})
    extra = skins.get(skin, {}) if skin else {}
    ox, oy = origin

    def to_px(x, y):
        return ox + x * scale, oy - y * scale

    for s in data['slots']:
        if s['name'] in hide or not s.get('attachment'):
            continue
        name = s['attachment']
        att = extra.get(s['name'], {}).get(name) or default.get(s['name'], {}).get(name)
        if att is None:
            continue
        rname = att.get('name', att.get('path', name))
        if rname not in regions:
            continue
        src = regions[rname]
        blend = s.get('blend')
        if blend == 'additive' and skip_additive:
            continue
        col = s.get('color')
        tint = hexc(col[:6], int(col[6:8], 16)) if col else None
        if tint and tint[3] == 0:
            continue
        bm = W[s['bone']]
        if att.get('type', 'region') == 'region':
            w, h = att['width'], att['height']
            r = math.radians(att.get('rotation', 0))
            sx, sy = att.get('scaleX', 1), att.get('scaleY', 1)
            cos, sin = math.cos(r), math.sin(r)
            corners = []
            for lx, ly in ((-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h / 2), (-w / 2, -h / 2)):
                lx, ly = lx * sx, ly * sy
                ax = att.get('x', 0) + cos * lx - sin * ly
                ay = att.get('y', 0) + sin * lx + cos * ly
                corners.append(to_px(*_apply(bm, ax, ay)))
            sw, sh = src.size
            sc = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
            _warp_tri(canvas, src, sc[:3], corners[:3], blend, tint)
            _warp_tri(canvas, src, [sc[0], sc[2], sc[3]], [corners[0], corners[2], corners[3]], blend, tint)
        elif att['type'] == 'mesh':
            uvs, verts, tris = att['uvs'], att['vertices'], att['triangles']
            n = len(uvs) // 2
            pts = []
            if len(verts) == len(uvs):
                for i in range(n):
                    pts.append(to_px(*_apply(bm, verts[2 * i], verts[2 * i + 1])))
            else:
                bones = data['bones']
                k = 0
                for _ in range(n):
                    cnt = int(verts[k]); k += 1
                    wx = wy = 0.0
                    for _ in range(cnt):
                        bi, vx, vy, wt = int(verts[k]), verts[k + 1], verts[k + 2], verts[k + 3]
                        k += 4
                        px, py = _apply(W[bones[bi]['name']], vx, vy)
                        wx += px * wt
                        wy += py * wt
                    pts.append(to_px(wx, wy))
            sw, sh = src.size
            uv = [(uvs[2 * i] * sw, uvs[2 * i + 1] * sh) for i in range(n)]
            for t in range(0, len(tris), 3):
                i0, i1, i2 = tris[t:t + 3]
                _warp_tri(canvas, src, [uv[i0], uv[i1], uv[i2]], [pts[i0], pts[i1], pts[i2]], blend, tint)
    return canvas


def wild_variant(skin):
    """Wild symbol with a multiplier skin (x2..x7), from the Spine export's setup
    pose: neutral WILD lettering (`text2`) hidden, the skin's `text` shown."""
    folder = os.path.join(ART_DIR, 'wild')
    data = json.load(open(os.path.join(folder, 'animation.json')))
    regions = atlas_regions(folder)
    ss = 3  # supersample
    im = render_setup(data, regions, (300 * ss, 300 * ss), (150 * ss, 150 * ss), scale=ss, skin=skin,
                      hide=('text2', 'blik_bolshoi'))
    return trim(im.resize((300, 300), Image.LANCZOS))


# --------------------------------------------------------------------------
# skeleton writer

class TrueColorSkel(Skel):
    """Skel whose atlas pages stay 32-bit. The kit palette-quantizes pages to 256
    colours, which contour-bands this game's big soft additive light (luchi
    burst, rays, title glow) — visibly so on the bright meadow bg."""

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
            premultiply(page).save(os.path.join(out, fname), optimize=True)
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


# --------------------------------------------------------------------------
# source art

def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), size)
    if weight:
        f.set_variation_by_axes([weight])
    return f


def symbol(code):
    return trim(Image.open(os.path.join(ART_DIR, code, 'static.png')).convert('RGBA'))


def nine_slice(src, w, h, b_src, b_dst):
    """Stretch `src` to w x h px keeping its b_src-px ornate border (drawn b_dst px)."""
    sw, sh = src.size
    out = Image.new('RGBA', (w, h))
    xs_s, xs_d = [0, b_src, sw - b_src, sw], [0, b_dst, w - b_dst, w]
    ys_s, ys_d = [0, b_src, sh - b_src, sh], [0, b_dst, h - b_dst, h]
    for i in range(3):
        for j in range(3):
            piece = src.crop((xs_s[i], ys_s[j], xs_s[i + 1], ys_s[j + 1]))
            dw, dh = xs_d[i + 1] - xs_d[i], ys_d[j + 1] - ys_d[j]
            if dw > 0 and dh > 0:
                out.alpha_composite(piece.resize((dw, dh), Image.LANCZOS), (xs_d[i], ys_d[j]))
    return out


def three_slice(src, w, h, cap_frac=0.22):
    """Horizontal plaque stretched to w x h: end caps keep their aspect."""
    k = h / src.height
    base = src.resize((max(2, round(src.width * k)), h), Image.LANCZOS)
    cap = round(base.width * cap_frac)
    out = Image.new('RGBA', (w, h))
    out.alpha_composite(base.crop((0, 0, cap, h)), (0, 0))
    out.alpha_composite(base.crop((base.width - cap, 0, base.width, h)), (w - cap, 0))
    mid = base.crop((cap, 0, base.width - cap, h)).resize((w - 2 * cap, h), Image.LANCZOS)
    out.alpha_composite(mid, (cap, 0))
    return out


def shadowed(im, r=14, dy=10, a=150):
    """Soft drop shadow under a panel (so it lifts off the bright meadow bg)."""
    pad = r * 3
    out = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad))
    sh = Image.new('L', out.size)
    sh.paste(im.getchannel('A').point(lambda v: v * a // 255), (pad, pad + dy))
    out.paste(Image.new('RGBA', out.size, hexc('0d2006')), (0, 0), sh.filter(ImageFilter.GaussianBlur(r)))
    out.alpha_composite(im, (pad, pad))
    return out, pad


def edge_fade(im):
    """Elliptical alpha falloff to exactly 0 at the region edge: the cut-out
    popup_luchi carries a faint haze to its bounds, which reads as a box when
    drawn additively at screen size."""
    g = Image.radial_gradient('L').resize(im.size)  # 0 centre -> 255 at the inscribed ellipse
    m = g.point(lambda v: int(255 * clamp(1 - v / 128) ** 1.4) if v < 128 else 0)
    out = im.copy()
    out.putalpha(ImageChops.multiply(im.getchannel('A'), m))
    return out


def soft(im, w):
    return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)


GOLD = [(0, hexc('fffbd0')), (0.45, hexc('ffd23a')), (1, hexc('f08a00'))]
CREAM = [(0, hexc('ffffff')), (1, hexc('fff0c8'))]
LIME = [(0, hexc('f6ffd0')), (0.5, hexc('b8f04a')), (1, hexc('4fae1c'))]
INK = '3a1a06'


def title(text, size, fill=GOLD, glow=None):
    return text_img(text, font('luckiest', size), fill, stroke=INK, stroke_w=max(3, size // 9),
                    glow=glow, glow_r=max(5, size // 6), shadow='1a0c02')


def lines(rows, size, fill=CREAM, gap=0.06, weight=800):
    ims = [text_img(r, font('baloo', size, weight), fill, stroke=INK, stroke_w=max(3, size // 8),
                    glow=None, shadow='1a0c02') for r in rows]
    w = max(i.width for i in ims)
    step = int(size * (1 + gap))
    h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims):
        out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


# Panel sizes (units). PANEL_PAD = shadow pad baked into the panel PNGs.
CARD_DESK = (410, 450)
CARD_MOB = (350, 405)
CHIP_DESK = (640, 150)
CHIP_MOB = (650, 150)
PANEL_PAD = {}

# Feature cards — copy matches app/seed/multi_fruits_story.py: 3x3, 3 row
# lines, only 3-of-a-kind pays; multiplier_wild variants x2/x3/x5/x7 (plain
# WILD otherwise) and several wilds on one line multiply together; 3 scatters
# = 10 free spins with every win x2 (retriggerable).
CARDS = [
    ('line', '3 IN A ROW', ['3 SAME SYMBOLS', 'ON A LINE WIN']),
    ('mwild', 'MULTI WILDS', ['WILDS LAND WITH', 'x2  x3  x5  x7']),
    ('stack', 'WILDS COMBINE', ['WILDS ON ONE LINE', 'MULTIPLY TOGETHER']),
    ('fs', 'FREE SPINS', ['3 SCATTERS = 10 SPINS', 'ALL WINS x2']),
]


def build_art():
    green = atlas_regions(os.path.join(ART_DIR, 'popup_bonus_spins_win'), restore=False)
    plate = trim(green['popup_bonus_spins_plashka_bg'])
    ART.update({
        'logo': trim(Image.open(os.path.join(ART_DIR, 'game-logo.png')).convert('RGBA')),
        'burst': edge_fade(soft(trim(green['popup_luchi']), 480)),
        'gold': trim(green['popup_mega_gold']),
        'gem': trim(green['popup_bonus_spins_diamond_bg']),
        'blik': trim(green['blik_heart2_png']),
        'plate': plate,
        'leaf': popup_region('popup_big_win', 'popup_big_win_list'),
        'clover': popup_region('popup_epic_win', 'popup_epic_list1'),
        'ruby': popup_region('popup_epic_win', 'popup_epic_bg'),
        'glow': soft_glow(256),
        'rays': rays(560, n=16, col=(255, 236, 150)),
    })
    for code in ('777', 'bell', 'diamond', 'klubnika', 'limon', 'grusha', 'vinograd', 'scatter', 'wild'):
        ART[code] = symbol(code)
    for m in ('x2', 'x3', 'x5', 'x7'):
        ART[f'wild_{m}'] = wild_variant(m)
    ART['logo_flash'] = flash_of(ART['logo'], 0.9)
    ART['scatter_flash'] = flash_of(ART['scatter'], 0.8)

    plaque = popup_region('popup_big_win', 'popup_big_win_plashka')
    for key, (w, h) in (('card_desk', CARD_DESK), ('card_mob', CARD_MOB)):
        ART[key], PANEL_PAD[key] = shadowed(nine_slice(plate, w, h, 92, 62))
    for key, (w, h) in (('chip_desk', CHIP_DESK), ('chip_mob', CHIP_MOB)):
        ART[key], PANEL_PAD[key] = shadowed(three_slice(plaque, w, h))
    ART['plate_big'], PANEL_PAD['plate_big'] = shadowed(plate, r=18, dy=12)

    for key, head, desc in CARDS:
        ART[f't_{key}'] = title(head, 60)
        ART[f'd_{key}'] = lines(desc, 38)
    ART['t_eq'] = title('= x15', 64, fill=LIME)
    ART['tap_continue'] = title('TAP TO CONTINUE', 58, fill=CREAM, glow='ffd23a')
    ART['tap_start'] = title('TAP TO START', 64, fill=CREAM, glow='ffd23a')
    ART['t_free_spins'] = title('FREE SPINS', 150, glow='fff3a0')
    ART['t_you_won'] = title('YOU HAVE WON', 64, fill=LIME)
    ART['d_chip_x2'] = lines(['EVERY WIN IN THE', 'BONUS PAYS DOUBLE'], 40)
    ART['d_chip_fs'] = lines(['3 SCATTERS AGAIN', 'GIVE +10 SPINS'], 40)


# --------------------------------------------------------------------------
# motion helpers (all idle offsets are 0 at t=0 so idle starts where intro ends)

def bob(t, amp, period=IDLE, phase=0.0):
    return amp * (wave(t, period, phase) - wave(0, period, phase))


def pop(t, t0, dur=0.55, s0=0.3):
    return seg(t, t0, t0 + dur, s0, 1.0, out_back)


def fade(t, t0, dur=0.3):
    return seg(t, t0, t0 + dur, 0.0, 1.0, out_cubic)


def move(sk, bone, intro_fn, idle_fn):
    """Translate as an offset from the bone's setup position (the kit wants the
    absolute local position, so the setup x/y is added back)."""
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


def panel_slot(sk, name, bone, key, w):
    """Slot for a shadow-padded panel PNG whose body is `w` units wide."""
    body_w = ART[key].width - 2 * PANEL_PAD[key]
    return sk.slot(name, bone, key, w=w * ART[key].width / body_w)


def twinkles(sk, parent, spots, seed, start=1.4, tint='fff6c8ff'):
    """Additive blik sparkles blinking out of phase; seamless over IDLE."""
    rnd = random.Random(seed)
    for i, (x, y, s) in enumerate(spots):
        b = sk.bone(f'tw{i}', parent, x, y)
        sk.slot(f'tw{i}', b, 'blik', w=110 * s, blend='additive', color=tint)
        ph = rnd.random()
        per = rnd.choice((1.0, 2.0, 4.0))

        def blink(tau, ph=ph, per=per):
            return math.sin(math.pi * (((tau / per) + ph) % 1.0)) ** 4

        env = lambda t: clamp((t - start) / 0.6)  # noqa: E731
        sk.both(b, 'scale', uniform(lambda t, f=blink: 0.3 + 0.9 * f(t - INTRO) * env(t)),
                uniform(lambda t, f=blink: 0.3 + 0.9 * f(t)))
        sk.both(b, 'rotate', lambda t: 90 * (t - INTRO) / IDLE, lambda t: 90 * t / IDLE)
        sk.both(f'tw{i}', 'alpha', lambda t, f=blink: f(t - INTRO) * env(t), lambda t, f=blink: f(t))


def light_burst(sk, name, parent, x, y, w, t0=0.0, alpha=0.8, rays_w=None, rays_alpha=0.32):
    """popup_luchi burst (breathing) + slowly turning rays behind it."""
    rw = rays_w or w * 0.75
    rb = sk.bone(f'{name}_rays', parent, x, y)
    sk.slot(f'{name}_rays', rb, 'rays', w=rw, blend='additive', color='ffe9a0ff')
    sk.both(rb, 'rotate', lambda t: -22.5 * (t - INTRO) / IDLE, lambda t: -22.5 * t / IDLE)
    sk.both(rb, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.8, 0.4, 1.0)), uniform(lambda t: 1))
    sk.both(f'{name}_rays', 'alpha', lambda t: rays_alpha * fade(t, t0, 0.6),
            lambda t: rays_alpha * (1 - 0.3 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))
    b = sk.bone(name, parent, x, y)
    sk.slot(name, b, 'burst', w=w, blend='additive')
    sk.both(b, 'scale', uniform(lambda t: seg(t, t0, t0 + 0.7, 0.3, 1.0)), uniform(lambda t: breathe(t, 2.0, 0.05)))
    sk.both(name, 'alpha', lambda t: alpha * fade(t, t0, 0.5),
            lambda t: alpha * (1 - 0.18 * (1 - math.cos(2 * math.pi * t / 2.0)) / 2))


def floater(sk, name, region, parent, x, y, w, t0, amp=10, period=IDLE, phase=0.0, rot_amp=0.0,
            slide=(0, -40), alpha=1.0, rot=0.0):
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


def tap_hint(sk, region, y, w):
    b = sk.bone('tap', 'root', 0, y)
    sk.slot('tap', b, region, w=w)
    sk.both(b, 'scale', uniform(lambda t: seg(t, 2.2, 2.7, 0.8, 1.0, out_back)), uniform(lambda t: breathe(t, 2.0, 0.04)))
    sk.both('tap', 'alpha', lambda t: fade(t, 2.2, 0.5),
            lambda t: 0.775 + 0.225 * math.cos(2 * math.pi * t / 2.0))


# --------------------------------------------------------------------------
# feature (preview) screen

def card_icons(sk, key, parent, t0, s):
    """Card illustration centred on `parent`; s = icon scale."""
    if key == 'line':
        for i, (code, x) in enumerate((('777', -112), ('bell', 0), ('diamond', 112))):
            b = sk.bone(f'{key}_i{i}', parent, x * s, 0)
            sk.slot(f'{key}_i{i}', b, code, w=104 * s)
            d = t0 + 0.12 * i
            sk.both(b, 'scale', uniform(lambda t, d=d: pop(t, d, 0.5, 0.0)),
                    uniform(lambda t, i=i: 1 + 0.1 * pulse(t, 2.0, 0.1 + i * 0.12, 6)))
            # reels landing: each symbol drops in from above
            move(sk, b, lambda t, d=d: (0, seg(t, d, d + 0.45, 80 * s, 0, out_back)),
                 lambda t: (0, 0))
    elif key == 'mwild':
        for i, m in enumerate(('x2', 'x3', 'x5', 'x7')):
            col, row = i % 2, i // 2
            b = sk.bone(f'{key}_i{i}', parent, (col - 0.5) * 118 * s, (0.5 - row) * 98 * s)
            sk.slot(f'{key}_i{i}', b, f'wild_{m}', w=(100 + 4 * i) * s)
            sk.both(b, 'scale', uniform(lambda t, d=t0 + 0.08 * i: pop(t, d, 0.45, 0.0)),
                    uniform(lambda t, i=i: 1 + 0.12 * pulse(t, 2.0, i * 0.12, 6)))
            sk.both(b, 'rotate', lambda t: 0, lambda t, i=i: bob(t, 6, 2.0, i * 0.25))
    elif key == 'stack':
        g = sk.bone(f'{key}_glow', parent, 0, 18 * s)
        sk.slot(f'{key}_glow', g, 'glow', w=300 * s, blend='additive', color='c8ff6aff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.12)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.45 * fade(t, t0), lambda t: 0.45)
        for i, (m, x) in enumerate((('x3', -62), ('x5', 62))):
            b = sk.bone(f'{key}_i{i}', parent, x * s, 28 * s)
            sk.slot(f'{key}_i{i}', b, f'wild_{m}', w=118 * s)
            d = t0 + 0.15 * i
            sk.both(b, 'scale', uniform(lambda t, d=d: pop(t, d, 0.5, 0.0)),
                    uniform(lambda t: 1 + 0.08 * pulse(t, 2.0, 0.35, 6)))
            # the two wilds slide in towards each other
            move(sk, b, lambda t, d=d, x=x: (seg(t, d, d + 0.5, x * 0.8 * s, 0), 0),
                 lambda t, i=i: (0, bob(t, 5 * s, 2.0, i * 0.5)))
        e = sk.bone(f'{key}_eq', parent, 0, -66 * s)
        sk.slot(f'{key}_eq', e, 't_eq', w=150 * s)
        sk.both(e, 'scale', uniform(lambda t: pop(t, t0 + 0.55, 0.5, 0.0)),
                uniform(lambda t: 1 + 0.14 * pulse(t, 2.0, 0.4, 6)))
    elif key == 'fs':
        g = sk.bone(f'{key}_glow', parent, 0, 0)
        sk.slot(f'{key}_glow', g, 'glow', w=280 * s, blend='additive', color='ffe27aff')
        sk.both(g, 'scale', uniform(lambda t: pop(t, t0, 0.5, 0.0)), uniform(lambda t: breathe(t, 2.0, 0.15)))
        sk.both(f'{key}_glow', 'alpha', lambda t: 0.6 * fade(t, t0), lambda t: 0.6)
        b = sk.bone(f'{key}_i0', parent)
        sk.slot(f'{key}_i0', b, 'scatter', w=190 * s)
        fl = sk.slot(f'{key}_fl', b, 'scatter_flash', w=190 * s, blend='additive', color='ffffff00')
        sk.both(b, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.0)), uniform(lambda t: 1))
        sk.both(b, 'rotate', lambda t: 0, lambda t: bob(t, 5, IDLE, 0.25))
        move(sk, b, lambda t: (0, 0), lambda t: (0, bob(t, 8 * s, 2.0)))
        sk.both(fl, 'alpha', lambda t: 0, lambda t: 0.5 * pulse(t, 4.0, 0.5, 8))


def feature_card(sk, idx, key, x, y, panel, pw, ph, t0, s):
    c = sk.bone(f'card{idx}', 'root', x, y)
    panel_slot(sk, f'card{idx}', c, panel, pw)
    sk.both(c, 'scale', uniform(lambda t: pop(t, t0, 0.55, 0.4)), uniform(lambda t: 1))
    move(sk, c, lambda t: (0, seg(t, t0, t0 + 0.55, -70, 0)),
         lambda t: (0, bob(t, 5, IDLE, idx * 0.25)))
    sk.both(f'card{idx}', 'alpha', lambda t: fade(t, t0, 0.25), lambda t: 1)

    ti, di = ART[f't_{key}'], ART[f'd_{key}']
    inner = pw - 96  # the gold frame eats ~48 units a side
    t_w = min(ti.width * 0.9 * s, inner)
    d_w = min(di.width * 0.82 * s, inner)
    t_y = ph * 0.5 - 70 * s
    d_y = -ph * 0.5 + 76 * s
    tb = sk.bone(f'card{idx}_t', c, 0, t_y)
    sk.slot(f'card{idx}_t', tb, f't_{key}', w=t_w)
    sk.both(f'card{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.15), lambda t: 1)

    gap_top = t_y - t_w * ti.height / ti.width / 2
    gap_bot = d_y + d_w * di.height / di.width / 2
    ib = sk.bone(f'card{idx}_icon', c, 0, (gap_top + gap_bot) / 2)
    card_icons(sk, key, ib, t0 + 0.25, s)

    db = sk.bone(f'card{idx}_d', c, 0, d_y)
    sk.slot(f'card{idx}_d', db, f'd_{key}', w=d_w)
    sk.both(f'card{idx}_d', 'alpha', lambda t: fade(t, t0 + 0.3), lambda t: 1)


def build_feature(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = TrueColorSkel(f'feature_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    panel = f'card_{variant}'
    add_art(sk, 'logo', 'logo_flash', 'burst', 'rays', 'glow', 'blik', 'leaf', 'clover', 'gem', 'tap_continue',
            '777', 'bell', 'diamond', 'scatter', 'scatter_flash', 'wild_x2', 'wild_x3', 'wild_x5', 'wild_x7',
            't_eq', panel, *[f't_{k}' for k, _, _ in CARDS], *[f'd_{k}' for k, _, _ in CARDS])

    if variant == 'desk':
        logo_y, logo_w = 295, 390
        pw, ph = CARD_DESK
        cards = [(-690 + 460 * i, -110) for i in range(4)]
        s = 1.0
        tap_y, tap_w = -408, 430
        deco = [('leaf', -560, 330, 150, 0.1, 20), ('clover', 600, 320, 110, 0.6, -10),
                ('gem', 820, 360, 110, 0.35, 0), ('leaf', 900, 150, 110, 0.8, -150)]
        spots = [(-330, 400, 0.8), (320, 390, 1.0), (-860, 330, 0.7), (720, 220, 0.6), (-240, 210, 0.5),
                 (250, 230, 0.6), (-930, -60, 0.6), (930, -130, 0.7), (0, -430, 0.5)]
    else:
        logo_y, logo_w = 545, 360
        pw, ph = CARD_MOB
        cards = [(-188, 162), (188, 162), (-188, -258), (188, -258)]
        s = 0.86
        tap_y, tap_w = -560, 420
        deco = [('leaf', -300, 640, 110, 0.1, 20), ('clover', 300, 610, 90, 0.6, -10),
                ('gem', -300, 420, 70, 0.35, 0)]
        spots = [(-250, 680, 0.7), (230, 470, 0.8), (-330, 470, 0.5), (340, -40, 0.6), (-340, -470, 0.6),
                 (300, -640, 0.5), (0, 690, 0.5)]

    light_burst(sk, 'burst', 'root', 0, logo_y - 10, logo_w * 2.6, t0=0.0, alpha=0.55, rays_alpha=0.22)
    for i, (region, x, y, dw, ph_, rot) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=12, phase=ph_, rot_amp=7, rot=rot)

    lb = sk.bone('logo', 'root', 0, logo_y)
    sk.slot('logo', lb, 'logo', w=logo_w)
    sk.slot('logo_flash', lb, 'logo_flash', w=logo_w, blend='additive', color='ffffff00')
    sk.both(lb, 'scale', uniform(lambda t: seg(t, 0.15, 0.85, 0.2, 1.0, out_back)),
            uniform(lambda t: breathe(t, IDLE, 0.025)))
    move(sk, lb, lambda t: (0, 0), lambda t: (0, bob(t, 6)))
    sk.both('logo', 'alpha', lambda t: fade(t, 0.15, 0.25), lambda t: 1)
    sk.both('logo_flash', 'alpha', lambda t: seg(t, 0.6, 1.1, 0.85, 0.0) if t >= 0.6 else 0,
            lambda t: 0.35 * pulse(t, IDLE, 0.55, 10))

    for i, ((x, y), (key, _, _)) in enumerate(zip(cards, CARDS)):
        feature_card(sk, i, key, x, y, panel, pw, ph, 0.75 + 0.18 * i, s)

    twinkles(sk, 'root', spots, seed=7)
    tap_hint(sk, 'tap_continue', tap_y, tap_w)
    sk.write()


# --------------------------------------------------------------------------
# bonus screen

def info_chip(sk, idx, panel, icon, text, x, y, cw, t0, from_x, icon_w):
    """Wooden plaque with an icon + 2-line caption."""
    c = sk.bone(f'chip{idx}', 'root', x, y)
    panel_slot(sk, f'chip{idx}', c, panel, cw)
    sk.both(f'chip{idx}', 'alpha', lambda t: fade(t, t0, 0.4), lambda t: 1)
    move(sk, c, lambda t: (seg(t, t0, t0 + 0.6, from_x, 0), 0), lambda t: (0, bob(t, 4, IDLE, idx * 0.5)))
    inner = cw - 150  # ornate end caps
    tw_ = min(ART[text].width * 0.8, inner - icon_w - 24)
    gap = 24
    total = icon_w + gap + tw_
    ib = sk.bone(f'chip{idx}_i', c, -total / 2 + icon_w / 2, 4)
    sk.slot(f'chip{idx}_i', ib, icon, w=icon_w)
    sk.both(ib, 'scale', uniform(lambda t: pop(t, t0 + 0.3, 0.5, 0.0)),
            uniform(lambda t: 1 + 0.1 * pulse(t, 2.0, idx * 0.25, 6)))
    sk.both(ib, 'rotate', lambda t: 0, lambda t: bob(t, 7, 2.0, idx * 0.5))
    tb = sk.bone(f'chip{idx}_t', c, total / 2 - tw_ / 2, 0)
    sk.slot(f'chip{idx}_t', tb, text, w=tw_)
    sk.both(f'chip{idx}_t', 'alpha', lambda t: fade(t, t0 + 0.25, 0.4), lambda t: 1)


def build_bonus(variant):
    w, h = DESK if variant == 'desk' else MOB
    sk = TrueColorSkel(f'bonus_{variant}', w, h, res=1.0, out_dir=OUT, intro=INTRO, idle=IDLE)
    panel = f'chip_{variant}'
    add_art(sk, 'burst', 'rays', 'glow', 'blik', 'gold', 'plate_big', 'leaf', 'clover', 'gem', 'ruby',
            'klubnika', 'limon', 'grusha', 'vinograd', 'wild_x2', 'wild_x7', 'scatter',
            't_free_spins', 't_you_won', 'd_chip_x2', 'd_chip_fs', 'tap_start', panel)

    if variant == 'desk':
        won_y, title_y, title_w = 405, 268, 720
        plate_y, plate_w = 35, 360
        gold_y, gold_w = -82, 560
        cw = CHIP_DESK[0]
        chips = [(-345, -248, -300), (345, -248, 300)]
        chip_icon = 112
        tap_y, tap_w = -408, 420
        fruits = [('klubnika', -560, 150, 150, 0.0, 8), ('limon', 560, 160, 140, 0.4, -8),
                  ('grusha', -760, -40, 130, 0.7, -6), ('vinograd', 770, -30, 140, 0.2, 6)]
        deco = [('leaf', -820, 340, 150, 0.1, 20), ('clover', 820, 330, 110, 0.6, -12),
                ('gem', -420, 380, 90, 0.35, 0), ('ruby', 440, 390, 80, 0.85, 0),
                ('leaf', 880, -330, 110, 0.5, -150)]
        spots = [(-480, 330, 0.8), (480, 340, 0.9), (-880, -280, 0.7), (870, -260, 0.6), (-200, 140, 0.5),
                 (210, -40, 0.5), (0, 445, 0.5)]
    else:
        won_y, title_y, title_w = 600, 472, 640
        plate_y, plate_w = 200, 380
        gold_y, gold_w = 72, 560
        cw = CHIP_MOB[0]
        chips = [(0, -140, -420), (0, -320, 420)]
        chip_icon = 112
        tap_y, tap_w = -560, 420
        fruits = [('klubnika', -300, 330, 120, 0.0, 8), ('limon', 300, 330, 110, 0.4, -8),
                  ('grusha', -290, -460, 110, 0.7, -6), ('vinograd', 290, -460, 120, 0.2, 6)]
        deco = [('leaf', -310, 650, 110, 0.1, 20), ('clover', 310, 640, 90, 0.6, -12),
                ('gem', 0, -455, 80, 0.35, 0)]
        spots = [(-300, 560, 0.6), (300, 540, 0.7), (-340, 140, 0.5), (340, 20, 0.6), (-300, -600, 0.5),
                 (300, -650, 0.5)]

    light_burst(sk, 'burst', 'root', 0, plate_y + 30, plate_w * 3.4, t0=0.5, alpha=0.6, rays_w=plate_w * 3.0,
                rays_alpha=0.22)

    for i, (region, x, y, dw, ph_, rot) in enumerate(fruits):
        floater(sk, f'fruit{i}', region, 'root', x, y, dw, 0.4 + 0.12 * i, amp=12, phase=ph_, rot_amp=6,
                rot=rot, slide=(-80 if x < 0 else 80, 0))
    for i, (region, x, y, dw, ph_, rot) in enumerate(deco):
        floater(sk, f'deco{i}', region, 'root', x, y, dw, 0.5 + 0.15 * i, amp=12, phase=ph_, rot_amp=7, rot=rot)

    # "YOU HAVE WON" drops in, "FREE SPINS" slams down with a flash
    yb = sk.bone('won', 'root', 0, won_y)
    sk.slot('won', yb, 't_you_won', w=title_w * 0.52)
    move(sk, yb, lambda t: (0, seg(t, 0.2, 0.7, 50, 0)), lambda t: (0, 0))
    sk.both('won', 'alpha', lambda t: fade(t, 0.2, 0.4), lambda t: 1)

    tb = sk.bone('title', 'root', 0, title_y)
    sk.slot('title', tb, 't_free_spins', w=title_w)
    sk.image('t_free_spins_flash', flash_of(ART['t_free_spins'], 0.9))
    sk.slot('title_flash', tb, 't_free_spins_flash', w=title_w, blend='additive', color='ffffff00')

    def slam(t):
        return seg(t, 0.35, 0.8, 2.2, 0.94, out_cubic) if t < 0.8 else seg(t, 0.8, 1.05, 0.94, 1.0, out_back)

    sk.both(tb, 'scale', uniform(slam), uniform(lambda t: breathe(t, 2.0, 0.025)))
    sk.both('title', 'alpha', lambda t: fade(t, 0.35, 0.2), lambda t: 1)
    sk.both('title_flash', 'alpha', lambda t: seg(t, 0.8, 1.3, 0.9, 0.0) if t >= 0.8 else 0,
            lambda t: 0.35 * pulse(t, IDLE, 0.5, 10))

    # gold pile spills out under the plate
    gb = sk.bone('gold', 'root', 0, gold_y)
    sk.slot('gold', gb, 'gold', w=gold_w)
    sk.both(gb, 'scale', lambda t: (seg(t, 1.1, 1.6, 0.3, 1.0, out_back), seg(t, 1.1, 1.6, 0.1, 1.0, out_back)),
            uniform(lambda t: 1))
    sk.both('gold', 'alpha', lambda t: fade(t, 1.1, 0.25), lambda t: 1)

    # counter plate (the live spin count is a DOM overlay glued to bone "count")
    pb = sk.bone('plate', 'root', 0, plate_y)
    panel_slot(sk, 'plate', pb, 'plate_big', plate_w)
    sk.bone('count', pb, 0, 0)
    sk.both(pb, 'scale', uniform(lambda t: pop(t, 1.0, 0.6, 0.0)),
            uniform(lambda t: 1 + 0.04 * pulse(t, 2.0, 0.0, 6)))
    sk.both('plate', 'alpha', lambda t: fade(t, 1.0, 0.2), lambda t: 1)

    (x0, y0, f0), (x1, y1, f1) = chips
    info_chip(sk, 0, panel, 'wild_x2', 'd_chip_x2', x0, y0, cw, 1.6, f0, chip_icon)
    info_chip(sk, 1, panel, 'scatter', 'd_chip_fs', x1, y1, cw, 1.75, f1, chip_icon)

    twinkles(sk, 'root', spots, seed=11)
    tap_hint(sk, 'tap_start', tap_y, tap_w)
    sk.write()


if __name__ == '__main__':
    FONTS = sys.argv[1]
    OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ART_DIR, 'screens')
    build_art()
    for v in ('desk', 'mob'):
        build_feature(v)
        build_bonus(v)
