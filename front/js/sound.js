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

function playSfx(name) {
  if (muted) return;
  const src = SOUND_FILES[name];
  if (!src) return;
  const audio = new Audio(src);
  audio.volume = SFX_VOLUME;
  audio.play().catch(() => {}); // autoplay-blocked / interrupted — fine to ignore
}

function playMusic(key) {
  pendingMusicKey = key;
  if (!musicUnlocked || currentMusicKey === key) return;
  if (currentMusic) currentMusic.pause();

  const src = MUSIC_FILES[key];
  if (!src) return;
  const audio = new Audio(src);
  audio.loop = true;
  audio.volume = muted ? 0 : MUSIC_VOLUME;
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
