// Dirty Money / MAFIA — sound through the shared SoundKit (js/sound-kit.js),
// so the ♪ button of the DEV panel can audition variants, set per-event
// volumes and mute single events right on the running slot. The game keeps
// calling Sound.playSfx / Sound.playMusic exactly as before.
//
// No bespoke pack was ever made for this theme: `sound/dirty-money-mafia/` is
// empty, so the events below point at the shared cues in `sound/common/` where
// one fits and are left EMPTY otherwise. An empty event still shows up in the
// panel as «нет звука», and its "+" library offers every file in
// front/sound/library.json (1000+ cues from the other games) — that is how a
// pack gets picked here before anything is recorded for this slot.
const COMMON = 'sound/common/';

window.Sound = SoundKit.create({
  game: 'dirty-money-mafia',
  sfxVolume: 0.7,
  musicVolume: 0.35,
  events: {
    // --- Барабаны ---
    spinStart: { group: 'Барабаны', label: 'Старт спина', src: [COMMON + 'reel-start.mp3'] },
    reelStop: { group: 'Барабаны', label: 'Стоп барабана', src: [COMMON + 'Reel_stop_slot.mp3'] },
    finalReelStop: { group: 'Барабаны', label: 'Стоп последнего барабана', src: [COMMON + 'REELS_final_stop.mp3'] },
    anticipation: { group: 'Барабаны', label: 'Антисипация', src: [COMMON + 'REELS_anticipation.mp3'] },

    // --- Выигрыши ---
    smallWin: { group: 'Выигрыши', label: 'Мелкий выигрыш (без попапа)', src: [] },
    bigWin: { group: 'Выигрыши', label: 'BIG WIN', src: [] },
    megaWin: { group: 'Выигрыши', label: 'MEGA WIN', src: [] },
    epicWin: { group: 'Выигрыши', label: 'EPIC WIN', src: [] },

    // --- Фичи ---
    wildGrow: { group: 'Фичи', label: 'WILD раскрывается на барабан', src: [] },
    wildWin: { group: 'Фичи', label: 'Раскрытый WILD в выигрыше', src: [] },
    wheelSpin: { group: 'Фичи', label: 'Колесо фортуны крутится', src: [], loop: true },

    // --- Интерфейс ---
    click: { group: 'Интерфейс', label: 'Клик по кнопке', src: [COMMON + 'Click_UI.mp3'] },
    popupOpen: { group: 'Интерфейс', label: 'Попап открылся', src: [COMMON + 'Popup-open.mp3'] },
    popupClose: { group: 'Интерфейс', label: 'Попап закрылся', src: [COMMON + 'Popup-close.mp3'] },

    // --- Музыка ---
    base: { kind: 'music', group: 'Музыка', label: 'База', src: [] },
    bonus: { kind: 'music', group: 'Музыка', label: 'Фриспины', src: [] },
  },
});

// The old sound.js exposed the mute state through the bar's ♪-less button and
// kept the icon in sync; SoundKit owns muting now, so only the icon is left.
function updateSoundIcon() {
  document.querySelectorAll('[data-action="sound"]').forEach((btn) => {
    btn.classList.toggle('is-muted', window.Sound.isMuted());
  });
}
const origToggleMuted = window.Sound.toggleMuted;
window.Sound.toggleMuted = function () {
  origToggleMuted.call(window.Sound);
  updateSoundIcon();
};
document.addEventListener('DOMContentLoaded', updateSoundIcon);
