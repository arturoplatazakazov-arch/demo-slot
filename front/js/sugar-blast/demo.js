// Demo panel for the Sugar Blast art variants (forked from js/savannah-kings/demo.js) (like Volt Coins' DEV panel,
// but shown on the deployed pages too): replay the BIG / MEGA / EPIC WIN
// popups and the four jackpot awards, one at a time or all in a row.
// Amounts are for show only: wins scale with the current bet, jackpots
// read the live plaque values. Nothing is sent to the server.
(function () {
  if (typeof playPopup !== 'function' || typeof showJackpotAward !== 'function') return;

  const panel = document.createElement('details');
  panel.className = 'demo-panel';
  panel.innerHTML = `
    <summary class="demo-btn demo-panel__toggle">DEMO</summary>
    <button class="demo-btn" type="button" data-demo="bigWin">Big Win</button>
    <button class="demo-btn" type="button" data-demo="megaWin">Mega Win</button>
    <button class="demo-btn" type="button" data-demo="epicWin">Epic Win</button>
    <button class="demo-btn" type="button" data-demo="mini">Mini</button>
    <button class="demo-btn" type="button" data-demo="minor">Minor</button>
    <button class="demo-btn" type="button" data-demo="major">Major</button>
    <button class="demo-btn" type="button" data-demo="grand">Grand</button>
    <button class="demo-btn demo-btn--all" type="button" data-demo="all">Все по очереди</button>
    <button class="demo-btn" type="button" data-demo="bombs">Бомбы ×2…×100</button>
    <button class="demo-btn" type="button" data-demo="total">TOTAL MULTIPLIER</button>
    <button class="demo-btn" type="button" data-demo="summary">Итог FS</button>
    <button class="demo-btn" type="button" data-line="a">Линия · шёлк</button>
    <button class="demo-btn" type="button" data-line="b">Линия · монеты</button>
    <button class="demo-btn" type="button" data-line="c">Линия · поток</button>
    <button class="demo-btn" type="button" data-line="classic">Линия · классика</button>`;
  document.body.appendChild(panel);

  const WIN_X = { bigWin: 25, megaWin: 60, epicWin: 150 };
  const JACKPOTS = ['mini', 'minor', 'major', 'grand'];

  function betCents() {
    const t = (document.getElementById('betValue') || {}).textContent || '1';
    return Math.round(parseFloat(t.replace(/,/g, '')) * 100) || 100;
  }
  function jackpotCents(tier) {
    const el = document.querySelector(`.crown [data-jp-value="${tier}"]`) || document.querySelector(`[data-jp-value="${tier}"]`);
    const v = el ? parseFloat(el.textContent.replace(/,/g, '')) : 0;
    return Math.round((v || 0) * 100) || betCents() * 100;
  }

  // Bombs: 2-4 random cells turn into bombs with values from the whole GDD
  // range (x2 ... x100), then they pop into the spin badge / TOTAL MULTIPLIER.
  const BOMB_SAMPLES = [2, 3, 5, 8, 10, 15, 25, 50, 100];
  function dropBombs() {
    teardownWins();
    const cells = cellInfos.filter(Boolean).sort(() => Math.random() - 0.5).slice(0, 2 + Math.floor(Math.random() * 3));
    let sum = 0;
    for (const info of cells) {
      const v = BOMB_SAMPLES[Math.floor(Math.random() * BOMB_SAMPLES.length)];
      setCellSymbol(info, 'bomb');
      setBombValue(info.cell, v);
      info.cell.classList.remove('is-landed'); void info.cell.offsetWidth; info.cell.classList.add('is-landed');
      sum += v;
    }
    return sum;
  }
  async function demoBombs() {
    const sum = dropBombs();
    await wait(700);
    setMascot('toss');
    await playBaseBombs(sum);
  }
  async function demoTotal() {
    const screen = document.getElementById('screen');
    const wasBase = screen.dataset.mode !== 'freespins';
    if (wasBase) { setTotalMult(1); applyMode('freespins'); await wait(900); }
    const from = totalMult;
    const sum = dropBombs();
    await wait(700);
    setMascot('toss');
    await playRoundBombs(from, from + sum);
    await wait(1600);
    if (wasBase) { applyMode('base'); setTotalMult(1); }
  }
  let busy = false;
  async function play(key) {
    if (key === 'bombs') return demoBombs();
    if (key === 'total') return demoTotal();
    if (key === 'summary') return playFsSummary({ spins: 17, mult: 37, total: betCents() * 128 });
    if (JACKPOTS.includes(key)) await showJackpotAward(key, jackpotCents(key));
    else await playPopup(key, betCents() * WIN_X[key]);
  }
  async function run(key) {
    if (busy) return;
    busy = true;
    panel.classList.add('is-busy');
    try {
      if (key === 'all') {
        for (const k of ['bigWin', 'megaWin', 'epicWin', ...JACKPOTS]) await play(k);
      } else {
        await play(key);
      }
    } finally {
      busy = false;
      panel.classList.remove('is-busy');
    }
  }
  // Win lines: switch the style (kept for real spins too) and show it on a
  // few paylines in turn — V, inverted V, zigzag, straight.
  const SAMPLE_LINES = [4, 5, 10, 8, 1];
  let sample = 0;
  let lineTimer = null;
  function markLine(style) {
    panel.querySelectorAll('[data-line]').forEach((b) => b.classList.toggle('is-on', b.dataset.line === style));
  }
  function showLineSample(style) {
    try { localStorage.setItem('sugarblast.winline', style); } catch (e) { /* ignore */ }
    markLine(style);
    const payline = SAMPLE_LINES[sample++ % SAMPLE_LINES.length];
    const positions = PAYLINES[payline - 1].slice(0, 4).map((row, col) => ({ row, col }));
    clearTimeout(lineTimer);
    showWinLine({ payline, positions });
    lineTimer = setTimeout(hideWinLine, 4000);
  }
  markLine(winLineStyle());

  panel.addEventListener('click', (e) => {
    const l = e.target.closest('[data-line]');
    if (l) showLineSample(l.dataset.line);
    const b = e.target.closest('[data-demo]');
    if (b) run(b.dataset.demo);
  });
})();
