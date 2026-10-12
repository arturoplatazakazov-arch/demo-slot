// Uniqorn Shaolin Struggles — FX-слой «дорогой» подачи.
//
// Игра целиком PNG+CSS (спайна нет), поэтому вся «жизнь» поверх неё собрана
// здесь, отдельным слоем, который ничего не знает о математике и только
// слушает хуки slot.js (window.ShaolinFX.hook(name, ...args)):
//
//   фон    -> Ken Burns + привязанный к картинке «риг» (фонари, жаровни,
//             лучи солнца / ореол луны) + канвас частиц (лепестки сакуры и
//             пыль в базе, угли и салют в раунде)
//   рамка  -> бегущий по канту свет, блик-свип, глоу, вспышки на выигрыше,
//             огонь антиципации, удар при посадке колонки
//   символы-> вертикальный motion blur при падении, sunburst + маскированный
//             по альфе блик + искры на выигрыше, глинты в простое
//   герой  -> аура ки, периодическое ката с послеобразами и ударной волной,
//             «зарядка» во время спина
//   логотип-> слэм-вход после прелоадера, блик по буквам, искорки
//   попапы -> лучи, побуквенный вход, счётчик суммы, монетный дождь, тряска
//
// Всё, что рисуется частицами, живёт на двух канвасах: под сценой (фон) и над
// затемнением, но под попапом (искры, монеты, ударные волны).
(() => {
  'use strict';

  const ASSET = 'img/uniqorn-shaolin-struggles';
  const screen = document.getElementById('screen');
  const stage = document.getElementById('stage');
  const bgLayer = document.getElementById('bgLayer');
  const hero = document.getElementById('hero');
  const reel = document.querySelector('.reel');
  const grid = document.getElementById('reelGrid');
  const logo = document.querySelector('.logo');
  if (!screen || !stage) return;

  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DPR = Math.min(window.devicePixelRatio || 1, 1.5);
  const isPortrait = () => window.matchMedia('(orientation: portrait)').matches;
  const stageScale = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale')) || 1;
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

  // Вертикальный motion blur для падающих лент — SVG-фильтр, CSS blur()
  // размывает во все стороны и превращает символ в кашу.
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '0');
  svg.setAttribute('height', '0');
  svg.style.position = 'absolute';
  svg.innerHTML = '<filter id="fxVBlur" x="0" y="-20%" width="100%" height="140%"><feGaussianBlur stdDeviation="0 9"/></filter>';
  document.body.appendChild(svg);

  // ===========================================================================
  // Канвасы и частицы
  // ===========================================================================

  function makeCanvas(cls, before) {
    const c = document.createElement('canvas');
    c.className = cls;
    if (before) screen.insertBefore(c, before);
    else screen.appendChild(c);
    return { c, ctx: c.getContext('2d'), w: 0, h: 0, list: [] };
  }
  const bgCv = makeCanvas('fx-canvas fx-canvas--bg', stage);
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

  // Заранее отрисованные спрайты: drawImage по готовому градиенту в разы
  // дешевле, чем строить radialGradient на каждую частицу каждый кадр.
  const spriteCache = new Map();
  function glowSprite(color) {
    if (spriteCache.has(color)) return spriteCache.get(color);
    const s = document.createElement('canvas');
    s.width = s.height = 64;
    const g = s.getContext('2d');
    const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0, 'rgba(255,255,255,1)');
    grd.addColorStop(0.18, color);
    grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 64, 64);
    spriteCache.set(color, s);
    return s;
  }
  function petalSprite(hue) {
    const key = `petal${hue}`;
    if (spriteCache.has(key)) return spriteCache.get(key);
    const s = document.createElement('canvas');
    s.width = 40;
    s.height = 28;
    const g = s.getContext('2d');
    const grd = g.createLinearGradient(0, 0, 40, 28);
    grd.addColorStop(0, `hsl(${hue}, 90%, 92%)`);
    grd.addColorStop(1, `hsl(${hue}, 75%, 70%)`);
    g.fillStyle = grd;
    g.beginPath();
    g.moveTo(2, 14);
    g.bezierCurveTo(10, 0, 30, 0, 38, 10);
    g.lineTo(33, 14);
    g.lineTo(38, 18);
    g.bezierCurveTo(30, 28, 10, 28, 2, 14);
    g.fill();
    spriteCache.set(key, s);
    return s;
  }
  const coinImg = new Image();
  coinImg.src = `${ASSET}/symbols/coin.png`;

  // --- Типы частиц -------------------------------------------------------------
  // Каждая частица: {kind, x, y, vx, vy, life, max, ...}; update/draw по kind.

  function spawnSparks(cv, x, y, n, opts = {}) {
    const colors = opts.colors || ['#ffe9a0', '#ffcf5a', '#fff6d8', '#ff9a3c'];
    const sp = (opts.speed || 1) * stageScale() * 2.2;
    for (let i = 0; i < n; i++) {
      const a = opts.angle != null ? opts.angle + rnd(-opts.spread, opts.spread) : rnd(0, Math.PI * 2);
      const v = rnd(4, 13) * sp;
      cv.list.push({
        kind: 'spark', x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v,
        life: 0, max: rnd(28, 55), color: pick(colors), w: rnd(1.5, 3.2) * stageScale() * 2,
        g: (opts.gravity ?? 0.25) * stageScale() * 2, drag: 0.94,
      });
    }
  }
  function spawnRing(cv, x, y, opts = {}) {
    cv.list.push({
      kind: 'ring', x, y, life: 0, max: opts.max || 32,
      r0: (opts.r0 || 10) * stageScale() * 2, r1: (opts.r1 || 140) * stageScale() * 2,
      color: opts.color || 'rgba(255, 220, 140, 1)', width: (opts.width || 10) * stageScale() * 2,
    });
  }
  function spawnFlash(cv, x, y, opts = {}) {
    cv.list.push({
      kind: 'flash', x, y, life: 0, max: opts.max || 18,
      r: (opts.r || 160) * stageScale() * 2, color: opts.color || 'rgba(255, 236, 170, 0.9)',
    });
  }
  function spawnCoins(cv, n, opts = {}) {
    const s = stageScale() * 2;
    for (let i = 0; i < n; i++) {
      const fromBottom = opts.fountain !== false && i % 3 !== 0;
      const size = rnd(34, 62) * s;
      const p = {
        kind: 'coin', life: 0, max: rnd(140, 220), size,
        spin: rnd(0, Math.PI * 2), spinV: rnd(0.12, 0.3) * (Math.random() < 0.5 ? -1 : 1),
        rot: rnd(-0.6, 0.6), rotV: rnd(-0.05, 0.05), g: 0.42 * s, delay: (i / n) * (opts.spreadFrames || 50),
      };
      if (fromBottom) {
        p.x = cv.w * rnd(0.15, 0.85);
        p.y = cv.h + size;
        p.vx = rnd(-5, 5) * s;
        p.vy = -rnd(17, 27) * s;
      } else {
        p.x = rnd(0, cv.w);
        p.y = -size - rnd(0, cv.h * 0.3);
        p.vx = rnd(-1.5, 1.5) * s;
        p.vy = rnd(2, 7) * s;
      }
      cv.list.push(p);
    }
  }
  // Поток света от монеты к коллектору: квадратичная кривая с хвостом.
  function spawnStream(cv, from, to, opts = {}) {
    const n = opts.count || 7;
    for (let i = 0; i < n; i++) {
      const mx = (from.x + to.x) / 2 + rnd(-1, 1) * 120 * stageScale();
      const my = Math.min(from.y, to.y) - rnd(60, 160) * stageScale();
      cv.list.push({
        kind: 'stream', x: from.x, y: from.y, fx: from.x, fy: from.y, tx: to.x, ty: to.y, mx, my,
        life: -i * 2.5, max: opts.max || 34, trail: [], color: opts.color || '#ffd77a',
        onArrive: i === n - 1 ? opts.onArrive : null,
      });
    }
  }
  function spawnInward(cv, cx, cy, radius, n) {
    for (let i = 0; i < n; i++) {
      const a = rnd(0, Math.PI * 2);
      const r = radius * rnd(0.8, 1.3);
      cv.list.push({
        kind: 'inward', x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r, cx, cy,
        life: 0, max: rnd(30, 46), color: pick(['#fff1b8', '#ffcf5a', '#ff8fd0', '#8fe8ff']),
        size: rnd(10, 22) * stageScale() * 2,
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
        if (p.onArrive) p.onArrive();
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
        case 'ring': {
          const e = 1 - Math.pow(1 - t, 3);
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = (1 - t) * 0.9;
          ctx.strokeStyle = p.color;
          ctx.lineWidth = Math.max(0.5, p.width * (1 - t));
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r0 + (p.r1 - p.r0) * e, 0, Math.PI * 2);
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
        case 'coin': {
          if (p.delay > 0) { p.delay -= 1; p.life -= 1; break; }
          p.vy += p.g;
          p.vx *= 0.995;
          p.x += p.vx;
          p.y += p.vy;
          p.spin += p.spinV;
          p.rot += p.rotV;
          if (p.y > cv.h + p.size * 2 && p.vy > 0) { p.life = p.max; break; }
          const sx = Math.cos(p.spin);
          ctx.globalCompositeOperation = 'source-over';
          ctx.globalAlpha = t > 0.85 ? (1 - t) / 0.15 : 1;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          ctx.scale(Math.max(0.08, Math.abs(sx)), 1);
          if (coinImg.complete && coinImg.naturalWidth) {
            ctx.drawImage(coinImg, -p.size / 2, -p.size / 2, p.size, p.size);
          }
          ctx.restore();
          // Блик на ребре: когда монета смотрит в камеру, она вспыхивает.
          if (Math.abs(sx) > 0.96) {
            ctx.globalCompositeOperation = 'lighter';
            ctx.globalAlpha = 0.55;
            const s = p.size * 0.9;
            ctx.drawImage(glowSprite('rgba(255,230,150,0.8)'), p.x - s / 2, p.y - s / 2, s, s);
          }
          break;
        }
        case 'stream': {
          const e = t * t * (3 - 2 * t);
          const u = 1 - e;
          p.x = u * u * p.fx + 2 * u * e * p.mx + e * e * p.tx;
          p.y = u * u * p.fy + 2 * u * e * p.my + e * e * p.ty;
          p.trail.push([p.x, p.y]);
          if (p.trail.length > 9) p.trail.shift();
          ctx.globalCompositeOperation = 'lighter';
          const spr = glowSprite(p.color);
          p.trail.forEach(([x, y], k) => {
            const a = (k + 1) / p.trail.length;
            const s = 46 * stageScale() * 2 * a;
            ctx.globalAlpha = a * 0.9;
            ctx.drawImage(spr, x - s / 2, y - s / 2, s, s);
          });
          break;
        }
        case 'inward': {
          const e = t * t;
          const x = p.x + (p.cx - p.x) * e;
          const y = p.y + (p.cy - p.y) * e;
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = Math.sin(t * Math.PI);
          const s = p.size;
          ctx.drawImage(glowSprite(p.color), x - s / 2, y - s / 2, s, s);
          break;
        }
        // ---- фон ----
        case 'petal': {
          p.t += 1;
          p.x += p.vx + Math.sin(p.t * p.swayF + p.ph) * p.sway;
          p.y += p.vy;
          p.rot += p.rotV;
          p.flip += p.flipV;
          p.life = 1; // вечные: перерождаются сверху
          if (p.y > cv.h + 40 || p.x < -60 || p.x > cv.w + 60) resetPetal(cv, p, false);
          ctx.globalCompositeOperation = 'source-over';
          ctx.globalAlpha = p.alpha;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          ctx.scale(p.size, p.size * Math.cos(p.flip));
          ctx.drawImage(p.spr, -20, -14);
          ctx.restore();
          break;
        }
        case 'mote': {
          p.t += 1;
          p.x += p.vx + Math.sin(p.t * 0.02 + p.ph) * 0.3;
          p.y += p.vy;
          p.life = 1;
          if (p.y < -20 || p.y > cv.h + 20) resetMote(cv, p);
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = p.alpha * (0.55 + 0.45 * Math.sin(p.t * p.tw + p.ph));
          const s = p.size;
          ctx.drawImage(glowSprite(p.color), p.x - s / 2, p.y - s / 2, s, s);
          break;
        }
        case 'ember': {
          p.vy -= 0.02;
          p.x += p.vx + Math.sin(p.life * 0.15 + p.ph) * 0.6;
          p.y += p.vy;
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = 1 - t;
          const s = p.size * (1 - t * 0.5);
          ctx.drawImage(glowSprite(p.color), p.x - s / 2, p.y - s / 2, s, s);
          break;
        }
        case 'rocket': {
          const px = p.x;
          const py = p.y;
          p.x += p.vx;
          p.y += p.vy;
          p.vy *= 0.985;
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = 0.9;
          ctx.strokeStyle = 'rgba(255,220,160,0.8)';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(px - p.vx * 3, py - p.vy * 3);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
          if (p.y <= p.ty) {
            p.life = p.max + 1;
            explodeFirework(cv, p.x, p.y);
          }
          break;
        }
        case 'fw': {
          p.vx *= 0.965;
          p.vy = p.vy * 0.965 + 0.05;
          const px = p.x;
          const py = p.y;
          p.x += p.vx;
          p.y += p.vy;
          ctx.globalCompositeOperation = 'lighter';
          ctx.globalAlpha = (1 - t) * (t > 0.6 ? 0.6 + 0.4 * Math.sin(p.life * 0.9) : 1);
          ctx.strokeStyle = p.color;
          ctx.lineWidth = 2.2;
          ctx.beginPath();
          ctx.moveTo(px - p.vx * 2.5, py - p.vy * 2.5);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
          const s = 12;
          ctx.drawImage(glowSprite(p.color), p.x - s / 2, p.y - s / 2, s, s);
          break;
        }
        default:
          break;
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  // --- Фоновые частицы -----------------------------------------------------------
  function resetPetal(cv, p, anywhere) {
    p.x = rnd(-40, cv.w + 40);
    p.y = anywhere ? rnd(0, cv.h) : rnd(-80, -20);
    p.vx = rnd(0.3, 1.4);
    p.vy = rnd(0.7, 1.9);
    p.size = rnd(0.45, 1.05) * Math.max(0.6, stageScale() * 1.6);
    p.alpha = rnd(0.55, 0.95);
  }
  function resetMote(cv, p) {
    p.x = rnd(0, cv.w);
    p.y = rnd(cv.h * 0.2, cv.h);
    p.vy = rnd(-0.35, -0.08);
  }
  function makePetal(cv) {
    const p = {
      kind: 'petal', life: 0, max: Infinity, t: 0, ph: rnd(0, 6), swayF: rnd(0.01, 0.03), sway: rnd(0.4, 1.2),
      rot: rnd(0, 6), rotV: rnd(-0.03, 0.03), flip: rnd(0, 6), flipV: rnd(0.02, 0.06), spr: petalSprite(rnd(330, 350)),
    };
    resetPetal(cv, p, true);
    return p;
  }
  function makeMote(cv, color) {
    const p = {
      kind: 'mote', life: 0, max: Infinity, t: rnd(0, 500), ph: rnd(0, 6), tw: rnd(0.03, 0.08),
      vx: rnd(-0.15, 0.15), size: rnd(6, 16), alpha: rnd(0.35, 0.8), color,
    };
    resetMote(cv, p);
    return p;
  }
  function explodeFirework(cv, x, y) {
    const palette = pick([
      ['#ffd25a', '#fff1b0'], ['#ff5fa8', '#ffc2e1'], ['#6fe3ff', '#d4f7ff'], ['#ff7b3a', '#ffd25a'],
    ]);
    const n = isPortrait() ? 46 : 64;
    const power = rnd(3.2, 5.2);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rnd(-0.05, 0.05);
      const v = power * rnd(0.75, 1.05);
      cv.list.push({ kind: 'fw', x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 0, max: rnd(55, 80), color: pick(palette) });
    }
    cv.list.push({ kind: 'flash', x, y, life: 0, max: 16, r: 70, color: 'rgba(255,230,190,0.5)' });
  }

  // ===========================================================================
  // Фон: риг, привязанный к картинке (object-fit: cover) + Ken Burns
  // ===========================================================================

  // Координаты в % от самой картинки фона: фонари, жаровни, солнце/луна.
  const BG_MAP = {
    bg_base: {
      sun: [49, 34], petals: true,
      lanterns: [[18.9, 17.1], [25.3, 20.1], [31.3, 21.9], [37.6, 23.1], [44, 23.7], [50.7, 23.7], [57.3, 23.3], [63.9, 22.1], [70, 21], [77.8, 17.6], [84.2, 15.3]],
    },
    bg_base_mob: {
      sun: [49.4, 37.9], petals: true,
      lanterns: [[6.8, 23.6], [20.3, 26.4], [35.3, 28.3], [51, 29.6], [66.5, 29.6], [80.5, 28.3], [93.5, 26]],
    },
    bg_bonus: {
      moon: [62, 19], fireworks: { x: [14, 82], y: [6, 30] },
      lanterns: [[5, 14.7], [11.7, 24], [17, 31], [4, 38], [89, 17.6], [82.8, 26.5], [97.4, 38]],
      braziers: [[9.3, 69], [90.7, 69], [33.6, 74], [65.4, 74]],
    },
    bg_bonus_mob: {
      moon: [51.4, 27], fireworks: { x: [10, 90], y: [3, 24] },
      lanterns: [[8.6, 13.6], [17.7, 16.9], [28.6, 15], [39, 15], [50.6, 11], [61, 8.9], [74.8, 8.9], [87, 5.7],
        [7.8, 29.7], [16.9, 29.7], [26.5, 29.7], [35.6, 29.7], [63, 29.7], [72, 29.7], [81.3, 29.7], [89.6, 29.7]],
      braziers: [[7.8, 75.4], [94.8, 75.4], [29, 72], [65, 72]],
    },
  };

  const rig = el('div', 'fx-bgrig');
  screen.insertBefore(rig, stage);
  bgLayer.classList.add('fx-kenburns');
  rig.classList.add('fx-kenburns');

  let bgKey = 'bg_base';
  let coverRect = { x: 0, y: 0, w: 1, h: 1 };
  let nextFirework = 0;

  function computeCover() {
    const nw = bgLayer.naturalWidth || 2704;
    const nh = bgLayer.naturalHeight || 1316;
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
    if (cfg.sun) {
      place(el('div', 'fx-godrays', rig), cfg.sun);
      place(el('div', 'fx-sunglow', rig), cfg.sun);
    }
    if (cfg.moon) {
      place(el('div', 'fx-moonrays', rig), cfg.moon);
      place(el('div', 'fx-moonglow', rig), cfg.moon);
    }
    for (const pt of cfg.lanterns || []) {
      const l = place(el('div', 'fx-lantern', rig), pt);
      l.style.animationDuration = `${rnd(1.6, 3.4).toFixed(2)}s`;
      l.style.animationDelay = `${-rnd(0, 3).toFixed(2)}s`;
    }
    for (const pt of cfg.braziers || []) {
      const b = place(el('div', 'fx-brazier', rig), pt);
      b.style.animationDelay = `${-rnd(0, 1).toFixed(2)}s`;
    }
    el('div', 'fx-vignette', rig);

    // Фоновые частицы под новый фон.
    bgCv.list.length = 0;
    if (REDUCED) return;
    const small = isPortrait();
    if (cfg.petals) {
      for (let i = 0; i < (small ? 16 : 26); i++) bgCv.list.push(makePetal(bgCv));
      for (let i = 0; i < (small ? 14 : 24); i++) bgCv.list.push(makeMote(bgCv, 'rgba(255,214,140,0.7)'));
    } else {
      for (let i = 0; i < (small ? 12 : 20); i++) bgCv.list.push(makeMote(bgCv, 'rgba(255,170,90,0.7)'));
    }
    nextFirework = performance.now() + 600;
  }
  bgLayer.addEventListener('load', buildRig);

  function tickBackground(now) {
    const cfg = BG_MAP[bgKey] || {};
    // Угли над жаровнями — непрерывный подъём.
    if (cfg.braziers && Math.random() < 0.55) {
      const pt = bgPoint(pick(cfg.braziers));
      bgCv.list.push({
        kind: 'ember', x: pt.x + rnd(-14, 14), y: pt.y - rnd(0, 20), vx: rnd(-0.4, 0.4), vy: rnd(-1.6, -0.6),
        life: 0, max: rnd(60, 110), ph: rnd(0, 6), size: rnd(5, 11), color: pick(['rgba(255,150,60,0.9)', 'rgba(255,210,90,0.9)']),
      });
    }
    if (cfg.fireworks && now > nextFirework) {
      nextFirework = now + rnd(900, 2300);
      const target = bgPoint([rnd(...cfg.fireworks.x), rnd(...cfg.fireworks.y)]);
      bgCv.list.push({
        kind: 'rocket', x: target.x + rnd(-40, 40), y: coverRect.y + coverRect.h * 0.55, vx: rnd(-0.4, 0.4),
        vy: -rnd(9, 12), ty: target.y, life: 0, max: 400,
      });
    }
  }

  // ===========================================================================
  // Рамка барабанов
  // ===========================================================================
  let frameChase;
  let frameChaseFast;
  function buildFrame() {
    if (!reel || reel.querySelector('.fx-frame-chase')) return;
    const back = el('div', 'fx-frame-aura');
    reel.insertBefore(back, reel.firstChild);
    frameChase = el('div', 'fx-frame-ring fx-frame-chase', reel);
    frameChaseFast = el('div', 'fx-frame-ring fx-frame-chase fx-frame-chase--fast', reel);
    el('div', 'fx-frame-ring fx-frame-sweep', reel);
    el('div', 'fx-window-depth', reel);
    for (const corner of reel.querySelectorAll('.reel__corner')) {
      el('span', 'fx-gem', corner);
      el('span', 'fx-gem-star', corner);
    }
    // Плашки джекпотов, кнопка покупки и счётчик — тот же лак, тот же блик.
    for (const plaque of document.querySelectorAll('.jp, .sign-buy-bonus, .respin-counter')) {
      if (!plaque.querySelector('.fx-sheen')) el('span', 'fx-sheen', plaque);
    }
    document.querySelectorAll('.jp').forEach((p, i) => p.style.setProperty('--fx-delay', `${i * 0.35}s`));
  }

  // ===========================================================================
  // Логотип
  // ===========================================================================
  function buildLogo() {
    if (!logo || logo.querySelector('.fx-logo-shine')) return;
    const img = logo.querySelector('.logo__img');
    const glow = el('div', 'fx-logo-glow');
    logo.insertBefore(glow, img);
    const shine = el('div', 'fx-logo-shine', logo);
    shine.style.setProperty('--fx-mask', `url("${img.getAttribute('src')}")`);
    for (let i = 0; i < 7; i++) {
      const s = el('span', 'fx-twinkle', logo);
      placeTwinkle(s);
      s.style.animationDelay = `${(i * 0.43).toFixed(2)}s`;
      s.addEventListener('animationiteration', () => placeTwinkle(s));
    }
  }
  function placeTwinkle(s) {
    // Звёздочки садятся на кромки букв: верхняя треть «UNIQORN» и строка снизу.
    const top = Math.random() < 0.65;
    s.style.left = `${rnd(8, 92)}%`;
    s.style.top = `${top ? rnd(6, 30) : rnd(64, 82)}%`;
    s.style.setProperty('--fx-s', rnd(0.6, 1.2).toFixed(2));
  }
  function logoEntrance() {
    if (!logo) return;
    restartClass(logo, 'fx-logo-enter', 1400);
    setTimeout(() => {
      const r = rectInScreen(logo);
      spawnFlash(fgCv, r.cx, r.cy, { r: 320, max: 22 });
      spawnRing(fgCv, r.cx, r.cy, { r0: 40, r1: 420, width: 16, max: 34 });
      spawnSparks(fgCv, r.cx, r.cy + r.h * 0.2, 46, { speed: 1.3 });
      shake('s');
    }, 470);
  }

  // ===========================================================================
  // Герой
  // ===========================================================================
  let heroAura;
  function buildHero() {
    if (!hero || heroAura) return;
    heroAura = el('div', 'fx-hero-aura');
    el('span', 'fx-hero-aura__ki', heroAura);
    el('span', 'fx-hero-aura__glow', heroAura);
    stage.insertBefore(heroAura, hero);
    placeHeroAura();
  }
  function placeHeroAura() {
    if (!heroAura || !hero.offsetHeight) return;
    // Габарит героя в координатах канваса сцены (offset* не видят transform).
    Object.assign(heroAura.style, {
      left: `${hero.offsetLeft}px`, top: `${hero.offsetTop}px`,
      width: `${hero.offsetWidth}px`, height: `${hero.offsetHeight}px`,
    });
  }
  let strikeBusy = false;
  function heroStrike(power = 1) {
    if (!hero || strikeBusy || REDUCED) return;
    strikeBusy = true;
    hero.style.setProperty('--fx-dir', '1');
    hero.style.setProperty('--fx-reach', isPortrait() ? '3%' : '7%');
    restartClass(hero, 'fx-strike', 780);
    setTimeout(() => {
      // Послеобразы: два полупрозрачных клона «отстают» от выпада.
      for (let i = 0; i < 2; i++) {
        const g = hero.cloneNode(false);
        g.removeAttribute('id');
        g.className = 'obj fx-hero-ghost';
        Object.assign(g.style, {
          left: `${hero.offsetLeft}px`, top: `${hero.offsetTop}px`,
          width: `${hero.offsetWidth}px`, height: `${hero.offsetHeight}px`,
          animationDelay: `${i * 70}ms`,
        });
        g.style.setProperty('--fx-hue', `${i ? 300 : 40}deg`);
        stage.insertBefore(g, hero);
        setTimeout(() => g.remove(), 700);
      }
    }, 230);
    setTimeout(() => {
      // Удар: кулак ~ (73%, 31%) картинки героя.
      const r = hero.getBoundingClientRect();
      const s = screen.getBoundingClientRect();
      const x = r.left - s.left + r.width * 0.78;
      const y = r.top - s.top + r.height * 0.3;
      spawnFlash(fgCv, x, y, { r: 120 * power, max: 14 });
      spawnRing(fgCv, x, y, { r0: 8, r1: 120 * power, width: 8, max: 22 });
      spawnSparks(fgCv, x, y, Math.round(16 * power), { angle: 0, spread: 0.9, speed: 1.1 });
      if (!isPortrait() && reel) restartClass(reel, 'fx-hit', 320);
    }, 400);
    setTimeout(() => { strikeBusy = false; }, 820);
  }

  // ===========================================================================
  // Символы
  // ===========================================================================
  function rectInScreen(node) {
    const r = node.getBoundingClientRect();
    const s = screen.getBoundingClientRect();
    return { x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height, cx: r.left - s.left + r.width / 2, cy: r.top - s.top + r.height / 2 };
  }
  function playShine(cell) {
    const img = cell && cell.querySelector(':scope > img');
    if (!img || !img.getAttribute('src') || img.style.visibility === 'hidden') return;
    let sh = cell.querySelector(':scope > .fx-shine');
    if (!sh) {
      sh = el('span', 'fx-shine', cell);
    }
    sh.style.setProperty('--fx-mask', `url("${img.getAttribute('src')}")`);
    restartClass(sh, 'is-on', 900);
  }
  function addBurst(cell, color) {
    if (!cell || cell.querySelector(':scope > .fx-burst')) return;
    const b = document.createElement('span');
    b.className = 'fx-burst';
    if (color) b.style.setProperty('--fx-burst', color);
    cell.insertBefore(b, cell.firstChild);
  }
  function clearBursts() {
    if (!grid) return;
    grid.querySelectorAll('.fx-burst').forEach((b) => b.remove());
  }
  const TIER_COLORS = { mini: '#c58bff', minor: '#6fb5ff', major: '#4fe39a', grand: '#ff6a5c' };
  function tierOf(code) {
    const m = /^coin_(\w+)$/.exec(code || '');
    return m ? m[1] : null;
  }

  // Глинты в простое: раз в пару секунд блик пробегает по случайному символу,
  // монеты и коллектор — чаще (они и так «главные» на поле).
  let busy = false;
  function idleGlint() {
    if (busy || document.hidden || !grid) return;
    const cells = [...grid.querySelectorAll('.reel__cell')].filter((c) => !c.classList.contains('is-dimmed'));
    if (!cells.length) return;
    const money = cells.filter((c) => c.classList.contains('is-money'));
    const target = money.length && Math.random() < 0.6 ? pick(money) : pick(cells);
    playShine(target);
  }

  // ===========================================================================
  // Тряска / вспышка экрана
  // ===========================================================================
  function shake(size = 's') {
    if (REDUCED) return;
    screen.classList.remove('fx-shake-s', 'fx-shake-m', 'fx-shake-l');
    void screen.offsetWidth;
    screen.classList.add(`fx-shake-${size}`);
    clearTimeout(screen.__fxShake);
    screen.__fxShake = setTimeout(() => screen.classList.remove(`fx-shake-${size}`), 700);
  }
  const flashLayer = el('div', 'fx-screen-flash', screen);
  function screenFlash(color = '#fff6d8', strength = 0.85) {
    flashLayer.style.setProperty('--fx-flash', color);
    flashLayer.style.setProperty('--fx-flash-a', strength);
    restartClass(flashLayer, 'is-on', 700);
  }

  // ===========================================================================
  // Попапы
  // ===========================================================================
  const POPUP_FX = {
    bigWin: { coins: 46, shake: 's', rays: '#ffcf5a' },
    megaWin: { coins: 90, shake: 'm', rays: '#ffb347', flash: true },
    epicWin: { coins: 150, shake: 'l', rays: '#ff7ad9', flash: true },
    holdWinIntro: { coins: 30, shake: 'm', rays: '#ffe08a', flash: true },
    holdWinTotal: { coins: 100, shake: 'm', rays: '#ffcf5a', flash: true },
  };

  function attachPopupFx(node, cfg, amount, holdMs) {
    // Лучи — отдельный слой за карточкой (у карточки свой stacking context,
    // ребёнок с z-index:-1 лёг бы поверх её фона).
    const rays = el('div', 'fx-popup-rays', screen);
    rays.style.setProperty('--fx-ray', cfg.rays || '#ffcf5a');
    requestAnimationFrame(() => rays.classList.add('is-in'));
    el('span', 'fx-popup-sheen', node);

    // Заголовок — побуквенный вход.
    const title = node.querySelector('.game-popup__title');
    if (title && !REDUCED) {
      const text = title.textContent;
      title.textContent = '';
      [...text].forEach((ch, i) => {
        const s = el('span', 'fx-ch', title);
        s.textContent = ch === ' ' ? ' ' : ch;
        s.style.animationDelay = `${120 + i * 55}ms`;
      });
    }
    // Счётчик суммы: от нуля до итога за ~60% времени показа.
    const amountEl = node.querySelector('.game-popup__amount');
    if (amountEl && Number(amount) > 0 && !REDUCED) {
      const target = Number(amount);
      const dur = Math.min(1800, (holdMs || 2500) * 0.6);
      const t0 = performance.now() + 250;
      const step = (now) => {
        const t = Math.min(1, Math.max(0, (now - t0) / dur));
        const e = 1 - Math.pow(1 - t, 3);
        amountEl.textContent = Math.round(target * e).toLocaleString('en-US');
        if (t < 1 && node.isConnected) requestAnimationFrame(step);
        else if (t >= 1) restartClass(amountEl, 'fx-amount-done', 600);
      };
      amountEl.textContent = '0';
      requestAnimationFrame(step);
    }

    // Уборка лучей вместе с карточкой.
    const watch = () => {
      if (!node.isConnected || node.classList.contains('is-out')) {
        rays.classList.remove('is-in');
        setTimeout(() => rays.remove(), 420);
        return;
      }
      requestAnimationFrame(watch);
    };
    requestAnimationFrame(watch);

    if (cfg.flash) screenFlash();
    if (cfg.shake) setTimeout(() => shake(cfg.shake), 120);
    if (cfg.coins && !REDUCED) spawnCoins(fgCv, isPortrait() ? Math.round(cfg.coins * 0.6) : cfg.coins);
    const c = { x: fgCv.w / 2, y: fgCv.h / 2 };
    spawnRing(fgCv, c.x, c.y, { r0: 60, r1: 620, width: 18, max: 38 });
    spawnSparks(fgCv, c.x, c.y, 50, { speed: 1.6 });
    if (logo) restartClass(logo, 'fx-logo-pulse', 900);
    heroStrike(1.4);
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
      // Вход логотипа — после того, как прелоадер ушёл с экрана.
      setTimeout(logoEntrance, 450);
    },

    spinStart() {
      busy = true;
      landedCols = 0;
      clearBursts();
      if (reel) {
        reel.classList.add('fx-spin');
        reel.classList.remove('fx-win', 'fx-antic');
      }
      grid && grid.querySelectorAll('.reel__strip').forEach((s) => s.classList.add('fx-blur'));
      if (heroAura) heroAura.classList.add('is-charged');
      if (hero && !REDUCED) {
        const r = rectInScreen(hero);
        spawnInward(fgCv, r.cx, r.y + r.h * 0.45, r.h * 0.55, 18);
      }
    },

    colDrop(col) {
      const strip = grid && grid.querySelectorAll('.reel__strip')[col];
      if (strip) strip.classList.add('fx-blur');
    },

    colLand(col) {
      const strips = grid ? grid.querySelectorAll('.reel__strip') : [];
      if (strips[col]) strips[col].classList.remove('fx-blur');
      const colEl = grid && grid.querySelectorAll('.reel__col')[col];
      if (colEl) {
        restartClass(colEl, 'fx-col-impact', 420);
        const r = rectInScreen(colEl);
        spawnSparks(fgCv, r.cx, r.y + r.h, 10, { angle: -Math.PI / 2, spread: 1.1, speed: 0.8 });
      }
      if (reel) restartClass(reel, 'fx-land', 220);
      landedCols += 1;
      if (landedCols >= 3) {
        busy = false;
        reel && reel.classList.remove('fx-spin', 'fx-antic');
        heroAura && heroAura.classList.remove('is-charged');
      }
    },

    anticipation(col) {
      if (reel) reel.classList.add('fx-antic');
      const colEl = grid && grid.querySelectorAll('.reel__col')[col];
      if (colEl) {
        const r = rectInScreen(colEl);
        spawnRing(fgCv, r.cx, r.cy, { r0: 30, r1: 260, width: 10, color: 'rgba(255,140,60,1)', max: 30 });
      }
      if (logo) restartClass(logo, 'fx-logo-pulse', 900);
    },

    win(infos) {
      if (!infos || !infos.length) return;
      if (reel) {
        reel.classList.add('fx-win');
        clearTimeout(reel.__fxWin);
        reel.__fxWin = setTimeout(() => reel.classList.remove('fx-win'), 1600);
      }
      for (const info of infos) {
        const tier = tierOf(info.symbol);
        addBurst(info.cell, tier ? TIER_COLORS[tier] : null);
        const r = rectInScreen(info.cell);
        spawnFlash(fgCv, r.cx, r.cy, { r: 120, max: 16 });
        spawnRing(fgCv, r.cx, r.cy, { r0: 20, r1: 150, width: 7, max: 26 });
      }
      heroStrike(1);
    },

    cellPulse(info) {
      if (!info || !info.cell) return;
      playShine(info.cell);
      const r = rectInScreen(info.cell);
      const tier = tierOf(info.symbol);
      spawnSparks(fgCv, r.cx, r.cy, 9, tier ? { colors: [TIER_COLORS[tier], '#fff'] } : {});
    },

    popup(key, node, amount, holdMs) {
      const cfg = POPUP_FX[key];
      if (!cfg || !node) return;
      attachPopupFx(node, cfg, amount, holdMs);
    },

    jackpot(tier, node) {
      const color = TIER_COLORS[tier] || '#ffcf5a';
      attachPopupFx(node, { coins: 110, shake: tier === 'grand' ? 'l' : 'm', rays: color, flash: true }, 0, 2200);
      const c = { x: fgCv.w / 2, y: fgCv.h / 2 };
      spawnSparks(fgCv, c.x, c.y, 60, { colors: [color, '#ffffff', '#ffe9a0'], speed: 1.8 });
      screenFlash(color, 0.6);
    },

    bonusEnter() {
      screenFlash('#fff1c2', 1);
      shake('m');
      const c = { x: fgCv.w / 2, y: fgCv.h / 2 };
      spawnRing(fgCv, c.x, c.y, { r0: 40, r1: 900, width: 24, max: 40 });
      spawnSparks(fgCv, c.x, c.y, 70, { speed: 2 });
      setTimeout(logoEntrance, 200);
    },

    bonusLeave() {
      screenFlash('#ffe2a8', 0.6);
    },

    coinLand(info, code) {
      if (!info || !info.cell || code === 'blank') return;
      const tier = tierOf(code);
      const color = tier ? TIER_COLORS[tier] : null;
      const r = rectInScreen(info.cell);
      restartClass(info.cell, 'fx-pop', 520);
      spawnFlash(fgCv, r.cx, r.cy, { r: tier ? 220 : 140, max: 18, color: color ? `${color}` : undefined });
      spawnRing(fgCv, r.cx, r.cy, { r0: 30, r1: tier ? 300 : 190, width: 10, max: 28, color: color || undefined });
      spawnSparks(fgCv, r.cx, r.cy, tier ? 36 : 20, color ? { colors: [color, '#fff'] } : {});
      playShine(info.cell);
      if (code === 'collector' || tier) shake(tier === 'grand' ? 'm' : 's');
    },

    // Монеты «текут» к каждому коллектору: новая монета — ко всем
    // коллекторам, новый коллектор — от всех монет к нему.
    collect(landedInfos, allInfos) {
      if (REDUCED) return;
      const collectors = allInfos.filter((i) => i && i.symbol === 'collector');
      const coins = allInfos.filter((i) => i && i.symbol !== 'collector' && i.symbol !== 'blank' && /^coin/.test(i.symbol));
      const pairs = [];
      for (const li of landedInfos) {
        if (!li) continue;
        if (li.symbol === 'collector') coins.forEach((c) => pairs.push([c, li]));
        else collectors.forEach((col) => pairs.push([li, col]));
      }
      pairs.forEach(([from, to], i) => {
        setTimeout(() => {
          const a = rectInScreen(from.cell);
          const b = rectInScreen(to.cell);
          spawnStream(fgCv, { x: a.cx, y: a.cy }, { x: b.cx, y: b.cy }, {
            onArrive: () => {
              spawnFlash(fgCv, b.cx, b.cy, { r: 130, max: 14 });
              spawnSparks(fgCv, b.cx, b.cy, 10);
              restartClass(to.cell, 'fx-pop', 420);
              const lbl = to.cell.querySelector('.coin-value');
              if (lbl) restartClass(lbl, 'fx-bump', 420);
            },
          });
        }, 260 + i * 110);
      });
    },

    respin(value) {
      const c = document.getElementById('respinCounter');
      if (c) restartClass(c, value >= 3 ? 'fx-reset' : 'fx-tick', 500);
    },
  };

  // Публичный API: slot.js зовёт ShaolinFX.hook('name', ...), ошибки FX
  // никогда не должны ронять игру.
  window.ShaolinFX = {
    hook(name, ...args) {
      try {
        if (HOOKS[name]) HOOKS[name](...args);
      } catch (err) {
        console.warn(`[shaolin-fx] ${name} failed:`, err);
      }
    },
  };

  // --- Цикл -------------------------------------------------------------------
  let lastGlint = 0;
  function frame(now) {
    if (!REDUCED) tickBackground(now);
    updateDraw(bgCv);
    updateDraw(fgCv);
    if (now - lastGlint > 1900) {
      lastGlint = now;
      idleGlint();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // Ката героя в простое — раз в 6-9 секунд.
  (function idleKata() {
    setTimeout(() => {
      if (!busy && !document.hidden && !document.querySelector('.game-popup')) heroStrike(0.8);
      idleKata();
    }, rnd(6000, 9000));
  })();

  let resizeRaf = 0;
  window.addEventListener('resize', () => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      sizeCanvases();
      computeCover();
      placeHeroAura();
    });
  });
  sizeCanvases();
})();
