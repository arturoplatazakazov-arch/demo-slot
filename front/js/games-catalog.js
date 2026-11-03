// Renders front/games.html's (and tg.html's) game cards from GET /api/v1/catalog
// (published games only — see app/api/v1/catalog.py) instead of the old
// hand-written static <li> blocks, so a slot published via the builder
// wizard's "all OK" action shows up here automatically. Reuses apiGet from
// js/api.js (loaded before this script) for the same base-URL resolution as
// the play pages.
//
// Where each section is shown:
//   - Готовые игры (READY_CARDS): tg.html, the bot's public catalog.
//   - Project tabs on games.html, each behind its own password (ROOMS in
//     games.html):
//       - Illuminator: ILLUMINATOR_CARDS (hand-ordered, one card per variant page).
//       - Uniqorn, four blocks top to bottom: «Игры с маскотом»
//         (UNIQORN_MASCOT_CODES), «В работе» (UNIQORN_WIP_CODES), «Готовые
//         игры» (READY_CARDS again), «Архив»
//         (every other unicorn game: uniqorn-*, mr-president-unicorn) —
//         the archive always goes last.
//       - Spin Factory: SPIN_FACTORY_CODES (was «В работе») + SPIN_FACTORY_EXTRA_CARDS.
//       - Secret Room: Cre8Pics analogues (CRE8_CODES: provider2 + provider3
//         + earlier ones; the section ids are still cre8*).
//     On localhost games.html opens every tab without passwords, plus Ready.
// A game in no list is shown nowhere — add its code to a room's list.
// The lists are explicit codes rather than "first N by created_at", so a
// newly seeded game doesn't shift others between rooms. Within a code-set
// section, cards go newest first (GET /catalog lists by created_at ascending, so the
// order is reversed here). A game not yet live on a given backend simply
// isn't in `entries` and is skipped. A section with zero cards hides itself
// (including its heading) rather than showing an empty title.
// Готовые игры in a fixed order, newest first (the same on every backend,
// whatever the created_at in its DB).
const READY_CARDS = [
  'gangsta-casino', 'lucky-joker-3h3', 'multi-fruits-story', 'wild-western-story',
  'sugar-galaxy', 'party-of-goods', 'neon-reels', 'golden-caravan',
  'east-discovery', 'dirty-money-mafia', 'amys-fruit-farm',
];
// Games shipped in several front-end layouts over one backend game: one
// page per variant. A card can point at any of them (overrides below).
const NJS_VARIANTS = {
  original: { page: 'neon-joker-spins.html', name: 'Neon Joker Spins · Original', badge: 'Оригинал', cover: 'img/neon-joker-spins/img/cover.jpg' },
  a: { page: 'neon-joker-spins-a.html', name: 'Neon Joker Spins · A', badge: 'Neon Sign',
    cover: 'img/neon-joker-spins/skins/a/img/cover.jpg',
    desc: 'Плоский неон 80-х: светящиеся трубки, мокрый асфальт, неоновая рама.' },
  b: { page: 'neon-joker-spins-b.html', name: 'Neon Joker Spins · B', badge: 'Glossy Show',
    cover: 'img/neon-joker-spins/skins/b/img/cover.jpg',
    desc: 'Глянцевое шоу: объёмные символы, золотая рама с лампочками, сцена.' },
  c: { page: 'neon-joker-spins-c.html', name: 'Neon Joker Spins · C', badge: 'Rock Chrome',
    cover: 'img/neon-joker-spins/skins/c/img/cover.jpg',
    desc: 'Рок-клуб: сталь и хром, Джокер-панк, молнии вместо линий выигрыша.' },
  d: { page: 'neon-joker-spins-d.html', name: 'Neon Joker Spins · D', badge: 'Retro 80s',
    cover: 'img/neon-joker-spins/skins/d/img/cover.jpg',
    desc: 'Автомат 80-х: хромированный корпус, барабаны под стеклом, лампы и рычаг.' },
};
const SAVANNAH_VARIANTS = {
  v3: { page: 'savannah-kings-v3.html', name: 'Savannah Kings',
    desc: 'Закатная саванна, каменная рамка: лестница джекпотов с GRAND в центре, медальоны покупки и выигрыша.',
    cover: 'img/savannah-kings/cover_v3.jpg' },
  lions: { page: 'lions-reign.html', name: "Lion's Reign",
    desc: 'Королевская версия: базальт с золотой филигранью и рубинами, символы в геральдических щитах, лев в короне.',
    cover: 'img/lions-reign/cover.jpg' },
  golden: { page: 'golden-savannah.html', name: 'Golden Savannah',
    desc: 'Графичная версия: африканский ар-деко и бумажная аппликация, узоры кенте, символы в ромбах.',
    cover: 'img/golden-savannah/cover.jpg' },
  classic: { page: 'savannah-kings.html', name: 'Savannah Kings · Classic',
    desc: 'Первая сборка: оригинальный арт, нижний бар управления, плашка выигрыша на барабанах.',
    cover: 'img/savannah-kings/cover_v1.jpg' },
  prideRock: { page: 'savannah-kings-v2.html', name: 'Savannah Kings · Pride Rock',
    desc: 'Альтернативная раскладка UI: скала гордости, панель управления сбоку от барабанов.',
    cover: 'img/savannah-kings/cover_v2.jpg' },
};
const njs = (key, extra) => ({ code: 'neon-joker-spins', ...NJS_VARIANTS[key], ...extra });
const savannah = (key, extra) => ({ code: 'savannah-kings', ...SAVANNAH_VARIANTS[key], ...extra });

// Illuminator: hand-ordered cards (first card first). A card is a game code
// or { code, page, name, badge, desc, cover } overriding the /catalog entry;
// badge: null keeps the game's own badge.
const ILLUMINATOR_CARDS = [
  'volt-coins',
  njs('c', { name: 'Neon Joker Spins', badge: null, desc: null }),
  'olympus-thunder',
  'olympus-thunder-v2',
  savannah('golden', { badge: null }),
];
// Spin Factory: its own games newest first, then the variants moved out of
// Illuminator, in this order.
const SPIN_FACTORY_CODES = new Set(['big-catch', 'caesars-fortune', 'ice-spin-deluxe', 'tesla-spins']);
const SPIN_FACTORY_EXTRA_CARDS = [
  'gold-of-baku',
  'gold-of-baku-2',
  njs('original'),
  njs('a'),
  njs('b'),
  njs('d'),
  'olympus-thunder-v3',
  savannah('v3'),
  savannah('lions'),
  savannah('classic'),
  savannah('prideRock'),
];
const CRE8_CODES = new Set([
  // provider2
  'rad-raiders', 'jade-paws', 'ghoul-groove', 'gummy-gold-rush', 'whisker-noir',
  'cogwork-skies', 'hex-hollow', 'bayou-bedlam', 'jaguar-eclipse', 'trident-vs-titan',
  // provider3
  'gladiator-gig', 'pyramid-pals', 'piggy-bankers', 'grit-and-gold', 'barnyard-bonanza',
  'stone-age-stash', 'tnt-tunnels', 'vault-runners', 'big-top-bonkers', 'parrot-plunder',
  'skull-harbor', 'sugar-rush-dj', 'pup-fishermen', 'pharaoh-hippo', 'bison-thunder',
  'evolve-rush', 'cash-kingpin',
  // earlier Cre8Pics reskins
  'deep-fortune', 'mariachi-muertos', 'monster-factory',
]);


const UNIQORN_MASCOT_CODES = new Set([]);
const UNIQORN_WIP_CODES = new Set(['great-uniqorn']);
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

// Builds the card entries of a hand-ordered list from the /catalog entries;
// games not live on this backend are skipped.
function resolveCards(cards, byCode) {
  return cards.flatMap((card) => {
    const spec = typeof card === 'string' ? { code: card } : card;
    const entry = byCode.get(spec.code);
    if (!entry) return [];
    return [{
      ...entry,
      name: spec.name || entry.name,
      catalog_badge: spec.badge === undefined || spec.badge === null ? entry.catalog_badge : spec.badge,
      catalog_play_url: spec.page || entry.catalog_play_url,
      catalog_cover_path: spec.cover || entry.catalog_cover_path,
      catalog_description: spec.desc || entry.catalog_description,
      fallbackCover: entry.catalog_cover_path,
    }];
  });
}

function appendCards(gridEl, entries) {
  for (const entry of entries) {
    appendCard(gridEl, entry);
    // Variant covers are optional screenshots: fall back to the game cover.
    const img = gridEl.lastElementChild.querySelector('.game-card__img');
    if (entry.fallbackCover && img) {
      img.addEventListener('error', () => { img.src = entry.fallbackCover; }, { once: true });
    }
  }
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
  const uniqornMascotGrid = document.getElementById('uniqornMascotGrid');
  const uniqornWipGrid = document.getElementById('uniqornWipGrid');
  const uniqornReadyGrid = document.getElementById('uniqornReadyGrid');
  const uniqornGrid = document.getElementById('uniqornGrid');
  const cre8Grid = document.getElementById('cre8Grid');
  const grids = [readyGrid, illuminatorGrid, spinFactoryGrid, uniqornGrid, cre8Grid].filter(Boolean);

  try {
    const entries = (await apiGet('/catalog')).reverse();
    const byCode = new Map(entries.map((e) => [e.code, e]));

    if (readyGrid) appendCards(readyGrid, resolveCards(READY_CARDS, byCode));
    if (illuminatorGrid) appendCards(illuminatorGrid, resolveCards(ILLUMINATOR_CARDS, byCode));
    if (spinFactoryGrid) {
      appendCards(spinFactoryGrid, entries.filter((e) => SPIN_FACTORY_CODES.has(e.code)));
      appendCards(spinFactoryGrid, resolveCards(SPIN_FACTORY_EXTRA_CARDS, byCode));
    }
    if (uniqornMascotGrid) appendCards(uniqornMascotGrid, entries.filter((e) => UNIQORN_MASCOT_CODES.has(e.code)));
    if (uniqornWipGrid) appendCards(uniqornWipGrid, entries.filter((e) => UNIQORN_WIP_CODES.has(e.code)));
    if (uniqornReadyGrid) appendCards(uniqornReadyGrid, resolveCards(READY_CARDS, byCode));
    if (uniqornGrid) {
      appendCards(uniqornGrid, entries.filter((e) => isUnicornGame(e.code) && !UNIQORN_MASCOT_CODES.has(e.code) && !UNIQORN_WIP_CODES.has(e.code)));
    }
    if (cre8Grid) appendCards(cre8Grid, entries.filter((e) => CRE8_CODES.has(e.code)));
  } catch (err) {
    const li = document.createElement('li');
    li.innerHTML = `<div class="game-card"><div class="game-card__body"><p class="game-card__desc">Не удалось загрузить каталог: ${err.message}</p></div></div>`;
    grids[0].appendChild(li);
  }

  if (readyGrid) toggleSection('readySection', readyGrid);
  if (illuminatorGrid) toggleSection('illuminatorSection', illuminatorGrid);
  if (spinFactoryGrid) toggleSection('spinFactorySection', spinFactoryGrid);
  if (uniqornGrid) {
    toggleSection('uniqornMascotSection', uniqornMascotGrid);
    toggleSection('uniqornWipSection', uniqornWipGrid);
    toggleSection('uniqornReadySection', uniqornReadyGrid);
    toggleSection('uniqornArchiveSection', uniqornGrid);
    // секция видна, если непуст хоть один из блоков
    document.getElementById('uniqornSection').hidden = ![uniqornMascotGrid, uniqornWipGrid, uniqornReadyGrid, uniqornGrid]
      .some((grid) => grid && grid.children.length);
  }
  if (cre8Grid) toggleSection('cre8Section', cre8Grid);
}

// games.html calls renderCatalog() itself once a tab's password is in (only
// the unlocked tabs' sections are in its DOM then).
if (!window.CATALOG_MANUAL_RENDER) renderCatalog();
