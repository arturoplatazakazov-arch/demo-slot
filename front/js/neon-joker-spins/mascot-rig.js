// Neon Joker Spins skins — the mascot as a skinned 2D mesh (WebGL).
//
// The flat picture is laid on a grid of triangles; seven bones bend the grid
// with soft weights, like a Spine mesh rig built in code:
//   hips (moves, legs blend from it down to the planted boots), spine
//   (lean + breathing stretch), head (pivot at the neck), two upper arms
//   (pivot at the shoulders) and two forearms (pivot at the elbows).
// Every bone parameter follows its target through a spring, so motion has
// weight and follow-through instead of curves:
//   idle   - breathing in the chest and shoulders, a slow weight shift with
//            the torso counter-balancing, the head looking around on its own
//            rhythm, arms swaying a beat behind the body, now and then a
//            "come on" beckon of the pointing hand;
//   win    - knees give, then he springs up, leans back laughing with both
//            arms up; laugh/big wins go further;
//   near   - leans into the reels, reaching hand forward;
//   miss   - a shrug.
// Pivots are fractions of the picture (RIGS below, measured on the art).
// No WebGL or no rig for this skin -> mascot.js keeps its strip animation.
(function () {
  const RIGS = {
    c: {
      head: [0.46, 0.08], neck: [0.45, 0.165], hips: [0.45, 0.42],
      shoulderL: [0.30, 0.20], elbowL: [0.11, 0.29], handL: [0.15, 0.18],
      shoulderR: [0.59, 0.21], elbowR: [0.70, 0.335], handR: [0.88, 0.375],
      ankleV: 0.82, hipsV: 0.45, neckBand: [0.14, 0.19],
      armR: [0.085, 0.07], // upper-arm, forearm radius (fraction of width)
    },
  };
  const rig = RIGS[window.NJS_SKIN];
  const img = document.getElementById('mascot');
  if (!rig || !img) return;
  const probe = document.createElement('canvas');
  const glProbe = probe.getContext('webgl', { premultipliedAlpha: true });
  if (!glProbe) return;
  window.NJS_MASCOT_RIG_ACTIVE = true;

  const TAU = Math.PI * 2;
  const DEG = Math.PI / 180;
  const PAD = 0.12;            // canvas margin around the figure (fraction of its height)
  const NX = 30;
  const NY = 56;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

  let canvas = null;
  let gl = null;
  let prog = null;
  let posBuf = null;
  let box = null;
  let rest = null;              // Float32Array of rest positions (image px)
  let weights = null;           // per vertex: [legs, spine, head, aLu, aLf, aRu, aRf]
  let legT = null;              // per vertex: blend 0 (boot) .. 1 (hips)
  let pos = null;
  let indexCount = 0;
  let W = 0;
  let H = 0;

  // --- springs ----------------------------------------------------------------
  const P = {};
  function param(name, omega = 7, zeta = 0.75) { P[name] = { x: 0, v: 0, target: 0, omega, zeta }; }
  [['hx', 3.2], ['hy', 9, 0.55], ['hrot', 3.2], ['srot', 4], ['breath', 6, 1], ['nrot', 3.5, 0.7], ['nlag', 2.4, 0.6],
    ['alu', 5, 0.6], ['alf', 7, 0.45], ['aru', 5, 0.6], ['arf', 7, 0.45]].forEach(([n, o, z]) => param(n, o, z));
  function stepSprings(dt) {
    for (const p of Object.values(P)) {
      const a = p.omega * p.omega * (p.target - p.x) - 2 * p.zeta * p.omega * p.v;
      p.v += a * dt;
      p.x += p.v * dt;
    }
  }

  // --- 2D affine helpers: [a, b, c, d, e, f] -> x' = a x + c y + e, y' = b x + d y + f
  const mul = (m, n) => [
    m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
    m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
    m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5],
  ];
  const rotAbout = (ang, px, py) => {
    const c = Math.cos(ang);
    const s = Math.sin(ang);
    return [c, s, -s, c, px - c * px + s * py, py - s * px - c * py];
  };
  const trans = (x, y) => [1, 0, 0, 1, x, y];
  const scaleYAbout = (k, py) => [1, 0, 0, k, 0, py - k * py];

  // --- mesh + weights ----------------------------------------------------------
  function segDist(px, py, a, b) {
    const ax = a[0] * W; const ay = a[1] * H; const bx = b[0] * W; const by = b[1] * H;
    const dx = bx - ax; const dy = by - ay;
    const t = clamp(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0, 1);
    return { d: Math.hypot(px - ax - t * dx, py - ay - t * dy), t };
  }

  function buildMesh() {
    W = img.naturalWidth;
    H = img.naturalHeight;
    const n = (NX + 1) * (NY + 1);
    rest = new Float32Array(n * 2);
    const uv = new Float32Array(n * 2);
    weights = new Float32Array(n * 7);
    legT = new Float32Array(n);
    for (let j = 0; j <= NY; j++) {
      for (let i = 0; i <= NX; i++) {
        const k = j * (NX + 1) + i;
        const u = i / NX;
        const v = j / NY;
        const x = u * W;
        const y = v * H;
        rest[k * 2] = x;
        rest[k * 2 + 1] = y;
        uv[k * 2] = u;
        uv[k * 2 + 1] = v;
        // arms: membership by distance to upper arm / forearm segments
        const ru = rig.armR[0] * W;
        const rf = rig.armR[1] * W;
        const uL = segDist(x, y, rig.shoulderL, rig.elbowL);
        const fL = segDist(x, y, rig.elbowL, rig.handL);
        const uR = segDist(x, y, rig.shoulderR, rig.elbowR);
        const fR = segDist(x, y, rig.elbowR, rig.handR);
        const mem = (d, r) => 1 - smooth(r * 0.75, r * 1.35, d);
        let aLu = mem(uL.d, ru) * (1 - smooth(0.7, 1.0, uL.t) * 0.5);
        let aLf = Math.max(mem(fL.d, rf), mem(uL.d, ru) * smooth(0.85, 1.0, uL.t) * 0.5);
        let aRu = mem(uR.d, ru) * (1 - smooth(0.7, 1.0, uR.t) * 0.5);
        let aRf = Math.max(mem(fR.d, rf), mem(uR.d, ru) * smooth(0.85, 1.0, uR.t) * 0.5);
        // the shoulder end of the upper arm stays with the torso
        aLu *= smooth(0.0, 0.25, uL.t) * 0.7 + 0.3;
        aRu *= smooth(0.0, 0.25, uR.t) * 0.7 + 0.3;
        let arms = aLu + aLf + aRu + aRf;
        if (arms > 1) { aLu /= arms; aLf /= arms; aRu /= arms; aRf /= arms; arms = 1; }
        // head vs spine across the neck band; below the hips -> legs
        const headW = 1 - smooth(rig.neckBand[0], rig.neckBand[1], v);
        const legW = smooth(rig.hipsV - 0.03, rig.hipsV + 0.03, v);
        const body = 1 - arms;
        const w = [body * legW, body * (1 - legW) * (1 - headW), body * (1 - legW) * headW, aLu, aLf, aRu, aRf];
        weights.set(w, k * 7);
        legT[k] = Math.pow(clamp((rig.ankleV - v) / (rig.ankleV - rig.hipsV), 0, 1), 1.25);
      }
    }
    const idx = [];
    for (let j = 0; j < NY; j++) {
      for (let i = 0; i < NX; i++) {
        const a = j * (NX + 1) + i;
        const b = a + 1;
        const c = a + NX + 1;
        const d = c + 1;
        idx.push(a, b, c, b, d, c);
      }
    }
    indexCount = idx.length;
    pos = new Float32Array(n * 2);

    const vs = `attribute vec2 p; attribute vec2 t; uniform vec2 s; uniform vec3 m; varying vec2 vt;
      void main(){ vec2 q = (p * m.z + m.xy) / s * 2.0 - 1.0; gl_Position = vec4(q.x, -q.y, 0.0, 1.0); vt = t; }`;
    const fs = `precision mediump float; varying vec2 vt; uniform sampler2D tex;
      void main(){ gl_FragColor = texture2D(tex, vt); }`;
    const sh = (type, src) => { const o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o); return o; };
    prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    posBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
    const pl = gl.getAttribLocation(prog, 'p');
    gl.enableVertexAttribArray(pl);
    gl.vertexAttribPointer(pl, 2, gl.FLOAT, false, 0, 0);
    const uvBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, uvBuf);
    gl.bufferData(gl.ARRAY_BUFFER, uv, gl.STATIC_DRAW);
    const tl = gl.getAttribLocation(prog, 't');
    gl.enableVertexAttribArray(tl);
    gl.vertexAttribPointer(tl, 2, gl.FLOAT, false, 0, 0);
    const ib = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(idx), gl.STATIC_DRAW);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  }

  function layout() {
    const bw = img.offsetWidth;
    const bh = img.offsetHeight;
    if (!bw || !bh || !W) return false;
    const s = Math.min(bw / W, bh / H);
    const dw = W * s;
    const dh = H * s;
    const pad = dh * PAD;
    box = { x: img.offsetLeft + (bw - dw) / 2, y: img.offsetTop + bh - dh, w: dw, h: dh, pad, s };
    canvas.style.left = `${box.x - pad}px`;
    canvas.style.top = `${box.y - pad}px`;
    canvas.style.width = `${dw + 2 * pad}px`;
    canvas.style.height = `${dh + pad}px`;
    const stage = document.getElementById('stage');
    const k = (stage.getBoundingClientRect().width / stage.offsetWidth || 1) * (window.devicePixelRatio || 1);
    const res = clamp(k, 0.5, 2);
    canvas.width = Math.round((dw + 2 * pad) * res);
    canvas.height = Math.round((dh + pad) * res);
    gl.viewport(0, 0, canvas.width, canvas.height);
    return true;
  }

  // --- motion -------------------------------------------------------------------
  const events = [];             // {t0, kind, k}
  let nearOn = 0;
  let headTarget = 0;
  let headNext = 0;
  let beckonAt = 4;

  function targets(t) {
    const breath = 0.5 - 0.5 * Math.cos(TAU * t / 3.9);
    const shift = 0.75 * Math.sin(TAU * t / 7.6) + 0.25 * Math.sin(TAU * t / 3.3 + 1.0);
    if (t > headNext) {                       // the head picks a new direction now and then
      headTarget = (Math.random() * 2 - 1) * 4.5 * DEG;
      headNext = t + 1.8 + Math.random() * 2.8;
    }
    let hx = 0.012 * H * shift;
    let hy = 0;
    let hrot = 0.9 * DEG * shift;
    let srot = -0.7 * DEG * shift;
    let nrot = headTarget + 1.2 * DEG * Math.sin(TAU * t / 5.3) - 0.5 * hrot;
    let alu = 2.5 * DEG * Math.sin(TAU * t / 3.9 + 0.4);
    let alf = 2.0 * DEG * Math.sin(TAU * t / 3.9 + 1.2);
    let aru = -2.2 * DEG * Math.sin(TAU * t / 3.9 + 0.9);
    let arf = 3.0 * DEG * Math.sin(TAU * t / 5.1);
    // "come on" beckon of the pointing hand every ~8-12 s (two flicks)
    if (t > beckonAt + 1.1) beckonAt = t + 8 + Math.random() * 4;
    const bu = t - beckonAt;
    if (bu > 0 && bu < 1.1) alf += 16 * DEG * Math.max(0, Math.sin(TAU * bu / 0.55));
    // near-win: lean into the reels, reach
    hx += 0.02 * H * nearOn;
    srot += 3 * DEG * nearOn;
    nrot += 4 * DEG * nearOn;
    aru -= 12 * DEG * nearOn;
    arf -= 6 * DEG * nearOn;
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      const u = t - e.t0;
      if (u > 2.2) { events.splice(i, 1); continue; }
      const bump = (a, b) => smooth(a, a + 0.15, u) * (1 - smooth(b - 0.35, b, u));
      if (e.kind === 'miss') {                // shrug
        const s = bump(0.0, 1.2) * e.k;
        hy -= 0.008 * H * s;
        alu += 10 * DEG * s;
        aru -= 10 * DEG * s;
        nrot += 7 * DEG * s;
        srot -= 1.5 * DEG * s;
        continue;
      }
      // win: knees give first, then up with arms raised, leaning back laughing
      const dip = smooth(0.0, 0.12, u) * (1 - smooth(0.12, 0.32, u));
      const up = bump(0.18, 1.7) * e.k;
      hy += 0.03 * H * dip * e.k - 0.01 * H * up;
      srot -= 4 * DEG * up;
      nrot -= 9 * DEG * up + 3 * DEG * up * Math.sin(TAU * u / 0.28);   // laughing nods
      alu += 34 * DEG * up;
      alf += 22 * DEG * up;
      aru -= 30 * DEG * up;
      arf -= 18 * DEG * up;
    }
    P.hx.target = hx; P.hy.target = hy; P.hrot.target = hrot; P.srot.target = srot; P.breath.target = breath;
    P.nrot.target = nrot; P.alu.target = alu; P.alf.target = alf; P.aru.target = aru; P.arf.target = arf;
  }

  let last = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    // rAF stamps can be older than performance.now() taken earlier: never step
    // the springs backwards (a negative step makes them blow up)
    const dt = clamp((now - last) / 1000, 0, 0.05);
    last = Math.max(last, now);
    if (!box || !img.offsetWidth) return;     // portrait: the mascot is hidden
    const t = now / 1000;
    targets(t);
    // integrate in small steps so stiff springs stay stable
    for (let k = 0; k < 3; k++) stepSprings(dt / 3);

    const px = (p) => [p[0] * W, p[1] * H];
    const hipsC = px(rig.hips);
    const neck = px(rig.neck);
    const sL = px(rig.shoulderL);
    const eL = px(rig.elbowL);
    const sR = px(rig.shoulderR);
    const eR = px(rig.elbowR);
    const Mh = mul(trans(P.hx.x, P.hy.x), rotAbout(P.hrot.x, hipsC[0], hipsC[1]));
    const Ms = mul(Mh, mul(rotAbout(P.srot.x, hipsC[0], hipsC[1]), scaleYAbout(1 + 0.012 * P.breath.x, hipsC[1])));
    const Mn = mul(Ms, rotAbout(P.nrot.x, neck[0], neck[1]));
    const MaLu = mul(Ms, rotAbout(P.alu.x, sL[0], sL[1]));
    const MaLf = mul(MaLu, rotAbout(P.alf.x, eL[0], eL[1]));
    const MaRu = mul(Ms, rotAbout(P.aru.x, sR[0], sR[1]));
    const MaRf = mul(MaRu, rotAbout(P.arf.x, eR[0], eR[1]));
    const mats = [null, Ms, Mn, MaLu, MaLf, MaRu, MaRf];
    const n = rest.length / 2;
    for (let k = 0; k < n; k++) {
      const x = rest[k * 2];
      const y = rest[k * 2 + 1];
      let ox = 0;
      let oy = 0;
      const wb = k * 7;
      // legs: blend from the planted boot (identity) to the hips
      const wl = weights[wb];
      if (wl) {
        const tl = legT[k];
        const lx = Mh[0] * x + Mh[2] * y + Mh[4];
        const ly = Mh[1] * x + Mh[3] * y + Mh[5];
        ox += wl * (x + (lx - x) * tl);
        oy += wl * (y + (ly - y) * tl);
      }
      for (let b = 1; b < 7; b++) {
        const w = weights[wb + b];
        if (!w) continue;
        const m = mats[b];
        ox += w * (m[0] * x + m[2] * y + m[4]);
        oy += w * (m[1] * x + m[3] * y + m[5]);
      }
      pos[k * 2] = ox;
      pos[k * 2 + 1] = oy;
    }
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, pos);
    const cw = box.w + 2 * box.pad;
    const ch = box.h + box.pad;
    gl.uniform2f(gl.getUniformLocation(prog, 's'), cw, ch);
    gl.uniform3f(gl.getUniformLocation(prog, 'm'), box.pad, box.pad, box.s);
    gl.drawElements(gl.TRIANGLES, indexCount, gl.UNSIGNED_SHORT, 0);
  }

  function start() {
    canvas = document.createElement('canvas');
    canvas.className = 'obj mascot-live';
    canvas.setAttribute('aria-hidden', 'true');
    img.after(canvas);
    gl = canvas.getContext('webgl', { premultipliedAlpha: true, alpha: true, antialias: true });
    if (!gl) { canvas.remove(); return; }
    img.classList.add('is-live');
    canvas.style.filter = getComputedStyle(img).filter;
    buildMesh();
    if (!layout()) box = null;
    window.addEventListener('resize', () => requestAnimationFrame(() => { if (!layout()) box = null; }));
    requestAnimationFrame(frame);
  }

  window.NJS_MASCOT = {
    react(clip) {
      const t0 = performance.now() / 1000;
      if (clip === 'near_miss') events.push({ t0, kind: 'miss', k: 1 });
      else events.push({ t0, kind: 'win', k: clip === 'laugh' || clip === 'win' ? 1.25 : 1 });
    },
    near(on) { nearOn = on ? 1 : 0; },
  };

  if (img.complete && img.naturalWidth) start();
  else img.addEventListener('load', start, { once: true });
})();
