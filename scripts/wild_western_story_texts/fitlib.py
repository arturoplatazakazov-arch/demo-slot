# Shared text drawing + fixed-size fit for the Wild Western Story preview screens.
# Product rule (2026-11-12): the engine never resizes plaques or fonts per language, so every
# field gets ONE font size at which EN and every translation fit its box.
# Used by doc.py (texts table) and by ../wild_western_story_screens.py (the screens themselves,
# in EN and in every language), so a string is measured exactly as it is drawn.
#
# Fonts: the game's own Rye and Luckiest Guy have no Cyrillic at all (and the shipped rye
# latin-ext subset has 27 glyphs, so PL/TR/AZ already fell back to a system font), so the
# localised build swaps them for Bitter 900 (titles) and Shantell Sans 800 (body) — the same
# subsets front/css/fonts.css declares for the web. Arial Black stays as a safety net.
import os, re, sys, itertools
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from spine_screen_kit import hexc, vgrad   # noqa: E402
from texts import TEXTS, FIELDS, WHERE, GROUPS, NOT_TRANSLATED   # noqa: E402
from translations import TR, LANGS         # noqa: E402

SLUG, NAME = 'wild_western_story', 'Wild Western Story'
GEN = 'scripts/wild_western_story_screens.py'
F = os.path.join(HERE, 'fonts')
ARIAL_BLACK = '/System/Library/Fonts/Supplemental/Arial Black.ttf'
# style: (name in the table, font file prefix in fonts/, wght axis or None, wide stand-in)
FAM = {'title': ('Bitter 900', 'bitter', None, ARIAL_BLACK),
       'body': ('Shantell Sans 800', 'shantell-sans', None, ARIAL_BLACK)}
FAM_USE = {'title': 'заголовки', 'body': 'описания, подсказки, YOU HAVE WON'}
FILLS = {'title': [(0, hexc('fff6c8')), (0.42, hexc('ffd04a')), (0.7, hexc('e8931a')), (1, hexc('9c4a0c'))],
         'body': [(0, hexc('fffaf0')), (1, hexc('f3d9a6'))]}
SHEET_BG, TILE_BG = (20, 10, 4), (52, 30, 14)
HDR = '#2A1204'

FILES = {st: sorted((os.path.join(F, n) for n in os.listdir(F) if n.startswith(base + '-latin')),
                    key=lambda p: '-ext' in p) for st, (_, base, _, _) in FAM.items()}
CMAPS = {p: set(TTFont(p).getBestCmap()) for fs in FILES.values() for p in fs}
_fc = {}


def fnt(path, size, wght=None):
    k = (path, size)
    if k not in _fc:
        f = ImageFont.truetype(path, size)
        if wght:
            try: f.set_variation_by_axes([wght])
            except Exception: pass
        _fc[k] = f
    return _fc[k]


def has_glyph(ch, style):
    return any(ord(ch) in CMAPS[p] for p in FILES[style])


def font_for(ch, style, size):
    """Game font file that has the glyph (latin, then latin-ext), else the wide stand-in."""
    _, _, w, proxy = FAM[style]
    for p in FILES[style]:
        if ord(ch) in CMAPS[p]: return fnt(p, size, w)
    return fnt(proxy, size)


def line_w(text, style, size):
    return sum(font_for(ch, style, size).getlength(ch) for ch in text)


def text_line(text, style, size, fill, stroke, stroke_w, glow, glow_r, shadow):
    """wild_western_story_screens.text_line, but the font is picked per character (shared
    baseline): glow, hard drop shadow `shadow` px down, stroke, gradient fill, carved top
    highlight."""
    pad = stroke_w + glow_r * 3 + 16
    fs = [font_for(ch, style, size) for ch in text]
    widths = [f.getlength(ch) for f, ch in zip(fs, text)]
    w = int(sum(widths)) + pad * 2; h = int(size * 1.6) + pad * 2
    mask, smask = Image.new('L', (w, h)), Image.new('L', (w, h))
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x, base = pad, pad + int(size * 1.15)
    for ch, f, cw in zip(text, fs, widths):
        d.text((x, base), ch, font=f, fill=255, anchor='ls')
        ds.text((x, base), ch, font=f, fill=255, stroke_width=stroke_w, stroke_fill=255, anchor='ls')
        x += cw
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(glow_r)).point(lambda a: min(255, int(a * 1.5)))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    if shadow:
        sh = smask.transform(smask.size, Image.AFFINE, (1, 0, 0, 0, 1, -shadow))
        out.paste(Image.new('RGBA', (w, h), (20, 8, 2, 230)), (0, 0), sh)
    out.paste(Image.new('RGBA', (w, h), hexc(stroke)), (0, 0), smask)
    bb = mask.getbbox() or (0, 0, w, h)
    fill_im = Image.new('RGBA', (w, h)); fill_im.paste(vgrad((w, max(1, bb[3] - bb[1])), fill), (0, bb[1]))
    out.paste(fill_im, (0, 0), mask)
    hl = ImageChops.subtract(mask, mask.transform(mask.size, Image.AFFINE, (1, 0, 0, 0, 1, -max(1, size // 28))))
    out.paste(Image.new('RGBA', (w, h), (255, 255, 240, 170)), (0, 0), hl)
    return out.crop(out.getchannel('A').getbbox())


def render(key, lines):
    """The block exactly as the screens draw it: every line its own trimmed image, centred,
    int(size * 0.12) apart."""
    t = TEXTS[key]; px = t['px']; st = t['style']
    ims = [text_line(l, st, px, FILLS[st], '2a1204', max(2, px // 9), t['glow'],
                     t['glow_r'] if t['glow_r'] is not None else max(4, px // 6), max(2, px // 14))
           for l in lines]
    if len(ims) == 1: return ims[0]
    gap = int(px * 0.12); w = max(i.width for i in ims); h = sum(i.height for i in ims) + gap * (len(ims) - 1)
    out = Image.new('RGBA', (w, h)); y = 0
    for im in ims: out.alpha_composite(im, ((w - im.width) // 2, y)); y += im.height + gap
    return out


_ic = {}


def draw(key, lines):
    k = (key, tuple(lines))
    if k not in _ic: _ic[k] = render(key, lines)
    return _ic[k]


# --- line breaking --------------------------------------------------------------------------
# Never break inside "3 / 4 / 5", "x2 - x8", around "=", or between a number and the word it
# counts ("20 SPINS", "3+ SCATTERS"), nor after a 1-2 letter word (preposition).
# '\n' in a text is a mandatory break.
G = '⁠'


def words(s):
    s = s.replace(' / ', G + '/' + G).replace(' - ', G + '-' + G).replace('= ', '=' + G).replace(' =', G + '=')
    s = re.sub(r'(?<=x\d)( +)(?=x\d)', lambda m: G * len(m.group(1)), s)            # x2 x3 x5 x7
    s = re.sub(r'(?:(?<=[\s⁠])|^)([+]?\d+[x+X]?)( )(?=\S)', lambda m: m.group(1) + G, s)  # 20 SPINS, 3+ SCATTERS
    s = re.sub(r'(?:(?<=\s)|^)([^\W\d_]{1,2})( )(?=\S)', lambda m: m.group(1) + G, s)   # no hanging "ДО", "В", "Z"
    out, hard = [], set()
    for seg_i, seg in enumerate(s.split('\n')):
        if seg_i: hard.add(len(out))
        out += [w.replace(G, ' ') for w in seg.split(' ') if w]
    return out, hard


def splits(ws, hard, n):
    for cut in itertools.combinations(range(1, len(ws)), n - 1):
        if not hard <= set(cut): continue
        b = (0,) + cut + (len(ws),)
        yield [' '.join(ws[b[i]:b[i + 1]]) for i in range(n)]


def best(key, text, bw, bh, max_lines):
    """(scale fitting bw x bh, lines) over the narrowest split per line count."""
    t = TEXTS[key]; ws, hard = words(text); out = None
    for n in range(len(hard) + 1, min(max_lines, len(ws)) + 1):
        cands = list(splits(ws, hard, n))
        if not cands: continue
        ls = min(cands, key=lambda L: max(line_w(x, t['style'], t['px']) for x in L))
        im = draw(key, ls); s = min(bw / im.width, bh / im.height)
        if out is None or s > out[0] + 1e-9: out = (s, ls)
    return out


def fields():
    """One record per text field: its box, the EN scale, and the one fixed scale that fits EN
    and every translation. `s` is design px per image px of draw()."""
    recs = []
    for fd in FIELDS:
        key = fd['key']; t = TEXTS[key]; en = draw(key, t['en_lines'])
        s_en = fd['slot'](en.width, en.height) / en.width     # design px per image px, as in the game
        bw = fd['box_w']; bh = fd['bh'] if fd['bh'] else en.height * s_en * fd['hk']
        nl = fd.get('max_lines') or len(t['en_lines']) + 1
        fixed, limit = s_en, 'en'
        for L in LANGS:
            s, _ = best(key, TR[L][key], bw, bh, nl)
            if s < fixed: fixed, limit = s, L
        recs.append(dict(screen=fd['screen'], dev=fd['dev'], key=key, bone=fd['bone'],
                         box_w=round(bw), box_h=round(bh), bw=bw, bh=bh,
                         en_px=round(t['px'] * s_en), px=round(t['px'] * fixed, 1), k=fixed / s_en,
                         limit=limit, s=fixed, s_en=s_en, nl=nl))
    for screen, dev, keys in GROUPS:          # one size per row of cards
        grp = [r for r in recs if r['screen'] == screen and r['dev'] == dev and r['key'] in keys]
        if not grp: continue
        lead = min(grp, key=lambda r: r['s'])
        for r in grp:
            r['s'], r['limit'] = lead['s'], lead['limit'] if r is not lead else r['limit']
            r['px'], r['k'] = round(TEXTS[r['key']]['px'] * r['s'], 1), r['s'] / r['s_en']
    return recs


def lines_for(key, lang, rec):
    """How the string is broken in that field (EN keeps the art's own break)."""
    if lang == 'en': return TEXTS[key]['en_lines']
    return best(key, TR[lang][key], rec['bw'], rec['bh'], rec['nl'])[1]


def block(key, lang, rec):
    """(image, scale) for the field: the text at the field's fixed size."""
    return draw(key, lines_for(key, lang, rec)), rec['s']
