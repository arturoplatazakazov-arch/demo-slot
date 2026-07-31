// Sugar Galaxy — bottom UI bar + spin orchestration, adapted from
// ../party-of-goods/app.js (itself from ../east-discovery/app.js) (same GAME_ID/session/Api conventions), trimmed
// to this game's own features: avalanche cascades (slot.js:playAvalanche)
// instead of a spinning reel, free_spins + bonus_buy only (no
// hold_and_win/coin_multiplier/expanding_wild — this game has no such
// FeatureConfig rows, see app/seed/sugar_galaxy.py).

const GAME_ID = 'sugar-galaxy';

const gameState = {
  sessionId: null,
  betSteps: [10000, 25000, 50000, 100000, 250000, 500000], // fallback if the backend is unreachable
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  freeSpinsRemaining: 0,
  lastGrid: null,
  symbols: [], // paytable info for the info popup — from session-start's `symbols`
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

function updateFreeSpinsCounter(remaining) {
  const el = document.getElementById('freeSpinsValue');
  if (el) el.textContent = remaining;
}

// Shared tail end of both a normal spin and a bonus-buy response, called
// *after* slot.js:playAvalanche has already animated every cascade step —
// updates balance/free-spins mode, then shows whatever popup/inline amount
// the server sent.
async function applySpinResult(data, totalWinFromCascades) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  const remaining = data.feature && data.feature.type === 'free_spins' ? data.feature.spins_remaining : 0;
  gameState.freeSpinsRemaining = remaining;

  // Product, this session: every winning combination's own cascade
  // animation (already finished — playAvalanche ran before applySpinResult
  // was ever called) must fully play out, THEN the scatters' own win
  // celebration, and only THEN the transition into bonus mode — never
  // simultaneously. Covers both a trigger from the initial grid and one
  // where the 3rd+ scatter only showed up via a cascade's own refill
  // (playScatterTriggerCelebration scans whatever's on screen right now,
  // which already reflects the final post-cascade grid either way).
  if (data.feature && data.feature.triggered) {
    await playScatterTriggerCelebration();
  }

  // Entering the bonus from the base game: setFreeSpinsMode runs the full
  // intro (blackout + bonusSpinsWin popup + reveal), so the popup block below
  // must not play that same popup a second time. A re-trigger *inside* the
  // bonus still shows its own bonusSpinsWin popup normally (mode is already
  // 'freespins' by then, so enteringBonus is false).
  const enteringBonus = document.getElementById('screen').dataset.mode !== 'freespins' && remaining > 0;
  await setFreeSpinsMode(remaining > 0, remaining);
  if (remaining > 0) {
    updateFreeSpinsCounter(remaining);
    // Session-wide accumulator (see spin_service.py's _run_avalanche_spin) —
    // set once here per spin; NOT the same number as the base game's
    // per-step multiplier this same spin's own cascade already showed.
    if (data.feature.multiplier != null) updateMultiCounter(data.feature.multiplier);
  }

  if (data.popup) {
    const shownByIntro = enteringBonus && data.popup.type === 'bonusSpinsWin';
    if (!shownByIntro) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      await playPopup(data.popup.type, data.popup.amount);
    }
  } else if (totalWinFromCascades > 0) {
    // Wins below the big/mega/epic threshold never get a Spine popup — show
    // the amount inline over the grid instead (same convention as East
    // Discovery's base-game wins). No sound here: WIN_Small already fired per
    // winning combination during the cascade (see slot.js celebrateStep).
    showInlineWinAmount(totalWinFromCascades);
  }
}

async function runSpin(request) {
  if (gameState.isSpinning || !gameState.sessionId) return;
  gameState.isSpinning = true;

  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');

  // SPIN_Start fires 0.1s after this press (product) — independent of network
  // latency. The Element_drop patter fires later, from spinStartTransition
  // when the grid lands.
  startSpinPressCue();

  try {
    const data = await request();
    const totalWin = await playAvalanche(data);
    await applySpinResult(data, totalWin);
  } catch (err) {
    console.error('spin failed:', err);
    if (gameState.lastGrid) renderInitialGrid(gameState.lastGrid);
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
  const buyBtn = document.querySelector('.sign-buy-bonus');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', () => {
    if (gameState.freeSpinsRemaining > 0) return;
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
    if (data.bet && data.bet.steps && data.bet.steps.length) {
      gameState.betSteps = data.bet.steps;
      const defaultIndex = gameState.betSteps.indexOf(data.bet.default);
      gameState.betIndex = defaultIndex >= 0 ? defaultIndex : Math.floor(gameState.betSteps.length / 2);
    }
    renderBet();
    renderBalance();
    renderInfoPopupContent();
  } catch (err) {
    // No backend reachable — leave the static placeholder values on screen
    // (asset/animation preview via the dev panel still works).
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
// session-start). Avalanche paytables are open-ended tiers ("8+", "10+",
// ...) rather than the other games' exact 3/4/5 counts, so every key in
// `paytable` is shown, sorted ascending, instead of a hardcoded [3,4,5].
// Multiplier tokens (x2/x3/x5/x7) and scatter carry an empty paytable and
// are skipped here — their role is explained in the note above the list
// (see the .info-popup__note markup in party-of-goods.html).
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const folder = SYMBOL_FOLDERS[symbol.code];
    // Skip symbols that aren't part of this game's real art set — an aborted
    // builder pass left zero-weight placeholder rows (high_a/low_a/boom) in
    // the config (see app/seed/sugar_galaxy.py); they never draw, and have no
    // SYMBOL_FOLDERS entry, so keep them out of the paytable too.
    if (!folder) continue;
    const counts = Object.keys(symbol.paytable).sort((a, b) => Number(a) - Number(b));
    if (counts.length === 0) continue;
    const payParts = counts
      .map((count) => `<span>${count}+: <b>${formatNumber(symbol.paytable[count])}</b></span>`)
      .join('');
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    row.innerHTML = `
      ${folder ? `<img src="img/sugar-galaxy/Export/${folder}/static.png" alt="${symbol.name}">` : ''}
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
