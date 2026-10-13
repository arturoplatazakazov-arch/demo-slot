// Tesla Spins — звук. Механика та же, что у gold-of-baku/sound.js
// (one-shot SFX через WebAudio, мягкое падение на отсутствующем файле), плюс
// СИНТЕЗИРОВАННЫЙ треск разряда: своего пака у темы нет, а электрического
// эффекта нет ни в одном паке проекта, поэтому `zap` собирается на лету из шума
// (полосовой фильтр + рваная огибающая) и низкого гула трансформатора.
//
// Тиры выигрыша и музыка — из неонового пака neon-reels (ближайшая по
// настроению тема), барабаны и UI — общие.
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

// --- синтез разряда -----------------------------------------------------------

let noiseBuffer = null;
function getNoise() {
  if (noiseBuffer) return noiseBuffer;
  const len = sfxCtx.sampleRate * 2;
  noiseBuffer = sfxCtx.createBuffer(1, len, sfxCtx.sampleRate);
  const data = noiseBuffer.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  return noiseBuffer;
}

// Треск: шум через полосовой фильтр, громкость рвётся на 10-25 коротких
// «искр» (каждая 4-20мс), плюс 50-герцовый гул под ними. power 0.5..2.
function zap(durationMs = 600, power = 1) {
  if (muted || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const t0 = sfxCtx.currentTime + 0.01;
  const dur = durationMs / 1000;

  const src = sfxCtx.createBufferSource();
  src.buffer = getNoise();
  src.loop = true;
  const band = sfxCtx.createBiquadFilter();
  band.type = 'bandpass';
  band.frequency.value = 2400;
  band.Q.value = 0.7;
  const hp = sfxCtx.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = 700;
  const env = sfxCtx.createGain();
  env.gain.setValueAtTime(0, t0);
  const sparks = Math.round(10 + 15 * Math.min(1, power));
  let t = t0;
  const level = 0.55 * Math.min(1.4, power);
  for (let i = 0; i < sparks && t < t0 + dur; i++) {
    const on = 0.004 + Math.random() * 0.016;
    const off = Math.random() * (dur / sparks);
    env.gain.setValueAtTime(level * (0.4 + Math.random() * 0.6), t);
    env.gain.setValueAtTime(0.02, t + on);
    t += on + off;
  }
  env.gain.setValueAtTime(0, t0 + dur);
  src.connect(band).connect(hp).connect(env).connect(sfxGain);
  src.start(t0);
  src.stop(t0 + dur + 0.05);

  // гул трансформатора
  const hum = sfxCtx.createOscillator();
  hum.type = 'sawtooth';
  hum.frequency.value = 55;
  const lp = sfxCtx.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.value = 220;
  const humGain = sfxCtx.createGain();
  humGain.gain.setValueAtTime(0, t0);
  humGain.gain.linearRampToValueAtTime(0.18 * Math.min(1.5, power), t0 + 0.05);
  humGain.gain.exponentialRampToValueAtTime(0.001, t0 + dur + 0.2);
  hum.connect(lp).connect(humGain).connect(sfxGain);
  hum.start(t0);
  hum.stop(t0 + dur + 0.25);
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
  zap,
  setMuted,
  toggleMuted: () => setMuted(!muted),
  preloadPromises: sfxLoadPromises,
  get muted() {
    return muted;
  },
};

updateSoundIcon();
