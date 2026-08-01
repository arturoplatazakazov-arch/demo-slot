Win-line animations — first trial (Wild Western Story only). If it looks
good we'll reuse the same set on the other 5x3 games (East Discovery, Neon
Reels, Amy's Fruit Farm — they all share this game's exact 20 payline
shapes, confirmed against the DB).

## What's here

One Spine skeleton, not 11 separate exports — `animation.atlas` /
`animation.json` / `animation.png`, same convention as every other
animated asset in this game (see `../Export/wild/`). It carries 11 named
animations internally: `"1"` through `"11"`.

## Mapping to paylines

The backend defines 20 paylines for this game (Payline.index 1-20, each a
5-cell row-position pattern — see `app/seed/wild_western_story.py` / the
`payline_index` field on `LineWin`). The 11 animations here are the ones
actually live for the client, but which of the 20 indices each of "1".."11"
corresponds to isn't confirmed yet — the skeleton's own animation names
("1".."11") are just a sequence, not payline indices.

Payline shapes (index: row per reel, 0=top row, 1=middle, 2=bottom):
```
 1: 1 1 1 1 1        11: 2 1 1 1 2
 2: 0 0 0 0 0        12: 1 0 1 0 1
 3: 2 2 2 2 2        13: 1 2 1 2 1
 4: 0 1 2 1 0        14: 0 1 0 1 0
 5: 2 1 0 1 2        15: 2 1 2 1 2
 6: 0 0 1 0 0        16: 0 2 0 2 0
 7: 2 2 1 2 2        17: 2 0 2 0 2
 8: 1 0 0 0 1        18: 1 1 0 1 1
 9: 1 2 2 2 1        19: 1 1 2 1 1
10: 0 1 1 1 0        20: 0 2 2 2 0
```
