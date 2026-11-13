# Every translatable string on the Multi Fruits Story preview screens
# (scripts/multi_fruits_story_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn. style: 'title' = Luckiest Guy (title(): gold / cream /
# lime fill, ink stroke, glow or none), 'caption' = Baloo 2 800 (lines(): cream, ink stroke).
# hard=True: the EN break is a sentence break, kept as '\n' (mandatory) in every language.
TEXTS = {
    't_line':  dict(en_lines=['3 IN A ROW'], style='title', px=60),
    't_mwild': dict(en_lines=['MULTI WILDS'], style='title', px=60),
    't_stack': dict(en_lines=['WILDS COMBINE'], style='title', px=60),
    't_fs':    dict(en_lines=['FREE SPINS'], style='title', px=60),
    'd_line':  dict(en_lines=['3 SAME SYMBOLS', 'ON A LINE WIN'], style='caption', px=38),
    'd_mwild': dict(en_lines=['WILDS LAND WITH', 'x2  x3  x5  x7'], style='caption', px=38),
    'd_stack': dict(en_lines=['WILDS ON ONE LINE', 'MULTIPLY TOGETHER'], style='caption', px=38),
    'd_fs':    dict(en_lines=['3 SCATTERS = 10 SPINS', 'ALL WINS x2'], style='caption', px=38, hard=True),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='title', px=58, fill='cream', glow='ffd23a'),
    't_you_won':    dict(en_lines=['YOU HAVE WON'], style='title', px=64, fill='lime'),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='title', px=150, glow='fff3a0'),
    'chip_x2':      dict(en_lines=['EVERY WIN IN THE', 'BONUS PAYS DOUBLE'], style='caption', px=40),
    'chip_fs':      dict(en_lines=['3 SCATTERS AGAIN', 'GIVE +10 SPINS'], style='caption', px=40),
    'tap_start':    dict(en_lines=['TAP TO START'], style='title', px=64, fill='cream', glow='ffd23a'),
}
for v in TEXTS.values():
    v.setdefault('fill', 'gold'); v.setdefault('glow', None); v.setdefault('gap', 0.22)   # межстрочный: было 0.06, строки стояли слишком тесно
    v['en'] = ('\n' if v.get('hard') else ' ').join(v['en_lines'])

# Where each string sits. Geometry mirrors multi_fruits_story_screens.py:
#   slot(iw, ih) = width the EN art is drawn at in the game (design px), from the image size
#   box_w        = the width a translation may use without touching other art (design px)
#   hk           = box height as a factor of the EN height (bh = absolute height instead)
# Cards: the description lives inside the green field (card width - 80: the gold frame eats ~48
# a side and the caption may run a hair onto the flat rail), the title sits ON the frame's top
# border, so it may run 5 px wider a side again (- 70) before it reaches the corner scrolls. Heights: the icon between them is re-centred in whatever
# the two blocks leave, so a title may take 1.35x its EN height (diacritics: Ğ İ Ё Ą, and room
# for a second line) and a description 1.5x (DE/FR run to three lines).
def _card(pw, s):
    inner, top = pw - 80, pw - 70
    return dict(t=lambda iw, ih: min(iw * 0.9 * s, top), d=lambda iw, ih: min(iw * 0.82 * s, inner),
                tbox=top, box=inner)
DESK_CARD, MOB_CARD = _card(410, 1.0), _card(350, 0.86)

def F(screen, dev, key, slot, box_w, bone, hk=1.0, bh=None):
    return dict(screen=screen, dev=dev, key=key, slot=slot, box_w=box_w, bone=bone, hk=hk, bh=bh)

FIELDS = []
for dev, c in (('desk', DESK_CARD), ('mob', MOB_CARD)):
    for i, k in enumerate(['line', 'mwild', 'stack', 'fs']):
        FIELDS.append(F('feature', dev, f't_{k}', c['t'], c['tbox'], f'card{i}_t', hk=1.35))
        FIELDS.append(F('feature', dev, f'd_{k}', c['d'], c['box'], f'card{i}_d', hk=1.75))
# chip caption: the plaque's ornate end caps are ~60 a side, then the icon and a 24 px gap
_chip = lambda cw: (lambda iw, ih: min(iw * 0.8, cw - 120 - 112 - 24))
CHIP_BOX = lambda cw: cw - 120 - 112 - 24
FIELDS += [
    # the bottom hint has the whole strip under the cards to itself: room for diacritics (1.5)
    F('feature', 'desk', 'tap_continue', lambda iw, ih: 430, 1100, 'tap', hk=1.5),
    F('feature', 'mob', 'tap_continue', lambda iw, ih: 420, 700, 'tap', hk=2.1),   # room for 2 lines
    # desk: the gem (x -465..-375) and the ruby (x 400..480) flank YOU HAVE WON;
    # mob: the leaf (x < -255) and the clover (x > 265) do. Above it the screen edge, below it
    # the FREE SPINS title: ~1.45x the EN height is free (É Ğ Ą sit above the caps).
    F('bonus', 'desk', 't_you_won', lambda iw, ih: 720 * 0.52, 740, 'won', hk=1.45),
    F('bonus', 'mob', 't_you_won', lambda iw, ih: 640 * 0.52, 500, 'won', hk=1.45),
    # desk: strawberry / lemon at |x| > 485 overlap the title's lower edge; mob: screen edge.
    # Between YOU HAVE WON and the counter plate the title may grow ~10%.
    F('bonus', 'desk', 't_free_spins', lambda iw, ih: 720, 860, 'title', hk=1.1),
    F('bonus', 'mob', 't_free_spins', lambda iw, ih: 640, 700, 'title', hk=1.12),
    # chips: the plaque is 150 tall, the caption ~70: hk 1.35
    F('bonus', 'desk', 'chip_x2', _chip(640), CHIP_BOX(640), 'chip0_t', hk=1.35),
    F('bonus', 'desk', 'chip_fs', _chip(640), CHIP_BOX(640), 'chip1_t', hk=1.35),
    F('bonus', 'mob', 'chip_x2', _chip(650), CHIP_BOX(650), 'chip0_t', hk=1.35),
    F('bonus', 'mob', 'chip_fs', _chip(650), CHIP_BOX(650), 'chip1_t', hk=1.35),
    F('bonus', 'desk', 'tap_start', lambda iw, ih: 420, 1100, 'tap', hk=1.5),
    F('bonus', 'mob', 'tap_start', lambda iw, ih: 420, 700, 'tap', hk=2.1),
]

WHERE = {'t_line': 'карточка 1, заголовок', 't_mwild': 'карточка 2, заголовок', 't_stack': 'карточка 3, заголовок',
         't_fs': 'карточка 4, заголовок', 'd_line': 'карточка 1, описание', 'd_mwild': 'карточка 2, описание',
         'd_stack': 'карточка 3, описание', 'd_fs': 'карточка 4, описание', 'tap_continue': 'подсказка внизу',
         't_you_won': 'над заголовком', 't_free_spins': 'главный заголовок',
         'chip_x2': 'плашка с вайлдом x2', 'chip_fs': 'плашка со скаттером', 'tap_start': 'подсказка внизу'}
NOT_TRANSLATED = ('Логотип MULTI FRUITS STORY, надписи на символах (WILD, множители x2/x3/x5/x7 на вайлдах) и «= x15» '
                  'в карточке 3 (только цифры) — арт, не переводятся. Число спинов на бонус-скрине — живая цифра (DOM) '
                  'поверх деревянной плашки. В d_fs перенос после «= 10 SPINS» обязательный (два предложения), '
                  'в таблице показан как « / ».')

# Fields that sit side by side and must share one size: all four card titles get the smallest
# of their fixed sizes, same for the four captions (a row of cards with different text sizes
# reads as broken, however well each one fits on its own). Same for the pair of bonus chips.
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('line', 'mwild', 'stack', 'fs')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]
GROUPS += [('bonus', dev, ['chip_x2', 'chip_fs']) for dev in ('desk', 'mob')]
