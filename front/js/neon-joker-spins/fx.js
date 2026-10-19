// Neon Joker Spins — standard Spine FX pack runtime (skeletons from
// scripts/neon_joker_spins_fx.py into img/neon-joker-spins/spine/).
// slot.js only reaches this through its fx() guard: no WebGL or a failed
// asset leaves the CSS game fully playable.
//
// Four canvases, each between the DOM layers it has to sit between:
//   #fxBack  (over the bg, under .stage) — background ambience (bokeh,
//            light passes; searchlights + confetti in free spins) and the
//            mascot, which stands BEHIND the cabinet;
//   #fxFront (over .stage)  — frame bulbs/tubes, logo, jackpot plates,
//            winning symbols, win lines;
//   #fxMid   (over the dim, under the popup) — Big Win rays + coin rain;
//   #fxTop   (over the popup) — the popup's neon title sign.
// Every skeleton is authored in its element's own pixel space, so CSS stays
// the only source of layout truth on both orientations.
(function () {
  const ROOT = 'img/neon-joker-spins/spine';
  const FX_V = 8;
  const box = (w, h) => ({ x: -w / 2, y: -h / 2, width: w, height: h });
  const BOX = {
    frame: box(1122, 1159),
    frame_mob: box(1173, 1130),
    logo: box(1350, 654),
    jp_mini: box(600, 217),
    jp_minor: box(600, 211),
    jp_major: box(600, 212),
    jp_grand: box(760, 317),
    symbols: box(360, 360),
    winlines: box(560, 550),
    bg_desk: box(1672, 941),
    bg_mob: box(941, 1672),
    mascot: box(760, 1520),
    bigwin: box(1200, 1200),
    buy: box(520, 328),
    sign_bigWin: box(727, 206),
    sign_megaWin: box(900, 243),
    sign_epicWin: box(900, 355),
    sign_freeSpins: box(900, 212),
    sign_holdAndWin: box(900, 209),
    sign_totalWin: box(801, 198),
  };
  const BG_SIZE = { bg_desk: [1672, 941], bg_mob: [941, 1672] };

  const S = {};
  const res = {};
  const inst = {};
  let mode = 'base';
  let winOn = false;
  let lineInst = null;
  let lineShown = 0;
  let bigInst = null;

  const NeonFx = { ready: false };
  const isMobile = () => window.matchMedia('(orientation: portrait)').matches;

  function load(stage, name) {
    if (res[name]) return Promise.resolve(res[name]);
    return SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/${name}`, { premultipliedAlpha: true, version: FX_V })
      .then((r) => { res[name] = r; return r; });
  }

  // The popup-level canvases are empty almost all the time, and an idle WebGL
  // canvas over the whole screen showed as a faint pink haze on the logo —
  // so they are only visible while they actually hold an instance.
  function syncVis(stage) {
    stage.canvasEl.style.visibility = stage.overlayInstances.length || stage.baseInstances.length ? 'visible' : 'hidden';
  }

  function make(name, anchorEl, fit = 1) {
    const i = res[name].createInstance();
    i.anchorEl = anchorEl;
    i.fit = fit;
    i.boundsOverride = BOX[name];
    return i;
  }

  // --- background anchor: the bg image's cover rect --------------------------
  function bgAnchor() {
    let el = document.getElementById('bgAnchor');
    if (!el) {
      el = document.createElement('div');
      el.id = 'bgAnchor';
      el.style.cssText = 'position:absolute;pointer-events:none;';
      document.getElementById('bgLayer').appendChild(el);
    }
    const v = isMobile() ? 'bg_mob' : 'bg_desk';
    const [iw, ih] = BG_SIZE[v];
    const host = document.getElementById('bgLayer').getBoundingClientRect();
    const k = Math.max(host.width / iw, host.height / ih) * 1.03; // .bg__img scale(1.03)
    const w = iw * k;
    const h = ih * k;
    el.style.left = `${(host.width - w) / 2}px`;
    el.style.top = `${(host.height - h) / 2}px`;
    el.style.width = `${w}px`;
    el.style.height = `${h}px`;
    return el;
  }

  // --- mounting per orientation ------------------------------------------------
  function mountBg() {
    const v = isMobile() ? 'bg_mob' : 'bg_desk';
    if (inst.bg && inst.bgName === v) { bgAnchor(); return; }
    if (!res[v]) { load(S.back, v).then(mountBg).catch(() => {}); return; }
    if (inst.bg) S.back.removeBase(inst.bg);
    inst.bgName = v;
    inst.bg = make(v, bgAnchor());
    inst.bg.play(mode === 'base' ? 'idle' : 'bonus', true);
    S.back.addBaseBehindAll(inst.bg);
  }

  function mountFrame() {
    const v = isMobile() ? 'frame_mob' : 'frame';
    if (inst.frame && inst.frameName === v) return;
    if (!res[v]) { load(S.front, v).then(mountFrame).catch(() => {}); return; }
    if (inst.frame) S.front.removeBase(inst.frame);
    inst.frameName = v;
    inst.frame = make(v, document.querySelector('.cabinet'));
    inst.frame.play(frameClip(), true);
    S.front.addBaseBehindAll(inst.frame);
  }

  function frameClip() {
    if (mode !== 'base') return 'bonus';
    return winOn ? 'win' : 'idle';
  }

  function mountMascot() {
    const el = document.getElementById('mascot');
    const show = !isMobile() && res.mascot;
    if (!show) {
      if (inst.mascot) S.back.removeBase(inst.mascot);
      inst.mascot = null;
      document.body.classList.remove('fx-mascot');
      return;
    }
    if (inst.mascot) return;
    // the rig's box is roomier than the old flat art — 1.16 brings him back
    // to the same height on screen
    inst.mascot = make('mascot', el, 1.16);
    // crossfade between clips: the near-win lean has to ease in and out,
    // a hard cut from idle read as a twitch
    res.mascot.animationStateData.defaultMix = 0.45;
    inst.mascot.play('idle', true);
    S.back.addBase(inst.mascot);
    document.body.classList.add('fx-mascot');
  }

  function mountAll() {
    mountBg();
    mountFrame();
    mountMascot();
  }

  NeonFx.load = function () {
    if (!window.spine || !window.SpineEngine) return Promise.resolve(false);
    try {
      S.back = new SpineEngine.SpineStage(document.getElementById('fxBack'));
      S.front = new SpineEngine.SpineStage(document.getElementById('fxFront'));
      S.mid = new SpineEngine.SpineStage(document.getElementById('fxMid'));
      S.top = new SpineEngine.SpineStage(document.getElementById('fxTop'));
    } catch (err) {
      console.warn('[neon-fx] no WebGL — CSS fallback', err);
      return Promise.resolve(false);
    }
    const mob = isMobile();
    const plates = ['mini', 'minor', 'major', 'grand'];
    const signs = ['bigWin', 'megaWin', 'epicWin', 'freeSpins', 'holdAndWin', 'totalWin'];
    return Promise.all([
      load(S.back, mob ? 'bg_mob' : 'bg_desk'),
      load(S.back, 'mascot'),
      load(S.front, mob ? 'frame_mob' : 'frame'),
      load(S.front, 'logo'),
      load(S.front, 'symbols'),
      load(S.front, 'winlines'),
      load(S.front, 'buy'),
      ...plates.map((t) => load(S.front, `jp_${t}`)),
      load(S.mid, 'bigwin'),
      ...signs.map((k) => load(S.top, `sign_${k}`)),
    ]).then(() => {
      NeonFx.ready = true;
      syncVis(S.mid);
      syncVis(S.top);
      mountAll();
      // the layered logo draws the whole sign itself: power-on letter by
      // letter, then the idle loop (the DOM <img> is only the anchor now)
      inst.logo = make('logo', document.querySelector('.logo img'));
      inst.logo.play('on', false);
      inst.logo.queue('idle', true);
      S.front.addBase(inst.logo);
      inst.plates = {};
      for (const t of plates) {
        const p = make(`jp_${t}`, document.querySelector(`.jp--${t}`));
        p.play('idle', true);
        S.front.addBase(p);
        inst.plates[t] = p;
      }
      inst.buy = make('buy', document.getElementById('buyBtn'));
      inst.buy.play('idle', true);
      S.front.addBase(inst.buy);
      NeonFx.buyState(!document.getElementById('buyBtn').disabled);
      document.getElementById('buyBtn').addEventListener('click', () => {
        if (!inst.buy) return;
        inst.buy.play('press', false);
        inst.buy.queue('idle', true);
      });
      document.body.classList.add('fx-ready');
      // the other orientation in the background, so a flip is instant
      load(S.back, mob ? 'bg_desk' : 'bg_mob').catch(() => {});
      load(S.front, mob ? 'frame' : 'frame_mob').catch(() => {});
      window.addEventListener('resize', () => setTimeout(mountAll, 50));
      return true;
    }).catch((err) => {
      console.warn('[neon-fx] assets failed — CSS fallback', err);
      return false;
    });
  };

  // --- hooks from slot.js ------------------------------------------------------

  NeonFx.spinStart = function () {
    NeonFx.hideLine();
    NeonFx.setWin(false);
  };

  NeonFx.anticipation = function (on) {
    if (!inst.frame) return;
    if (on) inst.frame.play('bonus', true);
    else inst.frame.play(frameClip(), true);
  };

  NeonFx.setWin = function (on) {
    if (on === winOn) return;
    winOn = on;
    if (inst.frame && mode === 'base') inst.frame.play(frameClip(), true);
    if (inst.logo) inst.logo.play(on ? 'win' : 'idle', true);
  };

  NeonFx.setMode = function (next) {
    if (next === mode) return;
    mode = next;
    if (inst.frame) inst.frame.play(frameClip(), true);
    if (inst.bg) inst.bg.play(next === 'base' ? 'idle' : 'bonus', true);
  };

  // Hold & Win entry: the frame's bulbs light up one by one and flash.
  NeonFx.holdWinStart = function () {
    if (!inst.frame) return;
    inst.frame.play('charge', false);
    inst.frame.queue('bonus', true);
  };

  // The sign's lights only run while the button can be pressed.
  NeonFx.buyState = function (on) {
    if (inst.buy) inst.buy.skeleton.color.a = on ? 1 : 0;
  };

  NeonFx.jackpotHit = function (tier) {
    const p = inst.plates && inst.plates[tier];
    if (!p) return;
    p.play('hit', false);
    p.queue('idle', true);
  };

  NeonFx.mascot = function (clip) {
    if (!inst.mascot) return;
    inst.mascot.play(clip, false);
    inst.mascot.queue('idle', true);
  };

  // Near win: loops while the last reel is anticipating; off -> back to idle
  // unless a reaction clip (win / near_miss) is about to take over.
  NeonFx.mascotNear = function (on) {
    if (!inst.mascot) return;
    if (on) inst.mascot.play('near_win', true);
    else inst.mascot.play('idle', true);
  };

  // A Spine copy of the tile plays over the cell; the caller hides the DOM
  // <img> meanwhile and drops the instance when the clip ends.
  NeonFx.symbol = function (cellEl, code) {
    if (!res.symbols || !res.symbols.skeletonData.findAnimation(code)) return null;
    const i = make('symbols', cellEl);
    i.play(code, false);
    S.front.addBase(i);
    return i;
  };
  NeonFx.dropSymbol = function (i) {
    if (i) S.front.removeBase(i);
  };

  // Payline 1..5 — showing the same line again keeps its loop running.
  NeonFx.showLine = function (n) {
    if (n === lineShown && lineInst) return true;
    NeonFx.hideLine();
    if (!res.winlines || !res.winlines.skeletonData.findAnimation(`line${n}_in`)) return false;
    lineInst = make('winlines', document.getElementById('reel'));
    lineInst.play(`line${n}_in`, false);
    lineInst.queue(`line${n}_loop`, true);
    lineShown = n;
    S.front.addOverlay(lineInst);
    return true;
  };
  NeonFx.hideLine = function () {
    if (lineInst) S.front.removeOverlay(lineInst);
    lineInst = null;
    lineShown = 0;
  };

  // Popup title sign: powers on over the (hidden) title <img>.
  NeonFx.popupTitle = function (imgEl, key) {
    const name = `sign_${key}`;
    if (!res[name]) return null;
    const i = make(name, imgEl);
    i.play('in', false);
    i.queue('idle', true);
    S.top.addOverlay(i);
    syncVis(S.top);
    return i;
  };
  NeonFx.dropTitle = function (i) {
    if (i) S.top.removeOverlay(i);
    syncVis(S.top);
  };

  // Big/Mega/Epic: rays + coin rain between the dim and the popup.
  NeonFx.bigWin = function (on) {
    if (on) {
      if (bigInst) return;
      bigInst = make('bigwin', document.getElementById('screen'));
      bigInst.play('in', false);
      bigInst.queue('loop', true);
      S.mid.addOverlay(bigInst);
    } else if (bigInst) {
      S.mid.removeOverlay(bigInst);
      bigInst = null;
    }
    syncVis(S.mid);
  };

  window.NeonFx = NeonFx;
})();
