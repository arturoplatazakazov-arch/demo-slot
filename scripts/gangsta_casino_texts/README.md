# Gangsta Casino — texts for localisation

The game shows the screens from the optimised pack (img/gangsta-casino/spine-pack/feature_screen,
bonus_screen; ?pack=old = the designer's baked exports). In the pack the captions are DOM text
(.pack-caption, Luckiest Guy) pinned to the text_* bones; boxes = PACK_CAPTIONS in
js/gangsta-casino/slot.js / text_marks.json x the bone's world scale. `texts.py` holds them,
`translations.py` — az de es fr kk pl pt ru tr uk uz.

```
../amys_preview_screens/venv/bin/python doc.py <out dir>   # xlsx + проверка_языков/<lang>.jpg + fit.json
```

doc.py is the same as ../east_discovery_texts/doc.py (DOM text: greedy wrap, one fixed size per
field). EN sizes repeat slot.js fitCaption(). Fonts: front/fonts luckiest-guy woff2 -> fonts/*.ttf;
missing glyphs measured with Arial Black.
