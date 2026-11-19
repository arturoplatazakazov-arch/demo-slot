// SoundKit — shared sound engine with a built-in "sound lab".
//
// A game describes every sound EVENT it has (spin start, reel stop, each
// symbol's win, transitions, music…) and, per event, one or more VARIANT
// files. The game calls Sound.playSfx('<event>') / Sound.playMusic('<event>')
// exactly as before; the kit picks the event's active variant and plays it at
// the event's own volume. The dev sound panel (js/dev-tools.js) drives the
// lab API: switch variants, set per-event / master volume, mute single events,
// watch a live log — and the choice is kept per game in localStorage, so it
// survives reloads and can be tried on the real slot.
//
//   const Sound = SoundKit.create({
//     game: 'gangsta-casino',
//     sfxVolume: 0.7, musicVolume: 0.35,
//     events: {
//       spinStart: { group: 'Барабаны', label: 'Старт спина', src: ['sound/common/reel-start.mp3', 'sound/x/v2.wav'] },
//       anticipation: { group: 'Барабаны', label: 'Антисипация', src: [...], loop: true },
//       base: { kind: 'music', group: 'Музыка', label: 'База', src: [...] },
//     },
//   });
//   window.Sound = Sound;
//
// An event with no files is still listed (status "нет звука"), so missing
// sounds are visible instead of silently absent. Every playSfx returns a
// handle with stop() — used for loops (anticipation, count-up).
(function () {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;

  function readJson(key) {
    try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { return null; }
  }
  function writeJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }

  function create(cfg) {
    const game = cfg.game || 'slot';
    const storeKey = `soundlab.${game}`;
    const defaults = {
      sfx: cfg.sfxVolume != null ? cfg.sfxVolume : 0.7,
      music: cfg.musicVolume != null ? cfg.musicVolume : 0.35,
    };
    // Catalogue: key -> { key, kind, group, label, src[], loop, volume, note }
    const events = {};
    const order = [];
    for (const [key, e] of Object.entries(cfg.events || {})) {
      events[key] = {
        key,
        kind: e.kind || 'sfx',
        group: e.group || 'Прочее',
        label: e.label || key,
        note: e.note || '',
        src: (e.src ? [].concat(e.src) : []).filter(Boolean),
        loop: !!e.loop,
        volume: e.volume != null ? e.volume : 1,
        variant: e.variant || null, // default active path (else src[0])
        defaultOff: !!e.off,
      };
      order.push(key);
    }

    // Persisted lab state.
    let state = readJson(storeKey) || {};
    state.master = state.master || {};
    state.ev = state.ev || {};
    state.extra = state.extra || {};
    const save = () => writeJson(storeKey, state);

    function variantsOf(key) {
      const e = events[key];
      if (!e) return [];
      // extras saved earlier from outside this game's own folder are dropped
      const extra = (state.extra[key] || []).filter((p) => !cfg.libraryPrefix || p.startsWith(cfg.libraryPrefix));
      return [...e.src, ...extra.filter((p) => !e.src.includes(p))];
    }
    function activePath(key) {
      const e = events[key];
      if (!e) return null;
      const list = variantsOf(key);
      const s = state.ev[key];
      if (s && s.off) return null; // "без звука" chosen as a variant
      if (s && s.v) {
        // a saved choice survives a pack version bump (?p=N on the paths)
        const bare = (p) => p.split('?')[0];
        const hit = list.find((p) => p === s.v) || list.find((p) => bare(p) === bare(s.v));
        if (hit) return hit;
      }
      // `off: true` in the catalogue: the event has candidates but the game
      // stays silent on it until a variant is picked in the panel.
      if (e.defaultOff && !(s && s.off === false)) return null;
      if (e.variant && list.includes(e.variant)) return e.variant;
      return list[0] || null;
    }
    function eventVolume(key) {
      const s = state.ev[key];
      if (s && s.vol != null) return s.vol;
      return events[key] ? events[key].volume : 1;
    }
    function eventMuted(key) {
      const s = state.ev[key];
      return !!(s && s.mute);
    }
    function master(kind) {
      const v = state.master[kind];
      return v != null ? v : defaults[kind];
    }
    function evState(key) {
      return (state.ev[key] = state.ev[key] || {});
    }

    // --- global mute (the bar's sound button) -------------------------------
    let muted = localStorage.getItem('slot.muted') === '1';

    // --- listeners (dev log) ------------------------------------------------
    const listeners = new Set();
    const fired = {};
    function emit(info) {
      fired[info.key] = (fired[info.key] || 0) + 1;
      info.count = fired[info.key];
      info.t = performance.now();
      for (const fn of listeners) {
        try { fn(info); } catch (err) { console.warn('sound listener', err); }
      }
    }

    // --- SFX via WebAudio ---------------------------------------------------
    const ctx = AudioCtx ? new AudioCtx() : null;
    const sfxMaster = ctx ? ctx.createGain() : null;
    if (sfxMaster) {
      sfxMaster.gain.value = master('sfx');
      sfxMaster.connect(ctx.destination);
    }
    const buffers = {};   // path -> AudioBuffer
    const loading = {};   // path -> Promise<AudioBuffer|null>
    function loadBuffer(path) {
      if (!ctx || !path) return Promise.resolve(null);
      if (buffers[path]) return Promise.resolve(buffers[path]);
      if (!loading[path]) {
        loading[path] = fetch(path)
          .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(r.status))))
          .then((ab) => new Promise((res, rej) => ctx.decodeAudioData(ab, res, rej)))
          .then((buf) => { buffers[path] = buf; return buf; })
          .catch(() => null);
      }
      return loading[path];
    }
    const live = {}; // key -> Set of handles
    function track(key, handle) {
      (live[key] = live[key] || new Set()).add(handle);
    }

    function startBuffer(key, buf, opts) {
      if (ctx.state === 'suspended') ctx.resume();
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.loop = !!opts.loop;
      const g = ctx.createGain();
      g.gain.value = eventVolume(key) * (opts.gain != null ? opts.gain : 1);
      src.connect(g);
      g.connect(sfxMaster);
      src.start();
      return { src, g };
    }

    function playSfx(key, opts = {}) {
      const e = events[key];
      const path = e ? activePath(key) : null;
      const loop = opts.loop != null ? opts.loop : !!(e && e.loop);
      const silent = muted || eventMuted(key);
      emit({ key, kind: 'sfx', path, known: !!e, missing: !path, muted: silent, mutedBy: muted ? 'game' : silent ? 'event' : null, loop });
      // handle.done resolves when the sound has finished (ended or stopped);
      // at once when nothing plays — callers can wait for a melody to end.
      let finish;
      const handle = { key, stopped: false, node: null, el: null, stop() {}, done: new Promise((res) => { finish = res; }) };
      if (!e || !path || silent) { finish(); return handle; }
      let stopAt = null;
      handle.stop = (fadeMs = 120) => {
        handle.stopped = true;
        finish();
        if (live[key]) live[key].delete(handle);
        if (handle.node) {
          const { src, g } = handle.node;
          try {
            const now = ctx.currentTime;
            g.gain.cancelScheduledValues(now);
            g.gain.setValueAtTime(g.gain.value, now);
            g.gain.linearRampToValueAtTime(0, now + fadeMs / 1000);
            src.stop(now + fadeMs / 1000 + 0.02);
          } catch (err) { /* already stopped */ }
        }
        if (handle.el) handle.el.pause();
      };
      track(key, handle);
      if (ctx) {
        const go = (buf) => {
          if (!buf || handle.stopped) { finish(); return; }
          handle.node = startBuffer(key, buf, { loop, gain: opts.gain });
          handle.node.src.onended = () => { if (live[key]) live[key].delete(handle); finish(); };
          if (opts.maxMs) stopAt = setTimeout(() => handle.stop(), opts.maxMs);
        };
        if (buffers[path]) go(buffers[path]);
        else loadBuffer(path).then(go);
      } else {
        const a = new Audio(path);
        a.loop = loop;
        a.volume = Math.min(1, master('sfx') * eventVolume(key));
        a.play().catch(() => {});
        a.addEventListener('ended', finish);
        a.addEventListener('error', finish);
        handle.el = a;
      }
      void stopAt;
      return handle;
    }

    function stopSfx(key, fadeMs) {
      if (!live[key]) return;
      for (const h of [...live[key]]) h.stop(fadeMs);
    }

    // --- Music via <audio> --------------------------------------------------
    const musicEls = {}; // path -> HTMLAudioElement
    let musicUnlocked = false;
    let pendingMusic = null;
    let currentMusicKey = null;
    let currentMusicEl = null;
    function musicEl(path) {
      if (!musicEls[path]) {
        const a = new Audio();
        a.preload = 'none';
        a.src = path;
        a.loop = true;
        musicEls[path] = a;
      }
      return musicEls[path];
    }
    function musicVolumeFor(key) {
      if (muted || eventMuted(key)) return 0;
      return Math.max(0, Math.min(1, master('music') * eventVolume(key)));
    }
    function playMusic(key, { force = false } = {}) {
      pendingMusic = key;
      if (!musicUnlocked) return;
      if (!force && currentMusicKey === key && currentMusicEl && !currentMusicEl.paused) return;
      const path = activePath(key);
      emit({ key, kind: 'music', path, known: !!events[key], missing: !path, muted: muted || eventMuted(key), mutedBy: muted ? 'game' : eventMuted(key) ? 'event' : null });
      if (currentMusicEl) currentMusicEl.pause();
      currentMusicKey = key;
      currentMusicEl = null;
      if (!path) return;
      const a = musicEl(path);
      a.volume = musicVolumeFor(key);
      if (a.readyState > 0) a.currentTime = 0;
      a.play().catch(() => {});
      currentMusicEl = a;
    }
    function stopMusic() {
      if (currentMusicEl) currentMusicEl.pause();
      currentMusicEl = null;
      currentMusicKey = null;
    }
    function refreshMusicVolume() {
      if (currentMusicEl && currentMusicKey) currentMusicEl.volume = musicVolumeFor(currentMusicKey);
    }
    function unlock() {
      if (ctx && ctx.state === 'suspended') ctx.resume();
      if (musicUnlocked) return;
      musicUnlocked = true;
      if (pendingMusic) playMusic(pendingMusic, { force: true });
    }
    window.addEventListener('pointerdown', unlock, { once: true });
    window.addEventListener('keydown', unlock, { once: true });
    window.addEventListener('load', () => {
      for (const key of order) {
        if (events[key].kind !== 'music') continue;
        const p = activePath(key);
        if (p) { const a = musicEl(p); a.preload = 'auto'; a.load(); }
      }
    });

    // Active SFX variants decode at boot (the preloader can wait on them).
    const preloadPromises = order
      .filter((k) => events[k].kind !== 'music')
      .map((k) => loadBuffer(activePath(k)));

    // --- mute button --------------------------------------------------------
    function syncMuteButtons() {
      document.querySelectorAll('[data-action="sound"]').forEach((btn) => btn.classList.toggle('is-muted', muted));
    }
    function setMuted(value) {
      muted = !!value;
      localStorage.setItem('slot.muted', muted ? '1' : '0');
      refreshMusicVolume();
      if (muted) for (const k of Object.keys(live)) stopSfx(k, 60);
      syncMuteButtons();
    }
    function toggleMuted() { setMuted(!muted); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', syncMuteButtons);
    else syncMuteButtons();

    // --- lab API (dev sound panel) -----------------------------------------
    const lab = {
      game,
      // optional per-game naming of variant files and library scope
      variantName: (path) => (cfg.variantName ? cfg.variantName(path) : null),
      libraryPrefix: cfg.libraryPrefix || null,
      groups() {
        const out = [];
        const byName = {};
        for (const key of order) {
          const g = events[key].group;
          if (!byName[g]) { byName[g] = { name: g, keys: [] }; out.push(byName[g]); }
          byName[g].keys.push(key);
        }
        return out;
      },
      event(key) {
        const e = events[key];
        if (!e) return null;
        const s = state.ev[key] || {};
        return {
          ...e,
          variants: variantsOf(key),
          active: activePath(key),
          off: !activePath(key),
          volume: eventVolume(key),
          muted: eventMuted(key),
          fired: fired[key] || 0,
          extra: state.extra[key] || [],
        };
      },
      keys: () => [...order],
      // Sets: groups of events switched together to the same variant number
      // (cfg.sets: [{ title, keys, names }]; names[i] = what variant i is).
      sets: () => (cfg.sets || []).map((st) => ({ ...st, keys: st.keys === '*' ? [...order] : st.keys.filter((k) => events[k]) })),
      applySet(index, variantIndex) {
        const st = lab.sets()[index];
        if (!st) return;
        for (const key of st.keys) {
          const list = variantsOf(key);
          if (list[variantIndex]) lab.setVariant(key, list[variantIndex]);
        }
      },
      // Variant number every event of the set is on, or -1 when mixed.
      setVariantIndex(index) {
        const st = lab.sets()[index];
        if (!st || !st.keys.length) return -1;
        let idx = null;
        for (const key of st.keys) {
          const i = variantsOf(key).indexOf(activePath(key));
          if (idx === null) idx = i;
          if (i !== idx || i < 0) return -1;
        }
        return idx;
      },
      master,
      setMaster(kind, v) {
        state.master[kind] = v;
        save();
        if (kind === 'sfx' && sfxMaster) sfxMaster.gain.value = v;
        if (kind === 'music') refreshMusicVolume();
      },
      setVariant(key, path) {
        const s = evState(key);
        if (path === null) { s.off = true; delete s.v; } else { s.off = false; s.v = path; }
        save();
        if (path) loadBuffer(path);
        if (events[key] && events[key].kind === 'music' && currentMusicKey === key) playMusic(key, { force: true });
      },
      setVolume(key, v) {
        evState(key).vol = v;
        save();
        if (live[key]) for (const h of live[key]) if (h.node) h.node.g.gain.value = v;
        if (events[key] && events[key].kind === 'music') refreshMusicVolume();
      },
      setMute(key, b) {
        evState(key).mute = !!b;
        save();
        if (b) stopSfx(key, 60);
        if (events[key] && events[key].kind === 'music') refreshMusicVolume();
      },
      addVariant(key, path) {
        const list = (state.extra[key] = state.extra[key] || []);
        if (!list.includes(path) && !(events[key].src || []).includes(path)) list.push(path);
        lab.setVariant(key, path);
      },
      removeVariant(key, path) {
        state.extra[key] = (state.extra[key] || []).filter((p) => p !== path);
        if (state.ev[key] && state.ev[key].v === path) delete state.ev[key].v;
        save();
      },
      // Audition: SFX once (a loop is cut after 3 s); music switches track.
      preview(key) {
        const e = events[key];
        if (!e) return null;
        unlock();
        if (e.kind === 'music') {
          if (currentMusicKey === key && currentMusicEl && !currentMusicEl.paused) { stopMusic(); return null; }
          return playMusic(key, { force: true });
        }
        const wasMuted = muted;
        muted = false; // the panel's ▶ plays even when the game is muted
        const h = playSfx(key, e.loop ? { maxMs: 3000 } : {});
        muted = wasMuted;
        return h;
      },
      stopAll() {
        for (const k of Object.keys(live)) stopSfx(k, 60);
        stopMusic();
      },
      currentMusic: () => currentMusicKey,
      onEvent(fn) { listeners.add(fn); return () => listeners.delete(fn); },
      exportState() {
        const out = { game, master: { sfx: master('sfx'), music: master('music') }, events: {} };
        for (const key of order) {
          const s = state.ev[key] || {};
          const changed = s.off != null || s.v || s.vol != null || s.mute || (state.extra[key] || []).length;
          if (!changed) continue;
          out.events[key] = {
            variant: s.off ? null : activePath(key),
            volume: eventVolume(key),
            ...(s.mute ? { muted: true } : {}),
          };
        }
        return out;
      },
      reset() {
        state = { master: {}, ev: {}, extra: {} };
        save();
        if (sfxMaster) sfxMaster.gain.value = master('sfx');
        refreshMusicVolume();
      },
    };

    return {
      playSfx,
      stopSfx,
      playMusic,
      stopMusic,
      toggleMuted,
      setMuted,
      isMuted: () => muted,
      get muted() { return muted; },
      preloadPromises,
      lab,
    };
  }

  window.SoundKit = { create };
})();
