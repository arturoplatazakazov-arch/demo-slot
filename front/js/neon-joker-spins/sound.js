// Neon Joker Spins — звук. Механика как у tesla-spins/sound.js (one-shot SFX
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

const SFX_VOLUME = 0.7;

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
}

function updateSoundIcon() {
  const btn = document.querySelector('[data-action="sound"]');
  if (btn) btn.classList.toggle('is-muted', muted);
}

function setMuted(next) {
  muted = next;
  localStorage.setItem('slot.muted', muted ? '1' : '0');
  updateSoundIcon();
}

window.addEventListener('pointerdown', unlockAudio, { once: true });
window.addEventListener('keydown', unlockAudio, { once: true });

window.Sound = {
  playSfx,
  spark,
  ding,
  blip,
  setMuted,
  toggleMuted: () => setMuted(!muted),
  preloadPromises: sfxLoadPromises,
  get muted() {
    return muted;
  },
};

updateSoundIcon();
