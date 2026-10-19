// Neon Joker Spins skins — a living mascot from ONE flat picture.
//
// The CSS idle used to bob and rotate the whole image, so the hero floated.
// Here the picture is redrawn every frame as thin horizontal strips on a
// canvas, each strip shifted / stretched by how high it sits above the floor:
// the boots never move (weight 0 at the soles), the legs barely, the torso and
// head carry the motion. That gives
//   - breathing: the chest band stretches a little, shoulders rise with it;
//   - weight shift: a slow sway from the ankles, bigger at the head;
//   - head follow-through: the head lags the body and nods a touch;
//   - win: a springy knee bend, then the body straightens and leans back;
//   - near-win: a slow lean towards the reels while the last reel spins.
// slot.js calls NJS_MASCOT.react(clip) / .near(on); the base game (Spine rig)
// does not load this file.
(function () {
  const img = document.getElementById('mascot');
  if (!img) return;

  const STRIP = 3;            // source px per strip
  const PAD = 0.06;           // canvas margin (fraction of the drawn height) for the sway
  const TAU = Math.PI * 2;
  const smooth = (a, b, x) => {
    const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
    return t * t * (3 - 2 * t);
  };

  let canvas = null;
  let ctx = null;
  let box = null;             // drawn image rect inside the img box (stage px)
  let reacts = [];            // active win reactions {t0, k}
  let nearTarget = 0;
  let near = 0;
  let last = performance.now();

  function layout() {
    const bw = img.offsetWidth;
    const bh = img.offsetHeight;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    if (!bw || !bh || !iw) return false;
    // object-fit: contain + object-position: 50% 100% (skin CSS)
    const s = Math.min(bw / iw, bh / ih);
    const dw = iw * s;
    const dh = ih * s;
    const pad = dh * PAD;
    box = { x: img.offsetLeft + (bw - dw) / 2, y: img.offsetTop + bh - dh, w: dw, h: dh, pad };
    canvas.style.left = `${box.x - pad}px`;
    canvas.style.top = `${box.y - pad}px`;
    canvas.style.width = `${dw + 2 * pad}px`;
    canvas.style.height = `${dh + pad}px`;
    const stage = document.getElementById('stage');
    const k = (stage.getBoundingClientRect().width / stage.offsetWidth || 1) * (window.devicePixelRatio || 1);
    const res = Math.min(2, Math.max(0.5, k));
    canvas.width = Math.round((dw + 2 * pad) * res);
    canvas.height = Math.round((dh + pad) * res);
    ctx.setTransform(res, 0, 0, res, 0, 0);
    ctx.imageSmoothingQuality = 'high';
    return true;
  }

  // Win reaction: damped spring — knees give (legs shorten), then the body
  // springs up a little past rest and leans back, settling in ~1.4 s.
  function reaction(t) {
    let legs = 0;
    let stretch = 0;
    let lean = 0;
    reacts = reacts.filter((r) => t - r.t0 < 1.8);
    for (const r of reacts) {
      const u = t - r.t0;
      const spring = Math.exp(-3.2 * u) * Math.sin(TAU * u / 0.62);
      legs += r.k * 0.045 * Math.max(0, spring);          // knee bend (down phase)
      stretch += r.k * 0.022 * Math.max(0, -spring);      // springing up
      lean += r.k * 0.03 * Math.exp(-2.2 * u) * Math.sin(Math.PI * Math.min(1, u / 0.45));
    }
    return { legs, stretch, lean };
  }

  function draw(now) {
    if (!box || !img.offsetWidth) {   // portrait: the mascot is hidden
      requestAnimationFrame(draw);
      return;
    }
    const t = now / 1000;
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    // near-win lean eases in and out (critically damped)
    near += (nearTarget - near) * (1 - Math.exp(-dt * 3));

    const { w, h, pad } = box;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    const r = reaction(t);
    const breath = 0.5 - 0.5 * Math.cos(TAU * t / 3.8);                          // 0..1
    const sway = 0.6 * Math.sin(TAU * t / 7.3) + 0.4 * Math.sin(TAU * t / 4.1 + 1.1);
    const swayLag = 0.6 * Math.sin(TAU * (t - 0.45) / 7.3) + 0.4 * Math.sin(TAU * (t - 0.45) / 4.1 + 1.1);
    const nod = Math.sin(TAU * t / 5.3 + 0.7);

    ctx.clearRect(0, 0, w + 2 * pad, h + pad);
    // walk strips from the soles up, stacking their (stretched) heights
    let y = h + pad;
    for (let sy = ih; sy > 0; sy -= STRIP) {
      const sh = Math.min(STRIP, sy);
      const hy = 1 - (sy - sh / 2) / ih;                 // 0 at the soles, 1 at the hat
      let sc = 1;
      sc *= 1 - r.legs * (smooth(0.06, 0.18, hy) - smooth(0.36, 0.48, hy)) * 2.2;  // knees
      sc *= 1 + 0.014 * breath * (smooth(0.48, 0.58, hy) - smooth(0.74, 0.84, hy)); // chest
      sc *= 1 + r.stretch * smooth(0.3, 0.6, hy);
      const body = Math.pow(smooth(0.08, 1, hy), 1.35);    // 0 at the boots
      const head = smooth(0.76, 0.95, hy);
      const dx = h * (
        0.0085 * sway * body
        + 0.004 * swayLag * head
        + 0.0025 * nod * head
        - r.lean * body
        + 0.014 * near * body
      );
      const dh = (sh * h / ih) * sc;
      y -= dh;
      ctx.drawImage(img, 0, sy - sh, iw, sh, pad + dx, y, w, dh + 0.6);
    }
    requestAnimationFrame(draw);
  }

  function start() {
    canvas = document.createElement('canvas');
    canvas.className = 'obj mascot-live';
    canvas.setAttribute('aria-hidden', 'true');
    img.after(canvas);
    ctx = canvas.getContext('2d');
    img.classList.add('is-live');
    canvas.style.filter = getComputedStyle(img).filter;
    if (!layout()) box = null;
    window.addEventListener('resize', () => requestAnimationFrame(() => { if (!layout()) box = null; }));
    requestAnimationFrame(draw);
  }

  window.NJS_MASCOT = {
    react(clip) {
      const k = clip === 'win' || clip === 'laugh' ? 1.35 : 1;
      reacts.push({ t0: performance.now() / 1000, k });
    },
    near(on) { nearTarget = on ? 1 : 0; },
  };

  if (img.complete && img.naturalWidth) start();
  else img.addEventListener('load', start, { once: true });
})();
