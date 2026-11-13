# Every translatable string on the Neon Reels preview screens
# (scripts/neon_reels_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn. style -> doc.STYLES (all Luckiest Guy, the script's
# own text_img): 'cap' = gold on the card ribbon, 'sub' = cyan line under the icon,
# 'tap' = white with cyan glow, 'fs_art' = the bonus title, today a PSB raster pair
# (t_free gold + t_spins cyan) — a translation has to be drawn as text in that look.
TEXTS = {
    't_fs':   dict(en_lines=['FREE SPINS'], style='cap', px=80),
    't_wild': dict(en_lines=['WILD'], style='cap', px=80),
    't_coin': dict(en_lines=['COIN MULTIPLIER'], style='cap', px=80),
    'd_fs':   dict(en_lines=['3+ SCATTERS'], style='sub', px=64),
    'd_wild': dict(en_lines=['SUBSTITUTES SYMBOLS'], style='sub', px=64),   # not the scatter or the coin
    'd_coin': dict(en_lines=['UP TO x100'], style='sub', px=64),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='tap', px=72),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='fs_art', px=120),
    'tap_start':    dict(en_lines=['TAP TO START'], style='tap', px=72),
}
for v in TEXTS.values(): v['en'] = ' '.join(v['en_lines'])

WHERE = {'t_fs': 'карточка 1, лента', 't_wild': 'карточка 2, лента', 't_coin': 'карточка 3, лента',
         'd_fs': 'карточка 1, под иконкой', 'd_wild': 'карточка 2, под иконкой', 'd_coin': 'карточка 3, под иконкой',
         'tap_continue': 'подсказка внизу', 't_free_spins': 'заголовок над драконом (сейчас арт PSB: FREE + SPINS)',
         'tap_start': 'подсказка внизу'}

# Where each string sits. Geometry mirrors neon_reels_screens.py:
#   slot(iw, ih) = width the EN art is drawn at in the game (design px), from the image size
#   box_w        = width a translation may use without touching other art (design px)
#   box_h        = <= 5: x EN height in the game; > 5: absolute design px
# Card (desk / mob): panel 300x310 / 236x255, ribbon 340x68 / 252x56 at y -170 / -142,
# caption = min(0.8 ribbon, 44 / 32 px tall); sub-line 38 / 28 px tall, <= 0.86 panel wide,
# room between the icon bottom and the ribbon top ~56 px. Ribbon text box = flat part of the
# ribbon (0.8 w) x ribbon height - 14 (accents may use the ribbon's 12 px margins).
def _cap(rw, ch, rh): return (lambda iw, ih: min(rw * 0.8, ch * iw / ih)), rw * 0.8, rh - 14
def _sub(pw, sh): return (lambda iw, ih: min(pw * 0.86, sh * iw / ih)), pw * 0.86, 56


# Ribbons and panels widened with the fixed sizes (the row had ~900 px of free screen on
# desk): ribbon 340->440 / 252->258, panel 300->370 / 236->244 — see neon_reels_screens.py.
CARD = dict(desk=(_cap(440, 44, 68), _sub(370, 38)), mob=(_cap(258, 32, 56), _sub(244, 28)))
FIELDS = []   # (screen, device, key, slot(iw, ih), box_w, box_h, bone in the current export)
for dev, (cap, sub) in CARD.items():
    for i, k in enumerate(['fs', 'wild', 'coin']):
        FIELDS.append(('feature', dev, f't_{k}', cap[0], cap[1], cap[2], f'rib{i} (слот cap{i})'))
        FIELDS.append(('feature', dev, f'd_{k}', sub[0], sub[1], sub[2], f'sub{i}'))
FIELDS += [
    # desk: between geisha (x < -454) and samurai (x > 371) at the tap's height (alpha of the layers),
    # room up to the ribbons; mob over the characters
    ('feature', 'desk', 'tap_continue', lambda iw, ih: 430, 700, 2.0, 'tap_b'),
    ('feature', 'mob', 'tap_continue', lambda iw, ih: 470, 700, 1.6, 'tap_b'),
    # FREE (-148, w 250) + SPINS (150, w 300): EN spans 573 / 502; characters sit lower, so the
    # title row is free to ~1000 / 720 wide; height = the EN art's (114 / 103: logo above, plaque below)
    ('bonus', 'desk', 't_free_spins', lambda iw, ih: 573, 1340, 124, 'title_b'),
    ('bonus', 'mob', 't_free_spins', lambda iw, ih: 502, 740, 112, 'title_b'),
    # desk: just under the counter plate (-341) and above the edge, between samurai (x < -388)
    # and geisha (x > 513)
    ('bonus', 'desk', 'tap_start', lambda iw, ih: 380, 740, 1.0, 'tap_b'),
    ('bonus', 'mob', 'tap_start', lambda iw, ih: 380, 700, 1.6, 'tap_b'),
]

# Fields that sit side by side and must share one size: the three card ribbons, and the three
# lines under the icons (a row of cards set at different sizes reads as broken).
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('fs', 'wild', 'coin')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]
