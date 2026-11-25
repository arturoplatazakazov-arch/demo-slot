// DevTools — shared dev panel for every slot: a DEV button (screens, symbol
// combinations, scenarios, popups, features) and a ♪ button (the sound lab of
// js/sound-kit.js). Shown only where SLOT_CONFIG.showDevPanels is on
// (localhost, or ?dev=1 — js/config.js), never on a plain deployed page.
//
// A game mounts it with an adapter that only lists what it has:
//
//   DevTools.mount({
//     tabs: [
//       { title: 'Экраны', sections: [
//         { title: 'Режим', items: [{ label: 'База', run: () => … }] },
//       ] },
//       { title: 'Комбинации', sections: [
//         { title: 'Линия', matrix: { rows: [{ label, img, key }], cols: [3, 4, 5], run: (row, n) => … } },
//       ] },
//     ],
//     fields: [{ key: 'amount', label: 'Сумма попапа', value: 1234500 }],
//   });
//
// `run` may return a promise; DevTools.value('amount') reads a field.
(function () {
  const LS = 'devtools.ui';
  const ui = (() => { try { return JSON.parse(localStorage.getItem(LS) || '{}'); } catch (e) { return {}; } })();
  const saveUi = () => { try { localStorage.setItem(LS, JSON.stringify(ui)); } catch (e) { /* noop */ } };

  const fieldValues = {};
  let statusEl = null;

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'style') el.style.cssText = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    }
    return el;
  }

  function enabled() {
    const cfg = window.SLOT_CONFIG;
    if (cfg && cfg.showDevPanels != null) return !!cfg.showDevPanels;
    return ['localhost', '127.0.0.1', ''].includes(location.hostname);
  }

  function setStatus(text, kind) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.dataset.kind = kind || '';
  }

  async function runItem(label, fn) {
    setStatus(`▶ ${label}`, 'run');
    try {
      await fn();
      setStatus(`✓ ${label}`, 'ok');
    } catch (err) {
      console.error('dev:', label, err);
      setStatus(`✗ ${label}: ${err && err.message ? err.message : err}`, 'err');
    }
  }

  // --- shell: two round buttons + one sheet ---------------------------------
  let root, sheet, body, tabsBar;
  function shell() {
    if (root) return;
    root = h('div', { class: 'dt-root' });
    const fabs = h('div', { class: 'dt-fabs' },
      h('button', { class: 'dt-fab', type: 'button', 'data-panel': 'dev', onclick: () => toggle('dev') }, 'DEV'),
      h('button', { class: 'dt-fab', type: 'button', 'data-panel': 'sound', onclick: () => toggle('sound') }, '♪'),
    );
    sheet = h('div', { class: 'dt-sheet', hidden: true });
    root.append(fabs, sheet);
    // Panel clicks must not reach the game underneath (feature screen closes on any click).
    // (pointerdown still bubbles: SoundKit unlocks audio on the first one.)
    sheet.addEventListener('click', (e) => e.stopPropagation());
    document.body.appendChild(root);
  }

  const panels = {};
  function toggle(name) {
    const open = ui.open === name && !sheet.hidden;
    ui.open = open ? null : name;
    saveUi();
    render();
  }
  function render() {
    root.querySelectorAll('.dt-fab').forEach((b) => b.classList.toggle('is-on', b.dataset.panel === ui.open));
    if (!ui.open || !panels[ui.open]) { sheet.hidden = true; return; }
    sheet.hidden = false;
    sheet.innerHTML = '';
    sheet.dataset.panel = ui.open;
    panels[ui.open](sheet);
  }

  // --- DEV panel ------------------------------------------------------------
  function devPanel(adapter) {
    return (host) => {
      const tabs = adapter.tabs || [];
      if (ui.devTab == null || ui.devTab >= tabs.length) ui.devTab = 0;
      tabsBar = h('div', { class: 'dt-tabs' }, tabs.map((t, i) => h('button', {
        type: 'button', class: `dt-tab${i === ui.devTab ? ' is-on' : ''}`,
        onclick: () => { ui.devTab = i; saveUi(); render(); },
      }, t.title)));
      statusEl = h('div', { class: 'dt-status' }, 'готово');
      body = h('div', { class: 'dt-body' });
      const fields = (adapter.fields || []).map((f) => {
        if (fieldValues[f.key] == null) fieldValues[f.key] = f.value;
        return h('label', { class: 'dt-field' }, f.label,
          h('input', {
            type: f.type || 'number', value: fieldValues[f.key],
            oninput: (e) => { fieldValues[f.key] = f.type === 'text' ? e.target.value : Number(e.target.value); },
          }));
      });
      host.append(
        h('div', { class: 'dt-head' }, h('b', {}, adapter.title || 'DEV'), h('button', { class: 'dt-x', type: 'button', onclick: () => toggle('dev') }, '×')),
        tabsBar,
        fields.length ? h('div', { class: 'dt-fields' }, fields) : null,
        statusEl,
        body,
      );
      const tab = tabs[ui.devTab];
      if (!tab) return;
      for (const sec of tab.sections || []) body.appendChild(renderSection(sec));
    };
  }

  function renderSection(sec) {
    const box = h('section', { class: 'dt-sec' }, sec.title ? h('h4', {}, sec.title) : null);
    if (sec.note) box.appendChild(h('p', { class: 'dt-note' }, sec.note));
    if (sec.items) {
      box.appendChild(h('div', { class: 'dt-btns' }, sec.items.map((it) => h('button', {
        type: 'button', class: 'dt-btn', title: it.hint || '',
        onclick: () => runItem(it.label, it.run),
      }, it.label))));
    }
    if (sec.matrix) {
      const m = sec.matrix;
      const colName = m.colLabel || ((c) => `×${c}`);   // подпись столбца (по умолчанию ×N)
      const table = h('table', { class: 'dt-matrix' },
        h('tr', {}, h('th', {}, ''), m.cols.map((c) => h('th', {}, colName(c)))),
        m.rows.map((r) => h('tr', {},
          h('td', { class: 'dt-sym' }, r.img ? h('img', { src: r.img, alt: '' }) : null, h('span', {}, r.label)),
          m.cols.map((c) => h('td', {}, h('button', {
            type: 'button', class: 'dt-btn dt-btn--cell',
            onclick: () => runItem(`${r.label} · ${colName(c)}`, () => m.run(r, c)),
          }, '▶'))),
        )),
      );
      box.appendChild(table);
    }
    return box;
  }

  // --- ♪ sound panel --------------------------------------------------------
  let library = null;
  function loadLibrary() {
    if (library) return Promise.resolve(library);
    return fetch('sound/library.json').then((r) => r.json()).then((l) => (library = l)).catch(() => (library = []));
  }
  const short = (p) => (p ? p.replace(/^sound\//, '') : '—');
  const pct = (v) => `${Math.round(v * 100)}%`;
  const logEntries = [];
  let logStart = null;
  let rowsByKey = {};
  let logEl = null;

  function soundPanel(host) {
    const lab = window.Sound && window.Sound.lab;
    if (!lab) { host.appendChild(h('p', { class: 'dt-note' }, 'У этой игры нет SoundKit (js/sound-kit.js).')); return; }
    rowsByKey = {};
    const filter = ui.soundFilter || 'all';
    const masterRow = (kind, label) => {
      const val = h('span', { class: 'dt-val' }, pct(lab.master(kind)));
      return h('label', { class: 'dt-master' }, label,
        h('input', { type: 'range', min: 0, max: 1.5, step: 0.01, value: lab.master(kind),
          oninput: (e) => { lab.setMaster(kind, Number(e.target.value)); val.textContent = pct(Number(e.target.value)); } }),
        val);
    };
    const filterBtn = (key, label) => h('button', {
      type: 'button', class: `dt-chip${filter === key ? ' is-on' : ''}`,
      onclick: () => { ui.soundFilter = key; saveUi(); render(); },
    }, label);

    host.append(
      h('div', { class: 'dt-head' }, h('b', {}, `Звук · ${lab.game}`), h('button', { class: 'dt-x', type: 'button', onclick: () => toggle('sound') }, '×')),
      h('div', { class: 'dt-masters' },
        window.Sound.isMuted() ? h('div', { class: 'dt-muted-banner' }, 'Звук игры выключен кнопкой в баре',
          h('button', { type: 'button', class: 'dt-btn', onclick: () => { window.Sound.setMuted(false); render(); } }, 'Включить')) : null,
        masterRow('music', 'Музыка'),
        masterRow('sfx', 'Эффекты'),
        h('div', { class: 'dt-btns' },
          h('button', { type: 'button', class: 'dt-btn', onclick: () => lab.stopAll() }, '■ Стоп всё'),
          h('button', { type: 'button', class: 'dt-btn', onclick: () => exportDialog(lab) }, 'Экспорт'),
          h('button', { type: 'button', class: 'dt-btn dt-btn--warn', onclick: () => { if (confirm('Сбросить все настройки звука этой игры?')) { lab.reset(); render(); } } }, 'Сброс'),
        ),
        h('div', { class: 'dt-btns' },
          filterBtn('all', 'все'), filterBtn('on', 'со звуком'), filterBtn('off', 'без звука'), filterBtn('fired', 'сработавшие'),
          h('button', { type: 'button', class: `dt-chip${ui.soundLog ? ' is-on' : ''}`, onclick: () => { ui.soundLog = !ui.soundLog; saveUi(); render(); } }, 'лог'),
        ),
      ),
    );
    const sets = lab.sets();
    if (sets.length) {
      host.appendChild(h('div', { class: 'dt-sets' }, sets.map((st, si) => {
        const cur = lab.setVariantIndex(si);
        // st.count: how many set variants there are (else the longest list)
        const count = st.count || Math.max(...st.keys.map((k) => lab.event(k).variants.length), 0);
        return h('div', { class: 'dt-set' },
          h('div', { class: 'dt-set__title' }, st.title, h('small', {}, cur >= 0 ? ` · сейчас ${String.fromCharCode(65 + cur)}` : ' · смешано')),
          st.note ? h('div', { class: 'dt-note' }, st.note) : null,
          h('div', { class: 'dt-btns' }, Array.from({ length: count }, (_, vi) => h('button', {
            type: 'button', class: `dt-chip${vi === cur ? ' is-on' : ''}`, title: (st.names && st.names[vi]) || '',
            onclick: () => {
              lab.applySet(si, vi);
              // keep the music audible: start the mode's track if nothing plays
              const pk = typeof st.preview === 'function' ? st.preview() : st.preview;
              if (pk && lab.currentMusic() !== pk) lab.preview(pk);
              render();
            },
          }, `${String.fromCharCode(65 + vi)}${st.names && st.names[vi] ? ` · ${st.names[vi]}` : ''}`))),
        );
      })));
    }
    if (ui.soundLog) {
      logEl = h('div', { class: 'dt-log' });
      host.appendChild(logEl);
      paintLog();
    } else logEl = null;

    const list = h('div', { class: 'dt-body' });
    host.appendChild(list);
    ui.soundOpenGroups = ui.soundOpenGroups || {};
    for (const g of lab.groups()) {
      const keys = g.keys.filter((k) => {
        const e = lab.event(k);
        if (filter === 'on') return !e.off;
        if (filter === 'off') return e.off;
        if (filter === 'fired') return e.fired > 0;
        return true;
      });
      if (!keys.length) continue;
      const open = ui.soundOpenGroups[g.name] !== false;
      const sec = h('section', { class: `dt-sec dt-sgroup${open ? '' : ' is-closed'}` },
        h('h4', { onclick: () => { ui.soundOpenGroups[g.name] = !open; saveUi(); render(); } }, `${open ? '▾' : '▸'} ${g.name} `, h('small', {}, String(keys.length))));
      if (open) for (const k of keys) sec.appendChild(soundRow(lab, k));
      list.appendChild(sec);
    }
  }

  function soundRow(lab, key) {
    const e = lab.event(key);
    const status = e.off ? (e.variants.length ? 'выкл' : 'нет звука') : 'есть';
    const sel = h('select', {
      class: 'dt-sel',
      onchange: (ev) => { const v = ev.target.value; lab.setVariant(key, v === '' ? null : v); refreshRow(lab, key); if (v) lab.preview(key); },
    },
    h('option', { value: '' }, '— без звука —'),
    e.variants.map((p, i) => h('option', { value: p, selected: p === e.active }, `${String.fromCharCode(65 + i)} · ${lab.variantName(p) || short(p)}`)));
    const step = (d) => {
      const opts = ['', ...e.variants];
      const cur = opts.indexOf(lab.event(key).active || '');
      const next = opts[(cur + d + opts.length) % opts.length];
      lab.setVariant(key, next === '' ? null : next);
      refreshRow(lab, key);
      if (next) lab.preview(key);
    };
    const val = h('span', { class: 'dt-val' }, pct(e.volume));
    const row = h('div', { class: `dt-srow${e.off ? ' is-off' : ''}${e.muted ? ' is-muted' : ''}`, 'data-key': key },
      h('div', { class: 'dt-srow__top' },
        h('button', { type: 'button', class: 'dt-play', title: 'прослушать', onclick: () => lab.preview(key) }, e.kind === 'music' ? '♫' : '▶'),
        h('span', { class: 'dt-srow__name' }, e.label, e.loop ? h('i', {}, ' петля') : null, h('small', {}, key)),
        h('span', { class: `dt-badge dt-badge--${e.off ? (e.variants.length ? 'off' : 'none') : 'on'}` }, status),
        h('span', { class: 'dt-fired', title: 'сколько раз сработало' }, e.fired ? `×${e.fired}` : ''),
      ),
      h('div', { class: 'dt-srow__ctl' },
        h('button', { type: 'button', class: 'dt-mini', title: 'предыдущий вариант', onclick: () => step(-1) }, '‹'),
        sel,
        h('button', { type: 'button', class: 'dt-mini', title: 'следующий вариант', onclick: () => step(1) }, '›'),
      ),
      h('div', { class: 'dt-srow__ctl' },
        h('input', { type: 'range', min: 0, max: 2, step: 0.01, value: e.volume, title: 'громкость события',
          oninput: (ev) => { lab.setVolume(key, Number(ev.target.value)); val.textContent = pct(Number(ev.target.value)); } }),
        val,
        h('button', { type: 'button', class: `dt-mini${e.muted ? ' is-on' : ''}`, title: 'заглушить событие', onclick: () => { lab.setMute(key, !lab.event(key).muted); refreshRow(lab, key); } }, 'M'),
        h('button', { type: 'button', class: 'dt-mini', title: 'добавить файл из библиотеки', onclick: () => libraryPicker(lab, key, row) }, '+'),
        // Только для движков, умеющих загрузку (SoundKit); у игр со своим
        // sound.js её может не быть — тогда кнопки просто нет.
        lab.addUpload ? h('button', { type: 'button', class: 'dt-mini', title: 'загрузить свой файл (только на эту сессию)', onclick: () => pickUpload(lab, key) }, '⤒') : null,
      ),
      e.note ? h('div', { class: 'dt-note' }, e.note) : null,
      uploadList(lab, key),
    );
    // Drag a file straight onto the event — same as the ⤒ button.
    row.addEventListener('dragover', (ev) => { ev.preventDefault(); row.classList.add('is-drop'); });
    row.addEventListener('dragleave', () => row.classList.remove('is-drop'));
    row.addEventListener('drop', (ev) => {
      ev.preventDefault();
      row.classList.remove('is-drop');
      addUploads(lab, key, ev.dataTransfer && ev.dataTransfer.files);
    });
    rowsByKey[key] = row;
    return row;
  }

  function refreshRow(lab, key) {
    const old = rowsByKey[key];
    if (!old || !old.isConnected) return;
    old.replaceWith(soundRow(lab, key));
  }

  // --- the sound designer's own files (session only) --------------------------
  // Files dropped here never leave the browser and are gone on reload — the
  // point is auditioning a take on the real slot, not storing it.
  function pickUpload(lab, key) {
    const input = h('input', { type: 'file', accept: 'audio/*', multiple: true, style: 'display:none' });
    input.addEventListener('change', () => { addUploads(lab, key, input.files); input.remove(); });
    document.body.appendChild(input);
    input.click();
  }

  function addUploads(lab, key, files) {
    if (!lab.addUpload || !files || !files.length) return;
    const audio = [...files].filter((f) => f.type.startsWith('audio/') || /\.(wav|mp3|ogg|m4a|aac|flac|opus|webm)$/i.test(f.name));
    if (!audio.length) { setStatus('это не аудиофайл', 'err'); return; }
    Promise.all(audio.map((f) => lab.addUpload(key, f))).then(() => {
      refreshRow(lab, key);
      lab.preview(key); // слышно сразу
      setStatus(audio.length === 1 ? `загружен ${audio[0].name}` : `загружено файлов: ${audio.length}`, 'ok');
    });
  }

  function uploadList(lab, key) {
    const mine = lab.uploads ? lab.uploads(key) : [];
    if (!mine.length) return null;
    const active = lab.event(key).active;
    return h('div', { class: 'dt-ups' },
      mine.map((u) => h('div', { class: `dt-ups__item${u.path === active ? ' is-on' : ''}` },
        h('button', { type: 'button', class: 'dt-mini', title: 'послушать', onclick: () => { lab.setVariant(key, u.path); refreshRow(lab, key); lab.preview(key); } }, '▶'),
        h('span', { class: 'dt-ups__name', title: u.name }, u.name),
        h('button', { type: 'button', class: 'dt-mini', title: 'убрать файл', onclick: () => { lab.removeVariant(key, u.path); refreshRow(lab, key); } }, '×'),
      )),
    );
  }

  function libraryPicker(lab, key, row) {
    if (row.querySelector('.dt-lib')) { row.querySelector('.dt-lib').remove(); return; }
    const box = h('div', { class: 'dt-lib' });
    const input = h('input', { type: 'search', placeholder: 'поиск по файлам: win, reel, coin…' });
    const out = h('div', { class: 'dt-lib__list' });
    box.append(input, out);
    row.appendChild(box);
    loadLibrary().then((lib) => {
      const paint = () => {
        const q = input.value.trim().toLowerCase();
        out.innerHTML = '';
        lib.filter((p) => (!lab.libraryPrefix || p.startsWith(lab.libraryPrefix)) && (!q || p.toLowerCase().includes(q))).slice(0, 80).forEach((p) => {
          out.appendChild(h('div', { class: 'dt-lib__item' },
            h('button', { type: 'button', class: 'dt-mini', title: 'послушать', onclick: () => auditionFile(p) }, '▶'),
            h('button', { type: 'button', class: 'dt-lib__add', onclick: () => { lab.addVariant(key, p); refreshRow(lab, key); lab.preview(key); } }, short(p)),
          ));
        });
      };
      input.addEventListener('input', paint);
      paint();
      input.focus();
    });
  }

  let auditionEl = null;
  function auditionFile(path) {
    if (auditionEl) auditionEl.pause();
    auditionEl = new Audio(path);
    auditionEl.volume = 0.7;
    auditionEl.play().catch(() => {});
    setTimeout(() => auditionEl && auditionEl.pause(), 6000);
  }

  function exportDialog(lab) {
    const json = JSON.stringify(lab.exportState(), null, 2);
    if (navigator.clipboard) navigator.clipboard.writeText(json).catch(() => {});
    const box = h('div', { class: 'dt-export' },
      h('p', {}, 'Скопировано в буфер. Отправь это в чат — закреплю выбор в sound.js.'),
      h('textarea', { readonly: true, rows: 12 }, json),
      h('button', { type: 'button', class: 'dt-btn', onclick: () => box.remove() }, 'Закрыть'),
    );
    sheet.prepend(box);
    box.querySelector('textarea').select();
  }

  function onSoundEvent(info) {
    if (logStart == null) logStart = info.t;
    logEntries.push(info);
    if (logEntries.length > 120) logEntries.shift();
    if (sheet && !sheet.hidden && sheet.dataset.panel === 'sound') {
      const row = rowsByKey[info.key];
      if (row) {
        const f = row.querySelector('.dt-fired');
        if (f) f.textContent = `×${info.count}`;
        row.classList.remove('is-flash');
        void row.offsetWidth;
        row.classList.add('is-flash');
      }
      paintLog();
    }
  }
  function paintLog() {
    if (!logEl) return;
    const lab = window.Sound && window.Sound.lab;
    logEl.innerHTML = '';
    if (!logEntries.length) { logEl.appendChild(h('div', { class: 'dt-note' }, 'Пока ничего не звучало — покрути слот или запусти сценарий во вкладке DEV.')); return; }
    logEl.appendChild(h('div', { class: 'dt-btns' },
      h('button', { type: 'button', class: 'dt-mini', onclick: () => { logEntries.length = 0; logStart = null; paintLog(); } }, 'очистить')));
    for (const e of logEntries.slice().reverse()) {
      const ev = lab && lab.event(e.key);
      const flag = !e.known ? 'нет в каталоге' : e.missing ? 'без звука' : e.mutedBy === 'game' ? 'звук игры выкл' : e.muted ? 'заглушено (M)' : '';
      logEl.appendChild(h('div', { class: `dt-logrow${flag ? ' is-silent' : ''}${!e.known ? ' is-unknown' : ''}` },
        h('span', { class: 'dt-logrow__t' }, `${((e.t - logStart) / 1000).toFixed(2)}s`),
        h('span', { class: 'dt-logrow__k' }, ev ? ev.label : e.key),
        h('span', { class: 'dt-logrow__f' }, flag || (lab && lab.variantName(e.path) ? `${lab.variantName(e.path)} · ${short(e.path).split('/').pop()}` : short(e.path))),
      ));
    }
  }

  // --- public ---------------------------------------------------------------
  function mount(adapter) {
    if (!enabled()) return;
    const start = () => {
      shell();
      panels.dev = devPanel(adapter || {});
      panels.sound = soundPanel;
      if (window.Sound && window.Sound.lab) window.Sound.lab.onEvent(onSoundEvent);
      render();
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }

  window.DevTools = {
    mount,
    value: (key) => fieldValues[key],
    status: setStatus,
    refresh: () => root && render(),
  };
})();
