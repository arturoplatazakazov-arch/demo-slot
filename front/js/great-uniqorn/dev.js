// Great Uniqorn — adapter for the shared dev panel (js/dev-tools.js), the same
// DEV / ♪ as Gangsta Casino. Unlike the other games it is ON on the deployed
// page too (the client reviews states and sound there); ?dev=0 hides it.
//
// Combinations and events are FRONT-ONLY: each builds a grid, evaluates it the
// way the backend does (app/seed/great_uniqorn.py — 11 lines, wilds substitute
// and multiply the line by their xN, scatters pay anywhere and give free
// spins) and plays the made-up response through app.js's real runSpin
// (window.__devSpin): reel stops, anticipation, wild -> multiplier reveal,
// Spine wins, win lines, popups and every sound fire exactly as on a live
// spin, so the ♪ log shows what a given outcome sounds like.
//
// «Своя сетка»: 15 codes, rows split by «/» — a j k q hair docs jet wild
// scatter, x2 x3 x5 x7 x9 = a wild that turns into that multiplier.
(function () {
  if (!window.DevTools) return;
  if (new URLSearchParams(location.search).get('dev') !== '0') {
    window.SLOT_CONFIG = window.SLOT_CONFIG || {};
    window.SLOT_CONFIG.showDevPanels = true;
  }

  const LINES = [ // payline n = LINES[n-1]: row per reel
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2], [1, 0, 1, 0, 1],
    [1, 2, 1, 2, 1], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2], [0, 2, 0, 2, 0], [2, 0, 2, 0, 2],
  ];
  const LOW = { 3: 2, 4: 5, 5: 10 };
  const HIGH = { 3: 8, 4: 20, 5: 40 };
  const PAYS = { a: LOW, k: LOW, q: LOW, j: LOW, jet: HIGH, docs: HIGH, hair: HIGH, wild: { 3: 10, 4: 30, 5: 75 } };
  const SCATTER_PAYS = { 3: 2, 4: 10, 5: 50 };
  const FS_BY_COUNT = { 3: 10, 4: 15, 5: 20 };
  const HIGH_TIER = new Set(['jet', 'docs', 'hair', 'wild']);
  const TIER_POPUP = { 3: 'bigWin', 4: 'megaWin', 5: 'epicWin' }; // app/services/popups.py
  const NAMES = { jet: 'Самолёт (Air Force Uni)', docs: 'Документы', hair: 'Причёска', a: 'A', k: 'K', q: 'Q', j: 'J', wild: 'Wild', scatter: 'Скаттер (бургер)' };
  const PLAIN = ['a', 'j', 'k', 'q', 'hair', 'docs', 'jet'];

  const bet = () => gameState.betSteps[gameState.betIndex] || 55000;
  const lineBet = () => bet() / LINES.length;
  const rnd = (list) => list[Math.floor(Math.random() * list.length)];
  const inBonus = () => document.getElementById('screen').dataset.mode === 'freespins';
  const field = (k, d) => (DevTools.value(k) == null || DevTools.value(k) === '' ? d : DevTools.value(k));
  const lineField = () => Math.min(11, Math.max(1, Number(field('line', 1)) || 1));
  const multField = () => { const m = Number(field('mult', 1)); return [2, 3, 5, 7, 9].includes(m) ? m : 1; };

  // Free-spins round of dev spins (the backend's own count isn't there).
  const fs = { total: 0 };

  // --- grid ------------------------------------------------------------------
  // cell = { code, mult } (mult > 1 only on wilds)
  const cell = (code, mult = 1) => ({ code, mult: code === 'wild' ? mult : 1 });
  function fillerGrid() {
    for (let t = 0; t < 300; t++) {
      const g = [0, 1, 2].map(() => Array.from({ length: 5 }, () => cell(rnd(PLAIN))));
      if (!evaluate(g).lineWins.length) return g;
    }
    return [0, 1, 2].map((r) => Array.from({ length: 5 }, (_, c) => cell(PLAIN[(r * 2 + c) % PLAIN.length])));
  }
  // Puts `code` on line `line` for reels 1..n and makes reel n+1 not extend it.
  function putLine(g, line, code, n, mult = 1) {
    const rows = LINES[line - 1];
    for (let c = 0; c < n; c++) g[rows[c]][c] = cell(code, mult);
    if (n < 5) {
      const r = rows[n];
      const avoid = new Set([code, 'wild', 'scatter']);
      if (avoid.has(g[r][n].code)) g[r][n] = cell(rnd(PLAIN.filter((x) => !avoid.has(x))));
    }
    return g;
  }
  // Re-roll stray wins the filler made by accident, keeping `keep` cells.
  function scrub(g, keepLines = []) {
    for (let t = 0; t < 200; t++) {
      const extra = evaluate(g).lineWins.filter((w) => !keepLines.includes(w.payline));
      if (!extra.length) return g;
      const w = extra[0];
      const p = w.positions[w.positions.length - 1];
      if (g[p.row][p.col].code !== 'wild' && g[p.row][p.col].code !== 'scatter') g[p.row][p.col] = cell(rnd(PLAIN));
      else break;
    }
    return g;
  }

  function parseGrid(text) {
    const rows = String(text).trim().split('/').map((r) => r.trim().split(/[\s,]+/).filter(Boolean));
    if (rows.length !== 3 || rows.some((r) => r.length !== 5)) throw new Error('нужно 3 строки по 5 символов через «/»');
    return rows.map((r) => r.map((t) => {
      const x = t.toLowerCase();
      const m = /^x([23579])$/.exec(x);
      if (m) return cell('wild', Number(m[1]));
      if (!PAYS[x] && x !== 'scatter') throw new Error(`неизвестный символ «${t}»`);
      return cell(x);
    }));
  }
  const gridToText = (g) => g.map((r) => r.map((c) => (c.code === 'wild' && c.mult > 1 ? `x${c.mult}` : c.code)).join(' ')).join(' / ');

  // --- evaluation, as the backend ---------------------------------------------
  function evaluate(g) {
    const lineWins = [];
    LINES.forEach((rows, i) => {
      const cells = rows.map((r, c) => ({ row: r, col: c, ...g[r][c] }));
      if (cells[0].code === 'scatter') return;
      // wild-only run from reel 1
      let w = 0;
      while (w < 5 && cells[w].code === 'wild') w++;
      const base = cells.find((c) => c.code !== 'wild');
      let n = 0;
      if (base && base.code !== 'scatter') while (n < 5 && (cells[n].code === base.code || cells[n].code === 'wild')) n++;
      const mult = (k) => cells.slice(0, k).reduce((m, c) => m * (c.code === 'wild' ? c.mult : 1), 1);
      const options = [];
      if (w >= 3) options.push({ code: 'wild', n: w, amount: PAYS.wild[w] * lineBet() * mult(w) });
      if (base && base.code !== 'scatter' && n >= 3) options.push({ code: base.code, n, amount: PAYS[base.code][n] * lineBet() * mult(n) });
      if (!options.length) return;
      const best = options.sort((a, b) => b.amount - a.amount)[0];
      lineWins.push({ payline: i + 1, symbol_code: best.code, count: best.n, positions: cells.slice(0, best.n).map(({ row, col }) => ({ row, col })), amount: Math.round(best.amount) });
    });
    const scat = [];
    g.forEach((r, row) => r.forEach((c, col) => { if (c.code === 'scatter') scat.push({ row, col }); }));
    const countWins = scat.length >= 3 ? [{ symbol_code: 'scatter', count: scat.length, positions: scat, amount: Math.round(SCATTER_PAYS[Math.min(5, scat.length)] * bet()) }] : [];
    return { lineWins, countWins, scatters: scat.length };
  }

  // --- play a grid ---------------------------------------------------------------
  function play(g, { bought = false } = {}) {
    const { lineWins, countWins, scatters } = evaluate(g);
    const cells = new Map();
    for (const w of [...lineWins, ...countWins]) for (const p of w.positions) cells.set(`${p.row}:${p.col}`, p);
    const total = [...lineWins, ...countWins].reduce((s, w) => s + w.amount, 0);
    const award = scatters >= 3 ? FS_BY_COUNT[Math.min(5, scatters)] : 0;
    let feature = null;
    let popup = null;
    const best = lineWins.filter((w) => HIGH_TIER.has(w.symbol_code)).reduce((b, w) => (!b || w.count > b.count ? w : b), null);
    if (best) popup = { type: TIER_POPUP[best.count], amount: total };
    const left = gameState.freeSpinsRemaining || 0;
    if (inBonus()) {
      fs.total += total;
      const next = Math.max(0, left - 1) + award;
      if (award) popup = { type: 'bonusSpinsWin', amount: award };
      if (next > 0) feature = { type: 'free_spins', spins_remaining: next };
      else popup = { type: 'bonusSpinsTotalWin', amount: fs.total };
    } else if (award || bought) {
      fs.total = 0;
      const spins = award || 10;
      feature = { type: 'free_spins', spins_remaining: spins };
      popup = { type: 'bonusSpinsWin', amount: spins };
    }
    if (bought) gameState.boughtBonus = true;
    if (!gameState.freeSpinsTrigger) gameState.freeSpinsTrigger = { trigger_symbol_code: 'scatter', trigger_count: 3 };
    gameState.balance += total - (bought ? bet() * 100 : 0);
    const multiplierWilds = [];
    g.forEach((r, row) => r.forEach((c, col) => { if (c.code === 'wild') multiplierWilds.push({ row, col, multiplier: String(c.mult) }); }));
    const status = `${gridToText(g)} → ${total ? `выигрыш ${total.toLocaleString('ru-RU')}` : 'без выигрыша'}${lineWins.length ? ` · линии ${lineWins.map((w) => `${w.payline}:${w.symbol_code}×${w.count}`).join(', ')}` : ''}${award ? ` · +${award} FS` : ''}`;
    DevTools.status(status, 'ok');
    return window.__devSpin({
      grid: g.map((r) => r.map((c) => c.code)),
      line_wins: lineWins,
      count_wins: countWins,
      winning_cells: [...cells.values()],
      multiplier_wilds: multiplierWilds,
      total_win: total,
      popup,
      feature,
    });
  }

  // --- building blocks -------------------------------------------------------
  function combo(code, n) {
    if (code === 'scatter') return scattersOn(n === 3 ? [0, 2, 4] : n === 4 ? [0, 1, 2, 4] : [0, 1, 2, 3, 4]);
    const line = lineField();
    const g = putLine(fillerGrid(), line, code, n, code === 'wild' ? multField() : 1);
    if (code !== 'wild' && multField() > 1) {
      // wild with the field's multiplier inside the line (reel 2)
      const r = LINES[line - 1][1];
      g[r][1] = cell('wild', multField());
    }
    return play(scrub(g, [line]));
  }
  function scattersOn(cols, g = fillerGrid()) {
    for (const col of cols) g[Math.floor(Math.random() * 3)][col] = cell('scatter');
    return play(scrub(g));
  }
  function withWilds(list, lineCode = null, n = 3) {
    let g = fillerGrid();
    if (lineCode) g = putLine(g, 1, lineCode, n);
    for (const [row, col, m] of list) g[row][col] = cell('wild', m);
    return play(scrub(g, lineCode ? [1] : []));
  }
  const toMode = async (fsOn) => {
    if (fsOn && !inBonus()) {
      gameState.freeSpinsRemaining = Number(field('spins', 10)) || 10;
      fs.total = 0;
    }
    if (!fsOn) gameState.freeSpinsRemaining = 0;
    await setFreeSpinsMode(fsOn, gameState.freeSpinsRemaining);
    if (fsOn && typeof updateFreeSpinsCounter === 'function') updateFreeSpinsCounter(gameState.freeSpinsRemaining);
  };
  async function toModeTo(mode, transition, spins = 10) {
    if (mode === 'freespins') {
      gameState.freeSpinsRemaining = spins;
      fs.total = 0;
      if (transition) await setFreeSpinsMode(true, spins);
      else if (!inBonus()) { applyModeScreen('freespins'); Sound.playMusic('bonus'); }
      updateFreeSpinsCounter(spins);
    } else {
      gameState.freeSpinsRemaining = 0;
      gameState.boughtBonus = false;
      if (transition) await setFreeSpinsMode(false);
      else if (inBonus()) { applyModeScreen('base'); Sound.playMusic('base'); }
    }
  }
  const amount = () => Number(field('amount', 1234500)) || 0;
  const spinsN = () => Number(field('spins', 10)) || 10;
  const grid = () => cellInfos.filter(Boolean);

  // The shared «Проверка» (js/dev-scenarios.js): its own scenarios run through
  // the same __devSpin and the trace of js/slot-flow.js is checked against the
  // shared rules. DevScenarios mounts a DEV panel of its own — keep ours (the
  // line / xN / own-grid combinations) and only take its runChecks.
  const realMount = DevTools.mount;
  DevTools.mount = () => {};
  const shared = window.DevScenarios ? DevScenarios.mount({
    title: 'DEV · Great Uniqorn',
    symbols: [
      { code: 'jet', name: NAMES.jet, img: symbolSrc('jet'), pays: HIGH, high: true },
      { code: 'docs', name: NAMES.docs, img: symbolSrc('docs'), pays: HIGH, high: true },
      { code: 'hair', name: NAMES.hair, img: symbolSrc('hair'), pays: HIGH, high: true },
      { code: 'a', name: 'A', img: symbolSrc('a'), pays: LOW },
      { code: 'k', name: 'K', img: symbolSrc('k'), pays: LOW },
      { code: 'q', name: 'Q', img: symbolSrc('q'), pays: LOW },
      { code: 'j', name: 'J', img: symbolSrc('j'), pays: LOW },
    ],
    wild: { code: 'wild', name: 'Wild', img: symbolSrc('wild'), pays: PAYS.wild, expands: false },
    scatter: { code: 'scatter', name: NAMES.scatter, img: symbolSrc('scatter'), pays: SCATTER_PAYS, award: FS_BY_COUNT, count: 3 },
    fillers: PLAIN,
    bet,
    spin: (d) => { if (!gameState.freeSpinsTrigger) gameState.freeSpinsTrigger = { trigger_symbol_code: 'scatter', trigger_count: 3 }; return window.__devSpin(d); },
    mode: () => (inBonus() ? 'freespins' : 'base'),
    toMode: (mode, transition, spins = 10) => toModeTo(mode, transition, spins),
    popups: { tier: (t, a) => playPopup(t, a), bonusSpinsWin: (n) => playPopup('bonusSpinsWin', n), total: (a) => playPopup('bonusSpinsTotalWin', a), small: (a) => showInlineWinAmount(a) },
    isBusy: () => spineScreenOpen || dimActiveCount > 0,
    // the bonus screen (TAP TO START) waits for a tap inside the spin
    autoTap: () => { const el = document.getElementById('featureScreen'); if (el && !el.hidden) el.click(); },
  }) : null;
  DevTools.mount = realMount;

  const symbolRows = ['jet', 'docs', 'hair', 'a', 'k', 'q', 'j', 'wild', 'scatter']
    .map((code) => ({ key: code, label: NAMES[code], img: symbolSrc(code) }));

  DevTools.mount({
    title: 'DEV · Great Uniqorn',
    fields: [
      { key: 'line', label: 'Линия (1–11)', value: 1 },
      { key: 'mult', label: 'Множитель вайлда (1/2/3/5/7/9)', value: 1 },
      { key: 'grid', label: 'Своя сетка', type: 'text', value: 'jet jet x3 jet k / q a docs j hair / k scatter q a scatter' },
      { key: 'amount', label: 'Сумма попапа', value: 1234500 },
      { key: 'spins', label: 'Фриспинов', value: 10 },
    ],
    tabs: [
      {
        title: 'Комбинации',
        sections: [
          {
            title: 'Символ ×3 / ×4 / ×5 на линии',
            note: 'Настоящий спин с подставленным результатом на линии из поля «Линия». «Множитель вайлда» > 1 — у вайлда в комбинации (или вайлд на 2-м барабане у обычного символа) свой xN. Скаттеры — в любом месте.',
            matrix: { rows: symbolRows, cols: [3, 4, 5], run: (row, n) => combo(row.key, n) },
          },
          { title: 'Своя сетка', note: '3 строки по 5 через «/»: a j k q hair docs jet wild scatter; x2 x3 x5 x7 x9 — вайлд с множителем. Выигрыш считается как на сервере.', items: [
            { label: '▶ Крутить свою сетку', run: () => play(parseGrid(field('grid', ''))) },
            { label: 'Записать текущую сетку в поле', run: () => {
              const g = [0, 1, 2].map((r) => [0, 1, 2, 3, 4].map((c) => { const i = cellInfos[r * 5 + c]; return i ? (i.symbol === 'wild' && i.mult > 1 ? `x${i.mult}` : i.symbol) : 'k'; }).join(' ')).join(' / ');
              const input = [...document.querySelectorAll('.dt-root input')].find((el) => el.value === String(field('grid', '')));
              if (input) { input.value = g; input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); }
              DevTools.status(g, 'ok');
            } },
          ] },
          { title: 'Несколько линий', items: [
            { label: '2 линии (A×3 + Самолёт×4)', run: () => { const g = putLine(putLine(fillerGrid(), 2, 'a', 3), 3, 'jet', 4); return play(scrub(g, [2, 3])); } },
            { label: '3 линии (верх + середина + низ)', run: () => { const g = putLine(putLine(putLine(fillerGrid(), 1, 'k', 3), 2, 'q', 4), 3, 'docs', 3); return play(scrub(g, [1, 2, 3])); } },
            { label: 'V-линия + вайлд x2 в центре', run: () => { const g = putLine(fillerGrid(), 4, 'hair', 5); g[2][2] = cell('wild', 2); return play(scrub(g, [4])); } },
          ] },
        ],
      },
      {
        title: 'События',
        sections: [
          { title: 'Антисипация', note: '2 бургера на первых барабанах → последний тянет.', items: [
            { label: '✓ Удачная (3-й бургер на 5-м)', run: () => scattersOn([0, 2, 4]) },
            { label: '✗ Неудачная (мимо)', run: () => scattersOn([0, 2]) },
            { label: '✗ Неудачная (2-й и 4-й)', run: () => scattersOn([1, 3]) },
          ] },
          { title: 'Скаттеры (бургеры)', items: [
            { label: '1 бургер', run: () => scattersOn([2]) },
            { label: '2 бургера', run: () => scattersOn([3, 4]) },
            { label: '3 → 10 фриспинов', run: () => scattersOn([0, 2, 4]) },
            { label: '4 → 15 фриспинов', run: () => scattersOn([0, 1, 2, 4]) },
            { label: '5 → 20 фриспинов', run: () => scattersOn([0, 1, 2, 3, 4]) },
          ] },
          { title: 'Вайлд → множитель', note: 'Вайлд падает простым и превращается в xN после остановки барабана; линия умножается на все xN вайлдов в ней.', items: [
            { label: 'Вайлд без выигрыша (остался WILD)', run: () => withWilds([[0, 2, 1]]) },
            { label: 'Вайлд x5 без выигрыша', run: () => withWilds([[0, 2, 5]]) },
            { label: 'Вайлд x3 в линии K×3', run: () => withWilds([[1, 1, 3]], 'k', 3) },
            { label: 'x2 и x7 в одной линии (×14)', run: () => withWilds([[1, 1, 2], [1, 3, 7]], 'docs', 5) },
            { label: '3 вайлда на линии (x2 x3 x5)', run: () => play(scrub((() => { const g = fillerGrid(); g[1][0] = cell('wild', 2); g[1][1] = cell('wild', 3); g[1][2] = cell('wild', 5); const r = LINES[0][3]; if (g[r][3].code === 'wild') g[r][3] = cell('k'); return g; })(), [1])) },
            { label: '5 вайлдов на линии (все x9)', run: () => { const g = fillerGrid(); for (let c = 0; c < 5; c++) g[1][c] = cell('wild', 9); return play(g); } },
          ] },
          { title: 'Большие выигрыши (попапы)', items: [
            { label: 'BIG WIN (Самолёт ×3)', run: () => { const g = putLine(fillerGrid(), 1, 'jet', 3); return play(scrub(g, [1])); } },
            { label: 'MEGA WIN (Причёска ×4)', run: () => { const g = putLine(fillerGrid(), 1, 'hair', 4); return play(scrub(g, [1])); } },
            { label: 'EPIC WIN (Документы ×5)', run: () => { const g = putLine(fillerGrid(), 1, 'docs', 5); return play(scrub(g, [1])); } },
            { label: 'Малый выигрыш (A ×3, без попапа)', run: () => { const g = putLine(fillerGrid(), 1, 'a', 3); return play(scrub(g, [1])); } },
          ] },
          { title: 'Фриспины', note: 'Спины ниже работают и в бонусе: счётчик уменьшается, последний спин закрывает раунд попапом TOTAL WIN.', items: [
            { label: 'Покупка бонуса → 10 FS', run: () => { if (inBonus()) return null; return play(fillerGrid(), { bought: true }); } },
            { label: 'Спин без выигрыша', run: () => play(fillerGrid()) },
            { label: 'Спин с выигрышем (вайлд x3)', run: () => withWilds([[1, 1, 3]], 'q', 4) },
            { label: 'Ретриггер (3 бургера)', run: () => scattersOn([0, 2, 4]) },
            { label: 'Последний спин → TOTAL', run: async () => { if (!inBonus()) await toMode(true); gameState.freeSpinsRemaining = 1; return withWilds([[1, 2, 5]], 'jet', 3); } },
          ] },
          { title: 'Пустые', items: [
            { label: 'Пустой спин', run: () => play(fillerGrid()) },
          ] },
        ],
      },
      {
        title: 'Проверка',
        sections: [
          { title: 'Порядок событий по правилам (js/slot-flow.js)', note: 'Прогоняет 6 сценариев и сверяет журнал событий с общими правилами. Около минуты; экран не трогать.', items: [
            { label: '▶ Прогнать все проверки', run: () => (shared ? shared.runChecks() : Promise.reject(new Error('dev-scenarios.js не подключён'))) },
          ] },
        ],
      },
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим', items: [
            { label: 'База', run: () => toMode(false) },
            { label: 'Фриспины (с входом в бонус)', run: () => toMode(true) },
          ] },
          { title: 'Экраны Spine', items: [
            { label: 'Feature screen', run: () => showFeatureScreen() },
            { label: 'Bonus screen (N спинов)', run: () => showBonusScreen(spinsN()) },
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
          { title: 'Фриспины', items: [
            { label: 'FREESPINS WIN (N спинов)', run: () => playPopup('bonusSpinsWin', spinsN()) },
            { label: 'BONUS SPINS TOTAL WIN', run: () => playPopup('bonusSpinsTotalWin', amount()) },
          ] },
        ],
      },
      {
        title: 'Анимации',
        sections: [
          { title: 'Страницы анимаций', note: 'Открываются в новой вкладке.', items: [
            { label: 'Все анимации игры →', run: () => { window.open('great-uniqorn-anims.html', '_blank'); } },
            { label: 'Приёмка Spine по ТЗ →', run: () => { window.open('great-uniqorn-spine-check.html', '_blank'); } },
          ] },
          { title: 'Spine на сетке', note: 'Клик по символу в сетке — его win; по WILD — превращение в множитель.', items: [
            { label: 'Все символы: win', run: () => Promise.all(grid().map((i) => playWinAnimationOnce(i))) },
            { label: 'Скаттеры: landing', run: () => grid().filter((i) => i.symbol === 'scatter').forEach((i) => mountSymbolSpine(i, 'landing')) },
            { label: 'Остановить анимации', run: () => { teardownCellInstances(); syncPersistentSpines(); } },
          ] },
          { title: 'WILD → множитель (все вайлды на сетке)', items: WILD_MULTIPLIERS.map((m) => ({
            label: `x${m}`,
            run: () => Promise.all(grid().filter((i) => i.symbol === 'wild').map((i) => setCellSymbol(i, 'wild').then(() => revealWildMultiplier(i, m)))),
          })) },
        ],
      },
    ],
  });
})();
