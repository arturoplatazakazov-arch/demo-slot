// Volt Coins — Spine FX layer (skeletons from scripts/volt_coins_fx.py into
// img/volt-coins/fx/). slot.js only ever calls these through its fx() guard,
// so a missing WebGL / failed asset leaves the CSS game fully playable.
//
// Two canvases sandwich the DOM stage:
//   #fxBack  (under .stage) — the vault door's light (bg_desk / bg_mob),
//                             anchored to #bgAnchor = the bg's cover rect;
//   #fxFront (over .stage)  — base: frame, logo, winning symbols;
//                             overlay: Tesla coils, lightning arcs, win lines.
// Every skeleton is authored in its element's own pixel space (BOX below), so
// CSS stays the only source of layout truth on both orientations.
//
// The coils follow the client's table: off in idle (a rare spark), a short
// charge on spin, a growing charge through last-reel anticipation, an arc to
// each landing coin, a discharge into the frame on Hold & Win, an arc from a
// jackpot coin to its plate, full discharge of both on GRAND 9/9, arcs at the
// peak of a Big Win.

(function () {
  const ROOT = 'img/volt-coins-v2/fx';
  // Версия atlas/json скелетов — поднимать при каждой пересборке fx
  // (PNG-страницы версионируются хешем в самом атласе).
  const FX_V = 14;
  const BOX = {
    bg_desk: { x: -899, y: -437.5, width: 1798, height: 875 },
    bg_mob: { x: -465.5, y: -845, width: 931, height: 1690 },
    coil: { x: -283, y: -540, width: 566, height: 1080 },
    frame: { x: -435, y: -347, width: 870, height: 694 },
    logo: { x: -620, y: -186, width: 1240, height: 372 },
    winlines: { x: -383, y: -302, width: 766, height: 604 },
  };
  // Where a coil's head (the ring) is, as a fraction of the coil image.
  const COIL_HEAD = { x: 283 / 566, y: 85 / 1080 };
  const ARC_LEN = 1000;

  let back = null;
  let front = null;
  const res = {};
  let doorInst = null;
  let doorVariant = null;
  let frameInst = null;
  let logoInst = null;
  const coils = [];
  let lineInst = null;
  let lineShown = 0;
  let mode = 'base';
  let winOn = false;
  let bigOn = false;
  let anticOn = false;
  let overDim = 0;
  let bigTimer = null;

  const VoltFx = { ready: false };

  const isMobile = () => window.matchMedia('(orientation: portrait)').matches;

  function load(stage, name) {
    return SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/${name}`, { premultipliedAlpha: true, version: FX_V })
      .then((r) => { res[name] = r; return r; });
  }

  function make(name, anchorEl, box = BOX[name]) {
    const inst = res[name].createInstance();
    inst.anchorEl = anchorEl;
    inst.fit = 1;
    if (box) inst.boundsOverride = box;
    return inst;
  }

  function mountDoor() {
    const v = isMobile() ? 'bg_mob' : 'bg_desk';
    if (v === doorVariant || !res[v]) return;
    if (doorInst) back.removeBase(doorInst);
    doorVariant = v;
    doorInst = make(v, document.getElementById('bgAnchor'));
    doorInst.play(mode === 'bonus' ? 'bonus' : 'idle', true);
    back.addBase(doorInst);
  }

  // --- coils -------------------------------------------------------------------

  function coilIdle(c) {
    c.inst.play('off', true);
    // the two coils spark at different moments, never in sync
    const e = c.inst.animationState.getCurrent(0);
    if (e) e.trackTime = c.phase;
  }

  function coilsPlay(clip, loop = false, thenIdle = true) {
    for (const c of coils) {
      c.inst.play(clip, loop);
      if (!loop && thenIdle) c.inst.queue(winOn ? 'win' : 'off', true);
    }
  }

  function coilsRest() {
    for (const c of coils) {
      if (bigOn) c.inst.play('bigwin', true);
      else if (anticOn) c.inst.play('charged', true);
      else if (winOn) c.inst.play('win', true);
      else coilIdle(c);
    }
  }

  function coilHead(c) {
    const r = c.el.getBoundingClientRect();
    return { x: r.left + r.width * COIL_HEAD.x, y: r.top + r.height * COIL_HEAD.y };
  }

  function center(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  function nearestCoil(p) {
    let best = coils[0];
    let bd = Infinity;
    for (const c of coils) {
      const h = coilHead(c);
      const d = (h.x - p.x) ** 2 + (h.y - p.y) ** 2;
      if (d < bd) { bd = d; best = c; }
    }
    return best;
  }

  // --- arcs ----------------------------------------------------------------------

  // One lightning stroke between two client-space points. The arc skeleton is
  // a 1000-unit stroke centred on its origin; the root bone is rotated and
  // stretched so it spans exactly a -> b. Thickness grows a little with length
  // so short hops stay crisp and long ones read from across the screen.
  function zap(a, b, delay = 0) {
    if (!res.arc) return;
    const run = () => {
      const canvas = front.canvasEl;
      const cr = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const ax = (a.x - cr.left) * dpr;
      const ay = (a.y - cr.top) * dpr;
      const bx = (b.x - cr.left) * dpr;
      const by = (b.y - cr.top) * dpr;
      const len = Math.hypot(bx - ax, by - ay);
      if (len < 4) return;
      const inst = res.arc.createInstance();
      const k = len / ARC_LEN;
      const sk = inst.skeleton;
      const root = sk.getRootBone();
      root.rotation = (Math.atan2(-(by - ay), bx - ax) * 180) / Math.PI;
      root.scaleX = k;
      root.scaleY = Math.min(1.1, Math.max(0.45, 0.35 + k * 0.6)) * dpr * 0.55;
      const place = () => {
        sk.x = (ax + bx) / 2 - canvas.width / 2;
        sk.y = canvas.height / 2 - (ay + by) / 2;
      };
      place();
      const update = inst.update.bind(inst);
      inst.update = (delta, canvasEl) => { place(); update(delta, canvasEl); };
      inst.play('zap', false);
      inst.onSettle = () => front.removeOverlay(inst);
      front.addOverlay(inst);
    };
    if (delay) setTimeout(run, delay); else run();
  }

  // --- load ---------------------------------------------------------------------

  VoltFx.load = function load_() {
    if (!window.spine || !window.SpineEngine) return Promise.resolve(false);
    try {
      back = new SpineEngine.SpineStage(document.getElementById('fxBack'));
      front = new SpineEngine.SpineStage(document.getElementById('fxFront'));
    } catch (err) {
      console.warn('[volt-fx] no WebGL — CSS fallback', err);
      return Promise.resolve(false);
    }
    return Promise.all([
      load(back, isMobile() ? 'bg_mob' : 'bg_desk'),
      load(front, 'coil'),
      load(front, 'arc'),
      load(front, 'frame'),
      load(front, 'logo'),
      load(front, 'winlines'),
      load(front, 'symbols'),
    ]).then(() => {
      VoltFx.ready = true;
      mountDoor();
      frameInst = make('frame', document.getElementById('cabinetFrame'));
      frameInst.play('idle', true);
      front.addBase(frameInst);
      logoInst = make('logo', document.querySelector('.logo__img'));
      logoInst.play('idle', true);
      front.addBase(logoInst);
      [['coilLeft', 0], ['coilRight', 3.4]].forEach(([id, phase]) => {
        const el = document.getElementById(id);
        if (!el) return;
        const c = { el, phase, inst: make('coil', el) };
        coils.push(c);
        coilIdle(c);
        front.addOverlay(c.inst);
      });
      document.body.classList.add('fx-ready');
      load(back, isMobile() ? 'bg_desk' : 'bg_mob').catch(() => {});
      window.addEventListener('resize', () => {
        const v = isMobile() ? 'bg_mob' : 'bg_desk';
        if (res[v]) mountDoor();
        else load(back, v).then(mountDoor).catch(() => {});
      });
      return true;
    }).catch((err) => {
      console.warn('[volt-fx] assets failed — CSS fallback', err);
      return false;
    });
  };

  // --- hooks from slot.js -------------------------------------------------------

  VoltFx.spinStart = function spinStart() {
    // GDD: «нажатие спина — короткий заряд ~0.5 с»
    if (anticOn || bigOn) return;
    coilsPlay('spin');
  };

  VoltFx.spinStop = function spinStop() {};

  VoltFx.anticipation = function anticipation(on) {
    if (on === anticOn) return;
    anticOn = on;
    if (on) {
      // GDD: «постепенный заряд, дуги растут вместе со звуком»
      for (const c of coils) {
        c.inst.play('charge', false);
        c.inst.queue('charged', true);
      }
    } else {
      coilsRest();
    }
  };

  // Ревью 2: молния ведёт взгляд К монете и не перечёркивает лого/джекпоты.
  // Если катушка выше рамки (портрет 1/2), разряд бьёт из боковой кромки
  // рамки на высоте монеты — ближайшей к ней стороны; иначе из головы катушки.
  function zapFrom(c, p) {
    const h = coilHead(c);
    const fr = document.getElementById('cabinetFrame').getBoundingClientRect();
    if (h.y >= fr.top) return h;
    const left = p.x < fr.left + fr.width / 2;
    return { x: left ? fr.left + fr.width * 0.02 : fr.right - fr.width * 0.02, y: p.y + (Math.random() - 0.5) * 12 };
  }

  VoltFx.coinLanded = function coinLanded(cellEl) {
    // GDD: «приземление монеты — короткая дуга от катушки к монете»
    const p = center(cellEl);
    const c = nearestCoil(p);
    if (!c) return;
    zap(zapFrom(c, p), p);
    if (!anticOn && !bigOn) {
      c.inst.play('spin', false);
      c.inst.queue(winOn ? 'win' : 'off', true);
    }
  };

  // Ревью 2, near-miss: заряд катушек гаснет с короткой искрой.
  VoltFx.nearMiss = function nearMiss() {
    for (const c of coils) {
      const h = coilHead(c);
      for (let i = 0; i < 3; i++) {
        const a = Math.random() * Math.PI * 2;
        const d = 30 + Math.random() * 40;
        zap(h, { x: h.x + Math.cos(a) * d, y: h.y + Math.sin(a) * d }, i * 90);
      }
      c.inst.play('spin', false);
      c.inst.queue(winOn ? 'win' : 'off', true);
    }
  };

  VoltFx.arcToPlate = function arcToPlate(cellEl, plateEl) {
    // GDD: «джекпот-коин — разряд идёт к своей плашке»
    if (!plateEl) return;
    zap(center(cellEl), center(plateEl));
    zap(center(cellEl), center(plateEl), 160);
  };

  // GDD: «старт Hold & Win — разряд в рамку, рамка заряжается»; дверь сейфа
  // за барабанами проворачивается и заряжается (без перелёта в сейф).
  VoltFx.holdWinStart = function holdWinStart() {
    const frameEl = document.getElementById('cabinetFrame');
    const fr = frameEl.getBoundingClientRect();
    coilsPlay('discharge');
    const targets = [
      { x: fr.left + fr.width * 0.04, y: fr.top + fr.height * 0.06 },
      { x: fr.left + fr.width * 0.96, y: fr.top + fr.height * 0.06 },
      { x: fr.left + fr.width * 0.03, y: fr.top + fr.height * 0.5 },
      { x: fr.left + fr.width * 0.97, y: fr.top + fr.height * 0.5 },
    ];
    for (const c of coils) {
      const h = coilHead(c);
      const near = targets.filter((t) => Math.abs(t.x - h.x) < fr.width * 0.6);
      (near.length ? near : targets).forEach((t, i) => {
        zap(h, t, i * 90);
        zap(h, t, 260 + i * 90);
      });
    }
    frameInst.play('charge', false);
    frameInst.queue('bonus', true);
    if (doorInst) {
      doorInst.play('charge', false);
      doorInst.queue('bonus', true);
    }
    return true;
  };

  VoltFx.setMode = function setMode(next) {
    if (next === mode) return;
    mode = next;
    if (next === 'base') {
      frameInst.play(winOn ? 'win' : 'idle', true);
      if (doorInst) doorInst.play('idle', true);
      coilsRest();
    } else {
      const cur = frameInst.animationState.getCurrent(0);
      if (!cur || cur.animation.name !== 'charge') frameInst.play('bonus', true);
      const dcur = doorInst && doorInst.animationState.getCurrent(0);
      if (doorInst && (!dcur || dcur.animation.name !== 'charge')) doorInst.play('bonus', true);
    }
  };

  // Frame + logo + coils pulse while a win is on screen (GDD: «пульсация при выигрыше»).
  VoltFx.setWin = function setWin(on) {
    if (on === winOn) return;
    winOn = on;
    if (mode === 'base') frameInst.play(on ? 'win' : 'idle', true);
    logoInst.play(on ? 'win' : 'idle', true);
    if (!anticOn && !bigOn) coilsRest();
  };

  // While the front canvas is lifted above the popup dim, everything on it but
  // the coils and arcs must read as dimmed too: base instances are tinted by
  // the stage, the win line (an overlay) is simply hidden.
  function lineAlpha() {
    if (lineInst) lineInst.skeleton.color.a = overDim ? 0 : 1;
  }

  function pushOverDim() {
    overDim += 1;
    document.body.classList.add('fx-over-dim');
    front.setBaseDim(true);
    lineAlpha();
  }

  function popOverDim() {
    overDim = Math.max(0, overDim - 1);
    if (overDim) return;
    document.body.classList.remove('fx-over-dim');
    front.setBaseDim(false);
    lineAlpha();
  }

  // GDD: «Big Win — дуги на пике счётчика». The coils sit above the dim for it.
  VoltFx.bigWin = function bigWin(on) {
    if (on === bigOn) return;
    bigOn = on;
    clearInterval(bigTimer);
    bigTimer = null;
    if (on) {
      pushOverDim();
      for (const c of coils) c.inst.play('bigwin', true);
      const frameEl = document.getElementById('cabinetFrame');
      const fire = () => {
        const fr = frameEl.getBoundingClientRect();
        for (const c of coils) {
          const h = coilHead(c);
          const tx = h.x < fr.left + fr.width / 2 ? fr.left + fr.width * 0.03 : fr.left + fr.width * 0.97;
          zap(h, { x: tx, y: fr.top + fr.height * (0.15 + Math.random() * 0.7) });
        }
      };
      setTimeout(fire, 450);
      bigTimer = setInterval(fire, 700);
    } else {
      popOverDim();
      coilsRest();
    }
  };

  // GDD: «Grand 9/9 — полный разряд обеих катушек».
  VoltFx.grandDischarge = function grandDischarge() {
    pushOverDim();
    coilsPlay('discharge');
    const cells = Array.from(document.querySelectorAll('#reelGrid .reel__cell'));
    const plate = document.querySelector('.jp--grand');
    let i = 0;
    for (const c of coils) {
      const h = coilHead(c);
      for (const cell of cells) zap(h, center(cell), (i++ % 9) * 60);
      if (plate) zap(h, center(plate), 600);
    }
    frameInst.play('charge', false);
    frameInst.queue(mode === 'bonus' ? 'bonus' : 'idle', true);
    setTimeout(popOverDim, 1600);
  };

  VoltFx.setLights = function setLights(on) {
    // CSS hides both canvases; nothing should keep spawning arcs meanwhile.
    if (!on) {
      clearInterval(bigTimer);
      bigTimer = null;
    }
  };

  // Payline 1..5 — re-showing the line on screen keeps its loop running.
  VoltFx.showLine = function showLine(n) {
    if (n === lineShown && lineInst) return true;
    VoltFx.hideLine();
    if (!res.winlines.skeletonData.findAnimation(`line${n}_in`)) return false;
    lineInst = make('winlines', document.getElementById('reelWindow'));
    lineInst.play(`line${n}_in`, false);
    lineInst.queue(`line${n}_loop`, true);
    lineShown = n;
    lineAlpha();
    front.addOverlay(lineInst);
    return true;
  };

  VoltFx.hideLine = function hideLine() {
    if (lineInst) front.removeOverlay(lineInst);
    lineInst = null;
    lineShown = 0;
  };

  // A Spine copy of the tile plays its clip over the cell; the caller hides the
  // DOM <img> meanwhile. The skeleton's bounds ARE the cell (320x254 canvas).
  VoltFx.symbol = function symbol(cellEl, code) {
    if (!res.symbols.skeletonData.findAnimation(code)) return null;
    const inst = res.symbols.createInstance();
    inst.anchorEl = cellEl;
    inst.fit = 1;
    inst.play(code, false);
    front.addBase(inst);
    return inst;
  };

  VoltFx.dropSymbol = function dropSymbol(inst) {
    if (inst && front) front.removeBase(inst);
  };

  window.VoltFx = VoltFx;
})();
