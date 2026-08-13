// Constructor v2 — Page 2 (Assets), backed by the real builder API.
//
// Flow: Stage 1 created the on-disk game folder (POST /games). Here the user
// drops all exported files into front/img/<slug>/ (symbols/popups as Spine
// sub-folders, backgrounds/frame/logo/buttons as loose files) and hits
// "Систематизировать" (POST /rescan) — which categorizes, spine-fixes atlases,
// and drops anything unrecognized into the "unassigned" bucket to tag by hand.
// A browser folder-upload (POST /upload-tree) mirrors the same for users who'd
// rather drag a folder into the page than into Finder.
(function () {
  const params = new URLSearchParams(window.location.search);
  const draft = Draft.load();
  const SLUG = params.get('slug') || draft.backendSlug;

  const main = document.getElementById('main');
  const gallery = document.getElementById('gallery');
  const statusEl = document.getElementById('status');
  const footInfo = document.getElementById('footInfo');

  if (!SLUG) {
    main.innerHTML = '<div class="empty-note">Игра ещё не создана. Вернись на <a href="setup.html">шаг 1</a>, задай название и базу — папка игры создастся там.</div>';
    return;
  }

  document.getElementById('folderPath').textContent = BuilderAPI.folderPath(SLUG);
  document.getElementById('nextBtn').href = `layout.html?slug=${encodeURIComponent(SLUG)}`;
  const stepLayout = document.getElementById('stepLayout');
  if (stepLayout) stepLayout.href = `layout.html?slug=${encodeURIComponent(SLUG)}`;

  const CATEGORY_LABELS = {
    symbol: 'Символы', background: 'Фоны', reel_background: 'Фон за барабанами', frame: 'Рамка',
    logo: 'Логотип', ui: 'UI / кнопки', hud: 'Счётчики / HUD', hero: 'Герой', catalog: 'Обложка каталога',
  };
  const SCREEN_LABELS = { base: 'база', bonus: 'бонус', both: 'оба' };
  const DEVICE_LABELS = { desktop: 'десктоп', mobile: 'моби', both: 'деск+моби' };

  function setStatus(msg, kind) {
    statusEl.textContent = msg || '';
    statusEl.className = 'intake__status' + (kind ? ' is-' + kind : '');
  }

  // --- Render -------------------------------------------------------------
  function categoryGroup(manifest, category) {
    const items = manifest.assets.images.filter((img) => img.category === category);
    if (items.length === 0) return null;
    const group = document.createElement('div');
    group.className = 'gallery-group';
    group.innerHTML = `<h3>${CATEGORY_LABELS[category]} · ${items.length}</h3>`;
    const grid = document.createElement('div');
    grid.className = 'gallery-grid';
    for (const img of items) {
      const tags = (img.screen && img.device)
        ? `<span class="gallery-item__tags"><span class="tag">${SCREEN_LABELS[img.screen] || img.screen}</span><span class="tag">${DEVICE_LABELS[img.device] || img.device}</span></span>`
        : '';
      const item = document.createElement('div');
      item.className = 'gallery-item';
      item.innerHTML = `
        <button class="gallery-item__delete" data-del-asset="${img.id}" title="Удалить файл">×</button>
        <img class="gallery-item__thumb" src="${BuilderAPI.imgUrl(SLUG, img.file)}" alt="${img.file}" loading="lazy">
        <div class="gallery-item__meta">
          <span class="gallery-item__name">${img.file}</span>
          ${tags}
        </div>
        <div class="gallery-item__actions">
          <button class="gallery-item__btn" data-unassign="${img.id}">→ в нераспределённые</button>
        </div>`;
      grid.appendChild(item);
    }
    group.appendChild(grid);
    return group;
  }

  function unassignedGroup(manifest) {
    const items = manifest.assets.images.filter((img) => !img.category);
    const group = document.createElement('div');
    group.className = 'gallery-group is-unassigned';
    group.innerHTML = `<h3>Нераспределённые · ${items.length}</h3>`;
    if (items.length === 0) {
      group.innerHTML += '<p class="gallery-empty">Всё разложено по категориям ✓</p>';
      return group;
    }
    const grid = document.createElement('div');
    grid.className = 'gallery-grid';
    const catOptions = Object.entries(CATEGORY_LABELS)
      .map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    for (const img of items) {
      const item = document.createElement('div');
      item.className = 'gallery-item gallery-item--unassigned';
      item.innerHTML = `
        <button class="gallery-item__delete" data-del-asset="${img.id}" title="Удалить файл">×</button>
        <img class="gallery-item__thumb" src="${BuilderAPI.imgUrl(SLUG, img.file)}" alt="${img.file}" loading="lazy">
        <div class="gallery-item__meta"><span class="gallery-item__name">${img.file}</span></div>
        <form class="tag-form" data-asset="${img.id}">
          <select name="category">${catOptions}</select>
          <select name="screen"><option value="base">База</option><option value="bonus">Бонус</option><option value="both" selected>Оба</option></select>
          <select name="device"><option value="desktop">Десктоп</option><option value="mobile">Моби</option><option value="both" selected>Деск+моби</option></select>
          <button class="btn btn--primary" type="submit">Разметить</button>
        </form>`;
      grid.appendChild(item);
    }
    group.appendChild(grid);
    return group;
  }

  function soundGroup(manifest) {
    if (manifest.assets.sounds.length === 0) return null;
    const group = document.createElement('div');
    group.className = 'gallery-group';
    group.innerHTML = `<h3>Звуки · ${manifest.assets.sounds.length}</h3>`;
    const list = document.createElement('ul');
    list.className = 'sound-list';
    for (const s of manifest.assets.sounds) {
      const li = document.createElement('li');
      li.innerHTML = `<span>${s.file}</span><audio controls src="${BuilderAPI.soundUrl(SLUG, s.file)}"></audio><button class="list-delete" data-del-asset="${s.id}" title="Удалить">×</button>`;
      list.appendChild(li);
    }
    group.appendChild(list);
    return group;
  }

  function animGroup(manifest) {
    if (manifest.assets.animations.length === 0) return null;
    const group = document.createElement('div');
    group.className = 'gallery-group';
    group.innerHTML = `<h3>Анимации / Spine · ${manifest.assets.animations.length}</h3>`;
    const list = document.createElement('ul');
    list.className = 'anim-list';
    for (const a of manifest.assets.animations) {
      const li = document.createElement('li');
      li.innerHTML = `<span>${a.name}</span><span class="anim-files">${a.files.join(', ')}</span><button class="list-delete" data-del-anim="${a.id}" title="Удалить папку">×</button>`;
      list.appendChild(li);
    }
    group.appendChild(list);
    return group;
  }

  function render(manifest) {
    document.getElementById('slotName').textContent = `— ${manifest.meta.display_name} (${manifest.meta.slug})`;
    gallery.innerHTML = '';
    gallery.appendChild(unassignedGroup(manifest));
    for (const cat of Object.keys(CATEGORY_LABELS)) {
      const g = categoryGroup(manifest, cat);
      if (g) gallery.appendChild(g);
    }
    const sg = soundGroup(manifest); if (sg) gallery.appendChild(sg);
    const ag = animGroup(manifest); if (ag) gallery.appendChild(ag);

    const imgCount = manifest.assets.images.length;
    const unassigned = manifest.assets.images.filter((i) => !i.category).length;
    footInfo.textContent = `${imgCount} картинок · ${manifest.assets.animations.length} анимаций · ${manifest.assets.sounds.length} звуков`
      + (unassigned ? ` · ${unassigned} не размечено` : '');
  }

  async function load() {
    const manifest = await BuilderAPI.request('GET', `/games/${SLUG}`);
    render(manifest);
    return manifest;
  }

  // --- Systematize --------------------------------------------------------
  function reportRescan(manifest) {
    const warns = manifest._spine_warnings || [];
    const unassigned = manifest.assets.images.filter((i) => !i.category).length;
    let msg = 'Готово. ';
    if (warns.length) msg += `Починил spine: ${warns.length} (${warns.slice(0, 3).join('; ')}${warns.length > 3 ? '…' : ''}). `;
    msg += unassigned ? `${unassigned} файлов ждут разметки ниже.` : 'Всё разложено.';
    setStatus(msg, warns.length ? 'warn' : 'ok');
  }

  document.getElementById('rescanBtn').addEventListener('click', async () => {
    setStatus('Сканирую папку игры…');
    try {
      const manifest = await BuilderAPI.request('POST', `/games/${SLUG}/rescan`);
      render(manifest);
      reportRescan(manifest);
    } catch (err) {
      setStatus(`Ошибка: ${err.message}`, 'error');
    }
  });

  // --- Browser folder upload ---------------------------------------------
  document.getElementById('folderInput').addEventListener('change', async (e) => {
    const files = [...e.target.files];
    if (!files.length) return;
    setStatus(`Загружаю ${files.length} файлов в папку игры…`);
    const fd = new FormData();
    for (const f of files) {
      fd.append('paths', f.webkitRelativePath || f.name);
      fd.append('files', f, f.name);
    }
    try {
      const manifest = await BuilderAPI.upload(`/games/${SLUG}/upload-tree`, fd);
      render(manifest);
      reportRescan(manifest);
    } catch (err) {
      setStatus(`Ошибка загрузки: ${err.message}`, 'error');
    } finally {
      e.target.value = '';
    }
  });

  // --- Assign / un-assign / delete (event delegation) ---------------------
  gallery.addEventListener('submit', async (e) => {
    const form = e.target.closest('.tag-form');
    if (!form) return;
    e.preventDefault();
    const fd = new FormData(form);
    try {
      const manifest = await BuilderAPI.request('PATCH', `/games/${SLUG}/assets/${form.dataset.asset}`, {
        category: fd.get('category'), screen: fd.get('screen'), device: fd.get('device'),
      });
      render(manifest);
      setStatus('Размечено ✓', 'ok');
    } catch (err) {
      setStatus(`Ошибка разметки: ${err.message}`, 'error');
    }
  });

  gallery.addEventListener('click', async (e) => {
    const unassignBtn = e.target.closest('[data-unassign]');
    if (unassignBtn) {
      try {
        const manifest = await BuilderAPI.request('PATCH', `/games/${SLUG}/assets/${unassignBtn.dataset.unassign}`, { category: null });
        render(manifest);
        setStatus('Снято в нераспределённые (файл на месте) ✓', 'ok');
      } catch (err) { setStatus(`Ошибка: ${err.message}`, 'error'); }
      return;
    }
    const delAnim = e.target.closest('[data-del-anim]');
    if (delAnim) {
      if (!confirm('Удалить анимацию вместе с папкой файлов на диске?')) return;
      try { await BuilderAPI.request('DELETE', `/games/${SLUG}/animations/${delAnim.dataset.delAnim}`); await load(); }
      catch (err) { setStatus(`Ошибка удаления: ${err.message}`, 'error'); }
      return;
    }
    const delAsset = e.target.closest('[data-del-asset]');
    if (delAsset) {
      if (!confirm('Удалить файл с диска? (это не «в нераспределённые», а полное удаление)')) return;
      try { await BuilderAPI.request('DELETE', `/games/${SLUG}/assets/${delAsset.dataset.delAsset}`); await load(); }
      catch (err) { setStatus(`Ошибка удаления: ${err.message}`, 'error'); }
    }
  });

  document.getElementById('copyPath').addEventListener('click', () => {
    navigator.clipboard?.writeText(BuilderAPI.folderPath(SLUG)).then(
      () => setStatus('Путь скопирован.', 'ok'),
      () => setStatus('Не удалось скопировать — выдели вручную.', 'error'),
    );
  });

  load().catch((err) => {
    main.innerHTML = `<div class="empty-note">Не удалось загрузить игру «${SLUG}»: ${err.message}<br>Бэкенд (:8000) запущен?</div>`;
  });
})();
