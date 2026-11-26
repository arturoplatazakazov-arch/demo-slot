// Neon Joker Spins R1 — one amount format for the whole screen (client round 2, 2026-11-26):
// "in Figma the sums are in x, in the build TOTAL is in currency — pick one, ship the other as atlas
// glyphs: casinos show currency, crypto shows multipliers".
//   cash (default)  every sum in currency, coin faces too (25x -> 12.5k at bet 500)
//   x               every sum as a multiple of the bet (TOTAL WIN 18,750 -> 37.5x), coins as they are
// ?amounts=x | ?amounts=cash, or the DEV panel (kept per browser). Both formats are the same glyph
// atlas (digits , . k m x). Only glyph rows that carry money change: wins, popups, TOTAL WIN, jackpots,
// the FS summary, coin faces. Counters, "x10", the balance and the buy price are left alone.
(function () {
  if (typeof setGlyphs !== 'function') return;
  const KEY = 'njs-r1-amounts';
  const q = new URLSearchParams(location.search).get('amounts');
  let mode = q === 'x' || q === 'cash' ? q : null;
  if (!mode) { try { mode = localStorage.getItem(KEY); } catch (e) { /* noop */ } }
  if (mode !== 'x') mode = 'cash';

  const MONEY = '#reelWinValue, #fsWin, #hwTotal, .jp__value, .game-popup__panel .glyphs, .r1-scene--summary .r1-scene__value, .r1-pop__value';
  const bet = () => (typeof currentBet === 'function' ? currentBet() : 0) || 1;
  const parse = (t) => {
    const m = /^([\d,]+(?:\.\d+)?)([km]?)$/.exec(t);
    if (!m) return null;
    return parseFloat(m[1].replace(/,/g, '')) * (m[2] === 'k' ? 1e3 : m[2] === 'm' ? 1e6 : 1);
  };
  const fmtX = (v) => {
    const r = v < 10 ? Math.round(v * 100) / 100 : v < 100 ? Math.round(v * 10) / 10 : Math.round(v);
    return `${r.toLocaleString('en-US', { maximumFractionDigits: 2 })}x`;
  };

  const raw = setGlyphs;
  window.setGlyphs = function (el, text) {
    let t = String(text).toLowerCase();
    if (el && el.matches) {
      if (mode === 'x' && el.matches(MONEY)) {
        const v = parse(t);
        if (v != null) t = v === 0 ? '0x' : fmtX(v / bet());
      } else if (mode === 'cash' && el.classList.contains('coin-val')) {
        const m = /^(\d+(?:\.\d+)?)x$/.exec(t);
        if (m) t = formatShort(parseFloat(m[1]) * bet());
      }
      // a currency face is longer than "25x": keep it inside the coin
      if (el.classList.contains('coin-val') && window.r1FitGlyphs) window.r1FitGlyphs(el, el.closest('.reel__cell') || el.parentElement, 0.66);
    }
    return raw(el, t);
  };

  window.R1Amounts = {
    get mode() { return mode; },
    set(m) {
      mode = m === 'x' ? 'x' : 'cash';
      try { localStorage.setItem(KEY, mode); } catch (e) { /* noop */ }
      document.documentElement.dataset.amounts = mode;
      // redraw what is on screen now
      if (typeof updateJackpotPlates === 'function') updateJackpotPlates(bet());
      document.querySelectorAll(MONEY).forEach((el) => { delete el.dataset.text; });
      return mode;
    },
  };
  document.documentElement.dataset.amounts = mode;
})();
