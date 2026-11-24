// Savannah Kings R2 — sound through the shared SoundKit (js/sound-kit.js), so
// the ♪ button of the DEV panel can audition variants, set per-event volumes
// and mute single events on the running slot. The game keeps calling
// Sound.playSfx / Sound.playMusic with the same keys as before.
//
// No pack of its own yet (GDD §9 wants African percussion + strings): the
// first variant of each event is what the Lodge version plays — music from
// Golden Caravan, stingers and the lion from East Discovery, the rest from
// sound/common/. The panel's "+" offers every file of front/sound/library.json.
const COMMON = 'sound/common/';
const WINS = 'sound/east-discovery/';
const DROP = 'sound/party-of-goods/';
const MUSIC = 'sound/golden-caravan/';

window.Sound = SoundKit.create({
  game: 'savannah-r2',
  sfxVolume: 0.7,
  musicVolume: 0.35,
  events: {
    // --- Барабаны ---
    spinStart: { group: 'Барабаны', label: 'Старт спина', src: [COMMON + 'reel-start.mp3'] },
    reelStop: { group: 'Барабаны', label: 'Стоп барабана', src: [COMMON + 'Reel_stop_slot.mp3'] },
    finalReelStop: { group: 'Барабаны', label: 'Стоп последнего барабана', src: [COMMON + 'REELS_final_stop.mp3'] },
    anticipation: { group: 'Барабаны', label: 'Ожидание 3-го скаттера / лапы', src: [COMMON + 'REELS_anticipation.mp3'] },

    // --- Выигрыши ---
    smallWin: { group: 'Выигрыши', label: 'Мелкий выигрыш (без попапа)', src: [WINS + 'WIN_Small.wav'] },
    bigWin: { group: 'Выигрыши', label: 'BIG WIN', src: [WINS + 'WIN_Big.wav'] },
    megaWin: { group: 'Выигрыши', label: 'MEGA WIN', src: [WINS + 'WIN_Mega.wav'] },
    epicWin: { group: 'Выигрыши', label: 'EPIC WIN', src: [WINS + 'WIN_Epic.wav'] },
    bonusTotalWin: { group: 'Выигрыши', label: 'TOTAL WIN фриспинов', src: [WINS + 'Bonus_spins_total_win.mp3'] },

    // --- Спецсимволы ---
    scatterLand: { group: 'Спецсимволы', label: 'Маска-скаттер приземлилась', src: [DROP + 'Element_drop.mp3'] },
    scatterWin: { group: 'Спецсимволы', label: 'Тригер фриспинов (маски)', src: [WINS + 'SCATTER_win.mp3'] },
    pawLand: { group: 'Спецсимволы', label: 'Лапа приземлилась', src: [DROP + 'Element_drop.mp3'] },
    pawTrigger: { group: 'Спецсимволы', label: 'Тригер колеса (лапы)', src: [WINS + 'HOLD&WIN_Coin.wav'] },
    wildGrow: { group: 'Спецсимволы', label: 'WILD раскрывается на барабан', src: [WINS + 'WILD_Scale.wav'] },
    roar: { group: 'Спецсимволы', label: 'Рык раскрытого льва', src: [WINS + 'WILD_Scale_wind.wav'] },

    // --- Колесо джекпотов ---
    wheelIn: { group: 'Колесо', label: 'Колесо появилось', src: [COMMON + 'Popup-open.mp3'] },
    wheelTick: { group: 'Колесо', label: 'Щелчок сектора', src: [COMMON + 'Click_UI.mp3'] },
    wheelStop: { group: 'Колесо', label: 'Остановка колеса', src: [COMMON + 'REELS_final_stop.mp3'] },

    // --- Интерфейс ---
    click: { group: 'Интерфейс', label: 'Клик по кнопке', src: [COMMON + 'Click_UI.mp3'] },
    popupOpen: { group: 'Интерфейс', label: 'Попап открылся', src: [COMMON + 'Popup-open.mp3'] },
    popupClose: { group: 'Интерфейс', label: 'Попап закрылся', src: [COMMON + 'Popup-close.mp3'] },

    // --- Музыка ---
    base: { kind: 'music', group: 'Музыка', label: 'База (закат)', src: [MUSIC + 'BG_Base.mp3'] },
    bonus: { kind: 'music', group: 'Музыка', label: 'Фриспины (ночь)', src: [MUSIC + 'BG_Bonus.mp3'] },
    wheel: { kind: 'music', group: 'Музыка', label: 'Колесо джекпотов', src: [WINS + 'BG_Bonus.mp3'] },
  },
});
