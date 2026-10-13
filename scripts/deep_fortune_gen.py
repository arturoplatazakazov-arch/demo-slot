"""Deep Fortune art: every layer generated with gpt-image-1.5 (via fal.ai).

Theme brief from the Cre8Pics "Deep Fortune" concept (sunken ruins, mermaids,
shark, Poseidon wild) — the concept is only described in words here, none of
its images are sent to the model: all art is our own generation. Later jobs
pass our own approved symbols back as a style reference so the pack stays in
one rendering style.

    python scripts/deep_fortune_gen.py JOB [JOB ...]
    python scripts/deep_fortune_gen.py --list

Raw outputs land in front/img/deep-fortune/src/<job>.png (not committed).
Needs FAL_KEY in .env — or OPENAI_API_KEY, which then takes precedence and
goes straight to OpenAI (model from OPENAI_IMAGE_MODEL, default gpt-image-1.5).
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
OUT_DIR = Path(os.environ.get("DF_OUT", ROOT / "front/img/deep-fortune/src"))

STYLE = (
    "Premium casual casino slot game art, chunky glossy stylised 3D rendering "
    "(like a top mobile slot): soft bevelled volumes, candy-bright saturated "
    "colours, crisp specular highlights, clean readable silhouette, soft rim "
    "light, no grain. Underwater sunken-city theme: turquoise and deep ocean "
    "blue, gold trims, pearl, colourful coral."
)

SYMBOL = (
    "One single slot machine symbol, centred, filling about 85% of the square, "
    "transparent background, nothing else in the image, no drop shadow on the "
    "ground, no text unless asked. "
)

TILE = (
    "Shown as a square portrait tile: the character is framed by a thick "
    "rounded square stone-and-shell frame in {color}, the character's head "
    "and fins may break out of the frame top edge. "
)

LETTER = (
    "The playing-card letter \"{l}\" as a thick chunky carved-stone glyph in "
    "glossy {color}, a small ancient greek-key ornament engraved on it, a few "
    "small pink coral branches and green sea leaves growing at its base. Only "
    "the single letter {l}. "
)

JOBS: dict[str, dict] = {
    "wild": {
        "size": "1024x1024",
        "prompt": SYMBOL + TILE.format(color="gold with turquoise inlays")
        + "Inside: POSEIDON, king of the sea, a grinning muscular old sea-god "
        "face with a huge wavy teal-green beard and hair, golden crown with an "
        "aquamarine gem. Across the lower part of the tile the word \"WILD\" in "
        "big bubbly iridescent mother-of-pearl letters with a gold outline. "
        + STYLE,
    },
    "scatter": {
        "size": "1024x1024",
        "prompt": SYMBOL + "A big open giant clam shell, glossy coral-orange "
        "outside with gold scroll trims, holding a huge glowing pink-white pearl "
        "that emits a soft magical light and sparkles, small coral at its base. "
        "No frame. " + STYLE,
    },
    "siren": {
        "size": "1024x1024",
        "prompt": SYMBOL + TILE.format(color="ruby red with gold")
        + "Inside: a confident flirty red-haired mermaid with fin-shaped ears, "
        "pearl necklace, seashell top (modest), sly smile, hand near her chin. "
        "Red is the dominant colour of the whole tile. " + STYLE,
    },
    "nymph": {
        "size": "1024x1024",
        "prompt": SYMBOL + TILE.format(color="emerald green with gold")
        + "Inside: a playful sea nymph with light green skin, long curly dark "
        "green seaweed hair, small fin ears, gold shell necklace, resting her "
        "cheek on her hand, mischievous smile. Green is the dominant colour of "
        "the whole tile. " + STYLE,
    },
    "shark": {
        "size": "1024x1024",
        "prompt": SYMBOL + TILE.format(color="royal blue with silver")
        + "Inside: a cheeky cartoon great white shark with a huge toothy grin, "
        "bursting out of the frame toward the viewer, blue back and white belly. "
        "Blue is the dominant colour of the whole tile. " + STYLE,
    },
    "a": {"size": "1024x1024", "prompt": SYMBOL + LETTER.format(l="A", color="golden yellow") + STYLE},
    "k": {"size": "1024x1024", "prompt": SYMBOL + LETTER.format(l="K", color="coral red") + STYLE},
    "q": {"size": "1024x1024", "prompt": SYMBOL + LETTER.format(l="Q", color="jade green") + STYLE},
    "j": {"size": "1024x1024", "prompt": SYMBOL + LETTER.format(l="J", color="sky blue") + STYLE},
    "wild_big": {
        "size": "1024x1536",
        "refs": ["@wild"],
        "prompt": "Same POSEIDON character and the same gold-turquoise frame "
        "style as the reference symbol. Now a TALL NARROW vertical banner panel, "
        "exactly three times taller than wide, centred and occupying only the "
        "middle third of the image width, transparent everywhere else: "
        "Poseidon shown from the head down to the waist, holding a golden "
        "trident upright, beard flowing, inside the tall framed panel with deep "
        "blue water behind him; the word \"WILD\" in the same iridescent pearl "
        "letters at the bottom of the panel. " + STYLE,
    },
    "hero": {
        "size": "1024x1536",
        "refs": ["@siren"],
        "prompt": "Full figure of the SAME red-haired mermaid as in the "
        "reference symbol (same face, hair, pearl necklace, shell top), now as "
        "a standalone mascot without any frame: whole body with her ruby-pink "
        "fish tail, sitting on a small rock with coral, relaxed idle pose, one "
        "hand waving gently, friendly smile. Centred, transparent background, "
        "nothing else in the image. " + STYLE,
    },
    "hero_tense": {
        "size": "1024x1536",
        "refs": ["@hero"],
        "prompt": "The exact same mermaid mascot, same rock, same framing and "
        "size, but now TENSE and excited: leaning forward, both hands clasped "
        "together in front of her chest, biting her lip, wide hopeful eyes. "
        "Transparent background. " + STYLE,
    },
    "hero_cheer": {
        "size": "1024x1536",
        "refs": ["@hero"],
        "prompt": "The exact same mermaid mascot, same rock, same framing and "
        "size, but now CHEERING a big win: both arms raised high in joy, huge "
        "open smile, tail flicking up, a few sparkles and bubbles around her. "
        "Transparent background. " + STYLE,
    },
    "logo": {
        "size": "1536x1024",
        "refs": ["@wild"],
        "prompt": "Game logo reading exactly \"DEEP FORTUNE\" on two lines: "
        "smaller \"DEEP\" above, big \"FORTUNE\" below, centred. Letters are "
        "fat rounded bubbly glossy mother-of-pearl / iridescent pearl white "
        "with a thick gold outline, like the WILD lettering in the reference. "
        "A golden trident crosses diagonally behind the word, a few turquoise "
        "starfish, seashells and bubbles decorate it. No plaque, no sign board "
        "behind the letters. Transparent background, nothing else. " + STYLE,
    },
    "bg_base": {
        "size": "1536x1024",
        "background": "opaque",
        "prompt": "Background plate for a slot game, wide landscape. The ruins "
        "of a sunken ancient city deep underwater: broken marble colonnades and "
        "arches on both sides, a domed temple far in the centre background, "
        "light rays from the surface, bubbles, bright colourful coral reefs "
        "and sea plants in the lower left and right corners, a sandy stone "
        "floor. The centre of the image is open calm deep blue water (the "
        "reels will cover it). The art fills every pixel edge to edge, no "
        "letterbox, no white or black bars, no border. NO reels, NO frame, NO "
        "text, NO logo, NO characters. " + STYLE,
    },
    "bg_base_mob": {
        "size": "1024x1536",
        "background": "opaque",
        "refs": ["@bg_base"],
        "prompt": "Portrait version of the reference background: the same "
        "sunken city ruins, colonnades on the sides, temple dome near the top "
        "centre, light rays, coral reefs along the bottom. Centre is open deep "
        "blue water. The art fills every pixel edge to edge, no bars, no text, "
        "no reels, no characters. " + STYLE,
    },
    "bg_bonus": {
        "size": "1536x1024",
        "background": "opaque",
        "refs": ["@bg_base"],
        "prompt": "Bonus round version of the reference background: we are now "
        "INSIDE Poseidon's sunken throne hall — golden columns, a huge golden "
        "throne far in the centre background with a trident behind it, heaps of "
        "gold coins and open treasure chests on the floor on both sides, warm "
        "gold and magenta glow mixed with the deep blue water, glowing "
        "jellyfish, bubbles. Centre is open space (reels go there). The art "
        "fills every pixel edge to edge, no bars, no text, no reels, no "
        "characters. " + STYLE,
    },
    "bg_bonus_mob": {
        "size": "1024x1536",
        "background": "opaque",
        "refs": ["@bg_bonus"],
        "prompt": "Portrait version of the reference bonus background: same "
        "golden throne hall, throne near the top centre, treasure along the "
        "bottom. Art fills every pixel edge to edge, no bars, no text, no "
        "reels, no characters. " + STYLE,
    },
    "popup_plate": {
        "size": "1536x1024",
        "refs": ["@logo"],
        "prompt": "A win banner plate for a slot game: wide rounded-rectangle "
        "frame of gold with turquoise shell ornaments and small pink coral on "
        "the corners; the inside is a plain EMPTY flat dark navy-blue glass "
        "panel (no text, no numbers, nothing inside) taking about 65% of the "
        "width. Centred, transparent background around it. " + STYLE,
    },
    "popup_plate_mega": {
        "size": "1536x1024",
        "refs": ["@popup_plate"],
        "prompt": "A RICHER version of the reference win plate for MEGA WIN: "
        "same empty dark navy centre panel (no text), the gold frame now "
        "crowned by a big golden shell on top, pearls along the border, coral "
        "and gold coins bursting out on both sides. Transparent background. "
        + STYLE,
    },
    "popup_plate_epic": {
        "size": "1536x1024",
        "refs": ["@popup_plate"],
        "prompt": "The MOST epic version of the reference win plate for EPIC "
        "WIN: a sunken marble temple portal with two columns and a pediment "
        "with Poseidon's golden trident on top, waterfalls of gold coins and "
        "pearls, glowing; between the columns a plain EMPTY dark navy panel "
        "(no text). Transparent background. " + STYLE,
    },
    "buy_bonus": {
        "size": "1024x1024",
        "refs": ["@scatter"],
        "prompt": "A 'buy bonus' button plate: a rounded golden-framed "
        "turquoise-and-navy shell-shaped badge, the open clam with the glowing "
        "pearl from the reference sitting on its top edge, the centre of the "
        "badge a plain EMPTY dark navy panel for text (no text). Centred, "
        "transparent background. " + STYLE,
    },
    "fs_counter": {
        "size": "1024x1536",
        "refs": ["@popup_plate"],
        "prompt": "A tall vertical free-spins counter plate in the same style "
        "as the reference: gold frame with turquoise shells, a small golden "
        "trident and pearl crest on top, the inside a plain EMPTY dark navy "
        "panel (no text, no numbers). Narrow: about two thirds as wide as "
        "tall, centred, transparent background. " + STYLE,
    },
    "cover": {
        "size": "1536x1024",
        "background": "opaque",
        "refs": ["@bg_base", "@logo", "@hero", "@wild"],
        "prompt": "Catalog cover art for the slot game: the sunken city "
        "background from reference 1, the DEEP FORTUNE logo from reference 2 "
        "big in the centre-top, the mermaid from reference 3 on the left and "
        "Poseidon from reference 4 on the right, gold coins and bubbles. "
        "Composition fits a wide 1.9:1 crop. Fills every pixel. " + STYLE,
    },
}


def _env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"') or None
    return None


def _env_key() -> str:
    return _env("FAL_KEY") or sys.exit("FAL_KEY missing")


def _openai_generate(job: dict) -> bytes:
    """Same job straight through OpenAI's Images API (OPENAI_API_KEY in .env)
    — the fallback for when the fal balance is empty. Refs go as multipart
    files to /images/edits, exactly like fal's /edit image_urls."""
    import httpx

    headers = {"Authorization": f"Bearer {_env('OPENAI_API_KEY')}"}
    fields = {
        "model": _env("OPENAI_IMAGE_MODEL") or "gpt-image-1.5",
        "prompt": job["prompt"],
        "size": job["size"],
        "background": job.get("background", "transparent"),
        "quality": "high",
        "output_format": "png",
        "n": "1",
    }
    refs = job.get("refs", [])
    with httpx.Client(timeout=420) as client:
        if refs:
            files = []
            for r in refs:
                im = Image.open(OUT_DIR / f"{r[1:]}.png")
                im.thumbnail((1280, 1280))
                buf = io.BytesIO()
                im.save(buf, "PNG")
                files.append(("image[]", (f"{r[1:]}.png", buf.getvalue(), "image/png")))
            fields["input_fidelity"] = "high"
            resp = client.post("https://api.openai.com/v1/images/edits",
                               headers=headers, data=fields, files=files)
        else:
            body = dict(fields, n=1)
            resp = client.post("https://api.openai.com/v1/images/generations",
                               headers=headers, json=body)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} {resp.text[:300]}")
    return base64.b64decode(resp.json()["data"][0]["b64_json"])


def _data_uri(path: Path, max_side: int = 1280) -> str:
    im = Image.open(path)
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def run(job_name: str, force: bool = False) -> None:
    out = OUT_DIR / f"{job_name}.png"
    if out.exists() and not force:
        print(f"{job_name}: skip (exists)")
        return
    job = JOBS[job_name]
    if _env("OPENAI_API_KEY"):
        for attempt in range(3):
            try:
                data = _openai_generate(job)
                Image.open(io.BytesIO(data)).load()
                break
            except Exception as exc:  # noqa: BLE001 — report and retry / move on
                print(f"{job_name}: FAIL#{attempt} {exc}", flush=True)
        else:
            return
        _save(out, data, job_name)
        return
    refs = [_data_uri(OUT_DIR / f"{r[1:]}.png") for r in job.get("refs", [])]
    body = {
        "prompt": job["prompt"],
        "image_size": job["size"],
        "background": job.get("background", "transparent"),
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
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=420) as resp:
                result = json.load(resp)
            url = result["images"][0]["url"]
            if url.startswith("data:"):
                data = base64.b64decode(url.split(",", 1)[1])
            else:
                with urllib.request.urlopen(url, timeout=120) as resp:
                    data = resp.read()
            Image.open(io.BytesIO(data)).load()  # reject truncated downloads
            break
        except Exception as exc:  # noqa: BLE001 — report and retry / move on
            detail = getattr(exc, "read", lambda: b"")()[:300]
            print(f"{job_name}: FAIL#{attempt} {exc} {detail!r}", flush=True)
    else:
        return
    _save(out, data, job_name)


def _save(out: Path, data: bytes, job_name: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.rename(out)
    print(f"{job_name}: {out}", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--list"]:
        print("\n".join(JOBS))
        raise SystemExit
    force = "--force" in args
    names = [a for a in args if not a.startswith("--")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: run(n, force), names))
