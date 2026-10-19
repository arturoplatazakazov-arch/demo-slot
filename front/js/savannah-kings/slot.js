// Savannah Kings — presentation layer (GDD-03, game #3 of the Illuminator
// ladder). Reel/win/popup plumbing comes from the Provider 2 template
// (js/bison-thunder/slot.js, itself caesars-fortune's descendant) with the
// shared Gangsta Casino spin (js/reel-spin.js); everything else is this
// game's own: a fixed-size design stage, the lion that expands over its reel
// in free spins, the Jackpot Wheel, the two-card Buy Bonus window and the
// paytable with the wheel odds. No Spine: statics + CSS + js/savannah-kings/fx.js.
//
// app.js owns the session and the order of events; this file only draws.

// Art variants of the game (same GDD, same backend) point their page at
// their own art folder with window.SK_ASSET_ROOT.
const ASSET_ROOT = window.SK_ASSET_ROOT || 'img/savannah-kings';
const GAME_CODE = 'savannah-kings';
const ART_V = 3;

// Codes are the contract with app/seed/savannah_kings.py.
const SYMBOL_CODES = ['wild', 'scatter', 'paw', 'elephant', 'buffalo', 'leopard', 'zebra', 'a', 'k', 'q', 'j'];
// Feature symbols never blur past as loop filler.
const TRIGGER_CODES = new Set(['scatter', 'wild', 'paw']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild', 'paw']);
// Where each symbol may land (GDD §3.3) — the spin loop respects it too, so
// a lion never blurs past on reel 1.
const REEL_ONLY = { wild: [1, 2, 3], paw: [0, 2, 4] };

const GRID_ROWS = 3;
const GRID_COLS = 5;
// Design px; the whole stage is scaled as one (see fitStage).
const CELL = 176;

// GDD §4.1 (rows 0..2) — the same table as PAYLINES in the seed; a line
// win names its payline (1-based) and the whole line is drawn.
const PAYLINES = [
  [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
  [1, 0, 0, 0, 1], [1, 2, 2, 2, 1], [0, 0, 1, 2, 2], [2, 2, 1, 0, 0], [1, 0, 1, 2, 1],
  [1, 2, 1, 0, 1], [0, 1, 1, 1, 0], [2, 1, 1, 1, 2], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2],
  [1, 1, 0, 1, 1], [1, 1, 2, 1, 1], [0, 0, 2, 0, 0], [2, 2, 0, 2, 2], [0, 2, 0, 2, 0],
];

const TIERS = ['grand', 'major', 'minor', 'mini'];
const TIER_X = { mini: 20, minor: 50, major: 250, grand: 1000 };

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.webp?v=${ART_V}`;
}
function img(file) {
  return `${ASSET_ROOT}/img/${file}?v=${ART_V}`;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Opening screen: a calm, readable spread — three medallions, two letters
// per row, the lion in the middle.
const SYMBOL_LAYOUT = [
  ['elephant', 'k', 'leopard', 'q', 'zebra'],
  ['a', 'buffalo', 'wild', 'j', 'scatter'],
  ['paw', 'q', 'a', 'elephant', 'k'],
];

// --- Money ------------------------------------------------------------------
// The backend counts in coins of 0.01 (bet 20 = 0.20): show currency units.
let currencyCode = 'FUN';
function setCurrency(code) { currencyCode = code || 'FUN'; }
function money(n, { cur = false } = {}) {
  const v = (Number(n) || 0) / 100;
  const s = v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return cur ? `${s} ${currencyCode}` : s;
}

// --- Stage ------------------------------------------------------------------
//
// One design canvas per orientation, scaled to fit (contain); the background
// is full-bleed behind it. Everything inside is laid out in design px, so the
// reel spin's rowStep is simply CELL.
const STAGE = { land: [1920, 1080], port: [1080, 1920] };

function isPortrait() {
  return window.innerHeight > window.innerWidth * 1.05;
}

function fitStage() {
  const portrait = isPortrait();
  document.body.classList.toggle('is-portrait', portrait);
  const [w, h] = portrait ? STAGE.port : STAGE.land;
  // A bar that lives outside the stage (V1) is a device-size HUD in portrait:
  // the stage fits into what is left above it. Pages that keep the bar
  // inside the stage reserve nothing.
  const bar = document.getElementById('bar');
  const hud = portrait && bar && !bar.closest('.stage') ? bar.offsetHeight : 0;
  const availH = window.innerHeight - hud;
  const s = Math.min(window.innerWidth / w, availH / h);
  for (const stage of document.querySelectorAll('.stage')) {
    stage.style.width = `${w}px`;
    stage.style.height = `${h}px`;
    stage.style.top = hud ? `${availH / 2}px` : '';
    stage.style.transform = `translate(-50%, -50%) scale(${s})`;
  }
  document.documentElement.style.setProperty('--stage-scale', String(s));
  updateBg();
  if (window.SKFx) SKFx.resize();
}

function updateBg() {
  const mode = document.getElementById('screen').dataset.mode || 'base';
  const suffix = isPortrait() ? '_mob' : '';
  document.getElementById('bgBase').src = img(`bg_base${suffix}.jpg`);
  document.getElementById('bgBonus').src = img(`bg_bonus${suffix}.jpg`);
  document.getElementById('screen').dataset.mode = mode;
}

// --- Cells ------------------------------------------------------------------

let cellInfos = [];
let reelCols = [];
let expandedWilds = [];

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  const im = document.createElement('img');
  im.alt = code;
  im.draggable = false;
  im.src = symbolSrc(code);
  cell.appendChild(im);
  return cell;
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
      const code = SYMBOL_LAYOUT[row][col];
      const cell = createCellNode(code);
      stripEl.appendChild(cell);
      registerCell(cell, row, col, code);
    }
  }
}

function registerCell(cell, row, col, code) {
  const info = { symbol: code, cell, col, row, winToken: 0, winLoopTimeout: null };
  cell.onclick = () => onCellClick(info);
  cellInfos[row * GRID_COLS + col] = info;
  return info;
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  info.cell.querySelector('img').src = symbolSrc(code);
}

function applyGrid(grid) {
  teardownWins();
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let col = 0; col < GRID_COLS; col++) setCellSymbol(cellInfos[row * GRID_COLS + col], grid[row][col]);
  }
}

function clearCellAnimation(info) {
  info.winToken += 1;
  clearTimeout(info.winLoopTimeout);
  info.winLoopTimeout = null;
  info.cell.classList.remove('is-winning', 'is-win-active', 'is-trigger', 'is-dimmed');
}

// Designer preview: click a symbol to see its win, click the lion to see it
// stand up over its reel.
function onCellClick(info) {
  if (document.body.classList.contains('is-busy')) return;
  if (info.symbol === 'wild') { previewBigWild(info.col); return; }
  playWinOnce(info);
}

// --- Win presentation -------------------------------------------------------

const WIN_PULSE_MS = 900;
const WIN_LOOP_PAUSE_MS = 420;
const WIN_LINE_NS = 'http://www.w3.org/2000/svg';
let winLineSvg = null;
let winCycleToken = 0;
let winCycleTimeout = null;

function playWinOnce(info) {
  const { cell } = info;
  cell.classList.remove('is-winning');
  void cell.offsetWidth;
  cell.classList.add('is-winning');
  if (window.SKFx) SKFx.sparkAt(cell, info.symbol);
  return wait(WIN_PULSE_MS).then(() => cell.classList.remove('is-winning'));
}

function cellCentre(row, col) {
  const info = cellInfos[row * GRID_COLS + col];
  if (!info) return null;
  return { x: col * CELL + CELL / 2, y: row * CELL + CELL / 2 };
}

function showWinLine(win) {
  hideWinLine();
  const positions = (win && win.positions) || [];
  if (positions.length < 2) return;
  const gridEl = document.getElementById('reelGrid');
  const svg = document.createElementNS(WIN_LINE_NS, 'svg');
  svg.setAttribute('class', 'win-line');
  svg.setAttribute('viewBox', `0 0 ${GRID_COLS * CELL} ${GRID_ROWS * CELL}`);
  // The line runs across the WHOLE payline (all five reels) so the player
  // reads which line paid; the paying part is drawn brighter on top.
  const rows = PAYLINES[(win.payline || 0) - 1];
  const line = rows ? rows.map((row, col) => ({ row, col })) : positions;
  const pts = line.slice().sort((a, b) => a.col - b.col).map(({ row, col }) => cellCentre(row, col));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join(' ');
  for (const cls of ['win-line__shadow', 'win-line__glow', 'win-line__ribbon', 'win-line__core', 'win-line__spark']) {
    const path = document.createElementNS(WIN_LINE_NS, 'path');
    path.setAttribute('class', cls);
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  // A gem node on each paying cell, so the line reads as "these pay".
  for (const { row, col } of positions) {
    const c = cellCentre(row, col);
    const gem = document.createElementNS(WIN_LINE_NS, 'path');
    gem.setAttribute('class', 'win-line__gem');
    gem.setAttribute('d', `M${c.x} ${c.y - 11}L${c.x + 11} ${c.y}L${c.x} ${c.y + 11}L${c.x - 11} ${c.y}Z`);
    svg.appendChild(gem);
  }
  gridEl.appendChild(svg);
  winLineSvg = svg;
}

function hideWinLine() {
  if (winLineSvg) winLineSvg.remove();
  winLineSvg = null;
}

function teardownWins() {
  winCycleToken += 1;
  clearTimeout(winCycleTimeout);
  winCycleTimeout = null;
  hideWinLine();
  for (const info of cellInfos) if (info) clearCellAnimation(info);
  for (const entry of expandedWilds) entry.el.remove();
  expandedWilds = [];
  document.getElementById('reelGrid').classList.remove('has-win');
}

// Every winning line in turn, with its line drawn, then all of them together,
// looping until the next spin. A lone win just pulses.
function playWins(winningCells, lineWins, countWins) {
  teardownWinCycle();
  const all = (winningCells || []).map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean);
  if (!all.length) return;
  const gridEl = document.getElementById('reelGrid');
  gridEl.classList.add('has-win');
  const winSet = new Set(all);
  for (const info of cellInfos) info.cell.classList.toggle('is-dimmed', !winSet.has(info));
  const groups = [
    ...(lineWins || []).map((w) => ({ win: w, cells: (w.positions || []).map(({ row, col }) => cellInfos[row * GRID_COLS + col]) })),
    ...(countWins || []).map((w) => ({ win: null, cells: (w.positions || []).map(({ row, col }) => cellInfos[row * GRID_COLS + col]) })),
  ];
  const token = ++winCycleToken;
  const phases = groups.length > 1 ? [{ win: null, cells: all }, ...groups] : groups;
  let i = 0;
  const step = () => {
    if (token !== winCycleToken) return;
    const phase = phases[i % phases.length];
    i += 1;
    const active = new Set(phase.cells);
    for (const info of all) info.cell.classList.toggle('is-win-active', active.has(info));
    if (phase.win) showWinLine(phase.win); else hideWinLine();
    Promise.all(phase.cells.filter(Boolean).map(playWinOnce)).then(() => {
      if (token !== winCycleToken) return;
      winCycleTimeout = setTimeout(step, WIN_LOOP_PAUSE_MS);
    });
  };
  step();
}

function teardownWinCycle() {
  winCycleToken += 1;
  clearTimeout(winCycleTimeout);
  hideWinLine();
}

// Feature symbols that triggered something flash on their own (they don't
// pay a line): the masks of a free-spins trigger, the paws of the wheel.
async function flashTriggers(code) {
  const infos = cellInfos.filter((i) => i && i.symbol === code);
  if (!infos.length) return;
  for (const info of cellInfos) info.cell.classList.toggle('is-dimmed', !infos.includes(info));
  Sound.playSfx(code === 'paw' ? 'pawTrigger' : 'scatterWin');
  for (const info of infos) {
    info.cell.classList.add('is-trigger');
    if (window.SKFx) SKFx.burstAt(info.cell, code === 'paw' ? 'gold' : 'sun');
  }
  await wait(1500);
  for (const info of cellInfos) info.cell.classList.remove('is-dimmed', 'is-trigger');
}

const INLINE_WIN_HOLD_MS = 2000;
let inlineWinTimeout = null;
function showInlineWinAmount(amount) {
  const el = document.getElementById('reelWinAmount');
  // Optional plate under the amount (pages that have one, e.g. V1).
  const plate = document.getElementById('reelWinPlate');
  clearTimeout(inlineWinTimeout);
  el.textContent = money(amount);
  for (const node of [el, plate].filter(Boolean)) {
    node.classList.remove('is-visible');
    void node.offsetWidth;
    node.classList.add('is-visible');
  }
  inlineWinTimeout = setTimeout(() => {
    el.classList.remove('is-visible');
    if (plate) plate.classList.remove('is-visible');
  }, INLINE_WIN_HOLD_MS);
}

// --- Reel motion ------------------------------------------------------------

let reelSpin = null;
let fillerCol = 0;

function fillerFor(col) {
  return () => {
    const pool = SYMBOL_CODES.filter((c) => c !== 'scatter' && (!REEL_ONLY[c] || REEL_ONLY[c].includes(col)) && c !== 'wild' && c !== 'paw');
    return pool[Math.floor(Math.random() * pool.length)];
  };
}

function getReelSpin() {
  if (!reelSpin) {
    reelSpin = ReelSpin.create({
      cols: () => reelCols,
      rows: GRID_ROWS,
      rowStep: () => CELL,
      makeCell: (code) => createCellNode(code),
      loopFiller: () => FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)],
      codes: SYMBOL_CODES,
      onReelStop: (col, isLast) => {
        Sound.playSfx(isLast ? 'finalReelStop' : 'reelStop');
        reelCols[col].colEl.classList.remove('is-anticipating');
      },
    });
  }
  return reelSpin;
}

function startReelLoop() {
  Sound.playSfx('spinStart');
  teardownWins();
  getReelSpin().startLoop();
}

function stopReelLoop() {
  getReelSpin().stopLoop();
}

// Reels where suspense is real: once two masks are in, every later reel that
// could still bring the third; once paws sit on reels 1 and 3, reel 5.
function anticipationColumns(grid) {
  const cols = new Set();
  let masks = 0;
  for (let col = 0; col < GRID_COLS; col++) {
    if (masks >= 2 && masks < 3) cols.add(col);
    if ([0, 1, 2].some((r) => grid[r][col] === 'scatter')) masks += 1;
  }
  const paw = (col) => [0, 1, 2].some((r) => grid[r][col] === 'paw');
  if (paw(0) && paw(2)) cols.add(4);
  return [...cols].sort((a, b) => a - b);
}

async function landReels(grid, { wildEvents = [], turbo = false } = {}) {
  teardownWins();
  const antic = anticipationColumns(grid);
  const firstAntic = antic.length ? antic[0] : GRID_COLS;
  const expandCols = new Set(wildEvents.filter((e) => e.event === 'expanded').map((e) => e.reel));
  const stagger = turbo ? 0 : ReelSpin.PHYS.STAGGER_FIGURES;

  const settle = (col, cells) => {
    for (let row = 0; row < GRID_ROWS; row++) registerCell(cells[row], row, col, grid[row][col]);
    const special = cells.filter((c) => c.dataset.symbol === 'scatter' || c.dataset.symbol === 'paw');
    for (const c of special) {
      c.classList.add('is-landed');
      Sound.playSfx(c.dataset.symbol === 'paw' ? 'pawLand' : 'scatterLand');
    }
  };

  const lead = [];
  for (let col = 0; col < firstAntic; col++) {
    const codes = [grid[0][col], grid[1][col], grid[2][col]];
    lead.push(getReelSpin().landReel(col, codes, { extra: col * stagger, filler: fillerFor(col) })
      .then((cells) => settle(col, cells)));
  }
  await Promise.all(lead);
  if (firstAntic < GRID_COLS) {
    Sound.playSfx('anticipation');
    for (let col = firstAntic; col < GRID_COLS; col++) {
      const codes = [grid[0][col], grid[1][col], grid[2][col]];
      const anticipating = antic.includes(col);
      if (anticipating) reelCols[col].colEl.classList.add('is-anticipating');
      const cells = await getReelSpin().landReel(col, codes, { extra: stagger, anticipating, filler: fillerFor(col) });
      settle(col, cells);
    }
  }
  // GDD §5.2.3: the lions expand once the reels are down, before the win.
  if (expandCols.size) {
    await wait(150);
    await Promise.all([...expandCols].map((col, i) => wait(i * 160).then(() => expandWild(col))));
    await wait(350);
  }
}

// --- Expanding Wild (free spins) -------------------------------------------
//
// The lion "stands up": a full-height lion rises out of its cell over the
// whole reel inside a gold frame, the reel's own symbols sink under it — but
// a mask or a paw it covers stays on top (it still counts, GDD §5.2.4).
async function expandWild(col) {
  const { colEl } = reelCols[col];
  const el = document.createElement('div');
  el.className = 'big-wild';
  const fromRow = Math.max(0, [0, 1, 2].find((r) => cellInfos[r * GRID_COLS + col]?.symbol === 'wild') ?? 1);
  el.style.setProperty('--from-row', String(fromRow));
  el.innerHTML = `
    <div class="big-wild__light"></div>
    <img class="big-wild__lion" src="${img('wild_big.webp')}" alt="">
    <div class="big-wild__frame"></div>
    <div class="big-wild__label">WILD</div>`;
  colEl.appendChild(el);
  expandedWilds.push({ el, col });
  for (let row = 0; row < GRID_ROWS; row++) {
    const info = cellInfos[row * GRID_COLS + col];
    if (!info) continue;
    if (info.symbol === 'scatter' || info.symbol === 'paw') info.cell.classList.add('is-over-wild');
    else info.cell.classList.add('is-under-wild');
  }
  Sound.playSfx('wildGrow');
  void el.offsetWidth;
  el.classList.add('is-grown');
  if (window.SKFx) SKFx.burstAt(el, 'gold');
  await wait(760);
  Sound.playSfx('roar');
  el.classList.add('is-roar');
}

async function previewBigWild(col) {
  if (expandedWilds.length || col < 1 || col > 3) return;
  await expandWild(col);
  await wait(2600);
  teardownWins();
  for (const info of cellInfos) info.cell.classList.remove('is-under-wild', 'is-over-wild');
}

// --- Screen dim / modes -----------------------------------------------------

let dimCount = 0;
function pushDim(opaque = false) {
  dimCount += 1;
  const el = document.getElementById('screenDim');
  el.classList.add('is-active');
  if (opaque) el.classList.add('is-opaque');
}
function popDim(opaque = false) {
  dimCount = Math.max(0, dimCount - 1);
  const el = document.getElementById('screenDim');
  if (!dimCount) el.classList.remove('is-active');
  if (opaque) el.classList.remove('is-opaque');
}
const DIM_MS = 340;

// Day <-> night: the backgrounds cross-fade under a short blackout; the
// logo makes room for the free-spins panel.
function applyMode(mode) {
  const screen = document.getElementById('screen');
  screen.dataset.mode = mode;
  if (window.SKFx) SKFx.setMode(mode);
}

async function enterFreeSpins(spins) {
  Sound.playMusic('bonus');
  pushDim(true);
  await wait(DIM_MS);
  await playPopup('freeSpinsIntro', spins, 2600, { ownDim: false });
  applyMode('freespins');
  setFsPanel(spins, 0);
  await wait(DIM_MS);
  popDim(true);
}

async function leaveFreeSpins(total) {
  await playPopup('freeSpinsTotal', total, 3000);
  Sound.playMusic('base');
  pushDim(true);
  await wait(DIM_MS);
  applyMode('base');
  await wait(DIM_MS);
  popDim(true);
}

function setFsPanel(remaining, total) {
  document.getElementById('fsLeft').textContent = String(remaining);
  document.getElementById('fsWin').textContent = money(total);
}

function bumpFsPanel() {
  const el = document.getElementById('fsPanel');
  el.classList.remove('is-bump');
  void el.offsetWidth;
  el.classList.add('is-bump');
}

// --- Jackpot plaques --------------------------------------------------------

function renderJackpots(bet) {
  for (const tier of TIERS) {
    for (const el of document.querySelectorAll(`[data-jp-value="${tier}"]`)) {
      const text = money(TIER_X[tier] * bet);
      el.textContent = text;
      // The value panel is a fixed slot in the art: long amounts shrink.
      el.style.fontSize = text.length > 8 ? `${(8 / text.length).toFixed(3)}em` : '';
    }
  }
}

// --- Popups -----------------------------------------------------------------
//
// Title wordmark (carved gold, from the art) over a stone-and-gold panel with
// a live number that counts up. Money popups rain coins over the dim.
const POPUP_CONFIG = {
  bigWin: { title: 'title_big.webp', kind: 'money', tier: 'big', count: 2600 },
  megaWin: { title: 'title_mega.webp', kind: 'money', tier: 'mega', count: 3400 },
  epicWin: { title: 'title_epic.webp', kind: 'money', tier: 'epic', count: 4200 },
  freeSpinsIntro: { title: 'title_freespins.webp', kind: 'count', sub: 'FREE SPINS AWARDED' },
  freeSpinsMore: { title: 'title_freespins.webp', kind: 'count', sub: 'EXTRA FREE SPINS', plus: true },
  freeSpinsTotal: { title: 'title_totalwin.webp', kind: 'money', tier: 'total', count: 2400 },
};

function countUp(el, to, ms, fmt) {
  const start = performance.now();
  return new Promise((resolve) => {
    const tick = (now) => {
      const t = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - t, 3);
      el.textContent = fmt(to * e);
      if (t < 1 && document.visibilityState === 'visible') requestAnimationFrame(tick);
      else { el.textContent = fmt(to); resolve(); }
    };
    requestAnimationFrame(tick);
  });
}

function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key];
  const root = document.createElement('div');
  root.className = `sk-popup is-${key}`;
  if (cfg.tier) root.classList.add(`is-tier-${cfg.tier}`);
  root.innerHTML = `
    <div class="sk-popup__rays"></div>
    <img class="sk-popup__title" src="${img(cfg.title)}" alt="">
    <div class="sk-popup__panel">
      <img src="${img('panel.webp')}" alt="">
      <div class="sk-popup__value"></div>
    </div>
    ${cfg.sub ? `<div class="sk-popup__sub">${cfg.sub}</div>` : ''}`;
  const value = root.querySelector('.sk-popup__value');
  if (cfg.kind === 'count') value.textContent = `${cfg.plus ? '+' : ''}${Math.round(amount)}`;
  else value.textContent = money(0);
  return root;
}

function playPopup(key, amount = 0, holdMs = 2500, { ownDim = true } = {}) {
  const cfg = POPUP_CONFIG[key];
  if (!cfg) return Promise.resolve();
  return new Promise((resolve) => {
    let node = null;
    let done = false;
    let skip = null;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safety);
      if (node) node.remove();
      if (window.SKFx) SKFx.stopShower();
      if (ownDim) popDim();
      resolve();
    };
    const safety = setTimeout(finish, holdMs + (cfg.count || 0) + 6000);
    (async () => {
      Sound.playSfx(cfg.kind === 'money' ? (cfg.tier === 'total' ? 'bonusTotalWin' : `${cfg.tier}Win`) : 'popupOpen');
      if (ownDim) { pushDim(); await wait(DIM_MS); }
      node = buildPopupNode(key, amount);
      document.getElementById('overlays').appendChild(node);
      void node.offsetWidth;
      node.classList.add('is-in');
      let skipped = false;
      const skipWait = new Promise((r) => { skip = () => { skipped = true; r(); }; });
      node.addEventListener('click', () => skip && skip());
      if (cfg.kind === 'money') {
        if (window.SKFx) SKFx.startShower(cfg.tier);
        const value = node.querySelector('.sk-popup__value');
        await Promise.race([countUp(value, amount, cfg.count, (v) => money(Math.round(v))), skipWait]);
        value.textContent = money(amount);
        node.classList.add('is-landed');
      }
      await Promise.race([wait(skipped ? 700 : holdMs), skipWait.then(() => wait(200))]);
      node.classList.remove('is-in');
      node.classList.add('is-out');
      Sound.playSfx('popupClose');
      await wait(300);
      finish();
    })().catch((err) => { console.error('popup failed', err); finish(); });
  });
}

// --- Jackpot Wheel ----------------------------------------------------------
//
// 12 sectors drawn here as SVG (tier colours of the line-up: bronze Mini,
// silver Minor, gold Major, ruby Grand) under the gold rim from the art.
// The server already decided the segment (GDD §6.2) — the wheel only lands
// on it. Sector i is centred at i*30° clockwise from 12 o'clock, under the
// pointer.
const SECTOR_STYLE = {
  mini: { a: '#b8723a', b: '#6e3a18', text: '#ffe2b8', label: 'MINI' },
  minor: { a: '#b7c6d4', b: '#566b80', text: '#f4fbff', label: 'MINOR' },
  major: { a: '#ffd75a', b: '#c98a00', text: '#5a2b00', label: 'MAJOR' },
  grand: { a: '#d42a3c', b: '#6b0a1a', text: '#ffe7a6', label: 'GRAND' },
};

function wheelSvg(segments) {
  const n = segments.length;
  const R = 300;
  const parts = [`<svg viewBox="-${R} -${R} ${2 * R} ${2 * R}" class="wheel__svg">`, '<defs>'];
  for (const [tier, s] of Object.entries(SECTOR_STYLE)) {
    parts.push(`<radialGradient id="wg-${tier}" cx="0" cy="0" r="${R}" gradientUnits="userSpaceOnUse">
      <stop offset="0.18" stop-color="${s.b}"/><stop offset="0.7" stop-color="${s.a}"/><stop offset="1" stop-color="${s.b}"/></radialGradient>`);
  }
  parts.push('</defs>');
  const step = 360 / n;
  segments.forEach((seg, i) => {
    const tier = seg.tier || 'mini';
    const a0 = ((i * step - step / 2 - 90) * Math.PI) / 180;
    const a1 = ((i * step + step / 2 - 90) * Math.PI) / 180;
    const p = (a, r) => `${(Math.cos(a) * r).toFixed(2)} ${(Math.sin(a) * r).toFixed(2)}`;
    parts.push(`<path d="M0 0 L${p(a0, R)} A${R} ${R} 0 0 1 ${p(a1, R)} Z" fill="url(#wg-${tier})" stroke="#2a1405" stroke-width="3"/>`);
    // Label runs along the sector's axis, always readable: on the left
    // half of the drum it would read bottom-to-top upside down, so it
    // turns the other way there.
    const a = i * step;
    const turn = a > 0 && a < 180 ? -90 : 90;
    parts.push(`<g transform="rotate(${a})"><text x="0" y="${-R * 0.62}" class="wheel__label wheel__label--${tier}"
      text-anchor="middle" dominant-baseline="middle" transform="rotate(${a === 0 ? -90 : turn} 0 ${-R * 0.62})">${SECTOR_STYLE[tier].label}</text></g>`);
  });
  // Gold studs on the spokes.
  segments.forEach((_, i) => {
    const a = ((i * step + step / 2 - 90) * Math.PI) / 180;
    parts.push(`<circle cx="${(Math.cos(a) * R * 0.94).toFixed(1)}" cy="${(Math.sin(a) * R * 0.94).toFixed(1)}" r="7" fill="#ffd75a" stroke="#5a2b00" stroke-width="2"/>`);
  });
  parts.push('</svg>');
  return parts.join('');
}

let wheelSegments = null;
let wheelAngle = 0;

// The rim's 12 bulbs (measured on wheel_rim: radius 0.86, every 30° from
// 12 o'clock) get a live glow each: a slow twinkle at rest, a chase while
// the wheel turns, all of them flashing on the stop.
const RIM_BULB_R = 0.86;

function buildWheel(segments) {
  wheelSegments = segments;
  document.getElementById('wheelDisc').innerHTML = wheelSvg(segments);
  const lights = document.getElementById('wheelLights');
  if (lights && !lights.children.length) {
    for (let i = 0; i < 12; i++) {
      const b = document.createElement('i');
      const a = (i * 30 * Math.PI) / 180;
      b.style.left = `${50 + Math.sin(a) * RIM_BULB_R * 50}%`;
      b.style.top = `${50 - Math.cos(a) * RIM_BULB_R * 50}%`;
      b.style.setProperty('--i', String(i));
      lights.appendChild(b);
    }
  }
}

// Plays the whole wheel moment and resolves when the award has been shown.
// `result` = response.wheel_of_fortune. `auto`: autoplay spins it after 3s.
async function playJackpotWheel(result, bet, { auto = false, bought = false } = {}) {
  if (!wheelSegments) buildWheel(result.segments);
  const overlay = document.getElementById('wheelOverlay');
  const button = document.getElementById('wheelSpinBtn');
  const tier = result.tier || result.segments[result.segment_index].tier;
  renderJackpots(bet);
  for (const el of overlay.querySelectorAll('.jp')) el.classList.remove('is-won');
  overlay.classList.toggle('is-bought', bought);
  overlay.hidden = false;
  Sound.playMusic('wheel');
  void overlay.offsetWidth;
  overlay.classList.add('is-in');
  Sound.playSfx('wheelIn');
  await wait(900);

  // SPIN THE WHEEL — or 3 s later on its own in autoplay (GDD §6.2).
  button.disabled = false;
  button.classList.add('is-ready');
  await new Promise((resolve) => {
    let t = null;
    const go = () => { clearTimeout(t); button.removeEventListener('click', go); resolve(); };
    button.addEventListener('click', go);
    if (auto) t = setTimeout(go, 3000);
  });
  button.disabled = true;
  button.classList.remove('is-ready');
  Sound.playSfx('click');

  // Land on the server's segment: whole turns + its angle + a little offset
  // inside the sector, so it never stops dead centre every time.
  const n = result.segments.length;
  const step = 360 / n;
  const jitter = (Math.random() - 0.5) * step * 0.6;
  const target = -(result.segment_index * step) + jitter;
  const base = Math.ceil(wheelAngle / 360) * 360;
  const finalAngle = base + 360 * 5 + (((target % 360) + 360) % 360);
  const disc = document.getElementById('wheelDisc');
  const SPIN_MS = 3800;
  disc.style.transition = `transform ${SPIN_MS}ms cubic-bezier(0.12, 0.6, 0.12, 1)`;
  disc.style.transform = `rotate(${finalAngle}deg)`;
  overlay.classList.add('is-spinning');
  tickWheel(disc, step, SPIN_MS);
  await wait(SPIN_MS + 120);
  wheelAngle = finalAngle;
  overlay.classList.remove('is-spinning');
  overlay.classList.add('is-stopped');
  Sound.playSfx('wheelStop');
  const plaque = overlay.querySelector(`.jp--${tier}`);
  if (plaque) plaque.classList.add('is-won');
  if (window.SKFx) SKFx.burstAt(document.getElementById('wheelPointer'), 'gold');
  await wait(900);

  // Award screen.
  const award = document.getElementById('wheelAward');
  award.dataset.tier = tier;
  award.querySelector('.wheel-award__tier').textContent = SECTOR_STYLE[tier].label;
  const value = award.querySelector('.wheel-award__value');
  value.textContent = money(0);
  award.hidden = false;
  overlay.classList.add('has-award');
  void award.offsetWidth;
  award.classList.add('is-in');
  Sound.playSfx(tier === 'grand' || tier === 'major' ? 'epicWin' : 'bigWin');
  if (window.SKFx) SKFx.startShower(tier === 'grand' ? 'epic' : tier === 'major' ? 'mega' : 'big');
  await countUp(value, result.win_amount, tier === 'grand' ? 4200 : tier === 'major' ? 3200 : 2200, (v) => money(Math.round(v)));
  await wait(auto ? 2200 : 2600);
  if (window.SKFx) SKFx.stopShower();
  award.classList.remove('is-in');
  overlay.classList.remove('is-in', 'is-stopped', 'has-award');
  await wait(450);
  award.hidden = true;
  overlay.hidden = true;
  Sound.playMusic(document.getElementById('screen').dataset.mode === 'freespins' ? 'bonus' : 'base');
}

// Ratchet clicks as the studs pass the pointer, read off the live transform.
function tickWheel(disc, step, ms) {
  const start = performance.now();
  let last = null;
  const tick = (now) => {
    const m = new DOMMatrixReadOnly(getComputedStyle(disc).transform);
    const ang = (Math.atan2(m.b, m.a) * 180) / Math.PI;
    const idx = Math.floor((ang + 360 + step / 2) / step);
    if (last !== null && idx !== last) {
      Sound.playSfx('wheelTick');
      document.getElementById('wheelPointer').classList.remove('is-tick');
      void document.getElementById('wheelPointer').offsetWidth;
      document.getElementById('wheelPointer').classList.add('is-tick');
    }
    last = idx;
    if (now - start < ms + 100) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// --- Buy Bonus window -------------------------------------------------------
//
// Two cards (GDD §6.4): Free Spins — night savannah; Jackpot Chance — the
// wheel. Pick one -> confirm -> the purchase. Resolves with the product's
// buy_id, or null.
function showBuyWindow(products) {
  const overlay = document.getElementById('buyOverlay');
  const cards = overlay.querySelector('.buy__cards');
  const confirm = overlay.querySelector('.buy__confirm');
  cards.innerHTML = '';
  for (const p of products) {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = `buy-card buy-card--${p.kind}`;
    card.disabled = !p.affordable;
    card.innerHTML = `
      <img class="buy-card__art" src="${img(p.kind === 'fs' ? 'card_fs.webp' : 'card_wheel.webp')}" alt="">
      <span class="buy-card__name">${p.name}</span>
      <span class="buy-card__desc">${p.desc}</span>
      <span class="buy-card__price">${p.affordable ? money(p.cost, { cur: true }) : 'NOT ENOUGH BALANCE'}</span>
      ${p.note ? `<span class="buy-card__note">${p.note}</span>` : ''}`;
    card.dataset.buyId = p.buyId;
    cards.appendChild(card);
  }
  overlay.classList.remove('is-confirm');
  overlay.hidden = false;
  document.body.classList.add('is-buying');
  pushDim();
  void overlay.offsetWidth;
  overlay.classList.add('is-in');
  Sound.playSfx('popupOpen');

  return new Promise((resolve) => {
    let chosen = null;
    const close = (answer) => {
      overlay.classList.remove('is-in');
      document.removeEventListener('keydown', onKey);
      overlay.onclick = null;
      Sound.playSfx('popupClose');
      setTimeout(() => { overlay.hidden = true; }, 300);
      document.body.classList.remove('is-buying');
      popDim();
      resolve(answer);
    };
    const onKey = (e) => { if (e.key === 'Escape') close(null); };
    document.addEventListener('keydown', onKey);
    overlay.onclick = (e) => {
      const card = e.target.closest('.buy-card');
      if (card && !card.disabled && !chosen) {
        Sound.playSfx('click');
        chosen = products.find((p) => p.buyId === card.dataset.buyId);
        confirm.querySelector('.buy__q').innerHTML =
          `Buy <b>${chosen.name}</b> for <b>${money(chosen.cost, { cur: true })}</b>?` +
          (chosen.mult ? `<small>${chosen.mult}× your bet · a separate round</small>` : '');
        for (const c of cards.children) c.classList.toggle('is-chosen', c === card);
        overlay.classList.add('is-confirm');
        return;
      }
      if (e.target.closest('[data-buy="yes"]')) { Sound.playSfx('click'); close(chosen.buyId); return; }
      if (e.target.closest('[data-buy="no"]')) {
        Sound.playSfx('click');
        chosen = null;
        overlay.classList.remove('is-confirm');
        for (const c of cards.children) c.classList.remove('is-chosen');
        return;
      }
      if (e.target.closest('[data-buy="close"]') || e.target === overlay) close(null);
    };
  });
}

// --- Boot -------------------------------------------------------------------

const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const im = new Image();
  im.src = src;
  return im.decode ? im.decode().catch(() => {}) : Promise.resolve();
}

function preloadAssets() {
  const P = window.Preloader;
  const track = (p) => {
    if (P) P.add(1);
    return Promise.resolve(p).catch(() => {}).finally(() => { if (P) P.step(); });
  };
  const tasks = [];
  for (const code of SYMBOL_CODES) {
    tasks.push(track(preloadImage(symbolSrc(code))));
    tasks.push(track(preloadImage(symbolSrc(code).replace('.webp', '_blur.webp'))));
  }
  for (const f of [
    'reel_frame.webp', 'logo.webp', 'wild_big.webp', 'panel.webp', 'mascot.webp',
    'jp_grand.webp', 'jp_major.webp', 'jp_minor.webp', 'jp_mini.webp',
    'wheel_rim.webp', 'wheel_hub.webp', 'wheel_pointer.webp',
    'title_big.webp', 'title_mega.webp', 'title_epic.webp', 'title_freespins.webp', 'title_totalwin.webp',
    'title_jackpot.webp', 'title_buybonus.webp', 'card_fs.webp', 'card_wheel.webp',
  ]) tasks.push(track(preloadImage(img(f))));
  const suffix = isPortrait() ? '_mob' : '';
  tasks.push(track(preloadImage(img(`bg_base${suffix}.jpg`))));
  tasks.push(track(preloadImage(img(`bg_bonus${suffix}.jpg`))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));
  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function initSlot() {
  fitStage();
  window.addEventListener('resize', fitStage);
  buildReelGrid();
  if (window.SKFx) SKFx.init();
  await preloadAssets();
  window.addEventListener('load', () => getReelSpin());
  getReelSpin();
  if (window.Preloader) window.Preloader.done();
  Sound.playMusic('base');
}

window.SK = {
  CELL, PAYLINES, GRID_ROWS, GRID_COLS, TIERS, TIER_X, money, setCurrency, symbolSrc, img,
  startReelLoop, stopReelLoop, landReels, applyGrid, playWins, teardownWins, flashTriggers,
  showInlineWinAmount, enterFreeSpins, leaveFreeSpins, setFsPanel, bumpFsPanel, playPopup,
  renderJackpots, buildWheel, playJackpotWheel, showBuyWindow, pushDim, popDim, wait,
  get dimCount() { return dimCount; },
};

initSlot();
