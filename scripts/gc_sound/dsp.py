"""Tiny numpy synth kit for procedurally made slot sounds (Gangsta Casino pack).

Everything is float64 mono arrays at SR unless a function says stereo
(shape (n, 2)). No external audio tools are needed: scripts/gc_sound/pack.py
renders, this module only makes and shapes signals.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

SR = 44100
A4 = 440.0
NOTE_NAMES = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4, "F#": -3,
              "Gb": -3, "G": -2, "G#": -1, "Ab": -1, "A": 0, "A#": 1, "Bb": 1, "B": 2}


def hz(note: str | float) -> float:
    """'A4', 'C#3' or a MIDI-ish float -> Hz."""
    if isinstance(note, (int, float)):
        return A4 * 2 ** ((note - 69) / 12)
    name, octave = note[:-1], int(note[-1])
    return A4 * 2 ** ((NOTE_NAMES[name] + (octave - 4) * 12) / 12)


def midi(note: str) -> int:
    name, octave = note[:-1], int(note[-1])
    return 69 + NOTE_NAMES[name] + (octave - 4) * 12


def n_of(dur: float) -> int:
    return max(1, int(round(dur * SR)))


def silence(dur: float) -> np.ndarray:
    return np.zeros(n_of(dur))


def tvec(dur: float) -> np.ndarray:
    return np.arange(n_of(dur)) / SR


def _freq_arr(freq, n):
    if callable(freq):
        return np.asarray(freq(np.arange(n) / SR), dtype=float)
    f = np.asarray(freq, dtype=float)
    if f.ndim == 0:
        return np.full(n, float(f))
    # a shorter curve holds its last value (a sweep that ends before the note)
    return f[:n] if len(f) >= n else np.concatenate([f, np.full(n - len(f), f[-1])])


def sweep(f0: float, f1: float, dur: float, curve: str = "exp") -> np.ndarray:
    x = np.linspace(0, 1, n_of(dur))
    if curve == "exp":
        return f0 * (f1 / f0) ** x
    return f0 + (f1 - f0) * x


def osc(kind: str, freq, dur: float, phase: float = 0.0, pw: float = 0.5) -> np.ndarray:
    n = n_of(dur)
    f = _freq_arr(freq, n)
    ph = (phase + np.cumsum(f) / SR) % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    if kind == "tri":
        return 2 * np.abs(2 * ph - 1) - 1
    if kind == "saw":  # polyBLEP-free but softened by a gentle LP later
        return 2 * ph - 1
    if kind == "square":
        return np.where(ph < pw, 1.0, -1.0)
    raise ValueError(kind)


def supersaw(freq, dur: float, voices: int = 7, detune: float = 0.18, rng=None) -> np.ndarray:
    rng = rng or np.random.default_rng(1)
    out = np.zeros(n_of(dur))
    base = _freq_arr(freq, n_of(dur))
    for v in range(voices):
        d = (v - (voices - 1) / 2) / max(1, voices - 1) * detune
        out += osc("saw", base * 2 ** (d / 12 * 2), dur, phase=rng.random())
    return out / np.sqrt(voices)


def fm(carrier, ratio: float, index, dur: float) -> np.ndarray:
    n = n_of(dur)
    fc = _freq_arr(carrier, n)
    idx = _freq_arr(index, n)
    ph_m = np.cumsum(fc * ratio) / SR
    mod = np.sin(2 * np.pi * ph_m) * idx
    ph_c = np.cumsum(fc) / SR
    return np.sin(2 * np.pi * ph_c + mod)


def noise(dur: float, rng=None, color: str = "white") -> np.ndarray:
    rng = rng or np.random.default_rng(7)
    x = rng.standard_normal(n_of(dur))
    if color == "pink":
        b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
        x = signal.lfilter(b, a, x) * 3
    elif color == "brown":
        x = signal.sosfilt(signal.butter(1, 30, "highpass", fs=SR, output="sos"), np.cumsum(x))
        x /= (np.max(np.abs(x)) + 1e-9)
    return x


# --- envelopes ---------------------------------------------------------------

def env_exp(dur: float, decay: float, attack: float = 0.002) -> np.ndarray:
    t = tvec(dur)
    e = np.exp(-t / max(decay, 1e-4))
    na = n_of(attack)
    e[:na] *= np.linspace(0, 1, na)
    return e


def adsr(dur: float, a: float = 0.01, d: float = 0.1, s: float = 0.7, r: float = 0.2) -> np.ndarray:
    n = n_of(dur)
    na, nd, nr = n_of(a), n_of(d), n_of(r)
    ns = max(0, n - na - nd - nr)
    e = np.concatenate([np.linspace(0, 1, na), np.linspace(1, s, nd), np.full(ns, s), np.linspace(s, 0, nr)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def fade(x: np.ndarray, fin: float = 0.002, fout: float = 0.01) -> np.ndarray:
    x = x.copy()
    a, b = min(len(x), n_of(fin)), min(len(x), n_of(fout))
    x[:a] *= np.linspace(0, 1, a)[:, None] if x.ndim == 2 else np.linspace(0, 1, a)
    x[len(x) - b:] *= np.linspace(1, 0, b)[:, None] if x.ndim == 2 else np.linspace(1, 0, b)
    return x


# --- filters -----------------------------------------------------------------

def _sos(kind, f, q=0.707):
    f = float(np.clip(f, 20, SR / 2 * 0.95))
    if kind == "bp":
        bw = f / max(q, 0.1)
        lo, hi = max(20, f - bw / 2), min(SR / 2 * 0.95, f + bw / 2)
        return signal.butter(2, [lo, hi], btype="bandpass", fs=SR, output="sos")
    return signal.butter(2, f, btype={"lp": "lowpass", "hp": "highpass"}[kind], fs=SR, output="sos")


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, min(f, SR * 0.47), "lowpass", fs=SR, output="sos"), x, axis=0)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "highpass", fs=SR, output="sos"), x, axis=0)


def bp(x, f, q=2.0):
    return signal.sosfilt(_sos("bp", f, q), x, axis=0)


def resonant_lp(x: np.ndarray, cutoff, q: float = 4.0, block: int = 128) -> np.ndarray:
    """Time-varying resonant low-pass (RBJ biquad, coefficients per block)."""
    n = len(x)
    c = _freq_arr(cutoff, n)
    y = np.zeros_like(x)
    z = np.zeros(2)
    for s in range(0, n, block):
        f = float(np.clip(c[s], 30, SR * 0.45))
        w = 2 * np.pi * f / SR
        alpha = np.sin(w) / (2 * q)
        cw = np.cos(w)
        b = np.array([(1 - cw) / 2, 1 - cw, (1 - cw) / 2])
        a = np.array([1 + alpha, -2 * cw, 1 - alpha])
        seg, z = signal.lfilter(b / a[0], a / a[0], x[s:s + block], zi=z)
        y[s:s + block] = seg
    return y


def bp_sweep(x, f, q=4.0, block=128):
    n = len(x)
    c = _freq_arr(f, n)
    y = np.zeros_like(x)
    z = np.zeros(2)
    for s in range(0, n, block):
        fc = float(np.clip(c[s], 40, SR * 0.45))
        w = 2 * np.pi * fc / SR
        alpha = np.sin(w) / (2 * q)
        b = np.array([alpha, 0, -alpha])
        a = np.array([1 + alpha, -2 * np.cos(w), 1 - alpha])
        seg, z = signal.lfilter(b / a[0], a / a[0], x[s:s + block], zi=z)
        y[s:s + block] = seg
    return y


# --- effects -----------------------------------------------------------------

def drive(x, amount=2.0):
    return np.tanh(x * amount) / np.tanh(amount)


def crush(x, bits=6, down=4):
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    return np.repeat(y[::down], down)[:len(x)]


def delay(x, time=0.18, fb=0.35, mix=0.3, tail=0.8):
    d = n_of(time)
    out = np.concatenate([x, np.zeros(n_of(tail))])
    wet = np.zeros_like(out)
    src = out.copy()
    g = 1.0
    for k in range(1, 12):
        g *= fb
        if g < 0.01:
            break
        sh = d * k
        if sh >= len(out):
            break
        wet[sh:] += src[:len(out) - sh] * g
    return out + wet * mix / max(fb, 1e-3) * fb


_IR_CACHE: dict = {}


def reverb(x, size=1.2, mix=0.25, bright=6000, seed=3, stereo=False):
    key = (size, bright, seed, stereo)
    if key not in _IR_CACHE:
        rng = np.random.default_rng(seed)
        n = n_of(size)
        t = np.arange(n) / SR
        e = np.exp(-t * 6.9 / size)
        chans = []
        for c in range(2 if stereo else 1):
            ir = rng.standard_normal(n) * e
            ir = lp(ir, bright)
            ir[: n_of(0.008)] *= np.linspace(0, 1, n_of(0.008))
            chans.append(ir / np.sqrt(np.sum(ir ** 2)))
        _IR_CACHE[key] = chans
    irs = _IR_CACHE[key]
    if x.ndim == 1 and not stereo:
        wet = signal.fftconvolve(x, irs[0])
        dry = np.pad(x, (0, len(wet) - len(x)))
        return dry * (1 - mix) + wet * mix
    mono = x if x.ndim == 1 else x.mean(axis=1)
    src = np.stack([x, x], 1) if x.ndim == 1 else x
    wet = np.stack([signal.fftconvolve(mono, ir) for ir in irs], 1)
    dry = np.pad(src, ((0, len(wet) - len(src)), (0, 0)))
    return dry * (1 - mix) + wet * mix


def pad_to(x, n):
    if len(x) >= n:
        return x[:n]
    w = ((0, n - len(x)),) + (((0, 0),) if x.ndim == 2 else ())
    return np.pad(x, w)


def mix(*parts):
    """mix((sig, t0, gain), ...) -> one buffer."""
    end = max(n_of(t0) + len(s) for s, t0, *_ in parts)
    stereo = any(s.ndim == 2 for s, *_ in parts)
    out = np.zeros((end, 2)) if stereo else np.zeros(end)
    for p in parts:
        s, t0 = p[0], p[1]
        g = p[2] if len(p) > 2 else 1.0
        if stereo and s.ndim == 1:
            s = np.stack([s, s], 1)
        i = n_of(t0)
        out[i:i + len(s)] += s * g
    return out


def pan(x, p=0.0):
    """mono -> stereo, p in [-1, 1]."""
    l, r = np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)
    return np.stack([x * l, x * r], 1)


def normalize(x, peak_db=-1.0):
    m = np.max(np.abs(x)) + 1e-12
    return x / m * 10 ** (peak_db / 20)


def trim_tail(x, thresh_db=-60, min_dur=0.03):
    a = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=1)
    th = np.max(a) * 10 ** (thresh_db / 20)
    idx = np.nonzero(a > th)[0]
    end = max(n_of(min_dur), (idx[-1] + n_of(0.01)) if len(idx) else len(x))
    return fade(x[:end], 0.0005, 0.008)


def loopify(x: np.ndarray, period_n: int) -> np.ndarray:
    """Fold everything past period_n back onto the start: seamless loop."""
    out = x[:period_n].copy()
    rest = x[period_n:]
    while len(rest):
        k = min(len(rest), period_n)
        out[:k] += rest[:k]
        rest = rest[k:]
    return out


# --- instruments -------------------------------------------------------------

def kick(dur=0.45, f0=150, f1=45, punch=1.0, click=0.3, rng=None):
    f = sweep(f0, f1, dur)
    body = osc("sine", f, dur) * env_exp(dur, dur * 0.35)
    c = hp(noise(0.012, rng), 1500) * env_exp(0.012, 0.003) * click
    return drive(mix((body, 0), (c, 0)), 1 + punch)


def sub808(note, dur=1.2, glide=1.3, dist=2.5):
    f0 = hz(note) if isinstance(note, str) else note
    f = f0 * (1 + (glide - 1) * np.exp(-tvec(dur) / 0.04))
    return drive(osc("sine", f, dur) * adsr(dur, 0.002, 0.1, 0.8, dur * 0.6), dist)


def snare(dur=0.25, tone=190, rng=None, bright=7000):
    n = bp(noise(dur, rng), 3000, 0.6) * env_exp(dur, 0.06)
    n = lp(n, bright)
    t = osc("sine", sweep(tone * 1.3, tone, dur), dur) * env_exp(dur, 0.04)
    return n * 0.9 + t * 0.6


def clap(dur=0.3, rng=None):
    out = np.zeros(n_of(dur))
    for k, t0 in enumerate([0, 0.011, 0.022, 0.034]):
        b = bp(noise(dur - t0, rng), 1400, 1.2) * env_exp(dur - t0, 0.012 if k < 3 else 0.09)
        i = n_of(t0)
        out[i:] += b[: len(out) - i]
    return out


def hat(dur=0.06, rng=None, open_=False):
    d = 0.32 if open_ else dur
    x = hp(noise(d, rng), 7500) * env_exp(d, 0.11 if open_ else 0.018)
    metal = sum(osc("square", f, d) for f in (3150, 4780, 6230, 7310)) * 0.06 * env_exp(d, 0.05)
    return hp(x + metal, 6000)


def crash(dur=2.2, rng=None):
    x = hp(noise(dur, rng), 4000) * env_exp(dur, 0.55)
    m = sum(fm(f, 1.41, 3.0, dur) for f in (520, 810, 1330)) * 0.12 * env_exp(dur, 0.4)
    return lp(hp(x + m, 3000), 9000)


def coin(f=3200, dur=0.5, rng=None, bright=1.0):
    """Metal coin ring: inharmonic partials, fast decays."""
    rng = rng or np.random.default_rng(5)
    parts = [(1.0, 1.0, 0.18), (2.756, 0.55, 0.11), (5.404, 0.35, 0.07), (8.933, 0.2, 0.05)]
    out = np.zeros(n_of(dur))
    for ratio, amp, dec in parts:
        out += osc("sine", f * ratio * (1 + rng.uniform(-0.004, 0.004)), dur, rng.random()) * amp * env_exp(dur, dec * bright, 0.0005)
    tick = hp(noise(0.006, rng), 5000) * env_exp(0.006, 0.0015)
    out[: len(tick)] += tick * 0.8
    return out


def chip_clack(dur=0.09, f=2400, rng=None):
    """Clay poker chip hitting chips: short bandpassed click with a body."""
    x = bp(noise(dur, rng), f, 3.0) * env_exp(dur, 0.012, 0.0003)
    body = osc("sine", f * 0.42, dur) * env_exp(dur, 0.01) * 0.4
    return x + body


def bell(note, dur=1.4, ratio=3.5, index=3.0, decay=0.5):
    f = hz(note) if isinstance(note, str) else note
    idx = index * env_exp(dur, decay * 0.6)
    return fm(f, ratio, idx, dur) * env_exp(dur, decay)


def epiano(note, dur=1.0, decay=0.5, bright=1.6):
    f = hz(note) if isinstance(note, str) else note
    a = fm(f, 1.0, bright * env_exp(dur, 0.15), dur) * env_exp(dur, decay)
    b = fm(f * 2, 7.0, 0.6 * env_exp(dur, 0.03), dur) * env_exp(dur, 0.05) * 0.25
    return a + b


def pluck(note, dur=0.4, cutoff=3500, q=3.0, decay=0.15, kind="saw"):
    f = hz(note) if isinstance(note, str) else note
    x = osc(kind, f, dur) + osc(kind, f * 1.005, dur) * 0.6
    c = 200 + cutoff * env_exp(dur, decay * 0.6)
    return resonant_lp(x, c, q) * env_exp(dur, decay)


def brass(notes, dur=0.6, cutoff=2600, attack=0.03, rng=None):
    out = np.zeros(n_of(dur))
    for nt in notes:
        f = hz(nt) if isinstance(nt, str) else nt
        out += supersaw(f, dur, 5, 0.12, rng)
    c = 300 + cutoff * adsr(dur, attack * 2, 0.15, 0.6, 0.2)
    return resonant_lp(out / len(notes), c, 1.2) * adsr(dur, attack, 0.2, 0.75, min(0.25, dur * 0.4))


def pad(notes, dur=2.0, cutoff=1800, rng=None):
    out = np.zeros(n_of(dur))
    for nt in notes:
        f = hz(nt) if isinstance(nt, str) else nt
        out += supersaw(f, dur, 7, 0.25, rng)
    return lp(out / len(notes), cutoff) * adsr(dur, dur * 0.25, 0.2, 0.8, dur * 0.35)


def chip(note, dur=0.12, pw=0.25):
    f = hz(note) if isinstance(note, str) else note
    return osc("square", f, dur, pw=pw) * adsr(dur, 0.001, 0.02, 0.6, 0.03) * 0.6


def whoosh(dur=0.5, f0=400, f1=4000, q=2.0, rng=None, color="pink"):
    x = noise(dur, rng, color)
    y = bp_sweep(x, sweep(f0, f1, dur), q)
    e = np.sin(np.linspace(0, np.pi, n_of(dur))) ** 1.5
    return y * e


def zap(f0=2400, f1=200, dur=0.25, kind="square"):
    return osc(kind, sweep(f0, f1, dur), dur) * env_exp(dur, dur * 0.5)


def shepard(dur: float, base=110.0, octaves=6, rate=0.25, up=True, kind="sine") -> np.ndarray:
    """Endless rise (or fall): looping-friendly when dur * rate is an integer."""
    t = tvec(dur)
    out = np.zeros_like(t)
    for k in range(octaves):
        pos = (k + (t * rate if up else -t * rate)) % octaves
        f = base * 2 ** pos
        amp = np.sin(np.pi * pos / octaves) ** 2
        ph = np.cumsum(f) / SR
        out += np.sin(2 * np.pi * ph) * amp
    return out / octaves * 2


# --- more instruments (v2: radically different variants) --------------------

def karplus(f: float, dur: float, bright: float = 0.6, decay: float = 0.996, rng=None) -> np.ndarray:
    """Plucked string: noise burst into a lowpassed feedback comb (lfilter IIR)."""
    rng = rng or np.random.default_rng(9)
    N = max(2, int(round(SR / f)))
    n = n_of(dur)
    exc = np.zeros(n)
    burst = rng.uniform(-1, 1, N)
    burst = lp(burst, 1500 + 9000 * bright)
    exc[:N] = burst
    a = np.zeros(N + 2)
    a[0] = 1.0
    a[N] = -decay * 0.5
    a[N + 1] = -decay * 0.5
    y = signal.lfilter([1.0], a, exc)
    return y / (np.max(np.abs(y)) + 1e-9)


def guitar(note, dur=0.8, bright=0.55, rng=None):
    f = hz(note) if isinstance(note, str) else note
    return karplus(f, dur, bright, 0.997, rng) * adsr(dur, 0.001, 0.05, 1.0, min(0.15, dur * 0.3))


def dist_guitar(note, dur=0.8, power=True, rng=None, mute=False):
    f = hz(note) if isinstance(note, str) else note
    s = karplus(f, dur, 0.8, 0.999 if not mute else 0.99, rng)
    if power:
        s = s + karplus(f * 1.4983, dur, 0.8, 0.999 if not mute else 0.99, rng) * 0.8 + karplus(f * 2, dur, 0.7, 0.998, rng) * 0.5
    s = drive(lp(s, 5000) * 3, 6.0)
    s = lp(hp(s, 90), 4200)
    return s * adsr(dur, 0.002, 0.1, 0.85, min(0.12, dur * 0.3)) * (env_exp(dur, 0.09) if mute else 1)


FORMANTS = {"a": (800, 1150, 2900), "o": (450, 800, 2830), "u": (325, 700, 2530), "e": (400, 1600, 2700), "i": (300, 2200, 3000)}


def choir(note, dur=1.0, vowel="a", voices=4, rng=None):
    rng = rng or np.random.default_rng(4)
    f = hz(note) if isinstance(note, str) else note
    t = tvec(dur)
    src = np.zeros(n_of(dur))
    for v in range(voices):
        vib = 1 + 0.006 * np.sin(2 * np.pi * (5.2 + rng.uniform(-0.6, 0.6)) * t + rng.random() * 6)
        src += osc("saw", f * vib * (1 + rng.uniform(-0.004, 0.004)), dur, rng.random())
    src /= voices
    out = sum(bp(src, fr, 6.0) * g for fr, g in zip(FORMANTS[vowel], (1.0, 0.6, 0.25)))
    breath = bp(noise(dur, rng), FORMANTS[vowel][1], 2.0) * 0.05
    return (out * 3 + breath) * adsr(dur, min(0.12, dur * 0.25), 0.1, 0.85, min(0.3, dur * 0.4))


def whistle(note, dur=0.6, rng=None):
    f = hz(note) if isinstance(note, str) else note
    t = tvec(dur)
    vib = 1 + 0.012 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.15, 0, 1)
    tone = osc("sine", f * vib, dur)
    br = bp(noise(dur, rng), f, 8.0) * 0.25
    return (tone + br) * adsr(dur, 0.03, 0.05, 0.9, min(0.08, dur * 0.3))


def organ(note, dur=0.8, rng=None):
    f = hz(note) if isinstance(note, str) else note
    t = tvec(dur)
    out = sum(osc("sine", f * h, dur) * w for h, w in ((0.5, 0.5), (1, 1.0), (2, 0.7), (3, 0.45), (4, 0.3), (6, 0.2), (8, 0.15)))
    leslie = 1 + 0.25 * np.sin(2 * np.pi * 6.5 * t)
    click = hp(noise(0.006, rng), 3000) * 0.3
    out = out * leslie * adsr(dur, 0.005, 0.02, 0.95, 0.05) / 3
    out[: len(click)] += click
    return out


def strings(note, dur=1.2, rng=None):
    f = hz(note) if isinstance(note, str) else note
    t = tvec(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * t)
    s = supersaw(f * vib, dur, 6, 0.1, rng)
    return lp(s, 2800) * adsr(dur, min(0.18, dur * 0.3), 0.1, 0.9, min(0.35, dur * 0.4))


def marimba(note, dur=0.5):
    f = hz(note) if isinstance(note, str) else note
    return (osc("sine", f, dur) * env_exp(dur, 0.25) + osc("sine", f * 3.93, dur) * env_exp(dur, 0.03) * 0.35
            + osc("sine", f * 9.2, dur) * env_exp(dur, 0.008) * 0.15)


def steel_drum(note, dur=0.8):
    f = hz(note) if isinstance(note, str) else note
    return (fm(f, 1.0, 1.4 * env_exp(dur, 0.12), dur) * env_exp(dur, 0.45)
            + osc("sine", f * 2.0, dur) * env_exp(dur, 0.25) * 0.4 + osc("sine", f * 3.01, dur) * env_exp(dur, 0.1) * 0.25)


def kalimba(note, dur=0.7):
    f = hz(note) if isinstance(note, str) else note
    return osc("sine", f, dur) * env_exp(dur, 0.4) + osc("sine", f * 5.4, dur) * env_exp(dur, 0.02) * 0.3


def lead(note, dur=0.5, rng=None):
    f = hz(note) if isinstance(note, str) else note
    t = tvec(dur)
    vib = 1 + 0.008 * np.sin(2 * np.pi * 6 * t) * np.clip((t - 0.1) / 0.2, 0, 1)
    s = osc("saw", f * vib, dur) + osc("square", f * vib * 1.003, dur, pw=0.3) * 0.6
    return resonant_lp(s, 2500 + 2000 * env_exp(dur, 0.1), 1.5) * adsr(dur, 0.005, 0.1, 0.8, 0.06) * 0.6


def timpani(note, dur=1.2, rng=None):
    f = hz(note) if isinstance(note, str) else note
    body = osc("sine", f * (1 + 0.15 * env_exp(dur, 0.05)), dur) * env_exp(dur, 0.45)
    over = osc("sine", f * 1.5, dur) * env_exp(dur, 0.2) * 0.4
    return pad_to(mix((body + over, 0), (lp(noise(0.05, rng), 1200) * env_exp(0.05, 0.015), 0, 0.5)), n_of(dur))


def conga(f=220, dur=0.3, rng=None):
    body = osc("sine", sweep(f * 1.4, f, dur), dur) * env_exp(dur, 0.09)
    slap = bp(noise(0.03, rng), 2500, 1.5) * env_exp(0.03, 0.006)
    return pad_to(mix((body, 0), (slap, 0, 0.5)), n_of(dur))


def shaker(dur=0.08, rng=None):
    return hp(noise(dur, rng), 6000) * adsr(dur, dur * 0.4, dur * 0.2, 0.3, dur * 0.4)


def cowbell(dur=0.35):
    s = osc("square", 545, dur) + osc("square", 815, dur)
    return bp(s, 800, 2.5) * env_exp(dur, 0.08)


def vinyl_scratch(dur=0.35, rng=None, f=900):
    t = tvec(dur)
    mod = np.abs(np.sin(2 * np.pi * (1.5 / dur) * t))
    n = bp_sweep(noise(dur, rng), f * (0.5 + 1.5 * mod), 3.0)
    tone = osc("saw", f * 0.3 * (0.4 + 1.6 * mod), dur) * 0.3
    return lp(n * 2 + tone, 5000) * np.sin(np.linspace(0, np.pi, n_of(dur)))


def register(rng=None):
    """Cash register: drawer slam + bell ding + coin rattle."""
    drawer = lp(noise(0.12, rng), 1800) * env_exp(0.12, 0.04)
    ding = fm(2093, 3.0, 1.5 * env_exp(1.0, 0.2), 1.0) * env_exp(1.0, 0.45)
    coins = mix(*[(coin(2800 + 500 * k, 0.3, rng), 0.12 + 0.03 * k, 0.4) for k in range(4)])
    return mix((drawer, 0, 0.8), (ding, 0.06, 0.7), (coins, 0, 0.6))


def gun_cock(rng=None):
    a = bp(noise(0.04, rng), 3000, 2) * env_exp(0.04, 0.008)
    b = bp(noise(0.06, rng), 1600, 2) * env_exp(0.06, 0.012)
    ring = osc("sine", 3400, 0.15) * env_exp(0.15, 0.03) * 0.2
    return mix((a, 0), (ring, 0), (b, 0.11), (ring * 0.7, 0.11))


def wood_block(f=1100, dur=0.15):
    return osc("sine", f, dur) * env_exp(dur, 0.025) + osc("sine", f * 2.7, dur) * env_exp(dur, 0.008) * 0.4


def dice(rng=None, n=6):
    rng = rng or np.random.default_rng(2)
    parts, t = [], 0.0
    for k in range(n):
        parts.append((wood_block(rng.uniform(1600, 2600), 0.05) * (1 - k / (n + 1)), t, 0.8))
        t += rng.uniform(0.03, 0.09) * (1 + k * 0.25)
    return mix(*parts)


def bubble(f0=300, f1=1400, dur=0.12):
    return osc("sine", sweep(f0, f1, dur), dur) * env_exp(dur, dur * 0.5)


def roulette(dur=2.0, rng=None):
    rng = rng or np.random.default_rng(6)
    roll = bp(noise(dur, rng), 3200, 4.0) * (0.6 + 0.4 * np.sin(2 * np.pi * 14 * tvec(dur))) * 0.6
    clacks = [(wood_block(rng.uniform(2200, 3000), 0.04), k * dur / 16, 0.4) for k in range(16)]
    return mix((roll, 0), *clacks)


def tape_stop(x: np.ndarray, start_frac: float = 0.4) -> np.ndarray:
    """Second part of the sound slows down to a halt (pitch drops)."""
    n = len(x)
    s = int(n * start_frac)
    rate = np.concatenate([np.ones(s), np.linspace(1, 0.05, n - s)])
    pos = np.cumsum(rate)
    pos = pos[pos < n - 1]
    return np.interp(pos, np.arange(n), x)


def reverse_swell(x: np.ndarray) -> np.ndarray:
    """Reversed reverb tail leading into the dry sound."""
    tail = reverb(x, 1.2, 1.0)[::-1]
    tail = tail[-n_of(0.6):] if len(tail) > n_of(0.6) else tail
    return np.concatenate([tail * 0.6 * np.linspace(0, 1, len(tail)) ** 2, x])


def chorus(x: np.ndarray, depth=0.003, rate=0.8) -> np.ndarray:
    n = len(x)
    t = np.arange(n) / SR
    d = (0.012 + depth * np.sin(2 * np.pi * rate * t)) * SR
    idx = np.clip(np.arange(n) - d, 0, n - 1)
    return 0.7 * x + 0.5 * np.interp(idx, np.arange(n), x)
