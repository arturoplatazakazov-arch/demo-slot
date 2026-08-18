// Miami Fruits 3 — рендер и анимации 3x3.
//
// Адаптировано с ../uniqorn-shaolin-struggles/slot.js: та же сетка, та же
// механика падающих лент и тот же приём подачи (спайна нет вообще, весь арт —
// PNG, а всё, что в других играх анимирует скелет, здесь делают CSS-классы).
//
// Отличие от донора — по продукту в игре НЕТ бонусов вообще: ни Hold & Win, ни
// монет-множителей, ни джекпотов, ни покупки, ни фриспинов. Остаётся чистый
// line pay по 5 линиям, поэтому из донора вычищены бонусный режим экрана,
// лестница джекпотов, метки номинала на монете и весь раунд респинов. Экран
// один, фон один, попап бывает только за размер выигрыша.

const ASSET_ROOT = 'img/miami-fruits-3';

// Версия арта в query. Символы и фоны лежат по постоянным путям, поэтому
// перерисованный PNG приезжает браузеру под тем же URL — и тот честно отдаёт
// старую картинку из кеша, пока пользователь не сделает жёсткую перезагрузку.
// Для страницы, где арт меняется по ходу работы, это выглядит как «ничего не
// изменилось». Подняли символ — поднимите здесь число, ровно как у ?v= на css и
// js в разметке.
const ASSET_VERSION = 2;
const versioned = (path) => `${path}?v=${ASSET_VERSION}`;

// Коды, которые может выдать бэкенд. 1:1 контракт с _SYMBOLS в
// app/seed/miami_fruits_3.py: код == имя файла в symbols/.
const SYMBOL_CODES = [
  'cherry', 'lemon', 'plum', 'grape', 'bell', 'bar', 'star', 'seven',
];

// Бонусных символов нет, так что засыпать крутящийся барабан можно чем угодно —
// «почти выпавшего» триггера, который нельзя показывать в размытии, тут не
// существует.
const FILLER_CODES = SYMBOL_CODES;

function symbolSrc(code) {
  return versioned(`${ASSET_ROOT}/symbols/${code}.png`);
}

const GRID_COLS = 3;
const GRID_ROWS = 3;

// Зеркало PAYLINES из сида — фронт читает их только ради антиципации (см.
// anticipationColumns). Значение — индекс ряда на каждом из трёх барабанов.
const PAYLINES = [
  [1, 1, 1],
  [0, 0, 0],
  [2, 2, 2],
  [0, 1, 2],
  [2, 1, 0],
];

// На что стоит задерживать последний барабан: пара дорогих символов на одной
// линии — это настоящий «почти выигрыш», а пара вишен — нет.
const ANTICIPATION_CODES = new Set(['seven', 'star', 'bar']);

// Раскладка attract-режима до первого спина — та же, что на макете игры.
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
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

// Геометрия ячейки живёт в CSS (--cell-w/--cell-h), чтобы десктопный и
// портретный блоки оставались единственным источником правды.
let cellW = 388;
let cellH = 229;
let rowStep = cellH;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => {
    const value = parseFloat(cs.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  cellW = num('--cell-w', 388);
  cellH = num('--cell-h', 229);
  rowStep = cellH;
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

// Поштучный масштаб символа поверх общей нарезки.
//
// Весь арт лежит в одном квадрате 512x512, а ячейка ШИРЕ, чем выше, поэтому
// object-fit: contain вписывает этот квадрат по ВЫСОТЕ — и по бокам всегда
// остаётся незанятое место. Широкому символу это стоит дорого: вывеска BAR
// занимает меньше половины высоты своего квадрата, то есть на барабане выходит
// заметно мельче фруктов, хотя платит больше них. Увеличить её пересборкой PNG
// нельзя — по ширине она уже почти упирается в край квадрата; растёт она
// именно в ту сторону, где у ячейки есть запас.
const SYMBOL_SCALE = {
  bar: 1.5,
  seven: 1.3,
};

function applyStaticContentOffset(img, code) {
  // Все символы нарезаны в один квадрат с общим оптическим центром, так что по
  // умолчанию сдвигать нечего; живой оверрайд из Anim Lab главнее.
  const override = window.SlotCalibration && window.SlotCalibration.get('miami-fruits-3', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  const scale = SYMBOL_SCALE[code] || 1;
  // Сдвиг и масштаб собираются в ОДИН transform: два CSS-правила на одно
  // свойство не складываются, а перебивают друг друга, и калибровка из Anim Lab
  // молча стёрла бы масштаб.
  const parts = [];
  if (dx !== 0 || dy !== 0) parts.push(`translate(${dx}px, ${dy}px)`);
  if (scale !== 1) parts.push(`scale(${scale})`);
  img.style.transform = parts.join(' ');
  // Тот же масштаб уезжает переменной в CSS: кейфреймы посадки и выигрыша тоже
  // анимируют transform и на время анимации перебивают инлайновый стиль
  // целиком — без этой переменной увеличенный символ прыгал бы к исходному
  // размеру на каждом приземлении.
  img.style.setProperty('--sym-scale', String(scale));
}

// Код без арта — это баг (бэкенд выдал символ, которого фронт не знает), и он
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
      const info = { symbol, row, col, cell, img, winLoopTimeout: null };
      cell.addEventListener('click', () => previewSymbolWin(info));
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

  // Фаза -1 играет все выигравшие ячейки разом, дальше группы крутятся по
  // одной, чтобы пересекающиеся линии можно было различить.
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
const INLINE_NOTICE_HOLD_MS = 2600;
let inlineWinAmountTimeout = null;

// Плашка по центру барабанов. Живёт в одном узле с суммой выигрыша, потому что
// показывать их одновременно всё равно незачем: либо спин отыграл и есть
// сумма, либо он не состоялся и есть причина.
function showInlineText(text, holdMs, extraClass = '') {
  const el = document.getElementById('reelWinAmount');
  if (!el) return;
  if (inlineWinAmountTimeout) {
    clearTimeout(inlineWinAmountTimeout);
    inlineWinAmountTimeout = null;
  }
  el.dataset.amount = text;
  el.classList.toggle('is-notice', extraClass === 'is-notice');
  el.classList.add('is-visible');
  inlineWinAmountTimeout = setTimeout(() => {
    inlineWinAmountTimeout = null;
    el.classList.remove('is-visible');
  }, holdMs);
}

function showInlineWinAmount(amount) {
  showInlineText(Number(amount).toLocaleString('en-US'), INLINE_WIN_AMOUNT_HOLD_MS);
}

// Причина, по которой спина не будет (нет сессии, запрос упал). Молчащая
// кнопка — худшее, что можно показать игроку: она читается как поломка игры.
function showInlineNotice(text) {
  showInlineText(text, INLINE_NOTICE_HOLD_MS, 'is-notice');
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
// Барабан = .reel__col с более высокой .reel__strip внутри; .reel__grid режет
// всё по окну корпуса, поэтому едущая лента исчезает за бортом.
//
// Фазы бесконечной прокрутки нет (как и в остальных играх проекта): по нажатию
// лежащие символы уезжают вниз, барабан стоит пустым, пока отвечает сервер, и
// финалы падают сверху. landReel ждёт reelClearDone, чтобы ни одна колонка не
// начала приземляться, пока старые символы ещё летят.

let reelLoopGeneration = 0;
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    // Два rAF: целый кадр, чтобы transition:none и сброс трансформа применились
    // до старта падения.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (gen !== reelLoopGeneration) return finish();
      for (const { stripEl } of reelCols) {
        stripEl.style.transition = `transform ${REEL_CLEAR_MS}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
        stripEl.style.transform = `translateY(${rowStep * (GRID_ROWS + 1)}px)`;
      }
      setTimeout(finish, REEL_CLEAR_MS + 40);
    }));
    // Страховка. rAF не гарантирован: в фоновой (или просто не перерисовываемой)
    // вкладке браузер его придерживает, и тогда обещание не резолвится НИКОГДА —
    // а его ждёт landReel, то есть спин повисает уже после того, как сервер
    // ответил. Симптом со стороны игрока ровно один: «нажал и ничего». Тот же
    // приём, что у transitionend ниже, — таймер, который доводит дело до конца.
    setTimeout(finish, REEL_CLEAR_MS + 400);
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

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, fillerFn = randomSymbolCode) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

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
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, fillerFn),
        ...Array.from({ length: prerollCount }, fillerFn),
      ];
      const cellEls = sequence.map((code) => {
        const { cell } = createCellNode(code);
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
        // Транзишен, который не выстрелил (скрытая вкладка, гонка стилей), не
        // должен подвесить спин.
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

// Ячейки уже собраны падающей лентой, поэтому здесь их НЕЛЬЗЯ переклеивать
// через setCellSymbol — остаётся завести на них info и сыграть посадку.
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
  return Promise.resolve();
}

// Барабан, на котором ещё может решиться линия: два одинаковых ДОРОГИХ символа
// на одной линии на первых двух барабанах — значит третий играет на выплату.
// Считается по уже известной (серверной) сетке, поэтому «почти выпало» здесь
// всегда честное, а не декоративное.
function anticipationColumns(grid) {
  for (const positions of PAYLINES) {
    const first = grid[positions[0]][0];
    if (first === grid[positions[1]][1] && ANTICIPATION_CODES.has(first)) return [2];
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
    const isAnticipating = anticipationSet.has(col);
    if (isAnticipating) reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, 0, isAnticipating);
    await settleColumnCells(cellEls, col, finalCodes);
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

// Жизненный цикл попапа (вход -> держим -> выход). Промис резолвится, только
// когда попап полностью отыграл. Любой выход идёт через ОДИН finish(), и он
// гарантированно отработает — иначе упавший попап оставил бы экран затемнённым
// навсегда.
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
  document.documentElement.style.setProperty('--design-w', `${d.w}px`);
  document.documentElement.style.setProperty('--design-h', `${d.h}px`);
  // Нулевой размер контейнера — это не «масштаб 0», это «мерить пока нечего».
  // Записать сюда 0 значит схлопнуть всю сцену в точку и оставить её такой до
  // первого события resize; в свёрнутой панели, в ещё не разложенном iframe и в
  // мини-аппе до прихода вьюпорта игра выглядела бы просто чёрным экраном.
  // Возвращаемся сюда из ResizeObserver, как только размер появится.
  if (vw <= 0 || vh <= 0) return;
  document.documentElement.style.setProperty('--stage-scale', String(Math.min(vw / d.w, vh / d.h)));
  readCellDims();
}

// Режим в игре один, так что фон различается только ориентацией.
function setBackground() {
  const suffix = isMobileLayout() ? '_mob' : '';
  document.getElementById('bgLayer').src = versioned(`${ASSET_ROOT}/img/bg_base${suffix}.jpg`);
}

// Геометрия ячейки разная на устройствах, а колонки несут пиксельные позиции,
// поэтому поворот экрана пересобирает сетку. Делать это посреди спина нельзя —
// пересборка сносит ячейки, которых ждёт анимация, — поэтому откладываем до
// конца спина.
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
  tasks.push(track(preloadImage(versioned(`${ASSET_ROOT}/img/logo.png`))));
  const suffix = isMobileLayout() ? '_mob' : '';
  tasks.push(track(preloadImage(versioned(`${ASSET_ROOT}/img/bg_base${suffix}.jpg`))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

// Загрузка калибровки не имеет собственного таймаута: это обычный fetch, и на
// сервере, который принял соединение и молчит, он висит СКОЛЬКО УГОДНО. Так как
// init() ждёт его первым, такой сервер оставлял бы игрока на прелоадере
// навсегда. Калибровка — это опциональные попиксельные сдвиги символов, без неё
// игра полностью работоспособна, поэтому ожиданию ставится потолок.
const CALIBRATION_TIMEOUT_MS = 4000;

async function loadCalibration() {
  try {
    await Promise.race([SlotCalibration.load(), wait(CALIBRATION_TIMEOUT_MS)]);
  } catch (err) {
    console.warn('[miami] calibration unavailable, using unshifted symbols:', err);
  }
}

async function init() {
  // ВСЯ загрузка — под try/finally, и прелоадер снимается в finally. Иначе любое
  // исключение по дороге (недокачанный шрифт, отвалившийся шаред-скрипт, кривой
  // асcет) навсегда оставляет игрока на экране загрузки: done() просто никогда
  // не вызовется, и это выглядит как «игра не запускается», хотя на самом деле
  // упала одна строка. Лучше показать игру без части украшений, чем не показать
  // вообще ничего.
  try {
    await loadCalibration(); // обязан отработать до applyStaticContentOffset
    Sound.playMusic('base');
    lastMobile = isMobileLayout();
    updateStageScale();
    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleResize);
    // Событие resize приходит только на смену размера ОКНА, а .screen может
    // получить свои габариты позже и без него — например, когда страницу
    // открыли в свёрнутой панели или в контейнере, который разложили уже после
    // загрузки. Наблюдатель ловит именно это.
    if (window.ResizeObserver) {
      new ResizeObserver(() => handleResize()).observe(document.getElementById('screen'));
    }

    buildReelGrid();
    setBackground();
    setupDevPanel();

    await preloadAssets();
    window.__slot = { cellInfos };
  } catch (err) {
    console.error('[miami] boot failed, opening the game anyway:', err);
  } finally {
    if (window.Preloader) window.Preloader.done();
  }
}

init();
