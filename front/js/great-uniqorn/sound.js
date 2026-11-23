// Great Uniqorn — sound event catalogue (engine: js/sound-kit.js, shared with
// the dev sound panel ♪ of js/dev-tools.js).
//
// v01 of every event is the composer's pack ("Great Uniqorn SFX (Short)",
// 2026-11-11); v02, where there is one, is the earlier synthesized take
// (sound/great-uniqorn/synth_v1/, scripts/great_uniqorn_audio.py) kept to
// compare in the panel. The pack has no reel stops or bonus enter/exit, so
// those are the synthesized ones. A choice made in ♪ (variant, volume, mute)
// is stored per game in localStorage ('soundlab.great-uniqorn') and applies
// both here in the slot and on the animations pages.
//
// Event keys follow the shared spin order (js/slot-flow.js): scatterLand1..3,
// anticipation (loop) + anticipationWin/Fail, winLine, symWin_<code>,
// countLoop/countEnd, baseToBonus/bonusToBase. Events with no file of this
// game yet stay listed in ♪ as «нет звука».
// The API the slot uses: playSfx(name), playMusic('base'|'bonus'),
// startLoop(name) -> stop(), toggleMuted(), muted, preloadPromises.
// On top of SoundKit: each music level also runs its ambience bed (the
// AMBIENT_* loop) underneath, switched together with the music.
(function () {
  const GAME = 'sound/great-uniqorn/';
  const OLD = `${GAME}synth_v1/`;
  const v = (...files) => files.filter(Boolean);

  const EVENTS = {
    base: { kind: 'music', group: 'Музыка', label: 'Музыка — база', src: v(`${GAME}MUSIC_Base.mp3`, `${OLD}BG_Base.mp3`) },
    bonus: { kind: 'music', group: 'Музыка', label: 'Музыка — фриспины', src: v(`${GAME}MUSIC_Bonus.mp3`, `${OLD}BG_Bonus.mp3`) },
    ambientBase: { group: 'Музыка', label: 'Эмбиент — база (под музыкой)', src: v(`${GAME}AMBIENT_Base.mp3`), loop: true, volume: 0.25 },
    ambientBonus: { group: 'Музыка', label: 'Эмбиент — фриспины (под музыкой)', src: v(`${GAME}AMBIENT_Bonus.mp3`), loop: true, volume: 0.25 },

    smallWin: { group: 'Выигрыши', label: 'Выигрыш по линии', src: v(`${GAME}WIN_Line.mp3`, `${OLD}WIN_Line.mp3`) },
    bigWin: { group: 'Выигрыши', label: 'BIG WIN', src: v(`${GAME}WIN_Bigwin.mp3`, `${OLD}WIN_Big.mp3`) },
    megaWin: { group: 'Выигрыши', label: 'MEGA WIN', src: v(`${GAME}WIN_Megawin.mp3`, `${OLD}WIN_Mega.mp3`) },
    epicWin: { group: 'Выигрыши', label: 'EPIC WIN', src: v(`${GAME}WIN_Epicwin.mp3`, `${OLD}WIN_Epic.mp3`) },
    bonusTotalWin: { group: 'Выигрыши', label: 'BONUS SPINS TOTAL WIN', src: v(`${GAME}WIN_Bigwin.mp3`, `${OLD}WIN_Big.mp3`), note: 'своей дорожки нет — как BIG WIN' },
    winLine: { group: 'Выигрыши', label: 'Линия в показе выигрыша (каждая по очереди)', src: v(`${GAME}WIN_Line.mp3`, `${OLD}WIN_Line.mp3`) },
    countLoop: { group: 'Выигрыши', label: 'Счётчик суммы (петля)', src: v(`${GAME}WIN_Cashloop.mp3`, `${OLD}WIN_CashLoop.mp3`), loop: true },
    countEnd: { group: 'Выигрыши', label: 'Счётчик суммы — конец' },

    scatterLand1: { group: 'Символы', label: 'Скаттер — 1-й бургер упал', src: v(`${GAME}SCATTER_1.mp3`, `${OLD}SCATTER_1.mp3`) },
    scatterLand2: { group: 'Символы', label: 'Скаттер — 2-й бургер упал', src: v(`${GAME}SCATTER_2.mp3`, `${OLD}SCATTER_2.mp3`) },
    scatterLand3: { group: 'Символы', label: 'Скаттер — 3-й и дальше', src: v(`${GAME}SCATTER_3.mp3`, `${OLD}SCATTER_3.mp3`) },
    // a symbol's melody under its first win pass (js/slot-flow.js presentWins)
    symWin_scatter: { group: 'Мелодии символов', label: 'Скаттер — выигрыш / запуск бонуса', src: v(`${GAME}SCATTER_Win.mp3`, `${OLD}SCATTER_Win.mp3`) },
    symWin_wild: { group: 'Мелодии символов', label: 'Wild' },
    symWin_jet: { group: 'Мелодии символов', label: 'Самолёт' },
    symWin_docs: { group: 'Мелодии символов', label: 'Документы' },
    symWin_hair: { group: 'Мелодии символов', label: 'Причёска' },
    symWin_a: { group: 'Мелодии символов', label: 'A' },
    symWin_k: { group: 'Мелодии символов', label: 'K' },
    symWin_q: { group: 'Мелодии символов', label: 'Q' },
    symWin_j: { group: 'Мелодии символов', label: 'J' },
    wildLand: { group: 'Символы', label: 'Wild упал на барабан', src: v(`${GAME}WILD_Land.mp3`) },
    wildGrow: { group: 'Символы', label: 'Wild → множитель', src: v(`${GAME}WILD_Multiplier.mp3`, `${OLD}WILD_Multiplier.mp3`) },

    baseToBonus: { group: 'Бонус', label: 'Вход в фриспины (затемнение)', src: v(`${GAME}BONUS_Enter.mp3`) },
    bonusToBase: { group: 'Бонус', label: 'Выход из фриспинов', src: v(`${GAME}BONUS_Exit.mp3`) },
    buyButton: { group: 'Бонус', label: 'Покупка — окно открылось', src: v(`${GAME}BUY_Button.mp3`) },
    buyConfirm: { group: 'Бонус', label: 'Покупка — BUY', src: v(`${GAME}BUY_Confirm.mp3`) },

    click: { group: 'Интерфейс', label: 'Клик', src: v(`${GAME}UI_Click.mp3`, `${OLD}UI_Click.mp3`) },
    popupOpen: { group: 'Интерфейс', label: 'Попап открылся', src: v(`${GAME}UI_Popupopen.mp3`, `${OLD}UI_PopupOpen.mp3`) },
    popupClose: { group: 'Интерфейс', label: 'Попап закрылся', src: v(`${GAME}UI_Popupclose.mp3`, `${OLD}UI_PopupClose.mp3`) },
    autospin: { group: 'Интерфейс', label: 'Автоспин', src: v(`${GAME}UI_Autospin.mp3`, `${OLD}UI_Autospin.mp3`) },
    betPlus: { group: 'Интерфейс', label: 'Ставка +', src: v(`${GAME}UI_Betplus.mp3`, `${OLD}UI_BetPlus.mp3`) },
    betMinus: { group: 'Интерфейс', label: 'Ставка −', src: v(`${GAME}UI_Betminus.mp3`, `${OLD}UI_BetMinus.mp3`) },
    menu: { group: 'Интерфейс', label: 'Меню', src: v(`${GAME}UI_Menu.mp3`, `${OLD}UI_Menu.mp3`) },
    turbo: { group: 'Интерфейс', label: 'Турбо', src: v(`${GAME}UI_Turbo.mp3`, `${OLD}UI_Turbo.mp3`) },

    // reels 1-4 stop on rising notes (a little melody per spin), the 5th resolves
    spinStart: { group: 'Барабаны', label: 'Старт спина', src: v(`${GAME}REEL_SpinStart.mp3`) },
    reelStop1: { group: 'Барабаны', label: 'Стоп барабана 1', src: v(`${GAME}REEL_Stop_1.mp3`) },
    reelStop2: { group: 'Барабаны', label: 'Стоп барабана 2', src: v(`${GAME}REEL_Stop_2.mp3`) },
    reelStop3: { group: 'Барабаны', label: 'Стоп барабана 3', src: v(`${GAME}REEL_Stop_3.mp3`) },
    reelStop4: { group: 'Барабаны', label: 'Стоп барабана 4', src: v(`${GAME}REEL_Stop_4.mp3`) },
    finalReelStop: { group: 'Барабаны', label: 'Стоп последнего барабана', src: v(`${GAME}REEL_StopLast.mp3`) },
    anticipation: { group: 'Барабаны', label: 'Антисипация (петля до стопа барабана)', src: v(`${GAME}REEL_Anticipation.mp3`), loop: true },
    anticipationWin: { group: 'Барабаны', label: 'Антисипация — удача' },
    anticipationFail: { group: 'Барабаны', label: 'Антисипация — неудача' },
  };

  const kit = SoundKit.create({
    game: 'great-uniqorn',
    sfxVolume: 0.7,
    musicVolume: 0.35,
    libraryPrefix: GAME,
    variantName: (path) => (path && path.includes('/synth_v1/') ? 'синтез (старый)' : path && path.startsWith(GAME) ? 'пак композитора' : null),
    events: EVENTS,
  });

  // --- ambience bed under the music ------------------------------------------
  let ambient = null;
  let ambientKey = null;
  function startAmbient(level) {
    const key = level === 'bonus' ? 'ambientBonus' : 'ambientBase';
    if (ambient && ambientKey === key && !ambient.stopped) return;
    if (ambient) ambient.stop(400);
    ambientKey = key;
    ambient = kit.playSfx(key, { loop: true });
  }
  let level = 'base';
  let unlocked = false;
  function playMusic(key, opts) {
    level = key;
    kit.playMusic(key, opts);
    if (unlocked) startAmbient(key);
  }
  // the bed starts with the music on the first gesture (autoplay rules)
  const unlock = () => { unlocked = true; startAmbient(level); };
  window.addEventListener('pointerdown', unlock, { once: true });
  window.addEventListener('keydown', unlock, { once: true });

  // --- looping SFX (cash counter): returns stop() ---------------------------
  function startLoop(name) {
    const h = kit.playSfx(name, { loop: true });
    return () => h.stop(80);
  }

  function setMuted(value) {
    kit.setMuted(value);
    if (!value && unlocked) { ambient = null; startAmbient(level); }
  }

  window.Sound = {
    playSfx: kit.playSfx,
    stopSfx: kit.stopSfx,
    playMusic,
    stopMusic: kit.stopMusic,
    startLoop,
    setMuted,
    toggleMuted: () => setMuted(!kit.isMuted()),
    isMuted: kit.isMuted,
    get muted() { return kit.isMuted(); },
    preloadPromises: kit.preloadPromises,
    lab: kit.lab,
  };
})();
