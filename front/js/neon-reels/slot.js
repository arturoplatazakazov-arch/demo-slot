// Neon Reels — game-specific wiring on top of spine-engine.js / reel-math.js,
// built from the slot-builder manifest (builder_drafts row, code
// "neon-reels"). Structurally a trimmed east-discovery/slot.js: same reel-
// motion / win-sequencing / popup plumbing, minus that theme's hero
// character, ambient environment, collector-tiger and hold-&-win features
// (none of which exist in this manifest's mechanics: line_pay, scatter,
// free_spins, coin_multiplier).
//
// Layout differs too: instead of scaling a frame-hole-measured reel, the
// whole design box (.stage) is scaled to the viewport and every element is
// pinned by its manifest coordinates (see css/neon-reels.css). The reel grid
// keeps a fixed intrinsic cell size so the scroll math runs in one constant
// unit (NR_ROW_STEP) regardless of device.

const ASSET_ROOT = 'img/neon-reels';

// Every neon-reels export's atlas declares `pma:true` (premultiplied alpha),
// same as Amy's Fruit Farm and spine-engine.js's own default — kept as a
// named wrapper so a future straight-alpha re-export only needs one edit.
function loadSpineResource(folderPath) {
  return SpineEngine.SpineResource.load(stage.assetManager, folderPath, { premultipliedAlpha: true });
}

// code -> uploaded Spine export folder under front/img/neon-reels/Export/.
// Matches the manifest's animation asset folders; wild/scatter/coin use the
// export's own capitalization.
const SYMBOL_FOLDERS = {
  scatter: 'SKATTER',
  wild: 'WILD',
  coin: 'Coin',
  geisha: 'geisha',
  samurai: 'samurai',
  sensei: 'sensei',
  yakudza: 'yakudza',
  a: 'A',
  k: 'K',
  q: 'Q',
  j: 'J',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// scatter/wild ship a live idle loop (idle/landing/win clips) shown on the
// base grid; every other symbol — including coin — ships only a single "win"
// clip (confirmed per animation.json), so they stay a plain static image
// until they actually win.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

const DEFAULT_CLIPS = { idle: 'idle', landing: 'landing', win: 'win' };
// Letters + high symbols + coin only have "win" — it does every job.
const SINGLE_WIN_CLIP = { idle: 'win', landing: 'win', win: 'win' };
const SYMBOL_CLIPS = {
  coin: SINGLE_WIN_CLIP,
  geisha: SINGLE_WIN_CLIP,
  samurai: SINGLE_WIN_CLIP,
  sensei: SINGLE_WIN_CLIP,
  yakudza: SINGLE_WIN_CLIP,
  a: SINGLE_WIN_CLIP,
  k: SINGLE_WIN_CLIP,
  q: SINGLE_WIN_CLIP,
  j: SINGLE_WIN_CLIP,
};
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || DEFAULT_CLIPS[kind];
}

function staticFileFor() {
  return 'static.png';
}

// Attract-mode layout shown before the first real spin — also fixes the
// grid's shape: 3 rows x 5 reels (manifest grid: rows 3, reels 5).
const SYMBOL_LAYOUT = [
  ['q', 'geisha', 'wild', 'a', 'samurai'],
  ['scatter', 'k', 'coin', 'sensei', 'j'],
  ['yakudza', 'a', 'q', 'coin', 'scatter'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

// Fixed intrinsic cell pitch (190px cell + 10px gap — the desktop
// reel_block) that the CSS grid and the scroll math below both agree on.
// Not ReelMath.ROW_STEP (that's the shared 200/10 = 210 default other games
// use) — this game's cells are 190px, so the scroll strip travels 200px per
// row. Named NR_* to avoid colliding with reel-math.js's own top-level
// consts in the shared global scope (no ES modules here).
const NR_ROW_STEP = 200;

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/Export/Popup's/big_win`,
  epicWin: `${ASSET_ROOT}/Export/Popup's/epic_win`,
  megaWin: `${ASSET_ROOT}/Export/Popup's/mega_win`,
  bonusSpinsWin: `${ASSET_ROOT}/Export/Popup's/free_spins`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/Export/Popup's/bonus_spins – total_win`,
  buyFreeSpins: `${ASSET_ROOT}/Export/Popup's/bay_free_spins`,
};
// Every popup skeleton carries a "bone_input" bone sitting where the win-
// amount plaque belongs (checked each animation.json's bone list). Popups
// use start/idle/end clips (there's also a "full" variant, unused here).
const POPUP_AMOUNT_BONE = 'bone_input';
const POPUP_CLIPS = { start: 'start', idle: 'idle', end: 'end' };

// The coin skeleton carries a "bone_numb" bone where its multiplier value
// ("10X", "1000X", ...) belongs — same per-cell bone-tracking idea as the
// popup amount, but several can show at once.
const COIN_MULTIPLIER_BONE = 'bone_numb';

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 100; // 0.1s между колонками (product), отсчёт от конца очистки
const WIN_LOOP_PAUSE_MS = 500;

// Manifest design boxes (layouts.<device>.w/h) — the .stage's intrinsic size,
// scaled to fit the viewport by updateStageScale.
const DESIGN = {
  desktop: { w: 1932, h: 940 },
  mobile: { w: 780, h: 1416 },
};

let stage = null;
let cellInfos = [];
let reelCols = [];

// --- Win-line animation (see front/img/neon-reels/Win_Lines) ---------------
//
// One Spine skeleton shipping 11 named animations ("1".."11"), one per
// payline — ported from wild-western-story/slot.js once confirmed there.
// The backend defines only these 11 paylines now (the other 9 shapes were
// removed from every 5x3 game's config, product this session — no art for
// them, so they no longer pay at all). Animation name is NOT the payline
// index: "1".."5" line up with payline indices 1-5, but "6".."11" are
// indices 12-17 (see app/seed/neon_reels.py's Payline rows).
const PAYLINE_TO_WIN_LINE_ANIMATION = {
  1: '1', 2: '2', 3: '3', 4: '4', 5: '5',
  12: '6', 13: '7', 14: '8', 15: '9', 16: '10', 17: '11',
};
const WIN_LINE_ASSET_PATH = `${ASSET_ROOT}/Win_Lines`;
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
    // Confirmed straight (non-premultiplied) alpha — this game's own
    // loadSpineResource wrapper defaults to premultipliedAlpha:true for its
    // own exports, so this bypasses it and calls SpineResource.load
    // directly rather than inherit the wrong flag.
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

const symbolResourceCache = {};

function getSymbolResource(code) {
  if (!symbolResourceCache[code]) {
    const folder = SYMBOL_FOLDERS[code];
    symbolResourceCache[code] = loadSpineResource(`${ASSET_ROOT}/Export/${folder}`);
  }
  return symbolResourceCache[code];
}

// Live per-symbol {dx,dy} nudge from Anim Lab's "Калибровать" button
// (front/js/anim-lab.js via slot-calibration.js). Nothing baked in yet —
// symbols center on their cell by CSS default until a calibration is written.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('neon-reels', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  img.decoding = 'async'; // strips rebuild mid-animation; keep decode off the main thread
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
  stopCoinMultiplierTracking();
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
    const bounds = resource.bounds;
    if (info.anchor) {
      info.anchor.style.width = `${bounds.width}px`;
      info.anchor.style.height = `${bounds.height}px`;
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'neon-reels', code);
    }
    const instance = resource.createInstance();
    instance.anchorEl = info.anchor || info.cell;
    instance.fit = 1;
    info.instance = instance;

    if (SPECIAL_SYMBOLS.has(code)) {
      info.img.style.visibility = 'hidden';
      instance.onSettle = null;
      stage.addBase(instance);
      instance.play(clipName(code, 'idle'), true);
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

// --- Coin multiplier value labels ------------------------------------------

let coinMultiplierRaf = null;
let coinMultiplierTrackers = [];

function ensureCoinMultiplierTrackingLoop() {
  if (coinMultiplierRaf) return;
  const canvasEl = document.getElementById('spineCanvas');
  const tick = () => {
    for (const { instance, el } of coinMultiplierTrackers) {
      const bone = instance.skeleton.findBone(COIN_MULTIPLIER_BONE);
      if (bone) {
        const pos = worldToScreen(bone.worldX, bone.worldY, canvasEl);
        el.style.left = `${pos.left}px`;
        el.style.top = `${pos.top}px`;
      }
    }
    coinMultiplierRaf = requestAnimationFrame(tick);
  };
  tick();
}

function stopCoinMultiplierTracking() {
  if (coinMultiplierRaf) cancelAnimationFrame(coinMultiplierRaf);
  coinMultiplierRaf = null;
  for (const { el } of coinMultiplierTrackers) el.remove();
  coinMultiplierTrackers = [];
}

// Plays the coin's single clip exactly once as it lands, then pulls the
// spine off stage so the cell's static PNG (info.img) is the resting art
// again — the value label is what persists, not a repeating animation
// (product, this session: was alpha:0 + loop:true, i.e. invisible AND
// looping forever — the landing flourish should actually be seen once, not
// hidden). Matches east-discovery/slot.js's own showCoinMultiplierLabel.
function showCoinMultiplierLabel(info, value) {
  const instance = info.instance;
  if (!instance) return;
  info.img.style.visibility = 'hidden';
  stage.addBase(instance);
  instance.play(clipName('coin', 'idle'), false);
  instance.onSettle = () => {
    instance.onSettle = null;
    stage.removeBase(instance);
    info.img.style.visibility = '';
  };

  const el = document.createElement('div');
  el.className = 'coin-multiplier-amount';
  el.textContent = `${value}X`;
  document.getElementById('screen').appendChild(el);
  coinMultiplierTrackers.push({ instance, el });
  ensureCoinMultiplierTrackingLoop();
}

function maybeShowCoinMultiplierLabels(col, coinMultiplier) {
  if (!coinMultiplier) return;
  for (const pos of coinMultiplier.positions) {
    if (pos.col !== col) continue;
    const info = cellInfos[pos.row * GRID_COLS + col];
    if (info && info.symbol === 'coin') showCoinMultiplierLabel(info, pos.value);
  }
}

function playCoinMultiplierReveal(coinMultiplier) {
  if (!coinMultiplier || !coinMultiplier.applied) return;
  let any = false;
  for (const pos of coinMultiplier.positions) {
    const info = cellInfos[pos.row * GRID_COLS + pos.col];
    if (info && info.symbol === 'coin' && info.instance) {
      info.instance.skeleton.color.a = 1;
      playWinAnimationOnce(info);
      any = true;
    }
  }
  if (any) Sound.playSfx('coinLand');
}

// --- Inline win-amount (base wins with no Spine popup) ---------------------

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

// --- Reel motion -----------------------------------------------------------

// The reel only clips (overflow:hidden, see css) while a spin is running, so
// resting symbol art can overflow its cell uncut. Add the flag when motion
// starts; landReels/stopReelLoop clear it once everything has settled.
function setReelSpinning(on) {
  const reelEl = document.getElementById('reel');
  if (reelEl) reelEl.classList.toggle('is-spinning', on);
}

// No spinning-loop phase at all (product, this session: the loop start
// "два раза дергается... сразу чтоб падали сверху"): on spin press the
// resting symbols just drop out of view downward (accelerating, clipped by
// .reel.is-spinning), the reel stands empty while the server answers, and
// the final symbols then fall in from the top via landReel's usual eased
// landing. landReel awaits reelClearDone so no column starts landing while
// the old symbols are still mid-drop.
const REEL_CLEAR_MS = 260;

let reelLoopGeneration = 0; // invalidates a pending clear when a newer spin supersedes it
let reelClearDone = Promise.resolve();

function startReelLoop() {
  Sound.playSfx('spinStart');
  setReelSpinning(true);
  teardownCellInstances();
  const gen = ++reelLoopGeneration;
  for (const { stripEl } of reelCols) {
    stripEl.classList.remove('is-looping');
    stripEl.style.transition = 'none';
    stripEl.style.transform = 'translateY(0px)';
  }
  reelClearDone = new Promise((resolve) => {
    // Two rAFs: one full frame so transition:none + transform reset apply
    // before the drop transition starts (same-frame kickoff dropped frames
    // on mobile and opened the move at a visible crawl).
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (gen !== reelLoopGeneration) return resolve();
      for (const { stripEl } of reelCols) {
        stripEl.style.transition = `transform ${REEL_CLEAR_MS}ms cubic-bezier(0.5, 0, 0.9, 0.4)`;
        stripEl.style.transform = `translateY(${NR_ROW_STEP * (GRID_ROWS + 1)}px)`;
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
  setReelSpinning(false);
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

function landReel(colIndex, finalCodes, delayMs, isAnticipating = false) {
  const { stripEl } = reelCols[colIndex];
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
  const prerollCount = isAnticipating ? ANTICIPATION_PREROLL_FILLER_COUNT : 0;

  return new Promise((resolve) => {
    (async () => {
      // The clear-out drop must finish first, and the per-column stagger
      // counts from the END of the clear — not from the spin press. Counting
      // from the press meant every column whose delay was shorter than the
      // clear duration woke up at the same instant, so the first four reels
      // landed simultaneously (reported live).
      await reelClearDone;
      await wait(delayMs);
      stripEl.classList.remove('is-looping');
      stripEl.style.transition = 'none';
      stripEl.innerHTML = '';

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

      const landStartY = -(REEL_LAND_FILLER_COUNT * NR_ROW_STEP);

      const beginLanding = () => {
        stripEl.style.transition = `transform ${REEL_LAND_DURATION_MS}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
        stripEl.style.transform = 'translateY(0px)';

        setTimeout(() => Sound.playSfx(stopSound), Math.max(0, REEL_LAND_DURATION_MS - 200));

        // Drop every cell below the 3 final rows the moment the strip has all
        // but settled — NOT only on transitionend. The row right under the last
        // visible one overlaps ~15px up into the reel's bottom hole margin at
        // rest (symbol art is 220px on a 190px cell), so if it's still in the
        // DOM for the final painted frame it flashes there for ~1 frame on stop
        // (reported: "4th row briefly visible after the spin"). Watching the
        // real translateY (px-based) instead of a timer keeps this independent
        // of landDuration/easing.
        let fillerRemoved = false;
        const removeFiller = () => {
          if (fillerRemoved) return;
          fillerRemoved = true;
          for (const cell of cellEls.slice(3)) cell.remove();
        };
        const currentTranslateY = () => {
          const t = getComputedStyle(stripEl).transform;
          return t && t !== 'none' ? new DOMMatrixReadOnly(t).m42 : 0;
        };
        const watchSettle = () => {
          if (fillerRemoved || settled) return;
          if (currentTranslateY() >= -2) removeFiller();
          else requestAnimationFrame(watchSettle);
        };
        // The strip can only be near translateY(0) in the transition's final
        // stretch, so start the per-frame computed-style polling there instead
        // of on frame one — getComputedStyle forces a style recalc, and doing
        // that 60x/s across 5 landing columns was real main-thread cost on
        // phones for frames where the answer was guaranteed "not yet".
        setTimeout(() => requestAnimationFrame(watchSettle), Math.max(0, REEL_LAND_DURATION_MS - 250));

        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          if (isAnticipating) reelCols[colIndex].colEl.classList.remove('is-anticipating');
          stripEl.removeEventListener('transitionend', onTransitionEnd);
          removeFiller();
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
        const prerollStartY = -((REEL_LAND_FILLER_COUNT + prerollCount) * NR_ROW_STEP);
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
    const info = { symbol: code, cell, img, anchor, instance: null, winLoopTimeout: null };
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks);
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: product ("не должны одновременно крутиться все оставшиеся
// барабаны") wants a single reel revealed, then the next, and so on.
// collectAnticipationColumns only flags a column while the trigger is still
// undecided, so once one of them lands the deciding symbol, later columns
// fall out of the flagged set on their own — those just land at normal
// speed, still one at a time, since the suspense is already resolved.
async function landReels(grid, anticipationColumns = [], coinMultiplier = null, lineWins = [], countWins = []) {
  teardownCellInstances();

  // Cleared once everything has settled (finally covers the no-anticipation
  // early return and any error) so the reel stops clipping and resting symbol
  // art shows uncut again — see setReelSpinning / .reel.is-spinning.
  try {
    const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
    const anticipationSet = new Set(anticipationColumns);

    const leadTasks = [];
    for (let col = 0; col < firstAnticipationCol; col++) {
      const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
      const delay = col * REEL_LAND_STAGGER_MS;
      leadTasks.push(
        landReel(col, finalCodes, delay, false)
          .then((cellEls) => settleColumnCells(cellEls, col, finalCodes))
          .then(() => maybeShowCoinMultiplierLabels(col, coinMultiplier)),
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
      maybeShowCoinMultiplierLabels(col, coinMultiplier);
    }
  } finally {
    setReelSpinning(false);
  }
}

// --- Screen dim ------------------------------------------------------------

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

// --- Popups ----------------------------------------------------------------

const popupResourceCache = {};
let popupAmountRaf = null;

function getPopupResource(key) {
  if (!popupResourceCache[key]) {
    popupResourceCache[key] = loadSpineResource(POPUP_FOLDERS[key]);
  }
  return popupResourceCache[key];
}

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

      const resource = await getPopupResource(key);

      const instance = resource.createInstance();
      instance.anchorEl = document.getElementById('screen');
      // Portrait doubles the popup (product); glow overflow accepted.
      instance.fit = isMobileLayout() ? 2 : 1;
      stage.addOverlay(instance);
      startPopupAmountTracking(instance, amount);

      instance.play(POPUP_CLIPS.start, false);
      instance.onSettle = () => {
        instance.onSettle = null;
        instance.play(POPUP_CLIPS.idle, true);
        setTimeout(() => {
          Sound.playSfx('popupClose');
          instance.play(POPUP_CLIPS.end, false);
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

// --- Layout scaling --------------------------------------------------------

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function updateStageScale() {
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth;
  const vh = screenEl.clientHeight;
  if (!vw || !vh) return;
  const scale = Math.min(vw / d.w, vh / d.h);
  document.documentElement.style.setProperty('--stage-scale', String(scale));
}

function bgSrcFor(mode) {
  const dev = isMobileLayout() ? 'mob' : 'desk';
  const scr = mode === 'freespins' ? 'bonus' : 'base';
  return `${ASSET_ROOT}/${scr}_bg_${dev}.jpg`;
}

function updateBgForLayout() {
  const screen = document.getElementById('screen');
  document.getElementById('bgLayer').src = bgSrcFor(screen.dataset.mode || 'base');
}

// --- Dev panel -------------------------------------------------------------

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
}

// --- Boot preloader --------------------------------------------------------

// Warm everything the first minutes of play will touch, while the progress
// overlay (front/js/neon-reels/preloader.js) is still up: decoded symbol
// statics, every Spine export (symbol wins, win lines, popups), both mode
// backgrounds, SFX buffers, and one invisible WebGL frame so the shaders
// compile now instead of on the first win. Every task resolves (errors
// swallowed) and the whole thing is capped by a timeout, so a missing file
// or dead network can only shorten the warmup — never strand the overlay.
const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const img = new Image();
  img.src = src;
  // decode() actually rasterizes now; onload alone would still leave the
  // first paint of each symbol to decode lazily mid-spin.
  return img.decode ? img.decode() : new Promise((res) => {
    img.onload = res;
    img.onerror = res;
  });
}

// One transparent draw through the full pipeline (texture upload + shader
// compile). Alpha 0 keeps it invisible; the idle-skip render gate sees a
// non-empty stage, so the frame really renders.
async function warmUpWebGl() {
  const resource = await getWinLineResource();
  const instance = resource.createInstance();
  instance.anchorEl = document.querySelector('.reel__grid');
  instance.boundsOverride = WIN_LINE_BOUNDS_OVERRIDE;
  instance.skeleton.color.set(1, 1, 1, 0);
  instance.play('1', true);
  stage.addOverlay(instance);
  await wait(120); // a couple of frames
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
    tasks.push(track(preloadImage(`${ASSET_ROOT}/Export/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`)));
    tasks.push(track(getSymbolResource(code)));
  }
  for (const key of Object.keys(POPUP_FOLDERS)) tasks.push(track(getPopupResource(key)));
  tasks.push(track(getWinLineResource()));
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('freespins'))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));
  tasks.push(track(warmUpWebGl()));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

// --- Init ------------------------------------------------------------------

async function init() {
  await SlotCalibration.load(); // before createCellNode's applyStaticContentOffset
  Sound.playMusic('base');
  updateBgForLayout();
  window.addEventListener('resize', updateBgForLayout);

  // ResizeObserver on #screen itself, not just window's 'resize' — the
  // window event never fires for some real-world size changes (devtools
  // panel toggle, OS display-zoom change, a window restored to a different
  // size than it loaded at) and this game's .screen clips with
  // overflow:hidden, so a stale --stage-scale isn't just "off", it visibly
  // crops the reel/logo/buy-bonus sign (reported live: still cropped after
  // the .bg fix — that fix only addressed the background image itself, not
  // this). ResizeObserver also fires once immediately on observe(), so it
  // replaces the explicit updateStageScale() call below too.
  new ResizeObserver(updateStageScale).observe(document.getElementById('screen'));

  buildReelGrid();
  stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  setupDevPanel();

  // Full warmup behind the boot progress bar (covers what the old lone
  // getWinLineResource() warmup did and everything else the first minutes
  // touch), then the attract grid — its resources are all hot by now.
  await preloadAssets();
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));
  if (window.Preloader) window.Preloader.done();

  window.__slot = { stage, cellInfos };
}

init();
