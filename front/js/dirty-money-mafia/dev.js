// Dirty Money / MAFIA — DEV panel (js/dev-tools.js). Every button here is a
// FRONT-ONLY fake spin response shaped like the backend's, played through the
// game's real pipeline via window.__devSpin — so reels, anticipation, win
// cycling, the wheel, popups and sounds all fire exactly as in a live spin.
//
// Deliberately NOT on js/dev-scenarios.js: that builds its tabs around the
// shared flow of js/slot-flow.js and ships a «Проверка» tab that reads the
// flow's trace. This game isn't on that shared flow yet, so those checks would
// report failures that mean nothing. Everything else it offers is here, plus
// the two things this slot has and no other does: the Wheel of Fortune and the
// reel-height wild.
//
// Pays follow app/seed/dirty_money_mafia.py.
(function () {
  const COMMON = { 3: 2, 4: 5, 5: 10 };
  const RARE = { 3: 10, 4: 25, 5: 50 };
  const WILD = { 3: 20, 4: 60, 5: 150 };
  const SCATTER = { 3: 2, 4: 10, 5: 50 };

  // The seed's 20 paylines, in its order — line 1 is the middle row.
  const LINES = [
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
    [0, 0, 1, 0, 0], [2, 2, 1, 2, 2], [1, 0, 0, 0, 1], [1, 2, 2, 2, 1], [0, 1, 1, 1, 0],
    [2, 1, 1, 1, 2], [1, 0, 1, 0, 1], [1, 2, 1, 2, 1], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2],
    [0, 2, 0, 2, 0], [2, 0, 2, 0, 2], [1, 1, 0, 1, 1], [1, 1, 2, 1, 1], [0, 2, 2, 2, 0],
  ];
  // Drum order of the wheel, straight from the seed's wheel_of_fortune params.
  const WHEEL_SEGMENTS = [
    { type: 'multiplier', value: 2 }, { type: 'multiplier', value: 3 },
    { type: 'multiplier', value: 4 }, { type: 'multiplier', value: 5 },
    { type: 'multiplier', value: 6 }, { type: 'multiplier', value: 7 },
    { type: 'multiplier', value: 8 }, { type: 'free_spins', value: null },
  ];
  const TIER_POPUP = { 3: 'bigWin', 4: 'megaWin', 5: 'epicWin' };

  const SYMBOLS = [
    { code: 'rare_red', name: 'Don', pays: RARE, high: true },
    { code: 'rare_yellow', name: 'Consigliere', pays: RARE, high: true },
    { code: 'rare_blue', name: 'Enforcer', pays: RARE, high: true },
    { code: 'rare_green', name: 'Bootlegger', pays: RARE, high: true },
    { code: 'common_red', name: 'Red Chip', pays: COMMON },
    { code: 'common_yellow', name: 'Gold Chip', pays: COMMON },
    { code: 'common_green', name: 'Green Chip', pays: COMMON },
    { code: 'common_blue', name: 'Blue Chip', pays: COMMON },
  ];
  const PAYS = { wild: WILD, scatter: SCATTER };
  for (const s of SYMBOLS) PAYS[s.code] = s.pays;
  const HIGH = new Set([...SYMBOLS.filter((s) => s.high).map((s) => s.code), 'wild']);

  const symbolSrc = (code) => `${ASSET_ROOT}/${SYMBOL_FOLDERS[code]}/${staticFileFor(code)}`;
  const rnd = (list) => list[Math.floor(Math.random() * list.length)];
  const bet = () => gameState.betSteps[gameState.betIndex];
  const lineBet = () => bet() / LINES.length;
  const inBonus = () => currentMode() === 'freespins';
  const amountField = () => Number(DevTools.value('amount')) || 0;
  const spinsField = () => Number(DevTools.value('spins')) || 10;

  // Free-spins bookkeeping for the fake round (the backend normally owns it).
  const fs = { left: 0, total: 0 };

  // --- grid / win builders ---------------------------------------------------

  // A grid of plain symbols that accidentally wins nothing: redraw until no
  // payline has 3 matching from reel 0.
  function fillerGrid() {
    for (let k = 0; k < 300; k++) {
      const g = Array.from({ length: GRID_ROWS }, () => Array.from({ length: GRID_COLS }, () => rnd(FILLER_CODES)));
      if (!LINES.some((l) => g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2])) return g;
    }
    return Array.from({ length: GRID_ROWS }, (_, r) =>
      Array.from({ length: GRID_COLS }, (_, c) => FILLER_CODES[(r * GRID_COLS + c) % FILLER_CODES.length]));
  }

  function lineWin(g, line, code, n) {
    const positions = [];
    for (let col = 0; col < n; col++) {
      const row = LINES[line - 1][col];
      g[row][col] = code;
      positions.push({ row, col });
    }
    // Break the line right after it, or the "x3" would read as a longer win.
    if (n < GRID_COLS) {
      const r = LINES[line - 1][n];
      while (g[r][n] === code) g[r][n] = rnd(FILLER_CODES.filter((c) => c !== code));
    }
    return { payline: line, symbol: code, count: n, positions, amount: Math.round((PAYS[code][n] || 0) * lineBet()) };
  }

  function devSpin({ grid, lineWins = [], countWins = [], wildEvents = [], wheel = null, triggers = 0, extra = {} }) {
    const cells = new Map();
    for (const w of [...lineWins, ...countWins]) for (const p of w.positions) cells.set(`${p.row}:${p.col}`, p);
    let total = lineWins.reduce((s, w) => s + w.amount, 0) + countWins.reduce((s, w) => s + w.amount, 0);
    if (wheel && wheel.prize_type === 'multiplier') total += wheel.win_amount;

    let popup = null;
    const best = lineWins.reduce((b, w) => (HIGH.has(w.symbol) && w.count > (b ? b.count : 0) ? w : b), null);
    if (best) popup = { type: TIER_POPUP[best.count], amount: total };

    // The wheel's free-spins segment awards the round the same way scatters do.
    const wheelFs = wheel && wheel.prize_type === 'free_spins';
    const n = countWins.length ? countWins[0].count : 0;
    const award = triggers ? ({ 3: 10, 4: 15, 5: 20 }[n] || 10) : (wheelFs ? 10 : 0);

    let feature = null;
    if (inBonus()) {
      fs.total += total;
      fs.left = Math.max(0, fs.left - 1) + award;
      if (award) popup = { type: 'bonusSpinsWin', amount: award };
      if (fs.left > 0) feature = { type: 'free_spins', triggered: !!award, spins_remaining: fs.left, total_win: fs.total };
      else popup = { type: 'bonusSpinsTotalWin', amount: fs.total };
    } else if (award) {
      fs.left = award;
      fs.total = total;
      feature = { type: 'free_spins', triggered: true, spins_remaining: fs.left, total_win: total };
      popup = { type: 'bonusSpinsWin', amount: award };
    }

    return window.__devSpin({
      grid,
      winning_cells: [...cells.values()],
      line_wins: lineWins,
      count_wins: countWins,
      wild_events: wildEvents,
      wheel_of_fortune: wheel,
      total_win: total,
      feature,
      popup,
      coin_multiplier: null,
      hold_and_win: null,
      avalanche: null,
      ...extra,
    });
  }

  // --- scenarios -------------------------------------------------------------

  function combo(code, n) {
    const g = fillerGrid();
    if (code === 'scatter') return scatters(n === 3 ? [0, 2, 4] : Array.from({ length: n }, (_, i) => i));
    if (code === 'wof') return wheelTriggerSpin(0);
    const w = lineWin(g, 1, code, n);
    const wildEvents = code === 'wild' ? w.positions.map((p) => ({ reel: p.col, event: 'expanded' })) : [];
    return devSpin({ grid: g, lineWins: [w], wildEvents });
  }

  function scatters(cols) {
    const g = fillerGrid();
    const positions = cols.map((col) => ({ row: Math.floor(Math.random() * GRID_ROWS), col }));
    for (const p of positions) g[p.row][p.col] = 'scatter';
    const n = positions.length;
    const trig = n >= 3;
    const countWins = trig
      ? [{ symbol: 'scatter', count: n, positions, amount: Math.round((SCATTER[Math.min(5, n)] || 0) * bet()) }]
      : [];
    return devSpin({ grid: g, countWins, triggers: trig ? 1 : 0 });
  }

  // 3 wheel symbols land, the wheel opens on `segment`.
  function wheelTriggerSpin(segment) {
    const g = fillerGrid();
    const spots = [{ row: 0, col: 0 }, { row: 1, col: 2 }, { row: 2, col: 4 }];
    for (const p of spots) g[p.row][p.col] = 'wof';
    const seg = WHEEL_SEGMENTS[segment];
    const wheel = {
      segment_index: segment,
      prize_type: seg.type,
      multiplier: seg.type === 'multiplier' ? seg.value : null,
      win_amount: seg.type === 'multiplier' ? seg.value * bet() : 0,
      segments: WHEEL_SEGMENTS,
    };
    return devSpin({ grid: g, wheel });
  }

  const twoLines = () => {
    const g = fillerGrid();
    return devSpin({ grid: g, lineWins: [lineWin(g, 1, 'common_blue', 3), lineWin(g, 2, 'rare_red', 4)] });
  };
  const wildInLine = () => {
    const g = fillerGrid();
    const w = lineWin(g, 1, 'common_green', 4);
    g[1][2] = 'wild';
    return devSpin({ grid: g, lineWins: [w], wildEvents: [{ reel: 2, event: 'expanded' }] });
  };

  const toMode = (mode, transition, spins = 10) => {
    if (currentMode() === mode) return Promise.resolve();
    if (transition) return setFreeSpinsMode(mode === 'freespins', spins);
    applyModeScreen(mode);
    Sound.playMusic(mode === 'freespins' ? 'bonus' : 'base');
    return Promise.resolve();
  };
  const startBonus = async (transition = false) => {
    fs.left = spinsField();
    fs.total = 0;
    await toMode('freespins', transition, fs.left);
    updateFreeSpinsCounter(fs.left);
  };

  // --- panel -----------------------------------------------------------------

  const symbolRows = [
    ...SYMBOLS.map((s) => ({ key: s.code, label: s.name, img: symbolSrc(s.code) })),
    { key: 'wild', label: 'Wild', img: symbolSrc('wild') },
    { key: 'scatter', label: 'Scatter', img: symbolSrc('scatter') },
  ];

  DevTools.mount({
    title: 'DEV · Dirty Money / MAFIA',
    fields: [{ key: 'amount', label: 'Сумма', value: 1234500 }, { key: 'spins', label: 'Фриспинов', value: 10 }],
    tabs: [
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим сразу', items: [
            { label: 'База', run: () => toMode('base', false) },
            { label: 'Бонус (фриспины)', run: () => startBonus(false) },
          ] },
          { title: 'Режим с переходом', items: [
            { label: 'База → Бонус', run: () => startBonus(true) },
            { label: 'Бонус → База', run: () => toMode('base', true) },
          ] },
          // Превью-экраны фичи и бонуса — они есть только в этой (pages)
          // сборке, в dev-копии игры их нет.
          { title: 'Превью-экраны', items: [
            { label: 'Feature screen', run: () => showFeatureScreen() },
            { label: 'Bonus screen', run: () => showBonusScreen(spinsField()) },
          ] },
          { title: 'Барабаны', items: [
            { label: 'Пустой спин', run: () => devSpin({ grid: fillerGrid() }) },
            { label: 'Крутить без остановки', run: () => startReelLoop() },
            { label: 'Остановить, сетка макета', run: () => { stopReelLoop(); return applyGrid(SYMBOL_LAYOUT); } },
          ] },
        ],
      },
      {
        title: 'Комбинации',
        sections: [
          { title: 'Символ на центральной линии',
            note: 'Настоящий спин с подставленным результатом: стопы, выигрыш, попап, звуки.',
            matrix: { rows: symbolRows, cols: [3, 4, 5], run: (row, n) => combo(row.key, n) } },
          { title: 'Несколько линий', items: [
            { label: '2 линии (дешёвая ×3 + дорогая ×4)', run: twoLines },
            { label: 'Вайлд в линии ×4', run: wildInLine },
          ] },
        ],
      },
      {
        title: 'Сценарии',
        sections: [
          { title: 'Антисипация', note: '2 скаттера на 1–4 барабанах → последний тянет.', items: [
            { label: '✓ Удачная (3-й скаттер)', run: () => scatters([0, 2, 4]) },
            { label: '✗ Неудачная (мимо)', run: () => scatters([0, 2]) },
            { label: '✗ Неудачная (2-й и 4-й)', run: () => scatters([1, 3]) },
          ] },
          { title: 'Скаттеры', items: [1, 2, 3, 4, 5].map((n) => ({
            label: n < 3 ? `${n} скаттер${n > 1 ? 'а' : ''}` : `${n} → фриспины`,
            run: () => scatters(n === 1 ? [2] : n === 2 ? [3, 4] : n === 3 ? [0, 2, 4] : Array.from({ length: n }, (_, i) => i)),
          })) },
          { title: 'Фриспины', note: 'В бонусе счётчик уменьшается, последний спин закрывает раунд попапом TOTAL WIN.', items: [
            { label: 'Спин без выигрыша', run: () => devSpin({ grid: fillerGrid() }) },
            { label: 'Спин с выигрышем', run: () => combo('rare_red', 3) },
            { label: 'Ретриггер (3 скаттера)', run: () => scatters([0, 2, 4]) },
            { label: 'Последний спин → TOTAL', run: () => { if (!inBonus()) return startBonus(false); fs.left = 1; return combo('common_blue', 3); } },
          ] },
        ],
      },
      {
        title: 'Колесо',
        sections: [
          { title: 'Спин с 3 WOF → колесо',
            note: 'Полный путь: символы WOF отыгрывают свою анимацию, затем открывается колесо и доводится до сегмента.',
            items: WHEEL_SEGMENTS.map((seg, i) => ({
              label: seg.type === 'free_spins' ? 'FREE SPINS' : `×${seg.value}`,
              run: () => wheelTriggerSpin(i),
            })) },
          { title: 'Только попап колеса (без спина)', items: WHEEL_SEGMENTS.map((seg, i) => ({
            label: seg.type === 'free_spins' ? 'FREE SPINS' : `×${seg.value}`,
            run: () => playWheelOfFortune({
              segment_index: i,
              prize_type: seg.type,
              multiplier: seg.type === 'multiplier' ? seg.value : null,
              win_amount: seg.type === 'multiplier' ? seg.value * bet() : 0,
              segments: WHEEL_SEGMENTS,
            }),
          })) },
        ],
      },
      {
        title: 'Фичи',
        sections: [
          { title: 'Раскрывающийся вайлд (превью, без спина)',
            items: [0, 1, 2, 3, 4].map((col) => ({ label: `Барабан ${col + 1}`, run: () => previewBigWild(col, true) })) },
          { title: 'Вайлд в спине', items: [
            { label: 'Раскрылся, без выигрыша', run: () => { const g = fillerGrid(); g[0][2] = 'wild'; return devSpin({ grid: g, wildEvents: [{ reel: 2, event: 'expanded' }] }); } },
            { label: '2 вайлда', run: () => { const g = fillerGrid(); g[0][1] = 'wild'; g[2][3] = 'wild'; return devSpin({ grid: g, wildEvents: [{ reel: 1, event: 'expanded' }, { reel: 3, event: 'expanded' }] }); } },
          ] },
          { title: 'Счётчик фриспинов', items: [
            { label: '−1', run: () => { fs.left = Math.max(0, fs.left - 1); updateFreeSpinsCounter(fs.left); } },
            { label: '+10', run: () => { fs.left += 10; updateFreeSpinsCounter(fs.left); } },
          ] },
        ],
      },
      {
        title: 'Попапы',
        sections: [
          { title: 'Выигрыш (сумма из поля)', items: [
            { label: 'Малый (без попапа)', run: () => { Sound.playSfx('smallWin'); showInlineWinAmount(amountField()); } },
            { label: 'BIG WIN', run: () => playPopup('bigWin', amountField()) },
            { label: 'MEGA WIN', run: () => playPopup('megaWin', amountField()) },
            { label: 'EPIC WIN', run: () => playPopup('epicWin', amountField()) },
          ] },
          { title: 'Бонус', items: [
            { label: 'YOU WON N FREE SPINS', run: () => playPopup('bonusSpinsWin', spinsField()) },
            { label: 'TOTAL WIN', run: () => playPopup('bonusSpinsTotalWin', amountField()) },
            { label: 'Покупка фриспинов', run: () => playPopup('buyFreeSpins', bet() * 100) },
          ] },
        ],
      },
    ],
  });

  window.__dev = { fs, devSpin, fillerGrid, lineWin, combo, scatters, wheelTriggerSpin, inBonus, bet };
})();
