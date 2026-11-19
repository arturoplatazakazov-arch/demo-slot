"""Gangsta Casino sound pack v2: 10 RADICALLY different variants per event.

    <venv with numpy scipy lameenc>/bin/python scripts/gc_sound/pack.py [event ...]

v1 drew every variant from the same melody and rhythm with a different timbre,
and product found the sets too alike to compare. Here every variant of an
event is a different IDEA:
  * melodic events: a different instrument AND a different motif (rising,
    falling, octave leap, fanfare, trill, run, blues…) AND different effects
    (dry, hall, echo, lo-fi, reverse swell, tape stop, chorus…);
  * percussive events (clicks, stops, landings): a different object
    (808, metal, wood, glass, scratch, gun cock, register, dice, conga…);
  * risers / transitions: a different riser type;
  * loops: a different concept (ratchet, motor, roulette, heartbeat, siren…);
  * win fanfares and music: a different GENRE per variant (rock, trap, funk,
    latin, jazz, disco, chiptune, noir orchestra, synthwave, lo-fi).
Writes front/sound/gangsta-casino/<event>/v01..v10.(mp3|wav), manifest.json
({event: [paths]}) and names.json ({event: [variant names]}) for the panel.
Everything stays in A (minor, major for wins). Seeded: same files every run.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dsp  # noqa: E402
from dsp import SR, mix, n_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "front"
OUT = ROOT / "sound" / "gangsta-casino"

A1, A2, A3, A4, A5, A6 = 33, 45, 57, 69, 81, 93
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
PENTA = [0, 3, 5, 7, 10]


def deg(scale, d, root):
    o, i = divmod(d, len(scale))
    return root + scale[i] + 12 * o


def H(m):
    return dsp.hz(float(m))


def _choir(m, d, r):
    dd = max(d, 0.25)
    return dsp.choir(H(m), dd, "a" if d >= 0.25 else "o", 4, r)[: n_of(d)]


# --- instruments: name, fn(midi, dur, rng), octave shift ----------------------
INSTS = [
    ("Гитара", lambda m, d, r: dsp.guitar(H(m), d, 0.55, r), 0),
    ("Рок-гитара", lambda m, d, r: dsp.dist_guitar(H(m), d, True, r), -12),
    ("Хор", _choir, 0),
    ("Свист", lambda m, d, r: dsp.whistle(H(m), d, r), 12),
    ("Орган", lambda m, d, r: dsp.organ(H(m), d, r), 0),
    ("Струнные", lambda m, d, r: dsp.strings(H(m), max(d, 0.2), r), 0),
    ("Маримба", lambda m, d, r: dsp.marimba(H(m), max(d, 0.3)), 0),
    ("Стил-драм", lambda m, d, r: dsp.steel_drum(H(m), max(d, 0.35)), 0),
    ("Чиптюн", lambda m, d, r: dsp.chip(H(m), d, 0.25) * dsp.env_exp(d, max(0.06, d * 0.8)), 12),
    ("Медь", lambda m, d, r: dsp.brass([H(m), H(m) * 1.5], max(d, 0.15), 2400, 0.02, r), 0),
    ("808-бас", lambda m, d, r: dsp.sub808(H(m), max(d, 0.3), 1.5, 2.2), -24),
    ("Синт-лид", lambda m, d, r: dsp.lead(H(m), d, r), 0),
    ("Электропиано", lambda m, d, r: dsp.epiano(H(m), max(d, 0.3), max(0.15, d * 0.6)), 0),
    ("Калимба", lambda m, d, r: dsp.kalimba(H(m), max(d, 0.35)), 12),
    ("Колокола", lambda m, d, r: dsp.bell(H(m), max(d, 0.4), 1.4142, 2.0, max(0.2, d * 0.8)), 12),
    ("Лазер", lambda m, d, r: dsp.fm(dsp.sweep(H(m) * 1.5, H(m), d), 0.5, 5 * dsp.env_exp(d, 0.06), d) * dsp.env_exp(d, max(0.05, d * 0.5)), 0),
]


def note(inst, m, dur, r, vel=1.0):
    name, fn, sh = INSTS[inst]
    x = np.asarray(fn(m + sh, dur, r))
    return dsp.fade(x * vel, 0.0008, min(0.02, len(x) / SR * 0.2))


# --- motifs: (beat position, scale degree, length in beats) -------------------
MOTIFS = [
    ("вверх", [(0, 0, 1), (1, 2, 1), (2, 4, 2)]),
    ("вниз", [(0, 7, 1), (1, 4, 1), (2, 2, 1), (3, 0, 2)]),
    ("октава", [(0, 0, 1), (1, 7, 3)]),
    ("фанфара", [(0, 4, 0.5), (0.5, 4, 0.5), (1, 4, 0.5), (1.5, 7, 2.5)]),
    ("трель", [(k * 0.25, k % 2, 0.25) for k in range(8)] + [(2, 2, 2)]),
    ("пробежка", [(k * 0.25, k, 0.3) for k in range(8)] + [(2, 8, 2)]),
    ("один удар", [(0, 0, 3)]),
    ("вопрос-ответ", [(0, 4, 0.5), (0.5, 5, 0.5), (1.5, 4, 0.5), (2, 0, 2)]),
    ("синкопа", [(0, 0, 0.5), (0.75, 2, 0.5), (1.5, 4, 0.5), (2.25, 7, 1.5)]),
    ("скачки", [(0, 7, 0.5), (0.5, 0, 0.5), (1, 7, 0.5), (1.5, 0, 0.5), (2, 9, 2)]),
    ("повтор", [(0, 4, 0.33), (0.33, 4, 0.33), (0.66, 4, 0.33), (1, 4, 2)]),
    ("блюз", [(0, 0, 0.5), (0.5, 1, 0.5), (1, 2, 0.5), (1.5, 3, 0.5), (2, 4, 2)]),
]
FX_HAPPY = ["сухо", "зал", "эхо", "лоу-фай", "реверс", "хорус", "перегруз", "широко"]
FX_SAD = ["сухо", "зал", "эхо", "лоу-фай", "лента", "хорус", "реверс", "перегруз"]


def apply_fx(x, fx, r):
    if fx == "зал":
        return dsp.reverb(x, 2.2, 0.35, 5000)
    if fx == "эхо":
        return dsp.delay(x, 0.16, 0.45, 0.5, 0.9)
    if fx == "лоу-фай":
        y = dsp.lp(dsp.crush(x, 7, 3), 3500)
        return y + dsp.hp(dsp.noise(len(y) / SR, r), 3000) * 0.01
    if fx == "реверс":
        return dsp.reverse_swell(x)
    if fx == "лента":
        return dsp.tape_stop(np.concatenate([x, np.zeros(n_of(0.2))]), 0.35)
    if fx == "хорус":
        return dsp.chorus(x)
    if fx == "перегруз":
        return dsp.lp(dsp.drive(x * 2.5, 3.0), 6000)
    if fx == "широко":
        return dsp.reverb(dsp.delay(x, 0.11, 0.3, 0.3, 0.5), 1.2, 0.2)
    return dsp.reverb(x, 0.5, 0.08)  # сухо: just a room


def play_motif(inst, motif, mood, beat, root, r, vel=0.9, chord_end=False):
    _, steps = MOTIFS[motif]
    scale = MAJOR if mood == "happy" else MINOR if mood == "sad" else PENTA
    parts = []
    for pos, d, ln in steps:
        dd = (len(scale) - d) if mood == "sad" else d  # sad: the motif mirrored downwards
        parts.append((note(inst, deg(scale, dd, root), ln * beat, r, vel), pos * beat))
    if chord_end:
        last = steps[-1][0] * beat
        for c in ([0, 4, 7] if mood == "happy" else [0, 3, 7]):
            parts.append((note(inst, root + c, beat * 2, r, 0.35), last))
    return mix(*parts)


# --- percussive objects: name, fn(size, r) -------------------------------------
def _metal(s, r):
    return mix((dsp.coin(900 + 500 * s, 0.4, r, 1.6), 0), (dsp.lp(dsp.noise(0.05, r), 3000) * dsp.env_exp(0.05, 0.01), 0, 0.5))


TEXTURES = [
    ("808", lambda s, r: dsp.sub808(30.0 + 8 * s, 0.25 + 0.4 * s, 1.8, 2.5)),
    ("металл", _metal),
    ("дерево", lambda s, r: dsp.wood_block(900 + 500 * (1 - s), 0.15)),
    ("стекло", lambda s, r: dsp.bell(2600.0 + 600 * s, 0.4, 2.7, 1.2, 0.12)),
    ("скретч", lambda s, r: dsp.vinyl_scratch(0.12 + 0.2 * s, r, 700 + 300 * s)),
    ("затвор", lambda s, r: dsp.gun_cock(r)),
    ("касса", lambda s, r: dsp.register(r)[: n_of(0.25 + 0.6 * s)]),
    ("чип-блип", lambda s, r: mix((dsp.chip(H(A5 + 12 * s), 0.06, 0.5), 0), (dsp.crush(dsp.noise(0.04, r) * dsp.env_exp(0.04, 0.01), 4, 6), 0, 0.5))),
    ("том", lambda s, r: dsp.osc("sine", dsp.sweep(260 - 80 * s, 80, 0.4), 0.4) * dsp.env_exp(0.4, 0.12)),
    ("хлопок", lambda s, r: dsp.clap(0.25, r)),
    ("конга", lambda s, r: dsp.conga(330 - 120 * s, 0.3, r)),
    ("кубики", lambda s, r: dsp.dice(r, 3 + int(3 * s))),
    ("пузырь", lambda s, r: dsp.bubble(250 + 200 * s, 1200 + 800 * s, 0.1)),
    ("каубелл", lambda s, r: dsp.cowbell(0.25)),
    ("фишки", lambda s, r: mix((dsp.chip_clack(0.1, 2300, r), 0), (dsp.chip_clack(0.08, 2800, r), 0.025, 0.6), (dsp.chip_clack(0.08, 2000, r), 0.05, 0.4))),
    ("лазер", lambda s, r: dsp.zap(2600, 180 + 200 * (1 - s), 0.18 + 0.1 * s, "sine")),
    ("литавра", lambda s, r: dsp.timpani(H(A2), 0.6 + 0.6 * s, r)),
    ("бочка", lambda s, r: dsp.kick(0.35, 120 + 60 * s, 45, 1.0)),
]


# --- risers / transitions: name, fn(dur, up, r) ---------------------------------
def _ramp(d, up):
    return np.linspace(0.15, 1, n_of(d)) if up else np.linspace(1, 0.15, n_of(d))


def _bell_curve(d):
    return np.sin(np.linspace(0, np.pi, n_of(d)))


RISERS = [
    ("шум-свуш", lambda d, up, r: dsp.whoosh(d, 300 if up else 5000, 5000 if up else 300, 1.6, r)),
    ("шепард", lambda d, up, r: dsp.lp(dsp.shepard(d, 110, 6, 1.5 / d, up, "saw"), 4000) * 0.5 * _ramp(d, up)),
    ("реверс-тарелка", lambda d, up, r: dsp.pad_to(dsp.crash(d, r)[::-1], n_of(d)) if up else dsp.crash(d, r)),
    ("перемотка ленты", lambda d, up, r: dsp.bp_sweep(dsp.noise(d, r), dsp.sweep(600, 4000, d) if up else dsp.sweep(4000, 300, d), 6) * 1.5),
    ("лазер-свип", lambda d, up, r: dsp.osc("square", dsp.sweep(200, 3000, d) if up else dsp.sweep(3000, 150, d), d) * 0.25 * _bell_curve(d)),
    ("хор-нарастание", lambda d, up, r: dsp.choir(H(A3 + (0 if up else 7)), d, "o" if up else "u", 5, r) * _ramp(d, up)),
    ("гитарный слайд", lambda d, up, r: dsp.drive(dsp.osc("saw", dsp.sweep(110, 880, d) if up else dsp.sweep(660, 82, d), d) * 2, 3) * 0.3 * _bell_curve(d)),
    ("барабанная дробь", lambda d, up, r: mix(*[(dsp.snare(0.1, 200, r) * (0.2 + 0.8 * (k / (d * 24) if up else 1 - k / (d * 24))), k / 24, 0.6) for k in range(max(1, int(d * 24)))])),
    ("тремоло струнных", lambda d, up, r: dsp.strings(H(A3), d, r) * (0.6 + 0.4 * np.sin(2 * np.pi * 12 * dsp.tvec(d))) * _ramp(d, up)),
    ("пила с фильтром", lambda d, up, r: dsp.resonant_lp(dsp.supersaw(H(A2), d, 5, 0.3, r), dsp.sweep(200, 6000, d) if up else dsp.sweep(6000, 200, d), 6) * 0.6),
]


# --- per-event variant plan -----------------------------------------------------
# Every variant gets its own inst / motif / texture / riser (and mostly its own
# fx); spread with steps coprime to the list lengths, offset per event so
# variant A is not the same idea everywhere.

def _h(name):
    return sum(map(ord, name))


def plan(name, i, fxs):
    h = _h(name)
    return {
        "inst": (i * 3 + h) % len(INSTS),
        "motif": (i * 5 + h) % len(MOTIFS),
        "fx": fxs[(i * 3 + h // 7) % len(fxs)],
        "tex": (i * 7 + h) % len(TEXTURES),
        "riser": (i + h) % len(RISERS),
    }


NAMES: dict[str, list[str]] = {}


def name_of(event, i, label):
    NAMES.setdefault(event, [""] * 10)[i] = label


def melodic(mood, beat=0.12, size=0.6, root=A4, accent=True, chord_end=False, fxs=None):
    """One-shot: instrument x motif x fx (+ a percussive accent)."""
    fxs = fxs or (FX_SAD if mood == "sad" else FX_HAPPY)

    def f(event, i, r):
        pl = plan(event, i, fxs)
        parts = [(play_motif(pl["inst"], pl["motif"], mood, beat, root, r, chord_end=chord_end), 0)]
        if accent:
            parts.append((TEXTURES[pl["tex"]][1](size, r), 0, 0.6))
        y = apply_fx(mix(*parts), pl["fx"], r)
        name_of(event, i, f"{INSTS[pl['inst']][0]} · {MOTIFS[pl['motif']][0]} · {pl['fx']}")
        return y
    return f


def percussive(size=0.5, pitched=False, low=False):
    def f(event, i, r):
        pl = plan(event, i, FX_HAPPY)
        t = TEXTURES[pl["tex"]]
        parts = [(t[1](size, r), 0)]
        label = t[0]
        if pitched:
            parts.append((note(pl["inst"], A3 if low else A5, 0.18, r, 0.5), 0.005))
            label += f" + {INSTS[pl['inst']][0].lower()}"
        name_of(event, i, label)
        return mix(*parts)
    return f


def riser_event(dur=0.6, up=True, mood="happy", hit=True, chord=True):
    def f(event, i, r):
        pl = plan(event, i, FX_HAPPY)
        rz = RISERS[pl["riser"]]
        parts = [(rz[1](dur, up, r), 0, 0.8)]
        if hit:
            parts.append((TEXTURES[pl["tex"]][1](1.0, r), dur * 0.95, 0.8))
        if chord:
            for c in ([0, 4, 7, 12] if mood == "happy" else [0, 3, 7]):
                parts.append((note(pl["inst"], A3 + c, 1.2 if up else 0.9, r, 0.4), dur * 0.95))
        label = f"{rz[0]}" + (f" · {INSTS[pl['inst']][0].lower()}" if chord else "") + (f" · {TEXTURES[pl['tex']][0]}" if hit else "")
        name_of(event, i, label)
        return dsp.reverb(mix(*parts), 1.4, 0.2)
    return f


# --- loops ----------------------------------------------------------------------

def loop_reel(event, i, r):
    d = 2.0
    st = d / 16
    concepts = [
        ("храповик", lambda k: dsp.chip_clack(0.04, 2600 if k % 2 else 2100, r)),
        ("мотор", None),
        ("рулетка", "roulette"),
        ("чип-тики", lambda k: dsp.chip(H(A6 if k % 4 == 0 else A5 + 7), 0.04, 0.5)),
        ("хай-хэт грув", lambda k: dsp.hat(0.05, r, open_=(k % 8 == 6))),
        ("шейкер", lambda k: dsp.shaker(0.09, r)),
        ("синт-пульс", lambda k: dsp.pluck(H(A3 + (12 if k % 4 == 2 else 0)), st, 1800, 3.0, 0.05)),
        ("часы", lambda k: dsp.wood_block(1800 if k % 4 == 0 else 1300, 0.06) if k % 2 == 0 else np.zeros(10)),
        ("конги", lambda k: dsp.conga([330, 250, 330, 200][k % 4], 0.2, r) if k % 2 == 0 else dsp.shaker(0.05, r) * 0.5),
        ("аркада", lambda k: dsp.bubble(400 + 90 * (k * 7 % 12), 900 + 120 * (k * 5 % 9), 0.05)),
    ]
    c = concepts[i]
    name_of(event, i, c[0])
    if c[1] is None:  # motor hum
        t = dsp.tvec(d + 0.5)
        x = dsp.lp(dsp.osc("saw", 55 * (1 + 0.01 * np.sin(2 * np.pi * 2 * t)), d + 0.5), 600) * 0.4 + dsp.lp(dsp.noise(d + 0.5, r, "pink"), 900) * 0.5
        x *= 0.85 + 0.15 * np.sin(2 * np.pi * 8 * t)
    elif c[1] == "roulette":
        x = dsp.roulette(d + 0.3, r)
    else:
        x = mix(*[(c[1](k), k * st, 1.0 if k % 4 == 0 else 0.6) for k in range(16)])
    return dsp.loopify(x, n_of(d))


def loop_anticipation(event, i, r):
    d = 4.0
    concepts = ["шепард", "сердцебиение", "барабанная дробь", "тремоло струнных", "тикающие часы",
                "сирена", "хор-пульс", "808-роллы", "трель органа", "гитарное тремоло"]
    k = i
    name_of(event, i, concepts[k])
    D = d + 0.6
    T = dsp.tvec(D)
    if k == 0:
        x = dsp.lp(dsp.shepard(D, 110, 6, 1 / d, True, "saw"), 3000) * 0.7
    elif k == 1:
        x = mix(*[(dsp.sub808(36.0, 0.25, 1.2, 1.6), b * 0.5 + o, g) for b in range(8) for o, g in ((0, 1.0), (0.17, 0.7))],
                (dsp.lp(dsp.noise(D, r, "pink"), 300) * 0.15, 0))
    elif k == 2:
        x = mix(*[(dsp.snare(0.08, 200, r), j / 20, 0.5 + 0.3 * (j % 2)) for j in range(int(d * 20))])
    elif k == 3:
        x = dsp.strings(H(A3), D, r) * (0.55 + 0.45 * np.sin(2 * np.pi * 10 * T)) + dsp.strings(H(A3 + 1), D, r) * 0.4
    elif k == 4:
        x = mix(*[(dsp.wood_block(2200 if j % 2 else 1600, 0.08), j * 0.25, 1.0) for j in range(16)],
                (dsp.osc("sine", 55, D) * 0.2, 0))
    elif k == 5:
        x = dsp.lp(dsp.osc("saw", 700 + 300 * np.sin(2 * np.pi * T), D), 2500) * 0.4
    elif k == 6:
        x = dsp.choir(H(A3), D, "a", 6, r) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * T) ** 2) + dsp.choir(H(A3 + 3), D, "o", 4, r) * 0.5
    elif k == 7:
        rolls = []
        for beat_i in range(8):  # 8 half-second cells, rolls get faster on odd cells
            sub = 4 if beat_i % 2 == 0 else 8
            for j in range(sub):
                rolls.append((dsp.hat(0.04, r), beat_i * 0.5 + j * 0.5 / sub, 0.5))
        x = mix((dsp.sub808(33.0, D, 1.0, 1.8) * 0.6, 0), *rolls)
    elif k == 8:
        x = mix(*[(dsp.organ(H(A4 + (1 if j % 2 else 0)), 0.13, r), j * 0.125, 0.6) for j in range(32)])
    else:
        x = mix(*[(dsp.dist_guitar(H(A2), 0.12, True, r, mute=True), j * 0.125, 0.7) for j in range(32)])
    return dsp.loopify(x, n_of(d))


def loop_count(event, i, r):
    d = 1.0
    st = d / 16
    concepts = [
        ("поток монет", lambda k: dsp.coin(2800 + 350 * (k % 5), 0.15, r) * 0.6),
        ("тикер кассы", lambda k: dsp.wood_block(2600, 0.03) if k % 2 == 0 else dsp.coin(3600, 0.08, r) * 0.3),
        ("чип-арпеджио", lambda k: dsp.chip(H([A5, A5 + 4, A5 + 7, A6][k % 4]), st * 0.9, 0.25)),
        ("маримба-ролл", lambda k: dsp.marimba(H([A5, A5 + 4, A5 + 7, A5 + 4][k % 4]), 0.15)),
        ("щелчки счётчика", lambda k: dsp.chip_clack(0.03, 3000, r)),
        ("каскад колоколов", lambda k: dsp.bell(H(A6 - (k % 8)), 0.2, 3.5, 1.5, 0.08) * 0.6),
        ("трель свиста", lambda k: dsp.whistle(H(A5 + 7 + (k % 2) * 2), st, r) * 0.6),
        ("синт-арп", lambda k: dsp.pluck(H([A4, A5, A4 + 7, A5 + 4][k % 4]), st * 1.2, 3000, 3.0, 0.05)),
        ("стил-драм ролл", lambda k: dsp.steel_drum(H([A5, A5 + 7][k % 2]), 0.15) * 0.6),
        ("цифровые бипы", lambda k: dsp.osc("sine", 1760 + 220 * (k % 3), 0.03) * dsp.env_exp(0.03, 0.01)),
    ]
    c = concepts[i]
    name_of(event, i, c[0])
    return dsp.loopify(mix(*[(c[1](k), k * st) for k in range(16)]), n_of(d))


# --- genres: fanfares + music --------------------------------------------------
GENRES = [
    dict(name="синтвейв", base=100, bonus=124, kick="x...x...x...x...", snare="....x.......x...", hat="..x...x...x...x.",
         bass=("saw8", [0, 2, 4, 6, 8, 10, 12, 14]), chords="pad", lead=11, prog=[(0, "m"), (-4, "M"), (3, "M"), (-2, "M")], fx="зал"),
    dict(name="трэп", base=72, bonus=140, kick="x.....x...x.....", snare="........x.......", hat="x.x.x.x.xxx.x.xx",
         bass=("808", [0, 6, 10]), chords="choir", lead=14, prog=[(0, "m"), (0, "m"), (-4, "M"), (-5, "M")], fx="эхо"),
    dict(name="фанк", base=104, bonus=116, swing=0.12, kick="x..x..x...x..x..", snare="....x..o....x...", hat="xxxxxxxxxxxxxxxx",
         bass=("slap", [0, 3, 6, 7, 10, 14]), chords="scratch", lead=9, prog=[(0, "m7"), (5, "m7"), (0, "m7"), (-2, "M")], fx="сухо"),
    dict(name="латино", base=110, bonus=124, kick="x..x....x..x....", snare="......x.......x.", hat="", perc="latin",
         bass=("tumbao", [3, 6, 11, 14]), chords=12, lead=7, prog=[(0, "m"), (5, "m"), (-5, "M"), (0, "m")], fx="зал"),
    dict(name="джаз-лаунж", base=88, bonus=116, swing=0.33, kick="x.......x.......", snare="....o.......o...", hat="x..xx..xx..xx..x", brush=True,
         bass=("walk", [0, 4, 8, 12]), chords=12, lead=6, prog=[(0, "m7"), (5, "m7"), (-2, "7"), (3, "M7")], fx="зал"),
    dict(name="рок", base=120, bonus=140, kick="x.x...x.x.x.....", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
         bass=("pick8", [0, 2, 4, 6, 8, 10, 12, 14]), chords="power", lead=1, prog=[(0, "5"), (-4, "5"), (-2, "5"), (-5, "5")], fx="сухо"),
    dict(name="чиптюн", base=128, bonus=150, kick="x...x...x...x...", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.", chip=True,
         bass=("tri8", [0, 2, 4, 6, 8, 10, 12, 14]), chords=8, lead=8, prog=[(0, "m"), (-4, "M"), (-2, "M"), (0, "m")], fx="сухо"),
    dict(name="нуар-оркестр", base=80, bonus=112, kick="", snare="", hat="", timp=True,
         bass=("pizz", [0, 4, 8, 12]), chords=5, lead=9, prog=[(0, "m"), (-4, "M"), (5, "m"), (-5, "M")], fx="зал"),
    dict(name="диско", base=118, bonus=126, kick="x...x...x...x...", snare="....x.......x...", hat="..x...x...x...x.", openhat=True,
         bass=("octave", [0, 2, 4, 6, 8, 10, 12, 14]), chords=5, lead=3, prog=[(0, "m7"), (-2, "M"), (-4, "M7"), (-5, "M")], fx="широко"),
    dict(name="лоу-фай", base=80, bonus=96, swing=0.25, kick="x......x..x.....", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.", lofi=True,
         bass=("sine", [0, 7, 10]), chords=12, lead=13, prog=[(0, "m7"), (5, "m7"), (-4, "M7"), (-5, "7")], fx="лоу-фай"),
]
QUAL = {"m": [0, 3, 7], "M": [0, 4, 7], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10], "M7": [0, 4, 7, 11], "5": [0, 7, 12]}


class Track:
    def __init__(self, dur):
        self.buf = np.zeros((n_of(dur + 3), 2))

    def put(self, sig, t, gain=1.0, pn=0.0):
        s = dsp.pan(sig, pn) if sig.ndim == 1 else sig
        i = n_of(t)
        e = min(len(self.buf), i + len(s))
        if e > i:
            self.buf[i:e] += s[: e - i] * gain


def render_bars(g, bars, bpm, r, layers, melody, prog, tr, t0=0.0, happy_end=False):
    """`bars` bars of genre g into track tr from t0. layers ⊂ drums/bass/chords/lead/perc.
    melody: list of (beat, midi, beats) for the lead (None = improvised)."""
    beat = 60 / bpm
    st = beat / 4
    prog = prog or g["prog"]
    sw = g.get("swing", 0.0)

    def step_t(bar, k):
        return t0 + bar * 4 * beat + k * st + (sw * st if k % 2 else 0)

    kick = dsp.kick(0.4, 140, 45, 1.0, 0.3, r)
    snare = dsp.clap(0.3, r) if g["name"] in ("трэп", "диско") else dsp.snare(0.25, 190, r)
    if g.get("brush"):
        snare = dsp.lp(dsp.noise(0.2, r), 4000) * dsp.env_exp(0.2, 0.06) * 0.6
    hatc = dsp.hat(0.05, r)
    if g.get("chip"):
        kick, snare, hatc = dsp.crush(kick, 4, 4), dsp.crush(snare, 4, 4), dsp.crush(hatc, 4, 4)
    for bar in range(bars):
        root, q = prog[bar % len(prog)]
        if happy_end and bar == bars - 1:
            root, q = 0, "M"
        ch = [A3 + root + c for c in QUAL[q]]
        if "drums" in layers:
            for k in range(16):
                for pat, smp, gn, pn in ((g["kick"], kick, 0.75, 0), (g["snare"], snare, 0.5, 0), (g["hat"], hatc, 0.18, 0.25)):
                    if pat and pat[k] in "xo":
                        tr.put(smp, step_t(bar, k), gn * (0.5 if pat[k] == "o" else 1.0), pn)
            if g.get("openhat"):
                for k in (2, 6, 10, 14):
                    tr.put(dsp.hat(0.05, r, True), step_t(bar, k), 0.12, -0.2)
            if g.get("timp") and bar % 2 == 0:
                tr.put(dsp.timpani(H(A2 + root), 1.4, r), step_t(bar, 0), 0.6)
        if "perc" in layers and g.get("perc") == "latin":
            for j, k in enumerate((0, 3, 6, 10, 12)):
                tr.put(dsp.conga([300, 220, 300, 260, 200][j], 0.25, r), step_t(bar, k), 0.5, -0.3)
            for k in range(0, 16, 2):
                tr.put(dsp.shaker(0.07, r), step_t(bar, k), 0.15, 0.4)
            for k in (0, 4, 8, 12):
                tr.put(dsp.cowbell(0.2), step_t(bar, k), 0.12, 0.3)
        if "bass" in layers:
            kind, steps = g["bass"]
            ln = st * (16 / max(1, len(steps))) * 0.9
            for j, k in enumerate(steps):
                m = ch[0] - 12
                if kind == "walk":
                    m += [0, 3 if q.startswith("m") else 4, 7, 5][j % 4]
                if kind == "octave" and j % 2:
                    m += 12
                if kind == "tumbao":
                    m += [7, 0, 7, 0][j % 4]
                if kind == "808":
                    s = dsp.sub808(H(m - 12), ln * 2, 1.3, 2.0)
                elif kind == "sine":
                    s = dsp.osc("sine", H(m), ln) * dsp.adsr(ln, 0.01, 0.1, 0.8, 0.1)
                elif kind == "tri8":
                    s = dsp.osc("tri", H(m), ln) * dsp.adsr(ln, 0.002, 0.05, 0.8, 0.02)
                elif kind in ("pizz", "walk"):
                    s = dsp.guitar(H(m), ln * 1.2, 0.3, r)
                elif kind == "slap":
                    s = dsp.pluck(H(m), ln, 3500, 4.0, 0.08, "square")
                elif kind == "pick8":
                    s = dsp.dist_guitar(H(m - 12), ln, False, r, mute=True) * 0.5
                else:
                    s = dsp.resonant_lp(dsp.osc("saw", H(m), ln), 300 + 900 * dsp.env_exp(ln, 0.05), 2.0) * dsp.adsr(ln, 0.002, 0.05, 0.6, 0.03)
                tr.put(s, step_t(bar, k), 0.4)
        if "chords" in layers:
            c = g["chords"]
            if c == "pad":
                tr.put(dsp.pad([H(m + 12) for m in ch], 4 * beat + 0.4, 1600, r), step_t(bar, 0), 0.22)
            elif c == "choir":
                for m in ch[:3]:
                    tr.put(dsp.choir(H(m + 12), 4 * beat, "o", 3, r), step_t(bar, 0), 0.18)
            elif c == "scratch":
                for k in (2, 6, 10, 14):
                    for m in ch[:3]:
                        tr.put(dsp.guitar(H(m + 12), st * 1.2, 0.9, r) * dsp.env_exp(st * 1.2, 0.03), step_t(bar, k), 0.15, 0.3)
            elif c == "power":
                for k in range(0, 16, 2):
                    tr.put(dsp.dist_guitar(H(ch[0]), st * 2.1, True, r, mute=k % 4 != 0), step_t(bar, k), 0.3, -0.25)
            else:
                hits = (0, 6, 10) if g["name"] in ("латино", "джаз-лаунж") else (0, 8)
                for k in hits:
                    for m in ch:
                        tr.put(note(c, m + 12, 2 * beat, r, 0.35), step_t(bar, k), 0.6, 0.1)
        if "lead" in layers and melody is None:
            lr = np.random.default_rng(int(1000 * bpm) + bar)
            for k in range(0, 16, 2):
                if lr.random() < 0.5:
                    m = ch[int(lr.integers(0, min(3, len(ch))))] + 24
                    tr.put(note(g["lead"], m, st * 3, r, 0.35), step_t(bar, k), 0.8, -0.1)
    if melody:
        for b_pos, m, ln in melody:
            tr.put(note(g["lead"], m, ln * beat, r, 0.8), t0 + b_pos * beat, 0.9, 0.0)
    return bars * 4 * beat


FANFARE_MEL = [(0, A5, 0.5), (0.5, A5 + 4, 0.5), (1, A5 + 7, 0.5), (1.5, A5 + 12, 1.5), (3, A5 + 11, 0.5), (3.5, A5 + 12, 0.5),
               (4, A5 + 9, 0.5), (4.5, A5 + 7, 0.5), (5, A5 + 4, 0.5), (5.5, A5 + 7, 0.5), (6, A5 + 12, 2),
               (8, A5 + 12, 0.5), (8.5, A5 + 14, 0.5), (9, A5 + 16, 1), (10, A5 + 19, 2)]


def apply_fx_stereo(x, fx, r):
    if fx == "лоу-фай":
        return np.stack([dsp.lp(dsp.crush(x[:, c], 8, 2), 4500) for c in range(2)], 1)
    size, wet = {"зал": (2.0, 0.25), "эхо": (1.2, 0.2), "широко": (1.6, 0.22)}.get(fx, (0.8, 0.1))
    return dsp.reverb(x, size, wet, stereo=True)


def fanfare_event(intensity):
    def f(event, i, r):
        g = GENRES[i]
        bpm = g["bonus"]
        beat = 60 / bpm
        bars = 2 if intensity < 1.5 else 3
        tr = Track(bars * 4 * beat + 5)
        t0 = 0.0
        if intensity >= 2.5:
            tr.put(RISERS[(i * 3) % len(RISERS)][1](1.0, True, r), 0, 0.6)
            t0 = 1.0
        lift = 12 if intensity >= 2 else 0
        mel = [(b + t0 / beat, m + (lift if b >= 4 else 0), ln) for b, m, ln in FANFARE_MEL if b < bars * 4 - 1]
        prog = [(0, "M"), (5, "M"), (-5, "M"), (0, "M")]
        end_t = t0 + render_bars(g, bars, bpm, r, {"drums", "bass", "chords", "perc"}, mel, prog, tr, t0, happy_end=True)
        for c in (0, 4, 7, 12):
            tr.put(note(g["lead"], A4 + c, 1.4, r, 0.5), end_t, 0.7)
        tr.put(TEXTURES[(i * 7) % len(TEXTURES)][1](1.0, r), end_t, 0.6)
        tr.put(dsp.crash(1.3, r), end_t, 0.14)
        if intensity >= 2:
            for k in range(int(10 * intensity)):
                tr.put(dsp.coin(2800 + 160 * (k % 9), 0.3, r), end_t + 0.05 * k, 0.25, (k % 5 - 2) / 3)
        x = apply_fx_stereo(tr.buf[: n_of(end_t + 1.8)], g["fx"], r)
        name_of(event, i, g["name"])
        return x
    return f


def music_event(bonus):
    def f(event, i, r):
        g = GENRES[i]
        bpm = g["bonus"] if bonus else g["base"]
        beat = 60 / bpm
        bars = 16 if bpm <= 130 else 24  # fast tracks get more bars (~37-40 s either way)
        tr = Track(bars * 4 * beat + 3)
        for sec in range(bars // 4):
            layers = {"bass", "chords"}
            if bonus or sec >= 1:
                layers |= {"drums", "perc"}
            if sec >= 2 or (bonus and sec >= 1):
                layers |= {"lead"}
            render_bars(g, 4, bpm, r, layers, None, None, tr, sec * 16 * beat)
        total = bars * 4 * beat
        x = apply_fx_stereo(tr.buf, g["fx"], r)
        x = np.stack([dsp.loopify(x[:, c], n_of(total)) for c in range(2)], 1)
        if g.get("lofi"):
            rr = np.random.default_rng(3)
            crackle = (rr.random(len(x)) > 0.9993) * rr.uniform(-0.3, 0.3, len(x))
            x += np.stack([crackle, crackle], 1)
        name_of(event, i, f"{g['name']} · {bpm} bpm")
        return x
    return f


def scatter_land(k):
    """Same idea per letter for land 1/2/3 (a set), pitch rising per scatter."""
    def f(event, i, r):
        pl = plan("scatterLand", i, FX_HAPPY)
        m = [A5, A5 + 4, A5 + 7][k - 1]
        x = mix((note(pl["inst"], m, 0.45, r, 0.9), 0), (note(pl["inst"], m + 12, 0.35, r, 0.35), 0.04),
                (TEXTURES[pl["tex"]][1](0.4 + 0.2 * k, r), 0, 0.6))
        name_of(event, i, f"{INSTS[pl['inst']][0]} + {TEXTURES[pl['tex']][0]} · {pl['fx']}")
        return apply_fx(x, pl["fx"], r)
    return f


def symbol_win(code):
    """Themed per-symbol foley (scripts/gc_sound/symbols.py), stereo."""
    import symbols

    def f(event, i, r):
        name, x = symbols.render(code, i, r)
        name_of(event, i, name)
        return x
    return f


SYMBOL_RMS_DB = -17.0
SYMBOLS = ["rare_purple", "rare_yellow", "rare_blue", "rare_green", "common_2", "common_4", "common_3", "common_1", "wild", "scatter"]

EVENTS: dict[str, tuple] = {
    "click": (percussive(0.25), -10, "one"),
    "spinPress": (percussive(0.5, pitched=True), -6, "one"),
    "betChange": (percussive(0.3, pitched=True), -8, "one"),
    "buyOpen": (melodic("happy", 0.07, 0.4), -5, "one"),
    "buyConfirm": (melodic("happy", 0.08, 1.0, chord_end=True), -2, "one"),
    "popupOpen": (riser_event(0.3, True, "happy", hit=False, chord=True), -5, "one"),
    "popupClose": (riser_event(0.3, False, "sad", hit=False, chord=False), -6, "one"),
    "spinStart": (riser_event(0.4, True, "neutral", hit=False, chord=False), -5, "one"),
    "reelLoop": (loop_reel, -12, "loop"),
    "reelStop": (percussive(0.55), -6, "one"),
    "finalReelStop": (percussive(1.0, pitched=True, low=True), -4, "one"),
    "anticipation": (loop_anticipation, -5, "loop"),
    "anticipationWin": (melodic("happy", 0.09, 1.2, chord_end=True), -1, "one"),
    "anticipationFail": (melodic("sad", 0.2, 0.4, fxs=FX_SAD), -3, "one"),
    "scatterLand1": (scatter_land(1), -3, "one"),
    "scatterLand2": (scatter_land(2), -2.5, "one"),
    "scatterLand3": (scatter_land(3), -2, "one"),
    "wildLand": (percussive(0.9, pitched=True, low=True), -3, "one"),
    "multLand": (percussive(0.4, pitched=True), -5, "one"),
    "smallWin": (melodic("happy", 0.1, 0.5), -3, "one"),
    "winLine": (melodic("neutral", 0.06, 0.3, accent=False), -6, "one"),
    "bigWin": (fanfare_event(1.0), -1, "one"),
    "megaWin": (fanfare_event(2.0), -1, "one"),
    "epicWin": (fanfare_event(3.0), -1, "one"),
    "countLoop": (loop_count, -10, "loop"),
    "countEnd": (melodic("happy", 0.07, 0.9, chord_end=True), -3, "one"),
    **{f"symWin_{c}": (symbol_win(c), -3, "one") for c in SYMBOLS},
    "wildGrow": (riser_event(0.7, True, "happy"), -2, "one"),
    "wildWin": (melodic("happy", 0.12, 1.3, root=A3, chord_end=True), -1.5, "one"),
    "multReveal": (melodic("happy", 0.06, 0.5), -3, "one"),
    "multFly": (riser_event(0.35, True, "neutral", hit=False, chord=False), -6, "one"),
    "multPlate": (percussive(0.7, pitched=True), -4, "one"),
    "baseToBonus": (riser_event(1.5, True, "happy"), -1, "one"),
    "bonusToBase": (riser_event(1.0, False, "sad", hit=True, chord=True), -2, "one"),
    "bonusSpinsWin": (fanfare_event(1.5), -1, "one"),
    "bonusTotalWin": (fanfare_event(2.6), -1, "one"),
    "fsCounter": (percussive(0.3), -8, "one"),
    "screenOpen": (riser_event(0.8, True, "neutral"), -1.5, "one"),
    "screenTap": (melodic("happy", 0.06, 0.5), -4, "one"),
    "base": (music_event(False), -3, "music"),
    "bonus": (music_event(True), -3, "music"),
}


def write_wav(path: Path, x: np.ndarray):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1 if x.ndim == 1 else 2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def write_mp3(path: Path, x: np.ndarray, kbps: int):
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1 if x.ndim == 1 else 2)
    enc.set_quality(2)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    path.write_bytes(enc.encode(pcm.tobytes()) + enc.flush())


def generate(name: str, i: int):
    fn, peak, kind = EVENTS[name]
    rng = np.random.default_rng(_h(name) * 31 + i)
    x = np.asarray(fn(name, i, rng), dtype=float)
    if kind == "one":
        x = dsp.fade(dsp.trim_tail(x, -55), 0.0008, 0.015)
    if name.startswith("symWin_"):
        # themed foley: a gunshot and a perfume spray must sit at the same
        # loudness — match RMS, then a soft limiter keeps the peaks in.
        mono = x.mean(axis=1) if x.ndim == 2 else x
        rms = np.sqrt(np.mean(mono ** 2)) + 1e-12
        x = x * (10 ** (SYMBOL_RMS_DB / 20) / rms)
        ceil = 10 ** (peak / 20)
        return ceil * np.tanh(x / ceil), kind
    return dsp.normalize(x, peak), kind


def render(name: str):
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("v*.*"):
        old.unlink()
    paths = []
    for i in range(10):
        x, kind = generate(name, i)
        ext = "wav" if kind == "loop" else "mp3"
        out = folder / f"v{i + 1:02d}.{ext}"
        if ext == "wav":
            write_wav(out, x)
        else:
            write_mp3(out, x, 160 if kind == "music" else 128)
        paths.append(out.relative_to(ROOT).as_posix())
    return paths


def main(argv):
    names = argv or list(EVENTS)
    mpath, npath = OUT / "manifest.json", OUT / "names.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    names_all = json.loads(npath.read_text()) if npath.exists() else {}
    for name in names:
        manifest[name] = render(name)
        names_all[name] = NAMES.get(name, [""] * 10)
        print(f"{name}: {' | '.join(names_all[name])}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps({k: manifest[k] for k in EVENTS if k in manifest}, ensure_ascii=False, indent=1) + "\n")
    npath.write_text(json.dumps({k: names_all[k] for k in EVENTS if k in names_all}, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
