// Olympus Thunder — sound. Same engine as every other game's sound.js
// (WebAudio one-shots, looped music unlocked on the first gesture, missing
// files fail soft). No themed pack exists yet, so the file cues borrow the
// closest existing sets (cascade cues from Sugar Galaxy, scatter / bonus
// total from East Discovery, cinematic beds from Golden Caravan).
//
// What the GDD asks for that no file covers is SYNTHESISED here:
//   thunder(value)  — the orb's thunderclap, pitched by its multiplier
//                     (GDD §12: "удар грома с высотой по значению");
//   crackle()       — the electric discharge of a tumbling symbol;
//   rise(step)      — the rising tone of the TOTAL MULTIPLIER.
const OT_SND = {
  COMMON: 'sound/common/',
  CASCADE: 'sound/sugar-galaxy/',
  EAST: 'sound/east-discovery/',
  BED: 'sound/golden-caravan/',
};

const SOUND_FILES = {
  smallWin: OT_SND.CASCADE + 'WIN_Small.mp3',
  bigWin: OT_SND.CASCADE + 'WIN_Big.mp3',
  megaWin: OT_SND.CASCADE + 'WIN_Mega.mp3',
  epicWin: OT_SND.CASCADE + 'WIN_Epic.mp3',
  drop: OT_SND.CASCADE + 'Element_drop.mp3',
  spinStart: OT_SND.CASCADE + 'SPIN_Start.mp3',
  boom: OT_SND.CASCADE + 'WIN_Boom.mp3',
  scatter: OT_SND.EAST + 'SCATTER_win.mp3',
  totalWin: OT_SND.EAST + 'Bonus_spins_total_win.mp3',
  coin: OT_SND.EAST + 'HOLD&WIN_Coin.wav',
  click: OT_SND.COMMON + 'Click_UI.mp3',
  popupOpen: OT_SND.COMMON + 'Popup-open.mp3',
  popupClose: OT_SND.COMMON + 'Popup-close.mp3',
  anticipation: OT_SND.COMMON + 'REELS_anticipation.mp3',
};

const MUSIC_FILES = {
  base: OT_SND.BED + 'BG_Base.mp3',
  fs: OT_SND.BED + 'BG_Bonus.mp3',
};

const SFX_VOLUME = 0.7;
const MUSIC_VOLUME = 0.32;

let muted = localStorage.getItem('slot.muted') === '1';
let currentMusic = null;
let currentMusicKey = null;
let musicUnlocked = false;
let pendingMusicKey = 'base';

const AudioCtx = window.AudioContext || window.webkitAudioContext;
const ctx = AudioCtx ? new AudioCtx() : null;
const master = ctx ? ctx.createGain() : null;
if (master) {
  master.gain.value = SFX_VOLUME;
  master.connect(ctx.destination);
}
const buffers = {};
const loadPromises = [];
if (ctx) {
  for (const [name, src] of Object.entries(SOUND_FILES)) {
    loadPromises.push(
      fetch(src)
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()))
        .then((ab) => ctx.decodeAudioData(ab))
        .then((buf) => { buffers[name] = buf; })
        .catch(() => {}),
    );
  }
}

function live() {
  if (muted || !ctx) return false;
  if (ctx.state === 'suspended') ctx.resume();
  return true;
}

function playSfx(name, { rate = 1, gain = 1 } = {}) {
  if (!live() || !buffers[name]) return;
  const src = ctx.createBufferSource();
  src.buffer = buffers[name];
  src.playbackRate.value = rate;
  const g = ctx.createGain();
  g.gain.value = gain;
  src.connect(g).connect(master);
  src.start();
}

let noiseBuf = null;
function noise() {
  if (noiseBuf) return noiseBuf;
  noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 3, ctx.sampleRate);
  const d = noiseBuf.getChannelData(0);
  let last = 0;
  for (let i = 0; i < d.length; i++) {
    // brown-ish noise: rumbles instead of hissing
    last = (last + 0.035 * (Math.random() * 2 - 1)) / 1.035;
    d[i] = last * 3.2;
  }
  return noiseBuf;
}

// Thunderclap: a sharp crack (filtered white burst) + a long low rumble.
// Bigger multipliers ring lower, longer and louder.
function thunder(value = 2) {
  if (!live()) return;
  const t = ctx.currentTime;
  const k = Math.min(1, Math.log(value) / Math.log(100)); // 0 .. 1
  const crack = ctx.createBufferSource();
  crack.buffer = noise();
  const hp = ctx.createBiquadFilter();
  hp.type = 'bandpass';
  hp.frequency.value = 2400 - 1400 * k;
  hp.Q.value = 0.7;
  const cg = ctx.createGain();
  cg.gain.setValueAtTime(0, t);
  cg.gain.linearRampToValueAtTime(0.9, t + 0.008);
  cg.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
  crack.connect(hp).connect(cg).connect(master);
  crack.start(t, Math.random());
  crack.stop(t + 0.4);

  const rum = ctx.createBufferSource();
  rum.buffer = noise();
  const lp = ctx.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.setValueAtTime(420 - 220 * k, t);
  lp.frequency.exponentialRampToValueAtTime(70, t + 1.4 + 1.6 * k);
  const rg = ctx.createGain();
  rg.gain.setValueAtTime(0, t);
  rg.gain.linearRampToValueAtTime(0.7 + 0.6 * k, t + 0.06);
  rg.gain.exponentialRampToValueAtTime(0.001, t + 1.5 + 1.8 * k);
  rum.connect(lp).connect(rg).connect(master);
  rum.start(t, Math.random());
  rum.stop(t + 3.6);

  // tonal body so a x100 is unmistakable
  const osc = ctx.createOscillator();
  osc.type = 'triangle';
  osc.frequency.setValueAtTime(140 - 70 * k, t);
  osc.frequency.exponentialRampToValueAtTime(40, t + 0.8);
  const og = ctx.createGain();
  og.gain.setValueAtTime(0.35 * (0.4 + k), t);
  og.gain.exponentialRampToValueAtTime(0.001, t + 0.9);
  osc.connect(og).connect(master);
  osc.start(t);
  osc.stop(t + 1);
}

// Electric discharge for symbols shattering in a tumble step.
function crackle() {
  if (!live()) return;
  const t = ctx.currentTime;
  const src = ctx.createBufferSource();
  src.buffer = noise();
  const hp = ctx.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = 3200;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0, t);
  for (let i = 0; i < 7; i++) {
    const at = t + i * 0.028 + Math.random() * 0.02;
    g.gain.setValueAtTime(0.5 * Math.random() + 0.2, at);
    g.gain.setValueAtTime(0.0, at + 0.012);
  }
  src.connect(hp).connect(g).connect(master);
  src.start(t, Math.random());
  src.stop(t + 0.3);
}

// Rising tone for the TOTAL MULTIPLIER — one semitone higher every hit.
let riseStep = 0;
function rise(reset = false) {
  if (reset) { riseStep = 0; return; }
  if (!live()) return;
  const t = ctx.currentTime;
  const f = 330 * Math.pow(2, Math.min(riseStep++, 24) / 12);
  for (const [mult, type, vol] of [[1, 'sine', 0.25], [2, 'triangle', 0.08], [1.5, 'sine', 0.08]]) {
    const o = ctx.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(f * mult * 0.7, t);
    o.frequency.exponentialRampToValueAtTime(f * mult, t + 0.12);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vol, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.7);
    o.connect(g).connect(master);
    o.start(t);
    o.stop(t + 0.75);
  }
}

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

window.addEventListener('pointerdown', unlockMusic, { once: true });
window.addEventListener('keydown', unlockMusic, { once: true });

window.Sound = {
  playSfx,
  playMusic,
  thunder,
  crackle,
  rise,
  preloadPromises: loadPromises,
  setMuted,
  toggleMuted: () => setMuted(!muted),
  get muted() { return muted; },
};
updateSoundIcon();
