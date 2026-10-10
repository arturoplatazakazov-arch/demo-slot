// Gangsta Casino — game-specific wiring. Layout comes from the designer's PSB
// (Desk_Gangsta_Slot_OUT, 1932x940); mechanics are Dirty Money / MAFIA's
// (../dirty-money-mafia/slot.js): 5x3 line pay, expanding + walking wild,
// scatter free spins, 3x WOF -> wheel of fortune, bonus buy.
//
// Symbols rest as static PNG tiles and play their Spine `win` clip only while
// winning (img/gangsta-casino/spine/<code>/, one skeleton per symbol); the
// expanding wild is the wild skeleton's own `expand` -> idle_big / win_big.
// Win / bonus popups and the buy dialog are DOM cards (.gpop / .buy-dialog).
// If Spine can't load (no WebGL, a broken export), every hook falls back to
// the CSS path: .is-winning pulse and the wild_big.png clip-path grow.
//
// Spine exports: delivered as Spine 4.3.26 JSON, run on the repo's 4.1
// runtime — they only use 4.x basics (bones/slots/region/mesh/clipping,
// rotate/scale/translate/rgba/attachment/deform), nothing 4.2+ added. Folder
// names in the delivery were swapped for two commons: export/common_2 is the
// pink glock (our common_4), export/common_4 the gold uzi (our common_2).

const ASSET_ROOT = 'img/gangsta-casino';
const SYMBOL_ROOT = `${ASSET_ROOT}/symbols`;
const SPINE_ROOT = `${ASSET_ROOT}/spine`;

// Every export is authored around a 200x200 tile centred on the skeleton
// origin (the atlas carries that exact tile), and the grid draws tiles at the
// PSB's 188px — so anchor = 200x200 box, fit = 188/200.
const TILE_BOX = { x: -100, y: -100, width: 200, height: 200 };
// Symbols are drawn 1:1 with the PSB (rare frame 187px in a 197px column,
// bat 193px…) — the sym_* land exports are authored in exactly those pixels.
const TILE_FIT = 1;
// Clip names that differ from the default `win`.
const WIN_CLIP = { wild: 'win_small' };

// code -> tile filename. Codes are a 1:1 contract with app/seed/gangsta_casino.py.
const SYMBOL_ART = {
  scatter: 'scatter.png',
  wof: 'wof.png',
  wild: 'wild.png',
  rare_purple: 'rare_purple.png',
  rare_yellow: 'rare_yellow.png',
  rare_blue: 'rare_blue.png',
  rare_green: 'rare_green.png',
  common_1: 'common_1.png',
  common_2: 'common_2.png',
  common_3: 'common_3.png',
  common_4: 'common_4.png',
};
const SYMBOL_CODES = Object.keys(SYMBOL_ART);
function symbolSrc(code) {
  return `${SYMBOL_ROOT}/${SYMBOL_ART[code]}`;
}

// Trigger symbols never appear as spin filler (a scatter blurring past reads
// as a near-miss that never was).
const TRIGGER_CODES = new Set(['scatter', 'wof', 'wild']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));

const WIN_PULSE_MS = 1100;
const DIM_TRANSITION_MS = 320;
const REEL_LOOP_STEP_MS = 420;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 450;

const GRID_COLS = 5;
const GRID_ROWS = 3;

// Attract layout = the PSB mockup's own grid (wild column in the middle is
// shown small here; the dev "Big Wild" button previews the grown one).
const SYMBOL_LAYOUT = [
  ['scatter', 'common_2', 'wild', 'rare_blue', 'common_1'],
  ['rare_purple', 'common_3', 'wild', 'common_2', 'wild'],
  ['common_4', 'rare_green', 'wild', 'rare_yellow', 'wof'],
];

// Cell pitch straight from the PSB: symbol centres are 197px apart across and
// 200px down (icons layer). Fixed for both layouts — portrait scales the whole
// .reel-rig instead (css), so the grid itself never changes pitch.
let cellW = 197, cellH = 200;
let colStep = cellW, rowStep = cellH;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => parseFloat(cs.getPropertyValue(name)) || fallback;
  cellW = num('--cell-w', 197);
  cellH = num('--cell-h', 200);
  colStep = cellW;
  rowStep = cellH;
}

let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];
let bigWildEls = [];
let reelsBusy = false;

const wait = SlotCore.wait;
const randomSymbolCode = SlotCore.makeRandomSymbol(FILLER_CODES);

// --- Grid -------------------------------------------------------------------

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  const img = document.createElement('img');
  img.alt = code;
  img.decoding = 'async';
  img.src = symbolSrc(code);
  img.draggable = false;
  cell.appendChild(img);
  const anchor = document.createElement('div');
  anchor.className = 'reel__cell-anchor';
  cell.appendChild(anchor);
  return { cell, img, anchor };
}

function buildReelGrid() {
  const gridEl = document.getElementById('reelGrid');
  gridEl.innerHTML = '';
  const inner = document.createElement('div');
  inner.className = 'reel__grid-inner';
  gridEl.appendChild(inner);

  readCellDims();
  cellInfos = [];
  reelCols = [];

  for (let col = 0; col < GRID_COLS; col++) {
    const colEl = document.createElement('div');
    colEl.className = 'reel__col';
    colEl.style.left = `${col * colStep}px`;
    const stripEl = document.createElement('div');
    stripEl.className = 'reel__strip';
    colEl.appendChild(stripEl);
    inner.appendChild(colEl);
    reelCols.push({ colEl, stripEl });

    for (let row = 0; row < GRID_ROWS; row++) {
      const symbol = SYMBOL_LAYOUT[row][col];
      const { cell, img, anchor } = createCellNode(symbol);
      stripEl.appendChild(cell);
      const info = { symbol, cell, img, anchor, instance: null, winLoopTimeout: null };
      cell.addEventListener('click', () => onCellClick(info, col));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
}

function clearBigWilds() {
  for (const el of bigWildEls) {
    if (el.__overlay && stage) stage.removeOverlay(el.__overlay);
    el.remove();
  }
  bigWildEls = [];
}

// Pull a cell's win clip off the canvas and give the tile back.
function dropCellInstance(info) {
  info.gen = (info.gen || 0) + 1; // invalidates a clip still loading for this cell
  if (info.instance && stage) stage.removeBase(info.instance);
  if (info.landInstance && stage) stage.removeBase(info.landInstance);
  info.instance = null;
  info.landInstance = null;
  if (info.img) info.img.style.visibility = '';
}

function teardownCellInstances() {
  winSequenceEpoch += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  clearBigWilds();
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed', 'is-winning', 'is-hidden');
    if (info.winLoopTimeout) {
      clearTimeout(info.winLoopTimeout);
      info.winLoopTimeout = null;
    }
    info.winToken = null;
    dropCellInstance(info);
  }
}

function setCellSymbol(info, code) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  info.winToken = null;
  dropCellInstance(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.cell.classList.remove('is-winning', 'is-hidden');
  info.img.src = symbolSrc(code);
}

// --- Spine ------------------------------------------------------------------

let stage = null; // SpineEngine.SpineStage, null if WebGL/Spine is unavailable

function getSymbolResource(code) {
  if (!stage) return Promise.reject(new Error('no spine stage'));
  // Atlases are true premultiplied alpha (pma:true, RGB <= A in every pixel).
  return SpineEngine.SpineResource.load(stage.assetManager, `${SPINE_ROOT}/${code}`, { premultipliedAlpha: true });
}

// Plays `clip` once and resolves when it ends — or after the clip's own length
// plus slack, whichever is first: onSettle never fires in a hidden tab (rAF
// is frozen) or once the instance was pulled off the stage by a new spin, and
// a spin chain must never hang on it.
function playClipOnce(instance, clip, loop = false) {
  const anim = instance.resource.skeletonData.findAnimation(clip);
  const ms = anim ? anim.duration * 1000 : WIN_PULSE_MS;
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      instance.onSettle = null;
      resolve();
    };
    instance.onSettle = finish;
    instance.play(clip, loop);
    setTimeout(finish, ms + 250);
  });
}

// --- Win presentation -------------------------------------------------------

// CSS fallback. Restarting a CSS animation needs the class off for one frame
// — toggling it back in the same task is a no-op.
function playCssPulse(info) {
  const { cell } = info;
  cell.classList.remove('is-winning');
  void cell.offsetWidth;
  cell.classList.add('is-winning');
  return wait(WIN_PULSE_MS).then(() => cell.classList.remove('is-winning'));
}

// Spine win clip over the cell: the tile hides while its skeleton plays, and
// comes back when the clip ends (no idle loops on the resting grid).
// A cell under a grown wild (.is-hidden) is represented by the big wild's own
// win_big — it must not draw its small win_small over it. It still takes the
// clip's time so line sequencing keeps its rhythm.
const BIG_WILD_COVERED_HOLD_MS = 1500;

async function playWinAnimationOnce(info) {
  if (info.cell.classList.contains('is-hidden')) return wait(BIG_WILD_COVERED_HOLD_MS);
  const gen = info.gen;
  let resource;
  try {
    resource = await getSymbolResource(info.symbol);
  } catch (err) {
    return playCssPulse(info);
  }
  // The cell may have been rebuilt (new spin) while the export was loading.
  if (!info.cell.isConnected || !info.anchor || info.gen !== gen) return;
  // A wild may have grown over this cell while its export was loading.
  if (info.cell.classList.contains('is-hidden')) return wait(BIG_WILD_COVERED_HOLD_MS);
  if (info.landInstance) {
    stage.removeBase(info.landInstance);
    info.landInstance = null;
  }
  if (!info.instance) {
    const instance = resource.createInstance();
    instance.anchorEl = info.anchor;
    instance.boundsOverride = TILE_BOX;
    instance.fit = TILE_FIT;
    info.instance = instance;
  }
  const { instance } = info;
  info.cell.classList.add('is-animating');
  info.img.style.visibility = 'hidden';
  stage.addBase(instance);
  await playClipOnce(instance, WIN_CLIP[info.symbol] || 'win');
  if (info.instance !== instance) return; // torn down / re-symboled meanwhile
  stage.removeBase(instance);
  info.img.style.visibility = '';
  info.cell.classList.remove('is-animating');
}

function previewSymbolWin(info) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  // The clip promise always settles (playClipOnce has a timeout), so a loop
  // that outlived its cell would keep re-adding its skeleton over the next
  // spin's grid — every teardown/re-symbol bumps the token to end it.
  const token = (info.winToken = {});
  const playOnce = () => {
    playWinAnimationOnce(info).then(() => {
      if (info.winToken !== token) return;
      info.winLoopTimeout = setTimeout(() => {
        info.winLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

function onCellClick(info, col) {
  if (info.symbol === 'wild') previewBigWild(col);
  else previewSymbolWin(info);
}

function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
}

let multiLineSequenceTimeout = null;

// Phase -1 plays every winning cell together, then each payline on its own so
// overlapping lines can be told apart — same cycle as the donor.
// Bumped by teardownCellInstances: an in-flight sequence step that resolves
// after a teardown must not schedule the next one.
let winSequenceEpoch = 0;

function playMultiLineWinSequence(groups, allWinInfos) {
  const epoch = winSequenceEpoch;
  let groupIndex = -1;
  const step = () => {
    if (epoch !== winSequenceEpoch) return;
    const activeInfos = groupIndex === -1 ? allWinInfos : groups[groupIndex];
    const activeSet = new Set(activeInfos);
    for (const info of cellInfos) {
      if (info) setCellDimmed(info, !activeSet.has(info));
    }
    Promise.all(activeInfos.map((info) => playWinAnimationOnce(info))).then(() => {
      if (epoch !== winSequenceEpoch) return;
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
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  const allWinInfos = (winningCells || [])
    .map(({ row, col }) => cellInfos[row * GRID_COLS + col])
    .filter(Boolean);
  const winSet = new Set(allWinInfos);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, allWinInfos.length > 0 && !winSet.has(info));
  }
  if (allWinInfos.length) {
    playSceneClip('frame', 'win');
    playSceneClip('logo', 'win');
  }
  // A grown wild column celebrates along with its line.
  for (const el of bigWildEls) {
    const col = Number(el.dataset.col);
    const winning = allWinInfos.some((i) => cellInfos.indexOf(i) % GRID_COLS === col);
    el.classList.toggle('is-winning', winning);
    if (el.__overlay && winning) el.__overlay.play('win_big', true);
  }

  const groups = buildWinGroups(lineWins, countWins);
  if (groups.length > 1) {
    playMultiLineWinSequence(groups, allWinInfos);
  } else {
    for (const info of allWinInfos) previewSymbolWin(info);
  }
}

function applyGrid(grid) {
  teardownCellInstances();
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      setCellSymbol(cellInfos[row * GRID_COLS + col], grid[row][col]);
    }
  }
}

const INLINE_WIN_AMOUNT_HOLD_MS = 1800;
let inlineWinAmountTimeout = null;

function showInlineWinAmount(amount) {
  const el = document.getElementById('reelWinAmount');
  if (!el) return;
  if (inlineWinAmountTimeout) clearTimeout(inlineWinAmountTimeout);
  el.dataset.amount = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');
  inlineWinAmountTimeout = setTimeout(() => {
    inlineWinAmountTimeout = null;
    el.classList.remove('is-visible');
  }, INLINE_WIN_AMOUNT_HOLD_MS);
}

// --- Reel motion (SlotCore) -------------------------------------------------

const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

const reelMotion = SlotCore.createReelMotion({
  cols: GRID_COLS,
  rows: GRID_ROWS,
  getReelCols: () => reelCols,
  getRowStep: () => rowStep,
  createCellNode,
  randomSymbolCode,
  currentColumnCodes: (col) => ReelMath.currentColumnCodes(cellInfos, GRID_COLS, GRID_ROWS, col),
  playSfx: (name) => Sound.playSfx(name),
  sounds: { spinStart: 'spinStart', reelStop: 'reelStop', finalReelStop: 'finalReelStop' },
  timings: {
    loopStepMs: REEL_LOOP_STEP_MS,
    landFillerCount: REEL_LAND_FILLER_COUNT,
    landDurationMs: REEL_LAND_DURATION_MS,
  },
  anticipation: { prerollMs: ANTICIPATION_PREROLL_MS, fillerCount: ANTICIPATION_PREROLL_FILLER_COUNT },
});

function startReelLoop() {
  reelsBusy = true;
  teardownCellInstances();
  reelMotion.startLoop();
}

function stopReelLoop() {
  reelsBusy = false;
  reelMotion.stopLoop();
}

const landReel = reelMotion.landReel;

function settleColumnCells(cellEls, col, finalCodes) {
  for (let row = 0; row < GRID_ROWS; row++) {
    const cell = cellEls[row];
    const img = cell.querySelector('img');
    const anchor = cell.querySelector('.reel__cell-anchor');
    const info = { symbol: finalCodes[row], cell, img, anchor, instance: null, winLoopTimeout: null };
    cell.addEventListener('click', () => onCellClick(info, col));
    cellInfos[row * GRID_COLS + col] = info;
    if (LAND_ENABLED) playLandOnce(info);
  }
}

// `land` bounce from the sym_* pack (img/gangsta-casino/spine/land/<code>/):
// the PSB icon art 1:1 around the origin, so it swaps with the static tile
// invisibly. Straight alpha (pma:false). Held in its own slot on the cell so
// a win that starts while it's still bouncing can take over cleanly.
function getLandResource(code) {
  if (!stage) return Promise.reject(new Error('no spine stage'));
  return SpineEngine.SpineResource.load(stage.assetManager, `${LAND_ROOT}/${code}`, { premultipliedAlpha: false });
}

async function playLandOnce(info) {
  if (!stage) return;
  const gen = info.gen;
  let resource;
  try {
    resource = await getLandResource(info.symbol);
  } catch (err) {
    return;
  }
  if (!info.cell.isConnected || info.gen !== gen || info.instance || info.cell.classList.contains('is-hidden')) return;
  const inst = resource.createInstance();
  inst.anchorEl = info.anchor;
  inst.boundsOverride = TILE_BOX;
  inst.fit = TILE_FIT;
  info.landInstance = inst;
  info.img.style.visibility = 'hidden';
  stage.addBase(inst);
  await playClipOnce(inst, 'land');
  if (info.landInstance !== inst) return; // a win or a teardown took over
  stage.removeBase(inst);
  info.landInstance = null;
  if (!info.instance) info.img.style.visibility = '';
}

// --- Expanding wild ---------------------------------------------------------
//
// Spine: the wild skeleton IS the grid tile in its setup pose, and `expand`
// opens that card into the reel-height wild (210x600, same as the PSB's
// wild_long). One instance per grown column, fitted by height to the
// 600px grid column, then idle_big — or win_big if the column pays.
// Fallback: wild_big.png grown out of the middle row by clip-path.

const BIG_WILD_GROW_MS = 650;

// Fit box of the GROWN wild = the card's bg art (210x600) in its idle_big
// pose; glows/sparks/rays pulse well past it and would make the fit wobble.
const BIG_WILD_CORE_SLOTS = new Set(['bg', 'girl', 'frame_top', 'frame_mid', 'frame_bot']);
function computeBigWildBounds(resource) {
  try {
    const probe = new spine.Skeleton(resource.skeletonData);
    probe.setToSetupPose();
    const state = new spine.AnimationState(resource.animationStateData);
    state.setAnimation(0, 'idle_big', true);
    state.update(0);
    state.apply(probe);
    for (const slot of probe.slots) {
      if (!BIG_WILD_CORE_SLOTS.has(slot.data.name)) slot.setAttachment(null);
    }
    probe.updateWorldTransform();
    const offset = new spine.Vector2();
    const size = new spine.Vector2();
    probe.getBounds(offset, size, []);
    if (!(size.x > 0 && size.y > 0)) return null;
    return { x: offset.x, y: offset.y, width: size.x, height: size.y };
  } catch (err) {
    console.warn('big-wild bounds compute failed:', err);
    return null;
  }
}

async function revealExpandedWildSpine(col, win) {
  const resource = await getSymbolResource('wild');
  if (resource.bigWildBounds === undefined) resource.bigWildBounds = computeBigWildBounds(resource);
  if (!resource.bigWildBounds) throw new Error('no big-wild bounds');

  const host = document.getElementById('bigWilds');
  const el = document.createElement('div');
  el.className = 'big-wild-anchor';
  el.dataset.col = String(col);
  el.style.setProperty('--col', String(col));
  host.appendChild(el);

  const overlay = resource.createInstance();
  overlay.anchorEl = el;
  overlay.fitMode = 'height';
  overlay.fit = 1;
  overlay.boundsOverride = resource.bigWildBounds;
  el.__overlay = overlay;
  bigWildEls.push(el);

  // The card takes over from the tiles straight away — it starts as the tile.
  for (let row = 0; row < GRID_ROWS; row++) {
    const info = cellInfos[row * GRID_COLS + col];
    if (!info) continue;
    dropCellInstance(info);
    info.cell.classList.add('is-hidden');
  }
  // Overlay layer, not base: base draws in insertion order, so a cell's win
  // clip added after the grow would paint over the big wild.
  stage.addOverlay(overlay);
  Sound.playSfx('wildGrow');
  await playClipOnce(overlay, 'expand');
  if (!el.isConnected) return el;
  if (win) Sound.playSfx('wildWin');
  overlay.play(win ? 'win_big' : 'idle_big', true);
  return el;
}

async function revealExpandedWild(col, { win = false } = {}) {
  if (stage) {
    try {
      return await revealExpandedWildSpine(col, win);
    } catch (err) {
      console.warn('spine expanding wild failed, using the CSS one:', err);
    }
  }
  const host = document.getElementById('bigWilds');
  const el = document.createElement('div');
  el.className = 'big-wild';
  el.dataset.col = String(col);
  el.style.setProperty('--col', String(col));
  el.innerHTML = `<img src="${SYMBOL_ROOT}/wild_big.png" alt="WILD">`;
  host.appendChild(el);
  bigWildEls.push(el);

  void el.offsetWidth;
  el.classList.add('is-grown');
  Sound.playSfx('wildGrow');
  await wait(BIG_WILD_GROW_MS);
  for (let row = 0; row < GRID_ROWS; row++) {
    const info = cellInfos[row * GRID_COLS + col];
    if (info) info.cell.classList.add('is-hidden');
  }
  if (win) {
    Sound.playSfx('wildWin');
    el.classList.add('is-winning');
  }
  return el;
}

function celebrateExpandedWild(col, wildEvents, winningCols) {
  const grew = wildEvents.some((e) => e.reel === col && (e.event === 'expanded' || e.event === 'walked'));
  if (grew) return revealExpandedWild(col, { win: winningCols.has(col) });
  return Promise.resolve(null);
}

let bigWildPreviewBusy = false;
async function previewBigWild(col = Math.floor(GRID_COLS / 2), win = true) {
  if (bigWildPreviewBusy || reelsBusy || bigWildEls.length) return;
  bigWildPreviewBusy = true;
  try {
    const saved = [0, 1, 2].map((row) => cellInfos[row * GRID_COLS + col].symbol);
    for (let row = 0; row < GRID_ROWS; row++) setCellSymbol(cellInfos[row * GRID_COLS + col], 'wild');
    const el = await revealExpandedWild(col, { win });
    await wait(2600);
    if (el.__overlay && stage) stage.removeOverlay(el.__overlay);
    el.remove();
    bigWildEls = bigWildEls.filter((e) => e !== el);
    for (let row = 0; row < GRID_ROWS; row++) setCellSymbol(cellInfos[row * GRID_COLS + col], saved[row]);
  } finally {
    bigWildPreviewBusy = false;
  }
}

function winningColumnSet(lineWins, countWins) {
  const cols = new Set();
  for (const w of [...(lineWins || []), ...(countWins || [])]) {
    for (const pos of w.positions || []) cols.add(pos.col);
  }
  return cols;
}

async function landReels(grid, anticipationColumns = [], wildEvents = [], lineWins = [], countWins = []) {
  reelsBusy = true;
  try {
    await landReelsInner(grid, anticipationColumns, wildEvents, lineWins, countWins);
  } finally {
    reelsBusy = false;
  }
}

// Columns from the first anticipation column on land ONE AT A TIME.
async function landReelsInner(grid, anticipationColumns, wildEvents, lineWins, countWins) {
  teardownCellInstances();
  const winningCols = winningColumnSet(lineWins, countWins);
  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    leadTasks.push(
      landReel(col, finalCodes, col * REEL_LAND_STAGGER_MS, false)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes))
        .then(() => celebrateExpandedWild(col, wildEvents, winningCols)),
    );
  }
  await Promise.all(leadTasks);
  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');
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
    settleColumnCells(cellEls, col, finalCodes);
    await celebrateExpandedWild(col, wildEvents, winningCols);
  }
}

// --- Screen dim / free spins mode -------------------------------------------

const screenDim = SlotCore.createScreenDim({ elId: 'screenDim', transitionMs: DIM_TRANSITION_MS });
const pushScreenDim = screenDim.push;
const popScreenDim = screenDim.pop;
const withScreenDim = screenDim.run;

function currentMode() {
  return document.getElementById('screen').dataset.mode || 'base';
}

function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
  syncScene();
}

const BONUS_INTRO_HOLD_MS = 3000;

async function enterBonusTransition(amount = 0) {
  pushScreenDim(true);
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS);
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true);
}

function setFreeSpinsMode(active, amount = 0) {
  const next = active ? 'freespins' : 'base';
  if (currentMode() === next) return Promise.resolve();
  Sound.playMusic(next === 'freespins' ? 'bonus' : 'base');
  if (next === 'freespins') return enterBonusTransition(amount);
  return withScreenDim(
    async () => {
      applyModeScreen(next);
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
}

// Three odometer windows on the counter art; zero-padded like a real drum.
function setFreeSpinsCounter(remaining) {
  const digits = String(Math.max(0, Math.min(999, remaining))).padStart(3, '0');
  playSceneClip('freespins', 'counter_update');
  document.querySelectorAll('.fs-counter__digit').forEach((el, i) => {
    el.textContent = digits[i];
  });
}

// --- Wheel of Fortune -------------------------------------------------------
//
// The prize is decided server-side (`wheel_of_fortune` in the spin response);
// the client draws the drum from `segments`, waits for SPIN and eases the drum
// onto `segment_index`. The pointer sits at 12 o'clock and segment 0 is centred
// under it at rest, so segment i lands after turning -i * (360 / count).

const WOF_SPIN_TURNS = 5;
const WOF_SPIN_MS = 4600;
const WOF_PRIZE_HOLD_MS = 2200;
// Purple / magenta alternation of the delivered drum art; free-spins slots go
// gold so the jackpot slice reads at a glance.
const WOF_COLORS = ['#5a2a9c', '#c8236e'];
const WOF_FS_COLOR = '#d9a21c';

async function celebrateWheelTrigger() {
  const triggers = cellInfos.filter((info) => info && info.symbol === 'wof');
  if (triggers.length === 0) return;
  const winSet = new Set(triggers);
  for (const info of cellInfos) if (info) setCellDimmed(info, !winSet.has(info));
  await Promise.all(triggers.map((info) => playWinAnimationOnce(info)));
  if (!stage) await Promise.all(triggers.map((info) => playWinAnimationOnce(info)));
  for (const info of cellInfos) if (info) setCellDimmed(info, false);
}

function wofSegmentLabel(segment) {
  return segment.type === 'free_spins' ? 'FREE SPINS' : `x${segment.value}`;
}

function renderWheel(segments) {
  const n = Math.max(1, segments.length);
  const step = 360 / n;
  // Sector i spans [-step/2, +step/2] around its own angle i*step.
  const stops = segments.map((seg, i) => {
    const color = seg.type === 'free_spins' ? WOF_FS_COLOR : WOF_COLORS[i % 2];
    return `${color} ${i * step}deg ${(i + 1) * step}deg`;
  });
  const disk = document.getElementById('wofDisk');
  disk.style.background =
    `radial-gradient(circle, transparent 0 58%, rgba(0,0,0,.35) 100%),` +
    `repeating-conic-gradient(from ${-step / 2}deg, rgba(235,235,245,.85) 0 0.7deg, transparent 0.7deg ${step}deg),` +
    `conic-gradient(from ${-step / 2}deg, ${stops.join(', ')})`;

  // Marquee bulbs on the rim — static (not on the rotor), built once.
  const bulbsEl = document.getElementById('wofBulbs');
  if (bulbsEl && !bulbsEl.childElementCount) {
    for (let i = 0; i < 28; i++) {
      const bulb = document.createElement('i');
      bulb.style.setProperty('--a', `${(i * 360) / 28}deg`);
      bulbsEl.appendChild(bulb);
    }
  }

  const labelsEl = document.getElementById('wofLabels');
  labelsEl.innerHTML = '';
  segments.forEach((segment, i) => {
    const spoke = document.createElement('div');
    spoke.className = `wof__label${segment.type === 'free_spins' ? ' wof__label--fs' : ''}`;
    spoke.style.setProperty('--a', `${i * step}deg`);
    const text = document.createElement('span');
    text.textContent = wofSegmentLabel(segment);
    spoke.appendChild(text);
    labelsEl.appendChild(spoke);
  });
}

function playWheelOfFortune(wheel) {
  const popup = document.getElementById('wofPopup');
  const rotor = document.getElementById('wofRotor');
  const spinBtn = document.getElementById('wofSpin');
  const prizeEl = document.getElementById('wofPrize');
  if (!popup || !wheel) return Promise.resolve();

  const segments = wheel.segments || [];
  renderWheel(segments);
  prizeEl.hidden = true;
  prizeEl.classList.remove('is-visible');
  spinBtn.disabled = false;
  rotor.style.transition = 'none';
  rotor.style.setProperty('--wof-angle', '0deg');
  void rotor.offsetHeight;

  popup.hidden = false;
  void popup.offsetHeight;
  popup.classList.add('is-open');
  Sound.playSfx('popupOpen');

  return new Promise((resolve) => {
    const start = () => {
      spinBtn.disabled = true;
      spinBtn.removeEventListener('click', start);
      Sound.playSfx('wheelSpin');
      const step = 360 / Math.max(1, segments.length);
      const target = -(WOF_SPIN_TURNS * 360 + wheel.segment_index * step);
      rotor.style.transition = `transform ${WOF_SPIN_MS}ms cubic-bezier(0.15, 0.85, 0.2, 1)`;
      rotor.style.setProperty('--wof-angle', `${target}deg`);

      let settled = false;
      const finish = async () => {
        if (settled) return;
        settled = true;
        rotor.removeEventListener('transitionend', onEnd);
        popup.classList.add('is-landed');
        const segment = segments[wheel.segment_index];
        prizeEl.textContent =
          wheel.prize_type === 'free_spins'
            ? 'FREE SPINS!'
            : `${segment ? wofSegmentLabel(segment) : ''} = ${Number(wheel.win_amount).toLocaleString('en-US')}`;
        prizeEl.hidden = false;
        void prizeEl.offsetHeight;
        prizeEl.classList.add('is-visible');
        Sound.playSfx(wheel.prize_type === 'free_spins' ? 'bigWin' : 'smallWin');
        await wait(WOF_PRIZE_HOLD_MS);
        popup.classList.remove('is-open', 'is-landed');
        Sound.playSfx('popupClose');
        await wait(DIM_TRANSITION_MS);
        popup.hidden = true;
        resolve();
      };
      const onEnd = (event) => {
        if (event.target === rotor && event.propertyName === 'transform') finish();
      };
      rotor.addEventListener('transitionend', onEnd);
      setTimeout(finish, WOF_SPIN_MS + 400);
    };
    spinBtn.addEventListener('click', start);
  });
}

// --- Popups (DOM) -----------------------------------------------------------

const POPUP_CONTENT = {
  bigWin: { title: 'BIG WIN', tier: 'big' },
  megaWin: { title: 'MEGA WIN', tier: 'mega' },
  epicWin: { title: 'EPIC WIN', tier: 'epic' },
  bonusSpinsTotalWin: { title: 'TOTAL WIN', tier: 'total', sub: 'FREE SPINS' },
  bonusSpinsWin: { title: 'YOU WON', tier: 'spins', sub: 'FREE SPINS', count: true },
};
const POPUP_COUNT_MS = 1400;
const BILL_COUNT = 26;

function countUp(el, target, ms, integer) {
  const start = performance.now();
  return new Promise((resolve) => {
    const tick = (now) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = target * eased;
      el.textContent = (integer ? Math.round(v) : Math.round(v)).toLocaleString('en-US');
      if (t < 1) requestAnimationFrame(tick);
      else resolve();
    };
    requestAnimationFrame(tick);
    // Hidden tab: rAF never ticks — land on the final number anyway.
    setTimeout(() => {
      el.textContent = Math.round(target).toLocaleString('en-US');
      resolve();
    }, ms + 300);
  });
}

// Falling-banknote confetti for the big tiers (CSS only, see .gpop__bill).
function spawnBills(host) {
  host.innerHTML = '';
  for (let i = 0; i < BILL_COUNT; i++) {
    const b = document.createElement('i');
    b.className = 'gpop__bill';
    b.style.setProperty('--x', `${Math.random() * 100}%`);
    b.style.setProperty('--delay', `${(Math.random() * 1.6).toFixed(2)}s`);
    b.style.setProperty('--dur', `${(2.2 + Math.random() * 1.6).toFixed(2)}s`);
    b.style.setProperty('--rot', `${Math.round(Math.random() * 720 - 360)}deg`);
    b.style.setProperty('--s', (0.7 + Math.random() * 0.6).toFixed(2));
    host.appendChild(b);
  }
}

let popupBusy = Promise.resolve();

// Resolves once the popup has fully closed. `ownDim` is false when the caller
// already holds a screen dim (the bonus intro's blackout).
function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = false } = {}) {
  const content = POPUP_CONTENT[key];
  if (!content) return Promise.resolve();
  const run = async () => {
    const root = document.getElementById('gpop');
    const amountEl = document.getElementById('gpopAmount');
    document.getElementById('gpopTitle').textContent = content.title;
    document.getElementById('gpopSub').textContent = content.sub || '';
    root.dataset.tier = content.tier;
    amountEl.textContent = '0';
    // Big moments: the two heroes in the armchairs celebrate too.
    playSceneClip('hero_man', 'win');
    playSceneClip('hero_woman', 'win');
    if (content.tier === 'spins') playSceneClip('freespins', 'win');
    if (content.tier === 'mega' || content.tier === 'epic' || content.tier === 'total') {
      spawnBills(document.getElementById('gpopBills'));
    } else {
      document.getElementById('gpopBills').innerHTML = '';
    }

    if (ownDim) pushScreenDim(false);
    Sound.playSfx('popupOpen');
    root.hidden = false;
    void root.offsetWidth;
    root.classList.add('is-open');
    await countUp(amountEl, Number(amount) || 0, content.count ? 500 : POPUP_COUNT_MS, content.count);
    await wait(holdMs);
    Sound.playSfx('popupClose');
    root.classList.remove('is-open');
    await wait(DIM_TRANSITION_MS);
    root.hidden = true;
    if (ownDim) popScreenDim(false);
  };
  popupBusy = popupBusy.then(run, run);
  return popupBusy;
}

function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// Buy-bonus confirmation: resolves true on ✓, false on ✗ / backdrop.
function openBuyDialog(price) {
  const dlg = document.getElementById('buyDialog');
  document.getElementById('buyDialogPrice').textContent = Number(price).toLocaleString('en-US');
  dlg.hidden = false;
  void dlg.offsetWidth;
  dlg.classList.add('is-open');
  Sound.playSfx('popupOpen');
  return new Promise((resolve) => {
    const close = (answer) => {
      dlg.classList.remove('is-open');
      Sound.playSfx('popupClose');
      yes.removeEventListener('click', onYes);
      no.removeEventListener('click', onNo);
      dlg.removeEventListener('click', onBackdrop);
      setTimeout(() => { dlg.hidden = true; }, DIM_TRANSITION_MS);
      resolve(answer);
    };
    const yes = document.getElementById('buyYes');
    const no = document.getElementById('buyNo');
    const onYes = () => close(true);
    const onNo = () => close(false);
    const onBackdrop = (e) => { if (e.target === dlg) close(false); };
    yes.addEventListener('click', onYes);
    no.addEventListener('click', onNo);
    dlg.addEventListener('click', onBackdrop);
  });
}

// --- Dev panel --------------------------------------------------------------

const DEV_WHEEL_SEGMENTS = [2, 5, 3, 8, 4, 'fs', 2, 6, 3, 7, 4, 5, 'fs', 10].map((v) =>
  v === 'fs' ? { type: 'free_spins', value: null } : { type: 'multiplier', value: v },
);

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');
  toggleBtn.addEventListener('click', () => {
    const next = currentMode() === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 10);
    if (next === 'freespins') setFreeSpinsCounter(10);
    toggleBtn.textContent = `mode: ${next}`;
  });
  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.popup;
      playPopup(key, key === 'bonusSpinsWin' ? 10 : 1234500);
    });
  });
  document.getElementById('devBuy').addEventListener('click', () => openBuyDialog(10000000));
  document.getElementById('devWheel').addEventListener('click', () => {
    const idx = Math.floor(Math.random() * DEV_WHEEL_SEGMENTS.length);
    const seg = DEV_WHEEL_SEGMENTS[idx];
    playWheelOfFortune({
      segments: DEV_WHEEL_SEGMENTS,
      segment_index: idx,
      prize_type: seg.type === 'free_spins' ? 'free_spins' : 'multiplier',
      win_amount: seg.type === 'free_spins' ? '0' : String(seg.value * 100000),
    });
  });
  document.getElementById('devBigWild').addEventListener('click', () => previewBigWild(2, false));
  document.getElementById('devFeature').addEventListener('click', () => showFeatureScreen());
}

// --- Viewport / background --------------------------------------------------
//
// #stage is the PSB canvas (1932x940; portrait: 780x1416), contain-scaled. On
// desktop it is fitted to the PSB's SAFE width (its "1612x940" guide, widened
// to keep the buy chest whole) rather than the full 1932: the outer strips
// are background only, and the background is its own cover-scaled layer.
const DESIGN = { desktop: { w: 1932, h: 940, safeW: 1720 }, mobile: { w: 780, h: 1416, safeW: 780 } };

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function updateStageScale() {
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth || document.documentElement.clientWidth;
  const vh = screenEl.clientHeight || document.documentElement.clientHeight;
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  const scale = Math.min(vw / d.safeW, vh / d.h, 1.6);
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  document.documentElement.style.setProperty('--design-w', `${d.w}px`);
  document.documentElement.style.setProperty('--design-h', `${d.h}px`);
  readCellDims();
}

function bgSrcFor(mode) {
  const device = isMobileLayout() ? 'mob' : 'desk';
  return `${ASSET_ROOT}/bg_${mode === 'base' ? 'base' : 'bonus'}_${device}.jpg`;
}

function updateBgForLayout() {
  document.getElementById('bgLayer').src = bgSrcFor(currentMode());
}

function preloadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = img.onerror = () => resolve();
    img.src = src;
  });
}

// Everything the first screens need, counted into the boot preloader
// (js/preloader.js). Failures never block: a missing asset just counts done.
function preloadAssets() {
  const P = window.Preloader;
  const track = (promise) => {
    if (P) P.add(1);
    return Promise.resolve(promise)
      .catch((err) => console.warn('preload:', err))
      .finally(() => { if (P) P.step(); });
  };
  const tasks = [
    ...SYMBOL_CODES.map(symbolSrc),
    `${SYMBOL_ROOT}/wild_big.png`,
    bgSrcFor('base'),
    bgSrcFor('bonus'),
    ...['frame.png', 'logo.png', 'buy_bonus.png', 'fs_counter.png', 'fs_shadow.png', 'plate.png', 'chest.png',
      'buy_title.png', 'wof_wheel.png', 'wof_of_fortune.png', 'scene_people.png'].map((f) => `${ASSET_ROOT}/ui/${f}`),
  ].map((src) => track(preloadImage(src)));
  if (stage) {
    // Skeletons up front so the first win doesn't wait on a fetch.
    for (const code of SYMBOL_CODES) tasks.push(track(getSymbolResource(code)));
    tasks.push(track(getSymbolResource(FEATURE_SCREEN_CODE)));
    if (LAND_ENABLED) for (const code of SYMBOL_CODES) tasks.push(track(getLandResource(code)));
  }
  if (backStage) {
    for (const name of SCENE_NAMES) if (SCENE_ON.has(name)) tasks.push(track(getSceneResource(name)));
  }
  return Promise.all(tasks);
}

// --- Living scene (spine pack "gangsta_spine_фоны") --------------------------
//
// background (terrace, palms, sun, water glints), the two heroes in their
// armchairs, the reel frame (chrome + glass, shine sweep), the logo and the
// Free Spins counter. All drawn on #spineBackCanvas, which sits UNDER #stage:
// the frame art includes the dark glass of the opening, so it has to be below
// the symbols (it is in the PSB too). The static PNG/CSS versions stay in the
// DOM as the fallback and are hidden by .screen.has-spine-scene.
//
// Placement is the pack's layout.json, in PSB scene px (y down): every
// skeleton's own box is pinned to an anchor div at the same design coords
// with fit 1, so 1 skeleton unit = 1 design px. Frame / logo / counter are
// anchored to the elements they replace instead, so they also follow the
// portrait layout. Background + heroes are the desktop terrace — off in
// portrait and in the bonus (the club background is a still).

const SCENE_ROOT = `${SPINE_ROOT}/scene`;
const LAND_ROOT = `${SPINE_ROOT}/land`;
const SCENE_NAMES = ['background', 'hero_man', 'hero_woman', 'frame', 'freespins', 'logo'];
// What actually runs (product, 2026-10-10: background, frame and logo live;
// the heroes are being redrawn, so the PSB's still people stand in for them —
// .scene-people in #stage; the counter and the sym_* land bounce stay off
// until asked for). Add a name back here to switch that part on.
const SCENE_ON = new Set(['background', 'frame', 'logo']);
const LAND_ENABLED = false;
// root_scene_x/y from layout.json (PSB px, y down).
const SCENE_ROOTS = {
  background: [966, 470.5],
  hero_man: [279.5, 955],
  hero_woman: [1614.5, 954],
};
let backStage = null;
const scene = {}; // name -> SpineInstance

function getSceneResource(name) {
  if (!backStage) return Promise.reject(new Error('no back stage'));
  // README: "без premultiplied alpha" — and no pma line in the atlases.
  return SpineEngine.SpineResource.load(backStage.assetManager, `${SCENE_ROOT}/${name}`, { premultipliedAlpha: false });
}

function sceneAnchorAt(name, resource) {
  const { x, y, width, height } = resource.bounds;
  const [rx, ry] = SCENE_ROOTS[name];
  const el = document.createElement('div');
  el.className = 'scene-anchor';
  el.style.left = `${rx + x}px`;
  el.style.top = `${ry - (y + height)}px`;
  el.style.width = `${width}px`;
  el.style.height = `${height}px`;
  document.getElementById('stage').appendChild(el);
  return el;
}

function sceneAnchorFor(name, resource) {
  if (SCENE_ROOTS[name]) return sceneAnchorAt(name, resource);
  if (name === 'frame') return document.getElementById('reelRig');
  if (name === 'logo') return document.querySelector('.stage--front .logo');
  // freespins: the counter skeleton's box is the PSB "Free Spins" group, i.e.
  // the jukebox plus its shadow — 68px left of .fs-counter, 384x311.
  const el = document.createElement('div');
  el.className = 'fs-counter__anchor';
  document.getElementById('freeSpinsCounter').prepend(el);
  return el;
}

async function setupScene() {
  if (!backStage) return;
  try {
    for (const name of SCENE_NAMES) {
      if (!SCENE_ON.has(name)) continue;
      const resource = await getSceneResource(name);
      resource.animationStateData.defaultMix = 0.2; // README recommendation
      const inst = resource.createInstance();
      inst.anchorEl = sceneAnchorFor(name, resource);
      inst.boundsOverride = resource.bounds;
      inst.fit = 1;
      inst.play('idle', true);
      // Desync the two heroes' breathing.
      if (name === 'hero_woman') inst.animationState.getCurrent(0).trackTime = 3.1;
      scene[name] = inst;
    }
  } catch (err) {
    console.warn('spine scene failed, keeping the static one:', err);
    for (const k of Object.keys(scene)) delete scene[k];
    return;
  }
  const screenEl = document.getElementById('screen');
  screenEl.classList.add('has-spine-scene');
  // Per-part flags: each hides only the static it replaces.
  for (const name of Object.keys(scene)) screenEl.classList.add(`has-spine-${name}`);
  syncScene();
}

// Which scene skeletons are on the canvas for the current mode / orientation.
// Rebuilt in SCENE_NAMES order every time — that order is the draw order.
function syncScene() {
  if (!backStage || !Object.keys(scene).length) return;
  const portrait = isMobileLayout();
  const bonus = currentMode() === 'freespins';
  const want = {
    background: !portrait && !bonus,
    hero_man: !portrait && !bonus,
    hero_woman: !portrait && !bonus,
    frame: true,
    freespins: bonus,
    logo: true,
  };
  document.getElementById('screen').classList.toggle('has-spine-terrace', want.background && !!scene.background);
  // Still people over the live terrace while the hero skeletons are off.
  document.getElementById('screen').classList.toggle('has-still-people', want.background && !!scene.background && !scene.hero_man);
  for (const name of SCENE_NAMES) if (scene[name]) backStage.removeBase(scene[name]);
  for (const name of SCENE_NAMES) if (want[name] && scene[name]) backStage.addBase(scene[name]);
}

// One-shot reaction, then back to the idle loop.
function playSceneClip(name, clip) {
  const inst = scene[name];
  if (!inst || !inst.resource.skeletonData.findAnimation(clip)) return;
  inst.play(clip, false);
  inst.queue('idle', true, 0);
}

// --- Feature (preview) screen -----------------------------------------------
//
// Spine export "pfs" (gangsta_feature_screen): `intro` (3s) then `idle`
// (looped). Authored on the desktop PSB canvas — skeleton origin = canvas
// centre, 1 unit = 1 design px — so on desktop it is anchored to #stage itself
// with a 1932x940 box and lands exactly on the game layout (its man/woman sit
// where the background's do). Portrait just contain-fits that box to the
// screen. Closed by a click: the whole screen fades out to transparent.

const FEATURE_SCREEN_CODE = 'feature_screen';
const FEATURE_BOX = { x: -966, y: -470, width: 1932, height: 940 };
const FEATURE_FADE_MS = 500;

function showFeatureScreen() {
  const root = document.getElementById('featureScreen');
  if (!stage || !root) return Promise.resolve();
  return getSymbolResource(FEATURE_SCREEN_CODE).then((resource) => new Promise((resolve) => {
    const inst = resource.createInstance();
    const place = () => {
      const portrait = isMobileLayout();
      inst.anchorEl = portrait ? root : document.getElementById('stage');
      inst.fit = 1;
    };
    place();
    inst.boundsOverride = FEATURE_BOX;
    window.addEventListener('resize', place);

    document.body.classList.add('is-feature-screen');
    root.hidden = false;
    void root.offsetWidth;
    root.classList.add('is-open');
    stage.addOverlay(inst);
    inst.play('intro', false);
    inst.queue('idle', true);

    let closing = false;
    const close = () => {
      if (closing) return;
      closing = true;
      root.removeEventListener('click', close);
      Sound.playSfx('click');
      // Plain fade-out: skeleton alpha and the dim go to 0 together; the
      // clip keeps playing underneath so nothing freezes mid-fade.
      root.style.transition = `opacity ${FEATURE_FADE_MS}ms ease-out`;
      root.classList.remove('is-open');
      const start = performance.now();
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        stage.removeOverlay(inst);
        window.removeEventListener('resize', place);
        root.hidden = true;
        root.style.transition = '';
        document.body.classList.remove('is-feature-screen');
        resolve();
      };
      const tick = (now) => {
        if (done) return;
        const t = Math.min(1, (now - start) / FEATURE_FADE_MS);
        inst.skeleton.color.a = 1 - t;
        if (t < 1) requestAnimationFrame(tick);
        else finish();
      };
      requestAnimationFrame(tick);
      setTimeout(finish, FEATURE_FADE_MS + 200); // hidden tab: rAF frozen
    };
    root.addEventListener('click', close);
  })).catch((err) => {
    console.warn('feature screen failed:', err);
  });
}

function init() {
  Sound.playMusic('base');
  updateStageScale();
  updateBgForLayout();
  window.addEventListener('resize', () => {
    updateStageScale();
    updateBgForLayout();
    syncScene();
  });
  buildReelGrid();
  try {
    stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
    backStage = new SpineEngine.SpineStage(document.getElementById('spineBackCanvas'));
  } catch (err) {
    console.warn('Spine stage unavailable — symbols fall back to CSS:', err);
    stage = null;
    backStage = null;
  }
  setupDevPanel();
  preloadAssets().then(() => {
    setupScene();
    if (window.Preloader) window.Preloader.done();
    // ?nofs — dev/screenshot convenience: straight into the game.
    if (new URLSearchParams(location.search).has('nofs')) {
      document.getElementById('preloader')?.remove();
      return null;
    }
    return showFeatureScreen();
  });
  window.__slot = { get cellInfos() { return cellInfos; }, get stage() { return stage; } };
}

init();
