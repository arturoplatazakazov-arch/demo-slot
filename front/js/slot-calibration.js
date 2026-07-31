// Symbol position calibration — per-symbol {dx, dy} pixel nudges for two
// independent layers: 'static' (the resting <img>, applyStaticContentOffset
// in each game's slot.js) and 'anim' (the win-animation's Spine anchor,
// applyAnchorOffset below). Backed by a real file on disk
// (front/calibration.json, via the backend — see
// app/api/admin/calibration.py), not localStorage: this is meant to be THE
// calibrated value for a demo, surviving server restarts, browser cache
// clears, and different machines/browsers — not a per-browser scratch
// layer. Anim Lab's "Калибровать" button (writes, needs the backend up)
// and every game's own startup (reads, via load() below) both go through
// this.
//
// Reads never need the backend: calibration.json sits right next to every
// front/*.html page, so load() just fetches it as a plain static file off
// whatever server is already serving the page itself. Only writes
// (set/clear) hit the backend, same as every other admin action in this
// project (front/js/api.js, front/admin/admin.js).
//
// load() must be awaited once before any get() call — every game's init()
// does this before building its reel grid; get() itself stays synchronous,
// reading from the in-memory cache load() populates.

(function () {
  const API_BASE = 'http://127.0.0.1:8000/api/admin/calibration';

  let cache = {}; // { [game]: { [code]: { static?: {dx,dy}, anim?: {dx,dy} } } }

  async function load() {
    try {
      const res = await fetch('calibration.json', { cache: 'no-store' });
      cache = res.ok ? await res.json() : {};
    } catch {
      cache = {}; // no file yet, or nothing reachable — just means no overrides
    }
  }

  function get(game, code, kind = 'static') {
    const raw = cache[game]?.[code]?.[kind];
    if (!raw) return null;
    return { dx: Number(raw.dx) || 0, dy: Number(raw.dy) || 0 };
  }

  async function set(game, code, dx, dy, kind = 'static') {
    const res = await fetch(`${API_BASE}/${game}/${code}/${kind}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dx, dy }),
    });
    if (!res.ok) throw new Error(`Не удалось сохранить калибровку (HTTP ${res.status}) — бэкенд запущен?`);
    // Optimistic local update, so a page that both writes and reads
    // calibration (Anim Lab) sees the change instantly without refetching.
    cache[game] = cache[game] || {};
    cache[game][code] = cache[game][code] || {};
    cache[game][code][kind] = { dx, dy };
  }

  async function clear(game, code, kind = 'static') {
    const res = await fetch(`${API_BASE}/${game}/${code}/${kind}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Не удалось сбросить калибровку (HTTP ${res.status}) — бэкенд запущен?`);
    if (cache[game]?.[code]) {
      delete cache[game][code][kind];
      if (Object.keys(cache[game][code]).length === 0) delete cache[game][code];
    }
  }

  // .reel__cell-anchor is always `transform: translate(-50%, -50%)` in every
  // game's CSS (that's what centers it on the cell) — an 'anim' override
  // adds a second translate() on top rather than replacing it. Setting the
  // inline style to '' when there's no override lets the CSS class's own
  // rule apply normally.
  function applyAnchorOffset(anchorEl, game, code) {
    const override = get(game, code, 'anim');
    anchorEl.style.transform = override ? `translate(-50%, -50%) translate(${override.dx}px, ${override.dy}px)` : '';
  }

  window.SlotCalibration = { load, get, set, clear, applyAnchorOffset };
})();
