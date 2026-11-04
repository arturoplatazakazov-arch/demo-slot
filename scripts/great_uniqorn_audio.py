"""Great Uniqorn — music + SFX audition pack, synthesized in code (numpy/scipy).

No samples and no AI audio service (fal.ai was locked on TOP_UP, 2026-11-04):
every sound below is built from oscillators, noise and filters, so the whole
pack is reproducible from this file.

Three variants of every sound the product listed:

  music    BG base, BG bonus — seamless loops (render + fold the reverb tail
           back onto the start)
  win      line win, big win, mega win, epic win, cash loop (seamless)
  scatter  scatter 1 / 2 / 3 (rising stingers), scatter win
  wild     wild -> multiplier reveal
  bonus    enter bonus, leave bonus
  ui       click, popup open / close, autospin, bet + / bet -, menu, turbo

Theme: «Great Uniqorn» — a unicorn president in the Oval Office (base) and on
a skyscraper terrace at sunset (bonus): brass, gold, money, a wink of pomp.

Output: front/sound/great-uniqorn/_audition/<group>/<name>_<A|B|C>.mp3 plus
manifest.json (titles/descriptions) for the listening page.

    python3 scripts/great_uniqorn_audio.py            # everything
    python3 scripts/great_uniqorn_audio.py ui win     # only these groups
"""

import json
import math
import os
import sys

import lameenc
import numpy as np
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'front/sound/great-uniqorn/_audition')
RNG = np.random.default_rng(7)

# =============================================================================
# basics


def n_of(sec):
    return max(1, int(round(sec * SR)))


def tt(sec):
    return np.arange(n_of(sec)) / SR


def hz(note):
    """'A4', 'C#5', 'Bb3' or a MIDI number -> Hz."""
    if not isinstance(note, str):
        return 440.0 * 2 ** ((float(note) - 69) / 12)
    names = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    s = note.strip()
    k = names[s[0].upper()]
    i = 1
    while i < len(s) and s[i] in '#b':
        k += 1 if s[i] == '#' else -1
        i += 1
    octave = int(s[i:])
    return 440.0 * 2 ** ((k + 12 * (octave + 1) - 69) / 12)


def midi(note):
    return int(round(69 + 12 * math.log2(hz(note) / 440.0)))


CHORDS = {
    'maj': [0, 4, 7], 'min': [0, 3, 7], 'maj7': [0, 4, 7, 11], 'min7': [0, 3, 7, 10], '7': [0, 4, 7, 10],
    'min9': [0, 3, 7, 10, 14], '9': [0, 4, 7, 10, 14], '13': [0, 4, 10, 14, 21], 'maj9': [0, 4, 7, 11, 14],
    'sus4': [0, 5, 7], 'min11': [0, 3, 7, 10, 14, 17], '6': [0, 4, 7, 9], 'dim7': [0, 3, 6, 9],
}


def chord(root, kind, inv=0):
    r = midi(root)
    notes = [r + i for i in CHORDS[kind]]
    for _ in range(inv):
        notes = notes[1:] + [notes[0] + 12]
    return notes


def env(n, a=0.005, d=0.1, s=0.7, r=0.1, hold=None):
    """ADSR over n samples; `hold` = seconds before release (default n - r)."""
    total = n / SR
    hold = total - r if hold is None else hold
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-6), 1.0)
    dd = (t >= a) & (t < a + d)
    e = np.where(dd, 1 - (1 - s) * (t - a) / max(d, 1e-6), e)
    e = np.where((t >= a + d), s, e)
    rel = t >= hold
    e = np.where(rel, s * np.clip(1 - (t - hold) / max(r, 1e-6), 0, 1), e)
    return e


def expdec(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


def sos_lp(x, fc, order=2):
    fc = min(fc, SR * 0.45)
    return sosfilt(butter(order, fc, 'low', fs=SR, output='sos'), x)


def sos_hp(x, fc, order=2):
    return sosfilt(butter(order, max(fc, 10), 'high', fs=SR, output='sos'), x)


def sos_bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [max(lo, 10), min(hi, SR * 0.45)], 'band', fs=SR, output='sos'), x)


def sweep_filter(x, fcs, kind='low', block=512):
    """Time-varying Butterworth: cutoff per block from the array `fcs` (per sample)."""
    y = np.empty_like(x)
    zi = None
    for i in range(0, len(x), block):
        fc = float(np.clip(fcs[min(i + block // 2, len(fcs) - 1)], 30, SR * 0.45))
        sos = butter(2, fc, kind, fs=SR, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        y[i:i + block], zi = sosfilt(sos, x[i:i + block], zi=zi)
    return y


def noise(sec):
    return RNG.normal(0, 1, n_of(sec))


# --- oscillators -------------------------------------------------------------

def sine(f, sec, phase=0.0):
    t = tt(sec)
    if np.ndim(f):
        ph = 2 * np.pi * np.cumsum(f) / SR
        return np.sin(ph + phase)
    return np.sin(2 * np.pi * f * t + phase)


def saw_add(f, sec, fc=None, harmonics=48, odd=False, vib=0.0, vib_rate=5.5, detune=0.0):
    """Band-limited additive saw (or square with odd=True). `fc` = cutoff in Hz
    (number or per-sample array): each harmonic is weighted by a 2-pole
    low-pass response, so a rising fc reads as a brass filter opening."""
    n = n_of(sec)
    t = np.arange(n) / SR
    f = f * (1 + detune)
    fm = f * (1 + vib * np.sin(2 * np.pi * vib_rate * t)) if vib else np.full(n, f)
    ph = 2 * np.pi * np.cumsum(fm) / SR
    out = np.zeros(n)
    kmax = int(min(harmonics, (SR * 0.45) / f))
    fcv = None if fc is None else (np.full(n, fc) if np.ndim(fc) == 0 else fc)
    for k in range(1, kmax + 1):
        if odd and k % 2 == 0:
            continue
        w = 1.0 / k
        if fcv is not None:
            w = w / (1 + (k * f / fcv) ** 4)
        out += w * np.sin(k * ph)
    return out


def fm(fc, ratio, index, sec, idx_tau=None, fb=0.0):
    t = tt(sec)
    idx = index * (np.exp(-t / idx_tau) if idx_tau else 1.0)
    mod = np.sin(2 * np.pi * fc * ratio * t)
    return np.sin(2 * np.pi * fc * t + idx * mod)


# --- effects -----------------------------------------------------------------

_IR = {}


def reverb_ir(t60=1.8, tone=6000, seed=3):
    key = (t60, tone, seed)
    if key not in _IR:
        r = np.random.default_rng(seed)
        n = n_of(t60)
        t = np.arange(n) / SR
        dec = np.exp(-6.9 * t / t60)
        ir = np.stack([sos_lp(r.normal(0, 1, n), tone) * dec, sos_lp(r.normal(0, 1, n), tone) * dec])
        ir[:, :n_of(0.012)] *= np.linspace(0, 1, n_of(0.012))  # soft pre-delay onset
        _IR[key] = ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
    return _IR[key]


def reverb(st, mix=0.22, t60=1.8, tone=6000):
    ir = reverb_ir(t60, tone)
    mono = st.mean(axis=0)
    wet = np.stack([fftconvolve(mono, ir[0])[:st.shape[1] + ir.shape[1]],
                    fftconvolve(mono, ir[1])[:st.shape[1] + ir.shape[1]]])
    dry = np.zeros_like(wet)
    dry[:, :st.shape[1]] = st
    return dry * (1 - mix * 0.5) + wet * mix


def delay(st, sec, fb=0.35, mix=0.25, pingpong=True):
    d = n_of(sec)
    out = np.zeros((2, st.shape[1] + d * 6))
    out[:, :st.shape[1]] += st
    tap = st.copy()
    for i in range(1, 6):
        g = mix * fb ** (i - 1)
        if g < 0.01:
            break
        src = tap[::-1] if (pingpong and i % 2) else tap
        out[:, d * i:d * i + st.shape[1]] += g * src
    return out


def pan(x, p=0.0, gain=1.0):
    """mono -> stereo, p in [-1, 1] (constant power)."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)]) * gain


def mix_into(buf, start_sec, st):
    i = n_of(start_sec) if start_sec > 0 else 0
    if st.ndim == 1:
        st = pan(st)
    end = min(buf.shape[1], i + st.shape[1])
    if end > i:
        buf[:, i:end] += st[:, :end - i]


def soft_master(st, drive=1.15, peak=0.89):
    st = np.tanh(st / max(1e-9, np.abs(st).max()) * drive * 1.4) / np.tanh(drive * 1.4)
    return st / max(1e-9, np.abs(st).max()) * peak


# =============================================================================
# instruments (mono, return arrays)

def epiano(note, sec, vel=0.8):
    f = hz(note) if not isinstance(note, float) else note
    t = tt(sec)
    body = fm(f, 1.0, 1.6 * vel, sec, idx_tau=0.35)
    tine = 0.25 * vel * fm(f * 4, 3.5, 2.0, sec, idx_tau=0.05) * expdec(len(t), 0.06)
    e = expdec(len(t), max(0.25, 0.9 + 0.6 * (1 - f / 1500))) * env(len(t), a=0.002, d=0.0, s=1.0, r=0.08)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 5.0 * t)
    return (body + tine) * e * trem * vel


def piano(note, sec, vel=0.8):
    f = hz(note)
    t = tt(sec)
    out = np.zeros_like(t)
    for k in range(1, 9):
        fk = f * k * np.sqrt(1 + 0.0004 * k * k)
        if fk > SR * 0.45:
            break
        out += (0.9 ** k) / k ** 0.6 * np.sin(2 * np.pi * fk * t) * expdec(len(t), 1.6 / (1 + 0.5 * k))
    ham = sos_bp(noise(0.02), 800, 5000) * 0.15
    out[:len(ham)] += ham * vel
    return out * env(len(t), a=0.002, d=0, s=1, r=0.12) * vel


def brass(note, sec, vel=0.8, bright=1.0, vib=0.004):
    f = hz(note) if isinstance(note, str) or isinstance(note, int) else note
    n = n_of(sec)
    t = np.arange(n) / SR
    fc = f * (1.5 + 7 * bright * vel * (1 - np.exp(-t / 0.05))) * (0.85 + 0.15 * np.exp(-t / 0.4))
    out = 0
    for dt in (-0.004, 0.0, 0.0045):
        out = out + saw_add(f, sec, fc=fc, harmonics=36, vib=vib * np.clip(t / 0.3, 0, 1).mean(), detune=dt)
    blat = sos_bp(noise(0.03), 600, 2400) * 0.3
    out[:len(blat)] += blat
    return out / 3 * env(n, a=0.025, d=0.12, s=0.8, r=0.09) * vel


def strings(note, sec, vel=0.6, attack=0.25):
    f = hz(note) if not isinstance(note, float) else note
    n = n_of(sec)
    out = 0
    for dt in (-0.006, -0.002, 0.003, 0.007):
        out = out + saw_add(f, sec, fc=f * 5 + 1200, harmonics=30, vib=0.003, vib_rate=5 + dt * 200, detune=dt)
    return out / 4 * env(n, a=attack, d=0.2, s=0.85, r=min(0.4, sec * 0.4)) * vel


def bell(note, sec, vel=0.7, ratio=3.5):
    f = hz(note) if not isinstance(note, float) else note
    n = n_of(sec)
    b = fm(f, ratio, 3.0, sec, idx_tau=0.25) + 0.3 * np.sin(2 * np.pi * f * 2.76 * tt(sec)) * expdec(n, 0.3)
    return b * expdec(n, 0.7) * env(n, a=0.001, d=0, s=1, r=0.05) * vel


def glock(note, sec=0.8, vel=0.7):
    f = hz(note) if not isinstance(note, float) else note
    t = tt(sec)
    n = len(t)
    g = np.sin(2 * np.pi * f * t) * expdec(n, 0.6) + 0.35 * np.sin(2 * np.pi * f * 5.4 * t) * expdec(n, 0.08)
    return g * env(n, a=0.001, d=0, s=1, r=0.04) * vel


def vibes(note, sec=1.2, vel=0.6):
    f = hz(note)
    t = tt(sec)
    n = len(t)
    g = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 4 * t) * expdec(n, 0.2)) * expdec(n, 1.1)
    return g * (1 + 0.25 * np.sin(2 * np.pi * 6 * t)) * env(n, a=0.002, d=0, s=1, r=0.1) * vel


def pluck(note, sec, vel=0.8, bright=0.5, damp=0.996):
    """Karplus-Strong string via an IIR comb (scipy lfilter: fast)."""
    f = hz(note) if not isinstance(note, float) else note
    n = n_of(sec)
    period = max(2, int(round(SR / f)))
    exc = np.zeros(n)
    burst = RNG.uniform(-1, 1, period)
    burst = lfilter([bright, 1 - bright], [1], burst)
    burst -= burst.mean()  # no DC: it would ring on as a sub-bass offset
    exc[:period] = burst
    a = np.zeros(period + 2)
    a[0] = 1
    a[period] = -damp * 0.5
    a[period + 1] = -damp * 0.5
    y = lfilter([1], a, exc)
    return y * env(n, a=0.001, d=0, s=1, r=0.03) * vel


def bass(note, sec, vel=0.9, kind='synth'):
    f = hz(note) if not isinstance(note, float) else note
    n = n_of(sec)
    t = np.arange(n) / SR
    if kind == 'upright':
        x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
        x *= expdec(n, 0.6)
        x[:n_of(0.01)] += sos_bp(noise(0.01), 200, 900) * 0.4
    elif kind == 'slap':
        fc = f * (2 + 18 * np.exp(-t / 0.03))
        x = saw_add(f, sec, fc=fc, harmonics=24) * 1.2 + 0.8 * np.sin(2 * np.pi * f * t)
        x *= expdec(n, 0.35)
        x[:n_of(0.006)] += noise(0.006) * 0.5
    elif kind == 'tuba':
        x = saw_add(f, sec, fc=f * 3.2, harmonics=12) + 0.6 * np.sin(2 * np.pi * f * t)
        x *= env(n, a=0.02, d=0.1, s=0.75, r=0.06)
    else:  # synth
        fc = f * (1.6 + 6 * np.exp(-t / 0.08))
        x = saw_add(f, sec, fc=fc, harmonics=30) + 0.7 * np.sin(2 * np.pi * f * t)
    return x * env(n, a=0.003, d=0, s=1, r=0.04) * vel


def choir(note, sec, vel=0.6, vowel='a'):
    """Saw through three formant band-passes — a synthetic 'aah'."""
    f = hz(note) if not isinstance(note, float) else note
    n = n_of(sec)
    src = 0
    for dt in (-0.005, 0.0, 0.006):
        src = src + saw_add(f, sec, harmonics=60, vib=0.006, vib_rate=5.2, detune=dt)
    forms = {'a': [(800, 1), (1150, 0.5), (2900, 0.25)], 'o': [(450, 1), (800, 0.4), (2830, 0.15)]}[vowel]
    out = sum(g * sos_bp(src, fc * 0.85, fc * 1.15) for fc, g in forms)
    return out * env(n, a=0.3, d=0.2, s=0.9, r=min(0.5, sec * 0.4)) * vel


# --- drums -------------------------------------------------------------------

def kick(vel=1.0, tone=50, punch=1.0):
    sec = 0.45
    t = tt(sec)
    f = tone + (tone * 2.6) * np.exp(-t / 0.035)
    x = sine(f, sec) * expdec(len(t), 0.18)
    x[:n_of(0.004)] += noise(0.004) * 0.6 * punch
    return np.tanh(x * 1.6) * vel


def snare(vel=0.9, tone=185, snap=1.0, sec=0.28):
    t = tt(sec)
    body = sine(tone * (1 + 0.4 * np.exp(-t / 0.01)), sec) * expdec(len(t), 0.06)
    nz = sos_bp(noise(sec), 1500, 9000) * expdec(len(t), 0.11 * snap)
    return (0.6 * body + 0.9 * nz) * vel


def clap(vel=0.8):
    sec = 0.3
    out = np.zeros(n_of(sec))
    for i, d in enumerate((0, 0.011, 0.022)):
        b = sos_bp(noise(0.06), 900, 3500) * expdec(n_of(0.06), 0.012 if i < 2 else 0.05)
        s = n_of(d)
        out[s:s + len(b)] += b
    return out * vel


def hat(vel=0.5, open_=False):
    sec = 0.35 if open_ else 0.06
    x = sos_hp(noise(sec), 7000) * expdec(n_of(sec), 0.12 if open_ else 0.018)
    return x * vel


def ride(vel=0.4):
    sec = 0.9
    t = tt(sec)
    x = sos_hp(noise(sec), 5000) * expdec(len(t), 0.35) * 0.6
    x += 0.25 * sum(np.sin(2 * np.pi * f * t) for f in (3170, 4410, 5920)) * expdec(len(t), 0.5) / 3
    return x * vel


def crash(vel=0.7, sec=2.2):
    t = tt(sec)
    x = sos_hp(noise(sec), 3500) * expdec(len(t), 0.7)
    x += 0.2 * sum(np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) for f in (2830, 3470, 4190, 5310)) * expdec(len(t), 0.5) / 4
    return x * vel


def brush(vel=0.4, sec=0.22):
    x = sos_bp(noise(sec), 2500, 9000) * env(n_of(sec), a=0.06, d=0, s=1, r=0.12)
    return x * vel


def shaker(vel=0.3):
    sec = 0.09
    return sos_bp(noise(sec), 5000, 12000) * env(n_of(sec), a=0.02, d=0, s=1, r=0.06) * vel


def tom(note='G2', vel=0.8):
    sec = 0.5
    f = hz(note)
    t = tt(sec)
    x = sine(f * (1 + 0.5 * np.exp(-t / 0.04)), sec) * expdec(len(t), 0.25)
    return x * vel


def timpani(note='F2', vel=0.9, sec=1.6):
    f = hz(note)
    t = tt(sec)
    x = sine(f * (1 + 0.08 * np.exp(-t / 0.05)), sec) * expdec(len(t), 0.7)
    x += 0.4 * sine(f * 1.5, sec) * expdec(len(t), 0.4)
    x[:n_of(0.03)] += sos_lp(noise(0.03), 1200) * 0.5
    return x * vel


def snare_roll(sec, vel=0.6, rate=26, cresc=True):
    out = np.zeros(n_of(sec + 0.3))
    k = int(sec * rate)
    for i in range(k):
        g = (0.35 + 0.65 * i / max(1, k - 1)) if cresc else 1.0
        s = snare(vel * g * RNG.uniform(0.8, 1.0), snap=0.5, sec=0.12)
        j = n_of(i / rate)
        out[j:j + len(s)] += s
    return out


# --- fx sources --------------------------------------------------------------

def coin(vel=0.7, pitch=1.0):
    sec = 0.45
    t = tt(sec)
    fs = np.array([2730, 4110, 5520, 6990]) * pitch * RNG.uniform(0.97, 1.03)
    x = sum(np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) * expdec(len(t), 0.18 / (1 + i * 0.6))
            for i, f in enumerate(fs))
    x[:n_of(0.004)] += noise(0.004) * 0.8
    return x * vel / 2


def coin_shower(sec, density=22, vel=0.5, pitch=1.0, rise=0.0):
    out = np.zeros(n_of(sec + 0.5))
    k = int(sec * density)
    for _ in range(k):
        at = RNG.uniform(0, sec)
        c = coin(vel * RNG.uniform(0.4, 1.0), pitch * (1 + rise * at / sec) * RNG.uniform(0.9, 1.15))
        j = n_of(at)
        out[j:j + len(c)] += c
    return out


def riser(sec, f0=300, f1=6000, vel=0.6, kind='low'):
    n = n_of(sec)
    t = np.arange(n) / SR
    fcs = f0 * (f1 / f0) ** (t / sec)
    x = sweep_filter(noise(sec), fcs, kind)
    tone = sine(fcs * 0.25, sec) * 0.25
    return (x + tone) * (t / sec) ** 1.6 * vel


def whoosh(sec=0.35, f0=600, f1=4000, vel=0.6):
    n = n_of(sec)
    t = np.arange(n) / SR
    fcs = f0 * (f1 / f0) ** (t / sec)
    x = sweep_filter(noise(sec), fcs, 'low')
    return x * np.sin(np.pi * t / sec) ** 1.5 * vel


def downer(sec=0.4, f0=4000, f1=400, vel=0.6):
    return whoosh(sec, f0, f1, vel)


def sizzle(sec=0.8, vel=0.4):
    """Burger on the grill — crackly fat sizzle."""
    n = n_of(sec)
    x = sos_hp(noise(sec), 3500) * 0.3
    pops = np.zeros(n)
    for _ in range(int(sec * 70)):
        j = RNG.integers(0, n - 200)
        pops[j:j + 120] += RNG.uniform(-1, 1) * expdec(120, 0.0006)
    x = x + sos_hp(pops, 2000)
    return x * env(n, a=0.03, d=0, s=1, r=sec * 0.5) * vel


def sparkle(sec=0.8, base='C6', vel=0.4, steps=8, scale=(0, 4, 7, 12, 16, 19, 24, 28)):
    out = np.zeros(n_of(sec + 0.6))
    for i in range(steps):
        g = glock(midi(base) + scale[i % len(scale)] + 12 * (i // len(scale)), 0.6, vel * (0.6 + 0.4 * RNG.random()))
        j = n_of(sec * i / steps)
        out[j:j + len(g)] += g
    return out


def impact(vel=1.0, tone=45):
    sec = 1.8
    t = tt(sec)
    x = sine(tone * (1 + 1.5 * np.exp(-t / 0.06)), sec) * expdec(len(t), 0.5)
    x += sos_lp(noise(sec), 900) * expdec(len(t), 0.25) * 0.6
    return np.tanh(x * 1.5) * vel


def register_bell(vel=0.7):
    """'Cha-ching': drawer slide + two bright bells."""
    out = np.zeros(n_of(1.4))
    slide = sos_bp(noise(0.12), 1500, 6000) * env(n_of(0.12), a=0.01, d=0, s=1, r=0.05) * 0.5
    out[:len(slide)] += slide
    for at, nt in ((0.1, 'E7'), (0.2, 'C7')):
        b = bell(nt, 1.1, 0.8, ratio=2.4)
        j = n_of(at)
        out[j:j + len(b)] += b
    return out * vel


# =============================================================================
# sequencing helpers

class Song:
    def __init__(self, bpm, bars, beats_per_bar=4, swing=0.0):
        self.bpm, self.bars, self.bpb, self.swing = bpm, bars, beats_per_bar, swing
        self.beat = 60.0 / bpm
        self.length = bars * beats_per_bar * self.beat
        self.buses = {}

    def at(self, bar, beat):
        """bar from 0, beat from 0 (fractional ok); swing pushes off-8ths late."""
        b = beat
        if self.swing:
            frac = b % 1
            if abs(frac - 0.5) < 1e-6:
                b = b - 0.5 + 0.5 + self.swing * 0.5
        return (bar * self.bpb + b) * self.beat

    def bus(self, name):
        if name not in self.buses:
            self.buses[name] = np.zeros((2, n_of(self.length + 4.0)))
        return self.buses[name]

    def add(self, bus, bar, beat, sig, p=0.0, g=1.0):
        mix_into(self.bus(bus), self.at(bar, beat), pan(sig, p, g) if sig.ndim == 1 else sig * g)

    def render(self, sends, fx=None):
        """sends: {bus: (gain, reverb_mix)}; returns a seamless loop."""
        total = None
        for name, buf in self.buses.items():
            gain, rv = sends.get(name, (1.0, 0.15))
            x = buf * gain
            if rv:
                x = reverb(x, mix=rv, t60=1.6)
            total = x if total is None else _add(total, x)
        if fx:
            total = fx(total)
        # master tone: clear the sub rumble, add a little air on top (the
        # synthesized mixes measured dull — 1-4% of energy above 4 kHz)
        total = np.stack([sos_hp(ch, 32) for ch in total])
        total = total + 0.45 * np.stack([sos_hp(ch, 6500) for ch in total])
        L = n_of(self.length)
        loop = total[:, :L].copy()
        tail = total[:, L:]
        k = min(tail.shape[1], L)
        loop[:, :k] += tail[:, :k]   # fold the ring-out back onto the start: seamless
        return loop


def _add(a, b):
    n = max(a.shape[1], b.shape[1])
    out = np.zeros((2, n))
    out[:, :a.shape[1]] += a
    out[:, :b.shape[1]] += b
    return out


def voicing(ch, lo=52, hi=72):
    """Fold chord tones into [lo, hi] (MIDI) for a compact keyboard voicing."""
    out = []
    for m in ch:
        while m < lo:
            m += 12
        while m > hi:
            m -= 12
        out.append(m)
    return sorted(set(out))


# =============================================================================
# MUSIC

def bg_base_A():
    """Oval Office Funk — 104 bpm, E dorian: tight drums, slap bass, chicken-
    scratch guitar, e-piano stabs, a cheeky brass hook every 4 bars."""
    s = Song(104, 16)
    prog = [('E3', 'min9'), ('E3', 'min9'), ('A2', '13'), ('A2', '13'),
            ('E3', 'min9'), ('E3', 'min9'), ('C3', 'maj7'), ('B2', '7')] * 2
    for bar in range(16):
        root, kind = prog[bar]
        ch = chord(root, kind)
        # drums
        for b in (0, 1.75, 2.5):
            s.add('drums', bar, b, kick(0.95))
        for b in (1, 3):
            s.add('drums', bar, b, snare(0.85), 0.05)
        for b in (1.75, 3.25, 3.75):
            s.add('drums', bar, b, snare(0.18, snap=0.6, sec=0.1), 0.05)  # ghost notes
        for i in range(16):
            s.add('drums', bar, i / 4, hat(0.32 if i % 2 == 0 else 0.18, open_=(i == 14)), 0.35)
        # slap bass (16th syncopation)
        r = midi(root) - 12 if midi(root) > 50 else midi(root)
        pattern = [(0, 0, 0.3), (0.75, 0, 0.12), (1.5, 12, 0.12), (2, 7, 0.25), (2.75, 10, 0.12), (3.25, 12, 0.12), (3.5, 0, 0.2)]
        for b, iv, d in pattern:
            s.add('bass', bar, b, bass(float(hz(r + iv)), d + 0.05, 0.9, 'slap'))
        # guitar scratches on 16ths, chord tones dampened
        v = voicing(ch, 60, 76)
        for i in range(16):
            if i % 4 in (1, 3) or i in (6, 14):
                for k, m in enumerate(v[:3]):
                    s.add('gtr', bar, i / 4 + k * 0.004, pluck(float(hz(m)), 0.12, 0.35, bright=0.8, damp=0.9), -0.4 + 0.15 * k)
        # e-piano stabs
        for b in (0.5, 2.25):
            for m in voicing(ch, 55, 72):
                s.add('keys', bar, b, epiano(float(hz(m)), 0.45, 0.45), 0.3)
        # brass hook on bars 3, 7, 11, 15
        if bar % 4 == 3:
            hook = [(2.5, 'B4', 0.22), (3.0, 'D5', 0.22), (3.5, 'E5', 0.5)]
            for b, nt, d in hook:
                for iv, p in ((0, -0.2), (-5, 0.2)):
                    s.add('brass', bar, b, brass(midi(nt) + iv, d, 0.8), p)
    return s.render({'drums': (1.0, 0.08), 'bass': (0.9, 0.0), 'gtr': (0.55, 0.12), 'keys': (0.6, 0.25), 'brass': (0.55, 0.3)})


def bg_base_B():
    """Presidential Strut — 112 bpm, Bb major: a light ceremonial march with a
    wink. Snare cadence + timpani, oom-pah tuba, brass fanfare melody doubled
    by glockenspiel, string pad underneath."""
    s = Song(112, 16)
    prog = [('Bb2', 'maj'), ('Eb3', 'maj'), ('Bb2', 'maj'), ('F2', '7'),
            ('Bb2', 'maj'), ('Eb3', 'maj'), ('C3', 'min7'), ('F2', '7'),
            ('G2', 'min'), ('Eb3', 'maj'), ('Bb2', 'maj'), ('F2', '7'),
            ('Eb3', 'maj'), ('F2', '7'), ('Bb2', 'maj'), ('F2', '7')]
    melody = {  # bar: [(beat, note, dur)] — an original fanfare line
        0: [(0, 'F4', 0.5), (0.5, 'Bb4', 0.5), (1, 'D5', 1), (2.5, 'C5', 0.5), (3, 'Bb4', 1)],
        1: [(0, 'G4', 1), (1, 'Bb4', 0.5), (1.5, 'Eb5', 1.5), (3, 'D5', 1)],
        2: [(0, 'F4', 0.5), (0.5, 'Bb4', 0.5), (1, 'D5', 1), (2, 'F5', 1), (3, 'D5', 1)],
        3: [(0, 'C5', 1.5), (1.5, 'A4', 0.5), (2, 'F4', 2)],
        8: [(0, 'D5', 1), (1, 'Bb4', 1), (2, 'G4', 2)],
        9: [(0, 'Eb5', 1), (1, 'G5', 1), (2, 'F5', 1), (3, 'Eb5', 1)],
        10: [(0, 'D5', 0.5), (0.5, 'F5', 0.5), (1, 'Bb5', 1.5), (2.5, 'A5', 0.5), (3, 'F5', 1)],
        11: [(0, 'C5', 1), (1, 'D5', 0.5), (1.5, 'Eb5', 0.5), (2, 'F5', 2)],
        14: [(0, 'D5', 0.5), (0.5, 'C5', 0.5), (1, 'Bb4', 1), (2, 'F5', 0.5), (2.5, 'D5', 0.5), (3, 'Bb4', 1)],
    }
    for bar in range(16):
        root, kind = prog[bar]
        ch = chord(root, kind)
        # march drums: kick on 1/3, snare cadence
        for b in (0, 2):
            s.add('drums', bar, b, kick(0.7, tone=55))
        for b in (1, 3):
            s.add('drums', bar, b, snare(0.7, snap=1.2))
        for b in (0.5, 1.5, 2.5, 3.5):
            s.add('drums', bar, b, snare(0.22, snap=0.6, sec=0.1), 0.1)
        if bar % 4 == 3:
            s.add('drums', bar, 2, snare_roll(1.9, 0.45))
        if bar % 8 == 0:
            s.add('drums', bar, 0, crash(0.22), -0.3)
            s.add('perc', bar, 0, timpani(root[:-1] + '2', 0.8))
        # oom-pah tuba
        r = midi(root) - 12 if midi(root) >= 48 else midi(root)
        for b, iv in ((0, 0), (2, 7)):
            s.add('bass', bar, b, bass(float(hz(r + iv)), 0.45, 0.9, 'tuba'))
        for b in (1, 3):
            for m in voicing(ch, 58, 70):
                s.add('keys', bar, b, brass(m, 0.25, 0.32, bright=0.5), 0.25)
        # string pad
        for m in voicing(ch, 55, 67):
            s.add('pad', bar, 0, strings(float(hz(m)), s.bpb * s.beat, 0.25, attack=0.4), -0.2)
        for b, nt, d in melody.get(bar, []):
            dur = d * s.beat * 0.92
            s.add('lead', bar, b, brass(nt, dur, 0.85, bright=1.1), -0.1)
            s.add('lead', bar, b, glock(midi(nt) + 12, 0.6, 0.35), 0.35)
    return s.render({'drums': (0.9, 0.1), 'perc': (0.8, 0.3), 'bass': (0.8, 0.05), 'keys': (0.5, 0.2),
                     'pad': (0.45, 0.3), 'lead': (0.6, 0.28)})


def bg_base_C():
    """Gold Room Lounge — 92 bpm swing, F major: brushes and ride, walking
    upright bass, piano comping, vibraphone melody with a muted trumpet answer."""
    s = Song(92, 16, swing=0.33)
    prog = [('F3', 'maj7'), ('D3', 'min7'), ('G3', 'min7'), ('C3', '7'),
            ('A3', 'min7'), ('D3', '7'), ('G3', 'min7'), ('C3', '7')] * 2
    vib = {
        0: [(0, 'A4', 1.5), (1.5, 'C5', 0.5), (2, 'E5', 1.5)],
        1: [(0, 'D5', 1), (1, 'C5', 0.5), (1.5, 'A4', 2.5)],
        2: [(0, 'Bb4', 1), (1, 'D5', 1), (2, 'F5', 1.5), (3.5, 'E5', 0.5)],
        3: [(0, 'E5', 2), (2.5, 'G4', 0.5), (3, 'Bb4', 1)],
        8: [(0, 'C5', 1), (1, 'A4', 0.5), (1.5, 'F4', 1), (2.5, 'G4', 0.5), (3, 'A4', 1)],
        9: [(0, 'F5', 1.5), (1.5, 'E5', 0.5), (2, 'D5', 2)],
        10: [(0, 'Bb4', 0.5), (0.5, 'D5', 0.5), (1, 'F5', 1), (2, 'A5', 1), (3, 'G5', 1)],
        11: [(0, 'E5', 3)],
    }
    trumpet = {5: [(1, 'F#4', 0.5), (1.5, 'A4', 0.5), (2, 'C5', 1.5)], 13: [(1, 'A4', 0.5), (1.5, 'C5', 0.5), (2, 'Eb5', 1.5)],
               7: [(2, 'G4', 0.5), (2.5, 'Bb4', 0.5), (3, 'E5', 1)], 15: [(2, 'Bb4', 0.5), (2.5, 'G4', 0.5), (3, 'E4', 1)]}
    for bar in range(16):
        root, kind = prog[bar]
        ch = chord(root, kind)
        nxt = chord(*prog[(bar + 1) % 16])
        for b in range(4):
            s.add('drums', bar, b, ride(0.32 if b % 2 else 0.22), 0.3)
            s.add('drums', bar, b + 0.5, ride(0.16), 0.3) if b in (1, 3) else None
            s.add('drums', bar, b, brush(0.22), -0.2)
        for b in (1, 3):
            s.add('drums', bar, b, snare(0.12, snap=0.4, sec=0.12), -0.1)
        s.add('drums', bar, 0, kick(0.35, tone=48))
        # walking bass: root, 3rd/5th, approach to next root
        r = midi(root) - 12 if midi(root) >= 52 else midi(root)
        walk = [r, r + ch[1] - ch[0], r + 7, (nxt[0] - 12 if nxt[0] >= 52 else nxt[0]) - 1]
        for b, m in enumerate(walk):
            s.add('bass', bar, b, bass(float(hz(m)), s.beat * 0.95, 0.8, 'upright'))
        # piano comping (Charleston rhythm)
        for b in (0, 1.5) if bar % 2 == 0 else (0.5, 2.5):
            for m in voicing(ch, 55, 71):
                s.add('keys', bar, b, piano(m, 0.6, 0.35), 0.15)
        for b, nt, d in vib.get(bar, []):
            s.add('lead', bar, b, vibes(nt, d * s.beat + 0.6, 0.55), -0.15)
        for b, nt, d in trumpet.get(bar, []):
            s.add('horn', bar, b, brass(nt, d * s.beat, 0.55, bright=0.35, vib=0.006), 0.25)
    return s.render({'drums': (0.8, 0.12), 'bass': (0.85, 0.05), 'keys': (0.6, 0.22), 'lead': (0.6, 0.3), 'horn': (0.6, 0.35)})


def bg_bonus_A():
    """Penthouse Disco — 120 bpm, A minor: four-on-the-floor, octave bass,
    string stabs and runs, house piano, open hats — sunset over the skyline."""
    s = Song(120, 16)
    prog = [('A2', 'min7'), ('F2', 'maj7'), ('C3', 'maj'), ('G2', 'maj')] * 4
    for bar in range(16):
        root, kind = prog[bar]
        ch = chord(root, kind)
        for b in range(4):
            s.add('drums', bar, b, kick(1.0, tone=52))
            s.add('drums', bar, b + 0.5, hat(0.42, open_=True), 0.3)
            s.add('drums', bar, b + 0.25, hat(0.15), 0.3)
            s.add('drums', bar, b + 0.75, hat(0.15), 0.3)
        for b in (1, 3):
            s.add('drums', bar, b, clap(0.7), -0.05)
            s.add('drums', bar, b, snare(0.4))
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.3), 0.3)
        r = midi(root) - 12 if midi(root) >= 48 else midi(root)
        for i in range(8):
            m = r + (12 if i % 2 else 0)
            s.add('bass', bar, i / 2, bass(float(hz(m)), 0.22, 0.85, 'synth'))
        # house piano on the off-beats
        for b in (0.5, 1.75, 2.5, 3.5):
            for m in voicing(ch, 57, 74):
                s.add('keys', bar, b, piano(m, 0.35, 0.4), 0.2)
        # strings: sustained + a run into every 4th bar
        for m in voicing(ch, 60, 76):
            s.add('pad', bar, 0, strings(float(hz(m)), 2 * s.beat, 0.3, attack=0.05), -0.3)
        if bar % 4 == 3:
            scale = [0, 2, 3, 5, 7, 8, 10, 12]
            for i, iv in enumerate(scale):
                s.add('pad', bar, 2 + i * 0.25, strings(float(hz(midi('A4') + iv)), 0.2, 0.35, attack=0.01), 0.3)
        # sparkle on top
        if bar % 2 == 1:
            s.add('lead', bar, 3, sparkle(0.5, 'A6', 0.18), 0.4)
    return s.render({'drums': (1.0, 0.06), 'bass': (0.9, 0.0), 'keys': (0.55, 0.2), 'pad': (0.5, 0.3), 'lead': (0.5, 0.35)})


def bg_bonus_B():
    """Victory Parade — 128 bpm, D major: driving march-funk, snare drive and
    toms, big brass melody, timpani on the turnarounds."""
    s = Song(128, 16)
    prog = [('D3', 'maj'), ('G2', 'maj'), ('A2', 'maj'), ('D3', 'maj'),
            ('B2', 'min'), ('G2', 'maj'), ('E2', 'min7'), ('A2', '7')] * 2
    mel = {
        0: [(0, 'A4', 0.5), (0.5, 'D5', 0.5), (1, 'F#5', 1), (2, 'E5', 0.5), (2.5, 'D5', 0.5), (3, 'A4', 1)],
        1: [(0, 'B4', 1), (1, 'D5', 0.5), (1.5, 'G5', 1.5), (3, 'F#5', 1)],
        2: [(0, 'E5', 0.5), (0.5, 'F#5', 0.5), (1, 'G5', 0.5), (1.5, 'A5', 1.5), (3, 'E5', 1)],
        3: [(0, 'D5', 2), (2.5, 'A4', 0.5), (3, 'D5', 1)],
        4: [(0, 'F#5', 1), (1, 'D5', 0.5), (1.5, 'B4', 1.5), (3, 'D5', 1)],
        5: [(0, 'G5', 1), (1, 'B5', 1), (2, 'A5', 1), (3, 'G5', 1)],
        6: [(0, 'E5', 0.5), (0.5, 'G5', 0.5), (1, 'B5', 1), (2, 'A5', 0.5), (2.5, 'G5', 0.5), (3, 'E5', 1)],
        7: [(0, 'A5', 1.5), (1.5, 'G5', 0.5), (2, 'E5', 0.5), (2.5, 'C#5', 0.5), (3, 'A4', 1)],
    }
    for bar in range(16):
        root, kind = prog[bar]
        ch = chord(root, kind)
        for b in (0, 1.5, 2, 3.5):
            s.add('drums', bar, b, kick(0.95, tone=54))
        for b in (1, 3):
            s.add('drums', bar, b, snare(0.9, snap=1.3))
        for i in range(8):
            s.add('drums', bar, i / 2, hat(0.25), 0.3)
        for b in (2.5, 2.75, 3.25):
            s.add('drums', bar, b, snare(0.25, snap=0.5, sec=0.1))
        if bar % 4 == 3:
            for i, nt in enumerate(('A2', 'F#2', 'D2', 'A1')):
                s.add('drums', bar, 3 + i * 0.25, tom(nt, 0.7), -0.4 + 0.25 * i)
            s.add('perc', bar, 3, timpani('A2', 0.8, 1.2))
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.24), -0.3)
        r = midi(root) - 12 if midi(root) >= 48 else midi(root)
        for i, iv in enumerate((0, 0, 12, 0, 7, 0, 12, 10)):
            s.add('bass', bar, i / 2, bass(float(hz(r + iv)), 0.24, 0.9, 'slap'))
        for b in (0.5, 2.5):
            for m in voicing(ch, 57, 72):
                s.add('keys', bar, b, brass(m, 0.22, 0.4, bright=0.8), 0.25)
        for b, nt, d in mel.get(bar % 8, []):
            dur = d * s.beat * 0.9
            s.add('lead', bar, b, brass(nt, dur, 0.85, bright=1.2), -0.15)
            s.add('lead', bar, b, brass(midi(nt) - 12, dur, 0.5, bright=0.9), 0.15)
    return s.render({'drums': (1.0, 0.08), 'perc': (0.8, 0.3), 'bass': (0.85, 0.0), 'keys': (0.5, 0.2), 'lead': (0.55, 0.28)})


def bg_bonus_C():
    """Skyline Synthwave — 108 bpm, F# minor: gated drums, pulsing saw bass,
    wide pad, glassy arpeggio and a soaring lead — the night skyline."""
    s = Song(108, 16)
    prog = [('F#2', 'min'), ('D2', 'maj'), ('A2', 'maj'), ('E2', 'maj')] * 4
    lead = {
        4: [(0, 'C#5', 1.5), (1.5, 'E5', 0.5), (2, 'F#5', 2)],
        5: [(0, 'A5', 1), (1, 'F#5', 1), (2, 'E5', 2)],
        6: [(0, 'C#5', 1), (1, 'E5', 1), (2, 'A5', 1.5), (3.5, 'G#5', 0.5)],
        7: [(0, 'G#5', 3), (3, 'E5', 1)],
        12: [(0, 'F#5', 1.5), (1.5, 'A5', 0.5), (2, 'C#6', 2)],
        13: [(0, 'B5', 1), (1, 'A5', 1), (2, 'F#5', 2)],
        14: [(0, 'E5', 1), (1, 'A5', 1), (2, 'C#6', 1), (3, 'B5', 1)],
        15: [(0, 'G#5', 4)],
    }
    for bar in range(16):
        root, kind = prog[bar]
        ch = chord(root, kind)
        for b in (0, 1.5, 2):
            s.add('drums', bar, b, kick(0.6, tone=55))
        for b in (1, 3):
            sn = snare(0.8, tone=200, snap=1.5, sec=0.5)
            s.add('drums', bar, b, sn)
        for i in range(8):
            s.add('drums', bar, i / 2, hat(0.18), 0.25)
        r = midi(root) - 12 if midi(root) >= 45 else midi(root)
        for i in range(8):  # octave pulse, the classic synthwave bass
            s.add('bass', bar, i / 2, bass(float(hz(r + (12 if i % 2 else 0))), 0.2, 0.8, 'synth'))
        for m in voicing(ch, 57, 72):
            s.add('pad', bar, 0, strings(float(hz(m)), 4 * s.beat, 0.3, attack=0.6), RNG.uniform(-0.5, 0.5))
        arp = voicing(ch, 64, 84)
        for i in range(16):
            m = arp[i % len(arp)] + (12 if (i // len(arp)) % 2 else 0)
            s.add('arp', bar, i / 4, pluck(float(hz(m)), 0.25, 0.35, bright=0.9, damp=0.99), 0.4 if i % 2 else -0.4)
        for b, nt, d in lead.get(bar, []):
            s.add('lead', bar, b, saw_add(hz(nt), d * s.beat, fc=hz(nt) * 4, vib=0.005, detune=0.003)
                  * env(n_of(d * s.beat), a=0.03, d=0.1, s=0.8, r=0.1) * 0.6, 0.0)
    # Bass kept well under the pad/arp/lead: the first render measured 86% of
    # its energy below 120 Hz with the melody buried.
    loop = s.render({'drums': (0.85, 0.18), 'bass': (0.55, 0.0), 'pad': (0.65, 0.4), 'arp': (0.6, 0.3), 'lead': (0.65, 0.4)})
    return loop


# =============================================================================
# SFX — each returns stereo; helpers to build short pieces

def sfx(sec):
    return np.zeros((2, n_of(sec)))


def put(buf, at, sig, p=0.0, g=1.0):
    mix_into(buf, at, pan(sig, p, g) if sig.ndim == 1 else sig * g)


def finish(buf, rv=0.18, t60=1.2, trim_tail=True):
    out = reverb(buf, mix=rv, t60=t60) if rv else buf
    if trim_tail:
        a = np.abs(out).max(axis=0)
        th = a.max() * 0.002
        last = np.nonzero(a > th)[0]
        if len(last):
            out = out[:, :last[-1] + n_of(0.05)]
    k = n_of(0.01)
    out[:, -k:] *= np.linspace(1, 0, k)
    return out


def triad_hit(buf, at, root, kind, dur, vel=0.8, inst='brass', p=0.0):
    for i, m in enumerate(voicing(chord(root, kind), midi(root) + 12, midi(root) + 26)):
        if inst == 'brass':
            put(buf, at, brass(m, dur, vel), p + (i - 1) * 0.2)
        elif inst == 'strings':
            put(buf, at, strings(float(hz(m)), dur, vel, attack=0.02), p + (i - 1) * 0.25)
        elif inst == 'epiano':
            put(buf, at, epiano(float(hz(m)), dur, vel), p + (i - 1) * 0.2)
        elif inst == 'choir':
            put(buf, at, choir(float(hz(m)), dur, vel), p + (i - 1) * 0.25)


# ---- WIN --------------------------------------------------------------------

def win_line(v):
    b = sfx(1.2)
    if v == 'A':  # gold chime arpeggio
        for i, nt in enumerate(('C6', 'E6', 'G6')):
            put(b, i * 0.06, bell(nt, 0.9, 0.5), -0.3 + 0.3 * i)
        put(b, 0.0, coin(0.5), 0.2)
    elif v == 'B':  # brass blip + coins
        for m in ('G4', 'C5'):
            put(b, 0.0 if m == 'G4' else 0.08, brass(m, 0.18, 0.7), 0)
        put(b, 0.05, coin_shower(0.25, 30, 0.35, 1.1))
    else:  # e-piano sparkle + shaker
        for i, nt in enumerate(('E5', 'G#5', 'B5', 'E6')):
            put(b, i * 0.045, epiano(nt, 0.5, 0.5), -0.3 + 0.2 * i)
        put(b, 0.0, shaker(0.4))
    return finish(b, 0.2)


def win_big(v):
    b = sfx(3.4)
    if v == 'A':  # fanfare: three rising hits then a held major chord
        for i, (root, kind) in enumerate((('C4', 'maj'), ('F4', 'maj'), ('G4', 'maj'))):
            triad_hit(b, i * 0.18, root, kind, 0.16, 0.85)
        triad_hit(b, 0.56, 'C4', 'maj', 1.3, 0.9)
        put(b, 0.56, timpani('C2', 0.9))
        put(b, 0.56, crash(0.45), 0.3)
        put(b, 0.6, coin_shower(1.6, 26, 0.35, 1.0, rise=0.3), 0.0)
    elif v == 'B':  # funk band stab + register
        put(b, 0.0, kick(1.0))
        for i, root in enumerate(('Eb4', 'F4', 'G4')):
            triad_hit(b, i * 0.12, root, '9' if i < 2 else 'maj', 0.12, 0.8)
        triad_hit(b, 0.42, 'Ab4', 'maj7', 1.0, 0.9)
        put(b, 0.42, snare(0.9))
        put(b, 0.5, register_bell(0.7), 0.25)
        put(b, 0.7, coin_shower(1.2, 22, 0.3), -0.2)
    else:  # glittery orchestral swell
        put(b, 0.0, riser(0.5, 400, 8000, 0.4))
        triad_hit(b, 0.5, 'D4', 'maj', 1.6, 0.7, inst='strings')
        triad_hit(b, 0.5, 'D4', 'maj', 1.0, 0.75)
        put(b, 0.5, sparkle(1.0, 'D6', 0.35))
        put(b, 0.5, crash(0.4), -0.3)
    return finish(b, 0.25, 1.6)


def win_mega(v):
    b = sfx(4.6)
    if v == 'A':  # bigger fanfare with key lift and timpani roll
        for i, (root, kind) in enumerate((('C4', 'maj'), ('E4', 'min'), ('F4', 'maj'), ('G4', '7'))):
            triad_hit(b, i * 0.16, root, kind, 0.15, 0.85)
            put(b, i * 0.16, timpani('G2' if i == 3 else 'C2', 0.5, 0.6))
        triad_hit(b, 0.66, 'D4', 'maj', 0.18, 0.9)
        triad_hit(b, 0.86, 'D4', 'maj', 1.8, 0.95)
        triad_hit(b, 0.86, 'D4', 'maj', 2.0, 0.5, inst='strings')
        put(b, 0.86, crash(0.55), 0.3)
        put(b, 0.86, impact(0.6))
        put(b, 0.9, coin_shower(2.4, 32, 0.38, 1.0, rise=0.4))
    elif v == 'B':  # disco break: drum fill -> brass + choir 'aah'
        for i in range(8):
            put(b, i * 0.07, snare(0.35 + i * 0.07, snap=0.6, sec=0.12))
        put(b, 0.56, kick(1.0))
        triad_hit(b, 0.56, 'Bb3', 'maj9', 1.6, 0.85)
        triad_hit(b, 0.56, 'Bb3', 'maj', 1.9, 0.45, inst='choir')
        put(b, 0.6, register_bell(0.8), 0.3)
        put(b, 0.7, coin_shower(2.2, 30, 0.35, 1.05, rise=0.3), -0.2)
    else:  # synth riser -> drop with sparkle cascade
        put(b, 0.0, riser(0.9, 300, 9000, 0.5))
        put(b, 0.9, impact(0.9, 40))
        triad_hit(b, 0.9, 'F#3', 'maj', 1.8, 0.7, inst='strings')
        triad_hit(b, 0.9, 'F#4', 'maj', 1.2, 0.75)
        put(b, 0.9, sparkle(1.4, 'F#6', 0.3, steps=12))
        put(b, 0.9, crash(0.5), 0.3)
    return finish(b, 0.28, 2.0)


def win_epic(v):
    b = sfx(6.5)
    if v == 'A':  # full ceremonial: snare roll -> orchestra hit -> anthem chords
        put(b, 0.0, snare_roll(1.0, 0.55))
        put(b, 1.0, impact(1.0, 38))
        put(b, 1.0, crash(0.6, 3.0), 0.3)
        put(b, 1.0, timpani('D2', 1.0))
        for i, (root, kind, d) in enumerate((('D4', 'maj', 0.5), ('G4', 'maj', 0.5), ('A4', 'maj', 0.5), ('D4', 'maj', 2.6))):
            at = 1.0 + i * 0.5
            triad_hit(b, at, root, kind, d, 0.95)
            triad_hit(b, at, root, kind, d + 0.2, 0.45, inst='choir')
        put(b, 1.1, coin_shower(4.0, 34, 0.38, 1.0, rise=0.5))
    elif v == 'B':  # funk anthem: drum fill, brass shout chorus, register x2
        for i, nt in enumerate(('A2', 'F2', 'D2', 'A1')):
            put(b, i * 0.12, tom(nt, 0.8), -0.4 + 0.25 * i)
        put(b, 0.5, kick(1.0))
        put(b, 0.5, crash(0.55, 2.5), -0.3)
        for i, (root, kind) in enumerate((('C4', '9'), ('F4', '9'), ('G4', '13'), ('C4', 'maj9'))):
            triad_hit(b, 0.5 + i * 0.42, root, kind, 0.35 if i < 3 else 2.2, 0.9)
            put(b, 0.5 + i * 0.42, kick(0.8))
            put(b, 0.5 + i * 0.42 + 0.21, snare(0.6))
        put(b, 1.8, register_bell(0.8), -0.3)
        put(b, 2.3, register_bell(0.8), 0.3)
        put(b, 1.8, coin_shower(3.2, 34, 0.38, 1.0, rise=0.4))
    else:  # cosmic: long riser, choir + strings bloom, bell cascade
        put(b, 0.0, riser(1.4, 200, 10000, 0.55))
        put(b, 1.4, impact(1.0, 36))
        triad_hit(b, 1.4, 'E3', 'maj', 3.6, 0.6, inst='choir')
        triad_hit(b, 1.4, 'E3', 'maj', 3.6, 0.55, inst='strings')
        triad_hit(b, 1.4, 'E4', 'maj', 1.4, 0.7)
        put(b, 1.4, sparkle(2.4, 'E6', 0.32, steps=16))
        put(b, 1.4, crash(0.55, 3.0), 0.3)
        put(b, 1.6, coin_shower(3.0, 26, 0.3, 1.1))
    return finish(b, 0.3, 2.4)


def cash_loop(v):
    """Seamless ~1.2s counter loop while a win counts up."""
    L = 1.2
    b = sfx(L + 1.0)
    if v == 'A':  # fast coin trickle
        for i in range(24):
            put(b, i * L / 24, coin(0.45 * RNG.uniform(0.6, 1.0), RNG.uniform(0.95, 1.2)), RNG.uniform(-0.5, 0.5))
    elif v == 'B':  # mechanical counter ticks + soft bell every beat
        for i in range(16):
            tick = sos_bp(noise(0.012), 2500, 7000) * expdec(n_of(0.012), 0.003)
            put(b, i * L / 16, tick * (0.9 if i % 4 == 0 else 0.5), 0.1)
        for i in range(4):
            put(b, i * L / 4, glock('E6' if i % 2 == 0 else 'G6', 0.4, 0.25), -0.2)
    else:  # rising arpeggio ladder of glock + shaker 16ths
        seq = [0, 4, 7, 12, 16, 19, 24, 19]
        for i, iv in enumerate(seq):
            put(b, i * L / 8, glock(midi('C6') + iv, 0.4, 0.3), -0.3 + 0.08 * i)
        for i in range(16):
            put(b, i * L / 16, shaker(0.22), 0.3)
    out = reverb(b, 0.15, 0.8)
    L_n = n_of(L)
    loop = out[:, :L_n].copy()
    tail = out[:, L_n:L_n * 2]
    loop[:, :tail.shape[1]] += tail
    return loop


# ---- SCATTER ----------------------------------------------------------------

SCATTER_STEPS = {'A': ('C5', 'E5', 'G5'), 'B': ('G4', 'B4', 'D5'), 'C': ('A4', 'C#5', 'E5')}


def scatter_land(v, k):
    """k = 1, 2, 3 — each landing a step higher, the third the biggest."""
    b = sfx(1.6)
    nt = SCATTER_STEPS[v][k - 1]
    g = 0.6 + 0.15 * k
    if v == 'A':  # bell ping + grill sizzle (it's a burger)
        put(b, 0.0, bell(nt, 1.2, g), 0)
        put(b, 0.0, bell(midi(nt) + 12, 0.8, g * 0.4), 0.2)
        put(b, 0.02, sizzle(0.35 + 0.15 * k, 0.25), -0.2)
        if k == 3:
            put(b, 0.0, sparkle(0.4, 'C7', 0.25, steps=6))
    elif v == 'B':  # brass stab + timpani, bigger each time
        triad_hit(b, 0.0, nt, 'maj', 0.25 + 0.1 * k, g)
        put(b, 0.0, timpani(['G2', 'B2', 'D3'][k - 1], g * 0.8, 0.9))
        if k == 3:
            put(b, 0.0, crash(0.35), 0.3)
    else:  # synth pluck chord + whoosh up
        for i, m in enumerate(chord(nt, 'maj')):
            put(b, i * 0.02, pluck(float(hz(m)), 0.9, g * 0.6, bright=0.9, damp=0.998), -0.3 + 0.3 * i)
        put(b, 0.0, whoosh(0.25, 800, 6000, 0.25 * k))
        if k == 3:
            put(b, 0.0, sparkle(0.35, 'A6', 0.25, steps=5))
    return finish(b, 0.25, 1.4)


def scatter_win(v):
    b = sfx(3.5)
    if v == 'A':  # sizzle swell + bell fanfare
        put(b, 0.0, sizzle(1.2, 0.35))
        for i, nt in enumerate(('C5', 'E5', 'G5', 'C6', 'E6', 'G6')):
            put(b, 0.1 + i * 0.08, bell(nt, 1.4, 0.55), -0.4 + 0.16 * i)
        triad_hit(b, 0.6, 'C4', 'maj', 1.4, 0.6, inst='strings')
    elif v == 'B':  # brass fanfare + snare
        put(b, 0.0, snare_roll(0.45, 0.45))
        for i, (root, kind) in enumerate((('G4', 'maj'), ('G4', 'maj'), ('C5', 'maj'))):
            triad_hit(b, 0.45 + i * 0.14, root, kind, 0.12 if i < 2 else 1.4, 0.9)
        put(b, 0.73, crash(0.45), 0.3)
        put(b, 0.73, timpani('C2', 0.9))
    else:  # whoosh -> pluck arp -> pad bloom
        put(b, 0.0, whoosh(0.4, 500, 7000, 0.4))
        for i, m in enumerate([midi('A4') + iv for iv in (0, 4, 7, 12, 16, 19, 24)]):
            put(b, 0.35 + i * 0.06, pluck(float(hz(m)), 0.8, 0.45, bright=0.9, damp=0.998), -0.4 + 0.13 * i)
        triad_hit(b, 0.75, 'A3', 'maj', 1.6, 0.55, inst='strings')
        put(b, 0.75, sparkle(0.8, 'A6', 0.25))
    return finish(b, 0.28, 1.8)


# ---- WILD -> MULTIPLIER ---------------------------------------------------------

def wild_reveal(v):
    """Matches revealWildMultiplier: 220ms squeeze, then a 460ms pop."""
    b = sfx(1.8)
    if v == 'A':  # suck-in whoosh -> pop -> cha-ching
        put(b, 0.0, whoosh(0.22, 3000, 400, 0.5))
        pop = sine(np.geomspace(300, 1200, n_of(0.08)), 0.08) * expdec(n_of(0.08), 0.03)
        put(b, 0.22, pop, 0, 0.8)
        put(b, 0.24, register_bell(0.65), 0.15)
    elif v == 'B':  # brass 'ta-daa' + coin burst
        put(b, 0.0, whoosh(0.2, 600, 5000, 0.35))
        put(b, 0.2, brass('C5', 0.1, 0.7))
        triad_hit(b, 0.3, 'F4', 'maj', 0.6, 0.8)
        put(b, 0.3, coin_shower(0.4, 40, 0.35, 1.1))
    else:  # magic: reverse shimmer -> bell + sparkle
        sh = sparkle(0.22, 'C6', 0.3, steps=6)[::-1]
        put(b, 0.0, sh)
        put(b, 0.22, bell('G6', 1.2, 0.6, ratio=2.0))
        put(b, 0.22, bell('C6', 1.2, 0.5, ratio=2.0), 0.2)
        put(b, 0.25, sparkle(0.5, 'G6', 0.25, steps=7))
    return finish(b, 0.22, 1.2)


# ---- BONUS IN / OUT -------------------------------------------------------------

def bonus_enter(v):
    b = sfx(4.0)
    if v == 'A':  # riser -> impact -> fanfare (pairs with the blackout + FS popup)
        put(b, 0.0, riser(1.2, 200, 9000, 0.5))
        put(b, 0.0, snare_roll(1.2, 0.4))
        put(b, 1.2, impact(1.0))
        put(b, 1.2, crash(0.55, 2.5), 0.3)
        for i, (root, kind, d) in enumerate((('Bb3', 'maj', 0.18), ('Bb3', 'maj', 0.18), ('Eb4', 'maj', 0.18), ('F4', 'maj', 1.6))):
            triad_hit(b, 1.2 + i * 0.2, root, kind, d, 0.9)
    elif v == 'B':  # elevator 'ding' up to the penthouse + whoosh + disco hit
        put(b, 0.0, bell('E6', 1.2, 0.5, ratio=2.0))
        put(b, 0.25, bell('C6', 1.2, 0.5, ratio=2.0), 0.2)
        put(b, 0.5, riser(0.9, 300, 7000, 0.45))
        put(b, 1.4, kick(1.0))
        put(b, 1.4, clap(0.8))
        triad_hit(b, 1.4, 'A3', 'min9', 1.8, 0.8)
        triad_hit(b, 1.4, 'A3', 'min', 2.0, 0.5, inst='strings')
        put(b, 1.4, crash(0.45), -0.3)
    else:  # cinematic: low drone swell -> choir bloom + sparkle
        drone = saw_add(hz('D2'), 1.4, fc=np.geomspace(150, 2500, n_of(1.4)), harmonics=30) * np.linspace(0, 1, n_of(1.4)) ** 2
        put(b, 0.0, drone, 0, 0.6)
        put(b, 1.4, impact(0.9, 40))
        triad_hit(b, 1.4, 'D3', 'maj', 2.2, 0.6, inst='choir')
        triad_hit(b, 1.4, 'D4', 'maj', 1.4, 0.7)
        put(b, 1.4, sparkle(1.2, 'D6', 0.3, steps=10))
    return finish(b, 0.3, 2.0)


def bonus_exit(v):
    b = sfx(3.0)
    if v == 'A':  # descending sweep + warm resolve chord
        put(b, 0.0, downer(0.7, 6000, 300, 0.45))
        triad_hit(b, 0.5, 'F3', 'maj7', 1.8, 0.55, inst='epiano')
        put(b, 0.5, bell('C6', 1.4, 0.3))
    elif v == 'B':  # brass 'that's a wrap' cadence
        for i, (root, kind) in enumerate((('C4', 'maj'), ('G3', '7'), ('C4', 'maj'))):
            triad_hit(b, i * 0.3, root, kind, 0.25 if i < 2 else 1.2, 0.75)
        put(b, 0.6, timpani('C2', 0.7))
    else:  # elevator down: ding + soft lounge chord
        put(b, 0.0, bell('C6', 1.1, 0.45, ratio=2.0))
        put(b, 0.22, bell('E5', 1.1, 0.45, ratio=2.0), 0.2)
        put(b, 0.4, downer(0.6, 5000, 500, 0.3))
        triad_hit(b, 0.7, 'F3', 'maj9', 1.6, 0.4, inst='epiano')
    return finish(b, 0.28, 1.6)


# ---- UI ---------------------------------------------------------------------------

def ui_click(v):
    b = sfx(0.3)
    if v == 'A':  # glossy tick
        x = sine(2400, 0.03) * expdec(n_of(0.03), 0.006)
        x[:n_of(0.01)] += sos_bp(noise(0.01), 3000, 9000) * 0.3 * expdec(n_of(0.01), 0.002)
        put(b, 0, x, 0, 0.7)
    elif v == 'B':  # soft wooden tap
        x = sine(np.geomspace(900, 600, n_of(0.05)), 0.05) * expdec(n_of(0.05), 0.012)
        put(b, 0, x, 0, 0.8)
    else:  # tiny coin tick
        put(b, 0, coin(0.4, 1.4) * expdec(n_of(0.45), 0.04))
    return finish(b, 0.05, 0.4)


def ui_popup_open(v):
    b = sfx(0.8)
    if v == 'A':
        put(b, 0, whoosh(0.22, 700, 5000, 0.35))
        put(b, 0.12, bell('E6', 0.5, 0.25, ratio=2.0))
    elif v == 'B':
        for i, nt in enumerate(('C6', 'G6')):
            put(b, i * 0.05, glock(nt, 0.4, 0.35), -0.2 + 0.4 * i)
    else:
        put(b, 0, epiano('A5', 0.4, 0.35))
        put(b, 0.04, epiano('E6', 0.4, 0.3), 0.2)
    return finish(b, 0.15, 0.7)


def ui_popup_close(v):
    b = sfx(0.8)
    if v == 'A':
        put(b, 0, downer(0.22, 5000, 700, 0.35))
        put(b, 0.08, bell('B5', 0.4, 0.2, ratio=2.0))
    elif v == 'B':
        for i, nt in enumerate(('G6', 'C6')):
            put(b, i * 0.05, glock(nt, 0.4, 0.3), 0.2 - 0.4 * i)
    else:
        put(b, 0, epiano('E6', 0.35, 0.3), 0.2)
        put(b, 0.04, epiano('A5', 0.35, 0.3))
    return finish(b, 0.15, 0.7)


def ui_autospin(v):
    b = sfx(0.8)
    if v == 'A':  # two-tone 'armed' blip
        put(b, 0, sine(880, 0.06) * expdec(n_of(0.06), 0.03), 0, 0.5)
        put(b, 0.07, sine(1320, 0.09) * expdec(n_of(0.09), 0.04), 0, 0.5)
    elif v == 'B':  # quick reel-whirr
        x = saw_add(140, 0.3, fc=np.geomspace(500, 3000, n_of(0.3)), harmonics=30) * env(n_of(0.3), a=0.02, d=0, s=1, r=0.12)
        put(b, 0, x, 0, 0.35)
        put(b, 0.25, glock('A6', 0.3, 0.25))
    else:  # circular arpeggio
        for i, nt in enumerate(('E5', 'A5', 'C#6', 'E6')):
            put(b, i * 0.04, pluck(nt, 0.3, 0.3, bright=0.9), -0.3 + 0.2 * i)
    return finish(b, 0.12, 0.6)


def ui_bet(v, up):
    b = sfx(0.5)
    step = 1 if up else -1
    if v == 'A':  # pitched blip pair
        f0, f1 = (700, 1050) if up else (1050, 700)
        put(b, 0, sine(np.geomspace(f0, f1, n_of(0.07)), 0.07) * expdec(n_of(0.07), 0.04), 0, 0.5)
    elif v == 'B':  # chip clack (stacking up / taking off)
        put(b, 0, coin(0.35, 0.8 if up else 0.7) * expdec(n_of(0.45), 0.05))
        put(b, 0.04 if up else 0.0, coin(0.25, 0.95 if up else 0.65) * expdec(n_of(0.45), 0.04), 0.2)
    else:  # e-piano third up / down
        a, c = ('C6', 'E6') if up else ('E6', 'C6')
        put(b, 0, epiano(a, 0.2, 0.3))
        put(b, 0.05, epiano(c, 0.25, 0.3), 0.15 * step)
    return finish(b, 0.08, 0.5)


def ui_menu(v):
    b = sfx(0.6)
    if v == 'A':  # paper/folder slide (executive folder)
        put(b, 0, sos_bp(noise(0.14), 1200, 6000) * env(n_of(0.14), a=0.03, d=0, s=1, r=0.08), 0, 0.35)
        put(b, 0.1, sine(1600, 0.03) * expdec(n_of(0.03), 0.008), 0, 0.4)
    elif v == 'B':  # soft pluck
        put(b, 0, pluck('G5', 0.4, 0.35, bright=0.7))
    else:  # airy whoosh
        put(b, 0, whoosh(0.18, 1200, 6000, 0.3))
    return finish(b, 0.1, 0.5)


def ui_turbo(v):
    b = sfx(0.9)
    if v == 'A':  # zippy rising zap
        x = saw_add(200, 0.25, fc=np.geomspace(600, 7000, n_of(0.25)), harmonics=40, vib=0.0)
        x *= env(n_of(0.25), a=0.01, d=0, s=1, r=0.08)
        f = np.geomspace(300, 2400, n_of(0.25))
        put(b, 0, sine(f, 0.25) * env(n_of(0.25), a=0.01, d=0, s=1, r=0.08) * 0.5 + x * 0.25, 0, 0.6)
    elif v == 'B':  # jet whoosh (Air Force Uni)
        put(b, 0, whoosh(0.45, 300, 8000, 0.5))
        put(b, 0.0, sine(np.geomspace(150, 900, n_of(0.45)), 0.45) * np.sin(np.pi * tt(0.45) / 0.45) * 0.2)
    else:  # electric spark + blip
        crk = np.zeros(n_of(0.2))
        for _ in range(10):
            j = RNG.integers(0, len(crk) - 100)
            crk[j:j + 80] += RNG.uniform(-1, 1) * expdec(80, 0.0005)
        put(b, 0, sos_hp(crk, 2000), 0, 0.6)
        put(b, 0.1, sine(1760, 0.08) * expdec(n_of(0.08), 0.04), 0, 0.45)
    return finish(b, 0.1, 0.6)


# ---- REELS: spin start, stops (a melody across the reels), last reel, anticipation

# Reels 1-4 stop on rising notes, the 5th lands on a resolving chord — so a
# whole spin plays a little phrase. Timing in the game: reel stops 110ms
# apart (REEL_LAND_STAGGER_MS), anticipation ~1.65s (900ms pre-roll + 750ms).
REEL_NOTES = {
    'A': ['C4', 'E4', 'G4', 'B4'],          # warm marimba-ish thump, Cmaj7 climb
    'B': ['C6', 'D6', 'E6', 'G6'],          # glockenspiel pentatonic steps
    'C': ['E5', 'G5', 'B5', 'D6'],          # e-piano, Em9 tones (the base track's key)
}
REEL_LAST = {'A': ('C4', 'maj9'), 'B': ('C5', 'maj'), 'C': ('E4', 'min9')}


def thump(vel=0.8, tone=90):
    """The physical part of a reel stop: short low body + tiny wood click."""
    sec = 0.18
    t = tt(sec)
    x = sine(tone * (1 + 0.6 * np.exp(-t / 0.012)), sec) * expdec(len(t), 0.045)
    x[:n_of(0.004)] += sos_bp(noise(0.004), 1500, 6000) * 0.5
    return x * vel


def marimba(note, sec=0.6, vel=0.7):
    f = hz(note)
    t = tt(sec)
    n = len(t)
    x = np.sin(2 * np.pi * f * t) * expdec(n, 0.35) + 0.3 * np.sin(2 * np.pi * f * 4 * t) * expdec(n, 0.05)
    return x * env(n, a=0.002, d=0, s=1, r=0.05) * vel


def reel_stop(v, k):
    """k = 1..4 (reels 1-4)."""
    b = sfx(0.9)
    nt = REEL_NOTES[v][k - 1]
    p = -0.5 + 0.25 * (k - 1)
    if v == 'A':
        put(b, 0, thump(0.85, 85), p)
        put(b, 0, marimba(nt, 0.6, 0.55), p)
    elif v == 'B':
        put(b, 0, thump(0.7, 100), p)
        put(b, 0, glock(nt, 0.6, 0.45), p)
    else:
        put(b, 0, thump(0.75, 95), p)
        put(b, 0, epiano(nt, 0.55, 0.45), p)
    return finish(b, 0.12, 0.8)


def reel_stop_last(v):
    b = sfx(1.6)
    root, kind = REEL_LAST[v]
    put(b, 0, thump(1.0, 70), 0.5)
    put(b, 0, kick(0.5, tone=55), 0.5)
    if v == 'A':
        for i, m in enumerate(voicing(chord(root, kind), 60, 76)):
            put(b, i * 0.015, marimba(m, 0.9, 0.45), -0.3 + 0.2 * i)
    elif v == 'B':
        for i, m in enumerate(voicing(chord(root, kind), 72, 88)):
            put(b, i * 0.03, glock(m, 0.9, 0.4), -0.3 + 0.3 * i)
        put(b, 0.0, bell('C7', 1.0, 0.25, ratio=2.0))
    else:
        for i, m in enumerate(voicing(chord(root, kind), 62, 78)):
            put(b, i * 0.012, epiano(float(hz(m)), 1.0, 0.4), -0.3 + 0.15 * i)
    return finish(b, 0.2, 1.2)


def spin_start(v):
    b = sfx(0.9)
    if v == 'A':  # lever pull: ratchet clicks + whoosh down (reels drop out)
        for i in range(6):
            tick = sos_bp(noise(0.01), 2000, 7000) * expdec(n_of(0.01), 0.003)
            put(b, i * 0.025, tick, 0, 0.7 - 0.08 * i)
        put(b, 0.05, downer(0.3, 3500, 400, 0.45))
    elif v == 'B':  # brass 'bap' + whoosh — the band kicks the spin off
        put(b, 0, brass('G4', 0.09, 0.6))
        put(b, 0, brass('D5', 0.09, 0.45), 0.2)
        put(b, 0.04, whoosh(0.3, 500, 4500, 0.4))
    else:  # coin flip + whirr
        put(b, 0, coin(0.45, 1.2))
        x = saw_add(220, 0.35, fc=np.geomspace(3500, 600, n_of(0.35)), harmonics=30)
        put(b, 0.03, x * env(n_of(0.35), a=0.01, d=0, s=1, r=0.2), 0, 0.3)
    return finish(b, 0.1, 0.6)


def anticipation(v):
    """~1.8s of rising tension while the last reel keeps spinning."""
    L = 1.8
    b = sfx(L + 0.6)
    if v == 'A':  # tremolo strings climbing + snare roll crescendo
        for i, m in enumerate((midi('E4'), midi('B4'), midi('E5'))):
            f = hz(m) * np.geomspace(1.0, 2 ** (5 / 12), n_of(L))
            x = 0
            for dt in (-0.004, 0.0, 0.004):
                x = x + np.sin(2 * np.pi * np.cumsum(f * (1 + dt)) / SR) + 0.4 * np.sin(4 * np.pi * np.cumsum(f * (1 + dt)) / SR)
            trem = 0.55 + 0.45 * np.sin(2 * np.pi * 14 * tt(L))
            put(b, 0, x / 3 * trem * np.linspace(0.3, 1.0, n_of(L)), -0.3 + 0.3 * i, 0.35)
        put(b, 0, snare_roll(L, 0.35))
    elif v == 'B':  # synth riser + heartbeat kicks speeding up
        put(b, 0, riser(L, 250, 7000, 0.55))
        at = 0.0
        gap = 0.42
        while at < L - 0.05:
            put(b, at, kick(0.42, tone=52))
            put(b, at + 0.12, kick(0.26, tone=52))
            at += gap
            gap *= 0.8
    else:  # ticking clock + glock trill rising
        for i in range(int(L / 0.15)):
            tick = sos_bp(noise(0.008), 3000, 8000) * expdec(n_of(0.008), 0.002)
            put(b, i * 0.15, tick, 0.3 if i % 2 else -0.3, 0.6)
        for i in range(int(L / 0.06)):
            m = midi('A5') + (i * 7 // int(L / 0.06)) + (3 if i % 2 else 0)
            put(b, i * 0.06, glock(m, 0.25, 0.12 + 0.2 * i / (L / 0.06)), 0.2 if i % 2 else -0.2)
        put(b, 0, riser(L, 400, 5000, 0.25))
    out = finish(b, 0.15, 0.9)
    return out


def reels_demo(v):
    """How a whole spin sounds: start, four stops, last reel."""
    b = sfx(3.2)
    put(b, 0.0, spin_start(v))
    for k in range(1, 5):
        put(b, 0.75 + 0.11 * (k - 1), reel_stop(v, k))
    put(b, 0.75 + 0.11 * 4, reel_stop_last(v))
    return b


def reels_demo_anticipation(v):
    """Same spin, but the last reel waits on the anticipation first."""
    b = sfx(5.0)
    put(b, 0.0, spin_start(v))
    for k in range(1, 5):
        put(b, 0.75 + 0.11 * (k - 1), reel_stop(v, k))
    put(b, 1.2, anticipation(v))
    put(b, 1.2 + 1.65, reel_stop_last(v))
    return b


# =============================================================================
# catalogue

V = ('A', 'B', 'C')
MUSIC_TITLES = {
    'bg_base': {'A': 'Oval Office Funk — фанк 104 bpm: слэп-бас, гитара-«чёс», электропиано, медный хук',
                'B': 'Presidential Strut — торжественный марш с подмигиванием 112 bpm: туба, малый барабан, фанфара + колокольчики',
                'C': 'Gold Room Lounge — лаунж-джаз 92 bpm свинг: щётки, контрабас, рояль, вибрафон и сурдина'},
    'bg_bonus': {'A': 'Penthouse Disco — диско 120 bpm: бочка в пол, октавный бас, струнные, хаус-рояль',
                 'B': 'Victory Parade — марш-фанк 128 bpm: большая медь, томы, литавры',
                 'C': 'Skyline Synthwave — синтвейв 108 bpm: пульсирующий бас, пэд, арпеджио, лид'},
}

SFX_CATALOG = [
    # group, name, title, builder, variant descriptions
    ('win', 'win_line', 'Линия выиграла', win_line,
     {'A': 'золотые колокольчики + монета', 'B': 'медный «блип» + горсть монет', 'C': 'электропиано-арпеджио + шейкер'}),
    ('win', 'win_big', 'BIG WIN', win_big,
     {'A': 'фанфара: три удара и аккорд, литавры, монеты', 'B': 'фанк-брасс + касса «ча-чинг»', 'C': 'нарастание → струнные и медь, блёстки'}),
    ('win', 'win_mega', 'MEGA WIN', win_mega,
     {'A': 'большая фанфара с модуляцией и литаврами', 'B': 'диско-брейк: дробь → медь + хор «а-а»', 'C': 'синт-нарастание → дроп с каскадом блёсток'}),
    ('win', 'win_epic', 'EPIC WIN', win_epic,
     {'A': 'церемония: дробь → оркестровый удар → гимн с хором', 'B': 'фанк-гимн: брасс-шаут, касса ×2', 'C': 'космос: долгий подъём, хор и струнные, каскад колокольчиков'}),
    ('win', 'cash_loop', 'Кэш-луп (счётчик суммы)', cash_loop,
     {'A': 'сыплются монеты', 'B': 'механический счётчик + колокольчик', 'C': 'лесенка глокеншпиля + шейкер'}),
    ('scatter', 'scatter_1', 'Скаттер 1', lambda v: scatter_land(v, 1),
     {'A': 'колокольчик + шкворчание гриля', 'B': 'медный стаб + литавра', 'C': 'синт-щипок + свист'}),
    ('scatter', 'scatter_2', 'Скаттер 2', lambda v: scatter_land(v, 2),
     {'A': 'то же, ступенью выше', 'B': 'то же, ступенью выше', 'C': 'то же, ступенью выше'}),
    ('scatter', 'scatter_3', 'Скаттер 3', lambda v: scatter_land(v, 3),
     {'A': 'самый высокий + блёстки', 'B': 'самый высокий + тарелка', 'C': 'самый высокий + блёстки'}),
    ('scatter', 'scatter_win', 'Скаттер выиграл', scatter_win,
     {'A': 'шкворчание + фанфара колокольчиков', 'B': 'дробь + медная фанфара', 'C': 'свист → арпеджио → пэд'}),
    ('wild', 'wild_multiplier', 'WILD превращается в множитель', wild_reveal,
     {'A': 'втягивание → «поп» → касса', 'B': 'свист → медное «та-дам» + монеты', 'C': 'обратное мерцание → колокол + блёстки'}),
    ('bonus', 'bonus_enter', 'Вход в бонус', bonus_enter,
     {'A': 'подъём + дробь → удар → фанфара', 'B': 'лифт «динь» в пентхаус → диско-удар', 'C': 'кино: гул → хор + блёстки'}),
    ('bonus', 'bonus_exit', 'Выход из бонуса', bonus_exit,
     {'A': 'нисходящий свип + тёплый аккорд', 'B': 'медная каденция «финал»', 'C': 'лифт вниз «динь» + лаунж-аккорд'}),
    ('reels', 'spin_start', 'Звук спина', spin_start,
     {'A': 'рычаг: трещотка + свист вниз', 'B': 'медное «бап» + свист', 'C': 'подброшенная монета + жужжание'}),
    ('reels', 'reel_stops', 'Приземление барабанов 1–4 (демо подряд)', lambda v: reels_demo(v),
     {'A': 'глухой стук + маримба, ноты вверх C-E-G-B, финал — аккорд', 'B': 'стук + глокеншпиль ступенями C-D-E-G, финал — аккорд и колокол',
      'C': 'стук + электропиано по тонам Em9 (тональность базы), финал — аккорд'}),
    ('reels', 'reel_stop_last', 'Последний барабан', reel_stop_last,
     {'A': 'аккорд маримбы + удар', 'B': 'аккорд глокеншпиля + колокол', 'C': 'аккорд электропиано + удар'}),
    ('reels', 'anticipation', 'Антисипация', anticipation,
     {'A': 'струнные тремоло вверх + дробь крещендо', 'B': 'синт-подъём + «сердцебиение», всё чаще', 'C': 'тиканье часов + трель глокеншпиля вверх'}),
    ('reels', 'reels_demo_anticipation', 'Демо: спин с антисипацией', lambda v: reels_demo_anticipation(v),
     {'A': 'всё вместе, вариант A', 'B': 'всё вместе, вариант B', 'C': 'всё вместе, вариант C'}),
    ('ui', 'ui_click', 'Клик', ui_click, {'A': 'глянцевый тик', 'B': 'мягкий деревянный стук', 'C': 'монетный тик'}),
    ('ui', 'ui_popup_open', 'Попап — открыть', ui_popup_open, {'A': 'свист + колокольчик', 'B': 'глокеншпиль вверх', 'C': 'электропиано вверх'}),
    ('ui', 'ui_popup_close', 'Попап — закрыть', ui_popup_close, {'A': 'свист вниз + колокольчик', 'B': 'глокеншпиль вниз', 'C': 'электропиано вниз'}),
    ('ui', 'ui_autospin', 'Автоспин', ui_autospin, {'A': 'двухтоновый «взвёл»', 'B': 'жужжание барабана + динь', 'C': 'круговое арпеджио'}),
    ('ui', 'ui_bet_plus', 'Ставка +', lambda v: ui_bet(v, True), {'A': 'блип вверх', 'B': 'фишки кладутся', 'C': 'терция вверх'}),
    ('ui', 'ui_bet_minus', 'Ставка −', lambda v: ui_bet(v, False), {'A': 'блип вниз', 'B': 'фишки снимаются', 'C': 'терция вниз'}),
    ('ui', 'ui_menu', 'Меню', ui_menu, {'A': 'папка-«шурх» + щелчок', 'B': 'мягкий щипок', 'C': 'лёгкий свист'}),
    ('ui', 'ui_turbo', 'Турбо', ui_turbo, {'A': 'быстрый «зззип» вверх', 'B': 'свист реактивного самолёта', 'C': 'искра + блип'}),
]


def write_mp3(path, st, kbps=160):
    st = np.asarray(st)
    if st.ndim == 1:
        st = pan(st)
    pcm = (np.clip(st.T, -1, 1) * 32767).astype('<i2')
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps)
    enc.set_in_sample_rate(SR)
    enc.set_channels(2)
    enc.set_quality(2)
    data = enc.encode(pcm.tobytes()) + enc.flush()
    with open(path, 'wb') as f:
        f.write(data)
    return st.shape[1] / SR


def main(groups):
    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, 'manifest.json')
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    builders = {'bg_base': {'A': bg_base_A, 'B': bg_base_B, 'C': bg_base_C},
                'bg_bonus': {'A': bg_bonus_A, 'B': bg_bonus_B, 'C': bg_bonus_C}}
    if not groups or 'music' in groups:
        os.makedirs(os.path.join(OUT, 'music'), exist_ok=True)
        for name, fns in builders.items():
            for v, fn in fns.items():
                st = soft_master(fn(), drive=1.1, peak=0.85)
                sec = write_mp3(os.path.join(OUT, 'music', f'{name}_{v}.mp3'), st, 192)
                manifest[f'music/{name}_{v}'] = {'group': 'music', 'name': name, 'variant': v,
                                                 'title': 'BG base' if name == 'bg_base' else 'BG bonus',
                                                 'desc': MUSIC_TITLES[name][v], 'sec': round(sec, 2), 'loop': True}
                print(name, v, f'{sec:.1f}s')
    for group, name, title, fn, descs in SFX_CATALOG:
        if groups and group not in groups:
            continue
        os.makedirs(os.path.join(OUT, group), exist_ok=True)
        for v in V:
            st = soft_master(fn(v), drive=0.9, peak=0.89)
            sec = write_mp3(os.path.join(OUT, group, f'{name}_{v}.mp3'), st)
            manifest[f'{group}/{name}_{v}'] = {'group': group, 'name': name, 'variant': v, 'title': title,
                                               'desc': descs[v], 'sec': round(sec, 2), 'loop': name == 'cash_loop'}
        print(group, name)
    if not groups or 'reels' in groups:
        # The game plays one file per reel (reels 1-4 climb, see REEL_NOTES):
        # export them individually as well; the page only shows the demos.
        for v in V:
            for k in range(1, 5):
                write_mp3(os.path.join(OUT, 'reels', f'reel_stop_{k}_{v}.mp3'), soft_master(reel_stop(v, k), drive=0.9, peak=0.89))
    json.dump(manifest, open(man_path, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
