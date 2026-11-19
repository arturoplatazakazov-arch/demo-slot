"""Index every audio file under front/sound/ into front/sound/library.json.

The dev sound panel (front/js/dev-tools.js) reads it to offer ANY sound in the
repo as an extra variant for an event ("из библиотеки"). Re-run after adding
or generating sounds:  python3 scripts/sound_library.py
"""
import json
from pathlib import Path

FRONT = Path(__file__).resolve().parent.parent / "front"
ROOT = FRONT / "sound"
EXT = {".mp3", ".wav", ".ogg", ".opus", ".m4a"}

files = sorted(
    p.relative_to(FRONT).as_posix()
    for p in ROOT.rglob("*")
    if p.suffix.lower() in EXT and not p.relative_to(ROOT).parts[0].startswith("zz-")
)
(ROOT / "library.json").write_text(json.dumps(files, ensure_ascii=False, indent=0) + "\n")
print(f"{len(files)} files -> {ROOT / 'library.json'}")
