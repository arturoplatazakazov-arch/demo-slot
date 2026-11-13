# Every translatable string on the Golden Caravan preview screens
# (scripts/golden_caravan_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn. style -> doc.STYLES (all Cinzel):
#   'title' = Cinzel 900 gold (title()), 'tap' / 'won' = title() in sand,
#   'caption' = Cinzel 800 sand (lines()), 'caption_gold' = lines() in gold.
TEXTS = {
    't_tumble': dict(en_lines=['AVALANCHE'], style='title', px=56),
    't_multi':  dict(en_lines=['MULTIPLIERS'], style='title', px=56),
    't_bomb':   dict(en_lines=['BOMBS'], style='title', px=56),
    't_fs':     dict(en_lines=['FREE SPINS'], style='title', px=56),
    'd_tumble': dict(en_lines=['8+ SAME SYMBOLS', 'ANYWHERE WIN'], style='caption', px=34),
    'd_multi':  dict(en_lines=['x2 x3 x5 TOKENS', 'BOOST THE CASCADE'], style='caption', px=34),
    'd_bomb':   dict(en_lines=['CLEAR THEIR WHOLE', 'ROW AND COLUMN'], style='caption', px=34),
    'd_fs':     dict(en_lines=['3 / 4 / 5 SCATTERS', 'AWARD 8 / 10 / 12'], style='caption', px=34),
    'd_buy':    dict(en_lines=['BUY BONUS', '100x BET'], style='caption_gold', px=32),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='tap', px=52),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='title', px=140),
    't_you_won':    dict(en_lines=['YOU HAVE WON'], style='won', px=54),
    'chip_multi':   dict(en_lines=['MULTIPLIERS ADD UP', 'ON EVERY CASCADE'], style='caption', px=36),
    'chip_fs':      dict(en_lines=['SCATTERS RETRIGGER', 'UP TO +12 SPINS'], style='caption', px=36),
    'tap_start':    dict(en_lines=['TAP TO START'], style='tap', px=58),
}
for v in TEXTS.values(): v['en'] = ' '.join(v['en_lines'])

WHERE = {'t_tumble': 'карточка 1, заголовок', 't_multi': 'карточка 2, заголовок', 't_bomb': 'карточка 3, заголовок',
         't_fs': 'карточка 4, заголовок', 'd_tumble': 'карточка 1, описание', 'd_multi': 'карточка 2, описание',
         'd_bomb': 'карточка 3, описание', 'd_fs': 'карточка 4, описание',
         'd_buy': 'под сундуком покупки бонуса (только деск)', 'tap_continue': 'подсказка внизу',
         't_free_spins': 'главный заголовок', 't_you_won': 'внутри золотого блюда, над счётчиком',
         'chip_multi': 'плашка с множителем x5', 'chip_fs': 'плашка со скаттером', 'tap_start': 'подсказка внизу'}

# Where each string sits. Geometry mirrors golden_caravan_screens.py:
#   slot(iw, ih) = width the EN art is drawn at in the game (design px), from the image size
#   box_w        = width a translation may use without touching other art (design px)
#   box_h        = <= 5: x EN height in the game; > 5: absolute design px
# Card: panel 408x448 (desk) / 358x420 (mob, s = 0.86); text inside the frame = pw - 2*34 - 24.
# The icon is centred in the gap between title and caption (~236 px for a ~170 px icon), so a
# title may take 1.5x its EN height (2 lines, grows down) and a caption 1.25x (grows up) — the
# icon then re-centres in what is left (>= 187 px), as the generator already does.
def _card(pw, s):
    inner = pw - 2 * 34 - 10          # the blue field inside the hieroglyph frame, less a hair
    return dict(t=lambda iw, ih: min(iw * 0.9 * s, inner), d=lambda iw, ih: min(iw * 0.85 * s, inner), inner=inner)


DESK_CARD, MOB_CARD = _card(450, 1.0), _card(372, 0.86)
FIELDS = []   # (screen, device, key, slot(iw, ih), box_w, box_h, bone in the current export)
for dev, c in (('desk', DESK_CARD), ('mob', MOB_CARD)):
    for i, k in enumerate(['tumble', 'multi', 'bomb', 'fs']):
        FIELDS.append(('feature', dev, f't_{k}', c['t'], c['inner'], 1.5, f'card{i}_t'))
        FIELDS.append(('feature', dev, f'd_{k}', c['d'], c['inner'], 1.25, f'card{i}_d'))


def _chip(cw, icon_w):
    room = cw - icon_w - 110
    return (lambda iw, ih: min(iw * 0.85, room)), room


CH = dict(desk=(_chip(760, 112 * 1.3), _chip(760, 112 * 1.45)), mob=(_chip(752, 104 * 1.3), _chip(752, 104 * 1.45)))
FIELDS += [
    # chest + "BUY BONUS / 100x BET" at (720, 196), right edge of the screen; can grow ~20% down to card 4
    ('feature', 'desk', 'd_buy', lambda iw, ih: iw * 0.9, 440, 1.2, 'buy'),
    # under the cards: desk ~1.5x EN height (cards end at y -316, edge at -470), mob room for 2 lines
    ('feature', 'desk', 'tap_continue', lambda iw, ih: 400, 1100, 1.5, 'tap'),
    ('feature', 'mob', 'tap_continue', lambda iw, ih: 400, 700, 2.1, 'tap'),
    ('bonus', 'desk', 't_free_spins', lambda iw, ih: 800, 1400, 1.18, 'title'),
    ('bonus', 'mob', 't_free_spins', lambda iw, ih: 680, 730, 1.5, 'title'),   # ~85 px free above the dish
    # inside the dish: its open part is ~0.7 of the dish width (EN uses 0.6)
    ('bonus', 'desk', 't_you_won', lambda iw, ih: 312, 372, 1.3, 'won'),
    ('bonus', 'mob', 't_you_won', lambda iw, ih: 336, 400, 1.3, 'won'),
    # chip text next to its icon on the dark band (150-160 tall, EN text ~70)
    ('bonus', 'desk', 'chip_multi', CH['desk'][0][0], CH['desk'][0][1], 1.3, 'chip0_t'),
    ('bonus', 'desk', 'chip_fs', CH['desk'][1][0], CH['desk'][1][1], 1.3, 'chip1_t'),
    ('bonus', 'mob', 'chip_multi', CH['mob'][0][0], CH['mob'][0][1], 1.3, 'chip0_t'),
    ('bonus', 'mob', 'chip_fs', CH['mob'][1][0], CH['mob'][1][1], 1.3, 'chip1_t'),
    # desk: between the band (ends at -338) and the bottom edge (-470); mob: room for 2 lines
    ('bonus', 'desk', 'tap_start', lambda iw, ih: 400, 1100, 1.5, 'tap'),
    ('bonus', 'mob', 'tap_start', lambda iw, ih: 400, 700, 2.1, 'tap'),
]

# Fields that sit side by side and must share one size: all four card titles get the smallest
# of their fixed sizes, same for the four captions (a row of cards with different text sizes
# reads as broken, however well each one fits on its own).
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('tumble', 'multi', 'bomb', 'fs')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]
GROUPS += [('bonus', dev, ['chip_multi', 'chip_fs']) for dev in ('desk', 'mob')]
