// Great Uniqorn — central sound manager (copied from Uniqorn Scandal): one-shot
// SFX through WebAudio, looping music unlocked on the first user gesture.
//
// The game's own pack lives in sound/great-uniqorn/: synthesized in code by
// scripts/great_uniqorn_audio.py, three takes of each sound, the product's
// picks copied here under these names (the rest stay in _audition/ for
// reference).
const GAME = 'sound/great-uniqorn/';

// 2026-11-11: the composer's pack ("Great Uniqorn SFX (Short)") replaced the
// synthesized placeholders (kept in _audition/synth_v1/). The pack has no reel
// stops or bonus enter/exit, so those stay synthesized (REEL_*, BONUS_*).
const SOUND_FILES = {
  // wins
  smallWin: GAME + 'WIN_Line.mp3',          // a line pays (no popup)
  bigWin: GAME + 'WIN_Bigwin.mp3',
  megaWin: GAME + 'WIN_Megawin.mp3',
  epicWin: GAME + 'WIN_Epicwin.mp3',
  bonusTotalWin: GAME + 'WIN_Bigwin.mp3',   // free-spins round total — no own take, BIG WIN's
  cashLoop: GAME + 'WIN_Cashloop.mp3',      // loop while a popup's amount counts up
  // scatters: the 1st/2nd/3rd burger to land in a spin, then the trigger
  scatter1: GAME + 'SCATTER_1.mp3',
  scatter2: GAME + 'SCATTER_2.mp3',
  scatter3: GAME + 'SCATTER_3.mp3',
  scatterWin: GAME + 'SCATTER_Win.mp3',
  wildLand: GAME + 'WILD_Land.mp3',         // a wild lands on a stopping reel
  wildGrow: GAME + 'WILD_Multiplier.mp3',   // wild -> multiplier reveal
  bonusEnter: GAME + 'BONUS_Enter.mp3',
  bonusExit: GAME + 'BONUS_Exit.mp3',
  // bonus buy: the sign opens the dialog, BUY confirms
  buyButton: GAME + 'BUY_Button.mp3',
  buyConfirm: GAME + 'BUY_Confirm.mp3',
  // ui
  click: GAME + 'UI_Click.mp3',
  popupOpen: GAME + 'UI_Popupopen.mp3',
  popupClose: GAME + 'UI_Popupclose.mp3',
  autospin: GAME + 'UI_Autospin.mp3',
  betPlus: GAME + 'UI_Betplus.mp3',
  betMinus: GAME + 'UI_Betminus.mp3',
  menu: GAME + 'UI_Menu.mp3',
  turbo: GAME + 'UI_Turbo.mp3',
  // reels: each of reels 1-4 stops on its own rising note (a little melody
  // per spin), the 5th lands on the resolving chord
  spinStart: GAME + 'REEL_SpinStart.mp3',
  reelStop1: GAME + 'REEL_Stop_1.mp3',
  reelStop2: GAME + 'REEL_Stop_2.mp3',
  reelStop3: GAME + 'REEL_Stop_3.mp3',
  reelStop4: GAME + 'REEL_Stop_4.mp3',
  finalReelStop: GAME + 'REEL_StopLast.mp3',
  anticipation: GAME + 'REEL_Anticipation.mp3',
};

// Each level = music + an ambience bed under it, both WebAudio buffer loops
// (an <audio loop> leaves a short gap at the mp3 boundary).
const MUSIC_FILES = {
  base: { music: GAME + 'MUSIC_Base.mp3', ambient: GAME + 'AMBIENT_Base.mp3' },
  bonus: { music: GAME + 'MUSIC_Bonus.mp3', ambient: GAME + 'AMBIENT_Bonus.mp3' },
};
const AMBIENT_VOLUME = 0.5; // relative to the music bus

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.35; // main background track

let muted = localStorage.getItem('slot.muted') === '1';
let currentLayers = []; // [{ audio, vol }] — music + environment played together
let currentMusicKey = null;
let musicUnlocked = false;
let pendingMusicKey = 'base';

// SFX go through WebAudio: <audio> elements have an inherent 100-300ms
// playback latency on mobile (both iOS Safari and the Telegram webview), so
// even fully-preloaded effects trailed the reel stops they were cued to.
// Buffers are fetched+decoded once at page load and each play is a
// BufferSource start — effectively instant. The preloaded-element path
// below stays as the fallback for browsers without AudioContext and for any
// buffer that hasn't finished decoding yet.
const AudioCtx = window.AudioContext || window.webkitAudioContext;
const sfxCtx = AudioCtx ? new AudioCtx() : null;
const sfxGain = sfxCtx ? sfxCtx.createGain() : null;
if (sfxGain) {
  sfxGain.gain.value = SFX_VOLUME;
  sfxGain.connect(sfxCtx.destination);
}
const sfxBuffers = {};
// Exposed via Sound.preloadPromises so the boot preloader can count each
// decode toward its progress bar; every promise resolves (errors swallowed),
// so awaiting them can't hang the loader on missing files.
const sfxLoadPromises = [];
if (sfxCtx) {
  for (const [name, src] of Object.entries(SOUND_FILES)) {
    sfxLoadPromises.push(
      fetch(src)
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()))
        .then((ab) => sfxCtx.decodeAudioData(ab))
        .then((buf) => { sfxBuffers[name] = buf; })
        .catch(() => {}), // missing file — fine to ignore
    );
  }
}

const sfxCache = {};
for (const [name, src] of Object.entries(SOUND_FILES)) {
  const audio = new Audio(src);
  audio.preload = sfxCtx ? 'none' : 'auto'; // fallback path only — don't double-fetch
  sfxCache[name] = audio;
}

function playSfx(name) {
  if (muted) return;
  if (sfxCtx && sfxBuffers[name]) {
    if (sfxCtx.state === 'suspended') sfxCtx.resume();
    const source = sfxCtx.createBufferSource();
    source.buffer = sfxBuffers[name];
    source.connect(sfxGain);
    source.start();
    return;
  }
  const cached = sfxCache[name];
  if (!cached) return;
  const audio = (cached.paused || cached.ended) ? cached : cached.cloneNode(true);
  audio.volume = SFX_VOLUME;
  if (audio.readyState > 0) audio.currentTime = 0;
  audio.play().catch(() => {}); // autoplay-blocked / missing file — fine to ignore
}

// --- music: WebAudio buffer loop, <audio loop> as the fallback ---------------
const musicGain = sfxCtx ? sfxCtx.createGain() : null;
if (musicGain) {
  musicGain.gain.value = muted ? 0 : MUSIC_VOLUME;
  musicGain.connect(sfxCtx.destination);
}
const musicBuffers = {};
function loadBuffer(src) {
  return fetch(src)
    .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()))
    .then((ab) => sfxCtx.decodeAudioData(ab))
    .catch(() => null);
}
// Resolves to { music, ambient } buffers (either may be null).
function loadMusicBuffer(key) {
  if (!sfxCtx || !MUSIC_FILES[key]) return Promise.resolve(null);
  if (!musicBuffers[key]) {
    const f = MUSIC_FILES[key];
    musicBuffers[key] = Promise.all([loadBuffer(f.music), f.ambient ? loadBuffer(f.ambient) : null])
      .then(([music, ambient]) => ({ music, ambient }));
  }
  return musicBuffers[key];
}

function startLayer(src, vol) {
  const audio = new Audio(src);
  audio.loop = true;
  audio.volume = muted ? 0 : vol;
  audio.play().catch(() => {}); // autoplay-blocked / missing file — fine to ignore
  return { audio, vol };
}

function stopLayers() {
  for (const layer of currentLayers) {
    if (layer.audio) layer.audio.pause();
    if (layer.node) { try { layer.node.stop(); } catch (e) { /* already stopped */ } }
  }
  currentLayers = [];
}

function playMusic(key) {
  pendingMusicKey = key;
  if (!musicUnlocked || currentMusicKey === key) return;
  stopLayers();
  currentMusicKey = key;
  const files = MUSIC_FILES[key];
  if (!files) return;
  const fallback = () => {
    currentLayers.push(startLayer(files.music, MUSIC_VOLUME));
    if (files.ambient) currentLayers.push(startLayer(files.ambient, MUSIC_VOLUME * AMBIENT_VOLUME));
  };
  if (!sfxCtx) { fallback(); return; }
  loadMusicBuffer(key).then((bufs) => {
    if (currentMusicKey !== key) return; // switched again while decoding
    if (!bufs || !bufs.music) { fallback(); return; }
    if (sfxCtx.state === 'suspended') sfxCtx.resume();
    const at = sfxCtx.currentTime + 0.05; // start both layers on the same tick
    for (const [buf, vol] of [[bufs.music, 1], [bufs.ambient, AMBIENT_VOLUME]]) {
      if (!buf) continue;
      const node = sfxCtx.createBufferSource();
      node.buffer = buf;
      node.loop = true;
      const g = sfxCtx.createGain();
      g.gain.value = vol;
      node.connect(g);
      g.connect(musicGain);
      node.start(at);
      currentLayers.push({ node, vol: MUSIC_VOLUME * vol });
    }
  });
}

// --- looping SFX (cash counter) -------------------------------------------------
// Returns a stop() — safe to call more than once.
function startLoop(name) {
  if (muted || !sfxCtx || !sfxBuffers[name]) return () => {};
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const node = sfxCtx.createBufferSource();
  node.buffer = sfxBuffers[name];
  node.loop = true;
  const g = sfxCtx.createGain();
  g.gain.value = 1;
  node.connect(g);
  g.connect(sfxGain);
  node.start();
  let stopped = false;
  return () => {
    if (stopped) return;
    stopped = true;
    const now = sfxCtx.currentTime;
    g.gain.setValueAtTime(1, now);
    g.gain.linearRampToValueAtTime(0, now + 0.08); // no click on the cut
    try { node.stop(now + 0.1); } catch (e) { /* ignore */ }
  };
}

function unlockMusic() {
  if (musicUnlocked) return;
  musicUnlocked = true;
  playMusic(pendingMusicKey);
}

function updateSoundIcon() {
  const btn = document.querySelector('[data-action="sound"]');
  if (btn) btn.classList.toggle('is-muted', muted);
}

function setMuted(next) {
  muted = next;
  localStorage.setItem('slot.muted', muted ? '1' : '0');
  for (const layer of currentLayers) if (layer.audio) layer.audio.volume = muted ? 0 : layer.vol;
  if (musicGain) musicGain.gain.value = muted ? 0 : MUSIC_VOLUME;
  updateSoundIcon();
}

function toggleMuted() {
  setMuted(!muted);
}

setTimeout(() => { loadMusicBuffer('base'); loadMusicBuffer('bonus'); }, 500);

window.addEventListener('pointerdown', unlockMusic, { once: true });
window.addEventListener('keydown', unlockMusic, { once: true });

const Sound = {
  playSfx,
  playMusic,
  startLoop,
  preloadPromises: sfxLoadPromises,
  setMuted,
  toggleMuted,
  get muted() {
    return muted;
  },
};
window.Sound = Sound;

updateSoundIcon();
