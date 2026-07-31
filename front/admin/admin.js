// Lightweight admin panel for game math: symbol weights, per-reel caps,
// paytables, and RTP/volatility/hit-frequency/bonus-frequency testing
// against a draft config before publishing it as active (see
// app/api/admin — draft/publish workflow, GameConfig is immutable once
// active). No build step, plain fetch — same convention as front/js/api.js.

const API_BASE = 'http://127.0.0.1:8000/api/admin';
// ?game=<slug> lets this same editor open any game (e.g. one just created
// via the builder wizard, front/builder/new.js); defaults to the original
// demo game so existing bookmarks/links without the param keep working.
const GAME_CODE = new URLSearchParams(window.location.search).get('game') || 'amys-fruit-farm';

let draft = null; // current draft config detail, or null if none loaded yet
let dirty = new Set(); // symbol ids with unsaved edits
let symbolAssets = []; // {id, file} for this game's builder-uploaded "symbol"-category images, if any

if (GAME_CODE !== 'amys-fruit-farm') {
  document.title = `${GAME_CODE} — Admin`;
  document.getElementById('pageTitle').textContent = `${GAME_CODE} — Game Math Admin`;
}

async function apiRequest(method, path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = (data && data.detail) || `${path} failed with HTTP ${response.status}`;
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return data;
}

function symbolAssetUrl(file) {
  return `../img/${GAME_CODE}/${file}`;
}

function fmtPct(fraction, digits = 2) {
  return `${(fraction * 100).toFixed(digits)}%`;
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString();
}

// ---------- Config version list ----------

async function loadConfigs() {
  const configs = await apiRequest('GET', `/games/${GAME_CODE}/configs`);
  renderConfigsTable(configs);

  const active = configs.find((c) => c.status === 'active');
  const existingDraft = configs.find((c) => c.status === 'draft');
  document.getElementById('statusLine').textContent = active
    ? `Active: v${active.version} (target RTP ${fmtPct(active.target_rtp)})${existingDraft ? ` — draft v${existingDraft.version} in progress` : ''}`
    : 'No active config';

  return { active, existingDraft };
}

function renderConfigsTable(configs) {
  const tbody = document.querySelector('#configsTable tbody');
  tbody.innerHTML = '';
  for (const c of configs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>v${c.version}</td>
      <td>${c.status}</td>
      <td>${fmtPct(c.target_rtp)}</td>
      <td>${c.notes || ''}</td>
      <td>${fmtDate(c.created_at)}</td>
    `;
    tbody.appendChild(tr);
  }
}

// ---------- Draft editor ----------

// The 4 hand-built demo games were never created via the builder wizard, so
// they have no BuilderDraft row and this 404s — that's expected, not an
// error: it just means no uploaded symbol art exists to pick from, same as
// an empty list.
async function loadSymbolAssets() {
  try {
    const manifest = await apiRequest('GET', `/builder/games/${GAME_CODE}`);
    symbolAssets = manifest.assets.images.filter((img) => img.category === 'symbol');
  } catch (err) {
    symbolAssets = [];
  }
}

async function editDraft() {
  const btn = document.getElementById('editDraftBtn');
  btn.disabled = true;
  try {
    draft = await apiRequest('POST', `/games/${GAME_CODE}/draft`);
    dirty.clear();
    await loadSymbolAssets();
    renderSymbolsEditor(draft);
    document.getElementById('editorPanel').hidden = false;
    document.getElementById('simPanel').hidden = false;
    document.getElementById('publishPanel').hidden = false;
    document.getElementById('draftVersionLabel').textContent = `v${draft.version}`;
    await loadHistory(draft.id);
    await loadConfigs();
  } catch (err) {
    alert(`Could not open a draft: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

function renderSymbolsEditor(config) {
  const headRow = document.getElementById('symbolsHeadRow');
  // Rebuild the reel-weight <th>s (count depends on config.num_reels) —
  // inserted right after the fixed "Symbol"/"Type" columns.
  headRow.querySelectorAll('.reel-col, .pay-col').forEach((th) => th.remove());
  const maxPerReelTh = document.getElementById('maxPerReelHeader');
  for (let i = 0; i < config.num_reels; i++) {
    const th = document.createElement('th');
    th.className = 'reel-col';
    th.textContent = `Reel ${i + 1}`;
    headRow.insertBefore(th, maxPerReelTh);
  }

  // Paytable columns aren't a fixed 3/4/5: line-pay games key by exact
  // match count (up to num_reels), avalanche games key by an open-ended
  // count-anywhere threshold (party-of-goods: 8/10/12/15), and a
  // builder-generated config (app/api/admin/builder_config.py) on a non-5
  // reel grid has yet another range — so the columns are whatever counts
  // actually appear across this config's symbols, not a hardcoded set.
  const payCounts = [...new Set(config.symbols.flatMap((s) => Object.keys(s.paytable).map(Number)))]
    .sort((a, b) => a - b);
  const counts = payCounts.length > 0 ? payCounts : [3, 4, 5];
  for (const count of counts) {
    const th = document.createElement('th');
    th.className = 'pay-col';
    th.textContent = `Pay ${count}`;
    headRow.appendChild(th);
  }

  const tbody = document.getElementById('symbolsBody');
  tbody.innerHTML = '';
  for (const symbol of config.symbols) {
    const tr = document.createElement('tr');
    tr.dataset.symbolId = symbol.id;

    const nameTd = document.createElement('td');
    nameTd.textContent = `${symbol.name} (${symbol.code})`;
    tr.appendChild(nameTd);

    const typeTd = document.createElement('td');
    typeTd.textContent = symbol.symbol_type;
    tr.appendChild(typeTd);

    const artTd = document.createElement('td');
    const artThumb = document.createElement('img');
    artThumb.className = 'symbol-art-thumb';
    artThumb.hidden = !symbol.image_ref;
    const artSelect = document.createElement('select');
    artSelect.dataset.field = 'imageRef';
    const noneOption = document.createElement('option');
    noneOption.value = '';
    noneOption.textContent = '— нет —';
    artSelect.appendChild(noneOption);
    for (const asset of symbolAssets) {
      const option = document.createElement('option');
      option.value = asset.id;
      option.textContent = asset.file;
      artSelect.appendChild(option);
    }
    artSelect.value = symbol.image_ref || '';
    const setThumb = () => {
      const asset = symbolAssets.find((a) => a.id === artSelect.value);
      artThumb.hidden = !asset;
      if (asset) artThumb.src = symbolAssetUrl(asset.file);
    };
    setThumb();
    if (symbol.image_ref && !symbolAssets.some((a) => a.id === symbol.image_ref)) {
      // A previously-picked asset that no longer exists (deleted since) —
      // keep it selectable/visible so save doesn't silently discard it.
      const staleOption = document.createElement('option');
      staleOption.value = symbol.image_ref;
      staleOption.textContent = `(missing asset ${symbol.image_ref})`;
      artSelect.appendChild(staleOption);
      artSelect.value = symbol.image_ref;
    }
    artSelect.addEventListener('change', () => { setThumb(); markDirty(symbol.id, artSelect); });
    artTd.appendChild(artThumb);
    artTd.appendChild(artSelect);
    tr.appendChild(artTd);

    symbol.reel_weights.forEach((weight, reelIndex) => {
      const td = document.createElement('td');
      const input = document.createElement('input');
      input.type = 'number';
      input.min = '0';
      input.step = '1';
      input.value = weight;
      input.dataset.field = 'weight';
      input.dataset.reelIndex = String(reelIndex);
      input.addEventListener('input', () => markDirty(symbol.id, input));
      td.appendChild(input);
      tr.appendChild(td);
    });

    const capTd = document.createElement('td');
    const capInput = document.createElement('input');
    capInput.type = 'number';
    capInput.min = '0';
    capInput.step = '1';
    capInput.placeholder = 'none';
    if (symbol.max_per_reel !== null && symbol.max_per_reel !== undefined) capInput.value = symbol.max_per_reel;
    capInput.dataset.field = 'maxPerReel';
    capInput.addEventListener('input', () => markDirty(symbol.id, capInput));
    capTd.appendChild(capInput);
    tr.appendChild(capTd);

    for (const count of counts) {
      const td = document.createElement('td');
      const input = document.createElement('input');
      input.type = 'number';
      input.min = '0';
      input.step = 'any';
      input.value = symbol.paytable[String(count)] ?? '';
      input.dataset.field = 'pay';
      input.dataset.count = String(count);
      input.addEventListener('input', () => markDirty(symbol.id, input));
      td.appendChild(input);
      tr.appendChild(td);
    }

    tbody.appendChild(tr);
  }
}

function markDirty(symbolId, input) {
  input.classList.add('is-dirty');
  dirty.add(symbolId);
  const status = document.getElementById('saveStatus');
  status.textContent = 'Unsaved changes';
  status.className = 'save-status';
}

function collectSymbolUpdates() {
  const rows = document.querySelectorAll('#symbolsBody tr');
  const updates = [];
  for (const row of rows) {
    const id = row.dataset.symbolId;
    const weightInputs = [...row.querySelectorAll('input[data-field="weight"]')]
      .sort((a, b) => Number(a.dataset.reelIndex) - Number(b.dataset.reelIndex));
    const reel_weights = weightInputs.map((el) => Number(el.value) || 0);

    const capInput = row.querySelector('input[data-field="maxPerReel"]');
    const max_per_reel = capInput.value === '' ? null : Number(capInput.value);

    const paytable = {};
    for (const el of row.querySelectorAll('input[data-field="pay"]')) {
      if (el.value !== '') paytable[el.dataset.count] = Number(el.value);
    }

    const artSelect = row.querySelector('select[data-field="imageRef"]');
    const image_ref = artSelect.value === '' ? null : artSelect.value;

    updates.push({ id, reel_weights, paytable, max_per_reel, image_ref });
  }
  return updates;
}

async function saveSymbols() {
  if (!draft) return;
  const btn = document.getElementById('saveSymbolsBtn');
  const status = document.getElementById('saveStatus');
  btn.disabled = true;
  status.textContent = 'Saving…';
  status.className = 'save-status';
  try {
    draft = await apiRequest('PUT', `/configs/${draft.id}/symbols`, { symbols: collectSymbolUpdates() });
    dirty.clear();
    document.querySelectorAll('#symbolsBody input.is-dirty').forEach((el) => el.classList.remove('is-dirty'));
    status.textContent = 'Saved';
    status.className = 'save-status is-ok';
  } catch (err) {
    status.textContent = `Save failed: ${err.message}`;
    status.className = 'save-status is-error';
  } finally {
    btn.disabled = false;
  }
}

// ---------- Simulation ----------

async function runSimulation() {
  if (!draft) return;
  const btn = document.getElementById('runSimBtn');
  const status = document.getElementById('simStatus');
  const num_spins = Number(document.getElementById('simSpins').value) || 100000;
  const betRaw = document.getElementById('simBet').value;
  const seedRaw = document.getElementById('simSeed').value;

  btn.disabled = true;
  status.textContent = `Running ${num_spins.toLocaleString()} spins…`;
  status.className = 'sim-status';
  document.getElementById('simReport').hidden = true;
  try {
    const report = await apiRequest('POST', `/configs/${draft.id}/simulate`, {
      num_spins,
      bet_amount: betRaw === '' ? null : Number(betRaw),
      seed: seedRaw === '' ? null : Number(seedRaw),
    });
    status.textContent = `Done — ${report.num_spins.toLocaleString()} spins simulated.`;
    renderSimReport(report);
    await loadHistory(draft.id);
  } catch (err) {
    status.textContent = `Simulation failed: ${err.message}`;
    status.className = 'sim-status is-error';
  } finally {
    btn.disabled = false;
  }
}

function renderSimReport(report) {
  document.getElementById('simReport').hidden = false;
  document.getElementById('statRtp').textContent = fmtPct(report.rtp);
  const targetEl = document.getElementById('statRtpTarget');
  const diff = report.rtp - report.target_rtp;
  targetEl.textContent = `target ${fmtPct(report.target_rtp)} (${diff >= 0 ? '+' : ''}${fmtPct(diff)})`;
  targetEl.className = `stat__sub ${Math.abs(diff) <= 0.02 ? 'is-ok' : 'is-warn'}`;

  document.getElementById('statHit').textContent = fmtPct(report.hit_frequency);
  document.getElementById('statBonus').textContent = fmtPct(report.bonus_frequency);
  document.getElementById('statVol').textContent = `${report.volatility_label} (σ ${report.volatility_stddev.toFixed(2)})`;
  document.getElementById('statMaxWin').textContent = `${report.max_win_multiplier.toFixed(1)}×`;
  // Keys vary per game (base/free_spins for line-pay games, base/free_spins/
  // hold_and_win for others, etc. — see app/simulator/engine.py) rather than
  // a fixed pair, so show whatever mechanics this report actually covers.
  document.getElementById('statRtpMechanic').textContent = Object.entries(report.rtp_by_mechanic)
    .map(([mechanic, rtp]) => `${mechanic}: ${fmtPct(rtp)}`)
    .join(' / ');

  const histEl = document.getElementById('histogram');
  histEl.innerHTML = '';
  const maxCount = Math.max(1, ...report.win_histogram.map((b) => b.count));
  for (const bucket of report.win_histogram) {
    const row = document.createElement('div');
    row.className = 'histogram__row';
    row.innerHTML = `
      <span>${bucket.label}</span>
      <span class="histogram__bar-track"><span class="histogram__bar" style="width:${(bucket.count / maxCount) * 100}%"></span></span>
      <span class="histogram__count">${bucket.count.toLocaleString()}</span>
    `;
    histEl.appendChild(row);
  }
}

async function loadHistory(configId) {
  const runs = await apiRequest('GET', `/configs/${configId}/simulations`);
  const tbody = document.querySelector('#historyTable tbody');
  tbody.innerHTML = '';
  for (const run of runs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${fmtDate(run.created_at)}</td>
      <td>${run.num_spins.toLocaleString()}</td>
      <td>${fmtPct(run.rtp)}</td>
      <td>${fmtPct(run.hit_frequency)}</td>
      <td>${fmtPct(run.bonus_frequency)}</td>
      <td>${run.volatility_label}</td>
    `;
    tbody.appendChild(tr);
  }
}

// ---------- Publish ----------

async function publish() {
  if (!draft) return;
  if (dirty.size > 0 && !confirm('You have unsaved changes that will NOT be published. Continue anyway?')) return;
  if (!confirm(`Publish draft v${draft.version} as the active config? This replaces the live game math immediately.`)) return;

  const btn = document.getElementById('publishBtn');
  btn.disabled = true;
  try {
    await apiRequest('POST', `/configs/${draft.id}/publish`);
    alert(`v${draft.version} is now active.`);
    draft = null;
    document.getElementById('editorPanel').hidden = true;
    document.getElementById('simPanel').hidden = true;
    document.getElementById('publishPanel').hidden = true;
    await loadConfigs();
  } catch (err) {
    alert(`Publish failed: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

// ---------- Init ----------

async function init() {
  document.getElementById('editDraftBtn').addEventListener('click', editDraft);
  document.getElementById('saveSymbolsBtn').addEventListener('click', saveSymbols);
  document.getElementById('runSimBtn').addEventListener('click', runSimulation);
  document.getElementById('publishBtn').addEventListener('click', publish);

  try {
    const { existingDraft } = await loadConfigs();
    if (existingDraft) await editDraft();
  } catch (err) {
    document.getElementById('statusLine').textContent = `Failed to load: ${err.message}`;
  }
}

init();
