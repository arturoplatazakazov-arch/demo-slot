// Lucky Joker — bottom UI bar + spin orchestration, adapted from
// ../multi-fruits-story/app.js (the other 3x3 game) with ../east-discovery's
// Hold & Win branch grafted in. The session bootstraps on load and every
// Spin/Buy click is a real request against app/seed/lucky_joker_3h3.py's
// config.

const GAME_ID = 'lucky-joker-3h3';

const gameState = {
  sessionId: null,
  // Fallback if the backend is unreachable — mirrors the seed's BET_STEPS,
  // which are multiples of 5 so the 5 paylines split them evenly.
  betSteps: [10000, 25000, 50000, 100000, 250000, 500000],
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  freeSpinsRemaining: 0,
  lastGrid: null,
  symbols: [],
  freeSpinsTrigger: null,
  // Set when a spin (or the dev button) triggers Hold & Win: the round is
  // already fully computed server-side, but stays "pending" until the player's
  // next Spin click — first respin manual, the rest auto-continue from inside
  // runHoldAndWinSequence (same shape as east-discovery).
  pendingHoldAndWin: null,
  pendingHoldAndWinLocked: null,
  // The triggering spin's coin values, kept alongside lastGrid so the base
  // reels can be restored exactly as they were when the round ends.
  pendingHoldAndWinCoins: null,
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

// The number on the free-spins plate — the plate itself is static art.
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
  // setFreeSpinsMode flips the mode.
  const enteringBonus = document.getElementById('screen').dataset.mode !== 'freespins' && remaining > 0;

  // Coin values are already on screen — they were baked into the reel strip
  // before it dropped (see landReels/resolveDrawnGrid), so a coin arrives
  // carrying its multiplier instead of having the number appear afterwards.
  playWinCells(data.winning_cells, data.line_wins, data.count_wins);
  if ((data.count_wins || []).length > 0) Sound.playSfx('scatterWin');
  if (data.coin_multiplier && data.coin_multiplier.applied) Sound.playSfx('coinLand');

  if (data.hold_and_win && data.hold_and_win.triggered) {
    // The round is already resolved server-side — switch to the bonus level
    // with the triggering coins locked in place and wait for the player's next
    // Spin click. No popup or win amount for the triggering spin itself; Hold
    // & Win's own total-win popup covers the payout at the end.
    gameState.pendingHoldAndWin = data.hold_and_win;
    // Kept so the base reels can be restored complete when the round ends —
    // grid AND the coin values that were showing on it.
    gameState.pendingHoldAndWinCoins = data.coin_multiplier;
    gameState.pendingHoldAndWinLocked = await enterHoldAndWinWaitingState(data.hold_and_win);
    return;
  }

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
    // Wins below the big/mega/epic threshold never get a Spine popup — show
    // the amount inline over the grid instead.
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
    // 3 reels: this flags the last one when the first two already carry 2 of
    // the 3 scatters the round needs.
    const anticipationColumns = gameState.freeSpinsTrigger
      ? ReelMath.collectAnticipationColumns(
          data.grid, GRID_COLS, GRID_ROWS,
          gameState.freeSpinsTrigger.trigger_symbol_code, gameState.freeSpinsTrigger.trigger_count,
        )
      : [];
    // The coin values go in with the grid: the strip is built with each coin's
    // multiplier already attached, so it falls with the number on it.
    await landReels(data.grid, anticipationColumns, data.coin_multiplier);
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
    if (gameState.pendingHoldAndWin) {
      const result = gameState.pendingHoldAndWin;
      const locked = gameState.pendingHoldAndWinLocked;
      gameState.pendingHoldAndWin = null;
      gameState.pendingHoldAndWinLocked = null;
      runHoldAndWin(result, locked);
      return;
    }
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.spin(gameState.sessionId, betAmount));
  });
}

// Kicks off the (fully server-resolved) respin sequence — this is the "first
// spin" the player manually presses; every respin after the first
// auto-continues from inside runHoldAndWinSequence itself. The balance already
// includes the payout (it landed with the triggering spin's response), so
// nothing is settled here.
async function runHoldAndWin(result, locked) {
  if (gameState.isSpinning) return;
  gameState.isSpinning = true;
  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  try {
    // lastGrid is the triggering spin's own grid — the round hands it (and the
    // coin values that were on it) back on the way out, so the base reels
    // aren't left holding the round's coins and empty cells.
    await runHoldAndWinSequence(result, locked, gameState.lastGrid, gameState.pendingHoldAndWinCoins);
  } finally {
    spinBtn.classList.remove('is-spinning');
    gameState.isSpinning = false;
  }
}

// Cost multiplier of the bonus_buy product in app/seed/lucky_joker_3h3.py —
// used only to show the price in the confirmation dialog; the server charges
// its own configured cost regardless of what's displayed here.
const BUY_BONUS_COST_MULTIPLIER = 20;

function setupBuyBonusButton() {
  const buyBtn = document.querySelector('.sign-buy-bonus');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', async () => {
    if (gameState.isSpinning || gameState.freeSpinsRemaining > 0 || gameState.pendingHoldAndWin) return;
    // The delivered popup art is a ✓/✗ dialog with its own bet stepper, so the
    // sign opens it and the purchase only fires on ✓ (slot.js
    // showBuyBonusDialog). Whatever bet the player stepped to in there is the
    // bet the purchase is made at.
    const { confirmed, betIndex } = await showBuyBonusDialog({
      betSteps: gameState.betSteps,
      betIndex: gameState.betIndex,
      costMultiplier: BUY_BONUS_COST_MULTIPLIER,
    });
    gameState.betIndex = betIndex;
    renderBet();
    if (!confirmed) return;
    // buy_id matches the bonus_buy product in app/seed/lucky_joker_3h3.py.
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.buyFeature(gameState.sessionId, 'free_spins_buy', betAmount));
  });
}

// Dev-only: runs a real spin (one normal bet, not a bonus-buy premium) via
// /dev/force-hold-and-win, which forces this game's own trigger count of coins
// onto an otherwise-real grid so Hold & Win fires through its normal
// is_triggered() path. Reuses runSpin as-is: it lands the (rigged) grid
// showing the coins first, same as a real trigger would, then applySpinResult
// notices hold_and_win.triggered and takes it from there.
function setupDevHoldAndWinButton() {
  const btn = document.getElementById('devHoldAndWin');
  if (!btn) return;
  btn.addEventListener('click', () => {
    if (gameState.pendingHoldAndWin || gameState.freeSpinsRemaining > 0) return;
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.devForceHoldAndWin(gameState.sessionId, betAmount));
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
// game only ever pays for 3 in a line, so there's a single column of numbers;
// COIN has no paytable of its own (it pays through Hold & Win), so it gets a
// note instead of an empty row.
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
      : '<span>множитель линии / Hold &amp; Win</span>';
    row.innerHTML = `
      ${folder ? `<img src="img/lucky-joker-3h3/${folder}/static.png" alt="${symbol.name}">` : ''}
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
setupDevHoldAndWinButton();
setupClickSounds();
setupSoundToggle();
setupInfoPopup();
bootstrapSession();
