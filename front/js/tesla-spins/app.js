// Tesla Spins — нижний бар и оркестрация спина. Скопировано с
// ../gold-of-baku/app.js (турбо и автоспины поверх общего бара V3 через
// MutationObserver — подробности там). Добавлено: проигрывание раунда
// Hold & Win (data.hold_and_win, см. playHoldAndWin в slot.js), лестница
// джекпотов под ставку и удар молний катушек в выигравшие ячейки.

const GAME_ID = 'tesla-spins';

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
  const bet = gameState.betSteps[gameState.betIndex];
  document.getElementById('betValue').textContent = formatNumber(bet);
  updateJackpotPlates(bet);
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

// Какой попап показать за выигрыш. Серверный тир (по длине линии) на трёх
// барабанах бесполезен — линия всегда 3, поэтому считаем по отношению к
// ставке. Лестница (×ставки за линию): лимон 1.4, вишня 2.4, слива 3.4, арбуз
// 6.., колокол ~18, звезда 46, слиток 110, семёрка 374; Hold & Win в среднем
// ~25x. bigWin — от колокола, megaWin — от 50x (крупный раунд, слиток),
// epicWin — от 200x (семёрка, MAJOR, GRAND).
const POPUP_TIER_BY_RATIO = [[200, 'epicWin'], [50, 'megaWin'], [10, 'bigWin']];

function popupForWin(totalWin, betAmount) {
  const ratio = betAmount > 0 ? totalWin / betAmount : 0;
  for (const [threshold, type] of POPUP_TIER_BY_RATIO) {
    if (ratio >= threshold) return type;
  }
  return null;
}

async function applySpinResult(data, betAmount, hw = null) {
  gameState.balance = data.balance;
  gameState.lastGrid = data.grid;
  renderBalance();

  // После раунда Hold & Win линии уже показаны до него, а поле занято
  // монетами — остаётся попап итога, затем выход из режима раунда.
  if (hw) {
    const type = popupForWin(data.total_win, betAmount) || 'bigWin';
    Sound.playSfx({ bigWin: 'bigWin', megaWin: 'megaWin', epicWin: 'epicWin' }[type]);
    await playPopup(type, data.total_win);
    exitHoldAndWinMode();
    return;
  }

  playWinCells(data.winning_cells, data.line_wins, data.count_wins);

  const popupType = popupForWin(data.total_win, betAmount);
  if (data.total_win > 0) {
    // Чем крупнее выигрыш, тем толще и дольше разряд (1 .. 2).
    const ratio = data.total_win / betAmount;
    const power = Math.min(2, 1 + Math.log10(Math.max(1, ratio)) / 2);
    strikeWinningCells(data.winning_cells, power);
  }
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
    const hw = data.hold_and_win && data.hold_and_win.triggered ? data.hold_and_win : null;
    if (hw) {
      // линии спина-триггера (если были) — коротко до раунда
      if (data.line_wins && data.line_wins.length) {
        playWinCells(data.winning_cells, data.line_wins, data.count_wins);
        strikeWinningCells(data.winning_cells, 1.2);
        await new Promise((r) => setTimeout(r, 1800));
      }
      await playHoldAndWin(hw, betAmount);
    }
    await applySpinResult(data, betAmount, hw);
  } catch (err) {
    console.error('spin failed:', err);
    stopAutoSpins();
    stopReelLoop();
    exitHoldAndWinMode();
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

// DEV: спин с принудительными монетами (app/api/v1/spin.py dev_force_hold_and_win).
function setupDevHoldAndWin() {
  const btn = document.querySelector('[data-dev="hw"]');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const betAmount = gameState.betSteps[gameState.betIndex];
    runSpin(() => Api.devForceHoldAndWin(gameState.sessionId, betAmount), betAmount);
  });
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
    const pay = symbol.paytable && symbol.paytable['3'];
    if (!pay) continue; // вайлд сам не платит — он описан в заметке над списком
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
setupDevHoldAndWin();
bootstrapSession();
