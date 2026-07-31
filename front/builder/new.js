// Stage 1 of the slot builder wizard: name a new slot, which creates its
// Game row, front/ asset folders, and build-spec manifest (see
// app/api/admin/builder.py). apiRequest/setStatus/API_BASE come from common.js.

const STAGE_LABELS = {
  1: 'Этап 1 — название',
  2: 'Этап 2 — материалы',
  3: 'Этап 3 — сетка и механики',
  4: 'Этап 4 — вёрстка',
  5: 'Этап 5 — тест',
};

const STAGE_PAGES = { 1: 'assets.html', 2: 'grid.html', 3: 'layout.html', 4: 'preview.html', 5: 'preview.html' };

function nextStageHref(draft) {
  const nextStage = Math.min(draft.stage_completed + 1, 5);
  return `${STAGE_PAGES[nextStage]}?slug=${encodeURIComponent(draft.slug)}`;
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString();
}

async function loadDrafts() {
  const drafts = await apiRequest('GET', '/games');
  const tbody = document.querySelector('#draftsTable tbody');
  tbody.innerHTML = '';
  document.getElementById('draftsEmpty').hidden = drafts.length > 0;

  for (const draft of drafts) {
    const tr = document.createElement('tr');
    const nameCell = document.createElement('td');
    nameCell.textContent = draft.name;
    const codeCell = document.createElement('td');
    codeCell.innerHTML = `<code></code>`;
    codeCell.querySelector('code').textContent = draft.slug;
    const stageCell = document.createElement('td');
    stageCell.textContent = STAGE_LABELS[draft.stage_completed] || `Этап ${draft.stage_completed}`;
    const updatedCell = document.createElement('td');
    updatedCell.textContent = fmtDate(draft.updated_at);
    const actionCell = document.createElement('td');
    actionCell.innerHTML = `<a class="btn" href="${nextStageHref(draft)}">Продолжить →</a>`;
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn--danger';
    deleteBtn.type = 'button';
    deleteBtn.textContent = 'Удалить';
    deleteBtn.addEventListener('click', () => deleteDraft(draft));
    actionCell.appendChild(deleteBtn);

    tr.append(nameCell, codeCell, stageCell, updatedCell, actionCell);
    tbody.appendChild(tr);
  }
}

async function deleteDraft(draft) {
  if (!confirm(`Удалить слот "${draft.name}" (${draft.slug})? Это действие нельзя отменить.`)) return;
  setStatus('formStatus', 'Удаляю…');
  try {
    await apiRequest('DELETE', `/games/${encodeURIComponent(draft.slug)}`);
    setStatus('formStatus', `Слот "${draft.name}" удалён.`, 'is-ok');
    await loadDrafts();
  } catch (err) {
    setStatus('formStatus', `Ошибка: ${err.message}`, 'is-error');
  }
}

document.getElementById('createForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = document.getElementById('nameInput');
  const name = input.value.trim();
  if (!name) return;

  setStatus('formStatus', 'Создаю…');
  try {
    const game = await apiRequest('POST', '/games', { name });
    setStatus('formStatus', `Готово: код слота "${game.slug}". Переход к материалам…`, 'is-ok');
    window.location.href = `assets.html?slug=${encodeURIComponent(game.slug)}`;
  } catch (err) {
    setStatus('formStatus', `Ошибка: ${err.message}`, 'is-error');
  }
});

loadDrafts().catch((err) => {
  setStatus('formStatus', `Не удалось загрузить список слотов: ${err.message}`, 'is-error');
});
