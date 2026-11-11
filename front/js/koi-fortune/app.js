// Koi Fortune — session, bar and the order of events. Every outcome comes
// from the server (app/seed/koi_fortune.py); this file only sequences what
// slot.js draws: reels -> line wins -> Hold & Win -> free-spins entry / exit
// -> win popups. Ante Bet: the spin request carries ante_bet, the spin costs
// cost_multiplier x the bet (from the session), wins are paid on the bet.
const GAME_ID = 'koi-fortune';

// bonus_buy products in the seed (cost x bet). The server charges by its own
// config; these only print the price. Buys always cost the plain bet.
const BUY_PRODUCTS = [
  {
    buyId: 'free_spins_buy', kind: 'fs', mult: 100, name: 'FREE SPINS',
    desc: '10 free spins — coins land far more often, +5 for 3 gongs',
  },
  {
    buyId: 'hold_and_win_buy', kind: 'hw', mult: 60, name: 'HOLD & WIN',
    desc: '6+ coins lock at once — 3 respins, Mini · Minor · Major, 15/15 = Grand',
  },
];
// Win-tier popups, x bet (base game and free spins alike).
const WIN_TIERS = [['epicWin', 50], ['megaWin', 25], ['bigWin', 10]];
const FS_SPIN_GAP_MS = 520;
const AUTO_SPIN_GAP_MS = 380;

const st = {
  sessionId: null,
  betSteps: [20, 40, 100, 200, 400, 1000, 2000, 4000, 10000],
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  busy: false,
  inFs: false,
  fsRemaining: 0,
  fsTotal: 0,
  fsBet: 0,
  auto: 0, // autospins left; Infinity for "until stopped"
  turbo: false,
  symbols: [],
  lastGrid: null,
  ante: false,
  anteMult: 0, // from the session; 0 = the game has no Ante Bet
};

const $ = (id) => document.getElementById(id);
const bet = () => st.betSteps[st.betIndex];
// What a base spin costs right now (Ante Bet adds cost_multiplier - 1).
const spinCost = () => (st.ante && st.anteMult ? Math.round(bet() * st.anteMult) : bet());

// --- Bar --------------------------------------------------------------------

function renderBalance(value = st.balance) {
  $('balanceValue').textContent = SK.money(value);
}
function renderBet() {
  $('betValue').textContent = SK.money(bet());
  SK.renderJackpots(st.inFs ? st.fsBet : bet());
  $('buyPrice').textContent = SK.money(bet() * BUY_PRODUCTS[1].mult);
  SK.setCoinBet(st.inFs ? st.fsBet : bet());
  renderAnte();
  renderPaytable();
}
function renderAnte() {
  const btn = $('anteBtn');
  if (!btn) return;
  btn.hidden = !st.anteMult;
  btn.classList.toggle('is-on', st.ante);
  btn.setAttribute('aria-pressed', String(st.ante));
  $('anteCost').textContent = st.ante ? `${SK.money(spinCost())}` : `+${Math.round((st.anteMult - 1) * 100)}%`;
  document.body.classList.toggle('is-ante', st.ante);
}
function renderWin(v) {
  $('winValue').textContent = v > 0 ? SK.money(v) : '';
  $('winReadout').classList.toggle('is-on', v > 0);
}
function setBusy(on) {
  st.busy = on;
  document.body.classList.toggle('is-busy', on);
  $('spinBtn').classList.toggle('is-spinning', on);
  syncControls();
}
function syncControls() {
  const locked = st.busy || st.inFs || st.auto > 0;
  document.body.classList.toggle('is-locked', locked);
  document.body.classList.toggle('is-auto', st.auto > 0);
  $('spinCount').textContent = st.auto > 0 ? (st.auto === Infinity ? '∞' : String(st.auto)) : '';
}

function stepBet(d) {
  if (st.busy || st.inFs || st.auto > 0) return;
  st.betIndex = Math.max(0, Math.min(st.betSteps.length - 1, st.betIndex + d));
  Sound.playSfx('click');
  renderBet();
}

// --- Spins ------------------------------------------------------------------

function winTier(amount, b) {
  for (const [key, x] of WIN_TIERS) if (amount >= x * b) return key;
  return null;
}

// One server round-trip, presented end to end.
async function present(data, { bought = null } = {}) {
  const spinBet = st.inFs ? st.fsBet : bet();
  st.lastGrid = data.grid;
  SK.setCoinBet(spinBet);
  const coinFaces = data.coin_multiplier ? data.coin_multiplier.positions : null;
  await SK.landReels(data.grid, { turbo: st.turbo, coinFaces });

  const hw = data.hold_and_win && data.hold_and_win.triggered ? data.hold_and_win : null;
  const hwWin = hw ? hw.total_win : 0;
  const lineWin = data.total_win - hwWin;
  const feature = data.feature && data.feature.type === 'free_spins' ? data.feature : null;
  const entering = !st.inFs && feature && feature.spins_remaining > 0;
  const retrigger = st.inFs && feature && feature.triggered;

  if (lineWin > 0) {
    SK.playWins(data.winning_cells, data.line_wins, data.count_wins);
    renderWin(lineWin);
    if (st.inFs) { st.fsTotal += lineWin; SK.setFsPanel(st.fsRemaining, st.fsTotal); }
    const tier = winTier(lineWin, spinBet);
    if (tier) {
      await SK.wait(700);
      await SK.playPopup(tier, lineWin, 1800);
    } else {
      SK.showInlineWinAmount(lineWin);
      Sound.playSfx('smallWin');
      await SK.wait(st.inFs || st.auto ? 900 : 350);
    }
  }

  // 6+ coins -> Hold & Win (base game, free spins, or a bought round).
  if (hw) {
    if (lineWin > 0) await SK.wait(600);
    SK.teardownWins();
    await SK.playHoldAndWin(hw, spinBet, { turbo: st.turbo, returnMode: st.inFs ? 'freespins' : 'base' });
    SK.applyGrid(data.grid);
    renderWin(data.total_win);
    if (st.inFs) { st.fsTotal += hwWin; SK.setFsPanel(st.fsRemaining, st.fsTotal); }
  }

  if (entering) {
    SK.teardownWins();
    await SK.flashTriggers('scatter');
    st.inFs = true;
    st.fsBet = spinBet;
    st.fsRemaining = feature.spins_remaining;
    st.fsTotal = 0;
    syncControls();
    await SK.enterFreeSpins(feature.spins_awarded || feature.spins_remaining);
  } else if (retrigger) {
    await SK.flashTriggers('scatter');
    await SK.playPopup('freeSpinsMore', feature.spins_awarded || 5, 1600);
  }

  st.balance = data.balance;
  renderBalance();

  if (st.inFs && !entering) {
    st.fsRemaining = feature ? feature.spins_remaining : 0;
    st.fsTotal = feature ? feature.total_win : st.fsTotal;
    SK.setFsPanel(st.fsRemaining, st.fsTotal);
    if (st.fsRemaining === 0) {
      await SK.wait(600);
      SK.teardownWins();
      await SK.leaveFreeSpins(st.fsTotal);
      renderWin(st.fsTotal);
      st.inFs = false;
      st.fsTotal = 0;
      renderBet();
      syncControls();
    }
  }
}

async function runSpin(request, opts = {}) {
  if (st.busy || !st.sessionId) return false;
  setBusy(true);
  renderWin(0);
  // The stake leaves the balance the moment the reels start (it comes back
  // with the server's figure at the end).
  if (!st.inFs && !opts.bought) renderBalance(st.balance - spinCost());
  SK.startReelLoop();
  let ok = true;
  try {
    const data = await request();
    await present(data, opts);
  } catch (err) {
    ok = false;
    console.error('spin failed:', err);
    toast('Connection problem — your balance is safe. Try again.');
    SK.stopReelLoop();
    if (st.lastGrid) SK.applyGrid(st.lastGrid);
    renderBalance();
    st.auto = 0;
  } finally {
    setBusy(false);
  }
  return ok;
}

function spinOnce() {
  if (st.inFs) {
    const remaining = st.fsRemaining;
    if (remaining > 0) {
      st.fsRemaining = remaining - 1;
      SK.setFsPanel(st.fsRemaining, st.fsTotal);
      SK.bumpFsPanel();
    }
    return runSpin(() => Api.spin(st.sessionId, st.fsBet));
  }
  if (st.balance < spinCost()) {
    st.auto = 0; syncControls(); flashBalance();
    toast(st.ante ? 'Not enough balance — lower the bet or switch Ante off.' : 'Not enough balance — lower the bet.');
    return Promise.resolve(false);
  }
  return runSpin(() => Api.spin(st.sessionId, bet(), st.ante ? { ante_bet: true } : null));
}

// Free spins run on their own; autoplay keeps the base game going.
let driving = false;
async function drive() {
  if (driving) return;
  driving = true;
  try {
    for (;;) {
      if (st.inFs) { await SK.wait(FS_SPIN_GAP_MS); if (!(await spinOnce())) break; continue; }
      if (st.auto > 0) {
        await SK.wait(AUTO_SPIN_GAP_MS);
        if (st.auto <= 0) break;
        if (st.auto !== Infinity) st.auto -= 1;
        syncControls();
        if (!(await spinOnce())) break;
        continue;
      }
      break;
    }
  } finally {
    driving = false;
    syncControls();
  }
}

// Short status line over the reels (pages that have #toast).
let toastTimer = null;
function toast(text) {
  const el = $('toast');
  if (!el) return;
  el.textContent = text;
  el.classList.add('is-on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-on'), 2600);
}

function flashBalance() {
  const el = $('balanceReadout');
  el.classList.remove('is-low');
  void el.offsetWidth;
  el.classList.add('is-low');
}

// --- Buy Bonus --------------------------------------------------------------

async function openBuy() {
  if (st.busy || st.inFs || st.auto > 0 || !st.sessionId || SK.dimCount > 0) return;
  Sound.playSfx('click');
  SK.teardownWins();
  const products = BUY_PRODUCTS.map((p) => {
    const q = BuyBonus.quote({ betSteps: st.betSteps, betIndex: st.betIndex, balance: st.balance, multiplier: p.mult });
    return {
      ...p, cost: q.cost, affordable: q.affordable, quote: q,
      note: q.lowered ? `BET ${SK.money(bet())} → ${SK.money(q.bet)}` : '',
    };
  });
  const buyId = await SK.showBuyWindow(products);
  if (!buyId) return;
  const chosen = products.find((p) => p.buyId === buyId);
  st.betIndex = chosen.quote.betIndex;
  renderBet();
  renderBalance(st.balance - chosen.cost);
  await runSpin(() => Api.buyFeature(st.sessionId, buyId, bet()), { bought: chosen.kind });
  drive();
}

// --- Paytable ---------------------------------------------------------------
//
// Generated from the session's paytable (per line = bet / 10) and the seed's
// rules (app/seed/koi_fortune.py).
const COIN_FACES = [1, 2, 3, 5, 8, 10, 15, 25, 50];

function renderPaytable() {
  const box = $('paytableBody');
  if (!box || !st.symbols.length) return;
  const b = bet();
  const line = b / 10;
  const sym = (code) => st.symbols.find((s) => s.code === code);
  const row = (code) => {
    const s = sym(code);
    if (!s) return '';
    const pays = ['5', '4', '3'].filter((k) => s.paytable[k] !== undefined)
      .map((k) => `<li><span>${k}×</span><b>${SK.money(s.paytable[k] * line)}</b></li>`).join('');
    return `<div class="pt-sym"><img src="${SK.symbolSrc(code)}" alt=""><ul>${pays}</ul></div>`;
  };
  const lines = SK.PAYLINES.map((rows, i) => `<div class="pt-line"><i>${i + 1}</i><svg viewBox="0 0 50 30">${
    rows.map((r, c) => `<rect x="${c * 10 + 1}" y="${r * 10 + 1}" width="8" height="8" rx="1.5"/>`).join('')
  }<polyline points="${rows.map((r, c) => `${c * 10 + 5},${r * 10 + 5}`).join(' ')}"/></svg></div>`).join('');
  const jps = SK.TIERS.slice().reverse().map((t) =>
    `<tr class="t-${t}"><td>${t.toUpperCase()}</td><td>${SK.TIER_X[t]}×</td><td>${SK.money(SK.TIER_X[t] * b)}</td></tr>`).join('');
  const ante = st.anteMult
    ? `<section><h3>Ante Bet</h3><p>Switch it on next to the balance: every base spin costs
      <b>${Math.round(st.anteMult * 100)}%</b> of the bet (${SK.money(Math.round(b * st.anteMult), { cur: true })}),
      wins are still paid on the bet, and Gongs and Coins land about twice as often, so both features come twice as often.
      Free spins and purchases are never affected.</p></section>`
    : '';
  box.innerHTML = `
    <section><h3>High symbols</h3><div class="pt-grid">${['koi', 'turtle', 'lantern', 'lotus'].map(row).join('')}</div></section>
    <section><h3>Low symbols</h3><div class="pt-grid">${['a', 'k', 'q', 'j'].map(row).join('')}</div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('wild')}" alt=""><div><h3>Dragon — Wild</h3>
      <p>Lands on reels 2 to 5 and substitutes for every paying symbol. A line of Dragons pays:</p>
      <ul class="pt-inline">${row('wild').replace(/^.*?<ul>|<\/ul>.*$/g, '')}</ul></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('scatter')}" alt=""><div><h3>Gong — Free Spins</h3>
      <p>3 or more anywhere (one per reel at most) start <b>10 Free Spins</b>. In Free Spins Coins land about three times as often;
      3 Gongs during the round add <b>+5</b> spins.</p></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('coin')}" alt=""><div><h3>Coin — Hold &amp; Win</h3>
      <p>Every Coin shows a value: ${COIN_FACES.map((x) => `${x}×`).join(' · ')} the bet. <b>6 or more</b> Coins start Hold &amp; Win:
      they lock, the other cells respin <b>3 times</b>, every new Coin locks and resets the count to 3.
      During respins the Jackpot Coin can land with MINI, MINOR or MAJOR. Fill all 15 cells for the <b>GRAND</b>.
      The round pays the sum of all Coins.</p></div></section>
    <section><h3>Jackpots</h3><div class="pt-odds"><table><tr><th>Jackpot</th><th>× bet</th><th>Win</th></tr>${jps}</table></div></section>
    ${ante}
    <section><h3>Buy Bonus</h3>
      <p><b>Free Spins</b> — ${SK.money(b * 100, { cur: true })} (100× the bet): 10 Free Spins.
      <b>Hold &amp; Win</b> — ${SK.money(b * 60, { cur: true })} (60× the bet): the round starts with 6 or more Coins.
      Purchases cost the plain bet with or without Ante. Not available during Free Spins or Autoplay.</p></section>
    <section><h3>10 paylines</h3><div class="pt-lines">${lines}</div>
      <p>Wins pay left to right from reel 1; only the longest win per line pays; wins on different lines add up.
      Malfunction voids all pays and plays.</p></section>
    <section class="pt-small"><p>Maximum win 5 000× the bet per round. Theoretical RTP 95.6% · with Ante 95.7% · purchases ~95.5%.</p></section>`;
}

// --- Setup ------------------------------------------------------------------

function setupBar() {
  $('spinBtn').addEventListener('click', () => {
    if (st.auto > 0) { st.auto = 0; syncControls(); return; } // spin = stop autoplay
    if (st.busy || st.inFs) return;
    Sound.playSfx('click');
    spinOnce().then(() => drive());
  });
  $('betMinus').addEventListener('click', () => stepBet(-1));
  $('betPlus').addEventListener('click', () => stepBet(1));
  $('autoBtn').addEventListener('click', () => {
    Sound.playSfx('click');
    if (st.auto > 0) { st.auto = 0; syncControls(); return; }
    $('autoMenu').hidden = !$('autoMenu').hidden;
  });
  $('autoMenu').addEventListener('click', (e) => {
    const b = e.target.closest('[data-auto]');
    if (!b) return;
    $('autoMenu').hidden = true;
    if (st.busy || st.inFs) return;
    st.auto = b.dataset.auto === 'inf' ? Infinity : Number(b.dataset.auto);
    syncControls();
    drive();
  });
  $('turboBtn').addEventListener('click', () => {
    st.turbo = !st.turbo;
    $('turboBtn').classList.toggle('is-on', st.turbo);
    Sound.playSfx('click');
  });
  for (const b of document.querySelectorAll('[data-buy-open]')) b.addEventListener('click', openBuy);
  const ante = $('anteBtn');
  if (ante) {
    ante.addEventListener('click', () => {
      if (st.busy || st.inFs) return;
      st.ante = !st.ante;
      Sound.playSfx(st.ante ? 'pawTrigger' : 'click');
      renderBet();
    });
  }
  $('menuBtn').addEventListener('click', () => { Sound.playSfx('click'); $('menu').classList.toggle('is-open'); });
  $('soundBtn').addEventListener('click', () => { Sound.toggleMuted(); $('soundBtn').classList.toggle('is-off'); });
  $('infoBtn').addEventListener('click', () => {
    $('menu').classList.remove('is-open');
    Sound.playSfx('popupOpen');
    renderPaytable();
    $('paytable').hidden = false;
  });
  $('paytableClose').addEventListener('click', () => { Sound.playSfx('popupClose'); $('paytable').hidden = true; });
  $('paytable').addEventListener('click', (e) => { if (e.target === $('paytable')) $('paytable').hidden = true; });
  document.addEventListener('pointerdown', (e) => {
    if (!e.target.closest('#menu, #menuBtn')) $('menu').classList.remove('is-open');
    if (!e.target.closest('#autoMenu, #autoBtn')) $('autoMenu').hidden = true;
  });
  // Space = spin (desktop).
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !e.repeat && $('paytable').hidden && $('buyOverlay').hidden) { e.preventDefault(); $('spinBtn').click(); }
  });
}

async function bootstrap() {
  try {
    const data = await Api.startSession(GAME_ID);
    st.sessionId = data.session_id;
    st.balance = data.balance;
    st.currency = data.currency;
    SK.setCurrency(data.currency);
    st.symbols = data.symbols || [];
    st.anteMult = data.ante_bet ? data.ante_bet.cost_multiplier : 0;
    if (data.bet && data.bet.steps && data.bet.steps.length) {
      st.betSteps = data.bet.steps;
      const i = st.betSteps.indexOf(data.bet.default);
      st.betIndex = i >= 0 ? i : Math.min(3, st.betSteps.length - 1);
    }
  } catch (err) {
    console.error('failed to start session, spin/buy stay disabled:', err);
  }
  $('currency').textContent = st.currency;
  renderBalance();
  renderBet();
  syncControls();
}

setupBar();
bootstrap();
