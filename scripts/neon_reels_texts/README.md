# Neon Reels — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../neon_reels_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's geometry).
`translations.py` — az de es fr kk pl pt ru tr uk uz.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Font: front/fonts luckiest-guy woff2 -> fonts/*.ttf (fontTools, flavor=None);
glyphs Luckiest Guy lacks (Cyrillic, Ə, ʻ ...) are drawn with an Arial Black stand-in.
Text is rendered with the generator's own text_img (glyph-bbox advance, 0.32 em space, slant).

The bonus title FREE SPINS is a PSB raster pair today (t_free gold + t_spins cyan); the table
models a translation as Luckiest Guy text in that look (last word cyan).
EN copy note: «WILD — SUBSTITUTES ALL», but in app/seed/neon_reels.py the wild only stands in
for regular symbols (not scatter / coin).
