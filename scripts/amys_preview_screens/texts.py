# Every translatable string on the preview screens, keyed by its gfx/ image name.
# gfx.py renders these; build.py --notext replaces each with a txt_<key> bone.
# hi = words drawn in gold (keep the same meaning highlighted in a translation).
TEXTS = {
    'sign_buy': dict(en='BUY\nBONUS', font='Luckiest Guy', hi=[]),
    't_fs': dict(en='FREE SPINS', font='Luckiest Guy', hi=[]),
    't_buy': dict(en='BUY BONUS', font='Luckiest Guy', hi=[]),
    'd_fs_desk': dict(en='3, 4 or 5 SCATTERS award\n10, 15 or 20 FREE SPINS.\nScatters retrigger the bonus!', font='Fredoka 650', hi=['SCATTERS', 'FREE', 'SPINS.', '10,', '15', '20']),
    'd_buy_desk': dict(en='Skip the wait: buy\nFREE SPINS straight away\nfor 100x your bet', font='Fredoka 650', hi=['FREE', 'SPINS', '100x']),
    'd_fs_mob': dict(en='3, 4 or 5 SCATTERS award\n10, 15 or 20 FREE SPINS.\nScatters retrigger!', font='Fredoka 650', hi=['SCATTERS', 'FREE', 'SPINS.', '10,', '15', '20']),
    'd_buy_mob': dict(en='Buy FREE SPINS straight\naway for 100x your bet', font='Fredoka 650', hi=['FREE', 'SPINS', '100x']),
    'cont_desk': dict(en='CLICK ANYWHERE TO CONTINUE', font='Luckiest Guy', hi=[]),
    'cont_mob': dict(en='TAP ANYWHERE\nTO CONTINUE', font='Luckiest Guy', hi=[]),
    'start_desk': dict(en='CLICK ANYWHERE TO START', font='Luckiest Guy', hi=[]),
    'start_mob': dict(en='TAP ANYWHERE\nTO START', font='Luckiest Guy', hi=[]),
    't_congrats': dict(en='CONGRATULATIONS!', font='Luckiest Guy', hi=[]),
    't_youwon': dict(en='YOU WON', font='Luckiest Guy', hi=[]),
    't_freespins': dict(en='FREE SPINS', font='Luckiest Guy', hi=[]),
    'b_fs': dict(en='3+ SCATTERS = MORE SPINS', font='Fredoka 650', hi=['SCATTERS']),
}
