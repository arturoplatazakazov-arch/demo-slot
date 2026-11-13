# Every translatable string on the Dirty Money / MAFIA preview screens
# (scripts/dirty_money_mafia_screens.py draws them). One text per key for desk and mob.
# en_lines = the EN line breaks as drawn. style: 'title' = Cinzel 900 (gold or cream),
# 'caption' = Baloo 2 800 cream.
TEXTS = {
    't_wild':  dict(en_lines=['EXPANDING', 'WILD'], style='title', px=50),
    't_fs':    dict(en_lines=['FREE', 'SPINS'], style='title', px=50),
    't_wheel': dict(en_lines=['WHEEL OF', 'FORTUNE'], style='title', px=50),
    't_buy':   dict(en_lines=['BUY', 'BONUS'], style='title', px=50),
    'd_wild':  dict(en_lines=['WILD GROWS TO', 'FILL THE REEL'], style='caption', px=34),
    'd_fs':    dict(en_lines=['3 / 4 / 5 SCATTERS', '= 10 / 15 / 20 SPINS'], style='caption', px=34),
    'd_wheel': dict(en_lines=['3 WHEEL SYMBOLS:', 'x2 - x8 OR FREE SPINS'], style='caption', px=34),
    'd_buy':   dict(en_lines=['FREE SPINS ROUND', 'FOR 100x BET'], style='caption', px=34),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='title', px=54, cream=True),
    't_you_won':    dict(en_lines=['YOU HAVE WON'], style='title', px=56, cream=True),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='title', px=140),
    'chip_wild':    dict(en_lines=['WILDS EXPAND', 'ON ANY REEL'], style='caption', px=36),
    'chip_fs':      dict(en_lines=['3+ SCATTERS', 'ADD MORE SPINS'], style='caption', px=36),
    'tap_start':    dict(en_lines=['TAP TO START'], style='title', px=60, cream=True),
}
for v in TEXTS.values(): v['en'] = ' '.join(v['en_lines'])

# Where each string sits. Geometry mirrors dirty_money_mafia_screens.py:
#   slot  = width the EN art is drawn at in the game (design px)
#   box   = the area a translation may use without touching other art (design px)
# Card titles/descriptions keep their EN height (the icon fills the rest of the card).
# box_h_factor > 1: the field is taller than the EN art, so a language with accents above the
# caps (TR Ş Ğ, AZ Ə, PL Ą) keeps the size instead of paying for its own diacritics.
# Plaques/panels: the chip plaques were widened (660/680 -> 760/740) when the fixed sizes went
# in, so the chip captions keep a readable size in every language.
CHIP = {'desk': (760, 96), 'mob': (740, 104)}       # plaque width, icon width (see screens.py)
def _chip(dev):
    pw, iw_ = CHIP[dev]
    return pw - iw_ - 150
def _card(pw, s):
    return dict(t=lambda iw: min(iw * 0.8 * s, pw - 70), tbox=pw - 70,
                d=lambda iw: min(iw * 0.8 * s, pw - 60), dbox=pw - 60)
DESK_CARD, MOB_CARD = _card(404, 1.0), _card(356, 0.86)
FIELDS = []   # (screen, device, key, slot_w(img_w), box_w, box_h_factor, bone in the current export)
for dev, c in (('desk', DESK_CARD), ('mob', MOB_CARD)):
    for i, k in enumerate(['wild', 'fs', 'wheel', 'buy']):
        FIELDS.append(('feature', dev, f't_{k}', c['t'], c['tbox'], 1.14, f'card{i}_t'))
        FIELDS.append(('feature', dev, f'd_{k}', c['d'], c['dbox'], 1.2, f'card{i}_d'))
FIELDS += [
    ('feature', 'desk', 'tap_continue', lambda iw: 420, 1400, 1.3, 'tap'),
    ('feature', 'mob', 'tap_continue', lambda iw: 440, 700, 2.1, 'tap'),     # room for 2 lines
    ('bonus', 'desk', 't_you_won', lambda iw: 410, 1200, 1.2, 'won'),
    ('bonus', 'mob', 't_you_won', lambda iw: 350, 700, 1.2, 'won'),
    ('bonus', 'desk', 't_free_spins', lambda iw: 820, 1340, 1.1, 'title'),
    ('bonus', 'mob', 't_free_spins', lambda iw: 700, 730, 1.9, 'title'),     # room for 2 lines
    ('bonus', 'desk', 'chip_wild', lambda iw: min(iw * 0.78, _chip('desk')), _chip('desk'), 1.15, 'chip0_t'),
    ('bonus', 'desk', 'chip_fs', lambda iw: min(iw * 0.78, _chip('desk')), _chip('desk'), 1.15, 'chip1_t'),
    ('bonus', 'mob', 'chip_wild', lambda iw: min(iw * 0.95, _chip('mob')), _chip('mob'), 1.15, 'chip0_t'),
    ('bonus', 'mob', 'chip_fs', lambda iw: min(iw * 0.95, _chip('mob')), _chip('mob'), 1.15, 'chip1_t'),
    ('bonus', 'desk', 'tap_start', lambda iw: 400, 1400, 1.3, 'tap'),
    ('bonus', 'mob', 'tap_start', lambda iw: 420, 700, 2.1, 'tap'),
]
