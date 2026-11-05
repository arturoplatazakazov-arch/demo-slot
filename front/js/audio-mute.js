// Общий «рубильник» звука для всех слотов. Подключается ДО sound.js игры.
//
// Почему не хватало кнопки из sound.js: там mute делался через
// `music.volume = 0`, а на iOS (Safari и webview Телеграма) volume у
// <audio>/<video> только для чтения — присваивание молча игнорируется, и
// музыка продолжает играть. Плюс в разных играх 50+ своих sound.js с
// WebAudio-лупами, клонами <audio> и т.п., и каждый глушит по-своему.
//
// Здесь глушим на уровне платформы, не трогая sound.js:
//  - источник правды — localStorage 'slot.muted' (его пишут все sound.js при
//    переключении); ловим запись через Storage.prototype.setItem;
//  - каждый AudioContext при mute → suspend() (мгновенно затыкает и SFX, и
//    WebAudio-лупы), resume() игры, пока mute, не пропускаем;
//  - <audio>: при mute всё играющее ставим на паузу, длинные/зацикленные
//    треки (музыка) запоминаем и возобновляем при unmute; play() во время
//    mute ничего не играет (музыка запоминается, короткие SFX — пропускаются).
(function () {
  const KEY = 'slot.muted';
  let muted = false;
  try { muted = localStorage.getItem(KEY) === '1'; } catch (e) { /* private mode */ }

  const contexts = new Set();
  const media = new Set(); // элементы, которые запускал код
  const held = new Set(); // музыка, придержанная на время mute

  const isMusic = (el) => el.loop || (isFinite(el.duration) && el.duration > 8);

  // ---------- WebAudio ----------
  // Оригинальные resume/suspend по прототипу (AudioContext и, на старых
  // Safari, webkitAudioContext), чтобы самим звать их в обход блокировки.
  const ORIG = new Map();
  ['AudioContext', 'webkitAudioContext'].forEach((name) => {
    const p = window[name] && window[name].prototype;
    if (!p || ORIG.has(p)) return;
    const o = { resume: p.resume, suspend: p.suspend };
    ORIG.set(p, o);
    p.resume = function () {
      contexts.add(this);
      if (muted) return Promise.resolve();
      return o.resume.apply(this, arguments);
    };
  });
  function orig(c) {
    for (let p = Object.getPrototypeOf(c); p; p = Object.getPrototypeOf(p)) {
      if (ORIG.has(p)) return ORIG.get(p);
    }
    return null;
  }
  const ctxResume = (c) => orig(c).resume.call(c);
  const ctxSuspend = (c) => orig(c).suspend.call(c);

  // Контексты создаются в sound.js до первого resume — регистрируем сразу.
  ['AudioContext', 'webkitAudioContext'].forEach((name) => {
    const Orig = window[name];
    if (!Orig) return;
    class Tracked extends Orig {
      constructor(...args) {
        super(...args);
        contexts.add(this);
        if (muted) ctxSuspend(this).catch(() => {});
      }
    }
    window[name] = Tracked;
  });

  // ---------- <audio>/<video> ----------
  const mproto = window.HTMLMediaElement && HTMLMediaElement.prototype;
  const origPlay = mproto && mproto.play;
  const origPause = mproto && mproto.pause;
  if (mproto) {
    mproto.play = function () {
      if (this instanceof HTMLVideoElement) return origPlay.apply(this, arguments);
      media.add(this);
      if (muted) {
        if (isMusic(this)) held.add(this);
        return Promise.resolve();
      }
      return origPlay.apply(this, arguments);
    };
    mproto.pause = function () {
      held.delete(this);
      return origPause.apply(this, arguments);
    };
  }

  function apply() {
    contexts.forEach((c) => {
      if (c.state === 'closed') return;
      (muted ? ctxSuspend(c) : ctxResume(c)).catch(() => {});
    });
    if (!mproto) return;
    if (muted) {
      media.forEach((el) => {
        if (el.paused) return;
        origPause.call(el);
        if (isMusic(el)) held.add(el);
      });
    } else {
      held.forEach((el) => {
        const p = origPlay.call(el);
        if (p && p.catch) p.catch(() => {});
      });
      held.clear();
    }
  }

  function setMuted(next) {
    next = !!next;
    if (next === muted) return;
    muted = next;
    apply();
  }

  // Все sound.js сохраняют состояние сюда — это и есть сигнал переключения.
  const origSetItem = Storage.prototype.setItem;
  Storage.prototype.setItem = function (key, value) {
    origSetItem.apply(this, arguments);
    if (key === KEY && this === window.localStorage) setMuted(String(value) === '1');
  };

  window.AudioMute = {
    get muted() { return muted; },
  };
})();
