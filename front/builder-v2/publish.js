// Constructor v2 — Page 4 (Publish).
//
// Bridges the browser-only v2 layout to the backend so the GENERIC play runtime
// (front/play.html + js/play/*) can render and run the game:
//   1. Convert the anchor-relative v2 layout (4 screens) into manifest.layouts
//      objects (center x/y + w/h + type + image_ref) and POST them.
//   2. generate-config (auto-registers spine symbols → real reel art).
//   3. test-spin.
//   4. publish-live → catalog card + playable play.html?slug=.
(function () {
  const params = new URLSearchParams(location.search);
  const draft = Draft.load();
  const SLUG = params.get('slug') || draft.backendSlug;

  const main = document.getElementById('main');
  if (!SLUG) {
    main.innerHTML = '<div class="empty-note">Игра ещё не создана — вернись на <a href="setup.html">шаг 1</a>.</div>';
    return;
  }
  document.getElementById('backBtn').href = `layout.html?slug=${encodeURIComponent(SLUG)}`;
  document.getElementById('stepLayout').href = `layout.html?slug=${encodeURIComponent(SLUG)}`;

  // Canonical design space = the max bound of each device (matches manifest.layouts w/h).
  const DESIGN = { desktop: { w: 1932, h: 940 }, mobile: { w: 780, h: 1416 } };
  const SCREEN_MAP = [
    { sid: 'desk-base', device: 'desktop', screen: 'base' },
    { sid: 'desk-bonus', device: 'desktop', screen: 'bonus' },
    { sid: 'mobi-base', device: 'mobile', screen: 'base' },
    { sid: 'mobi-bonus', device: 'mobile', screen: 'bonus' },
  ];
  // Controls come from the generic engine's own UI, not layout objects.
  const CONTROL_SKIP = new Set(['spin_btn', 'bet_field', 'balance', 'win', 'turbo', 'auto', 'sound', 'info']);

  let manifest = null;
  let symbolArt = null; // code -> url, for the test-spin preview

  function status(id, msg, kind) {
    const el = document.getElementById(id);
    el.textContent = msg || '';
    el.className = 'pub-status' + (kind ? ' is-' + kind : '');
  }
  function markDone(stepId) { document.getElementById(stepId).classList.add('is-done'); }

  // --- Geometry (mirror layout.js) ---
  function computeLeft(el, W) {
    if (el.anchorH === 'left') return el.dx;
    if (el.anchorH === 'right') return W - el.w - el.dx;
    return W / 2 - el.w / 2 + el.dx;
  }
  function computeTop(el, H) {
    if (el.anchorV === 'top') return el.dy;
    if (el.anchorV === 'bottom') return H - el.h - el.dy;
    return H / 2 - el.h / 2 + el.dy;
  }

  // --- Asset resolution from the manifest ---
  function idOf(img) { return img ? img.id : null; }
  function imgByCat(cat, screen, device) {
    const m = manifest.assets.images.filter((i) =>
      i.category === cat && (i.screen === screen || i.screen === 'both')
      && (i.device === device || i.device === 'both'));
    if (!m.length) return null;
    m.sort((a, b) => ((b.device === device ? 2 : 0) + (b.screen === screen ? 1 : 0))
      - ((a.device === device ? 2 : 0) + (a.screen === screen ? 1 : 0)));
    return m[0];
  }
  function imgByUi(re, device) {
    const m = manifest.assets.images.filter((i) => i.category === 'ui' && re.test(i.file)
      && (i.device === device || i.device === 'both'));
    return m.length ? m[0] : null;
  }
  function imgByFile(file) { return manifest.assets.images.find((i) => i.file === file) || null; }

  // --- Convert one screen's v2 elements → {objects, background} ---
  function convertScreen(sm) {
    const els = (draft.layout[sm.sid] && draft.layout[sm.sid].elements) || [];
    const { w: W, h: H } = DESIGN[sm.device];
    const objects = [];
    let background = null;
    for (const el of els) {
      if (el.role === 'ui_panel' || CONTROL_SKIP.has(el.role)) continue;
      const w = Math.max(1, Math.round(el.w || 1));
      const h = Math.max(1, Math.round(el.h || 1));
      const x = Math.round(computeLeft(el, W) + w / 2);
      const y = Math.round(computeTop(el, H) + h / 2);
      const geo = { id: el.id, x, y, w, h, z_index: el.z || 0 };

      if (el.role === 'bg_base' || el.role === 'bg_bonus') {
        const a = imgByCat('background', sm.screen, sm.device);
        if (a) background = { asset_id: a.id, x, y, w, h };
        continue;
      }
      if (el.role === 'reels') {
        objects.push({
          ...geo, type: 'system.reel_block', role: 'slot_reel_block',
          cell_w: Math.max(1, el.cellW || Math.round(w / (BASES[draft.base].reels || 1))),
          cell_h: Math.max(1, el.cellH || Math.round(h / (BASES[draft.base].rows || 1))),
          gap_x: Math.max(0, el.gapX || 0), gap_y: Math.max(0, el.gapY || 0),
        });
        continue;
      }
      let type = 'decor.image', imageRef = null, role = null;
      if (el.role === 'frame') { type = 'decor.frame'; imageRef = idOf(imgByCat('frame', sm.screen, sm.device)); role = 'slot_frame'; }
      else if (el.role === 'reel_background') { type = 'decor.reel_background'; imageRef = idOf(imgByCat('reel_background', sm.screen, sm.device)); }
      else if (el.role === 'logo') { type = 'decor.image'; imageRef = idOf(imgByCat('logo', sm.screen, sm.device)); role = 'slot_logo'; }
      else if (el.role === 'hero') { type = 'decor.hero'; imageRef = idOf(imgByCat('hero', sm.screen, sm.device)); }
      else if (el.role === 'fs_counter') { type = 'decor.hud'; imageRef = idOf(imgByUi(/free.?spin|fs|counter/i, sm.device)); role = 'free_spins_counter'; }
      else if (el.role === 'hw_counter' || el.role === 'multi_counter') { type = 'decor.hud'; imageRef = idOf(imgByUi(/counter|multi|hold/i, sm.device)); }
      else if (el.role === 'buy_bonus') { type = 'decor.image'; imageRef = idOf(imgByUi(/buy/i, sm.device)); role = 'buy_bonus'; }
      else if (el.role === 'image' && el.assetFile) { type = 'decor.image'; imageRef = idOf(imgByFile(el.assetFile)); }

      if (!imageRef) continue; // skip decor with no resolvable art (keeps the screen clean)
      const obj = { ...geo, type, image_ref: imageRef };
      if (role) obj.role = role;
      objects.push(obj);
    }
    return { objects, background };
  }

  // --- Step 1: save layout ---
  async function saveLayout() {
    status('statusLayout', 'Конвертирую и сохраняю…', 'busy');
    try {
      let totalObjs = 0, totalBg = 0;
      const perScreen = [];
      for (const sm of SCREEN_MAP) {
        const { objects, background } = convertScreen(sm);
        await BuilderAPI.request('POST', `/games/${SLUG}/layout/objects`, { device: sm.device, screen: sm.screen, objects });
        if (background) { await BuilderAPI.request('POST', `/games/${SLUG}/layout/background`, { device: sm.device, screen: sm.screen, ...background }); totalBg++; }
        totalObjs += objects.length;
        perScreen.push(`${sm.device}/${sm.screen}: ${objects.length} об.${background ? ' + фон' : ''}`);
      }
      status('statusLayout', `Сохранено ✓  (${totalObjs} объектов, ${totalBg} фонов)\n${perScreen.join(' · ')}`, 'ok');
      markDone('pubStep1');
    } catch (err) {
      status('statusLayout', `Ошибка: ${err.message}`, 'error');
    }
  }

  // --- Step 2: generate config ---
  async function genConfig() {
    status('statusConfig', 'Собираю конфиг + подцепляю символы…', 'busy');
    try {
      const r = await BuilderAPI.request('POST', `/games/${SLUG}/generate-config`);
      status('statusConfig', `Готово ✓  символов: ${r.num_symbols}, линий: ${r.num_paylines}, фич: ${r.num_features} (config ${r.status})`, 'ok');
      markDone('pubStep2');
      manifest = await BuilderAPI.request('GET', `/games/${SLUG}`); // refresh (symbol images added)
    } catch (err) {
      status('statusConfig', `Ошибка: ${err.message}`, 'error');
    }
  }

  // --- Step 3: test-spin ---
  async function loadSymbolArt() {
    if (symbolArt) return symbolArt;
    symbolArt = {};
    try {
      const cfgId = manifest.game_config_id;
      if (!cfgId) return symbolArt;
      // draft config symbols via admin endpoint (code -> image_ref)
      const cfg = await BuilderAPI.request('GET', `/../configs/${cfgId}`);
      const id2file = {}; manifest.assets.images.forEach((i) => { id2file[i.id] = i.file; });
      for (const s of (cfg.symbols || [])) {
        if (s.image_ref && id2file[s.image_ref]) symbolArt[s.code] = BuilderAPI.imgUrl(SLUG, id2file[s.image_ref]);
      }
    } catch (e) { /* preview art is best-effort */ }
    return symbolArt;
  }
  function renderSpinGrid(container, grid, wins) {
    if (!Array.isArray(grid)) return;
    const cols = grid.length, rows = Array.isArray(grid[0]) ? grid[0].length : 0;
    const g = document.createElement('div');
    g.className = 'spin-grid';
    g.style.gridTemplateColumns = `repeat(${cols}, 44px)`;
    const winSet = new Set();
    (wins || []).forEach((w) => (w.positions || w.cells || []).forEach((p) => winSet.add(`${p[0]},${p[1]}`)));
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const code = grid[c] && grid[c][r];
        const cell = document.createElement('div');
        cell.className = 'spin-cell' + (winSet.has(`${c},${r}`) ? ' is-win' : '');
        const url = symbolArt && symbolArt[code];
        cell.innerHTML = url ? `<img src="${url}">` : (code || '');
        g.appendChild(cell);
      }
    }
    container.appendChild(g);
  }
  async function testSpin() {
    status('statusSpin', 'Кручу…', 'busy');
    try {
      if (!manifest.game_config_id) { status('statusSpin', 'Сначала собери конфиг (шаг 2).', 'error'); return; }
      await loadSymbolArt();
      const r = await BuilderAPI.request('POST', `/games/${SLUG}/test-spin`);
      const win = r.total_win ?? r.win ?? r.payout ?? 0;
      const el = document.getElementById('statusSpin');
      el.className = 'pub-status is-ok';
      el.textContent = `Спин ок ✓  выигрыш: ${win}`;
      const grid = r.grid || r.board || (r.result && r.result.grid);
      const wins = r.wins || r.lines || (r.result && r.result.wins);
      if (grid) renderSpinGrid(el, grid, wins);
      markDone('pubStep3');
    } catch (err) {
      status('statusSpin', `Ошибка: ${err.message}`, 'error');
    }
  }

  // --- Step 4: publish ---
  async function publish() {
    const badge = document.getElementById('pubBadge').value.trim();
    const description = document.getElementById('pubDescription').value.trim();
    if (!badge || !description) { status('statusPublish', 'Заполни бейдж и описание.', 'error'); return; }
    status('statusPublish', 'Публикую…', 'busy');
    try {
      await BuilderAPI.request('POST', `/games/${SLUG}/publish-live`, { badge, description });
      status('statusPublish', 'Опубликовано ✓ — игра в каталоге и играется.', 'ok');
      markDone('pubStep4');
      const links = document.getElementById('pubLinks');
      links.hidden = false;
      links.innerHTML = `<a href="../games.html" target="_blank">📋 Открыть каталог</a>`
        + `<a href="../play.html?slug=${encodeURIComponent(SLUG)}" target="_blank">🎮 Играть</a>`;
    } catch (err) {
      status('statusPublish', `Ошибка: ${err.message}`, 'error');
    }
  }

  // --- Summary + wiring ---
  async function loadSummary() {
    manifest = await BuilderAPI.request('GET', `/games/${SLUG}`);
    document.getElementById('slotName').textContent = `— ${manifest.meta.display_name} (${manifest.meta.slug})`;
    const grid = manifest.grid ? `${manifest.grid.reels}×${manifest.grid.rows}` : '—';
    const layoutScreens = Object.keys(draft.layout || {}).filter((k) => (draft.layout[k].elements || []).some((e) => e.role !== 'ui_panel')).length;
    document.getElementById('summary').innerHTML =
      `<div><span>Игра:</span> <b>${manifest.meta.display_name}</b></div>`
      + `<div><span>Сетка:</span> <b>${grid}</b></div>`
      + `<div><span>Механики:</span> <b>${(manifest.mechanics || []).join(', ') || '—'}</b></div>`
      + `<div><span>Ассеты:</span> <b>${manifest.assets.images.length} картинок · ${manifest.assets.animations.length} spine</b></div>`
      + `<div><span>Экраны с вёрсткой:</span> <b>${layoutScreens}/4</b></div>`;
    document.getElementById('footInfo').textContent = manifest.game_config_id ? 'Конфиг уже собран' : 'Конфиг ещё не собран';
  }

  document.getElementById('btnSaveLayout').addEventListener('click', saveLayout);
  document.getElementById('btnGenConfig').addEventListener('click', genConfig);
  document.getElementById('btnTestSpin').addEventListener('click', testSpin);
  document.getElementById('btnPublish').addEventListener('click', publish);

  loadSummary().catch((err) => {
    main.innerHTML = `<div class="empty-note">Не удалось загрузить игру «${SLUG}»: ${err.message}<br>Бэкенд (:8000) запущен?</div>`;
  });
})();
