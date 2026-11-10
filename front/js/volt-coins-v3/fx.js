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
  const ROOT = 'img/volt-coins-v3/fx';
  // Версия atlas/json скелетов — поднимать при каждой пересборке fx
  // (PNG-страницы версионируются хешем в самом атласе).
  const FX_V = 51;
  const BOX = {
    bg_desk: { x: -899, y: -437.5, width: 1798, height: 875 },
    bg_mob: { x: -465.5, y: -845, width: 931, height: 1690 },
    coil: { x: -283, y: -540, width: 566, height: 1080 },
    frame: { x: -435, y: -347, width: 870, height: 694 },
    logo: { x: -620, y: -186, width: 1240, height: 372 },
    winlines: { x: -383, y: -302, width: 766, height: 604 },
    cellbolt: { x: -165, y: -150, width: 330, height: 300 },
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
  let cellInsts = [];   // V3: молния по периметру выигрышных ячеек
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
    // V3 деск: фон из макета дизайнера — у него своя дверь, Spine-подсветка
    // старого фона на нём не ложится; только портрет.
    if (true) {   // V3: и на мобиле фон макета
      if (doorInst) back.removeBase(doorInst);
      doorInst = null;
      doorVariant = null;
      return;
    }
    const v = 'bg_mob';
    if (v === doorVariant || !res[v]) return;
    if (doorInst) back.removeBase(doorInst);
    doorVariant = v;
    doorInst = make(v, document.getElementById('bgAnchor'));
    doorInst.play(mode === 'bonus' ? 'bonus' : 'idle', true);
    back.addBase(doorInst);
  }

  // --- V3: молнии дизайнера на катушках ------------------------------------------
  // В PSB у каждой вышки две картинки разряда (скрытые слои flash / flash2):
  // веер молний над головой и вся катушка в разрядах. Вместо Spine-свечения
  // катушки они вспыхивают ПОПЕРЕМЕННО (динамика). Объект повторяет нужный
  // кусок API Spine-инстанса (play / queue / animationState), так что все
  // вызовы coilsPlay / coilsRest / coinLanded работают как раньше.
  // Коробки картинок — в долях коробки катушки, по координатам PSB.
  const FLASH_BOX = {
    l: { flash: [-34.55, -43.13, 169.09, 86.72], flash2: [-60.61, -69.69, 226.67, 161.72] },
    r: { flash: [-38.37, -43.13, 168.58, 86.72], flash2: [-65.86, -69.69, 225.98, 161.72] },
  };
  // клип Spine → [длительность вспышки, пауза между вспышками (луп), яркость]
  const FLASH_CLIP = {
    spin: [420, 0, 0.85], charge: [700, 0, 0.9], discharge: [650, 0, 1],
    charged: [300, 240, 0.9], win: [460, 1100, 0.75], bigwin: [300, 200, 1],
  };
  function makeCoilFlash(el, side) {
    const box = document.createElement('div');
    box.className = 'v3-flash';
    const imgs = ['flash', 'flash2'].map((name) => {
      const img = document.createElement('img');
      img.src = `img/volt-coins-v3/v3/${name}_${side}.webp`;
      img.alt = '';
      const [l, t, w, h] = FLASH_BOX[side][name];
      Object.assign(img.style, { left: `${l}%`, top: `${t}%`, width: `${w}%`, height: `${h}%` });
      box.appendChild(img);
      return img;
    });
    el.after(box);
    const place = () => Object.assign(box.style, {
      left: `${el.offsetLeft}px`, top: `${el.offsetTop}px`, width: `${el.offsetWidth}px`, height: `${el.offsetHeight}px`,
    });
    let turn = Math.random() < 0.5 ? 0 : 1;
    let loopTimer = null;
    let queued = null;
    let busyUntil = 0;
    const flash = (dur, peak, both = false) => {
      if (document.body.classList.contains('lights-off')) return;
      place();
      const pick = both ? imgs : [imgs[turn]];
      turn = 1 - turn;
      for (const img of pick) {
        img.animate([
          { opacity: 0 }, { opacity: peak, offset: 0.12 }, { opacity: peak * 0.45, offset: 0.3 },
          { opacity: peak, offset: 0.45 }, { opacity: 0 },
        ], { duration: dur, easing: 'ease-out' });
      }
    };
    const stop = () => { clearTimeout(loopTimer); loopTimer = null; };
    const inst = {
      animationState: { getCurrent: () => null },
      play(clip, loop = false) {
        stop();
        queued = null;
        const c = FLASH_CLIP[clip];
        if (!c) { busyUntil = 0; return; }        // 'off' и прочее — тишина
        const [dur, gap, peak] = c;
        if (loop && gap) {
          const tick = () => { flash(dur, peak); loopTimer = setTimeout(tick, dur + gap * (0.7 + Math.random() * 0.6)); };
          tick();
          busyUntil = Infinity;
          return;
        }
        flash(dur, peak, clip === 'discharge');
        busyUntil = performance.now() + dur;
        loopTimer = setTimeout(() => {
          loopTimer = null;
          if (queued) { const [qc, ql] = queued; queued = null; inst.play(qc, ql); }
        }, dur);
      },
      isBusy: () => performance.now() < busyUntil,
      queue(clip, loop = false) {
        if (performance.now() < busyUntil && loopTimer) queued = [clip, loop];
        else inst.play(clip, loop);
      },
    };
    window.addEventListener('resize', place);
    place();
    return inst;
  }

  // --- coils -------------------------------------------------------------------

  function coilIdle(c) {
    c.inst.play('off', true);
    // the two coils spark at different moments, never in sync
    const e = c.inst.animationState.getCurrent(0);
    if (e) e.trackTime = c.phase;
  }

  // V2: разряд катушки подсвечивает фон вокруг неё — мягкая голубая вспышка,
  // гаснет за ~0.9 с. DOM-слой под сценой (над фоном), без Spine.
  function bgFlash(c, strength = 1) {
    if (document.body.classList.contains('lights-off')) return;
    const scr = document.getElementById('screen');
    if (!scr || !c) return;
    const sr = scr.getBoundingClientRect();
    const r = c.el.getBoundingClientRect();
    const h = coilHead(c);
    const d = document.createElement('div');
    d.className = 'bg-flash';
    const size = Math.max(r.width, r.height) * 1.6;
    Object.assign(d.style, {
      left: `${h.x - sr.left - size / 2}px`, top: `${h.y - sr.top - size * 0.35}px`,
      width: `${size}px`, height: `${size}px`, '--flash-a': String(0.55 * strength),
    });
    scr.appendChild(d);
    setTimeout(() => d.remove(), 1000);
  }
  function flashCoils(strength = 1) { for (const c of coils) bgFlash(c, strength); }

  // V3: фон тёмный (виньетка V2) и иногда подсвечивается ОТ ИСКР: раз в
  // 4–8 с одна из катушек коротко искрит (клип spin + пара мелких дуг у
  // головы), и вокруг неё из темноты проступает сам фон — та же картинка,
  // ярче, под радиальной маской, ровно поверх фона (его прямоугольник берём
  // у #bgLayer: на деске он не cover). Во время выигрыша/антиципации — нет.
  let ambientTimer = null;
  function ambientGlow() {
    // бонус (2026-11-09): катушки искрят заметно чаще, без «проявления» фона —
    // в бонусе фон и так почти не затемнён
    const bonus = mode === 'bonus';
    clearTimeout(ambientTimer);
    ambientTimer = setTimeout(ambientGlow, bonus ? 900 + Math.random() * 1300 : 4000 + Math.random() * 4000);
    if (document.hidden || document.body.classList.contains('lights-off')) return;
    if (bigOn || !coils.length) return;
    if (bonus) { bonusSpark(); return; }
    if (winOn || anticOn) return;
    const scr = document.getElementById('screen');
    const bg = document.getElementById('bgLayer');
    if (!scr || !bg) return;
    const c = coils[Math.floor(Math.random() * coils.length)];
    const sr = scr.getBoundingClientRect();
    const br = bg.getBoundingClientRect();
    const h = coilHead(c);
    // искра на катушке + жужжание электричества
    c.inst.play('spin', false);
    if (window.Sound) Sound.playSfx('coilBuzz');
    c.inst.queue('off', true);
    for (let i = 0; i < 2 + Math.floor(Math.random() * 2); i++) {
      const ang = Math.random() * Math.PI * 2;
      const dist = 26 + Math.random() * 34;
      zap(h, { x: h.x + Math.cos(ang) * dist, y: h.y + Math.sin(ang) * dist * 0.6 }, i * 110);
    }
    bgFlash(c, 0.7);
    // фон проступает вокруг искрящей катушки
    const size = Math.max(sr.width, sr.height) * (0.4 + Math.random() * 0.15);
    const x = h.x - sr.left;
    const y = h.y - sr.top + size * 0.12;
    const d = document.createElement('div');
    d.className = 'bg-reveal';
    d.style.backgroundImage = `url("${bg.currentSrc || bg.src}")`;
    d.style.backgroundSize = `${br.width}px ${br.height}px`;
    d.style.backgroundPosition = `${br.left - sr.left}px ${br.top - sr.top}px`;
    const m = `radial-gradient(${size / 2}px ${size / 2}px at ${x}px ${y}px, #000 0%, rgba(0,0,0,0.55) 45%, transparent 100%)`;
    d.style.webkitMaskImage = m;
    d.style.maskImage = m;
    d.style.setProperty('--reveal-a', (0.8 + Math.random() * 0.2).toFixed(2));
    scr.appendChild(d);
    setTimeout(() => d.remove(), 2600);
  }

  function bonusSpark() {
    const free = coils.filter((c) => !(c.inst.isBusy && c.inst.isBusy()));
    if (!free.length) return;
    // иногда обе катушки разом
    const pick = free.length > 1 && Math.random() < 0.3 ? free : [free[Math.floor(Math.random() * free.length)]];
    for (const c of pick) {
      const h = coilHead(c);
      c.inst.play('spin', false);
      c.inst.queue('off', true);
      const n = 3 + Math.floor(Math.random() * 3);
      for (let i = 0; i < n; i++) {
        const ang = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.7;
        const dist = 30 + Math.random() * 50;
        zap(h, { x: h.x + Math.cos(ang) * dist, y: h.y + Math.sin(ang) * dist * 0.7 }, i * 90);
      }
      bgFlash(c, 0.6);
    }
    if (window.Sound && Math.random() < 0.35) Sound.playSfx('coilBuzz');
  }

  function coilsPlay(clip, loop = false, thenIdle = true) {
    if (clip !== 'off') flashCoils(clip === 'spin' ? 0.6 : 1);
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
  // слот скелета arc (без цифр) → цвет 0..1 в бонусе
  // вариант C «Золото монет» (выбран 2026-11-10 на странице анимаций)
  const BONUS_ARC_TINT = {
    glow: [0.96, 0.7, 0.24], bolt: [1, 0.92, 0.66], src: [1, 0.78, 0.45],
    hitdot: [1, 0.78, 0.45], hitflare: [1, 0.94, 0.75], headdot: [1, 0.78, 0.45], headflare: [1, 0.94, 0.75],
  };
  function zap(a, b, delay = 0, clip = 'zap') {
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
      // бонус (проба 2026-11-10): молнии жёлтые — цвет слотов перекрашиваем
      // после каждого apply (таймлайны клипа пишут только альфу поверх setup)
      const tint = mode === 'bonus' ? BONUS_ARC_TINT : null;
      inst.update = (delta, canvasEl) => {
        place();
        update(delta, canvasEl);
        if (tint) {
          for (const sl of sk.slots) {
            const c = tint[sl.data.name.replace(/\d+$/, '')];
            if (c) { sl.color.r = c[0]; sl.color.g = c[1]; sl.color.b = c[2]; }
          }
        }
      };
      inst.play(clip, false);
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
      load(front, 'cellbolt'),
      load(front, 'symbols'),
    ]).then(() => {
      VoltFx.ready = true;
      mountDoor();
      frameInst = make('frame', document.getElementById('cabinetFrame'));
      frameInst.play('idle', true);
      frameLampsOn = false;   // V3: рама макета без ламп V2
      if (frameLampsOn) front.addBase(frameInst);
      logoInst = make('logo', document.querySelector('.logo__img'));
      logoInst.play('idle', true);
      front.addBase(logoInst);
      [['coilLeft', 0], ['coilRight', 3.4]].forEach(([id, phase]) => {
        const el = document.getElementById(id);
        if (!el) return;
        // V3: вместо Spine-свечения — попеременные молнии дизайнера (DOM)
        const v3 = document.body.classList.contains('v3');
        const c = { el, phase, inst: v3 ? makeCoilFlash(el, id === 'coilLeft' ? 'l' : 'r') : make('coil', el) };
        coils.push(c);
        coilIdle(c);
        if (!v3) front.addOverlay(c.inst);
      });
      document.body.classList.add('fx-ready');
      if (document.body.classList.contains('v3')) loadSymFx();
      ambientTimer = setTimeout(ambientGlow, 2500);
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
    if (window.Sound && Sound.stopSfx) Sound.stopSfx('coilBuzz');
    // GDD: «нажатие спина — короткий заряд ~0.5 с»
    if (anticOn || bigOn) return;
    coilsPlay('spin');
  };

  VoltFx.spinStop = function spinStop() {};

  VoltFx.anticipation = function anticipation(on) {
    if (on === anticOn) return;
    anticOn = on;
    if (on) {
      // в антиципации — только её мелодия, без треска искры катушки
      if (window.Sound && Sound.stopSfx) Sound.stopSfx('coilBuzz');
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
    // V3: молния всегда уходит в саму вышку (продукт), и на мобиле тоже
    if (document.body.classList.contains('v3')) return h;
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
    // V3 (продукт): разряд идёт С монеты В вышку
    zap(p, zapFrom(c, p));
    bgFlash(c, 0.8);
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
      bgFlash(c, 0.5);
    }
  };

  // Разряд монета ↔ катушка (2026-11-06, продукт; сцены на странице анимаций):
  // молния бежит клипом arc `travel` (голова-искра ведёт ствол, попадание в
  // TRAVEL_HIT_MS), катушка искрит — вспышки discharge + короткие разряды
  // вокруг головы. База: монета → катушка; Hold & Win: катушка → монета.
  const TRAVEL_HIT_MS = 300;
  const SPARK_LEAD_MS = 350;
  function coilSparks(c) {
    const h = coilHead(c);
    bgFlash(c, 1);
    if (!anticOn && !bigOn) {
      c.inst.play('discharge', false);
      c.inst.queue(winOn ? 'win' : 'off', true);
    }
    for (let i = 0; i < 4; i++) {
      const a = Math.random() * Math.PI * 2;
      const d = 28 + Math.random() * 36;
      zap(h, { x: h.x + Math.cos(a) * d, y: h.y + Math.sin(a) * d }, i * 90);
    }
  }
  const hasTravel = () => res.arc && res.arc.skeletonData.findAnimation('travel');

  VoltFx.coinToCoil = function coinToCoil(cellEl) {
    const p = center(cellEl);
    const c = nearestCoil(p);
    if (!c) return;
    if (!hasTravel()) { VoltFx.coinLanded(cellEl); return; }
    zap(p, coilHead(c), 0, 'travel');
    setTimeout(() => coilSparks(c), TRAVEL_HIT_MS);
  };

  // onHit — когда молния попала в монету (там slot.js запускает её выигрыш)
  VoltFx.coilToCoin = function coilToCoin(cellEl, onHit) {
    const p = center(cellEl);
    const c = nearestCoil(p);
    if (!c || !hasTravel()) { VoltFx.coinLanded(cellEl); if (onHit) onHit(); return; }
    coilSparks(c);
    zap(coilHead(c), p, SPARK_LEAD_MS, 'travel');
    if (onHit) setTimeout(onHit, SPARK_LEAD_MS + TRAVEL_HIT_MS);
  };

  // Hold & Win (2026-11-09): новая монета после своего выигрыша бьёт молнией
  // в табличку респинов; onHit — табличка заполняется (slot.js).
  VoltFx.coinToCounter = function coinToCounter(cellEl, counterEl, onHit) {
    if (!counterEl || !hasTravel()) return false;
    const p = center(cellEl);
    const q = center(counterEl);
    zap(p, q, 0, 'travel');
    setTimeout(() => {
      for (let i = 0; i < 4; i++) {
        const a = Math.random() * Math.PI * 2;
        const d = 22 + Math.random() * 26;
        zap(q, { x: q.x + Math.cos(a) * d * 1.6, y: q.y + Math.sin(a) * d * 0.7 }, i * 60);
      }
      if (onHit) onHit();
    }, TRAVEL_HIT_MS);
    return true;
  };

  // Респин без монеты (2026-11-10): молния обегает по кромке синюю ячейку
  // гаснущей цифры — верх → правый край → низ → левый край (клип arc `travel`).
  // Ячейки — замер синих полей в v3/respins_h.png (мобила, 424x89) и
  // v3/respins.png (деск, 148x388): [left, top, width, height] в px картинки.
  const RESP_CELLS = {
    h: { w: 424, h: 89, cells: [[11, 12, 113, 61], [155, 12, 113, 61], [299, 12, 113, 61]] },
    v: { w: 148, h: 388, cells: [[17, 53, 111, 61], [17, 160, 111, 61], [17, 267, 111, 61]] },
  };
  const EDGE_LAP_MS = [0, 210, 330, 540];   // старт каждой стороны (длинные — дольше)
  VoltFx.counterTick = function counterTick(digitEl) {
    if (!digitEl || !hasTravel()) return;
    const plate = digitEl.closest('.v3resp');
    if (!plate) return;
    const artH = plate.querySelector('.v3resp__art--h');
    const spec = artH && getComputedStyle(artH).display !== 'none' ? RESP_CELLS.h : RESP_CELLS.v;
    const cell = spec.cells[Number(digitEl.dataset.n) - 1];
    if (!cell) return;
    const r = plate.getBoundingClientRect();
    const kx = r.width / spec.w;
    const ky = r.height / spec.h;
    const x0 = r.left + cell[0] * kx;
    const y0 = r.top + cell[1] * ky;
    const x1 = x0 + cell[2] * kx;
    const y1 = y0 + cell[3] * ky;
    const corners = [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }];
    for (let i = 0; i < 4; i++) zap(corners[i], corners[(i + 1) % 4], EDGE_LAP_MS[i], 'travel');
  };

  // Сбор монет (2026-11-10): обе катушки бьют молнией в точку, где слились
  // монеты, вокруг — венец коротких разрядов. В бонусе цвет — золото (zap).
  VoltFx.collectBurst = function collectBurst(p, r = 90) {
    for (const c of coils) {
      coilSparks(c);
      if (hasTravel()) zap(coilHead(c), p, SPARK_LEAD_MS, 'travel');
    }
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2 + Math.random() * 0.3;
      const d = r * (0.9 + Math.random() * 0.5);
      zap({ x: p.x + Math.cos(a) * r * 0.45, y: p.y + Math.sin(a) * r * 0.45 },
        { x: p.x + Math.cos(a) * d, y: p.y + Math.sin(a) * d }, SPARK_LEAD_MS + TRAVEL_HIT_MS + i * 25);
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
  // 2026-11-10: молния по кругу рамы слота. Две молнии бегут по середине хромового
  // бортика из противоположных углов по часовой (как неон в желобе), каждая сторона —
  // клип arc `travel`; цвет — как у остальных разрядов (в бонусе золото).
  // Бортик рамы 698x639, окно барабанов с отступом 19 — молния идёт на 9,5 от края.
  const FRAME_BAND = { w: 698, h: 639, inset: 9.5 };
  const FRAME_LAP_MS = [0, 250, 480, 730];     // старт каждой стороны (длинные дольше)
  function frameLap(delay = 0, laps = 1) {
    const frameEl = document.getElementById('cabinetFrame');
    if (!frameEl || !hasTravel()) return 0;
    const r = frameEl.getBoundingClientRect();
    const ix = (FRAME_BAND.inset / FRAME_BAND.w) * r.width;
    const iy = (FRAME_BAND.inset / FRAME_BAND.h) * r.height;
    const p = [
      { x: r.left + ix, y: r.top + iy }, { x: r.right - ix, y: r.top + iy },
      { x: r.right - ix, y: r.bottom - iy }, { x: r.left + ix, y: r.bottom - iy },
    ];
    const lapMs = FRAME_LAP_MS[3] + 260;
    for (let l = 0; l < laps; l++) {
      for (const start of [0, 2]) {           // из левого верхнего и из правого нижнего
        for (let i = 0; i < 4; i++) {
          const a = p[(start + i) % 4];
          const b = p[(start + i + 1) % 4];
          zap(a, b, delay + l * lapMs + FRAME_LAP_MS[i], 'travel');
        }
      }
    }
    // искры по углам, когда молнии проходят их
    p.forEach((c, i) => setTimeout(() => {
      for (let k = 0; k < 2; k++) {
        const ang = Math.random() * Math.PI * 2;
        zap(c, { x: c.x + Math.cos(ang) * 26, y: c.y + Math.sin(ang) * 26 }, k * 60);
      }
    }, delay + FRAME_LAP_MS[i] + 240));
    return delay + laps * lapMs;
  }
  VoltFx.frameLap = (delay, laps) => frameLap(delay, laps);

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
    // молния обегает раму, как только разряды катушек в неё попали
    frameLap(220);
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
      // бонус: частые искры катушек начинаются сразу, не через 4–8 с
      clearTimeout(ambientTimer);
      ambientTimer = setTimeout(ambientGlow, 700);
      const cur = frameInst.animationState.getCurrent(0);
      if (!cur || cur.animation.name !== 'charge') frameInst.play('bonus', true);
      const dcur = doorInst && doorInst.animationState.getCurrent(0);
      if (doorInst && (!dcur || dcur.animation.name !== 'charge')) doorInst.play('bonus', true);
    }
  };

  // V2 «Рама: Неон» — Spine-лампы старой рамы не показываем (review.js).
  let frameLampsOn = true;
  VoltFx.frameLamps = function frameLamps(on) {
    if (frameInst && on !== frameLampsOn) {
      if (on) front.addBase(frameInst);
      else front.removeBase(frameInst);
    }
    frameLampsOn = on;
  };

  // Frame + logo + coils pulse while a win is on screen (GDD: «пульсация при выигрыше»).
  VoltFx.setWin = function setWin(on) {
    if (on === winOn) return;
    winOn = on;
    document.body.classList.toggle('fx-win', on);
    if (mode === 'base') frameInst.play(on ? 'win' : 'idle', true);
    logoInst.play(on ? 'win' : 'idle', true);
    if (!anticOn && !bigOn) coilsRest();
  };

  // While the front canvas is lifted above the popup dim, everything on it but
  // the coils and arcs must read as dimmed too: base instances are tinted by
  // the stage, the win line (an overlay) is simply hidden.
  function lineAlpha() {
    if (lineInst) lineInst.skeleton.color.a = overDim ? 0 : 1;
    for (const c of cellInsts) c.skeleton.color.a = overDim ? 0 : 1;
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
    // 9/9: два круга молнии по раме (в бонусе — золотые) перед попапом GRAND
    frameLap(150, 2);
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

  // V3: вместо линии — молния по периметру каждой выигрышной ячейки
  // (scripts/volt_coins_v3_cellbolt.py)
  VoltFx.showCells = function showCells(cells) {
    VoltFx.hideLine();
    cellInsts = cells.map((cell) => {
      const inst = make('cellbolt', cell);
      inst.play('in', false);
      inst.queue('loop', true);
      front.addOverlay(inst);
      return inst;
    });
    lineAlpha();
    return true;
  };

  VoltFx.hideLine = function hideLine() {
    for (const c of cellInsts) front.removeOverlay(c);
    cellInsts = [];
    if (lineInst) front.removeOverlay(lineInst);
    lineInst = null;
    lineShown = 0;
  };

  // A Spine copy of the tile plays its clip over the cell; the caller hides the
  // DOM <img> meanwhile. The skeleton's bounds ARE the cell (320x254 canvas).
  // V3: у каждого символа свой скелет с выбранным в лабе клипом 'win'
  // (scripts/volt_coins_v3_symbol_game.py → fx/sym_<code>, карта в sym.json).
  // Грузятся фоном после старта; пока не готов — CSS-пульс, как раньше.
  let symMap = null;
  function loadSymFx() {
    fetch(`${ROOT}/sym.json?v=${FX_V}`).then((r) => r.json()).then((m) => {
      symMap = m;
      [...new Set(Object.values(m.art))].forEach((c) => load(front, `sym_${c}`).catch(() => {}));
    }).catch(() => {});
  }

  VoltFx.symbol = function symbol(cellEl, code) {
    const sc = symMap && symMap.art[code];
    const r = sc && res[`sym_${sc}`];
    if (r) {
      const inst = r.createInstance();
      inst.anchorEl = cellEl;
      inst.fit = 1;
      inst.play('win', false);
      inst.durMs = Math.round((symMap.dur[sc] || 1.1) * 1000);
      front.addBase(inst);
      return inst;
    }
    if (sc) return null;
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
