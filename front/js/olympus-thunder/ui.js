// Olympus Thunder — overlays: win popups, jackpot wheel, Buy Bonus window,
// paytable. Pure presentation; game.js owns state and decides what to show.
(function () {
  const $ = (id) => document.getElementById(id);
  // design variants: <body data-titles="img/.../" data-cards="img/.../">
  const TITLES = document.body.dataset.titles || 'img/olympus-thunder/titles/';
  const CARDS = document.body.dataset.cards || 'img/olympus-thunder/ui/';

  function fmt(n) {
    return Number(Math.round(n)).toLocaleString('en-US');
  }

  // ---------- dim ----------
  let dimCount = 0;
  function dim(on, black = false) {
    dimCount = Math.max(0, dimCount + (on ? 1 : -1));
    $('screenDim').classList.toggle('is-on', dimCount > 0);
    $('screenDim').classList.toggle('is-black', black && on);
  }

  // ---------- count-up ----------
  function countUp(el, to, ms, from = 0) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      let skip = false;
      const stop = () => { skip = true; };
      el._skip = stop;
      const tick = (t) => {
        const k = skip ? 1 : Math.min(1, (t - t0) / ms);
        const e = 1 - Math.pow(1 - k, 3);
        el.textContent = fmt(from + (to - from) * e);
        if (k < 1) requestAnimationFrame(tick);
        else resolve();
      };
      requestAnimationFrame(tick);
    });
  }

  // ---------- popup ----------
  // kind: big | mega | epic | fs | super | total | jackpot
  const POPUP = {
    big: { title: 'big_win.webp', tier: 'win', sound: 'bigWin', ms: 2200 },
    mega: { title: 'mega_win.webp', tier: 'win', sound: 'megaWin', ms: 3200 },
    epic: { title: 'epic_win.webp', tier: 'win', sound: 'epicWin', ms: 4200 },
    fs: { title: 'free_spins.webp', tier: 'fs', sound: 'scatter', ms: 0 },
    super: { title: 'super_free_spins.webp', tier: 'super', sound: 'scatter', ms: 0 },
    total: { title: 'free_spins.webp', tier: 'fs', sound: 'totalWin', ms: 2600 },
    jackpot: { title: 'jackpot.webp', tier: 'win', sound: 'epicWin', ms: 1600 },
  };

  async function popup(kind, { amount = null, sub = '', count = null, autoMs = 0 } = {}) {
    const cfg = POPUP[kind];
    const el = $('popup');
    $('popupTitle').src = TITLES + cfg.title;
    $('popupSub').textContent = sub;
    $('popupAmount').textContent = '';
    el.dataset.tier = cfg.tier;
    el.classList.remove('is-in', 'can-close');
    dim(true);
    el.hidden = false;
    void el.offsetWidth;
    el.classList.add('is-in');
    if (window.Sound) Sound.playSfx(cfg.sound);
    if (window.OTSpine) OTSpine.celebrate(kind);
    const amountEl = $('popupAmount');
    let counting = Promise.resolve();
    if (amount != null) counting = countUp(amountEl, amount, cfg.ms || 1200);
    else if (count != null) amountEl.textContent = String(count);
    // tap skips the count-up, second tap (or the timer) closes
    await new Promise((resolve) => {
      let ready = false;
      const close = () => {
        if (!ready) {
          if (amountEl._skip) amountEl._skip();
          return;
        }
        el.removeEventListener('click', close);
        resolve();
      };
      el.addEventListener('click', close);
      counting.then(() => {
        ready = true;
        el.classList.add('can-close');
        setTimeout(close, autoMs || 1800);
      });
    });
    el.hidden = true;
    if (window.OTSpine) OTSpine.celebrate(null);
    dim(false);
    if (window.Sound) Sound.playSfx('popupClose');
  }

  // ---------- jackpot wheel ----------
  const TIER_LABEL = { mini: 'MINI', minor: 'MINOR', major: 'MAJOR', grand: 'GRAND' };
  let wheelAngle = 0;

  function buildWheel(sectors, prizes) {
    const box = $('wheelLabels');
    box.innerHTML = '';
    sectors.forEach((tier, i) => {
      const a = 15 + 30 * i; // sector centre, clockwise from 12 o'clock
      const d = document.createElement('div');
      d.className = 'wheel__label';
      d.dataset.index = i;
      const r = 31; // % of the disc radius... in % of width
      const rad = (a * Math.PI) / 180;
      d.style.left = `${50 + r * Math.sin(rad)}%`;
      d.style.top = `${50 - r * Math.cos(rad)}%`;
      const s = document.createElement('span');
      s.innerHTML = `${TIER_LABEL[tier]}<br>${prizes[tier]}×`;
      s.style.transform = `translate(-50%, -50%) rotate(${a}deg)`;
      s.style.textAlign = 'center';
      d.appendChild(s);
      box.appendChild(d);
    });
  }

  async function wheel({ sector, tier, amount }) {
    const scene = $('wheelScene');
    dim(true);
    scene.hidden = false;
    $('wheelLabels').querySelectorAll('.wheel__label').forEach((l) => l.classList.remove('is-win'));
    if (window.Sound) Sound.playSfx('popupOpen');
    await Board.wait(700);
    // land sector centre under the pointer (12 o'clock): rotate disc by -centre
    const centre = 15 + 30 * sector;
    const jitter = (Math.random() - 0.5) * 16;
    const base = Math.ceil(wheelAngle / 360) * 360;
    const target = base + 360 * 6 + (360 - centre) + jitter;
    const disc = $('wheelDisc');
    disc.style.transition = 'transform 5.2s cubic-bezier(.12,.6,.12,1)';
    disc.style.transform = `rotate(${target}deg)`;
    wheelAngle = target;
    // ticking as the pegs pass
    let ticks = 0;
    const tickTimer = setInterval(() => {
      if (window.Sound && ticks++ < 40) Sound.playSfx('click', { rate: 1.4, gain: 0.5 });
    }, 120);
    await new Promise((r) => setTimeout(r, 5300));
    clearInterval(tickTimer);
    const lbl = $('wheelLabels').querySelector(`[data-index="${sector}"]`);
    if (lbl) lbl.classList.add('is-win');
    if (window.Sound) Sound.thunder(tier === 'grand' ? 100 : tier === 'major' ? 50 : 10);
    if (window.OTSpine) OTSpine.strike();
    document.querySelector(`.jp[data-tier="${tier}"]`)?.classList.add('is-hit');
    await new Promise((r) => setTimeout(r, 1300));
    scene.hidden = true;
    dim(false);
    await popup('jackpot', { amount, sub: `${TIER_LABEL[tier]} JACKPOT` });
    document.querySelector(`.jp[data-tier="${tier}"]`)?.classList.remove('is-hit');
  }

  // ---------- buy window ----------
  const SKU_TEXT = {
    free_spins: { name: 'FREE SPINS', desc: '15 фриспинов, общий множитель от ×1' },
    super_free_spins: { name: 'SUPER FREE SPINS', desc: '15 фриспинов, сферы чаще и минимум одна в каждом спине' },
    jackpot: { name: 'JACKPOT CHANCE', desc: 'Гарантированное колесо джекпотов' },
  };
  const CARD_ART = { free_spins: 'card_free_spins.webp', super_free_spins: 'card_super_free_spins.webp', jackpot: 'card_jackpot_chance.webp' };

  // opts: { products, betSteps, betIndex, balance, currency }
  // resolves { buyId, betIndex } or null
  function buyWindow(opts) {
    return new Promise((resolve) => {
      const win = $('buyWindow');
      const cards = $('buyCards');
      let betIndex = opts.betIndex;
      let pending = null;

      function render() {
        const bet = opts.betSteps[betIndex];
        $('buyBet').textContent = `${fmt(bet)} ${opts.currency}`;
        cards.innerHTML = '';
        for (const p of opts.products) {
          const price = bet * p.cost_multiplier;
          const t = SKU_TEXT[p.kind] || { name: p.buy_id, desc: '' };
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'card';
          b.disabled = price > opts.balance;
          b.innerHTML = `<img src="${CARDS + (CARD_ART[p.kind] || CARD_ART.free_spins)}" alt="">
            <div class="card__text"><div class="card__name">${t.name}</div><div class="card__price">${fmt(price)}</div></div>`;
          const desc = document.createElement('div');
          desc.className = 'card__desc';
          desc.textContent = t.desc;
          const wrap = document.createElement('div');
          wrap.style.display = 'flex';
          wrap.style.flexDirection = 'column';
          wrap.style.alignItems = 'center';
          wrap.style.maxWidth = 'min(24vw, 30vh, 250px)';
          wrap.appendChild(b);
          wrap.appendChild(desc);
          b.addEventListener('click', () => {
            if (b.disabled) return;
            pending = p;
            $('buyConfirmText').innerHTML = `Купить <b>${t.name}</b><br>за <b>${fmt(price)} ${opts.currency}</b>?`;
            $('buyConfirm').hidden = false;
            if (window.Sound) Sound.playSfx('popupOpen');
          });
          cards.appendChild(wrap);
        }
      }

      function done(result) {
        win.hidden = true;
        $('buyConfirm').hidden = true;
        $('buyBetMinus').onclick = $('buyBetPlus').onclick = $('buyClose').onclick = $('buyYes').onclick = $('buyNo').onclick = null;
        resolve(result);
      }

      $('buyBetMinus').onclick = () => { betIndex = Math.max(0, betIndex - 1); render(); };
      $('buyBetPlus').onclick = () => { betIndex = Math.min(opts.betSteps.length - 1, betIndex + 1); render(); };
      $('buyClose').onclick = () => done(null);
      $('buyNo').onclick = () => { pending = null; $('buyConfirm').hidden = true; };
      $('buyYes').onclick = () => done({ buyId: pending.buy_id, kind: pending.kind, betIndex });
      win.onclick = (e) => { if (e.target === win) done(null); };

      render();
      win.hidden = false;
    });
  }

  // ---------- paytable / rules ----------
  function renderInfo(rules, bet, currency) {
    const body = $('infoBody');
    if (!rules) { body.textContent = 'Правила недоступны без сервера.'; return; }
    const names = {};
    const rows = Object.entries(rules.paytable).map(([code, tiers]) => {
      const pays = Object.entries(tiers)
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([k, v], i, arr) => {
          const label = i < arr.length - 1 ? `${k}–${Number(arr[i + 1][0]) - 1}` : `${k}+`;
          return `<span>${label}</span><b>${fmt(bet * v)}</b>`;
        }).join('');
      return `<div class="pt__row"><img src="${Board.srcFor(code)}" alt=""><div class="pt__pays">${pays}</div></div>`;
    }).join('');
    const sp = rules.scatter_pays;
    const jp = rules.jackpot;
    const oddsRow = (o) => o.map(([t, w]) => `<td>${TIER_LABEL[t]}</td><td>${w}%</td>`).join('');
    body.innerHTML = `
      <h2>Выплаты за скаттеры</h2>
      <p>Сетка 6×5, линий нет. Выигрыш — 8 и более одинаковых символов в любом месте сетки. Суммы ниже — при текущей ставке ${fmt(bet)} ${currency}.</p>
      <div class="pt">${rows}</div>
      <h2>Каскады</h2>
      <p>Выигравшие символы разбиваются разрядом, остальные падают вниз, сверху добираются новые — пока появляются выигрыши. Кольца молний, Сферы и Орлы не исчезают в каскаде.</p>
      <h2>Сферы-множители</h2>
      <p><img src="${Board.srcFor('orb_2')}" alt="" style="width:48px;vertical-align:middle"> Сфера несёт значение от ×2 до ×100. Если серия каскадов принесла выигрыш, он умножается на сумму всех сфер на поле. Без выигрыша сферы гаснут.</p>
      <h2>Free Spins</h2>
      <p><img src="${Board.srcFor('scatter')}" alt="" style="width:48px;vertical-align:middle"> 4, 5 или 6+ Колец молний запускают ${rules.free_spins.spins} фриспинов и платят ${sp['4']}×, ${sp['5']}× или ${sp['6']}× ставки.
      Общий множитель стартует с ×1. Если в выигрышной серии есть сферы, их значения добавляются к общему множителю, и выигрыш серии умножается на него; выигрыш без сфер платится как есть. Множитель не сбрасывается до конца бонуса.
      ${rules.free_spins.retrigger_count}+ Кольца во фриспинах — ещё +${rules.free_spins.retrigger_spins} спинов. Выплаты за Кольца и колесо множителями не умножаются.</p>
      <h2>Jackpot Wheel</h2>
      <p><img src="${Board.srcFor('eagle')}" alt="" style="width:48px;vertical-align:middle"> ${jp.trigger_count}+ Орлов Зевса за спин (с учётом каскадов) запускают колесо: Mini ${jp.prizes.mini}×, Minor ${jp.prizes.minor}×, Major ${jp.prizes.major}×, Grand ${fmt(jp.prizes.grand)}× ставки. Исход определяет сервер.</p>
      <table><tr><th>Шансы</th><th></th><th></th><th></th><th></th><th></th><th></th><th></th></tr>
      <tr><td>В игре:</td>${oddsRow(jp.natural_odds)}</tr><tr><td>Jackpot Chance:</td>${oddsRow(jp.buy_odds)}</tr></table>
      ${rules.bonus_buy.products.length ? `<h2>Buy Bonus</h2><p>${rules.bonus_buy.products.map((p) => `${(SKU_TEXT[p.kind] || {}).name || p.buy_id} — ${p.cost_multiplier}× ставки`).join(' · ')}.
      Покупка списывает цену и делает служебный спин с гарантированным запуском; его выигрыши не выплачиваются. Недоступна во время фич.</p>` : ''}
      <p>Максимальный выигрыш — ${fmt(rules.max_win_multiplier)}× ставки за раунд. RTP 96.0 %.</p>`;
  }

  window.UI = { fmt, dim, popup, wheel, buildWheel, buyWindow, renderInfo, countUp };
})();
