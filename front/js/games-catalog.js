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
//   - Spin Factory Portfolio: a fixed hand-picked list (SPIN_FACTORY_CODES).
//   - Игры в разработке: every other published game.
// The lists are explicit codes rather than "first N by created_at", so a
// newly seeded game lands in "в разработке" instead of shifting others
// between sections. Within a section, cards keep catalog order. A game not
// yet live on a given backend simply isn't in `entries` and is skipped.
// A section with zero cards hides itself (including its heading) rather
// than showing an empty title.
const READY_CODES = new Set([
  'amys-fruit-farm', 'dirty-money-mafia', 'east-discovery', 'golden-caravan',
  'neon-reels', 'party-of-goods', 'sugar-galaxy', 'wild-western-story',
  'multi-fruits-story', 'lucky-joker-3h3', 'gangsta-casino',
]);
const ILLUMINATOR_CODES = new Set(['gold-of-baku', 'gold-of-baku-2', 'volt-coins']);
const SPIN_FACTORY_CODES = new Set(['big-catch', 'caesars-fortune', 'ice-spin-deluxe', 'tesla-spins']);

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

  try {
    const entries = await apiGet('/catalog');
    const ready = entries.filter((e) => READY_CODES.has(e.code));
    const illuminator = entries.filter((e) => ILLUMINATOR_CODES.has(e.code));
    const spinFactory = entries.filter((e) => SPIN_FACTORY_CODES.has(e.code));
    const dev = entries.filter((e) => !READY_CODES.has(e.code)
      && !ILLUMINATOR_CODES.has(e.code) && !SPIN_FACTORY_CODES.has(e.code));

    for (const entry of ready) appendCard(readyGrid, entry);
    for (const entry of illuminator) appendCard(illuminatorGrid, entry);
    for (const entry of spinFactory) appendCard(spinFactoryGrid, entry);
    for (const entry of dev) appendCard(devGrid, entry);
  } catch (err) {
    const li = document.createElement('li');
    li.innerHTML = `<div class="game-card"><div class="game-card__body"><p class="game-card__desc">Не удалось загрузить каталог: ${err.message}</p></div></div>`;
    readyGrid.appendChild(li);
  }

  toggleSection('readySection', readyGrid);
  toggleSection('illuminatorSection', illuminatorGrid);
  toggleSection('spinFactorySection', spinFactoryGrid);
  toggleSection('devSection', devGrid);
}

renderCatalog();
