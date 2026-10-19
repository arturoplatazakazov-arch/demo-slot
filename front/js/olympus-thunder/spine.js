// Olympus Thunder — Spine layer (skeletons built in code by
// scripts/olympus_thunder_spine.py into img/olympus-thunder/spine/).
//
//   #fxBack  (behind the temple)  bg: drifting cloud banks + far lightning
//   #fxMid   (behind the stage)   zeus rig, logo
//   #fxFront (over the stage)     symbol win clips, orbs (with their value
//            glyphs), discharge bursts, board strike, coin shower (lifted
//            over the dim while a popup is up: body.fx-over-dim)
//
// Every instance is anchored to a DOM element and fitted to the skeleton's
// own authored box, so CSS stays the single source of layout. If WebGL or an
// asset fails, OTSpine.ready stays false and the page keeps its PNG/CSS look.
(function () {
  const ROOT = 'img/olympus-thunder/spine';
  const V = '4';
  const SK = ['bg', 'zeus', 'logo', 'orb', 'symbols', 'fx', 'strike', 'shower'];
  const res = {};
  let back = null;
  let mid = null;
  let front = null;
  let bgInst = null;
  let zeusInst = null;
  let showerInst = null;
  let mode = 'base';
  const byEl = new Map(); // element -> [instances]

  const OTSpine = { ready: false };

  function load(stage, name) {
    return SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/${name}`, { premultipliedAlpha: true, version: V })
      .then((r) => { res[name] = r; return r; });
  }

  function make(name, anchorEl) {
    const r = res[name];
    const inst = r.createInstance();
    const sd = r.skeletonData;
    inst.anchorEl = anchorEl;
    inst.fit = 1;
    inst.boundsOverride = { x: sd.x, y: sd.y, width: sd.width, height: sd.height };
    return inst;
  }

  function track(el, inst) {
    if (!byEl.has(el)) byEl.set(el, []);
    byEl.get(el).push(inst);
  }

  function drop(stage, inst) {
    stage.removeBase(inst);
    stage.removeOverlay(inst);
  }

  // A fixed-position stand-in with the element's current rect: effects that
  // outlive their cell (the cell is removed mid-burst) anchor to this.
  function proxy(el, ms) {
    const r = el.getBoundingClientRect();
    const p = document.createElement('div');
    p.style.cssText = `position:fixed;left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;pointer-events:none;visibility:hidden`;
    document.body.appendChild(p);
    setTimeout(() => p.remove(), ms);
    return p;
  }

  function bgFit() {
    if (!bgInst) return;
    const s = document.getElementById('screen');
    bgInst.fitMode = s.clientWidth / s.clientHeight > 1920 / 1080 ? 'width' : 'height';
  }

  OTSpine.load = function () {
    if (!window.spine || !window.SpineEngine) return Promise.resolve(false);
    try {
      back = new SpineEngine.SpineStage(document.getElementById('fxBack'));
      mid = new SpineEngine.SpineStage(document.getElementById('fxMid'));
      front = new SpineEngine.SpineStage(document.getElementById('fxFront'));
    } catch (err) {
      console.warn('[ot-spine] no WebGL — PNG/CSS fallback', err);
      return Promise.resolve(false);
    }
    // rigs a design variant switched off (data-spine-*="off") are not fetched
    const on = (k) => document.body.dataset[k] !== 'off';
    const jobs = [load(front, 'fx'), load(front, 'strike'), load(front, 'shower')];
    if (on('spineBg')) jobs.push(load(back, 'bg'));
    if (on('spineZeus')) jobs.push(load(mid, 'zeus'));
    if (on('spineLogo')) jobs.push(load(front, 'logo'));
    if (on('spineSymbols')) jobs.push(load(front, 'orb'), load(front, 'symbols'));
    return Promise.all(jobs).then(() => {
      if (res.zeus) res.zeus.animationStateData.defaultMix = 0.22;
      if (res.orb) res.orb.animationStateData.defaultMix = 0.12;
      // <body data-spine-bg="off">: the v1 painted clouds/lightning stay out
      if (document.body.dataset.spineBg !== 'off') {
        bgInst = make('bg', document.getElementById('screen'));
        bgFit();
        bgInst.play('idle', true);
        back.addBase(bgInst);
      }

      // design variants with their own hero / logo art opt out of the v1
      // rigs: <body data-spine-zeus="off" data-spine-logo="off">
      const opts = document.body.dataset;
      if (opts.spineZeus !== 'off') {
        zeusInst = make('zeus', document.getElementById('zeus'));
        zeusInst.play('idle', true);
        mid.addBase(zeusInst);
        document.body.classList.add('spine-zeus');
      }
      if (opts.spineLogo !== 'off') {
        // the logo lives on the FRONT canvas: the temple columns are drawn in
        // front of the mid canvas (Zeus) and would otherwise cover it
        const logo = make('logo', document.getElementById('logo'));
        logo.play('idle', true);
        front.addBaseBehindAll(logo);
        document.body.classList.add('spine-logo');
      }
      // the symbol win clips / orb rig carry v1 symbol art
      if (opts.spineSymbols !== 'off') document.body.classList.add('spine-symbols');
      OTSpine.ready = true;
      return true;
    }).catch((err) => {
      console.warn('[ot-spine] assets failed — PNG/CSS fallback', err);
      return false;
    });
  };

  OTSpine.relayout = bgFit;

  OTSpine.setMode = function (m) {
    mode = m;
    if (bgInst) bgInst.play(m === 'fs' ? 'fs' : 'idle', true);
  };

  OTSpine.zeus = function (anim) {
    if (!zeusInst) return false;
    if (anim === 'idle') {
      zeusInst.play('idle', true);
      return true;
    }
    const known = ['orb', 'big_mult', 'fs', 'jackpot', 'bigwin'];
    if (!known.includes(anim)) return false;
    zeusInst.play(anim, false);
    zeusInst.queue('idle', true, 0);
    return true;
  };

  // ---- cells ---------------------------------------------------------------
  OTSpine.releaseCell = function (el) {
    const list = byEl.get(el);
    if (!list) return;
    for (const inst of list) drop(front, inst);
    byEl.delete(el);
    el.classList.remove('is-spine', 'is-spine-orb');
  };

  OTSpine.clearWins = function () {
    for (const [el, list] of byEl) {
      const keep = [];
      for (const inst of list) {
        if (inst._kind === 'win') drop(front, inst);
        else keep.push(inst);
      }
      if (keep.length) byEl.set(el, keep);
      else byEl.delete(el);
    }
  };

  const v1Symbols = () => document.body.dataset.spineSymbols !== 'off';

  OTSpine.symbolWin = function (el, code) {
    if (!OTSpine.ready || !code || !v1Symbols()) return false;
    if (code.startsWith('orb_')) {
      // an orb "wins" by charging
      OTSpine.orbCharge(el);
      return false;
    }
    const anim = `win_${code}`;
    if (!res.symbols.skeletonData.findAnimation(anim)) return false;
    const list = byEl.get(el) || [];
    for (const i of list.filter((x) => x._kind === 'win')) drop(front, i);
    byEl.set(el, list.filter((x) => x._kind !== 'win'));
    const inst = make('symbols', el);
    inst._kind = 'win';
    // rares are drawn 10% larger on the board (see the stylesheets)
    if (['helmet', 'lyre', 'amphora', 'wreath'].includes(code)) inst.fit = 1.1;
    inst.play(anim, false);
    front.addBase(inst);
    track(el, inst);
    el.classList.add('is-spine');
    return true;
  };

  OTSpine.mountOrb = function (el, value) {
    if (!OTSpine.ready || !v1Symbols() || (byEl.get(el) || []).some((i) => i._kind === 'orb')) return;
    const inst = make('orb', el);
    inst._kind = 'orb';
    const text = `x${value}`;
    const n = text.length;
    for (let i = 0; i < n; i++) inst.skeleton.setAttachment(`n${n}_${i}`, `g_${text[i]}`);
    inst.play('land', false);
    inst.queue('idle', true, 0);
    front.addBase(inst);
    track(el, inst);
    el.classList.add('is-spine-orb');
  };

  function orbOf(el) {
    return (byEl.get(el) || []).find((i) => i._kind === 'orb');
  }

  OTSpine.orbCharge = function (el) {
    const o = orbOf(el);
    if (!o) return;
    o.play('charge', false);
  };

  OTSpine.fadeOrb = function (el) {
    const o = orbOf(el);
    if (!o) return false;
    o.play('fade', false);
    return true;
  };

  OTSpine.orbLand = function () {};

  OTSpine.burst = function (el) {
    if (!OTSpine.ready) return;
    const p = proxy(el, 700);
    const inst = make('fx', p);
    inst.play('burst', false);
    inst.onSettle = () => drop(front, inst);
    front.addBase(inst);
  };

  OTSpine.zap = function (_from, target) {
    if (!OTSpine.ready) return;
    const p = proxy(target, 700);
    const inst = make('fx', p);
    inst.fit = 0.8;
    inst.play('burst', false);
    inst.onSettle = () => drop(front, inst);
    front.addOverlay(inst);
  };

  OTSpine.strike = function () {
    if (!OTSpine.ready) return;
    const inst = make('strike', document.getElementById('board'));
    inst.play('strike', false);
    inst.onSettle = () => drop(front, inst);
    front.addOverlay(inst);
  };

  // coin shower over the win popups (canvas lifted above the dim; board
  // content on the same canvas is darkened in-shader meanwhile)
  OTSpine.celebrate = function (kind) {
    if (!OTSpine.ready) return;
    const on = kind && ['big', 'mega', 'epic', 'total', 'jackpot'].includes(kind);
    if (on && !showerInst) {
      showerInst = make('shower', document.getElementById('screen'));
      showerInst.fitMode = 'width';
      showerInst.play('loop', true);
      front.addOverlay(showerInst);
      front.setBaseDim(true);
      document.body.classList.add('fx-over-dim');
    } else if (!on && showerInst) {
      drop(front, showerInst);
      showerInst = null;
      front.setBaseDim(false);
      document.body.classList.remove('fx-over-dim');
    }
  };

  window.OTSpine = OTSpine;
})();
