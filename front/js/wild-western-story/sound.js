// Wild Western Story — central sound manager, same mechanics as the other
// games' sound.js (overlappable one-shot SFX, crossfading looped music
// unlocked on first user gesture). Assets split two ways (see
// front/sound/README.md): repeating SFX shared by every game live in
// sound/common/; this theme's win tiers, background music and the wild-scale
// SFX are delivered (all .mp3). Each background level plays TWO looped layers
// at once — the music track plus an environment/atmosphere bed under it (see
// MUSIC_FILES). The scatter win and the longer wild-win bed aren't delivered
// yet, so those GAME paths still 404 harmlessly until the files land.
const COMMON = 'sound/common/';
const GAME = 'sound/wild-western-story/';

const SOUND_FILES = {
  // unique to this game — delivered
  smallWin: GAME + 'WIN_Small.mp3',
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  wildGrow: GAME + 'WILD_Scale.mp3', // wild expand/scale beat
  // unique to this game — not delivered yet (404 harmless until they land)
  scatterWin: GAME + 'SCATTER_win.mp3',
  wildWin: GAME + 'WILD_Scale_wind.mp3', // longer bed under a wild win
  // shared / repeating (already present in sound/common/)
  click: COMMON + 'Click_UI.mp3',
  spinStart: COMMON + 'reel-start.mp3',
  reelStop: COMMON + 'Reel_stop_slot.mp3',
  finalReelStop: COMMON + 'REELS_final_stop.mp3',
  anticipation: COMMON + 'REELS_anticipation.mp3',
  popupOpen: COMMON + 'Popup-open.mp3',
  popupClose: COMMON + 'Popup-close.mp3',
};

// Each background key plays two looped layers together: `music` is the main
// background track, `env` is the environment/atmosphere bed sitting under it.
// Drop `env` (or set it to null) to fall back to a single-track background.
const MUSIC_FILES = {
  base: { music: GAME + 'BG_Base.mp3', env: GAME + 'BG_Base_environment.mp3' },
  bonus: { music: GAME + 'BG_Bonus.mp3', env: GAME + 'BG_Bonus_environment.mp3' },
};

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.35; // main background track
const ENV_VOLUME = 0.25; // environment/atmosphere layer — sits under the music

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

function startLayer(src, vol) {
  const audio = new Audio(src);
  audio.loop = true;
  audio.volume = muted ? 0 : vol;
  audio.play().catch(() => {}); // autoplay-blocked / missing file — fine to ignore
  return { audio, vol };
}

function playMusic(key) {
  pendingMusicKey = key;
  if (!musicUnlocked || currentMusicKey === key) return;
  for (const layer of currentLayers) layer.audio.pause();
  currentLayers = [];

  const set = MUSIC_FILES[key];
  if (!set) return;
  currentLayers.push(startLayer(set.music, MUSIC_VOLUME));
  if (set.env) currentLayers.push(startLayer(set.env, ENV_VOLUME));
  currentMusicKey = key;
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
  for (const layer of currentLayers) layer.audio.volume = muted ? 0 : layer.vol;
  updateSoundIcon();
}

function toggleMuted() {
  setMuted(!muted);
}

window.addEventListener('pointerdown', unlockMusic, { once: true });
window.addEventListener('keydown', unlockMusic, { once: true });

const Sound = {
  playSfx,
  playMusic,
  preloadPromises: sfxLoadPromises,
  setMuted,
  toggleMuted,
  get muted() {
    return muted;
  },
};
window.Sound = Sound;

updateSoundIcon();
