// Neon Reels — central sound manager, same mechanics as the other games'
// sound.js (overlappable one-shot SFX + crossfading looped music unlocked on
// the first user gesture). Assets split two ways (see front/sound/README.md):
// repeating SFX shared by every game live in sound/common/; this theme's win
// tiers and background music are delivered (all .mp3). The coin-land SFX
// isn't delivered yet, so that GAME path still 404s harmlessly until it lands.
const COMMON = 'sound/common/';
const GAME = 'sound/neon-reels/';

const SOUND_FILES = {
  // unique to this game — delivered
  smallWin: GAME + 'WIN_Small.mp3',
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  // unique to this game — not delivered yet (404 harmless until it lands)
  coinLand: GAME + 'COIN_land.wav',
  // shared / repeating (already present in sound/common/)
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

// Preload every SFX up front: creating a fresh Audio at play time means the
// fetch/decode starts when the sound should already be audible, which on
// mobile webviews (Telegram Mini App) makes every effect land late and adds
// main-thread hiccups mid-spin. One element per SFX is fetched once at page
// load (~300KB total); overlapping plays clone the element, hitting the HTTP
// cache instead of the network.
const sfxCache = {};
for (const [name, src] of Object.entries(SOUND_FILES)) {
  const audio = new Audio(src);
  audio.preload = 'auto';
  sfxCache[name] = audio;
}

function playSfx(name) {
  if (muted) return;
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
  setMuted,
  toggleMuted,
  get muted() {
    return muted;
  },
};
window.Sound = Sound;

updateSoundIcon();
