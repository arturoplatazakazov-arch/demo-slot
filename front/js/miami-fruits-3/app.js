// Miami Fruits 3 — оркестрация спина поверх ОБЩЕГО нижнего бара V3 (тот же
// css/ui-bar-v3.css + js/ui-bar-v3.js, что у соседних игр). Адаптировано с
// ../uniqorn-shaolin-struggles/app.js, минус всё бонусное: в этой игре нет ни
// Hold & Win, ни монет, ни покупки — спин отвечает сразу окончательным
// результатом, и после приземления остаётся только показать выигрыш.
//
// Разделение с ui-bar-v3.js: тот держит ВИД бара (флайаут, тултипы, подсветка
// активных состояний, зеркало ставки), а этот файл — смысл (сколько стоит
// спин, что делает кнопка, сколько автоспинов осталось). Контракт между ними —
// data-action и id из разметки, их менять нельзя.

const GAME_ID = 'miami-fruits-3';

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
};

function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

function renderBet() {
  // Зеркало в тултипе (#v3BetMirror) заполняет сам ui-bar-v3.js по
  // MutationObserver на этом узле — писать туда второй раз не нужно.
  document.getElementById('betValue').textContent = formatNumber(gameState.betSteps[gameState.betIndex]);
}

function renderBalance() {
  document.getElementById('balanceValue').textContent = formatNumber(gameState.balance);
  for (const el of document.querySelectorAll('.ui-balance__currency, .ui-bet-field__currency')) {
    el.textContent = gameState.currency;
  }
}

function setupBetStepper() {
  document.querySelector('[data-action="bet-minus"]').addEventListener('click', () => {
    if (gameState.isSpinning) return;
    gameState.betIndex = Math.max(0, gameState.betIndex - 1);
    renderBet();
  });
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
    if (gameState.isSpinning) return;
    gameState.betIndex = Math.min(gameState.betSteps.length - 1, gameState.betIndex + 1);
    renderBet();
  });
}

// Какой попап показать за выигрыш. Сервер (app/services/popups.py) считает тир
// по ДЛИНЕ выигрышной линии, а на трёх барабанах она всегда 3, так что этот
// сигнал здесь бесполезен — тир считаем по отношению выигрыша к ставке, а
// серверный попап оставляем нижней границей.
const POPUP_TIER_BY_RATIO = [[40, 'epicWin'], [20, 'megaWin'], [8, 'bigWin']];

function popupForWin(totalWin, betAmount, serverPopup) {
  const ratio = betAmount > 0 ? totalWin / betAmount : 0;
  for (const [threshold, type] of POPUP_TIER_BY_RATIO) {
    if (ratio >= threshold) return type;
  }
  return serverPopup ? serverPopup.type : null;
}

async function applySpinResult(data, betAmount) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  playWinCells(data.winning_cells, data.line_wins, data.count_wins);

  const popupType = popupForWin(data.total_win, betAmount, data.popup);
  if (popupType) {
    Sound.playSfx({ bigWin: 'bigWin', megaWin: 'megaWin', epicWin: 'epicWin' }[popupType]);
    await playPopup(popupType, data.total_win);
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
    await landReels(data.grid);
    await applySpinResult(data, betAmount);
  } catch (err) {
    console.error('spin failed:', err);
    showInlineNotice('СПИН НЕ ПРОШЁЛ');
    stopReelLoop();
    if (gameState.lastGrid) await applyGrid(gameState.lastGrid);
  } finally {
    spinBtn.classList.remove('is-spinning');
    gameState.isSpinning = false;
    autoplayTick();
  }
}

// Без сессии спин физически невозможен, но МОЛЧА ничего не делать нельзя: со
// стороны это выглядит как «кнопка сломана». Поэтому сначала пробуем поднять
// сессию заново (бэкенд мог быть недоступен только на старте страницы), и лишь
// если и это не вышло — говорим об этом прямо на барабанах.
async function ensureSession() {
  if (gameState.sessionId) return true;
  await bootstrapSession();
  if (gameState.sessionId) return true;
  showInlineNotice('НЕТ СВЯЗИ С СЕРВЕРОМ');
  return false;
}

async function spinOnce() {
  if (!await ensureSession()) {
    stopAutoplay();
    return;
  }
  const betAmount = gameState.betSteps[gameState.betIndex];
  runSpin(() => Api.spin(gameState.sessionId, betAmount), betAmount);
}

function setupSpinButton() {
  document.querySelector('[data-action="spin"]').addEventListener('click', () => {
    if (autoplayLeft > 0) { stopAutoplay(); return; }
    spinOnce();
  });
}

// --- Автоигра ----------------------------------------------------------------
//
// В отличие от донора (там чипы были чистой заглушкой ui-bar-v3.js) выбор
// 10/25/50/100 реально крутит столько же спинов подряд: следующий стартует из
// finally предыдущего, так что попап успевает отыграть до конца. Счётчик
// показывается там же, где его рисует бар, — в кольце кнопки SPIN.
let autoplayLeft = 0;

function renderAutoplay() {
  const count = document.getElementById('v3SpinCount');
  const spinBtn = document.querySelector('.v3-spin');
  if (!count || !spinBtn) return;
  count.textContent = autoplayLeft > 0 ? String(autoplayLeft) : '';
  count.hidden = autoplayLeft === 0;
  spinBtn.classList.toggle('has-count', autoplayLeft > 0);
  if (autoplayLeft === 0) {
    document.getElementById('v3AutoBtn').classList.remove('is-active');
    document.querySelectorAll('#v3AutoTip .v3-chip').forEach((c) => c.classList.remove('is-active'));
  }
}

function stopAutoplay() {
  autoplayLeft = 0;
  renderAutoplay();
}

function autoplayTick() {
  if (autoplayLeft <= 0) return;
  autoplayLeft -= 1;
  renderAutoplay();
  if (autoplayLeft > 0) setTimeout(spinOnce, 350);
}

function setupAutoplay() {
  document.querySelectorAll('#v3AutoTip .v3-chip').forEach((chip) => {
    // Слушатель ДОПОЛНЯЕТ обработчик ui-bar-v3.js на том же чипе: тот рисует
    // состояние, этот запускает серию.
    chip.addEventListener('click', () => {
      const spins = Number(chip.dataset.spins);
      // Повторный клик по активному чипу в баре означает «выключить».
      autoplayLeft = autoplayLeft > 0 ? 0 : spins;
      renderAutoplay();
      if (autoplayLeft > 0 && !gameState.isSpinning) spinOnce();
    });
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
    // превью арта и анимаций всё равно работало. Спин при этом не молчит:
    // ensureSession() покажет причину на барабанах.
    console.error('failed to start session, spin will stay disabled until it succeeds:', err);
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
// бывает только длины 3, поэтому колонка чисел одна.
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    row.innerHTML = `
      <img src="${symbolSrc(symbol.code)}" alt="${symbol.name}">
      <span class="info-popup__row-name">${symbol.name}</span>
      <span class="info-popup__row-pays">×3: <b>${formatNumber(symbol.paytable['3'] || 0)}</b></span>
    `;
    list.appendChild(row);
  }
}

function setupInfoPopup() {
  const popup = document.getElementById('infoPopup');
  document.querySelectorAll('[data-action="info"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      Sound.playSfx('popupOpen');
      popup.hidden = false;
    });
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
setupAutoplay();
setupClickSounds();
setupSoundToggle();
setupInfoPopup();
bootstrapSession();
