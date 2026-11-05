"""Neon Joker Spins C (Rock Chrome) — the whole slot sound pack as an
audition: five takes for every position, synthesized in code (no samples).

Positions (key -> what the game plays):
  bg_base      base-game music loop      — the round-2 rock loops (music_1..5,
                                            scripts/neon_joker_spins_c_music.py)
  bg_bonus     free spins / bonus loop    — five hotter rock loops
  spin         spin button press
  reel_loop    reels spinning (seamless loop)
  reel_stop    reel landing (demo = three reels stopping)
  coin_land    coin landing on a reel
  win_small / win_big / win_mega / win_epic
  bonus_enter / bonus_exit
  ui_click / ui_popup_open / ui_popup_close / ui_autospin / ui_bet_plus /
  ui_bet_minus / ui_menu / ui_turbo

Every take is rock: double-tracked power chords through the amp model, a
rock kit with a room, picked bass, guitar natural harmonics, amp switches and
pick scrapes, coins for the money moments. The five takes of the wins share
five "bands": 1 hard rock (A), 2 punk (E), 3 metal (E), 4 stadium anthem (D),
5 rock'n'roll boogie (A).

    <venv with numpy scipy lameenc>/bin/python scripts/neon_joker_spins_c_sfx.py [position ...]
    <venv>/bin/python scripts/neon_joker_spins_c_sfx.py install   # picks -> sound/neon-joker-spins-c/

Output: front/sound/neon-joker-spins-c/_audition/pack/<position>_<1..5>.mp3
        + pack.json (titles / descriptions); page: _audition/index.html.
"""

import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from great_uniqorn_audio import (  # noqa: E402
    SR, clap, coin, coin_shower, crash, downer, env, expdec, finish, hat, impact, kick, midi,
    n_of, noise, pan, put, reverb, ride, riser, sfx, sine, snare_roll, soft_master, sos_bp,
    sos_hp, sos_lp, tom, whoosh, write_mp3, hz,
)
from neon_joker_spins_c_music import (  # noqa: E402
    RNG, RockSong, amp, backbeat, bass_di, chord_di, fill, lead_di, power5, rock_kick,
    rock_snare, string,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, 'front/sound/neon-joker-spins-c/_audition')
OUT = os.path.join(AUD, 'pack')


# =============================================================================
# rock building blocks for one-shots

def gtr(notes, sec, gain=9.0, vel=0.8, mute=False, width=0.8):
    """Double-tracked chord through the amp, stereo."""
    notes = [midi(m) if isinstance(m, str) else m for m in notes]
    L = amp(chord_di(notes, sec, mute=mute, cents=-4), gain)
    R = amp(chord_di(notes, sec, mute=mute, cents=4), gain)
    lag = n_of(0.008)
    R = np.concatenate([np.zeros(lag), R])[:len(L)]
    a = (1 - width) * np.pi / 4
    return np.stack([L * np.cos(a) + R * np.sin(a), R * np.cos(a) + L * np.sin(a)]) * vel


def lead(note, sec, vel=0.6, bend=0.0, gain=14.0):
    return amp(lead_di(note, sec, 0.8, bend_from=bend), gain, tight=200, presence=0.6, fizz=6000) * vel


def harmonic(note, sec=1.2, vel=0.5):
    """Guitar natural harmonic: glassy partials through a clean-ish amp."""
    m = midi(note) if isinstance(note, str) else note
    t = np.arange(n_of(sec)) / SR
    f = hz(m)
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)
    x = x * expdec(len(t), sec * 0.35)
    x[:n_of(0.004)] += sos_bp(noise(0.004), 2000, 8000) * 0.6
    return np.tanh(1.5 * x) * vel * 0.7


def pick_scrape(sec=0.35, up=False, vel=0.6):
    """Pick slide along wound strings: a sweeping comb of noise, amped."""
    n = n_of(sec)
    t = np.arange(n) / SR
    f0, f1 = (300, 2500) if up else (2500, 300)
    f = f0 * (f1 / f0) ** (t / sec)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sign(np.sin(ph)) * 0.4 + noise(sec) * 0.6
    x = sos_bp(x, 400, 5000)
    return amp(x * np.sin(np.pi * t / sec) ** 0.7, 6.0, presence=0.8) * vel


def amp_switch(vel=0.6, hum=True):
    """Footswitch / amp toggle: a hard click plus a burst of amp hum."""
    sec = 0.25
    x = np.zeros(n_of(sec))
    x[:n_of(0.004)] = sos_bp(noise(0.004), 1500, 9000) * 1.2
    x[:n_of(0.03)] += sine(np.geomspace(1800, 400, n_of(0.03)), 0.03) * expdec(n_of(0.03), 0.006) * 0.6
    if hum:
        t = np.arange(n_of(sec)) / SR
        h = (np.sin(2 * np.pi * 60 * t) + 0.5 * np.sin(2 * np.pi * 120 * t) + 0.3 * np.sin(2 * np.pi * 180 * t))
        x += h * expdec(n_of(sec), 0.06) * 0.15
    return x * vel


def mute_tick(vel=0.6, note='E3'):
    """Fret-hand mute 'tchk': a dead strum, very short."""
    x = chord_di([midi(note), midi(note) + 7, midi(note) + 12], 0.06, mute=True)
    return amp(x, 8.0) * expdec(n_of(0.06), 0.015) * vel


def bass_pluck(note, sec=0.35, vel=0.8):
    m = midi(note) if isinstance(note, str) else note
    return bass_di(m, sec, vel)


def cowbell_r(vel=0.5):
    t = np.arange(n_of(0.3)) / SR
    x = np.sign(np.sin(2 * np.pi * 562 * t)) + np.sign(np.sin(2 * np.pi * 845 * t))
    return sos_bp(x, 500, 3200) * expdec(len(t), 0.08) * vel * 0.35


def ride_bell(vel=0.5):
    t = np.arange(n_of(1.0)) / SR
    x = sum(np.sin(2 * np.pi * f * t) for f in (1220, 2950, 4630)) * expdec(len(t), 0.4) / 3
    x[:n_of(0.003)] += noise(0.003) * 0.5
    return x * vel


def choke_crash(vel=0.7, sec=0.25):
    c = crash(vel, sec + 0.1)[:n_of(sec)]
    c[-n_of(0.04):] *= np.linspace(1, 0, n_of(0.04))
    return c


# five "bands" for the money moments: chord roots, the hook lick, kit flavour
BANDS = {
    1: dict(name='хард-рок', chords=['A2', 'D3', 'E2', 'A2'], lick=['A4', 'C5', 'D5', 'E5', 'A5'], gain=8.0,
            sec=lambda m: power5(midi(m) - (12 if midi(m) > midi('B2') else 0))),
    2: dict(name='панк', chords=['E2', 'B1', 'C#2', 'E2'], lick=['B4', 'E5', 'G#5', 'B5', 'E6'], gain=10.0,
            sec=lambda m: power5(midi(m) + (12 if m[-1] == '1' else 0), octave=False)),
    3: dict(name='метал', chords=['E2', 'C3', 'D3', 'E2'], lick=['E5', 'G5', 'A5', 'B5', 'E6'], gain=12.0,
            sec=lambda m: power5(midi(m) - (12 if midi(m) > midi('B2') else 0))),
    4: dict(name='стадионный гимн', chords=['D3', 'A2', 'G2', 'D3'], lick=['D5', 'F#5', 'A5', 'B5', 'D6'], gain=7.0,
            sec=lambda m: power5(midi(m) - (12 if midi(m) > midi('E3') else 0))),
    5: dict(name='рок-н-ролл', chords=['A2', 'D3', 'E2', 'A2'], lick=['C#5', 'E5', 'F#5', 'A5', 'C#6'], gain=4.5,
            sec=lambda m: [midi(m) - (12 if midi(m) > midi('B2') else 0), midi(m) - (12 if midi(m) > midi('B2') else 0) + 9]),
}


def band_chord(v, i, sec, vel=0.85, mute=False):
    b = BANDS[v]
    return gtr(b['sec'](b['chords'][i % 4]), sec, b['gain'], vel, mute)


# =============================================================================
# BG bonus — five hotter loops

def bonus_1():
    """Overdrive — 140 bpm hard rock, the lead never stops."""
    s = RockSong(140, 16)
    A, D, E, G = midi('A2'), midi('D3') - 12, midi('E2'), midi('G2')
    roots = [A, A, G, D, A, A, E, E] * 2
    for bar in range(16):
        r = roots[bar]
        backbeat(s, bar, kicks=(0, 0.5, 2, 2.5), hats=8, ride_=bar >= 8)
        for i in range(8):
            s.gtr(bar, i / 2, power5(r), 0.22, 0.85, mute=i % 4 == 1)
            s.bass(bar, i / 2, r - 12, 0.2)
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.75, 1.6), 0.2)
        if bar % 4 == 3:
            fill(s, bar, 2.0, ('A2', 'F2', 'D2', 'A1'))
        lick = [(0, 'E5', 0.4), (0.5, 'G5', 0.4), (1, 'A5', 0.9, 2), (2, 'G5', 0.4), (2.5, 'E5', 0.4), (3, 'D5', 0.9, 1)]
        for item in lick:
            b, nt, d = item[:3]
            s.lead(bar, b, nt, d, 0.6, item[3] if len(item) > 3 else 0)
    return s.mixdown(gtr_gain=9.0, levels={'lead': 0.38})


def bonus_2():
    """Punk Frenzy — 196 bpm, double-time punk with octave lead."""
    s = RockSong(196, 16)
    prog = ['E2', 'C3', 'G2', 'D3'] * 4
    for bar in range(16):
        r = midi(prog[bar]) - (12 if midi(prog[bar]) > midi('B2') else 0)
        for i in range(8):
            s.add('drums', bar, i / 2, rock_kick(0.95) if i % 2 == 0 else rock_snare(0.9), 0.03)
            s.add('drums', bar, i / 2, hat(0.42, open_=i == 7), 0.3)
            s.gtr(bar, i / 2, power5(r, octave=False), 0.19, 0.88)
            s.bass(bar, i / 2, r - 12, 0.18, 0.9)
        if bar % 2 == 0:
            s.add('drums', bar, 0, crash(0.7, 1.2), -0.2)
        if bar >= 8:
            for b, nt in ((0, 'B4'), (1, 'E5'), (2, 'D5'), (3, 'B4')):
                s.lead(bar, b, nt, 0.9, 0.5)
                s.lead(bar, b, midi(nt) + 12, 0.9, 0.3)
    return s.mixdown(gtr_gain=11.0, levels={'gtr': 0.7})


def bonus_3():
    """Thrash Jackpot — 170 bpm thrash: 16th palm-mutes, double kick, chord stabs."""
    s = RockSong(170, 16)
    E = midi('E2')
    for bar in range(16):
        stab_bar = bar % 4 == 3
        for i in range(16):
            if stab_bar and i >= 8:
                break
            s.gtr(bar, i / 4, power5(E, octave=False), 0.1, 0.85, mute=True)
            if i % 2 == 0:
                s.bass(bar, i / 4, E - 12, 0.12, 0.85, mute=True)
            s.add('drums', bar, i / 4, rock_kick(0.75))
        if stab_bar:
            for b, m in ((2, 'F2'), (2.5, 'F#2'), (3, 'G2'), (3.5, 'A#2')):
                s.gtr(bar, b, power5(midi(m)), 0.4, 0.9)
                s.bass(bar, b, midi(m) - 12, 0.35)
                s.add('drums', bar, b, crash(0.45, 0.5), 0.2)
        for b in (1, 3):
            s.add('drums', bar, b, rock_snare(1.0), 0.05)
        for i in range(8):
            s.add('drums', bar, i / 2, ride(0.3), 0.35)
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.8, 1.4), -0.25)
    return s.mixdown(gtr_gain=13.0)


def bonus_4():
    """Stadium Anthem — 124 bpm: big open chords, tom-heavy groove, a melody
    you can sing, a crash on every bar."""
    s = RockSong(124, 16)
    prog = [('D3', 'D5'), ('A2', 'C#5'), ('B2', 'D5'), ('G2', 'B4')] * 4
    for bar in range(16):
        root, mel = prog[bar]
        m = midi(root) - 12
        for b in (0, 1.5, 2, 3):
            s.gtr(bar, b, [m, m + 7, m + 12, m + 16 if bar % 4 in (0,) else m + 15], 0.55, 0.9)
        for i in range(8):
            s.bass(bar, i / 2, m - 12 + (12 if i % 4 == 3 else 0), 0.22)
        backbeat(s, bar, kicks=(0, 1.5, 2), hats=8, ride_=True)
        s.add('drums', bar, 0, crash(0.7, 1.8), 0.25 if bar % 2 else -0.25)
        for k, nt in enumerate(('A2', 'F2')):
            s.add('drums', bar, 3 + k * 0.5, tom(nt, 0.7), -0.3 + 0.6 * k)
        if bar >= 4:
            s.lead(bar, 0, mel, 1.8, 0.55, bend=1 if bar % 4 == 0 else 0)
            s.lead(bar, 2, midi(mel) + (2 if bar % 2 else -3), 1.8, 0.5)
    return s.mixdown(gtr_gain=7.0, levels={'lead': 0.4})


def bonus_5():
    """Boogie Fever — 184 bpm shuffle rock'n'roll with a lead that keeps going."""
    s = RockSong(184, 16, swing=0.33)
    prog = ['A2', 'A2', 'D3', 'A2', 'E2', 'D3', 'A2', 'E2'] * 2
    for bar in range(16):
        r = midi(prog[bar]) - (12 if midi(prog[bar]) > midi('B2') else 0)
        for i in range(8):
            top = r + (7 if (i // 2) % 2 == 0 else 9)
            s.gtr(bar, i / 2, [r, top], 0.18, 0.78)
            s.bass(bar, i / 2, r - 12 + [0, 4, 7, 9, 10, 9, 7, 4][i], 0.18)
        backbeat(s, bar, kicks=(0, 2), hats=8, ride_=True)
        s.add('drums', bar, 0, clap(0.4), 0.0)
        for b, nt in ((0, 'C#5'), (0.5, 'E5'), (1, 'A5'), (2, 'G5'), (2.5, 'E5'), (3, 'C#5')):
            s.lead(bar, b, nt, 0.45, 0.45, bend=1 if nt == 'A5' else 0)
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.6, 1.4), -0.2)
    return s.mixdown(gtr_gain=5.0, levels={'lead': 0.36})


# =============================================================================
# spin / reels / coins

def spin(v):
    b = sfx(1.0)
    if v == 1:    # chord stab + kick: the band hits the button
        put(b, 0, gtr([midi('E2'), midi('B2'), midi('E3')], 0.35, 9.0, 0.8))
        put(b, 0, rock_kick(0.9))
    elif v == 2:  # pick scrape down
        put(b, 0, pick_scrape(0.4, up=False, vel=0.75))
    elif v == 3:  # snare flam + choked crash
        put(b, 0, rock_snare(0.6), -0.1)
        put(b, 0.025, rock_snare(1.0), 0.1)
        put(b, 0.025, choke_crash(0.6, 0.22), 0.3)
    elif v == 4:  # amp switch + palm-mute chug
        put(b, 0, amp_switch(0.7, hum=False))
        put(b, 0.04, gtr(['E2', 'B2'], 0.18, 10.0, 0.75, mute=True))
    else:         # bass dive + whoosh
        put(b, 0, bass_pluck('E2', 0.35, 0.8))
        put(b, 0.02, downer(0.35, 3500, 300, 0.35))
    return finish(b, 0.08, 0.6)


def reel_loop(v):
    """Seamless loops while the reels run."""
    if v == 1:    # palm-mute chug 16ths, 160 bpm, 1 bar
        s = RockSong(160, 2)
        for bar in range(2):
            for i in range(16):
                s.gtr(bar, i / 4, power5(midi('E2'), octave=False), 0.1, 0.7 if i % 4 else 0.85, mute=True)
        return s.mixdown(gtr_gain=10.0, levels={'gtr': 0.55})
    if v == 2:    # snare drag + ride ticks
        s = RockSong(150, 2)
        for bar in range(2):
            for i in range(16):
                s.add('drums', bar, i / 4, rock_snare(0.25 + 0.15 * (i % 4 == 0)), 0.0)
            for i in range(8):
                s.add('drums', bar, i / 2, ride(0.25), 0.3)
        return s.mixdown()
    if v == 3:    # tremolo-picked note (surf/metal) on E
        s = RockSong(160, 2)
        for bar in range(2):
            for i in range(32):
                s.gtr(bar, i / 8, [midi('E3')], 0.07, 0.6 + 0.2 * (i % 8 == 0))
        return s.mixdown(gtr_gain=10.0, levels={'gtr': 0.5})
    if v == 4:    # hats 16ths + kick pulse + bass eighths
        s = RockSong(140, 2)
        for bar in range(2):
            for i in range(16):
                s.add('drums', bar, i / 4, hat(0.3 if i % 2 == 0 else 0.18), 0.3)
            for b in range(4):
                s.add('drums', bar, b, rock_kick(0.7))
            for i in range(8):
                s.bass(bar, i / 2, midi('E1'), 0.18, 0.7)
        return s.mixdown(levels={'bass': 0.5})
    # 5: amp hum + gated low drone, rhythmic
    s = RockSong(150, 2)
    for bar in range(2):
        for i in range(8):
            s.gtr(bar, i / 2, [midi('E2'), midi('E2') + 7], 0.16, 0.55, mute=False)
        for b in range(4):
            s.add('drums', bar, b + 0.5, hat(0.25, open_=True), 0.3)
    return s.mixdown(gtr_gain=14.0, levels={'gtr': 0.45})


def reel_stop_one(v, k):
    """k = 0..2: reels 1..3."""
    b = sfx(0.8)
    p = -0.5 + 0.5 * k
    if v == 1:    # muted power-chord chunk, rising
        put(b, 0, gtr(power5(midi('E2') + (0, 3, 5)[k], octave=False), 0.2, 10.0, 0.75, mute=True), p * 0.5)
        put(b, 0, rock_kick(0.5), p)
    elif v == 2:  # floor tom -> rack tom -> rack tom
        put(b, 0, tom(('D2', 'G2', 'C3')[k], 0.95), p)
    elif v == 3:  # kick + chain clank
        put(b, 0, rock_kick(0.75), p)
        put(b, 0.005, sos_bp(noise(0.06), 2500, 9000) * expdec(n_of(0.06), 0.012) * 0.6, p)
        put(b, 0.01, ride_bell(0.15 + 0.08 * k), p)
    elif v == 4:  # rimshot + bass pluck
        put(b, 0, rock_snare(0.6), p)
        put(b, 0, bass_pluck(('E2', 'G2', 'A2')[k], 0.3, 0.6), p)
    else:         # bass thump + harmonic ping
        put(b, 0, bass_pluck('E1', 0.25, 0.8), p)
        put(b, 0.01, harmonic(('E5', 'G5', 'B5')[k], 0.6, 0.35), p)
    return finish(b, 0.1, 0.7)


def reel_stop_demo(v):
    b = sfx(1.6)
    for k in range(3):
        put(b, 0.28 * k, reel_stop_one(v, k))
    return finish(b, 0.0)


def coin_land(v):
    b = sfx(1.2)
    if v == 1:    # coin + guitar harmonic
        put(b, 0, coin(0.6, 1.0))
        put(b, 0.01, harmonic('B5', 0.8, 0.35), 0.2)
    elif v == 2:  # coin + cowbell
        put(b, 0, coin(0.6, 0.9))
        put(b, 0, cowbell_r(0.5), 0.3)
    elif v == 3:  # heavy gold thunk + ring
        put(b, 0, rock_kick(0.6))
        put(b, 0.005, coin(0.7, 0.75))
        put(b, 0.02, ride_bell(0.25), 0.2)
    elif v == 4:  # ride bell + coin pair
        put(b, 0, ride_bell(0.45), -0.2)
        put(b, 0.03, coin(0.5, 1.15), 0.2)
    else:         # small shower + pick tick
        put(b, 0, mute_tick(0.5))
        put(b, 0.01, coin_shower(0.18, 40, 0.45, 1.05))
    return finish(b, 0.12, 0.8)


# =============================================================================
# wins: one builder per tier, five bands

def win_small(v):
    b = sfx(1.4)
    put(b, 0, band_chord(v, 0, 0.45, 0.75))
    put(b, 0, rock_kick(0.6))
    put(b, 0.05, coin(0.45, 1.0), 0.3)
    put(b, 0.14, coin(0.4, 1.12), -0.3)
    if v in (3, 4):
        put(b, 0.0, choke_crash(0.35, 0.3), 0.3)
    return finish(b, 0.15, 0.9)


def win_big(v):
    b = sfx(3.6)
    hits = [(0, 0, 0.25), (0.3, 1, 0.25), (0.6, 2, 1.6)]
    for at, i, d in hits:
        put(b, at, band_chord(v, i, d, 0.85))
        put(b, at, rock_kick(0.9))
        put(b, at, rock_snare(0.7), 0.05)
    put(b, 0.6, crash(0.75, 2.2), 0.25)
    put(b, 0.6, coin_shower(1.6, 18, 0.4, 1.0))
    lk = BANDS[v]['lick']
    put(b, 0.75, lead(lk[2], 0.9, 0.45, bend=2), 0.1)
    return finish(b, 0.18, 1.2)


def win_mega(v):
    b = sfx(5.2)
    for k in range(4):
        put(b, k * 0.11, tom(('C3', 'A2', 'F2', 'D2')[k], 0.8), -0.4 + 0.27 * k)
    for at, i, d in ((0.45, 0, 0.3), (0.75, 1, 0.3), (1.05, 2, 0.3), (1.35, 3, 2.6)):
        put(b, at, band_chord(v, i, d, 0.9))
        put(b, at, rock_kick(1.0))
        put(b, at, rock_snare(0.85), 0.05)
    put(b, 1.35, crash(0.85, 2.6), -0.25)
    put(b, 1.35, crash(0.6, 2.2), 0.3)
    lk = BANDS[v]['lick']
    for k, nt in enumerate(lk[:4]):
        put(b, 1.45 + 0.16 * k, lead(nt, 0.2, 0.42), 0.1)
    put(b, 2.1, lead(lk[4], 1.6, 0.5, bend=2), 0.1)
    put(b, 0.4, coin_shower(3.2, 22, 0.4, 1.0, rise=0.25))
    return finish(b, 0.2, 1.4)


def win_epic(v):
    b = sfx(8.0)
    put(b, 0, riser(1.1, 300, 6000, 0.45))
    put(b, 0.2, snare_roll(0.9, 0.55), 0.0)
    put(b, 1.1, impact(0.8, 42))
    for at, i, d in ((1.1, 0, 0.45), (1.6, 1, 0.45), (2.1, 2, 0.45), (2.6, 3, 3.6)):
        put(b, at, band_chord(v, i, d, 0.95))
        put(b, at, rock_kick(1.0))
        put(b, at, rock_snare(0.9), 0.05)
        put(b, at, crash(0.55, 1.4), (-0.3, 0.3)[i % 2])
    put(b, 2.6, crash(0.9, 3.4), 0.0)
    lk = BANDS[v]['lick']
    for k, nt in enumerate(lk + lk[::-1][1:]):
        put(b, 2.7 + 0.13 * k, lead(nt, 0.18, 0.4), 0.1)
    put(b, 3.9, lead(lk[4], 2.4, 0.55, bend=2), 0.1)
    put(b, 1.1, coin_shower(5.5, 26, 0.42, 1.0, rise=0.3))
    put(b, 6.0, gtr(BANDS[v]['sec'](BANDS[v]['chords'][0]), 1.6, BANDS[v]['gain'], 0.9))
    put(b, 6.0, rock_kick(1.0))
    put(b, 6.0, crash(0.8, 1.8), 0.2)
    return finish(b, 0.2, 1.6)


# =============================================================================
# bonus enter / exit

def bonus_enter(v):
    b = sfx(4.5)
    put(b, 0, riser(1.2, 250, 7000, 0.45))
    put(b, 0.3, snare_roll(0.9, 0.5), 0.0)
    put(b, 1.2, impact(0.9, 40))
    put(b, 1.2, band_chord(v, 0, 2.6, 0.95))
    put(b, 1.2, crash(0.9, 2.8), -0.2)
    put(b, 1.2, crash(0.6, 2.4), 0.3)
    put(b, 1.25, lead(BANDS[v]['lick'][4], 2.2, 0.5, bend=3), 0.1)
    if v == 3:
        for i in range(8):
            put(b, 1.2 + i * 0.09, rock_kick(0.6))
    if v == 5:
        put(b, 1.2, coin_shower(1.5, 24, 0.4, 1.0))
    return finish(b, 0.2, 1.5)


def bonus_exit(v):
    """A rock ending: three hits, a held chord, the last crash choked."""
    b = sfx(3.6)
    for at, i in ((0, 1), (0.28, 2), (0.56, 3)):
        put(b, at, band_chord(v, i, 0.22 if at < 0.5 else 1.9, 0.9))
        put(b, at, rock_kick(0.95))
        put(b, at, rock_snare(0.85), 0.05)
    put(b, 0.56, crash(0.85, 2.0), 0.2)
    put(b, 2.45, choke_crash(0.7, 0.18), -0.2)
    put(b, 2.45, rock_kick(1.0))
    put(b, 2.45, band_chord(v, 0, 0.3, 0.95))
    return finish(b, 0.16, 1.2)


# =============================================================================
# UI: five families — 1 pick/string, 2 drum kit, 3 amp & metal,
# 4 guitar harmonics, 5 bass

def ui_click(v):
    b = sfx(0.35)
    if v == 1:
        put(b, 0, mute_tick(0.6))
    elif v == 2:
        put(b, 0, hat(0.5), 0.0)
        put(b, 0, sos_bp(noise(0.01), 2500, 8000) * expdec(n_of(0.01), 0.002) * 0.4)
    elif v == 3:
        put(b, 0, amp_switch(0.5, hum=False))
    elif v == 4:
        put(b, 0, harmonic('E6', 0.25, 0.35))
    else:
        put(b, 0, bass_pluck('A2', 0.12, 0.55) * expdec(n_of(0.12), 0.03))
    return finish(b, 0.05, 0.4)


def ui_popup_open(v):
    b = sfx(0.9)
    if v == 1:
        put(b, 0, pick_scrape(0.25, up=True, vel=0.5))
    elif v == 2:
        put(b, 0, tom('A2', 0.5), -0.3)
        put(b, 0.07, tom('D3', 0.5), 0.3)
    elif v == 3:
        put(b, 0, amp_switch(0.5))
        put(b, 0.05, gtr(['E3', 'B3'], 0.3, 6.0, 0.35))
    elif v == 4:
        put(b, 0, harmonic('B5', 0.4, 0.3), -0.2)
        put(b, 0.06, harmonic('E6', 0.5, 0.3), 0.2)
    else:
        m0, m1 = midi('A1'), midi('A2')
        put(b, 0, bass_pluck(m0, 0.12, 0.6))
        put(b, 0.07, bass_pluck(m1, 0.2, 0.6))
    return finish(b, 0.12, 0.6)


def ui_popup_close(v):
    b = sfx(0.9)
    if v == 1:
        put(b, 0, pick_scrape(0.22, up=False, vel=0.45))
    elif v == 2:
        put(b, 0, tom('D3', 0.5), 0.3)
        put(b, 0.07, tom('A2', 0.5), -0.3)
    elif v == 3:
        put(b, 0, amp_switch(0.45, hum=False))
        put(b, 0.02, downer(0.18, 2500, 500, 0.25))
    elif v == 4:
        put(b, 0, harmonic('E6', 0.35, 0.28), 0.2)
        put(b, 0.06, harmonic('B5', 0.45, 0.28), -0.2)
    else:
        put(b, 0, bass_pluck('A2', 0.12, 0.6))
        put(b, 0.07, bass_pluck('A1', 0.2, 0.6))
    return finish(b, 0.12, 0.6)


def ui_autospin(v):
    b = sfx(1.0)
    if v == 1:
        for k, nt in enumerate(('E3', 'G3', 'A3')):
            put(b, k * 0.08, gtr([nt], 0.12, 8.0, 0.45), -0.2 + 0.2 * k)
    elif v == 2:
        for k in range(6):
            put(b, k * 0.045, rock_snare(0.25 + 0.08 * k), 0.0)
    elif v == 3:
        put(b, 0, amp_switch(0.5))
        put(b, 0.04, whoosh(0.3, 500, 4000, 0.3))
    elif v == 4:
        for k, nt in enumerate(('E5', 'B5', 'E6')):
            put(b, k * 0.07, harmonic(nt, 0.4, 0.28), -0.3 + 0.3 * k)
    else:
        for k, nt in enumerate(('E1', 'G1', 'A1', 'B1')):
            put(b, k * 0.06, bass_pluck(nt, 0.1, 0.5))
    return finish(b, 0.1, 0.6)


def ui_bet(v, up):
    b = sfx(0.5)
    nt = ('A3', 'E4', 'A2', 'B5', 'A2') if up else ('E3', 'B3', 'E2', 'E5', 'E2')
    if v == 1:
        put(b, 0, gtr([nt[0]], 0.14, 6.0, 0.4))
    elif v == 2:
        put(b, 0, tom('D3' if up else 'A2', 0.45))
    elif v == 3:
        put(b, 0, amp_switch(0.4, hum=False))
        put(b, 0.01, sine(np.geomspace(900, 1500, n_of(0.06)) if up else np.geomspace(1500, 900, n_of(0.06)), 0.06)
            * expdec(n_of(0.06), 0.02) * 0.3)
    elif v == 4:
        put(b, 0, harmonic(nt[3], 0.3, 0.3))
    else:
        put(b, 0, bass_pluck(nt[4], 0.15, 0.55))
    return finish(b, 0.06, 0.4)


def ui_menu(v):
    b = sfx(0.6)
    if v == 1:
        put(b, 0, mute_tick(0.45))
        put(b, 0.06, mute_tick(0.4, 'A3'))
    elif v == 2:
        put(b, 0, hat(0.4), -0.2)
        put(b, 0.06, hat(0.35, open_=True), 0.2)
    elif v == 3:
        put(b, 0, amp_switch(0.45))
    elif v == 4:
        put(b, 0, harmonic('G5', 0.35, 0.3))
    else:
        put(b, 0, bass_pluck('D2', 0.14, 0.5))
        put(b, 0.06, bass_pluck('A2', 0.14, 0.45))
    return finish(b, 0.08, 0.5)


def ui_turbo(v):
    b = sfx(1.0)
    if v == 1:
        put(b, 0, pick_scrape(0.3, up=True, vel=0.6))
        put(b, 0.28, gtr(['E3', 'B3', 'E4'], 0.2, 10.0, 0.5))
    elif v == 2:
        for k in range(8):
            put(b, k * 0.04, rock_kick(0.55 + 0.05 * k))
        put(b, 0.32, choke_crash(0.5, 0.2), 0.2)
    elif v == 3:
        put(b, 0, amp_switch(0.5))
        put(b, 0.03, riser(0.35, 400, 6000, 0.35))
    elif v == 4:
        put(b, 0, lead('E6', 0.45, 0.4, bend=3, gain=18.0))
    else:
        for k in range(5):
            put(b, k * 0.05, bass_pluck(midi('E1') + 2 * k, 0.1, 0.55))
    return finish(b, 0.08, 0.5)


# =============================================================================
# catalog

POSITIONS = [
    ('bg_bonus', 'БГ бонусного уровня', [
        ('Overdrive', '140 BPM хард-рок, соло-гитара не замолкает'),
        ('Punk Frenzy', '196 BPM панк вдвое быстрее, лид в октаву'),
        ('Thrash Jackpot', '170 BPM трэш: глушёные шестнадцатые и двойная бочка'),
        ('Stadium Anthem', '124 BPM гимн стадиона: открытые аккорды, томы, мелодия'),
        ('Boogie Fever', '184 BPM рок-н-ролльный шаффл с непрерывным соло'),
    ], None, True),
    ('spin', 'Нажатие на спин', [
        ('Аккорд + бочка', 'группа бьёт по кнопке'), ('Скрежет медиатора', 'медиатор по обмотке вниз'),
        ('Флэм + чок тарелки', 'малый с форшлагом и заглушённый крэш'), ('Тумблер + чаг', 'щелчок усилителя и глушёный аккорд'),
        ('Бас-провал', 'басовый щипок и свист вниз'),
    ], spin, False),
    ('reel_loop', 'Вращение барабанов (петля)', [
        ('Глушёный чаг', 'шестнадцатые глушёными струнами'), ('Дробь малого', 'тихая дробь и райд'),
        ('Тремоло', 'тремоло на одной ноте'), ('Хэты + пульс', 'хэты шестнадцатыми, бочка и бас'),
        ('Гул усилителя', 'перегруженный бурдон восьмыми'),
    ], reel_loop, True),
    ('reel_stop', 'Приземление барабанов (3 барабана подряд)', [
        ('Глушёный аккорд', 'аккорд растёт от барабана к барабану'), ('Томы', 'напольный → навесные'),
        ('Бочка + цепь', 'удар с металлическим лязгом'), ('Римшот + бас', 'обод малого и бас'),
        ('Бас + флажолет', 'глухой бас и звонкий флажолет'),
    ], reel_stop_demo, False),
    ('coin_land', 'Приземление монеты', [
        ('Монета + флажолет', ''), ('Монета + коровий колокольчик', ''), ('Тяжёлое золото', 'глухой удар и звон'),
        ('Колокол райда', ''), ('Россыпь монет', 'маленький дождь монет'),
    ], coin_land, False),
    ('win_small', 'Маленький выигрыш', None, win_small, False),
    ('win_big', 'Big Win', None, win_big, False),
    ('win_mega', 'Mega Win', None, win_mega, False),
    ('win_epic', 'Epic Win', None, win_epic, False),
    ('bonus_enter', 'Вход в бонус', None, bonus_enter, False),
    ('bonus_exit', 'Выход из бонуса', None, bonus_exit, False),
    ('ui_click', 'Клик', None, ui_click, False),
    ('ui_popup_open', 'Открытие попапа', None, ui_popup_open, False),
    ('ui_popup_close', 'Закрытие попапа', None, ui_popup_close, False),
    ('ui_autospin', 'Автоспин', None, ui_autospin, False),
    ('ui_bet_plus', 'Ставка +', None, lambda v: ui_bet(v, True), False),
    ('ui_bet_minus', 'Ставка −', None, lambda v: ui_bet(v, False), False),
    ('ui_menu', 'Меню', None, ui_menu, False),
    ('ui_turbo', 'Турбо', None, ui_turbo, False),
]
BAND_TITLES = [(f'{i}. {BANDS[i]["name"]}', '') for i in range(1, 6)]
UI_TITLES = [('Медиатор / струны', ''), ('Ударная установка', ''), ('Усилитель / металл', ''),
             ('Флажолеты', ''), ('Бас', '')]
BONUS_LOOPS = [bonus_1, bonus_2, bonus_3, bonus_4, bonus_5]


def titles_for(key):
    if key.startswith('ui_'):
        return UI_TITLES
    return [(BANDS[i]['name'].capitalize(), '') for i in range(1, 6)]


# The user's picks (2026-11-05, from the audition page) -> the game's files.
PICKS = {
    'bg_base': 2, 'bg_bonus': 2, 'spin': 2, 'reel_loop': 1, 'reel_stop': 1, 'coin_land': 1,
    'win_small': 1, 'win_big': 1, 'win_mega': 1, 'win_epic': 1, 'bonus_enter': 1, 'bonus_exit': 1,
    'ui_click': 1, 'ui_popup_open': 1, 'ui_popup_close': 1, 'ui_autospin': 1, 'ui_bet_plus': 1,
    'ui_bet_minus': 1, 'ui_menu': 1, 'ui_turbo': 1,
}
GAME = os.path.join(ROOT, 'front/sound/neon-joker-spins-c')


def install():
    """Copy the picked takes to front/sound/neon-joker-spins-c/<position>.mp3;
    the reel stop goes out per reel (reel_stop_1..3) for the game."""
    os.makedirs(GAME, exist_ok=True)
    for key, v in PICKS.items():
        if key == 'reel_stop':
            for k in range(3):
                write_mp3(os.path.join(GAME, f'reel_stop_{k + 1}.mp3'), soft_master(reel_stop_one(v, k), drive=1.1, peak=0.89))
            continue
        shutil.copy(os.path.join(OUT, f'{key}_{v}.mp3'), os.path.join(GAME, f'{key}.mp3'))
    print('installed ->', GAME)


if __name__ == '__main__' and sys.argv[1:] == ['install']:
    install()
    sys.exit()

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    only = set(sys.argv[1:])
    man_path = os.path.join(AUD, 'pack.json')
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    # bg_base = the round-2 loops already rendered by the music script
    music = json.load(open(os.path.join(AUD, 'manifest.json')))
    if not only or 'bg_base' in only:
        items = []
        for k in range(1, 6):
            shutil.copy(os.path.join(AUD, f'music_{k}.mp3'), os.path.join(OUT, f'bg_base_{k}.mp3'))
            m = music[f'music_{k}']
            items.append({'file': f'pack/bg_base_{k}.mp3', 'title': m['title'], 'desc': f"{m['tag']} — {m['desc']}",
                          'sec': m['sec'], 'loop': True})
        manifest['bg_base'] = {'title': 'БГ базового уровня', 'items': items}
    for key, title, names, fn, loop in POSITIONS:
        if only and key not in only:
            continue
        names = names or titles_for(key)
        items = []
        for v in range(1, 6):
            if key == 'bg_bonus':
                st = soft_master(BONUS_LOOPS[v - 1](), drive=1.2, peak=0.89)
                kbps = 192
            else:
                st = soft_master(fn(v), drive=1.0 if key.startswith('ui_') else 1.1, peak=0.89)
                kbps = 160
            path = os.path.join(OUT, f'{key}_{v}.mp3')
            sec = write_mp3(path, st, kbps)
            items.append({'file': f'pack/{key}_{v}.mp3', 'title': names[v - 1][0], 'desc': names[v - 1][1],
                          'sec': round(sec, 2), 'loop': loop})
            print(key, v, f'{sec:.2f}s', flush=True)
        manifest[key] = {'title': title, 'items': items}
    order = ['bg_base'] + [p[0] for p in POSITIONS]
    manifest = {k: manifest[k] for k in order if k in manifest}
    json.dump(manifest, open(man_path, 'w'), ensure_ascii=False, indent=1)
