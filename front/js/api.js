// Thin fetch wrapper for the demo-slot backend (see app/api/v1, docs at
// {API_BASE_URL}/../docs). Kept separate from slot.js (rendering/animation)
// and app.js (UI bar + orchestration) so the network layer has one home.

// Resolve the backend base URL for whatever environment the page runs in,
// without a build step (this is a static site). Priority:
//   1. `?api=<url>` query string — ad-hoc override for testing.
//   2. window.SLOT_CONFIG.apiBaseUrl from js/config.js — the prod deploy value.
//   3. Local dev default — the backend on 127.0.0.1:8000.
function resolveApiBaseUrl() {
  const fromQuery = new URLSearchParams(location.search).get('api');
  if (fromQuery) return fromQuery.replace(/\/+$/, '');

  const configured = (window.SLOT_CONFIG && window.SLOT_CONFIG.apiBaseUrl || '').trim();
  if (configured) return configured.replace(/\/+$/, '');

  return 'http://127.0.0.1:8000/api/v1';
}

const API_BASE_URL = resolveApiBaseUrl();

// --- Access-code gate --------------------------------------------------------
// The public backend (Railway) requires a shared code (see app/api/security.py).
// We store what the user typed and send it on every request. The flow is purely
// reactive: on a 401 we (re)prompt. On localhost the backend has no code set, so
// it never returns 401 and this UI never appears — local dev is unaffected.
const ACCESS_CODE_KEY = 'slot_access_code';

function getAccessCode() {
  try { return localStorage.getItem(ACCESS_CODE_KEY) || ''; } catch { return ''; }
}
function setAccessCode(value) {
  try { localStorage.setItem(ACCESS_CODE_KEY, value); } catch { /* ignore */ }
}
function clearAccessCode() {
  try { localStorage.removeItem(ACCESS_CODE_KEY); } catch { /* ignore */ }
}

// Shown on 401. Resolves once the user submits a code; the caller then reloads
// so the game re-initialises with the code in place.
function promptAccessCode(message) {
  return new Promise((resolve) => {
    if (document.getElementById('access-gate')) return; // already open

    const overlay = document.createElement('div');
    overlay.id = 'access-gate';
    overlay.style.cssText =
      'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;' +
      'justify-content:center;background:rgba(8,10,20,0.92);' +
      'font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;';
    overlay.innerHTML =
      '<div style="width:min(90vw,340px);padding:28px 24px;border-radius:16px;' +
      'background:#161a2b;box-shadow:0 20px 60px rgba(0,0,0,.5);text-align:center;color:#eef;">' +
      '<div style="font-size:18px;font-weight:700;margin-bottom:6px;">Demo access</div>' +
      '<div id="access-gate-msg" style="font-size:13px;opacity:.7;margin-bottom:16px;">' +
      (message || 'Enter the access code to play the demo.') + '</div>' +
      '<input id="access-gate-input" type="password" inputmode="text" autocomplete="off" ' +
      'placeholder="Access code" style="width:100%;box-sizing:border-box;padding:12px 14px;' +
      'border-radius:10px;border:1px solid #333a55;background:#0e1120;color:#fff;font-size:16px;' +
      'outline:none;margin-bottom:14px;">' +
      '<button id="access-gate-submit" style="width:100%;padding:12px;border:0;border-radius:10px;' +
      'background:#4f7cff;color:#fff;font-size:15px;font-weight:700;cursor:pointer;">Enter</button>' +
      '</div>';
    document.body.appendChild(overlay);

    const input = overlay.querySelector('#access-gate-input');
    const submit = () => {
      const value = input.value.trim();
      if (!value) { input.focus(); return; }
      setAccessCode(value);
      overlay.remove();
      resolve(value);
    };
    overlay.querySelector('#access-gate-submit').addEventListener('click', submit);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
    input.focus();
  });
}

async function apiFetch(path, init) {
  const headers = Object.assign({}, init && init.headers);
  const code = getAccessCode();
  if (code) headers['X-Access-Code'] = code;

  const response = await fetch(`${API_BASE_URL}${path}`, Object.assign({}, init, { headers }));
  const data = await response.json().catch(() => null);

  if (response.status === 401) {
    // Wrong/missing code — forget it, ask again, then retry the same call once.
    clearAccessCode();
    await promptAccessCode(getAccessCode() ? 'Wrong code. Try again.' : undefined);
    return apiFetch(path, init);
  }

  if (!response.ok) {
    const message = (data && data.detail) || `${path} failed with HTTP ${response.status}`;
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return data;
}

function apiPost(path, body) {
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function apiGet(path) {
  return apiFetch(path, { method: 'GET' });
}

const Api = {
  startSession(gameId) {
    return apiPost('/session/start', { game_id: gameId });
  },
  spin(sessionId, betAmount) {
    return apiPost('/spin', { session_id: sessionId, bet_amount: betAmount });
  },
  buyFeature(sessionId, featureId, betAmount) {
    return apiPost('/feature/buy', { session_id: sessionId, feature_id: featureId, bet_amount: betAmount });
  },
  // Dev/test-only — see app/api/v1/spin.py's dev_force_hold_and_win.
  devForceHoldAndWin(sessionId, betAmount) {
    return apiPost('/dev/force-hold-and-win', { session_id: sessionId, bet_amount: betAmount });
  },
  getSessionState(sessionId) {
    return apiGet(`/session/${sessionId}/state`);
  },
};

window.Api = Api;
