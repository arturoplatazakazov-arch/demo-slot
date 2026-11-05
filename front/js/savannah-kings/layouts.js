// Desktop layout options for the Savannah Kings art variants (see
// css/savannah-layouts.css). The «Варианты» switch sets #screen[data-layout]
// to 1 / 2 / 3 and remembers the pick per page, like Great Uniqorn.
//
// Layouts 2 and 3 are placed here, in stage px (the 1920x1080 design frame),
// from the variant's real frame geometry (--frame-win-* in its stylesheet)
// and the plaque/logo art proportions, so one rule set fits all five frames:
//   2  GRAND over MINI · MINOR · MAJOR, sitting on the frame's top border;
//      the reels grow until the frame meets the control pill, and the
//      plaques never reach down into the symbol window.
//   1  logo top centre, GRAND MAJOR MINOR MINI in one row on the frame's
//      top border, reels as large as layout 2's.
//   3  the frame (as tall as the columns allow), centred on x and at 45% of the stage height
//      (60% of it below); the left column (logo, WIN, BUY BONUS) and the
//      right column (jackpots, MINI at the bottom) are exactly as tall as the
//      frame, items scaled up as far as the column width allows, equal gaps.
(function () {
  const screen = document.getElementById('screen');
  const sw = document.getElementById('layoutSwitch');
  if (!screen || !sw) return;
  const KEY = `savannah.layout.${location.pathname.split('/').pop()}`;

  const W = 1920, H = 1080;
  const WIN_W = 880, WIN_H = 528, REEL_LEFT = 520;
  const PILL_TOP = 976;           // .bar top: frames stay above it
  const MEDAL_SIDE = 340;         // layout 2: medallions own x < 340 and x > 1580

  const $ = (s) => document.querySelector(s);
  const reel = $('.reel');
  const logo = $('.logo');
  const sys = $('.sys');
  const ladder = $('.crown--ladder');
  const buy = $('.medal--buy');
  const status = $('.medal--status');
  const plaques = ladder ? [...ladder.querySelectorAll('.jp')] : [];
  const touched = [reel, logo, sys, ladder, buy, status, ...plaques].filter(Boolean);

  function reset() {
    for (const el of touched) el.removeAttribute('style');
  }

  function cssNum(name) {
    return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
  }

  // The frame art's box relative to the reel's top-left, unscaled.
  function frameBox() {
    const fw = WIN_W / cssNum('--frame-win-w');
    const fh = WIN_H / cssNum('--frame-win-h');
    return { w: fw, h: fh, x: -fw * cssNum('--frame-win-l'), y: -fh * cssNum('--frame-win-t') };
  }

  function ratio(img, fallback) {
    return img && img.naturalWidth ? img.naturalHeight / img.naturalWidth : fallback;
  }

  // Plaque widths keep layout 1's proportion: GRAND is 350/310 of the rest.
  const GRAND_K = 350 / 310;
  function plaqueRatios() {
    return plaques.map((p) => ({ el: p, grand: p.classList.contains('jp--grand'), r: ratio(p.querySelector('img'), 0.35) }));
  }
  function sizePlaque(p, w) {
    p.el.style.width = `${w}px`;
    p.el.style.fontSize = `${Math.round(w * 0.088)}px`;
  }

  // --- 2: two floors on the frame's top border ---------------------------
  function layout2() {
    const f = frameBox();
    const ps = plaqueRatios();
    const wRow = 250, wGrand = 320, gap = 6;
    ps.forEach((p) => sizePlaque(p, p.grand ? wGrand : wRow));
    const hGrand = ps.filter((p) => p.grand).reduce((a, p) => a + p.r * wGrand, 0);
    const hRow = Math.max(...ps.filter((p) => !p.grand).map((p) => p.r * wRow));
    const crownTop = 14;
    const winTop = crownTop + hGrand + gap + hRow + 10;      // plaques end above the symbols
    const below = f.y + f.h - WIN_H;                          // frame under the window
    let s = (PILL_TOP - 12 - winTop) / (WIN_H + below);
    s = Math.min(s, (W - 2 * MEDAL_SIDE) / f.w);
    Object.assign(reel.style, { top: `${winTop}px`, transform: `scale(${s})`, transformOrigin: '50% 0' });
    Object.assign(ladder.style, { top: `${crownTop}px` });
  }

  // --- 3: side columns as tall as the frame ------------------------------
  const L3_FRAME_MAX = 940;    // frame height on stage: tallest tried
  const L3_FRAME_MIN = 560;    // ...and the floor
  const L3_CY = H * 0.45;      // frame centre: 45% from the top
  const EDGE = 28;             // outer margin of both columns
  const COL_GAP = 24;          // between a column and the frame
  const GAP = 16;              // minimum gap between items in a column

  // The frame and the left column are sized as one width wC (the slot as
  // large as possible while wC >= COL_MIN_W); the jackpots are JP_K times
  // that and may lie over the frame's right border.
  const COL_MIN_W = 240;
  const JP_EDGE = 14;
  const JP_K = 1.5;            // jackpot plaques vs the column width
  function plan3(f, frameH) {
    const s = frameH / f.h;
    const fW = f.w * s;
    const logoR = ratio(logo, 0.6), medalH0 = buy.offsetHeight, md0 = 256;
    const ps = plaqueRatios();
    const rightUnit = ps.reduce((a, p) => a + p.r * (p.grand ? 1 : 1 / GRAND_K), 0);
    const side = W / 2 - fW / 2 - COL_GAP - EDGE;
    const wC = Math.min(
      side,
      (frameH - 2 * GAP) / (logoR + (2 * medalH0) / md0),
      (frameH - 3 * GAP) / rightUnit,
    );
    return { frameH, s, fW, logoR, medalH0, md0, ps, wC, fits: wC >= COL_MIN_W };
  }

  function layout3() {
    const f = frameBox();
    buy.style.zoom = '1';
    let frameH = L3_FRAME_MAX, p = plan3(f, frameH);
    while (!p.fits && frameH > L3_FRAME_MIN) { frameH -= 4; p = plan3(f, frameH); }
    const fLeft = W / 2 - p.fW / 2, fRight = W / 2 + p.fW / 2;
    const wC = p.wC;

    // Frame centred on x = 960; transform-origin is the reel's centre.
    const dx = f.x + f.w / 2 - WIN_W / 2;
    const dy = f.y + f.h / 2 - WIN_H / 2;
    Object.assign(reel.style, {
      left: `${W / 2 - WIN_W / 2 - dx * p.s}px`, top: `${L3_CY - WIN_H / 2 - dy * p.s}px`,
      transform: `scale(${p.s})`, transformOrigin: '50% 50%',
    });

    // Left: logo, WIN, BUY BONUS, each wC wide.
    const k = wC / p.md0;
    const lcx = (EDGE + fLeft - COL_GAP) / 2;
    const logoH = wC * p.logoR, medalH = p.medalH0 * k;
    // Tight GAP gaps, the group centred on the frame's vertical centre.
    const g = GAP;
    const lTop = L3_CY - (logoH + 2 * medalH + 2 * g) / 2;
    Object.assign(logo.style, { left: `${lcx - wC / 2}px`, top: `${lTop}px`, width: `${wC}px` });
    // zoom scales the medallion and its own left/top, so place in zoomed px.
    const place = (el, y) => Object.assign(el.style, {
      zoom: String(k), left: `${(lcx - wC / 2) / k}px`, right: 'auto', top: `${y / k}px`,
    });
    place(status, lTop + logoH + g);
    place(buy, lTop + logoH + g + medalH + g);

    // Right: jackpots 1.5x the column width (GRAND = JP_K * wC, the others
    // that / GRAND_K), MINI at the bottom, tight equal gaps, centred on the
    // frame. Pinned to the stage's right edge; whatever is wider than the
    // room beside the frame lies over the frame's right border.
    const wG = JP_K * wC;
    const x1 = W - JP_EDGE;
    p.ps.forEach((q) => sizePlaque(q, q.grand ? wG : wG / GRAND_K));
    const stackH = p.ps.reduce((a, q) => a + q.r * (q.grand ? wG : wG / GRAND_K), 0) + 3 * GAP;
    const colH = Math.max(frameH, stackH);
    Object.assign(ladder.style, {
      left: `${x1 - wG}px`, right: 'auto', width: `${wG}px`,
      top: `${L3_CY - colH / 2}px`, height: `${colH}px`, transform: 'none',
      justifyContent: 'center', alignItems: 'flex-end', gap: `${GAP}px`, zIndex: '6',
    });

    // The system buttons move off the jackpot column, next to the pill.
    Object.assign(sys.style, { top: `${PILL_TOP + 12}px`, right: '48px' });
  }

  // --- 1: logo on top, then GRAND MAJOR MINOR MINI in one row on the frame
  // The layout-2 recipe with one floor of plaques and the logo above them:
  // the plaques rest on the frame's top border, never on the symbols, and
  // the reels grow until the frame meets the pill.
  function layout1() {
    const f = frameBox();
    const ps = plaqueRatios();
    const logoW = 230, logoTop = 6;
    const logoH = logoW * ratio(logo, 0.6);
    Object.assign(logo.style, { left: `${W / 2 - logoW / 2}px`, top: `${logoTop}px`, width: `${logoW}px` });
    const wGrand = 250, wRow = 210;
    ps.forEach((p) => sizePlaque(p, p.grand ? wGrand : wRow));
    const crownTop = logoTop + logoH + 4;
    const crownH = Math.max(...ps.map((p) => p.r * (p.grand ? wGrand : wRow)));
    // DOM order is MINI MINOR MAJOR GRAND: row-reverse reads GRAND -> MINI.
    Object.assign(ladder.style, { top: `${crownTop}px`, flexDirection: 'row-reverse', zIndex: '6' });
    const winTop = crownTop + crownH + 10;
    const below = f.y + f.h - WIN_H;
    let s = (PILL_TOP - 12 - winTop) / (WIN_H + below);
    s = Math.min(s, (W - 2 * MEDAL_SIDE) / f.w);
    Object.assign(reel.style, { top: `${winTop}px`, transform: `scale(${s})`, transformOrigin: '50% 0' });
  }

  function arrange() {
    reset();
    if (document.body.classList.contains('is-portrait')) return;
    const v = screen.dataset.layout;
    if (v === '2') layout2();
    else if (v === '3') layout3();
    else layout1();
  }

  function set(v) {
    const next = ['1', '2', '3'].includes(String(v)) ? String(v) : '1';
    screen.dataset.layout = next;
    sw.querySelectorAll('[data-layout]').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.layout === next));
    });
    try { localStorage.setItem(KEY, next); } catch (e) { /* private mode */ }
    arrange();
  }

  let saved = new URLSearchParams(location.search).get('layout');
  if (!saved) { try { saved = localStorage.getItem(KEY); } catch (e) { /* ignore */ } }
  set(saved || '1');
  sw.querySelectorAll('[data-layout]').forEach((b) => {
    b.addEventListener('click', () => {
      if (window.Sound && Sound.playSfx) { try { Sound.playSfx('click'); } catch (e) { /* no sfx */ } }
      set(b.dataset.layout);
    });
  });
  // Art proportions are known once images load; portrait flips on resize
  // (slot.js toggles body.is-portrait in its own resize handler first).
  window.addEventListener('load', arrange);
  window.addEventListener('resize', () => requestAnimationFrame(arrange));
  [logo, ...plaques.map((p) => p.querySelector('img'))].forEach((img) => {
    if (img && !img.complete) img.addEventListener('load', arrange, { once: true });
  });
})();
