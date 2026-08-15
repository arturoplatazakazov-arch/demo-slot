// Uniqorn Back to Fabulous — нижний бар + оркестрация спина, адаптировано из
// ../neon-reels/app.js (та же механика: линии, скаттерные фриспины, множитель
// на эссенции). Сессия поднимается при загрузке; каждый клик Spin/Buy — реальный
// запрос.
const GAME_ID = 'uniqorn-back-to-fabulous';

const gameState = {
  sessionId: null,
  betSteps: [5500, 13750, 27500, 55000, 137500, 275000], // фолбэк, если бэкенд недоступен
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  freeSpinsRemaining: 0,
  lastGrid: null,
  symbols: [],
  freeSpinsTrigger: null,
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

// Число на fs_counter.png — сама пара картинка/подпись статична.
function updateFreeSpinsCounter(remaining) {
  const el = document.getElementById('freeSpinsValue');
  if (el) el.textContent = remaining;
}

// Общий хвост обычного спина и покупки бонуса: обновить баланс/режим/счётчик,
// проиграть выигрыш, показать попап, если сервер его прислал.
async function applySpinResult(data) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  const remaining = data.feature && data.feature.type === 'free_spins' ? data.feature.spins_remaining : 0;
  gameState.freeSpinsRemaining = remaining;
  // Входит ли этот спин в бонус из базовой игры — фиксируем ДО того, как
  // setFreeSpinsMode переключит режим. Сначала играют выигравшие ячейки
  // (приземлившиеся скаттеры), потом идёт интро (чёрный + попап + показ).
  const enteringBonus = document.getElementById('screen').dataset.mode !== 'freespins' && remaining > 0;

  playWinCells(data.winning_cells, data.line_wins, data.count_wins);
  playCoinMultiplierReveal(data.coin_multiplier);

  await setFreeSpinsMode(remaining > 0, remaining);
  if (remaining > 0) updateFreeSpinsCounter(remaining);

  if (data.popup) {
    // Входной bonusSpinsWin показывает сама интро-последовательность; ретриггер
    // внутри бонуса всё так же получает свой попап здесь.
    const shownByIntro = enteringBonus && data.popup.type === 'bonusSpinsWin';
    if (!shownByIntro) {
      const tierSound = WIN_TIER_SOUNDS[data.popup.type];
      if (tierSound) Sound.playSfx(tierSound);
      playPopup(data.popup.type, data.popup.amount);
    }
  } else if (data.total_win > 0) {
    // Базовые выигрыши ниже порога big/mega/epic попапа не получают — сумма
    // показывается инлайном поверх сетки.
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
    // Если бэкенд недоступен — оставляем на экране статичные плейсхолдеры,
    // а не падаем целиком.
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

// Пейтейбл — авторитет на стороне сервера (gameState.symbols из session-start).
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    const payParts = ['3', '4', '5']
      .filter((count) => symbol.paytable[count] !== undefined)
      .map((count) => `<span>×${count}: <b>${formatNumber(symbol.paytable[count])}</b></span>`)
      .join('');
    row.innerHTML = `
      <img src="${symbolSrc(symbol.code)}" alt="${symbol.name}" onerror="this.remove()">
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
