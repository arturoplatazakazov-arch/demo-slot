// Neon Joker Spins — skin-specific win lines (A neon tube, B marquee bulbs,
// C lightning, D lit winning cells instead of a line). slot.js showWinLine() hands over its SVG (stage pixels) with
// the line's points: window edges + cell centres (all) and cell centres only
// (cells); the skin page sets window.NJS_SKIN before this script.
// The base game keeps its own Spine line (fx.js) and does not load this file.
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const skin = window.NJS_SKIN;
  let timer = null;

  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const pathOf = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

  // A jagged copy of the line: perpendicular jitter every ~seg px, ends pinned.
  function bolt(pts, seg, amp) {
    const out = [];
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1];
      const b = pts[i];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      const n = Math.max(2, Math.round(len / seg));
      const nx = -(b.y - a.y) / len;
      const ny = (b.x - a.x) / len;
      for (let k = i === 1 ? 0 : 1; k <= n; k++) {
        const t = k / n;
        const pinned = (i === 1 && k === 0) || (i === pts.length - 1 && k === n);
        const j = pinned ? 0 : (Math.random() * 2 - 1) * amp;
        out.push({ x: a.x + (b.x - a.x) * t + nx * j, y: a.y + (b.y - a.y) * t + ny * j });
      }
    }
    return out;
  }

  const STYLE = `
  .wl-a-glow { stroke: #ff3cac; stroke-width: 30; opacity: .55; filter: blur(7px); }
  .wl-a-tube { stroke: #ff5cbc; stroke-width: 12; }
  .wl-a-core { stroke: #fff2fb; stroke-width: 4; }
  .wl-a-tube, .wl-a-core, .wl-a-glow { fill: none; stroke-linecap: round; stroke-linejoin: round; }
  .win-line.is-playing .wl-a-ign { animation: wl-a-ignite 360ms steps(1, end) both; }
  @keyframes wl-a-ignite { 0% { opacity: 0 } 20% { opacity: 1 } 35% { opacity: .2 } 55% { opacity: 1 } 70% { opacity: .5 } 85% { opacity: 1 } }
  .wl-b-glow { fill: none; stroke: #ff5ad0; stroke-width: 38; opacity: .7; filter: blur(9px); }
  .wl-b-tube { fill: none; stroke: #ffd75a; stroke-width: 14; filter: drop-shadow(0 0 6px #ffb000); }
  .wl-b-core { fill: none; stroke: #fffbe8; stroke-width: 5; }
  .wl-b-glow, .wl-b-tube, .wl-b-core { stroke-linecap: round; stroke-linejoin: round; }
  .win-line.is-playing .wl-b-draw { stroke-dasharray: 1600; animation: wl-b-draw 380ms ease-out both; }
  @keyframes wl-b-draw { from { stroke-dashoffset: 1600 } to { stroke-dashoffset: 0 } }

  .wl-c-glow { fill: none; stroke: #ff2fb4; stroke-width: 22; opacity: .5; filter: blur(8px); }
  .wl-c-arc { fill: none; stroke: #2ce8ff; stroke-width: 5; stroke-linejoin: miter; filter: drop-shadow(0 0 4px #2ce8ff); }
  .wl-c-arc2 { fill: none; stroke: #ff7ad8; stroke-width: 2.5; opacity: .9; }
  .wl-c-core { fill: none; stroke: #ffffff; stroke-width: 1.8; }

  .wl-d-fill { fill: #ffb02e; opacity: 0; }
  .win-line.is-playing .wl-d-fill { animation: wl-d-fill 620ms ease-out both; }
  @keyframes wl-d-fill { 0% { opacity: 0 } 25% { opacity: .45 } 100% { opacity: .22 } }
  .wl-d-frame { fill: none; stroke: #e2380c; stroke-width: 10; filter: drop-shadow(0 0 6px #ff6a00) drop-shadow(0 0 16px #ff3b1f); }
  .wl-d-bulbs { fill: none; stroke: #fff3b0; stroke-width: 9; stroke-linecap: round; stroke-dasharray: 0.1 26;
    filter: drop-shadow(0 0 4px #ffb02e) drop-shadow(0 0 9px #ff6a00); }
  .win-line.is-playing .wl-d-bulbs { animation: wl-d-chase 700ms linear infinite; }
  @keyframes wl-d-chase { to { stroke-dashoffset: -26.1 } }
  .win-line.is-playing .wl-d-cell { animation: wl-d-on 360ms steps(1, end) both; }
  @keyframes wl-d-on { 0% { opacity: 0 } 30% { opacity: 1 } 50% { opacity: .3 } 70%, 100% { opacity: 1 } }
  `;
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.appendChild(style);

  function stop() {
    clearInterval(timer);
    timer = null;
  }

  const RENDER = {
    // A — неоновая трубка, зажигается с миганием.
    a(svg, all) {
      const d = pathOf(all);
      const g = el('g', { class: 'wl-a-ign' }, svg);
      for (const cls of ['wl-a-glow', 'wl-a-tube', 'wl-a-core']) el('path', { class: cls, d }, g);
    },
    // B — простая золотая неоновая трубка с розовым свечением, прорисовывается.
    b(svg, all) {
      const d = pathOf(all);
      for (const cls of ['wl-b-glow', 'wl-b-tube', 'wl-b-core']) el('path', { class: `${cls} wl-b-draw`, d }, svg);
    },
    // C — молния: дуга перерисовывается каждые 60 мс.
    c(svg, all) {
      const glow = el('path', { class: 'wl-c-glow', d: pathOf(all) }, svg);
      const arc = el('path', { class: 'wl-c-arc' }, svg);
      const arc2 = el('path', { class: 'wl-c-arc2' }, svg);
      const core = el('path', { class: 'wl-c-core' }, svg);
      const zap = () => {
        if (!svg.isConnected) { stop(); return; }
        const main = bolt(all, 22, 16);
        arc.setAttribute('d', pathOf(main));
        core.setAttribute('d', pathOf(main));
        arc2.setAttribute('d', pathOf(bolt(all, 30, 26)));
        glow.style.opacity = String(0.35 + Math.random() * 0.3);
      };
      stop();
      zap();
      timer = setInterval(zap, 60);
    },
    // D — без линии: выигрышные ячейки загораются ламповой рамкой, как на
    // автомате 80-х — янтарная окантовка, бегущие лампочки по периметру,
    // тёплая подсветка внутри; ячейки вспыхивают по очереди.
    d(svg, all, cells) {
      const reel = document.getElementById('reel');
      const cw = reel.offsetWidth / 3;
      const ch = reel.offsetHeight / 3;
      const m = 7;
      cells.forEach((c, i) => {
        const g = el('g', { class: 'wl-d-cell' }, svg);
        g.style.animationDelay = `${i * 110}ms`;
        const box = { x: c.x - cw / 2 + m, y: c.y - ch / 2 + m, width: cw - 2 * m, height: ch - 2 * m, rx: 14 };
        el('rect', { class: 'wl-d-fill', ...box }, g).style.animationDelay = `${i * 110}ms`;
        el('rect', { class: 'wl-d-frame', ...box }, g);
        el('rect', { class: 'wl-d-bulbs', ...box }, g);
      });
    },
  };

  if (RENDER[skin]) {
    window.NJS_WINLINE = (svg, all, cells) => { stop(); RENDER[skin](svg, all, cells); };
    window.NJS_WINLINE_STOP = stop;
  }
})();
