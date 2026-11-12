# Glyph coverage of the game fonts per language (used by texts_table.py).
import os
from fontTools.ttLib import TTFont
from texts import TEXTS
from translations import TR, plain
S = os.path.dirname(os.path.abspath(__file__))
FONTS = {'Luckiest Guy': ['luckiest-guy-latin-fe2ede07', 'luckiest-guy-latin-ext-36d626a4'],
         'Fredoka 650': ['fredoka-latin-849e3a33', 'fredoka-latin-ext-20489dbf']}
CMAP = {fam: set().union(*(TTFont(os.path.join(S, f'../../front/fonts/{n}.woff2')).getBestCmap() for n in files))
        for fam, files in FONTS.items()}

def coverage(lang):
    """{font family: missing characters (sorted string)} over every string drawn in that family."""
    out = {}
    for fam in FONTS:
        chars = set(''.join(plain(TR[lang][k]) for k, v in TEXTS.items() if v['font'] == fam)) - set('  ')
        out[fam] = ''.join(sorted(c for c in chars if ord(c) not in CMAP[fam]))
    return out
