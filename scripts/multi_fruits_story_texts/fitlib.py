# Shared text drawing + fixed-size fit for the Multi Fruits Story preview screens.
# Product rule (2026-11-12): the engine never resizes plaques or fonts per language, so every
# field gets ONE font size at which EN and every translation fit its box.
# Used by doc.py (texts table) and by ../multi_fruits_story_screens.py (the screens themselves,
# in EN and in every language), so a string is measured exactly as it is drawn.
import os, re, sys, itertools
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from spine_screen_kit import hexc, vgrad, trim        # noqa: E402
from texts import TEXTS, FIELDS, WHERE, GROUPS        # noqa: E402
from translations import TR, LANGS                    # noqa: E402

F = os.path.join(HERE, 'fonts')
SUP = '/System/Library/Fonts/Supplemental/'
# --- the game: fonts and text styles exactly as multi_fruits_story_screens.py draws them -----
# Luckiest Guy -> Shantell Sans 800 and Baloo 2 -> Nunito 900: the originals have no Cyrillic,
# these subsets cover all 12 client languages (the same files front/fonts serves the game).
# The Arial stand-ins stay as a safety net for a glyph a subset might still miss: the widest
# first (a conservative fit), then one that covers the rest (Arial Black has no Kazakh
# Ң Ө Ұ Ү or Azerbaijani Ə).
# style: (name in the table, font file prefix in fonts/, wght axis or None, stand-ins)
FAM = {'title': ('Shantell Sans 800', 'shantell-sans', 800, [SUP + 'Arial Black.ttf', SUP + 'Arial Bold.ttf']),
       'caption': ('Nunito 900', 'nunito', 900, [SUP + 'Arial Bold.ttf'])}
FILLS = {'gold': [(0, hexc('fffbd0')), (0.45, hexc('ffd23a')), (1, hexc('f08a00'))],
         'cream': [(0, hexc('ffffff')), (1, hexc('fff0c8'))],
         'lime': [(0, hexc('f6ffd0')), (0.5, hexc('b8f04a')), (1, hexc('4fae1c'))]}
INK = '3a1a06'

FILES = {st: [os.path.join(F, n) for n in sorted(os.listdir(F)) if n.startswith(base + '-latin')]
         for st, (_, base, _, _) in FAM.items()}   # latin, latin-ext
for st in FILES: FILES[st].sort(key=lambda p: '-ext' in p)
CMAPS = {p: set(TTFont(p).getBestCmap()) for fs in FILES.values() for p in fs}
PROXY_CMAPS = {p: set(TTFont(p).getBestCmap()) for _, _, _, ps in FAM.values() for p in ps}
_fc = {}


def fnt(path, size, wght=None):
    k = (path, size, wght)
    if k not in _fc:
        f = ImageFont.truetype(path, size)
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
    """Characters the game's own font files do not have (drawn with a stand-in)."""
    return ''.join(sorted({c for c in text if c not in '  \n' and not font_for(c, style, 20)[1]}))


def line_w(text, style, size):
    return sum(font_for(ch, style, size)[0].getlength(ch) for ch in text)


def text_img(text, style, size, fill, stroke, stroke_w, glow, glow_r, shadow):
    """spine_screen_kit.text_img, but the font is picked per character (shared baseline)."""
    pad = stroke_w + glow_r * 3 + 12
    fs = [font_for(ch, style, size)[0] for ch in text]
    widths = [f.getlength(ch) for f, ch in zip(fs, text)]
    w = int(sum(widths)) + pad * 2; h = int(size * 1.4) + pad * 2
    mask, smask = Image.new('L', (w, h)), Image.new('L', (w, h))
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x, base = pad, pad + int(size * 1.05)
    for ch, f, cw in zip(text, fs, widths):
        d.text((x, base), ch, font=f, fill=255, anchor='ls')
        ds.text((x, base), ch, font=f, fill=255, stroke_width=stroke_w, stroke_fill=255, anchor='ls')
        x += cw
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(glow_r)).point(lambda a: min(255, int(a * 1.5)))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    if shadow:
        sh = ImageChops.offset(smask.filter(ImageFilter.GaussianBlur(max(1, size // 18))), 0, max(2, size // 14))
        out.paste(Image.new('RGBA', (w, h), hexc(shadow, 200)), (0, 0), sh)
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


def render(key, lines):
    """The block exactly as multi_fruits_story_screens.py draws it: title() (Shantell Sans 800,
    ink stroke, optional glow) for titles, lines() (Nunito 900 cream) for captions."""
    t = TEXTS[key]; px = t['px']
    if t['style'] == 'title':
        ims = [text_img(l, 'title', px, FILLS[t['fill']], INK, max(3, px // 9), t['glow'], max(5, px // 6), '1a0c02')
               for l in lines]
        return stack(ims, int(px * 1.12))   # titles: a hair more leading between two lines
    ims = [text_img(l, 'caption', px, FILLS['cream'], INK, max(3, px // 8), None, 0, '1a0c02') for l in lines]
    return stack(ims, int(px * (1 + t['gap'])))


_ic = {}


def draw(key, lines):
    k = (key, tuple(lines))
    if k not in _ic: _ic[k] = render(key, lines)
    return _ic[k]


# --- line breaking --------------------------------------------------------------------------
# Never break inside "3 / 4 / 5", "x2 - x8", "x2 x3 x5 x7", around "=", or between a number
# and the word it counts ("7 SPINS", "+7 SPINS"), nor after a 1-2 letter word (preposition).
# '\n' in a text is a mandatory break.
G = '⁠'


def words(s):
    s = s.replace(' / ', G + '/' + G).replace(' - ', G + '-' + G).replace('= ', '=' + G).replace(' =', G + '=')
    s = re.sub(r'(?<=x\d)( +)(?=x\d)', lambda m: G * len(m.group(1)), s)            # x2 x3 x5 x7
    s = re.sub(r'(?:(?<=[\s⁠])|^)([+]?\d+[x+]?)( )(?=\S)', lambda m: m.group(1) + G, s)  # 7 SPINS
    s = re.sub(r'(?:(?<=\s)|^)([^\W\d_]{1,2})( )(?=\S)', lambda m: m.group(1) + G, s)   # no hanging "ДО", "В"
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
        s_en = fd['slot'](en.width, en.height) / en.width      # design px per image px, as in the game
        bw = fd['box_w']; bh = fd['bh'] if fd['bh'] else en.height * s_en * fd['hk']
        nl = t.get('max_lines', len(t['en_lines']) + 1)
        fixed, limit = s_en, 'en'
        for L in LANGS:
            sc, _ = best(key, TR[L][key], bw, bh, nl)
            if sc < fixed: fixed, limit = sc, L
        recs.append(dict(screen=fd['screen'], dev=fd['dev'], key=key, bone=fd['bone'],
                         box_w=round(bw), box_h=round(bh), en_px=round(t['px'] * s_en),
                         px=round(t['px'] * fixed, 1), k=fixed / s_en, limit=limit,
                         s=fixed, s_en=s_en, nl=nl, bw=bw, bh=bh))
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
