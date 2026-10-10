// SlotCore — общий каркас слотов, вынесенный из пер-игровых slot.js.
// Клоны разошлись в деталях, поэтому ядро строится на самом свежем варианте
// (dirty-money-mafia) и параметризуется конфигом; игра подключает ядро через
// тонкие обёртки, сохраняя свой публичный API (startReelLoop / landReel /
// pushScreenDim ...), так что app.js и остальной код игры не меняются.
//
// Что здесь есть:
//   SlotCore.wait(ms)
//   SlotCore.makeRandomSymbol(fillerCodes)      -> () => code
//   SlotCore.createReelMotion(cfg)              -> { startLoop, stopLoop, landReel }
//   SlotCore.createScreenDim(cfg)               -> { push, pop, run, isOpaque }
//
// Ядро не знает ни про Spine-стейдж, ни про режимы base/bonus — всё
// игрозависимое передаётся колбэками (playSfx, onOpaqueOn/Off, createCellNode).

window.SlotCore = (() => {
  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function makeRandomSymbol(fillerCodes) {
    return () => fillerCodes[Math.floor(Math.random() * fillerCodes.length)];
  }

  // --- Reel motion -----------------------------------------------------------
  //
  // Луп: полоса из 2 экранов (случайная тройка НАД текущими символами),
  // покоится сдвинутой вверх на экран и CSS-анимацией скроллится к 0 — сверху
  // всегда есть чем заезжать, нет пустой вспышки на границе цикла.
  // Посадка: финальные символы сверху, филлер под ними; полоса стартует
  // сдвинутой вверх и с easing съезжает к 0. Anticipation-колонка получает
  // линейный пре-ролл (ровный «ещё крутится» скролл без плато) и затем ту же
  // короткую посадку, что обычные колонки.
  //
  // cfg:
  //   cols, rows            — размер сетки
  //   getReelCols()         — [{ colEl, stripEl }] (живой массив игры)
  //   getRowStep()          — высота ряда в px (меняется на ресайзе)
  //   createCellNode(code)  — { cell } готовый DOM узла ячейки
  //   randomSymbolCode()    — код случайного филлера
  //   currentColumnCodes(col) — коды, стоящие в колонке сейчас (null -> филлер)
  //   playSfx(name)         — звук; имена в cfg.sounds
  //   sounds: { spinStart, reelStop, finalReelStop }
  //   timings: { loopStepMs, landFillerCount, landDurationMs }
  //   anticipation: { prerollMs, fillerCount }
  function createReelMotion(cfg) {
    const { cols, rows, timings, anticipation } = cfg;

    function startLoop() {
      cfg.playSfx(cfg.sounds.spinStart);
      const reelCols = cfg.getReelCols();
      const rowStep = cfg.getRowStep();
      for (let col = 0; col < cols; col++) {
        const { stripEl } = reelCols[col];
        stripEl.style.transition = 'none';
        stripEl.classList.remove('is-looping');

        const currentCodes = cfg.currentColumnCodes(col).map((code) => code || cfg.randomSymbolCode());

        stripEl.innerHTML = '';
        const randomFill = Array.from({ length: rows }, cfg.randomSymbolCode);
        for (const code of [...randomFill, ...currentCodes]) {
          const { cell } = cfg.createCellNode(code);
          stripEl.appendChild(cell);
        }

        const screenful = rowStep * rows;
        stripEl.style.setProperty('--reel-loop-distance', `${screenful}px`);
        stripEl.style.setProperty('--reel-loop-duration', `${timings.loopStepMs}ms`);
        stripEl.style.transform = `translateY(${-screenful}px)`;
        void stripEl.offsetHeight;
        stripEl.classList.add('is-looping');
      }
    }

    function stopLoop() {
      for (const { stripEl } of cfg.getReelCols()) {
        stripEl.classList.remove('is-looping');
      }
    }

    function landReel(colIndex, finalCodes, delayMs, isAnticipating = false) {
      const reelCols = cfg.getReelCols();
      const rowStep = cfg.getRowStep();
      const { stripEl } = reelCols[colIndex];
      const stopSound = colIndex === cols - 1 ? cfg.sounds.finalReelStop : cfg.sounds.reelStop;
      const prerollCount = isAnticipating ? anticipation.fillerCount : 0;

      return new Promise((resolve) => {
        setTimeout(() => {
          stripEl.classList.remove('is-looping');
          stripEl.style.transition = 'none';
          stripEl.innerHTML = '';

          const sequence = [
            ...finalCodes,
            ...Array.from({ length: timings.landFillerCount }, cfg.randomSymbolCode),
            ...Array.from({ length: prerollCount }, cfg.randomSymbolCode),
          ];
          const cellEls = sequence.map((code) => {
            const { cell } = cfg.createCellNode(code);
            stripEl.appendChild(cell);
            return cell;
          });

          const landStartY = -(timings.landFillerCount * rowStep);

          const beginLanding = () => {
            stripEl.style.transition = `transform ${timings.landDurationMs}ms cubic-bezier(0.19, 0.79, 0.24, 1)`;
            stripEl.style.transform = 'translateY(0px)';

            setTimeout(() => cfg.playSfx(stopSound), Math.max(0, timings.landDurationMs - 200));

            let settled = false;
            const finish = () => {
              if (settled) return;
              settled = true;
              if (isAnticipating) reelCols[colIndex].colEl.classList.remove('is-anticipating');
              stripEl.removeEventListener('transitionend', onTransitionEnd);
              for (const cell of cellEls.slice(rows)) cell.remove();
              stripEl.style.transition = 'none';
              stripEl.style.transform = 'translateY(0px)';
              resolve(cellEls.slice(0, rows));
            };
            const onTransitionEnd = (event) => {
              if (event.target === stripEl && event.propertyName === 'transform') finish();
            };
            stripEl.addEventListener('transitionend', onTransitionEnd);
            // Страховка: transitionend не придёт, если вкладка скрыта или
            // анимации отключены — финализируем по таймеру в любом случае.
            setTimeout(finish, timings.landDurationMs + 200);
          };

          if (isAnticipating) {
            const prerollStartY = -((timings.landFillerCount + prerollCount) * rowStep);
            stripEl.style.transform = `translateY(${prerollStartY}px)`;
            void stripEl.offsetHeight;
            stripEl.style.transition = `transform ${anticipation.prerollMs}ms linear`;
            stripEl.style.transform = `translateY(${landStartY}px)`;

            setTimeout(() => {
              stripEl.style.transition = 'none';
              stripEl.style.transform = `translateY(${landStartY}px)`;
              void stripEl.offsetHeight;
              beginLanding();
            }, anticipation.prerollMs);
            return;
          }

          stripEl.style.transform = `translateY(${landStartY}px)`;
          void stripEl.offsetHeight;
          beginLanding();
        }, delayMs);
      });
    }

    return { startLoop, stopLoop, landReel };
  }

  // --- Screen dim ------------------------------------------------------------
  //
  // Счётный туман поверх экрана: вложенные push'ы складываются, класс снимается
  // только когда счётчик обнулился. Opaque-вариант (blackout перехода
  // base<->bonus) считается отдельным счётчиком и дополнительно дёргает
  // игровые хуки (притушить canvas-слой, снять/вернуть Spine-инстансы —
  // ядро про них ничего не знает).
  //
  // cfg: { el | elId, transitionMs, onOpaqueOn?, onOpaqueOff? }
  function createScreenDim(cfg) {
    const el = () => cfg.el || document.getElementById(cfg.elId);
    let activeCount = 0;
    let opaqueCount = 0;

    function push(opaque = false) {
      activeCount += 1;
      el().classList.add('is-active');
      if (opaque) {
        opaqueCount += 1;
        el().classList.add('is-opaque');
        if (opaqueCount === 1 && cfg.onOpaqueOn) cfg.onOpaqueOn();
      }
    }

    function pop(opaque = false) {
      activeCount = Math.max(0, activeCount - 1);
      if (activeCount === 0) el().classList.remove('is-active');
      if (opaque) {
        opaqueCount = Math.max(0, opaqueCount - 1);
        if (opaqueCount === 0) {
          el().classList.remove('is-opaque');
          if (cfg.onOpaqueOff) cfg.onOpaqueOff();
        }
      }
    }

    async function run(mutateFn, { opaque = false } = {}) {
      push(opaque);
      await wait(cfg.transitionMs);
      try {
        await mutateFn();
      } finally {
        pop(opaque);
      }
    }

    return { push, pop, run, isOpaque: () => opaqueCount > 0 };
  }

  return { wait, makeRandomSymbol, createReelMotion, createScreenDim };
})();
