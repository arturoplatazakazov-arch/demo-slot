// Диагностика рендера, подключается только по ?diag=1 (см. хвост
// lucky-joker-3h3.html). Нужна для браузеров, куда не дотянуться отладчиком:
// собирает всё, что мешает Spine-канвасу показывать анимации, и отправляет
// отчёт в access-log бэкенда — его видно из терминала.
(() => {
  const lines = [];
  const log = (l) => {
    lines.push(l);
    let box = document.getElementById('zzDiag');
    if (!box) {
      box = document.createElement('div');
      box.id = 'zzDiag';
      box.style.cssText = 'position:fixed;left:0;bottom:0;z-index:9999;max-width:100%;' +
        'background:rgba(0,0,0,.85);color:#eee;font:11px/1.35 ui-monospace,Menlo,monospace;' +
        'padding:6px 8px;white-space:pre-wrap;pointer-events:none';
      document.body.appendChild(box);
    }
    box.textContent = lines.join('\n');
  };

  const send = (tag) => {
    const report = lines.join(' | ').replace(/\s+/g, ' ').slice(0, 1800);
    fetch('http://127.0.0.1:8000/health?' + tag + '=' + encodeURIComponent(report), { mode: 'no-cors' });
  };

  window.addEventListener('error', (e) => log('JS ERROR: ' + e.message + ' @' + (e.filename || '').split('/').pop() + ':' + e.lineno));
  window.addEventListener('unhandledrejection', (e) => log('REJECT: ' + (e.reason && e.reason.message)));

  const canvas = document.getElementById('spineCanvas');
  canvas.addEventListener('webglcontextlost', () => { log('!! WEBGL CONTEXT LOST'); send('diagGame'); });
  canvas.addEventListener('webglcontextrestored', () => log('webgl context restored'));

  log('UA ' + navigator.userAgent.slice(0, 60));
  log('dpr ' + window.devicePixelRatio);

  // Второй этап: то, на что жалуются — СТАРТ win-анимации. Берём ячейку с
  // обычным символом (у него нет idle, он живёт статикой), запускаем его
  // win-клип и смотрим, появились ли пиксели ИМЕННО в этой ячейке.
  function probeWinAnimation() {
    const stage = window.__slot.stage;
    const gl = stage.spineCanvas.gl;
    const dpr = window.devicePixelRatio || 1;
    const info = window.__slot.cellInfos.find((c) => c && !['scatter', 'wild'].includes(c.symbol));
    if (!info) { log('нет обычного символа для теста'); send('diagGame'); return; }

    const rectPixels = () => {
      const r = info.cell.getBoundingClientRect();
      const cr = canvas.getBoundingClientRect();
      const x = Math.max(0, Math.round((r.left - cr.left) * dpr));
      const y = Math.max(0, Math.round((cr.bottom - r.bottom) * dpr)); // GL — снизу вверх
      const w = Math.max(1, Math.min(Math.round(r.width * dpr), canvas.width - x));
      const h = Math.max(1, Math.min(Math.round(r.height * dpr), canvas.height - y));
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      let hits = 0;
      for (let i = 3; i < buf.length; i += 4) if (buf[i] > 0) hits++;
      return hits;
    };

    log('тестовая ячейка: ' + info.symbol + ', instance=' + !!info.instance);
    requestAnimationFrame(() => {
      log('до win: ' + rectPixels() + ' px в ячейке');
      previewSymbolWin(info);            // ровно то, что игра зовёт на выигрыш
      let checks = 0;
      const after = () => {
        checks++;
        const px = rectPixels();
        const vis = getComputedStyle(info.img).visibility;
        if (checks >= 3 || px > 0) {
          log('после win (кадр ' + checks + '): ' + px + ' px, img visibility=' + vis +
              ', на канвасе=' + stage.baseInstances.includes(info.instance));
          log('VERDICT win: ' + (px > 0 ? 'анимация рисуется' : 'ячейка ПУСТА — символ пропал'));
          probeSpin();
          return;
        }
        setTimeout(() => requestAnimationFrame(after), 250);
      };
      setTimeout(() => requestAnimationFrame(after), 250);
    });
  }

  // Третий этап: настоящий спин. Ищем ячейки, которые стали НЕВИДИМЫМИ —
  // статика спрятана, а инстанса на канвасе нет: это и есть «символ пропал».
  function probeSpin() {
    const stage = window.__slot.stage;
    const invisible = () => window.__slot.cellInfos
      .map((info, i) => {
        if (!info) return 'нет cellInfo #' + i;
        const hidden = getComputedStyle(info.img).visibility === 'hidden' || !info.img.getAttribute('src');
        const onCanvas = info.instance && stage.baseInstances.includes(info.instance);
        return (hidden && !onCanvas) ? (i + ':' + info.symbol) : null;
      })
      .filter(Boolean);

    const spinBtn = document.querySelector('[data-action="spin"]');
    log('спин: session=' + (window.gameState && !!gameState.sessionId));
    spinBtn.click();

    let step = 0;
    const watch = () => {
      step++;
      const bad = invisible();
      log('t+' + (step * 1.5) + 's: сетка ' + window.__slot.cellInfos.map((c) => c && c.symbol).join(',').slice(0, 60) +
          ' | невидимых: ' + (bad.length ? bad.join(' ') : 'нет'));
      if (step >= 4) {
        log('VERDICT спин: ' + (invisible().length ? 'ЕСТЬ пропавшие ячейки' : 'все символы на месте'));
        send('diagGame');
        return;
      }
      setTimeout(watch, 1500);
    };
    setTimeout(watch, 1500);
  }

  const waitForSlot = setInterval(() => {
    if (!window.__slot) return;
    clearInterval(waitForSlot);
    const stage = window.__slot.stage;
    const am = stage.assetManager;
    const gl = stage.spineCanvas.gl;

    log('assets loaded/toLoad ' + am.loaded + '/' + am.toLoad);
    const errs = Object.keys(am.errors || {});
    log('asset errors (' + errs.length + '): ' + (errs.slice(0, 4).map((e) => e.split('/').slice(-2).join('/')).join(', ') || 'нет'));
    log('base instances ' + stage.baseInstances.length + ', overlays ' + stage.overlayInstances.length);
    log('canvas backing ' + canvas.width + 'x' + canvas.height);
    log('gl lost? ' + gl.isContextLost());

    // Сколько кадров успел отрисовать движок — 0 значит цикл не стартовал
    // (вендорный SpineCanvas не запускает его, если у AssetManager есть ошибки).
    setTimeout(() => {
      log('frames after 2s: ' + stage.spineCanvas.time.frameCount);

      // Замер ВНУТРИ кадра: иначе буфер уже очищен композитором.
      const probe = () => {
        const w = canvas.width, h = canvas.height;
        const buf = new Uint8Array(w * h * 4);
        try { gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf); }
        catch (e) { log('readPixels FAIL ' + e.message); send('diagGame'); return; }
        let hits = 0, maxA = 0;
        for (let i = 3; i < buf.length; i += 4) { if (buf[i] > 0) hits++; if (buf[i] > maxA) maxA = buf[i]; }
        log('IN-FRAME pixels: ' + hits + ' (maxAlpha ' + maxA + ')');
        log('VERDICT idle: ' + (hits > 0 ? 'канвас рисует' : 'канвас ПУСТ'));
        probeWinAnimation();
      };
      requestAnimationFrame(probe);
    }, 2000);
  }, 200);
})();
