"""Olympus Thunder art: every layer generated with gpt-image-1.5 (via fal.ai).

The pack is built in parts on purpose: Zeus, the temple and the special symbols
come out as separate pieces (body / arms / beard / cape, sky / temple / columns,
orb shell / core) so the Spine rigs in olympus_thunder_spine.py can move them
independently instead of sliding one flat picture around.

    python scripts/olympus_thunder_gen.py JOB [JOB ...]   # see JOBS
    python scripts/olympus_thunder_gen.py --list

Jobs that list `refs` are run through /edit with those images as the style
anchor ("@job" = an earlier job's output), so the whole pack stays in one hand.
Raw outputs land in front/img/olympus-thunder/src/<job>.png (gitignored);
cutting/cleanup lives in olympus_thunder_build.py. Needs FAL_KEY in .env.
"""

from __future__ import annotations

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
OUT_DIR = Path(os.environ.get("OT_OUT", ROOT / "front/img/olympus-thunder/src"))

STYLE = (
    "Hand-painted stylised 3D game art, the art-directed finish of a top-tier "
    "slot studio: sculpted forms with clear, simple, readable silhouettes; "
    "painterly material texture (veined marble, hammered gold, worn bronze, "
    "cut gemstone); ONE consistent key light from the upper left, a cool "
    "cyan-white rim light from storm lightning behind, soft deep occlusion. "
    "Restrained palette: storm navy #16213E to #0B1026, warm marble #E8E1D0, "
    "gold #F5B400 / #FFD75A, electric cyan #9FE8FF only as an accent. Mature, "
    "dramatic, slightly dark mood. Crafted, not generated: no plastic gloss, no "
    "airbrushed glow on everything, no lens flares, no random sparkles or bokeh, "
    "no noisy filigree, no melted details, no gibberish text."
)

ISOLATE = (
    "Transparent background. Each object fully separate with generous empty "
    "space around it, nothing touching or overlapping, no cell borders, no "
    "labels, no drop shadow on the ground."
)

JOBS: dict[str, dict] = {
    # -- master style anchor -------------------------------------------------
    "sym_high": {
        "size": "1024x1024", "background": "transparent",
        "prompt": STYLE + "\n\n" + ISOLATE + """
Four slot-machine HIGH symbols for a Greek mythology game, a 2 by 2 grid, each
centred in its quarter, each filling about 70% of its quarter, seen from a
slight three-quarter front angle:
top-left: a Corinthian bronze-and-gold war helmet with a tall crimson horsehair
crest, dark eye slits, hammered gold cheek guards;
top-right: a golden lyre with ivory strings and a small sapphire at the yoke;
bottom-left: a black-figure Greek amphora, terracotta orange with black painted
meander band, gold rim and handles;
bottom-right: a laurel wreath of deep green leaves with gold veins tied by a
crimson ribbon.
Each a chunky, iconic object a player reads instantly at 90 pixels. Distinct
dominant colours: helmet crimson+gold, lyre gold, amphora terracotta, wreath green.""",
    },
    "sym_gems": {
        "size": "1536x1024", "background": "transparent", "refs": ["@sym_high"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
Same rendering style and light as the reference. Five slot LOW symbols: cut
gemstones that share EXACTLY the same silhouette and cut (a chunky octagonal
step-cut gem, slightly taller than wide, seen straight on with a faint tilt),
only the colour differs. Layout: 3 in the top row, 2 centred in the bottom row,
equal size, each about 260 px tall.
Top row left to right: ruby red, amethyst violet, emerald green.
Bottom row: sapphire blue, citrine yellow-amber.
Inner facets clean and readable, a small hard specular glint at the upper left,
no gold mount, no sparkle stars.""",
    },
    "sym_special": {
        "size": "1536x1024", "background": "transparent", "refs": ["@sym_high"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
Same rendering style and light as the reference. Three SPECIAL slot symbols in
one row, equal visual weight, each about 420 px:
1) SCATTER "Ring of Lightning": a thick round golden amulet ring, an open
   centre showing deep storm-blue enamel with a white-cyan lightning bolt
   running across it, small Greek key pattern engraved on the gold band;
2) JACKPOT "Eagle of Zeus": a golden eagle with spread wings, front view, head
   turned to the side, clutching a short lightning bolt in its talons, polished
   gold with dark bronze feather separations;
3) MULTIPLIER ORB: a glowing sphere of electric gold, a white-hot core, thin
   cyan arcs of electricity curling across its surface, a narrow gold metal
   band around its equator, the centre left calm and bright so a number can be
   printed on it later. NO number, NO text.""",
    },
    # -- Zeus, in parts --------------------------------------------------------
    "zeus_full": {
        "size": "1024x1536", "background": "transparent", "refs": ["@sym_high"],
        "prompt": STYLE + """

Transparent background. Character art: ZEUS, our own original mascot, waist-up
(cut at the belt), three-quarter view facing right, powerful and old: long
silver-white beard and hair moving in the wind, heavy brows, glowing pale-cyan
eyes, golden muscled cuirass with a lion-head buckle and a dark navy cloak over
his left shoulder. His right arm is raised high, the fist gripping a long
jagged lightning bolt of white-cyan energy pointing up; his left arm rests in
front, palm open with small sparks. Stern, regal, a little smile. Clear
silhouette, no background elements, no ground.""",
    },
    "zeus_parts": {
        "size": "1536x1024", "background": "transparent", "refs": ["@zeus_full"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
A cut-out PARTS SHEET of exactly this character for 2D skeletal animation,
same style, same colours, same scale, all parts in the SAME pose as the
reference, each part complete (painted fully where it would be hidden behind
other parts), laid out separately with space between them:
1) TORSO with neck and the cloak on the shoulder, NO head, NO beard, NO arms
   (clean round shoulder joints);
2) HEAD with hair and eyes but WITHOUT the beard (bare chin and jaw);
3) BEARD alone (the long silver beard and moustache);
4) RIGHT ARM raised, upper arm + forearm + fist, WITHOUT the lightning bolt;
5) LEFT ARM bent in front with the open palm;
6) the long LIGHTNING BOLT alone, vertical;
7) the loose back part of the navy CLOAK alone.""",
    },
    # -- environment, in layers -------------------------------------------------
    "bg_sky": {
        "size": "1536x1024", "background": "opaque", "refs": ["@sym_high"],
        "prompt": STYLE + """

Background plate for a slot game, NO buildings, NO characters: the sky above
the summit of Mount Olympus during a storm. Dense dark navy storm clouds,
rolling, with a few dramatic tears through which warm gold light falls from
above; distant faint mountain ridges at the very bottom edge. The centre is
calmer and darker (the reels will sit there). Painterly, cinematic, deep.""",
    },
    "bg_temple": {
        "size": "1536x1024", "background": "transparent", "refs": ["@bg_sky"],
        "prompt": STYLE + """

Transparent background. ONLY the architecture, as a separate layer to put over
a storm sky: the inside of a white marble Greek temple on Olympus seen from the
front. Two massive fluted Ionic columns with gold capitals, one at the far
left edge and one at the far right edge, each full height; a marble floor
with stone steps across the bottom fifth; between the columns NOTHING (fully
transparent, the sky shows through). Lit by the same storm light, cyan rim
light on the column edges, warm gold bounce from below.""",
    },
    "bg_sky_fs": {
        "size": "1536x1024", "background": "opaque", "refs": ["@bg_sky"],
        "prompt": STYLE + """

The same storm sky plate as the reference, same composition, but for the FREE
SPINS mode: the clouds lit from inside in royal purple and molten gold, a
blazing gold break in the clouds at the top centre, the storm charged and
glorious. NO buildings, NO characters.""",
    },
    "bg_sky_mob": {
        "size": "1024x1536", "background": "opaque", "refs": ["@bg_sky"],
        "prompt": STYLE + """

The same storm sky as the reference, re-composed for a portrait phone screen:
dark navy storm clouds with gold tears, the calmer darker middle where the
reels sit. NO buildings, NO characters.""",
    },
    "bg_sky_fs_mob": {
        "size": "1024x1536", "background": "opaque", "refs": ["@bg_sky_fs"],
        "prompt": STYLE + """

The same purple-and-gold charged storm sky as the reference, re-composed for a
portrait phone screen, blazing gold break at the top. NO buildings, NO characters.""",
    },
    "clouds": {
        "size": "1536x1024", "background": "transparent", "refs": ["@bg_sky"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
Six separate soft storm cloud wisps of different sizes for a parallax layer,
dark blue-grey with a cyan-lit rim on the upper edge, soft painted edges,
semi-transparent at their borders.""",
    },
    # -- reel frame ------------------------------------------------------------
    "frame": {
        "size": "1024x1024", "background": "transparent", "refs": ["@bg_temple"],
        "prompt": STYLE + """

Transparent background. A slot-machine reel frame for a 6 by 5 grid, seen
straight on, flat front view, symmetrical. The frame: a slim polished gold
border with a narrow Greek-key meander engraved band, small gold palmette
ornaments only at the four corners and at the middle of the top bar, dark
bronze inner bevel. The inner opening is a rectangle a little wider than tall
(ratio 6 to 5) and takes about 86% of the image width; fill the inner opening
with FLAT PURE MAGENTA #FF00FF. Outside the frame transparent. No text.""",
    },
    "logo": {
        "size": "1536x1024", "background": "transparent", "refs": ["@sym_high"],
        "prompt": STYLE + """

Transparent background. Game logo, the words "OLYMPUS" (large, top line) and
"THUNDER" (second line, a bit smaller, wider letter spacing), spelled exactly
like that. Heavy chiselled classical capital letters in hammered gold with a
dark bronze bevel, a thin white-cyan lightning crack running through the gold
of the second word, a small golden laurel sprig and lightning bolt crest above
the centre. Compact, wide composition, sharp, legible, nothing else.""",
    },
    # -- UI --------------------------------------------------------------------
    "ui_plates": {
        "size": "1536x1024", "background": "transparent", "refs": ["@frame"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
UI parts in the same gold and dark-bronze style as the reference frame, all
EMPTY (no text, no numbers), their inner panels filled with FLAT PURE MAGENTA
#FF00FF:
row 1: four identical small horizontal jackpot plaques (pill-shaped gold rim,
       small gem at each end) — gem colours: green, blue, violet, red;
row 2 left: a wide horizontal plaque with a laurel on each end (win counter);
row 2 middle: a round medallion with a lightning bolt crest on top (multiplier
       counter);
row 2 right: a big round button rim, gold with a lightning bolt engraved in
       its lower edge (buy bonus button).""",
    },
    "buy_cards": {
        "size": "1536x1024", "background": "transparent", "refs": ["@sym_special", "@frame"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
Three tall vertical offer cards for a bonus-buy window, one row, same size
(portrait 2:3), gold rim with a dark bronze bevel, NO text anywhere, the lower
third of each card left as an EMPTY flat dark navy band for text:
1) FREE SPINS card: the golden Ring of Lightning amulet over a storm-blue glow;
2) SUPER FREE SPINS card: a richer purple-and-gold card, three glowing golden
   multiplier orbs stacked in a cluster with crackling lightning;
3) JACKPOT CHANCE card: the golden eagle of Zeus over a gold sunburst.""",
    },
    "wheel": {
        "size": "1024x1024", "background": "transparent", "refs": ["@frame"],
        "prompt": STYLE + """

Transparent background. A jackpot prize WHEEL seen perfectly front-on, a flat
circle: exactly TWELVE equal wedge sectors, alternating colours in this order
clockwise from the top: green, blue, green, violet, green, blue, green, red,
green, blue, green, violet. Thin gold spokes between the sectors, a heavy gold
outer rim with twelve small round gold studs, a gold hub in the centre with a
lightning bolt. The sectors are flat, slightly glossy enamel, EMPTY, no text,
no numbers, no icons.""",
    },
    "wheel_pointer": {
        "size": "1024x1024", "background": "transparent", "refs": ["@wheel"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
A single gold wheel POINTER for the top of the prize wheel in the reference:
a downward-pointing gold arrowhead shaped like a stylised eagle head and a
lightning bolt tip, pointing straight down, centred, about 40% of the image.""",
    },
    "titles": {
        "size": "1536x1024", "background": "transparent", "refs": ["@logo"],
        "prompt": STYLE + "\n\n" + ISOLATE + """
Popup title lettering in the same gold chiselled style as the reference logo,
six separate words / phrases, each on its own line, centred, spelled EXACTLY:
"BIG WIN"
"MEGA WIN"
"EPIC WIN"
"FREE SPINS"
"SUPER FREE SPINS"
"JACKPOT"
Each a little different in trim: BIG WIN gold, MEGA WIN gold with cyan
lightning crack, EPIC WIN gold with violet glow edge, FREE SPINS gold with
storm-blue bevel, SUPER FREE SPINS gold with purple bevel, JACKPOT gold with
red gems.""",
    },
    # -- FX sprites (painted on black, keyed by luminance) ----------------------
    "fx_bolts": {
        "size": "1536x1024", "background": "opaque",
        "prompt": """Pure black background #000000. VFX sprite sheet for a game: six
separate lightning bolts, white-hot core fading to electric cyan #9FE8FF
glow, crisp jagged branching shapes, no other objects, no ground, no clouds.
Layout: three tall vertical bolts on the left half, three shorter forked bolts
on the right half, nothing touching.""",
    },
    "cover": {
        "size": "1024x1024", "background": "opaque", "refs": ["@zeus_full", "@bg_sky", "@logo", "@sym_special"],
        "prompt": STYLE + """

Square lobby icon for the slot game: the Zeus character from the reference on
the left, lightning bolt raised, storm sky behind, a big glowing golden
multiplier orb in the lower right printed with "x100", the "OLYMPUS THUNDER"
logo across the bottom. Dramatic, high contrast, readable as a small tile.""",
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
    return OUT_DIR / f"{ref[1:]}.png" if ref.startswith("@") else Path(ref)


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
    with urllib.request.urlopen(req, timeout=900) as resp:
        result = json.load(resp)
    url = result["images"][0]["url"]
    out = OUT_DIR / f"{job_name}{suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
    else:
        urllib.request.urlretrieve(url, out)
    print(f"{job_name}{suffix}: {out}", flush=True)
    return out


def _safe(name: str, suffix: str) -> None:
    try:
        run(name, suffix)
    except Exception as exc:  # keep the other parallel jobs going
        print(f"{name}{suffix}: FAILED {exc}", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--list"]:
        print("\n".join(JOBS))
        raise SystemExit
    suffix = ""
    if args[0].startswith("--suffix="):
        suffix = args.pop(0).split("=", 1)[1]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda n: _safe(n, suffix), args))
