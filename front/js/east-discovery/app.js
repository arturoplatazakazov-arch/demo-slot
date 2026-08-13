// East Discovery — bottom UI bar + spin orchestration, adapted from
// ../app.js (Amy's Fruit Farm). Session bootstraps on load; every
// Spin/Buy click is a real request — no backend game exists for this GAME_ID
// yet (see the plan doc), so bootstrapSession's catch just leaves the static
// placeholder values on screen, same as Amy's Fruit Farm already tolerates
// when the backend is unreachable.

const GAME_ID = 'east-discovery';

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
  // Set right after a hold_and_win_buy purchase resolves — the round is
  // already fully computed server-side, but stays "pending" until the
  // player's next Spin click (product: first spin manual, the rest of the
  // respins auto-continue from there — see setupSpinButton).
  pendingHoldAndWin: null,
};

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

// sign_freespins_counter's number — the img/label pair is otherwise static art.
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
  // Whether this spin enters free spins from the base game — captured before
  // setFreeSpinsMode (below) flips the mode. Hold & Win never sets remaining>0,
  // so it never counts as entering here (and returns early before the switch).
  const enteringBonus = document.getElementById('screen').dataset.mode !== 'freespins' && remaining > 0;

  playWinCells(data.winning_cells, data.line_wins, data.count_wins);
  playCoinMultiplierReveal(data.coin_multiplier);
  playCollectorTigerWinIfApplied(data.coin_multiplier);

  if (data.hold_and_win && data.hold_and_win.triggered) {
    // Whether this came from a natural 3+ collector_tiger landing or the
    // dev panel's forced spin, the round is already fully resolved
    // server-side — transition to the bonus level with an empty grid and
    // wait for the player's next Spin click (product: first respin manual,
    // the rest auto-continue — see setupSpinButton/runHoldAndWinSequence).
    // No popup/win-amount for the triggering spin itself; Hold & Win's own
    // "Bonus Spins Total Win" popup covers the payout at the end.
    gameState.pendingHoldAndWin = data.hold_and_win;
    await enterHoldAndWinWaitingState();
    return;
  }

  // Free-spins (scatter) entry runs the intro (blackout + bonusSpinsWin popup +
  // reveal) inside setFreeSpinsMode; win cells above have already played.
  await setFreeSpinsMode(remaining > 0, remaining);
  if (remaining > 0) updateFreeSpinsCounter(remaining);

  if (data.popup) {
    // The entry's bonusSpinsWin is shown by the intro transition itself; a
    // re-trigger inside the bonus still shows its popup normally here.
    const shownByIntro = enteringBonus && data.popup.type === 'bonusSpinsWin';
    if (!shownByIntro) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount);
    }
    if (characterControllerRef) characterControllerRef.playEmotion('win');
  } else if (data.total_win > 0) {
    // Base wins (below the big/mega/epic threshold) never get a Spine
    // popup — show the amount inline over the grid instead.
    Sound.playSfx('smallWin');
    showInlineWinAmount(data.total_win);
    if (characterControllerRef) characterControllerRef.playEmotion('win');
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
      data.wild_events || [],
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
    if (gameState.pendingHoldAndWin) {
      const result = gameState.pendingHoldAndWin;
      gameState.pendingHoldAndWin = null;
      runHoldAndWin(result);
      return;
    }
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.spin(gameState.sessionId, betAmount));
  });
}

function setupBuyBonusButton() {
  const buyBtn = document.querySelector('.sign-buy-bonus');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', () => {
    if (gameState.freeSpinsRemaining > 0) return;
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.buyFeature(gameState.sessionId, 'free_spins_buy', betAmount));
  });
}

// Kicks off the (fully server-resolved) respin sequence — this is the
// "first spin" the player manually presses; every respin after the first
// auto-continues from inside runHoldAndWinSequence itself.
async function runHoldAndWin(result) {
  if (gameState.isSpinning) return;
  gameState.isSpinning = true;
  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  try {
    await runHoldAndWinSequence(result);
  } finally {
    spinBtn.classList.remove('is-spinning');
    gameState.isSpinning = false;
  }
}

// Dev-only: runs a real spin (one normal bet, not a 100x bonus-buy premium)
// via /dev/force-hold-and-win, which forces 3 collector_tiger onto an
// otherwise-real grid so Hold & Win triggers through its own normal
// is_triggered() path — same as a natural in-game trigger, just not left to
// chance. Reuses runSpin as-is: it lands the (rigged) grid showing the 3
// collectors first, same as a real trigger would, then applySpinResult
// notices hold_and_win.triggered and takes it from there.
function setupBuyHoldAndWinButton() {
  const btn = document.getElementById('devBuyHoldAndWin');
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
    // No east-discovery game exists on the backend yet — leave the static
    // placeholder values on screen (asset/animation preview still works)
    // rather than hard-failing.
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
// session-start); empty until a real east-discovery backend game exists.
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
      ${folder ? `<img src="img/east-discovery/Export/${folder}/static.png" alt="${symbol.name}">` : ''}
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
setupBuyHoldAndWinButton();
setupClickSounds();
setupSoundToggle();
setupInfoPopup();
bootstrapSession();
