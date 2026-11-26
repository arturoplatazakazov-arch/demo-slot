// Neon Joker Spins R1 — screen switches behind a pair of panels (2026-11-26):
//   Hold & Win (the concert stage)  -> two velvet stage curtains glide shut and open
//   Free Spins (the dressing room)  -> two heavy metal backstage doors slam shut (a little bounce) and slide open
// app.js / slot.js call NJS_HOOKS.curtain(fn, kind) where the screen switches; fn swaps the screen while
// the panels are shut. Covers the whole window, above everything.
(function () {
  const screen = document.getElementById('screen');
  if (!screen) return;
  const ART = {
    hw: 'img/neon-joker-spins/skins/c/sets/r1/img/curtain.webp?v=1',
    hwPlain: 'img/neon-joker-spins/skins/c/sets/r1/img/curtain_plain.webp?v=1',   // phones: just the fabric
    fs: 'img/neon-joker-spins/skins/c/sets/r1/img/door.webp?v=2',                  // no neon, no tags
  };
  const TIME = { hw: [620, 260, 760], fs: [520, 320, 640] };     // close, hold, open (ms)
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  Object.values(ART).forEach((u) => { const i = new Image(); i.src = u; });

  const root = document.createElement('div');
  root.className = 'r1-curtain';
  root.innerHTML = '<div class="r1-curtain__half r1-curtain__half--l"></div><div class="r1-curtain__half r1-curtain__half--r"></div>';
  screen.appendChild(root);

  let busy = Promise.resolve();
  function curtain(fn, kind = 'hw') {
    const k = ART[kind] ? kind : 'hw';
    const [CLOSE, HOLD, OPEN] = TIME[k];
    const run = async () => {
      // absolute url: a relative url() in a custom property resolves against the stylesheet
      const art = k === 'hw' && matchMedia('(orientation: portrait)').matches ? ART.hwPlain : ART[k];
      root.style.setProperty('--curtain', `url('${new URL(art, location.href).href}')`);
      root.style.setProperty('--close-ms', `${CLOSE}ms`);
      root.style.setProperty('--open-ms', `${OPEN}ms`);
      root.dataset.kind = k;
      root.classList.remove('is-open'); root.classList.add('is-on');
      void root.offsetWidth;
      root.classList.add('is-shut');
      if (typeof Sound !== 'undefined' && Sound.blip) Sound.blip(k === 'fs' ? 140 : 220);
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
