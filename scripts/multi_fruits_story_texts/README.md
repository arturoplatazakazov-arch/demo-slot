# Multi Fruits Story — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../multi_fruits_story_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's geometry),
plus `GROUPS`: fields that stand side by side (a row of card titles, a row of card captions, the
pair of bonus chips) and therefore share ONE size — the smallest in the row.
`translations.py` — az de es fr kk pl pt ru tr uk uz.
`fitlib.py` — the drawing + fitting itself (`fields()`, `lines_for()`, `block()`), shared with
the screens generator, so a string is measured exactly as it is drawn.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
python ../multi_fruits_story_screens.py <fonts_dir> [out] [--lang ru] [--notext]
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Fonts: the game's own Luckiest Guy / Baloo 2 have no Cyrillic, so the screens
(and the game's CSS) use the central replacements — Shantell Sans 800 for Luckiest Guy and
Nunito 900 for Baloo 2 (`fonts/*.ttf` here, `front/fonts/*.woff2` in the game); Arial Black /
Arial Bold stay as stand-ins for any glyph those subsets might still miss.
Same layout as ../golden_caravan_texts / ../dirty_money_mafia_texts.
