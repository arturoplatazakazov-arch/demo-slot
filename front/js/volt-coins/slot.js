// Volt Coins — 3x3 classic Hold & Win.
//
// Каркас (дизайн-канвас, колонки под окном рамы, раунд, который сервер решил
// целиком, а клиент проигрывает респин за респином) — от
// ../uniqorn-shaolin-struggles. Отличия по продукту:
//
//   * Hold & Win классический: 3+ монеты где угодно открывают раунд, монеты
//     триггера залипают первыми (result.initial), пустые ячейки крутятся по
//     одной, все 9 — GRAND поверх суммы (result.full_grid_jackpot);
//   * на базе монета без номинала, номинал (xN / MINI / MINOR / MAJOR) она
//     получает только в раунде — .coin-face, «дисплей» поверх центра монеты;
//   * плашки джекпотов печатают сумму в валюте (множитель x текущая ставка);
//   * свет — Spine (window.VoltFx, js/volt-coins/fx.js): катушки, дверь,
//     рама, лого, вин-линии, символы, дуги разрядов. Всё, что тут зовёт Fx,
//     обязано работать и без него (CSS-фолбэк), поэтому вызовы идут через fx().

const ASSET_ROOT = 'img/volt-coins';

// 1:1 контракт с _SYMBOLS в app/seed/volt_coins.py: код == имя файла в symbols/.
const SYMBOL_CODES = ['horseshoe', 'star', 'bar', 'bell', 'ingot', 'diamond', 'seven', 'wild', 'coin'];

const JACKPOT_TIERS = ['mini', 'minor', 'major', 'grand'];
// Зеркало JACKPOT_VALUES сида. Порядок = порядок плашек слева направо:
// от меньшего к большему, GRAND справа (решение по макету, 2026-10-13).
const JACKPOT_LADDER = [
  { tier: 'mini', name: 'MINI', value: 20 },
  { tier: 'minor', name: 'MINOR', value: 50 },
  { tier: 'major', name: 'MAJOR', value: 250 },
  { tier: 'grand', name: 'GRAND', value: 1000 },
];
const JACKPOT_VALUE_BY_TIER = Object.fromEntries(JACKPOT_LADDER.map((j) => [j.tier, j.value]));

const COIN_STATE_ART = ['coin_value', 'coin_mini', 'coin_minor', 'coin_major'];

// = PAYLINES сида (ряд на каждом барабане). Три монеты на любой из них
// открывают Hold & Win (hold_and_win trigger_mode "payline").
const PAYLINES = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];

// В прокрутке не мелькают монеты: мелькнувший триггер читается как обман.
const FILLER_CODES = SYMBOL_CODES.filter((code) => code !== 'coin');

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}

// Fx-хук: без WebGL/ассетов window.VoltFx нет или он не ready — тогда молча
// ничего, CSS уже показывает своё.
function fx(name, ...args) {
  const F = window.VoltFx;
  if (!F || !F.ready || typeof F[name] !== 'function') return undefined;
  try {
    return F[name](...args);
  } catch (err) {
    console.warn(`[volt-fx] ${name} failed`, err);
    return undefined;
  }
}

const GRID_COLS = 3;
const GRID_ROWS = 3;

const SYMBOL_LAYOUT = [
  ['seven', 'diamond', 'bell'],
  ['ingot', 'wild', 'coin'],
  ['bar', 'star', 'horseshoe'],
];

const WIN_PULSE_MS = 620;
const FX_SYMBOL_MS = 1100;   // длина клипа символа в fx/symbols
const LAND_BOUNCE_MS = 260;
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;
const DIM_TRANSITION_MS = 320;
const WIN_LOOP_PAUSE_MS = 450;

const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const REEL_CLEAR_MS = 260;
const ANTICIPATION_PREROLL_MS = 1500;
const ANTICIPATION_PREROLL_FILLER_COUNT = 22;

let cellW = 220;
let cellH = 174;
let rowStep = cellH;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => {
    const value = parseFloat(cs.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  cellW = num('--cell-w', 220);
  cellH = num('--cell-h', 174);
  rowStep = cellH;
}

let cellInfos = [];
let reelCols = [];
let reelsBusy = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomSymbolCode() {
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

// --- Джекпоты ----------------------------------------------------------------

function formatAmount(n) {
  // «10 000» — как в ТЗ заказчика, тонкая неразрывная шпация между тысячами.
  return Math.round(Number(n)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function buildJackpotRow() {
  const row = document.getElementById('jpRow');
  if (!row) return;
  row.innerHTML = '';
  for (const { tier, name } of JACKPOT_LADDER) {
    const plate = document.createElement('div');
    plate.className = `jp jp--${tier}`;
    plate.dataset.tier = tier;
    plate.innerHTML = `
      <span class="jp__plate"></span>
      <span class="jp__name">${name}</span>
      <span class="jp__value" data-jp-value></span>
    `;
    row.appendChild(plate);
  }
}

let jackpotBet = 10;
function setJackpotBet(bet) {
  jackpotBet = bet;
  for (const { tier, value } of JACKPOT_LADDER) {
    const el = document.querySelector(`.jp--${tier} [data-jp-value]`);
    if (el) el.textContent = formatAmount(value * bet);
  }
}

// --- Ячейки ------------------------------------------------------------------

function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('volt-coins', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function applyCellFlags(cell, code) {
  cell.classList.toggle('is-coin', code === 'coin');
  cell.classList.toggle('is-blank', code === 'blank');
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  applyCellFlags(cell, code);
  const img = document.createElement('img');
  img.alt = code;
  img.decoding = 'async';
  if (code === 'blank') {
    img.style.visibility = 'hidden';
  } else {
    img.src = symbolSrc(code);
    img.addEventListener('error', () => {
      img.classList.add('is-missing');
      console.warn(`[volt] no art for symbol code "${code}"`);
    }, { once: true });
  }
  applyStaticContentOffset(img, code);
  cell.appendChild(img);
  return { cell, img };
}

function buildReelGrid() {
  const gridEl = document.getElementById('reelGrid');
  gridEl.innerHTML = '';
  readCellDims();
  cellInfos = [];
  reelCols = [];
  for (let col = 0; col < GRID_COLS; col++) {
    const colEl = document.createElement('div');
    colEl.className = 'reel__col';
    colEl.style.left = `${col * cellW}px`;
    const stripEl = document.createElement('div');
    stripEl.className = 'reel__strip';
    colEl.appendChild(stripEl);
    gridEl.appendChild(colEl);
    reelCols.push({ colEl, stripEl });
    for (let row = 0; row < GRID_ROWS; row++) {
      const symbol = SYMBOL_LAYOUT[row][col];
      const { cell, img } = createCellNode(symbol);
      stripEl.appendChild(cell);
      const info = { symbol, row, col, cell, img, winLoopTimeout: null, coinFace: null, fxInst: null };
      cell.addEventListener('click', () => previewSymbolWin(info));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
}

function dropSymbolFx(info) {
  if (info.fxInst) {
    fx('dropSymbol', info.fxInst);
    info.fxInst = null;
  }
  info.cell.classList.remove('is-fx');
}

function clearCellAnimation(info) {
  info.winToken = (info.winToken || 0) + 1;
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  dropSymbolFx(info);
  info.cell.classList.remove('is-winning', 'is-win-active', 'is-landing');
}

function teardownCellInstances() {
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  fx('hideLine');
  fx('setWin', false);
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    // Номинал НЕ снимаем: на старте спина монета уезжает вниз вместе со своим
    // числом (иначе на долю секунды мелькала голая монета с молнией). Номинал
    // снимает setCellSymbol, когда ячейку действительно подменяют.
    clearCellAnimation(info);
  }
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  clearCoinFace(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  applyCellFlags(info.cell, code);
  info.img.classList.remove('is-missing');
  if (code === 'blank') {
    info.img.removeAttribute('src');
    info.img.style.visibility = 'hidden';
  } else {
    info.img.src = symbolSrc(code);
    info.img.style.visibility = '';
  }
  applyStaticContentOffset(info.img, code);
  return Promise.resolve();
}

// --- Номинал монеты (только в раунде) -----------------------------------------

function clearCoinFace(info) {
  if (!info || !info.coinFace) return;
  info.coinFace.remove();
  info.coinFace = null;
  if (info.symbol === 'coin') info.img.src = symbolSrc('coin');
}

// Арт монеты в раунде: золото с пустой эмалью под номинал, у тиров джекпота —
// свой металл (MINI бронза, MINOR серебро, MAJOR золото с камнями). Подпись
// печатает клиент, чтобы суммы не разъезжались с математикой сида.
function coinFaceFor(kind, value) {
  if (JACKPOT_TIERS.includes(kind)) return { text: kind.toUpperCase(), cls: `is-tier is-${kind}`, art: `coin_${kind}` };
  return { text: `x${value}`, cls: '', art: 'coin_value' };
}

function makeCoinFace(face) {
  const el = document.createElement('span');
  el.className = face.cls ? `coin-face ${face.cls}` : 'coin-face';
  el.innerHTML = `<span class="coin-face__text"></span>`;
  el.firstChild.textContent = face.text;
  return el;
}

function showCoinFace(info, face) {
  clearCoinFace(info);
  if (face.art) info.img.src = symbolSrc(face.art);
  const el = makeCoinFace(face);
  info.cell.appendChild(el);
  info.coinFace = el;
}

// --- Показ выигрыша ----------------------------------------------------------

// Один «удар» выигрыша по ячейке: Spine-копия символа, если есть, иначе CSS-пульс.
function playWinAnimationOnce(info) {
  // Монета с номиналом: Spine-копия нарисовала бы голую монету без числа,
  // поэтому у неё CSS-пульс (число едет вместе с картинкой).
  if (info.symbol !== 'blank' && !info.coinFace) {
    dropSymbolFx(info);
    const inst = fx('symbol', info.cell, info.symbol);
    if (inst) {
      info.fxInst = inst;
      info.cell.classList.add('is-fx');
      // Клип кончается в позе статичного тайла — снимаем копию сразу, иначе
      // она так и светила бы поверх притушенной ячейки на следующей линии.
      return wait(FX_SYMBOL_MS).then(() => {
        if (info.fxInst === inst) dropSymbolFx(info);
      });
    }
  }
  info.cell.classList.remove('is-winning');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-winning');
  return wait(WIN_PULSE_MS).then(() => info.cell.classList.remove('is-winning'));
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

function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
}

let multiLineSequenceTimeout = null;
let multiLineToken = 0;

// Линии крутятся по одной: луч линии (Spine) + удар каждой её ячейки, всё
// остальное притушено. Одна линия — то же самое, просто по кругу.
function playLineSequence(lines) {
  const token = ++multiLineToken;
  let index = 0;
  const step = () => {
    if (token !== multiLineToken) return;
    const { payline, infos } = lines[index];
    const active = new Set(infos);
    for (const info of cellInfos) {
      if (!info) continue;
      setCellDimmed(info, !active.has(info));
      info.cell.classList.toggle('is-win-active', active.has(info));
    }
    fx('showLine', payline);
    Promise.all(infos.map((info) => playWinAnimationOnce(info))).then(() => {
      if (token !== multiLineToken) return;
      multiLineSequenceTimeout = setTimeout(() => {
        multiLineSequenceTimeout = null;
        index = (index + 1) % lines.length;
        step();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  step();
}

function playWinCells(lineWins) {
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  const lines = (lineWins || [])
    .filter((w) => w && w.positions && w.positions.length)
    .map((w) => ({
      payline: w.payline,
      infos: w.positions.map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean),
    }));
  if (!lines.length) return;
  fx('setWin', true);
  playLineSequence(lines);
}

const INLINE_WIN_AMOUNT_HOLD_MS = 1800;
let inlineWinAmountTimeout = null;

function showInlineWinAmount(amount) {
  const el = document.getElementById('reelWinAmount');
  if (!el) return;
  if (inlineWinAmountTimeout) clearTimeout(inlineWinAmountTimeout);
  el.dataset.amount = formatAmount(amount);
  el.classList.add('is-visible');
  inlineWinAmountTimeout = setTimeout(() => {
    inlineWinAmountTimeout = null;
    el.classList.remove('is-visible');
  }, INLINE_WIN_AMOUNT_HOLD_MS);
}

async function applyGrid(grid) {
  teardownCellInstances();
  const tasks = [];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      tasks.push(setCellSymbol(cellInfos[row * GRID_COLS + col], grid[row][col]));
    }
  }
  await Promise.all(tasks);
}

// --- Движение барабанов ------------------------------------------------------

let reelLoopGeneration = 0;
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  fx('spinStart');
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (gen !== reelLoopGeneration) return resolve();
      for (const { stripEl } of reelCols) {
        stripEl.style.transition = `transform ${REEL_CLEAR_MS}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
        stripEl.style.transform = `translateY(${rowStep * (GRID_ROWS + 1)}px)`;
      }
      setTimeout(resolve, REEL_CLEAR_MS + 40);
    }));
  });
}

function stopReelLoop() {
  reelsBusy = false;
  fx('anticipation', false);
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
}

// `faces` — по записи на ряд (null, где монеты нет): монета собирается в ленту
// уже со своим номиналом и падает с ним, а не получает его после остановки.
function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, faces = null) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    (async () => {
      await reelClearDone;
      await wait(delayMs);
      stripEl.style.transition = 'none';
      stripEl.innerHTML = '';
      const sequence = [
        ...finalCodes,
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, randomSymbolCode),
        ...Array.from({ length: prerollCount }, randomSymbolCode),
      ];
      const cellEls = sequence.map((code, index) => {
        const { cell, img } = createCellNode(code);
        const face = faces && index < GRID_ROWS ? faces[index] : null;
        if (face) {
          img.src = symbolSrc(face.art);
          cell.appendChild(makeCoinFace(face));
        }
        stripEl.appendChild(cell);
        return cell;
      });
      const landStartY = -(REEL_LAND_FILLER_COUNT * rowStep);

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
          for (const cell of cellEls.slice(GRID_ROWS)) cell.remove();
          stripEl.style.transition = 'none';
          stripEl.style.transform = 'translateY(0px)';
          resolve(cellEls.slice(0, GRID_ROWS));
        };
        const onTransitionEnd = (event) => {
          if (event.target === stripEl && event.propertyName === 'transform') finish();
        };
        stripEl.addEventListener('transitionend', onTransitionEnd);
        setTimeout(finish, REEL_LAND_DURATION_MS + 200);
      };

      if (isAnticipating) {
        const prerollStartY = -((REEL_LAND_FILLER_COUNT + prerollCount) * rowStep);
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
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const info = {
      symbol: code, row, col, cell,
      img: cell.querySelector('img'),
      winLoopTimeout: null,
      coinFace: cell.querySelector('.coin-face'),
      fxInst: null,
    };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    playLandBounce(info);
    // Приземлилась монета — короткая дуга от катушки (GDD: «приземление монеты»).
    if (code === 'coin') {
      fx('coinLanded', cell);
      Sound.playSfx('coinLand');
    }
  }
  return Promise.resolve();
}

// Раунд открывают 3 монеты В ЛИНИЮ, значит последний барабан решает, если
// хоть одна линия уже несёт монеты на первых двух. По серверной сетке — честно.
function anticipationColumns(codes) {
  const open = PAYLINES.some((line) => codes[line[0]][0] === 'coin' && codes[line[1]][1] === 'coin');
  return open ? [GRID_COLS - 1] : [];
}

// Номиналы монет базовой сетки (3x3, null без монеты) из coin_multiplier.
// Хранятся отдельно: пересборка сетки при повороте и возврат из раунда
// должны вернуть монетам их числа.
let lastBaseFaces = null;

function baseFacesFor(grid, coinMultiplier) {
  const faces = grid.map((row) => row.map(() => null));
  for (const pos of (coinMultiplier && coinMultiplier.positions) || []) {
    if (grid[pos.row]?.[pos.col] === 'coin') faces[pos.row][pos.col] = coinFaceFor(pos.kind, pos.value);
  }
  return faces;
}

function paintBaseFaces() {
  if (!lastBaseFaces) return;
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let col = 0; col < GRID_COLS; col++) {
      const face = lastBaseFaces[row][col];
      const info = cellInfos[row * GRID_COLS + col];
      if (face && info && info.symbol === 'coin') showCoinFace(info, face);
    }
  }
}

// Линии, на которых стоят три монеты (их подсветка перед входом в раунд).
function coinLines(grid) {
  const out = [];
  PAYLINES.forEach((line, i) => {
    if (line.every((row, col) => grid[row][col] === 'coin')) out.push(i + 1);
  });
  return out;
}

async function landReels(grid, coinMultiplier = null) {
  reelsBusy = true;
  try {
    await landReelsInner(grid, coinMultiplier);
  } finally {
    reelsBusy = false;
    await flushDeviceRebuild();
  }
}

async function landReelsInner(grid, coinMultiplier) {
  teardownCellInstances();
  const faces = baseFacesFor(grid, coinMultiplier);
  lastBaseFaces = faces;
  const columnCodes = (col) => [grid[0][col], grid[1][col], grid[2][col]];
  const columnFaces = (col) => [faces[0][col], faces[1][col], faces[2][col]];
  const antic = anticipationColumns(grid);
  const firstAnticipationCol = antic.length ? Math.min(...antic) : GRID_COLS;

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = columnCodes(col);
    leadTasks.push(
      landReel(col, finalCodes, col * REEL_LAND_STAGGER_MS, false, columnFaces(col))
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes)),
    );
  }
  await Promise.all(leadTasks);
  if (firstAnticipationCol === GRID_COLS) {
    fx('spinStop');
    return;
  }

  Sound.playSfx('anticipation');
  // GDD: «антиципация на 3-м барабане — постепенный заряд катушек».
  fx('anticipation', true);
  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const { stripEl } = reelCols[col];
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const finalCodes = columnCodes(col);
    reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, 0, true, columnFaces(col));
    await settleColumnCells(cellEls, col, finalCodes);
  }
  fx('anticipation', false);
  fx('spinStop');
}

// --- Затемнение и режимы -----------------------------------------------------

let dimActiveCount = 0;
let opaqueDimActiveCount = 0;

function pushScreenDim(opaque = false) {
  dimActiveCount += 1;
  document.getElementById('screenDim').classList.add('is-active');
  if (opaque) {
    opaqueDimActiveCount += 1;
    document.getElementById('screenDim').classList.add('is-opaque');
  }
}

function popScreenDim(opaque = false) {
  dimActiveCount = Math.max(0, dimActiveCount - 1);
  if (dimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-active');
  if (opaque) {
    opaqueDimActiveCount = Math.max(0, opaqueDimActiveCount - 1);
    if (opaqueDimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-opaque');
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

function currentMode() {
  return document.getElementById('screen').dataset.mode || 'base';
}

function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  fx('setMode', next);
}

const BONUS_INTRO_HOLD_MS = 2200;

// Вход в раунд без перелёта (заказчик: «анимацию полёта в сейф не надо»):
// катушки бьют разрядом в раму, дверь сейфа за барабанами проворачивается и
// «заряжается», затем короткая карточка HOLD & WIN на затемнении.
async function enterBonusMode() {
  if (currentMode() === 'bonus') return;
  Sound.playMusic('bonus');
  Sound.playSfx('anticipation');
  const charge = fx('holdWinStart');
  await wait(charge ? 1300 : 200);
  pushScreenDim(false);
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('holdWinIntro', 0, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('bonus');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(false);
}

function leaveBonusMode() {
  if (currentMode() === 'base') return Promise.resolve();
  Sound.playMusic('base');
  return withScreenDim(async () => {
    applyModeScreen('base');
    await wait(DIM_TRANSITION_MS);
  }, { opaque: true });
}

// --- Попапы ------------------------------------------------------------------

const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN' },
  megaWin: { title: 'MEGA WIN' },
  epicWin: { title: 'EPIC WIN' },
  holdWinIntro: { title: 'HOLD & WIN', sub: '3 RESPINS', hideAmount: true, coin: 'coin' },
  holdWinTotal: { title: 'TOTAL WIN', sub: 'HOLD & WIN' },
};

function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key] || { title: key };
  const root = document.createElement('div');
  root.className = 'game-popup';
  if (cfg.coin) {
    const coin = document.createElement('img');
    coin.className = 'game-popup__coin';
    coin.src = symbolSrc(cfg.coin);
    coin.alt = '';
    root.appendChild(coin);
  }
  if (cfg.sub) {
    const sub = document.createElement('div');
    sub.className = 'game-popup__sub';
    sub.textContent = cfg.sub;
    root.appendChild(sub);
  }
  const title = document.createElement('div');
  title.className = 'game-popup__title';
  title.textContent = cfg.title;
  root.appendChild(title);
  if (!cfg.hideAmount) {
    const amountEl = document.createElement('div');
    amountEl.className = 'game-popup__amount';
    amountEl.textContent = formatAmount(amount);
    root.appendChild(amountEl);
  }
  return root;
}

const BIG_WIN_KEYS = new Set(['bigWin', 'megaWin', 'epicWin']);

function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = true, opaque = false } = {}) {
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
      if (dimmed) popScreenDim(opaque);
      if (BIG_WIN_KEYS.has(key)) fx('bigWin', false);
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
      void node.offsetWidth;
      node.classList.add('is-in');
      // GDD: Big Win — дуги катушек на пике счётчика.
      if (BIG_WIN_KEYS.has(key)) fx('bigWin', true);
      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`[volt] popup "${key}" failed:`, err);
      finish();
    });
  });
}

function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Награда джекпота --------------------------------------------------------

const JACKPOT_AWARD_HOLD_MS = 2200;
const TIER_COLORS = {
  mini: ['#df8d52', '#ffd0a6'],
  minor: ['#cfd8e4', '#ffffff'],
  major: ['#ffc93c', '#fff0a8'],
  grand: ['#bfefff', '#ffffff'],
};

function playJackpotAward(tier) {
  const value = JACKPOT_VALUE_BY_TIER[tier];
  if (!value) return Promise.resolve();
  return new Promise((resolve) => {
    let node = null;
    let done = false;
    const plate = document.querySelector(`.jp--${tier}`);
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safety);
      if (node) node.remove();
      if (plate) plate.classList.remove('is-won');
      popScreenDim(false);
      resolve();
    };
    const safety = setTimeout(finish, JACKPOT_AWARD_HOLD_MS + 8000);
    (async () => {
      Sound.playSfx('jackpotWin');
      if (plate) plate.classList.add('is-won');
      if (tier === 'grand') fx('grandDischarge');
      pushScreenDim(false);
      await wait(DIM_TRANSITION_MS);
      node = document.createElement('div');
      node.className = 'game-popup is-jackpot';
      const [c, lt] = TIER_COLORS[tier];
      node.style.setProperty('--tier-color', c);
      node.style.setProperty('--tier-lt', lt);
      node.innerHTML = `
        <img class="game-popup__coin" src="${symbolSrc(tier === 'grand' ? 'coin' : `coin_${tier}`)}" alt="">
        <div class="game-popup__sub">${tier === 'grand' ? '9 / 9 — JACKPOT' : 'JACKPOT'}</div>
        <div class="game-popup__title">${tier.toUpperCase()}</div>
        <div class="game-popup__amount">${formatAmount(value * jackpotBet)}</div>
      `;
      document.getElementById('screen').appendChild(node);
      void node.offsetWidth;
      node.classList.add('is-in');
      await wait(POPUP_ENTER_MS + JACKPOT_AWARD_HOLD_MS);
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error('[volt] jackpot award failed:', err);
      finish();
    });
  });
}

// --- Диалог покупки ----------------------------------------------------------

let buyDialogOpen = false;

function showBuyBonusDialog({ betSteps, betIndex, costMultiplier, currency, balance }) {
  if (buyDialogOpen) return Promise.resolve({ confirmed: false, betIndex });
  buyDialogOpen = true;
  return new Promise((resolve) => {
    let index = betIndex;
    pushScreenDim(false);
    Sound.playSfx('popupOpen');
    const node = document.createElement('div');
    node.className = 'buy-dialog';
    node.innerHTML = `
      <div class="buy-dialog__title">BUY HOLD &amp; WIN</div>
      <div class="buy-dialog__note" data-note></div>
      <div class="buy-dialog__price" data-price></div>
      <div class="buy-dialog__bet">
        <button class="buy-dialog__step" data-step="-1" type="button" aria-label="Уменьшить ставку">−</button>
        <span class="buy-dialog__bet-value" data-bet></span>
        <button class="buy-dialog__step" data-step="1" type="button" aria-label="Увеличить ставку">+</button>
      </div>
      <div class="buy-dialog__actions">
        <button class="buy-dialog__answer buy-dialog__answer--no" data-answer="0" type="button" aria-label="Отмена">✕</button>
        <button class="buy-dialog__answer buy-dialog__answer--yes" data-answer="1" type="button" aria-label="Купить раунд">✓</button>
      </div>
    `;
    document.getElementById('screen').appendChild(node);
    void node.offsetWidth;
    node.classList.add('is-in');
    const render = () => {
      const bet = betSteps[index];
      const cost = bet * costMultiplier;
      node.querySelector('[data-price]').textContent = `${formatAmount(cost)} ${currency}`;
      node.querySelector('[data-bet]').textContent = `BET ${formatAmount(bet)}`;
      const affordable = balance == null || cost <= balance;
      const yes = node.querySelector('[data-answer="1"]');
      yes.disabled = !affordable;
      yes.style.opacity = affordable ? '' : '0.35';
      node.querySelector('[data-note]').textContent = affordable
        ? 'Раунд запускается сразу, ставка списывается один раз'
        : 'Не хватает баланса — уменьшите ставку';
    };
    render();
    let answered = false;
    const answer = (confirmed) => {
      if (answered) return;
      answered = true;
      Sound.playSfx('click');
      node.classList.remove('is-in');
      setTimeout(() => {
        node.remove();
        popScreenDim(false);
        buyDialogOpen = false;
        resolve({ confirmed, betIndex: index });
      }, POPUP_EXIT_MS);
    };
    node.querySelectorAll('[data-step]').forEach((btn) => {
      btn.addEventListener('click', () => {
        Sound.playSfx('click');
        index = Math.min(betSteps.length - 1, Math.max(0, index + Number(btn.dataset.step)));
        render();
      });
    });
    node.querySelectorAll('[data-answer]').forEach((btn) => {
      btn.addEventListener('click', () => answer(btn.dataset.answer === '1'));
    });
  });
}

// --- Hold & Win --------------------------------------------------------------
//
// Истинный hold: залипшая монета не двигается, крутятся только пустые ячейки,
// каждая своей мини-лентой.

const RESPIN_COUNT = 3;                 // = hold_and_win.respin_count сида
const HOLD_AND_WIN_RESPIN_PAUSE_MS = 700;
const HW_CELL_SPIN_MS = 620;
const HW_CELL_SPIN_FILLER = 8;
const HW_COIN_FILLER_CHANCE = 0.07;     // = respin_land_weights coin 7 / 100

const coinKey = (row, col) => `${row}-${col}`;
let holdAndWinLocked = null;

function buildHoldAndWinGrid(locked) {
  const grid = [[], [], []];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      grid[row][col] = locked.has(coinKey(row, col)) ? 'coin' : 'blank';
    }
  }
  return grid;
}

function paintLockedCoins(locked) {
  for (const info of cellInfos) if (info) clearCoinFace(info);
  for (const [key, coin] of locked) {
    const [row, col] = key.split('-').map(Number);
    const info = cellInfos[row * GRID_COLS + col];
    if (info) showCoinFace(info, coinFaceFor(coin.kind, coin.value));
  }
}

function setRespinCounter(value, reset = false) {
  const el = document.getElementById('respinValue');
  if (!el) return;
  el.textContent = value;
  if (reset) {
    el.classList.remove('is-reset');
    void el.offsetWidth;
    el.classList.add('is-reset');
  }
}

function spinCellTo(info, code, delayMs, face = null) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const spinner = document.createElement('div');
      spinner.className = 'cell-spinner';
      const strip = document.createElement('div');
      strip.className = 'cell-spinner__strip';
      const filler = () => (Math.random() < HW_COIN_FILLER_CHANCE ? 'coin' : 'blank');
      for (const [i, itemCode] of [code, ...Array.from({ length: HW_CELL_SPIN_FILLER }, filler)].entries()) {
        const item = document.createElement('div');
        if (i === 0 && face) {
          item.appendChild(makeCoinFace(face));
          item.style.position = 'relative';
        }
        item.className = 'cell-spinner__item';
        if (itemCode !== 'blank') {
          const img = document.createElement('img');
          img.decoding = 'async';
          img.src = symbolSrc(i === 0 && face ? face.art : itemCode === 'coin' ? 'coin_value' : itemCode);
          item.insertBefore(img, item.firstChild);
        }
        strip.appendChild(item);
      }
      spinner.appendChild(strip);
      info.cell.appendChild(spinner);
      info.img.style.visibility = 'hidden';
      strip.style.transform = `translateY(${-HW_CELL_SPIN_FILLER * rowStep}px)`;
      void strip.offsetHeight;
      strip.style.transition = `transform ${HW_CELL_SPIN_MS}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
      strip.style.transform = 'translateY(0px)';
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        spinner.remove();
        setCellSymbol(info, code).then(() => {
          if (face) showCoinFace(info, face);
          if (code !== 'blank') playLandBounce(info);
          resolve();
        });
      };
      strip.addEventListener('transitionend', (event) => {
        if (event.propertyName === 'transform') finish();
      });
      setTimeout(finish, HW_CELL_SPIN_MS + 250);
    }, delayMs);
  });
}

async function respinEmptyCells(locked, landing) {
  const tasks = [];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const key = coinKey(row, col);
      if (locked.has(key)) continue;
      const info = cellInfos[row * GRID_COLS + col];
      if (!info) continue;
      const coin = landing.get(key);
      tasks.push(spinCellTo(info, coin ? 'coin' : 'blank', col * REEL_LAND_STAGGER_MS,
        coin ? coinFaceFor(coin.kind, coin.value) : null));
    }
  }
  await Promise.all(tasks);
}

// Монеты триггера уже лежат на поле — они залипают и показывают номиналы,
// всё остальное гаснет в пустые ячейки. Раунд ждёт нажатия Spin.
async function enterHoldAndWinWaitingState(result) {
  const locked = new Map();
  for (const c of result.initial || []) locked.set(coinKey(c.row, c.col), { value: c.value, kind: c.kind });
  // Сначала — что сработало: линия из трёх монет загорается молнией, её
  // монеты пульсируют, остальное притухает. Потом вход в раунд.
  const grid = buildHoldAndWinGrid(locked);
  const lines = coinLines(grid);
  const lineCells = new Set();
  for (const n of lines) PAYLINES[n - 1].forEach((row, col) => lineCells.add(row * GRID_COLS + col));
  for (const [i, info] of cellInfos.entries()) {
    if (!info) continue;
    if (lineCells.has(i)) previewSymbolWin(info);
    else setCellDimmed(info, !locked.has(coinKey(info.row, info.col)));
  }
  if (lines.length) {
    fx('setWin', true);
    fx('showLine', lines[0]);
    for (const i of lineCells) fx('coinLanded', cellInfos[i].cell);
  }
  Sound.playSfx('coinLand');
  await wait(1500);
  teardownCellInstances();
  await enterBonusMode();
  await applyGrid(buildHoldAndWinGrid(locked));
  holdAndWinLocked = locked;
  paintLockedCoins(locked);
  setRespinCounter(RESPIN_COUNT);
  return locked;
}

async function runHoldAndWinSequence(result, locked, baseGrid = null) {
  const wonTiers = [];
  const noteTier = (kind) => {
    if (JACKPOT_TIERS.includes(kind) && !wonTiers.includes(kind)) wonTiers.push(kind);
  };
  for (const [, coin] of locked) noteTier(coin.kind);

  let respinsLeft = RESPIN_COUNT;
  for (const respin of result.respins) {
    const landing = new Map(respin.landed.map((c) => [coinKey(c.row, c.col), { value: c.value, kind: c.kind }]));
    await respinEmptyCells(locked, landing);
    for (const [key, coin] of landing) locked.set(key, coin);
    holdAndWinLocked = locked;
    paintLockedCoins(locked);

    respinsLeft = respin.landed.length ? RESPIN_COUNT : respinsLeft - 1;
    setRespinCounter(Math.max(0, respinsLeft), respin.landed.length > 0);

    for (const c of respin.landed) {
      noteTier(c.kind);
      const info = cellInfos[c.row * GRID_COLS + c.col];
      if (!info) continue;
      fx('coinLanded', info.cell);
      // Джекпот-монета: разряд идёт от неё к своей плашке (GDD).
      if (JACKPOT_TIERS.includes(c.kind)) {
        const plate = document.querySelector(`.jp--${c.kind}`);
        fx('arcToPlate', info.cell, plate);
        if (plate) {
          plate.classList.remove('is-hit');
          void plate.offsetWidth;
          plate.classList.add('is-hit');
        }
      }
    }
    if (respin.landed.length) Sound.playSfx('coinLand');
    await wait(HOLD_AND_WIN_RESPIN_PAUSE_MS);
  }

  await wait(300);
  for (const tier of wonTiers) await playJackpotAward(tier);
  // 9/9: GRAND сверху суммы монет — полный разряд обеих катушек.
  if (result.full_grid_jackpot) await playJackpotAward(result.full_grid_jackpot);

  Sound.playSfx('roundTotalWin');
  await playPopup('holdWinTotal', result.total_win, 3000);
  holdAndWinLocked = null;
  if (baseGrid) {
    await applyGrid(baseGrid);
    paintBaseFaces();
  }
  await leaveBonusMode();
}

// --- Dev ---------------------------------------------------------------------

function setupDevPanel() {
  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 12345));
  });
  const jp = document.getElementById('devJackpot');
  if (jp) {
    jp.addEventListener('click', async () => {
      for (const tier of JACKPOT_TIERS) {
        const plate = document.querySelector(`.jp--${tier}`);
        const info = cellInfos[4];
        if (info) fx('arcToPlate', info.cell, plate);
        await wait(500);
        await playJackpotAward(tier);
      }
    });
  }
  const lines = document.getElementById('devLines');
  if (lines) {
    lines.addEventListener('click', () => {
      teardownCellInstances();
      const rows = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];
      playWinCells(rows.map((r, i) => ({
        payline: i + 1,
        positions: r.map((row, col) => ({ row, col })),
      })));
    });
  }
  const light = document.getElementById('devLight');
  if (light) {
    light.addEventListener('click', () => {
      const off = !document.body.classList.contains('lights-off');
      document.body.classList.toggle('lights-off', off);
      light.setAttribute('aria-pressed', String(off));
      fx('setLights', !off);
    });
  }
}

// --- Вьюпорт и фон -----------------------------------------------------------

const DESIGN = { desktop: { w: 1920, h: 1040 }, mobile: { w: 800, h: 1450 } };
// Натуральные размеры фонов — по ним считается cover-прямоугольник для
// привязки Spine-фона (катушки нарисованы в картинке).
const BG_SIZE = { desktop: { w: 1798, h: 875 }, mobile: { w: 931, h: 1690 } };

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
  layoutBg();
}

function layoutBg() {
  const screenEl = document.getElementById('screen');
  const anchor = document.getElementById('bgAnchor');
  if (!anchor) return;
  const vw = screenEl.clientWidth;
  const vh = screenEl.clientHeight;
  const b = isMobileLayout() ? BG_SIZE.mobile : BG_SIZE.desktop;
  const k = Math.max(vw / b.w, vh / b.h);
  const w = b.w * k;
  const h = b.h * k;
  Object.assign(anchor.style, {
    left: `${(vw - w) / 2}px`, top: `${(vh - h) / 2}px`, width: `${w}px`, height: `${h}px`,
  });
}

function setBackground() {
  const name = isMobileLayout() ? 'bg_mob' : 'bg_desk';
  document.getElementById('bgLayer').src = `${ASSET_ROOT}/img/${name}.jpg`;
}

let lastMobile = null;
let pendingDeviceRebuild = false;

async function handleResize() {
  updateStageScale();
  const nowMobile = isMobileLayout();
  if (nowMobile === lastMobile) return;
  lastMobile = nowMobile;
  setBackground();
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
  if (holdAndWinLocked) paintLockedCoins(holdAndWinLocked);
  else paintBaseFaces();
}

// --- Прелоадер ---------------------------------------------------------------

const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const img = new Image();
  img.src = src;
  return img.decode ? img.decode() : new Promise((res) => { img.onload = res; img.onerror = res; });
}

function preloadAssets() {
  const P = window.Preloader;
  const track = (promise) => {
    if (P) P.add(1);
    return Promise.resolve(promise).catch(() => {}).finally(() => { if (P) P.step(); });
  };
  const tasks = [];
  for (const code of [...SYMBOL_CODES, ...COIN_STATE_ART]) tasks.push(track(preloadImage(symbolSrc(code))));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/logo.png`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/frame.png`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/${isMobileLayout() ? 'bg_mob' : 'bg_desk'}.jpg`)));
  if (window.VoltFx) tasks.push(track(window.VoltFx.load()));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));
  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load();
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  window.addEventListener('orientationchange', handleResize);
  buildJackpotRow();
  setJackpotBet(jackpotBet);
  buildReelGrid();
  setBackground();
  setupDevPanel();
  await preloadAssets();
  if (window.Preloader) window.Preloader.done();
  window.__slot = { cellInfos };
}

init();
