// Neon Joker Spins — нижний бар и оркестрация спина. Каркас — ../tesla-spins/app.js
// (турбо и автоспины поверх общего бара V3 через MutationObserver). Своё:
//
// - Free Spins: 3+ Джокера -> смех Джокеров, заставка FREE SPINS (тап —
//   пропуск), фон и панель раунда; спины раунда идут сами; ретриггер «+5»;
//   в конце — TOTAL WIN. Ставка раунда заперта на сервере.
// - Hold & Win (база и внутри FS): сервер решает раунд целиком, slot.js его
//   проигрывает; если в одном спине и FS, и H&W — сначала H&W (GDD §6.1).
// - Buy Hold & Win: окно с ценой -> /feature/buy -> тот же путь проигрывания.
// - Обрыв: на старте сессии /session/<id>/state, активные FS продолжаются.

const GAME_ID = 'neon-joker-spins';
const BUY_ID = 'hold_and_win_buy';
// Зеркалит BONUS_BUY_COST_MULTIPLIER сида — только для цены на кнопке.
const BUY_COST_MULTIPLIER = 34.5;

const gameState = {
  sessionId: null,
  betSteps: [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000],
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  autoSpinsLeft: 0,
  lastGrid: null,
  symbols: [],
  inFreeSpins: false,
  fsLeft: 0,
  fsBet: null,
};

function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

function currentBet() {
  return gameState.inFreeSpins && gameState.fsBet ? gameState.fsBet : gameState.betSteps[gameState.betIndex];
}

function renderBet() {
  const bet = currentBet();
  document.getElementById('betValue').textContent = formatNumber(bet);
  const mirror = document.getElementById('v3BetMirror');
  if (mirror) mirror.textContent = formatNumber(bet);
  window.__currentBet = bet;
  updateJackpotPlates(bet);
  setGlyphs(document.getElementById('buyPrice'), formatNumber(bet * BUY_COST_MULTIPLIER));
}

function renderBalance() {
  document.getElementById('balanceValue').textContent = formatNumber(gameState.balance);
  document.querySelectorAll('.ui-balance__currency, .ui-bet-field__currency, .v3-readout__cur')
    .forEach((el) => { el.textContent = gameState.currency; });
}

function setupBetStepper() {
  const step = (d) => {
    if (gameState.isSpinning || gameState.inFreeSpins) return;
    gameState.betIndex = Math.max(0, Math.min(gameState.betSteps.length - 1, gameState.betIndex + d));
    renderBet();
  };
  document.querySelector('[data-action="bet-minus"]').addEventListener('click', () => step(-1));
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => step(1));
}

// Попап за выигрыш — по отношению к ставке (на 3x3 линия всегда длины 3).
const POPUP_TIER_BY_RATIO = [[100, 'epicWin'], [30, 'megaWin'], [10, 'bigWin']];
function popupForWin(totalWin, bet) {
  const ratio = bet > 0 ? totalWin / bet : 0;
  for (const [threshold, type] of POPUP_TIER_BY_RATIO) if (ratio >= threshold) return type;
  return null;
}
const WIN_SOUND = { bigWin: 'bigWin', megaWin: 'megaWin', epicWin: 'epicWin' };

function setBusyUi(busy) {
  document.querySelector('[data-action="spin"]').classList.toggle('is-spinning', busy);
  document.getElementById('buyBtn').disabled = busy;
  // lights off while hidden in a feature too (CSS fades the button there)
  const ns = window.NeonFx;
  if (ns && ns.ready) ns.buyState(!busy && !gameState.inFreeSpins);
}

// --- Free Spins ---------------------------------------------------------------

function enterFreeSpins(spins, bet) {
  gameState.inFreeSpins = true;
  gameState.fsLeft = spins;
  gameState.fsBet = bet;
  setFreeSpinsMode(true);
  updateFreeSpinsPanel(spins, 0);
  renderBet();
}

async function leaveFreeSpins(total, maxWin) {
  gameState.inFreeSpins = false;
  gameState.fsLeft = 0;
  await playPopup('totalWin', total, 3200, maxWin ? { sub: 'MAX WIN 2 500×' } : {});
  setFreeSpinsMode(false);
  gameState.fsBet = null;
  renderBet();
}

// --- Спин ---------------------------------------------------------------------

async function presentResult(data, bet) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;

  const hw = data.hold_and_win && data.hold_and_win.triggered ? data.hold_and_win : null;
  const fs = data.feature && data.feature.type === 'free_spins' ? data.feature : null;
  const wasInFs = gameState.inFreeSpins;
  const fsTriggeredNow = fs && fs.triggered && !wasInFs;
  const retrigger = fs && fs.triggered && wasInFs;

  const lineWin = (data.line_wins || []).length || (data.count_wins || []).length;
  if (lineWin) playWinCells(data.winning_cells, data.line_wins, data.count_wins);

  // 1. Hold & Win — всегда первым.
  if (hw) {
    if (lineWin) await new Promise((r) => setTimeout(r, 1500));
    const hwTotal = await playHoldAndWin(hw, bet);
    await playPopup('totalWin', hw.total_win, 2600, hw.collector_total ? { sub: `COLLECTOR ${hw.collector_total}×` } : {});
    exitHoldAndWinMode();
    // Поле раунда (монеты + пустые ячейки) уходит — возвращаем сетку спина.
    await applyGrid(data.grid);
    void hwTotal;
  }

  // 2. Free Spins: вход / ретриггер / счётчик / выход.
  if (fsTriggeredNow) {
    await celebrateScatters();
    await playPopup('freeSpins', 0, 2000, { panelText: String(fs.spins_awarded || fs.spins_remaining) });
    enterFreeSpins(fs.spins_remaining, bet);
  } else if (retrigger) {
    await celebrateScatters();
    flashRetrigger(fs.spins_awarded || 5);
  }

  if (wasInFs && fs) {
    gameState.fsLeft = fs.spins_remaining;
    updateFreeSpinsPanel(fs.spins_remaining, fs.total_win);
  }

  // 3. Выигрыш спина (без раунда H&W — его итог уже показан). Герой
  // реагирует: обычный выигрыш — `win`, крупный — радость в попапе,
  // антиципация без выигрыша — «эх!» (near_miss).
  if (!hw && !fsTriggeredNow && data.total_win > 0) {
    const type = popupForWin(data.total_win, bet);
    if (type) {
      Sound.playSfx(WIN_SOUND[type]);
      await playPopup(type, data.total_win);
    } else {
      Sound.playSfx('smallWin');
      showInlineWinAmount(data.total_win);
      mascotCheer('win');
    }
  } else if (!hw && !fs && window.__lastAnticipated) {
    mascotCheer('near_miss');
  }

  renderBalance();

  if (wasInFs && fs && (fs.spins_remaining === 0 || data.max_win_reached)) {
    await new Promise((r) => setTimeout(r, 600));
    await leaveFreeSpins(fs.total_win, data.max_win_reached);
  } else if (data.max_win_reached && !wasInFs) {
    await playPopup('totalWin', data.total_win, 2600, { sub: 'MAX WIN 2 500×' });
  }
}

async function runSpin(request, bet, { anticipate = true } = {}) {
  if (gameState.isSpinning || !gameState.sessionId) return;
  gameState.isSpinning = true;
  setBusyUi(true);
  startReelLoop();
  try {
    const data = await request();
    await landReels(data.grid, { anticipate });
    await presentResult(data, bet);
  } catch (err) {
    console.error('spin failed:', err);
    stopAutoSpins();
    stopReelLoop();
    exitHoldAndWinMode();
    if (gameState.lastGrid) await applyGrid(gameState.lastGrid);
  } finally {
    gameState.isSpinning = false;
    setBusyUi(false);
    scheduleNextSpin();
  }
}

function spinOnce() {
  const bet = currentBet();
  runSpin(() => Api.spin(gameState.sessionId, bet), bet);
}

// Фриспины крутятся сами; вне раунда — автоигра из бара.
function scheduleNextSpin() {
  if (gameState.inFreeSpins && gameState.fsLeft > 0) {
    setTimeout(() => { if (!gameState.isSpinning) spinOnce(); }, 700);
    return;
  }
  scheduleAutoSpin();
}

function setupSpinButton() {
  document.querySelector('[data-action="spin"]').addEventListener('click', () => {
    if (gameState.inFreeSpins) return;
    if (gameState.autoSpinsLeft > 0) {
      stopAutoSpins();
      return;
    }
    spinOnce();
  });
  // Пробел = спин (десктоп).
  window.addEventListener('keydown', (e) => {
    if (e.code !== 'Space' || e.target.closest('input, textarea, button')) return;
    e.preventDefault();
    if (!gameState.inFreeSpins && !gameState.autoSpinsLeft) spinOnce();
  });
}

function setupBuyButton() {
  const btn = document.getElementById('buyBtn');
  btn.addEventListener('click', async () => {
    // Недоступна во время фич и в автоигре (GDD §7.4).
    if (gameState.isSpinning || gameState.inFreeSpins || gameState.autoSpinsLeft > 0) return;
    const bet = currentBet();
    const ok = await showBuyDialog(bet * BUY_COST_MULTIPLIER, gameState.currency);
    if (!ok) return;
    runSpin(() => Api.buyFeature(gameState.sessionId, BUY_ID, bet), bet, { anticipate: false });
  });
  // Юрисдикция без покупки: ?buy=0 прячет кнопку (флаг buy_bonus_enabled).
  if (new URLSearchParams(location.search).get('buy') === '0') {
    document.getElementById('screen').classList.add('is-buy-off');
  }
}

function setupDevButtons() {
  const hwBtn = document.querySelector('[data-dev="hw"]');
  if (hwBtn) hwBtn.addEventListener('click', () => {
    const bet = currentBet();
    runSpin(() => Api.devForceHoldAndWin(gameState.sessionId, bet), bet);
  });
  const fsBtn = document.querySelector('[data-dev="fs"]');
  if (fsBtn) fsBtn.addEventListener('click', () => {
    const bet = currentBet();
    runSpin(() => Api.devForceFreeSpins(gameState.sessionId, bet), bet);
  });
}

// ---------- Турбо и автоспины поверх общего бара V3 ----------

const AUTO_SPIN_GAP_MS = 900;
const spinCountEl = document.getElementById('v3SpinCount');
const spinBtnEl = document.querySelector('[data-action="spin"]');
const turboBtnEl = document.getElementById('v3TurboBtn');
const autoBtnEl = document.getElementById('v3AutoBtn');
let writingSpinCount = false;

function writeSpinCount(value) {
  if (!spinCountEl) return;
  writingSpinCount = true;
  if (value > 0) {
    spinCountEl.textContent = String(value);
    spinCountEl.hidden = false;
  } else {
    spinCountEl.hidden = true;
    document.querySelectorAll('#v3AutoTip .v3-chip').forEach((c) => c.classList.remove('is-active'));
    if (autoBtnEl) autoBtnEl.classList.remove('is-active');
  }
  if (spinBtnEl) spinBtnEl.classList.toggle('has-count', value > 0);
  writingSpinCount = false;
}

function stopAutoSpins() {
  if (gameState.autoSpinsLeft === 0) return;
  gameState.autoSpinsLeft = 0;
  writeSpinCount(0);
}

function scheduleAutoSpin() {
  if (gameState.autoSpinsLeft <= 0) return;
  gameState.autoSpinsLeft -= 1;
  writeSpinCount(gameState.autoSpinsLeft);
  if (gameState.autoSpinsLeft <= 0) return;
  setTimeout(() => {
    if (gameState.autoSpinsLeft > 0 && !gameState.isSpinning) spinOnce();
  }, AUTO_SPIN_GAP_MS);
}

function setupTurboAndAuto() {
  if (turboBtnEl) {
    new MutationObserver(() => setTurbo(turboBtnEl.classList.contains('is-active')))
      .observe(turboBtnEl, { attributes: true, attributeFilter: ['class'] });
  }
  if (!spinCountEl) return;
  new MutationObserver(() => {
    if (writingSpinCount) return;
    const requested = spinCountEl.hidden ? 0 : parseInt(spinCountEl.textContent, 10) || 0;
    gameState.autoSpinsLeft = requested;
    if (requested > 0 && !gameState.isSpinning && !gameState.inFreeSpins) spinOnce();
  }).observe(spinCountEl, { attributes: true, attributeFilter: ['hidden'], childList: true, characterData: true, subtree: true });
}

// ---------- Сессия ----------

async function bootstrapSession() {
  await window.slotReady;
  try {
    const data = await Api.startSession(GAME_ID);
    gameState.sessionId = data.session_id;
    gameState.balance = data.balance;
    gameState.currency = data.currency;
    gameState.symbols = data.symbols || [];
    if (data.bet && data.bet.steps && data.bet.steps.length) {
      gameState.betSteps = data.bet.steps;
      const i = gameState.betSteps.indexOf(data.bet.default);
      gameState.betIndex = i >= 0 ? i : Math.floor(gameState.betSteps.length / 2);
    }
    renderBet();
    renderBalance();
    renderInfoPopupContent();
    await restoreActiveRound();
  } catch (err) {
    console.error('failed to start session, spin will stay disabled:', err);
    renderBet();
  }
}

// Обрыв посреди фриспинов: сервер держит состояние раунда — продолжаем с
// текущего спина (ставка раунда заперта на сервере).
// id прошлой сессии живёт в localStorage: если она оборвалась посреди
// фриспинов, игра переключается на неё (а не на только что созданную).
const SESSION_KEY = `njs.session.${GAME_ID}`;

async function restoreActiveRound() {
  let prev = null;
  try { prev = localStorage.getItem(SESSION_KEY); } catch { /* приватный режим */ }
  try {
    if (prev && prev !== gameState.sessionId) {
      const st = await Api.getSessionState(prev);
      const f = st && st.active_feature;
      if (f && f.type === 'free_spins' && f.spins_remaining > 0) {
        gameState.sessionId = st.session_id;
        gameState.balance = st.balance;
        renderBalance();
        enterFreeSpins(f.spins_remaining, currentBet());
        updateFreeSpinsPanel(f.spins_remaining, f.total_win);
        scheduleNextSpin();
        return;
      }
    }
  } catch (err) {
    console.warn('previous session not restorable:', err);
  }
  try { localStorage.setItem(SESSION_KEY, gameState.sessionId); } catch { /* ignore */ }
}

function setupClickSounds() {
  document.querySelectorAll('.ui-icon-btn, .ui-spin-btn, .buy-btn').forEach((btn) => {
    btn.addEventListener('click', () => Sound.playSfx('click'));
  });
}

function setupSoundToggle() {
  document.querySelector('[data-action="sound"]').addEventListener('click', () => Sound.toggleMuted());
}

// Paytable из session-start; выплата линии на сервере — за линию (ставка / 5),
// игроку показываем в ставках.
const SCATTER_PAYS = { 3: 2, 4: 5, 5: 10, 6: 20, 7: 50, 8: 100, 9: 200 };
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const pay = symbol.paytable && symbol.paytable['3'];
    let pays;
    if (symbol.code === 'scatter') {
      pays = `3–9: <b>${SCATTER_PAYS[3]}×–${SCATTER_PAYS[9]}×</b>`;
    } else if (pay) {
      pays = `×3: <b>${+(pay / 5).toFixed(2)}×</b>`;
    } else continue;
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    row.innerHTML = `<img src="${symbolSrc(symbol.code)}" alt=""><span class="info-popup__row-name">${symbol.name}</span><span class="info-popup__row-pays">${pays}</span>`;
    list.appendChild(row);
  }
}

function setupInfoPopup() {
  const popup = document.getElementById('infoPopup');
  document.querySelector('[data-action="info"]').addEventListener('click', () => {
    Sound.playSfx('popupOpen');
    popup.hidden = false;
  });
  const close = () => { Sound.playSfx('popupClose'); popup.hidden = true; };
  document.getElementById('infoPopupClose').addEventListener('click', close);
  popup.addEventListener('click', (e) => { if (e.target === popup) close(); });
}

setupBetStepper();
setupSpinButton();
setupBuyButton();
setupTurboAndAuto();
setupClickSounds();
setupSoundToggle();
setupInfoPopup();
setupDevButtons();
bootstrapSession();
