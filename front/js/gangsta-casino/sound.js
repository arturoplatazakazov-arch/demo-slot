// Gangsta Casino — sound event catalogue (engine: js/sound-kit.js).
//
// Only the sound designer's pack (2026-11-27): one file per event in
// sound/gangsta-casino/designer/<event>.mp3 (the three scatter landings are
// WAV). Our generated variants were removed. An event the pack has no file
// for stays listed in the ♪ panel as «нет звука».
const GC_SOUND = 'sound/gangsta-casino/designer/';
// Bump when the designer sends a new version: the files keep their names.
const GC_DESIGNER_PACK = 1;
const GC_DESIGNER_WAV = new Set(['scatterLand1', 'scatterLand2', 'scatterLand3']);
const GC_DESIGNER = new Set(['base', 'bonus', 'click', 'spinPress', 'betChange', 'buyOpen', 'buyConfirm', 'popupOpen', 'popupClose',
  'spinStart', 'reelLoop', 'reelStop', 'finalReelStop', 'anticipation', 'anticipationWin', 'anticipationFail',
  'scatterLand1', 'scatterLand2', 'scatterLand3', 'multLand', 'smallWin', 'bigWin', 'megaWin', 'epicWin', 'countLoop', 'countEnd',
  'symWin_rare_purple', 'symWin_rare_yellow', 'symWin_rare_blue', 'symWin_rare_green', 'symWin_common_2', 'symWin_common_4',
  'symWin_common_3', 'symWin_common_1', 'symWin_wild', 'symWin_scatter', 'wildLand', 'wildGrow', 'multReveal', 'multFly', 'multPlate',
  'baseToBonus', 'bonusToBase', 'bonusSpinsWin', 'bonusTotalWin', 'screenOpen', 'fsCounter', 'winLine', 'screenTap']);

// Choices saved before the designer pack pointed at our old files: drop the
// saved variant picks once (volumes and mutes stay).
try {
  const flag = 'soundlab.gangsta-casino.designer';
  if (localStorage.getItem(flag) !== String(GC_DESIGNER_PACK)) {
    const st = JSON.parse(localStorage.getItem('soundlab.gangsta-casino') || 'null');
    if (st && st.ev) {
      for (const s of Object.values(st.ev)) { delete s.v; delete s.off; }
      localStorage.setItem('soundlab.gangsta-casino', JSON.stringify(st));
    }
    localStorage.setItem(flag, String(GC_DESIGNER_PACK));
  }
} catch (e) { /* private mode */ }

function gcVariants(key) {
  if (!GC_DESIGNER.has(key)) return [];
  return [`${GC_SOUND}${key}.${GC_DESIGNER_WAV.has(key) ? 'wav' : 'mp3'}?d=${GC_DESIGNER_PACK}`];
}

// One win event per symbol (code -> paytable name, app/seed/gangsta_casino.py).
const GC_SYMBOL_NAMES = {
  rare_purple: 'Queen', rare_yellow: 'Diva', rare_blue: 'Boss', rare_green: 'Hustler',
  common_2: 'Golden Uzi', common_4: 'Pink Glock', common_3: 'Knuckles', common_1: 'Bat',
  wild: 'Wild', scatter: 'Scatter',
};

const GC_EVENTS = {
  base: { kind: 'music', group: 'Музыка', label: 'Фон — база' },
  bonus: { kind: 'music', group: 'Музыка', label: 'Фон — фриспины' },

  click: { group: 'Интерфейс', label: 'Клик по кнопке' },
  spinPress: { group: 'Интерфейс', label: 'Нажатие SPIN' },
  betChange: { group: 'Интерфейс', label: 'Ставка + / −' },
  buyOpen: { group: 'Интерфейс', label: 'Клик по сундуку Buy' },
  buyConfirm: { group: 'Интерфейс', label: 'Покупка подтверждена ✓' },
  popupOpen: { group: 'Интерфейс', label: 'Попап открылся' },
  popupClose: { group: 'Интерфейс', label: 'Попап закрылся / ✗' },

  spinStart: { group: 'Барабаны', label: 'Старт спина' },
  reelLoop: { group: 'Барабаны', label: 'Вращение (петля)', loop: true },
  reelStop: { group: 'Барабаны', label: 'Стоп барабана' },
  finalReelStop: { group: 'Барабаны', label: 'Стоп последнего барабана' },
  anticipation: { group: 'Барабаны', label: 'Антисипация (петля, до стопа)', loop: true },
  anticipationWin: { group: 'Барабаны', label: 'Антисипация — удачная' },
  anticipationFail: { group: 'Барабаны', label: 'Антисипация — неудачная' },

  scatterLand1: { group: 'Приземления', label: 'Скаттер — 1-й' },
  scatterLand2: { group: 'Приземления', label: 'Скаттер — 2-й' },
  scatterLand3: { group: 'Приземления', label: 'Скаттер — 3-й и дальше' },
  wildLand: { group: 'Приземления', label: 'Вайлд упал' },
  multLand: { group: 'Приземления', label: 'Фишка множителя упала' },

  smallWin: { group: 'Выигрыши', label: 'Малый выигрыш (без попапа)' },
  winLine: { group: 'Выигрыши', label: 'Показ линии (каждая по очереди)' },
  bigWin: { group: 'Выигрыши', label: 'BIG WIN' },
  megaWin: { group: 'Выигрыши', label: 'MEGA WIN' },
  epicWin: { group: 'Выигрыши', label: 'EPIC WIN' },
  countLoop: { group: 'Выигрыши', label: 'Подсчёт суммы (петля)', loop: true },
  countEnd: { group: 'Выигрыши', label: 'Сумма досчитана' },
};
for (const [code, name] of Object.entries(GC_SYMBOL_NAMES)) {
  GC_EVENTS[`symWin_${code}`] = { group: 'Выигрыш символа', label: name, note: 'звучит, когда в показе выигрыша играет этот символ' };
}
Object.assign(GC_EVENTS, {
  wildGrow: { group: 'Вайлд и множители', label: 'Вайлд раскрывается' },
  wildWin: { group: 'Вайлд и множители', label: 'Большой вайлд в выигрыше' },
  multReveal: { group: 'Вайлд и множители', label: 'Множитель открылся' },
  multFly: { group: 'Вайлд и множители', label: 'Множитель летит на плашку' },
  multPlate: { group: 'Вайлд и множители', label: 'Плашка множителя обновилась' },

  baseToBonus: { group: 'Бонус и переходы', label: 'Переход база → бонус' },
  bonusToBase: { group: 'Бонус и переходы', label: 'Переход бонус → база' },
  bonusSpinsWin: { group: 'Бонус и переходы', label: 'Попап «YOU WON N FREE SPINS»' },
  bonusTotalWin: { group: 'Бонус и переходы', label: 'Попап «TOTAL WIN»' },
  fsCounter: { group: 'Бонус и переходы', label: 'Счётчик фриспинов −1' },
  screenOpen: { group: 'Бонус и переходы', label: 'Экран фичи / бонуса появился' },
  screenTap: { group: 'Бонус и переходы', label: 'Тап по экрану (TAP TO START)' },
});
for (const [key, e] of Object.entries(GC_EVENTS)) e.src = gcVariants(key);

window.Sound = SoundKit.create({
  game: 'gangsta-casino',
  sfxVolume: 0.7,
  musicVolume: 0.35,
  variantName: (path) => (path ? 'саунд-дизайнер' : null),
  libraryPrefix: GC_SOUND,
  events: GC_EVENTS,
});
