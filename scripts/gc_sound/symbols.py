"""Themed win sounds for every Gangsta Casino symbol — 10 variants each, all
built around what the symbol IS (app/seed/gangsta_casino.py names):

  common_4 Pink Glock  — pistol shots      common_2 Golden Uzi — bursts, casings, gold
  common_1 Bat         — swings and hits   common_3 Knuckles   — punches
  rare_purple Queen    — royal glamour     rare_yellow Diva    — star / party
  rare_blue Boss       — weight and money  rare_green Hustler  — cash, cards, dice
  wild (masked robber) — the heist         scatter (vault)     — the safe opening

Each variant = the object's foley + (mostly) a short musical sting, finished
with foley.finish (glue, stereo width, room). Key: A (wins in A major).
"""
from __future__ import annotations

import numpy as np

import dsp
import foley as F
from dsp import mix

A2, A3, A4, A5, A6 = 45, 57, 69, 81, 93
H = lambda m: dsp.hz(float(m))  # noqa: E731


def stab(m_list, inst="brass", dur=0.6, r=None):
    if inst == "brass":
        return dsp.brass([H(m) for m in m_list], dur, 2600, 0.01, r)
    if inst == "strings":
        return sum(dsp.strings(H(m), dur, r) for m in m_list) / len(m_list)
    if inst == "choir":
        return sum(dsp.choir(H(m), dur, "a", 3, r) for m in m_list) / len(m_list)
    if inst == "epiano":
        return sum(dsp.epiano(H(m), dur, dur * 0.6) for m in m_list) / len(m_list)
    if inst == "organ":
        return sum(dsp.organ(H(m), dur, r) for m in m_list) / len(m_list)
    if inst == "bells":
        return sum(dsp.bell(H(m), dur, 1.4142, 1.6, dur * 0.7) for m in m_list) / len(m_list)
    if inst == "guitar":
        return sum(dsp.dist_guitar(H(m), dur, True, r) for m in m_list[:1])
    raise ValueError(inst)


MAJ = [A4, A4 + 4, A4 + 7]
MIN = [A3, A3 + 3, A3 + 7]


def glock(r):
    shot = lambda: F.gunshot(r, 0.9, 1.1)
    return [
        ("выстрел с эхом улицы", lambda: F.outdoor_tail(shot(), r, 1.6, 0.6)),
        ("дабл-тап + гильзы", lambda: mix((shot(), 0), (shot(), 0.16, 0.9), (F.casings(r, 2, 0.25), 0))),
        ("затвор → выстрел → гильза", lambda: mix((F.gun_cock_long(r), 0), (shot(), 0.42), (F.casings(r, 1, 0.6), 0))),
        ("глушитель ×2", lambda: mix((F.silenced(r), 0), (F.silenced(r), 0.22, 0.9), (F.casings(r, 2, 0.35), 0, 0.7))),
        ("рикошет", lambda: mix((shot(), 0), (F.ricochet(r), 0.08, 0.9))),
        ("выстрел + розовый блеск", lambda: mix((shot(), 0), (stab(MAJ + [A5], "bells", 1.2, r), 0.1, 0.6), (F.sparkle_dust(r, 10, 0.6), 0.12, 0.6))),
        ("мультяшный «пиу»", lambda: mix((F.pew(2200, 400, 0.2), 0), (F.pew(2600, 500, 0.2), 0.2), (F.sparkle_dust(r, 6, 0.3), 0.3, 0.5))),
        ("барабан револьвера + выстрел", lambda: mix((F.revolver_spin(r, 9), 0), (shot(), 0.55))),
        ("выстрел в зале + бас-дроп", lambda: mix((dsp.reverb(shot(), 2.4, 0.4), 0), (dsp.sub808(H(A2 - 12), 1.2, 2.0, 2.5), 0.05, 0.7))),
        ("осечка, перезарядка, выстрел", lambda: mix((F.dry_fire(r), 0), (F.dry_fire(r), 0.18), (F.gun_cock_long(r), 0.4), (shot(), 0.8), (F.casings(r, 1, 1.0), 0))),
    ]


def uzi(r):
    return [
        ("длинная очередь + дождь гильз", lambda: mix((F.burst(r, 14, 15), 0), (F.casings(r, 8, 0.2), 0))),
        ("две короткие очереди", lambda: mix((F.burst(r, 3, 16), 0), (F.burst(r, 3, 16), 0.38), (F.casings(r, 4, 0.2), 0))),
        ("очередь + золотые монеты", lambda: mix((F.burst(r, 8, 15), 0), (F.coin_pile(r, 20, 0.8), 0.45, 0.8))),
        ("очередь с глушителем", lambda: mix(*[(F.silenced(r), k / 13, 0.8) for k in range(9)], (F.casings(r, 5, 0.3), 0, 0.6))),
        ("очередь + раскат", lambda: F.outdoor_tail(F.burst(r, 10, 14, 0.9), r, 1.8, 0.7)),
        ("8-битная очередь", lambda: dsp.crush(F.burst(r, 10, 14), 5, 6)),
        ("взвод + гильзы, без стрельбы", lambda: mix((F.gun_cock_long(r), 0), (F.casings(r, 6, 0.4), 0), (F.sparkle_dust(r, 10, 0.6, 4000, 9000), 0.4, 0.6))),
        ("очередь с рикошетами", lambda: mix((F.burst(r, 9, 15), 0), (F.ricochet(r, 4200), 0.25, 0.6), (F.ricochet(r, 3300), 0.5, 0.5))),
        ("очередь + трэп 808", lambda: mix((F.burst(r, 6, 16), 0), (dsp.sub808(H(A2 - 12), 1.3, 1.8, 2.5), 0.4, 0.8), (dsp.clap(0.3, r), 0.4, 0.5))),
        ("веер очереди + золотой аккорд", lambda: mix((F.burst(r, 16, 17, 0.6), 0), (stab(MAJ + [A5], "strings", 1.4, r), 0.8, 0.6), (F.sparkle_dust(r, 12, 0.8), 0.85, 0.5))),
    ]


def bat(r):
    return [
        ("замах + удар деревом", lambda: mix((F.swing(r), 0), (F.wood_crack(r), 0.25))),
        ("хоумран + трибуны", lambda: mix((F.wood_crack(r), 0), (F.crowd_cheer(r, 2.2), 0.1, 0.6))),
        ("два промаха и попадание", lambda: mix((F.swing(r, 0.22), 0), (F.swing(r, 0.22), 0.3), (F.swing(r, 0.25), 0.62), (F.punch(r, 1.2), 0.85), (F.wood_crack(r), 0.85, 0.7))),
        ("алюминиевая бита «пинг»", lambda: mix((F.swing(r), 0), (F.alu_ping(r), 0.25))),
        ("удар + разбитое стекло", lambda: mix((F.swing(r), 0), (F.wood_crack(r), 0.25), (F.glass_smash(r, 1.0), 0.27, 0.8))),
        ("постукивание по ладони", lambda: mix((F.wood_crack(r, 0.7) * 0.5, 0), (F.wood_crack(r, 0.7) * 0.5, 0.45), (F.swing(r), 0.8), (F.punch(r, 1.3), 1.05))),
        ("мультяшный «бонк»", lambda: mix((F.swing(r, 0.2), 0), (F.bonk(), 0.2), (F.bonk(700, 1500, 0.2), 0.42, 0.6))),
        ("киношный удар с бумом", lambda: mix((F.swing(r, 0.35, 200, 1200), 0), (F.wood_crack(r), 0.33), (dsp.sub808(H(A2 - 12), 0.9, 1.6, 3.0), 0.33, 0.8), (dsp.crash(1.0, r), 0.33, 0.15))),
        ("бита по асфальту + удар", lambda: mix((F.scrape(r, 0.7), 0), (F.swing(r), 0.75), (F.wood_crack(r), 1.0))),
        ("удар + стадионный орган", lambda: mix((F.wood_crack(r), 0), (mix(*[(dsp.organ(H(m), 0.18, r), k * 0.16) for k, m in enumerate([A4, A4 + 4, A4 + 7, A5, A4 + 7, A5])]), 0.2, 0.7))),
    ]


def knuckles(r):
    return [
        ("свист + удар в корпус", lambda: mix((F.swing(r, 0.15, 600, 2500), 0), (F.punch(r, 1.0), 0.12))),
        ("двоечка", lambda: mix((F.swing(r, 0.12, 700, 2600), 0), (F.punch(r, 0.8), 0.1), (F.swing(r, 0.14, 500, 2200), 0.25), (F.punch(r, 1.2), 0.37))),
        ("кастет на пальцы + удар", lambda: mix((F.metal_ring(2200, 0.4) * 0.3, 0), (F.metal_ring(2500, 0.4) * 0.25, 0.12), (F.swing(r, 0.15), 0.35), (F.punch(r, 1.1), 0.48), (F.metal_ring(1500, 0.8) * 0.3, 0.48))),
        ("апперкот с хрустом", lambda: mix((F.swing(r, 0.2, 300, 2000), 0), (F.punch(r, 1.3), 0.18), (F.bone_crack(r), 0.19, 0.7))),
        ("комикс «POW»", lambda: mix((F.punch(r, 1.0), 0), (F.bonk(300, 900, 0.3), 0, 0.6), (dsp.zap(1200, 3000, 0.2, "square") * 0.2, 0.05))),
        ("тяжёлый удар + звон металла", lambda: mix((F.swing(r, 0.15), 0), (F.punch(r, 1.4), 0.12), (F.metal_ring(1300, 1.2) * 0.5, 0.12))),
        ("слоу-мо удар", lambda: mix((dsp.whoosh(0.6, 150, 900, 1.2, r), 0, 0.9), (dsp.sub808(H(A2 - 12), 1.2, 1.4, 2.0), 0.55), (F.punch(r, 1.5), 0.55, 0.8))),
        ("гонг ринга + удар", lambda: mix((F.boxing_bell(r), 0, 0.7), (F.swing(r, 0.15), 0.35), (F.punch(r, 1.1), 0.47))),
        ("хруст костяшек + удар", lambda: mix((F.knuckle_crack(r), 0), (F.swing(r, 0.15), 0.4), (F.punch(r, 1.2), 0.52))),
        ("удар в реверб + 808", lambda: mix((dsp.reverb(F.punch(r, 1.2), 2.0, 0.45), 0), (dsp.sub808(H(A2 - 12), 1.0, 1.8, 2.5), 0, 0.7), (dsp.clap(0.3, r), 0.25, 0.4))),
    ]


def queen(r):
    return [
        ("арфа-глиссандо + блёстки", lambda: mix((F.harp_gliss(r, A4, True, 14), 0), (F.sparkle_dust(r, 12, 0.8), 0.35, 0.6))),
        ("сокровища короны + хор", lambda: mix((F.sparkle_dust(r, 16, 0.9, 4000, 9000), 0), (stab([A4, A4 + 4, A4 + 7], "choir", 1.4, r), 0.05, 0.8))),
        ("королевские трубы", lambda: mix(*[(stab([m, m + 7], "brass", d, r), t) for t, m, d in ((0, A4, 0.16), (0.18, A4, 0.16), (0.36, A4 + 4, 0.16), (0.54, A4 + 7, 0.7))], (dsp.timpani(H(A2), 1.0, r), 0.54, 0.6))),
        ("каскад бриллиантов", lambda: mix(*[(dsp.bell(H(A6 + 7 - k), 0.6, 2.7, 1.4, 0.25) * 0.5, k * 0.06) for k in range(12)])),
        ("томный саксофон", lambda: mix((F.sax(A4 + 7, 0.25, r), 0), (F.sax(A4 + 4, 0.25, r), 0.24), (F.sax(A5, 0.8, r), 0.48))),
        ("поцелуй + колокольчики", lambda: mix((F.kiss(r), 0), (stab([A5, A5 + 4, A5 + 7], "bells", 1.0, r), 0.25, 0.6))),
        ("струнные + стеклянная арфа", lambda: mix((stab([A3, A4, A4 + 4, A4 + 7], "strings", 1.4, r), 0, 0.8), (F.harp_gliss(r, A5, True, 10, 0.05), 0.3, 0.5))),
        ("шаги на каблуках + аккорд", lambda: mix((F.heel_steps(r, 3, 0.2), 0), (stab([A4, A4 + 4, A4 + 11], "epiano", 1.0, r), 0.62))),
        ("пшик духов + блеск", lambda: mix((F.spray(r, 0.35), 0), (F.sparkle_dust(r, 10, 0.7), 0.2), (stab(MAJ, "bells", 1.0, r), 0.3, 0.4))),
        ("шкатулка-челеста", lambda: F.celesta([A5, A5 + 4, A5 + 7, A6, A5 + 11, A6 + 4], 0.13, r)),
    ]


def diva(r):
    return [
        ("пробка шампанского + шипение", lambda: mix((F.cork_pop(r), 0), (F.fizz(r, 1.2), 0.05, 0.8), (stab(MAJ, "bells", 1.0, r), 0.1, 0.4))),
        ("вокал дивы", lambda: mix((F.solo_voice(A5 + 4, 1.3, "a", r), 0), (stab(MAJ, "strings", 1.3, r), 0, 0.4))),
        ("вспышки папарацци", lambda: mix(*[(F.camera_flash(r), t, g) for t, g in ((0, 1.0), (0.18, 0.8), (0.3, 0.9), (0.55, 0.7))], (F.sparkle_dust(r, 8, 0.5), 0.6, 0.4))),
        ("помада и поцелуй", lambda: mix((F.cork_pop(r) * 0.5, 0), (F.kiss(r), 0.3), (F.harp_gliss(r, A5, True, 6, 0.04), 0.5, 0.5))),
        ("шорох меха + джазовый аккорд", lambda: mix((dsp.whoosh(0.5, 500, 2500, 0.8, r) * 0.6, 0), (stab([A3 + 3, A3 + 7, A3 + 10, A4 + 2], "epiano", 1.3, r), 0.25))),
        ("софит + блеск", lambda: mix((F.slam(r, 0.8) * 0.6, 0), (dsp.reverse_swell(stab(MAJ, "choir", 0.9, r)), 0.05, 0.6), (F.sparkle_dust(r, 10, 0.8), 0.1, 0.5))),
        ("звон бокалов", lambda: mix((F.glass_clink(r, 2900), 0), (F.glass_clink(r, 3300), 0.15, 0.8), (F.fizz(r, 0.8), 0.1, 0.4))),
        ("труба с сурдиной «уа-уа»", lambda: mix((F.muted_trumpet(A4 + 7, 0.3, r), 0), (F.muted_trumpet(A4 + 4, 0.3, r), 0.3), (F.muted_trumpet(A5, 0.7, r), 0.6))),
        ("диско-струнные", lambda: mix(*[(stab([m, m + 12], "strings", 0.14, r), k * 0.07) for k, m in enumerate([A4, A4 + 4, A4 + 7, A5, A5 + 4, A5 + 7])], (stab(MAJ, "strings", 1.0, r), 0.45, 0.6))),
        ("каблуки + шум вечеринки", lambda: mix((F.heel_steps(r, 2, 0.2), 0), (F.crowd_cheer(r, 1.4) * 0.5, 0.35), (stab(MAJ, "epiano", 0.9, r), 0.35, 0.5))),
    ]


def boss(r):
    return [
        ("медный удар + бас-дроп", lambda: mix((stab([A2, A2 + 7, A3], "brass", 0.9, r), 0), (dsp.sub808(H(A2 - 12), 1.4, 2.0, 2.5), 0, 0.8))),
        ("зажигалка + выдох + аккорд", lambda: mix((F.lighter(r), 0), (F.exhale(r, 0.9), 0.5, 0.8), (stab(MIN, "strings", 1.4, r), 0.6, 0.6))),
        ("замки кейса + монеты", lambda: mix((F.latch(r), 0), (F.coin_pile(r, 20, 0.7), 0.3, 0.9))),
        ("пачка денег на стол + касса", lambda: mix((F.money_thud(r), 0), (dsp.register(r), 0.15, 0.8))),
        ("оркестровый удар", lambda: F.orch_hit(A2, r, True)),
        ("удар по столу «по рукам»", lambda: mix((F.slam(r, 1.3), 0), (stab([A2, A2 + 7], "brass", 0.7, r), 0.02, 0.7))),
        ("крёстный отец — орган", lambda: mix((stab([A2, A3, A3 + 3, A3 + 7], "organ", 1.4, r), 0), (dsp.timpani(H(A2), 1.4, r), 0, 0.6))),
        ("скретч + 808 бум", lambda: mix((dsp.vinyl_scratch(0.35, r, 800), 0), (dsp.sub808(H(A2 - 12), 1.2, 1.5, 2.8), 0.3), (dsp.clap(0.3, r), 0.3, 0.4))),
        ("дверь лимузина + мотор", lambda: mix((F.slam(r, 1.0), 0), (F.engine_rev(r, 1.4), 0.25, 0.7))),
        ("дверь сейфа + золото", lambda: mix((F.vault_clunk(r), 0), (F.coin_pile(r, 24, 0.9), 0.2, 0.7), (stab(MAJ, "bells", 1.0, r), 0.3, 0.4))),
    ]


def hustler(r):
    return [
        ("пересчёт купюр + «дзынь»", lambda: mix((F.bills_flip(r, 16, 22), 0), (dsp.register(r), 0.75, 0.8))),
        ("бросок костей + победа", lambda: mix((dsp.dice(r, 6), 0), (stab(MAJ, "brass", 0.6, r), 0.55, 0.7))),
        ("фанковый слэп-бас", lambda: mix(*[(dsp.pluck(H(m), 0.14, 3500, 4.0, 0.06, "square"), t) for t, m in ((0, A2), (0.12, A2 + 12), (0.3, A2 + 10), (0.42, A2 + 7), (0.54, A3))])),
        ("тасовка + открытая карта", lambda: mix((F.card_shuffle(r, 0.6), 0), (F.card_flip(r), 0.7), (stab(MAJ, "epiano", 0.9, r), 0.75, 0.5))),
        ("монеты в кармане", lambda: mix((F.jingle(r, 0.8), 0), (stab([A4 + 4, A4 + 7], "bells", 0.8, r), 0.5, 0.4))),
        ("щелчки пальцами + стэб", lambda: mix((F.snap(r), 0), (F.snap(r), 0.25), (stab([A3 + 3, A3 + 7, A3 + 10], "brass", 0.4, r), 0.5))),
        ("присвист + касса", lambda: mix((F.catcall(r), 0), (dsp.register(r), 0.8, 0.7))),
        ("резинка с пачки + шелест", lambda: mix((F.band_snap(r), 0), (F.bills_flip(r, 8, 18), 0.12))),
        ("стопка фишек + выигрыш", lambda: mix((F.chips_stack(r, 8), 0), (F.coin_pile(r, 10, 0.4), 0.5, 0.5))),
        ("токбокс-рифф", lambda: mix((F.talkbox(A3 + 7, 0.25, "u", "a", r), 0), (F.talkbox(A3 + 10, 0.25, "o", "e", r), 0.25), (F.talkbox(A4, 0.5, "u", "a", r), 0.5))),
    ]


def wild(r):
    return [
        ("сирена + тяжёлый удар", lambda: mix((F.siren(r, 1.0, "wail"), 0, 0.8), (F.slam(r, 1.4), 0.9))),
        ("звонок тревоги + бум", lambda: mix((F.alarm_bell(r, 0.9), 0), (dsp.sub808(H(A2 - 12), 1.1, 1.5, 2.5), 0.8))),
        ("разбитая витрина + тревога", lambda: mix((F.glass_smash(r, 1.0), 0), (F.alarm_bell(r, 0.8), 0.4, 0.7))),
        ("взлом сейфа + бум", lambda: mix((F.safe_dial(r, 7, 0.07), 0), (F.explosion(r, 1.4), 0.6, 0.8))),
        ("визг шин + мотор", lambda: mix((F.tire_screech(r, 0.8), 0), (F.engine_rev(r, 1.2), 0.5, 0.8))),
        ("тревожный стэб + выстрел", lambda: mix((stab([A3, A3 + 1, A3 + 6], "strings", 0.7, r), 0, 0.8), (F.gunshot(r, 1.0), 0.45))),
        ("шпионский серф-рифф", lambda: F.surf_guitar([A2 + 7, A2 + 8, A2 + 7, A2 + 6, A2 + 7, A3 + 7], 0.11, r)),
        ("мешок денег об пол", lambda: mix((F.bag_drop(r), 0), (stab(MAJ, "brass", 0.6, r), 0.25, 0.6))),
        ("взрыв динамита", lambda: F.explosion(r, 2.0)),
        ("вертолёт + удар", lambda: mix((F.rotor(r, 1.4), 0, 0.9), (F.slam(r, 1.2), 1.2))),
    ]


def scatter(r):
    return [
        ("код сейфа + щелчок + скрип двери", lambda: mix((F.safe_dial(r, 6), 0), (F.vault_clunk(r), 0.45), (F.creak(r, 0.9), 0.75, 0.7))),
        ("дверь хранилища + золотой хор", lambda: mix((F.vault_clunk(r), 0), (stab(MAJ, "choir", 1.6, r), 0.3, 0.8), (F.sparkle_dust(r, 12, 1.0), 0.35, 0.5))),
        ("засовы один за другим + блеск", lambda: mix(*[(F.latch(r), k * 0.16, 0.8) for k in range(4)], (F.sparkle_dust(r, 12, 0.8), 0.65, 0.6))),
        ("лазерная сетка отключена", lambda: mix((F.laser_beeps(r), 0), (F.hydraulic(r, 0.5), 0.5, 0.6), (F.vault_clunk(r), 0.9, 0.8))),
        ("код на клавиатуре + успех", lambda: mix((F.keypad(), 0), (F.keypad((1477, 1633)), 0.48, 0.8), (stab([A5, A5 + 4, A5 + 7], "bells", 1.0, r), 0.75, 0.6))),
        ("огромный гонг + золото", lambda: mix((F.gong(r, 98, 2.6), 0), (F.coin_pile(r, 16, 0.8), 0.2, 0.5))),
        ("сокровище: арфа + хор + монеты", lambda: mix((F.harp_gliss(r, A4, True, 12), 0), (stab(MAJ, "choir", 1.4, r), 0.3, 0.7), (F.coin_pile(r, 18, 0.9), 0.35, 0.6))),
        ("гидравлика + щелчок", lambda: mix((F.hydraulic(r, 0.8), 0), (F.vault_clunk(r), 0.7))),
        ("сердце → замок → фанфара", lambda: mix((dsp.sub808(36.0, 0.25, 1.2, 1.6), 0), (dsp.sub808(36.0, 0.25, 1.2, 1.6), 0.25, 0.7), (F.vault_clunk(r), 0.6), (stab([A4, A4 + 4, A4 + 7], "brass", 0.9, r), 0.75, 0.8))),
        ("удар двери + эхо + искры", lambda: mix((dsp.reverb(F.slam(r, 1.5), 2.5, 0.5), 0), (F.sparkle_dust(r, 14, 1.0), 0.2, 0.6))),
    ]


DESIGNS = {
    "common_4": glock, "common_2": uzi, "common_1": bat, "common_3": knuckles,
    "rare_purple": queen, "rare_yellow": diva, "rare_blue": boss, "rare_green": hustler,
    "wild": wild, "scatter": scatter,
}


def render(code: str, i: int, r):
    name, fn = DESIGNS[code](r)[i]
    return name, F.finish(fn(), r)
