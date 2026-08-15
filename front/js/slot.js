// Game-specific wiring on top of spine-engine.js: reel grid, character, popups.
// Wired to the real backend (app/api/v1, see app.js) — cells render whatever
// symbol the server returns, not a fixed layout. The dev panel below still
// works standalone for asset preview.

const SYMBOL_FOLDERS = {
  scatter: 'Scatter',
  wild: 'Wild',
  duck: 'guse',
  watermelon: 'watermelon',
  corn: 'corn',
  blueberry: 'blueberry',
  strawberry: 'strawberry',
  cow: 'cow',
  pear: 'pear',
  dog: 'dog',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// scatter/wild ship with idle+landing+win; the rest only ship a win celebration.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// Attract-mode layout shown before the first real spin (also fixes the grid's
// row/col shape: 3 rows x 5 reels, matching the backend's `grid` response).
const SYMBOL_LAYOUT = [
  ['scatter', 'duck', 'watermelon', 'corn', 'blueberry'],
  ['strawberry', 'blueberry', 'scatter', 'strawberry', 'wild'],
  ['watermelon', 'cow', 'pear', 'dog', 'pear'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

const POPUP_FOLDERS = {
  bigWin: "img/amys-fruit-farm/Popup's/Big_win",
  epicWin: "img/amys-fruit-farm/Popup's/Epic_Win",
  megaWin: "img/amys-fruit-farm/Popup's/Mega_Win",
  bonusSpinsWin: "img/amys-fruit-farm/Popup's/bonus_spins_win",
  bonusSpinsTotalWin: "img/amys-fruit-farm/Popup's/bonus_spins_total_win",
  buyFreeSpins: "img/amys-fruit-farm/Popup's/buy_free_spins",
};
// Bone every popup skeleton positions its win-amount field on — an HTML
// overlay is placed at this bone's live world position each frame, since
// Spine text isn't otherwise reachable from CSS/DOM.
const POPUP_AMOUNT_BONE = 'bone_input_number';

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
// After a winning symbol plays its win animation once, wait this long, then
// play it again — repeating until the next spin tears the cell down.
const WIN_LOOP_PAUSE_MS = 500;

let stage = null;
let cellInfos = [];
let reelCols = []; // [{ colEl, stripEl }, ...] one per reel, left to right
let characterControllerRef = null;

// --- Win-line animation (see front/img/amys-fruit-farm/Win_Lines) ----------
//
// One Spine skeleton shipping 11 named animations ("1".."11"), one per
// payline — ported from wild-western-story/slot.js once confirmed there.
// The backend now defines exactly these 11 paylines, renumbered 1..11 in
// art order (see the game's app/seed PAYLINES) — animation name equals
// the payline index 1:1 (было 20 линий, лишние 9 платили без арта).
const PAYLINE_TO_WIN_LINE_ANIMATION = {
  1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
  7: '7', 8: '8', 9: '9', 10: '10', 11: '11',
};
const WIN_LINE_ASSET_PATH = 'img/amys-fruit-farm/Win_Lines';
let winLineResourcePromise = null;

// Precomputed once against the shared Win_Lines asset (union of all 11
// animations' AABB) rather than recomputed live in the browser — see
// wild-western-story/slot.js's own comment on this constant: that scan is
// real per-frame Spine runtime work which blocked the main thread long
// enough on a real mobile device to trip the browser's "page unresponsive"
// state. Same asset file byte-for-byte, so the same box applies here.
const WIN_LINE_BOUNDS_OVERRIDE = { x: -433.9161688016173, y: -211.514175415039, width: 856.6346179651904, height: 438.3254852294921 };

function getWinLineResource() {
  if (!winLineResourcePromise) {
    // Confirmed straight (non-premultiplied) alpha, same as wild-western-story's
    // copy of this exact asset — NOT this file's own default (this game's own
    // exports load with the SpineResource.load default of true), so this is
    // called explicitly rather than through this file's usual load call.
    winLineResourcePromise = SpineEngine.SpineResource.load(stage.assetManager, WIN_LINE_ASSET_PATH, {
      premultipliedAlpha: false,
    });
  }
  return winLineResourcePromise;
}

let winLineInstance = null;
let winLineLoopTimeout = null;

// Drawn as an overlay (not base), same layer as popups — so it always
// renders on top of every base-layer win clip (the winning symbols' own
// glow/loop), never underneath them. Anchored to .reel__grid, i.e. the
// frame's actual opening, so it's centered on the reel regardless of
// viewport scale. Always plays the clip exactly ONCE and resolves when it
// settles — never loop:true (that raced the caller's own repeat timer on a
// different clock and made the line visibly play twice per symbol-glow
// cycle). The caller owns the repeat cadence: previewWinLine below for a
// lone win, playMultiLineWinSequence's own per-phase step() for a
// multi-line win.
async function showWinLine(payline) {
  const animName = PAYLINE_TO_WIN_LINE_ANIMATION[payline];
  if (!animName) {
    hideWinLine();
    return;
  }
  const resource = await getWinLineResource();
  if (!winLineInstance) {
    winLineInstance = resource.createInstance();
    winLineInstance.anchorEl = document.querySelector('.reel__grid');
    winLineInstance.fit = 0.9; // product, this session: "уменьшить на 10%"
    winLineInstance.boundsOverride = WIN_LINE_BOUNDS_OVERRIDE;
    stage.addOverlay(winLineInstance);
  }
  await new Promise((resolve) => {
    winLineInstance.play(animName, false);
    winLineInstance.onSettle = () => {
      winLineInstance.onSettle = null;
      resolve();
    };
  });
}

// Lone-line case only (playWinCells' single-group branch): repeats showWinLine
// on the exact same play-once/pause/repeat cadence previewSymbolWin already
// uses for the winning symbols themselves (WIN_LOOP_PAUSE_MS), so the line
// pulses in lockstep with their glow instead of drifting against it.
function previewWinLine(payline) {
  if (winLineLoopTimeout) {
    clearTimeout(winLineLoopTimeout);
    winLineLoopTimeout = null;
  }
  const playOnce = () => {
    showWinLine(payline).then(() => {
      winLineLoopTimeout = setTimeout(() => {
        winLineLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

function hideWinLine() {
  if (winLineLoopTimeout) {
    clearTimeout(winLineLoopTimeout);
    winLineLoopTimeout = null;
  }
  if (!winLineInstance) return;
  stage.removeOverlay(winLineInstance);
  winLineInstance = null;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomSymbolCode() {
  return SYMBOL_CODES[Math.floor(Math.random() * SYMBOL_CODES.length)];
}

// code -> Promise<SpineResource>, shared across all cells so any symbol can
// land in any cell without re-fetching its skeleton every time.
const symbolResourceCache = {};

function getSymbolResource(code) {
  if (!symbolResourceCache[code]) {
    const folder = SYMBOL_FOLDERS[code];
    symbolResourceCache[code] = SpineEngine.SpineResource.load(stage.assetManager, `img/amys-fruit-farm/Export/${folder}`);
  }
  return symbolResourceCache[code];
}

// Cells are fixed-size layout slots (--cell-size in CSS) — a spacing unit,
// not a clipping/fitting box. Every symbol renders at its own asset-native
// size, uncropped and unscaled ("не масштабируем, используем такие же как
// и в оригинале"), centered on the cell. The static <img> is centered via
// the cell's own flex rules; the Spine instance gets a separate `.reel__cell-anchor`
// placeholder (sized to the skeleton's own bounds once loaded — see
// setCellSymbol) so its native contain-fit resolves to true 1:1 scale
// rather than "fill the 200px slot".
// Shifts the static <img> so its *visible content* centers on the cell
// (canceling out asymmetric transparent padding baked into some static.png
// files — see ReelMath.STATIC_CONTENT_OFFSET), matching where Spine renders
// the same symbol's content (Spine bounds are always content-centered).
function applyStaticContentOffset(img, code) {
  // A live override from Anim Lab's "Калибровать" button (front/js/anim-lab.js,
  // shared via front/js/slot-calibration.js) wins over the baked-in table —
  // lets a calibration be checked in this actual game before it's copied
  // into ReelMath.STATIC_CONTENT_OFFSET to make it permanent.
  const { dx, dy } = (window.SlotCalibration && window.SlotCalibration.get('fruit-farm', code)) || ReelMath.staticContentOffset(code);
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  img.src = `img/amys-fruit-farm/Export/${SYMBOL_FOLDERS[code]}/static.png`;
  img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

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
      const info = { symbol, cell, img, anchor, instance: null, winLoopTimeout: null };
      cell.addEventListener('click', () => previewSymbolWin(info));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
}

function teardownCellInstances() {
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  hideWinLine();
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    if (info.winLoopTimeout) {
      clearTimeout(info.winLoopTimeout);
      info.winLoopTimeout = null;
    }
    if (info.instance) {
      stage.removeBase(info.instance);
      info.instance = null;
    }
    // A cell that was mid-animation had its static tile hidden in favour of
    // the canvas (a win clip, an idle loop). Pulling the instance off the
    // canvas without putting the tile back leaves the cell EMPTY — and since
    // this runs at the start of every spin, that empty cell is what visibly
    // drops out of view when the reels clear. Cells that are meant to be
    // empty carry no `src` at all, so they stay hidden.
    if (info.img && info.img.getAttribute('src')) info.img.style.visibility = '';
  }
}

// Renders `code` into `info`'s cell: static image at rest for every symbol,
// plus a live idle loop for scatter/wild (the only two with idle/win clips).
// Goes straight to 'idle' rather than playing a 'landing' entrance first, so
// the very first Spine frame shown matches the static image it replaces —
// no separate "bounce in" that would visibly differ from the static frame.
async function setCellSymbol(info, code) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  if (info.instance) {
    stage.removeBase(info.instance);
    info.instance = null;
  }
  info.symbol = code;
  info.cell.dataset.symbol = code;
  const folder = SYMBOL_FOLDERS[code];
  info.img.src = `img/amys-fruit-farm/Export/${folder}/static.png`;
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);

  try {
    const resource = await getSymbolResource(code);
    // Size the anchor to the skeleton's own bounds so fit:1's contain-fit
    // (anchor size / bounds size) resolves to exactly 1 — true native
    // scale, independent of the 200px cell slot. Centered on the cell via
    // .reel__cell-anchor's own CSS (position:absolute + translate(-50%,-50%)).
    if (info.anchor) {
      info.anchor.style.width = `${resource.bounds.width}px`;
      info.anchor.style.height = `${resource.bounds.height}px`;
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'fruit-farm', code);
    }
    const instance = resource.createInstance();
    instance.anchorEl = info.anchor || info.cell;
    instance.fit = 1; // native scale — see the anchor sizing above
    info.instance = instance;

    if (SPECIAL_SYMBOLS.has(code)) {
      // Scatter/Wild stay alive with a subtle idle loop even at rest.
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      stage.addBase(instance);
      instance.play('idle', true);
    }
  } catch (err) {
    console.warn(`Spine load failed for symbol "${code}" (${folder}):`, err);
  }
}

// Plays a cell's win Spine animation once; resolves once it settles.
// Shared by the independent per-cell loop below and the multi-line group
// sequencer (playMultiLineWinSequence) — same stage.addBase/play/onSettle
// sequence either way, just driven by different callers.
function playWinAnimationOnce(info) {
  const { instance, img } = info;
  if (!instance) return Promise.resolve();
  img.style.visibility = 'hidden';
  stage.addBase(instance);
  return new Promise((resolve) => {
    instance.play('win', false);
    instance.onSettle = () => {
      instance.onSettle = null;
      resolve();
    };
  });
}

// Plays the win animation once, waits WIN_LOOP_PAUSE_MS, plays it again, and
// so on — until teardownCellInstances() cancels it (i.e. the next spin).
// Used for the single-winning-line case and the symbol-click preview; when
// multiple lines win at once, playMultiLineWinSequence drives things instead.
function previewSymbolWin(info) {
  if (!info.instance) return;

  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }

  const playOnce = () => {
    playWinAnimationOnce(info).then(() => {
      info.winLoopTimeout = setTimeout(() => {
        info.winLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

// Toggles a cell between "actively playing its win animation" (Spine
// instance on stage, static image hidden behind it) and "resting" (Spine
// instance off-stage, static image visible again — so is-dimmed's opacity,
// which only affects the DOM image, actually has something to dim; the
// Spine canvas paints above the DOM regardless of any cell's CSS).
function setCellActive(info, active) {
  const { instance, img } = info;
  if (!instance) return;
  if (active) {
    img.style.visibility = 'hidden';
    stage.addBase(instance);
  } else {
    stage.removeBase(instance);
    img.style.visibility = '';
  }
}

// Matches .reel__cell.is-dimmed img's own opacity (0.3) — that CSS rule only
// dims the DOM <img>, which is invisible whenever the cell has a live Spine
// instance instead (wild/scatter's persistent idle loop — see
// SPECIAL_SYMBOLS/setCellActive: img.style.visibility is 'hidden' the whole
// time the instance is on stage). Without this, a wild sitting idle outside
// the winning line stayed at full brightness while every other losing cell
// dimmed around it (product, this session).
const CELL_DIM_TINT = 0.3;
function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
  if (info.instance) {
    const c = dimmed ? CELL_DIM_TINT : 1;
    info.instance.skeleton.color.set(c, c, c, 1);
  }
}

let multiLineSequenceTimeout = null;

// More than one line/count-win landed on the same spin: play every winning
// cell together once (dimming everything else), then cycle through each
// line's cells one at a time — until teardownCellInstances() cancels it.
function playMultiLineWinSequence(groups, allWinInfos, lineWins) {
  const playPhaseOnce = (activeInfos) => {
    const activeSet = new Set(activeInfos);
    // Dim every cell that isn't part of the current phase — not just the
    // *other* winning cells, but genuinely non-winning ones too.
    for (const info of cellInfos) {
      if (info) setCellDimmed(info, !activeSet.has(info));
    }
    // Only toggle the Spine win-clip on/off for cells that actually have
    // one to toggle (i.e. the winning cells) — a non-winning cell's
    // instance (idle loop or nothing) is left alone, just dimmed above.
    for (const info of allWinInfos) {
      setCellActive(info, activeSet.has(info));
    }
    return Promise.all(activeInfos.map((info) => playWinAnimationOnce(info)));
  };

  let groupIndex = -1; // -1 = the initial "every line together" phase
  const step = () => {
    const activeInfos = groupIndex === -1 ? allWinInfos : groups[groupIndex];
    // groups[i] < lineWins.length corresponds 1:1 to lineWins[i] (see
    // buildWinGroups/ReelMath.collectWinGroups — line wins are spread before
    // count wins, positions-only, so index is the only way back to a
    // payline). The "all together" phase (groupIndex -1) mixes lines, so no
    // single line's art applies there.
    const win = groupIndex >= 0 ? lineWins[groupIndex] : null;
    if (win) showWinLine(win.payline);
    else hideWinLine();
    playPhaseOnce(activeInfos).then(() => {
      multiLineSequenceTimeout = setTimeout(() => {
        multiLineSequenceTimeout = null;
        groupIndex = (groupIndex + 1) % groups.length;
        step();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  step();
}

// Instantly (no scroll animation) sets every cell to `grid`'s symbols —
// used for the error-recovery path (revert to the last good result).
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

// Maps each line_wins/count_wins entry's {row,col} positions to the actual
// cellInfos for that line — i.e. one group of cells per winning line/combo,
// as opposed to winning_cells' single deduped union (see ReelMath.collectWinGroups).
function buildWinGroups(lineWins, countWins) {
  return ReelMath.collectWinGroups(lineWins, countWins).map((positions) =>
    positions.map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean),
  );
}

// Plays the win animation on exactly the cells the backend flagged as
// winning ({row, col, symbol} — see winning_cells in the /spin response).
// With a single winning line, every cell just loops independently as
// before. With more than one, the first play shows every line together
// (dimming non-winning cells); repeats cycle through each line in turn —
// see playMultiLineWinSequence.
function playWinCells(winningCells, lineWins, countWins) {
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
      previewWinLine(lineWins[0].payline);
    } else {
      hideWinLine();
    }
    for (const info of allWinInfos) previewSymbolWin(info);
  }
}

const INLINE_WIN_AMOUNT_HOLD_MS = 1800;
let inlineWinAmountTimeout = null;

// Small/base wins never trigger a Spine popup (only big/mega/epic do) — this
// is the only place their amount is shown at all, so it doesn't just
// disappear into the win animation with no readable number anywhere.
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

// --- Reel motion -----------------------------------------------------------
//
// No symbol asset ships a "spinning" clip, so motion is built from plain
// static images sliding through a masked column (overflow: hidden), moving
// top to bottom: new symbols slide in from under the top of the frame, old
// ones slide out under the bottom. Two phases:
//   1. startReelLoop(): an open-ended seamless CSS loop while the network
//      request is in flight (we don't know the final symbols yet).
//   2. landReels(grid): once the result is known, a decelerating scroll
//      that ends exactly on the real symbols, staggered reel by reel.
//
// Cells are fixed-size with a fixed gap (--cell-size/--cell-gap in CSS), so
// the scroll "step" between consecutive cell positions is ReelMath.ROW_STEP
// (cell + gap) — no runtime measurement needed anymore.

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
// the end that, stretched over ANTICIPATION_LAND_DURATION_MS, there's a long
// near-motionless stretch partway through — reads as "it landed", followed
// by one final small creep into the true resting spot, i.e. "falls, then
// falls again" (reported live). Fix: two separate phases instead of one
// stretched curve — a plain LINEAR pre-roll (no easing, so no plateau,
// just a steady "still spinning" scroll) for the wait, followed by the
// *exact* same short eased landing normal columns already use (proven fine,
// never stretched).
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false) {
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

      // Cell 0..2 (the real result) sit at the top of the strip; the window
      // starts showing the filler cells at the bottom and scrolls up-index
      // (== moving the strip *down* on screen) until the real result settles
      // at translateY(0) — its natural resting position. The pre-roll filler
      // (anticipating columns only) sits *below* the normal landing filler,
      // i.e. further from the result, so it's scrolled through first.
      const sequence = [
        ...finalCodes,
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, randomSymbolCode),
        ...Array.from({ length: prerollCount }, randomSymbolCode),
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

        // Fired on its own timer (0.2s ahead of the landing transition's own
        // end/finish() below) rather than from finish() itself — the visual
        // landing timing is untouched, only the sound cue moved earlier.
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
        setTimeout(finish, REEL_LAND_DURATION_MS + 200); // safety net (e.g. backgrounded tab)
      };

      if (isAnticipating) {
        const prerollStartY = -((REEL_LAND_FILLER_COUNT + prerollCount) * ReelMath.ROW_STEP);
        stripEl.style.transform = `translateY(${prerollStartY}px)`;
        void stripEl.offsetHeight; // force reflow before enabling the transition
        stripEl.style.transition = `transform ${ANTICIPATION_PREROLL_MS}ms linear`;
        stripEl.style.transform = `translateY(${landStartY}px)`;

        setTimeout(() => {
          // Commit exactly (rather than trusting the transition arrived
          // precisely on time) before starting the landing phase, same
          // "clean handoff" reasoning as the loop-restart fix above.
          stripEl.style.transition = 'none';
          stripEl.style.transform = `translateY(${landStartY}px)`;
          void stripEl.offsetHeight;
          beginLanding();
        }, ANTICIPATION_PREROLL_MS);
      } else {
        stripEl.style.transform = `translateY(${landStartY}px)`;
        void stripEl.offsetHeight; // force reflow before enabling the transition
        beginLanding();
      }
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
    const info = { symbol: code, cell, img, anchor, instance: null, winLoopTimeout: null };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks);
}

// `anticipationColumns` — column indices flagged by
// ReelMath.collectAnticipationColumns (empty array = no suspense this spin).
//
// The reveal that triggers anticipation (the column landing just before it)
// must actually be *visible* first — dressing up the remaining reels the
// instant landReels() is called would just be a real-time spoiler ("how
// does it already know?"). So this lands every column before the
// anticipation zone on the normal staggered schedule first, only *then*
// enters the suspense zone.
//
// From there columns land ONE AT A TIME, never in parallel: product ("не
// должны одновременно крутиться все оставшиеся барабаны") wants a single
// reel revealed, then the next, and so on — not every remaining reel
// spinning at once. collectAnticipationColumns only flags a column while the
// trigger is still undecided (landedCount stuck at triggerCount-1), so once
// one of them actually lands the deciding symbol, later columns fall out of
// the flagged set on their own — those just land at normal speed, still one
// at a time, since the suspense is already resolved by then.
async function landReels(grid, anticipationColumns = []) {
  teardownCellInstances();

  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const delay = col * REEL_LAND_STAGGER_MS;
    leadTasks.push(
      landReel(col, finalCodes, delay, false).then((cellEls) => settleColumnCells(cellEls, col, finalCodes)),
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

// --- Screen dim (popups + base<->bonus transitions) ------------------------
//
// Reference-counted rather than a plain boolean: a feature trigger fires a
// mode switch *and* a popup together, each wanting the screen dimmed for its
// own (differently-timed) duration. Whichever finishes first must not lift
// the dim out from under the other still-showing one.

let dimActiveCount = 0;
// Separate, independently-counted flag: base<->bonus mode switches want a
// *fully* opaque blackout (no background peeking through while bgLayer's
// src swaps underneath), while a plain win popup (big/mega/epic, no mode
// switch involved) keeps the lighter partial dim. Sharing the same
// reference-counted #screenDim element/timing, just an additional class.
let opaqueDimActiveCount = 0;

function pushScreenDim(opaque = false) {
  dimActiveCount += 1;
  document.getElementById('screenDim').classList.add('is-active');
  if (opaque) {
    opaqueDimActiveCount += 1;
    document.getElementById('screenDim').classList.add('is-opaque');
    // Opaque dim = the base<->bonus mode transition — the character and any
    // still-looping win symbols are drawn on the same canvas as the popup,
    // so #screenDim (a DOM element) can't darken them without also covering
    // the popup. Tint the canvas's base layer directly instead; the overlay
    // (popup) instances are untouched, so the popup stays bright.
    stage.setBaseDim(true);
  }
}

function popScreenDim(opaque = false) {
  dimActiveCount = Math.max(0, dimActiveCount - 1);
  if (dimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-active');
  if (opaque) {
    opaqueDimActiveCount = Math.max(0, opaqueDimActiveCount - 1);
    if (opaqueDimActiveCount === 0) {
      document.getElementById('screenDim').classList.remove('is-opaque');
      stage.setBaseDim(false);
    }
  }
}

// Dims the screen, runs `mutateFn` once the dim-in transition has mostly
// played out, then fades back. Used for both popups and mode switches so
// they read as one consistent piece of screen language.
async function withScreenDim(mutateFn, { opaque = false } = {}) {
  pushScreenDim(opaque);
  await wait(DIM_TRANSITION_MS);
  try {
    await mutateFn();
  } finally {
    popScreenDim(opaque);
  }
}

// Swaps the on-screen mode (background + character) for `next`. Shared by the
// plain leave-bonus dim and the enter-bonus intro so the two never drift apart.
function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
  if (characterControllerRef) characterControllerRef.setMode(next);
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
  // leaving it keeps the plain opaque dim swap (fully opaque so the bgLayer
  // src swap is never visible mid-transition).
  if (next === 'freespins') return enterBonusTransition(amount);

  return withScreenDim(
    async () => {
      applyModeScreen(next);
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
}

async function setupCharacter() {
  const characterImg = document.getElementById('character');
  const [baseResource, bonusResource] = await Promise.all([
    SpineEngine.SpineResource.load(stage.assetManager, 'img/amys-fruit-farm/Export/girl_base'),
    SpineEngine.SpineResource.load(stage.assetManager, 'img/amys-fruit-farm/Export/girl_bonus'),
  ]);

  const instances = {
    base: baseResource.createInstance(),
    bonus: bonusResource.createInstance(),
  };
  for (const inst of Object.values(instances)) {
    inst.anchorEl = characterImg;
    inst.fit = 1;
    inst.play('idle', true);
  }

  characterImg.style.visibility = 'hidden';
  let active = 'base';
  stage.addBase(instances[active]);

  return {
    setMode(mode) {
      const next = mode === 'freespins' ? 'bonus' : 'base';
      if (next === active) return;
      stage.removeBase(instances[active]);
      active = next;
      stage.addBase(instances[active]);
    },
  };
}

// --- Popups ------------------------------------------------------------

const popupResourceCache = {};
let popupAmountRaf = null;

function worldToScreen(worldX, worldY, canvasEl) {
  const dpr = window.devicePixelRatio || 1;
  const canvasRect = canvasEl.getBoundingClientRect();
  const cx = worldX + canvasEl.width / 2;
  const cy = canvasEl.height / 2 - worldY;
  return { left: canvasRect.left + cx / dpr, top: canvasRect.top + cy / dpr };
}

function startPopupAmountTracking(instance, amount) {
  const canvasEl = document.getElementById('spineCanvas');
  const el = document.getElementById('popupAmount');
  el.textContent = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');

  const tick = () => {
    const bone = instance.skeleton.findBone(POPUP_AMOUNT_BONE);
    if (bone) {
      const pos = worldToScreen(bone.worldX, bone.worldY, canvasEl);
      el.style.left = `${pos.left}px`;
      el.style.top = `${pos.top}px`;
    }
    popupAmountRaf = requestAnimationFrame(tick);
  };
  tick();
}

function stopPopupAmountTracking() {
  if (popupAmountRaf) cancelAnimationFrame(popupAmountRaf);
  popupAmountRaf = null;
  document.getElementById('popupAmount').classList.remove('is-visible');
}

// Core popup lifecycle (start -> idle hold -> end). The returned promise
// resolves only once the popup has FULLY played out, so a caller can sequence
// work after it. `ownDim` lets a caller that already owns the screen dim (the
// bonus intro below) borrow the popup without it pushing/popping its own dim.
function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = true, opaque = false } = {}) {
  const folder = POPUP_FOLDERS[key];
  if (!folder) return Promise.resolve();

  return new Promise((resolve) => {
    (async () => {
      Sound.playSfx('popupOpen');
      if (ownDim) {
        pushScreenDim(opaque);
        await wait(DIM_TRANSITION_MS);
      }

      if (!popupResourceCache[key]) {
        popupResourceCache[key] = SpineEngine.SpineResource.load(stage.assetManager, folder);
      }
      const resource = await popupResourceCache[key];

      const instance = resource.createInstance();
      instance.anchorEl = document.getElementById('screen');
      // Portrait doubles the popup (product): fine art scale for landscape
      // reads tiny on a tall phone screen. Glow overflowing the viewport is
      // accepted (product).
      instance.fit = isMobileLayout() ? 2 : 1;
      stage.addOverlay(instance);
      startPopupAmountTracking(instance, amount);

      instance.play('start', false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play('idle', true);
        setTimeout(() => {
          Sound.playSfx('popupClose');
          instance.play('end', false);
          instance.onSettle = () => {
            instance.onSettle = null;
            stage.removeOverlay(instance);
            stopPopupAmountTracking();
            if (ownDim) popScreenDim(opaque);
            resolve();
          };
        }, holdMs);
      };
    })();
  });
}

// Win-tier / dev popups: own their (partial) screen dim, as before.
function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

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
}

// Reserved side/vertical margins for the experimental fit-to-screen layout
// (body.layout-fit — see style.css): side room for the character + buy-bonus
// sign, and a little top/bottom breathing room for the logo — no separate
// budget for .ui-bar since that layout turns it into a translucent overlay
// instead of a row that competes for height.
const FIT_RESERVE_WIDTH_PX = 360;
const FIT_RESERVE_HEIGHT_PX = 60;

function isFullscreenFitLayout() {
  return document.body.classList.contains('layout-fit');
}

function updateReelScale() {
  // documentElement.clientWidth (actual rendered CSS pixel width, excludes
  // scrollbar) rather than window.innerWidth — some environments report the
  // two very differently for narrow/mobile viewports.
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
    document.documentElement.style.setProperty('--reel-scale', String(ReelMath.viewportScale(viewportWidth)));
  }

  document.documentElement.style.setProperty(
    '--reel-scale-mobile',
    String(ReelMath.mobileReelScale(viewportWidth, frameWidth)),
  );
}

// True below the portrait breakpoint (see the media query in style.css) —
// same signal driving the CSS layout switch, read from JS so bg image
// selection (mobile vs desktop art) can follow it too.
function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function bgSrcFor(mode) {
  if (isMobileLayout()) {
    return mode === 'base' ? 'img/amys-fruit-farm/img/Mob_Base_bg.png' : 'img/amys-fruit-farm/img/Mob_Bonus_bg.png';
  }
  return mode === 'base' ? 'img/amys-fruit-farm/img/bg_base_game.png' : 'img/amys-fruit-farm/img/bg_freespins.png';
}

// Rotating the device / resizing across the portrait breakpoint should
// swap in the right background art for whatever mode is already active,
// not just wait for the next mode change.
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

// One transparent draw through the full pipeline (texture upload + shader
// compile) so the first real win animation doesn't pay for it.
async function warmUpWebGl(resourcePromise) {
  const resource = await resourcePromise;
  const instance = resource.createInstance();
  instance.anchorEl = document.getElementById('screen');
  instance.skeleton.color.set(1, 1, 1, 0);
  stage.addOverlay(instance);
  await wait(120);
  stage.removeOverlay(instance);
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
  for (const code of SYMBOL_CODES) {
    tasks.push(track(preloadImage(`img/amys-fruit-farm/Export/${SYMBOL_FOLDERS[code]}/static.png`)));
    tasks.push(track(getSymbolResource(code)));
  }
  for (const key of Object.keys(POPUP_FOLDERS)) {
    if (!popupResourceCache[key]) {
      popupResourceCache[key] = SpineEngine.SpineResource.load(stage.assetManager, POPUP_FOLDERS[key]);
    }
    tasks.push(track(popupResourceCache[key]));
  }
  tasks.push(track(getWinLineResource()));
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('bonus'))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));
  tasks.push(track(warmUpWebGl(getWinLineResource())));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // must resolve before buildReelGrid's createCellNode calls applyStaticContentOffset
  Sound.playMusic('base'); // queued until the player's first click/keypress unlocks audio
  document.body.classList.add('layout-fit'); // fit-to-screen is now the default desktop layout — see setupDevPanel's toggle
  updateReelScale();
  updateBgForLayout();
  window.addEventListener('resize', () => {
    updateReelScale();
    updateBgForLayout();
  });

  buildReelGrid();
  stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  // Warmed up here, not on first use — a cold getWinLineResource() load
  // (network + parse) on a player's first win would delay the line's own
  // first .play() well past the symbols' (already-loaded by then), breaking
  // "starts the same instant" (product, this session).
  getWinLineResource();

  await preloadAssets();
  characterControllerRef = await setupCharacter();
  setupDevPanel();

  // Preload all unique symbol skeletons up front (small, ~1.5MB total) so grid clicks
  // and reel landings can trigger instantly with no per-symbol load stall.
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));

  if (window.Preloader) window.Preloader.done();

  window.__slot = { stage, cellInfos };
}

init();
