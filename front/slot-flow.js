// SlotFlow — the shared ORDER of what happens on a spin, worked out on
// Gangsta Casino (2026-11-19) and reused by every 5x3 line game that plugs in.
// A game keeps its own art and mechanics; it only hands SlotFlow small
// primitives ("play this phase of the win", "open this popup", "blackout in")
// and SlotFlow decides WHEN each runs. The rules:
//
//  1. Landing: every reel stop has its sound; scatters land as 1st / 2nd /
//     3rd+ (rising), the wild and the game's own specials have a land sound.
//  2. Anticipation: its loop plays until the anticipated reel stops, then a
//     hit or a miss sound.
//  3. The game's mechanic step (multipliers, wheel, …) runs between the
//     landing and the win presentation.
//  4. Win presentation: all winning cells together, then each line on its
//     own. The FIRST pass plays the line sound + the paying symbol's melody
//     and waits for animation AND sound; later passes loop silently.
//  5. Big / mega / epic open only after that first full pass.
//  6. Bonus entry from scatters: scatter pass + melody -> YOU WON popup ->
//     blackout (the light never comes back in between) -> bonus mode, bonus
//     music starts with the bonus preview screen -> tap -> bonus game.
//  7. A retrigger's YOU WON inside the bonus waits for the scatter pass too.
//  8. Nothing of the win shows through a popup or a screen (layer guard).
//  9. Counting a win up has its loop sound and an end sound.
//
// Every step is traced (SlotFlow.trace / SlotFlow.onTrace) — the DEV panel's
// "Проверка" tab runs scenarios and checks the trace against these rules.
(function () {
  const wait = (ms) => new Promise((res) => setTimeout(res, ms));
  const S = () => window.Sound || { playSfx: () => ({ done: Promise.resolve(), stop() {} }), playMusic() {}, isMuted: () => true };

  // --- trace ------------------------------------------------------------------
  const listeners = new Set();
  const log = [];
  function trace(type, info = {}) {
    const e = { type, t: performance.now(), ...info };
    log.push(e);
    if (log.length > 400) log.shift();
    for (const fn of listeners) { try { fn(e); } catch (err) { console.warn('flow trace', err); } }
    return e;
  }

  // --- 4. win presentation -------------------------------------------------------
  // groups: arrays of cells (one per line / count win); allInfos: every winning
  // cell. playPhase(infos, index) plays one phase (-1 = all together) and
  // resolves when its animation is done. symbolOf(infos) -> symbol code.
  // Resolves after the first full pass (capped by maxMs). The loop goes on
  // until isCurrent() turns false (the next spin / teardown).
  function presentWins({ groups, allInfos, playPhase, symbolOf, pauseMs = 450, isCurrent = () => true, maxMs = 9000 }) {
    if (!allInfos || !allInfos.length) return Promise.resolve();
    trace('wins:start', { lines: groups.length });
    let done;
    const cycle = new Promise((res) => { done = res; });
    const melody = (infos) => {
      const code = infos.length ? symbolOf(infos) : null;
      return code ? S().playSfx(`symWin_${code}`).done : Promise.resolve();
    };
    let index = -1;
    let first = true;
    const step = () => {
      if (!isCurrent()) { done(); return; }
      const infos = index === -1 ? allInfos : groups[index];
      let sound = null;
      if (first) {
        if (index === -1) sound = melody(groups[0] || allInfos);
        else if (groups.length > 1) sound = Promise.all([S().playSfx('winLine').done, melody(infos)]);
      }
      const waits = [Promise.resolve(playPhase(infos, index))];
      if (sound) waits.push(sound);
      Promise.all(waits).then(() => {
        if (!isCurrent()) { done(); return; }
        const last = groups.length <= 1 ? index === -1 : index === groups.length - 1;
        if (first && last) { first = false; trace('wins:cycleDone'); done(); }
        setTimeout(() => {
          if (!isCurrent()) return;
          index = groups.length <= 1 ? -1 : (index + 1) % groups.length;
          step();
        }, pauseMs);
      });
    };
    step();
    let settled = false;
    cycle.then(() => { settled = true; });
    return Promise.race([cycle, wait(maxMs).then(() => { if (!settled) trace('wins:cycleTimeout'); })]);
  }

  // --- 1. landing -------------------------------------------------------------
  // landing({ scatter: 'scatter', specials: { wild: 'wildLand', wof: 'multLand' } })
  function landing({ scatter = 'scatter', specials = { wild: 'wildLand' } } = {}) {
    let scatters = 0;
    return {
      reset() { scatters = 0; },
      land(codes) {
        for (const code of codes) {
          if (code === scatter) {
            scatters += 1;
            S().playSfx(`scatterLand${Math.min(3, scatters)}`);
          } else if (specials[code]) S().playSfx(specials[code]);
        }
      },
    };
  }

  // --- 2. anticipation ------------------------------------------------------------
  function anticipation() {
    const loop = S().playSfx('anticipation');
    trace('anticipation:start');
    return {
      resolve(hit) {
        loop.stop(150);
        S().playSfx(hit ? 'anticipationWin' : 'anticipationFail');
        trace(hit ? 'anticipation:hit' : 'anticipation:miss');
      },
    };
  }

  // --- 8. layer guard ---------------------------------------------------------------
  // layerGuard(setVisible) -> { hide(), show() }, counted: a popup can open
  // inside a screen's lifetime.
  function layerGuard(setVisible) {
    let n = 0;
    return {
      hide() { n += 1; if (n === 1) { setVisible(false); trace('layer:hide'); } },
      show() { n = Math.max(0, n - 1); if (n === 0) { setVisible(true); trace('layer:show'); } },
      get hidden() { return n > 0; },
    };
  }

  // --- 9. count-up --------------------------------------------------------------------
  function countSound() {
    const loop = S().playSfx('countLoop');
    let ended = false;
    return { end() { if (ended) return; ended = true; loop.stop(120); S().playSfx('countEnd'); } };
  }

  // --- 6. bonus entry / exit ------------------------------------------------------------
  // p: { popup(amount) -> Promise (opens and fully closes YOU WON, no own dim),
  //      dimIn(opaque) / dimOut(opaque), dimMs, switchMode('freespins'),
  //      preview(spins) -> Promise<boolean>|null (the bonus preview screen;
  //      resolves after the tap; false/null = the game has none) }
  async function enterBonus(p, { spins = 0, popupAmount = spins, withPopup = false } = {}) {
    const dimMs = p.dimMs != null ? p.dimMs : 320;
    if (withPopup) {
      p.dimIn(false);
      trace('popup:open', { kind: 'bonusSpinsWin', amount: popupAmount });
      await p.popup(popupAmount); // the popup plays its own sound
      trace('popup:close', { kind: 'bonusSpinsWin' });
    }
    S().playSfx('baseToBonus');
    p.dimIn(true);
    trace('bonus:blackout');
    await wait(dimMs);
    p.switchMode('freespins');
    S().playMusic('bonus');
    trace('bonus:music');
    let shown = false;
    if (p.preview) {
      trace('bonus:preview');
      shown = !!(await p.preview(spins));
    }
    if (!shown && !withPopup && p.popup) {
      // no preview screen and no popup yet: the YOU WON card stands in
      trace('popup:open', { kind: 'bonusSpinsWin', amount: spins });
      await p.popup(spins);
      trace('popup:close', { kind: 'bonusSpinsWin' });
    }
    await wait(dimMs);
    p.dimOut(true);
    if (withPopup) p.dimOut(false);
    trace('bonus:enter');
  }

  async function exitBonus(p) {
    const dimMs = p.dimMs != null ? p.dimMs : 320;
    S().playMusic('base');
    S().playSfx('bonusToBase');
    p.dimIn(true);
    await wait(dimMs);
    p.switchMode('base');
    await wait(dimMs);
    p.dimOut(true);
    trace('bonus:exit');
  }

  // --- 5, 6, 7. the spin result order ---------------------------------------------------
  const TIERS = new Set(['bigWin', 'megaWin', 'epicWin']);
  // h: { isBonus(), mechanic(data, wasInRound) -> Promise (optional),
  //      playWins(data) -> Promise (first pass), setCounter(n) (optional),
  //      enterBonus(opts) -> Promise, exitBonus() -> Promise,
  //      popup(type, amount) (opens a popup; need not be awaited),
  //      smallWin(amount), skipPopup(type) -> bool (optional) }
  async function applyResult(data, h) {
    const remaining = data.feature && data.feature.type === 'free_spins' ? data.feature.spins_remaining : 0;
    const wasInRound = h.isBonus();
    const entering = !wasInRound && remaining > 0;
    trace('result', { win: data.total_win || 0, popup: data.popup && data.popup.type, remaining });
    if (h.mechanic) await h.mechanic(data, wasInRound);
    const cycle = h.playWins(data);
    if (remaining > 0 && h.setCounter) h.setCounter(remaining);
    const popup = data.popup;
    const scatterEntry = entering && !!popup && popup.type === 'bonusSpinsWin';
    if (scatterEntry) await cycle;
    if (entering) await h.enterBonus({ spins: remaining, popupAmount: scatterEntry ? popup.amount : remaining, withPopup: scatterEntry });
    else if (wasInRound && remaining === 0) await h.exitBonus();
    if (popup) {
      const shown = scatterEntry || popup.type === 'buyFreeSpins' || (h.skipPopup && h.skipPopup(popup.type));
      if (!shown) {
        if (TIERS.has(popup.type) || popup.type === 'bonusSpinsWin') await cycle;
        trace('popup:open', { kind: popup.type, amount: popup.amount });
        h.popup(popup.type, popup.amount);
      }
    } else if (data.total_win > 0) {
      S().playSfx('smallWin');
      h.smallWin(data.total_win);
    }
  }

  window.SlotFlow = {
    presentWins, landing, anticipation, layerGuard, countSound, enterBonus, exitBonus, applyResult,
    trace, onTrace(fn) { listeners.add(fn); return () => listeners.delete(fn); }, log,
    TIERS,
  };
})();
