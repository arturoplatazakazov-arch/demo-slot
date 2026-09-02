// Caesar's Fortune — central sound manager, скопирован с ../big-catch/sound.js.
// Своего пака у римской темы пока нет, поэтому звук одолжен — но НЕ у
// Wild Western Story, чья математика лежит в основе игры: продукт отдельно
// просил не дублировать её фоновую музыку. Донор — Party of Goods
// (античная тема, ближайшая по настроению): оттуда и музыка обоих уровней, и
// тиры выигрышей, и тематический старт спина. Единственное исключение —
// звук роста вайлда: у Party of Goods такой механики нет, поэтому он взят у
// East Discovery, откуда родом сам расширяющийся вайлд.
//
// Приедет римский пак — заменить GAME на 'sound/caesars-fortune/' и разложить
// файлы под теми же именами (см. front/sound/README.md).
//
// Assets split two ways (see front/sound/README.md): repeating SFX shared by
// every game live in sound/common/.
const COMMON = 'sound/common/';
const GAME = 'sound/party-of-goods/';
const WILD = 'sound/east-discovery/';

const SOUND_FILES = {
  // одолжено у Party of Goods
  smallWin: GAME + 'WIN_Small1.mp3',
  bigWin: GAME + 'WIN_Big.mp3',
  megaWin: GAME + 'WIN_Mega.mp3',
  epicWin: GAME + 'WIN_Epic.mp3',
  scatterWin: GAME + 'SCATTER_win.mp3',
  bonusTotalWin: GAME + 'BONUS_SPINS_TOTAL_WIN.wav', // итог раунда фриспинов
  spinStart: GAME + 'SPIN_Start.mp3',                // тематический, вместо общего reel-start
  // рост вайлда — у донора такой механики нет, берём у East Discovery
  wildGrow: WILD + 'WILD_Scale.wav',
  // ВНИМАНИЕ: ключа `wildWin` тут нет намеренно. Длинной подложки под выигрыш
  // вайлда ни в одном паке нет, а мёртвый путь стоил бы 404 на каждой
  // загрузке страницы. playSfx на неизвестном ключе просто ничего не делает —
  // поведение то же. Вернуть, когда приедет файл.
  // общие / повторяющиеся (уже лежат в sound/common/)
  click: COMMON + 'Click_UI.mp3',
  reelStop: COMMON + 'Reel_stop_slot.mp3',
  finalReelStop: COMMON + 'REELS_final_stop.mp3',
  anticipation: COMMON + 'REELS_anticipation.mp3',
  popupOpen: COMMON + 'Popup-open.mp3',
  popupClose: COMMON + 'Popup-close.mp3',
};

// Одна дорожка на уровень: слоя окружения у донора нет (у Wild Western Story
// он был, но её пак сюда не берём).
const MUSIC_FILES = {
  base: { music: GAME + 'BG_Base.mp3' },
  bonus: { music: GAME + 'BG_Bonus.mp3' },
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
