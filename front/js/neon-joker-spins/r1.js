// Neon Joker Spins · Neon Tubes R1 — page extras for the client's round-1 feedback (2026-11-23):
// feature hints (desktop: next to the jackpots; portrait: rotating in the win strip), and a buy
// window with both bonuses. The game only sells Hold & Win, so the Free Spins card is a static
// mock of the future buy. Layout: css/njs-r1.css.
(function () {
  const stage = document.getElementById('stage');
  if (!stage) return;
  const SYM = 'img/neon-joker-spins/skins/c/sets/r1/symbols';
  const HINTS = [
    { cls: 'fs', img: `${SYM}/scatter.webp?v=3`, n: '3+', what: 'FREE SPINS', sub: 'JOKERS ANYWHERE' },
    { cls: 'hw', img: `${SYM}/coin.webp?v=3`, n: '5+', what: 'HOLD & WIN', sub: 'COINS ANYWHERE' },
  ];

  // ONE info plaque (neon sign, img/.../r1/img/plaque.webp): FREE SPINS flickers on, holds, goes
  // dark, then HOLD & WIN does the same, round and round. Desktop: under the jackpots; phones: the
  // win strip (hidden while a win is shown and during the bonuses).
  const plaque = document.createElement('div');
  plaque.className = 'obj r1-plaque';
  plaque.innerHTML = '<div class="r1-plaque__face"><img class="r1-plaque__icon" alt=""><span class="r1-plaque__text"><b></b><small></small></span></div>';
  stage.appendChild(plaque);
  const face = plaque.firstElementChild;
  const icon = face.querySelector('img');
  const title = face.querySelector('b');
  const sub = face.querySelector('small');
  HINTS.forEach((h) => { const i = new Image(); i.src = h.img; });
  const ON_MS = 3600, OFF_MS = 520, GAP_MS = 900;
  let k = 0;
  const show = () => {
    const h = HINTS[k];
    plaque.dataset.k = h.cls;
    icon.src = h.img;
    title.textContent = h.what;
    sub.textContent = `${h.n} ${h.sub}`;
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
    if (text) text.textContent = 'Выберите бонус. Hold & Win — за 34.5× ставки; Free Spins — макет будущей покупки.';
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
    // Free Spins mock price = 100× bet (Hold & Win costs 34.5× bet)
    const fsPrice = cards.querySelector('#r1BuyFs');
    const upd = () => {
      const v = parseFloat(price.textContent.replace(/[^\d.]/g, '')) || 0;
      fsPrice.textContent = Math.round((v / 34.5) * 100).toLocaleString('en-US');
      note.textContent = '';
    };
    new MutationObserver(upd).observe(price, { childList: true, characterData: true, subtree: true });
    upd();
    cards.querySelector('.r1-buy__card--hw').addEventListener('click', () => yes.click());
    cards.querySelector('.r1-buy__card--fs').addEventListener('click', () => {
      note.textContent = 'Buy Free Spins — статичный макет: в этой сборке покупается только Hold & Win.';
    });
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
  const KEY = 'njs-r1-hero';
  let cur = 'lean';
  try { cur = localStorage.getItem(KEY) || 'lean'; } catch (e) { /* noop */ }
  if (!HEROES.some((h) => h.id === cur)) cur = 'lean';
  const mascot = document.getElementById('mascot');
  if (!mascot) return;
  const apply = (id) => {
    cur = id;
    try { localStorage.setItem(KEY, id); } catch (e) { /* noop */ }
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
  document.body.appendChild(box);
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
