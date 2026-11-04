"""Recover alpha for Great Uniqorn art exported from Figma flattened onto #F5F5F5.

The Figma MCP export (download_assets) composites frames over the page colour,
so every PNG comes out opaque. Background = pixels near (245,245,245) that are
connected to the image border, plus large enclosed pockets of it (inside of the
frame, holes in letters). Pixels within EDGE px of that region get GIMP-style
colour-to-alpha against the known background; everything else stays opaque.

usage: python3 scripts/great_uniqorn_matte.py <edge_px> [--no-pockets] <file>...   (in place)

--no-pockets: only background connected to the image border is removed. Use
it for art whose own light areas (white lettering, a white shirt) match the
export background — the pocket rule cut a see-through hole into the «O» of
BUY BONUS and into the WILD's «D» (2026-11-04).
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

BG = 245.0


def matte(path: str, edge: int, pockets: bool = True) -> None:
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    diff = np.abs(im - BG).max(axis=2)
    near = diff <= 3
    labels, n = ndimage.label(near)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    sizes = ndimage.sum(near, labels, index=np.arange(1, n + 1))
    min_pocket = max(400, int(im.shape[0] * im.shape[1] * 0.0004))
    keep = [i for i in range(1, n + 1) if i in border or (pockets and sizes[i - 1] >= min_pocket)]
    bg = np.isin(labels, keep)
    band = ndimage.binary_dilation(bg, iterations=edge) & ~bg

    # colour-to-alpha against BG
    below = (BG - im) / BG
    above = (im - BG) / (255.0 - BG)
    a = np.clip(np.where(im < BG, below, above).max(axis=2), 0, 1)
    alpha = np.ones(im.shape[:2], np.float32)
    alpha[band] = a[band]
    alpha[bg] = 0
    safe = np.maximum(alpha, 1e-3)[..., None]
    fg = np.clip((im - (1 - alpha[..., None]) * BG) / safe, 0, 255)
    fg = np.where(band[..., None], fg, im)
    out = np.dstack([fg, alpha * 255]).round().astype(np.uint8)
    Image.fromarray(out, "RGBA").save(path)


if __name__ == "__main__":
    edge = int(sys.argv[1])
    args = sys.argv[2:]
    pockets = "--no-pockets" not in args
    for p in [a for a in args if a != "--no-pockets"]:
        matte(p, edge, pockets)
        print("matted", p)
