# Shared text measurement for the fixed-size text fields (product 2026-11-12: the engine
# will NOT resize plaques or fonts per language). Every field gets ONE font size that the
# EN copy and every translation in translations.py fit at, inside a fixed box.
# A string is drawn with the same gfx style as its EN art; line breaks are searched
# (up to EN lines + 1, narrowest split per line count). Glyphs the game fonts lack are
# measured with wide stand-ins (Arial Black for Luckiest Guy, Arial Bold for Fredoka).
import os, json, itertools
from PIL import Image
from fontTools.ttLib import TTFont
import gfx
from texts import TEXTS, IMAGES
from translations import TR, LANGS, plain, bold_words

S = os.path.dirname(os.path.abspath(__file__))
LG_FULL = os.path.join(S, 'fonts/luckiest-guy-full.ttf')   # latin + latin-ext merged
FR_LAT = gfx.FR
SUP = '/System/Library/Fonts/Supplemental/'
PROXY = {'Luckiest Guy': SUP + 'Arial Black.ttf', 'Fredoka 650': SUP + 'Arial Bold.ttf'}
CMAP = {'Luckiest Guy': set(TTFont(LG_FULL).getBestCmap()),
        'Fredoka 650': set(TTFont(os.path.join(S, 'fonts/fredoka-latin-849e3a33.ttf')).getBestCmap())
                       | set(TTFont(os.path.join(S, 'fonts/fredoka-latin-ext-20489dbf.ttf')).getBestCmap())}
FR_CMAP = set(TTFont(FR_LAT).getBestCmap())
GOLD = ((255, 250, 225), (255, 222, 120), (246, 170, 30))
PALE = ((255, 255, 240), (255, 236, 160), (255, 200, 70))
SIGN = dict(grad=((255, 250, 205), (255, 214, 80), (240, 150, 10)), line_h=0.95, shadow=4)
SIGN_SHRINK = 0.9
# image -> how gfx.py draws it (function, font px, extra kwargs)
STYLE = {
    't_fs': ('styled', 50, {}), 't_buy': ('styled', 50, {}),
    'd_fs_desk': ('body', 30, {}), 'd_fs_mob': ('body', 30, {}), 'd_buy_desk': ('body', 30, {}), 'd_buy_mob': ('body', 30, {}),
    'cont_desk': ('styled', 44, dict(grad=PALE)), 'cont_mob': ('styled', 50, dict(grad=PALE)),
    'start_desk': ('styled', 44, dict(grad=PALE)), 'start_mob': ('styled', 50, dict(grad=PALE)),
    't_congrats': ('styled', 84, {}), 't_youwon': ('styled', 46, dict(grad=GOLD)), 't_freespins': ('styled', 50, dict(grad=GOLD)),
    'b_fs': ('body', 34, {}),
    'sign_buy': ('styled', 64, SIGN),
}

def font_px(img):
    """Nominal font size of the gfx image (the sign label is drawn smaller)."""
    return STYLE[img][1] * (SIGN_SHRINK if img == 'sign_buy' else 1)

def en_lines(img):
    return IMAGES[img][1]

def draw(img, lines, fam, hi):
    fn, size, kw = STYLE[img]
    covered = all(ord(c) in CMAP[fam] or c in ' \n ' for c in lines)
    if fam == 'Luckiest Guy':
        im = gfx.styled(lines, size, fnt=LG_FULL if covered else PROXY[fam], **kw)
    elif covered and all(ord(c) in FR_CMAP or c in ' \n ' for c in lines):
        im = gfx.body(lines, size, hi=hi, **kw)
    else:   # stand-in (also when only the latin-ext subset has the glyph: PIL cannot mix files)
        im = gfx.body(lines, size, hi=hi, wght=None, fnt=PROXY[fam], **kw)
    if img == 'sign_buy': im = im.resize((int(im.width * SIGN_SHRINK), int(im.height * SIGN_SHRINK)), Image.LANCZOS)
    return im, covered

# image sizes are what the fit needs; drawing is slow (per-pixel gradient), so cache them
_CACHE_P = os.path.join(S, 'gfx', '.fit_cache.json')
try: _CACHE = json.load(open(_CACHE_P))
except Exception: _CACHE = {}

def size_of(img, lines, fam, hi):
    k = '|'.join([img, fam, ','.join(hi), lines])
    if k not in _CACHE:
        im, _ = draw(img, lines, fam, hi); _CACHE[k] = im.size
        os.makedirs(os.path.dirname(_CACHE_P), exist_ok=True)
        json.dump(_CACHE, open(_CACHE_P, 'w'))
    return tuple(_CACHE[k])

def splits(words, n):
    if n == 1: yield [' '.join(words)]; return
    for cut in itertools.combinations(range(1, len(words)), n - 1):
        b = (0,) + cut + (len(words),)
        yield [' '.join(words[b[i]:b[i + 1]]) for i in range(n)]

def candidates(text, img, fam, max_lines):
    _, size, _ = STYLE[img]
    f = gfx.font(LG_FULL if fam == 'Luckiest Guy' else FR_LAT, size, None if fam == 'Luckiest Guy' else 650)
    words = text.split(' ')
    for n in range(1, min(max_lines, len(words)) + 1):
        yield min(splits(words, n), key=lambda ls: max(f.getlength(l) for l in ls))

def best_layout(text, img, fam, fw, fh, max_lines, hi):
    """(scale that fits fw x fh, lines) for the most legible split."""
    out = None
    for ls in candidates(text, img, fam, max_lines):
        w, h = size_of(img, '\n'.join(ls), fam, hi)
        s = min(fw / w, fh / h)
        if out is None or s > out[0]: out = (s, ls)
    return out

def strings(key):
    """(lang, plain text, gold words) for EN + every translation."""
    t = TEXTS[key]
    yield 'en', t['en'], t['hi']
    for L in LANGS: yield L, plain(TR[L][key]), bold_words(TR[L][key])

def common_scale(img, fw, fh, cap):
    """One scale for the gfx image `img` (= EN art) so that EN and all translations fit
    fw x fh (same units as the scale). Never above `cap` (the EN design size).
    Returns (scale, limiting language)."""
    key = IMAGES[img][0]; fam = TEXTS[key]['font']
    nl = en_lines(img).count('\n') + 2
    best, who = cap, 'en'
    for L, txt, hi in strings(key):
        if L == 'en':
            w, h = size_of(img, en_lines(img), fam, TEXTS[key]['hi']); s = min(fw / w, fh / h)
        else:
            s, _ = best_layout(txt, img, fam, fw, fh, nl, hi)
        # same scale applies to the translation image, which is drawn at the same font px:
        # its fit scale is directly comparable
        if s < best: best, who = s, L
    return best, who
