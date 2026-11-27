// Neon Joker Spins R1 — screen switches behind a pair of panels (2026-11-26):
//   Hold & Win (the concert stage)  -> two velvet stage curtains, simulated cloth (canvas, below)
//   Free Spins (the dressing room)  -> two heavy metal backstage doors (CSS, css/njs-r1.css)
// app.js / slot.js call NJS_HOOKS.curtain(fn, kind) where the screen switches; fn swaps the screen while
// the panels are shut. Covers the whole window, above everything.
//
// Cloth: each half = N vertical strips. A strip's top hangs on the rail and follows it exactly; its hem is a
// damped spring coupled to its neighbours, so the cloth swings, lags, overshoots and settles. The rail's
// outer end moves later than its leading end, so on opening the strips gather towards the side and the
// folds darken; then the gathered bunch slides off.
(function () {
  const screen = document.getElementById('screen');
  if (!screen) return;
  const ART = {
    hw: 'img/neon-joker-spins/skins/c/sets/r1/img/curtain.webp?v=1',
    hwPlain: 'img/neon-joker-spins/skins/c/sets/r1/img/curtain_plain.webp?v=1',   // phones: just the fabric
    fs: 'img/neon-joker-spins/skins/c/sets/r1/img/door.webp?v=2',                  // no neon, no tags
  };
  const TIME = { hw: [1150, 260, 1250], fs: [520, 320, 640] };   // close, hold, open (ms)
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const imgs = {};
  Object.entries(ART).forEach(([k, u]) => { const i = new Image(); i.src = u; imgs[k] = i; });

  const root = document.createElement('div');
  root.className = 'r1-curtain';
  root.innerHTML = '<div class="r1-curtain__half r1-curtain__half--l"></div><div class="r1-curtain__half r1-curtain__half--r"></div><canvas class="r1-curtain__cloth"></canvas>';
  screen.appendChild(root);
  const cv = root.querySelector('canvas');
  const g = cv.getContext('2d');

  // ---- cloth -------------------------------------------------------------------------------
  const N = 40, BANDS = 24;
  const clamp01 = (t) => Math.max(0, Math.min(1, t));
  const outCubic = (t) => 1 - (1 - t) ** 3;
  const inOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
  const outBack = (t, s) => 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2;
  let W = 0, H = 0, half = 0;
  const halves = [0, 1].map((side) => ({ side, p: new Float32Array(N + 1), v: new Float32Array(N + 1), k: side ? 74 : 86, ph: side ? 1.7 : 0 }));
  function resize() {
    const r = root.getBoundingClientRect();
    dpr = Math.min(1.6, window.devicePixelRatio || 1);
    W = r.width; H = r.height; half = W * 0.52;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  // rail of a half in "left half" coordinates: E = outer end, R = leading end
  const openR = () => -12, openE = () => -12 - half * 0.34;
  function railClose(u) {
    const wind = 0.16, back = half * 0.07;
    if (u < wind) { const t = inOutCubic(u / wind); return { R: openR() - back * t, E: openE() - half * 0.04 * t }; }
    const t = (u - wind) / (1 - wind);
    const R0 = openR() - back, E0 = openE() - half * 0.04;
    return { R: R0 + (half - R0) * outBack(clamp01(t), 0.9), E: E0 + (0 - E0) * outCubic(clamp01((t - 0.08) / 0.92)) };
  }
  function railOpen(u) {
    const tug = 0.13;
    const R = u < tug ? half + half * 0.035 * Math.sin((u / tug) * Math.PI / 2)
      : half * 1.035 + (openR() - half * 1.035) * inOutCubic(clamp01((u - tug) / (1 - tug)));
    return { R, E: openE() * inOutCubic(clamp01((u - 0.34) / 0.66)) };
  }
  const topAt = (rail, i) => rail.E + (rail.R - rail.E) * (i / N);
  function simulate(h, rail, breathe, dt) {
    const now = performance.now();
    for (let i = 0; i <= N; i++) {
      const d = h.p[i] - topAt(rail, i);
      const dl = i > 0 ? h.p[i - 1] - topAt(rail, i - 1) : d;
      const dr = i < N ? h.p[i + 1] - topAt(rail, i + 1) : d;
      const f = -h.k * d - 7.5 * h.v[i] + 30 * (dl + dr - 2 * d) + breathe * Math.sin(now / 520 + i * 0.35 + h.ph) * 7;
      h.v[i] += f * dt;
    }
    for (let i = 0; i <= N; i++) h.p[i] += h.v[i] * dt;
  }
  let dpr = 1;
  function render(h, rail, img) {
    if (!img.complete || !img.naturalWidth) return;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const s = Math.max(half / iw, H / ih);
    const sw = half / s, sh = H / s, sx0 = iw - sw, sy0 = (ih - sh) / 2;   // cover, anchored on the leading edge
    const rest = half / N;
    // x of strip edge i at height y: the top follows the rail, the hem the spring
    const xAt = (i, y) => { const t = topAt(rail, i); return t + (h.p[i] - t) * (y / H) ** 1.35; };
    const m = h.side ? -1 : 1, ox = h.side ? W : 0;
    const bh = H / BANDS, sbh = sh / BANDS, sW = sw / N;
    for (let j = 0; j < BANDS; j++) {
      const y0 = bh * j, y1 = y0 + bh;
      let l0 = xAt(0, y0), l1 = xAt(0, y1);
      for (let i = 0; i < N; i++) {
        const r0 = xAt(i + 1, y0), r1 = xAt(i + 1, y1);
        const w = Math.max(0.5, ((r0 - l0) + (r1 - l1)) / 2);
        if (!(Math.max(l0, l1, r0, r1) < -2 || Math.min(l0, l1) > W + 2)) {
          // a parallelogram: left edge from (l0, y0) to (l1, y1), width w, so bands join without steps
          g.setTransform(dpr * m * w, 0, dpr * m * (l1 - l0), dpr * (bh + 0.7), dpr * (ox + m * l0), dpr * y0);
          g.drawImage(img, sx0 + sW * i, sy0 + sbh * j, sW + 0.5, sbh + 0.5, 0, 0, 1 + 0.9 / w, 1);
          const squeeze = 1 - w / rest;                                 // folds: squeezed strips darken
          if (squeeze > 0.05) { g.fillStyle = `rgba(10, 0, 8, ${Math.min(0.55, squeeze * 0.6).toFixed(3)})`; g.fillRect(0, 0, 1 + 0.9 / w, 1); }
        }
        l0 = r0; l1 = r1;
      }
    }
    // soft shadow past the leading edge
    g.setTransform(dpr * m, 0, 0, dpr, dpr * ox, 0);
    const lx = (h.p[N] + rail.R) / 2;
    const sg = g.createLinearGradient(lx, 0, lx + 30, 0);
    sg.addColorStop(0, 'rgba(0,0,0,0.5)'); sg.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = sg; g.fillRect(lx, 0, 30, H);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function cloth(img, phase, ms) {
    return new Promise((resolve) => {
      const t0 = performance.now(); let last = t0;
      const step = (now) => {
        const dt = Math.min(0.033, (now - last) / 1000); last = now;
        const u = clamp01((now - t0) / ms);
        const rail = phase === 'close' ? railClose(u) : phase === 'open' ? railOpen(u) : { R: half, E: 0 };
        halves.forEach((h) => { for (let k = 0; k < 3; k++) simulate(h, rail, phase === 'hold' ? 1 : 0, dt / 3); });
        g.clearRect(0, 0, W, H);
        halves.forEach((h) => render(h, rail, img));
        if (u < 1) requestAnimationFrame(step); else resolve();
      };
      requestAnimationFrame(step);
    });
  }

  let busy = Promise.resolve();
  function curtain(fn, kind = 'hw') {
    const k = ART[kind] ? kind : 'hw';
    const [CLOSE, HOLD, OPEN] = TIME[k];
    const run = async () => {
      root.dataset.kind = k;
      if (k === 'hw') {
        const img = matchMedia('(orientation: portrait)').matches ? imgs.hwPlain : imgs.hw;
        resize();
        const r0 = railClose(0);
        halves.forEach((h) => { for (let i = 0; i <= N; i++) { h.p[i] = topAt(r0, i); h.v[i] = 0; } });
        root.classList.add('is-on', 'is-cloth');
        if (typeof Sound !== 'undefined' && Sound.blip) Sound.blip(220);
        await cloth(img, 'close', CLOSE);
        const hold = cloth(img, 'hold', HOLD + 400);                  // keeps breathing while the screen swaps
        try { await fn(); } catch (e) { console.error('[r1] transition fn', e); }
        await hold;
        await cloth(img, 'open', OPEN);
        g.clearRect(0, 0, W, H);
        root.classList.remove('is-on', 'is-cloth');
        return;
      }
      // doors: CSS
      root.style.setProperty('--curtain', `url('${new URL(ART[k], location.href).href}')`);   // absolute: a relative url() in a custom property resolves against the stylesheet
      root.style.setProperty('--close-ms', `${CLOSE}ms`);
      root.style.setProperty('--open-ms', `${OPEN}ms`);
      root.classList.remove('is-open', 'is-shut'); root.classList.add('is-on');
      void root.offsetWidth;
      root.classList.add('is-shut');
      if (typeof Sound !== 'undefined' && Sound.blip) Sound.blip(140);
      await sleep(CLOSE);
      try { await fn(); } catch (e) { console.error('[r1] transition fn', e); }
      await sleep(HOLD);
      root.classList.remove('is-shut'); root.classList.add('is-open');
      await sleep(OPEN);
      root.classList.remove('is-on', 'is-open');
    };
    busy = busy.then(run, run);
    return busy;
  }
  window.NJS_HOOKS = Object.assign(window.NJS_HOOKS || {}, { curtain });
})();
