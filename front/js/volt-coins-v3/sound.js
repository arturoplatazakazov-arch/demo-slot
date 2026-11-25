// Volt Coins V3 — звук через общий SoundKit (js/sound-kit.js): кнопка ♪
// DEV-пульта (js/dev-tools.js) переключает варианты, громкость каждого события
// и глушит отдельные звуки прямо на живом слоте; выбор хранится в
// localStorage (soundlab.volt-coins-v3). Игра зовёт Sound.playSfx / stopSfx /
// playMusic как раньше. Пакет — sound/volt-coins/ (ILL_1_VoltCoin от
// звукорежиссёра, 2026-10-20); первым в src стоит звук, который играет сейчас,
// дальше — прежние примерки (coin_try / zap_try / antic_try) и запасные файлы пакета.
(function () {
  const VC = 'sound/volt-coins/';
  const q = new URLSearchParams(location.search);
  // старые ссылки примерки (?coin= / ?zap= / ?antic=) по-прежнему выбирают вариант
  const pickTry = (param, names, folder) => {
    const n = names[Number(q.get(param)) - 1];
    return n ? `${VC}${folder}/${n}.wav` : null;
  };
  const COIN_TRY = ['coin_1_metal_tap', 'coin_2_chip_clack', 'coin_3_heavy_drop', 'coin_4_electric_drop', 'coin_5_short_ting', 'coin_6_soft_thud'];
  const ZAP_TRY = ['zap_1_snap_zap', 'zap_2_tesla_arc', 'zap_3_charge_release', 'zap_4_spark_shower', 'zap_5_zap_sweep', 'zap_6_thunder_strike'];
  const ANTIC_TRY = ['antic_1_tempo', 'antic_2_speedup', 'antic_3_cut_middle', 'antic_4_no_intro', 'antic_5_tempo_trim'];
  const f = (name) => VC + name;
  const tries = (folder, names) => names.map((n) => `${VC}${folder}/${n}.wav`);

  // Музыка и фон зала идут парой: «трек + фон@k» (слои SoundKit). Фон был
  // 0.22/3 при музыке 0.35 → слой ×0.21 от громкости музыки.
  const AMB = '@0.21';

  window.Sound = SoundKit.create({
    game: 'volt-coins-v3',
    sfxVolume: 0.7,
    musicVolume: 0.35,
    events: {
      // --- Барабаны ---
      spinStart: { group: 'Барабаны', label: 'Старт спина / респина', src: [f('UI_Spin.mp3'), f('HOLDWIN_Respin.mp3'), f('REELS_Spinloop.mp3')] },
      reelStop: { group: 'Барабаны', label: 'Стоп барабана', src: [f('REELS_Reelstop.mp3')] },
      finalReelStop: { group: 'Барабаны', label: 'Стоп последнего барабана', src: [f('REELS_Finalstop.mp3')] },
      anticipation: { group: 'Барабаны', label: 'Антисипация (2 монеты на линии)',
        src: [f('REELS_Anticipation_short.wav'), ...tries('antic_try', ANTIC_TRY), f('REELS_Anticipation_Nearhit.mp3')],
        variant: pickTry('antic', ANTIC_TRY, 'antic_try') },
      coinLand: { group: 'Барабаны', label: 'Монета упала на барабан',
        src: [f('SYMBOL_Coin_Landing_v3.wav'), ...tries('coin_try', COIN_TRY), f('SYMBOL_Coin_Landing_soft.wav'), f('SYMBOL_Coin_Landing.mp3')],
        variant: pickTry('coin', COIN_TRY, 'coin_try') },
      coilBuzz: { group: 'Барабаны', label: 'Искра катушки в простое',
        src: [f('SFX_CoilArc.wav'), ...tries('zap_try', ZAP_TRY), f('SFX_CoilBuzz.wav')],
        variant: pickTry('zap', ZAP_TRY, 'zap_try') },

      // --- Выигрыши ---
      winPresent: { group: 'Выигрыши', label: 'Показ выигрышной линии', src: [f('UI_Winpresent.mp3')] },
      smallWin: { group: 'Выигрыши', label: 'Мелкий выигрыш (без попапа)', src: [f('WIN_Smallwin.mp3')] },
      bigWin: { group: 'Выигрыши', label: 'BIG WIN', src: [f('WIN_Bigwin.mp3')] },
      megaWin: { group: 'Выигрыши', label: 'MEGA WIN', src: [f('WIN_Megawin.mp3')] },
      epicWin: { group: 'Выигрыши', label: 'EPIC WIN', src: [f('WIN_Epicwin.mp3')] },

      // --- Символы в выигрышной линии ---
      sym_horseshoe: { group: 'Символы', label: 'Подкова', src: [f('SYMBOL_Horseshoe.mp3')] },
      sym_star: { group: 'Символы', label: 'Звезда', src: [f('SYMBOL_Star.mp3')] },
      sym_bar: { group: 'Символы', label: 'BAR', src: [f('SYMBOL_BAR.mp3')] },
      sym_seven: { group: 'Символы', label: '7', src: [f('SYMBOL_Seven.mp3')] },
      sym_bell: { group: 'Символы', label: 'Колокол', src: [f('SYMBOL_Bell.mp3')] },
      sym_ingot: { group: 'Символы', label: 'Батарейка', src: [f('SYMBOL_Goldbar.mp3')] },
      sym_diamond: { group: 'Символы', label: 'Бриллиант', src: [f('SYMBOL_Diamond.mp3')] },
      sym_wild: { group: 'Символы', label: 'Wild', src: [f('SYMBOL_Wild.mp3')] },

      // --- Hold & Win ---
      holdWinTrigger: { group: 'Hold & Win', label: 'Триггер: 3 монеты в линию', src: [f('HOLDWIN_Trigger.mp3')] },
      baseToBonus: { group: 'Hold & Win', label: 'Переход база → раунд', src: [f('TRANSITION_BaseToBonus.mp3')] },
      holdWinStart: { group: 'Hold & Win', label: 'Старт раунда', src: [f('HOLDWIN_Start.mp3'), f('BONUS_HoldwinStart.mp3')] },
      respinCount: { group: 'Hold & Win', label: 'Счётчик респинов −1', src: [f('HOLDWIN_Respincount.mp3')] },
      resetCounter: { group: 'Hold & Win', label: 'Счётчик сброшен на 3', src: [f('HOLDWIN_Resetcounter.mp3')] },
      newCoin: { group: 'Hold & Win', label: 'Новая монета в раунде', src: [f('HOLDWIN_NewCoin.mp3')] },
      coinLock: { group: 'Hold & Win', label: 'Монета закрепилась', src: [f('HOLDWIN_CoinLock.mp3')] },
      jackpotCoin: { group: 'Hold & Win', label: 'Выпала джекпот-монета', src: [f('HOLDWIN_JackpotCoin.mp3')] },
      gridComplete: { group: 'Hold & Win', label: 'Всё поле заполнено', src: [f('HOLDWIN_GridComplete.mp3')] },
      coinCollect: { group: 'Hold & Win', label: 'Сбор монет', src: [f('HOLDWIN_CoinCollect.mp3'), f('WIN_Coinloop.mp3')] },
      roundTotalWin: { group: 'Hold & Win', label: 'Итог раунда (TOTAL WIN)', src: [f('HOLDWIN_End.mp3')] },
      bonusToBase: { group: 'Hold & Win', label: 'Переход раунд → база', src: [f('TRANSITION_BonusToBase.mp3')] },

      // --- Джекпоты ---
      jackpotReveal: { group: 'Джекпоты', label: 'Раскрытие джекпота', src: [f('TRANSITION_JackpotReveal.mp3')] },
      jackpot_mini: { group: 'Джекпоты', label: 'MINI', src: [f('JACKPOT_Mini.mp3')] },
      jackpot_minor: { group: 'Джекпоты', label: 'MINOR', src: [f('JACKPOT_Minor.mp3')] },
      jackpot_major: { group: 'Джекпоты', label: 'MAJOR', src: [f('JACKPOT_Major.mp3')] },
      jackpot_grand: { group: 'Джекпоты', label: 'GRAND', src: [f('JACKPOT_Grand.mp3')] },

      // --- Покупка бонуса ---
      buyBonus: { group: 'Покупка бонуса', label: 'Кнопка BUY BONUS', src: [f('UI_Buybonus.mp3')] },
      buyConfirm: { group: 'Покупка бонуса', label: 'Покупка подтверждена', src: [f('BONUS_BuyConfirm.mp3')] },

      // --- Интерфейс ---
      click: { group: 'Интерфейс', label: 'Клик', src: [f('UI_Click.mp3')] },
      bet: { group: 'Интерфейс', label: 'Ставка ±', src: [f('UI_Bet.mp3')] },
      autoplay: { group: 'Интерфейс', label: 'Автоигра', src: [f('UI_Autoplay.mp3')] },
      toggle: { group: 'Интерфейс', label: 'Турбо / звук', src: [f('UI_Toggle.mp3')] },
      popupOpen: { group: 'Интерфейс', label: 'Попап открылся', src: [f('UI_Popupopen.mp3')] },
      popupClose: { group: 'Интерфейс', label: 'Попап закрылся', src: [f('UI_Popupclose.mp3')] },

      // --- Музыка (с фоном зала под ней) ---
      base: { kind: 'music', group: 'Музыка', label: 'База (музыка + фон)',
        src: [`${f('MUSIC_Basemusic.mp3')} + ${f('AMBIENT_Baseambience.mp3')}${AMB}`, f('MUSIC_Basemusic.mp3'), f('AMBIENT_Baseambience.mp3')] },
      bonus: { kind: 'music', group: 'Музыка', label: 'Hold & Win (музыка + фон)',
        src: [`${f('MUSIC_Bonusmusic.mp3')} + ${f('AMBIENT_Bonusambience.mp3')}${AMB}`, f('MUSIC_Bonusmusic.mp3'), f('MUSIC_Jackpot.mp3')] },
    },
  });
})();
