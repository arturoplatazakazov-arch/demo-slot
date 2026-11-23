// Neon Joker Spins R1 — the client's picked Spine win animations per symbol
// (neon-joker-spins-r1-symbol-anims.html, 2026-11-23). Stands in for fx.js's NeonFx with only
// the symbol hooks slot.js asks for: playWinAnimationOnce -> NeonFx.symbol(cell, code) plays the
// picked clip over the cell (the DOM tile hides meanwhile) and reports its length (inst.ms).
// Hold & Win: the coin clip plays on the trigger coins' charge-up, the Collector's when it lands.
// Every other fx(...) call finds no function here and slot.js keeps its CSS path.
(function () {
  if (window.NeonFx || !window.SpineEngine || !window.spine) return;
  const PICK = { seven: 2, bell: 3, star: 1, cherry: 3, lemon: 3, plum: 3, grape: 3, wild: 2, scatter: 5, coin: 1, collector: 4 };
  const ROOT = 'img/neon-joker-spins/skins/c/sets/r1/spine/sym';
  const VER = '2';
  const screen = document.getElementById('screen');
  const dim = document.getElementById('screenDim');
  if (!screen) return;
  const canvas = document.createElement('canvas');
  canvas.className = 'layer r1-sym-fx';
  canvas.style.cssText = 'inset:0;width:100%;height:100%;pointer-events:none;z-index:3';
  if (dim) screen.insertBefore(canvas, dim); else screen.appendChild(canvas);
  let stage;
  try { stage = new SpineEngine.SpineStage(canvas); } catch (e) { canvas.remove(); return; }

  const res = {};
  for (const code of Object.keys(PICK)) {
    SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/${code}`, { premultipliedAlpha: true, version: VER })
      .then((r) => { res[code] = r; }).catch((e) => console.warn('[r1] symbol fx', code, e));
  }
  const BOUNDS = { x: -200, y: -200, width: 400, height: 400 };   // one cell = 400 units (symbol art 360 x 0.9 x its own scale)

  function play(cell, code) {
    const r = res[code];
    if (!r || !cell) return null;
    const clip = `win_${PICK[code]}`;
    const anim = r.skeletonData.findAnimation(clip);
    if (!anim) return null;
    const inst = r.createInstance();
    inst.anchorEl = cell;
    inst.fit = 1;
    inst.boundsOverride = BOUNDS;
    inst.play(clip, false);
    inst.ms = anim.duration * 1000;
    stage.addBase(inst);
    return inst;
  }
  function drop(inst) { if (inst) stage.removeBase(inst); }

  window.NeonFx = {
    ready: true,
    // app.js / slot.js call these directly when a NeonFx exists: harmless no-ops here
    load: () => Promise.resolve(),
    buyState: () => {},
    symbol(cell, code) { return play(cell, code) || undefined; },
    dropSymbol: drop,
  };

  // Hold & Win: coins on the trigger charge-up, the Collector when it lands (DOM tile hidden meanwhile)
  const once = (cell, code) => {
    if (cell.classList.contains('is-animating')) return;
    const inst = play(cell, code);
    if (!inst) return;
    cell.classList.add('is-animating');
    setTimeout(() => { drop(inst); cell.classList.remove('is-animating'); }, inst.ms);
  };
  const orig = window.restartClass;
  if (typeof orig === 'function') {
    window.restartClass = function (el, cls, ms) {
      orig(el, cls, ms);
      if (!el || !el.dataset) return;
      if (cls === 'is-charging' && el.dataset.symbol === 'coin') once(el, 'coin');
      if (cls === 'is-slam' && el.dataset.symbol === 'collector' && !el.classList.contains('is-collect')) once(el, 'collector');
    };
  }
})();
