// Gangsta Casino — bottom UI bar + spin orchestration, adapted from
// ../dirty-money-mafia/app.js (same mechanic set: line pay + scatter free
// spins + expanding/walking wild + multipliers + bonus buy). The session
// Spin/Buy click is a real request against app/seed/gangsta_casino.py's
// config.

const GAME_ID = 'gangsta-casino';

const gameState = {
  sessionId: null,
  betSteps: [5500, 13750, 27500, 55000, 137500, 275000], // fallback if the backend is unreachable
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

// Bonus buy costs 86x the bet (BUY_COST_MULTIPLIER in the seed) — the price on
// the chest follows the current bet.
const BUY_COST_MULTIPLIER = 86;

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
  const wasInRound = document.getElementById('screen').dataset.mode === 'freespins';
  const enteringBonus = !wasInRound && remaining > 0;

  // Multipliers flip in on their chips first (and fly into the plate when
  // they count), then the wins play — total_win already includes them.
  await playMultipliers(data.coin_multiplier, wasInRound);
  playWinCells(data.winning_cells, data.line_wins, data.count_wins);

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
  if (currentMode() !== 'freespins') resetMultiplierPlate();
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
    // Base game only, and never over another popup / transition (screen dim),
    // the wheel, the Spine preview screens or an already open dialog.
    const shown = (id) => { const el = document.getElementById(id); return el && !el.hidden; };
    if (currentMode() !== 'base' || document.getElementById('screenDim').classList.contains('is-active')) return;
    if (shown('buyDialog') || shown('featureScreen')) return;
    // Price at the current bet when the balance covers it, else at the
    // highest bet step it does (js/buy-bonus.js).
    const q = BuyBonus.quote({
      betSteps: gameState.betSteps,
      betIndex: gameState.betIndex,
      balance: gameState.balance,
      multiplier: BUY_COST_MULTIPLIER,
    });
    const confirmed = await openBuyDialog(q.cost, {
      affordable: q.affordable,
      note: q.lowered ? `BET ${formatNumber(gameState.betSteps[gameState.betIndex])} → ${formatNumber(q.bet)}` : '',
    });
    if (!confirmed || !q.affordable) return;
    gameState.betIndex = q.betIndex;
    renderBet();
    // buy_id matches the bonus_buy product in app/seed/gangsta_casino.py.
    runSpin(() => Api.buyFeature(gameState.sessionId, 'free_spins_buy', q.bet));
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
