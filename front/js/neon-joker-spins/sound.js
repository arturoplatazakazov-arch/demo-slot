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
  const silent = labOff(name);
  labEmit(name, 'sfx', silent);
  if (muted || silent || !sfxCtx || !sfxBuffers[name]) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const source = sfxCtx.createBufferSource();
  source.buffer = sfxBuffers[name];
  const g = sfxCtx.createGain();
  g.gain.value = labVol(name);
  source.connect(g).connect(sfxGain);
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
  if (!loops[name]) labEmit(name, name.startsWith('music_') ? 'music' : 'sfx', labOff(name), true);
  if (!sfxCtx || !sfxBuffers[name] || loops[name] || labOff(name)) return;
  volume *= labVol(name) * (name.startsWith('music_') ? labMaster('music') / MUSIC_VOLUME : 1);
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
  labEmit('spark', 'sfx', labOff('spark'));
  if (muted || labOff('spark') || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const t0 = sfxCtx.currentTime + 0.005;
  const base = 520 * Math.pow(1.122, Math.min(n, 14));
  tone(base, t0, 0.16, { type: 'square', gain: 0.07, glideTo: base * 1.9 });
  tone(base * 2, t0 + 0.02, 0.12, { gain: 0.06 });
}

// Финальный «дзынь»: мажорное трезвучие колокольчиком.
function ding(power = 1) {
  labEmit('ding', 'sfx', labOff('ding'));
  if (muted || labOff('ding') || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  const t0 = sfxCtx.currentTime + 0.01;
  const g = 0.16 * Math.min(1.5, power);
  [1318.5, 1661.2, 1975.5, 2637].forEach((f, i) => tone(f, t0 + i * 0.035, 0.9, { type: 'sine', gain: g }));
}

// «+5» и захват монеты — короткий блип.
function blip(freq = 880) {
  labEmit('blip', 'sfx', labOff('blip'));
  if (muted || labOff('blip') || !sfxCtx) return;
  if (sfxCtx.state === 'suspended') sfxCtx.resume();
  tone(freq, sfxCtx.currentTime + 0.005, 0.18, { type: 'triangle', gain: 0.16, glideTo: freq * 1.5 });
}

// --- Hold & Win: tension, a coin lands, a respin brings nothing (synth, R1) ----------------
const hwReady = (key) => { labEmit(key, 'sfx', labOff(key)); if (muted || labOff(key) || !sfxCtx) return false; if (sfxCtx.state === 'suspended') sfxCtx.resume(); return true; };
// a cell stops empty: a dull, low knock
function hwThud() {
  if (!hwReady('hwThud')) return;
  const t0 = sfxCtx.currentTime + 0.005;
  tone(150, t0, 0.16, { type: 'sine', gain: 0.22, glideTo: 70 });
  tone(300, t0, 0.05, { type: 'triangle', gain: 0.05 });
}
// tension tick while the last cells hold out: higher and louder each time
function hwTick(k = 0) {
  if (!hwReady('hwTick')) return;
  const t0 = sfxCtx.currentTime + 0.005;
  const f = 440 * Math.pow(1.06, k);
  tone(f, t0, 0.07, { type: 'square', gain: 0.05 + Math.min(0.06, k * 0.012) });
  tone(f * 0.5, t0, 0.12, { type: 'sine', gain: 0.12 });
}
// a coin lands: a quick rising major arpeggio + sparkle; the n-th coin of a respin plays higher
function hwHit(n = 0) {
  if (!hwReady('hwHit')) return;
  const t0 = sfxCtx.currentTime + 0.005;
  const k = Math.pow(2, Math.min(n, 6) * 2 / 12);
  [523.3, 659.3, 784, 1046.5].forEach((f, i) => {
    tone(f * k, t0 + i * 0.06, 0.22, { type: 'square', gain: 0.06 });
    tone(f * k, t0 + i * 0.06, 0.3, { type: 'triangle', gain: 0.12 });
  });
  [2093, 2637, 3136].forEach((f, i) => tone(f * k, t0 + 0.26 + i * 0.04, 0.35, { type: 'sine', gain: 0.05 }));
}
// the respin is over and at least one coin came: a short brass-like fanfare
function hwWin(n = 1) {
  if (!hwReady('hwWin')) return;
  const t0 = sfxCtx.currentTime + 0.01;
  const chord = [392, 493.9, 587.3, 784];
  chord.forEach((f, i) => tone(f, t0 + i * 0.03, 0.18, { type: 'sawtooth', gain: 0.045 }));
  chord.forEach((f) => tone(f * 1.335, t0 + 0.2, 0.55 + Math.min(0.3, n * 0.08), { type: 'sawtooth', gain: 0.05 }));
  tone(1568, t0 + 0.2, 0.6, { type: 'sine', gain: 0.07 });
}
// the respin brought nothing: a falling "wah-wah-wah-waah" (sadder when it was the last chance)
function hwMiss(left = 2) {
  if (!hwReady('hwMiss')) return;
  const t0 = sfxCtx.currentTime + 0.01;
  const notes = left <= 0 ? [392, 370, 349.2, 329.6] : [349.2, 329.6, 311.1];
  notes.forEach((f, i) => {
    const last = i === notes.length - 1;
    tone(f, t0 + i * 0.22, last ? 0.75 : 0.2, { type: 'triangle', gain: 0.16, glideTo: last ? f * 0.86 : f * 0.97 });
    tone(f / 2, t0 + i * 0.22, last ? 0.75 : 0.2, { type: 'sawtooth', gain: 0.03, glideTo: last ? f * 0.43 : f * 0.49 });
  });
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


// --- sound lab (♪ panel of js/dev-tools.js; same lab API as js/sound-kit.js) --------
// Per event: switch the file (own file or any from sound/library.json), volume,
// mute; master volumes; live log. Kept per page in localStorage — without the
// panel the game sounds exactly as before.
const LAB_GAME = `neon-joker-spins${window.NJS_SKIN ? '-' + window.NJS_SKIN : ''}${window.NJS_LAB_SUFFIX || ''}`;
const LAB_KEY = `soundlab.${LAB_GAME}`;
let labState = (() => { try { return JSON.parse(localStorage.getItem(LAB_KEY)) || {}; } catch (e) { return {}; } })();
labState.ev = labState.ev || {}; labState.master = labState.master || {}; labState.extra = labState.extra || {};
const labSave = () => { try { localStorage.setItem(LAB_KEY, JSON.stringify(labState)); } catch (e) { /* noop */ } };
const LAB_META = {
  music_base: ['Музыка', 'База', 'music'], music_bonus: ['Музыка', 'Бонус', 'music'],
  spinStart: ['Барабаны', 'Старт спина'], reelLoop: ['Барабаны', 'Петля вращения', 'loop'],
  reelStop1: ['Барабаны', 'Стоп барабана 1'], reelStop2: ['Барабаны', 'Стоп барабана 2'], reelStop3: ['Барабаны', 'Стоп барабана 3'],
  reelStop: ['Барабаны', 'Стоп (общий)'], finalReelStop: ['Барабаны', 'Последний стоп'], anticipation: ['Барабаны', 'Ожидание'],
  coinLand: ['Барабаны', 'Монета встала'],
  smallWin: ['Выигрыш', 'Малый выигрыш'], bigWin: ['Выигрыш', 'Big Win'], megaWin: ['Выигрыш', 'Mega Win'], epicWin: ['Выигрыш', 'Epic Win'],
  bonusEnter: ['Бонусы', 'Вход в бонус'], bonusExit: ['Бонусы', 'Выход из бонуса'],
  hwThud: ['Hold & Win', 'Пустая ячейка (синтез)', 'synth'], hwTick: ['Hold & Win', 'Напряжение (синтез)', 'synth'],
  hwHit: ['Hold & Win', 'Монета выпала (синтез)', 'synth'], hwWin: ['Hold & Win', 'Удачный респин (синтез)', 'synth'],
  hwMiss: ['Hold & Win', 'Пустой респин (синтез)', 'synth'],
  spark: ['Бонусы', 'Искра Коллектора (синтез)', 'synth'], ding: ['Бонусы', 'Сбор «дзынь» (синтез)', 'synth'], blip: ['Бонусы', 'Монета / +5 (синтез)', 'synth'],
  popupOpen: ['Интерфейс', 'Попап открылся'], popupClose: ['Интерфейс', 'Попап закрылся'], click: ['Интерфейс', 'Клик'],
  autospin: ['Интерфейс', 'Автоигра'], betPlus: ['Интерфейс', 'Ставка +'], betMinus: ['Интерфейс', 'Ставка −'], menu: ['Интерфейс', 'Меню'], turbo: ['Интерфейс', 'Турбо'],
};
const LAB_ORIG = { ...SOUND_FILES };
const labKeys = () => [...new Set([...Object.keys(LAB_META), ...Object.keys(SOUND_FILES)])];
const labEv = (k) => (labState.ev[k] = labState.ev[k] || {});
function labVol(k) { const v = labState.ev[k] && labState.ev[k].vol; return v == null ? 1 : v; }
function labOff(k) { const e = labState.ev[k]; return !!(e && (e.mute || e.off)); }
function labMaster(kind) { const v = labState.master[kind]; return v == null ? (kind === 'music' ? MUSIC_VOLUME : SFX_VOLUME) : v; }
const labListeners = new Set();
const labFired = {};
function labEmit(key, kind, silent, loop = false) {
  labFired[key] = (labFired[key] || 0) + 1;
  const path = SOUND_FILES[key] || null;
  const info = { key, kind, path, known: !!LAB_META[key], missing: !path && !(LAB_META[key] || [])[2], muted: muted || silent,
    mutedBy: muted ? 'game' : silent ? 'event' : null, loop, count: labFired[key], t: performance.now() };
  for (const fn of labListeners) { try { fn(info); } catch (e) { /* noop */ } }
}
function labLoad(key, path) {
  if (!sfxCtx || !path) return Promise.resolve();
  return fetch(path).then((r) => (r.ok ? r.arrayBuffer() : Promise.reject())).then((ab) => sfxCtx.decodeAudioData(ab))
    .then((buf) => { if (SOUND_FILES[key] === path) sfxBuffers[key] = buf; }).catch(() => {});
}
// saved choices of this page
for (const [k, e] of Object.entries(labState.ev)) if (e.v && e.v !== SOUND_FILES[k]) { SOUND_FILES[k] = e.v; sfxLoadPromises.push(labLoad(k, e.v)); }
if (sfxGain && labState.master.sfx != null) sfxGain.gain.value = labState.master.sfx;
function labRestartMusic(key) {
  if (key === `music_${musicKind}`) { const k = musicKind; stopLoop(key, 0.2); musicKind = null; music(k); }
}
const soundLab = {
  game: LAB_GAME,
  variantName: () => null,
  libraryPrefix: null,
  groups() {
    const out = []; const by = {};
    for (const k of labKeys()) { const g = (LAB_META[k] || ['Прочее'])[0]; if (!by[g]) { by[g] = { name: g, keys: [] }; out.push(by[g]); } by[g].keys.push(k); }
    return out;
  },
  event(key) {
    const m = LAB_META[key] || ['Прочее', key];
    const synth = m[2] === 'synth';
    const orig = LAB_ORIG[key] ? [LAB_ORIG[key]] : [];
    const extra = labState.extra[key] || [];
    const e = labState.ev[key] || {};
    return { key, kind: m[2] === 'music' ? 'music' : 'sfx', group: m[0], label: m[1], note: synth ? 'звук синтезируется в коде' : '',
      src: orig, loop: m[2] === 'loop' || m[2] === 'music', volume: labVol(key), variants: [...orig, ...extra],
      active: synth ? (e.off ? null : 'synth') : (e.off ? null : SOUND_FILES[key] || null), off: !!e.off || (!synth && !SOUND_FILES[key]),
      muted: !!e.mute, fired: labFired[key] || 0, extra };
  },
  keys: labKeys,
  sets: () => [],
  applySet() {},
  setVariantIndex: () => -1,
  master: labMaster,
  setMaster(kind, v) {
    labState.master[kind] = v; labSave();
    if (kind === 'sfx' && sfxGain) sfxGain.gain.value = v;
    if (kind === 'music' && musicKind) labRestartMusic(`music_${musicKind}`);
  },
  setVariant(key, path) {
    const e = labEv(key);
    if (path === null) { e.off = true; delete e.v; } else { e.off = false; e.v = path; if (path !== 'synth') { SOUND_FILES[key] = path; labLoad(key, path).then(() => labRestartMusic(key)); } }
    labSave();
  },
  setVolume(key, v) { labEv(key).vol = v; labSave(); if (loops[key]) loops[key].gain.gain.value = loops[key].volume * v; labRestartMusic(key); },
  setMute(key, b) { labEv(key).mute = !!b; labSave(); if (b) stopLoop(key); labRestartMusic(key); },
  addVariant(key, path) { const l = (labState.extra[key] = labState.extra[key] || []); if (!l.includes(path) && path !== LAB_ORIG[key]) l.push(path); soundLab.setVariant(key, path); },
  removeVariant(key, path) { labState.extra[key] = (labState.extra[key] || []).filter((p) => p !== path); if (labState.ev[key] && labState.ev[key].v === path) { delete labState.ev[key].v; SOUND_FILES[key] = LAB_ORIG[key]; labLoad(key, LAB_ORIG[key]); } labSave(); },
  preview(key) {
    unlockAudio();
    if (key.startsWith('music_')) { const k = key.slice(6); if (musicKind === k) music(null); else music(k); return null; }
    const was = muted; muted = false;
    if ((LAB_META[key] || [])[2] === 'synth') ({ spark, ding, blip, hwThud, hwTick, hwHit, hwWin, hwMiss })[key]();
    else if ((LAB_META[key] || [])[2] === 'loop') { startLoop(key); setTimeout(() => stopLoop(key), 2500); }
    else playSfx(key);
    muted = was;
    return null;
  },
  stopAll() { for (const k of Object.keys(loops)) stopLoop(k); musicKind = null; },
  currentMusic: () => (musicKind ? `music_${musicKind}` : null),
  onEvent(fn) { labListeners.add(fn); return () => labListeners.delete(fn); },
  exportState() {
    const out = { game: LAB_GAME, master: { sfx: labMaster('sfx'), music: labMaster('music') }, events: {} };
    for (const k of labKeys()) { const e = labState.ev[k]; if (e && (e.v || e.off || e.vol != null || e.mute)) out.events[k] = { variant: e.off ? null : SOUND_FILES[k], volume: labVol(k), ...(e.mute ? { muted: true } : {}) }; }
    return out;
  },
  reset() { labState = { ev: {}, master: {}, extra: {} }; labSave(); Object.assign(SOUND_FILES, LAB_ORIG); for (const [k, p] of Object.entries(LAB_ORIG)) labLoad(k, p); if (sfxGain) sfxGain.gain.value = SFX_VOLUME; },
};

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
  hwThud,
  hwTick,
  hwHit,
  hwWin,
  hwMiss,
  setMuted,
  toggleMuted: () => setMuted(!muted),
  isMuted: () => muted,
  preloadPromises: sfxLoadPromises,
  lab: soundLab,
  get muted() {
    return muted;
  },
  get musicPlaying() {
    return musicKind && loops[`music_${musicKind}`] ? musicKind : null;
  },
};

updateSoundIcon();
