// Neon Joker Spins · Neon Tubes R1 — page extras for the client's round-1 feedback (2026-11-23):
// feature hints (desktop: next to the jackpots; portrait: rotating in the win strip), and a buy
// window with both bonuses. The game only sells Hold & Win, so the Free Spins card is a static
// mock of the future buy. Layout: css/njs-r1.css.
// Numbers never leave their plate (client round 2): a glyph row wider than `ratio` of its box is
// scaled down (the CSS `scale` property, so the element's own transform stays intact). Re-fits on
// every change of the row (count-ups, counters).
window.r1FitGlyphs = function (el, box, ratio = 0.8) {
  if (!el || el.__r1fit) return;
  el.__r1fit = true;
  const fit = () => {
    el.style.scale = '';
    const need = [...el.children].reduce((w, c) => w + c.getBoundingClientRect().width, 0);
    const room = (box || el.parentElement).getBoundingClientRect().width * ratio;
    el.style.scale = need > room && need > 0 ? String((room / need).toFixed(3)) : '';
  };
  new MutationObserver(() => requestAnimationFrame(fit)).observe(el, { childList: true, subtree: true });
  el.addEventListener('load', () => requestAnimationFrame(fit), true);
  window.addEventListener('resize', () => requestAnimationFrame(fit));
  requestAnimationFrame(fit);
};

(function () {
  const stage = document.getElementById('stage');
  if (!stage) return;
  const SYM = 'img/neon-joker-spins/skins/c/sets/r1/symbols';
  // Free Spins background: the dressing room (css/njs-r1.css .bg__img--room)
  const bgLayer = document.getElementById('bgLayer');
  if (bgLayer && !bgLayer.querySelector('.bg__img--room')) {
    const room = document.createElement('div');
    room.className = 'bg__img bg__img--room';
    bgLayer.appendChild(room);
  }
  // Hint texts live here, apart from the art, so they can be localised (client, round 2):
  // one dictionary per language, ?lang=xx or the browser's language, English by default.
  const STRINGS = {
    en: { fs: ['FREE SPINS', '3 JOKERS ANYWHERE'], hw: ['HOLD & WIN', 'COIN ON EVERY REEL'], respins: 'RESPINS', fsLeft: 'FREE SPINS' },
  };
  const LANG = (new URLSearchParams(location.search).get('lang') || navigator.language || 'en').slice(0, 2).toLowerCase();
  const T = STRINGS[LANG] || STRINGS.en;
  // the condition is drawn as well as written: 3 jokers / a coin in each of the 3 reels
  const HINTS = [
    { cls: 'fs', img: `${SYM}/scatter.webp?v=3`, slots: false, what: T.fs[0], sub: T.fs[1] },
    { cls: 'hw', img: `${SYM}/coin.webp?v=3`, slots: true, what: T.hw[0], sub: T.hw[1] },
  ];

  // Bonus HUD (client, 2026-11-23): the counter sits in the middle of the frame's bottom tube
  // (Hold & Win: plate with slots 1-2-3, the digits up to the respins left are lit, like Volt
  // Coins; Free Spins: plate with the spins left), TOTAL WIN on the info-plaque art at the side.
  // slot.js keeps driving its own #hwPanel / #fsPanel (hidden); this mirrors them.
  const G = 'img/neon-joker-spins/skins/c/glyphs';
  const UI = 'img/neon-joker-spins/skins/c/sets/r1/ui';
  const lamps = document.querySelector('#hwPanel .hw-lamps');
  const hud = document.createElement('div');
  hud.className = 'obj r1-count';
  // round 2 (client): ONE counter scheme for both bonuses, as in 3OAKS games — a plate with the
  // label and a big number of what is LEFT (no "1 2 3" lamps); it pops on every change
  hud.innerHTML = `<div class="r1-resp r1-cnt"><span class="r1-cnt__label">${T.respins}</span><span class="r1-cnt__n glyphs"></span></div>`
    + `<div class="r1-fsc r1-cnt"><span class="r1-cnt__label">${T.fsLeft}</span><span class="r1-cnt__n glyphs r1-fsc__n"></span></div>`;
  stage.appendChild(hud);
  const total = document.createElement('div');
  total.className = 'obj r1-total';
  total.innerHTML = '<div class="r1-total__face"><span class="r1-total__label">TOTAL WIN</span><span class="r1-total__value glyphs"></span></div>';
  stage.appendChild(total);
  const mirror = (src, dst) => {
    if (!src || !dst) return;
    const copy = () => { dst.innerHTML = src.innerHTML; };
    new MutationObserver(copy).observe(src, { childList: true, subtree: true, characterData: true, attributes: true });
    copy();
  };
  mirror(document.getElementById('fsLeft'), hud.querySelector('.r1-fsc__n'));
  const totalValue = total.querySelector('.r1-total__value');
  const hwTotal = document.getElementById('hwTotal');
  const fsWin = document.getElementById('fsWin');
  const screenEl = document.getElementById('screen');
  const syncTotal = () => {
    const src = screenEl.classList.contains('is-hw') ? hwTotal : fsWin;
    if (src) totalValue.innerHTML = src.innerHTML;
  };
  [hwTotal, fsWin, screenEl].forEach((el) => el && new MutationObserver(syncTotal).observe(el, el === screenEl
    ? { attributes: true, attributeFilter: ['class'] } : { childList: true, subtree: true, characterData: true }));
  syncTotal();
  // numbers stay inside their plates: TOTAL WIN, the free-spin counter, the jackpot windows
  window.r1FitGlyphs(totalValue, total.querySelector('.r1-total__face'), 0.9);
  hud.querySelectorAll('.r1-cnt').forEach((c) => window.r1FitGlyphs(c.querySelector('.r1-cnt__n'), c, 0.3));
  // pop the number whenever it changes
  hud.querySelectorAll('.r1-cnt__n').forEach((n) => new MutationObserver(() => {
    n.classList.remove('is-tick'); void n.offsetWidth; n.classList.add('is-tick');
  }).observe(n, { childList: true }));
  document.querySelectorAll('.jp__value').forEach((el) => window.r1FitGlyphs(el, el, 0.94));
  if (lamps) {
    // respins left = the lit lamps of slot.js's (hidden) panel; back to 3 = a reset flash
    const resp = hud.querySelector('.r1-resp');
    const num = resp.querySelector('.r1-cnt__n');
    const sync = () => {
      const lit = lamps.querySelectorAll('.hw-lamp.is-lit').length;
      setGlyphs(num, String(lit));
      if (lamps.classList.contains('is-reset') && !resp.classList.contains('is-reset')) {
        resp.classList.add('is-reset');
        setTimeout(() => resp.classList.remove('is-reset'), 700);
      }
    };
    new MutationObserver(sync).observe(lamps, { attributes: true, subtree: true, attributeFilter: ['class'] });
    sync();
  }

  // ONE info plaque (neon sign, img/.../r1/img/plaque.webp): FREE SPINS flickers on, holds, goes
  // dark, then HOLD & WIN does the same, round and round. Desktop: under the jackpots; phones: the
  // win strip (hidden while a win is shown and during the bonuses).
  const plaque = document.createElement('div');
  plaque.className = 'obj r1-plaque';
  plaque.innerHTML = '<div class="r1-plaque__face"><span class="r1-plaque__art"></span><span class="r1-plaque__text"><b></b><small></small></span></div>';
  stage.appendChild(plaque);
  const face = plaque.firstElementChild;
  const art = face.querySelector('.r1-plaque__art');
  const title = face.querySelector('b');
  const sub = face.querySelector('small');
  // any text, any language: the whole face shrinks to the plate when it would overflow
  window.r1FitGlyphs(face, plaque, 0.82);
  HINTS.forEach((h) => { const i = new Image(); i.src = h.img; });
  const ON_MS = 3600, OFF_MS = 520, GAP_MS = 900;
  let k = 0;
  const show = () => {
    const h = HINTS[k];
    plaque.dataset.k = h.cls;
    art.innerHTML = [0, 1, 2].map(() => `<i class="${h.slots ? 'is-slot' : ''}"><img src="${h.img}" alt=""></i>`).join('');
    title.textContent = h.what;
    sub.textContent = h.sub;
    plaque.classList.remove('is-off');
    void plaque.offsetWidth;
    plaque.classList.add('is-on');
    setTimeout(() => {
      plaque.classList.remove('is-on');
      plaque.classList.add('is-off');
      setTimeout(() => { k = (k + 1) % HINTS.length; show(); }, OFF_MS + GAP_MS);
    }, ON_MS);
  };
  show();
  // frame state: hot while a win is shown (win strip / highlighted cells) and in the bonuses
  {
    const reelEl = document.getElementById('reel');
    const winEl = document.getElementById('reelWin');
    const scr = document.getElementById('screen');
    let raf = 0;
    const hot = () => {
      raf = 0;
      const on = (winEl && winEl.classList.contains('is-on'))
        || (reelEl && !!reelEl.querySelector('.is-winning, .is-win-active'))
        || scr.classList.contains('is-hw') || scr.classList.contains('is-fs');
      document.body.classList.toggle('r1-frame-hot', on);
    };
    const later = () => { if (!raf) raf = requestAnimationFrame(hot); };
    [winEl, scr].forEach((el) => el && new MutationObserver(later).observe(el, { attributes: true, attributeFilter: ['class'] }));
    if (reelEl) new MutationObserver(later).observe(reelEl, { attributes: true, subtree: true, attributeFilter: ['class'] });
    hot();
  }
  const win = document.getElementById('reelWin');
  if (win) {
    const sync = () => plaque.classList.toggle('is-win', win.classList.contains('is-on'));
    new MutationObserver(sync).observe(win, { attributes: true, attributeFilter: ['class'] });
  }

  // buy window: FREE SPINS (mock) | HOLD & WIN (the real buy, #buyYes)
  const card = document.querySelector('#buyDialog .buy-dialog__card');
  const price = document.getElementById('buyDialogPrice');
  const cur = document.getElementById('buyDialogCur');
  const yes = document.getElementById('buyYes');
  if (card && price && yes) {
    card.classList.add('r1-buy');
    card.querySelector('.buy-dialog__title').textContent = 'BUY BONUS';
    const text = card.querySelector('.buy-dialog__text');
    if (text) text.textContent = 'Выберите бонус: Free Spins или Hold & Win.';
    const cards = document.createElement('div');
    cards.className = 'r1-buy__cards';
    cards.innerHTML = `
      <button class="r1-buy__card r1-buy__card--fs" type="button" aria-label="Buy Free Spins">
        <span class="r1-buy__price"><span id="r1BuyFs">0</span> <small></small></span></button>
      <button class="r1-buy__card r1-buy__card--hw" type="button" aria-label="Buy Hold & Win">
        <span class="r1-buy__price"></span></button>`;
    const hwPrice = cards.querySelector('.r1-buy__card--hw .r1-buy__price');
    hwPrice.append(price, ' ', cur);
    cards.querySelector('.r1-buy__card--fs small').textContent = cur.textContent;
    text.after(cards);
    const note = document.createElement('p');
    note.className = 'r1-buy__note';
    cards.after(note);
    // Free Spins mock price = 100× bet (Hold & Win costs 23.5× bet)
    const fsPrice = cards.querySelector('#r1BuyFs');
    const upd = () => {
      const v = parseFloat(price.textContent.replace(/[^\d.]/g, '')) || 0;
      fsPrice.textContent = Math.round((v / 23.5) * 100).toLocaleString('en-US');
      note.textContent = '';
    };
    new MutationObserver(upd).observe(price, { childList: true, characterData: true, subtree: true });
    upd();
    cards.querySelector('.r1-buy__card--hw').addEventListener('click', () => yes.click());
    // Free Spins: app.js reads the kind and opens the round with a forced scatter spin
    cards.querySelector('.r1-buy__card--fs').addEventListener('click', () => { window.__njsBuyKind = 'fs'; yes.click(); });
  }
})();

// Hero switcher on the slot (client, 2026-11-23): pick between the hero versions; the choice
// is kept per browser. Art: img/neon-joker-spins/skins/c/sets/r1/heroes/<id>.webp (not img/: dev-sets.js
// rewrites every img/ path to the locked set's own mascot).
(function () {
  const IMG = 'img/neon-joker-spins/skins/c/sets/r1/heroes';
  const HEROES = [
    { id: 'lean', name: 'У края экрана' },
    { id: 'front', name: 'Фронтально' },
    { id: 'punk', name: 'Вполоборота' },
    { id: 'jester', name: 'Шут' },
  ];
  // the client picked the final hero (2026-11-26): 'lean' is locked, the switcher is no longer shown
  const LOCKED = 'lean';
  let cur = LOCKED;
  const mascot = document.getElementById('mascot');
  if (!mascot) return;
  const apply = (id) => {
    cur = id;
    HEROES.forEach((h) => document.body.classList.toggle(`hero-${h.id}`, h.id === id));
    mascot.src = `${IMG}/${id}.webp?v=1`;
    box.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
  };
  const box = document.createElement('div');
  box.className = 'r1-heroes';
  box.innerHTML = `<span class="r1-heroes__lbl">Герой</span>${HEROES.map((h) =>
    `<button type="button" data-id="${h.id}" title="${h.name}" aria-label="${h.name}"><img src="${IMG}/${h.id}.webp?v=1" alt=""></button>`).join('')}`;
  // phones: only the current hero shows; a tap on it opens the others
  box.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    e.stopPropagation();
    if (b.dataset.id === cur) { box.classList.toggle('is-open'); return; }
    apply(b.dataset.id);
    box.classList.remove('is-open');
  });
  box.addEventListener('pointerdown', (e) => e.stopPropagation());
  apply(cur);
  // the stage is centred and scaled: on a screen wider than its 16:9 (or 9:16) there are side
  // margins, so "left: 0" is not the screen edge. --r1-edge = the screen's left edge in stage px.
  const stage = document.getElementById('stage');
  const edge = () => {
    if (!stage) return;
    const r = stage.getBoundingClientRect();
    const k = r.width / stage.offsetWidth || 1;
    const s = document.getElementById('screen').getBoundingClientRect();
    document.documentElement.style.setProperty('--r1-edge', `${((s.left - r.left) / k).toFixed(1)}px`);
  };
  addEventListener('resize', () => requestAnimationFrame(edge));
  edge(); setTimeout(edge, 300); setTimeout(edge, 1500);
  // dev-sets.js may set the cluster's own mascot after us: keep the pick
  new MutationObserver(() => { if (!mascot.src.includes(`heroes/${cur}.webp`)) mascot.src = `${IMG}/${cur}.webp?v=1`; })
    .observe(mascot, { attributes: true, attributeFilter: ['src'] });
})();
