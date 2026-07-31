# East Discovery — asset checklist

Игра по референсу присланных скринов: китайская тема, Hold'n'Win + Free Spins + Buy Bonus,
маскот — тигр-император (красная мантия в базовой игре / синяя в фриспинах).

Конвенция файлов — та же, что уже используется в `front/img/Export/` для Amy's Fruit Farm:
каждый анимированный символ = папка с 4 файлами Spine-экспорта:
`static.png`, `animation.png`, `animation.json`, `animation.atlas`.

## Корневые файлы (сюда, `front/img/east-discovery/`)

- `logo_east_discovery.png` — логотип "EAST DISCOVERY hold'n'win"
- `bg_base_game.png` — фон базовой игры (день, бамбук, сакура)
- `bg_freespins.png` — фон бонуса (ночь, фонари, та же локация)
- `Desk_base.png` / `Desk_bonus.png` — десктопные полные фоны (как в исходной игре)
- `Mob_Base_bg.png` / `Mob_Bonus_bg.png` — мобильные фоны
- `reel_frame.png` — золотая рамка барабанов (ворота пагоды)
- `reel_bg_panel.png` — тёмная подложка под символами
- `sign_buy_bonus.png` — баннер "BUY BONUS"
- `sign_freespins_counter.png` — фонарь-счётчик "FREE SPINS ###"
- `tiger_king_base.png` — маскот, красная мантия, мешок с золотом (база)
- `tiger_king_freespins.png` — маскот, синяя мантия, приветственный жест (бонус)

## `Export/<символ>/` — по 4 файла (static/animation.png/animation.json/animation.atlas) в каждой:

- `Scatter_Lantern` — красный фонарь (SCATTER)
- `Wild_Dragon` — маленький квадратный символ дракона (WILD, обычный)
- `Wild_Dragon_Big` — высокий дракон на весь барабан (уточнить у продукта: это отдельный
  декоративный элемент 3-го барабана или анимация "разворота" wild — можно переиспользовать
  логику expanding_wild, которую уже сделали для Amy's Fruit Farm)
- `Koi_Fish` — два кои на синем фоне
- `Fan_Green`, `Fan_Red`, `Fan_Blue`, `Fan_Pink` — веера с иероглифом 福, 4 цвета
  (если по факту это один символ с 4 расцветками под разные тиры — скажи, объединим в одну папку)
- `Tiger_King_Card` — портрет тигра-императора (символ в сетке, премиум-тир)
- `Scroll` — свиток с красной лентой
- `Lucky_Cat` — манэки-нэко (белый кот с поднятой лапой)
- `Coin_HoldWin` — монета Hold'n'Win с "财运" + множителем. На скрине виден только "1000X" —
  движок уже поддерживает Hold & Win с тирами 1x/2x/5x/10x/grand по умолчанию, так что
  минимум нужно 5 вариантов лица монеты под эти значения (текст на монете можно оставить
  реальными числами вместо "1x" и т.п.); если хочешь больше промежуточных тиров — скажи, поправим.

## `Popup's/<тип>/` — по образцу существующих поп-апов темы:

- `Big_win`, `Mega_Win`, `Epic_Win` — баннеры выигрыша разных уровней
- `bonus_spins_win`, `bonus_spins_total_win` — поп-апы во время/по итогу фриспинов
- `buy_free_spins` — поп-ап подтверждения покупки бонуса

## Звук

Схема и имена файлов — в `front/sound/README.md`. Кратко: повторяющиеся звуки
(клики, попапы, старт/стоп барабанов, anticipation) общие для всех игр и лежат
в `front/sound/common/`. Уникальные звуки этой игры — в
`front/sound/east-discovery/`: `WIN_Small/Big/Mega/Epic.wav`, `BG_Base.mp3`,
`BG_Bonus.mp3`, `SCATTER_win.mp3`, `WILD_Scale.wav`, `WILD_Scale_wind.wav`,
`HOLD&WIN_Coin.wav`. Все уже на месте.

## Что дальше

Как только файлы появятся — заведу под эту игру новый seed-конфиг в `app/seed/` (переиспользуя
уже готовые в движке модули Hold & Win, Free Spins и Bonus Buy — писать новую механику не
придётся) и подключу верстку.
