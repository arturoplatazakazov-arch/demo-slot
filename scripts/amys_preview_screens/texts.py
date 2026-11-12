# Every translatable string on the preview screens: ONE text per key for desk and mob
# (product 2026-11-12: the copy must match across devices; only line breaks may differ).
# `img` maps each gfx/ image to the line-broken form it is drawn with; without `img`
# the image is named after the key and drawn from `en` as is.
# gfx.py renders these; build.py --notext replaces each with a txt_<slot> bone.
# hi = words drawn in gold (keep the same meaning highlighted in a translation).
TEXTS = {
    'sign_buy': dict(en='BUY BONUS', font='Luckiest Guy', hi=[], img={'sign_buy': 'BUY\nBONUS'}),
    't_fs': dict(en='FREE SPINS', font='Luckiest Guy', hi=[]),
    't_buy': dict(en='BUY BONUS', font='Luckiest Guy', hi=[]),
    'd_fs': dict(en='3, 4 or 5 SCATTERS award 10, 15 or 20 FREE SPINS. Scatters retrigger the bonus!',
                 font='Fredoka 650', hi=['SCATTERS', 'FREE', 'SPINS.', '10,', '15', '20'],
                 img={'d_fs_desk': '3, 4 or 5 SCATTERS award\n10, 15 or 20 FREE SPINS.\nScatters retrigger the bonus!',
                      'd_fs_mob': '3, 4 or 5 SCATTERS award\n10, 15 or 20 FREE SPINS.\nScatters retrigger the bonus!'}),
    'd_buy': dict(en='Skip the wait: buy FREE SPINS straight away for 100x your bet',
                  font='Fredoka 650', hi=['FREE', 'SPINS', '100x'],
                  img={'d_buy_desk': 'Skip the wait: buy\nFREE SPINS straight away\nfor 100x your bet',
                       'd_buy_mob': 'Skip the wait: buy\nFREE SPINS straight away\nfor 100x your bet'}),
    'cont': dict(en='PRESS ANYWHERE TO CONTINUE', font='Luckiest Guy', hi=[],
                 img={'cont_desk': 'PRESS ANYWHERE TO CONTINUE', 'cont_mob': 'PRESS ANYWHERE\nTO CONTINUE'}),
    'start': dict(en='PRESS ANYWHERE TO START', font='Luckiest Guy', hi=[],
                  img={'start_desk': 'PRESS ANYWHERE TO START', 'start_mob': 'PRESS ANYWHERE\nTO START'}),
    't_congrats': dict(en='CONGRATULATIONS!', font='Luckiest Guy', hi=[]),
    't_youwon': dict(en='YOU WON', font='Luckiest Guy', hi=[]),
    't_freespins': dict(en='FREE SPINS', font='Luckiest Guy', hi=[]),
    'b_fs': dict(en='3+ SCATTERS = MORE SPINS', font='Fredoka 650', hi=['SCATTERS']),
}

# image name -> (key, string as drawn)
IMAGES = {}
for _k, _v in TEXTS.items():
    for _img, _s in _v.get('img', {_k: _v['en']}).items():
        assert ' '.join(_s.split('\n')) == _v['en'], (_img, 'copy differs from en')
        IMAGES[_img] = (_k, _s)
