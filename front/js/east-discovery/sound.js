// East Discovery — central sound manager, same mechanics as ../sound.js
// (overlappable one-shot SFX, crossfading looped music unlocked on first
// user gesture) — only SOUND_FILES/MUSIC_FILES differ. Assets split two ways
// (see front/sound/README.md): repeating SFX shared by every game live once
// in sound/common/; this theme's win tiers, music and unique SFX live in
// sound/east-discovery/.
//
// wildGrow/wildWin: the wild's own pair (WILD_Scale.wav, short ~1.1s vs
// WILD_Scale_wind.wav, ~10.5s) — the short one fits the quick reel-height
// grow beat (revealExpandedWild's big_landing), the long one fits sitting
// under a win celebration loop (playBigWildWinIfWinning's big_win).
const COMMON = 'sound/common/';
const GAME = 'sound/east-discovery/';

const SOUND_FILES = {
  // unique to this game
  smallWin: GAME + 'WIN_Small.wav',
  bigWin: GAME + 'WIN_Big.wav',
  megaWin: GAME + 'WIN_Mega.wav',
  epicWin: GAME + 'WIN_Epic.wav',
  scatterWin: GAME + 'SCATTER_win.mp3',
  wildGrow: GAME + 'WILD_Scale.wav',
  wildWin: GAME + 'WILD_Scale_wind.wav',
  coinLand: GAME + 'HOLD&WIN_Coin.wav',
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
  audio.play().catch(() => {}); // autoplay-blocked / missing file — fine to ignore
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
