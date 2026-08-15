// Uniqorn Shaolin Struggles — нижний бар и оркестрация спина. Адаптировано с
// ../lucky-joker-3h3/app.js (та же 3x3-механика), минус всё, что связано с
// фриспинами: скаттера в этой игре нет, единственный бонус — Hold & Win,
// который сервер решает целиком в ответе на триггерный спин.

const GAME_ID = 'uniqorn-shaolin-struggles';

const gameState = {
  sessionId: null,
  // Запасные значения, если бэкенд недоступен — зеркалят BET_STEPS сида
  // (кратны 5, чтобы ставка делилась на 5 линий).
  betSteps: [10000, 25000, 50000, 100000, 250000, 500000],
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  lastGrid: null,
  symbols: [],
  // Заполняется, когда спин (или dev-кнопка) открыл раунд: он уже полностью
  // посчитан сервером, но ждёт следующего нажатия Spin — первый респин
  // ручной, остальные докручиваются изнутри runHoldAndWinSequence.
  pendingHoldAndWin: null,
  pendingHoldAndWinLocked: null,
  // Монеты триггерного спина — чтобы вернуть барабаны ровно такими, какими
  // они были, когда раунд закончится.
  pendingHoldAndWinCoins: null,
};

// cost_multiplier продукта hold_and_win_buy в
// app/seed/uniqorn_shaolin_struggles.py (BONUS_BUY_COST_MULTIPLIER). Здесь
// только для показа цены — списывает сервер по своей конфигурации.
const BUY_BONUS_COST_MULTIPLIER = 50;

function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

function renderBet() {
  document.getElementById('betValue').textContent = formatNumber(gameState.betSteps[gameState.betIndex]);
  renderBuyBonusPrice();
}

function renderBalance() {
  document.getElementById('balanceValue').textContent = formatNumber(gameState.balance);
  document.querySelector('.ui-balance__currency').textContent = gameState.currency;
  document.querySelector('.ui-bet-field__currency').textContent = gameState.currency;
}

function renderBuyBonusPrice() {
  const el = document.getElementById('buyBonusPrice');
  if (!el) return;
  const cost = gameState.betSteps[gameState.betIndex] * BUY_BONUS_COST_MULTIPLIER;
  el.textContent = `${formatNumber(cost)} ${gameState.currency}`;
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

// Какой попап показать за выигрыш. Сервер (app/services/popups.py) умеет
// прислать только bigWin: тир там считается по ДЛИНЕ выигрышной линии, а на
// трёх барабанах она всегда 3. Для этой игры это слишком грубо — множитель
// монеты легко превращает копеечную линию в сотни ставок, — поэтому тир
// считается по отношению выигрыша к ставке, а серверный попап работает нижней
// границей (высокий символ всегда получает хотя бы bigWin).
const POPUP_TIER_BY_RATIO = [[25, 'epicWin'], [12, 'megaWin'], [5, 'bigWin']];

function popupForWin(totalWin, betAmount, serverPopup) {
  const ratio = betAmount > 0 ? totalWin / betAmount : 0;
  for (const [threshold, type] of POPUP_TIER_BY_RATIO) {
    if (ratio >= threshold) return type;
  }
  return serverPopup ? serverPopup.type : null;
}

// Общий хвост обычного спина: обновить баланс, проиграть выигрыш, показать
// попап или сумму.
async function applySpinResult(data, betAmount) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  if (data.hold_and_win && data.hold_and_win.triggered) {
    // Раунд уже решён сервером — переключаемся на бонусный экран с монетами
    // триггера на месте и ждём следующего нажатия Spin. Ни попапа, ни суммы за
    // сам триггерный спин: его выплату закрывает карточка итога раунда.
    gameState.pendingHoldAndWin = data.hold_and_win;
    gameState.pendingHoldAndWinCoins = data.coin_multiplier;
    gameState.pendingHoldAndWinLocked = await enterHoldAndWinWaitingState(data.hold_and_win);
    return;
  }

  // Значения монет уже на экране — они были вклеены в ленту до её падения
  // (landReels/resolveDrawnGrid), так что монета приезжает со своим
  // множителем. Здесь остаётся только подсветить те, что реально сработали.
  playWinCells(data.winning_cells, data.line_wins, data.count_wins);
  playCoinMultiplierReveal(data.coin_multiplier);

  const popupType = popupForWin(data.total_win, betAmount, data.popup);
  if (popupType) {
    Sound.playSfx({ bigWin: 'bigWin', megaWin: 'megaWin', epicWin: 'epicWin' }[popupType]);
    playPopup(popupType, data.total_win);
  } else if (data.total_win > 0) {
    Sound.playSfx('smallWin');
    showInlineWinAmount(data.total_win);
  }
}

async function runSpin(request, betAmount) {
  if (gameState.isSpinning || !gameState.sessionId) return;
  gameState.isSpinning = true;

  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  startReelLoop();

  try {
    const data = await request();
    // Антиципация последнего барабана считается внутри landReels по самой
    // сетке (коллектор на среднем + монета на первом), а не по конфигу
    // фриспинов — их здесь нет.
    await landReels(data.grid, data.coin_multiplier);
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
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.spin(gameState.sessionId, betAmount), betAmount);
  });
}

// Запускает (уже решённую сервером) серию респинов — это тот самый «первый
// спин», который игрок нажимает сам; дальше раунд докручивается изнутри
// runHoldAndWinSequence. Баланс уже включает выплату (она пришла с ответом на
// триггерный спин), поэтому здесь ничего не рассчитывается.
async function runHoldAndWin(result, locked) {
  if (gameState.isSpinning) return;
  gameState.isSpinning = true;
  const spinBtn = document.querySelector('[data-action="spin"]');
  spinBtn.classList.add('is-spinning');
  try {
    await runHoldAndWinSequence(result, locked, gameState.lastGrid, gameState.pendingHoldAndWinCoins);
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
    // buy_id — единственный продукт bonus_buy в сиде этой игры.
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.buyFeature(gameState.sessionId, 'hold_and_win_buy', betAmount), betAmount);
  });
}

// Dev-only: настоящий спин по /dev/force-hold-and-win — эндпоинт подкладывает
// коллектор и монеты на честно вытянутую сетку, так что Hold & Win срабатывает
// своим обычным is_triggered(), и стоит это одну обычную ставку, а не цену
// покупки.
function setupDevHoldAndWinButton() {
  const btn = document.getElementById('devHoldAndWin');
  if (!btn) return;
  btn.addEventListener('click', () => {
    if (gameState.pendingHoldAndWin) return;
    const betAmount = gameState.betSteps[gameState.betIndex];
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
      const defaultIndex = gameState.betSteps.indexOf(data.bet.default);
      gameState.betIndex = defaultIndex >= 0 ? defaultIndex : Math.floor(gameState.betSteps.length / 2);
    }
    renderBet();
    renderBalance();
    renderInfoPopupContent();
  } catch (err) {
    // Бэкенд недоступен — оставляем статические заглушки на экране, чтобы
    // превью арта и анимаций всё равно работало.
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
  document.querySelector('[data-action="sound"]').addEventListener('click', () => {
    Sound.toggleMuted();
  });
}

// Paytable — server-authoritative (gameState.symbols из session-start),
// картинки берутся из тех же PNG, что и на барабанах. На трёх барабанах линия
// бывает только длины 3, поэтому колонка чисел одна; у монеты и коллектора
// своей выплаты нет вовсе — вместо пустой строки они получают пояснение.
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const pays = symbol.paytable['3'] !== undefined
      ? `<span>×3: <b>${formatNumber(symbol.paytable['3'])}</b></span>`
      : '<span>множитель линии / Hold &amp; Win</span>';
    row.innerHTML = `
      <img src="img/uniqorn-shaolin-struggles/symbols/${symbol.code}.png" alt="${symbol.name}">
      <span class="info-popup__row-name">${symbol.name}</span>
      <span class="info-popup__row-pays">${pays}</span>
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
