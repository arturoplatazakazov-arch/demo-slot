// Constructor v2 — registry of reel BASES and MECHANICS.
//
// This is the heart of the constructor: one source of truth that drives all
// three pages. Page 1 filters mechanics by the chosen base. Page 2 turns the
// chosen base + mechanics into a required-asset checklist. Page 3 turns them
// into the palette of placeable elements and the "role/function" vocabulary.
//
// It mirrors the backend feature registry (app/features/registry.py): adding a
// new mechanic here (plus its runtime module) makes it available in every slot.

// --- Reel bases ------------------------------------------------------------
// Each base = a reel geometry + the reel runtime that plays it. `mechanics` is
// the set of add-ons that make sense on that base (page 1 offers only these).
window.BASES = {
  '3x3': {
    label: '3×3',
    hint: 'Классика, самый простой. Максимум скаттер / Hold & Win.',
    reels: 3, rows: 3,
    runtime: 'lines',
    mechanics: ['scatter', 'free_spins', 'hold_and_win'],
  },
  '5x3': {
    label: '5×3',
    hint: 'Выплаты по линиям + добавки: скаттер, бай-бонус, вайлды, Hold & Win.',
    reels: 5, rows: 3,
    runtime: 'lines',
    mechanics: ['scatter', 'free_spins', 'bonus_buy', 'expanding_wild', 'sticky_wild', 'coin_multiplier', 'hold_and_win'],
  },
  '6x5': {
    label: '6×5',
    hint: 'Аваланч/каскад. Бомбы и множители-токены — опционально.',
    reels: 6, rows: 5,
    runtime: 'avalanche',
    mechanics: ['scatter', 'free_spins', 'bonus_buy', 'bombs', 'multiplier_tokens'],
  },
};

// --- Mechanics -------------------------------------------------------------
// `requires` / `conflicts` are mechanic ids. `assets` is the required-asset
// checklist contribution (page 2). `roles` are the placeable functions this
// mechanic adds to page 3's element palette. `optional` assets can be skipped.
window.MECHANICS = {
  scatter: {
    label: 'Scatter',
    hint: 'Спец-символ, обычно триггерит бонус.',
    assets: [{ id: 'sym_scatter', label: 'Символ Scatter', kind: 'symbol' }],
    roles: [],
  },
  free_spins: {
    label: 'Free Spins',
    hint: 'Бесплатные вращения. Обычно от скаттеров.',
    requires: ['scatter'],
    assets: [
      { id: 'popup_bonus_win', label: 'Попап «Bonus Spins Win»', kind: 'popup' },
      { id: 'bg_bonus', label: 'Фон бонус-режима', kind: 'background' },
    ],
    roles: [{ id: 'fs_counter', label: 'Счётчик фри-спинов' }],
  },
  bonus_buy: {
    label: 'Bonus Buy',
    hint: 'Покупка бонуса за ставку.',
    requires: ['free_spins'],
    assets: [{ id: 'btn_buy_bonus', label: 'Кнопка Buy Bonus', kind: 'button' }],
    roles: [{ id: 'buy_bonus', label: 'Кнопка Buy Bonus' }],
  },
  expanding_wild: {
    label: 'Expanding / Growing Wild',
    hint: 'Вайлд, растущий на весь барабан.',
    conflicts: ['sticky_wild'],
    assets: [{ id: 'sym_wild', label: 'Символ Wild', kind: 'symbol' }],
    roles: [],
  },
  sticky_wild: {
    label: 'Sticky Wild',
    hint: 'Вайлд, залипающий на месте.',
    conflicts: ['expanding_wild'],
    assets: [{ id: 'sym_wild', label: 'Символ Wild', kind: 'symbol' }],
    roles: [],
  },
  coin_multiplier: {
    label: 'Coin Multiplier',
    hint: 'Монеты-множители, собираемые в бонусе.',
    assets: [{ id: 'sym_coin', label: 'Символ монеты', kind: 'symbol' }],
    roles: [{ id: 'multi_counter', label: 'Счётчик множителя' }],
  },
  hold_and_win: {
    label: 'Hold & Win',
    hint: 'Респины с залипающими символами.',
    assets: [
      { id: 'sym_coin', label: 'Символ монеты/приза', kind: 'symbol' },
      { id: 'bg_hw', label: 'Фон Hold & Win', kind: 'background', optional: true },
    ],
    roles: [{ id: 'hw_counter', label: 'Счётчик респинов' }],
  },
  bombs: {
    label: 'Бомбы',
    hint: 'Взрывают ряд+колонку (аваланч).',
    assets: [
      { id: 'sym_bomb', label: 'Символ бомбы', kind: 'symbol' },
      { id: 'vfx_boom_bomb', label: 'VFX взрыва бомбы', kind: 'vfx' },
    ],
    roles: [],
  },
  multiplier_tokens: {
    label: 'Множители-токены',
    hint: 'x2/x3/x5 токены, копятся в множитель (аваланч).',
    assets: [{ id: 'sym_tokens', label: 'Символы токенов (x2/x3/…)', kind: 'symbol' }],
    roles: [{ id: 'multi_counter', label: 'Счётчик множителя' }],
  },
};

// --- Base (always-present) roles for page 3's palette ----------------------
// Every slot has these regardless of mechanics.
window.BASE_ROLES = [
  { id: 'logo', label: 'Логотип' },
  { id: 'bg_base', label: 'Фон базовой игры' },
  { id: 'reel_background', label: 'Фон за барабанами' },
  { id: 'reels', label: 'Барабан (сетка)' },
  { id: 'frame', label: 'Рамка барабана' },
  { id: 'spin_btn', label: 'Кнопка Spin' },
  { id: 'bet_field', label: 'Поле ставки (bet −/+)' },
  { id: 'balance', label: 'Баланс' },
  { id: 'win', label: 'Выигрыш' },
  { id: 'turbo', label: 'Турбо' },
  { id: 'auto', label: 'Автоспин' },
  { id: 'sound', label: 'Звук' },
  { id: 'info', label: 'Инфо / paytable' },
];

// --- The 4 layout screens + fixed/flex design canvas (from the ТЗ) ---------
// Desktop: height FIXED 940, width range 1612–1932. Mobile: width FIXED 780,
// height range 1216–1416. One axis is pixels, the other is anchor+offset.
window.SCREENS = [
  { id: 'desk-base', label: 'Десктоп · база', device: 'desk', mode: 'base' },
  { id: 'desk-bonus', label: 'Десктоп · бонус', device: 'desk', mode: 'bonus' },
  { id: 'mobi-base', label: 'Мобайл · база', device: 'mobi', mode: 'base' },
  { id: 'mobi-bonus', label: 'Мобайл · бонус', device: 'mobi', mode: 'bonus' },
];
window.DEVICES = {
  desk: { label: 'Десктоп', fixed: 'height', h: 940, wMin: 1612, wMax: 1932 },
  mobi: { label: 'Мобайл', fixed: 'width', w: 780, hMin: 1216, hMax: 1416 },
};

// Helper: resolve the full set of required assets for a base + mechanics.
window.requiredAssets = function (baseId, mechanics) {
  const out = [];
  const seen = new Set();
  const add = (a) => { if (!seen.has(a.id)) { seen.add(a.id); out.push(a); } };
  // Base always needs symbols + a base background + frame + logo.
  add({ id: 'symbols_base', label: 'Обычные символы барабана', kind: 'symbol' });
  add({ id: 'bg_base', label: 'Фон базовой игры', kind: 'background' });
  add({ id: 'frame', label: 'Рамка барабана', kind: 'frame' });
  add({ id: 'logo', label: 'Логотип игры', kind: 'logo' });
  for (const m of mechanics) {
    const def = window.MECHANICS[m];
    if (def && def.assets) def.assets.forEach(add);
  }
  return out;
};

// Helper: resolve the palette roles for a base + mechanics.
window.paletteRoles = function (baseId, mechanics) {
  const roles = [...window.BASE_ROLES];
  const seen = new Set(roles.map((r) => r.id));
  for (const m of mechanics) {
    const def = window.MECHANICS[m];
    if (def && def.roles) {
      for (const r of def.roles) if (!seen.has(r.id)) { seen.add(r.id); roles.push(r); }
    }
  }
  return roles;
};
