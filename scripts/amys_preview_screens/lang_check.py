# Fixed-size check of translations.TR against the --notext text fields.
# Each field has ONE font size (build.py picks it via fitkit.common_scale so EN and every
# translation fit). Here every string is drawn at exactly that size with its best line
# split, verified to stay inside the field and pasted onto the setup-pose render.
# usage: venv/bin/python lang_check.py <notext dir> <dir with nt_<skeleton>.png renders> <out dir>
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw
import fitkit
from texts import TEXTS
from translations import TR, LANGS, plain, bold_words

NOTEXT, RENDERS, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
recs = json.load(open(os.path.join(NOTEXT, 'text_fields.json')))

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
    r['k'] = math.hypot(M[0, 0], M[1, 0])          # parent units -> design px
    r['fw'], r['fh'] = r['w'] * r['k'], r['h'] * r['k']

results = {}
for L in ['en'] + LANGS:
    canv = {sk: Image.open(os.path.join(RENDERS, f'nt_{sk}.png')).convert('RGBA') for sk in skels}
    for r in recs:
        key, img = r['key'], r['img']; fam = TEXTS[key]['font']
        s = r['scale'] * r['k']                       # the field's fixed size, design px per gfx px
        if L == 'en':
            ls = fitkit.en_lines(img).split('\n'); hi = TEXTS[key]['hi']
        else:
            txt = TR[L][key]; hi = bold_words(txt)
            nl = fitkit.en_lines(img).count('\n') + 2
            _, ls = fitkit.best_layout(plain(txt), img, fam, r['w'], r['h'], nl, hi)
        im, _ = fitkit.draw(img, '\n'.join(ls), fam, hi)
        w, h = round(im.width * s), round(im.height * s)
        fits = w <= r['fw'] + 0.5 and h <= r['fh'] + 0.5
        miss = '' if L == 'en' else ''.join(sorted({c for c in plain(TR[L][key]) if ord(c) not in fitkit.CMAP[fam] and c not in '  '}))
        results.setdefault(L, {}).setdefault(key, []).append(dict(
            skeleton=r['skeleton'], lines=ls, status='ok' if fits else 'nofit', missing=miss, fam=fam,
            used_w=round(w / r['fw'], 3), used_h=round(h / r['fh'], 3)))
        _, sk = skels[r['skeleton']]
        x = round(r['cx'] - sk['x'] - w / 2); y = round(sk['y'] + sk['height'] - r['cy'] - h / 2)
        canv[r['skeleton']].alpha_composite(im.resize((w, h), Image.LANCZOS), (x, y))
        if not fits: print('DOES NOT FIT', L, r['skeleton'], key, ls)
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
