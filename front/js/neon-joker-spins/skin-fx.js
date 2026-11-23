// Neon Joker Spins skins — casino life on the reels (skin A for now; the
// skin page sets window.NJS_SKIN). CSS for the states lives in the skin's
// stylesheet (scripts/neon_joker_spins_skins.py EXTRA_CSS); here only what
// needs the DOM:
//   - glints: a light sweep clipped to the symbol's own silhouette (mask =
//     the symbol picture), a couple of random symbols every ~1.7 s while the
//     reels stand still;
//   - win sparkles: neon stars burst out of a winning cell and the cell gets
//     a glint, every time slot.js pulses it (.is-winning).
(function () {
  const SKINS = { a: true };
  if (!SKINS[window.NJS_SKIN]) return;
  document.body.classList.add(`skin-${window.NJS_SKIN}-fx`);

  const reel = document.getElementById('reel');
  if (!reel) return;
  const spinning = () => !!reel.querySelector('.reel__strip.is-looping, .reel__strip.is-fast');
  const SPECIAL = new Set(['wild', 'scatter', 'coin', 'collector', 'seven', 'jackpot']);

  function glint(cell, delay = 0) {
    const img = cell.querySelector(':scope > img.sym');
    if (!img || !img.currentSrc || cell.querySelector(':scope > .sym-glint')) return;
    const g = document.createElement('div');
    g.className = 'sym-glint';
    g.style.left = `${img.offsetLeft}px`;
    g.style.top = `${img.offsetTop}px`;
    g.style.width = `${img.offsetWidth}px`;
    g.style.height = `${img.offsetHeight}px`;
    const mask = `url("${img.currentSrc}") center / contain no-repeat`;
    g.style.webkitMask = mask;
    g.style.mask = mask;
    g.style.animationDelay = `${delay}ms`;
    cell.appendChild(g);
    setTimeout(() => g.remove(), 1000 + delay);
  }

  function sparkles(cell, n = 7) {
    if (cell.querySelectorAll(':scope > .sym-spark').length > n) return;  // one burst per pulse
    const w = cell.offsetWidth;
    const h = cell.offsetHeight;
    for (let i = 0; i < n; i++) {
      const s = document.createElement('div');
      s.className = 'sym-spark';
      const a = (Math.PI * 2 * i) / n + Math.random() * 0.6;
      const r = 0.32 + Math.random() * 0.2;
      s.style.left = `${w / 2}px`;
      s.style.top = `${h / 2}px`;
      s.style.setProperty('--dx', `${Math.cos(a) * w * r}px`);
      s.style.setProperty('--dy', `${Math.sin(a) * h * r}px`);
      s.style.setProperty('--s', (0.6 + Math.random() * 0.7).toFixed(2));
      s.style.animationDelay = `${Math.round(Math.random() * 120)}ms`;
      if (i % 2) s.classList.add('is-cyan');
      cell.appendChild(s);
      setTimeout(() => s.remove(), 900);
    }
  }

  // idle glints — specials a bit more often
  setInterval(() => {
    if (document.hidden || spinning() || document.body.classList.contains('is-feature-screen')) return;
    const cells = [...reel.querySelectorAll('.reel__cell')].filter((c) => {
      const r = c.getBoundingClientRect();
      const rr = reel.getBoundingClientRect();
      return r.top >= rr.top - 2 && r.bottom <= rr.bottom + 2 && !c.classList.contains('is-empty');
    });
    if (!cells.length) return;
    const pick = () => {
      const sp = cells.filter((c) => SPECIAL.has(c.dataset.symbol));
      const pool = sp.length && Math.random() < 0.55 ? sp : cells;
      return pool[Math.floor(Math.random() * pool.length)];
    };
    glint(pick());
    if (Math.random() < 0.6) glint(pick(), 380);
  }, 1700);

  // win pulses: slot.js re-adds .is-winning on every pulse of a winning cell
  new MutationObserver((list) => {
    for (const m of list) {
      const c = m.target;
      if (m.attributeName !== 'class' || !c.classList.contains('reel__cell')) continue;
      const was = (m.oldValue || '').split(' ').includes('is-winning');
      if (c.classList.contains('is-winning') && !was) {
        sparkles(c);
        glint(c, 120);
      }
    }
  }).observe(reel, { subtree: true, attributes: true, attributeFilter: ['class'], attributeOldValue: true });
})();
