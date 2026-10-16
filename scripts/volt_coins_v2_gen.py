"""Volt Coins v2 art: generate every layer with gpt-image-1.5 (via fal.ai).

Client feedback (hybrid of 6 AI concepts): layout/UI from F, glossy symbols from
D/B, muted vault door from C layer 8, Tesla coils from D (OFF in idle). Each
job below is one generation; later jobs pass the approved symbol sheet back as a
style reference so the whole pack stays in one rendering style.

    python scripts/volt_coins_v2_gen.py JOB [JOB ...]   # see JOBS
    python scripts/volt_coins_v2_gen.py --list

Raw outputs land in OUT_DIR/<job>.png (cutting/cleanup: volt_coins_v2_cut.py).
Needs FAL_KEY in .env.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(os.environ.get("VC2_OUT", ROOT / "front/img/volt-coins-v2/src"))
REF_DIR = Path(os.environ.get("VC2_REFS", OUT_DIR / "refs"))

STYLE = (
    "Premium casino slot game art, glossy semi-3D rendering: smooth bevelled "
    "volumes, crisp specular highlights, clean dark outlines, soft rim light, "
    "no grain, no text artifacts. Palette from the game design doc: deep indigo "
    "night blue, gold, electric cyan. Reads well on a phone."
)

SYMBOL_SPEC = """\
Nine slot symbols, laid out on a 3 by 3 grid with generous empty space between
them, each symbol centred in its own cell, fully separate, nothing touching or
overlapping, no cell borders, no labels, transparent background, no shadow on
the ground.
Row 1: WILD, COIN, DIAMOND.
Row 2: SEVEN, INGOT, BELL.
Row 3: BAR, STAR, HORSESHOE.

WILD: a bold capital letter "W" built from jagged lightning bolts, electric
white-cyan core with a thin gold bevel trim, crackling at the tips. NO circle,
NO disc, NO coin shape behind it.
COIN: the ONLY round symbol. Thick glossy rich gold coin seen straight on,
raised lightning-bolt emblem in the middle, outer rim wrapped in a bright blue
electric ring with small sparks. The most saturated gold in the whole set.
DIAMOND: large brilliant-cut gem, cyan / aqua, faceted, sparkling.
SEVEN: classic slot "7", glossy candy red with a gold edge, italic, chunky.
INGOT: rectangular gold bar (trapezoid bullion ingot, NOT a Chinese boat
ingot), pale warm gold, a lightning bolt stamped into the top face.
BELL: classic slot bell, warm copper-amber metal (not yellow gold), clapper.
BAR: TRIPLE BAR - three stacked rounded plates each reading "BAR", brushed
blue steel with white letters.
STAR: five-pointed star in magenta-violet neon glass, simpler and flatter.
HORSESHOE: polished silver horseshoe, nail holes, simpler and flatter.

Hierarchy: the four high symbols (seven, diamond, ingot, bell) and the specials
(wild, coin) are larger and more detailed; the low symbols (bar, star,
horseshoe) are slightly smaller, flatter and simpler. Only the coin is round.
Avoid making everything gold - the board must not look monochrome.
"""

COIN_STATES_SPEC = """\
Four variants of the SAME glossy gold COIN from the reference sheet, in one row,
evenly spaced, nothing touching, transparent background, no labels:
1) the coin with its centre emblem removed: a smooth, slightly recessed dark
   indigo-blue enamel face filling about 60% of the coin, for a number to be
   printed on later; keep the gold body and the blue electric rim;
2) same blank-face coin but the outer rim and glow are BRONZE / copper;
3) same blank-face coin but the outer rim and glow are bright SILVER-white;
4) same blank-face coin but the outer rim is rich GOLD with a strong gold glow.
Same angle, size and rendering for all four.
"""

JOBS: dict[str, dict] = {
    "symbols": {
        "size": "1536x1024",
        "background": "transparent",
        "refs": ["D_6.png", "B_4.png", "F_9.png"],
        "prompt": (
            "Use the reference concept screens ONLY as a style guide for the "
            "glossy symbol rendering (images 1 and 2) and for the triple BAR and "
            "the lightning-W wild (image 3). Do not copy their layout. "
            + STYLE + "\n\n" + SYMBOL_SPEC
        ),
    },
    "coin_states": {
        "size": "1536x1024",
        "background": "transparent",
        "refs": ["@symbols"],
        "prompt": "Reference: the approved symbol sheet; keep its exact rendering style. "
        + STYLE + "\n\n" + COIN_STATES_SPEC,
    },
    "bg_desk": {
        "size": "1536x1024",
        "background": "opaque",
        "refs": ["F_9.png", "C_8.png", "@symbols"],
        "prompt": (
            "Background plate for a slot game, landscape. A calm dark indigo "
            "vault tunnel in a clean, simplified style (like reference image 1), "
            "receding to a big ROUND VAULT DOOR centred behind where the reels "
            "will sit (door shape from reference image 2 but much simpler, fewer "
            "bolts, darker and matte, low contrast). The whole image at about "
            "35% brightness of the symbols in reference 3: strong vignette, "
            "slight depth blur, only a few thin cyan accent lights in the walls. "
            "NO reels, NO frame, NO symbols, NO logo, NO text, NO jackpot plates, "
            "NO Tesla coils, NO coins, NO bright light beams from top or bottom. "
            "Flat even lighting so it can be recoloured; the centre is empty "
            "dark space for the reels. " + STYLE
        ),
    },
    "bg_mob": {
        "size": "1024x1536",
        "background": "opaque",
        "refs": ["@bg_desk"],
        "prompt": (
            "Portrait version of the reference background: same dark indigo "
            "vault tunnel and the same simplified round vault door, door centred "
            "a little above the middle. Same muted 35% brightness, vignette, "
            "no reels, no frame, no text, no coils, no coins, no light beams. "
            + STYLE
        ),
    },
    "coil": {
        "size": "1024x1536",
        "background": "transparent",
        "refs": ["D_6.png", "@symbols"],
        "prompt": (
            "One single Tesla coil tower as a standalone game object, front "
            "view, centred, transparent background. Shape like the coils in "
            "reference image 1 (stacked torus rings on a copper-wound column, "
            "heavy dark-steel base) but switched OFF: no lightning, no glow, no "
            "sparks, the copper and steel only lit by soft ambient rim light, "
            "dark-indigo metal with gold trims and unlit glass rings. Same glossy "
            "rendering as reference 2. Nothing else in the image. " + STYLE
        ),
    },
    "frame": {
        "size": "1536x1024",
        "background": "transparent",
        "refs": ["F_9.png", "@symbols"],
        "prompt": (
            "A THIN slot reel frame for a 3x3 grid, front view, centred, "
            "transparent background, the whole inner window FULLY TRANSPARENT "
            "(empty, no cells, no symbols, no grid lines). Frame profile like "
            "reference image 1: slim dark gunmetal bevel with small gold corner "
            "brackets and a thin cyan inner light line, but thinner. Window "
            "aspect about 1.25:1 (slightly wider than tall). No text, no "
            "numbers, no line indicators, no jackpot plates. Same glossy "
            "rendering as reference 2. " + STYLE
        ),
    },
    "logo": {
        "size": "1536x1024",
        "background": "transparent",
        "refs": ["F_9.png", "@symbols"],
        "prompt": (
            "Game logo reading exactly \"VOLT COINS\" on two lines: \"VOLT\" "
            "above, \"COINS\" below, centred. The letter O in VOLT is replaced by "
            "a glowing electric-blue lightning bolt (like reference image 1). "
            "Chunky bevelled glossy gold letters with a dark outline and a thin "
            "electric cyan edge light, same rendering as the symbols in "
            "reference 2. Transparent background, nothing else in the image. "
            + STYLE
        ),
    },
    "plates": {
        "size": "1536x1024",
        "background": "transparent",
        "refs": ["F_9.png", "@symbols"],
        "prompt": (
            "Four EMPTY jackpot plates (no text at all, the centre is a plain "
            "dark-indigo glass panel), stacked vertically with clear gaps, "
            "transparent background. Shape like the plates in reference image 1: "
            "wide rounded hexagonal bezel. Top to bottom the bezel metal is: "
            "1) ELECTRIC WHITE - glowing white-platinum bezel with a cold "
            "white-cyan glow (this one is the GRAND plate); "
            "2) GOLD; 3) SILVER; 4) BRONZE / copper. "
            "All four the same size and shape, same rendering as reference 2. "
            + STYLE
        ),
    },
    "cell_empty": {
        "size": "1024x1024",
        "background": "transparent",
        "refs": ["@symbols", "@coin_states"],
        "prompt": (
            "An EMPTY Hold & Win cell marker for the slot: a dark indigo "
            "recessed round socket where a coin will later land, with a faint "
            "dashed cyan ring and a dim lightning glyph in the centre, very low "
            "contrast so it reads as 'empty'. Same rendering as the references. "
            "Centred, transparent background, nothing else. " + STYLE
        ),
    },
}


def _env_key() -> str:
    key = os.environ.get("FAL_KEY")
    if key:
        return key
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("FAL_KEY missing")


def _data_uri(path: Path, max_side: int = 1280) -> str:
    im = Image.open(path)
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    if im.mode == "RGBA" and im.getextrema()[3][0] < 255:
        im.save(buf, "PNG")
        mime = "image/png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=90)
        mime = "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def _ref_path(ref: str) -> Path:
    return OUT_DIR / f"{ref[1:]}.png" if ref.startswith("@") else REF_DIR / ref


def run(job_name: str, suffix: str = "") -> Path:
    job = JOBS[job_name]
    refs = [_data_uri(_ref_path(r)) for r in job.get("refs", [])]
    body = {
        "prompt": job["prompt"],
        "image_size": job["size"],
        "background": job["background"],
        "quality": "high",
        "output_format": "png",
        "num_images": 1,
    }
    endpoint = "fal-ai/gpt-image-1.5"
    if refs:
        endpoint += "/edit"
        body["image_urls"] = refs
        body["input_fidelity"] = "high"
    req = urllib.request.Request(
        f"https://fal.run/{endpoint}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Key {_env_key()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        result = json.load(resp)
    url = result["images"][0]["url"]
    out = OUT_DIR / f"{job_name}{suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
    else:
        urllib.request.urlretrieve(url, out)
    print(f"{job_name}: {out}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--list"]:
        print("\n".join(JOBS))
        raise SystemExit
    suffix = ""
    if args[0].startswith("--suffix="):
        suffix = args.pop(0).split("=", 1)[1]
    for name in args:
        run(name, suffix)
