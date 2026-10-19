// Renders front/games.html's (and tg.html's) game cards from GET /api/v1/catalog
// (published games only — see app/api/v1/catalog.py) instead of the old
// hand-written static <li> blocks, so a slot published via the builder
// wizard's "all OK" action shows up here automatically. Reuses apiGet from
// js/api.js (loaded before this script) for the same base-URL resolution as
// the play pages.
//
// The catalog is split into four sections, same as the Telegram bot's menu,
// in this order on the page:
//   - Готовые игры: a fixed hand-picked list (READY_CODES).
//   - Illuminator: a fixed hand-picked showcase (ILLUMINATOR_CODES).
//   - В работе (was Spin Factory Portfolio): a fixed hand-picked list (SPIN_FACTORY_CODES).
//   - Игры в разработке: every other published game. These live only on
//     secret-room.html (behind a password), not in the public catalog —
//     each page renders just the sections it has grids for.
// The lists are explicit codes rather than "first N by created_at", so a
// newly seeded game lands in "в разработке" instead of shifting others
// between sections. Within a section, cards go newest first (GET /catalog
// lists by created_at ascending, so the order is reversed here). A game not
// yet live on a given backend simply isn't in `entries` and is skipped.
// Exception: in «Игры в разработке» the unicorn games (uniqorn-*,
// mr-president-unicorn) go after all the others, each group newest first.
// A section with zero cards hides itself (including its heading) rather
// than showing an empty title.
const READY_CODES = new Set([
  'amys-fruit-farm', 'dirty-money-mafia', 'east-discovery', 'golden-caravan',
  'neon-reels', 'party-of-goods', 'sugar-galaxy', 'wild-western-story',
  'multi-fruits-story', 'lucky-joker-3h3', 'gangsta-casino',
]);
const ILLUMINATOR_CODES = new Set(['gold-of-baku', 'gold-of-baku-2', 'volt-coins', 'neon-joker-spins', 'savannah-kings']);

// Illuminator games shipped in several front-end layouts over one backend
// game get their own sub-section (heading + one card per variant) instead of
// a single card. Each variant overrides the play page, badge, name and
// description; the cover falls back to the game's catalog cover.
const VARIANT_GROUPS = {
  'savannah-kings': {
    title: 'Savannah Kings',
    variants: [
      { url: 'savannah-kings-v3.html', badge: '1', name: 'Savannah Kings',
        desc: 'Закатная саванна, каменная рамка: лестница джекпотов с GRAND в центре, медальоны покупки и выигрыша.',
        cover: 'img/savannah-kings/cover_v3.jpg' },
      { url: 'lions-reign.html', badge: '2', name: "Lion's Reign",
        desc: 'Королевская версия: базальт с золотой филигранью и рубинами, символы в геральдических щитах, лев в короне.',
        cover: 'img/lions-reign/cover.jpg' },
      { url: 'golden-savannah.html', badge: '3', name: 'Golden Savannah',
        desc: 'Графичная версия: африканский ар-деко и бумажная аппликация, узоры кенте, символы в ромбах.',
        cover: 'img/golden-savannah/cover.jpg' },
      { url: 'savannah-kings.html', badge: '4', name: 'Savannah Kings · Classic',
        desc: 'Первая сборка: оригинальный арт, нижний бар управления, плашка выигрыша на барабанах.',
        cover: 'img/savannah-kings/cover_v1.jpg' },
      { url: 'savannah-kings-v2.html', badge: '5', name: 'Savannah Kings · Pride Rock',
        desc: 'Альтернативная раскладка UI: скала гордости, панель управления сбоку от барабанов.',
        cover: 'img/savannah-kings/cover_v2.jpg' },
    ],
  },
};
const SPIN_FACTORY_CODES = new Set(['big-catch', 'caesars-fortune', 'ice-spin-deluxe', 'tesla-spins']);

// Neon Joker Spins и его скины (A/B/C/D — сравнение арт-дирекшена по ГДД):
// одна игра на бэкенде (код neon-joker-spins), четыре страницы. В Illuminator
// они живут отдельной подкатегорией #njsGrid — карточки строятся из одной
// записи /catalog. Нет подкатегории на странице — NJS идёт в Illuminator как раньше.
const NJS_CODE = 'neon-joker-spins';
const NJS_VARIANTS = [
  { page: 'neon-joker-spins.html', name: 'Neon Joker Spins', badge: 'Оригинал', cover: 'img/neon-joker-spins/img/cover.jpg' },
  {
    page: 'neon-joker-spins-a.html', name: 'Neon Joker Spins · A', badge: 'Neon Sign',
    cover: 'img/neon-joker-spins/skins/a/img/cover.jpg',
    desc: 'Плоский неон 80-х: светящиеся трубки, мокрый асфальт, неоновая рама.',
  },
  {
    page: 'neon-joker-spins-b.html', name: 'Neon Joker Spins · B', badge: 'Glossy Show',
    cover: 'img/neon-joker-spins/skins/b/img/cover.jpg',
    desc: 'Глянцевое шоу: объёмные символы, золотая рама с лампочками, сцена.',
  },
  {
    page: 'neon-joker-spins-c.html', name: 'Neon Joker Spins · C', badge: 'Rock Chrome',
    cover: 'img/neon-joker-spins/skins/c/img/cover.jpg',
    desc: 'Рок-клуб: сталь и хром, Джокер-панк, молнии вместо линий выигрыша.',
  },
  {
    page: 'neon-joker-spins-d.html', name: 'Neon Joker Spins · D', badge: 'Retro 80s',
    cover: 'img/neon-joker-spins/skins/d/img/cover.jpg',
    desc: 'Автомат 80-х: хромированный корпус, барабаны под стеклом, лампы и рычаг.',
  },
];

function njsEntries(entry) {
  return NJS_VARIANTS.map((v) => ({
    ...entry,
    name: v.name,
    catalog_badge: v.badge,
    catalog_play_url: v.page,
    catalog_cover_path: v.cover || entry.catalog_cover_path,
    catalog_description: v.desc || entry.catalog_description,
  }));
}

const isUnicornGame = (code) => /uniqorn|unicorn/.test(code);

const PLAY_ICON = '<svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8V4Z" fill="currentColor"/></svg>';
const ADMIN_ICON = '<svg viewBox="0 0 24 24"><path d="M19.4 13a7.5 7.5 0 0 0 0-2l2-1.5-2-3.4-2.4 1a7.7 7.7 0 0 0-1.7-1L15 3h-4l-.3 2.5a7.7 7.7 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a7.5 7.5 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7.7 7.7 0 0 0 1.7 1L11 21h4l.3-2.5a7.7 7.7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="13" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';

function gameCardHtml(entry) {
  let playUrl = entry.catalog_play_url || `play.html?slug=${encodeURIComponent(entry.code)}`;
  // Каталог открыт с ?api=<url> (свой локальный бэкенд) — передаём его в игру,
  // иначе она уйдёт на бэкенд по умолчанию, где этой игры может не быть.
  const apiOverride = new URLSearchParams(location.search).get('api');
  if (apiOverride) playUrl += `${playUrl.includes('?') ? '&' : '?'}api=${encodeURIComponent(apiOverride)}`;
  // tg.html (портфолио для Telegram Mini App) выставляет CATALOG_PORTFOLIO:
  // карточки те же, но без кнопки «Админка» — наружу только игры.
  const adminLink = window.CATALOG_PORTFOLIO
    ? ''
    : `<a class="game-card__admin" href="admin/index.html?game=${encodeURIComponent(entry.code)}">${ADMIN_ICON} Админка</a>`;
  return `
    <div class="game-card">
      <a class="game-card__media" href="${playUrl}">
        ${entry.catalog_badge ? `<span class="game-card__badge">${entry.catalog_badge}</span>` : ''}
        <img class="game-card__img" src="${entry.catalog_cover_path || ''}" alt="${entry.name}">
      </a>
      <div class="game-card__body">
        <h2 class="game-card__name">${entry.name}</h2>
        <p class="game-card__desc">${entry.catalog_description || ''}</p>
        <div class="game-card__actions">
          <a class="game-card__play" href="${playUrl}">${PLAY_ICON} Играть</a>
          ${adminLink}
        </div>
      </div>
    </div>
  `;
}

function appendCard(gridEl, entry) {
  const li = document.createElement('li');
  li.innerHTML = gameCardHtml(entry);
  gridEl.appendChild(li);
}

// A sub-section inside a section's grid: spans the full row, own heading,
// own grid of variant cards.
function appendVariantGroup(gridEl, entry, group) {
  const li = document.createElement('li');
  li.className = 'catalog-sub';
  li.innerHTML = `<h3 class="catalog-sub__title">${group.title}</h3><ul class="game-grid catalog-sub__grid"></ul>`;
  const sub = li.querySelector('ul');
  for (const v of group.variants) {
    appendCard(sub, {
      ...entry,
      name: v.name,
      catalog_badge: v.badge,
      catalog_description: v.desc,
      catalog_play_url: v.url,
      catalog_cover_path: v.cover || entry.catalog_cover_path,
    });
  }
  // Variant covers are optional screenshots: fall back to the game cover.
  for (const img of sub.querySelectorAll('.game-card__img')) {
    img.addEventListener('error', () => { img.src = entry.catalog_cover_path; }, { once: true });
  }
  gridEl.appendChild(li);
}

// Hides a section (heading included) when its grid ended up empty — e.g. no
// game landed in Illuminator yet on this backend.
function toggleSection(sectionId, gridEl) {
  const section = document.getElementById(sectionId);
  if (section) section.hidden = gridEl.children.length === 0;
}

async function renderCatalog() {
  const readyGrid = document.getElementById('readyGrid');
  const illuminatorGrid = document.getElementById('illuminatorGrid');
  const spinFactoryGrid = document.getElementById('spinFactoryGrid');
  const devGrid = document.getElementById('devGrid');
  const njsGrid = document.getElementById('njsGrid');
  const grids = [readyGrid, illuminatorGrid, spinFactoryGrid, devGrid].filter(Boolean);

  try {
    const entries = (await apiGet('/catalog')).reverse();
    const ready = entries.filter((e) => READY_CODES.has(e.code));
    const illuminator = entries.filter((e) => ILLUMINATOR_CODES.has(e.code) && !(njsGrid && e.code === NJS_CODE));
    const njs = njsGrid ? entries.filter((e) => e.code === NJS_CODE).flatMap(njsEntries) : [];
    const spinFactory = entries.filter((e) => SPIN_FACTORY_CODES.has(e.code));
    const dev = entries.filter((e) => !READY_CODES.has(e.code)
      && !ILLUMINATOR_CODES.has(e.code) && !SPIN_FACTORY_CODES.has(e.code));
    dev.sort((a, b) => isUnicornGame(a.code) - isUnicornGame(b.code));

    if (readyGrid) for (const entry of ready) appendCard(readyGrid, entry);
    if (illuminatorGrid) {
      for (const entry of illuminator) {
        if (VARIANT_GROUPS[entry.code]) appendVariantGroup(illuminatorGrid, entry, VARIANT_GROUPS[entry.code]);
        else appendCard(illuminatorGrid, entry);
      }
    }
    if (njsGrid) for (const entry of njs) appendCard(njsGrid, entry);
    if (spinFactoryGrid) for (const entry of spinFactory) appendCard(spinFactoryGrid, entry);
    if (devGrid) for (const entry of dev) appendCard(devGrid, entry);
  } catch (err) {
    const li = document.createElement('li');
    li.innerHTML = `<div class="game-card"><div class="game-card__body"><p class="game-card__desc">Не удалось загрузить каталог: ${err.message}</p></div></div>`;
    grids[0].appendChild(li);
  }

  if (readyGrid) toggleSection('readySection', readyGrid);
  if (njsGrid) toggleSection('njsSubsection', njsGrid);
  if (illuminatorGrid) {
    toggleSection('illuminatorSection', illuminatorGrid);
    // секция видна, если есть хотя бы подкатегория NJS
    if (njsGrid && njsGrid.children.length) document.getElementById('illuminatorSection').hidden = false;
  }
  if (spinFactoryGrid) toggleSection('spinFactorySection', spinFactoryGrid);
  if (devGrid) toggleSection('devSection', devGrid);
}

// secret-room.html calls renderCatalog() itself once the password is in.
if (!window.CATALOG_SECRET_ROOM) renderCatalog();
