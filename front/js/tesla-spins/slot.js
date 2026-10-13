// Tesla Spins — 3x3, five lines, Hold & Win on lightning coins.
//
// Движок барабанов — от ../gold-of-baku (та же 3x3 раскладка, дизайн-канвас,
// рама поверх лент, Spine-клипы выигрыша на общем WebGL-канвасе). Отличия:
//
// - колонки разной ширины, у каждой своё окно обрезки (ячейки шкафа на
//   референсе нарисованы от руки — см. шапку css/tesla-spins.css);
// - монета-молния: 3+ на поле открывают Hold & Win. Раунд целиком решает
//   сервер (data.hold_and_win: initial + respins + full_grid_jackpot), клиент
//   его ПРОИГРЫВАЕТ: зарядка монет, раскрытие номиналов, респины пустых ячеек,
//   сбор в счётчик, GRAND за 9/9 (см. раздел «Hold & Win» ниже);
// - каждый выигрыш сопровождают молнии от катушек (tesla-fx.js) и
//   синтезированный треск (Sound.zap).

const ASSET_ROOT = 'img/tesla-spins';

// Версия арта в URL: статика раздаётся без Cache-Control. Поднимать при ЛЮБОЙ
// замене файла в img/tesla-spins/.
const ASSET_VERSION = 3;

function assetSrc(path) {
  return `${ASSET_ROOT}/${path}?v=${ASSET_VERSION}`;
}

// 1:1 контракт с app/seed/tesla_spins.py: код == имя файла в symbols/.
const SYMBOL_CODES = [
  'lemon', 'cherry', 'plum', 'watermelon', 'bell', 'star', 'gold', 'seven', 'coin',
];

// Монеты в прокрутке мелькают — как и положено в Hold & Win.
const FILLER_CODES = SYMBOL_CODES;
const COIN_CODE = 'coin';

// Зеркалит JACKPOT_VALUES в app/seed/tesla_spins.py (множители ставки).
const JACKPOT_LADDER = { mini: 20, minor: 50, major: 200, grand: 1000 };

function symbolSrc(code) {
  return assetSrc(`symbols/${code}.png`);
}

const GRID_COLS = 3;
const GRID_ROWS = 3;

// Зеркалит PAYLINES в app/seed/tesla_spins.py — нужен только для антиципации
// (выплаты считает сервер). row index: 0=top, 1=mid, 2=bottom.
const PAYLINE_ROWS = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];

// Раскладка attract-режима — как на референсе.
const SYMBOL_LAYOUT = [
  ['lemon', 'seven', 'bell'],
  ['plum', 'coin', 'cherry'],
  ['gold', 'watermelon', 'star'],
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

// --- Spine-анимации символов -------------------------------------------------
//
// Скелеты сгенерированы кодом (scripts/tesla_spins_spine.py): у каждого символа
// клип win (1.9с — удар молнии, электрошок, волны, лучи, дуги, искры), у
// монеты ещё idle; отдельный FX-скелет zap (клип hit) бьёт в ячейку, куда в
// раунде упала монета. Контракт тот же, что у художественных экспортов gold-of-baku: слот
// `item` = PNG символа в его собственных пикселях, win начинается и кончается
// в setup-позе (= статика), поэтому подмена <img> на скелет бесшовная.
const SPINE_ROOT = `${ASSET_ROOT}/spine`;

// Клипов land у сгенерированных скелетов нет; idle есть только у монеты.
const PLAY_IDLE_CLIP = false;
const PLAY_LAND_CLIP = false;

let spineStage = null;
const spineItemBoxes = new Map();

function spineFolder(code) {
  return `${SPINE_ROOT}/${code}`;
}

function loadSymbolResource(code) {
  // spine_screen_kit пишет атласы с pma:true — премультиплицированная альфа.
  return SpineEngine.SpineResource.load(spineStage.assetManager, spineFolder(code), {
    premultipliedAlpha: true,
  });
}

// Коробка ОДНОГО слота item в координатах скелета. Полные границы скелета
// включают свечение, блик и лучи, и символ, вписанный по ним, оказался бы
// заметно мельче статики; по коробке item движок даёт ровно тот же масштаб,
// что и <img> с object-fit: contain и долей --sym.
function symbolItemBox(code, resource) {
  if (spineItemBoxes.has(code)) return spineItemBoxes.get(code);
  let box = resource.bounds;
  try {
    const skeleton = new spine.Skeleton(resource.skeletonData);
    skeleton.setToSetupPose();
    for (const slot of skeleton.slots) {
      if (slot.data.name !== 'item') slot.setAttachment(null);
    }
    skeleton.updateWorldTransform();
    const rect = skeleton.getBoundsRect();
    if (rect && rect.width > 0 && rect.height > 0) box = rect;
  } catch (err) {
    console.warn(`[tesla] не смог померить item у "${code}", беру границы скелета:`, err);
  }
  spineItemBoxes.set(code, box);
  return box;
}

// Доля ячейки, которую занимает символ, живёт в CSS (--sym на .reel__cell) —
// читаем её оттуда, чтобы скелет и статика масштабировались одним числом.
function symbolFit(cell) {
  const raw = parseFloat(getComputedStyle(cell).getPropertyValue('--sym'));
  return Number.isFinite(raw) ? raw : 0.92;
}

async function ensureCellInstance(info) {
  if (!spineStage) return null;
  if (info.instance && info.instanceCode === info.symbol) return info.instance;
  releaseCellInstance(info);
  const code = info.symbol;
  let resource;
  try {
    resource = await loadSymbolResource(code);
  } catch (err) {
    console.warn(`[tesla] нет spine-анимации для "${code}" — остаётся статика:`, err);
    return null;
  }
  // Пока грузили, ячейку могло перезаписать новым спином.
  if (info.symbol !== code || !info.cell.isConnected) return null;
  const instance = resource.createInstance();
  instance.anchorEl = info.cell;
  instance.boundsOverride = symbolItemBox(code, resource);
  instance.fit = symbolFit(info.cell);
  info.instance = instance;
  info.instanceCode = code;
  return instance;
}

function releaseCellInstance(info) {
  if (!info.instance) return;
  spineStage.removeBase(info.instance);
  info.instance.onSettle = null;
  info.instance = null;
  info.instanceCode = null;
  info.cell.classList.remove('is-animating');
}

// Проиграть клип на ячейке. Резолвится true, если анимация реально отыграла, и
// false, если скелета нет — вызывающий тогда откатывается на CSS.
//
// Конец клипа ловится ДВУМЯ путями: событием complete от Spine и таймером на
// длительность клипа. Таймер здесь не перестраховка, а обязательный дублёр:
// AnimationState двигают кадры rAF, а в скрытой вкладке кадров нет вовсе —
// выигрыш, начатый перед уходом со вкладки, иначе повис бы навсегда и утащил
// за собой всю последовательность подсветки линий.
function playCellClip(info, clip, { loop = false } = {}) {
  return new Promise((resolve) => {
    ensureCellInstance(info).then((instance) => {
      if (!instance) {
        resolve(false);
        return;
      }
      // Статика прячется только на время клипа: скелет рисует ту же картинку,
      // и два слоя разом дали бы двойную плотность на полупрозрачных краях.
      info.cell.classList.add('is-animating');
      spineStage.addBase(instance);
      instance.play(clip, loop);
      if (loop) {
        resolve(true);
        return;
      }
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        instance.onSettle = null;
        resolve(true);
      };
      const animation = instance.resource.skeletonData.findAnimation(clip);
      const timer = setTimeout(finish, (animation ? animation.duration : 2) * 1000 + 400);
      instance.onSettle = finish;
    });
  });
}

function stopCellClip(info) {
  if (!info || !info.instance) return;
  spineStage.removeBase(info.instance);
  info.instance.onSettle = null;
  info.cell.classList.remove('is-animating');
}

// --- Ячейки ------------------------------------------------------------------

function applyStaticContentOffset(img, code) {
  // Символы нарезаны вплотную по содержимому и вписываются в ячейку contain'ом,
  // так что по умолчанию сдвигать нечего; живой оверрайд из Anim Lab главнее.
  const override = window.SlotCalibration && window.SlotCalibration.get('tesla-spins', code);
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
    console.warn(`[tesla] no art for symbol code "${code}"`);
  }, { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  return { cell, img };
}

// Три колонки, у каждой своё окно обрезки (left/width по нарисованным ячейкам
// шкафа задаёт CSS), в каждой своя лента.
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
  // Скелет снимаем с канваса, но сам инстанс держим: он привязан к коду
  // символа и переживает повторные подсветки без пересоздания.
  stopCellClip(info);
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

// Appended to #stageFront (z-index 6), not #reel (z-index 2): #reel is
// itself a positioned, z-indexed element, so it opens its OWN stacking
// context — anything inside it, this SVG included, is capped at that level
// no matter what z-index the SVG itself asks for, always painting under
// .spine-canvas (z-index 5, reported live: the line hid behind a symbol's
// win effect). #stageFront already sits above spine-canvas, so appending
// there is enough — no per-game CSS position formula to keep in sync with
// #reel's own; positionWinLineOverlay measures #reel's real screen rect
// each time instead (same "measure live" approach cellCentre already uses).
function ensureWinLineSvg() {
  const parentEl = document.getElementById('stageFront');
  if (!parentEl) return null;
  if (winLineSvg && winLineSvg.parentNode === parentEl) return winLineSvg;
  const svg = document.createElementNS(WIN_LINE_NS, 'svg');
  svg.setAttribute('class', 'win-line');
  svg.setAttribute('preserveAspectRatio', 'none');
  parentEl.appendChild(svg);
  winLineSvg = svg;
  return svg;
}

// Sizes/positions the (now cross-parent) SVG to sit exactly over #reel in
// real screen pixels, independent of whatever transform #stageFront itself
// carries.
function positionWinLineOverlay(svg, gridEl) {
  const parentEl = svg.parentNode;
  if (!parentEl) return;
  const gridRect = gridEl.getBoundingClientRect();
  const parentRect = parentEl.getBoundingClientRect();
  // parentEl (#stageFront) carries its own transform: scale(--stage-scale),
  // which then ALSO scales this SVG's inline left/top/width/height (they're
  // interpreted in the parent's pre-transform local space, not real screen
  // px) — dividing by that factor here is what cancels it back out so the
  // assigned px values land at gridRect's real on-screen position/size.
  const scale = parentRect.width / parentEl.offsetWidth || 1;
  svg.style.left = `${(gridRect.left - parentRect.left) / scale}px`;
  svg.style.top = `${(gridRect.top - parentRect.top) / scale}px`;
  svg.style.width = `${gridRect.width / scale}px`;
  svg.style.height = `${gridRect.height / scale}px`;
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
  positionWinLineOverlay(svg, gridEl);
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
  info.cell.classList.remove('is-empty', 'is-locked', 'is-hw-spin');
  const face = info.cell.querySelector('.coin-face');
  if (face) face.remove();
  if (info.instanceCode && info.instanceCode !== code) releaseCellInstance(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.img.classList.remove('is-missing');
  info.img.src = symbolSrc(code);
  applyStaticContentOffset(info.img, code);
  return Promise.resolve();
}

// --- Показ выигрыша ----------------------------------------------------------

// Выигрыш играет клипом из Spine; CSS-пульс остаётся запасным путём на случай,
// когда скелет не загрузился (битый атлас, оффлайн) — тогда ячейка всё равно
// подсветится, а не замрёт молча.
function playWinAnimationOnce(info) {
  return playCellClip(info, 'win').then((played) => {
    if (played) {
      stopCellClip(info);
      return;
    }
    info.cell.classList.remove('is-winning');
    void info.cell.offsetWidth; // рестарт кейфреймов
    info.cell.classList.add('is-winning');
    return wait(WIN_PULSE_MS).then(() => {
      info.cell.classList.remove('is-winning');
    });
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

// Приземление. Анимации на нём сейчас нет вовсе: CSS-приседание убрали (читалось
// как дрожь), spine-клип land выключен (читался как второе падение). Функция
// остаётся точкой, куда его вернуть, и её по-прежнему зовёт landReel.
function playLandBounce(info) {
  if (!info) return;
  if (PLAY_LAND_CLIP) {
    playCellClip(info, 'land').then((played) => {
      if (!played) return;
      if (PLAY_IDLE_CLIP) {
        playCellClip(info, 'idle', { loop: true });
      } else {
        stopCellClip(info);
      }
    });
    return;
  }
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

function playMultiLineWinSequence(groups, allWinInfos, lineWins) {
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
  // Always through playMultiLineWinSequence, even for a single group: it
  // gates the phase's own pause behind Promise.all of every cell's own win
  // animation, so a longer clip (e.g. a bigger/slower symbol) still holds
  // the line and the rest of the cells until it actually finishes, instead
  // of each cell and the line looping on its own independent timer and
  // drifting out of phase with each other (reported live).
  if (groups.length > 0) {
    playMultiLineWinSequence(groups, allWinInfos, lineWins);
  }
}

// --- Молнии в выигрыш ------------------------------------------------------------

// Центры ячеек в КЛИЕНТСКИХ пикселях — так их ждёт tesla-fx.js.
function cellClientCentre(info) {
  const r = info.cell.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

// Удар катушек по выигравшим ячейкам. power растёт с размером выигрыша:
// мелкий — одна катушка на ячейку, крупный — обе и толще.
function strikeWinningCells(winningCells, power = 1) {
  if (!window.TeslaFX || !winningCells || !winningCells.length) return Promise.resolve();
  const targets = winningCells
    .map(({ row, col }) => cellInfos[row * GRID_COLS + col])
    .filter(Boolean)
    .map(cellClientCentre);
  Sound.zap(700 + 300 * power, power);
  return TeslaFX.strike(targets, { duration: 750 + 350 * power, power });
}

// --- Hold & Win ------------------------------------------------------------------
//
// Раунд целиком решён сервером (app/features/hold_and_win.py, classic mode):
// hw.initial — монеты, открывшие раунд, с номиналами; hw.respins[] — что упало
// на каждом респине; hw.full_grid_jackpot — "grand", если заполнены все 9.
// Клиент только проигрывает это по шагам:
//
//   1. зарядка — катушки бьют в монеты, монеты бьются током (Spine win);
//   2. баннер HOLD & WIN, остальные ячейки гаснут, HUD с лампами респинов;
//   3. монеты по одной переворачиваются и показывают номинал / джекпот;
//   4. респины: пустые ячейки крутятся, новая монета падает с ударом молнии
//      (Spine zap) и сбрасывает лампы на 3; между монетами бегут дуги;
//   5. сбор: от каждой монеты разряд в счётчик TOTAL, за 9/9 — удар в GRAND.
//
// Номинал — множитель ставки (сервер шлёт value = множитель, kind = "5" или
// "mini"/"minor"/"major"); на монете печатаем ×N и сумму.

function coinFaceSrc(face) {
  return assetSrc(`coins/${face}.png`);
}

function formatShort(n) {
  const v = Number(n);
  if (v >= 1e6) return `${+(v / 1e6).toFixed(v >= 1e7 ? 1 : 2)}M`;
  if (v >= 1e3) return `${+(v / 1e3).toFixed(v >= 1e4 ? 0 : 1)}K`;
  return String(v);
}

function updateJackpotPlates(bet) {
  for (const [tier, mult] of Object.entries(JACKPOT_LADDER)) {
    const el = document.querySelector(`.jp--${tier} .jp__value`);
    if (el) el.textContent = Number(mult * bet).toLocaleString('en-US');
  }
}
window.updateJackpotPlates = updateJackpotPlates;

function isJackpotKind(kind) {
  return Object.prototype.hasOwnProperty.call(JACKPOT_LADDER, kind);
}

function setCoinFace(info, coin, bet) {
  info.cell.classList.remove('is-empty');
  info.cell.classList.add('is-locked');
  info.cell.dataset.symbol = COIN_CODE;
  info.symbol = COIN_CODE;
  const jackpot = isJackpotKind(coin.kind);
  info.img.src = coinFaceSrc(jackpot ? coin.kind : 'face');
  let face = info.cell.querySelector('.coin-face');
  if (!face) {
    face = document.createElement('div');
    face.className = 'coin-face';
    info.cell.appendChild(face);
  }
  face.innerHTML = jackpot
    ? `<span class="coin-face__amount" style="margin-top:58%">${formatShort(coin.value * bet)}</span>`
    : `<span class="coin-face__mult">×${coin.value}</span><span class="coin-face__amount">${formatShort(coin.value * bet)}</span>`;
}

function setCellEmpty(info) {
  info.cell.classList.add('is-empty');
  info.cell.classList.remove('is-locked', 'is-dimmed');
  const face = info.cell.querySelector('.coin-face');
  if (face) face.remove();
}

function restartClass(el, cls, ms) {
  el.classList.remove(cls);
  void el.offsetWidth;
  el.classList.add(cls);
  if (ms) setTimeout(() => el.classList.remove(cls), ms);
}

function elCentre(el) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

// FX-скелет zap поверх ячейки: удар сверху, волны, искры. Отдельный инстанс,
// не связанный с info.instance (тот принадлежит символу).
async function playZap(info) {
  if (!spineStage) return;
  try {
    const resource = await SpineEngine.SpineResource.load(spineStage.assetManager, spineFolder('zap'), {
      premultipliedAlpha: true,
    });
    const inst = resource.createInstance();
    inst.anchorEl = info.cell;
    inst.fit = 1.05;
    spineStage.addBase(inst);
    inst.play('hit', false);
    setTimeout(() => spineStage.removeBase(inst), 1100);
  } catch (err) {
    console.warn('[tesla] нет скелета zap:', err);
  }
}

function setRespinLamps(lit) {
  document.querySelectorAll('#hwHud .hw-lamp').forEach((el, i) => el.classList.toggle('is-lit', i < lit));
}

// Счётчик TOTAL считает вверх таймером (не rAF — в скрытой вкладке тоже).
let hwTotalShown = 0;
function tweenTotal(to, ms = 280) {
  const el = document.getElementById('hwTotal');
  if (!el) return;
  const from = hwTotalShown;
  hwTotalShown = to;
  const steps = 8;
  for (let i = 1; i <= steps; i++) {
    setTimeout(() => {
      el.textContent = Math.round(from + ((to - from) * i) / steps).toLocaleString('en-US');
    }, (ms * i) / steps);
  }
  restartClass(el.parentElement, 'is-pulse', 400);
}

function hitPlate(tier, fromPt, power = 1.5) {
  const plate = document.querySelector(`.jp--${tier}`);
  if (!plate) return Promise.resolve();
  restartClass(plate, 'is-hit', 1200);
  Sound.zap(900, power);
  return window.TeslaFX ? TeslaFX.arc(fromPt, elCentre(plate), { duration: 700, power }) : wait(700);
}

function enterHoldAndWinMode() {
  document.getElementById('screen').classList.add('is-hw');
  document.getElementById('hwHud').classList.add('is-on');
}

function exitHoldAndWinMode() {
  document.getElementById('screen').classList.remove('is-hw');
  document.getElementById('hwHud').classList.remove('is-on');
  if (window.TeslaFX) TeslaFX.setLinks(null);
}
window.exitHoldAndWinMode = exitHoldAndWinMode;

async function playHoldAndWin(hw, bet) {
  teardownCellInstances();
  hwTotalShown = 0;
  const idx = (c) => c.row * GRID_COLS + c.col;
  const locked = new Map(); // cell index -> {coin, info}
  const initial = (hw.initial || []).slice().sort((a, b) => a.col - b.col || a.row - b.row);

  // 1. зарядка
  const coinInfos = initial.map((c) => cellInfos[idx(c)]).filter(Boolean);
  Sound.zap(1200, 1.9);
  if (window.TeslaFX) TeslaFX.strike(coinInfos.map(cellClientCentre), { duration: 1200, power: 1.9 });
  coinInfos.forEach((info) => playCellClip(info, 'win').then(() => stopCellClip(info)));
  await wait(1500);
  coinInfos.forEach(stopCellClip);

  // 2. баннер, гасим всё, кроме монет
  Sound.playSfx('bigWin');
  restartClass(document.getElementById('hwBanner'), 'is-on', 1950);
  enterHoldAndWinMode();
  const initialSet = new Set(initial.map(idx));
  cellInfos.forEach((info, i) => { if (info && !initialSet.has(i)) setCellEmpty(info); });
  setRespinLamps(3);
  document.getElementById('hwTotal').textContent = '0';
  await wait(1700);

  // 3. раскрытие номиналов
  for (const c of initial) {
    const info = cellInfos[idx(c)];
    if (!info) continue;
    restartClass(info.cell, 'is-flipping', 540);
    Sound.zap(260, 0.7);
    setTimeout(() => setCoinFace(info, c, bet), 240);
    playZap(info);
    locked.set(idx(c), { coin: c, info });
    if (isJackpotKind(c.kind)) {
      await wait(300);
      await hitPlate(c.kind, cellClientCentre(info));
    } else {
      await wait(380);
    }
  }
  if (window.TeslaFX) {
    TeslaFX.setLinks(() => [...locked.values()].map(({ info }) => cellClientCentre(info)));
  }
  await wait(400);

  // 4. респины
  let left = 3;
  for (const respin of hw.respins || []) {
    left -= 1;
    setRespinLamps(left);
    const landedByIdx = new Map((respin.landed || []).map((c) => [idx(c), c]));
    const empties = cellInfos.filter((info, i) => info && !locked.has(i));
    empties.forEach((info) => info.cell.classList.add('is-hw-spin'));
    Sound.playSfx('spinStart');
    await wait(420);
    for (let col = 0; col < GRID_COLS; col++) {
      await wait(240);
      let stopped = false;
      for (let row = 0; row < GRID_ROWS; row++) {
        const i = row * GRID_COLS + col;
        const info = cellInfos[i];
        if (!info || locked.has(i)) continue;
        info.cell.classList.remove('is-hw-spin');
        stopped = true;
        const c = landedByIdx.get(i);
        if (!c) continue;
        setCoinFace(info, c, bet);
        restartClass(info.cell, 'is-slam', 440);
        playZap(info);
        Sound.zap(700, 1.4);
        if (window.TeslaFX) TeslaFX.strike([cellClientCentre(info)], { duration: 650, power: 1.4 });
        locked.set(i, { coin: c, info });
        if (isJackpotKind(c.kind)) hitPlate(c.kind, cellClientCentre(info));
      }
      if (stopped) Sound.playSfx(col === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop');
    }
    if (landedByIdx.size) {
      left = 3;
      setRespinLamps(3);
      restartClass(document.querySelector('#hwHud .hw-hud__respins'), 'is-reset', 650);
      await wait(900);
    } else {
      await wait(500);
    }
  }
  cellInfos.forEach((info) => info && info.cell.classList.remove('is-hw-spin'));

  // 5. сбор в счётчик
  await wait(400);
  const meter = document.getElementById('hwTotal');
  let total = 0;
  const order = [...locked.values()].sort((a, b) => a.coin.col - b.coin.col || a.coin.row - b.coin.row);
  for (const { coin, info } of order) {
    restartClass(info.cell, 'is-collect', 440);
    Sound.zap(220, 0.6);
    if (window.TeslaFX) TeslaFX.arc(cellClientCentre(info), elCentre(meter), { duration: 360, power: 1 });
    total += coin.value * bet;
    tweenTotal(total);
    await wait(320);
  }
  if (hw.full_grid_jackpot && JACKPOT_LADDER[hw.full_grid_jackpot]) {
    const tier = hw.full_grid_jackpot;
    const plate = document.querySelector(`.jp--${tier}`);
    await wait(300);
    Sound.zap(1500, 2);
    if (window.TeslaFX && plate) TeslaFX.strike([elCentre(plate)], { duration: 1500, power: 2 });
    if (plate) restartClass(plate, 'is-hit', 1200);
    await wait(900);
    if (plate) await hitPlate(tier, elCentre(plate), 2);
    total += JACKPOT_LADDER[tier] * bet;
    tweenTotal(total, 600);
  }
  await wait(900);
  if (window.TeslaFX) TeslaFX.setLinks(null);
  return total;
}
window.playHoldAndWin = playHoldAndWin;

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
// спинов, и антиципация на каждом втором лимоне перестала бы что-либо значить.
// Плюс Hold & Win: две монеты на первых двух барабанах — третий решает раунд.
const ANTICIPATION_CODES = new Set(['bell', 'star', 'gold', 'seven']);

function anticipationColumns(codes) {
  let coins = 0;
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let col = 0; col < 2; col++) if (codes[row][col] === COIN_CODE) coins += 1;
  }
  if (coins >= 2) return [2];
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
// Плашек-картинок у игры нет: заголовок — неоновый текст, сумма — на стальной
// пластине (всё в CSS, .game-popup). Нода собирается заново на каждый показ.
const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN' },
  megaWin: { title: 'MEGA WIN' },
  epicWin: { title: 'EPIC WIN' },
};

function buildPopupNode(key, amount) {
  const root = document.createElement('div');
  root.className = `game-popup game-popup--${key}`;

  const title = document.createElement('div');
  title.className = 'game-popup__title';
  title.textContent = POPUP_CONFIG[key].title;
  root.appendChild(title);

  const amountEl = document.createElement('div');
  amountEl.className = 'game-popup__amount';
  amountEl.textContent = Number(amount).toLocaleString('en-US');
  root.appendChild(amountEl);
  return root;
}

// Попап встаёт по центру ОКНА БАРАБАНОВ, а не экрана. В портрете слот сидит в
// верхней трети (под ним живёт фиксированный бар V3), и попап, центрированный
// по экрану, накрывал бы пустой фон под рамой, а не выигрыш, ради которого он
// вылез. На десктопе центр слота и центр экрана почти совпадают, так что
// правило одно на обе раскладки.
function positionPopup(node) {
  const screenEl = document.getElementById('screen');
  const reelEl = document.getElementById('reel');
  if (!screenEl || !reelEl) return;
  const screenBox = screenEl.getBoundingClientRect();
  const reelBox = reelEl.getBoundingClientRect();
  if (!reelBox.height) return;   // барабаны ещё не разложены — оставляем центр
  node.style.top = `${Math.round(reelBox.top - screenBox.top + reelBox.height / 2)}px`;
}

// Потолок игры — 1450x от максимальной ставки, сумма в девять знаков с
// запятыми; ужимаем кегль, пока строка не влезет в пластину.
function fitPopupAmount(node) {
  const el = node.querySelector('.game-popup__amount');
  if (!el) return;
  const box = el.clientWidth;
  if (!box) return;                       // попап ещё без ширины — не трогаем
  let size = parseFloat(getComputedStyle(el).fontSize);
  for (let i = 0; i < 14 && el.scrollWidth > box; i++) {
    size *= 0.92;
    el.style.fontSize = `${size}px`;
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
      positionPopup(node);
      fitPopupAmount(node);
      void node.offsetWidth; // зафиксировать пред-входное состояние
      node.classList.add('is-in');
      // Катушки бьют в заголовок попапа — молнии лежат под затемнением, но
      // их вспышка видна сквозь него.
      if (window.TeslaFX) {
        const r = node.getBoundingClientRect();
        Sound.zap(1100, 1.8);
        TeslaFX.strike([{ x: r.left + r.width / 2, y: r.top + r.height * 0.3 }], { duration: 1200, power: 2 });
      }

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`[tesla] popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
      finish();
    });
  });
}

// --- Dev-панель --------------------------------------------------------------

function setupDevPanel() {
  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 123456));
  });
  const strikeBtn = document.querySelector('[data-dev="strike"]');
  if (strikeBtn) {
    strikeBtn.addEventListener('click', () => {
      const line = PAYLINE_ROWS[Math.floor(Math.random() * PAYLINE_ROWS.length)];
      strikeWinningCells(line.map((row, col) => ({ row, col })), 1 + Math.random());
    });
  }
}

// --- Вьюпорт и фон -----------------------------------------------------------
//
// Игра нарисована в фиксированном дизайн-канвасе (размеры фонов), и #stage
// contain-масштабируется в .screen.
const DESIGN = { desktop: { w: 1280, h: 930 }, mobile: { w: 720, h: 1280 } };

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

// Арт один на обе раскладки (сцена, рама, катушки) — меняет его только CSS.
function setDeviceArt() {}

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
  for (const f of ['logo.png', 'scene_ext.jpg', 'cabinet.png', 'coil_l.png', 'coil_r.png']) {
    tasks.push(track(preloadImage(assetSrc(`img/${f}`))));
  }
  for (const f of ['face', 'mini', 'minor', 'major', 'grand']) tasks.push(track(preloadImage(coinFaceSrc(f))));
  // Скелеты символов: без прогрева первый выигрыш ждал бы загрузку атласа уже
  // после приземления и подсветился бы с задержкой.
  if (spineStage) {
    for (const code of SYMBOL_CODES) tasks.push(track(loadSymbolResource(code)));
    tasks.push(track(SpineEngine.SpineResource.load(spineStage.assetManager, spineFolder('zap'), { premultipliedAlpha: true })));
  }
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // обязан отработать до applyStaticContentOffset
  // Канвас анимаций поднимаем до сборки сетки: ячейки при создании уже могут
  // попросить скелет.
  const canvasEl = document.getElementById('spineCanvas');
  if (canvasEl && window.SpineEngine && window.spine) {
    try {
      spineStage = new SpineEngine.SpineStage(canvasEl);
    } catch (err) {
      console.error('[tesla] не поднялся WebGL-канвас Spine — играем на статике:', err);
      spineStage = null;
    }
  }
  const teslaEl = document.getElementById('teslaCanvas');
  if (teslaEl && window.TeslaFX) TeslaFX.init(teslaEl);
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  window.addEventListener('orientationchange', handleResize);

  buildReelGrid();
  setDeviceArt();
  setupDevPanel();

  await preloadAssets();
  // Корпус грузится позже сетки, а высота ячейки меряется по окну — после
  // загрузки арта пересчитываем, иначе первый спин поедет со старым шагом.
  readCellDims();
  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
