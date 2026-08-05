// Anim Lab — renders every Spine animation + static image asset (from
// anim-lab-manifest.js) as a row with its own position-nudge controls, so
// misalignments can be measured in px and the same numbers reused as
// translate() offsets in the real slot front-end.
//
// Layout: one full-viewport Spine canvas shared by every row (same
// SpineStage/anchorEl pattern the actual games use — see spine-engine.js).
// Each row has an outer, never-moved frame (border + grid + crosshair) and
// an inner anchor/img that gets translated by the row's X/Y — so the
// crosshair always shows the untouched center to compare against.

(async function () {
  const STORAGE_PREFIX = 'animlab:offset:';

  const manifest = window.ANIM_LAB_MANIFEST;
  const listEl = document.getElementById('list');
  const canvasEl = document.getElementById('spineCanvas');
  const tabsEl = document.getElementById('gameTabs');
  const searchEl = document.getElementById('searchInput');
  const staticOnlyEl = document.getElementById('staticOnlyToggle');
  const resetAllBtn = document.getElementById('resetAllBtn');

  const stage = new SpineEngine.SpineStage(canvasEl);

  const rows = []; // every row controller, for filtering + reset-all
  let activeGame = 'all';

  // East Discovery's, Wild Western Story's, Sugar Galaxy's, Golden
  // Caravan's, and Dirty Money Mafia's Spine exports use straight
  // (non-premultiplied) alpha, unlike the other games here — see the same
  // flag in each one's own slot.js. Loading them as premultiplied (the
  // SpineResource.load default) gives glow/gradient attachments a hard,
  // wrongly-colored edge instead of a soft one — checked every game's own
  // slot.js by hand (`grep premultipliedAlpha`) rather than assuming, since
  // this list has been missing an entry before.
  const STRAIGHT_ALPHA_GAMES = new Set([
    'east-discovery', 'wild-western-story', 'sugar-galaxy', 'golden-caravan', 'dirty-money-mafia',
  ]);
  function spineLoadOptions(game) {
    return STRAIGHT_ALPHA_GAMES.has(game) ? { premultipliedAlpha: false } : undefined;
  }

  // Reverse of each game's own SYMBOL_FOLDERS map (front/js/slot.js,
  // front/js/east-discovery/slot.js, front/js/party-of-goods/slot.js) — the
  // short "code" each game's logic and STATIC_CONTENT_OFFSET tables key on,
  // which sometimes differs from the asset folder name anim-lab-manifest.js
  // uses (e.g. fruit-farm's "duck" code ships from the "guse" folder).
  // Kept in sync by hand — if a game remaps a folder, mirror it here too.
  const SYMBOL_CODE_BY_FOLDER = {
    'fruit-farm': {
      Scatter: 'scatter', Wild: 'wild', guse: 'duck', watermelon: 'watermelon', corn: 'corn',
      blueberry: 'blueberry', strawberry: 'strawberry', cow: 'cow', pear: 'pear', dog: 'dog',
    },
    'east-discovery': {
      scatter: 'scatter', wild: 'wild', coin: 'coin', collector_tiger: 'collector_tiger',
      'lp-blue': 'lp_blue', 'lp-green': 'lp_green', 'lp-pink': 'lp_pink', 'lp-red': 'lp_red',
      rare_cat: 'rare_cat', rare_fish: 'rare_fish', rare_papirus: 'rare_papirus',
    },
    'party-of-goods': {
      Scatter: 'scatter', Wild: 'wild', zeus: 'zeus', afrodita: 'afrodita', cupidon: 'cupidon',
      blue: 'blue', green: 'green', red: 'red', yelow: 'yellow',
      x2: 'x2', x3: 'x3', x5: 'x5', x7: 'x7', bomb_flash: 'boom',
    },
    // Neon Reels has no real neon-reels.html/slot.js yet, so there's no
    // actual SYMBOL_FOLDERS to reverse — this is a best-guess mapping
    // (lowercase folder name, SKATTER corrected to the "scatter" spelling
    // every other game uses) so calibration can still be saved and won't
    // sit unusable until that game gets built. If the real slot.js ends up
    // using different codes, this table (and any calibration.json entries
    // already saved under "neon-reels") will need to be updated to match.
    'neon-reels': {
      A: 'a', Coin: 'coin', J: 'j', K: 'k', Q: 'q',
      SKATTER: 'scatter', WILD: 'wild',
      geisha: 'geisha', samurai: 'samurai', sensei: 'sensei', yakudza: 'yakudza',
    },
    'wild-western-story': {
      scatter: 'scatter', wild: 'wild', wolf: 'wolf', whickey: 'whiskey', gun: 'gun',
      A: 'a', J: 'j', K: 'k', Q: 'q',
    },
    // Every folder here is spelled identically to its code — no remapping
    // needed. boom_bomb/boom_standart are deliberately absent: they're
    // one-shot explosion VFX exports (no SYMBOL_FOLDERS entry in slot.js,
    // same pattern as party-of-goods' standalone "boom" clip), not real
    // grid symbols, so their calibrate button correctly stays disabled.
    'sugar-galaxy': {
      scatter: 'scatter', wild: 'wild', bomb: 'bomb',
      hp_red: 'hp_red', hp_yellow: 'hp_yellow', hp_green: 'hp_green', hp_blue: 'hp_blue',
      lp_blue: 'lp_blue', lp_green: 'lp_green', lp_red: 'lp_red', lp_yellow: 'lp_yellow',
      x2: 'x2', x3: 'x3', x5: 'x5', x7: 'x7',
    },
    // Folder names here are the slot-builder-normalized Spine folders
    // (SYMBOL_FOLDERS values in golden-caravan/slot.js), not the separate
    // Export/ names used only for locating static.png (handled by
    // staticFolder/staticFile in the manifest, not by this code lookup).
    // "boom" (shared explosion VFX, no SYMBOL_FOLDERS entry) deliberately
    // absent, same as every other game's standalone VFX clip.
    'golden-caravan': {
      scatter: 'scatter', wild: 'wild', bomb: 'bomb',
      rare_faraon: 'rare_faraon', rare_skorobei: 'rare_skorobei', rare_snake: 'rare_snake',
      common_blue: 'common_blue', common_green: 'common_green', common_red: 'common_red', common_yellow: 'common_yellow',
      multiplier_x2: 'x2', multiplier_x3: 'x3', multiplier_x5: 'x5',
    },
    // Folder name == symbol code here too (slot-builder assembled game,
    // 1:1 contract with app/seed/dirty_money_mafia.py — see slot.js's own
    // comment on SYMBOL_FOLDERS). WOF (wheel of fortune) deliberately
    // absent: uploaded but no mechanic/layout references it yet, same
    // "real Spine export, not a real grid symbol" case as every other
    // game's standalone VFX/unused clip.
    'dirty-money-mafia': {
      scatter: 'scatter', wild: 'wild', rare_red: 'rare_red',
      rare_blue: 'rare_blue', rare_green: 'rare_green', rare_yellow: 'rare_yellow',
      common_blue: 'common_blue', common_green: 'common_green', common_red: 'common_red', common_yellow: 'common_yellow',
    },
  };

  function storageKey(rowId) {
    return STORAGE_PREFIX + rowId;
  }

  function loadOffset(rowId) {
    try {
      const raw = localStorage.getItem(storageKey(rowId));
      if (!raw) return { x: 0, y: 0 };
      const parsed = JSON.parse(raw);
      return { x: Number(parsed.x) || 0, y: Number(parsed.y) || 0 };
    } catch {
      return { x: 0, y: 0 };
    }
  }

  function saveOffset(rowId, x, y) {
    if (x === 0 && y === 0) {
      localStorage.removeItem(storageKey(rowId));
    } else {
      localStorage.setItem(storageKey(rowId), JSON.stringify({ x, y }));
    }
  }

  // Frame is sized to the content's real pixel dimensions (capped + scrollable
  // for huge backgrounds) so nothing is scaled to fit a box — every row shows
  // its asset at true 100% / original size. The crosshair is a separate
  // full-frame overlay, so with the frame sized exactly to the content its
  // center always lands exactly on the content's own bounds-center.
  function makeFrame(width, height) {
    const wrap = document.createElement('div');
    wrap.className = 'row__frame-wrap';
    const frame = document.createElement('div');
    frame.className = 'row__frame';
    frame.style.width = `${width}px`;
    frame.style.height = `${height}px`;
    const cross = document.createElement('div');
    cross.className = 'row__cross';
    frame.appendChild(cross);
    const dims = document.createElement('span');
    dims.className = 'row__dims';
    dims.textContent = `${Math.round(width)}×${Math.round(height)}px`;
    frame.appendChild(dims);
    wrap.appendChild(frame);
    return { wrap, frame };
  }

  function makeControls(rowId, label, sub, withCalibrate) {
    const meta = document.createElement('div');
    meta.className = 'row__meta';

    const labelEl = document.createElement('div');
    labelEl.className = 'row__label';
    labelEl.textContent = label;
    if (sub) {
      const small = document.createElement('small');
      small.textContent = sub;
      labelEl.appendChild(small);
    }

    const controls = document.createElement('div');
    controls.className = 'row__controls';

    const xField = document.createElement('label');
    xField.className = 'row__field';
    xField.innerHTML = 'X <input type="number" step="1">';
    const xInput = xField.querySelector('input');

    const yField = document.createElement('label');
    yField.className = 'row__field';
    yField.innerHTML = 'Y <input type="number" step="1">';
    const yInput = yField.querySelector('input');

    const resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'row__reset';
    resetBtn.textContent = 'Сброс';

    const readout = document.createElement('span');
    readout.className = 'row__readout';
    readout.title = 'Нажмите, чтобы скопировать translate()';

    controls.appendChild(xField);
    controls.appendChild(yField);
    controls.appendChild(resetBtn);

    let calibrateBtn = null;
    if (withCalibrate) {
      calibrateBtn = document.createElement('button');
      calibrateBtn.type = 'button';
      calibrateBtn.className = 'row__calibrate';
      calibrateBtn.textContent = 'Калибровать';
      calibrateBtn.title =
        'Сохранить смещение статики для этого символа и применить его сразу в реальном слоте (тот же браузер), плюс скопировать готовую строку dx/dy для кода';
      controls.appendChild(calibrateBtn);
    }

    controls.appendChild(readout);

    meta.appendChild(labelEl);
    meta.appendChild(controls);

    return { meta, xInput, yInput, resetBtn, readout, calibrateBtn };
  }

  function updateReadout(readout, x, y) {
    readout.textContent = `translate(${x}px, ${y}px)`;
    readout.classList.toggle('is-zero', x === 0 && y === 0);
  }

  function wireRow({ rowId, row, applyOffset, calibrate }) {
    const { meta, xInput, yInput, resetBtn, readout, calibrateBtn } = makeControls(rowId, row.label, row.sub, !!calibrate);
    row.wrap.parentElement || null; // no-op, keeps structure obvious

    // For a calibrate-capable row, the actually-saved calibration (already
    // loaded into SlotCalibration's cache by the time this runs) IS the
    // right initial value — it's what the real slot is showing right now.
    // Only fall back to the local "last slider position" memory when
    // nothing's been calibrated yet, so an in-progress, not-yet-saved nudge
    // still isn't lost across a reload.
    const initial = calibrate?.initial || loadOffset(rowId);
    let state = { x: initial.x, y: initial.y };
    xInput.value = state.x;
    yInput.value = state.y;
    updateReadout(readout, state.x, state.y);
    applyOffset(state.x, state.y);

    function commit() {
      state.x = Math.round(Number(xInput.value) || 0);
      state.y = Math.round(Number(yInput.value) || 0);
      applyOffset(state.x, state.y);
      updateReadout(readout, state.x, state.y);
      saveOffset(rowId, state.x, state.y);
    }

    function flashButton(btn, text, ok, holdMs) {
      const prevText = btn.textContent;
      btn.textContent = text;
      btn.classList.toggle('is-done', ok);
      btn.classList.toggle('is-error', !ok);
      setTimeout(() => {
        btn.textContent = prevText;
        btn.classList.remove('is-done', 'is-error');
      }, holdMs);
    }

    xInput.addEventListener('input', commit);
    yInput.addEventListener('input', commit);
    resetBtn.addEventListener('click', () => {
      xInput.value = 0;
      yInput.value = 0;
      commit();
      if (!calibrate?.onReset) return;
      calibrate.onReset().catch((err) => {
        console.error(err);
        alert(err.message || 'Не удалось сбросить калибровку на сервере');
      });
    });
    readout.addEventListener('click', () => {
      navigator.clipboard?.writeText(`transform: translate(${state.x}px, ${state.y}px);`);
      const prev = readout.textContent;
      readout.textContent = 'скопировано ✓';
      setTimeout(() => updateReadout(readout, state.x, state.y), 900);
      void prev;
    });

    if (calibrateBtn) {
      if (calibrate.unavailable) {
        // No game code to write to (e.g. Neon Reels) — shown, not hidden,
        // so this reads as "nothing to calibrate here" rather than a
        // missing button.
        calibrateBtn.disabled = true;
        calibrateBtn.title = calibrate.unavailable;
        calibrateBtn.classList.add('is-unavailable');
      } else {
        calibrateBtn.addEventListener('click', () => {
          calibrateBtn.disabled = true;
          calibrate
            .onCalibrate(state.x, state.y)
            .then(() => flashButton(calibrateBtn, 'Сохранено ✓', true, 1400))
            .catch((err) => {
              console.error(err);
              flashButton(calibrateBtn, 'Ошибка ✗', false, 2200);
              alert(err.message || 'Не удалось сохранить калибровку на сервере');
            })
            .finally(() => {
              calibrateBtn.disabled = false;
            });
        });
      }
    }

    return { meta, reset: () => resetBtn.click() };
  }

  function buildAnimRow(item, animName) {
    const rowId = `${item.game}:${item.name}:anim:${animName}`;
    const rowEl = document.createElement('div');
    rowEl.className = 'row';
    rowEl.dataset.kind = 'anim';

    const { wrap, frame } = makeFrame(item.width, item.height);
    const anchor = document.createElement('div');
    anchor.className = 'row__anchor';
    anchor.style.cssText = `flex: 0 0 auto; width:${item.width}px; height:${item.height}px;`;
    frame.appendChild(anchor);

    let instance = null;
    let loading = null;

    function activate() {
      if (instance) {
        stage.addBase(instance);
        return;
      }
      if (loading) return;
      loading = SpineEngine.SpineResource.load(stage.assetManager, item.folder, spineLoadOptions(item.game)).then((resource) => {
        instance = resource.createInstance();
        instance.anchorEl = anchor;
        instance.fit = 1; // anchor is sized to the skeleton's own bounds, so fit=1 renders at true 100% / original size
        instance.play(animName, true);
        stage.addBase(instance);
      });
    }
    function deactivate() {
      if (instance) stage.removeBase(instance);
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          rowEl.classList.toggle('is-visible', e.isIntersecting);
          if (e.isIntersecting) activate();
          else deactivate();
        }
      },
      { rootMargin: '150px' },
    );
    observer.observe(rowEl);

    const controller = wireRow({
      rowId,
      row: { wrap, label: animName, sub: null },
      applyOffset: (x, y) => {
        anchor.style.transform = `translate(${x}px, ${y}px)`;
      },
    });

    rowEl.appendChild(wrap);
    rowEl.appendChild(controller.meta);
    rows.push({ el: rowEl, game: item.game, name: item.name.toLowerCase(), type: 'anim', reset: controller.reset });
    return rowEl;
  }

  // Realistic highlight loop: static 0.5s -> this animation once -> static
  // 0.5s -> (next play, 1s after the previous one finished, since the tail
  // static of one cycle and the head static of the next are back-to-back) ->
  // repeat. This mirrors how a landed symbol actually pulses on the real
  // reels, so misalignment between the static art and the animation's own
  // centering shows up the same way it would in the game. Built for every
  // animation the symbol has (see buildElementSection), not just "win" —
  // a symbol like Wild Western Story's wild ships 6 clips (idle_big/
  // idle_small/landing_small/move/win_big/win_small), and the real game's
  // static-image calibration is one shared value for the whole symbol
  // regardless of which clip happens to be playing, so every clip needs to
  // be checked against it, not just the win one.
  //
  // Two rows are built per symbol per animation (see buildElementSection),
  // one per `mode`: 'static' moves the static <img> while the animation
  // stays centered (drives SlotCalibration's 'static' layer, same as
  // applyStaticContentOffset in each game's slot.js); 'anim' moves the
  // animation while the static art stays centered instead (drives the
  // 'anim' layer, applied on top of .reel__cell-anchor's own centering via
  // SlotCalibration.applyAnchorOffset). Whichever side ISN'T being dragged
  // in a given row stays untouched at its neutral (centered) position, so
  // each row isolates one variable at a time. Calibrating from ANY of a
  // symbol's animation rows writes to the same (game, code, kind) target —
  // that's intentional: try the offset against each clip, then hit
  // "Калибровать" on whichever row currently looks right.
  function buildWinCycleRow(item, animName, mode) {
    const rowId = `${item.game}:${item.name}:cycle:${mode}:${animName}`;
    const rowEl = document.createElement('div');
    rowEl.className = 'row';
    rowEl.dataset.kind = 'cycle';

    // Frame covers whichever phase is larger, so switching phases never
    // resizes/reflows the row — both phases render at their own true size,
    // centered by the frame's flex layout.
    const frameW = Math.max(item.width, item.staticWidth);
    const frameH = Math.max(item.height, item.staticHeight);
    const { wrap, frame } = makeFrame(frameW, frameH);
    const img = document.createElement('img');
    img.className = 'row__img';
    img.loading = 'lazy';
    img.src = `${item.staticFolder}/${item.staticFile}`;
    img.style.cssText = `flex: 0 0 auto; width:${item.staticWidth}px; height:${item.staticHeight}px;`;
    frame.appendChild(img);

    const anchor = document.createElement('div');
    anchor.style.cssText = `flex: 0 0 auto; width:${item.width}px; height:${item.height}px; display:none;`;
    frame.appendChild(anchor);

    const phase = document.createElement('span');
    phase.className = 'row__phase';
    phase.textContent = 'static';
    frame.appendChild(phase);

    let instance = null;
    let loadingPromise = null;
    let timers = [];
    let active = false;

    function clearTimers() {
      for (const t of timers) clearTimeout(t);
      timers = [];
    }

    function showStatic() {
      img.style.display = '';
      anchor.style.display = 'none';
      phase.textContent = 'static';
      if (instance) stage.removeBase(instance);
    }

    function showWin() {
      if (!active || !instance) return;
      img.style.display = 'none';
      anchor.style.display = '';
      phase.textContent = animName;
      instance.play(animName, false);
      stage.addBase(instance);
    }

    function ensureInstance() {
      if (instance) return Promise.resolve();
      if (loadingPromise) return loadingPromise;
      loadingPromise = SpineEngine.SpineResource.load(stage.assetManager, item.folder, spineLoadOptions(item.game)).then(
        (resource) => {
          instance = resource.createInstance();
          instance.anchorEl = anchor;
          instance.fit = 1; // anchor is sized to the skeleton's own bounds, so fit=1 renders at true 100% / original size
          instance.onSettle = () => {
            if (!active) return;
            showStatic();
            timers.push(setTimeout(showWin, 1000));
          };
        },
      );
      return loadingPromise;
    }

    function start() {
      active = true;
      ensureInstance().then(() => {
        if (!active) return;
        showStatic();
        timers.push(setTimeout(showWin, 500));
      });
    }
    function stop() {
      active = false;
      clearTimers();
      if (instance) stage.removeBase(instance);
      showStatic();
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          rowEl.classList.toggle('is-visible', e.isIntersecting);
          if (e.isIntersecting) start();
          else stop();
        }
      },
      { rootMargin: '150px' },
    );
    observer.observe(rowEl);

    // The real slot's own "code" for this symbol (SYMBOL_FOLDERS is keyed
    // by code, not folder name) — what SlotCalibration and the copied code
    // snippet both need. Every symbol folder used here does map to a real
    // grid code in its game (checked against each slot.js's SYMBOL_FOLDERS).
    const code = SYMBOL_CODE_BY_FOLDER[item.game]?.[item.name];
    const kind = mode === 'static' ? 'static' : 'anim';

    const isStaticMode = mode === 'static';
    const label = isStaticMode ? `${animName} · сдвиг статики` : `${animName} · сдвиг анимации`;
    const sub = isStaticMode
      ? `статика 0.5с → ${animName} → статика 0.5с (интервал 1с) — X/Y двигают только статику, ${animName} всегда по центру`
      : `статика 0.5с → ${animName} → статика 0.5с (интервал 1с) — X/Y двигают только ${animName}, статика всегда по центру`;

    const controller = wireRow({
      rowId,
      row: { wrap, label, sub },
      applyOffset: (x, y) => {
        // Only one side ever moves — the other is the fixed reference point,
        // so nudging X/Y shows exactly how far this side is from it.
        const t = `translate(${x}px, ${y}px)`;
        if (isStaticMode) img.style.transform = t;
        else anchor.style.transform = t;
      },
      // Always an object (never omitted) so the row always shows a
      // Калибровать button — when there's no game code to write to, it
      // renders disabled with a tooltip explaining why, instead of just
      // silently not being there (which reads as a bug, not "nothing to
      // calibrate"). One honest message covering both actual causes: the
      // whole game has no real slot.js yet (Neon Reels), or the game does
      // but this particular folder just isn't a referenced grid symbol
      // (e.g. dirty-money-mafia's WOF — uploaded but no mechanic/layout
      // uses it yet, same as any other game's standalone unused clip).
      calibrate: !code
        ? {
            unavailable: `«${item.name}» не привязан к коду символа в реальной игре — либо у ${item.gameLabel} ещё нет своего slot.js, либо это загруженный, но не используемый ассет`,
          }
        : {
            // Already-saved calibration (loaded before render() ran) — the
            // row should open showing what's actually live on the real
            // slot, not 0,0, so it never looks like a fresh nudge got lost.
            // SlotCalibration uses {dx,dy}, wireRow's state uses {x,y}.
            initial: (() => {
              const saved = SlotCalibration.get(item.game, code, kind);
              return saved && { x: saved.dx, y: saved.dy };
            })(),
            onCalibrate: (x, y) =>
              // Saved to front/calibration.json via the backend — a real
              // file on disk, survives server restarts/browser clears/other
              // machines, not just this browser's localStorage.
              SlotCalibration.set(item.game, code, x, y, kind).then(() => {
                // Also copy a ready-to-paste line — for the static layer
                // this matches the game's own STATIC_CONTENT_OFFSET table
                // format; the anim layer has no such table anywhere (it's
                // covered by calibration.json alone), so this is just a
                // readable record.
                navigator.clipboard?.writeText(`${code}: { dx: ${x}, dy: ${y} },`);
              }),
            onReset: () => SlotCalibration.clear(item.game, code, kind),
          },
    });

    rowEl.appendChild(wrap);
    rowEl.appendChild(controller.meta);
    rows.push({ el: rowEl, game: item.game, name: item.name.toLowerCase(), type: 'cycle', reset: controller.reset });
    return rowEl;
  }

  function buildStaticRow(item, src, label, width, height) {
    const rowId = `${item.game}:${item.name}:static`;
    const rowEl = document.createElement('div');
    rowEl.className = 'row';
    rowEl.dataset.kind = 'static';

    const { wrap, frame } = makeFrame(width, height);
    const img = document.createElement('img');
    img.className = 'row__img';
    img.loading = 'lazy';
    img.src = src;
    img.style.cssText = `flex: 0 0 auto; width:${width}px; height:${height}px;`;
    frame.appendChild(img);

    const controller = wireRow({
      rowId,
      row: { wrap, label: label || 'static', sub: null },
      applyOffset: (x, y) => {
        img.style.transform = `translate(${x}px, ${y}px)`;
      },
    });

    rowEl.appendChild(wrap);
    rowEl.appendChild(controller.meta);
    rows.push({ el: rowEl, game: item.game, name: item.name.toLowerCase(), type: 'static', reset: controller.reset });
    return rowEl;
  }

  function buildElementSection(item) {
    const section = document.createElement('section');
    section.className = 'element';
    section.dataset.game = item.game;
    section.dataset.name = item.name.toLowerCase();

    const title = document.createElement('h3');
    title.className = 'element__title';
    const gameSpan = document.createElement('span');
    gameSpan.className = 'element__game';
    gameSpan.textContent = item.gameLabel;
    const nameSpan = document.createElement('span');
    nameSpan.textContent = item.name;
    const badge = document.createElement('span');
    badge.className = 'element__badge';
    badge.textContent = item.kind;
    title.appendChild(gameSpan);
    title.appendChild(nameSpan);
    title.appendChild(badge);
    section.appendChild(title);

    if (item.hasStatic) {
      section.appendChild(buildStaticRow(item, `${item.staticFolder}/${item.staticFile}`, 'static', item.staticWidth, item.staticHeight));
      // A calibrate-capable pair (сдвиг статики / сдвиг анимации) for every
      // animation the symbol has, not just "win" — see buildWinCycleRow's
      // comment for why (one shared calibration value per symbol, checked
      // against every clip that might play over the static art).
      for (const animName of item.animations) {
        section.appendChild(buildWinCycleRow(item, animName, 'static'));
        section.appendChild(buildWinCycleRow(item, animName, 'anim'));
      }
    }
    for (const animName of item.animations) {
      section.appendChild(buildAnimRow(item, animName));
    }
    return section;
  }

  function render() {
    // Only reel-grid symbols — heroes, backgrounds/environment, and popups
    // aren't placed in the slot grid, so they're excluded here. Static
    // environment/UI assets (backgrounds, logos, signs, frames) are dropped
    // entirely for the same reason.
    const items = manifest.spineItems.filter((item) => item.kind === 'symbol').sort((a, b) => a.name.localeCompare(b.name));

    const frag = document.createDocumentFragment();
    for (const item of items) frag.appendChild(buildElementSection(item));
    listEl.appendChild(frag);
  }

  function buildTabs() {
    const allGames = [{ slug: 'all', label: 'Все' }, ...manifest.games];
    for (const g of allGames) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'lab__tab' + (g.slug === 'all' ? ' is-active' : '');
      btn.textContent = g.label;
      btn.dataset.slug = g.slug;
      btn.addEventListener('click', () => {
        activeGame = g.slug;
        for (const el of tabsEl.querySelectorAll('.lab__tab')) el.classList.toggle('is-active', el === btn);
        applyFilters();
      });
      tabsEl.appendChild(btn);
    }
  }

  function applyFilters() {
    const query = searchEl.value.trim().toLowerCase();
    const staticOnly = staticOnlyEl.checked;
    let anyVisible = false;

    for (const section of listEl.querySelectorAll('.element')) {
      const game = section.dataset.game;
      const name = section.dataset.name;
      const gameMatch = activeGame === 'all' || game === activeGame;
      const searchMatch = !query || name.includes(query);
      const sectionVisible = gameMatch && searchMatch;
      section.style.display = sectionVisible ? '' : 'none';
      if (!sectionVisible) continue;
      anyVisible = true;

      for (const rowEl of section.querySelectorAll('.row')) {
        const isStatic = rowEl.dataset.kind === 'static';
        rowEl.style.display = staticOnly && !isStatic ? 'none' : '';
      }
    }

    let empty = listEl.querySelector('.lab__empty');
    if (!anyVisible) {
      if (!empty) {
        empty = document.createElement('div');
        empty.className = 'lab__empty';
        empty.textContent = 'Ничего не найдено';
        listEl.appendChild(empty);
      }
    } else if (empty) {
      empty.remove();
    }
  }

  await SlotCalibration.load(); // so calibrated rows show their saved offset on first render, not 0,0
  render();
  buildTabs();
  applyFilters();

  searchEl.addEventListener('input', applyFilters);
  staticOnlyEl.addEventListener('change', applyFilters);
  resetAllBtn.addEventListener('click', () => {
    if (!confirm('Сбросить смещения у всех элементов?')) return;
    for (const r of rows) r.reset();
  });
})();
