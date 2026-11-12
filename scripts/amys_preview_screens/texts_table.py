# Writes the localisation table (xlsx) for the --notext build: one row per string,
# plus a sheet with every txt_ bone, its setup-pose centre and field size.
# usage: venv/bin/python texts_table.py <notext out dir>
import os, sys, json, math
import numpy as np
# xlsxwriter, not openpyxl: openpyxl stores rich text as inline strings, and Numbers /
# Google Sheets / previews drop the bold there; xlsxwriter writes shared-string runs.
import xlsxwriter
from texts import TEXTS
from translations import TR, LANGS, plain
import fitkit

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
    k = math.hypot(M[0, 0], M[1, 0])
    r['fw'], r['fh'] = round(r['w'] * k), round(r['h'] * math.hypot(M[0, 1], M[1, 1]))
    r['font_px'] = round(fitkit.font_px(r['img']) * r['scale'] * k)   # one fixed size for every language

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

def md_runs(s):
    """'a **b** c' -> [('a ', False), ('b', True), (' c', False)]"""
    return [(p, i % 2 == 1) for i, p in enumerate(s.split('**')) if p]

FIT_PATH = os.path.join(os.path.dirname(os.path.normpath(out)), 'проверка_языков', 'fit.json')
FIT = json.load(open(FIT_PATH)) if os.path.exists(FIT_PATH) else {}
LANG_NAME = dict(ru='RU · русский', uk='UK · українська', kk='KK · қазақша', az='AZ · azərbaycan', de='DE · Deutsch',
                 es='ES · español', fr='FR · français', pl='PL · polski', pt='PT · português (BR)', tr='TR · Türkçe',
                 uz='UZ · oʻzbek (лат.)')

def fit_of(L, key):
    v = FIT.get(L, {}).get(key)
    if not v: return None
    return max(v, key=lambda x: x['used_w'])   # tightest of desk/mob

order = []
for r in recs:
    if r['key'] not in order: order.append(r['key'])

dst = os.path.join(os.path.dirname(os.path.normpath(out)), 'amys_fruit_farm_тексты.xlsx')
wb = xlsxwriter.Workbook(dst)
F = 'Arial'
base = dict(font_name=F, font_size=10, text_wrap=True, valign='top', border=1, border_color='#BBBBBB')
f_hdr = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color='#3A2A14', valign='vcenter'))
f_cell = wb.add_format(base)
f_ok = wb.add_format(dict(base, bg_color='#E2F0D9'))
f_small = wb.add_format(dict(base, bg_color='#FCE4C4'))
f_bad = wb.add_format(dict(base, bg_color='#F4C7C3'))
f_pct = {k: wb.add_format(dict(base, num_format='0%', align='center', bg_color=c)) for k, c in
         dict(ok='#E2F0D9', small='#FCE4C4', nofit='#F4C7C3').items()}
f_bold = wb.add_format(dict(font_name=F, font_size=10, bold=True))
f_plain = wb.add_format(dict(font_name=F, font_size=10))
f_note_b = wb.add_format(dict(font_name=F, font_size=10, bold=True))
f_note = wb.add_format(dict(font_name=F, font_size=10, italic=True))

def header(ws, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths)):
        ws.write(0, i, c, f_hdr); ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)

ws = wb.add_worksheet('Тексты')
NL = len(LANGS)
header(ws, ['Ключ', 'Где', 'EN (оригинал)'] + [LANG_NAME[L] for L in LANGS] + ['Как разбито в макете (EN)', 'Поле, px (Ш×В)', 'Кегль, px (фикс.)', 'Кость Spine', 'Шрифт'],
       [12, 20, 34] + [30] * NL + [30, 16, 14, 18, 13])
for row, key in enumerate(order, 1):
    t = TEXTS[key]; rs = [r for r in recs if r['key'] == key]
    vals = [key, '\n'.join(dict.fromkeys(where(r) for r in rs)), None] + [None] * NL + [
            '\n\n'.join(f"{'деск' if i.endswith('desk') else 'моб' if i.endswith('mob') else 'все'}: {s}" for i, s in t.get('img', {key: t['en']}).items()),
            '\n'.join(dict.fromkeys(f"{r['fw']}×{r['fh']}" for r in rs)),
            '\n'.join(dict.fromkeys(f"{'деск' if r['skeleton'].endswith('desk') else 'моб'}: {r['font_px']}" for r in rs)),
            '\n'.join(dict.fromkeys(r['bone'] for r in rs)), t['font']]
    for col, v in enumerate(vals):
        if 2 <= col < 3 + NL: continue
        ws.write(row, col, v, f_cell)
    rr = runs(t['en'], t['hi'])
    if any(b for _, b in rr):
        frags = []
        for txt, b in rr: frags += [f_bold if b else f_plain, txt]
        ws.write_rich_string(row, 2, *frags, f_cell)
    else:
        ws.write(row, 2, t['en'], f_cell)
    for j, L in enumerate(LANGS):
        col = 3 + j; txt = TR[L][key]; m = fit_of(L, key)
        fmt = f_cell if m is None else f_ok if m['status'] == 'ok' else f_bad
        rr = md_runs(txt)
        if any(b for _, b in rr) and len(rr) > 1:
            frags = []
            for t_, b in rr: frags += [f_bold if b else f_plain, t_]
            ws.write_rich_string(row, col, *frags, fmt)
        else:
            ws.write(row, col, plain(txt), wb.add_format(dict(base, bold=True, bg_color=fmt.bg_color)) if rr and rr[0][1] else fmt)
        if m is not None:
            ws.write_comment(row, col, ('Влезает' if m['status'] == 'ok' else 'НЕ ВЛЕЗАЕТ') +
                             f" фиксированным кеглем; занято {round(m['used_w'] * 100)}% ширины поля ({m['skeleton']}). "
                             f"Разбито: {' / '.join(m['lines'])}", dict(x_scale=2, y_scale=1.2))
n = len(order) + 2
notes = [
    'Размер плашек и кегль фиксированы и одинаковы для всех языков («Кегль, px»): они подобраны так, что EN и все переводы из этой таблицы влезают в поле, не меняя размера. Зелёный — влезает (наведи на ячейку — разбивка по строкам), красный — не влезает.',
    'Текст один для деска и мобилки; различаются только переносы строк под ширину поля («Как разбито в макете»). В переводе переносы ставим так же по ширине поля.',
    'Поле, px — область текста в дизайн-пикселях макета (деск 1932×940, моб 780×1416). Кегль и поле не подстраиваются под язык; новый перевод должен влезать в поле этим кеглем (переносы — по словам).',
    'Жирным выделены слова, которые в игре подсвечены золотом; в переводах — слова с тем же смыслом.',
    'Шрифты игры (Luckiest Guy, Fredoka) не содержат кириллицу и часть латиницы — см. лист «Шрифты». Для RU/UK/KK вёрстка проверена на замещающих шрифтах той же ширины.',
    'Логотип AMY\'S FRUIT FARM и надпись SCATTER на символе — арт, не переводятся.',
    'Число спинов на бонус-скрине (10/15/20) — цифры n0…n9 внутри Spine, их не переводим.',
]
for i, s in enumerate(notes):
    ws.write(n + i, 0, s, f_note_b if i == 0 else f_note)

if FIT:
    wf = wb.add_worksheet('Проверка')
    header(wf, ['Ключ'] + [L.upper() for L in LANGS], [14] + [9] * NL)
    for row, key in enumerate(order, 1):
        wf.write(row, 0, key, f_cell)
        for j, L in enumerate(LANGS):
            m = fit_of(L, key); wf.write(row, 1 + j, m['used_w'], f_pct[m['status']])
    n = len(order) + 2
    for i, s_ in enumerate([
            'Сколько ширины поля занимает текст при фиксированном кегле (≤100% = влезает). Худший из деск/моб.',
            'Каждая строка нарисована тем же стилем и кеглем, что EN-арт, переносы подобраны автоматически (до числа строк EN + 1), проверено попадание в поле (лист «Кости Spine»).',
            'Картинки всех экранов по каждому языку: папка проверка_языков/<язык>.jpg.']):
        wf.write(n + i, 0, s_, f_note)

    from lang_check_fonts import coverage
    wfo = wb.add_worksheet('Шрифты')
    header(wfo, ['Язык', 'Luckiest Guy (заголовки, плашки)', 'Fredoka (описания)', 'Итог'], [16, 44, 44, 44])
    for row, L in enumerate(LANGS, 1):
        cv = coverage(L)
        wfo.write(row, 0, LANG_NAME[L], f_cell)
        for j, fam in enumerate(['Luckiest Guy', 'Fredoka 650']):
            miss = cv[fam]
            wfo.write(row, 1 + j, 'все символы есть' if not miss else 'нет символов: ' + miss, f_ok if not miss else f_bad)
        bad = [f for f in cv if cv[f]]
        wfo.write(row, 3, 'отображается правильно' if not bad else
                  ('нужен другой шрифт: в шрифтах игры нет кириллицы' if L in ('ru', 'uk', 'kk') else
                   'в шрифте игры нет этих букв: нужен файл шрифта с ними или замена для этого языка'), f_ok if not bad else f_bad)
    n = len(LANGS) + 2
    for i, s_ in enumerate([
            'Проверено по файлам шрифтов игры (front/fonts: latin + latin-ext подмножества Luckiest Guy и Fredoka).',
            'Luckiest Guy вообще не имеет кириллицы и буквы Ə — для RU/UK/KK/AZ нужен замещающий шрифт в том же стиле.',
            'В Fredoka кириллицы тоже нет; польских ą/ę, турецких/азербайджанских ş/İ/ə и узбекской ʻ нет в файлах игры — нужно проверить, есть ли они в актуальной полной Fredoka, иначе подобрать замену.']):
        wfo.write(n + i, 0, s_, f_note)

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
