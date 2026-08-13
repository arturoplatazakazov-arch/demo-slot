// Multi Fruits Story — game-specific wiring on top of spine-engine.js.
// Second game assembled in the slot-builder wizard, so this file starts from
// ../dirty-money-mafia/slot.js (the first one): everything lives in a fixed
// design canvas matching the builder manifest's coordinate space (desktop
// 1932x940, mobile portrait 780x1416), contain-scaled as one unit — see
// css/multi-fruits-story.css — with scrolling reel columns clipped at the
// frame's opening.
//
// Differences from that donor, all straight out of this game's manifest:
//   * the grid is 3x3, not 5x3 (first 3-reel game in the project), and the
//     manifest's 3 paylines are the three rows;
//   * mechanics are line_pay + scatter + free_spins + bonus_buy only — no
//     expanding wild (the wild export ships no reel-height pose), no wheel of
//     fortune, no coin multiplier, no Hold & Win, no avalanche, no hero;
//   * the desktop screens carry a decor.spine background (bg_base_desk /
//     bg_bonus_desk), rendered on its own canvas the way ../golden-caravan does.
//     Portrait has no such object — there the static PNG is the background.
//
// Asset notes (front/img/multi-fruits-story/, uploaded through the wizard):
//   * every symbol folder holds animation.{atlas,json,png} + static.png (the
//     resting tile), all on a 300x300 canvas;
//   * `bell` shipped a Spine export with ZERO animations in it; its win clip is
//     a graft of diamond's — see front/img/multi-fruits-story/README.md;
//   * the win popups carry BOTH a desktop and a portrait cut of start/idle/end,
//     with the mobile ones named inconsistently across exports (mob_start vs
//     mob-start) — see popupClip().

const ASSET_ROOT = 'img/multi-fruits-story';

// Checked against the delivered atlas PNGs: these exports declare no `pma`
// flag, i.e. straight (non-premultiplied) alpha like the other builder game, so
// go through this wrapper rather than SpineResource.load directly or every soft
// glow edge blends against the wrong colour. `assetManager` is passed
// explicitly for the background stage, which owns a separate GL context.
function loadSpineResource(folderPath, assetManager = null) {
  return SpineEngine.SpineResource.load(assetManager || stage.assetManager, folderPath, {
    premultipliedAlpha: false,
  });
}

// code -> asset folder. Codes are a 1:1 contract with the backend seed
// (app/seed/multi_fruits_story.py) — folder name == symbol code here.
const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild',
  777: '777',
  diamond: 'diamond',
  bell: 'bell',
  klubnika: 'klubnika',
  grusha: 'grusha',
  vinograd: 'vinograd',
  limon: 'limon',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// Codes eligible as random spin-loop filler — excludes scatter and wild (both
// trigger/substitute symbols; blurring them past during a spin reads as a
// near-miss that never was).
const TRIGGER_CODES = new Set(['scatter', 'wild']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));

// Every symbol animates. `bell` very nearly didn't: its delivered export had no
// `animations` block at all, and its win clip is a hand-assembled graft of
// diamond's (identical rig) — see front/img/multi-fruits-story/README.md, which
// also says how to drop it when a real re-export lands. A code left out of this
// set falls back to a still tile whose "win animation" is just the
// dim/highlight beat, held for STATIC_WIN_HOLD_MS.
const SPINE_SYMBOLS = new Set(SYMBOL_CODES);
const STATIC_WIN_HOLD_MS = 900;

// Symbols that ship a live idle loop for the resting grid (landing -> idle);
// everything else is a static tile until it wins. Both special symbols here
// carry idle + landing clips.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// Delivered clip inventory (read from each animation.json):
//   scatter        -> idle / landing / win
//   wild           -> idle / landing / show / win  (`show` is the multiplier
//                     reveal — see the multiplier-wild section below)
//   fruits/777/    -> win   (grusha also ships a second variant, "win2")
//   diamond
//   bell           -> win   (grafted from diamond's, see SPINE_SYMBOLS)
const DEFAULT_CLIPS = { idle: 'idle', landing: 'landing', win: 'win' };
const SYMBOL_CLIPS = {};
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || DEFAULT_CLIPS[kind];
}

// --- Multiplier wild --------------------------------------------------------
//
// Every WILD that lands rolls a multiplier server-side (app/features/
// multiplier_wild.py, reported as `multiplier_wilds` on the spin response): it
// either stays a plain WILD or turns into x2/x3/x5/x7, and multiplies the
// payline it takes part in.
//
// The export carries the whole thing in its skins. Slot `text2` holds the
// neutral WILD lettering from the default skin; slot `text` is EMPTY in the
// default skin and each named skin below fills it with one variant's art. The
// clips then do the rest: `landing` keeps `text` hidden (so the symbol always
// lands as a plain WILD), `show` crossfades WILD out and the skin's lettering
// in, and `idle`/`win` hold WILD at zero alpha so only the variant reads.
//
// Which means: a skin must ALWAYS be set. With none, the default skin's empty
// `text` plus idle's zero-alpha `text2` leaves the wild with no lettering at
// all — which is exactly how it looked before this feature existed.
const WILD_SKINS = { 1: 'wild', 2: 'x2', 3: 'x3', 5: 'x5', 7: 'x7' };
const WILD_REVEAL_CLIP = 'show';
// Landed multipliers for the current grid, position key -> multiplier. Filled
// from the spin response before the reels land so each wild cell can pick its
// skin the moment it's built.
let wildMultipliers = new Map();
const wildKey = (row, col) => `${row}:${col}`;

function setWildMultipliers(entries) {
  wildMultipliers = new Map((entries || []).map((w) => [wildKey(w.row, w.col), w.multiplier]));
}

// Attract mode and the dev panel have no server response behind them, so the
// wild falls back to a plain one rather than rendering blank.
function wildMultiplierAt(row, col) {
  return wildMultipliers.get(wildKey(row, col)) || 1;
}

function applyWildSkin(instance, multiplier) {
  const skin = WILD_SKINS[multiplier] || WILD_SKINS[1];
  instance.skeleton.setSkinByName(skin);
  // setSkinByName alone leaves the previous skin's attachments on the slots —
  // the setup pose is what actually resolves the new skin's `text`.
  instance.skeleton.setSlotsToSetupPose();
}

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/popup_big_win`,
  epicWin: `${ASSET_ROOT}/popup_epic_win`,
  megaWin: `${ASSET_ROOT}/popup_mega_win`,
  bonusSpinsWin: `${ASSET_ROOT}/popup_bonus_spins_win`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/popup_bonus_spins_total_win`,
  buyFreeSpins: `${ASSET_ROOT}/popup_buy_bonus_spins`,
};
// Bone the win-amount overlay tracks. From each animation.json's slot->bone
// map: the number plate is the "popup_big_win_dengi" slot — deliberately
// EMPTY (no attachment) in every win popup, i.e. the hole the amount goes in —
// driven by bone "bg_dengi".
const POPUP_AMOUNT_BONE = {
  bigWin: 'bg_dengi',
  epicWin: 'bg_dengi',
  megaWin: 'bg_dengi',
  bonusSpinsWin: 'bg_dengi',
  bonusSpinsTotalWin: 'bg_dengi',
  // The buy dialog is the exception: its number slot ships BAKED-IN art (a
  // "3", placeholder from the art pass), so the live price can only go there
  // once that attachment is dropped — see POPUP_HIDDEN_SLOTS.
  buyFreeSpins: 'bone',
};
// Attachments to drop when a popup is instantiated: placeholder numbers the
// artist baked into the card, which would otherwise sit under the live amount.
// Four of the five win popups leave their `popup_big_win_dengi` slot EMPTY (the
// hole the amount goes in) — mega win is the one that shipped art in it, a
// "1 000 000 USD" plaque. No clip in either export keys the slot's ATTACHMENT
// (only its rgba), so clearing it once at creation sticks — no need to re-apply
// per frame.
const POPUP_HIDDEN_SLOTS = {
  buyFreeSpins: ['popup_buy_bonus_spins_numb'],
  megaWin: ['popup_big_win_dengi'],
};
// The five win popups are authored on the full design canvas (~1931x942), so
// fit 1 lands them exactly over the screen on desktop. Portrait doubles them
// (product): the export's box is landscape, so contain-fitting it into a narrow
// screen is driven by the width and leaves the card small in a tall viewport —
// at fit 2 it reads at the size it does on desktop, and the light rays simply
// overflow, which is the intended burst.
//
// The buy dialog is deliberately NOT doubled (product: "все кроме бай бонус
// спинс"). It's a small 760x653 card rather than a full-canvas composition, so
// contain-fitting it already fills a good part of the screen; it carries its own
// fraction instead, slightly larger in portrait for the same narrow-width
// reason.
const POPUP_FIT = { buyFreeSpins: { desktop: 0.5, mobile: 0.85 } };
const POPUP_FIT_DEFAULT = { desktop: 1, mobile: 2 };
function popupFit(key) {
  const fit = POPUP_FIT[key] || POPUP_FIT_DEFAULT;
  return isMobileLayout() ? fit.mobile : fit.desktop;
}

// Each win popup ships a portrait cut of start/idle/end alongside the desktop
// one, but the exports disagree on how to spell it (mob_start / mob-start), and
// the buy dialog has no portrait cut at all. Resolve against the skeleton's own
// animation list instead of hardcoding per popup, so a re-export that settles on
// one spelling keeps working.
function popupClip(resource, kind) {
  const names = new Set(resource.skeletonData.animations.map((a) => a.name));
  const candidates = isMobileLayout() ? [`mob_${kind}`, `mob-${kind}`, kind] : [kind];
  return candidates.find((name) => names.has(name)) || kind;
}

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 100; // 0.1s между колонками (product), отсчёт от конца очистки
const WIN_LOOP_PAUSE_MS = 500;

// Matches the backend grid shape (3 reels x 3 rows, row-major grid[row][col])
// and the builder manifest's grid block.
const GRID_COLS = 3;
const GRID_ROWS = 3;

// Attract-mode layout shown before the first spin lands.
const SYMBOL_LAYOUT = [
  ['klubnika', 'scatter', 'limon'],
  ['diamond', 'wild', 'vinograd'],
  ['limon', 'grusha', '777'],
];

// Grid geometry comes from CSS (--cell-w/--cell-h/--cell-gap-x/-y) so the
// desktop (268x230, gap 10/0) and mobile-portrait (200x200, gap 8/0) blocks —
// both straight from the builder manifest — stay the single source of truth.
let cellW = 268, cellH = 230, gapX = 10, gapY = 0;
let colStep = cellW + gapX, rowStep = cellH + gapY;
// Cached alongside the cell dims: --symbol-scale would otherwise be re-read
// from getComputedStyle once per cell, i.e. a forced style recalc per cell in
// the middle of the busiest frame of a spin. It only changes with the device
// breakpoint, so read it where the rest of the geometry is read.
let cachedSymbolScale = 1;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => {
    const value = parseFloat(cs.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  cellW = num('--cell-w', 268);
  cellH = num('--cell-h', 230);
  gapX = num('--cell-gap-x', 10);
  gapY = num('--cell-gap-y', 0);
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
// True from the moment the reels start spinning until they've landed — the
// window in which nothing may tear the grid down from under the animation
// (see handleResize/flushDeviceRebuild).
let reelsBusy = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// A Spine clip's completion drives the spin's own sequencing, so one clip that
// never settles (its instance pulled off the stage, a bad export, ...) would
// hang the spin and leave the SPIN button disabled for good. Bound every such
// await — same guard the other games use.
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
// instance: it's the union of every slot including glow/VFX layers, and these
// exports declare anywhere from 248x241 (wild) to 613x613 (777, diamond, bell)
// against a 300x300 tile — fitting to it would render symbols at wildly
// different sizes.
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
      probe.addEventListener('error', () => resolve({ w: 300, h: 300 }));
      probe.src = `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/static.png`;
    });
  }
  return staticSizeCache[code];
}

async function cellSpineBox(code) {
  const { w, h } = await getStaticSize(code);
  return { x: -w / 2, y: -h / 2, width: w, height: h };
}

// Live per-symbol static-image nudge, written only by Anim Lab's "Калибровать"
// button (js/slot-calibration.js) — nothing is offset by default, so the static
// <img> is centred on its cell purely by .reel__cell's flex CSS (plus the
// --symbol-scale shrink the stylesheet applies).
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('multi-fruits-story', code);
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
  // A landing rebuilds 17 cells per column (3 result + 14 filler) x 3 columns —
  // ~50 fresh <img> in one burst, right when the reels are scrolling. Async
  // decoding keeps that off the main thread so the scroll doesn't hitch.
  img.decoding = 'async';
  img.src = `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/static.png`;
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
      // row/col ride along on the info: the wild needs them to look up the
      // multiplier the server rolled for this cell (see setCellSymbol).
      const info = { symbol, row, col, cell, img, anchor, instance: null, winLoopTimeout: null };
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
  info.img.src = `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/static.png`;
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);

  const resourcePromise = getSymbolResource(code);
  if (!resourcePromise) return; // static-only symbol (bell)

  try {
    const [resource, staticBox] = await Promise.all([resourcePromise, cellSpineBox(code)]);
    const instance = resource.createInstance();
    if (info.anchor) {
      // Anchor sized to the fit box + fit == --symbol-scale means the world->px
      // mapping is exactly the scale the static <img> renders at.
      info.anchor.style.width = `${staticBox.width}px`;
      info.anchor.style.height = `${staticBox.height}px`;
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'multi-fruits-story', code);
    }
    instance.anchorEl = info.anchor || info.cell;
    instance.fit = symbolScale();
    instance.boundsOverride = staticBox;
    info.instance = instance;

    if (code === 'wild') {
      // Pick the variant BEFORE the first frame draws, or the setup pose shows
      // the previous skin's lettering for a frame.
      applyWildSkin(instance, wildMultiplierAt(info.row, info.col));
    }

    if (SPECIAL_SYMBOLS.has(code)) {
      // scatter/wild: landing once, then the idle loop for as long as they sit
      // there. The wild slips its multiplier reveal in between — it lands as a
      // plain WILD, `show` crossfades in whatever it rolled, and idle holds
      // that. A wild that stayed x1 plays the same beat with the same WILD
      // lettering on both sides of the crossfade, which is what the art
      // intends (there's a dedicated `wild` skin for exactly this case).
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      addCellBase(instance);
      const queue = code === 'wild' ? [WILD_REVEAL_CLIP, clipName(code, 'idle')] : [clipName(code, 'idle')];
      const playNext = () => {
        const next = queue.shift();
        const last = queue.length === 0;
        instance.onSettle = last ? null : playNext;
        instance.play(next, last); // only the final clip (idle) loops
      };
      instance.play(clipName(code, 'landing'), false);
      instance.onSettle = playNext;
    }
  } catch (err) {
    console.warn(`Spine load failed for symbol "${code}":`, err);
  }
}

// --- Win presentation -------------------------------------------------------

function playWinAnimationOnce(info) {
  const { instance, img } = info;
  // bell has no Spine clip — hold the highlight for a beat so the win still
  // reads, then hand back to the same sequencing every other symbol uses.
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
// motion disappears behind the border rather than past the frame.
//
// The looping strip is 6 cells — 3 fresh random ones stacked ABOVE the 3
// currently on screen — and rests shifted up by one screenful so the visible
// window shows the current symbols. The keyframe then scrolls it back down to
// 0, i.e. the random trio falls into view.

// No spinning-loop phase (same clear-drop + land-from-top as every other
// reel game, product-approved): on spin press the resting symbols drop out
// of view downward, the reel stands empty while the server answers, and the
// finals fall in from the top via landReel's usual eased landing. landReel
// awaits reelClearDone so no column starts landing mid-drop; the per-column
// stagger counts from the END of the clear.
const REEL_CLEAR_MS = 260;

let reelLoopGeneration = 0; // invalidates a pending clear when a newer spin supersedes it
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  reelsBusy = true;
  teardownCellInstances();
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    // Two rAFs: one full frame so transition:none + the transform reset
    // apply before the drop transition starts.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (gen !== reelLoopGeneration) return resolve();
      for (const { stripEl } of reelCols) {
        stripEl.style.transition = `transform ${REEL_CLEAR_MS}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
        stripEl.style.transform = `translateY(${rowStep * (GRID_ROWS + 1)}px)`;
      }
      setTimeout(resolve, REEL_CLEAR_MS + 40);
    }));
  });
}

function stopReelLoop() {
  // Error-path cleanup: put the strips back before re-applying the last grid.
  reelsBusy = false;
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
}

// Suspense treatment for a column flagged by ReelMath.collectAnticipationColumns
// (here: the last reel, when the first two already hold 2 of the 3 scatters a
// trigger needs): a plain LINEAR pre-roll (steady "still spinning" scroll, no
// easing so there's no mid-way plateau that reads as a false landing), followed
// by the exact same short eased landing every normal column uses.
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    (async () => {
      // Каскад считается от конца очистки, не от нажатия — иначе колонки с
      // задержкой меньше длительности очистки просыпаются одновременно.
      await reelClearDone;
      await wait(delayMs);
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
    const info = { symbol: code, row, col, cell, img, anchor, instance: null, winLoopTimeout: null };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks);
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: a single reel is revealed, then the next, so the suspense reads.
async function landReels(grid, anticipationColumns = []) {
  reelsBusy = true;
  try {
    await landReelsInner(grid, anticipationColumns);
  } finally {
    reelsBusy = false;
    // An orientation flip that arrived mid-spin was parked instead of ripping
    // the grid out from under the landing — apply it now.
    await flushDeviceRebuild();
  }
}

async function landReelsInner(grid, anticipationColumns) {
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
    // blackout — and scatter/wild idle loops mean there's practically always a
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
  setBackground(next);
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
  const boneName = POPUP_AMOUNT_BONE[key];
  if (!boneName) return; // popup with its own baked-in number (buy dialog)
  const canvasEl = document.getElementById('spineCanvas');
  const el = document.getElementById('popupAmount');
  el.textContent = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');

  const tick = () => {
    const bone = instance.skeleton.findBone(boneName);
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

// Shared instantiation so both the plain popup player and the buy dialog place
// and strip a popup identically.
function createPopupInstance(resource, key) {
  const instance = resource.createInstance();
  instance.anchorEl = document.getElementById('screen');
  instance.fit = popupFit(key);
  for (const slotName of POPUP_HIDDEN_SLOTS[key] || []) {
    const slot = instance.skeleton.findSlot(slotName);
    if (slot) slot.setAttachment(null);
  }
  return instance;
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

      const instance = createPopupInstance(resource, key);
      stage.addOverlay(instance);
      startPopupAmountTracking(instance, key, amount);

      instance.play(popupClip(resource, 'start'), false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play(popupClip(resource, 'idle'), true);
        setTimeout(() => {
          Sound.playSfx('popupClose');
          instance.play(popupClip(resource, 'end'), false);
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

// --- Buy Bonus confirmation dialog ------------------------------------------
//
// popup_buy_bonus_spins is the one delivered popup that's a DIALOG rather than
// an announcement: the card carries a ✓ and an ✗ (slots
// popup_buy_bonus_spins_yes / _no on bones bone3 / bone2). So the Buy Bonus
// sign opens this and the purchase only fires on ✓ — no click ever spends the
// player's balance on its own. app.js skips the server's own "buyFreeSpins"
// popup on the response, which would just repeat the card after the fact.
//
// The buttons are drawn on the Spine canvas, which takes no pointer events, so
// each gets an invisible DOM hit-area that follows its bone every frame — the
// same worldToScreen tracking the win-amount overlay uses. Box sizes are the
// attachments' own art-space dimensions (read from the skin), scaled by the
// instance's live skeleton scale, so they stay on the buttons at any viewport.
const BUY_DIALOG_BUTTONS = [
  { answer: true, bone: 'bone3', w: 248, h: 144, label: 'Купить фриспины' },
  { answer: false, bone: 'bone2', w: 246, h: 150, label: 'Отмена' },
];

let buyDialogOpen = false;

function trackBuyDialogHits(instance, buttons) {
  const canvasEl = document.getElementById('spineCanvas');
  const dpr = window.devicePixelRatio || 1;
  let raf = null;
  const tick = () => {
    // skeleton.scaleX is the world-units-per-art-unit factor the engine
    // applied when fitting the popup; /dpr converts it to CSS pixels.
    const scale = instance.skeleton.scaleX / dpr;
    for (const { el, spec } of buttons) {
      const bone = instance.skeleton.findBone(spec.bone);
      if (!bone) continue;
      const pos = worldToScreen(bone.worldX, bone.worldY, canvasEl);
      el.style.left = `${pos.left}px`;
      el.style.top = `${pos.top}px`;
      el.style.width = `${spec.w * scale}px`;
      el.style.height = `${spec.h * scale}px`;
    }
    raf = requestAnimationFrame(tick);
  };
  tick();
  return () => cancelAnimationFrame(raf);
}

// Resolves true if the player confirmed, false if they cancelled — the caller
// only spends money on true.
function showBuyBonusDialog(cost) {
  const key = 'buyFreeSpins';
  if (buyDialogOpen) return Promise.resolve(false);
  buyDialogOpen = true;

  return new Promise((resolve) => {
    (async () => {
      Sound.playSfx('popupOpen');
      pushScreenDim(false);
      await wait(DIM_TRANSITION_MS);

      if (!popupResourceCache[key]) popupResourceCache[key] = loadSpineResource(POPUP_FOLDERS[key]);
      const resource = await popupResourceCache[key];

      const instance = createPopupInstance(resource, key);
      stage.addOverlay(instance);
      startPopupAmountTracking(instance, key, cost);

      const layer = document.getElementById('buyDialogHits');
      layer.innerHTML = '';
      layer.hidden = false;
      const buttons = BUY_DIALOG_BUTTONS.map((spec) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'buy-dialog-hit';
        el.setAttribute('aria-label', spec.label);
        layer.appendChild(el);
        return { el, spec };
      });
      const stopTracking = trackBuyDialogHits(instance, buttons);

      let answered = false;
      const answer = (confirmed) => {
        if (answered) return;
        answered = true;
        Sound.playSfx('click');
        stopTracking();
        layer.hidden = true;
        layer.innerHTML = '';
        instance.play(popupClip(resource, 'end'), false);
        instance.onSettle = () => {
          instance.onSettle = null;
          stage.removeOverlay(instance);
          stopPopupAmountTracking();
          popScreenDim(false);
          buyDialogOpen = false;
          resolve(confirmed);
        };
      };
      for (const { el, spec } of buttons) {
        el.addEventListener('click', () => answer(spec.answer));
      }

      instance.play(popupClip(resource, 'start'), false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play(popupClip(resource, 'idle'), true);
      };
    })();
  });
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

  // Drops a wild on the middle row of each reel with a different multiplier, so
  // the transform can be watched without waiting for the RNG to cooperate.
  const wildBtn = document.getElementById('devWildMultipliers');
  if (wildBtn) {
    wildBtn.addEventListener('click', async () => {
      const demo = [2, 5, 7];
      setWildMultipliers(demo.map((multiplier, col) => ({ row: 1, col, multiplier })));
      await Promise.all(demo.map((_, col) => setCellSymbol(cellInfos[1 * GRID_COLS + col], 'wild')));
    });
  }
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

// --- Animated Spine background (desktop only) --------------------------------
//
// The manifest places a decor.spine "bg_hero_animation" covering the whole
// desktop canvas on both screens (bg_base_desk / bg_bonus_desk, clip "idle").
// Its portrait screens carry no such object, so there the static PNG below is
// the whole background. Rendered on its own canvas/GL context (bgSpineCanvas),
// same split ../golden-caravan uses.
const BG_SPINE_FOLDERS = { base: 'bg_base_desk', freespins: 'bg_bonus_desk' };
let bgStage = null;
let bgInstance = null;
const bgResourceCache = {};
let bgRenderToken = 0;

function bgFallbackSrc(mode) {
  if (isMobileLayout()) {
    return mode === 'base' ? `${ASSET_ROOT}/bg_base_mob.png` : `${ASSET_ROOT}/bg_bonus_mob.png`;
  }
  // The bonus desktop background kept the wizard upload's typo'd filename.
  return mode === 'base' ? `${ASSET_ROOT}/bg_base_desk.png` : `${ASSET_ROOT}/bg_bunus_desk.png`;
}

// Pick the fit axis that makes the skeleton COVER the screen (fill the short
// side, overflow the long one) — the art is authored at canvas size, so on a
// viewport of a different aspect ratio contain-fitting would letterbox it.
function applyBgCoverFit() {
  if (!bgInstance) return;
  const anchor = document.getElementById('bgAnchor').getBoundingClientRect();
  const b = bgInstance.resource.bounds;
  if (!anchor.width || !anchor.height || !b.width || !b.height) return;
  bgInstance.fitMode = b.width / b.height > anchor.width / anchor.height ? 'height' : 'width';
}

function clearBgSpine() {
  if (!bgInstance) return;
  bgStage.removeBase(bgInstance);
  bgInstance = null;
}

function setBackground(mode) {
  document.getElementById('bgLayer').src = bgFallbackSrc(mode);
  if (!bgStage) return;

  const myToken = ++bgRenderToken;
  if (isMobileLayout()) {
    clearBgSpine(); // portrait: static PNG only, per the manifest
    return;
  }

  const folder = BG_SPINE_FOLDERS[mode] || BG_SPINE_FOLDERS.base;
  if (!bgResourceCache[folder]) {
    bgResourceCache[folder] = loadSpineResource(`${ASSET_ROOT}/${folder}`, bgStage.assetManager);
  }
  bgResourceCache[folder].then((resource) => {
    if (myToken !== bgRenderToken) return; // a newer setBackground already ran
    clearBgSpine();
    const instance = resource.createInstance();
    instance.anchorEl = document.getElementById('bgAnchor');
    instance.fit = 1;
    bgInstance = instance;
    applyBgCoverFit();
    bgStage.addBase(instance);
    instance.play('idle', true);
  });
}

let lastMobile = null;
let pendingDeviceRebuild = false;

// Cell geometry differs per device (268x230 vs 200x200 cells) and every
// cell/strip carries pixel positions, so flipping orientation has to rebuild the
// grid onto the new pitch. It must NEVER do that mid-spin, though: the rebuild
// tears down every cell instance, so a clip the spin is awaiting can no longer
// complete — landReels would then hang and the spin button stay disabled for
// good. Defer to the end of the spin instead — see flushDeviceRebuild's call in
// landReels.
async function handleResize() {
  updateStageScale();
  applyBgCoverFit();
  const nowMobile = isMobileLayout();
  if (nowMobile === lastMobile) return;
  lastMobile = nowMobile;
  // The background art and whether there's an animated one at all both differ
  // per device.
  setBackground(currentMode());
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

// --- Boot preloader --------------------------------------------------------
// Mirror of the other games' warmup (см. например front/js/neon-reels/slot.js).
const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const img = new Image();
  img.src = src;
  return img.decode ? img.decode() : new Promise((res) => {
    img.onload = res;
    img.onerror = res;
  });
}

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
    tasks.push(track(preloadImage(`${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/static.png`)));
    tasks.push(track(getSymbolResource(code)));
  }
  for (const key of Object.keys(POPUP_FOLDERS)) {
    if (!popupResourceCache[key]) popupResourceCache[key] = loadSpineResource(POPUP_FOLDERS[key]);
    tasks.push(track(popupResourceCache[key]));
  }
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));
  tasks.push(track(warmUpWebGl(getSymbolResource(SYMBOL_CODES[0]))));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // must resolve before buildReelGrid's applyStaticContentOffset
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);

  buildReelGrid();
  stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  bgStage = new SpineEngine.SpineStage(document.getElementById('bgSpineCanvas'));
  setBackground(currentMode());
  setupDevPanel();

  await preloadAssets();
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));
  if (window.Preloader) window.Preloader.done();

  window.__slot = { stage, bgStage, cellInfos };
}

init();
