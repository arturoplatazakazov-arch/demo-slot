// Uniqorn Bad Santa — central sound manager, mechanically identical to every
// other game's sound.js (overlappable one-shot SFX through WebAudio, crossfading
// looped music unlocked on the first user gesture, missing files fail soft).
//
// No bespoke audio pack has been delivered for this theme yet, so it borrows
// Sugar Galaxy's cascade set — the cue list is identical (spin start, element
// drop, win tiers, the element-clear boom, the bomb blast), because the
// mechanic is identical. Point GAME at sound/uniqorn-bad-santa/ the moment a
// themed pack lands; nothing else here has to change.
const COMMON = 'sound/common/';
const GAME = 'sound/sugar-galaxy/';

const SOUND_FILES = {
  smallWin: GAME + 'WIN_Small.mp3', // every winning combination (see slot.js celebrateStep)
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  winBoom: GAME + 'WIN_Boom.mp3', // element-clear explosion after a combination
  cascadeDrop: GAME + 'Element_drop.mp3', // element lands after collapse/refill
  bombExplode: GAME + 'bomb-explode.mp3', // fires mid-way through the bomb wind-up
  spinStart: GAME + 'SPIN_Start.mp3',
  scatterWin: GAME + 'SCATTER_win.mp3', // not delivered anywhere yet — 404s harmlessly
  click: COMMON + 'Click_UI.mp3',
  popupOpen: COMMON + 'Popup-open.mp3',
  popupClose: COMMON + 'Popup-close.mp3',
};

const MUSIC_FILES = {
  base: GAME + 'BG_Base.mp3',
  bonus: GAME + 'BG_Bonus.wav',
};

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.35;

let muted = localStorage.getItem('slot.muted') === '1';
let currentMusic = null;
let currentMusicKey = null;
let musicUnlocked = false;
let pendingMusicKey = 'base';

// SFX go through WebAudio: <audio> elements have an inherent 100-300ms playback
// latency on mobile, so even fully-preloaded effects trail the beat they're cued
// to. Buffers are fetched+decoded once at page load and each play is a
// BufferSource start. The preloaded-element path below stays as the fallback for
// browsers without AudioContext and for any buffer still decoding.
const AudioCtx = window.AudioContext || window.webkitAudioContext;
const sfxCtx = AudioCtx ? new AudioCtx() : null;
const sfxGain = sfxCtx ? sfxCtx.createGain() : null;
if (sfxGain) {
  sfxGain.gain.value = SFX_VOLUME;
  sfxGain.connect(sfxCtx.destination);
}
const sfxBuffers = {};
// Exposed via Sound.preloadPromises so the boot preloader can count each decode
// toward its progress bar; every promise resolves (errors swallowed), so
// awaiting them can't hang the loader on a missing file.
const sfxLoadPromises = [];
if (sfxCtx) {
  for (const [name, src] of Object.entries(SOUND_FILES)) {
    sfxLoadPromises.push(
      fetch(src)
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()))
        .then((ab) => sfxCtx.decodeAudioData(ab))
        .then((buf) => { sfxBuffers[name] = buf; })
        .catch(() => {}),
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
  audio.play().catch(() => {});
}

// Music tracks are ~2MB each, so elements are created up front but only start
// buffering after window 'load' — by the time the first gesture unlocks
// playback the track is (mostly) buffered.
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
