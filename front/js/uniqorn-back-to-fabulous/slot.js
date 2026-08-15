// Uniqorn Back to Fabulous — хеллоуин-слот про ведьму и проклятого единорога.
//
// Механика взята у ../neon-reels (5x3 line pay, скаттерные фриспины, множитель
// на символе-эссенции), а весь способ РИСОВАНИЯ — у ../mr-president-unicorn:
// арт здесь целиком AI-generated PNG, скелетов/атласов/клипов нет нигде, и всё,
// что в neon-reels анимировал Spine, тут делают DOM+CSS:
//
//   idle / win / landing символа   -> классы на .reel__cell (см. стиль темы)
//   линии выигрыша (11 клипов)     -> SVG-полилиния по выигравшим ячейкам
//   значение множителя на монете   -> .coin-value внутри ячейки (без bone-трекинга)
//   попапы (6 скелетов)            -> buildPopupNode(), DOM-плашка + текст
//
// Отличие от mr-president-unicorn: там расширяющийся вайлд, здесь — обычный
// подставляющийся, зато есть эссенция-множитель (coin_multiplier), поэтому
// весь блок big-wild выброшен, а вместо него — метки множителя ниже.

const ASSET_ROOT = 'img/uniqorn-back-to-fabulous';

const SYMBOL_CODES = ['wild', 'scatter', 'essence', 'cauldron', 'book', 'ball', 'hat', 'a', 'k', 'q', 'j'];

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}

// --- Hero moods -------------------------------------------------------------
//
// Единорог-ведьма сбоку от барабанов: три позы, у каждой свой PNG и свой
// CSS-луп. Все три вырезаны ОДНИМ общим bbox'ом (объединение трёх), поэтому
// смена src не заставляет героиню прыгать или менять размер. Персонаж именно
// единорог (рог сквозь шляпу, радужная грива) — это бренд игры, а не просто
// ведьма.
//
//   idle    колдует, представляет барабаны   по умолчанию
//   tense   сжалась, затаила дыхание         пока идёт антиципация скаттера
//   cheer   празднует, руки вверх            пока выплачивается выигрыш
const HERO_SRC = {
  idle: `${ASSET_ROOT}/img/hero.png`,
  tense: `${ASSET_ROOT}/img/hero_tense.png`,
  cheer: `${ASSET_ROOT}/img/hero_cheer.png`,
};
let heroMood = 'idle';

function setHeroMood(mood) {
  if (mood === heroMood) return;
  const el = document.querySelector('.hero');
  if (!el) return;
  heroMood = mood;
  el.src = HERO_SRC[mood] || HERO_SRC.idle;
  el.classList.remove('is-idle', 'is-tense', 'is-cheer');
  el.classList.add(`is-${mood}`);
}

// Коды, которыми можно засыпать барабан во время прокрутки — без скаттера
// (символ-триггер, не должен мелькать в размытии) и без эссенции (она приезжает
// со своим значением множителя, филлер бы показывал её пустой).
const FILLER_CODES = SYMBOL_CODES.filter((c) => c !== 'scatter' && c !== 'essence');

// wild, scatter и эссенция «дышат» на поле постоянно; остальные стоят смирно до
// выигрыша. Чистый CSS-класс — см. .reel__cell.is-special в стилях.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild', 'essence']);

// Длительность одного win-пульса, синхронно с CSS-кейфреймами. Оба конца наши,
// поэтому числа просто обязаны совпадать.
const WIN_PULSE_MS = 620;
const LAND_BOUNCE_MS = 260;
// Длительности входа/выхода попапа — должны совпадать с переходами .game-popup.
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;

// Раскладка attract-режима до первого реального спина (она же фиксирует форму
// сетки 3 ряда x 5 барабанов).
const SYMBOL_LAYOUT = [
  ['scatter', 'cauldron', 'q', 'a', 'j'],
  ['a', 'k', 'wild', 'essence', 'q'],
  ['q', 'ball', 'k', 'j', 'book'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

// Попапы собираются в DOM (см. buildPopupNode): сгенерированная плашка, тайтл и
// сумма. `sub` — мелкая строка над тайтлом.
//
// `plate` выбирает одну из трёх плашек, и это намеренная лестница — каждый тир
// заметно наряднее предыдущего, так что попап сам сообщает величину выигрыша
// раньше, чем игрок прочитает число:
//
//   plate   арт                                                    где
//   base    золотой картуш с филигранью и зелёным огнём            big win, free spins, buy
//   mega    + корона, лавры, самоцветы, дождь монет, фейерверк      mega win, total win
//   epic    медальон с горгульями, драпировка, полный залп          epic win
//
// Пустая панель у каждой плашки своя (у epic вообще круглая), поэтому её
// границы заданы отдельно на каждую плашку в стилях, а текст ужимается в неё
// в рантайме — см. fitPopupText.
const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN', tone: 'gold', plate: 'base' },
  megaWin: { title: 'MEGA WIN', tone: 'gold', plate: 'mega' },
  epicWin: { title: 'EPIC WIN', tone: 'red', plate: 'epic' },
  bonusSpinsWin: { title: 'FREE SPINS', sub: 'YOU WON', tone: 'blue', plate: 'base', amountSuffix: ' SPINS' },
  bonusSpinsTotalWin: { title: 'TOTAL WIN', sub: 'FREE SPINS OVER', tone: 'gold', plate: 'mega' },
  buyFreeSpins: { title: 'BUY FREE SPINS', sub: 'CONFIRM PURCHASE', tone: 'blue', plate: 'base' },
};

const POPUP_PLATE_SRC = {
  base: 'popup_plate.png',
  mega: 'popup_plate_mega.png',
  epic: 'popup_plate_epic.png',
};

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 500;

let cellInfos = [];
let reelCols = [];

// --- Win lines --------------------------------------------------------------
//
// Оригинал (neon-reels) играл одну из 11 запечённых Spine-анимаций по индексу
// пейлайна. Здесь спайна нет, и таблица пейлайнов не нужна: каждый линейный
// выигрыш и так несёт свои `positions`, поэтому линия рисуется SVG-полилинией
// прямо по реальным центрам выигравших ячеек поверх .reel__grid.
const WIN_LINE_NS = 'http://www.w3.org/2000/svg';
let winLineSvg = null;
let winLineLoopTimeout = null;
// Каждый повторяющийся цикл «сыграть — пауза — сыграть» здесь это цепочка
// промисов, и снять его pending-таймаут НЕДОСТАТОЧНО: если цикл отменили в
// момент проигрывания, зависший промис всё равно дорезолвится и заново взведёт
// таймаут, воскресив цикл, который должен был умереть. Поэтому у цикла есть
// поколение-токен, который бампает всё, что его отменяет, и каждое продолжение
// сверяет токен, с которым стартовало, прежде чем планировать новую работу.
let winLineToken = 0;

function ensureWinLineSvg() {
  const gridEl = document.querySelector('.reel__grid');
  if (!gridEl) return null;
  if (winLineSvg && winLineSvg.parentNode === gridEl) return winLineSvg;
  const svg = document.createElementNS(WIN_LINE_NS, 'svg');
  svg.setAttribute('class', 'win-line');
  svg.setAttribute('preserveAspectRatio', 'none');
  gridEl.appendChild(svg);
  winLineSvg = svg;
  return svg;
}

// Центры ячеек в системе координат самой .reel__grid. Читаются вживую, а не
// считаются арифметикой row/col: сетка масштабируется через CSS
// (updateReelScale), поэтому измерение — единственное, что остаётся верным на
// всех брейкпоинтах.
function cellCentre(row, col) {
  const info = cellInfos[row * GRID_COLS + col];
  const gridEl = document.querySelector('.reel__grid');
  if (!info || !gridEl) return null;
  const cellRect = info.cell.getBoundingClientRect();
  const gridRect = gridEl.getBoundingClientRect();
  const scale = gridRect.width / gridEl.offsetWidth || 1;
  return {
    x: (cellRect.left + cellRect.width / 2 - gridRect.left) / scale,
    y: (cellRect.top + cellRect.height / 2 - gridRect.top) / scale,
  };
}

// Одна вспышка линии: нарисовать, проиграть прорисовку, зарезолвиться после
// одного прохода. Ритм повторов — на вызывающей стороне.
function showWinLine(win) {
  const positions = (win && win.positions) || [];
  const svg = positions.length >= 2 ? ensureWinLineSvg() : null;
  if (!svg) {
    hideWinLine();
    return Promise.resolve();
  }
  const gridEl = document.querySelector('.reel__grid');
  svg.setAttribute('viewBox', `0 0 ${gridEl.offsetWidth} ${gridEl.offsetHeight}`);

  const points = positions
    .slice()
    .sort((a, b) => a.col - b.col)
    .map(({ row, col }) => cellCentre(row, col))
    .filter(Boolean);
  if (points.length < 2) {
    hideWinLine();
    return Promise.resolve();
  }
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

  svg.innerHTML = '';
  // Два наложенных штриха: широкое мягкое свечение снизу, яркое ядро сверху.
  for (const cls of ['win-line__glow', 'win-line__core']) {
    const path = document.createElementNS(WIN_LINE_NS, 'path');
    path.setAttribute('class', cls);
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  svg.classList.remove('is-playing');
  void svg.getBoundingClientRect(); // рестарт CSS-анимации
  svg.classList.add('is-playing');

  return wait(WIN_PULSE_MS);
}

// Только для случая одной линии (ветка playWinCells с одной группой): повторяет
// showWinLine в том же ритме, что и свечение выигравших символов, чтобы линия
// пульсировала с ними в такт, а не разъезжалась.
function previewWinLine(win) {
  if (winLineLoopTimeout) {
    clearTimeout(winLineLoopTimeout);
    winLineLoopTimeout = null;
  }
  const token = ++winLineToken;
  const playOnce = () => {
    showWinLine(win).then(() => {
      if (token !== winLineToken) return;
      winLineLoopTimeout = setTimeout(() => {
        winLineLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

function hideWinLine() {
  winLineToken += 1;
  if (winLineLoopTimeout) {
    clearTimeout(winLineLoopTimeout);
    winLineLoopTimeout = null;
  }
  if (!winLineSvg) return;
  winLineSvg.remove();
  winLineSvg = null;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomSymbolCode() {
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

// --- Cells ------------------------------------------------------------------
//
// Каждая ячейка — один <img>. Там, где оригинал подменял статику Spine-инстансом,
// здесь просто переключаются классы, поэтому ниже нигде нет `info.instance` и
// нет канваса вообще.

// Померенных пер-символьных сдвигов нет: все символы при нарезке нормализованы
// в один квадрат с общим оптическим центром, так что они и так совпадают. Живой
// оверрайд из Anim Lab («Калибровать») по-прежнему главнее.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('uniqorn-back-to-fabulous', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));

  const img = document.createElement('img');
  img.alt = code;
  img.src = symbolSrc(code);
  img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  // Оставлен (пустым), чтобы общий инструмент калибровки нашёл якорь.
  const anchor = document.createElement('div');
  anchor.className = 'reel__cell-anchor';
  cell.appendChild(anchor);

  return { cell, img, anchor };
}

function buildReelGrid() {
  const gridEl = document.getElementById('reelGrid');
  gridEl.innerHTML = '';
  cellInfos = [];
  reelCols = [];

  for (let col = 0; col < GRID_COLS; col++) {
    const colEl = document.createElement('div');
    colEl.className = 'reel__col';
    const stripEl = document.createElement('div');
    stripEl.className = 'reel__strip';
    colEl.appendChild(stripEl);
    gridEl.appendChild(colEl);
    reelCols.push({ colEl, stripEl });

    for (let row = 0; row < GRID_ROWS; row++) {
      const symbol = SYMBOL_LAYOUT[row][col];
      const { cell, img, anchor } = createCellNode(symbol);
      stripEl.appendChild(cell);
      const info = { symbol, cell, img, anchor, winLoopTimeout: null };
      cell.addEventListener('click', () => onCellClick(info, col));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
}

function clearCellAnimation(info) {
  info.winToken = (info.winToken || 0) + 1;
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  info.cell.classList.remove('is-winning', 'is-win-active', 'is-landing');
}

function teardownCellInstances() {
  setHeroMood('idle');
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  hideWinLine();
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    info.cell.style.opacity = '';
    clearCoinMultiplierLabel(info);
    clearCellAnimation(info);
  }
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  clearCoinMultiplierLabel(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  info.cell.style.opacity = '';
  info.img.src = symbolSrc(code);
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);
  return Promise.resolve();
}

// Маленькое приседание, которое символ делает, когда его барабан встаёт.
function playLandBounce(info) {
  if (!info) return;
  info.cell.classList.remove('is-landing');
  void info.cell.offsetWidth; // рестарт кейфреймов
  info.cell.classList.add('is-landing');
  setTimeout(() => info.cell.classList.remove('is-landing'), LAND_BOUNCE_MS);
}

function playWinAnimationOnce(info) {
  info.cell.classList.remove('is-winning');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-winning');
  return wait(WIN_PULSE_MS).then(() => {
    info.cell.classList.remove('is-winning');
  });
}

function previewSymbolWin(info) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  const token = (info.winToken = (info.winToken || 0) + 1);
  const playOnce = () => {
    playWinAnimationOnce(info).then(() => {
      if (token !== info.winToken) return;
      info.winLoopTimeout = setTimeout(() => {
        info.winLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

// Клик по эссенции показывает, как выглядит её метка множителя (без бэкенда
// значения взять неоткуда — берём случайное из той же лестницы, что в сиде);
// по любому другому символу — луп его win-анимации.
const PREVIEW_MULTIPLIER_VALUES = [1, 2, 5, 10, 25, 50, 100];

function onCellClick(info, col) {
  if (info.symbol === 'essence') {
    const value = PREVIEW_MULTIPLIER_VALUES[Math.floor(Math.random() * PREVIEW_MULTIPLIER_VALUES.length)];
    showCoinMultiplierLabel(info, value);
    previewSymbolWin(info);
  } else {
    previewSymbolWin(info);
  }
}

function setCellActive(info, active) {
  info.cell.classList.toggle('is-win-active', active);
  if (!active) info.cell.classList.remove('is-winning');
}

function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
}

let multiLineSequenceTimeout = null;
let multiLineToken = 0;

function playMultiLineWinSequence(groups, allWinInfos, lineWins) {
  const token = ++multiLineToken;
  const playPhaseOnce = (activeInfos) => {
    const activeSet = new Set(activeInfos);
    for (const info of cellInfos) {
      if (info) setCellDimmed(info, !activeSet.has(info));
    }
    for (const info of allWinInfos) {
      setCellActive(info, activeSet.has(info));
    }
    return Promise.all(activeInfos.map((info) => playWinAnimationOnce(info)));
  };

  let groupIndex = -1;
  const step = () => {
    const activeInfos = groupIndex === -1 ? allWinInfos : groups[groupIndex];
    // groups[i] при i < lineWins.length соответствует lineWins[i] один в один
    // (см. buildWinGroups/ReelMath.collectWinGroups — линейные выигрыши идут
    // первыми и несут только позиции, так что индекс — единственный путь назад
    // к пейлайну). Фаза «все вместе» (groupIndex -1) мешает линии, поэтому там
    // ничья линия не рисуется.
    const win = groupIndex >= 0 ? lineWins[groupIndex] : null;
    if (win) showWinLine(win);
    else hideWinLine();
    playPhaseOnce(activeInfos).then(() => {
      if (token !== multiLineToken) return;
      multiLineSequenceTimeout = setTimeout(() => {
        multiLineSequenceTimeout = null;
        groupIndex = (groupIndex + 1) % groups.length;
        step();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  step();
}

async function applyGrid(grid) {
  teardownCellInstances();
  const tasks = [];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const info = cellInfos[row * GRID_COLS + col];
      tasks.push(setCellSymbol(info, grid[row][col]));
    }
  }
  await Promise.all(tasks);
}

function buildWinGroups(lineWins, countWins) {
  return ReelMath.collectWinGroups(lineWins, countWins).map((positions) =>
    positions.map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean),
  );
}

function playWinCells(winningCells, lineWins, countWins) {
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }

  const allWinInfos = (winningCells || [])
    .map(({ row, col }) => cellInfos[row * GRID_COLS + col])
    .filter(Boolean);
  // Любой выигрыш (даже одна группа) притушивает все не входящие в него ячейки,
  // чтобы он читался на фоне остальной сетки.
  const winSet = new Set(allWinInfos);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, allWinInfos.length > 0 && !winSet.has(info));
  }
  // Заодно снимает напряжённую позу, оставшуюся от антиципации, которая в
  // итоге ничего не заплатила.
  setHeroMood(allWinInfos.length > 0 ? 'cheer' : 'idle');

  const groups = buildWinGroups(lineWins, countWins);

  if (groups.length > 1) {
    playMultiLineWinSequence(groups, allWinInfos, lineWins);
  } else {
    // Одна группа: это линия только если в lineWins ровно одна запись
    // (одинокий count-pay/скаттер формы линии не имеет).
    if (lineWins && lineWins.length === 1 && countWins && countWins.length === 0) {
      previewWinLine(lineWins[0]);
    } else {
      hideWinLine();
    }
    for (const info of allWinInfos) previewSymbolWin(info);
  }
}

// --- Метки множителя (эссенция) ---------------------------------------------
//
// В neon-reels значение висело на кости `bone_numb` монеточного скелета, и его
// приходилось каждый кадр трекать через worldToScreen. Скелетов здесь нет,
// поэтому метка — просто ребёнок ячейки: она масштабируется и ездит вместе с
// сеткой сама, без rAF-цикла.
function clearCoinMultiplierLabel(info) {
  if (!info || !info.coinLabel) return;
  info.coinLabel.remove();
  info.coinLabel = null;
  info.cell.classList.remove('has-coin-value');
}

function showCoinMultiplierLabel(info, value) {
  clearCoinMultiplierLabel(info);
  const el = document.createElement('span');
  el.className = 'coin-value';
  el.textContent = `x${value}`;
  info.cell.appendChild(el);
  info.cell.classList.add('has-coin-value');
  info.coinLabel = el;
}

// Вызывается сразу после приземления колонки: каждая эссенция получает своё
// значение, независимо от того, применится множитель в этом спине или нет
// (презентация не гейтится — см. app/features/coin_multiplier.py).
function maybeShowCoinMultiplierLabels(col, coinMultiplier) {
  if (!coinMultiplier) return;
  for (const pos of coinMultiplier.positions || []) {
    if (pos.col !== col) continue;
    const info = cellInfos[pos.row * GRID_COLS + col];
    if (info && info.symbol === 'essence') showCoinMultiplierLabel(info, pos.value);
  }
}

// А вот это уже про применённый множитель: эссенции подсвечиваются вместе с
// выигрышем.
function playCoinMultiplierReveal(coinMultiplier) {
  if (!coinMultiplier || !coinMultiplier.applied) return;
  let any = false;
  for (const pos of coinMultiplier.positions || []) {
    const info = cellInfos[pos.row * GRID_COLS + pos.col];
    if (info && info.symbol === 'essence') {
      info.cell.classList.add('is-coin-applied');
      previewSymbolWin(info);
      any = true;
    }
  }
  if (any) Sound.playSfx('coinLand');
}

const INLINE_WIN_AMOUNT_HOLD_MS = 1800;
let inlineWinAmountTimeout = null;

function showInlineWinAmount(amount) {
  const el = document.getElementById('reelWinAmount');
  if (!el) return;
  if (inlineWinAmountTimeout) {
    clearTimeout(inlineWinAmountTimeout);
    inlineWinAmountTimeout = null;
  }

  el.dataset.amount = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');
  inlineWinAmountTimeout = setTimeout(() => {
    inlineWinAmountTimeout = null;
    el.classList.remove('is-visible');
  }, INLINE_WIN_AMOUNT_HOLD_MS);
}

// --- Reel motion (механика общая для всех тем — подробный разбор техники с
// маскированной колонкой см. в других играх) ---------------------------------

// Фазы бесконечной прокрутки нет (перенесено из neon-reels, там продукт это
// одобрил: «по ощущениям даже лучше чем у нас на демо»): по нажатию спина
// лежащие символы уезжают вниз с ускорением (их скрывает собственный overflow
// колонки), барабан стоит пустым, пока отвечает сервер, а финалы падают сверху
// обычным приземлением landReel. landReel ждёт reelClearDone, чтобы ни одна
// колонка не начала приземляться, пока старые символы ещё летят вниз.
const REEL_CLEAR_MS = 260;

let reelLoopGeneration = 0; // обесценивает висящий clear, если пришёл новый спин
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  teardownCellInstances();
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    // Два rAF: целый кадр, чтобы transition:none + сброс трансформа применились
    // до старта падения (одинкадровый старт роняет кадры на мобилке и открывает
    // движение видимым «ползком»).
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (gen !== reelLoopGeneration) return resolve();
      for (const { stripEl } of reelCols) {
        stripEl.style.transition = `transform ${REEL_CLEAR_MS}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
        stripEl.style.transform = `translateY(${ReelMath.ROW_STEP * (GRID_ROWS + 1)}px)`;
      }
      setTimeout(resolve, REEL_CLEAR_MS + 40);
    }));
  });
}

function stopReelLoop() {
  // Уборка на пути ошибки (см. catch в runSpin): падение-очистка могло оставить
  // ленты уехавшими ниже окна — вернуть их на место, прежде чем вызывающий
  // заново применит последнюю известную сетку.
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
}

// Саспенс для колонки, помеченной ReelMath.collectAnticipationColumns: вместо
// перезапуска бесконечного CSS-лупа на меньшей скорости — линейный пре-ролл
// (без easing, поэтому без «плато» посередине), а следом РОВНО то же короткое
// приземление, что и у обычных колонок. Подробный разбор, почему не одна
// растянутая кривая, — в mr-president-unicorn/slot.js.
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, fillerCodeFn = randomSymbolCode) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    (async () => {
      // Падение-очистка должно закончиться первым, и пер-колоночный стаггер
      // считается от КОНЦА очистки, а не от нажатия спина. Отсчёт от нажатия
      // означал, что все колонки с задержкой короче очистки просыпались
      // одновременно, и первые барабаны приземлялись разом.
      await reelClearDone;
      await wait(delayMs);
      stripEl.classList.remove('is-looping');
      stripEl.style.transition = 'none';
      stripEl.innerHTML = '';

      const sequence = [
        ...finalCodes,
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, fillerCodeFn),
        ...Array.from({ length: prerollCount }, fillerCodeFn),
      ];
      const cellEls = sequence.map((code) => {
        const { cell } = createCellNode(code);
        stripEl.appendChild(cell);
        return cell;
      });

      const landStartY = -(REEL_LAND_FILLER_COUNT * ReelMath.ROW_STEP);

      const beginLanding = () => {
        stripEl.style.transition = `transform ${REEL_LAND_DURATION_MS}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
        stripEl.style.transform = 'translateY(0px)';

        setTimeout(() => Sound.playSfx(stopSound), Math.max(0, REEL_LAND_DURATION_MS - 200));

        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          if (isAnticipating) reelCols[colIndex].colEl.classList.remove('is-anticipating');
          stripEl.removeEventListener('transitionend', onTransitionEnd);
          for (const cell of cellEls.slice(3)) cell.remove();
          stripEl.style.transition = 'none';
          stripEl.style.transform = 'translateY(0px)';
          resolve(cellEls.slice(0, 3));
        };
        const onTransitionEnd = (event) => {
          if (event.target === stripEl && event.propertyName === 'transform') finish();
        };
        stripEl.addEventListener('transitionend', onTransitionEnd);
        setTimeout(finish, REEL_LAND_DURATION_MS + 200);
      };

      if (isAnticipating) {
        const prerollStartY = -((REEL_LAND_FILLER_COUNT + prerollCount) * ReelMath.ROW_STEP);
        stripEl.style.transform = `translateY(${prerollStartY}px)`;
        void stripEl.offsetHeight;
        stripEl.style.transition = `transform ${ANTICIPATION_PREROLL_MS}ms linear`;
        stripEl.style.transform = `translateY(${landStartY}px)`;

        setTimeout(() => {
          stripEl.style.transition = 'none';
          stripEl.style.transform = `translateY(${landStartY}px)`;
          void stripEl.offsetHeight;
          beginLanding();
        }, ANTICIPATION_PREROLL_MS);
        return;
      }

      stripEl.style.transform = `translateY(${landStartY}px)`;
      void stripEl.offsetHeight;
      beginLanding();
    })();
  });
}

function settleColumnCells(cellEls, col, finalCodes) {
  const tasks = [];
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const img = cell.querySelector('img');
    const anchor = cell.querySelector('.reel__cell-anchor');
    const info = { symbol: code, cell, img, anchor, winLoopTimeout: null };
    cell.addEventListener('click', () => onCellClick(info, col));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code).then(() => playLandBounce(info)));
  }
  return Promise.all(tasks);
}

// Колонки начиная с firstAnticipationCol приземляются ПО ОДНОЙ, никогда
// параллельно: продукт хочет, чтобы открывался один барабан, потом следующий.
// collectAnticipationColumns помечает колонку, только пока триггер ещё не решён,
// поэтому как только одна из них уронит решающий символ, поздние выпадут из
// набора сами — они просто приземлятся на обычной скорости, всё так же по одной.
async function landReels(grid, anticipationColumns = [], coinMultiplier = null, lineWins = [], countWins = []) {
  teardownCellInstances();

  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const delay = col * REEL_LAND_STAGGER_MS;
    leadTasks.push(
      landReel(col, finalCodes, delay, false)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes))
        .then(() => maybeShowCoinMultiplierLabels(col, coinMultiplier)),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');
  setHeroMood('tense');

  // Заморозить все оставшиеся барабаны сразу: приземления по одному (выше) мало,
  // если те, что ждут очереди, всё это время продолжают крутиться на фоне.
  // Каждый замороженный всё равно полностью пересобирается landReel'ом, когда
  // доходит его очередь, так что состояние заморозки роли не играет.
  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const { stripEl } = reelCols[col];
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }

  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const isAnticipating = anticipationSet.has(col);
    if (isAnticipating) reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, 0, isAnticipating);
    await settleColumnCells(cellEls, col, finalCodes);
    maybeShowCoinMultiplierLabels(col, coinMultiplier);
  }
}

// --- Screen dim -------------------------------------------------------------

let dimActiveCount = 0;
let opaqueDimActiveCount = 0;

function pushScreenDim(opaque = false) {
  dimActiveCount += 1;
  document.getElementById('screenDim').classList.add('is-active');
  if (opaque) {
    opaqueDimActiveCount += 1;
    // Непрозрачное затемнение = переход base<->bonus. Всё здесь DOM, поэтому
    // попап просто лежит выше #screenDim в порядке наложения, и один класс
    // делает всю работу.
    document.getElementById('screenDim').classList.add('is-opaque');
  }
}

function popScreenDim(opaque = false) {
  dimActiveCount = Math.max(0, dimActiveCount - 1);
  if (dimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-active');
  if (opaque) {
    opaqueDimActiveCount = Math.max(0, opaqueDimActiveCount - 1);
    if (opaqueDimActiveCount === 0) {
      document.getElementById('screenDim').classList.remove('is-opaque');
    }
  }
}

async function withScreenDim(mutateFn, { opaque = false } = {}) {
  pushScreenDim(opaque);
  await wait(DIM_TRANSITION_MS);
  try {
    await mutateFn();
  } finally {
    popScreenDim(opaque);
  }
}

// Меняет экранный режим (фон) на `next`. Общий для обычного выхода из бонуса и
// для интро входа, чтобы эти два не разъехались.
function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
}

// Сколько попап «ты выиграл бонус» висит на чёрном, прежде чем откроется
// бонусный экран (продукт: ~3с попапа, потом показ).
const BONUS_INTRO_HOLD_MS = 3000;

// Момент base -> free spins: залить экран чёрным, проиграть на чёрном попап
// bonusSpinsWin, под всё ещё непрозрачным чёрным подменить бонусный экран и
// снять заливку. Общий и для настоящего скаттерного триггера (app.js), и для
// dev-переключателя режима — оба идут через setFreeSpinsMode ниже.
async function enterBonusTransition(amount = 0) {
  pushScreenDim(true); // непрозрачная заливка
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true); // показать бонусный экран
}

function setFreeSpinsMode(active, amount = 0) {
  const screen = document.getElementById('screen');
  const next = active ? 'freespins' : 'base';
  if (screen.dataset.mode === next) return Promise.resolve();

  Sound.playMusic(next === 'freespins' ? 'bonus' : 'base');

  // Вход в бонус получает полноценное интро (чёрный + попап + показ); выход —
  // обычную непрозрачную подмену.
  if (next === 'freespins') return enterBonusTransition(amount);

  return withScreenDim(
    async () => {
      applyModeScreen(next);
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
}

// --- Popups -----------------------------------------------------------------

// Собирается заново на каждый показ, а не хранится: попап висит пару секунд
// несколько раз за сессию, кэшировать нечего, а ноды, которой нет в DOM, нечем
// оставить после себя устаревшую сумму.
function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key] || { title: key, tone: 'gold', plate: 'base' };
  const plate = cfg.plate || 'base';
  const root = document.createElement('div');
  root.className = `game-popup is-${cfg.tone} is-plate-${plate}`;
  if (isMobileLayout()) root.classList.add('is-mobile');

  // Плашка — один сгенерированный PNG с намеренно пустой панелью; текст лежит
  // поверх DOM'ом, позиционируясь по измеренным границам этой панели (см.
  // --popup-panel-* в стилях). Перемерить, если плашку перегенерируют.
  const art = document.createElement('img');
  art.className = 'game-popup__art';
  art.src = `${ASSET_ROOT}/img/${POPUP_PLATE_SRC[plate]}`;
  art.alt = '';
  root.appendChild(art);

  const body = document.createElement('div');
  body.className = 'game-popup__body';

  if (cfg.sub) {
    const sub = document.createElement('div');
    sub.className = 'game-popup__sub';
    sub.textContent = cfg.sub;
    body.appendChild(sub);
  }

  const title = document.createElement('div');
  title.className = 'game-popup__title';
  title.textContent = cfg.title;
  body.appendChild(title);

  const amountEl = document.createElement('div');
  amountEl.className = 'game-popup__amount';
  amountEl.textContent = Number(amount).toLocaleString('en-US') + (cfg.amountSuffix || '');
  body.appendChild(amountEl);

  root.appendChild(body);
  return root;
}

// У трёх плашек панели разной ширины (у epic — вообще круг), а тайтлы бывают от
// «BIG WIN» до «BUY FREE SPINS». Вместо ручного подбора размера под каждую пару
// плашка/тайтл — ужимать каждую строку, пока она не влезет. Запускается после
// вставки ноды в DOM, чтобы у панели были настоящие границы.
function fitPopupText(node) {
  const body = node.querySelector('.game-popup__body');
  if (!body) return;
  // Мерить надо по ПАНЕЛИ, а не по собственной коробке строки: body — центрированная
  // флекс-колонка, поэтому nowrap-строка просто вылезает за родителя, а её
  // собственные scrollWidth/clientWidth остаются равны — сама себе она никогда
  // не кажется переполненной.
  const limit = body.clientWidth;
  for (const el of body.querySelectorAll('.game-popup__title, .game-popup__amount, .game-popup__sub')) {
    let size = parseFloat(getComputedStyle(el).fontSize);
    // 24 шага хватает, чтобы довести самый длинный тайтл до самой узкой панели;
    // нижний порог не даёт патологическому случаю схлопнуть текст в ничто.
    for (let i = 0; i < 24 && el.getBoundingClientRect().width > limit && size > 8; i += 1) {
      size *= 0.92;
      el.style.fontSize = `${size}px`;
    }
  }
}

// Жизненный цикл попапа (вход -> держим -> выход). Возвращаемый промис
// резолвится, только когда попап ПОЛНОСТЬЮ отыграл, чтобы вызывающий мог
// выстроить работу после него. `ownDim` позволяет вызывающему, который уже
// владеет затемнением (интро бонуса выше), одолжить попап без собственного
// push/pop затемнения.
function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = true, opaque = false } = {}) {
  if (!POPUP_CONFIG[key]) return Promise.resolve();

  return new Promise((resolve) => {
    // Любой выход идёт через ОДИН finish(), который гарантированно отработает —
    // на обычном пути, на любой ошибке и по страховочному таймауту. Затемнение
    // поднимается до сборки попапа, поэтому всё, что может бросить между этими
    // двумя моментами, не должно уметь оставить экран затемнённым без попапа.
    let node = null;
    let dimmed = false;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safetyTimer);
      if (node) node.remove();
      if (dimmed) popScreenDim(opaque);
      resolve();
    };
    const safetyTimer = setTimeout(finish, holdMs + 8000);

    (async () => {
      Sound.playSfx('popupOpen');
      if (ownDim) {
        pushScreenDim(opaque);
        dimmed = true;
        await wait(DIM_TRANSITION_MS);
      }

      node = buildPopupNode(key, amount);
      document.getElementById('screen').appendChild(node);
      fitPopupText(node);
      void node.offsetWidth; // зафиксировать пред-входное состояние
      node.classList.add('is-in');

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
      finish();
    });
  });
}

// Тировые/dev-попапы владеют своим (частичным) затемнением, как и раньше.
function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Dev panel --------------------------------------------------------------

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');

  toggleBtn.addEventListener('click', () => {
    const next = document.getElementById('screen').dataset.mode === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 10); // демо-число спинов для интро-попапа
    toggleBtn.textContent = `mode: ${next}`;
  });

  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 12345));
  });

  const fitToggleBtn = document.getElementById('devFitToggle');
  if (fitToggleBtn) {
    fitToggleBtn.textContent = `fit-screen: ${isFullscreenFitLayout() ? 'on' : 'off'}`;
    fitToggleBtn.addEventListener('click', () => {
      const on = document.body.classList.toggle('layout-fit');
      fitToggleBtn.textContent = `fit-screen: ${on ? 'on' : 'off'}`;
      updateReelScale();
    });
  }
}

// Дизайн нарисован на родном холсте фона; масштаб замораживается на 1612px и
// ниже этого кропится — то же поведение, что у East Discovery.
const DESKTOP_DESIGN_MAX_WIDTH = 1932;
const DESKTOP_DESIGN_MIN_WIDTH = 1612;

// Экспериментальная раскладка «влезть целиком, без прокрутки» — см.
// body.layout-fit в стилях темы и ReelMath.fitScale.
// Ширина резерва больше, чем у mr-president-unicorn (360): при 360 на
// вьюпорте 1280 рамка вырастает до 920px и ведьме слева остаётся 180px — она
// уезжала за край экрана вместе с половиной шляпы. 480 оставляет по ~240px с
// каждой стороны: слева целиком помещается героиня, справа — табличка Buy Bonus.
const FIT_RESERVE_WIDTH_PX = 480;
const FIT_RESERVE_HEIGHT_PX = 60;

function isFullscreenFitLayout() {
  return document.body.classList.contains('layout-fit');
}

function updateReelScale() {
  const viewportWidth = document.documentElement.clientWidth;
  const viewportHeight = document.documentElement.clientHeight;
  const rootStyle = getComputedStyle(document.documentElement);
  const frameWidth = parseFloat(rootStyle.getPropertyValue('--reel-frame-w')) || 0;

  if (isFullscreenFitLayout()) {
    const frameHeight = parseFloat(rootStyle.getPropertyValue('--reel-frame-h')) || 0;
    const frameScale = parseFloat(rootStyle.getPropertyValue('--reel-frame-scale')) || 1;
    const scale = ReelMath.fitScale(
      viewportWidth,
      viewportHeight,
      frameWidth * frameScale,
      frameHeight * frameScale,
      FIT_RESERVE_WIDTH_PX,
      FIT_RESERVE_HEIGHT_PX,
    );
    document.documentElement.style.setProperty('--reel-scale', String(scale));
  } else {
    document.documentElement.style.setProperty(
      '--reel-scale',
      String(
        ReelMath.viewportScale(
          viewportWidth,
          DESKTOP_DESIGN_MAX_WIDTH,
          DESKTOP_DESIGN_MIN_WIDTH / DESKTOP_DESIGN_MAX_WIDTH,
        ),
      ),
    );
  }

  document.documentElement.style.setProperty(
    '--reel-scale-mobile',
    String(ReelMath.mobileReelScale(viewportWidth, frameWidth)),
  );
}

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function bgSrcFor(mode) {
  if (isMobileLayout()) {
    return mode === 'base' ? `${ASSET_ROOT}/img/bg_base_mob.jpg` : `${ASSET_ROOT}/img/bg_bonus_mob.jpg`;
  }
  return mode === 'base' ? `${ASSET_ROOT}/img/bg_base.jpg` : `${ASSET_ROOT}/img/bg_bonus.jpg`;
}

function updateBgForLayout() {
  const screen = document.getElementById('screen');
  document.getElementById('bgLayer').src = bgSrcFor(screen.dataset.mode || 'base');
}

// --- Boot preloader --------------------------------------------------------
// Прогрев за прелоадером (js/preloader.js): декодировать статику символов,
// подтянуть все позы героини, оба фона и прогреть буферы SFX. Каждая задача
// резолвится (ошибки глотаются), и всё целиком ограничено таймаутом, поэтому
// оверлей нельзя оставить висеть.
const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const img = new Image();
  img.src = src;
  return img.decode ? img.decode() : new Promise((res) => {
    img.onload = res;
    img.onerror = res;
  });
}

function preloadAssets() {
  const P = window.Preloader;
  const track = (promise) => {
    if (P) P.add(1);
    return Promise.resolve(promise)
      .catch(() => {})
      .finally(() => { if (P) P.step(); });
  };

  const tasks = [];
  for (const code of SYMBOL_CODES) tasks.push(track(preloadImage(symbolSrc(code))));
  // Все три позы сразу: смена настроения посреди спина не должна ждать сетевого
  // раунд-трипа, иначе героиня мигнёт ровно в момент реакции.
  for (const src of Object.values(HERO_SRC)) tasks.push(track(preloadImage(src)));
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('bonus'))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // обязан отработать до applyStaticContentOffset в buildReelGrid
  Sound.playMusic('base');
  document.body.classList.add('layout-fit'); // fit-to-screen — дефолтная десктопная раскладка
  updateReelScale();
  updateBgForLayout();
  window.addEventListener('resize', () => {
    updateReelScale();
    updateBgForLayout();
  });

  buildReelGrid();
  setupDevPanel();

  await preloadAssets();
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));

  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
