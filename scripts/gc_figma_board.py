"""Gangsta Casino board for Figma, laid out after the layout-spec file
("ТЗ на слоты"): numbered sections, each = horizontal view 1932x940 +
vertical view 780x1416 + a notes card; then an assets sheet. Output: one SVG
(drag into Figma -> named groups, image layers, text layers) + the raw files.
Usage: python scripts/gc_figma_board.py <shots_dir> <out_dir>"""
import base64, io, os, shutil, sys
from html import escape
from PIL import Image

SHOTS, OUT = sys.argv[1], sys.argv[2]
LAYERS = sys.argv[3] if len(sys.argv) > 3 else None  # scripts/gc_figma_layers.py output
ROOT = os.path.join(os.path.dirname(__file__), '..', 'front', 'img', 'gangsta-casino')
os.makedirs(os.path.join(OUT, 'screens'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True)

SECTIONS = [
    ('00_feature_screen', 'Превью-экран фич', [
        'После прелоадера: Spine feature_screen_v2 (деск) / feature_screen_v2_mob (моб), затемнение 90 %.',
        'intro 3 с, затем idle в цикле; по тапу экран растворяется в прозрачность.',
        '! Подпись «BONUS WHEEL» устарела (колесо заменено множителем) — ждём арт.']),
    ('01_general', 'Общий вид / Размеры', [
        'Деск: 1932 x 940 (safe-зона 1720), моб: 780 x 1416 (макс. высота по ТЗ; среднее по ТЗ — 1316).',
        'Рил 5 x 3, клетка 197 x 200; рамка — Spine frame_v2 / frame_mob_v2, символы уходят под рамку.',
        'Символов 11 (ТЗ: 9): 4 дешёвых (оружие), 4 дорогих (персонажи), Wild (расширяется на барабан), Scatter, Множитель.',
        '11 линий. Панель управления — своя (V3-бар), не панель из ТЗ.',
        'Название игры — посередине над рилом (деск и моб).']),
    ('02_highlight', 'Выделение символов', [
        'Выигравшие символы — Spine-анимация win (1.3 с), остальные затемняются.',
        'Линия выигрыша — Spine winlines (line{n}_in + line{n}_loop), от рамки до рамки, ЗА символами.',
        'Несколько линий: сначала все вместе, потом по одной в цикле.']),
    ('03_total_win', 'Сумма выигрыша', [
        'Сумма спина показывается по центру над рилом (деск и моб).',
        '! ТЗ: только моб, между рилом и панелью, с текстом «WIN» и валютой — у нас без «WIN» и валюты.']),
    ('04_combination_win', 'Сумма выигрыша комбинации', [
        'Линии показываются по очереди в цикле.',
        '! Отдельная сумма одной комбинации сейчас не выводится — та же плашка суммы спина.']),
    ('05_buy_button', 'Кнопка покупки бонуса', [
        'Сундук + пульсирующий красный луч + надпись BUY FREE SPINS (3 слоя PSB).',
        'Деск: слева от рила; моб: под рилом слева.',
        '! ТЗ: справа и с ценой на кнопке — у нас цена только в диалоге (решение продукта).']),
    ('06_buy_dialog', 'Диалог покупки бонуса', [
        'BUY FREE SPINS + сундук + «10 FREE SPINS» + цена (x87 ставки).',
        '! Кнопки — иконки ✗ / ✓ вместо текста Cancel / Buy.']),
    ('07_big_win', 'Сообщение Big Win', [
        'BIG / MEGA / EPIC WIN: плашка + счётчик суммы, лучи; составной, анимируется.']),
    ('08_fs_win', 'Сообщение выигрыша фри спинов', [
        'Вход в бонус: затемнение → Spine-бонус-экран (следующий кадр) → «TAP TO START».',
        'CSS-фолбэк (этот кадр): YOU WON 10 FREE SPINS.']),
    ('08b_fs_screen', 'Бонус-экран (Spine)', [
        'bonus_screen_v4 / _mob: клуб, музыкальный автомат со счётчиком спинов (цифры — слоты скелета).']),
    ('09_fs_total_win', 'Сумма выигрыша после фри спинов', [
        'TOTAL WIN + сумма + летящие купюры.']),
    ('10_fs_mode', 'Режим фри спинов', [
        'Фон меняется на ночной клуб (живой Spine-фон на моб), герои клуба.',
        'Счётчик оставшихся спинов — автомат «Free spins» (Spine freespins_v2, counter_update).',
        'Множитель раунда копится до конца фри спинов (на кадре x9).']),
    ('11_multiplier_base', 'Множитель (новая механика)', [
        'Фишка-множитель: после остановки буква G в центре переворачивается в значение x2…x25 (0.7 с).',
        'База: множители умножают выигрыш линий спина (сумма значений) → значение летит в плашку MULTIPLIER.',
        'Фри спины: каждый множитель добавляется к плашке и действует до конца раунда.',
        'Плашка и подмена буквы пока наши (CSS + кроп фишки) — ждём арт дизайнера.']),
]
SPINE_NOTE = [
    'Рантайм Spine 4.1 (экспорт 4.2/4.3 грузится на 4.1). Файлы: /<имя>/animation.atlas | .json | .png',
    'common_1..4, rare_blue/green/purple/yellow, scatter, wof: win',
    'wild: win_small, expand, win_big, idle_big',
    'scene/background_v2, background_mob_v3, bonus_bg_mob_v3: idle',
    'scene/frame_v2, frame_mob_v2, logo_v2, logo_mob, hero_man, hero_woman: idle, win',
    'scene/freespins_v2: idle, counter_update, win',
    'feature_screen_v2(_mob), bonus_screen_v4(_mob): intro, idle',
    'winlines (сгенерирован кодом): line1..11_in, line1..11_loop',
    '! ТЗ: у scatter нужны landing / idle / win (1.7 с) — у нас только win; у Wild нет idle для фри спинов.',
]
ASSETS = [
    ('Символы', [f'symbols/{n}.png' for n in ['common_1', 'common_2', 'common_3', 'common_4', 'rare_purple', 'rare_yellow', 'rare_blue', 'rare_green', 'wild', 'scatter', 'wof', 'wild_big']]),
    ('Рил / рамка', ['ui/frame.png', 'ui/frame_mob.png']),
    ('Логотип', ['ui/logo.png', 'ui/logo_mob.png', 'ui/logo_preloader.png']),
    ('Кнопка покупки', ['ui/buy_chest.png', 'ui/buy_cone.png', 'ui/buy_text.png', 'ui/buy_chest_mob.png', 'ui/buy_cone_mob.png', 'ui/buy_text_mob.png']),
    ('Попапы', ['ui/buy_title.png', 'ui/chest.png', 'ui/plate.png']),
    ('Фри спины', ['ui/fs_counter.png', 'ui/bonus_table_mob.png']),
    ('Множитель', ['ui/mult_hub_g.png', 'ui/mult_hub_blank.png', '@mult_plate.png']),
    ('Фоны', ['bg_base_desk.jpg', 'bg_bonus_desk.jpg', 'bg_base_mob.jpg', 'bg_bonus_mob.jpg']),
    ('Каталог', ['cover.jpg']),
]

# multiplier plate is CSS: cut it from the lit base screenshot
Image.open(os.path.join(SHOTS, '11_multiplier_base_h.png')).crop((1214, 0, 1494, 116)).save(os.path.join(OUT, 'assets', 'mult_plate.png'))

def data_uri(path, jpeg=False):
    im = Image.open(path)
    buf = io.BytesIO()
    if jpeg:
        im.convert('RGB').save(buf, 'JPEG', quality=85); mime = 'image/jpeg'
    else:
        buf.write(open(path, 'rb').read()); mime = 'image/jpeg' if path.endswith('.jpg') else 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(buf.getvalue()).decode()

FONT = "font-family=\"Inter\""
parts = []
def text(x, y, s, size=40, weight=400, fill='#ffffff', name=None):
    nm = f' id="{escape(name)}"' if name else ''
    parts.append(f'<text{nm} x="{x}" y="{y}" {FONT} font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(s)}</text>')
def image(x, y, w, h, uri, name):
    parts.append(f'<image id="{escape(name)}" x="{x}" y="{y}" width="{w}" height="{h}" href="{uri}" xlink:href="{uri}"/>')
def card(x, y, w, lines, name):
    h = 60 + 56 * len(lines)
    parts.append(f'<g id="{escape(name)}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#e9e9e9"/>')
    for i, ln in enumerate(lines):
        fill = '#b00020' if ln.startswith('!') else '#111111'
        text(x + 30, y + 64 + 56 * i, ('• ' if not ln.startswith('!') else '') + ln, 30, 500, fill)
    parts.append('</g>')
    return h

X0, GAP = 0, 100
HX, VX = X0, X0 + 1932 + GAP
CX = VX + 780 + GAP
y = 0
text(X0, y + 120, 'Gangsta Casino — макет по ТЗ на слоты', 110, 700, name='Title')
y += 260

# Assembled screens: every part a layer at its place (scripts/gc_figma_layers.py)
if LAYERS:
    import json
    asm_start, asm_y0 = len(parts), y
    parts.append('<g id="Сборка экранов (слои)">')
    text(X0, y + 82, 'Сборка экранов — базовый и бонусный (слои)', 70, 700)
    y += 180
    rows = [(('desk_base', 'Horizontal View — Base'), ('desk_bonus', 'Horizontal View — Free Spins')),
            (('mob_base', 'Vertical View — Base'), ('mob_bonus', 'Vertical View — Free Spins'))]
    for row in rows:
        x, rowh = X0, 0
        for key, label in row:
            d = json.load(open(os.path.join(LAYERS, key, 'layers.json')))
            W_, H_ = d['width'], d['height']
            dst = os.path.join(OUT, 'layers', key); os.makedirs(dst, exist_ok=True)
            text(x, y - 24, f'{label}  {W_} x {H_}', 32, 500, '#9a9a9a')
            parts.append(f'<svg id="{escape(label)}" x="{x}" y="{y}" width="{W_}" height="{H_}" viewBox="0 0 {W_} {H_}" overflow="hidden">')
            parts.append(f'<rect width="{W_}" height="{H_}" fill="#000"/>')
            for L in d['layers']:
                src = os.path.join(LAYERS, key, L['file'])
                shutil.copy(src, os.path.join(dst, L['file']))
                jpeg = L['name'] == 'background'
                image(L['x'], L['y'], L['w'], L['h'], data_uri(src, jpeg=jpeg), L['name'])
            parts.append('</svg>')
            x += W_ + 120; rowh = max(rowh, H_)
        y += rowh + 200
    parts.append('</g>')
    aw, ah = 1932 * 2 + 120, y - asm_y0
    open(os.path.join(OUT, 'gangsta-casino_screens_layers.svg'), 'w').write(
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{aw + 200}" height="{ah + 200}" viewBox="-100 {asm_y0 - 100} {aw + 200} {ah + 200}">'
        f'<rect x="-100" y="{asm_y0 - 100}" width="{aw + 200}" height="{ah + 200}" fill="#1e1e1e"/>' + ''.join(parts[asm_start:]) + '</svg>')
    y += 100

for idx, (key, title, notes) in enumerate(SECTIONS):
    parts.append(f'<g id="{escape(f"{idx:02d} {title}")}">')
    parts.append(f'<rect x="{X0}" y="{y}" width="110" height="110" rx="14" fill="none" stroke="#ffffff" stroke-width="6"/>')
    text(X0 + 55 - (24 if idx >= 10 else 14) * 1, y + 80, str(idx), 70, 700)
    text(X0 + 150, y + 82, title, 70, 700)
    top = y + 180
    for view, vx, (w, h) in (('h', HX, (1932, 940)), ('v', VX, (780, 1416))):
        src = os.path.join(SHOTS, f'{key}_{view}.png')
        shutil.copy(src, os.path.join(OUT, 'screens', f'{key}_{"desk" if view == "h" else "mob"}.png'))
        image(vx, top, w, h, data_uri(src, jpeg=True), f'{key} {"Horizontal View" if view == "h" else "Vertical View"}')
        text(vx, top - 24, 'Horizontal View 1932 x 940' if view == 'h' else 'Vertical View 780 x 1416', 32, 500, '#9a9a9a')
    card(CX, top, 2300, notes, f'{key} Description')
    parts.append('</g>')
    y = top + 1416 + 200

# Spine
NS = len(SECTIONS)
parts.append(f'<g id="{NS} Анимации Spine">')
parts.append(f'<rect x="{X0}" y="{y}" width="110" height="110" rx="14" fill="none" stroke="#ffffff" stroke-width="6"/>')
text(X0 + 31, y + 80, str(NS), 70, 700); text(X0 + 150, y + 82, 'Анимации (Spine)', 70, 700)
h = card(X0, y + 180, 2400, SPINE_NOTE, 'Spine Description')
parts.append('</g>')
y += 180 + h + 200

# Assets
parts.append(f'<g id="{NS + 1} Ассеты">')
text(X0 + 150, y + 82, 'Ассеты', 70, 700)
parts.append(f'<rect x="{X0}" y="{y}" width="110" height="110" rx="14" fill="none" stroke="#ffffff" stroke-width="6"/>')
text(X0 + 31, y + 80, str(NS + 1), 70, 700)
y += 200
for group, files in ASSETS:
    parts.append(f'<g id="{escape("Ассеты / " + group)}">')
    text(X0, y + 50, group, 48, 700)
    x, rowh = X0, 0; y0 = y + 90
    for f in files:
        path = os.path.join(OUT, 'assets', f[1:]) if f.startswith('@') else os.path.join(ROOT, f)
        if not f.startswith('@'):
            shutil.copy(path, os.path.join(OUT, 'assets', os.path.basename(f)))
        w, h = Image.open(path).size
        if group == 'Фоны' or group == 'Каталог':
            k = 900 / max(w, h); w, h = int(w * k), int(h * k)
        if x + w > 5000:
            x = X0; y0 += rowh + 110; rowh = 0
        parts.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" fill="#2b2b2b"/>')
        image(x, y0, w, h, data_uri(path), os.path.splitext(os.path.basename(f.lstrip('@')))[0])
        text(x, y0 + h + 40, os.path.basename(f.lstrip('@')) + f'  {Image.open(path).size[0]}x{Image.open(path).size[1]}', 26, 500, '#9a9a9a')
        x += w + 80; rowh = max(rowh, h)
    parts.append('</g>')
    y = y0 + rowh + 160
parts.append('</g>')

W = CX + 2300 + 100
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{y}" viewBox="-100 -100 {W + 100} {y + 100}">'
       f'<rect x="-100" y="-100" width="{W + 100}" height="{y + 100}" fill="#1e1e1e"/>' + ''.join(parts) + '</svg>')
open(os.path.join(OUT, 'gangsta-casino_board.svg'), 'w').write(svg)
print('svg MB', round(len(svg) / 1e6, 1), 'size', W, y)
