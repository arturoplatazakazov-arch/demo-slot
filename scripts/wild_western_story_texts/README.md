# Wild Western Story — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../wild_western_story_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's geometry).
`translations.py` — az de es fr kk pl pt ru tr uk uz.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
```

`fitlib.py` — the drawing + fit machinery (fonts, line breaking, one fixed size per field),
shared with ../wild_western_story_screens.py so a string is measured exactly as it is drawn.
`fields()`, `lines_for(key, lang, rec)`, `block(key, lang, rec)` are its public API.

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Fields that sit side by side (the three card titles, the three descriptions)
share the smallest size of their row — see GROUPS in texts.py.

Fonts: the game's Rye / Luckiest Guy have no Cyrillic (and the shipped rye latin-ext subset is
27 glyphs, so PL/TR/AZ already fell back), so the localised build swaps them for
**Bitter 900** (titles) and **Shantell Sans 800** (body) — fonts/bitter-latin-900.ttf and
fonts/shantell-sans-latin-800.ttf, the same subsets front/css/fonts.css declares for the web
and front/css/wild-western-story.css now puts first. Arial Black stays as a stand-in safety net.

One string per field for desk and mob (only the line breaks differ), so the prompts read
"TAP TO ..." on both.
Same layout as ../golden_caravan_texts (fitlib + doc.py split, GROUPS).
