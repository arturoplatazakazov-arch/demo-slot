// Multi Fruits Story — bottom UI bar + spin orchestration, adapted from
// ../dirty-money-mafia/app.js with its expanding-wild and wheel-of-fortune
// branches dropped (this game's mechanic set is line pay + scatter free spins +
// bonus buy). The session bootstraps on load and every Spin/Buy click is a real
// request against app/seed/multi_fruits_story.py's config.

const GAME_ID = 'multi-fruits-story';

const gameState = {
  sessionId: null,
  // Fallback if the backend is unreachable — mirrors the seed's BET_STEPS,
  // which are multiples of 3 so the 3 paylines split them evenly.
  betSteps: [12000, 30000, 60000, 120000, 300000, 600000],
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

// The number on bonus_spins_counter.png — the plate itself is static art.
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
  if ((data.count_wins || []).length > 0) Sound.playSfx('scatterWin');

  await setFreeSpinsMode(remaining > 0, remaining);
  updateFreeSpinsCounter(remaining);

  if (data.popup) {
    // Two popups the client has already shown by the time the response lands:
    // the entry's bonusSpinsWin (played by the intro transition — a re-trigger
    // INSIDE the bonus still shows its popup normally here), and buyFreeSpins
    // (the confirmation dialog the purchase went through in the first place).
    const shownByIntro =
      (enteringBonus && data.popup.type === 'bonusSpinsWin') || data.popup.type === 'buyFreeSpins';
    if (!shownByIntro) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type] || (data.popup.type === 'bonusSpinsTotalWin' ? 'bonusTotalWin' : null);
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount);
    }
  } else if (data.total_win > 0) {
    // Wins below the big/mega/epic threshold never get a Spine popup — show the
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
    // Hand the per-wild multipliers over BEFORE the reels land: each wild cell
    // reads its own the moment it's built, so it can pick the Spine skin and
    // play the reveal as its reel settles (slot.js setCellSymbol).
    setWildMultipliers(data.multiplier_wilds);
    // 3 reels: this flags the last one when the first two already carry 2 of
    // the 3 scatters the round needs.
    const anticipationColumns = gameState.freeSpinsTrigger
      ? ReelMath.collectAnticipationColumns(
          data.grid, GRID_COLS, GRID_ROWS,
          gameState.freeSpinsTrigger.trigger_symbol_code, gameState.freeSpinsTrigger.trigger_count,
        )
      : [];
    await landReels(data.grid, anticipationColumns);
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

// Cost multiplier of the bonus_buy product in app/seed/multi_fruits_story.py —
// used only to show the price in the confirmation dialog; the server charges
// its own configured cost regardless of what's displayed here.
const BUY_BONUS_COST_MULTIPLIER = 20;

function setupBuyBonusButton() {
  const buyBtn = document.querySelector('.sign-buy-bonus');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', async () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0) return;
    const betAmount = gameState.betSteps[gameState.betIndex];
    // The delivered popup art is a ✓/✗ dialog, so the sign opens it and the
    // purchase only fires on ✓ (see slot.js showBuyBonusDialog).
    const confirmed = await showBuyBonusDialog(betAmount * BUY_BONUS_COST_MULTIPLIER);
    if (!confirmed) return;
    // buy_id matches the bonus_buy product in app/seed/multi_fruits_story.py.
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
// session-start); thumbnails reuse each symbol's own resting tile. A 3-reel
// game only ever pays for 3 in a line, so there's a single column of numbers.
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const folder = SYMBOL_FOLDERS[symbol.code];
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const payParts = symbol.paytable['3'] !== undefined
      ? `<span>×3: <b>${formatNumber(symbol.paytable['3'])}</b></span>`
      : '';
    row.innerHTML = `
      ${folder ? `<img src="img/multi-fruits-story/${folder}/static.png" alt="${symbol.name}">` : ''}
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
