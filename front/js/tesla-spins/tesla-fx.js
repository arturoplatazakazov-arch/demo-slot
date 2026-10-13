// Tesla Spins — живые молнии катушек Теслы (canvas 2D, без арта).
//
// Катушки нарисованы в фоне (img/tesla-spins/img/scene_ext.jpg), а разряды —
// процедурные: ломаная по midpoint displacement, перегенерируется каждые
// ~45мс, поэтому дуга «дрожит», а не ползёт. Рисуется на своём полноэкранном
// канвасе ПОВЕРХ корпуса: молния бьёт от кольца катушки через раму прямо в
// выигравшую ячейку.
//
// Точки берутся из DOM, а не из чисел: на сцене лежат невидимые якоря
// .coil-anchor (кольца тороидов) в координатах дизайн-канваса, и
// getBoundingClientRect даёт их реальное место на экране при любом масштабе и
// раскладке. Цели удара slot.js передаёт уже в экранных пикселях.
//
// API (window.TeslaFX):
//   init(canvasEl)                — запуск; idle-треск колец начинается сразу
//   strike(targets, opts) -> Promise — разряды от обеих катушек в цели
//       targets: [{x, y}] (client px), opts: {duration, power}
//   column(rect, opts) -> Promise — «удар в барабан»: пучок молний сверху вниз
//       по столбцу + удары катушек в его центр (раскрытие вайлда)
//
// В скрытой вкладке rAF не тикает: промисы всё равно резолвятся по таймеру,
// а отрисовка просто догонит, когда вкладка вернётся.

(function () {
  const BOLT_REFRESH_MS = 45;

  let canvas = null;
  let ctx = null;
  let dpr = 1;
  let running = false;
  const effects = new Set(); // активные эффекты: {until, draw(t), bolts...}
  let nextIdleAt = 0;

  function rand(a, b) {
    return a + Math.random() * (b - a);
  }

  function anchors() {
    return [...document.querySelectorAll('.coil-anchor')]
      .map((el) => {
        const r = el.getBoundingClientRect();
        if (!r.width) return null;
        return { x: r.left + r.width / 2, y: r.top + r.height / 2, rx: r.width / 2, ry: r.height / 2 };
      })
      .filter(Boolean);
  }

  // --- геометрия молнии ------------------------------------------------------

  function boltPath(x0, y0, x1, y1, rough, depth) {
    let pts = [[x0, y0], [x1, y1]];
    let disp = rough;
    for (let d = 0; d < depth; d++) {
      const next = [pts[0]];
      for (let i = 0; i < pts.length - 1; i++) {
        const [ax, ay] = pts[i];
        const [bx, by] = pts[i + 1];
        const mx = (ax + bx) / 2;
        const my = (ay + by) / 2;
        const dx = bx - ax;
        const dy = by - ay;
        const len = Math.hypot(dx, dy) || 1;
        const off = rand(-disp, disp);
        next.push([mx - (dy / len) * off, my + (dx / len) * off], pts[i + 1]);
      }
      pts = next;
      disp *= 0.55;
    }
    return pts;
  }

  // Молния с ответвлениями: главный ствол + 1..3 коротких отростка.
  function makeBolt(x0, y0, x1, y1, power = 1) {
    const len = Math.hypot(x1 - x0, y1 - y0);
    const trunk = boltPath(x0, y0, x1, y1, len * 0.2, 7);
    const branches = [];
    const n = Math.round(rand(1, 3) * power);
    for (let i = 0; i < n; i++) {
      const at = trunk[Math.floor(rand(0.2, 0.8) * trunk.length)];
      const ang = Math.atan2(y1 - y0, x1 - x0) + rand(-1.2, 1.2);
      const l = len * rand(0.1, 0.28);
      branches.push(boltPath(at[0], at[1], at[0] + Math.cos(ang) * l, at[1] + Math.sin(ang) * l, l * 0.3, 4));
    }
    return { trunk, branches };
  }

  function strokePath(pts) {
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.stroke();
  }

  // Масштаб дизайн-канваса: толщина и свечение молний задуманы в его пикселях,
  // иначе на телефоне (сцена x0.5) разряд выходит вдвое толще шкафа.
  let stageScale = 1;
  function readStageScale() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale'));
    stageScale = Number.isFinite(v) && v > 0 ? Math.max(0.45, Math.min(1.6, v)) : 1;
  }

  // Три прохода: широкое синее свечение, голубой ореол, белое ядро.
  function drawBolt(bolt, alpha, width) {
    const w = width * dpr * stageScale;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.shadowColor = `rgba(90, 160, 255, ${alpha})`;
    ctx.shadowBlur = 18 * dpr * stageScale;
    ctx.strokeStyle = `rgba(60, 120, 255, ${0.35 * alpha})`;
    ctx.lineWidth = w * 5;
    strokePath(bolt.trunk);
    ctx.shadowBlur = 8 * dpr * stageScale;
    ctx.strokeStyle = `rgba(140, 200, 255, ${0.75 * alpha})`;
    ctx.lineWidth = w * 2;
    strokePath(bolt.trunk);
    for (const b of bolt.branches) strokePath(b);
    ctx.shadowBlur = 0;
    ctx.strokeStyle = `rgba(245, 250, 255, ${alpha})`;
    ctx.lineWidth = w * 0.8;
    strokePath(bolt.trunk);
    ctx.lineWidth = w * 0.45;
    for (const b of bolt.branches) strokePath(b);
    ctx.restore();
  }

  function drawFlash(x, y, r, alpha) {
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(230, 245, 255, ${0.9 * alpha})`);
    g.addColorStop(0.25, `rgba(110, 180, 255, ${0.5 * alpha})`);
    g.addColorStop(1, 'rgba(40, 90, 255, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
    ctx.restore();
  }

  // Подсветка тороида: яркий эллипс поверх нарисованного кольца.
  function drawRing(a, alpha) {
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.shadowColor = `rgba(120, 190, 255, ${alpha})`;
    ctx.shadowBlur = 26 * dpr * stageScale;
    ctx.strokeStyle = `rgba(170, 215, 255, ${0.8 * alpha})`;
    ctx.lineWidth = 4 * dpr * stageScale;
    ctx.beginPath();
    ctx.ellipse(a.x * dpr, a.y * dpr, a.rx * dpr, a.ry * dpr, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  // Точка на кольце тороида, ближайшая к цели: молния срывается с края кольца,
  // а не из его центра.
  function ringPoint(a, tx, ty) {
    const ang = Math.atan2((ty - a.y) / a.ry, (tx - a.x) / a.rx);
    return [a.x + Math.cos(ang) * a.rx, a.y + Math.sin(ang) * a.ry];
  }

  // --- эффекты ---------------------------------------------------------------

  function addEffect(fx) {
    effects.add(fx);
    ensureLoop();
    return new Promise((resolve) => {
      fx.resolve = resolve;
      // таймер-дублёр: в скрытой вкладке кадров нет
      setTimeout(() => {
        if (effects.delete(fx)) resolve();
      }, fx.until - performance.now() + 30);
    });
  }

  function strike(targets, { duration = 900, power = 1 } = {}) {
    const coils = anchors();
    if (!canvas || !coils.length || !targets || !targets.length) return Promise.resolve();
    const start = performance.now();
    let bolts = [];
    let lastGen = 0;
    const regen = () => {
      bolts = [];
      targets.forEach((t) => {
        // одна цель или крупный выигрыш — бьют обе катушки, иначе ближайшая
        const order = coils.slice().sort((a, b) => Math.abs(a.x - t.x) - Math.abs(b.x - t.x));
        const from = power > 1 || targets.length === 1 ? order : [order[0]];
        for (const c of from) {
          const [sx, sy] = ringPoint(c, t.x, t.y);
          bolts.push({ coil: c, bolt: makeBolt(sx * dpr, sy * dpr, t.x * dpr, t.y * dpr, power) });
        }
      });
    };
    return addEffect({
      until: start + duration,
      draw(now) {
        const k = (now - start) / duration;
        if (now - lastGen > BOLT_REFRESH_MS) {
          regen();
          lastGen = now;
        }
        // мерцание: разряд то гаснет, то вспыхивает; к концу затухает
        const flick = Math.random() < 0.18 ? 0.25 : 1;
        const fade = k < 0.08 ? k / 0.08 : k > 0.75 ? (1 - k) / 0.25 : 1;
        const alpha = Math.max(0, fade * flick);
        for (const { coil, bolt } of bolts) {
          drawBolt(bolt, alpha, 2.2 * power);
          drawRing(coil, alpha);
        }
        for (const t of targets) drawFlash(t.x * dpr, t.y * dpr, 70 * dpr * stageScale * power, alpha);
      },
    });
  }

  function column(rect, { duration = 900 } = {}) {
    if (!canvas) return Promise.resolve();
    const start = performance.now();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    let bolts = [];
    let lastGen = 0;
    const coilStrike = strike([{ x: cx, y: cy }], { duration, power: 1.6 });
    const own = addEffect({
      until: start + duration,
      draw(now) {
        const k = (now - start) / duration;
        if (now - lastGen > BOLT_REFRESH_MS) {
          bolts = [];
          for (let i = 0; i < 3; i++) {
            const x0 = rect.left + rect.width * rand(0.2, 0.8);
            const x1 = rect.left + rect.width * rand(0.2, 0.8);
            bolts.push(makeBolt(x0 * dpr, rect.top * dpr, x1 * dpr, rect.bottom * dpr, 1.2));
          }
          lastGen = now;
        }
        // молния «падает» сверху: первые 15% клипа видна только верхняя часть
        const reach = Math.min(1, k / 0.15);
        ctx.save();
        ctx.beginPath();
        ctx.rect(rect.left * dpr - 40 * dpr, rect.top * dpr, (rect.width + 80) * dpr, rect.height * dpr * reach);
        ctx.clip();
        const alpha = k > 0.7 ? (1 - k) / 0.3 : 1;
        for (const b of bolts) drawBolt(b, alpha, 2.6);
        ctx.restore();
        drawFlash(cx * dpr, cy * dpr, rect.width * 0.9 * dpr, (k < 0.25 ? 1 : Math.max(0, 1 - (k - 0.25) / 0.5)));
      },
    });
    return Promise.all([coilStrike, own]).then(() => {});
  }

  // Разряд между двумя произвольными точками (client px): сбор монеты в
  // счётчик, удар катушки в плашку джекпота. Вспышки на обоих концах.
  function arc(from, to, { duration = 420, power = 1 } = {}) {
    if (!canvas) return Promise.resolve();
    const start = performance.now();
    let bolt = null;
    let lastGen = 0;
    return addEffect({
      until: start + duration,
      draw(now) {
        const k = (now - start) / duration;
        if (now - lastGen > BOLT_REFRESH_MS) {
          bolt = makeBolt(from.x * dpr, from.y * dpr, to.x * dpr, to.y * dpr, power);
          lastGen = now;
        }
        const alpha = Math.max(0, (k > 0.7 ? (1 - k) / 0.3 : 1) * (Math.random() < 0.15 ? 0.3 : 1));
        drawBolt(bolt, alpha, 1.8 * power);
        drawFlash(from.x * dpr, from.y * dpr, 40 * dpr * stageScale * power, alpha);
        drawFlash(to.x * dpr, to.y * dpr, 60 * dpr * stageScale * power, alpha);
      },
    });
  }

  // Цепь между зафиксированными монетами раунда: пока задан источник точек,
  // каждые 0.15–0.5с короткая дуга между случайной парой соседних монет —
  // сетка «под напряжением». getPoints() -> [{x, y}] в client px.
  let linkSource = null;
  let nextLinkAt = 0;
  function setLinks(getPoints) {
    linkSource = getPoints || null;
    if (linkSource) ensureLoop();
  }
  function maybeLink(now) {
    if (!linkSource || now < nextLinkAt) return;
    nextLinkAt = now + rand(150, 500);
    const pts = linkSource();
    if (!pts || pts.length < 2) return;
    // ближайший сосед случайной монеты — дуги не перечёркивают всю сетку
    const a = pts[Math.floor(Math.random() * pts.length)];
    let b = null;
    let best = Infinity;
    for (const p of pts) {
      if (p === a) continue;
      const d = Math.hypot(p.x - a.x, p.y - a.y) * rand(0.8, 1.25);
      if (d < best) { best = d; b = p; }
    }
    if (!b) return;
    const start = now;
    const dur = rand(160, 320);
    let bolt = null;
    let lastGen = 0;
    effects.add({
      until: start + dur,
      idle: true,
      draw(t) {
        if (t - lastGen > 45) {
          bolt = makeBolt(a.x * dpr, a.y * dpr, b.x * dpr, b.y * dpr, 0.8);
          lastGen = t;
        }
        drawBolt(bolt, Math.random() < 0.25 ? 0.35 : 0.95, 1.3);
      },
    });
  }

  // Треск в простое: короткая дуга по кольцу случайной катушки раз в 0.5–2с.
  function maybeIdle(now) {
    if (now < nextIdleAt) return;
    nextIdleAt = now + rand(500, 2000);
    const coils = anchors();
    if (!coils.length) return;
    const c = coils[Math.floor(Math.random() * coils.length)];
    const a0 = rand(0, Math.PI * 2);
    const a1 = a0 + rand(0.6, 1.6) * (Math.random() < 0.5 ? -1 : 1);
    const outward = Math.random() < 0.4;
    const p0 = [c.x + Math.cos(a0) * c.rx, c.y + Math.sin(a0) * c.ry];
    const p1 = outward
      ? [c.x + Math.cos(a0) * c.rx * rand(1.5, 2.1), c.y + Math.sin(a0) * c.ry * rand(2, 4) - rand(10, 50)]
      : [c.x + Math.cos(a1) * c.rx, c.y + Math.sin(a1) * c.ry];
    const start = now;
    const dur = rand(160, 360);
    let bolt = null;
    let lastGen = 0;
    effects.add({
      until: start + dur,
      idle: true,
      draw(t) {
        if (t - lastGen > 50) {
          bolt = makeBolt(p0[0] * dpr, p0[1] * dpr, p1[0] * dpr, p1[1] * dpr, 0.6);
          lastGen = t;
        }
        const alpha = Math.random() < 0.3 ? 0.3 : 0.9;
        drawBolt(bolt, alpha, 1.1);
      },
    });
  }

  // Разряд по буквам логотипа раз в 1.2–3с: короткая дуга поперёк слова TESLA
  // (верхние ~60% картинки), иногда двойная — со вспышкой в точке старта.
  let nextLogoAt = 0;
  function maybeLogoArc(now) {
    if (now < nextLogoAt) return;
    nextLogoAt = now + rand(1200, 3000);
    const el = document.querySelector('.logo__img');
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (!r.width) return;
    const n = Math.random() < 0.35 ? 2 : 1;
    for (let i = 0; i < n; i++) {
      const x0 = r.left + r.width * rand(0.08, 0.6);
      const x1 = x0 + r.width * rand(0.15, 0.35);
      const y0 = r.top + r.height * rand(0.08, 0.55);
      const y1 = r.top + r.height * rand(0.08, 0.55);
      const start = now + i * 90;
      const dur = rand(180, 340);
      let bolt = null;
      let lastGen = 0;
      effects.add({
        until: start + dur,
        idle: true,
        draw(t) {
          if (t < start) return;
          if (t - lastGen > 45) {
            bolt = makeBolt(x0 * dpr, y0 * dpr, x1 * dpr, y1 * dpr, 0.7);
            lastGen = t;
          }
          const alpha = Math.random() < 0.25 ? 0.35 : 1;
          drawBolt(bolt, alpha, 1.2);
          drawFlash(x0 * dpr, y0 * dpr, 26 * dpr * stageScale, alpha * 0.8);
        },
      });
    }
  }

  // --- цикл ------------------------------------------------------------------

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(canvas.clientWidth * dpr);
    const h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
  }

  function frame(now) {
    if (!running) return;
    drawFrame(now);
    requestAnimationFrame(frame);
  }

  function drawFrame(now) {
    resize();
    readStageScale();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // канвас на весь экран, а координаты целей — client px: переводим
    // смещение самого канваса (он может стоять не в (0,0)).
    const r = canvas.getBoundingClientRect();
    ctx.save();
    ctx.translate(-r.left * dpr, -r.top * dpr);
    maybeIdle(now);
    maybeLogoArc(now);
    maybeLink(now);
    for (const fx of [...effects]) {
      if (now >= fx.until) {
        effects.delete(fx);
        if (fx.resolve) fx.resolve();
        continue;
      }
      fx.draw(now);
    }
    ctx.restore();
  }

  function ensureLoop() {
    if (running || !canvas) return;
    running = true;
    requestAnimationFrame(frame);
  }

  function init(canvasEl) {
    canvas = canvasEl;
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    ensureLoop();
  }

  // renderAt — отладка: один кадр без rAF (во вкладке, которая считается
  // скрытой, кадры не идут, а посмотреть на молнию хочется).
  window.TeslaFX = { init, strike, column, arc, setLinks, renderAt: (now) => drawFrame(now ?? performance.now()) };
})();
