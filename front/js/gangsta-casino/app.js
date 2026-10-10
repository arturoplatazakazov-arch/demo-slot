// Gangsta Casino — bottom UI bar + spin orchestration, adapted from
// ../dirty-money-mafia/app.js (same mechanic set: line pay + scatter free
// spins + expanding/walking wild + wheel of fortune + bonus buy). The session
// Spin/Buy click is a real request against app/seed/gangsta_casino.py's
// config.

const GAME_ID = 'gangsta-casino';

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

const WIN_TIER_SOUNDS = { bigWin: 'bigWin', epicWin: 'epicWin', megaWin: 'megaWin' };

function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

// Bonus buy costs 100x the bet (cost_multiplier in the seed) — the price on
// the chest follows the current bet.
const BUY_COST_MULTIPLIER = 100;

function renderBet() {
  const bet = gameState.betSteps[gameState.betIndex];
  document.getElementById('betValue').textContent = formatNumber(bet);
  const priceEl = document.getElementById('buyBonusPrice');
  if (priceEl) priceEl.textContent = formatNumber(bet * BUY_COST_MULTIPLIER);
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

function updateFreeSpinsCounter(remaining) {
  setFreeSpinsCounter(remaining);
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

  // Wheel of Fortune runs BEFORE the bonus-mode switch: when its prize is the
  // free-spins round, the server has already added those spins to `feature`,
  // so the wheel has to play out first and the usual blackout + intro popup
  // then carries the player into the bonus.
  if (data.wheel_of_fortune) {
    await celebrateWheelTrigger();
    await playWheelOfFortune(data.wheel_of_fortune);
  }

  if (remaining > 0) updateFreeSpinsCounter(remaining);
  await setFreeSpinsMode(remaining > 0, remaining);

  if (data.popup) {
    // The entry's bonusSpinsWin is shown by the intro transition itself; a
    // re-trigger inside the bonus still shows its popup normally here.
    const shownByIntro = enteringBonus && data.popup.type === 'bonusSpinsWin';
    // buyFreeSpins: the purchase was already confirmed in our own ✓/✗ dialog
    // — replaying a card for it after the fact would just repeat it.
    if (!shownByIntro && data.popup.type !== 'buyFreeSpins') {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount);
    }
  } else if (data.total_win > 0) {
    // Wins below the big/mega/epic threshold never get a popup — show the
    // amount inline over the grid instead.
    Sound.playSfx('smallWin');
    showInlineWinAmount(data.total_win);
  }
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

function setupBuyBonusButton() {
  const buyBtn = document.getElementById('buyBonusBtn');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', async () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || !gameState.sessionId) return;
    const betAmount = gameState.betSteps[gameState.betIndex];
    const confirmed = await openBuyDialog(betAmount * BUY_COST_MULTIPLIER);
    if (!confirmed) return;
    // buy_id matches the bonus_buy product in app/seed/gangsta_casino.py.
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
    // Backend unreachable — leave the static placeholder values on screen
    // rather than hard-failing (asset/animation preview still works).
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
// session-start); thumbnails reuse each symbol's own resting tile.
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const art = SYMBOL_ART[symbol.code];
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const payParts = ['3', '4', '5']
      .filter((count) => symbol.paytable[count] !== undefined)
      .map((count) => `<span>×${count}: <b>${formatNumber(symbol.paytable[count])}</b></span>`)
      .join('');
    row.innerHTML = `
      ${art ? `<img src="${symbolSrc(symbol.code)}" alt="${symbol.name}">` : ''}
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
