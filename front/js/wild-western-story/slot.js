// Wild Western Story — game-specific wiring on top of spine-engine.js,
// adapted from ../east-discovery/slot.js. Mechanics kept: reel motion,
// win-cell sequencing, scatter anticipation, free-spins mode, Spine popups,
// inline win amount, expanding-wild substitution. Mechanics DROPPED (this
// theme has no coins / Hold & Win): coin-multiplier labels, hold&win respin
// theatre, collector symbol, ambient-environment Spine decoration, standing
// hero character.
//
// Asset gaps to fill later (see front/img/wild-western-story/README.md):
//   * Export/wild — the cowgirl WILD symbol art was NOT delivered. Wild cells
//     currently render as a dashed "missing" box. Once the asset lands, decide
//     whether it ships a reel-height "big" variant for a grow animation and
//     wire revealExpandedWild accordingly (see the TODO there).
//   * No frame.png / decorative props — reels sit on the CSS placeholder panel.

const ASSET_ROOT = 'img/wild-western-story';

// The delivered Spine exports were checked to use straight (non-premultiplied)
// alpha, same as East Discovery — go through this wrapper, not
// SpineEngine.SpineResource.load directly, so soft edges blend correctly.
function loadSpineResource(folderPath) {
  return SpineEngine.SpineResource.load(stage.assetManager, folderPath, { premultipliedAlpha: false });
}

const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild', // asset not delivered yet — renders as a missing-box placeholder
  wolf: 'wolf',
  whiskey: 'whickey', // folder is spelled "whickey" in the delivered assets
  gun: 'gun',
  a: 'A',
  k: 'K',
  q: 'Q',
  j: 'J',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// Codes eligible as random spin-loop filler — excludes scatter (a trigger
// symbol, shouldn't blur past as filler) and wild (no art yet).
const FILLER_CODES = SYMBOL_CODES.filter((c) => c !== 'scatter' && c !== 'wild');

// scatter and wild ship a live idle loop on the base grid; every other symbol
// only carries a "win" clip (a plain static image until it wins). wild's
// skeleton bundles both a grid-cell "small" variant and a reel-height "big"
// variant (idle_big/win_big/move) — the grid uses the small clips.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// Delivered clip inventory: scatter = idle/landing/win; wild = small_*/big_*
// variants under the names below; every other symbol = win only. Falls back
// to the default names.
const SYMBOL_CLIPS = {
  wild: { idle: 'idle_small', landing: 'landing_small', win: 'win_small' },
};
const DEFAULT_CLIPS = { idle: 'idle', landing: 'landing', win: 'win' };
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || DEFAULT_CLIPS[kind];
}

// gun/wolf shipped their static frame as "statik.png"; wild ships small/big
// static frames; the rest use static.png. The grid always uses wild's small one.
const SYMBOL_STATIC_OVERRIDE = { gun: 'statik.png', wolf: 'statik.png', wild: 'static-small.png' };
function staticFileFor(code) {
  return SYMBOL_STATIC_OVERRIDE[code] || 'static.png';
}

// Attract-mode layout shown before the first real spin (also fixes the grid's
// 3 rows x 5 reels shape — no real backend game exists for this theme yet, so
// this placeholder is what renders until that's wired up).
const SYMBOL_LAYOUT = [
  ['scatter', 'wolf', 'q', 'a', 'j'],
  ['a', 'k', 'wild', 'whiskey', 'q'],
  ['q', 'gun', 'k', 'j', 'wolf'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/Popup's/popup_big_win`,
  epicWin: `${ASSET_ROOT}/Popup's/popup_epic_win`,
  megaWin: `${ASSET_ROOT}/Popup's/popup_mega_win`,
  bonusSpinsWin: `${ASSET_ROOT}/Popup's/popup_bonus_spins_win`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/Popup's/popup_bonus_spins_total_win`,
  buyFreeSpins: `${ASSET_ROOT}/Popup's/popup_buy_bonus_spins`,
};
// Bone the win-amount overlay tracks, per popup (bone names differ between the
// delivered skeletons — read from each animation.json). Falls back to the
// first that resolves at runtime.
const POPUP_AMOUNT_BONE = {
  bigWin: 'bone_input',
  epicWin: 'bone_input_number',
  megaWin: 'bone_input_number',
  bonusSpinsWin: 'bone_main_star_number',
  bonusSpinsTotalWin: 'bone_main_input_number',
  buyFreeSpins: 'bone_main_input_number',
};
const POPUP_AMOUNT_BONE_FALLBACKS = ['bone_input_number', 'bone_input', 'bone_main_input_number', 'main_input'];

const DIM_TRANSITION_MS = 320;
const REEL_LOOP_STEP_MS = 420;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 500;

let stage = null;
let cellInfos = [];
let reelCols = [];
// Reel-height "big wild" overlays currently on screen (see revealExpandedWild).
// Cleared at the start of every spin, same lifecycle as the small cell instances.
let expandedWildOverlays = [];

// --- Win-line animation (trial, this game only — see front/img/wild-western-story/Win_Lines) ---
//
// One Spine skeleton shipping 11 named animations ("1".."11"), one per
// payline. The backend defines 20 paylines total (app/seed/wild_western_story.py),
// but only these 11 are actually live for the client. Animation name is NOT
// the payline index — confirmed against the client's own line reference,
// this session: animations "1".."5" line up with payline indices 1-5, but
// "6".."11" are indices 12-17 (the backend's indices 6-11 are shapes the
// client doesn't use and have no line art at all). A win on any payline
// index missing from this map just shows no line art.
const PAYLINE_TO_WIN_LINE_ANIMATION = {
  1: '1', 2: '2', 3: '3', 4: '4', 5: '5',
  12: '6', 13: '7', 14: '8', 15: '9', 16: '10', 17: '11',
};
const WIN_LINE_ASSET_PATH = `${ASSET_ROOT}/Win_Lines`;
let winLineResourcePromise = null;

// This skeleton's animation.json has no setup-pose bounds baked in (its
// "skeleton" block only carries hash/version, no x/y/width/height — some
// export configs omit it), so resource.bounds comes back empty and the
// normal fit-to-anchor math (SpineInstance._placeInAnchor) would divide by
// an undefined width/height. Same class of problem as wild's small-variant
// override above, just needing the union across every animation (each
// payline's own line occupies a different slice of the grid) instead of one
// named slot.
//
// Precomputed once (union of all 11 animations' AABB, sampled across each
// timeline via the runtime's own Skeleton.getBounds) rather than recomputed
// live in the browser — that scan is real per-frame Spine runtime work
// (skeleton pose + world-transform + bounds, x11 animations x7 samples)
// which is cheap on desktop but blocked the main thread long enough on a
// real mobile device to trip the browser's own "page unresponsive" state
// (reported live, this session). If Win_Lines/animation.json is ever
// replaced, recompute this once (e.g. temporarily reinstate the scan,
// log the result, paste it back in here) rather than doing it on every load.
const WIN_LINE_BOUNDS_OVERRIDE = { x: -433.9161688016173, y: -211.514175415039, width: 856.6346179651904, height: 438.3254852294921 };

function getWinLineResource() {
  if (!winLineResourcePromise) winLineResourcePromise = loadSpineResource(WIN_LINE_ASSET_PATH);
  return winLineResourcePromise;
}

let winLineInstance = null;
let winLineLoopTimeout = null;

// Drawn as an overlay (not base), same layer as popups — so it always
// renders on top of every base-layer win clip (the winning symbols' own
// glow/loop), never underneath them. Anchored to .reel__grid, i.e. the
// frame's actual opening, so it's centered on the reel regardless of
// viewport scale. Always plays the clip exactly ONCE and resolves when it
// settles — never loop:true here. The caller owns the repeat cadence
// (previewWinLine below for a lone win; playMultiLineWinSequence's own
// per-phase step() for a multi-line win) — looping internally on top of
// that used to race the caller's own timer on a different clock, which is
// what caused the line to visibly play twice per symbol-glow cycle
// (product, this session).
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
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

const symbolResourceCache = {};

// wild's skeleton reports its setup bounds for the tall "big" variant
// (~249x592), but the grid cell shows the "small" variant. The small art is
// the 'wild_small' slot's own region attachment (static-small2) — play
// idle_small, read that region's world bounds, and use it as the fit/centre
// box so the grid instance renders at the small silhouette's real size.
function computeWildSmallBoundsOverride(resource) {
  try {
    const probe = new spine.Skeleton(resource.skeletonData);
    probe.setToSetupPose();
    const state = new spine.AnimationState(resource.animationStateData);
    state.setAnimation(0, 'idle_small', true);
    state.update(0);
    state.apply(probe);
    probe.updateWorldTransform();

    const slot = probe.findSlot('wild_small');
    const att = slot && slot.getAttachment();
    if (!att || typeof att.computeWorldVertices !== 'function') return null;

    // Region attachment = 4 corners (8 floats); mesh = worldVerticesLength.
    const len = att.worldVerticesLength || 8;
    const verts = new Float32Array(len);
    att.computeWorldVertices(slot, verts, 0, 2);
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < verts.length; i += 2) {
      minX = Math.min(minX, verts[i]);
      maxX = Math.max(maxX, verts[i]);
      minY = Math.min(minY, verts[i + 1]);
      maxY = Math.max(maxY, verts[i + 1]);
    }
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  } catch (err) {
    console.warn('wild small-bounds compute failed:', err);
    return null;
  }
}

function getSymbolResource(code) {
  if (!symbolResourceCache[code]) {
    const folder = SYMBOL_FOLDERS[code];
    symbolResourceCache[code] = loadSpineResource(`${ASSET_ROOT}/Export/${folder}`).then((resource) => {
      if (code === 'wild') resource.wildSmallBoundsOverride = computeWildSmallBoundsOverride(resource);
      return resource;
    });
  }
  return symbolResourceCache[code];
}

// No measured per-symbol offsets yet — every static frame is authored centered
// in its own canvas, so default to no correction. A live override from Anim
// Lab's "Калибровать" button still wins if one is set for this game.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('wild-western-story', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  img.src = `${ASSET_ROOT}/Export/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`;
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
  hideWinLine();
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
  const folder = SYMBOL_FOLDERS[code];
  info.img.src = `${ASSET_ROOT}/Export/${folder}/${staticFileFor(code)}`;
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);

  try {
    const resource = await getSymbolResource(code);
    const bounds = (code === 'wild' && resource.wildSmallBoundsOverride) || resource.bounds;
    if (info.anchor) {
      info.anchor.style.width = `${bounds.width}px`;
      info.anchor.style.height = `${bounds.height}px`;
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'wild-western-story', code);
    }
    const instance = resource.createInstance();
    instance.anchorEl = info.anchor || info.cell;
    instance.fit = 1;
    if (code === 'wild' && resource.wildSmallBoundsOverride) {
      instance.boundsOverride = resource.wildSmallBoundsOverride;
    }
    info.instance = instance;

    if (SPECIAL_SYMBOLS.has(code)) {
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      stage.addBase(instance);
      if (code === 'wild') {
        // Rule 1 + 3: on landing play landing_small once, then settle into
        // idle_small. A win (rule 4) or expansion (rules 2/5/6) overrides this
        // afterwards via playWinCells / revealExpandedWild.
        instance.play('landing_small', false);
        instance.onSettle = () => {
          instance.onSettle = null;
          instance.play('idle_small', true);
        };
      } else {
        instance.play(clipName(code, 'idle'), true);
      }
    }
  } catch (err) {
    console.warn(`Spine load failed for symbol "${code}" (${folder}):`, err);
  }
}

function playWinAnimationOnce(info) {
  const { instance, img } = info;
  if (!instance) return Promise.resolve();
  img.style.visibility = 'hidden';
  stage.addBase(instance);
  return new Promise((resolve) => {
    instance.play(clipName(info.symbol, 'win'), false);
    instance.onSettle = () => {
      instance.onSettle = null;
      resolve();
    };
  });
}

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

function playMultiLineWinSequence(groups, allWinInfos, lineWins) {
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

  let groupIndex = -1;
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

// --- Reel motion (game-agnostic — see the other themes for the full writeup
// of how the masked-column scroll technique works) -----------------------

function startReelLoop() {
  Sound.playSfx('spinStart');
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
    for (const code of ReelMath.buildLoopSequence(currentCodes, randomTrio)) {
      const { cell } = createCellNode(code);
      stripEl.appendChild(cell);
    }

    stripEl.style.setProperty('--reel-loop-distance', `${ReelMath.ROW_STEP * GRID_ROWS}px`);
    stripEl.style.setProperty('--reel-loop-duration', `${REEL_LOOP_STEP_MS}ms`);
    stripEl.style.transform = 'translateY(0px)';
    void stripEl.offsetHeight;
    stripEl.classList.add('is-looping');
  }
}

function stopReelLoop() {
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
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
// the end that, stretched over a much longer duration, there's a long
// near-motionless stretch partway through — reads as "it landed", followed
// by one final small creep into the true resting spot, i.e. "falls, then
// falls again" (reported live). Fix: two separate phases instead of one
// stretched curve — a plain LINEAR pre-roll (no easing, so no plateau,
// just a steady "still spinning" scroll) for the wait, followed by the
// *exact* same short eased landing normal columns already use (proven fine,
// never stretched).
const ANTICIPATION_PREROLL_MS = 900;
const ANTICIPATION_PREROLL_FILLER_COUNT = 16;

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false, fillerCodeFn = randomSymbolCode) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    setTimeout(() => {
      stripEl.classList.remove('is-looping');
      stripEl.style.transition = 'none';
      stripEl.innerHTML = '';

      const sequence = [
        ...finalCodes,
        ...Array.from({ length: REEL_LAND_FILLER_COUNT }, fillerCodeFn),
        ...Array.from({ length: prerollCount }, fillerCodeFn),
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
        setTimeout(finish, REEL_LAND_DURATION_MS + 200);
      };

      if (isAnticipating) {
        const prerollStartY = -((REEL_LAND_FILLER_COUNT + prerollCount) * ReelMath.ROW_STEP);
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

// --- Expanding wild --------------------------------------------------------
//
// Big wild reveal: the wild skeleton bundles a reel-height "big" variant
// (idle_big / win_big / move) alongside the grid-cell "small" one. When a
// reel expands, grow one big wild overlay over that whole column and fade the
// 3 small wild cells out — same technique as East Discovery's revealExpandedWild.

// Tuning for the reel-height overlay (fit-to-column-height). Adjust live.
const BIG_WILD_FIT = 1.0;
const BIG_WILD_VERTICAL_OFFSET_RATIO = 0;

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

// Grow the reel-height wild over a column. Sequence per product:
//   move (expansion, once) -> win_big (loop) if the reel is in a winning
//   combination [rule 5], otherwise idle_big (loop) [rule 6].
// The 3 small wild cells fade out while the big one grows.
async function revealExpandedWild(col, { win = false } = {}) {
  const { stripEl } = reelCols[col];
  const gridEl = document.querySelector('.reel__grid');
  const resource = await getSymbolResource('wild');
  const overlay = resource.createInstance();
  overlay.anchorEl = stripEl; // horizontal centre = this reel column
  overlay.heightAnchorEl = gridEl; // vertical extent = the real frame opening
  overlay.fitMode = 'height';
  overlay.fit = BIG_WILD_FIT;
  overlay.verticalOffsetRatio = BIG_WILD_VERTICAL_OFFSET_RATIO;
  overlay.boundsOverride = resource.bounds; // the big variant's own (tall) bounds, NOT the small override
  overlay.reelCol = col;
  overlay.winLoopTimeout = null;
  stage.addOverlay(overlay);
  expandedWildOverlays.push(overlay);

  const fadeInfos = [0, 1, 2].map((row) => cellInfos[row * GRID_COLS + col]).filter(Boolean);
  const fadeDone = fadeCellsToTransparent(fadeInfos, 450);

  Sound.playSfx('wildGrow');
  // Rule 2 / 5: the expansion animation is `move`, played once.
  await new Promise((res) => {
    overlay.play('move', false);
    overlay.onSettle = () => {
      overlay.onSettle = null;
      res();
    };
  });
  await fadeDone;
  if (win) Sound.playSfx('wildWin');
  overlay.play(win ? 'win_big' : 'idle_big', true); // rule 5 (win) / rule 6 (idle)
  return overlay;
}

function celebrateExpandedWild(col, wildEvents, winningCols) {
  const grew = wildEvents.some((e) => e.reel === col && (e.event === 'expanded' || e.event === 'walked'));
  if (grew) return revealExpandedWild(col, { win: winningCols.has(col) });
  return Promise.resolve(null);
}

// Dev/testing preview (no backend yet to send real wild_events): turn a whole
// column to wild, grow the big wild over it (move -> win_big or idle_big),
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
    await wait(2200); // let move + win_big/idle_big loop play a while
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

// Columns that carry a winning line/count this spin — drives win_small (rule 4,
// via playWinCells) and win_big (rule 5, via celebrateExpandedWild).
function winningColumnSet(lineWins, countWins) {
  const cols = new Set();
  for (const w of [...(lineWins || []), ...(countWins || [])]) {
    for (const pos of w.positions || []) cols.add(pos.col);
  }
  return cols;
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: product ("не должны одновременно крутиться все оставшиеся
// барабаны") wants a single reel revealed, then the next, and so on.
// collectAnticipationColumns only flags a column while the trigger is still
// undecided, so once one of them lands the deciding symbol, later columns
// fall out of the flagged set on their own — those just land at normal
// speed, still one at a time, since the suspense is already resolved.
async function landReels(grid, anticipationColumns = [], wildEvents = [], lineWins = [], countWins = []) {
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
    await celebrateExpandedWild(col, wildEvents, winningCols);
  }
}

// --- Screen dim -------------------------------------------------------------

let dimActiveCount = 0;
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

async function withScreenDim(mutateFn, { opaque = false } = {}) {
  pushScreenDim(opaque);
  await wait(DIM_TRANSITION_MS);
  try {
    await mutateFn();
  } finally {
    popScreenDim(opaque);
  }
}

// Swaps the on-screen mode (grid background) for `next`. Shared by the plain
// leave-bonus dim and the enter-bonus intro so the two never drift apart.
function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
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

function resolveAmountBone(instance, key) {
  const preferred = POPUP_AMOUNT_BONE[key];
  for (const name of [preferred, ...POPUP_AMOUNT_BONE_FALLBACKS]) {
    if (name && instance.skeleton.findBone(name)) return name;
  }
  return null;
}

function startPopupAmountTracking(instance, key, amount) {
  const canvasEl = document.getElementById('spineCanvas');
  const el = document.getElementById('popupAmount');
  el.textContent = Number(amount).toLocaleString('en-US');
  el.classList.add('is-visible');

  const boneName = resolveAmountBone(instance, key);
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
        popupResourceCache[key] = loadSpineResource(folder);
      }
      const resource = await popupResourceCache[key];

      const instance = resource.createInstance();
      instance.anchorEl = document.getElementById('screen');
      // Portrait doubles the popup (product); glow overflow accepted.
      instance.fit = isMobileLayout() ? 2 : 1;
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

// Win-tier / dev popups: own their (partial) screen dim, as before.
function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Dev panel --------------------------------------------------------------

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

  // Dev button previews the non-winning expansion (move -> idle_big, rule 6);
  // clicking a wild cell previews the winning one (move -> win_big, rule 5).
  const bigWildBtn = document.getElementById('devBigWild');
  if (bigWildBtn) bigWildBtn.addEventListener('click', () => previewBigWild(Math.floor(GRID_COLS / 2), false));
}

// Design authored at bg_base.png's native 1932-wide canvas; freeze the scale
// at 1612px and crop below that, same behavior as East Discovery.
const DESKTOP_DESIGN_MAX_WIDTH = 1932;
const DESKTOP_DESIGN_MIN_WIDTH = 1612;

// Experimental "fit everything, no scroll" layout — see
// wild-western-story.css body.layout-fit and ReelMath.fitScale.
const FIT_RESERVE_WIDTH_PX = 360;
const FIT_RESERVE_HEIGHT_PX = 60;

function isFullscreenFitLayout() {
  return document.body.classList.contains('layout-fit');
}

function updateReelScale() {
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
    document.documentElement.style.setProperty(
      '--reel-scale',
      String(
        ReelMath.viewportScale(
          viewportWidth,
          DESKTOP_DESIGN_MAX_WIDTH,
          DESKTOP_DESIGN_MIN_WIDTH / DESKTOP_DESIGN_MAX_WIDTH,
        ),
      ),
    );
  }

  document.documentElement.style.setProperty(
    '--reel-scale-mobile',
    String(ReelMath.mobileReelScale(viewportWidth, frameWidth)),
  );
}

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function bgSrcFor(mode) {
  if (isMobileLayout()) {
    return mode === 'base' ? `${ASSET_ROOT}/img/mob_Base_bg.png` : `${ASSET_ROOT}/img/mob_Bonus_bg.png`;
  }
  return mode === 'base' ? `${ASSET_ROOT}/img/bg_base.png` : `${ASSET_ROOT}/img/bg_bonus.png`;
}

function updateBgForLayout() {
  const screen = document.getElementById('screen');
  document.getElementById('bgLayer').src = bgSrcFor(screen.dataset.mode || 'base');
}

async function init() {
  await SlotCalibration.load(); // must resolve before buildReelGrid's applyStaticContentOffset
  Sound.playMusic('base');
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
  setupDevPanel();

  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));

  window.__slot = { stage, cellInfos };
}

init();
