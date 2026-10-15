"""Provider 3 game registry (same contract as provider2/games.py; the
provider2 tools read it with P_SET=provider3). Only games whose art set is
complete are listed — fjord-fortune, mythic-vault and spartan-spoils join
once ChatGPT draws their missing images.
"""

LETTERS = ['ten', 'jack', 'queen', 'king', 'ace']
LETTER_NAMES = ['10', 'J', 'Q', 'K', 'A']


def g(name, ref, hp, hp_names, scatter, wild, accent, accent2, ink, night, fx, halo, music, desc, **kw):
    d = dict(name=name, ref=ref, hp=hp, hp_names=hp_names, scatter_name=scatter, wild_name=wild,
             accent=accent, accent2=accent2, ink=ink, night=night, fx=fx, halo=halo, music=music, desc=desc)
    d.update(kw)
    return d


GAMES = {
    'gladiator-gig': g('Gladiator Gig', 'rome-n-roll', ['guitar', 'helmet', 'wreath', 'setlist'],
                       ['Golden Lyre-Guitar', 'Rock Helmet', 'Gold Wreath', 'Setlist Scroll'], 'Concert Ticket', 'Rock Hand',
                       '#f2c14a', '#b06bff', '#1a0a26', '#160822', 'disco', (200, 120, 255), 'party-of-goods',
                       'Рок-концерт в Колизее: вайлд на весь барабан и фриспины за билет'),
    'pyramid-pals': g('Pyramid Pals', 'spin-hoter', ['block', 'ankh', 'blueprint', 'jug'],
                      ['Stone Block', 'Golden Ankh', 'Blueprint', 'Water Jug'], 'Eye of Horus', 'Golden Capstone',
                      '#f2c14a', '#3fd8d0', '#2a1606', '#2a1a08', 'embers', (255, 210, 120), 'golden-caravan',
                      'Стройка пирамиды: вершина-вайлд и фриспины за Око Гора'),
    'piggy-bankers': g('Piggy Bankers', 'penny-wenny', ['piggy', 'goldbars', 'keys', 'banknotes'],
                       ['Golden Piggy', 'Gold Bars', 'Vault Keys', 'Banknotes'], 'Vault Door', 'Golden Key',
                       '#f2c14a', '#3fdc8c', '#1e1206', '#1e1408', 'sparkle', (255, 210, 110), 'wild-western-story',
                       'Старый банк: ключ-вайлд и фриспины за дверь хранилища'),
    'grit-and-gold': g('Grit & Gold', 'dust-lust', ['revolver', 'whiskey', 'nuggets', 'wanted'],
                       ['Revolver & Cards', 'Whiskey', 'Gold Pouch', 'Wanted Poster'], 'Money Sack', 'Sheriff Star',
                       '#e0b060', '#c8322a', '#1e140a', '#1c140c', 'embers', (255, 190, 110), 'wild-western-story',
                       'Город-призрак Дикого Запада: звезда-вайлд и фриспины за мешок денег'),
    'barnyard-bonanza': g('Barnyard Bonanza', 'country-spins', ['pig', 'rooster', 'bull', 'sheep'],
                          ['Pig', 'Rooster', 'Bull', 'Sheep'], 'Red Barn', 'Golden Horseshoe',
                          '#ffc23a', '#d93a2a', '#2a1a0a', '#24180a', 'petals', (255, 220, 120), 'amys-fruit-farm',
                          'Весёлая ферма: подкова-вайлд и фриспины за амбар',
                          lp=['tomato', 'carrot', 'eggplant', 'pepper', 'cabbage'],
                          lp_names=['Tomato', 'Carrot', 'Eggplant', 'Pepper', 'Cabbage']),
    'stone-age-stash': g('Stone Age Stash', 'frosty-brosty', ['sabretooth', 'mammoth', 'dodo', 'meat'],
                         ['Sabre-Tooth', 'Mammoth', 'Dodo', 'Roast Meat'], 'Dino Egg', 'Frozen Amber',
                         '#8fd8ff', '#ff9a3c', '#0e1a26', '#0c1622', 'night', (150, 220, 255), 'east-discovery',
                         'Ледниковый период: янтарь-вайлд и фриспины за яйцо динозавра'),
    'tnt-tunnels': g('TNT Tunnels', 'dig-dig-boom', ['minecart', 'pickaxe', 'lantern', 'gloves'],
                     ['Mine Cart', 'Pickaxe', 'Lantern', 'Gloves'], 'Miner Badge', 'TNT Box',
                     '#ffb43a', '#e0402a', '#1a1208', '#16100a', 'embers', (255, 180, 80), 'golden-caravan',
                     'Золотая шахта: ящик TNT на весь барабан и фриспины за жетон шахтёра'),
    'vault-runners': g('Vault Runners', 'diamond-dash', ['goldbars', 'cash', 'safe', 'diamond'],
                       ['Gold Bars', 'Cash', 'Red Safe', 'Blue Diamond'], 'Keycard', 'Time Bomb',
                       '#ffc84a', '#b46bff', '#0c0c22', '#0a0a1e', 'disco', (160, 120, 255), 'neon-reels',
                       'Ограбление банка: бомба-вайлд и фриспины за ключ-карту'),
    'big-top-bonkers': g('Big Top Bonkers', 'hong-bonk', ['elephant', 'seal', 'cannon', 'tophat'],
                         ['Elephant', 'Seal', 'Cannon', 'Magic Hat'], 'Circus Ticket', 'Circus Tent',
                         '#f2c14a', '#d9302a', '#24140a', '#20120a', 'sparkle', (255, 200, 120), 'party-of-goods',
                         'Ретро-цирк: шатёр-вайлд и фриспины за билет'),
    'parrot-plunder': g('Parrot Plunder', 'curse-of-the-black-wave', ['piratehat', 'map', 'rum', 'compass'],
                        ['Pirate Hat', 'Treasure Map', 'Rum', 'Compass'], 'Treasure Chest', 'Skull & Swords',
                        '#f2c14a', '#3fd8d0', '#1a1008', '#0e1a20', 'night', (255, 210, 120), 'east-discovery',
                        'Пиратский остров: череп-вайлд и фриспины за сундук'),
    'skull-harbor': g('Skull Harbor', 'hidden-havens', ['lantern', 'chest', 'compass', 'rum'],
                      ['Lantern', 'Treasure Chest', 'Compass', 'Skull Rum'], 'Mermaid Pearl', 'Skull Captain',
                      '#f2c14a', '#3fdcc8', '#0a1a18', '#08161a', 'fireflies', (120, 255, 220), 'east-discovery',
                      'Бухта призраков: череп-вайлд и фриспины за жемчужину'),
    'sugar-rush-dj': g('Sugar Rush DJ', 'candy-beats', ['lollipop', 'cupcake', 'icepop', 'cottoncandy'],
                       ['Lollipop', 'Cupcake', 'Ice Pop', 'Cotton Candy'], 'Disco Ball', 'Candy Vinyl',
                       '#ff5fb8', '#3fd8ff', '#2a0a2a', '#22082a', 'disco', (255, 130, 220), 'neon-reels',
                       'Конфетный фестиваль: винил-вайлд и фриспины за диско-шар',
                       lp=['heart', 'star', 'bean', 'choco', 'gumdrop'],
                       lp_names=['Jelly Heart', 'Star Candy', 'Jelly Bean', 'Chocolate', 'Gumdrop']),
    'pup-fishermen': g('Pup Fishermen', 'fluffy-catch', ['goldfish', 'lifebuoy', 'rod', 'tackle'],
                       ['Golden Fish', 'Lifebuoy', 'Fishing Rod', 'Tackle Box'], 'Fish Trophy', 'Golden Anchor',
                       '#ffc84a', '#3fa8ff', '#0a1a2a', '#0a1826', 'rain', (130, 200, 255), 'east-discovery',
                       'Псы-рыбаки: якорь-вайлд и фриспины за трофей'),
    'pharaoh-hippo': g('Pharaoh Hippo', 'croco-nile', ['scarab', 'lotus', 'chest', 'book'],
                       ['Golden Scarab', 'Lotus Pot', 'Treasure Chest', 'Hieroglyph Book'], 'Golden Pyramid', 'Hippo Mask',
                       '#f2c14a', '#3fd8d0', '#10142a', '#0e1226', 'night', (255, 210, 120), 'golden-caravan',
                       'Бегемот-фараон: маска-вайлд и фриспины за пирамиду'),
    'bison-thunder': g('Bison Thunder', 'buffalo-force', ['wolf', 'eagle', 'bear', 'cougar'],
                       ['Grey Wolf', 'Bald Eagle', 'Grizzly', 'Mountain Lion'], 'Sunset Coin', 'Golden Bison',
                       '#f2b04a', '#ff6a3a', '#1e0e0a', '#1c0e0c', 'embers', (255, 170, 90), 'wild-western-story',
                       'Каньон бизонов: бизон-вайлд и фриспины за монету заката'),
    'evolve-rush': g('Evolve Rush', 'evolution', ['fossil', 'amber', 'plant', 'mushroom'],
                     ['Fossil Shell', 'Amber', 'Carnivorous Plant', 'Giant Mushroom'], 'Mystic Egg', 'Meteor Rock',
                     '#9dff5a', '#ff8a3a', '#0c1a10', '#0c180e', 'fireflies', (150, 255, 120), 'neon-reels',
                     'Доисторические джунгли: метеорит-вайлд и фриспины за яйцо'),
    'cash-kingpin': g('Cash Kingpin', 'lucky-boss', ['briefcase', 'whiskey', 'ring', 'cash'],
                      ['Gold Briefcase', 'Whiskey', 'Diamond Ring', 'Cash Stack'], 'Vintage Car', 'Gold Dollar',
                      '#f2c14a', '#ff4fb8', '#1a0a22', '#16081e', 'disco', (255, 120, 210), 'neon-reels',
                      'Мафиозный босс: доллар-вайлд и фриспины за машину'),
}

for _slug, _g in GAMES.items():
    _g.setdefault('lp', list(LETTERS))
    _g.setdefault('lp_names', list(LETTER_NAMES))
    _g['slug'] = _slug
    _g['codes'] = ['wild', 'scatter'] + _g['hp'] + _g['lp']

# UI-kit crops (ui_kit.png px, 1448x1086), measured by hand: ChatGPT lays the
# kits out differently every time and neighbours touch, so the auto cut mixes
# them up. evolve-rush's kit has no FREE SPINS banner (code-drawn fallback).
UI_BOXES = {
    'gladiator-gig': dict(big=(125, 40, 600, 340), mega=(720, 20, 1430, 360), epic=(30, 340, 1320, 680), fs=(40, 690, 680, 880),
                          buy=(700, 700, 1380, 900), plate=(100, 905, 920, 1065), yes=(950, 900, 1130, 1065), no=(1135, 900, 1320, 1065)),
    'pyramid-pals': dict(big=(48, 95, 686, 362), mega=(695, 76, 1419, 362), epic=(48, 352, 1410, 733), fs=(38, 752, 638, 933),
                         buy=(714, 762, 1333, 914), plate=(38, 933, 914, 1067), yes=(1038, 933, 1200, 1067), no=(1229, 933, 1400, 1067)),
    'piggy-bankers': dict(big=(57, 57, 648, 352), mega=(686, 38, 1400, 362), epic=(210, 391, 1314, 714), fs=(29, 771, 486, 1029),
                          buy=(505, 800, 810, 1029), plate=(838, 819, 1276, 1019), yes=(1295, 724, 1419, 857), no=(1295, 895, 1419, 1029)),
    'grit-and-gold': dict(big=(29, 76, 667, 381), mega=(686, 38, 1429, 400), epic=(38, 381, 905, 838), fs=(933, 419, 1429, 819),
                          buy=(19, 867, 514, 1019), plate=(533, 848, 1029, 1019), yes=(1038, 876, 1210, 1019), no=(1229, 876, 1400, 1019)),
    'barnyard-bonanza': dict(big=(19, 219, 400, 533), mega=(419, 162, 886, 533), epic=(895, 38, 1429, 552), fs=(19, 552, 429, 867),
                             buy=(486, 552, 848, 857), plate=(857, 600, 1419, 848), yes=(476, 867, 676, 1038), no=(762, 867, 962, 1038)),
    'stone-age-stash': dict(big=(48, 57, 648, 381), mega=(667, 19, 1438, 381), epic=(86, 391, 1362, 781), fs=(48, 790, 476, 1029),
                            buy=(495, 819, 924, 1019), plate=(933, 790, 1419, 914), yes=(1010, 924, 1172, 1057), no=(1181, 924, 1343, 1057)),
    'tnt-tunnels': dict(big=(57, 38, 648, 381), mega=(667, 57, 1419, 391), epic=(200, 410, 1248, 791), fs=(29, 791, 467, 1029),
                        buy=(476, 791, 810, 1038), plate=(810, 791, 1257, 1029), yes=(1267, 734, 1429, 886), no=(1267, 905, 1429, 1048)),
    'vault-runners': dict(big=(48, 57, 629, 391), mega=(629, 38, 1419, 410), epic=(333, 391, 1305, 772), fs=(38, 724, 610, 943),
                          buy=(905, 753, 1438, 914), plate=(19, 934, 972, 1067), yes=(1038, 924, 1210, 1067), no=(1219, 924, 1400, 1067)),
    'big-top-bonkers': dict(big=(38, 29, 676, 305), mega=(714, 29, 1429, 305), epic=(143, 314, 1305, 676), fs=(38, 676, 724, 886),
                            buy=(829, 705, 1419, 886), plate=(76, 895, 952, 1048), yes=(1038, 914, 1200, 1048), no=(1238, 914, 1410, 1048)),
    'parrot-plunder': dict(big=(38, 29, 667, 352), mega=(724, 19, 1438, 362), epic=(76, 343, 1352, 752), fs=(19, 752, 476, 1038),
                           buy=(571, 743, 933, 905), plate=(476, 914, 1029, 1057), yes=(1029, 819, 1229, 1038), no=(1238, 819, 1429, 1038)),
    'skull-harbor': dict(big=(95, 57, 629, 448), mega=(657, 38, 1419, 448), epic=(48, 429, 867, 848), fs=(895, 514, 1419, 829),
                         buy=(29, 876, 467, 1038), plate=(495, 876, 1057, 1048), yes=(1067, 886, 1238, 1029), no=(1248, 886, 1419, 1029)),
    'sugar-rush-dj': dict(big=(76, 29, 638, 419), mega=(667, 19, 1410, 419), epic=(38, 400, 838, 857), fs=(838, 467, 1419, 848),
                          buy=(29, 876, 438, 1048), plate=(438, 857, 1010, 1048), yes=(1019, 867, 1210, 1048), no=(1219, 867, 1410, 1048)),
    'pup-fishermen': dict(big=(67, 76, 629, 381), mega=(705, 67, 1419, 381), epic=(57, 381, 1372, 800), fs=(57, 829, 419, 1019),
                          buy=(457, 857, 752, 1010), plate=(752, 867, 1133, 1000), yes=(1143, 867, 1286, 1000), no=(1286, 867, 1429, 1000)),
    'pharaoh-hippo': dict(big=(57, 29, 676, 400), mega=(695, 29, 1419, 419), epic=(38, 429, 914, 838), fs=(914, 467, 1429, 800),
                          buy=(29, 867, 429, 1057), plate=(486, 867, 1000, 1048), yes=(1038, 867, 1210, 1038), no=(1238, 867, 1410, 1038)),
    'bison-thunder': dict(big=(67, 29, 676, 295), mega=(714, 10, 1429, 295), epic=(57, 286, 1381, 667), fs=(57, 667, 800, 876),
                          buy=(819, 676, 1410, 867), plate=(48, 886, 933, 1038), yes=(1019, 886, 1210, 1038), no=(1229, 886, 1419, 1038)),
    'evolve-rush': dict(big=(191, 10, 752, 238), buy=(905, 19, 1391, 333), mega=(48, 238, 914, 514), yes=(1133, 371, 1333, 552),
                        epic=(95, 533, 1095, 886), no=(1133, 629, 1333, 829), plate=(152, 886, 1391, 1048)),
    'cash-kingpin': dict(big=(38, 105, 657, 429), mega=(657, 29, 1429, 448), epic=(29, 429, 886, 838), fs=(886, 467, 1419, 838),
                         buy=(29, 867, 524, 1038), plate=(533, 857, 1029, 1048), yes=(1048, 867, 1229, 1038), no=(1238, 867, 1419, 1038)),
}
for _slug, _b in UI_BOXES.items():
    GAMES[_slug]['ui_boxes'] = _b

# the wild and scatter splashes touch on Pup Fishermen's sheet: hand boxes
GAMES['pup-fishermen']['hp_boxes'] = [(40, 70, 395, 480), (400, 120, 745, 480), (740, 70, 1070, 480),
                                      (1075, 115, 1430, 500), (30, 510, 512, 1015), (528, 520, 935, 1020),
                                      (965, 515, 1425, 1015)]
