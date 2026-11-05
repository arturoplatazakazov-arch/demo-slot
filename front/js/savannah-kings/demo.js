// Demo panel for the Savannah Kings art variants (like Volt Coins' DEV panel,
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
    <button class="demo-btn demo-btn--all" type="button" data-demo="all">Все по очереди</button>`;
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

  let busy = false;
  async function play(key) {
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
  panel.addEventListener('click', (e) => {
    const b = e.target.closest('[data-demo]');
    if (b) run(b.dataset.demo);
  });
})();
