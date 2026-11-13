# Every translatable string on the Sugar Galaxy preview screens
# (scripts/sugar_galaxy_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn. style: 'title' = Luckiest Guy (title(): gold, white
# or pink fill, purple stroke + glow), 'caption' = Baloo 2 800 (lines(): white, purple stroke).
# fill / glow = the generator's arguments; gap = lines() line gap.
TEXTS = {
    't_tumble': dict(en_lines=['TUMBLE WINS'], style='title', px=60),
    't_multi':  dict(en_lines=['MULTIPLIERS'], style='title', px=60),
    't_bomb':   dict(en_lines=['BOMBS'], style='title', px=60),
    't_fs':     dict(en_lines=['FREE SPINS'], style='title', px=60),
    'd_tumble': dict(en_lines=['8+ SAME SYMBOLS', 'ANYWHERE WIN'], style='caption', px=40),
    'd_multi':  dict(en_lines=['x2 x3 x5 x7 ADD UP', 'ON EVERY CASCADE'], style='caption', px=40),
    'd_bomb':   dict(en_lines=['BLAST THEIR WHOLE', 'ROW AND COLUMN'], style='caption', px=40),
    'd_fs':     dict(en_lines=['3+ SCATTERS', 'AWARD 7 SPINS'], style='caption', px=40),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='title', px=58, fill='white', glow='b44dff'),
    't_you_won':    dict(en_lines=['YOU HAVE WON'], style='title', px=64, fill='pink', glow='7a2bff'),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='title', px=150),
    'chip_multi':   dict(en_lines=['MULTIPLIERS STACK', 'FOR THE WHOLE ROUND'], style='caption', px=40),
    'chip_fs':      dict(en_lines=['3+ SCATTERS', 'GIVE +7 SPINS'], style='caption', px=40),
    'tap_start':    dict(en_lines=['TAP TO START'], style='title', px=64, fill='white', glow='b44dff'),
}
for v in TEXTS.values():
    v.setdefault('fill', 'gold'); v.setdefault('glow', 'ff3fd0'); v.setdefault('gap', 0.08)
    v['en'] = ' '.join(v['en_lines'])

# Where each string sits. Geometry mirrors sugar_galaxy_screens.py:
#   slot(iw, ih) = width the EN art is drawn at in the game (design px), from the image size
#   box_w        = the width a translation may use without touching other art (design px)
#   hk           = box height as a factor of the EN height (bh = absolute height instead)
# Cards were widened for the localisation pass (desk 400 -> 440, mob 352 -> 372, text inset
# 20/18 -> 14 px): the row of titles and the row of captions each take ONE size (GROUPS), and
# at the old width the whole row was dragged down by the longest word (FR MULTIPLICATEUR) and
# by the longest caption (ES). The title box hangs from the card's top and the caption box
# stands on its bottom (hk 1.45 / 1.5 = room for a 2-line title and a 3-line caption); the
# illustration re-centres in whatever is left between them, as the generator does.
PANEL = {'desk': (440, 450), 'mob': (372, 420)}      # card panel W x H, mirrored by the generator


def _card(pw, s):
    inner = pw - 28
    return dict(t=lambda iw, ih: min(iw * 0.92 * s, inner), tbox=inner,
                d=lambda iw, ih: min(iw * 0.8 * s, inner), dbox=inner)
DESK_CARD, MOB_CARD = _card(PANEL['desk'][0], 1.0), _card(PANEL['mob'][0], 0.86)

def F(screen, dev, key, slot, box_w, bone, hk=1.0, bh=None):
    return dict(screen=screen, dev=dev, key=key, slot=slot, box_w=box_w, bone=bone, hk=hk, bh=bh)

# chip width, icon width, padding -> (slot, box) for the caption next to the icon
CHIP_W = {'desk': (760, 120, 60), 'mob': (720, 112, 60)}
CHIP = {d: ((lambda iw, ih, r=cw - icon - pad: min(iw * 0.85, r)), cw - icon - pad)
        for d, (cw, icon, pad) in CHIP_W.items()}

FIELDS = []
for dev, c in (('desk', DESK_CARD), ('mob', MOB_CARD)):
    for i, k in enumerate(['tumble', 'multi', 'bomb', 'fs']):
        FIELDS.append(F('feature', dev, f't_{k}', c['t'], c['tbox'], f'card{i}_t', hk=1.45))
        FIELDS.append(F('feature', dev, f'd_{k}', c['d'], c['dbox'], f'card{i}_d', hk=1.5))
FIELDS += [
    F('feature', 'desk', 'tap_continue', lambda iw, ih: 430, 1100, 'tap', hk=1.35),
    F('feature', 'mob', 'tap_continue', lambda iw, ih: 420, 700, 'tap', hk=2.1),   # room for 2 lines
    # desk: the planet (x < -525) and the crystal (x > 695) flank the titles
    F('bonus', 'desk', 't_you_won', lambda iw, ih: 430, 960, 'won', hk=1.35),
    F('bonus', 'mob', 't_you_won', lambda iw, ih: 350, 420, 'won', hk=1.35),      # planet at x < -210
    # desk: plate right under it, one line; the title's own glow may reach the planet's rim.
    # mob: ~80 px free between the title and the plate, ~0 to YOU HAVE WON: 2 lines fit at hk 1.7
    F('bonus', 'desk', 't_free_spins', lambda iw, ih: 860, 1040, 'title', hk=1.2),
    F('bonus', 'mob', 't_free_spins', lambda iw, ih: 700, 740, 'title', hk=1.7),
    # info chips: text width = min(iw * 0.85, chip width - icon - gap). Widened for the
    # localisation pass: the desk pair sits on one 1560-wide band (room to 780 per half) and
    # the padding around the text was 90 px of nothing.
    F('bonus', 'desk', 'chip_multi', CHIP['desk'][0], CHIP['desk'][1], 'chip0_t', hk=1.35),
    F('bonus', 'desk', 'chip_fs', CHIP['desk'][0], CHIP['desk'][1], 'chip1_t', hk=1.35),
    F('bonus', 'mob', 'chip_multi', CHIP['mob'][0], CHIP['mob'][1], 'chip0_t', hk=1.35),
    F('bonus', 'mob', 'chip_fs', CHIP['mob'][0], CHIP['mob'][1], 'chip1_t', hk=1.35),
    F('bonus', 'desk', 'tap_start', lambda iw, ih: 420, 1100, 'tap', hk=1.35),
    F('bonus', 'mob', 'tap_start', lambda iw, ih: 420, 700, 'tap', hk=2.1),
]

# Shown in the table (Где) and the notes.
WHERE = {'t_tumble': 'карточка 1, заголовок', 't_multi': 'карточка 2, заголовок', 't_bomb': 'карточка 3, заголовок',
         't_fs': 'карточка 4, заголовок', 'd_tumble': 'карточка 1, описание', 'd_multi': 'карточка 2, описание',
         'd_bomb': 'карточка 3, описание', 'd_fs': 'карточка 4, описание', 'tap_continue': 'подсказка внизу',
         't_you_won': 'над заголовком', 't_free_spins': 'главный заголовок',
         'chip_multi': 'плашка с множителем x5', 'chip_fs': 'плашка со скаттером', 'tap_start': 'подсказка внизу'}
NOT_TRANSLATED = ('Логотип SUGAR GALAXY и токены x2/x3/x5/x7 — арт, не переводятся. Число спинов на бонус-скрине — '
                  'живая цифра (DOM) поверх плашки-счётчика.')

# Fields that sit side by side and must share one size: all four card titles get the smallest
# of their fixed sizes, same for the four captions and for the pair of bonus chips (a row of
# cards with different text sizes reads as broken, however well each one fits on its own).
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('tumble', 'multi', 'bomb', 'fs')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]
GROUPS += [('bonus', dev, ['chip_multi', 'chip_fs']) for dev in ('desk', 'mob')]
