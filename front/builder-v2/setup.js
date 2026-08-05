// Constructor v2 — Page 1 (Setup) logic.
(function () {
  const draft = Draft.load();

  const nameEl = document.getElementById('gameName');
  const gapEl = document.getElementById('gapInput');
  const baseGrid = document.getElementById('baseGrid');
  const mechArea = document.getElementById('mechArea');
  const nextBtn = document.getElementById('nextBtn');
  const footInfo = document.getElementById('footInfo');

  // Restore prior draft values.
  nameEl.value = draft.name || '';
  gapEl.value = draft.gap ?? 10;

  function persist() {
    draft.name = nameEl.value.trim();
    draft.slug = Draft.slugify(draft.name);
    draft.gap = Number(gapEl.value) || 0;
    Draft.save(draft);
    updateFooter();
  }

  function updateFooter() {
    const ok = draft.name && draft.base;
    nextBtn.disabled = !ok;
    footInfo.textContent = draft.base
      ? `${draft.name || 'без названия'} · ${BASES[draft.base].label} · механик: ${draft.mechanics.length}`
      : 'Выбери название и базу';
  }

  // --- Base picker ---
  function renderBases() {
    baseGrid.innerHTML = '';
    for (const [id, base] of Object.entries(BASES)) {
      const btn = document.createElement('button');
      btn.className = 'pick' + (draft.base === id ? ' is-on' : '');
      btn.type = 'button';
      const dots = document.createElement('span');
      dots.className = 'pick__grid';
      dots.style.gridTemplateColumns = `repeat(${base.reels}, 7px)`;
      for (let i = 0; i < base.reels * base.rows; i++) dots.appendChild(document.createElement('i'));
      const title = document.createElement('div');
      title.className = 'pick__title';
      title.append(`${base.label}`, dots);
      const hint = document.createElement('div');
      hint.className = 'pick__hint';
      hint.textContent = base.hint;
      btn.append(title, hint);
      btn.addEventListener('click', () => selectBase(id));
      baseGrid.appendChild(btn);
    }
  }

  function selectBase(id) {
    if (draft.base !== id) {
      draft.base = id;
      // Drop mechanics not valid on the new base.
      const allowed = new Set(BASES[id].mechanics);
      draft.mechanics = draft.mechanics.filter((m) => allowed.has(m));
    }
    Draft.save(draft);
    renderBases();
    renderMechanics();
    updateFooter();
  }

  // --- Mechanics ---
  function isBlocked(mId) {
    const def = MECHANICS[mId];
    // conflict with an already-selected mechanic
    if (def.conflicts && def.conflicts.some((c) => draft.mechanics.includes(c))) return 'conflict';
    return null;
  }

  function toggleMechanic(mId) {
    const on = draft.mechanics.includes(mId);
    if (on) {
      draft.mechanics = draft.mechanics.filter((m) => m !== mId);
      // Drop anything that required this one.
      let changed = true;
      while (changed) {
        changed = false;
        for (const m of [...draft.mechanics]) {
          const req = MECHANICS[m].requires || [];
          if (req.some((r) => !draft.mechanics.includes(r))) {
            draft.mechanics = draft.mechanics.filter((x) => x !== m);
            changed = true;
          }
        }
      }
    } else {
      if (isBlocked(mId)) return;
      draft.mechanics.push(mId);
      // Auto-add requirements.
      for (const r of MECHANICS[mId].requires || []) {
        if (!draft.mechanics.includes(r) && !isBlocked(r)) draft.mechanics.push(r);
      }
    }
    Draft.save(draft);
    renderMechanics();
    updateFooter();
  }

  function renderMechanics() {
    if (!draft.base) {
      mechArea.innerHTML = '<div class="empty-note">Сначала выбери размер барабана.</div>';
      return;
    }
    const grid = document.createElement('div');
    grid.className = 'mech-grid';
    for (const mId of BASES[draft.base].mechanics) {
      const def = MECHANICS[mId];
      const on = draft.mechanics.includes(mId);
      const blocked = !on && isBlocked(mId);
      const el = document.createElement('div');
      el.className = 'mech' + (on ? ' is-on' : '') + (blocked ? ' is-disabled' : '');
      const check = document.createElement('div');
      check.className = 'mech__check';
      check.textContent = '✓';
      const body = document.createElement('div');
      body.className = 'mech__body';
      const title = document.createElement('div');
      title.className = 'mech__title';
      title.textContent = def.label;
      const hint = document.createElement('div');
      hint.className = 'mech__hint';
      hint.textContent = def.hint || '';
      body.append(title, hint);
      const notes = [];
      if (def.requires) notes.push('нужно: ' + def.requires.map((r) => MECHANICS[r].label).join(', '));
      if (blocked === 'conflict') notes.push('конфликт с уже выбранной');
      if (notes.length) {
        const req = document.createElement('div');
        req.className = 'mech__req';
        req.textContent = notes.join(' · ');
        body.append(req);
      }
      el.append(check, body);
      el.addEventListener('click', () => toggleMechanic(mId));
      grid.appendChild(el);
    }
    mechArea.innerHTML = '';
    mechArea.appendChild(grid);
  }

  // --- Wire up ---
  nameEl.addEventListener('input', persist);
  gapEl.addEventListener('input', persist);
  document.getElementById('nextBtn').addEventListener('click', () => {
    if (!draft.name || !draft.base) return;
    persist();
    location.href = 'assets.html';
  });
  document.getElementById('resetBtn').addEventListener('click', () => {
    if (!confirm('Сбросить черновик?')) return;
    Draft.reset();
    location.reload();
  });

  renderBases();
  renderMechanics();
  updateFooter();
})();
