# Lucky Joker (3x3 Hold & Win) — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../lucky_joker_3h3_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's geometry).
`translations.py` — az de es fr kk pl pt ru tr uk uz.
`fitlib.py` — the drawing + fit code shared with the generator: `fields()` (one record per field,
its box and its one fixed size), `lines_for()` (how a string breaks there), `block()` (the image).

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
../amys_preview_screens/venv/bin/python ../lucky_joker_3h3_screens.py <fonts> <out> [--lang ru] [--notext]
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Fields that stand side by side (the row of card titles, the row of card
captions, the two bonus chips) share the group's smallest size — see `GROUPS` in texts.py.

Fonts: the game's own Luckiest Guy / Baloo 2 have no Cyrillic, so the localised build draws
titles in **Shantell Sans 800** and captions in **Nunito 900** (`fonts/*.ttf`, the same subsets
front/css/fonts.css serves; front/css/lucky-joker-3h3.css names them first). Arial Black / Arial
Bold stay in `FAM` as a stand-in for any glyph even those lack.
Boxes are the EN block's own size, so titles stay one line and captions two in every language and
the card illustration never changes size between languages. `'\n'` in a text = a forced break (d_fs).
