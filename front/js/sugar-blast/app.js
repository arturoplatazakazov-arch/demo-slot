// Sugar Blast — session, bar and the order of events (GDD-05). Every outcome
// comes from the server (app/seed/sugar_blast.py); this file only sequences
// what slot.js draws: reels -> bombs (into the spin's × badge, or into TOTAL
// MULTIPLIER in free spins) -> wins -> scatters/wrappers -> Jackpot Wheel ->
// free-spins entry / exit -> win popups. Forked from js/savannah-kings/app.js;
// the bottom bar is the standard ui-bar-v3 (data-action contract).
const GAME_ID = 'sugar-blast';

// bonus_buy products in the seed (cost x bet). The server charges by its own
// config; these only print the price.
const BUY_PRODUCTS = [
  {
    buyId: 'free_spins_buy', kind: 'fs', mult: 102, name: 'FREE SPINS',
    desc: '15 free spins — winning bombs grow the TOTAL MULTIPLIER',
  },
  {
    buyId: 'super_free_spins_buy', kind: 'sfs', mult: 170, name: 'SUPER FREE SPINS',
    desc: '15 free spins — bombs twice as often, at least one every spin',
  },
  {
    buyId: 'jackpot_chance_buy', kind: 'jc', mult: 50, name: 'JACKPOT CHANCE',
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
  fsSpins: 0,
  fsSuper: false,
};

const $ = (id) => document.getElementById(id);
const bet = () => st.betSteps[st.betIndex];

// --- Bar --------------------------------------------------------------------

function renderBalance(value = st.balance) {
  $('balanceValue').textContent = SK.money(value);
}
function renderBet() {
  $('betValue').textContent = SK.money(bet());
  const mirror = $('v3BetMirror');
  if (mirror) mirror.textContent = SK.money(bet());
  SK.renderJackpots(st.inFs ? st.fsBet : bet());
  renderPaytable();
}
function renderWin(v) {
  $('winValue').textContent = v > 0 ? SK.money(v) : '';
  $('winReadout').classList.toggle('is-on', v > 0);
}
function setBusy(on) {
  st.busy = on;
  document.body.classList.toggle('is-busy', on);
  document.querySelector('[data-action="spin"]').classList.toggle('is-spinning', on);
  syncControls();
}
function syncControls() {
  const locked = st.busy || st.inFs || st.auto > 0;
  document.body.classList.toggle('is-locked', locked);
  document.body.classList.toggle('is-auto', st.auto > 0);
  const count = $('v3SpinCount');
  if (count) {
    count.hidden = !(st.auto > 0);
    count.textContent = st.auto > 0 ? (st.auto === Infinity ? '∞' : String(st.auto)) : '';
  }
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
  const cm = data.coin_multiplier || null;
  await SK.landReels(data.grid, { turbo: st.turbo, bombs: cm ? cm.positions : [] });

  // Bombs (GDD §5 / §6.2): with a line win they pop and fly into the spin's
  // × badge (base) or into TOTAL MULTIPLIER (free spins); without one they
  // go dark. The server already multiplied total_win.
  if (cm && cm.positions.length) {
    if (cm.applied && st.inFs) {
      SK.setMascot('toss');
      await SK.playRoundBombs(SK.totalMult, cm.round_multiplier || SK.totalMult);
    } else if (cm.applied) {
      SK.setMascot('toss');
      await SK.playBaseBombs(cm.multiplier_sum);
    } else {
      SK.dimBombs();
    }
  }

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
      SK.setMascot('cheer', 3500);
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
    await SK.flashTriggers('wrapper');
    await SK.playJackpotWheel(wheel, spinBet, { auto: st.auto > 0 || st.inFs, bought: bought === 'jc' });
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
    st.fsSpins = 0;
    st.fsSuper = bought === 'sfs';
    syncControls();
    await SK.enterFreeSpins(feature.spins_awarded || feature.spins_remaining, { superRound: st.fsSuper });
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
      await SK.leaveFreeSpins(st.fsTotal, { spins: st.fsSpins, mult: SK.totalMult });
      SK.setTotalMult(1);
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
    st.fsSpins += 1;
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
  const el = $('balanceValue');
  if (!el) return;
  el.classList.remove('is-low');
  void el.offsetWidth;
  el.classList.add('is-low');
}

// --- Buy Bonus --------------------------------------------------------------

async function openBuy() {
  // The button lives in the bar's menu flyout: fold the menu first.
  const menuBtn = $('v3MenuBtn');
  if (menuBtn && menuBtn.getAttribute('aria-expanded') === 'true') menuBtn.click();
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
// From the session's paytable (coins x line bet = bet / 20) plus the GDD §13
// rules text; pages «Candy Bombs», «Free Spins», «Jackpot Wheel», «Buy Bonus»
// (GDD §11), the wheel with both odds tables.
const WHEEL_ODDS = {
  natural: { mini: 60, minor: 28, major: 10, grand: 2 },
  bought: { mini: 76, minor: 17.5, major: 5.5, grand: 1 },
};
const BOMB_VALUES = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 50, 100];

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
    rows.map((r, c) => `<rect x="${c * 10 + 1}" y="${r * 10 + 1}" width="8" height="8" rx="1.5"/>`).join('')
  }<polyline points="${rows.map((r, c) => `${c * 10 + 5},${r * 10 + 5}`).join(' ')}"/></svg></div>`).join('');
  const odds = (set) => SK.TIERS.slice().reverse().map((t) =>
    `<tr class="t-${t}"><td>${t.toUpperCase()}</td><td>${SK.money(SK.TIER_X[t] * b)}</td><td>${WHEEL_ODDS[set][t]}%</td></tr>`).join('');
  const price = (id) => SK.money(b * BUY_PRODUCTS.find((p) => p.buyId === id).mult, { cur: true });
  box.innerHTML = `
    <section><h3>High symbols</h3><div class="pt-grid">${['h1', 'h2', 'h3', 'h4'].map(row).join('')}</div></section>
    <section><h3>Low symbols</h3><div class="pt-grid">${['l1', 'l2', 'l3', 'l4'].map(row).join('')}</div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('wild')}" alt=""><div><h3>Swirl Lollipop — Wild</h3>
      <p>Appears on reels 2, 3 and 4 and substitutes for every symbol except the Golden Lollipop, the Candy Bomb and the Golden Wrapper.</p></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('bomb')}" alt=""><div><h3>Candy Bombs</h3>
      <p>Every Candy Bomb carries a multiplier: ${BOMB_VALUES.map((v) => `×${v}`).join(' · ')}.
      If the spin has a line win, the values of all bombs on the screen are added up and the total line win is multiplied by the sum.
      Without a line win the bombs give nothing. Scatter and Jackpot Wheel pays are never multiplied.</p></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('scatter')}" alt=""><div><h3>Golden Lollipop — Free Spins</h3>
      <p>3, 4 or 5 anywhere (one per reel) start 15, 20 or 25 Free Spins and pay:</p><ul class="pt-inline">${scPay}</ul>
      <p>In Free Spins a TOTAL MULTIPLIER starts at ×1. If a free spin has a line win and bombs, their values are added to the
      TOTAL MULTIPLIER and the line win is multiplied by it; a line win without bombs pays as it is. The TOTAL MULTIPLIER never resets
      during the round. 3 or more Golden Lollipops during Free Spins add +5 spins.</p></div></section>
    <section class="pt-feature"><img src="${SK.symbolSrc('wrapper')}" alt=""><div><h3>Golden Wrapper — Jackpot Wheel</h3>
      <p>Lands on reels 1, 3 and 5. Three Wrappers at once spin the Jackpot Wheel — in the base game and in Free Spins.</p></div></section>
    <section><h3>Jackpot Wheel</h3>
      <p>The prize is decided before the wheel starts; the wheel shows it. The 12 sectors on the wheel are not the odds —
      the real chance of each prize is:</p>
      <div class="pt-odds">
        <table><caption>Natural trigger</caption><tr><th>Prize</th><th>Win</th><th>Chance</th></tr>${odds('natural')}</table>
        <table><caption>Jackpot Chance purchase</caption><tr><th>Prize</th><th>Win</th><th>Chance</th></tr>${odds('bought')}</table>
      </div></section>
    <section><h3>Buy Bonus</h3>
      <p><b>Free Spins</b> — ${price('free_spins_buy')}: 15 Free Spins with the TOTAL MULTIPLIER.
      <b>Super Free Spins</b> — ${price('super_free_spins_buy')}: 15 Free Spins, bombs land almost twice as often and at least one in every spin.
      <b>Jackpot Chance</b> — ${price('jackpot_chance_buy')}: one spin of the Jackpot Wheel with the purchase odds above.
      The purchase spin itself pays nothing. Not available during Free Spins or Autoplay. Each purchase is a separate round.</p></section>
    <section><h3>20 paylines</h3><div class="pt-lines">${lines}</div>
      <p>Wins pay left to right from reel 1; only the longest win per line pays; wins on different lines add up.
      Malfunction voids all pays and plays.</p></section>
    <section class="pt-small"><p>Maximum win 10 000× the bet per round. Theoretical RTP 96.0% · purchases ~95.5%.</p></section>`;
}

// --- Setup ------------------------------------------------------------------

function setupBar() {
  // Standard bar (ui-bar-v3): spin / bet / sound / info by data-action. Its
  // own script only draws the menu, tooltips and chips — autoplay and turbo
  // are wired here.
  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.addEventListener('click', () => {
    if (st.auto > 0) { st.auto = 0; syncControls(); return; } // spin = stop autoplay
    if (st.busy || st.inFs) return;
    Sound.playSfx('click');
    spinOnce().then(() => drive());
  });
  for (const b of document.querySelectorAll('[data-action="bet-minus"]')) b.addEventListener('click', () => stepBet(-1));
  for (const b of document.querySelectorAll('[data-action="bet-plus"]')) b.addEventListener('click', () => stepBet(1));
  for (const chip of document.querySelectorAll('.v3-chip[data-spins]')) {
    chip.addEventListener('click', () => {
      // ui-bar-v3.js toggles the chip first; an active chip starts autoplay.
      setTimeout(() => {
        if (!chip.classList.contains('is-active')) { st.auto = 0; syncControls(); return; }
        if (st.busy || st.inFs) return;
        st.auto = Number(chip.dataset.spins);
        syncControls();
        drive();
      }, 0);
    });
  }
  const turbo = $('v3TurboBtn');
  if (turbo) turbo.addEventListener('click', () => { st.turbo = !st.turbo; });
  for (const b of document.querySelectorAll('[data-buy-open]')) b.addEventListener('click', openBuy);
  const sound = document.querySelector('[data-action="sound"]');
  if (sound) {
    sound.addEventListener('click', () => Sound.toggleMuted());   // sound.js keeps .is-muted in sync
  }
  const info = document.querySelector('[data-action="info"]');
  if (info) info.addEventListener('click', () => {
    Sound.playSfx('popupOpen');
    renderPaytable();
    $('paytable').hidden = false;
  });
  $('paytableClose').addEventListener('click', () => { Sound.playSfx('popupClose'); $('paytable').hidden = true; });
  $('paytable').addEventListener('click', (e) => { if (e.target === $('paytable')) $('paytable').hidden = true; });
  // Space = spin (desktop).
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !e.repeat && $('paytable').hidden && $('buyOverlay').hidden) { e.preventDefault(); spinBtn.click(); }
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
  for (const el of document.querySelectorAll('.ui-balance__currency, .ui-bet-field__currency, .v3-readout__cur')) el.textContent = st.currency;
  renderBalance();
  renderBet();
  syncControls();
}

setupBar();
bootstrap();
