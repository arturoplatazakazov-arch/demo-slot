# Writes the localisation table (xlsx) for the --notext build: one row per string,
# plus a sheet with every txt_ bone, its setup-pose centre and field size.
# usage: venv/bin/python texts_table.py <notext out dir>
import os, sys, json, math
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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

F = 'Arial'
hdr_font = Font(name=F, bold=True, color='FFFFFF'); hdr_fill = PatternFill('solid', fgColor='3A2A14')
fill_in = PatternFill('solid', fgColor='FFFF00'); thin = Side(style='thin', color='BBBBBB')
box = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(wrap_text=True, vertical='top')

def header(ws, cols, widths):
    ws.append(cols)
    for i, c in enumerate(ws[1]):
        c.font, c.fill, c.alignment, c.border = hdr_font, hdr_fill, Alignment(wrap_text=True, vertical='center'), box
        ws.column_dimensions[c.column_letter].width = widths[i]
    ws.freeze_panes = 'A2'

wb = Workbook()
ws = wb.active; ws.title = 'Тексты'
header(ws, ['Ключ', 'Где', 'EN (оригинал)', 'Перевод', 'Слова золотом', 'Как разбито в макете', 'Поле, px (Ш×В)', 'Кость Spine', 'Шрифт'],
       [14, 22, 40, 40, 24, 34, 22, 22, 14])
order = []
for r in recs:
    if r['key'] not in order: order.append(r['key'])
for key in order:
    t = TEXTS[key]; rs = [r for r in recs if r['key'] == key]
    ws.append([key, '\n'.join(dict.fromkeys(where(r) for r in rs)), t['en'], None,
               ', '.join(w.strip(',.!') for w in t['hi']) or '—', '\n\n'.join(f"{'деск' if i.endswith('desk') else 'моб' if i.endswith('mob') else 'все'}: {s}" for i, s in t.get('img', {key: t['en']}).items()),
               '\n'.join(dict.fromkeys(f"{r['fw']}×{r['fh']}" for r in rs)),
               '\n'.join(dict.fromkeys(r['bone'] for r in rs)), t['font']])
    row = ws.max_row
    for c in ws[row]: c.font, c.alignment, c.border = Font(name=F), wrap, box
    ws.cell(row, 4).fill = fill_in
n = ws.max_row + 2
notes = [
    'Как заполнять: перевод пишем только в жёлтые ячейки колонки «Перевод».',
    'Текст один для деска и мобилки; различаются только переносы строк под ширину поля («Как разбито в макете»). В переводе переносы ставим так же по ширине поля.',
    'Поле, px — габарит текста в дизайн-пикселях макета (деск 1932×940, моб 780×1416). Если перевод длиннее, уменьшаем кегль, чтобы текст влез в поле.',
    '«Слова золотом» в оригинале подсвечены золотым: в переводе подсветить слова с тем же смыслом.',
    'Логотип AMY\'S FRUIT FARM и надпись SCATTER на символе — арт, не переводятся.',
    'Число спинов на бонус-скрине (10/15/20) — цифры n0…n9 внутри Spine, их не переводим.',
]
for i, s in enumerate(notes):
    c = ws.cell(n + i, 1, s); c.font = Font(name=F, italic=(i > 0), bold=(i == 0))

ws2 = wb.create_sheet('Кости Spine')
header(ws2, ['Скелет', 'Кость', 'Слот (альфа-анимация)', 'Ключ текста', 'Центр X', 'Центр Y', 'Поле Ш', 'Поле В'],
       [22, 20, 22, 14, 10, 10, 10, 10])
for r in recs:
    ws2.append([r['skeleton'], r['bone'], r['slot'], r['key'], r['cx'], r['cy'], r['fw'], r['fh']])
    for c in ws2[ws2.max_row]: c.font, c.border = Font(name=F), box
n = ws2.max_row + 2
for i, s in enumerate([
        'Координаты — поза setup, дизайн-пиксели, начало в центре бокса скелета, Y вверх (как в Spine).',
        'Кость txt_* стоит в центре текстового поля и наследует анимацию родителя (вылет, масштаб, покачивание).',
        'На кости висит пустой слот с тем же именем: в нём осталась анимация прозрачности текста (intro/idle) — цвет слота применять к тексту.']):
    ws2.cell(n + i, 1, s).font = Font(name=F, italic=True)
dst = os.path.join(os.path.dirname(os.path.normpath(out)), 'amys_fruit_farm_тексты.xlsx')
wb.save(dst); print(dst)
