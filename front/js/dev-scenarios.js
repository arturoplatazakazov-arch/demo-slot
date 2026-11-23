// DevScenarios — builds the DEV panel (js/dev-tools.js) for any 5x3 line game
// from a short description of its symbols, and adds a "Проверка" tab that
// runs the scenarios and checks the trace of js/slot-flow.js against the
// shared rules (see the header of slot-flow.js).
//
// Every combination / scenario is FRONT-ONLY: a made-up spin response shaped
// like the backend's, played through the game's real spin pipeline
// (cfg.spin, usually window.__devSpin from app.js).
//
//   DevScenarios.mount({
//     title: 'DEV · Game', symbols: [{ code, name, img, pays: {3,4,5}, high }],
//     wild: { code: 'wild', pays: {...} }, scatter: { code: 'scatter', pays: {...}, award: {3: 10} },
//     fillers: [...codes without specials], bet: () => n, spin: (data) => window.__devSpin(data),
//     mode: () => 'base' | 'freespins', toMode: (mode, withTransition) => Promise,
//     popups: { tier: (type, amount), bonusSpinsWin: (n), total: (amount), small: (amount), buy: [{ label, run }] },
//     screens: [{ label, run }], isBusy: () => bool, autoTap: () => void,
//     extra: { 'Сценарии': [sections], 'Фичи': [sections] }, result: (draft) => draft,
//   });
(function () {
  const LINES_11 = [
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2], [1, 0, 1, 0, 1],
    [1, 2, 1, 2, 1], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2], [0, 2, 0, 2, 0], [2, 0, 2, 0, 2],
  ];
  const TIER_POPUP = { 3: 'bigWin', 4: 'megaWin', 5: 'epicWin' };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const rnd = (list) => list[Math.floor(Math.random() * list.length)];

  function mount(cfg) {
    const COLS = cfg.cols || 5;
    const ROWS = cfg.rows || 3;
    const LINES = cfg.lines || LINES_11;
    const wildCode = cfg.wild ? cfg.wild.code : null;
    const sc = cfg.scatter || null;
    const pays = {};
    for (const s of cfg.symbols) pays[s.code] = s.pays;
    if (cfg.wild) pays[wildCode] = cfg.wild.pays;
    const high = new Set(cfg.symbols.filter((s) => s.high).map((s) => s.code));
    if (wildCode) high.add(wildCode);
    const fillers = cfg.fillers;
    const bet = () => cfg.bet();
    const lineBet = () => bet() / LINES.length;
    const inBonus = () => cfg.mode() === 'freespins';
    const award = (n) => (sc && sc.award && (sc.award[n] || sc.award[3])) || 10;
    const fs = { left: 0, total: 0 };

    // --- grid / win builders ---------------------------------------------------
    function fillerGrid() {
      for (let k = 0; k < 300; k++) {
        const g = Array.from({ length: ROWS }, () => Array.from({ length: COLS }, () => rnd(fillers)));
        if (!LINES.some((l) => g[l[0]][0] === g[l[1]][1] && g[l[1]][1] === g[l[2]][2])) return g;
      }
      return Array.from({ length: ROWS }, (_, r) => Array.from({ length: COLS }, (_, c) => fillers[(r * COLS + c) % fillers.length]));
    }
    function lineWin(g, line, code, n, payAs = code) {
      const positions = [];
      for (let col = 0; col < n; col++) {
        const row = LINES[line - 1][col];
        if (g[row][col] !== wildCode) g[row][col] = code;
        positions.push({ row, col });
      }
      if (n < COLS) {
        const r = LINES[line - 1][n];
        while (g[r][n] === code || g[r][n] === wildCode) g[r][n] = rnd(fillers.filter((c) => c !== code));
      }
      return { payline: line, symbol_code: payAs, count: n, positions, amount: Math.round((pays[payAs][n] || 0) * lineBet()) };
    }

    function spin({ grid, lineWins = [], countWins = [], wildEvents = [], triggers = 0, multiplier = 1, extra = {} }) {
      const cells = new Map();
      for (const w of [...lineWins, ...countWins]) for (const p of w.positions) cells.set(`${p.row}:${p.col}`, p);
      const total = Math.round(lineWins.reduce((s, w) => s + w.amount, 0) * multiplier + countWins.reduce((s, w) => s + w.amount, 0));
      let feature = null;
      let popup = null;
      const best = lineWins.reduce((b, w) => (high.has(w.symbol_code) && w.count > (b ? b.count : 0) ? w : b), null);
      if (best) popup = { type: TIER_POPUP[best.count], amount: total };
      const n = countWins.length ? countWins[0].count : 0;
      if (inBonus()) {
        fs.total += total;
        fs.left = Math.max(0, fs.left - 1) + (triggers ? award(n) : 0);
        if (triggers) popup = { type: 'bonusSpinsWin', amount: award(n) };
        if (fs.left > 0) feature = { type: 'free_spins', spins_remaining: fs.left };
        else popup = { type: 'bonusSpinsTotalWin', amount: fs.total };
      } else if (triggers) {
        fs.left = award(n);
        fs.total = 0;
        feature = { type: 'free_spins', spins_remaining: fs.left };
        popup = { type: 'bonusSpinsWin', amount: fs.left };
      }
      let draft = {
        grid, line_wins: lineWins, count_wins: countWins, winning_cells: [...cells.values()],
        wild_events: wildEvents, total_win: total, popup, feature, ...extra,
      };
      if (cfg.result) draft = cfg.result(draft) || draft;
      return cfg.spin(draft);
    }

    function combo(code, n) {
      const g = fillerGrid();
      if (sc && code === sc.code) return scatters(n === 3 ? [0, 2, 4] : Array.from({ length: n }, (_, i) => i), g);
      const w = lineWin(g, 1, code, n);
      const wildEvents = code === wildCode && cfg.wild.expands ? w.positions.map((p) => ({ reel: p.col, event: 'expanded' })) : [];
      return spin({ grid: g, lineWins: [w], wildEvents });
    }

    function scatters(cols, g = fillerGrid()) {
      const positions = cols.map((col) => ({ row: Math.floor(Math.random() * ROWS), col }));
      for (const p of positions) g[p.row][p.col] = sc.code;
      const n = positions.length;
      const trig = n >= (sc.count || 3);
      const countWins = trig ? [{ symbol_code: sc.code, count: n, positions, amount: Math.round(((sc.pays || {})[Math.min(5, n)] || 0) * bet()) }] : [];
      return spin({ grid: g, countWins, triggers: trig ? 1 : 0 });
    }

    const lows = cfg.symbols.filter((s) => !s.high).map((s) => s.code);
    const highs = cfg.symbols.filter((s) => s.high).map((s) => s.code);
    const twoLines = () => { const g = fillerGrid(); return spin({ grid: g, lineWins: [lineWin(g, 1, lows[0], 3), lineWin(g, 2, highs[0], 4)] }); };
    const wildInLine = () => {
      const g = fillerGrid();
      g[1][2] = wildCode;
      return spin({ grid: g, lineWins: [lineWin(g, 1, lows[1] || lows[0], 4)], wildEvents: cfg.wild.expands ? [{ reel: 2, event: 'expanded' }] : [] });
    };
    const startBonus = async (transition = false) => {
      fs.left = 10; fs.total = 0;
      await cfg.toMode('freespins', transition, fs.left);
    };

    const amount = () => Number(DevTools.value('amount')) || 0;
    const spinsField = () => Number(DevTools.value('spins')) || 10;
    const symbolRows = [...cfg.symbols, ...(cfg.wild ? [{ code: wildCode, name: cfg.wild.name || 'Wild', img: cfg.wild.img }] : []),
      ...(sc ? [{ code: sc.code, name: sc.name || 'Scatter', img: sc.img }] : [])].map((s) => ({ key: s.code, label: s.name, img: s.img }));

    const P = cfg.popups || {};
    const tabs = [
      {
        title: 'Экраны',
        sections: [
          { title: 'Режим сразу', items: [
            { label: 'База', run: () => cfg.toMode('base', false) },
            { label: 'Бонус (фриспины)', run: () => startBonus(false) },
          ] },
          { title: 'Режим с переходом', items: [
            { label: 'База → Бонус', run: () => startBonus(true) },
            { label: 'Бонус → База', run: () => cfg.toMode('base', true) },
          ] },
          ...(cfg.screens && cfg.screens.length ? [{ title: 'Экраны игры', items: cfg.screens }] : []),
          { title: 'Барабаны', items: [{ label: 'Пустой спин', run: () => spin({ grid: fillerGrid() }) }] },
        ],
      },
      {
        title: 'Комбинации',
        sections: [
          { title: 'Символ на центральной линии', note: 'Настоящий спин с подставленным результатом: стопы, выигрыш, попап, звуки.',
            matrix: { rows: symbolRows, cols: [3, 4, 5], run: (row, n) => combo(row.key, n) } },
          { title: 'Несколько линий', items: [
            { label: '2 линии (дешёвая ×3 + дорогая ×4)', run: twoLines },
            ...(wildCode ? [{ label: 'Вайлд в линии ×4', run: wildInLine }] : []),
          ] },
        ],
      },
      {
        title: 'Сценарии',
        sections: [
          ...(sc ? [
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
              { label: 'Спин без выигрыша', run: () => spin({ grid: fillerGrid() }) },
              { label: 'Спин с выигрышем', run: () => combo(highs[0], 3) },
              { label: 'Ретриггер (3 скаттера)', run: () => scatters([0, 2, 4]) },
              { label: 'Последний спин → TOTAL', run: () => { if (!inBonus()) return startBonus(false); fs.left = 1; return combo(lows[0], 3); } },
            ] },
          ] : []),
          ...(wildCode && cfg.wild.expands ? [{ title: 'Вайлд', items: [
            { label: 'Вайлд раскрылся, без выигрыша', run: () => { const g = fillerGrid(); g[0][2] = wildCode; return spin({ grid: g, wildEvents: [{ reel: 2, event: 'expanded' }] }); } },
            { label: '2 вайлда', run: () => { const g = fillerGrid(); g[0][1] = wildCode; g[2][3] = wildCode; return spin({ grid: g, wildEvents: [{ reel: 1, event: 'expanded' }, { reel: 3, event: 'expanded' }] }); } },
          ] }] : []),
          ...((cfg.extra && cfg.extra['Сценарии']) || []),
        ],
      },
      {
        title: 'Попапы',
        sections: [
          { title: 'Выигрыш (сумма из поля)', items: [
            ...(P.small ? [{ label: 'Малый (без попапа)', run: () => { Sound.playSfx('smallWin'); P.small(amount()); } }] : []),
            { label: 'BIG WIN', run: () => P.tier('bigWin', amount()) },
            { label: 'MEGA WIN', run: () => P.tier('megaWin', amount()) },
            { label: 'EPIC WIN', run: () => P.tier('epicWin', amount()) },
          ] },
          { title: 'Бонус', items: [
            { label: 'YOU WON N FREE SPINS', run: () => P.bonusSpinsWin(spinsField()) },
            { label: 'TOTAL WIN', run: () => P.total(amount()) },
          ] },
          ...(P.buy && P.buy.length ? [{ title: 'Покупка', items: P.buy }] : []),
        ],
      },
      ...((cfg.extra && cfg.extra['Фичи']) ? [{ title: 'Фичи', sections: cfg.extra['Фичи'] }] : []),
      { title: 'Проверка', sections: [checkSection()] },
    ];

    // --- "Проверка": run scenarios, check the SlotFlow trace ---------------------
    function checkSection() {
      return {
        title: 'Порядок событий по правилам',
        note: 'Прогоняет сценарии и сверяет журнал с правилами из slot-flow.js. Займёт около минуты; экран не трогать.',
        items: [{ label: '▶ Прогнать все проверки', run: () => runChecks() }],
      };
    }

    function collect() {
      const ev = [];
      const t0 = performance.now();
      const offA = SlotFlow.onTrace((e) => ev.push({ k: e.type, kind: e.kind, t: e.t - t0 }));
      const offB = window.Sound && Sound.lab ? Sound.lab.onEvent((e) => ev.push({ k: `sfx:${e.key}`, t: e.t - t0 })) : () => {};
      return { ev, stop() { offA(); offB(); } };
    }
    const busy = () => (cfg.isBusy ? cfg.isBusy() : false) || (window.gameState && gameState.isSpinning);
    async function settle(maxMs = 30000) {
      const t = performance.now();
      await wait(400);
      while (performance.now() - t < maxMs) {
        if (!busy()) { await wait(500); if (!busy()) return true; }
        await wait(250);
      }
      return false;
    }
    const idx = (ev, k, kind, from = 0) => ev.findIndex((e, i) => i >= from && e.k === k && (kind == null || e.kind === kind));
    const before = (ev, a, b) => { const i = ev.findIndex(a), j = ev.findIndex(b); return i >= 0 && j >= 0 && i < j; };
    const is = (k, kind) => (e) => e.k === k && (kind == null || e.kind === kind);

    const CHECKS = [
      { name: 'Дорогая ×4 → MEGA только после полного цикла и мелодии', run: () => combo(highs[0], 4), rules: (ev) => [
        ['цикл выигрыша завершён', idx(ev, 'wins:cycleDone') >= 0],
        ['мелодия символа прозвучала до попапа', before(ev, is(`sfx:symWin_${highs[0]}`), is('popup:open', 'megaWin'))],
        ['MEGA открылся после цикла', before(ev, is('wins:cycleDone'), is('popup:open', 'megaWin'))],
        ['под попапом слой выигрыша скрыт', idx(ev, 'layer:hide') > idx(ev, 'popup:open', 'megaWin')],
      ] },
      { name: '2 линии → попап после того, как сыграли обе', run: twoLines, rules: (ev) => [
        ['каждая линия сыграла своим звуком', ev.filter(is('sfx:winLine')).length >= 2],
        ['попап после второй линии', (() => { const ls = ev.map((e, i) => (e.k === 'sfx:winLine' ? i : -1)).filter((i) => i >= 0); const p = idx(ev, 'popup:open', 'megaWin'); return ls.length >= 2 && p > ls[1]; })()],
      ] },
      ...(sc ? [
        { name: 'Антисипация мимо → звук неудачи, бонуса нет', run: () => scatters([0, 2]), rules: (ev) => [
          ['петля антисипации стартовала', idx(ev, 'anticipation:start') >= 0],
          ['исход — неудача', idx(ev, 'anticipation:miss') >= 0 && idx(ev, 'anticipation:hit') < 0],
          ['бонус не начался', idx(ev, 'bonus:blackout') < 0],
        ] },
        { name: 'Антисипация → 3 скаттера → вход в бонус по порядку', run: () => scatters([0, 2, 4]), rules: (ev) => {
          const order = ['wins:cycleDone', 'popup:open', 'bonus:blackout', 'bonus:music', 'bonus:enter'];
          const at = order.map((k) => idx(ev, k, k === 'popup:open' ? 'bonusSpinsWin' : null));
          const pv = idx(ev, 'bonus:preview');
          return [
            ['исход антисипации — удача', idx(ev, 'anticipation:hit') >= 0],
            ['мелодия скаттера до попапа', before(ev, is(`sfx:symWin_${sc.code}`), is('popup:open', 'bonusSpinsWin'))],
            ['цикл скаттеров → YOU WON → затемнение → бонусная музыка → бонус', at.every((v, i) => v >= 0 && (i === 0 || v > at[i - 1]))],
            ['превью бонуса после старта бонусной музыки', pv < 0 || pv > at[3]],
          ];
        } },
        { name: 'Ретриггер в бонусе → YOU WON после цикла скаттеров', pre: () => startBonus(false), run: () => scatters([0, 2, 4]), rules: (ev) => [
          ['YOU WON после цикла', before(ev, is('wins:cycleDone'), is('popup:open', 'bonusSpinsWin'))],
        ] },
        { name: 'Последний фриспин → выход в базу → TOTAL WIN', pre: async () => { await startBonus(false); fs.left = 1; }, run: () => combo(lows[0], 3), rules: (ev) => [
          ['выход из бонуса', idx(ev, 'bonus:exit') >= 0],
          ['TOTAL после выхода', before(ev, is('bonus:exit'), is('popup:open', 'bonusSpinsTotalWin'))],
        ] },
      ] : []),
    ];

    async function runChecks() {
      const out = document.querySelector('.dt-check-out') || (() => {
        const el = document.createElement('div');
        el.className = 'dt-check-out';
        document.querySelector('.dt-body').appendChild(el);
        return el;
      })();
      out.innerHTML = '';
      const results = [];
      // the bonus preview waits for a tap INSIDE the spin — tap it all along
      const tapper = cfg.autoTap ? setInterval(() => cfg.autoTap(), 400) : null;
      try {
      for (const c of CHECKS) {
        const row = document.createElement('div');
        row.className = 'dt-check';
        row.textContent = `… ${c.name}`;
        out.appendChild(row);
        await cfg.toMode('base', false);
        await settle();
        if (c.pre) { await c.pre(); await settle(); }
        const rec = collect();
        await c.run();
        const ok = await settle();
        rec.stop();
        const rules = c.rules(rec.ev);
        if (!ok) rules.push(['сценарий закончился вовремя', false]);
        const pass = rules.every((r) => r[1]);
        results.push({ name: c.name, pass, rules, trace: rec.ev.map((e) => `${(e.t / 1000).toFixed(2)} ${e.k}${e.kind ? `(${e.kind})` : ''}`) });
        row.className = `dt-check ${pass ? 'is-pass' : 'is-fail'}`;
        row.innerHTML = `<b>${pass ? '✓' : '✗'} ${c.name}</b>` + rules.map(([t, v]) => `<div class="dt-check__rule ${v ? '' : 'is-fail'}">${v ? '✓' : '✗'} ${t}</div>`).join('');
      }
      } finally {
        if (tapper) clearInterval(tapper);
      }
      await cfg.toMode('base', false);
      window.__flowCheck = results;
      const failed = results.filter((r) => !r.pass).length;
      DevTools.status(failed ? `✗ проверок не прошло: ${failed} из ${results.length}` : `✓ все ${results.length} проверок прошли`, failed ? 'err' : 'ok');
      return results;
    }

    DevTools.mount({
      title: cfg.title,
      fields: [{ key: 'amount', label: 'Сумма', value: 1234500 }, { key: 'spins', label: 'Фриспинов', value: 10 }],
      tabs,
    });

    const api = { fs, spin, fillerGrid, lineWin, combo, scatters, runChecks, inBonus, lineBet, bet };
    window.__dev = api;
    return api;
  }

  window.DevScenarios = { mount, LINES_11 };
})();
