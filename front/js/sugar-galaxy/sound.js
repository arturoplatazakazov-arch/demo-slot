// Sugar Galaxy — central sound manager, same mechanics as the other games'
// sound.js (overlappable one-shot SFX, crossfading looped music unlocked on
// first user gesture; `new Audio(src).play()` fails soft when a file is
// missing). Assets split two ways (see front/sound/README.md): repeating SFX
// shared by every game live in sound/common/; this cascade theme's win tiers,
// music, spin-start, element-drop, win-boom and bomb SFX are delivered. This
// game overrides the shared spin-start with its own themed SPIN_Start.mp3.
// Only the scatter-win SFX isn't delivered yet, so that GAME path still 404s
// harmlessly until it lands.
const COMMON = 'sound/common/';
const GAME = 'sound/sugar-galaxy/';

const SOUND_FILES = {
  // unique to this game — delivered
  smallWin: GAME + 'WIN_Small.mp3', // every winning combination (see slot.js celebrateStep)
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  winBoom: GAME + 'WIN_Boom.mp3', // element-clear explosion after a combination
  cascadeDrop: GAME + 'Element_drop.mp3', // element lands on its cell after collapse/refill
  bombExplode: GAME + 'bomb-explode.mp3', // fires 0.9s after the bomb animation starts
  spinStart: GAME + 'SPIN_Start.mp3', // themed spin-start (overrides the shared one)
  // unique to this game — not delivered yet (404 harmless until it lands)
  scatterWin: GAME + 'SCATTER_win.mp3',
  // shared / repeating (already present in sound/common/)
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
