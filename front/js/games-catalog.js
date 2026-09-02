// Renders front/games.html's (and tg.html's) game cards from GET /api/v1/catalog
// (published games only — see app/api/v1/catalog.py) instead of the old
// hand-written static <li> blocks, so a slot published via the builder
// wizard's "all OK" action shows up here automatically. Reuses apiGet from
// js/api.js (loaded before this script) for the same base-URL resolution as
// the play pages.
//
// The catalog is split into three sections (product, this session), in this
// order on the page:
//   - Готовые игры: the first READY_COUNT entries left after pulling
//     Illuminator out (below), in catalog order (== Game.created_at, oldest
//     first).
//   - Illuminator: a fixed hand-picked showcase, pulled out of the ordering
//     regardless of where those games would otherwise land.
//   - Игры в разработке: everything after that. A game not yet live on a
//     given backend (e.g. still local-only) simply isn't in `entries` at
//     all, so it's absent everywhere rather than mis-slotted — nothing here
//     needs to special-case that.
// A section with zero cards hides itself (including its heading) rather
// than showing an empty title.
const ILLUMINATOR_CODES = new Set(['gold-of-baku', 'gold-of-baku-2', 'big-catch', 'caesars-fortune']);
const READY_COUNT = 10;

const PLAY_ICON = '<svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8V4Z" fill="currentColor"/></svg>';
const ADMIN_ICON = '<svg viewBox="0 0 24 24"><path d="M19.4 13a7.5 7.5 0 0 0 0-2l2-1.5-2-3.4-2.4 1a7.7 7.7 0 0 0-1.7-1L15 3h-4l-.3 2.5a7.7 7.7 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a7.5 7.5 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7.7 7.7 0 0 0 1.7 1L11 21h4l.3-2.5a7.7 7.7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="13" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';

function gameCardHtml(entry) {
  const playUrl = entry.catalog_play_url || `play.html?slug=${encodeURIComponent(entry.code)}`;
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

// Hides a section (heading included) when its grid ended up empty — e.g. no
// game landed in Illuminator yet on this backend, or fewer than READY_COUNT
// games are published at all so "Игры в разработке" has nothing left.
function toggleSection(sectionId, gridEl) {
  const section = document.getElementById(sectionId);
  if (section) section.hidden = gridEl.children.length === 0;
}

async function renderCatalog() {
  const readyGrid = document.getElementById('readyGrid');
  const illuminatorGrid = document.getElementById('illuminatorGrid');
  const devGrid = document.getElementById('devGrid');

  try {
    const entries = await apiGet('/catalog');
    const illuminator = entries.filter((e) => ILLUMINATOR_CODES.has(e.code));
    const rest = entries.filter((e) => !ILLUMINATOR_CODES.has(e.code));
    const ready = rest.slice(0, READY_COUNT);
    const dev = rest.slice(READY_COUNT);

    for (const entry of ready) appendCard(readyGrid, entry);
    for (const entry of illuminator) appendCard(illuminatorGrid, entry);
    for (const entry of dev) appendCard(devGrid, entry);
  } catch (err) {
    const li = document.createElement('li');
    li.innerHTML = `<div class="game-card"><div class="game-card__body"><p class="game-card__desc">Не удалось загрузить каталог: ${err.message}</p></div></div>`;
    readyGrid.appendChild(li);
  }

  toggleSection('readySection', readyGrid);
  toggleSection('illuminatorSection', illuminatorGrid);
  toggleSection('devSection', devGrid);
}

renderCatalog();
