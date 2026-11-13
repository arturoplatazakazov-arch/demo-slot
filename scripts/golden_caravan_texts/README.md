# Golden Caravan — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../golden_caravan_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's geometry).
`translations.py` — az de es fr kk pl pt ru tr uk uz.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Font: front/fonts cinzel woff2 -> fonts/*.ttf (fontTools, flavor=None);
glyphs Cinzel lacks (Cyrillic, Ə, ʻ ...) are drawn with an Arial Black stand-in.
Card titles may go to 2 lines (1.5x EN height) and captions to 1.25x: the generator centres
the icon in the gap between them, so it re-centres.
