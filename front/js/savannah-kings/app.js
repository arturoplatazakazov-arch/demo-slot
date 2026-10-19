// Savannah Kings — session, bar and the order of events (GDD-03). Every
// outcome comes from the server (app/seed/savannah_kings.py); this file only
// sequences what slot.js draws: reels -> lions expand -> wins -> masks/paws
// -> Jackpot Wheel -> free-spins entry / exit -> win popups.
const GAME_ID = 'savannah-kings';

// bonus_buy products in the seed (cost x bet). The server charges by its own
// config; these only print the price.
const BUY_PRODUCTS = [
  {
    buyId: 'free_spins_buy', kind: 'fs', mult: 50, name: 'FREE SPINS',
    desc: '10 free spins at night — every lion stands over its whole reel',
  },
  {
    buyId: 'jackpot_chance_buy', kind: 'wheel', mult: 50, name: 'JACKPOT CHANCE',
    desc: 'One spin of the Jackpot Wheel — Mini, Minor, Major or Grand',
  },
];
// Win-tier popups, x bet (base game and free spins alike).
const WIN_TIERS = [['epicWin', 50], ['megaWin', 25], ['bigWin', 10]];
const FS_SPIN_GAP_MS = 520;
const AUTO_SPIN_GAP_MS = 380;

const st = {
  sessionId: null,
  betSteps: [20, 40, 60, 100, 200, 400, 600, 1000, 2000, 4000, 6000, 10000],
  betIndex: 4,
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
  wheelSegments: null,
};

const $ = (id) => document.getElementById(id);
const bet = () => st.betSteps[st.betIndex];

// --- Bar --------------------------------------------------------------------

function renderBalance(value = st.balance) {
  $('balanceValue').textContent = SK.money(value);
}
function renderBet() {
  $('betValue').textContent = SK.money(bet());
  SK.renderJackpots(st.inFs ? st.fsBet : bet());
  $('buyPrice').textContent = SK.money(bet() * BUY_PRODUCTS[0].mult);
  renderPaytable();
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
  await SK.landReels(data.grid, { wildEvents: data.wild_events || [], turbo: st.turbo });

  const wheel = data.wheel_of_fortune || null;
  const wheelWin = wheel ? wheel.win_amount : 0;
  const lineWin = data.total_win - wheelWin;
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

  // Three paws -> the wheel (base game, free spins, or a bought Jackpot Chance).
  if (wheel) {
    SK.teardownWins();
    await SK.flashTriggers('paw');
    await SK.playJackpotWheel(wheel, spinBet, { auto: st.auto > 0 || st.inFs, bought: bought === 'wheel' });
    renderWin(data.total_win);
    if (st.inFs) { st.fsTotal += wheelWin; SK.setFsPanel(st.fsRemaining, st.fsTotal); }
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
  if (!st.inFs && !opts.bought) renderBalance(st.balance - bet());
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
  if (st.balance < bet()) {
    st.auto = 0; syncControls(); flashBalance();
    toast('Not enough balance — lower the bet.');
    return Promise.resolve(false);
  }
  return runSpin(() => Api.spin(st.sessionId, bet()));
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
// Generated from the session's paytable (coins x line bet = bet / 20), with
// the GDD rules and both wheel odds tables (§6.2 / §6.4).
const WHEEL_ODDS = {
  natural: { mini: 60, minor: 28, major: 10, grand: 2 },
  bought: { mini: 76, minor: 17.5, major: 5.5, grand: 1 },
};

function renderPaytable() {
  const box = $('paytableBody');
  if (!box || !st.symbols.length) return;
  const b = bet();
  const line = b / 20;
  const sym = (code) => st.symbols.find((s) => s.code === code);
  const row = (code) => {
    const s = sym(code);
    if (!s) return '';
    const pays = ['5', '4', '3'].filter((k) => s.paytable[k] !== undefined)
      .map((k) => `<li><span>${k}×</span><b>${SK.money(s.paytable[k] * line)}</b></li>`).join('');
    return `<div class="pt-sym"><img src="${SK.symbolSrc(code)}" alt=""><ul>${pays}</ul></div>`;
  };
  const sc = sym('scatter');
  const scPay = sc ? ['5', '4', '3'].map((k) => `<li><span>${k}×</span><b>${SK.money(sc.paytable[k] * b)}</b></li>`).join('') : '';
  const lines = SK.PAYLINES.map((rows, i) => `<div class="pt-line"><i>${i + 1}</i><svg viewBox="0 0 50 30">${
    rows.map((r, c) => `<rect x="${c * 10 + 1}" y="${r * 10 + 1}" width="8" height="8" rx="1.5" class="${''}"/>`).join('')
  }<polyline points="${rows.map((r, c) => `${c * 10 + 5},${r * 10 + 5}`).join(' ')}"/></svg></div>`).join('');
  const odds = (set) => SK.TIERS.slice().reverse().map((t) =>
    `<tr class="t-${t}"><td>${t.toUpperCase()}</td><td>${SK.money(SK.TIER_X[t] * b)}</td><td>${WHEEL_ODDS[set][t]}%</td></tr>`).join('');
  box.innerHTML = `
    <section><h3>High symbols</h3><div class="pt-grid">${['elephant', 'buffalo', 'leopard', 'zebra'].map(row).join('')}</div></section>
    <section><h3>Low symbols</h3><div class="pt-grid">${['a', 'k', 'q', 'j'].map(row).join('')}</div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('wild')}" alt=""><div><h3>Lion — Wild</h3>
      <p>Appears on reels 2, 3 and 4 and substitutes for every symbol except the Sun Mask and the Golden Paw.
      In Free Spins every Lion expands to cover its whole reel before wins are counted.</p></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('scatter')}" alt=""><div><h3>Sun Mask — Scatter</h3>
      <p>3, 4 or 5 anywhere start 10, 15 or 20 Free Spins and pay:</p><ul class="pt-inline">${scPay}</ul>
      <p>3 or more during Free Spins add +5 spins. Masks and Paws under an expanded Lion still count.</p></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('paw')}" alt=""><div><h3>Golden Paw — Jackpot Wheel</h3>
      <p>Lands on reels 1, 3 and 5. Three Paws at once spin the Jackpot Wheel — in the base game and in Free Spins.</p></div></section>
    <section><h3>Jackpot Wheel</h3>
      <p>The prize is decided before the wheel starts; the wheel shows it. The 12 sectors on the wheel are not the odds —
      the real chance of each prize is:</p>
      <div class="pt-odds">
        <table><caption>Natural trigger</caption><tr><th>Prize</th><th>Win</th><th>Chance</th></tr>${odds('natural')}</table>
        <table><caption>Jackpot Chance purchase</caption><tr><th>Prize</th><th>Win</th><th>Chance</th></tr>${odds('bought')}</table>
      </div></section>
    <section><h3>Buy Bonus</h3>
      <p><b>Free Spins</b> — ${SK.money(b * 50, { cur: true })}: 10 Free Spins with the expanding Lion.
      <b>Jackpot Chance</b> — ${SK.money(b * 50, { cur: true })}: one spin of the Jackpot Wheel with the purchase odds above.
      Not available during Free Spins or Autoplay. Each purchase is a separate round.</p></section>
    <section><h3>20 paylines</h3><div class="pt-lines">${lines}</div>
      <p>Wins pay left to right from reel 1; only the longest win per line pays; wins on different lines add up.
      Malfunction voids all pays and plays.</p></section>
    <section class="pt-small"><p>Maximum win 5 000× the bet per round. Theoretical RTP 96.0% · purchases ~95.4%.</p></section>`;
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
    if (data.bet && data.bet.steps && data.bet.steps.length) {
      st.betSteps = data.bet.steps;
      const i = st.betSteps.indexOf(data.bet.default);
      st.betIndex = i >= 0 ? i : Math.min(4, st.betSteps.length - 1);
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
