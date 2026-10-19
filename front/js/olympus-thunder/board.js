// Olympus Thunder — the 6x5 board: cells, drops, tumble steps, orbs.
//
// Cells are absolutely positioned DOM nodes moved with transforms in DESIGN
// px (the whole #stage is scaled), one node per symbol. Server grids are
// row-major (grid[row][col]); here every cell is addressed as (col,row).
//
// Spine is decoration on top (window.OTSpine: symbol win clips, discharge
// bursts, orb rigs). If it is missing every step still plays with the CSS
// fallbacks in olympus-thunder.css.
(function () {
  const COLS = 6;
  const ROWS = 5;
  // design variants point at their own symbol set: <body data-symbols="img/.../">
  const ART = document.body.dataset.symbols || 'img/olympus-thunder/symbols/';

  // Timings (ms) — mirrored in olympus-thunder.css where CSS animates.
  const T = {
    fall: 430,       // one drop (start -> rest)
    colStagger: 70,  // drop delay between columns
    rowStagger: 34,  // inside a column, bottom rows land first
    win: 760,        // winners pulse before they shatter
    burst: 300,      // shatter
    settle: 120,
  };
  let speed = 1; // 0.5 in turbo

  let gridEl = null;
  let fxEl = null;
  let cell = 126;
  const cells = []; // cells[col][row] = { el, code }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms * speed));

  function readCell() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--cell'));
    if (v) cell = v;
  }

  function orbValue(code) {
    return code && code.startsWith('orb_') ? Number(code.slice(4)) : null;
  }

  function srcFor(code) {
    return ART + (orbValue(code) ? 'orb' : code) + '.webp';
  }

  function place(c, col, row, dy = 0) {
    c.el.style.transform = `translate3d(${col * cell}px, ${row * cell + dy}px, 0)`;
  }

  function makeCell(code) {
    const el = document.createElement('div');
    el.className = 'cell';
    const img = document.createElement('img');
    img.className = 'cell__img';
    img.alt = '';
    img.draggable = false;
    img.src = srcFor(code);
    el.appendChild(img);
    const v = orbValue(code);
    if (v) {
      el.classList.add('is-orb');
      const num = document.createElement('span');
      num.className = 'cell__num' + (v >= 50 ? ' is-huge' : v >= 10 ? ' is-big' : '');
      num.textContent = `x${v}`;
      el.appendChild(num);
    }
    el.dataset.code = code;
    gridEl.appendChild(el);
    return { el, code };
  }

  function removeCell(c) {
    if (window.OTSpine) OTSpine.releaseCell(c.el);
    c.el.remove();
  }

  function setGrid(rows) {
    readCell();
    for (const col of cells) for (const c of col) if (c) removeCell(c);
    cells.length = 0;
    for (let col = 0; col < COLS; col++) {
      cells.push([]);
      for (let row = 0; row < ROWS; row++) {
        const c = makeCell(rows[row][col]);
        place(c, col, row);
        cells[col].push(c);
        mountSpecial(c);
      }
    }
  }

  function mountSpecial(c) {
    if (window.OTSpine && OTSpine.ready && orbValue(c.code)) OTSpine.mountOrb(c.el, orbValue(c.code));
  }

  function animateTo(c, col, row, fromDy, delay, dur) {
    c.el.style.transition = 'none';
    place(c, col, row, fromDy);
    // force the start pose before the transition
    void c.el.offsetWidth;
    c.el.style.transition = `transform ${dur}ms cubic-bezier(.45,.05,.75,.5) ${delay}ms`;
    place(c, col, row);
    return new Promise((resolve) => {
      setTimeout(() => {
        c.el.style.transition = '';
        c.el.classList.remove('is-land');
        void c.el.offsetWidth;
        c.el.classList.add('is-land');
        resolve();
      }, delay + dur);
    });
  }

  // Old board falls out through the floor.
  async function dropOut() {
    readCell();
    const dur = T.fall * speed;
    const jobs = [];
    for (let col = 0; col < cells.length; col++) {
      for (let row = 0; row < ROWS; row++) {
        const c = cells[col][row];
        if (!c) continue;
        const delay = (col * T.colStagger + (ROWS - 1 - row) * T.rowStagger) * speed * 0.6;
        c.el.style.transition = `transform ${dur}ms cubic-bezier(.5,0,.9,.4) ${delay}ms, opacity ${dur}ms linear ${delay}ms`;
        place(c, col, row, (ROWS + 1) * cell);
        jobs.push(wait((delay + dur) / speed).then(() => removeCell(c)));
      }
    }
    await Promise.all(jobs);
    cells.length = 0;
  }

  // New board falls in from above, column by column; `onLand(col,row,code)`
  // fires as each symbol touches down (orb thunder, scatter chime...).
  async function dropIn(rows, onLand) {
    readCell();
    cells.length = 0;
    const dur = T.fall * speed;
    const jobs = [];
    for (let col = 0; col < COLS; col++) {
      cells.push([]);
      for (let row = 0; row < ROWS; row++) {
        const c = makeCell(rows[row][col]);
        cells[col].push(c);
        const delay = (col * T.colStagger + (ROWS - 1 - row) * T.rowStagger) * speed;
        jobs.push(animateTo(c, col, row, -(ROWS + 1) * cell, delay, dur).then(() => {
          mountSpecial(c);
          if (onLand) onLand(col, row, c.code);
        }));
      }
    }
    await Promise.all(jobs);
  }

  function each(fn) {
    for (let col = 0; col < cells.length; col++) for (let row = 0; row < ROWS; row++) if (cells[col][row]) fn(cells[col][row], col, row);
  }

  function clearMarks() {
    if (window.OTSpine && OTSpine.ready) OTSpine.clearWins();
    each((c) => c.el.classList.remove('is-win', 'is-dim', 'is-spine'));
  }

  // Winners pulse (Spine clip if available), everything else dims.
  async function highlight(wins) {
    const hot = new Set();
    for (const w of wins) for (const p of w.positions) hot.add(`${p.col},${p.row}`);
    each((c, col, row) => {
      const on = hot.has(`${col},${row}`);
      c.el.classList.toggle('is-win', on);
      c.el.classList.toggle('is-dim', !on);
      if (on && window.OTSpine && OTSpine.ready && OTSpine.symbolWin(c.el, c.code)) c.el.classList.add('is-spine');
    });
    await wait(T.win);
  }

  // Winners discharge and vanish.
  async function shatter(removed) {
    if (window.Sound) Sound.crackle();
    for (const p of removed) {
      const c = cells[p.col][p.row];
      if (!c) continue;
      c.el.classList.remove('is-win', 'is-spine');
      c.el.classList.add('is-pop');
      if (window.OTSpine && OTSpine.ready) OTSpine.burst(c.el);
    }
    await wait(T.burst);
    for (const p of removed) {
      const c = cells[p.col][p.row];
      if (c) removeCell(c);
      cells[p.col][p.row] = null;
    }
    each((c) => c.el.classList.remove('is-dim'));
  }

  // Gravity: survivors fall to the floor, the gap at the top refills from
  // `gridAfter` (the server's board after this step).
  async function collapse(gridAfter, onLand) {
    const dur = T.fall * speed;
    const jobs = [];
    for (let col = 0; col < COLS; col++) {
      const kept = cells[col].filter(Boolean);
      const missing = ROWS - kept.length;
      const next = [];
      for (let i = 0; i < missing; i++) next.push(makeCell(gridAfter[i][col]));
      const column = next.concat(kept);
      for (let row = ROWS - 1; row >= 0; row--) {
        const c = column[row];
        const wasRow = row < missing ? row - missing : cells[col].indexOf(c);
        if (wasRow === row) continue;
        const delay = (col * T.colStagger * 0.5 + (ROWS - 1 - row) * T.rowStagger) * speed;
        const fresh = row < missing;
        jobs.push(animateTo(c, col, row, (wasRow - row) * cell, delay, dur).then(() => {
          if (fresh) {
            mountSpecial(c);
            if (onLand) onLand(col, row, c.code);
          }
        }));
      }
      cells[col] = column;
    }
    await Promise.all(jobs);
    await wait(T.settle);
  }

  function orbs() {
    const out = [];
    each((c, col, row) => {
      const v = orbValue(c.code);
      if (v) out.push({ col, row, value: v, el: c.el });
    });
    return out;
  }

  function cellsOf(code) {
    const out = [];
    each((c, col, row) => { if (c.code === code) out.push({ col, row, el: c.el }); });
    return out;
  }

  function fadeOrbs() {
    for (const o of orbs()) {
      if (!(window.OTSpine && OTSpine.fadeOrb(o.el))) o.el.classList.add('is-orb-fade');
    }
  }

  // Centre of a cell in viewport px (for flying numbers).
  function cellCenter(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  function combo(text) {
    const el = document.createElement('div');
    el.className = 'combo';
    el.textContent = text;
    fxEl.appendChild(el);
    void el.offsetWidth;
    el.classList.add('is-on');
    setTimeout(() => el.remove(), 1300);
  }

  function init(grid, fx) {
    gridEl = grid;
    fxEl = fx;
    readCell();
  }

  function relayout(rows) {
    readCell();
    each((c, col, row) => place(c, col, row));
  }

  window.Board = {
    init, setGrid, dropOut, dropIn, highlight, shatter, collapse, clearMarks,
    orbs, cellsOf, fadeOrbs, cellCenter, combo, relayout,
    setSpeed(s) { speed = s; },
    get speed() { return speed; },
    wait,
    orbValue,
    srcFor,
    COLS, ROWS,
  };
})();
