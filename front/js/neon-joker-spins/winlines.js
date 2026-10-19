// Neon Joker Spins — skin-specific win lines (A neon tube, B marquee bulbs,
// C lightning). slot.js showWinLine() hands over its SVG (stage pixels) with
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

  // Evenly spaced points along a polyline (step in stage px).
  function along(pts, step) {
    const out = [];
    let carry = 0;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1];
      const b = pts[i];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      let d = carry;
      while (d <= len) {
        const t = d / len;
        out.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
        d += step;
      }
      carry = d - len;
    }
    return out;
  }

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
  .wl-a-socket { fill: none; stroke: #2ce8ff; stroke-width: 4; filter: drop-shadow(0 0 6px #2ce8ff); }
  .win-line.is-playing .wl-a-socket { animation: wl-a-pop 420ms cubic-bezier(.3,1.6,.5,1) both; transform-box: fill-box; transform-origin: center; }
  @keyframes wl-a-pop { from { transform: scale(0); opacity: 0 } }

  .wl-b-rope { fill: none; stroke: #8a5a00; stroke-width: 18; stroke-linecap: round; stroke-linejoin: round; }
  .wl-b-rope2 { fill: none; stroke: #ffd75a; stroke-width: 7; stroke-linecap: round; stroke-linejoin: round; }
  .wl-b-bulb { fill: #fff6c8; filter: drop-shadow(0 0 5px #ffd75a) drop-shadow(0 0 10px #ff9a00); }
  .win-line.is-playing .wl-b-bulb { animation: wl-b-chase 540ms linear infinite; }
  @keyframes wl-b-chase { 0%, 100% { fill: #fff6c8; opacity: 1 } 50% { fill: #b07a10; opacity: .55 } }
  .wl-b-star { fill: #fff; filter: drop-shadow(0 0 6px #ff5ad0); }
  .win-line.is-playing .wl-b-star { animation: wl-b-twinkle 620ms ease-out both; transform-box: fill-box; transform-origin: center; }
  @keyframes wl-b-twinkle { 0% { transform: scale(0) rotate(0) } 50% { transform: scale(1.2) rotate(45deg) } 100% { transform: scale(1) rotate(90deg) } }
  .win-line.is-playing .wl-b-draw { stroke-dasharray: 1400; animation: wl-b-draw 420ms ease-out both; }
  @keyframes wl-b-draw { from { stroke-dashoffset: 1400 } to { stroke-dashoffset: 0 } }

  .wl-c-glow { fill: none; stroke: #ff2fb4; stroke-width: 22; opacity: .5; filter: blur(8px); }
  .wl-c-arc { fill: none; stroke: #2ce8ff; stroke-width: 5; stroke-linejoin: miter; filter: drop-shadow(0 0 4px #2ce8ff); }
  .wl-c-arc2 { fill: none; stroke: #ff7ad8; stroke-width: 2.5; opacity: .9; }
  .wl-c-core { fill: none; stroke: #ffffff; stroke-width: 1.8; }
  .wl-c-node { fill: #e9fbff; filter: drop-shadow(0 0 8px #2ce8ff) drop-shadow(0 0 16px #ff2fb4); }
  .win-line.is-playing .wl-c-node { animation: wl-c-hit 380ms ease-out both; transform-box: fill-box; transform-origin: center; }
  @keyframes wl-c-hit { 0% { transform: scale(2.4); opacity: 0 } 40% { opacity: 1 } 100% { transform: scale(1) } }
  `;
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.appendChild(style);

  function stop() {
    clearInterval(timer);
    timer = null;
  }

  const RENDER = {
    // A — неоновая трубка: зажигается с миганием, в каждой ячейке — циан-кольцо.
    a(svg, all, cells) {
      const d = pathOf(all);
      const g = el('g', { class: 'wl-a-ign' }, svg);
      for (const cls of ['wl-a-glow', 'wl-a-tube', 'wl-a-core']) el('path', { class: cls, d }, g);
      cells.forEach((c, i) => {
        const r = el('circle', { class: 'wl-a-socket', cx: c.x, cy: c.y, r: 22 }, svg);
        r.style.animationDelay = `${120 + i * 90}ms`;
      });
    },
    // B — шоу-гирлянда: золотой шнур прорисовывается, по нему бегут лампочки.
    b(svg, all, cells) {
      const d = pathOf(all);
      el('path', { class: 'wl-b-rope wl-b-draw', d }, svg);
      el('path', { class: 'wl-b-rope2 wl-b-draw', d }, svg);
      along(all, 34).forEach((p, i) => {
        const b = el('circle', { class: 'wl-b-bulb', cx: p.x, cy: p.y, r: 11 }, svg);
        b.style.animationDelay = `${-(i % 3) * 180}ms`;
      });
      cells.forEach((c, i) => {
        const s = 30;
        const star = `M${c.x} ${c.y - s} L${c.x + s * 0.28} ${c.y - s * 0.28} L${c.x + s} ${c.y} L${c.x + s * 0.28} ${c.y + s * 0.28} `
          + `L${c.x} ${c.y + s} L${c.x - s * 0.28} ${c.y + s * 0.28} L${c.x - s} ${c.y} L${c.x - s * 0.28} ${c.y - s * 0.28} Z`;
        const e = el('path', { class: 'wl-b-star', d: star }, svg);
        e.style.animationDelay = `${150 + i * 110}ms`;
      });
    },
    // C — молния: дуга перерисовывается каждые 60 мс, узлы-вспышки в ячейках.
    c(svg, all, cells) {
      const glow = el('path', { class: 'wl-c-glow', d: pathOf(all) }, svg);
      const arc = el('path', { class: 'wl-c-arc' }, svg);
      const arc2 = el('path', { class: 'wl-c-arc2' }, svg);
      const core = el('path', { class: 'wl-c-core' }, svg);
      cells.forEach((c, i) => {
        const n = el('circle', { class: 'wl-c-node', cx: c.x, cy: c.y, r: 9 }, svg);
        n.style.animationDelay = `${i * 70}ms`;
      });
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
  };

  if (RENDER[skin]) {
    window.NJS_WINLINE = (svg, all, cells) => { stop(); RENDER[skin](svg, all, cells); };
    window.NJS_WINLINE_STOP = stop;
  }
})();
