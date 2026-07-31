# Wild expand/walk assets — drop files here

New art/animation for the expanding + walking wild feature. Same Spine export
convention as the existing `../Wild/` folder — drop these 4 files:

- `static.png`
- `animation.png`
- `animation.json`
- `animation.atlas`

If it's easier for the animator to add new clip names (e.g. `expand`,
`walk_loop`, `walk_exit`) directly into the existing `Wild` skeleton instead
of a separate one, that's fine too — just overwrite the files in `../Wild/`
directly and skip this folder.

## Sound

Sounds are split into shared vs per-game folders now — see
`front/sound/README.md`. Repeating SFX live once in `front/sound/common/`;
theme-specific wild SFX go in that game's folder, e.g. drop
`WILD_Expand.mp3` / `WILD_WalkStep.mp3` into `front/sound/<game>/` and wire
the key in `front/js/<game>/sound.js`.

## Status

Backend support for this feature (grid mutation, `session.state` tracking,
`/spin` response's new `wild_events` field) is implemented. Frontend
animation wiring in `front/js/slot.js` is a follow-up once the assets above
land — it needs the actual clip/atlas names to hook up.
