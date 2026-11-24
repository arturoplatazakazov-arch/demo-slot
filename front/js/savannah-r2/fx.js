// Savannah Kings — ambient + celebration FX on two canvases (no Spine).
//   back  (#fxBack, over the background, under the reels): warm dust drifting
//         in the low sun and the odd flock of birds by day (GDD §3.4 P2);
//         fireflies and campfire embers by night (free spins).
//   front (#fxFront, over everything but the dim): sparks on wins, bursts on
//         triggers, a coin shower on big wins and jackpots.
// Everything is drawn procedurally — nothing to load. Both loops sleep while
// the tab is hidden and when there is nothing to draw.
(function () {
  const TAU = Math.PI * 2;
  let back, front, bctx, fctx, dpr = 1, W = 0, H = 0;
  let mode = 'base';
  let motes = [];
  let birds = [];
  let nextFlock = 0;
  let parts = [];
  let shower = null;
  let running = false;
  let last = 0;

  const rnd = (a, b) => a + Math.random() * (b - a);

  function init() {
    back = document.getElementById('fxBack');
    front = document.getElementById('fxFront');
    if (!back || !front) return;
    bctx = back.getContext('2d');
    fctx = front.getContext('2d');
    resize();
    seedMotes();
    nextFlock = performance.now() + rnd(4000, 9000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) kick(); });
    kick();
  }

  function resize() {
    if (!back) return;
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = window.innerWidth;
    H = window.innerHeight;
    for (const c of [back, front]) {
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
    }
    bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    fctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seedMotes();
  }

  function seedMotes() {
    const n = Math.round(Math.min(90, (W * H) / 16000));
    motes = Array.from({ length: n }, () => newMote(true));
  }

  function newMote(anywhere) {
    if (mode === 'freespins') {
      // Fireflies over the grass + embers from the fire, bottom left.
      const ember = Math.random() < 0.35;
      return ember
        ? { k: 'ember', x: rnd(0, W * 0.35), y: anywhere ? rnd(H * 0.4, H) : H + 10, vx: rnd(-6, 14), vy: rnd(-46, -22),
            r: rnd(1, 2.4), life: 0, max: rnd(3, 6), ph: rnd(0, TAU) }
        : { k: 'fly', x: rnd(0, W), y: rnd(H * 0.45, H * 0.95), vx: rnd(-8, 8), vy: rnd(-5, 5),
            r: rnd(1.6, 3), life: 0, max: rnd(6, 12), ph: rnd(0, TAU) };
    }
    return { k: 'dust', x: rnd(0, W), y: anywhere ? rnd(0, H) : rnd(H * 0.2, H), vx: rnd(4, 16), vy: rnd(-6, 2),
      r: rnd(0.8, 2.6), life: anywhere ? rnd(0, 8) : 0, max: rnd(8, 16), ph: rnd(0, TAU) };
  }

  function spawnFlock(now) {
    const fromLeft = Math.random() < 0.5;
    const n = 4 + Math.floor(Math.random() * 6);
    const y0 = rnd(H * 0.08, H * 0.3);
    const sp = rnd(70, 110) * (fromLeft ? 1 : -1);
    for (let i = 0; i < n; i++) {
      birds.push({ x: (fromLeft ? -40 : W + 40) - i * 22 * Math.sign(sp) + rnd(-8, 8), y: y0 + rnd(-18, 18) + (i % 2) * 10,
        vx: sp * rnd(0.92, 1.08), s: rnd(5, 8), ph: rnd(0, TAU), f: rnd(7, 9) });
    }
    nextFlock = now + rnd(14000, 26000);
  }

  function drawBack(dt, now) {
    bctx.clearRect(0, 0, W, H);
    for (let i = 0; i < motes.length; i++) {
      const m = motes[i];
      m.life += dt;
      m.x += m.vx * dt + Math.sin(now / 1300 + m.ph) * 0.15;
      m.y += m.vy * dt;
      if (m.life > m.max || m.x > W + 20 || m.y < -20) { motes[i] = newMote(false); continue; }
      const fade = Math.min(1, m.life / 1.5, (m.max - m.life) / 1.5);
      if (m.k === 'dust') {
        bctx.fillStyle = `rgba(255, 214, 150, ${0.35 * fade})`;
        bctx.beginPath(); bctx.arc(m.x, m.y, m.r, 0, TAU); bctx.fill();
      } else if (m.k === 'fly') {
        const blink = 0.5 + 0.5 * Math.sin(now / 420 + m.ph * 3);
        const a = fade * blink;
        const g = bctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, m.r * 6);
        g.addColorStop(0, `rgba(230, 255, 140, ${0.9 * a})`);
        g.addColorStop(1, 'rgba(230, 255, 140, 0)');
        bctx.fillStyle = g;
        bctx.beginPath(); bctx.arc(m.x, m.y, m.r * 6, 0, TAU); bctx.fill();
        m.vx += rnd(-12, 12) * dt; m.vy += rnd(-12, 12) * dt;
        m.vx *= 0.98; m.vy *= 0.98;
      } else {
        m.vx += Math.sin(now / 500 + m.ph) * 4 * dt;
        bctx.fillStyle = `rgba(255, ${140 + Math.round(80 * fade)}, 60, ${0.85 * fade})`;
        bctx.beginPath(); bctx.arc(m.x, m.y, m.r, 0, TAU); bctx.fill();
      }
    }
    if (mode === 'base') {
      if (now > nextFlock) spawnFlock(now);
      bctx.strokeStyle = 'rgba(40, 14, 20, 0.75)';
      bctx.lineCap = 'round';
      birds = birds.filter((b) => b.x > -80 && b.x < W + 80);
      for (const b of birds) {
        b.x += b.vx * dt;
        b.y += Math.sin(now / 900 + b.ph) * 0.12;
        const flap = Math.sin(now / 1000 * b.f + b.ph);
        bctx.lineWidth = Math.max(1.2, b.s / 4.5);
        bctx.beginPath();
        bctx.moveTo(b.x - b.s, b.y - flap * b.s * 0.55);
        bctx.quadraticCurveTo(b.x - b.s * 0.4, b.y - b.s * 0.15, b.x, b.y);
        bctx.quadraticCurveTo(b.x + b.s * 0.4, b.y - b.s * 0.15, b.x + b.s, b.y - flap * b.s * 0.55);
        bctx.stroke();
      }
    }
  }

  // --- Front: sparks, bursts, coins ---------------------------------------

  const PALETTE = {
    gold: ['255,215,90', '255,180,40', '255,240,190'],
    sun: ['255,150,50', '255,210,80', '255,90,40'],
  };

  function rectCentre(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height };
  }

  function sparkAt(el, code) {
    if (!el) return;
    const c = rectCentre(el);
    const n = code === 'wild' || code === 'scatter' ? 16 : 9;
    for (let i = 0; i < n; i++) {
      const a = rnd(0, TAU);
      const v = rnd(60, 180);
      parts.push({ k: 'spark', x: c.x + Math.cos(a) * c.w * 0.3, y: c.y + Math.sin(a) * c.h * 0.3,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v - 40, g: 120, life: 0, max: rnd(0.5, 0.9),
        r: rnd(1.2, 2.6), col: PALETTE.gold[i % 3] });
    }
    kick();
  }

  function burstAt(el, kind = 'gold') {
    if (!el) return;
    const c = rectCentre(el);
    const pal = PALETTE[kind] || PALETTE.gold;
    parts.push({ k: 'ring', x: c.x, y: c.y, life: 0, max: 0.55, r0: Math.min(c.w, c.h) * 0.3, r1: Math.max(c.w, c.h) * 0.8, col: pal[0] });
    for (let i = 0; i < 26; i++) {
      const a = rnd(0, TAU);
      const v = rnd(140, 380);
      parts.push({ k: 'spark', x: c.x, y: c.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, g: 260,
        life: 0, max: rnd(0.6, 1.1), r: rnd(1.5, 3.4), col: pal[i % pal.length] });
    }
    kick();
  }

  function startShower(tier = 'big') {
    shower = { rate: tier === 'epic' ? 70 : tier === 'mega' ? 48 : 30, acc: 0 };
    kick();
  }
  function stopShower() { shower = null; }

  function newCoin() {
    return { k: 'coin', x: rnd(W * 0.05, W * 0.95), y: -30, vx: rnd(-40, 40), vy: rnd(120, 260), g: 520,
      life: 0, max: 4, r: rnd(9, 16) * Math.min(1.4, Math.max(0.7, W / 1400)), spin: rnd(4, 9), ph: rnd(0, TAU) };
  }

  function drawCoin(p) {
    const sx = Math.cos(p.ph + p.life * p.spin);
    const w = Math.max(0.12, Math.abs(sx)) * p.r;
    fctx.save();
    fctx.translate(p.x, p.y);
    const g = fctx.createLinearGradient(-w, -p.r, w, p.r);
    g.addColorStop(0, sx > 0 ? '#fff1b0' : '#c98a00');
    g.addColorStop(0.5, '#f5b400');
    g.addColorStop(1, '#8a5200');
    fctx.fillStyle = g;
    fctx.beginPath(); fctx.ellipse(0, 0, w, p.r, 0, 0, TAU); fctx.fill();
    fctx.strokeStyle = 'rgba(90,45,0,0.8)';
    fctx.lineWidth = Math.max(1, p.r * 0.12);
    fctx.stroke();
    if (w > p.r * 0.45) {
      fctx.strokeStyle = 'rgba(255,240,190,0.7)';
      fctx.beginPath(); fctx.ellipse(0, 0, w * 0.62, p.r * 0.62, 0, 0, TAU); fctx.stroke();
    }
    fctx.restore();
  }

  function drawFront(dt) {
    fctx.clearRect(0, 0, W, H);
    if (shower) {
      shower.acc += shower.rate * dt;
      while (shower.acc >= 1) { shower.acc -= 1; parts.push(newCoin()); }
    }
    fctx.globalCompositeOperation = 'source-over';
    const alive = [];
    for (const p of parts) {
      p.life += dt;
      if (p.life >= p.max || p.y > H + 60) continue;
      alive.push(p);
      const t = p.life / p.max;
      if (p.k === 'coin') {
        p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt;
        drawCoin(p);
      } else if (p.k === 'ring') {
        const r = p.r0 + (p.r1 - p.r0) * (1 - Math.pow(1 - t, 3));
        fctx.strokeStyle = `rgba(${p.col}, ${0.7 * (1 - t)})`;
        fctx.lineWidth = 6 * (1 - t) + 1;
        fctx.beginPath(); fctx.arc(p.x, p.y, r, 0, TAU); fctx.stroke();
      } else {
        p.vy += p.g * dt; p.vx *= 0.985; p.x += p.vx * dt; p.y += p.vy * dt;
        fctx.globalCompositeOperation = 'lighter';
        fctx.fillStyle = `rgba(${p.col}, ${1 - t})`;
        fctx.beginPath(); fctx.arc(p.x, p.y, p.r * (1 - t * 0.5), 0, TAU); fctx.fill();
        fctx.globalCompositeOperation = 'source-over';
      }
    }
    parts = alive;
  }

  function frame(now) {
    if (document.hidden) { running = false; return; }
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
    last = now;
    drawBack(dt, now);
    drawFront(dt);
    requestAnimationFrame(frame);
  }

  function kick() {
    if (running || !back) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(frame);
  }

  function setMode(next) {
    if (next === mode) return;
    mode = next;
    birds = [];
    seedMotes();
  }

  window.SKFx = { init, resize, setMode, sparkAt, burstAt, startShower, stopShower };
})();
