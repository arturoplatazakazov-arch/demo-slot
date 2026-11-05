// Volt Coins V3 — новый деск-макет дизайнера (PSB 30.10) поверх V2; варианты V2 остаются
// для портрета (мобильного макета ещё нет), деск — один, по PSB. Варианты, которые клиент
// просил показать «2–3 штуки», переключаются панелью «Варианты» и живут в
// атрибутах <body>: data-field (подсветка поля), data-wild (выделение Wild),
// data-layout (компоновка портрета). Выбор помнится в localStorage и
// задаётся ссылкой: ?field=2&wild=1&layout=3.

const REVIEW_VARIANTS = {
  field: { title: 'Поле', opts: { 1: 'Подсветка', 2: 'Виньетка', 3: 'Колодец света' }, def: '2' },
  wild: { title: 'Wild', opts: { 0: 'Плашка + вспышка на выигрыше', 1: 'Подложка', 2: 'Крупнее', 3: 'Энергия' }, def: '0' },
  ingot: { title: 'Слиток (H2)', opts: { 7: 'Батарея дизайнера (V3)', 8: 'Энергоблок', 9: 'Энергоблок широкий (разряды)', 6: 'Мешок денег', 5: 'Сейф', 2: 'Батарея', 1: 'Изумруд', 3: 'Ядро', 4: 'Золото (было)' }, def: '7' },   // V3: в макете — новая батарея дизайнера (из PSB)
  glow: { title: 'Свечение символов', opts: { 0: 'Выкл', 1: 'Колокол + слиток + бриллиант' }, def: '1' },   // V3: в PSB у колокола и батареи есть свечение
  // V3: рама и раскладки деска/портрета — из макета, вариантов V2 больше нет
};

function reviewGet(key) {
  const q = new URLSearchParams(location.search).get(key);
  if (q && REVIEW_VARIANTS[key].opts[q]) return q;
  try {
    const v = localStorage.getItem(`vc3a.${key}`);
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
  try { localStorage.setItem(`vc3a.${key}`, val); } catch (e) { /* ignore */ }
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
  if (neonOn()) return `img/volt-coins-v3/ui/${key}_neon.webp?v=1`;
  return lit ? `img/volt-coins-v3/ui/${key}.webp?v=1` : `img/volt-coins-v3/ui/${key}_off.webp?v=1`;
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

// V3: рама из макета дизайнера (v3/frame.png) везде — без ламп и неона V2
// (свой неон в желобе — .v3-neon).
function v3Desk() { return true; }

function applyFrameVariant() {
  const desk = v3Desk();
  const neon = document.body.dataset.frame === '2' && !desk;
  const img = document.getElementById('cabinetFrame');
  if (img) {
    const src = desk ? 'img/volt-coins-v3/v3/frame.png' : `img/volt-coins-v3/img/${neon ? 'frame_neon.png?v=5' : 'frame_off.png'}`;
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
  if (window.VoltFx && VoltFx.frameLamps) VoltFx.frameLamps(!neon && !desk);
  if (typeof applyUiArt === 'function') applyUiArt();
}
window.addEventListener('resize', applyFrameVariant);

function wildScale() {
  const w = document.body.dataset.wild;
  return w === '2' ? 1.22 : w === '3' ? 1.1 : w === '0' ? 1.398 : 1;
}

function setupVariantsPanel() {
  for (const key of Object.keys(REVIEW_VARIANTS)) document.body.dataset[key] = reviewGet(key);
  // панель «Варианты» снята (2026-11-05): выбранные варианты применяются, кнопки нет
  if (!new URLSearchParams(location.search).has('variants')) {
    for (const key of Object.keys(REVIEW_VARIANTS)) reviewSet(key, document.body.dataset[key]);
    applyFrameVariant();
    return;
  }
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
  applyFrameVariant();
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
  try { off = localStorage.getItem('vc3b.lightsOff') === '1'; } catch (e) { /* ignore */ }
  const apply = () => {
    document.body.classList.toggle('lights-off', off);
    btn.setAttribute('aria-pressed', String(off));
    if (typeof fx === 'function') fx('setLights', !off);
    try { localStorage.setItem('vc3b.lightsOff', off ? '1' : '0'); } catch (e) { /* ignore */ }
  };
  btn.addEventListener('click', () => { off = !off; apply(); });
  apply();
}

// V3: Buy Bonus — не кнопка на сцене, а пункт меню (флайаут стандартного
// бара). Жмёт спрятанную #buyBonusBtn — вся логика покупки остаётся в app.js.
function setupBuyInMenu() {
  const flyout = document.getElementById('v3Flyout');
  const buy = document.getElementById('buyBonusBtn');
  if (!flyout || !buy || flyout.querySelector('.v3-btn--buy')) return;
  const btn = document.createElement('button');
  btn.className = 'ui-icon-btn v3-btn v3-btn--buy';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Buy Bonus');
  btn.title = 'Buy Bonus';
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6.2 8.4h11.6l-1 11.1H7.2l-1-11.1Z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 10.6V7a3 3 0 0 1 6 0v3.6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/><path d="m12.9 11.6-2.4 3.6h2.2l-.9 3 2.6-3.8h-2.2l.7-2.8Z" fill="currentColor"/></svg>';
  btn.addEventListener('click', () => {
    if (buy.disabled) return;
    buy.click();
  });
  // доступность = как у самой кнопки (её гасит app.js во время спина/бонуса)
  const sync = () => {
    const bonus = document.getElementById('screen')?.dataset.mode === 'bonus';
    btn.disabled = buy.disabled || bonus;
  };
  new MutationObserver(sync).observe(buy, { attributes: true, attributeFilter: ['disabled'] });
  new MutationObserver(sync).observe(document.getElementById('screen'), { attributes: true, attributeFilter: ['data-mode'] });
  flyout.prepend(btn);
  sync();
}
window.addEventListener('load', setupBuyInMenu);

// Номинал → «вес» монеты: x1–x3 обычная, x5 ярче, x10/x15 — горячая.
function coinWeightClass(face) {
  if (!face || face.word) return '';
  const v = Number(String(face.digits || '').replace('x', ''));
  if (v >= 10) return 'is-val-hi';
  if (v >= 5) return 'is-val-mid';
  return 'is-val-lo';
}

// Иерархия монет (2026-11-05, лаба: scripts/volt_coins_v3_coin_tiers.py LADDER):
// диаметр монеты — доля высоты ячейки (x1 72% … MAJOR 95%), сила кольца
// молний 0..1 (у x1 нет) и число искр. coinSizeK — множитель к прежнему
// размеру монеты (монета в тайле 338/381 × scale 1.1 = 0.9757 ячейки).
const COIN_LADDER = {
  x1: [0.72, 0, 0], x2: [0.745, 0.18, 1], x3: [0.77, 0.32, 1], x5: [0.795, 0.46, 2],
  x10: [0.82, 0.6, 2], x15: [0.845, 0.72, 3], x25: [0.87, 0.84, 3],
  mini: [0.89, 0.92, 4], minor: [0.92, 1, 5], major: [0.95, 1, 6],
};
const COIN_BASE_FRAC = (338 / 381) * 1.1;
function coinTier(face) {
  return (face && COIN_LADDER[face.word || face.digits]) || null;
}
function coinSizeK(face) {
  const t = coinTier(face);
  return t ? t[0] / COIN_BASE_FRAC : 1;
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
    // V3 мобила («катушки у рилов»): катушки под рамой, их низ уходит под
    // градиент бара — как в V2 портрете 5, считаем от того же 1185
    const v3m = document.body.classList.contains('v3m');
    const bottom = v3m ? 1185 : (LAYOUT_BOTTOM[document.body.dataset.layout] || 1154);
    extra = Math.max(-60, Math.min(260, avail - bottom));
  }
  document.body.style.setProperty('--extra', `${Math.round(extra)}px`);
}
window.addEventListener('resize', () => requestAnimationFrame(() => { fitPortraitExtra(); placeVignette(); }));
window.addEventListener('load', () => setTimeout(() => { fitPortraitExtra(); placeVignette(); }, 60));

const INGOT_ART = { 7: 'ingot_battery', 1: 'ingot_emerald', 2: 'ingot_cell', 3: 'ingot_core', 4: 'ingot', 5: 'ingot_safe', 6: 'ingot_bag', 8: 'ingot_block', 9: 'ingot_block_wide' };
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
