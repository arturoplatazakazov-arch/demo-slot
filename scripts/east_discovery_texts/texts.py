# Every translatable string on the East Discovery info screens, and the fixed box each one
# gets on the design canvas. The screens are Spine skeletons built by
# ../east_discovery_screens.py (feature / bonus / hold&win x desk 1932x940, mob 780x1416);
# this module is the single source of the text geometry — the generator imports LAYOUT and
# FIELDS from here, so the table and the screens can never drift apart.
#
# Not texts: Logo_east.png, the WILD/SCATTER lettering baked into the symbol art, and the live
# spin count drawn on the lantern (bone `count`).
#
# style: 'title' = Luckiest Guy gold, 'tap' = Luckiest Guy cream, 'desc' = Fredoka 600 cream.
# px = the EN design size on DESKTOP; a field's `s` scales it per device (mob text is larger
# relative to its narrower canvas, exactly as the CSS vw sizes were).
TEXTS = {
    't_wild': dict(en_lines=['EXPANDING WILD'], style='title', px=30),
    't_fs':   dict(en_lines=['FREE SPINS'], style='title', px=30),
    't_hw':   dict(en_lines=['HOLD & WIN'], style='title', px=30),
    't_buy':  dict(en_lines=['BUY BONUS'], style='title', px=30),
    'd_wild': dict(en_lines=['Wild expands and', 'walks to the right'], style='desc', px=17),
    'd_fs':   dict(en_lines=['3 / 4 / 5 Scatters =', '10 / 15 / 20 free spins'], style='desc', px=17),
    'd_hw':   dict(en_lines=['3+ Tigers start respins,', 'coins pay up to x100'], style='desc', px=17),
    'd_buy':  dict(en_lines=['Free spins or Hold & Win', 'for 100x bet'], style='desc', px=17),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='tap', px=36),
    'tap_start':    dict(en_lines=['TAP TO START'], style='tap', px=36),
    'b_title':  dict(en_lines=['BONUS GAME'], style='title', px=89),
    'b_sub':    dict(en_lines=['FREE SPINS'], style='title', px=61),
    'hw_title': dict(en_lines=['HOLD & WIN'], style='title', px=89),
    'hw_sub':   dict(en_lines=['COLLECT THE COINS'], style='title', px=45),
}
for v in TEXTS.values():
    v['en'] = ' '.join(v['en_lines'])

# --- layout shared with ../east_discovery_screens.py --------------------------------------
# Card: panel size, the inset of the text column, and where the two text boxes sit inside the
# panel (y = distance from the panel's bottom edge to the box's bottom edge, design px).
LAYOUT = {
    'desk': dict(canvas=(1932, 940), card=(404, 470), cards_y=-78, cards_x=(-666, 444),
                 t_box=(334, 50), d_box=(344, 66), d_y=70, t_y=150, logo=(0, 330, 520),
                 tap_y=-398, tap_box=(1400, 120)),
    'mob': dict(canvas=(780, 1416), card=(356, 450), cards_y=None, cards_x=None,
                t_box=(264, 84), d_box=(270, 100), d_y=34, t_y=128, logo=(0, 548, 500),
                tap_y=-600, tap_box=(700, 150)),
}
MOB_CARDS = [(-188, 236), (188, 236), (-188, -236), (188, -236)]
CARD_KEYS = ['wild', 'fs', 'hw', 'buy']
# Device scale of a text field: the EN design px / TEXTS[key]['px'].
S = {'desk': dict(title=1.0, desc=1.0, tap=1.0),
     'mob': dict(title=1.34, desc=1.53, tap=1.28)}

FIELDS = []   # (screen, device, key, EN scale, box_w, box_h, max lines, bone)
for dev in ('desk', 'mob'):
    L = LAYOUT[dev]
    for i, k in enumerate(CARD_KEYS):
        FIELDS.append(('feature', dev, f't_{k}', S[dev]['title'], *L['t_box'], 1 if dev == 'desk' else 2, f'card{i}_t'))
        FIELDS.append(('feature', dev, f'd_{k}', S[dev]['desc'], *L['d_box'], 2 if dev == 'desk' else 3, f'card{i}_d'))
    FIELDS.append(('feature', dev, 'tap_continue', S[dev]['tap'], *L['tap_box'], 2, 'tap'))
    FIELDS.append(('bonus', dev, 'tap_start', S[dev]['tap'], *L['tap_box'], 2, 'tap'))
    FIELDS.append(('holdwin', dev, 'tap_start', S[dev]['tap'], *L['tap_box'], 2, 'tap'))
FIELDS += [
    # Bonus screen: title over the lantern, sub under it. The lantern (with the live spin
    # count) sits between them, so neither box may grow into the other.
    ('bonus', 'desk', 'b_title', 1.0, 1340, 140, 1, 'title'),
    ('bonus', 'desk', 'b_sub', 1.0, 1100, 96, 1, 'sub'),
    ('bonus', 'mob', 'b_title', 0.97, 720, 150, 2, 'title'),
    ('bonus', 'mob', 'b_sub', 1.02, 700, 104, 1, 'sub'),
    ('holdwin', 'desk', 'hw_title', 1.0, 1340, 140, 1, 'title'),
    ('holdwin', 'desk', 'hw_sub', 1.0, 1100, 80, 1, 'sub'),
    ('holdwin', 'mob', 'hw_title', 0.97, 720, 150, 2, 'title'),
    ('holdwin', 'mob', 'hw_sub', 1.04, 700, 88, 2, 'sub'),
]
