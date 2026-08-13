// Dirty Money / MAFIA — central sound manager, same mechanics as the other
// games' sound.js (overlappable one-shot SFX, crossfading looped music unlocked
// on first user gesture; `new Audio(src).play()` fails soft when a file is
// missing). No sound pack was delivered for this theme — the slot-builder
// manifest ships zero sounds — so the GAME paths below 404 harmlessly until
// audio lands; the shared UI/reel cues in sound/common/ still play.
const COMMON = 'sound/common/';
const GAME = 'sound/dirty-money-mafia/';

const SOUND_FILES = {
  // unique to this game — not delivered yet (404 harmless until it lands)
  smallWin: GAME + 'WIN_Small.mp3',
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  wildGrow: GAME + 'WILD_Scale.mp3', // wild expanding over its reel
  wildWin: GAME + 'WILD_Win.mp3',
  wheelSpin: GAME + 'WHEEL_Spin.mp3', // Wheel of Fortune drum spinning up
  // shared / repeating (already present in sound/common/)
  spinStart: COMMON + 'reel-start.mp3',
  reelStop: COMMON + 'Reel_stop_slot.mp3',
  finalReelStop: COMMON + 'REELS_final_stop.mp3',
  anticipation: COMMON + 'REELS_anticipation.mp3',
  click: COMMON + 'Click_UI.mp3',
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

// Browsers block audio until the user interacts with the page — start the
// pending music track on the first gesture.
function unlockMusic() {
  if (musicUnlocked) return;
  musicUnlocked = true;
  const key = pendingMusicKey;
  currentMusicKey = null;
  playMusic(key);
}
window.addEventListener('pointerdown', unlockMusic, { once: true });
window.addEventListener('keydown', unlockMusic, { once: true });

function setMuted(value) {
  muted = value;
  localStorage.setItem('slot.muted', muted ? '1' : '0');
  if (currentMusic) currentMusic.volume = muted ? 0 : MUSIC_VOLUME;
  document.querySelectorAll('[data-action="sound"]').forEach((btn) => {
    btn.classList.toggle('is-muted', muted);
  });
}

function toggleMuted() {
  setMuted(!muted);
}

document.addEventListener('DOMContentLoaded', () => setMuted(muted));

window.Sound = { playSfx, playMusic, toggleMuted, setMuted, isMuted: () => muted };
