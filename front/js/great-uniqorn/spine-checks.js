// Great Uniqorn — the animator's-spec (ТЗ) checks of the Spine export, shared
// by the acceptance page (great-uniqorn-spine-check.html) and the all-animations
// page (great-uniqorn-anims.html) so both judge the same way.
//
//   const C = GUChecks.create({ base: 'img/great-uniqorn/spine/d', report, version });
//   const { res, data } = await C.pixelChecks(name, reportObject, skin);
//   const items = C.checklist(reportObject, data, res);   // [{ st: ok|fail|warn, what, why }]
//   const clips = C.clipStatus(reportObject, data, res);  // { clip: { st, why[] } }
//
// Pixel checks (setup pose vs static, first / last frame vs setup) render on
// an offscreen WebGL canvas of their own; everything about the delivered
// files (names, texture sizes, unused images, meshes, keyed properties) comes
// from spine/d/report.json (scripts/great_uniqorn_designer_spine.py).
(function () {
  // ТЗ: which clips each kind of object needs (null = length not fixed)
  const SPEC = { symbol: { win: 1.3 }, wild: { win: 1.3, idle: null }, scatter: { landing: null, idle: null, win: 1.7 }, scene: null };
  const DIFF_DELTA = 24, SAME = 0.005, NEAR_STATIC = 0.04, FAR_STATIC = 0.12, DUR_EPS = 0.02;
  const ICON = { ok: '✅', fail: '❌', warn: '⚠️' };

  function create({ base: BASE, report, version: V = Date.now() }) {
    const glCanvas = document.createElement('canvas');
    glCanvas.width = 400; glCanvas.height = 400;
    glCanvas.style.cssText = 'position:fixed;left:-9999px;top:0;';
    document.body.appendChild(glCanvas);
      const gctx = new spine.ManagedWebGLRenderingContext(glCanvas, { alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true });
      const grenderer = new spine.SceneRenderer(glCanvas, gctx, true);
      const gassets = new spine.AssetManager(gctx, '');
      const gl = gctx.gl;
      const loadOff = (name) => new Promise((resolve, reject) => {
        gassets.loadTextureAtlas(`${BASE}/${name}/animation.atlas?v=${V}`, (p, atlas) => {
          gassets.loadJson(`${BASE}/${name}/animation.json?v=${V}`, (p2, json) => {
            resolve(new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(json));
          }, (p2, e) => reject(new Error(e)));
        }, (p, e) => reject(new Error(e)));
      });
      const offData = {};
      const loadImg = (src) => new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src; });
      function renderPose(skel, view, W, H) {
        glCanvas.width = W; glCanvas.height = H;
        gl.viewport(0, 0, W, H);
        const cam = grenderer.camera;
        cam.setViewport(W, H);
        cam.position.x = view.cx; cam.position.y = view.cy;
        cam.zoom = Math.max(view.w / W, view.h / H);
        cam.update();
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        grenderer.begin();
        grenderer.drawSkeleton(skel, true);
        grenderer.end();
        const c = document.createElement('canvas');
        c.width = W; c.height = H;
        c.getContext('2d').drawImage(glCanvas, 0, 0);
        return c;
      }
      function drawStaticAt(img, view, W, H) {
        const c = document.createElement('canvas');
        c.width = W; c.height = H;
        const z = Math.max(view.w / W, view.h / H);
        c.getContext('2d').drawImage(img, W / 2 - view.cx / z - img.width / (2 * z), H / 2 + view.cy / z - img.height / (2 * z), img.width / z, img.height / z);
        return c;
      }
      function diff(a, b) {
        const da = a.getContext('2d').getImageData(0, 0, a.width, a.height).data;
        const db = b.getContext('2d').getImageData(0, 0, b.width, b.height).data;
        let n = 0, bad = 0;
        for (let i = 0; i < da.length; i += 4) {
          if (da[i + 3] < 8 && db[i + 3] < 8) continue;
          n++;
          if (Math.abs(da[i] - db[i]) > DIFF_DELTA || Math.abs(da[i + 1] - db[i + 1]) > DIFF_DELTA ||
              Math.abs(da[i + 2] - db[i + 2]) > DIFF_DELTA || Math.abs(da[i + 3] - db[i + 3]) > DIFF_DELTA) bad++;
        }
        return n ? bad / n : 0;
      }
      function poseOff(skel, skin, anim, t) {
        if (skin) skel.setSkinByName(skin);
        skel.setToSetupPose();
        if (anim) anim.apply(skel, t, t, false, null, 1, spine.MixBlend.setup, spine.MixDirection.mixIn);
        skel.updateWorldTransform();
      }
      async function pixelChecks(name, o, skin) {
        const data = offData[name] || (offData[name] = await loadOff(name));
        const skel = new spine.Skeleton(data);
        const stName = skin && o.statics.includes(`static_${skin}.png`) ? `static_${skin}.png` : o.statics.includes('static.png') ? 'static.png' : null;
        const img = stName ? await loadImg(`${BASE}/${name}/${stName}?v=${V}`) : null;
        let x0 = data.x, y0 = data.y, x1 = data.x + data.width, y1 = data.y + data.height;
        if (img) { x0 = Math.min(x0, -img.width / 2); x1 = Math.max(x1, img.width / 2); y0 = Math.min(y0, -img.height / 2); y1 = Math.max(y1, img.height / 2); }
        const view = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: (x1 - x0) * 1.06, h: (y1 - y0) * 1.06 };
        const S = data.width > 1000 ? 480 : 300;
        const W = Math.round(view.w >= view.h ? S : S * view.w / view.h), H = Math.round(view.w >= view.h ? S * view.h / view.w : S);
        poseOff(skel, skin, null, 0);
        const setup = renderPose(skel, view, W, H);
        const res = { first: {}, last: {}, staticDiff: null, staticName: stName, staticSize: img ? [img.width, img.height] : null };
        if (img) res.staticDiff = diff(drawStaticAt(img, view, W, H), setup);
        for (const a of data.animations) {
          poseOff(skel, skin, a, 0); res.first[a.name] = diff(renderPose(skel, view, W, H), setup);
          poseOff(skel, skin, a, a.duration); res.last[a.name] = diff(renderPose(skel, view, W, H), setup);
        }
        return { res, data };
      }

      const pct = (x) => `${(x * 100).toFixed(x < 0.01 ? 2 : 1)} %`;
      const ICON = { ok: '✅', fail: '❌', warn: '⚠️' };
      const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
      const list = (arr, max = 6) => arr.slice(0, max).map((x) => `<code>${esc(x)}</code>`).join(' ') + (arr.length > max ? ` … ещё ${arr.length - max}` : '');
      const winDurs = Object.entries(report.objects).filter(([, o]) => o.kind === 'symbol' || o.kind === 'wild').map(([n, o]) => [n, o.animations.win]);
      function checklist(o, data, res) {
        const items = [];
        const add = (st, what, why) => items.push({ st, what, why });
        const anims = data.animations;
        const ver = o.spine || '?';
        add(/^4\.1/.test(ver) ? 'ok' : 'fail', 'Версия экспорта 4.1', `<code>${esc(ver)}</code>`);
        const spec = SPEC[o.kind];
        if (spec) {
          const miss = [], bad = [], extra = [];
          for (const [n, d] of Object.entries(spec)) {
            const a = data.findAnimation(n);
            if (!a) miss.push(n);
            else if (d != null && Math.abs(a.duration - d) > DUR_EPS) bad.push(`${n}: ${a.duration.toFixed(2)} с вместо ${d} с`);
          }
          for (const a of anims) if (!(a.name in spec)) extra.push(a.name);
          add(miss.length || bad.length ? 'fail' : 'ok', 'Названия и длительность клипов',
            miss.length || bad.length ? [miss.length ? `нет: ${list(miss)}` : '', bad.map(esc).join('; ')].filter(Boolean).join(' · ')
              : Object.entries(spec).map(([n, d]) => `<code>${n}</code>${d != null ? ` ${String(d).replace('.', ',')} с` : ''}`).join(', '));
          add(extra.length ? 'fail' : 'ok', 'Нет лишних клипов', extra.length ? `в ТЗ нет: ${list(extra)}` : 'только клипы из ТЗ');
        } else add('warn', 'Клипы', 'для фона и героя в ТЗ клипы не описаны');
        if (o.kind === 'symbol' || o.kind === 'wild') {
          const off = winDurs.filter(([, d]) => Math.abs(d - 1.3) > DUR_EPS);
          add(off.length ? 'fail' : 'ok', 'Один ритм с фигурами и Wild', off.length ? `win не 1,3 с: ${list(off.map(([n, d]) => `${n} ${d}`))}` : `win у всех ${winDurs.length} — 1,3 с; движение сравнить кнопкой «Все: win»`);
        }
        add(o.naming.length ? 'fail' : 'ok', 'Названия файлов', o.naming.length ? o.naming.map(esc).join(' · ') : 'как в ТЗ');
        if (res.staticDiff != null) {
          const k = res.staticDiff < NEAR_STATIC ? 'ok' : res.staticDiff < FAR_STATIC ? 'warn' : 'fail';
          add(k, 'По центру, кадр 0 ≈ исходник', `статика <code>${esc(res.staticName)}</code> ${res.staticSize.join('×')} центром в (0,0) против кадра 0: расходятся ${pct(res.staticDiff)} пикселей — смотреть «Статика поверх»`);
        } else add('warn', 'По центру, кадр 0 ≈ исходник', 'static.png в экспорте нет — смотреть глазами');
        const bad = [];
        for (const a of anims) {
          if (res.first[a.name] >= SAME) bad.push(`${a.name} первый ${pct(res.first[a.name])}`);
          if (res.last[a.name] >= SAME) bad.push(`${a.name} последний ${pct(res.last[a.name])}`);
        }
        add(bad.length ? 'fail' : 'ok', 'Кадр 0 = первый = последний', bad.length ? `отличаются от кадра 0: ${bad.map(esc).join('; ')}` : 'совпадают у всех клипов');
        add(o.sizeIssues.length ? 'fail' : 'ok', 'Размеры текстур = исходникам',
          o.sizeIssues.length ? o.sizeIssues.map((s) => `<code>${esc(s.name)}</code> ${s.export.join('×')} вместо ${s.source.join('×')}`).join(' · ') : `${o.regions.length} текстур совпали с img/`);
        const extraImg = [...o.unusedRegions, ...o.neverShown];
        add(extraImg.length ? 'fail' : 'ok', 'Нет лишних картинок', extraImg.length ? `не показываются: ${list(extraImg)}` : 'все используются');
        const meshes = o.meshes.filter((m) => m.type !== 'clipping'), masks = o.meshes.filter((m) => m.type === 'clipping');
        add(meshes.length || masks.length ? 'warn' : 'ok', 'Меши и маски только где нужно',
          meshes.length || masks.length ? `мешей ${meshes.length}, масок ${masks.length} (${list([...new Set(o.meshes.map((m) => m.attachment))], 5)}) — уточнить у аниматора` : 'нет');
        if (o.kind === 'scatter' || o.kind === 'wild') {
          const ov = Object.entries(o.overlaps);
          add(ov.length ? 'fail' : 'ok', 'Клипы не конфликтуют на треках',
            ov.length ? ov.map(([p, k]) => `<b>${esc(p.replace('+', ' + '))}</b>: общие ${k.length} свойств`).join(' · ') + ' — кнопка «на треках» показывает переход' : 'клипы ключуют разное');
        }
        return items;
      }


      // per clip: name / length per the spec, first & last frame = setup
      function clipStatus(o, data, res) {
        const spec = SPEC[o.kind] || {};
        const out = {};
        for (const a of data.animations) {
          const why = [];
          if (SPEC[o.kind] && !(a.name in spec)) why.push('клипа нет в ТЗ');
          const want = spec[a.name];
          if (want != null && Math.abs(a.duration - want) > DUR_EPS) why.push(`длится ${a.duration.toFixed(2)} с вместо ${want} с`);
          if (res.first[a.name] >= SAME) why.push(`первый кадр ≠ кадр 0 (${pct(res.first[a.name])})`);
          if (res.last[a.name] >= SAME) why.push(`последний кадр ≠ кадр 0 (${pct(res.last[a.name])})`);
          out[a.name] = { st: why.length ? 'fail' : 'ok', why };
        }
        return out;
      }
      const worst = (items) => (items.some((i) => i.st === 'fail') ? 'fail' : items.some((i) => i.st === 'warn') ? 'warn' : 'ok');
      return { pixelChecks, checklist, clipStatus, worst, ICON, SPEC };
    }

    window.GUChecks = { create, SPEC, ICON };
  })();
