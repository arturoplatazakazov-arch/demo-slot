// Volt Coins V3 — DEV-пульт (js/dev-tools.js) + ♪ (SoundKit, js/volt-coins-v3/sound.js).
// Каждая кнопка спина — ПОДСТАВНОЙ ответ в форме серверного, проигранный
// настоящим путём игры через window.__devSpin (app.js): барабаны,
// антисипация, линии, попапы, вход в Hold & Win, респины и все звуки идут
// ровно как в живом спине, только без сервера и без ставки.
//
// Выплаты — как у тест-панели (TEST_COMBO_PAY в slot.js = сид), номиналы монет
// в ставках, джекпоты — JACKPOT_VALUE_BY_TIER.
(function () {
  const COIN_VALUES = [1, 2, 3, 5, 10, 15, 25];
  const rnd = (list) => list[Math.floor(Math.random() * list.length)];
  const bet = () => currentBet();
  const amountField = () => Number(DevTools.value('amount')) || 0;
  const PLAIN = FILLER_CODES.filter((c) => c !== 'wild');

  // --- сетки ------------------------------------------------------------------

  // Наполнитель без случайного выигрыша и без монет: ни на одной из 5 линий
  // три одинаковых символа.
  function fillerGrid() {
    for (let k = 0; k < 300; k++) {
      const g = [0, 1, 2].map(() => [0, 1, 2].map(() => rnd(PLAIN)));
      if (!PAYLINES.some((l) => g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2])) return g;
    }
    return [0, 1, 2].map((r) => [0, 1, 2].map((c) => PLAIN[(r * 3 + c) % PLAIN.length]));
  }
  const linePos = (n) => PAYLINES[n - 1].map((row, col) => ({ row, col }));

  function lineWin(g, n, code, wildCol = -1) {
    const positions = linePos(n);
    for (const p of positions) g[p.row][p.col] = p.col === wildCol ? 'wild' : code;
    return { payline: n, symbol: code, count: 3, positions, amount: Math.round(bet() * TEST_COMBO_PAY[code]) };
  }

  function spin({ grid, lineWins = [], coins = [], holdAndWin = null, bought = false }) {
    const total = lineWins.reduce((s, w) => s + w.amount, 0);
    return window.__devSpin({
      grid,
      line_wins: lineWins,
      total_win: total,
      coin_multiplier: coins.length ? { positions: coins } : null,
      hold_and_win: holdAndWin,
    }, { bought });
  }

  // --- комбинации -------------------------------------------------------------

  function combo(code, line = 1) {
    const g = fillerGrid();
    return spin({ grid: g, lineWins: [lineWin(g, line, code)] });
  }
  function twoLines() {
    // дешёвая сверху + дорогая снизу: строки не пересекаются
    const g = fillerGrid();
    return spin({ grid: g, lineWins: [lineWin(g, 2, 'horseshoe'), lineWin(g, 3, 'diamond')] });
  }
  function wildInLine(code) {
    const g = fillerGrid();
    return spin({ grid: g, lineWins: [lineWin(g, 1, code, 1)] });
  }
  // Крупный выигрыш по ставке → тир попапа выбирает сама игра (popupForWin).
  function bigByRatio(x) {
    const g = fillerGrid();
    const w = lineWin(g, 1, 'diamond');
    w.amount = Math.round(bet() * x);
    return spin({ grid: g, lineWins: [w] });
  }

  // --- монеты и Hold & Win ----------------------------------------------------

  const coinAt = (row, col, kind = 'value', value = rnd(COIN_VALUES)) =>
    ({ row, col, kind, value: kind === 'value' ? value : JACKPOT_VALUE_BY_TIER[kind] });
  const key = (c) => `${c.row}:${c.col}`;

  // Монеты на базовой сетке без триггера (лежат номиналами).
  function coinsNoTrigger(cells) {
    const g = fillerGrid();
    const coins = cells.map(([row, col, kind]) => coinAt(row, col, kind));
    for (const c of coins) g[c.row][c.col] = 'coin';
    return spin({ grid: g, coins });
  }

  // Раунд по плану: plan — список респинов, каждый — список [row, col, kind?].
  // Счётчик сбрасывается на 3 при каждой монете; раунд кончается на трёх
  // пустых подряд или на полном поле (как у сервера).
  function round(initial, plan) {
    const locked = new Map(initial.map((c) => [key(c), c]));
    const respins = [];
    let left = RESPIN_COUNT;
    for (const step of plan) {
      if (left <= 0 || locked.size >= 9) break;
      const landed = step.map(([row, col, kind]) => coinAt(row, col, kind)).filter((c) => !locked.has(key(c)));
      for (const c of landed) locked.set(key(c), c);
      respins.push({ landed });
      left = landed.length ? RESPIN_COUNT : left - 1;
    }
    while (left > 0 && locked.size < 9) { respins.push({ landed: [] }); left -= 1; }
    const full = locked.size >= 9;
    const x = [...locked.values()].reduce((s, c) => s + c.value, 0) + (full ? JACKPOT_VALUE_BY_TIER.grand : 0);
    return { triggered: true, initial, respins, full_grid_jackpot: full, total_win: Math.round(bet() * x) };
  }

  // Случайный план: в каждом респине с шансом p падает 1–2 монеты в пустые ячейки.
  function randomPlan(initial, p = 0.45, jackpots = []) {
    const taken = new Set(initial.map(key));
    const free = () => [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => [Math.floor(i / 3), i % 3]).filter(([r, c]) => !taken.has(`${r}:${c}`));
    const plan = [];
    const jp = [...jackpots];
    for (let i = 0; i < 14; i++) {
      const cells = free();
      if (!cells.length) break;
      if (Math.random() > p && !jp.length) { plan.push([]); continue; }
      const n = Math.min(cells.length, Math.random() < 0.3 ? 2 : 1);
      const step = [];
      for (let k = 0; k < n; k++) {
        const [r, c] = cells.splice(Math.floor(Math.random() * cells.length), 1)[0];
        taken.add(`${r}:${c}`);
        step.push([r, c, jp.length ? jp.shift() : 'value']);
      }
      plan.push(step);
    }
    return plan;
  }

  // Спин-триггер: 3 монеты на линии line (+ extra ячейки), дальше раунд по плану.
  // Раунд стартует по кнопке SPIN — как в живой игре.
  function trigger({ line = 1, extra = [], plan = null, jackpots = [], bought = false } = {}) {
    const g = fillerGrid();
    const initial = [...linePos(line).map((p) => coinAt(p.row, p.col)), ...extra.map(([r, c, k]) => coinAt(r, c, k))];
    for (const c of initial) g[c.row][c.col] = 'coin';
    const hw = round(initial, plan || randomPlan(initial, 0.45, jackpots));
    return spin({ grid: g, coins: initial, holdAndWin: hw, bought });
  }

  const allCells = (except) => [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => [Math.floor(i / 3), i % 3])
    .filter(([r, c]) => !except.some((p) => p.row === r && p.col === c));

  const HW = [
    { label: 'Случайный раунд', run: () => trigger() },
    { label: 'Пустой раунд (3 пустых респина)', run: () => trigger({ plan: [] }) },
    { label: 'Монета на последнем респине', run: () => trigger({ plan: [[], [], [[0, 0]], [], [], []] }) },
    { label: 'Монета каждый респин (сбросы счётчика)', run: () => trigger({ plan: [[[0, 0]], [[2, 2]], [[0, 2]], [[2, 0]]] }) },
    { label: '2 монеты за один респин', run: () => trigger({ plan: [[[0, 0], [2, 2]], [], [[0, 1]]] }) },
    { label: 'Почти полное поле (8/9)', run: () => trigger({ plan: [[[0, 0], [0, 1]], [[0, 2], [2, 0]], [[2, 1]]] }) },
    { label: 'Полное поле → GRAND', run: () => trigger({ plan: [[[0, 0], [0, 1]], [], [[0, 2], [2, 0]], [[2, 1], [2, 2]]] }) },
    { label: 'Триггер 5 монет (2 линии)', run: () => trigger({ extra: [[0, 0], [2, 2]] }) },
    { label: 'Триггер 9 монет сразу → GRAND', run: () => {
      const g = [0, 1, 2].map(() => ['coin', 'coin', 'coin']);
      const initial = allCells([]).map(([r, c]) => coinAt(r, c));
      return spin({ grid: g, coins: initial, holdAndWin: round(initial, []) });
    } },
  ];
  const JP = [
    ...['mini', 'minor', 'major'].map((t) => ({ label: `${t.toUpperCase()} в раунде`, run: () => trigger({ plan: [[], [[0, 1, t]], [], [[2, 1]]] }) })),
    { label: 'MINI + MINOR + MAJOR', run: () => trigger({ plan: [[[0, 1, 'mini']], [], [[2, 0, 'minor']], [[0, 2, 'major']]] }) },
    { label: 'Джекпот-монета в триггере', run: () => trigger({ extra: [[0, 0, 'major']] }) },
  ];

  // --- экраны -----------------------------------------------------------------

  function lightsToggle() {
    const off = !document.body.classList.contains('lights-off');
    document.body.classList.toggle('lights-off', off);
    fx('setLights', !off);
  }
  async function jackpotStrikes() {
    for (const tier of JACKPOT_TIERS) {
      const info = cellInfos[4];
      if (info) fx('arcToPlate', info.cell, document.querySelector(`.jp--${tier}`));
      await wait(500);
      await playJackpotAward(tier);
    }
  }
  function allLines() {
    teardownCellInstances();
    playWinCells(PAYLINES.map((r, i) => ({ payline: i + 1, positions: r.map((row, col) => ({ row, col })) })));
  }

  // --- панель -----------------------------------------------------------------

  const symImg = (code) => `img/volt-coins-v3/symbols/${artCode(code)}.png`;
  const symbolRows = TEST_COMBO.slice().reverse().map((code) => ({ key: code, label: TEST_COMBO_NAME[code], img: symImg(code) }));

  DevTools.mount({
    title: 'DEV · Volt Coins',
    fields: [{ key: 'amount', label: 'Сумма попапа', value: 123450 }],
    tabs: [
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим', items: [
            { label: 'База → Hold & Win (переход)', run: () => enterBonusMode() },
            { label: 'Hold & Win → База (переход)', run: () => leaveBonusMode() },
          ] },
          { title: 'Инфо-экраны', items: [
            { label: 'Экран фичи (старт)', run: () => showFeatureScreen() },
            { label: 'Бонус-экран Hold & Win', run: () => showBonusScreen(RESPIN_COUNT) },
          ] },
          { title: 'Барабаны', items: [
            { label: 'Пустой спин', run: () => spin({ grid: fillerGrid() }) },
            { label: 'Все 5 линий подряд', run: allLines },
            { label: 'Свет вкл / выкл', run: lightsToggle },
          ] },
        ],
      },
      {
        title: 'Комбинации',
        sections: [
          { title: '3 в линию',
            note: 'Подставной спин настоящим путём игры: стопы, линия, звук символа, попап по сумме.',
            matrix: { rows: symbolRows, cols: [1, 2, 3, 4, 5], colLabel: (n) => `Л${n}`, run: (row, n) => combo(row.key, n) } },
          { title: 'С Wild в середине', items: ['horseshoe', 'seven', 'diamond'].map((c) => ({ label: `${TEST_COMBO_NAME[c]} + Wild`, run: () => wildInLine(c) })) },
          { title: 'Несколько линий', items: [{ label: '2 линии (Подкова + Бриллиант)', run: twoLines }] },
          { title: 'Тир по сумме выигрыша', note: 'Попап выбирает игра: ×10 BIG, ×25 MEGA, ×50 EPIC, ×1600 MAX.', items: [
            { label: '×5 (без попапа)', run: () => bigByRatio(5) },
            { label: '×15 → BIG', run: () => bigByRatio(15) },
            { label: '×30 → MEGA', run: () => bigByRatio(30) },
            { label: '×60 → EPIC', run: () => bigByRatio(60) },
            { label: `×${MAX_WIN_X} → MAX WIN`, run: () => bigByRatio(MAX_WIN_X) },
          ] },
        ],
      },
      {
        title: 'Сценарии',
        sections: [
          { title: 'Антисипация', note: '2 монеты на линии на 1-м и 2-м барабане → 3-й тянет с зарядом катушек.', items: [
            { label: '✓ Удачная → Hold & Win', run: () => trigger({ line: rnd([1, 2, 3, 4, 5]) }) },
            { label: '✗ Неудачная (мимо)', run: () => coinsNoTrigger([[1, 0], [1, 1]]) },
            { label: '✗ Неудачная (диагональ)', run: () => coinsNoTrigger([[0, 0], [1, 1]]) },
          ] },
          { title: 'Монеты без триггера', items: [
            { label: '1 монета', run: () => coinsNoTrigger([[1, 1]]) },
            { label: '2 монеты не на линии', run: () => coinsNoTrigger([[0, 0], [2, 1]]) },
            { label: 'Джекпот-монеты MINI / MINOR', run: () => coinsNoTrigger([[0, 2, 'mini'], [2, 0, 'minor']]) },
          ] },
          { title: 'Покупка бонуса', items: [
            { label: 'Кнопка BUY BONUS (диалог)', run: () => document.getElementById('buyBonusBtn')?.click() },
            { label: 'Купленный раунд (без диалога)', run: () => { Sound.playSfx('buyConfirm'); return trigger({ bought: true }); } },
          ] },
        ],
      },
      {
        title: 'Hold & Win',
        sections: [
          { title: 'Раунды', note: 'Спин-триггер ставит раунд, дальше — кнопка SPIN, как в игре.', items: HW },
          { title: 'Джекпоты', items: JP },
        ],
      },
      {
        title: 'Попапы',
        sections: [
          { title: 'Выигрыш (сумма из поля)', items: [
            { label: 'Мелкий (табло, без попапа)', run: () => { Sound.playSfx('smallWin'); showTotalWin(amountField()); } },
            ...['bigWin', 'megaWin', 'epicWin'].map((k) => ({ label: k.replace('Win', ' WIN').toUpperCase(), run: () => { Sound.playSfx(k); return playPopup(k, amountField()); } })),
            { label: 'MAX WIN', run: () => playMaxWin(amountField()) },
          ] },
          { title: 'Hold & Win', items: [
            { label: 'TOTAL WIN', run: () => { Sound.playSfx('roundTotalWin'); return playPopup('holdWinTotal', amountField(), 2500); } },
            { label: 'GRAND JACKPOT (попап)', run: () => playPopup('grandWin', amountField(), 2500) },
          ] },
          { title: 'Джекпот: награда', items: [
            ...JACKPOT_TIERS.map((t) => ({ label: t.toUpperCase(), run: () => playJackpotAward(t) })),
            { label: 'Все 4 с разрядом в плашку', run: jackpotStrikes },
          ] },
        ],
      },
    ],
  });

  window.__dev = { fillerGrid, spin, combo, trigger, round, randomPlan, coinsNoTrigger };
})();
