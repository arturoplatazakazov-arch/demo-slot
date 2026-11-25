// Gangsta Casino — DEV panel: the shared scenarios (js/dev-scenarios.js) plus
// this game's own bits — multiplier chips, the plate, the big wild per reel,
// the Spine feature / bonus screens. Pays follow app/seed/gangsta_casino.py.
(function () {
  const COMMON = { 3: 4.2, 4: 10.5, 5: 21 };
  const RARE = { 3: 21, 4: 52.5, 5: 105 };
  const sym = (code, name, pays, high) => ({ code, name, pays, high, img: symbolSrc(code) });

  const dev = DevScenarios.mount({
    title: 'DEV · Gangsta Casino',
    symbols: [
      sym('rare_purple', 'Queen', RARE, true), sym('rare_yellow', 'Diva', RARE, true),
      sym('rare_blue', 'Boss', RARE, true), sym('rare_green', 'Hustler', RARE, true),
      sym('common_2', 'Golden Uzi', COMMON, false), sym('common_4', 'Pink Glock', COMMON, false),
      sym('common_3', 'Knuckles', COMMON, false), sym('common_1', 'Bat', COMMON, false),
    ],
    wild: { code: 'wild', name: 'Wild', img: symbolSrc('wild'), pays: { 3: 42, 4: 126, 5: 315 }, expands: true },
    scatter: { code: 'scatter', name: 'Scatter', img: symbolSrc('scatter'), pays: { 3: 2, 4: 10, 5: 50 }, award: { 3: 10 }, count: 3 },
    fillers: FILLER_CODES,
    bet: () => gameState.betSteps[gameState.betIndex],
    spin: (data) => {
      if (!gameState.freeSpinsTrigger) gameState.freeSpinsTrigger = { trigger_symbol_code: 'scatter', trigger_count: 3 };
      return window.__devSpin(data);
    },
    mode: () => currentMode(),
    toMode: (mode, transition, spins = 10) => {
      if (currentMode() === mode) return Promise.resolve();
      if (transition) {
        if (mode === 'freespins') setFreeSpinsCounter(spins);
        return setFreeSpinsMode(mode === 'freespins', spins);
      }
      applyModeScreen(mode);
      Sound.playMusic(mode === 'freespins' ? 'bonus' : 'base');
      if (mode === 'freespins') setFreeSpinsCounter(spins);
      return Promise.resolve();
    },
    popups: {
      small: (a) => showInlineWinAmount(a),
      tier: (type, a) => playPopup(type, a),
      bonusSpinsWin: (n) => playPopup('bonusSpinsWin', n),
      total: (a) => playPopup('bonusSpinsTotalWin', a),
      buy: [
        { label: 'Диалог покупки', run: () => openBuyDialog(gameState.betSteps[gameState.betIndex] * BUY_COST_MULTIPLIER) },
        { label: 'Не хватает баланса', run: () => openBuyDialog(gameState.betSteps[gameState.betIndex] * BUY_COST_MULTIPLIER, { affordable: false }) },
      ],
    },
    screens: [
      { label: 'Feature screen', run: () => showFeatureScreen() },
      { label: 'Bonus screen', run: () => showBonusScreen(Number(DevTools.value('spins')) || 10) },
      { label: 'Барабаны без остановки', run: () => startReelLoop() },
      { label: 'Остановить, сетка макета', run: () => { stopReelLoop(); applyGrid(SYMBOL_LAYOUT); } },
    ],
    isBusy: () => document.body.classList.contains('is-spine-popup') || document.body.classList.contains('is-feature-screen')
      || !document.getElementById('gpop').hidden || document.getElementById('screenDim').classList.contains('is-active'),
    // the checker taps the bonus preview ("TAP TO START") when it is up
    autoTap: () => { const fs = document.getElementById('featureScreen'); if (fs && !fs.hidden && fs.classList.contains('is-open')) fs.click(); },
    extra: {
      'Сценарии': [{ title: 'Множители', items: [
        { label: 'x3 + x5 с выигрышем', run: () => multiplierSpin([3, 5]) },
        { label: 'x9 с выигрышем', run: () => multiplierSpin([9]) },
        { label: 'x2 без выигрыша', run: () => multiplierSpin([2], false) },
        { label: 'x2 + x3 + x7', run: () => multiplierSpin([2, 3, 7]) },
      ] }],
      'Фичи': [
        { title: 'Большой вайлд (превью, без спина)', items: [0, 1, 2, 3, 4].map((col) => ({ label: `Барабан ${col + 1}`, run: () => previewBigWild(col, true) })) },
        { title: 'Множитель', items: [
          { label: 'Демо множителей', run: () => demoMultipliers() },
          { label: 'Плашка +x5', run: () => setMultiplierPlate(5, { lit: true, bump: true }) },
          { label: 'Плашка сброс', run: () => resetMultiplierPlate() },
        ] },
        { title: 'Счётчик фриспинов', items: [
          { label: '−1', run: () => { dev.fs.left = Math.max(0, dev.fs.left - 1); setFreeSpinsCounter(dev.fs.left); } },
          { label: '+10', run: () => { dev.fs.left += 10; setFreeSpinsCounter(dev.fs.left); } },
        ] },
      ],
    },
  });

  // Multiplier chips (`wof`): line win x the spin's sum, or the round total in free spins.
  let roundMult = 1;
  function multiplierSpin(values, win = true) {
    const g = dev.fillerGrid();
    const lineWins = win ? [dev.lineWin(g, 1, 'rare_blue', 3)] : [];
    const spots = [{ row: 0, col: 3 }, { row: 2, col: 4 }, { row: 0, col: 1 }];
    const positions = values.map((value, i) => ({ ...spots[i], value }));
    for (const p of positions) g[p.row][p.col] = 'wof';
    const sum = values.reduce((a, b) => a + b, 0);
    let round = null;
    if (dev.inBonus()) { roundMult += sum; round = roundMult; } else roundMult = 1;
    const coin_multiplier = { positions, applied: win, multiplier_sum: sum, round_multiplier: round };
    return dev.spin({ grid: g, lineWins, multiplier: win ? (round || sum) : 1, extra: { coin_multiplier } });
  }
})();
