// Uniqorn Shaolin Struggles — 3x3 Hold & Win.
//
// МЕХАНИКА и порядок сцен взяты у ../lucky-joker-3h3 (та же игра по продукту и
// тот же референс api.dreamplay.games/hell-coins): дизайн-канвас, колонки,
// обрезанные окном корпуса, и раунд, который сервер уже полностью решил, а
// клиент проигрывает респин за респином.
//
// ПОДАЧА — как в ../uniqorn-back-to-fabulous: спайна нет вообще, весь арт это
// PNG, и всё, что там анимировал скелет, тут делают классы:
//
//   idle / win / landing символа  -> .reel__cell.is-* (css/uniqorn-shaolin-struggles.css)
//   номинал монеты                -> .coin-value, ребёнок ячейки
//   попапы, диалог покупки        -> DOM-карточки, плашка нарисована в CSS
//
// Из-за этого метки монет здесь ПРОЩЕ, чем у донора: там они жили в fixed-слое
// и каждый кадр гнались за ячейкой через rAF (символ рисовался на канвасе, а
// не в DOM). Здесь метка лежит внутри самой ячейки, поэтому едет с барабаном,
// масштабируется со сценой и обрезается окном корпуса сама.
//
// Отличия от донора по продукту: скаттера и фриспинов в игре нет вообще, так
// что бонусный экран — это ТОЛЬКО раунд Hold & Win, а на месте счётчика
// фриспинов стоит счётчик респинов.

const ASSET_ROOT = 'img/uniqorn-shaolin-struggles';

// Коды, которые может выдать бэкенд. 1:1 контракт с _SYMBOLS в
// app/seed/uniqorn_shaolin_struggles.py: код == имя файла в symbols/.
const SYMBOL_CODES = [
  'noodles', 'bamboo', 'nunchaku', 'bucket', 'bell', 'dragon', 'pagoda',
  'coin', 'collector',
];

// Клиентские коды поверх серверных:
//   blank        — пустая ячейка раунда (арта нет вовсе)
//   coin_<tier>  — монета джекпота, у каждого тира свой ободок
const JACKPOT_TIERS = ['mini', 'minor', 'major', 'grand'];
// Суммы зеркалят JACKPOT_VALUES сида — они же печатаются на лестнице, поэтому
// разъехаться с сервером незаметно нельзя: цифра на плашке приходит отсюда.
const JACKPOT_LADDER = [
  { tier: 'grand', name: 'GRAND', value: 1000 },
  { tier: 'major', name: 'MAJOR', value: 150 },
  { tier: 'minor', name: 'MINOR', value: 50 },
  { tier: 'mini', name: 'MINI', value: 25 },
];
const JACKPOT_VALUE_BY_TIER = Object.fromEntries(JACKPOT_LADDER.map((j) => [j.tier, j.value]));

const ALL_ART_CODES = [...SYMBOL_CODES, ...JACKPOT_TIERS.map((t) => `coin_${t}`)];

// Символы-деньги: они «дышат» на поле постоянно, потому что сами по себе
// событие (монета несёт множитель, коллектор открывает раунд).
const MONEY_CODES = new Set(['coin', 'collector', ...JACKPOT_TIERS.map((t) => `coin_${t}`)]);

// Чем можно засыпать барабан во время прокрутки: без монет и коллектора —
// мелькнувший в размытии триггер читается как несостоявшийся почти-выигрыш.
const FILLER_CODES = SYMBOL_CODES.filter((code) => !MONEY_CODES.has(code));

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}

// Монета `kind` от сервера (app/features/coin_multiplier.py и hold_and_win.py)
// -> код арта. Тир джекпота получает свой ободок, всё остальное — обычную
// монету с числом поверх.
function coinCodeForKind(kind) {
  if (kind === 'collector') return 'collector';
  return JACKPOT_TIERS.includes(kind) ? `coin_${kind}` : 'coin';
}

const GRID_COLS = 3;
const GRID_ROWS = 3;

// Раскладка attract-режима до первого спина.
const SYMBOL_LAYOUT = [
  ['noodles', 'bell', 'bamboo'],
  ['bucket', 'collector', 'nunchaku'],
  ['bamboo', 'dragon', 'pagoda'],
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
let cellW = 224;
let cellH = 196;
let rowStep = cellH;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => {
    const value = parseFloat(cs.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  cellW = num('--cell-w', 224);
  cellH = num('--cell-h', 196);
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

// --- Герой ------------------------------------------------------------------
//
// Один PNG и три CSS-лупа: idle (по умолчанию), tense (пока крутятся барабаны)
// и cheer (пока выплачивается выигрыш).
let heroMood = 'idle';
function setHeroMood(mood) {
  if (mood === heroMood) return;
  const el = document.getElementById('hero');
  if (!el) return;
  heroMood = mood;
  el.classList.remove('is-idle', 'is-tense', 'is-cheer');
  el.classList.add(`is-${mood}`);
}

// --- Лестница джекпотов ------------------------------------------------------

function buildJackpotLadder() {
  const ladder = document.getElementById('jpLadder');
  if (!ladder) return;
  ladder.innerHTML = '';
  for (const { tier, name, value } of JACKPOT_LADDER) {
    const plate = document.createElement('div');
    plate.className = `jp jp--${tier}`;
    plate.dataset.tier = tier;
    // Имя тира печатается в пустом центре монеты — тем же приёмом, что номинал
    // на монете в сетке (весь монетный арт нарисован с пустой серединой).
    plate.innerHTML = `
      <span class="jp__coin">
        <img src="${symbolSrc(`coin_${tier}`)}" alt="">
        <span class="jp__name">${name}</span>
      </span>
      <span class="jp__value">×${value}</span>
    `;
    ladder.appendChild(plate);
  }
}

// --- Ячейки ------------------------------------------------------------------

function applyStaticContentOffset(img, code) {
  // Все символы нарезаны в один квадрат с общим оптическим центром, так что по
  // умолчанию сдвигать нечего; живой оверрайд из Anim Lab главнее.
  const override = window.SlotCalibration && window.SlotCalibration.get('uniqorn-shaolin-struggles', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

// `blank` — единственный код, который законно рисуется ничем (незаполненная
// ячейка раунда). Любой другой код без арта это баг (код, который бэкенд
// выдаёт, а фронт не знает), и он должен быть громким, а не дырой в сетке.
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
      console.warn(`[shaolin] no art for symbol code "${code}"`);
    }, { once: true });
  }
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  return { cell, img };
}

function applyCellFlags(cell, code) {
  cell.classList.toggle('is-money', MONEY_CODES.has(code));
  cell.classList.toggle('is-collector', code === 'collector');
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
      const info = { symbol, row, col, cell, img, winLoopTimeout: null, coinLabel: null };
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
  setHeroMood('idle');
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    clearCoinLabel(info);
    clearCellAnimation(info);
  }
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  clearCoinLabel(info);
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

// --- Номиналы монет ----------------------------------------------------------
//
// Монета нарисована с пустым центром: значение печатает клиент. У джекпотной
// монеты значение — имя тира (сумма всё равно на лестнице), у обычной — «xN»,
// у коллектора — текущая собранная сумма раунда.

function clearCoinLabel(info) {
  if (!info || !info.coinLabel) return;
  info.coinLabel.remove();
  info.coinLabel = null;
}

function showCoinLabel(info, text, extraClass = '') {
  clearCoinLabel(info);
  const el = document.createElement('span');
  el.className = extraClass ? `coin-value ${extraClass}` : 'coin-value';
  el.textContent = text;
  info.cell.appendChild(el);
  info.coinLabel = el;
}

// Та же метка, но на ещё не «осевшей» ячейке падающей ленты (у неё нет info) —
// монета должна падать уже с числом, а не получать его после остановки.
function attachCoinLabelToCell(cell, text, extraClass = '') {
  const el = document.createElement('span');
  el.className = extraClass ? `coin-value ${extraClass}` : 'coin-value';
  el.textContent = text;
  cell.appendChild(el);
}

function coinLabelFor(kind, value) {
  if (JACKPOT_TIERS.includes(kind)) return { text: kind.toUpperCase(), cls: 'is-tier' };
  return { text: `x${value}`, cls: '' };
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
  setHeroMood(allWinInfos.length > 0 ? 'cheer' : 'idle');

  const groups = buildWinGroups(lineWins, countWins);
  if (groups.length > 1) {
    playMultiLineWinSequence(groups, allWinInfos);
  } else {
    for (const info of allWinInfos) previewSymbolWin(info);
  }
}

// Подсветить монеты, чей множитель реально применился к линии (сервер говорит
// applied). Без этого игрок видит «x5» на монете и не понимает, сработала она
// или нет.
function playCoinMultiplierReveal(coinMultiplier) {
  if (!coinMultiplier || !coinMultiplier.applied) return;
  let any = false;
  for (const pos of coinMultiplier.positions || []) {
    const info = cellInfos[pos.row * GRID_COLS + pos.col];
    if (info && MONEY_CODES.has(info.symbol)) {
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
  setHeroMood('tense');
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    // Два rAF: целый кадр, чтобы transition:none и сброс трансформа применились
    // до старта падения.
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
  // Уборка на пути ошибки: вернуть ленты на место перед тем, как вызывающий
  // заново применит последнюю известную сетку.
  reelsBusy = false;
  setHeroMood('idle');
  for (const { stripEl } of reelCols) {
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
}

// `coinLabels` (по одной записи на ряд, null там, где монеты нет) вешает метку
// НА ЭТАПЕ СБОРКИ ленты, то есть до начала падения: монета падает уже со своим
// множителем, а не получает число после остановки.
function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, fillerFn = randomSymbolCode, coinLabels = null) {
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
      const cellEls = sequence.map((code, index) => {
        const { cell } = createCellNode(code);
        stripEl.appendChild(cell);
        const label = coinLabels && index < GRID_ROWS ? coinLabels[index] : null;
        if (label) attachCoinLabelToCell(cell, label.text, label.cls);
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

// Ячейки уже собраны падающей лентой (арт и метка монеты на месте), поэтому
// здесь их НЕЛЬЗЯ переклеивать через setCellSymbol — это стёрло бы метку,
// приехавшую вместе с монетой. Остаётся завести на них info и сыграть посадку.
function settleColumnCells(cellEls, col, finalCodes) {
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const info = {
      symbol: code, row, col, cell,
      img: cell.querySelector('img'),
      winLoopTimeout: null,
      coinLabel: cell.querySelector('.coin-value'),
    };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    playLandBounce(info);
  }
  return Promise.resolve();
}

// Метки монет базовой игры (3x3, null там, где монеты нет) — держим отдельно,
// потому что поворот экрана пересобирает сетку с нуля и стирает всё, что лежало
// в ячейках. Раунд Hold & Win восстанавливается из holdAndWinLocked, а базовая
// игра — отсюда.
let lastBaseLabels = null;

// Превращает серверную сетку в то, что реально рисуется: монета, вытянувшая
// тир джекпота, приземляется своим ободком, остальные — обычной монетой с «xN».
function resolveDrawnGrid(grid, coinMultiplier) {
  const codes = grid.map((row) => row.slice());
  const labels = grid.map((row) => row.map(() => null));
  for (const pos of (coinMultiplier && coinMultiplier.positions) || []) {
    if (codes[pos.row]?.[pos.col] !== 'coin') continue;
    codes[pos.row][pos.col] = coinCodeForKind(pos.kind);
    labels[pos.row][pos.col] = coinLabelFor(pos.kind, pos.value);
  }
  return { codes, labels };
}

// Барабан, на котором ещё может решиться раунд: коллектор на среднем и монета
// на первом — значит последний барабан играет на триггер. Считается по уже
// известной (серверной) сетке, поэтому «почти выпало» здесь всегда честное.
function holdAndWinAnticipationColumns(codes) {
  const hasCoin = (col) => codes.some((row) => row[col] === 'coin');
  const hasCollector = (col) => codes.some((row) => row[col] === 'collector');
  return hasCoin(0) && hasCollector(1) ? [2] : [];
}

// Колонки начиная с firstAnticipationCol приземляются ПО ОДНОЙ, никогда
// параллельно: открывается один барабан, потом следующий — иначе саспенса нет.
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
  setHeroMood('tense');

  const { codes, labels } = resolveDrawnGrid(grid, coinMultiplier);
  lastBaseLabels = labels;
  const columnCodes = (col) => [codes[0][col], codes[1][col], codes[2][col]];
  const columnLabels = (col) => [labels[0][col], labels[1][col], labels[2][col]];

  const anticipationColumns = holdAndWinAnticipationColumns(codes);
  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = columnCodes(col);
    const cols = columnLabels(col);
    leadTasks.push(
      landReel(col, finalCodes, col * REEL_LAND_STAGGER_MS, false, randomSymbolCode, cols)
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
    const cols = columnLabels(col);
    const isAnticipating = anticipationSet.has(col);
    if (isAnticipating) reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, 0, isAnticipating, randomSymbolCode, cols);
    await settleColumnCells(cellEls, col, finalCodes);
  }
}

// Сетка, появляющаяся БЕЗ приземления (базовые барабаны, возвращаемые после
// раунда): арт и метки монет надо расставить руками.
async function applyGridWithCoins(grid, coinMultiplier) {
  const { codes, labels } = resolveDrawnGrid(grid, coinMultiplier);
  await applyGrid(codes);
  lastBaseLabels = labels;
  paintBaseLabels();
}

// Развешивает lastBaseLabels по текущим ячейкам — после приземления это уже
// сделала сама лента, так что вызывается только там, где сетка появилась без
// падения (возврат из раунда, пересборка под другую ориентацию).
function paintBaseLabels() {
  if (!lastBaseLabels) return;
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let col = 0; col < GRID_COLS; col++) {
      const label = lastBaseLabels[row][col];
      const info = cellInfos[row * GRID_COLS + col];
      if (label && info && MONEY_CODES.has(info.symbol)) showCoinLabel(info, label.text, label.cls);
    }
  }
}

// --- Затемнение и смена режима ----------------------------------------------

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
  setBackground(next);
}

// Сколько интро-попап раунда висит на чёрном, прежде чем откроется бонусный
// экран (тот же ритм, что у остальных игр проекта).
const BONUS_INTRO_HOLD_MS = 2600;

// Вход в раунд: залить экран чёрным, проиграть на чёрном попап «HOLD & WIN»,
// под всё ещё непрозрачной заливкой подменить экран и снять её. В отличие от
// донора бонусный экран здесь один и он же единственный — фриспинов нет.
async function enterBonusMode() {
  if (currentMode() === 'bonus') return;
  Sound.playMusic('bonus');
  pushScreenDim(true);
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('holdWinIntro', 0, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('bonus');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true);
}

function leaveBonusMode() {
  if (currentMode() === 'base') return Promise.resolve();
  Sound.playMusic('base');
  return withScreenDim(
    async () => {
      applyModeScreen('base');
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
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
  holdWinIntro: { title: 'HOLD & WIN', sub: 'COLLECTOR LANDED', hideAmount: true, coin: 'collector' },
  holdWinTotal: { title: 'TOTAL WIN', sub: 'ROUND OVER' },
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
    amountEl.textContent = Number(amount).toLocaleString('en-US');
    root.appendChild(amountEl);
  }
  return root;
}

// Жизненный цикл попапа (вход -> держим -> выход). Промис резолвится, только
// когда попап полностью отыграл, чтобы вызывающий мог выстроить работу после
// него. `ownDim` позволяет вызывающему, который уже владеет затемнением (интро
// раунда), одолжить попап без собственного push/pop.
//
// Любой выход идёт через ОДИН finish(), и он гарантированно отработает — иначе
// упавший попап оставил бы экран затемнённым навсегда.
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
      void node.offsetWidth; // зафиксировать пред-входное состояние
      node.classList.add('is-in');

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`[shaolin] popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
      finish();
    });
  });
}

function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Награда джекпота --------------------------------------------------------
//
// Монета джекпота, попавшая в раунд, получает собственный момент: её плашка на
// лестнице загорается, а по центру выезжает карточка тира с суммой в ставках.
const JACKPOT_AWARD_HOLD_MS = 2200;

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
      pushScreenDim(false);
      await wait(DIM_TRANSITION_MS);

      node = document.createElement('div');
      node.className = 'game-popup is-jackpot';
      node.style.setProperty('--tier-color', getComputedStyle(plate || document.body).getPropertyValue('--tier-color') || '#ffcf5a');
      node.innerHTML = `
        <img class="game-popup__coin" src="${symbolSrc(`coin_${tier}`)}" alt="">
        <div class="game-popup__sub">JACKPOT</div>
        <div class="game-popup__title">${tier.toUpperCase()}</div>
        <div class="game-popup__amount">×${value}</div>
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
      console.error('[shaolin] jackpot award failed:', err);
      finish();
    });
  });
}

// --- Диалог покупки раунда ---------------------------------------------------
//
// Кнопка Buy Bonus сама денег не тратит: она открывает диалог, и покупка
// уходит на сервер только по ✓. Ставку внутри диалога можно переключить — с
// какой вышли, с такой и покупаем.
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
      <div class="buy-dialog__note" id="buyDialogNote"></div>
      <div class="buy-dialog__price" id="buyDialogPrice"></div>
      <div class="buy-dialog__bet">
        <button class="buy-dialog__step" data-step="-1" type="button" aria-label="Уменьшить ставку">−</button>
        <span class="buy-dialog__bet-value" id="buyDialogBet"></span>
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
      node.querySelector('#buyDialogPrice').textContent =
        `${Number(cost).toLocaleString('en-US')} ${currency}`;
      node.querySelector('#buyDialogBet').textContent =
        `BET ${Number(bet).toLocaleString('en-US')}`;
      // Раунд стоит 50 ставок, так что на верхних ступенях он дороже всего
      // баланса — сервер ответил бы 400, а игрок не понял бы почему. Гасим ✓ и
      // говорим прямо: ступенька ставки тут же рядом.
      const affordable = balance == null || cost <= balance;
      const yes = node.querySelector('[data-answer="1"]');
      yes.disabled = !affordable;
      yes.style.opacity = affordable ? '' : '0.35';
      node.querySelector('#buyDialogNote').textContent = affordable
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
        const delta = Number(btn.dataset.step);
        index = Math.min(betSteps.length - 1, Math.max(0, index + delta));
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
// Раунд целиком решается одним ответом сервера (app/features/hold_and_win.py) —
// респины ниже это чистый театр, проигрывающий уже известный исход так, чтобы
// игрок переживал его как настоящий.
//
// Это ИСТИННЫЙ hold: приземлившийся символ больше не двигается, крутятся только
// пустые ячейки — а значит крутить надо ПОКЛЕТОЧНО, не колонками (в одной
// колонке одновременно бывает и залипшая монета, и пустая ячейка).

const COLLECTOR_REEL = 1;             // средний барабан — только коллекторы
const RESPIN_COUNT = 3;               // = hold_and_win.respin_count в сиде
const HOLD_AND_WIN_RESPIN_PAUSE_MS = 900;
const HW_CELL_SPIN_MS = 620;
const HW_CELL_SPIN_FILLER = 8;
// Только для филлера: доли совпадают с respin_land_weights/collector_land_weights,
// чтобы мелькающее в прокрутке не врало о том, что может выпасть.
const HW_COIN_FILLER_CHANCE = 0.16;
const HW_COLLECTOR_FILLER_CHANCE = 0.07;

function holdAndWinFillerFor(col) {
  return col === COLLECTOR_REEL
    ? () => (Math.random() < HW_COLLECTOR_FILLER_CHANCE ? 'collector' : 'blank')
    : () => (Math.random() < HW_COIN_FILLER_CHANCE ? 'coin' : 'blank');
}

const coinKey = (row, col) => `${row}-${col}`;

// Залипшие монеты текущего раунда, "row-col" -> {value, kind}. На уровне модуля
// — чтобы поворот экрана посреди раунда мог перерисовать метки после пересборки
// сетки (flushDeviceRebuild её полностью сносит).
let holdAndWinLocked = null;

function buildHoldAndWinGrid(locked) {
  const grid = [[], [], []];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const coin = locked.get(coinKey(row, col));
      grid[row][col] = coin ? coinCodeForKind(coin.kind) : 'blank';
    }
  }
  return grid;
}

// Сколько сейчас стоит КАЖДЫЙ коллектор: сумма множителей всех монет (включая
// джекпотные, по номиналу их тира). Зеркалит выплату сервера — coin_total x
// количество коллекторов.
function collectedTotal(locked) {
  let total = 0;
  for (const [, coin] of locked) {
    if (coin.kind !== 'collector') total += Number(coin.value);
  }
  return total;
}

// Перерисовывает все метки раунда: «xN»/имя тира на монетах и текущую собранную
// сумму на КАЖДОМ коллекторе — все они собирают, потому второй коллектор и
// удваивает раунд.
function paintLockedCoins(locked) {
  const total = collectedTotal(locked);
  for (const info of cellInfos) {
    if (info) clearCoinLabel(info);
  }
  for (const [key, coin] of locked) {
    const [row, col] = key.split('-').map(Number);
    const info = cellInfos[row * GRID_COLS + col];
    if (!info) continue;
    if (coin.kind === 'collector') {
      if (total > 0) showCoinLabel(info, `x${total}`, 'is-collector');
    } else {
      const label = coinLabelFor(coin.kind, coin.value);
      showCoinLabel(info, label.text, label.cls);
    }
  }
}

function setRespinCounter(value) {
  const el = document.getElementById('respinValue');
  if (el) el.textContent = value;
}

// Крутит ОДНУ ячейку до `code`: полоса филлера над результатом, обрезанная по
// ячейке, съезжает вниз и выбрасывается в пользу настоящего арта. Залипшие
// ячейки такой полосы не получают — на этом и читается hold.
function spinCellTo(info, code, fillerFn, delayMs) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const spinner = document.createElement('div');
      spinner.className = 'cell-spinner';
      const strip = document.createElement('div');
      strip.className = 'cell-spinner__strip';

      for (const itemCode of [code, ...Array.from({ length: HW_CELL_SPIN_FILLER }, fillerFn)]) {
        const item = document.createElement('div');
        item.className = 'cell-spinner__item';
        if (itemCode !== 'blank') {
          const img = document.createElement('img');
          img.decoding = 'async';
          img.src = symbolSrc(itemCode);
          item.appendChild(img);
        }
        strip.appendChild(item);
      }
      spinner.appendChild(strip);
      info.cell.appendChild(spinner);
      info.img.style.visibility = 'hidden';

      // Старт на последнем филлере, съезд к результату (индекс 0).
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

// Один респин: крутится каждая незалипшая ячейка, приземляя либо то, что сервер
// туда положил, либо пустоту. Залипшие не трогаются вовсе.
async function respinEmptyCells(locked, landing) {
  const tasks = [];
  for (let col = 0; col < GRID_COLS; col++) {
    const filler = holdAndWinFillerFor(col);
    for (let row = 0; row < GRID_ROWS; row++) {
      const key = coinKey(row, col);
      if (locked.has(key)) continue;
      const info = cellInfos[row * GRID_COLS + col];
      if (!info) continue;
      const arriving = landing.get(key);
      const code = arriving ? coinCodeForKind(arriving.kind) : 'blank';
      tasks.push(spinCellTo(info, code, filler, col * REEL_LAND_STAGGER_MS));
    }
  }
  await Promise.all(tasks);
}

// Раунд открывается на коллекторе триггерной сетки (result.initial), всё
// остальное гаснет — и ждёт нажатия Spin.
async function enterHoldAndWinWaitingState(result) {
  const locked = new Map();
  for (const c of result.initial || []) {
    locked.set(coinKey(c.row, c.col), { value: c.value, kind: c.kind });
  }
  await enterBonusMode();
  await applyGrid(buildHoldAndWinGrid(locked));
  holdAndWinLocked = locked;
  paintLockedCoins(locked);
  setRespinCounter(RESPIN_COUNT);
  return locked;
}

// `baseGrid`/`baseCoins` — сетка триггерного спина и его монеты. Раунд
// оставляет барабаны в своей раскладке, поэтому без возврата игрок вышел бы в
// базовую игру на дырах и монетах без чисел.
async function runHoldAndWinSequence(result, locked, baseGrid = null, baseCoins = null) {
  const wonTiers = [];
  const noteTier = (kind) => {
    if (JACKPOT_TIERS.includes(kind) && !wonTiers.includes(kind)) wonTiers.push(kind);
  };
  for (const [, coin] of locked) noteTier(coin.kind);

  let respinsLeft = RESPIN_COUNT;
  for (const respin of result.respins) {
    // Крутятся только пустые ячейки; `locked` пополняется ПОСЛЕ приземления
    // (ячейка не может залипнуть раньше, чем в ней что-то есть).
    const landing = new Map(
      respin.landed.map((c) => [coinKey(c.row, c.col), { value: c.value, kind: c.kind }]),
    );
    await respinEmptyCells(locked, landing);
    for (const [key, coin] of landing) locked.set(key, coin);
    holdAndWinLocked = locked;
    paintLockedCoins(locked);

    // Любая посадка сбрасывает счётчик — это и есть правило раунда.
    respinsLeft = respin.landed.length ? RESPIN_COUNT : respinsLeft - 1;
    setRespinCounter(Math.max(0, respinsLeft));

    for (const c of respin.landed) noteTier(c.kind);
    if (respin.landed.length) Sound.playSfx('coinLand');

    await wait(HOLD_AND_WIN_RESPIN_PAUSE_MS);
  }

  await wait(300);
  // Монеты джекпота получают свой момент до карточки итога.
  for (const tier of wonTiers) await playJackpotAward(tier);

  Sound.playSfx('roundTotalWin');
  await playPopup('holdWinTotal', result.total_win, 3000);
  holdAndWinLocked = null;
  // Базовые барабаны возвращаются ДО того, как экран снова откроется: подмена
  // идёт под заливкой перехода, поэтому раунд не мелькает своими остатками.
  if (baseGrid) await applyGridWithCoins(baseGrid, baseCoins);
  await leaveBonusMode();
}

// --- Dev-панель --------------------------------------------------------------

function setupDevPanel() {
  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 123456));
  });
  const jackpotBtn = document.getElementById('devJackpot');
  if (jackpotBtn) {
    jackpotBtn.addEventListener('click', async () => {
      for (const tier of JACKPOT_TIERS) await playJackpotAward(tier);
    });
  }
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

function setBackground(mode) {
  const suffix = isMobileLayout() ? '_mob' : '';
  const name = mode === 'base' ? 'bg_base' : 'bg_bonus';
  document.getElementById('bgLayer').src = `${ASSET_ROOT}/img/${name}${suffix}.jpg`;
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
  setBackground(currentMode());
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
  // Пересборка унесла метки вместе с ячейками — вернуть их: в раунде из
  // залипших монет, в базовой игре из меток последнего спина (иначе после
  // поворота экрана монета остаётся на барабане без своего множителя).
  if (holdAndWinLocked) paintLockedCoins(holdAndWinLocked);
  else paintBaseLabels();
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
  for (const code of ALL_ART_CODES) tasks.push(track(preloadImage(symbolSrc(code))));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/hero.png`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/logo.png`)));
  const suffix = isMobileLayout() ? '_mob' : '';
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/bg_base${suffix}.jpg`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/bg_bonus${suffix}.jpg`)));
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

  buildJackpotLadder();
  buildReelGrid();
  setBackground(currentMode());
  setupDevPanel();

  await preloadAssets();
  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
