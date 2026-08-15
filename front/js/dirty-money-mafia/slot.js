// Dirty Money / MAFIA — game-specific wiring on top of spine-engine.js.
// The game was assembled in the slot-builder wizard, so this file is a hybrid
// of the two existing donors:
//   * layout/staging from ../golden-caravan/slot.js — everything lives in a
//     fixed design canvas matching the builder manifest's own coordinate space
//     (desktop 1932x940, mobile portrait 780x1416), contain-scaled as one unit
//     (see css/dirty-money-mafia.css).
//   * reel motion + line-win sequencing + expanding wild from
//     ../wild-western-story/slot.js — this is a 5x3 line-pay game (the
//     manifest's mechanics: line_pay, scatter, expanding_wild, free_spins,
//     bonus_buy), not an avalanche.
//
// Mechanics DROPPED (not in the manifest, no art/feature for them): coin
// multipliers, Hold & Win, collector, avalanche cascades, hero character.
//
// Asset notes (front/img/dirty-money-mafia/, uploaded through the wizard):
//   * every symbol folder holds animation.{atlas,json,png}; the resting tile is
//     static.png EXCEPT where the export kept its original filenames — see
//     SYMBOL_STATIC_OVERRIDE.
//   * `rare_red` shipped static.png ONLY (no Spine export) — it renders as a
//     plain tile and has no win animation; see SPINE_SYMBOLS.
//   * `WOF` (wheel of fortune) was uploaded but the builder layout never places
//     it and no wheel mechanic is enabled, so nothing references it yet.

const ASSET_ROOT = 'img/dirty-money-mafia';

// Checked against the delivered atlas PNGs: these exports use straight
// (non-premultiplied) alpha like East Discovery / Golden Caravan, so go through
// this wrapper rather than SpineResource.load directly or every soft glow edge
// blends against the wrong colour.
function loadSpineResource(folderPath) {
  return SpineEngine.SpineResource.load(stage.assetManager, folderPath, { premultipliedAlpha: false });
}

// code -> asset folder. Codes are a 1:1 contract with the backend seed
// (app/seed/dirty_money_mafia.py) — folder name == symbol code here.
const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wof: 'WOF',
  wild: 'wild',
  rare_red: 'rare_red',
  rare_yellow: 'rare_yellow',
  rare_blue: 'rare_blue',
  rare_green: 'rare_green',
  common_red: 'common_red',
  common_yellow: 'common_yellow',
  common_green: 'common_green',
  common_blue: 'common_blue',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// Codes eligible as random spin-loop filler — excludes scatter, wof and wild
// (all trigger symbols; blurring them past during a spin reads as a near-miss
// that never was).
const TRIGGER_CODES = new Set(['scatter', 'wof', 'wild']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));

// Every symbol now ships a Spine export (rare_red's landed last and had to be
// renamed from rare_red.{json,png,atlas.txt} to the animation.* names the
// loader expects — scripts/check_spine_assets.py --fix does the atlas page
// name). A code left out of this set falls back to a still tile whose "win
// animation" is just the dim/highlight beat, held for STATIC_WIN_HOLD_MS.
const SPINE_SYMBOLS = new Set(SYMBOL_CODES);
const STATIC_WIN_HOLD_MS = 900;

// Only scatter ships a live idle loop for the resting grid; every other symbol
// is a static tile until it wins.
const SPECIAL_SYMBOLS = new Set(['scatter']);

// Delivered clip inventory (read from each animation.json):
//   scatter        -> idle / landing / win
//   wild           -> move / win-small / win-big  (no idle of either size)
//   wof            -> a single clip literally named "animation"
//   everything else-> win
const SYMBOL_CLIPS = {
  wild: { win: 'win-small' },
  wof: { win: 'animation' },
};
const DEFAULT_CLIPS = { idle: 'idle', landing: 'landing', win: 'win' };
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || DEFAULT_CLIPS[kind];
}

// The resting tile isn't always static.png:
//   common_green -> the export kept "buba-win_0.png" for it
//   common_red   -> names are swapped in that export: "buba.png" is the ATLAS
//                   texture (the .atlas points at it) and animation.png is the
//                   200x200 resting tile
//   wild         -> static.png is a 300x580 canvas sized for the EXPANDED wild
//                   with the small symbol sitting in the middle; static-small.png
//                   is that square cropped out for the grid cell (derived asset)
const SYMBOL_STATIC_OVERRIDE = {
  common_green: 'buba-win_0.png',
  common_red: 'animation.png',
  wild: 'static-small.png',
};
function staticFileFor(code) {
  return SYMBOL_STATIC_OVERRIDE[code] || 'static.png';
}

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/popups/big_win`,
  epicWin: `${ASSET_ROOT}/popups/epic_win`,
  megaWin: `${ASSET_ROOT}/popups/mega_win`,
  bonusSpinsWin: `${ASSET_ROOT}/popups/free_spins_win`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/popups/free_spins_total_win`,
  buyFreeSpins: `${ASSET_ROOT}/popups/buy_free_spins`,
};
// Bone the win-amount overlay tracks. The exports carry no descriptive bone
// names, so this comes from each animation.json's slot->bone map: the empty
// number plate is the "*_input" slot, driven by bone2 in the win popups and
// bone3 in the buy-free-spins dialog.
const POPUP_AMOUNT_BONE = {
  bigWin: 'bone2',
  epicWin: 'bone2',
  megaWin: 'bone2',
  bonusSpinsWin: 'bone2',
  bonusSpinsTotalWin: 'bone2',
  buyFreeSpins: 'bone3',
};
// The popup skeletons declare a ~1342x755 setup box that's mostly the win card
// (unlike Golden Caravan's ray-dominated exports, which needed scaling UP).
// Contain-fit to the whole screen would run it edge to edge, so hold it a bit
// back from the borders.
const POPUP_FIT = 0.85;

const DIM_TRANSITION_MS = 320;
const REEL_LOOP_STEP_MS = 420;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 500;

// Matches the backend grid shape (5 reels x 3 rows, row-major grid[row][col])
// and the builder manifest's grid block.
const GRID_COLS = 5;
const GRID_ROWS = 3;

// Attract-mode layout shown before the first spin lands.
const SYMBOL_LAYOUT = [
  ['scatter', 'common_blue', 'rare_green', 'common_yellow', 'wof'],
  ['common_red', 'rare_blue', 'wild', 'rare_red', 'common_blue'],
  ['common_yellow', 'common_green', 'rare_yellow', 'common_red', 'rare_blue'],
];

// Grid geometry comes from CSS (--cell-w/--cell-h/--cell-gap-x/-y) so the
// desktop (190x190, gap 10) and mobile-portrait (140x140, gap 10) blocks — both
// straight from the builder manifest — stay the single source of truth.
let cellW = 190, cellH = 190, gapX = 10, gapY = 10;
let colStep = cellW + gapX, rowStep = cellH + gapY;
// Cached alongside the cell dims: --symbol-scale used to be re-read straight
// from getComputedStyle inside setCellSymbol, i.e. once per cell — 15 forced
// style recalcs on every landing, in the middle of the busiest frame of a spin.
// It only ever changes with the device breakpoint, so read it where the rest of
// the geometry is read.
let cachedSymbolScale = 1;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => parseFloat(cs.getPropertyValue(name)) || fallback;
  cellW = num('--cell-w', 190);
  cellH = num('--cell-h', 190);
  gapX = num('--cell-gap-x', 10);
  gapY = num('--cell-gap-y', 10);
  colStep = cellW + gapX;
  rowStep = cellH + gapY;
  cachedSymbolScale = num('--symbol-scale', 1);
}
function symbolScale() {
  return cachedSymbolScale;
}

let stage = null;
let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];
// Reel-height "big wild" overlays currently on screen (see revealExpandedWild).
// Cleared at the start of every spin, same lifecycle as the cell instances.
let expandedWildOverlays = [];
// True from the moment the reels start spinning until they've landed and any
// expanding wild has finished growing — the window in which nothing may tear
// the grid down from under the animation (see handleResize/flushDeviceRebuild).
let reelsBusy = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// A Spine clip's completion drives the spin's own sequencing, so one clip that
// never settles (its instance pulled off the stage, a bad export, ...) would
// hang the spin and leave the SPIN button disabled for good. Bound every such
// await — same guard golden-caravan uses for its cascade clips.
const CLIP_TIMEOUT_MS = 4000;
function withTimeout(promise, ms = CLIP_TIMEOUT_MS) {
  return Promise.race([promise, wait(ms)]);
}

function randomSymbolCode() {
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

// --- Symbol resources -------------------------------------------------------

const symbolResourceCache = {};

function getSymbolResource(code) {
  if (!SPINE_SYMBOLS.has(code)) return null;
  if (!symbolResourceCache[code]) {
    symbolResourceCache[code] = loadSpineResource(`${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}`);
  }
  return symbolResourceCache[code];
}

// --- Grid-cell footprint for a Spine instance --------------------------------
//
// `resource.bounds` (the exported setup-pose box) can't be used to size a grid
// instance here: it's the union of every slot including glow/VFX layers and, for
// wild, of BOTH sizes the export carries (setup pose = the grid-cell wild; the
// `move` clip raises bone "bone" ~198px to grow it reel-height). Measured:
// commons 202x202 (≈ their tile), but rare_yellow 300x300, scatter 335x300 and
// wild 316x684 — all against a 200/220px tile, so fitting to them rendered
// symbols up to 1.7x oversized (scatter visibly spilled out past the frame).
//
// What IS reliable is that these exports are authored in art pixels around the
// skeleton origin, and each symbol's static tile is that same art on a centred
// canvas. So use the tile's own natural size as the box, centred on the origin:
// world unit == 1 design px, and the Spine instance lands exactly where the
// static <img> it replaces was. Anything the clip scales up over its timeline
// still grows past that box, which is the point.
const staticSizeCache = {};
function getStaticSize(code) {
  if (!staticSizeCache[code]) {
    staticSizeCache[code] = new Promise((resolve) => {
      const probe = new Image();
      probe.addEventListener('load', () => resolve({ w: probe.naturalWidth, h: probe.naturalHeight }));
      probe.addEventListener('error', () => resolve({ w: 200, h: 200 }));
      probe.src = `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`;
    });
  }
  return staticSizeCache[code];
}

async function cellSpineBox(code) {
  const { w, h } = await getStaticSize(code);
  return { x: -w / 2, y: -h / 2, width: w, height: h };
}

// --- wild: picking the small variant out of the shared export ---------------
//
// The wild export holds both variants in ONE skeleton. The rigged art (wild_bg,
// wild_frame*, wild_hero*, wild_text, ...) IS the reel-height wild — `move`
// raises bone "bone" ~198px to grow it — and alongside it the export ships two
// flat, single-image GUIDE regions the artist left in: "wild-win-big_0" (the
// grown wild, 211x593) and "wild-move_0" (the grid tile, 210x205). Both `move`
// and `win-big` null the guides out; only the SETUP pose has "wild-win-big_0"
// attached, which is why an untouched instance dropped in a grid cell drew a
// full-height figure hanging out of it.
//
// There is no rigged "small" pose to use for the grid, so the cell renders the
// wild-move_0 guide (that flat image is exactly the tile art) with every rigged
// slot dropped, keeping the shared blik/smoke FX so `win-small` still sparkles.
// The fit box comes from that attachment's own world bounds — no hand-tuned
// offset, so a re-export can't silently shift it.
const WILD_SMALL_SLOT = 'wild-move_0';
const WILD_GUIDE_SLOTS = ['wild-move_0', 'wild-win-big_0'];
const WILD_SHARED_FX_SLOT = /^(blik|wild_smoke)/;

// Re-applied on every frame (see makeWildSmallInstance), so it resolves the
// slot list and the small attachment ONCE per instance rather than walking all
// 22 slots and regex-testing each name 60 times a second.
function makeWildSmallSkinApplier(skeleton) {
  const smallSlot = skeleton.findSlot(WILD_SMALL_SLOT);
  const smallAttachment = smallSlot && skeleton.getAttachment(smallSlot.data.index, WILD_SMALL_SLOT);
  const hide = skeleton.slots.filter(
    (slot) => slot.data.name !== WILD_SMALL_SLOT && !WILD_SHARED_FX_SLOT.test(slot.data.name),
  );
  return () => {
    if (smallSlot) smallSlot.setAttachment(smallAttachment);
    for (const slot of hide) slot.setAttachment(null);
  };
}

function attachmentBounds(skeleton, slotName) {
  const slot = skeleton.findSlot(slotName);
  const attachment = slot && slot.getAttachment();
  if (!attachment || typeof attachment.computeWorldVertices !== 'function') return null;
  const verts = new Float32Array(attachment.worldVerticesLength || 8);
  attachment.computeWorldVertices(slot, verts, 0, 2);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (let i = 0; i < verts.length; i += 2) {
    minX = Math.min(minX, verts[i]);
    maxX = Math.max(maxX, verts[i]);
    minY = Math.min(minY, verts[i + 1]);
    maxY = Math.max(maxY, verts[i + 1]);
  }
  if (!isFinite(minX)) return null;
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

// Grid-cell wild: small skin + its own measured box. Falls back to the static
// tile's footprint if the export ever stops shipping that slot.
function makeWildSmallInstance(resource, fallbackBox) {
  const instance = resource.createInstance();
  const applySkin = makeWildSmallSkinApplier(instance.skeleton);
  applySkin();
  instance.skeleton.updateWorldTransform();
  const box = attachmentBounds(instance.skeleton, WILD_SMALL_SLOT) || fallbackBox;
  // The clip re-asserts the setup pose's attachments on every apply(), so
  // re-hide the rigged slots each frame (same technique golden-caravan uses for
  // its boom export's additive layers).
  const baseUpdate = instance.update.bind(instance);
  instance.update = (delta, canvasEl) => {
    baseUpdate(delta, canvasEl);
    applySkin();
  };
  return { instance, box };
}

// Live per-symbol static-image nudge, written only by Anim Lab's "Калибровать"
// button (js/slot-calibration.js) — nothing is offset by default, so the static
// <img> is centred on its cell purely by .reel__cell's flex CSS (plus the
// --symbol-scale shrink the stylesheet applies).
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('dirty-money-mafia', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `scale(var(--symbol-scale, 1)) translate(${dx}px, ${dy}px)`;
}

// --- Grid -------------------------------------------------------------------

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  // A landing rebuilds 17 cells per column (3 result + 14 filler) x 5 columns —
  // ~85 fresh <img> in one burst, right when the reels are scrolling. Async
  // decoding keeps that off the main thread so the scroll doesn't hitch.
  img.decoding = 'async';
  img.src = `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`;
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

function teardownCellInstances() {
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  for (const overlay of expandedWildOverlays) {
    if (overlay.winLoopTimeout) clearTimeout(overlay.winLoopTimeout);
    stage.removeOverlay(overlay);
  }
  expandedWildOverlays = [];
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
  info.img.src = `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`;
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);

  const resourcePromise = getSymbolResource(code);
  if (!resourcePromise) return; // static-only symbol (rare_red)

  try {
    const [resource, staticBox] = await Promise.all([resourcePromise, cellSpineBox(code)]);
    const made =
      code === 'wild'
        ? makeWildSmallInstance(resource, staticBox)
        : { instance: resource.createInstance(), box: staticBox };
    const { instance, box } = made;
    if (info.anchor) {
      // Anchor sized to the fit box + fit == --symbol-scale means the world->px
      // mapping is exactly the scale the static <img> renders at.
      info.anchor.style.width = `${box.width}px`;
      info.anchor.style.height = `${box.height}px`;
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'dirty-money-mafia', code);
    }
    instance.anchorEl = info.anchor || info.cell;
    instance.fit = symbolScale();
    instance.boundsOverride = box;
    info.instance = instance;

    if (SPECIAL_SYMBOLS.has(code)) {
      // scatter: landing once, then its idle loop for as long as it sits there.
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      addCellBase(instance);
      instance.play(clipName(code, 'landing'), false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play(clipName(code, 'idle'), true);
      };
    }
  } catch (err) {
    console.warn(`Spine load failed for symbol "${code}":`, err);
  }
}

// --- Win presentation -------------------------------------------------------

function playWinAnimationOnce(info) {
  const { instance, img } = info;
  // rare_red has no Spine export — hold the highlight for a beat so the win
  // still reads, then hand back to the same sequencing every other symbol uses.
  if (!instance) return wait(STATIC_WIN_HOLD_MS);
  img.style.visibility = 'hidden';
  addCellBase(instance);
  return new Promise((resolve) => {
    instance.play(clipName(info.symbol, 'win'), false);
    instance.onSettle = () => {
      instance.onSettle = null;
      resolve();
    };
  });
}

function previewSymbolWin(info) {
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

// Clicking a wild cell previews the reel-height expansion; any other symbol
// loops its win animation.
function onCellClick(info, col) {
  if (info.symbol === 'wild') {
    previewBigWild(col);
  } else {
    previewSymbolWin(info);
  }
}

function setCellActive(info, active) {
  const { instance, img } = info;
  if (!instance) return;
  if (active) {
    img.style.visibility = 'hidden';
    addCellBase(instance);
  } else {
    stage.removeBase(instance);
    img.style.visibility = '';
  }
}

function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
}

let multiLineSequenceTimeout = null;

function playMultiLineWinSequence(groups, allWinInfos) {
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

  // Phase -1 plays every winning cell together, then the groups cycle one at a
  // time so overlapping paylines can be told apart.
  let groupIndex = -1;
  const step = () => {
    const activeInfos = groupIndex === -1 ? allWinInfos : groups[groupIndex];
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
  // Any win at all dims every cell that isn't part of it, so the combination
  // reads clearly against the rest of the grid.
  const winSet = new Set(allWinInfos);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, allWinInfos.length > 0 && !winSet.has(info));
  }

  const groups = buildWinGroups(lineWins, countWins);
  if (groups.length > 1) {
    playMultiLineWinSequence(groups, allWinInfos);
  } else {
    for (const info of allWinInfos) previewSymbolWin(info);
  }
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

// --- Reel motion ------------------------------------------------------------
//
// A reel = a .reel__col holding a taller .reel__strip that scrolls vertically;
// .reel__grid clips the whole block at the frame's opening, so a strip in
// motion disappears behind the golden border rather than past the frame.
//
// The looping strip is 6 cells — 3 fresh random ones stacked ABOVE the 3
// currently on screen — and rests shifted up by one screenful so the visible
// window shows the current symbols. The keyframe then scrolls it back down to
// 0, i.e. the random trio falls into view. (The donor games instead start the
// loop at translateY(0) and scroll down from there, which leaves the top of the
// window with nothing above row 0 to scroll in — a blank flash on every cycle.)

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  for (let col = 0; col < GRID_COLS; col++) {
    const { stripEl } = reelCols[col];
    stripEl.style.transition = 'none';
    stripEl.classList.remove('is-looping');

    const currentCodes = ReelMath.currentColumnCodes(cellInfos, GRID_COLS, GRID_ROWS, col).map(
      (code) => code || randomSymbolCode(),
    );

    stripEl.innerHTML = '';
    const randomTrio = [randomSymbolCode(), randomSymbolCode(), randomSymbolCode()];
    // Random trio first (above), current symbols below — the reverse of
    // ReelMath.buildLoopSequence's order, which is written for the
    // scroll-down-from-zero variant described above.
    for (const code of [...randomTrio, ...currentCodes]) {
      const { cell } = createCellNode(code);
      stripEl.appendChild(cell);
    }

    const screenful = rowStep * GRID_ROWS;
    stripEl.style.setProperty('--reel-loop-distance', `${screenful}px`);
    stripEl.style.setProperty('--reel-loop-duration', `${REEL_LOOP_STEP_MS}ms`);
    stripEl.style.transform = `translateY(${-screenful}px)`;
    void stripEl.offsetHeight;
    stripEl.classList.add('is-looping');
  }
}

function stopReelLoop() {
  reelsBusy = false;
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
  }
}

// Suspense treatment for a column flagged by ReelMath.collectAnticipationColumns:
// a plain LINEAR pre-roll (steady "still spinning" scroll, no easing so there's
// no mid-way plateau that reads as a false landing), followed by the exact same
// short eased landing every normal column uses.
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    setTimeout(() => {
      stripEl.classList.remove('is-looping');
      stripEl.style.transition = 'none';
      stripEl.innerHTML = '';

      // Final symbols at the top, filler stacked below them: the strip starts
      // shifted up so the filler is what's visible, then slides back down to 0
      // to reveal the result.
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
    }, delayMs);
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
    cell.addEventListener('click', () => onCellClick(info, col));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks);
}

// --- Expanding wild ---------------------------------------------------------
//
// The wild export bundles both sizes in one skeleton (see makeWildSmallInstance).
// When a reel expands, grow one reel-height overlay over that whole column via
// the `move` clip and fade the 3 small wild cells out underneath it.

const BIG_WILD_FIT = 1.0;

// Same problem as the grid tile, other end. `resource.bounds` (the declared
// 316x684 setup box) is 15% taller than the reel-height wild actually is, so
// fitting the overlay to it left the wild well short of the frame opening
// instead of filling it edge to edge the way East Discovery's / Wild Western's
// do. Measure the real thing instead — in its settled pose (frame 0 of
// `win-big` already carries move's +198 bone translate), and counting only the
// core art: the sparkle/smoke layers pulse well past the frame over the clip
// (592 -> 625 tall), so including them would make the fit wobble by ~6%.
const WILD_FX_SLOT = /^(blik|wild_smoke)/;

function computeBigWildBounds(resource) {
  try {
    const probe = new spine.Skeleton(resource.skeletonData);
    probe.setToSetupPose();
    const state = new spine.AnimationState(resource.animationStateData);
    state.setAnimation(0, 'win-big', true);
    state.update(0);
    state.apply(probe);
    for (const slot of probe.slots) {
      if (WILD_FX_SLOT.test(slot.data.name) || WILD_GUIDE_SLOTS.includes(slot.data.name)) slot.setAttachment(null);
    }
    probe.updateWorldTransform();
    const offset = new spine.Vector2();
    const size = new spine.Vector2();
    probe.getBounds(offset, size);
    if (!(size.x > 0 && size.y > 0)) return null;
    return { x: offset.x, y: offset.y, width: size.x, height: size.y };
  } catch (err) {
    console.warn('big-wild bounds compute failed:', err);
    return null;
  }
}

function fadeCellsToTransparent(infos, durationMs) {
  const targets = infos.filter((info) => info.instance);
  if (targets.length === 0) return Promise.resolve();
  const start = performance.now();
  return new Promise((resolve) => {
    function step(now) {
      const t = Math.min(1, (now - start) / durationMs);
      for (const info of targets) info.instance.skeleton.color.a = 1 - t;
      if (t < 1) {
        requestAnimationFrame(step);
      } else {
        for (const info of targets) {
          stage.removeBase(info.instance);
          info.instance = null;
        }
        resolve();
      }
    }
    requestAnimationFrame(step);
  });
}

// Sequence: `move` (the expansion, once) -> `win-big` looped if the reel is part
// of a winning combination, otherwise hold on move's final (grown) pose — this
// export ships no separate idle_big.
async function revealExpandedWild(col, { win = false } = {}) {
  const { stripEl } = reelCols[col];
  // The frame's actual opening, not .reel__grid-inner (the bare 3-row block):
  // the wild should reach the golden border top and bottom, same as the other
  // games' expanding wilds.
  const openingEl = document.querySelector('.reel__grid');
  const resource = await getSymbolResource('wild');
  if (resource.bigWildBounds === undefined) resource.bigWildBounds = computeBigWildBounds(resource);
  const overlay = resource.createInstance();
  // The setup pose still carries the flat "wild-win-big_0" guide image on top of
  // the rigged art — `move` nulls it, but not before the first frame draws.
  for (const name of WILD_GUIDE_SLOTS) {
    const slot = overlay.skeleton.findSlot(name);
    if (slot) slot.setAttachment(null);
  }
  overlay.anchorEl = stripEl;         // horizontal centre = this reel column
  overlay.heightAnchorEl = openingEl; // vertical extent = the frame opening
  overlay.fitMode = 'height';
  overlay.fit = BIG_WILD_FIT;
  overlay.boundsOverride = resource.bigWildBounds || resource.bounds;
  overlay.reelCol = col;
  overlay.winLoopTimeout = null;
  stage.addOverlay(overlay);
  expandedWildOverlays.push(overlay);

  const fadeInfos = [0, 1, 2].map((row) => cellInfos[row * GRID_COLS + col]).filter(Boolean);
  const fadeDone = fadeCellsToTransparent(fadeInfos, 450);

  Sound.playSfx('wildGrow');
  await withTimeout(
    new Promise((res) => {
      overlay.play('move', false);
      overlay.onSettle = () => {
        overlay.onSettle = null;
        res();
      };
    }),
  );
  await withTimeout(fadeDone);
  if (win) {
    Sound.playSfx('wildWin');
    overlay.play('win-big', true);
  }
  return overlay;
}

function celebrateExpandedWild(col, wildEvents, winningCols) {
  const grew = wildEvents.some((e) => e.reel === col && (e.event === 'expanded' || e.event === 'walked'));
  if (grew) return revealExpandedWild(col, { win: winningCols.has(col) });
  return Promise.resolve(null);
}

// Dev/testing preview: turn a whole column to wild, grow the big wild over it,
// hold, then restore the column to the attract layout. Clicking a wild cell
// previews the winning expansion; the dev "Big Wild" button the idle one.
let bigWildPreviewBusy = false;
async function previewBigWild(col = Math.floor(GRID_COLS / 2), win = true) {
  if (bigWildPreviewBusy || expandedWildOverlays.length) return;
  bigWildPreviewBusy = true;
  try {
    for (let row = 0; row < GRID_ROWS; row++) {
      const info = cellInfos[row * GRID_COLS + col];
      if (info) await setCellSymbol(info, 'wild');
    }
    const overlay = await revealExpandedWild(col, { win });
    if (!overlay) return;
    await wait(2200);
    if (overlay.winLoopTimeout) clearTimeout(overlay.winLoopTimeout);
    stage.removeOverlay(overlay);
    expandedWildOverlays = expandedWildOverlays.filter((o) => o !== overlay);
    for (let row = 0; row < GRID_ROWS; row++) {
      const info = cellInfos[row * GRID_COLS + col];
      if (info) await setCellSymbol(info, SYMBOL_LAYOUT[row][col]);
    }
  } finally {
    bigWildPreviewBusy = false;
  }
}

// Columns carrying a winning line/count this spin — drives win-big.
function winningColumnSet(lineWins, countWins) {
  const cols = new Set();
  for (const w of [...(lineWins || []), ...(countWins || [])]) {
    for (const pos of w.positions || []) cols.add(pos.col);
  }
  return cols;
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: a single reel is revealed, then the next, so the suspense reads.
async function landReels(grid, anticipationColumns = [], wildEvents = [], lineWins = [], countWins = []) {
  reelsBusy = true;
  try {
    await landReelsInner(grid, anticipationColumns, wildEvents, lineWins, countWins);
  } finally {
    reelsBusy = false;
    // An orientation flip that arrived mid-spin was parked instead of ripping
    // the grid out from under the landing — apply it now.
    await flushDeviceRebuild();
  }
}

async function landReelsInner(grid, anticipationColumns, wildEvents, lineWins, countWins) {
  teardownCellInstances();
  const winningCols = winningColumnSet(lineWins, countWins);

  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const delay = col * REEL_LAND_STAGGER_MS;
    leadTasks.push(
      landReel(col, finalCodes, delay, false)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes))
        .then(() => celebrateExpandedWild(col, wildEvents, winningCols)),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');

  // Freeze every remaining reel right away — landing one at a time isn't enough
  // on its own if the ones still waiting their turn keep spinning in the
  // background. landReel() rebuilds each column from scratch when its turn
  // comes, so freezing here doesn't need to leave them in any given state.
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
    await celebrateExpandedWild(col, wildEvents, winningCols);
  }
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
    // Opaque dim = the base<->bonus transition. Any still-looping win symbol is
    // drawn on the same canvas as the popup, so #screenDim (a DOM element)
    // can't darken it without also covering the popup — tint the canvas's base
    // layer directly instead; overlays (the popup) stay bright.
    stage.setBaseDim(true);
    // setBaseDim only darkens to 25%, which still reads clearly against a full
    // blackout — and scatter's idle loop means there's practically always a
    // base instance on screen, so it looked like a lone symbol floating in the
    // void. Pull the cells off the canvas outright for the blackout. (Tinting
    // their skeleton alpha instead doesn't survive: addBase/_applyBaseDim
    // rewrite skeleton.color wholesale.)
    detachedBaseInstances = cellInfos
      .filter((info) => info && info.instance && stage.baseInstances.includes(info.instance))
      .map((info) => info.instance);
    for (const instance of detachedBaseInstances) stage.removeBase(instance);
  }
}

// Cell instances pulled off the canvas by an opaque dim, restored on pop.
let detachedBaseInstances = [];

// Every cell instance goes on the canvas through here so one that appears while
// the blackout is up (a scatter landing mid-transition) is held back with the
// rest instead of popping into the void.
function addCellBase(instance) {
  if (opaqueDimActiveCount > 0) {
    if (!detachedBaseInstances.includes(instance)) detachedBaseInstances.push(instance);
    return;
  }
  stage.addBase(instance);
}

function popScreenDim(opaque = false) {
  dimActiveCount = Math.max(0, dimActiveCount - 1);
  if (dimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-active');
  if (opaque) {
    opaqueDimActiveCount = Math.max(0, opaqueDimActiveCount - 1);
    if (opaqueDimActiveCount === 0) {
      document.getElementById('screenDim').classList.remove('is-opaque');
      stage.setBaseDim(false);
      // Only put back what's still on the grid — a cell the transition replaced
      // meanwhile has had its instance torn down already.
      const live = new Set(cellInfos.filter((info) => info && info.instance).map((info) => info.instance));
      for (const instance of detachedBaseInstances) {
        if (live.has(instance)) stage.addBase(instance);
      }
      detachedBaseInstances = [];
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

function currentMode() {
  return document.getElementById('screen').dataset.mode || 'base';
}

// Swaps the on-screen mode (background art) for `next`. Shared by the plain
// leave-bonus dim and the enter-bonus intro so the two never drift apart.
function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
}

// How long the "you won the bonus" popup holds on the blackout before the bonus
// screen is revealed behind it.
const BONUS_INTRO_HOLD_MS = 3000;

async function enterBonusTransition(amount = 0) {
  pushScreenDim(true); // opaque blackout in
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true); // reveal the bonus screen
}

function setFreeSpinsMode(active, amount = 0) {
  const next = active ? 'freespins' : 'base';
  if (currentMode() === next) return Promise.resolve();

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

// --- Wheel of Fortune -------------------------------------------------------
//
// Opened when the server reports 3+ wof symbols (spin response's
// `wheel_of_fortune`). The prize is ALREADY decided server-side — this only
// labels the drum from `segments`, waits for the player to hit SPIN, and
// eases the drum onto `segment_index`.

// The drum art has 8 bullet slots, evenly spaced from 12 o'clock, and the
// pointer sits at 3 o'clock — so segment i is under the pointer once the drum
// has turned (90 - i*45) degrees. Both constants are dictated by the artwork.
const WOF_SEGMENT_COUNT = 8;
const WOF_POINTER_ANGLE = 90;
const WOF_SPIN_TURNS = 5; // full turns before settling, for the wind-up
const WOF_SPIN_MS = 4200;
const WOF_PRIZE_HOLD_MS = 2200;

// The wof symbols pay nothing, so the server never lists them in
// `winning_cells` and playWinCells skips them — play their own clip here so
// the trigger reads before the wheel takes over the screen.
async function celebrateWheelTrigger() {
  const triggers = cellInfos.filter((info) => info && info.symbol === 'wof');
  if (triggers.length === 0) return;
  const winSet = new Set(triggers);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, !winSet.has(info));
  }
  await Promise.all(triggers.map((info) => withTimeout(playWinAnimationOnce(info))));
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, false);
  }
}

function wofSegmentLabel(segment) {
  return segment.type === 'free_spins' ? 'FREE SPINS' : `x${segment.value}`;
}

function renderWheelLabels(segments) {
  const labelsEl = document.getElementById('wofLabels');
  labelsEl.innerHTML = '';
  segments.slice(0, WOF_SEGMENT_COUNT).forEach((segment, i) => {
    const spoke = document.createElement('div');
    spoke.className = `wof__label${segment.type === 'free_spins' ? ' wof__label--fs' : ''}`;
    spoke.style.setProperty('--i', String(i));
    const text = document.createElement('span');
    text.textContent = wofSegmentLabel(segment);
    spoke.appendChild(text);
    labelsEl.appendChild(spoke);
  });
}

// Resolves once the wheel has landed and its prize has been shown, so the
// caller can sequence the payout/bonus entry after it.
function playWheelOfFortune(wheel) {
  const popup = document.getElementById('wofPopup');
  const rotor = document.getElementById('wofRotor');
  const spinBtn = document.getElementById('wofSpin');
  const prizeEl = document.getElementById('wofPrize');
  if (!popup || !wheel) return Promise.resolve();

  renderWheelLabels(wheel.segments || []);
  prizeEl.hidden = true;
  prizeEl.classList.remove('is-visible');
  spinBtn.disabled = false;
  // Reset without animating back through 5 turns.
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

      const target = WOF_SPIN_TURNS * 360 + WOF_POINTER_ANGLE - wheel.segment_index * (360 / WOF_SEGMENT_COUNT);
      rotor.style.transition = `transform ${WOF_SPIN_MS}ms cubic-bezier(0.16, 0.9, 0.2, 1)`;
      rotor.style.setProperty('--wof-angle', `${target}deg`);

      let settled = false;
      const finish = async () => {
        if (settled) return;
        settled = true;
        rotor.removeEventListener('transitionend', onEnd);

        const segment = (wheel.segments || [])[wheel.segment_index];
        prizeEl.textContent =
          wheel.prize_type === 'free_spins'
            ? 'FREE SPINS!'
            : `${segment ? wofSegmentLabel(segment) : ''} — ${Number(wheel.win_amount).toLocaleString('en-US')}`;
        prizeEl.hidden = false;
        void prizeEl.offsetHeight;
        prizeEl.classList.add('is-visible');
        Sound.playSfx(wheel.prize_type === 'free_spins' ? 'bigWin' : 'smallWin');

        await wait(WOF_PRIZE_HOLD_MS);
        popup.classList.remove('is-open');
        Sound.playSfx('popupClose');
        await wait(DIM_TRANSITION_MS);
        popup.hidden = true;
        resolve();
      };
      const onEnd = (event) => {
        if (event.target === rotor && event.propertyName === 'transform') finish();
      };
      rotor.addEventListener('transitionend', onEnd);
      // Same belt-and-braces fallback the reel landing uses: a transitionend
      // that never fires (tab hidden mid-spin, ...) must not strand the spin.
      setTimeout(finish, WOF_SPIN_MS + 400);
    };
    spinBtn.addEventListener('click', start);
  });
}

// --- Popups -----------------------------------------------------------------

const popupResourceCache = {};
let popupAmountRaf = null;

function worldToScreen(worldX, worldY, canvasEl) {
  const dpr = window.devicePixelRatio || 1;
  const canvasRect = canvasEl.getBoundingClientRect();
  const cx = worldX + canvasEl.width / 2;
  const cy = canvasEl.height / 2 - worldY;
  return { left: canvasRect.left + cx / dpr, top: canvasRect.top + cy / dpr };
}

function startPopupAmountTracking(instance, key, amount) {
  const canvasEl = document.getElementById('spineCanvas');
  const el = document.getElementById('popupAmount');
  el.textContent = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');

  const boneName = POPUP_AMOUNT_BONE[key];
  const tick = () => {
    const bone = boneName && instance.skeleton.findBone(boneName);
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

// Core popup lifecycle (start -> idle hold -> end). Resolves only once the popup
// has FULLY played out, so a caller can sequence work after it. `ownDim` lets a
// caller that already owns the screen dim (the bonus intro) borrow the popup
// without it pushing/popping its own.
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
      // Portrait doubles the popup (product). The wheel-of-fortune drum is
      // its own DOM overlay, not a playPopupSequence popup — deliberately
      // unaffected (product: "кроме ВОФ попапа").
      instance.fit = POPUP_FIT * (isMobileLayout() ? 2 : 1);
      stage.addOverlay(instance);
      startPopupAmountTracking(instance, key, amount);

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

// Win-tier / dev popups: own their (partial) screen dim.
function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Dev panel --------------------------------------------------------------

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');
  toggleBtn.addEventListener('click', () => {
    const next = currentMode() === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 10); // demo spins count for the intro popup
    toggleBtn.textContent = `mode: ${next}`;
  });

  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 12345));
  });

  // Dev button previews the non-winning expansion (move, then hold); clicking a
  // wild cell previews the winning one (move -> win-big).
  const bigWildBtn = document.getElementById('devBigWild');
  if (bigWildBtn) bigWildBtn.addEventListener('click', () => previewBigWild(Math.floor(GRID_COLS / 2), false));
}

// --- Viewport / background --------------------------------------------------
//
// The whole game is authored in the builder manifest's own design canvas and
// #stage is contain-scaled to fit the viewport.
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

function bgSrcFor(mode) {
  if (isMobileLayout()) {
    return mode === 'base' ? `${ASSET_ROOT}/base_mob_bg.png` : `${ASSET_ROOT}/bonus_mob_bg.png`;
  }
  return mode === 'base' ? `${ASSET_ROOT}/base_desk_bg.png` : `${ASSET_ROOT}/bonus_desk_bg.png`;
}

function updateBgForLayout() {
  document.getElementById('bgLayer').src = bgSrcFor(currentMode());
}

let lastMobile = null;
let pendingDeviceRebuild = false;

// Cell geometry differs per device (190px vs 140px cells) and every cell/strip
// carries pixel positions, so flipping orientation has to rebuild the grid onto
// the new pitch. It must NEVER do that mid-spin, though: the rebuild tears down
// every cell instance AND the expanding-wild overlay, so the `move` clip the
// spin is awaiting can no longer complete — landReels then hangs forever and
// the spin button stays disabled for good. (Hit for real: a spurious portrait/
// landscape flip during a spin killed the game on the expanding wild.) Defer to
// the end of the spin instead — see flushDeviceRebuild's call in landReels.
async function handleResize() {
  updateStageScale();
  updateBgForLayout();
  const nowMobile = isMobileLayout();
  if (nowMobile === lastMobile) return;
  lastMobile = nowMobile;
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
}

async function init() {
  await SlotCalibration.load(); // must resolve before buildReelGrid's applyStaticContentOffset
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  updateBgForLayout();
  window.addEventListener('resize', handleResize);

  buildReelGrid();
  stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  setupDevPanel();

  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));

  window.__slot = { stage, cellInfos };
}

init();
