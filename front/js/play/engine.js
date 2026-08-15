// Orchestrates a real play session for a slot-builder game: session/start,
// spin, buy-bonus, rendering results onto the manifest-driven screen from
// manifest-render.js. Deliberately simple for v1 — a crossfade/highlight on
// winning cells and a plain free-spins-counter/multiplier text overlay, no
// Spine playback or avalanche/hold-and-win choreography (those stay
// exclusive to the 4 hand-built demo games for now).

const SLUG = new URLSearchParams(window.location.search).get('slug');

let manifest = null;
let device = pickDevice();
let screen = 'base';
let hooks = null;
let codeToUrl = {};
let codeToFolder = {};
let symbolSpineInstances = [];
let symbolToken = 0;
const symbolResourceCache = {}; // folder -> Promise<SpineResource>
let sessionId = null;
let balance = 0;
let betConfig = null;
let betIndex = 0;
let spinInFlight = false;

// Two Spine WebGL canvases/stages, not one — a single canvas is one flat
// plane at ONE fixed position relative to the rest of the DOM, so
// addBase/addOverlay only orders Spine content *among itself*, never
// against #playScreen's own DOM content (a static image background always
// occludes anything drawn on a canvas positioned behind it, regardless of
// any z-index). spineStage's canvas sits behind #playScreen (correct for a
// Spine background); overlaySpineStage's canvas sits in front of
// #playScreen instead, for decor.spine "layers on top" objects, which need
// to be visible on top of everything, including an image background. Both
// are created once at init and never torn down (spine-engine.js's
// SpineStage owns its own rAF loop tied to a specific <canvas>); only the
// SpineInstances anchored to them get replaced each renderCurrentScreen(),
// since that wipes #playScreen's DOM children — including any previous
// anchor div.
let spineStage = null;
let overlaySpineStage = null;
let bgSpineInstance = null;
let overlaySpineInstances = [];
let renderToken = 0;

function setStatus(text, kind) {
  const el = document.getElementById('playStatus');
  el.textContent = text || '';
  el.className = 'play-status-float' + (kind ? ` is-${kind}` : '');
}

function updateBalanceUI() {
  document.getElementById('balanceValue').textContent = balance.toLocaleString();
}

function currentBet() {
  return betConfig.steps[betIndex];
}

function updateBetUI() {
  document.getElementById('betValue').textContent = currentBet().toLocaleString();
}

function updateSpinButtonUI() {
  // V3 bar: rotation is driven by the .is-spinning class (ui-bar-v3.js watches it).
  const spin = document.querySelector('[data-action="spin"]');
  if (spin) spin.classList.toggle('is-spinning', spinInFlight);
  const down = document.querySelector('[data-action="bet-minus"]');
  const up = document.querySelector('[data-action="bet-plus"]');
  if (down) down.disabled = spinInFlight || betIndex === 0;
  if (up) up.disabled = spinInFlight || betIndex === betConfig.steps.length - 1;
}

function updateFreeSpinsCounterUI(remaining) {
  if (!hooks.freeSpinsCounterText) return;
  hooks.freeSpinsCounterText.textContent = remaining > 0 ? String(remaining) : '';
}

function updateMultiplierUI(value) {
  if (!hooks.multiplierEl) return;
  hooks.multiplierEl.hidden = value == null;
  if (value != null) hooks.multiplierText.textContent = `×${value}`;
}

function renderCurrentScreen() {
  hooks = renderManifestScreen(manifest, SLUG, device, screen);
  if (hooks.buyBonusEl) hooks.buyBonusEl.addEventListener('click', onBuyBonusClick);
  updateFreeSpinsCounterUI(0);
  updateMultiplierUI(null);
  reconcileBgSpine();
  reconcileOverlaySpine();
  clearSymbolSpine(); // drop symbol instances anchored to the now-removed cells
}

function reconcileBgSpine() {
  const myToken = ++renderToken;
  if (bgSpineInstance) { spineStage.removeBase(bgSpineInstance); bgSpineInstance = null; }
  if (!hooks.bgSpineAnchor) return;
  const { el, folder, animationName } = hooks.bgSpineAnchor;
  SpineEngine.SpineResource.load(spineStage.assetManager, `img/${SLUG}/${folder}`).then((resource) => {
    if (myToken !== renderToken) return; // a later renderCurrentScreen() already ran; this anchor is dead
    const inst = resource.createInstance();
    inst.anchorEl = el;
    inst.fit = 1;
    inst.play(animationName || 'idle', true);
    spineStage.addBaseBehindAll(inst);
    bgSpineInstance = inst;
  });
}

// decor.spine overlay objects — unlimited, drawn on top of everything (same
// track hand-built games use for win-celebration FX), unlike the single
// exclusive background slot above.
function reconcileOverlaySpine() {
  const myToken = renderToken; // reconcileBgSpine already bumped it this render
  overlaySpineInstances.forEach((inst) => overlaySpineStage.removeBase(inst));
  overlaySpineInstances = [];
  for (const { el, folder, animationName } of hooks.spineObjectAnchors || []) {
    SpineEngine.SpineResource.load(overlaySpineStage.assetManager, `img/${SLUG}/${folder}`).then((resource) => {
      if (myToken !== renderToken) return;
      const inst = resource.createInstance();
      inst.anchorEl = el;
      inst.fit = 1;
      inst.play(animationName || 'idle', true);
      overlaySpineStage.addBase(inst);
      overlaySpineInstances.push(inst);
    });
  }
}

function clearWinHighlights() {
  if (!hooks.reelCells) return;
  for (const row of hooks.reelCells) for (const cell of row) cell.classList.remove('is-winner');
}

function renderGrid(grid) {
  // SpinResponse.grid is row-major — grid[row][reel] (see
  // app/services/grid_format.py's to_frontend_grid), same orientation as
  // hooks.reelCells and WinningCellOut's {row, col} (col == reel index).
  if (!hooks.reelCells) return;
  const rows = hooks.reelCells.length;
  const reels = hooks.reelCells[0].length;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < reels; c++) {
      renderSymbolInCell(hooks.reelCells[r][c], grid[r][c], codeToUrl);
    }
  }
  renderSymbolSpine(grid);
}

// Symbols uploaded as Spine bundles get animated in-cell (idle loop) instead of
// the flat static.png tile. Instances live on overlaySpineStage (in front of the
// reel background), anchored to each cell; the static <img> underneath stays as
// an instant/fallback render and is hidden once its Spine covers it. A folder
// with no Spine (or a load failure) just keeps the static tile.
function pickSymbolAnim(resource) {
  const names = (resource.skeletonData.animations || []).map((a) => a.name);
  return names.find((n) => /idle|loop|static|anim/i.test(n)) || names[0] || 'idle';
}

function clearSymbolSpine() {
  symbolToken++;
  for (const inst of symbolSpineInstances) overlaySpineStage.removeBase(inst);
  symbolSpineInstances = [];
  // The static tile was hidden the moment its Spine took over, so dropping the
  // instances without putting it back leaves empty cells — the same trap the
  // hand-built games have in teardownCellInstances. A cell that is meant to be
  // empty carries no `src`, so it stays hidden.
  if (hooks && hooks.reelCells) {
    for (const row of hooks.reelCells) {
      for (const cell of row) {
        const img = cell && cell.querySelector('.play-symbol-img');
        if (img && img.getAttribute('src')) img.style.visibility = '';
      }
    }
  }
}

function renderSymbolSpine(grid) {
  if (!overlaySpineStage || !hooks || !hooks.reelCells) return;
  clearSymbolSpine();
  const myToken = symbolToken;
  const rows = hooks.reelCells.length;
  const reels = hooks.reelCells[0].length;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < reels; c++) {
      const folder = codeToFolder[grid[r][c]];
      if (!folder) continue;
      const cell = hooks.reelCells[r][c];
      const p = symbolResourceCache[folder]
        || (symbolResourceCache[folder] = SpineEngine.SpineResource.load(overlaySpineStage.assetManager, `img/${SLUG}/${folder}`));
      p.then((resource) => {
        if (myToken !== symbolToken) return; // grid re-rendered since this load started
        const inst = resource.createInstance();
        inst.anchorEl = cell;
        inst.fit = 0.92;
        inst.play(pickSymbolAnim(resource), true);
        overlaySpineStage.addBase(inst);
        symbolSpineInstances.push(inst);
        const img = cell.querySelector('.play-symbol-img');
        if (img) img.style.visibility = 'hidden';
      }).catch(() => { /* keep the static tile on any load error */ });
    }
  }
}

function highlightWins(winningCells) {
  if (!hooks.reelCells) return;
  for (const wc of winningCells) {
    const cell = hooks.reelCells[wc.row] && hooks.reelCells[wc.row][wc.col];
    if (cell) cell.classList.add('is-winner');
  }
}

// SpinResponse.grid for an avalanche game is the INITIAL pre-cascade grid —
// caller already rendered it via renderGrid before calling this. Each step
// then: highlights whatever's about to clear (line/count wins + swept-up
// multiplier tokens + bomb blast radius — union of all three, no separate
// visual language per removal kind, matching the player's simple-by-design
// scope), pauses, re-renders from grid_after, shows the step's running
// multiplier, pauses again before the next step.
async function playAvalancheSteps(steps) {
  if (!hooks.reelCells) return;
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  for (const step of steps) {
    const cleared = new Set();
    for (const win of step.wins) for (const p of win.positions) cleared.add(`${p.row},${p.col}`);
    for (const token of step.tokens_consumed) cleared.add(`${token.row},${token.col}`);
    for (const bomb of step.bombs_detonated) for (const c of bomb.cleared) cleared.add(`${c.row},${c.col}`);
    for (const key of cleared) {
      const [r, c] = key.split(',').map(Number);
      const cell = hooks.reelCells[r] && hooks.reelCells[r][c];
      if (cell) cell.classList.add('is-winner');
    }
    await pause(500);
    clearWinHighlights();
    renderGrid(step.grid_after);
    updateMultiplierUI(step.step_multiplier > 1 ? step.step_multiplier : null);
    await pause(400);
  }
}

async function applySpinResult(result) {
  balance = result.balance;
  updateBalanceUI();
  clearWinHighlights();
  renderGrid(result.grid);

  if (result.avalanche) {
    await playAvalancheSteps(result.avalanche.steps);
  } else {
    highlightWins(result.winning_cells || []);
  }

  const multiplierValue = (result.coin_multiplier && result.coin_multiplier.applied)
    ? result.coin_multiplier.multiplier_sum
    : (result.feature ? result.feature.multiplier ?? null : null);
  // playAvalancheSteps already left the right thing showing (or nothing) —
  // don't stomp it with the (empty, for avalanche) coin_multiplier/feature fields.
  if (!result.avalanche) updateMultiplierUI(multiplierValue);

  if (result.feature) {
    const remaining = result.feature.spins_remaining ?? 0;
    if (remaining > 0) {
      if (screen !== 'bonus') { screen = 'bonus'; renderCurrentScreen(); }
      updateFreeSpinsCounterUI(remaining);
    } else if (screen === 'bonus') {
      updateFreeSpinsCounterUI(0);
      setTimeout(() => { screen = 'base'; renderCurrentScreen(); }, 1200);
    }
  }
}

async function onSpinClick() {
  if (spinInFlight) return;
  spinInFlight = true;
  updateSpinButtonUI();
  setStatus('Кручу…');
  try {
    const result = await apiPost('/spin', { session_id: sessionId, bet_amount: currentBet() });
    await applySpinResult(result);
    setStatus('');
  } catch (err) {
    setStatus(`Ошибка: ${err.message}`, 'error');
  } finally {
    spinInFlight = false;
    updateSpinButtonUI();
  }
}

async function onBuyBonusClick() {
  if (spinInFlight) return;
  spinInFlight = true;
  updateSpinButtonUI();
  setStatus('Покупаю бонус…');
  try {
    const result = await apiPost('/feature/buy', {
      session_id: sessionId, feature_id: 'bonus_buy', bet_amount: currentBet(),
    });
    await applySpinResult(result);
    setStatus('');
  } catch (err) {
    setStatus(`Ошибка: ${err.message}`, 'error');
  } finally {
    spinInFlight = false;
    updateSpinButtonUI();
  }
}

async function init() {
  if (!SLUG) {
    document.body.innerHTML = '<p class="play-error">Не указан слаг слота (нет ?slug=... в адресе).</p>';
    return;
  }
  spineStage = new SpineEngine.SpineStage(document.getElementById('playSpineCanvas'));
  overlaySpineStage = new SpineEngine.SpineStage(document.getElementById('playSpineOverlayCanvas'));
  try {
    manifest = await fetchManifest(SLUG);
    document.getElementById('gameName').textContent = manifest.meta.display_name;
    document.title = manifest.meta.display_name;

    const art = await loadSymbolArtMap(SLUG, manifest);
    codeToUrl = art.codeToUrl;
    codeToFolder = art.codeToFolder;

    const startResponse = await apiPost('/session/start', { game_id: SLUG });
    sessionId = startResponse.session_id;
    balance = startResponse.balance;
    betConfig = startResponse.bet;
    betIndex = betConfig.steps.indexOf(betConfig.default);
    if (betIndex === -1) betIndex = 0;

    renderCurrentScreen();
    updateBalanceUI();
    updateBetUI();
    updateSpinButtonUI();
  } catch (err) {
    document.body.innerHTML = `<p class="play-error">Не удалось загрузить слот "${SLUG}": ${err.message}</p>`;
    return;
  }

  document.querySelector('[data-action="spin"]').addEventListener('click', onSpinClick);
  document.querySelector('[data-action="bet-minus"]').addEventListener('click', () => {
    if (betIndex > 0) { betIndex -= 1; updateBetUI(); updateSpinButtonUI(); }
  });
  document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
    if (betIndex < betConfig.steps.length - 1) { betIndex += 1; updateBetUI(); updateSpinButtonUI(); }
  });
  const homeBtn = document.querySelector('[data-action="home"]');
  if (homeBtn) homeBtn.addEventListener('click', () => { window.location.href = 'games.html'; });
  window.addEventListener('resize', () => {
    const nextDevice = pickDevice();
    if (nextDevice !== device) { device = nextDevice; renderCurrentScreen(); }
    else renderCurrentScreen();
  });
}

init();
