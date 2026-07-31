const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  currentColumnCodes,
  buildLoopSequence,
  CELL_SIZE,
  CELL_GAP,
  ROW_STEP,
  GRID_EDGE_MARGIN,
  gridDimensions,
  FRAME_HOLE_INSET,
  BG_HOLE_INSET,
  frameSizeForGrid,
  STATIC_CONTENT_OFFSET,
  staticContentOffset,
  REEL_DESIGN_VIEWPORT_WIDTH,
  REEL_MIN_SCALE,
  viewportScale,
  reelColumnBleed,
  reelColumnFadeStops,
  collectWinGroups,
  mobileReelScale,
  fitScale,
  REEL_FIT_MIN_SCALE,
  collectAnticipationColumns,
} = require('../js/reel-math.js');

// --- currentColumnCodes -----------------------------------------------------

test('currentColumnCodes reads a column top-to-bottom in row-major order', () => {
  // 3 rows x 5 cols, row-major: index = row * cols + col
  const cellInfos = [
    { symbol: 'scatter' }, { symbol: 'duck' }, { symbol: 'watermelon' }, { symbol: 'corn' }, { symbol: 'blueberry' },
    { symbol: 'strawberry' }, { symbol: 'blueberry' }, { symbol: 'scatter' }, { symbol: 'strawberry' }, { symbol: 'wild' },
    { symbol: 'watermelon' }, { symbol: 'cow' }, { symbol: 'pear' }, { symbol: 'dog' }, { symbol: 'pear' },
  ];

  assert.deepEqual(currentColumnCodes(cellInfos, 5, 3, 0), ['scatter', 'strawberry', 'watermelon']);
  assert.deepEqual(currentColumnCodes(cellInfos, 5, 3, 2), ['watermelon', 'scatter', 'pear']);
  assert.deepEqual(currentColumnCodes(cellInfos, 5, 3, 4), ['blueberry', 'wild', 'pear']);
});

test('currentColumnCodes returns null for missing slots instead of throwing', () => {
  const sparse = [{ symbol: 'wild' }];
  assert.deepEqual(currentColumnCodes(sparse, 5, 3, 0), ['wild', null, null]);
});

test('currentColumnCodes works for non-default grid sizes', () => {
  const cellInfos = [
    { symbol: 'a' }, { symbol: 'b' },
    { symbol: 'c' }, { symbol: 'd' },
  ];
  assert.deepEqual(currentColumnCodes(cellInfos, 2, 2, 1), ['b', 'd']);
});

// --- buildLoopSequence -------------------------------------------------------
//
// This is the reel-spin-start bug fix: the animation must scroll away from
// whatever is currently on screen, not pop straight to random filler. That
// only holds if the *current* symbols are the first ones in the strip
// (translateY(0) resting position renders index 0..2 — see slot.js startReelLoop).

test('buildLoopSequence puts the current symbols first, filler after', () => {
  const current = ['scatter', 'wild', 'duck'];
  const filler = ['corn', 'pear', 'cow'];
  const sequence = buildLoopSequence(current, filler);

  assert.deepEqual(sequence.slice(0, 3), current, 'current symbols must be first — no abrupt swap on spin start');
  assert.deepEqual(sequence.slice(3), filler);
  assert.equal(sequence.length, 6);
});

test('buildLoopSequence does not mutate its inputs', () => {
  const current = ['scatter', 'wild', 'duck'];
  const filler = ['corn', 'pear', 'cow'];
  buildLoopSequence(current, filler);
  assert.deepEqual(current, ['scatter', 'wild', 'duck']);
  assert.deepEqual(filler, ['corn', 'pear', 'cow']);
});

// --- Anticipation (free-spins trigger suspense) -----------------------------

test('collectAnticipationColumns flags only the last reel when the earlier columns land exactly one short of the trigger', () => {
  const grid = [
    ['scatter', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'scatter', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
  ];
  assert.deepEqual(collectAnticipationColumns(grid, 5, 3, 'scatter', 3), [4]);
});

test('collectAnticipationColumns is empty once the trigger is already secured before the last reel', () => {
  // All 3 needed scatters land in column 0 alone — no suspense left for the
  // last reel, the trigger already happened earlier in the spin.
  const grid = [
    ['scatter', 'duck', 'duck', 'duck', 'duck'],
    ['scatter', 'duck', 'duck', 'duck', 'duck'],
    ['scatter', 'duck', 'duck', 'duck', 'duck'],
  ];
  assert.deepEqual(collectAnticipationColumns(grid, 5, 3, 'scatter', 3), []);
});

test('collectAnticipationColumns is empty when the trigger symbol never appears', () => {
  const grid = [
    ['duck', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
  ];
  assert.deepEqual(collectAnticipationColumns(grid, 5, 3, 'scatter', 3), []);
});

test('collectAnticipationColumns still flags the last reel on a spin that ends up a near-miss (does not actually trigger)', () => {
  // Only 2 scatters land before the last reel, and the last reel itself
  // (col 4) has no scatter either — the suspense was genuine but it misses.
  // The function only looks at counts *before* the last column, so it
  // flags it regardless of what the last column turns out to hold.
  const grid = [
    ['scatter', 'duck', 'scatter', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
  ];
  assert.deepEqual(collectAnticipationColumns(grid, 5, 3, 'scatter', 3), [4]);
});

test('collectAnticipationColumns with trigger_count 1 flags the last reel only if nothing landed before it', () => {
  const noneYet = [
    ['duck', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
  ];
  assert.deepEqual(collectAnticipationColumns(noneYet, 5, 3, 'scatter', 1), [4]);

  const alreadyLanded = [
    ['duck', 'duck', 'scatter', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
    ['duck', 'duck', 'duck', 'duck', 'duck'],
  ];
  assert.deepEqual(collectAnticipationColumns(alreadyLanded, 5, 3, 'scatter', 1), []);
});

// --- Fixed-pixel grid layout -------------------------------------------------
//
// Each cell is a 200x200 *layout slot* with a 10px gap — symbols render at
// their own asset-native size inside it, uncropped/unscaled (product
// direction: "не масштабируем, используем такие же как и в оригинале") —
// replaced the earlier percentage-of-viewport responsive grid entirely.

test('CELL_SIZE/CELL_GAP/ROW_STEP match the agreed spacing', () => {
  assert.equal(CELL_SIZE, 200);
  assert.equal(CELL_GAP, 10);
  assert.equal(ROW_STEP, CELL_SIZE + CELL_GAP);
});

test('gridDimensions computes total grid size from cell size + gaps', () => {
  // 5 cols: 5 cells + 4 gaps between them. 3 rows: 3 cells + 2 gaps.
  const grid = gridDimensions(5, 3);
  assert.equal(grid.width, 5 * CELL_SIZE + 4 * CELL_GAP);
  assert.equal(grid.height, 3 * CELL_SIZE + 2 * CELL_GAP);
  assert.equal(grid.width, 1040);
  assert.equal(grid.height, 620);
});

test('gridDimensions handles a single row/column (no internal gaps)', () => {
  assert.deepEqual(gridDimensions(1, 1), { width: CELL_SIZE, height: CELL_SIZE });
});

test('frameSizeForGrid scales the frame up so its inner opening exactly contains the grid plus edge margin', () => {
  const grid = gridDimensions(5, 3);
  const frame = frameSizeForGrid(grid.width, grid.height);

  // Inverting the math: shrinking the frame back down by its own hole
  // insets must reproduce the grid size plus the edge margin exactly —
  // the margin is deliberate breathing room for native-size symbols that
  // exceed the 200px slot (e.g. static.png's 220x220 canvas).
  const impliedWidth = frame.width * (1 - FRAME_HOLE_INSET.left - FRAME_HOLE_INSET.right);
  const impliedHeight = frame.height * (1 - FRAME_HOLE_INSET.top - FRAME_HOLE_INSET.bottom);

  assert.ok(Math.abs(impliedWidth - (grid.width + GRID_EDGE_MARGIN)) < 1e-9);
  assert.ok(Math.abs(impliedHeight - (grid.height + GRID_EDGE_MARGIN)) < 1e-9);
});

test('frameSizeForGrid with edgeMargin=0 reproduces the grid size exactly', () => {
  const grid = gridDimensions(5, 3);
  const frame = frameSizeForGrid(grid.width, grid.height, 0);
  const impliedWidth = frame.width * (1 - FRAME_HOLE_INSET.left - FRAME_HOLE_INSET.right);
  const impliedHeight = frame.height * (1 - FRAME_HOLE_INSET.top - FRAME_HOLE_INSET.bottom);
  assert.ok(Math.abs(impliedWidth - grid.width) < 1e-9);
  assert.ok(Math.abs(impliedHeight - grid.height) < 1e-9);
});

// --- CSS regression: fixed sizing constants match style.css -----------------

const GRID_COLS_FOR_TEST = 5;
const GRID_ROWS_FOR_TEST = 3;

function readCss() {
  return fs.readFileSync(path.join(__dirname, '../css/style.css'), 'utf8');
}

test(':root --cell-size / --cell-gap match reel-math.js', () => {
  const css = readCss();
  assert.match(css, new RegExp(`--cell-size:\\s*${CELL_SIZE}px`));
  assert.match(css, new RegExp(`--cell-gap:\\s*${CELL_GAP}px`));
});

test(':root --reel-frame-w/h match ReelMath.frameSizeForGrid for the 5x3 grid', () => {
  const css = readCss();
  const grid = gridDimensions(GRID_COLS_FOR_TEST, GRID_ROWS_FOR_TEST);
  const frame = frameSizeForGrid(grid.width, grid.height);

  const widthMatch = css.match(/--reel-frame-w:\s*(\d+)px/);
  const heightMatch = css.match(/--reel-frame-h:\s*(\d+)px/);
  assert.ok(widthMatch && heightMatch, '--reel-frame-w/h not found in style.css');

  assert.ok(Math.abs(Number(widthMatch[1]) - frame.width) < 1, `expected ~${frame.width}px, got ${widthMatch[1]}px`);
  assert.ok(Math.abs(Number(heightMatch[1]) - frame.height) < 1, `expected ~${frame.height}px, got ${heightMatch[1]}px`);
});

test('.reel__grid inset matches the measured frame-hole fractions exactly (symbols must land precisely in the hole)', () => {
  const css = readCss();
  const match = css.match(/\.reel__grid\s*{[^}]*inset:\s*([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%/);
  assert.ok(match, '.reel__grid 4-value inset rule not found');

  const [, top, right, bottom, left] = match.map(Number);
  const expected = {
    top: FRAME_HOLE_INSET.top * 100,
    right: FRAME_HOLE_INSET.right * 100,
    bottom: FRAME_HOLE_INSET.bottom * 100,
    left: FRAME_HOLE_INSET.left * 100,
  };

  for (const [side, value] of Object.entries({ top, right, bottom, left })) {
    assert.ok(
      Math.abs(value - expected[side]) < 0.05,
      `${side}: expected ~${expected[side].toFixed(3)}%, got ${value}%`,
    );
  }
});

test('.reel__bg inset matches BG_HOLE_INSET (deliberately larger than the grid, to cover the frame\'s soft inner-braid edge)', () => {
  const css = readCss();
  const match = css.match(/\.reel__bg\s*{[^}]*inset:\s*([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%/);
  assert.ok(match, '.reel__bg 4-value inset rule not found');

  const [, top, right, bottom, left] = match.map(Number);
  const expected = {
    top: BG_HOLE_INSET.top * 100,
    right: BG_HOLE_INSET.right * 100,
    bottom: BG_HOLE_INSET.bottom * 100,
    left: BG_HOLE_INSET.left * 100,
  };

  for (const [side, value] of Object.entries({ top, right, bottom, left })) {
    assert.ok(
      Math.abs(value - expected[side]) < 0.05,
      `${side}: expected ~${expected[side].toFixed(3)}%, got ${value}%`,
    );
  }
});

test('.reel__bg extends further out than .reel__grid on every side (backing covers more than just the hard content hole)', () => {
  assert.ok(BG_HOLE_INSET.top < FRAME_HOLE_INSET.top);
  assert.ok(BG_HOLE_INSET.right < FRAME_HOLE_INSET.right);
  assert.ok(BG_HOLE_INSET.bottom < FRAME_HOLE_INSET.bottom);
  assert.ok(BG_HOLE_INSET.left < FRAME_HOLE_INSET.left);
});

// --- Reel column scroll-clip bleed -------------------------------------
//
// Fix: during the spin animation, symbols scrolling in/out of the 3-row
// window were visibly clipped mid-shape against the plain dark backdrop.
// The clip mask (.reel__col) now bleeds beyond the window into the zone
// .reel__bg already extends into — covered by the frame's opaque wood — so
// symbols appear to emerge from / vanish under the frame instead.

test('.reel__col height/margin-top match ReelMath.reelColumnBleed(932) for the current frame height', () => {
  const css = readCss();
  const bleed = reelColumnBleed(932); // --reel-frame-h
  const total = bleed.top + bleed.bottom;

  const heightMatch = css.match(/\.reel__col\s*{[^}]*height:\s*calc\(100% \+ ([\d.]+)px\)/);
  const marginMatch = css.match(/\.reel__col\s*{[^}]*margin-top:\s*-([\d.]+)px/);
  const stripTopMatch = css.match(/\.reel__strip\s*{[^}]*top:\s*([\d.]+)px/);

  assert.ok(heightMatch, '.reel__col height: calc(100% + Npx) not found');
  assert.ok(marginMatch, '.reel__col margin-top not found');
  assert.ok(stripTopMatch, '.reel__strip top (in px) not found');

  assert.ok(Math.abs(Number(heightMatch[1]) - total) < 0.01, `expected total bleed ~${total}px, got ${heightMatch[1]}px`);
  assert.ok(Math.abs(Number(marginMatch[1]) - bleed.top) < 0.01, `expected top bleed ~${bleed.top}px, got ${marginMatch[1]}px`);
  assert.ok(Math.abs(Number(stripTopMatch[1]) - bleed.top) < 0.01, `.reel__strip top must equal the top bleed (compensates .reel__col's margin-top so the resting position is unaffected)`);
});

// --- Reel column bottom fade --------------------------------------------
//
// Fix: a symbol scrolling past row 3 could ride the full bottom bleed and
// briefly peek out under the frame's bottom edge (not fully opaque there).
// A short mask-image fade starting right at the row-3 boundary hides it
// faster than the hard clip — top bleed/behavior is untouched.

test('.reel__col mask-image fades out starting exactly at the row-3 boundary (top bleed + grid height)', () => {
  const css = readCss();
  const grid = gridDimensions(GRID_COLS_FOR_TEST, GRID_ROWS_FOR_TEST);
  const stops = reelColumnFadeStops(932, grid.height);

  const maskMatch = css.match(/\.reel__col\s*{[^}]*mask-image:\s*linear-gradient\(to bottom,\s*#000\s+([\d.]+)px,\s*transparent\s+([\d.]+)px\)/);
  assert.ok(maskMatch, '.reel__col mask-image linear-gradient not found');

  const [, opaqueEnd, transparentEnd] = maskMatch.map(Number);
  assert.ok(Math.abs(opaqueEnd - stops.opaqueEnd) < 0.01, `expected opaque-end ~${stops.opaqueEnd}px, got ${opaqueEnd}px`);
  assert.ok(Math.abs(transparentEnd - stops.transparentEnd) < 0.01, `expected transparent-end ~${stops.transparentEnd}px, got ${transparentEnd}px`);
  assert.ok(transparentEnd > opaqueEnd, 'fade must end after it starts');
});

// --- Multi-line win grouping -------------------------------------------------
//
// Feature: when more than one line/count-win hits on the same spin, the
// first win animation plays every winning cell together (dimming the rest),
// then repeats cycle through each line one at a time. `winning_cells` alone
// can't drive that (it's a deduped flat union) — `line_wins`/`count_wins`
// each carry their own `positions`, one group per win.

test('collectWinGroups returns one group per line_win/count_win, in order', () => {
  const lineWins = [
    { payline: 0, symbol: 'duck', count: 3, amount: 1000, positions: [{ row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }] },
    { payline: 4, symbol: 'pear', count: 4, amount: 2000, positions: [{ row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }, { row: 1, col: 3 }] },
  ];
  const countWins = [
    { symbol: 'scatter', count: 3, amount: 500, positions: [{ row: 0, col: 0 }, { row: 2, col: 2 }, { row: 1, col: 4 }] },
  ];

  const groups = collectWinGroups(lineWins, countWins);
  assert.equal(groups.length, 3);
  assert.deepEqual(groups[0], lineWins[0].positions);
  assert.deepEqual(groups[1], lineWins[1].positions);
  assert.deepEqual(groups[2], countWins[0].positions);
});

test('collectWinGroups skips wins with no positions and handles missing/empty inputs', () => {
  assert.deepEqual(collectWinGroups(undefined, undefined), []);
  assert.deepEqual(collectWinGroups([], []), []);
  assert.deepEqual(
    collectWinGroups([{ payline: 0, symbol: 'duck', count: 3, amount: 1000, positions: [] }], null),
    [],
  );
});

test('collectWinGroups treats a single line/count win as one group (feeds the "no dimming, single line" fallback)', () => {
  const groups = collectWinGroups(
    [{ payline: 0, symbol: 'duck', count: 3, amount: 1000, positions: [{ row: 0, col: 0 }] }],
    [],
  );
  assert.equal(groups.length, 1);
});

// --- Static-image content offset --------------------------------------------
//
// Bug fix: the win animation showed a one-time jump away from the static
// image on landing (repeats matched fine — those never involve the static
// image at all). Root cause: static.png's art isn't always centered on its
// own 220x220 canvas, while Spine bounds are always content-centered.

test('every symbol the frontend renders has a calibrated content offset', () => {
  const renderedSymbols = [
    'scatter', 'wild', 'duck', 'watermelon', 'corn',
    'blueberry', 'strawberry', 'cow', 'pear', 'dog',
  ];
  for (const code of renderedSymbols) {
    assert.ok(code in STATIC_CONTENT_OFFSET, `missing STATIC_CONTENT_OFFSET entry for "${code}"`);
  }
});

test('staticContentOffset returns the calibrated {dx, dy} for a known symbol', () => {
  assert.deepEqual(staticContentOffset('duck'), { dx: -5, dy: 10 });
  assert.deepEqual(staticContentOffset('blueberry'), { dx: -8, dy: 0 });
});

test('staticContentOffset defaults to {dx:0, dy:0} for an unknown symbol', () => {
  assert.deepEqual(staticContentOffset('not_a_real_symbol'), { dx: 0, dy: 0 });
});

test('content offsets are small corrections, not full re-centers (sanity bound)', () => {
  // A correct measurement should never need to shift by anywhere near half
  // the 220px canvas — that would indicate a measurement bug, not padding.
  for (const code of Object.keys(STATIC_CONTENT_OFFSET)) {
    const { dx, dy } = STATIC_CONTENT_OFFSET[code];
    assert.ok(Math.abs(dx) < 30, `${code} dx=${dx} looks too large to be padding correction`);
    assert.ok(Math.abs(dy) < 30, `${code} dy=${dy} looks too large to be padding correction`);
  }
});

// --- Responsive desktop scale -----------------------------------------------
//
// CSS-only `calc(100vw / 1920)` (length / length -> number) silently made
// the *entire* `transform` on .reel invalid in at least one real browser
// tested, dropping the centering translate along with the scale — this is
// why the scale is computed in JS and written into --reel-scale instead.

test('viewportScale is 1 (no shrink) at and above the design width', () => {
  assert.equal(viewportScale(REEL_DESIGN_VIEWPORT_WIDTH), 1);
  assert.equal(viewportScale(REEL_DESIGN_VIEWPORT_WIDTH + 500), 1);
});

test('viewportScale shrinks proportionally below the design width', () => {
  // Both comfortably above the 0.6 floor, so the ratio isn't clamped.
  assert.ok(Math.abs(viewportScale(1728) - 0.9) < 1e-9);
  assert.ok(Math.abs(viewportScale(1440) - 0.75) < 1e-9);
});

test('viewportScale never goes below the floor', () => {
  assert.equal(viewportScale(200), REEL_MIN_SCALE);
  assert.equal(viewportScale(0), REEL_MIN_SCALE);
});

test('viewportScale never divides by zero / mishandles a zero design width', () => {
  assert.ok(Number.isFinite(viewportScale(1000, 0)));
});

// --- Mobile (portrait) scale --------------------------------------------

test('mobileReelScale fills the viewport edge to edge (no shrink-to-floor)', () => {
  assert.ok(Math.abs(mobileReelScale(1372, 1372) - 1) < 1e-9);
  assert.ok(Math.abs(mobileReelScale(686, 1372) - 0.5) < 1e-9);
  assert.ok(Math.abs(mobileReelScale(390, 1372) - 390 / 1372) < 1e-9);
});

test('mobileReelScale never divides by zero / mishandles a missing frame width', () => {
  assert.ok(Number.isFinite(mobileReelScale(390, 0)));
  assert.ok(Number.isFinite(mobileReelScale(390, undefined)));
});

// --- Fullscreen fit scale (width+height constrained, no scroll) --------

test('fitScale picks the more constraining axis', () => {
  // Width is tighter here: (1000-0)/1000=1 vs (2000-0)/1000=2 -> width wins.
  assert.ok(Math.abs(fitScale(1000, 2000, 1000, 1000) - 1) < 1e-9);
  // Height is tighter here: (2000-0)/1000=2 vs (500-0)/1000=0.5 -> height wins.
  assert.ok(Math.abs(fitScale(2000, 500, 1000, 1000) - 0.5) < 1e-9);
});

test('fitScale accounts for reserved margins on each axis', () => {
  assert.ok(Math.abs(fitScale(1100, 2000, 1000, 1000, 100, 0) - 1) < 1e-9);
  assert.ok(Math.abs(fitScale(2000, 1100, 1000, 1000, 0, 100) - 1) < 1e-9);
});

test('fitScale never upscales past 1', () => {
  assert.equal(fitScale(5000, 5000, 1000, 1000), 1);
});

test('fitScale floors at REEL_FIT_MIN_SCALE (much lower than viewportScale\'s floor)', () => {
  assert.equal(fitScale(10, 10, 1000, 1000), REEL_FIT_MIN_SCALE);
  assert.ok(REEL_FIT_MIN_SCALE < REEL_MIN_SCALE);
});

test('fitScale never divides by zero / mishandles a missing frame size', () => {
  assert.ok(Number.isFinite(fitScale(1000, 1000, 0, 1000)));
  assert.ok(Number.isFinite(fitScale(1000, 1000, 1000, 0)));
});

// --- Inline win-amount stacking regression ----------------------------------
//
// Bug: .reel-win-amount was nested inside .reel with z-index:15, intended to
// beat #spineCanvas's z-index:5. But .reel itself has no z-index (auto), so
// .reel as a whole stacks below #spineCanvas in .screen's stacking context —
// the child z-index only ever competed against .reel's *other* children, never
// against the canvas. Win animations painted over the number. Fix: the
// win-amount viewport lives outside .reel, as a sibling of #spineCanvas, with
// its own z-index above it.

test('.reel-win-amount-viewport out-ranks .spine-canvas in z-index (so win animations never cover the number)', () => {
  const css = readCss();
  const viewportMatch = css.match(/\.reel-win-amount-viewport\s*{[^}]*z-index:\s*(\d+)/);
  const canvasMatch = css.match(/\.spine-canvas\s*{[^}]*z-index:\s*(\d+)/);
  assert.ok(viewportMatch, '.reel-win-amount-viewport z-index not found');
  assert.ok(canvasMatch, '.spine-canvas z-index not found');
  assert.ok(
    Number(viewportMatch[1]) > Number(canvasMatch[1]),
    `.reel-win-amount-viewport (z:${viewportMatch[1]}) must out-rank .spine-canvas (z:${canvasMatch[1]})`,
  );
});

test('index.html does not nest #reelWinAmount inside .reel (a non-z-indexed ancestor would trap it below #spineCanvas)', () => {
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  const reelOpenIdx = html.indexOf('<div class="reel">');
  const reelWinAmountIdx = html.indexOf('id="reelWinAmount"');
  assert.ok(reelOpenIdx >= 0 && reelWinAmountIdx >= 0, 'expected elements not found in index.html');

  // Find the matching close of the specific `<div class="reel">` by counting
  // nested <div> opens/closes from that point.
  let depth = 0;
  let i = reelOpenIdx;
  const divOpen = /<div\b/g;
  const divClose = /<\/div>/g;
  divOpen.lastIndex = reelOpenIdx;
  let closeIdx = -1;
  let cursor = reelOpenIdx;
  while (cursor < html.length) {
    const nextOpen = html.indexOf('<div', cursor + 1);
    const nextClose = html.indexOf('</div>', cursor);
    if (nextClose === -1) break;
    if (nextOpen !== -1 && nextOpen < nextClose) {
      depth++;
      cursor = nextOpen;
    } else {
      depth--;
      cursor = nextClose + 6;
      if (depth === 0) { closeIdx = nextClose; break; }
    }
  }
  assert.ok(closeIdx > reelOpenIdx, 'could not find the closing </div> for .reel');
  assert.ok(
    reelWinAmountIdx < reelOpenIdx || reelWinAmountIdx > closeIdx,
    '#reelWinAmount must not be inside .reel — .reel has no z-index of its own and stacks below #spineCanvas',
  );
});
