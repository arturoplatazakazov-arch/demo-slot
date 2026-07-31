// Golden Caravan — game-specific wiring on top of spine-engine.js. Structurally
// a port of ../sugar-galaxy/slot.js (same avalanche/cascade play loop — see
// app/engine/avalanche.py), adapted to this game's uploaded assets:
//   * every symbol/bg/popup Spine export was normalised by the slot-builder
//     into a top-level folder holding animation.{atlas,json,png}
//     (front/img/golden-caravan/<folder>/), so clips load from there — NOT from
//     the Export/ tree (which keeps the original per-symbol filenames + a
//     static.png per resting tile, still used for the grid <img> and paytable).
//   * layout comes from the slot-builder manifest (builder draft
//     "golden-caravan"), baked into css/golden-caravan.css.
//   * a single shared "boom" explosion export (front/img/golden-caravan/boom,
//     one "win" clip) plays as a one-shot overlay when a cell clears — both for
//     ordinary winning symbols and for a bomb's own row+column blast.
//
// A spin's whole result (initial grid + every cascade step, already fully
// resolved server-side) lands in one response; this file animates the walk
// from one step's grid to the next.

const ASSET_ROOT = 'img/golden-caravan';

// Golden Caravan's Spine exports ship STRAIGHT (non-premultiplied) alpha — same
// as Sugar Galaxy / East Discovery. Drawing them premultiplied blows out the
// semi-transparent glow/blik pixels, so force premultipliedAlpha:false.
//
// `assetManager` matters because textures are WebGL-context-specific: symbols/
// popups render on the main `stage`, the animated backgrounds + hero on the
// separate `bgStage` (a different <canvas>/GL context). Each resource must be
// loaded through the asset manager of the stage that draws it.
function loadSpineResource(folderPath, assetManager) {
  return SpineEngine.SpineResource.load(assetManager || stage.assetManager, folderPath, {
    premultipliedAlpha: false,
  });
}

// code -> normalised top-level Spine folder (front/img/golden-caravan/<folder>/
// animation.*). Codes match the seed (app/seed/golden_caravan.py) 1:1.
const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild',
  rare_faraon: 'rare_faraon',
  rare_skorobei: 'rare_skorobei',
  rare_snake: 'rare_snake',
  common_blue: 'common_blue',
  common_green: 'common_green',
  common_red: 'common_red',
  common_yellow: 'common_yellow',
  x2: 'multiplier_x2',
  x3: 'multiplier_x3',
  x5: 'multiplier_x5',
  bomb: 'bomb',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// code -> Export/<folder> holding the resting-tile static.png (the grid <img>
// and the paytable thumbnail — see app.js:renderInfoPopupContent). The Export
// subfolder names differ from the normalised Spine folders for the bomb (Bomb)
// and multiplier tokens (2x/3x/5x); everything else matches.
const STATIC_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild',
  rare_faraon: 'rare_faraon',
  rare_skorobei: 'rare_skorobei',
  rare_snake: 'rare_snake',
  common_blue: 'common_blue',
  common_green: 'common_green',
  common_red: 'common_red',
  common_yellow: 'common_yellow',
  x2: '2x',
  x3: '3x',
  x5: '5x',
  bomb: 'Bomb',
};

// Live per-symbol static-image nudge, written only by Anim Lab's "Калибровать"
// button (front/js/slot-calibration.js) — nothing is offset by default, so the
// static <img> is centred on its cell purely by .reel__cell's flex CSS.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('golden-caravan', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

// Every symbol export ships exactly one clip, "win", doing every job at once
// (idle/landing/win) — confirmed by inspecting each animation.json's
// `animations` key (this includes the bomb: its detonation clip is also just
// "win"). Scatter is the sole exception: it also ships a "landing" clip, played
// once when the initial grid reveals a scatter.
const SYMBOL_CLIPS = {
  scatter: { landing: 'landing', win: 'win' },
};
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || 'win';
}

// Popup Spine folders (normalised top-level). Each ships device-specific
// start/idle/end clips (desk_* / mob_*) instead of one shared start/idle/end —
// popupClip() picks the pair for the current orientation.
const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/popup_big_win`,
  epicWin: `${ASSET_ROOT}/popup_epic_win`,
  megaWin: `${ASSET_ROOT}/popup_mega_win`,
  bonusSpinsWin: `${ASSET_ROOT}/popup_bonus_spins_win`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/popup_bonus_spins_total_win`,
  buyFreeSpins: `${ASSET_ROOT}/popup_buy_bonus_spins`,
};
function popupClip(kind) {
  return `${isMobileLayout() ? 'mob' : 'desk'}_${kind}`;
}
// The win-amount plaque ("popup_*_plashka_dengi" slot) is driven by "bone6" in
// every popup export (checked each animation.json's slots→bone map) — track
// that bone so the amount sits on the money plaque.
const POPUP_AMOUNT_BONE = 'bone6';

// Matches the backend's grid shape (app/api/v1/schemas.py's SpinResponse.grid)
// and the slot-builder manifest — 6 reels x 5 rows, row-major: grid[row][col].
const GRID_COLS = 6;
const GRID_ROWS = 5;

// Grid geometry comes from CSS (--cell-w/--cell-h/--cell-gap-x/-y) so the
// desktop (116x116, gap 10) and mobile-portrait (100x100, gap 10) layouts —
// both from the slot-builder manifest and defined in css/golden-caravan.css —
// stay the single source of truth. Cached here, refreshed by readCellDims().
let cellW = 116, cellH = 116, gapX = 10, gapY = 10;
let colStep = cellW + gapX, rowStep = cellH + gapY;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => parseFloat(cs.getPropertyValue(name)) || fallback;
  cellW = num('--cell-w', 116);
  cellH = num('--cell-h', 116);
  gapX = num('--cell-gap-x', 10);
  gapY = num('--cell-gap-y', 10);
  colStep = cellW + gapX;
  rowStep = cellH + gapY;
}

function rowTop(row) {
  return row * rowStep;
}

// Attract-mode layout shown before the first real spin.
const SYMBOL_LAYOUT = [
  ['rare_faraon', 'common_blue', 'x2', 'common_green', 'rare_snake', 'common_yellow'],
  ['rare_skorobei', 'common_red', 'wild', 'x3', 'common_blue', 'rare_faraon'],
  ['scatter', 'common_green', 'rare_snake', 'common_yellow', 'x5', 'common_red'],
  ['common_blue', 'bomb', 'rare_skorobei', 'common_green', 'wild', 'rare_snake'],
  ['common_yellow', 'rare_faraon', 'common_red', 'x2', 'common_blue', 'common_green'],
];

const DIM_TRANSITION_MS = 320;
const WIN_LANDING_DELAY_MS = 0;
const CASCADE_FADE_MS = 200;
const CASCADE_DROP_MS = 100; // must match .reel__cell's `top` transition in css/golden-caravan.css
const CASCADE_STEP_GAP_MS = 220;
const WIN_LOOP_PAUSE_MS = 500;
// Bomb sits still for this long after landing before its own detonation clip.
const BOMB_PRE_EXPLODE_MS = 500;
// Bomb explosion SFX fires this long after the bomb's detonation clip starts.
const BOMB_SFX_AFTER_START_MS = 900;
// Spin-start fall/refill diagonal-wave offsets (see spinStartTransition).
const ROW_STAGGER_MS = 50;
const REEL_STAGGER_MS = 50;
const SPIN_START_WAVE_MS = (GRID_ROWS - 1) * ROW_STAGGER_MS + (GRID_COLS - 1) * REEL_STAGGER_MS + CASCADE_DROP_MS;
const SPIN_START_GAP_MS = 300;
// Spin-start SFX: SPIN_Start once 0.1s after the press, plus an Element_drop
// patter (one beat per reel column) when the fresh grid lands.
const SPIN_LANDING_DROP_COUNT = GRID_COLS;
const SPIN_LANDING_DROP_INTERVAL_MS = 100;
const SPIN_START_CUE_DELAY_MS = 100;
function startSpinPressCue() {
  setTimeout(() => Sound.playSfx('spinStart'), SPIN_START_CUE_DELAY_MS);
}
function playElementDropPatter() {
  for (let i = 0; i < SPIN_LANDING_DROP_COUNT; i++) {
    setTimeout(() => Sound.playSfx('cascadeDrop'), i * SPIN_LANDING_DROP_INTERVAL_MS);
  }
}
// Consumed multiplier token flying from its cell to the multiplier badge — must
// match css/golden-caravan.css's .token-flight animation duration.
const TOKEN_FLIGHT_MS = 1000;

let stage = null;
let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Bounds a Spine clip's promise so one asset that never settles can't hang the
// whole cascade forever.
const CLIP_TIMEOUT_MS = 4000;
function withTimeout(promise, ms = CLIP_TIMEOUT_MS) {
  return Promise.race([promise, wait(ms)]);
}

function randomSymbolCode() {
  return SYMBOL_CODES[Math.floor(Math.random() * SYMBOL_CODES.length)];
}

const symbolResourceCache = {};
function getSymbolResource(code) {
  if (!symbolResourceCache[code]) {
    const folder = SYMBOL_FOLDERS[code];
    symbolResourceCache[code] = loadSpineResource(`${ASSET_ROOT}/${folder}`);
  }
  return symbolResourceCache[code];
}

// Shared explosion VFX (front/img/golden-caravan/boom, single "win" clip),
// played as a one-shot overlay on a cleared cell. Its two additive-blend layers
// (boom_2/boom_4) paint solid black boxes under the vendor render path (same as
// Sugar Galaxy's boom exports), so keep only the Normal-blend layers
// (boom_1/boom_3) — re-hidden every frame because the clip re-asserts the
// additive attachments.
let boomResource = null;
function getBoomResource() {
  if (!boomResource) boomResource = loadSpineResource(`${ASSET_ROOT}/boom`);
  return boomResource;
}
function hideBlendFxSlots(instance) {
  for (const slot of instance.skeleton.slots) {
    if (slot.data.blendMode !== 0 && slot.getAttachment()) slot.setAttachment(null);
  }
}

// Plays the boom clip once, anchored to a *cell* (a stable size, never resized
// by JS — playSymbolClipOnce resizes info.anchor per-instance, so sharing it
// would race two target sizes). 1.3 = "explosion feels this big relative to the
// cell".
function playBoomExplosion(info) {
  return getBoomResource().then(
    (resource) =>
      new Promise((resolve) => {
        const instance = resource.createInstance();
        hideBlendFxSlots(instance);
        const baseUpdate = instance.update.bind(instance);
        instance.update = (delta, canvasEl) => {
          baseUpdate(delta, canvasEl);
          hideBlendFxSlots(instance);
        };
        instance.anchorEl = info.cell;
        instance.fit = 1.3;
        stage.addOverlay(instance);
        instance.play('win', false);
        instance.onSettle = () => {
          instance.onSettle = null;
          stage.removeOverlay(instance);
          resolve();
        };
      }),
  );
}

function createCellNode(col, row, code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.style.top = `${rowTop(row)}px`;
  cell.dataset.symbol = code;
  // Scatter always draws on top of neighbouring symbols (product). Cells share
  // the .reel__grid stacking context (the columns don't create their own), so a
  // z-index here lifts the scatter above every other cell regardless of column.
  if (code === 'scatter') cell.style.zIndex = '10';

  const img = document.createElement('img');
  img.alt = code;
  img.src = `${ASSET_ROOT}/Export/${STATIC_FOLDERS[code]}/static.png`;
  img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  const anchor = document.createElement('div');
  anchor.className = 'reel__cell-anchor';
  cell.appendChild(anchor);

  const info = { row, col, symbol: code, cell, img, anchor, instance: null, winLoopTimeout: null };
  cell.addEventListener('click', () => previewSymbolWin(info));
  return info;
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
  const gridHeight = GRID_ROWS * rowStep - gapY;
  for (let col = 0; col < GRID_COLS; col++) {
    const colEl = document.createElement('div');
    colEl.className = 'reel__col';
    colEl.style.left = `${col * colStep}px`;
    colEl.style.height = `${gridHeight}px`;
    inner.appendChild(colEl);
    reelCols.push(colEl);
  }
}

function teardownCellInstances() {
  for (const info of cellInfos) {
    if (!info) continue;
    if (info.winLoopTimeout) {
      clearTimeout(info.winLoopTimeout);
      info.winLoopTimeout = null;
    }
    if (info.instance) {
      stage.removeBase(info.instance);
      info.instance = null;
    }
  }
}

function renderInitialGrid(grid) {
  teardownCellInstances();
  buildReelGrid();
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const code = grid[row][col];
      const info = createCellNode(col, row, code);
      reelCols[col].appendChild(info.cell);
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
  revealScatterLandings();
}

// Animated counterpart of renderInitialGrid, used at the start of every spin:
// the current on-screen elements fall away one after another, then — after a
// short pause — the new spin's initial grid falls in from above the same way.
async function spinStartTransition(newGrid) {
  const outgoing = cellInfos.filter(Boolean);
  if (outgoing.length === 0) {
    renderInitialGrid(newGrid);
    playElementDropPatter();
    return;
  }

  for (let row = GRID_ROWS - 1; row >= 0; row--) {
    const rowOrderIndex = GRID_ROWS - 1 - row;
    for (let col = 0; col < GRID_COLS; col++) {
      const info = cellInfos[row * GRID_COLS + col];
      if (!info) continue;
      const delay = rowOrderIndex * ROW_STAGGER_MS + col * REEL_STAGGER_MS;
      setTimeout(() => {
        info.cell.classList.add('is-removing');
        info.cell.style.top = `${rowTop(row + 2)}px`;
      }, delay);
    }
  }
  await wait(SPIN_START_WAVE_MS);
  teardownCellInstances();

  await wait(SPIN_START_GAP_MS);

  buildReelGrid();
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const code = newGrid[row][col];
      const info = createCellNode(col, row, code);
      info.cell.style.transition = 'none';
      info.cell.style.top = `${rowTop(row - GRID_ROWS)}px`; // start stacked above the reel
      reelCols[col].appendChild(info.cell);
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
  void document.getElementById('reelGrid').offsetHeight; // force reflow so the next `top` change transitions

  playElementDropPatter();

  for (let row = GRID_ROWS - 1; row >= 0; row--) {
    const rowOrderIndex = GRID_ROWS - 1 - row;
    for (let col = 0; col < GRID_COLS; col++) {
      const info = cellInfos[row * GRID_COLS + col];
      const delay = rowOrderIndex * ROW_STAGGER_MS + col * REEL_STAGGER_MS;
      setTimeout(() => {
        info.cell.style.transition = '';
        info.cell.style.top = `${rowTop(row)}px`;
      }, delay);
      if (info.symbol === 'scatter') {
        setTimeout(() => playSymbolClipOnce(info, 'landing'), delay + CASCADE_DROP_MS);
      }
    }
  }
  await wait(SPIN_START_WAVE_MS);
}

// Scatter ships a "landing" clip separate from "win" — play it once,
// fire-and-forget, on every scatter in a fresh initial grid.
function revealScatterLandings() {
  for (const info of cellInfos) {
    if (info && info.symbol === 'scatter') playSymbolClipOnce(info, 'landing');
  }
}

// Free spins trigger/retrigger celebration: plays every scatter's own "win"
// clip — awaited (unlike revealScatterLandings) so app.js can hold off
// switching into bonus mode until it's done. Scans the *current* on-screen
// cellInfos, which by now reflects the final post-cascade grid.
async function playScatterTriggerCelebration() {
  const scatterInfos = cellInfos.filter((info) => info && info.symbol === 'scatter');
  if (scatterInfos.length === 0) return;
  Sound.playSfx('scatterWin');
  await Promise.all(scatterInfos.map((info) => withTimeout(playSymbolClipOnce(info, 'win'))));
}

// Plays one non-looping clip on a cell, swapping the static <img> out for a
// live Spine instance for the duration, then reverting to the static image once
// it settles.
function playSymbolClipOnce(info, kind) {
  return getSymbolResource(info.symbol).then(
    (resource) =>
      new Promise((resolve) => {
        // Size the anchor to the skeleton's own setup-pose bounds so fit:1's
        // contain-fit resolves to exactly native scale, matching the
        // native-size static <img>.
        if (info.anchor) {
          info.anchor.style.width = `${resource.bounds.width}px`;
          info.anchor.style.height = `${resource.bounds.height}px`;
          window.SlotCalibration?.applyAnchorOffset(info.anchor, 'golden-caravan', info.symbol);
        }
        const instance = resource.createInstance();
        instance.anchorEl = info.anchor || info.cell;
        instance.fit = 1;
        // Center the clip on the skeleton ORIGIN, not the exported setup-pose
        // bbox center. The rare exports (faraon/skorobei/snake) bake an
        // off-centre glow into their skeleton bounds, dragging bounds-center
        // down ~+18..+28px in Y while the actual symbol art sits on the origin
        // (measured: art centre ≈ (0,0), bbox centre ≈ (0,+28)). The engine
        // centres bounds-centre on the cell, so those rares landed ~20-30px low
        // relative to their (canvas-centred) static tile. A symmetric override
        // keeps the same size (width/height unchanged -> same native scale, so
        // symbols still overflow their cell / overlap neighbours) but re-centres
        // on the origin, so the art always sits on the cell regardless of what
        // the glow does to the bounds. Wild/commons/scatter/tokens already have
        // a bbox centre within a few px of the origin, so this leaves them put.
        const b = resource.bounds;
        instance.boundsOverride = { x: -b.width / 2, y: -b.height / 2, width: b.width, height: b.height };
        info.instance = instance;
        info.img.style.visibility = 'hidden';
        stage.addBase(instance);
        instance.play(clipName(info.symbol, kind), false);
        instance.onSettle = () => {
          instance.onSettle = null;
          stage.removeBase(instance);
          if (info.instance === instance) info.instance = null;
          info.img.style.visibility = '';
          resolve();
        };
      }),
  );
}

// Dev-only: click a resting cell to loop-preview its win clip.
function previewSymbolWin(info) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  const playOnce = () => {
    playSymbolClipOnce(info, 'win').then(() => {
      info.winLoopTimeout = setTimeout(() => {
        info.winLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
}

// --- Cascade-banner (per-step "xN" + step win amount) ----------------------

function showCascadeBanner(multiplier, amount) {
  document.getElementById('cascadeBannerMult').textContent = `x${multiplier}`;
  document.getElementById('cascadeBannerWin').textContent = Number(amount).toLocaleString('en-US');
  document.getElementById('cascadeBanner').classList.add('is-visible');
}

function hideCascadeBanner() {
  document.getElementById('cascadeBanner').classList.remove('is-visible');
}

// --- Multi counter (UI_Multy.png, both modes) -------------------------------
// Base game: the current spin's running cascade multiplier (resets each spin).
// Free spins: the session-wide token-multiplier accumulator (set once per spin
// from the server response — see applySpinResult in app.js).

function currentMode() {
  return document.getElementById('screen').dataset.mode || 'base';
}

function updateMultiCounter(value) {
  document.getElementById('multiCounterValue').textContent = `x${value}`;
}

// --- One cascade step --------------------------------------------------
// step (CascadeStepOut): { wins, step_multiplier, step_win, grid_after,
// tokens_consumed, bombs_detonated }.

function collectStepRemovals(step) {
  const removedByCol = new Map(); // col -> Set(row)
  const mark = (row, col) => {
    if (!removedByCol.has(col)) removedByCol.set(col, new Set());
    removedByCol.get(col).add(row);
  };
  for (const win of step.wins) {
    for (const pos of win.positions) mark(pos.row, pos.col);
  }
  for (const tok of step.tokens_consumed) mark(tok.row, tok.col);
  for (const bomb of step.bombs_detonated) {
    for (const pos of bomb.cleared) mark(pos.row, pos.col);
  }
  return removedByCol;
}

async function celebrateStep(step, removedByCol) {
  const winInfos = [];
  for (const win of step.wins) {
    for (const pos of win.positions) {
      const info = cellInfos[pos.row * GRID_COLS + pos.col];
      if (info) winInfos.push(info);
    }
  }
  const bombInfos = [];
  for (const bomb of step.bombs_detonated) {
    const info = cellInfos[bomb.row * GRID_COLS + bomb.col];
    if (info) bombInfos.push(info);
  }

  for (const info of cellInfos) {
    if (!info) continue;
    const removed = removedByCol.get(info.col);
    setCellDimmed(info, !(removed && removed.has(info.row)));
  }

  // A removed (non-token) winning cell plays its own "win" clip; the instant it
  // ends the static image goes invisible and the shared boom explosion plays
  // right after on that cell.
  let winBoomPlayed = false;
  const winThenClear = async (info) => {
    await withTimeout(playSymbolClipOnce(info, 'win'));
    info.img.style.visibility = 'hidden';
    if (!winBoomPlayed) {
      winBoomPlayed = true;
      Sound.playSfx('winBoom'); // WIN_Boom once per step, no matter how many cells clear
    }
    await withTimeout(playBoomExplosion(info));
  };

  // Multiplier tokens (x2/x3/x5): win-clip plays, then the token flies from its
  // cell to the multiplier badge (its actual cell still fades out normally
  // afterward via fadeOutRemoved — this only drives the flying ghost clone).
  const tokenThenFly = async (info, onArrive) => {
    await withTimeout(playSymbolClipOnce(info, 'win'));
    await flyTokenToBadge(info);
    onArrive();
  };

  const winPromise = (async () => {
    if (winInfos.length === 0 && step.tokens_consumed.length === 0) return;
    await wait(WIN_LANDING_DELAY_MS);
    Sound.playSfx('smallWin'); // WIN_Small on every winning combination
    showCascadeBanner(step.step_multiplier, step.step_win);

    // The badge reveals this step's multiplier progressively as each token
    // actually *arrives*, starting from the step's trail baseline.
    const tokenSum = step.tokens_consumed.reduce((sum, tok) => sum + tok.value, 0);
    let runningMultiplier = step.step_multiplier - tokenSum;
    if (currentMode() === 'base') updateMultiCounter(runningMultiplier);

    const chains = winInfos.map(winThenClear);
    for (const tok of step.tokens_consumed) {
      const info = cellInfos[tok.row * GRID_COLS + tok.col];
      if (!info) continue;
      chains.push(
        tokenThenFly(info, () => {
          runningMultiplier += tok.value;
          if (currentMode() === 'base') updateMultiCounter(runningMultiplier);
        }),
      );
    }

    await Promise.all(chains);
  })();

  // Bomb: sits still for BOMB_PRE_EXPLODE_MS after landing, then its own "win"
  // clip plays alone on its cell; once that settles, every affected cell (the
  // bomb's own cell + its whole row/column, `bomb.cleared`) loses its static
  // art. Runs concurrently with winPromise; celebrateStep waits for both.
  const bombPromise = (async () => {
    if (bombInfos.length === 0) return;
    await wait(BOMB_PRE_EXPLODE_MS);
    setTimeout(() => Sound.playSfx('bombExplode'), BOMB_SFX_AFTER_START_MS);

    await Promise.all(bombInfos.map((info) => withTimeout(playSymbolClipOnce(info, 'win'))));

    const blastInfos = new Set();
    for (const bomb of step.bombs_detonated) {
      for (const pos of bomb.cleared) {
        const info = cellInfos[pos.row * GRID_COLS + pos.col];
        if (info) blastInfos.add(info);
      }
    }
    for (const info of blastInfos) info.img.style.visibility = 'hidden';
    // The blast explosion fires on every affected cell at the same moment.
    await Promise.all([...blastInfos].map((info) => withTimeout(playBoomExplosion(info))));
  })();

  await Promise.all([winPromise, bombPromise]);
}

// Plain DOM/CSS ghost fly of a consumed multiplier token from its cell to the
// .multi-counter HUD element (well outside the avalanche grid, so viewport-
// space, not a Spine effect).
function flyTokenToBadge(info) {
  const badge = document.querySelector('.multi-counter');
  if (!badge) return Promise.resolve();

  const startRect = info.cell.getBoundingClientRect();
  const endRect = badge.getBoundingClientRect();
  const dx = endRect.left + endRect.width / 2 - (startRect.left + startRect.width / 2);
  const dy = endRect.top + endRect.height / 2 - (startRect.top + startRect.height / 2);

  const ghost = document.createElement('img');
  ghost.src = info.img.src;
  ghost.className = 'token-flight';
  ghost.style.left = `${startRect.left}px`;
  ghost.style.top = `${startRect.top}px`;
  ghost.style.width = `${startRect.width}px`;
  ghost.style.height = `${startRect.height}px`;
  ghost.style.setProperty('--tf-mid-x', `${dx * 0.3}px`);
  ghost.style.setProperty('--tf-mid-y', `${dy * 0.3}px`);
  ghost.style.setProperty('--tf-end-x', `${dx}px`);
  ghost.style.setProperty('--tf-end-y', `${dy}px`);
  document.body.appendChild(ghost);

  return new Promise((resolve) => {
    const done = () => {
      ghost.remove();
      resolve();
    };
    ghost.addEventListener('animationend', done, { once: true });
    setTimeout(done, TOKEN_FLIGHT_MS + 200);
  });
}

async function fadeOutRemoved(removedByCol) {
  for (const info of cellInfos) {
    if (!info) continue;
    const removed = removedByCol.get(info.col);
    if (removed && removed.has(info.row)) info.cell.classList.add('is-removing');
  }
  hideCascadeBanner();
  await wait(CASCADE_FADE_MS);
}

// Drops each affected column's survivors down to fill the gaps, refilling the
// vacated top slots with grid_after's new draws — collapse_and_refill's own
// "survivors drop to bottom, new draws prepended at top" semantics.
async function dropAndRefillStep(removedByCol, gridAfter) {
  const tasks = [];
  for (const [col, removedRows] of removedByCol.entries()) {
    tasks.push(dropAndRefillColumn(col, removedRows, gridAfter.map((row) => row[col])));
  }
  await Promise.all(tasks);
}

async function dropAndRefillColumn(col, removedRows, targetColumn) {
  const numRemoved = removedRows.size;
  if (numRemoved === 0) return;

  const removedInfos = [...removedRows].map((r) => cellInfos[r * GRID_COLS + col]).filter(Boolean);
  const survivorRows = [];
  for (let r = 0; r < GRID_ROWS; r++) {
    if (!removedRows.has(r)) survivorRows.push(r);
  }

  const newColInfos = new Array(GRID_ROWS);
  survivorRows.forEach((origRow, rank) => {
    const finalRow = numRemoved + rank;
    const info = cellInfos[origRow * GRID_COLS + col];
    info.row = finalRow;
    info.cell.style.top = `${rowTop(finalRow)}px`;
    newColInfos[finalRow] = info;
  });

  const colEl = reelCols[col];
  for (let finalRow = 0; finalRow < numRemoved; finalRow++) {
    const code = targetColumn[finalRow];
    const info = createCellNode(col, finalRow, code);
    info.cell.style.transition = 'none';
    info.cell.style.top = `${rowTop(finalRow - numRemoved)}px`;
    colEl.appendChild(info.cell);
    void info.cell.offsetHeight; // force reflow so the next `top` change transitions
    info.cell.style.transition = '';
    info.cell.style.top = `${rowTop(finalRow)}px`;
    newColInfos[finalRow] = info;
  }

  Sound.playSfx('cascadeDrop');
  await wait(CASCADE_DROP_MS);

  for (const info of removedInfos) info.cell.remove();
  for (let row = 0; row < GRID_ROWS; row++) {
    cellInfos[row * GRID_COLS + col] = newColInfos[row];
  }
}

async function playCascadeStep(step) {
  const removedByCol = collectStepRemovals(step);
  await celebrateStep(step, removedByCol);
  await fadeOutRemoved(removedByCol);
  await dropAndRefillStep(removedByCol, step.grid_after);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, false);
  }
  await wait(CASCADE_STEP_GAP_MS);
}

// Full round: paint the initial grid, then walk every cascade step in order
// (empty for a no-win spin). Returns the round's total win.
async function playAvalanche(data) {
  if (currentMode() === 'base') updateMultiCounter(1);
  await spinStartTransition(data.grid);

  const steps = (data.avalanche && data.avalanche.steps) || [];
  for (const step of steps) {
    await playCascadeStep(step);
  }
  return (data.avalanche && data.avalanche.total_win) || 0;
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

// --- Screen dim / free spins mode -------------------------------------------

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

// How long the "you won the bonus" popup holds on the blackout before the bonus
// screen is revealed behind it.
const BONUS_INTRO_HOLD_MS = 3000;

// base -> free-spins: black the screen out, play the bonusSpinsWin popup over
// the black, swap the bonus screen in behind the still-opaque black, then lift
// the blackout to reveal it.
async function enterBonusTransition(amount = 0) {
  const screen = document.getElementById('screen');
  pushScreenDim(true);
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  screen.dataset.mode = 'freespins';
  setBackground('freespins');
  setHero('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true);
}

function setFreeSpinsMode(active, amount = 0) {
  const screen = document.getElementById('screen');
  const next = active ? 'freespins' : 'base';
  if (screen.dataset.mode === next) return Promise.resolve();

  Sound.playMusic(next === 'freespins' ? 'bonus' : 'base');

  if (next === 'freespins') return enterBonusTransition(amount);

  return withScreenDim(
    async () => {
      screen.dataset.mode = next;
      setBackground(next);
      setHero(next);
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
}

// --- Popups (start/idle/end lifecycle; device-specific clip names) ----------

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

// The popup exports declare a giant setup-pose bbox (~2100px) dominated by the
// light rays, with the actual win-card only ~10% of it — so contain-fitting the
// whole thing to the screen (fit:1) renders the card quite small (product: "они
// выглядят меньше чем должны быть"). Scale the popup up so the card reads
// bigger; the rays simply overflow the screen (the intended light-burst). A
// straight fit multiplier (rather than re-centering on the card) is used on
// purpose: the card animates/bobs, so any static measurement of it mismatches
// the live pose and throws the popup off-centre — keeping the export's own
// centre is stable and stays correctly positioned.
const POPUP_FIT = 1.875; // 25% smaller than the previous 2.5 (product)

// Each popup export ships ONE self-contained clip per device — desk_full /
// mob_full — that plays the whole start -> hold -> end in a single shot. (The
// separate start/idle/end clips are the client's own "idle loops until the user
// clicks, then end" flow; we don't need that, and stitching them by hand made
// the popups misbehave.) So just play the one `*_full` clip and resolve when it
// settles. `ownDim` lets a caller that already owns the screen dim (the bonus
// intro) borrow the popup without its own dim. `holdMs` is unused now — the clip
// owns its own duration — but kept for call-site compatibility.
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
        popupResourceCache[key] = loadSpineResource(folder);
      }
      const resource = await popupResourceCache[key];

      const instance = resource.createInstance();
      instance.anchorEl = document.getElementById('screen');
      instance.fit = POPUP_FIT; // scale up (rays overflow) — see POPUP_FIT
      stage.addOverlay(instance);
      startPopupAmountTracking(instance, amount);

      instance.play(popupClip('full'), false);
      instance.onSettle = () => {
        instance.onSettle = null;
        stage.removeOverlay(instance);
        stopPopupAmountTracking();
        if (ownDim) popScreenDim(opaque);
        resolve();
      };
    })();
  });
}

// Win-tier / dev popups: own their (partial) screen dim.
function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');
  toggleBtn.addEventListener('click', () => {
    const next = document.getElementById('screen').dataset.mode === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 10);
    toggleBtn.textContent = `mode: ${next}`;
  });

  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 12345));
  });

  const fitToggleBtn = document.getElementById('devFitToggle');
  if (fitToggleBtn) {
    fitToggleBtn.textContent = 'fit-screen: on';
    fitToggleBtn.disabled = true;
  }
}

// The whole game is authored in a fixed design canvas matching the slot-builder
// manifest's own coordinate space (see css/golden-caravan.css) — desktop
// 1932x940, mobile portrait 780x1416 — and #stage is contain-scaled to fit the
// viewport.
const DESIGN = { desktop: { w: 1932, h: 940 }, mobile: { w: 780, h: 1416 } };

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function updateStageScale() {
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth || document.documentElement.clientWidth;
  const vh = screenEl.clientHeight || document.documentElement.clientHeight;
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  const scale = Math.min(vw / d.w, vh / d.h, 1);
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  document.documentElement.style.setProperty('--design-w', `${d.w}px`);
  document.documentElement.style.setProperty('--design-h', `${d.h}px`);
  readCellDims();
}

// --- Animated Spine backgrounds + base-mode hero character (all on bgStage,
// behind the reel panel), with a static PNG kept underneath as a fallback. ---
const BG_FOLDERS = {
  desktop: { base: 'bg_base_desk', freespins: 'bg_bonus_desk' },
  mobile: { base: 'bg_base_mob', freespins: 'bg_bonus_mob' },
};
// Per-folder loop clip name (most are "idle"; bg_bonus_desk ships "animation").
const BG_CLIPS = { bg_bonus_desk: 'animation' };
function bgClip(folder) {
  return BG_CLIPS[folder] || 'idle';
}
// Scale multiplier on top of the cover-fit. Mobile base is halved (product:
// "уменьши в два раза анимацию бг на моби бейс") — the static bg PNG underneath
// still fills the screen, only the animated Spine layer shrinks.
function bgFit(mode) {
  return isMobileLayout() && mode === 'base' ? 0.5 : 1;
}
// Vertical shift (fraction of the screen height, positive = up) on top of the
// cover-fit. Mobile base is raised 25% (product: "на моби бг анимацию поднять на
// 25%").
function bgVerticalOffset(mode) {
  return isMobileLayout() && mode === 'base' ? 0.25 : 0;
}
let bgStage = null;
let bgInstance = null;
let bgResourceCache = {};

function bgFallbackSrc(mode) {
  const desk = mode === 'base' ? 'bg_base_desk-2.png' : 'bg_bonus_desk-2.png';
  const mob = mode === 'base' ? 'bg_base_mob-2.jpg' : 'bg_bonus_mob-2.jpg';
  return `${ASSET_ROOT}/${isMobileLayout() ? mob : desk}`;
}

// Pick the fit axis that makes the skeleton COVER the anchor (fill the short
// side, overflow the long one).
function applyBgCoverFit() {
  if (!bgInstance) return;
  const anchor = document.getElementById('bgAnchor').getBoundingClientRect();
  const b = bgInstance.resource.bounds;
  if (!anchor.width || !anchor.height || !b.width || !b.height) return;
  bgInstance.fitMode = b.width / b.height > anchor.width / anchor.height ? 'height' : 'width';
}

let bgRenderToken = 0;

function setBackground(mode) {
  const folder = (isMobileLayout() ? BG_FOLDERS.mobile : BG_FOLDERS.desktop)[mode] || BG_FOLDERS.desktop.base;
  document.getElementById('bgLayer').src = bgFallbackSrc(mode);
  if (!bgStage) return;
  const key = folder;
  if (!bgResourceCache[key]) bgResourceCache[key] = loadSpineResource(`${ASSET_ROOT}/${folder}`, bgStage.assetManager);
  const myToken = ++bgRenderToken;
  bgResourceCache[key].then((resource) => {
    if (myToken !== bgRenderToken) return; // a newer setBackground already ran
    if (bgInstance) {
      bgStage.removeBase(bgInstance);
      bgInstance = null;
    }
    const instance = resource.createInstance();
    instance.anchorEl = document.getElementById('bgAnchor');
    instance.fit = bgFit(mode);
    instance.verticalOffsetRatio = bgVerticalOffset(mode);
    bgInstance = instance;
    applyBgCoverFit();
    bgStage.addBaseBehindAll(instance); // always behind the hero character
    instance.play(bgClip(folder), true);
  });
}

// Base-mode hero character (manifest bg_hero_animation -> hero_base "idle"),
// anchored to #heroAnchor inside #stage. Drawn on the MAIN `stage` (the
// foreground spine-canvas, above the reel panel/frame) so the camel sits in
// front of the machine (product: "жираф должен быть на первом плане"), not
// tucked behind it. addBaseBehindAll keeps it under any symbol win-clips that
// play later on the same stage. Only present in base mode (in the bonus the
// full-screen bonus background takes over that role).
let heroInstance = null;
let heroResource = null;
function setHero(mode) {
  if (!stage) return;
  if (mode !== 'base') {
    if (heroInstance) {
      stage.removeBase(heroInstance);
      heroInstance = null;
    }
    return;
  }
  if (heroInstance) return; // already showing
  if (!heroResource) heroResource = loadSpineResource(`${ASSET_ROOT}/hero_base`, stage.assetManager);
  heroResource.then((resource) => {
    if (currentMode() !== 'base' || heroInstance) return;
    const instance = resource.createInstance();
    instance.anchorEl = document.getElementById('heroAnchor');
    instance.fit = 1;
    heroInstance = instance;
    stage.addBaseBehindAll(instance); // foreground vs the reels, but under win-clips
    instance.play('idle', true);
  });
}

let lastMobile = null;

function handleResize() {
  updateStageScale();
  applyBgCoverFit();
  const nowMobile = isMobileLayout();
  if (nowMobile !== lastMobile) {
    lastMobile = nowMobile;
    // Device flipped: the animated background art differs per device — reload
    // it (the hero follows its anchor automatically, no reload needed).
    setBackground(currentMode());
  }
}

async function init() {
  await SlotCalibration.load(); // must resolve before renderInitialGrid's createCellNode calls applyStaticContentOffset
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  setTimeout(() => {
    lastMobile = isMobileLayout();
    updateStageScale();
    setBackground(currentMode());
    setHero(currentMode());
    applyBgCoverFit();
  }, 250);

  bgStage = new SpineEngine.SpineStage(document.getElementById('bgSpineCanvas'));
  stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  setBackground('base');
  setHero('base');
  setupDevPanel();

  renderInitialGrid(SYMBOL_LAYOUT);

  window.__slot = { stage, bgStage, cellInfos };
}

init();
