// Lucky Joker (3x3) — game-specific wiring on top of spine-engine.js.
// Starts from ../multi-fruits-story/slot.js (the project's other 3x3 game):
// everything lives in a fixed design canvas (desktop 1932x940, portrait
// 780x1416 — the sizes of the delivered backgrounds), contain-scaled as one
// unit, with scrolling reel columns clipped at the cabinet's window. See the
// header of css/lucky-joker-3h3.css for how the layout numbers were measured
// off the art, since this game has no builder manifest.
//
// Differences from that donor:
//   * no multiplier wild (this wild export has no variant skins) and no
//     animated Spine background (the backgrounds came as flat PNGs);
//   * the logo IS a Spine export (single `idle` clip), rendered over the
//     static PNG that stands in until it loads;
//   * Hold & Win, ported from ../east-discovery/slot.js: 5+ COIN opens a
//     respin round that the server has already fully resolved, replayed here
//     respin by respin. Coins carry either a plain multiplier (the blank
//     `coins/empty` art plus a live "xN" label) or one of the four jackpot
//     tiers, which ship their own lettering (`coins/mini` .. `coins/grand`)
//     and get the matching `jackpots/*_jackpot` award animation at the end.
//
// Asset notes (front/img/lucky-joker-3h3/):
//   * every symbol folder holds animation.{atlas,json,png} + static.png (the
//     resting tile) on a 220x220 canvas; coins and jackpot plates are the same
//     shape at 220x220 / 250x250;
//   * only `scatter` and `wild` ship idle/landing clips — every other symbol
//     (fruits, BAR, bell, 777, all coins) has exactly one clip, `win`;
//   * the popups are authored on the design canvas (their `dark-bg` is a 1x1
//     pixel scaled to 1932), so fit 1 lands them over the screen on desktop.

const ASSET_ROOT = 'img/lucky-joker-3h3';

// Checked against the delivered atlas PNGs: these exports declare no `pma`
// flag, i.e. straight (non-premultiplied) alpha, so go through this wrapper
// rather than SpineResource.load directly or every soft glow edge blends
// against the wrong colour.
function loadSpineResource(folderPath) {
  return SpineEngine.SpineResource.load(stage.assetManager, folderPath, {
    premultipliedAlpha: false,
  });
}

// code -> asset folder. The codes of real game symbols are a 1:1 contract with
// the backend seed (app/seed/lucky_joker_3h3.py) — do not rename them.
// Everything from `blank` down is client-only: those never come off the
// backend's reels, they're what the Hold & Win round draws with.
const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild',
  777: '777',
  bell: 'bell',
  bar: 'bar',
  watermelon: 'watermelon',
  plum: 'plum',
  lemon: 'lemon',
  cherry: 'cherry',
  // The money coin: blank art, its multiplier drawn over it as "xN" (the
  // server rolls the value — coin_multiplier.positions in the base game,
  // hold_and_win's landed coins in the round).
  coin: 'coins/empty',

  // Client-only codes:
  //   blank       — an empty cell, no art at all
  //   collector   — the joker coin; collects the coins' multipliers, and in
  //                 the round it is the ONLY thing the middle reel takes
  //   coin_<tier> — a jackpot coin, its tier's name baked into the art
  blank: null,
  collector: 'coins/joker',
  coin_mini: 'coins/mini',
  coin_minor: 'coins/minor',
  coin_major: 'coins/major',
  coin_grand: 'coins/grand',
};
// Only the codes the backend can actually deal — what the paytable, the
// preloader and the spin filler iterate over. `collector` is dealt too, but
// only ever on the middle reel (its reel_weights are [0, w, 0]).
const SYMBOL_CODES = [
  'scatter', 'wild', '777', 'bell', 'bar', 'watermelon', 'plum', 'lemon', 'cherry',
  'coin', 'collector',
];

// Codes eligible as random spin-loop filler — excludes the trigger symbols
// (blurring them past during a spin reads as a near-miss that never was).
const TRIGGER_CODES = new Set(['scatter', 'wild', 'coin', 'collector']);
const FILLER_CODES = SYMBOL_CODES.filter((c) => !TRIGGER_CODES.has(c));

// Every code with art has a Spine export; `blank` is the one that doesn't.
const SPINE_SYMBOLS = new Set(Object.keys(SYMBOL_FOLDERS).filter((c) => SYMBOL_FOLDERS[c]));
const STATIC_WIN_HOLD_MS = 900;

// Symbols that play landing -> idle when they arrive (both clips once, see
// setCellSymbol). Everything else is a static tile until it wins.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// Money symbols: they animate the moment they land rather than waiting to be
// part of a win — a coin arriving is an event in itself here.
const LANDING_ANIMATED = new Set([
  'coin', 'collector', 'coin_mini', 'coin_minor', 'coin_major', 'coin_grand',
]);

// Delivered clip inventory (read from each animation.json):
//   scatter / wild -> idle / landing / win
//   everything else -> win only
// A single-clip symbol therefore uses `win` for all three roles: it's the only
// thing the export can play, and for the coins it's exactly the right beat
// (the coin flips/glints as it lands).
const DEFAULT_CLIPS = { idle: 'idle', landing: 'landing', win: 'win' };
const SINGLE_CLIP = { idle: 'win', landing: 'win', win: 'win' };
const SYMBOL_CLIPS = {};
for (const code of Object.keys(SYMBOL_FOLDERS)) {
  if (SYMBOL_FOLDERS[code] && !SPECIAL_SYMBOLS.has(code)) SYMBOL_CLIPS[code] = SINGLE_CLIP;
}
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || DEFAULT_CLIPS[kind];
}

// --- Jackpots ---------------------------------------------------------------
//
// The four tiers and their multipliers are baked into the ladder plates
// (jackpot_*.png) and mirrored by JACKPOT_VALUES in
// app/seed/lucky_joker_3h3.py — the server reports which tier a coin is as
// `kind` on every Hold & Win coin, and that's what picks the art here.
const JACKPOT_TIERS = ['mini', 'minor', 'major', 'grand'];
const JACKPOT_FOLDERS = {
  mini: `${ASSET_ROOT}/jackpots/mini_jackpot`,
  minor: `${ASSET_ROOT}/jackpots/minor_jackpot`,
  major: `${ASSET_ROOT}/jackpots/major_jackpot`,
  grand: `${ASSET_ROOT}/jackpots/grand_jackpot`,
};

// Coin `kind` (as reported by app/features/coin_multiplier.py and
// hold_and_win.py) -> grid code. A jackpot tier gets its own art with the
// amount baked in; anything else is the blank coin plus an "xN" label.
function coinCodeForKind(kind) {
  if (kind === 'collector') return 'collector';
  return JACKPOT_TIERS.includes(kind) ? `coin_${kind}` : 'coin';
}

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/popups/big_win`,
  megaWin: `${ASSET_ROOT}/popups/mega_win`,
  epicWin: `${ASSET_ROOT}/popups/epic_win`,
  bonusSpinsWin: `${ASSET_ROOT}/popups/win_free_spins`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/popups/free-spins-total-win`,
  buyFreeSpins: `${ASSET_ROOT}/popups/buy_free_spins`,
};
// Bone the headline number rides on. Every popup here draws an empty "input"
// plate — the hole the live amount goes in — and parents the number bone to
// it: `usd`/`numb` on the announcements, `numb_usd` on the buy dialog (whose
// `input-counter`/`number` pair carries the bet instead, see the dialog
// section).
const POPUP_AMOUNT_BONE = {
  bigWin: 'usd',
  megaWin: 'usd',
  epicWin: 'usd',
  bonusSpinsWin: 'numb',
  bonusSpinsTotalWin: 'usd',
  buyFreeSpins: 'numb_usd',
};
// The popups are authored on the full design canvas, so fit 1 lands them
// exactly over the screen on desktop. Portrait doubles them: the export's box
// is landscape, so contain-fitting it into a narrow screen is driven by the
// width and leaves the card small in a tall viewport — same call as
// ../multi-fruits-story.
const POPUP_FIT_DEFAULT = { desktop: 1, mobile: 2 };
function popupFit() {
  const fit = POPUP_FIT_DEFAULT;
  return isMobileLayout() ? fit.mobile : fit.desktop;
}

// These exports ship one cut of start/idle/end (no separate portrait cut), but
// resolve against the skeleton's own animation list anyway so a re-export that
// adds `mob_*` keeps working.
function popupClip(resource, kind) {
  const names = new Set(resource.skeletonData.animations.map((a) => a.name));
  const candidates = isMobileLayout() ? [`mob_${kind}`, `mob-${kind}`, kind] : [kind];
  return candidates.find((name) => names.has(name)) || kind;
}

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 100;
const WIN_LOOP_PAUSE_MS = 500;

// Matches the backend grid shape (3 reels x 3 rows, row-major grid[row][col]).
const GRID_COLS = 3;
const GRID_ROWS = 3;

// Attract-mode layout shown before the first spin lands.
const SYMBOL_LAYOUT = [
  ['cherry', 'scatter', 'lemon'],
  ['bar', 'wild', 'plum'],
  ['lemon', 'bell', '777'],
];

// Grid geometry comes from CSS (--cell-w/--cell-h/--cell-gap-x/-y) so the
// desktop (193x163) and portrait (150x127) blocks stay the single source of
// truth.
let cellW = 193, cellH = 163, gapX = 0, gapY = 0;
let colStep = cellW + gapX, rowStep = cellH + gapY;
// Cached alongside the cell dims: --symbol-scale would otherwise be re-read
// from getComputedStyle once per cell, i.e. a forced style recalc per cell in
// the middle of the busiest frame of a spin.
let cachedSymbolScale = 1;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => {
    const value = parseFloat(cs.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  cellW = num('--cell-w', 193);
  cellH = num('--cell-h', 163);
  gapX = num('--cell-gap-x', 0);
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
// window in which nothing may tear the grid down from under the animation.
let reelsBusy = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// A Spine clip's completion drives the round's own sequencing, so one clip
// that never settles would hang it and leave the SPIN button disabled for
// good — see the jackpot award, whose onSettle is backed by this timeout.
const CLIP_TIMEOUT_MS = 4000;

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
// instance: it's the union of every slot including glow/VFX layers. What IS
// reliable is that these exports are authored in art pixels around the
// skeleton origin, and each symbol's static tile is that same art on a centred
// canvas. So use the tile's own natural size as the box, centred on the
// origin: world unit == 1 design px, and the Spine instance lands exactly
// where the static <img> it replaces was.
const staticSizeCache = {};
function getStaticSize(code) {
  if (!staticSizeCache[code]) {
    staticSizeCache[code] = new Promise((resolve) => {
      const probe = new Image();
      probe.addEventListener('load', () => resolve({ w: probe.naturalWidth, h: probe.naturalHeight }));
      probe.addEventListener('error', () => resolve({ w: 220, h: 220 }));
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
// button (js/slot-calibration.js) — nothing is offset by default.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('lucky-joker-3h3', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `scale(var(--symbol-scale, 1)) translate(${dx}px, ${dy}px)`;
}

// --- Grid -------------------------------------------------------------------

// `blank` is the ONLY code that is legitimately drawn as nothing (an unfilled
// Hold & Win cell). Anything else without art is a bug — a code the backend
// deals that this file has no folder for — and must be loud rather than a
// silent hole in the grid: that's exactly how the builder's placeholder
// symbols (low_a..high_b) used to show up before the seed replaced them.
function symbolFolder(code) {
  const folder = SYMBOL_FOLDERS[code];
  if (folder) return folder;
  if (code !== 'blank') console.warn(`[lucky-joker] no art for symbol code "${code}" — rendering a placeholder`);
  return null;
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  // A landing rebuilds 17 cells per column (3 result + 14 filler) x 3 columns
  // in one burst, right when the reels are scrolling. Async decoding keeps
  // that off the main thread so the scroll doesn't hitch.
  img.decoding = 'async';
  const folder = symbolFolder(code);
  if (folder) {
    img.src = `${ASSET_ROOT}/${folder}/static.png`;
    img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
  } else if (code === 'blank') {
    // An empty Hold & Win cell — an <img> with no src would draw a broken-
    // image glyph, so keep the node and hide it.
    img.style.visibility = 'hidden';
  } else {
    img.classList.add('is-missing');
  }
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
  clearCoinAmountLabels();
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
    // the canvas (playWinAnimationOnce / the scatter+wild idle loops). Pulling
    // the instance off the canvas without putting the tile back leaves the
    // cell EMPTY — and since this runs at the start of every spin, that empty
    // cell is what visibly drops out of view when the reels clear. `blank`
    // (an unfilled Hold & Win cell) is the one code that stays hidden.
    if (info.img) info.img.style.visibility = info.symbol === 'blank' ? 'hidden' : '';
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
  info.img.classList.remove('is-missing');
  const folder = symbolFolder(code);
  if (folder) {
    info.img.src = `${ASSET_ROOT}/${folder}/static.png`;
    info.img.style.visibility = '';
  } else {
    info.img.removeAttribute('src');
    // Only `blank` disappears; an unknown code keeps a visible placeholder.
    info.img.style.visibility = code === 'blank' ? 'hidden' : '';
    if (code !== 'blank') info.img.classList.add('is-missing');
  }
  applyStaticContentOffset(info.img, code);

  const resourcePromise = getSymbolResource(code);
  if (!resourcePromise) return; // `blank` — nothing to draw

  try {
    const [resource, staticBox] = await Promise.all([resourcePromise, cellSpineBox(code)]);
    const instance = resource.createInstance();
    if (info.anchor) {
      // Anchor sized to the fit box + fit == --symbol-scale means the
      // world->px mapping is exactly the scale the static <img> renders at.
      info.anchor.style.width = `${staticBox.width}px`;
      info.anchor.style.height = `${staticBox.height}px`;
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'lucky-joker-3h3', code);
    }
    instance.anchorEl = info.anchor || info.cell;
    instance.fit = symbolScale();
    instance.boundsOverride = staticBox;
    info.instance = instance;

    if (SPECIAL_SYMBOLS.has(code)) {
      // scatter/wild: landing, then the idle ONCE (product — it used to loop
      // forever, which made the two of them the loudest thing on a resting
      // grid). The instance stays on the canvas afterwards, holding the idle's
      // last frame, so the symbol simply comes to rest.
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      addCellBase(instance);
      instance.play(clipName(code, 'landing'), false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play(clipName(code, 'idle'), false);
      };
    } else if (LANDING_ANIMATED.has(code)) {
      // Coins and the collector animate as they LAND (product: "если у монет
      // есть айдл анимация она тоже может срабатывать при падении"). These
      // exports ship a single clip, so `landing` resolves to it; it plays once
      // and stops on its last frame.
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      addCellBase(instance);
      instance.play(clipName(code, 'landing'), false);
    }
  } catch (err) {
    console.warn(`Spine load failed for symbol "${code}":`, err);
  }
}

// --- Win presentation -------------------------------------------------------

function playWinAnimationOnce(info) {
  const { instance, img } = info;
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
// .reel__grid clips the whole block at the cabinet's window, so a strip in
// motion disappears behind the border rather than past the frame.
//
// No spinning-loop phase (same clear-drop + land-from-top as every other reel
// game): on spin press the resting symbols drop out of view downward, the reel
// stands empty while the server answers, and the finals fall in from the top.
// landReel awaits reelClearDone so no column starts landing mid-drop; the
// per-column stagger counts from the END of the clear.
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
    // Two rAFs: one full frame so transition:none + the transform reset apply
    // before the drop transition starts.
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
// trigger needs): a plain LINEAR pre-roll, then the same short eased landing
// every normal column uses.
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

// `coinValues` (one entry per row, null where there's no coin) attaches the
// "xN" label to the result cells AS THE STRIP IS BUILT, i.e. before the drop
// even starts — the coin falls with its multiplier already on it instead of
// having the number pop in after it lands (product). The label tracks the
// cell node itself, so it rides down with the reel.
function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, fillerFn = randomSymbolCode, coinValues = null) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    (async () => {
      // The cascade counts from the end of the clear, not from the click —
      // otherwise columns whose delay is shorter than the clear all wake up
      // together.
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
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, fillerFn),
        ...Array.from({ length: prerollCount }, fillerFn),
      ];
      const cellEls = sequence.map((code, index) => {
        const { cell } = createCellNode(code);
        stripEl.appendChild(cell);
        // Only the result rows (the first GRID_ROWS) carry a value.
        const value = coinValues && index < GRID_ROWS ? coinValues[index] : null;
        if (value != null) showCoinAmountLabel({ cell }, value);
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

// Resolves the backend grid into what actually gets DRAWN, using the coin
// values the server rolled: a coin that drew a jackpot tier lands as that
// tier's own art, everything else lands as itself. Returns the drawable codes
// plus the "xN" each cell needs, so both are ready before the drop starts.
function resolveDrawnGrid(grid, coinMultiplier) {
  const codes = grid.map((row) => row.slice());
  const values = grid.map((row) => row.map(() => null));
  for (const pos of (coinMultiplier && coinMultiplier.positions) || []) {
    if (codes[pos.row]?.[pos.col] !== 'coin') continue;
    if (JACKPOT_TIERS.includes(pos.kind)) {
      codes[pos.row][pos.col] = coinCodeForKind(pos.kind); // amount baked into the art
    } else {
      values[pos.row][pos.col] = pos.value;
    }
  }
  return { codes, values };
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: a single reel is revealed, then the next, so the suspense reads.
async function landReels(grid, anticipationColumns = [], coinMultiplier = null) {
  reelsBusy = true;
  try {
    await landReelsInner(grid, anticipationColumns, coinMultiplier);
  } finally {
    reelsBusy = false;
    // An orientation flip that arrived mid-spin was parked instead of ripping
    // the grid out from under the landing — apply it now.
    await flushDeviceRebuild();
  }
}

async function landReelsInner(grid, anticipationColumns, coinMultiplier) {
  teardownCellInstances();

  const { codes, values } = resolveDrawnGrid(grid, coinMultiplier);
  const columnCodes = (col) => [codes[0][col], codes[1][col], codes[2][col]];
  const columnValues = (col) => [values[0][col], values[1][col], values[2][col]];

  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = columnCodes(col);
    const delay = col * REEL_LAND_STAGGER_MS;
    leadTasks.push(
      landReel(col, finalCodes, delay, false, randomSymbolCode, columnValues(col))
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes)),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');

  // Freeze every remaining reel right away — landing one at a time isn't
  // enough on its own if the ones still waiting their turn keep spinning in
  // the background.
  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const { stripEl } = reelCols[col];
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }

  for (let col = firstAnticipationCol; col < GRID_COLS; col++) {
    const finalCodes = columnCodes(col);
    const isAnticipating = anticipationSet.has(col);
    if (isAnticipating) reelCols[col].colEl.classList.add('is-anticipating');
    const cellEls = await landReel(col, finalCodes, 0, isAnticipating, randomSymbolCode, columnValues(col));
    await settleColumnCells(cellEls, col, finalCodes);
  }
}

// --- Bone-tracked DOM overlays ----------------------------------------------
//
// Text drawn over Spine art (win amounts, coin values, the buy dialog's
// numbers) lives in the DOM, not on the canvas — so each label has to follow
// its bone every frame. One shared tracker for all of them.

function worldToScreen(worldX, worldY, canvasEl) {
  const dpr = window.devicePixelRatio || 1;
  const canvasRect = canvasEl.getBoundingClientRect();
  const cx = worldX + canvasEl.width / 2;
  const cy = canvasEl.height / 2 - worldY;
  return { left: canvasRect.left + cx / dpr, top: canvasRect.top + cy / dpr };
}

// items: [{ instance, bone, el, size? }] — `size` ({w,h}) also stretches the
// element to the attachment's art-space box (the buy dialog's hit areas).
// Returns a stop() that cancels the rAF loop.
function trackBoneElements(items) {
  const canvasEl = document.getElementById('spineCanvas');
  let raf = null;
  const tick = () => {
    const dpr = window.devicePixelRatio || 1;
    for (const item of items) {
      const bone = item.instance.skeleton.findBone(item.bone);
      if (!bone) continue;
      const pos = worldToScreen(bone.worldX, bone.worldY, canvasEl);
      item.el.style.left = `${pos.left}px`;
      item.el.style.top = `${pos.top}px`;
      if (item.size) {
        // skeleton.scaleX is the world-units-per-art-unit factor the engine
        // applied when fitting; /dpr converts it to CSS pixels.
        const scale = item.instance.skeleton.scaleX / dpr;
        item.el.style.width = `${item.size.w * scale}px`;
        item.el.style.height = `${item.size.h * scale}px`;
      }
    }
    raf = requestAnimationFrame(tick);
  };
  tick();
  return () => cancelAnimationFrame(raf);
}

// --- Hold & Win coin labels --------------------------------------------------
//
// A numeric coin is the blank `coins/empty` art with its value written over
// it. Jackpot coins ship their own lettering and get no label. Several coins
// are on screen at once, so this is a pool rather than the popup's single
// shared element.
//
// These track their CELL, not a bone: a coin sitting on the grid is the static
// tile, its Spine instance isn't on the canvas, and a skeleton that never
// updates leaves every bone at world 0,0 — which parked all five labels in the
// middle of the screen. The cell's own rect is also what actually defines
// where the art is drawn, so it stays right through stage rescales.
// How far above the cell's centre the number sits, as a share of cell height
// (see trackCoinAmounts).
const COIN_AMOUNT_LIFT = 0.015;

let coinAmountRaf = null;
let coinAmountItems = [];

function trackCoinAmounts() {
  if (coinAmountRaf) return;
  const layer = document.getElementById('coinAmountsReels');
  const viewport = document.querySelector('.reel-win-amount-viewport');
  const tick = () => {
    // Метки живут в fixed-слое поверх всего, поэтому окно барабанов их не
    // режет само — режем вручную по тому же прямоугольнику, что и символы
    // (.reel-win-amount-viewport = проём корпуса). Без этого номинал видно
    // у верха экрана, пока монета ещё едет над окном.
    const v = viewport.getBoundingClientRect();
    layer.style.clipPath = `inset(${v.top}px ${window.innerWidth - v.right}px ` +
      `${window.innerHeight - v.bottom}px ${v.left}px)`;
    for (const { info, el, scale } of coinAmountItems) {
      const r = info.cell.getBoundingClientRect();
      el.style.left = `${r.left + r.width / 2}px`;
      // Lifted off the cell's centre: the number reads low against the coin,
      // whose own face sits slightly above centre in the art. Expressed as a
      // share of the cell so it holds at any stage scale — 1.5% is the 2px
      // product asked for at the desktop fit.
      el.style.top = `${r.top + r.height / 2 - r.height * COIN_AMOUNT_LIFT}px`;
      // Sized off the cell so the number keeps its proportion to the coin at
      // every viewport/stage scale.
      el.style.fontSize = `${Math.round(r.height * scale)}px`;
    }
    coinAmountRaf = requestAnimationFrame(tick);
  };
  tick();
}

function showCoinAmountLabel(info, value, extraClass = '') {
  const el = document.createElement('div');
  el.className = extraClass ? `coin-amount ${extraClass}` : 'coin-amount';
  el.textContent = `x${value}`;
  // В обрезаемый слой: это номинал НА БАРАБАНЕ, он должен появляться из-под
  // рамки вместе со своей монетой.
  document.getElementById('coinAmountsReels').appendChild(el);
  // The collector's running total is the round's headline number — it reads a
  // size up from the coins feeding it.
  coinAmountItems.push({ info, el, scale: extraClass === 'is-collector' ? 0.38 : 0.28 });
  trackCoinAmounts();
}

function clearCoinAmountLabels() {
  if (coinAmountRaf) cancelAnimationFrame(coinAmountRaf);
  coinAmountRaf = null;
  for (const { el } of coinAmountItems) el.remove();
  coinAmountItems = [];
}

// --- Base-game coins ---------------------------------------------------------
//
// Every COIN that lands carries a multiplier the server rolled for it
// (coin_multiplier.positions). A plain value is drawn as "xN" over the blank
// coin; a jackpot tier swaps the cell to that tier's own art, which already
// has its amount on it. The multiplier only pays when the spin also has a
// winning line — the amount is shown either way, which is what makes a coin
// landing feel like something before the reels are even judged.
//
// A NORMAL spin doesn't come through here: it resolves art and values up front
// and builds them into the falling strip (resolveDrawnGrid + landReel). This
// is for grids that appear without a landing — the base reels restored when a
// Hold & Win round ends.
async function applyCoinValues(coinMultiplier) {
  if (!coinMultiplier || !coinMultiplier.positions) return;
  const swaps = [];
  for (const pos of coinMultiplier.positions) {
    const info = cellInfos[pos.row * GRID_COLS + pos.col];
    if (!info || info.symbol !== 'coin') continue;
    if (JACKPOT_TIERS.includes(pos.kind)) {
      swaps.push(setCellSymbol(info, coinCodeForKind(pos.kind)));
    } else {
      showCoinAmountLabel(info, pos.value);
    }
  }
  await Promise.all(swaps);
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
    // Opaque dim = the base<->bonus transition. Any still-looping win symbol
    // is drawn on the same canvas as the popup, so #screenDim (a DOM element)
    // can't darken it without also covering the popup — pull the cells off the
    // canvas outright for the blackout and put them back after.
    stage.setBaseDim(true);
    detachedBaseInstances = cellInfos
      .filter((info) => info && info.instance && stage.baseInstances.includes(info.instance))
      .map((info) => info.instance);
    for (const instance of detachedBaseInstances) stage.removeBase(instance);
  }
}

// Cell instances pulled off the canvas by an opaque dim, restored on pop.
let detachedBaseInstances = [];

// Every cell instance goes on the canvas through here so one that appears
// while the blackout is up is held back with the rest instead of popping into
// the void.
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
      // Only put back what's still on the grid — a cell the transition
      // replaced meanwhile has had its instance torn down already.
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

// How long the "you won the bonus" popup holds on the blackout before the
// bonus screen is revealed behind it.
const BONUS_INTRO_HOLD_MS = 3000;

async function enterBonusTransition(amount = 0) {
  pushScreenDim(true); // opaque blackout in
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true); // reveal the bonus screen
}

// `intro` is true for the free-spins (scatter) trigger — it gets the full
// intro moment (blackout + bonusSpinsWin popup + reveal). Hold & Win reuses
// freespins mode as its bonus level but passes intro:false: it shows no entry
// popup, its own total-win popup covers the end.
function setFreeSpinsMode(active, amount = 0, { intro = true } = {}) {
  const next = active ? 'freespins' : 'base';
  if (currentMode() === next) return Promise.resolve();

  Sound.playMusic(next === 'freespins' ? 'bonus' : 'base');

  if (next === 'freespins' && intro) return enterBonusTransition(amount);

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
let popupAmountStop = null;

function startPopupAmountTracking(instance, key, amount) {
  const boneName = POPUP_AMOUNT_BONE[key];
  if (!boneName) return;
  const el = document.getElementById('popupAmount');
  el.textContent = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');
  popupAmountStop = trackBoneElements([{ instance, bone: boneName, el }]);
}

function stopPopupAmountTracking() {
  if (popupAmountStop) popupAmountStop();
  popupAmountStop = null;
  document.getElementById('popupAmount').classList.remove('is-visible');
}

function createPopupInstance(resource) {
  const instance = resource.createInstance();
  instance.anchorEl = document.getElementById('screen');
  instance.fit = popupFit();
  return instance;
}

// Core popup lifecycle (start -> idle hold -> end). Resolves only once the
// popup has FULLY played out, so a caller can sequence work after it. `ownDim`
// lets a caller that already owns the screen dim (the bonus intro) borrow the
// popup without it pushing/popping its own.
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

      const instance = createPopupInstance(resource);
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

// --- Jackpot award -----------------------------------------------------------
//
// The `jackpots/*_jackpot` exports are the celebration for a jackpot coin: one
// `win` clip showing that tier's plate. Played over the screen once the round's
// coins are all down, before the total-win popup, with the matching ladder
// plate lit up.
const jackpotResourceCache = {};
const JACKPOT_FIT = { desktop: 0.55, mobile: 0.9 };

function playJackpotAward(tier) {
  const folder = JACKPOT_FOLDERS[tier];
  if (!folder) return Promise.resolve();

  return new Promise((resolve) => {
    (async () => {
      if (!jackpotResourceCache[tier]) jackpotResourceCache[tier] = loadSpineResource(folder);
      const resource = await jackpotResourceCache[tier];

      const plate = document.querySelector(`.jp--${tier}`);
      if (plate) plate.classList.add('is-won');
      Sound.playSfx('jackpotWin');

      const instance = resource.createInstance();
      instance.anchorEl = document.getElementById('screen');
      instance.fit = isMobileLayout() ? JACKPOT_FIT.mobile : JACKPOT_FIT.desktop;
      stage.addOverlay(instance);

      const finish = () => {
        stage.removeOverlay(instance);
        if (plate) plate.classList.remove('is-won');
        resolve();
      };
      instance.play('win', false);
      instance.onSettle = () => {
        instance.onSettle = null;
        finish();
      };
      // The award is on the round's critical path — never let a clip that
      // doesn't settle strand the player in the bonus.
      setTimeout(finish, CLIP_TIMEOUT_MS);
    })();
  });
}

// --- Buy Bonus confirmation dialog ------------------------------------------
//
// popup_buy_free_spins is a DIALOG, not an announcement: the card carries ✓/✗
// (bones btn-accept / btn-cancel) AND a bet stepper (−/+ on bones minus/plus
// around an input-counter). So the Buy Bonus sign opens this and the purchase
// only fires on ✓ — no click ever spends the player's balance on its own.
//
// The buttons are drawn on the Spine canvas, which takes no pointer events, so
// each gets an invisible DOM hit-area that follows its bone every frame. Box
// sizes are the attachments' own art-space dimensions (read out of the export).
const BUY_DIALOG_BUTTONS = [
  { action: 'accept', bone: 'btn-accept', w: 214, h: 105, label: 'Купить фриспины' },
  { action: 'cancel', bone: 'btn-cancel', w: 214, h: 105, label: 'Отмена' },
  { action: 'bet-plus', bone: 'plus', w: 104, h: 77, label: 'Увеличить ставку' },
  { action: 'bet-minus', bone: 'minus', w: 104, h: 77, label: 'Уменьшить ставку' },
];

let buyDialogOpen = false;

// Resolves { confirmed, betIndex } — the caller only spends money on
// `confirmed`, and takes back whatever bet the player stepped to in the
// dialog. `betSteps`/`betIndex` come straight from app.js's gameState.
function showBuyBonusDialog({ betSteps, betIndex, costMultiplier }) {
  const key = 'buyFreeSpins';
  if (buyDialogOpen) return Promise.resolve({ confirmed: false, betIndex });
  buyDialogOpen = true;

  return new Promise((resolve) => {
    (async () => {
      Sound.playSfx('popupOpen');
      pushScreenDim(false);
      await wait(DIM_TRANSITION_MS);

      if (!popupResourceCache[key]) popupResourceCache[key] = loadSpineResource(POPUP_FOLDERS[key]);
      const resource = await popupResourceCache[key];

      const instance = createPopupInstance(resource);
      stage.addOverlay(instance);

      let index = betIndex;
      // Two live numbers: the total price on the popup's own amount overlay
      // (bone numb_usd) and the current bet inside the stepper's counter
      // (bone number).
      const betEl = document.createElement('div');
      betEl.className = 'coin-amount';
      document.getElementById('coinAmounts').appendChild(betEl);

      const renderNumbers = () => {
        const bet = betSteps[index];
        document.getElementById('popupAmount').textContent =
          Number(bet * costMultiplier).toLocaleString('en-US');
        betEl.textContent = Number(bet).toLocaleString('en-US');
      };
      startPopupAmountTracking(instance, key, betSteps[index] * costMultiplier);
      renderNumbers();

      const layer = document.getElementById('buyDialogHits');
      layer.innerHTML = '';
      layer.hidden = false;
      const buttons = BUY_DIALOG_BUTTONS.map((spec) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'buy-dialog-hit';
        el.setAttribute('aria-label', spec.label);
        layer.appendChild(el);
        return { instance, bone: spec.bone, el, size: { w: spec.w, h: spec.h }, spec };
      });
      const stopTracking = trackBoneElements([
        ...buttons,
        { instance, bone: 'number', el: betEl },
      ]);

      let answered = false;
      const answer = (confirmed) => {
        if (answered) return;
        answered = true;
        Sound.playSfx('click');
        stopTracking();
        betEl.remove();
        layer.hidden = true;
        layer.innerHTML = '';
        instance.play(popupClip(resource, 'end'), false);
        instance.onSettle = () => {
          instance.onSettle = null;
          stage.removeOverlay(instance);
          stopPopupAmountTracking();
          popScreenDim(false);
          buyDialogOpen = false;
          resolve({ confirmed, betIndex: index });
        };
      };
      for (const { el, spec } of buttons) {
        el.addEventListener('click', () => {
          if (spec.action === 'accept') return answer(true);
          if (spec.action === 'cancel') return answer(false);
          Sound.playSfx('click');
          index = spec.action === 'bet-plus'
            ? Math.min(betSteps.length - 1, index + 1)
            : Math.max(0, index - 1);
          renderNumbers();
        });
      }

      instance.play(popupClip(resource, 'start'), false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play(popupClip(resource, 'idle'), true);
      };
    })();
  });
}

// --- Hold & Win playback ----------------------------------------------------
//
// The whole round resolves in one backend call (app/features/hold_and_win.py)
// — the respins/pacing here are purely client-side theater replaying that
// already-known outcome respin by respin, so the player experiences it as
// "real time".
//
// Unlike ../east-discovery, which re-lands whole columns every respin (so a
// locked coin visibly re-drops into its own cell), this round is a TRUE hold:
// a symbol that has landed never moves again, and only the cells that are
// still empty spin. That means spinning per CELL rather than per column — a
// column here can hold a locked coin and an empty cell at the same time — so
// each empty cell gets its own little strip clipped to the cell
// (see spinCellTo / .cell-spinner).

// The round's own reel roles, straight out of the server config (app/seed/
// lucky_joker_3h3.py's hold_and_win params): the middle reel takes ONLY
// collectors, the outer two take ONLY coins. That's what makes this a 3x3
// round rather than the generic one — 6 coin slots and 3 collector slots, and
// every collector is worth the sum of all the coins.
const COLLECTOR_REEL = 1;

const HOLD_AND_WIN_RESPIN_PAUSE_MS = 1000;
const HOLD_AND_WIN_COIN_FILLER_CHANCE = 0.16; // flavor only — matches respin_land_weights
const HOLD_AND_WIN_COLLECTOR_FILLER_CHANCE = 0.07; // ...and collector_land_weights

// Filler blurring past during a respin: only what that reel could actually
// land, or the spin lies about what's coming.
function holdAndWinFillerFor(col) {
  return col === COLLECTOR_REEL
    ? () => (Math.random() < HOLD_AND_WIN_COLLECTOR_FILLER_CHANCE ? 'collector' : 'blank')
    : () => (Math.random() < HOLD_AND_WIN_COIN_FILLER_CHANCE ? 'coin' : 'blank');
}

const coinKey = (row, col) => `${row}-${col}`;

// The coins locked in the round currently on screen, "row-col" ->
// {value, kind}. Module-level only so an orientation flip mid-round can
// repaint their labels after the grid is rebuilt (flushDeviceRebuild) —
// the rebuild tears every cell down, labels included.
let holdAndWinLocked = null;

// locked: Map "row-col" -> { value, kind }
function buildHoldAndWinGrid(locked) {
  const grid = [[], [], []];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const coin = locked.get(coinKey(row, col));
      grid[row][col] = coin ? coinCodeForKind(coin.kind) : 'blank';
    }
  }
  return grid;
}

// What every collector on the grid is currently worth: the sum of all the
// coins' multipliers (jackpot coins included, at their tier's value). Mirrors
// the payout the server computed — coin_total x collector_count.
function collectedTotal(locked) {
  let total = 0;
  for (const [, coin] of locked) {
    if (coin.kind !== 'collector') total += coin.value;
  }
  return total;
}

// Repaints every label the round shows: "xN" on each plain coin (jackpot coins
// carry their amount in the art), and the running collected total on EVERY
// collector — they all collect, which is exactly why a second one doubles the
// round. Called after each landing, since that rebuilds the cells from scratch.
function paintLockedCoins(locked) {
  clearCoinAmountLabels();
  const total = collectedTotal(locked);
  for (const [key, coin] of locked) {
    const [row, col] = key.split('-').map(Number);
    const info = cellInfos[row * GRID_COLS + col];
    if (!info) continue;
    if (coin.kind === 'collector') {
      if (total > 0) showCoinAmountLabel(info, total, 'is-collector');
    } else if (!JACKPOT_TIERS.includes(coin.kind)) {
      showCoinAmountLabel(info, coin.value);
    }
  }
}

const HW_CELL_SPIN_MS = 620;
const HW_CELL_SPIN_FILLER = 8;

// Scrolls ONE cell to `code`: a strip of filler above the result, clipped to
// the cell, slid down into place and then thrown away in favour of the real
// cell art. Locked cells never get one, which is what makes the hold read.
function spinCellTo(info, code, fillerFn, delayMs) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const spinner = document.createElement('div');
      spinner.className = 'cell-spinner';
      const strip = document.createElement('div');
      strip.className = 'cell-spinner__strip';

      for (const itemCode of [code, ...Array.from({ length: HW_CELL_SPIN_FILLER }, fillerFn)]) {
        const item = document.createElement('div');
        item.className = 'cell-spinner__item';
        const folder = symbolFolder(itemCode);
        if (folder) {
          const img = document.createElement('img');
          img.decoding = 'async';
          img.src = `${ASSET_ROOT}/${folder}/static.png`;
          item.appendChild(img);
        }
        strip.appendChild(item);
      }
      spinner.appendChild(strip);
      info.cell.appendChild(spinner);
      info.img.style.visibility = 'hidden';

      // Start on the last filler, slide down to the result at index 0.
      strip.style.transform = `translateY(${-HW_CELL_SPIN_FILLER * rowStep}px)`;
      void strip.offsetHeight;
      strip.style.transition = `transform ${HW_CELL_SPIN_MS}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
      strip.style.transform = 'translateY(0px)';

      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        spinner.remove();
        setCellSymbol(info, code).then(resolve);
      };
      strip.addEventListener('transitionend', (event) => {
        if (event.propertyName === 'transform') finish();
      });
      // A transition that never fires (tab hidden, style recalc raced) must
      // not strand the round — same guard the column landing uses.
      setTimeout(finish, HW_CELL_SPIN_MS + 250);
    }, delayMs);
  });
}

// One respin: every cell that isn't locked spins, landing either what the
// server says arrives there this respin or nothing (blank). Locked cells are
// not touched at all — no re-drop, no re-render, labels stay put.
async function respinEmptyCells(locked, landing) {
  const tasks = [];
  for (let col = 0; col < GRID_COLS; col++) {
    const filler = holdAndWinFillerFor(col);
    for (let row = 0; row < GRID_ROWS; row++) {
      const key = coinKey(row, col);
      if (locked.has(key)) continue;
      const info = cellInfos[row * GRID_COLS + col];
      if (!info) continue;
      const arriving = landing.get(key);
      const code = arriving ? coinCodeForKind(arriving.kind) : 'blank';
      tasks.push(spinCellTo(info, code, filler, col * REEL_LAND_STAGGER_MS));
    }
  }
  await Promise.all(tasks);
}

// The round opens on the triggering grid's own coins (result.initial) already
// locked — everything else blanked out — and then waits for the player's Spin
// click.
async function enterHoldAndWinWaitingState(result) {
  const locked = new Map();
  for (const c of result.initial || []) locked.set(coinKey(c.row, c.col), { value: c.value, kind: c.kind });

  // Marks the bonus screen as a Hold & Win round rather than free spins: the
  // two share the same background/mode, but the free-spins counter has nothing
  // to count here (CSS hides it on this attribute).
  document.getElementById('screen').dataset.round = 'holdwin';
  await setFreeSpinsMode(true, 0, { intro: false }); // Hold & Win shows no entry popup
  await applyGrid(buildHoldAndWinGrid(locked));
  holdAndWinLocked = locked;
  paintLockedCoins(locked);
  return locked;
}

// `baseGrid`/`baseCoins` are the grid the triggering spin landed on and the
// coin values it drew. The round leaves the reels holding its own coin/blank
// layout, so without putting those back the player returns to the base game
// staring at holes where the round never filled a cell — and at coins with no
// number on them.
async function runHoldAndWinSequence(result, locked, baseGrid = null, baseCoins = null) {
  const wonTiers = [];
  const noteTier = (kind) => {
    if (JACKPOT_TIERS.includes(kind) && !wonTiers.includes(kind)) wonTiers.push(kind);
  };
  for (const [, coin] of locked) noteTier(coin.kind);

  for (const respin of result.respins) {
    // Spin the empty cells only — what arrives lands out of that spin, and
    // `locked` isn't updated until it has (a cell can't be held before it
    // holds anything).
    const landing = new Map(
      respin.landed.map((c) => [coinKey(c.row, c.col), { value: c.value, kind: c.kind }]),
    );
    await respinEmptyCells(locked, landing);
    for (const [key, coin] of landing) locked.set(key, coin);
    holdAndWinLocked = locked;
    paintLockedCoins(locked);

    // No explicit celebration here any more: a coin/collector animates itself
    // the moment it lands (LANDING_ANIMATED in setCellSymbol), so replaying
    // the clip would only restart it mid-way.
    for (const c of respin.landed) noteTier(c.kind);
    if (respin.landed.length) Sound.playSfx('coinLand');

    await wait(HOLD_AND_WIN_RESPIN_PAUSE_MS);
  }

  await wait(300);
  // Jackpot coins get their tier's own award animation before the payout card.
  for (const tier of wonTiers) await playJackpotAward(tier);

  Sound.playSfx('bonusTotalWin');
  await playPopup('bonusSpinsTotalWin', result.total_win);
  clearCoinAmountLabels();
  holdAndWinLocked = null;
  // Put the base reels back BEFORE the screen is revealed again — the swap
  // happens under the transition's blackout, so the player never sees the
  // round's leftover coins/holes.
  if (baseGrid) {
    await applyGrid(baseGrid);
    await applyCoinValues(baseCoins);
  }
  await setFreeSpinsMode(false);
  delete document.getElementById('screen').dataset.round;
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

  const jackpotBtn = document.getElementById('devJackpot');
  if (jackpotBtn) {
    jackpotBtn.addEventListener('click', async () => {
      for (const tier of JACKPOT_TIERS) await playJackpotAward(tier);
    });
  }
}

// --- Viewport / background --------------------------------------------------
//
// The whole game is authored in a fixed design canvas (the size of the
// delivered backgrounds) and #stage is contain-scaled to the viewport.
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

// Backgrounds are flat PNGs in this delivery (no Spine background object), one
// per mode per device.
function setBackground(mode) {
  const desk = mode === 'base' ? 'bg_base_desk.png' : 'bg_bonus_desk.png';
  const mob = mode === 'base' ? 'bg_mob_base.png' : 'bg_mob_bonus.png';
  document.getElementById('bgLayer').src = `${ASSET_ROOT}/${isMobileLayout() ? mob : desk}`;
}

// --- Logo -------------------------------------------------------------------
//
// Static PNG (game_logo.png), which is exactly what the builder manifest
// places on the arch — a decor.image, not an animation object.
//
// The delivery DOES also include a `logo/` Spine export with a single `idle`
// clip, deliberately not wired up: the manifest puts the logo ABOVE the
// cabinet (z4 vs z3), the cabinet lives on #stageFront over the Spine canvas,
// so the skeleton would have to draw on a THIRD layer stacked above the front
// stage — and a second SpineCanvas created on this page never started its
// render loop (the vendor's SpineCanvas only begins once its own AssetManager
// reports idle, and this one is constructed while the shared preload is still
// in flight). Not worth a GL context for a shine loop; revisit if product
// wants the animated logo.

let lastMobile = null;
let pendingDeviceRebuild = false;

// Cell geometry differs per device, and every cell/strip carries pixel
// positions, so flipping orientation has to rebuild the grid onto the new
// pitch. It must NEVER do that mid-spin, though: the rebuild tears down every
// cell instance, so a clip the spin is awaiting can no longer complete and the
// spin would hang. Defer to the end of the spin instead.
async function handleResize() {
  updateStageScale();
  const nowMobile = isMobileLayout();
  if (nowMobile === lastMobile) return;
  lastMobile = nowMobile;
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
  // teardownCellInstances dropped the coin labels with the cells they were
  // pinned to — put them back if a Hold & Win round is on screen.
  if (holdAndWinLocked) paintLockedCoins(holdAndWinLocked);
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
  setBackground(currentMode());
  setupDevPanel();

  await preloadAssets();
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));
  if (window.Preloader) window.Preloader.done();

  window.__slot = { stage, cellInfos };
}

init();
