# Gangsta Casino localisation preview: the game's own Spine screens, captured once from the
# page (loc-gangsta-shot.html -> gcshot2/*.png + the caption geometry below), with every
# language's caption drawn into its box at the ONE fixed size the game uses
# (front/js/gangsta-casino/slot.js PACK_CAPTIONS: fontSize = line * 0.62 * s * fix).
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = '/Users/arturkasian/demo_slot'
SC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'gangsta_casino_texts'))
from texts import TEXTS                      # noqa: E402
from translations import TR, LANGS           # noqa: E402

SHOTS = os.path.join(SC, 'gcshot2')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SC, 'gcprev')
ART = os.path.join(ROOT, 'front', 'img', 'gangsta-casino')
FONT = os.path.join(ROOT, 'scripts', 'gangsta_casino_texts', 'fonts', 'shantell-sans-latin-800.ttf')
os.makedirs(OUT, exist_ok=True)

# Where each caption's box sits in the captured image: the bone centre (canvas px, from
# loc-gangsta-shot.html) — and how big it is: straight from the localisation table
# (gangsta_casino_texts, sheet «Поля»), in design px of the PSB canvas.
POS = {
    ('feature', 'desk'): {'free_spins': (424.7, 520.9), 'expanding_wild': (700.0, 520.9),
                          'multiplier': (975.3, 513.3), 'multiplier_note': (975.3, 540.5),
                          'tap_to_continue': (700.0, 615.8)},
    ('feature', 'mob'): {'free_spins': (99.0, 589.0), 'expanding_wild': (300.0, 589.0),
                         'multiplier': (501.0, 582.0), 'multiplier_note': (501.0, 605.0),
                         'tap_to_continue': (300.0, 668.0)},
    ('bonus', 'desk'): {'bonus_game': (700.0, 559.9), 'tap_to_start': (700.0, 631.7)},
    ('bonus', 'mob'): {'bonus_game': (300.0, 539.0), 'tap_to_start': (300.0, 592.0)},
}
# design px of the field and the one fixed font size, per the table: key -> (W, lines, font px)
FIELDS = {
    ('feature', 'desk'): {'free_spins': (273.2, 2, 37.0), 'expanding_wild': (317.6, 2, 35.5),
                          'multiplier': (273.2, 1, 29.2), 'multiplier_note': (273.0, 1, 14.3),
                          'tap_to_continue': (520.0, 2, 46.7)},
    ('feature', 'mob'): {'free_spins': (195.0, 2, 29.6), 'expanding_wild': (195.0, 2, 21.8),
                         'multiplier': (195.0, 1, 20.8), 'multiplier_note': (195.2, 1, 10.2),
                         'tap_to_continue': (440.0, 2, 39.6)},
    ('bonus', 'desk'): {'bonus_game': (252.7, 1, 29.2), 'tap_to_start': (600.0, 1, 39.4)},
    ('bonus', 'mob'): {'bonus_game': (252.7, 1, 29.2), 'tap_to_start': (700.0, 1, 45.9)},
}
# design canvas -> captured image
K = {'desk': 1400 / 1932, 'mob': 600 / 780}
BG = {('feature', 'desk'): 'bg_base_desk.jpg', ('feature', 'mob'): 'bg_base_mob.jpg',
      ('bonus', 'desk'): 'bg_bonus_desk.jpg', ('bonus', 'mob'): 'bg_bonus_mob.jpg'}
FILL = (255, 243, 200)          # .pack-caption color
_fc = {}


def font(px):
    px = max(4, int(round(px)))
    if px not in _fc: _fc[px] = ImageFont.truetype(FONT, px)
    return _fc[px]


def wrap(text, f, max_w, max_lines):
    """Greedy wrap, as the browser breaks a flex line — at most max_lines lines."""
    if max_lines <= 1: return [text]
    words, lines, cur = text.split(' '), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if cur and f.getlength(t) > max_w and len(lines) + 1 < max_lines:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    return lines


def caption(text, px, max_w, max_lines):
    """One caption exactly as the page styles it: cream fill, hard drop shadow, warm glow."""
    f = font(px)
    lines = wrap(text, f, max_w, max_lines)
    step = int(round(px * 1.02)) if max_lines > 1 else int(round(px * 1.0))
    pad = int(px * 0.6) + 8
    w = int(max(f.getlength(l) for l in lines)) + pad * 2
    h = step * (len(lines) - 1) + int(px * 1.35) + pad * 2
    mask = Image.new('L', (w, h))
    d = ImageDraw.Draw(mask)
    for i, l in enumerate(lines):
        d.text(((w - f.getlength(l)) / 2, pad + i * step), l, font=f, fill=255)
    out = Image.new('RGBA', (w, h))
    glow = mask.filter(ImageFilter.GaussianBlur(max(1, px * 0.25))).point(lambda a: int(a * 0.55))
    out.paste(Image.new('RGBA', (w, h), (255, 190, 60, 255)), (0, 0), glow)
    sh = mask.point(lambda a: int(a * 0.75))
    out.paste(Image.new('RGBA', (w, h), (0, 0, 0, 255)), (0, max(1, int(px * 0.06))), sh)
    out.paste(Image.new('RGBA', (w, h), FILL + (255,)), (0, 0), mask)
    return out.crop(out.getbbox() or (0, 0, w, h))


def text_for(key, lang):
    return TEXTS[key]['en'] if lang == 'en' else TR[lang][key]


for (screen, lay), pos in POS.items():
    shot = Image.open(os.path.join(SHOTS, f'{screen}_{lay}.png')).convert('RGBA')
    W, H = shot.size
    bg = Image.open(os.path.join(ART, BG[(screen, lay)])).convert('RGB')
    k = max(W / bg.width, H / bg.height)
    bg = bg.resize((round(bg.width * k), round(bg.height * k)), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = Image.blend(bg, Image.new('RGB', (W, H), (4, 4, 8)), 0.88)     # the screen's own dim
    base = bg.convert('RGBA'); base.alpha_composite(shot)
    scale = K[lay]
    for lang in ['en'] + list(LANGS):
        im = base.copy()
        for key, (x, y) in pos.items():
            bw, lines, px = FIELDS[(screen, lay)][key]
            t = caption(text_for(key, lang), px * scale, bw * scale, lines)
            im.alpha_composite(t, (round(x - t.width / 2), round(y - t.height / 2)))
        im.convert('RGB').save(os.path.join(OUT, f'{screen}_{lay}_{lang}.jpg'), quality=88)
    print(screen, lay, 'ok')
