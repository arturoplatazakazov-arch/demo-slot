// Neon Joker Spins — 3x3, 5 линий, Free Spins + Hold & Win с Коллектором.
//
// Движок барабанов — от ../tesla-spins (та же 3x3 раскладка, дизайн-канвас,
// рама поверх лент, падение финалов сверху без бесконечной прокрутки), но без
// Spine: вся подача — PNG/WebP + CSS + спрайты FX (fx/*.webp) на WAAPI.
//
// Числа нигде не запечены в арт: номинал монеты, сумма Коллектора, джекпоты,
// счётчики и попапы набираются битмап-шрифтом glyphs/ (setGlyphs).
//
// Раунд Hold & Win целиком решает сервер (hold_and_win: initial + respins +
// full_grid_jackpot + collector_total), клиент его ПРОИГРЫВАЕТ: зарядка,
// раскрытие номиналов, респины, Коллектор (искры от каждой монеты), сбор в
// TOTAL, GRAND за 9/9.

// Страницы-скины (neon-joker-spins-a|b|c.html) подменяют корень на свою папку арта.
const ASSET_ROOT = window.NJS_ASSET_ROOT || 'img/neon-joker-spins';
// Статика без Cache-Control — поднимать при ЛЮБОЙ замене файла в img/neon-joker-spins/.
const ASSET_VERSION = 3;

// Spine-слой (fx.js, window.NeonFx) — необязательный: без WebGL или при
// упавшей загрузке игра остаётся полностью на CSS.
function fx(name, ...args) {
  const F = window.NeonFx;
  if (!F || !F.ready || typeof F[name] !== 'function') return undefined;
  try {
    return F[name](...args);
  } catch (err) {
    console.warn(`[njs] fx ${name} failed:`, err);
    return undefined;
  }
}

function assetSrc(path) {
  return `${ASSET_ROOT}/${path}?v=${ASSET_VERSION}`;
}

// 1:1 контракт с app/seed/neon_joker_spins.py: код == имя файла в symbols/.
const SYMBOL_CODES = ['grape', 'plum', 'lemon', 'cherry', 'star', 'bell', 'seven', 'wild', 'scatter', 'coin'];
const FILLER_CODES = SYMBOL_CODES;
const COIN_CODE = 'coin';
const SCATTER_CODE = 'scatter';
const COLLECTOR_KIND = 'collector';

// Зеркалит JACKPOT_VALUES сида (множители ставки).
const JACKPOT_LADDER = { mini: 20, minor: 50, major: 250, grand: 1000 };

function symbolSrc(code) {
  return assetSrc(`symbols/${code}.webp`);
}
function coinSrc(name) {
  return assetSrc(`coins/${name}.webp`);
}

const GRID_COLS = 3;
const GRID_ROWS = 3;
const PAYLINE_ROWS = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];

const SYMBOL_LAYOUT = [
  ['seven', 'scatter', 'cherry'],
  ['bell', 'wild', 'coin'],
  ['lemon', 'coin', 'grape'],
];

const WIN_PULSE_MS = 620;
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;
const DIM_TRANSITION_MS = 320;
const WIN_LOOP_PAUSE_MS = 500;

// Турбо (бар V3): раунд Hold & Win играется вдвое быстрее, барабаны общего
// спина — на 80% быстрее (ReelSpin.PHYS.SPEED — объект на эту страницу).
const BASE_REEL_SPEED = window.ReelSpin ? ReelSpin.PHYS.SPEED : 0;
let timings = { hw: 1 };
let turbo = false;

function setTurbo(on) {
  turbo = !!on;
  timings = { hw: on ? 0.5 : 1 };
  if (window.ReelSpin) ReelSpin.PHYS.SPEED = BASE_REEL_SPEED * (on ? 1.8 : 1);
}
window.setTurbo = setTurbo;

let rowStep = 138;
function readCellDims() {
  const windowEl = document.getElementById('reel');
  if (windowEl && windowEl.clientHeight > 0) rowStep = windowEl.clientHeight / GRID_ROWS;
}

let cellInfos = [];
let reelCols = [];
let reelsBusy = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
// Пауза в раунде Hold & Win — короче в турбо (Коллектор: ~1.5с -> 0.5с, GDD §3.4).
function hwWait(ms) {
  return wait(Math.round(ms * timings.hw));
}

// rAF с таймерным дублёром: в скрытой вкладке кадров нет вовсе.
function afterFrame() {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    const timer = setTimeout(finish, 60);
    requestAnimationFrame(() => requestAnimationFrame(() => { clearTimeout(timer); finish(); }));
  });
}

function randomSymbolCode() {
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function restartClass(el, cls, ms) {
  if (!el) return;
  el.classList.remove(cls);
  void el.offsetWidth;
  el.classList.add(cls);
  if (ms) setTimeout(() => el.classList.remove(cls), ms);
}

// --- Битмап-шрифт ---------------------------------------------------------------
//
// glyphs/<char>.webp на общей высоте заглавной (116px у цифр); glyphs.json —
// размеры. Высота каждого глифа в % высоты контейнера, так что размер строки
// задаёт CSS контейнера (.glyphs { height }).
const GLYPH_CAP = 116;
let glyphSizes = null;
const GLYPH_FILES = { '.': 'dot', ',': 'comma' };

function glyphSrc(ch) {
  return assetSrc(`glyphs/${GLYPH_FILES[ch] || ch}.webp`);
}

function setGlyphs(el, text) {
  if (!el) return;
  const str = String(text).toLowerCase();
  if (el.dataset.text === str) return;
  el.dataset.text = str;
  el.innerHTML = '';
  for (const ch of str) {
    const size = glyphSizes && glyphSizes[ch];
    if (!size) continue;
    const img = document.createElement('img');
    img.src = glyphSrc(ch);
    img.alt = ch;
    img.style.height = `${(size[1] / GLYPH_CAP) * 100}%`;
    if (ch === ',') img.className = 'g-comma';
    el.appendChild(img);
  }
}
window.setGlyphs = setGlyphs;

function formatAmount(n) {
  return Math.round(Number(n)).toLocaleString('en-US');
}
// Компактно для монет: 1,500 -> 1.5k, 25,000 -> 25k.
function formatShort(n) {
  const v = Number(n);
  if (v >= 1e6) return `${+(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}m`;
  if (v >= 1e4) return `${+(v / 1e3).toFixed(v >= 1e5 ? 0 : 1)}k`;
  return formatAmount(v);
}

// --- Ячейки ---------------------------------------------------------------------

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  const img = document.createElement('img');
  img.className = 'sym';
  img.alt = code;
  img.decoding = 'async';
  img.src = symbolSrc(code);
  img.addEventListener('error', () => console.warn(`[njs] no art for symbol "${code}"`), { once: true });
  cell.appendChild(img);
  return { cell, img };
}

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
}

function clearCoinDecor(info) {
  info.cell.querySelectorAll('.coin-val, .cell-back').forEach((el) => el.remove());
  info.cell.classList.remove('is-empty', 'is-locked', 'is-hw-spin');
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  clearCoinDecor(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.img.src = symbolSrc(code);
}

// --- Win line ---------------------------------------------------------------------
const WIN_LINE_NS = 'http://www.w3.org/2000/svg';
let winLineSvg = null;

function cellCentreInStage(info) {
  const stage = document.getElementById('stage');
  const r = info.cell.getBoundingClientRect();
  return clientToStage(r.left + r.width / 2, r.top + r.height / 2, stage);
}

function clientToStage(x, y, stage = document.getElementById('stage')) {
  const s = stage.getBoundingClientRect();
  const k = s.width / stage.offsetWidth || 1;
  return { x: (x - s.left) / k, y: (y - s.top) / k };
}

function showWinLine(win) {
  // Spine-линия (неоновая трубка внутри окна, кометы) — по номеру линии.
  if (win && win.payline && fx('showLine', win.payline)) {
    if (winLineSvg) { winLineSvg.remove(); winLineSvg = null; }
    return wait(WIN_PULSE_MS);
  }
  const positions = (win && win.positions) || [];
  if (positions.length < 2) { hideWinLine(); return Promise.resolve(); }
  const stage = document.getElementById('stage');
  if (!winLineSvg) {
    winLineSvg = document.createElementNS(WIN_LINE_NS, 'svg');
    winLineSvg.setAttribute('class', 'win-line');
    stage.appendChild(winLineSvg);
  }
  const svg = winLineSvg;
  svg.setAttribute('width', stage.offsetWidth);
  svg.setAttribute('height', stage.offsetHeight);
  svg.style.left = '0px';
  svg.style.top = '0px';
  svg.setAttribute('viewBox', `0 0 ${stage.offsetWidth} ${stage.offsetHeight}`);
  const pts = positions.slice().sort((a, b) => a.col - b.col)
    .map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean).map(cellCentreInStage);
  // Линия от края до края окна, а не только между центрами.
  const reel = document.getElementById('reel');
  const rr = reel.getBoundingClientRect();
  const left = clientToStage(rr.left, 0).x;
  const right = clientToStage(rr.right, 0).x;
  const first = pts[0];
  const last = pts[pts.length - 1];
  const slope0 = pts.length > 1 ? (pts[1].y - first.y) / (pts[1].x - first.x) : 0;
  const slope1 = pts.length > 1 ? (last.y - pts[pts.length - 2].y) / (last.x - pts[pts.length - 2].x) : 0;
  const all = [{ x: left, y: first.y - slope0 * (first.x - left) }, ...pts, { x: right, y: last.y + slope1 * (right - last.x) }];
  const d = all.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  svg.innerHTML = '';
  // Скины рисуют свою линию (js/neon-joker-spins/winlines.js): точки — края
  // окна + центры ячеек, cells — только центры.
  if (window.NJS_WINLINE) window.NJS_WINLINE(svg, all, pts);
  else {
    for (const cls of ['win-line__glow', 'win-line__core']) {
      const path = document.createElementNS(WIN_LINE_NS, 'path');
      path.setAttribute('class', cls);
      path.setAttribute('d', d);
      svg.appendChild(path);
    }
  }
  svg.classList.remove('is-playing');
  void svg.getBoundingClientRect();
  svg.classList.add('is-playing');
  return wait(WIN_PULSE_MS);
}

function hideWinLine() {
  fx('hideLine');
  if (window.NJS_WINLINE_STOP) window.NJS_WINLINE_STOP();
  if (winLineSvg) {
    winLineSvg.remove();
    winLineSvg = null;
  }
}

let multiLineSequenceTimeout = null;
let multiLineToken = 0;

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

// Выигрыш символа: Spine-копия тайла играет свой клип (1.1с, у каждого
// символа своё движение) поверх ячейки; без Spine — CSS-пульс.
const SYMBOL_CLIP_MS = 1100;
function playWinAnimationOnce(info) {
  const inst = fx('symbol', info.cell, info.symbol);
  if (inst) {
    info.cell.classList.add('is-animating');
    return wait(SYMBOL_CLIP_MS).then(() => {
      fx('dropSymbol', inst);
      info.cell.classList.remove('is-animating');
    });
  }
  info.cell.classList.remove('is-winning');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-winning');
  return wait(WIN_PULSE_MS).then(() => info.cell.classList.remove('is-winning'));
}

function previewSymbolWin(info) {
  playWinAnimationOnce(info);
  burstAtCell(info, 'spark', 6);
}

function setCellActive(info, active) {
  info.cell.classList.toggle('is-win-active', active);
  if (!active) info.cell.classList.remove('is-winning');
}
function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
}

function playMultiLineWinSequence(groups, allWinInfos, lineWins) {
  const token = ++multiLineToken;
  let groupIndex = -1;
  const step = () => {
    const activeInfos = groupIndex === -1 ? allWinInfos : groups[groupIndex];
    const win = groupIndex >= 0 ? lineWins[groupIndex] : null;
    if (win) showWinLine(win); else hideWinLine();
    const activeSet = new Set(activeInfos);
    for (const info of cellInfos) if (info) setCellDimmed(info, !activeSet.has(info));
    for (const info of allWinInfos) setCellActive(info, activeSet.has(info));
    Promise.all(activeInfos.map(playWinAnimationOnce)).then(() => {
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

function playWinCells(winningCells, lineWins, countWins) {
  multiLineToken += 1;
  const allWinInfos = (winningCells || []).map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean);
  if (!allWinInfos.length) return;
  const groups = ReelMath.collectWinGroups(lineWins, countWins).map((positions) =>
    positions.map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean));
  const lines = [...(lineWins || []), ...(countWins || []).map(() => null)];
  allWinInfos.forEach((info) => burstAtCell(info, 'spark', 4));
  fx('setWin', true);
  if (groups.length) playMultiLineWinSequence(groups, allWinInfos, lines);
}

// --- FX-спрайты ----------------------------------------------------------------
//
// fx/*.webp (лист ChatGPT, нарезан аддитивно — alpha = яркость) кладутся в
// #fxLayer в координатах сцены и живут на WAAPI; в скрытой вкладке анимации
// просто завершаются по таймеру удаления.
function fxSprite(name, x, y, size) {
  const layer = document.getElementById('fxLayer');
  const img = document.createElement('img');
  img.className = 'fx-sprite';
  img.src = assetSrc(`fx/${name}.webp`);
  img.style.width = `${size}px`;
  img.style.transform = `translate(${x - size / 2}px, ${y - size / 2}px)`;
  layer.appendChild(img);
  return img;
}

function burstAt(x, y, name = 'spark', count = 8, spread = 90, size = 46) {
  for (let i = 0; i < count; i++) {
    const s = size * (0.6 + Math.random() * 0.7);
    const el = fxSprite(name, x, y, s);
    const a = Math.random() * Math.PI * 2;
    const r = spread * (0.5 + Math.random() * 0.6);
    const dx = Math.cos(a) * r;
    const dy = Math.sin(a) * r;
    const base = `translate(${x - s / 2}px, ${y - s / 2}px)`;
    el.animate([
      { transform: `${base} scale(0.2) rotate(0deg)`, opacity: 1 },
      { transform: `translate(${x - s / 2 + dx}px, ${y - s / 2 + dy}px) scale(1) rotate(${(Math.random() - 0.5) * 240}deg)`, opacity: 0 },
    ], { duration: 650 + Math.random() * 350, easing: 'cubic-bezier(0.2, 0.8, 0.3, 1)', fill: 'forwards' });
    setTimeout(() => el.remove(), 1100);
  }
}

function ringAt(x, y, name = 'ring_pink', size = 160, ms = 600) {
  const el = fxSprite(name, x, y, size);
  const base = `translate(${x - size / 2}px, ${y - size / 2}px)`;
  el.animate([
    { transform: `${base} scale(0.3)`, opacity: 1 },
    { transform: `${base} scale(1.5)`, opacity: 0 },
  ], { duration: ms, easing: 'ease-out', fill: 'forwards' });
  setTimeout(() => el.remove(), ms + 60);
}

function burstAtCell(info, name, count) {
  const p = cellCentreInStage(info);
  burstAt(p.x, p.y, name, count, rowStep * 0.55, rowStep * 0.32);
}

// Искра летит от точки к точке по дуге — «неоновая искра с номиналом» Коллектора.
function flySpark(from, to, ms, { name = 'orb_pink', size = 56 } = {}) {
  const el = fxSprite(name, from.x, from.y, size);
  const mid = { x: (from.x + to.x) / 2 + (Math.random() - 0.5) * 80, y: Math.min(from.y, to.y) - 60 };
  const t = (p) => `translate(${p.x - size / 2}px, ${p.y - size / 2}px)`;
  el.animate([
    { transform: `${t(from)} scale(0.6)`, opacity: 0.2 },
    { transform: `${t(mid)} scale(1.1)`, opacity: 1, offset: 0.5 },
    { transform: `${t(to)} scale(0.7)`, opacity: 1 },
  ], { duration: ms, easing: 'cubic-bezier(0.4, 0, 0.6, 1)', fill: 'forwards' });
  setTimeout(() => el.remove(), ms + 40);
  return wait(ms);
}

function confettiRain(ms = 2200) {
  const stage = document.getElementById('stage');
  const W = stage.offsetWidth;
  const end = Date.now() + ms;
  const tick = () => {
    if (Date.now() > end) return;
    for (let i = 0; i < 4; i++) {
      const name = ['confetti', 'ribbon', 'spark', 'coin_edge'][Math.floor(Math.random() * 4)];
      const x = Math.random() * W;
      const s = 26 + Math.random() * 30;
      const el = fxSprite(name, x, -40, s);
      const dur = 1600 + Math.random() * 1200;
      el.animate([
        { transform: `translate(${x}px, -40px) rotate(0deg)`, opacity: 1 },
        { transform: `translate(${x + (Math.random() - 0.5) * 160}px, ${stage.offsetHeight + 40}px) rotate(${Math.random() * 720}deg)`, opacity: 0.9 },
      ], { duration: dur, easing: 'ease-in', fill: 'forwards' });
      setTimeout(() => el.remove(), dur + 50);
    }
    setTimeout(tick, 90);
  };
  tick();
}

function mascotCheer(clip = 'cheer') {
  if (window.NeonFx && NeonFx.ready && document.body.classList.contains('fx-mascot')) {
    fx('mascot', clip);
    return;
  }
  if (window.NJS_MASCOT) {   // скины: живой маскот (js/neon-joker-spins/mascot.js)
    NJS_MASCOT.react(clip);
    return;
  }
  restartClass(document.getElementById('mascot'), 'is-cheer', 950);
}
window.mascotCheer = mascotCheer;

// --- Сумма под окном ------------------------------------------------------------
let reelWinTimeout = null;
function showInlineWinAmount(amount) {
  const el = document.getElementById('reelWin');
  setGlyphs(document.getElementById('reelWinValue'), formatAmount(amount));
  el.classList.add('is-on');
  clearTimeout(reelWinTimeout);
  reelWinTimeout = setTimeout(() => el.classList.remove('is-on'), 1900);
}
function hideInlineWinAmount() {
  clearTimeout(reelWinTimeout);
  document.getElementById('reelWin').classList.remove('is-on');
}

async function applyGrid(grid) {
  teardownCellInstances();
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) setCellSymbol(cellInfos[row * GRID_COLS + col], grid[row][col]);
  }
}

// --- Движение барабанов: общий спин (js/reel-spin.js) ----------------------------
//
// Стандарт студии (спин Gangsta Casino): разгон в бесшовную петлю, пока
// отвечает сервер; барабан i прокручивает i*2 лишних фигуры, тормозит
// ease-out на последней ячейке без отскока; на скорости символы подменяются
// размытыми двойниками symbols/<code>_blur.webp (build-скрипт, blur()).

const REEL_STAGGER_FIGURES = 2;
let reelSpin = null;

function getReelSpin() {
  if (!reelSpin) {
    reelSpin = ReelSpin.create({
      cols: () => reelCols,
      rows: GRID_ROWS,
      rowStep: () => rowStep,
      makeCell: (code) => createCellNode(code).cell,
      loopFiller: randomSymbolCode,
      codes: SYMBOL_CODES,
      onReelStop: (col, isLast) => {
        Sound.playSfx(isLast ? 'finalReelStop' : 'reelStop');
        fx('reelStop', col);
      },
    });
  }
  return reelSpin;
}
window.addEventListener('load', () => getReelSpin());

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  hideInlineWinAmount();
  readCellDims();
  fx('spinStart');
  getReelSpin().startLoop();
}

function stopReelLoop() {
  reelsBusy = false;
  getReelSpin().stopLoop();
}

function landReel(colIndex, finalCodes, extraFigures = 0, isAnticipating = false) {
  return getReelSpin().landReel(colIndex, finalCodes, { extra: extraFigures, anticipating: isAnticipating });
}

// Ячейки уже собраны общим спином — заводим на них info и играем посадку;
// спец-символы (Джокер, монета) приземляются со вспышкой кольца.
function settleColumnCells(cellEls, col, finalCodes) {
  for (let row = 0; row < GRID_ROWS; row++) {
    const cell = cellEls[row];
    const info = { symbol: finalCodes[row], row, col, cell, img: cell.querySelector('img'), winLoopTimeout: null };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    restartClass(cell, 'is-landing', 280);
    if (info.symbol === SCATTER_CODE) {
      // landing: the Joker blinks, the ring turns, the bells jingle
      const inst = fx('symbol', cell, 'scatter_land');
      if (inst) {
        cell.classList.add('is-animating');
        setTimeout(() => { fx('dropSymbol', inst); cell.classList.remove('is-animating'); }, 900);
      }
    }
    if (info.symbol === SCATTER_CODE || info.symbol === COIN_CODE) {
      setTimeout(() => {
        const p = cellCentreInStage(info);
        ringAt(p.x, p.y, info.symbol === SCATTER_CODE ? 'ring_pink' : 'ring_cyan', rowStep * 1.1, 520);
      }, 20);
      Sound.blip(info.symbol === SCATTER_CODE ? 660 : 990);
    }
  }
}

// Антиципация: третий барабан решает — 2 Джокера (3-й даст фриспины),
// 3+ монеты на первых двух (из 5 нужных), или пара хай-символов на линии.
const ANTICIPATION_CODES = new Set(['seven', 'bell', 'star', 'wild']);
function anticipationColumns(codes) {
  let jokers = 0;
  let coins = 0;
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let col = 0; col < 2; col++) {
      if (codes[row][col] === SCATTER_CODE) jokers += 1;
      if (codes[row][col] === COIN_CODE) coins += 1;
    }
  }
  if (jokers >= 2 || coins >= 3) return [2];
  for (const line of PAYLINE_ROWS) {
    const first = codes[line[0]][0];
    if (ANTICIPATION_CODES.has(first) && first === codes[line[1]][1]) return [2];
  }
  return [];
}

async function landReels(grid, { anticipate = true } = {}) {
  reelsBusy = true;
  window.__lastAnticipated = false;
  try {
    teardownCellInstances();
    const columnCodes = (col) => [grid[0][col], grid[1][col], grid[2][col]];
    const anticipating = anticipate ? anticipationColumns(grid) : [];
    const firstAnt = anticipating.length ? Math.min(...anticipating) : GRID_COLS;
    const lead = [];
    for (let col = 0; col < firstAnt; col++) {
      const codes = columnCodes(col);
      lead.push(landReel(col, codes, col * REEL_STAGGER_FIGURES).then((els) => settleColumnCells(els, col, codes)));
    }
    await Promise.all(lead);
    if (firstAnt < GRID_COLS) {
      Sound.playSfx('anticipation');
      fx('anticipation', true);
      fx('mascotNear', true);
      if (window.NJS_MASCOT) NJS_MASCOT.near(true);
      window.__lastAnticipated = true;
      for (let col = firstAnt; col < GRID_COLS; col++) {
        const codes = columnCodes(col);
        reelCols[col].colEl.classList.add('is-anticipating');
        const els = await landReel(col, codes, REEL_STAGGER_FIGURES, true);
        reelCols[col].colEl.classList.remove('is-anticipating');
        settleColumnCells(els, col, codes);
      }
      fx('anticipation', false);
      fx('mascotNear', false);
      if (window.NJS_MASCOT) NJS_MASCOT.near(false);
    }
  } finally {
    reelsBusy = false;
    await flushDeviceRebuild();
  }
}

// --- Затемнение и попапы ----------------------------------------------------------

let dimCount = 0;
function pushScreenDim() {
  dimCount += 1;
  document.getElementById('screenDim').classList.add('is-active');
}
function popScreenDim() {
  dimCount = Math.max(0, dimCount - 1);
  if (!dimCount) document.getElementById('screenDim').classList.remove('is-active');
}

// Попап = вывеска-заголовок (popups/<key>.webp) + общая панель суммы
// (popups/panel.webp) + сумма шрифтом. Нет арта — неоновый CSS-текст.
const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN' },
  megaWin: { title: 'MEGA WIN', confetti: true },
  epicWin: { title: 'EPIC WIN', confetti: true },
  freeSpins: { title: 'FREE SPINS' },
  holdAndWin: { title: 'HOLD & WIN', noPanel: true },
  totalWin: { title: 'TOTAL WIN', confetti: true },
};
let popupArt = {};

function buildPopupNode(key, amount, { sub = null, breakdown = null, panelText = null } = {}) {
  const cfg = POPUP_CONFIG[key];
  const root = document.createElement('div');
  root.className = `game-popup game-popup--${key}`;
  if (popupArt[key]) {
    const img = document.createElement('img');
    img.className = 'game-popup__title-img';
    img.src = assetSrc(`popups/${key}.webp`);
    root.appendChild(img);
  } else {
    const t = document.createElement('div');
    t.className = 'game-popup__title';
    t.textContent = cfg.title;
    root.appendChild(t);
  }
  if (!cfg.noPanel) {
    const panel = document.createElement('div');
    panel.className = 'game-popup__panel';
    if (popupArt.panel) {
      panel.classList.add('has-art');
      panel.style.backgroundImage = `url('${assetSrc('popups/panel.webp')}')`;
    }
    const g = document.createElement('div');
    g.className = 'glyphs';
    panel.appendChild(g);
    root.appendChild(panel);
    root._amountEl = g;
    setGlyphs(g, panelText != null ? panelText : '0');
  }
  if (sub) {
    const s = document.createElement('div');
    s.className = 'game-popup__sub';
    s.textContent = sub;
    root.appendChild(s);
  }
  if (breakdown && breakdown.length) {
    const b = document.createElement('div');
    b.className = 'game-popup__breakdown';
    b.innerHTML = breakdown.map(([label, v]) => `<span>${label}</span><b>${formatAmount(v)}</b>`).join('');
    root.appendChild(b);
  }
  return root;
}

// Счёт суммы вверх таймером (не rAF — в скрытой вкладке тоже доигрывает).
function countUp(el, to, ms) {
  const steps = Math.max(1, Math.round(ms / 50));
  for (let i = 1; i <= steps; i++) {
    setTimeout(() => setGlyphs(el, formatAmount((to * i) / steps)), (ms * i) / steps);
  }
}

// Один finish() на любой выход — иначе упавший попап оставил бы экран тёмным.
// Тап по экрану пропускает (GDD: заставка FS «пропускается тапом»).
function playPopup(key, amount = 0, holdMs = 2500, opts = {}) {
  if (!POPUP_CONFIG[key]) return Promise.resolve();
  return new Promise((resolve) => {
    let node = null;
    let done = false;
    let skip = null;
    let titleInst = null;
    const big = ['bigWin', 'megaWin', 'epicWin', 'totalWin'].includes(key);
    const skipP = new Promise((r) => { skip = r; });
    const onTap = () => skip();
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safety);
      document.getElementById('screen').removeEventListener('pointerdown', onTap);
      if (node) node.remove();
      fx('dropTitle', titleInst);
      if (big) fx('bigWin', false);
      popScreenDim();
      resolve();
    };
    const safety = setTimeout(finish, holdMs + 8000);
    (async () => {
      Sound.playSfx('popupOpen');
      pushScreenDim();
      await wait(DIM_TRANSITION_MS);
      node = buildPopupNode(key, amount, opts);
      document.getElementById('popupHost').appendChild(node);
      positionPopup(node);
      void node.offsetWidth;
      node.classList.add('is-in');
      const titleImg = node.querySelector('.game-popup__title-img');
      if (titleImg) {
        titleInst = fx('popupTitle', titleImg, key);
        if (titleInst) titleImg.classList.add('is-spine');
      }
      if (big) fx('bigWin', true);
      if (node._amountEl && opts.panelText == null) countUp(node._amountEl, amount, Math.min(1400, holdMs * 0.6));
      if (POPUP_CONFIG[key].confetti) confettiRain(holdMs);
      mascotCheer();
      setTimeout(() => document.getElementById('screen').addEventListener('pointerdown', onTap), 400);
      await Promise.race([wait(POPUP_ENTER_MS + holdMs), skipP]);
      if (node._amountEl && opts.panelText == null) setGlyphs(node._amountEl, formatAmount(amount));
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`[njs] popup "${key}" failed:`, err);
      finish();
    });
  });
}
window.playPopup = playPopup;

// По центру окна барабанов, а не экрана (в портрете слот выше центра).
function positionPopup(node) {
  const host = document.getElementById('popupHost').getBoundingClientRect();
  const reel = document.getElementById('reel').getBoundingClientRect();
  if (!reel.height) return;
  node.style.top = `${Math.round(reel.top - host.top + reel.height / 2)}px`;
}

// --- Джекпоты ---------------------------------------------------------------------

function updateJackpotPlates(bet) {
  for (const [tier, mult] of Object.entries(JACKPOT_LADDER)) {
    setGlyphs(document.querySelector(`.jp--${tier} .jp__value`), formatShort(mult * bet));
  }
}
window.updateJackpotPlates = updateJackpotPlates;

function isJackpotKind(kind) {
  return Object.prototype.hasOwnProperty.call(JACKPOT_LADDER, kind);
}

function hitPlate(tier) {
  const plate = document.querySelector(`.jp--${tier}`);
  if (!plate) return;
  restartClass(plate, 'is-hit', 1250);
  fx('jackpotHit', tier);
  mascotCheer('bow');
  const r = plate.getBoundingClientRect();
  const p = clientToStage(r.left + r.width / 2, r.top + r.height / 2);
  burstAt(p.x, p.y, 'spark', 14, 140, 50);
  ringAt(p.x, p.y, 'ring_cyan', 260, 700);
  Sound.ding(1.2);
}

// --- Free Spins: режим и панель -------------------------------------------------

function setFreeSpinsMode(on) {
  document.getElementById('screen').classList.toggle('is-fs', on);
  fx('setMode', on ? 'fs' : 'base');
  document.getElementById('fsPanel').classList.toggle('is-on', on);
}
window.setFreeSpinsMode = setFreeSpinsMode;

function updateFreeSpinsPanel(left, win) {
  setGlyphs(document.getElementById('fsLeft'), String(left));
  setGlyphs(document.getElementById('fsWin'), formatAmount(win || 0));
}
window.updateFreeSpinsPanel = updateFreeSpinsPanel;

function flashRetrigger(added) {
  const el = document.getElementById('fsPlus');
  el.textContent = `+${added}`;
  restartClass(el, 'is-on', 1550);
  restartClass(document.getElementById('fsPanel'), 'is-pulse', 560);
  Sound.blip(1320);
  mascotCheer();
}
window.flashRetrigger = flashRetrigger;

// Джокеры на поле смеются и «щёлкают пальцами» (P0) перед заставкой FS.
async function celebrateScatters() {
  const jokers = cellInfos.filter((i) => i && i.symbol === SCATTER_CODE);
  jokers.forEach((info) => {
    playWinAnimationOnce(info);
    const p = cellCentreInStage(info);
    burstAt(p.x, p.y, 'heart', 5, rowStep * 0.6, rowStep * 0.3);
    ringAt(p.x, p.y, 'ring_pink', rowStep * 1.4, 700);
  });
  mascotCheer('laugh');
  Sound.playSfx('bigWin');
  await wait(1300);
}
window.celebrateScatters = celebrateScatters;

// --- Hold & Win ---------------------------------------------------------------------

function setCellEmpty(info) {
  clearCoinDecor(info);
  info.cell.classList.add('is-empty');
  info.cell.classList.remove('is-dimmed');
  const back = document.createElement('img');
  back.className = 'cell-back cell-back--empty';
  back.src = coinSrc('cell_empty');
  info.cell.prepend(back);
}

// Монета на поле: пустая монета + номинал шрифтом, джекпот — свой арт,
// Коллектор — рамка COLLECT + собранная сумма.
function setCoinFace(info, coin) {
  clearCoinDecor(info);
  info.cell.classList.add('is-locked');
  const back = document.createElement('img');
  back.className = 'cell-back';
  back.src = coinSrc('cell_locked');
  info.cell.prepend(back);
  const kind = coin.kind;
  if (isJackpotKind(kind)) {
    info.symbol = COIN_CODE;
    info.cell.dataset.symbol = 'jackpot';
    info.img.src = coinSrc(kind);
    return;
  }
  const collector = kind === COLLECTOR_KIND;
  info.symbol = collector ? COLLECTOR_KIND : COIN_CODE;
  info.cell.dataset.symbol = collector ? 'collector' : 'coin';
  info.img.src = coinSrc(collector ? 'collector' : 'blank');
  const val = document.createElement('div');
  val.className = 'coin-val glyphs';
  info.cell.appendChild(val);
  setGlyphs(val, collector ? '0x' : `${coin.value}x`);
  info.valEl = val;
}

function setRespinLamps(lit) {
  document.querySelectorAll('#hwPanel .hw-lamp').forEach((el, i) => el.classList.toggle('is-lit', i < lit));
}

let hwTotalShown = 0;
function tweenHwTotal(to, ms = 260) {
  const el = document.getElementById('hwTotal');
  const from = hwTotalShown;
  hwTotalShown = to;
  const steps = 8;
  for (let i = 1; i <= steps; i++) {
    setTimeout(() => setGlyphs(el, formatAmount(from + ((to - from) * i) / steps)), (ms * i) / steps);
  }
  restartClass(document.getElementById('hwPanel'), 'is-pulse', 520);
}

function enterHoldAndWinMode() {
  document.getElementById('screen').classList.add('is-hw');
  fx('holdWinStart');
  fx('setMode', 'hw');
  document.getElementById('hwPanel').classList.add('is-on');
  // В FS панель фриспинов уступает место (счётчик заморожен на время раунда).
  document.getElementById('fsPanel').classList.remove('is-on');
}
function exitHoldAndWinMode() {
  const screen = document.getElementById('screen');
  screen.classList.remove('is-hw');
  document.getElementById('hwPanel').classList.remove('is-on');
  if (screen.classList.contains('is-fs')) document.getElementById('fsPanel').classList.add('is-on');
  fx('setMode', screen.classList.contains('is-fs') ? 'fs' : 'base');
}
window.exitHoldAndWinMode = exitHoldAndWinMode;

// Коллектор: от каждой обычной монеты к нему летит искра, число на нём
// растёт с отсчётом (~1.5с, турбо 0.5с).
async function playCollector(info, coinsOnGrid, total) {
  const to = cellCentreInStage(info);
  ringAt(to.x, to.y, 'ring_pink', rowStep * 1.6, 700);
  burstAt(to.x, to.y, 'spark', 10, rowStep * 0.7, rowStep * 0.3);
  Sound.blip(520);
  mascotCheer();
  await hwWait(450);
  const per = Math.max(110, Math.min(300, 1500 / Math.max(1, coinsOnGrid.length))) * timings.hw;
  let acc = 0;
  for (let n = 0; n < coinsOnGrid.length; n++) {
    const { coin, info: from } = coinsOnGrid[n];
    restartClass(from.cell, 'is-collect', 420);
    Sound.spark(n);
    flySpark(cellCentreInStage(from), to, per * 1.4);
    await wait(per);
    acc += Number(coin.value);
    setGlyphs(info.valEl, `${acc}x`);
  }
  await wait(per * 0.5);
  setGlyphs(info.valEl, `${total}x`);
  restartClass(info.cell, 'is-slam', 440);
  burstAt(to.x, to.y, 'burst', 1, 0, rowStep * 1.2);
  burstAt(to.x, to.y, 'spark', 12, rowStep * 0.8, rowStep * 0.3);
  Sound.ding(1);
  await hwWait(500);
}

async function playHoldAndWin(hw, bet) {
  teardownCellInstances();
  hwTotalShown = 0;
  const idx = (c) => c.row * GRID_COLS + c.col;
  const locked = new Map(); // index -> {coin, info}
  const initial = (hw.initial || []).slice().sort((a, b) => a.col - b.col || a.row - b.row);

  // 1. зарядка монет-триггеров
  const coinInfos = initial.map((c) => cellInfos[idx(c)]).filter(Boolean);
  coinInfos.forEach((info) => {
    restartClass(info.cell, 'is-charging', 920);
    burstAtCell(info, 'spark', 5);
  });
  Sound.ding(0.8);
  await hwWait(1000);

  // 2. вывеска HOLD & WIN, режим раунда
  if (!(await showBonusScreen('hw'))) await playPopup('holdAndWin', 0, turbo ? 600 : 1300);
  enterHoldAndWinMode();
  const initialSet = new Set(initial.map(idx));
  cellInfos.forEach((info, i) => { if (info && !initialSet.has(i)) setCellEmpty(info); });
  setRespinLamps(3);
  setGlyphs(document.getElementById('hwTotal'), '0');

  // 3. раскрытие номиналов
  for (const c of initial) {
    const info = cellInfos[idx(c)];
    if (!info) continue;
    setCoinFace(info, c);
    restartClass(info.cell, 'is-slam', 440);
    Sound.blip(880);
    locked.set(idx(c), { coin: c, info });
    if (isJackpotKind(c.kind)) {
      await hwWait(250);
      hitPlate(c.kind);
      await hwWait(500);
    } else {
      await hwWait(260);
    }
  }
  await hwWait(350);

  // 4. респины
  let left = 3;
  for (const respin of hw.respins || []) {
    left -= 1;
    setRespinLamps(left);
    const landed = respin.landed || [];
    const coinsLanded = landed.filter((c) => c.kind !== COLLECTOR_KIND);
    const collectors = landed.filter((c) => c.kind === COLLECTOR_KIND);
    const landedByIdx = new Map(coinsLanded.map((c) => [idx(c), c]));
    const collectorIdx = new Set(collectors.map(idx));
    const empties = cellInfos.filter((info, i) => info && !locked.has(i));
    empties.forEach((info) => info.cell.classList.add('is-hw-spin'));
    Sound.playSfx('spinStart');
    await hwWait(380);
    for (let col = 0; col < GRID_COLS; col++) {
      await hwWait(220);
      let stopped = false;
      for (let row = 0; row < GRID_ROWS; row++) {
        const i = row * GRID_COLS + col;
        const info = cellInfos[i];
        if (!info || locked.has(i)) continue;
        info.cell.classList.remove('is-hw-spin');
        stopped = true;
        const c = landedByIdx.get(i);
        if (collectorIdx.has(i)) {
          // Коллектор встаёт сразу, но считает ПОСЛЕ монет этого респина.
          setCoinFace(info, { kind: COLLECTOR_KIND, value: 0 });
          restartClass(info.cell, 'is-slam', 440);
          continue;
        }
        if (!c) continue;
        setCoinFace(info, c);
        restartClass(info.cell, 'is-slam', 440);
        burstAtCell(info, 'spark', 5);
        Sound.blip(990);
        locked.set(i, { coin: c, info });
        if (isJackpotKind(c.kind)) hitPlate(c.kind);
      }
      if (stopped) Sound.playSfx(col === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop');
    }
    // Коллекторы этого респина: сумма всех обычных монет на поле (без
    // джекпотов и других Коллекторов) — значение уже посчитал сервер.
    for (const c of collectors) {
      const info = cellInfos[idx(c)];
      const plain = [...locked.values()]
        .filter(({ coin }) => coin.kind !== COLLECTOR_KIND && !isJackpotKind(coin.kind))
        .sort((a, b) => a.coin.col - b.coin.col || a.coin.row - b.coin.row);
      await playCollector(info, plain, c.value);
      locked.set(idx(c), { coin: c, info });
    }
    if (landed.length) {
      left = 3;
      setRespinLamps(3);
      restartClass(document.querySelector('#hwPanel .hw-lamps'), 'is-reset', 620);
      await hwWait(700);
    } else {
      await hwWait(450);
    }
  }
  cellInfos.forEach((info) => info && info.cell.classList.remove('is-hw-spin'));

  // 5. сбор в TOTAL
  await hwWait(350);
  const meter = document.getElementById('hwTotal');
  const mr = meter.getBoundingClientRect();
  const meterPt = clientToStage(mr.left + mr.width / 2, mr.top + mr.height / 2);
  let total = 0;
  const order = [...locked.values()].sort((a, b) => a.coin.col - b.coin.col || a.coin.row - b.coin.row);
  let n = 0;
  for (const { coin, info } of order) {
    restartClass(info.cell, 'is-collect', 420);
    Sound.spark(n++);
    flySpark(cellCentreInStage(info), meterPt, 360 * timings.hw, { name: 'orb_cyan', size: 44 });
    const value = isJackpotKind(coin.kind) ? JACKPOT_LADDER[coin.kind] : Number(coin.value);
    total += value * bet;
    tweenHwTotal(total);
    await hwWait(260);
  }
  if (hw.full_grid_jackpot && JACKPOT_LADDER[hw.full_grid_jackpot]) {
    const tier = hw.full_grid_jackpot;
    await hwWait(300);
    cellInfos.forEach((info) => burstAtCell(info, 'spark', 3));
    hitPlate(tier);
    confettiRain(1800);
    await hwWait(900);
    total += JACKPOT_LADDER[tier] * bet;
    tweenHwTotal(total, 600);
  }
  Sound.ding(1.3);
  await hwWait(800);
  return total;
}
window.playHoldAndWin = playHoldAndWin;

// --- Окно покупки -----------------------------------------------------------------

function showBuyDialog(price, currency) {
  const dlg = document.getElementById('buyDialog');
  document.getElementById('buyDialogPrice').textContent = formatAmount(price);
  document.getElementById('buyDialogCur').textContent = currency;
  dlg.hidden = false;
  Sound.playSfx('popupOpen');
  return new Promise((resolve) => {
    const close = (ok) => {
      dlg.hidden = true;
      yes.removeEventListener('click', onYes);
      no.removeEventListener('click', onNo);
      dlg.removeEventListener('click', onBack);
      Sound.playSfx('popupClose');
      resolve(ok);
    };
    const yes = document.getElementById('buyYes');
    const no = document.getElementById('buyNo');
    const onYes = () => close(true);
    const onNo = () => close(false);
    const onBack = (e) => { if (e.target === dlg) close(false); };
    yes.addEventListener('click', onYes);
    no.addEventListener('click', onNo);
    dlg.addEventListener('click', onBack);
  });
}
window.showBuyDialog = showBuyDialog;

// --- Dev-панель -----------------------------------------------------------------

function setupDevPanel() {
  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 123456));
  });
  document.querySelectorAll('[data-screen]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const k = btn.dataset.screen;
      if (k === 'feature') showFeatureScreen(); else showBonusScreen(k);
    });
  });
}

// --- Превью фич / бонус-экраны -----------------------------------------------------
//
// Spine-скелеты из scripts/neon_joker_spins_screens.py (у каждого скина свои —
// в ASSET_ROOT/screens): `intro` (3 с) -> `idle` (петля) до тапа, затем 500 мс
// затухания. Нарисованы на дизайн-канвасе игры (1600x900 / 720x1280, центр в
// нуле) и привязаны к #stage его дизайн-боксом. Свой SpineStage на
// #screenCanvas поверх всего. Атласы кита — premultiplied. Нет WebGL или
// скелета — экран просто не показывается (бонус уходит в старый попап).

const SCREEN_ROOT = `${ASSET_ROOT}/screens`;
const SCREEN_BOX = {
  desk: { x: -800, y: -450, width: 1600, height: 900 },
  mob: { x: -360, y: -640, width: 720, height: 1280 },
};
const SCREEN_V = 3;                 // поднимать при пересборке screens
const SCREEN_FADE_MS = 500;
const BONUS_SCREEN_AUTOCLOSE_MS = 10000;
let screenStage = null;
let screenOpen = false;
const screenResourceCache = {};

function screenVariant() {
  return isMobileLayout() ? 'mob' : 'desk';
}

function getScreenStage() {
  if (screenStage) return screenStage;
  if (!window.spine || !window.SpineEngine) return null;
  try {
    screenStage = new SpineEngine.SpineStage(document.getElementById('screenCanvas'));
  } catch (err) {
    console.warn('[njs] screens: no WebGL', err);
    return null;
  }
  return screenStage;
}

function getScreenResource(kind, variant = screenVariant()) {
  const key = `${kind}_${variant}`;
  if (!screenResourceCache[key]) {
    screenResourceCache[key] = SpineEngine.SpineResource.load(screenStage.assetManager, `${SCREEN_ROOT}/${key}`, {
      premultipliedAlpha: true, version: SCREEN_V,
    });
    screenResourceCache[key].catch(() => { delete screenResourceCache[key]; });
  }
  return screenResourceCache[key];
}

function showSpineScreen(kind, { dark = false, autoCloseMs = 0 } = {}) {
  const root = document.getElementById('featureScreen');
  const stage = getScreenStage();
  if (!stage || !root || screenOpen) return Promise.resolve(false);
  screenOpen = true;
  return getScreenResource(kind).then((resource) => new Promise((resolve) => {
    let variant = screenVariant();
    let inst = null;
    let alpha = 1;
    let done = false;
    let closing = false;
    let autoTimer = null;

    const mount = (res, fromEntry) => {
      const next = res.createInstance();
      next.anchorEl = document.getElementById('stage');
      next.fit = 1;
      next.boundsOverride = SCREEN_BOX[variant];
      if (fromEntry && fromEntry.animation) {
        const entry = next.animationState.setAnimation(0, fromEntry.animation.name, fromEntry.loop);
        entry.trackTime = fromEntry.trackTime;
        if (!fromEntry.loop) next.queue('idle', true);
      } else {
        next.play('intro', false);
        next.queue('idle', true);
      }
      next.skeleton.color.a = alpha;
      if (inst) stage.removeOverlay(inst);
      inst = next;
      stage.addOverlay(inst);
    };
    root.classList.toggle('is-dark', dark);
    const setBg = () => {
      const src = `${ASSET_ROOT}/img/${isMobileLayout() ? 'bg_base_mob' : 'bg_base'}.jpg`;
      root.style.setProperty('--fs-bg', `url("${new URL(src, location.href).href}")`);
    };
    const onResize = () => {
      setBg();
      const v = screenVariant();
      if (v === variant || closing) return;
      variant = v;
      const entry = inst.animationState.getCurrent(0);
      getScreenResource(kind, v).then((res) => { if (!done) mount(res, entry); }).catch(() => {});
    };

    setBg();
    mount(resource, null);
    window.addEventListener('resize', onResize);
    document.body.classList.add('is-feature-screen');
    root.hidden = false;
    void root.offsetWidth;
    root.classList.add('is-open');

    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(autoTimer);
      stage.removeOverlay(inst);
      window.removeEventListener('resize', onResize);
      root.hidden = true;
      root.classList.remove('is-open');
      root.style.transition = '';
      document.body.classList.remove('is-feature-screen');
      screenOpen = false;
      resolve(true);
    };
    const close = () => {
      if (closing) return;
      closing = true;
      clearTimeout(autoTimer);
      root.removeEventListener('click', close);
      if (window.Sound) Sound.playSfx('click');
      root.style.transition = `opacity ${SCREEN_FADE_MS}ms ease-out`;
      root.classList.remove('is-open');
      const start = performance.now();
      const tick = (now) => {
        if (done) return;
        const t = Math.min(1, (now - start) / SCREEN_FADE_MS);
        alpha = 1 - t;
        inst.skeleton.color.a = alpha;
        if (t < 1) requestAnimationFrame(tick);
        else finish();
      };
      requestAnimationFrame(tick);
      setTimeout(finish, SCREEN_FADE_MS + 200); // скрытая вкладка: rAF стоит
    };
    root.addEventListener('click', close);
    if (autoCloseMs) autoTimer = setTimeout(close, autoCloseMs);
  })).catch((err) => {
    console.warn(`[njs] ${kind} screen failed:`, err);
    screenOpen = false;
    document.body.classList.remove('is-feature-screen');
    root.hidden = true;
    return false;
  });
}

function showFeatureScreen() {
  return showSpineScreen('feature');
}

// kind: 'fs' (вход во фриспины) | 'hw' (вход в Hold & Win). false — экрана нет,
// вызывающий показывает старый попап.
function showBonusScreen(kind) {
  return showSpineScreen(`bonus_${kind}`, { dark: true, autoCloseMs: BONUS_SCREEN_AUTOCLOSE_MS });
}
window.showBonusScreen = showBonusScreen;

// --- Вьюпорт ---------------------------------------------------------------------

const DESIGN = { desktop: { w: 1600, h: 900 }, mobile: { w: 720, h: 1280 } };

function updateStageScale() {
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth || document.documentElement.clientWidth;
  const vh = screenEl.clientHeight || document.documentElement.clientHeight;
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  const scale = Math.min(vw / d.w, vh / d.h);
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  readCellDims();
}

let lastMobile = null;
let pendingDeviceRebuild = false;

async function handleResize() {
  updateStageScale();
  const nowMobile = isMobileLayout();
  if (nowMobile === lastMobile) return;
  lastMobile = nowMobile;
  pendingDeviceRebuild = true;
  await flushDeviceRebuild();
}

async function flushDeviceRebuild() {
  if (!pendingDeviceRebuild || reelsBusy || document.getElementById('screen').classList.contains('is-hw')) return;
  pendingDeviceRebuild = false;
  const snapshot = cellInfos.map((info) => (info ? info.symbol : null));
  teardownCellInstances();
  buildReelGrid();
  cellInfos.forEach((info, i) => setCellSymbol(info, SYMBOL_CODES.includes(snapshot[i]) ? snapshot[i] : info.symbol));
}

// --- Прелоадер ---------------------------------------------------------------------
const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const img = new Image();
  img.src = src;
  return img.decode ? img.decode() : new Promise((res) => { img.onload = res; img.onerror = res; });
}

function probeImage(src) {
  return new Promise((res) => {
    const img = new Image();
    img.onload = () => res(true);
    img.onerror = () => res(false);
    img.src = src;
  });
}

async function preloadAssets() {
  const P = window.Preloader;
  const track = (promise) => {
    if (P) P.add(1);
    return Promise.resolve(promise).catch(() => {}).finally(() => { if (P) P.step(); });
  };
  const tasks = [];
  tasks.push(track(fetch(assetSrc('glyphs/glyphs.json')).then((r) => r.json()).then((j) => { glyphSizes = j; })));
  for (const code of SYMBOL_CODES) tasks.push(track(preloadImage(symbolSrc(code))));
  for (const f of ['blank', 'mini', 'minor', 'major', 'grand', 'collector', 'cell_locked', 'cell_empty']) {
    tasks.push(track(preloadImage(coinSrc(f))));
  }
  const portrait = isMobileLayout();
  for (const f of ['frame.webp', 'logo.webp', 'mascot.webp', 'jp_mini.webp', 'jp_minor.webp', 'jp_major.webp', 'jp_grand.webp',
    portrait ? 'bg_base_mob.jpg' : 'bg_base.jpg']) {
    tasks.push(track(preloadImage(assetSrc(`img/${f}`))));
  }
  // Попапы: какой арт вывесок уже нарезан — тот и используем.
  for (const key of [...Object.keys(POPUP_CONFIG), 'panel']) {
    tasks.push(track(probeImage(assetSrc(`popups/${key}.webp`)).then((ok) => { popupArt[key] = ok; })));
  }
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));
  // Spine-пак: без него игра остаётся на CSS (fx.js сам ловит отказ WebGL).
  if (window.NeonFx) tasks.push(track(NeonFx.load()));
  await Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
  // Глифы — после json, без них не знаем размеры.
  // decode() может не завершиться в скрытой вкладке — не ждём дольше 3с.
  if (glyphSizes) {
    await Promise.race([
      Promise.all(Object.keys(glyphSizes).map((ch) => preloadImage(glyphSrc(ch)).catch(() => {}))),
      wait(3000),
    ]);
  }
}

async function init() {
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  window.addEventListener('orientationchange', handleResize);
  buildReelGrid();
  setupDevPanel();
  await preloadAssets();
  readCellDims();
  if (window.updateJackpotPlates && window.__currentBet) updateJackpotPlates(window.__currentBet);
  document.dispatchEvent(new Event('njs:ready'));
  if (window.Preloader) window.Preloader.done();
  window.__slot = { cellInfos };
  showFeatureScreen();
}

window.slotReady = new Promise((resolve) => document.addEventListener('njs:ready', resolve, { once: true }));
init();
