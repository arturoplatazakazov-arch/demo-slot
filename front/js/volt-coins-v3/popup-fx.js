// Volt Coins V3: animated popups from the designer's 2nd PSB (2026-11-05).
//
// Skeletons fx/pop_<key> (scripts/volt_coins_v3_popups_fx.py): clip `in`
// (1 s: rays bloom, panel unfolds, title slams in, coins burst out) then
// `loop` (3 s, seamless). fx/pop.json gives, per popup, the core box (title +
// panel; rays/coins spill out of it), the amount panel and buttons as
// fractions of that box, and where the static fallback popups/<key>_v3.webp
// sits against it.
//
// One canvas (#fxPopup) of its own, drawn right under the popup DOM node (its
// z-index follows the node), so the live amount / the buy buttons stay DOM on
// top of the art. Without WebGL or with a failed load, the node shows the
// static fallback image instead — the game never waits for it.
//
// Coin rain (fx/coin_rain, scripts/volt_coins_v3_coin_rain.py) on Big / Mega /
// Epic Win and GRAND: coins rise from behind the popup (an instance on the
// popup canvas, drawn before the popup) and fall in front of everything, the
// amount included (a second canvas #fxPopupTop just above the node).
(function () {
  const ROOT = 'img/volt-coins-v3/fx';
  const V = 4;
  const VoltPop = { meta: null, ready: false };
  let stage = null;
  let canvas = null;
  let topStage = null;
  let topCanvas = null;
  let rain = null;
  const res = {};
  const RAIN = { big_win: 'big', mega_win: 'mega', epic_win: 'epic', jp_grand: 'grand' };
  // rain units: the popup core width = 1000 (fit by width to the node)
  const RAIN_BOX = { x: -500, y: -260, width: 1000, height: 520 };

  VoltPop.load = async function load() {
    try {
      VoltPop.meta = await fetch(`${ROOT}/pop.json?v=${V}`).then((r) => r.json());
      if (!window.SpineEngine || !window.spine) return;
      canvas = document.createElement('canvas');
      canvas.className = 'layer fx-canvas fx-canvas--popup';
      canvas.id = 'fxPopup';
      document.getElementById('screen').appendChild(canvas);
      stage = new SpineEngine.SpineStage(canvas);
      topCanvas = document.createElement('canvas');
      topCanvas.className = 'layer fx-canvas fx-canvas--popup-top';
      topCanvas.id = 'fxPopupTop';
      document.getElementById('screen').appendChild(topCanvas);
      topStage = new SpineEngine.SpineStage(topCanvas);
      // one skeleton, two GL contexts: the resource cache is keyed by path, so
      // the second load names the json explicitly (a separate cache entry)
      Promise.all([
        SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/coin_rain`, { premultipliedAlpha: true, version: V }),
        SpineEngine.SpineResource.load(topStage.assetManager, `${ROOT}/coin_rain`, { premultipliedAlpha: true, version: V, skeleton: 'animation' }),
      ]).then(([back, front]) => { rain = { back, front }; })
        .catch((e) => console.warn('[volt] coin rain failed', e));
      await Promise.all(Object.keys(VoltPop.meta).map((k) =>
        SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/pop_${k}`, { premultipliedAlpha: true, version: V })
          .then((r) => { res[k] = r; })
          .catch((e) => console.warn('[volt] popup skeleton failed', k, e))));
      VoltPop.ready = true;
    } catch (e) {
      console.warn('[volt] popups: static fallback only', e);
    }
  };

  VoltPop.has = (key) => Boolean(VoltPop.meta && VoltPop.meta[key]);

  // Static fallback + panel/buttons boxes into `node` (the core box).
  VoltPop.dress = function dress(node, key) {
    const m = VoltPop.meta[key];
    node.style.setProperty('--art-ar', `${m.core[0]} / ${m.core[1]}`);
    const a = m.art;
    const img = document.createElement('img');
    img.className = 'game-popup__art pop-art';
    img.alt = '';
    img.src = `img/volt-coins-v3/popups/${key}_v3.webp?v=${V}`;
    Object.assign(img.style, {
      left: `${a.l * 100}%`, top: `${a.t * 100}%`, width: `${a.w * 100}%`, height: `${a.h * 100}%`, inset: 'auto',
    });
    node.prepend(img);
    return m;
  };

  VoltPop.box = (m) => `left:${m.l * 100}%;top:${m.t * 100}%;width:${m.w * 100}%;height:${m.h * 100}%`;

  // Play `key` anchored to `node`; returns a handle with hide().
  function rainInst(r, node, clip) {
    const inst = r.createInstance();
    inst.anchorEl = node;
    inst.fit = 1;
    inst.fitMode = 'width';
    inst.boundsOverride = RAIN_BOX;
    inst.play(`${clip}_start`, false).queue(clip, true, 0);
    return inst;
  }

  function fadeOut(st, inst, ms) {
    const t0 = performance.now();
    const step = () => {
      const k = Math.min(1, (performance.now() - t0) / ms);
      inst.skeleton.color.a = 1 - k;
      if (k < 1) requestAnimationFrame(step);
      else st.removeOverlay(inst);
    };
    requestAnimationFrame(step);
  }

  // Play `key` anchored to `node`; returns a handle with hide().
  VoltPop.show = function show(key, node) {
    if (!VoltPop.ready || !res[key]) return null;
    const z = parseInt(getComputedStyle(node).zIndex, 10) || 30;
    canvas.style.zIndex = String(z - 1);
    topCanvas.style.zIndex = String(z + 1);
    const parts = [];
    const tier = RAIN[key];
    if (tier && rain) {
      const back = rainInst(rain.back, node, `${tier}_back`);
      stage.addOverlay(back);                 // under the popup art
      parts.push([stage, back]);
    }
    const inst = res[key].createInstance();
    inst.anchorEl = node;
    inst.fit = 1;
    inst.play('in', false).queue('loop', true, 0);
    stage.addOverlay(inst);
    parts.push([stage, inst]);
    if (tier && rain) {
      const front = rainInst(rain.front, node, `${tier}_front`);
      topStage.addOverlay(front);             // over the popup and the amount
      parts.push([topStage, front]);
    }
    node.classList.add('is-spine');
    return {
      // fade these instances only (another popup may still be on the canvas)
      hide(ms = 260) {
        for (const [st, i] of parts) fadeOut(st, i, ms);
      },
    };
  };

  window.VoltPop = VoltPop;
  // after the game itself has loaded: the popup atlases are not on the first screen
  const start = () => setTimeout(() => VoltPop.load(), 1500);
  if (document.readyState === 'complete') start();
  else window.addEventListener('load', start, { once: true });
})();
