// Lucky Miami 3 — central sound manager, те же механики, что у остальных игр
// (перекрывающиеся one-shot SFX через WebAudio + зацикленная музыка,
// разблокируемая первым жестом; отсутствующий файл падает мягко).
//
// Своего звукового пака у темы нет, поэтому играем чужие (тот же приём, что в
// uniqorn-shaolin-struggles/sound.js): тиры выигрыша — из neon-reels, UI и
// барабаны — общие. Из набора донора выпало всё, чего нет в этой игре:
// монета, итог раунда и джекпот.
const COMMON = 'sound/common/';
const NEON = 'sound/neon-reels/';

const SOUND_FILES = {
  smallWin: NEON + 'WIN_Small.mp3',
  bigWin: NEON + 'WIN_Big.mp3',
  megaWin: NEON + 'WIN_Mega.mp3',
  epicWin: NEON + 'WIN_Epic.mp3',
  click: COMMON + 'Click_UI.mp3',
  spinStart: COMMON + 'reel-start.mp3',
  reelStop: COMMON + 'Reel_stop_slot.mp3',
  finalReelStop: COMMON + 'REELS_final_stop.mp3',
  anticipation: COMMON + 'REELS_anticipation.mp3',
  popupOpen: COMMON + 'Popup-open.mp3',
  popupClose: COMMON + 'Popup-close.mp3',
};

// Product, this session: no music at all is better than another game's reused
// track — silent until this theme's own BG_Base is delivered.
const MUSIC_FILES = {};


const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.35;

let muted = localStorage.getItem('slot.muted') === '1';
let currentMusic = null;
let currentMusicKey = null;
let musicUnlocked = false;
let pendingMusicKey = 'base';

// SFX идут через WebAudio: у <audio> на мобилках собственная задержка
// 100-300ms, из-за которой даже предзагруженный эффект отставал от остановки
// барабана. Буферы декодируются один раз на загрузке, дальше каждый проигрыш —
// это старт BufferSource. Путь через элементы остаётся запасным.
const AudioCtx = window.AudioContext || window.webkitAudioContext;
const sfxCtx = AudioCtx ? new AudioCtx() : null;
const sfxGain = sfxCtx ? sfxCtx.createGain() : null;
if (sfxGain) {
  sfxGain.gain.value = SFX_VOLUME;
  sfxGain.connect(sfxCtx.destination);
}
const sfxBuffers = {};
// Отдаётся наружу как Sound.preloadPromises, чтобы прелоадер считал каждый
// декод в свой прогресс; каждый промис резолвится (ошибки глотаются), так что
// ожидание не может подвесить загрузчик на отсутствующем файле.
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
  audio.preload = sfxCtx ? 'none' : 'auto'; // запасной путь — не качать дважды
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

// Треки по ~2MB, поэтому элементы создаются сразу, а качать начинают только
// после window 'load' — иначе они конкурируют с артом игры.
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
  if (sfxCtx && sfxCtx.state === 'suspended') sfxCtx.resume();
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
  preloadPromises: sfxLoadPromises,
  get muted() {
    return muted;
  },
};
window.Sound = Sound;

updateSoundIcon();
