"""Tiny Spine 4.1 authoring library for Olympus Thunder's code-built rigs.

Unlike scripts/spine_screen_kit.py (region attachments + intro/idle only)
this one does what a character rig needs:

- any number of named animations, each with its own duration;
- WEIGHTED MESH attachments laid out as a grid and skinned to a bone chain
  (beard, hair, cloak sway as cloth instead of a rigid card);
- CLIPPING attachments (a light sweep that stays inside a symbol's
  silhouette);
- slot colour / attachment timelines and draw-order-free additive slots.

Timelines are authored as Python functions of time and sampled at FPS, then
thinned (a key is dropped when linear interpolation reproduces it within a
tolerance). Rotate / translate values are OFFSETS added to the setup pose,
scale values MULTIPLY it — exactly Spine's own timeline semantics.

Output per skeleton: <out>/<name>/animation.{json,atlas,png} with a
premultiplied-alpha atlas (load with premultipliedAlpha: true).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageChops, ImageFilter

FPS = 30


# ---------------------------------------------------------------- easing ----
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def in_cubic(t):
    t = clamp(t)
    return t ** 3


def in_out(t):
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def out_back(t, s=1.8):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def out_elastic(t, p=0.32):
    t = clamp(t)
    if t in (0, 1):
        return t
    return 2 ** (-10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1


def seg(t, t0, t1, v0, v1, ease=out_cubic):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    return lerp(v0, v1, ease((t - t0) / (t1 - t0)))


def keys(t, pts, ease=in_out):
    """Piecewise curve through [(t, v), ...] with `ease` on every segment."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return lerp(v0, v1, ease((t - t0) / (t1 - t0)))
    return pts[-1][1]


def loop_sin(t, period, phase=0.0):
    return math.sin(2 * math.pi * (t / period + phase))


def flicker(t, rate=18.0, seed=1.0):
    """Deterministic electric flicker in 0..1 (sum of incommensurate sines)."""
    v = (math.sin(t * rate * 1.0 + seed) + math.sin(t * rate * 1.618 + seed * 2.1) * 0.7
         + math.sin(t * rate * 2.414 + seed * 3.3) * 0.5)
    return clamp(0.5 + v / 4.4)


# ---------------------------------------------------------------- images ----
def premultiply(im: Image.Image) -> Image.Image:
    r, g, b, a = im.split()
    return Image.merge("RGBA", (ImageChops.multiply(r, a), ImageChops.multiply(g, a), ImageChops.multiply(b, a), a))


def glow_of(im: Image.Image, color=(255, 214, 90), radius=14, grow=1.25, strength=1.0) -> Image.Image:
    """Soft additive halo built from an image's alpha (for 'add' slots)."""
    pad = int(radius * 3)
    a = im.split()[3]
    big = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad))
    big.paste(a, (pad, pad))
    big = big.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(radius))
    arr = np.asarray(big).astype(np.float32) / 255 * strength
    arr = np.clip(arr * grow, 0, 1)
    out = np.zeros((big.height, big.width, 4), np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = color
    out[..., 3] = (arr * 255).astype(np.uint8)
    return Image.fromarray(out)


def bright_copy(im: Image.Image, k=1.0) -> Image.Image:
    """The image itself, brightened toward white — an additive 'flash' layer
    that lights the art from inside without changing its silhouette."""
    arr = np.asarray(im).astype(np.float32)
    rgb = arr[..., :3] / 255
    rgb = 1 - (1 - rgb) * (1 - 0.55 * k)
    arr[..., :3] = np.clip(rgb * 255, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def soft_dot(size=128, color=(255, 255, 255), power=2.2) -> Image.Image:
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2) / (size / 2)
    a = np.clip(1 - d, 0, 1) ** power
    out = np.zeros((size, size, 4), np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = color
    out[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(out)


def shine_bar(w=90, h=512) -> Image.Image:
    """Vertical soft light bar (rotated by the bone) for silhouette sweeps."""
    xx = np.linspace(-1, 1, w)[None, :]
    yy = np.linspace(-1, 1, h)[:, None]
    a = np.exp(-(xx ** 2) * 5.5) * np.clip(1 - np.abs(yy) ** 6, 0, 1)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = 255
    out[..., 3] = (a * 235).astype(np.uint8)
    return Image.fromarray(out)


def hull_polygon(im: Image.Image, n=20, thr=40, inset=0.0) -> list[tuple[float, float]]:
    """Convex hull of the alpha mask, resampled to ~n points (image px, y down)."""
    a = np.asarray(im.split()[3])
    ys, xs = np.where(a > thr)
    pts = np.stack([xs, ys], 1).astype(float)
    # monotone chain
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
    pts = np.unique(pts, axis=0)

    def cross(o, a_, b):
        return (a_[0] - o[0]) * (b[1] - o[1]) - (a_[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(tuple(p))
    for p in pts[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(tuple(p))
    hull = lower[:-1] + upper[:-1]
    # resample by perimeter
    seglen = [math.dist(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull))]
    total = sum(seglen)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        target = total * k / n
        while acc + seglen[i] < target:
            acc += seglen[i]
            i += 1
        f = (target - acc) / seglen[i] if seglen[i] else 0
        p0, p1 = hull[i], hull[(i + 1) % len(hull)]
        out.append((lerp(p0[0], p1[0], f), lerp(p0[1], p1[1], f)))
    if inset:
        cx = sum(p[0] for p in out) / n
        cy = sum(p[1] for p in out) / n
        out = [(lerp(x, cx, inset), lerp(y, cy, inset)) for x, y in out]
    return out


# ------------------------------------------------------------------ pack ----
def pack(regions: dict[str, Image.Image], max_w=2048, max_h=2048, gap=2):
    items = sorted(regions.items(), key=lambda kv: (-kv[1].height, -kv[1].width))
    pages = []
    while items:
        placed, left = {}, []
        x = y = shelf = used_w = used_h = 0
        for r, im in items:
            w, h = im.size
            if x + w > max_w:
                x, y, shelf = 0, y + shelf + gap, 0
            if y + h > max_h or w > max_w:
                left.append((r, im))
                continue
            placed[r] = (x, y, w, h)
            x += w + gap
            shelf = max(shelf, h)
            used_w, used_h = max(used_w, x), max(used_h, y + h)
        if not placed:
            raise SystemExit(f"region too big: {left[0][0]}")
        page = Image.new("RGBA", (used_w, used_h))
        for r, (px, py, w, h) in placed.items():
            page.paste(regions[r], (px, py))
        pages.append((page, placed))
        items = left
    return pages


# ------------------------------------------------------------------ rig -----
@dataclass
class Bone:
    name: str
    parent: str | None
    x: float = 0
    y: float = 0
    rot: float = 0
    sx: float = 1
    sy: float = 1
    length: float = 0


@dataclass
class Rig:
    name: str
    w: float  # box (skeleton units) the anchor element maps to
    h: float
    out_dir: str
    res: float = 1.0  # texture px per skeleton unit
    bones: list[Bone] = field(default_factory=list)
    slots: list[dict] = field(default_factory=list)
    atts: dict = field(default_factory=dict)
    images: dict = field(default_factory=dict)
    need: dict = field(default_factory=dict)
    anims: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)

    def __post_init__(self):
        self.bones.append(Bone("root", None))

    # -- setup ---------------------------------------------------------------
    def image(self, region: str, im: Image.Image) -> str:
        self.images[region] = im
        return region

    def bone(self, name, parent="root", x=0, y=0, rot=0, sx=1, sy=1, length=0) -> str:
        assert all(b.name != name for b in self.bones), name
        assert any(b.name == parent for b in self.bones), parent
        self.bones.append(Bone(name, parent, x, y, rot, sx, sy, length))
        return name

    def bone_at(self, name, parent, wx, wy, rot=0.0, length=0) -> str:
        """Bone placed by its WORLD setup position; `rot` is its world
        rotation (deg, CCW). Local values are derived from the parent."""
        pw = self.world(parent)
        lx, ly, _ = np.linalg.inv(pw) @ np.array([wx, wy, 1.0])
        prot = math.degrees(math.atan2(pw[1, 0], pw[0, 0]))
        return self.bone(name, parent, float(lx), float(ly), rot - prot, length=length)

    def _bone(self, name) -> Bone:
        return next(b for b in self.bones if b.name == name)

    def world(self, name) -> np.ndarray:
        """Setup-pose world matrix (3x3) of a bone."""
        b = self._bone(name)
        r = math.radians(b.rot)
        local = np.array([[math.cos(r) * b.sx, -math.sin(r) * b.sy, b.x],
                          [math.sin(r) * b.sx, math.cos(r) * b.sy, b.y],
                          [0, 0, 1]])
        return local if b.parent is None else self.world(b.parent) @ local

    def _slot(self, name, bone, attachment, blend=None, color=None, dark=None):
        s = {"name": name, "bone": bone}
        if attachment:
            s["attachment"] = attachment
        if blend:
            s["blend"] = blend
        if color:
            s["color"] = color
        self.slots.append(s)
        self.atts.setdefault(name, {})
        return name

    def region(self, slot, bone, region, x=0, y=0, w=None, h=None, rot=0, blend=None, color=None,
               attachment=None, visible=True, add_to_existing=False) -> str:
        """Region attachment (x,y = centre in the bone's space, y up)."""
        im = self.images[region]
        if w is None and h is None:
            w, h = im.width, im.height
        elif h is None:
            h = w * im.height / im.width
        elif w is None:
            w = h * im.width / im.height
        att_name = attachment or region
        if not add_to_existing:
            self._slot(slot, bone, att_name if visible else None, blend, color)
        att = {"x": round(x, 2), "y": round(y, 2), "width": round(w, 2), "height": round(h, 2)}
        if att_name != region:
            att["path"] = region
        if rot:
            att["rotation"] = round(rot, 2)
        self.atts.setdefault(slot, {})[att_name] = att
        pw, ph = self.need.get(region, (0, 0))
        self.need[region] = (max(pw, w), max(ph, h))
        return slot

    def mesh_grid(self, slot, region, cx, cy, w, h, weights, nx=4, ny=6, blend=None, color=None, bone=None):
        """Grid mesh of `region` centred at (cx, cy) skeleton units, skinned:
        weights(px, py) -> [(bone, weight), ...] in skeleton space (y up)."""
        im = self.images[region]
        names = [b.name for b in self.bones]
        inv = {}
        # vertex order: hull (boundary ring) first, then interior
        grid = [(i, j) for j in range(ny + 1) for i in range(nx + 1)]
        ring = ([(i, 0) for i in range(nx + 1)] + [(nx, j) for j in range(1, ny + 1)]
                + [(i, ny) for i in range(nx - 1, -1, -1)] + [(0, j) for j in range(ny - 1, 0, -1)])
        interior = [p for p in grid if p not in set(ring)]
        order = ring + interior
        index = {p: k for k, p in enumerate(order)}
        uvs, verts = [], []
        for (i, j) in order:
            u, v = i / nx, j / ny  # v=0 top of the image
            uvs += [round(u, 5), round(v, 5)]
            px = cx - w / 2 + u * w
            py = cy + h / 2 - v * h
            ws = [(b, wt) for b, wt in weights(px, py) if wt > 1e-4]
            total = sum(wt for _, wt in ws)
            verts.append(len(ws))
            for b, wt in ws:
                if b not in inv:
                    inv[b] = np.linalg.inv(self.world(b))
                lx, ly, _ = inv[b] @ np.array([px, py, 1.0])
                verts += [names.index(b), round(lx, 3), round(ly, 3), round(wt / total, 5)]
        tris = []
        for j in range(ny):
            for i in range(nx):
                a, b_ = index[(i, j)], index[(i + 1, j)]
                c, d = index[(i, j + 1)], index[(i + 1, j + 1)]
                tris += [a, c, b_, b_, c, d]
        self._slot(slot, bone or weights(cx, cy)[0][0], region, blend, color)
        self.atts[slot][region] = {"type": "mesh", "uvs": uvs, "triangles": tris, "vertices": verts,
                                   "hull": len(ring), "width": round(w, 2), "height": round(h, 2)}
        pw, ph = self.need.get(region, (0, 0))
        self.need[region] = (max(pw, w), max(ph, h))
        return slot

    def clip(self, slot, bone, polygon, end_slot):
        """Clipping polygon (skeleton units, bone space) active until end_slot."""
        self._slot(slot, bone, "clip")
        flat = []
        for x, y in polygon:
            flat += [round(x, 2), round(y, 2)]
        self.atts[slot]["clip"] = {"type": "clipping", "end": end_slot, "vertexCount": len(polygon), "vertices": flat}
        return slot

    def event(self, name):
        self.events[name] = {}

    # -- animation -----------------------------------------------------------
    TOL = {"translate": 0.2, "scale": 0.0012, "rotate": 0.06, "rgba": 0.004, "shear": 0.06}

    def anim(self, name: str, dur: float) -> Anim:
        a = Anim(self, name, dur)
        self.anims[name] = a.data
        return a

    # -- output --------------------------------------------------------------
    def write(self, max_page=2048, quantize=False, webp=True):
        out = os.path.join(self.out_dir, self.name)
        os.makedirs(out, exist_ok=True)
        for f in os.listdir(out):
            if f.startswith("animation"):
                os.remove(os.path.join(out, f))
        regions = {}
        for r, im in self.images.items():
            if r not in self.need:
                continue
            w, h = self.need[r]
            scale = min(1.0, (w * self.res) / im.width, (h * self.res) / im.height) if im.width and im.height else 1
            scale = max(scale, min(1.0, 4 / max(1, min(im.size))))
            tw, th = max(2, round(im.width * scale)), max(2, round(im.height * scale))
            regions[r] = im.resize((tw, th), Image.LANCZOS) if (tw, th) != im.size else im
        pages = pack(regions, max_page, max_page)
        lines = []
        for pi, (page, placed) in enumerate(pages):
            ext = "webp" if webp else "png"
            fname = f"animation.{ext}" if pi == 0 else f"animation{pi + 1}.{ext}"
            page = premultiply(page)
            if quantize:
                page = page.quantize(256, Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
            if webp:
                # lossy WebP keeps 8-bit alpha and smooth PMA glows (a 256-colour
                # quantise bands them) at a fraction of the PNG size
                page.save(os.path.join(out, fname), "WEBP", quality=90, alpha_quality=95, method=6)
            else:
                page.save(os.path.join(out, fname), optimize=True)
            lines += [fname, f"size:{page.width},{page.height}", "filter:Linear,Linear", "pma:true"]
            for r, (x, y, w, h) in placed.items():
                lines += [r, f"bounds:{x},{y},{w},{h}"]
            lines.append("")
        with open(os.path.join(out, "animation.atlas"), "w") as f:
            f.write("\n".join(lines))
        bones = []
        for b in self.bones:
            d = {"name": b.name}
            if b.parent:
                d["parent"] = b.parent
            for k, v, dflt in (("x", b.x, 0), ("y", b.y, 0), ("rotation", b.rot, 0), ("scaleX", b.sx, 1),
                               ("scaleY", b.sy, 1), ("length", b.length, 0)):
                if v != dflt:
                    d[k] = round(v, 3)
            bones.append(d)
        data = {
            "skeleton": {"hash": self.name, "spine": "4.1.24", "x": -self.w / 2, "y": -self.h / 2,
                         "width": self.w, "height": self.h, "fps": FPS},
            "bones": bones,
            "slots": self.slots,
            "skins": [{"name": "default", "attachments": self.atts}],
            "events": self.events,
            "animations": self.anims,
        }
        with open(os.path.join(out, "animation.json"), "w") as f:
            json.dump(data, f, separators=(",", ":"))
        size = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out))
        print(f"{self.name}: bones {len(self.bones)} slots {len(self.slots)} anims {len(self.anims)} "
              f"pages {[p.size for p, _ in pages]} {size // 1024} KB")


class Anim:
    def __init__(self, rig: Rig, name: str, dur: float):
        self.rig, self.name, self.dur = rig, name, dur
        self.data = {"bones": {}, "slots": {}}

    def _sample(self, fn):
        n = max(1, int(round(self.dur * FPS)))
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
        if len(out) > 1 and all(vals(v) == vals(out[0][1]) for _, v in out):
            out = out[:1]
        return out

    def bone(self, target, prop, fn):
        """rotate: fn(t)->deg offset · translate: fn(t)->(dx,dy) · scale:
        fn(t)->(sx,sy) or s · shear: fn(t)->(x,y)."""
        if prop == "scale":
            f0 = fn
            fn = lambda t: f0(t) if isinstance(f0(t), tuple) else (f0(t), f0(t))  # noqa: E731
        rows = []
        for t, v in self._thin(self._sample(fn), Rig.TOL[prop]):
            r = {"time": round(t, 4)} if t else {}
            if prop in ("translate", "scale", "shear"):
                r["x"], r["y"] = round(v[0], 4), round(v[1], 4)
            else:
                r["value"] = round(v, 3)
            rows.append(r)
        self.data["bones"].setdefault(target, {})[prop] = rows
        return self

    def rgba(self, slot, fn, base=(1, 1, 1)):
        """fn(t) -> alpha or (r,g,b,a) in 0..1."""
        def full(t):
            v = fn(t)
            return v if isinstance(v, tuple) else (*base, v)

        rows = []
        for t, v in self._thin(self._sample(full), Rig.TOL["rgba"]):
            c = "".join(f"{int(round(clamp(x) * 255)):02x}" for x in v)
            rows.append({"time": round(t, 4), "color": c} if t else {"color": c})
        self.data["slots"].setdefault(slot, {})["rgba"] = rows
        return self

    def attach(self, slot, keys_):
        """keys_: [(t, attachment_name or None), ...]"""
        self.data["slots"].setdefault(slot, {})["attachment"] = [
            ({"time": round(t, 4)} if t else {}) | {"name": n} for t, n in keys_
        ]
        return self

    def event(self, name, t):
        self.data.setdefault("events", []).append({"time": round(t, 4), "name": name})
        return self
