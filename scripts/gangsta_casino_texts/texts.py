# Every translatable string on the Gangsta Casino preview screens.
# The game loads its screens from the optimised designer pack by default
# (front/js/gangsta-casino/slot.js: PACK = img/gangsta-casino/spine-pack unless ?pack=old):
# spine-pack/feature_screen + spine-pack/bonus_screen, one skeleton each with skins desk / mob.
# In the pack the captions are NOT baked: they are DOM text (.pack-caption, Luckiest Guy,
# css/gangsta-casino.css) pinned every frame to the empty text_<key> bones
# (spine-pack/feature_screen/text_marks.json, PACK_CAPTIONS in slot.js). The old designer
# exports spine/feature_screen_v2{,_mob} / bonus_screen_v4{,_mob} (only with ?pack=old) have
# the same copy baked as atlas regions t_freespins / t_wild / t_wheel ("BONUS WHEEL") /
# t_continue / t_bonus / t_start in a condensed bold sans the repo has no file of.
# Not texts: the logo, the neon "Free spins" sign on the jukebox (fs_machine art), WILD /
# SCATTER printed on the symbol art, the multiplier values, the live spin digits.
SUP = '/System/Library/Fonts/Supplemental/'
# Luckiest Guy -> Shantell Sans 800 (2026-11-13): the original has no Cyrillic; this subset
# carries all 12 client languages and is what the page loads from front/fonts.
FAM = {'caption': ('Shantell Sans 800', 'shantell-sans', 800, SUP + 'Arial Black.ttf', ((255, 243, 200), (40, 20, 0)))}

TEXTS = {
    'free_spins': dict(en='FREE SPINS', style='caption', where='лента панели 1 (скаттер)'),
    'expanding_wild': dict(en='EXPANDING WILD', style='caption', where='лента панели 2 (вайлд)'),
    'multiplier': dict(en='MULTIPLIER', style='caption', where='лента панели 3 (множитель)'),
    # The seed: in free spins every landed multiplier adds to a round multiplier kept to the
# end of the round; in the base game they only sum on screen. The old copy said only
# "accumulated in bonus game", which read as if they did nothing in the base game.
    'multiplier_note': dict(en='ADD UP IN FREE SPINS', style='caption', where='панель 3, строка под MULTIPLIER'),
    'tap_to_continue': dict(en='TAP TO CONTINUE', style='caption', where='подсказка внизу'),
    'bonus_game': dict(en='BONUS GAME', style='caption', where='лента над автоматом'),
    'tap_to_start': dict(en='TAP TO START', style='caption', where='подсказка внизу'),
}

# PACK_CAPTIONS (slot.js): [bone, text, box w, box h, lines, line] in text-bone units; the
# caption's font = line (default box h) * 0.62. ws = the text bone's world scale in the setup
# pose (bone chain of the pack skeleton) -> everything below is in design px of the PSB
# canvas (desk 1932x940, mob 780x1416), 1 unit = 1 design px at the root.
def _fit_en(en, w, h, lines, line, ws):
    """EN size exactly as fitCaption() gets it: the box's font if one line fits, else
    one line scaled to the width (lines < 2), else wrap + shrink by 0.94 until it fits."""
    def f(width, wrap):
        W, H, f0 = w * ws, h * ws, line * 0.62 * ws
        if width(en, 'caption', f0) <= W + 0.5: return f0
        if lines < 2: return f0 * W / width(en, 'caption', f0)
        k = 1.0
        while k > 0.3:
            ls = wrap(en, 'caption', f0 * k, W, 0, False)
            if max(width(l, 'caption', f0 * k) for l in ls) <= W + 0.5 and len(ls) * 1.02 * f0 * k <= H + 0.5: break
            k *= 0.94
        return f0 * k
    return f

def C(screen, dev, key, bone, w, h, lines, ws, line=None):
    line = line or h
    fit = lines > 0
    return dict(screen=screen, dev=dev, key=key, el=bone, box_w=w * ws, box_h=h * ws,
                lines=max(1, lines) if fit else 1, nowrap=lines < 2,
                lh=1.02 if fit else 1.08,               # .pack-caption--fit line-height 1.02; plain: 1 + 0.08em padding
                en_px=_fit_en(TEXTS[key]['en'], w, h, lines, line, ws) if fit else (lambda W_, w_, f0=line * 0.62 * ws: f0))

FIELDS = [
    C('feature', 'desk', 'free_spins', 'text_free_spins', 240, 66, 2, 1.1385),
    C('feature', 'desk', 'expanding_wild', 'text_expanding_wild', 279, 66, 2, 1.1382),
    C('feature', 'desk', 'multiplier', 'text_multiplier', 240, 42, 1, 1.1385),
    C('feature', 'desk', 'multiplier_note', 'text_multiplier_note', 273, 27, 1, 1.0),
    C('feature', 'desk', 'tap_to_continue', 'text_tap_to_continue', 400, 116, 2, 1.3, line=58),
    C('feature', 'mob', 'free_spins', 'm_text_free_spins', 240, 74, 2, 0.8123),
    C('feature', 'mob', 'expanding_wild', 'm_text_expanding_wild', 279, 86, 2, 0.6989),
    C('feature', 'mob', 'multiplier', 'm_text_multiplier', 240, 47, 1, 0.8123),
    C('feature', 'mob', 'multiplier_note', 'm_text_multiplier_note', 244, 27, 1, 0.8),
    C('feature', 'mob', 'tap_to_continue', 'm_text_tap_to_continue', 400, 116, 2, 1.1, line=58),
    # bonus screen: one list for both layouts, no fitting (lines = 0: nowrap at h * 0.62)
    C('bonus', 'desk', 'bonus_game', 'text_bonus_game', 266, 71, 0, 0.95),
    # TAP TO START has no ribbon: its PACK_CAPTIONS box (211 = the old baked region) is just the
    # EN width; the real free room under the BONUS GAME ribbon is ~600 design px on desk (machine
    # plinth / the woman's chair at x = +-340) and ~700 on mob (canvas 780, the woman starts below).
    C('bonus', 'desk', 'tap_to_start', 'text_tap_to_start', 600 / 1.3, 58, 0, 1.3),
    C('bonus', 'mob', 'bonus_game', 'm_text_bonus_game', 266, 71, 0, 0.95),
    C('bonus', 'mob', 'tap_to_start', 'm_text_tap_to_start', 700 / 1.3, 58, 0, 1.3),
]

META = dict(
    xlsx='gangsta_casino_тексты.xlsx', hdr='#3A1250', tile_bg=(30, 16, 44), sheet_bg=(12, 6, 20),
    screens={'feature': 'Фича-скрин', 'bonus': 'Бонус-скрин'},
    font_use={'caption': 'все подписи экранов'},
    notes=[
        'Размер шрифта фиксирован и одинаков для всех языков («Кегль, px (фикс.)»): подобран так, что EN и все переводы из этой таблицы влезают в поле ленты. Зелёный — влезает (наведи на ячейку — разбивка по строкам), красный — не влезает.',
        'Подписи в игре — DOM-текст поверх костей text_* Spine-пака (spine-pack/feature_screen, bonus_screen; поля — text_marks.json / PACK_CAPTIONS в slot.js), шрифт Luckiest Guy. Сейчас fitCaption() сам уменьшает шрифт под каждый текст — по продуктовому правилу кегль надо зафиксировать значением из этой таблицы (в slot.js: множитель 0.62 → кегль/линия поля).',
        'Поле и кегль — в дизайн-px холста PSB (деск 1932×940, моб 780×1416) = поле кости × мировой масштаб кости в setup-позе. «Элемент/кость» — кость в пакете.',
        '«Кегль EN сейчас» — как EN рисуется сейчас (повтор алгоритма fitCaption). Бонус-скрин подписи не подгоняет (nowrap, кегль = высота поля × 0.62) — длинный перевод сейчас вылез бы за ленту.',
        'Шрифт Luckiest Guy не содержит кириллицу — см. лист «Шрифты». Для RU/UK/KK вёрстка проверена на более широком замещающем шрифте (Arial Black).',
        'Не переводятся: логотип GANGSTA CASINO, неоновая надпись «Free spins» на автомате (нарисована в арте fs_machine — для локализации нужен арт без надписи), WILD / SCATTER на символах, значения множителя, цифры спинов.',
        'Старый дизайнерский экспорт (spine/feature_screen_v2, bonus_screen_v4; только ?pack=old) — тексты запечены в атласе другим шрифтом (узкий жирный гротеск, файла в репозитории нет), на третьей панели там «BONUS WHEEL» от колеса, которого в игре больше нет.',
        'Поле TAP TO START на бонус-скрине взято шире, чем в PACK_CAPTIONS (211 — ширина самой EN-надписи): под лентой BONUS GAME свободно ~600 px (деск) / ~700 px (моб) — при сборке поле в slot.js надо расширить до этих значений.',
        'WILD, SCATTER в латинских языках — термины слотов.'],
    fonts_note='Проверено по файлам шрифта игры (front/fonts: latin + latin-ext подмножества Luckiest Guy).',
    fields_note='Поля — text_marks.json / PACK_CAPTIONS (front/js/gangsta-casino/slot.js) × мировой масштаб кости text_* в setup-позе (spine-pack/*/animation.json).',
)
