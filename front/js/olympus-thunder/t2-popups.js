// Olympus Thunder · Tides 2/3 — win & jackpot popups as a storm scene (client 2026-11-20).
// Big / Mega / Epic and the four jackpots are FRONTAL painted titles (own colour per tier, bigger the richer),
// the amount counts up on a cloud under the title, and the scene grows with the tier: more lightning bolts
// across the sky, more storm clouds rolling in from the screen corners (out of transparency and back), flashes
// and a camera shake from Epic / Major up. Other popups (free spins, totals) keep the original UI.popup.
// Art per variant: <body data-pop="img/olympus-thunder/<var>/pop/" data-pop-clouds="img/olympus-thunder/<var>/zeus_clouds/">
(function () {
  if (!window.UI) return;
  const B = document.body.dataset;
  const POP = B.pop || 'img/olympus-thunder/tides2/pop/';
  const CL = B.popClouds || 'img/olympus-thunder/tides2/zeus_clouds/';
  const orig = UI.popup;

  // lvl drives the whole scene: bolts, clouds, flashes, shake, title size, count-up length
  const TIERS = {
    big:   { lvl: 1, img: 'big',   scale: 0.74, ms: 2200, sound: 'bigWin' },
    mega:  { lvl: 2, img: 'mega',  scale: 0.86, ms: 3200, sound: 'megaWin' },
    epic:  { lvl: 3, img: 'epic',  scale: 1.0,  ms: 4200, sound: 'epicWin' },
    mini:  { lvl: 1, img: 'mini',  scale: 0.66, ms: 1600, sound: 'bigWin' },
    minor: { lvl: 2, img: 'minor', scale: 0.78, ms: 2200, sound: 'megaWin' },
    major: { lvl: 3, img: 'major', scale: 0.9,  ms: 3000, sound: 'epicWin' },
    grand: { lvl: 4, img: 'grand', scale: 1.06, ms: 4200, sound: 'epicWin' },
  };
  // corner clouds per level: [corner, sprite, size vw]
  const CLOUDS = [
    ['bl', 'c2', 46], ['br', 'c3', 46],
    ['tl', 'c1', 42], ['tr', 'c2', 42],
    ['ml', 'c3', 38], ['mr', 'c1', 38],
  ];

  // ---------- DOM ----------
  const root = document.createElement('div');
  root.className = 't2pop'; root.hidden = true;
  root.innerHTML =
    '<canvas class="t2pop__fx"></canvas>' +
    '<div class="t2pop__flash"></div>' +
    '<div class="t2pop__clouds">' + CLOUDS.map(([c, s], i) =>
      `<img class="t2pop__cl t2pop__cl--${c}" data-i="${i}" src="${CL}${s}.webp?v=2" alt="">`).join('') + '</div>' +
    '<div class="t2pop__stack"><img class="t2pop__title" alt="">' +
    `<div class="t2pop__cloud"><img src="${CL}c2.webp?v=2" alt=""><span class="t2pop__amount"></span></div></div>` +
    '<div class="t2pop__hint">TAP TO CONTINUE</div>';
  document.body.appendChild(root);
  const cv = root.querySelector('.t2pop__fx'), ctx = cv.getContext('2d');
  const title = root.querySelector('.t2pop__title'), amountEl = root.querySelector('.t2pop__amount');
  const flash = root.querySelector('.t2pop__flash');
  Object.values(TIERS).forEach((t) => { const i = new Image(); i.src = `${POP}${t.img}.webp?v=1`; });

  // ---------- lightning (same 3-pass bolt as the Tesla Spins fx) ----------
  const rand = (a, b) => a + Math.random() * (b - a);
  function path(x0, y0, x1, y1, rough, depth) {
    let p = [[x0, y0], [x1, y1]], d = rough;
    for (let k = 0; k < depth; k++) {
      const n = [p[0]];
      for (let i = 0; i < p.length - 1; i++) {
        const [ax, ay] = p[i], [bx, by] = p[i + 1], dx = bx - ax, dy = by - ay, l = Math.hypot(dx, dy) || 1, o = rand(-d, d);
        n.push([(ax + bx) / 2 - (dy / l) * o, (ay + by) / 2 + (dx / l) * o], p[i + 1]);
      }
      p = n; d *= 0.55;
    }
    return p;
  }
  function bolt(x0, y0, x1, y1, power) {
    const len = Math.hypot(x1 - x0, y1 - y0), trunk = path(x0, y0, x1, y1, len * 0.18, 7), br = [];
    for (let i = 0, n = Math.round(rand(1, 3) * power); i < n; i++) {
      const at = trunk[Math.floor(rand(0.2, 0.8) * trunk.length)], a = Math.atan2(y1 - y0, x1 - x0) + rand(-1.1, 1.1), l = len * rand(0.12, 0.3);
      br.push(path(at[0], at[1], at[0] + Math.cos(a) * l, at[1] + Math.sin(a) * l, l * 0.3, 4));
    }
    return { trunk, br, t0: performance.now(), life: rand(260, 520) };
  }
  const stroke = (p) => { ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]); for (let i = 1; i < p.length; i++) ctx.lineTo(p[i][0], p[i][1]); ctx.stroke(); };
  function draw(b, a, w) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.lineJoin = ctx.lineCap = 'round';
    ctx.shadowColor = `rgba(110, 200, 255, ${a})`; ctx.shadowBlur = 22 * dpr;
    ctx.strokeStyle = `rgba(70, 150, 255, ${0.35 * a})`; ctx.lineWidth = w * 5; stroke(b.trunk);
    ctx.shadowBlur = 10 * dpr; ctx.strokeStyle = `rgba(160, 225, 255, ${0.8 * a})`; ctx.lineWidth = w * 2; stroke(b.trunk); b.br.forEach(stroke);
    ctx.shadowBlur = 0; ctx.strokeStyle = `rgba(250, 252, 255, ${a})`; ctx.lineWidth = w * 0.8; stroke(b.trunk); ctx.lineWidth = w * 0.45; b.br.forEach(stroke);
    ctx.restore();
  }
  let dpr = 1, bolts = [], raf = 0, nextAt = 0, run = null;
  function resize() { dpr = Math.min(2, devicePixelRatio || 1); cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; }
  function spawn(lvl) {
    const W = cv.width, H = cv.height, side = Math.random();
    // from the top edge / upper corners down toward the sides of the screen (the title stays readable)
    const x0 = side < 0.5 ? rand(0, W * 0.45) : rand(W * 0.55, W), y0 = -10;
    const x1 = (x0 < W / 2 ? rand(-W * 0.05, W * 0.32) : rand(W * 0.68, W * 1.05)), y1 = rand(H * 0.45, H * 0.95);
    bolts.push(bolt(x0, y0, x1, y1, 0.8 + lvl * 0.35));
    if (lvl >= 2 && Math.random() < 0.35 + lvl * 0.1) bolts.push(bolt(W - x0, y0, W - x1, y1 * rand(0.8, 1), 0.8 + lvl * 0.3));
    flash.style.setProperty('--fa', String(Math.min(0.55, 0.16 + lvl * 0.1)));
    flash.classList.remove('is-on'); void flash.offsetWidth; flash.classList.add('is-on');
    if (lvl >= 3) { root.classList.remove('is-shake'); void root.offsetWidth; root.classList.add('is-shake'); }
    if (window.Sound && Sound.thunder && Math.random() < 0.5) try { Sound.thunder(lvl * 12); } catch (e) {}
  }
  function frame(now) {
    if (!run) return;
    if (now >= nextAt) { spawn(run.lvl); nextAt = now + rand(900, 1700) / (0.6 + run.lvl * 0.55); }
    ctx.clearRect(0, 0, cv.width, cv.height);
    bolts = bolts.filter((b) => now - b.t0 < b.life);
    for (const b of bolts) {
      const k = (now - b.t0) / b.life, a = k < 0.12 ? 1 : Math.max(0, 1 - (k - 0.12) / 0.88) * (0.75 + 0.25 * Math.sin(k * 40));
      draw(b, a, (2.2 + run.lvl * 0.6) * dpr);
    }
    raf = requestAnimationFrame(frame);
  }

  // ---------- count-up ----------
  function countUp(to, ms) {
    return new Promise((resolve) => {
      const t0 = performance.now(); let skip = false;
      amountEl._skip = () => { skip = true; };
      const tick = (t) => {
        const k = skip ? 1 : Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
        amountEl.textContent = UI.fmt(to * e);
        if (k < 1) requestAnimationFrame(tick); else resolve();
      };
      requestAnimationFrame(tick);
    });
  }

  async function scene(key, amount) {
    const t = TIERS[key];
    root.dataset.tier = key; root.dataset.lvl = String(t.lvl);
    root.style.setProperty('--title-k', String(t.scale));
    title.src = `${POP}${t.img}.webp?v=1`;
    amountEl.textContent = '';
    root.querySelectorAll('.t2pop__cl').forEach((c) => c.classList.toggle('is-used', +c.dataset.i < [0, 2, 4, 4, 6][t.lvl]));
    root.classList.remove('is-in', 'is-out', 'can-close');
    UI.dim(true);
    root.hidden = false; resize();
    void root.offsetWidth; root.classList.add('is-in');
    if (window.Sound) try { Sound.playSfx(t.sound); } catch (e) {}
    if (window.OTSpine) OTSpine.celebrate(key === 'mini' || key === 'minor' || key === 'major' || key === 'grand' ? 'jackpot' : key);
    run = { lvl: t.lvl }; bolts = []; nextAt = performance.now() + 250; raf = requestAnimationFrame(frame);
    const counting = amount != null ? countUp(amount, t.ms) : Promise.resolve();
    await new Promise((resolve) => {
      let ready = false;
      const close = () => {
        if (!ready) { if (amountEl._skip) amountEl._skip(); return; }
        root.removeEventListener('click', close); resolve();
      };
      root.addEventListener('click', close);
      counting.then(() => { ready = true; root.classList.add('can-close'); if (!window.__holdPop) setTimeout(close, 1800 + t.lvl * 400); });
    });
    // the storm leaves the way it came: clouds back to the corners, bolts stop, title out
    root.classList.add('is-out'); run = null;
    await new Promise((r) => setTimeout(r, 650));
    cancelAnimationFrame(raf); ctx.clearRect(0, 0, cv.width, cv.height);
    root.hidden = true; root.classList.remove('is-in', 'is-out', 'is-shake');
    if (window.OTSpine) OTSpine.celebrate(null);
    UI.dim(false);
    if (window.Sound) try { Sound.playSfx('popupClose'); } catch (e) {}
  }

  UI.popup = function (kind, opts = {}) {
    if (kind === 'big' || kind === 'mega' || kind === 'epic') return scene(kind, opts.amount);
    if (kind === 'jackpot') {
      const m = /MINI|MINOR|MAJOR|GRAND/.exec(opts.sub || '');
      return scene(m ? m[0].toLowerCase() : 'mini', opts.amount);
    }
    return orig.call(UI, kind, opts);
  };
  addEventListener('resize', () => { if (!root.hidden) resize(); });

  // ---------- preview buttons in the presentation switches (stop the click before the switch handler) ----------
  const box = document.getElementById('demoSwitch');
  if (box) {
    const row = document.createElement('div');
    row.innerHTML = '<b>Popups</b>' + ['big', 'mega', 'epic', 'mini', 'minor', 'major', 'grand']
      .map((k) => `<button type="button" data-pop="${k}">${k[0].toUpperCase() + k.slice(1)}</button>`).join('');
    box.appendChild(row);
    row.querySelectorAll('button').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      const k = b.dataset.pop, base = 10000;
      const amt = { big: 15, mega: 40, epic: 120, mini: 20, minor: 50, major: 250, grand: 1000 }[k] * base;
      if (k === 'big' || k === 'mega' || k === 'epic') UI.popup(k, { amount: amt });
      else UI.popup('jackpot', { amount: amt, sub: `${k.toUpperCase()} JACKPOT` });
    }));
  }
  // screenshots / Figma export: stop the loop and leave a fixed set of bolts on the canvas
  function still(n) {
    run = null; cancelAnimationFrame(raf); bolts = [];
    const lvl = +(root.dataset.lvl || 1);
    for (let i = 0; i < (n || lvl + 1); i++) spawn(lvl);
    ctx.clearRect(0, 0, cv.width, cv.height);
    bolts.forEach((b) => draw(b, 1, (2.2 + lvl * 0.6) * dpr));
  }
  window.T2Pop = { scene, still };
})();
