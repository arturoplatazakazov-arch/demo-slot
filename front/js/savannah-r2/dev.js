// Savannah Kings R2 — DEV panel (js/dev-tools.js, the shared DEV + ♪ pult).
// Replaces the old DEMO panel (js/savannah-r2/demo.js is no longer loaded).
// Every combination is a FRONT-ONLY fake spin response shaped like the
// backend's, played through the game's real pipeline via window.__devSpin
// (app.js runSpin), so reels, anticipation, the lion's expansion, win lines,
// the Jackpot Wheel, popups, sounds and the leopard's reactions all fire
// exactly as in a live spin. Visible on localhost and with ?dev=1 only.
//
// Pays follow app/seed/savannah_kings.py.
(function () {
  if (!window.DevTools || !window.SK) return;

  // Per-line pays in coins (1 coin = bet / 20).
  const PAYS = {
    elephant: { 3: 50, 4: 200, 5: 1000 }, buffalo: { 3: 40, 4: 150, 5: 600 },
    leopard: { 3: 30, 4: 100, 5: 400 }, zebra: { 3: 25, 4: 80, 5: 300 },
    a: { 3: 10, 4: 40, 5: 150 }, k: { 3: 10, 4: 30, 5: 125 },
    q: { 3: 8, 4: 25, 5: 100 }, j: { 3: 8, 4: 20, 5: 80 },
  };
  const SCATTER = { 3: 2, 4: 5, 5: 20 };              // x total bet
  const LINES = SK.PAYLINES;                            // 20 lines, row per reel
  const FILLER = ['a', 'k', 'q', 'j', 'zebra', 'leopard', 'buffalo', 'elephant'];
  // The GDD drum: 12 sectors, 6 Mini, 3 Minor, 2 Major, 1 Grand.
  const DRUM = ['grand', 'mini', 'minor', 'mini', 'major', 'mini', 'minor', 'mini', 'major', 'mini', 'minor', 'mini'];
  const SEGMENTS = DRUM.map((tier) => ({ type: 'multiplier', tier, value: SK.TIER_X[tier] }));
  const NAMES = { elephant: 'Слон', buffalo: 'Буйвол', leopard: 'Леопард', zebra: 'Зебра', a: 'A', k: 'K', q: 'Q', j: 'J' };

  const rnd = (list) => list[Math.floor(Math.random() * list.length)];
  const bet = () => (st.inFs ? st.fsBet : st.betSteps[st.betIndex]);
  const coin = () => bet() / 20;
  const amountField = () => Number(DevTools.value('amount')) || 0;
  const spinsField = () => Number(DevTools.value('spins')) || 10;
  const leo = (k, on) => window.SK_LIVING && SK_LIVING.react(k, on);

  // --- grid / win builders ---------------------------------------------------

  // Plain symbols that win nothing: no payline with 3 alike from reel 1, no
  // scatter, paw or lion.
  function fillerGrid() {
    for (let t = 0; t < 400; t++) {
      const g = Array.from({ length: 3 }, () => Array.from({ length: 5 }, () => rnd(FILLER)));
      if (!LINES.some((l) => g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2])) return g;
    }
    return [['a', 'k', 'q', 'j', 'a'], ['zebra', 'leopard', 'buffalo', 'elephant', 'zebra'], ['j', 'q', 'k', 'a', 'j']];
  }
  function lineWin(g, line, code, n) {
    const positions = [];
    for (let col = 0; col < n; col++) {
      const row = LINES[line - 1][col];
      g[row][col] = code;
      positions.push({ row, col });
    }
    if (n < 5) {
      const r = LINES[line - 1][n];
      while (g[r][n] === code) g[r][n] = rnd(FILLER.filter((c) => c !== code));
    }
    return { payline: line, symbol: code, count: n, positions, amount: Math.round((PAYS[code][n] || 0) * coin()) };
  }

  // Free-spins bookkeeping the backend normally owns: inside the bonus every
  // fake spin uses one spin (app.js already took it off the counter when it
  // was pressed by hand — a DEV button doesn't press, so it is taken here).
  function devSpin({ grid, lineWins = [], countWins = [], wildEvents = [], wheel = null, triggers = false }) {
    const cells = new Map();
    for (const w of [...lineWins, ...countWins]) for (const p of w.positions) cells.set(`${p.row}:${p.col}`, p);
    const lineTotal = lineWins.reduce((s, w) => s + w.amount, 0) + countWins.reduce((s, w) => s + w.amount, 0);
    const total = lineTotal + (wheel ? wheel.win_amount : 0);
    let feature = null;
    if (st.inFs) {
      const left = Math.max(0, st.fsRemaining - 1) + (triggers ? 5 : 0);
      feature = { type: 'free_spins', triggered: triggers, spins_awarded: triggers ? 5 : 0, spins_remaining: left, total_win: st.fsTotal + total };
    } else if (triggers) {
      const n = spinsField();
      feature = { type: 'free_spins', triggered: true, spins_awarded: n, spins_remaining: n, total_win: 0 };
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
      balance: st.balance - (st.inFs ? 0 : bet()) + total,
    });
  }

  // --- scenarios -------------------------------------------------------------

  const combo = (code, n) => { const g = fillerGrid(); return devSpin({ grid: g, lineWins: [lineWin(g, 1, code, n)] }); };
  function lines(list) {
    const g = fillerGrid();
    return devSpin({ grid: g, lineWins: list.map(([line, code, n]) => lineWin(g, line, code, n)) });
  }
  // Masks on the given reels; 3+ pay and start (or extend) the free spins.
  function scatters(cols) {
    const g = fillerGrid();
    const positions = cols.map((col) => ({ row: Math.floor(Math.random() * 3), col }));
    for (const p of positions) g[p.row][p.col] = 'scatter';
    const n = positions.length;
    const countWins = n >= 3 ? [{ symbol: 'scatter', count: n, positions, amount: Math.round(SCATTER[Math.min(5, n)] * bet()) }] : [];
    return devSpin({ grid: g, countWins, triggers: n >= 3 });
  }
  // Paws on the given reels (they land on 1, 3 and 5 only); 3 open the wheel.
  function paws(cols, tier) {
    const g = fillerGrid();
    for (const col of cols) g[Math.floor(Math.random() * 3)][col] = 'paw';
    let wheel = null;
    if (cols.length >= 3) {
      const idx = tier ? DRUM.indexOf(tier) : Math.floor(Math.random() * DRUM.length);
      const t = DRUM[idx];
      wheel = { segments: SEGMENTS, segment_index: idx, tier: t, win_amount: Math.round(SK.TIER_X[t] * bet()) };
    }
    return devSpin({ grid: g, wheel });
  }
  // A lion on `col` (reels 2-4) that expands; `withCode` lays a mask / paw
  // in the same reel (it stays on top of the lion).
  function lion(col, { win = true, withCode = null } = {}) {
    const g = fillerGrid();
    const lineWins = [];
    if (win) {
      const w = lineWin(g, 1, 'elephant', 4);
      w.amount = Math.round(PAYS.elephant[4] * coin());
      lineWins.push(w);
    }
    g[0][col] = 'wild';
    if (withCode) g[2][col] = withCode;
    return devSpin({ grid: g, lineWins, wildEvents: [{ reel: col, event: 'expanded' }] });
  }

  // --- modes -----------------------------------------------------------------

  async function toBonus(transition) {
    if (st.inFs) return;
    st.inFs = true; st.fsBet = st.betSteps[st.betIndex]; st.fsRemaining = spinsField(); st.fsTotal = 0;
    syncControls();
    if (transition) await SK.enterFreeSpins(st.fsRemaining);
    else { applyMode('freespins'); Sound.playMusic('bonus'); }
    SK.setFsPanel(st.fsRemaining, st.fsTotal);
  }
  async function toBase(transition) {
    if (!st.inFs) return;
    if (transition) await SK.leaveFreeSpins(st.fsTotal || amountField());
    else { applyMode('base'); Sound.playMusic('base'); }
    st.inFs = false; st.fsTotal = 0; st.fsRemaining = 0;
    syncControls(); renderBet();
  }

  // --- panel -----------------------------------------------------------------

  const symbolRows = Object.keys(PAYS).map((code) => ({ key: code, label: NAMES[code], img: SK.symbolSrc(code) }));
  const wheelItems = (fn) => ['mini', 'minor', 'major', 'grand'].map((t) => ({ label: t.toUpperCase(), run: () => fn(t) }));

  DevTools.mount({
    title: 'DEV · Savannah Kings R2',
    fields: [{ key: 'amount', label: 'Сумма', value: 1234500 }, { key: 'spins', label: 'Фриспинов', value: 10 }],
    tabs: [
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим сразу', items: [
            { label: 'База (закат)', run: () => toBase(false) },
            { label: 'Фриспины (ночь)', run: () => toBonus(false) },
          ] },
          { title: 'Режим с переходом', items: [
            { label: 'База → Фриспины', run: () => toBonus(true) },
            { label: 'Фриспины → База (TOTAL WIN)', run: () => toBase(true) },
          ] },
          { title: 'Барабаны', items: [
            { label: 'Пустой спин', run: () => devSpin({ grid: fillerGrid() }) },
            { label: 'Крутить без остановки', run: () => SK.startReelLoop() },
            { label: 'Остановить', run: () => { SK.stopReelLoop(); SK.applyGrid(fillerGrid()); } },
          ] },
        ],
      },
      {
        title: 'Комбинации',
        sections: [
          { title: 'Символ на центральной линии',
            note: 'Настоящий спин с подставленным результатом: стопы, линия, попап по сумме, звуки, леопард.',
            matrix: { rows: symbolRows, cols: [3, 4, 5], run: (row, n) => combo(row.key, n) } },
          { title: 'Несколько линий сразу', items: [
            { label: '2 линии', run: () => lines([[1, 'k', 3], [4, 'leopard', 4]]) },
            { label: '3 линии', run: () => lines([[1, 'q', 3], [4, 'zebra', 3], [5, 'buffalo', 4]]) },
            { label: '5 линий', run: () => lines([[1, 'a', 3], [2, 'j', 3], [3, 'k', 3], [4, 'q', 3], [5, 'zebra', 3]]) },
          ] },
        ],
      },
      {
        title: 'Сценарии',
        sections: [
          { title: 'Ожидание 3-го скаттера', note: '2 маски → последние барабаны тянут, леопард смотрит на поле.', items: [
            { label: '✓ Удачное (3 маски)', run: () => scatters([0, 2, 4]) },
            { label: '✗ Неудачное', run: () => scatters([0, 2]) },
          ] },
          { title: 'Ожидание 3-й лапы', note: 'Лапы встают только на 1, 3 и 5 барабаны.', items: [
            { label: '✓ Удачное → колесо', run: () => paws([0, 2, 4]) },
            { label: '✗ Неудачное', run: () => paws([0, 2]) },
          ] },
          { title: 'Маски', items: [1, 2, 3, 4, 5].map((n) => ({
            label: n < 3 ? `${n} маск${n > 1 ? 'и' : 'а'}` : `${n} → фриспины`,
            run: () => scatters(n === 1 ? [2] : n === 2 ? [1, 3] : n === 3 ? [0, 2, 4] : Array.from({ length: n }, (_, i) => i)),
          })) },
          { title: 'В фриспинах', note: 'Счётчик уменьшается, последний спин закрывает раунд попапом TOTAL WIN.', items: [
            { label: 'Спин без выигрыша', run: () => (st.inFs ? devSpin({ grid: fillerGrid() }) : toBonus(false)) },
            { label: 'Спин с выигрышем', run: () => (st.inFs ? combo('buffalo', 4) : toBonus(false)) },
            { label: 'Ретриггер (+5)', run: () => (st.inFs ? scatters([0, 2, 4]) : toBonus(false)) },
            { label: 'Последний спин → TOTAL', run: () => { if (!st.inFs) return toBonus(false); st.fsRemaining = 1; return combo('zebra', 3); } },
          ] },
        ],
      },
      {
        title: 'Колесо',
        sections: [
          { title: 'Спин с 3 лапами → колесо', note: 'Полный путь: лапы вспыхивают, леопард вскакивает, колесо доводится до сектора, экран джекпота.', items: wheelItems((t) => paws([0, 2, 4], t)) },
          { title: 'Только экран джекпота', items: wheelItems((t) => SK_award(t)) },
        ],
      },
      {
        title: 'WILD',
        sections: [
          { title: 'Лев раскрывается в спине', items: [1, 2, 3].map((col) => ({ label: `Барабан ${col + 1}`, run: () => lion(col) })) },
          { title: 'Поверх раскрытого льва', note: 'Маска и лапа остаются сверху и считаются.', items: [
            { label: 'Лев + маска', run: () => lion(2, { win: false, withCode: 'scatter' }) },
            { label: 'Лев + лапа', run: () => lion(2, { win: false, withCode: 'paw' }) },
          ] },
          { title: 'Без выигрыша', items: [{ label: 'Лев раскрылся, линии нет', run: () => lion(2, { win: false }) }] },
        ],
      },
      {
        title: 'Попапы',
        sections: [
          { title: 'Выигрыш (сумма из поля)', items: [
            { label: 'Малый (без попапа)', run: () => { Sound.playSfx('smallWin'); SK.showInlineWinAmount(amountField()); } },
            { label: 'BIG WIN', run: () => SK.playPopup('bigWin', amountField()) },
            { label: 'MEGA WIN', run: () => SK.playPopup('megaWin', amountField()) },
            { label: 'EPIC WIN', run: () => SK.playPopup('epicWin', amountField()) },
          ] },
          { title: 'Фриспины', items: [
            { label: 'FREE SPINS AWARDED', run: () => SK.playPopup('freeSpinsIntro', spinsField()) },
            { label: 'EXTRA FREE SPINS', run: () => SK.playPopup('freeSpinsMore', 5) },
            { label: 'TOTAL WIN', run: () => SK.playPopup('freeSpinsTotal', amountField()) },
          ] },
          { title: 'Джекпоты (попап)', note: 'Только попап джекпота поверх игры, без колеса. Сумма = множитель тира × ставка.', items: wheelItems((t) => SK_award(t, { alone: true })) },
          { title: 'Колесо джекпотов', note: 'Спин с 3 лапами: колесо, остановка на секторе, затем попап джекпота.', items: wheelItems((t) => paws([0, 2, 4], t)) },
        ],
      },
      {
        title: 'Фон',
        sections: [
          { title: 'Леопард', items: [
            { label: 'Поднять голову', run: () => SK_LIVING.leopard() },
            { label: 'Смотрит на поле (2 скаттера)', run: () => { leo('look', true); setTimeout(() => leo('look', false), 3500); } },
            { label: 'Вскакивает (Big Win, колесо)', run: () => leo('jump') },
          ] },
          { title: 'События фона', note: 'В игре — одно за раз, с паузами, не во время спина.', items: [
            { label: 'Стадо', run: () => SK_LIVING.herd() },
            { label: 'Слон на водопой', run: () => SK_LIVING.herd('elephant') },
            { label: 'Птицы (днём)', run: () => SK_LIVING.birds() },
            { label: 'Глаза в темноте (ночью)', run: () => SK_LIVING.eyes() },
          ] },
        ],
      },
    ],
  });

  // The jackpot award screen on its own (the wheel's last step).
  function SK_award(tier, opts) { return showJackpotAward(tier, Math.round(SK.TIER_X[tier] * bet()), opts); }

  window.__dev = { devSpin, fillerGrid, lineWin, combo, lines, scatters, paws, lion, toBonus, toBase };
})();
