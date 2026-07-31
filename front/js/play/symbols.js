// Resolves a spin's symbol codes into real uploaded art: GET
// /api/v1/config/{code}/symbols gives code -> Symbol.image_ref (a builder
// asset id), and the manifest's assets.images gives asset id -> file. Codes
// with no image_ref (or fewer symbol images were uploaded than the config
// has symbols — see app/api/admin/builder_config.py's generate_default_config)
// fall back to a plain placeholder block instead of a broken <img>.

async function loadSymbolArtMap(gameCode, manifest) {
  const artEntries = await apiGet(`/config/${encodeURIComponent(gameCode)}/symbols`);
  const codeToUrl = {};
  for (const entry of artEntries) {
    if (!entry.image_ref) continue;
    const asset = manifest.assets.images.find((img) => img.id === entry.image_ref);
    if (asset) codeToUrl[entry.code] = manifestImgUrl(gameCode, asset.file);
  }
  return codeToUrl;
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
