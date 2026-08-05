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
  const previews = {}; // assetId -> object URL (none across reloads for now)

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
      reels: { anchorH: 'center', anchorV: 'center', dx: 0, dy: -30, w: Math.round(Math.min(w * 0.62, base.reels * 150)), h: Math.round(Math.min(h * 0.6, base.rows * 150)), z: 2 },
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
    };
    return map[role] || { anchorH: 'center', anchorV: 'center', dx: 0, dy: 0, w: 140, h: 90, z: 4 };
  }

  function roleLabel(role) {
    const all = [...BASE_ROLES, ...Object.values(MECHANICS).flatMap((m) => m.roles || [])];
    return (all.find((r) => r.id === role) || {}).label || role;
  }
  const ROLE_ICON = {
    logo: '🔤', bg_base: '🖼️', bg_bonus: '🌌', reels: '🎰', frame: '🔲', spin_btn: '🌀',
    bet_field: '🎚️', balance: '💰', win: '🏆', turbo: '⚡', auto: '🔁', sound: '🔊', info: 'ℹ️',
    buy_bonus: '🛒', fs_counter: '🔢', multi_counter: '✖️', hw_counter: '🔢',
  };

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
    for (const r of roles) {
      const item = document.createElement('div');
      item.className = 'pal-item' + (placed.has(r.id) ? ' is-placed' : '');
      item.innerHTML = `<span class="pal-item__ic">${ROLE_ICON[r.id] || '▫️'}</span><span>${r.label}</span>`;
      if (placed.has(r.id)) item.insertAdjacentHTML('beforeend', '<span class="pal-item__placed">на сцене</span>');
      item.addEventListener('click', () => addElement(r.id));
      paletteList.appendChild(item);
    }
  }

  function renderElements() {
    const { w: W, h: H } = designSize();
    [...stage.querySelectorAll('.el')].forEach((n) => n.remove());
    for (const el of elements()) {
      const node = document.createElement('div');
      node.className = 'el' + (el.role === 'reels' ? ' is-reels' : '') + (el.id === selectedId ? ' is-selected' : '');
      node.style.left = computeLeft(el, W) + 'px';
      node.style.top = computeTop(el, H) + 'px';
      node.style.width = el.w + 'px';
      node.style.height = el.h + 'px';
      node.style.zIndex = el.z;
      const asset = draft.assets && draft.assets[el.assetId];
      if (previews[el.assetId]) {
        node.innerHTML = `<img src="${previews[el.assetId]}">`;
      } else if (el.role === 'reels') {
        node.appendChild(reelGrid());
      }
      const tag = document.createElement('span');
      tag.className = 'el__tag';
      tag.textContent = roleLabel(el.role);
      node.appendChild(tag);
      node.addEventListener('mousedown', (e) => startDrag(e, el, node));
      stage.appendChild(node);
    }
  }
  function reelGrid() {
    const g = document.createElement('div');
    const base = BASES[draft.base];
    g.style.cssText = `display:grid;gap:${Math.max(2, draft.gap / 3)}px;width:86%;height:86%;grid-template-columns:repeat(${base.reels},1fr);grid-template-rows:repeat(${base.rows},1fr)`;
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

  function renderAll() { renderTabs(); renderPalette(); fitStage(); renderElements(); applyEdit(); }

  window.addEventListener('resize', () => { fitStage(); renderElements(); reselectNode(); });
  renderAll();
  document.getElementById('footInfo').textContent = `${draft.name} · ${BASES[draft.base].label}`;
})();
