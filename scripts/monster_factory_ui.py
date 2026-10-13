"""Monster Factory: the UI art drawn in code (frame, logo, plates).

Stand-ins for the ChatGPT-generated UI that hasn't been delivered yet, drawn in
the same language as the rest of the pack — chunky orange-painted steel with a
dark outline, bolts, hazard stripes, navy display windows, Luckiest Guy
lettering. Every window is drawn at exactly the size the CSS expects, so the
geometry printed at the end is what goes into css/monster-factory.css.

    python scripts/monster_factory_ui.py            # all
    python scripts/monster_factory_ui.py frame logo  # some

Writes front/img/monster-factory/img/{frame_desk,frame_mob,logo,buy_bonus,
plate_counter,plate_amount}.png. If a real generated version lands in src/,
scripts/monster_factory_build.py overwrites the matching file.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "front/img/monster-factory/img"
FONT = str(ROOT / "front/fonts/luckiest-guy-latin-fe2ede07.woff2")

INK = (42, 18, 6, 255)
ORANGE_TOP = (255, 182, 72)
ORANGE_BOT = (214, 88, 10)
NAVY_TOP = (32, 42, 88)
NAVY_BOT = (10, 14, 34)
SS = 2  # supersampling


# --- primitives ---------------------------------------------------------------

def vgrad(size, top, bot):
    w, h = size
    g = Image.new("RGBA", (1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)) + (255,))
    return g.resize((w, h))


def rrect_mask(size, box, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, r, fill=255)
    return m


def fill(mask, src):
    out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    out.paste(src, (0, 0), mask)
    return out


def bevel(mask, depth, strength=0.55):
    """Light from the top-left: emboss the mask's own edges."""
    b = mask.filter(ImageFilter.GaussianBlur(depth))
    shifted_lo = shift(b, depth // 2, depth // 2)
    shifted_hi = shift(b, -depth // 2, -depth // 2)
    light = ImageChops.subtract(b, shifted_lo)   # top-left edges
    shade = ImageChops.subtract(b, shifted_hi)   # bottom-right edges
    hi = Image.new("RGBA", mask.size, (255, 240, 200, 0))
    hi.putalpha(ImageChops.multiply(light.point(lambda v: min(255, int(v * 3 * strength))), mask))
    lo = Image.new("RGBA", mask.size, (60, 20, 0, 0))
    lo.putalpha(ImageChops.multiply(shade.point(lambda v: min(255, int(v * 3 * strength))), mask))
    return hi, lo


def outline(mask, width, col=INK):
    grown = mask.filter(ImageFilter.MaxFilter(width * 2 + 1))
    o = Image.new("RGBA", mask.size, col[:3] + (0,))
    o.putalpha(grown)
    return o


def steel(size, mask, top=ORANGE_TOP, bot=ORANGE_BOT, depth=14, line=5):
    """Orange-painted steel: gradient + bevel + dark outline + top sheen."""
    base = fill(mask, vgrad(size, top, bot))
    hi, lo = bevel(mask, depth)
    base.alpha_composite(lo)
    base.alpha_composite(hi)
    out = outline(mask, line)
    out.alpha_composite(base)
    return out


def shift(m, dx, dy):
    """Move an L image without wrapping round the edges (ImageChops.offset wraps)."""
    out = Image.new("L", m.size, 0)
    out.paste(m, (dx, dy))
    return out


def drop_shadow(im, blur, off, alpha=150):
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(shift(a, *off))
    sh.alpha_composite(im)
    return sh


def hazard(size, stripe=26, angle_dir=1):
    w, h = size
    im = Image.new("RGBA", size, (255, 200, 30, 255))
    d = ImageDraw.Draw(im)
    for x in range(-h - stripe * 2, w + h, stripe * 2):
        d.polygon([(x, 0), (x + stripe, 0), (x + stripe + h * angle_dir, h), (x + h * angle_dir, h)], fill=(30, 22, 16, 255))
    return im


def bolt(r):
    S = r * 2 * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=INK)
    d.ellipse([S * 0.12, S * 0.12, S * 0.88, S * 0.88], fill=(150, 150, 160, 255))
    d.ellipse([S * 0.18, S * 0.14, S * 0.8, S * 0.72], fill=(214, 216, 224, 255))
    d.line([(S * 0.32, S * 0.5), (S * 0.68, S * 0.5)], fill=(90, 90, 100, 255), width=max(2, S // 9))
    d.ellipse([S * 0.26, S * 0.2, S * 0.46, S * 0.36], fill=(255, 255, 255, 200))
    return im.resize((r * 2, r * 2), Image.LANCZOS)


def lamp(r, col):
    S = r * 2
    im = Image.new("RGBA", (S * 3, S * 3), (0, 0, 0, 0))
    glow = Image.new("L", im.size, 0)
    ImageDraw.Draw(glow).ellipse([S * 0.6, S * 0.6, S * 2.4, S * 2.4], fill=170)
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.35))
    g = Image.new("RGBA", im.size, col + (0,))
    g.putalpha(glow)
    im.alpha_composite(g)
    d = ImageDraw.Draw(im)
    c = S * 1.5
    d.ellipse([c - r - 3, c - r - 3, c + r + 3, c + r + 3], fill=INK)
    d.ellipse([c - r, c - r, c + r, c + r], fill=tuple(min(255, v + 40) for v in col) + (255,))
    d.ellipse([c - r * 0.55, c - r * 0.7, c + r * 0.1, c - r * 0.1], fill=(255, 255, 255, 210))
    return im


def window(size, box, r):
    """Navy display window with an inner shadow, punched into a plate."""
    m = rrect_mask(size, box, r)
    win = fill(m, vgrad(size, NAVY_TOP, NAVY_BOT))
    inner = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(17)).filter(ImageFilter.GaussianBlur(6)))
    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    sh.putalpha(inner.point(lambda v: int(v * 0.8)))
    win.alpha_composite(sh)
    rim = outline(m, 4)
    rim.alpha_composite(win)
    # glass sheen across the top third
    sheen = Image.new("L", size, 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(sheen).rounded_rectangle([x0 + 10, y0 + 6, x1 - 10, y0 + (y1 - y0) * 0.32], r, fill=38)
    s = Image.new("RGBA", size, (255, 255, 255, 0))
    s.putalpha(ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(4)), m))
    rim.alpha_composite(s)
    return rim


# --- frame ---------------------------------------------------------------------

def build_frame(name, gw, gh, side, top, bottom, radius, scale=1.0):
    W, H = gw + 2 * side, gh + top + bottom
    size = (W, H)
    outer = rrect_mask(size, [6, 6, W - 7, H - 7], radius)
    hole = rrect_mask(size, [side, top, side + gw - 1, top + gh - 1], int(14 * scale))
    body_mask = ImageChops.subtract(outer, hole)
    frame = steel(size, body_mask, depth=int(16 * scale), line=max(4, int(6 * scale)))

    # hazard-striped pillar inlays on both sides
    pw = int(side * 0.42)
    for x in (int(side * 0.3), W - int(side * 0.3) - pw):
        ph = H - int(top * 1.2) - int(bottom * 1.2)
        strip = hazard((pw, ph), stripe=int(18 * scale))
        m = rrect_mask((pw, ph), [0, 0, pw - 1, ph - 1], pw // 3)
        s = fill(m, strip)
        o = outline(m, 3)
        o.alpha_composite(s)
        frame.alpha_composite(o, (x, int(top * 1.2)))

    # dark lip round the window
    lip = ImageChops.subtract(rrect_mask(size, [side - 8, top - 8, side + gw + 7, top + gh + 7], int(20 * scale)), hole)
    lipc = Image.new("RGBA", size, (24, 12, 6, 0))
    lipc.putalpha(lip)
    frame.alpha_composite(lipc)

    # bolts on the corners and along the rails
    br = max(7, int(11 * scale))
    b = bolt(br)
    for x in (side * 0.5, W - side * 0.5):
        for y in (top * 0.5, H - bottom * 0.5):
            frame.alpha_composite(b, (int(x - br), int(y - br)))
    n = 6
    for i in range(1, n):
        x = side + gw * i / n
        for y in (top * 0.5, H - bottom * 0.5):
            frame.alpha_composite(b, (int(x - br), int(y - br)))

    # signal lamps on the top rail
    lr = max(7, int(10 * scale))
    for i, col in enumerate([(80, 255, 90), (255, 170, 40), (255, 70, 60), (80, 190, 255)]):
        x = side + gw * (0.5 / 4 + i / 4) + gw / 8 * (1 if i % 2 else -1) * 0.5
        lm = lamp(lr, col)
        frame.alpha_composite(lm, (int(x - lm.width / 2), int(top * 0.5 - lm.height / 2)))

    frame = drop_shadow(frame, 10, (0, 8), 140)
    frame.save(OUT / f"{name}.png", optimize=True)
    print(f"{name}.png {W}x{H}  opening at ({side},{top}) {gw}x{gh}")
    return W, H, side, top


# --- logo ----------------------------------------------------------------------

def text_layer(text, font, fill_top, fill_bot, stroke=10, extrude=10, tracking=0, wobble=0.0):
    """Bubbly 3D lettering: per-letter bounce + tilt, gradient face, thick ink
    stroke, an extruded darker side and a glossy top highlight."""
    letters = []
    x = 0
    for i, ch in enumerate(text):
        l, t, r, bt = font.getbbox(ch)
        w, h = r - l, bt - t
        pad = stroke + extrude + 8
        cw, chh = w + pad * 2, h + pad * 2
        m = Image.new("L", (cw, chh), 0)
        ImageDraw.Draw(m).text((pad - l, pad - t), ch, font=font, fill=255)
        rot = math.sin(i * 1.7) * 6 * wobble
        dy = math.sin(i * 1.3 + 0.5) * 10 * wobble
        m = m.rotate(rot, resample=Image.BICUBIC, expand=False)
        letters.append((m, x, dy))
        x += w + tracking
    total_w = x - tracking
    H = max(m.height for m, _, _ in letters) + 30
    W = total_w + (stroke + extrude + 8) * 2 + 10
    face_m = Image.new("L", (W, H), 0)
    for m, lx, dy in letters:
        face_m.paste(ImageChops.lighter(face_m.crop((lx, int(15 + dy), lx + m.width, int(15 + dy) + m.height)), m),
                     (lx, int(15 + dy)))
    # extrusion
    ext = Image.new("L", (W, H), 0)
    for k in range(1, extrude + 1):
        ext = ImageChops.lighter(ext, shift(face_m, 0, k))
    stroke_m = ImageChops.lighter(face_m, ext).filter(ImageFilter.MaxFilter(stroke * 2 + 1))
    out = Image.new("RGBA", (W, H), INK[:3] + (0,))
    out.putalpha(stroke_m)
    side = Image.new("RGBA", (W, H), tuple(int(c * 0.55) for c in fill_bot) + (0,))
    side.putalpha(ext)
    out.alpha_composite(side)
    face = fill(face_m, vgrad((W, H), fill_top, fill_bot))
    out.alpha_composite(face)
    # gloss: top half of each glyph, softened
    # gloss: a thin rim of light along each glyph's upper edge
    gloss_m = ImageChops.subtract(face_m, shift(face_m, 0, int(H * 0.05)))
    gloss = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    gloss.putalpha(gloss_m.filter(ImageFilter.GaussianBlur(2)).point(lambda v: int(v * 0.55)))
    out.alpha_composite(gloss)
    return out.crop(out.getbbox())


def eyeball(d):
    S = d * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, S - 1, S - 1], fill=INK)
    dr.ellipse([S * 0.07, S * 0.07, S * 0.93, S * 0.93], fill=(255, 250, 236, 255))
    dr.ellipse([S * 0.28, S * 0.3, S * 0.78, S * 0.8], fill=(255, 120, 20, 255))
    dr.ellipse([S * 0.38, S * 0.4, S * 0.68, S * 0.7], fill=(30, 12, 4, 255))
    dr.ellipse([S * 0.44, S * 0.42, S * 0.54, S * 0.52], fill=(255, 255, 255, 240))
    # angry lid
    dr.chord([S * 0.05, S * -0.25, S * 0.95, S * 0.45], 0, 180, fill=(230, 90, 10, 255), outline=INK, width=S // 18)
    return im.resize((d, d), Image.LANCZOS)


def build_logo():
    f1 = ImageFont.truetype(FONT, 190)
    f2 = ImageFont.truetype(FONT, 168)
    top = text_layer("MONSTER", f1, (255, 170, 60), (232, 70, 10), stroke=12, extrude=12, tracking=-2, wobble=1.0)
    bot = text_layer("FACTORY", f2, (255, 244, 120), (255, 176, 20), stroke=12, extrude=12, tracking=-2, wobble=0.8)
    W = max(top.width, bot.width) + 60
    H = top.height + bot.height - 30 + 40
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(bot, ((W - bot.width) // 2, top.height - 30))
    out.alpha_composite(top, ((W - top.width) // 2, 10))
    # the O of MONSTER becomes a monster eye
    f = ImageFont.truetype(FONT, 190)
    m_w = f.getbbox("M")[2] - f.getbbox("M")[0] - 2
    o_box = f.getbbox("O")
    ow = o_box[2] - o_box[0]
    ex = (W - top.width) // 2 + 12 + 8 + 12 + m_w + int(ow * 0.5)
    ey = 10 + int(top.height * 0.5)
    e = eyeball(int(ow * 0.78))
    out.alpha_composite(e, (ex - e.width // 2, ey - e.height // 2 + 4))
    out = drop_shadow(out, 10, (0, 10), 160)
    out = out.crop(out.getbbox())
    out = out.resize((760, round(out.height * 760 / out.width)), Image.LANCZOS)
    out.save(OUT / "logo.png", optimize=True)
    print(f"logo.png {out.size}")


# --- plates --------------------------------------------------------------------

def build_buy_bonus():
    W, H = 520, 470
    size = (W, H)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    # red push button on top
    bx, by, br = W // 2, 92, 74
    housing = steel(size, rrect_mask(size, [bx - 120, by - 6, bx + 120, by + 70], 26), top=(150, 156, 170), bot=(80, 84, 96), depth=8, line=5)
    im.alpha_composite(housing)
    btn = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(btn)
    d.ellipse([bx - br - 6, by - br * 0.7 - 6, bx + br + 6, by + br * 0.7 + 6], fill=INK)
    d.ellipse([bx - br, by - br * 0.7, bx + br, by + br * 0.7], fill=(222, 30, 30, 255))
    d.ellipse([bx - br * 0.7, by - br * 0.6, bx + br * 0.3, by - br * 0.05], fill=(255, 140, 130, 200))
    im.alpha_composite(btn.filter(ImageFilter.GaussianBlur(0.6)))
    # plate
    pm = rrect_mask(size, [14, 150, W - 15, H - 16], 40)
    plate = steel(size, pm, depth=14, line=6)
    im.alpha_composite(plate)
    for x in (14 + 10, W - 15 - 10 - 26):
        strip = hazard((26, H - 150 - 16 - 60), stripe=14)
        sm = rrect_mask(strip.size, [0, 0, 25, strip.height - 1], 8)
        s = outline(sm, 3)
        s.alpha_composite(fill(sm, strip))
        im.alpha_composite(s, (x, 180))
    win = (66, 190, W - 66, H - 52)
    im.alpha_composite(window(size, win, 22))
    b = bolt(9)
    for x, y in ((40, 170), (W - 58, 170), (40, H - 46), (W - 58, H - 46)):
        im.alpha_composite(b, (x, y))
    im = drop_shadow(im, 10, (0, 8), 150)
    im.save(OUT / "buy_bonus.png", optimize=True)
    inset = (win[1] / H * 100, (W - win[2]) / W * 100, (H - win[3]) / H * 100, win[0] / W * 100)
    print("buy_bonus.png", size, "--buy-panel: %.1f%% %.1f%% %.1f%% %.1f%%" % inset)


def build_plate_counter():
    W, H = 480, 360
    size = (W, H)
    pm = rrect_mask(size, [10, 10, W - 11, H - 11], 46)
    im = steel(size, pm, depth=14, line=6)
    strip = hazard((W - 120, 30), stripe=16)
    sm = rrect_mask(strip.size, [0, 0, strip.width - 1, 29], 10)
    s = outline(sm, 3)
    s.alpha_composite(fill(sm, strip))
    im.alpha_composite(s, (60, H - 62))
    win = (52, 54, W - 52, H - 80)
    im.alpha_composite(window(size, win, 26))
    for i, col in enumerate([(80, 255, 90), (255, 70, 60)]):
        lm = lamp(9, col)
        im.alpha_composite(lm, ((40 if i == 0 else W - 40) - lm.width // 2, 32 - lm.height // 2))
    b = bolt(8)
    for x, y in ((28, H - 52), (W - 44, H - 52)):
        im.alpha_composite(b, (x, y))
    im = drop_shadow(im, 10, (0, 8), 150)
    im.save(OUT / "plate_counter.png", optimize=True)
    cy = (win[1] + win[3]) / 2
    print("plate_counter.png", size, "window y %.1f%%..%.1f%% (label ~%.0f%%, value ~%.0f%%)" % (
        win[1] / H * 100, win[3] / H * 100, (win[1] + (win[3] - win[1]) * 0.24) / H * 100,
        (win[1] + (win[3] - win[1]) * 0.62) / H * 100))


def build_plate_amount():
    W, H = 900, 250
    size = (W, H)
    pm = rrect_mask(size, [10, 30, W - 11, H - 31], 90)
    im = steel(size, pm, depth=14, line=6)
    for x in (24, W - 24 - 70):
        strip = hazard((70, H - 100), stripe=14)
        sm = rrect_mask(strip.size, [0, 0, 69, strip.height - 1], 30)
        s = outline(sm, 3)
        s.alpha_composite(fill(sm, strip))
        im.alpha_composite(s, (x, 50))
    win = (110, 54, W - 110, H - 56)
    im.alpha_composite(window(size, win, 60))
    # goo drips under the bar
    d = Image.new("RGBA", size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(d)
    for x, h in ((240, 30), (520, 22), (690, 34)):
        dd.rounded_rectangle([x - 12, H - 40, x + 12, H - 40 + h], 12, fill=INK)
        dd.rounded_rectangle([x - 8, H - 40, x + 8, H - 42 + h], 9, fill=(120, 255, 60, 255))
    d.alpha_composite(im)
    im = drop_shadow(d, 10, (0, 8), 150)
    im.save(OUT / "plate_amount.png", optimize=True)
    print("plate_amount.png", size, "ratio %.2f" % (W / H))


def main(argv):
    want = set(argv) or {"frame", "logo", "buy", "counter", "amount"}
    OUT.mkdir(parents=True, exist_ok=True)
    if "frame" in want:
        build_frame("frame_desk", 968, 660, 62, 74, 74, 46, 1.0)
        build_frame("frame_mob", 662, 534, 46, 58, 58, 36, 0.8)
    if "logo" in want:
        build_logo()
    if "buy" in want:
        build_buy_bonus()
    if "counter" in want:
        build_plate_counter()
    if "amount" in want:
        build_plate_amount()


if __name__ == "__main__":
    main(sys.argv[1:])
