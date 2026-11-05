// Neon Joker Spins C — neon graffiti on the club wall, left and right of the
// slot. Every piece is always there as faint paint; one after another they
// light up: the neon tube draws itself along the stroke, flickers on, holds,
// then flickers off and the next one takes over, so the wall keeps "waking".
// Drawn in the stage's design space (desk 1600x900 / mob 720x1280) behind
// the mascot, frame and jackpots, so the pieces peek out from behind them.
(function () {
  if (window.NJS_SKIN !== 'c') return;
  const stage = document.getElementById('stage');
  if (!stage) return;
  const NS = 'http://www.w3.org/2000/svg';
  const PINK = '#ff2fb4';
  const CYAN = '#2ce8ff';
  const GOLD = '#ffd75a';

  const SHAPES = {
    crown: 'M0 62 L12 12 L36 42 L60 0 L84 42 L108 12 L120 62 Z M4 78 H116',
    bolt: 'M38 0 L4 58 H32 L14 112 L66 40 H38 L56 0 Z',
    star: 'M50 0 L62 36 L100 36 L69 58 L81 95 L50 72 L19 95 L31 58 L0 36 L38 36 Z',
    spade: 'M50 0 C52 30 0 42 0 72 C0 96 34 102 46 82 L36 112 H64 L54 82 C66 102 100 96 100 72 C100 42 48 30 50 0 Z',
    drip: 'M0 0 V40 C0 52 10 52 10 40 V0',
  };

  // [kind, value, x, y, scale/size, rotate, colour]
  const PIECES = {
    desk: [
      ['text', 'ROCK', 262, 175, 104, -12, CYAN],
      ['shape', 'crown', 318, 34, 0.9, -8, GOLD],
      ['shape', 'bolt', 430, 196, 0.95, 14, PINK],
      ['shape', 'star', 236, 44, 0.42, 0, PINK],
      ['text', 'PUNK', 18, 640, 84, -78, PINK],
      ['shape', 'star', 96, 300, 0.36, 12, CYAN],
      ['text', 'JOKER', 1150, 82, 64, -5, CYAN],
      ['text', '777', 1146, 330, 86, 8, PINK],
      ['shape', 'spade', 1170, 430, 0.95, -6, CYAN],
      ['shape', 'bolt', 1214, 620, 0.9, -12, GOLD],
      ['shape', 'star', 1290, 230, 0.4, 0, GOLD],
      ['shape', 'drip', 1160, 372, 1, 0, PINK],
    ],
    mob: [
      ['text', 'ROCK', 14, 336, 56, -10, CYAN],
      ['shape', 'bolt', 170, 284, 0.55, 16, PINK],
      ['text', '777', 520, 338, 54, 8, PINK],
      ['shape', 'crown', 640, 288, 0.55, -6, GOLD],
      ['text', 'JOKER', 548, 72, 40, -5, CYAN],
      ['shape', 'star', 660, 112, 0.32, 0, GOLD],
    ],
  };

  const style = document.createElement('style');
  style.textContent = `
  .graffiti { position: absolute; left: 0; top: 0; width: 100%; height: 100%; z-index: 0; pointer-events: none; overflow: visible; }
  .graffiti--mob { display: none; }
  @media (orientation: portrait) { .graffiti--desk { display: none; } .graffiti--mob { display: block; } }
  .gf path, .gf text { fill: none; stroke-linecap: round; stroke-linejoin: round; }
  .gf .paint { stroke-width: 5; opacity: 0.16; }
  .gf .tube { stroke-width: 4.5; stroke-dasharray: 2400; stroke-dashoffset: 2400; opacity: 0; }
  .gf .core { stroke: #fff; stroke-width: 1.6; stroke-dasharray: 2400; stroke-dashoffset: 2400; opacity: 0; }
  .gf.is-drawing .tube, .gf.is-drawing .core { opacity: 1; animation: gf-draw var(--draw) cubic-bezier(.4,.1,.4,1) forwards; }
  .gf.is-lit .tube, .gf.is-lit .core { opacity: 1; stroke-dashoffset: 0; }
  .gf.is-lit { animation: gf-on 520ms steps(1, end) both; filter: drop-shadow(0 0 4px var(--c)) drop-shadow(0 0 14px var(--c)); }
  .gf.is-lit.is-buzz { animation: gf-buzz 2.6s steps(1, end) infinite; }
  .gf.is-off .tube, .gf.is-off .core { opacity: 1; stroke-dashoffset: 0; animation: gf-off 600ms steps(1, end) forwards; }
  @keyframes gf-draw { to { stroke-dashoffset: 0; } }
  @keyframes gf-on { 0% { opacity: .2 } 18% { opacity: 1 } 30% { opacity: .35 } 48% { opacity: 1 } 60% { opacity: .6 } 72%, 100% { opacity: 1 } }
  @keyframes gf-buzz { 0%, 91%, 95%, 100% { opacity: 1 } 93% { opacity: .55 } 97% { opacity: .8 } }
  @keyframes gf-off { 0% { opacity: 1 } 25% { opacity: .3 } 40% { opacity: .85 } 60% { opacity: .15 } 100% { opacity: 0 } }
  `;
  document.head.appendChild(style);

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function build(variant, w, h) {
    const svg = el('svg', { class: `graffiti graffiti--${variant}`, viewBox: `0 0 ${w} ${h}`, 'aria-hidden': 'true' });
    const groups = PIECES[variant].map(([kind, value, x, y, s, rot, c]) => {
      const g = el('g', { class: 'gf', transform: `translate(${x} ${y}) rotate(${rot})` }, svg);
      g.style.setProperty('--c', c);
      for (const layer of ['paint', 'tube', 'core']) {
        let node;
        if (kind === 'text') {
          node = el('text', { x: 0, y: 0, 'font-family': "'Luckiest Guy', 'Baloo 2', sans-serif", 'font-size': s, 'letter-spacing': 2 }, g);
          node.textContent = value;
        } else {
          node = el('path', { d: SHAPES[value], transform: `scale(${s})`, 'vector-effect': 'non-scaling-stroke' }, g);
        }
        node.setAttribute('class', layer);
        if (layer !== 'core') node.setAttribute('stroke', c);
      }
      g.style.setProperty('--draw', kind === 'text' ? '1300ms' : '800ms');
      return g;
    });
    stage.insertBefore(svg, stage.firstChild);
    return groups;
  }

  const sets = { desk: build('desk', 1600, 900), mob: build('mob', 720, 1280) };
  const active = () => (window.matchMedia('(orientation: portrait)').matches ? sets.mob : sets.desk);

  // Light the pieces one by one in a shuffled order; each stays lit while the
  // next few come on, so 3-4 glow at once and the wall never goes dark.
  const LIT_AT_ONCE = 4;
  const STEP_MS = 1500;
  let queue = [];
  const lit = [];
  function next() {
    const groups = active();
    if (!queue.length) queue = groups.slice().sort(() => Math.random() - 0.5);
    const g = queue.shift();
    if (lit.includes(g)) return;
    g.classList.remove('is-off', 'is-lit', 'is-buzz');
    void g.getBoundingClientRect();
    g.classList.add('is-drawing');
    const draw = parseFloat(getComputedStyle(g).getPropertyValue('--draw')) || 1000;
    setTimeout(() => {
      g.classList.remove('is-drawing');
      g.classList.add('is-lit');
      setTimeout(() => g.classList.add('is-buzz'), 600);
    }, draw);
    lit.push(g);
    while (lit.length > LIT_AT_ONCE) {
      const old = lit.shift();
      old.classList.remove('is-lit', 'is-buzz', 'is-drawing');
      old.classList.add('is-off');
    }
  }
  window.matchMedia('(orientation: portrait)').addEventListener('change', () => {
    queue = [];
    while (lit.length) lit.shift().classList.remove('is-lit', 'is-buzz', 'is-drawing', 'is-off');
  });
  setInterval(() => { if (!document.hidden) next(); }, STEP_MS);
  next();
})();
