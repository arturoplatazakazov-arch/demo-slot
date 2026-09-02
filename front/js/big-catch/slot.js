// Big Catch — adapted from ../western-treasure/slot.js, which runs the same
// PNG-instead-of-Spine presentation (reel motion, win-cell sequencing, scatter
// anticipation, free-spins mode, inline win amount, expanding wild, buy bonus).
// Колесо фортуны родителя здесь вырезано: механика этой игры — Amy's Fruit
// Farm (line pay по 11 линиям, скаттерные фриспины, расширяющийся вайлд,
// bonus buy), см. app/seed/big_catch.py.
//
// Символы играет Spine (экспорты дизайнера в front/img/big-catch/export,
// общий движок — js/spine-engine.js). Всё остальное, что в оригинале было
// скелетом, по-прежнему собрано из PNG макета и DOM/CSS:
//
//   symbol idle / win           -> Spine (см. SYMBOL_SPINE ниже); классы на
//                                  .reel__cell остались запасным вариантом
//   win lines (baked clips)      -> an SVG polyline through the winning cells
//   expanding wild               -> a reel-height <img> with a CSS grow
//   popups (6 skeletons)         -> buildPopupNode(), a DOM plate + text
//
// Персонажа рядом с барабанами у этой темы нет вообще: домик, лодка и
// указатель Buy Free Spins нарисованы прямо в фоне, поэтому hero/bonus-hero
// родителя тут не заводятся.


const ASSET_ROOT = 'img/big-catch';

// 10 символов: 4 лоу — рыбацкие вещи без медальона (ящик / панама / воблер /
// поплавок), 4 хая — рыбы на медальонах (марлин / судак / окунь / рыба-ёж),
// плюс вайлд и скаттер. Коды — контракт с app/seed/big_catch.py.
//
// `wild` — доска с рыбой и надписью WILD. Расширяющегося вайлда у этой игры
// НЕТ (продукт: «здесь нет такой механики, только маленький вайлд») — ни на
// фронте, ни в сиде.
const SYMBOL_CODES = [
  'wild', 'scatter',
  'marlin', 'pike', 'bass', 'puffer',
  'tacklebox', 'hat', 'lure', 'bobber',
];

// Trigger symbols: they open a feature rather than pay a line, so they never
// stand in as spin-loop filler.
const TRIGGER_CODES = new Set(['scatter', 'wild']);

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}

// --- Spine-анимации символов ------------------------------------------------
//
// Дизайнер прислал ЧЕТЫРЕ скелета, а не десять: `common` и `rare` — это по
// одному скелету с четырьмя скинами (лоу-паи и рыбы на медальонах), scatter и
// wild — свои. У каждого три клипа: idle / land / win.
//
// `canvas` — размер холста экспортной статики. Он же задаёт нативный масштаб:
// статики отрисованы из этой же сцены с центром в начале координат скелета,
// поэтому если поставить якорь такого размера и приравнять к нему bounds, то
// скелет встанет ровно туда же, где лежит картинка, и в тот же размер (см.
// attachSymbolInstance). Никаких калибровочных сдвигов не нужно.
const SPINE_ROOT = `${ASSET_ROOT}/export`;
const SYMBOL_SPINE = {
  bobber:    { folder: 'common',  skin: 'common_1', canvas: 200 },
  tacklebox: { folder: 'common',  skin: 'common_2', canvas: 200 },
  hat:       { folder: 'common',  skin: 'common_3', canvas: 200 },
  lure:      { folder: 'common',  skin: 'common_4', canvas: 200 },
  marlin:    { folder: 'rare',    skin: 'rare1',    canvas: 200 },
  puffer:    { folder: 'rare',    skin: 'rare2',    canvas: 200 },
  bass:      { folder: 'rare',    skin: 'rare3',    canvas: 200 },
  pike:      { folder: 'rare',    skin: 'rare4',    canvas: 200 },
  scatter:   { folder: 'scatter', skin: null,       canvas: 226 },
  wild:      { folder: 'wild',    skin: null,       canvas: 200 },
};

// Общий WebGL-стейдж на всю игру; заводится в init(). Если Spine по любой
// причине не поднялся, всё ниже тихо деградирует в прежнюю CSS-подачу.
let stage = null;
const symbolResourceCache = {};

function getSymbolResource(code) {
  const spec = SYMBOL_SPINE[code];
  if (!spec || !stage) return null;
  if (!symbolResourceCache[spec.folder]) {
    symbolResourceCache[spec.folder] =
      SpineEngine.SpineResource.load(stage.assetManager, `${SPINE_ROOT}/${spec.folder}`);
  }
  return symbolResourceCache[spec.folder];
}

// Ставит скелет символа в ячейку. Возвращает инстанс (ещё НЕ добавленный на
// стейдж) или null, если анимации для символа нет / не загрузились.
async function attachSymbolInstance(info, code) {
  const spec = SYMBOL_SPINE[code];
  const promise = getSymbolResource(code);
  if (!spec || !promise) return null;
  let resource;
  try {
    resource = await promise;
  } catch (err) {
    console.warn(`[big-catch] скелет "${spec.folder}" не загрузился, символ ${code} останется картинкой:`, err);
    return null;
  }
  // Ячейку могли переиспользовать под другой символ, пока грузился атлас.
  if (info.symbol !== code) return null;

  const instance = resource.createInstance();
  if (spec.skin) {
    instance.skeleton.setSkinByName(spec.skin);
    instance.skeleton.setSlotsToSetupPose();
  }
  // bounds по холсту статики с центром в нуле: движок ставит ЦЕНТР bounds на
  // центр якоря, значит начало координат скелета попадает ровно в центр
  // ячейки — туда же, где отцентрована картинка. А fit=1 при якоре такого же
  // размера разрешается в масштаб барабанов, то есть в нативный.
  const half = spec.canvas / 2;
  instance.boundsOverride = { x: -half, y: -half, width: spec.canvas, height: spec.canvas };
  instance.fit = 1;
  if (info.anchor) {
    info.anchor.style.width = `${spec.canvas}px`;
    info.anchor.style.height = `${spec.canvas}px`;
    window.SlotCalibration?.applyAnchorOffset(info.anchor, 'big-catch', code);
  }
  instance.anchorEl = info.anchor || info.cell;
  info.instance = instance;
  return instance;
}

// Показать скелет вместо статики (и наоборот). Статику именно ПРЯЧЕМ, а не
// убираем: пустой src сделал бы ячейку по-настоящему пустой, если скелет
// потом снимут со стейджа.
function showInstance(info, on) {
  if (!info.img) return;
  info.img.style.visibility = on ? 'hidden' : '';
}

function detachInstance(info) {
  if (!info.instance) return;
  if (stage) stage.removeBase(info.instance);
  info.instance.onSettle = null;
  info.instance = null;
  showInstance(info, false);
}

// Codes eligible as random spin-loop filler — excludes the two trigger
// symbols: скаттер не должен мелькать в блюре, а вайлд расширяется, поэтому
// ему тоже нечего делать в прокрутке.
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));

// wild and scatter idle permanently on the grid (a slow breathe/glow);
// every other symbol sits still until it wins. Purely a CSS class — see
// .reel__cell.is-special in the stylesheet.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// How long one win pulse runs, in sync with the CSS keyframes. The original
// resolved this from the Spine clip's own duration; with CSS we own both ends,
// so the two numbers just have to agree.
const WIN_PULSE_MS = 620;
// Самый длинный клип `win` среди скелетов символов; заполняется в
// preloadAssets. Именно максимум, а не длина конкретного клипа: линия
// выигрыша не знает, какой символ сейчас играет, а в одной линии их обычно
// несколько с разной длиной клипа (у общих 1.6s, у редких 2.4s). Пока null
// (Spine не поднялся) везде действует WIN_PULSE_MS — длина запасной
// CSS-пульсации.
let symbolWinMs = null;
function winPulseMs() {
  return symbolWinMs || WIN_PULSE_MS;
}
// Popup in/out durations — must match the .game-popup transitions.
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;

// Attract-mode layout shown before the first real spin (also fixes the grid's
// 3 rows x 5 reels shape — no real backend game exists for this theme yet, so
// this placeholder is what renders until that's wired up).
// Раскладка снята с макета (кадр базовой игры в Figma), чтобы первый экран
// совпадал с тем, что рисовал дизайнер.
const SYMBOL_LAYOUT = [
  ['bobber', 'pike', 'tacklebox', 'bass', 'hat'],
  ['marlin', 'lure', 'scatter', 'hat', 'tacklebox'],
  ['puffer', 'tacklebox', 'bobber', 'lure', 'wild'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

// Попапы собираются в DOM (см. buildPopupNode), но, в отличие от родительских
// игр, ЗАГОЛОВОК В НИХ НЕ РИСУЕТСЯ: плашки приехали из макета уже с надписью —
// «BIG WIN!», «MEGA WIN!», «EPIC WIN!», «BONUS SPINS WINS», «BONUS SPINS TOTAL
// WIN», «BUY BONUS SPINS» нарисованы прямо на арте. Заполнить остаётся ровно
// одно поле, и у плашек их два разных типа:
//
//   slot: 'amount'  пустая деревянная панель под суммой  big / mega / epic / total
//   slot: 'count'   фиолетовый бейдж наверху, число      bonusSpinsWin / buyFreeSpins
//
// Границы обоих полей померены по арту каждой плашки и лежат в стилях
// (--popup-panel-*); перережут плашку — мерить заново.
const POPUP_CONFIG = {
  bigWin:             { plate: 'big',   slot: 'amount' },
  megaWin:            { plate: 'mega',  slot: 'amount' },
  epicWin:            { plate: 'epic',  slot: 'amount' },
  bonusSpinsWin:      { plate: 'fs',    slot: 'count' },
  bonusSpinsTotalWin: { plate: 'total', slot: 'amount' },
  buyFreeSpins:       { plate: 'buy',   slot: 'count' },
};

const POPUP_PLATE_SRC = {
  big: 'popup_big.png',
  mega: 'popup_mega.png',
  epic: 'popup_epic.png',
  fs: 'popup_bonus_spins.png',
  total: 'popup_bonus_total.png',
  buy: 'popup_buy.png',
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
// The Wild Western original played one of 11 pre-baked Spine animations, keyed
// by payline index. This game has no Spine, and it doesn't need the payline
// table either: every line win already carries its own `positions`, so the
// line is drawn straight through the winning cells' real centres as an SVG
// polyline over .reel__grid. That also means a backend payline the art never
// covered can no longer pay without a line.
const WIN_LINE_NS = 'http://www.w3.org/2000/svg';
let winLineSvg = null;
let winLineLoopTimeout = null;
// Every repeating "play once, pause, play again" loop in this file is a
// promise chain, and clearing its pending timeout is NOT enough to stop it: if
// the loop is mid-play when it's cancelled, the in-flight promise still
// resolves afterwards and re-arms the timeout, resurrecting a loop that was
// supposed to be dead. That is what made a win line from an earlier spin
// reappear over later, non-winning spins. Each loop therefore carries a
// generation token, bumped by whatever cancels it, and every continuation
// checks the token it started with before scheduling more work.
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

// Cell centres in .reel__grid's own coordinate space. Read live rather than
// computed from row/col arithmetic: the grid is CSS-scaled (updateReelScale)
// and the frame's opening is not a plain even split, so measuring is the only
// thing that stays correct across breakpoints.
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

// One flash of the line: draw it, run the dash-in, resolve when it has played
// once. The caller owns the repeat cadence, exactly as with the Spine version.
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
  // Two stacked strokes: a wide soft glow underneath, a bright core on top.
  for (const cls of ['win-line__glow', 'win-line__core']) {
    const path = document.createElementNS(WIN_LINE_NS, 'path');
    path.setAttribute('class', cls);
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  svg.classList.remove('is-playing');
  void svg.getBoundingClientRect(); // restart the CSS animation
  // Линия должна жить ровно столько же, сколько выигрышный клип символа, —
  // иначе в одиночном выигрыше (previewWinLine) она успевает перерисоваться
  // дважды, пока символ проигрывает свой клип один раз.
  svg.style.setProperty('--win-line-ms', `${winPulseMs()}ms`);
  svg.classList.add('is-playing');

  return wait(winPulseMs());
}

// Lone-line case only (playWinCells' single-group branch): repeats showWinLine
// on the same play-once/pause/repeat cadence the winning symbols use, so the
// line pulses in lockstep with their glow instead of drifting against it.
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
// Every cell is one <img>. Where the original swapped a Spine instance in over
// a hidden static tile, this game just toggles classes on the cell — so there
// is no `info.instance` anywhere below, and no canvas stage at all.

// No measured per-symbol offsets — every generated symbol was normalised into
// the same square box with a common optical centre when it was cut, so they
// already line up. A live override from Anim Lab's "Калибровать" still wins.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('big-catch', code);
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

  // Kept (empty) so the shared calibration tooling still finds an anchor node.
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
      cell.addEventListener('click', () => onCellClick(info));
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
  info.cell.classList.remove('is-winning', 'is-win-active');
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
    info.cell.style.opacity = '';
    clearCellAnimation(info);
    detachInstance(info);
  }
}

async function setCellSymbol(info, code) {
  clearCellAnimation(info);
  detachInstance(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  info.cell.style.opacity = '';
  info.img.src = symbolSrc(code);
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);

  const instance = await attachSymbolInstance(info, code);
  // Idle крутят ВСЕ символы (продукт): сетка целиком живая, статика остаётся
  // только запасным кадром на случай, если скелет не приехал.
  if (instance) startIdle(info);
}

// Порядок отрисовки на стейдже = порядок добавления, а рендерер сбрасывает
// батч на каждой смене текстуры. Символы садятся на поле вперемешку, и в
// худшем случае это 11 переключений на кадр вместо трёх. Группируем по
// семействам: на десктопе это ~8% времени отрисовки, на мобильном GPU дороже
// именно число вызовов. Порядок между символами на глаз не влияет — свечения
// соседей пересекаются симметрично.
function regroupBaseInstances() {
  if (!stage) return;
  const order = [];
  for (const inst of stage.baseInstances) {
    if (!order.includes(inst.resource)) order.push(inst.resource);
  }
  stage.baseInstances.sort((a, b) => order.indexOf(a.resource) - order.indexOf(b.resource));
}

// Ставит символ в вечный idle. Фаза у каждой ячейки своя: клип один на всё
// семейство, и без разбежки все четыре ящика на поле дышали бы синхронно,
// как метроном.
function startIdle(info) {
  const { instance } = info;
  if (!instance || !stage) return;
  showInstance(info, true);
  stage.addBase(instance);
  instance.play('idle', true);
  const track = instance.animationState.tracks[0];
  if (track && track.animation) track.trackTime = Math.random() * track.animation.duration;
}

// Один проигрыш выигрышного клипа; резолвится, когда он досмотрен.
function playWinAnimationOnce(info) {
  const { instance } = info;
  if (instance) {
    showInstance(info, true);
    stage.addBase(instance);
    return new Promise((resolve) => {
      instance.play('win', false);
      instance.onSettle = () => {
        instance.onSettle = null;
        if (info.instance !== instance) return resolve();
        instance.play('idle', true);   // все символы возвращаются в покой
        resolve();
      };
    });
  }
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

// Клик по ячейке гоняет её выигрышную анимацию — превью для дизайнера.
function onCellClick(info) {
  previewSymbolWin(info);
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
    // groups[i] < lineWins.length corresponds 1:1 to lineWins[i] (see
    // buildWinGroups/ReelMath.collectWinGroups — line wins are spread before
    // count wins, positions-only, so index is the only way back to a
    // payline). The "all together" phase (groupIndex -1) mixes lines, so no
    // single line's art applies there.
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
  // Any win at all (even just one line/count-pay group) dims every cell not
  // part of it, so the win reads clearly against the rest of the grid —
  // previously only the 2+-groups cycling sequence did this; a lone win just
  // cleared dimming and left the whole grid at full brightness.
  const winSet = new Set(allWinInfos);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, allWinInfos.length > 0 && !winSet.has(info));
  }
  const groups = buildWinGroups(lineWins, countWins);

  if (groups.length > 1) {
    playMultiLineWinSequence(groups, allWinInfos, lineWins);
  } else {
    // Single group: it's a line win iff lineWins has exactly the one entry
    // (a lone count-pay/scatter win has no line shape to draw).
    if (lineWins && lineWins.length === 1 && countWins && countWins.length === 0) {
      previewWinLine(lineWins[0]);
    } else {
      hideWinLine();
    }
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

// --- Reel motion (game-agnostic — see the other themes for the full writeup
// of how the masked-column scroll technique works) -----------------------

// No spinning-loop phase (ported from neon-reels, product-approved there:
// "по ощущениям даже лучше чем у нас на демо"): on spin press the resting
// symbols drop out of view downward (accelerating, hidden by the column's
// own overflow clip), the reel stands empty while the server answers, and
// the finals fall in from the top via landReel's usual eased landing.
// landReel awaits reelClearDone so no column starts landing while the old
// symbols are still mid-drop.
const REEL_CLEAR_MS = 260;

let reelLoopGeneration = 0; // invalidates a pending clear when a newer spin supersedes it
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
    // Two rAFs: one full frame so transition:none + the transform reset
    // apply before the drop transition starts (a same-frame kickoff drops
    // frames on mobile and opens the move at a visible crawl).
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
  // Error-path cleanup (see runSpin's catch): the clear-out drop may have
  // left the strips translated below the hole — put them back before the
  // caller re-applies the last known grid.
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
}

// Suspense treatment for a column flagged by ReelMath.collectAnticipationColumns
// — instead of restarting the infinite CSS loop at a slower speed (which
// requires forcing the strip back to translateY(0); since the loop isn't
// phase-synced to that moment, the strip is essentially never actually AT 0
// when this fires, so the reset itself was a visible snap — the "jumps up
// then falls down" glitch persisted even after switching to a clean restart).
//
// Replacing that with one long eased scroll (same curve as a normal landing,
// just stretched over ~2x the distance/duration) traded that bug for a
// different one: cubic-bezier(0.19, 0.79, 0.24, 1) decelerates so hard near
// the end that, stretched over a much longer duration, there's a long
// near-motionless stretch partway through — reads as "it landed", followed
// by one final small creep into the true resting spot, i.e. "falls, then
// falls again" (reported live). Fix: two separate phases instead of one
// stretched curve — a plain LINEAR pre-roll (no easing, so no plateau,
// just a steady "still spinning" scroll) for the wait, followed by the
// *exact* same short eased landing normal columns already use (proven fine,
// never stretched).
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, fillerCodeFn = randomSymbolCode) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    (async () => {
      // The clear-out drop must finish first, and the per-column stagger
      // counts from the END of the clear — not from the spin press. Counting
      // from the press meant every column whose delay was shorter than the
      // clear duration woke up at the same instant, so the first few reels
      // landed simultaneously (reported live — see neon-reels/slot.js, fixed
      // there first).
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
    cell.addEventListener('click', () => onCellClick(info));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks).then(regroupBaseInstances);
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: product ("не должны одновременно крутиться все оставшиеся
// барабаны") wants a single reel revealed, then the next, and so on.
// collectAnticipationColumns only flags a column while the trigger is still
// undecided, so once one of them lands the deciding symbol, later columns
// fall out of the flagged set on their own — those just land at normal
// speed, still one at a time, since the suspense is already resolved.
async function landReels(grid, anticipationColumns = [], lineWins = [], countWins = []) {
  teardownCellInstances();

  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const delay = col * REEL_LAND_STAGGER_MS;
    leadTasks.push(
      landReel(col, finalCodes, delay, false)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes)),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');

  // Freeze every remaining reel right away — landing one at a time (above)
  // isn't enough on its own if the ones still waiting their turn keep
  // spinning in the background the whole time (reported live: looked like
  // their own falling-into-place kept looping). Only the reel currently
  // being processed should ever visibly be in motion; each frozen one gets
  // fully rebuilt by landReel() anyway once its own turn comes up, so
  // freezing here doesn't need to leave them in any particular state.
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
    // Opaque dim = the base<->bonus mode transition. The original also had to
    // tint the Spine canvas by hand, because #screenDim (a DOM element) could
    // not darken canvas content without also covering the popup drawn on it.
    // Everything here is DOM, so the popup simply sits above #screenDim in the
    // stacking order and the one class does the whole job.
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

// Swaps the on-screen mode (grid background) for `next`. Shared by the plain
// leave-bonus dim and the enter-bonus intro so the two never drift apart.
function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
}

// How long the "you won the bonus" popup holds on the blackout before the
// bonus screen is revealed behind it (product: ~3s of popup, then reveal).
const BONUS_INTRO_HOLD_MS = 3000;

// The base -> free-spins moment: black the screen out, play the bonusSpinsWin
// popup over the black for BONUS_INTRO_HOLD_MS, swap the bonus screen in behind
// the still-opaque black, then lift the blackout to reveal it. Shared by both
// the real scatter trigger (app.js) and the dev mode toggle, since both enter
// the bonus through setFreeSpinsMode below.
async function enterBonusTransition(amount = 0) {
  pushScreenDim(true); // opaque blackout in
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true); // reveal the bonus screen
}

function setFreeSpinsMode(active, amount = 0) {
  const screen = document.getElementById('screen');
  const next = active ? 'freespins' : 'base';
  if (screen.dataset.mode === next) return Promise.resolve();

  Sound.playMusic(next === 'freespins' ? 'bonus' : 'base');

  // Entering the bonus gets the full intro moment (blackout + popup + reveal);
  // leaving it keeps the plain opaque dim swap.
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

// Built fresh per showing rather than kept around: a popup is on screen for a
// couple of seconds a few times a session, so there is nothing to cache, and a
// node that isn't in the DOM can't leave a stale amount behind.
function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key] || { plate: 'big', slot: 'amount' };
  const root = document.createElement('div');
  root.className = `game-popup is-plate-${cfg.plate} is-slot-${cfg.slot}`;
  if (isMobileLayout()) root.classList.add('is-mobile');

  const art = document.createElement('img');
  art.className = 'game-popup__art';
  art.src = `${ASSET_ROOT}/img/${POPUP_PLATE_SRC[cfg.plate]}`;
  art.alt = '';
  root.appendChild(art);

  // Одна строка на попап: либо сумма в деревянной панели, либо число спинов
  // в бейдже. Обёртка нужна, чтобы fitPopupText мерил строку против ПОЛЯ, а
  // не против всей плашки.
  const body = document.createElement('div');
  body.className = 'game-popup__body';
  const value = document.createElement('div');
  value.className = 'game-popup__amount';
  value.textContent = cfg.slot === 'count'
    ? String(Math.round(Number(amount)))
    : Number(amount).toLocaleString('en-US');
  body.appendChild(value);
  root.appendChild(body);
  return root;
}

// The three plaques have panels of different widths — and the epic one's is a
// circle — while titles run from "BIG WIN" to "BUY FREE SPINS". Rather than
// hand-tune a font size per plate/title pair, shrink each line until it fits
// its panel. Runs after the node is in the DOM so the panel has real bounds.
function fitPopupText(node) {
  const body = node.querySelector('.game-popup__body');
  if (!body) return;
  const lines = [...body.querySelectorAll('.game-popup__amount')];

  // The panel bounds are percentages of the PLATE ART, and the popup's own
  // height comes from that art's intrinsic ratio (width from CSS, height
  // auto). Until the image is laid out the body is 0 tall, the height pass
  // below sees "content overflows" on every iteration and runs straight to
  // its floor — that is how the first EPIC WIN of a session ended up with
  // 11px letters in a plate the size of the screen. Fit again on load
  // instead of fitting against a box that isn't there yet.
  const art = node.querySelector('.game-popup__art');
  if (art && !art.complete) {
    art.addEventListener('load', () => fitPopupText(node), { once: true });
    return;
  }
  if (!body.clientWidth || !body.clientHeight) return;

  // Measure against the PANEL, not the line's own box: the body is a centred
  // flex column, so a nowrap line simply grows past its parent and its own
  // scrollWidth/clientWidth stay equal — it never looks overflowing to itself.
  //
  // offsetWidth, NOT getBoundingClientRect(): this runs before .is-in, i.e.
  // while the popup still carries the enter transition's scale(0.7), and a
  // client rect is post-transform while body.clientWidth is not. Comparing
  // the two let a title 1.25x too wide look like it fit (measured 0.7x
  // against an unscaled limit) — "MEGA WIN" then rendered straight across
  // the plate's gold frame. Both numbers are layout-space now.
  const limit = body.clientWidth;
  for (const el of lines) {
    let size = parseFloat(getComputedStyle(el).fontSize);
    // 24 steps takes the longest title down to the narrowest panel; the floor
    // stops a pathological case from collapsing the text to nothing.
    for (let i = 0; i < 24 && el.offsetWidth > limit && size > 8; i += 1) {
      size *= 0.92;
      el.style.fontSize = `${size}px`;
    }
  }

  // Then the same for height: the epic plate's panel is a circle, so its
  // inscribed box is much shorter than the other two and a three-line popup
  // (sub + title + amount) can overrun it vertically even once every line
  // fits width-wise. Scales the whole block down together so the lines keep
  // their relative sizes. Content height is summed from the lines rather than
  // read off body.scrollHeight: the body is a centred flex column, so
  // overflow spills BOTH ways and scrollHeight never drops back to
  // clientHeight — the loop would just run to its floor and leave the text
  // microscopic.
  const gap = parseFloat(getComputedStyle(body).rowGap) || 0;
  const contentHeight = () =>
    lines.reduce((sum, el) => sum + el.offsetHeight, 0) + gap * Math.max(0, lines.length - 1);
  for (let i = 0; i < 24 && contentHeight() > body.clientHeight; i += 1) {
    for (const el of lines) {
      const size = parseFloat(getComputedStyle(el).fontSize) * 0.92;
      if (size <= 8) return;
      el.style.fontSize = `${size}px`;
    }
  }
}

// Core popup lifecycle (in -> hold -> out). The returned promise resolves only
// once the popup has FULLY played out, so a caller can sequence work after it.
// `ownDim` lets a caller that already owns the screen dim (the bonus intro
// below) borrow the popup without it pushing/popping its own dim.
function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = true, opaque = false } = {}) {
  if (!POPUP_CONFIG[key]) return Promise.resolve();

  return new Promise((resolve) => {
    // Every exit goes through ONE finish(), guaranteed to run — on the normal
    // path, on any error, and on a safety timeout. The dim goes up before the
    // popup is built, so anything that throws in between must not be able to
    // leave the screen dimmed forever with no popup on it.
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
      void node.offsetWidth; // commit the pre-enter state before transitioning
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

// Win-tier / dev popups: own their (partial) screen dim, as before.
// --- Buy Bonus confirmation dialog ------------------------------------------
//
// Плашка «BUY BONUS SPINS» из макета — единственная, что не объявление, а
// ДИАЛОГ: под ней в макете стоят зелёная ✓ и красная ✗. Поэтому указатель
// открывает её, а покупка уходит на сервер только по ✓ — ни один клик не
// тратит баланс сам по себе. app.js за это же гасит серверный попап
// "buyFreeSpins" в ответе, иначе та же карточка повторилась бы постфактум.
//
// Кнопки — обычные DOM-кнопки поверх арта (в отличие от multi-fruits-story,
// где они нарисованы на спайн-канвасе и им нужны хит-ареи по костям).
const BUY_DIALOG_BUTTONS = [
  { answer: true, src: 'btn_yes.png', label: 'Купить фриспины' },
  { answer: false, src: 'btn_no.png', label: 'Отмена' },
];

let buyDialogOpen = false;

// Резолвится true, если игрок подтвердил, и false, если отменил, — деньги
// тратит только true.
function showBuyBonusDialog(spins) {
  if (buyDialogOpen) return Promise.resolve(false);
  buyDialogOpen = true;

  return new Promise((resolve) => {
    let node = null;
    let done = false;
    const finish = (confirmed) => {
      if (done) return;
      done = true;
      clearTimeout(safetyTimer);
      Sound.playSfx('popupClose');
      if (node) {
        node.classList.remove('is-in');
        node.classList.add('is-out');
        const dead = node;
        setTimeout(() => dead.remove(), POPUP_EXIT_MS);
      }
      popScreenDim(false);
      buyDialogOpen = false;
      resolve(confirmed);
    };
    // Диалог ждёт игрока сколько угодно, но не вечно: если попап почему-то
    // не отрисовался, экран не должен остаться затемнённым навсегда.
    const safetyTimer = setTimeout(() => finish(false), 120000);

    (async () => {
      Sound.playSfx('popupOpen');
      pushScreenDim(false);
      await wait(DIM_TRANSITION_MS);

      node = buildPopupNode('buyFreeSpins', spins);
      const choice = document.createElement('div');
      choice.className = 'game-popup__choice';
      for (const spec of BUY_DIALOG_BUTTONS) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('aria-label', spec.label);
        const img = document.createElement('img');
        img.src = `${ASSET_ROOT}/img/${spec.src}`;
        img.alt = '';
        btn.appendChild(img);
        btn.addEventListener('click', () => {
          Sound.playSfx('click');
          finish(spec.answer);
        });
        choice.appendChild(btn);
      }
      node.appendChild(choice);

      document.getElementById('screen').appendChild(node);
      fitPopupText(node);
      void node.offsetWidth;
      node.classList.add('is-in');
    })().catch((err) => {
      console.error('buy-bonus dialog failed — closing it so the screen is usable:', err);
      finish(false);
    });
  });
}

function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Dev panel --------------------------------------------------------------

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');

  toggleBtn.addEventListener('click', () => {
    const next = document.getElementById('screen').dataset.mode === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 10); // demo spins count for the intro popup
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

  // Dev button previews the non-winning expansion (move -> idle_big, rule 6);
  // clicking a wild cell previews the winning one (move -> win_big, rule 5).

}

// Макет нарисован под кадр 1932x940 (bg_base.jpg — его натив), поэтому и
// потолок берётся оттуда; ниже 1280 масштаб замораживается и фон кропается —
// то же поведение, что у East Discovery.
const DESKTOP_DESIGN_MAX_WIDTH = 1932;
const DESKTOP_DESIGN_MIN_WIDTH = 1280;

// Экспериментальный «влезть целиком, без скролла» лейаут — см.
// body.layout-fit в стилях и ReelMath.fitScale.
// Персонажа сбоку у этой темы нет, зато справа от рамки стоит указатель Buy
// Free Spins. Он привязан к рамке и масштабируется вместе с ней, поэтому на
// барабаны наехать не может — резерв нужен ровно чтобы он не уехал за край
// экрана: указатель торчит на 287px правее рамки (360 - 73 захода), рамка
// центрирована, значит по обе стороны надо держать по столько же.
const FIT_RESERVE_WIDTH_PX = 600;
// The band the fit has to keep clear above the reels for the logo. The logo is
// a FIXED share of the screen width now (see .logo), so this is a fixed number
// too: its height at that width, minus the overlap — доска логотипа в макете
// заходит на верхнее бревно рамки, а не висит над ним.
// NOTE the fit is scale-invariant in --reel-frame-scale: fitScale is handed
// frameHeight * frameScale and returns the scale that makes that fill
// (viewport - reserve), so the on-screen size is (viewport - reserve) whatever
// --reel-frame-scale says. THESE RESERVES are the only real lever on how big
// the reels render, which is why the 20% bump lives here and not only in the
// stylesheet's --reel-frame-scale.
// Логотип поднимается над рамкой на 91px (доска 162 минус 71 захода на
// верхнее бревно), плюс небольшой воздух сверху — как в макете, где над
// рамкой ровно 95px кадра.
const FIT_RESERVE_HEIGHT_PX = 120;

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
// Mirror of neon-reels' warmup (see front/js/neon-reels/slot.js for the full
// rationale): decode symbol statics, load every Spine export the first
// minutes will touch, warm the SFX buffers and compile the WebGL shaders —
// all behind the progress overlay driven by js/preloader.js. Every task
// resolves (errors swallowed) and the whole thing is capped by a timeout, so
// nothing can strand the overlay.
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
  // Рамка барабанов и указатель Buy Free Spins — тоже вперёд: рамка видна с
  // первого кадра, а указатель кликают до первого спина.
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/reel_frame.png`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/reel_ropes.png`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/buy_bonus.png`)));
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/fs_counter.png`)));
  for (const spec of BUY_DIALOG_BUTTONS) {
    tasks.push(track(preloadImage(`${ASSET_ROOT}/img/${spec.src}`)));
  }
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('bonus'))));
  // Плашки попапов — обязательно ДО первого попапа, а не лениво: fitPopupText
  // меряет строку против .game-popup__body, а тот позиционирован в процентах
  // от ещё не загруженной картинки. На незагруженной плашке body.clientWidth
  // около нуля, цикл ужимает текст до пола (~10px), и первый в сессии BIG WIN
  // выходит с микроскопическими буквами.
  for (const file of Object.values(POPUP_PLATE_SRC)) {
    tasks.push(track(preloadImage(`${ASSET_ROOT}/img/${file}`)));
  }
  // Четыре скелета символов. Грузим до первого спина: атлас, подъехавший
  // посреди приземления, означал бы, что первые барабаны сели без анимации.
  for (const folder of new Set(Object.values(SYMBOL_SPINE).map((s) => s.folder))) {
    const promise = getSymbolResource(Object.keys(SYMBOL_SPINE).find((c) => SYMBOL_SPINE[c].folder === folder));
    if (!promise) continue;
    tasks.push(track(promise.then((resource) => {
      const clip = resource.skeletonData.findAnimation('win');
      if (clip) symbolWinMs = Math.max(symbolWinMs || 0, Math.round(clip.duration * 1000));
    })));
  }
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // must resolve before buildReelGrid's applyStaticContentOffset
  // Стейдж — до buildReelGrid: setCellSymbol уже на первом кадре захочет
  // подцепить скелеты вайлда и скаттера. Если WebGL недоступен, игра просто
  // остаётся на статике и CSS-анимациях, а не падает.
  try {
    stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  } catch (err) {
    console.warn('[big-catch] Spine-стейдж не поднялся, анимации символов отключены:', err);
    stage = null;
  }
  // Пока класса нет, действуют запасные CSS-анимации символов (см. стили).
  if (stage) document.body.classList.add('has-spine');
  Sound.playMusic('base');
  document.body.classList.add('layout-fit'); // fit-to-screen is now the default desktop layout — see setupDevPanel's toggle
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
  regroupBaseInstances();

  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos, stage };
}

init();
