// Uniqorn Bad Santa — game-specific wiring for the avalanche/cascade round.
//
// The play loop is Sugar Galaxy's, port for port (app/engine/avalanche.py): a
// spin's whole result — initial grid plus every cascade step — arrives in one
// response, and this file only animates the walk from one step's grid to the
// next: highlight the step's wins + consumed multiplier baubles, blow them up,
// drop the survivors down and refill from the top with `grid_after`.
//
// The one structural difference from Sugar Galaxy: that game's art is Spine
// exports, and this theme's art is AI-generated flat PNGs — there are no
// skeletons, atlases, WebGL canvases or clip names anywhere here. Everything
// Sugar Galaxy played through a skeleton has a DOM/CSS counterpart (same
// approach as mr-president-unicorn/slot.js):
//
//   symbol win / landing / idle    -> classes on .reel__cell (see the stylesheet)
//   boom_standart / boom_bomb VFX  -> spawnBoom(), a flash + ring + sparks node
//   popups (6 skeletons)           -> buildPopupNode(), a plaque PNG + DOM text
//
// Everything else — the cascade choreography, its timings and the product
// decisions baked into them — is carried over unchanged.

const ASSET_ROOT = 'img/uniqorn-bad-santa';

// Codes match app/seed/uniqorn_bad_santa.py and the PNG file names 1:1.
const SYMBOL_CODES = [
  'wild', 'scatter',
  'hp_red', 'hp_yellow', 'hp_green', 'hp_blue',
  'lp_red', 'lp_yellow', 'lp_green', 'lp_blue',
  'x2', 'x3', 'x5', 'x7', 'bomb',
];

// Symbols that idle (breathe) permanently on the grid — everything else sits
// still until it wins. Purely a CSS class, see .reel__cell.is-special.
const SPECIAL_SYMBOLS = new Set(['wild', 'scatter', 'bomb']);

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}

const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN', tone: 'gold', plate: 'base' },
  megaWin: { title: 'MEGA WIN', tone: 'gold', plate: 'mega' },
  epicWin: { title: 'EPIC WIN', tone: 'red', plate: 'epic' },
  bonusSpinsWin: { title: 'FREE SPINS', sub: 'YOU WON', plate: 'base', amountSuffix: ' SPINS' },
  bonusSpinsTotalWin: { title: 'TOTAL WIN', sub: 'FREE SPINS OVER', plate: 'mega' },
  buyFreeSpins: { title: 'BUY FREE SPINS', sub: 'CONFIRM PURCHASE', plate: 'base' },
};
const POPUP_PLATE_SRC = {
  base: 'popup_plate.png',
  mega: 'popup_plate_mega.png',
  epic: 'popup_plate_epic.png',
};

// Matches the backend's grid shape (SpinResponse.grid), row-major grid[row][col].
const GRID_COLS = 6;
const GRID_ROWS = 5;

// Grid geometry comes from CSS (--cell-w/--cell-h/--cell-gap-x/-y) so the
// desktop (153x124, gap 10) and mobile-portrait (102x102, gap 10x6) layouts
// stay the single source of truth; both match the reel frame's own 9-sliced
// opening. Cached here, refreshed by readCellDims() on init/resize and at the
// start of every grid rebuild.
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
  ['hp_red', 'lp_yellow', 'x2', 'lp_green', 'hp_yellow', 'lp_blue'],
  ['lp_red', 'hp_green', 'wild', 'lp_yellow', 'hp_blue', 'lp_green'],
  ['scatter', 'lp_blue', 'hp_yellow', 'lp_red', 'x5', 'hp_red'],
  ['lp_green', 'bomb', 'lp_yellow', 'hp_blue', 'wild', 'lp_blue'],
  ['hp_green', 'lp_red', 'lp_blue', 'x7', 'lp_yellow', 'hp_red'],
];

const DIM_TRANSITION_MS = 320;
// One win pulse, in sync with the CSS keyframes (symbol-win). Spine drove this
// from the clip's own duration; with CSS both ends are ours, so the two numbers
// just have to agree.
const WIN_PULSE_MS = 700;
const LAND_BOUNCE_MS = 260;
const BOOM_MS = 520;
const BOMB_BOOM_MS = 680;
// Popup in/out — must match the .game-popup transitions.
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;

// Cascade pacing, inherited from Sugar Galaxy (every value there was a product
// decision made live on that game; this theme keeps the same feel).
const WIN_LANDING_DELAY_MS = 0;
const CASCADE_FADE_MS = 200;
const CASCADE_DROP_MS = 100; // must match .reel__cell's `top` transition
const CASCADE_STEP_GAP_MS = 220;
const WIN_LOOP_PAUSE_MS = 500;
// A bomb sits still this long after landing before its own wind-up plays.
const BOMB_PRE_EXPLODE_MS = 500;
const BOMB_ARM_MS = 620;
// Explosion SFX fires this long after the wind-up starts — mid-animation, not
// at the blast itself.
const BOMB_SFX_AFTER_START_MS = 400;
// Spin start: the resting elements fall away bottom row first, each cell
// starting rowOrderIndex*ROW_STAGGER_MS + col*REEL_STAGGER_MS after the wave
// begins (a pure diagonal offset, never gated on the previous row landing),
// then the fresh grid falls in from above the same way.
const ROW_STAGGER_MS = 50;
const REEL_STAGGER_MS = 50;
const SPIN_START_WAVE_MS = (GRID_ROWS - 1) * ROW_STAGGER_MS + (GRID_COLS - 1) * REEL_STAGGER_MS + CASCADE_DROP_MS;
const SPIN_START_GAP_MS = 300;
const SPIN_LANDING_DROP_COUNT = GRID_COLS;
const SPIN_LANDING_DROP_INTERVAL_MS = 100;
const SPIN_START_CUE_DELAY_MS = 100;
// Consumed multiplier bauble flying to the persistent multiplier badge — must
// match .token-flight's animation duration.
const TOKEN_FLIGHT_MS = 1000;

let cellInfos = []; // flat, row * GRID_COLS + col
let reelCols = [];

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Bounds a stage of the cascade so one wedged animation can't hang the round.
const STAGE_TIMEOUT_MS = 4000;
function withTimeout(promise, ms = STAGE_TIMEOUT_MS) {
  return Promise.race([promise, wait(ms)]);
}

function startSpinPressCue() {
  setTimeout(() => Sound.playSfx('spinStart'), SPIN_START_CUE_DELAY_MS);
}
function playElementDropPatter() {
  for (let i = 0; i < SPIN_LANDING_DROP_COUNT; i++) {
    setTimeout(() => Sound.playSfx('cascadeDrop'), i * SPIN_LANDING_DROP_INTERVAL_MS);
  }
}

// --- Cells ------------------------------------------------------------------

// No measured per-symbol offsets: every generated symbol was normalised into
// the same square box with a common optical centre when it was cut, so they
// already line up. A live override from Anim Lab's "Калибровать" still wins.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('uniqorn-bad-santa', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(col, row, code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.style.top = `${rowTop(row)}px`;
  cell.dataset.symbol = code;
  cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));

  const img = document.createElement('img');
  img.alt = code;
  img.src = symbolSrc(code);
  img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  const info = { row, col, symbol: code, cell, img, winLoopTimeout: null };
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
    info.winToken = (info.winToken || 0) + 1;
    info.cell.classList.remove('is-winning', 'is-arming', 'is-landing');
    if (info.img && info.img.getAttribute('src')) info.img.style.visibility = '';
  }
}

function renderInitialGrid(grid) {
  teardownCellInstances();
  buildReelGrid();
  for (let col = 0; col < GRID_COLS; col++) {
    for (let row = 0; row < GRID_ROWS; row++) {
      const info = createCellNode(col, row, grid[row][col]);
      reelCols[col].appendChild(info.cell);
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
  revealScatterLandings();
}

// Animated counterpart of renderInitialGrid, used at the start of every spin:
// the current elements fall away one after another, and after a short pause the
// new spin's initial grid falls in from above the same way. Falls back to a
// plain renderInitialGrid when there's nothing on screen yet (first load).
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
      const info = createCellNode(col, row, newGrid[row][col]);
      info.cell.style.transition = 'none';
      info.cell.style.top = `${rowTop(row - GRID_ROWS)}px`; // stacked above the reel
      reelCols[col].appendChild(info.cell);
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
  void document.getElementById('reelGrid').offsetHeight; // reflow so `top` transitions

  playElementDropPatter();

  // Bottom row first, filling upward, same per-cell diagonal delay as the
  // outgoing wave. Each cell's landing bounce and each scatter's landing
  // flourish are scheduled for the exact moment that cell's own `top`
  // transition finishes — not once for the whole wave.
  const scatterLandings = [];
  for (let row = GRID_ROWS - 1; row >= 0; row--) {
    const rowOrderIndex = GRID_ROWS - 1 - row;
    for (let col = 0; col < GRID_COLS; col++) {
      const info = cellInfos[row * GRID_COLS + col];
      const delay = rowOrderIndex * ROW_STAGGER_MS + col * REEL_STAGGER_MS;
      setTimeout(() => {
        info.cell.style.transition = '';
        info.cell.style.top = `${rowTop(row)}px`;
        setTimeout(() => playLandBounce(info), CASCADE_DROP_MS);
      }, delay);
      if (info.symbol === 'scatter') {
        scatterLandings.push(
          new Promise((resolve) => {
            setTimeout(() => playWinPulse(info).then(resolve), delay + CASCADE_DROP_MS);
          }),
        );
      }
    }
  }
  // The landing flourish is always primary: if this same grid also has a win,
  // playAvalanche's next step is celebrateStep, which must never start while a
  // scatter is still playing its landing.
  await Promise.all([wait(SPIN_START_WAVE_MS), ...scatterLandings]);
}

function revealScatterLandings() {
  for (const info of cellInfos) {
    if (info && info.symbol === 'scatter') playWinPulse(info);
  }
}

// Free spins trigger/retrigger celebration: pulses every scatter on the board —
// awaited, unlike revealScatterLandings, so app.js can hold off switching into
// bonus mode until it's done. Scans the *current* cells, which by then already
// reflect the post-cascade grid the backend's own trigger check read, so a
// scatter that only appeared via a refill is covered too.
async function playScatterTriggerCelebration() {
  const scatterInfos = cellInfos.filter((info) => info && info.symbol === 'scatter');
  if (scatterInfos.length === 0) return;
  Sound.playSfx('scatterWin');
  await Promise.all(scatterInfos.map((info) => withTimeout(playWinPulse(info))));
}

// The little squash-and-settle a symbol does as it lands on its cell.
function playLandBounce(info) {
  if (!info) return;
  info.cell.classList.remove('is-landing');
  void info.cell.offsetWidth; // restart the keyframes
  info.cell.classList.add('is-landing');
  setTimeout(() => info.cell.classList.remove('is-landing'), LAND_BOUNCE_MS);
}

// One win pulse on a cell (the CSS stand-in for a symbol's "win" clip).
function playWinPulse(info) {
  info.cell.classList.remove('is-winning');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-winning');
  return wait(WIN_PULSE_MS).then(() => {
    info.cell.classList.remove('is-winning');
  });
}

// Dev-only: click a resting cell to loop-preview its win pulse. Not used by the
// real cascade flow, which calls playWinPulse directly.
function previewSymbolWin(info) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  const token = (info.winToken = (info.winToken || 0) + 1);
  const playOnce = () => {
    playWinPulse(info).then(() => {
      if (token !== info.winToken) return;
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

// --- Hero -------------------------------------------------------------------
//
// The unicorn sitting beside the reels. Static art with CSS moods (see .hero in
// the stylesheet) — 'idle' is the resting loop, 'cheer' plays while a win is
// being celebrated. Every cheer is self-cancelling: a later win restarts the
// timer rather than stacking, so he always lands back on idle.
let heroMoodTimeout = null;

function setHeroMood(mood, holdMs = 0) {
  const hero = document.getElementById('hero');
  if (!hero) return;
  if (heroMoodTimeout) {
    clearTimeout(heroMoodTimeout);
    heroMoodTimeout = null;
  }
  hero.classList.toggle('is-cheer', mood === 'cheer');
  if (mood !== 'idle' && holdMs > 0) {
    heroMoodTimeout = setTimeout(() => {
      heroMoodTimeout = null;
      hero.classList.remove('is-cheer');
    }, holdMs);
  }
}

// --- Explosions -------------------------------------------------------------
//
// Sugar Galaxy plays two Spine VFX here (boom_standart when winning symbols
// clear, boom_bomb when a bomb detonates). This theme has no skeletons, so the
// blast is a DOM node: a white-hot flash, an expanding ring and a ring of
// sparks, all CSS keyframes (see .boom in the stylesheet). Resolves when the
// longest of them has finished, so the caller can sequence the drop after it.
const BOOM_SPARK_COUNT = 10;

function spawnBoom(info, { bomb = false } = {}) {
  const node = document.createElement('div');
  node.className = bomb ? 'boom boom--bomb' : 'boom';

  const flash = document.createElement('div');
  flash.className = 'boom__flash';
  node.appendChild(flash);

  const ring = document.createElement('div');
  ring.className = 'boom__ring';
  node.appendChild(ring);

  const spread = (bomb ? cellW * 1.0 : cellW * 0.62);
  for (let i = 0; i < BOOM_SPARK_COUNT; i++) {
    const spark = document.createElement('div');
    spark.className = 'boom__spark';
    // Deterministic fan (i/N of a full turn) with a small per-spark jitter, so
    // the burst reads as a ring rather than a random cluster.
    spark.style.setProperty('--a', `${(360 / BOOM_SPARK_COUNT) * i + (i % 2 ? 9 : -9)}deg`);
    spark.style.setProperty('--d', `${spread * (0.7 + (i % 3) * 0.15)}px`);
    node.appendChild(spark);
  }

  info.cell.appendChild(node);
  const life = bomb ? BOMB_BOOM_MS : BOOM_MS;
  return wait(life).then(() => node.remove());
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

// --- Multi counter ----------------------------------------------------------
//
// Base game: this spin's running cascade multiplier, reset to x1 every spin.
// Free spins: the session-wide token accumulator (FeatureOut.multiplier), set
// once per spin from the server response (applySpinResult in app.js).

function currentMode() {
  return document.getElementById('screen').dataset.mode || 'base';
}

function updateMultiCounter(value) {
  const el = document.getElementById('multiCounterValue');
  if (!el) return;
  el.textContent = `x${value}`;
  const badge = document.getElementById('multiCounter');
  if (badge) {
    badge.classList.remove('is-hit');
    void badge.offsetWidth;
    badge.classList.add('is-hit');
  }
}

// --- One cascade step -------------------------------------------------------
//
// step (CascadeStepOut): { wins, step_multiplier, step_win, grid_after,
// tokens_consumed, bombs_detonated }. grid_after is already the post-collapse
// grid computed server-side; this only animates the transition to it.

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

  // A removed (non-token) cell pulses, then the instant that ends both its art
  // and the cell go invisible and the explosion plays on the empty cell.
  let winBoomPlayed = false;
  const winThenExplode = async (info) => {
    await withTimeout(playWinPulse(info));
    info.img.style.visibility = 'hidden';
    // One WIN_Boom per step, no matter how many cells clear at once.
    if (!winBoomPlayed) {
      winBoomPlayed = true;
      Sound.playSfx('winBoom');
    }
    await withTimeout(spawnBoom(info));
  };

  // Multiplier baubles get their own choreography: they pulse, then fly to the
  // multiplier badge — no explosion. The cell itself still fades out afterwards
  // via fadeOutRemoved; this only drives the flying ghost clone.
  const tokenThenFly = async (info, onArrive) => {
    await withTimeout(playWinPulse(info));
    await flyTokenToBadge(info);
    onArrive();
  };

  const winPromise = (async () => {
    if (winInfos.length === 0 && step.tokens_consumed.length === 0) return;
    await wait(WIN_LANDING_DELAY_MS);
    Sound.playSfx('smallWin');
    showCascadeBanner(step.step_multiplier, step.step_win);
    // He cheers for as long as this step's celebration runs, then drops back to
    // idle on his own (the hold is generous — a long chain of clips and
    // explosions still ends inside it, and the next step just restarts it).
    setHeroMood('cheer', 4000);

    // The badge reveals this step's multiplier progressively, as each bauble
    // actually *arrives*: it starts from the step's trail baseline
    // (step_multiplier minus this step's own token values) and adds each value
    // in on landing, so once every bauble has arrived it reads exactly
    // step.step_multiplier.
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

  // Bomb: sits still for BOMB_PRE_EXPLODE_MS after landing, then plays its own
  // wind-up alone on its cell; only once every bomb has finished arming does the
  // blast happen — every cell in the blast radius (bomb.cleared already includes
  // the bomb's own position) loses its art and gets the bomb explosion at the
  // same moment. Independent of whether anything else won this step; runs
  // concurrently with winPromise and celebrateStep waits for both.
  const bombPromise = (async () => {
    if (bombInfos.length === 0) return;
    await wait(BOMB_PRE_EXPLODE_MS);
    setTimeout(() => Sound.playSfx('bombExplode'), BOMB_SFX_AFTER_START_MS);

    for (const info of bombInfos) {
      info.cell.classList.remove('is-arming');
      void info.cell.offsetWidth;
      info.cell.classList.add('is-arming');
    }
    await wait(BOMB_ARM_MS);
    for (const info of bombInfos) info.cell.classList.remove('is-arming');

    const blastInfos = new Set();
    for (const bomb of step.bombs_detonated) {
      for (const pos of bomb.cleared) {
        const info = cellInfos[pos.row * GRID_COLS + pos.col];
        if (info) blastInfos.add(info);
      }
    }
    for (const info of blastInfos) info.img.style.visibility = 'hidden';
    await Promise.all([...blastInfos].map((info) => withTimeout(spawnBoom(info, { bomb: true }))));
  })();

  await Promise.all([winPromise, bombPromise]);
}

// Plain DOM ghost — the multiplier badge sits well outside the grid, so this is
// a viewport-space fly. Clones the bauble's art and animates it from the cell's
// screen rect to the badge's via .token-flight's own keyframes; the ghost only
// has to compute the travel distance and hand it over as CSS custom properties.
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
  // Ease-in feel: the 50% keyframe sits at 30% of the distance, so the second
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
    // Safety net: animationend can miss (element removed mid-flight, reduced
    // motion disabling animations) — a bauble's flight can never hang the round.
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

// Drops each affected column's survivors down into the gaps and refills the
// vacated top slots with grid_after's new draws — exactly collapse_and_refill's
// semantics, so a survivor's fall distance is the number of removed cells
// originally below it in that column, individually, not a uniform column shift.
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
    const info = createCellNode(col, finalRow, targetColumn[finalRow]);
    info.cell.style.transition = 'none';
    info.cell.style.top = `${rowTop(finalRow - numRemoved)}px`;
    colEl.appendChild(info.cell);
    void info.cell.offsetHeight; // reflow so the next `top` change transitions
    info.cell.style.transition = '';
    info.cell.style.top = `${rowTop(finalRow)}px`;
    newColInfos[finalRow] = info;
  }

  Sound.playSfx('cascadeDrop');
  await wait(CASCADE_DROP_MS);

  for (const info of removedInfos) info.cell.remove();
  for (let row = 0; row < GRID_ROWS; row++) {
    cellInfos[row * GRID_COLS + col] = newColInfos[row];
    const landed = newColInfos[row];
    if (landed && landed.row === row) playLandBounce(landed);
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
  // The base game's running multiplier starts fresh every spin; free spins'
  // session accumulator is untouched here (set once from the server response
  // after this whole round finishes — applySpinResult).
  if (currentMode() === 'base') updateMultiCounter(1);
  setHeroMood('idle'); // last spin's cheer never carries into this one
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

// --- Screen dim / free spins mode ------------------------------------------

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
// screen is revealed behind it (product: ~3s of popup, then reveal).
const BONUS_INTRO_HOLD_MS = 3000;

// The base -> free-spins moment: black the screen out, play bonusSpinsWin over
// the black, swap the bonus screen in behind the still-opaque black, then lift
// the blackout to reveal it. Shared by the real scatter trigger (app.js) and the
// dev mode toggle, since both enter the bonus through setFreeSpinsMode.
async function enterBonusTransition(amount = 0) {
  pushScreenDim(true);
  await wait(DIM_TRANSITION_MS);
  await playPopupSequence('bonusSpinsWin', amount, BONUS_INTRO_HOLD_MS, { ownDim: false });
  applyModeScreen('freespins');
  await wait(DIM_TRANSITION_MS);
  popScreenDim(true);
}

function applyModeScreen(next) {
  document.getElementById('screen').dataset.mode = next;
  document.getElementById('bgLayer').src = bgSrcFor(next);
}

function setFreeSpinsMode(active, amount = 0) {
  const screen = document.getElementById('screen');
  const next = active ? 'freespins' : 'base';
  if (screen.dataset.mode === next) return Promise.resolve();

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

// --- Popups -----------------------------------------------------------------
//
// Built fresh per showing rather than kept around: a popup is on screen for a
// couple of seconds a few times a session, so there is nothing to cache, and a
// node that isn't in the DOM can't leave a stale amount behind.
function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key] || { title: key, plate: 'base' };
  const plate = cfg.plate || 'base';
  const root = document.createElement('div');
  root.className = `game-popup is-plate-${plate}`;
  if (isMobileLayout()) root.classList.add('is-mobile');

  // The plaque art is a generated PNG with a deliberately empty navy panel; the
  // text is DOM on top, positioned against that panel's measured bounds (see
  // --popup-panel-* in the stylesheet). Re-measure those if a plate is ever
  // regenerated.
  const art = document.createElement('img');
  art.className = 'game-popup__art';
  art.src = `${ASSET_ROOT}/img/${POPUP_PLATE_SRC[plate]}`;
  art.alt = '';
  root.appendChild(art);

  const body = document.createElement('div');
  body.className = 'game-popup__body';

  if (cfg.sub) {
    const sub = document.createElement('div');
    sub.className = 'game-popup__sub';
    sub.textContent = cfg.sub;
    body.appendChild(sub);
  }

  const title = document.createElement('div');
  title.className = 'game-popup__title';
  title.textContent = cfg.title;
  body.appendChild(title);

  const amountEl = document.createElement('div');
  amountEl.className = 'game-popup__amount';
  amountEl.textContent = Number(amount).toLocaleString('en-US') + (cfg.amountSuffix || '');
  body.appendChild(amountEl);

  root.appendChild(body);
  return root;
}

// The three plaques have panels of different shapes (the epic one's is a
// circle) while titles run from "BIG WIN" to "BUY FREE SPINS" — rather than
// hand-tune a font size per plate/title pair, shrink each line until it fits.
// Runs after the node is in the DOM so the panel has real bounds.
function fitPopupText(node) {
  const panel = node.querySelector('.game-popup__body');
  if (!panel) return;
  for (const el of node.querySelectorAll('.game-popup__title, .game-popup__amount, .game-popup__sub')) {
    let size = parseFloat(getComputedStyle(el).fontSize);
    // Measure against the PANEL, not the line's own box: the lines are
    // nowrap flex items in a centred column, so each one is exactly as wide as
    // its text (scrollWidth === clientWidth) no matter how far it overhangs the
    // plaque — comparing a line against itself never detected the overflow that
    // pushed "MEGA WIN" off both sides of its panel.
    // offsetWidth, not getBoundingClientRect(): this runs before the popup's
    // enter transition, while it is still scaled to 0.7 — a rect-based width
    // is 30% short and reads as "it fits" for text that plainly doesn't.
    for (let i = 0; i < 24 && el.offsetWidth > panel.clientWidth && size > 8; i += 1) {
      size *= 0.92;
      el.style.fontSize = `${size}px`;
    }
  }
}

// Core popup lifecycle (in -> hold -> out). The returned promise resolves only
// once the popup has FULLY played out, so a caller can sequence work after it.
// `ownDim` lets a caller that already owns the screen dim (the bonus intro
// above) borrow the popup without it pushing/popping its own dim.
function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = true, opaque = false } = {}) {
  if (!POPUP_CONFIG[key]) return Promise.resolve();

  return new Promise((resolve) => {
    // Every exit goes through ONE finish(), guaranteed to run — on the normal
    // path, on any error, and on a safety timeout. The dim goes up before the
    // popup is built, so anything that throws in between must not be able to
    // leave the screen dimmed forever with no popup on it.
    let node = null;
    let dimmed = false;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safetyTimer);
      if (node) node.remove();
      if (dimmed) popScreenDim(opaque);
      resolve();
    };
    const safetyTimer = setTimeout(finish, holdMs + 8000);

    (async () => {
      Sound.playSfx('popupOpen');
      if (ownDim) {
        pushScreenDim(opaque);
        dimmed = true;
        await wait(DIM_TRANSITION_MS);
      }

      node = buildPopupNode(key, amount);
      document.getElementById('screen').appendChild(node);
      fitPopupText(node);
      void node.offsetWidth; // commit the pre-enter state before transitioning
      node.classList.add('is-in');

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      await wait(POPUP_EXIT_MS);
      finish();
    })().catch((err) => {
      console.error(`popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
      finish();
    });
  });
}

function playPopup(key, amount = 0, holdMs = 2500) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true });
}

// --- Dev panel --------------------------------------------------------------

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');
  toggleBtn.addEventListener('click', () => {
    const next = document.getElementById('screen').dataset.mode === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 7); // demo spins count for the intro popup
    toggleBtn.textContent = `mode: ${next}`;
  });

  document.querySelectorAll('[data-popup]').forEach((btn) => {
    btn.addEventListener('click', () => playPopup(btn.dataset.popup, 12345));
  });

  const boomBtn = document.getElementById('devBoom');
  if (boomBtn) {
    boomBtn.addEventListener('click', async () => {
      const picks = cellInfos.filter(Boolean).slice(6, 12);
      await Promise.all(picks.map(async (info) => {
        await playWinPulse(info);
        info.img.style.visibility = 'hidden';
        await spawnBoom(info, { bomb: info.symbol === 'bomb' });
        info.img.style.visibility = '';
      }));
    });
  }
}

// --- Layout -----------------------------------------------------------------
//
// The whole game is authored in a fixed design canvas (desktop 1932x940, mobile
// portrait 780x1416) and #stage is contain-scaled to fit, exactly like Sugar
// Galaxy / the manifest renderer.
const DESIGN = { desktop: { w: 1932, h: 940 }, mobile: { w: 780, h: 1416 } };

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function updateStageScale() {
  const screenEl = document.getElementById('screen');
  const vw = screenEl.clientWidth || document.documentElement.clientWidth;
  const vh = screenEl.clientHeight || document.documentElement.clientHeight;
  const d = isMobileLayout() ? DESIGN.mobile : DESIGN.desktop;
  const scale = Math.min(vw / d.w, vh / d.h, 1); // contain-fit, never upscale
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  document.documentElement.style.setProperty('--design-w', `${d.w}px`);
  document.documentElement.style.setProperty('--design-h', `${d.h}px`);
  readCellDims();
}

function bgSrcFor(mode) {
  if (isMobileLayout()) {
    return mode === 'base' ? `${ASSET_ROOT}/img/bg_base_mob.jpg` : `${ASSET_ROOT}/img/bg_bonus_mob.jpg`;
  }
  return mode === 'base' ? `${ASSET_ROOT}/img/bg_base.jpg` : `${ASSET_ROOT}/img/bg_bonus.jpg`;
}

// The reel frame is two files, not one stretched image: each was 9-sliced to
// its own device's grid aspect (see the stylesheet header), so the art swaps
// with the layout exactly like the background does.
function frameSrcFor() {
  return `${ASSET_ROOT}/img/${isMobileLayout() ? 'frame_mob.png' : 'frame_desk.png'}`;
}

function updateBgForLayout() {
  document.getElementById('bgLayer').src = bgSrcFor(currentMode());
  const frameEl = document.getElementById('frameLayer');
  if (frameEl) frameEl.src = frameSrcFor();
}

let lastMobile = null;

function handleResize() {
  updateStageScale();
  const nowMobile = isMobileLayout();
  if (nowMobile !== lastMobile) {
    lastMobile = nowMobile;
    // Device flipped: both the background art and the cell geometry differ per
    // device, so reload the bg and rebuild the grid at the new cell size.
    updateBgForLayout();
    renderInitialGrid(currentGrid());
  }
}

// The grid as it currently stands on screen — used when the layout flips and
// the cells have to be rebuilt at the other device's cell size.
function currentGrid() {
  const grid = [];
  for (let row = 0; row < GRID_ROWS; row++) {
    const cols = [];
    for (let col = 0; col < GRID_COLS; col++) {
      const info = cellInfos[row * GRID_COLS + col];
      cols.push(info ? info.symbol : SYMBOL_LAYOUT[row][col]);
    }
    grid.push(cols);
  }
  return grid;
}

// --- Boot preloader --------------------------------------------------------
// Decode every symbol PNG, both backgrounds and the popup plaques, and warm the
// SFX buffers, all behind the progress overlay driven by js/preloader.js. Every
// task resolves (errors swallowed) and the whole thing is capped by a timeout,
// so nothing can strand the overlay.
const PRELOAD_TIMEOUT_MS = 12000;

function preloadImage(src) {
  const img = new Image();
  img.src = src;
  return img.decode ? img.decode() : new Promise((res) => {
    img.onload = res;
    img.onerror = res;
  });
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
  for (const code of SYMBOL_CODES) tasks.push(track(preloadImage(symbolSrc(code))));
  for (const plate of Object.values(POPUP_PLATE_SRC)) {
    tasks.push(track(preloadImage(`${ASSET_ROOT}/img/${plate}`)));
  }
  tasks.push(track(preloadImage(`${ASSET_ROOT}/img/hero.png`)));
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('freespins'))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // must resolve before createCellNode's applyStaticContentOffset
  Sound.playMusic('base');
  lastMobile = isMobileLayout();
  updateStageScale();
  updateBgForLayout();
  window.addEventListener('resize', handleResize);
  // Some embeddings (the in-app browser pane) report a transient portrait /
  // zero-size viewport on the very first layout pass, then settle without
  // firing a clean resize — re-sync shortly after boot.
  setTimeout(() => {
    lastMobile = isMobileLayout();
    updateStageScale();
    updateBgForLayout();
  }, 250);

  setupDevPanel();

  await preloadAssets();
  renderInitialGrid(SYMBOL_LAYOUT);

  if (window.Preloader) window.Preloader.done();

  // A getter, not a snapshot: buildReelGrid REASSIGNS cellInfos on every spin,
  // so handing out the array captured at boot would leave dev tooling (Anim Lab,
  // console pokes) holding cells that were detached from the document spins ago
  // — they still look like real nodes, they just have no layout and nothing
  // rendered on them ever shows up.
  window.__slot = { get cellInfos() { return cellInfos; } };
}

init();
