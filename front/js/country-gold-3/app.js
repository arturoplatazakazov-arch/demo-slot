// Country Gold 3 — нижний бар и оркестрация спина. Адаптировано с
// ../lucky-miami-3/app.js: один путь — нажали спин, дождались ответа, уронили
// барабаны, показали выигрыш; ни покупки бонуса, ни второго режима экрана в
// игре нет.
//
// Добавлено против донора — ТУРБО и АВТОСПИНЫ. В общем баре (js/ui-bar-v3.js)
// это визуальные заглушки, а трогать общий файл ради одной игры нельзя, поэтому
// они доводятся до настоящих ЧЕРЕЗ MutationObserver: турбо читается по классу
// is-active на #v3TurboBtn, автоспины — по счётчику #v3SpinCount, который бар
// печатает в кольце SPIN. Наблюдение вместо своего onclick снимает зависимость
// от порядка навешивания слушателей.

const GAME_ID = 'country-gold-3';

const gameState = {
  sessionId: null,
  // Запасные значения, если бэкенд недоступен — зеркалят BET_STEPS сида
  // (кратны 5, чтобы ставка делилась на 5 линий).
  betSteps: [10000, 25000, 50000, 100000, 250000, 500000],
  betIndex: 3,
  balance: 1_000_000,
  currency: 'FUN',
  isSpinning: false,
  autoSpinsLeft: 0,
  lastGrid: null,
  symbols: [],
};

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
// по ДЛИНЕ выигрышной линии, а на трёх барабанах она всегда 3 — то есть для
// этой игры серверный тир бесполезен. Считаем по отношению выигрыша к ставке:
// пороги подобраны под здешнюю выплатную лестницу (слива даёт 1.8x, семёрка —
// 1000x), так что bigWin начинается примерно с колокольчика.
const POPUP_TIER_BY_RATIO = [[150, 'epicWin'], [50, 'megaWin'], [15, 'bigWin']];

function popupForWin(totalWin, betAmount) {
  const ratio = betAmount > 0 ? totalWin / betAmount : 0;
  for (const [threshold, type] of POPUP_TIER_BY_RATIO) {
    if (ratio >= threshold) return type;
  }
  return null;
}

async function applySpinResult(data, betAmount) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  playWinCells(data.winning_cells, data.line_wins, data.count_wins);

  const popupType = popupForWin(data.total_win, betAmount);
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
    await landReels(data.grid);
    await applySpinResult(data, betAmount);
  } catch (err) {
    console.error('spin failed:', err);
    stopAutoSpins();
    stopReelLoop();
    if (gameState.lastGrid) await applyGrid(gameState.lastGrid);
  } finally {
    spinBtn.classList.remove('is-spinning');
    gameState.isSpinning = false;
    // Подсказка под барабанами живёт ровно между спинами — startReelLoop её
    // прячет, вернуть её больше некому.
    setHintVisible(true);
    scheduleAutoSpin();
  }
}

function spinOnce() {
  const betAmount = gameState.betSteps[gameState.betIndex];
  runSpin(() => Api.spin(gameState.sessionId, betAmount), betAmount);
}

function setupSpinButton() {
  document.querySelector('[data-action="spin"]').addEventListener('click', () => {
    // Клик по SPIN во время автоигры — это «стоп», а не лишний спин поверх.
    if (gameState.autoSpinsLeft > 0) {
      stopAutoSpins();
      return;
    }
    spinOnce();
  });
}

// ---------- Турбо и автоспины поверх общего бара V3 ----------

// Пауза между автоспинами: выигрыш должен успеть проиграться, но не настолько,
// чтобы автоигра выглядела зависшей.
const AUTO_SPIN_GAP_MS = 900;

const spinCountEl = document.getElementById('v3SpinCount');
const spinBtnEl = document.querySelector('[data-action="spin"]');
const turboBtnEl = document.getElementById('v3TurboBtn');
const autoBtnEl = document.getElementById('v3AutoBtn');
// Счётчик перерисовываем сами, а наблюдаем за ним же — флаг гасит собственную
// запись, иначе observer заводил бы автоигру заново на каждый спин.
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

// Вызывается в finally каждого спина: серия уменьшается на отыгранный спин, и
// если осталось ещё — следующий заводится после паузы на показ выигрыша.
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
    new MutationObserver(() => {
      setTurbo(turboBtnEl.classList.contains('is-active'));
    }).observe(turboBtnEl, { attributes: true, attributeFilter: ['class'] });
  }

  if (!spinCountEl) return;
  new MutationObserver(() => {
    if (writingSpinCount) return;
    const requested = spinCountEl.hidden ? 0 : parseInt(spinCountEl.textContent, 10) || 0;
    gameState.autoSpinsLeft = requested;
    if (requested > 0 && !gameState.isSpinning) spinOnce();
  }).observe(spinCountEl, {
    attributes: true,
    attributeFilter: ['hidden'],
    childList: true,
    characterData: true,
    subtree: true,
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
    console.error('failed to start session, spin will stay disabled:', err);
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
// бывает только длины 3, поэтому колонка чисел одна; рядом печатаем ту же
// выплату в ставках (paytable / 5 линий), потому что игрок думает ставкой, а
// не долей линии.
function renderInfoPopupContent() {
  const list = document.getElementById('infoPopupList');
  if (!list) return;
  const lineCount = 5;
  list.innerHTML = '';
  for (const symbol of gameState.symbols) {
    const pay = symbol.paytable['3'];
    const row = document.createElement('div');
    row.className = 'info-popup__row';
    row.innerHTML = `
      <img src="${symbolSrc(symbol.code)}" alt="${symbol.name}">
      <span class="info-popup__row-name">${symbol.name}</span>
      <span class="info-popup__row-pays">
        <span>×3: <b>${formatNumber(pay)}</b></span>
        <span>= <b>${(pay / lineCount).toFixed(1)}</b>× ставки</span>
      </span>
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
setupTurboAndAuto();
setupClickSounds();
setupSoundToggle();
setupInfoPopup();
bootstrapSession();
