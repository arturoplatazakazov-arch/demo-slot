// Neon Reels — bottom UI bar + spin orchestration. Session bootstraps on
// load; every Spin/Buy click is a real backend request. If no neon-reels
// backend game exists yet, bootstrapSession's catch just leaves the static
// placeholder values on screen — asset/animation preview (click a symbol,
// dev-panel popups) still works without a backend.

const GAME_ID = 'neon-reels';

const gameState = {
  sessionId: null,
  betSteps: [10000, 25000, 50000, 100000, 250000, 500000], // fallback if backend unreachable
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
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || isBuyDialogOpen()) return;
    gameState.betIndex = Math.max(0, gameState.betIndex - 1);
    renderBet();
  });
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || isBuyDialogOpen()) return;
    gameState.betIndex = Math.min(gameState.betSteps.length - 1, gameState.betIndex + 1);
    renderBet();
  });
}

function updateFreeSpinsCounter(remaining) {
  const el = document.getElementById('freeSpinsValue');
  if (el) el.textContent = remaining;
}

// Shared tail end of a spin/bonus-buy response: update balance/mode/counter,
// play whatever won, show a popup if the server sent one.
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
  playCoinMultiplierReveal(data.coin_multiplier);

  await setFreeSpinsMode(remaining > 0, remaining);
  if (remaining > 0) updateFreeSpinsCounter(remaining);

  if (data.popup) {
    // The entry's bonusSpinsWin is shown by the intro transition itself; a
    // re-trigger inside the bonus still shows its popup normally here.
    // buyFreeSpins is the confirm card the purchase already went through.
    const shownByIntro =
      (enteringBonus && data.popup.type === 'bonusSpinsWin') || data.popup.type === 'buyFreeSpins';
    if (!shownByIntro) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount);
    }
  } else if (data.total_win > 0) {
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
    await landReels(
      data.grid,
      anticipationColumns,
      data.coin_multiplier || null,
      data.line_wins || [],
      data.count_wins || [],
    );
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
    if (isBuyDialogOpen()) return;
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.spin(gameState.sessionId, betAmount));
  });
}

// free_spins_buy product of the bonus_buy row in app/seed/neon_reels.py:
// cost_multiplier 100, awards the free_spins fallback of 10 spins.
const BUY_BONUS_COST_MULTIPLIER = 100;
const BUY_BONUS_SPINS = 10;

function setupBuyBonusButton() {
  const buyBtn = document.querySelector('.sign-buy-bonus');
  if (!buyBtn) return;
  buyBtn.style.cursor = 'pointer';
  buyBtn.addEventListener('click', async () => {
    // Base game only, nothing else on screen.
    if (!gameState.sessionId || gameState.isSpinning || gameState.freeSpinsRemaining > 0) return;
    if (document.getElementById('screen').dataset.mode !== 'base' || isScreenBusy()) return;

    // A buy costs bet x 100; when the current bet can't be covered, quote the
    // highest bet step the balance still can (the bet switches to it on ✓).
    const currentBet = gameState.betSteps[gameState.betIndex];
    const q = BuyBonus.quote({
      betSteps: gameState.betSteps,
      betIndex: gameState.betIndex,
      balance: gameState.balance,
      multiplier: BUY_BONUS_COST_MULTIPLIER,
    });
    const confirmed = await showBuyBonusDialog({
      price: `${formatNumber(q.cost)} ${gameState.currency}`,
      spins: BUY_BONUS_SPINS,
      note: q.lowered ? `BET ${formatNumber(currentBet)} → ${formatNumber(q.bet)}` : '',
      affordable: q.affordable,
    });
    if (!confirmed || !q.affordable) return;
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0) return;
    if (q.lowered) {
      gameState.betIndex = q.betIndex;
      renderBet();
    }
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
    // No neon-reels backend game yet — leave the placeholder values on
    // screen (asset/animation preview still works) rather than hard-failing.
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
// session-start); empty until a real neon-reels backend game exists.
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const folder = SYMBOL_FOLDERS[symbol.code];
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const payParts = ['3', '4', '5']
      .filter((count) => symbol.paytable[count] !== undefined)
      .map((count) => `<span>×${count}: <b>${formatNumber(symbol.paytable[count])}</b></span>`)
      .join('');
    row.innerHTML = `
      ${folder ? `<img src="img/neon-reels/Export/${folder}/static.png" alt="${symbol.name}">` : ''}
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
