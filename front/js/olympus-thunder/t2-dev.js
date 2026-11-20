// Olympus Thunder · Tides 2/3 — adapter for the shared dev panel (js/dev-tools.js, shown on localhost or ?dev=1).
//
// Combinations and scatters are FRONT-ONLY: each builds a made-up spin response shaped like the backend's
// (app/api/v1/spin_tumble.py _tumble_out) and plays it through game.js's real pipeline (OTGame.devSpin):
// drop-in, wins, shatter + tumble, orb collect, scatters -> free spins, eagles -> jackpot wheel, win popups.
// Pays follow the seed (app/seed/olympus_thunder.py): x total bet for 8-9 / 10-11 / 12+ anywhere.
(function () {
  if (!window.DevTools || !window.OTGame) return;
  const G = OTGame;
  const COLS = 6, ROWS = 5;
  const PAYTABLE = {
    helmet: { 8: 10, 10: 25, 12: 50 }, lyre: { 8: 2.5, 10: 10, 12: 25 }, amphora: { 8: 2, 10: 5, 12: 15 },
    wreath: { 8: 1.5, 10: 2, 12: 12 }, ruby: { 8: 1, 10: 1.5, 12: 10 }, amethyst: { 8: 0.8, 10: 1.2, 12: 8 },
    emerald: { 8: 0.5, 10: 1, 12: 5 }, sapphire: { 8: 0.4, 10: 0.9, 12: 4 }, citrine: { 8: 0.25, 10: 0.75, 12: 2 },
  };
  const NAMES = {
    helmet: 'Шлем', lyre: 'Лира', amphora: 'Амфора', wreath: 'Венок', ruby: 'Рубин', amethyst: 'Аметист',
    emerald: 'Изумруд', sapphire: 'Сапфир', citrine: 'Цитрин',
  };
  const SYMS = Object.keys(PAYTABLE);
  const SCATTER_PAYS = { 4: 3, 5: 5, 6: 100 };
  const FS_SPINS = 15, RETRIGGER = 5;
  const PRIZES = { mini: 20, minor: 50, major: 250, grand: 1000 };
  const SECTORS = ['mini', 'minor', 'mini', 'major', 'mini', 'mini', 'grand', 'minor', 'mini', 'minor', 'mini', 'major'];
  const ART = document.body.dataset.symbols || 'img/olympus-thunder/tides2/symbols/';

  const bet = () => G.bet();
  const pay = (code, n) => { const t = PAYTABLE[code]; return n >= 12 ? t[12] : n >= 10 ? t[10] : t[8]; };
  const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const allCells = () => { const c = []; for (let col = 0; col < COLS; col++) for (let row = 0; row < ROWS; row++) c.push({ col, row }); return c; };

  // filler: lows/highs with at most 7 of any code (no win of its own), avoiding `avoid`
  function filler(counts, avoid) {
    const pool = SYMS.filter((s) => s !== avoid && (counts[s] || 0) < 7);
    const s = pool[Math.floor(Math.random() * pool.length)] || 'citrine';
    counts[s] = (counts[s] || 0) + 1;
    return s;
  }
  function blankGrid() { return Array.from({ length: ROWS }, () => Array(COLS).fill(null)); }
  function fill(grid, avoid) {
    const counts = {};
    grid.forEach((r) => r.forEach((c) => { if (c) counts[c] = (counts[c] || 0) + 1; }));
    for (let row = 0; row < ROWS; row++) for (let col = 0; col < COLS; col++) if (!grid[row][col]) grid[row][col] = filler(counts, avoid);
    return grid;
  }
  // one tumble: remove `positions`, survivors fall, new filler symbols on top (no new wins)
  function tumble(grid, positions, avoid) {
    const gone = new Set(positions.map((p) => p.col + ':' + p.row));
    const next = blankGrid();
    for (let col = 0; col < COLS; col++) {
      const kept = [];
      for (let row = 0; row < ROWS; row++) if (!gone.has(col + ':' + row)) kept.push(grid[row][col]);
      const missing = ROWS - kept.length;
      for (let row = 0; row < ROWS; row++) next[row][col] = row < missing ? null : kept[row - missing];
    }
    return fill(next, avoid);
  }

  // build a full SpinResponse-like object
  function response({ wins = [], orbs = [], scatters = 0, eagles = 0, jackpotTier = null, inFs = false } = {}) {
    const b = bet(), grid = blankGrid(), free = shuffle(allCells());
    const take = (n) => free.splice(0, n);
    const winPos = wins.map((w) => ({ ...w, pos: take(w.count) }));
    winPos.forEach((w) => w.pos.forEach((p) => { grid[p.row][p.col] = w.symbol; }));
    const orbPos = orbs.map((v) => ({ v, p: take(1)[0] }));
    orbPos.forEach(({ v, p }) => { grid[p.row][p.col] = `orb_${v}`; });
    take(scatters).forEach((p) => { grid[p.row][p.col] = 'scatter'; });
    take(eagles).forEach((p) => { grid[p.row][p.col] = 'eagle'; });
    fill(grid, wins.length ? wins[0].symbol : null);
    const initial = grid.map((r) => r.slice());

    // one step per win (each removes its symbols; the specials stay on the board)
    const steps = [];
    let cur = grid;
    for (const w of winPos) {
      const positions = [];
      cur.forEach((r, row) => r.forEach((c, col) => { if (c === w.symbol) positions.push({ col, row }); }));
      const amount = Math.round(pay(w.symbol, positions.length) * b);
      const after = tumble(cur, positions, w.symbol);
      steps.push({ wins: [{ symbol: w.symbol, count: positions.length, amount, positions }], removed: positions, step_win: amount, grid_after: after });
      cur = after;
    }
    const baseWin = steps.reduce((s, x) => s + x.step_win, 0);
    const orbSum = orbs.reduce((s, v) => s + v, 0);
    const st = G.state;
    const multBefore = inFs ? st.totalMult : 1;
    const multAfter = inFs && baseWin > 0 ? multBefore + orbSum : multBefore;
    const applied = baseWin > 0 && orbSum > 0 ? (inFs ? multAfter : orbSum) : 1;
    const seriesWin = baseWin * applied;
    const scatterWin = SCATTER_PAYS[Math.min(scatters, 6)] ? SCATTER_PAYS[Math.min(scatters, 6)] * b : 0;
    const fsAwarded = inFs ? (scatters >= 3 ? RETRIGGER : 0) : (scatters >= 4 ? FS_SPINS : 0);
    let jackpot = null;
    if (eagles >= 3) {
      const tier = jackpotTier || 'mini';
      const idx = SECTORS.map((t, i) => (t === tier ? i : -1)).filter((i) => i >= 0);
      jackpot = { tier, sector: idx[Math.floor(Math.random() * idx.length)], amount: PRIZES[tier] * b };
    }
    const spinWin = seriesWin + (inFs ? 0 : scatterWin) + (jackpot ? jackpot.amount : 0);
    return {
      grid: initial,
      tumble: {
        mode: inFs ? (st.devSuper ? 'super' : 'fs') : 'base', service: null, steps,
        base_win: baseWin, orbs: orbPos.map(({ v, p }) => ({ col: p.col, row: p.row, value: v })), orb_sum: orbSum,
        applied_multiplier: applied, series_win: seriesWin,
        total_multiplier_before: multBefore, total_multiplier_after: multAfter,
        scatter_count: scatters, scatter_win: inFs ? 0 : scatterWin, free_spins_awarded: fsAwarded,
        eagle_count: eagles, jackpot, capped: false, spin_win: spinWin,
      },
      total_win: spinWin,
      balance: st.balance - (inFs ? 0 : b) + spinWin,
      feature: fsAwarded && !inFs ? { type: 'free_spins', triggered: true, spins_awarded: fsAwarded, spins_remaining: fsAwarded, total_win: 0, multiplier: 1 } : null,
    };
  }

  // ---------- free-spins round of the dev spins (OTGame.runFreeSpins asks OTDev.fsSpin) ----------
  const fsRound = { left: 0, total: 0, queue: [] };
  window.OTDev = {
    async fsSpin() {
      const next = fsRound.queue.shift();
      const data = next ? next() : response({ inFs: true, wins: Math.random() < 0.5 ? [{ symbol: SYMS[3 + Math.floor(Math.random() * 6)], count: 8 }] : [], orbs: Math.random() < 0.4 ? [[2, 3, 5, 10][Math.floor(Math.random() * 4)]] : [] });
      fsRound.left = fsRound.left - 1 + (data.tumble.free_spins_awarded || 0);
      fsRound.total += data.tumble.spin_win;
      data.feature = { type: 'free_spins', triggered: !!data.tumble.free_spins_awarded, spins_awarded: data.tumble.free_spins_awarded || null, spins_remaining: Math.max(0, fsRound.left), total_win: fsRound.total, multiplier: data.tumble.total_multiplier_after };
      return data;
    },
  };

  const inFs = () => G.state.mode === 'fs';
  function play(opts) {
    const data = response({ ...opts, inFs: inFs() });
    if (inFs()) {   // inside a running round: queue it as the next free spin
      if (G.state.devFs) { fsRound.queue.push(() => response({ ...opts, inFs: true })); return; }
    } else if (data.feature) {
      G.state.devFs = true; G.state.devSuper = false;
      fsRound.left = data.feature.spins_remaining; fsRound.total = 0; fsRound.queue = [];
    }
    return G.devSpin(data);
  }

  // symbol sets = the page's presentation switches (?high / ?low are read at start, so reload)
  function setSet(k, v) { const q = new URLSearchParams(location.search); q.set(k, v); location.search = '?' + q; }

  const amount = () => Math.max(1, Number(DevTools.value('amount')) || 1);
  const symbolRows = SYMS.map((k) => ({ key: k, label: NAMES[k], img: `${ART}${k}.webp` }));

  DevTools.mount({
    title: 'DEV · Olympus Thunder',
    fields: [{ key: 'amount', label: 'Сумма попапа', value: 1234500 }],
    tabs: [
      {
        title: 'Комбинации',
        sections: [
          {
            title: 'Символ где угодно (8 / 10 / 12 / 15)',
            note: 'Подставной спин через настоящую анимацию: выигрыш, каскад, звуки, попап по сумме. В бонусе спин встаёт следующим фриспином.',
            matrix: { rows: symbolRows, cols: [8, 10, 12, 15], run: (row, n) => play({ wins: [{ symbol: row.key, count: n }] }) },
          },
          { title: 'Каскады и сферы', items: [
            { label: '2 каскада (Шлем 8 + Лира 10)', run: () => play({ wins: [{ symbol: 'helmet', count: 8 }, { symbol: 'lyre', count: 10 }] }) },
            { label: '3 каскада', run: () => play({ wins: [{ symbol: 'wreath', count: 8 }, { symbol: 'ruby', count: 10 }, { symbol: 'amphora', count: 12 }] }) },
            { label: 'Выигрыш + сфера ×5', run: () => play({ wins: [{ symbol: 'lyre', count: 10 }], orbs: [5] }) },
            { label: 'Выигрыш + сферы ×10 ×25', run: () => play({ wins: [{ symbol: 'amphora', count: 10 }], orbs: [10, 25] }) },
            { label: 'Выигрыш + сфера ×100', run: () => play({ wins: [{ symbol: 'helmet', count: 8 }], orbs: [100] }) },
            { label: 'Сферы без выигрыша (гаснут)', run: () => play({ orbs: [3, 8] }) },
            { label: 'Пустой спин', run: () => play({}) },
          ] },
          { title: 'Уровни выигрыша через спин', items: [
            { label: 'BIG (Шлем 10 = 25×)', run: () => play({ wins: [{ symbol: 'helmet', count: 10 }] }) },
            { label: 'MEGA (Шлем 12 = 50×)', run: () => play({ wins: [{ symbol: 'helmet', count: 12 }] }) },
            { label: 'EPIC (Шлем 12 × сфера 5)', run: () => play({ wins: [{ symbol: 'helmet', count: 12 }], orbs: [5] }) },
          ] },
        ],
      },
      {
        title: 'Скаттеры и орлы',
        sections: [
          { title: 'Скаттеры', note: '4+ в базе = 15 фриспинов (подставной раунд), 3+ в бонусе = +5. 4 / 5 / 6 платят 3× / 5× / 100×.', items:
            [1, 2, 3, 4, 5, 6].map((n) => ({ label: `${n} скаттер${n === 1 ? '' : n < 5 ? 'а' : 'ов'}${(!inFs() && n >= 4) ? ' → FS' : ''}`, run: () => play({ scatters: n }) })) },
          { title: 'Орлы → колесо джекпотов', note: '3 орла запускают колесо; сектор выпадает под выбранный джекпот.', items:
            ['mini', 'minor', 'major', 'grand'].map((t) => ({ label: `3 орла → ${t.toUpperCase()}`, run: () => play({ eagles: 3, jackpotTier: t }) })).concat([{ label: '2 орла (мимо)', run: () => play({ eagles: 2 }) }]) },
        ],
      },
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим сразу', items: [
            { label: 'База', run: () => { G.state.devFs = false; G.setMode('base'); G.plate.reset(); } },
            { label: 'Бонус (фриспины)', run: () => { G.setMode('fs'); G.setTotalMult(1); document.getElementById('fsLeft').textContent = FS_SPINS; G.plate.set(0, 'ВЫИГРЫШ БОНУСА'); } },
          ] },
          { title: 'С переходом', items: [
            { label: 'Запустить бонус (4 скаттера)', run: () => play({ scatters: 4 }) },
          ] },
        ],
      },
      {
        title: 'Сеты',
        sections: [
          { title: 'Рарки (High)', note: 'Перезагружает страницу с выбранным сетом (то же, что шестерёнка слева).', items: [
            { label: 'Luxury', run: () => setSet('high', 'lux') },
            { label: 'Classic', run: () => setSet('high', 'classic') },
          ] },
          { title: 'Коммонки (Low)', items: [
            { label: 'Gems', run: () => setSet('low', 'gems') },
            { label: 'Letters', run: () => setSet('low', 'letters') },
            { label: 'Gems T3', run: () => setSet('low', 'gems3') },
          ] },
        ],
      },
      {
        title: 'Попапы',
        sections: [
          { title: 'Выигрыш (сумма из поля)', items: ['big', 'mega', 'epic'].map((k) => ({ label: k.toUpperCase() + ' WIN', run: () => UI.popup(k, { amount: amount() }) })) },
          { title: 'Джекпоты', items: ['mini', 'minor', 'major', 'grand'].map((k) => ({ label: k.toUpperCase(), run: () => UI.popup('jackpot', { amount: amount(), sub: `${k.toUpperCase()} JACKPOT` }) })) },
          { title: 'Бонус', items: [
            { label: 'FREE SPINS', run: () => UI.popup('fs', { count: FS_SPINS, sub: 'ОБЩИЙ МНОЖИТЕЛЬ ОТ ×1' }) },
            { label: 'SUPER FREE SPINS', run: () => UI.popup('super', { count: FS_SPINS, sub: 'СФЕРЫ В КАЖДОМ СПИНЕ' }) },
            { label: '+5 спинов', run: () => UI.popup('fs', { count: '+5', sub: 'ДОПОЛНИТЕЛЬНЫЕ СПИНЫ', autoMs: 1200 }) },
            { label: 'ИТОГ БОНУСА', run: () => UI.popup('total', { amount: amount(), sub: 'ИТОГ БОНУСА · МНОЖИТЕЛЬ ×12' }) },
          ] },
        ],
      },
    ],
  });
  // only when the DEV / ♪ buttons are really on screen (localhost or ?dev=1)
  const mark = () => { if (document.querySelector('.dt-fab')) document.body.classList.add('has-devtools'); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(mark, 0)); else setTimeout(mark, 0);
})();
