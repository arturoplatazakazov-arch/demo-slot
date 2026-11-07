// Desktop layout options for the Sugar Blast art variants (forked from
// js/savannah-kings/layouts.js; css/sugar-blast-layouts.css). The «Варианты»
// switch sets #screen[data-layout] to 1 / 2 / 3 and remembers the pick per page.
//   1  (main) one-line logo on the frame, WIN + BUY BONUS side by side at the
//      top of the left column with the chef under them, jackpots right;
//   2  GRAND over MINI · MINOR · MAJOR on the frame's top border;
//   3  logo top centre, GRAND MAJOR MINOR MINI in one row on the frame.
// The bottom bar is the standard ui-bar-v3 OUTSIDE the stage (slot.js fits
// the stage above it), so the whole 1920x1080 stage is ours.
// Free spins: TOTAL MULTIPLIER (the largest element above the reels, GDD
// §6.3) takes the place of the one-line logo (1, portrait) or of the jackpot
// row (2, 3) — placed here, shown by CSS in data-mode="freespins".
(function () {
  const screen = document.getElementById('screen');
  if (!screen) return;
  const KEY = `sugarblast.layout.${location.pathname.split('/').pop()}`;

  let W = 1920;
  const H = 1080;
  const WIN_W = 880, WIN_H = 528, REEL_LEFT = 520;
  const PILL_TOP = 1072;          // stage bottom: the bar lives outside the stage
  const MEDAL_SIDE = 340;         // layouts 2/3: the chef owns x < 340
  // Desktop reels vs the Savannah-derived fit: +20% (first pass) and +20% again
  // with the chef and the jackpots (user, 2026-11-07, layout 1 only).
  const DESK_K = 1.36;   // = 1097 px frame (the size reviewed) x 1.2 on the Forest frame

  const $ = (s) => document.querySelector(s);
  const reel = $('.reel');
  const logo = $('.logo');
  const sys = $('.sys');
  const ladder = $('.crown--ladder');
  const mascot = $('#mascot');
  const totalMult = $('#totalMult');
  const plaques = ladder ? [...ladder.querySelectorAll('.jp')] : [];
  // Layout 3's one-line title banner, a sibling of the stacked logo.
  const logoWide = document.createElement('img');
  logoWide.className = 'logo logo--wide';
  logoWide.alt = '';
  logoWide.src = `${window.SB_ASSET_ROOT || 'img/sugar-blast-forest'}/img/logo_wide.webp`;
  logoWide.style.display = 'none';
  if (logo) logo.after(logoWide);
  const touched = [reel, logo, sys, ladder, mascot, totalMult, ...plaques].filter(Boolean);

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
    p.el.style.flexShrink = '0';
    p.el.style.fontSize = `${Math.round(w * 0.088)}px`;
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
  const JP_W = 432;            // GRAND width: 360 x 1.2 (user, 2026-11-07)
  const BANNER_K = 0.8;        // logo banner width vs the frame width
  const L3_MEDAL_W = 200;      // WIN / BUY BONUS disc width

  function layoutSides() {
    const f = frameBox();
    const ps = plaqueRatios();
    const bannerR = logoWide.naturalWidth ? logoWide.naturalHeight / logoWide.naturalWidth : 0.18;

    // Largest centred frame that leaves the jackpots their room, then
    // shrink until banner top >= 6 and frame bottom stays above the pill.
    // Base fit = what the Savannah recipe gave with a banner of ratio 0.3
    // (the logos the user approved the size on), independent of the art.
    let fW = 1920 - 2 * (JP_FRAME_GAP + 360 + JP_EDGE), s, fH, top, winTop, bannerW, bannerH;
    for (;;) {
      s = fW / f.w; fH = f.h * s;
      top = L3_CY - fH / 2;
      winTop = top - f.y * s;
      bannerW = fW * BANNER_K; bannerH = bannerW * 0.3;
      if ((winTop - 4 - bannerH >= 6 && top + fH <= PILL_TOP - 12) || fW < 700) break;
      fW -= 8;
    }
    // Then 20% larger (user, 2026-11-07): the banner is capped, the frame is
    // re-centred between the stage top and floor, and shrinks only if it
    // still cannot fit.
    fW *= DESK_K;
    let cy = L3_CY;
    for (;;) {
      s = fW / f.w; fH = f.h * s;
      // logo 1.5x the reviewed size (user, 2026-11-07): caps 900/170 -> 1350/255
      // per-variant desktop factor (window.SB_LOGO_K, set by scripts/sugar_blast_pages.py)
      bannerW = Math.min(fW * BANNER_K * 1.5, 1350, 255 / bannerR) * (window.SB_LOGO_K || 1); bannerH = bannerW * bannerR;
      const above = Math.max(0, bannerH + 4 + f.y * s);   // banner top above the frame top (it overlaps the top border)
      const span = above + fH;
      if ((span <= PILL_TOP - 12 - 40 - 6 && fW <= W - 2 * (300 + JP_EDGE - 60)) || fW < 700) {
        // banner + frame centred between the stage top and the floor (minus the
        // half of the WIN plate that hangs under the frame)
        top = 6 + above + Math.max(0, (PILL_TOP - 12 - 40 - 6 - span) / 2);
        cy = top + fH / 2;
        winTop = top - f.y * s;
        break;
      }
      fW -= 8;
    }
    const fLeft = W / 2 - fW / 2, fRight = W / 2 + fW / 2;
    const dx = f.x + f.w / 2 - WIN_W / 2;
    const dy = f.y + f.h / 2 - WIN_H / 2;
    Object.assign(reel.style, {
      left: `${W / 2 - WIN_W / 2 - dx * s}px`, top: `${cy - WIN_H / 2 - dy * s}px`,
      transform: `scale(${s})`, transformOrigin: '50% 50%',
    });

    // Title banner: bottom just above the symbol window, over the top border.
    logo.style.display = 'none';
    Object.assign(logoWide.style, {
      display: 'block', left: `${W / 2 - bannerW / 2}px`, top: `${winTop - 4 - bannerH}px`, width: `${bannerW}px`,
      zIndex: '7',   // over the frame's crest
    });

    // Right: jackpots, MINI at the bottom, JP_FRAME_GAP from the frame, as
    // wide as the side strip allows.
    const tuck = Math.max(0, Math.min(60, JP_W - (W - fRight - JP_FRAME_GAP - JP_EDGE)));
    const jpW = Math.min(JP_W, W - fRight - JP_FRAME_GAP - JP_EDGE + tuck);
    ps.forEach((q) => sizePlaque(q, q.grand ? jpW : jpW / GRAND_K));
    const stackH = ps.reduce((a, q) => a + q.r * (q.grand ? jpW : jpW / GRAND_K), 0) + 3 * GAP;
    const stackTop = cy - stackH / 2;
    Object.assign(ladder.style, {
      left: `${fRight + JP_FRAME_GAP - tuck}px`, right: 'auto', width: `${jpW}px`,
      top: `${stackTop}px`, height: `${stackH}px`, transform: 'none',
      justifyContent: 'center', alignItems: 'center', gap: `${GAP}px`, zIndex: '6',   // one centre axis: GRAND over MAJOR
    });

    // Left: the chef alone (WIN sits on the frame, Buy Bonus is in the bar
    // menu), standing on the stage floor, as tall as the strip allows.
    if (mascot) {
      const side = fLeft - EDGE;
      // 718 x 1.2 (user): as tall as the strip's width and the floor allow.
      const mH = Math.min(862, H - 8 - 120, (side + 60) * 2.05);
      const lcx = Math.max(EDGE / 2 + side / 2, mH * 0.25 + 8);   // whole chef on stage
      // 10% of his height lower (user): the feet go under the bar's gradient.
      Object.assign(mascot.style, { left: `${lcx}px`, top: `${H - 8 - mH + mH * 0.1}px`, height: `${mH}px`, display: '' });
    }
    placeTotalMult({ cx: W / 2, bottom: winTop - 4, w: Math.min(fW * 0.86, 820) });
  }

  // TOTAL MULTIPLIER: centred on `cx`, its bottom at `bottom` (stage px).
  function placeTotalMult({ cx, bottom, w }) {
    if (!totalMult) return;
    const im = totalMult.querySelector('img');
    const r = ratio(im, 0.32);
    w = Math.min(w, (bottom - 4) / r);   // never down over the symbols
    const h = w * r;
    Object.assign(totalMult.style, { left: `${cx - w / 2}px`, top: `${Math.max(4, bottom - h)}px`, width: `${w}px` });
  }

  // --- Portrait (phones): the jackpot ladder (5% larger) on top, then the
  // frame with the one-line title banner lying over its top border (never
  // over the symbols); the medallions follow the frame.
  const P_SCALE = 1.034;
  function layoutPortrait() {
    // The portrait stage is as tall as the phone allows (slot.js), so its
    // width = the screen width: the frame takes 95% of it (user, 2026-11-07).
    const HP = (document.getElementById('stage') || {}).offsetHeight || 1920;
    const f = frameBox();
    const ps = plaqueRatios();
    const sP = (1080 * 0.95 * 1.05) / f.w;   // 95% of the width, then +5% (user, 2026-11-07)
    const wGrand = 380 * 1.05, wRow = 300 * 1.05;
    ps.forEach((q) => sizePlaque(q, q.grand ? wGrand : wRow));
    const crownH = ps.filter((q) => q.grand).reduce((a, q) => a + q.r * wGrand, 0)
      + 8 + Math.max(...ps.filter((q) => !q.grand).map((q) => q.r * wRow));

    // One-line logo at half the old size (user), lying on the frame's top border.
    const bannerR = logoWide.naturalWidth ? logoWide.naturalHeight / logoWide.naturalWidth : 0.2;
    const bannerW = Math.min(900, f.w * sP * BANNER_K) * 0.5 * 2;   // halved, then doubled back (user)
    const bannerH = bannerW * bannerR;
    const frameAbove = -f.y * sP;                         // frame top border over the window
    const lift = Math.max(0, bannerH + 4 - frameAbove);   // banner part above the frame
    const plateBelow = 0.35 * WIN_H * sP;                 // WIN plate hanging under the window (approx.)
    const total = crownH + 12 + lift + frameAbove + WIN_H * sP + plateBelow;
    const top0 = Math.max(16, (HP - total) / 2);          // the whole group centred in the stage
    Object.assign(ladder.style, { top: `${top0}px` });
    const winTop = top0 + crownH + 12 + lift + frameAbove;
    logo.style.display = 'none';
    Object.assign(logoWide.style, {
      display: 'block', left: `${(1080 - bannerW) / 2}px`, top: `${winTop - 4 - bannerH}px`, width: `${bannerW}px`, zIndex: '7',
    });
    const dx = f.x + f.w / 2 - WIN_W / 2;
    Object.assign(reel.style, {
      left: `${540 - WIN_W / 2 - dx * sP}px`, top: `${winTop}px`, transform: `scale(${sP})`, transformOrigin: '50% 0',
    });
    if (mascot) mascot.style.display = 'none';   // GDD §3.1: the chef is a landscape element
    placeTotalMult({ cx: 540, bottom: winTop - 4, w: Math.min(980, f.w * sP * 0.8) });
  }

  function arrange() {
    W = (document.getElementById('stage') || {}).offsetWidth || 1920;
    reset();
    if (document.body.classList.contains('is-portrait')) { layoutPortrait(); return; }
    layoutSides();
  }

  // One desktop layout (user, 2026-11-07: variants 2 and 3 removed).
  screen.dataset.layout = '1';
  if (new URLSearchParams(location.search).has('shot')) document.body.classList.add('is-shot');
  arrange();
  // Art proportions are known once images load; portrait flips on resize
  // (slot.js toggles body.is-portrait in its own resize handler first).
  window.addEventListener('load', arrange);
  window.addEventListener('resize', () => requestAnimationFrame(arrange));
  [logo, logoWide, totalMult && totalMult.querySelector('img'), ...plaques.map((p) => p.querySelector('img'))].forEach((img) => {
    if (img && !img.complete) img.addEventListener('load', arrange, { once: true });
  });
})();
