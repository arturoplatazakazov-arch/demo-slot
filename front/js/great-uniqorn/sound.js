// Great Uniqorn — central sound manager (copied from Uniqorn Scandal): one-shot
// SFX through WebAudio, looping music unlocked on the first user gesture.
//
// The game's own pack lives in sound/great-uniqorn/: synthesized in code by
// scripts/great_uniqorn_audio.py, three takes of each sound, the product's
// picks copied here under these names (the rest stay in _audition/ for
// reference).
const GAME = 'sound/great-uniqorn/';

const SOUND_FILES = {
  // wins
  smallWin: GAME + 'WIN_Line.mp3',          // a line pays (no popup)
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  bonusTotalWin: GAME + 'WIN_Big.mp3',      // free-spins round total — no own take, BIG WIN's
  cashLoop: GAME + 'WIN_CashLoop.mp3',      // seamless loop while a popup's amount counts up
  // scatters: the 1st/2nd/3rd burger to land in a spin, then the trigger
  scatter1: GAME + 'SCATTER_1.mp3',
  scatter2: GAME + 'SCATTER_2.mp3',
  scatter3: GAME + 'SCATTER_3.mp3',
  scatterWin: GAME + 'SCATTER_Win.mp3',
  wildGrow: GAME + 'WILD_Multiplier.mp3',   // wild -> multiplier reveal
  bonusEnter: GAME + 'BONUS_Enter.mp3',
  bonusExit: GAME + 'BONUS_Exit.mp3',
  // ui
  click: GAME + 'UI_Click.mp3',
  popupOpen: GAME + 'UI_PopupOpen.mp3',
  popupClose: GAME + 'UI_PopupClose.mp3',
  autospin: GAME + 'UI_Autospin.mp3',
  betPlus: GAME + 'UI_BetPlus.mp3',
  betMinus: GAME + 'UI_BetMinus.mp3',
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

// One seamless loop per level (the files are rendered with the reverb tail
// folded back onto the start), played as a WebAudio buffer loop: an <audio
// loop> leaves a short gap at the mp3 boundary.
const MUSIC_FILES = {
  base: { music: GAME + 'BG_Base.mp3' },
  bonus: { music: GAME + 'BG_Bonus.mp3' },
};

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
function loadMusicBuffer(key) {
  if (!sfxCtx || !MUSIC_FILES[key]) return Promise.resolve(null);
  if (!musicBuffers[key]) {
    musicBuffers[key] = fetch(MUSIC_FILES[key].music)
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()))
      .then((ab) => sfxCtx.decodeAudioData(ab))
      .catch(() => null);
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
  if (!MUSIC_FILES[key]) return;
  if (!sfxCtx) {
    currentLayers.push(startLayer(MUSIC_FILES[key].music, MUSIC_VOLUME));
    return;
  }
  loadMusicBuffer(key).then((buf) => {
    if (currentMusicKey !== key) return; // switched again while decoding
    if (!buf) {
      currentLayers.push(startLayer(MUSIC_FILES[key].music, MUSIC_VOLUME));
      return;
    }
    if (sfxCtx.state === 'suspended') sfxCtx.resume();
    const node = sfxCtx.createBufferSource();
    node.buffer = buf;
    node.loop = true;
    node.connect(musicGain);
    node.start();
    currentLayers.push({ node, vol: MUSIC_VOLUME });
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
