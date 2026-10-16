// Shared reel motion — the Gangsta Casino spin (front/js/gangsta-casino/slot.js,
// itself modelled on Uniqorn Wild Western Story's reel config), lifted out so
// other DOM-reel games can run the same thing:
//   - on spin press every reel accelerates (ease-in over ACCEL_CELLS) into a
//     seamless linear loop while the server answers;
//   - once the result is in, reel i runs i * STAGGER_FIGURES extra symbols
//     before its result (the stagger), brakes over the last cell (ease-out)
//     and stops dead on it — no bounce; an anticipating reel runs
//     SUSPENDED_FIGURES more;
//   - while a reel runs fast its symbols are swapped for pre-blurred twins
//     (`<static>_blur.png` next to each static, see scripts/make_reel_blur.py)
//     via `content: url()` — no per-frame filter.
// Everything plays as Web Animations on `transform` (compositor): a rAF loop
// moving the strips stuttered on phones busy skinning Spine.
//
// Assumes the usual DOM: reelCols[i] = { colEl, stripEl }, cells stacked in
// the strip with a constant rowStep, the column clipping the window, and the
// result's row 0 at translateY(0).
(function () {
  const PHYS = {
    SPEED: 3.3 / 200,     // cells per ms (Gangsta: 55 px/frame at 60 fps, 200 px cell)
    ACCEL_CELLS: 3,       // distance of the ease-in start
    LOOP_CELLS: 6,        // free-spin loop period
    BRAKE_CELLS: 1,       // ease-out stop over the last cell
    STAGGER_FIGURES: 2,   // extra symbols per reel to the right
    SUSPENDED_FIGURES: 24,
  };
  const EASE_IN_QUAD = 'cubic-bezier(0.55, 0.085, 0.68, 0.53)';
  const EASE_OUT_QUAD = 'cubic-bezier(0.25, 0.46, 0.45, 0.94)';

  let cssInjected = false;
  function injectCss() {
    if (cssInjected) return;
    cssInjected = true;
    const style = document.createElement('style');
    style.textContent = [
      '.reel__strip { will-change: transform; }',
      '.reel__strip.is-fast .reel__cell img[data-reel-blur] { content: var(--reel-blur); }',
    ].join('\n');
    document.head.appendChild(style);
  }

  const blurOk = new Map(); // blur url -> true (loaded) | false (missing) | Promise
  function blurUrlFor(src) {
    if (!src || !/\.png(\?|$)/i.test(src) || /_blur\.png/i.test(src)) return null;
    return src.replace(/\.png(\?.*)?$/i, '_blur.png');
  }
  function preloadBlur(url) {
    if (blurOk.has(url)) return;
    const img = new Image();
    img.decoding = 'async';
    const p = new Promise((resolve) => {
      img.onload = () => { blurOk.set(url, true); (img.decode ? img.decode() : Promise.resolve()).catch(() => {}).then(resolve); };
      img.onerror = () => { blurOk.set(url, false); resolve(); };
    });
    blurOk.set(url, p);
    img.src = url;
  }
  function tagBlur(cell) {
    for (const img of cell.querySelectorAll('img')) {
      const src = img.getAttribute('src');
      const url = blurUrlFor(src);
      if (!url) continue;
      if (!blurOk.has(url)) preloadBlur(url);
      if (blurOk.get(url) === false) continue;
      img.style.setProperty('--reel-blur', `url("${url}")`);
      img.dataset.reelBlur = '';
    }
    return cell;
  }

  function currentY(el) {
    return new DOMMatrixReadOnly(getComputedStyle(el).transform).m42;
  }

  // cfg: {
  //   cols: () => reelCols, rows, rowStep: () => px,
  //   makeCell: (code) => cell element,
  //   loopFiller: () => code (the symbols blurring past while waiting),
  //   codes: all symbol codes (to preload their blur twins),
  //   onReelStop: (col, isLast) => void,
  // }
  function create(cfg) {
    injectCss();
    const state = []; // per column: { stripEl, anim, fastTimer, stopping, saved }
    const speed = () => PHYS.SPEED * cfg.rowStep(); // px per ms
    const makeCell = (code) => tagBlur(cfg.makeCell(code));

    // Warm the blur twins up front so the first spin doesn't flash empty.
    try {
      for (const code of cfg.codes || []) tagBlur(cfg.makeCell(code));
    } catch (_) { /* best effort */ }

    function animate(st, frames, opts) {
      if (st.anim) st.anim.cancel();
      st.anim = st.stripEl.animate(frames, { fill: 'forwards', ...opts });
      return st.anim;
    }

    function startLoop() {
      const rs = cfg.rowStep(), L = PHYS.LOOP_CELLS, filler = cfg.loopFiller;
      const cols = cfg.cols();
      for (let col = 0; col < cols.length; col++) {
        const { stripEl } = cols[col];
        const prev = state[col];
        if (prev) { prev.stopping = true; clearTimeout(prev.fastTimer); if (prev.anim) prev.anim.cancel(); }
        stripEl.getAnimations().forEach((a) => a.cancel());
        stripEl.style.transition = 'none';
        stripEl.classList.remove('is-looping', 'is-fast');
        // The resting cells themselves ride along at the bottom of the strip
        // (labels and all), and go back in place if the spin errors out.
        const saved = Array.from(stripEl.children).slice(0, cfg.rows);
        const loop = Array.from({ length: L }, filler);
        stripEl.innerHTML = '';
        for (const code of [...loop, ...loop]) stripEl.appendChild(makeCell(code));
        for (const c of saved) stripEl.appendChild(c);
        // [loop, loop again, current]: the window starts on `current`, the
        // ease-in brings the second loop copy in, then a seamless linear loop.
        const y0 = -2 * L * rs;
        const yLoop = y0 + PHYS.ACCEL_CELLS * rs;
        stripEl.style.transform = `translateY(${y0}px)`;
        const st = { stripEl, anim: null, fastTimer: null, stopping: false, saved };
        state[col] = st;
        const accelMs = (2 * PHYS.ACCEL_CELLS * rs) / speed(); // ease-in quad ends at full speed
        const a = animate(st, [{ transform: `translateY(${y0}px)` }, { transform: `translateY(${yLoop}px)` }],
          { duration: accelMs, easing: EASE_IN_QUAD });
        st.fastTimer = setTimeout(() => stripEl.classList.add('is-fast'), accelMs * 0.4);
        a.onfinish = () => {
          if (st.stopping || state[col] !== st) return;
          // seamless: at yLoop and at yLoop + L*rs the window shows the same cells
          animate(st, [{ transform: `translateY(${yLoop}px)` }, { transform: `translateY(${yLoop + L * rs}px)` }],
            { duration: (L * rs) / speed(), iterations: Infinity, easing: 'linear' });
        };
      }
    }

    // Error path: the resting cells go back, no motion.
    function stopLoop() {
      const cols = cfg.cols();
      for (let col = 0; col < cols.length; col++) {
        const { stripEl } = cols[col];
        const st = state[col];
        stripEl.classList.remove('is-fast', 'is-looping');
        stripEl.style.transition = 'none';
        if (!st || st.stopping) { stripEl.style.transform = 'translateY(0px)'; continue; }
        st.stopping = true;
        clearTimeout(st.fastTimer);
        if (st.anim) st.anim.cancel();
        st.anim = null;
        stripEl.innerHTML = '';
        for (const c of st.saved) stripEl.appendChild(c);
        stripEl.style.transform = 'translateY(0px)';
      }
    }

    // Resolves with the result cells (top -> bottom) once the reel has
    // stopped on them. `opts`: { extra, anticipating, filler, onBuilt(cells) }.
    function landReel(col, finalCodes, opts = {}) {
      const { extra = 0, anticipating = false, filler = cfg.loopFiller, onBuilt = null } = opts;
      const rs = cfg.rowStep();
      const { stripEl } = cfg.cols()[col];
      let st = state[col];
      if (!st || st.stripEl !== stripEl || st.stopping) {
        // Not looping (e.g. a respin that skipped startLoop): run from rest.
        stripEl.getAnimations().forEach((a) => a.cancel());
        st = { stripEl, anim: null, fastTimer: null, stopping: false, saved: [] };
        state[col] = st;
        stripEl.style.transform = 'translateY(0px)';
      }
      return new Promise((resolve) => {
        st.stopping = true;
        stripEl.style.transition = 'none';
        let y = currentY(stripEl);
        if (st.anim) st.anim.cancel();
        // Trim the queued symbols above the window to one, so every reel's
        // run to its result is exactly its extra figures long (deterministic
        // left-to-right stop order).
        while (Math.floor(-y / rs) > 1 && stripEl.firstChild) { stripEl.firstChild.remove(); y += rs; }
        // Drop what's below the window.
        const below = () => (stripEl.children.length - 1) * rs + y > (cfg.rows + 1) * rs;
        while (stripEl.children.length > cfg.rows + 1 && below()) stripEl.lastChild.remove();
        const run = Array.from({ length: extra + (anticipating ? PHYS.SUSPENDED_FIGURES : 0) }, filler);
        // top -> bottom: 1 filler above the result, the result, then the run
        const made = [filler(), ...finalCodes, ...run].map(makeCell);
        const resultCells = made.slice(1, 1 + finalCodes.length);
        if (onBuilt) onBuilt(resultCells);
        const frag = document.createDocumentFragment();
        for (const c of made) frag.appendChild(c);
        stripEl.insertBefore(frag, stripEl.firstChild);
        y -= made.length * rs;
        const yStop = -1 * rs; // result row 0 at the window top
        const dist = yStop - y;
        const brake = Math.min(PHYS.BRAKE_CELLS * rs, dist);
        const v = speed();
        const runMs = Math.max(0, (dist - brake) / v);
        const brakeMs = (2 * brake) / v; // ease-out quad starts at full speed
        const total = runMs + brakeMs;
        stripEl.style.transform = `translateY(${y}px)`;
        st.anim = stripEl.animate([
          { transform: `translateY(${y}px)`, offset: 0, easing: 'linear' },
          { transform: `translateY(${yStop - brake}px)`, offset: total ? runMs / total : 0, easing: EASE_OUT_QUAD },
          { transform: `translateY(${yStop}px)`, offset: 1 },
        ], { duration: total, fill: 'forwards' });
        clearTimeout(st.fastTimer);
        stripEl.classList.add('is-fast');
        st.fastTimer = setTimeout(() => stripEl.classList.remove('is-fast'), runMs + brakeMs * 0.35);
        let done = false;
        const finish = () => {
          if (done) return;
          done = true;
          clearTimeout(st.fastTimer);
          stripEl.classList.remove('is-fast');
          if (st.anim) st.anim.cancel();
          st.anim = null;
          if (cfg.onReelStop) cfg.onReelStop(col, col === cfg.cols().length - 1);
          stripEl.innerHTML = '';
          for (const c of resultCells) stripEl.appendChild(c);
          stripEl.style.transform = 'translateY(0px)';
          resolve(resultCells);
        };
        st.anim.onfinish = finish;
        setTimeout(finish, total + 1200); // hidden tab: animations may not finish
      });
    }

    return { startLoop, stopLoop, landReel };
  }

  window.ReelSpin = { create, PHYS };
})();
