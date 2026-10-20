// Volt Coins V2 — правки по арт-ревью №2 (локально). Варианты, которые клиент
// просил показать «2–3 штуки», переключаются панелью «Варианты» и живут в
// атрибутах <body>: data-field (подсветка поля), data-wild (выделение Wild),
// data-layout (компоновка портрета). Выбор помнится в localStorage и
// задаётся ссылкой: ?field=2&wild=1&layout=3.

const REVIEW_VARIANTS = {
  field: { title: 'Поле', opts: { 1: 'Подсветка', 2: 'Виньетка', 3: 'Колодец света' }, def: '2' },
  wild: { title: 'Wild', opts: { 0: 'Плашка + вспышка на выигрыше', 1: 'Подложка', 2: 'Крупнее', 3: 'Энергия' }, def: '0' },
  ingot: { title: 'Слиток (H2)', opts: { 8: 'Энергоблок', 9: 'Энергоблок широкий (разряды)', 6: 'Мешок денег', 5: 'Сейф', 2: 'Батарея', 1: 'Изумруд', 3: 'Ядро', 4: 'Золото (было)' }, def: '8' },
  layout: { title: 'Портрет', opts: { 1: 'Рилы ниже', 2: 'Джекпоты в 2 ряда', 3: 'Катушки у рилов' }, def: '1' },
};

function reviewGet(key) {
  const q = new URLSearchParams(location.search).get(key);
  if (q && REVIEW_VARIANTS[key].opts[q]) return q;
  try {
    const v = localStorage.getItem(`vc2g.${key}`);
    if (v && REVIEW_VARIANTS[key].opts[v]) return v;
  } catch (e) { /* private mode */ }
  return REVIEW_VARIANTS[key].def;
}

function reviewSet(key, val) {
  document.body.dataset[key] = val;
  try { localStorage.setItem(`vc2g.${key}`, val); } catch (e) { /* ignore */ }
  document.querySelectorAll(`.variants [data-key="${key}"]`).forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.val === val));
  });
  // позиции катушек/рамки меняются — Spine и HUD перепривязать
  window.dispatchEvent(new Event("resize"));
  requestAnimationFrame(placeVignette);
}

function wildScale() {
  const w = document.body.dataset.wild;
  return w === '2' ? 1.22 : w === '3' ? 1.1 : w === '0' ? 1.21 : 1;
}

function setupVariantsPanel() {
  for (const key of Object.keys(REVIEW_VARIANTS)) document.body.dataset[key] = reviewGet(key);
  const panel = document.createElement('details');
  panel.className = 'variants';
  panel.innerHTML = '<summary>Варианты</summary>' + Object.entries(REVIEW_VARIANTS).map(([key, v]) =>
    `<div class="variants__row"><span>${v.title}</span>${Object.entries(v.opts).map(([val, label]) =>
      `<button type="button" data-key="${key}" data-val="${val}" title="${label}">${val} · ${label}</button>`).join('')}</div>`).join('');
  document.body.appendChild(panel);
  panel.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-key]');
    if (b) reviewSet(b.dataset.key, b.dataset.val);
  });
  for (const key of Object.keys(REVIEW_VARIANTS)) reviewSet(key, document.body.dataset[key]);
}

// Тумблер «turn off light» в меню (ревью: для игроков, чувствительных к
// вспышкам, и для батареи). Гасит Spine-свет и CSS-разряды.
function setupLightsToggle() {
  const flyout = document.getElementById('v3Flyout');
  if (!flyout) return;
  const btn = document.createElement('button');
  btn.className = 'ui-icon-btn v3-btn v3-btn--lights';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Свет');
  btn.setAttribute('aria-pressed', 'false');
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.8.6 1.1 1.4 1.1 2.2h5c0-.8.3-1.6 1.1-2.2A6 6 0 0 0 12 3Z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/></svg>';
  flyout.prepend(btn);
  let off = false;
  try { off = localStorage.getItem('vc2b.lightsOff') === '1'; } catch (e) { /* ignore */ }
  const apply = () => {
    document.body.classList.toggle('lights-off', off);
    btn.setAttribute('aria-pressed', String(off));
    if (typeof fx === 'function') fx('setLights', !off);
    try { localStorage.setItem('vc2b.lightsOff', off ? '1' : '0'); } catch (e) { /* ignore */ }
  };
  btn.addEventListener('click', () => { off = !off; apply(); });
  apply();
}

// Номинал → «вес» монеты: x1–x3 обычная, x5 ярче, x10/x15 — горячая.
function coinWeightClass(face) {
  if (!face || face.word) return '';
  const v = Number(String(face.digits || '').replace('x', ''));
  if (v >= 10) return 'is-val-hi';
  if (v >= 5) return 'is-val-mid';
  return 'is-val-lo';
}

// Центр/радиус виньетки = прямоугольник барабанов (в % экрана).
function placeVignette() {
  const vig = document.querySelector('.field-vignette');
  const win = document.getElementById('reelWindow');
  const scr = document.getElementById('screen');
  if (!vig || !win || !scr) return;
  const s = scr.getBoundingClientRect();
  const r = win.getBoundingClientRect();
  vig.style.setProperty('--vig-x', `${((r.left + r.width / 2 - s.left) / s.width) * 100}%`);
  vig.style.setProperty('--vig-y', `${((r.top + r.height / 2 - s.top) / s.height) * 100}%`);
  vig.style.setProperty('--vig-rx', `${r.width * 0.95}px`);
  vig.style.setProperty('--vig-ry', `${r.height * 0.95}px`);
}
window.addEventListener('resize', () => requestAnimationFrame(placeVignette));
window.addEventListener('load', () => setTimeout(placeVignette, 50));

// Портрет на высоких телефонах: сцена 800x1450 упирается в ширину, и между
// поле выигрыша и Spin остаётся пустота. --extra (px сцены) раздаётся
// компоновкам: верх чуть ниже, барабаны ниже, нижний ряд ещё ниже.
const LAYOUT_BOTTOM = { 1: 1185, 2: 1192, 3: 1190 };
function fitPortraitExtra() {
  const portrait = matchMedia('(orientation: portrait)').matches;
  const spin = document.querySelector('.v3-spin');
  const scale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale')) || 1;
  let extra = 0;
  if (portrait && spin) {
    const scr = document.getElementById('screen').getBoundingClientRect();
    const avail = (spin.getBoundingClientRect().top - scr.top) / scale - 24;
    extra = Math.max(-60, Math.min(260, avail - (LAYOUT_BOTTOM[document.body.dataset.layout] || 1154)));
  }
  document.body.style.setProperty('--extra', `${Math.round(extra)}px`);
}
window.addEventListener('resize', () => requestAnimationFrame(() => { fitPortraitExtra(); placeVignette(); }));
window.addEventListener('load', () => setTimeout(() => { fitPortraitExtra(); placeVignette(); }, 60));

const INGOT_ART = { 1: 'ingot_emerald', 2: 'ingot_cell', 3: 'ingot_core', 4: 'ingot', 5: 'ingot_safe', 6: 'ingot_bag', 8: 'ingot_block', 9: 'ingot_block_wide' };
function ingotArt() { return INGOT_ART[document.body.dataset.ingot] || 'ingot_block'; }
// смена варианта слитка — перерисовать уже лежащие на поле и в лентах
window.addEventListener('resize', () => {
  if (typeof symbolSrc !== 'function') return;
  document.querySelectorAll('.reel__cell[data-symbol="ingot"] > img').forEach((img) => {
    const src = symbolSrc('ingot');
    if (!img.src.endsWith(src)) img.src = src;
  });
});

// Десктоп: Buy Bonus и поле выигрыша — вертикальные плашки по бокам автомата;
// портрет — горизонтальные под ним. Картинка и окно под сумму меняются по ориентации.
const UI_PLATES = {"buy":{"w":487,"h":192,"price":{"l":0,"t":0,"w":0,"h":0}},"win":{"w":559,"h":192,"panel":{"l":0.322,"t":0.2604,"w":0.585,"h":0.4844}},"buy_v":{"w":298,"h":279},"win_v":{"w":319,"h":283,"panel":{"l":0.163,"t":0.4452,"w":0.6677,"h":0.3746}},"buy_A":{"w":487,"h":192},"win_A":{"w":559,"h":192,"panel":{"l":0.322,"t":0.2604,"w":0.585,"h":0.4844}},"buy_B":{"w":488,"h":159},"win_B":{"w":564,"h":159,"panel":{"l":0.25,"t":0.0503,"w":0.7394,"h":0.9119}},"buy_vA":{"w":298,"h":279},"win_vA":{"w":319,"h":283,"panel":{"l":0.163,"t":0.4452,"w":0.6677,"h":0.3746}},"buy_vB":{"w":300,"h":308},"win_vB":{"w":318,"h":313,"panel":{"l":0.022,"t":0.2971,"w":0.9528,"h":0.6805}}};
function applyUiArt() {
  const desk = !matchMedia('(orientation: portrait)').matches;
  for (const [el, key] of [[document.getElementById('buyBonusBtn'), desk ? 'buy_v' : 'buy'], [document.getElementById('winMeter'), desk ? 'win_v' : 'win']]) {
    if (!el) continue;
    const art = UI_PLATES[key];
    const img = el.querySelector('.ui-art');
    const slot = el.querySelector('.ui-slot');
    const src = `img/volt-coins-v2/ui/${key}.webp`;
    if (!img.src.endsWith(src)) img.src = src;
    const p = art.panel;
    // Buy Bonus без окна цены (цена — в попапе покупки)
    slot.hidden = key.startsWith('buy');
    if (p) Object.assign(slot.style, { left: `${p.l * 100}%`, top: `${p.t * 100}%`, width: `${p.w * 100}%`, height: `${p.h * 100}%` });
    el.style.aspectRatio = `${art.w} / ${art.h}`;
    el.classList.toggle('is-vertical', desk);
  }
}
window.addEventListener('resize', applyUiArt);
window.addEventListener('load', applyUiArt);
