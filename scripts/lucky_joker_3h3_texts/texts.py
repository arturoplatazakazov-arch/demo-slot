# Every translatable string on the Lucky Joker (3x3 Hold & Win) preview screens
# (scripts/lucky_joker_3h3_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn ('\n' in a text = a forced break, kept in every
# language). style -> fitlib.STYLES (titles = Shantell Sans 800, the Luckiest Guy stand-in;
# captions = Nunito 900, the Baloo 2 stand-in):
#   'title' = gold title(), 'title_purple' = title() in purple (3 RESPINS, YOU HAVE WON),
#   'title_cream' = title() in cream (the tap prompts), 'caption' = cream lines().
# Not texts: the logo, the MINI/MINOR/MAJOR/GRAND jackpot plates, x2/x3/x5/x10 on the coins
# (Roboto Mono numbers), the live spin count on the plate.
TEXTS = {
    't_multi': dict(en_lines=['MULTIPLIERS'], style='title', px=60),
    't_hw':    dict(en_lines=['HOLD & WIN'], style='title', px=60),
    't_jp':    dict(en_lines=['JACKPOTS'], style='title', px=60),
    't_fs':    dict(en_lines=['FREE SPINS'], style='title', px=60),
    'd_multi': dict(en_lines=['COINS MULTIPLY', 'A WINNING LINE'], style='caption', px=40),
    'd_hw':    dict(en_lines=['JOKER COLLECTS', 'EVERY COIN'], style='caption', px=40),
    'd_jp':    dict(en_lines=['UP TO x1000', 'YOUR BET'], style='caption', px=40),
    'd_fs':    dict(en_lines=['3 SCATTERS = 10', 'ALL WINS x2'], style='caption', px=40, forced=True),
    'respins': dict(en_lines=['3 RESPINS'], style='title_purple', px=40),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='title_cream', px=58),
    't_you_won':    dict(en_lines=['YOU HAVE WON'], style='title_purple', px=64),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='title', px=150),
    'chip_x2':      dict(en_lines=['ALL WINS', 'PAY DOUBLE'], style='caption', px=40),
    'chip_fs':      dict(en_lines=['3 SCATTERS', 'GIVE +10 SPINS'], style='caption', px=40),
    'tap_start':    dict(en_lines=['TAP TO START'], style='title_cream', px=64),
}
for v in TEXTS.values(): v['en'] = ('\n' if v.get('forced') else ' ').join(v['en_lines'])

WHERE = {'t_multi': 'карточка 1, заголовок', 't_hw': 'карточка 2, заголовок', 't_jp': 'карточка 3, заголовок',
         't_fs': 'карточка 4, заголовок', 'd_multi': 'карточка 1, описание', 'd_hw': 'карточка 2, описание',
         'd_jp': 'карточка 3, описание', 'd_fs': 'карточка 4, описание (2 строки — перенос обязательный)',
         'respins': 'карточка 2, под джокером', 'tap_continue': 'подсказка внизу',
         't_you_won': 'над заголовком', 't_free_spins': 'главный заголовок', 'chip_x2': 'плашка с монетой x2',
         'chip_fs': 'плашка со скаттером', 'tap_start': 'подсказка внизу'}

# Where each string sits. Geometry mirrors lucky_joker_3h3_screens.py (design px):
#   slot(iw, ih) = width the EN art is drawn at in the game, box_w = the area a translation may
#   use, box_h = <= 5: x the EN height in the game; > 5: absolute design px.
# Cards: the velvet frame is 693 px wide, its velvet field runs x=45..648 (the gold rim with its
# bulbs is ~45 px) -> the text keeps 590 of it: max_w = 590 * cw / 693
# (cw 440 desk / 362 mob). The icon group between title and caption is scaled to the room they
# leave; a translation keeps the EN block's height, so the illustration never changes size
# between languages (titles stay one line, captions two).
# "3 RESPINS" sits under the joker inside the icon group (scale s * fit: desk 1.0 * 0.8109,
# mob 0.8 * 0.9568 in the approved export: the generator divides by the live fit, so the text
# keeps that size whatever room the icons get).
def _card(cw, tscale):
    mw = 590 * cw / 693
    return dict(t=lambda iw, ih: min(iw * tscale, mw), d=lambda iw, ih: min(iw * tscale * 0.95, mw), box=mw)


DESK_CARD, MOB_CARD = _card(440, 0.8), _card(362, 0.66)
HW_K = {'desk': 1.0 * 0.8109, 'mob': 0.8 * 0.9568}
FIELDS = []   # (screen, device, key, slot(iw, ih), box_w, box_h, bone in the current export)
for dev, c in (('desk', DESK_CARD), ('mob', MOB_CARD)):
    for i, k in enumerate(['multi', 'hw', 'jp', 'fs']):
        FIELDS.append(('feature', dev, f't_{k}', c['t'], c['box'], 1.0, f'card{i}_t'))
        FIELDS.append(('feature', dev, f'd_{k}', c['d'], c['box'], 1.0, f'card{i}_d'))
    hk = HW_K[dev]
    FIELDS.append(('feature', dev, 'respins', lambda iw, ih, hk=hk: 210 * hk, min(c['box'], 330 * hk), 1.0, 'hw_r'))
FIELDS += [
    ('feature', 'desk', 'tap_continue', lambda iw, ih: 430, 1100, 1.4, 'tap'),   # 1.4: room for accents (cards end 90 px above)
    ('feature', 'mob', 'tap_continue', lambda iw, ih: 420, 700, 2.1, 'tap'),     # room for 2 lines
    ('bonus', 'desk', 't_you_won', lambda iw, ih: 410, 900, 1.0, 'won'),
    ('bonus', 'mob', 't_you_won', lambda iw, ih: 345, 700, 1.0, 'won'),
    # the heroes (x = +-435..685) sit a good 75 px below the title band, so it may run wider
    ('bonus', 'desk', 't_free_spins', lambda iw, ih: 820, 960, 1.0, 'title'),
    ('bonus', 'mob', 't_free_spins', lambda iw, ih: 690, 730, 1.0, 'title'),   # canvas 780 less a 25 px margin
    ('bonus', 'desk', 'chip_x2', lambda iw, ih: min(iw * 0.85, 700 - 116 - 90), 700 - 116 - 90, 1.0, 'chip0_t'),
    ('bonus', 'desk', 'chip_fs', lambda iw, ih: min(iw * 0.85, 700 - 116 - 90), 700 - 116 - 90, 1.0, 'chip1_t'),
    ('bonus', 'mob', 'chip_x2', lambda iw, ih: min(iw * 0.82, 700 - 108 - 90), 700 - 108 - 90, 1.0, 'chip0_t'),
    ('bonus', 'mob', 'chip_fs', lambda iw, ih: min(iw * 0.82, 700 - 108 - 90), 700 - 108 - 90, 1.0, 'chip1_t'),
    ('bonus', 'desk', 'tap_start', lambda iw, ih: 420, 1100, 1.4, 'tap'),       # 1.4: room for accents (band ends 90 px above)
    ('bonus', 'mob', 'tap_start', lambda iw, ih: 420, 700, 2.1, 'tap'),
]

# Fields that sit side by side and must share one size: the row of card titles, the row of card
# captions, and the pair of chips on the bonus screen — each takes the group's smallest size.
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('multi', 'hw', 'jp', 'fs')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]
GROUPS += [('bonus', dev, ['chip_x2', 'chip_fs']) for dev in ('desk', 'mob')]
