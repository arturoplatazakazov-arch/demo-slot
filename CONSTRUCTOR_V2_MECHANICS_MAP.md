# Конструктор v2 — карта механик и зависимостей

> Read-only аудит текущего кода (6 игр + движок). Цель — найти границы модулей
> для перехода от «копия slot.js под игру» к «сборка слота из модулей».
> Текущий проект этим документом не меняется.

## Главный вывод

- **Бек уже модульный.** `app/features/registry.py` + `BonusFeature` (base.py):
  каждая механика — плагин, сама описывает параметры через `get_config_schema()`,
  движок собирает включённые из строк `FeatureConfig` через реестр. Добавить
  механику = зарегистрировать новый модуль.
- **Фронт НЕ модульный.** Каждый `front/js/<game>/slot.js` — копия донора с
  правками. Механики присутствуют как неформальные списки «kept/dropped» в
  комментариях, а не как подключаемые модули.

Значит основная работа v2 — **построить зеркальный фронт-реестр модулей** и
композиционный слой, читающий манифест.

## Reel-базы

| База | Reel-движок (бек) | Reel-рендер (фронт, кластер функций) | Игры-примеры |
|---|---|---|---|
| **5×3 lines** | `reels.py` + `wins.py` | `setCellSymbol`, `startReelLoop`/`stopReelLoop`, `landReel`, `settleColumnCells`, `landReels`, `playMultiLineWinSequence`, `buildWinGroups`, `playWinCells`, `playWinAnimationOnce` | amys (root), neon-reels, wild-western, east-discovery |
| **6×5 avalanche** | `avalanche.py` | `renderInitialGrid`, `spinStartTransition`, `playSymbolClipOnce`, `collectStepRemovals`, `celebrateStep`, `fadeOutRemoved`, `dropAndRefillStep`/`dropAndRefillColumn`, `playCascadeStep`, `playAvalanche`, `showCascadeBanner`, `updateMultiCounter` | sugar-galaxy, party-of-goods, golden-caravan |
| **3×3 simple** | тот же line-pay | — | *примера ещё нет* |

## Общий скелет (во ВСЕХ 7 файлах — кандидат в ядро рантайма)

Загрузка/ресурсы: `loadSpineResource`, `getSymbolResource`, `applyStaticContentOffset`,
`clipName`, `wait`, `randomSymbolCode`.
Сетка: `createCellNode`, `buildReelGrid`, `teardownCellInstances`, `previewSymbolWin`,
`setCellDimmed`/`setCellActive`.
Экраны/режимы: `pushScreenDim`/`popScreenDim`/`withScreenDim`, `applyModeScreen`,
`enterBonusTransition`, `setFreeSpinsMode`.
Попапы: `worldToScreen`, `startPopupAmountTracking`/`stopPopupAmountTracking`,
`playPopupSequence`, `playPopup`.
Вьюпорт/фон: `isMobileLayout`, `updateStageScale`/`updateReelScale`, `bgSrcFor`,
`updateBgForLayout`/`setBackground`, `handleResize`, `setupDevPanel`, `init`.

`spine-engine.js` и `reel-math.js` (js-root) уже game-agnostic — часть ядра.

## Механики-добавки → фронт-кластеры → бек-модуль

Каждая строка = один будущий фронт-модуль (пара к бек-модулю).

| Механика | Фронт-функции (кластер) | В каких играх | Бек-модуль | Базы |
|---|---|---|---|---|
| **Bombs** (аваланч) | `getBombFlashResource`, `getBoomBombResource`, `playBombExplosion`, `playFlashOverlay` | sugar, party, golden | inline в `avalanche.py` | 6×5 |
| **Множители-токены** | `flyTokenToBadge`, `getBoomStdResource`, token-логика в `celebrateStep` | sugar, golden | inline в `avalanche.py` | 6×5 |
| **Scatter / anticipation** | `revealScatterLandings`, `playScatterTriggerCelebration`, `isAnticipating` в `landReel` | sugar, party, golden, west, east | в `wins.py`/движке | все |
| **Expanding / big wild** | `computeWildSmallBoundsOverride`, `revealExpandedWild`, `maybeRevealExpandedWild`, `celebrateExpandedWild`, `previewBigWild`, `playBigWildWinLoop`, `maybeCelebrateBigWildWin` | wild-western, east | `expanding_wild.py` | 5×3 |
| **Coin multiplier** | `ensureCoinMultiplierTrackingLoop`, `stopCoinMultiplierTracking`, `showCoinMultiplierLabel`, `maybeShowCoinMultiplierLabels`, `playCoinMultiplierReveal` | neon, east | `coin_multiplier.py` | 5×3 |
| **Collector** | `playCollectorTigerWinIfApplied` | east | (часть coin_multiplier) | 5×3 |
| **Hold & Win** | `randomHoldAndWinFillerCode`, `buildHoldAndWinGrid`, `landHoldAndWinRespin`, `enterHoldAndWinWaitingState`, `runHoldAndWinSequence` | east | `hold_and_win.py` | 5×3, 3×3 |
| **Free spins** | `setFreeSpinsMode` (+ режимные ветки) | amys, west, east, аваланч-игры | `free_spins.py` | 5×3, 6×5 |
| **Bonus buy** | UI-кнопка + ветка в `init`/spin | несколько | `bonus_buy.py` | 5×3, 6×5 |
| **Hero character** | `setupCharacter` | amys, east | — (декор) | все |
| **Ambient environment** | `setupEnvironment` | east | — (декор) | все |
| **Sticky wild** | — (нет) | — | — (нет) | 5×3 |
| **Gamble / Jackpot** | — (нет фронта) | — | `gamble.py`, `jackpot.py` | все |

## Пропорция

Ориентировочно на каждый `slot.js`: **~70% общий скелет, ~15% база (линии/аваланч),
~15% add-on-механики**. Дублирование скелета — основной источник «пишем фронт под
игру каждый раз».

## Предлагаемые границы модулей (что извлекать)

```
front/js/
  core/            ← общий скелет (ресурсы, сетка, экраны, попапы, вьюпорт, init)
  bases/
    lines.js       ← 5×3/3×3 reel-motion + win-sequencing
    avalanche.js   ← 6×5 каскад
  mechanics/       ← ЗЕРКАЛО app/features/, по модулю на механику
    scatter.js  free_spins.js  bonus_buy.js  expanding_wild.js
    coin_multiplier.js  hold_and_win.js  bombs.js  multiplier_tokens.js
    sticky_wild.js (новый)  gamble.js (новый)  jackpot.js (новый)
  registry.js      ← как app/features/registry.py: манифест → включённые модули
```

Манифест игры: `{ base, mechanics: [...], params: {...per-mechanic...}, layout, art }`.
Рантайм `play.html` читает манифест → core + выбранная база + хореография
включённых mechanics. Новая игра знакомого набора = 0 строк фронта.

## Пилот (первый перенос)

Аваланч-семья (sugar/party/golden — фактически один движок с разным набором
bombs/токенов) — самый чистый первый кандидат: извлечь `core` + `bases/avalanche`
+ `mechanics/bombs` + `mechanics/multiplier_tokens`, собрать одну из трёх игр
через конструктор, сверить пиксель-в-пиксель с эталоном.
