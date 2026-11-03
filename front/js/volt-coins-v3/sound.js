// Volt Coins V3 — central sound manager: overlapping one-shot SFX via
// WebAudio + looped music unlocked by the first gesture; a missing file fails
// soft. V3 plays the theme's own sound pack (sound/volt-coins/, ILL_1_VoltCoin
// from the sound designer, 2026-10-20).
const VC = 'sound/volt-coins/';

const SOUND_FILES = {
  // wins
  smallWin: VC + 'WIN_Smallwin.mp3',
  bigWin: VC + 'WIN_Bigwin.mp3',
  megaWin: VC + 'WIN_Megawin.mp3',
  epicWin: VC + 'WIN_Epicwin.mp3',
  winPresent: VC + 'UI_Winpresent.mp3',
  // reels
  spinStart: VC + 'UI_Spin.mp3',
  reelStop: VC + 'REELS_Reelstop.mp3',
  finalReelStop: VC + 'REELS_Finalstop.mp3',
  anticipation: VC + 'REELS_Anticipation_Nearhit.mp3',
  // symbols on a win line
  sym_seven: VC + 'SYMBOL_Seven.mp3',
  sym_bar: VC + 'SYMBOL_BAR.mp3',
  sym_bell: VC + 'SYMBOL_Bell.mp3',
  sym_diamond: VC + 'SYMBOL_Diamond.mp3',
  sym_ingot: VC + 'SYMBOL_Goldbar.mp3',
  sym_horseshoe: VC + 'SYMBOL_Horseshoe.mp3',
  sym_star: VC + 'SYMBOL_Star.mp3',
  sym_wild: VC + 'SYMBOL_Wild.mp3',
  coinLand: VC + 'SYMBOL_Coin_Landing.mp3',
  // Hold & Win
  holdWinTrigger: VC + 'HOLDWIN_Trigger.mp3',
  baseToBonus: VC + 'TRANSITION_BaseToBonus.mp3',
  holdWinStart: VC + 'HOLDWIN_Start.mp3',
  respin: VC + 'HOLDWIN_Respin.mp3',
  newCoin: VC + 'HOLDWIN_NewCoin.mp3',
  coinLock: VC + 'HOLDWIN_CoinLock.mp3',
  jackpotCoin: VC + 'HOLDWIN_JackpotCoin.mp3',
  respinCount: VC + 'HOLDWIN_Respincount.mp3',
  resetCounter: VC + 'HOLDWIN_Resetcounter.mp3',
  gridComplete: VC + 'HOLDWIN_GridComplete.mp3',
  coinCollect: VC + 'HOLDWIN_CoinCollect.mp3',
  roundTotalWin: VC + 'HOLDWIN_End.mp3',
  bonusToBase: VC + 'TRANSITION_BonusToBase.mp3',
  // jackpots
  jackpotReveal: VC + 'TRANSITION_JackpotReveal.mp3',
  jackpot_mini: VC + 'JACKPOT_Mini.mp3',
  jackpot_minor: VC + 'JACKPOT_Minor.mp3',
  jackpot_major: VC + 'JACKPOT_Major.mp3',
  jackpot_grand: VC + 'JACKPOT_Grand.mp3',
  jackpotCounter: VC + 'UI_Jackpotcounter.mp3',
  // buy bonus
  buyBonus: VC + 'UI_Buybonus.mp3',
  buyConfirm: VC + 'BONUS_BuyConfirm.mp3',
  // UI
  click: VC + 'UI_Click.mp3',
  bet: VC + 'UI_Bet.mp3',
  autoplay: VC + 'UI_Autoplay.mp3',
  toggle: VC + 'UI_Toggle.mp3',
  error: VC + 'UI_Error.mp3',
  popupOpen: VC + 'UI_Popupopen.mp3',
  popupClose: VC + 'UI_Popupclose.mp3',
};

// Music and the room tone run as two loops: base / bonus music + ambience;
// a jackpot plays its own short track over the bonus.
const MUSIC_FILES = {
  base: VC + 'MUSIC_Basemusic.mp3',
  bonus: VC + 'MUSIC_Bonusmusic.mp3',
};
const AMBIENCE_FILES = {
  base: VC + 'AMBIENT_Baseambience.mp3',
  bonus: VC + 'AMBIENT_Bonusambience.mp3',
};
const AMBIENCE_VOLUME = 0.22;

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.35;

let muted = localStorage.getItem('vc3.muted') === '1';
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
const ambienceCache = {};
for (const [key, src] of Object.entries(AMBIENCE_FILES)) {
  const audio = new Audio();
  audio.preload = 'none';
  audio.src = src;
  audio.loop = true;
  ambienceCache[key] = audio;
}
let currentAmbience = null;
for (const [key, src] of Object.entries(MUSIC_FILES)) {
  const audio = new Audio();
  audio.preload = 'none';
  audio.src = src;
  audio.loop = true;
  musicCache[key] = audio;
}
window.addEventListener('load', () => {
  for (const audio of [...Object.values(musicCache), ...Object.values(ambienceCache)]) {
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
  if (currentAmbience) currentAmbience.pause();
  currentAmbience = ambienceCache[key] || null;
  if (currentAmbience) {
    currentAmbience.volume = muted ? 0 : AMBIENCE_VOLUME;
    if (currentAmbience.readyState > 0) currentAmbience.currentTime = 0;
    currentAmbience.play().catch(() => {});
  }
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
  localStorage.setItem('vc3.muted', muted ? '1' : '0');
  if (currentMusic) currentMusic.volume = muted ? 0 : MUSIC_VOLUME;
  if (currentAmbience) currentAmbience.volume = muted ? 0 : AMBIENCE_VOLUME;
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
