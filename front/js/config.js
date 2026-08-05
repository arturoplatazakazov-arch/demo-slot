// Per-deployment runtime config for the static frontend.
// This is the ONE file you edit when publishing to GitHub Pages.
//
// Local dev: leave apiBaseUrl empty — api.js auto-targets the local backend
//   at http://127.0.0.1:8000/api/v1 when the page is opened on localhost.
// Production (GitHub Pages): set apiBaseUrl to your Railway API origin, e.g.
//   apiBaseUrl: 'https://demo-slot-production.up.railway.app/api/v1'
//
// A '?api=<url>' query string on the page URL overrides this at runtime,
// which is handy for pointing a local page at a staging backend.
window.SLOT_CONFIG = {
  apiBaseUrl: 'https://api-production-ea3c.up.railway.app/api/v1',
};

// Dev-only UI (mode toggle, forced Big/Epic/Mega Win popups, feature-buy
// shortcuts) is shown on localhost and hidden on any deployed origin, so the
// embedded/public build looks clean. Elements are only hidden (not removed),
// so the handlers app.js/slot.js bind to them stay intact.
// Override explicitly with ?dev=1 (force show) or ?dev=0 (force hide).
(function hideDevUiOnDeployedOrigins() {
  const forced = new URLSearchParams(location.search).get('dev');
  const host = location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1' || host === '';
  const showDev = forced === '1' ? true : forced === '0' ? false : isLocal;
  window.SLOT_CONFIG.showDevPanels = showDev;
  if (!showDev) {
    document.querySelectorAll('.dev-panel').forEach((el) => {
      // Inline !important beats the .dev-panel { display: flex } class rule;
      // the plain `hidden` attribute alone would be overridden by it.
      el.hidden = true;
      el.style.setProperty('display', 'none', 'important');
    });
  }
})();
