// Deep Fortune — FX-слой «дорогой» подачи (по схеме Shaolin Struggles, 223faaf).
//
// Игра целиком PNG+CSS, спайна нет, поэтому вся «жизнь» собрана здесь
// отдельным слоем: он ничего не знает о математике и только слушает хуки
// slot.js (window.DeepFX.hook(name, ...args)). Без этого файла игра работает
// как раньше.
//
//   фон     -> Ken Burns, лучи с поверхности, каустика на дне, свечения
//              купола/трона, медузы и блики на сокровищах в бонусе; канвас
//              с пузырями, планктоном и стайками рыб
//   рамка   -> гирлянда жемчужных огней по канту (бегущий свет, как у
//              автоматов в Вегасе), две кометы, блик-свип, аура, вспышки
//   символы -> motion blur при падении, всплеск о дно, sunburst + блик по
//              альфе + искры и пузыри на выигрыше, глинты в простое
//   вайлд   -> столб воды и пузырей по барабану при раскрытии
//   герой   -> плавание в толще воды, аура, пузыри и искры на событиях
//   логотип -> падение в воду со всплеском, блик по буквам, звёздочки
//   попапы  -> лучи, побуквенный вход, счётчик суммы, фонтан монет и
//              жемчуга, пузырьковый шторм, тряска
(() => {
  'use strict';

  const ASSET = 'img/deep-fortune';
  const screen = document.getElementById('screen');
  const bgLayer = document.getElementById('bgLayer');
  const hero = document.querySelector('.hero');
  const reel = document.querySelector('.reel');
  const grid = document.getElementById('reelGrid');
  let logo = document.querySelector('img.logo');
  if (!screen || !bgLayer || !reel) return;

  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DPR = Math.min(window.devicePixelRatio || 1, 1.5);
  const isPortrait = () => window.matchMedia('(orientation: portrait)').matches;
  // Масштаб «автомата» на экране: все размеры частиц задуманы под рамку 1076px.
  const S = () => Math.max(0.35, reel.getBoundingClientRect().width / 1076);
  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];
  const el = (tag, cls, parent) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (parent) parent.appendChild(n);
    return n;
  };
  const restartClass = (node, cls, ms) => {
    if (!node) return;
    node.classList.remove(cls);
    void node.offsetWidth;
    node.classList.add(cls);
    if (ms) {
      clearTimeout(node[`__fx_${cls}`]);
      node[`__fx_${cls}`] = setTimeout(() => node.classList.remove(cls), ms);
    }
  };
  // CSS variables are substituted where they are USED — inside the
  // stylesheet in css/ — so a relative image path in --fx-mask would resolve
  // against css/ and 404. Always hand masks an absolute URL.
  const absUrl = (u) => new URL(u, document.baseURI).href;
  function rectInScreen(node) {
    const r = node.getBoundingClientRect();
    const s = screen.getBoundingClientRect();
    return { x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height, cx: r.left - s.left + r.width / 2, cy: r.top - s.top + r.height / 2 };
  }

  // Вертикальный motion blur для падающих лент — CSS blur() мажет во все
  // стороны и превращает символ в кашу, SVG-фильтр — только по вертикали.
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '0');
  svg.setAttribute('height', '0');
  svg.style.position = 'absolute';
  // dfHeroWave — hair/tail of the mascot drift in the current: a noise field
  //   slides slowly (feOffset) and displaces the hair layer through it, so
  //   the strands wave instead of boiling in place.
  // dfWave — the water ripple a living symbol's character gets on a win.
  svg.innerHTML = `
    <filter id="dfVBlur" x="0" y="-20%" width="100%" height="140%"><feGaussianBlur stdDeviation="0 10"/></filter>
    <filter id="dfHeroWave" x="-25%" y="-30%" width="150%" height="160%" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="0.006 0.014" numOctaves="2" seed="11" result="noise"/>
      <feOffset in="noise" dx="0" dy="0" result="flow">
        <animate attributeName="dy" values="0;-90;0" dur="9s" repeatCount="indefinite" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>
        <animate attributeName="dx" values="0;26;0" dur="6.5s" repeatCount="indefinite" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>
      </feOffset>
      <feDisplacementMap in="SourceGraphic" in2="flow" scale="22" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
    <filter id="dfWave" x="-10%" y="-10%" width="120%" height="120%" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="0.02 0.05" numOctaves="1" seed="4" result="noise">
        <animate attributeName="baseFrequency" values="0.02 0.05;0.026 0.06;0.02 0.05" dur="1.2s" repeatCount="indefinite"/>
      </feTurbulence>
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="9" xChannelSelector="R" yChannelSelector="G"/>
    </filter>`;
  document.body.appendChild(svg);

  // ===========================================================================
  // Процедурные спрайты (рисуются один раз)
  // ===========================================================================
  const sprites = new Map();
  function sprite(key, size, draw) {
    if (sprites.has(key)) return sprites.get(key);
    const c = document.createElement('canvas');
    c.width = c.height = size;
    draw(c.getContext('2d'), size);
    sprites.set(key, c);
    return c;
  }
  const glowSprite = (color) => sprite(`glow${color}`, 64, (g) => {
    const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0, 'rgba(255,255,255,1)');
    grd.addColorStop(0.2, color);
    grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 64, 64);
  });
  // Пузырь: прозрачная середина, светлый обод, блик сверху-слева.
  const bubbleSprite = () => sprite('bubble', 64, (g) => {
    const grd = g.createRadialGradient(32, 32, 14, 32, 32, 30);
    grd.addColorStop(0, 'rgba(160,240,255,0.05)');
    grd.addColorStop(0.7, 'rgba(170,240,255,0.22)');
    grd.addColorStop(0.92, 'rgba(225,252,255,0.85)');
    grd.addColorStop(1, 'rgba(225,252,255,0)');
    g.fillStyle = grd;
    g.beginPath();
    g.arc(32, 32, 30, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = 'rgba(255,255,255,0.9)';
    g.beginPath();
    g.ellipse(22, 20, 7, 4, -0.7, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = 'rgba(255,255,255,0.5)';
    g.beginPath();
    g.arc(41, 44, 2.4, 0, Math.PI * 2);
    g.fill();
  });
  // Золотая монета с ракушкой.
  const coinSprite = () => sprite('coin', 96, (g) => {
    const c = 48;
    let grd = g.createRadialGradient(36, 30, 4, c, c, 46);
    grd.addColorStop(0, '#fff6c4');
    grd.addColorStop(0.35, '#ffd457');
    grd.addColorStop(0.8, '#d18b12');
    grd.addColorStop(1, '#8a5206');
    g.fillStyle = grd;
    g.beginPath();
    g.arc(c, c, 45, 0, Math.PI * 2);
    g.fill();
    g.strokeStyle = 'rgba(255,240,180,0.9)';
    g.lineWidth = 3;
    g.beginPath();
    g.arc(c, c, 36, 0, Math.PI * 2);
    g.stroke();
    // Ракушка-гребешок: веер лучей из точки внизу.
    g.strokeStyle = 'rgba(150,90,10,0.85)';
    g.lineWidth = 3.2;
    g.lineCap = 'round';
    for (let i = -3; i <= 3; i++) {
      const a = -Math.PI / 2 + i * 0.28;
      g.beginPath();
      g.moveTo(c, c + 16);
      g.lineTo(c + Math.cos(a) * 24, c + 16 + Math.sin(a) * 30);
      g.stroke();
    }
    grd = g.createLinearGradient(0, 0, 96, 96);
    grd.addColorStop(0.2, 'rgba(255,255,255,0.55)');
    grd.addColorStop(0.45, 'rgba(255,255,255,0)');
    g.fillStyle = grd;
    g.beginPath();
    g.arc(c, c, 45, 0, Math.PI * 2);
    g.fill();
  });
  // Жемчужина с перламутровым переливом.
  const pearlSprite = (tint) => sprite(`pearl${tint}`, 64, (g) => {
    const grd = g.createRadialGradient(24, 22, 2, 32, 32, 30);
    grd.addColorStop(0, '#ffffff');
    grd.addColorStop(0.35, tint);
    grd.addColorStop(0.85, '#9fb6d6');
    grd.addColorStop(1, 'rgba(120,140,180,0)');
    g.fillStyle = grd;
    g.beginPath();
    g.arc(32, 32, 29, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = 'rgba(255,255,255,0.95)';
    g.beginPath();
    g.ellipse(23, 20, 6, 4, -0.6, 0, Math.PI * 2);
    g.fill();
  });
  // Силуэт рыбки (смотрит вправо).
  const fishSprite = (color) => sprite(`fish${color}`, 64, (g) => {
    g.fillStyle = color;
    g.beginPath();
    g.ellipse(30, 32, 18, 8, 0, 0, Math.PI * 2);
    g.fill();
    g.beginPath();
    g.moveTo(14, 32);
    g.lineTo(3, 23);
    g.lineTo(6, 32);
    g.lineTo(3, 41);
    g.closePath();
    g.fill();
  });

  // Тайл каустики: сумма косинусов с целыми волновыми числами — тайл
  // бесшовный; яркие нити там, где сумма проходит через ноль.
  function causticsTile(seed) {
    const N = 256;
    const c = document.createElement('canvas');
    c.width = c.height = N;
    const g = c.getContext('2d');
    const img = g.createImageData(N, N);
    const waves = [[1, 2], [2, -1], [3, 1], [-1, 3], [2, 3]].map(([kx, ky], i) => [kx, ky, seed * (i + 1) * 1.7]);
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        let v = 0;
        for (const [kx, ky, ph] of waves) v += Math.cos(((kx * x + ky * y) / N) * Math.PI * 2 + ph);
        const t = Math.pow(Math.max(0, 1 - Math.abs(v) / 1.1), 5);
        const i = (y * N + x) * 4;
        img.data[i] = 210;
        img.data[i + 1] = 250;
        img.data[i + 2] = 255;
        img.data[i + 3] = Math.round(t * 255);
      }
    }
    g.putImageData(img, 0, 0);
    return c.toDataURL();
  }

  // ===========================================================================
  // Канвасы
  // ===========================================================================
  function makeCanvas(cls, after) {
    const c = document.createElement('canvas');
    c.className = cls;
    if (after) after.after(c);
    else screen.appendChild(c);
    return { c, ctx: c.getContext('2d'), w: 0, h: 0, list: [] };
  }
  // Задник: сразу за фоном, до всех слоёв сцены (z 0 + порядок в DOM).
  const rig = el('div', 'fx-bgrig');
  bgLayer.after(rig);
  const bgCv = makeCanvas('fx-canvas fx-canvas--bg', rig);
  // Передний: над затемнением и рамкой, под попапом.
  const fgCv = makeCanvas('fx-canvas fx-canvas--fg');

  function sizeCanvases() {
    const w = screen.clientWidth;
    const h = screen.clientHeight;
    for (const cv of [bgCv, fgCv]) {
      cv.w = w;
      cv.h = h;
      cv.c.width = Math.round(w * DPR);
      cv.c.height = Math.round(h * DPR);
      cv.c.style.width = `${w}px`;
      cv.c.style.height = `${h}px`;
      cv.ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    }
  }

  // --- Частицы ------------------------------------------------------------------
  function spawnSparks(cv, x, y, n, opts = {}) {
    const colors = opts.colors || ['#fff6c8', '#ffd76a', '#bdf6ff', '#ffffff'];
    const s = S();
    const sp = (opts.speed || 1) * s * 2;
    for (let i = 0; i < n; i++) {
      const a = opts.angle != null ? opts.angle + rnd(-opts.spread, opts.spread) : rnd(0, Math.PI * 2);
      const v = rnd(4, 13) * sp;
      cv.list.push({
        kind: 'spark', x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 0, max: rnd(26, 52),
        color: pick(colors), w: rnd(1.6, 3.4) * s * 2, g: (opts.gravity ?? 0.22) * s * 2, drag: 0.93,
      });
    }
  }
  function spawnDroplets(cv, x, y, n, power = 1) {
    const s = S();
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + rnd(-1.1, 1.1);
      const v = rnd(6, 16) * s * 2 * power;
      cv.list.push({
        kind: 'drop', x: x + rnd(-40, 40) * s, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v,
        life: 0, max: rnd(40, 70), size: rnd(5, 12) * s * 2, g: 0.5 * s * 2,
      });
    }
  }
  function spawnRing(cv, x, y, opts = {}) {
    const s = S() * 2;
    cv.list.push({
      kind: 'ring', x, y, life: 0, max: opts.max || 32, r0: (opts.r0 || 10) * s, r1: (opts.r1 || 140) * s,
      color: opts.color || 'rgba(170, 245, 255, 1)', width: (opts.width || 10) * s, squash: opts.squash || 1,
    });
  }
  function spawnFlash(cv, x, y, opts = {}) {
    cv.list.push({
      kind: 'flash', x, y, life: 0, max: opts.max || 18, r: (opts.r || 160) * S() * 2,
      color: opts.color || 'rgba(200, 250, 255, 0.9)',
    });
  }
  function spawnBubble(cv, x, y, opts = {}) {
    const s = S();
    cv.list.push({
      kind: 'bubble', x, y, vx: opts.vx ?? rnd(-0.3, 0.3) * s, vy: -(opts.speed ?? rnd(1.2, 3.2)) * s * 1.6,
      size: (opts.size ?? rnd(6, 22)) * s * 1.6, life: 0, max: opts.max ?? rnd(120, 260),
      ph: rnd(0, 6), wob: rnd(0.4, 1.4) * s, alpha: opts.alpha ?? rnd(0.55, 0.95), pop: opts.pop ?? Math.random() < 0.35,
    });
  }
  function bubbleBurst(cv, x, y, n, spread = 60) {
    const s = S();
    for (let i = 0; i < n; i++) {
      spawnBubble(cv, x + rnd(-spread, spread) * s, y + rnd(-spread, spread) * 0.5 * s, {
        speed: rnd(2.5, 6), size: rnd(5, 18), max: rnd(60, 120), vx: rnd(-1.2, 1.2) * s,
      });
    }
  }
  // Фонтан монет и жемчуга снизу + дождь сверху.
  function spawnTreasure(cv, n, opts = {}) {
    const s = S() * 2;
    for (let i = 0; i < n; i++) {
      const fromBottom = opts.fountain !== false && i % 3 !== 0;
      const pearl = Math.random() < (opts.pearls ?? 0.35);
      const size = (pearl ? rnd(20, 34) : rnd(34, 60)) * s;
      const p = {
        kind: 'coin', pearl, tint: pick(['#ffe8f4', '#e6f6ff', '#fff4dc']), life: 0, max: rnd(150, 230), size,
        spin: rnd(0, Math.PI * 2), spinV: rnd(0.12, 0.3) * (Math.random() < 0.5 ? -1 : 1),
        rot: rnd(-0.6, 0.6), rotV: rnd(-0.05, 0.05), g: 0.4 * s, delay: (i / n) * (opts.spreadFrames || 50),
      };
      if (fromBottom) {
        p.x = cv.w * rnd(0.12, 0.88);
        p.y = cv.h + size;
        p.vx = rnd(-5, 5) * s;
        p.vy = -rnd(16, 26) * s;
      } else {
        p.x = rnd(0, cv.w);
        p.y = -size - rnd(0, cv.h * 0.3);
        p.vx = rnd(-1.5, 1.5) * s;
        p.vy = rnd(2, 7) * s;
      }
      cv.list.push(p);
    }
  }
  function spawnInward(cv, cx, cy, radius, n, colors) {
    for (let i = 0; i < n; i++) {
      const a = rnd(0, Math.PI * 2);
      const r = radius * rnd(0.8, 1.3);
      cv.list.push({
        kind: 'inward', x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r, cx, cy, life: 0, max: rnd(30, 46),
        color: pick(colors || ['#bdf6ff', '#ffe9a8', '#ffc4e6']), size: rnd(10, 22) * S() * 2,
      });
    }
  }

  function updateDraw(cv) {
    const { ctx, list } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    for (let i = list.length - 1; i >= 0; i--) {
      const p = list[i];
      p.life += 1;
      if (p.life > p.max) {
        if (p.onEnd) p.onEnd(p);
        list.splice(i, 1);
        continue;
      }
      if (p.life < 0) continue;
      const t = p.life / p.max;
      switch (p.kind) {
        case 'spark': {
          p.vx *= p.drag;
          p.vy = p.vy * p.drag + p.g;
          const px = p.x;
          const py = p.y;
          p.x += p.vx;
          p.y += p.vy;
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = 1 - t;
          ctx.strokeStyle = p.color;
          ctx.lineWidth = p.w * (1 - t * 0.6);
          ctx.lineCap = 'round';
          ctx.beginPath();
          ctx.moveTo(px - p.vx * 1.6, py - p.vy * 1.6);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
          break;
        }
        case 'drop': {
          p.vy += p.g;
          p.vx *= 0.99;
          p.x += p.vx;
          p.y += p.vy;
          ctx.globalCompositeOperation = 'source-over';
          ctx.globalAlpha = (1 - t) * 0.95;
          const s = p.size;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(Math.atan2(p.vy, p.vx) + Math.PI / 2);
          ctx.scale(0.75, 1.25);
          ctx.drawImage(bubbleSprite(), -s / 2, -s / 2, s, s);
          ctx.restore();
          break;
        }
        case 'ring': {
          const e = 1 - Math.pow(1 - t, 3);
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = (1 - t) * 0.9;
          ctx.strokeStyle = p.color;
          ctx.lineWidth = Math.max(0.5, p.width * (1 - t));
          const r = p.r0 + (p.r1 - p.r0) * e;
          ctx.beginPath();
          ctx.ellipse(p.x, p.y, r, r * p.squash, 0, 0, Math.PI * 2);
          ctx.stroke();
          break;
        }
        case 'flash': {
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = Math.pow(1 - t, 2);
          const r = p.r * (0.6 + t * 0.6);
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
          g.addColorStop(0, p.color);
          g.addColorStop(1, 'rgba(0,0,0,0)');
          ctx.fillStyle = g;
          ctx.fillRect(p.x - r, p.y - r, r * 2, r * 2);
          break;
        }
        case 'bubble': {
          p.x += p.vx + Math.sin(p.life * 0.06 + p.ph) * p.wob;
          p.y += p.vy;
          p.vy *= 1.002; // всплывая, пузырь чуть разгоняется
          ctx.globalCompositeOperation = 'source-over';
          const fadeIn = Math.min(1, p.life / 12);
          const fadeOut = t > 0.85 ? (1 - t) / 0.15 : 1;
          ctx.globalAlpha = p.alpha * fadeIn * fadeOut;
          const s = p.size * (1 + Math.sin(p.life * 0.2 + p.ph) * 0.05);
          ctx.drawImage(bubbleSprite(), p.x - s / 2, p.y - s / 2, s, s);
          if (p.pop && p.life === p.max) spawnRing(cv, p.x, p.y, { r0: 2, r1: 10, width: 2, max: 10 });
          break;
        }
        case 'coin': {
          if (p.delay > 0) { p.delay -= 1; p.life -= 1; break; }
          p.vy += p.g;
          p.vx *= 0.995;
          p.x += p.vx;
          p.y += p.vy;
          p.spin += p.spinV;
          p.rot += p.rotV;
          if (p.y > cv.h + p.size * 2 && p.vy > 0) { p.life = p.max; break; }
          ctx.globalCompositeOperation = 'source-over';
          ctx.globalAlpha = t > 0.85 ? (1 - t) / 0.15 : 1;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          const sx = p.pearl ? 1 : Math.cos(p.spin);
          ctx.scale(Math.max(0.08, Math.abs(sx)), 1);
          ctx.drawImage(p.pearl ? pearlSprite(p.tint) : coinSprite(), -p.size / 2, -p.size / 2, p.size, p.size);
          ctx.restore();
          if (Math.abs(sx) > 0.96 && !p.pearl) {
            ctx.globalCompositeOperation = 'lighter';
            ctx.globalAlpha = 0.55;
            const s = p.size * 0.9;
            ctx.drawImage(glowSprite('rgba(255,230,150,0.8)'), p.x - s / 2, p.y - s / 2, s, s);
          }
          break;
        }
        case 'inward': {
          const e = t * t;
          const x = p.x + (p.cx - p.x) * e;
          const y = p.y + (p.cy - p.y) * e;
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = Math.sin(t * Math.PI);
          ctx.drawImage(glowSprite(p.color), x - p.size / 2, y - p.size / 2, p.size, p.size);
          break;
        }
        case 'leaf': {
          p.x += p.vx + Math.sin(p.life * 0.12 + p.ph) * 1.2;
          p.y += p.vy;
          p.vy *= 0.985;
          p.rot += p.rotV;
          ctx.globalCompositeOperation = 'source-over';
          ctx.globalAlpha = Math.min(1, (1 - t) * 1.6);
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          ctx.scale(1, Math.cos(p.life * 0.15 + p.ph) * 0.5 + 0.6);
          ctx.fillStyle = p.color;
          ctx.beginPath();
          ctx.ellipse(0, 0, p.size * 0.5, p.size * 0.18, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = 'rgba(255,255,255,0.35)';
          ctx.fillRect(-p.size * 0.45, -0.6, p.size * 0.9, 1.2);
          ctx.restore();
          break;
        }
        // ---- фон ----
        case 'mote': {
          p.t += 1;
          p.x += p.vx + Math.sin(p.t * 0.015 + p.ph) * 0.25;
          p.y += p.vy;
          p.life = 1;
          if (p.y < -20 || p.x < -20 || p.x > cv.w + 20) resetMote(cv, p, false);
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = p.alpha * (0.5 + 0.5 * Math.sin(p.t * p.tw + p.ph));
          ctx.drawImage(glowSprite(p.color), p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
          break;
        }
        case 'fish': {
          p.x += p.vx;
          p.y += Math.sin(p.life * 0.05 + p.ph) * 0.35;
          ctx.globalCompositeOperation = 'source-over';
          const edge = Math.min(1, p.life / 40, (p.max - p.life) / 40);
          ctx.globalAlpha = p.alpha * edge;
          ctx.save();
          ctx.translate(p.x, p.y);
          if (p.vx < 0) ctx.scale(-1, 1);
          // Хвост бьётся: лёгкое сжатие по Y.
          ctx.scale(1, 1 + Math.sin(p.life * 0.4 + p.ph) * 0.08);
          ctx.drawImage(fishSprite(p.color), -p.size / 2, -p.size / 2, p.size, p.size);
          ctx.restore();
          break;
        }
        case 'glint': {
          ctx.globalCompositeOperation = 'lighter';
          const a = Math.sin(t * Math.PI);
          ctx.globalAlpha = a;
          const s = p.size * (0.4 + a * 0.6);
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(t * 1.2);
          ctx.fillStyle = 'rgba(255,248,220,0.95)';
          ctx.fillRect(-s / 2, -s * 0.05, s, s * 0.1);
          ctx.fillRect(-s * 0.05, -s / 2, s * 0.1, s);
          ctx.restore();
          ctx.drawImage(glowSprite('rgba(255,214,110,0.8)'), p.x - s * 0.4, p.y - s * 0.4, s * 0.8, s * 0.8);
          break;
        }
        default:
          break;
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  function resetMote(cv, p, anywhere) {
    p.x = rnd(0, cv.w);
    p.y = anywhere ? rnd(0, cv.h) : cv.h + 10;
    p.vy = -rnd(0.08, 0.4);
    p.vx = rnd(-0.12, 0.12);
  }
  function makeMote(cv, color) {
    const p = {
      kind: 'mote', life: 0, max: Infinity, t: rnd(0, 500), ph: rnd(0, 6), tw: rnd(0.02, 0.07),
      size: rnd(4, 12), alpha: rnd(0.3, 0.75), color,
    };
    resetMote(cv, p, true);
    return p;
  }

  // ===========================================================================
  // Фон: «риг», привязанный к картинке (object-fit: cover)
  // ===========================================================================

  // Координаты в % самой картинки фона.
  const BG_MAP = {
    bg_base: {
      sun: [50, -4], domes: [[55, 25], [86, 20]],
      vents: [[8, 92], [22, 96], [80, 95], [93, 88]],
    },
    bg_base_mob: {
      sun: [50, -3], domes: [[58, 12], [89, 15]],
      vents: [[6, 93], [20, 97], [82, 96], [94, 90]],
    },
    bg_bonus: {
      sun: [50, -4], throne: [50, 22], bonus: true,
      jelly: [[31.5, 7], [69.5, 9], [17.5, 37], [84, 33], [65.5, 44], [35, 45]],
      treasure: [[6, 80], [14, 70], [20, 88], [9, 93], [86, 70], [93, 80], [80, 88], [90, 93]],
      vents: [[30, 98], [70, 98]],
    },
    bg_bonus_mob: {
      sun: [50, -3], throne: [50, 15], bonus: true,
      jelly: [[15, 7], [79, 6], [80, 15], [24, 20]],
      treasure: [[6, 82], [14, 90], [24, 95], [86, 80], [94, 88], [76, 92]],
      vents: [[40, 99], [60, 99]],
    },
  };

  let bgKey = 'bg_base';
  let coverRect = { x: 0, y: 0, w: 1, h: 1 };
  const caustics = [causticsTile(0.3), causticsTile(1.9)];
  let nextFish = 0;
  let nextGlint = 0;

  function computeCover() {
    const nw = bgLayer.naturalWidth || 1536;
    const nh = bgLayer.naturalHeight || 1024;
    const sw = screen.clientWidth;
    const sh = screen.clientHeight;
    const k = Math.max(sw / nw, sh / nh);
    const w = nw * k;
    const h = nh * k;
    coverRect = { x: (sw - w) / 2, y: (sh - h) / 2, w, h };
    Object.assign(rig.style, { left: `${coverRect.x}px`, top: `${coverRect.y}px`, width: `${w}px`, height: `${h}px` });
  }
  const bgPoint = ([px, py]) => ({ x: coverRect.x + (coverRect.w * px) / 100, y: coverRect.y + (coverRect.h * py) / 100 });

  function buildRig() {
    const m = /\/(bg_[a-z_]+)\.jpg/.exec(bgLayer.getAttribute('src') || '');
    bgKey = m ? m[1] : 'bg_base';
    const cfg = BG_MAP[bgKey] || {};
    computeCover();
    rig.innerHTML = '';
    rig.dataset.bg = bgKey;
    const place = (node, [x, y]) => {
      node.style.left = `${x}%`;
      node.style.top = `${y}%`;
      return node;
    };

    // Каустика: два бесшовных слоя, плывущих навстречу, в перспективе пола.
    const floor = el('div', 'fx-caustics', rig);
    caustics.forEach((url, i) => {
      const layer = el('div', `fx-caustics__layer fx-caustics__layer--${i}`, floor);
      layer.style.backgroundImage = `url(${url})`;
    });
    // Лучи с поверхности: веер полос, каждая качается в своём ритме.
    if (cfg.sun) {
      const fan = place(el('div', 'fx-rays', rig), cfg.sun);
      const n = isPortrait() ? 6 : 9;
      for (let i = 0; i < n; i++) {
        const ray = el('span', 'fx-ray', fan);
        ray.style.setProperty('--fx-rot', `${((i / (n - 1)) - 0.5) * 70 + rnd(-4, 4)}deg`);
        ray.style.setProperty('--fx-w', `${rnd(3, 8).toFixed(1)}%`);
        ray.style.animationDuration = `${rnd(5, 9).toFixed(1)}s, ${rnd(7, 13).toFixed(1)}s`;
        ray.style.animationDelay = `${-rnd(0, 8).toFixed(1)}s, ${-rnd(0, 8).toFixed(1)}s`;
      }
      place(el('div', 'fx-surface-glow', rig), cfg.sun);
    }
    for (const pt of cfg.domes || []) place(el('div', 'fx-dome-glow', rig), pt).style.animationDelay = `${-rnd(0, 4).toFixed(1)}s`;
    if (cfg.throne) place(el('div', 'fx-throne-glow', rig), cfg.throne);
    for (const pt of cfg.jelly || []) {
      const j = place(el('div', 'fx-jelly', rig), pt);
      j.style.animationDuration = `${rnd(2.6, 4.4).toFixed(1)}s`;
      j.style.animationDelay = `${-rnd(0, 4).toFixed(1)}s`;
    }
    for (const pt of cfg.treasure || []) {
      const t = place(el('div', 'fx-treasure-glow', rig), pt);
      t.style.animationDelay = `${-rnd(0, 3).toFixed(1)}s`;
    }
    el('div', 'fx-vignette', rig);

    bgCv.list.length = 0;
    if (REDUCED) return;
    const small = isPortrait();
    const moteColor = cfg.bonus ? 'rgba(255,214,120,0.7)' : 'rgba(170,240,255,0.65)';
    for (let i = 0; i < (small ? 22 : 40); i++) bgCv.list.push(makeMote(bgCv, moteColor));
    for (let i = 0; i < (small ? 10 : 18); i++) {
      spawnBubble(bgCv, rnd(0, bgCv.w), rnd(bgCv.h * 0.2, bgCv.h), { max: rnd(200, 420), alpha: rnd(0.3, 0.7), size: rnd(4, 14) });
    }
    nextFish = performance.now() + rnd(1500, 4000);
  }
  bgLayer.addEventListener('load', buildRig);

  function tickBackground(now) {
    const cfg = BG_MAP[bgKey] || {};
    // Струйки пузырей из кораллов / щелей у дна.
    if (cfg.vents && Math.random() < 0.09) {
      const pt = bgPoint(pick(cfg.vents));
      spawnBubble(bgCv, pt.x + rnd(-20, 20), pt.y, { alpha: rnd(0.4, 0.85) });
    }
    if (Math.random() < 0.015) spawnBubble(bgCv, rnd(0, bgCv.w), bgCv.h + 20, { size: rnd(10, 26), alpha: 0.5 });
    // Стайки рыб в толще воды: идут на фоне, за автоматом.
    if (now > nextFish) {
      nextFish = now + rnd(9000, 16000);
      const dir = Math.random() < 0.5 ? 1 : -1;
      const y0 = bgCv.h * rnd(0.12, 0.45);
      const n = (Math.random() * 6 + 5) | 0;
      const s = S();
      const speed = rnd(1.1, 1.9) * s * 1.6 * dir;
      const color = cfg.bonus ? 'rgba(20,40,70,1)' : 'rgba(10,40,80,1)';
      for (let i = 0; i < n; i++) {
        bgCv.list.push({
          kind: 'fish', x: dir > 0 ? -60 - i * rnd(18, 34) * s : bgCv.w + 60 + i * rnd(18, 34) * s,
          y: y0 + rnd(-30, 30) * s, vx: speed * rnd(0.9, 1.1), life: 0, max: (bgCv.w + 400) / Math.abs(speed),
          size: rnd(26, 40) * s, ph: rnd(0, 6), alpha: rnd(0.25, 0.45), color,
        });
      }
    }
    // Бонус: искры на сокровищах.
    if (cfg.treasure && now > nextGlint) {
      nextGlint = now + rnd(120, 360);
      const pt = bgPoint(pick(cfg.treasure));
      bgCv.list.push({ kind: 'glint', x: pt.x + rnd(-40, 40), y: pt.y + rnd(-30, 30), life: 0, max: rnd(30, 50), size: rnd(20, 42) * S() });
    }
  }

  // ===========================================================================
  // Рамка: гирлянда жемчужных огней + кометы + блик
  // ===========================================================================
  let bulbs = [];
  function buildFrame() {
    if (reel.querySelector('.fx-frame-chase')) return;
    reel.insertBefore(el('div', 'fx-frame-aura'), reel.firstChild);
    el('div', 'fx-window-depth', reel);
    el('div', 'fx-frame-ring fx-frame-chase', reel);
    el('div', 'fx-frame-ring fx-frame-chase fx-frame-chase--fast', reel);
    el('div', 'fx-frame-ring fx-frame-sweep', reel);

    // Огни по канту рамки: координаты в пикселях самой .reel (1076x656) —
    // рамка масштабируется вместе с ней, огни тоже.
    const W = 1076;
    const H = 656;
    const m = 12.5; // середина канта: inset 7px + половина толщины 11px
    const step = 46;
    const pts = [];
    const nx = Math.round((W - 2 * m) / step);
    const ny = Math.round((H - 2 * m) / step);
    for (let i = 0; i < nx; i++) pts.push([m + ((W - 2 * m) * i) / nx, m]);
    for (let i = 0; i < ny; i++) pts.push([W - m, m + ((H - 2 * m) * i) / ny]);
    for (let i = 0; i < nx; i++) pts.push([W - m - ((W - 2 * m) * i) / nx, H - m]);
    for (let i = 0; i < ny; i++) pts.push([m, H - m - ((H - 2 * m) * i) / ny]);
    const wrap = el('div', 'fx-bulbs', reel);
    bulbs = pts.map(([x, y], i) => {
      const b = el('span', 'fx-bulb', wrap);
      b.style.left = `${x}px`;
      b.style.top = `${y}px`;
      b.style.setProperty('--i', i);
      return b;
    });
    wrap.style.setProperty('--n', bulbs.length);
    // Угловые жемчужины-самоцветы со звездой-вспышкой.
    for (const [x, y] of [[m, m], [W - m, m], [W - m, H - m], [m, H - m]]) {
      const c = el('span', 'fx-corner', reel);
      c.style.left = `${x}px`;
      c.style.top = `${y}px`;
      el('span', 'fx-corner__star', c);
    }

    // Блик и подсветка по альфе плашек (маска = их собственный PNG).
    for (const img of document.querySelectorAll('.sign-buy-bonus__img, .fs-counter__img')) {
      const sh = el('span', 'fx-plate-sheen');
      sh.style.setProperty('--fx-mask', `url("${absUrl(img.getAttribute('src'))}")`);
      img.after(sh);
    }
  }
  function setFrameMode(mode) {
    reel.classList.remove('fx-spin', 'fx-win', 'fx-antic', 'fx-idle');
    reel.classList.add(`fx-${mode}`);
  }

  // ===========================================================================
  // Логотип: оборачиваем <img>, чтобы под ним жили свечение, блик и звёзды
  // ===========================================================================
  let logoWrap = null;
  function buildLogo() {
    if (!logo || logoWrap) return;
    logoWrap = el('div', 'layer logo fx-logo');
    logo.replaceWith(logoWrap);
    logo.className = 'fx-logo__img';
    el('div', 'fx-logo__glow', logoWrap);
    logoWrap.appendChild(logo);
    const shine = el('div', 'fx-logo__shine', logoWrap);
    shine.style.setProperty('--fx-mask', `url("${absUrl(logo.getAttribute('src'))}")`);
    for (let i = 0; i < 8; i++) {
      const s = el('span', 'fx-twinkle', logoWrap);
      placeTwinkle(s);
      s.style.animationDelay = `${(i * 0.41).toFixed(2)}s`;
      s.addEventListener('animationiteration', () => placeTwinkle(s));
    }
  }
  function placeTwinkle(s) {
    s.style.left = `${rnd(12, 88)}%`;
    s.style.top = `${rnd(18, 82)}%`;
    s.style.setProperty('--fx-s', rnd(0.6, 1.25).toFixed(2));
  }
  function logoEntrance() {
    if (!logoWrap) return;
    restartClass(logoWrap, 'fx-logo-enter', 1500);
    // Касание «воды»: всплеск, кольца, брызги.
    setTimeout(() => {
      const r = rectInScreen(logoWrap);
      const y = r.y + r.h * 0.8;
      spawnFlash(fgCv, r.cx, r.cy, { r: 300, max: 22, color: 'rgba(200,250,255,0.85)' });
      spawnRing(fgCv, r.cx, y, { r0: 30, r1: 360, width: 14, max: 36, squash: 0.28 });
      spawnRing(fgCv, r.cx, y, { r0: 10, r1: 220, width: 10, max: 30, squash: 0.28 });
      spawnDroplets(fgCv, r.cx, y, 34, 1.1);
      bubbleBurst(fgCv, r.cx, y, 26, 160);
      spawnSparks(fgCv, r.cx, r.cy, 30, { speed: 1.2 });
      shake('s');
    }, 520);
  }

  // ===========================================================================
  // Героиня
  // ===========================================================================
  let heroAura = null;
  function buildHero() {
    if (!hero || heroAura) return;
    heroAura = el('div', 'fx-hero-aura');
    el('span', 'fx-hero-aura__halo', heroAura);
    el('span', 'fx-hero-aura__glow', heroAura);
    hero.before(heroAura);
    placeHeroAura();
  }
  function placeHeroAura() {
    if (!heroAura || !hero || !hero.offsetHeight) return;
    Object.assign(heroAura.style, {
      left: `${hero.offsetLeft}px`, top: `${hero.offsetTop}px`,
      width: `${hero.offsetWidth}px`, height: `${hero.offsetHeight}px`,
    });
  }
  // Точки на картинке героини (доли её бокса): поднятая рука и хвост.
  const HERO_HAND = [0.86, 0.2];
  const HERO_TAIL = [0.3, 0.86];
  const heroPoint = ([fx, fy]) => {
    const r = rectInScreen(hero);
    return { x: r.x + r.w * fx, y: r.y + r.h * fy };
  };
  let heroBusy = false;
  function heroFlourish(power = 1) {
    if (!hero || heroBusy || REDUCED || !hero.offsetHeight) return;
    heroBusy = true;
    restartClass(hero, 'fx-hero-glow', 900);
    const hand = heroPoint(HERO_HAND);
    spawnSparks(fgCv, hand.x, hand.y, Math.round(14 * power), { colors: ['#fff6c8', '#ffd76a', '#ffc4e6'], speed: 0.8, gravity: 0.05 });
    for (let i = 0; i < 4; i++) {
      setTimeout(() => {
        const p = heroPoint(HERO_HAND);
        bgCv.list.push({ kind: 'glint', x: p.x + rnd(-20, 20), y: p.y + rnd(-20, 20), life: 0, max: 34, size: rnd(26, 40) * S() });
      }, i * 90);
    }
    const tail = heroPoint(HERO_TAIL);
    bubbleBurst(fgCv, tail.x, tail.y, Math.round(10 * power), 40);
    setTimeout(() => { heroBusy = false; }, 900);
  }

  // ===========================================================================
  // Символы
  // ===========================================================================
  function playShine(cell) {
    const img = cell && cell.querySelector(':scope > img');
    if (!img || !img.getAttribute('src') || img.style.visibility === 'hidden') return;
    let sh = cell.querySelector(':scope > .fx-shine');
    if (!sh) sh = el('span', 'fx-shine', cell);
    sh.style.setProperty('--fx-mask', `url("${absUrl(img.getAttribute('src'))}")`);
    restartClass(sh, 'is-on', 900);
  }
  const BURST_COLORS = { wild: '#ffd25a', scatter: '#ff9ad5', siren: '#ff6a6a', nymph: '#5fe3a1', shark: '#5fb8ff' };
  function addBurst(cell, symbol) {
    if (!cell || cell.querySelector(':scope > .fx-burst')) return;
    const b = document.createElement('span');
    b.className = 'fx-burst';
    b.style.setProperty('--fx-burst', BURST_COLORS[symbol] || '#7fe9ff');
    cell.insertBefore(b, cell.firstChild);
  }
  function clearBursts() {
    if (grid) grid.querySelectorAll('.fx-burst').forEach((b) => b.remove());
  }

  let busy = false;
  function idleGlint() {
    if (busy || document.hidden || !grid) return;
    const cells = [...grid.querySelectorAll('.reel__cell')].filter((c) => !c.classList.contains('is-dimmed'));
    if (!cells.length) return;
    const special = cells.filter((c) => c.classList.contains('is-special'));
    const target = special.length && Math.random() < 0.55 ? pick(special) : pick(cells);
    playShine(target);
    if (target.classList.contains('is-special') && !REDUCED) {
      const r = rectInScreen(target);
      spawnSparks(fgCv, r.cx, r.cy, 6, { speed: 0.5, gravity: 0.03 });
    }
  }

  // Частицы выигрыша у каждой буквы свои (пара к её CSS-анимации).
  const LETTER_FX = {
    // A — золото: мини-монеты подлетают и крутятся, золотые искры.
    a(r) {
      const s = S() * 2;
      for (let i = 0; i < 6; i++) {
        fgCv.list.push({
          kind: 'coin', pearl: false, life: 0, max: rnd(50, 70), size: rnd(16, 24) * s,
          x: r.cx + rnd(-20, 20) * S(), y: r.cy, vx: rnd(-4, 4) * s, vy: -rnd(7, 12) * s,
          spin: rnd(0, 6), spinV: rnd(0.25, 0.45), rot: 0, rotV: rnd(-0.08, 0.08), g: 0.45 * s, delay: i * 2,
        });
      }
      spawnSparks(fgCv, r.cx, r.cy, 12, { colors: ['#fff3b0', '#ffd25a', '#ffb22e'] });
    },
    // K — коралл: тёплая вспышка, красно-розовые искры, пузыри.
    k(r) {
      spawnFlash(fgCv, r.cx, r.cy, { r: 110, max: 14, color: 'rgba(255,120,100,0.8)' });
      spawnSparks(fgCv, r.cx, r.cy, 14, { colors: ['#ff7a6a', '#ffb3a6', '#ff9ad5', '#fff'] });
      bubbleBurst(fgCv, r.cx, r.cy + r.h * 0.2, 5, 30);
    },
    // Q — нефрит: листья водорослей, кружась, поднимаются вверх.
    q(r) {
      const s = S();
      for (let i = 0; i < 9; i++) {
        fgCv.list.push({
          kind: 'leaf', x: r.cx + rnd(-r.w * 0.35, r.w * 0.35), y: r.y + r.h * rnd(0.55, 0.9),
          vx: rnd(-0.6, 0.6) * s, vy: -rnd(1.6, 3.2) * s * 1.6, life: 0, max: rnd(60, 90),
          size: rnd(14, 24) * s * 1.6, rot: rnd(0, 6), rotV: rnd(-0.12, 0.12), ph: rnd(0, 6),
          color: pick(['#4fe39a', '#2fbf74', '#9ff2c4']),
        });
      }
      spawnSparks(fgCv, r.cx, r.cy, 6, { colors: ['#9ff2c4', '#ffffff'], speed: 0.7 });
    },
    // J — лазурь: кольца ряби по воде + голубые пузыри.
    j(r) {
      for (let i = 0; i < 3; i++) {
        setTimeout(() => spawnRing(fgCv, r.cx, r.y + r.h * 0.82, {
          r0: 8, r1: 70 + i * 22, width: 5, max: 30, squash: 0.32, color: 'rgba(140,215,255,1)',
        }), i * 110);
      }
      bubbleBurst(fgCv, r.cx, r.cy, 7, 35);
    },
    // Живые символы: частицы в пару к их CSS-«игре».
    siren(r) {
      spawnSparks(fgCv, r.cx, r.y + r.h * 0.3, 16, { colors: ['#ff9ab0', '#ffd6e6', '#fff', '#ffe9a8'], speed: 0.9, gravity: 0.04 });
      for (let i = 0; i < 4; i++) bgCv.list.push({ kind: 'glint', x: r.cx + rnd(-r.w * 0.3, r.w * 0.3), y: r.y + r.h * rnd(0.2, 0.6), life: 0, max: 34, size: rnd(26, 40) * S() });
    },
    nymph(r) {
      LETTER_FX.q(r);
      spawnFlash(fgCv, r.cx, r.cy, { r: 110, max: 14, color: 'rgba(120,255,180,0.7)' });
    },
    shark(r) {
      spawnRing(fgCv, r.cx, r.cy, { r0: 20, r1: 170, width: 8, max: 26, color: 'rgba(150,220,255,1)' });
      bubbleBurst(fgCv, r.cx, r.cy, 16, 70);
    },
    wild(r) {
      spawnFlash(fgCv, r.cx, r.cy, { r: 160, max: 18, color: 'rgba(255,225,140,0.9)' });
      spawnRing(fgCv, r.cx, r.cy, { r0: 20, r1: 200, width: 10, max: 30, color: 'rgba(255,215,120,1)' });
      spawnSparks(fgCv, r.cx, r.cy, 22, { colors: ['#ffd25a', '#fff6c8', '#7fe9ff'], speed: 1.3 });
    },
  };

  // ===========================================================================
  // Тряска / вспышка экрана
  // ===========================================================================
  function shake(size = 's') {
    if (REDUCED) return;
    screen.classList.remove('fx-shake-s', 'fx-shake-m', 'fx-shake-l');
    void screen.offsetWidth;
    screen.classList.add(`fx-shake-${size}`);
    clearTimeout(screen.__fxShake);
    screen.__fxShake = setTimeout(() => screen.classList.remove(`fx-shake-${size}`), 720);
  }
  const flashLayer = el('div', 'fx-screen-flash', screen);
  function screenFlash(color = '#e6fbff', strength = 0.85) {
    flashLayer.style.setProperty('--fx-flash', color);
    flashLayer.style.setProperty('--fx-flash-a', strength);
    restartClass(flashLayer, 'is-on', 700);
  }

  // ===========================================================================
  // Попапы
  // ===========================================================================
  const POPUP_FX = {
    bigWin: { coins: 50, shake: 's', rays: '#7fe9ff', bubbles: 24 },
    megaWin: { coins: 100, shake: 'm', rays: '#ffd25a', flash: true, bubbles: 40 },
    epicWin: { coins: 170, shake: 'l', rays: '#ff9ad5', flash: true, bubbles: 60 },
    bonusSpinsWin: { coins: 40, pearls: 0.8, shake: 'm', rays: '#7fe9ff', flash: true, bubbles: 90 },
    bonusSpinsTotalWin: { coins: 110, shake: 'm', rays: '#ffd25a', flash: true, bubbles: 40 },
    buyFreeSpins: { coins: 0, rays: '#7fe9ff', bubbles: 16 },
  };

  function attachPopupFx(key, node, amount, holdMs) {
    const cfg = POPUP_FX[key] || { rays: '#7fe9ff' };
    // Лучи — отдельный слой за карточкой (у карточки свой stacking context).
    const rays = el('div', 'fx-popup-rays', screen);
    rays.style.setProperty('--fx-ray', cfg.rays);
    requestAnimationFrame(() => rays.classList.add('is-in'));
    el('span', 'fx-popup-sheen', node);

    const title = node.querySelector('.game-popup__title');
    if (title && !REDUCED) {
      const text = title.textContent;
      title.textContent = '';
      [...text].forEach((ch, i) => {
        const s = el('span', 'fx-ch', title);
        s.textContent = ch === ' ' ? '\u00a0' : ch;
        s.style.animationDelay = `${120 + i * 55}ms, ${900 + i * 60}ms`;
      });
    }
    // Счётчик суммы от нуля (фриспины — без счётчика: «10 SPINS» читается сразу).
    const amountEl = node.querySelector('.game-popup__amount');
    if (amountEl && Number(amount) > 0 && !REDUCED && key !== 'bonusSpinsWin') {
      const suffix = amountEl.textContent.replace(/^[\d,]+/, '');
      const target = Number(amount);
      const dur = Math.min(1800, (holdMs || 2500) * 0.6);
      const t0 = performance.now() + 250;
      const step = (now) => {
        const t = Math.min(1, Math.max(0, (now - t0) / dur));
        const e = 1 - Math.pow(1 - t, 3);
        amountEl.textContent = Math.round(target * e).toLocaleString('en-US') + suffix;
        if (t < 1 && node.isConnected) requestAnimationFrame(step);
        else if (t >= 1) restartClass(amountEl, 'fx-amount-done', 600);
      };
      amountEl.textContent = `0${suffix}`;
      requestAnimationFrame(step);
    }

    const watch = () => {
      if (!node.isConnected || node.classList.contains('is-out')) {
        rays.classList.remove('is-in');
        setTimeout(() => rays.remove(), 420);
        return;
      }
      requestAnimationFrame(watch);
    };
    requestAnimationFrame(watch);

    if (REDUCED) return;
    if (cfg.flash) screenFlash();
    if (cfg.shake) setTimeout(() => shake(cfg.shake), 120);
    const k = isPortrait() ? 0.6 : 1;
    if (cfg.coins) spawnTreasure(fgCv, Math.round(cfg.coins * k), { pearls: cfg.pearls });
    const c = { x: fgCv.w / 2, y: fgCv.h * 0.46 };
    spawnRing(fgCv, c.x, c.y, { r0: 60, r1: 620, width: 18, max: 38 });
    spawnSparks(fgCv, c.x, c.y, 50, { speed: 1.6 });
    if (cfg.bubbles) {
      for (let i = 0; i < cfg.bubbles * k; i++) {
        spawnBubble(fgCv, rnd(0, fgCv.w), fgCv.h + rnd(0, 120), { speed: rnd(3, 7), size: rnd(8, 30), max: rnd(90, 160) });
      }
    }
    if (logoWrap) restartClass(logoWrap, 'fx-logo-pulse', 900);
    heroFlourish(1.4);
  }

  // ===========================================================================
  // Хуки из slot.js
  // ===========================================================================
  let landedCols = 0;
  const HOOKS = {
    ready() {
      sizeCanvases();
      buildRig();
      buildFrame();
      buildLogo();
      buildHero();
      setFrameMode('idle');
      setTimeout(logoEntrance, 450);
    },

    spinStart() {
      busy = true;
      landedCols = 0;
      clearBursts();
      setFrameMode('spin');
      if (grid) grid.querySelectorAll('.reel__strip').forEach((s) => s.classList.add('fx-blur'));
      if (heroAura) heroAura.classList.add('is-charged');
      if (hero && !REDUCED && hero.offsetHeight) {
        const r = rectInScreen(hero);
        spawnInward(fgCv, r.cx, r.y + r.h * 0.45, r.h * 0.5, 16);
      }
    },

    // Blur only while the strip is fast: drop it at ~half the landing ease,
    // when the motion has already slowed — switching the filter off at the
    // very stop made the symbols visibly snap into focus.
    colDrop(col) {
      const strip = grid && grid.querySelectorAll('.reel__strip')[col];
      if (!strip) return;
      strip.classList.add('fx-blur');
      clearTimeout(strip.__fxBlur);
      strip.__fxBlur = setTimeout(() => strip.classList.remove('fx-blur'), 330);
    },

    colLand(col) {
      const strips = grid ? grid.querySelectorAll('.reel__strip') : [];
      if (strips[col]) strips[col].classList.remove('fx-blur');
      const colEl = grid && grid.querySelectorAll('.reel__col')[col];
      if (colEl) {
        restartClass(colEl, 'fx-col-impact', 460);
        // Колонка «падает на дно»: пузыри из-под барабана.
        if (!REDUCED) {
          const r = rectInScreen(reel);
          const x = r.x + r.w * ((col + 0.5) / 5);
          const y = r.y + r.h * 0.94;
          for (let i = 0; i < 5; i++) spawnBubble(fgCv, x + rnd(-40, 40) * S(), y, { speed: rnd(1.5, 3.5), size: rnd(5, 12), max: rnd(50, 90) });
        }
      }
      landedCols += 1;
      if (landedCols >= 5) {
        busy = false;
        setFrameMode('idle');
        if (heroAura) heroAura.classList.remove('is-charged');
      }
    },

    anticipation(col) {
      setFrameMode('antic');
      const colEl = grid && grid.querySelectorAll('.reel__col')[col];
      if (colEl && !REDUCED) {
        const r = rectInScreen(reel);
        const x = r.x + r.w * ((col + 0.5) / 5);
        spawnRing(fgCv, x, r.cy, { r0: 30, r1: 260, width: 10, color: 'rgba(255,140,220,1)', max: 30 });
        for (let i = 0; i < 14; i++) spawnBubble(fgCv, x + rnd(-60, 60) * S(), r.y + r.h, { speed: rnd(3, 6), size: rnd(6, 16), max: rnd(60, 110) });
      }
      if (logoWrap) restartClass(logoWrap, 'fx-logo-pulse', 900);
    },

    win(infos) {
      if (!infos || !infos.length) return;
      setFrameMode('win');
      clearTimeout(reel.__fxWin);
      reel.__fxWin = setTimeout(() => { if (!busy) setFrameMode('idle'); }, 1800);
      for (const info of infos) {
        addBurst(info.cell, info.symbol);
        if (REDUCED) continue;
        const r = rectInScreen(info.cell);
        spawnFlash(fgCv, r.cx, r.cy, { r: 120, max: 16 });
        spawnRing(fgCv, r.cx, r.cy, { r0: 20, r1: 150, width: 7, max: 26 });
      }
      heroFlourish(1);
    },

    cellPulse(info) {
      if (!info || !info.cell) return;
      playShine(info.cell);
      if (REDUCED) return;
      const r = rectInScreen(info.cell);
      const letter = LETTER_FX[info.symbol];
      if (letter) {
        letter(r);
        return;
      }
      spawnSparks(fgCv, r.cx, r.cy, 8);
      for (let i = 0; i < 3; i++) spawnBubble(fgCv, r.cx + rnd(-30, 30) * S(), r.cy + rnd(0, 30) * S(), { speed: rnd(2, 4), size: rnd(5, 12), max: 60 });
    },

    // Раскрытие вайлда: столб воды и пузырей вдоль всего барабана.
    bigWild(col, win) {
      if (REDUCED) return;
      const r = rectInScreen(reel);
      const x = r.x + r.w * ((col + 0.5) / 5);
      spawnFlash(fgCv, x, r.cy, { r: 260, max: 22, color: 'rgba(255,230,150,0.9)' });
      for (let i = 0; i < 40; i++) {
        spawnBubble(fgCv, x + rnd(-70, 70) * S(), r.y + r.h * rnd(0.6, 1), { speed: rnd(4, 9), size: rnd(6, 20), max: rnd(50, 100) });
      }
      spawnSparks(fgCv, x, r.cy, 30, { colors: ['#ffd25a', '#fff6c8', '#7fe9ff'], speed: 1.3 });
      if (win) shake('s');
    },

    inlineWin() {
      if (REDUCED) return;
      const r = rectInScreen(reel);
      spawnSparks(fgCv, r.cx, r.cy, 24, { speed: 1.1 });
    },

    popup(key, node, amount, holdMs) {
      if (node) attachPopupFx(key, node, amount, holdMs);
    },

    bonusEnter() {
      screenFlash('#fff1c2', 1);
      shake('m');
      if (!REDUCED) {
        const c = { x: fgCv.w / 2, y: fgCv.h / 2 };
        spawnRing(fgCv, c.x, c.y, { r0: 40, r1: 900, width: 24, max: 40, color: 'rgba(255,220,140,1)' });
        spawnSparks(fgCv, c.x, c.y, 70, { speed: 2, colors: ['#ffd25a', '#fff6c8', '#ffe9a8'] });
        for (let i = 0; i < 70; i++) spawnBubble(fgCv, rnd(0, fgCv.w), fgCv.h + rnd(0, 200), { speed: rnd(4, 9), size: rnd(8, 30), max: rnd(90, 150) });
      }
      setTimeout(logoEntrance, 200);
    },

    bonusLeave() {
      screenFlash('#bdf6ff', 0.6);
    },
  };

  window.DeepFX = {
    hook(name, ...args) {
      try {
        if (HOOKS[name]) HOOKS[name](...args);
      } catch (err) {
        console.warn(`[deep-fx] ${name} failed:`, err);
      }
    },
  };

  // --- Цикл ---------------------------------------------------------------------
  let lastGlint = 0;
  function frame(now) {
    if (!REDUCED && !document.hidden) tickBackground(now);
    updateDraw(bgCv);
    updateDraw(fgCv);
    if (now - lastGlint > 1900) {
      lastGlint = now;
      idleGlint();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // Жест героини в простое — раз в 6-10 секунд.
  (function idleFlourish() {
    setTimeout(() => {
      if (!busy && !document.hidden && !document.querySelector('.game-popup')) heroFlourish(0.8);
      idleFlourish();
    }, rnd(6000, 10000));
  })();

  let resizeRaf = 0;
  window.addEventListener('resize', () => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      sizeCanvases();
      buildRig();
      placeHeroAura();
    });
  });
  if (hero) hero.querySelector('img')?.addEventListener('load', placeHeroAura);
  sizeCanvases();
})();
