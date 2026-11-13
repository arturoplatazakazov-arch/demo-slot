# Texts table (xlsx) + fixed-size fit check + per-language sheets for preview screens whose
# texts are HTML text (DOM), not baked images. Same output as scripts/dirty_money_mafia_texts/
# doc.py; the game-specific part (strings, boxes, fonts, notes) lives in texts.py.
# Product rule (2026-11-12): plaques and font sizes never change per language, so every field
# gets ONE font size at which EN and all translations fit its box. The browser wraps DOM text
# itself, so lines are found the way it does it: greedy wrap at ordinary spaces (a no-break
# space U+00A0 / U+202F keeps words together), white-space: nowrap = one line.
# usage: ../amys_preview_screens/venv/bin/python doc.py <out dir>
import os, sys, json
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
import xlsxwriter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from texts import TEXTS, FIELDS, FAM, META        # noqa: E402
from translations import TR, LANGS                # noqa: E402

OUT = sys.argv[1]; os.makedirs(os.path.join(OUT, 'проверка_языков'), exist_ok=True)
F = os.path.join(HERE, 'fonts')
FILES = {st: sorted((os.path.join(F, n) for n in os.listdir(F) if n.startswith(base + '-latin')),
                    key=lambda p: '-ext' in p) for st, (_, base, _, _, _) in FAM.items()}   # latin, latin-ext
CMAPS = {p: set(TTFont(p).getBestCmap()) for fs in FILES.values() for p in fs}
REF = 100   # widths are measured at 100 px and scaled linearly
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
    """Game font file that has the glyph (latin, then latin-ext), else the wide stand-in."""
    _, _, w, proxy, _ = FAM[style]
    for p in FILES[style]:
        if ord(ch) in CMAPS[p]: return fnt(p, size, w), True
    return fnt(proxy, size), False

_wc = {}
def width(s, style, px, ls=0.0):
    """Advance width of one line in CSS px (letter-spacing ls in em follows every character)."""
    k = (s, style)
    if k not in _wc: _wc[k] = sum(font_for(c, style, REF)[0].getlength(c) for c in s)
    return _wc[k] * px / REF + ls * px * len(s)

def wrap(text, style, px, W, ls, nowrap):
    if nowrap: return [text]
    lines, cur = [], ''
    for w in text.split(' '):
        t = w if not cur else cur + ' ' + w
        if cur and width(t, style, px, ls) > W: lines.append(cur); cur = w
        else: cur = t
    return lines + [cur]

def fits(f, text, px):
    ls = f.get('ls', 0.0); ls_ = wrap(text, TEXTS[f['key']]['style'], px, f['box_w'], ls, f.get('nowrap'))
    w = max(width(l, TEXTS[f['key']]['style'], px, ls) for l in ls_)
    return w <= f['box_w'] + 0.5 and len(ls_) <= f['lines'] and len(ls_) * f['lh'] * px <= f['box_h'] + 0.5, ls_, w

def max_px(f, text):
    """Largest size <= the EN size at which `text` fits the field (0.25 % steps)."""
    for i in range(400):
        px = f['en_px'] * (1 - 0.0025 * i)
        if fits(f, text, px)[0]: return px
    return 0.0

# --- fields: EN size in the game, box, the one fixed size --------------------------------
recs = []
for f in FIELDS:
    f = dict(f); f.setdefault('lh', 1.0)
    if callable(f['en_px']): f['en_px'] = f['en_px'](width, wrap)
    en = TEXTS[f['key']]['en']
    fixed, limit = (max_px(f, en), 'en')
    for L in LANGS:
        p = max_px(f, TR[L][f['key']])
        if p < fixed - 1e-9: fixed, limit = p, L
    f.update(px=round(fixed, 1), fixed=fixed, k=fixed / f['en_px'], limit=limit,
             en_lines=fits(f, en, f['en_px'])[1])
    recs.append(f)

# --- per-language results at the fixed size -----------------------------------------------
FIT = {}
for L in ['en'] + LANGS:
    for r in recs:
        txt = TEXTS[r['key']]['en'] if L == 'en' else TR[L][r['key']]
        ok, ls_, w = fits(r, txt, r['fixed'])
        FIT.setdefault(L, {}).setdefault(r['key'], []).append(dict(
            where=f"{r['screen']}_{r['dev']}", lines=ls_, used_w=round(w / r['box_w'], 3), status='ok' if ok else 'nofit'))
json.dump(dict(fields=[{k: v for k, v in r.items() if k not in ('fixed',)} for r in recs], fit=FIT),
          open(os.path.join(OUT, 'проверка_языков', 'fit.json'), 'w'), ensure_ascii=False, indent=1)

# --- per-language sheet: every field box with the text at its fixed size -------------------
def render(r, lines, px, z):
    """The lines as the browser lays them out in the box (zoom z), game colours, 1 px stroke."""
    st = TEXTS[r['key']]['style']; fill, stroke = FAM[st][4]
    ls = r.get('ls', 0.0); bw, bh = round(r['box_w'] * z), round(r['box_h'] * z)
    im = Image.new('RGBA', (bw, bh)); d = ImageDraw.Draw(im)
    lh = r['lh'] * px * z; y = (bh - lh * len(lines)) / 2
    for line in lines:
        lw = width(line, st, px, ls) * z
        x = {'left': 0, 'center': (bw - lw) / 2}[r.get('align', 'center')]
        for c in line:
            fo = font_for(c, st, max(1, round(px * z)))[0]
            t, b = fo.getbbox('H')[1::2]   # this font's cap height centred in the line
            d.text((x, y + lh / 2 - (t + b) / 2), c, font=fo, fill=fill, stroke_width=max(1, round(z)), stroke_fill=stroke)
            x += fo.getlength(c) + ls * px * z
        y += lh
    return im

def sheet(L):
    tiles = []
    for r in recs:
        z = r.get('zoom', 1)
        txt = TEXTS[r['key']]['en'] if L == 'en' else TR[L][r['key']]
        ok, lines, _ = fits(r, txt, r['fixed'])
        im = render(r, lines, r['fixed'], z); bw, bh = im.size
        tile = Image.new('RGB', (max(bw, 330) + 20, bh + 44), META['tile_bg']); d = ImageDraw.Draw(tile)
        d.rectangle([10, 34, 10 + bw, 34 + bh], outline=(0, 220, 230) if ok else (255, 60, 60), width=2)
        d.text((10, 8), f"{r['screen']} · {r['dev']} · {r['key']} · {r['px']:g}px" + (f" (x{z})" if z != 1 else ''),
               fill=(200, 200, 200), font=fnt('/System/Library/Fonts/Supplemental/Arial.ttf', 16))
        tile.paste(im, (10, 34), im); tiles.append(tile)
    W = 2300; x = y = 10; rowh = 0; pos = []
    for t in tiles:
        if x + t.width > W: x, y, rowh = 10, y + rowh + 10, 0
        pos.append((x, y)); x += t.width + 10; rowh = max(rowh, t.height)
    out = Image.new('RGB', (W, y + rowh + 10), META['sheet_bg'])
    for t, p in zip(tiles, pos): out.paste(t, p)
    out.save(os.path.join(OUT, 'проверка_языков', f'{L}.jpg'), quality=86)
for L in ['en'] + LANGS: sheet(L)

# --- fonts coverage ------------------------------------------------------------------------
def coverage(L):
    out = {}
    for st, (name, _, _, _, _) in FAM.items():
        keys = [k for k, v in TEXTS.items() if v['style'] == st]
        chars = {c for k in keys for c in TR[L][k] if c not in '   ⁠\n'}
        out[st] = ''.join(sorted(c for c in chars if not any(ord(c) in CMAPS[p] for p in FILES[st])))
    return out

# --- xlsx ----------------------------------------------------------------------------------
LANG_NAME = dict(ru='RU · русский', uk='UK · українська', kk='KK · қазақша', az='AZ · azərbaycan', de='DE · Deutsch',
                 es='ES · español', fr='FR · français', pl='PL · polski', pt='PT · português (BR)', tr='TR · Türkçe',
                 uz='UZ · oʻzbek (лат.)')
SCREEN, WHERE = META['screens'], {k: v['where'] for k, v in TEXTS.items()}
dst = os.path.join(OUT, META['xlsx'])
wb = xlsxwriter.Workbook(dst)
base = dict(font_name='Arial', font_size=10, text_wrap=True, valign='top', border=1, border_color='#BBBBBB')
f_hdr = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color=META['hdr'], valign='vcenter'))
f_cell = wb.add_format(base); f_ok = wb.add_format(dict(base, bg_color='#E2F0D9')); f_bad = wb.add_format(dict(base, bg_color='#F4C7C3'))
f_pct = {k: wb.add_format(dict(base, num_format='0%', align='center', bg_color=c)) for k, c in dict(ok='#E2F0D9', nofit='#F4C7C3').items()}
f_note = wb.add_format(dict(font_name='Arial', font_size=10, italic=True)); f_note_b = wb.add_format(dict(font_name='Arial', font_size=10, bold=True))
show = lambda s: s.replace(' ', ' ').replace(' ', ' ')

def header(ws, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths)): ws.write(0, i, c, f_hdr); ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)

def tight(L, key): return max(FIT[L][key], key=lambda x: x['used_w'])
dv = lambda r: 'деск' if r['dev'] == 'desk' else 'моб'

ws = wb.add_worksheet('Тексты'); NL = len(LANGS)
header(ws, ['Ключ', 'Где', 'EN (оригинал)'] + [LANG_NAME[L] for L in LANGS] +
       ['Как разбито в игре (EN)', 'Поле, px (Ш×В)', 'Кегль, px (фикс.)', 'Кегль EN сейчас, px', 'Элемент/кость', 'Шрифт'],
       [13, 24, 30] + [28] * NL + [24, 16, 14, 14, 22, 14])
order = list(dict.fromkeys(r['key'] for r in recs))
for row, key in enumerate(order, 1):
    rs = [r for r in recs if r['key'] == key]; t = TEXTS[key]
    ws.write(row, 0, key, f_cell)
    ws.write(row, 1, '\n'.join(dict.fromkeys(f"{SCREEN[r['screen']]} · {dv(r)}" for r in rs)) + '\n' + WHERE[key], f_cell)
    ws.write(row, 2, t['en'], f_cell)
    for j, L in enumerate(LANGS):
        m = tight(L, key)
        ws.write(row, 3 + j, show(TR[L][key]), f_ok if m['status'] == 'ok' else f_bad)
        ws.write_comment(row, 3 + j, ('Влезает' if m['status'] == 'ok' else 'НЕ ВЛЕЗАЕТ') + f" фиксированным кеглем; занято "
                         f"{round(m['used_w'] * 100)}% ширины поля ({m['where']}). Строки: {' / '.join(map(show, m['lines']))}",
                         dict(x_scale=2, y_scale=1.2))
    c = 3 + NL
    for v in ['\n'.join(f"{dv(r)}: " + ' / '.join(r['en_lines']) for r in rs),
              '\n'.join(f"{dv(r)}: {r['box_w']:g}×{r['box_h']:g}" + (f" ({r['lines']} стр.)" if r['lines'] > 1 else '') for r in rs),
              '\n'.join(f"{dv(r)}: {r['px']:g}" for r in rs),
              '\n'.join(f"{dv(r)}: {r['en_px']:.4g}" + ('' if r['k'] > 0.995 else f" (−{round((1 - r['k']) * 100)}%, упирается в {r['limit'].upper()})") for r in rs),
              '\n'.join(dict.fromkeys(r['el'] for r in rs)), FAM[t['style']][0]]:
        ws.write(row, c, v, f_cell); c += 1
n = len(order) + 2
for i, s in enumerate(META['notes']):
    ws.write(n + i, 0, s, f_note_b if i == 0 else f_note)

wf = wb.add_worksheet('Проверка')
header(wf, ['Ключ'] + [L.upper() for L in LANGS], [14] + [9] * NL)
for row, key in enumerate(order, 1):
    wf.write(row, 0, key, f_cell)
    for j, L in enumerate(LANGS):
        m = tight(L, key); wf.write(row, 1 + j, m['used_w'], f_pct[m['status']])
wf.write(len(order) + 2, 0, 'Сколько ширины поля занимает текст при фиксированном кегле (≤100% = влезает, и по числу строк тоже). Худший из деск/моб. Картинки: проверка_языков/<язык>.jpg.', f_note)

wfo = wb.add_worksheet('Шрифты')
names = list(FAM)
header(wfo, ['Язык'] + [f"{FAM[st][0]} ({META['font_use'][st]})" for st in FAM] + ['Итог'], [16] + [44] * len(FAM) + [48])
for row, L in enumerate(LANGS, 1):
    cv = coverage(L); wfo.write(row, 0, LANG_NAME[L], f_cell)
    for j, nm in enumerate(names):
        wfo.write(row, 1 + j, 'все символы есть' if not cv[nm] else 'нет символов: ' + cv[nm], f_ok if not cv[nm] else f_bad)
    bad = any(cv.values())
    wfo.write(row, 1 + len(names), 'отображается правильно' if not bad else
              ('нужен другой шрифт: в шрифтах игры нет кириллицы' if L in ('ru', 'uk', 'kk') else
               'в шрифте игры нет этих букв: нужен файл шрифта с ними или замена'), f_ok if not bad else f_bad)
wfo.write(len(LANGS) + 2, 0, META['fonts_note'], f_note)

ws2 = wb.add_worksheet('Поля')
header(ws2, ['Экран', 'Устройство', 'Ключ', 'Элемент/кость', 'Поле Ш', 'Поле В', 'Строк макс.', 'Кегль фикс., px', 'Кегль EN сейчас, px', 'Упирается в'],
       [12, 12, 14, 26, 9, 9, 10, 14, 16, 12])
for row, r in enumerate(recs, 1):
    for col, v in enumerate([r['screen'], r['dev'], r['key'], r['el'], round(r['box_w'], 1), round(r['box_h'], 1), r['lines'],
                             r['px'], round(r['en_px'], 1), r['limit'].upper()]):
        ws2.write(row, col, v, f_cell)
ws2.write(len(recs) + 2, 0, META['fields_note'], f_note)
wb.close(); print(dst)
for r in recs: print(f"{r['screen']:8}{r['dev']:5}{r['key']:15} box {r['box_w']:.0f}x{r['box_h']:.0f}  EN {r['en_px']:.1f}px -> fixed {r['px']}px ({r['k']:.2f}, {r['limit']})")
