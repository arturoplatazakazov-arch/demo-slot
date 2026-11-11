// Koi Fortune — presentation layer (Asian Fortune brief, scripts/chatgpt_art/
// brief_asian_fortune.md). The stage, reels, win lines, popups, buy window
// and layouts come from the Savannah Kings pages (js/savannah-kings/*); the
// Jackpot Wheel is replaced by this game's Hold & Win round (coins lock,
// 3 respins, MINI/MINOR/MAJOR jackpot coins, 15/15 = GRAND), the expanding
// lion by a plain wild. No Spine: statics + CSS + js/savannah-kings/fx.js.
//
// app.js owns the session and the order of events; this file only draws.

// Art variants of the game (same GDD, same backend) point their page at
// their own art folder with window.SK_ASSET_ROOT.
const ASSET_ROOT = window.SK_ASSET_ROOT || 'img/koi-fortune-silk';
const GAME_CODE = 'koi-fortune';
const ART_V = 1;

// Codes are the contract with app/seed/koi_fortune.py.
const SYMBOL_CODES = ['wild', 'scatter', 'coin', 'koi', 'turtle', 'lantern', 'lotus', 'a', 'k', 'q', 'j'];
// Feature symbols never blur past as loop filler.
const TRIGGER_CODES = new Set(['scatter', 'wild', 'coin']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild', 'coin']);
// The dragon (wild) lands on reels 2-5 only.
const REEL_ONLY = { wild: [1, 2, 3, 4] };

const GRID_ROWS = 3;
const GRID_COLS = 5;
// Design px; the whole stage is scaled as one (see fitStage).
const CELL = 176;

// The seed's PAYLINES (rows 0..2); a line win names its payline (1-based).
const PAYLINES = [
  [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
  [0, 0, 1, 2, 2], [2, 2, 1, 0, 0], [1, 0, 0, 0, 1], [1, 2, 2, 2, 1], [0, 1, 1, 1, 0],
];

const TIERS = ['grand', 'major', 'minor', 'mini'];
const TIER_X = { mini: 20, minor: 50, major: 150, grand: 1000 };

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.webp?v=${ART_V}`;
}
function img(file) {
  return `${ASSET_ROOT}/img/${file}?v=${ART_V}`;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Opening screen: a calm, readable spread with the dragon in the middle.
const SYMBOL_LAYOUT = [
  ['koi', 'k', 'lantern', 'q', 'turtle'],
  ['a', 'lotus', 'wild', 'j', 'scatter'],
  ['coin', 'q', 'a', 'koi', 'k'],
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
  const suffix = isPortrait() ? '_mob' : '';
  document.getElementById('bgBase').src = img(`bg_base${suffix}.jpg`);
  document.getElementById('bgBonus').src = img(`bg_fs${suffix}.jpg`);
  document.getElementById('bgHw').src = img(`bg_hw${suffix}.jpg`);
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
  clearCoinLabel(info);
  info.cell.classList.remove('is-empty', 'is-locked', 'is-slam', 'is-collect', 'is-hw-spin');
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
  if (document.body.classList.contains('is-busy') || document.body.classList.contains('is-hw')) return;
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
// the page sets window.SK_WIN_LINE — the five art variants default to 'a'
// (silk glow). The DEMO panel can switch to 'b' (coin beads), 'c' (flow
// ribbon) or back (kept in localStorage); ?line= overrides both.
function winLineStyle() {
  let saved = null;
  try { saved = localStorage.getItem('savannah.winline'); } catch (e) { /* ignore */ }
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
// pay a line): the gongs of a free-spins trigger, the coins of Hold & Win.
async function flashTriggers(code) {
  const infos = cellInfos.filter((i) => i && i.symbol === code);
  if (!infos.length) return;
  for (const info of cellInfos) info.cell.classList.toggle('is-dimmed', !infos.includes(info));
  Sound.playSfx(code === 'coin' ? 'pawTrigger' : 'scatterWin');
  for (const info of infos) {
    info.cell.classList.add('is-trigger');
    if (window.SKFx) SKFx.burstAt(info.cell, code === 'coin' ? 'gold' : 'sun');
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

// Reels where suspense is real: once two gongs are in, every later reel
// that could still bring the third; with 4-5 coins down, the reels that
// could still make it 6.
function anticipationColumns(grid) {
  const cols = new Set();
  let gongs = 0;
  let coins = 0;
  for (let col = 0; col < GRID_COLS; col++) {
    if (gongs === 2) cols.add(col);
    if (coins >= 4 && coins < 6 && coins + 3 * (GRID_COLS - col) >= 6) cols.add(col);
    if ([0, 1, 2].some((r) => grid[r][col] === 'scatter')) gongs += 1;
    coins += [0, 1, 2].filter((r) => grid[r][col] === 'coin').length;
  }
  return [...cols].sort((a, b) => a - b);
}

async function landReels(grid, { turbo = false, coinFaces = null } = {}) {
  teardownWins();
  const antic = anticipationColumns(grid);
  const firstAntic = antic.length ? antic[0] : GRID_COLS;
  const stagger = turbo ? 0 : ReelSpin.PHYS.STAGGER_FIGURES;
  const faces = new Map((coinFaces || []).map((c) => [`${c.row}:${c.col}`, c]));

  const settle = (col, cells) => {
    for (let row = 0; row < GRID_ROWS; row++) {
      const info = registerCell(cells[row], row, col, grid[row][col]);
      const face = faces.get(`${row}:${col}`);
      if (face && grid[row][col] === 'coin') setCoinLabel(info, face);
    }
    const special = cells.filter((c) => c.dataset.symbol === 'scatter' || c.dataset.symbol === 'coin');
    for (const c of special) {
      c.classList.add('is-landed');
      Sound.playSfx(c.dataset.symbol === 'coin' ? 'pawLand' : 'scatterLand');
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

// --- Coin labels --------------------------------------------------------------
//
// A coin shows its value in money (value x bet) in the game's own glyphs
// (img/glyphs/*); a jackpot coin shows its MINI / MINOR / MAJOR tag.
let coinBet = 0;
function setCoinBet(b) { coinBet = b; }

const GLYPH_NAME = { '.': 'dot', ',': 'comma', x: 'x' };
function glyphRow(text) {
  const row = document.createElement('span');
  row.className = 'glyph-row';
  for (const ch of String(text)) {
    const g = document.createElement('img');
    g.alt = ch;
    g.draggable = false;
    g.src = img(`glyphs/${GLYPH_NAME[ch] || ch}.webp`);
    g.className = ch === '.' || ch === ',' ? 'glyph glyph--punct' : 'glyph';
    row.appendChild(g);
  }
  return row;
}

// Short money for a coin face: 12.00 -> "12", 1.50 -> "1.5", 1200 -> "1,200".
function coinMoney(value) {
  const v = (value * coinBet) / 100;
  if (v >= 1000) return Math.round(v).toLocaleString('en-US');
  if (v >= 100) return String(Math.round(v));
  return String(+v.toFixed(2));
}

function isJackpotKind(kind) {
  return kind === 'mini' || kind === 'minor' || kind === 'major' || kind === 'grand';
}

function clearCoinLabel(info) {
  info.cell.querySelectorAll('.coin-label').forEach((n) => n.remove());
  info.cell.classList.remove('is-jp-coin');
  info.coin = null;
}

function setCoinLabel(info, coin) {
  clearCoinLabel(info);
  const label = document.createElement('div');
  label.className = 'coin-label';
  if (isJackpotKind(coin.kind)) {
    info.cell.classList.add('is-jp-coin');
    info.cell.dataset.symbol = 'jpcoin';
    info.cell.querySelector('img').src = symbolSrc('jpcoin');
    const tag = document.createElement('img');
    tag.className = 'coin-label__tag';
    tag.src = img(`tag_${coin.kind}.webp`);
    tag.alt = coin.kind.toUpperCase();
    label.appendChild(tag);
  } else {
    label.appendChild(glyphRow(coinMoney(Number(coin.value))));
  }
  info.cell.appendChild(label);
  info.coin = coin;
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
// Pages that ship tier popup art (popup_big ... popup_grand) set
// window.SK_POPUP_ART; the others keep the plain wordmark titles.
const POPUP_ART = !!window.SK_POPUP_ART;
const POPUP_CONFIG = {
  bigWin: { title: 'title_big.webp', art: 'popup_big.webp', kind: 'money', tier: 'big', count: 2600 },
  megaWin: { title: 'title_mega.webp', art: 'popup_mega.webp', kind: 'money', tier: 'mega', count: 3400 },
  epicWin: { title: 'title_epic.webp', art: 'popup_epic.webp', kind: 'money', tier: 'epic', count: 4200 },
  freeSpinsIntro: { title: 'title_freespins.webp', kind: 'count', sub: 'FREE SPINS AWARDED' },
  freeSpinsMore: { title: 'title_freespins.webp', kind: 'count', sub: 'EXTRA FREE SPINS', plus: true },
  freeSpinsTotal: { title: 'title_totalwin.webp', kind: 'money', tier: 'total', count: 2400 },
  holdWinIntro: { title: 'title_holdwin.webp', kind: 'count', sub: 'RESPINS · COINS LOCK · FILL ALL 15 FOR GRAND' },
  holdWinTotal: { title: 'title_totalwin.webp', kind: 'money', tier: 'total', count: 2400 },
  jp_mini: { title: 'title_big.webp', art: 'popup_mini.webp', kind: 'money', tier: 'big', count: 1600, jp: 'mini' },
  jp_minor: { title: 'title_big.webp', art: 'popup_minor.webp', kind: 'money', tier: 'big', count: 2000, jp: 'minor' },
  jp_major: { title: 'title_mega.webp', art: 'popup_major.webp', kind: 'money', tier: 'mega', count: 2800, jp: 'major' },
  jp_grand: { title: 'title_epic.webp', art: 'popup_grand.webp', kind: 'money', tier: 'epic', count: 4200, jp: 'grand' },
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
  if (cfg.jp) root.classList.add('is-jackpot', `is-jp-${cfg.jp}`);
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

// --- Hold & Win ---------------------------------------------------------------
//
// The whole round is decided by the server (response.hold_and_win: initial
// coins + every respin's landings + total + full-grid GRAND); this only
// replays it. The screen goes to the night pond (bg_hw), every non-coin
// cell empties, the coins that triggered lock with their faces; each respin
// spins the empty cells, new coins lock and reset the counter to 3. At the
// end every coin flies into the total, jackpot coins light their plaque.
const HW_RESPINS = 3;
let hwTurbo = false;

function hwWait(ms) { return wait(hwTurbo ? ms * 0.45 : ms); }

function setRespinCount(n) {
  const el = document.getElementById('hwRespins');
  if (!el) return;
  el.innerHTML = '';
  el.appendChild(glyphRow(String(n)));
  el.classList.remove('is-bump');
  void el.offsetWidth;
  el.classList.add('is-bump');
}

let hwTotalShown = 0;
function setHwTotal(cents, { bump = true } = {}) {
  hwTotalShown = cents;
  const el = document.getElementById('hwTotal');
  if (!el) return;
  el.textContent = money(cents);
  if (bump) { el.classList.remove('is-bump'); void el.offsetWidth; el.classList.add('is-bump'); }
}

function setCellEmpty(info) {
  clearCoinLabel(info);
  info.cell.classList.add('is-empty');
  info.cell.classList.remove('is-locked', 'is-dimmed');
}

function lockCoin(info, coin) {
  info.symbol = 'coin';
  info.cell.dataset.symbol = 'coin';
  info.cell.classList.remove('is-empty', 'is-hw-spin');
  info.cell.classList.add('is-locked', 'is-special');
  info.cell.querySelector('img').src = symbolSrc('coin');
  setCoinLabel(info, coin);
  info.cell.classList.remove('is-slam');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-slam');
}

function hitPlaque(tier) {
  for (const el of document.querySelectorAll(`.jp--${tier}`)) {
    el.classList.remove('is-hit');
    void el.offsetWidth;
    el.classList.add('is-hit');
  }
}

async function playHoldAndWin(hw, bet, { turbo = false, returnMode = 'base' } = {}) {
  hwTurbo = turbo;
  setCoinBet(bet);
  teardownWins();
  const idx = (c) => c.row * GRID_COLS + c.col;
  const locked = new Map();
  const initial = (hw.initial || []).slice().sort((a, b) => a.col - b.col || a.row - b.row);

  // 1. the coins that triggered it
  await flashTriggers('coin');

  // 2. title, then the night pond
  Sound.playMusic('wheel');
  pushDim(true);
  await wait(DIM_MS);
  await playPopup('holdWinIntro', HW_RESPINS, 2200, { ownDim: false });
  applyMode('hw');
  document.body.classList.add('is-hw');
  const initialSet = new Set(initial.map(idx));
  cellInfos.forEach((info, i) => { if (info && !initialSet.has(i)) setCellEmpty(info); });
  for (const c of initial) {
    const info = cellInfos[idx(c)];
    if (!info) continue;
    lockCoin(info, c);
    locked.set(idx(c), { coin: c, info });
  }
  setRespinCount(HW_RESPINS);
  setHwTotal(0, { bump: false });
  await wait(DIM_MS);
  popDim(true);
  await hwWait(700);

  // 3. respins
  let left = HW_RESPINS;
  for (const respin of hw.respins || []) {
    left -= 1;
    setRespinCount(left);
    const landed = new Map((respin.landed || []).map((c) => [idx(c), c]));
    const empties = cellInfos.filter((info, i) => info && !locked.has(i));
    for (const info of empties) info.cell.classList.add('is-hw-spin');
    Sound.playSfx('spinStart');
    await hwWait(520);
    for (let col = 0; col < GRID_COLS; col++) {
      await hwWait(180);
      let stopped = false;
      for (let row = 0; row < GRID_ROWS; row++) {
        const i = row * GRID_COLS + col;
        const info = cellInfos[i];
        if (!info || locked.has(i)) continue;
        info.cell.classList.remove('is-hw-spin');
        stopped = true;
        const c = landed.get(i);
        if (!c) continue;
        lockCoin(info, c);
        locked.set(i, { coin: c, info });
        Sound.playSfx('pawTrigger');
        if (window.SKFx) SKFx.burstAt(info.cell, 'gold');
        if (isJackpotKind(c.kind)) hitPlaque(c.kind);
      }
      if (stopped) Sound.playSfx(col === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop');
    }
    if (landed.size) {
      left = HW_RESPINS;
      await hwWait(380);
      setRespinCount(left);
      await hwWait(520);
    } else {
      await hwWait(420);
    }
  }
  cellInfos.forEach((info) => info && info.cell.classList.remove('is-hw-spin'));

  // 4. every coin into the total, in reading order
  await hwWait(400);
  let total = 0;
  const order = [...locked.values()].sort((a, b) => a.coin.col - b.coin.col || a.coin.row - b.coin.row);
  for (const { coin, info } of order) {
    info.cell.classList.remove('is-collect');
    void info.cell.offsetWidth;
    info.cell.classList.add('is-collect');
    Sound.playSfx('pawLand');
    const x = isJackpotKind(coin.kind) ? TIER_X[coin.kind] : Number(coin.value);
    total += x * bet;
    setHwTotal(total);
    if (isJackpotKind(coin.kind)) {
      hitPlaque(coin.kind);
      await showJackpotAward(coin.kind, TIER_X[coin.kind] * bet, { auto: true });
    } else {
      await hwWait(230);
    }
  }
  if (hw.full_grid_jackpot) {
    await hwWait(300);
    hitPlaque(hw.full_grid_jackpot);
    await showJackpotAward(hw.full_grid_jackpot, TIER_X[hw.full_grid_jackpot] * bet, { auto: true });
    total += TIER_X[hw.full_grid_jackpot] * bet;
  }
  // The server's figure is the truth (caps, rounding).
  setHwTotal(hw.total_win);
  await hwWait(700);
  await playPopup('holdWinTotal', hw.total_win, 2600);

  // 5. back to the reels
  pushDim(true);
  await wait(DIM_MS);
  document.body.classList.remove('is-hw');
  for (const info of cellInfos) if (info) info.cell.classList.remove('is-empty', 'is-locked', 'is-slam', 'is-collect');
  applyMode(returnMode);
  Sound.playMusic(returnMode === 'freespins' ? 'bonus' : 'base');
  await wait(DIM_MS);
  popDim(true);
  return hw.total_win;
}

// The jackpot award: the tier's emblem over the counting panel. Used by the
// Hold & Win round and by the DEMO panel (js/savannah-kings/demo.js).
function showJackpotAward(tier, amount, { auto = false } = {}) {
  return playPopup(`jp_${tier}`, amount, auto ? 1600 : 2400);
}

// --- Buy Bonus window -------------------------------------------------------
//
// Two cards: Free Spins (the gong) and Hold & Win (the coins). Pick one ->
// confirm -> the purchase. Resolves with the product's
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
      <img class="buy-card__art" src="${img(p.kind === 'fs' ? 'card_fs.webp' : 'card_hw.webp')}" alt="">
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
    'reel_frame.webp', 'logo.webp', 'logo_wide.webp', 'panel.webp', 'respins.webp',
    'jp_grand.webp', 'jp_major.webp', 'jp_minor.webp', 'jp_mini.webp',
    'tag_mini.webp', 'tag_minor.webp', 'tag_major.webp', 'ante_off.webp', 'ante_on.webp',
    'title_big.webp', 'title_mega.webp', 'title_epic.webp', 'title_freespins.webp', 'title_totalwin.webp',
    'title_holdwin.webp', 'title_buybonus.webp', 'card_fs.webp', 'card_hw.webp',
    ...'0123456789'.split('').map((d) => `glyphs/${d}.webp`), 'glyphs/dot.webp', 'glyphs/comma.webp',
  ]) tasks.push(track(preloadImage(img(f))));
  tasks.push(track(preloadImage(symbolSrc('jpcoin'))));
  if (POPUP_ART) {
    for (const t of ['big', 'mega', 'epic', 'mini', 'minor', 'major', 'grand']) {
      tasks.push(track(preloadImage(img(`popup_${t}.webp`))));
    }
  }
  const suffix = isPortrait() ? '_mob' : '';
  tasks.push(track(preloadImage(img(`bg_base${suffix}.jpg`))));
  tasks.push(track(preloadImage(img(`bg_fs${suffix}.jpg`))));
  tasks.push(track(preloadImage(img(`bg_hw${suffix}.jpg`))));
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
  renderJackpots, playHoldAndWin, showJackpotAward, setCoinBet, showBuyWindow, pushDim, popDim, wait,
  get dimCount() { return dimCount; },
};

initSlot();
