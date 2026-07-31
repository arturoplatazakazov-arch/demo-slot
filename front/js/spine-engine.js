// Generic Spine 4.1 runtime glue: one shared WebGL canvas/AssetManager, resource
// caching per skeleton folder, and lightweight per-use instances positioned against
// arbitrary DOM elements (so the DOM/CSS layout stays the single source of truth
// for where things sit on screen, and Spine only has to know how to draw itself there).

const spineResourceCache = new Map();

function spineLoadTextureAtlas(assetManager, path) {
  return new Promise((resolve, reject) => {
    assetManager.loadTextureAtlas(path, (_p, atlas) => resolve(atlas), (_p, msg) => reject(new Error(msg)));
  });
}

function spineLoadJson(assetManager, path) {
  return new Promise((resolve, reject) => {
    assetManager.loadJson(path, (_p, json) => resolve(json), (_p, msg) => reject(new Error(msg)));
  });
}

class SpineResource {
  constructor(skeletonData, premultipliedAlpha = true) {
    this.skeletonData = skeletonData;
    this.animationStateData = new spine.AnimationStateData(skeletonData);
    // Whether this skeleton's texture atlas PNG was exported with
    // premultiplied alpha — must match the actual file or any semi-
    // transparent pixel (glows, soft edges, gradients) blends with the
    // wrong color, typically a hard edge on what should be a soft
    // gradient. Confirmed by sampling pixels directly: Amy's Fruit Farm's
    // exports are true PMA (RGB <= alpha everywhere), East Discovery's are
    // straight/non-premultiplied alpha (RGB routinely exceeds alpha in
    // semi-transparent regions, which is impossible under real PMA) — two
    // different export pipelines, not a bug in either asset set on its
    // own, just two different conventions this flag needs to track per
    // resource rather than assume globally.
    this.premultipliedAlpha = premultipliedAlpha;
    // Setup-pose bounding box, used to center/fit instances inside a target DOM rect.
    this.bounds = {
      x: skeletonData.x,
      y: skeletonData.y,
      width: skeletonData.width,
      height: skeletonData.height,
    };
  }

  static load(assetManager, folderPath, { premultipliedAlpha = true } = {}) {
    if (spineResourceCache.has(folderPath)) return spineResourceCache.get(folderPath);
    const promise = (async () => {
      const [atlas, json] = await Promise.all([
        spineLoadTextureAtlas(assetManager, `${folderPath}/animation.atlas`),
        spineLoadJson(assetManager, `${folderPath}/animation.json`),
      ]);
      const atlasLoader = new spine.AtlasAttachmentLoader(atlas);
      const skeletonJson = new spine.SkeletonJson(atlasLoader);
      const skeletonData = skeletonJson.readSkeletonData(json);
      return new SpineResource(skeletonData, premultipliedAlpha);
    })();
    spineResourceCache.set(folderPath, promise);
    return promise;
  }

  createInstance() {
    return new SpineInstance(this);
  }
}

class SpineInstance {
  constructor(resource) {
    this.resource = resource;
    this.skeleton = new spine.Skeleton(resource.skeletonData);
    this.animationState = new spine.AnimationState(resource.animationStateData);
    this.anchorEl = null;
    this.fit = 0.9;
    // 'contain' (default) scales by whichever axis is tighter, so the whole
    // skeleton fits inside the anchor with no cropping — right for grid
    // symbols/popups/character, where the asset and anchor share roughly the
    // same aspect ratio. 'height'/'width' instead scale by just that one
    // axis, letting the other overflow the anchor — needed for the
    // reel-height big wild (east-discovery's revealExpandedWild/
    // previewBigWild): its art is proportioned wider-relative-to-height than
    // a single reel column, so 'contain' would fit the width and leave the
    // reel only half-covered top-to-bottom instead of filling it edge to
    // edge like the reference art (the overlap into neighboring columns is
    // intentional there, not a bug).
    this.fitMode = 'contain';
    // Fraction of the height-anchor's own height to shift the instance up
    // by (0 = centered, default). Positive = up.
    this.verticalOffsetRatio = 0;
    // Overrides resource.bounds for the fit-to-anchor math below — needed
    // when an instance only shows a subset of its skeleton's slots (see
    // east-discovery's setupEnvironment, which splits one multi-slot
    // skeleton into independently-anchored pieces): the shared resource's
    // bounds cover every slot, but a piece showing only one slot should
    // fit-to-anchor using just that slot's own bounds. Set via
    // `skeleton.getBoundsRect()` after hiding the unwanted slots.
    this.boundsOverride = null;
    this.onSettle = null; // fires once when the current non-looping animation completes
    this.animationState.addListener({
      complete: (entry) => {
        if (!entry.loop && this.onSettle) this.onSettle();
      },
    });
  }

  play(name, loop = false) {
    this.animationState.setAnimation(0, name, loop);
    return this;
  }

  queue(name, loop = false, delay = 0) {
    this.animationState.addAnimation(0, name, loop, delay);
    return this;
  }

  update(delta, canvasEl) {
    if (this.anchorEl) this._placeInAnchor(canvasEl);
    this.animationState.update(delta);
    this.animationState.apply(this.skeleton);
    this.skeleton.updateWorldTransform();
  }

  _placeInAnchor(canvasEl) {
    const canvasRect = canvasEl.getBoundingClientRect();
    const elRect = this.anchorEl.getBoundingClientRect();
    // heightAnchorEl: source the vertical extent/center from a *different*
    // element than anchorEl — needed for the reel-height big wild, whose
    // horizontal center must stay on its own reel column (anchorEl) but
    // whose height must match the frame's actual visible hole, not
    // .reel__col/.reel__strip (both deliberately taller than the hole, for
    // the reel-loop scroll/mask trick — see revealExpandedWild).
    const heightRect = this.heightAnchorEl ? this.heightAnchorEl.getBoundingClientRect() : elRect;
    const dpr = window.devicePixelRatio || 1;

    const left = elRect.left - canvasRect.left;
    const top = heightRect.top - canvasRect.top;
    const cx = (left + elRect.width / 2) * dpr;
    const cy = (top + heightRect.height / 2) * dpr - this.verticalOffsetRatio * heightRect.height * dpr;

    // Camera is centered on the canvas with Y pointing up (spine-webgl ResizeMode.Expand default).
    const worldX = cx - canvasEl.width / 2;
    const worldY = canvasEl.height / 2 - cy;

    const b = this.boundsOverride || this.resource.bounds;
    const widthScale = (elRect.width * dpr) / b.width;
    const heightScale = (heightRect.height * dpr) / b.height;
    const fitScale =
      this.fitMode === 'height' ? heightScale : this.fitMode === 'width' ? widthScale : Math.min(widthScale, heightScale);
    const scale = this.fit * fitScale;
    const boundsCenterX = b.x + b.width / 2;
    const boundsCenterY = b.y + b.height / 2;

    this.skeleton.scaleX = scale;
    this.skeleton.scaleY = scale;
    this.skeleton.x = worldX - boundsCenterX * scale;
    this.skeleton.y = worldY - boundsCenterY * scale;
  }
}

class SpineStage {
  constructor(canvasEl) {
    this.canvasEl = canvasEl;
    this.baseInstances = [];
    this.overlayInstances = []; // always drawn on top of base (popups)
    this.baseDimmed = false; // see setBaseDim below

    this.spineCanvas = new spine.SpineCanvas(canvasEl, {
      pathPrefix: '',
      webglConfig: { alpha: true },
      app: {
        update: (canvas, delta) => {
          for (const inst of this.baseInstances) inst.update(delta, canvasEl);
          for (const inst of this.overlayInstances) inst.update(delta, canvasEl);
        },
        render: (canvas) => {
          const renderer = canvas.renderer;
          renderer.resize(spine.ResizeMode.Expand);
          canvas.clear(0, 0, 0, 0);
          renderer.begin();
          for (const inst of this.baseInstances) renderer.drawSkeleton(inst.skeleton, inst.resource.premultipliedAlpha);
          for (const inst of this.overlayInstances) renderer.drawSkeleton(inst.skeleton, inst.resource.premultipliedAlpha);
          renderer.end();
        },
      },
    });
    this.assetManager = this.spineCanvas.assetManager;
  }

  addBase(instance) {
    if (!this.baseInstances.includes(instance)) {
      this.baseInstances.push(instance);
      this._applyBaseDim(instance);
    }
  }
  // Draw order = array order (earlier = drawn first = appears behind later
  // entries). Base instances that must stay visually behind everything else
  // added afterwards (e.g. an ambient background piece that should sit
  // behind the character even across repeated add/remove churn from mode
  // switches — plain addBase's push-to-end would eventually put it back on
  // top) should use this instead of addBase.
  addBaseBehindAll(instance) {
    if (this.baseInstances.includes(instance)) return;
    this.baseInstances.unshift(instance);
    this._applyBaseDim(instance);
  }
  removeBase(instance) {
    const i = this.baseInstances.indexOf(instance);
    if (i >= 0) this.baseInstances.splice(i, 1);
  }
  addOverlay(instance) {
    if (!this.overlayInstances.includes(instance)) this.overlayInstances.push(instance);
  }
  removeOverlay(instance) {
    const i = this.overlayInstances.indexOf(instance);
    if (i >= 0) this.overlayInstances.splice(i, 1);
  }

  _applyBaseDim(instance) {
    const c = this.baseDimmed ? 0.25 : 1;
    instance.skeleton.color.set(c, c, c, 1);
  }

  // Base and overlay instances share one WebGL canvas, so a DOM dim overlay
  // (#screenDim) can only ever sit *outside* it — above everything (hiding
  // the popup too) or below everything (leaving base content, e.g. the
  // idle character and any looping win symbols, showing through). The
  // base<->bonus mode transition wants the popup bright but everything else
  // dark, so that split is done here instead, by tinting base instances'
  // own skeleton color — applied immediately to whatever's on stage now,
  // and to anything added while still dimmed (see _applyBaseDim above).
  setBaseDim(active) {
    this.baseDimmed = active;
    for (const inst of this.baseInstances) this._applyBaseDim(inst);
  }
}

window.SpineEngine = { SpineResource, SpineInstance, SpineStage };
