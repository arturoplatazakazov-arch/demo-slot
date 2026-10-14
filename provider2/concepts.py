"""Provider 2: ten original slot concepts, each an alternative to a Cre8Pics
portfolio project (same theme, our own name, characters and items).

The references are only described in words here; none of their images go to
an image model. Running this file writes CONCEPTS.md (human brief) and
prompts.json (one prompt per art job, ready for ChatGPT / gpt-image / fal).

    python provider2/concepts.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

STYLE = (
    "Premium mobile casino slot game art, glossy stylised hand-painted 3D look "
    "(top-tier slot provider quality), saturated colours, crisp specular "
    "highlights, soft rim light, clean readable silhouettes, no watermark, "
    "no signature."
)

GAMES: list[dict] = [
    {
        "slug": "rad-raiders",
        "name": "RAD RAIDERS",
        "ref": "spinout",
        "theme": "Retro-atomic 1950s wasteland: ruined suburb under a toxic orange sky, glowing green acid puddles, scavengers and mutants.",
        "palette": "acid green, rust orange, toxic yellow, faded teal, red warning stripes",
        "logo": "RAD RAIDERS in chunky riveted metal letters dripping glowing green goo, a yellow-black radiation trefoil replacing the O-like shape of the first A, rusty bolts",
        "heroes": [
            "Scavenger mechanic girl with welding goggles on her head, patched orange jumpsuit, wrench over shoulder, cheeky grin",
            "Huge mutant two-headed armadillo wearing a scrap-metal helmet, glowing green spikes",
            "Ghoul DJ biker with half-melted face, leather jacket with radiation patch, holding a glowing jukebox remote",
        ],
        "hp": [
            "Geiger counter with a glowing needle and dangling cable",
            "Retro gas mask with green-glowing lenses",
            "Dented can of 'GLOW BEANS' leaking luminous green goo",
            "Bottle of fizzy 'RAD POP' soda with radioactive bubbles",
        ],
        "lp_style": "rusty riveted scrap-metal letters with yellow-black hazard stripe accents and glowing green rivets",
        "wild": "Leaking yellow radioactive barrel with dripping green slime and the word WILD stencilled on it",
        "scatter": "Round steel bunker vault door with gauge lights and the word SCATTER on a plate",
        "bonus": "Red retro tube radio transmitter crackling with green energy, the word BONUS on a plate",
        "frame": "Reel frame built from rusty steel girders, hazard-striped corners, dangling cables, glowing green tubes along the sides and a cracked warning light on top",
        "bg_base": "Ruined 1950s suburban main street at sunset under a toxic orange sky, burnt-out diner with flickering neon sign, abandoned rusty car, glowing green acid puddles, radioactive barrels, drones in the sky",
        "bg_bonus": "Inside an underground fallout bunker at night: green-lit control room with blinking consoles, vault door half open, glowing reactor core in the centre, sparks and steam",
    },
    {
        "slug": "jade-paws",
        "name": "JADE PAWS",
        "ref": "panda-adventures",
        "theme": "Peaceful oriental bamboo valley with a red-panda monk, lanterns, koi pond and a mountain temple.",
        "palette": "jade green, lacquer red, warm gold, soft cream, sky teal",
        "logo": "JADE PAWS in carved glossy jade-green letters with gold trim, a small red panda paw print in the letter A, bamboo leaves and a red silk tassel on the side",
        "heroes": [
            "Cute red panda monk in an orange robe and straw hat holding a steaming tea bowl",
            "Wise old tortoise sage with a long white beard and a bamboo staff",
        ],
        "hp": [
            "Golden koi fish leaping out of a splash of water",
            "Bamboo steamer basket full of jade dumplings",
            "Bronze gong with a red tassel striker",
            "Folded paper fan painted with pink cherry blossoms",
        ],
        "lp_style": "glossy carved jade-stone letters with gold edges and a small pink lotus flower on each",
        "wild": "Golden pagoda temple bell with red ribbons and the word WILD in gold",
        "scatter": "Glowing pink lotus flower on a lily pad with the word SCATTER",
        "bonus": "Red paper lantern with a golden fortune coin, the word BONUS",
        "frame": "Reel frame of dark lacquered red wood with gold cloud carvings, a curved pagoda roof on top, hanging red lanterns on the corners and bamboo stalks on the sides",
        "bg_base": "Sunny bamboo valley with a calm koi pond, stone path with pink petals, small wooden pagodas and stone lanterns, misty mountains in the distance",
        "bg_bonus": "The same valley at night during a lantern festival: hundreds of floating glowing lanterns over the pond, fireworks, a big full moon behind the mountain temple",
    },
    {
        "slug": "ghoul-groove",
        "name": "GHOUL GROOVE",
        "ref": "disco-potion",
        "theme": "Monster disco party in a haunted manor: DJ werewolf, dancing mummy, neon dance floor, spooky cocktails.",
        "palette": "neon purple, hot pink, toxic green, electric cyan, gold",
        "logo": "GHOUL GROOVE in glossy neon-purple and green bubbly letters with a disco-ball skull in the first O, music notes and bat wings on the sides",
        "heroes": [
            "Werewolf DJ with headphones, sunglasses and a gold chain, scratching a glowing vinyl",
            "Mummy dancer in loose bandages striking a disco pose, glowing eyes",
            "Ghost girl diva with a microphone and a sparkling sequin dress",
        ],
        "hp": [
            "Skull-shaped mirror disco ball",
            "Coffin-shaped boombox with glowing speakers",
            "Bubbling glowing green potion bottle with a bat stopper",
            "Neon pink cocktail in a skull glass with a cherry eyeball",
        ],
        "lp_style": "glossy chrome-and-neon letters, each in a different neon colour, with tiny star sparkles",
        "wild": "Glowing vinyl record with a jack-o-lantern label and the word WILD in neon",
        "scatter": "Haunted jukebox glowing purple with the word SCATTER",
        "bonus": "Golden VIP party ticket with bat wings, the word BONUS",
        "frame": "Reel frame shaped like a gothic DJ stage: stone arch with neon tubes, speakers stacked on both sides, a DJ mixer console along the bottom, bats on the top corners",
        "bg_base": "Haunted gothic manor hall turned into a disco: glowing multicolour tiled dance floor, coloured spotlights, cobwebs, candles, balloons, full moon visible through tall windows",
        "bg_bonus": "Rooftop of the haunted manor at midnight: huge glowing moon, laser beams in the sky, fireworks, flying bats, neon dance floor on the roof tiles",
    },
    {
        "slug": "gummy-gold-rush",
        "name": "GUMMY GOLD RUSH",
        "ref": "sugar-way",
        "theme": "Candy Wild West: gummy cowboys, a licorice railway through a sugar canyon, candy cacti.",
        "palette": "candy pink, sunny yellow, mint, caramel orange, sky blue",
        "logo": "GUMMY GOLD RUSH in puffy glossy candy letters (pink, yellow, mint) on a wooden saloon sign with gold nuggets and a lollipop",
        "heroes": [
            "Gummy bear sheriff with a cowboy hat and a star badge",
            "Marshmallow cowgirl with a lasso made of licorice",
            "Chocolate-cookie bandit with a red bandana mask",
        ],
        "hp": [
            "Gummy bear sheriff portrait in a square tile",
            "Marshmallow cowgirl portrait in a square tile",
            "Cookie bandit portrait in a square tile",
            "Caramel gold nugget pile in a mine cart",
        ],
        "lp_style": "five glossy jelly candies: red jelly heart, orange candy star, green gummy worm, purple wrapped bonbon, blue rock-candy crystal (no letters)",
        "wild": "Golden sheriff star badge made of hard candy with the word WILD",
        "scatter": "Candy WANTED poster with a lollipop, the word SCATTER",
        "bonus": "Candy steam locomotive ticket, the word BONUS",
        "frame": "Reel frame made of a pink wafer-and-licorice railway trestle, candy-cane posts on the corners, frosting dripping from the top, a tiny candy train on top",
        "bg_base": "Sunny candy desert canyon: caramel rock mesas, lollipop and candy-cane cacti, a licorice railway track winding to a candy saloon town, cotton-candy clouds",
        "bg_bonus": "The candy canyon at sunset: chocolate river, glittering sugar crystal mine entrance lit with lanterns, the candy train crossing a bridge, pink-orange sky",
    },
    {
        "slug": "whisker-noir",
        "name": "WHISKER NOIR",
        "ref": "wild-detectives",
        "theme": "1940s film-noir city of animal detectives: rainy streets, neon, a jewel heist to solve.",
        "palette": "deep navy, rain blue, neon red, amber lamp light, gold",
        "logo": "WHISKER NOIR in elegant art-deco gold letters with a neon red outline, a cat-whisker flourish under the word, rain drops",
        "heroes": [
            "Owl police inspector in a trench coat and fedora holding a magnifying glass",
            "Black cat femme fatale in a red evening dress with a long cigarette holder (no smoke)",
            "Raccoon jewel thief with a striped shirt and a sack of diamonds",
            "Bulldog police chief in a blue uniform with a badge",
        ],
        "hp": [
            "Owl inspector portrait in an art-deco tile",
            "Black cat femme fatale portrait in an art-deco tile",
            "Raccoon thief portrait in an art-deco tile",
            "Bulldog police chief portrait in an art-deco tile",
        ],
        "lp_style": "art-deco gold letters with a polished stone inlay in different colours (ruby, sapphire, emerald, amber)",
        "wild": "Golden police badge with a paw print and the word WILD",
        "scatter": "Red fingerprint dossier folder stamped SCATTER",
        "bonus": "Stolen giant pink diamond in a glass case, the word BONUS",
        "frame": "Reel frame of art-deco brass and dark lacquered wood like a 1940s detective office window, venetian blind shadows, a desk lamp on the top corner",
        "bg_base": "Rainy 1940s city street at night: neon signs, wet cobblestones reflecting lights, a vintage car, detective office windows, fog",
        "bg_bonus": "Inside a grand art-deco museum vault at night: laser alarms, pedestals with jewels, a huge pink diamond under a spotlight, moonlight through a glass dome",
    },
    {
        "slug": "cogwork-skies",
        "name": "COGWORK SKIES",
        "ref": "gearspier",
        "theme": "Steampunk floating sky city: brass airships, clockwork towers, little inventor automatons.",
        "palette": "brass gold, copper, teal glass, cream parchment, sky blue",
        "logo": "COGWORK SKIES in embossed brass letters on a riveted copper plate, spinning cogs behind, a small airship propeller on the side, steam puffs",
        "heroes": [
            "Young inventor girl with brass goggles and a mechanical arm, holding blueprints",
            "Brass owl automaton with glowing teal eyes and clockwork wings",
        ],
        "hp": [
            "Brass airship with a striped balloon",
            "Glowing teal tesla coil in a bell jar",
            "Golden pocket watch with exposed gears",
            "Brass telescope on a tripod",
        ],
        "lp_style": "letters forged from brass pipes and cogs with small rivets and copper accents",
        "wild": "Big golden master cog with the word WILD engraved",
        "scatter": "Steam-powered treasure safe with dials, the word SCATTER",
        "bonus": "Golden key with clockwork bow, the word BONUS",
        "frame": "Reel frame of riveted brass and copper pipes, rotating cogs in the corners, pressure gauges and a small steam whistle on top",
        "bg_base": "Steampunk sky city floating above clouds in daylight: brass towers, copper domes, airships, steam pipes, a clock tower, blue sky",
        "bg_bonus": "The sky city at golden sunset with fireworks over a giant clockwork airship dock, many airships launching, glowing lanterns",
    },
    {
        "slug": "hex-hollow",
        "name": "HEX HOLLOW",
        "ref": "witches-book",
        "theme": "Enchanted witch forest: cauldrons, spellbooks, crystal ball, black cat familiars under a purple moon.",
        "palette": "deep purple, toxic green, pumpkin orange, gold, midnight blue",
        "logo": "HEX HOLLOW in glossy gold letters with green magical smoke, the O as a crystal ball with a moon inside, a witch hat on the H",
        "heroes": [
            "Young red-haired witch with a pointy hat and a glowing wand",
            "Old warlock with a purple robe and a raven on his shoulder",
            "Black cat familiar with glowing yellow eyes and a tiny witch hat",
        ],
        "hp": [
            "Glowing crystal ball on a claw stand",
            "Ancient spellbook with a glowing rune on the cover",
            "Mandrake root with a screaming face in a pot",
            "Black candle with purple flame on a skull holder",
        ],
        "lp_style": "five magic objects: green potion vial, purple moth, blue rune stone, orange mushroom, red magic gem (no letters)",
        "wild": "Carved jack-o-lantern style turnip lantern with green fire and the word WILD",
        "scatter": "Bubbling green cauldron with the word SCATTER",
        "bonus": "Witch broomstick crossed with a moon amulet, the word BONUS",
        "frame": "Reel frame of twisted dark tree roots and branches with hanging lanterns, glowing mushrooms and a gold moon ornament on top",
        "bg_base": "Enchanted dark forest clearing with a crooked witch cottage, glowing mushrooms, fireflies, purple fog, a stone path",
        "bg_bonus": "Blood-red moon over an ancient stone circle, witches flying on brooms, green magic fire in the centre, swirling spell runes in the sky",
    },
    {
        "slug": "bayou-bedlam",
        "name": "BAYOU BEDLAM",
        "ref": "toxic-swamp",
        "theme": "Cartoon rubber-hose style hillbilly bayou full of goofy mutant critters and moonshine.",
        "palette": "swamp green, mud brown, moonshine amber, purple dusk, slime lime",
        "logo": "BAYOU BEDLAM in wobbly hand-painted cartoon letters on a crooked swamp plank sign, slime dripping, a moonshine jug on top",
        "heroes": [
            "Grumpy hillbilly granny in a rocking chair holding a frying pan",
            "Skinny swamp guy in overalls with a corncob pipe (no smoke) and a lantern",
        ],
        "hp": [
            "Three-eyed mutant catfish with whiskers",
            "Goofy alligator with a bandage and a tooth gap",
            "Purple swamp leech with big googly eyes",
            "Possum with a glowing green tail",
        ],
        "lp_style": "wobbly cartoon letters cut from swamp planks, each painted a different colour, ink outlines (rubber-hose 1930s cartoon style)",
        "wild": "Moonshine jug marked XXX glowing green, the word WILD",
        "scatter": "Swamp hut on stilts with glowing windows, the word SCATTER",
        "bonus": "Bubbling cauldron of gumbo, the word BONUS",
        "frame": "Reel frame of crooked swamp planks with ropes, hanging Spanish moss, a lantern in each corner, slime dripping, cartoon ink outlines",
        "bg_base": "Cartoon rubber-hose style bayou at night: crooked trees with Spanish moss, a wooden dock, fireflies, a rusty pickup truck, green glowing water",
        "bg_bonus": "Cartoon interior of a hillbilly swamp shack: fireplace, moonshine still, mounted mutant trophies on log walls, rocking chair, warm firelight",
        "style_override": "1930s rubber-hose cartoon style with thick ink outlines, flat bright colours and slight grain",
    },
    {
        "slug": "jaguar-eclipse",
        "name": "JAGUAR ECLIPSE",
        "ref": "obsidian-sun",
        "theme": "Mayan jungle temple of carved jade and gold animal idols, jaguar warrior heroes, solar eclipse.",
        "palette": "jungle emerald, jade, gold, turquoise, ruby red",
        "logo": "JAGUAR ECLIPSE in carved gold-and-jade Mayan-style letters with a black eclipsed sun disc and jaguar spots",
        "heroes": [
            "Jaguar warrior in a jaguar-pelt headdress holding a jade spear",
            "Mayan sun priestess with a feathered headdress and a glowing gold sun disc",
        ],
        "hp": [
            "Carved jade toucan idol with gold beak",
            "Golden axolotl figurine with turquoise inlays",
            "Red stone monkey totem mask",
            "Turquoise feathered serpent mask",
        ],
        "lp_style": "carved Mayan stone letters in jade, ruby, turquoise and gold with step-fret patterns",
        "wild": "Golden jaguar head mask with emerald eyes and the word WILD",
        "scatter": "Black obsidian eclipse sun disc with a golden corona, the word SCATTER",
        "bonus": "Ancient stone calendar wheel glowing gold, the word BONUS",
        "frame": "Reel frame of carved Mayan stone with gold step-fret borders, jungle vines and flowers, jade serpent heads on the bottom corners",
        "bg_base": "Lush tropical jungle in daylight with a stepped Mayan pyramid, waterfalls, turquoise pools, parrots, sun rays",
        "bg_bonus": "The Mayan pyramid during a total solar eclipse: dark sky with a glowing golden corona, torches on the steps, glowing jade runes, mist",
    },
    {
        "slug": "trident-vs-titan",
        "name": "TRIDENT VS TITAN",
        "ref": "clash-of-realms",
        "theme": "Greek myth duel: Poseidon of the sea against the lava Titan Kronos, Atlantis coast vs volcanic Tartarus.",
        "palette": "ocean blue, marble white, gold, lava orange, obsidian",
        "logo": "TRIDENT VS TITAN in heavy gold marble Greek-style letters, a golden trident crossing a flaming stone sickle behind VS, splashing water on the left and lava on the right",
        "heroes": [
            "Poseidon, muscular sea god with flowing white-blue hair, golden trident, water swirling around",
            "Kronos, giant lava Titan with cracked obsidian skin, glowing orange veins and a stone sickle",
        ],
        "hp": [
            "Golden trident",
            "White Pegasus head medallion",
            "Bronze Greek amphora with sea waves pattern",
            "Golden lyre",
        ],
        "lp_style": "carved marble letters with gold Greek-key borders and inlaid coloured gems (blue, green, red, purple)",
        "wild": "Poseidon portrait tile in a gold Greek frame with the word WILD",
        "scatter": "Kronos portrait tile in a lava-stone frame with the word SCATTER",
        "bonus": "Golden hourglass with lava sand, the word BONUS",
        "frame": "Reel frame of white marble columns with gold capitals, a Greek pediment on top; left side wrapped in ocean waves and shells, right side cracked with glowing lava",
        "bg_base": "Atlantis coast: white marble temples on cliffs above a turquoise sea, waterfalls, clouds, sunny sky",
        "bg_bonus": "Volcanic Tartarus: obsidian cliffs, rivers of lava, broken Greek columns, ash sky lit by orange glow, chains of the titan",
    },
]


def jobs(g: dict) -> list[dict]:
    style = g.get("style_override", STYLE)
    theme = f"Theme: {g['theme']} Palette: {g['palette']}."
    sym = (
        "Arrange the items in a neat grid with generous empty space between "
        "them, each one isolated, all in the same style and lighting, on a "
        "transparent background (if not possible, plain flat black)."
    )
    return [
        {"job": "logo", "size": "1536x1024", "prompt":
            f"Slot game logo: {g['logo']}. Isolated on a transparent background, "
            f"no other text. {theme} {style}"},
        {"job": "symbols_hp", "size": "1536x1024", "prompt":
            "Slot symbol sheet, 2 rows: top row the high-pay symbols — "
            + "; ".join(g["hp"]) + ". Bottom row the specials — WILD: "
            f"{g['wild']}; SCATTER: {g['scatter']}; BONUS: {g['bonus']}. "
            f"{sym} {theme} {style}"},
        {"job": "symbols_lp", "size": "1536x1024", "prompt":
            f"Slot low-pay symbol sheet, one row: {g['lp_style']}. "
            "If letters, exactly: 10, J, Q, K, A. "
            f"{sym} {theme} {style}"},
        {"job": "characters", "size": "1536x1024", "prompt":
            "Character line-up for the slot game, full body, side by side, "
            "consistent style: " + "; ".join(g["heroes"]) + ". "
            f"{sym} {theme} {style}"},
        {"job": "frame", "size": "1536x1024", "prompt":
            f"Slot reel frame for a 5x3 reel grid: {g['frame']}. The centre "
            "window is an empty flat dark panel (no symbols, no reels drawn); "
            "ornaments only on the corners and the middle of each side, plain "
            "repeating trim elsewhere. Transparent background outside the "
            f"frame, front view, symmetrical. {theme} {style}"},
        {"job": "bg_base", "size": "1536x1024", "prompt":
            f"Base-game background for a slot, wide 16:9 landscape, no UI, no "
            f"text, no reels: {g['bg_base']}. Keep the centre calmer for the "
            f"reels. {theme} {style}"},
        {"job": "bg_bonus", "size": "1536x1024", "prompt":
            f"Free-spins bonus background for the same slot, wide 16:9, no "
            f"UI, no text, no reels: {g['bg_bonus']}. More dramatic and "
            f"festive than the base game, centre calmer for the reels. "
            f"{theme} {style}"},
    ]


def main() -> None:
    md = [
        "# Provider 2 — 10 слотов по мотивам Cre8Pics\n",
        "Каждая игра — своя альтернатива проекту Cre8Pics: та же тематика, своё "
        "имя, свои персонажи и предметы. Арт референсов в модели не отправляется — "
        "только словесное описание. Промпты для каждой картинки лежат в "
        "`prompts.json` (их можно вставлять в ChatGPT как есть).\n",
    ]
    out = {}
    for i, g in enumerate(GAMES, 1):
        md += [
            f"\n## {i}. {g['name']}  (`{g['slug']}`)\n",
            f"Референс: https://www.cre8pics.com/project/{g['ref']}\n",
            f"- **Тема:** {g['theme']}",
            f"- **Палитра:** {g['palette']}",
            f"- **Лого:** {g['logo']}",
            "- **Герои:** " + "; ".join(g["heroes"]),
            "- **HP-символы:** " + "; ".join(g["hp"]),
            f"- **LP:** {g['lp_style']}",
            f"- **WILD:** {g['wild']}",
            f"- **SCATTER:** {g['scatter']}",
            f"- **BONUS:** {g['bonus']}",
            f"- **Рамка:** {g['frame']}",
            f"- **Фон база:** {g['bg_base']}",
            f"- **Фон бонус:** {g['bg_bonus']}",
        ]
        out[g["slug"]] = {"name": g["name"], "ref": g["ref"], "jobs": jobs(g)}
    (HERE / "CONCEPTS.md").write_text("\n".join(md) + "\n")
    (HERE / "prompts.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"{len(GAMES)} games, {sum(len(v['jobs']) for v in out.values())} jobs")


if __name__ == "__main__":
    main()
