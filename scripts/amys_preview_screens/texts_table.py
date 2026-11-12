# Writes the localisation table (xlsx) for the --notext build: one row per string,
# plus a sheet with every txt_ bone, its setup-pose centre and field size.
# usage: venv/bin/python texts_table.py <notext out dir>
import os, sys, json, math
import numpy as np
# xlsxwriter, not openpyxl: openpyxl stores rich text as inline strings, and Numbers /
# Google Sheets / previews drop the bold there; xlsxwriter writes shared-string runs.
import xlsxwriter
from texts import TEXTS

def world(d):
    def mat(x=0, y=0, rot=0, sx=1, sy=1):
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        return np.array([[c * sx, -s * sy, x], [s * sx, c * sy, y], [0, 0, 1]])
    W = {}
    for b in d['bones']:
        m = mat(b.get('x', 0), b.get('y', 0), b.get('rotation', 0), b.get('scaleX', 1), b.get('scaleY', 1))
        W[b['name']] = (W[b['parent']] @ m) if 'parent' in b else m
    return W

out = sys.argv[1]
recs = json.load(open(os.path.join(out, 'text_fields.json')))
cache = {}
for r in recs:
    if r['skeleton'] not in cache:
        cache[r['skeleton']] = world(json.load(open(os.path.join(out, r['skeleton'], 'animation.json'))))
    M = cache[r['skeleton']][r['bone']]
    r['cx'], r['cy'] = round(M[0, 2]), round(M[1, 2])
    r['fw'], r['fh'] = round(r['w'] * math.hypot(M[0, 0], M[1, 0])), round(r['h'] * math.hypot(M[0, 1], M[1, 1]))

SCREEN = {'feature_screen': 'Фича-скрин', 'bonus_screen': 'Бонус-скрин'}
def where(r):
    sc, dev = r['skeleton'].rsplit('_', 1)
    return f"{SCREEN[sc]} · {'деск' if dev == 'desk' else 'моб'}"

def runs(text, hi):
    """EN copy split into (text, bold) runs; bold = the gold words, same test as
    gfx.body(): w.strip(',.!') in hi. Bold words separated by one space merge."""
    out = []
    def add(t, b):
        if not t: return
        if out and out[-1][1] == b: out[-1] = (out[-1][0] + t, b)
        else: out.append((t, b))
    for i, w in enumerate(text.split(' ')):
        sep = ' ' if i else ''
        core = w.strip(',.!')
        if core and core in hi:
            pre = w[:w.index(core)]; post = w[w.index(core) + len(core):]
            if not pre and out and out[-1][1] and sep: add(sep, True)  # "20 FREE" -> one bold run
            else: add(sep + pre, False)
            add(core, True); add(post, False)
        else:
            add(sep + w, False)
    return out

order = []
for r in recs:
    if r['key'] not in order: order.append(r['key'])

dst = os.path.join(os.path.dirname(os.path.normpath(out)), 'amys_fruit_farm_тексты.xlsx')
wb = xlsxwriter.Workbook(dst)
F = 'Arial'
base = dict(font_name=F, font_size=10, text_wrap=True, valign='top', border=1, border_color='#BBBBBB')
f_hdr = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color='#3A2A14', valign='vcenter'))
f_cell = wb.add_format(base)
f_fill = wb.add_format(dict(base, bg_color='#FFFF00'))
f_bold = wb.add_format(dict(font_name=F, font_size=10, bold=True))
f_plain = wb.add_format(dict(font_name=F, font_size=10))
f_note_b = wb.add_format(dict(font_name=F, font_size=10, bold=True))
f_note = wb.add_format(dict(font_name=F, font_size=10, italic=True))

def header(ws, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths)):
        ws.write(0, i, c, f_hdr); ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)

ws = wb.add_worksheet('Тексты')
header(ws, ['Ключ', 'Где', 'EN (оригинал)', 'Перевод', 'Как разбито в макете', 'Поле, px (Ш×В)', 'Кость Spine', 'Шрифт'],
       [14, 22, 40, 40, 34, 22, 22, 14])
for row, key in enumerate(order, 1):
    t = TEXTS[key]; rs = [r for r in recs if r['key'] == key]
    vals = [key, '\n'.join(dict.fromkeys(where(r) for r in rs)), None, None,
            '\n\n'.join(f"{'деск' if i.endswith('desk') else 'моб' if i.endswith('mob') else 'все'}: {s}" for i, s in t.get('img', {key: t['en']}).items()),
            '\n'.join(dict.fromkeys(f"{r['fw']}×{r['fh']}" for r in rs)),
            '\n'.join(dict.fromkeys(r['bone'] for r in rs)), t['font']]
    for col, v in enumerate(vals):
        if col in (2, 3): continue
        ws.write(row, col, v, f_cell)
    rr = runs(t['en'], t['hi'])
    if any(b for _, b in rr):
        frags = []
        for txt, b in rr: frags += [f_bold if b else f_plain, txt]
        ws.write_rich_string(row, 2, *frags, f_cell)
    else:
        ws.write(row, 2, t['en'], f_cell)
    ws.write_blank(row, 3, None, f_fill)
n = len(order) + 2
notes = [
    'Как заполнять: перевод пишем только в жёлтые ячейки колонки «Перевод».',
    'Текст один для деска и мобилки; различаются только переносы строк под ширину поля («Как разбито в макете»). В переводе переносы ставим так же по ширине поля.',
    'Поле, px — габарит текста в дизайн-пикселях макета (деск 1932×940, моб 780×1416). Если перевод длиннее, уменьшаем кегль, чтобы текст влез в поле.',
    'Жирным в EN выделены слова, которые в игре подсвечены золотом: в переводе выделить жирным слова с тем же смыслом.',
    'Логотип AMY\'S FRUIT FARM и надпись SCATTER на символе — арт, не переводятся.',
    'Число спинов на бонус-скрине (10/15/20) — цифры n0…n9 внутри Spine, их не переводим.',
]
for i, s in enumerate(notes):
    ws.write(n + i, 0, s, f_note_b if i == 0 else f_note)

ws2 = wb.add_worksheet('Кости Spine')
header(ws2, ['Скелет', 'Кость', 'Слот (альфа-анимация)', 'Ключ текста', 'Центр X', 'Центр Y', 'Поле Ш', 'Поле В'],
       [22, 20, 22, 14, 10, 10, 10, 10])
for row, r in enumerate(recs, 1):
    for col, v in enumerate([r['skeleton'], r['bone'], r['slot'], r['key'], r['cx'], r['cy'], r['fw'], r['fh']]):
        ws2.write(row, col, v, f_cell)
n = len(recs) + 2
for i, s in enumerate([
        'Координаты — поза setup, дизайн-пиксели, начало в центре бокса скелета, Y вверх (как в Spine).',
        'Кость txt_* стоит в центре текстового поля и наследует анимацию родителя (вылет, масштаб, покачивание).',
        'На кости висит пустой слот с тем же именем: в нём осталась анимация прозрачности текста (intro/idle) — цвет слота применять к тексту.']):
    ws2.write(n + i, 0, s, f_note)
wb.close(); print(dst)
