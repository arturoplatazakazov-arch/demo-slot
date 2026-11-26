// Neon Joker Spins R1 — Free Spins staging (client feedback, round 2, 2026-11-26):
//   intro   "FREE SPINS ×10" with the hero (pose "front"), tap or ~3 s
//   +5      retrigger burst over the reels
//   summary TOTAL WIN with the hero (pose "punk"), spins played
//   NEXT    "FREE SPINS ×10 NEXT" plate in the logo's place while a Hold & Win plays first
// app.js calls these through window.NJS_HOOKS. The base keeps the leaning hero, so every screen
// shows the punk in its own pose. Drawn in a stage-sized layer above the dim (#screen), laid out in
// design px like the stage (desktop 1600x900, portrait 720x1280, phone landscape 1600x640).
// Texts sit in STRINGS for localisation; the numbers are the game's glyph atlas (setGlyphs).
(function () {
  const screen = document.getElementById('screen');
  if (!screen || typeof setGlyphs !== 'function') return;
  const HERO = 'img/neon-joker-spins/skins/c/sets/r1/heroes';
  const POP = 'img/neon-joker-spins/skins/c/popups';
  const STRINGS = {
    en: { tap: 'TAP TO CONTINUE', played: (n) => `${n} FREE SPINS PLAYED`, next: 'NEXT', spins: 'FREE SPINS', maxWin: 'MAX WIN 2 500X' },
  };
  const LANG = (new URLSearchParams(location.search).get('lang') || navigator.language || 'en').slice(0, 2).toLowerCase();
  const T = STRINGS[LANG] || STRINGS.en;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const layer = document.createElement('div');
  layer.className = 'r1-scenes';
  screen.appendChild(layer);
  [`${HERO}/front.webp?v=1`, `${HERO}/punk.webp?v=1`, `${POP}/freeSpins.webp?v=3`, `${POP}/totalWin.webp?v=3`, `${POP}/panel.webp?v=3`]
    .forEach((u) => { const i = new Image(); i.src = u; });

  // a full screen: hero + sign + glyph panel (+ lines); resolves after holdMs or a tap
  function scene({ cls, hero, sign, value, count, lines, holdMs }) {
    return new Promise((resolve) => {
      const el = document.createElement('div');
      el.className = `r1-scene r1-scene--${cls}`;
      el.innerHTML = `<img class="r1-scene__hero" src="${HERO}/${hero}.webp?v=1" alt="">
        <div class="r1-scene__col">
          <img class="r1-scene__sign" src="${POP}/${sign}.webp?v=3" alt="">
          <div class="r1-scene__panel"><span class="glyphs r1-scene__value"></span></div>
          ${lines.map((l) => `<div class="r1-scene__line">${l}</div>`).join('')}
          <div class="r1-scene__tap">${T.tap}</div>
        </div>`;
      layer.appendChild(el);
      const v = el.querySelector('.r1-scene__value');
      if (window.r1FitGlyphs) window.r1FitGlyphs(v, el.querySelector('.r1-scene__panel'), 0.78);
      if (count && typeof countUp === 'function') { setGlyphs(v, '0'); countUp(v, value, Math.min(1400, holdMs * 0.5)); } else setGlyphs(v, String(value));
      if (typeof pushScreenDim === 'function') pushScreenDim();
      document.body.classList.add('r1-scene-on');   // the base (leaning) hero steps out while the punk is on screen
      if (typeof Sound !== 'undefined' && Sound.playSfx) Sound.playSfx('popupOpen');
      void el.offsetWidth;
      el.classList.add('is-in');
      let done = false;
      const close = async () => {
        if (done) return;
        done = true;
        screen.removeEventListener('pointerdown', close);
        if (count) setGlyphs(v, formatAmount(value));
        el.classList.remove('is-in');
        el.classList.add('is-out');
        await sleep(320);
        el.remove();
        if (!layer.querySelector('.r1-scene')) document.body.classList.remove('r1-scene-on');
        if (typeof popScreenDim === 'function') popScreenDim();
        resolve();
      };
      setTimeout(() => screen.addEventListener('pointerdown', close), 500);
      setTimeout(close, holdMs);
    });
  }

  let nextEl = null;
  window.NJS_HOOKS = {
    fsIntro: (spins) => scene({ cls: 'intro', hero: 'front', sign: 'freeSpins', value: `x${spins}`, lines: [], holdMs: 3200 }),
    fsSummary: (total, played, maxWin) => scene({
      cls: 'summary', hero: 'punk', sign: 'totalWin', value: total, count: true,
      lines: [T.played(played), ...(maxWin ? [T.maxWin] : [])], holdMs: 4200,
    }),
    async fsRetrigger(added) {
      const reel = document.getElementById('reel');
      const el = document.createElement('div');
      el.className = 'r1-plus';
      el.innerHTML = `<b>+${added}</b><span>${T.spins}</span>`;
      if (reel) {
        el.style.left = `${reel.offsetLeft + reel.offsetWidth / 2}px`;
        el.style.top = `${reel.offsetTop + reel.offsetHeight / 2}px`;
      }
      layer.appendChild(el);
      void el.offsetWidth;
      el.classList.add('is-in');
      await sleep(1500);
      el.classList.add('is-out');
      await sleep(300);
      el.remove();
    },
    fsNext(on, spins) {
      if (nextEl) { nextEl.remove(); nextEl = null; }
      document.body.classList.toggle('r1-fs-next', !!on);
      if (!on) return;
      nextEl = document.createElement('div');
      nextEl.className = 'r1-next';
      nextEl.innerHTML = `<img src="${POP}/freeSpins.webp?v=3" alt="FREE SPINS"><div class="r1-next__row"><span class="r1-next__in"><span class="glyphs"></span><b>${T.next}</b></span></div>`;
      layer.appendChild(nextEl);
      setGlyphs(nextEl.querySelector('.glyphs'), `x${spins}`);
      if (window.r1FitGlyphs) window.r1FitGlyphs(nextEl.querySelector('.r1-next__in'), nextEl.querySelector('.r1-next__row'), 0.72);
    },
  };
})();
