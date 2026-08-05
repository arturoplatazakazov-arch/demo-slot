// Constructor v2 — Page 2 (Assets) logic.
//
// Client-only for now: dropping a file records {name,size} into the draft and
// shows an in-session preview (object URL). Real files get POSTed to the builder
// API later; the canonical path shown is where each one will land.
(function () {
  const draft = Draft.load();

  // Guard: need a base first.
  if (!draft.base) { location.replace('setup.html'); return; }

  const slotArea = document.getElementById('slotArea');
  const progress = document.getElementById('progress');
  const footInfo = document.getElementById('footInfo');

  const slug = draft.slug || 'game';
  const previews = {}; // id -> object URL (in-session only)

  // Canonical destination path per asset kind.
  function pathFor(a) {
    switch (a.kind) {
      case 'symbol': return `img/${slug}/Export/${a.id}/…`;
      case 'popup': return `img/${slug}/Popup/${a.id}.*`;
      case 'background': return `img/${slug}/${a.id}.*`;
      case 'vfx': return `img/${slug}/Export/${a.id}/…`;
      default: return `img/${slug}/${a.id}.*`;
    }
  }
  const KIND_ICON = { symbol: '🎰', popup: '🎉', background: '🖼️', frame: '🖼️', logo: '🔤', button: '🔘', vfx: '💥' };
  const KIND_GROUP = {
    symbol: 'Символы', background: 'Фоны', frame: 'Рамка / панель', logo: 'Логотип',
    popup: 'Попапы', button: 'Кнопки', vfx: 'VFX',
  };

  const assets = requiredAssets(draft.base, draft.mechanics);

  function provided(id) { return !!(draft.assets[id] && draft.assets[id].file); }
  function requiredList() { return assets.filter((a) => !a.optional); }

  function updateProgress() {
    const req = requiredList();
    const have = req.filter((a) => provided(a.id)).length;
    const pct = req.length ? Math.round((have / req.length) * 100) : 100;
    progress.innerHTML =
      `<div class="assets-progress__txt">${have} / ${req.length} обязательных</div>` +
      `<div class="assets-progress__bar"><div class="assets-progress__fill" style="width:${pct}%"></div></div>` +
      `<div class="assets-progress__txt">${pct}%</div>`;
    footInfo.textContent = have < req.length
      ? `Не хватает ${req.length - have} обязательных (можно вернуться позже)`
      : 'Все обязательные ассеты на месте ✓';
  }

  function acceptFile(a, file) {
    if (!file) return;
    if (previews[a.id]) URL.revokeObjectURL(previews[a.id]);
    previews[a.id] = URL.createObjectURL(file);
    draft.assets[a.id] = { file: file.name, size: file.size };
    Draft.save(draft);
    render();
  }

  function removeFile(a) {
    if (previews[a.id]) { URL.revokeObjectURL(previews[a.id]); delete previews[a.id]; }
    delete draft.assets[a.id];
    Draft.save(draft);
    render();
  }

  function makeSlot(a) {
    const el = document.createElement('div');
    el.className = 'slot' + (provided(a.id) ? ' is-done' : '') + (a.optional ? ' is-optional' : '');

    const thumb = document.createElement('div');
    thumb.className = 'slot__thumb';
    if (previews[a.id]) {
      const img = document.createElement('img');
      img.src = previews[a.id];
      thumb.appendChild(img);
    } else {
      const k = document.createElement('span');
      k.className = 'slot__thumb-kind';
      k.textContent = KIND_ICON[a.kind] || '📄';
      thumb.appendChild(k);
    }

    const body = document.createElement('div');
    body.className = 'slot__body';
    const label = document.createElement('div');
    label.className = 'slot__label';
    label.append(a.label);
    const tag = document.createElement('span');
    tag.className = 'slot__tag';
    tag.textContent = a.kind;
    label.append(tag);
    if (a.optional) { const o = document.createElement('span'); o.className = 'slot__opt'; o.textContent = '· опционально'; label.append(o); }
    const path = document.createElement('div');
    path.className = 'slot__path';
    path.textContent = pathFor(a);
    body.append(label, path);
    if (provided(a.id)) {
      const f = document.createElement('div');
      f.className = 'slot__file';
      f.textContent = '✓ ' + draft.assets[a.id].file;
      body.append(f);
    }

    const actions = document.createElement('div');
    actions.className = 'slot__actions';
    const pick = document.createElement('button');
    pick.className = 'slot__btn';
    pick.textContent = provided(a.id) ? 'Заменить' : 'Выбрать';
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*,.json,.atlas'; input.hidden = true;
    input.addEventListener('change', () => acceptFile(a, input.files[0]));
    pick.addEventListener('click', () => input.click());
    actions.append(pick, input);
    if (provided(a.id)) {
      const rm = document.createElement('button');
      rm.className = 'slot__btn slot__btn--remove';
      rm.textContent = 'Убрать';
      rm.addEventListener('click', () => removeFile(a));
      actions.append(rm);
    }

    el.append(thumb, body, actions);

    // Drag & drop.
    el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('is-over'); });
    el.addEventListener('dragleave', () => el.classList.remove('is-over'));
    el.addEventListener('drop', (e) => {
      e.preventDefault(); el.classList.remove('is-over');
      if (e.dataTransfer.files[0]) acceptFile(a, e.dataTransfer.files[0]);
    });
    return el;
  }

  function render() {
    // Group by kind for readability.
    const groups = {};
    for (const a of assets) (groups[a.kind] ||= []).push(a);
    slotArea.innerHTML = '';
    for (const [kind, list] of Object.entries(groups)) {
      const g = document.createElement('div');
      g.className = 'slot-group';
      const t = document.createElement('h3');
      t.className = 'slot-group__title';
      t.textContent = KIND_GROUP[kind] || kind;
      const l = document.createElement('div');
      l.className = 'slot-list';
      list.forEach((a) => l.appendChild(makeSlot(a)));
      g.append(t, l);
      slotArea.appendChild(g);
    }
    updateProgress();
  }

  render();
})();
