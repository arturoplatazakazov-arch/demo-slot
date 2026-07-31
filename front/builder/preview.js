// Stage 5 of the slot builder wizard: a read-only render of what Stages
// 2-4 saved (background + positioned objects), so you can look at the
// composed screen without opening the Konva editor, plus quick links back
// to each stage to fix something. Purely display — CSS transform:scale is
// enough here since nothing gets dragged or written back.
// apiRequest/setStatus/API_BASE come from common.js.

const params = new URLSearchParams(window.location.search);
const SLUG = params.get('slug');

const NATIVE = {
  desktop: { w: 1932, h: 940 },
  mobile: { w: 780, h: 1416 },
};

const DEFAULT_GAP = 10;

let manifest = null;
let currentDevice = 'desktop';
let currentScreen = 'base';

// Two Spine WebGL canvases/stages, not one — a single canvas is one flat
// plane at ONE fixed position relative to the rest of the DOM, so
// addBase/addOverlay only orders Spine content *among itself*, never
// against #previewScreen's own DOM content (a static image background
// always occludes anything drawn on a canvas positioned behind it,
// regardless of any z-index). spineStage's canvas sits behind
// #previewScreen (correct for a Spine background — real DOM decor drawn on
// top of it still shows); overlaySpineStage's canvas sits in front of
// #previewScreen instead, for decor.spine "layers on top" objects, which
// need to actually be visible on top of everything, including an image
// background. Both are created once at init and never torn down; only the
// SpineInstances anchored to them get replaced each render, since
// renderScreen() wipes #previewScreen's DOM children — including any
// previous anchor div — on every call.
let spineStage = null;
let overlaySpineStage = null;
let bgSpineInstance = null;
let overlaySpineInstances = [];
let renderToken = 0;

// rows x reels 2D array of the current screen's reel_block cell <div>s (same
// shape as js/play/manifest-render.js's hooks.reelCells) — set by
// renderScreen() whenever a system.reel_block object exists on the current
// screen/device, so a test spin can drop real symbol art straight into the
// same cells the player would see, instead of a separate schematic table.
let reelCells = null;
// code -> real image URL, resolved once per page load from the *draft*
// config's own symbols (GET /api/admin/configs/{id}, not the public
// /api/v1/config/{code}/symbols used by the live player — that one only
// serves an ACTIVE config, and the whole point of Stage 5 is testing before
// publish).
let codeToUrl = {};

function imgUrl(file) { return `../img/${SLUG}/${file}`; }

function getGridSize() {
  if (manifest.grid && manifest.grid.reels && manifest.grid.rows) {
    return { reels: manifest.grid.reels, rows: manifest.grid.rows };
  }
  return { reels: 5, rows: 3 };
}

function renderScreen() {
  const native = NATIVE[currentDevice];
  const frame = document.getElementById('previewFrame');
  const screen = document.getElementById('previewScreen');
  screen.innerHTML = '';

  const myToken = ++renderToken;
  if (bgSpineInstance) { spineStage.removeBase(bgSpineInstance); bgSpineInstance = null; }
  overlaySpineInstances.forEach((inst) => overlaySpineStage.removeBase(inst));
  overlaySpineInstances = [];

  const maxW = Math.min(frame.parentElement.clientWidth, 1150);
  const maxH = window.innerHeight - 420;
  const scale = Math.min(maxW / native.w, maxH / native.h, 1);

  frame.style.width = `${native.w * scale}px`;
  frame.style.height = `${native.h * scale}px`;
  screen.style.width = `${native.w}px`;
  screen.style.height = `${native.h}px`;
  screen.style.transform = `scale(${scale})`;

  const layoutForDevice = manifest.layouts[currentDevice];
  const bg = layoutForDevice.backgrounds[currentScreen];
  if (bg && bg.animation_ref) {
    const anim = manifest.assets.animations.find((a) => a.id === bg.animation_ref);
    if (anim) {
      const bgAnchor = document.createElement('div');
      bgAnchor.className = 'preview-object';
      bgAnchor.style.left = `${bg.x - bg.w / 2}px`;
      bgAnchor.style.top = `${bg.y - bg.h / 2}px`;
      bgAnchor.style.width = `${bg.w}px`;
      bgAnchor.style.height = `${bg.h}px`;
      bgAnchor.style.zIndex = 0;
      screen.appendChild(bgAnchor);
      SpineEngine.SpineResource.load(spineStage.assetManager, imgUrl(anim.folder)).then((resource) => {
        if (myToken !== renderToken) return; // a later renderScreen() already ran; this anchor is dead
        const inst = resource.createInstance();
        inst.anchorEl = bgAnchor;
        inst.fit = 1;
        inst.play(bg.animation_name || 'idle', true);
        spineStage.addBaseBehindAll(inst);
        bgSpineInstance = inst;
      });
    }
  } else if (bg) {
    const bgAsset = manifest.assets.images.find((i) => i.id === bg.asset_id);
    if (bgAsset) {
      const bgEl = document.createElement('img');
      bgEl.className = 'preview-object';
      bgEl.src = imgUrl(bgAsset.file);
      bgEl.style.left = `${bg.x - bg.w / 2}px`;
      bgEl.style.top = `${bg.y - bg.h / 2}px`;
      bgEl.style.width = `${bg.w}px`;
      bgEl.style.height = `${bg.h}px`;
      bgEl.style.zIndex = 0;
      screen.appendChild(bgEl);
    }
  }

  reelCells = null;
  const objects = [...(layoutForDevice.screens[currentScreen] || [])].sort((a, b) => a.z_index - b.z_index);
  objects.forEach((obj, i) => {
    let el;
    if (obj.animation_ref) {
      const anim = manifest.assets.animations.find((a) => a.id === obj.animation_ref);
      if (!anim) return;
      el = document.createElement('div');
      el.className = 'preview-object';
    } else if (obj.image_ref) {
      const asset = manifest.assets.images.find((img) => img.id === obj.image_ref);
      if (!asset) return;
      el = document.createElement('img');
      el.src = imgUrl(asset.file);
      el.className = 'preview-object';
    } else {
      el = document.createElement('div');
      el.className = 'preview-object preview-object--reelblock';
      const { reels, rows } = getGridSize();
      const cellW = obj.cell_w ?? Math.max(10, (obj.w - DEFAULT_GAP * (reels - 1)) / reels);
      const cellH = obj.cell_h ?? Math.max(10, (obj.h - DEFAULT_GAP * (rows - 1)) / rows);
      const gapX = obj.gap_x ?? DEFAULT_GAP;
      const gapY = obj.gap_y ?? DEFAULT_GAP;
      const cells = [];
      for (let r = 0; r < rows; r++) {
        const rowCells = [];
        for (let c = 0; c < reels; c++) {
          const cell = document.createElement('div');
          cell.className = 'preview-cell';
          cell.style.left = `${c * (cellW + gapX)}px`;
          cell.style.top = `${r * (cellH + gapY)}px`;
          cell.style.width = `${cellW}px`;
          cell.style.height = `${cellH}px`;
          el.appendChild(cell);
          rowCells.push(cell);
        }
        cells.push(rowCells);
      }
      reelCells = cells;
    }
    el.style.left = `${obj.x - obj.w / 2}px`;
    el.style.top = `${obj.y - obj.h / 2}px`;
    el.style.width = `${obj.w}px`;
    el.style.height = `${obj.h}px`;
    el.style.zIndex = i + 1;
    screen.appendChild(el);

    if (obj.animation_ref) {
      const anim = manifest.assets.animations.find((a) => a.id === obj.animation_ref);
      SpineEngine.SpineResource.load(overlaySpineStage.assetManager, imgUrl(anim.folder)).then((resource) => {
        if (myToken !== renderToken) return; // a later renderScreen() already ran; this anchor is dead
        const inst = resource.createInstance();
        inst.anchorEl = el;
        inst.fit = 1;
        inst.play(obj.animation_name || 'idle', true);
        overlaySpineStage.addBase(inst);
        overlaySpineInstances.push(inst);
      });
    }
  });
}

// Loads code -> real image URL for the *draft* config (manifest.game_config_id)
// via the admin config-detail endpoint, which — unlike the public
// /api/v1/config/{code}/symbols the live player uses — returns symbols for
// any config regardless of DRAFT/ACTIVE status.
async function loadDraftSymbolArtMap() {
  if (!manifest.game_config_id) return {};
  const configBase = API_BASE.replace(/\/builder$/, '');
  const response = await fetch(`${configBase}/configs/${manifest.game_config_id}`);
  if (!response.ok) return {};
  const config = await response.json();
  const map = {};
  for (const symbol of config.symbols) {
    if (!symbol.image_ref) continue;
    const asset = manifest.assets.images.find((img) => img.id === symbol.image_ref);
    if (asset) map[symbol.code] = imgUrl(asset.file);
  }
  return map;
}

// rowMajor=true means grid[row][reel] (avalanche's to_frontend_grid
// convention); rowMajor=false means grid[reel][row] (the line-pay branch's
// own historical shape — see run_builder_test_spin's two return shapes).
// Renders straight into the live preview screen's own reel_block cells
// (reelCells) with real symbol art, instead of a separate schematic table —
// same renderSymbolInCell used by the actual player (js/play/symbols.js).
function renderGridIntoCells(grid, rowMajor) {
  if (!reelCells) return;
  const rows = reelCells.length;
  const reels = reelCells[0].length;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < reels; c++) {
      const code = rowMajor ? grid[r][c] : grid[c][r];
      renderSymbolInCell(reelCells[r][c], code, codeToUrl);
    }
  }
}

function clearCellHighlights() {
  if (!reelCells) return;
  for (const row of reelCells) for (const cell of row) cell.classList.remove('is-winner');
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function playAvalancheOnScreen(avalanche) {
  let html = avalanche.steps.length === 0
    ? '<p class="hint">Без каскадов в этом спине — крути ещё раз.</p>'
    : '';
  for (let i = 0; i < avalanche.steps.length; i++) {
    const step = avalanche.steps[i];
    const clearedCount = step.wins.reduce((n, w) => n + w.positions.length, 0)
      + step.tokens_consumed.length
      + step.bombs_detonated.reduce((n, b) => n + b.cleared.length, 0);
    html += `<p class="hint">Каскад ${i + 1}: множитель ×${step.step_multiplier}, выигрыш шага ${step.step_win}${clearedCount ? ` (убрано ${clearedCount} ячеек)` : ''}</p>`;

    if (reelCells) {
      const cleared = new Set();
      for (const win of step.wins) for (const p of win.positions) cleared.add(`${p.row},${p.col}`);
      for (const token of step.tokens_consumed) cleared.add(`${token.row},${token.col}`);
      for (const bomb of step.bombs_detonated) for (const c of bomb.cleared) cleared.add(`${c.row},${c.col}`);
      for (const key of cleared) {
        const [r, c] = key.split(',').map(Number);
        if (reelCells[r] && reelCells[r][c]) reelCells[r][c].classList.add('is-winner');
      }
      await pause(500);
      clearCellHighlights();
      renderGridIntoCells(step.grid_after, true);
      await pause(400);
    }
  }
  return html;
}

async function applyTestSpinResult(result) {
  const el = document.getElementById('testSpinResult');
  el.hidden = false;

  if (result.avalanche) {
    renderGridIntoCells(result.grid, true);
    el.innerHTML = `<p>Ставка: ${result.bet_amount} · Итоговый выигрыш: <strong>${result.total_win}</strong></p>`;
    const cascadeHtml = await playAvalancheOnScreen(result.avalanche);
    el.innerHTML += cascadeHtml;
    return;
  }

  renderGridIntoCells(result.grid, false);
  if (reelCells) {
    for (const wc of (result.winning_cells || [])) {
      if (reelCells[wc.row] && reelCells[wc.row][wc.col]) reelCells[wc.row][wc.col].classList.add('is-winner');
    }
  }
  const winLines = [
    ...result.line_wins.map((w) => `<li>Линия ${w.payline}: ${w.symbol} ×${w.count} — ${w.amount}</li>`),
    ...result.count_wins.map((w) => `<li>${w.symbol} ×${w.count} (по всей сетке) — ${w.amount}</li>`),
  ];
  const winsHtml = winLines.length > 0
    ? `<ul>${winLines.join('')}</ul>`
    : '<p class="hint">Без выигрыша в этом спине — крути ещё раз.</p>';
  el.innerHTML = `
    <p>Ставка: ${result.bet_amount} · Выигрыш: <strong>${result.total_win}</strong></p>
    ${winsHtml}
  `;
}

function updateBackLinks() {
  const q = `?slug=${encodeURIComponent(SLUG)}`;
  document.getElementById('backToAssetsBtn').href = `assets.html${q}`;
  document.getElementById('backToGridBtn').href = `grid.html${q}`;
  document.getElementById('backToLayoutBtn').href = `layout.html${q}`;
}

function findCatalogCoverAsset() {
  return manifest.assets.images.find((img) => img.category === 'catalog') || null;
}

function renderCatalogCoverThumb() {
  const thumb = document.getElementById('catalogCoverThumb');
  const cover = findCatalogCoverAsset();
  thumb.innerHTML = cover
    ? `<img class="gallery-item__thumb" src="${imgUrl(cover.file)}" alt="">`
    : '<p class="gallery-empty" id="catalogCoverEmpty">Нет обложки</p>';
}

// Prefills badge/description/cover from what's already published (if
// anything) so re-publishing just to add/replace a cover doesn't force
// retyping text that was already set on an earlier publish-live call.
async function prefillFromCatalog() {
  try {
    const response = await fetch(`${API_BASE.replace(/\/admin\/builder$/, '/v1')}/catalog`);
    if (!response.ok) return;
    const entries = await response.json();
    const entry = entries.find((g) => g.code === SLUG);
    if (!entry) return;
    if (entry.catalog_badge) document.getElementById('publishBadgeInput').value = entry.catalog_badge;
    if (entry.catalog_description) document.getElementById('publishDescriptionInput').value = entry.catalog_description;
  } catch {
    // best-effort prefill only — a failure here shouldn't block the page
  }
}

async function init() {
  if (!SLUG) {
    document.querySelector('main').innerHTML = '<section class="panel"><p class="hint">Не указан слаг слота (нет ?slug=... в адресе). Вернись к <a href="new.html">списку слотов</a>.</p></section>';
    return;
  }

  spineStage = new SpineEngine.SpineStage(document.getElementById('previewSpineCanvas'));
  overlaySpineStage = new SpineEngine.SpineStage(document.getElementById('previewSpineOverlayCanvas'));

  manifest = await apiRequest('GET', `/games/${SLUG}`);
  document.getElementById('slotName').textContent = `— ${manifest.meta.display_name} (${manifest.meta.slug})`;
  document.title = `Конструктор слота — ${manifest.meta.display_name} — Этап 5`;
  updateBackLinks();
  renderScreen();
  renderCatalogCoverThumb();
  codeToUrl = await loadDraftSymbolArtMap();
  prefillFromCatalog();

  document.getElementById('deviceSelect').addEventListener('change', (e) => {
    currentDevice = e.target.value;
    renderScreen();
  });
  document.getElementById('screenSelect').addEventListener('change', (e) => {
    currentScreen = e.target.value;
    renderScreen();
  });
  window.addEventListener('resize', renderScreen);

  document.getElementById('testSpinBtn').addEventListener('click', async () => {
    // The base game is what a spin result actually describes — switch there
    // first (feature/bonus transitions aren't simulated by this test-spin
    // endpoint) so reelCells always exists to render real art into.
    if (currentScreen !== 'base') {
      currentScreen = 'base';
      document.getElementById('screenSelect').value = 'base';
      renderScreen();
    }
    setStatus('testSpinStatus', 'Кручу…');
    try {
      const result = await apiRequest('POST', `/games/${SLUG}/test-spin`);
      setStatus('testSpinStatus', 'Готово.', 'is-ok');
      await applyTestSpinResult(result);
    } catch (err) {
      setStatus('testSpinStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('catalogCoverBtn').addEventListener('click', () => document.getElementById('catalogCoverInput').click());
  document.getElementById('catalogCoverInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    setStatus('catalogCoverStatus', 'Загружаю…');
    try {
      const formData = new FormData();
      formData.set('kind', 'image');
      formData.set('category', 'catalog');
      formData.set('file', file);
      manifest = await apiUpload(`/games/${SLUG}/assets`, formData);
      const newId = manifest._uploaded_asset_id;
      // Only one catalog cover at a time — publish-live picks the *first*
      // category:catalog image it finds, so a stale older one left in the
      // manifest would silently keep winning over this new upload.
      const stale = manifest.assets.images.filter((img) => img.category === 'catalog' && img.id !== newId);
      for (const img of stale) {
        manifest = await apiRequest('DELETE', `/games/${SLUG}/assets/${img.id}`);
      }
      renderCatalogCoverThumb();
      setStatus('catalogCoverStatus', 'Обложка загружена — нажми «Опубликовать», чтобы применить.', 'is-ok');
    } catch (err) {
      setStatus('catalogCoverStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('publishLiveBtn').addEventListener('click', async () => {
    const badge = document.getElementById('publishBadgeInput').value.trim();
    const description = document.getElementById('publishDescriptionInput').value.trim();
    if (!badge || !description) {
      setStatus('previewStatus', 'Укажи и бейдж, и описание.', 'is-error');
      return;
    }
    setStatus('previewStatus', 'Публикую…');
    try {
      const result = await apiRequest('POST', `/games/${SLUG}/publish-live`, { badge, description });
      await apiRequest('POST', `/games/${SLUG}/stage`, { stage: 5 });
      setStatus('previewStatus', 'Опубликовано.', 'is-ok');
      const resultEl = document.getElementById('publishResult');
      resultEl.hidden = false;
      resultEl.innerHTML = `
        <p class="hint">Слот в каталоге и доступен для игры.</p>
        <div class="back-links">
          <a class="btn btn--primary" href="../${result.catalog_play_url}" target="_blank">Играть →</a>
          <a class="btn" href="../games.html" target="_blank">Каталог →</a>
        </div>
      `;
    } catch (err) {
      setStatus('previewStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });
}

init().catch((err) => {
  document.querySelector('main').innerHTML = `<section class="panel"><p class="hint">Не удалось загрузить слот "${SLUG}": ${err.message}</p></section>`;
});
