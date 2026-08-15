// Reads a slot-builder manifest (GET /api/admin/builder/games/{slug}) and
// renders one screen (device x base/bonus) as absolutely-positioned DOM
// elements, exactly like front/builder/preview.js's read-only renderer —
// same coordinate system (x/y is each object's CENTER point, w/h is its
// rendered size), same reel_block cell-grid construction. Extended here to
// also expose live hooks (reel cells to drop symbol art into, the
// buy-bonus/free-spins-counter/multiplier role elements) so js/play/engine.js
// can wire real spin results onto it instead of it being read-only.

const NATIVE_SIZES = {
  desktop: { w: 1932, h: 940 },
  mobile: { w: 780, h: 1416 },
};
const DEFAULT_GAP = 10;

// The admin builder API lives under /api/admin/builder, not /api/v1 — derive
// its base the same way js/api.js resolves its own (query override / config.js
// override / localhost default) rather than hardcoding a second convention.
function builderApiBase() {
  return API_BASE_URL.replace(/\/api\/v1$/, '/api/admin/builder');
}

async function fetchManifest(slug) {
  const response = await fetch(`${builderApiBase()}/games/${encodeURIComponent(slug)}`);
  if (!response.ok) throw new Error(`could not load slot "${slug}" (HTTP ${response.status})`);
  return response.json();
}

function manifestImgUrl(slug, file) {
  return `img/${slug}/${file}`;
}

function pickDevice() {
  // innerWidth can legitimately read 0 before the very first layout pass
  // (seen in at least one automated embedding) — treat that as "not known
  // yet" and default to desktop rather than misreading it as a narrow phone.
  const w = window.innerWidth;
  return w > 0 && w < 900 ? 'mobile' : 'desktop';
}

function gridSize(manifest) {
  if (manifest.grid && manifest.grid.reels && manifest.grid.rows) {
    return { reels: manifest.grid.reels, rows: manifest.grid.rows };
  }
  return { reels: 5, rows: 3 };
}

// Renders `screen` (base/bonus) for `device` into #playScreen, scaled to
// fit #playFrame. Returns hooks the spin engine drives:
//   reelCells: rows x reels 2D array of the reel_block's cell <div>s
//   buyBonusEl / freeSpinsCounterEl / freeSpinsCounterText / multiplierEl / multiplierText
function renderManifestScreen(manifest, slug, device, screen) {
  const native = NATIVE_SIZES[device];
  const frame = document.getElementById('playFrame');
  const screenEl = document.getElementById('playScreen');
  screenEl.innerHTML = '';

  const maxW = Math.min(frame.parentElement.clientWidth, native.w);
  // The bottom control surface is the fixed V3 bar (js/ui-bar-v3.js); reserve
  // its height so the stage isn't hidden behind it. Falls back to 190 if the bar
  // isn't in the DOM yet.
  const bar = document.getElementById('v3Bar');
  const barH = bar ? bar.offsetHeight : 190;
  const maxH = window.innerHeight - barH - 140;
  const scale = Math.min(maxW / native.w, maxH / native.h, 1);

  frame.style.width = `${native.w * scale}px`;
  frame.style.height = `${native.h * scale}px`;
  screenEl.style.width = `${native.w}px`;
  screenEl.style.height = `${native.h}px`;
  screenEl.style.transform = `scale(${scale})`;

  const hooks = {
    reelCells: null, buyBonusEl: null,
    freeSpinsCounterEl: null, freeSpinsCounterText: null,
    multiplierEl: null, multiplierText: null,
    // {el, folder, animationName} when the background is a Spine animation
    // instead of an image — js/play/engine.js owns the actual SpineStage/
    // SpineInstance (rendering is a separate WebGL canvas), this just hands
    // back the anchor div it should position the skeleton against.
    bgSpineAnchor: null,
    // Same idea, but a list — decor.spine objects are unlimited overlay
    // layers on top of the background, not a single exclusive slot.
    spineObjectAnchors: [],
  };

  const layoutForDevice = manifest.layouts[device];
  const bg = layoutForDevice.backgrounds[screen];
  if (bg && bg.animation_ref) {
    const anim = manifest.assets.animations.find((a) => a.id === bg.animation_ref);
    if (anim) {
      const bgAnchor = document.createElement('div');
      bgAnchor.className = 'play-object';
      bgAnchor.style.left = `${bg.x - bg.w / 2}px`;
      bgAnchor.style.top = `${bg.y - bg.h / 2}px`;
      bgAnchor.style.width = `${bg.w}px`;
      bgAnchor.style.height = `${bg.h}px`;
      bgAnchor.style.zIndex = 0;
      screenEl.appendChild(bgAnchor);
      hooks.bgSpineAnchor = { el: bgAnchor, folder: anim.folder, animationName: bg.animation_name };
    }
  } else if (bg) {
    const bgAsset = manifest.assets.images.find((i) => i.id === bg.asset_id);
    if (bgAsset) {
      const bgEl = document.createElement('img');
      bgEl.className = 'play-object';
      bgEl.src = manifestImgUrl(slug, bgAsset.file);
      bgEl.style.left = `${bg.x - bg.w / 2}px`;
      bgEl.style.top = `${bg.y - bg.h / 2}px`;
      bgEl.style.width = `${bg.w}px`;
      bgEl.style.height = `${bg.h}px`;
      bgEl.style.zIndex = 0;
      screenEl.appendChild(bgEl);
    }
  }

  const objects = [...(layoutForDevice.screens[screen] || [])].sort((a, b) => a.z_index - b.z_index);
  objects.forEach((obj, i) => {
    let el;
    if (obj.type === 'system.reel_block') {
      el = document.createElement('div');
      el.className = 'play-object play-object--reelblock';
      const { reels, rows } = gridSize(manifest);
      const cellW = obj.cell_w ?? Math.max(10, (obj.w - DEFAULT_GAP * (reels - 1)) / reels);
      const cellH = obj.cell_h ?? Math.max(10, (obj.h - DEFAULT_GAP * (rows - 1)) / rows);
      const gapX = obj.gap_x ?? DEFAULT_GAP;
      const gapY = obj.gap_y ?? DEFAULT_GAP;
      const cells = [];
      for (let r = 0; r < rows; r++) {
        const rowCells = [];
        for (let c = 0; c < reels; c++) {
          const cell = document.createElement('div');
          cell.className = 'play-cell';
          cell.style.left = `${c * (cellW + gapX)}px`;
          cell.style.top = `${r * (cellH + gapY)}px`;
          cell.style.width = `${cellW}px`;
          cell.style.height = `${cellH}px`;
          el.appendChild(cell);
          rowCells.push(cell);
        }
        cells.push(rowCells);
      }
      hooks.reelCells = cells;
    } else if (obj.animation_ref) {
      const anim = manifest.assets.animations.find((a) => a.id === obj.animation_ref);
      if (!anim) return;
      el = document.createElement('div');
      el.className = 'play-object';
    } else if (obj.image_ref) {
      const asset = manifest.assets.images.find((img) => img.id === obj.image_ref);
      if (!asset) return;
      el = document.createElement('img');
      el.className = 'play-object';
      el.src = manifestImgUrl(slug, asset.file);
      if (obj.role === 'buy_bonus') {
        el.classList.add('play-object--interactive');
        hooks.buyBonusEl = el;
      }
    } else {
      return;
    }

    el.style.left = `${obj.x - obj.w / 2}px`;
    el.style.top = `${obj.y - obj.h / 2}px`;
    el.style.width = `${obj.w}px`;
    el.style.height = `${obj.h}px`;
    el.style.zIndex = i + 1;
    screenEl.appendChild(el);

    if (obj.animation_ref) {
      const anim = manifest.assets.animations.find((a) => a.id === obj.animation_ref);
      hooks.spineObjectAnchors.push({ el, folder: anim.folder, animationName: obj.animation_name });
    }

    if (obj.role === 'free_spins_counter' || obj.role === 'multiplier') {
      const overlay = document.createElement('div');
      overlay.className = 'play-role-overlay';
      overlay.style.left = el.style.left;
      overlay.style.top = el.style.top;
      overlay.style.width = el.style.width;
      overlay.style.height = el.style.height;
      overlay.style.zIndex = i + 2;
      overlay.hidden = obj.role === 'multiplier';
      screenEl.appendChild(overlay);
      if (obj.role === 'free_spins_counter') {
        hooks.freeSpinsCounterEl = overlay;
        hooks.freeSpinsCounterText = overlay;
      } else {
        hooks.multiplierEl = overlay;
        hooks.multiplierText = overlay;
      }
    }
  });

  return hooks;
}
