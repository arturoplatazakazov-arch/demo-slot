"""Great Uniqorn — 5 complete sound SETS, synthesized in code.

    <venv with numpy scipy lameenc>/bin/python scripts/great_uniqorn_sound_sets.py [set ...]

A set is a GENRE that every game sound of that set is written in: the base and
bonus music, the win fanfares (BIG / MEGA / EPIC / TOTAL), the line win, the
cash counter, scatter landings and the scatter melody, wild land / grow, the
bonus transitions, buy-bonus, reel stops, anticipation. The ♪ panel switches
a whole set with one chip (js/great-uniqorn/sound.js `sets`). UI clicks stay
shared on purpose (the bar is the same in every set).

Built on the Gangsta Casino toolkit (scripts/gc_sound: dsp + the bar renderer
of pack.py). Everything is in A, MAJOR (a pompous, happy president), each set
with its own instrument, drums, groove and room.

Writes front/sound/great-uniqorn/sets/<set>/<event>.(mp3|wav) — loops as wav
(gapless), the rest mp3 — and sets/manifest.json. Levels follow the composer's
quieter re-export (2026-11-23): music ~-33 dB RMS, fanfares ~-24 dB.
Seeded: the same files every run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gc_sound"))
import dsp  # noqa: E402
import pack as gc  # noqa: E402
from dsp import SR, mix, n_of  # noqa: E402

ROOT = HERE.parent / "front"
OUT = ROOT / "sound" / "great-uniqorn" / "sets"
A2, A3, A4, A5, A6 = 45, 57, 69, 81, 93
H = gc.H

# --- the 5 sets -----------------------------------------------------------------
# `logic` is the Gangsta Casino genre name whose special cases render_bars
# applies (claps for disco, off-beat chord hits for jazz), `name` the label.
# INSTS: 0 гитара 1 рок-гитара 2 хор 3 свист 4 орган 5 струнные 6 маримба
# 7 стил-драм 8 чиптюн 9 медь 10 808 11 синт-лид 12 электропиано 13 калимба 14 колокола
SETS = [
    dict(key="march", name="Президентский марш", logic="марш", base=108, bonus=126,
         kick="x.......x.......", snare="x..x.xx.x..x.xxx", hat="", timp=True,
         bass=("pizz", [0, 8]), chords=5, lead=9, prog=[(0, "M"), (5, "M"), (-5, "M"), (0, "M")],
         fx="зал", count=("медь-тремоло", 9), anticip=2, tex=16, stop_tex=9),
    dict(key="jazz", name="Джаз Овального кабинета", logic="джаз-лаунж", base=92, bonus=118, swing=0.33,
         kick="x.......x.......", snare="....o.......o...", hat="x..xx..xx..xx..x", brush=True,
         bass=("walk", [0, 4, 8, 12]), chords=12, lead=6, prog=[(2, "m7"), (-5, "7"), (0, "M7"), (-3, "m7")],
         fx="зал", count=("вибрафон", 6), anticip=4, tex=2, stop_tex=2),
    dict(key="funk", name="Фанк-кампания", logic="фанк", base=104, bonus=118, swing=0.12,
         kick="x..x..x...x..x..", snare="....x..o....x...", hat="xxxxxxxxxxxxxxxx",
         bass=("slap", [0, 3, 6, 7, 10, 14]), chords="scratch", lead=4, prog=[(0, "7"), (5, "7"), (0, "7"), (-5, "7")],
         fx="сухо", lowcut=0.72, count=("орган", 4), anticip=8, tex=13, stop_tex=10),
    dict(key="synthwave", name="Синтвейв-Вашингтон", logic="синтвейв", base=100, bonus=122,
         kick="x...x...x...x...", snare="....x.......x...", hat="..x...x...x...x.",
         bass=("saw8", [0, 2, 4, 6, 8, 10, 12, 14]), chords="pad", lead=11, prog=[(0, "M"), (-5, "M"), (-3, "m"), (5, "M")],
         fx="широко", lowcut=0.65, count=("синт-арп", 11), anticip=0, tex=15, stop_tex=7),
    dict(key="disco", name="Диско-гала", logic="диско", base=118, bonus=126,
         kick="x...x...x...x...", snare="....x.......x...", hat="..x...x...x...x.", openhat=True,
         bass=("octave", [0, 2, 4, 6, 8, 10, 12, 14]), chords=9, lead=5, prog=[(0, "M7"), (-3, "m7"), (2, "m7"), (-5, "7")],
         fx="широко", count=("колокольчики", 14), anticip=3, tex=1, stop_tex=13),
]
MAJ = [0, 2, 4, 5, 7, 9, 11]


def deg(d, root=A4):
    return gc.deg(MAJ, d, root)


def genre(s):
    g = dict(s)
    g["name"] = s["logic"]  # render_bars' special cases key on this
    return g


def lead(s, m, d, r, vel=0.9):
    return gc.note(s["lead"], m, d, r, vel)


def fx1(s, x, r):
    """Mono one-shot through the set's room."""
    return gc.apply_fx(x, s["fx"], r)


def motif(s, steps, beat, r, root=A4, vel=0.9, chord=None, chord_len=2.0):
    parts = [(lead(s, deg(d, root), ln * beat, r, vel), pos * beat) for pos, d, ln in steps]
    if chord is not None:
        t = steps[-1][0] * beat
        for c in chord:
            parts.append((lead(s, root + c, beat * chord_len, r, 0.35), t))
    return mix(*parts)


def tex(s, size, r, which="tex"):
    return gc.TEXTURES[s[which]][1](size, r)


def riser(s, d, up, r):
    idx = {"march": 7, "jazz": 8, "funk": 3, "synthwave": 9, "disco": 0}[s["key"]]
    return gc.RISERS[idx][1](d, up, r)


# --- events ---------------------------------------------------------------------

def music(s, bonus, r):
    g = genre(s)
    bpm = s["bonus"] if bonus else s["base"]
    beat = 60 / bpm
    bars = 16 if bpm <= 130 else 24
    tr = gc.Track(bars * 4 * beat + 3)
    for sec in range(bars // 4):
        layers = {"bass", "chords"}
        if bonus or sec >= 1:
            layers |= {"drums", "perc"}
        if sec >= 2 or (bonus and sec >= 1):
            layers |= {"lead"}
        gc.render_bars(g, 4, bpm, r, layers, None, None, tr, sec * 16 * beat)
    total = bars * 4 * beat
    x = gc.apply_fx_stereo(tr.buf, s["fx"], r)
    x = np.stack([tame_lows(x[:, c], s.get("lowcut", 0.45)) for c in range(2)], 1)
    return np.stack([dsp.loopify(x[:, c], n_of(total)) for c in range(2)], 1)


def tame_lows(x, k=0.45):
    """Sub rumble off, the bass under 110 Hz down ~5 dB: a phone speaker plays
    none of it, and the first synth mixes were half sub."""
    from scipy.signal import butter, sosfiltfilt
    x = dsp.hp(x, 38)
    # zero-phase low band, so subtracting it really lowers it (a plain
    # Butterworth's phase shift made the subtraction do next to nothing)
    low = sosfiltfilt(butter(4, 130, "lowpass", fs=SR, output="sos"), x)
    return x - k * low


def fanfare(s, intensity, r):
    g = genre(s)
    bpm = s["bonus"]
    beat = 60 / bpm
    bars = 2 if intensity < 1.5 else 3
    tr = gc.Track(bars * 4 * beat + 5)
    t0 = 0.0
    if intensity >= 2.5:
        tr.put(riser(s, 1.0, True, r), 0, 0.6)
        t0 = 1.0
    lift = 12 if intensity >= 2 else 0
    mel = [(b + t0 / beat, m - 12 + (lift if b >= 4 else 0), ln) for b, m, ln in gc.FANFARE_MEL if b < bars * 4 - 1]
    prog = [(0, "M"), (5, "M"), (-5, "M"), (0, "M")]
    end_t = t0 + gc.render_bars(g, bars, bpm, r, {"drums", "bass", "chords", "perc"}, mel, prog, tr, t0, happy_end=True)
    for c in (0, 4, 7, 12):
        tr.put(lead(s, A4 + c, 1.4, r, 0.5), end_t, 0.7)
    tr.put(tex(s, 1.0, r), end_t, 0.6)
    tr.put(dsp.crash(1.3, r), end_t, 0.14)
    if intensity >= 2:
        for k in range(int(10 * intensity)):
            tr.put(dsp.coin(2800 + 160 * (k % 9), 0.3, r), end_t + 0.05 * k, 0.22, (k % 5 - 2) / 3)
    return gc.apply_fx_stereo(tr.buf[: n_of(end_t + 1.8)], s["fx"], r)


def count_loop(s, r):
    d = 1.0
    st = d / 16
    arp = [A5, A5 + 4, A5 + 7, A6, A5 + 7, A5 + 4, A5, A5 + 4]
    x = mix(*[(gc.note(s["count"][1], arp[k % len(arp)], st * 1.4, r, 0.6), k * st, 1.0 if k % 4 == 0 else 0.7) for k in range(16)],
            *[(dsp.coin(3000 + 240 * (k % 5), 0.12, r) * 0.25, k * st * 2) for k in range(8)])
    return dsp.loopify(x, n_of(d))


def anticipation(s, r):
    return gc.loop_anticipation("anticipation", s["anticip"], r)


def reel_stop(s, k, r):
    """Reels 1-4 climb the scale, the last one lands on the octave."""
    last = k == 5
    m = deg([0, 2, 4, 5, 7][k - 1], A3)
    x = mix((tex(s, 0.9 if last else 0.45, r, "stop_tex"), 0, 0.9),
            (lead(s, m, 0.35 if last else 0.18, r, 0.6), 0.004),
            *([(lead(s, m - 12, 0.4, r, 0.4), 0.004), (dsp.kick(0.3, 110, 45, 0.8), 0, 0.35)] if last else []))
    # a stop is a short, dry hit (a hall tail smears four stops into one)
    return dsp.reverb(tame_lows(x), 0.5, 0.08)


def build(s, ev, r):
    beat = 60 / s["bonus"] / 2
    if ev == "base":
        return music(s, False, r)
    if ev == "bonus":
        return music(s, True, r)
    if ev == "bigWin":
        return fanfare(s, 1.0, r)
    if ev == "megaWin":
        return fanfare(s, 2.0, r)
    if ev == "epicWin":
        return fanfare(s, 3.0, r)
    if ev == "bonusTotalWin":
        return fanfare(s, 2.6, r)
    if ev == "smallWin":
        return fx1(s, mix((motif(s, [(0, 0, 1), (1, 2, 1), (2, 4, 2)], beat, r, chord=[0, 4, 7]), 0), (dsp.coin(3200, 0.4, r) * 0.4, beat * 2)), r)
    if ev == "winLine":
        return fx1(s, motif(s, [(0, 4, 0.5), (0.5, 7, 1.5)], beat * 0.8, r, A5, 0.6), r)
    if ev == "countLoop":
        return count_loop(s, r)
    if ev == "countEnd":
        return fx1(s, mix((motif(s, [(0, 7, 0.5), (0.5, 9, 0.5), (1, 11, 0.5), (1.5, 14, 2)], beat * 0.6, r, A4, chord=[0, 4, 7, 12]), 0),
                          (dsp.coin(3600, 0.6, r) * 0.4, beat)), r)
    if ev.startswith("scatterLand"):
        k = int(ev[-1])
        m = [A5, A5 + 4, A5 + 7][k - 1]
        x = mix((lead(s, m, 0.45, r), 0), (lead(s, m + 12, 0.35, r, 0.35), 0.04),
                (dsp.bell(H(m + 12), 0.6, 3.5, 1.4, 0.25) * 0.4, 0), (tex(s, 0.4 + 0.2 * k, r), 0, 0.5))
        return fx1(s, x, r)
    if ev == "symWin_scatter":
        return fx1(s, mix((motif(s, [(0, 4, 0.5), (0.5, 4, 0.5), (1, 4, 0.5), (1.5, 7, 1), (2.5, 9, 0.5), (3, 11, 0.5), (3.5, 14, 2.5)], beat, r, A4, chord=[0, 4, 7, 12], chord_len=3), 0),
                          *[(dsp.coin(2900 + 200 * (k % 6), 0.3, r) * 0.25, beat * 3.5 + 0.06 * k) for k in range(8)]), r)
    if ev == "wildLand":
        return fx1(s, mix((tex(s, 1.0, r, "stop_tex"), 0), (lead(s, A3, 0.5, r, 0.8), 0.005), (lead(s, A3 + 7, 0.5, r, 0.4), 0.005),
                          (dsp.timpani(H(A2), 0.7, r) * 0.5, 0)), r)
    if ev == "wildGrow":
        d = 0.7
        parts = [(riser(s, d, True, r), 0, 0.7), (tex(s, 1.0, r), d * 0.95, 0.7)]
        parts += [(lead(s, A4 + c, 1.0, r, 0.45), d * 0.95) for c in (0, 4, 7, 12)]
        return dsp.reverb(mix(*parts), 1.4, 0.2)
    if ev in ("baseToBonus", "bonusToBase"):
        up = ev == "baseToBonus"
        d = 1.5 if up else 1.0
        parts = [(riser(s, d, up, r), 0, 0.8), (tex(s, 1.0, r), d * 0.95, 0.8)]
        parts += [(lead(s, A3 + c, 1.4 if up else 1.0, r, 0.45), d * 0.95) for c in ([0, 4, 7, 12] if up else [0, 4, 7])]
        if up:
            parts.append((dsp.crash(1.6, r), d * 0.95, 0.15))
        return dsp.reverb(mix(*parts), 1.6, 0.25)
    if ev == "buyButton":
        return fx1(s, motif(s, [(0, 0, 0.5), (0.5, 4, 0.5), (1, 7, 1)], beat * 0.6, r, A4, 0.8), r)
    if ev == "buyConfirm":
        return fx1(s, mix((motif(s, [(0, 0, 0.5), (0.5, 4, 0.5), (1, 7, 0.5), (1.5, 12, 2)], beat * 0.7, r, A4, chord=[0, 4, 7]), 0),
                          (dsp.register(r)[: n_of(0.7)] * 0.4, beat)), r)
    if ev == "spinStart":
        return mix((riser(s, 0.35, True, r) * 0.6, 0), (lead(s, A4, 0.15, r, 0.4), 0.3))
    if ev.startswith("reelStop"):
        return reel_stop(s, int(ev[-1]), r)
    if ev == "finalReelStop":
        return reel_stop(s, 5, r)
    if ev == "anticipation":
        return anticipation(s, r)
    if ev == "anticipationWin":
        return fx1(s, motif(s, [(0, 0, 0.5), (0.5, 2, 0.5), (1, 4, 0.5), (1.5, 7, 0.5), (2, 12, 2)], beat * 0.7, r, A4, chord=[0, 4, 7]), r)
    if ev == "anticipationFail":
        return fx1(s, motif(s, [(0, 4, 1), (1, 3, 1), (2, 2, 1), (3, 1, 3)], beat * 1.2, r, A3, 0.7), r)
    raise KeyError(ev)


# event -> (kind, target RMS dB, peak ceiling dB)
EVENTS = {
    "base": ("music", -33, -6), "bonus": ("music", -33, -6),
    "smallWin": ("one", -25, -6), "winLine": ("one", -28, -9),
    "bigWin": ("one", -24, -5), "megaWin": ("one", -24, -5), "epicWin": ("one", -23, -5), "bonusTotalWin": ("one", -24, -5),
    "countLoop": ("loop", -34, -14), "countEnd": ("one", -26, -7),
    "scatterLand1": ("one", -25, -6), "scatterLand2": ("one", -24.5, -6), "scatterLand3": ("one", -24, -6),
    "symWin_scatter": ("one", -24, -5),
    "wildLand": ("one", -25, -6), "wildGrow": ("one", -25, -6),
    "baseToBonus": ("one", -24, -5), "bonusToBase": ("one", -25, -6),
    "buyButton": ("one", -27, -8), "buyConfirm": ("one", -25, -6),
    "spinStart": ("one", -30, -10),
    "reelStop1": ("one", -29, -9), "reelStop2": ("one", -29, -9), "reelStop3": ("one", -29, -9), "reelStop4": ("one", -29, -9),
    "finalReelStop": ("one", -27, -7),
    "anticipation": ("loop", -30, -9), "anticipationWin": ("one", -25, -6), "anticipationFail": ("one", -27, -8),
}


def level(x, rms_db, peak_db):
    mono = x.mean(axis=1) if x.ndim == 2 else x
    rms = np.sqrt(np.mean(mono ** 2)) + 1e-12
    x = x * (10 ** (rms_db / 20) / rms)
    ceil = 10 ** (peak_db / 20)
    return ceil * np.tanh(x / ceil)


def render_set(s):
    folder = OUT / s["key"]
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for i, (ev, (kind, rms_db, peak_db)) in enumerate(EVENTS.items()):
        r = np.random.default_rng(gc._h(ev) * 17 + gc._h(s["key"]))
        x = np.asarray(build(s, ev, r), dtype=float)
        if kind == "one":
            x = dsp.fade(dsp.trim_tail(x, -55), 0.0008, 0.015)
        x = level(x, rms_db, peak_db)
        ext = "wav" if kind == "loop" else "mp3"
        p = folder / f"{ev}.{ext}"
        if ext == "wav":
            gc.write_wav(p, x)
        else:
            gc.write_mp3(p, x, 160 if kind == "music" else 128)
        out[ev] = p.relative_to(ROOT).as_posix()
        print(f"  {s['key']}/{ev}.{ext}", flush=True)
    return out


def main(argv):
    for s in SETS:
        if not argv or s["key"] in argv:
            print(s["name"], flush=True)
            render_set(s)
    # the manifest from what is on disk (sets may be rendered in parallel runs)
    manifest = {}
    for s in SETS:
        files = {}
        for ev, (kind, _, _) in EVENTS.items():
            p = OUT / s["key"] / f"{ev}.{'wav' if kind == 'loop' else 'mp3'}"
            if p.exists():
                files[ev] = p.relative_to(ROOT).as_posix()
        if files:
            manifest[s["key"]] = {"name": s["name"], "files": files}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
