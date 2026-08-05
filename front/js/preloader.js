// Progress UI for the boot preloader (shared by every game page; tasks
// are registered by slot.js's preloadAssets). Pure view: add() grows the task
// total, step() marks one finished, done() plays the fade-out and removes the
// overlay. Safe to call in any order — done() wins over everything after it.
(function () {
  const root = document.getElementById('preloader');
  if (!root) return;
  const fill = document.getElementById('preloaderFill');
  const pct = document.getElementById('preloaderPct');

  let total = 0;
  let loaded = 0;
  let finished = false;

  function render() {
    const p = total ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
    fill.style.width = `${p}%`;
    pct.textContent = `${p}%`;
  }

  window.Preloader = {
    add(n = 1) {
      if (finished) return;
      total += n;
      render();
    },
    step() {
      if (finished) return;
      loaded++;
      render();
    },
    done() {
      if (finished) return;
      finished = true;
      fill.style.width = '100%';
      pct.textContent = '100%';
      root.classList.add('is-done');
      // Keep the node until the opacity transition ends, then drop it so it
      // never intercepts input (pointer-events are already off while fading).
      setTimeout(() => root.remove(), 600);
    },
  };
})();
