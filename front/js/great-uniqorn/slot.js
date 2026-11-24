// Great Uniqorn — adapted from ../uniqorn-scandal/slot.js (same Amy's Fruit
// Farm mechanic, same PNG-instead-of-Spine presentation: reel motion, win-cell
// sequencing, scatter anticipation, free-spins mode, inline win amount, buy
// bonus). What differs:
//
//   layout     the whole scene is the designer's Figma frame (1932x940 desktop,
//              780x1416 portrait), scaled as one piece by layoutStage()
//   wild       no expansion; every landed WILD rolls a multiplier server-side
//              (multiplier_wilds in the spin response) and flips into its x2/x3/
//              x5/x7/x9 art right after its reel stops — revealWildMultiplier()
//   popups     one designer PNG per popup + the amount as DOM text
//   hero       baked into the background art, so there is no hero layer


const ASSET_ROOT = 'img/great-uniqorn';

const SYMBOL_CODES = ['wild', 'scatter', 'jet', 'docs', 'hair', 'a', 'k', 'q', 'j'];
// Multiplier variants the art ships (symbols/x2.png ... x9.png). Anything else
// the server might send falls back to the plain WILD art.
const WILD_MULTIPLIERS = [2, 3, 5, 7, 9];

// Bumped when a symbol PNG is re-cut, so browsers/Telegram drop the cached one
// (v2: the WILD's «D» had a see-through hole from the alpha recovery).
const SYMBOL_VERSION = '5';

function symbolSrc(code, mult = 1) {
  if (code === 'wild' && WILD_MULTIPLIERS.includes(mult)) return `${ASSET_ROOT}/symbols/x${mult}.png?v=${SYMBOL_VERSION}`;
  return `${ASSET_ROOT}/symbols/${code}.png?v=${SYMBOL_VERSION}`;
}

// Codes eligible as random spin-loop filler — excludes scatter (a trigger
// symbol, shouldn't blur past as filler) and wild (a wild blurring past would
// read as one that landed and should have rolled a multiplier).
const FILLER_CODES = SYMBOL_CODES.filter((c) => c !== 'scatter' && c !== 'wild');

// wild and scatter idle permanently on the grid (a slow breathe/glow); every
// other symbol sits still until it wins. Purely a CSS class — see
// .reel__cell.is-special in the stylesheet.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// How long one win pulse runs, in sync with the CSS keyframes. The original
// resolved this from the Spine clip's own duration; with CSS we own both ends,
// so the two numbers just have to agree.
const WIN_PULSE_MS = 620;
// Popup in/out durations — must match the .game-popup transitions. The
// skeleton's own intro is 1.2s; the plate has popped by POPUP_AMOUNT_DELAY_MS
// (matches --amount-delay in the stylesheet), so the amount appears then.
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;
const POPUP_AMOUNT_DELAY_MS = 720;

// Attract-mode layout shown before the first real spin — the grid from the
// Figma mockup, including its x5 wild (ATTRACT_MULTIPLIERS). Also fixes the
// grid's 3 rows x 5 reels shape.
const SYMBOL_LAYOUT = [
  ['k', 'wild', 'j', 'docs', 'scatter'],
  ['docs', 'a', 'hair', 'wild', 'jet'],
  ['a', 'wild', 'q', 'k', 'j'],
];
const ATTRACT_MULTIPLIERS = { '0,1': 5 };
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

// Popups are the designer's art (one PNG per popup, see the stylesheet) with
// only the amount in the DOM. `kind` picks which text box of the mockup the
// amount sits in: a win plate, the larger total-win plate, or the round badge
// of the free-spins popup. Every free-spins round ends on BONUS SPINS TOTAL
// WIN, won from scatters or bought (FREE SPINS TOTAL WIN dropped 2026-11-05).
//
// Each popup is a Spine skeleton (scripts/great_uniqorn_popups.py) — `spine` /
// `boughtSpine` name its folder under popups/, one per layout (_desk/_mob).
// `art` / `boughtArt` is the flat designer PNG, kept as the fallback when
// WebGL or the skeleton isn't available.
const POPUP_CONFIG = {
  bigWin: { art: 'pop_big', spine: 'big', kind: 'win' },
  epicWin: { art: 'pop_epic', spine: 'epic', kind: 'win' },
  megaWin: { art: 'pop_mega', spine: 'mega', kind: 'win' },
  bonusSpinsWin: { art: 'pop_fswin', spine: 'fswin', kind: 'spins' },
  bonusSpinsTotalWin: { art: 'pop_bstotal', spine: 'bstotal', kind: 'total' },
};

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 500;

let cellInfos = [];
let reelCols = [];

// --- Win lines --------------------------------------------------------------
//
// The Wild Western original played one of 11 pre-baked Spine animations, keyed
// by payline index. This game has no Spine, and it doesn't need the payline
// table either: every line win already carries its own `positions`, so the
// line is drawn straight through the winning cells' real centres as an SVG
// polyline over .reel__grid. That also means a backend payline the art never
// covered can no longer pay without a line.
const WIN_LINE_NS = 'http://www.w3.org/2000/svg';
let winLineSvg = null;
let winLineLoopTimeout = null;
// Every repeating "play once, pause, play again" loop in this file is a
// promise chain, and clearing its pending timeout is NOT enough to stop it: if
// the loop is mid-play when it's cancelled, the in-flight promise still
// resolves afterwards and re-arms the timeout, resurrecting a loop that was
// supposed to be dead. That is what made a win line from an earlier spin
// reappear over later, non-winning spins. Each loop therefore carries a
// generation token, bumped by whatever cancels it, and every continuation
// checks the token it started with before scheduling more work.
let winLineToken = 0;

function ensureWinLineSvg() {
  const gridEl = document.querySelector('.reel__grid');
  if (!gridEl) return null;
  if (winLineSvg && winLineSvg.parentNode === gridEl) return winLineSvg;
  const svg = document.createElementNS(WIN_LINE_NS, 'svg');
  svg.setAttribute('class', 'win-line');
  svg.setAttribute('preserveAspectRatio', 'none');
  gridEl.appendChild(svg);
  winLineSvg = svg;
  return svg;
}

// Cell centres in .reel__grid's own coordinate space. Read live rather than
// computed from row/col arithmetic: the grid is CSS-scaled (layoutStage + the stylesheet)
// and the frame's opening is not a plain even split, so measuring is the only
// thing that stays correct across breakpoints.
function cellCentre(row, col) {
  const info = cellInfos[row * GRID_COLS + col];
  const gridEl = document.querySelector('.reel__grid');
  if (!info || !gridEl) return null;
  const cellRect = info.cell.getBoundingClientRect();
  const gridRect = gridEl.getBoundingClientRect();
  const scale = gridRect.width / gridEl.offsetWidth || 1;
  return {
    x: (cellRect.left + cellRect.width / 2 - gridRect.left) / scale,
    y: (cellRect.top + cellRect.height / 2 - gridRect.top) / scale,
  };
}

// --- Spine win lines (scripts/great_uniqorn_winlines.py) ---------------------
//
// One skeleton holds all 11 paylines in .reel__grid space (1040 x 620, origin
// at its centre), clipped at the reel window. A shown line plays
// line{n}_in (draws itself with a star on the front, rings + stars pop on the
// cells) then line{n}_loop (glow breath, comet, twinkling stars). Several
// lines at once = one track each, slightly staggered. It is drawn UNDER the
// symbol skeletons (behind-all base), over the static symbol pictures; the SVG
// line below stays as the fallback when the skeleton can't run.
const WINLINES_DIR = `${ASSET_ROOT}/spine/winlines`;
const WINLINES_VERSION = '1';
const WINLINES_STAGGER_S = 0.09;
let winLinesInst = null;
let winLinesShown = false;

function loadWinLines() {
  const stage = ensureSpineStage();
  const grid = document.querySelector('.reel__grid');
  if (!stage || !grid) return Promise.resolve();
  return SpineEngine.SpineResource.load(stage.assetManager, WINLINES_DIR, { version: WINLINES_VERSION })
    .then((res) => {
      const inst = res.createInstance();
      inst.anchorEl = grid;
      inst.fit = 1;
      inst.boundsOverride = { x: -520, y: -310, width: 1040, height: 620 };
      winLinesInst = inst;
    })
    .catch((err) => console.warn('win-line skeleton unavailable, SVG lines stay:', err));
}

function showSpineWinLines(paylines) {
  if (!winLinesInst || !spineStage) return false;
  const st = winLinesInst.animationState;
  const data = winLinesInst.resource.skeletonData;
  st.clearTracks();
  winLinesInst.skeleton.setToSetupPose();
  const lines = paylines.filter((n) => data.findAnimation(`line${n}_in`));
  if (!lines.length) { hideSpineWinLines(); return true; }
  lines.forEach((n, i) => {
    st.setEmptyAnimation(i, 0);
    st.addAnimation(i, `line${n}_in`, false, i * WINLINES_STAGGER_S);
    st.addAnimation(i, `line${n}_loop`, true, 0);
  });
  if (!winLinesShown) { spineStage.addBaseBehindAll(winLinesInst); winLinesShown = true; }
  return true;
}

function hideSpineWinLines() {
  if (!winLinesInst) return;
  winLinesInst.animationState.clearTracks();
  winLinesInst.skeleton.setToSetupPose();
  if (winLinesShown && spineStage) spineStage.removeBase(winLinesInst);
  winLinesShown = false;
}

// One flash of the line: draw it, run the dash-in, resolve when it has played
// once. The caller owns the repeat cadence, exactly as with the Spine version.
function showWinLine(win) {
  if (win && win.payline && showSpineWinLines([win.payline])) {
    if (winLineSvg) { winLineSvg.remove(); winLineSvg = null; }
    return wait(WIN_PULSE_MS);
  }
  const positions = (win && win.positions) || [];
  const svg = positions.length >= 2 ? ensureWinLineSvg() : null;
  if (!svg) {
    hideWinLine();
    return Promise.resolve();
  }
  const gridEl = document.querySelector('.reel__grid');
  svg.setAttribute('viewBox', `0 0 ${gridEl.offsetWidth} ${gridEl.offsetHeight}`);

  const points = positions
    .slice()
    .sort((a, b) => a.col - b.col)
    .map(({ row, col }) => cellCentre(row, col))
    .filter(Boolean);
  if (points.length < 2) {
    hideWinLine();
    return Promise.resolve();
  }
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

  svg.innerHTML = '';
  // Two stacked strokes: a wide soft glow underneath, a bright core on top.
  for (const cls of ['win-line__glow', 'win-line__core']) {
    const path = document.createElementNS(WIN_LINE_NS, 'path');
    path.setAttribute('class', cls);
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  svg.classList.remove('is-playing');
  void svg.getBoundingClientRect(); // restart the CSS animation
  svg.classList.add('is-playing');

  return wait(WIN_PULSE_MS);
}

// Lone-line case only (playWinCells' single-group branch): repeats showWinLine
// on the same play-once/pause/repeat cadence the winning symbols use, so the
// line pulses in lockstep with their glow instead of drifting against it.
function previewWinLine(win) {
  if (winLineLoopTimeout) {
    clearTimeout(winLineLoopTimeout);
    winLineLoopTimeout = null;
  }
  const token = ++winLineToken;
  const playOnce = () => {
    showWinLine(win).then(() => {
      if (token !== winLineToken) return;
      winLineLoopTimeout = setTimeout(() => {
        winLineLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

function hideWinLine() {
  hideSpineWinLines();
  winLineToken += 1;
  if (winLineLoopTimeout) {
    clearTimeout(winLineLoopTimeout);
    winLineLoopTimeout = null;
  }
  if (!winLineSvg) return;
  winLineSvg.remove();
  winLineSvg = null;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomSymbolCode() {
  return FILLER_CODES[Math.floor(Math.random() * FILLER_CODES.length)];
}

// --- Cells ------------------------------------------------------------------
//
// Every cell is one <img>. Where the original swapped a Spine instance in over
// a hidden static tile, this game just toggles classes on the cell — so there
// is no `info.instance` anywhere below, and no canvas stage at all.

// No measured per-symbol offsets — every symbol was cut from the mockup on the
// same 127px component box (plus a common margin), so they already line up. A live override from Anim Lab's "Калибровать" still wins.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('great-uniqorn', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(code, mult = 1) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  cell.classList.toggle('is-multiplier', code === 'wild' && mult > 1);

  const img = document.createElement('img');
  img.alt = code;
  img.src = symbolSrc(code, mult);
  img.addEventListener('error', () => img.classList.add('is-missing'), { once: true });
  applyStaticContentOffset(img, code);
  cell.appendChild(img);

  // Kept (empty) so the shared calibration tooling still finds an anchor node.
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
      const mult = ATTRACT_MULTIPLIERS[`${row},${col}`] || 1;
      const { cell, img, anchor } = createCellNode(symbol, mult);
      stripEl.appendChild(cell);
      const info = { symbol, mult, cell, img, anchor, winLoopTimeout: null };
      cell.addEventListener('click', () => onCellClick(info));
      cellInfos[row * GRID_COLS + col] = info;
    }
  }
}

function clearCellAnimation(info) {
  info.winToken = (info.winToken || 0) + 1;
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  info.cell.classList.remove('is-winning', 'is-win-active', 'is-wild-squeeze', 'is-wild-pop');
  const spineInst = symbolSpines.get(info);
  if (spineInst) {
    if (!isPersistentSpine(info)) unmountSymbolSpine(info);
    else {
      const cur = spineInst.animationState.getCurrent(0);
      if (cur && cur.animation && cur.animation.name !== 'idle') spineInst.play('idle', true);
    }
  }
}

function teardownCellInstances() {
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  hideWinLine();
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    info.cell.style.opacity = '';
    clearCellAnimation(info);
    applySpineDim(info);
  }
}

function setCellSymbol(info, code, mult = 1) {
  clearCellAnimation(info);
  unmountSymbolSpine(info);
  info.symbol = code;
  info.mult = mult;
  info.cell.dataset.symbol = code;
  info.cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  info.cell.classList.toggle('is-multiplier', code === 'wild' && mult > 1);
  info.cell.style.opacity = '';
  info.img.src = symbolSrc(code, mult);
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);
  return Promise.resolve();
}

function playWinAnimationOnce(info) {
  const spineMs = playSymbolSpineWin(info);
  if (spineMs) return wait(spineMs);
  info.cell.classList.remove('is-winning');
  void info.cell.offsetWidth;
  info.cell.classList.add('is-winning');
  return wait(WIN_PULSE_MS).then(() => {
    info.cell.classList.remove('is-winning');
  });
}

function previewSymbolWin(info) {
  if (info.winLoopTimeout) {
    clearTimeout(info.winLoopTimeout);
    info.winLoopTimeout = null;
  }
  const token = (info.winToken = (info.winToken || 0) + 1);
  const playOnce = () => {
    playWinAnimationOnce(info).then(() => {
      if (token !== info.winToken) return;
      info.winLoopTimeout = setTimeout(() => {
        info.winLoopTimeout = null;
        playOnce();
      }, WIN_LOOP_PAUSE_MS);
    });
  };
  playOnce();
}

// Clicking a wild cell previews the multiplier reveal with a random variant;
// any other symbol loops its win animation.
function onCellClick(info) {
  if (info.symbol === 'wild') {
    const mult = WILD_MULTIPLIERS[Math.floor(Math.random() * WILD_MULTIPLIERS.length)];
    setCellSymbol(info, 'wild').then(() => revealWildMultiplier(info, mult));
  } else {
    previewSymbolWin(info);
  }
}

function setCellActive(info, active) {
  info.cell.classList.toggle('is-win-active', active);
  if (!active) info.cell.classList.remove('is-winning');
}

function setCellDimmed(info, dimmed) {
  info.cell.classList.toggle('is-dimmed', dimmed);
  applySpineDim(info);
}

let multiLineSequenceTimeout = null;
let multiLineToken = 0;

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
  syncPersistentSpines();
}

function buildWinGroups(lineWins, countWins) {
  return ReelMath.collectWinGroups(lineWins, countWins).map((positions) =>
    positions.map(({ row, col }) => cellInfos[row * GRID_COLS + col]).filter(Boolean),
  );
}

// The paying symbol of one win group (a line's own symbol; wilds count only
// when the line is all wilds) — for its melody, symWin_<code>.
function groupSymbol(infos) {
  const plain = infos.map((i) => i.symbol).find((c) => c !== 'wild');
  return plain || (infos[0] && infos[0].symbol) || null;
}

// Win presentation order lives in js/slot-flow.js (SlotFlow.presentWins): all
// winning cells together, then each line on its own; the first pass plays the
// line sound + the symbol's melody and resolves (big/mega/epic wait for it),
// later passes loop silently until the next spin.
function playWinCells(winningCells, lineWins, countWins) {
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  const allWinInfos = (winningCells || [])
    .map(({ row, col }) => cellInfos[row * GRID_COLS + col])
    .filter(Boolean);
  if (allWinInfos.length) { playHeroWin(); playLogoWin(); }
  const winSet = new Set(allWinInfos);
  for (const info of cellInfos) {
    if (info) setCellDimmed(info, allWinInfos.length > 0 && !winSet.has(info));
  }
  const groups = buildWinGroups(lineWins, countWins);
  const lines = lineWins || [];
  const token = multiLineToken;
  return SlotFlow.presentWins({
    groups,
    allInfos: allWinInfos,
    pauseMs: WIN_LOOP_PAUSE_MS,
    symbolOf: groupSymbol,
    isCurrent: () => token === multiLineToken,
    playPhase: (infos, index) => {
      // groups[i] < lineWins.length is lineWins[i] (count wins come after)
      const win = index >= 0 ? lines[index] : (groups.length === 1 && lines.length === 1 && !(countWins || []).length ? lines[0] : null);
      if (index === -1 && lines.length > 1 && showSpineWinLines(lines.map((l) => l.payline))) { /* every line at once */ }
      else if (win) showWinLine(win); else hideWinLine();
      const active = new Set(infos);
      for (const info of cellInfos) if (info) setCellDimmed(info, !active.has(info));
      for (const info of allWinInfos) setCellActive(info, active.has(info));
      return Promise.all(infos.map((info) => playWinAnimationOnce(info)));
    },
  });
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
  landSounds.reset();
  unmountAllSymbolSpines();
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
  // caller re-applies the last known grid. Bumping the generation also kills
  // a drop that hasn't started yet: a request that fails fast (e.g. "not
  // enough balance" on BUY BONUS) lands here before startReelLoop's two rAFs,
  // which would otherwise kick the drop off AFTER this reset and leave the
  // reels empty.
  reelLoopGeneration += 1;
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
  // Reels 1-4 each stop on their own note, the last on the closing chord.
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : `reelStop${colIndex + 1}`;
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
    })();
  });
}

// Landing sounds (js/slot-flow.js): the 1st / 2nd / 3rd+ burger rise, the
// wild has its own; reset on spin start.
const landSounds = SlotFlow.landing({ scatter: 'scatter', specials: { wild: 'wildLand' } });

function settleColumnCells(cellEls, col, finalCodes) {
  const tasks = [];
  landSounds.land(finalCodes);
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const img = cell.querySelector('img');
    const anchor = cell.querySelector('.reel__cell-anchor');
    const info = { symbol: code, mult: 1, cell, img, anchor, winLoopTimeout: null };
    cell.addEventListener('click', () => onCellClick(info));
    cellInfos[row * GRID_COLS + col] = info;
    // No landing squash: the product wants symbols to just settle (2026-11-04).
    tasks.push(setCellSymbol(info, code).then(() => {
      if (code === 'scatter') mountSymbolSpine(info, 'landing');
      else if (code === 'wild' && isFreeSpinsScreen()) mountSymbolSpine(info, 'idle');
    }));
  }
  return Promise.all(tasks);
}

// --- Spine symbols (the animator's export) ---------------------------------
//
// Every symbol has the animator's skeleton (uniqorn_presedent.zip ->
// scripts/great_uniqorn_designer_spine.py -> spine/d/<code>/), drawn on the
// shared #spineCanvas over its cell. Per the spec:
//   pay symbols  `win` 1.3 s — mounted only while they win, static PNG otherwise
//   WILD         `win` 1.3 s (its money shower lives in the `wild` skin only,
//                so on the x2..x9 skins the same clip plays without it —
//                scripts/great_uniqorn_fix_exports.py), `idle` looping
//                for the whole free-spins session
//   SCATTER      `landing` as its reel stops, `idle` looping on the grid,
//                `win` 1.7 s
// The skeleton's setup pose is the static art, so swapping PNG <-> skeleton
// is seamless. spine/d/fit.json gives each skeleton's box in cell units (our
// PNGs are the animator's statics at 3x). The static PNG stays in the cell,
// hidden while the skeleton covers it, and comes back whenever the skeleton
// can't run (no WebGL, failed load) or the reels spin off.
const SYMBOL_SPINE_DIR = `${ASSET_ROOT}/spine/d`;
const SYMBOL_SPINE_VERSION = '12';
const SYMBOL_SPINE_CODES = ['a', 'j', 'k', 'q', 'hair', 'docs', 'jet', 'wild', 'scatter'];
const SYMBOL_SPINE_WIN_MS = { scatter: 1700, default: 1300 };
let symbolFit = null;
const symbolResources = {};
const symbolSpines = new Map(); // info -> SpineInstance

function loadSymbolResources() {
  const stage = ensureSpineStage();
  if (!stage) return Promise.resolve(null);
  return fetch(`${SYMBOL_SPINE_DIR}/fit.json?v=${SYMBOL_SPINE_VERSION}`)
    .then((r) => r.json())
    .then((fit) => {
      symbolFit = fit;
      return Promise.all(SYMBOL_SPINE_CODES.map((code) =>
        SpineEngine.SpineResource.load(stage.assetManager, `${SYMBOL_SPINE_DIR}/${code}`, { version: SYMBOL_SPINE_VERSION })
          .then((res) => { symbolResources[code] = res; })
          .catch((err) => console.warn(`${code} skeleton unavailable, static PNG stays:`, err))));
    })
    .catch((err) => { console.warn('symbol skeletons unavailable, static PNGs stay:', err); return null; });
}

function isFreeSpinsScreen() {
  return document.getElementById('screen').dataset.mode === 'freespins';
}

// Scatters always carry their skeleton; wilds only during free spins (idle).
function isPersistentSpine(info) {
  return info.symbol === 'scatter' || (info.symbol === 'wild' && isFreeSpinsScreen());
}

function symbolSpineAnchor(info, fit) {
  let el = info.cell.querySelector('.reel__cell-spine');
  if (!el) {
    el = document.createElement('div');
    el.className = 'reel__cell-spine';
    info.cell.appendChild(el);
  }
  Object.assign(el.style, { left: `${fit.left}px`, top: `${fit.top}px`, width: `${fit.width}px`, height: `${fit.height}px` });
  return el;
}

const wildSkin = (info) => (info.mult > 1 ? `x${info.mult}` : 'wild');

// anim: clip to start; it loops if it's `idle`, otherwise plays once and hands
// over to `idle` (scatter, free-spins wild) or ends on the setup pose.
function mountSymbolSpine(info, anim) {
  unmountSymbolSpine(info);
  const res = symbolResources[info.symbol];
  const fit = symbolFit && symbolFit[info.symbol];
  if (!res || !fit || !spineStage || !res.skeletonData.findAnimation(anim)) return null;
  const inst = res.createInstance();
  if (info.symbol === 'wild') {
    inst.skeleton.setSkinByName(wildSkin(info));
    inst.skeleton.setSlotsToSetupPose();
  }
  inst.anchorEl = symbolSpineAnchor(info, fit);
  inst.fit = 1;
  if (anim === 'idle') inst.play('idle', true);
  else {
    inst.play(anim, false);
    if (isPersistentSpine(info) && res.skeletonData.findAnimation('idle')) inst.queue('idle', true);
  }
  spineStage.addBase(inst);
  info.img.style.visibility = 'hidden';
  symbolSpines.set(info, inst);
  applySpineDim(info);
  return inst;
}

function unmountSymbolSpine(info) {
  if (info.spineOffTimer) { clearTimeout(info.spineOffTimer); info.spineOffTimer = null; }
  const inst = symbolSpines.get(info);
  if (!inst) return;
  symbolSpines.delete(info);
  if (spineStage) spineStage.removeBase(inst);
  if (info.img) info.img.style.visibility = '';
}

function unmountAllSymbolSpines() {
  for (const info of [...symbolSpines.keys()]) unmountSymbolSpine(info);
}

// Plays the symbol's win clip; resolves its length in ms, or 0 when the symbol
// has no skeleton (the caller then runs the CSS pulse).
function playSymbolSpineWin(info) {
  const res = symbolResources[info.symbol];
  if (!res) return 0;
  const clip = 'win';
  const ms = SYMBOL_SPINE_WIN_MS[info.symbol] || SYMBOL_SPINE_WIN_MS.default;
  const inst = symbolSpines.get(info);
  if (inst && isPersistentSpine(info)) {
    inst.play(clip, false).queue('idle', true);
    return ms;
  }
  if (!mountSymbolSpine(info, clip)) return 0;
  // a pay symbol goes back to its static PNG once the clip ends (= setup pose)
  info.spineOffTimer = setTimeout(() => {
    info.spineOffTimer = null;
    if (!isPersistentSpine(info)) unmountSymbolSpine(info);
  }, ms);
  return ms;
}

// Scatter idle / free-spins wild idle on every cell that should carry one.
function syncPersistentSpines() {
  for (const info of cellInfos) {
    if (!info) continue;
    const has = symbolSpines.has(info);
    if (isPersistentSpine(info)) { if (!has) mountSymbolSpine(info, 'idle'); }
    else if (has && !info.spineOffTimer) unmountSymbolSpine(info);
  }
}

function applySpineDim(info) {
  const inst = symbolSpines.get(info);
  if (inst) inst.skeleton.color.a = info.cell.classList.contains('is-dimmed') ? 0.32 : 1;
}

// Base skeletons (the symbols) live on the same canvas as the popups and the
// full-screen intro screens, above the DOM dim — so they follow the dim by
// hand: tinted under a popup's dim, gone under the opaque blackout and the
// Spine screens.
function refreshSpineBase() {
  if (!spineStage) return;
  spineStage.baseHidden = opaqueDimActiveCount > 0 || spineScreenOpen || winLayerHidden;
  spineStage.setBaseDim(dimActiveCount > 0);
  for (const info of symbolSpines.keys()) applySpineDim(info);
  refreshLogoSpine();
}

// --- Spine logo (scripts/great_uniqorn_logo_fx.py) ---------------------------
//
// `idle` loops all the time; `win` plays on every winning spin, then idle
// again. It is anchored to the .logo picture (hidden while the skeleton runs,
// back if it can't), so every layout's logo placement still applies. It is an
// OVERLAY of the shared stage — the win-layer guard hides the base skeletons
// under a popup and the logo must stay — dimmed by hand with the screen dim,
// gone under the blackout and the full-screen Spine screens, and drawn under
// the popups (they are added after it).
const LOGO_SPINE_DIR = `${ASSET_ROOT}/spine/logo`;
const LOGO_SPINE_VERSION = '1';
let logoInst = null;

function initLogoSpine() {
  const stage = ensureSpineStage();
  const img = document.querySelector('.logo');
  if (!stage || !img) return Promise.resolve();
  return SpineEngine.SpineResource.load(stage.assetManager, LOGO_SPINE_DIR, { version: LOGO_SPINE_VERSION })
    .then((res) => {
      logoInst = res.createInstance();
      logoInst.anchorEl = img;
      logoInst.fit = 1;
      logoInst.play('idle', true);
      stage.addOverlay(logoInst);
      img.style.visibility = 'hidden';
      refreshLogoSpine();
    })
    .catch((err) => console.warn('logo skeleton unavailable, the picture stays:', err));
}

function playLogoWin() {
  if (!logoInst) return;
  const cur = logoInst.animationState.getCurrent(0);
  if (cur && cur.animation && cur.animation.name === 'win' && !cur.isComplete()) return;
  logoInst.play('win', false).queue('idle', true);
}

function refreshLogoSpine() {
  if (!logoInst) return;
  const c = logoInst.skeleton.color;
  const hidden = opaqueDimActiveCount > 0 || spineScreenOpen;
  const k = dimActiveCount > 0 ? 0.35 : 1; // the screen dim's darkness
  c.r = k; c.g = k; c.b = k;
  c.a = hidden ? 0 : 1;
}

// --- Wild -> multiplier ----------------------------------------------------
//
// Every WILD rolls its multiplier server-side (app/features/multiplier_wild.py)
// and the spin response lists each one in `multiplier_wilds` ({row, col,
// multiplier}, 1 = stayed a plain WILD). A wild always LANDS as the plain WILD
// art; once its reel has stopped, the ones that rolled x2+ squeeze into a
// flash, swap to their xN art and pop back out — so the transform reads as an
// event on the grid, not as a different symbol having landed.
const WILD_SQUEEZE_MS = 220;
const WILD_POP_MS = 460;

async function revealWildMultiplier(info, mult) {
  if (!info || !WILD_MULTIPLIERS.includes(mult)) return;
  const { cell } = info;
  unmountSymbolSpine(info); // the squeeze/pop runs on the PNG
  cell.classList.remove('is-wild-pop');
  void cell.offsetWidth;
  cell.classList.add('is-wild-squeeze');
  Sound.playSfx('wildGrow');
  await wait(WILD_SQUEEZE_MS);
  info.mult = mult;
  info.img.src = symbolSrc('wild', mult);
  cell.classList.add('is-multiplier');
  cell.classList.remove('is-wild-squeeze');
  void cell.offsetWidth;
  cell.classList.add('is-wild-pop');
  await wait(WILD_POP_MS);
  cell.classList.remove('is-wild-pop');
  if (info.symbol === 'wild' && isFreeSpinsScreen() && !symbolSpines.has(info)) mountSymbolSpine(info, 'idle');
}

// Multipliers rolled on one column, keyed by row.
function columnMultipliers(multiplierWilds, col) {
  const byRow = {};
  for (const w of multiplierWilds || []) {
    if (w.col === col && Number(w.multiplier) > 1) byRow[w.row] = Number(w.multiplier);
  }
  return byRow;
}

function revealColumnMultipliers(col, multiplierWilds) {
  const byRow = columnMultipliers(multiplierWilds, col);
  const tasks = Object.entries(byRow).map(([row, mult]) => {
    const info = cellInfos[Number(row) * GRID_COLS + col];
    return info && info.symbol === 'wild' ? revealWildMultiplier(info, mult) : null;
  });
  return Promise.all(tasks);
}

// Columns from firstAnticipationCol onward land ONE AT A TIME, never in
// parallel: product ("не должны одновременно крутиться все оставшиеся
// барабаны") wants a single reel revealed, then the next, and so on.
// collectAnticipationColumns only flags a column while the trigger is still
// undecided, so once one of them lands the deciding symbol, later columns
// fall out of the flagged set on their own — those just land at normal
// speed, still one at a time, since the suspense is already resolved.
async function landReels(grid, anticipationColumns = [], multiplierWilds = []) {
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
        .then(() => revealColumnMultipliers(col, multiplierWilds)),
    );
  }
  await Promise.all(leadTasks);

  if (firstAnticipationCol === GRID_COLS) return;

  const anticipation = SlotFlow.anticipation();
  let anticipationResolved = false;
  const lastAnticipated = Math.max(...anticipationColumns);

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
    if (isAnticipating && !anticipationResolved) {
      // hit = the trigger burger landed on an anticipated reel; miss = the
      // last anticipated reel stopped without one
      const hit = finalCodes.includes('scatter');
      if (hit || col === lastAnticipated) { anticipation.resolve(hit); anticipationResolved = true; }
    }
    await settleColumnCells(cellEls, col, finalCodes);
    await revealColumnMultipliers(col, multiplierWilds);
  }
  if (!anticipationResolved) anticipation.resolve(false);
}

// --- Screen dim -------------------------------------------------------------

let dimActiveCount = 0;
let opaqueDimActiveCount = 0;

function pushScreenDim(opaque = false) {
  dimActiveCount += 1;
  document.getElementById('screenDim').classList.add('is-active');
  // The control bar lives outside the stage (fixed, above it) — dim it along
  // with the scene, as on the mockup's popup frames.
  document.body.classList.add('is-screen-dimmed');
  if (opaque) {
    opaqueDimActiveCount += 1;
    // Opaque dim = the base<->bonus mode transition. The original also had to
    // tint the Spine canvas by hand, because #screenDim (a DOM element) could
    // not darken canvas content without also covering the popup drawn on it.
    // Everything here is DOM, so the popup simply sits above #screenDim in the
    // stacking order and the one class does the whole job.
    document.getElementById('screenDim').classList.add('is-opaque');
  }
  refreshSpineBase();
}

function popScreenDim(opaque = false) {
  dimActiveCount = Math.max(0, dimActiveCount - 1);
  if (dimActiveCount === 0) {
    document.getElementById('screenDim').classList.remove('is-active');
    document.body.classList.remove('is-screen-dimmed');
  }
  if (opaque) {
    opaqueDimActiveCount = Math.max(0, opaqueDimActiveCount - 1);
    if (opaqueDimActiveCount === 0) {
      document.getElementById('screenDim').classList.remove('is-opaque');
    }
  }
  refreshSpineBase();
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
  syncPersistentSpines(); // free-spins wilds idle, base-game wilds go static
  updateBgForLayout();
  document.getElementById('slotBg').src = `${ASSET_ROOT}/img/${next === 'freespins' ? 'slotbg_bonus' : 'slotbg_base'}.png`;
}

// How long the "you won the bonus" popup holds on the blackout before the
// bonus screen is revealed behind it (product: ~3s of popup, then reveal).
const BONUS_INTRO_HOLD_MS = 3000;

// Bonus entry / exit order lives in js/slot-flow.js (rule 6): scatter pass ->
// YOU WON over the base game -> blackout (the light doesn't come back in
// between) -> bonus mode + bonus music -> the Spine bonus screen (tap) ->
// reveal. These are the game's primitives.
const bonusSteps = {
  dimMs: DIM_TRANSITION_MS,
  dimIn: (opaque) => pushScreenDim(opaque),
  dimOut: (opaque) => popScreenDim(opaque),
  popup: (amount) => playPopupSequence('bonusSpinsWin', amount, 2500, { ownDim: false, bought: gameState.boughtBonus }),
  switchMode: (mode) => applyModeScreen(mode),
  preview: (spins) => showBonusScreen(spins),
};

function setFreeSpinsMode(active, amount = 0, entry = {}) {
  const next = active ? 'freespins' : 'base';
  if (document.getElementById('screen').dataset.mode === next) return Promise.resolve();
  if (next === 'freespins') return SlotFlow.enterBonus(bonusSteps, { spins: amount, popupAmount: entry.popupAmount, withPopup: !!entry.withPopup });
  return SlotFlow.exitBonus(bonusSteps);
}

// --- Popups -----------------------------------------------------------------

// Thousands split with spaces, as on the mockup's plates («1 000 000 USD»).
function formatPopupAmount(n) {
  return Math.round(Number(n)).toLocaleString('en-US').replace(/,/g, '\u00a0');
}

// --- Spine popups -------------------------------------------------------------
//
// One shared WebGL canvas (#spineCanvas) over the whole scene. A popup's
// skeleton is anchored to its DOM frame (.game-popup, the mockup's 780x1416
// popup frame) — the skeleton is authored on exactly that frame (origin at its
// centre), so fit=1 + these bounds put every layer where the mockup has it.
const POPUP_SPINE_VERSION = '10';
const POPUP_FRAME_BOUNDS = { x: -390, y: -708, width: 780, height: 1416 };
// How long a popup may wait for its skeleton before falling back to the PNG.
const POPUP_SPINE_WAIT_MS = 1500;
let spineStage = null;

function ensureSpineStage() {
  if (spineStage) return spineStage;
  if (!window.spine || !window.SpineEngine) return null;
  try {
    spineStage = new SpineEngine.SpineStage(document.getElementById('spineCanvas'));
  } catch (err) {
    console.warn('Spine popups unavailable, using the flat PNGs:', err);
    spineStage = null;
  }
  return spineStage;
}

function popupSpineFolder(cfg, bought) {
  const name = bought && cfg.boughtSpine ? cfg.boughtSpine : cfg.spine;
  return `${ASSET_ROOT}/popups/${name}_${isMobileLayout() ? 'mob' : 'desk'}`;
}

function loadPopupResource(folder) {
  const stage = ensureSpineStage();
  if (!stage) return Promise.reject(new Error('no spine stage'));
  return SpineEngine.SpineResource.load(stage.assetManager, folder, {
    premultipliedAlpha: true, // the kit writes PMA atlases
    version: POPUP_SPINE_VERSION,
  });
}

// Resolves to the resource, or null if it isn't ready in time / failed.
function popupResourceOrNull(folder) {
  return Promise.race([loadPopupResource(folder).catch(() => null), wait(POPUP_SPINE_WAIT_MS).then(() => null)]);
}

function mountPopupSpine(resource, node) {
  const inst = resource.createInstance();
  inst.anchorEl = node;
  inst.fit = 1;
  inst.boundsOverride = POPUP_FRAME_BOUNDS;
  // start = the popup appearing, idle = the loop while the amount counts up,
  // end = the popup closing (scripts/great_uniqorn_popups.py)
  inst.play('start', false);
  inst.queue('idle', true);
  spineStage.addOverlay(inst);
  return inst;
}

// Closes the skeleton with its own `end` clip (mixed in from wherever idle
// is), alongside the DOM frame's opacity transition.
const POPUP_END_MS = 550;
const POPUP_END_MIX_S = 0.15;
function playPopupEnd(inst) {
  const entry = inst.animationState.setAnimation(0, 'end', false);
  entry.mixDuration = POPUP_END_MIX_S;
  return wait(POPUP_END_MS + 40).finally(() => spineStage && spineStage.removeOverlay(inst));
}

// Thousands split with spaces, as on the mockup's plates («1 000 000 USD»).
function formatPopupAmount(n) {
  return Math.round(Number(n)).toLocaleString('en-US').replace(/,/g, '\u00a0');
}

// Built fresh per showing rather than kept around: a popup is on screen for a
// couple of seconds a few times a session, so there is nothing to cache, and a
// node that isn't in the DOM can't leave a stale amount behind. `withArt`
// adds the flat PNG (fallback when there is no skeleton).
function buildPopupNode(key, amount, { bought = false, withArt = false } = {}) {
  const cfg = POPUP_CONFIG[key];
  const root = document.createElement('div');
  root.className = `game-popup is-${cfg.kind} ${withArt ? 'is-static' : 'is-spine'}`;

  if (withArt) {
    const art = document.createElement('img');
    art.className = 'game-popup__art';
    art.src = `${ASSET_ROOT}/img/${bought && cfg.boughtArt ? cfg.boughtArt : cfg.art}.png`;
    art.alt = '';
    root.appendChild(art);
  }

  const amountEl = document.createElement('div');
  amountEl.className = 'game-popup__amount';
  if (cfg.kind === 'spins') {
    amountEl.textContent = String(amount);
  } else {
    const value = document.createElement('span');
    value.className = 'game-popup__value';
    value.textContent = formatPopupAmount(0);
    const cur = document.createElement('span');
    cur.className = 'game-popup__cur';
    cur.textContent = (typeof gameState !== 'undefined' && gameState.currency) || 'FUN';
    amountEl.append(value, cur);
  }
  root.appendChild(amountEl);
  return root;
}

// Win amounts count up from zero while the popup is on screen (after
// `delayMs` — the skeleton's plate pops in first).
const POPUP_COUNT_UP_MS = 1100;
function countUpPopupAmount(node, amount, delayMs = 0) {
  const value = node.querySelector('.game-popup__value');
  if (!value) return;
  const start = performance.now() + delayMs;
  // The count-up loop runs for exactly as long as the number does, then its
  // end sound (js/slot-flow.js countSound: countLoop / countEnd).
  let counter = null;
  const tick = (now) => {
    if (!node.isConnected) {
      if (counter) counter.end();
      return;
    }
    const t = Math.max(0, Math.min(1, (now - start) / POPUP_COUNT_UP_MS));
    if (t > 0 && !counter) counter = SlotFlow.countSound();
    const eased = 1 - Math.pow(1 - t, 3);
    value.textContent = formatPopupAmount(amount * eased);
    if (t < 1) requestAnimationFrame(tick);
    else if (counter) counter.end();
  };
  requestAnimationFrame(tick);
}

// Shrinks the amount until it fits its plate (a 9-digit win in FUN is wider
// than the mockup's «1 000 000 USD»). offsetWidth, not getBoundingClientRect:
// this runs while the popup still carries its scale-in transform.
function fitPopupText(node, amount) {
  const el = node.querySelector('.game-popup__amount');
  const value = node.querySelector('.game-popup__value');
  if (!el || !value) return;
  value.textContent = formatPopupAmount(amount); // measure at the final width
  let size = parseFloat(getComputedStyle(el).fontSize);
  const limit = el.clientWidth;
  for (let i = 0; i < 24 && el.scrollWidth > limit && size > 12; i += 1) {
    size *= 0.92;
    el.style.fontSize = `${size}px`;
  }
  value.textContent = formatPopupAmount(0);
}

// Core popup lifecycle (in -> hold -> out). The returned promise resolves only
// once the popup has FULLY played out, so a caller can sequence work after it.
// `ownDim` lets a caller that already owns the screen dim (the bonus intro
// below) borrow the popup without it pushing/popping its own dim.
// Each popup's fanfare (played by the popup itself, as js/slot-flow.js expects).
const POPUP_SOUNDS = { bigWin: 'bigWin', megaWin: 'megaWin', epicWin: 'epicWin', bonusSpinsTotalWin: 'bonusTotalWin' };

// Layer guard (js/slot-flow.js rule 8): the win layer — symbol skeletons and
// the win line — is not drawn under a popup.
let winLayerHidden = false;
const winLayer = SlotFlow.layerGuard((visible) => {
  winLayerHidden = !visible;
  const line = document.querySelector('.win-line');
  if (line) line.style.visibility = visible ? '' : 'hidden';
  refreshSpineBase();
});

function playPopupSequence(key, amount = 0, holdMs = 2500, { ownDim = true, opaque = false, bought = false } = {}) {
  if (!POPUP_CONFIG[key]) return Promise.resolve();

  return new Promise((resolve) => {
    // Every exit goes through ONE finish(), guaranteed to run — on the normal
    // path, on any error, and on a safety timeout. The dim goes up before the
    // popup is built, so anything that throws in between must not be able to
    // leave the screen dimmed forever with no popup on it.
    let node = null;
    let inst = null;
    let dimmed = false;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(safetyTimer);
      if (node) node.remove();
      if (inst && spineStage) spineStage.removeOverlay(inst);
      if (dimmed) popScreenDim(opaque);
      winLayer.show();
      resolve();
    };
    const safetyTimer = setTimeout(finish, holdMs + 8000);
    winLayer.hide(); // nothing of the win shows through a popup (rule 8)

    (async () => {
      const cfg = POPUP_CONFIG[key];
      // Start fetching the skeleton while the dim fades in.
      const resourcePromise = popupResourceOrNull(popupSpineFolder(cfg, bought));
      Sound.playSfx('popupOpen');
      if (POPUP_SOUNDS[key]) Sound.playSfx(POPUP_SOUNDS[key]); // the popup plays its own fanfare
      if (ownDim) {
        pushScreenDim(opaque);
        dimmed = true;
        await wait(DIM_TRANSITION_MS);
      }
      const resource = await resourcePromise;

      node = buildPopupNode(key, amount, { bought, withArt: !resource });
      document.getElementById('stageTop').appendChild(node);
      fitPopupText(node, amount);
      if (resource) inst = mountPopupSpine(resource, node);
      void node.offsetWidth; // commit the pre-enter state before transitioning
      node.classList.add('is-in');
      countUpPopupAmount(node, amount, resource ? POPUP_AMOUNT_DELAY_MS : 0);

      await wait(POPUP_ENTER_MS + holdMs);
      Sound.playSfx('popupClose');
      node.classList.remove('is-in');
      node.classList.add('is-out');
      if (inst) await playPopupEnd(inst);
      else await wait(POPUP_EXIT_MS);
      inst = null;
      finish();
    })().catch((err) => {
      console.error(`popup "${key}" failed — closing it so the screen isn't left dimmed:`, err);
      finish();
    });
  });
}

// Win-tier / dev popups: own their (partial) screen dim, as before.
function playPopup(key, amount = 0, holdMs = 2500, { bought = false } = {}) {
  return playPopupSequence(key, amount, holdMs, { ownDim: true, bought });
}

// --- Dev panel --------------------------------------------------------------

// DEV / ♪ — the shared dev panel lives in js/great-uniqorn/dev.js.
function setupDevPanel() {}

// --- Stage layout -----------------------------------------------------------
//
// The scene is the mockup frame itself (.stage, 1932x940 desktop / 780x1416
// portrait) scaled as one piece:
//   desktop   fit the frame's SAFE area — the mockup marks 160px strips on
//             both sides ("bg rect left/right") as croppable — into the
//             viewport, centred; whatever is left over shows .bg-fill.
//   portrait  fit the frame's width, pinned to the top; the phone is taller
//             than the frame, and .bg-fill (cover, bottom-aligned) is the
//             background there.
const DESK_W = 1932;
const DESK_H = 940;
const DESK_SAFE_W = 1612;
// Desktop arrangement: the bigger frame on the right, the logo over the hero
// (the former variant 2 — the only one kept, 2026-11-23; #screen carries
// data-layout="2", which css/great-uniqorn.css keys it on). The bigger frame
// reaches x≈1800 and the logo starts at x≈118, past the mockup's 160px
// croppable strips, so more of the frame stays on screen.
const LAYOUT_SAFE_W = 1712;
const MOB_W = 780;
const MOB_H = 1416;

function isMobileLayout() {
  return window.matchMedia('(orientation: portrait)').matches;
}

function layoutStage() {
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const root = document.documentElement.style;
  let s, x, y;
  if (isMobileLayout()) {
    // Width-bound, but never so tall that the BUY BONUS plate (bottom at
    // 701 of 1416) slides under the control bar on a short, wide phone.
    s = Math.min(vw / MOB_W, (vh * 0.62) / 701);
    x = (vw - MOB_W * s) / 2;
    y = 0;
  } else {
    s = Math.min(vw / LAYOUT_SAFE_W, vh / DESK_H);
    x = (vw - DESK_W * s) / 2;
    y = (vh - DESK_H * s) / 2;
  }
  root.setProperty('--stage-s', String(s));
  root.setProperty('--stage-x', `${x}px`);
  root.setProperty('--stage-y', `${y}px`);
  // Viewport height in stage units — the portrait popup is placed against it.
  root.setProperty('--view-h', `${vh / s}px`);
  coverSceneBg();
  setTimeout(coverSceneBg, 340); // layouts move the bg layer with a 300ms transition
}

function bgSrcFor(mode) {
  const bonus = mode === 'freespins';
  if (isMobileLayout()) {
    // with the animated hero on top, the room without him (product, 2026-11-23)
    if (!bonus && mobileHeroReady('base')) return `${ASSET_ROOT}/img/bg_mob_base_room.jpg`;
    return `${ASSET_ROOT}/img/${bonus ? 'bg_mob_bonus' : 'bg_mob_base'}.jpg`;
  }
  return `${ASSET_ROOT}/img/${bonus ? 'bg_desk_bonus' : 'bg_desk_base'}.jpg`;
}

function updateBgForLayout() {
  const src = bgSrcFor(document.getElementById('screen').dataset.mode || 'base');
  for (const id of ['bgLayer', 'bgFill']) {
    const el = document.getElementById(id);
    if (!el.src.endsWith(src)) el.src = src;
  }
  updateSceneSpine();
}

// --- Spine scene: the animator's background + hero (desktop) ---------------
//
// bg_base/bg_bonus (1932x940, the scene's own frame — origin at its centre)
// and hero/hero_bonus loop `idle` on their own SpineStage (#bgCanvas, under
// #stage). Their anchors live in #bgSpineWrap, a .stage__bg twin, so layouts
// 1/2/3 move them exactly like the background picture. The hero's (0,0) is the
// centre of its static.png, which sits in the animator's Horizontal View at
// (0,314) / (163,233) (found by template search). Portrait keeps the picture
// backgrounds: the animator's scene is landscape only.
const SCENE_SPINE_DIR = `${ASSET_ROOT}/spine/d`;
const SCENE_SPINE = {
  base: { bg: 'bg_base', hero: 'hero', heroCenter: [452.5, 627] },
  freespins: { bg: 'bg_bonus', hero: 'hero_bonus', heroCenter: [369.5, 565] },
};
let sceneStage = null;
const sceneInsts = {}; // mode -> { bg, hero, heroBox }
let sceneShown = null;
let sceneMode = null; // the mode whose hero is on screen (desktop or portrait)

function initSceneSpine() {
  const canvas = document.getElementById('bgCanvas');
  if (!canvas || !window.SpineEngine || !window.spine) return Promise.resolve();
  try { sceneStage = new SpineEngine.SpineStage(canvas); } catch (err) { console.warn('scene Spine unavailable:', err); return Promise.resolve(); }
  const load = (name) => SpineEngine.SpineResource.load(sceneStage.assetManager, `${SCENE_SPINE_DIR}/${name}`, { version: SYMBOL_SPINE_VERSION });
  return Promise.all(Object.entries(SCENE_SPINE).map(async ([mode, cfg]) => {
    try {
      const [bgRes, heroRes] = await Promise.all([load(cfg.bg), load(cfg.hero)]);
      const bg = bgRes.createInstance();
      bg.anchorEl = document.getElementById('bgAnchor');
      bg.fit = 1;
      bg.play('idle', true);
      const hero = heroRes.createInstance();
      const b = heroRes.bounds;
      const [cx, cy] = cfg.heroCenter;
      hero.fit = 1;
      hero.play('idle', true);
      sceneInsts[mode] = { bg, hero, heroBox: { left: cx + b.x, top: cy - (b.y + b.height), width: b.width, height: b.height } };
    } catch (err) {
      console.warn(`scene skeletons for ${mode} unavailable, picture background stays:`, err);
    }
  })).then(() => updateBgForLayout()); // picks the hero-less mobile room once the hero is in
}

// The hero's `win` plays on track 1 over his idle whenever a spin wins,
// mixed in and out so idle carries on beneath:
//   base       scripts/great_uniqorn_hero_win.py — pops his bubble gum, grins
//              at the slot, shows his fist, taps his hoof
//   freespins  scripts/great_uniqorn_hero_bonus_win.py — a victory drag on the
//              cigar, a big cloud of smoke, tail swishes, a pleased bounce
const HERO_WIN_MIX = 0.25;
function playHeroWin() {
  const set = sceneMode && sceneInsts[sceneMode];
  if (!set) return;
  const st = set.hero.animationState;
  const data = set.hero.resource.skeletonData;
  if (!data.findAnimation('win')) return;
  const cur = st.getCurrent(1);
  if (cur && cur.animation && cur.animation.name === 'win' && !cur.isComplete()) return;
  st.setEmptyAnimation(1, 0);
  st.addAnimation(1, 'win', false, 0).mixDuration = HERO_WIN_MIX;
  st.addEmptyAnimation(1, 0.35, 0);
}

// The animated background covers the whole window, not just the 1932x940
// stage: on a window taller (or wider) than the stage the picture background
// left letterbox bands with only the blurred .bg-fill in them. The bg
// skeleton's anchor is scaled up (cover) around the viewport centre, in the
// coordinates of #bgSpineWrap (so a layout's transform of the bg layer still
// applies); the hero keeps the stage's own placement. The art is exactly the
// stage frame (a mask clips it there), so cover — not extra art — fills it.
function coverSceneBg() {
  if (sceneMode && isMobileLayout()) placeMobileHero(sceneMode);
  const wrap = document.getElementById('bgSpineWrap');
  const el = document.getElementById('bgAnchor');
  if (!wrap || !el) return;
  const r = wrap.getBoundingClientRect();
  if (!r.width) return;
  const s = r.width / DESK_W;
  const vw = window.innerWidth / s;
  const vh = window.innerHeight / s;
  const k = Math.max(vw / DESK_W, vh / DESK_H, 1);
  const w = DESK_W * k;
  const h = DESK_H * k;
  Object.assign(el.style, {
    left: `${-r.left / s + vw / 2 - w / 2}px`,
    top: `${-r.top / s + vh / 2 - h / 2}px`,
    width: `${w}px`,
    height: `${h}px`,
  });
}

// Portrait: the picture background stays (bg-fill: cover, bottom-aligned) and
// only the hero is animated, on the hero-less room bg_mob_base_room.jpg. His
// place on the 780x1416 mobile frame: static.png at x1.09 with its top-left at
// (-150, 720) — matched by eye to the old bg_mob_base.jpg, which had him drawn
// in. The bonus has no hero-less mobile art yet, so it keeps its picture.
const MOB_HERO = { base: { scale: 1.09, center: [-150 + 905 * 1.09 / 2, 720 + 626 * 1.09 / 2] } };
const MOB_W_FRAME = 780;
const MOB_H_FRAME = 1416;
const mobileHeroReady = (mode) => !!(MOB_HERO[mode] && sceneInsts[mode]);

function placeMobileHero(mode) {
  const set = sceneInsts[mode];
  const cfg = MOB_HERO[mode];
  const el = document.getElementById('heroAnchorMob');
  if (!set || !cfg || !el) return;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const S = Math.max(vw / MOB_W_FRAME, vh / MOB_H_FRAME); // the bg-fill's cover scale
  const left0 = (vw - MOB_W_FRAME * S) / 2;
  const top0 = vh - MOB_H_FRAME * S;                       // bottom-aligned
  const b = set.hero.resource.bounds;
  const k = cfg.scale * S;
  const [cx, cy] = cfg.center;
  Object.assign(el.style, {
    left: `${left0 + cx * S + b.x * k}px`,
    top: `${top0 + cy * S - (b.y + b.height) * k}px`,
    width: `${b.width * k}px`,
    height: `${b.height * k}px`,
  });
}

function updateSceneSpine() {
  if (!sceneStage) return;
  const mode = document.getElementById('screen').dataset.mode === 'freespins' ? 'freespins' : 'base';
  const mobile = isMobileLayout();
  const set = !mobile && sceneInsts[mode];
  const mob = mobile && mobileHeroReady(mode) ? sceneInsts[mode] : null;
  const key = set ? mode : mob ? `mob:${mode}` : null;
  document.getElementById('screen').classList.toggle('has-scene-spine', !!set);
  document.getElementById('screen').classList.toggle('has-scene-hero-mob', !!mob);
  coverSceneBg();
  setTimeout(coverSceneBg, 340); // after the layouts' 300ms bg transition
  if (mob) placeMobileHero(mode);
  if (sceneShown === key) return;
  for (const s of Object.values(sceneInsts)) { sceneStage.removeBase(s.bg); sceneStage.removeBase(s.hero); }
  sceneShown = key;
  sceneMode = set || mob ? mode : null;
  if (mob) {
    mob.hero.anchorEl = document.getElementById('heroAnchorMob');
    mob.hero.play('idle', true);
    sceneStage.addBase(mob.hero);
    return;
  }
  if (!set) return;
  const heroEl = document.getElementById('heroAnchor');
  Object.assign(heroEl.style, { left: `${set.heroBox.left}px`, top: `${set.heroBox.top}px`, width: `${set.heroBox.width}px`, height: `${set.heroBox.height}px` });
  set.hero.anchorEl = heroEl;
  set.bg.play('idle', true);
  set.hero.play('idle', true);
  sceneStage.addBase(set.bg);
  sceneStage.addBase(set.hero);
}

// --- Feature preview / bonus screens -------------------------------------------
//
// Spine skeletons generated by scripts/great_uniqorn_screens.py from the game's
// own art: `intro` (3s) then `idle` (looped) until a tap, then a 500ms fade.
// Authored on the design canvas (desk 1932x940 / mob 780x1416, origin at the
// centre) and fitted (contain) into the full-screen #featureScreen layer, which
// shows the game's own background under the canvas and catches the tap. Same
// contract as Multi Fruits Story / Neon Reels.
const SCREEN_ROOT = `${ASSET_ROOT}/screens`;
const SCREEN_VERSION = '7';
const SCREEN_BOX = {
  desk: { x: -966, y: -470, width: 1932, height: 940 },
  mob: { x: -390, y: -708, width: 780, height: 1416 },
};
const SCREEN_FADE_MS = 500;
// Bonus screen: the round badge spins in at 0.9-1.5s of intro; the spin count
// then counts up inside it. Font size in skeleton units (badge inner ~200).
const SCREEN_COUNT_AT = 1.4;
const SCREEN_COUNT_UP_S = 0.6;
const SCREEN_COUNT_UNITS = { desk: 150, mob: 130 };
// The bonus screen closes itself if nobody taps, so an unattended session
// (or autoplay) can't stall on it.
const BONUS_SCREEN_AUTOCLOSE_MS = 10000;
let spineScreenOpen = false;

function screenVariant() {
  return isMobileLayout() ? 'mob' : 'desk';
}

function getScreenResource(kind, variant = screenVariant()) {
  const stage = ensureSpineStage();
  if (!stage) return Promise.reject(new Error('no spine stage'));
  return SpineEngine.SpineResource.load(stage.assetManager, `${SCREEN_ROOT}/${kind}_${variant}`, {
    premultipliedAlpha: true, // the kit writes PMA atlases
    version: SCREEN_VERSION,
  });
}

function worldToScreen(wx, wy, canvasEl) {
  const rect = canvasEl.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  return { left: rect.left + (wx + canvasEl.width / 2) / dpr, top: rect.top + (canvasEl.height / 2 - wy) / dpr };
}

// Resolves true once the screen was shown and closed, false if it couldn't
// run at all (so the caller can fall back).
function showSpineScreen(kind, { bgMode = 'base', onFrame = null, autoCloseMs = 0 } = {}) {
  const root = document.getElementById('featureScreen');
  const stage = ensureSpineStage();
  if (!stage || !root || spineScreenOpen) return Promise.resolve(false);
  spineScreenOpen = true;
  return getScreenResource(kind).then((resource) => new Promise((resolve) => {
    let variant = screenVariant();
    let inst = null;
    let alpha = 1;
    let done = false;
    let closing = false;
    let autoTimer = null;

    // (Re)mount for the current orientation; `fromEntry` carries the clip and
    // time over when the device is rotated mid-screen.
    const mount = (res, fromEntry) => {
      const next = res.createInstance();
      next.anchorEl = root;
      next.fit = 1;
      next.boundsOverride = SCREEN_BOX[variant];
      if (fromEntry && fromEntry.animation) {
        const entry = next.animationState.setAnimation(0, fromEntry.animation.name, fromEntry.loop);
        entry.trackTime = fromEntry.trackTime;
        if (!fromEntry.loop) next.queue('idle', true);
      } else {
        next.play('intro', false);
        next.queue('idle', true);
      }
      next.skeleton.color.a = alpha;
      if (inst) stage.removeOverlay(inst);
      inst = next;
      stage.addOverlay(inst);
    };
    // Absolute URL: a url() inside a custom property resolves against the
    // stylesheet that uses it (css/), not the page.
    const setBg = () => root.style.setProperty('--fs-bg', `url("${new URL(bgSrcFor(bgMode), location.href).href}")`);
    const onResize = () => {
      setBg();
      const v = screenVariant();
      if (v === variant || closing) return;
      variant = v;
      const entry = inst.animationState.getCurrent(0);
      getScreenResource(kind, v).then((res) => { if (!done) mount(res, entry); }).catch(() => {});
    };

    setBg();
    mount(resource, null);
    window.addEventListener('resize', onResize);
    document.body.classList.add('is-feature-screen');
    refreshSpineBase();
    root.hidden = false;
    void root.offsetWidth;
    root.classList.add('is-open');

    const frame = () => {
      if (done) return;
      if (onFrame) onFrame(inst, alpha, variant);
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);

    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(autoTimer);
      stage.removeOverlay(inst);
      window.removeEventListener('resize', onResize);
      root.hidden = true;
      root.style.transition = '';
      document.body.classList.remove('is-feature-screen');
      spineScreenOpen = false;
      refreshSpineBase();
      resolve(true);
    };
    const close = () => {
      if (closing) return;
      closing = true;
      clearTimeout(autoTimer);
      root.removeEventListener('click', close);
      Sound.playSfx('click');
      // Skeleton alpha and the DOM layer fade together; the clip keeps
      // playing underneath so nothing freezes mid-fade.
      root.style.transition = `opacity ${SCREEN_FADE_MS}ms ease-out`;
      root.classList.remove('is-open');
      const start = performance.now();
      const tick = (now) => {
        if (done) return;
        const t = Math.min(1, (now - start) / SCREEN_FADE_MS);
        alpha = 1 - t;
        inst.skeleton.color.a = alpha;
        if (t < 1) requestAnimationFrame(tick);
        else finish();
      };
      requestAnimationFrame(tick);
      setTimeout(finish, SCREEN_FADE_MS + 200); // hidden tab: rAF frozen
    };
    root.addEventListener('click', close);
    if (autoCloseMs) autoTimer = setTimeout(close, autoCloseMs);
  })).catch((err) => {
    console.warn(`${kind} screen failed:`, err);
    spineScreenOpen = false;
    document.body.classList.remove('is-feature-screen');
    refreshSpineBase();
    root.hidden = true;
    return false;
  });
}

function showFeatureScreen() {
  return showSpineScreen('feature', { bgMode: 'base' });
}

function showBonusScreen(spins) {
  const el = document.getElementById('fscreenCount');
  const canvasEl = document.getElementById('spineCanvas');
  if (!el) return Promise.resolve(false);
  const total = Math.max(0, Number(spins) || 0);
  el.textContent = '0';
  el.style.opacity = '0';
  el.hidden = false;
  return showSpineScreen('bonus', {
    bgMode: 'freespins',
    autoCloseMs: BONUS_SCREEN_AUTOCLOSE_MS,
    onFrame: (inst, alpha, variant) => {
      const bone = inst.skeleton.findBone('count');
      if (!bone) return;
      const dpr = window.devicePixelRatio || 1;
      const pos = worldToScreen(bone.worldX, bone.worldY, canvasEl);
      el.style.left = `${pos.left}px`;
      el.style.top = `${pos.top}px`;
      el.style.fontSize = `${(SCREEN_COUNT_UNITS[variant] * Math.hypot(bone.b, bone.d)) / dpr}px`;
      const entry = inst.animationState.getCurrent(0);
      const inIntro = entry && entry.animation && entry.animation.name === 'intro';
      const t = inIntro ? entry.trackTime : Infinity;
      const k = Math.max(0, Math.min(1, (t - SCREEN_COUNT_AT) / SCREEN_COUNT_UP_S));
      el.textContent = String(Math.round(total * k));
      el.style.opacity = t < SCREEN_COUNT_AT ? '0' : String(alpha);
    },
  }).then((ran) => {
    el.hidden = true;
    return ran;
  });
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
  // The xN arts swap in mid-reveal — a late fetch would flash an empty cell.
  for (const mult of WILD_MULTIPLIERS) tasks.push(track(preloadImage(symbolSrc('wild', mult))));
  for (const name of ['frame.png?v=2', 'slotbg_base', 'slotbg_bonus', 'logo.png?v=2', 'btn_buy.png?v=2', 'btn_fs']) {
    tasks.push(track(preloadImage(`${ASSET_ROOT}/img/${name.includes('.png') ? name : `${name}.png`}`)));
  }
  tasks.push(track(loadSymbolResources()));
  tasks.push(track(initSceneSpine()));
  tasks.push(track(initLogoSpine()));
  tasks.push(track(loadWinLines()));
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('freespins'))));
  // Popup skeletons are only needed later — warm this layout's six in the
  // background instead of holding the preloader on them.
  setTimeout(() => {
    for (const cfg of Object.values(POPUP_CONFIG)) {
      for (const bought of [false, true]) {
        if (bought && !cfg.boughtSpine) continue;
        loadPopupResource(popupSpineFolder(cfg, bought)).catch(() => {});
      }
    }
  }, 1500);
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
}

async function init() {
  await SlotCalibration.load(); // must resolve before buildReelGrid's applyStaticContentOffset
  Sound.playMusic('base');
  ensureSpineStage();
  layoutStage();
  updateBgForLayout();
  window.addEventListener('resize', () => {
    layoutStage();
    updateBgForLayout();
  });

  buildReelGrid();
  setupDevPanel();

  await preloadAssets();
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol, info.mult)));
  syncPersistentSpines();

  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos, showFeatureScreen, showBonusScreen, symbolSpines, mountSymbolSpine, unmountSymbolSpine, get logo() { return logoInst; }, playLogoWin };
  // ?nofs — dev/screenshot convenience: straight into the game.
  if (!new URLSearchParams(location.search).has('nofs')) showFeatureScreen();
}

init();
