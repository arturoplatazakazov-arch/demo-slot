// Volt Coins — нижний бар и оркестрация спина (с ../uniqorn-shaolin-struggles/app.js).
// Единственный бонус — Hold & Win, который сервер решает целиком в ответе на
// триггерный спин; клиент его только проигрывает.

const GAME_ID = 'volt-coins';

// Ставка, под которую заказчик выписал суммы на плашках (10 000 / 2 500 /
// 500 / 200) — с неё игра и открывается, если она есть среди шагов сервера.
const OPENING_BET = 10;

const gameState = {
  sessionId: null,
  betSteps: [10, 20, 50, 100, 200, 500, 1000, 2000, 5000],
  betIndex: 0,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  lastGrid: null,
  symbols: [],
  pendingHoldAndWin: null,
  pendingHoldAndWinLocked: null,
};

// = BONUS_BUY_COST_MULTIPLIER в app/seed/volt_coins.py (только для показа).
const BUY_BONUS_COST_MULTIPLIER = 40;

function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

function currentBet() {
  return gameState.betSteps[gameState.betIndex];
}

function renderBet() {
  document.getElementById('betValue').textContent = formatNumber(currentBet());
  const mirror = document.getElementById('v3BetMirror');
  if (mirror) mirror.textContent = formatNumber(currentBet());
  setJackpotBet(currentBet());
  renderBuyBonusPrice();
}

function renderBalance() {
  document.getElementById('balanceValue').textContent = formatNumber(gameState.balance);
  document.querySelector('.ui-balance__currency').textContent = gameState.currency;
  document.querySelectorAll('.ui-bet-field__currency, .v3-readout__cur').forEach((el) => {
    el.textContent = gameState.currency;
  });
}

function renderBuyBonusPrice() {
  const el = document.getElementById('buyBonusPrice');
  if (el) el.textContent = `${formatNumber(currentBet() * BUY_BONUS_COST_MULTIPLIER)} ${gameState.currency}`;
}

function setupBetStepper() {
  document.querySelector('[data-action="bet-minus"]').addEventListener('click', () => {
    if (gameState.isSpinning || gameState.pendingHoldAndWin) return;
    gameState.betIndex = Math.max(0, gameState.betIndex - 1);
    renderBet();
  });
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
    if (gameState.isSpinning || gameState.pendingHoldAndWin) return;
    gameState.betIndex = Math.min(gameState.betSteps.length - 1, gameState.betIndex + 1);
    renderBet();
  });
}

// Сервер на трёх барабанах присылает максимум bigWin (тир по длине линии),
// поэтому тир попапа считается по отношению выигрыша к ставке.
const POPUP_TIER_BY_RATIO = [[50, 'epicWin'], [25, 'megaWin'], [10, 'bigWin']];

function popupForWin(totalWin, betAmount) {
  const ratio = betAmount > 0 ? totalWin / betAmount : 0;
  for (const [threshold, type] of POPUP_TIER_BY_RATIO) if (ratio >= threshold) return type;
  return null;
}

async function applySpinResult(data, betAmount) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  if (data.hold_and_win && data.hold_and_win.triggered) {
    // Линия на триггерном спине тоже бывает — её выплата уже в балансе,
    // но раунд важнее: сразу в него, итог покажет карточка раунда.
    gameState.pendingHoldAndWin = data.hold_and_win;
    gameState.pendingHoldAndWinLocked = await enterHoldAndWinWaitingState(data.hold_and_win);
    return;
  }

  playWinCells(data.line_wins);
  // Общий выигрыш спина — на табло над барабанами до следующего спина
  // (поверх линий и Spine), и в попапе, если он крупный.
  showTotalWin(data.total_win);
  const popupType = popupForWin(data.total_win, betAmount);
  if (popupType) {
    Sound.playSfx({ bigWin: 'bigWin', megaWin: 'megaWin', epicWin: 'epicWin' }[popupType]);
    playPopup(popupType, data.total_win);
  } else if (data.total_win > 0) {
    Sound.playSfx('smallWin');
  }
}

// opts.bought: купленный раунд — исход известен заранее, антиципация
// последнего барабана была бы обманом.
async function runSpin(request, betAmount, opts = {}) {
  if (gameState.isSpinning || !gameState.sessionId) return;
  gameState.isSpinning = true;
  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  startReelLoop();
  try {
    const data = await request();
    // Монеты падают уже с номиналом/джекпотом (coin_multiplier, display_only).
    await landReels(data.grid, data.coin_multiplier, { anticipate: !opts.bought });
    await applySpinResult(data, betAmount);
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
    const betAmount = currentBet();
    runSpin(() => Api.spin(gameState.sessionId, betAmount), betAmount);
  });
}

async function runHoldAndWin(result, locked) {
  if (gameState.isSpinning) return;
  gameState.isSpinning = true;
  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  try {
    await runHoldAndWinSequence(result, locked, gameState.lastGrid);
  } finally {
    spinBtn.classList.remove('is-spinning');
    gameState.isSpinning = false;
  }
}

function setupBuyBonusButton() {
  const buyBtn = document.getElementById('buyBonusBtn');
  if (!buyBtn) return;
  buyBtn.addEventListener('click', async () => {
    if (gameState.isSpinning || gameState.pendingHoldAndWin) return;
    const { confirmed, betIndex } = await showBuyBonusDialog({
      betSteps: gameState.betSteps,
      betIndex: gameState.betIndex,
      costMultiplier: BUY_BONUS_COST_MULTIPLIER,
      currency: gameState.currency,
      balance: gameState.balance,
    });
    gameState.betIndex = betIndex;
    renderBet();
    if (!confirmed) return;
    const betAmount = currentBet();
    // Сервер кладёт в купленный спин линию монет по центру (buy_coin_line)
    // с номиналами — она падает, подсвечивается и уводит в Hold & Win.
    runSpin(() => Api.buyFeature(gameState.sessionId, 'hold_and_win_buy', betAmount), betAmount, { bought: true });
  });
}

// Dev: настоящий спин по /dev/force-hold-and-win (3 монеты подложены в честно
// вытянутую сетку), стоит одну ставку.
function setupDevHoldAndWinButton() {
  const btn = document.getElementById('devHoldAndWin');
  if (!btn) return;
  btn.addEventListener('click', () => {
    if (gameState.pendingHoldAndWin) return;
    const betAmount = currentBet();
    runSpin(() => Api.devForceHoldAndWin(gameState.sessionId, betAmount), betAmount);
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
      const opening = gameState.betSteps.indexOf(OPENING_BET);
      const fallback = gameState.betSteps.indexOf(data.bet.default);
      gameState.betIndex = opening >= 0 ? opening : Math.max(0, fallback);
    }
    renderBet();
    renderBalance();
    renderInfoPopupContent();
  } catch (err) {
    console.error('failed to start session, spin/buy will stay disabled:', err);
    renderBet();
  }
}

function setupClickSounds() {
  document.querySelectorAll('.ui-icon-btn, .ui-spin-btn').forEach((btn) => {
    btn.addEventListener('click', () => Sound.playSfx('click'));
  });
}

function setupSoundToggle() {
  document.querySelector('[data-action="sound"]').addEventListener('click', () => Sound.toggleMuted());
}

function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const pays = symbol.paytable['3'] !== undefined
      ? `<span>×3: <b>${formatNumber(symbol.paytable['3'])}</b> × ставка на линию</span>`
      : '<span>3 в линию запускают Hold &amp; Win</span>';
    row.innerHTML = `
      <img src="img/volt-coins/symbols/${symbol.code === 'coin' ? 'coin_value' : symbol.code}.png" alt="">
      <span class="info-popup__row-name"></span>
      <span class="info-popup__row-pays">${pays}</span>
    `;
    row.querySelector('.info-popup__row-name').textContent = symbol.name;
    list.appendChild(row);
  }
}

function setupInfoPopup() {
  const popup = document.getElementById('infoPopup');
  document.querySelector('[data-action="info"]').addEventListener('click', () => {
    Sound.playSfx('popupOpen');
    popup.hidden = false;
  });
  const close = () => {
    Sound.playSfx('popupClose');
    popup.hidden = true;
  };
  document.getElementById('infoPopupClose').addEventListener('click', close);
  popup.addEventListener('click', (event) => {
    if (event.target === popup) close();
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
