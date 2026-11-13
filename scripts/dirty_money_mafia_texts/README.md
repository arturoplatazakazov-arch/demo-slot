# Dirty Money / MAFIA — texts for localisation

`texts.py` — every string on the preview screens and the box it may use (the geometry is the
generator's: ../dirty_money_mafia_screens.py reads these same records).
`translations.py` — az de es fr kk pl pt ru tr uk uz.
`fitlib.py` — draws a string exactly as the screens do and picks the fixed size; shared by the
table and the generator, so nothing is measured twice.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
python ../dirty_money_mafia_screens.py <out> [--lang ru] [--notext]
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box — so `--lang` changes the glyphs and
the line breaks, never the layout, and `--notext` leaves a bare bone per field (plus
text_fields.json) for the engine to draw the translated string on. The boxes in texts.py were
widened (and the chip plaques with them, 660/680 -> 760/740) until every field held at >= 0.90
of its EN design size.

Fonts: front/fonts cinzel/baloo-2 woff2 -> fonts/*.ttf (fontTools, flavor=None); glyphs the game
fonts lack are drawn with Arial Black, then Arial Bold for what Arial Black also lacks (Kazakh
Ң Ө Ұ Ү, Azerbaijani Ə) — both at least as wide as the game fonts, so the fit is conservative.
