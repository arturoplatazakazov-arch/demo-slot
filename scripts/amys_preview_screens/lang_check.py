# Fit + font check of translations.TR against the --notext text fields.
# Every string is drawn with the same gfx style as its EN art, line breaks are searched
# (up to EN lines + 1), and the best-fitting variant is scaled into the field. The result
# is the font scale vs EN as drawn in the game (1.0 = same size, never bigger) plus glyph coverage of the game fonts.
# Strings the game font cannot draw are measured with a stand-in (Arial Black for Luckiest
# Guy, Arial Bold for Fredoka) and flagged.
# usage: venv/bin/python lang_check.py <notext dir> <dir with nt_<skeleton>.png renders> <out dir>
import os, sys, json, math, itertools
from PIL import Image
from fontTools.ttLib import TTFont
import gfx
from texts import TEXTS, IMAGES
from translations import TR, LANGS, plain, bold_words

NOTEXT, RENDERS, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
S = os.path.dirname(os.path.abspath(__file__))
LG_FULL = os.path.join(S, 'fonts/luckiest-guy-full.ttf')   # latin + latin-ext merged
FR_LAT = gfx.FR
SUP = '/System/Library/Fonts/Supplemental/'
PROXY = {'Luckiest Guy': SUP + 'Arial Black.ttf', 'Fredoka 650': SUP + 'Arial Bold.ttf'}
CMAP = {'Luckiest Guy': set(TTFont(LG_FULL).getBestCmap()),
        'Fredoka 650': set(TTFont(os.path.join(S, 'fonts/fredoka-latin-849e3a33.ttf')).getBestCmap())
                       | set(TTFont(os.path.join(S, 'fonts/fredoka-latin-ext-20489dbf.ttf')).getBestCmap())}
GOLD = ((255, 250, 225), (255, 222, 120), (246, 170, 30))
PALE = ((255, 255, 240), (255, 236, 160), (255, 200, 70))
# image -> how gfx.py draws it (function, size, extra kwargs)
STYLE = {
    't_fs': ('styled', 50, {}), 't_buy': ('styled', 50, {}),
    'd_fs_desk': ('body', 30, {}), 'd_fs_mob': ('body', 30, {}), 'd_buy_desk': ('body', 30, {}), 'd_buy_mob': ('body', 30, {}),
    'cont_desk': ('styled', 44, dict(grad=PALE)), 'cont_mob': ('styled', 50, dict(grad=PALE)),
    'start_desk': ('styled', 44, dict(grad=PALE)), 'start_mob': ('styled', 50, dict(grad=PALE)),
    't_congrats': ('styled', 84, {}), 't_youwon': ('styled', 46, dict(grad=GOLD)), 't_freespins': ('styled', 50, dict(grad=GOLD)),
    'b_fs': ('body', 34, {}),
    'sign_buy': ('styled', 64, dict(grad=((255, 250, 205), (255, 214, 80), (240, 150, 10)), line_h=0.95, shadow=4)),
}
OK, SMALL = 0.85, 0.60   # scale vs EN: >= OK fits, >= SMALL fits with a smaller font, else does not fit

def draw(img, lines, fam, hi):
    fn, size, kw = STYLE[img]
    covered = all(ord(c) in CMAP[fam] or c in ' \n ' for c in lines)
    if fam == 'Luckiest Guy':
        f = LG_FULL if covered else PROXY[fam]
        im = gfx.styled(lines, size, fnt=f, **kw)
    else:
        if covered and all(ord(c) in set(TTFont(FR_LAT).getBestCmap()) or c in ' \n ' for c in lines):
            im = gfx.body(lines, size, hi=hi, **kw)
        else:   # stand-in (also when only the latin-ext subset has the glyph: PIL cannot mix files)
            im = gfx.body(lines, size, hi=hi, wght=None, fnt=PROXY[fam], **kw)
    if img == 'sign_buy': im = im.resize((int(im.width * 0.9), int(im.height * 0.9)), Image.LANCZOS)
    return im, covered

def splits(words, n):
    if n == 1: yield [' '.join(words)]; return
    for cut in itertools.combinations(range(1, len(words)), n - 1):
        b = (0,) + cut + (len(words),)
        yield [' '.join(words[b[i]:b[i + 1]]) for i in range(n)]

def best_layout(text, img, fam, fw, fh, max_lines, hi, cap):
    """Most legible line split: maximise the scale that fits fw x fh."""
    fn, size, kw = STYLE[img]
    f = gfx.font(LG_FULL if fam == 'Luckiest Guy' else FR_LAT, size, None if fam == 'Luckiest Guy' else 650)
    words = text.split(' ')
    cands = []
    for n in range(1, min(max_lines, len(words)) + 1):
        # per n keep the split with the narrowest longest line
        best = min(splits(words, n), key=lambda ls: max(f.getlength(l) for l in ls))
        cands.append(best)
    out = None
    for ls in cands:
        im, cov = draw(img, '\n'.join(ls), fam, hi)
        s = min(fw / im.width, fh / im.height, cap)
        if out is None or s > out[0]: out = (s, ls, im, cov)
    return out

recs = json.load(open(os.path.join(NOTEXT, 'text_fields.json')))
import numpy as np
def mat(x=0, y=0, rot=0, sx=1, sy=1):
    c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return np.array([[c * sx, -s_ * sy, x], [s_ * sx, c * sy, y], [0, 0, 1]])
skels = {}
for r in recs:
    if r['skeleton'] not in skels:
        d = json.load(open(os.path.join(NOTEXT, r['skeleton'], 'animation.json')))
        W = {}
        for b in d['bones']:
            m = mat(b.get('x', 0), b.get('y', 0), b.get('rotation', 0), b.get('scaleX', 1), b.get('scaleY', 1))
            W[b['name']] = (W[b['parent']] @ m) if 'parent' in b else m
        skels[r['skeleton']] = (W, d['skeleton'])
    W, _ = skels[r['skeleton']]
    M = W[r['bone']]
    r['cx'], r['cy'] = M[0, 2], M[1, 2]
    sx, sy = math.hypot(M[0, 0], M[1, 0]), math.hypot(M[0, 1], M[1, 1])
    r['fw'], r['fh'] = r['w'] * sx, r['h'] * sy
    r['ew'] = r['en_w'] * sx   # EN art width on screen

def img_of(r):
    """gfx image the field was cut from (sign uses the label, not the whole sign)."""
    if r['key'] == 'sign_buy': return 'sign_buy'
    dev = r['skeleton'].rsplit('_', 1)[1]
    for img, (k, _) in IMAGES.items():
        if k == r['key'] and (img == k or img.endswith('_' + dev)): return img

results = {}
for L in ['en'] + LANGS:
    canv = {sk: Image.open(os.path.join(RENDERS, f'nt_{sk}.png')).convert('RGBA') for sk in skels}
    for r in recs:
        key, img = r['key'], img_of(r)
        fam = TEXTS[key]['font']
        en_lines = IMAGES[img][1] if img in IMAGES else TEXTS[key]['img']['sign_buy']
        en_im, _ = draw(img, en_lines, fam, TEXTS[key]['hi'])
        s0 = r['ew'] / en_im.width   # scale the EN art has in the game
        if L == 'en':
            s, ls, im, cov = s0, en_lines.split('\n'), en_im, True
        else:
            txt = TR[L][key]
            s, ls, im, cov = best_layout(plain(txt), img, fam, r['fw'], r['fh'], en_lines.count('\n') + 2, bold_words(txt), s0)
        ratio = s / s0
        miss = '' if L == 'en' else ''.join(sorted({c for c in plain(TR[L][key]) if ord(c) not in CMAP[fam] and c not in '  '}))
        status = 'ok' if ratio >= OK else 'small' if ratio >= SMALL else 'nofit'
        results.setdefault(L, {}).setdefault(key, []).append(dict(skeleton=r['skeleton'], ratio=round(ratio, 3), lines=ls,
                                                                    status=status, missing=miss, fam=fam))
        # paste into the preview at the bone
        _, sk = skels[r['skeleton']]
        w, h = max(1, round(im.width * s)), max(1, round(im.height * s))
        x = round(r['cx'] - sk['x'] - w / 2); y = round(sk['y'] + sk['height'] - r['cy'] - h / 2)
        canv[r['skeleton']].alpha_composite(im.resize((w, h), Image.LANCZOS), (x, y))
    # contact sheet: desk feature | desk bonus  over  mob feature | mob bonus
    fd, bd = canv['feature_screen_desk'], canv['bonus_screen_desk']
    fm, bm = canv['feature_screen_mob'], canv['bonus_screen_mob']
    H = 940; mw = round(780 * H / 1416)
    sheet = Image.new('RGB', (1932 * 2 + mw * 2 + 50, H + 20), (24, 24, 24))
    for i, im in enumerate([fd, bd]): sheet.paste(im.convert('RGB'), (10 + i * 1942, 10))
    for i, im in enumerate([fm, bm]): sheet.paste(im.convert('RGB').resize((mw, H), Image.LANCZOS), (3894 + 10 + i * (mw + 10), 10))
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    sheet.save(os.path.join(OUT, f'{L}.jpg'), quality=86)
    print(L, 'done')
json.dump(results, open(os.path.join(OUT, 'fit.json'), 'w'), ensure_ascii=False, indent=1)
