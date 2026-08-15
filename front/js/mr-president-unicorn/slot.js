// Mr. President Unicorn — adapted from ../wild-western-story/slot.js, which
// this game keeps the mechanics of: reel motion, win-cell sequencing, scatter
// anticipation, free-spins mode, inline win amount, expanding wild, buy bonus.
//
// The one structural difference: the original's art was a Spine export per
// symbol, and this game's art is AI-generated flat PNGs — there are no
// skeletons, atlases or clips anywhere. Everything the original animated
// through a skeleton is a DOM/CSS counterpart here:
//
//   symbol idle / win / landing  -> classes on .reel__cell (see the stylesheet)
//   win lines (11 baked clips)   -> an SVG polyline through the winning cells
//   expanding wild               -> a reel-height <img> with a CSS grow
//   popups (6 skeletons)         -> buildPopupNode(), a DOM plate + text


const ASSET_ROOT = 'img/mr-president-unicorn';

const SYMBOL_CODES = ['wild', 'scatter', 'burger', 'toilet', 'money', 'a', 'k', 'q', 'j'];

function symbolSrc(code) {
  return `${ASSET_ROOT}/symbols/${code}.png`;
}
const BIG_WILD_SRC = `${ASSET_ROOT}/symbols/wild_big.png`;

// --- Hero moods -------------------------------------------------------------
//
// The mascot beside the reels has three poses, each its own PNG plus its own
// CSS loop. All three were cut into one shared frame (same canvas, feet on the
// same baseline), so swapping the src never makes him jump or resize.
//
//   idle    presenting the reels    default
//   tense   braced, sweating        while a scatter anticipation is running
//   cheer   arms up, jumping        while a win is being paid out
const HERO_SRC = {
  idle: `${ASSET_ROOT}/img/hero.png`,
  tense: `${ASSET_ROOT}/img/hero_tense.png`,
  cheer: `${ASSET_ROOT}/img/hero_cheer.png`,
};
let heroMood = 'idle';

function setHeroMood(mood) {
  if (mood === heroMood) return;
  const el = document.querySelector('.hero');
  if (!el) return;
  heroMood = mood;
  el.src = HERO_SRC[mood] || HERO_SRC.idle;
  el.classList.remove('is-idle', 'is-tense', 'is-cheer');
  el.classList.add(`is-${mood}`);
}

// Codes eligible as random spin-loop filler — excludes scatter (a trigger
// symbol, shouldn't blur past as filler) and wild (it expands, so it must not
// flicker through the blur).
const FILLER_CODES = SYMBOL_CODES.filter((c) => c !== 'scatter' && c !== 'wild');

// wild and scatter idle permanently on the grid (a slow breathe/glow); every
// other symbol sits still until it wins. Purely a CSS class — see
// .reel__cell.is-special in the stylesheet.
const SPECIAL_SYMBOLS = new Set(['scatter', 'wild']);

// How long one win pulse runs, in sync with the CSS keyframes. The original
// resolved this from the Spine clip's own duration; with CSS we own both ends,
// so the two numbers just have to agree.
const WIN_PULSE_MS = 620;
const LAND_BOUNCE_MS = 260;
// Popup in/out durations — must match the .game-popup transitions.
const POPUP_ENTER_MS = 420;
const POPUP_EXIT_MS = 260;

// Attract-mode layout shown before the first real spin (also fixes the grid's
// 3 rows x 5 reels shape — no real backend game exists for this theme yet, so
// this placeholder is what renders until that's wired up).
const SYMBOL_LAYOUT = [
  ['scatter', 'burger', 'q', 'a', 'j'],
  ['a', 'k', 'wild', 'money', 'q'],
  ['q', 'toilet', 'k', 'j', 'burger'],
];
const GRID_ROWS = SYMBOL_LAYOUT.length;
const GRID_COLS = SYMBOL_LAYOUT[0].length;

// Popups are built in the DOM (see buildPopupNode): a generated plaque, a
// title and the amount. `sub` is the small line above the title.
//
// `plate` picks one of three generated plaques, and they are a deliberate
// ladder — each tier is visibly grander than the one below it, so the popup
// itself tells the player how big the win was before they read the number:
//
//   plate   art                                                    used by
//   base    gold cartouche, eagle, ribbons, light rays             big win, free spins, buy
//   mega    + gems, crown, laurels, coin shower, fireworks         mega win, total win
//   epic    jewelled medallion, crowned unicorn-eagle, columns,    epic win
//           velvet drapery, full firework burst
//
// Each plaque's empty panel sits in a different place (the epic one's is even
// circular), so the panel bounds live per plate in the stylesheet and the text
// is scaled to fit at runtime — see fitPopupText.
const POPUP_CONFIG = {
  bigWin: { title: 'BIG WIN', tone: 'gold', plate: 'base' },
  megaWin: { title: 'MEGA WIN', tone: 'gold', plate: 'mega' },
  epicWin: { title: 'EPIC WIN', tone: 'red', plate: 'epic' },
  bonusSpinsWin: { title: 'FREE SPINS', sub: 'YOU WON', tone: 'blue', plate: 'base', amountSuffix: ' SPINS' },
  bonusSpinsTotalWin: { title: 'TOTAL WIN', sub: 'FREE SPINS OVER', tone: 'gold', plate: 'mega' },
  buyFreeSpins: { title: 'BUY FREE SPINS', sub: 'CONFIRM PURCHASE', tone: 'blue', plate: 'base' },
};

const POPUP_PLATE_SRC = {
  base: 'popup_plate.png',
  mega: 'popup_plate_mega.png',
  epic: 'popup_plate_epic.png',
};

const DIM_TRANSITION_MS = 320;
const REEL_LAND_FILLER_COUNT = 14;
const REEL_LAND_DURATION_MS = 750;
const REEL_LAND_STAGGER_MS = 110;
const WIN_LOOP_PAUSE_MS = 500;

let cellInfos = [];
let reelCols = [];
// Reel-height "big wild" overlays currently on screen (see revealExpandedWild).
// Cleared at the start of every spin, same lifecycle as the small cell instances.
let expandedWildOverlays = [];

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
// computed from row/col arithmetic: the grid is CSS-scaled (updateReelScale)
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

// No measured per-symbol offsets — every generated symbol was normalised into
// the same square box with a common optical centre when it was cut, so they
// already line up. A live override from Anim Lab's "Калибровать" still wins.
function applyStaticContentOffset(img, code) {
  const override = window.SlotCalibration && window.SlotCalibration.get('mr-president-unicorn', code);
  const { dx, dy } = override || { dx: 0, dy: 0 };
  img.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`;
}

function createCellNode(code) {
  const cell = document.createElement('div');
  cell.className = 'reel__cell';
  cell.dataset.symbol = code;
  cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));

  const img = document.createElement('img');
  img.alt = code;
  img.src = symbolSrc(code);
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
      const { cell, img, anchor } = createCellNode(symbol);
      stripEl.appendChild(cell);
      const info = { symbol, cell, img, anchor, winLoopTimeout: null };
      cell.addEventListener('click', () => onCellClick(info, col));
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
  info.cell.classList.remove('is-winning', 'is-win-active', 'is-landing');
}

function teardownCellInstances() {
  setHeroMood('idle');
  multiLineToken += 1;
  if (multiLineSequenceTimeout) {
    clearTimeout(multiLineSequenceTimeout);
    multiLineSequenceTimeout = null;
  }
  hideWinLine();
  for (const overlay of expandedWildOverlays) overlay.remove();
  expandedWildOverlays = [];
  for (const info of cellInfos) {
    if (!info) continue;
    info.cell.classList.remove('is-dimmed');
    info.cell.style.opacity = '';
    clearCellAnimation(info);
  }
}

function setCellSymbol(info, code) {
  clearCellAnimation(info);
  info.symbol = code;
  info.cell.dataset.symbol = code;
  info.cell.classList.toggle('is-special', SPECIAL_SYMBOLS.has(code));
  info.cell.style.opacity = '';
  info.img.src = symbolSrc(code);
  info.img.classList.remove('is-missing');
  info.img.style.visibility = '';
  applyStaticContentOffset(info.img, code);
  return Promise.resolve();
}

// The little squash-and-settle a symbol does as its reel stops.
function playLandBounce(info) {
  if (!info) return;
  info.cell.classList.remove('is-landing');
  void info.cell.offsetWidth; // restart the keyframes
  info.cell.classList.add('is-landing');
  setTimeout(() => info.cell.classList.remove('is-landing'), LAND_BOUNCE_MS);
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
  // Also clears the tense pose an anticipation left behind when that
  // anticipation didn't actually pay.
  setHeroMood(allWinInfos.length > 0 ? 'cheer' : 'idle');

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
  // caller re-applies the last known grid.
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
  const stopSound = colIndex === GRID_COLS - 1 ? 'finalReelStop' : 'reelStop';
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

function settleColumnCells(cellEls, col, finalCodes) {
  const tasks = [];
  for (let row = 0; row < GRID_ROWS; row++) {
    const code = finalCodes[row];
    const cell = cellEls[row];
    const img = cell.querySelector('img');
    const anchor = cell.querySelector('.reel__cell-anchor');
    const info = { symbol: code, cell, img, anchor, winLoopTimeout: null };
    cell.addEventListener('click', () => onCellClick(info, col));
    cellInfos[row * GRID_COLS + col] = info;
    tasks.push(setCellSymbol(info, code).then(() => playLandBounce(info)));
  }
  return Promise.all(tasks);
}

// --- Expanding wild --------------------------------------------------------
//
// When a reel expands, a reel-height wild <img> grows over that whole column
// and the 3 small wild cells fade out underneath it. The original drove this
// with the wild skeleton's `move` -> `win_big`/`idle_big` clips; here the grow
// is a CSS transition and the winning state is a class.
const BIG_WILD_GROW_MS = 420;

function fadeCellsToTransparent(infos, durationMs) {
  const targets = infos.filter(Boolean);
  if (targets.length === 0) return Promise.resolve();
  for (const info of targets) {
    info.cell.style.transition = `opacity ${durationMs}ms ease`;
    info.cell.style.opacity = '0';
  }
  return wait(durationMs);
}

async function revealExpandedWild(col, { win = false } = {}) {
  const { colEl } = reelCols[col];
  const overlay = document.createElement('img');
  overlay.className = 'big-wild';
  overlay.src = BIG_WILD_SRC;
  overlay.alt = 'wild';
  colEl.appendChild(overlay);
  expandedWildOverlays.push(overlay);

  const fadeInfos = [0, 1, 2].map((row) => cellInfos[row * GRID_COLS + col]).filter(Boolean);
  const fadeDone = fadeCellsToTransparent(fadeInfos, 450);

  Sound.playSfx('wildGrow');
  void overlay.offsetWidth; // commit the pre-grow state before transitioning
  overlay.classList.add('is-grown');
  await wait(BIG_WILD_GROW_MS);
  await fadeDone;
  if (win) {
    Sound.playSfx('wildWin');
    overlay.classList.add('is-winning');
  }
  return overlay;
}

function celebrateExpandedWild(col, wildEvents, winningCols) {
  const grew = wildEvents.some((e) => e.reel === col && (e.event === 'expanded' || e.event === 'walked'));
  if (grew) return revealExpandedWild(col, { win: winningCols.has(col) });
  return Promise.resolve(null);
}

// Dev/testing preview (no backend yet to send real wild_events): turn a whole
// column to wild, grow the big wild over it, hold, then restore the column to
// the attract layout. Clicking a wild cell previews the winning expansion; the
// dev "Big Wild" button the idle one.
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
    overlay.remove();
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
  setHeroMood('tense');

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
  if (dimActiveCount === 0) document.getElementById('screenDim').classList.remove('is-active');
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

// Built fresh per showing rather than kept around: a popup is on screen for a
// couple of seconds a few times a session, so there is nothing to cache, and a
// node that isn't in the DOM can't leave a stale amount behind.
function buildPopupNode(key, amount) {
  const cfg = POPUP_CONFIG[key] || { title: key, tone: 'gold', plate: 'base' };
  const plate = cfg.plate || 'base';
  const root = document.createElement('div');
  root.className = `game-popup is-${cfg.tone} is-plate-${plate}`;
  if (isMobileLayout()) root.classList.add('is-mobile');

  // The plaque art is one generated PNG with a deliberately empty navy panel;
  // the text is DOM on top of it, positioned against that panel's measured
  // bounds (see --popup-panel-* in the stylesheet). Re-measure those if
  // popup_plate.png is ever regenerated.
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

// The three plaques have panels of different widths — and the epic one's is a
// circle — while titles run from "BIG WIN" to "BUY FREE SPINS". Rather than
// hand-tune a font size per plate/title pair, shrink each line until it fits
// its panel. Runs after the node is in the DOM so the panel has real bounds.
function fitPopupText(node) {
  const body = node.querySelector('.game-popup__body');
  if (!body) return;
  // Measure against the PANEL, not the line's own box: the body is a centred
  // flex column, so a nowrap line simply grows past its parent and its own
  // scrollWidth/clientWidth stay equal — it never looks overflowing to itself.
  const limit = body.clientWidth;
  for (const el of body.querySelectorAll('.game-popup__title, .game-popup__amount, .game-popup__sub')) {
    let size = parseFloat(getComputedStyle(el).fontSize);
    // 24 steps takes the longest title down to the narrowest panel; the floor
    // stops a pathological case from collapsing the text to nothing.
    for (let i = 0; i < 24 && el.getBoundingClientRect().width > limit && size > 8; i += 1) {
      size *= 0.92;
      el.style.fontSize = `${size}px`;
    }
  }
}

// Core popup lifecycle (in -> hold -> out). The returned promise resolves only
// once the popup has FULLY played out, so a caller can sequence work after it.
// `ownDim` lets a caller that already owns the screen dim (the bonus intro
// below) borrow the popup without it pushing/popping its own dim.
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
    return mode === 'base' ? `${ASSET_ROOT}/img/bg_base_mob.jpg` : `${ASSET_ROOT}/img/bg_bonus_mob.jpg`;
  }
  return mode === 'base' ? `${ASSET_ROOT}/img/bg_base.jpg` : `${ASSET_ROOT}/img/bg_bonus.jpg`;
}

function updateBgForLayout() {
  const screen = document.getElementById('screen');
  document.getElementById('bgLayer').src = bgSrcFor(screen.dataset.mode || 'base');
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
  tasks.push(track(preloadImage(BIG_WILD_SRC)));
  // All three hero poses up front: a mood swap mid-spin must not wait on a
  // network round trip, or he'd blink out at the exact moment he should react.
  for (const src of Object.values(HERO_SRC)) tasks.push(track(preloadImage(src)));
  tasks.push(track(preloadImage(bgSrcFor('base'))));
  tasks.push(track(preloadImage(bgSrcFor('bonus'))));
  for (const p of Sound.preloadPromises || []) tasks.push(track(p));

  return Promise.race([Promise.all(tasks), wait(PRELOAD_TIMEOUT_MS)]);
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
  setupDevPanel();

  await preloadAssets();
  await Promise.all(cellInfos.map((info) => setCellSymbol(info, info.symbol)));

  if (window.Preloader) window.Preloader.done();

  window.__slot = { cellInfos };
}

init();
