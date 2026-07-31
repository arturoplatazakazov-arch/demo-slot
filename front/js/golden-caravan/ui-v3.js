// Golden Caravan — поведение нижнего бара V3 (макет Figma "V3").
//
// Слой поверх app.js, НЕ дублирующий его логику: спин, ставка, звук и info
// по-прежнему живут в app.js/sound.js и цепляются к своим data-action. Здесь
// только то, чего в старом баре не было: раскрытие меню, тултип ставки, выбор
// числа автоспинов и активные (зелёные) состояния.
//
// Автоигра и турбо в этом заходе — ВИЗУАЛЬНЫЕ ЗАГЛУШКИ: они переключают вид и
// показывают состояния из макета, но не запускают спины и не ускоряют анимацию.

(function () {
  const bar = document.getElementById('v3Bar');
  if (!bar) return;

  const menu = bar.querySelector('.v3-menu');
  const menuBtn = document.getElementById('v3MenuBtn');
  const autoBtn = document.getElementById('v3AutoBtn');
  const turboBtn = document.getElementById('v3TurboBtn');
  const betBtn = document.getElementById('v3BetBtn');
  const betTip = document.getElementById('v3BetTip');
  const autoTip = document.getElementById('v3AutoTip');
  const spinBtn = bar.querySelector('.v3-spin');
  const spinCount = document.getElementById('v3SpinCount');
  const betValue = document.getElementById('betValue');
  const betMirror = document.getElementById('v3BetMirror');

  // ---------- Тултипы: одновременно открыт максимум один ----------

  function setMenuOpen(open) {
    menu.classList.toggle('is-open', open);
    menuBtn.classList.toggle('is-open', open);
    menuBtn.setAttribute('aria-expanded', String(open));
  }

  function setTipOpen(tip, btn, open) {
    tip.hidden = !open;
    btn.classList.toggle('is-active', open);
    btn.setAttribute('aria-expanded', String(open));
  }

  // Открытие любой панели закрывает остальные — как в макете, где состояния
  // "меню раскрыто" / "ставка" / "автоспины" показаны по отдельности.
  function closeAll(except) {
    if (except !== 'menu') setMenuOpen(false);
    if (except !== 'bet') setTipOpen(betTip, betBtn, false);
    if (except !== 'auto') setTipOpen(autoTip, autoBtn, false);
  }

  menuBtn.addEventListener('click', () => {
    const next = !menu.classList.contains('is-open');
    closeAll('menu');
    setMenuOpen(next);
  });

  betBtn.addEventListener('click', () => {
    const next = betTip.hidden;
    closeAll('bet');
    setTipOpen(betTip, betBtn, next);
  });

  autoBtn.addEventListener('click', () => {
    const next = autoTip.hidden;
    closeAll('auto');
    setTipOpen(autoTip, autoBtn, next);
  });

  // Клик мимо бара — закрыть всё раскрытое.
  document.addEventListener('pointerdown', (event) => {
    if (!bar.contains(event.target)) closeAll(null);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAll(null);
  });

  // ---------- Ставка ----------

  // Крупное число в тултипе — зеркало #betValue, который обновляет app.js
  // (renderBet). Наблюдаем за ним, чтобы не трогать app.js.
  function syncBetMirror() {
    betMirror.textContent = betValue.textContent;
  }
  syncBetMirror();
  new MutationObserver(syncBetMirror).observe(betValue, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  // ---------- Автоспины (заглушка) ----------

  // Выбранное число показывается в кольце SPIN — то самое состояние из макета
  // (счётчик между стрелками). Реальный автозапуск появится вместе с логикой.
  autoTip.querySelectorAll('.v3-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const wasActive = chip.classList.contains('is-active');
      autoTip.querySelectorAll('.v3-chip').forEach((c) => c.classList.remove('is-active'));

      if (wasActive) {
        spinCount.hidden = true;
        autoBtn.classList.remove('is-active');
      } else {
        chip.classList.add('is-active');
        spinCount.textContent = chip.dataset.spins;
        spinCount.hidden = false;
      }
      spinBtn.classList.toggle('has-count', !spinCount.hidden);
      closeAll(null);
    });
  });

  // ---------- Турбо (заглушка) ----------

  turboBtn.addEventListener('click', () => {
    const next = !turboBtn.classList.contains('is-active');
    turboBtn.classList.toggle('is-active', next);
    turboBtn.setAttribute('aria-pressed', String(next));
  });

  // ---------- Домой ----------

  // В старом баре кнопка была декоративной; ведём туда же, куда ссылка
  // "В каталог" в шапке.
  bar.querySelector('[data-action="home"]').addEventListener('click', () => {
    window.location.href = 'games.html';
  });

  // Выбор пункта меню закрывает флайаут — кроме звука, чтобы было видно,
  // как переключается его состояние.
  bar.querySelector('[data-action="info"]').addEventListener('click', () => setMenuOpen(false));
})();
