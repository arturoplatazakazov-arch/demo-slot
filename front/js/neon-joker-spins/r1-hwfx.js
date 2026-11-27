// Neon Joker Spins R1 — Hold & Win drama (2026-11-27). The round used to stop whole columns at once and
// move on; now it is a show:
//   pace      empty cells stop one by one, each a little later than the one before; the last cells
//             hold out and shake (.is-tense) with rising ticks; longer breaths between respins
//   a coin    slams in with a rising arpeggio, the screen jolts, a gold ring bursts from the cell
//   a miss    an empty cell goes out with a dull knock and a grey puff
//   respin    nothing came: the empties flicker out, the counter drops with a jolt, the lights sag,
//             a falling "wah-wah"; something came: a short fanfare before the spotlights hit the counter
// slot.js reads window.NJS_HW_PACE and calls NJS_HOOKS.hwCell / hwRespinEnd (other NJS pages: no-ops).
(function () {
  const screen = document.getElementById('screen');
  const stage = document.getElementById('stage');
  if (!screen || !stage) return;
  window.NJS_HW_PACE = {
    before: 650,      // the cells start spinning, a breath before the first stop
    cell: 330,        // first stop
    grow: 45,         // each next stop a bit later
    tenseLast: 2,     // the last N cells hold out ...
    tense: 380,       // ... this much longer each, shaking
    afterMiss: 350,   // a dead respin sinks in (on top of the miss show)
    between: 450,     // a breath before the next respin
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const restart = (el, cls, ms) => { if (!el) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); if (ms) setTimeout(() => el.classList.remove(cls), ms); };
  let hits = 0;
  let ticks = 0;

  function hwCell(info, hit, k, total) {
    const rest = total - k - 1;
    if (hit) {
      hits += 1;
      if (Sound.hwHit) Sound.hwHit(hits - 1);
      restart(stage, 'r1-jolt', 320);
      restart(info.cell, 'r1-hit', 900);
    } else {
      if (Sound.hwThud) Sound.hwThud();
      restart(info.cell, 'r1-miss', 700);
    }
    // the last cells: a rising tick for each one that is still spinning
    if (rest > 0 && rest <= window.NJS_HW_PACE.tenseLast && Sound.hwTick) Sound.hwTick(ticks++);
  }

  async function hwRespinEnd(landed, left, turbo) {
    const k = turbo ? 0.5 : 1;
    const got = hits;
    hits = 0; ticks = 0;
    if (landed > 0 || got > 0) {
      if (Sound.hwWin) Sound.hwWin(got);
      restart(screen, 'r1-hw-win', 900);
      await sleep(380 * k);
      return;
    }
    // nothing came
    if (Sound.hwMiss) Sound.hwMiss(left);
    screen.querySelectorAll('#reel .reel__cell').forEach((c) => { if (!c.classList.contains('is-locked')) restart(c, 'r1-fizzle', 1100); });
    restart(document.querySelector('.r1-count .r1-resp'), 'r1-drop', 800);
    restart(screen, 'r1-hw-sag', 1200);
    await sleep(700 * k);
  }

  window.NJS_HOOKS = Object.assign(window.NJS_HOOKS || {}, { hwCell, hwRespinEnd });
})();
