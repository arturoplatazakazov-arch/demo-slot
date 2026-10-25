"""Gangsta Casino bonus backgrounds as lean generated Spine 4.1 skeletons —
desktop (bg_bonus_desk.jpg, 1932x940) and portrait (the club photo of
bonus_bg_mob_v3, 800x1463):

- the photo (region, page 2);
- the club spotlights' beams + lamp glows, the same placement / colours /
  motion as the bonus screen's (bonus_screen_v4), but resampled to a key
  every 0.5 s with smooth bezier handles instead of 30 keys a second
  (product: «просто лучи, чтоб много не весила»);
- the heroine on the sofa: a weighted mesh over a crop of the same photo
  (borders pinned, so at rest it is the photo pixel for pixel), bound to an
  `arm` bone at the sofa's foot. `idle` = she breathes 2 % bigger and back
  (4 s loop), `win` (1.3 s) = one such pulse. Beams run in both clips,
  45 % brighter than the bonus screen's.

Usage: python scripts/gc_bonus_bg.py <out_root>  -> <out_root>/bonus_bg, bonus_bg_mob
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, '..', 'front', 'img', 'gangsta-casino')
OUT_ROOT = sys.argv[1]

# The heroine on her sofa, DESKTOP photo px (product: no hand wave — the
# whole figure breathes 2 % bigger and back): polygon of woman + sofa (the
# side table with the champagne stays out), scale pivot = the sofa's foot.
ARM_POLY = [(1610, 325), (1700, 330), (1760, 420), (1850, 470), (1850, 580), (1745, 640), (1700, 700), (1690, 830),
            (1640, 900), (1300, 885), (1272, 800), (1266, 700), (1290, 610), (1440, 540), (1500, 460), (1560, 395)]
ELBOW = (1500, 880)
FACE_X = None
CROP = (1226, 296, 1886, 936)
FALL = 30.0
# portrait photo = the same art: mob = (518, 823) + (desk - (1500, 380)) * 0.765
def to_mob(x, y): return (518 + (x - 1500) * 0.765, 823 + (y - 380) * 0.765)

def bezier_keys(samples, step=0.5):
    """[(t, v)] dense samples -> sparse keys with smooth (Catmull-Rom) bezier
    handles in 4.1 JSON form (absolute time / value)."""
    ts = np.array([t for t, _ in samples]); vs = np.array([v for _, v in samples])
    T = ts[-1]
    kt = list(np.arange(0, T + 1e-6, step))
    if abs(kt[-1] - T) > 1e-6: kt.append(T)
    kv = [float(np.interp(t, ts, vs)) for t in kt]
    n = len(kt)
    looped = abs(kv[0] - kv[-1]) < 1e-6
    def slope(i):
        if 0 < i < n - 1: return (kv[i + 1] - kv[i - 1]) / (kt[i + 1] - kt[i - 1])
        if looped: return (kv[1] - kv[-2]) / (kt[1] - kt[0] + kt[-1] - kt[-2])
        return 0.0
    keys = []
    for i in range(n):
        k = {'time': round(kt[i], 4), 'v': round(kv[i], 4)}
        if i < n - 1:
            dt = kt[i + 1] - kt[i]
            k['curve'] = [round(kt[i] + dt / 3, 4), round(kv[i] + slope(i) * dt / 3, 4),
                          round(kt[i + 1] - dt / 3, 4), round(kv[i + 1] - slope(i + 1) * dt / 3, 4)]
        keys.append(k)
    return keys

def ease_keys(pts):
    """[(t, v)] -> keys with ease-in-out handles between them (a stop at each key)."""
    out = []
    for i, (t, v) in enumerate(pts):
        k = {'time': t, 'v': v}
        if i + 1 < len(pts):
            t1, v1 = pts[i + 1]; d = t1 - t
            k['curve'] = [round(t + d * 0.45, 4), v, round(t1 - d * 0.45, 4), v1]
        out.append(k)
    return out

def rotate_tl(keys):
    return [dict({'time': k['time'], 'value': k['v']}, **({'curve': k['curve']} if 'curve' in k else {})) for k in keys]

def rgba_tl(rgb, keys):
    out = []
    for k in keys:
        a = max(0, min(255, round(k['v'] * 255)))
        e = {'time': k['time'], 'color': f'{rgb}{a:02x}'}
        if 'curve' in k:
            c = k['curve']; ch = [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            e['curve'] = sum(([c[0], round(v, 4), c[2], round(v, 4)] for v in ch), []) + [c[0], c[1], c[2], c[3]]
        out.append(e)
    return out

def beam_set(src_json, box_w, box_h, beam_parent_offset=(0, 0), origins=None):
    """Beams + lamps of a donor skeleton: bones, slots, attachments, resampled idle."""
    J = json.load(open(src_json))
    bones = {b['name']: b for b in J['bones']}
    sk = J['skins'][0]['attachments']
    idle = J['animations']['idle']
    names = sorted({b['name'] for b in J['bones'] if b['name'].startswith('beam')}, key=lambda s: int(s[4:]))
    out_b, out_s, out_a, tl_b, tl_s = [], [], {}, {}, {}
    for bi, n in enumerate(names):
        b = bones[n]
        if origins:  # the beam starts in this photo's own lamp head (photo px)
            ox, oy = origins[bi]
            out_b.append({'name': n, 'parent': 'root', 'x': ox - box_w / 2, 'y': box_h / 2 - oy})
        else:
            out_b.append({'name': n, 'parent': 'root', 'x': b['x'] + beam_parent_offset[0], 'y': b['y'] + beam_parent_offset[1]})
        for sn in (n, 'lamp' + n[4:]):
            slot = next(s for s in J['slots'] if s['name'] == sn)
            out_s.append(dict(slot, bone=n))
            out_a[sn] = sk[sn]
            rg = idle['slots'][sn]['rgba']
            samples = [(k.get('time', 0), min(1.0, int(k['color'][6:], 16) / 255 * BEAM_BOOST)) for k in rg]
            tl_s[sn] = {'rgba': rgba_tl(slot['color'][:6], bezier_keys(samples))}
        rot = idle['bones'][n]['rotate']
        samples = [(k.get('time', 0), k.get('value', 0)) for k in rot]
        tl_b[n] = {'rotate': rotate_tl(bezier_keys(samples))}
    # rest pose = the clip's first frame (so the static is the scene as it plays)
    for b in out_b:
        b['rotation'] = tl_b[b['name']]['rotate'][0]['value']
    for s in out_s:
        s['color'] = tl_s[s['name']]['rgba'][0]['color']
    # the timeline is relative to the setup rotation in 4.x: subtract it
    for b in out_b:
        r0 = b['rotation']
        for k in tl_b[b['name']]['rotate']:
            k['value'] = round(k['value'] - r0, 4)
            if 'curve' in k: k['curve'][1] = round(k['curve'][1] - r0, 4); k['curve'][3] = round(k['curve'][3] - r0, 4)
    return out_b, out_s, out_a, tl_b, tl_s, J

def point_in_poly(x, y, poly):
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: inside = not inside
    return inside

def seg_dist(px, py, poly):
    d = 1e9
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = x2 - x1, y2 - y1
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        d = min(d, math.hypot(px - x1 - t * dx, py - y1 - t * dy))
    return d

def arm_mesh(photo, crop, poly, elbow, face_x, fall, W, H, step):
    """Weighted grid mesh over `crop` of the photo, skeleton coords (y up,
    origin = photo centre). Returns (crop image, attachment dict, elbow bone xy)."""
    x0, y0, x1, y1 = crop
    img = photo.crop((int(x0), int(y0), int(x1), int(y1)))
    cw, ch = img.size
    nx, ny = max(2, round(cw / step)) + 1, max(2, round(ch / step)) + 1
    gx = [x0 + cw * i / (nx - 1) for i in range(nx)]
    gy = [y0 + ch * j / (ny - 1) for j in range(ny)]
    ex, ey = elbow[0] - W / 2, H / 2 - elbow[1]
    # vertex order: hull loop first, then the interior
    hull = [(i, 0) for i in range(nx)] + [(nx - 1, j) for j in range(1, ny)] + \
           [(i, ny - 1) for i in range(nx - 2, -1, -1)] + [(0, j) for j in range(ny - 2, 0, -1)]
    inner = [(i, j) for j in range(1, ny - 1) for i in range(1, nx - 1)]
    order = hull + inner
    index = {p: k for k, p in enumerate(order)}
    verts, uvs = [], []
    for (i, j) in order:
        px, py = gx[i], gy[j]
        w = 0.0
        if 0 < i < nx - 1 and 0 < j < ny - 1:
            d = 0 if point_in_poly(px, py, poly) else seg_dist(px, py, poly)
            w = 1.0 if d == 0 else max(0.0, 1 - d / fall)
            w = w * w * (3 - 2 * w)  # smoothstep
            if face_x:
                fx = (px - face_x[0]) / (face_x[1] - face_x[0])
                w *= 1 - max(0.0, min(1.0, fx))
        sx, sy = px - W / 2, H / 2 - py
        if w <= 0.001:
            verts += [1, 0, round(sx, 3), round(sy, 3), 1]
        elif w >= 0.999:
            verts += [1, 1, round(sx - ex, 3), round(sy - ey, 3), 1]
        else:
            verts += [2, 0, round(sx, 3), round(sy, 3), round(1 - w, 4), 1, round(sx - ex, 3), round(sy - ey, 3), round(w, 4)]
        uvs += [round((px - x0) / cw, 5), round((py - y0) / ch, 5)]
    tris = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = index[(i, j)], index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]
            tris += [a, b, c, a, c, d]
    att = {'type': 'mesh', 'uvs': uvs, 'triangles': tris, 'vertices': verts, 'hull': len(hull),
           'width': cw, 'height': ch}
    return img, att, (ex, ey)

HERO_IDLE = [(0, 1), (2.0, 1.02), (4.0, 1)]    # scale, 4 s loop
HERO_WIN = [(0, 1), (0.5, 1.02), (1.3, 1)]      # one pulse, 1.3 s
BEAM_BOOST = 1.45  # «ярче светить стробоскопами»: beam / lamp alpha x this (capped)

def build(name, photo_path, W, H, beams_src, poly, elbow, face_x, crop, fall, step, origins=None):
    out = os.path.join(OUT_ROOT, name)
    os.makedirs(out, exist_ok=True)
    photo = Image.open(photo_path).convert('RGB')
    bb, bs, ba, tlb, tls, _ = beam_set(beams_src, W, H, origins=origins)
    arm_img, arm_att, (ex, ey) = arm_mesh(photo, crop, poly, elbow, face_x, fall, W, H, step)
    # atlas page 1: beam + glow textures (from the donor page) + the arm crop
    donor_dir = os.path.dirname(beams_src)
    donor_atlas = open(os.path.join(donor_dir, 'animation.atlas')).read()
    donor_page = Image.open(os.path.join(donor_dir, 'animation.png')).convert('RGBA')
    pma = 'pma:true' in donor_atlas.split('\n\n')[0]
    regions = {}
    for block in donor_atlas.split('\n'):
        pass
    import re
    for m in re.finditer(r'^(fx/beam|fx/glow_soft)\n\s*bounds:(\d+),(\d+),(\d+),(\d+)(\n\s*offsets:([\d,]+))?', donor_atlas, re.M):
        regions[m.group(1)] = (tuple(int(v) for v in m.group(2, 3, 4, 5)), m.group(7))
    tiles = [(n, donor_page.crop((x, y, x + w, y + h)), off) for n, ((x, y, w, h), off) in regions.items()]
    if pma:  # back to straight alpha: this skeleton's page is straight
        fixed = []
        for n, im, off in tiles:
            a = np.asarray(im).astype(np.float64); al = a[..., 3:4] / 255
            a[..., :3] = np.where(al > 0, a[..., :3] / np.maximum(al, 1e-6), 0)
            fixed.append((n, Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), off))
        tiles = fixed
    tiles.append(('arm', arm_img.convert('RGBA'), None))
    pw = sum(t[1].width + 2 for t in tiles); ph = max(t[1].height for t in tiles)
    page = Image.new('RGBA', (pw, ph)); x = 0
    lines = ['animation.png', f'size:{pw},{ph}', 'filter:Linear,Linear']
    for n, im, off in tiles:
        page.paste(im, (x, 0)); lines += [n, f'bounds:{x},0,{im.width},{im.height}'] + ([f'offsets:{off}'] if off else []); x += im.width + 2
    page.save(os.path.join(out, 'animation.png'), optimize=True)
    photo.save(os.path.join(out, 'animation-p2.png'), optimize=True)
    lines += ['', 'animation-p2.png', f'size:{W},{H}', 'filter:Linear,Linear', 'bg', f'bounds:0,0,{W},{H}', '']
    open(os.path.join(out, 'animation.atlas'), 'w').write('\n'.join(lines))
    bones = [{'name': 'root'}, {'name': 'arm', 'parent': 'root', 'x': round(ex, 2), 'y': round(ey, 2)}] + bb
    slots = [{'name': 'bg', 'bone': 'root', 'attachment': 'bg'}, {'name': 'arm', 'bone': 'root', 'attachment': 'arm'}] + bs
    skin = {'bg': {'bg': {'width': W, 'height': H}}, 'arm': {'arm': arm_att}}
    skin.update({s: {list(a)[0]: list(a.values())[0]} for s, a in ba.items()})
    def scale_tl(keys):
        out = []
        for k in keys:
            e = {'time': k['time'], 'x': k['v'], 'y': k['v']}
            if 'curve' in k: e['curve'] = k['curve'] + k['curve']
            out.append(e)
        return out
    idle = {'bones': dict(tlb, arm={'scale': scale_tl(ease_keys(HERO_IDLE))}), 'slots': tls}
    # win: the beams keep running (their first 1.3 s), the hand waves
    def cut(tl, T):
        return [k for k in tl if k['time'] <= T + 1e-6]
    win = {'bones': {n: {'rotate': cut(v['rotate'], 1.3)} for n, v in tlb.items()}, 'slots': {n: {'rgba': cut(v['rgba'], 1.3)} for n, v in tls.items()}}
    win['bones']['arm'] = {'scale': scale_tl(ease_keys(HERO_WIN))}
    J = {'skeleton': {'spine': '4.1.24', 'x': -W / 2, 'y': -H / 2, 'width': W, 'height': H},
         'bones': bones, 'slots': slots, 'skins': [{'name': 'default', 'attachments': skin}],
         'animations': {'idle': idle, 'win': win}}
    json.dump(J, open(os.path.join(out, 'animation.json'), 'w'), separators=(',', ':'))
    print(name, 'json KB', os.path.getsize(os.path.join(out, 'animation.json')) // 1024, 'arm verts', len(arm_att['uvs']) // 2)

# beam / lamp textures + motion from the portrait bonus background (the same
# set the bonus screen uses), re-anchored on the desktop photo's lamp heads
build('bonus_bg', os.path.join(IMG, 'bg_bonus_desk.jpg'), 1932, 940,
      os.path.join(IMG, 'spine', 'scene', 'bonus_bg_mob_v3', 'animation.json'),
      ARM_POLY, ELBOW, FACE_X, CROP, FALL, 16,
      # the six stage lamp heads of the desktop club photo (brightest spots, top rows)
      origins=[(484, 56), (644, 17), (841, 16), (1024, 14), (1289, 15), (1442, 54)])
mp = lambda pts: [to_mob(*p) for p in pts]
mx0, my0 = to_mob(CROP[0], CROP[1]); mx1, my1 = to_mob(CROP[2], CROP[3])
build('bonus_bg_mob', os.path.join(IMG, 'spine', 'scene', 'bonus_bg_mob_v3', 'photo1.jpg'), 800, 1463,
      os.path.join(IMG, 'spine', 'scene', 'bonus_bg_mob_v3', 'animation.json'),
      mp(ARM_POLY), to_mob(*ELBOW), None,
      (round(mx0), round(my0), round(mx1), round(my1)), FALL * 0.765, 12)
