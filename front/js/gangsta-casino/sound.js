// Gangsta Casino — sound event catalogue (engine: js/sound-kit.js).
//
// The game's OWN pack only: every event has 10 variants made in code by
// scripts/gc_sound/pack.py -> sound/gangsta-casino/<event>/v01..v10. The 10
// variants of an event are different ideas (instrument x motif x effect,
// different objects for hits, different genres for fanfares and music) to
// compare in the dev sound panel (♪). Loops are WAV
// (seamless), everything else MP3. v01 plays until a choice is made; once a
// variant is approved, set it as `variant` here (or move it to v01).
const GC_SOUND = 'sound/gangsta-casino/';
// Bump on every re-render of the pack: the files keep their names, so the
// browser would otherwise play the cached old ones.
const GC_PACK_VERSION = 3;
// Variant names ("Рок-гитара · октава · эхо", "фанк"…) written by the generator.
let GC_NAMES = {};
fetch(`${GC_SOUND}names.json?p=${GC_PACK_VERSION}`).then((r) => r.json()).then((n) => { GC_NAMES = n; if (window.DevTools) DevTools.refresh(); }).catch(() => {});
const GC_LOOPS = new Set(['reelLoop', 'anticipation', 'countLoop']);

function gcVariants(key) {
  const ext = GC_LOOPS.has(key) ? 'wav' : 'mp3';
  return Array.from({ length: 10 }, (_, i) => `${GC_SOUND}${key}/v${String(i + 1).padStart(2, '0')}.${ext}?p=${GC_PACK_VERSION}`);
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
  // ".../reelStop/v03.mp3" -> "фишки" in the panel
  variantName: (path) => {
    const m = /\/([^/]+)\/v(\d+)\.\w+(\?.*)?$/.exec(path || '');
    return m && GC_NAMES[m[1]] ? GC_NAMES[m[1]][Number(m[2]) - 1] || null : null;
  },
  libraryPrefix: GC_SOUND,
  // Variant N of the music and of every win fanfare is the same GENRE
  // (scripts/gc_sound/pack.py GENRES), so they switch as one set.
  sets: [
    {
      title: 'Музыкальный сет',
      note: 'фон базы + фон фриспинов + все фанфары (BIG / MEGA / EPIC / YOU WON / TOTAL)',
      keys: ['base', 'bonus', 'bigWin', 'megaWin', 'epicWin', 'bonusSpinsWin', 'bonusTotalWin'],
      names: ['синтвейв', 'трэп', 'фанк', 'латино', 'джаз-лаунж', 'рок', 'чиптюн', 'нуар-оркестр', 'диско', 'лоу-фай'],
      preview: () => (typeof currentMode === 'function' && currentMode() === 'freespins' ? 'bonus' : 'base'),
    },
    { title: 'Весь звук на один вариант', note: 'все 50 событий разом; у разных событий одна буква = разные идеи', keys: '*' },
  ],
  events: GC_EVENTS,
});
