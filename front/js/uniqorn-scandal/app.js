// Uniqorn Scandal — bottom UI bar + spin orchestration, adapted from
// ../mr-president-unicorn/app.js. Session bootstraps on load; every Spin/Buy
// click is a real request.
const GAME_ID = 'uniqorn-scandal';

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
};

// Buy Bonus: the price is bet × BUY_BONUS_COST_MULTIPLIER and the buy awards
// BUY_BONUS_SPINS free spins — both from the bonus_buy / free_spins features
// in app/seed/uniqorn_scandal.py. Keep them in sync with the seed.
const BUY_BONUS_COST_MULTIPLIER = 100;
const BUY_BONUS_SPINS = 10;

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
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || buyDialogOpen) return;
    gameState.betIndex = Math.max(0, gameState.betIndex - 1);
    renderBet();
  });
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || buyDialogOpen) return;
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

  await setFreeSpinsMode(remaining > 0, remaining);
  if (remaining > 0) updateFreeSpinsCounter(remaining);

  if (data.popup) {
    // The entry's bonusSpinsWin is shown by the intro transition itself; a
    // re-trigger inside the bonus still shows its popup normally here.
    const shownByIntro = enteringBonus && data.popup.type === 'bonusSpinsWin';
    // buyFreeSpins = receipt for a purchase the player already confirmed in
    // the Buy Bonus dialog — never replay it.
    const alreadyConfirmed = data.popup.type === 'buyFreeSpins';
    if (!shownByIntro && !alreadyConfirmed) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount);
    }
  } else if (data.total_win > 0) {
    // Base wins (below the big/mega/epic threshold) never get a Spine popup —
    // show the amount inline over the grid instead.
    Sound.playSfx('smallWin');
    showInlineWinAmount(data.total_win);
  }
}

async function runSpin(request) {
  if (gameState.isSpinning || !gameState.sessionId || buyDialogOpen) return;
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
    await landReels(data.grid, anticipationColumns, data.wild_events || [], data.line_wins || [], data.count_wins || []);
    await applySpinResult(data);
  } catch (err) {
    console.error('spin failed:', err);
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

// The sign opens the confirm dialog (slot.js:openBuyBonusDialog); only BUY
// spends. js/buy-bonus.js prices it: at the default bet the 100× buy is beyond
// the starting balance, so the dialog quotes the highest bet step the balance
// covers and the bet is switched to that step before buying.
function canOpenBuyBonus() {
  return (
    gameState.sessionId &&
    !gameState.isSpinning &&
    gameState.freeSpinsRemaining === 0 &&
    document.getElementById('screen').dataset.mode !== 'freespins' &&
    !buyDialogOpen &&
    dimActiveCount === 0 &&
    !document.querySelector('.game-popup, .info-popup:not([hidden]), .wof:not([hidden])')
  );
}

function setupBuyBonusButton() {
  const buyBtn = document.querySelector('.sign-buy-bonus');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', async () => {
    if (!canOpenBuyBonus()) return;
    const prevBet = gameState.betSteps[gameState.betIndex];
    const quote = BuyBonus.quote({
      betSteps: gameState.betSteps,
      betIndex: gameState.betIndex,
      balance: gameState.balance,
      multiplier: BUY_BONUS_COST_MULTIPLIER,
    });
    const confirmed = await openBuyBonusDialog({
      spins: BUY_BONUS_SPINS,
      quote,
      prevBet,
      currency: gameState.currency,
    });
    if (!confirmed || !quote.affordable) return;
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || buyDialogOpen) return;
    if (quote.betIndex !== gameState.betIndex) {
      gameState.betIndex = quote.betIndex;
      renderBet();
    }
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.buyFeature(gameState.sessionId, 'free_spins_buy', betAmount));
  });
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

function setupClickSounds() {
  document.querySelectorAll('.ui-icon-btn, .ui-spin-btn').forEach((btn) => {
    btn.addEventListener('click', () => Sound.playSfx('click'));
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
