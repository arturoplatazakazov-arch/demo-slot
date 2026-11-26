// Neon Joker Spins R1 — concert spotlights for Hold & Win (2026-11-26): the round plays on the concert
// stage, so stage lights shine in from beyond the screen edges and sweep across the scene.
//   between respins  slow, soft sweeps behind the reels
//   during a respin  (cells with .is-hw-spin) faster, brighter, a light strobe, extra thin beams over the stage
//   a coin lands     (.is-slam) all beams flash once
// Pure CSS beams (css/njs-r1.css .r1-lights); this file only builds them and flips the state classes.
(function () {
  const screen = document.getElementById('screen');
  const reel = document.getElementById('reel');
  const fxBack = document.getElementById('fxBack');
  if (!screen || !reel) return;
  // [side, x% of the screen width, angle range (deg), colour, delay (s)]
  const BACK = [
    ['l', -4, [-38, 8], '255, 60, 172', 0],
    ['l', 14, [-28, 18], '44, 232, 255', -1.7],
    ['m', 50, [-24, 24], '255, 236, 190', -0.6],
    ['r', 86, [-18, 28], '170, 90, 255', -2.4],
    ['r', 104, [-8, 38], '255, 60, 172', -1.1],
  ];
  const FRONT = [
    ['l', 6, [-30, 12], '44, 232, 255', -0.4],
    ['r', 94, [-12, 30], '255, 180, 90', -1.3],
  ];
  const build = (cls, list) => {
    const el = document.createElement('div');
    el.className = `layer r1-lights ${cls}`;
    el.innerHTML = list.map(([side, x, [a0, a1], rgb, d]) =>
      `<i class="r1-beam r1-beam--${side}" style="left:${x}%;--a0:${a0}deg;--a1:${a1}deg;--c:${rgb};--d:${d}s"></i>`).join('');
    return el;
  };
  const back = build('r1-lights--back', BACK);
  const front = build('r1-lights--front', FRONT);
  (fxBack || screen.firstChild).after(back);
  screen.appendChild(front);

  let raf = 0;
  const sync = () => {
    raf = 0;
    const spinning = !!reel.querySelector('.reel__cell.is-hw-spin');
    document.body.classList.toggle('r1-hw-spinning', spinning);
    if (reel.querySelector('.reel__cell.is-slam')) {
      [back, front].forEach((l) => { l.classList.remove('is-flash'); void l.offsetWidth; l.classList.add('is-flash'); });
    }
  };
  new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(sync); })
    .observe(reel, { attributes: true, subtree: true, attributeFilter: ['class'] });

  // respins back to 3 (slot.js awaits NJS_HOOKS.respinReset): a burst of wild sweeps, then every beam
  // swings onto the RESPINS counter and the number rolls up to 3 under the light, then the show goes on
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const beams = () => [...document.querySelectorAll('.r1-beam')];
  async function respinReset(from, to, turbo) {
    const k = turbo ? 0.5 : 1;
    const counter = document.querySelector('.r1-count .r1-resp');
    const num = counter && counter.querySelector('.r1-cnt__n');
    [back, front].forEach((l) => l.classList.add('is-burst'));
    await sleep(560 * k);
    // aim: beam top centre -> counter centre (beams hang down, CSS rotate turns them clockwise)
    const target = (counter || reel).getBoundingClientRect();
    const tx = target.left + target.width / 2, ty = target.top + target.height / 2;
    for (const b of beams()) {
      const lr = b.parentElement.getBoundingClientRect();
      const ox = lr.left + (parseFloat(b.style.left) / 100) * lr.width, oy = lr.top - 0.14 * lr.height;
      const ang = -Math.atan2(tx - ox, ty - oy) * 180 / Math.PI;
      // the beam ends on the counter's top edge, so its label and number stay readable in the light
      const ey = target.top + 4;
      b.style.height = `${(ey - oy) / Math.cos(ang * Math.PI / 180)}px`;
      const cur = getComputedStyle(b).rotate;
      b.style.animation = 'none';
      b.style.rotate = cur === 'none' ? '0deg' : cur;
      void b.offsetWidth;
      b.style.transition = `rotate ${Math.round(420 * k)}ms cubic-bezier(.3, .8, .3, 1), opacity 260ms ease`;
      b.style.rotate = `${ang.toFixed(1)}deg`;
    }
    [back, front].forEach((l) => { l.classList.remove('is-burst'); l.classList.add('is-focus'); });
    await sleep(440 * k);
    if (counter) counter.classList.add('is-spot');
    spot.style.left = `${tx}px`; spot.style.top = `${ty}px`; spot.classList.add('is-on');
    // the number rolls up step by step: 0 -> 1 -> 2 -> 3
    for (let v = Math.max(0, from) + 1; v <= to; v++) {
      if (num && typeof setGlyphs === 'function') setGlyphs(num, String(v));
      if (typeof Sound !== 'undefined' && Sound.blip) Sound.blip(660 + v * 180);
      await sleep(230 * k);
    }
    if (from >= to && num) { num.classList.remove('is-tick'); void num.offsetWidth; num.classList.add('is-tick'); }
    await sleep(380 * k);
    // release: fade the beams, hand them back to their sweep, fade in
    [back, front].forEach((l) => l.classList.add('is-hide'));
    await sleep(180);
    for (const b of beams()) { b.style.animation = ''; b.style.rotate = ''; b.style.transition = ''; b.style.height = ''; }
    [back, front].forEach((l) => l.classList.remove('is-focus', 'is-hide'));
    if (counter) counter.classList.remove('is-spot');
    spot.classList.remove('is-on');
  }
  const spot = document.createElement('div');
  spot.className = 'r1-spot';
  document.body.appendChild(spot);
  window.NJS_HOOKS = Object.assign(window.NJS_HOOKS || {}, { respinReset });
})();
