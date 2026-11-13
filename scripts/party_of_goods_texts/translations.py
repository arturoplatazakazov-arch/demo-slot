# Translations of texts.TEXTS (client set: az de es fr kk pl pt ru tr uk uz). All caps like
# the EN art. Turkish/Azerbaijani upper case keeps dotted İ. pt = Brazilian Portuguese.
# French: no-break space before : and !. Wording shared with Dirty Money / Amy's Fruit Farm /
# Golden Caravan (FREE SPINS, MULTIPLIERS, TAP TO ..., SCATTER as a term in Latin scripts).
# '·' = the strap's separator; a 2-line layout breaks there and drops it.
# Uzbek: the modifier letter ʻ is written as ’ — no game font has U+02BB (ʻ -> ’).
LANGS = ['ru', 'uk', 'kk', 'az', 'de', 'es', 'fr', 'pl', 'pt', 'tr', 'uz']
NB = ' '

TR = {
    'ru': dict(tag='КАСКАДНЫЕ ВЫИГРЫШИ  ·  8+ В ЛЮБОМ МЕСТЕ', t_fs='ФРИСПИНЫ', t_multi='МНОЖИТЕЛЬ', t_bolt='УДАР ЗЕВСА',
               d_fs='3+ СКАТТЕРА · ДО 20 СПИНОВ', d_multi='x2 x3 x5 x7 СУММИРУЮТСЯ ПРИ ВЫИГРЫШЕ',
               d_bolt='ОЧИЩАЕТ СВОЙ РЯД И СТОЛБЕЦ', tap_continue='НАЖМИТЕ, ЧТОБЫ ПРОДОЛЖИТЬ',
               t_bonus_win='ВАШИ СПИНЫ', tap_start='НАЖМИТЕ, ЧТОБЫ НАЧАТЬ'),
    'uk': dict(tag='КАСКАДНІ ВИГРАШІ  ·  8+ БУДЬ-ДЕ', t_fs='ФРІСПІНИ', t_multi='МНОЖНИК', t_bolt='УДАР ЗЕВСА',
               d_fs='3+ СКАТЕРИ · ДО 20 СПІНІВ', d_multi='x2 x3 x5 x7 ДОДАЮТЬСЯ ПРИ ВИГРАШІ',
               d_bolt='ОЧИЩАЄ СВІЙ РЯД І СТОВПЕЦЬ', tap_continue='НАТИСНІТЬ, ЩОБ ПРОДОВЖИТИ',
               t_bonus_win='ВАШІ СПІНИ', tap_start='НАТИСНІТЬ, ЩОБ ПОЧАТИ'),
    'kk': dict(tag='КАСКАДТЫ ҰТЫСТАР  ·  8+ КЕЗ КЕЛГЕН ЖЕРДЕ', t_fs='ФРИСПИН', t_multi='КӨБЕЙТКІШ',
               t_bolt='ЗЕВС ЖАЙЫ', d_fs='3+ СКАТТЕР · 20 СПИНГЕ ДЕЙІН', d_multi='x2 x3 x5 x7 ҰТЫСТА ҚОСЫЛАДЫ',
               d_bolt='ҚАТАР МЕН БАҒАНДЫ ТАЗАЛАЙДЫ', tap_continue='ЖАЛҒАСТЫРУ ҮШІН БАСЫҢЫЗ',
               t_bonus_win='СПИН ҰТЫСЫ', tap_start='БАСТАУ ҮШІН БАСЫҢЫЗ'),
    'az': dict(tag='KASKAD UDUŞLARI  ·  8+ İSTƏNİLƏN YERDƏ', t_fs='PULSUZ SPİN', t_multi='ÇARPAN',
               t_bolt='ZEVSİN İLDIRIMI', d_fs='3+ SKATTER · 20 SPİNƏ QƏDƏR', d_multi='x2 x3 x5 x7 UDUŞDA TOPLANIR',
               d_bolt='SƏTRİ VƏ SÜTUNU TƏMİZLƏYİR', tap_continue='DAVAM ETMƏK ÜÇÜN TOXUNUN',
               t_bonus_win='PULSUZ SPİN UDDUNUZ', tap_start='BAŞLAMAQ ÜÇÜN TOXUNUN'),
    'de': dict(tag='KASKADENGEWINNE  ·  8+ ÜBERALL ZAHLT', t_fs='FREISPIELE', t_multi='MULTIPLIKATOR',
               t_bolt='ZEUS-BLITZ', d_fs='3+ SCATTER · BIS ZU 20 FREISPIELE', d_multi='x2 x3 x5 x7 ADDIEREN SICH BEIM GEWINN',
               d_bolt='RÄUMT SEINE REIHE & SPALTE', tap_continue='TIPPEN ZUM FORTFAHREN',
               t_bonus_win='FREISPIELE GEWONNEN', tap_start='TIPPEN ZUM STARTEN'),
    'es': dict(tag='GANANCIAS EN CASCADA  ·  8+ PAGAN EN CUALQUIER LUGAR', t_fs='TIRADAS GRATIS',
               t_multi='MULTIPLICADOR', t_bolt='RAYO DE ZEUS', d_fs='3+ SCATTERS · HASTA 20 TIRADAS',
               d_multi='x2 x3 x5 x7 SE SUMAN AL GANAR', d_bolt='DESPEJA SU FILA Y COLUMNA',
               tap_continue='TOCA PARA CONTINUAR', t_bonus_win='HAS GANADO TIRADAS GRATIS', tap_start='TOCA PARA EMPEZAR'),
    'fr': dict(tag='GAINS EN CASCADE  ·  8+ PAIENT PARTOUT', t_fs='TOURS GRATUITS', t_multi='MULTIPLICATEUR',
               t_bolt='FOUDRE DE ZEUS', d_fs="3+ SCATTERS · JUSQU'À 20 TOURS", d_multi="x2 x3 x5 x7 S'ADDITIONNENT AU GAIN",
               d_bolt='VIDE SA LIGNE ET SA COLONNE', tap_continue='TOUCHEZ POUR CONTINUER',
               t_bonus_win='TOURS GRATUITS GAGNÉS', tap_start='TOUCHEZ POUR COMMENCER'),
    'pl': dict(tag='KASKADOWE WYGRANE  ·  8+ WYGRYWA WSZĘDZIE', t_fs='DARMOWE SPINY', t_multi='MNOŻNIK',
               t_bolt='PIORUN ZEUSA', d_fs='3+ SCATTERY · DO 20 SPINÓW', d_multi='x2 x3 x5 x7 SUMUJĄ SIĘ PRZY WYGRANEJ',
               d_bolt='CZYŚCI SWÓJ RZĄD I KOLUMNĘ', tap_continue='DOTKNIJ, ABY KONTYNUOWAĆ',
               t_bonus_win='WYGRANE DARMOWE SPINY', tap_start='DOTKNIJ, ABY ZACZĄĆ'),
    'pt': dict(tag='GANHOS EM CASCATA  ·  8+ PAGAM EM QUALQUER LUGAR', t_fs='RODADAS GRÁTIS', t_multi='MULTIPLICADOR',
               t_bolt='RAIO DE ZEUS', d_fs='3+ SCATTERS · ATÉ 20 RODADAS', d_multi='x2 x3 x5 x7 SE SOMAM NO GANHO',
               d_bolt='LIMPA SUA LINHA E COLUNA', tap_continue='TOQUE PARA CONTINUAR',
               t_bonus_win='VOCÊ GANHOU RODADAS GRÁTIS', tap_start='TOQUE PARA COMEÇAR'),
    'tr': dict(tag='KASKAD KAZANÇLAR  ·  8+ HER YERDE ÖDER', t_fs='BEDAVA DÖNÜŞ', t_multi='ÇARPAN',
               t_bolt="ZEUS'UN ŞİMŞEĞİ", d_fs='3+ SCATTER · 20 DÖNÜŞE KADAR', d_multi='x2 x3 x5 x7 KAZANÇTA TOPLANIR',
               d_bolt='SATIRINI VE SÜTUNUNU TEMİZLER', tap_continue='DEVAM ETMEK İÇİN DOKUNUN',
               t_bonus_win='BEDAVA DÖNÜŞ KAZANCI', tap_start='BAŞLAMAK İÇİN DOKUNUN'),
    'uz': dict(tag='KASKAD YUTUQLAR  ·  8+ ISTALGAN JOYDA', t_fs='BEPUL SPINLAR', t_multi='KO’PAYTIRGICH',
               t_bolt='ZEVS CHAQMOG’I', d_fs='3+ SKATTER · 20 TAGACHA SPIN', d_multi='x2 x3 x5 x7 YUTUQDA QO’SHILADI',
               d_bolt='QATOR VA USTUNNI TOZALAYDI', tap_continue='DAVOM ETISH UCHUN BOSING',
               t_bonus_win='BEPUL SPIN YUTDINGIZ', tap_start='BOSHLASH UCHUN BOSING'),
}
