// Stage 4 of the slot builder wizard: a GUIDED, step-by-step version —
// background (x4: base/bonus × desktop/mobile) -> "slot" (reel block +
// frame + logo, once per device, mirrored between base/bonus) -> Buy Bonus
// button (desktop then mobile) -> Free Spins counter (desktop then mobile)
// -> Multiplier (desktop then mobile, only if coin_multiplier was picked in
// Stage 3). Objects carry x/y as their CENTER point, w/h as rendered size
// (see LayoutObjectIn in app/api/admin/builder.py). The Konva stage itself
// is scaled to fit the viewport (stage.scale()), so every coordinate read
// from/written to a node stays in native pixels.
//
// Step completion is derived from the manifest (role tags + backgrounds),
// not separately persisted — resuming later just re-derives where you left
// off. Every step navigation refetches the manifest fresh from the server
// (rather than trusting a possibly long-stale in-memory copy) so a tab left
// open across a backend restart or another tab's edits can't silently
// clobber newer saves with old data.
// apiRequest/apiUpload/setStatus/API_BASE come from common.js.

const params = new URLSearchParams(window.location.search);
const SLUG = params.get('slug');

const NATIVE = {
  desktop: { w: 1932, h: 940 },
  mobile: { w: 780, h: 1416 },
};

const DEFAULT_GAP = 10;

// Fixed drawing order for the slot's core pieces — always enforced
// regardless of manual drag-reordering (logo above frame above reels above
// the reel background); everything else keeps its freely-set z-index, same
// as before. Higher number = drawn later = visually on top.
const ROLE_PRIORITY = { slot_reel_background: 0, slot_reel_block: 1, slot_frame: 2 };

let manifest = null;
let stage, layer, transformer;
let bgNode = null;
let objectNodes = [];
let selectedNode = null;
let currentDevice = 'desktop';
let currentScreen = 'base';
let scale = 1;
let wizardSteps = [];
let currentStepIndex = 0;
let draggedEntryIndex = null;

function imgUrl(file) { return `../img/${SLUG}/${file}`; }
function genId() { return 'obj-' + Math.random().toString(36).slice(2, 10); }

function isReelBlock(node) {
  return !!(node && node.appData && node.appData.type === 'system.reel_block');
}
function isBackground(node) {
  return !!node && node === bgNode;
}
// True for any node backed by a Spine animation — the background slot when
// it's a Spine animation, or a decor.spine overlay object. Used where the
// resize/rebuild behavior is shared between the two; isSpineObject below is
// the narrower "specifically a decor.spine overlay object" check.
function isSpineNode(node) {
  return !!(node && node.appData && node.appData.animation_ref);
}
function isSpineObject(node) {
  return !!(node && node.appData && node.appData.type === 'decor.spine');
}

function getGridSize() {
  if (manifest.grid && manifest.grid.reels && manifest.grid.rows) {
    return { reels: manifest.grid.reels, rows: manifest.grid.rows };
  }
  return { reels: 5, rows: 3 };
}

// ---------- wizard step definitions ----------

function buildWizardSteps() {
  const steps = [
    { id: 'bg-base-desktop', kind: 'background', device: 'desktop', screen: 'base',
      title: 'Фон — База (Десктоп)', hint: 'Фон базового экрана на десктопе.' },
    { id: 'bg-bonus-desktop', kind: 'background', device: 'desktop', screen: 'bonus',
      title: 'Фон — Бонус (Десктоп)', hint: 'Фон бонусного экрана на десктопе.' },
    { id: 'bg-base-mobile', kind: 'background', device: 'mobile', screen: 'base',
      title: 'Фон — База (Моби)', hint: 'Фон базового экрана на мобильном.' },
    { id: 'bg-bonus-mobile', kind: 'background', device: 'mobile', screen: 'bonus',
      title: 'Фон — Бонус (Моби)', hint: 'Фон бонусного экрана на мобильном.' },
    { id: 'slot-desktop', kind: 'slot', device: 'desktop', screen: 'base',
      title: 'Слот — Десктоп', hint: 'Барабаны (центрируй по ширине, задай размер ячеек и отступов), рамка, логотип. Одинаково для базового и бонусного экранов — подтверждение скопирует их на оба.' },
    { id: 'slot-mobile', kind: 'slot', device: 'mobile', screen: 'base',
      title: 'Слот — Моби', hint: 'То же самое для мобильной версии.' },
    { id: 'buybonus-desktop', kind: 'ui', role: 'buy_bonus', device: 'desktop', screen: 'base',
      title: 'Кнопка Buy Bonus — Десктоп', hint: 'Разместите кнопку покупки бонуса на базовом экране (десктоп).' },
    { id: 'buybonus-mobile', kind: 'ui', role: 'buy_bonus', device: 'mobile', screen: 'base',
      title: 'Кнопка Buy Bonus — Моби', hint: 'То же на мобильном.' },
    { id: 'fscounter-desktop', kind: 'hud', role: 'free_spins_counter', device: 'desktop', screen: 'bonus',
      title: 'Счётчик Free Spins — Десктоп', hint: 'Разместите счётчик фриспинов на бонусном экране (десктоп).' },
    { id: 'fscounter-mobile', kind: 'hud', role: 'free_spins_counter', device: 'mobile', screen: 'bonus',
      title: 'Счётчик Free Spins — Моби', hint: 'То же на мобильном.' },
  ];
  const mechanics = new Set(manifest.mechanics || []);
  if (mechanics.has('coin_multiplier')) {
    steps.push(
      { id: 'multiplier-desktop', kind: 'hud', role: 'multiplier', device: 'desktop', screen: 'bonus',
        title: 'Мультипликатор — Десктоп', hint: 'Разместите индикатор мультипликатора на бонусном экране (десктоп).' },
      { id: 'multiplier-mobile', kind: 'hud', role: 'multiplier', device: 'mobile', screen: 'bonus',
        title: 'Мультипликатор — Моби', hint: 'То же на мобильном.' },
    );
  }
  return steps;
}

function isStepDone(step) {
  if ((manifest.layout_skips || []).includes(step.id)) return true;
  if (step.kind === 'background') {
    return !!manifest.layouts[step.device].backgrounds[step.screen];
  }
  const objs = manifest.layouts[step.device].screens[step.screen] || [];
  if (step.kind === 'slot') return objs.some((o) => o.role === 'slot_reel_block');
  return objs.some((o) => o.role === step.role);
}

function isSkippable(step) {
  return step.kind === 'ui' || step.kind === 'hud';
}

function findResumeIndex() {
  const idx = wizardSteps.findIndex((s) => !isStepDone(s));
  return idx === -1 ? wizardSteps.length : idx;
}

function roleForCategory(step, category) {
  if (step.kind === 'slot') {
    if (category === 'frame') return 'slot_frame';
    if (category === 'logo') return 'slot_logo';
    if (category === 'reel_background') return 'slot_reel_background';
    // Anything else dropped on this step (e.g. dragged from the palette
    // rather than one of the dedicated quick-add buttons) still needs a
    // role so it mirrors between base/bonus like frame/logo/reel_background do.
    return 'slot_decor';
  }
  if (step.kind === 'ui' || step.kind === 'hud') return step.role;
  return null;
}

// ---------- properties panel ----------

function updatePropsFromNode(node) {
  document.getElementById('propX').value = Math.round(node.x() + node.width() / 2);
  document.getElementById('propY').value = Math.round(node.y() + node.height() / 2);
  document.getElementById('propW').value = Math.round(node.width());
  document.getElementById('propH').value = Math.round(node.height());
  document.getElementById('propZ').value = objectNodes.indexOf(node);

  const reelBlock = isReelBlock(node);
  document.getElementById('propW').disabled = reelBlock;
  document.getElementById('propH').disabled = reelBlock;
  for (const id of ['propCellWField', 'propCellHField', 'propGapXField', 'propGapYField']) {
    document.getElementById(id).classList.toggle('is-hidden', !reelBlock);
  }
  if (reelBlock) {
    document.getElementById('propCellW').value = Math.round(node.appData.cellW);
    document.getElementById('propCellH').value = Math.round(node.appData.cellH);
    document.getElementById('propGapX').value = Math.round(node.appData.gapX);
    document.getElementById('propGapY').value = Math.round(node.appData.gapY);
  }
  document.getElementById('propZField').classList.toggle('is-hidden', isBackground(node));

  const spineObj = isSpineObject(node);
  document.getElementById('propAnimNameField').classList.toggle('is-hidden', !spineObj);
  if (spineObj) {
    const anim = manifest.assets.animations.find((a) => a.id === node.appData.animation_ref);
    if (anim) {
      populatePropAnimNameSelect(anim.folder, node.appData.animation_name).then(() => {
        node.appData.animation_name = document.getElementById('propAnimName').value;
        syncLiveSpineAnimationName(node);
      });
    }
  }
}

function selectNode(node) {
  selectedNode = node;
  transformer.nodes([node]);
  layer.draw();
  updatePropsFromNode(node);
  document.getElementById('propsPanel').hidden = false;
  document.getElementById('propsLabel').textContent = isBackground(node)
    ? 'Фон экрана'
    : isSpineObject(node)
      ? 'Слой поверх (Spine)'
      : node.appData.type + (node.appData.image_ref ? '' : ' (без картинки)');
  renderLayersList();
}

function hideProps() {
  selectedNode = null;
  document.getElementById('propsPanel').hidden = true;
  renderLayersList();
}

function removeNode(node) {
  unregisterLiveSpine(node);
  const idx = objectNodes.indexOf(node);
  if (idx >= 0) objectNodes.splice(idx, 1);
  node.destroy();
  transformer.nodes([]);
  layer.draw();
  hideProps();
}

// ---------- reel-block placeholder: a real reels x rows cell grid, no
// image of its own (a frame/dimming image goes on top as its own
// decor.frame/decor.image object, ordered via z_index) ----------

function rebuildReelBlockCells(group, reels, rows, cellW, cellH, gapX, gapY) {
  group.destroyChildren();
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < reels; c++) {
      group.add(new Konva.Rect({
        x: c * (cellW + gapX), y: r * (cellH + gapY),
        width: cellW, height: cellH,
        fill: 'rgba(76,141,255,0.15)', stroke: '#4c8dff', strokeWidth: 1, dash: [6, 3],
        listening: false,
      }));
    }
  }
  group.width(reels * cellW + (reels - 1) * gapX);
  group.height(rows * cellH + (rows - 1) * gapY);
}

function setReelBlockGrid(group, reels, rows, cellW, cellH, gapX, gapY) {
  rebuildReelBlockCells(group, reels, rows, cellW, cellH, gapX, gapY);
  group.appData = { ...group.appData, reels, rows, cellW, cellH, gapX, gapY };
}

function makeReelBlockNode(reels, rows, cellW, cellH, gapX, gapY) {
  const group = new Konva.Group({ draggable: true });
  group.appData = {};
  setReelBlockGrid(group, reels, rows, cellW, cellH, gapX, gapY);
  return group;
}

// ---------- Spine placeholder box: a labeled dashed outline, same idea as
// the reel-block cell grid above. Once its real Spine bundle finishes
// loading (see registerLiveSpine below), the fill goes fully transparent so
// the actual live WebGL animation underneath is what's visible — the dashed
// stroke + Rect's hit region are what's left, purely for selecting/
// dragging/resizing. Before that resolves (or if it fails to load), the
// tinted box + label stay visible as a fallback so something is always
// shown. ----------

function rebuildSpinePlaceholder(group, name, w, h, transparent) {
  group.destroyChildren();
  group.add(new Konva.Rect({
    // listening stays default (true) here, unlike the reel-block cells this
    // pattern otherwise mirrors — a Konva Group has no hit region of its
    // own, only what its listening children contribute, so this Rect is
    // what makes the whole placeholder clickable/draggable directly on the
    // canvas (matching how a Konva.Image background already behaves).
    width: w, height: h,
    fill: transparent ? 'transparent' : 'rgba(255,140,66,0.12)',
    stroke: '#ff8c42', strokeWidth: 2, dash: [8, 4],
  }));
  if (!transparent) {
    group.add(new Konva.Text({
      width: w, height: h, text: `\u{1F3AC} ${name || 'Spine'}`, fontSize: 18, fill: '#ff8c42',
      align: 'center', verticalAlign: 'middle', padding: 8, listening: false,
    }));
  }
  group.width(w);
  group.height(h);
}

function makeSpinePlaceholderNode(name, w, h) {
  const group = new Konva.Group({ draggable: true });
  rebuildSpinePlaceholder(group, name, w, h);
  return group;
}

// ---------- live Spine playback in the editor: one shared WebGL canvas
// (layoutSpineCanvas, a sibling of #stageContainer inside #stageWrapper —
// see layout.html) plus a hidden per-node anchor <div> whose rect is kept
// in sync with the node's on-screen position/size so spine-engine.js's
// SpineInstance.anchorEl mechanism can position the skeleton correctly.
// Background goes on the base track (one at a time, matching its existing
// exclusivity); decor.spine overlay objects go on the overlay track, which
// already supports several simultaneous instances (same pattern east-
// discovery's expandedWildOverlays uses for concurrent reel-column FX). ----------

// Two separate canvases/stages, not one — a single WebGL canvas is one flat
// plane with ONE fixed position relative to the rest of the DOM, so
// addBase/addOverlay only orders Spine instances *among themselves*, not
// against Konva-drawn content. The background canvas sits behind Konva (so
// a Spine background is naturally hidden behind Konva-drawn decor, correct
// for a background); a decor.spine "layer on top" needs its own canvas
// sitting IN FRONT of Konva instead, or a static image background (drawn
// by Konva) always occludes it regardless of any z-index set on the Konva
// side — z-index only reorders content within Konva's own canvas, it can't
// reach across to a different canvas element.
let layoutSpineStage = null; // background — canvas behind Konva
let layoutSpineOverlayStage = null; // decor.spine "layers on top" — canvas in front of Konva
const liveSpineNodes = new Map(); // Konva node -> { anchorEl, instance, track }

function spineStageFor(track) {
  return track === 'base' ? layoutSpineStage : layoutSpineOverlayStage;
}

function syncSpineAnchor(node) {
  const entry = liveSpineNodes.get(node);
  if (!entry) return;
  const w = node.width() * node.scaleX();
  const h = node.height() * node.scaleY();
  entry.anchorEl.style.left = `${node.x() * scale}px`;
  entry.anchorEl.style.top = `${node.y() * scale}px`;
  entry.anchorEl.style.width = `${w * scale}px`;
  entry.anchorEl.style.height = `${h * scale}px`;
}

// Centers a node on the current device's native screen and stretches it to
// fill the whole width/height — the "На весь экран" quick action available
// on every background-step block (the background itself, and each named
// Spine overlay slot). Doesn't save on its own for non-background nodes —
// same convention as a manual drag/resize, which also waits for the
// block's own Save button / step confirm.
function fillScreenNode(node) {
  if (!node) return;
  const native = NATIVE[currentDevice];
  if (isSpineNode(node)) {
    rebuildSpinePlaceholder(node, node.appData.animation_name, native.w, native.h, node.appData._liveActive);
  } else {
    node.width(native.w);
    node.height(native.h);
  }
  node.x(0);
  node.y(0);
  syncSpineAnchor(node);
  layer.batchDraw();
  if (selectedNode === node) updatePropsFromNode(node);
}

function registerLiveSpine(node, folder, track) {
  const anchorEl = document.createElement('div');
  anchorEl.style.cssText = 'position:absolute; opacity:0; pointer-events:none;';
  document.getElementById('stageWrapper').appendChild(anchorEl);
  const entry = { anchorEl, instance: null, track };
  liveSpineNodes.set(node, entry);
  syncSpineAnchor(node);

  const stage = spineStageFor(track);
  SpineEngine.SpineResource.load(stage.assetManager, imgUrl(folder))
    .then((resource) => {
      if (!liveSpineNodes.has(node)) return; // torn down before the load finished
      const instance = resource.createInstance();
      instance.anchorEl = anchorEl;
      instance.fit = 1;
      instance.play(node.appData.animation_name || 'idle', true);
      entry.instance = instance;
      stage.addBase(instance);
      node.appData._liveActive = true;
      rebuildSpinePlaceholder(node, node.appData.animation_name, node.width(), node.height(), true);
      layer.batchDraw();
    })
    .catch(() => {
      node.appData._liveActive = false;
    });
}

function unregisterLiveSpine(node) {
  const entry = liveSpineNodes.get(node);
  if (!entry) return;
  if (entry.instance) spineStageFor(entry.track).removeBase(entry.instance);
  entry.anchorEl.remove();
  liveSpineNodes.delete(node);
}

// Called when the props panel's animation-name select changes for a
// decor.spine object — retargets the already-loaded instance without
// reloading the resource.
function syncLiveSpineAnimationName(node) {
  const entry = liveSpineNodes.get(node);
  if (entry && entry.instance) entry.instance.play(node.appData.animation_name || 'idle', true);
}

// ---------- shared node behavior ----------

function attachCommonHandlers(node) {
  node.on('click tap', () => selectNode(node));
  node.on('dblclick dbltap', () => {
    selectNode(node);
    const xInput = document.getElementById('propX');
    xInput.focus();
    xInput.select();
  });
  node.on('contextmenu', (e) => {
    e.evt.preventDefault();
    if (confirm('Удалить элемент?')) removeNode(node);
  });
  // No-ops for nodes not registered in liveSpineNodes (the map lookup
  // inside syncSpineAnchor is the guard) — safe to attach unconditionally.
  node.on('dragmove', () => syncSpineAnchor(node));
  node.on('transform', () => syncSpineAnchor(node));
  node.on('dragend', () => { if (selectedNode === node) updatePropsFromNode(node); });
  node.on('transformend', () => {
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    node.scaleX(1);
    node.scaleY(1);
    if (isReelBlock(node)) {
      const { reels, rows, cellW, cellH, gapX, gapY } = node.appData;
      setReelBlockGrid(node, reels, rows, cellW * scaleX, cellH * scaleY, gapX * scaleX, gapY * scaleY);
    } else if (isSpineNode(node)) {
      rebuildSpinePlaceholder(
        node, node.appData.animation_name,
        Math.max(5, node.width() * scaleX), Math.max(5, node.height() * scaleY),
        node.appData._liveActive,
      );
    } else {
      node.width(Math.max(5, node.width() * scaleX));
      node.height(Math.max(5, node.height() * scaleY));
    }
    syncSpineAnchor(node);
    if (selectedNode === node) updatePropsFromNode(node);
  });
}

// ---------- loading images onto the canvas ----------

function loadImageNode(assetId, category, file, centerX, centerY, role) {
  const img = new Image();
  img.onload = () => {
    let w = img.naturalWidth;
    let h = img.naturalHeight;
    const cap = 400;
    const shrink = Math.min(1, cap / Math.max(w, h));
    w = Math.round(w * shrink);
    h = Math.round(h * shrink);
    const type = category === 'hero' ? 'decor.hero'
      : category === 'ui' ? 'system.button'
      : category === 'frame' ? 'decor.frame'
      : category === 'reel_background' ? 'decor.reel_background'
      : category === 'hud' ? 'decor.hud'
      : 'decor.image';
    const node = new Konva.Image({ image: img, x: centerX - w / 2, y: centerY - h / 2, width: w, height: h, draggable: true });
    node.appData = { id: genId(), type, image_ref: assetId, role: role || null };
    attachCommonHandlers(node);
    layer.add(node);
    objectNodes.push(node);
    selectNode(node);
    layer.draw();
  };
  img.src = imgUrl(file);
}

function loadSavedObject(obj) {
  if (obj.type === 'system.reel_block') {
    // Falls back to deriving cell/gap from the saved w/h + current grid size
    // for reel_blocks saved before this feature existed (no cell_w etc. at
    // all) — same shape as neon-reels' real one.
    const { reels, rows } = getGridSize();
    const cellW = obj.cell_w ?? Math.max(10, (obj.w - DEFAULT_GAP * (reels - 1)) / reels);
    const cellH = obj.cell_h ?? Math.max(10, (obj.h - DEFAULT_GAP * (rows - 1)) / rows);
    const gapX = obj.gap_x ?? DEFAULT_GAP;
    const gapY = obj.gap_y ?? DEFAULT_GAP;
    const node = makeReelBlockNode(reels, rows, cellW, cellH, gapX, gapY);
    node.appData.id = obj.id;
    node.appData.type = obj.type;
    node.appData.image_ref = null;
    node.appData.role = obj.role || null;
    node.x(obj.x - node.width() / 2);
    node.y(obj.y - node.height() / 2);
    attachCommonHandlers(node);
    layer.add(node);
    objectNodes.push(node);
    layer.draw();
    renderLayersList();
    return;
  }

  if (obj.animation_ref) {
    const anim = manifest.assets.animations.find((a) => a.id === obj.animation_ref);
    if (!anim) return;
    const node = makeSpinePlaceholderNode(anim.name, obj.w, obj.h);
    node.x(obj.x - obj.w / 2);
    node.y(obj.y - obj.h / 2);
    node.appData = {
      id: obj.id, type: obj.type, animation_ref: obj.animation_ref, animation_name: obj.animation_name,
      role: obj.role || null,
    };
    attachCommonHandlers(node);
    layer.add(node);
    objectNodes.push(node);
    registerLiveSpine(node, anim.folder, 'overlay');
    layer.draw();
    renderLayersList();
    return;
  }

  if (obj.image_ref) {
    const asset = manifest.assets.images.find((i) => i.id === obj.image_ref);
    if (!asset) return;
    const img = new Image();
    img.onload = () => {
      const node = new Konva.Image({
        image: img, x: obj.x - obj.w / 2, y: obj.y - obj.h / 2, width: obj.w, height: obj.h, draggable: true,
      });
      node.appData = { id: obj.id, type: obj.type, image_ref: obj.image_ref, role: obj.role || null };
      attachCommonHandlers(node);
      layer.add(node);
      objectNodes.push(node);
      layer.draw();
      renderLayersList();
    };
    img.src = imgUrl(asset.file);
  }
}

async function saveBackgroundPosition() {
  if (!bgNode) return;
  setStatus('stepStatus', 'Сохраняю фон…');
  const payload = {
    device: currentDevice, screen: currentScreen,
    x: Math.round(bgNode.x() + bgNode.width() / 2),
    y: Math.round(bgNode.y() + bgNode.height() / 2),
    w: Math.round(bgNode.width()),
    h: Math.round(bgNode.height()),
  };
  if (isSpineNode(bgNode)) {
    payload.animation_ref = bgNode.appData.animation_ref;
    payload.animation_name = bgNode.appData.animation_name;
  } else {
    payload.asset_id = bgNode.appData.assetId;
  }
  try {
    manifest = await apiRequest('POST', `/games/${SLUG}/layout/background`, payload);
    setStatus('stepStatus', 'Фон сохранён.', 'is-ok');
    renderWizardProgress();
  } catch (err) {
    setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
  }
}

async function clearBackground() {
  setStatus('stepStatus', 'Убираю фон…');
  try {
    manifest = await apiRequest('POST', `/games/${SLUG}/layout/background`, { device: currentDevice, screen: currentScreen, asset_id: null });
    if (bgNode) { unregisterLiveSpine(bgNode); bgNode.destroy(); bgNode = null; }
    transformer.nodes([]);
    layer.draw();
    hideProps();
    hideAnimationNameSelect();
    renderBgSelect();
    renderWizardProgress();
    setStatus('stepStatus', 'Фон убран.', 'is-ok');
  } catch (err) {
    setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
  }
}

function attachBackgroundHandlers(node) {
  node.on('click tap', () => selectNode(node));
  node.on('dblclick dbltap', () => {
    selectNode(node);
    const xInput = document.getElementById('propX');
    xInput.focus();
    xInput.select();
  });
  node.on('contextmenu', (e) => {
    e.evt.preventDefault();
    if (confirm('Убрать фон экрана?')) clearBackground();
  });
  node.on('dragmove', () => syncSpineAnchor(node));
  node.on('transform', () => syncSpineAnchor(node));
  node.on('dragend', () => {
    if (selectedNode === node) updatePropsFromNode(node);
    saveBackgroundPosition();
  });
  node.on('transformend', () => {
    const newW = Math.max(5, node.width() * node.scaleX());
    const newH = Math.max(5, node.height() * node.scaleY());
    node.scaleX(1);
    node.scaleY(1);
    if (isSpineNode(node)) {
      rebuildSpinePlaceholder(node, node.appData.animation_name, newW, newH, node.appData._liveActive);
    } else {
      node.width(newW);
      node.height(newH);
    }
    syncSpineAnchor(node);
    if (selectedNode === node) updatePropsFromNode(node);
    saveBackgroundPosition();
  });
}

function loadBackgroundOnly() {
  if (bgNode) { unregisterLiveSpine(bgNode); bgNode.destroy(); bgNode = null; }
  const bg = manifest.layouts[currentDevice].backgrounds[currentScreen];
  if (!bg) { hideAnimationNameSelect(); layer.draw(); renderLayersList(); return; }

  if (bg.animation_ref) {
    const anim = manifest.assets.animations.find((a) => a.id === bg.animation_ref);
    if (!anim) { layer.draw(); renderLayersList(); return; }
    bgNode = makeSpinePlaceholderNode(anim.name, bg.w, bg.h);
    bgNode.x(bg.x - bg.w / 2);
    bgNode.y(bg.y - bg.h / 2);
    bgNode.appData = { animation_ref: bg.animation_ref, animation_name: bg.animation_name };
    attachBackgroundHandlers(bgNode);
    layer.add(bgNode);
    bgNode.moveToBottom();
    registerLiveSpine(bgNode, anim.folder, 'base');
    layer.draw();
    renderLayersList();
    populateAnimationNameSelect(anim.folder, bg.animation_name);
    return;
  }

  hideAnimationNameSelect();
  const asset = manifest.assets.images.find((i) => i.id === bg.asset_id);
  if (!asset) { layer.draw(); renderLayersList(); return; }
  const img = new Image();
  img.onload = () => {
    bgNode = new Konva.Image({
      image: img, x: bg.x - bg.w / 2, y: bg.y - bg.h / 2, width: bg.w, height: bg.h, draggable: true,
    });
    bgNode.appData = { assetId: bg.asset_id };
    attachBackgroundHandlers(bgNode);
    layer.add(bgNode);
    bgNode.moveToBottom();
    layer.draw();
    renderLayersList();
  };
  img.src = imgUrl(asset.file);
}

// ---------- animation-name picker: reads the real animation.json (a plain
// static file next to the atlas — no backend endpoint needed) so the
// dropdown always reflects what's actually inside a given Spine bundle,
// instead of guessing/hardcoding a name like "idle" that may not exist. ----------

function hideAnimationNameSelect() {
  document.getElementById('bgAnimNameField').classList.add('is-hidden');
}

async function populateAnimationSelect(selectEl, folder, selectedName) {
  selectEl.innerHTML = '<option>Загрузка…</option>';
  try {
    const res = await fetch(imgUrl(`${folder}/animation.json`));
    const json = await res.json();
    const names = Object.keys(json.animations || {});
    selectEl.innerHTML = '';
    for (const name of names) {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      selectEl.appendChild(opt);
    }
    selectEl.value = names.includes(selectedName) ? selectedName : names.includes('idle') ? 'idle' : (names[0] || '');
  } catch (err) {
    selectEl.innerHTML = '<option value="">— не удалось прочитать animation.json —</option>';
  }
}

function populateAnimationNameSelect(folder, selectedName) {
  document.getElementById('bgAnimNameField').classList.remove('is-hidden');
  return populateAnimationSelect(document.getElementById('bgAnimNameSelect'), folder, selectedName);
}

function populatePropAnimNameSelect(folder, selectedName) {
  return populateAnimationSelect(document.getElementById('propAnimName'), folder, selectedName);
}

async function saveAnimationBackground(animId, animName) {
  setStatus('stepStatus', 'Сохраняю фон…');
  try {
    manifest = await apiRequest('POST', `/games/${SLUG}/layout/background`, {
      device: currentDevice, screen: currentScreen, animation_ref: animId, animation_name: animName || null,
    });
    loadBackgroundOnly();
    renderWizardProgress();
    setStatus('stepStatus', 'Фон сохранён.', 'is-ok');
  } catch (err) {
    setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
  }
}

// ---------- named Spine overlay slots: three fixed, optional decor.spine
// slots on every background step (hero + two background-decoration layers),
// picked via <select> instead of free palette drag — a <select> can't leave
// an ambiguous "empty drag ghost" behind the way dragging a plain styled
// <div> chip could across browsers. Identified per screen+device by a
// stable `role` tag (already a free-form field, no schema change), the same
// way buy_bonus/free_spins_counter/multiplier are already tracked. ----------

const NAMED_SPINE_SLOTS = [
  { role: 'bg_hero_animation', title: '2. Анимация героя', w: 400, h: 400 },
  { role: 'bg_animation_1', title: '3. Анимация фона 1', w: 400, h: 400 },
  { role: 'bg_animation_2', title: '4. Анимация фона 2', w: 400, h: 400 },
];

function renderNamedSpineSlots() {
  const container = document.getElementById('namedSpineSlots');
  container.innerHTML = '';

  for (const slot of NAMED_SPINE_SLOTS) {
    const block = document.createElement('div');
    block.className = 'wizard-subblock';

    const heading = document.createElement('h4');
    heading.textContent = slot.title;
    block.appendChild(heading);

    const animLabel = document.createElement('label');
    animLabel.append('Анимация ');
    const animSelect = document.createElement('select');
    animLabel.appendChild(animSelect);
    block.appendChild(animLabel);

    const clipField = document.createElement('label');
    clipField.className = 'is-hidden';
    clipField.append('Клип ');
    const clipSelect = document.createElement('select');
    clipField.appendChild(clipSelect);
    block.appendChild(clipField);

    const fillBtn = document.createElement('button');
    fillBtn.className = 'btn';
    fillBtn.type = 'button';
    fillBtn.textContent = 'Отцентровать и растянуть на весь экран';
    block.appendChild(fillBtn);

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn';
    saveBtn.type = 'button';
    saveBtn.textContent = 'Сохранить';
    block.appendChild(saveBtn);

    const status = document.createElement('div');
    status.className = 'form-status';
    block.appendChild(status);

    animSelect.innerHTML = '<option value="">— нет —</option>';
    for (const anim of manifest.assets.animations) {
      const opt = document.createElement('option');
      opt.value = anim.id;
      opt.textContent = `\u{1F3AC} ${anim.name}`;
      animSelect.appendChild(opt);
    }

    const existingNode = objectNodes.find((n) => n.appData.role === slot.role);
    if (existingNode) {
      animSelect.value = existingNode.appData.animation_ref;
      const anim = manifest.assets.animations.find((a) => a.id === existingNode.appData.animation_ref);
      if (anim) {
        clipField.classList.remove('is-hidden');
        populateAnimationSelect(clipSelect, anim.folder, existingNode.appData.animation_name);
      }
    }

    animSelect.addEventListener('change', () => {
      const animId = animSelect.value;
      if (!animId) {
        clipField.classList.add('is-hidden');
        return;
      }
      const anim = manifest.assets.animations.find((a) => a.id === animId);
      if (anim) {
        clipField.classList.remove('is-hidden');
        populateAnimationSelect(clipSelect, anim.folder, null);
      }
    });

    fillBtn.addEventListener('click', () => {
      const node = objectNodes.find((n) => n.appData.role === slot.role);
      fillScreenNode(node);
    });

    saveBtn.addEventListener('click', () => saveNamedSpineSlot(slot, animSelect, clipSelect, status));

    container.appendChild(block);
  }
}

async function saveNamedSpineSlot(slot, animSelect, clipSelect, statusEl) {
  const animId = animSelect.value || null;
  const clipName = clipSelect.value || null;
  const existingNode = objectNodes.find((n) => n.appData.role === slot.role);

  statusEl.textContent = 'Сохраняю…';
  statusEl.className = 'form-status';

  try {
    if (!animId) {
      if (existingNode) removeNode(existingNode);
    } else if (!existingNode) {
      const anim = manifest.assets.animations.find((a) => a.id === animId);
      if (!anim) throw new Error('анимация не найдена');
      const native = NATIVE[currentDevice];
      const node = makeSpinePlaceholderNode(anim.name, slot.w, slot.h);
      node.x(native.w / 2 - slot.w / 2);
      node.y(native.h / 2 - slot.h / 2);
      node.appData = { id: genId(), type: 'decor.spine', animation_ref: animId, animation_name: clipName, role: slot.role };
      attachCommonHandlers(node);
      layer.add(node);
      objectNodes.push(node);
      registerLiveSpine(node, anim.folder, 'overlay');
      layer.draw();
    } else if (existingNode.appData.animation_ref !== animId) {
      unregisterLiveSpine(existingNode);
      const anim = manifest.assets.animations.find((a) => a.id === animId);
      if (!anim) throw new Error('анимация не найдена');
      rebuildSpinePlaceholder(existingNode, anim.name, existingNode.width(), existingNode.height(), false);
      existingNode.appData.animation_ref = animId;
      existingNode.appData.animation_name = clipName;
      registerLiveSpine(existingNode, anim.folder, 'overlay');
      layer.draw();
    } else if (existingNode.appData.animation_name !== clipName) {
      existingNode.appData.animation_name = clipName;
      syncLiveSpineAnimationName(existingNode);
    }

    await saveCurrentScreenObjects();
    renderLayersList();
    statusEl.textContent = 'Сохранено.';
    statusEl.className = 'form-status is-ok';
  } catch (err) {
    statusEl.textContent = `Ошибка: ${err.message}`;
    statusEl.className = 'form-status is-error';
  }
}

function renderObjectsForScreen() {
  objectNodes.forEach((n) => { unregisterLiveSpine(n); n.destroy(); });
  objectNodes = [];
  transformer.nodes([]);
  hideProps();
  loadBackgroundOnly();

  const screenObjects = manifest.layouts[currentDevice].screens[currentScreen] || [];
  for (const obj of [...screenObjects].sort((a, b) => a.z_index - b.z_index)) {
    loadSavedObject(obj);
  }
  renderNamedSpineSlots();
}

// ---------- layers panel: everything currently placed, with a reset button ----------

function layerLabel(node) {
  if (isBackground(node)) {
    if (isSpineNode(node)) {
      const anim = manifest.assets.animations.find((a) => a.id === node.appData.animation_ref);
      return `Фон (Spine): ${anim ? anim.name : '?'}`;
    }
    const asset = manifest.assets.images.find((i) => i.id === node.appData.assetId);
    return `Фон: ${asset ? asset.file : '?'}`;
  }
  if (isReelBlock(node)) return 'Блок барабанов';
  if (isSpineObject(node)) {
    const anim = manifest.assets.animations.find((a) => a.id === node.appData.animation_ref);
    return `Слой поверх (Spine): ${anim ? anim.name : '?'}`;
  }
  const asset = node.appData.image_ref ? manifest.assets.images.find((i) => i.id === node.appData.image_ref) : null;
  return `${node.appData.type}${asset ? ': ' + asset.file : ''}`;
}

// Fixes the relative order of the roles in ROLE_PRIORITY (reel background
// below reels below frame) without disturbing where they sit relative to
// anything else in the stack, then unconditionally pins the logo above
// literally everything — the one role that's "above all", not just above
// its three siblings. Runs every render so it self-corrects after a drag,
// an add, a delete, or a fresh load, no matter what the user just did.
function enforceRolePriority() {
  const prioritized = [];
  objectNodes.forEach((n, i) => { if (n.appData.role in ROLE_PRIORITY) prioritized.push(i); });
  const sorted = prioritized.map((i) => objectNodes[i])
    .sort((a, b) => ROLE_PRIORITY[a.appData.role] - ROLE_PRIORITY[b.appData.role]);
  prioritized.forEach((slot, k) => { objectNodes[slot] = sorted[k]; });

  const logoIdx = objectNodes.findIndex((n) => n.appData.role === 'slot_logo');
  if (logoIdx !== -1 && logoIdx !== objectNodes.length - 1) {
    const [logoNode] = objectNodes.splice(logoIdx, 1);
    objectNodes.push(logoNode);
  }

  const bgOffset = bgNode ? 1 : 0;
  objectNodes.forEach((n, i) => n.zIndex(i + bgOffset));
  layer.batchDraw();
}

// Drag-reorder in the layers list: entryIdx includes the background slot
// (index 0 when present), which can't be moved or be a drop target — it's
// always the bottom of the stack, handled separately from objectNodes.
function reorderLayer(fromEntryIdx, toEntryIdx) {
  const bgOffset = bgNode ? 1 : 0;
  const fromIdx = fromEntryIdx - bgOffset;
  const toIdx = toEntryIdx - bgOffset;
  if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0) return;
  const [moved] = objectNodes.splice(fromIdx, 1);
  objectNodes.splice(toIdx, 0, moved);
  renderLayersList();
}

function renderLayersList() {
  enforceRolePriority();
  const list = document.getElementById('layersList');
  list.innerHTML = '';
  const entries = [...(bgNode ? [bgNode] : []), ...objectNodes];
  document.getElementById('layersEmpty').hidden = entries.length > 0;

  entries.forEach((node, entryIdx) => {
    const li = document.createElement('li');
    li.className = node === selectedNode ? 'is-selected' : '';
    const draggableNode = !isBackground(node);
    li.draggable = draggableNode;
    if (draggableNode) li.classList.add('is-draggable');
    li.addEventListener('click', () => selectNode(node));
    li.addEventListener('dragstart', (e) => {
      draggedEntryIndex = entryIdx;
      e.dataTransfer.effectAllowed = 'move';
    });
    li.addEventListener('dragover', (e) => {
      if (draggedEntryIndex === null || isBackground(node)) return;
      e.preventDefault();
      li.classList.add('is-drag-over');
    });
    li.addEventListener('dragleave', () => li.classList.remove('is-drag-over'));
    li.addEventListener('drop', (e) => {
      e.preventDefault();
      li.classList.remove('is-drag-over');
      if (draggedEntryIndex !== null) reorderLayer(draggedEntryIndex, entryIdx);
      draggedEntryIndex = null;
    });
    li.addEventListener('dragend', () => { draggedEntryIndex = null; });
    const name = document.createElement('span');
    name.className = 'layer-name';
    name.textContent = layerLabel(node);
    const del = document.createElement('button');
    del.className = 'list-delete';
    del.type = 'button';
    del.title = 'Сбросить';
    del.textContent = '×';
    del.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!confirm('Сбросить элемент?')) return;
      if (isBackground(node)) clearBackground();
      else removeNode(node);
    });
    li.appendChild(name);
    li.appendChild(del);
    list.appendChild(li);
  });
}

// ---------- asset palette (right panel): every uploaded image, always —
// no category/screen/device filtering. Tags used to gate which images
// showed up per step/screen/device, which meant an asset tagged for the
// wrong combination was invisible right when you needed to reuse it; now
// everything's always there and you pick the right one yourself while
// walking through the steps. ----------

function palettableImages() {
  return manifest.assets.images.filter((img) => img.category !== 'catalog');
}

function renderPaletteForStep(step) {
  const palette = document.getElementById('assetPalette');
  palette.innerHTML = '<h3>Материалы</h3>';

  if (step.kind === 'background') {
    palette.innerHTML += '<p class="palette-empty">Для фона и слоёв анимации используй блоки слева.</p>';
    return;
  }

  const images = palettableImages();
  if (images.length === 0) {
    palette.innerHTML += '<p class="palette-empty">Пока ничего не загружено — загрузи материалы на Этапе 2 или кнопкой выше.</p>';
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'palette-grid';
  for (const img of images) {
    const thumb = document.createElement('img');
    thumb.className = 'palette-thumb';
    thumb.src = imgUrl(img.file);
    thumb.draggable = true;
    thumb.title = img.file;
    thumb.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', JSON.stringify({ assetId: img.id, category: img.category, file: img.file }));
    });
    grid.appendChild(thumb);
  }
  palette.appendChild(grid);
}

function renderBgSelect() {
  const select = document.getElementById('bgSelect');
  select.innerHTML = '<option value="">— нет —</option>';
  for (const img of palettableImages()) {
    const opt = document.createElement('option');
    opt.value = `img:${img.id}`;
    opt.textContent = img.file;
    select.appendChild(opt);
  }
  for (const anim of manifest.assets.animations) {
    const opt = document.createElement('option');
    opt.value = `anim:${anim.id}`;
    opt.textContent = `\u{1F3AC} ${anim.name}`;
    select.appendChild(opt);
  }
  const bg = manifest.layouts[currentDevice].backgrounds[currentScreen];
  select.value = bg && bg.animation_ref ? `anim:${bg.animation_ref}` : bg && bg.asset_id ? `img:${bg.asset_id}` : '';
}

// ---------- stage sizing (Konva-native scale-to-fit, not CSS transform) ----------

function setupStageSize() {
  const native = NATIVE[currentDevice];
  const area = document.getElementById('canvasArea');
  const maxW = area.clientWidth - 24;
  const maxH = window.innerHeight - 260;
  scale = Math.min(maxW / native.w, maxH / native.h, 1);
  stage.width(native.w * scale);
  stage.height(native.h * scale);
  stage.scale({ x: scale, y: scale });
  liveSpineNodes.forEach((_entry, node) => syncSpineAnchor(node));
}

// ---------- wizard controller ----------

function showStepControls(step) {
  const blocks = { background: 'bgControls', slot: 'slotControls', ui: 'uiControls', hud: 'hudControls' };
  for (const id of Object.values(blocks)) document.getElementById(id).classList.add('is-hidden');
  document.getElementById(blocks[step.kind]).classList.remove('is-hidden');
}

function renderWizardProgress() {
  const container = document.getElementById('wizardProgress');
  container.innerHTML = '';
  wizardSteps.forEach((step, i) => {
    const chip = document.createElement('span');
    chip.className = 'wizard-step-chip';
    chip.textContent = `${i + 1}. ${step.title}`;
    const done = isStepDone(step);
    if (done) chip.classList.add('is-done');
    if (i === currentStepIndex) chip.classList.add('is-current');
    if (!done && i > currentStepIndex) chip.classList.add('is-locked');
    if (done || i <= currentStepIndex) {
      chip.addEventListener('click', () => goToStep(i));
    }
    container.appendChild(chip);
  });
}

function showWizardComplete() {
  document.getElementById('stepTitle').textContent = 'Готово!';
  document.getElementById('stepHint').textContent = 'Все шаги вёрстки пройдены.';
  for (const id of ['bgControls', 'slotControls', 'uiControls', 'hudControls']) {
    document.getElementById(id).classList.add('is-hidden');
  }
  document.getElementById('prevStepBtn').hidden = false;
  document.getElementById('skipStepBtn').hidden = true;
  document.getElementById('confirmStepBtn').textContent = 'К тесту →';
  document.getElementById('confirmStepBtn').onclick = () => {
    window.location.href = `preview.html?slug=${encodeURIComponent(SLUG)}`;
  };
  renderWizardProgress();
}

async function goToStep(index) {
  if (index >= wizardSteps.length) {
    currentStepIndex = wizardSteps.length;
    showWizardComplete();
    return;
  }
  currentStepIndex = index;
  const step = wizardSteps[index];
  currentDevice = step.device;
  currentScreen = step.screen;

  setStatus('stepStatus', 'Загружаю…');
  try {
    manifest = await apiRequest('GET', `/games/${SLUG}`);
  } catch (err) {
    setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
    return;
  }

  document.getElementById('stepTitle').textContent = `${index + 1}. ${step.title}`;
  document.getElementById('stepHint').textContent = step.hint;
  document.getElementById('confirmStepBtn').textContent = 'Подтвердить и продолжить →';
  document.getElementById('confirmStepBtn').onclick = () => confirmStep();
  document.getElementById('prevStepBtn').hidden = index === 0;
  document.getElementById('skipStepBtn').hidden = !isSkippable(step);
  setStatus('stepStatus', '');

  showStepControls(step);
  setupStageSize();
  renderBgSelect();
  renderObjectsForScreen();
  renderPaletteForStep(step);
  renderWizardProgress();
}

function nodeToPayload(node, i) {
  return {
    id: node.appData.id,
    type: node.appData.type,
    image_ref: node.appData.image_ref || null,
    animation_ref: node.appData.animation_ref || null,
    animation_name: node.appData.animation_name || null,
    role: node.appData.role || null,
    x: Math.round(node.x() + node.width() / 2),
    y: Math.round(node.y() + node.height() / 2),
    w: Math.round(node.width()),
    h: Math.round(node.height()),
    z_index: i,
    cell_w: isReelBlock(node) ? Math.round(node.appData.cellW) : null,
    cell_h: isReelBlock(node) ? Math.round(node.appData.cellH) : null,
    gap_x: isReelBlock(node) ? Math.round(node.appData.gapX) : null,
    gap_y: isReelBlock(node) ? Math.round(node.appData.gapY) : null,
  };
}

async function saveCurrentScreenObjects() {
  const objects = objectNodes.map((node, i) => nodeToPayload(node, i));
  manifest = await apiRequest('POST', `/games/${SLUG}/layout/objects`, { device: currentDevice, screen: currentScreen, objects });
}

async function mirrorSlotObjectsToOtherScreen(step) {
  const otherScreen = step.screen === 'base' ? 'bonus' : 'base';
  const mirrorRoles = new Set(['slot_reel_block', 'slot_frame', 'slot_logo', 'slot_reel_background', 'slot_decor']);
  const mirrorObjects = objectNodes.filter((n) => mirrorRoles.has(n.appData.role)).map((node, i) => nodeToPayload(node, i));
  const existingOther = (manifest.layouts[step.device].screens[otherScreen] || []).filter((o) => !mirrorRoles.has(o.role));
  const merged = [...existingOther, ...mirrorObjects];
  manifest = await apiRequest('POST', `/games/${SLUG}/layout/objects`, { device: step.device, screen: otherScreen, objects: merged });
}

// Guards confirmStep/goToPrevStep against re-entrant double-invocation
// (e.g. a rapid double-click, or a duplicate event) — without it, two
// overlapping calls both read the same currentStepIndex before either
// finishes advancing it, and the wizard silently skips a step.
let stepActionInFlight = false;

async function confirmStep() {
  if (stepActionInFlight) return;
  stepActionInFlight = true;
  try {
    const step = wizardSteps[currentStepIndex];

    if (step.kind === 'background') {
      if (!manifest.layouts[step.device].backgrounds[step.screen]) {
        setStatus('stepStatus', 'Сначала выбери или загрузи фон.', 'is-error');
        return;
      }
      await goToStep(currentStepIndex + 1);
      return;
    }

    const hasRole = step.kind === 'slot'
      ? objectNodes.some((n) => n.appData.role === 'slot_reel_block')
      : objectNodes.some((n) => n.appData.role === step.role);
    if (!hasRole) {
      setStatus('stepStatus', 'Сначала разместите нужный элемент на сцене.', 'is-error');
      return;
    }

    setStatus('stepStatus', 'Сохраняю…');
    try {
      await saveCurrentScreenObjects();
      if (step.kind === 'slot') {
        await mirrorSlotObjectsToOtherScreen(step);
      }
      setStatus('stepStatus', 'Сохранено.', 'is-ok');
      await goToStep(currentStepIndex + 1);
    } catch (err) {
      setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  } finally {
    stepActionInFlight = false;
  }
}

async function skipStep() {
  if (stepActionInFlight) return;
  stepActionInFlight = true;
  try {
    const step = wizardSteps[currentStepIndex];
    if (!isSkippable(step)) return;
    setStatus('stepStatus', 'Пропускаю…');
    try {
      manifest = await apiRequest('POST', `/games/${SLUG}/layout/skip`, { step_id: step.id, skipped: true });
      await goToStep(currentStepIndex + 1);
    } catch (err) {
      setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  } finally {
    stepActionInFlight = false;
  }
}

async function goToPrevStep() {
  if (stepActionInFlight || currentStepIndex === 0) return;
  stepActionInFlight = true;
  try {
    setStatus('stepStatus', 'Сохраняю…');
    try {
      await saveCurrentScreenObjects();
    } catch (err) {
      setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
      return;
    }
    await goToStep(currentStepIndex - 1);
  } finally {
    stepActionInFlight = false;
  }
}

// ---------- init ----------

async function init() {
  if (!SLUG) {
    document.body.innerHTML = '<section class="panel"><p class="hint">Не указан слаг слота (нет ?slug=... в адресе). Вернись к <a href="new.html">списку слотов</a>.</p></section>';
    return;
  }

  manifest = await apiRequest('GET', `/games/${SLUG}`);
  document.getElementById('slotName').textContent = `— ${manifest.meta.display_name} (${manifest.meta.slug})`;
  document.title = `Конструктор слота — ${manifest.meta.display_name} — Этап 4`;

  wizardSteps = buildWizardSteps();

  layoutSpineStage = new SpineEngine.SpineStage(document.getElementById('layoutSpineCanvas'));
  layoutSpineOverlayStage = new SpineEngine.SpineStage(document.getElementById('layoutSpineOverlayCanvas'));

  stage = new Konva.Stage({ container: 'stageContainer', width: 100, height: 100 });
  layer = new Konva.Layer();
  stage.add(layer);
  transformer = new Konva.Transformer({ rotateEnabled: false, borderStroke: '#4c8dff', anchorStroke: '#4c8dff' });
  layer.add(transformer);

  stage.on('click tap', (e) => {
    if (e.target === stage) {
      transformer.nodes([]);
      layer.draw();
      hideProps();
    }
  });

  const stageContainerEl = document.getElementById('stageContainer');
  stageContainerEl.addEventListener('dragover', (e) => e.preventDefault());
  stageContainerEl.addEventListener('drop', (e) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData('text/plain');
    if (!raw) return;
    const data = JSON.parse(raw);
    const rect = stageContainerEl.getBoundingClientRect();
    const nativeX = (e.clientX - rect.left) / scale;
    const nativeY = (e.clientY - rect.top) / scale;
    const { assetId, category, file } = data;
    const role = roleForCategory(wizardSteps[currentStepIndex], category);
    loadImageNode(assetId, category, file, nativeX, nativeY, role);
  });

  document.getElementById('bgSelect').addEventListener('change', async (e) => {
    const value = e.target.value;
    if (!value) { await clearBackground(); return; }
    const [kind, id] = value.split(':');
    if (kind === 'anim') {
      const anim = manifest.assets.animations.find((a) => a.id === id);
      await populateAnimationNameSelect(anim.folder, null);
      await saveAnimationBackground(id, document.getElementById('bgAnimNameSelect').value);
      return;
    }
    hideAnimationNameSelect();
    setStatus('stepStatus', 'Сохраняю фон…');
    try {
      manifest = await apiRequest('POST', `/games/${SLUG}/layout/background`, { device: currentDevice, screen: currentScreen, asset_id: id });
      loadBackgroundOnly();
      renderWizardProgress();
      setStatus('stepStatus', 'Фон сохранён.', 'is-ok');
    } catch (err) {
      setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('bgAnimNameSelect').addEventListener('change', (e) => {
    const bg = manifest.layouts[currentDevice].backgrounds[currentScreen];
    if (bg && bg.animation_ref) saveAnimationBackground(bg.animation_ref, e.target.value);
  });

  document.getElementById('addBgBtn').addEventListener('click', () => document.getElementById('bgFileInput').click());
  document.getElementById('bgFileInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    setStatus('stepStatus', 'Загружаю фон…');
    try {
      const formData = new FormData();
      formData.set('kind', 'image');
      formData.set('category', 'background');
      formData.set('screen', currentScreen);
      formData.set('device', currentDevice);
      formData.set('file', file);
      manifest = await apiUpload(`/games/${SLUG}/assets`, formData);
      const uploaded = manifest._uploaded_asset_id;
      manifest = await apiRequest('POST', `/games/${SLUG}/layout/background`, { device: currentDevice, screen: currentScreen, asset_id: uploaded });
      renderBgSelect();
      loadBackgroundOnly();
      renderWizardProgress();
      setStatus('stepStatus', 'Фон добавлен и установлен.', 'is-ok');
    } catch (err) {
      setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
    }
  });

  document.getElementById('bgFillScreenBtn').addEventListener('click', () => {
    if (!bgNode) return;
    fillScreenNode(bgNode);
    saveBackgroundPosition();
  });

  document.getElementById('addReelBlockBtn').addEventListener('click', () => {
    const native = NATIVE[currentDevice];
    const { reels, rows } = getGridSize();
    const targetW = native.w * 0.5;
    const targetH = native.h * 0.7;
    const cellW = Math.max(10, (targetW - DEFAULT_GAP * (reels - 1)) / reels);
    const cellH = Math.max(10, (targetH - DEFAULT_GAP * (rows - 1)) / rows);
    const node = makeReelBlockNode(reels, rows, cellW, cellH, DEFAULT_GAP, DEFAULT_GAP);
    node.appData.id = genId();
    node.appData.type = 'system.reel_block';
    node.appData.image_ref = null;
    node.appData.role = 'slot_reel_block';
    node.x(native.w / 2 - node.width() / 2);
    node.y(native.h / 2 - node.height() / 2);
    attachCommonHandlers(node);
    layer.add(node);
    objectNodes.push(node);
    selectNode(node);
    layer.draw();
  });

  function setupImageQuickAdd(btnId, inputId, category) {
    document.getElementById(btnId).addEventListener('click', () => document.getElementById(inputId).click());
    document.getElementById(inputId).addEventListener('change', async (e) => {
      const file = e.target.files[0];
      e.target.value = '';
      if (!file) return;
      setStatus('stepStatus', 'Загружаю…');
      try {
        const formData = new FormData();
        formData.set('kind', 'image');
        formData.set('category', category);
        formData.set('screen', currentScreen);
        formData.set('device', currentDevice);
        formData.set('file', file);
        manifest = await apiUpload(`/games/${SLUG}/assets`, formData);
        const assetId = manifest._uploaded_asset_id;
        const asset = manifest.assets.images.find((i) => i.id === assetId);
        renderPaletteForStep(wizardSteps[currentStepIndex]);
        const role = roleForCategory(wizardSteps[currentStepIndex], category);
        loadImageNode(assetId, category, asset.file, NATIVE[currentDevice].w / 2, NATIVE[currentDevice].h / 2, role);
        setStatus('stepStatus', 'Добавлено.', 'is-ok');
      } catch (err) {
        setStatus('stepStatus', `Ошибка: ${err.message}`, 'is-error');
      }
    });
  }
  setupImageQuickAdd('addReelBgBtn', 'reelBgFileInput', 'reel_background');
  setupImageQuickAdd('addFrameBtn', 'frameFileInput', 'frame');
  setupImageQuickAdd('addLogoBtn', 'logoFileInput', 'logo');
  setupImageQuickAdd('addUiBtn', 'uiFileInput', 'ui');
  setupImageQuickAdd('addHudBtn', 'hudFileInput', 'hud');

  document.getElementById('propX').addEventListener('input', (e) => {
    if (!selectedNode) return;
    selectedNode.x(Number(e.target.value) - selectedNode.width() / 2);
    syncSpineAnchor(selectedNode);
    layer.batchDraw();
    if (isBackground(selectedNode)) saveBackgroundPosition();
  });
  document.getElementById('propY').addEventListener('input', (e) => {
    if (!selectedNode) return;
    selectedNode.y(Number(e.target.value) - selectedNode.height() / 2);
    syncSpineAnchor(selectedNode);
    layer.batchDraw();
    if (isBackground(selectedNode)) saveBackgroundPosition();
  });
  document.getElementById('propW').addEventListener('input', (e) => {
    if (!selectedNode || isReelBlock(selectedNode)) return;
    const cx = selectedNode.x() + selectedNode.width() / 2;
    const newW = Math.max(5, Number(e.target.value));
    if (isSpineNode(selectedNode)) {
      rebuildSpinePlaceholder(selectedNode, selectedNode.appData.animation_name, newW, selectedNode.height(), selectedNode.appData._liveActive);
    } else {
      selectedNode.width(newW);
    }
    selectedNode.x(cx - selectedNode.width() / 2);
    syncSpineAnchor(selectedNode);
    layer.batchDraw();
    if (isBackground(selectedNode)) saveBackgroundPosition();
  });
  document.getElementById('propH').addEventListener('input', (e) => {
    if (!selectedNode || isReelBlock(selectedNode)) return;
    const cy = selectedNode.y() + selectedNode.height() / 2;
    const newH = Math.max(5, Number(e.target.value));
    if (isSpineNode(selectedNode)) {
      rebuildSpinePlaceholder(selectedNode, selectedNode.appData.animation_name, selectedNode.width(), newH, selectedNode.appData._liveActive);
    } else {
      selectedNode.height(newH);
    }
    selectedNode.y(cy - selectedNode.height() / 2);
    syncSpineAnchor(selectedNode);
    layer.batchDraw();
    if (isBackground(selectedNode)) saveBackgroundPosition();
  });

  function applyReelBlockCellChange() {
    if (!selectedNode || !isReelBlock(selectedNode)) return;
    const cellW = Math.max(1, Number(document.getElementById('propCellW').value));
    const cellH = Math.max(1, Number(document.getElementById('propCellH').value));
    const gapX = Math.max(0, Number(document.getElementById('propGapX').value));
    const gapY = Math.max(0, Number(document.getElementById('propGapY').value));
    const cx = selectedNode.x() + selectedNode.width() / 2;
    const cy = selectedNode.y() + selectedNode.height() / 2;
    const { reels, rows } = selectedNode.appData;
    setReelBlockGrid(selectedNode, reels, rows, cellW, cellH, gapX, gapY);
    selectedNode.x(cx - selectedNode.width() / 2);
    selectedNode.y(cy - selectedNode.height() / 2);
    updatePropsFromNode(selectedNode);
    layer.batchDraw();
  }
  document.getElementById('propCellW').addEventListener('input', applyReelBlockCellChange);
  document.getElementById('propCellH').addEventListener('input', applyReelBlockCellChange);
  document.getElementById('propGapX').addEventListener('input', applyReelBlockCellChange);
  document.getElementById('propGapY').addEventListener('input', applyReelBlockCellChange);
  document.getElementById('propAnimName').addEventListener('change', (e) => {
    if (!selectedNode || !isSpineObject(selectedNode)) return;
    selectedNode.appData.animation_name = e.target.value;
    syncLiveSpineAnimationName(selectedNode);
  });
  document.getElementById('propZ').addEventListener('change', (e) => {
    if (!selectedNode || isBackground(selectedNode)) return;
    const bgOffset = bgNode ? 1 : 0;
    const idx = Math.max(0, Math.min(objectNodes.length - 1, Number(e.target.value)));
    selectedNode.zIndex(idx + bgOffset);
    objectNodes = layer.getChildren().filter((n) => n !== transformer && n !== bgNode);
    layer.batchDraw();
    renderLayersList();
  });
  document.getElementById('propsDeleteBtn').addEventListener('click', () => {
    if (!selectedNode) return;
    if (isBackground(selectedNode)) {
      if (confirm('Убрать фон экрана?')) clearBackground();
      return;
    }
    if (confirm('Удалить элемент?')) removeNode(selectedNode);
  });

  // confirmStepBtn's click handler is (re)assigned via .onclick in goToStep()/
  // showWizardComplete() instead of addEventListener here, since it needs to
  // change target (confirmStep vs. jumping to preview.html) per step — an
  // addEventListener here would double-fire alongside that reassignment.
  document.getElementById('prevStepBtn').addEventListener('click', () => goToPrevStep());
  document.getElementById('skipStepBtn').addEventListener('click', () => skipStep());

  window.addEventListener('resize', setupStageSize);

  goToStep(findResumeIndex());
}

init().catch((err) => {
  document.body.innerHTML = `<section class="panel"><p class="hint">Не удалось загрузить слот "${SLUG}": ${err.message}</p></section>`;
});
