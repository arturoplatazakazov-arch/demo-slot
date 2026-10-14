"""Provider 2 game registry: everything the asset builder, the FX generator,
the front template and the seed template need to know per game.

Symbol codes are the contract between app/seed/<slug>.py and
front/js/<slug>/slot.js. `hp` are the four high symbols (left to right on the
art sheet), `lp` the five low ones (10 J Q K A, or the five objects of the
games whose low symbols are not letters). The sheet's BONUS symbol is not a
reel symbol: it becomes the Buy Bonus button art.
"""

LETTERS = ['ten', 'jack', 'queen', 'king', 'ace']
LETTER_NAMES = ['10', 'J', 'Q', 'K', 'A']

GAMES = {
    'rad-raiders': {
        'music': 'neon-reels',
        'name': 'Rad Raiders', 'ref': 'spinout',
        'hp': ['geiger', 'gasmask', 'beans', 'radpop'],
        'hp_names': ['Geiger Counter', 'Gas Mask', 'Glow Beans', 'Rad Pop'],
        'scatter_name': 'Bunker Door', 'wild_name': 'Toxic Barrel',
        'accent': '#9dff3a', 'accent2': '#ff8a1e', 'ink': '#1b1407', 'night': '#20140a',
        'fx': 'embers', 'halo': (150, 255, 70),
        'desc': 'Атомный пустырь: бочка-вайлд на весь барабан и фриспины за бункер',
    },
    'jade-paws': {
        'music': 'east-discovery',
        'name': 'Jade Paws', 'ref': 'panda-adventures',
        'hp': ['koi', 'dumplings', 'gong', 'fan'],
        'hp_names': ['Golden Koi', 'Jade Dumplings', 'Temple Gong', 'Blossom Fan'],
        'scatter_name': 'Lotus', 'wild_name': 'Temple Bell',
        'accent': '#3fdc8c', 'accent2': '#ff5a4a', 'ink': '#0e1f14', 'night': '#0f2018',
        'fx': 'petals', 'halo': (120, 255, 170),
        'desc': 'Бамбуковая долина красной панды: колокол-вайлд и фриспины за лотос',
    },
    'ghoul-groove': {
        'music': 'neon-reels',
        'name': 'Ghoul Groove', 'ref': 'disco-potion',
        'hp': ['discoskull', 'boombox', 'potion', 'cocktail'],
        'hp_names': ['Disco Skull', 'Coffin Boombox', 'Bat Potion', 'Eyeball Cocktail'],
        'scatter_name': 'Haunted Jukebox', 'wild_name': 'Jack-o-Vinyl',
        'accent': '#c66bff', 'accent2': '#5dff7a', 'ink': '#14061f', 'night': '#12061c',
        'fx': 'disco', 'halo': (200, 110, 255),
        'desc': 'Монстр-диско в особняке: винил-вайлд и фриспины за джукбокс',
        'ui_boxes': {'big': (30, 20, 680, 430), 'mega': (730, 20, 1420, 475),
                     'epic': (20, 430, 940, 872), 'fs': (940, 490, 1430, 845),
                     'buy': (20, 885, 475, 1082), 'plate': (490, 875, 1065, 1082),
                     'yes': (1100, 890, 1272, 1078), 'no': (1272, 890, 1425, 1078)},
    },
    'gummy-gold-rush': {
        'music': 'amys-fruit-farm',
        'name': 'Gummy Gold Rush', 'ref': 'sugar-way',
        'hp': ['sheriff', 'cowgirl', 'bandit', 'minecart'],
        'hp_names': ['Gummy Sheriff', 'Marshmallow Cowgirl', 'Cookie Bandit', 'Gold Cart'],
        'lp': ['heart', 'star', 'worm', 'bonbon', 'crystal'],
        'lp_names': ['Jelly Heart', 'Candy Star', 'Gummy Worm', 'Bonbon', 'Rock Candy'],
        'scatter_name': 'Wanted Poster', 'wild_name': 'Sheriff Badge',
        'accent': '#ff5fb8', 'accent2': '#ffd23a', 'ink': '#3a1020', 'night': '#3a1a1a',
        'fx': 'sparkle', 'halo': (255, 150, 210),
        'desc': 'Конфетный Дикий Запад: значок-вайлд и фриспины за плакат WANTED',
    },
    'whisker-noir': {
        'music': 'wild-western-story',
        'name': 'Whisker Noir', 'ref': 'wild-detectives',
        'hp': ['owl', 'cat', 'raccoon', 'bulldog'],
        'hp_names': ['Owl Inspector', 'Black Cat', 'Raccoon Thief', 'Bulldog Chief'],
        'scatter_name': 'Case File', 'wild_name': 'Paw Badge',
        'accent': '#f2c14a', 'accent2': '#ff3550', 'ink': '#120a06', 'night': '#0b0d1a',
        'fx': 'rain', 'halo': (255, 90, 110),
        'desc': 'Нуар-город зверей-детективов: значок-вайлд и фриспины за досье',
    },
    'cogwork-skies': {
        'music': 'golden-caravan',
        'name': 'Cogwork Skies', 'ref': 'gearspier',
        'hp': ['airship', 'teslajar', 'pocketwatch', 'telescope'],
        'hp_names': ['Airship', 'Tesla Jar', 'Pocket Watch', 'Telescope'],
        'scatter_name': 'Steam Safe', 'wild_name': 'Master Cog',
        'accent': '#f0b24a', 'accent2': '#3fd8d0', 'ink': '#1e1206', 'night': '#1c1408',
        'fx': 'steam', 'halo': (255, 200, 110),
        'desc': 'Стимпанк-город в облаках: шестерня-вайлд и фриспины за сейф',
    },
    'hex-hollow': {
        'music': 'party-of-goods',
        'name': 'Hex Hollow', 'ref': 'witches-book',
        'hp': ['crystalball', 'spellbook', 'mandrake', 'candle'],
        'hp_names': ['Crystal Ball', 'Spellbook', 'Mandrake', 'Black Candle'],
        'lp': ['vial', 'moth', 'rune', 'mushroom', 'gem'],
        'lp_names': ['Potion Vial', 'Moth', 'Rune Stone', 'Mushroom', 'Magic Gem'],
        'scatter_name': 'Cauldron', 'wild_name': 'Hex Lantern',
        'accent': '#9dff5a', 'accent2': '#b06bff', 'ink': '#120720', 'night': '#100820',
        'fx': 'fireflies', 'halo': (150, 255, 110),
        'desc': 'Ведьмин лес: фонарь-вайлд на весь барабан и фриспины за котёл',
    },
    'bayou-bedlam': {
        'music': 'wild-western-story',
        'name': 'Bayou Bedlam', 'ref': 'toxic-swamp',
        'hp': ['catfish', 'gator', 'leech', 'possum'],
        'hp_names': ['Three-Eyed Catfish', 'Goofy Gator', 'Swamp Leech', 'Glow Possum'],
        'scatter_name': 'Swamp Hut', 'wild_name': 'Moonshine',
        'accent': '#b6e83a', 'accent2': '#ffb03a', 'ink': '#1a1408', 'night': '#141a0c',
        'fx': 'fireflies', 'halo': (190, 255, 80),
        'desc': 'Мультяшное болото: самогон-вайлд и фриспины за хижину',
        # the leech touches the possum's tail on the sheet: cut by hand (sheet px)
        'hp_boxes': [(20, 60, 430, 556), (430, 60, 790, 556), (790, 110, 1068, 556),
                     (1070, 100, 1432, 566), (60, 596, 492, 1066), (496, 596, 972, 1066),
                     (974, 596, 1424, 1066)],
    },
    'jaguar-eclipse': {
        'music': 'golden-caravan',
        'name': 'Jaguar Eclipse', 'ref': 'obsidian-sun',
        'hp': ['toucan', 'axolotl', 'monkey', 'serpent'],
        'hp_names': ['Jade Toucan', 'Golden Axolotl', 'Monkey Totem', 'Feathered Serpent'],
        'scatter_name': 'Eclipse Disc', 'wild_name': 'Jaguar Mask',
        'accent': '#f2c14a', 'accent2': '#3fdcb0', 'ink': '#0c1a10', 'night': '#0c1a10',
        'fx': 'embers', 'halo': (255, 200, 90),
        'desc': 'Храм майя: маска ягуара на весь барабан и фриспины за затмение',
    },
    'trident-vs-titan': {
        'music': 'party-of-goods',
        'name': 'Trident vs Titan', 'ref': 'clash-of-realms',
        'hp': ['trident', 'pegasus', 'amphora', 'lyre'],
        'hp_names': ['Golden Trident', 'Pegasus', 'Sea Amphora', 'Golden Lyre'],
        'scatter_name': 'Kronos', 'wild_name': 'Poseidon',
        'accent': '#ffcf5a', 'accent2': '#3fb8ff', 'ink': '#0a1424', 'night': '#0a1424',
        'fx': 'night', 'halo': (110, 200, 255),
        'desc': 'Посейдон против титана: Посейдон-вайлд и фриспины за Кроноса',
        # its UI kit banners overlap, so they are cut by hand (ui_kit.png px)
        'ui_boxes': {'big': (360, 10, 1090, 232), 'mega': (150, 228, 1300, 505),
                     'epic': (20, 505, 1420, 850), 'fs': (20, 855, 372, 1080),
                     'buy': (378, 855, 732, 1080), 'plate': (736, 862, 1242, 1062),
                     'yes': (1278, 850, 1412, 955), 'no': (1278, 955, 1412, 1078)},
    },
}

for _slug, _g in GAMES.items():
    _g.setdefault('lp', list(LETTERS))
    _g.setdefault('lp_names', list(LETTER_NAMES))
    _g['slug'] = _slug
    _g['codes'] = ['wild', 'scatter'] + _g['hp'] + _g['lp']
