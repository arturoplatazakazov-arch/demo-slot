// Stage 2 of the slot builder wizard: upload materials (images/sounds/
// animations) into the folders Stage 1 created, tagged with enough metadata
// (category/screen/device) for Stage 4's layout editor to place them later.
// See app/api/admin/builder.py for the endpoints this talks to.
// apiRequest/apiUpload/setStatus/API_BASE come from common.js.

const params = new URLSearchParams(window.location.search);
const SLUG = params.get('slug');

const CATEGORY_LABELS = {
  background: 'Фон', symbol: 'Символы', ui: 'UI', hero: 'Герой', logo: 'Логотип', frame: 'Рамка',
  reel_background: 'Фон за барабанами', hud: 'Счётчик/HUD', catalog: 'Обложка каталога',
};
const SCREEN_LABELS = { base: 'база', bonus: 'бонус', both: 'оба экрана' };
const DEVICE_LABELS = { desktop: 'десктоп', mobile: 'моби', both: 'деск+моби' };

function imgUrl(file) { return `../img/${SLUG}/${file}`; }
function soundUrl(file) { return `../sound/${SLUG}/${file}`; }
function animFileUrl(anim, file) { return `../img/${SLUG}/${anim.folder}/${file}`; }

function renderGallery(manifest) {
  const gallery = document.getElementById('gallery');
  gallery.innerHTML = '';

  for (const category of Object.keys(CATEGORY_LABELS)) {
    const items = manifest.assets.images.filter((img) => img.category === category);
    const group = document.createElement('div');
    group.className = 'gallery-group';
    const heading = document.createElement('h3');
    heading.textContent = CATEGORY_LABELS[category];
    group.appendChild(heading);

    if (items.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'gallery-empty';
      empty.textContent = 'Пока ничего не загружено.';
      group.appendChild(empty);
    } else {
      const grid = document.createElement('div');
      grid.className = 'gallery-grid';
      for (const img of items) {
        const tags = (img.screen && img.device)
          ? `<span class="gallery-item__tags"><span class="tag">${SCREEN_LABELS[img.screen]}</span><span class="tag">${DEVICE_LABELS[img.device]}</span></span>`
          : '';
        const item = document.createElement('div');
        item.className = 'gallery-item';
        item.innerHTML = `
          <button class="gallery-item__delete" data-asset-id="${img.id}" title="Удалить">×</button>
          <img class="gallery-item__thumb" src="${imgUrl(img.file)}" alt="${img.file}">
          <div class="gallery-item__meta">
            <span class="gallery-item__name">${img.file}</span>
            ${tags}
          </div>
        `;
        grid.appendChild(item);
      }
      group.appendChild(grid);
    }
    gallery.appendChild(group);
  }

  const unassigned = manifest.assets.images.filter((img) => !img.category);
  const unassignedGroup = document.createElement('div');
  unassignedGroup.className = 'gallery-group';
  unassignedGroup.innerHTML = '<h3>Не размечено</h3>';
  if (unassigned.length === 0) {
    unassignedGroup.innerHTML += '<p class="gallery-empty">Всё размечено.</p>';
  } else {
    const grid = document.createElement('div');
    grid.className = 'gallery-grid';
    for (const img of unassigned) {
      const item = document.createElement('div');
      item.className = 'gallery-item gallery-item--unassigned';
      item.innerHTML = `
        <button class="gallery-item__delete" data-asset-id="${img.id}" title="Удалить">×</button>
        <img class="gallery-item__thumb" src="${imgUrl(img.file)}" alt="${img.file}">
        <div class="gallery-item__meta">
          <span class="gallery-item__name">${img.file}</span>
        </div>
        <form class="tag-form" data-asset-id="${img.id}">
          <select name="category">
            <option value="background">Фон</option>
            <option value="symbol">Символ</option>
            <option value="ui">UI</option>
            <option value="hero">Герой</option>
            <option value="logo">Логотип</option>
            <option value="frame">Рамка</option>
            <option value="reel_background">Фон за барабанами</option>
            <option value="hud">Счётчик/HUD</option>
            <option value="catalog">Обложка каталога</option>
          </select>
          <select name="screen">
            <option value="base">База</option>
            <option value="bonus">Бонус</option>
            <option value="both">Оба экрана</option>
          </select>
          <select name="device">
            <option value="desktop">Десктоп</option>
            <option value="mobile">Моби</option>
            <option value="both">Деск + моби</option>
          </select>
          <button class="btn btn--primary" type="submit">Сохранить</button>
        </form>
      `;
      grid.appendChild(item);
    }
    unassignedGroup.appendChild(grid);
  }
  gallery.appendChild(unassignedGroup);

  const soundGroup = document.createElement('div');
  soundGroup.className = 'gallery-group';
  soundGroup.innerHTML = '<h3>Звуки</h3>';
  if (manifest.assets.sounds.length === 0) {
    soundGroup.innerHTML += '<p class="gallery-empty">Пока ничего не загружено.</p>';
  } else {
    const list = document.createElement('ul');
    list.className = 'sound-list';
    for (const sound of manifest.assets.sounds) {
      const li = document.createElement('li');
      li.innerHTML = `<span>${sound.file}</span><audio controls src="${soundUrl(sound.file)}"></audio><button class="list-delete" data-asset-id="${sound.id}" title="Удалить">×</button>`;
      list.appendChild(li);
    }
    soundGroup.appendChild(list);
  }
  gallery.appendChild(soundGroup);

  const animGroup = document.createElement('div');
  animGroup.className = 'gallery-group';
  animGroup.innerHTML = '<h3>Анимации</h3>';
  if (manifest.assets.animations.length === 0) {
    animGroup.innerHTML += '<p class="gallery-empty">Пока ничего не загружено.</p>';
  } else {
    const list = document.createElement('ul');
    list.className = 'anim-list';
    for (const anim of manifest.assets.animations) {
      const li = document.createElement('li');
      li.innerHTML = `<span>${anim.name}</span><span class="anim-files">${anim.files.join(', ')}</span><button class="list-delete anim-delete" data-anim-id="${anim.id}" title="Удалить">×</button>`;
      list.appendChild(li);
    }
    animGroup.appendChild(list);
  }
  gallery.appendChild(animGroup);
}

async function loadGame() {
  const manifest = await apiRequest('GET', `/games/${SLUG}`);
  document.getElementById('slotName').textContent = `— ${manifest.meta.display_name} (${manifest.meta.slug})`;
  document.title = `Конструктор слота — ${manifest.meta.display_name} — Этап 2`;
  renderGallery(manifest);
  return manifest;
}

if (!SLUG) {
  document.querySelector('main').innerHTML = '<section class="panel"><p class="hint">Не указан слаг слота (нет ?slug=... в адресе). Вернись к <a href="new.html">списку слотов</a>.</p></section>';
} else {
  const toggleImagePlacementFields = () => {
    const isCatalog = document.getElementById('imageCategory').value === 'catalog';
    document.getElementById('imageScreenField').classList.toggle('is-hidden', isCatalog);
    document.getElementById('imageDeviceField').classList.toggle('is-hidden', isCatalog);
  };
  document.getElementById('imageCategory').addEventListener('change', toggleImagePlacementFields);
  toggleImagePlacementFields();

  document.getElementById('imageForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    formData.set('kind', 'image');
    setStatus('imageStatus', 'Загружаю…');
    try {
      await apiUpload(`/games/${SLUG}/assets`, formData);
      setStatus('imageStatus', 'Загружено.', 'is-ok');
      form.reset();
      await loadGame();
    } catch (err) {
      setStatus('imageStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('soundForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    formData.set('kind', 'sound');
    setStatus('soundStatus', 'Загружаю…');
    try {
      await apiUpload(`/games/${SLUG}/assets`, formData);
      setStatus('soundStatus', 'Загружено.', 'is-ok');
      form.reset();
      await loadGame();
    } catch (err) {
      setStatus('soundStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('animForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    setStatus('animStatus', 'Загружаю…');
    try {
      await apiUpload(`/games/${SLUG}/animations`, formData);
      setStatus('animStatus', 'Загружено.', 'is-ok');
      form.reset();
      await loadGame();
    } catch (err) {
      setStatus('animStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('rescanBtn').addEventListener('click', async () => {
    setStatus('rescanStatus', 'Проверяю папки…');
    try {
      const manifest = await apiRequest('POST', `/games/${SLUG}/rescan`);
      setStatus('rescanStatus', 'Готово.', 'is-ok');
      document.title = `Конструктор слота — ${manifest.meta.display_name} — Этап 2`;
      renderGallery(manifest);
    } catch (err) {
      setStatus('rescanStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('gallery').addEventListener('submit', async (event) => {
    const form = event.target.closest('.tag-form');
    if (!form) return;
    event.preventDefault();
    const assetId = form.dataset.assetId;
    const formData = new FormData(form);
    const body = {
      category: formData.get('category'),
      screen: formData.get('screen'),
      device: formData.get('device'),
    };
    try {
      await apiRequest('PATCH', `/games/${SLUG}/assets/${assetId}`, body);
      await loadGame();
    } catch (err) {
      setStatus('rescanStatus', `Ошибка разметки: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('gallery').addEventListener('click', async (event) => {
    const animBtn = event.target.closest('.anim-delete');
    if (animBtn) {
      if (!confirm('Удалить анимацию вместе с папкой файлов?')) return;
      try {
        await apiRequest('DELETE', `/games/${SLUG}/animations/${animBtn.dataset.animId}`);
        await loadGame();
      } catch (err) {
        setStatus('rescanStatus', `Ошибка удаления: ${err.message}`, 'is-error');
      }
      return;
    }
    const assetBtn = event.target.closest('.gallery-item__delete, .list-delete');
    if (assetBtn) {
      if (!confirm('Удалить материал?')) return;
      try {
        await apiRequest('DELETE', `/games/${SLUG}/assets/${assetBtn.dataset.assetId}`);
        await loadGame();
      } catch (err) {
        setStatus('rescanStatus', `Ошибка удаления: ${err.message}`, 'is-error');
      }
    }
  });

  document.getElementById('stageDoneBtn').addEventListener('click', async () => {
    setStatus('stageStatus', 'Сохраняю…');
    try {
      await apiRequest('POST', `/games/${SLUG}/stage`, { stage: 2 });
      setStatus('stageStatus', 'Готово. Переход к сетке и механикам…', 'is-ok');
      window.location.href = `grid.html?slug=${encodeURIComponent(SLUG)}`;
    } catch (err) {
      setStatus('stageStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  loadGame().catch((err) => {
    document.querySelector('main').innerHTML = `<section class="panel"><p class="hint">Не удалось загрузить слот "${SLUG}": ${err.message}</p></section>`;
  });
}
