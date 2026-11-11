// Great Uniqorn — bottom UI bar + spin orchestration, adapted from
// ../uniqorn-scandal/app.js. Session bootstraps on load; every Spin/Buy click
// is a real request.
const GAME_ID = 'great-uniqorn';

const gameState = {
  sessionId: null,
  betSteps: [10000, 25000, 50000, 100000, 250000, 500000], // fallback if the backend is unreachable
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  freeSpinsRemaining: 0,
  lastGrid: null,
  symbols: [],
  freeSpinsTrigger: null,
  // The current free-spins round was bought (BUY BONUS), not won from
  // scatters — picks BONUS SPINS TOTAL WIN over FREE SPINS TOTAL WIN at its end.
  boughtBonus: false,
};

// How long the scatter win plays over the grid before the bonus intro starts.
const SCATTER_WIN_LEAD_MS = 2300;

const WIN_TIER_SOUNDS = { bigWin: 'bigWin', epicWin: 'epicWin', megaWin: 'megaWin', bonusSpinsTotalWin: 'bonusTotalWin' };

function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

function renderBet() {
  document.getElementById('betValue').textContent = formatNumber(gameState.betSteps[gameState.betIndex]);
}

function renderBalance() {
  document.getElementById('balanceValue').textContent = formatNumber(gameState.balance);
  document.querySelector('.ui-balance__currency').textContent = gameState.currency;
  document.querySelector('.ui-bet-field__currency').textContent = gameState.currency;
}

function setupBetStepper() {
  document.querySelector('[data-action="bet-minus"]').addEventListener('click', () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0) return;
    gameState.betIndex = Math.max(0, gameState.betIndex - 1);
    renderBet();
  });
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0) return;
    gameState.betIndex = Math.min(gameState.betSteps.length - 1, gameState.betIndex + 1);
    renderBet();
  });
}

// free-spins-counter.png's number — the img/label pair is otherwise static art.
function updateFreeSpinsCounter(remaining) {
  const el = document.getElementById('freeSpinsValue');
  if (el) el.textContent = remaining;
}

// Shared tail end of both a normal spin and a bonus-buy response: update
// balance/mode/counter, play whatever won, show a popup if the server sent one.
async function applySpinResult(data) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  const remaining = data.feature && data.feature.type === 'free_spins' ? data.feature.spins_remaining : 0;
  gameState.freeSpinsRemaining = remaining;
  // Whether this spin enters the bonus from the base game — captured before
  // setFreeSpinsMode flips the mode. Win cells (the scatters landing) play
  // first, then the intro (blackout + bonusSpinsWin popup + reveal) runs.
  const enteringBonus = document.getElementById('screen').dataset.mode !== 'freespins' && remaining > 0;

  playWinCells(data.winning_cells, data.line_wins, data.count_wins);

  // Free spins won from burgers (not bought): the scatter win plays over the
  // pulsing scatters before the bonus intro blacks the screen out.
  const scatterTrigger = data.popup && data.popup.type === 'bonusSpinsWin' && !(enteringBonus && gameState.boughtBonus);
  if (scatterTrigger) {
    Sound.playSfx('scatterWin');
    if (enteringBonus) await new Promise((r) => setTimeout(r, SCATTER_WIN_LEAD_MS));
  }

  await setFreeSpinsMode(remaining > 0, remaining);
  if (remaining > 0) updateFreeSpinsCounter(remaining);
  const roundOver = remaining === 0;

  if (data.popup) {
    // The entry's bonusSpinsWin is shown by the intro transition itself; a
    // re-trigger inside the bonus still shows its popup normally here.
    const shownByIntro = enteringBonus && data.popup.type === 'bonusSpinsWin';
    if (!shownByIntro) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount, 2500, { bought: gameState.boughtBonus });
    }
  } else if (data.total_win > 0) {
    // Base wins (below the big/mega/epic threshold) never get a Spine popup —
    // show the amount inline over the grid instead.
    Sound.playSfx('smallWin');
    showInlineWinAmount(data.total_win);
  }
  if (roundOver) gameState.boughtBonus = false;
}

async function runSpin(request) {
  if (gameState.isSpinning || !gameState.sessionId) return;
  gameState.isSpinning = true;

  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  startReelLoop();

  try {
    const data = await request();
    const anticipationColumns = gameState.freeSpinsTrigger
      ? ReelMath.collectAnticipationColumns(
          data.grid, GRID_COLS, GRID_ROWS,
          gameState.freeSpinsTrigger.trigger_symbol_code, gameState.freeSpinsTrigger.trigger_count,
        )
      : [];
    await landReels(data.grid, anticipationColumns, data.multiplier_wilds || []);
    await applySpinResult(data);
  } catch (err) {
    console.error('spin failed:', err);
    if (gameState.freeSpinsRemaining === 0) gameState.boughtBonus = false;
    stopReelLoop();
    if (gameState.lastGrid) await applyGrid(gameState.lastGrid);
  } finally {
    spinBtn.classList.remove('is-spinning');
    gameState.isSpinning = false;
  }
}

function setupSpinButton() {
  document.querySelector('[data-action="spin"]').addEventListener('click', () => {
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.spin(gameState.sessionId, betAmount));
  });
}

// Bonus buy terms — the seed's bonus_buy product (app/seed/great_uniqorn.py):
// the session-start response doesn't carry them, so they live here.
const BUY_COST_MULTIPLIER = 100;
const BUY_SPINS = 10;

// BUY BONUS opens a confirmation with the price; only BUY sends the purchase.
// It used to buy straight away, and at the default bet (55 000 -> 5.5M)
// the server refused for lack of balance with nothing on screen — now the
// dialog says so and keeps BUY disabled.
function setupBuyBonusButton() {
  const buyBtn = document.querySelector('.sign-buy-bonus');
  const dialog = document.getElementById('buyDialog');
  if (!buyBtn || !dialog) return;
  const confirmBtn = document.getElementById('buyConfirm');
  let open = false;

  const close = (playSound = true) => {
    if (!open) return;
    open = false;
    if (playSound) Sound.playSfx('popupClose');
    dialog.classList.remove('is-open');
    popScreenDim();
    setTimeout(() => { if (!open) dialog.hidden = true; }, 220);
  };

  buyBtn.addEventListener('click', () => {
    if (open || gameState.freeSpinsRemaining > 0 || gameState.isSpinning || !gameState.sessionId) return;
    const bet = gameState.betSteps[gameState.betIndex];
    const price = bet * BUY_COST_MULTIPLIER;
    const affordable = price <= gameState.balance;
    document.getElementById('buySpins').textContent = BUY_SPINS;
    document.getElementById('buyPrice').textContent = formatPopupAmount(price);
    document.getElementById('buyCur').textContent = gameState.currency;
    document.getElementById('buyNote').hidden = affordable;
    confirmBtn.disabled = !affordable;
    open = true;
    Sound.playSfx('buyButton');
    pushScreenDim();
    dialog.hidden = false;
    void dialog.offsetWidth;
    dialog.classList.add('is-open');
    (affordable ? confirmBtn : document.getElementById('buyCancel')).focus({ preventScroll: true });
  });

  document.getElementById('buyCancel').addEventListener('click', () => close());
  confirmBtn.addEventListener('click', () => {
    if (confirmBtn.disabled) return;
    close(false);
    Sound.playSfx('buyConfirm');
    const betAmount = gameState.betSteps[gameState.betIndex];
    gameState.boughtBonus = true;
    runSpin(() => Api.buyFeature(gameState.sessionId, 'free_spins_buy', betAmount));
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
}

async function bootstrapSession() {
  try {
    const data = await Api.startSession(GAME_ID);
    gameState.sessionId = data.session_id;
    gameState.balance = data.balance;
    gameState.currency = data.currency;
    gameState.symbols = data.symbols || [];
    gameState.freeSpinsTrigger = data.free_spins_trigger || null;
    if (data.bet && data.bet.steps && data.bet.steps.length) {
      gameState.betSteps = data.bet.steps;
      const defaultIndex = gameState.betSteps.indexOf(data.bet.default);
      gameState.betIndex = defaultIndex >= 0 ? defaultIndex : Math.floor(gameState.betSteps.length / 2);
    }
    renderBet();
    renderBalance();
    renderInfoPopupContent();
  } catch (err) {
    // Leave the static placeholder values on screen rather than hard-failing
    // if the backend is unreachable.
    console.error('failed to start session, spin/buy will stay disabled:', err);
  }
}

// Every control of the bar has its own sound; anything not listed clicks.
const UI_SOUNDS = [
  ['[data-action="bet-plus"]', 'betPlus'],
  ['[data-action="bet-minus"]', 'betMinus'],
  ['#v3MenuBtn', 'menu'],
  ['#v3AutoBtn', 'autospin'],
  ['.v3-chip', 'autospin'],
  ['#v3TurboBtn', 'turbo'],
];

function setupClickSounds() {
  const claimed = new Set();
  for (const [sel, name] of UI_SOUNDS) {
    document.querySelectorAll(sel).forEach((btn) => {
      claimed.add(btn);
      btn.addEventListener('click', () => Sound.playSfx(name));
    });
  }
  document.querySelectorAll('.ui-icon-btn, .ui-spin-btn').forEach((btn) => {
    if (!claimed.has(btn)) btn.addEventListener('click', () => Sound.playSfx('click'));
  });
}

function setupSoundToggle() {
  document.querySelector('[data-action="sound"]').addEventListener('click', () => {
    Sound.toggleMuted();
  });
}

// Paytable info popup — server-authoritative (gameState.symbols, from
// session-start).
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  // The five multiplier faces a WILD can turn into, under the rules note.
  const mults = document.createElement('div');
  mults.className = 'info-popup__multipliers';
  mults.innerHTML = WILD_MULTIPLIERS.map((m) => `<img src="${symbolSrc('wild', m)}" alt="x${m}">`).join('');
  list.appendChild(mults);
  for (const symbol of gameState.symbols) {
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const payParts = ['3', '4', '5']
      .filter((count) => symbol.paytable[count] !== undefined)
      .map((count) => `<span>×${count}: <b>${formatNumber(symbol.paytable[count])}</b></span>`)
      .join('');
    row.innerHTML = `
      <img src="${symbolSrc(symbol.code)}" alt="${symbol.name}" onerror="this.remove()">
      <span class="info-popup__row-name">${symbol.name}</span>
      <span class="info-popup__row-pays">${payParts}</span>
    `;
    list.appendChild(row);
  }
}

function setupInfoPopup() {
  const popup = document.getElementById('infoPopup');
  document.querySelector('[data-action="info"]').addEventListener('click', () => {
    Sound.playSfx('popupOpen');
    popup.hidden = false;
  });
  document.getElementById('infoPopupClose').addEventListener('click', () => {
    Sound.playSfx('popupClose');
    popup.hidden = true;
  });
  popup.addEventListener('click', (event) => {
    if (event.target === popup) {
      Sound.playSfx('popupClose');
      popup.hidden = true;
    }
  });
}

setupBetStepper();
setupSpinButton();
setupBuyBonusButton();
setupClickSounds();
setupSoundToggle();
setupInfoPopup();
bootstrapSession();
