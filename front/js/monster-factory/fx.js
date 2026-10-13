// Monster Factory — ambient + celebration particles (window.FactoryFX).
//
// Two canvases, both pointer-events:none:
//   #fxCanvas  behind the stage: goo bubbles rising off the side vats, sparks
//              dropping from the lamps, dust motes; in the bonus, purple
//              lightning arcs on the side machinery + a screen flash.
//   front      created here, above the screen dim but under the popup: the
//              coin burst behind a win popup.
//
// slot.js calls in through three hooks only — setMode(mode), coinBurst(count,
// ms), splatAt(cell, {bomb}) — and works unchanged if this file is missing.
(function () {
  const back = document.getElementById('fxCanvas');
  const screenEl = document.getElementById('screen');
  if (!back || !screenEl) return;

  const front = document.createElement('canvas');
  front.className = 'layer fx-canvas fx-coins';
  front.style.zIndex = '29';
  screenEl.appendChild(front);

  const bctx = back.getContext('2d');
  const fctx = front.getContext('2d');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let W = 0, H = 0, dpr = 1;
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    W = screenEl.clientWidth;
    H = screenEl.clientHeight;
    for (const c of [back, front]) {
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
    }
    bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    fctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resize);
  resize();

  let mode = 'base';
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];

  // --- Ambient particles ------------------------------------------------------
  const GOO = {
    base: ['120,255,60', '190,90,255', '255,160,40', '60,170,255'],
    freespins: ['190,90,255', '220,120,255', '120,255,60', '60,170,255'],
  };
  const ambient = [];

  function spawnBubble(initial) {
    // Bubbles rise from the vats standing on either side of the reels.
    const left = Math.random() < 0.5;
    const x = left ? rand(0.01, 0.2) * W : rand(0.8, 0.99) * W;
    ambient.push({
      kind: 'bubble',
      x,
      y: initial ? rand(0.2, 1) * H : H + rand(0, 40),
      r: rand(2.5, 8) * Math.max(0.6, Math.min(W, H) / 900),
      vy: -rand(18, 46),
      wob: rand(0, Math.PI * 2),
      col: pick(GOO[mode]),
      life: 1,
    });
  }
  function spawnSpark() {
    // A short shower of sparks dripping off a ceiling lamp / welding point.
    const x = pick([0.3, 0.7, rand(0.15, 0.85)]) * W;
    const y = rand(0.02, 0.12) * H;
    for (let i = 0; i < 10; i++) {
      ambient.push({
        kind: 'spark', x, y,
        vx: rand(-60, 60), vy: rand(-40, 30),
        life: rand(0.6, 1.1), max: 1.1,
        col: mode === 'base' ? '255,190,80' : '220,160,255',
      });
    }
  }
  function spawnMote(initial) {
    ambient.push({
      kind: 'mote',
      x: rand(0, W), y: initial ? rand(0, H) : H + 10,
      r: rand(0.8, 2), vy: -rand(4, 12), vx: rand(-6, 6), life: 1,
      a: rand(0.15, 0.45),
    });
  }

  // --- Lightning (bonus only) ---------------------------------------------------
  let bolts = [];
  function boltPath(x0, y0, x1, y1, depth) {
    const pts = [[x0, y0]];
    const n = 9;
    for (let i = 1; i < n; i++) {
      const t = i / n;
      pts.push([x0 + (x1 - x0) * t + rand(-1, 1) * depth, y0 + (y1 - y0) * t + rand(-1, 1) * depth * 0.4]);
    }
    pts.push([x1, y1]);
    return pts;
  }
  function spawnBolt() {
    const left = Math.random() < 0.5;
    const x0 = (left ? rand(0.02, 0.18) : rand(0.82, 0.98)) * W;
    const x1 = x0 + rand(-0.08, 0.08) * W;
    bolts.push({ pts: boltPath(x0, rand(0, 0.15) * H, x1, rand(0.3, 0.6) * H, W * 0.03), life: 0.32 });
    const flash = document.getElementById('fxBolt');
    if (flash) {
      flash.classList.remove('is-flash');
      void flash.offsetWidth;
      flash.classList.add('is-flash');
    }
  }

  // --- Coins (front canvas) ---------------------------------------------------
  const coins = [];
  let coinSpawnUntil = 0;
  let coinRate = 0;
  let coinPerSec = 0;
  function spawnCoin() {
    const cx = W / 2, cy = H * 0.45;
    const a = rand(-Math.PI * 0.95, -Math.PI * 0.05);
    const sp = rand(0.6, 1.25) * Math.max(W, H) * 0.75;
    const s = Math.max(W, H) / 1400;
    coins.push({
      x: cx + rand(-60, 60) * s, y: cy + rand(-30, 30) * s,
      vx: Math.cos(a) * sp, vy: Math.sin(a) * sp,
      r: rand(14, 26) * s, spin: rand(0, Math.PI * 2), vs: rand(6, 14),
    });
  }
  function drawCoin(ctx, c) {
    const sx = Math.abs(Math.cos(c.spin));
    const w = Math.max(c.r * sx, c.r * 0.12);
    ctx.save();
    ctx.translate(c.x, c.y);
    // rim
    ctx.fillStyle = '#b8660c';
    ctx.beginPath();
    ctx.ellipse(0, 0, w, c.r, 0, 0, Math.PI * 2);
    ctx.fill();
    // face
    const g = ctx.createRadialGradient(-w * 0.3, -c.r * 0.35, c.r * 0.1, 0, 0, c.r);
    g.addColorStop(0, '#fff6b0');
    g.addColorStop(0.45, '#ffd23f');
    g.addColorStop(1, '#e08a10');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.ellipse(0, 0, w * 0.82, c.r * 0.82, 0, 0, Math.PI * 2);
    ctx.fill();
    // monster-eye emblem, foreshortened with the spin
    if (sx > 0.35) {
      ctx.fillStyle = 'rgba(176,90,8,0.8)';
      ctx.beginPath();
      ctx.ellipse(0, 0, w * 0.32, c.r * 0.32, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#fff3c0';
      ctx.beginPath();
      ctx.ellipse(0, 0, w * 0.14, c.r * 0.14, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  // --- Loop -------------------------------------------------------------------
  let last = performance.now();
  let bubbleAcc = 0, moteAcc = 0, sparkT = rand(2, 5), boltT = rand(1.5, 3);
  for (let i = 0; i < 18; i++) spawnBubble(true);
  for (let i = 0; i < 24; i++) spawnMote(true);

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (document.hidden || reduced) { requestAnimationFrame(frame); return; }

    // spawn
    bubbleAcc += dt * (mode === 'base' ? 5 : 7);
    while (bubbleAcc > 1) { spawnBubble(false); bubbleAcc -= 1; }
    moteAcc += dt * 4;
    while (moteAcc > 1) { spawnMote(false); moteAcc -= 1; }
    sparkT -= dt;
    if (sparkT <= 0) { spawnSpark(); sparkT = rand(2.5, 6); }
    if (mode === 'freespins') {
      boltT -= dt;
      if (boltT <= 0) { spawnBolt(); boltT = rand(1.8, 4.2); }
    }

    // back canvas
    bctx.clearRect(0, 0, W, H);
    bctx.globalCompositeOperation = 'lighter';
    for (let i = ambient.length - 1; i >= 0; i--) {
      const p = ambient[i];
      if (p.kind === 'bubble') {
        p.wob += dt * 2.2;
        p.x += Math.sin(p.wob) * 12 * dt;
        p.y += p.vy * dt;
        if (p.y < H * 0.15) p.life -= dt * 1.2;
        const a = Math.max(0, p.life) * 0.55;
        const g = bctx.createRadialGradient(p.x - p.r * 0.3, p.y - p.r * 0.3, 0, p.x, p.y, p.r * 2.2);
        g.addColorStop(0, `rgba(255,255,255,${a})`);
        g.addColorStop(0.3, `rgba(${p.col},${a})`);
        g.addColorStop(1, `rgba(${p.col},0)`);
        bctx.fillStyle = g;
        bctx.beginPath();
        bctx.arc(p.x, p.y, p.r * 2.2, 0, Math.PI * 2);
        bctx.fill();
      } else if (p.kind === 'spark') {
        p.vy += 220 * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.life -= dt;
        const a = Math.max(0, p.life / p.max);
        bctx.strokeStyle = `rgba(${p.col},${a})`;
        bctx.lineWidth = 2;
        bctx.beginPath();
        bctx.moveTo(p.x, p.y);
        bctx.lineTo(p.x - p.vx * 0.03, p.y - p.vy * 0.03);
        bctx.stroke();
      } else {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        if (p.y < -10) p.life = 0;
        bctx.fillStyle = mode === 'base' ? `rgba(255,210,150,${p.a})` : `rgba(220,180,255,${p.a})`;
        bctx.beginPath();
        bctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        bctx.fill();
      }
      if (p.life <= 0 || p.y < -40) ambient.splice(i, 1);
    }
    for (let i = bolts.length - 1; i >= 0; i--) {
      const b = bolts[i];
      b.life -= dt;
      const a = Math.max(0, b.life / 0.32);
      for (const [w, col] of [[7, `rgba(150,80,255,${a * 0.5})`], [2.5, `rgba(240,220,255,${a})`]]) {
        bctx.strokeStyle = col;
        bctx.lineWidth = w;
        bctx.beginPath();
        b.pts.forEach(([x, y], k) => (k ? bctx.lineTo(x, y) : bctx.moveTo(x, y)));
        bctx.stroke();
      }
      if (Math.random() < 0.5) b.pts = boltPath(b.pts[0][0], b.pts[0][1], b.pts[b.pts.length - 1][0], b.pts[b.pts.length - 1][1], W * 0.03);
      if (b.life <= 0) bolts.splice(i, 1);
    }
    bctx.globalCompositeOperation = 'source-over';

    // front canvas — coins
    if (now < coinSpawnUntil) {
      coinRate += dt * coinPerSec;
      while (coinRate > 1) { spawnCoin(); coinRate -= 1; }
    }
    fctx.clearRect(0, 0, W, H);
    for (let i = coins.length - 1; i >= 0; i--) {
      const c = coins[i];
      c.vy += Math.max(W, H) * 1.1 * dt;
      c.x += c.vx * dt;
      c.y += c.vy * dt;
      c.spin += c.vs * dt;
      drawCoin(fctx, c);
      if (c.y > H + 60) coins.splice(i, 1);
    }

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  window.FactoryFX = {
    setMode(next) {
      mode = next === 'freespins' ? 'freespins' : 'base';
      if (mode === 'freespins') boltT = 0.6;
    },
    // `count` coins spread over the first part of `ms`, plus an opening burst.
    coinBurst(count, ms = 2500) {
      if (reduced) return;
      const opening = Math.min(count, Math.round(count * 0.4));
      for (let i = 0; i < opening; i++) spawnCoin();
      const trickleMs = Math.min(ms, 1800);
      coinSpawnUntil = performance.now() + trickleMs;
      coinPerSec = (count - opening) / (trickleMs / 1000);
      coinRate = 0;
    },
    // A bomb shakes the reel block; plain goo splats are pure CSS (.boom).
    splatAt(cell, { bomb = false } = {}) {
      if (!bomb || reduced) return;
      const grid = document.querySelector('.reel__grid-inner');
      if (!grid) return;
      grid.classList.remove('is-shake');
      void grid.offsetWidth;
      grid.classList.add('is-shake');
    },
  };
})();
