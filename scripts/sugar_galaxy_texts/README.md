# Sugar Galaxy — texts for localisation

`texts.py` — every string on the preview screens (drawn by ../sugar_galaxy_screens.py) and
where it sits (EN slot width + the box a translation may use, mirroring the generator's
geometry), plus GROUPS: fields that sit side by side and share one size.
`fitlib.py` — the drawing + fit machinery (fonts, text_img/draw, line breaking, fields(),
lines_for(), block()), shared by doc.py and ../sugar_galaxy_screens.py, so a string is
measured exactly as it is drawn.
`translations.py` — az de es fr kk pl pt ru tr uk uz.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
```

Fixed sizes (product 2026-11-12: plaques and fonts never resize per language): each field gets
ONE font size at which EN and every translation fit its box; the table shows it next to the
current EN size. Fonts: Luckiest Guy and Baloo 2 have no Cyrillic, so the game now draws
these texts in Shantell Sans 800 and Nunito 900 (fonts/*.ttf, the same families
front/css/fonts.css serves to front/css/sugar-galaxy.css); glyphs even those lack fall back
to Arial Black / Arial Bold stand-ins. Same layout as ../golden_caravan_texts.
