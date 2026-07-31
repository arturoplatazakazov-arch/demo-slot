// Renders front/games.html's game cards from GET /api/v1/catalog (published
// games only — see app/api/v1/catalog.py) instead of the old hand-written
// static <li> blocks, so a slot published via the builder wizard's "all OK"
// action shows up here automatically. Reuses apiGet from js/api.js (loaded
// before this script) for the same base-URL resolution as the play pages.

const PLAY_ICON = '<svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8V4Z" fill="currentColor"/></svg>';
const ADMIN_ICON = '<svg viewBox="0 0 24 24"><path d="M19.4 13a7.5 7.5 0 0 0 0-2l2-1.5-2-3.4-2.4 1a7.7 7.7 0 0 0-1.7-1L15 3h-4l-.3 2.5a7.7 7.7 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a7.5 7.5 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7.7 7.7 0 0 0 1.7 1L11 21h4l.3-2.5a7.7 7.7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="13" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';

function gameCardHtml(entry) {
  const playUrl = entry.catalog_play_url || `play.html?slug=${encodeURIComponent(entry.code)}`;
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
          <a class="game-card__admin" href="admin/index.html?game=${encodeURIComponent(entry.code)}">${ADMIN_ICON} Админка</a>
        </div>
      </div>
    </div>
  `;
}

async function renderCatalog() {
  const grid = document.getElementById('gameGrid');
  // The 2 static utility cards (create-slot, anim-lab) already sit in the
  // HTML as <li>s — fetched game cards get inserted right before the first
  // one so they always lead, regardless of how many games are published.
  const staticStart = grid.querySelector('.static-card');
  try {
    const entries = await apiGet('/catalog');
    for (const entry of entries) {
      const li = document.createElement('li');
      li.innerHTML = gameCardHtml(entry);
      grid.insertBefore(li, staticStart);
    }
  } catch (err) {
    const li = document.createElement('li');
    li.innerHTML = `<div class="game-card"><div class="game-card__body"><p class="game-card__desc">Не удалось загрузить каталог: ${err.message}</p></div></div>`;
    grid.insertBefore(li, staticStart);
  }
}

renderCatalog();
