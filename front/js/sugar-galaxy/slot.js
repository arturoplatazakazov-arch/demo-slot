// Sugar Galaxy — game-specific wiring on top of spine-engine.js. Structurally
// mirrors east-discovery/slot.js's Spine/popup/screen-dim plumbing, but the
// core play loop is completely different: this is an avalanche/cascade game
// (app/engine/avalanche.py), not a spinning reel — there's no reel-strip
// scroll at all. A spin's whole result (initial grid + every cascade step,
// already fully resolved server-side) lands in one response; this file's
// job is just to animate the walk from one step's grid to the next:
// highlight the step's wins + consumed multiplier tokens, fade them out,
// drop survivors down / refill from the top with the step's grid_after.

const ASSET_ROOT = 'img/sugar-galaxy';

// Every Sugar Galaxy Spine export ships STRAIGHT (non-premultiplied) alpha —
// confirmed by sampling each animation.png directly: RGB routinely exceeds
// alpha in semi-transparent pixels (glows, soft edges), which only happens
// when alpha isn't premultiplied. Same case as East Discovery. Drawing them
// with the default premultipliedAlpha:true blows out those semi-transparent
// glow/blik pixels (the "побитые свечения"), so force it false here.
//
// The `assetManager` arg matters because textures are WebGL-context-specific:
// symbols/popups render on the main `stage`, the animated backgrounds on the
// separate `bgStage` (a different <canvas>/GL context). Each resource must be
// loaded through the asset manager of the stage that will draw it, or its
// texture simply never appears (which is why the animated bg was invisible
// and only the static PNG fallback showed).
function loadSpineResource(folderPath, assetManager) {
  return SpineEngine.SpineResource.load(assetManager || stage.assetManager, folderPath, {
    premultipliedAlpha: false,
  });
}

// code -> uploaded Spine export folder (front/img/sugar-galaxy/Export/). Codes
// match the seed (app/seed/sugar_galaxy.py) and the folder names 1:1. "bomb"
// is the resting bomb tile (Export/bomb, has its own static.png + an
// "animation" clip); the actual explosion VFX are the separate, static-less
// Export/boom_standart (ordinary win clears) and Export/boom_bomb (a bomb's
// own detonation) clips, loaded directly below (getBoomStdResource /
// getBoomBombResource), never as a resting symbol's art.
const SYMBOL_FOLDERS = {
  scatter: 'scatter',
  wild: 'wild',
  hp_red: 'hp_red',
  hp_yellow: 'hp_yellow',
  hp_green: 'hp_green',
  hp_blue: 'hp_blue',
  lp_blue: 'lp_blue',
  lp_green: 'lp_green',
  lp_red: 'lp_red',
  lp_yellow: 'lp_yellow',
  x2: 'x2',
  x3: 'x3',
  x5: 'x5',
  x7: 'x7',
  bomb: 'bomb',
};
const SYMBOL_CODES = Object.keys(SYMBOL_FOLDERS);

// Product, this session: "верни все обратно, выровняй статические картинки
// по центру по высоте и ширине относительно своих ячеек и так же анимации"
// — no baked-in per-symbol table (unlike Amy's Fruit Farm/East Discovery's
// STATIC_CONTENT_OFFSET). The static <img> is centered on the cell purely
// by .reel__cell's own CSS (flex centering, both axes) by default, and the
// Spine anchor the same way via .reel__cell-anchor's CSS (both axes) — see
// playSymbolClipOnce for the animation side. applyStaticContentOffset below
// only ever applies a *live* correction written by Anim Lab's "Калибровать"
// button (front/js/anim-lab.js, via front/js/slot-calibration.js) — nothing
// is offset by default, so the centered-by-default behavior product asked
// for is unchanged until someone explicitly calibrates a symbol.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('sugar-galaxy', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

// Every symbol export ships exactly one clip, "win", doing every job at once
// (idle/landing/win) — confirmed by inspecting each animation.json's
// `animations` key. Scatter is the sole exception: it also ships a
// "landing" clip, played once right when the initial grid reveals a scatter
// (see revealScatterLanding below), separate from its "win" celebration
// when free spins actually trigger.
const SYMBOL_CLIPS = {
  scatter: { landing: 'landing', win: 'win' },
  // Bomb's resting art (Export/bomb) ships one clip named "animation" (not
  // "win") — its own detonation animation, played on the bomb cell before
  // the boom_bomb explosion (see celebrateStep's bombPromise).
  bomb: { win: 'animation' },
};
function clipName(code, kind) {
  return (SYMBOL_CLIPS[code] && SYMBOL_CLIPS[code][kind]) || 'win';
}

const POPUP_FOLDERS = {
  bigWin: `${ASSET_ROOT}/Popup/popup_big_win`,
  epicWin: `${ASSET_ROOT}/Popup/popup_epic_win`,
  megaWin: `${ASSET_ROOT}/Popup/popup_mega_win`,
  bonusSpinsWin: `${ASSET_ROOT}/Popup/popup_bonus_spins_win`,
  bonusSpinsTotalWin: `${ASSET_ROOT}/Popup/popup_bonus_spins_total_win`,
  buyFreeSpins: `${ASSET_ROOT}/Popup/popup_buy_bonus_spins`,
};
// The win-amount sits in the popup's counter plaque (the "popup_back_counter"
// / "popup_*_counter" slot), positioned by the "counter" bone — NOT the "text"
// bone, which sits on the big title lettering (BIG/EPIC/MEGA WIN). Every popup
// export carries a "counter" bone (checked each animation.json's bone list).
const POPUP_AMOUNT_BONE = 'counter';

// Matches the backend's grid shape (app/api/v1/schemas.py's SpinResponse.grid) —
// 6 reels x 5 rows, row-major: grid[row][col].
const GRID_COLS = 6;
const GRID_ROWS = 5;

// Grid geometry comes from CSS (--cell-w/--cell-h/--cell-gap-x/-y) so the
// desktop (153x124, gap 10) and mobile-portrait (116x116, gap 18x5) layouts —
// both from the slot-builder manifest and defined in css/sugar-galaxy.css —
// stay the single source of truth. Cached here, refreshed by readCellDims()
// on init/resize and at the start of every grid rebuild. Horizontal steps use
// the width, vertical steps the height (cells are rectangular on desktop).
let cellW = 153, cellH = 124, gapX = 10, gapY = 10;
let colStep = cellW + gapX, rowStep = cellH + gapY;
function readCellDims() {
  const cs = getComputedStyle(document.documentElement);
  const num = (name, fallback) => parseFloat(cs.getPropertyValue(name)) || fallback;
  cellW = num('--cell-w', 153);
  cellH = num('--cell-h', 124);
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
  ['hp_red', 'lp_blue', 'x2', 'lp_green', 'hp_green', 'lp_yellow'],
  ['hp_yellow', 'lp_red', 'wild', 'x3', 'lp_blue', 'hp_red'],
  ['scatter', 'lp_green', 'hp_green', 'lp_yellow', 'x5', 'lp_red'],
  ['lp_blue', 'x7', 'hp_yellow', 'lp_green', 'wild', 'hp_blue'],
  ['lp_yellow', 'hp_red', 'lp_red', 'x2', 'lp_blue', 'lp_green'],
];

const DIM_TRANSITION_MS = 320;
// Pause between the grid landing/highlighting a combination and its win
// clips starting — 0 (product, this session: "давай сделаем чтоб сразу
// играла вин анимация", was 500).
const WIN_LANDING_DELAY_MS = 0;
// "после взрыва через 0.2 секунды на пустые места досыпаются элементы"
// (product, this session) — the pause between a cell being marked removed
// and the drop/refill starting, shared by every removal source (tier wins,
// tokens, bomb blasts alike).
const CASCADE_FADE_MS = 200;
const CASCADE_DROP_MS = 100; // product, this session: "поменяй на 100мс" (was 520)
const CASCADE_STEP_GAP_MS = 220;
const WIN_LOOP_PAUSE_MS = 500;
// Bomb symbol ("boom"): "после его приземления на поле и паузы 0.5 секунд
// у него отыгрывает анимация" (product, this session) — a bomb sits still
// for this long after landing before its own (explosion) clip plays.
const BOMB_PRE_EXPLODE_MS = 500;
// Bomb explosion SFX (bomb-explode.mp3) fires this long after the bomb's own
// detonation animation *starts* — product: 0.9s in, mid-animation, not at the
// wind-up or the tail blast.
const BOMB_SFX_AFTER_START_MS = 900;
// Spin start (product, this session: "элементы построчно начиная с нижней
// падают вниз в прозрачность, и как только последняя строка стала
// прозрачной элементы начинают построчно падать сверху на слот"), later
// refined (product, this session: "каждая следующая строка должна начинать
// падать... не после того как упадет вся предыдущая строка, а на 0.1
// секунду позже элемента под собой") — a row does NOT wait for the row
// below it (outgoing wave) / above it (incoming wave, since it fills
// bottom-up) to fully land; it just starts ROW_STAGGER_MS after that
// neighboring row itself *started*, a pure diagonal-wave offset, not a
// completion gate. Same idea across columns within a row (product, this
// session: "задержка между барабанами 0.1 секунду") — column 0 starts
// immediately, column 1 REEL_STAGGER_MS later, etc. Every cell's own delay
// is therefore rowOrderIndex*ROW_STAGGER_MS + col*REEL_STAGGER_MS (see
// spinStartTransition), all scheduled via setTimeout up front, then the
// whole wave is awaited once via SPIN_START_WAVE_MS (the last cell's delay
// plus its own CASCADE_DROP_MS to land).
const ROW_STAGGER_MS = 50; // product, this session: "не 0.1 сек задержки а 0.05" (was 100)
const REEL_STAGGER_MS = 50;
const SPIN_START_WAVE_MS = (GRID_ROWS - 1) * ROW_STAGGER_MS + (GRID_COLS - 1) * REEL_STAGGER_MS + CASCADE_DROP_MS;
const SPIN_START_GAP_MS = 300;
// Spin-start SFX (product), two separate cues:
//  - SPIN_Start: a single cue fired SPIN_START_CUE_DELAY_MS (0.1s) after the
//    spin *press* (from app.js runSpin), independent of network latency.
//  - Element_drop patter: one beat per reel column (GRID_COLS = 6), 0.1s
//    apart, fired from spinStartTransition when the fresh grid lands —
//    imitating the elements hitting the reel.
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
// Consumed multiplier token flying from its cell to the persistent
// multiplier badge (reference: Sweet Crumbles, DreamPlay) — must match
// css/sugar-galaxy.css's .token-flight animation duration (product, this
// session: "1 секунда", was 550).
const TOKEN_FLIGHT_MS = 1000;

let stage = null;
let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Bounds a Spine clip's promise (resolves on the engine's `complete` event —
// see spine-engine.js's onSettle) so one asset that never settles — missing
// export, a WebGL context that never gets a paint tick, or any other engine
// hiccup — can't hang the whole cascade forever. The round always keeps
// moving after CLIP_TIMEOUT_MS even in the worst case.
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
    symbolResourceCache[code] = loadSpineResource(`${ASSET_ROOT}/Export/${folder}`);
  }
  return symbolResourceCache[code];
}

// Two explosion VFX clips ship for this theme, neither a resting symbol (both
// are pure one-shot clips with no static.png, so unreachable via
// getSymbolResource): Export/boom_standart plays when ordinary winning
// symbols clear (winThenExplode), Export/boom_bomb plays when a bomb
// detonates its whole row+column (bombPromise). Each exposes a single "win"
// clip.
//
// These VFX skeletons layer three slots — flame_smok (Multiply), boom_1
// (Normal) and sprite_fx (Additive). The vendor render path does not
// composite the Additive/Multiply layers over the bright reel grid correctly
// (their black-backed textures paint a solid black box around the blast, and
// neither premultiplied nor straight alpha fixes it), so we keep only the
// Normal-blend boom_1 layer — the core blast reads cleanly on its own. See
// hideBlendFxSlots below, called every frame because the clip's timelines
// re-assert the hidden attachments. Straight alpha, same as the symbols.
let boomStdResource = null;
function getBoomStdResource() {
  if (!boomStdResource) boomStdResource = loadSpineResource(`${ASSET_ROOT}/Export/boom_standart`);
  return boomStdResource;
}
let boomBombResource = null;
function getBoomBombResource() {
  if (!boomBombResource) boomBombResource = loadSpineResource(`${ASSET_ROOT}/Export/boom_bomb`);
  return boomBombResource;
}

// Null out every non-Normal-blend slot's attachment (see the boom loaders'
// note). Cheap; safe to call each frame.
function hideBlendFxSlots(instance) {
  for (const slot of instance.skeleton.slots) {
    if (slot.data.blendMode !== 0 && slot.getAttachment()) slot.setAttachment(null);
  }
}

// boom_standart/boom_bomb ship NO setup-pose width/height in their skeleton
// JSON (unlike every symbol/popup export), so resource.bounds is empty and the
// engine's fit math (anchor size / bounds size) divides by undefined → NaN
// scale → the explosion never draws. They're also empty at frame 0 (the blast
// expands over the clip), so getBoundsRect at the setup pose is null too.
// Compute a representative bounds by posing the skeleton at mid-'win' and
// caching it on the resource, then feed it in as boundsOverride.
function explosionBoundsOverride(resource) {
  if (resource._boundsOverride) return resource._boundsOverride;
  const probe = resource.createInstance();
  const anim = resource.skeletonData.findAnimation('win');
  anim.apply(probe.skeleton, 0, anim.duration * 0.5, false, [], 1, spine.MixBlend.setup, spine.MixDirection.mixIn);
  probe.skeleton.updateWorldTransform();
  resource._boundsOverride = probe.skeleton.getBoundsRect();
  return resource._boundsOverride;
}

// Plays one explosion clip (getRes -> boom_standart | boom_bomb) as a one-shot
// overlay on info's cell. Anchors to the *cell* (a stable size, never resized
// by JS), not info.anchor — that div gets resized per-instance to whichever
// symbol/token clip is currently playing there (playSymbolClipOnce), and an
// explosion can run concurrently with that, so sharing the anchor would race
// two target sizes onto one element. 1.3 is an aesthetic "explosion feels
// this big relative to the cell" choice — no static counterpart to match.
function playExplosion(info, getRes) {
  return getRes().then(
    (resource) =>
      new Promise((resolve) => {
        const instance = resource.createInstance();
        if (!resource.bounds || !resource.bounds.width) {
          instance.boundsOverride = explosionBoundsOverride(resource);
        }
        // Keep only the Normal-blend layer — re-hidden every frame because the
        // clip re-asserts the Additive/Multiply attachments (see boom loaders).
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
function playBoomExplosion(info) {
  return playExplosion(info, getBoomStdResource);
}
function playBombExplosion(info) {
  return playExplosion(info, getBoomBombResource);
}

function createCellNode(col, row, code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.style.top = `${rowTop(row)}px`;
  cell.dataset.symbol = code;

  const img = document.createElement('img');
  img.alt = code;
  img.src = `${ASSET_ROOT}/Export/${SYMBOL_FOLDERS[code]}/static.png`;
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

// Animated counterpart of renderInitialGrid, used at the start of every
// spin (see playAvalanche): the current on-screen elements fall away one
// after another, clearing the reel, then — after a short pause — the new
// spin's initial grid falls in from above the same way (product, this
// session). Falls back to a plain renderInitialGrid when there's nothing
// on screen yet (first load).
async function spinStartTransition(newGrid) {
  const outgoing = cellInfos.filter(Boolean);
  if (outgoing.length === 0) {
    renderInitialGrid(newGrid);
    playElementDropPatter(); // elements landed (SPIN_Start fires earlier, at press)
    return;
  }

  // Bottom row first, falling further down while fading out (product, this
  // session: "элементы... не должны просто уходить в прозрачность, они
  // должны еще имитировать падение вниз"). Every cell's own start delay is
  // rowOrderIndex*ROW_STAGGER_MS + col*REEL_STAGGER_MS — row GRID_ROWS-1
  // (bottom, rowOrderIndex 0) starts first, each row above it ROW_STAGGER_MS
  // later than the row below it *started* (not once it's fully landed —
  // product, this session: "не после того как упадет вся предыдущая
  // строка, а на 0.1 секунду позже элемента под собой"), and within a row
  // each column starts REEL_STAGGER_MS after the previous one. All
  // scheduled up front (setTimeout); .reel__grid's overflow:hidden clips
  // the fall once it passes the frame.
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

  // Fresh grid has landed — Element_drop patter (SPIN_Start already fired
  // 0.1s after the press, see startSpinPressCue).
  playElementDropPatter();

  // Bottom row first, filling upward (product, this session: "слот
  // заполнялся снизу вверх") — same per-cell diagonal delay as the outgoing
  // wave above. Each scatter's own landing clip is scheduled right along
  // with it, at delay + CASCADE_DROP_MS — the exact moment *that* cell's own
  // top transition finishes (product, this session: "лендинг анимация у
  // скаттера начинается в ту же долесекунду когда скаттер занимает свою
  // ячейку") — not a single revealScatterLandings() pass after the whole
  // wave settles, which would fire every scatter's clip in lockstep
  // regardless of how early its own cell actually landed.
  const scatterLandingPromises = [];
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
        scatterLandingPromises.push(
          new Promise((resolve) => {
            setTimeout(() => playSymbolClipOnce(info, 'landing').then(resolve), delay + CASCADE_DROP_MS);
          }),
        );
      }
    }
  }
  // Landing is always primary (product, this session): if this same grid
  // also has a win, playAvalanche's next step is celebrateStep — the
  // winning line's own animation — which must never start while a
  // scatter's landing clip here is still playing. The wave timer alone
  // doesn't guarantee that: a scatter's clip starts once *its own* cell
  // finishes falling and then plays out on its own schedule, which can run
  // past SPIN_START_WAVE_MS — so wait for every scheduled clip too, not
  // just the wave.
  await Promise.all([wait(SPIN_START_WAVE_MS), ...scatterLandingPromises]);
}

// Scatter ships a "landing" clip separate from "win" (see SYMBOL_CLIPS) —
// play it once, fire-and-forget, on every scatter that shows up in a fresh
// initial grid, purely cosmetic flourish (settles back to the static image
// on its own via onSettle, same lifecycle as any other one-shot clip here).
function revealScatterLandings() {
  for (const info of cellInfos) {
    if (info && info.symbol === 'scatter') playSymbolClipOnce(info, 'landing');
  }
}

// Free spins trigger/retrigger celebration (product, this session): plays
// every scatter's own "win" clip — awaited, not fire-and-forget, unlike
// revealScatterLandings above — so the caller (app.js's applySpinResult)
// can hold off switching into bonus mode until it's done. Scans the
// *current* on-screen cellInfos, which by the time this is called (after
// playAvalanche has finished every cascade step) already reflects
// avalanche_result.final_grid — the same grid the backend's trigger check
// itself now reads (app/api/v1/spin_service.py:_run_avalanche_spin), so
// this naturally covers a scatter that only appeared via a cascade's own
// refill, not just one that was already on the initial grid.
async function playScatterTriggerCelebration() {
  const scatterInfos = cellInfos.filter((info) => info && info.symbol === 'scatter');
  if (scatterInfos.length === 0) return;
  Sound.playSfx('scatterWin');
  await Promise.all(scatterInfos.map((info) => withTimeout(playSymbolClipOnce(info, 'win'))));
}

// Plays one non-looping clip on a cell, swapping the static <img> out for a
// live Spine instance for the duration, then reverting to the static image
// once it settles (cells are static images at rest — see the module
// docstring — so there's no persistent per-cell Spine instance to manage).
function playSymbolClipOnce(info, kind) {
  return getSymbolResource(info.symbol).then(
    (resource) =>
      new Promise((resolve) => {
        // Desktop: size the anchor to the skeleton's own setup-pose bounds so
        // fit:1 resolves to native scale, matching the native-size static <img>
        // (product: "не масштабируй"). Mobile: the 116px cell is far smaller
        // than the 150px art, so fit the clip to the cell instead — matching
        // the static's contain-fit in the portrait media query. getBounding-
        // ClientRect reflects --stage-scale, so this tracks the page scale.
        if (info.anchor) {
          const mobile = isMobileLayout();
          info.anchor.style.width = `${mobile ? cellW : resource.bounds.width}px`;
          info.anchor.style.height = `${mobile ? cellH : resource.bounds.height}px`;
          window.SlotCalibration?.applyAnchorOffset(info.anchor, 'sugar-galaxy', info.symbol);
        }
        const instance = resource.createInstance();
        instance.anchorEl = info.anchor || info.cell;
        instance.fit = 1;
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

// Dev-only: click a resting cell to loop-preview its win clip (mirrors
// East Discovery's previewSymbolWin) — not used by the real cascade flow,
// which calls playSymbolClipOnce directly and lets each step's own pacing
// decide when to move on.
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

// --- Multi counter (multy_counter.png, both modes) --------------------------
//
// Base game: the *current spin's* running cascade multiplier — same value
// as the cascade-banner above, just also mirrored onto this persistent HUD
// element, and reset to x1 at the start of every spin (playAvalanche).
// Free spins: the session-wide token-multiplier accumulator
// (FeatureOut.multiplier) — set once per spin from the server response
// (applySpinResult in app.js), NOT touched by this spin's own per-step
// trail multiplier (a different number — see product decision this
// session: base game resets every spin, free spins persists the whole
// round).

function currentMode() {
  return document.getElementById('screen').dataset.mode || 'base';
}

function updateMultiCounter(value) {
  document.getElementById('multiCounterValue').textContent = `x${value}`;
}

// --- One cascade step --------------------------------------------------
//
// step (CascadeStepOut, see app/api/v1/schemas.py): { wins, step_multiplier,
// step_win, grid_after, tokens_consumed, bombs_detonated }. grid_after is
// already the post-collapse-and-refill grid computed server-side
// (survivors dropped to the bottom preserving order, new draws prepended
// at top) — this only animates the transition to it.

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
  const tokenInfos = [];
  for (const tok of step.tokens_consumed) {
    const info = cellInfos[tok.row * GRID_COLS + tok.col];
    if (info) tokenInfos.push(info);
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

  // A removed (non-token) cell's own win animation (~1.7s, clip-driven —
  // see SYMBOL_FIT/getSymbolResource), then the instant it ends both the
  // static image and the (already-settled-back-to-static) cell go invisible
  // — "после её окончания статика и анимация сразу же пропадает" — and the
  // shared explosion plays right after ("и сразу же за ним анимация
  // взрыва").
  let winBoomPlayed = false;
  const winThenExplode = async (info) => {
    await withTimeout(playSymbolClipOnce(info, 'win'));
    info.img.style.visibility = 'hidden';
    // WIN_Boom fires with the element-clear explosion — once per step, no
    // matter how many cells clear at once (product).
    if (!winBoomPlayed) {
      winBoomPlayed = true;
      Sound.playSfx('winBoom');
    }
    await withTimeout(playBoomExplosion(info));
  };

  // Multiplier tokens (x2/x3/x5/x7) get their own, different choreography
  // (product, this session): win-clip plays, and the instant it settles the
  // token is already back to its static image (playSymbolClipOnce does this
  // on its own via onSettle) — no explosion, no flash poof, it just flies
  // from there (flyTokenToBadge, 1s, glow baked into .token-flight's own
  // drop-shadow) to the multi counter. The token's actual cell still fades
  // out normally afterward via fadeOutRemoved, called once celebrateStep
  // resolves — this only drives the flying ghost clone, a separate DOM
  // element (see flyTokenToBadge).
  const tokenThenFly = async (info, onArrive) => {
    await withTimeout(playSymbolClipOnce(info, 'win'));
    await flyTokenToBadge(info);
    onArrive();
  };

  // Tier wins / multiplier tokens: win clips start the instant the
  // combination is highlighted (WIN_LANDING_DELAY_MS = 0), then every
  // winning cell's own chain runs (withTimeout bounds each stage so a clip
  // that never settles can't hang the round) — celebrateStep's caller waits
  // for the real clip/flight durations, no artificial floor.
  const winPromise = (async () => {
    if (winInfos.length === 0 && tokenInfos.length === 0) return;
    await wait(WIN_LANDING_DELAY_MS);
    Sound.playSfx('smallWin'); // WIN_Small on every winning combination (product)
    showCascadeBanner(step.step_multiplier, step.step_win);

    // Product, this session: "в каунтере суммируются прилетевшие
    // множители" — the badge reveals this step's own multiplier
    // progressively as each token actually *arrives* (not the instant it's
    // swept up), starting from the step's trail baseline (step_multiplier
    // minus this step's own token values) and adding each token's value in
    // as its flight lands, so once every token has arrived the badge reads
    // exactly step.step_multiplier.
    const tokenSum = step.tokens_consumed.reduce((sum, tok) => sum + tok.value, 0);
    let runningMultiplier = step.step_multiplier - tokenSum;
    if (currentMode() === 'base') updateMultiCounter(runningMultiplier);

    const chains = winInfos.map(winThenExplode);
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

  // Bomb ("bomb", app/engine/avalanche.py:BombDetonation): sits still for
  // BOMB_PRE_EXPLODE_MS after landing, then its own "animation" clip
  // (Export/bomb via playSymbolClipOnce) plays alone on its own cell first —
  // only once every bomb's own clip has settled does the actual blast
  // happen: every affected cell (the bomb's own cell + its whole row/column
  // blast radius, `bomb.cleared` already includes the bomb's own position)
  // loses its static art and the bomb explosion VFX (playBombExplosion,
  // Export/boom_bomb) starts on all of them at the same moment. Independent
  // of whether anything else won this step.
  // Runs concurrently with winPromise above; celebrateStep waits for
  // whichever finishes last.
  const bombPromise = (async () => {
    if (bombInfos.length === 0) return;
    await wait(BOMB_PRE_EXPLODE_MS);

    // Explosion SFX fires BOMB_SFX_AFTER_START_MS (0.9s) after the bomb's own
    // detonation animation begins — scheduled up front so it lands mid-clip,
    // unconditionally at 0.9s, not gated on the clip finishing (product).
    setTimeout(() => Sound.playSfx('bombExplode'), BOMB_SFX_AFTER_START_MS);

    // Each bomb plays its own "animation" clip on its cell (playSymbolClipOnce
    // hides the static bomb <img> for the duration), then settles back — see
    // SYMBOL_CLIPS.bomb.
    await Promise.all(bombInfos.map((info) => withTimeout(playSymbolClipOnce(info, 'win'))));

    const blastInfos = new Set();
    for (const bomb of step.bombs_detonated) {
      for (const pos of bomb.cleared) {
        const info = cellInfos[pos.row * GRID_COLS + pos.col];
        if (info) blastInfos.add(info);
      }
    }
    for (const info of blastInfos) info.img.style.visibility = 'hidden';
    await Promise.all([...blastInfos].map((info) => withTimeout(playBombExplosion(info))));
  })();

  await Promise.all([winPromise, bombPromise]);
}

// Plain DOM/CSS ghost — a ".multi-counter" HUD element is well outside the
// avalanche grid, so this is a viewport-space fly, not a Spine effect (the
// canvas only ever draws inside the grid frame). Clones the token's current
// static image (whatever's showing right now — plain <img>, since
// playSymbolClipOnce/playBoomExplosion swap the img's visibility, not its
// src) and animates it from the cell's screen rect to the badge's via
// .token-flight's own @keyframes (css/sugar-galaxy.css) — the ghost's
// only job here is to compute the travel distance and hand it over as CSS
// custom properties.
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
  // Ease-in feel over the full flight (product, this session: "скорость от
  // медленной и чуть ускоряется к концу") — the animation's own 50%
  // keyframe places this at 30% of the distance, not 50%, so the second
  // half visibly covers more ground in the same time as the first.
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
    // Safety net: animationend can miss (element removed mid-flight,
    // prefers-reduced-motion disabling animations, etc.) — a token's
    // flight can never hang the round.
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

// Drops each affected column's survivors down to fill the gaps left by the
// removed cells, and refills the vacated top slots with grid_after's new
// draws — exactly collapse_and_refill's own "survivors drop to bottom, new
// draws prepended at top" semantics (app/engine/reels.py), so a survivor's
// fall distance is (number of removed cells originally below it in that
// column), individually, not a uniform per-column shift.
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
  // Base game's own running multiplier starts fresh every spin — free
  // spins' session accumulator is untouched here, set once from the
  // server response after this whole round finishes (applySpinResult).
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

// --- Screen dim / free spins mode (same mechanics as East Discovery) -------

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

// How long the "you won the bonus" popup holds on the blackout before the
// bonus screen is revealed behind it (product: ~3s of popup, then reveal).
const BONUS_INTRO_HOLD_MS = 3000;

// The base -> free-spins moment: black the screen out, play the bonusSpinsWin
// popup over the black for BONUS_INTRO_HOLD_MS, swap the bonus screen in behind
// the still-opaque black, then lift the blackout to reveal it. Shared by both
// the real scatter trigger (app.js) and the dev mode toggle, since both enter
// the bonus through setFreeSpinsMode below.
async function enterBonusTransition(amount = 0) {
  const screen = document.getElementById('screen');
  pushScreenDim(true); // opaque blackout in
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  screen.dataset.mode = 'freespins';
  setBackground('freespins');
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
      screen.dataset.mode = next;
      setBackground(next);
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
}

// --- Popups (same start/idle/end lifecycle as East Discovery's own popups) -

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

// Core popup lifecycle (start -> idle hold -> end). Unlike the old playPopup,
// the returned promise resolves only once the popup has FULLY played out (end
// animation done), so a caller can sequence work after it. `ownDim` lets a
// caller that already owns the screen dim (the bonus intro below) borrow the
// popup without it pushing/popping a dim of its own.
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

  // fit toggle is a no-op holdover from the party template — the layout now
  // always uses the design-space contain-scale below (there's no alternate
  // "scroll" layout), so just keep the button label honest.
  const fitToggleBtn = document.getElementById('devFitToggle');
  if (fitToggleBtn) {
    fitToggleBtn.textContent = 'fit-screen: on';
    fitToggleBtn.disabled = true;
  }
}

// The whole game is authored in a fixed design canvas that matches the
// slot-builder manifest's own coordinate space (see the layout coords baked
// into css/sugar-galaxy.css) — desktop 1932x940, mobile portrait 780x1416 —
// and #stage is contain-scaled to fit the viewport, exactly like the
// manifest renderer scales #playScreen (front/js/play/manifest-render.js).
const DESIGN = { desktop: { w: 1932, h: 940 }, mobile: { w: 780, h: 1416 } };

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function updateStageScale() {
  // Measure #screen (flex child above the UI bar) so the contain-scale fits
  // the play area, not the whole viewport — the UI bar keeps its own height.
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth || document.documentElement.clientWidth;
  const vh = screenEl.clientHeight || document.documentElement.clientHeight;
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  // Contain-fit so nothing is cropped; capped at 1 (never upscale past native).
  const scale = Math.min(vw / d.w, vh / d.h, 1);
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  document.documentElement.style.setProperty('--design-w', `${d.w}px`);
  document.documentElement.style.setProperty('--design-h', `${d.h}px`);
  readCellDims();
}

// --- Animated Spine backgrounds (builder manifest's bg_*_desk/mob "idle"
// loops) rendered on a dedicated full-screen stage behind everything, with a
// static PNG kept underneath as a fallback if the skeleton fails to load. ---
const BG_FOLDERS = {
  desktop: { base: 'bg_base_desk', freespins: 'bg_bonus_desk' },
  mobile: { base: 'bg_base_mob', freespins: 'bg_bonus_mob' },
};
// Per-mode scale multiplier applied on top of the cover-fit (product: the base
// animation didn't reach the screen edges — blow it up 10%, kept centred on
// #bgAnchor which is the full screen).
const BG_FIT = { base: 1.21, freespins: 1.0 };
let bgStage = null;
let bgInstance = null;
let bgResourceCache = {};

function bgFallbackSrc(mode) {
  if (isMobileLayout()) return mode === 'base' ? `${ASSET_ROOT}/bg_mob_base.png` : `${ASSET_ROOT}/bg_mob_bonus.png`;
  return mode === 'base' ? `${ASSET_ROOT}/bg_base_desk.png` : `${ASSET_ROOT}/bg_bonus_desk.png`;
}

// Pick the fit axis that makes the skeleton COVER the anchor (fill the short
// side, overflow the long one) — the engine only offers contain/width/height,
// so cover = whichever single-axis scale is larger, i.e. fit by the axis whose
// ratio demands it. Recomputed on resize because the viewport aspect changes.
function applyBgCoverFit() {
  if (!bgInstance) return;
  const anchor = document.getElementById('bgAnchor').getBoundingClientRect();
  const b = bgInstance.resource.bounds;
  if (!anchor.width || !anchor.height || !b.width || !b.height) return;
  bgInstance.fitMode = b.width / b.height > anchor.width / anchor.height ? 'height' : 'width';
}

function setBackground(mode) {
  const folder = (isMobileLayout() ? BG_FOLDERS.mobile : BG_FOLDERS.desktop)[mode] || BG_FOLDERS.desktop.base;
  document.getElementById('bgLayer').src = bgFallbackSrc(mode);
  if (!bgStage) return;
  const key = folder;
  // Load through bgStage's own asset manager — its texture lives in bgStage's
  // WebGL context, not the symbol stage's (see loadSpineResource).
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
    instance.fit = BG_FIT[mode] || 1;
    bgInstance = instance;
    applyBgCoverFit();
    bgStage.addBase(instance);
    instance.play('idle', true);
  });
}
let bgRenderToken = 0;

let lastMobile = null;

function handleResize() {
  updateStageScale();
  applyBgCoverFit();
  const nowMobile = isMobileLayout();
  if (nowMobile !== lastMobile) {
    lastMobile = nowMobile;
    // Device flipped: the animated background art differs per device — reload
    // it. The grid is left as-is until the next spin rebuilds it at the new
    // cell size (rebuilding here would tear cells down mid-animation and leave
    // orphaned Spine clips rendering at stale positions).
    setBackground(currentMode());
  }
}

async function init() {
  await SlotCalibration.load(); // must resolve before renderInitialGrid's createCellNode calls applyStaticContentOffset
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  window.addEventListener('resize', handleResize);
  // Some embeddings (the in-app browser pane) report a transient portrait /
  // zero-size viewport on the very first layout pass, then settle to the real
  // size without firing a clean resize — re-sync bg + scale shortly after boot.
  setTimeout(() => {
    lastMobile = isMobileLayout();
    updateStageScale();
    setBackground(currentMode());
    applyBgCoverFit();
  }, 250);

  bgStage = new SpineEngine.SpineStage(document.getElementById('bgSpineCanvas'));
  stage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  setBackground('base');
  setupDevPanel();

  renderInitialGrid(SYMBOL_LAYOUT);

  window.__slot = { stage, bgStage, cellInfos };
}

init();
