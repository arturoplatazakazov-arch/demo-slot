// Living background for the Savannah variants (first used by "lodge", V6).
// A DOM layer between the painted background and the stage, placed in the
// background's own pixel space so it follows object-fit: cover on any screen:
//   - leopard asleep on the acacia (sprite over the painted one) that now and
//     then lifts its head and looks at the player (cross-fade of two poses);
//   - herds (zebra, impala, elephant, giraffe) walking along the horizon in
//     both directions; an elephant sometimes stops at the waterhole;
//   - flocks of birds crossing the sky (daytime only).
// Config: window.SK_LIVING_BG = { root, desk: {...}, mob: {...} } (see
// savannah-lodge.html). window.SK_LIVING exposes leopard()/herd()/birds() for
// the DEMO panel. prefers-reduced-motion: only the leopard, no walkers.
(function () {
  const C = window.SK_LIVING_BG;
  const screen = document.getElementById('screen');
  if (!C || !screen) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const FX = `${C.root}/fx`;

  const layer = document.createElement('div');
  layer.className = 'living';
  (document.getElementById('bgBonus') || screen.firstChild).after(layer);

  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const isNight = () => screen.dataset.mode === 'freespins';
  const cfg = () => {
    const c = document.body.classList.contains('is-portrait') ? C.mob : C.desk;
    return isNight() && c.night ? { ...c, ...c.night } : c;    // night art may differ
  };

  // Background px -> screen px (object-fit: cover, object-position 50% Y%).
  function map() {
    const c = cfg();
    const W = screen.clientWidth, H = screen.clientHeight;
    const s = Math.max(W / c.size[0], H / c.size[1]);
    return { c, s, ox: (W - c.size[0] * s) * 0.5, oy: (H - c.size[1] * s) * (C.posY || 0.58) };
  }

  // --- leopard ---------------------------------------------------------------
  const leo = document.createElement('div');
  leo.className = 'living__leo';
  leo.innerHTML = `<img class="living__leo-sleep" src="${FX}/leopard_sleep.webp" alt="">`
    + `<img class="living__leo-awake" src="${FX}/leopard_awake.webp" alt="">`;
  layer.appendChild(leo);
  function placeLeo() {
    const { c, s, ox, oy } = map();
    const [x, y, w, flip, rot] = c.leopard;
    // leopardCut: the sprite without its own branch (fx/*_cut.webp) lies on
    // the painted branch, aligned to its top edge.
    const suf = c.leopardCut ? '_cut' : '';
    leo.querySelector('.living__leo-sleep').src = `${FX}/leopard_sleep${suf}.webp`;
    leo.querySelector('.living__leo-awake').src = `${FX}/leopard_awake${suf}.webp`;
    Object.assign(leo.style, {
      left: `${ox + x * s}px`, top: `${oy + y * s}px`, width: `${w * s}px`,
      scale: flip ? '-1 1' : '', rotate: rot ? `${rot}deg` : '',
    });
    leo.classList.toggle('is-fade', !!c.leopardFade);     // soften the branch stub at the frame
    // Never under the slot: if the reel frame reaches the leopard (short
    // phones), drop it just below the frame.
    const fr = document.querySelector('.reel__frame');
    if (fr && document.body.classList.contains('is-portrait')) {
      const fb = fr.getBoundingClientRect().bottom - screen.getBoundingClientRect().top;
      const h = w * s * (505 / 640);
      const bodyTop = oy + y * s + 0.06 * h;
      leo.dataset.shift = '0';
      if (bodyTop < fb + 6) { leo.style.top = `${oy + y * s + (fb + 6 - bodyTop)}px`; leo.dataset.shift = String(Math.round(fb + 6 - bodyTop)); }
    }
  }
  let leoTimer = null;
  function leopard() {
    leo.classList.add('is-up');
    setTimeout(() => leo.classList.remove('is-up'), rnd(2600, 4200));
  }
  (function loop() { leoTimer = setTimeout(() => { leopard(); loop(); }, rnd(9000, 17000)); })();

  // --- herds -----------------------------------------------------------------
  // Walk cycle without frames: each sprite is cut by clip-path into the body
  // (above `hip`) and two leg groups split at `mid` (hind / fore, sprites face
  // right). The leg groups swing in opposite phase (skewX from the hip line),
  // the body bobs twice per stride and long necks nod. `gait` = stride, s.
  const SPECIES = {
    zebra: { files: ['zebra1', 'zebra2', 'zebra3'], h: 54, speed: 26, group: [2, 4], hip: 0.6, mid: 0.46, swing: 13, gait: 0.82, ar: 1.08 },
    impala: { files: ['impala1', 'impala2', 'impala3'], h: 48, speed: 40, group: [2, 5], hip: 0.52, mid: 0.55, swing: 15, gait: 0.62, ar: 1.05 },
    elephant: { files: ['elephant1', 'elephant2'], h: 66, speed: 16, group: [1, 2], drink: true, hip: 0.66, mid: 0.5, swing: 8, gait: 1.25, nod: 1.2, ar: 1.42 },
    giraffe: { files: ['giraffe'], h: 108, speed: 20, group: [1, 1], hip: 0.6, mid: 0.5, swing: 10, gait: 1.1, nod: 1.6, ar: 0.68 },
  };
  function walker(src, sp, h) {
    const el = document.createElement('div');
    el.className = 'living__walker';
    el.style.cssText = `height:${h}px; --hip:${sp.hip * 100}%; --mid:${sp.mid * 100}%; --sw:${sp.swing}deg;`
      + ` --gait:${(sp.gait * rnd(0.92, 1.08)).toFixed(2)}s; --nod:${sp.nod || 0.4}deg; animation-delay:${-rnd(0, 1).toFixed(2)}s;`;
    el.innerHTML = `<img class="w-body" src="${src}" alt=""><img class="w-legs w-legs--hind" src="${src}" alt="">`
      + `<img class="w-legs w-legs--fore" src="${src}" alt="">`;
    return el;
  }
  // One ground plane: every walker stands on c.horizon (no jitter), scaled to
  // the far plain by c.animalK, one herd on screen at a time (so herds never
  // cross through each other), members in single file with a clear gap.
  function herd(kind, force) {
    const busy = layer.querySelector('.living__walker');
    if (busy && !force) return;
    if (force) layer.querySelectorAll('.living__walker').forEach((e) => e.remove());
    const { c, s, ox, oy } = map();
    const sp = SPECIES[kind] || SPECIES[pick(['zebra', 'zebra', 'impala', 'impala', 'elephant', 'giraffe'])];
    const toRight = Math.random() < 0.5;
    const n = Math.round(rnd(sp.group[0], sp.group[1]));
    const ground = oy + c.horizon * s;
    const h = sp.h * (c.animalK || 1) * s;
    const w = h * sp.ar;
    const W = screen.clientWidth;
    const speed = sp.speed * s * 1.1;                          // px/s
    const drinkX = sp.drink && Math.random() < 0.7 ? ox + c.waterX * s : null;
    let lead = 0;
    for (let i = 0; i < n; i++) {
      const el = walker(`${FX}/${pick(sp.files)}.webp`, sp, h);
      el.style.top = `${ground - h * 0.985}px`;           // hooves on the ground line
      if (!toRight) el.style.scale = '-1 1';              // sprites face right
      layer.appendChild(el);
      const gap = lead;
      lead += w * rnd(1.25, 1.6);                          // single file, never overlapping
      const x0 = toRight ? -w - gap : W + gap;
      const x1 = toRight ? W + 20 : -w - 20;
      const dist = Math.abs(x1 - x0);
      const dur = dist / speed * 1000;
      let frames, D = dur;
      if (drinkX == null) {
        frames = [{ translate: `${x0}px 0` }, { translate: `${x1}px 0` }];
      } else {
        const stop = drinkX + (toRight ? -gap : gap);
        const t1 = Math.abs(stop - x0) / speed * 1000, pause = 6000;
        D = dur + pause;
        frames = [{ translate: `${x0}px 0`, offset: 0 }, { translate: `${stop}px 0`, offset: t1 / D },
          { translate: `${stop}px 0`, offset: (t1 + pause) / D }, { translate: `${x1}px 0`, offset: 1 }];
        setTimeout(() => el.classList.add('is-still'), t1);   // legs rest while it drinks
        setTimeout(() => el.classList.remove('is-still'), t1 + pause);
      }
      const a = el.animate(frames, { duration: D, easing: 'linear' });
      a.onfinish = () => el.remove();
    }
  }

  // --- birds -----------------------------------------------------------------
  function birds() {
    if (isNight()) return;
    const { c, s, ox, oy } = map();
    const W = screen.clientWidth;
    const toRight = Math.random() < 0.5;
    const n = Math.round(rnd(3, 6));
    const y0 = oy + rnd(c.sky[0], c.sky[1]) * s;
    const size = rnd(11, 17) * s * 1.6 * (c.birdK || 1);   // far away: small, high
    const dur = rnd(16000, 24000);
    for (let i = 0; i < n; i++) {
      const b = document.createElement('div');
      b.className = 'living__bird';
      b.innerHTML = '<svg viewBox="0 0 24 10"><path d="M0 7 Q6 0 12 7 Q18 0 24 7"/></svg>';
      b.style.width = `${size * rnd(0.8, 1.1)}px`;
      b.style.animationDelay = `${-rnd(0, 0.6)}s`;
      layer.appendChild(b);
      const dy = (i % 2 ? 1 : -1) * Math.ceil(i / 2) * size * 0.7;
      const dx = i * size * 0.9;
      const x0 = toRight ? -80 - dx : W + 80 + dx, x1 = toRight ? W + 80 : -80 - dx * 2;
      const lift = rnd(-60, 30) * s;
      const a = b.animate([
        { translate: `${x0}px ${y0 + dy}px` },
        { translate: `${(x0 + x1) / 2}px ${y0 + dy + lift}px` },
        { translate: `${x1}px ${y0 + dy}px` },
      ], { duration: dur, easing: 'linear' });
      a.onfinish = () => b.remove();
    }
  }

  // Foreground on the walking line (c.occ, bg px ranges: trunks, the painted
  // herds that stand nearer): a walker that reaches one fades out and comes
  // back past it, so it never walks over something in front of it.
  function occlude() {
    const ws = layer.querySelectorAll('.living__walker');
    if (ws.length) {
      const { c, s, ox } = map();
      const occ = c.occ || [];
      const L = layer.getBoundingClientRect().left;
      ws.forEach((el) => {
        const r = el.getBoundingClientRect();
        const a = (r.left - L - ox) / s, b = (r.right - L - ox) / s;
        const hit = occ.some(([x0, x1]) => a < x1 && b > x0);
        el.classList.toggle('is-behind', hit);
      });
    }
    requestAnimationFrame(occlude);
  }
  requestAnimationFrame(occlude);

  // c.logo = [cx, cy, w] in bg px: the desktop logo is pinned to a spot of
  // the painted scene (over the birds), whatever the screen ratio. The logo
  // lives in the scaled stage, so bg px -> screen px -> stage px.
  const logoEl = document.querySelector('.stage .logo:not(.logo--wide)');
  function placeLogo() {
    const { c, s, ox, oy } = map();
    if (!logoEl || !c.logo || document.body.classList.contains('is-portrait')) return;
    const st = logoEl.offsetParent.getBoundingClientRect();
    const k = st.width / logoEl.offsetParent.offsetWidth;          // stage scale
    const L = layer.getBoundingClientRect();
    const [cx, cy, w] = c.logo;
    const ww = w * s / k, hh = ww * (logoEl.naturalHeight / logoEl.naturalWidth || 0.704);
    const sx = (L.left + ox + cx * s - st.left) / k, sy = (L.top + oy + cy * s - st.top) / k;
    Object.assign(logoEl.style, { left: `${sx - ww / 2}px`, top: `${sy - hh / 2}px`, width: `${ww}px`, zIndex: '8' });
  }
  function layoutAll() { placeLeo(); placeLogo(); }
  // layouts.js re-arranges (and clears inline styles) on resize: pin after it.
  addEventListener('resize', () => setTimeout(placeLogo, 60));
  addEventListener('resize', layoutAll);
  new MutationObserver(layoutAll).observe(document.body, { attributes: true, attributeFilter: ['class'] });
  new MutationObserver(() => {
    layer.classList.toggle('is-night', isNight()); layoutAll();
    layer.querySelectorAll('.living__walker').forEach((e) => e.remove());   // night ground line differs
  })
    .observe(screen, { attributes: true, attributeFilter: ['data-mode'] });
  layoutAll();
  addEventListener('load', () => setTimeout(layoutAll, 300));
  setTimeout(layoutAll, 800);

  if (!reduce) {
    (function walk() { setTimeout(() => { if (!document.hidden) herd(); walk(); }, rnd(7000, 13000)); })();
    (function fly() { setTimeout(() => { if (!document.hidden) birds(); fly(); }, rnd(9000, 16000)); })();
    setTimeout(() => herd('zebra'), 1500);
    setTimeout(birds, 3500);
  }
  window.SK_LIVING = { leopard, herd: (k) => herd(k, true), birds };
})();
