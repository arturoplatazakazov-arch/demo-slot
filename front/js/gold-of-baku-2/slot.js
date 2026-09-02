// Gold of Baku 2 — 3x3 classic, five lines, no bonus round.
//
// Сцена и движение барабанов взяты у ../country-gold-3 целиком: та же 3x3
// раскладка, тот же дизайн-канвас, тот же нарисованный корпус поверх барабанов
// с ОДНИМ проёмом на все три ленты. В игре нет ни вайлда, ни скаттера, ни
// фриспинов, ни покупки — остаётся ровно спин: увезти старые символы вниз,
// дождаться сервера, уронить новые, подсветить выигравшие линии.
//
// Отличия от донора чисто в арте: восточная рама вместо кантри-корпуса и СЕМЬ
// символов вместо восьми (сливы в этой теме нет — её место занял гранат).
// Всё остальное — окно из долей альфы корпуса, замер ячейки по факту вместо
// парсинга calc'а, afterFrame() вместо голого двойного rAF в скрытой вкладке —
// работает ровно как там.

const ASSET_ROOT = 'img/gold-of-baku-2';

// Версия арта в URL. Статика раздаётся без Cache-Control, поэтому браузер
// держит символы и корпус по эвристике и после перерисовки показывает старую
// картинку (777 «не приезжал» на уже открытой странице). Поднимать при ЛЮБОЙ
// замене файла в img/gold-of-baku-2/.
const ASSET_VERSION = 5;

function assetSrc(path) {
  return `${ASSET_ROOT}/${path}?v=${ASSET_VERSION}`;
}

// Коды, которые может выдать бэкенд. 1:1 контракт с _SYMBOLS в
// app/seed/gold_of_baku_2.py: код == имя файла в symbols/.
const SYMBOL_CODES = [
  'orange', 'grape', 'pomegranate', 'tea', 'bell', 'bar', 'seven',
];

// Крутить можно всем: спец-символов, чьё мелькание врало бы о почти-выигрыше,
// в игре нет вовсе.
const FILLER_CODES = SYMBOL_CODES;

function symbolSrc(code) {
  return assetSrc(`symbols/${code}.png`);
}

const GRID_COLS = 3;
const GRID_ROWS = 3;

// Зеркалит PAYLINES в app/seed/gold_of_baku_2.py — нужен только для антиципации
// (выплаты считает сервер). row index: 0=top, 1=mid, 2=bottom.
const PAYLINE_ROWS = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];

// Раскладка attract-режима до первого спина.
const SYMBOL_LAYOUT = [
  ['bell', 'orange', 'grape'],
  ['pomegranate', 'seven', 'tea'],
  ['grape', 'bar', 'orange'],
];

// Длительности; числа обязаны совпадать с кейфреймами в CSS.
const WIN_PULSE_MS = 620;
const LAND_BOUNCE_MS = 260;
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;
const DIM_TRANSITION_MS = 320;
const WIN_LOOP_PAUSE_MS = 500;

const REEL_LAND_FILLER_COUNT = 14;
const BASE_TIMINGS = {
  landDuration: 750,
  landStagger: 110,
  clear: 260,
};
// Турбо (кнопка в общем баре V3) множит длительности движения — см. setTurbo.
let timings = { ...BASE_TIMINGS };

// Геометрия ячейки живёт в CSS (проём корпуса), поэтому её МЕРЯЮТ, а не парсят.
let rowStep = 200;
function readCellDims() {
  const windowEl = document.getElementById('reel');
  if (windowEl && windowEl.clientHeight > 0) rowStep = windowEl.clientHeight / GRID_ROWS;
}

let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];
// true с нажатия спина и до приземления — окно, в котором сетку нельзя
// пересобирать под новое устройство.
let reelsBusy = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// rAF с таймерным дублёром: в скрытой вкладке кадры не идут вовсе, и всё, что
// запланировано внутри requestAnimationFrame, вместе с ними не выполнится.
function afterFrame() {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve();
    };
    const timer = setTimeout(finish, 60);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      clearTimeout(timer);
      finish();
    }));
  });
}

function randomSymbolCode() {
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

// Турбо из общего бара: анимации короче, логика спина не меняется.
function setTurbo(on) {
  const k = on ? 0.45 : 1;
  timings = {
    landDuration: Math.round(BASE_TIMINGS.landDuration * k),
    landStagger: Math.round(BASE_TIMINGS.landStagger * k),
    clear: Math.round(BASE_TIMINGS.clear * k),
  };
}
window.setTurbo = setTurbo;

// --- Ячейки ------------------------------------------------------------------

function applyStaticContentOffset(img, code) {
  // Символы нарезаны вплотную по содержимому и вписываются в ячейку contain'ом,
  // так что по умолчанию сдвигать нечего; живой оверрайд из Anim Lab главнее.
  const override = window.SlotCalibration && window.SlotCalibration.get('gold-of-baku-2', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

// Код без арта — это баг (бэкенд выдаёт символ, которого фронт не знает), и он
// должен быть громким, а не дырой в сетке.
function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  img.decoding = 'async';
  img.src = symbolSrc(code);
  img.addEventListener('error', () => {
    img.classList.add('is-missing');
    console.warn(`[baku] no art for symbol code "${code}"`);
  }, { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  return { cell, img };
}

// Одно окно (#reel, обрезка в CSS) — три колонки, в каждой своя лента.
function buildReelGrid() {
  const reelEl = document.getElementById('reel');
  reelEl.innerHTML = '';
  cellInfos = [];
  reelCols = [];

  for (let col = 0; col < GRID_COLS; col++) {
    const colEl = document.createElement('div');
    colEl.className = 'reel__col';
    const stripEl = document.createElement('div');
    stripEl.className = 'reel__strip';
    colEl.appendChild(stripEl);
    reelEl.appendChild(colEl);
    reelCols.push({ colEl, stripEl });

    for (let row = 0; row < GRID_ROWS; row++) {
      const symbol = SYMBOL_LAYOUT[row][col];
      const { cell, img } = createCellNode(symbol);
      stripEl.appendChild(cell);
      const info = { symbol, row, col, cell, img, winLoopTimeout: null };
      cell.addEventListener('click', () => previewSymbolWin(info));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }

  readCellDims();
}

function clearCellAnimation(info) {
  info.winToken = (info.winToken || 0) + 1;
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  info.cell.classList.remove('is-winning', 'is-win-active', 'is-landing');
  if (info.spineInstance) stopSpineWin(info);
}

// --- Win line (same idea as uniqorn-scandal's css/*.css .win-line): one
// continuous SVG polyline drawn through the centres of the winning cells,
// not a per-payline art asset — the ONLY backend payline shapes rendered are
// the ones the SVG can literally draw a straight-segment line over.
const WIN_LINE_NS = 'http://www.w3.org/2000/svg';
let winLineSvg = null;
let winLineLoopTimeout = null;
// Generation token: cancelling a loop mid-play doesn't stop its in-flight
// promise from re-arming the timeout afterwards without this.
let winLineToken = 0;

function ensureWinLineSvg() {
  const gridEl = document.getElementById('reel');
  if (!gridEl) return null;
  if (winLineSvg && winLineSvg.parentNode === gridEl) return winLineSvg;
  const svg = document.createElementNS(WIN_LINE_NS, 'svg');
  svg.setAttribute('class', 'win-line');
  svg.setAttribute('preserveAspectRatio', 'none');
  gridEl.appendChild(svg);
  winLineSvg = svg;
  return svg;
}

// Cell centres in #reel's own coordinate space, measured live rather than
// computed from row/col arithmetic: the stage is CSS-scaled.
function cellCentre(row, col) {
  const info = cellInfos[row * GRID_COLS + col];
  const gridEl = document.getElementById('reel');
  if (!info || !gridEl) return null;
  const cellRect = info.cell.getBoundingClientRect();
  const gridRect = gridEl.getBoundingClientRect();
  const scale = gridRect.width / gridEl.offsetWidth || 1;
  return {
    x: (cellRect.left + cellRect.width / 2 - gridRect.left) / scale,
    y: (cellRect.top + cellRect.height / 2 - gridRect.top) / scale,
  };
}

// One flash of the line: draw it, run the dash-in, resolve when it has
// played once. The caller owns the repeat cadence.
function showWinLine(win) {
  const positions = (win && win.positions) || [];
  const svg = positions.length >= 2 ? ensureWinLineSvg() : null;
  if (!svg) {
    hideWinLine();
    return Promise.resolve();
  }
  const gridEl = document.getElementById('reel');
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
  // Two stacked strokes: a wide soft glow underneath, a bright core on top.
  for (const cls of ['win-line__glow', 'win-line__core']) {
    const path = document.createElementNS(WIN_LINE_NS, 'path');
    path.setAttribute('class', cls);
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  svg.classList.remove('is-playing');
  void svg.getBoundingClientRect(); // restart the CSS animation
  svg.classList.add('is-playing');

  return wait(WIN_PULSE_MS);
}

// Lone-line case only (playWinCells' single-group branch): repeats
// showWinLine on the same play-once/pause/repeat cadence the winning
// symbols use.
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

function teardownCellInstances() {
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  hideWinLine();
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    clearCellAnimation(info);
  }
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.img.classList.remove('is-missing');
  info.img.src = symbolSrc(code);
  applyStaticContentOffset(info.img, code);
  return Promise.resolve();
}

// --- Spine: win-анимации символов --------------------------------------------
//
// Сетка остаётся PNG-статикой (три ленты крутятся дёшево, CSS'ом), а на
// выигрыш ячейка НА ВРЕМЯ анимации отдаётся спайну: художник свёл клип win
// так, что его первый и последний кадр — ровно статичный symbols/<code>.png
// (сверено попиксельно: сдвиг bbox 0, alpha Δ0.00 у всех семи), поэтому
// подмена не даёт скачка ни на входе, ни на выходе.
//
// idle и land в экспорте тоже есть, но здесь НЕ играют: idle крутил бы девять
// скелетов с бликами в вебвью ради «дыхания» и вдобавок стартует на 1-6px
// мимо статики, а land дублировал бы падение ленты, которое уже делает
// landReel. Включаются они одной строкой в SPINE_CLIPS, если продукт захочет.
const SPINE_ROOT = `${ASSET_ROOT}/spine`;
const SPINE_FALLBACK_PAD_MS = 600; // страховка, если onSettle не придёт

let spineStage = null;
const spineResources = new Map(); // code -> Promise<resource|null>
const spineReady = new Map();     // code -> resource (только загруженные)

function initSpine() {
  const canvasEl = document.getElementById('spineCanvas');
  if (!canvasEl || !window.spine || !window.SpineEngine) return;
  try {
    spineStage = new SpineEngine.SpineStage(canvasEl);
  } catch (err) {
    // Нет WebGL — игра просто остаётся на CSS-пульсе, а не падает целиком.
    console.error('[gold-of-baku-2] spine stage не поднялся, win-анимации на CSS:', err);
    spineStage = null;
  }
}

// Габариты ОДНОГО ТЕЛА символа в setup-позе: skeletonData.width/height — это
// квадрат сцены (573x573 у апельсина при теле 273x195), и вписывание по нему
// дало бы символ вдвое мельче статики. Считаем bbox без fx-слоёв — он совпадает
// с обрезкой PNG, поэтому спайн садится в ячейку ровно туда же, где стоял img.
function bodyBounds(resource) {
  const skeleton = new spine.Skeleton(resource.skeletonData);
  skeleton.setToSetupPose();
  for (const slot of skeleton.slots) {
    const name = slot.data.attachmentName || '';
    if (name.startsWith('fx_')) slot.setAttachment(null);
  }
  skeleton.updateWorldTransform();
  const offset = new spine.Vector2();
  const size = new spine.Vector2();
  skeleton.getBounds(offset, size, []);
  return { x: offset.x, y: offset.y, width: size.x, height: size.y };
}

function getSymbolResource(code) {
  if (!spineStage) return Promise.resolve(null);
  if (spineResources.has(code)) return spineResources.get(code);
  const promise = SpineEngine.SpineResource.load(spineStage.assetManager, `${SPINE_ROOT}/${code}`)
    .then((resource) => {
      resource.bodyBounds = bodyBounds(resource);
      const win = resource.skeletonData.findAnimation('win');
      resource.winDurationMs = win ? win.duration * 1000 : 0;
      spineReady.set(code, resource);
      return resource;
    })
    .catch((err) => {
      console.error(`[gold-of-baku-2] spine ${code} не загрузился, остаётся CSS-пульс:`, err);
      return null;
    });
  spineResources.set(code, promise);
  return promise;
}

// Доля ячейки, которую занимает арт символа: та же --sym, по которой статика
// вписана contain'ом (у граната/винограда она своя) — иначе спайн-тело было бы
// крупнее PNG и подмена читалась бы рывком.
function cellFit(cell) {
  const raw = parseFloat(getComputedStyle(cell).getPropertyValue('--sym'));
  return Number.isFinite(raw) ? raw : 0.92;
}

function stopSpineWin(info) {
  if (!info.spineInstance) return;
  spineStage.removeBase(info.spineInstance);
  info.spineInstance = null;
  info.img.style.visibility = '';
}

// Возвращает промис на время клипа, либо null — тогда зовущий играет CSS-пульс.
function playSpineWin(info) {
  const resource = spineReady.get(info.symbol);
  if (!spineStage || !resource) {
    void getSymbolResource(info.symbol); // подтянуть к следующему выигрышу
    return null;
  }
  stopSpineWin(info);
  const instance = resource.createInstance();
  instance.anchorEl = info.cell;
  instance.boundsOverride = resource.bodyBounds;
  instance.fit = cellFit(info.cell);
  info.spineInstance = instance;
  spineStage.addBase(instance);
  instance.play('win', false);
  // Статику прячем не раньше, чем спайн реально отрисовал кадр — то есть из
  // rAF. В замороженном вебвью (свёрнутая мини-аппа) рендер-луп не тикает, и
  // скрытие «сразу» оставило бы на месте символа дыру до конца клипа; так же
  // мы гарантируем, что кадр спайна уже лежит поверх, когда PNG исчезает.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (info.spineInstance === instance) info.img.style.visibility = 'hidden';
  }));

  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      stopSpineWin(info);
      resolve();
    };
    instance.onSettle = finish;
    // onSettle приходит из рендер-лупа, а он не тикает в скрытой вкладке:
    // без страховки ячейка осталась бы с hidden-статикой навсегда.
    const timer = setTimeout(finish, resource.winDurationMs + SPINE_FALLBACK_PAD_MS);
  });
}

// --- Показ выигрыша ----------------------------------------------------------

function playWinAnimationOnce(info) {
  const spinePlay = playSpineWin(info);
  if (spinePlay) return spinePlay;
  info.cell.classList.remove('is-winning');
  void info.cell.offsetWidth; // рестарт кейфреймов
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

function playLandBounce(info) {
  if (!info) return;
  info.cell.classList.remove('is-landing');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-landing');
  setTimeout(() => info.cell.classList.remove('is-landing'), LAND_BOUNCE_MS);
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

function playMultiLineWinSequence(groups, allWinInfos) {
  const token = ++multiLineToken;
  const playPhaseOnce = (activeInfos) => {
    const activeSet = new Set(activeInfos);
    for (const info of cellInfos) {
      if (info) setCellDimmed(info, !activeSet.has(info));
    }
    for (const info of allWinInfos) setCellActive(info, activeSet.has(info));
    return Promise.all(activeInfos.map((info) => playWinAnimationOnce(info)));
  };

  // Фаза -1 играет все выигравшие ячейки разом, дальше линии крутятся по
  // одной, чтобы пересекающиеся можно было различить.
  let groupIndex = -1;
  const step = () => {
    const activeInfos = groupIndex === -1 ? allWinInfos : groups[groupIndex];
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
  // Любой выигрыш притушивает всё, что в него не входит, — комбинация должна
  // читаться на фоне остальной сетки.
  const winSet = new Set(allWinInfos);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, allWinInfos.length > 0 && !winSet.has(info));
  }

  const groups = buildWinGroups(lineWins, countWins);
  if (groups.length > 1) {
    playMultiLineWinSequence(groups, allWinInfos);
  } else {
    for (const info of allWinInfos) previewSymbolWin(info);
  }
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

function setHintVisible(visible) {
  const el = document.getElementById('hintLine');
  if (el) el.classList.toggle('is-hidden', !visible);
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

// --- Движение барабанов ------------------------------------------------------
//
// Барабан = .reel__strip внутри общего окна #reel; окно режет всё, что выехало
// за проём корпуса. Фазы бесконечной прокрутки нет (как и в остальных играх
// проекта): по нажатию лежащие символы уезжают вниз, барабан стоит пустым, пока
// отвечает сервер, и финалы падают сверху. landReel ждёт reelClearDone, чтобы
// ни одна колонка не начала приземляться, пока старые ещё летят.

let reelLoopGeneration = 0;
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  setHintVisible(false);
  readCellDims();
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = (async () => {
    // Целый кадр, чтобы transition:none и сброс трансформа применились до
    // старта падения (в скрытой вкладке его отсчитает таймер в afterFrame).
    await afterFrame();
    if (gen !== reelLoopGeneration) return;
    for (const { stripEl } of reelCols) {
      stripEl.style.transition = `transform ${timings.clear}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
      stripEl.style.transform = `translateY(${rowStep * (GRID_ROWS + 1)}px)`;
    }
    await wait(timings.clear + 40);
  })();
}

function stopReelLoop() {
  // Уборка на пути ошибки: вернуть ленты на место перед тем, как вызывающий
  // заново применит последнюю известную сетку.
  reelsBusy = false;
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
}

function landReel(colIndex, finalCodes, delayMs) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';

  return new Promise((resolve) => {
    (async () => {
      // Стаггер считается от КОНЦА очистки, а не от нажатия: иначе колонки с
      // задержкой короче очистки просыпаются одновременно.
      await reelClearDone;
      await wait(delayMs);
      stripEl.style.transition = 'none';
      stripEl.innerHTML = '';

      const sequence = [
        ...finalCodes,
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, randomSymbolCode),
      ];
      const cellEls = sequence.map((code) => {
        const { cell } = createCellNode(code);
        stripEl.appendChild(cell);
        return cell;
      });

      const landStartY = -(REEL_LAND_FILLER_COUNT * rowStep);
      stripEl.style.transform = `translateY(${landStartY}px)`;
      void stripEl.offsetHeight;

      stripEl.style.transition = `transform ${timings.landDuration}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
      stripEl.style.transform = 'translateY(0px)';
      setTimeout(() => Sound.playSfx(stopSound), Math.max(0, timings.landDuration - 200));

      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        stripEl.removeEventListener('transitionend', onTransitionEnd);
        for (const cell of cellEls.slice(GRID_ROWS)) cell.remove();
        stripEl.style.transition = 'none';
        stripEl.style.transform = 'translateY(0px)';
        resolve(cellEls.slice(0, GRID_ROWS));
      };
      const onTransitionEnd = (event) => {
        if (event.target === stripEl && event.propertyName === 'transform') finish();
      };
      stripEl.addEventListener('transitionend', onTransitionEnd);
      // Транзишен, который не выстрелил (скрытая вкладка, гонка стилей), не
      // должен подвесить спин.
      setTimeout(finish, timings.landDuration + 200);
    })();
  });
}

// Ячейки уже собраны падающей лентой, поэтому переклеивать их через
// setCellSymbol здесь нечего — остаётся завести на них info и сыграть посадку.
function settleColumnCells(cellEls, col, finalCodes) {
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const info = {
      symbol: code, row, col, cell,
      img: cell.querySelector('img'),
      winLoopTimeout: null,
    };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    playLandBounce(info);
  }
}

// Последний барабан «на подходе», когда первые два уже дали пару одинаковых на
// какой-нибудь линии: то есть третий действительно доигрывает выигрыш, а не
// просто крутится. Считается по уже известной (серверной) сетке, поэтому
// «почти выпало» здесь всегда честное.
//
// Только по ХАЙ-символам: любая пара подряд встречается больше чем в половине
// спинов, и антиципация на каждом втором апельсине перестала бы что-либо
// значить. Чай сюда входит — он в этой лестнице уже хай (10.4x ставки).
const ANTICIPATION_CODES = new Set(['tea', 'bell', 'bar', 'seven']);

function anticipationColumns(codes) {
  for (const line of PAYLINE_ROWS) {
    const first = codes[line[0]][0];
    if (ANTICIPATION_CODES.has(first) && first === codes[line[1]][1]) return [2];
  }
  return [];
}

// Колонки начиная с firstAnticipationCol приземляются ПО ОДНОЙ, никогда
// параллельно: открывается один барабан, потом следующий — иначе саспенса нет.
async function landReels(grid) {
  reelsBusy = true;
  try {
    await landReelsInner(grid);
  } finally {
    reelsBusy = false;
    await flushDeviceRebuild();
  }
}

async function landReelsInner(grid) {
  teardownCellInstances();

  const columnCodes = (col) => [grid[0][col], grid[1][col], grid[2][col]];
  const anticipating = anticipationColumns(grid);
  const firstAnticipationCol = anticipating.length > 0 ? Math.min(...anticipating) : GRID_COLS;
  const anticipationSet = new Set(anticipating);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = columnCodes(col);
    leadTasks.push(
      landReel(col, finalCodes, col * timings.landStagger)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes)),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');

  // Заморозить оставшиеся барабаны сразу: приземления по одному мало, если те,
  // что ждут очереди, продолжают крутиться на фоне.
  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const { stripEl } = reelCols[col];
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }

  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const finalCodes = columnCodes(col);
    if (anticipationSet.has(col)) reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, 0);
    reelCols[col].colEl.classList.remove('is-anticipating');
    settleColumnCells(cellEls, col, finalCodes);
  }
}

// --- Затемнение --------------------------------------------------------------

let dimActiveCount = 0;

function pushScreenDim() {
  dimActiveCount += 1;
  document.getElementById('screenDim').classList.add('is-active');
}

function popScreenDim() {
  dimActiveCount = Math.max(0, dimActiveCount - 1);
  if (dimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-active');
}

// --- Попапы ------------------------------------------------------------------
//
// Плашка нарисована в CSS (.game-popup), так что попап — это просто набор
// строк; собирается заново на каждый показ, а не кэшируется: ноды, которой нет
// в DOM, нечем оставить после себя устаревшую сумму.
// Титул нарисован на самой плашке, поэтому от игры тут только сумма: она
// ложится в пустую рамку внизу PNG (её доли — в .game-popup--* в CSS).
const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN', mod: 'big', plate: 'img/popup_big.png' },
  megaWin: { title: 'MEGA WIN', mod: 'mega', plate: 'img/popup_mega.png' },
  epicWin: { title: 'EPIC WIN', mod: 'epic', plate: 'img/popup_epic.png' },
};

function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key];
  const root = document.createElement('div');
  root.className = `game-popup game-popup--${cfg.mod}`;
  root.setAttribute('role', 'img');
  root.setAttribute('aria-label', `${cfg.title} ${Number(amount).toLocaleString('en-US')}`);

  const plate = document.createElement('img');
  plate.className = 'game-popup__plate';
  plate.src = assetSrc(cfg.plate);
  plate.alt = '';
  root.appendChild(plate);

  const amountEl = document.createElement('div');
  amountEl.className = 'game-popup__amount';
  const value = document.createElement('span');
  value.textContent = Number(amount).toLocaleString('en-US');
  amountEl.appendChild(value);
  root.appendChild(amountEl);
  return root;
}

// Рамка под сумму нарисована и не тянется, а сумма растёт от 4 знаков до 9 —
// поэтому длинную дожимаем шрифтом. Меряем ВНУТРЕННИЙ span против ширины
// рамки: сам .game-popup__amount — центрирующий флекс, текст в нём вылезает в
// обе стороны, и его собственные scrollWidth/clientWidth остаются равны.
function fitPopupAmount(node) {
  const box = node.querySelector('.game-popup__amount');
  const value = box && box.firstElementChild;
  if (!value) return;
  const limit = box.clientWidth;
  let size = parseFloat(getComputedStyle(box).fontSize);
  for (let i = 0; i < 24 && value.offsetWidth > limit && size > 8; i += 1) {
    size *= 0.92;
    box.style.fontSize = `${size}px`;
  }
}

// Жизненный цикл попапа (вход -> держим -> выход). Любой выход идёт через ОДИН
// finish(), и он гарантированно отработает — иначе упавший попап оставил бы
// экран затемнённым навсегда.
function playPopup(key, amount = 0, holdMs = 2500) {
  if (!POPUP_CONFIG[key]) return Promise.resolve();

  return new Promise((resolve) => {
    let node = null;
    let dimmed = false;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safetyTimer);
      if (node) node.remove();
      if (dimmed) popScreenDim();
      resolve();
    };
    const safetyTimer = setTimeout(finish, holdMs + 8000);

    (async () => {
      Sound.playSfx('popupOpen');
      pushScreenDim();
      dimmed = true;
      await wait(DIM_TRANSITION_MS);
      node = buildPopupNode(key, amount);
      document.getElementById('screen').appendChild(node);
      fitPopupAmount(node); // до .is-in: коробка ещё не под scale(0.7)-трансформом
      void node.offsetWidth; // зафиксировать пред-входное состояние
      node.classList.add('is-in');

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`[baku] popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
      finish();
    });
  });
}

// --- Dev-панель --------------------------------------------------------------

function setupDevPanel() {
  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 123456));
  });
}

// --- Вьюпорт и фон -----------------------------------------------------------
//
// Игра нарисована в фиксированном дизайн-канвасе (размеры фонов), и #stage
// contain-масштабируется в .screen.
const DESIGN = { desktop: { w: 1720, h: 1000 }, mobile: { w: 780, h: 1300 } };

function updateStageScale() {
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth || document.documentElement.clientWidth;
  const vh = screenEl.clientHeight || document.documentElement.clientHeight;
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  const scale = Math.min(vw / d.w, vh / d.h);
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  document.documentElement.style.setProperty('--design-w', `${d.w}px`);
  document.documentElement.style.setProperty('--design-h', `${d.h}px`);
  readCellDims();
}

// Под устройство меняется только ФОН: корпус на обоих раскладках один и тот же
// (cabinet.png) — своя портретная картинка со своим проёмом делала из слота
// другую игру, там рама и ячейка были другой пропорции.
function setDeviceArt() {
  const suffix = isMobileLayout() ? '_mob' : '';
  document.getElementById('bgLayer').src = assetSrc(`img/bg_base${suffix}.jpg`);
}

// Геометрия ячейки разная на устройствах, поэтому поворот экрана пересобирает
// сетку. Делать это посреди спина нельзя — пересборка сносит ячейки, которых
// ждёт анимация, — поэтому откладываем до конца спина.
let lastMobile = null;
let pendingDeviceRebuild = false;

async function handleResize() {
  updateStageScale();
  const nowMobile = isMobileLayout();
  if (nowMobile === lastMobile) return;
  lastMobile = nowMobile;
  setDeviceArt();
  pendingDeviceRebuild = true;
  await flushDeviceRebuild();
}

async function flushDeviceRebuild() {
  if (!pendingDeviceRebuild || reelsBusy) return;
  pendingDeviceRebuild = false;
  const snapshot = cellInfos.map((info) => (info ? info.symbol : null));
  teardownCellInstances();
  buildReelGrid();
  await Promise.all(cellInfos.map((info, i) => setCellSymbol(info, snapshot[i] || info.symbol)));
}

// --- Прелоадер ---------------------------------------------------------------
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
  tasks.push(track(preloadImage(assetSrc('img/logo.png'))));
  const suffix = isMobileLayout() ? '_mob' : '';
  tasks.push(track(preloadImage(assetSrc(`img/bg_base${suffix}.jpg`))));
  tasks.push(track(preloadImage(assetSrc('img/cabinet.png'))));
  for (const cfg of Object.values(POPUP_CONFIG)) tasks.push(track(preloadImage(assetSrc(cfg.plate))));
  for (const code of SYMBOL_CODES) tasks.push(track(getSymbolResource(code)));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // обязан отработать до applyStaticContentOffset
  // Sound.playMusic здесь нет намеренно: у игры нет фоновой музыки, только SFX
  // (см. шапку sound.js).
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  window.addEventListener('orientationchange', handleResize);

  buildReelGrid();
  setDeviceArt();
  setupDevPanel();
  initSpine(); // до preloadAssets: он же тянет скелеты через stage.assetManager

  await preloadAssets();
  // Корпус грузится позже сетки, а высота ячейки меряется по окну — после
  // загрузки арта пересчитываем, иначе первый спин поедет со старым шагом.
  readCellDims();
  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
