// Lucky Miami 3 — 3x3 classic, five lines, no bonus round.
//
// Сцена и движение барабанов взяты у ../uniqorn-shaolin-struggles (та же 3x3
// раскладка, тот же дизайн-канвас, та же подача целиком на PNG + CSS), но
// СИЛЬНО короче: в игре нет ни монет с номиналом, ни Hold & Win, ни фриспинов,
// ни покупки — а значит нет ни второго режима экрана, ни поклеточной
// прокрутки, ни меток, которые надо переживать пересборку сетки. Остаётся
// ровно спин: увезти старые символы вниз, дождаться сервера, уронить новые,
// подсветить выигравшие линии.
//
// Отличие в РАЗМЕТКЕ от донора: там колонки лежат в одном общем окне обрезки,
// здесь у каждой колонки своё (три отдельные рамки на референсе), поэтому
// сетка строится как три .reel__box, а не как один .reel__grid.

const ASSET_ROOT = 'img/lucky-miami-3';

// Коды, которые может выдать бэкенд. 1:1 контракт с _SYMBOLS в
// app/seed/lucky_miami_3.py: код == имя файла в symbols/.
const SYMBOL_CODES = [
  'cherry', 'lemon', 'plum', 'grape', 'watermelon', 'bell', 'bar', 'seven',
];

// Крутить можно всем: спец-символов, чьё мелькание врало бы о почти-выигрыше,
// в игре нет вовсе.
const FILLER_CODES = SYMBOL_CODES;

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}

const GRID_COLS = 3;
const GRID_ROWS = 3;

// Зеркалит PAYLINES в app/seed/lucky_miami_3.py — нужен только для антиципации
// (выплаты считает сервер). row index: 0=top, 1=mid, 2=bottom.
const PAYLINE_ROWS = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];

// Раскладка attract-режима до первого спина — сетка с референсного скрина.
const SYMBOL_LAYOUT = [
  ['bell', 'lemon', 'grape'],
  ['cherry', 'lemon', 'grape'],
  ['cherry', 'bell', 'bar'],
];

// Длительности; числа обязаны совпадать с кейфреймами в CSS.
const WIN_PULSE_MS = 620;
const LAND_BOUNCE_MS = 260;
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;
const DIM_TRANSITION_MS = 320;
const WIN_LOOP_PAUSE_MS = 500;

const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const REEL_CLEAR_MS = 260;

// Геометрия ячейки живёт в CSS (--cell-h), чтобы десктопный и портретный блоки
// оставались единственным источником правды.
let rowStep = 200;
function readCellDims() {
  const value = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--cell-h'));
  rowStep = Number.isFinite(value) ? value : 200;
}

let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];
// true с нажатия спина и до приземления — окно, в котором сетку нельзя
// пересобирать под новое устройство.
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

// --- Ячейки ------------------------------------------------------------------

function applyStaticContentOffset(img, code) {
  // Символы нарезаны в один квадрат с общим оптическим центром, так что по
  // умолчанию сдвигать нечего; живой оверрайд из Anim Lab главнее.
  const override = window.SlotCalibration && window.SlotCalibration.get('lucky-miami-3', code);
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
    console.warn(`[miami] no art for symbol code "${code}"`);
  }, { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  return { cell, img };
}

// Три отдельные колонки, у каждой своя рамка и своё окно обрезки; между ними —
// ромбовидные огоньки (чисто декор, поэтому вне колонок).
function buildReelGrid() {
  const reelEl = document.getElementById('reel');
  reelEl.innerHTML = '';
  readCellDims();
  cellInfos = [];
  reelCols = [];

  for (let col = 0; col < GRID_COLS; col++) {
    const boxEl = document.createElement('div');
    boxEl.className = 'reel__box';
    const windowEl = document.createElement('div');
    windowEl.className = 'reel__window';
    const stripEl = document.createElement('div');
    stripEl.className = 'reel__strip';
    windowEl.appendChild(stripEl);
    boxEl.appendChild(windowEl);
    reelEl.appendChild(boxEl);
    reelCols.push({ colEl: boxEl, stripEl });

    for (let row = 0; row < GRID_ROWS; row++) {
      const symbol = SYMBOL_LAYOUT[row][col];
      const { cell, img } = createCellNode(symbol);
      stripEl.appendChild(cell);
      const info = { symbol, row, col, cell, img, winLoopTimeout: null };
      cell.addEventListener('click', () => previewSymbolWin(info));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }

  // Огоньки ставятся ПОСЛЕ колонок, по их фактическим позициям: считать их
  // из --cell-w/--box-* заново значило бы держать вторую копию геометрии.
  for (let gap = 1; gap < GRID_COLS; gap++) {
    const dot = document.createElement('span');
    dot.className = 'reel__dot';
    dot.style.left = `${reelCols[gap].colEl.offsetLeft - parseFloat(getComputedStyle(reelEl).gap || 0) / 2}px`;
    reelEl.appendChild(dot);
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
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
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

// --- Показ выигрыша ----------------------------------------------------------

function playWinAnimationOnce(info) {
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
// Барабан = .reel__strip внутри своего .reel__window; окно режет всё, что
// выехало за колонку. Фазы бесконечной прокрутки нет (как и в остальных играх
// проекта): по нажатию лежащие символы уезжают вниз, барабан стоит пустым,
// пока отвечает сервер, и финалы падают сверху. landReel ждёт reelClearDone,
// чтобы ни одна колонка не начала приземляться, пока старые ещё летят.

let reelLoopGeneration = 0;
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  setHintVisible(false);
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    // Страховка ЗА пределами rAF: в скрытой вкладке кадры не идут вовсе, а
    // всё, что запланировано внутри requestAnimationFrame, вместе с ними
    // никогда не выполнится — и спин, начатый перед уходом со вкладки, повис
    // бы навсегда (по возвращении слот остался бы с крутящимися барабанами).
    const safety = setTimeout(resolve, REEL_CLEAR_MS + 400);
    // Два rAF: целый кадр, чтобы transition:none и сброс трансформа применились
    // до старта падения.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (gen !== reelLoopGeneration) {
        clearTimeout(safety);
        return resolve();
      }
      for (const { stripEl } of reelCols) {
        stripEl.style.transition = `transform ${REEL_CLEAR_MS}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
        stripEl.style.transform = `translateY(${rowStep * (GRID_ROWS + 1)}px)`;
      }
      clearTimeout(safety);
      setTimeout(resolve, REEL_CLEAR_MS + 40);
    }));
  });
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

      stripEl.style.transition = `transform ${REEL_LAND_DURATION_MS}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
      stripEl.style.transform = 'translateY(0px)';
      setTimeout(() => Sound.playSfx(stopSound), Math.max(0, REEL_LAND_DURATION_MS - 200));

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
      setTimeout(finish, REEL_LAND_DURATION_MS + 200);
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
// спинов, и антиципация на каждой второй вишне перестала бы что-либо значить —
// с этим фильтром она выпадает примерно на 8% спинов.
const ANTICIPATION_CODES = new Set(['watermelon', 'bell', 'bar', 'seven']);

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
      landReel(col, finalCodes, col * REEL_LAND_STAGGER_MS)
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
const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN' },
  megaWin: { title: 'MEGA WIN' },
  epicWin: { title: 'EPIC WIN' },
};

function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key] || { title: key };
  const root = document.createElement('div');
  root.className = 'game-popup';

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

  const amountEl = document.createElement('div');
  amountEl.className = 'game-popup__amount';
  amountEl.textContent = Number(amount).toLocaleString('en-US');
  root.appendChild(amountEl);
  return root;
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
      void node.offsetWidth; // зафиксировать пред-входное состояние
      node.classList.add('is-in');

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`[miami] popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
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
const DESIGN = { desktop: { w: 1932, h: 940 }, mobile: { w: 780, h: 1416 } };

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

function setBackground() {
  const suffix = isMobileLayout() ? '_mob' : '';
  document.getElementById('bgLayer').src = `${ASSET_ROOT}/img/bg_base${suffix}.jpg`;
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
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/logo.png`)));
  const suffix = isMobileLayout() ? '_mob' : '';
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/bg_base${suffix}.jpg`)));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // обязан отработать до applyStaticContentOffset
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  window.addEventListener('orientationchange', handleResize);

  buildReelGrid();
  setBackground();
  setupDevPanel();

  await preloadAssets();
  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
