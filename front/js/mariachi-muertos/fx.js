// Mariachi Muertos — particle FX layer (window.MMFX), driven by hooks in slot.js.
//
// Two canvases, both sprite-based (img/mariachi-muertos/fx/*.png, cut from one
// generated particle sheet by scripts/mariachi_muertos_build.py):
//   #fxAmbient — behind the stage: marigold petals drifting down across the
//                plaza and candle embers rising from the bottom edge.
//   #fxBurst   — above everything: per-symbol win bursts, bomb blasts, the
//                coin + flower fountain behind big-win popups, music notes from
//                the mariachi's trumpet while he cheers, and logo sparkles.
// Pure decoration: nothing here is awaited by the game flow, and every hook is
// a no-op until the sprites have loaded.
(function () {
  const ROOT = 'img/mariachi-muertos/fx/';
  const NAMES = ['petal_1', 'petal_2', 'petal_3', 'marigold_1', 'marigold_2', 'marigold_3',
    'coin_1', 'coin_2', 'glow', 'spark_1', 'spark_2', 'flame_1', 'flag_pink', 'flag_green', 'flag_teal'];
  const S = {};
  let ready = false;
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  Promise.all(NAMES.map((n) => new Promise((res) => {
    const im = new Image();
    im.onload = () => { S[n] = im; res(); };
    im.onerror = res;
    im.src = ROOT + n + '.png';
  }))).then(() => { ready = true; });

  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];

  // --- canvases ---------------------------------------------------------------
  function makeCanvas(id, z) {
    const c = document.createElement('canvas');
    c.id = id;
    c.className = 'fx-canvas';
    c.style.zIndex = z;
    document.getElementById('screen').appendChild(c);
    return c;
  }
  let amb, burst, actx, bctx, W = 0, H = 0, dpr = 1;
  function resize() {
    const r = document.getElementById('screen').getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = r.width; H = r.height;
    for (const c of [amb, burst]) {
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
    }
  }
  // Screen-space centre of an element, relative to #screen.
  function centerOf(el, fx = 0.5, fy = 0.5) {
    const s = document.getElementById('screen').getBoundingClientRect();
    const r = el.getBoundingClientRect();
    return { x: r.left - s.left + r.width * fx, y: r.top - s.top + r.height * fy, w: r.width, h: r.height };
  }
  // Sprite size follows the stage scale so phones don't get dinner-plate petals.
  function unit() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale'));
    return Number.isFinite(v) && v > 0 ? Math.max(0.45, Math.min(1.4, v)) : 1;
  }

  // --- particles --------------------------------------------------------------
  // p: {img|glyph, x, y, vx, vy, g (gravity), rot, vr, size, life, age, sway, fade, add}
  const ambient = [];
  const parts = [];

  function spawnAmbientPetal(initial) {
    const u = unit();
    const flower = Math.random() < 0.12;
    ambient.push({
      img: flower ? pick(['marigold_1', 'marigold_2', 'marigold_3']) : pick(['petal_1', 'petal_2', 'petal_3']),
      x: rand(-40, W + 40), y: initial ? rand(-40, H) : rand(-80, -30),
      vx: rand(-12, 18), vy: rand(28, 60), g: 0,
      rot: rand(0, Math.PI * 2), vr: rand(-1.4, 1.4),
      size: (flower ? rand(18, 28) : rand(16, 30)) * u,
      sway: rand(0.6, 1.6), ph: rand(0, 6.28), flip: rand(0, 6.28), alpha: rand(0.55, 0.9),
      life: Infinity, age: 0,
    });
  }
  function spawnEmber() {
    const u = unit();
    ambient.push({
      img: 'glow', x: rand(0, W), y: H + 10, vx: rand(-6, 6), vy: rand(-55, -25), g: 0,
      rot: 0, vr: 0, size: rand(8, 18) * u, sway: rand(0.5, 1.2), ph: rand(0, 6.28),
      alpha: 1, life: rand(3.5, 7), age: 0, add: true, ember: true,
    });
  }

  function burstAt(x, y, opts = {}) {
    const u = unit();
    const n = opts.count || 10;
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2);
      const sp = rand(opts.speedMin || 120, opts.speedMax || 320) * u;
      parts.push({
        img: pick(opts.imgs || ['petal_1', 'petal_2', 'petal_3', 'spark_1']),
        x, y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - (opts.lift || 80) * u,
        g: (opts.g ?? 420) * u, rot: rand(0, 6.28), vr: rand(-6, 6),
        size: rand(opts.sizeMin || 14, opts.sizeMax || 26) * u,
        life: rand(0.7, opts.life || 1.2), age: 0, add: false, alpha: 1,
      });
    }
    // A soft additive flash under the debris.
    if (opts.flash !== false) {
      parts.push({ img: 'glow', x, y, vx: 0, vy: 0, g: 0, rot: 0, vr: 0,
        size: (opts.flashSize || 90) * u, grow: 1.6, life: 0.45, age: 0, add: true, alpha: 1 });
    }
  }

  function fountain(level) {
    // Coins and marigolds shot up from the bottom edge, falling back through the
    // popup; level 1..3 = big/mega/epic.
    const u = unit();
    const total = [0, 40, 70, 110][level] || 40;
    let fired = 0;
    const tick = () => {
      if (fired >= total) return;
      for (let k = 0; k < 4 && fired < total; k++, fired++) {
        const coin = Math.random() < 0.55;
        const flag = !coin && Math.random() < 0.18;
        parts.push({
          img: coin ? pick(['coin_1', 'coin_2']) : flag ? pick(['flag_pink', 'flag_green', 'flag_teal'])
            : pick(['marigold_1', 'marigold_2', 'marigold_3', 'petal_1', 'petal_2']),
          x: rand(W * 0.15, W * 0.85), y: H + 30,
          vx: rand(-220, 220) * u, vy: rand(-H * 1.25, -H * 0.8),
          g: H * 1.05, rot: rand(0, 6.28), vr: rand(-5, 5),
          size: (coin ? rand(30, 46) : rand(26, 42)) * u, spin: coin,
          life: 3.2, age: 0, alpha: 1,
        });
      }
      setTimeout(tick, 45);
    };
    tick();
  }

  function notesFromTrumpet() {
    const hero = document.getElementById('hero');
    if (!hero) return;
    // The trumpet bell sits near the art's top-right in hero.png; the CSS
    // mirrors him (scale: -1 1) to face the reels, so aim from the other side.
    const mirrored = String(getComputedStyle(hero).scale).trim().startsWith('-');
    const p = centerOf(hero, mirrored ? 0.05 : 0.95, 0.2);
    const dir = mirrored ? -1 : 1;
    const u = unit();
    parts.push({
      glyph: pick(['♪', '♫', '♬', '♩']), color: pick(['#ffd35c', '#ff9f2e', '#ff5f8f', '#5fe0d0']),
      x: p.x, y: p.y, vx: dir * rand(40, 120) * u, vy: rand(-110, -60) * u, g: -10 * u,
      rot: rand(-0.3, 0.3), vr: rand(-0.8, 0.8), size: rand(26, 40) * u,
      life: 1.8, age: 0, alpha: 1, sway: 2.2, ph: rand(0, 6.28),
    });
  }

  function logoSparkle() {
    const logo = document.querySelector('.logo');
    if (!logo) return;
    const p = centerOf(logo, rand(0.12, 0.88), rand(0.2, 0.8));
    const u = unit();
    parts.push({ img: pick(['spark_1', 'spark_2']), x: p.x, y: p.y, vx: 0, vy: 0, g: 0,
      rot: 0, vr: rand(-1, 1), size: rand(22, 40) * u, life: 0.9, age: 0, add: true, alpha: 1, twinkle: true });
  }

  // --- drawing ----------------------------------------------------------------
  function draw(ctx, p) {
    const t = p.age / p.life;
    let a = p.alpha;
    if (Number.isFinite(p.life)) {
      if (p.twinkle) a *= Math.sin(Math.PI * t);
      else if (p.ember) a *= Math.min(1, t * 5) * (1 - t);
      else a *= t > 0.7 ? (1 - t) / 0.3 : 1;
    }
    if (a <= 0.01) return;
    ctx.globalAlpha = a;
    ctx.globalCompositeOperation = p.add ? 'lighter' : 'source-over';
    ctx.setTransform(dpr, 0, 0, dpr, p.x * dpr, p.y * dpr);
    ctx.rotate(p.rot);
    let sx = 1;
    if (p.spin) sx = Math.cos(p.age * 9); // coins flip
    if (p.flip !== undefined) sx = 0.45 + 0.55 * Math.abs(Math.cos(p.flip + p.age * 2)); // petals tumble
    const size = p.size * (p.grow ? 1 + (p.grow - 1) * t : 1);
    if (p.glyph) {
      ctx.font = `800 ${size}px 'Baloo 2', serif`;
      ctx.fillStyle = p.color;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowColor = 'rgba(0,0,0,0.6)';
      ctx.shadowBlur = 6;
      ctx.fillText(p.glyph, 0, 0);
      ctx.shadowBlur = 0;
      return;
    }
    const im = S[p.img];
    if (!im) return;
    const k = size / Math.max(im.width, im.height);
    ctx.scale(sx, 1);
    ctx.drawImage(im, -im.width * k / 2, -im.height * k / 2, im.width * k, im.height * k);
  }

  function step(list, dt, ctx) {
    for (let i = list.length - 1; i >= 0; i--) {
      const p = list[i];
      p.age += dt;
      p.vy += p.g * dt;
      p.x += (p.vx + (p.sway ? Math.sin(p.ph + p.age * p.sway) * 26 : 0)) * dt;
      p.y += p.vy * dt;
      p.rot += p.vr * dt;
      const off = p.y > H + 120 || p.y < -200 || p.x < -200 || p.x > W + 200;
      if (p.age >= p.life || (off && p.life === Infinity && p.y > H + 60) || (off && p.age > 0.5)) {
        list.splice(i, 1);
        continue;
      }
      draw(ctx, p);
    }
  }

  let last = 0, emberT = 0, petalT = 0, noteT = 0, sparkleT = 2, cheering = false;
  function frame(ts) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, last ? (ts - last) / 1000 : 0.016);
    last = ts;
    if (!ready || !W) return;

    // Ambient population: ~one petal per 0.35 s, capped.
    petalT -= dt; emberT -= dt; sparkleT -= dt;
    const petals = ambient.filter((p) => !p.ember).length;
    if (petalT <= 0 && petals < (W < 700 ? 18 : 34)) { spawnAmbientPetal(false); petalT = rand(0.2, 0.5); }
    if (emberT <= 0) { spawnEmber(); emberT = rand(0.15, 0.4); }
    if (sparkleT <= 0) { logoSparkle(); sparkleT = rand(0.6, 1.6); }
    if (cheering) { noteT -= dt; if (noteT <= 0) { notesFromTrumpet(); noteT = rand(0.18, 0.32); } }

    actx.setTransform(1, 0, 0, 1, 0, 0);
    actx.clearRect(0, 0, amb.width, amb.height);
    step(ambient, dt, actx);
    bctx.setTransform(1, 0, 0, 1, 0, 0);
    bctx.clearRect(0, 0, burst.width, burst.height);
    step(parts, dt, bctx);
    actx.globalAlpha = 1; bctx.globalAlpha = 1;
  }

  function init() {
    amb = makeCanvas('fxAmbient', 1);
    burst = makeCanvas('fxBurst', 31);
    actx = amb.getContext('2d');
    bctx = burst.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    if (reduced) return;
    for (let i = 0; i < 16; i++) spawnAmbientPetal(true);
    requestAnimationFrame(frame);
  }

  // --- hooks (called from slot.js) -------------------------------------------
  const POPUP_LEVEL = { bigWin: 1, megaWin: 2, epicWin: 3, bonusSpinsTotalWin: 2, bonusSpinsWin: 1 };
  window.MMFX = {
    win(info) {
      if (!ready || reduced || !info) return;
      const p = centerOf(info.cell);
      const special = info.symbol === 'wild' || info.symbol === 'scatter';
      burstAt(p.x, p.y, {
        count: special ? 16 : 8,
        imgs: special ? ['marigold_1', 'petal_1', 'petal_2', 'spark_1', 'coin_1'] : ['petal_1', 'petal_2', 'petal_3', 'spark_2'],
        flashSize: p.w * 0.9,
      });
    },
    boom(info, bomb) {
      if (!ready || reduced || !info) return;
      const p = centerOf(info.cell);
      burstAt(p.x, p.y, bomb
        ? { count: 26, imgs: ['flag_pink', 'flag_green', 'flag_teal', 'marigold_2', 'petal_1', 'spark_1', 'coin_2'],
          speedMin: 260, speedMax: 620, sizeMin: 18, sizeMax: 36, flashSize: p.w * 2.4, life: 1.5 }
        : { count: 6, speedMin: 90, speedMax: 220, flashSize: p.w * 0.8 });
    },
    hero(mood) {
      cheering = mood === 'cheer' && !reduced;
      noteT = 0;
    },
    popup(key) {
      if (!ready || reduced) return;
      const lvl = POPUP_LEVEL[key];
      if (lvl) fountain(lvl);
    },
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
