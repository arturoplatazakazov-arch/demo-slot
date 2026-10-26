// Gangsta Casino — game-specific wiring. Layout comes from the designer's PSB
// (Desk_Gangsta_Slot_OUT, 1932x940); mechanics are Dirty Money / MAFIA's
// (../dirty-money-mafia/slot.js): 5x3 line pay, expanding + walking wild,
// scatter free spins, multipliers (the `wof` chip), bonus buy.
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
  // Pre-blurred twin shown while the reel runs fast (.reel__strip.is-fast):
  // a per-frame SVG/CSS blur filter on the whole strip was the main cost of
  // a spin on phones. Lazy — only decoded when it's actually shown.
  const blur = document.createElement('img');
  blur.className = 'reel__cell-blur';
  blur.alt = '';
  blur.decoding = 'async';
  blur.src = `${SYMBOL_ROOT}/blur/${SYMBOL_ART[code]}`;
  blur.draggable = false;
  cell.appendChild(blur);
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
  // Win lines live UNDER the columns (first child, columns paint over it) —
  // behind the symbols, product: "за сыгравшими элементами".
  inner.appendChild(createWinLinesLayer());

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
  clearWinLines();
  clearMultiplierBadges();
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

// On a phone link a page image sometimes just fails (connection reset while
// ~20 MB is in flight) — and both the engine's resource cache and the asset
// manager remember the failure under that path for good. Retry under an
// equivalent path ("<dir>/." is the same folder, but a fresh cache key), with
// a short pause, a couple of times.
const spineRetryCache = new Map();
function loadSpineWithRetry(assetManager, folder, opts, tries = 3) {
  const key = `${folder}|${opts.premultipliedAlpha}|${opts.skeleton || ''}`;
  if (spineRetryCache.has(key)) return spineRetryCache.get(key);
  const attempt = (n, path) => SpineEngine.SpineResource.load(assetManager, path, opts).catch((err) => {
    if (n + 1 >= tries) throw err;
    console.warn(`spine retry ${n + 1} for ${folder}:`, err && err.message);
    return wait(700 * (n + 1)).then(() => attempt(n + 1, `${path}/.`));
  });
  const promise = attempt(0, folder);
  spineRetryCache.set(key, promise);
  return promise;
}

function getSymbolResource(code) {
  if (!stage) return Promise.reject(new Error('no spine stage'));
  // Atlases are true premultiplied alpha (pma:true, RGB <= A in every pixel).
  return loadSpineWithRetry(stage.assetManager, `${SPINE_ROOT}/${code}`, { premultipliedAlpha: true });
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
  const dim = dimmed && !multLitCells.has(info);
  info.cell.classList.toggle('is-dimmed', dim);
  const chip = multChips.find((m) => m.info === info && m.inst);
  if (chip) chip.inst.skeleton.color.set(dim ? 0.4 : 1, dim ? 0.4 : 1, dim ? 0.4 : 1, 1);
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
    if (groupIndex === -1) showWinLines(currentLineWins);
    else showWinLines(currentLineWins[groupIndex] ? [currentLineWins[groupIndex]] : []);
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

// --- Win lines (Spine, under the symbols) -----------------------------------
//
// One generated skeleton (scripts/gangsta_casino_winlines.py) holds all 11
// paylines (shapes = the seed's PAYLINES, indexed by the server's 1-based
// `payline`): straight glow + core beams per segment with a round joint at
// every bend, additive and tinted per line, clipped to the glass. `line{n}_in`
// draws it on, `line{n}_loop` pulses it with a comet running along. It plays
// on the BACK canvas (over the frame's glass, under the DOM symbols and the
// win clips on the top canvas) — product: "за сыгравшими элементами". Each
// shown line runs on its own track of one instance; nothing is drawn by the
// lines while none are shown. Turn it off with WIN_LINES_ENABLED.
const WIN_LINES_ENABLED = true;
const WIN_LINES_CODE = 'winlines';
const WIN_LINES_STAGGER_S = 0.09;
let winLinesAnchor = null;
let winLinesInst = null; // SpineInstance, on backStage only while lines show
let winLinesShown = false;
let currentLineWins = [];

function createWinLinesLayer() {
  const el = document.createElement('div');
  el.className = 'win-lines';
  winLinesAnchor = el;
  return el;
}

function getWinLinesInstance() {
  if (winLinesInst) return Promise.resolve(winLinesInst);
  if (!backStage) return Promise.reject(new Error('no back stage'));
  return loadSpineWithRetry(backStage.assetManager, `${SPINE_ROOT}/${WIN_LINES_CODE}`, { premultipliedAlpha: false })
    .then((resource) => {
      if (winLinesInst) return winLinesInst;
      const inst = resource.createInstance();
      const w = GRID_COLS * 197, h = GRID_ROWS * 200; // skeleton units = design grid px
      inst.boundsOverride = { x: -w / 2, y: -h / 2, width: w, height: h };
      inst.fit = 1;
      winLinesInst = inst;
      return inst;
    });
}

function clearWinLines() {
  winLinesShown = false;
  if (!winLinesInst) return;
  winLinesInst.animationState.clearTracks();
  winLinesInst.skeleton.setToSetupPose();
  if (backStage) backStage.removeOverlay(winLinesInst);
}

function showWinLines(lineWins) {
  clearWinLines();
  if (!WIN_LINES_ENABLED || !backStage || !winLinesAnchor) return;
  const lines = (lineWins || []).map((w) => w.payline).filter((n) => n >= 1 && n <= 11);
  if (!lines.length) return;
  winLinesShown = true;
  const epoch = winSequenceEpoch;
  getWinLinesInstance().then((inst) => {
    if (!winLinesShown || epoch !== winSequenceEpoch) return;
    inst.anchorEl = winLinesAnchor;
    // Lines run frame to frame: cut at this layout's chrome inner edge.
    inst.skeleton.setAttachment('clip', isMobileLayout() ? 'clip_mob' : 'clip_desk');
    const state = inst.animationState;
    lines.forEach((n, i) => {
      const entry = i ? state.addAnimation(i, `line${n}_in`, false, i * WIN_LINES_STAGGER_S) : state.setAnimation(i, `line${n}_in`, false);
      entry.mixDuration = 0;
      state.addAnimation(i, `line${n}_loop`, true, 0).mixDuration = 0;
    });
    backStage.removeOverlay(inst);
    backStage.addOverlay(inst);
  }).catch((err) => console.warn('win lines:', err));
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
    for (const name of ['frame', 'frame_mob', 'logo', 'logo_mob']) playSceneClip(name, 'win');
  }
  // A grown wild column celebrates along with its line.
  for (const el of bigWildEls) {
    const col = Number(el.dataset.col);
    const winning = allWinInfos.some((i) => cellInfos.indexOf(i) % GRID_COLS === col);
    el.classList.toggle('is-winning', winning);
    if (el.__overlay && winning) el.__overlay.play('win_big', true);
  }

  const groups = buildWinGroups(lineWins, countWins);
  // Line i of the sequence == lineWins[i] (count wins come after them).
  currentLineWins = lineWins || [];
  showWinLines(currentLineWins);
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


// Reel motion modelled on the studio's own engine (Uniqorn Wild Western Story
// reels config): every reel starts together and accelerates to MAX_SPEED
// px/frame (60 fps units, cell = 200 design px — same units as ours); once
// the result is in, reel i runs i * NEXT_REEL_DELAY_FIGURES extra symbols
// before its result (the stagger), brakes over the last cell
// (STOPPING_DISTANCE) and stops dead on it — no bounce. A reel in
// anticipation runs SUSPENDED_FIGURES extra.
//
// Everything is played as Web Animations on `transform`, i.e. on the
// compositor: a rAF loop moving the strips on the main thread stuttered and
// froze on phones, where the main thread is busy skinning the two Spine
// scenes every frame. JS only touches the DOM at start and at each stop.
const REEL_PHYS = {
  MAX_SPEED: 55,
  NEXT_REEL_DELAY_FIGURES: 2,
  SUSPENDED_FIGURES: 24,
  STOPPING_DISTANCE: 200,
  LOOP_CELLS: 6,      // free-spin loop period
  ACCEL_CELLS: 3,     // distance of the ease-in start
};
const REEL_SPEED = REEL_PHYS.MAX_SPEED * 60 / 1000; // design px per ms (3.3)
const EASE_IN_QUAD = 'cubic-bezier(0.55, 0.085, 0.68, 0.53)';
const EASE_OUT_QUAD = 'cubic-bezier(0.25, 0.46, 0.45, 0.94)';
const reelState = []; // per column: { stripEl, anim, stopping }

function currentStripY(stripEl) {
  const m = new DOMMatrixReadOnly(getComputedStyle(stripEl).transform);
  return m.m42;
}

function animateStrip(st, frames, opts) {
  if (st.anim) st.anim.cancel();
  st.anim = st.stripEl.animate(frames, { fill: 'forwards', ...opts });
  return st.anim;
}

const reelMotion = {
  startLoop() {
    Sound.playSfx('spinStart');
    const rs = rowStep, L = REEL_PHYS.LOOP_CELLS;
    for (let col = 0; col < GRID_COLS; col++) {
      const { stripEl } = reelCols[col];
      const prev = reelState[col];
      if (prev && prev.anim) prev.anim.cancel();
      stripEl.style.transition = 'none';
      stripEl.classList.remove('is-looping', 'is-fast');
      const current = ReelMath.currentColumnCodes(cellInfos, GRID_COLS, GRID_ROWS, col).map((c) => c || randomSymbolCode());
      const loop = Array.from({ length: L }, randomSymbolCode);
      // [loop, loop again, current]: the window starts on `current`, the
      // ease-in brings the second loop copy in, then a seamless linear loop.
      stripEl.innerHTML = '';
      for (const code of [...loop, ...loop, ...current]) stripEl.appendChild(createCellNode(code).cell);
      const y0 = -2 * L * rs;
      const yLoop = y0 + REEL_PHYS.ACCEL_CELLS * rs;
      stripEl.style.transform = `translateY(${y0}px)`;
      const st = { stripEl, anim: null, stopping: false };
      reelState[col] = st;
      const accelMs = (2 * REEL_PHYS.ACCEL_CELLS * rs) / REEL_SPEED; // ease-in quad ends at full speed
      const a = animateStrip(st, [{ transform: `translateY(${y0}px)` }, { transform: `translateY(${yLoop}px)` }],
        { duration: accelMs, easing: EASE_IN_QUAD });
      st.fastTimer = setTimeout(() => stripEl.classList.add('is-fast'), accelMs * 0.4);
      a.onfinish = () => {
        if (st.stopping || reelState[col] !== st) return;
        // seamless: at yLoop and at yLoop + L*rs the window shows the same cells
        animateStrip(st, [{ transform: `translateY(${yLoop}px)` }, { transform: `translateY(${yLoop + L * rs}px)` }],
          { duration: (L * rs) / REEL_SPEED, iterations: Infinity, easing: 'linear' });
      };
    }
  },
  stopLoop() {
    // Error path: put the last known grid cells back, no motion.
    for (let col = 0; col < GRID_COLS; col++) {
      const st = reelState[col];
      if (st) { st.stopping = true; clearTimeout(st.fastTimer); if (st.anim) st.anim.cancel(); }
      const { stripEl } = reelCols[col];
      stripEl.classList.remove('is-fast');
      stripEl.style.transform = 'translateY(0px)';
      stripEl.innerHTML = '';
      for (let row = 0; row < GRID_ROWS; row++) {
        const info = cellInfos[row * GRID_COLS + col];
        if (info) stripEl.appendChild(info.cell);
      }
    }
  },
  // Resolves with the 3 result cells once the reel has stopped on them.
  landReel(col, finalCodes, extraFigures = 0, isAnticipating = false) {
    const st = reelState[col];
    const rs = rowStep;
    return new Promise((resolve) => {
      st.stopping = true;
      const { stripEl } = st;
      let y = currentStripY(stripEl);
      if (st.anim) st.anim.cancel();
      // Trim the queued symbols above the window to one, so every reel's run
      // to its result is exactly its extra figures long (deterministic
      // left-to-right stop order).
      while (Math.floor(-y / rs) > 1 && stripEl.firstChild) { stripEl.firstChild.remove(); y += rs; }
      // Drop what's below the window.
      const below = () => (stripEl.children.length - 1) * rs + y > 4 * rs;
      while (stripEl.children.length > 4 && below()) stripEl.lastChild.remove();
      const extra = Array.from({ length: extraFigures + (isAnticipating ? REEL_PHYS.SUSPENDED_FIGURES : 0) }, randomSymbolCode);
      // top -> bottom: 1 filler above the result, the result, then the extra run
      const codes = [randomSymbolCode(), ...finalCodes, ...extra];
      const frag = document.createDocumentFragment();
      const made = codes.map((code) => createCellNode(code).cell);
      for (const c of made) frag.appendChild(c);
      stripEl.insertBefore(frag, stripEl.firstChild);
      y -= codes.length * rs;
      const resultCells = made.slice(1, 4);
      const yStop = -1 * rs; // result row 0 at the window top
      const dist = yStop - y;
      const brake = Math.min(REEL_PHYS.STOPPING_DISTANCE, dist);
      const runMs = Math.max(0, (dist - brake) / REEL_SPEED);
      const brakeMs = (2 * brake) / REEL_SPEED; // ease-out quad starts at full speed
      const total = runMs + brakeMs;
      stripEl.style.transform = `translateY(${y}px)`;
      st.anim = stripEl.animate([
        { transform: `translateY(${y}px)`, offset: 0, easing: 'linear' },
        { transform: `translateY(${yStop - brake}px)`, offset: total ? runMs / total : 0, easing: EASE_OUT_QUAD },
        { transform: `translateY(${yStop}px)`, offset: 1 },
      ], { duration: total, fill: 'forwards' });
      clearTimeout(st.fastTimer);
      stripEl.classList.add('is-fast');
      st.fastTimer = setTimeout(() => stripEl.classList.remove('is-fast'), runMs + brakeMs * 0.35);
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        clearTimeout(st.fastTimer);
        stripEl.classList.remove('is-fast');
        if (st.anim) st.anim.cancel();
        st.anim = null;
        Sound.playSfx(col === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop');
        if (isAnticipating) reelCols[col].colEl.classList.remove('is-anticipating');
        stripEl.innerHTML = '';
        for (const c of resultCells) stripEl.appendChild(c);
        stripEl.style.transform = 'translateY(0px)';
        resolve(resultCells);
      };
      st.anim.onfinish = finish;
      setTimeout(finish, total + 1200); // hidden tab: animations may not finish
    });
  },
};

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
      landReel(col, finalCodes, col * REEL_PHYS.NEXT_REEL_DELAY_FIGURES, false)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes))
        .then(() => celebrateExpandedWild(col, wildEvents, winningCols)),
    );
  }
  await Promise.all(leadTasks);
  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');
  // The remaining reels keep spinning; they stop one at a time.
  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const isAnticipating = anticipationSet.has(col);
    if (isAnticipating) reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, REEL_PHYS.NEXT_REEL_DELAY_FIGURES, isAnticipating);
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
  // A round's multiplier starts at x1 and is gone with the round.
  if (currentMode() !== next) resetMultiplierPlate();
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
  syncScene();
}

const BONUS_INTRO_HOLD_MS = 3000;

// Entering the bonus: blackout, then the Spine bonus screen (bfs) with the
// real spin count — it waits for the player's tap ("TAP TO START") and the
// club is switched in behind it. Without Spine, the CSS "YOU WON" card.
async function enterBonusTransition(amount = 0) {
  pushScreenDim(true);
  await wait(DIM_TRANSITION_MS);
  applyModeScreen('freespins');
  const ran = await showBonusScreen(amount);
  if (!ran) await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS);
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

// --- Multipliers (the `wof` chip) ------------------------------------------
//
// Product 2026-10-20: no wheel any more — the chip is a MULTIPLIER (designer's
// art from Desk_Gangsta_Slot_F.psb, 2026-10-25). The value is drawn server-side
// (`coin_multiplier.positions`); the reel tile is the empty chip, and after
// the reels land each chip plays the Spine `landing` (the value flips in,
// 0.7 s, skin val_<n>) and holds on it; a chip that counts plays `win` and
// its value flies into the plate. The plate (#multPlate) is the interface
// element: base game = the spin's sum when it multiplies a line win, free
// spins = the round total, which only grows until the round ends.
const MULT_REVEAL_MS = 700;
const MULT_FLY_MS = 520;
const MULT_UI = `${ASSET_ROOT}/ui`;
const MULT_ART = [2, 3, 5, 7, 9];           // values the art exists for
let multChips = [];                         // { info, inst, value, el }
const multLitCells = new Set(); // multiplier cells kept bright over the win dim

function multArt(value) {
  return MULT_ART.includes(value) ? value : null;
}

function getMultiplierResource() {
  if (!stage) return Promise.reject(new Error('no spine stage'));
  return loadSpineWithRetry(stage.assetManager, `${SPINE_ROOT}/multiplier`, { premultipliedAlpha: false });
}

function clearMultiplierBadges() {
  for (const m of multChips) {
    if (m.inst && stage) stage.removeBase(m.inst);
    if (m.el) m.el.remove();
    if (m.info.img && m.info.cell.isConnected) m.info.img.style.visibility = '';
  }
  multChips = [];
  multLitCells.clear();
}

// Spine chip over the cell (falls back to the value art laid over the tile).
async function createMultiplierChip(info, value) {
  const m = { info, value, inst: null, el: null };
  try {
    const res = await getMultiplierResource();
    const inst = res.createInstance();
    inst.anchorEl = info.anchor;
    inst.boundsOverride = TILE_BOX;
    inst.fit = TILE_FIT;
    const art = multArt(value) || 3;
    inst.skeleton.setSkinByName(`val_${art}`);
    inst.skeleton.setSlotsToSetupPose();
    inst.play('landing', false);
    stage.addBase(inst);
    info.img.style.visibility = 'hidden';
    m.inst = inst;
  } catch (err) {
    const el = document.createElement('img');
    el.className = 'mult-chip-value';
    el.src = `${MULT_UI}/mult_chip_x${multArt(value) || 3}.png`;
    info.cell.appendChild(el);
    m.el = el;
  }
  multChips.push(m);
  return m;
}

// Every landed multiplier flips its value in, all at once.
async function revealMultipliers(positions) {
  const list = (positions || []).map((p) => ({ p, info: cellInfos[p.row * GRID_COLS + p.col] }))
    .filter(({ info }) => info && info.symbol === 'wof');
  if (!list.length) return [];
  const shown = await Promise.all(list.map(({ p, info }) => createMultiplierChip(info, p.value)));
  Sound.playSfx('wildWin');
  await wait(MULT_REVEAL_MS);
  return shown;
}

// The plate: the art + its value as gold text (round totals add up).
function setMultiplierPlate(value, { lit = false, bump = false } = {}) {
  const plate = document.getElementById('multPlate');
  if (!plate) return;
  // always text: in free spins the values add up (x17, x33 …)
  const box = document.getElementById('multPlateValue');
  box.innerHTML = `<span>x${value}</span>`;
  plate.classList.toggle('is-lit', lit);
  if (bump) {
    box.classList.remove('is-bump');
    void box.offsetWidth; // restart the keyframes
    box.classList.add('is-bump');
  }
}

// A copy of each value flies from its chip into the plate.
function flyMultipliersToPlate(shown) {
  const plate = document.getElementById('multPlateValue');
  if (!plate || !shown.length) return Promise.resolve();
  const to = plate.getBoundingClientRect();
  return Promise.all(shown.map(({ info, value }, i) => {
    const r = info.anchor.getBoundingClientRect();
    const k = r.width / 200; // stage scale
    const fly = document.createElement('img');
    fly.className = 'mult-fly';
    fly.src = `${MULT_UI}/mult_chip_x${multArt(value) || 3}.png`;
    fly.style.left = `${r.left + r.width / 2}px`;
    fly.style.top = `${r.top + r.height / 2}px`;
    fly.style.height = `${62 * k}px`;
    document.body.appendChild(fly);
    const dx = to.left + to.width / 2 - (r.left + r.width / 2);
    const dy = to.top + to.height / 2 - (r.top + r.height / 2);
    const anim = fly.animate([
      { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
      { transform: `translate(calc(-50% + ${dx * 0.5}px), calc(-50% + ${dy * 0.5 - 60}px)) scale(1.4)`, opacity: 1, offset: 0.45 },
      { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(0.8)`, opacity: 0.9 },
    ], { duration: MULT_FLY_MS, delay: i * 90, easing: 'cubic-bezier(0.45, 0, 0.35, 1)', fill: 'both' });
    return anim.finished.catch(() => {}).then(() => fly.remove());
  }));
}

// The whole step, between the landing and the win presentation.
// inRound: this spin was played inside a free-spins round.
async function playMultipliers(cm, inRound) {
  if (!cm) return;
  const shown = await revealMultipliers(cm.positions);
  const counts = inRound ? shown.length > 0 : cm.applied;
  if (counts) {
    for (const m of shown) {
      multLitCells.add(m.info);
      if (m.inst) m.inst.play('win', false);
    }
    await flyMultipliersToPlate(shown);
  }
  if (inRound && cm.round_multiplier != null) {
    setMultiplierPlate(cm.round_multiplier, { lit: cm.round_multiplier > 1, bump: counts || cm.applied });
  } else if (cm.applied) {
    setMultiplierPlate(cm.multiplier_sum, { lit: true, bump: true });
  }
}

// A base-game spin starts from x1; a round keeps its total.
function resetMultiplierPlate() {
  setMultiplierPlate(1);
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
    if (SPINE_POPUPS[key] && stage) {
      for (const name of ['hero_man', 'hero_woman', 'hero_man_mob', 'hero_woman_mob']) playSceneClip(name, 'win');
      if (content.tier === 'spins') playSceneClip('freespins', 'win');
      if (ownDim) pushScreenDim(false);
      Sound.playSfx('popupOpen');
      const done = await runSpinePopup(SPINE_POPUPS[key], async (inst, pin) => {
        const el = document.createElement('div');
        el.className = `spop-amount${content.count ? ' spop-amount--count' : ''}`;
        el.textContent = '0';
        pin(el, content.count ? 'count' : 'amount', content.count ? 150 : 82);
        await wait(450);
        await countUp(el, Number(amount) || 0, content.count ? 500 : POPUP_COUNT_MS, content.count);
        await wait(holdMs);
        Sound.playSfx('popupClose');
      });
      if (ownDim) popScreenDim(false);
      if (done) return;
    }
    const root = document.getElementById('gpop');
    const amountEl = document.getElementById('gpopAmount');
    document.getElementById('gpopTitle').textContent = content.title;
    document.getElementById('gpopSub').textContent = content.sub || '';
    root.dataset.tier = content.tier;
    amountEl.textContent = '0';
    // Big moments: the two heroes in the armchairs celebrate too.
    for (const name of ['hero_man', 'hero_woman', 'hero_man_mob', 'hero_woman_mob']) playSceneClip(name, 'win');
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

// --- Spine popups (designer's PSB Desk_Gangsta_Slot_F, 2026-10-25) --------
//
// img/gangsta-casino/spine/popups/<slug> (scripts/gc_popups_spine.py): clips
// intro → idle (loop) → outro. Their own 70 % dim slot is switched off — the
// game's screen dim does that job in both layouts. The amount / spin count is
// DOM text pinned every frame to the skeleton's `amount` / `count` bone (its
// scale 0 → 1 in intro, → 0 in outro). The DOM cards stay as the fallback.
const SPINE_POPUPS = {
  bigWin: 'big_win', megaWin: 'mega_win', epicWin: 'epic_win',
  bonusSpinsWin: 'bonus_spins_win', bonusSpinsTotalWin: 'bonus_spins_total_win', buy: 'buy_free_spins',
};
const POPUP_BOX_MOB = { x: -500, y: -470, width: 1000, height: 940 }; // the popup art, not the whole 1932
const POPUP_OUT_S = 0.5;

function getPopupResource(slug) {
  if (!stage) return Promise.reject(new Error('no spine stage'));
  // one atlas shared by all popups (spine/popups/animation.atlas), a skeleton per popup
  return loadSpineWithRetry(stage.assetManager, `${SPINE_ROOT}/popups`, { premultipliedAlpha: false, skeleton: slug });
}

// screen px of a bone + its world scale in CSS px per skeleton unit
function boneOnScreen(inst, name) {
  const b = inst.skeleton.findBone(name);
  if (!b) return null;
  const canvas = document.getElementById('spineCanvas');
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  return {
    x: r.left + (b.worldX + canvas.width / 2) / dpr,
    y: r.top + (canvas.height / 2 - b.worldY) / dpr,
    s: b.getWorldScaleX() / dpr,
  };
}

// Opens a Spine popup; `body(inst, pin)` runs while it is up and decides when it
// closes (resolve). pin(el, bone, heightPx) keeps a DOM element on a bone.
async function runSpinePopup(slug, body) {
  let res;
  try { res = await getPopupResource(slug); } catch (err) { console.warn('popup', slug, err); return null; }
  const inst = res.createInstance();
  const portrait = isMobileLayout();
  inst.anchorEl = document.getElementById('stage');
  inst.boundsOverride = portrait ? POPUP_BOX_MOB : FEATURE_BOX;
  inst.fit = 1;
  for (const slot of inst.skeleton.slots) {
    if (slot.attachment && slot.attachment.name === 'black') slot.setAttachment(null);
  }
  const pins = [];
  const pin = (el, bone, h) => { document.body.appendChild(el); pins.push({ el, bone, h }); };
  let live = true;
  const follow = () => {
    if (!live) return;
    for (const p of pins) {
      const o = boneOnScreen(inst, p.bone);
      if (!o) continue;
      p.el.style.left = `${o.x}px`;
      p.el.style.top = `${o.y}px`;
      if (p.h) p.el.style.fontSize = `${Math.max(0, p.h * o.s)}px`;
      p.el.style.setProperty('--s', o.s);
      p.el.style.opacity = o.s > 0.02 ? '' : '0';
    }
    requestAnimationFrame(follow);
  };
  // swallow clicks on the game underneath while the popup is up
  const blocker = document.createElement('div');
  blocker.className = 'spop-block';
  document.body.appendChild(blocker);
  document.body.classList.add('is-spine-popup');
  stage.addOverlay(inst);
  inst.play('intro', false);
  inst.queue('idle', true);
  requestAnimationFrame(follow);
  const outcome = await body(inst, pin);
  inst.play('outro', false);
  await wait(POPUP_OUT_S * 1000 + 40);
  live = false;
  stage.removeOverlay(inst);
  for (const p of pins) p.el.remove();
  blocker.remove();
  document.body.classList.remove('is-spine-popup');
  return { value: outcome };
}

function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// Buy-bonus confirmation: resolves true on ✓, false on ✗ / backdrop / Escape.
// `note` is a small line under the price ("BET a → b" when the bet had to be
// lowered — js/buy-bonus.js); `affordable: false` turns the card into a
// NOT ENOUGH BALANCE notice with only ✗.
function openBuyDialog(price, opts = {}) {
  if (!stage) return openBuyDialogDom(price, opts);
  const { note = '', affordable = true } = opts;
  pushScreenDim(false);
  Sound.playSfx('popupOpen');
  return runSpinePopup(SPINE_POPUPS.buy, (inst, pin) => new Promise((resolve) => {
    const el = document.createElement('div');
    el.className = `spop-amount spop-amount--price${affordable ? '' : ' is-notice'}`;
    el.innerHTML = affordable ? `${Number(price).toLocaleString('en-US')}${note ? `<small>${note}</small>` : ''}` : 'NOT ENOUGH BALANCE';
    pin(el, 'amount', affordable ? 62 : 40);
    if (!affordable) inst.skeleton.findSlot('accept').setAttachment(null);
    // invisible hit areas over the art's ✓ / ✗ (they follow the bones)
    const hit = (bone, label) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'spop-hit';
      b.setAttribute('aria-label', label);
      const a = inst.skeleton.getAttachmentByName(bone, bone);
      b.style.setProperty('--w', a ? a.width : 300);
      b.style.setProperty('--h', a ? a.height : 95);
      pin(b, bone, 0);
      return b;
    };
    const yes = affordable ? hit('accept', 'Купить') : null;
    const no = hit('decline', 'Отмена');
    const finish = (answer) => {
      document.removeEventListener('keydown', onKey);
      Sound.playSfx(answer ? 'click' : 'popupClose');
      resolve(answer && affordable);
    };
    const onKey = (e) => { if (e.key === 'Escape') finish(false); };
    document.addEventListener('keydown', onKey);
    if (yes) yes.addEventListener('click', () => finish(true), { once: true });
    no.addEventListener('click', () => finish(false), { once: true });
  })).then((r) => {
    popScreenDim(false);
    if (r) return r.value;
    return openBuyDialogDom(price, opts); // the export failed to load
  });
}

function openBuyDialogDom(price, { note = '', affordable = true } = {}) {
  const dlg = document.getElementById('buyDialog');
  const priceEl = document.getElementById('buyDialogPrice');
  priceEl.textContent = affordable ? Number(price).toLocaleString('en-US') : 'NOT ENOUGH BALANCE';
  priceEl.classList.toggle('is-notice', !affordable);
  const noteEl = document.getElementById('buyDialogNote');
  if (noteEl) noteEl.textContent = note;
  document.getElementById('buyYes').hidden = !affordable;
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
      document.removeEventListener('keydown', onKey);
      setTimeout(() => { dlg.hidden = true; }, DIM_TRANSITION_MS);
      resolve(answer && affordable);
    };
    const yes = document.getElementById('buyYes');
    const no = document.getElementById('buyNo');
    const onYes = () => close(true);
    const onNo = () => close(false);
    const onBackdrop = (e) => { if (e.target === dlg) close(false); };
    const onKey = (e) => { if (e.key === 'Escape') close(false); };
    document.addEventListener('keydown', onKey);
    yes.addEventListener('click', onYes);
    no.addEventListener('click', onNo);
    dlg.addEventListener('click', onBackdrop);
  });
}

// --- Dev panel --------------------------------------------------------------

// Multiplier demo without the backend: a middle-row win plus two chips (x3,
// x5). In the base game the plate shows the spin's x8; in free spins the
// values add to the round total each time (?demomult / ?demomult=fs).
let devRoundMultiplier = 1;
async function demoMultipliers() {
  const inRound = currentMode() === 'freespins';
  await applyGrid([
    ['rare_purple', 'rare_blue', 'common_4', 'wof', 'common_3'],
    ['common_1', 'common_1', 'common_1', 'common_4', 'common_2'],
    ['rare_yellow', 'rare_green', 'common_2', 'common_3', 'wof'],
  ]);
  const positions = [{ row: 0, col: 3, value: 3 }, { row: 2, col: 4, value: 5 }];
  if (inRound) devRoundMultiplier += 8;
  await playMultipliers({
    positions, applied: true, multiplier_sum: 8, round_multiplier: inRound ? devRoundMultiplier : null,
  }, inRound);
  const lw = [{ payline: 1, positions: [{ row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }] }];
  playWinCells(lw[0].positions, lw, []);
  showInlineWinAmount(21000 * (inRound ? devRoundMultiplier : 8));
}

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
  document.getElementById('devMult').addEventListener('click', () => demoMultipliers());
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
  // The feature screen goes FIRST: on a phone the whole spine set (~20 MB of
  // atlas pages) loading at once made the screen's own page fail with the
  // rest, so it never appeared. The bonus screen isn't needed before the
  // first bonus — it loads after the feature screen (see init).
  const tasks = [];
  if (stage) tasks.push(track(getSymbolResource(screenCode(FEATURE_SCREEN_CODE))));
  tasks.push(...[
    ...SYMBOL_CODES.map(symbolSrc),
    ...SYMBOL_CODES.map((c) => `${SYMBOL_ROOT}/blur/${SYMBOL_ART[c]}`),
    `${SYMBOL_ROOT}/wild_big.png`,
    bgSrcFor('base'),
    bgSrcFor('bonus'),
    ...['frame.png', 'logo.png', 'buy_chest.png', 'buy_cone.png', 'buy_text.png', 'fs_counter.png', 'plate.png', 'chest.png',
      'buy_title.png', 'mult_plate.png', 'scene_people.png',
      ...(isMobileLayout() ? ['logo_mob.png', 'buy_chest_mob.png', 'buy_cone_mob.png', 'buy_text_mob.png', 'frame_mob.png'] : [])].map((f) => `${ASSET_ROOT}/ui/${f}`),
  ].map((src) => track(preloadImage(src))));
  if (stage) {
    // Skeletons up front so the first win doesn't wait on a fetch.
    for (const code of SYMBOL_CODES) tasks.push(track(getSymbolResource(code)));
    if (LAND_ENABLED) for (const code of SYMBOL_CODES) tasks.push(track(getLandResource(code)));
  }
  if (backStage) {
    for (const name of SCENE_NAMES) if (sceneWanted(name)) tasks.push(track(getSceneResource(name)));
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
// *_mob = the portrait mockup's own frame / logo (Mob_Mafia_Slot.psb), the
// same skeletons retargeted onto that art (2026-10-16 redesign).
// Draw order (= this order): backgrounds, heroes, frames, counter, logos.
// Portrait (2026-10-16): background_mob (mobile terrace without people: palm
// sway mesh, sun, rays, water glints), the same hero skeletons placed on the
// mobile mockup's armchairs (hero_*_mob), bonus_bg_mob (club spotlights).
const SCENE_NAMES = ['background', 'background_mob', 'bonus_bg_mob', 'hero_man', 'hero_woman', 'hero_man_mob', 'hero_woman_mob',
  'frame', 'frame_mob', 'freespins', 'logo', 'logo_mob'];
// What actually runs (product, 2026-10-10: background, frame, logo and the
// redrawn heroes live; the counter and the sym_* land bounce stay off until
// asked for). Drop a hero from here and the PSB's still people
// (.scene-people) stand in for it automatically.
const SCENE_ON = new Set(['background', 'background_mob', 'bonus_bg_mob', 'hero_man', 'hero_woman', 'hero_man_mob', 'hero_woman_mob',
  'frame', 'frame_mob', 'logo', 'logo_mob']);
const LAND_ENABLED = false;
// root_scene_x/y from layout.json (PSB px, y down).
const SCENE_ROOTS = {
  background: [966, 470.5],
  hero_man: [279.5, 955],
  hero_woman: [1614.5, 954],
  // Mob_Mafia_Slot.psb people_normal: same art, scaled (man 'Layer 127'
  // 464 wide = 0.8375 of 554, woman 'Layer 94' 398 = 0.77 of 517), root =
  // bottom-centre of each layer.
  hero_man_mob: [159, 1305, 0.8375],
  hero_woman_mob: [634, 1271, 0.77],
};
let backStage = null;
const scene = {}; // name -> SpineInstance

// Folders of skeletons re-cut for the 2026-10-16 mockup (versioned so a cached
// old atlas page can't meet the new atlas text — see FEATURE_SCREEN_CODE).
const SCENE_DIR = {
  logo: 'logo_v2', freespins: 'freespins_v2', hero_man_mob: 'hero_man', hero_woman_mob: 'hero_woman',
  // glass inside the chrome = 70% black (product, 2026-10-16)
  frame: 'frame_v2', frame_mob: 'frame_mob_v2',
  // photo backgrounds moved to JPG atlas pages (2026-10-16 optimisation)
  background: 'background_v2', background_mob: 'background_mob_v3', bonus_bg_mob: 'bonus_bg_mob_v3',
};
// Only the current layout's skeletons are loaded (desktop vs portrait sets).
const SCENE_PORTRAIT_ONLY = new Set(['background_mob', 'bonus_bg_mob', 'hero_man_mob', 'hero_woman_mob', 'frame_mob', 'logo_mob']);
const SCENE_DESKTOP_ONLY = new Set(['background', 'hero_man', 'hero_woman', 'frame', 'logo']);
function sceneWanted(name) {
  if (!SCENE_ON.has(name)) return false;
  return isMobileLayout() ? !SCENE_DESKTOP_ONLY.has(name) : !SCENE_PORTRAIT_ONLY.has(name);
}
function getSceneResource(name) {
  if (!backStage) return Promise.reject(new Error('no back stage'));
  name = SCENE_DIR[name] || name;
  // README: "без premultiplied alpha" — and no pma line in the atlases.
  return loadSpineWithRetry(backStage.assetManager, `${SCENE_ROOT}/${name}`, { premultipliedAlpha: false });
}

function sceneAnchorAt(name, resource) {
  const { x, y, width, height } = resource.bounds;
  const [rx, ry, k = 1] = SCENE_ROOTS[name];
  const el = document.createElement('div');
  el.className = 'scene-anchor';
  el.style.left = `${rx + x * k}px`;
  el.style.top = `${ry - (y + height) * k}px`;
  el.style.width = `${width * k}px`;
  el.style.height = `${height * k}px`;
  document.getElementById('stage').appendChild(el);
  return el;
}

function sceneAnchorFor(name, resource) {
  if (SCENE_ROOTS[name]) return sceneAnchorAt(name, resource);
  if (name === 'background_mob') return document.querySelector('.bg-mob--base');
  if (name === 'bonus_bg_mob') return document.querySelector('.bg-mob--bonus');
  if (name === 'frame') return document.getElementById('reelRig');
  if (name === 'frame_mob') return document.querySelector('.frame-mob');
  if (name === 'logo') return document.querySelector('.stage--front .logo--desk');
  if (name === 'logo_mob') return document.querySelector('.stage--front .logo--mob');
  // freespins: the counter skeleton's box is the counter art itself (jukebox
  // plus its shadow), i.e. the whole .fs-counter box.
  const el = document.createElement('div');
  el.className = 'fs-counter__anchor';
  document.getElementById('freeSpinsCounter').prepend(el);
  return el;
}

async function setupScene() {
  if (!backStage) return;
  try {
    for (const name of SCENE_NAMES) {
      if (!sceneWanted(name)) continue;
      const resource = await getSceneResource(name);
      resource.animationStateData.defaultMix = 0.2; // README recommendation
      const inst = resource.createInstance();
      inst.anchorEl = sceneAnchorFor(name, resource);
      inst.boundsOverride = resource.bounds;
      inst.fit = 1;
      inst.play('idle', true);
      // Product: the scene photo behind the slot 20% darker (FX stay bright).
      if (/^(background|bonus_bg)/.test(name)) {
        const bgSlot = inst.skeleton.findSlot('bg');
        if (bgSlot) bgSlot.color.set(0.8, 0.8, 0.8, 1);
      }
      // Desync the two heroes' breathing.
      if (name.startsWith('hero_woman')) inst.animationState.getCurrent(0).trackTime = 3.1;
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
    background_mob: portrait && !bonus,
    hero_man_mob: portrait && !bonus,
    hero_woman_mob: portrait && !bonus,
    bonus_bg_mob: portrait && bonus,
    frame: !portrait,
    frame_mob: portrait,
    freespins: bonus,
    logo: !portrait,
    logo_mob: portrait,
  };
  document.getElementById('screen').classList.toggle('has-spine-terrace', want.background && !!scene.background);
  // Still people over the live terrace while the hero skeletons are off.
  document.getElementById('screen').classList.toggle('has-still-people', want.background && !!scene.background && !scene.hero_man);
  for (const name of SCENE_NAMES) if (scene[name]) backStage.removeBase(scene[name]);
  for (const name of SCENE_NAMES) if (want[name] && scene[name]) backStage.addBase(scene[name]);
}

// One-shot reaction, then back to the idle loop.
// Heroes (README of the hero pack): idle never stops on track 0 and `win` is
// layered ADDITIVELY on track 1 — it starts and ends in the zero pose, so
// there is no pop in or out and the breathing carries on underneath.
function playSceneClip(name, clip) {
  const inst = scene[name];
  if (!inst || !inst.resource.skeletonData.findAnimation(clip)) return;
  if (name.startsWith('hero_')) {
    const state = inst.animationState;
    const cur = state.getCurrent(1);
    if (cur && cur.animation && cur.animation.name === clip && !cur.isComplete()) return; // already celebrating
    const entry = state.setAnimation(1, clip, false);
    entry.mixBlend = spine.MixBlend.add;
    entry.mixDuration = 0;
    state.addEmptyAnimation(1, 0, 0);
    return;
  }
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

// _v2: re-cut for the 2026-10-16 mockup. New folder names on purpose — Spine
// assets load without a ?v=, so a cached old atlas page must never meet the new
// atlas text under the same URL.
const PRELOAD_TIMEOUT_MS = 12000;
const FEATURE_SCREEN_CODE = 'feature_screen_v2';
const BONUS_SCREEN_CODE = 'bonus_screen_v4'; // v3: digits inside the skeleton; v4: club photo as a JPG page
// Both full-screen exports (pfs / bfs) are authored on the PSB canvas around
// the skeleton origin, 1 unit = 1 design px.
const FEATURE_BOX = { x: -966, y: -470, width: 1932, height: 940 };
// Portrait builds (<code>_mob): the same skeletons re-laid out on the mobile
// canvas 780x1416 (Mob_Mafia_Slot.psb), origin = its centre.
const FEATURE_BOX_MOB = { x: -390, y: -708, width: 780, height: 1416 };
function screenCode(code) {
  return isMobileLayout() ? `${code}_mob` : code;
}
const FEATURE_FADE_MS = 500;

// Bonus screen (bfs): the "Free spins" jukebox rolls three digit strips in
// clipped windows and hides each strip once it lands — the painted "010" is
// erased from the machine art and the real count is a glyph slot per window
// (see showBonusScreen).

// Shared lifecycle of the two full-screen Spine screens: 90% dim, intro ->
// idle loop, click anywhere -> fade out. `onFrame(inst)` runs every frame
// while the screen is up (the bonus screen's live digits).
function showSpineScreen(baseCode, { onFrame = null, onClose = null, onCreate = null } = {}) {
  const root = document.getElementById('featureScreen');
  if (!stage || !root) return Promise.resolve(false);
  const portrait = isMobileLayout(); // the layout is fixed for the screen's lifetime
  const code = portrait ? `${baseCode}_mob` : baseCode;
  return getSymbolResource(code).then((resource) => new Promise((resolve) => {
    const inst = resource.createInstance();
    if (onCreate) onCreate(inst);
    // Both layouts pin the skeleton's canvas box onto #stage, which is that
    // same design canvas (1932x940 / 780x1416) contain-scaled to the screen.
    const place = () => {
      inst.anchorEl = document.getElementById('stage');
      inst.fit = 1;
    };
    place();
    inst.boundsOverride = portrait ? FEATURE_BOX_MOB : FEATURE_BOX;
    window.addEventListener('resize', place);

    document.body.classList.add('is-feature-screen');
    root.hidden = false;
    void root.offsetWidth;
    root.classList.add('is-open');
    stage.addOverlay(inst);
    inst.play('intro', false);
    inst.queue('idle', true);
    // ?seek=<s> — dev/screenshot: jump the intro to that moment.
    const seek = Number(new URLSearchParams(location.search).get('seek'));
    if (seek > 0) inst.animationState.getCurrent(0).trackTime = seek;

    let done = false;
    let alpha = 1;
    const frame = () => {
      if (done) return;
      if (onFrame) onFrame(inst, alpha);
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);

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
      if (onClose) onClose();
      const start = performance.now();
      const finish = () => {
        if (done) return;
        done = true;
        stage.removeOverlay(inst);
        window.removeEventListener('resize', place);
        root.hidden = true;
        root.style.transition = '';
        document.body.classList.remove('is-feature-screen');
        resolve(true);
      };
      const tick = (now) => {
        if (done) return;
        const t = Math.min(1, (now - start) / FEATURE_FADE_MS);
        alpha = 1 - t;
        inst.skeleton.color.a = alpha;
        if (t < 1) requestAnimationFrame(tick);
        else finish();
      };
      requestAnimationFrame(tick);
      setTimeout(finish, FEATURE_FADE_MS + 200); // hidden tab: rAF frozen
    };
    root.addEventListener('click', close);
  })).catch((err) => {
    console.warn(`${code} screen failed:`, err);
    return false;
  });
}

function showFeatureScreen() {
  return showSpineScreen(FEATURE_SCREEN_CODE);
}

// Resolves true if the Spine bonus screen ran, false if it couldn't (no
// WebGL / export missing) so the caller falls back to the CSS popup.
function showBonusScreen(spins) {
  // The spin count is drawn INSIDE the skeleton (slots dig1..3 on the window
  // bones, glyph regions d0..d9, faded in by the intro as each strip stops) —
  // a DOM overlay chasing bone positions lagged a frame behind the bounce.
  const digits = String(Math.max(0, Math.min(999, spins))).padStart(3, '0');
  return showSpineScreen(BONUS_SCREEN_CODE, {
    onCreate: (inst) => {
      [...digits].forEach((ch, i) => {
        try { inst.skeleton.setAttachment(`dig${i + 1}`, `d${ch}`); } catch (err) { /* old export */ }
      });
    },
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
  // Bounded like the other games' preloaders: on a slow phone link one heavy
  // atlas (the screens are 2-4 MB) must not hold the game behind the bar — the
  // feature screen still waits for its own skeleton when it opens.
  Promise.race([preloadAssets(), wait(PRELOAD_TIMEOUT_MS)]).then(() => {
    setupScene();
    if (window.Preloader) window.Preloader.done();
    // ?nofs — dev/screenshot convenience: straight into the game.
    const qs = new URLSearchParams(location.search);
    // Warm the bonus screen now that the first screen is up.
    if (stage) getSymbolResource(screenCode(BONUS_SCREEN_CODE)).catch((err) => console.warn('bonus screen:', err));
    if (qs.has('nofs') || qs.has('screen')) {
      document.getElementById('preloader')?.remove();
      // ?screen=feature|bonus — dev/screenshot: open that screen straight away.
      if (qs.get('screen') === 'feature') return showFeatureScreen();
      if (qs.get('screen') === 'bonus') return showBonusScreen(Number(qs.get('spins')) || 10);
      // ?demospin — dev/screenshot: reels spinning at full speed, never land.
      if (qs.has('demospin')) startReelLoop();
      // ?demomult[=fs] — dev/screenshot: the multiplier reveal (free spins: round total).
      if (qs.has('demomult')) {
        if (qs.get('demomult') === 'fs') { applyModeScreen('freespins'); setFreeSpinsCounter(7); }
        setTimeout(() => demoMultipliers(), 600);
      }
      // ?demowin — dev/screenshot: a two-line win on a fixed grid.
      if (qs.has('demowin')) {
        applyGrid([['common_1', 'common_2', 'common_2', 'rare_blue', 'common_3'], ['common_2', 'common_2', 'common_3', 'common_4', 'common_1'], ['rare_green', 'common_4', 'common_2', 'common_1', 'scatter']]);
        const lw = [
          { payline: 4, positions: [{ row: 0, col: 0 }, { row: 1, col: 1 }, { row: 2, col: 2 }] },
          { payline: 1, positions: [{ row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }] },
        ];
        playWinCells(lw.flatMap((w) => w.positions), lw, []);
      }
      return null;
    }
    return showFeatureScreen();
  });
  window.__slot = { get cellInfos() { return cellInfos; }, get stage() { return stage; } };
}

init();
