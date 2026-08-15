// Constructor v2 — Page 3 (Layout editor).
//
// The design canvas per the ТЗ: desktop height FIXED 940 / width range
// 1612–1932; mobile width FIXED 780 / height range 1216–1416. Each element is
// stored anchor-relative — { anchorH, anchorV, dx, dy } — so one layout is
// correct at both the min and max bound of the flexible axis (toggle top-right).
// Fixed axis behaves like plain pixels; flexible axis follows the anchor.
(function () {
  const draft = Draft.load();
  if (!draft.base) { location.replace('setup.html'); return; }

  draft.layout = draft.layout || {};
  const previews = {}; // assetId -> object URL (in-session override, optional)

  // Real uploaded assets come from the backend manifest (Stage 2). Resolve an
  // element's role -> a concrete image file for the CURRENT screen (device +
  // base/bonus) so backgrounds / frame / logo / buttons render as their real art.
  const slugParam = new URLSearchParams(location.search).get('slug') || draft.backendSlug;
  let manifest = null;
  async function loadManifest() {
    if (!slugParam || !window.BuilderAPI) return;
    try {
      manifest = await BuilderAPI.request('GET', `/games/${slugParam}`);
      renderPalette();
      renderElements();
    } catch (e) { /* keep placeholders if the backend/game isn't reachable */ }
  }
  function assetForRole(role, scr) {
    if (!manifest || !slugParam) return null;
    const dev = scr.device === 'desk' ? 'desktop' : 'mobile';
    const imgs = manifest.assets.images;
    const dvOk = (i) => i.device === dev || i.device === 'both';
    const scOk = (i, want) => i.screen === want || i.screen === 'both';
    // Prefer an exact device/screen match over a "both"-tagged fallback, so e.g.
    // bg_base_desk wins over a shared background on the desktop-base screen.
    const score = (i, want) => (i.device === dev ? 2 : 0) + (want && i.screen === want ? 1 : 0);
    const pick = (pred, want) => {
      const m = imgs.filter(pred);
      if (!m.length) return null;
      m.sort((a, b) => score(b, want) - score(a, want));
      return m[0];
    };
    const cat = (c, want) => pick((i) => i.category === c && dvOk(i) && (want ? scOk(i, want) : true), want);
    const ui = (re) => pick((i) => i.category === 'ui' && re.test(i.file) && dvOk(i), scr.mode);
    switch (role) {
      case 'bg_base': return cat('background', 'base');
      case 'bg_bonus': return cat('background', 'bonus');
      case 'frame': return cat('frame');
      case 'logo': return cat('logo');
      case 'reel_background': return cat('reel_background');
      case 'buy_bonus': return ui(/buy/i);
      case 'fs_counter': return ui(/free.?spin|fs|counter/i);
      case 'hw_counter': return ui(/counter|hold/i);
      case 'multi_counter': return ui(/multi|counter/i);
      default: return null;
    }
  }
  function assetUrlForRole(role, scr) {
    const img = assetForRole(role, scr);
    return img ? BuilderAPI.imgUrl(slugParam, img.file) : null;
  }
  // Uploaded images placeable directly in the "Другое" section. Only the clean
  // single-instance roles (bg / bonus bg / frame / logo / reel bg) "claim" a file
  // and hide it here — ui-category assets (counters, buttons, jackpots) have no
  // 1:1 role so they always stay available. Filtered to the current screen's
  // device (desktop screen shows desktop/both, mobile shows mobile/both) so a
  // device-specific file only appears where it belongs.
  const CLAIM_ROLES = ['bg_base', 'bg_bonus', 'frame', 'logo', 'reel_background'];
  function otherAssets(scr) {
    if (!manifest) return [];
    const dev = scr.device === 'desk' ? 'desktop' : 'mobile';
    const claimed = new Set();
    for (const r of CLAIM_ROLES) { const a = assetForRole(r, scr); if (a) claimed.add(a.file); }
    return manifest.assets.images.filter((i) =>
      i.category !== 'catalog' && (i.device === dev || i.device === 'both') && !claimed.has(i.file));
  }

  let screenId = SCREENS[0].id;
  let bound = 'max';
  let editMode = true;
  let selectedId = null;

  const stage = document.getElementById('stage');
  const stageWrap = document.getElementById('stageWrap');
  const paletteList = document.getElementById('paletteList');
  const props = document.getElementById('props');

  // --- Geometry ---
  function screen() { return SCREENS.find((s) => s.id === screenId); }
  function designSize() {
    const dev = DEVICES[screen().device];
    if (dev.fixed === 'height') return { w: bound === 'min' ? dev.wMin : dev.wMax, h: dev.h };
    return { w: dev.w, h: bound === 'min' ? dev.hMin : dev.hMax };
  }
  function elements() {
    draft.layout[screenId] = draft.layout[screenId] || { elements: [] };
    return draft.layout[screenId].elements;
  }
  function computeLeft(el, W) {
    if (el.anchorH === 'left') return el.dx;
    if (el.anchorH === 'right') return W - el.w - el.dx;
    return W / 2 - el.w / 2 + el.dx; // center
  }
  function computeTop(el, H) {
    if (el.anchorV === 'top') return el.dy;
    if (el.anchorV === 'bottom') return H - el.h - el.dy;
    return H / 2 - el.h / 2 + el.dy; // center
  }
  function setFromLeftTop(el, left, top, W, H) {
    if (el.anchorH === 'left') el.dx = Math.round(left);
    else if (el.anchorH === 'right') el.dx = Math.round(W - el.w - left);
    else el.dx = Math.round(left + el.w / 2 - W / 2);
    if (el.anchorV === 'top') el.dy = Math.round(top);
    else if (el.anchorV === 'bottom') el.dy = Math.round(H - el.h - top);
    else el.dy = Math.round(top + el.h / 2 - H / 2);
  }

  // --- Fit the stage into the editor viewport ---
  let scale = 1;
  function fitStage() {
    const { w, h } = designSize();
    stage.style.width = w + 'px';
    stage.style.height = h + 'px';
    const availW = stageWrap.clientWidth - 56;
    const availH = stageWrap.clientHeight - 56;
    scale = Math.min(availW / w, availH / h, 1);
    stage.style.transform = `scale(${scale})`;
    const scaler = document.getElementById('stageScaler');
    scaler.style.width = w * scale + 'px';
    scaler.style.height = h * scale + 'px';
    document.getElementById('dimsLabel').textContent =
      `${screen().label} · ${w}×${h} (${DEVICES[screen().device].fixed === 'height' ? 'H фикс' : 'W фикс'})`;
  }

  // --- Default placement per role (anchor-relative) ---
  function defaults(role) {
    const { w, h } = designSize();
    const base = BASES[draft.base];
    const map = {
      bg_base: { anchorH: 'center', anchorV: 'center', dx: 0, dy: 0, w, h, z: 0 },
      bg_bonus: { anchorH: 'center', anchorV: 'center', dx: 0, dy: 0, w, h, z: 0 },
      reel_background: { anchorH: 'center', anchorV: 'center', dx: 0, dy: -30, w: Math.round(Math.min(w * 0.66, base.reels * 160)), h: Math.round(Math.min(h * 0.64, base.rows * 160)), z: 1 },
      reels: (function () { const g = draft.gap || 10, cw = 150, ch = 150; return { anchorH: 'center', anchorV: 'center', dx: 0, dy: -30, gapX: g, gapY: g, cellW: cw, cellH: ch, w: base.reels * cw + (base.reels - 1) * g, h: base.rows * ch + (base.rows - 1) * g, z: 2 }; })(),
      frame: { anchorH: 'center', anchorV: 'center', dx: 0, dy: -30, w: Math.round(Math.min(w * 0.68, base.reels * 165)), h: Math.round(Math.min(h * 0.66, base.rows * 165)), z: 3 },
      logo: { anchorH: 'center', anchorV: 'top', dx: 0, dy: 24, w: 260, h: 150, z: 4 },
      spin_btn: { anchorH: 'center', anchorV: 'bottom', dx: 0, dy: 24, w: 120, h: 120, z: 5 },
      bet_field: { anchorH: 'center', anchorV: 'bottom', dx: 170, dy: 40, w: 150, h: 80, z: 5 },
      balance: { anchorH: 'right', anchorV: 'bottom', dx: 30, dy: 44, w: 190, h: 60, z: 5 },
      win: { anchorH: 'center', anchorV: 'bottom', dx: 0, dy: 150, w: 220, h: 60, z: 5 },
      turbo: { anchorH: 'center', anchorV: 'bottom', dx: 330, dy: 44, w: 70, h: 70, z: 5 },
      auto: { anchorH: 'center', anchorV: 'bottom', dx: -330, dy: 44, w: 70, h: 70, z: 5 },
      sound: { anchorH: 'left', anchorV: 'bottom', dx: 30, dy: 44, w: 60, h: 60, z: 5 },
      info: { anchorH: 'left', anchorV: 'bottom', dx: 100, dy: 44, w: 60, h: 60, z: 5 },
      buy_bonus: { anchorH: 'right', anchorV: 'center', dx: 20, dy: 0, w: 150, h: 150, z: 4 },
      fs_counter: { anchorH: 'center', anchorV: 'top', dx: 0, dy: 190, w: 200, h: 90, z: 4 },
      multi_counter: { anchorH: 'left', anchorV: 'center', dx: 20, dy: 0, w: 150, h: 120, z: 4 },
      hw_counter: { anchorH: 'center', anchorV: 'top', dx: 0, dy: 190, w: 200, h: 90, z: 4 },
      image: { anchorH: 'center', anchorV: 'center', dx: 0, dy: 0, w: 220, h: 130, z: 6 },
    };
    return map[role] || { anchorH: 'center', anchorV: 'center', dx: 0, dy: 0, w: 140, h: 90, z: 4 };
  }

  function roleLabel(role) {
    const all = [...BASE_ROLES, ...Object.values(MECHANICS).flatMap((m) => m.roles || [])];
    return (all.find((r) => r.id === role) || {}).label || role;
  }
  const ROLE_ICON = {
    logo: '🔤', bg_base: '🖼️', bg_bonus: '🌌', reel_background: '🎞️', reels: '🎰', frame: '🔲', spin_btn: '🌀',
    bet_field: '🎚️', balance: '💰', win: '🏆', turbo: '⚡', auto: '🔁', sound: '🔊', info: 'ℹ️',
    buy_bonus: '🛒', fs_counter: '🔢', multi_counter: '✖️', hw_counter: '🔢', image: '🧩',
  };

  // Default LOCKED UI panel — mirrors css/ui-bar-v3.css (one bar for all slots):
  // bottom-pinned, full width, non-deformable, always on top. Auto-present on
  // every screen, rendered as a pointer-events:none footprint (can't move/resize).
  const UI_PANEL_H = { desk: 380, mobi: 760 }; // design-px ≈ 2× the 190/380 CSS bar
  const UI_PANEL_Z = 99999;
  function ensureUiPanel() {
    const list = elements();
    if (!list.some((e) => e.role === 'ui_panel')) {
      list.push({ id: 'uipanel', role: 'ui_panel', locked: true });
      Draft.save(draft);
    }
  }

  // A fresh BASE screen starts with the whole base layer already placed (bg +
  // reel bg + slot + frame + logo) so a published game is complete without
  // hand-placing every piece. Only seeds a base screen that has nothing but the
  // locked UI panel — once anything else exists (incl. after deleting a seeded
  // element) it never re-seeds.
  const BASE_SEED_ROLES = ['bg_base', 'reel_background', 'reels', 'frame', 'logo'];
  function ensureBaseSeed() {
    if (screen().mode !== 'base') return;
    const list = elements();
    if (list.some((e) => e.role !== 'ui_panel')) return;
    for (const role of BASE_SEED_ROLES) {
      list.push({ id: 'e' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5) + role, role, assetId: role, ...defaults(role) });
    }
    Draft.save(draft);
  }
  function uiPanelNode(W, H) {
    const h = UI_PANEL_H[screen().device];
    const node = document.createElement('div');
    node.className = 'el el--uipanel';
    node.style.left = '0px';
    node.style.top = (H - h) + 'px';
    node.style.width = W + 'px';
    node.style.height = h + 'px';
    node.style.zIndex = UI_PANEL_Z;
    node.innerHTML = `<div class="uibar" style="--ubh:${h}px">
      <div class="uibar__readout uibar__readout--l"><span>BALANCE</span><b>1 000.00 ₴</b></div>
      <div class="uibar__cluster">
        <button class="uibar__btn"></button><button class="uibar__btn"></button>
        <div class="uibar__spin">▶</div>
        <button class="uibar__btn"></button><button class="uibar__btn"></button>
      </div>
      <div class="uibar__readout uibar__readout--r"><span>BET</span><b>2.00 ₴</b></div>
      <span class="uibar__lock">🔒 UI-панель (V3) · фиксированная, всегда сверху</span>
    </div>`;
    return node;
  }

  // --- Render ---
  function renderTabs() {
    const tabs = document.getElementById('screenTabs');
    tabs.innerHTML = '';
    for (const s of SCREENS) {
      const b = document.createElement('button');
      b.className = 'lay-tab' + (s.id === screenId ? ' is-on' : '');
      b.textContent = s.label;
      b.addEventListener('click', () => { screenId = s.id; selectedId = null; renderAll(); });
      tabs.appendChild(b);
    }
  }

  function renderPalette() {
    const roles = paletteRoles(draft.base, draft.mechanics)
      .concat(screen().mode === 'bonus' ? [{ id: 'bg_bonus', label: 'Фон бонуса' }] : []);
    const placed = new Set(elements().map((e) => e.role));
    paletteList.innerHTML = '';
    // Locked default UI panel — always present, can't be edited or removed.
    const uiItem = document.createElement('div');
    uiItem.className = 'pal-item is-placed';
    uiItem.innerHTML = '<span class="pal-item__ic">🎛️</span><span>UI-панель (V3)</span><span class="pal-item__placed">🔒 всегда</span>';
    paletteList.appendChild(uiItem);
    for (const r of roles) {
      const item = document.createElement('div');
      item.className = 'pal-item' + (placed.has(r.id) ? ' is-placed' : '');
      item.innerHTML = `<span class="pal-item__ic">${ROLE_ICON[r.id] || '▫️'}</span><span>${r.label}</span>`;
      if (placed.has(r.id)) item.insertAdjacentHTML('beforeend', '<span class="pal-item__placed">на сцене</span>');
      item.addEventListener('click', () => addElement(r.id));
      paletteList.appendChild(item);
    }

    // "Другое" — every uploaded file with no dedicated role, placeable directly.
    const others = otherAssets(screen());
    if (others.length) {
      const hdr = document.createElement('div');
      hdr.className = 'pal-section';
      hdr.textContent = 'Другое (загруженные файлы)';
      paletteList.appendChild(hdr);
      const placedFiles = new Set(elements().filter((e) => e.assetFile).map((e) => e.assetFile));
      for (const a of others) {
        const item = document.createElement('div');
        item.className = 'pal-item pal-item--asset';
        item.innerHTML = `<img class="pal-item__thumb" src="${BuilderAPI.imgUrl(slugParam, a.file)}" loading="lazy"><span class="pal-item__name">${a.file}</span>`;
        if (placedFiles.has(a.file)) item.insertAdjacentHTML('beforeend', '<span class="pal-item__placed">×' + elements().filter((e) => e.assetFile === a.file).length + '</span>');
        item.addEventListener('click', () => addCustomElement(a));
        paletteList.appendChild(item);
      }
    }
  }

  function renderElements() {
    const { w: W, h: H } = designSize();
    [...stage.querySelectorAll('.el')].forEach((n) => n.remove());
    ensureUiPanel();
    ensureBaseSeed();
    elements().forEach((e) => { if (e.role === 'reels' && e.cellW == null) reelsApplySize(e); });
    for (const el of elements()) {
      if (el.role === 'ui_panel') { stage.appendChild(uiPanelNode(W, H)); continue; }
      const node = document.createElement('div');
      node.className = 'el' + (el.role === 'reels' ? ' is-reels' : '') + (el.id === selectedId ? ' is-selected' : '');
      node.style.left = computeLeft(el, W) + 'px';
      node.style.top = computeTop(el, H) + 'px';
      node.style.width = el.w + 'px';
      node.style.height = el.h + 'px';
      node.style.zIndex = el.z;
      const url = el.assetFile ? BuilderAPI.imgUrl(slugParam, el.assetFile)
        : (previews[el.assetId] || assetUrlForRole(el.role, screen()));
      if (url) {
        const im = document.createElement('img');
        im.src = url;
        node.appendChild(im);
      } else if (el.role === 'reels') {
        node.appendChild(reelGrid(el));
      }
      const tag = document.createElement('span');
      tag.className = 'el__tag';
      tag.textContent = el.label || roleLabel(el.role);
      node.appendChild(tag);
      node.addEventListener('mousedown', (e) => startDrag(e, el, node));
      stage.appendChild(node);
    }
  }
  // Reel geometry = per-cell size + separate horizontal/vertical gaps (matches
  // the backend reel_block: cell_w/cell_h/gap_x/gap_y). The element's w/h are
  // DERIVED from these, so the box always exactly wraps the grid.
  function cellParams(el) {
    const base = BASES[draft.base];
    const legacy = (el.gap != null) ? el.gap : draft.gap;
    const gapX = el.gapX != null ? el.gapX : legacy;
    const gapY = el.gapY != null ? el.gapY : legacy;
    const cellW = el.cellW != null ? el.cellW : Math.max(1, Math.round(((el.w || base.reels * 150) - (base.reels - 1) * gapX) / base.reels));
    const cellH = el.cellH != null ? el.cellH : Math.max(1, Math.round(((el.h || base.rows * 150) - (base.rows - 1) * gapY) / base.rows));
    return { gapX, gapY, cellW, cellH };
  }
  function reelsApplySize(el) {
    const base = BASES[draft.base];
    const p = cellParams(el);
    el.gapX = p.gapX; el.gapY = p.gapY; el.cellW = p.cellW; el.cellH = p.cellH;
    el.w = base.reels * p.cellW + (base.reels - 1) * p.gapX;
    el.h = base.rows * p.cellH + (base.rows - 1) * p.gapY;
  }
  function reelGrid(el) {
    const g = document.createElement('div');
    const base = BASES[draft.base];
    const { gapX, gapY, cellW, cellH } = cellParams(el);
    g.style.cssText = `display:grid;column-gap:${Math.max(0, gapX)}px;row-gap:${Math.max(0, gapY)}px;width:100%;height:100%;grid-template-columns:repeat(${base.reels},${cellW}px);grid-template-rows:repeat(${base.rows},${cellH}px);justify-content:center;align-content:center`;
    for (let i = 0; i < base.reels * base.rows; i++) {
      const c = document.createElement('div');
      c.style.cssText = 'background:rgba(255,207,92,0.18);border-radius:4px';
      g.appendChild(c);
    }
    return g;
  }

  function addElement(role) {
    const existing = elements().find((e) => e.role === role);
    if (existing) { select(existing.id); return; }
    const d = defaults(role);
    const el = { id: 'e' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), role, assetId: role, ...d };
    elements().push(el);
    Draft.save(draft);
    renderPalette();
    renderElements();
    select(el.id);
  }

  // Place a specific uploaded file (from the "Другое" section) as a free image
  // element — multiple allowed, each bound to its own file, fully editable.
  function addCustomElement(asset) {
    const el = { id: 'e' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5),
      role: 'image', assetFile: asset.file, label: asset.file, ...defaults('image') };
    elements().push(el);
    Draft.save(draft);
    renderPalette();
    renderElements();
    select(el.id);
  }

  // --- Drag ---
  function startDrag(e, el, node) {
    if (!editMode) return;
    e.preventDefault();
    select(el.id);
    const { w: W, h: H } = designSize();
    const startX = e.clientX, startY = e.clientY;
    const left0 = computeLeft(el, W), top0 = computeTop(el, H);
    let moved = false;
    function move(ev) {
      const dxp = (ev.clientX - startX) / scale;
      const dyp = (ev.clientY - startY) / scale;
      if (Math.abs(dxp) + Math.abs(dyp) > 2) moved = true;
      setFromLeftTop(el, left0 + dxp, top0 + dyp, W, H);
      node.style.left = computeLeft(el, W) + 'px';
      node.style.top = computeTop(el, H) + 'px';
      if (props.hidden === false) syncProps();
    }
    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      if (moved) Draft.save(draft);
      positionProps(node);
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }

  // --- Selection + properties popover ---
  function selectedEl() { return elements().find((e) => e.id === selectedId); }
  function select(id) {
    selectedId = id;
    renderElements();
    const el = selectedEl();
    if (!el) { props.hidden = true; return; }
    openProps();
  }
  function openProps() {
    const el = selectedEl();
    if (!el) return;
    document.getElementById('propRole').textContent = roleLabel(el.role);
    // role select
    const sel = document.getElementById('propRoleSel');
    const roles = paletteRoles(draft.base, draft.mechanics).concat([{ id: 'bg_bonus', label: 'Фон бонуса' }]);
    sel.innerHTML = roles.map((r) => `<option value="${r.id}"${r.id === el.role ? ' selected' : ''}>${r.label}</option>`).join('');
    renderAnchorGrid();
    syncProps();
    props.hidden = false;
    const node = [...stage.querySelectorAll('.el')].find((n) => n.querySelector('.el__tag') && n.classList.contains('is-selected'));
    positionProps(node);
  }
  function syncProps() {
    const el = selectedEl(); if (!el) return;
    document.getElementById('propDx').value = el.dx;
    document.getElementById('propDy').value = el.dy;
    document.getElementById('propW').value = el.w;
    document.getElementById('propH').value = el.h;
    document.getElementById('propZ').value = el.z;
    // Reel geometry (cell size + separate H/V gaps) — only for the reel grid;
    // its W/H are derived from those, so lock the generic W/H inputs.
    const isReels = el.role === 'reels';
    document.querySelectorAll('.lay-reelsonly').forEach((r) => { r.hidden = !isReels; });
    document.getElementById('propW').disabled = isReels;
    document.getElementById('propH').disabled = isReels;
    if (isReels) {
      const p = cellParams(el);
      document.getElementById('propCellW').value = p.cellW;
      document.getElementById('propCellH').value = p.cellH;
      document.getElementById('propGapX').value = p.gapX;
      document.getElementById('propGapY').value = p.gapY;
    }
    renderAnchorGrid();
  }
  function positionProps(node) {
    if (!node) { props.style.left = '80px'; props.style.top = '160px'; return; }
    const r = node.getBoundingClientRect();
    let left = r.right + 14, top = r.top;
    if (left + 300 > window.innerWidth) left = Math.max(12, r.left - 314);
    top = Math.min(top, window.innerHeight - 360);
    top = Math.max(70, top);
    props.style.left = left + 'px';
    props.style.top = top + 'px';
  }
  const ANCHORS = [
    ['left', 'top'], ['center', 'top'], ['right', 'top'],
    ['left', 'center'], ['center', 'center'], ['right', 'center'],
    ['left', 'bottom'], ['center', 'bottom'], ['right', 'bottom'],
  ];
  function renderAnchorGrid() {
    const el = selectedEl(); if (!el) return;
    const grid = document.getElementById('anchorGrid');
    grid.innerHTML = '';
    for (const [h, v] of ANCHORS) {
      const b = document.createElement('button');
      const on = el.anchorH === h && el.anchorV === v;
      b.className = on ? 'is-on' : '';
      b.textContent = '·';
      b.title = `${h} / ${v}`;
      b.addEventListener('click', () => { el.anchorH = h; el.anchorV = v; el.dx = 0; el.dy = 0; Draft.save(draft); renderElements(); syncProps(); reselectNode(); });
      grid.appendChild(b);
    }
  }
  function reselectNode() {
    const node = [...stage.querySelectorAll('.el')].find((n) => n.classList.contains('is-selected'));
    positionProps(node);
  }

  // property inputs
  ['propDx', 'propDy', 'propW', 'propH', 'propZ'].forEach((id) => {
    document.getElementById(id).addEventListener('input', (e) => {
      const el = selectedEl(); if (!el) return;
      const v = Number(e.target.value) || 0;
      if (id === 'propDx') el.dx = v; else if (id === 'propDy') el.dy = v;
      else if (id === 'propW') el.w = v; else if (id === 'propH') el.h = v; else el.z = v;
      Draft.save(draft);
      renderElements();
      reselectNode();
    });
  });
  [['propCellW', 'cellW'], ['propCellH', 'cellH'], ['propGapX', 'gapX'], ['propGapY', 'gapY']].forEach(([id, key]) => {
    document.getElementById(id).addEventListener('input', (e) => {
      const el = selectedEl(); if (!el || el.role !== 'reels') return;
      const min = key.indexOf('cell') === 0 ? 1 : 0;
      el[key] = Math.max(min, Number(e.target.value) || 0);
      reelsApplySize(el);
      document.getElementById('propW').value = el.w;
      document.getElementById('propH').value = el.h;
      Draft.save(draft);
      renderElements();
      reselectNode();
    });
  });
  document.getElementById('propRoleSel').addEventListener('change', (e) => {
    const el = selectedEl(); if (!el) return;
    el.role = e.target.value; el.assetId = e.target.value;
    Draft.save(draft); renderPalette(); renderElements(); openProps();
  });
  document.getElementById('propDelete').addEventListener('click', () => {
    const el = selectedEl(); if (!el) return;
    draft.layout[screenId].elements = elements().filter((x) => x.id !== el.id);
    selectedId = null; Draft.save(draft);
    props.hidden = true; renderPalette(); renderElements();
  });
  document.getElementById('propClose').addEventListener('click', () => { props.hidden = true; selectedId = null; renderElements(); });
  document.getElementById('propSave').addEventListener('click', () => { Draft.save(draft); props.hidden = true; selectedId = null; renderElements(); });

  // deselect on empty stage click
  stage.addEventListener('mousedown', (e) => { if (e.target === stage || e.target.classList.contains('lay-stage__ruler')) { selectedId = null; props.hidden = true; renderElements(); } });

  // --- Toolbar ---
  document.getElementById('previewToggle').addEventListener('click', (e) => {
    const b = e.target.closest('.lay-seg'); if (!b) return;
    bound = b.dataset.bound;
    document.querySelectorAll('.lay-seg').forEach((s) => s.classList.toggle('is-on', s.dataset.bound === bound));
    fitStage(); renderElements(); reselectNode();
  });
  const editBtn = document.getElementById('editToggle');
  function applyEdit() {
    editBtn.classList.toggle('is-on', editMode);
    editBtn.textContent = editMode ? '● Редактирование' : '✎ Редактировать';
    stage.classList.toggle('is-edit', editMode);
    if (!editMode) { props.hidden = true; selectedId = null; renderElements(); }
  }
  editBtn.addEventListener('click', () => { editMode = !editMode; applyEdit(); });

  document.getElementById('doneBtn').addEventListener('click', () => {
    Draft.save(draft);
    document.getElementById('footInfo').textContent = 'Черновик сохранён ✓';
  });

  // --- Copy base-screen geometry onto the bonus screen (same device) ---
  // Carries size + position (anchor+offset+z) of bg / reels / frame / logo from
  // this device's base screen to its bonus screen, so the bonus screen starts
  // aligned with the base instead of re-laid-out by hand. bg_base → bg_bonus;
  // reels/frame/logo keep their role.
  const COPY_PAIRS = [['bg_base', 'bg_bonus'], ['reel_background', 'reel_background'], ['reels', 'reels'], ['frame', 'frame'], ['logo', 'logo']];
  const GEOM_KEYS = ['anchorH', 'anchorV', 'dx', 'dy', 'w', 'h', 'z', 'cellW', 'cellH', 'gapX', 'gapY'];
  function baseScreenIdFor(scr) {
    const s = SCREENS.find((x) => x.device === scr.device && x.mode === 'base');
    return s ? s.id : null;
  }
  function copyFromBase() {
    const bid = baseScreenIdFor(screen());
    if (!bid || bid === screenId) return;
    const baseEls = (draft.layout[bid] && draft.layout[bid].elements) || [];
    const list = elements();
    const newId = (i) => 'e' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5) + i;
    const grab = (src) => { const g = {}; GEOM_KEYS.forEach((k) => { if (src[k] !== undefined) g[k] = src[k]; }); return g; };
    let n = 0;
    // Fixed-role elements (bg / reel bg / reels / frame / logo).
    for (const [srcRole, dstRole] of COPY_PAIRS) {
      const src = baseEls.find((e) => e.role === srcRole);
      if (!src) continue;
      const dst = list.find((e) => e.role === dstRole);
      if (dst) Object.assign(dst, grab(src));
      else list.push({ id: newId(n), role: dstRole, assetId: dstRole, ...grab(src) });
      n++;
    }
    // Free "Другое" images (jackpots, extra buttons…) — matched by file name.
    for (const src of baseEls.filter((e) => e.role === 'image' && e.assetFile)) {
      const dst = list.find((e) => e.role === 'image' && e.assetFile === src.assetFile);
      if (dst) Object.assign(dst, grab(src));
      else list.push({ id: newId(n), role: 'image', assetFile: src.assetFile, label: src.label, ...grab(src) });
      n++;
    }
    Draft.save(draft);
    renderPalette();
    renderElements();
    document.getElementById('footInfo').textContent = n
      ? `Перенесено с базы: ${n} элем. (фон, барабан, рамка, логотип, джекпоты и др.) ✓`
      : 'На базовом экране этих элементов ещё нет';
  }
  function updateCopyBtn() {
    document.getElementById('copyFromBaseBtn').hidden = screen().mode !== 'bonus';
  }
  document.getElementById('copyFromBaseBtn').addEventListener('click', copyFromBase);

  function renderAll() { renderTabs(); renderPalette(); fitStage(); renderElements(); applyEdit(); updateCopyBtn(); }

  window.addEventListener('resize', () => { fitStage(); renderElements(); reselectNode(); });
  renderAll();
  loadManifest();
  if (slugParam) {
    const q = `?slug=${encodeURIComponent(slugParam)}`;
    const back = document.getElementById('backBtn'); if (back) back.href = 'assets.html' + q;
    const pub = document.getElementById('publishBtn'); if (pub) pub.href = 'publish.html' + q;
    const sp = document.getElementById('stepPublish'); if (sp) sp.href = 'publish.html' + q;
  }
  document.getElementById('footInfo').textContent = `${draft.name} · ${BASES[draft.base].label}`;
})();
