// Sugar Blast — presentation layer (GDD-05, game #5 of the Illuminator
// ladder). Forked from js/savannah-kings/slot.js (GDD-03: 5x3, 20 lines, the
// Jackpot Wheel, the design stage, popups, win lines) — the lion's
// expansion is gone; new here: candy bombs with their x-values (digit art),
// bombs flying into the spin / round multiplier, the TOTAL MULTIPLIER plaque
// of the free spins, three Buy Bonus cards, the chef mascot and the free-spins
// summary screen. Four art variants share this file (window.SB_ASSET_ROOT).
//
// app.js owns the session and the order of events; this file only draws.

// Art variants of the game (same GDD, same backend) point their page at
// their own art folder with window.SB_ASSET_ROOT.
const ASSET_ROOT = window.SB_ASSET_ROOT || 'img/sugar-blast-forest';
const GAME_CODE = 'sugar-blast';
const ART_V = window.SB_ART_V || 1;

// Codes are the contract with app/seed/sugar_blast.py (by ROLE: the variants
// draw different sweets for h1..h4 / l1..l4, colour and tier stay fixed).
const SYMBOL_CODES = ['wild', 'scatter', 'bomb', 'wrapper', 'h1', 'h2', 'h3', 'h4', 'l1', 'l2', 'l3', 'l4'];
// Feature symbols never blur past as loop filler.
const TRIGGER_CODES = new Set(['scatter', 'wild', 'wrapper', 'bomb']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild', 'wrapper', 'bomb']);
// Where each symbol may land (GDD §3.3) — the spin loop respects it too.
const REEL_ONLY = { wild: [1, 2, 3], wrapper: [0, 2, 4] };

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

// Opening screen: a calm, readable spread with every special once.
const SYMBOL_LAYOUT = [
  ['h1', 'l2', 'h3', 'l3', 'h4'],
  ['l1', 'h2', 'wild', 'l4', 'bomb'],
  ['wrapper', 'l3', 'l1', 'h1', 'scatter'],
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
  let [w, h] = portrait ? STAGE.port : STAGE.land;
  // A bar that lives outside the stage (V1) is a device-size HUD in portrait:
  // the stage fits into what is left above it. Pages that keep the bar
  // inside the stage reserve nothing.
  // The standard bar (ui-bar-v3) is a fixed device-px HUD under the stage:
  // the stage fits into what is left above its button row.
  const hud = document.getElementById('v3Bar')
    ? (window.innerWidth < 560 ? Math.min(260, window.innerHeight * 0.24) : (window.innerHeight <= 560 ? 104 : 124))
    : 0;
  const availH = window.innerHeight - hud;
  // Landscape: the stage is as wide as the window's aspect allows (min 1920,
  // max 2560) — on wide desktops the side strips hold the jackpots and the
  // chef instead of empty letterbox margins. layouts.js reads the width.
  if (!portrait) w = Math.round(Math.min(2560, Math.max(1920, h * window.innerWidth / availH)));
  // Portrait: as tall as the phone's free height allows (1300..2400), so the
  // stage is always width-bound and 1080 stage px = the screen width.
  else h = Math.round(Math.min(2400, Math.max(1300, w * availH / window.innerWidth)));
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

// Designer preview: click a symbol to see its win.
function onCellClick(info) {
  if (document.body.classList.contains('is-busy')) return;
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

// Win-line look: 'classic' (the original polyline with diamond gems) unless
// the page sets window.SB_WIN_LINE — the five art variants default to 'a'
// (silk glow). The DEMO panel can switch to 'b' (coin beads), 'c' (flow
// ribbon) or back (kept in localStorage); ?line= overrides both.
function winLineStyle() {
  let saved = null;
  try { saved = localStorage.getItem('sugarblast.winline'); } catch (e) { /* ignore */ }
  return new URLSearchParams(location.search).get('line') || saved || window.SK_WIN_LINE || 'classic';
}

function svgEl(tag, attrs) {
  const el = document.createElementNS(WIN_LINE_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

// Catmull-Rom through the cell centres, run on past both ends of the window
// so the line enters and leaves the reels instead of stopping mid-cell.
function smoothLinePath(pts) {
  const p = [{ x: pts[0].x - CELL * 0.55, y: pts[0].y }, ...pts, { x: pts[pts.length - 1].x + CELL * 0.55, y: pts[pts.length - 1].y }];
  let d = `M${p[0].x} ${p[0].y}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] || p[i], p1 = p[i], p2 = p[i + 1], p3 = p[i + 2] || p2;
    const t = 0.5 / 3;
    d += ` C${p1.x + (p2.x - p0.x) * t} ${p1.y + (p2.y - p0.y) * t} ${p2.x - (p3.x - p1.x) * t} ${p2.y - (p3.y - p1.y) * t} ${p2.x} ${p2.y}`;
  }
  return d;
}

function showWinLine(win) {
  hideWinLine();
  const positions = (win && win.positions) || [];
  if (positions.length < 2) return;
  const gridEl = document.getElementById('reelGrid');
  const style = winLineStyle();
  const svg = svgEl('svg', { class: `win-line win-line--${style}`, viewBox: `0 0 ${GRID_COLS * CELL} ${GRID_ROWS * CELL}` });
  // The line runs across the WHOLE payline (all five reels) so the player
  // reads which line paid; the paying cells are marked on top.
  const rows = PAYLINES[(win.payline || 0) - 1];
  const line = rows ? rows.map((row, col) => ({ row, col })) : positions;
  const pts = line.slice().sort((a, b) => a.col - b.col).map(({ row, col }) => cellCentre(row, col));
  if (style === 'classic') {
    const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join(' ');
    for (const cls of ['win-line__shadow', 'win-line__glow', 'win-line__ribbon', 'win-line__core', 'win-line__spark']) {
      svg.appendChild(svgEl('path', { class: cls, d }));
    }
    // A gem node on each paying cell, so the line reads as "these pay".
    for (const { row, col } of positions) {
      const c = cellCentre(row, col);
      svg.appendChild(svgEl('path', { class: 'win-line__gem', d: `M${c.x} ${c.y - 11}L${c.x + 11} ${c.y}L${c.x} ${c.y + 11}L${c.x - 11} ${c.y}Z` }));
    }
  } else {
    const d = smoothLinePath(pts);
    const uid = `wl${Date.now() % 1e6}`;
    const layers = {
      a: ['wl-a-glow', 'wl-a-body', 'wl-a-core', 'wl-a-pulse', 'wl-a-pulse wl-a-pulse--2'],
      b: ['wl-b-shadow', 'wl-b-bead', 'wl-b-shine'],
      c: ['wl-c-edge', 'wl-c-bed', 'wl-c-flow', 'wl-c-glint'],
    }[style] || [];
    const group = svgEl('g');
    if (style === 'b') {
      // Beads appear left to right under a mask that draws itself on.
      const mask = svgEl('mask', { id: `${uid}m`, maskUnits: 'userSpaceOnUse', x: -400, y: -400, width: GRID_COLS * CELL + 800, height: GRID_ROWS * CELL + 800 });
      mask.appendChild(svgEl('path', { class: 'wl-b-reveal', d, pathLength: 1 }));
      svg.appendChild(mask);
      group.setAttribute('mask', `url(#${uid}m)`);
    }
    // Silk measures its draw-on and pulses in path fractions (pathLength 1).
    for (const cls of layers) group.appendChild(svgEl('path', style === 'a' ? { class: cls, d, pathLength: 1 } : { class: cls, d }));
    svg.appendChild(group);
    positions.forEach(({ row, col }, i) => {
      const c = cellCentre(row, col);
      const delay = `${0.12 + i * 0.09}s`;
      if (style === 'a') {
        svg.appendChild(svgEl('circle', { class: 'wl-a-ring', cx: c.x, cy: c.y, r: CELL * 0.44, style: `animation-delay:${delay}` }));
      } else if (style === 'b') {
        svg.appendChild(svgEl('circle', { class: 'wl-b-orb-glow', cx: c.x, cy: c.y, r: 40, style: `animation-delay:${delay}` }));
        svg.appendChild(svgEl('circle', { class: 'wl-b-orb', cx: c.x, cy: c.y, r: 22, style: `animation-delay:${delay}` }));
      } else if (style === 'c') {
        const h = CELL * 0.46;
        svg.appendChild(svgEl('rect', { class: 'wl-c-box', x: c.x - h, y: c.y - h, width: 2 * h, height: 2 * h, rx: 18, pathLength: 1, style: `animation-delay:${delay}` }));
      }
    });
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
  Sound.playSfx(code === 'wrapper' ? 'pawTrigger' : 'scatterWin');
  for (const info of infos) {
    info.cell.classList.add('is-trigger');
    if (window.SKFx) SKFx.burstAt(info.cell, code === 'wrapper' ? 'gold' : 'sun');
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
    const pool = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c) && (!REEL_ONLY[c] || REEL_ONLY[c].includes(col)));
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
  const wrapper = (col) => [0, 1, 2].some((r) => grid[r][col] === 'wrapper');
  if (wrapper(0) && wrapper(2)) cols.add(4);
  return [...cols].sort((a, b) => a - b);
}

async function landReels(grid, { turbo = false, bombs = [] } = {}) {
  teardownWins();
  const antic = anticipationColumns(grid);
  const firstAntic = antic.length ? antic[0] : GRID_COLS;
  const bombAt = new Map(bombs.map((b) => [`${b.row}:${b.col}`, b.value]));
  const stagger = turbo ? 0 : ReelSpin.PHYS.STAGGER_FIGURES;

  const settle = (col, cells) => {
    for (let row = 0; row < GRID_ROWS; row++) {
      registerCell(cells[row], row, col, grid[row][col]);
      // GDD §3.4: the bomb lands with a spring and its value appears with a pop.
      const v = bombAt.get(`${row}:${col}`);
      if (grid[row][col] === 'bomb' && v) setBombValue(cells[row], v);
    }
    const special = cells.filter((c) => ['scatter', 'wrapper', 'bomb'].includes(c.dataset.symbol));
    for (const c of special) {
      c.classList.add('is-landed');
      Sound.playSfx(c.dataset.symbol === 'wrapper' ? 'pawLand' : c.dataset.symbol === 'bomb' ? 'bombLand' : 'scatterLand');
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
}

// --- Candy bombs, multipliers, mascot ---------------------------------------
//
// Numbers are drawn with the variant's digit art (d0..d9, dx = ×, dplus = +),
// never baked into the bomb (GDD §3.3: one bomb picture, any value).
const GLYPH = { x: 'dx', '×': 'dx', '+': 'dplus' };
function digitsHtml(text, cls = 'glyphs') {
  const chars = String(text).split('').map((ch) => {
    const name = GLYPH[ch] || (/[0-9]/.test(ch) ? `d${ch}` : null);
    return name ? `<img src="${img(`${name}.webp`)}" alt="${ch}" draggable="false">` : '';
  }).join('');
  return `<span class="${cls}" aria-label="${text}">${chars}</span>`;
}

function setBombValue(cell, value) {
  let tag = cell.querySelector('.bomb-value');
  if (!tag) {
    tag = document.createElement('span');
    tag.className = 'bomb-value';
    cell.appendChild(tag);
  }
  tag.innerHTML = digitsHtml(`×${value}`);
  tag.dataset.value = String(value);
  // Bigger values pop bigger (GDD §11: the pop's pitch follows the value).
  cell.dataset.bombTier = value >= 50 ? 'huge' : value >= 15 ? 'big' : value >= 6 ? 'mid' : 'low';
}

// Bombs of a spin without a line win go dark (GDD §5.2.3 / §6.2.5).
function dimBombs() {
  for (const info of cellInfos) {
    if (info && info.symbol === 'bomb') info.cell.classList.add('is-bomb-off');
  }
}

// Every bomb on the grid "pops" and flies into `target` (an element); the
// flights land one after another, `onEach(value)` fires as each arrives.
async function flyBombs(target, onEach) {
  const bombs = cellInfos.filter((i) => i && i.symbol === 'bomb' && i.cell.querySelector('.bomb-value'));
  if (!bombs.length || !target) return;
  const layer = document.getElementById('overlays');
  const lr = layer.getBoundingClientRect();
  const sc = lr.width / layer.offsetWidth || 1;
  const tr = target.getBoundingClientRect();
  const tx = (tr.left + tr.width / 2 - lr.left) / sc;
  const ty = (tr.top + tr.height / 2 - lr.top) / sc;
  Sound.playSfx('bombPop');
  const flights = bombs.map((info, i) => new Promise((resolve) => {
    const tag = info.cell.querySelector('.bomb-value');
    const r = tag.getBoundingClientRect();
    const x = (r.left + r.width / 2 - lr.left) / sc;
    const y = (r.top + r.height / 2 - lr.top) / sc;
    const fly = document.createElement('div');
    fly.className = 'bomb-fly';
    fly.innerHTML = tag.innerHTML;
    fly.style.left = `${x}px`;
    fly.style.top = `${y}px`;
    layer.appendChild(fly);
    info.cell.classList.add('is-bomb-popped');
    if (window.SKFx) SKFx.burstAt(info.cell, 'candy');
    setTimeout(() => {
      fly.style.transition = 'left 0.55s cubic-bezier(.5, 0, .7, 1), top 0.55s cubic-bezier(.2, -0.6, .4, 1), transform 0.55s ease, opacity 0.2s 0.45s';
      fly.style.left = `${tx}px`;
      fly.style.top = `${ty}px`;
      fly.style.transform = 'translate(-50%, -50%) scale(0.55)';
      fly.style.opacity = '0';
    }, 40 + i * 140);
    setTimeout(() => {
      fly.remove();
      Sound.playSfx('multAdd');
      if (onEach) onEach(Number(tag.dataset.value));
      resolve();
    }, 640 + i * 140);
  }));
  await Promise.all(flights);
}

// Base game: the bombs fly into a × badge over the reels, which then "hits"
// the line win (GDD §3.4 P0).
async function playBaseBombs(sum) {
  const badge = document.getElementById('multBadge');
  let acc = 0;
  badge.innerHTML = digitsHtml('×0');
  badge.classList.remove('is-hit');
  badge.classList.add('is-on');
  await flyBombs(badge, (v) => {
    acc += v;
    badge.innerHTML = digitsHtml(`×${acc}`);
    bump(badge);
  });
  badge.innerHTML = digitsHtml(`×${sum}`);
  await wait(260);
  badge.classList.add('is-hit');
  Sound.playSfx('multHit');
  if (window.SKFx) SKFx.burstAt(badge, 'candy');
  setTimeout(() => badge.classList.remove('is-on', 'is-hit'), 1500);
  await wait(420);
}

// Free spins: TOTAL MULTIPLIER (starts at ×1, never resets in the round).
let totalMult = 1;
function setTotalMult(n, { animate = false } = {}) {
  totalMult = n;
  const el = document.getElementById('totalMultValue');
  if (el) el.innerHTML = digitsHtml(`×${n}`);
  if (animate) {
    bump(document.getElementById('totalMult'));
    if (window.SKFx) SKFx.burstAt(document.getElementById('totalMult'), 'candy');
  }
}
async function playRoundBombs(from, to) {
  let acc = from;
  await flyBombs(document.getElementById('totalMultValue'), (v) => {
    acc += v;
    setTotalMult(Math.min(acc, to), { animate: true });
  });
  setTotalMult(to, { animate: true });
  await wait(300);
}

function bump(el) {
  if (!el) return;
  el.classList.remove('is-bump');
  void el.offsetWidth;
  el.classList.add('is-bump');
}

// The chef (landscape only): idle, toss (bombs), cheer (big wins, free
// spins), point (jackpot). Returns to idle on its own.
let mascotTimer = null;
function setMascot(pose, ms = 2200) {
  const el = document.getElementById('mascot');
  if (!el) return;
  clearTimeout(mascotTimer);
  const changed = el.dataset.pose !== pose;
  for (const im of el.querySelectorAll('img')) im.classList.toggle('is-on', im.dataset.pose === pose);
  el.dataset.pose = pose;
  // Only a real reaction hops (bomb, big win, free spins, jackpot); going back
  // to idle — every spin start — is a quiet swap (user: the hop on each spin
  // pulled the eye away from the reels).
  if (changed && pose !== 'idle') bump(el);
  if (pose !== 'idle') mascotTimer = setTimeout(() => setMascot('idle'), ms);
}

// Free-spins summary (GDD §6.2.9): spins played, final multiplier, total.
async function playFsSummary({ spins, mult, total }) {
  Sound.playSfx('bonusTotalWin');
  pushDim();
  await wait(DIM_MS);
  const node = document.createElement('div');
  node.className = 'fs-summary';
  node.innerHTML = `
    <div class="sk-popup__rays"></div>
    <img class="fs-summary__panel" src="${img('fs_end.webp')}" alt="">
    <div class="fs-summary__rows">
      <div class="fs-summary__row"><span>FREE SPINS</span><b>${spins}</b></div>
      <div class="fs-summary__row"><span>MULTIPLIER</span><b>${digitsHtml(`×${mult}`)}</b></div>
      <div class="fs-summary__row fs-summary__row--total"><span>TOTAL WIN</span><b class="fs-summary__total">${money(0)}</b></div>
    </div>`;
  document.getElementById('overlays').appendChild(node);
  void node.offsetWidth;
  node.classList.add('is-in');
  if (window.SKFx) SKFx.startShower('mega');
  setMascot('cheer', 5000);
  let skip = null;
  const skipped = new Promise((r) => { skip = r; node.addEventListener('click', () => r()); });
  await Promise.race([countUp(node.querySelector('.fs-summary__total'), total, 2600, (v) => money(Math.round(v))), skipped]);
  node.querySelector('.fs-summary__total').textContent = money(total);
  await Promise.race([wait(2600), skipped.then(() => wait(250))]);
  if (window.SKFx) SKFx.stopShower();
  node.classList.remove('is-in');
  await wait(320);
  node.remove();
  popDim();
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

async function enterFreeSpins(spins, { superRound = false, mult = 1 } = {}) {
  Sound.playMusic('bonus');
  setMascot('cheer', 3000);
  pushDim(true);
  await wait(DIM_MS);
  await playPopup(superRound ? 'superFreeSpinsIntro' : 'freeSpinsIntro', spins, 2600, { ownDim: false });
  setTotalMult(mult);
  document.getElementById('screen').classList.toggle('is-super', superRound);
  applyMode('freespins');
  setFsPanel(spins, 0);
  await wait(DIM_MS);
  popDim(true);
}

async function leaveFreeSpins(total, { spins = 0, mult = 1 } = {}) {
  await playFsSummary({ spins, mult, total });
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
// Pages that ship tier popup art (popup_big ... popup_grand) set
// window.SK_POPUP_ART; the others keep the plain wordmark titles.
const POPUP_ART = true;
const POPUP_CONFIG = {
  bigWin: { title: 'title_big.webp', art: 'popup_big.webp', kind: 'money', tier: 'big', count: 2600 },
  megaWin: { title: 'title_mega.webp', art: 'popup_mega.webp', kind: 'money', tier: 'mega', count: 3400 },
  epicWin: { title: 'title_epic.webp', art: 'popup_epic.webp', kind: 'money', tier: 'epic', count: 4200 },
  freeSpinsIntro: { title: 'title_freespins.webp', kind: 'count', sub: 'FREE SPINS AWARDED' },
  superFreeSpinsIntro: { title: 'title_superfs.webp', kind: 'count', sub: 'SUPER FREE SPINS · A BOMB EVERY SPIN' },
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
    ${POPUP_ART && cfg.art
      ? `<img class="sk-popup__art" src="${img(cfg.art)}" alt="">`
      : `<img class="sk-popup__title" src="${img(cfg.title)}" alt="">`}
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
// The jackpot award screen (tier emblem or word + counting amount), shown at
// the end of a wheel round; also called by the demo panel (js/savannah-kings/demo.js).
async function showJackpotAward(tier, amount, { auto = false } = {}) {
  const overlay = document.getElementById('wheelOverlay');
  overlay.hidden = false;
  overlay.classList.add('is-in');
  const award = document.getElementById('wheelAward');
  award.dataset.tier = tier;
  award.querySelector('.wheel-award__tier').textContent = SECTOR_STYLE[tier].label;
  setMascot('point', 4000);
  if (POPUP_ART) {
    // Pages with tier popup art show the jackpot's own emblem instead of the word.
    let art = award.querySelector('.wheel-award__art');
    if (!art) {
      art = document.createElement('img');
      art.className = 'wheel-award__art';
      art.alt = '';
      award.querySelector('.wheel-award__tier').before(art);
    }
    art.src = img(`popup_${tier}.webp`);
    award.classList.add('has-art');
  }
  const value = award.querySelector('.wheel-award__value');
  value.textContent = money(0);
  award.hidden = false;
  overlay.classList.add('has-award');
  void award.offsetWidth;
  award.classList.add('is-in');
  Sound.playSfx(tier === 'grand' || tier === 'major' ? 'epicWin' : 'bigWin');
  if (window.SKFx) SKFx.startShower(tier === 'grand' ? 'epic' : tier === 'major' ? 'mega' : 'big');
  await countUp(value, amount, tier === 'grand' ? 4200 : tier === 'major' ? 3200 : 2200, (v) => money(Math.round(v)));
  await wait(auto ? 2200 : 2600);
  if (window.SKFx) SKFx.stopShower();
  award.classList.remove('is-in');
  overlay.classList.remove('is-in', 'is-stopped', 'has-award');
  await wait(450);
  award.hidden = true;
  overlay.hidden = true;
  Sound.playMusic(document.getElementById('screen').dataset.mode === 'freespins' ? 'bonus' : 'base');
}

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

  await showJackpotAward(tier, result.win_amount, { auto });
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
// Three cards (GDD §8.2): Free Spins, Super Free Spins, Jackpot Chance. Pick one -> confirm -> the purchase. Resolves with the product's
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
      <img class="buy-card__art" src="${img(`card_${p.kind}.webp`)}" alt="">
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
  return im.decode ? Promise.race([im.decode().catch(() => {}), wait(4000)]) : Promise.resolve();
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
    'reel_frame.webp', 'logo.webp', 'logo_wide.webp', 'panel.webp', 'total_mult.webp', 'fs_end.webp',
    'mascot_idle.webp', 'mascot_toss.webp', 'mascot_cheer.webp', 'mascot_point.webp',
    'jp_grand.webp', 'jp_major.webp', 'jp_minor.webp', 'jp_mini.webp',
    'wheel_rim.webp', 'wheel_hub.webp', 'wheel_pointer.webp',
    'title_freespins.webp', 'title_superfs.webp', 'title_jackpot.webp', 'title_buybonus.webp',
    'card_fs.webp', 'card_sfs.webp', 'card_jc.webp',
    ...'0123456789'.split('').map((d) => `d${d}.webp`), 'dx.webp', 'dplus.webp',
  ]) tasks.push(track(preloadImage(img(f))));
  if (POPUP_ART) {
    for (const t of ['big', 'mega', 'epic', 'mini', 'minor', 'major', 'grand']) {
      tasks.push(track(preloadImage(img(`popup_${t}.webp`))));
    }
  }
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
  setMascot('idle');
  setTotalMult(1);
}

window.SK = {
  CELL, PAYLINES, GRID_ROWS, GRID_COLS, TIERS, TIER_X, money, setCurrency, symbolSrc, img,
  startReelLoop, stopReelLoop, landReels, applyGrid, playWins, teardownWins, flashTriggers,
  dimBombs, playBaseBombs, playRoundBombs, setTotalMult, setMascot, digitsHtml,
  get totalMult() { return totalMult; },
  showInlineWinAmount, enterFreeSpins, leaveFreeSpins, setFsPanel, bumpFsPanel, playPopup,
  renderJackpots, buildWheel, playJackpotWheel, showBuyWindow, pushDim, popDim, wait,
  get dimCount() { return dimCount; },
};

initSlot();
