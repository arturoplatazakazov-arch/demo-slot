// Volt Coins V3 — central sound manager: overlapping one-shot SFX via
// WebAudio + looped music unlocked by the first gesture; a missing file fails
// soft. V3 plays the theme's own sound pack (sound/volt-coins/, ILL_1_VoltCoin
// from the sound designer, 2026-10-20).
const VC = 'sound/volt-coins/';

// примерка посадки монеты: ?coin=1..6 → sound/volt-coins/coin_try/ (2026-11-03)
const COIN_TRY = {
  1: 'coin_1_metal_tap', 2: 'coin_2_chip_clack', 3: 'coin_3_heavy_drop',
  4: 'coin_4_electric_drop', 5: 'coin_5_short_ting', 6: 'coin_6_soft_thud',
}[new URLSearchParams(location.search).get('coin')];

// примерка разряда под искру катушки: ?zap=1..6 → sound/volt-coins/zap_try/
const ZAP_TRY = {
  1: 'zap_1_snap_zap', 2: 'zap_2_tesla_arc', 3: 'zap_3_charge_release',
  4: 'zap_4_spark_shower', 5: 'zap_5_zap_sweep', 6: 'zap_6_thunder_strike',
}[new URLSearchParams(location.search).get('zap')];

const ANTIC_TRY = {
  1: 'antic_1_tempo', 2: 'antic_2_speedup', 3: 'antic_3_cut_middle', 4: 'antic_4_no_intro', 5: 'antic_5_tempo_trim',
}[new URLSearchParams(location.search).get('antic')];

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
  // на 1 с короче: выбран вариант 2 «ускорение» (= antic_try/antic_2_speedup, 2026-11-03);
  // ?antic=1..5 — примерка остальных (только локально)
  anticipation: ANTIC_TRY ? `${VC}antic_try/${ANTIC_TRY}.wav` : VC + 'REELS_Anticipation_short.wav',
  // symbols on a win line
  sym_seven: VC + 'SYMBOL_Seven.mp3',
  sym_bar: VC + 'SYMBOL_BAR.mp3',
  sym_bell: VC + 'SYMBOL_Bell.mp3',
  sym_diamond: VC + 'SYMBOL_Diamond.mp3',
  sym_ingot: VC + 'SYMBOL_Goldbar.mp3',
  sym_horseshoe: VC + 'SYMBOL_Horseshoe.mp3',
  sym_star: VC + 'SYMBOL_Star.mp3',
  sym_wild: VC + 'SYMBOL_Wild.mp3',
  // проще, без звона (scripts/volt_coins_v3_sfx.py; было SYMBOL_Coin_Landing.mp3)
  // выбран вариант 4 «электро-капля» (2026-11-03); ?coin=N — примерка остальных
  coinLand: COIN_TRY ? `${VC}coin_try/${COIN_TRY}.wav` : VC + 'SYMBOL_Coin_Landing_v3.wav',   // = coin_try/coin_4
  // жужжание электричества под искру катушки в простое (fx.js ambientGlow)
  // выбран разряд 2 «дуга Теслы», вдвое тише (2026-11-03); ?zap=N — примерка
  coilBuzz: ZAP_TRY ? `${VC}zap_try/${ZAP_TRY}.wav` : VC + 'SFX_CoilArc.wav',
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
const AMBIENCE_VOLUME = 0.22 / 3;   // искры фона в 3 раза тише (2026-11-03)

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

const playing = {};   // name -> Set({source, gain}) — звучащие сейчас

// Погасить звучащий эффект (30 мс), напр. искру катушки, когда началась
// антиципация или спин.
function stopSfx(name) {
  const live = playing[name];
  if (!live || !sfxCtx) return;
  const t = sfxCtx.currentTime;
  for (const { source, g } of live) {
    g.gain.setValueAtTime(g.gain.value, t);
    g.gain.linearRampToValueAtTime(0, t + 0.03);
    try { source.stop(t + 0.04); } catch (e) { /* уже остановлен */ }
  }
  live.clear();
}

function playSfx(name) {
  if (muted) return;
  if (sfxCtx && sfxBuffers[name]) {
    if (sfxCtx.state === 'suspended') sfxCtx.resume();
    const source = sfxCtx.createBufferSource();
    source.buffer = sfxBuffers[name];
    // свой гейн на каждый проигрыш — чтобы stopSfx мог его быстро погасить
    const g = sfxCtx.createGain();
    source.connect(g);
    g.connect(sfxGain);
    source.start();
    const live = (playing[name] = playing[name] || new Set());
    const item = { source, g };
    live.add(item);
    source.onended = () => live.delete(item);
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
  stopSfx,
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
