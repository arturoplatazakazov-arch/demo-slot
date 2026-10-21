// Volt Coins V2 — правки по арт-ревью №2 (локально). Варианты, которые клиент
// просил показать «2–3 штуки», переключаются панелью «Варианты» и живут в
// атрибутах <body>: data-field (подсветка поля), data-wild (выделение Wild),
// data-layout (компоновка портрета). Выбор помнится в localStorage и
// задаётся ссылкой: ?field=2&wild=1&layout=3.

const REVIEW_VARIANTS = {
  field: { title: 'Поле', opts: { 1: 'Подсветка', 2: 'Виньетка', 3: 'Колодец света' }, def: '2' },
  wild: { title: 'Wild', opts: { 0: 'Плашка + вспышка на выигрыше', 1: 'Подложка', 2: 'Крупнее', 3: 'Энергия' }, def: '0' },
  ingot: { title: 'Слиток (H2)', opts: { 8: 'Энергоблок', 9: 'Энергоблок широкий (разряды)', 6: 'Мешок денег', 5: 'Сейф', 2: 'Батарея', 1: 'Изумруд', 3: 'Ядро', 4: 'Золото (было)' }, def: '8' },
  glow: { title: 'Свечение символов', opts: { 0: 'Выкл', 1: 'Колокол + слиток + бриллиант' }, def: '0' },
  frame: { title: 'Рама', opts: { 1: 'Лампы', 2: 'Неон' }, def: '1' },
  desk: { title: 'Десктоп', opts: { 1: 'Стандарт', 2: 'Джекпоты в 2 ряда' }, def: '1' },
  layout: { title: 'Портрет', opts: { 1: 'Стандарт', 2: 'Джекпоты в 2 ряда', 4: 'Джекпоты в 2 ряда + катушки внизу', 3: 'Катушки у рилов', 5: 'Катушки у рилов + джекпоты в 2 ряда' }, def: '1' },
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

// Портрет 4 и 5 — комбинации: вёрстка базового варианта (2 / 3) плюс
// модификатор data-layout-mod (low — катушки внизу, jp2 — джекпоты в 2 ряда).
const LAYOUT_COMBO = { 4: ['2', 'low'], 5: ['3', 'jp2'] };

function reviewSet(key, val) {
  document.body.dataset[key] = val;
  if (key === 'layout') {
    const [base, mod] = LAYOUT_COMBO[val] || [val, ''];
    document.body.dataset.layout = base;
    document.body.dataset.layoutMod = mod;
  }
  try { localStorage.setItem(`vc2g.${key}`, val); } catch (e) { /* ignore */ }
  document.querySelectorAll(`.variants [data-key="${key}"]`).forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.val === val));
  });
  if (key === 'frame') applyFrameVariant();
  // позиции катушек/рамки меняются — Spine и HUD перепривязать
  window.dispatchEvent(new Event("resize"));
  requestAnimationFrame(placeVignette);
}

// Рама «Неон»: простая стальная рама с LED-желобом по середине борта
// (img/frame_neon.png, ChatGPT, подогнана 9-slice под окно барабанов);
// по желобу по часовой медленно крутятся два одинаковых неона на
// противоположных сторонах (CSS: выигрыш — быстрее, бонус — желоб горит весь). Плашки Buy Bonus / WIN / респинов в этом режиме
// — той же стали со своим желобом и неоном (ui/<key>_neon.webp, NEON_PLATES).
// Spine-слой ламп старой рамы в этом режиме скрыт.
// Осевая желоба в px рамы 870x694: борт 20 px вокруг окна (48,47)-(814,653), желоб по его середине
// (scripts/volt_coins_neon_frame.py печатает эти числа при пересборке).
const NEON_PATH = { x: 38, y: 37, w: 786, h: 626, r: 5.5 };
// Осевые желобов плашек (px их картинок) — печатает volt_coins_neon_frame.py.
const NEON_PLATES = {"buy": {"x": 9.0, "y": 9.0, "w": 469, "h": 174, "r": 4.4}, "win": {"x": 9.0, "y": 9.0, "w": 541, "h": 174, "r": 4.4}, "buy_v": {"x": 9.5, "y": 9.5, "w": 279, "h": 260, "r": 4.7}, "win_v": {"x": 10.5, "y": 10.5, "w": 298, "h": 262, "r": 5.3}, "resp": {"x": 14.0, "y": 14.0, "w": 972, "h": 280, "r": 7.2}, "resp_v": {"x": 15.5, "y": 15.5, "w": 477, "h": 451, "r": 8.0}};
// Где на неоновой плашке подпись (доли картинки: l, t, w, h) и её текст.
const NEON_LABELS = {
  buy: [[0.06, 0.12, 0.88, 0.76], 'BUY BONUS'], buy_v: [[0.08, 0.12, 0.84, 0.76], 'BUY<br>BONUS'],
  win: [[0.04, 0.2, 0.27, 0.6], 'WIN'], win_v: [[0.08, 0.1, 0.84, 0.3], 'WIN'],
  resp: [[0.05, 0.2, 0.37, 0.6], 'RESPINS'], resp_v: [[0.08, 0.12, 0.84, 0.36], 'RESPINS'],
};
function neonOn() { return document.body.dataset.frame === '2'; }
function plateSrc(key, lit) {
  if (neonOn()) return `img/volt-coins-v2/ui/${key}_neon.webp?v=1`;
  return lit ? `img/volt-coins-v2/ui/${key}.webp?v=1` : `img/volt-coins-v2/ui/${key}_off.webp?v=1`;
}
// Подпись и неон-обводка поверх плашки (видны только при раме «Неон», CSS).
function decorateNeonPlate(el, key) {
  const p = NEON_PLATES[key];
  const art = { w: 0, h: 0, ...(UI_PLATES[key] || RESP_PLATES[key]) };
  let svg = el.querySelector(':scope > .plate-neon');
  if (!svg || svg.dataset.key !== key) {
    if (svg) svg.remove();
    el.querySelector(':scope > .neon-label')?.remove();
    const rect = `<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="${p.r}" ry="${p.r}" pathLength="1000"/>`;
    el.insertAdjacentHTML('beforeend', `<svg class="frame-neon plate-neon" data-key="${key}" viewBox="0 0 ${art.w} ${art.h}" preserveAspectRatio="none" aria-hidden="true">
      <g class="frame-neon__base">${rect}</g><g class="frame-neon__run">${rect}</g></svg>`);
    const [[l, t, w, h], text] = NEON_LABELS[key];
    el.insertAdjacentHTML('beforeend', `<span class="neon-label" style="left:${l * 100}%;top:${t * 100}%;width:${w * 100}%;height:${h * 100}%"><b>${text}</b></span>`);
  }
}

function applyFrameVariant() {
  const neon = document.body.dataset.frame === '2';
  const img = document.getElementById('cabinetFrame');
  if (img) {
    const src = `img/volt-coins-v2/img/${neon ? 'frame_neon.png?v=5' : 'frame_off.png'}`;
    if (!img.src.endsWith(src)) img.src = src;
  }
  let svg = document.getElementById('frameNeon');
  if (neon && !svg) {
    const { x, y, w, h, r } = NEON_PATH;
    const rect = `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" ry="${r}" pathLength="1000"/>`;
    img.insertAdjacentHTML('afterend', `<svg class="frame-neon" id="frameNeon" viewBox="0 0 870 694" preserveAspectRatio="none" aria-hidden="true">
      <g class="frame-neon__base">${rect}</g>
      <g class="frame-neon__run">${rect}</g>
      <g class="frame-neon__run frame-neon__run--b">${rect}</g>
    </svg>`);
    svg = document.getElementById('frameNeon');
  }
  // у SVG нет свойства hidden (оно только у HTML-элементов) — через display
  if (svg) svg.style.display = neon ? '' : 'none';
  if (window.VoltFx && VoltFx.frameLamps) VoltFx.frameLamps(!neon);
  if (typeof applyUiArt === 'function') applyUiArt();
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

// Размер монеты по номиналу (продукт): каждая ступень на 2% крупнее —
// x1 < x2 < x3 < x5 < x10 < x15 < MINI < MINOR < MAJOR, чтобы номинал ловился
// взглядом; шкала вокруг обычного размера (x1 −8%, MAJOR +8%).
const COIN_SIZE_ORDER = ['x1', 'x2', 'x3', 'x5', 'x10', 'x15', 'mini', 'minor', 'major'];
function coinSizeK(face) {
  const i = face ? COIN_SIZE_ORDER.indexOf(face.word || face.digits) : -1;
  return i < 0 ? 1 : 0.92 + 0.02 * i;   // x1 0.92 … MAJOR 1.08
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
const LAYOUT_BOTTOM = { 1: 1185, 2: 1185, 3: 1185 };   // мобила: автомат и кнопки везде как в «Стандарт»
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
// Счётчик респинов (бонус): плашка в стиле Buy Bonus / WIN из ChatGPT
// (ui/resp*.webp), три лампы-заряда ложатся в нарисованные гнёзда. Центры и
// диаметр стекла гнезда — доли картинки (замерено по листу respins_plates.png).
const RESP_PLATES = {
  resp: { w: 1000, h: 308, d: 0.1, sockets: [[0.485, 0.5065], [0.653, 0.5065], [0.823, 0.5065]] },
  resp_v: { w: 508, h: 482, d: 0.167, sockets: [[0.2717, 0.641], [0.5, 0.641], [0.7323, 0.641]] },
};
function placeRespinPlate(desk) {
  const el = document.getElementById('respinCounter');
  if (!el) return;
  const key = desk ? 'resp_v' : 'resp';
  const art = RESP_PLATES[key];
  const img = el.querySelector('.ui-art');
  const src = plateSrc(key, false);
  if (!img.src.endsWith(src)) img.src = src;
  decorateNeonPlate(el, key);
  let lit = el.querySelector('.ui-art-lit');
  if (!lit) {
    lit = document.createElement('img');
    lit.className = 'ui-art ui-art-lit';
    lit.alt = '';
    img.after(lit);
  }
  const litSrc = plateSrc(key, true);
  if (!lit.src.endsWith(litSrc)) lit.src = litSrc;
  el.style.aspectRatio = `${art.w} / ${art.h}`;
  el.classList.toggle('is-vertical', desk);
  const pips = document.getElementById('respinPips');
  if (pips) [...pips.children].forEach((pip, i) => {
    const s = art.sockets[i];
    if (!s) return;
    Object.assign(pip.style, { left: `${s[0] * 100}%`, top: `${s[1] * 100}%`, width: `${art.d * 100}%` });
  });
}

function applyUiArt() {
  const desk = !matchMedia('(orientation: portrait)').matches;
  placeRespinPlate(desk);
  for (const [el, key] of [[document.getElementById('buyBonusBtn'), desk ? 'buy_v' : 'buy'], [document.getElementById('winMeter'), desk ? 'win_v' : 'win']]) {
    if (!el) continue;
    const art = UI_PLATES[key];
    const img = el.querySelector('.ui-art');
    const slot = el.querySelector('.ui-slot');
    // лампы плашки: снизу погашенная копия, сверху горящая (её прозрачность
    // ведёт CSS: Buy Bonus вспыхивает раз в ~4.5 с, WIN горит только при выигрыше)
    const src = plateSrc(key, false);
    if (!img.src.endsWith(src)) img.src = src;
    decorateNeonPlate(el, key);
    let lit = el.querySelector('.ui-art-lit');
    if (!lit) {
      lit = document.createElement('img');
      lit.className = 'ui-art ui-art-lit';
      lit.alt = '';
      img.after(lit);
    }
    const litSrc = plateSrc(key, true);
    if (!lit.src.endsWith(litSrc)) lit.src = litSrc;
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
