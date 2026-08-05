// Debug-only FPS overlay, enabled with ?fps=1 — for comparing rendering
// performance between environments (plain mobile browser vs the Telegram
// Mini App webview) on the same device. Shows rolling FPS plus a cumulative
// count of janky frames (>34ms, i.e. dropped below ~30fps). Zero cost when
// the flag is absent: the file returns before touching the DOM or rAF.
(function () {
  if (new URLSearchParams(location.search).get('fps') !== '1') return;

  const el = document.createElement('div');
  el.style.cssText =
    'position:fixed;left:8px;bottom:8px;z-index:9999;padding:4px 10px;' +
    'font:700 14px/1.4 monospace;color:#0f0;background:rgba(0,0,0,0.65);' +
    'border-radius:6px;pointer-events:none;';
  el.textContent = 'fps —';
  document.body.appendChild(el);

  let frames = 0;
  let jank = 0;
  let last = performance.now();
  let windowStart = last;

  function tick(now) {
    frames++;
    if (now - last > 34) jank++;
    last = now;
    if (now - windowStart >= 500) {
      const fps = Math.round((frames * 1000) / (now - windowStart));
      el.textContent = `fps ${fps} | jank ${jank}`;
      frames = 0;
      windowStart = now;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();
