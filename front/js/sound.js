// Central sound manager: one-shot SFX (overlappable — reels stop with a
// natural stagger, each needs its own independent playback) plus looping
// background music that crossfades between base/bonus on mode switch.
// Browsers block audio before a user gesture, so music is queued and only
// actually starts once the player's first click/keypress unlocks it.

// Sound assets split two ways (see front/sound/README.md):
//   COMMON — repeating SFX shared by every game, one copy in sound/common/
//   GAME   — this game's unique win tiers + music, in sound/amys-fruit-farm/
const COMMON = 'sound/common/';
const GAME = 'sound/amys-fruit-farm/';

const SOUND_FILES = {
  // unique to this game
  smallWin: GAME + 'WIN_Small.mp3',
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  // shared / repeating
  click: COMMON + 'Click_UI.mp3',
  spinStart: COMMON + 'reel-start.mp3',
  reelStop: COMMON + 'Reel_stop_slot.mp3',
  finalReelStop: COMMON + 'REELS_final_stop.mp3',
  anticipation: COMMON + 'REELS_anticipation.mp3',
  popupOpen: COMMON + 'Popup-open.mp3',
  popupClose: COMMON + 'Popup-close.mp3',
};

const MUSIC_FILES = {
  base: GAME + 'BG_Base.mp3',
  bonus: GAME + 'BG_Bonus.mp3',
};

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.35;

let muted = localStorage.getItem('slot.muted') === '1';
let currentMusic = null;
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

// Music tracks are ~2MB each, so they'd compete with the game art if fetched
// immediately; elements are created up front but only start buffering after
// window 'load'. By the time the first gesture unlocks playback the track is
// (mostly) buffered, so the background music starts on time instead of
// trailing the game by however long the fetch takes.
const musicCache = {};
for (const [key, src] of Object.entries(MUSIC_FILES)) {
  const audio = new Audio();
  audio.preload = 'none';
  audio.src = src;
  audio.loop = true;
  musicCache[key] = audio;
}
window.addEventListener('load', () => {
  for (const audio of Object.values(musicCache)) {
    audio.preload = 'auto';
    audio.load();
  }
});

function playMusic(key) {
  pendingMusicKey = key;
  if (!musicUnlocked || currentMusicKey === key) return;
  if (currentMusic) currentMusic.pause();

  const audio = musicCache[key];
  if (!audio) return;
  audio.volume = muted ? 0 : MUSIC_VOLUME;
  if (audio.readyState > 0) audio.currentTime = 0;
  audio.play().catch(() => {});
  currentMusic = audio;
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
  if (currentMusic) currentMusic.volume = muted ? 0 : MUSIC_VOLUME;
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
