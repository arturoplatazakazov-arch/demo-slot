"""Deep Fortune: cut the high-pay symbols into animation layers ("cutout rig").

Each framed tile (siren / shark / nymph / wild) becomes three PNGs that stack
back-to-front in the cell and are animated separately in CSS
(front/css/deep-fortune-fx.css, "Живые символы"):

  <code>_back.png   frame + inner scene, the character painted out (inpainted)
  <code>_char.png   the character alone, including what breaks out of the frame
  <code>_front.png  what must stay ON TOP of the character: the frame's bottom
                    bar (and the WILD lettering on the wild)

The character is segmented INSIDE the frame window only (on the whole tile
every model just returns the whole tile as the salient object), then joined
with what sticks out past the frame's outer edge, and the frame bar between
the two is bridged column-by-column (row-by-row for side break-outs).

All layers get exactly the same trim/scale/centre as the symbol PNG made by
scripts/deep_fortune_build.py, so they line up with it pixel for pixel.

Needs rembg + opencv (not in the app's venv):
    uv venv /tmp/rig && uv pip install --python /tmp/rig/bin/python "rembg[cpu]" opencv-python-headless
    /tmp/rig/bin/python scripts/deep_fortune_rig.py
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "front/img/deep-fortune"
OUT = BASE / "symbols/rig"
CELL = 360
FILL = 0.98  # must match deep_fortune_build.symbols() for these codes

# window: frame opening as fractions of the tile; front_y: from this row down
# the tile is copied to the front layer (bottom bar / WILD lettering).
RIGS = {
    "siren": {"src": "src/gpt/siren.webp", "window": (0.135, 0.19, 0.865, 0.83), "front_y": 0.83},
    "shark": {"src": "src/gpt/shark.webp", "window": (0.135, 0.17, 0.865, 0.83), "front_y": 0.83, "bridge_rows": (0.50, 0.66)},
    "nymph": {"src": "src/nymph.png", "window": (0.11, 0.14, 0.89, 0.84), "front_y": 0.84},
    "wild": {"src": "src/wild.png", "window": (0.11, 0.14, 0.89, 0.60), "front_y": 0.60},
}


def frame_outer(alpha: np.ndarray) -> tuple[int, int, int, int]:
    """Outer edge of the frame: first/last rows and columns that are mostly
    opaque (the bars span most of the tile; hair or a fin never does)."""
    h, w = alpha.shape
    rows = np.where((alpha > 128).mean(axis=1) > 0.6)[0]
    cols = np.where((alpha > 128).mean(axis=0) > 0.6)[0]
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def build(code: str, cfg: dict, session) -> None:
    tile = Image.open(BASE / cfg["src"]).convert("RGBA")
    W, H = tile.size
    rgba = np.array(tile)
    alpha = rgba[:, :, 3]

    # 1) character inside the window
    wx0, wy0, wx1, wy1 = (round(cfg["window"][0] * W), round(cfg["window"][1] * H),
                          round(cfg["window"][2] * W), round(cfg["window"][3] * H))
    crop = tile.crop((wx0, wy0, wx1, wy1))
    flat = Image.new("RGBA", crop.size, (128, 128, 128, 255))
    flat.alpha_composite(crop)
    m = np.array(remove(flat.convert("RGB"), session=session, only_mask=True), dtype=np.float32) / 255
    mask = np.zeros((H, W), np.float32)
    mask[wy0:wy1, wx0:wx1] = m

    # 2) break-out: opaque pixels past the frame's outer edge are character
    fx0, fy0, fx1, fy1 = frame_outer(alpha)
    out = np.zeros((H, W), bool)
    out[:fy0, :] = True
    # Sideways only where the config says something crosses a side bar: the
    # frame's own outer bevel lies past fx0/fx1 along its whole height.
    side = cfg.get("bridge_rows")
    if side:
        r0, r1 = round(side[0] * H), round(side[1] * H)
        out[r0:r1, :fx0] = True
        out[r0:r1, fx1 + 1:] = True
    breakout = (alpha > 8) & out
    # Morphological opening drops the frame's 1-3px anti-aliased rim (it
    # touches the shark's fin and would ride along as a thin gold line).
    breakout = cv2.morphologyEx(breakout.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) > 0
    solid = (alpha > 200) & out  # past the frame's anti-aliased rim
    mask = np.maximum(mask, breakout.astype(np.float32) * (alpha / 255))

    # 3) bridge the frame bar where the character crosses it
    probe = 6
    far = 16  # how far outside the frame edge to look for the break-out
    for x in range(wx0, wx1):  # top bar
        if solid[max(0, fy0 - far), x] and m[min(probe, m.shape[0] - 1), x - wx0] > 0.5:
            mask[fy0 - probe:wy0 + probe, x] = 1
    for y in range(round(side[0] * H), round(side[1] * H)) if side else ():
        if solid[y, max(0, fx0 - far)] and m[y - wy0, min(probe, m.shape[1] - 1)] > 0.5:
            mask[y, fx0 - probe:wx0 + probe] = 1
        if solid[y, min(W - 1, fx1 + far)] and m[y - wy0, max(0, m.shape[1] - 1 - probe)] > 0.5:
            mask[y, wx1 - probe:fx1 + probe] = 1

    front_y = round(cfg["front_y"] * H)
    mask[front_y:, :] = 0
    # Keep only what is connected to the character found in the window: the
    # frame's anti-aliased outer edge and corner shells also sit past the
    # "outer edge" and would otherwise come along as stray slivers.
    n, labels = cv2.connectedComponents((mask > 0.3).astype(np.uint8), connectivity=8)
    seed = np.zeros((H, W), bool)
    seed[wy0:wy1, wx0:wx1] = m > 0.5
    keep = np.unique(labels[seed & (labels > 0)])
    mask[~np.isin(labels, keep)] = 0
    mask = cv2.GaussianBlur(mask, (0, 0), 0.8)

    # 4) back = tile with the character painted out
    hole = (mask > 0.12).astype(np.uint8) * 255
    hole = cv2.dilate(hole, np.ones((7, 7), np.uint8))
    hole[~((alpha > 8) & ~breakout)] = 0
    bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    filled = cv2.inpaint(bgr, hole, 12, cv2.INPAINT_TELEA)
    back = np.dstack([cv2.cvtColor(filled, cv2.COLOR_BGR2RGB), alpha.copy()])
    back[:, :, 3][cv2.dilate(breakout.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0] = 0
    # Soften the painted-out area a touch more: the inpaint smears, a blur
    # reads as depth-of-field behind the character instead.
    blur = cv2.GaussianBlur(back[:, :, :3], (0, 0), 3)
    k = (cv2.GaussianBlur(hole, (0, 0), 6) / 255.0)[:, :, None]
    back[:, :, :3] = (back[:, :, :3] * (1 - k) + blur * k).astype(np.uint8)

    char = rgba.copy()
    char[:, :, 3] = (alpha * mask).astype(np.uint8)
    front = rgba.copy()
    front[:front_y, :, 3] = 0

    # 5) same trim/fit as the symbol PNG
    bbox = Image.fromarray(alpha).point(lambda v: 255 if v > 8 else 0).getbbox()
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    s = min(CELL * FILL / bw, CELL * FILL / bh)
    size = (round(bw * s), round(bh * s))
    off = ((CELL - size[0]) // 2, (CELL - size[1]) // 2)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, arr in (("back", back), ("char", char), ("front", front)):
        layer = Image.fromarray(arr, "RGBA").crop(bbox).resize(size, Image.LANCZOS)
        canvas = Image.new("RGBA", (CELL, CELL))
        canvas.alpha_composite(layer, off)
        canvas.quantize(224, method=Image.Quantize.FASTOCTREE).save(OUT / f"{code}_{name}.png", optimize=True)
    print(code, "frame", (fx0, fy0, fx1, fy1), "window", (wx0, wy0, wx1, wy1))


if __name__ == "__main__":
    sess = new_session("birefnet-general-lite")
    for code, cfg in RIGS.items():
        build(code, cfg, sess)


def hero_hair() -> None:
    """Hair + tail layer for the mascot (img/<pose>_hair.png): the red/pink,
    saturated pixels — her hair and tail — with a soft edge. It is stacked
    over the full figure and wobbled with an SVG displacement filter, so the
    hair and tail float in the water while face, hands and body stay crisp."""
    for pose in ("hero", "hero_tense", "hero_cheer"):
        src = BASE / "img" / f"{pose}.png"
        rgba = np.array(Image.open(src).convert("RGBA"))
        hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1] / 255, hsv[:, :, 2] / 255
        red = ((h < 9) | (h > 165)) & (s > 0.5) & (v > 0.3)
        # Opening with a big kernel drops small red bits — her lips above all;
        # the hair and tail are large masses and survive.
        red = cv2.morphologyEx(red.astype(np.uint8), cv2.MORPH_OPEN, np.ones((17, 17), np.uint8)) > 0
        weight = cv2.GaussianBlur(red.astype(np.float32), (0, 0), 3)
        # Taper towards the head: the roots barely move, the ends sway most.
        rows = np.linspace(0, 1, rgba.shape[0])[:, None]
        weight *= np.clip(0.35 + rows * 1.2, 0, 1)
        out = rgba.copy()
        out[:, :, 3] = (rgba[:, :, 3] * np.clip(weight * 1.3, 0, 1)).astype(np.uint8)
        Image.fromarray(out, "RGBA").quantize(224, method=Image.Quantize.FASTOCTREE).save(
            BASE / "img" / f"{pose}_hair.png", optimize=True)
        print(pose, "hair layer")


if __name__ == "__main__":
    hero_hair()
