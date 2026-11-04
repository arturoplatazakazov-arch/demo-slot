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

function symbolSrc(code, mult = 1) {
  if (code === 'wild' && WILD_MULTIPLIERS.includes(mult)) return `${ASSET_ROOT}/symbols/x${mult}.png`;
  return `${ASSET_ROOT}/symbols/${code}.png`;
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
// of the free-spins popup. The free-spins round end has two arts — FREE SPINS
// TOTAL WIN for a round won from scatters, BONUS SPINS TOTAL WIN for a bought
// one (see app.js gameState.boughtBonus).
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
  bonusSpinsTotalWin: { art: 'pop_fstotal', boughtArt: 'pop_bstotal', spine: 'fstotal', boughtSpine: 'bstotal', kind: 'total' },
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

// One flash of the line: draw it, run the dash-in, resolve when it has played
// once. The caller owns the repeat cadence, exactly as with the Spine version.
function showWinLine(win) {
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
  }
}

function setCellSymbol(info, code, mult = 1) {
  clearCellAnimation(info);
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
}

let multiLineSequenceTimeout = null;
let multiLineToken = 0;

function playMultiLineWinSequence(groups, allWinInfos, lineWins) {
  const token = ++multiLineToken;
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
    if (win) showWinLine(win);
    else hideWinLine();
    playPhaseOnce(activeInfos).then(() => {
      if (token !== multiLineToken) return;
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
  multiLineToken += 1;
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
      previewWinLine(lineWins[0]);
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
  scatterLandCount = 0;
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

// Scatters landed so far this spin: the 1st/2nd/3rd each get their own,
// rising sound (scatter1..3). Reset by startReelLoop.
let scatterLandCount = 0;

function settleColumnCells(cellEls, col, finalCodes) {
  const tasks = [];
  const scatters = finalCodes.filter((c) => c === 'scatter').length;
  for (let i = 0; i < scatters && scatterLandCount < 3; i++) {
    scatterLandCount += 1;
    Sound.playSfx(`scatter${scatterLandCount}`);
  }
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const img = cell.querySelector('img');
    const anchor = cell.querySelector('.reel__cell-anchor');
    const info = { symbol: code, mult: 1, cell, img, anchor, winLoopTimeout: null };
    cell.addEventListener('click', () => onCellClick(info));
    cellInfos[row * GRID_COLS + col] = info;
    // No landing squash: the product wants symbols to just settle (2026-11-04).
    tasks.push(setCellSymbol(info, code));
  }
  return Promise.all(tasks);
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
    await revealColumnMultipliers(col, multiplierWilds);
  }
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
  updateBgForLayout();
  document.getElementById('slotBg').src = `${ASSET_ROOT}/img/${next === 'freespins' ? 'slotbg_bonus' : 'slotbg_base'}.png`;
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
  Sound.playSfx('bonusEnter');
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
  Sound.playSfx('bonusExit');

  return withScreenDim(
    async () => {
      applyModeScreen(next);
      await wait(DIM_TRANSITION_MS);
    },
    { opaque: true },
  );
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
const POPUP_SPINE_VERSION = '1';
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
  inst.play('intro', false);
  inst.queue('idle', true);
  spineStage.addOverlay(inst);
  return inst;
}

// Fades the skeleton out alongside the DOM frame's own opacity transition.
function fadeOutPopupSpine(inst, ms) {
  return new Promise((resolve) => {
    const start = performance.now();
    const tick = (now) => {
      const k = Math.min(1, (now - start) / ms);
      inst.skeleton.color.a = 1 - k;
      if (k < 1) requestAnimationFrame(tick);
      else resolve();
    };
    requestAnimationFrame(tick);
  }).finally(() => spineStage && spineStage.removeOverlay(inst));
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
  // The cash counter loops for exactly as long as the number runs.
  let stopCash = null;
  const tick = (now) => {
    if (!node.isConnected) {
      if (stopCash) stopCash();
      return;
    }
    const t = Math.max(0, Math.min(1, (now - start) / POPUP_COUNT_UP_MS));
    if (t > 0 && !stopCash) stopCash = Sound.startLoop('cashLoop');
    const eased = 1 - Math.pow(1 - t, 3);
    value.textContent = formatPopupAmount(amount * eased);
    if (t < 1) requestAnimationFrame(tick);
    else if (stopCash) stopCash();
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
      resolve();
    };
    const safetyTimer = setTimeout(finish, holdMs + 8000);

    (async () => {
      const cfg = POPUP_CONFIG[key];
      // Start fetching the skeleton while the dim fades in.
      const resourcePromise = popupResourceOrNull(popupSpineFolder(cfg, bought));
      Sound.playSfx('popupOpen');
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
      if (inst) await fadeOutPopupSpine(inst, POPUP_EXIT_MS);
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

function setupDevPanel() {
  const toggleBtn = document.getElementById('devToggle');

  toggleBtn.addEventListener('click', () => {
    const next = document.getElementById('screen').dataset.mode === 'base' ? 'freespins' : 'base';
    setFreeSpinsMode(next === 'freespins', 10); // demo spins count for the intro popup
    toggleBtn.textContent = `mode: ${next}`;
  });

  document.querySelectorAll('[data-popup]').forEach((btn) => {
    const key = btn.dataset.popup;
    const amount = key === 'bonusSpinsWin' ? 10 : 1234500;
    btn.addEventListener('click', () => playPopup(key, amount, 2500, { bought: btn.dataset.bought === '1' }));
  });
}

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
// Desktop layout variants (the «Варианты» switch): the horizontal span of the
// frame that must stay on screen. Variant 2's bigger frame reaches x≈1800
// and its logo starts at x≈118, past the mockup's 160px croppable strips.
const LAYOUT_SAFE_W = { 1: DESK_SAFE_W, 2: 1712, 3: DESK_SAFE_W };
const LAYOUT_KEY = 'great-uniqorn.layout';

function currentLayout() {
  return document.getElementById('screen').dataset.layout || '1';
}

function setLayoutVariant(v) {
  const next = ['1', '2', '3'].includes(String(v)) ? String(v) : '1';
  document.getElementById('screen').dataset.layout = next;
  document.querySelectorAll('#layoutSwitch [data-layout]').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.layout === next));
  });
  try { localStorage.setItem(LAYOUT_KEY, next); } catch (e) { /* private mode — fine */ }
  layoutStage();
}

function setupLayoutSwitch() {
  let saved = '1';
  try { saved = localStorage.getItem(LAYOUT_KEY) || '1'; } catch (e) { /* ignore */ }
  setLayoutVariant(saved);
  document.querySelectorAll('#layoutSwitch [data-layout]').forEach((b) => {
    b.addEventListener('click', () => {
      Sound.playSfx('click');
      setLayoutVariant(b.dataset.layout);
    });
  });
}
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
    s = Math.min(vw / (LAYOUT_SAFE_W[currentLayout()] || DESK_SAFE_W), vh / DESK_H);
    x = (vw - DESK_W * s) / 2;
    y = (vh - DESK_H * s) / 2;
  }
  root.setProperty('--stage-s', String(s));
  root.setProperty('--stage-x', `${x}px`);
  root.setProperty('--stage-y', `${y}px`);
  // Viewport height in stage units — the portrait popup is placed against it.
  root.setProperty('--view-h', `${vh / s}px`);
}

function bgSrcFor(mode) {
  const bonus = mode === 'freespins';
  if (isMobileLayout()) return `${ASSET_ROOT}/img/${bonus ? 'bg_mob_bonus' : 'bg_mob_base'}.jpg`;
  return `${ASSET_ROOT}/img/${bonus ? 'bg_desk_bonus' : 'bg_desk_base'}.jpg`;
}

function updateBgForLayout() {
  const src = bgSrcFor(document.getElementById('screen').dataset.mode || 'base');
  for (const id of ['bgLayer', 'bgFill']) {
    const el = document.getElementById(id);
    if (!el.src.endsWith(src)) el.src = src;
  }
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
  for (const name of ['frame', 'slotbg_base', 'slotbg_bonus', 'logo', 'btn_buy', 'btn_fs']) {
    tasks.push(track(preloadImage(`${ASSET_ROOT}/img/${name}.png`)));
  }
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
  setupLayoutSwitch();
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

  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
