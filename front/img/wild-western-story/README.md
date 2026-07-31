# Wild Western Story — asset checklist

Механика как у East Discovery, **но без монет (coin multiplier) и без Hold & Win**.
Остаётся: барабаны 3x5 с линиями, expanding wild, free spins (scatter-триггер),
buy bonus. Тема — Дикий Запад (ковбои, салун, пустыня, каньоны).

Конвенция файлов — та же, что у East Discovery / Amy's Fruit Farm:
каждый анимированный символ = папка со Spine-экспортом из 4 файлов:
`static.png`, `animation.png`, `animation.json`, `animation.atlas`.

## Корневые файлы (сюда, `front/img/wild-western-story/img/`)

- `logo_wild_western_story.png` — логотип игры
- `bg-base-desk.png` / `bg-base-mob.jpg` — фон базовой игры (десктоп / моб)
- `bg-bonus-desk.jpg` / `bg-bonus-mob.jpg` — фон фриспинов (десктоп / моб)
- `frame.png` — рамка барабанов
- `reel_bg_panel.png` — подложка под символами (если отдельная)
- `buy-bonus-button.png` — кнопка/баннер "BUY BONUS"
- `free-spins-counter.png` — счётчик фриспинов
- `hero_base.png` / `hero_bonus.png` — маскот в базе / в бонусе

## `Export/<символ>/` — по 4 файла Spine (static/animation.png/animation.json/animation.atlas)

Символы (уточним точный набор и тиры под ваши материалы):
- `Scatter` — триггер фриспинов
- `Wild` — обычный wild
- `Wild_Big` / expanding — растягивающийся wild (переиспользуем логику expanding_wild)
- Премиум-символы (напр. `Sheriff`, `Cowboy`, `Bandit`, `Cowgirl`)
- Младшие символы (напр. `Revolver`, `Horseshoe`, `Whiskey`, `Card`, картомасти A/K/Q/J)

## `Popup's/<тип>/` — баннеры

- `popup-bigwin`, `popup-megawin`, `popup-epicwin`
- `popup-bonusspinswin`, `popup-bonusspinswintotalwin`
- `popup-buybonusspins`

## Звук

Схема и имена файлов — в `front/sound/README.md`. Повторяющиеся звуки (клики,
попапы, старт/стоп барабанов, anticipation) общие и лежат в
`front/sound/common/`. Уникальные звуки этой игры кладутся в
`front/sound/wild-western-story/` (список — в
`front/sound/wild-western-story/README.md`): `WIN_Small/Big/Mega/Epic.mp3`,
`BG_Base.mp3`, `BG_Bonus.mp3`, `SCATTER_win.mp3`, `WILD_Scale.wav`,
`WILD_Scale_wind.wav`. Пока не доставлены.

## Статус фронтенда (собран на загруженных материалах)

Готово и подключено: `front/wild-western-story.html`, `css/wild-western-story.css`,
`js/wild-western-story/{sound,slot,app}.js`, карточка в `games.html`. Барабаны 3×5,
режимы база/бонус (смена фона), антисипация скаттера, попапы, счётчик фриспинов,
знак Buy Bonus, инфо-пейтейбл. Проверено в браузере (desktop 1920): база, бонус,
попап Big Win с корректным позиционированием суммы.

Правка ассетов при сборке: во **всех 14** `.atlas` первая строка ссылалась на
исходное имя текстуры (`BIG WIN.png`, `A.png`, `Layer 3.png`…), а сам PNG назван
`animation.png` — из-за этого Spine-анимации не грузились. Исправлено на
`animation.png` во всех атласах (конвенция как в East Discovery). Если будете
перезаливать эти папки — проверьте, чтобы первая строка `.atlas` совпадала с
именем PNG.

## Подключено во второй итерации

- **Рама** `img/Frame.png` — подставлена вместо CSS-плейсхолдера; сетка посажена в
  измеренное прозрачное «окно» рамы.
- **Символ WILD** `Export/wild/` — подключён. При заливке пришлось: переименовать
  `animation.atlas.txt` → `animation.atlas` и поправить в нём ссылку `wild.png` →
  `animation.png`; статика малого варианта — `static-small.png`, размер ячейки берётся
  по слоту `wild_small`. Есть большой reel-height вариант (`idle_big/win_big/move`) —
  расширяющийся wild-оверлей ещё не дописан (заглушка `celebrateExpandedWild`).
- **Декор окружения** — расставлена **статика** (`skull_bone`, `light`, `hat`,
  `cactus_1/2`) вокруг рамы.
- **Buy Bonus** перенесён вправо от слота (десктоп); на мобиле — по центру снизу.

## Ещё нужно от вас (пропуски)

- **Анимация окружения** — `Export/enviroment/{cactus,light,logo}/` содержат только
  `.json`-скелеты **без** `.atlas` и `.png`-текстуры, поэтому через движок не
  анимируются (стоит статика). Нужен полный Spine-экспорт (json + atlas + png) для
  мерцающего фонаря / покачивающихся кактусов / анимированного лого.
- **Звук** — уникальные звуки в `front/sound/wild-western-story/` ещё не
  доставлены (только README со списком ожидаемых файлов); общие звуки из
  `front/sound/common/` уже подключены. Игра идёт с общими SFX, но без
  тематических win/музыки.
- Мелочь: на арт-табличке `Buy-bonus-button.png` текст «**Bu** Bonus» (обрезано «Buy»).
- Если у вас в браузере scatter/символы «не отображались» — это старый атлас в HTTP-кэше;
  жёсткий рефреш (Cmd+Shift+R) подхватит исправленные файлы.

## Что дальше

Как только файлы появятся — заведу seed-конфиг `app/seed/wild_western_story.py`
(переиспользуя готовые модули expanding_wild / free_spins / bonus_buy — coin_multiplier
и hold_and_win НЕ подключаем), верстку `front/wild-western-story.html`, фронтовые скрипты
в `front/js/wild-western-story/` и тесты `tests/test_api_spin_wild_western_story.py` /
`tests/test_api_feature_buy_wild_western_story.py`.
