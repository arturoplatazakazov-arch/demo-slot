// East Discovery — game-specific wiring on top of spine-engine.js, adapted
// from ../slot.js (Amy's Fruit Farm). Differences from that file are called
// out in comments; the reel-motion/win-sequencing/popup mechanics themselves
// are unchanged copies since spine-engine.js/reel-math.js are game-agnostic.

const ASSET_ROOT = 'img/east-discovery';

// All East Discovery Spine exports use straight (non-premultiplied) alpha —
// confirmed by sampling pixel data directly (RGB routinely exceeds alpha in
// semi-transparent regions, which is mathematically impossible under real
// premultiplied alpha). spine-engine.js's SpineResource.load defaults to
// premultipliedAlpha:true (Amy's Fruit Farm's export convention — a
// different pipeline) — every load in this file must go through this
// wrapper instead of calling SpineEngine.SpineResource.load directly, or
// glow/gradient/soft-edge attachments render with a hard, wrongly-colored
// edge instead of blending smoothly (the artifact this was chasing).
function loadSpineResource(folderPath) {
  return SpineEngine.SpineResource.load(stage.assetManager, folderPath, { premultipliedAlpha: false });
}

const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild',
  coin: 'coin',
  collector_tiger: 'collector_tiger',
  lp_blue: 'lp-blue',
  lp_green: 'lp-green',
  lp_pink: 'lp-pink',
  lp_red: 'lp-red',
  rare_cat: 'rare_cat',
  rare_fish: 'rare_fish',
  rare_papirus: 'rare_papirus',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// scatter/wild ship a live idle loop on the base grid; coin does NOT — it
// only animates when coin_multiplier actually triggers (coin + collector +
// a line win together — see playCoinMultiplierReveal), so it stays a plain
// static image the rest of the time even though it's a Spine-backed symbol.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// Unlike Amy's Fruit Farm (uniform idle/landing/win clip names across every
// special symbol), this set isn't uniform: wild uses small_*-prefixed clips
// (it also ships a big_* set for the reel-height variant — see
// previewBigWild, not used in the normal grid), and coin only has a single
// clip named "animation" doing double duty as both its idle loop and its
// win celebration. Falls back to the idle/landing/win default for scatter
// and any future symbol that follows that convention.
const SYMBOL_CLIPS = {
  wild: { idle: 'small_idle', landing: 'small_landing', win: 'small_win' },
  coin: { idle: 'win', landing: 'win', win: 'win' },
  // Same single-clip-does-everything shape as coin's asset.
  collector_tiger: { idle: 'win', landing: 'win', win: 'win' },
};
const DEFAULT_CLIPS = { idle: 'idle', landing: 'landing', win: 'win' };
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || DEFAULT_CLIPS[kind];
}

// wild ships two static images (static_wild_small.png / static_wild_big.png)
// instead of the usual single static.png — the grid always uses the small one.
const SYMBOL_STATIC_OVERRIDE = { wild: 'static_wild_small.png' };
function staticFileFor(code) {
  return SYMBOL_STATIC_OVERRIDE[code] || 'static.png';
}

// Attract-mode layout shown before the first real spin (also fixes the grid's
// row/col shape: 3 rows x 5 reels, matching the backend's `grid` response —
// no real east-discovery backend game exists yet, see the plan doc, so this
// placeholder is what actually renders until that's wired up).
const SYMBOL_LAYOUT = [
  ['scatter', 'rare_fish', 'lp_green', 'coin', 'rare_cat'],
  ['lp_red', 'collector_tiger', 'wild', 'coin', 'rare_papirus'],
  ['rare_fish', 'lp_blue', 'lp_pink', 'collector_tiger', 'rare_cat'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/Popup's/popup-bigwin`,
  epicWin: `${ASSET_ROOT}/Popup's/popup-epicwin`,
  megaWin: `${ASSET_ROOT}/Popup's/popup-megawin`,
  bonusSpinsWin: `${ASSET_ROOT}/Popup's/popup-bonusspinswin`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/Popup's/popup-bonusspinswintotalwin`,
  buyFreeSpins: `${ASSET_ROOT}/Popup's/popup-buybonusspins`,
};
// Amy's popups ship a `bone_input_number` bone the win-amount overlay tracks
// every frame. These skeletons don't have an equivalent bone at all (checked
// popup-bigwin's bone list) — 'plashka' (looks like the amount plaque) is a
// best guess, unconfirmed. Fix once seen live, or ask for a same-named bone
// in future popup exports.
const POPUP_AMOUNT_BONE = 'plashka';

const DIM_TRANSITION_MS = 320;
const REEL_LOOP_STEP_MS = 420;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 500;

let stage = null;
let cellInfos = [];
let reelCols = [];
let characterControllerRef = null;
let environmentControllerRef = null;
// Big-wild reveal overlays (see revealExpandedWild) — one per reel currently
// showing the reel-height grow animation. Cleared at the start of every spin
// (teardownCellInstances), same lifecycle as the small-cell instances they
// cover.
let expandedWildOverlays = [];

// --- Win-line animation (see front/img/east-discovery/Win_Lines) -----------
//
// One Spine skeleton shipping 11 named animations ("1".."11"), one per
// payline — ported from wild-western-story/slot.js once confirmed there.
// The backend defines only these 11 paylines now (the other 9 shapes were
// removed from every 5x3 game's config, product this session — no art for
// them, so they no longer pay at all). Animation name is NOT the payline
// index: "1".."5" line up with payline indices 1-5, but "6".."11" are
// indices 12-17 (see app/seed/east_discovery.py's Payline rows).
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
    // Confirmed straight (non-premultiplied) alpha, like this game's own
    // exports — NOT loadSpineResource's default, called explicitly here so
    // it stays correct even if this file's own default ever changes.
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

// wild's skeleton bundles both the small (grid-cell) and big (reel-height)
// variants sharing the same bones/attachments, distinguished by *clipping
// masks* (ClippingAttachment) rather than separate slots — small_idle's
// visible silhouette is a mask, not a distinct set of regions. Spine's own
// skeleton.getBoundsRect() doesn't account for clipping at all, so it
// reports the union of every attachment's *unclipped* geometry (measured:
// ~594x1012 Spine units) — hugely bigger than what's actually visible
// (confirmed by inspecting slot draw order: every region/mesh has alpha:1
// during small_idle, nothing's hidden by color/scale, only by the clip).
// resource.bounds (from the skeleton JSON's own top-level metadata) turns
// out to already suit the *big* variant's own aspect fine (confirmed
// visually) — this only needs fixing for the small grid-cell usage, via the
// "bone" slot's own clip polygon (the small silhouette's actual mask),
// computed dynamically (not hardcoded) since this asset has already been
// re-uploaded with different data multiple times this session.
function computeWildSmallBoundsOverride(resource) {
  const probe = new spine.Skeleton(resource.skeletonData);
  probe.setToSetupPose();
  const state = new spine.AnimationState(resource.animationStateData);
  state.setAnimation(0, 'small_idle', true);
  state.update(0);
  state.apply(probe);
  probe.updateWorldTransform();

  const slot = probe.findSlot('bone');
  const clip = slot && slot.getAttachment();
  if (!clip || clip.constructor.name !== 'ClippingAttachment') return null;

  const len = clip.worldVerticesLength;
  const verts = new Float32Array(len);
  clip.computeWorldVertices(slot, 0, len, verts, 0, 2);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (let i = 0; i < verts.length; i += 2) {
    minX = Math.min(minX, verts[i]);
    maxX = Math.max(maxX, verts[i]);
    minY = Math.min(minY, verts[i + 1]);
    maxY = Math.max(maxY, verts[i + 1]);
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function getSymbolResource(code) {
  if (!symbolResourceCache[code]) {
    const folder = SYMBOL_FOLDERS[code];
    symbolResourceCache[code] = loadSpineResource(`${ASSET_ROOT}/Export/${folder}`).then((resource) => {
      if (code === 'wild') {
        resource.wildSmallBoundsOverride = computeWildSmallBoundsOverride(resource);
      }
      return resource;
    });
  }
  return symbolResourceCache[code];
}

// Own table, NOT ReelMath.staticContentOffset — that one carries Amy's
// Fruit Farm's own measured values under the *same* code names (its table
// also has "scatter"/"wild" keys), which would silently apply Amy's pixel
// corrections to East Discovery's completely different art if reused here.
// Same measurement method as Amy's (scan each static.png's non-transparent
// (alpha>10) pixel extent, offset = canvas_center - content_bbox_center).
const EAST_DISCOVERY_STATIC_CONTENT_OFFSET = {
  scatter: { dx: -0.5, dy: 4.5 },
  wild: { dx: 2.5, dy: 3.5 },
  coin: { dx: -0.5, dy: 0.5 },
  collector_tiger: { dx: -0.5, dy: 2.0 },
  lp_blue: { dx: -0.5, dy: 0.5 },
  lp_green: { dx: -0.5, dy: 2.0 },
  lp_pink: { dx: -0.5, dy: 2.5 },
  lp_red: { dx: 0, dy: 2.5 },
  rare_cat: { dx: 0, dy: 0 },
  rare_fish: { dx: 0, dy: 0 },
  rare_papirus: { dx: 0, dy: 0 },
};

function applyStaticContentOffset(img, code) {
  // A live override from Anim Lab's "Калибровать" button (front/js/anim-lab.js,
  // shared via front/js/slot-calibration.js) wins over the baked-in table —
  // lets a calibration be checked in this actual game before it's copied
  // into EAST_DISCOVERY_STATIC_CONTENT_OFFSET above to make it permanent.
  const override = window.SlotCalibration && window.SlotCalibration.get('east-discovery', code);
  const { dx, dy } = override || EAST_DISCOVERY_STATIC_CONTENT_OFFSET[code] || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

// 'blank' isn't a real game symbol — Hold & Win's grid is empty apart from
// whatever coins have landed (see runHoldAndWinSequence), and there's no
// SYMBOL_FOLDERS entry for it, so it's handled as "no image at all" rather
// than routed through the normal symbol asset lookup.
function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  if (code !== 'blank') {
    img.src = `${ASSET_ROOT}/Export/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`;
    img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
    applyStaticContentOffset(img, code);
  } else {
    img.style.visibility = 'hidden';
  }
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
  for (const overlay of expandedWildOverlays) {
    if (overlay.winLoopTimeout) clearTimeout(overlay.winLoopTimeout);
    stage.removeOverlay(overlay);
  }
  expandedWildOverlays = [];
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
  if (code === 'blank') {
    info.img.removeAttribute('src');
    info.img.style.visibility = 'hidden';
    return;
  }
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
      window.SlotCalibration?.applyAnchorOffset(info.anchor, 'east-discovery', code);
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

// The coin skeleton carries a "multy" bone (see animation.json) positioned
// where its value text ("10X", "1000X", ...) belongs — same bone-tracking
// idea as POPUP_AMOUNT_BONE, but per-cell and multiple at once (several
// coins can be showing a value simultaneously), so this tracks a pool of
// DOM elements instead of the popup's single shared one. Every coin shows
// its drawn value as soon as it lands (product: it's not gated behind a
// win) — see maybeShowCoinMultiplierLabels, called per-column from
// landReels. Whether the multiplier actually *paid out* this spin
// (coin_multiplier.applied) only gates the celebratory win animation on
// top of the always-showing label — see playCoinMultiplierReveal.
const COIN_MULTIPLIER_BONE = 'multy';
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

// Plays the coin's single clip exactly once as it lands, then pulls the spine
// off stage so the cell's static PNG (info.img) is the resting art again — the
// value label is what persists, not a repeating animation (product: one landing
// play, no perpetual idle loop). NB: hiding the coin has to be done by removing
// it from the stage, NOT by setting skeleton.color.a = 0 — stage.addBase runs
// _applyBaseDim, which does skeleton.color.set(c, c, c, 1) and would overwrite
// an alpha-0 back to full (and any later setBaseDim would revive it too). That
// overwrite is exactly what turned this into a visible, forever-looping coin.
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

// coin's own win animation only plays when coin_multiplier actually applied
// (coin + collector_tiger + a line win together, this spin) — the value
// label itself is already showing regardless (see above). Plays once (not
// looped like other winning symbols) — the multiplier value is what's meant
// to keep showing, not a repeating animation (product feedback).
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

// The collector_tiger(s) on the grid also celebrate when coin_multiplier
// actually applies — same trigger as the coin's own reveal above, just a
// different symbol. Unlike coin, this one keeps the standard looping
// winning-symbol treatment (previewSymbolWin) since nothing asked for it to
// stop repeating.
function playCollectorTigerWinIfApplied(coinMultiplier) {
  if (!coinMultiplier || !coinMultiplier.applied) return;
  for (const info of cellInfos) {
    if (info && info.symbol === 'collector_tiger') previewSymbolWin(info);
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

// --- Reel motion (unchanged from Amy's Fruit Farm — see that file for the
// full writeup of how the masked-column scroll technique works) -----------

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
    cell.addEventListener('click', () => previewSymbolWin(info));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks);
}

// --- Big-wild reveal (expand/walk) -----------------------------------------
//
// A reel whose wild_events entry this spin says "expanded" (freshly landed
// and rolled to expand) or "walked" (a previously-expanded wild moved onto
// this reel) already shows 3 stacked small wild cells once settleColumnCells
// resolves (the grid the server sent already has `wild` in every row of that
// reel). On top of that, per product ("анимация его увеличения... элементы
// которые окажутся под ним плавно за 0.5 секунды уходят в прозрачность"),
// grow one reel-height big wild over it and fade the 3 small cells out.

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

async function revealExpandedWild(col) {
  // anchorEl (stripEl) supplies the horizontal center — it's this specific
  // reel's own column. heightAnchorEl (.reel__grid) supplies the vertical
  // extent instead of stripEl's/colEl's own rect: both of those are
  // deliberately taller than the frame's actual visible hole (colEl:
  // calc(100% + 132px)/-112px margin, stripEl: masked off at 727-742px —
  // both are the reel-loop scroll/mask trick, not the true window), while
  // .reel__grid's inset is measured directly off frame.png's alpha channel,
  // i.e. it IS the real hole.
  const { stripEl } = reelCols[col];
  const gridEl = document.querySelector('.reel__grid');
  const resource = await loadSpineResource(`${ASSET_ROOT}/Export/wild`);
  const overlay = resource.createInstance();
  overlay.anchorEl = stripEl;
  overlay.heightAnchorEl = gridEl;
  overlay.fit = 0.64335735; // 15% smaller than a full frame-hole fill, per product feedback
  overlay.verticalOffsetRatio = 0.16;
  overlay.fitMode = 'height';
  overlay.reelCol = col; // looked up later by playBigWildWinIfWinning
  overlay.winLoopTimeout = null;
  overlay.winLoopActive = false;
  stage.addOverlay(overlay);
  expandedWildOverlays.push(overlay);

  const fadeInfos = [0, 1, 2].map((row) => cellInfos[row * GRID_COLS + col]).filter(Boolean);
  const fadeDone = fadeCellsToTransparent(fadeInfos, 500);

  Sound.playSfx('wildGrow');
  await new Promise((resolve) => {
    overlay.play('big_landing', false);
    overlay.onSettle = () => {
      overlay.onSettle = null;
      overlay.play('big_idle', true);
      resolve();
    };
  });
  await fadeDone;
  return overlay;
}

function maybeRevealExpandedWild(col, wildEvents) {
  const grew = wildEvents.some((e) => e.reel === col && (e.event === 'expanded' || e.event === 'walked'));
  return grew ? revealExpandedWild(col) : Promise.resolve(null);
}

const BIG_WILD_WIN_DELAY_MS = 500;

function columnHasWin(col, lineWins, countWins) {
  for (const w of [...(lineWins || []), ...(countWins || [])]) {
    if (w.positions.some((pos) => pos.col === col)) return true;
  }
  return false;
}

// If a winning line/count actually runs through the reel the big wild just
// grew to fill, its own win celebration (big_win, looped with a pause the
// same way every other winning symbol's does — see previewSymbolWin) plays
// half a second after the grow animation settles, not simultaneously with
// it (product: grow first, then win) — see maybeCelebrateBigWildWin, called
// right after the reveal finishes for this column.
function playBigWildWinLoop(overlay) {
  if (overlay.winLoopActive) return;
  overlay.winLoopActive = true;
  Sound.playSfx('wildWin');
  const playOnce = () => {
    overlay.play('big_win', false);
    overlay.onSettle = () => {
      overlay.onSettle = null;
      overlay.play('big_idle', true);
      overlay.winLoopTimeout = setTimeout(() => {
        overlay.winLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    };
  };
  playOnce();
}

async function maybeCelebrateBigWildWin(col, overlay, lineWins, countWins) {
  if (!overlay || !columnHasWin(col, lineWins, countWins)) return;
  await wait(BIG_WILD_WIN_DELAY_MS);
  playBigWildWinLoop(overlay);
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: product ("не должны одновременно крутиться все оставшиеся
// барабаны") wants a single reel revealed, then the next, and so on.
// collectAnticipationColumns only flags a column while the trigger is still
// undecided, so once one of them lands the deciding symbol, later columns
// fall out of the flagged set on their own — those just land at normal
// speed, still one at a time, since the suspense is already resolved.
async function landReels(
  grid,
  anticipationColumns = [],
  wildEvents = [],
  coinMultiplier = null,
  lineWins = [],
  countWins = [],
) {
  teardownCellInstances();

  const firstAnticipationCol = anticipationColumns.length > 0 ? Math.min(...anticipationColumns) : GRID_COLS;
  const anticipationSet = new Set(anticipationColumns);

  const leadTasks = [];
  for (let col = 0; col < firstAnticipationCol; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const delay = col * REEL_LAND_STAGGER_MS;
    leadTasks.push(
      landReel(col, finalCodes, delay, false)
        .then((cellEls) => settleColumnCells(cellEls, col, finalCodes))
        .then(async () => {
          const overlay = await maybeRevealExpandedWild(col, wildEvents);
          maybeShowCoinMultiplierLabels(col, coinMultiplier);
          await maybeCelebrateBigWildWin(col, overlay, lineWins, countWins);
        }),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  Sound.playSfx('anticipation');
  if (characterControllerRef) characterControllerRef.playEmotion('near_to_win');

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
    const overlay = await maybeRevealExpandedWild(col, wildEvents);
    maybeShowCoinMultiplierLabels(col, coinMultiplier);
    await maybeCelebrateBigWildWin(col, overlay, lineWins, countWins);
  }
}

// --- Hold & Win playback ----------------------------------------------------
//
// The whole round resolves in one backend call (hold_and_win.py) — the
// respins/pacing here are purely client-side theater replaying that
// already-known outcome respin by respin, so the player experiences it as
// "real time" (product: "если сессия считается сразу на беке... пользователь
// этого знать не должен"). Reuses landReel's existing scroll-and-land
// animation with a coin/blank-only filler set instead of the full symbol
// set, since Hold & Win's grid is empty apart from locked coins.

const HOLD_AND_WIN_RESPIN_PAUSE_MS = 1000;
const HOLD_AND_WIN_COIN_FILLER_CHANCE = 0.15; // flavor only — matches the seed's respin_land_weights ratio

function randomHoldAndWinFillerCode() {
  return Math.random() < HOLD_AND_WIN_COIN_FILLER_CHANCE ? 'coin' : 'blank';
}

function buildHoldAndWinGrid(locked, newlyLanded = []) {
  const newlyByKey = new Set(newlyLanded.map((c) => `${c.row}-${c.col}`));
  const grid = [[], [], []];
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const key = `${row}-${col}`;
      grid[row][col] = locked.has(key) || newlyByKey.has(key) ? 'coin' : 'blank';
    }
  }
  return grid;
}

async function landHoldAndWinRespin(grid) {
  const tasks = [];
  for (let col = 0; col < GRID_COLS; col++) {
    const finalCodes = [grid[0][col], grid[1][col], grid[2][col]];
    const delay = col * REEL_LAND_STAGGER_MS;
    tasks.push(
      landReel(col, finalCodes, delay, false, randomHoldAndWinFillerCode).then((cellEls) =>
        settleColumnCells(cellEls, col, finalCodes),
      ),
    );
  }
  await Promise.all(tasks);
}

async function enterHoldAndWinWaitingState() {
  await setFreeSpinsMode(true, 0, { intro: false }); // Hold & Win shows no entry popup
  await applyGrid(buildHoldAndWinGrid(new Set()));
}

async function runHoldAndWinSequence(result) {
  const locked = new Map(); // "row-col" -> value

  for (const respin of result.respins) {
    await landHoldAndWinRespin(buildHoldAndWinGrid(new Set(locked.keys()), respin.landed));

    for (const c of respin.landed) {
      locked.set(`${c.row}-${c.col}`, c.value);
      const info = cellInfos[c.row * GRID_COLS + c.col];
      if (info && info.instance) {
        // value 0 = a plain coin with no multiplier (product, this
        // session) — still sticks and still animates landing, just no "×N"
        // label over it.
        if (c.value > 0) showCoinMultiplierLabel(info, c.value);
        info.instance.skeleton.color.a = 1;
        playWinAnimationOnce(info);
      }
    }
    if (respin.landed.length) Sound.playSfx('coinLand');

    await wait(HOLD_AND_WIN_RESPIN_PAUSE_MS);
  }

  await wait(300);
  await playPopup('bonusSpinsTotalWin', result.total_win);
  await setFreeSpinsMode(false);
}

// --- Screen dim (unchanged mechanics, see Amy's Fruit Farm's slot.js) ------

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

// Swaps the on-screen mode (background + character + environment) for `next`.
// Shared by the plain leave-bonus dim and the enter-bonus intro so the two
// never drift apart.
function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
  if (characterControllerRef) characterControllerRef.setMode(next);
  if (environmentControllerRef) environmentControllerRef.setMode(next);
}

// How long the "you won the bonus" popup holds on the blackout before the
// bonus screen is revealed behind it (product: ~3s of popup, then reveal).
const BONUS_INTRO_HOLD_MS = 3000;

// The base -> free-spins moment: black the screen out, play the bonusSpinsWin
// popup over the black for BONUS_INTRO_HOLD_MS, swap the bonus screen in behind
// the still-opaque black, then lift the blackout to reveal it.
async function enterBonusTransition(amount = 0) {
  pushScreenDim(true); // opaque blackout in
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true); // reveal the bonus screen
}

// `intro` is true for the free-spins (scatter) trigger — it gets the full intro
// moment (blackout + bonusSpinsWin popup + reveal). Hold & Win reuses freespins
// mode as its "bonus level" but passes intro:false, since it deliberately shows
// no entry popup (its own Bonus Spins Total Win popup covers the end — see
// app.js's hold_and_win branch).
function setFreeSpinsMode(active, amount = 0, { intro = true } = {}) {
  const screen = document.getElementById('screen');
  const next = active ? 'freespins' : 'base';
  if (screen.dataset.mode === next) return Promise.resolve();

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

// --- Character (Hero_base / Hero_Bonus) -------------------------------
//
// New vs. Amy's Fruit Farm: 3 clips (idle/near_to_win/win) instead of just
// idle, exposed as playEmotion() on top of the existing setMode().

async function setupCharacter() {
  const characterImg = document.getElementById('character');
  const [baseResource, bonusResource] = await Promise.all([
    loadSpineResource(`${ASSET_ROOT}/Export/Hero_base`),
    loadSpineResource(`${ASSET_ROOT}/Export/Hero_Bonus`),
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
    // 'idle' loops forever; 'near_to_win'/'win' play once, then fall back to idle.
    playEmotion(name) {
      const inst = instances[active];
      if (name === 'idle') {
        inst.onSettle = null;
        inst.play('idle', true);
        return;
      }
      inst.play(name, false);
      inst.onSettle = () => {
        inst.onSettle = null;
        inst.play('idle', true);
      };
    },
  };
}

// --- Ambient background (BG_Base_desk/mob, BG_Bonus_desk/mob) -------------
//
// New capability, no Amy's Fruit Farm equivalent: looping Spine decoration
// drawn behind the character and symbols but above the static bg <img>.
//
// Each BG_* skeleton bundles multiple decorative elements as separate slots
// on one shared texture (confirmed by inspecting animation.json): base's
// two slots are bamboo (left) and a blossom tree (right); bonus's slots are
// named `light*_l`/`tree_l` (left lantern string) and `light*_r`/`tree_r`
// (right). Product wants each piece pinned to its own screen edge/corner
// independently (bamboo behind the hero on the left, tree top-right, a
// lantern cluster top-left AND top-right in bonus) rather than the whole
// skeleton scaled as one full-screen "contain" fit — which is also what was
// making bamboo grow across the reel on mobile (a single fit computed from
// the *combined* bounds of every element together doesn't leave any element
// pinned to a stable edge once the aspect ratio changes).
//
// So this creates one SpineInstance per decorative *piece*, each from the
// same shared resource/texture, with every slot except that piece's own
// hidden (`slot.setAttachment(null)`) and anchored to its own small,
// edge-pinned DOM element (see east-discovery.html/.css) instead of one
// full-screen anchor. `instance.boundsOverride` (spine-engine.js) makes the
// fit-to-anchor math use just that piece's own bounds
// (`skeleton.getBoundsRect()`, computed once after hiding the other slots)
// instead of the shared resource's combined bounds.

const ENV_CONFIG = {
  base: {
    desktop: {
      folder: 'BG_Base_desk',
      pieces: { bamboo: ['1image'], tree: ['1image(2)'] },
    },
    mobile: {
      folder: 'BG_Base_mob',
      pieces: { bamboo: ['1image'], tree: ['1image2'] },
    },
  },
  bonus: {
    desktop: {
      folder: 'BG_Bonus_desk',
      pieces: {
        lanternLeft: ['light1_l', 'light2_l', 'light3_l', 'tree_l'],
        lanternRight: ['light1_r', 'light2_r', 'tree_r'],
      },
    },
    mobile: {
      folder: 'BG_Bonus_mob',
      pieces: {
        lanternLeft: ['light1_l', 'light2_l', 'light3_l', 'tree_l'],
        lanternRight: ['light1_r', 'light2_r', 'tree_r'],
      },
    },
  },
};

const ENV_ANCHOR_IDS = {
  bamboo: 'envBambooAnchor',
  tree: 'envTreeAnchor',
  lanternLeft: 'envLanternLeftAnchor',
  lanternRight: 'envLanternRightAnchor',
};

async function setupEnvironment() {
  const resourceCache = {}; // folder -> Promise<SpineResource>, shared across mode/layout combos that reuse it
  const pieceInstances = {}; // pieceInstances[mode][layout] = { pieceName: SpineInstance }

  for (const [mode, byLayout] of Object.entries(ENV_CONFIG)) {
    pieceInstances[mode] = {};
    for (const [layout, { folder, pieces }] of Object.entries(byLayout)) {
      if (!resourceCache[folder]) {
        resourceCache[folder] = loadSpineResource(`${ASSET_ROOT}/Export/${folder}`);
      }
      const resource = await resourceCache[folder];
      const allSlotNames = resource.skeletonData.slots.map((s) => s.name);

      pieceInstances[mode][layout] = {};
      for (const [pieceName, keepSlots] of Object.entries(pieces)) {
        const instance = resource.createInstance();
        for (const slotName of allSlotNames) {
          if (!keepSlots.includes(slotName)) {
            const slot = instance.skeleton.findSlot(slotName);
            if (slot) slot.setAttachment(null);
          }
        }
        instance.skeleton.updateWorldTransform();
        instance.boundsOverride = instance.skeleton.getBoundsRect();
        instance.anchorEl = document.getElementById(ENV_ANCHOR_IDS[pieceName]);
        instance.fit = 1;
        instance.play('idle', true);
        pieceInstances[mode][layout][pieceName] = instance;
      }
    }
  }

  let activeKey = null; // "mode:layout"
  function keyFor(mode) {
    return `${mode}:${isMobileLayout() ? 'mobile' : 'desktop'}`;
  }
  function activate(mode) {
    const key = keyFor(mode);
    if (key === activeKey) return;
    if (activeKey) {
      const [prevMode, prevLayout] = activeKey.split(':');
      for (const inst of Object.values(pieceInstances[prevMode][prevLayout])) stage.removeBase(inst);
    }
    const [nextMode, nextLayout] = key.split(':');
    // addBaseBehindAll (not addBase): keeps every ambient piece behind the
    // character even after repeated mode-switch churn — plain addBase's
    // push-to-end would otherwise put it back in front after the first toggle.
    for (const inst of Object.values(pieceInstances[nextMode][nextLayout])) stage.addBaseBehindAll(inst);
    activeKey = key;
  }
  activate('base');

  return {
    // Called both on base<->bonus mode switches and on layout (desktop<->
    // mobile) changes — either can change which piece set is active.
    setMode(mode) {
      activate(mode === 'freespins' ? 'bonus' : 'base');
    },
  };
}

// --- Popups (unchanged mechanics from Amy's Fruit Farm) --------------------

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
        popupResourceCache[key] = loadSpineResource(folder);
      }
      const resource = await popupResourceCache[key];

      const instance = resource.createInstance();
      instance.anchorEl = document.getElementById('screen');
      instance.fit = 1;
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

// --- Big wild preview (dev-only) -------------------------------------------
//
// The reel-height "big" dragon wild (static_wild_big.png, big_idle/
// big_landing/big_win) shows up on reel 3 in every reference screenshot, but
// no real game rule for it is confirmed yet (see the plan doc) — this is a
// visual-only preview, not tied to actual spin results. Overlays it on reel
// index 2 (the 3rd reel) for a few seconds, then plays its win clip once.

let bigWildPreviewInstance = null;

async function previewBigWild() {
  if (bigWildPreviewInstance || reelCols.length < 3) return;
  const resource = await loadSpineResource(`${ASSET_ROOT}/Export/wild`);
  const instance = resource.createInstance();
  instance.anchorEl = reelCols[2].stripEl;
  instance.heightAnchorEl = document.querySelector('.reel__grid');
  instance.fit = 0.64335735; // matches revealExpandedWild's fit — same asset, same reel-fill treatment
  instance.verticalOffsetRatio = 0.16;
  instance.fitMode = 'height';
  bigWildPreviewInstance = instance;
  stage.addOverlay(instance);
  instance.play('big_idle', true);

  await wait(1500);
  await new Promise((resolve) => {
    instance.play('big_win', false);
    instance.onSettle = () => {
      instance.onSettle = null;
      resolve();
    };
  });
  await wait(400);

  stage.removeOverlay(instance);
  bigWildPreviewInstance = null;
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

  document.querySelectorAll('[data-emotion]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (characterControllerRef) characterControllerRef.playEmotion(btn.dataset.emotion);
    });
  });

  const bigWildBtn = document.getElementById('devBigWild');
  if (bigWildBtn) bigWildBtn.addEventListener('click', previewBigWild);

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

// Design is authored at a fixed 1932x940 canvas (matches bg-base-desk.png)
// with 1612px as the narrowest width it still looks right at — between the
// two, the whole composition scales down proportionally with viewport
// width, same as Amy's Fruit Farm's default behavior (see ReelMath.
// viewportScale in the shared reel-math.js). Below 1612px, instead of
// continuing to shrink (Amy's default floors at a flat 0.6 scale), freeze
// at the scale 1612px itself maps to and let the excess get cropped at the
// viewport edge (see `overflow-x: hidden` on body in east-discovery.css) —
// passed as explicit designWidth/minScale args so this doesn't touch the
// shared file's defaults, which Amy's Fruit Farm also relies on.
const DESKTOP_DESIGN_MAX_WIDTH = 1932;
const DESKTOP_DESIGN_MIN_WIDTH = 1612;

// Experimental "fit everything, no scroll" layout — see east-discovery.css
// body.layout-fit and ReelMath.fitScale. Reserve budget mirrors Amy's Fruit
// Farm's (side ambient decoration + a little top/bottom breathing room; no
// separate .ui-bar budget since that layout turns it into an overlay).
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
    return mode === 'base' ? `${ASSET_ROOT}/img/bg-base-mob.jpg` : `${ASSET_ROOT}/img/bg-bonus-mob.jpg`;
  }
  return mode === 'base' ? `${ASSET_ROOT}/img/bg-base-desk.png` : `${ASSET_ROOT}/img/bg-bonus-desk.jpg`;
}

function updateBgForLayout() {
  const screen = document.getElementById('screen');
  document.getElementById('bgLayer').src = bgSrcFor(screen.dataset.mode || 'base');
  // Layout changes (desktop<->mobile) can also change which of the 4 ambient
  // background instances should be active, independent of any mode switch.
  if (environmentControllerRef) environmentControllerRef.setMode(screen.dataset.mode || 'base');
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
    tasks.push(track(preloadImage(`${ASSET_ROOT}/Export/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`)));
    tasks.push(track(getSymbolResource(code)));
  }
  for (const key of Object.keys(POPUP_FOLDERS)) {
    if (!popupResourceCache[key]) popupResourceCache[key] = loadSpineResource(POPUP_FOLDERS[key]);
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

  await preloadAssets();
  // Environment added to the stage before the character, so it draws behind it.
  environmentControllerRef = await setupEnvironment();
  characterControllerRef = await setupCharacter();
  setupDevPanel();

  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));

  if (window.Preloader) window.Preloader.done();

  window.__slot = { stage, cellInfos };
}

init();
