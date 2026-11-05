// Neon Joker Spins — звук (+ пакет версии C: музыка, петля барабанов, свои UI). Механика как у tesla-spins/sound.js (one-shot SFX
// через WebAudio, мягкое падение на отсутствующем файле): тиры выигрыша и
// петли — из неонового пака neon-reels (тот же синт-поп), барабаны и UI —
// общие. Своё — СИНТЕЗ: «искра» Коллектора (короткий восходящий блип, высота
// растёт с номером искры) и финальный «дзынь» сбора (GDD §10).
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

// Страница может принести свой звуковой пакет (версия C: window.NJS_SOUND_PACK
// = { dir, files: { name: file } }) — его файлы заменяют/дополняют общие. Без
// пакета игра звучит как раньше; всё новое ниже (музыка, петли, отдельные
// звуки кнопок и барабанов) молча молчит, если файла нет.
const PACK = window.NJS_SOUND_PACK;
if (PACK) for (const [name, file] of Object.entries(PACK.files)) SOUND_FILES[name] = PACK.dir + file;

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.42;
const LOOP_VOLUME = 0.5;

let muted = localStorage.getItem('slot.muted') === '1';
let audioUnlocked = false;

const AudioCtx = window.AudioContext || window.webkitAudioContext;
const sfxCtx = AudioCtx ? new AudioCtx() : null;
const sfxGain = sfxCtx ? sfxCtx.createGain() : null;
if (sfxGain) {
  sfxGain.gain.value = SFX_VOLUME;
  sfxGain.connect(sfxCtx.destination);
}
const sfxBuffers = {};
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

function playSfx(name) {
  if (muted || !sfxCtx || !sfxBuffers[name]) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const source = sfxCtx.createBufferSource();
  source.buffer = sfxBuffers[name];
  source.connect(sfxGain);
  source.start();
}

const has = (name) => !!SOUND_FILES[name];
// Звук с запасным: свой файл пакета, иначе общий.
function playOr(name, fallback) {
  if (has(name)) playSfx(name);
  else if (fallback) playSfx(fallback);
}

// --- петли и музыка (WebAudio buffer loop: у <audio loop> щель на стыке mp3) ---

const loops = {};          // name -> { src, gain }
function startLoop(name, volume = LOOP_VOLUME, fade = 0.05) {
  if (!sfxCtx || !sfxBuffers[name] || loops[name]) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const src = sfxCtx.createBufferSource();
  src.buffer = sfxBuffers[name];
  src.loop = true;
  const g = sfxCtx.createGain();
  const t = sfxCtx.currentTime;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(muted ? 0.0001 : volume, t + fade);
  src.connect(g).connect(sfxCtx.destination);
  src.start();
  loops[name] = { src, gain: g, volume };
}
function stopLoop(name, fade = 0.08) {
  const l = loops[name];
  if (!l) return;
  delete loops[name];
  const t = sfxCtx.currentTime;
  l.gain.gain.cancelScheduledValues(t);
  l.gain.gain.setValueAtTime(Math.max(0.0001, l.gain.gain.value), t);
  l.gain.gain.exponentialRampToValueAtTime(0.0001, t + fade);
  l.src.stop(t + fade + 0.02);
}

// Фоновая музыка: 'base' | 'bonus' | null, смена — кроссфейдом.
let musicKind = null;
let wantMusic = null;
function music(kind) {
  wantMusic = kind;
  if (!audioUnlocked) return;            // запустится по первому касанию
  if (kind === musicKind) return;
  if (musicKind) stopLoop(`music_${musicKind}`, 0.9);
  musicKind = kind;
  if (!kind || !has(`music_${kind}`)) return;
  if (sfxBuffers[`music_${kind}`]) startLoop(`music_${kind}`, MUSIC_VOLUME, 0.9);
  else Promise.all(sfxLoadPromises).then(() => { if (musicKind === kind) startLoop(`music_${kind}`, MUSIC_VOLUME, 0.9); });
}

// Остановка барабана: у пакета свой звук на каждый барабан.
function reelStop(col, isLast) {
  if (has(`reelStop${col + 1}`)) playSfx(`reelStop${col + 1}`);
  else playSfx(isLast ? 'finalReelStop' : 'reelStop');
}

// --- синтез ------------------------------------------------------------------

function tone(freq, t0, dur, { type = 'triangle', gain = 0.22, glideTo = null } = {}) {
  const osc = sfxCtx.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (glideTo) osc.frequency.exponentialRampToValueAtTime(glideTo, t0 + dur);
  const env = sfxCtx.createGain();
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(gain, t0 + 0.012);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(env).connect(sfxGain);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

// Искра, летящая в Коллектор: n-я искра звучит выше — сбор «нарастает».
function spark(n = 0) {
  if (muted || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const t0 = sfxCtx.currentTime + 0.005;
  const base = 520 * Math.pow(1.122, Math.min(n, 14));
  tone(base, t0, 0.16, { type: 'square', gain: 0.07, glideTo: base * 1.9 });
  tone(base * 2, t0 + 0.02, 0.12, { gain: 0.06 });
}

// Финальный «дзынь»: мажорное трезвучие колокольчиком.
function ding(power = 1) {
  if (muted || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const t0 = sfxCtx.currentTime + 0.01;
  const g = 0.16 * Math.min(1.5, power);
  [1318.5, 1661.2, 1975.5, 2637].forEach((f, i) => tone(f, t0 + i * 0.035, 0.9, { type: 'sine', gain: g }));
}

// «+5» и захват монеты — короткий блип.
function blip(freq = 880) {
  if (muted || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  tone(freq, sfxCtx.currentTime + 0.005, 0.18, { type: 'triangle', gain: 0.16, glideTo: freq * 1.5 });
}

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  if (sfxCtx && sfxCtx.state === 'suspended') sfxCtx.resume();
  if (wantMusic) Promise.all(sfxLoadPromises).then(() => { const k = wantMusic; musicKind = null; music(k); });
}

function updateSoundIcon() {
  const btn = document.querySelector('[data-action="sound"]');
  if (btn) btn.classList.toggle('is-muted', muted);
}

function setMuted(next) {
  muted = next;
  localStorage.setItem('slot.muted', muted ? '1' : '0');
  updateSoundIcon();
  if (sfxCtx) {
    const t = sfxCtx.currentTime;
    for (const l of Object.values(loops)) l.gain.gain.setTargetAtTime(muted ? 0.0001 : l.volume, t, 0.05);
  }
}

window.addEventListener('pointerdown', unlockAudio, { once: true });
window.addEventListener('keydown', unlockAudio, { once: true });

window.Sound = {
  playSfx,
  playOr,
  has,
  startLoop,
  stopLoop,
  music,
  reelStop,
  spark,
  ding,
  blip,
  setMuted,
  toggleMuted: () => setMuted(!muted),
  preloadPromises: sfxLoadPromises,
  get muted() {
    return muted;
  },
  get musicPlaying() {
    return musicKind && loops[`music_${musicKind}`] ? musicKind : null;
  },
};

updateSoundIcon();
