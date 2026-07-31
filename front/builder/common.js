// Shared fetch client + status-message helper for the slot-builder wizard's
// pages (new.js, assets.js, grid.js, layout.js, preview.js) — was five
// near-identical copies of the same three functions, drifting slightly from
// each other (e.g. error-message wording). Loaded via a plain <script> tag
// before each stage's own script, same no-build-step convention as the rest
// of front/.
//
// API_BASE is derived from the page's own hostname/protocol rather than
// hardcoded to http://127.0.0.1:8000 — a hardcoded address only works when
// the builder UI is opened from localhost; deriving it means the same file
// works unmodified wherever front/ is actually served from, as long as the
// API listens on port 8000 of that same host (front/ and the API are
// commonly two different ports of one host, not two different hosts —
// see docker-compose.yml / run_games.sh).
const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api/admin/builder`;

async function handleResponse(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = (data && data.detail) || `HTTP ${response.status}`;
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return data;
}

async function apiRequest(method, path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse(response);
}

async function apiUpload(path, formData) {
  const response = await fetch(`${API_BASE}${path}`, { method: 'POST', body: formData });
  return handleResponse(response);
}

function setStatus(elId, message, kind) {
  const el = document.getElementById(elId);
  el.textContent = message;
  el.classList.remove('is-error', 'is-ok');
  if (kind) el.classList.add(kind);
}
