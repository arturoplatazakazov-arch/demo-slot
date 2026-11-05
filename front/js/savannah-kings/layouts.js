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
//   3  logo top centre, GRAND MAJOR MINOR MINI in one row on the frame's
//      top border, reels as large as layout 2's.
//   1  (main) one-line title banner on the frame, WIN/BUY left, jackpots right,
//      the frame centred on x at 45% of the stage height
//      (60% of it below); the left column (logo, WIN, BUY BONUS) and the
//      right column (jackpots, MINI at the bottom) are exactly as tall as the
//      frame, items scaled up as far as the column width allows, equal gaps.
(function () {
  const screen = document.getElementById('screen');
  const sw = document.getElementById('layoutSwitch');
  if (!screen || !sw) return;
  const KEY = `savannah.layout.v2.${location.pathname.split('/').pop()}`;

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
  // Layout 3's one-line title banner, a sibling of the stacked logo.
  const logoWide = document.createElement('img');
  logoWide.className = 'logo logo--wide';
  logoWide.alt = '';
  logoWide.src = `${window.SK_ASSET_ROOT || 'img/savannah-kings'}/img/logo_wide.webp`;
  logoWide.style.display = 'none';
  if (logo) logo.after(logoWide);
  const touched = [reel, logo, sys, ladder, buy, status, ...plaques].filter(Boolean);

  function reset() {
    for (const el of touched) el.removeAttribute('style');
    logoWide.setAttribute('style', 'display: none');
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

  // --- 1 (main): title banner on the frame, WIN/BUY left, jackpots right --------
  // The jackpots (GRAND JP_W wide) stand JP_FRAME_GAP right of the frame;
  // the frame is centred, so it is as wide as that leaves on both sides.
  // The one-line logo (logo_wide.webp) rests on the frame's top border and
  // never reaches down into the symbols; WIN and BUY BONUS stack on the
  // left, centred on the frame.
  const L3_CY = H * 0.45;      // frame centre: 45% from the top
  const EDGE = 28;             // outer margin of the left column
  const JP_EDGE = 14;          // jackpot column to the stage edge
  const JP_FRAME_GAP = 10;     // jackpots / WIN-BUY to the frame
  const GAP = 16;              // between items in a column
  const JP_W = 360;            // GRAND width (1.5x the old 240 column)
  const BANNER_K = 0.8;        // logo banner width vs the frame width
  const L3_MEDAL_W = 200;      // WIN / BUY BONUS disc width

  function layoutSides() {
    const f = frameBox();
    buy.style.zoom = '1';
    const ps = plaqueRatios();
    const bannerR = logoWide.naturalWidth ? logoWide.naturalHeight / logoWide.naturalWidth : 0.18;

    // Largest centred frame that leaves the jackpots their room, then
    // shrink until banner top >= 6 and frame bottom stays above the pill.
    let fW = W - 2 * (JP_FRAME_GAP + JP_W + JP_EDGE), s, fH, top, winTop, bannerW, bannerH;
    for (;;) {
      s = fW / f.w; fH = f.h * s;
      top = L3_CY - fH / 2;
      winTop = top - f.y * s;
      bannerW = fW * BANNER_K; bannerH = bannerW * bannerR;
      if ((winTop - 4 - bannerH >= 6 && top + fH <= PILL_TOP - 12) || fW < 700) break;
      fW -= 8;
    }
    const fLeft = W / 2 - fW / 2, fRight = W / 2 + fW / 2;
    const dx = f.x + f.w / 2 - WIN_W / 2;
    const dy = f.y + f.h / 2 - WIN_H / 2;
    Object.assign(reel.style, {
      left: `${W / 2 - WIN_W / 2 - dx * s}px`, top: `${L3_CY - WIN_H / 2 - dy * s}px`,
      transform: `scale(${s})`, transformOrigin: '50% 50%',
    });

    // Title banner: bottom just above the symbol window, over the top border.
    logo.style.display = 'none';
    Object.assign(logoWide.style, {
      display: 'block', left: `${W / 2 - bannerW / 2}px`, top: `${winTop - 4 - bannerH}px`, width: `${bannerW}px`,
      zIndex: '7',   // over the frame's crest
    });

    // Right: jackpots, MINI at the bottom, JP_FRAME_GAP from the frame.
    ps.forEach((q) => sizePlaque(q, q.grand ? JP_W : JP_W / GRAND_K));
    const stackH = ps.reduce((a, q) => a + q.r * (q.grand ? JP_W : JP_W / GRAND_K), 0) + 3 * GAP;
    const stackTop = L3_CY - stackH / 2;
    Object.assign(ladder.style, {
      left: `${fRight + JP_FRAME_GAP}px`, right: 'auto', width: `${JP_W}px`,
      top: `${stackTop}px`, height: `${stackH}px`, transform: 'none',
      justifyContent: 'center', alignItems: 'center', gap: `${GAP}px`, zIndex: '6',   // one centre axis: GRAND over MAJOR
    });

    // Left: WIN and BUY BONUS spanning exactly the jackpot block's height:
    // WIN's top on GRAND's top, BUY's chip bottom on MINI's bottom.
    const room = fLeft - JP_FRAME_GAP - EDGE;
    const md0 = 256, medalH0 = buy.offsetHeight;
    const wC = Math.min(room, L3_MEDAL_W, ((stackH - GAP) / 2) * (md0 / medalH0));
    const k = wC / md0, medalH = medalH0 * k;
    const lcx = (EDGE + fLeft - JP_FRAME_GAP) / 2;
    const place = (el, y) => Object.assign(el.style, {
      zoom: String(k), left: `${(lcx - wC / 2) / k}px`, right: 'auto', top: `${y / k}px`,
    });
    place(status, stackTop);
    place(buy, stackTop + stackH - medalH);

    // The system buttons move off the jackpot column, next to the pill.
    Object.assign(sys.style, { top: `${PILL_TOP + 12}px`, right: '48px' });
  }

  // --- 3: logo on top, then GRAND MAJOR MINOR MINI in one row on the frame
  // The layout-2 recipe with one floor of plaques and the logo above them:
  // the plaques rest on the frame's top border, never on the symbols, and
  // the reels grow until the frame meets the pill.
  function layoutTop() {
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
    else if (v === '3') layoutTop();
    else layoutSides();
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
  [logo, logoWide, ...plaques.map((p) => p.querySelector('img'))].forEach((img) => {
    if (img && !img.complete) img.addEventListener('load', arrange, { once: true });
  });
})();
