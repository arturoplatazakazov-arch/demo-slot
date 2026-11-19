"""Foley kit for the themed symbol-win sounds (Gangsta Casino): guns, hits,
cash, glamour, heist, vault. Mono float arrays at dsp.SR unless noted.
Every sound is layered the way a real SFX is: transient + body + tail.
"""
from __future__ import annotations

import numpy as np

import dsp
from dsp import SR, mix, n_of


def _rng(r, seed=0):
    return r if r is not None else np.random.default_rng(seed)


# --- guns ---------------------------------------------------------------------

def gunshot(r=None, size=1.0, bright=1.0, dist=0.0):
    """Close pistol shot: crack (bp noise) + boom (sine drop) + clipped blast."""
    r = _rng(r, 1)
    crack = dsp.bp(dsp.noise(0.09, r), 2200 * bright, 0.8) * dsp.env_exp(0.09, 0.012, 0.0002) * 1.6
    blast = dsp.lp(dsp.noise(0.25, r), 3500 * bright) * dsp.env_exp(0.25, 0.04, 0.0002)
    boom = dsp.osc("sine", dsp.sweep(160 * size, 48, 0.35), 0.35) * dsp.env_exp(0.35, 0.08 * size, 0.0005)
    x = mix((crack, 0), (blast, 0, 0.9), (boom, 0, 1.1 * size))
    x = dsp.drive(x * 2.0, 2.5)
    if dist:
        x = dsp.lp(x, 6000 - 4000 * dist)
    return x


def outdoor_tail(x, r=None, length=1.4, mix_=0.5):
    """Slapback echoes off buildings + a long low-passed decay."""
    r = _rng(r, 2)
    echoes = [(dsp.lp(x, 2500), t, g) for t, g in ((0.12, 0.35), (0.29, 0.22), (0.47, 0.12))]
    wet = mix((np.zeros(n_of(length)), 0), *echoes)
    wet = dsp.reverb(wet, 1.6, 0.6, 3000)
    return mix((x, 0), (wet, 0, mix_))


def silenced(r=None):
    r = _rng(r, 3)
    thup = dsp.bp(dsp.noise(0.08, r), 900, 1.0) * dsp.env_exp(0.08, 0.015, 0.0003)
    puff = dsp.lp(dsp.noise(0.15, r), 1200) * dsp.env_exp(0.15, 0.03)
    mech = dsp.bp(dsp.noise(0.03, r), 4000, 3) * dsp.env_exp(0.03, 0.004)
    return mix((thup, 0, 1.4), (puff, 0, 0.6), (mech, 0.005, 0.5))


def casings(r=None, n=4, t0=0.15):
    """Brass shells bouncing on concrete."""
    r = _rng(r, 4)
    parts = []
    for k in range(n):
        t = t0 + r.uniform(0, 0.25) + k * 0.05
        for b in range(3):  # bounces, each quieter and closer together
            f = r.uniform(3800, 6200)
            ping = dsp.osc("sine", f, 0.12) * dsp.env_exp(0.12, 0.025, 0.0003) + dsp.osc("sine", f * 1.52, 0.12) * dsp.env_exp(0.12, 0.012) * 0.5
            parts.append((ping, t + b * (0.09 / (b + 1)), 0.25 / (b + 1)))
    return mix(*parts)


def burst(r=None, rounds=10, rate=14.0, size=0.7, jitter=0.12):
    """Sub-machine-gun burst: rapid shots with mechanical clatter."""
    r = _rng(r, 5)
    parts = []
    for k in range(rounds):
        t = k / rate * (1 + r.uniform(-jitter, jitter) * 0.3)
        g = 0.75 + 0.25 * r.random()
        parts.append((gunshot(r, size * (0.85 + 0.3 * r.random()), 1.1), t, g))
        parts.append((dsp.bp(dsp.noise(0.02, r), 5000, 3) * dsp.env_exp(0.02, 0.003), t + 0.03, 0.3))
    return mix(*parts)


def ricochet(r=None, f0=None):
    r = _rng(r, 6)
    f0 = f0 or r.uniform(3200, 4800)
    whine = dsp.osc("sine", dsp.sweep(f0, f0 * 0.35, 0.6), 0.6) * dsp.env_exp(0.6, 0.25)
    whine = whine * (1 + 0.3 * np.sin(2 * np.pi * 38 * dsp.tvec(0.6)))
    hit = dsp.bp(dsp.noise(0.04, r), 3000, 2) * dsp.env_exp(0.04, 0.006)
    return mix((hit, 0), (whine, 0.01, 0.4))


def dry_fire(r=None):
    r = _rng(r, 7)
    return dsp.bp(dsp.noise(0.04, r), 3500, 4) * dsp.env_exp(0.04, 0.005) + 0 * dsp.noise(0.04, r)


def revolver_spin(r=None, clicks=10):
    r = _rng(r, 8)
    return mix(*[(dsp.bp(dsp.noise(0.02, r), 4200, 5) * dsp.env_exp(0.02, 0.003), k * 0.035 * (1 + k * 0.08), 0.5) for k in range(clicks)])


def pew(f0=1800, f1=300, dur=0.22):
    return dsp.osc("square", dsp.sweep(f0, f1, dur), dur, pw=0.3) * dsp.env_exp(dur, dur * 0.5) * 0.5


# --- hits ---------------------------------------------------------------------

def punch(r=None, weight=1.0):
    r = _rng(r, 10)
    thud = dsp.osc("sine", dsp.sweep(140 * weight + 40, 45, 0.25), 0.25) * dsp.env_exp(0.25, 0.06)
    slap = dsp.bp(dsp.noise(0.05, r), 900, 1.0) * dsp.env_exp(0.05, 0.01, 0.0002)
    snap = dsp.hp(dsp.noise(0.02, r), 3000) * dsp.env_exp(0.02, 0.003)
    return dsp.drive(mix((thud, 0, 1.2 * weight), (slap, 0, 0.9), (snap, 0, 0.3)), 1.8)


def swing(r=None, dur=0.28, f0=300, f1=1600):
    return dsp.whoosh(dur, f0, f1, 1.3, _rng(r, 11)) * 1.2


def bone_crack(r=None):
    r = _rng(r, 12)
    return mix(*[(dsp.bp(dsp.noise(0.015, r), r.uniform(1500, 3000), 3) * dsp.env_exp(0.015, 0.003), k * 0.012, 0.7) for k in range(4)])


def metal_ring(f=1300, dur=1.0):
    parts = [(1, 1.0, 0.35), (2.41, 0.5, 0.25), (3.87, 0.35, 0.15), (5.9, 0.2, 0.08)]
    return sum(dsp.osc("sine", f * k, dur) * a * dsp.env_exp(dur, d) for k, a, d in parts)


def wood_crack(r=None, f=1.0):
    r = _rng(r, 13)
    trans = dsp.bp(dsp.noise(0.03, r), 2600, 1.2) * dsp.env_exp(0.03, 0.004, 0.0001) * 2
    modes = sum(dsp.osc("sine", m * f, 0.25) * a * dsp.env_exp(0.25, d) for m, a, d in ((420, 1.0, 0.05), (1130, 0.6, 0.03), (2380, 0.35, 0.015)))
    return dsp.drive(mix((trans, 0), (modes, 0, 0.9)), 1.5)


def alu_ping(r=None):
    return mix((wood_crack(r, 1.6), 0, 0.6), (metal_ring(1900, 0.9), 0, 0.5))


def crowd_cheer(r=None, dur=2.0):
    r = _rng(r, 14)
    out = np.zeros(n_of(dur))
    for v in range(14):
        f = r.uniform(180, 420)
        voice = dsp.choir(f, dur, r.choice(["a", "e", "o"]), 1, r) * 0.6
        voice *= dsp.adsr(dur, r.uniform(0.05, 0.3), 0.2, 0.7, 0.6)
        out += voice[: len(out)]
    roar = dsp.bp(dsp.noise(dur, r, "pink"), 1200, 0.7) * dsp.adsr(dur, 0.15, 0.3, 0.6, 0.8)
    return out / 6 + roar * 0.6


def glass_smash(r=None, dur=1.0):
    r = _rng(r, 15)
    hit = dsp.hp(dsp.noise(0.05, r), 2500) * dsp.env_exp(0.05, 0.01)
    shards = mix(*[(dsp.osc("sine", r.uniform(2500, 7500), 0.2) * dsp.env_exp(0.2, r.uniform(0.02, 0.08)), r.uniform(0, dur * 0.7) ** 1.6 / max(dur * 0.7, 1e-3) ** 0.6, r.uniform(0.1, 0.35)) for _ in range(40)])
    return mix((hit, 0, 1.2), (shards, 0.01))


def bonk(f0=500, f1=1100, dur=0.25):
    return dsp.osc("sine", dsp.sweep(f0, f1, dur * 0.3), dur) * dsp.env_exp(dur, 0.08) + dsp.osc("tri", f0 * 2, dur) * dsp.env_exp(dur, 0.02) * 0.3


def scrape(r=None, dur=0.6):
    r = _rng(r, 16)
    x = dsp.bp_sweep(dsp.noise(dur, r), dsp.sweep(800, 1600, dur), 4)
    return x * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 23 * dsp.tvec(dur)))) * dsp.adsr(dur, 0.05, 0.1, 0.8, 0.1) * 1.5


def boxing_bell(r=None):
    return metal_ring(1050, 1.6) * 0.8 + metal_ring(1050 * 1.01, 1.6) * 0.3


def knuckle_crack(r=None):
    r = _rng(r, 17)
    return mix(*[(dsp.bp(dsp.noise(0.012, r), r.uniform(1800, 3500), 4) * dsp.env_exp(0.012, 0.002), k * r.uniform(0.05, 0.09), 0.6) for k in range(4)])


# --- glamour ---------------------------------------------------------------------

def harp_gliss(r=None, root=69, up=True, steps=12, gap=0.035):
    r = _rng(r, 20)
    scale = [0, 2, 4, 7, 9]
    notes = [root + scale[k % 5] + 12 * (k // 5) for k in range(steps)]
    if not up:
        notes = notes[::-1]
    return mix(*[(dsp.guitar(dsp.hz(float(m)), 1.2, 0.35, r) * 0.5, k * gap) for k, m in enumerate(notes)])


def sparkle_dust(r=None, n=14, dur=0.9, lo=3000, hi=8000):
    r = _rng(r, 21)
    return mix(*[(dsp.bell(r.uniform(lo, hi), 0.4, 3.5, 1.0, 0.1) * 0.3, r.uniform(0, dur), 1.0) for _ in range(n)])


def celesta(notes, gap=0.14, r=None):
    return mix(*[(dsp.bell(dsp.hz(float(m)), 0.9, 4.0, 1.2, 0.3) * 0.6 + dsp.osc("sine", dsp.hz(float(m)), 0.9) * dsp.env_exp(0.9, 0.4) * 0.4, k * gap) for k, m in enumerate(notes)])


def sax(m, dur=0.5, r=None):
    """Breathy reed lead: pulse + formant + vibrato + breath."""
    f = dsp.hz(float(m))
    t = dsp.tvec(dur)
    vib = 1 + 0.01 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.08) / 0.15, 0, 1)
    src = dsp.osc("square", f * vib, dur, pw=0.42) * 0.6 + dsp.osc("saw", f * vib, dur) * 0.4
    body = dsp.bp(src, 1100, 1.2) * 1.4 + dsp.bp(src, 2600, 2.5) * 0.5 + dsp.lp(src, 700) * 0.6
    breath = dsp.bp(dsp.noise(dur, _rng(r, 22)), 2000, 1.0) * 0.06
    return (body + breath) * dsp.adsr(dur, 0.03, 0.1, 0.85, min(0.1, dur * 0.3))


def muted_trumpet(m, dur=0.4, r=None, wah=True):
    f = dsp.hz(float(m))
    s = dsp.osc("saw", f, dur) + dsp.osc("saw", f * 1.003, dur) * 0.5
    cut = dsp.sweep(500, 2400, dur) if wah else 1500
    return dsp.bp_sweep(s, cut, 3.0) * dsp.adsr(dur, 0.02, 0.1, 0.8, 0.08) * 1.6


def solo_voice(m, dur=1.2, vowel="a", r=None):
    return dsp.choir(dsp.hz(float(m)), dur, vowel, 1, _rng(r, 23)) * 1.4


def kiss(r=None):
    r = _rng(r, 24)
    smack = dsp.bp(dsp.noise(0.03, r), 1500, 2) * dsp.env_exp(0.03, 0.006)
    mwah = dsp.choir(dsp.hz(64.0), 0.35, "a", 1, r) * dsp.env_exp(0.35, 0.12)
    return mix((smack, 0, 1.0), (mwah, 0.02, 0.5))


def heel_steps(r=None, n=3, gap=0.22):
    r = _rng(r, 25)
    step = lambda: mix((dsp.bp(dsp.noise(0.02, r), 3200, 3) * dsp.env_exp(0.02, 0.003), 0, 1.0), (dsp.wood_block(1400, 0.08), 0, 0.5))
    return mix(*[(step(), k * gap, 0.8 + 0.2 * (k % 2)) for k in range(n)])


def spray(r=None, dur=0.4):
    r = _rng(r, 26)
    return dsp.hp(dsp.noise(dur, r), 5000) * dsp.adsr(dur, 0.01, 0.05, 0.7, 0.15) * 0.8


def cork_pop(r=None):
    r = _rng(r, 27)
    pop = dsp.osc("sine", dsp.sweep(700, 280, 0.06), 0.06) * dsp.env_exp(0.06, 0.02, 0.0002)
    air = dsp.bp(dsp.noise(0.06, r), 1800, 1.5) * dsp.env_exp(0.06, 0.01)
    return mix((pop, 0, 1.2), (air, 0, 0.6))


def fizz(r=None, dur=1.2):
    r = _rng(r, 28)
    x = np.zeros(n_of(dur))
    idx = r.integers(0, len(x), int(dur * 900))
    x[idx] = r.uniform(-1, 1, len(idx)) * np.exp(-idx / (dur * SR * 0.5))
    return dsp.hp(x, 3000) * 1.5


def glass_clink(r=None, f=2900):
    return dsp.bell(f, 1.2, 2.76, 1.4, 0.35) * 0.6 + dsp.bell(f * 1.07, 1.2, 2.76, 1.2, 0.3) * 0.4


def camera_flash(r=None):
    r = _rng(r, 29)
    shutter = mix((dsp.bp(dsp.noise(0.015, r), 3000, 3) * dsp.env_exp(0.015, 0.003), 0), (dsp.bp(dsp.noise(0.015, r), 2400, 3) * dsp.env_exp(0.015, 0.003), 0.05, 0.7))
    whine = dsp.osc("sine", dsp.sweep(3000, 9000, 0.4), 0.4) * dsp.adsr(0.4, 0.02, 0.1, 0.5, 0.1) * 0.08
    return mix((shutter, 0), (whine, 0.08))


# --- boss / money -----------------------------------------------------------------

def lighter(r=None):
    r = _rng(r, 30)
    flick = dsp.bp(dsp.noise(0.03, r), 2500, 2) * dsp.env_exp(0.03, 0.006)
    flame = dsp.lp(dsp.noise(0.6, r), 1500) * dsp.adsr(0.6, 0.02, 0.1, 0.5, 0.3) * 0.4
    return mix((flick, 0, 1.0), (flame, 0.03))


def exhale(r=None, dur=0.9):
    r = _rng(r, 31)
    return dsp.bp_sweep(dsp.noise(dur, r, "pink"), dsp.sweep(1200, 600, dur), 1.2) * dsp.adsr(dur, 0.1, 0.2, 0.6, 0.4) * 1.2


def latch(r=None):
    r = _rng(r, 32)
    c = lambda f: mix((dsp.bp(dsp.noise(0.03, r), f, 3) * dsp.env_exp(0.03, 0.005), 0), (dsp.osc("sine", f * 0.8, 0.08) * dsp.env_exp(0.08, 0.01), 0, 0.3))
    return mix((c(2600), 0), (c(2300), 0.12))


def coin_pile(r=None, n=24, dur=0.9):
    r = _rng(r, 33)
    return mix(*[(dsp.coin(r.uniform(2200, 4200), 0.35, r) * 0.4, (k / n) ** 1.5 * dur, 0.4 + 0.6 * r.random()) for k in range(n)])


def money_thud(r=None):
    r = _rng(r, 34)
    return mix((dsp.osc("sine", dsp.sweep(120, 60, 0.2), 0.2) * dsp.env_exp(0.2, 0.05), 0), (dsp.lp(dsp.noise(0.08, r), 1500) * dsp.env_exp(0.08, 0.02), 0, 0.8))


def orch_hit(root=45, r=None, minor=True):
    r = _rng(r, 35)
    ch = [0, 3, 7, 12] if minor else [0, 4, 7, 12]
    strings = sum(dsp.strings(dsp.hz(float(root + 12 + c)), 0.8, r) for c in ch) * 0.3
    brass = dsp.brass([dsp.hz(float(root + c)) for c in ch[:3]], 0.8, 2000, 0.01, r)
    timp = dsp.timpani(dsp.hz(float(root - 12)), 1.4, r)
    env = dsp.env_exp(0.8, 0.25, 0.003)
    return mix((strings * env, 0), (brass * env, 0, 0.8), (timp, 0, 0.9), (dsp.crash(1.2, r), 0, 0.12))


def slam(r=None, heavy=1.0):
    r = _rng(r, 36)
    return dsp.drive(mix((dsp.osc("sine", dsp.sweep(110, 40, 0.4), 0.4) * dsp.env_exp(0.4, 0.1), 0, heavy),
                         (dsp.lp(dsp.noise(0.15, r), 2200) * dsp.env_exp(0.15, 0.03), 0, 0.9),
                         (dsp.bp(dsp.noise(0.3, r), 400, 1) * dsp.env_exp(0.3, 0.1), 0.02, 0.4)), 1.6)


def engine_rev(r=None, dur=1.4):
    r = _rng(r, 37)
    rpm = np.concatenate([np.linspace(28, 75, n_of(dur * 0.5)), np.linspace(75, 40, n_of(dur * 0.5))])
    rpm = dsp.pad_to(rpm, n_of(dur))
    x = dsp.osc("saw", rpm, dur) + dsp.osc("square", rpm * 2, dur, pw=0.3) * 0.4
    x = dsp.drive(dsp.lp(x, 900), 2.5) * dsp.adsr(dur, 0.05, 0.2, 0.8, 0.3)
    return x + dsp.lp(dsp.noise(dur, r), 600) * 0.2


def tire_screech(r=None, dur=0.9):
    r = _rng(r, 38)
    t = dsp.tvec(dur)
    f = 1800 + 400 * np.sin(2 * np.pi * 3 * t) + r.normal(0, 60, len(t))
    tone = dsp.osc("saw", f, dur) * 0.2 + dsp.bp(dsp.noise(dur, r), 2500, 3) * 0.8
    return dsp.bp(tone, 2200, 1.2) * dsp.adsr(dur, 0.03, 0.1, 0.8, 0.25) * 1.5


# --- hustler -------------------------------------------------------------------------

def bills_flip(r=None, n=14, rate=22.0):
    r = _rng(r, 40)
    flip = lambda: dsp.bp(dsp.noise(0.03, r), r.uniform(2500, 4200), 2) * dsp.adsr(0.03, 0.004, 0.01, 0.5, 0.015)
    return mix(*[(flip(), k / rate * (1 + 0.1 * r.random()), 0.6 + 0.4 * r.random()) for k in range(n)])


def card_shuffle(r=None, dur=0.7):
    r = _rng(r, 41)
    return mix(*[(dsp.bp(dsp.noise(0.012, r), r.uniform(3000, 5000), 3) * dsp.env_exp(0.012, 0.003), k * dur / 60, 0.5) for k in range(60)])


def card_flip(r=None):
    r = _rng(r, 42)
    return mix((dsp.bp(dsp.noise(0.05, r), 2200, 1.5) * dsp.adsr(0.05, 0.005, 0.01, 0.6, 0.03), 0), (dsp.bp(dsp.noise(0.02, r), 3500, 3) * dsp.env_exp(0.02, 0.004), 0.05, 0.6))


def jingle(r=None, dur=0.8):
    r = _rng(r, 43)
    return mix(*[(dsp.coin(r.uniform(3000, 5500), 0.2, r) * 0.35, r.uniform(0, dur), 1.0) for _ in range(18)])


def snap(r=None):
    r = _rng(r, 44)
    return mix((dsp.hp(dsp.noise(0.02, r), 2000) * dsp.env_exp(0.02, 0.004), 0, 1.0), (dsp.bp(dsp.noise(0.04, r), 1200, 2) * dsp.env_exp(0.04, 0.01), 0, 0.5))


def _glide_whistle(f0, f1, dur, r):
    f = dsp.sweep(f0, f1, dur)
    tone = dsp.osc("sine", f, dur)
    breath = dsp.bp_sweep(dsp.noise(dur, r), f, 8.0) * 0.6
    return (tone + breath) * dsp.adsr(dur, 0.02, 0.05, 0.9, min(0.08, dur * 0.3))


def catcall(r=None):
    r = _rng(r, 47)
    return mix((_glide_whistle(1400, 2600, 0.3, r), 0), (_glide_whistle(2400, 1100, 0.45, r), 0.36))


def band_snap(r=None):
    r = _rng(r, 45)
    return mix((dsp.osc("sine", dsp.sweep(400, 120, 0.08), 0.08) * dsp.env_exp(0.08, 0.02), 0), (dsp.hp(dsp.noise(0.01, r), 3000) * dsp.env_exp(0.01, 0.002), 0, 0.8))


def chips_stack(r=None, n=8):
    r = _rng(r, 46)
    return mix(*[(dsp.chip_clack(0.08, r.uniform(2000, 2800), r), k * 0.06, 0.7) for k in range(n)])


def talkbox(m, dur=0.35, vowel_from="u", vowel_to="a", r=None):
    f = dsp.hz(float(m))
    src = dsp.osc("saw", f, dur) + dsp.osc("saw", f * 1.005, dur) * 0.5
    a, b = dsp.FORMANTS[vowel_from], dsp.FORMANTS[vowel_to]
    out = sum(dsp.bp_sweep(src, dsp.sweep(fa, fb, dur, "lin"), 6) * g for fa, fb, g in zip(a, b, (1.0, 0.6, 0.3)))
    return out * 2.5 * dsp.adsr(dur, 0.01, 0.05, 0.85, 0.06)


# --- heist / wild ---------------------------------------------------------------------

def siren(r=None, dur=1.2, kind="wail"):
    t = dsp.tvec(dur)
    if kind == "wail":
        f = 900 + 500 * np.sin(2 * np.pi * (1 / dur) * t - np.pi / 2)
    else:  # two-tone
        f = np.where((t * 3).astype(int) % 2 == 0, 960, 770)
    x = dsp.osc("saw", f, dur) * 0.4 + dsp.osc("square", f, dur, pw=0.5) * 0.2
    return dsp.bp(x, 1400, 0.8) * dsp.adsr(dur, 0.05, 0.1, 0.9, 0.2) * 1.4


def alarm_bell(r=None, dur=1.0):
    t = dsp.tvec(dur)
    ring = metal_ring(2100, dur) * (0.5 + 0.5 * (np.sin(2 * np.pi * 22 * t) > 0))
    return ring * dsp.adsr(dur, 0.005, 0.05, 0.9, 0.15) * 0.7


def explosion(r=None, dur=2.0):
    r = _rng(r, 50)
    boom = dsp.osc("sine", dsp.sweep(80, 28, dur), dur) * dsp.env_exp(dur, 0.5)
    rumble = dsp.lp(dsp.noise(dur, r, "brown"), 400) * dsp.env_exp(dur, 0.7) * 2
    crack = dsp.lp(dsp.noise(0.3, r), 5000) * dsp.env_exp(0.3, 0.05)
    debris = mix(*[(dsp.wood_block(r.uniform(600, 2500), 0.06) * 0.3, r.uniform(0.2, dur * 0.8), 1.0) for _ in range(20)])
    return dsp.drive(mix((boom, 0, 1.5), (rumble, 0, 1.0), (crack, 0, 1.0), (debris, 0, 0.6)), 2.0)


def rotor(r=None, dur=1.6):
    r = _rng(r, 51)
    t = dsp.tvec(dur)
    chop = (np.sin(2 * np.pi * 11 * t) > 0.6).astype(float)
    chop = dsp.lp(chop, 200)
    return dsp.lp(dsp.noise(dur, r), 700) * chop * 2.0 * dsp.adsr(dur, 0.3, 0.1, 0.9, 0.3)


def safe_dial(r=None, n=8, gap=0.07):
    r = _rng(r, 52)
    return mix(*[(dsp.wood_block(r.uniform(2600, 3200), 0.04) * 0.6, k * gap, 0.6 + 0.4 * (k == n - 1)) for k in range(n)])


def vault_clunk(r=None):
    r = _rng(r, 53)
    return mix((slam(r, 1.4), 0), (metal_ring(310, 1.5) * 0.5, 0), (metal_ring(470, 1.2) * 0.3, 0.01))


def creak(r=None, dur=1.0):
    r = _rng(r, 54)
    t = dsp.tvec(dur)
    f = 160 + 60 * np.sin(2 * np.pi * 0.7 * t)
    pulses = dsp.osc("saw", f, dur) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t + r.random()))
    return dsp.bp(pulses, 900, 2.5) * dsp.adsr(dur, 0.1, 0.1, 0.8, 0.3) * 1.5


def hydraulic(r=None, dur=0.7):
    r = _rng(r, 55)
    return dsp.hp(dsp.noise(dur, r), 2500) * dsp.adsr(dur, 0.01, 0.1, 0.6, 0.4) * 0.9


def keypad(notes=(1209, 1336, 1477, 1209), gap=0.12):
    return mix(*[(dsp.osc("sine", f, 0.09) * 0.5 + dsp.osc("sine", 770, 0.09) * 0.5, k * gap, 0.5) for k, f in enumerate(notes)])


def gong(r=None, f=110, dur=3.0):
    r = _rng(r, 56)
    parts = [(1.0, 1.0, 1.2), (1.48, 0.6, 0.9), (2.15, 0.5, 0.7), (2.9, 0.4, 0.5), (4.1, 0.25, 0.3)]
    body = sum(dsp.osc("sine", f * k * (1 + 0.003 * np.sin(2 * np.pi * 0.8 * dsp.tvec(dur))), dur) * a * dsp.env_exp(dur, d) for k, a, d in parts)
    strike = dsp.lp(dsp.noise(0.05, r), 1500) * dsp.env_exp(0.05, 0.01)
    return mix((strike, 0, 0.8), (body, 0, 0.8))


def laser_beeps(r=None):
    return mix(*[(dsp.osc("square", 2400 - k * 250, 0.07, pw=0.5) * dsp.env_exp(0.07, 0.03) * 0.3, k * 0.08) for k in range(6)])


def surf_guitar(notes, gap=0.11, r=None):
    """Spy / heist twang: plucked string + tremolo + spring reverb."""
    r = _rng(r, 57)
    x = mix(*[(dsp.guitar(dsp.hz(float(m)), 0.5, 0.75, r), k * gap) for k, m in enumerate(notes)])
    x = x * (0.75 + 0.25 * np.sin(2 * np.pi * 7 * dsp.tvec(len(x) / SR)))
    return dsp.reverb(x, 1.6, 0.35, 4500)


def bag_drop(r=None):
    return mix((money_thud(r), 0, 1.2), (coin_pile(r, 12, 0.5), 0.03, 0.7))


# --- finishing -----------------------------------------------------------------------

def finish(x, r=None, space=0.18, width=0.5, size=1.3):
    """Premium polish: gentle glue compression, stereo width, shared space."""
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        x = x.mean(axis=1)
    peak = np.max(np.abs(x)) + 1e-9
    x = np.tanh(x / peak * 1.4) / np.tanh(1.4)  # glue
    wet = dsp.reverb(x, size, 1.0, 6500, stereo=True)
    dry = np.stack([x, x], 1)
    # Haas width: right channel a few ms late on the wet only
    d = n_of(0.012 * width)
    if d:
        wet[:, 1] = np.concatenate([np.zeros(d), wet[:-d, 1]])
    dry = np.pad(dry, ((0, len(wet) - len(dry)), (0, 0)))
    return dry * (1 - space) + wet * space


def gun_cock_long(r=None):
    """Pistol slide racked: pull back (metal scrape) + release snap + ring."""
    r = _rng(r, 9)
    pull = dsp.bp_sweep(dsp.noise(0.12, r), dsp.sweep(2500, 4500, 0.12), 5) * dsp.adsr(0.12, 0.01, 0.03, 0.7, 0.04)
    click1 = dsp.bp(dsp.noise(0.03, r), 3200, 3) * dsp.env_exp(0.03, 0.005)
    snap_ = dsp.bp(dsp.noise(0.05, r), 1800, 2) * dsp.env_exp(0.05, 0.01) * 1.4
    ring = metal_ring(3100, 0.25) * 0.15
    return mix((click1, 0), (pull, 0.02, 0.6), (snap_, 0.2), (ring, 0.2))
