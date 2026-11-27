// Neon Joker Spins — adapter for the shared dev panel (js/dev-tools.js): DEV (screens, every
// line combination, scenarios with success / failed anticipation, Free Spins, Hold & Win with
// Collector and jackpots, popups) and ♪ (Sound.lab of sound.js).
//
// Everything is FRONT-ONLY: a made-up spin response shaped like the backend's is played through
// app.js's real runSpin(), so reel stops, anticipation, wins, popups and sounds fire exactly as on
// a live spin. Pays follow app/seed/neon_joker_spins.py: line pay x (bet / 5 lines), Joker count
// pay x bet, coins 1x..25x / jackpots MINI 20 · MINOR 50 · MAJOR 250 · GRAND 1000 x bet.
// While a dev Free Spins round runs, Api.spin answers locally too (the server knows nothing of it).
(function () {
  if (!window.DevTools) return;
  const LINES = [[1, 1, 1], [0, 0, 0], [2, 2, 2], [0, 1, 2], [2, 1, 0]];
  const PAYS = { wild: 125, seven: 100, bell: 60, star: 40, cherry: 25, lemon: 17.5, plum: 12.5, grape: 10 };
  const JOKER_PAY = { 3: 2, 4: 5, 5: 10, 6: 20, 7: 50, 8: 100, 9: 200 };
  const JP = { mini: 20, minor: 50, major: 250, grand: 1000 };
  const NAMES = { seven: '7', bell: 'Колокол', star: 'Звезда', cherry: 'Вишня', lemon: 'Лайм', plum: 'Слива', grape: 'Виноград', wild: 'Wild' };
  const SYM = (c) => `img/neon-joker-spins/skins/c/sets/r1/symbols/${c}.webp?v=4`;
  const FILL = ['cherry', 'lemon', 'plum', 'grape', 'star', 'bell', 'seven'];
  const rnd = (l) => l[Math.floor(Math.random() * l.length)];
  const bet = () => currentBet();
  const amount = () => Number(DevTools.value('amount')) || 25000;

  // --- grids ------------------------------------------------------------------
  // a grid with no line win, no Joker and no coin
  function filler() {
    for (let t = 0; t < 300; t++) {
      const g = [0, 1, 2].map(() => [0, 1, 2].map(() => rnd(FILL)));
      if (!LINES.some((l) => g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2])) return g;
    }
    return [['cherry', 'lemon', 'plum'], ['grape', 'cherry', 'lemon'], ['plum', 'grape', 'cherry']];
  }
  const clearLines = (g, keep = []) => {
    for (let t = 0; t < 200; t++) {
      const bad = LINES.findIndex((l, n) => !keep.includes(n) && g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2] && !['scatter', 'coin'].includes(g[l[0]][0]));
      if (bad < 0) return g;
      const l = LINES[bad];
      const col = keep.length ? 2 : Math.floor(Math.random() * 3);
      if (keep.some((k) => LINES[k][col] === l[col])) continue;
      g[l[col]][col] = rnd(FILL.filter((c) => c !== g[l[col]][col]));
    }
    return g;
  };
  const cellsOf = (wins) => {
    const seen = new Set(); const out = [];
    for (const w of wins) for (const p of w.positions) { const k = p.row * 3 + p.col; if (!seen.has(k)) { seen.add(k); out.push(p); } }
    return out;
  };
  function lineWin(g, line, code) {
    LINES[line].forEach((r, c) => { g[r][c] = code; });
    return { payline: line + 1, symbol: code, count: 3, positions: LINES[line].map((r, c) => ({ row: r, col: c })), win_amount: (PAYS[code] * bet()) / 5 };
  }
  function response(g, { lines = [], counts = [], feature = null, hw = null } = {}) {
    const wins = [...lines, ...counts];
    const total = wins.reduce((a, w) => a + w.win_amount, 0);
    return { balance: gameState.balance + total, grid: g, line_wins: lines, count_wins: counts, winning_cells: cellsOf(wins),
      total_win: total, feature, hold_and_win: hw, max_win_reached: false };
  }
  const play = (data, opts) => runSpin(() => Promise.resolve(typeof data === 'function' ? data() : data), bet(), opts);
  const busy = () => gameState.isSpinning;
  const need = () => { if (busy()) throw new Error('дождитесь конца спина'); if (gameState.inFreeSpins && !fs) throw new Error('идут настоящие Free Spins'); };

  // --- Free Spins (dev round: Api.spin answers locally while fs is set) ----------------
  let fs = null;
  const realSpin = Api.spin.bind(Api);
  Api.spin = (sid, b) => (fs ? Promise.resolve(fsSpin()) : realSpin(sid, b));
  function fsSpin() {
    fs.left -= 1; fs.n += 1;
    const g = filler(); const lines = [];
    let added = 0;
    if (fs.n === fs.retriggerAt) { [[0, 0], [1, 2], [2, 1]].forEach(([r, c]) => { g[r][c] = 'scatter'; }); added = 5; }
    else if (Math.random() < 0.45) lines.push(lineWin(g, Math.floor(Math.random() * 5), rnd(['cherry', 'lemon', 'plum', 'grape', 'star', 'bell'])));
    clearLines(g, lines.map((w) => w.payline - 1));
    const counts = added ? [{ symbol: 'scatter', count: 3, positions: [{ row: 0, col: 0 }, { row: 1, col: 2 }, { row: 2, col: 1 }], win_amount: JOKER_PAY[3] * bet() }] : [];
    fs.left += added;
    const win = [...lines, ...counts].reduce((a, w) => a + w.win_amount, 0);
    fs.total += win;
    const r = response(g, { lines, counts, feature: { type: 'free_spins', triggered: !!added, spins_awarded: added, spins_remaining: fs.left, total_win: fs.total } });
    if (fs.left <= 0) fs = null;
    return r;
  }
  function startFs(jokers = 3, { retrigger = true } = {}) {
    need();
    const g = filler();
    const spots = [[0, 0], [2, 1], [1, 2], [0, 1], [2, 2], [1, 0], [0, 2], [2, 0], [1, 1]].slice(0, jokers);
    spots.forEach(([r, c]) => { g[r][c] = 'scatter'; });
    const counts = [{ symbol: 'scatter', count: jokers, positions: spots.map(([row, col]) => ({ row, col })), win_amount: JOKER_PAY[jokers] * bet() }];
    fs = { left: 10, total: 0, n: 0, retriggerAt: retrigger ? 3 : -1 };
    return play(response(g, { counts, feature: { type: 'free_spins', triggered: true, spins_awarded: 10, spins_remaining: 10, total_win: 0 } }));
  }

  // --- Hold & Win ------------------------------------------------------------------
  const coin = (row, col, v) => ({ row, col, kind: 'coin', value: v });
  function hwSpin(initial, respins, extra = {}) {
    need();
    const g = filler();
    for (const c of initial) g[c.row][c.col] = 'coin';
    clearLines(g);
    const all = [...initial, ...respins.flatMap((r) => r.landed)];
    const total = all.reduce((a, c) => a + (JP[c.kind] ? JP[c.kind] : Number(c.value)) * bet(), 0) + (extra.full_grid_jackpot ? JP.grand * bet() : 0);
    return play(response(g, { hw: { triggered: true, initial, respins, total_win: total, ...extra } }));
  }
  const HW = {
    plain: () => hwSpin([coin(0, 0, 5), coin(1, 1, 2), coin(2, 0, 10), coin(0, 2, 3), coin(2, 2, 1)],
      [{ landed: [coin(1, 0, 4)] }, { landed: [] }, { landed: [coin(0, 1, 8)] }, { landed: [] }, { landed: [] }, { landed: [] }]),
    collector: () => hwSpin([coin(0, 0, 5), coin(1, 1, 10), coin(2, 0, 3), coin(0, 2, 25), coin(2, 2, 15)],
      [{ landed: [{ row: 0, col: 1, kind: 'collector', value: 58 }] }, { landed: [] }, { landed: [coin(1, 2, 4)] }, { landed: [] }, { landed: [] }, { landed: [] }],
      { collector_total: 58 }),
    jackpot: (tier) => hwSpin([coin(0, 0, 5), coin(1, 1, 2), { row: 2, col: 0, kind: tier, value: JP[tier] }, coin(0, 2, 3), coin(2, 2, 1)],
      [{ landed: [] }, { landed: [coin(1, 0, 6)] }, { landed: [] }, { landed: [] }, { landed: [] }]),
    grand: () => hwSpin([coin(0, 0, 5), coin(1, 1, 2), coin(2, 0, 10), coin(0, 2, 3), coin(2, 2, 1)],
      [{ landed: [coin(0, 1, 4), coin(1, 0, 8)] }, { landed: [coin(1, 2, 2)] }, { landed: [{ row: 2, col: 1, kind: 'major', value: 250 }] }],
      { full_grid_jackpot: 'grand' }),
  };

  // Hold & Win and Free Spins on the same spin: a coin on every reel (top row) + 3 jokers below.
  // The hold plays first with the "FREE SPINS x10 NEXT" plate, then the free spins start.
  function hwPlusFs() {
    need();
    const g = filler();
    const initial = [coin(0, 0, 5), coin(0, 1, 2), coin(0, 2, 10)];
    for (const c of initial) g[c.row][c.col] = 'coin';
    const jokers = [[1, 0], [2, 1], [1, 2]];
    jokers.forEach(([r, c]) => { g[r][c] = 'scatter'; });
    clearLines(g);
    const respins = [{ landed: [coin(2, 0, 3)] }, { landed: [] }, { landed: [] }, { landed: [] }];
    const hwTotal = [...initial, ...respins.flatMap((r) => r.landed)].reduce((a, c) => a + Number(c.value) * bet(), 0);
    const counts = [{ symbol: 'scatter', count: 3, positions: jokers.map(([row, col]) => ({ row, col })), win_amount: JOKER_PAY[3] * bet() }];
    fs = { left: 10, total: 0, n: 0, retriggerAt: -1 };
    return play(response(g, { counts, hw: { triggered: true, initial, respins, total_win: hwTotal },
      feature: { type: 'free_spins', triggered: true, spins_awarded: 10, spins_remaining: 10, total_win: 0 } }));
  }

  // --- scenarios ---------------------------------------------------------------------
  function lineCombo(code, line) {
    need();
    const g = filler();
    const w = lineWin(g, line, code);
    clearLines(g, [line]);
    return play(response(g, { lines: [w] }));
  }
  function bigByLines(n) { // n winning lines of wild/seven -> Big / Mega / Epic tier
    need();
    const g = filler(); const lines = [];
    if (n >= 5) { for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) g[r][c] = 'wild'; for (let k = 0; k < 5; k++) lines.push(lineWin(g, k, 'wild')); }
    else for (let k = 0; k < n; k++) lines.push(lineWin(g, k, k ? 'seven' : 'wild'));
    clearLines(g, lines.map((w) => w.payline - 1));
    return play(response(g, { lines }));
  }
  function anticipation(kind, success) {
    need();
    const g = filler();
    if (kind === 'joker') {
      g[0][0] = 'scatter'; g[2][1] = 'scatter';
      if (success) { g[1][2] = 'scatter'; fs = { left: 10, total: 0, n: 0, retriggerAt: -1 };
        const counts = [{ symbol: 'scatter', count: 3, positions: [{ row: 0, col: 0 }, { row: 2, col: 1 }, { row: 1, col: 2 }], win_amount: JOKER_PAY[3] * bet() }];
        return play(response(g, { counts, feature: { type: 'free_spins', triggered: true, spins_awarded: 10, spins_remaining: 10, total_win: 0 } })); }
      return play(response(clearLines(g)));
    }
    if (kind === 'coins') {
      g[0][0] = 'coin'; g[1][0] = 'coin'; g[2][1] = 'coin';
      if (success) return hwSpinFrom(g);
      g[1][2] = 'coin';
      return play(response(clearLines(g)));
    }
    // line: two sevens on reels 1-2 of the middle line
    g[1][0] = 'seven'; g[1][1] = 'seven';
    if (success) { const w = lineWin(g, 0, 'seven'); clearLines(g, [0]); return play(response(g, { lines: [w] })); }
    g[1][2] = 'cherry';
    return play(response(clearLines(g, [])));
  }
  function hwSpinFrom(g) {
    g[0][2] = 'coin'; g[2][2] = 'coin';
    const initial = [coin(0, 0, 5), coin(1, 0, 3), coin(2, 1, 10), coin(0, 2, 2), coin(2, 2, 1)];
    const respins = [{ landed: [] }, { landed: [coin(1, 1, 6)] }, { landed: [] }, { landed: [] }, { landed: [] }];
    const total = [...initial, coin(1, 1, 6)].reduce((a, c) => a + c.value * bet(), 0);
    return play(response(g, { hw: { triggered: true, initial, respins, total_win: total } }));
  }

  // --- screens -----------------------------------------------------------------------
  function toBase() {
    if (busy()) throw new Error('дождитесь конца спина');
    document.getElementById('buyDialog').hidden = true;
    if (document.getElementById('screen').classList.contains('is-hw')) exitHoldAndWinMode();
    if (gameState.inFreeSpins) { gameState.inFreeSpins = false; gameState.fsLeft = 0; fs = null; }
    setFreeSpinsMode(false);
    return applyGrid(gameState.lastGrid || filler());
  }
  function hwField() {
    if (busy()) throw new Error('дождитесь конца спина');
    enterHoldAndWinMode();
    const spec = [{ v: 5 }, { k: 'collector', v: 58 }, null, null, { v: 10 }, { v: 3 }, { v: 25 }, { k: 'minor' }, { v: 15 }];
    cellInfos.forEach((info, i) => { const s = spec[i]; if (!s) setCellEmpty(info); else setCoinFace(info, { kind: s.k || 'coin', value: s.v || 0 }); });
    setRespinLamps(2);
  }

  const ROWS = Object.keys(PAYS).map((code) => ({ label: NAMES[code], img: SYM(code), key: code }));
  DevTools.mount({
    fields: [{ key: 'amount', label: 'Сумма попапа', value: 25000 }],
    tabs: [
      { title: 'Экраны', sections: [
        { title: 'Режим', items: [
          { label: 'База', run: toBase },
          { label: 'Free Spins (сцена)', run: () => { if (busy()) throw new Error('дождитесь конца спина'); setFreeSpinsMode(true); updateFreeSpinsPanel(10, 0); } },
          { label: 'Поле Hold & Win', run: hwField },
          { label: 'Окно покупки', run: () => document.querySelector('[data-buy-open]').click() },
        ] },
        { title: 'Плашки', items: [
          { label: 'Джекпот MINI', run: () => hitPlate('mini') }, { label: 'MINOR', run: () => hitPlate('minor') },
          { label: 'MAJOR', run: () => hitPlate('major') }, { label: 'GRAND', run: () => hitPlate('grand') },
          { label: 'Маскот радуется', run: () => mascotCheer() },
        ] },
        ...(window.NJS_HOOKS && window.NJS_HOOKS.curtain ? [{ title: 'Переходы между экранами', items: [
          { label: 'Шторы (Hold & Win)', run: () => window.NJS_HOOKS.curtain(() => new Promise((r) => setTimeout(r, 400)), 'hw') },
          { label: 'Двери (Free Spins)', run: () => window.NJS_HOOKS.curtain(() => new Promise((r) => setTimeout(r, 400)), 'fs') },
        ] }] : []),
        ...(window.R1Amounts ? [{ title: 'Суммы (валюта для казино, множители для крипто)', items: [
          { label: 'В валюте', run: () => window.R1Amounts.set('cash') },
          { label: 'В множителях ×', run: () => window.R1Amounts.set('x') },
        ] }] : []),
      ] },
      { title: 'Комбинации', sections: [
        { title: '3 в ряд по линии (1 средняя · 2 верх · 3 низ · 4 ↘ · 5 ↗)', matrix: { rows: ROWS, cols: [1, 2, 3, 4, 5], run: (row, n) => lineCombo(row.key, n - 1) } },
        { title: 'Джокеры (платят в любом месте, 3+ → 10 Free Spins)', items: [3, 4, 5, 6, 9].map((n) => ({ label: `${n} Джокера`, run: () => startFs(n) })) },
        { title: 'Несколько линий', items: [
          { label: 'Big Win (2 линии)', run: () => bigByLines(2) },
          { label: 'Mega Win (3 линии)', run: () => bigByLines(3) },
          { label: 'Epic Win (поле Wild)', run: () => bigByLines(5) },
        ] },
      ] },
      { title: 'Сценарии', sections: [
        { title: 'Ожидание на 3-м барабане', items: [
          { label: '2 Джокера → 3-й есть (Free Spins)', run: () => anticipation('joker', true) },
          { label: '2 Джокера → мимо', run: () => anticipation('joker', false) },
          { label: '3 монеты → Hold & Win', run: () => anticipation('coins', true) },
          { label: '3 монеты → мимо', run: () => anticipation('coins', false) },
          { label: '7 · 7 → третья 7', run: () => anticipation('line', true) },
          { label: '7 · 7 → мимо', run: () => anticipation('line', false) },
        ] },
        { title: 'Free Spins', items: [
          { label: 'Раунд 10 спинов + ретриггер +5', run: () => startFs(3) },
          { label: 'Раунд без ретриггера', run: () => startFs(3, { retrigger: false }) },
        ] },
        { title: 'Hold & Win', items: [
          { label: 'Обычный раунд', run: HW.plain },
          { label: 'С Коллектором', run: HW.collector },
          { label: 'Джекпот MINI', run: () => HW.jackpot('mini') }, { label: 'MINOR', run: () => HW.jackpot('minor') },
          { label: 'MAJOR', run: () => HW.jackpot('major') }, { label: 'GRAND (9/9)', run: HW.grand },
          { label: 'Hold & Win + Free Spins в одном спине', run: hwPlusFs },
        ] },
      ] },
      { title: 'Попапы', sections: [
        { title: 'Сумма — из поля внизу', items: [
          { label: 'BIG WIN', run: () => playPopup('bigWin', amount()) },
          { label: 'MEGA WIN', run: () => playPopup('megaWin', amount()) },
          { label: 'EPIC WIN', run: () => playPopup('epicWin', amount()) },
          { label: 'TOTAL WIN', run: () => playPopup('totalWin', amount(), 2600) },
          { label: 'TOTAL WIN + Collector', run: () => playPopup('totalWin', amount(), 2600, { sub: 'COLLECTOR 58×' }) },
          { label: 'FREE SPINS (10)', run: () => playPopup('freeSpins', 0, 2000, { panelText: '10' }) },
          { label: 'HOLD & WIN', run: () => playPopup('holdAndWin', 0, 1300) },
          { label: 'Сумма в поле выигрыша', run: () => showInlineWinAmount(amount()) },
        ] },
      ] },
    ],
  });
})();
