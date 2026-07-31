// Stage 3 of the slot builder wizard: grid size + which mechanics are
// present. Mechanic ids match app/features/registry.py's feature_id values
// (plus the two base win types, line_pay/scatter) so this list can later
// become FeatureConfig rows without renaming anything.
// apiRequest/setStatus/API_BASE come from common.js.

const params = new URLSearchParams(window.location.search);
const SLUG = params.get('slug');

// Avalanche (app/engine/avalanche.py) replaces line-pay's whole win model —
// count-anywhere tiered payouts instead of paylines — and has no
// avalanche-aware expanding-wild/hold-and-win implementation, so these three
// are mutually exclusive with it rather than just additional options.
const INCOMPATIBLE_WITH_AVALANCHE = ['mechanicLinePay', 'mechanicHoldAndWin', 'mechanicExpandingWild'];

function applyAvalancheExclusivity() {
  const avalancheChecked = document.getElementById('mechanicAvalanche').checked;
  for (const id of INCOMPATIBLE_WITH_AVALANCHE) {
    const checkbox = document.getElementById(id);
    checkbox.disabled = avalancheChecked;
    if (avalancheChecked) checkbox.checked = false;
  }
}

function renderConfigLink(manifest) {
  const el = document.getElementById('configLink');
  if (!manifest.game_config_id) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.innerHTML = `Конфиг сгенерирован (id ${manifest.game_config_id}). ` +
    `<a href="../admin/index.html?game=${encodeURIComponent(SLUG)}">Открыть в редакторе конфига →</a>`;
}

async function loadGame() {
  const manifest = await apiRequest('GET', `/games/${SLUG}`);
  document.getElementById('slotName').textContent = `— ${manifest.meta.display_name} (${manifest.meta.slug})`;
  document.title = `Конструктор слота — ${manifest.meta.display_name} — Этап 3`;

  // Only overwrite the checkbox defaults (line_pay/scatter pre-checked in
  // the HTML) once the grid has actually been saved before — otherwise a
  // brand-new game's empty mechanics:[] would wipe those sensible defaults.
  if (manifest.grid) {
    document.querySelector('[name=reels]').value = manifest.grid.reels;
    document.querySelector('[name=rows]').value = manifest.grid.rows;
    const selected = new Set(manifest.mechanics || []);
    for (const checkbox of document.querySelectorAll('[name=mechanics]')) {
      checkbox.checked = selected.has(checkbox.value);
    }
  }
  applyAvalancheExclusivity();
  renderConfigLink(manifest);
  return manifest;
}

if (!SLUG) {
  document.querySelector('main').innerHTML = '<section class="panel"><p class="hint">Не указан слаг слота (нет ?slug=... в адресе). Вернись к <a href="new.html">списку слотов</a>.</p></section>';
} else {
  document.getElementById('mechanicAvalanche').addEventListener('change', applyAvalancheExclusivity);

  document.getElementById('gridForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const mechanics = [...form.querySelectorAll('[name=mechanics]:checked')].map((cb) => cb.value);
    const body = {
      reels: Number(form.reels.value),
      rows: Number(form.rows.value),
      mechanics,
    };
    setStatus('gridStatus', 'Сохраняю…');
    try {
      await apiRequest('POST', `/games/${SLUG}/grid`, body);
      setStatus('gridStatus', 'Сохранено.', 'is-ok');
    } catch (err) {
      setStatus('gridStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('toLayoutBtn').addEventListener('click', () => {
    window.location.href = `layout.html?slug=${encodeURIComponent(SLUG)}`;
  });

  document.getElementById('generateConfigBtn').addEventListener('click', async () => {
    setStatus('configStatus', 'Генерирую…');
    try {
      const result = await apiRequest('POST', `/games/${SLUG}/generate-config`);
      setStatus('configStatus', `Готово: ${result.num_symbols} символов, ${result.num_paylines} линий, ${result.num_features} фич.`, 'is-ok');
      const manifest = await apiRequest('GET', `/games/${SLUG}`);
      renderConfigLink(manifest);
    } catch (err) {
      setStatus('configStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  loadGame().catch((err) => {
    document.querySelector('main').innerHTML = `<section class="panel"><p class="hint">Не удалось загрузить слот "${SLUG}": ${err.message}</p></section>`;
  });
}
