// Neon Joker Spins R1 — win and jackpot popups (2026-11-26): a big wide title, the punk in his own
// pose per popup, the amount on the glyph panel, light rays, a coin rain and neon punk props
// (bolts, stars, notes, picks...) scattered in the empty corners. Strict value hierarchy: each tier is bigger, denser, longer than the one below.
//   wins      BIG (1) < MEGA (2) < EPIC (3)              app.js -> playPopup('bigWin' | ...)
//   jackpots  MINI (1) < MINOR (2) < MAJOR (3) < GRAND (4)  slot.js -> NJS_HOOKS.jackpot(tier, amount)
// Drawn in a stage-sized layer above the dim, in design px (desktop 1600x900, portrait 720x1280,
// phone landscape 1600x640). Tap skips. Other popups (TOTAL WIN, FREE SPINS...) keep slot.js's own.
(function () {
  const screen = document.getElementById('screen');
  if (!screen || typeof setGlyphs !== 'function' || typeof playPopup !== 'function') return;
  const A = 'img/neon-joker-spins/skins/c/sets/r1/popups';
  const COIN = 'img/neon-joker-spins/skins/c/sets/r1/symbols/coin.webp?v=3';
  const CFG = {
    bigWin:   { tier: 1, title: 'bigWin',  hero: 'hero_big',     hold: 3000, coins: 26 },
    megaWin:  { tier: 2, title: 'megaWin', hero: 'hero_mega',    hold: 3600, coins: 70 },
    epicWin:  { tier: 3, title: 'epicWin', hero: 'hero_epic',    hold: 4300, coins: 150 },
    mini:     { tier: 1, title: 'jpMini',  hero: 'hero_big',     hold: 3000, coins: 30, jp: true },
    minor:    { tier: 2, title: 'jpMinor', hero: 'hero_mega',    hold: 3500, coins: 70, jp: true },
    major:    { tier: 3, title: 'jpMajor', hero: 'hero_jackpot', hold: 4200, coins: 140, jp: true },
    grand:    { tier: 4, title: 'jpGrand', hero: 'hero_jackpot', hold: 5200, coins: 240, jp: true },
    // bonus screens in the same look (2026-11-27): HOLD & WIN entry, its TOTAL WIN (+ COLLECTOR),
    // the FREE SPINS entry (x10) and the free spins' TOTAL WIN
    holdAndWin: { tier: 2, title: 'holdAndWin', hero: 'hero_epic', hold: 1500, coins: 40, noAmount: true },
    totalWin:   { tier: 2, title: 'totalWin', hero: 'hero_mega', hold: 3000, coins: 80 },
    fsIntro:    { tier: 2, title: 'freeSpins', heroSrc: 'img/neon-joker-spins/skins/c/sets/r1/heroes/front.webp?v=1', hold: 3200, coins: 30, tap: true },
    fsTotal:    { tier: 3, title: 'totalWin', heroSrc: 'img/neon-joker-spins/skins/c/sets/r1/heroes/punk.webp?v=1', hold: 4200, coins: 120 },
  };
  const TXT = { tap: 'TAP TO CONTINUE' };
  const V = '?v=2';
  const preload = (u) => { const i = new Image(); i.src = u; };
  const heroOf = (c) => c.heroSrc || `${A}/${c.hero}.webp${V}`;
  Object.values(CFG).forEach((c) => { preload(`${A}/${c.title}.webp${V}`); preload(heroOf(c)); });
  preload(`${A}/collector.webp${V}`);
  preload(COIN);
  // corner decor: neon punk props scattered in the empty corners, more of them per tier
  const DECOR = ['bolt_violet', 'star_pink', 'pick', 'note_cyan', 'stud', 'heart', 'sparkle', 'notes_cyan', 'card', 'bolt_pink', 'mic', 'sparkles'];
  DECOR.forEach((d) => preload(`${A}/d_${d}.webp${V}`));
  const PER_CORNER = { 1: 1, 2: 3, 3: 4, 4: 6 };
  function decor(tier) {
    let seed = 7 + tier * 31;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    const out = [];
    let k = Math.floor(rnd() * DECOR.length);
    for (const [cx, cy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
      const n = tier === 1 && cy === 0 ? 0 : PER_CORNER[tier];       // BIG: only the two bottom corners
      for (let i = 0; i < n; i++) {
        const d = DECOR[k++ % DECOR.length];
        // inside a corner zone, denser towards the very corner
        const u = Math.pow(rnd(), 1.4), v = Math.pow(rnd(), 1.4);
        const x = cx ? 100 - (2 + u * 20) : 2 + u * 20, y = cy ? 100 - (3 + v * 24) : 3 + v * 24;
        const size = Math.round(70 + rnd() * 60 + tier * 8);
        const rot = Math.round((rnd() - 0.5) * 50);
        const delay = Math.round(150 + out.length * 70);
        const dur = (2.4 + rnd() * 1.8).toFixed(2);
        out.push(`<img class="r1-pop__decor" src="${A}/d_${d}.webp${V}" alt="" style="left:${x.toFixed(1)}%;top:${y.toFixed(1)}%;--s:${size}px;--r:${rot}deg;--d:${delay}ms;--f:${dur}s">`);
      }
    }
    return out.join('');
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const layer = document.createElement('div');
  layer.className = 'r1-pops';
  screen.appendChild(layer);

  // coin rain on a canvas the size of the design stage
  function coinRain(cv, n, ms) {
    const g = cv.getContext('2d');
    const img = new Image(); img.src = COIN;
    const W = cv.width, H = cv.height;
    const coins = Array.from({ length: n }, (_, i) => ({
      x: Math.random() * W, y: -Math.random() * H * 0.9 - 60,
      vy: 380 + Math.random() * 520, vx: (Math.random() - 0.5) * 160,
      r: 26 + Math.random() * 30, rot: Math.random() * 6.28, vr: (Math.random() - 0.5) * 8,
      flip: Math.random() * 6.28, vf: 4 + Math.random() * 6, delay: (i / n) * ms * 0.55,
    }));
    let t0 = 0, raf = 0;
    const step = (t) => {
      if (!t0) t0 = t;
      const el = t - t0;
      g.clearRect(0, 0, W, H);
      if (img.complete && img.naturalWidth) {
        for (const c of coins) {
          const dt = (el - c.delay) / 1000;
          if (dt < 0) continue;
          const y = c.y + c.vy * dt + 260 * dt * dt, x = c.x + c.vx * dt;
          if (y > H + 80) continue;
          const sx = Math.abs(Math.cos(c.flip + c.vf * dt));
          g.save(); g.translate(x, y); g.rotate(c.rot + c.vr * dt); g.scale(Math.max(0.12, sx), 1);
          g.drawImage(img, -c.r, -c.r, c.r * 2, c.r * 2); g.restore();
        }
      }
      if (el < ms + 2500) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }

  // opts: hold (ms), text (shown in the panel instead of the amount, e.g. 'x10'), lines (text lines
  // under the panel), collector (the COLLECTOR badge + its value), tap (a TAP TO CONTINUE hint)
  function show(key, amount, opts = {}) {
    const c = Object.assign({}, CFG[key], opts.hold ? { hold: opts.hold } : {});
    const lines = (opts.lines || []).filter(Boolean);
    return new Promise((resolve) => {
      const el = document.createElement('div');
      el.className = `r1-pop r1-pop--t${c.tier}${c.jp ? ' r1-pop--jp' : ''} r1-pop--${key}`;
      el.innerHTML = `<div class="r1-pop__rays"></div><canvas class="r1-pop__coins"></canvas>
        ${decor(c.tier)}
        <img class="r1-pop__hero" src="${heroOf(c)}" alt="">
        <div class="r1-pop__col">
          <img class="r1-pop__title" src="${A}/${c.title}.webp${V}" alt="">
          ${c.noAmount ? '' : '<div class="r1-pop__panel"><span class="glyphs r1-pop__value"></span></div>'}
          ${opts.collector != null ? `<div class="r1-pop__coll"><img src="${A}/collector.webp${V}" alt="COLLECTOR"><span class="glyphs r1-pop__coll-v"></span></div>` : ''}
          ${lines.map((l) => `<div class="r1-pop__line">${l}</div>`).join('')}
          ${c.tap || opts.tap ? `<div class="r1-pop__tap">${TXT.tap}</div>` : ''}
        </div>`;
      layer.appendChild(el);
      const cv = el.querySelector('canvas');
      cv.width = layer.offsetWidth; cv.height = layer.offsetHeight;
      const v = el.querySelector('.r1-pop__value');
      if (v && window.r1FitGlyphs) window.r1FitGlyphs(v, el.querySelector('.r1-pop__panel'), 0.8);
      if (v) setGlyphs(v, opts.text != null ? String(opts.text) : '0');
      const cvv = el.querySelector('.r1-pop__coll-v');
      if (cvv) setGlyphs(cvv, String(opts.collector));
      if (typeof pushScreenDim === 'function') pushScreenDim();
      document.body.classList.add('r1-scene-on');
      if (typeof Sound !== 'undefined') { if (c.jp && Sound.ding) Sound.ding(1.2 + c.tier * 0.1); if (Sound.playSfx) Sound.playSfx('popupOpen'); }
      // phones: the hero is cut at the waist; slide him down so the cut hides behind the title plate
      if (matchMedia('(orientation: portrait)').matches) {
        const hero = el.querySelector('.r1-pop__hero'), title = el.querySelector('.r1-pop__title');
        const place = () => {
          const k = layer.getBoundingClientRect().height / layer.offsetHeight || 1;
          const ty = (title.getBoundingClientRect().top - layer.getBoundingClientRect().top) / k;
          const visible = hero.offsetHeight * 0.54;                 // clip-path keeps the top 54 %
          hero.style.top = `${Math.round(ty + 34 - visible)}px`;
        };
        if (title.complete) place(); else title.addEventListener('load', place, { once: true });
        if (!hero.complete) hero.addEventListener('load', place, { once: true });
      }
      void el.offsetWidth;
      el.classList.add('is-in');
      const stopRain = coinRain(cv, c.coins, c.hold);
      if (v && opts.text == null) { if (typeof countUp === 'function') countUp(v, amount, Math.min(2200, c.hold * 0.55)); else setGlyphs(v, formatAmount(amount)); }
      let done = false;
      const close = async () => {
        if (done) return;
        done = true;
        screen.removeEventListener('pointerdown', close);
        if (v && opts.text == null) setGlyphs(v, formatAmount(amount));
        el.classList.add('is-out');
        await sleep(360);
        stopRain(); el.remove();
        if (!layer.querySelector('.r1-pop') && !document.querySelector('.r1-scene')) document.body.classList.remove('r1-scene-on');
        if (typeof popScreenDim === 'function') popScreenDim();
        resolve();
      };
      setTimeout(() => screen.addEventListener('pointerdown', close), 600);
      setTimeout(close, c.hold + 600);
    });
  }

  // wins: take over the three big-win popups, pass everything else through
  const basePopup = window.playPopup;
  window.playPopup = function (key, amount = 0, holdMs, opts = {}) {
    if (key === 'totalWin') {
      // "COLLECTOR 58×" -> the COLLECTOR badge with its value; anything else -> a text line
      const m = /^COLLECTOR\s+(.+?)\s*[×x]?$/i.exec(opts.sub || '');
      return show('totalWin', amount, m ? { collector: `${m[1]}x` } : { lines: [opts.sub] });
    }
    if (key === 'holdAndWin') return show('holdAndWin', 0, { hold: holdMs });
    if (key === 'freeSpins') return show('fsIntro', 0, { text: `x${(opts && opts.panelText) || 10}` });
    if (CFG[key] && !CFG[key].jp) return show(key, amount);
    return basePopup(key, amount, holdMs, opts);
  };
  // jackpots: slot.js awaits this when a jackpot coin is collected / on 9 of 9
  window.NJS_HOOKS = Object.assign(window.NJS_HOOKS || {}, {
    jackpot: (tier, amount) => (CFG[tier] ? show(tier, amount) : Promise.resolve()),
  });
  window.R1Popups = { show };
})();
