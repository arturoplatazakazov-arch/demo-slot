// Telegram Mini App bootstrap, shared by every game page and the catalogs.
// Safe to include anywhere: outside Telegram the SDK reports platform
// 'unknown' with empty initData, and this file only sets
// window.IS_TELEGRAM = false and the "to catalog" target.
//
// The official SDK (https://telegram.org/js/telegram-web-app.js) must be
// loaded BEFORE this script — see the <script> block at the bottom of
// neon-reels.html for the include order.
//
// `?tg=1` on the page URL forces Telegram mode in a plain browser so the
// in-Telegram layout/visibility tweaks can be checked without a phone.
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const forced = new URLSearchParams(location.search).get('tg') === '1';
  const inTelegram = forced || (!!tg && (tg.initData !== '' || tg.platform !== 'unknown'));

  window.IS_TELEGRAM = inTelegram;

  // "To catalog" leads back to the catalog page the game was opened from
  // (games.html with its project tabs, or tg.html — each stores itself in
  // sessionStorage 'catalogHome', games.html keeps ?from=tg). Without one: tg.html inside
  // Telegram (the portfolio catalog: games only), else the hardcoded
  // games.html. Covers the top-left overlay button here and the V3 bar's /
  // play.html's home button via window.CATALOG_URL (see ui-bar-v3.js).
  let home = null;
  try { home = sessionStorage.getItem('catalogHome'); } catch { /* storage off */ }
  if (!home && inTelegram) home = 'tg.html';
  if (home) {
    window.CATALOG_URL = home;
    document.querySelectorAll('.to-catalog-btn').forEach((el) => {
      el.setAttribute('href', home);
    });
  }

  if (!inTelegram) return;

  document.documentElement.classList.add('in-telegram');

  if (!tg || forced && tg.platform === 'unknown') return; // browser test run

  // Every SDK call below talks to a live Telegram client; versions older than
  // the method's Bot API level throw, hence the guards/try.
  tg.ready();
  tg.expand();

  // A vertical swipe over the reels would drag the whole mini-app down and
  // collapse it on mobile clients (Bot API 7.7+).
  if (typeof tg.disableVerticalSwipes === 'function') tg.disableVerticalSwipes();

  // Match the Telegram chrome to the dark game pages.
  try {
    tg.setHeaderColor('#000000');
    tg.setBackgroundColor('#000000');
  } catch { /* Bot API < 6.1 */ }
})();
