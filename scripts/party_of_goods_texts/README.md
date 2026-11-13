# Party Gods (party-of-goods) — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../party_of_goods_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's geometry).
`translations.py` — az de es fr kk pl pt ru tr uk uz.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Fonts: front/fonts cinzel / luckiest-guy woff2 -> fonts/*.ttf (fontTools,
flavor=None); glyphs the game fonts lack are drawn with an Arial Black stand-in.

The bonus title BONUS SPINS WIN is PSB raster art today; the table models a translation as
Luckiest Guy gold text in the same box (the theatre's curtain opening).
