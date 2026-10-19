"""Savannah Kings: the art pieces that never made it out of ChatGPT,
generated with the same model (gpt-image-1.5, via fal.ai) and the ChatGPT
sources as style references (front/img/savannah-kings/src/, gitignored).
Writes src/<job>.png for scripts/savannah_kings_art.py to cut.

    .venv/bin/python scripts/savannah_kings_gen.py job [job ...]
"""

import base64
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'front/img/savannah-kings/src'
KEY_FILE = Path('/Users/arturkasian/demo_slot/.env')

STYLE = (
    'Same art direction as the reference slot mockup: painterly but precise premium slot art, '
    'African savannah at sunset, warm stone and restrained gold, one consistent low sun rim light '
    'from the left, controlled palette, no plastic look, no random sparkles, no extra text.'
)

JOBS = {
    'wild_big': {
        'size': '1024x1536', 'background': 'transparent', 'refs': ['specials', 'mockup'],
        'prompt': 'The WILD lion from reference image 1 as a full-body figure for a whole slot reel: a '
                  'majestic male lion sitting proudly on a small rock ledge, seen from the front, head '
                  'high and mouth open in a roar, golden-amber mane, filling the tall frame from top to '
                  'bottom. Fully transparent background, no frame, no medallion, no text. ' + STYLE,
    },
    'bg_base': {
        'size': '1536x1024', 'background': 'opaque', 'refs': ['mockup'],
        'prompt': 'The background of this slot mockup WITHOUT the slot machine, without UI, without '
                  'logo, without any text: African savannah one hour before sunset, sky orange-gold at '
                  'the horizon to deep wine at the top, long thin clouds, low sun on the left behind '
                  'distant blue-violet mountains, acacia silhouettes at the left and right edges, dry '
                  'golden grass and warm rocks in the foreground. The centre stays calm and empty, '
                  'horizon at about 60% height. No animals, no people. ' + STYLE,
    },
    'bg_base_mob': {
        'size': '1024x1536', 'background': 'opaque', 'refs': ['@bg_base'],
        'prompt': 'Portrait version of this exact background for phones: same style, palette, sun, '
                  'mountains and grass, recomposed vertically — big sky with clouds in the upper half, '
                  'the sun low behind the mountains, one acacia on the side, golden grass at the bottom. '
                  'Centre calm and empty. No text, no UI, no animals.',
    },
    'bg_bonus': {
        'size': '1536x1024', 'background': 'opaque', 'refs': ['@bg_base'],
        'prompt': 'The exact same landscape composition at NIGHT: deep indigo-blue sky with stars and a '
                  'big pale moon instead of the sun, mountains as dark blue silhouettes, acacias black '
                  'against the sky, the grass lit by a small warm campfire glow at the bottom left, a few '
                  'fireflies. Same framing, centre calm and empty. No text, no UI, no animals.',
    },
    'bg_bonus_mob': {
        'size': '1024x1536', 'background': 'opaque', 'refs': ['@bg_bonus'],
        'prompt': 'Portrait version of this exact night background for phones: indigo starry sky, big '
                  'moon, dark mountains, an acacia silhouette, warm campfire glow at the bottom. Same '
                  'style and palette. No text, no UI, no animals.',
    },
    'frame': {
        'size': '1536x1024', 'background': 'transparent', 'refs': ['mockup', 'jackpots'],
        'prompt': 'Only the REEL FRAME of the slot in reference image 1, as a standalone asset: carved '
                  'warm sandstone with thin restrained gold trim (gold like reference image 2) around a '
                  'rectangular window for 5 columns x 3 rows of square cells, window proportion 5:3. '
                  'The window must be completely EMPTY and TRANSPARENT, everything outside the frame '
                  'transparent too. Thin walls (about 7% of the window height), decoration only in the '
                  'four corners and a small lion-head crest at the top centre, tufts of dry golden grass '
                  'at the bottom corners. No text, no reels, no symbols. ' + STYLE,
    },
    'logo': {
        'size': '1536x1024', 'background': 'transparent', 'refs': ['cover', 'titles_more'],
        'prompt': 'The game logo "SAVANNAH KINGS" exactly in the style of the logo in reference image 1 '
                  '(carved gold lettering on a stone plate with a golden lion head crest on top and red '
                  'gems), as a standalone asset on a fully transparent background. Two lines: '
                  '"SAVANNAH" big, "KINGS" below it. Exact spelling SAVANNAH KINGS. Nothing else — no '
                  'lion body, no landscape, no plaques.',
    },
    'panel': {
        'size': '1536x1024', 'background': 'transparent', 'refs': ['titles_more', 'jackpots'],
        'prompt': 'A wide ornate PANEL for showing numbers in popups, in exactly the same style, gold '
                  'and gems as the title plates in reference image 1: a horizontal carved gold-and-stone '
                  'cartouche, proportion about 3.5:1, with a large recessed EMPTY dark brown centre panel '
                  '(like the value panels in reference image 2), red gems at both ends and at top and '
                  'bottom centre. Fully transparent background, no text, no numbers.',
    },
}


def _key() -> str:
    if os.environ.get('FAL_KEY'):
        return os.environ['FAL_KEY']
    for line in KEY_FILE.read_text().splitlines():
        if line.startswith('FAL_KEY='):
            return line.split('=', 1)[1].strip().strip('"')
    raise SystemExit('FAL_KEY missing')


def _src(name: str) -> Path:
    name = name.lstrip('@')
    for ext in ('png', 'webp'):
        p = SRC / f'{name}.{ext}'
        if p.exists():
            return p
    raise FileNotFoundError(name)


def _data_uri(path: Path, max_side: int = 1280) -> str:
    im = Image.open(path)
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    if im.mode == 'RGBA':
        im.save(buf, 'PNG')
        mime = 'image/png'
    else:
        im.convert('RGB').save(buf, 'JPEG', quality=90)
        mime = 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(buf.getvalue()).decode()


def run(name: str) -> str:
    job = JOBS[name]
    body = {
        'prompt': job['prompt'], 'image_size': job['size'], 'background': job['background'],
        'quality': 'high', 'output_format': 'png', 'num_images': 1,
        'image_urls': [_data_uri(_src(r)) for r in job['refs']], 'input_fidelity': 'high',
    }
    req = urllib.request.Request(
        'https://fal.run/fal-ai/gpt-image-1.5/edit', data=json.dumps(body).encode(),
        headers={'Authorization': f'Key {_key()}', 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        url = json.load(resp)['images'][0]['url']
    out = SRC / f'{name}.png'
    if url.startswith('data:'):
        out.write_bytes(base64.b64decode(url.split(',', 1)[1]))
    else:
        urllib.request.urlretrieve(url, out)
    return f'{name}: {out.name} {Image.open(out).size}'


def _safe(name):
    try:
        return run(name)
    except Exception as e:  # keep the other jobs going
        return f'{name}: FAILED {e}'


if __name__ == '__main__':
    names = sys.argv[1:] or list(JOBS)
    # Jobs that reference another job's output run after it.
    first = [n for n in names if not any(r.startswith('@') for r in JOBS[n]['refs'])]
    later = [n for n in names if n not in first]
    for wave in (first, [n for n in later if JOBS[n]['refs'] == ['@bg_base']], [n for n in later if JOBS[n]['refs'] != ['@bg_base']]):
        if not wave:
            continue
        with ThreadPoolExecutor(len(wave)) as pool:
            for name, res in zip(wave, pool.map(lambda n: _safe(n), wave)):
                print(res, flush=True)

