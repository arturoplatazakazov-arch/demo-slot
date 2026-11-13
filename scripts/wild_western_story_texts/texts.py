# Every translatable string on the Wild Western Story preview screens
# (scripts/wild_western_story_screens.py draws them). One text per key: the same string runs on
# desk and mob, only the line breaks differ (product rule — desk and mob never carry different
# wording), so the prompts are device-neutral ("TAP TO ...") instead of CLICK/TAP pairs.
# en_lines = the EN line breaks as drawn. style: 'title' = Bitter 900 (gold, carved highlight,
# glow — replaces Rye), 'body' = Shantell Sans 800 (cream — replaces Luckiest Guy).
# glow / glow_r = text_img() arguments.
TEXTS = {
    't_wild': dict(en_lines=['EXPANDING WILD'], style='title', px=88, glow='ff8a2a', glow_r=9),
    't_fs':   dict(en_lines=['FREE SPINS'], style='title', px=88, glow='ff8a2a', glow_r=9),
    't_buy':  dict(en_lines=['BUY BONUS'], style='title', px=88, glow='ff8a2a', glow_r=9),
    # the wild expands only half the time and may also walk one reel right (app/seed/
    # wild_western_story.py: expand_chance 0.5, walk_chance 0.5) — the old copy promised a
    # full reel every time
    'd_wild': dict(en_lines=['WILD CAN EXPAND', 'AND WALK RIGHT'], style='body', px=56),
    'd_fs':   dict(en_lines=['3+ SCATTERS AWARD', 'UP TO 20 FREE SPINS'], style='body', px=56),
    'd_buy':  dict(en_lines=['INSTANT FREE SPINS', 'FOR 100X BET'], style='body', px=56),
    'tap_continue': dict(en_lines=['TAP TO CONTINUE'], style='body', px=72, glow='ff9a3c', glow_r=10),
    't_you_won':    dict(en_lines=['YOU HAVE WON'], style='body', px=72, glow='ff8a2a', glow_r=10),
    't_free_spins': dict(en_lines=['FREE SPINS'], style='title', px=120, glow='ff7a1a', glow_r=14),
    'tap_start':    dict(en_lines=['TAP TO START'], style='body', px=72, glow='ff9a3c', glow_r=10),
}
for v in TEXTS.values():
    v.setdefault('glow', None); v.setdefault('glow_r', None)
    v['en'] = ' '.join(v['en_lines'])

# Where each string sits. Geometry mirrors wild_western_story_screens.py, where text slots are
# sized by HEIGHT (text_slot(h=..., maxw=...): w = min(maxw, h * iw / ih)):
#   slot(iw, ih) = width the EN art is drawn at in the game (design px)
#   box_w        = the width a translation may use without touching other art (design px)
#   bh           = box height (design px); hk = factor of the EN height when bh is None
def F(screen, dev, key, slot, box_w, bone, hk=1.0, bh=None, max_lines=None):
    return dict(screen=screen, dev=dev, key=key, slot=slot, box_w=box_w, bone=bone, hk=hk, bh=bh,
                max_lines=max_lines)

def by_h(h, maxw=None):
    return lambda iw, ih: min(maxw, h * iw / ih) if maxw else h * iw / ih

# Cards (log panels): title h 44/42, desc h 27*2.3 / 25*2.3. The title box was widened to the
# dark field inside the logs (desk 377, mob 400 — the card art sits left of the mob text, so the
# box grows to the panel's right edge) and the description box with it: the fixed size is shared
# across the row, so the longest title (RU «РАСТУЩИЙ ВАЙЛД») sets it for all three cards.
# Titles sit right under the top log and the description on the bottom log (mob) / ~35 px under
# the art (desk): boxes keep the generator's slot height, titles get a little more room.
FIELDS = []
for dev, (th, dh, mw, dh_box) in (('desk', (44, 27 * 2.3, 332, 27 * 2.3 * 1.5)),
                                  ('mob', (42, 25 * 2.3, 370, 25 * 2.3 * 1.3))):
    for i, k in enumerate(['wild', 'fs', 'buy']):
        FIELDS.append(F('feature', dev, f't_{k}', by_h(th, mw), mw, f'title{i}', bh=th * 1.25, max_lines=2))
        FIELDS.append(F('feature', dev, f'd_{k}', by_h(dh, mw), mw, f'desc{i}', bh=dh_box, max_lines=3))
FIELDS += [
    # desk: between the corner cacti; mob: cacti at |x| > 229 reach above the hint -> 440 wide,
    # 2 lines fit above the bottom edge
    F('feature', 'desk', 'tap_continue', by_h(48), 1100, 'tap_b', bh=48 * 1.7),
    F('feature', 'mob', 'tap_continue', by_h(48), 440, 'tap_b', bh=48 * 2.1),
    # wolf tile (x > 440) and the hero wild (x < -470) flank YOU HAVE WON on desk
    F('bonus', 'desk', 't_you_won', by_h(56), 840, 'won_b', bh=56 * 2),
    F('bonus', 'mob', 't_you_won', by_h(54), 700, 'won_b', bh=54 * 2),
    # FREE SPINS: desk between the plaque (bottom -156) and the hint (top -376), gun tile at x > 390;
    # mob between the plaque (bottom 71) and the wild/wolf (top -156)
    F('bonus', 'desk', 't_free_spins', by_h(100, 720), 720, 'title_b', bh=150),
    F('bonus', 'mob', 't_free_spins', by_h(100, 680), 680, 'title_b', bh=140),
    F('bonus', 'desk', 'tap_start', by_h(48), 1100, 'tap_b', bh=48 * 1.7),
    # mob: the hero wild's foot is at y -595, the hint at -640: up to ~1.8 lines
    F('bonus', 'mob', 'tap_start', by_h(48), 700, 'tap_b', bh=48 * 1.8),
]

# Fields that sit side by side and must share one size: the three card titles get the smallest
# of their fixed sizes, same for the three descriptions (a row of cards with different text
# sizes reads as broken, however well each one fits on its own).
GROUPS = [('feature', dev, [f'{p}_{k}' for k in ('wild', 'fs', 'buy')])
          for dev in ('desk', 'mob') for p in ('t', 'd')]

WHERE = {'t_wild': 'карточка 1, заголовок', 't_fs': 'карточка 2, заголовок', 't_buy': 'карточка 3, заголовок',
         'd_wild': 'карточка 1, описание', 'd_fs': 'карточка 2, описание', 'd_buy': 'карточка 3, описание',
         'tap_continue': 'подсказка внизу', 't_you_won': 'над плашкой-счётчиком',
         't_free_spins': 'главный заголовок под плашкой', 'tap_start': 'подсказка внизу'}
NOT_TRANSLATED = ('Логотип WILD WESTERN STORY и надписи на символах (WILD, SCATTER) — арт, не переводятся. '
                  'С таблички-указателя в карточке 3 (img/Buy-bonus-button.png) впечатанная надпись Buy Bonus '
                  'стёрта — текст идёт заголовком карточки. Число спинов на бонус-скрине — живая цифра (DOM) '
                  'поверх деревянной плашки. Подсказка внизу — одна строка для деска и мобилки.')
