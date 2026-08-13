// Constructor v2 — thin backend client for the slot-builder API.
// Mirrors front/builder/common.js: API_BASE is derived from the page host so
// the same file works wherever front/ is served, as long as the API listens on
// :8000 of that host. The v2 pages live at /builder-v2/ and the game folders at
// /img/<slug>/, so front asset URLs are one level up (`../img/...`).
window.BuilderAPI = (function () {
  const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api/admin/builder`;

  async function handle(response) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const message = (data && data.detail) || `HTTP ${response.status}`;
      throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
    }
    return data;
  }

  async function request(method, path, body) {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    return handle(response);
  }

  async function upload(path, formData) {
    return handle(await fetch(`${API_BASE}${path}`, { method: 'POST', body: formData }));
  }

  return {
    base: API_BASE,
    request,
    upload,
    imgUrl: (slug, file) => `../img/${slug}/${file}`,
    soundUrl: (slug, file) => `../sound/${slug}/${file}`,
    animFileUrl: (slug, folder, file) => `../img/${slug}/${folder}/${file}`,
    folderPath: (slug) => `front/img/${slug}/`,
  };
})();
