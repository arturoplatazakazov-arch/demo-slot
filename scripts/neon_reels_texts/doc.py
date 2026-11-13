# Neon Reels: texts table (xlsx) + fixed-size fit check + per-language sheets.
# Product rule (2026-11-12): the engine never resizes plaques or fonts per language, so every
# field gets ONE font size at which EN and all translations fit its box. Drawing and fitting
# live in fitlib.py, shared with the screens generator.
# usage: ../amys_preview_screens/venv/bin/python doc.py <out dir>
import os, sys, json
from PIL import Image, ImageDraw
import xlsxwriter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fitlib                                                     # noqa: E402
from fitlib import (FAM, FILES, CMAPS, STYLES, draw, fnt, best, lines_for, has_glyph)  # noqa: E402
from texts import TEXTS, FIELDS, WHERE                            # noqa: E402
from translations import TR, LANGS                                # noqa: E402

OUT = sys.argv[1]; os.makedirs(os.path.join(OUT, 'проверка_языков'), exist_ok=True)
GAME = dict(slug='neon-reels', xlsx='neon_reels_тексты.xlsx', hdr='#3A1466', tile=(27, 13, 61), sheet=(10, 6, 32))
FAM_USE = {'luckiest': 'все тексты'}
NOTES = [
    'Размер плашек и кегль фиксированы и одинаковы для всех языков («Кегль, px (фикс.)»): подобраны так, что EN и все переводы из этой таблицы влезают в поле. Зелёный — влезает (наведи на ячейку — разбивка по строкам), красный — не влезает.',
    '«Кегль EN сейчас» — как текст нарисован в текущей анимации. Где фиксированный кегль меньше (−N%), при сборке Spine с костями для текста поле/плашку можно расширить, если рядом есть место.',
    'Текст один для деска и мобилки; различаются только переносы строк под ширину поля. Переносы ставим по словам; «3+ SCATTERS», «x100» не разрываем.',
    'Поле, px — область текста в дизайн-пикселях макета (деск 1932×940, моб 780×1416).',
    'Шрифт игры (Luckiest Guy) не содержит кириллицу и часть букв — см. лист «Шрифты». Для RU/UK/KK и недостающих букв вёрстка проверена на замещающем шрифте (Arial Black).',
    't_free_spins: сейчас это арт из PSB (два слоя: FREE золотом, SPINS голубым). Для перевода его нужно рисовать текстом в том же виде (Luckiest Guy, наклон, последнее слово голубым); в таблице он так и смоделирован.',
    'Логотип NEON REELS, иероглифы на драконе, символы (скаттер, вайлд, монета x100) — арт, не переводятся. Число спинов на бонус-скрине — живая цифра (DOM) поверх плашки.',
    'Термины слотов: WILD, SCATTER в латинских языках оставлены как есть (AZ/UZ — SKATTER), в кириллице — ВАЙЛД, СКАТТЕР.',
]


# --- fields -------------------------------------------------------------------------------
recs = fitlib.fields()


def lines_for_rec(L, r):
    return lines_for(r['key'], L, r)

# --- per-language results at the fixed size ---------------------------------------------
FIT = {}
for L in ['en'] + LANGS:
    for r in recs:
        ls = lines_for_rec(L, r); im = draw(r['key'], ls)
        w, h = im.width * r['s'], im.height * r['s']
        s_nat = 1.0 if L == 'en' else best(r['key'], TR[L][r['key']], r['bw'], r['bh'], r['nl'])[0] / (r['s'] / r['k'])
        FIT.setdefault(L, {}).setdefault(r['key'], []).append(dict(
            where=f"{r['screen']}_{r['dev']}", lines=ls, used_w=round(w / r['bw'], 3), k_own=round(min(s_nat, 1.0), 3),
            status='ok' if w <= r['bw'] + 0.5 and h <= r['bh'] + 0.5 else 'nofit'))
json.dump(dict(fields=[{k: v for k, v in r.items() if k not in ('bw', 'bh')} for r in recs], fit=FIT),
          open(os.path.join(OUT, 'проверка_языков', 'fit.json'), 'w'), ensure_ascii=False, indent=1)


# --- per-language sheet: every field box with the text at its fixed size -------------------
def sheet(L):
    tiles = []
    for r in recs:
        im = draw(r['key'], lines_for_rec(L, r)); w, h = max(1, round(im.width * r['s'])), max(1, round(im.height * r['s']))
        bw, bh = r['box_w'], r['box_h']
        tile = Image.new('RGB', (max(bw, 330) + 20, bh + 44), GAME['tile']); d = ImageDraw.Draw(tile)
        ox = 10 + (max(bw, 330) - bw) // 2
        d.rectangle([ox, 34, ox + bw, 34 + bh], outline=(0, 220, 230), width=2)
        d.text((10, 8), f"{r['screen']} · {r['dev']} · {r['key']} · {r['px']}px", fill=(200, 200, 200),
               font=fnt('/System/Library/Fonts/Supplemental/Arial.ttf', 16))
        sm = im.resize((w, h), Image.LANCZOS)
        tile.paste(sm, (ox + (bw - w) // 2, 34 + (bh - h) // 2), sm)
        tiles.append(tile)
    W = 2300; x = y = 10; rowh = 0; pos = []
    for t in tiles:
        if x + t.width > W: x, y, rowh = 10, y + rowh + 10, 0
        pos.append((x, y)); x += t.width + 10; rowh = max(rowh, t.height)
    out = Image.new('RGB', (W, y + rowh + 10), GAME['sheet'])
    for t, p in zip(tiles, pos): out.paste(t, p)
    out.save(os.path.join(OUT, 'проверка_языков', f'{L}.jpg'), quality=86)


for L in ['en'] + LANGS: sheet(L)


# --- fonts coverage ---------------------------------------------------------------------
USED = list(dict.fromkeys(STYLES[v['style']]['fam'] for v in TEXTS.values()))


def coverage(L):
    out = {}
    for fam in USED:
        keys = [k for k, v in TEXTS.items() if STYLES[v['style']]['fam'] == fam]
        chars = {c for k in keys for c in TR[L][k] if c not in '  '}
        out[fam] = ''.join(sorted(c for c in chars if not has_glyph(c, fam)))
    return out


# --- xlsx ----------------------------------------------------------------------------------
LANG_NAME = dict(ru='RU · русский', uk='UK · українська', kk='KK · қазақша', az='AZ · azərbaycan', de='DE · Deutsch',
                 es='ES · español', fr='FR · français', pl='PL · polski', pt='PT · português (BR)', tr='TR · Türkçe',
                 uz='UZ · oʻzbek (лат.)')
SCREEN = {'feature': 'Фича-скрин', 'bonus': 'Бонус-скрин'}
dst = os.path.join(OUT, GAME['xlsx'])
wb = xlsxwriter.Workbook(dst)
base = dict(font_name='Arial', font_size=10, text_wrap=True, valign='top', border=1, border_color='#BBBBBB')
f_hdr = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color=GAME['hdr'], valign='vcenter'))
f_cell = wb.add_format(base); f_ok = wb.add_format(dict(base, bg_color='#E2F0D9')); f_bad = wb.add_format(dict(base, bg_color='#F4C7C3'))
f_pct = {k: wb.add_format(dict(base, num_format='0%', align='center', bg_color=c)) for k, c in dict(ok='#E2F0D9', nofit='#F4C7C3').items()}
f_note = wb.add_format(dict(font_name='Arial', font_size=10, italic=True)); f_note_b = wb.add_format(dict(font_name='Arial', font_size=10, bold=True))


def header(ws, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths)): ws.write(0, i, c, f_hdr); ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)


def tight(L, key): return max(FIT[L][key], key=lambda x: x['used_w'])


ws = wb.add_worksheet('Тексты'); NL = len(LANGS)
header(ws, ['Ключ', 'Где', 'EN (оригинал)'] + [LANG_NAME[L] for L in LANGS] +
       ['Как разбито в макете (EN)', 'Поле, px (Ш×В)', 'Кегль, px (фикс.)', 'Кегль EN сейчас, px', 'Кость Spine (сейчас)', 'Шрифт'],
       [13, 24, 30] + [28] * NL + [24, 16, 14, 14, 16, 14])
order = list(dict.fromkeys(r['key'] for r in recs))
for row, key in enumerate(order, 1):
    rs = [r for r in recs if r['key'] == key]; t = TEXTS[key]
    ws.write(row, 0, key, f_cell)
    ws.write(row, 1, '\n'.join(dict.fromkeys(f"{SCREEN[r['screen']]} · {'деск' if r['dev'] == 'desk' else 'моб'}" for r in rs)) + '\n' + WHERE[key], f_cell)
    ws.write(row, 2, t['en'], f_cell)
    for j, L in enumerate(LANGS):
        m = tight(L, key)
        ws.write(row, 3 + j, TR[L][key], f_ok if m['status'] == 'ok' else f_bad)
        ws.write_comment(row, 3 + j, ('Влезает' if m['status'] == 'ok' else 'НЕ ВЛЕЗАЕТ') + f" фиксированным кеглем; занято "
                         f"{round(m['used_w'] * 100)}% ширины поля ({m['where']}). Разбито: {' / '.join(m['lines'])}",
                         dict(x_scale=2, y_scale=1.2))
    c = 3 + NL
    dv = lambda r: 'деск' if r['dev'] == 'desk' else 'моб'
    st = STYLES[t['style']]
    for v in [' / '.join(t['en_lines']),
              '\n'.join(f"{dv(r)}: {r['box_w']}×{r['box_h']}" for r in rs),
              '\n'.join(f"{dv(r)}: {r['px']:g}" for r in rs),
              '\n'.join(f"{dv(r)}: {r['en_px']}" + ('' if r['k'] > 0.995 else f" (−{round((1 - r['k']) * 100)}%, упирается в {r['limit'].upper()})") for r in rs),
              rs[0]['bone'], FAM[st['fam']][0] + (f" {st['wght']}" if st.get('wght') else '')]:
        ws.write(row, c, v, f_cell); c += 1
n = len(order) + 2
for i, s in enumerate(NOTES):
    ws.write(n + i, 0, s, f_note_b if i == 0 else f_note)

wf = wb.add_worksheet('Проверка')
header(wf, ['Ключ'] + [L.upper() for L in LANGS], [14] + [9] * NL)
for row, key in enumerate(order, 1):
    wf.write(row, 0, key, f_cell)
    for j, L in enumerate(LANGS):
        m = tight(L, key); wf.write(row, 1 + j, m['used_w'], f_pct[m['status']])
wf.write(len(order) + 2, 0, 'Сколько ширины поля занимает текст при фиксированном кегле (≤100% = влезает). Худший из деск/моб. Картинки: проверка_языков/<язык>.jpg.', f_note)

wfo = wb.add_worksheet('Шрифты')
header(wfo, ['Язык'] + [f"{FAM[f][0]} ({FAM_USE[f]})" for f in USED] + ['Итог'], [16] + [44] * len(USED) + [48])
for row, L in enumerate(LANGS, 1):
    cv = coverage(L); wfo.write(row, 0, LANG_NAME[L], f_cell)
    for j, fam in enumerate(USED):
        wfo.write(row, 1 + j, 'все символы есть' if not cv[fam] else 'нет символов: ' + cv[fam], f_ok if not cv[fam] else f_bad)
    bad = any(cv.values())
    wfo.write(row, 1 + len(USED), 'отображается правильно' if not bad else
              ('нужен другой шрифт: в шрифтах игры нет кириллицы' if L in ('ru', 'uk', 'kk') else
               'в шрифте игры нет этих букв: нужен файл шрифта с ними или замена'), f_ok if not bad else f_bad)
wfo.write(len(LANGS) + 2, 0, f"Проверено по файлам шрифтов игры (front/fonts: latin + latin-ext подмножества {', '.join(FAM[f][0] for f in USED)}).", f_note)

ws2 = wb.add_worksheet('Поля')
header(ws2, ['Экран', 'Устройство', 'Ключ', 'Кость (сейчас)', 'Поле Ш', 'Поле В', 'Кегль фикс., px', 'Кегль EN сейчас, px', 'Упирается в'],
       [12, 12, 14, 18, 9, 9, 14, 16, 12])
for row, r in enumerate(recs, 1):
    for col, v in enumerate([r['screen'], r['dev'], r['key'], r['bone'], r['box_w'], r['box_h'], r['px'], r['en_px'], r['limit'].upper()]):
        ws2.write(row, col, v, f_cell)
ws2.write(len(recs) + 2, 0, f"Кости — из текущего экспорта (front/img/{GAME['slug']}/screens). Отдельные кости txt_* без текста сделаем, когда утвердим правки экранов.", f_note)
wb.close(); print(dst)
for r in recs: print(f"{r['screen']:8}{r['dev']:5}{r['key']:14} box {r['box_w']}x{r['box_h']}  EN {r['en_px']}px -> fixed {r['px']}px ({r['k']:.2f}, {r['limit']})")
print('nofit:', [(L, k, x['where']) for L in FIT for k in FIT[L] for x in FIT[L][k] if x['status'] != 'ok'])
