# Shared text drawing + fixed-size fit for the East Discovery info screens.
# Product rule (2026-11-12): the engine never resizes plaques or fonts per language, so every
# field gets ONE font size at which EN and every translation fit its box.
# Used by doc.py (texts table) and by ../east_discovery_screens.py (the screens themselves, in
# EN and in every language), so a string is measured exactly as it is drawn.
import os, sys, itertools
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from spine_screen_kit import hexc, vgrad, trim   # noqa: E402
from texts import TEXTS, FIELDS                  # noqa: E402
from translations import TR, LANGS               # noqa: E402

F = os.path.join(HERE, 'fonts')
SUP = '/System/Library/Fonts/Supplemental/'
# style -> (name, font-file prefix, weight axis, stand-ins for glyphs the game font lacks:
# the widest first (a conservative fit), then one that covers the rest — Arial Black has no
# Kazakh Ң Ө Ұ Ү and no Azerbaijani Ə).
FAM = {'title': ('Luckiest Guy', 'luckiest-guy', None, [SUP + 'Arial Black.ttf', SUP + 'Arial Bold.ttf']),
       'tap': ('Luckiest Guy', 'luckiest-guy', None, [SUP + 'Arial Black.ttf', SUP + 'Arial Bold.ttf']),
       'desc': ('Fredoka 600', 'fredoka', 600, [SUP + 'Arial Bold.ttf'])}
FILES = {st: [os.path.join(F, n) for n in sorted(os.listdir(F)) if n.startswith(base + '-latin')]
         for st, (_, base, _, _) in FAM.items()}   # latin, latin-ext
for st in FILES: FILES[st].sort(key=lambda p: '-ext' in p)
CMAPS = {p: set(TTFont(p).getBestCmap()) for fs in FILES.values() for p in fs}
PROXY_CMAPS = {p: set(TTFont(p).getBestCmap()) for _, _, _, ps in FAM.values() for p in ps}
# The screens' palette, straight from front/css/east-discovery.css (.info-card__title gradient
# #fff6c8 -> #ffd35c -> #d98a1f on a #3a1a06 stroke with a #2b1204 drop shadow).
GOLD = [(0, hexc('fff6c8')), (0.45, hexc('ffd35c')), (1, hexc('d98a1f'))]
CREAM = [(0, hexc('fffaf0')), (1, hexc('ffe6b4'))]
STROKE, SHADOW = '3a1a06', '2b1204'
_fc = {}


def fnt(path, size, wght=None):
    k = (path, round(size, 2))
    if k not in _fc:
        f = ImageFont.truetype(path, max(4, int(round(size))))
        if wght:
            try: f.set_variation_by_axes([wght])
            except Exception: pass
        _fc[k] = f
    return _fc[k]


def font_for(ch, style, size):
    """Game font file that has the glyph (latin, then latin-ext), else a stand-in."""
    _, _, w, proxies = FAM[style]
    for p in FILES[style]:
        if ord(ch) in CMAPS[p]: return fnt(p, size, w), True
    for p in proxies:
        if ord(ch) in PROXY_CMAPS[p]: return fnt(p, size), False
    return fnt(proxies[-1], size), False


def missing(text, style):
    return ''.join(sorted({c for c in text if c not in '  \n' and not font_for(c, style, 20)[1]}))


def text_img(text, style, size, fill, stroke, stroke_w, glow, glow_r, shadow):
    """One line, with the font picked per character."""
    pad = stroke_w + (glow_r * 3 if glow else 0) + 12
    fs = [font_for(ch, style, size)[0] for ch in text]
    widths = [f.getlength(ch) for f, ch in zip(fs, text)]
    w = int(sum(widths)) + pad * 2; h = int(size * 1.6) + pad * 2
    mask, smask = Image.new('L', (w, h)), Image.new('L', (w, h))
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x = pad
    for ch, f, cw in zip(text, fs, widths):
        d.text((x, pad), ch, font=f, fill=255)
        ds.text((x, pad), ch, font=f, fill=255, stroke_width=stroke_w, stroke_fill=255)
        x += cw
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(glow_r)).point(lambda a: min(255, int(a * 1.4)))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    if shadow:
        sh = ImageChops.offset(smask, 0, max(2, int(size // 11)))
        out.paste(Image.new('RGBA', (w, h), hexc(shadow)), (0, 0), sh)
    out.paste(Image.new('RGBA', (w, h), hexc(stroke)), (0, 0), smask)
    bb = mask.getbbox() or (0, 0, w, h)
    fill_im = Image.new('RGBA', (w, h)); fill_im.paste(vgrad((w, max(1, bb[3] - bb[1])), fill), (0, bb[1]))
    out.paste(fill_im, (0, 0), mask)
    return trim(out, thr=2)


def stack(ims, step):
    w = max(i.width for i in ims); h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims): out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


_ic = {}


def draw(key, lines):
    """The text block exactly as east_discovery_screens.py draws it."""
    k = (key, tuple(lines))
    if k in _ic: return _ic[k]
    t = TEXTS[key]; px = t['px']; st = t['style']
    if st == 'desc':
        ims = [text_img(l, st, px, CREAM, '241003', max(2, px // 8), None, 0, None) for l in lines]
        im = stack(ims, int(px * 1.25))
    else:
        fill = CREAM if st == 'tap' else GOLD
        glow = 'ffcf5c' if st == 'tap' else None
        ims = [text_img(l, st, px, fill, STROKE, max(2, round(px / 14)), glow, max(5, px // 5), SHADOW)
               for l in lines]
        im = stack(ims, int(px * 1.05))
    _ic[k] = im
    return im


GLUE = [(' / ', '⁠/⁠'), (' - ', '⁠-⁠'), ('= ', '=⁠'), (' =', '⁠=')]


def words(s, key=None):
    for a, b in GLUE: s = s.replace(a, b)
    return [w.replace('⁠', ' ') for w in s.replace(' ', ' ').split(' ')]


def splits(ws, n):
    if n == 1: yield [' '.join(ws)]; return
    for cut in itertools.combinations(range(1, len(ws)), n - 1):
        b = (0,) + cut + (len(ws),)
        yield [' '.join(ws[b[i]:b[i + 1]]) for i in range(n)]


def best(key, text, bw, bh, max_lines):
    """(scale fitting bw x bh, lines) over the narrowest split per line count."""
    t = TEXTS[key]; f = font_for('A', t['style'], t['px'])[0]
    ws = words(text, key); out = None
    for n in range(1, min(max_lines, len(ws)) + 1):
        ls = min(splits(ws, n), key=lambda L: max(f.getlength(x) for x in L))
        im = draw(key, ls); s = min(bw / im.width, bh / im.height)
        if out is None or s > out[0]: out = (s, ls)
    return out


def fields():
    """One record per text field: its box, the EN scale, and the one fixed scale that fits EN
    and every translation. `s` is design px per image px of draw()."""
    recs = []
    for screen, dev, key, s_en, bw, bh, nl, bone in FIELDS:
        t = TEXTS[key]
        fixed, limit = s_en, 'en'
        en = draw(key, t['en_lines'])
        if en.width * s_en > bw or en.height * s_en > bh:      # EN art itself must fit the box
            fixed = min(bw / en.width, bh / en.height); limit = 'en'
        for L in LANGS:
            s, _ = best(key, TR[L][key], bw, bh, nl)
            if s < fixed: fixed, limit = s, L
        recs.append(dict(screen=screen, dev=dev, key=key, bone=bone, box_w=bw, box_h=bh,
                         en_px=round(t['px'] * s_en, 1), px=round(t['px'] * fixed, 1),
                         k=fixed / s_en, limit=limit, s=fixed, s_en=s_en, nl=nl))
    return recs


def lines_for(key, lang, rec):
    """How the string is broken in that field (EN keeps the art's own break when it fits)."""
    if lang == 'en':
        en = draw(key, TEXTS[key]['en_lines'])
        if en.width * rec['s'] <= rec['box_w'] + 0.5 and en.height * rec['s'] <= rec['box_h'] + 0.5:
            return TEXTS[key]['en_lines']
        return best(key, TEXTS[key]['en'], rec['box_w'], rec['box_h'], rec['nl'])[1]
    return best(key, TR[lang][key], rec['box_w'], rec['box_h'], rec['nl'])[1]


def block(key, lang, rec):
    """(image, scale) for the field: the text at the field's fixed size."""
    return draw(key, lines_for(key, lang, rec)), rec['s']
