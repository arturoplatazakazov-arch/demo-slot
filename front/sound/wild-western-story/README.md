# Wild Western Story — уникальные звуки

Повторяющиеся звуки берутся из `../common/` (см. `../README.md`).
Ключи — в `front/js/wild-western-story/sound.js`.

## Уже на месте

- `WIN_Small.mp3`, `WIN_Big.mp3`, `WIN_Mega.mp3`, `WIN_Epic.mp3` — 4 выигрыша
- `WILD_Scale.mp3` — звук роста / скейла wild
- Фон **базового** уровня — два слоя, играют вместе:
  - `BG_Base.mp3` — музыка
  - `BG_Base_environment.mp3` — окружение / атмосфера (звучит под музыкой)
- Фон **бонусного** уровня — два слоя, играют вместе:
  - `BG_Bonus.mp3` — музыка
  - `BG_Bonus_environment.mp3` — окружение / атмосфера

Слой `environment` опционален: убрать файл или выставить `env: null` в
`MUSIC_FILES` → фон играет одной дорожкой.

## Ещё ждём

- `SCATTER_win.mp3` — выигрыш scatter
- `WILD_Scale_wind.mp3` — длинный «бед» под выигрыш с wild (играет поверх
  `win_big`; сейчас просто молчит)
