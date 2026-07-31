// Pure helpers for reel-spin / grid-layout logic — no DOM or Spine access,
// so these are unit-testable directly under Node (see front/tests/).
// Exposed as `window.ReelMath` for the browser (loaded before slot.js) and
// as a CommonJS export for the test runner.

// Row-major lookup: cellInfos[row * gridCols + col].symbol for a given
// column, in row order (top to bottom). Falls back to `null` for a missing
// slot instead of throwing, so callers can decide how to backfill it.
function currentColumnCodes(cellInfos, gridCols, gridRows, col) {
  const codes = [];
  for (let row = 0; row < gridRows; row++) {
    const info = cellInfos[row * gridCols + col];
    codes.push(info ? info.symbol : null);
  }
  return codes;
}

// The loop strip's cell order: whatever's currently on screen first (so the
// spin-start animation scrolls *away* from the real result instead of
// popping straight to filler), then fresh random filler behind it.
function buildLoopSequence(currentCodes, randomCodes) {
  return [...currentCodes, ...randomCodes];
}

// --- Anticipation (free-spins trigger suspense) ------------------------------
//
// The full grid is already known (server-resolved) before the landing
// animation plays, so "anticipation" isn't guessed live — it's computed up
// front. Product (this session): suspense is reserved for the LAST reel
// only, never an earlier one, and only when it could still be the one that
// completes the trigger — i.e. every column *before* it landed exactly one
// short of the trigger threshold. If the trigger was already secured earlier
// (or could never be reached even with the last reel), the last reel just
// lands normally, no suspense. Threshold and symbol come from the backend
// (session-start's free_spins_trigger) — never hardcoded, since they're
// admin-configurable.
//
// `grid` is row-major (grid[row][col], matching the /spin response contract).
// Returns either [] (no suspense this spin) or [gridCols - 1] (the last reel).
function collectAnticipationColumns(grid, gridCols, gridRows, triggerSymbolCode, triggerCount) {
  const lastCol = gridCols - 1;
  let landedCount = 0;
  for (let col = 0; col < lastCol; col++) {
    for (let row = 0; row < gridRows; row++) {
      if (grid[row][col] === triggerSymbolCode) landedCount++;
    }
  }
  return landedCount === triggerCount - 1 ? [lastCol] : [];
}

// --- Multi-line win grouping -------------------------------------------------
//
// The backend's `winning_cells` is a single flat/deduped union across every
// winning line and count-win — it can't tell two simultaneous lines apart.
// `line_wins`/`count_wins` each carry their own `positions` ({row, col}[])
// though, so each entry *is* one group of cells that won together. Used to
// play every group at once on the first win animation, then cycle through
// them one at a time on repeats (see slot.js playMultiLineWinSequence).
function collectWinGroups(lineWins, countWins) {
  const groups = [];
  for (const win of [...(lineWins || []), ...(countWins || [])]) {
    if (win && win.positions && win.positions.length) groups.push(win.positions);
  }
  return groups;
}

// --- Fixed-pixel grid layout -------------------------------------------------
//
// Each cell is a 200x200 layout slot with a 10px gap to its neighbors.
// Symbols themselves render at their own asset-native size, uncropped and
// unscaled to that slot (static.png and the Spine skeletons were authored
// to already agree on size/centering — see slot.js for how each is
// centered on its cell independently of the 200px slot size).
const CELL_SIZE = 200;
const CELL_GAP = 10;
// Center-to-center distance between consecutive cells in the scrolling
// strip — the scroll-animation math (slot.js startReelLoop/landReel) moves
// the strip in units of this, not just CELL_SIZE, since the gap travels
// with it as one rigid flex column.
const ROW_STEP = CELL_SIZE + CELL_GAP;

function gridDimensions(cols, rows) {
  return {
    width: cols * CELL_SIZE + (cols - 1) * CELL_GAP,
    height: rows * CELL_SIZE + (rows - 1) * CELL_GAP,
  };
}

// Native symbol art can be modestly larger than the 200px slot (e.g.
// static.png's shared canvas is 220x220) — since content isn't cropped to
// the slot, give the frame a little extra room on each edge so that
// overflow never pokes past the wood border. 10px/edge covers the largest
// known asset (220 - 200 = 20px over two edges).
const GRID_EDGE_MARGIN = 20;

// reel_frame.png's inner opening as a fraction of its own canvas (measured
// from the 1201x813 source: transparent hole at x:134-1061, y:132-689 — see
// the CSS for the derivation). The frame is scaled up to whatever size
// makes its hole exactly contain the fixed-pixel grid (plus edge margin).
const FRAME_HOLE_INSET = {
  top: 132 / 813,
  right: 139 / 1201,
  bottom: 123 / 813,
  left: 134 / 1201,
};

// The dark backing panel (.reel__bg) deliberately extends further out than
// the grid/frame-hole — halfway from the measured hole edge toward the
// frame's outer edge — so the panel also covers the frame's soft/vignetted
// inner-braid pixels instead of stopping exactly at the hard content hole.
// .reel__grid keeps the precise FRAME_HOLE_INSET unchanged (confirmed good).
const BG_HOLE_INSET = {
  top: FRAME_HOLE_INSET.top / 2,
  right: FRAME_HOLE_INSET.right / 2,
  bottom: FRAME_HOLE_INSET.bottom / 2,
  left: FRAME_HOLE_INSET.left / 2,
};

function frameSizeForGrid(gridWidth, gridHeight, edgeMargin = GRID_EDGE_MARGIN) {
  const holeWidthFraction = 1 - FRAME_HOLE_INSET.left - FRAME_HOLE_INSET.right;
  const holeHeightFraction = 1 - FRAME_HOLE_INSET.top - FRAME_HOLE_INSET.bottom;
  return {
    width: (gridWidth + edgeMargin) / holeWidthFraction,
    height: (gridHeight + edgeMargin) / holeHeightFraction,
  };
}

// --- Static-image content offset --------------------------------------------
//
// Bug: right after a spin lands, a winning symbol's win animation shows a
// slight jump away from where the static image was sitting (every *repeat*
// of the loop matches fine, since those are Spine-frame-to-Spine-frame —
// only the one-time static-image-to-first-Spine-frame handoff is affected).
// Root cause: static.png's art isn't always centered on its own 220x220
// canvas (asymmetric transparent padding), while Spine's bounds are by
// definition centered on the true content. Centering the *image box* (what
// CSS does) therefore isn't the same as centering the *content* (what Spine
// does) for symbols with off-center art.
//
// Values are (canvas_center - content_bbox_center) in px, measured by
// scanning each static.png for its non-transparent (alpha > 10) pixel
// extent — i.e. how far the image box must shift for its *content* to land
// on the true center, matching where Spine renders it. 0,0 means the art
// was already centered.
const STATIC_CONTENT_OFFSET = {
  scatter: { dx: 0, dy: -1.5 },
  wild: { dx: 1, dy: 1.5 },
  duck: { dx: -5, dy: 10 },
  watermelon: { dx: 0.5, dy: -5 },
  corn: { dx: 1.5, dy: -0.5 },
  blueberry: { dx: -8, dy: 0 },
  strawberry: { dx: -5.5, dy: 9.5 },
  cow: { dx: -4, dy: -2.5 },
  pear: { dx: 0, dy: 2.5 },
  dog: { dx: -0.5, dy: 4.5 },
};

function staticContentOffset(code) {
  return STATIC_CONTENT_OFFSET[code] || { dx: 0, dy: 0 };
}

// --- Responsive desktop scale -------------------------------------------
//
// --reel-frame-w/h (and everything sized from them) were designed for a
// 1920px-wide desktop. Below that, the whole composition shrinks
// proportionally rather than overflowing into horizontal scroll. Applied
// from JS (slot.js updateReelScale), not a CSS `calc(100vw / 1920)` —
// length-divided-by-length isn't reliably supported across browsers.
const REEL_DESIGN_VIEWPORT_WIDTH = 1920;
const REEL_MIN_SCALE = 0.6;

function viewportScale(viewportWidth, designWidth = REEL_DESIGN_VIEWPORT_WIDTH, minScale = REEL_MIN_SCALE) {
  return Math.min(1, Math.max(minScale, viewportWidth / designWidth));
}

// --- Mobile (portrait) scale ---------------------------------------------
//
// Mobile has no shrink-to-a-floor like desktop's viewportScale — the reel
// always fills the viewport edge to edge, at whatever scale that takes,
// since there's no side content (character, logo margins) competing for
// horizontal space the way there is on desktop. frameWidth is the reel's
// own natural (unscaled) design width — --reel-frame-w in CSS.
function mobileReelScale(viewportWidth, frameWidth) {
  if (!frameWidth) return 1;
  return viewportWidth / frameWidth;
}

// --- Fullscreen "fit everything, no scroll" experimental layout ---------
//
// viewportScale only ever looks at width, because the default layout lets
// the page grow taller than the viewport and scroll — .ui-bar has its own
// row below .screen, and .screen's min-height just guarantees enough room
// for the reel, nothing more. The fullscreen experiment (body.layout-fit —
// see style.css) removes that escape hatch: .ui-bar becomes a translucent
// overlay pinned over the bottom of .screen, and .screen is pinned to
// exactly 100vw/100vh. With no scroll allowed, the reel must shrink to
// whichever of width or height is more constraining, so this checks both
// and floors much lower than viewportScale's 0.6 — the point of this mode
// is to always fit, not to protect a minimum size.
const REEL_FIT_MIN_SCALE = 0.35;

function fitScale(viewportWidth, viewportHeight, frameWidth, frameHeight, reserveWidth = 0, reserveHeight = 0, minScale = REEL_FIT_MIN_SCALE) {
  const scaleW = (viewportWidth - reserveWidth) / frameWidth;
  const scaleH = (viewportHeight - reserveHeight) / frameHeight;
  return Math.min(1, Math.max(minScale, Math.min(scaleW, scaleH)));
}

// The reel column's scroll-clip mask deliberately bleeds beyond the visible
// 3-row window. Top bleeds deep toward the frame's top edge, on the
// halfway-to-outer-edge formula (BG_HOLE_INSET) — confirmed safe, no gaps
// there. The bottom *in theory* follows the same formula, but
// reel_frame.png's braid is a woven-rope texture with real gaps in the
// weave further from the hole, not a solid block of wood — a symbol riding
// the full computed bottom bleed was still visible through them. Cap the
// bottom bleed to a small, fixed distance that stays close to the hole
// (well short of where the weave has gaps) instead of scaling it with
// frame size.
const REEL_COL_BOTTOM_BLEED_PX = 20;

function reelColumnBleed(frameHeight) {
  return {
    top: BG_HOLE_INSET.top * frameHeight,
    bottom: REEL_COL_BOTTOM_BLEED_PX,
  };
}

// On top of the small hard-clip bleed above, fade the symbol out well
// *within* that budget (finishing a few px before the hard clip edge) so
// there's never a hard pop past row 3, let alone a lingering peek through
// the weave.
const REEL_COL_FADE_LEAD = 5;
const REEL_COL_FADE_DISTANCE = 15;

function reelColumnFadeStops(frameHeight, gridHeight) {
  const boundary = reelColumnBleed(frameHeight).top + gridHeight;
  const opaqueEnd = boundary - REEL_COL_FADE_LEAD;
  return { opaqueEnd, transparentEnd: opaqueEnd + REEL_COL_FADE_DISTANCE };
}

const ReelMath = {
  currentColumnCodes,
  buildLoopSequence,
  collectAnticipationColumns,
  collectWinGroups,
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
  mobileReelScale,
  fitScale,
  REEL_FIT_MIN_SCALE,
  reelColumnBleed,
  REEL_COL_FADE_DISTANCE,
  reelColumnFadeStops,
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = ReelMath;
}
if (typeof window !== 'undefined') {
  window.ReelMath = ReelMath;
}
