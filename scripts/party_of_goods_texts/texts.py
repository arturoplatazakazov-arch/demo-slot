# Every translatable string on the Party Gods preview screens
# (scripts/party_of_goods_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn. style -> doc.STYLES: 'tag' = Cinzel 900 gold strap
# line, 'cap' = Luckiest Guy gold on the crimson plate, 'sub' = Cinzel 800 cream under it,
# 'tap' = Cinzel 900 gold, 'title_art' = the bonus title, today a PSB raster
# (Popups/bonus_spins_win/bonus_spins_Win: BONUS / SPINS / WIN) — a translation has to be
# drawn as text in that look (Luckiest-like gold).
TEXTS = {
    'tag':    dict(en_lines=['CASCADING WINS  ·  8+ ANYWHERE PAYS'], style='tag', px=64),
    't_fs':    dict(en_lines=['FREE SPINS'], style='cap', px=96),
    't_multi': dict(en_lines=['MULTIPLIERS'], style='cap', px=96),
    't_bolt':  dict(en_lines=['ZEUS BOLT'], style='cap', px=96),
    'd_fs':    dict(en_lines=['3+ SCATTERS · UP TO 20 SPINS'], style='sub', px=64),
    'd_multi': dict(en_lines=['x2 x3 x5 x7 ADD UP ON A WIN'], style='sub', px=64),
    'd_bolt':  dict(en_lines=['CLEARS ITS ROW & COLUMN'], style='sub', px=64),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='tap', px=80),
    't_bonus_win':  dict(en_lines=['BONUS', 'SPINS', 'WIN'], style='title_art', px=96),
    'tap_start':    dict(en_lines=['TAP TO START'], style='tap', px=80),
}
for v in TEXTS.values(): v['en'] = ' '.join(v['en_lines'])

WHERE = {'tag': 'строка под логотипом', 't_fs': 'карточка 1, плашка', 't_multi': 'карточка 2, плашка',
         't_bolt': 'карточка 3, плашка', 'd_fs': 'карточка 1, под плашкой', 'd_multi': 'карточка 2, под плашкой',
         'd_bolt': 'карточка 3, под плашкой', 'tap_continue': 'подсказка внизу',
         't_bonus_win': 'заголовок в театре над медальоном (сейчас арт PSB)', 'tap_start': 'подсказка внизу'}

# Where each string sits. Geometry mirrors party_of_goods_screens.py:
#   slot(iw, ih) = width the EN art is drawn at in the game (design px), from the image size
#   box_w        = width a translation may use without touching other art (design px)
#   box_h        = <= 5: x EN height in the game; > 5: absolute design px
# Plate (desk / mob) 340x97.8 / 420x120.8: caption <= 0.66 plate wide, 0.42 plate tall.
# Sub-line 30 / 28 px tall under the plate (desk: cards 400 apart -> 380 wide; mob: right column
# 430 wide); only ~6-10 px free above it (plate) and some below -> 1.4 / 1.7 x EN height.
# 0.66 -> 0.78 of the plate: the gold plate's flat middle is wider than the EN art used,
# and the row of three captions now shares one size (GROUPS below).
def _cap(pw, ph): return (lambda iw, ih: min(pw * 0.78, ph * 0.42 * iw / ih)), pw * 0.78, ph * 0.42
def _sub(sw, sh): return (lambda iw, ih: min(sw, sh * iw / ih))


CARD = dict(desk=(_cap(340, 97.77), _sub(390, 30), 380, 1.4), mob=(_cap(420, 120.77), _sub(430, 28), 430, 1.7))
FIELDS = []   # (screen, device, key, slot(iw, ih), box_w, box_h, bone in the current export)
for dev, (cap, sub, sw, sk) in CARD.items():
    for i, k in enumerate(['fs', 'multi', 'bolt']):
        FIELDS.append(('feature', dev, f't_{k}', cap[0], cap[1], cap[2], f'plate{i} (слот cap{i})'))
        FIELDS.append(('feature', dev, f'd_{k}', sub, sw, sk, f'sub{i}'))
FIELDS += [
    # strap line: desk between the gods (|x| < 600), logo bottom 187 / medallion top 109;
    # mob full width, logo bottom 383 / plate top 228 -> 2 lines possible
    ('feature', 'desk', 'tag', lambda iw, ih: min(1932 * 0.9, 34 * iw / ih), 1200, 2.0, 'tag_b'),
    ('feature', 'mob', 'tag', lambda iw, ih: min(780 * 0.9, 30 * iw / ih), 702, 2.2, 'tag_b'),
    ('feature', 'desk', 'tap_continue', lambda iw, ih: 52 * iw / ih, 1100, 1.8, 'tap_b'),
    ('feature', 'mob', 'tap_continue', lambda iw, ih: 54 * iw / ih, 700, 2.1, 'tap_b'),
    # inside the theatre's curtain opening: EN width (292 / 324) + ~8%, EN art height
    ('bonus', 'desk', 't_bonus_win', lambda iw, ih: 292.19, 315, 248, 'title_b'),
    ('bonus', 'mob', 't_bonus_win', lambda iw, ih: 323.66, 350, 275, 'title_b'),
    # desk: theatre ends at -365, edge -470, gods at |x| > 500; mob: gods end at -572, edge -708
    ('bonus', 'desk', 'tap_start', lambda iw, ih: 50 * iw / ih, 1000, 1.8, 'tap_b'),
    ('bonus', 'mob', 'tap_start', lambda iw, ih: 54 * iw / ih, 700, 1.6, 'tap_b'),
]

# Fields that sit side by side and must share one size: the three plate captions and the
# three lines under them.
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('fs', 'multi', 'bolt')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]
