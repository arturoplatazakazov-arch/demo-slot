// Resolves a spin's symbol codes into real uploaded art: GET
// /api/v1/config/{code}/symbols gives code -> Symbol.image_ref (a builder
// asset id), and the manifest's assets.images gives asset id -> file. Codes
// with no image_ref (or fewer symbol images were uploaded than the config
// has symbols — see app/api/admin/builder_config.py's generate_default_config)
// fall back to a plain placeholder block instead of a broken <img>.

async function loadSymbolArtMap(gameCode, manifest) {
  const artEntries = await apiGet(`/config/${encodeURIComponent(gameCode)}/symbols`);
  const codeToUrl = {};
  const codeToFolder = {};
  for (const entry of artEntries) {
    if (!entry.image_ref) continue;
    const asset = manifest.assets.images.find((img) => img.id === entry.image_ref);
    if (!asset) continue;
    codeToUrl[entry.code] = manifestImgUrl(gameCode, asset.file);
    // Symbols registered from Spine folders use "<folder>/static.png"; the Spine
    // bundle (animation.json/.atlas/.png) lives in that same folder, so the play
    // engine can animate the symbol instead of showing the flat static tile.
    const slash = asset.file.indexOf('/');
    if (slash > 0 && /\/static\.(png|webp|jpe?g)$/i.test(asset.file)) {
      codeToFolder[entry.code] = asset.file.slice(0, slash);
    }
  }
  return { codeToUrl, codeToFolder };
}

function renderSymbolInCell(cell, code, codeToUrl) {
  cell.innerHTML = '';
  cell.classList.remove('is-winner');
  const url = codeToUrl[code];
  if (url) {
    const img = document.createElement('img');
    img.className = 'play-symbol-img';
    img.src = url;
    cell.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'play-symbol-placeholder';
    placeholder.textContent = code;
    cell.appendChild(placeholder);
  }
}
