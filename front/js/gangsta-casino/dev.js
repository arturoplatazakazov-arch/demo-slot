// Gangsta Casino — adapter for the shared dev panel (js/dev-tools.js).
//
// Combinations and scenarios are FRONT-ONLY: each builds a made-up spin
// response shaped like the backend's and plays it through app.js's real
// runSpin (window.__devSpin) — reel stops, anticipation, landings, wins,
// multipliers, popups and every sound fire exactly as on a live spin, so the
// ♪ log shows what a given outcome sounds like. Pays follow the seed
// (app/seed/gangsta_casino.py): line pay x (bet / 11 lines), scatter x bet.
(function () {
  const LINES = [ // app/seed/amys_fruit_farm.py PAYLINES (row per reel), payline n = LINES[n-1]
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2], [1, 0, 1, 0, 1],
    [1, 2, 1, 2, 1], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2], [0, 2, 0, 2, 0], [2, 0, 2, 0, 2],
  ];
  const COMMON = { 3: 4.2, 4: 10.5, 5: 21 };
  const RARE = { 3: 21, 4: 52.5, 5: 105 };
  const WILD = { 3: 42, 4: 126, 5: 315 };
  const SCATTER = { 3: 2, 4: 10, 5: 50 };
  const PAYS = {
    rare_purple: RARE, rare_yellow: RARE, rare_blue: RARE, rare_green: RARE,
    common_1: COMMON, common_2: COMMON, common_3: COMMON, common_4: COMMON, wild: WILD,
  };
  const HIGH = new Set(['rare_purple', 'rare_yellow', 'rare_blue', 'rare_green', 'wild']);
  const TIER_POPUP = { 3: 'bigWin', 4: 'megaWin', 5: 'epicWin' }; // app/services/popups.py
  const FS_AWARD = 10;
  const NAMES = {
    rare_purple: 'Queen', rare_yellow: 'Diva', rare_blue: 'Boss', rare_green: 'Hustler',
    common_2: 'Golden Uzi', common_4: 'Pink Glock', common_3: 'Knuckles', common_1: 'Bat',
    wild: 'Wild', scatter: 'Scatter',
  };

  const bet = () => gameState.betSteps[gameState.betIndex];
  const lineBet = () => bet() / LINES.length;
  const rnd = (list) => list[Math.floor(Math.random() * list.length)];
  const inBonus = () => currentMode() === 'freespins';

  // Free-spins round of the dev spins (the backend's own count isn't there).
  const fs = { left: 0, total: 0, roundMult: 1 };

  // A filler grid with no win of its own: no specials, and no three of a
  // kind from reel 1 on any payline.
  function fillerGrid() {
    for (let tries = 0; tries < 200; tries++) {
      const g = [0, 1, 2].map(() => Array.from({ length: GRID_COLS }, () => rnd(FILLER_CODES)));
      if (!LINES.some((l) => g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2])) return g;
    }
    return SYMBOL_LAYOUT.map((r) => r.map((c) => (TRIGGER_CODES.has(c) ? 'common_1' : c)));
  }
  // Put `code` at (row, col) and make sure nothing else breaks the setup.
  function put(g, row, col, code) { g[row][col] = code; }
  // A cell next to a line's end must not extend it.
  function breakAfter(g, line, n, code) {
    if (n >= GRID_COLS) return;
    const r = LINES[line - 1][n];
    while (g[r][n] === code || g[r][n] === 'wild') g[r][n] = rnd(FILLER_CODES.filter((c) => c !== code));
  }

  function lineWin(g, line, code, n, payAs = code) {
    const positions = [];
    for (let col = 0; col < n; col++) {
      const row = LINES[line - 1][col];
      if (g[row][col] !== 'wild') put(g, row, col, code);
      positions.push({ row, col });
    }
    breakAfter(g, line, n, code);
    return { payline: line, symbol_code: payAs, count: n, positions, amount: Math.round(PAYS[payAs][n] * lineBet()) };
  }

  // Assemble the response and play it.
  function spin({ grid, lineWins = [], countWins = [], wildEvents = [], cm = null, multiplier = 1, triggers = 0 }) {
    const cells = new Map();
    for (const w of [...lineWins, ...countWins]) for (const p of w.positions) cells.set(`${p.row}:${p.col}`, p);
    let lineTotal = lineWins.reduce((s, w) => s + w.amount, 0) * multiplier;
    const scatterTotal = countWins.reduce((s, w) => s + w.amount, 0);
    const total = Math.round(lineTotal + scatterTotal);
    let feature = null;
    let popup = null;
    const best = lineWins.reduce((b, w) => (HIGH.has(w.symbol_code) && w.count > (b ? b.count : 0) ? w : b), null);
    if (best) popup = { type: TIER_POPUP[best.count], amount: total };

    if (inBonus()) {
      fs.total += total;
      fs.left = Math.max(0, fs.left - 1) + (triggers ? FS_AWARD : 0);
      if (triggers) popup = { type: 'bonusSpinsWin', amount: FS_AWARD };
      if (fs.left > 0) feature = { type: 'free_spins', spins_remaining: fs.left };
      else popup = { type: 'bonusSpinsTotalWin', amount: fs.total };
    } else if (triggers) {
      fs.left = FS_AWARD;
      fs.total = 0;
      fs.roundMult = 1;
      feature = { type: 'free_spins', spins_remaining: fs.left };
      popup = { type: 'bonusSpinsWin', amount: FS_AWARD };
    }
    gameState.balance += total;
    if (!gameState.freeSpinsTrigger) gameState.freeSpinsTrigger = { trigger_symbol_code: 'scatter', trigger_count: 3 };
    return window.__devSpin({
      balance: gameState.balance,
      grid,
      line_wins: lineWins,
      count_wins: countWins,
      winning_cells: [...cells.values()],
      wild_events: wildEvents,
      coin_multiplier: cm,
      total_win: total,
      popup,
      feature,
    });
  }

  // N of a symbol on the middle line (wilds grow over their reels).
  function combo(code, n) {
    const g = fillerGrid();
    if (code === 'scatter') return scatters(Array.from({ length: n }, (_, i) => i * (n === 3 ? 2 : 1)).slice(0, n), g);
    const w = lineWin(g, 1, code, n);
    const wildEvents = code === 'wild' ? w.positions.map((p) => ({ reel: p.col, event: 'expanded' })) : [];
    return spin({ grid: g, lineWins: [w], wildEvents });
  }

  // Scatters on the given reels (random rows); 3+ = free spins.
  function scatters(cols, g = fillerGrid()) {
    const positions = cols.map((col) => ({ row: Math.floor(Math.random() * 3), col }));
    for (const p of positions) put(g, p.row, p.col, 'scatter');
    const n = positions.length;
    const countWins = n >= 3 ? [{ symbol_code: 'scatter', count: n, positions, amount: Math.round(SCATTER[Math.min(5, n)] * bet()) }] : [];
    return spin({ grid: g, countWins, triggers: n >= 3 ? 1 : 0 });
  }

  function multiplierSpin({ values = [3, 5], win = true } = {}) {
    const g = fillerGrid();
    const lw = win ? [lineWin(g, 1, 'rare_blue', 3)] : [];
    const spots = [{ row: 0, col: 3 }, { row: 2, col: 4 }, { row: 0, col: 1 }];
    const positions = values.map((value, i) => ({ ...spots[i], value }));
    for (const p of positions) put(g, p.row, p.col, 'wof');
    const sum = values.reduce((a, b) => a + b, 0);
    let roundMult = null;
    if (inBonus()) { fs.roundMult += sum; roundMult = fs.roundMult; }
    const applied = win;
    const cm = { positions, applied, multiplier_sum: sum, round_multiplier: roundMult };
    return spin({ grid: g, lineWins: lw, cm, multiplier: !win ? 1 : (inBonus() ? roundMult : sum) });
  }

  const amount = () => Number(DevTools.value('amount')) || 0;
  const spinsField = () => Number(DevTools.value('spins')) || FS_AWARD;

  function toMode(mode, { transition }) {
    if (currentMode() === mode) return Promise.resolve();
    if (mode === 'freespins') { fs.left = spinsField(); fs.total = 0; fs.roundMult = 1; }
    if (transition) {
      if (mode === 'freespins') setFreeSpinsCounter(fs.left);
      return setFreeSpinsMode(mode === 'freespins', fs.left);
    }
    applyModeScreen(mode);
    Sound.playMusic(mode === 'freespins' ? 'bonus' : 'base');
    if (mode === 'freespins') setFreeSpinsCounter(fs.left);
    return Promise.resolve();
  }

  const symbolRows = ['rare_purple', 'rare_yellow', 'rare_blue', 'rare_green', 'common_2', 'common_4', 'common_3', 'common_1', 'wild', 'scatter']
    .map((code) => ({ key: code, label: NAMES[code], img: symbolSrc(code) }));

  DevTools.mount({
    title: 'DEV · Gangsta Casino',
    fields: [
      { key: 'amount', label: 'Сумма', value: 1234500 },
      { key: 'spins', label: 'Фриспинов', value: 10 },
    ],
    tabs: [
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим сразу', items: [
            { label: 'База', run: () => toMode('base', { transition: false }) },
            { label: 'Бонус (фриспины)', run: () => toMode('freespins', { transition: false }) },
          ] },
          { title: 'Режим с переходом', items: [
            { label: 'База → Бонус', run: () => toMode('freespins', { transition: true }) },
            { label: 'Бонус → База', run: () => toMode('base', { transition: true }) },
          ] },
          { title: 'Экраны Spine', items: [
            { label: 'Feature screen', run: () => showFeatureScreen() },
            { label: 'Bonus screen (N спинов)', run: () => showBonusScreen(spinsField()) },
          ] },
          { title: 'Барабаны', items: [
            { label: 'Крутить без остановки', run: () => startReelLoop() },
            { label: 'Остановить', run: () => { stopReelLoop(); applyGrid(SYMBOL_LAYOUT); } },
            { label: 'Сетка из макета', run: () => applyGrid(SYMBOL_LAYOUT) },
            { label: 'Пустой спин', run: () => spin({ grid: fillerGrid() }) },
          ] },
        ],
      },
      {
        title: 'Комбинации',
        sections: [
          {
            title: 'Символ на центральной линии',
            note: 'Настоящий спин с подставленным результатом: стопы, выигрыш, попап, звуки. Вайлд раскрывается на свои барабаны, скаттеры 3+ дают фриспины.',
            matrix: { rows: symbolRows, cols: [3, 4, 5], run: (row, n) => combo(row.key, n) },
          },
          { title: 'Несколько линий', items: [
            { label: '2 линии (Bat ×3 + Boss ×4)', run: () => { const g = fillerGrid(); return spin({ grid: g, lineWins: [lineWin(g, 1, 'common_1', 3), lineWin(g, 2, 'rare_blue', 4)] }); } },
            { label: '3 линии (V + верх + низ)', run: () => { const g = fillerGrid(); return spin({ grid: g, lineWins: [lineWin(g, 2, 'common_3', 3), lineWin(g, 3, 'common_2', 4), lineWin(g, 1, 'rare_green', 3)] }); } },
            { label: 'Вайлд в линии (Knuckles ×4)', run: () => { const g = fillerGrid(); put(g, 1, 2, 'wild'); return spin({ grid: g, lineWins: [lineWin(g, 1, 'common_3', 4)], wildEvents: [{ reel: 2, event: 'expanded' }] }); } },
          ] },
        ],
      },
      {
        title: 'Сценарии',
        sections: [
          { title: 'Антисипация', note: '2 скаттера на 1-3 барабанах → последний барабан тянет.', items: [
            { label: '✓ Удачная (3-й скаттер)', run: () => scatters([0, 2, 4]) },
            { label: '✗ Неудачная (мимо)', run: () => scatters([0, 2]) },
            { label: '✗ Неудачная (2-й и 4-й)', run: () => scatters([1, 3]) },
          ] },
          { title: 'Скаттеры', items: [
            { label: '1 скаттер', run: () => scatters([2]) },
            { label: '2 скаттера (без антисипации)', run: () => scatters([3, 4]) },
            { label: '3 → фриспины', run: () => scatters([0, 2, 4]) },
            { label: '4 → фриспины', run: () => scatters([0, 1, 2, 4]) },
            { label: '5 → фриспины', run: () => scatters([0, 1, 2, 3, 4]) },
          ] },
          { title: 'Фриспины', note: 'Спины ниже работают и в бонусе: счётчик уменьшается, последний спин закрывает раунд попапом TOTAL WIN.', items: [
            { label: 'Спин без выигрыша', run: () => spin({ grid: fillerGrid() }) },
            { label: 'Спин с выигрышем', run: () => combo('rare_yellow', 3) },
            { label: 'Ретриггер (3 скаттера)', run: () => scatters([0, 2, 4]) },
            { label: 'Последний спин → TOTAL', run: () => { if (!inBonus()) return toMode('freespins', { transition: false }); fs.left = 1; return combo('common_4', 3); } },
          ] },
          { title: 'Вайлд', items: [
            { label: 'Вайлд раскрылся, без выигрыша', run: () => { const g = fillerGrid(); put(g, 0, 2, 'wild'); return spin({ grid: g, wildEvents: [{ reel: 2, event: 'expanded' }] }); } },
            { label: '2 вайлда', run: () => { const g = fillerGrid(); put(g, 0, 1, 'wild'); put(g, 2, 3, 'wild'); return spin({ grid: g, wildEvents: [{ reel: 1, event: 'expanded' }, { reel: 3, event: 'expanded' }] }); } },
          ] },
          { title: 'Множители', items: [
            { label: 'x3 + x5 с выигрышем', run: () => multiplierSpin({ values: [3, 5] }) },
            { label: 'x9 с выигрышем', run: () => multiplierSpin({ values: [9] }) },
            { label: 'x2 без выигрыша', run: () => multiplierSpin({ values: [2], win: false }) },
            { label: 'x2 + x3 + x7', run: () => multiplierSpin({ values: [2, 3, 7] }) },
          ] },
        ],
      },
      {
        title: 'Попапы',
        sections: [
          { title: 'Выигрыш (сумма из поля)', items: [
            { label: 'Малый (без попапа)', run: () => { Sound.playSfx('smallWin'); showInlineWinAmount(amount()); } },
            { label: 'BIG WIN', run: () => playPopup('bigWin', amount()) },
            { label: 'MEGA WIN', run: () => playPopup('megaWin', amount()) },
            { label: 'EPIC WIN', run: () => playPopup('epicWin', amount()) },
          ] },
          { title: 'Бонус', items: [
            { label: 'YOU WON N FREE SPINS', run: () => playPopup('bonusSpinsWin', spinsField()) },
            { label: 'TOTAL WIN', run: () => playPopup('bonusSpinsTotalWin', amount()) },
          ] },
          { title: 'Покупка', items: [
            { label: 'Диалог покупки', run: () => openBuyDialog(bet() * BUY_COST_MULTIPLIER) },
            { label: 'Не хватает баланса', run: () => openBuyDialog(bet() * BUY_COST_MULTIPLIER, { affordable: false }) },
            { label: 'Ставка понижена', run: () => openBuyDialog(bet() * BUY_COST_MULTIPLIER, { note: 'BET 275,000 → 55,000' }) },
          ] },
        ],
      },
      {
        title: 'Фичи',
        sections: [
          { title: 'Большой вайлд (превью, без спина)', items: [0, 1, 2, 3, 4].map((col) => ({
            label: `Барабан ${col + 1}`, run: () => previewBigWild(col, true),
          })) },
          { title: 'Множитель', items: [
            { label: 'Демо множителей', run: () => demoMultipliers() },
            { label: 'Плашка +x5', run: () => setMultiplierPlate(5, { lit: true, bump: true }) },
            { label: 'Плашка сброс', run: () => resetMultiplierPlate() },
          ] },
          { title: 'Счётчик фриспинов', items: [
            { label: '−1', run: () => { fs.left = Math.max(0, fs.left - 1); setFreeSpinsCounter(fs.left); } },
            { label: '+10', run: () => { fs.left += 10; setFreeSpinsCounter(fs.left); } },
          ] },
        ],
      },
    ],
  });
})();
