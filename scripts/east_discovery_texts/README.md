# East Discovery — texts for localisation

`texts.py` — every string on the three info screens (preview / bonus / Hold & Win) and the
fixed box each one gets. It also holds LAYOUT, which `../east_discovery_screens.py` imports:
the table and the screens share one source of geometry.
`translations.py` — az de es fr kk pl pt ru tr uk uz.
`fitlib.py` — draws a string exactly as the screens do and picks the fixed size; shared by the
table and the generator, so nothing is measured twice.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
python ../east_discovery_screens.py <out> [--lang ru] [--notext]
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box — so `--lang` changes the glyphs and
the line breaks, never the layout, and `--notext` leaves a bare bone per field (plus
text_fields.json) for the engine to draw the translated string on. Every field holds at least
0.81 of its EN design size (the worst is the mob card titles, two lines in a 264 px card).

Copy follows app/seed/east_discovery.py, which the old DOM screens did not: the wild expands
AND walks right (50/50 each), 3/4/5 scatters pay 10/15/20 free spins, 3+ tigers start the
Hold & Win respins with coin values up to x100, and both bonuses cost 100x the bet.

Fonts: front/fonts luckiest-guy/fredoka woff2 -> fonts/*.ttf (fontTools, flavor=None); glyphs
the game fonts lack are drawn with Arial Black, then Arial Bold for what Arial Black also lacks
(Kazakh Ң Ө Ұ Ү, Azerbaijani Ə) — both at least as wide as the game fonts, so the fit is
conservative. Neither game font has Cyrillic at all: that still needs a font decision.
