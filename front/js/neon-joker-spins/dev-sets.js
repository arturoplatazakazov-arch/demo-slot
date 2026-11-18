// Neon Joker Spins C — DEV: swap art sets by cluster (background, logo, low,
// high, special symbols, coins). Sets live in <ASSET_ROOT>/sets/<id>/ with the
// same layout as the skin (symbols/, coins/, img/); '0' = the skin's own art.
// Loaded BEFORE slot.js: window.NJS_ASSET_ROOT_FOR(path) picks the root per
// asset path, so preload and every later symbol/coin uses the chosen set.
// The choice is kept in localStorage (per browser) and in ?sets=bg.logo.low.high.special.coins.frame.hlogo.hero.jp.
// 'Лого гориз.' (img/logo_h.webp, one-line logo) replaces the stacked logo while it is on.
(function () {
  if (window.NJS_SKIN !== 'c') return;
  const ROOT = window.NJS_ASSET_ROOT;
  const META = window.NJS_SETS || { ids: [], names: {}, coinVal: {}, logo: {} };
  const KEY = 'njs-c-sets-v1';
  const CLUSTERS = [
    ['bg', 'Фон', ['img/bg_base.jpg', 'img/bg_fs.jpg', 'img/bg_base_mob.jpg', 'img/bg_fs_mob.jpg']],
    ['logo', 'Лого', ['img/logo.webp']],
    ['low', 'Дешёвые', ['cherry', 'lemon', 'plum', 'grape'].map((c) => `symbols/${c}`)],
    ['high', 'Редкие', ['seven', 'bell', 'star'].map((c) => `symbols/${c}`)],
    ['special', 'Спец', ['wild', 'scatter'].map((c) => `symbols/${c}`)],
    ['coins', 'Монеты', ['symbols/coin', 'coins/blank', 'coins/collector', 'coins/mini', 'coins/minor', 'coins/major', 'coins/grand']],
    ['frame', 'Рамка', ['img/frame.webp']],
    ['hlogo', 'Лого гориз.', []],
    ['hero', 'Герой', ['img/mascot.webp']],
    ['jp', 'Джекпоты', []],
  ];

  let pick = {};
  try { pick = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { pick = {}; }
  const q = new URLSearchParams(location.search).get('sets');
  if (q) q.split('.').forEach((v, i) => { if (CLUSTERS[i]) pick[CLUSTERS[i][0]] = v; });
  const save = () => { if (window.NJS_SETS_LOCK) return; try { localStorage.setItem(KEY, JSON.stringify(pick)); } catch (e) {} };
  // A fixed variant page (e.g. neon-joker-spins-reels.html): its clusters are locked, no panel.
  const LOCK = window.NJS_SETS_LOCK;
  if (LOCK) pick = { ...LOCK };

  function clusterOf(path) {
    const p = path.replace(/(_blur)?\.(webp|jpg)$/, '');
    for (const [k, , list] of CLUSTERS) {
      if (list.some((x) => x.replace(/\.(webp|jpg)$/, '') === p)) return k;
    }
    return null;
  }
  const has = (id, k) => META.ids.includes(id) && (!META.has || (META.has[id] || []).includes(k));
  function rootFor(path) {
    const k = clusterOf(path);
    const id = k && pick[k];
    return id && id !== '0' && has(id, k) ? `${ROOT}/sets/${id}` : ROOT;
  }
  window.NJS_ASSET_ROOT_FOR = rootFor;

  // --- live apply ---------------------------------------------------------
  const style = document.createElement('style');
  document.head.appendChild(style);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const IMG_RE = new RegExp(`${esc(ROOT)}(?:/sets/[^/]+)?/((?:symbols|coins|img)/[^?]+)(\\?.*)?$`);

  function cssRules() {
    const u = (p) => `url('${rootFor(p)}/${p}?v=m')`;
    let css = '';
    if (pick.bg && pick.bg !== '0' && has(pick.bg, 'bg')) {
      css += `.bg__img--base { background-image: ${u('img/bg_base.jpg')} !important; }
.bg__img--fs { background-image: ${u('img/bg_fs.jpg')} !important; }
@media (orientation: portrait) {
  .bg__img--base { background-image: ${u('img/bg_base_mob.jpg')} !important; }
  .bg__img--fs { background-image: ${u('img/bg_fs_mob.jpg')} !important; }
}\n`;
    }
    else if (META.mob0) {  // the skin's own scene, with its drawn portrait background
      const m0 = (f) => `url('${ROOT}/sets/s0/img/${f}?v=m')`;
      css += `@media (orientation: portrait) {
  .bg__img--base { background-image: ${m0('bg_base_mob.jpg')} !important; }
  .bg__img--fs { background-image: ${m0('bg_fs_mob.jpg')} !important; }
}\n`;
    }
    const cv = has(pick.coins, 'coins') && META.coinVal[pick.coins];
    if (cv) {
      css += `.reel__cell .coin-val { left: ${cv.blank[0]}%; right: ${cv.blank[1]}%; top: ${cv.blank[2]}%; height: ${cv.blank[3]}%; }
.reel__cell[data-symbol="collector"] .coin-val { left: ${cv.coll[0]}%; right: ${cv.coll[1]}%; top: ${cv.coll[2]}%; height: ${cv.coll[3]}%; }\n`;
    }
    const hl = has(pick.hlogo, 'hlogo') && (META.logoH || {})[pick.hlogo];
    const lg = hl || (has(pick.logo, 'logo') && META.logo[pick.logo]);
    if (lg) css += `.logo { ${lg.desk} }\n@media (orientation: portrait) { .logo { ${lg.mob} } }\n`;
    const jp = has(pick.jp, 'jp') && (META.jp || {})[pick.jp];
    if (jp) css += `${jp.desk.replace(/url\('\.\.\/\.\.\//g, "url('")}\n@media (orientation: portrait) { ${jp.mob} }\n`;
    const fr = has(pick.frame, 'frame') && (META.frame || {})[pick.frame];
    if (!LOCK && META.ar) css += portraitStack(hl);
    if (fr) {
      css += `.cabinet { background-image: ${u('img/frame.webp')} !important; }
:root { ${fr.desk} }
@media (orientation: portrait) { :root { ${fr.mob} } .cabinet { background-image: ${u('img/frame.webp')} !important; } }\n`;
    }
    return css;
  }

  // Portrait (user, 2026-11-18): GRAND a bit bigger on top, a row MAJOR · MINOR · MINI
  // under it, then the logo sitting on the reel frame's top edge (its lower part overlaps
  // the frame), then the reels in whatever frame is picked. Sizes come from the aspects.
  function portraitStack(hl) {
    const A = META.ar;
    const arOf = (k, key) => {
      const id = pick[k] && pick[k] !== '0' && has(pick[k], k) ? pick[k] : '0';
      return (A[id] || {})[key] || (A['0'] || {})[key] || 1.6;
    };
    const logoAr = hl ? (A[pick.hlogo] || {}).logoH || 4 : arOf('logo', 'logo');
    const CX = 360;
    const GAP = 10;
    let y = 8;
    let r = '';
    const gh = 128;
    const gw = Math.min(330, gh * arOf('jp', 'grand'));
    r += `.jp--grand { left: ${CX - gw / 2}px !important; top: ${y}px !important; width: ${gw}px !important; height: ${gw / arOf('jp', 'grand')}px !important; animation: none; }\n`;
    y += gw / arOf('jp', 'grand') + GAP;
    const rw = 222;
    const rh = Math.min(104, Math.min(...['major', 'minor', 'mini'].map((n) => rw / arOf('jp', n))));
    ['major', 'minor', 'mini'].forEach((n, k) => {
      const w = Math.min(rw, rh * arOf('jp', n));
      const x = CX - (3 * rw + 2 * GAP) / 2 + k * (rw + GAP) + (rw - w) / 2;
      r += `.jp--${n} { left: ${x}px !important; top: ${y}px !important; width: ${w}px !important; height: ${w / arOf('jp', n)}px !important; }\n`;
    });
    y += rh + GAP;
    const lh = hl ? 135 : 180;   // 1.5x the first pass (user)
    const lw = Math.min(700, lh * logoAr);
    const lH = lw / logoAr;
    r += `.logo { left: ${CX - lw / 2}px !important; top: ${y}px !important; width: ${lw}px !important; z-index: 8 !important; }\n`;
    // the logo's centre sits on the middle of the frame's top border (border = frame-h * fw-t)
    // ...but never so high that the logo covers the top symbols: with thin frames (the
    // skin's own, sets 1-3) the reel window starts at most 10 px above the logo's bottom.
    r += `:root { --frame-y: max(calc(${y + lH / 2}px - var(--frame-h) * var(--fw-t) / 2), calc(${y + lH - 10}px - var(--frame-h) * var(--fw-t))) !important; }\n`;
    return `@media (orientation: portrait) {\n${r}}\n`;
  }

  function apply() {
    const before = style.textContent;
    style.textContent = cssRules();
    // the frame decides the reel window: let slot.js re-measure the cells
    if (before !== style.textContent) setTimeout(() => window.dispatchEvent(new Event('resize')), 30);
    document.querySelectorAll('img').forEach((img) => {
      const m = IMG_RE.exec(img.getAttribute('src') || '');
      if (!m) return;
      let next = `${rootFor(m[1])}/${m[1]}${m[2] || ''}`;
      if (/^img\/logo(_h)?\.webp$/.test(m[1])) {
        next = has(pick.hlogo, 'hlogo') ? `${ROOT}/sets/${pick.hlogo}/img/logo_h.webp${m[2] || ''}`
          : `${rootFor('img/logo.webp')}/img/logo.webp${m[2] || ''}`;
      }
      if (img.getAttribute('src') !== next) img.src = next;
    });
  }

  // --- showcase: put the chosen cluster on the reels -----------------------
  const SHOW = {
    low: [['cherry', 'lemon', 'plum'], ['grape', 'cherry', 'lemon'], ['plum', 'grape', 'cherry']],
    high: [['seven', 'bell', 'star'], ['star', 'seven', 'bell'], ['bell', 'star', 'seven']],
    special: [['wild', 'scatter', 'wild'], ['scatter', 'wild', 'scatter'], ['wild', 'scatter', 'wild']],
  };
  const COINS = [[null, { kind: 'coin', value: 5 }, { kind: 'collector' }], [{ kind: 'mini' }, { kind: 'minor' }, { kind: 'major' }], [{ kind: 'grand' }, { kind: 'coin', value: 25 }, null]];
  function showcase(k) {
    if (typeof applyGrid !== 'function' || typeof cellInfos === 'undefined' || !cellInfos.length) return;
    if (SHOW[k]) { applyGrid(SHOW[k]); return; }
    if (k === 'coins') {
      applyGrid([['coin', 'coin', 'coin'], ['coin', 'coin', 'coin'], ['coin', 'coin', 'coin']]).then(() => {
        COINS.forEach((row, r) => row.forEach((c, col) => { if (c) setCoinFace(cellInfos[r * 3 + col], c); }));
      });
    }
  }

  // --- panel ----------------------------------------------------------------
  function build() {
    if (LOCK) return;
    const show = window.NJS_SETS_FORCE_DEV || (window.SLOT_CONFIG ? window.SLOT_CONFIG.showDevPanels !== false : true);
    if (!show || !META.ids.length) return;
    const css = document.createElement('style');
    css.textContent = `
.njs-sets-btn { position: fixed; right: 8px; top: 8px; z-index: 10000; padding: 7px 12px; border-radius: 8px; border: 1px solid #ff2fb4;
  background: rgba(20, 8, 24, .85); color: #ffd2ef; font: 700 12px/1 system-ui, sans-serif; cursor: pointer; }
.njs-sets { position: fixed; right: 8px; top: 42px; z-index: 10000; width: 330px; max-width: calc(100vw - 20px); padding: 10px; border-radius: 12px;
  background: rgba(14, 6, 18, .94); border: 1px solid #3a3344; color: #eee; font: 12px/1.3 system-ui, sans-serif; display: grid; gap: 8px; }
.njs-sets[hidden] { display: none; }
.njs-sets__row { display: grid; gap: 4px; }
.njs-sets__row b { font-weight: 700; color: #c9ced8; display: flex; justify-content: space-between; }
.njs-sets__row b small { font-weight: 400; color: #8f88a0; }
.njs-sets__chips { display: flex; gap: 4px; }
.njs-sets__chips button { flex: 1; min-width: 0; padding: 5px 0; border-radius: 6px; border: 1px solid #3a3344; background: #1d1724; color: #ddd; cursor: pointer; font: 600 12px/1 system-ui, sans-serif; }
.njs-sets__chips button:disabled { opacity: .3; cursor: default; }
.njs-sets__chips button.is-on { background: #ff2fb4; border-color: #ff2fb4; color: #14000c; }
.njs-sets__foot { display: flex; gap: 6px; }
.njs-sets__foot button { flex: 1; padding: 7px 0; border-radius: 6px; border: 1px solid #2ce8ff; background: transparent; color: #bff6ff; cursor: pointer; font: 600 12px/1 system-ui, sans-serif; }
`;
    document.head.appendChild(css);
    const btn = document.createElement('button');
    btn.className = 'njs-sets-btn';
    btn.type = 'button';
    btn.textContent = 'DEV · Сеты';
    const panel = document.createElement('div');
    panel.className = 'njs-sets';
    panel.hidden = true;
    const ids = ['0', ...META.ids];
    const nameOf = (id, k) => (id === '0' ? (k === 'hlogo' ? 'выкл' : 'Оригинал') : META.names[id] || id);
    function render() {
      panel.innerHTML = '';
      for (const [k, label] of CLUSTERS) {
        const cur = pick[k] || '0';
        const row = document.createElement('div');
        row.className = 'njs-sets__row';
        row.innerHTML = `<b>${label}<small>${nameOf(cur, k)}</small></b><div class="njs-sets__chips"></div>`;
        const chips = row.querySelector('.njs-sets__chips');
        ids.forEach((id, i) => {
          const b = document.createElement('button');
          b.type = 'button';
          b.textContent = i === 0 ? (k === 'hlogo' ? 'Выкл' : 'Ориг') : String(i);
          b.title = nameOf(id);
          b.classList.toggle('is-on', cur === id);
          b.disabled = id !== '0' && !has(id, k);
          b.addEventListener('click', () => {
            pick[k] = id;
            save();
            apply();
            render();
            showcase(k);
          });
          chips.appendChild(b);
        });
        panel.appendChild(row);
      }
      const foot = document.createElement('div');
      foot.className = 'njs-sets__foot';
      foot.innerHTML = '<button type="button" data-a="mix">Микс</button><button type="button" data-a="all">Весь сет…</button><button type="button" data-a="link">Ссылка</button>';
      foot.querySelector('[data-a="mix"]').addEventListener('click', () => {
        for (const [k] of CLUSTERS) {
          const ok = ids.filter((id) => id === '0' || has(id, k));
          pick[k] = ok[Math.floor(Math.random() * ok.length)];
        }
        save(); apply(); render();
      });
      foot.querySelector('[data-a="all"]').addEventListener('click', (e) => {
        const cur = pick.low || '0';
        const nxt = ids[(ids.indexOf(cur) + 1) % ids.length];
        for (const [k] of CLUSTERS) pick[k] = k === 'hlogo' ? '0' : nxt;
        save(); apply(); render();
        e.target.textContent = `Весь сет: ${nameOf(nxt)}`;
      });
      foot.querySelector('[data-a="link"]').addEventListener('click', async (e) => {
        const v = CLUSTERS.map(([k]) => pick[k] || '0').join('.');
        const u = new URL(location.href);
        u.searchParams.set('sets', v);
        try { await navigator.clipboard.writeText(u.toString()); } catch (err) {}
        e.target.textContent = v;
      });
      panel.appendChild(foot);
    }
    render();
    btn.addEventListener('click', () => { panel.hidden = !panel.hidden; });
    document.body.append(btn, panel);
  }

  apply();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => { apply(); build(); });
  else build();
})();
