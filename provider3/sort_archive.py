"""Sort a ChatGPT download dump (files named after the image titles) into
provider3/art/<slug>/src/<job>.png using provider3/title_map.json.

    python3 provider3/sort_archive.py <folder>

Same-title duplicates: the second file of a job becomes <job>_alt. Backgrounds:
the title map can mix base/mobile when ChatGPT reused a title, so the aspect
decides: portrait = mobile.
"""
import json, re, shutil, sys, unicodedata
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
JOBS = {'1': 'logo', '2': 'symbols_hp', '3': 'symbols_lp', '4': 'characters', '5': 'frame', '5b': 'frame_parts',
        '6': 'bg_base', '7': 'bg_bonus', '8': 'bg_base_mob', '9': 'bg_bonus_mob', '10': 'ui_kit'}
m = json.loads((HERE / 'title_map.json').read_text())
norm = lambda s: re.sub(r'\s+', ' ', re.sub(r'\s*\(\d+\)$', '', unicodedata.normalize('NFC', s))).strip()
mm = {norm(k): v for k, v in m.items()}
seen, miss = {}, []
for f in sorted(Path(sys.argv[1]).iterdir()):
    if f.suffix.lower() not in ('.png', '.jpg', '.webp'):
        continue
    key = mm.get(norm(f.stem))
    if not key:
        miss.append(f.name)
        continue
    slug, j = key.split('|')
    job = JOBS[j]
    if job.startswith('bg_'):
        w, h = Image.open(f).size
        mob = h > w
        bonus = 'bonus' in job
        job = 'bg_' + ('bonus' if bonus else 'base') + ('_mob' if mob else '')
    dst = HERE / 'art' / slug / 'src'
    dst.mkdir(parents=True, exist_ok=True)
    name = job
    n = seen.get((slug, job), 0)
    if n:
        name = f'{job}_alt{n}'
    seen[(slug, job)] = n + 1
    shutil.copy2(f, dst / f'{name}{f.suffix.lower()}')
print('sorted', sum(seen.values()), 'unmatched', len(miss))
for x in miss:
    print('  ?', x)
