// Neon Joker Spins R1 — the hero's idle as Spine (scripts/njs_r1_hero_spine.py: one weighted mesh,
// breathing / head / presenting arm, pseudo-3D head turn). Drawn on its own canvas right above
// .stage (under the FX, the dim and the popups), anchored to the hero picture #mascot, which is
// hidden while the skeleton plays. Only heroes with a skeleton (SPINE below) animate; the others
// stay the still picture. No WebGL / a failed load -> the picture stays.
(function () {
  const ROOT = 'img/neon-joker-spins/skins/c/sets/r1/spine';
  const SPINE = { lean: { v: '2', w: 846, h: 1500 } };
  const img = document.getElementById('mascot');
  const screen = document.getElementById('screen');
  const stageEl = document.getElementById('stage');
  if (!img || !screen || !stageEl || !window.SpineEngine || !window.spine) return;

  const canvas = document.createElement('canvas');
  canvas.className = 'layer r1-hero-spine';
  canvas.style.cssText = 'inset:0;width:100%;height:100%;pointer-events:none;z-index:2';
  stageEl.after(canvas);
  let stage;
  try { stage = new SpineEngine.SpineStage(canvas); } catch (e) { canvas.remove(); return; }

  let inst = null;
  let token = 0;
  const heroId = () => (document.body.className.match(/\bhero-([a-z]+)\b/) || [])[1];
  const drop = () => {
    if (inst) { stage.removeBase ? stage.removeBase(inst) : stage.removeOverlay(inst); inst = null; }
    img.style.visibility = '';
  };
  async function sync() {
    const id = heroId();
    const cfg = SPINE[id];
    const my = ++token;
    if (!cfg) { drop(); return; }
    try {
      const res = await SpineEngine.SpineResource.load(stage.assetManager, `${ROOT}/${id}`, { premultipliedAlpha: true, version: cfg.v });
      if (my !== token) return;
      drop();
      inst = res.createInstance();
      inst.anchorEl = img;
      inst.fit = 1;
      inst.fitMode = 'contain';
      inst.boundsOverride = { x: -cfg.w / 2, y: 0, width: cfg.w, height: cfg.h };
      stage.addBase(inst);
      inst.play('idle', true);
      img.style.visibility = 'hidden';
    } catch (e) {
      console.warn('[r1] hero spine failed', e);
      drop();
    }
  }
  new MutationObserver(sync).observe(document.body, { attributes: true, attributeFilter: ['class'] });
  sync();
})();
