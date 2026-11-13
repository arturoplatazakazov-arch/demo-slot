"""Render the SETUP POSE of a Spine 4.x export to a transparent PNG.

Handles region attachments and mesh attachments (unweighted and weighted),
atlas trim offsets and 90/180/270 page rotation, slot setup color + blend mode.
Animations are ignored entirely.

    from spine_pose import render
    info = render(folder, out_png, scale=1.0)

`folder` must contain animation.json / animation.atlas / the page PNG(s).
Alpha: pages are treated as straight (non-premultiplied) unless the atlas
header says `pma:true`; pass premultiplied=True/False to override.
The saved PNG is straight-alpha RGBA, tightly cropped to visible pixels.
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image

# --------------------------------------------------------------------------- #
# atlas
# --------------------------------------------------------------------------- #


def parse_atlas(path):
    """-> (regions_by_name, page_meta). Region keys: page, bounds, offsets, rotate."""
    regions, pages = {}, {}
    page = None
    cur = None
    expect_page_header = True
    with open(path) as fh:
        lines = fh.read().splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip():
            page = None
            expect_page_header = True
            cur = None
            continue
        if page is None and expect_page_header:
            page = line.strip()
            pages[page] = {}
            # page header key:value lines
            while i < len(lines) and ':' in lines[i] and not lines[i].startswith((' ', '\t')):
                k, v = (s.strip() for s in lines[i].split(':', 1))
                pages[page][k] = v
                i += 1
            expect_page_header = False
            cur = None
            continue
        if ':' in line:
            if cur is not None:
                k, v = (s.strip() for s in line.split(':', 1))
                cur[k] = v
            continue
        cur = regions[line.strip()] = {'page': page}
    return regions, pages


def region_rect(reg):
    """-> (x, y, w, h, ox, oy, ow, oh, degrees) in page pixels.

    x,y = top-left of the packed rect in the page. w,h = packed size in the
    UNROTATED orientation (as the atlas writes it); when degrees is 90/270 the
    rect actually occupies h x w pixels of the page. ox,oy = trim offset from
    the bottom-left of the original, ow,oh = original (untrimmed) size.
    """
    if 'bounds' in reg:
        x, y, w, h = (int(float(v)) for v in reg['bounds'].split(','))
    else:
        x, y = (int(float(v)) for v in reg['xy'].split(','))
        w, h = (int(float(v)) for v in reg['size'].split(','))
    if 'offsets' in reg:
        ox, oy, ow, oh = (int(float(v)) for v in reg['offsets'].split(','))
    elif 'offset' in reg:
        ox, oy = (int(float(v)) for v in reg['offset'].split(','))
        ow, oh = (int(float(v)) for v in reg.get('orig', f'{w},{h}').split(','))
    else:
        ox = oy = 0
        ow, oh = w, h
    deg = 0
    rot = reg.get('rotate', reg.get('rotation', 'false'))
    if rot in ('true', 'True'):
        deg = 90
    elif rot not in ('false', 'False'):
        deg = int(float(rot)) % 360
    return x, y, w, h, ox, oy, ow, oh, deg


def uv_to_page_px(reg, u, v):
    """Map Spine region UVs (0..1 over the ORIGINAL image) to page pixels.

    Mirrors MeshAttachment.updateUVs() from the official 4.1 runtime, expressed
    in pixels instead of normalised texture coordinates.
    """
    x, y, w, h, ox, oy, ow, oh, deg = region_rect(reg)
    if deg == 90:
        u0 = x - (oh - oy - h)
        v0 = y - (ow - ox - w)
        return u0 + v * oh, v0 + ow - u * ow
    if deg == 180:
        u0 = x - (ow - ox - w)
        v0 = y - oy
        return u0 + ow - u * ow, v0 + oh - v * oh
    if deg == 270:
        u0 = x - oy
        v0 = y - ox
        return u0 + oh - v * oh, v0 + u * ow
    u0 = x - ox
    v0 = y - (oh - oy - h)
    return u0 + u * ow, v0 + v * oh


# --------------------------------------------------------------------------- #
# bones
# --------------------------------------------------------------------------- #


def _local(b):
    """Local 2x3 matrix [[a, b, x], [c, d, y]] for a bone's setup pose."""
    rot = b.get('rotation', 0.0)
    sx, sy = b.get('scaleX', 1.0), b.get('scaleY', 1.0)
    shx, shy = b.get('shearX', 0.0), b.get('shearY', 0.0)
    ra = math.radians(rot + shx)
    rb = math.radians(rot + 90.0 + shy)
    return np.array([
        [math.cos(ra) * sx, math.cos(rb) * sy, b.get('x', 0.0)],
        [math.sin(ra) * sx, math.sin(rb) * sy, b.get('y', 0.0)],
    ], np.float64)


def _compose(parent, b):
    lo = _local(b)
    pa, pb, px = parent[0]
    pc, pd, py = parent[1]
    wx = pa * lo[0, 2] + pb * lo[1, 2] + px
    wy = pc * lo[0, 2] + pd * lo[1, 2] + py
    mode = b.get('transform', b.get('inherit', 'normal'))

    if mode in ('normal', 'Normal'):
        a = pa * lo[0, 0] + pb * lo[1, 0]
        bb = pa * lo[0, 1] + pb * lo[1, 1]
        c = pc * lo[0, 0] + pd * lo[1, 0]
        d = pc * lo[0, 1] + pd * lo[1, 1]
        return np.array([[a, bb, wx], [c, d, wy]], np.float64)

    if mode in ('onlyTranslation', 'OnlyTranslation'):
        return np.array([[lo[0, 0], lo[0, 1], wx], [lo[1, 0], lo[1, 1], wy]], np.float64)

    if mode in ('noRotationOrReflection', 'NoRotationOrReflection'):
        s = pa * pa + pc * pc
        if s > 1e-12:
            s = abs(pa * pd - pb * pc) / s
            pb = pc * s
            pd = pa * s
        else:
            pa, pc = 0.0, 0.0
        a = pa * lo[0, 0] + pb * lo[1, 0]
        bb = pa * lo[0, 1] + pb * lo[1, 1]
        c = pc * lo[0, 0] + pd * lo[1, 0]
        d = pc * lo[0, 1] + pd * lo[1, 1]
        return np.array([[a, bb, wx], [c, d, wy]], np.float64)

    # noScale / noScaleOrReflection: keep the parent's rotation, drop its scale
    pr = math.atan2(pc, pa)
    ca, sa = math.cos(pr), math.sin(pr)
    if mode in ('noScaleOrReflection', 'NoScaleOrReflection') and (pa * pd - pb * pc) < 0:
        sa = -sa
    za = np.array([[ca, -sa], [sa, ca]], np.float64)
    m = za @ lo[:, :2]
    return np.array([[m[0, 0], m[0, 1], wx], [m[1, 0], m[1, 1], wy]], np.float64)


def bone_world(data):
    world = {}
    ident = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    order = []
    for b in data.get('bones', []):
        p = b.get('parent')
        world[b['name']] = _local(b) if p is None else _compose(world[p], b)
        order.append(b['name'])
    if not order:
        world['root'] = ident
        order.append('root')
    return world, order


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #


def _apply(m, x, y):
    return m[0, 0] * x + m[0, 1] * y + m[0, 2], m[1, 0] * x + m[1, 1] * y + m[1, 2]


def _nums(v):
    return [float(t) for t in v] if isinstance(v, list) else []


def attachment_geometry(att, reg, slot_bone_m, world, bone_names):
    """-> (verts Nx2 world, uvs Nx2 in 0..1 region space, triangles Mx3) or None."""
    kind = att.get('type', 'region')

    if kind == 'region':
        x, y, w, h, ox, oy, ow, oh, deg = region_rect(reg)
        aw = float(att.get('width', ow))
        ah = float(att.get('height', oh))
        asx = float(att.get('scaleX', 1.0))
        asy = float(att.get('scaleY', 1.0))
        rsx = aw / ow * asx
        rsy = ah / oh * asy
        pw, ph = w, h              # packed size, already in original orientation
        lx = -aw / 2 * asx + ox * rsx
        ly = -ah / 2 * asy + oy * rsy
        lx2 = lx + pw * rsx
        ly2 = ly + ph * rsy
        m = slot_bone_m @ np.vstack([_local({
            'x': att.get('x', 0.0), 'y': att.get('y', 0.0),
            'rotation': att.get('rotation', 0.0),
        }), [0, 0, 1]])
        corners = [(lx, ly2), (lx2, ly2), (lx2, ly), (lx, ly)]
        # UVs over the ORIGINAL image for those corners
        u1, u2 = ox / ow, (ox + pw) / ow
        v1, v2 = 1.0 - (oy + ph) / oh, 1.0 - oy / oh   # v grows downward
        uvs = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
        verts = [_apply(m, cx, cy) for cx, cy in corners]
        return (np.array(verts, np.float64), np.array(uvs, np.float64),
                np.array([[0, 1, 2], [0, 2, 3]], np.int32))

    if kind not in ('mesh', 'linkedmesh', 'skinnedmesh'):
        return None

    uvs = _nums(att.get('uvs'))
    tris = [int(t) for t in att.get('triangles', [])]
    vraw = _nums(att.get('vertices'))
    if not uvs or not tris or not vraw:
        return None
    n = len(uvs) // 2

    if len(vraw) == len(uvs):                      # unweighted: bone-local pairs
        verts = [_apply(slot_bone_m, vraw[2 * i], vraw[2 * i + 1]) for i in range(n)]
    else:                                          # weighted
        verts = []
        i = 0
        for _ in range(n):
            cnt = int(vraw[i]); i += 1
            wx = wy = 0.0
            for _k in range(cnt):
                bi = int(vraw[i]); vx = vraw[i + 1]; vy = vraw[i + 2]; wt = vraw[i + 3]
                i += 4
                bm = world[bone_names[bi]]
                px, py = _apply(bm, vx, vy)
                wx += px * wt
                wy += py * wt
            verts.append((wx, wy))

    return (np.array(verts, np.float64),
            np.array(uvs, np.float64).reshape(-1, 2),
            np.array(tris, np.int32).reshape(-1, 3))


# --------------------------------------------------------------------------- #
# rasterizer
# --------------------------------------------------------------------------- #


def _sample(page, sx, sy):
    """Bilinear sample a premultiplied float page (H,W,4) at pixel centres."""
    H, W = page.shape[:2]
    fx = np.clip(sx - 0.5, 0, W - 1)
    fy = np.clip(sy - 0.5, 0, H - 1)
    x0 = np.floor(fx).astype(np.int32)
    y0 = np.floor(fy).astype(np.int32)
    x1 = np.minimum(x0 + 1, W - 1)
    y1 = np.minimum(y0 + 1, H - 1)
    tx = (fx - x0)[..., None]
    ty = (fy - y0)[..., None]
    a = page[y0, x0]
    b = page[y0, x1]
    c = page[y1, x0]
    d = page[y1, x1]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def _raster_triangles(layer, verts_px, uvs, tris, reg, page, bleed=0.6):
    """Draw triangles into `layer` (H,W,4 premultiplied), last write wins."""
    H, W = layer.shape[:2]
    for t in tris:
        p0, p1, p2 = verts_px[t[0]], verts_px[t[1]], verts_px[t[2]]
        area = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
        if abs(area) < 1e-9:
            continue
        x0 = int(math.floor(min(p0[0], p1[0], p2[0]) - bleed - 1))
        x1 = int(math.ceil(max(p0[0], p1[0], p2[0]) + bleed + 1))
        y0 = int(math.floor(min(p0[1], p1[1], p2[1]) - bleed - 1))
        y1 = int(math.ceil(max(p0[1], p1[1], p2[1]) + bleed + 1))
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W), min(y1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        px = xs + 0.5
        py = ys + 0.5

        def edge(a, b):
            return (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])

        def elen(a, b):
            return math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-9

        sgn = 1.0 if area > 0 else -1.0
        e0 = edge(p1, p2) * sgn      # weight of v0
        e1 = edge(p2, p0) * sgn      # weight of v1
        e2 = edge(p0, p1) * sgn      # weight of v2
        tol0 = bleed * elen(p1, p2)
        tol1 = bleed * elen(p2, p0)
        tol2 = bleed * elen(p0, p1)
        mask = (e0 >= -tol0) & (e1 >= -tol1) & (e2 >= -tol2)
        if not mask.any():
            continue
        inv = 1.0 / (area * sgn)
        w0 = np.clip(e0[mask] * inv, 0, 1)
        w1 = np.clip(e1[mask] * inv, 0, 1)
        w2 = np.clip(e2[mask] * inv, 0, 1)
        s = w0 + w1 + w2
        s = np.where(s < 1e-9, 1.0, s)
        w0, w1, w2 = w0 / s, w1 / s, w2 / s
        u = w0 * uvs[t[0], 0] + w1 * uvs[t[1], 0] + w2 * uvs[t[2], 0]
        v = w0 * uvs[t[0], 1] + w1 * uvs[t[1], 1] + w2 * uvs[t[2], 1]
        sx, sy = uv_to_page_px(reg, u, v)
        col = _sample(page, sx, sy)
        sub = layer[y0:y1, x0:x1]
        prev = sub[mask]
        # keep whatever is already there if it is more opaque (seam safety)
        take = col[..., 3] >= prev[..., 3]
        prev[take] = col[take]
        sub[mask] = prev


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #


def render(folder, out_png, scale=1.0, premultiplied=None, skin=None,
           skip_zero_alpha=True, pad=2):
    """Render the setup pose of the export in `folder` to `out_png`.

    Returns a dict:
        x, y        skeleton coords of the image's left / BOTTOM edge
        top         skeleton coord of the image's top edge
        width,
        height      size of the crop in skeleton units
        pixel_width,
        pixel_height, scale
    """
    data = json.load(open(os.path.join(folder, 'animation.json')))
    regions, pages_meta = parse_atlas(os.path.join(folder, 'animation.atlas'))
    world, bone_names = bone_world(data)

    # ----- pick the skin's attachment table -------------------------------- #
    skins = data.get('skins', [])
    tables = []
    if isinstance(skins, dict):
        for nm, tbl in skins.items():
            if skin is None or nm == skin:
                tables.append(tbl)
        if skin is None and 'default' in skins:
            tables = [skins['default']]
    else:
        for s in skins:
            if skin is None or s.get('name') == skin:
                tables.append(s.get('attachments', {}))
        if skin is None and tables:
            tables = [tables[0]]

    def find_att(slot_name, att_name):
        for tbl in tables:
            got = tbl.get(slot_name, {}).get(att_name)
            if got is not None:
                return got
        if isinstance(skins, list):
            for s in skins:
                got = s.get('attachments', {}).get(slot_name, {}).get(att_name)
                if got is not None:
                    return got
        elif isinstance(skins, dict):
            for tbl in skins.values():
                got = tbl.get(slot_name, {}).get(att_name)
                if got is not None:
                    return got
        return None

    # ----- collect drawable slots ------------------------------------------ #
    draw = []
    for slot in data.get('slots', []):
        att_name = slot.get('attachment')
        if not att_name:
            continue
        col = slot.get('color', 'ffffffff')
        alpha = int(col[6:8], 16) / 255.0 if len(col) >= 8 else 1.0
        if skip_zero_alpha and alpha <= 0:
            continue
        att = find_att(slot['name'], att_name)
        if att is None:
            continue
        if att.get('type') == 'linkedmesh':
            parent = find_att(slot['name'], att.get('parent', '')) or {}
            merged = dict(parent)
            merged.update({k: v for k, v in att.items() if k not in ('type', 'parent')})
            merged['type'] = 'mesh'
            att = merged
        path = att.get('path', att_name)
        reg = regions.get(path) or regions.get(att_name)
        if reg is None:
            continue
        bone_m = world.get(slot.get('bone', 'root'), world[bone_names[0]])
        geom = attachment_geometry(att, reg, bone_m, world, bone_names)
        if geom is None:
            continue
        tint = np.array([int(col[i:i + 2], 16) / 255.0 for i in (0, 2, 4)] + [alpha], np.float32)
        if 'color' in att:
            ac = att['color']
            tint = tint * np.array(
                [int(ac[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6)], np.float32)
        draw.append((slot, reg, geom, tint))

    if not draw:
        raise RuntimeError(f'nothing to draw in {folder}')

    # ----- canvas bounds from actual geometry ------------------------------ #
    allv = np.vstack([g[0] for _s, _r, g, _t in draw])
    minx, miny = allv.min(0)
    maxx, maxy = allv.max(0)
    minx -= pad / scale
    miny -= pad / scale
    maxx += pad / scale
    maxy += pad / scale
    W = max(1, int(math.ceil((maxx - minx) * scale)))
    H = max(1, int(math.ceil((maxy - miny) * scale)))

    # ----- pages ----------------------------------------------------------- #
    page_cache = {}

    def get_page(name):
        if name in page_cache:
            return page_cache[name]
        im = Image.open(os.path.join(folder, name)).convert('RGBA')
        arr = np.asarray(im).astype(np.float32) / 255.0
        pma = premultiplied
        if pma is None:
            pma = pages_meta.get(name, {}).get('pma', 'false') in ('true', 'True')
        if not pma:
            arr = np.concatenate([arr[..., :3] * arr[..., 3:4], arr[..., 3:4]], 2)
        page_cache[name] = arr
        return arr

    canvas = np.zeros((H, W, 4), np.float32)   # premultiplied
    for slot, reg, (verts, uvs, tris), tint in draw:
        px = (verts[:, 0] - minx) * scale
        py = (maxy - verts[:, 1]) * scale
        layer = np.zeros((H, W, 4), np.float32)
        _raster_triangles(layer, np.stack([px, py], 1), uvs, tris, reg, get_page(reg['page']))
        layer *= tint                       # premultiplied * (rgb tint, alpha)
        a = layer[..., 3:4]
        if slot.get('blend') == 'additive':
            canvas[..., :3] += layer[..., :3]
            canvas[..., 3:4] = np.clip(canvas[..., 3:4] + a, 0, 1)
        else:
            canvas = canvas * (1 - a) + layer

    # ----- unpremultiply + tight crop -------------------------------------- #
    canvas = np.clip(canvas, 0, 1)
    a = canvas[..., 3:4]
    rgb = np.divide(canvas[..., :3], np.where(a < 1e-5, 1.0, a)).clip(0, 1)
    out = (np.concatenate([rgb, a], 2) * 255.0 + 0.5).astype(np.uint8)
    img = Image.fromarray(out)
    box = img.getbbox() or (0, 0, W, H)
    img = img.crop(box)
    img.save(out_png)

    l, t, r, b = box
    return {
        'x': minx + l / scale,
        'y': maxy - b / scale,
        'top': maxy - t / scale,
        'width': (r - l) / scale,
        'height': (b - t) / scale,
        'pixel_width': img.width,
        'pixel_height': img.height,
        'scale': scale,
        'crop_box_px': box,
    }


if __name__ == '__main__':
    sc = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    print(render(sys.argv[1], sys.argv[2], sc))
