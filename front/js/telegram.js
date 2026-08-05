// Telegram Mini App bootstrap, shared by every game page and (later) the
// tg.html portfolio catalog. Safe to include anywhere: outside Telegram the
// SDK reports platform 'unknown' with empty initData, and this file does
// nothing beyond setting window.IS_TELEGRAM = false.
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
  if (!inTelegram) return;

  document.documentElement.classList.add('in-telegram');

  // The public games.html catalog still links to the builder/anim-lab/admin
  // utility pages — none of that belongs in the portfolio mini-app, so the
  // escape hatch to it is hidden until tg.html (portfolio catalog) exists.
  document.querySelectorAll('.to-catalog-btn').forEach((el) => {
    el.style.setProperty('display', 'none', 'important');
  });

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
