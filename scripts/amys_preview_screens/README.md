# Amy's Fruit Farm — preview screens (Spine 4.1)

Generates `front/img/amys-fruit-farm/Screens/{feature,bonus}_screen_{desk,mob}/`
(`intro` + looping `idle`, PMA atlas + JPEG background page). Runtime:
`showPreviewScreen` in `front/js/slot.js`.

```
python3 -m venv venv && venv/bin/pip install pillow fonttools brotli numpy xlsxwriter
mkdir -p parts fonts
for p in buy_free_spins bonus_spins_win bonus_spins_total_win; do
  venv/bin/python extract.py "../../front/img/amys-fruit-farm/Popup's/$p" parts $p; done
# fonts/: luckiest-guy-latin-fe2ede07.ttf, fredoka-latin-849e3a33.ttf
#   (convert front/fonts/*.woff2 with fontTools: TTFont(f).flavor=None; save)
venv/bin/python gfx.py     # -> gfx/ (text, glows, copies of game art)
venv/bin/python build.py   # -> Screens/*
```

Layout/timing lives in `build.py` (design px, box centre origin, y up).
Run from this folder; `venv/ parts/ fonts/ gfx/` are build scratch (gitignored).

## Localisation build (no baked text)

```
venv/bin/python build.py --notext <out>/spine_notext   # txt_<slot> bones instead of text images
venv/bin/python texts_table.py <out>/spine_notext      # -> <out>/amys_fruit_farm_тексты.xlsx
```

All strings live in `texts.py` (gfx.py renders them from there). Under `--notext`
each text slot becomes a bare `txt_<slot>` bone at the text-field centre with an
empty slot of the same name (keeps the alpha timelines); the BUY BONUS sign uses
the blank sign art. The normal build is unchanged byte-for-byte.
