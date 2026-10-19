// Olympus Thunder — session, layout, and the spin choreography.
//
// The server (app/api/v1/spin_tumble.py) resolves the whole spin; this file
// only plays it back from `data.tumble`:
//   drop the board -> for each tumble step: winners pulse, discharge, fall,
//   refill -> orbs: collect into the win plate (base) or the TOTAL
//   MULTIPLIER medallion (free spins) and multiply -> scatter pay / free-spins
//   award -> jackpot wheel -> win-tier popup.
(function () {
  // Design variants (olympus-thunder-v2/-v3 pages) share this script: the game
  // code, the design canvas and the art set come from the page itself —
  // <body data-game-id data-sky data-sky-fs data-temple data-frame> and the
  // --design-w / --design-h custom properties of its stylesheet.
  const BODY = document.body.dataset;
  const GAME_ID = BODY.gameId || 'olympus-thunder';
  const IMG = 'img/olympus-thunder/';
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => UI.fmt(n);

  const BAR_RESERVE_PORTRAIT = 170; // css px the V3 bar takes at the bottom
  const BAR_RESERVE_LANDSCAPE = 110; // its button row + readouts in landscape
  const TIER = { big: 15, mega: 50, epic: 150 }; // x bet
  const FALLBACK_RULES = null;

  const state = {
    sessionId: null,
    betSteps: [2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000],
    betIndex: 2,
    balance: 1_000_000,
    currency: 'FUN',
    busy: false,
    rules: FALLBACK_RULES,
    mode: 'base', // base | fs
    fsLeft: 0,
    totalMult: 1,
    autoLeft: 0,
    grid: null,
  };

  const START_GRID = [
    ['helmet', 'ruby', 'lyre', 'emerald', 'amphora', 'sapphire'],
    ['citrine', 'wreath', 'scatter', 'amethyst', 'ruby', 'lyre'],
    ['emerald', 'orb_5', 'helmet', 'citrine', 'eagle', 'wreath'],
    ['sapphire', 'amphora', 'ruby', 'lyre', 'amethyst', 'citrine'],
    ['wreath', 'emerald', 'sapphire', 'orb_25', 'helmet', 'ruby'],
  ];

  const bet = () => state.betSteps[state.betIndex];
  const isPortrait = () => window.matchMedia('(orientation: portrait)').matches;

  // ---------- layout ----------
  function fitStage() {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const css = getComputedStyle(document.documentElement);
    const d = {
      w: parseFloat(css.getPropertyValue('--design-w')) || (isPortrait() ? 1080 : 1920),
      h: parseFloat(css.getPropertyValue('--design-h')) || (isPortrait() ? 1700 : 1080),
    };
    // the slot is fitted to (and centred in) the screen ABOVE the V3 bar
    const usableH = vh - (isPortrait() ? BAR_RESERVE_PORTRAIT : BAR_RESERVE_LANDSCAPE);
    const scale = Math.min(vw / d.w, usableH / d.h);
    document.documentElement.style.setProperty('--stage-scale', String(scale));
    // spare height (a screen taller than the canvas) is split above and below
    // so the slot sits in the middle of the screen, not glued to the top
    const spare = Math.max(0, usableH - d.h * scale);
    document.getElementById('stage').style.top = `${Math.round(spare / 2)}px`;
    setArtForLayout();
    Board.relayout();
  }

  let lastPortrait = null;
  function setArtForLayout() {
    const p = isPortrait();
    if (p === lastPortrait) return;
    lastPortrait = p;
    // "<desktop>|<portrait>" art paths, or "none" to leave the layer empty
    const art = (id, key, dflt) => {
      const el = $(id);
      if (!el) return;
      const spec = BODY[key] || dflt;
      if (spec === 'none') { el.removeAttribute('src'); el.hidden = true; return; }
      const [desk, mob] = spec.split('|');
      el.src = IMG + (p ? (mob || desk) : desk);
    };
    art('skyBase', 'sky', 'bg/sky.jpg|bg/sky_mob.jpg');
    art('skyFs', 'skyFs', 'bg/sky_fs.jpg|bg/sky_fs_mob.jpg');
    art('temple', 'temple', 'bg/temple.webp|bg/temple_mob.webp');
    art('frame', 'frame', 'frame_desk.webp?v=2|frame_mob.webp?v=2');
    $('zeusFallback').src = IMG + (BODY.hero || 'hero.webp');
    if (window.OTSpine) OTSpine.relayout();
  }

  // ---------- readouts ----------
  function renderBet() {
    $('betValue').textContent = fmt(bet());
    if (state.rules && !$('infoPopup').hidden) UI.renderInfo(state.rules, bet(), state.currency);
    renderJackpots();
  }
  function renderBalance() {
    $('balanceValue').textContent = fmt(state.balance);
    document.querySelectorAll('.ui-balance__currency, .ui-bet-field__currency, .v3-readout__cur').forEach((el) => { el.textContent = state.currency; });
  }
  function renderJackpots() {
    const prizes = state.rules ? state.rules.jackpot.prizes : { mini: 20, minor: 50, major: 250, grand: 1000 };
    document.querySelectorAll('.jp').forEach((el) => {
      el.querySelector('.jp__val').textContent = fmt(prizes[el.dataset.tier] * bet());
    });
  }

  const plate = {
    reset() {
      $('winPlate').classList.remove('has-value');
      $('winPlateLabel').textContent = state.mode === 'fs' ? 'ВЫИГРЫШ БОНУСА' : `ВЫИГРЫШ ДО ${fmt(state.rules ? state.rules.max_win_multiplier : 10000)}×`;
      $('winPlateValue').textContent = '';
      if (state.mode === 'fs') this.set(state.fsWin || 0, 'ВЫИГРЫШ БОНУСА');
    },
    set(amount, label = 'ВЫИГРЫШ') {
      $('winPlate').classList.add('has-value');
      $('winPlateLabel').textContent = label;
      $('winPlateValue').textContent = fmt(amount);
      const p = $('winPlate');
      p.classList.remove('is-bump');
      void p.offsetWidth;
      p.classList.add('is-bump');
    },
    text(label, value) {
      $('winPlate').classList.add('has-value');
      $('winPlateLabel').textContent = label;
      $('winPlateValue').textContent = value;
    },
  };

  function setTotalMult(v, hit = false) {
    state.totalMult = v;
    $('totalMult').textContent = `×${v}`;
    if (hit) {
      const m = $('medallion');
      m.classList.remove('is-hit');
      void m.offsetWidth;
      m.classList.add('is-hit');
    }
  }

  function setMode(mode) {
    state.mode = mode;
    $('screen').dataset.mode = mode;
    if (window.OTSpine) OTSpine.setMode(mode);
    if (window.Sound) Sound.playMusic(mode === 'fs' ? 'fs' : 'base');
  }

  function flash() {
    const f = $('flash');
    f.classList.remove('is-on');
    void f.offsetWidth;
    f.classList.add('is-on');
  }

  // ---------- landing cues ----------
  let zeusCueAt = 0;
  function onLand(col, row, code) {
    const v = Board.orbValue(code);
    if (v) {
      Sound.thunder(v);
      flash();
      if (window.OTSpine) OTSpine.orbLand(col, row);
      if (performance.now() - zeusCueAt > 900) {
        zeusCueAt = performance.now();
        zeus(v >= 25 ? 'big_mult' : 'orb');
      }
    } else if (code === 'scatter') {
      Sound.playSfx('coin', { rate: 1.25, gain: 0.8 });
    } else if (code === 'eagle') {
      Sound.playSfx('coin', { rate: 0.8, gain: 0.8 });
    }
  }
  let dropSoundAt = 0;
  function dropCue() {
    if (performance.now() - dropSoundAt < 120) return;
    dropSoundAt = performance.now();
    Sound.playSfx('drop', { gain: 0.6 });
  }

  function zeus(anim) {
    if (window.OTSpine && OTSpine.zeus(anim)) return;
    const z = $('zeus');
    z.dataset.anim = anim;
    clearTimeout(z._t);
    z._t = setTimeout(() => { z.dataset.anim = 'idle'; }, 1600);
  }

  // ---------- orb collect ----------
  // Every orb's value flies into `targetEl`; resolves after the last lands.
  async function collectOrbs(orbs, targetEl, onEach) {
    const layer = $('flyLayer');
    const tr = targetEl.getBoundingClientRect();
    const tx = tr.left + tr.width / 2;
    const ty = tr.top + tr.height * 0.6;
    const stageScale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale')) || 1;
    let i = 0;
    for (const o of orbs) {
      const c = Board.cellCenter(o.el);
      const fly = document.createElement('div');
      fly.className = 'fly';
      fly.textContent = `x${o.value}`;
      fly.style.fontSize = `${Math.round(54 * stageScale)}px`;
      fly.style.transform = `translate(${c.x}px, ${c.y}px) translate(-50%, -50%) scale(1)`;
      layer.appendChild(fly);
      if (window.OTSpine) OTSpine.orbCharge(o.el);
      const delay = i * 260;
      i++;
      setTimeout(() => {
        fly.style.transition = 'transform 560ms cubic-bezier(.55,-0.25,.4,1.2), opacity 120ms linear 520ms';
        fly.style.transform = `translate(${tx}px, ${ty}px) translate(-50%, -50%) scale(.7)`;
        fly.style.opacity = '0';
      }, delay + 40);
      setTimeout(() => {
        fly.remove();
        if (!(window.OTSpine && OTSpine.fadeOrb(o.el))) o.el.classList.add('is-orb-fade');
        Sound.rise();
        if (window.OTSpine) OTSpine.zap(o.el, targetEl);
        onEach(o.value);
      }, delay + 600);
    }
    await new Promise((r) => setTimeout(r, (orbs.length - 1) * 260 + 760));
  }

  // ---------- one spin ----------
  async function playSpin(data, { isBuy = false } = {}) {
    const t = data.tumble;
    const betNow = bet();
    plate.reset();
    $('boardFx').innerHTML = '';
    Sound.playSfx('spinStart');
    await Board.dropOut();
    const landed = (c, r, code) => { dropCue(); onLand(c, r, code); };
    await Board.dropIn(data.grid, landed);

    let running = 0;
    for (const step of t.steps) {
      await Board.highlight(step.wins);
      running += step.step_win;
      plate.set(running, state.mode === 'fs' ? 'ВЫИГРЫШ СЕРИИ' : 'ВЫИГРЫШ');
      Sound.playSfx('smallWin');
      Board.combo(`+${fmt(step.step_win)}`);
      await Board.shatter(step.removed);
      await Board.collapse(step.grid_after, landed);
    }
    Board.clearMarks();

    // multiplier phase
    const orbs = Board.orbs();
    if (t.base_win > 0 && t.orb_sum > 0 && orbs.length) {
      zeus(t.orb_sum >= 25 ? 'big_mult' : 'orb');
      if (t.mode === 'base') {
        let sum = 0;
        await collectOrbs(orbs, $('winPlate'), (v) => {
          sum += v;
          plate.text(`${fmt(t.base_win)} ×`, `x${sum}`);
        });
        await Board.wait(300);
        plate.set(t.series_win, `ВЫИГРЫШ ×${t.orb_sum}`);
        Sound.thunder(t.orb_sum);
        flash();
      } else {
        let mult = t.total_multiplier_before;
        await collectOrbs(orbs, $('medallion'), (v) => {
          mult += v;
          setTotalMult(mult, true);
        });
        await Board.wait(250);
        plate.text(`${fmt(t.base_win)} ×`, `x${t.total_multiplier_after}`);
        await Board.wait(600);
        plate.set(t.series_win, `ВЫИГРЫШ СЕРИИ ×${t.total_multiplier_after}`);
        Sound.thunder(t.total_multiplier_after);
        flash();
      }
      await Board.wait(500);
    } else if (orbs.length) {
      Board.fadeOrbs(); // losing series: orbs fade (GDD §6.2 / §7.2)
    }

    // scatters
    if (t.scatter_win > 0 || t.free_spins_awarded > 0) {
      const sc = Board.cellsOf('scatter');
      sc.forEach((s) => s.el.classList.add('is-win'));
      if (window.OTSpine) sc.forEach((s) => OTSpine.symbolWin(s.el, 'scatter'));
      Sound.playSfx('scatter');
      zeus('fs');
      await Board.wait(1400);
      sc.forEach((s) => s.el.classList.remove('is-win'));
      if (t.scatter_win > 0 && !isBuy) plate.set(t.series_win + t.scatter_win, 'С УЧЁТОМ КОЛЕЦ');
    }

    // jackpot wheel
    if (t.jackpot) {
      const eg = Board.cellsOf('eagle');
      eg.forEach((s) => s.el.classList.add('is-win'));
      zeus('jackpot');
      await Board.wait(1200);
      eg.forEach((s) => s.el.classList.remove('is-win'));
      await UI.wheel(t.jackpot);
    }

    // win tier popup (jackpot already had its own)
    const spinWin = t.spin_win - (t.jackpot ? t.jackpot.amount : 0);
    const x = spinWin / betNow;
    if (x >= TIER.big) {
      zeus('bigwin');
      const kind = x >= TIER.epic ? 'epic' : x >= TIER.mega ? 'mega' : 'big';
      await UI.popup(kind, { amount: spinWin });
    }
    if (t.capped) plate.text('МАКСИМАЛЬНЫЙ ВЫИГРЫШ', `${fmt(state.rules ? state.rules.max_win_multiplier : 10000)}×`);
    return data;
  }

  // ---------- free spins ----------
  async function enterFreeSpins(kind, spins) {
    zeus('fs');
    await UI.popup(kind === 'super' ? 'super' : 'fs', { count: spins, sub: kind === 'super' ? 'СФЕРЫ В КАЖДОМ СПИНЕ' : 'ОБЩИЙ МНОЖИТЕЛЬ ОТ ×1' });
    UI.dim(true, true);
    await Board.wait(450);
    setMode('fs');
    state.fsWin = 0;
    setTotalMult(1);
    Sound.rise(true);
    $('fsLeft').textContent = spins;
    plate.reset();
    await Board.wait(500);
    UI.dim(false);
  }

  async function runFreeSpins() {
    while (state.fsLeft > 0) {
      await Board.wait(450);
      const data = await Api.spin(state.sessionId, bet());
      state.fsLeft = data.feature ? data.feature.spins_remaining : 0;
      $('fsLeft').textContent = Math.max(0, state.fsLeft - 0);
      await playSpin(data);
      state.balance = data.balance;
      renderBalance();
      state.fsWin = data.feature ? data.feature.total_win : state.fsWin;
      if (data.feature && data.feature.triggered && data.feature.spins_awarded) {
        await UI.popup('fs', { count: `+${data.feature.spins_awarded}`, sub: 'ДОПОЛНИТЕЛЬНЫЕ СПИНЫ', autoMs: 1200 });
      }
      $('fsLeft').textContent = state.fsLeft;
      plate.set(state.fsWin, 'ВЫИГРЫШ БОНУСА');
    }
    zeus('bigwin');
    await UI.popup('total', { amount: state.fsWin, sub: `ИТОГ БОНУСА · МНОЖИТЕЛЬ ×${state.totalMult}` });
    UI.dim(true, true);
    await Board.wait(450);
    setMode('base');
    plate.reset();
    await Board.wait(400);
    UI.dim(false);
  }

  // ---------- requests ----------
  function setBusy(on) {
    state.busy = on;
    document.body.classList.toggle('is-busy', on);
    document.querySelector('[data-action="spin"]').classList.toggle('is-spinning', on);
  }

  async function run(request, { isBuy = false, buyKind = null } = {}) {
    if (state.busy || !state.sessionId) return;
    setBusy(true);
    Board.setSpeed(document.getElementById('v3TurboBtn').classList.contains('is-active') ? 0.5 : 1);
    try {
      const data = await request();
      // balance: the bet / price leaves at once, the win lands after the show
      if (!isBuy) state.balance -= bet();
      else state.balance = data.balance - (data.total_win || 0);
      renderBalance();
      await playSpin(data, { isBuy });
      state.balance = data.balance;
      renderBalance();
      if (data.feature && data.feature.triggered && data.feature.spins_remaining > 0) {
        state.fsLeft = data.feature.spins_remaining;
        await enterFreeSpins(data.tumble.mode === 'super' || buyKind === 'super_free_spins' ? 'super' : 'fs', state.fsLeft);
        await runFreeSpins();
        state.autoLeft = 0;
      }
    } catch (err) {
      console.error('[olympus-thunder] spin failed', err);
    } finally {
      setBusy(false);
    }
    autoNext();
  }

  function spin() {
    if (state.busy) return;
    const b = bet();
    if (state.balance < b) return;
    run(() => Api.spin(state.sessionId, b));
  }

  // autoplay: the V3 chips set a count on the spin button
  function autoNext() {
    const badge = $('v3SpinCount');
    if (badge.hidden) return;
    const left = Number(badge.textContent) - 1;
    if (left <= 0 || state.balance < bet()) {
      badge.hidden = true;
      document.querySelector('.v3-spin').classList.remove('has-count');
      document.querySelectorAll('.v3-chip').forEach((c) => c.classList.remove('is-active'));
      return;
    }
    badge.textContent = String(left);
    setTimeout(spin, 350);
  }

  async function openBuy() {
    if (state.busy || state.mode !== 'base' || !state.rules) return;
    const products = state.rules.bonus_buy.products;
    if (!products.length) return;
    Sound.playSfx('popupOpen');
    const pick = await UI.buyWindow({
      products, betSteps: state.betSteps, betIndex: state.betIndex, balance: state.balance, currency: state.currency,
    });
    if (!pick) return;
    if (pick.betIndex !== state.betIndex) { state.betIndex = pick.betIndex; renderBet(); }
    const b = bet();
    run(() => Api.buyFeature(state.sessionId, pick.buyId, b), { isBuy: true, buyKind: pick.kind });
  }

  // ---------- wiring ----------
  function wire() {
    document.querySelector('[data-action="spin"]').addEventListener('click', () => {
      // a pending autoplay badge starts with this press
      spin();
    });
    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !e.repeat && document.activeElement.tagName !== 'INPUT') { e.preventDefault(); spin(); }
    });
    document.querySelector('[data-action="bet-minus"]').addEventListener('click', () => {
      if (state.busy || state.mode !== 'base') return;
      state.betIndex = Math.max(0, state.betIndex - 1);
      renderBet();
    });
    document.querySelector('[data-action="bet-plus"]').addEventListener('click', () => {
      if (state.busy || state.mode !== 'base') return;
      state.betIndex = Math.min(state.betSteps.length - 1, state.betIndex + 1);
      renderBet();
    });
    document.querySelector('[data-action="sound"]').addEventListener('click', () => Sound.toggleMuted());
    document.querySelectorAll('.ui-icon-btn, .ui-spin-btn').forEach((b) => b.addEventListener('click', () => Sound.playSfx('click')));
    $('buyBtn').addEventListener('click', openBuy);
    const info = $('infoPopup');
    document.querySelector('[data-action="info"]').addEventListener('click', () => {
      UI.renderInfo(state.rules, bet(), state.currency);
      info.hidden = false;
    });
    $('infoPopupClose').addEventListener('click', () => { info.hidden = true; });
    info.addEventListener('click', (e) => { if (e.target === info) info.hidden = true; });
    window.addEventListener('resize', fitStage);
  }

  async function startSession() {
    try {
      const data = await Api.startSession(GAME_ID);
      state.sessionId = data.session_id;
      state.balance = data.balance;
      state.currency = data.currency;
      state.rules = data.game_rules || null;
      if (data.bet && data.bet.steps && data.bet.steps.length) {
        state.betSteps = data.bet.steps;
        const i = state.betSteps.indexOf(data.bet.default);
        state.betIndex = i >= 0 ? i : Math.floor(state.betSteps.length / 2);
      }
      if (state.rules) UI.buildWheel(state.rules.jackpot.sectors, state.rules.jackpot.prizes);
      if (state.rules && !state.rules.bonus_buy.products.length) $('buyBtn').disabled = true;
    } catch (err) {
      console.error('[olympus-thunder] no session — spin disabled', err);
    }
    renderBet();
    renderBalance();
    plate.reset();
  }

  // ---------- boot ----------
  function preload(src) {
    const img = new Image();
    img.src = src;
    return (img.decode ? img.decode() : new Promise((r) => { img.onload = r; img.onerror = r; })).catch(() => {});
  }

  async function boot() {
    Board.init($('grid'), $('boardFx'));
    fitStage();
    setTimeout(fitStage, 250);
    wire();
    const P = window.Preloader;
    const t0 = performance.now();
    const track = (p, label = '') => {
      if (P) P.add(1);
      return Promise.resolve(p).catch(() => {}).finally(() => {
        if (P) P.step();
        const ms = performance.now() - t0;
        if (ms > 3000) console.warn(`[olympus-thunder] slow preload ${label} ${Math.round(ms)}ms`);
      });
    };
    const symbols = ['helmet', 'lyre', 'amphora', 'wreath', 'ruby', 'amethyst', 'emerald', 'sapphire', 'citrine', 'scatter', 'eagle', 'orb'];
    const symBase = BODY.symbols || `${IMG}symbols/`;
    const titles = BODY.titles || `${IMG}titles/`;
    const cards = BODY.cards || `${IMG}ui/`;
    const tasks = symbols.map((s) => track(preload(`${symBase}${s}.webp`)));
    for (const f of ['big_win', 'mega_win', 'epic_win', 'free_spins', 'super_free_spins', 'jackpot']) tasks.push(track(preload(`${titles}${f}.webp`)));
    for (const f of ['card_free_spins', 'card_super_free_spins', 'card_jackpot_chance']) tasks.push(track(preload(`${cards}${f}.webp`)));
    tasks.push(track(preload($('wheelDisc').querySelector('img').src)));
    for (const id of ['skyBase', 'temple', 'frame']) {
      const el = $(id);
      if (el && el.getAttribute('src')) tasks.push(track(preload(el.src), id));
    }
    if (window.OTSpine) tasks.push(track(OTSpine.load(), 'spine'));
    for (const p of Sound.preloadPromises || []) tasks.push(track(p, 'sound'));
    tasks.push(track(startSession(), 'session'));
    await Promise.race([Promise.all(tasks), new Promise((r) => setTimeout(r, 15000))]);
    Board.setGrid(START_GRID);
    fitStage();
    if (P) P.done();
    Sound.playMusic('base');
    zeus('idle');
  }

  window.OTGame = { state, playSpin, zeus };
  boot();
})();
