"""Neon Joker Spins C (Rock Chrome) — five ROCK base-game loops, synthesized
in code for an audition (no samples, no AI audio service).

Round 2 (round 1 sounded like synths, not a band; it is kept in
front/sound/neon-joker-spins-c/_audition/round1/). The guitars are now plucked
strings (Karplus-Strong) recorded "DI" onto their own tracks and run through
an amp model as a whole — pre-emphasis, two tanh gain stages, cabinet
filter — like a real rhythm track, so chords intermodulate into proper grit.
Every rhythm part is double-tracked: two separate takes (own pluck noise, a
few cents and milliseconds apart) panned hard L/R. The drum bus gets a room
and parallel saturation; bass is a picked string with a little drive.

Reuses Song / drums / reverb / mp3 export from scripts/great_uniqorn_audio.py.

    <venv with numpy scipy lameenc>/bin/python scripts/neon_joker_spins_c_music.py [music_N ...]

Output: front/sound/neon-joker-spins-c/_audition/music_<1..5>.mp3 + manifest.json;
listening page: front/sound/neon-joker-spins-c/_audition/index.html.
"""

import json
import os
import sys

import numpy as np
from scipy.signal import lfilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from great_uniqorn_audio import (  # noqa: E402
    SR, Song, crash, env, expdec, hat, hz, kick, midi, n_of, noise, pan, reverb, ride,
    snare, soft_master, sos_bp, sos_hp, sos_lp, tom, write_mp3,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'front/sound/neon-joker-spins-c/_audition')
RNG = np.random.default_rng(11)


# =============================================================================
# strings

def string(m, sec, vel=0.8, bright=0.85, damp=0.9985, cents=0.0):
    """One plucked string (Karplus-Strong), MIDI note m."""
    f = hz(m) * 2 ** (cents / 1200)
    n = n_of(sec)
    period = max(2, int(round(SR / f)))
    exc = np.zeros(n)
    burst = RNG.uniform(-1, 1, period)
    burst = lfilter([bright, 1 - bright], [1], burst)
    burst -= burst.mean()
    exc[:period] = burst
    a = np.zeros(period + 2)
    a[0] = 1
    a[period] = -damp * 0.5
    a[period + 1] = -damp * 0.5
    y = lfilter([1], a, exc)
    return y * env(n, a=0.0005, d=0, s=1, r=0.025) * vel


def chord_di(notes, sec, vel=0.8, mute=False, strum=0.005, cents=0.0):
    """Down-strum of several strings (low to high), clean DI."""
    n = n_of(sec)
    x = np.zeros(n)
    for k, m in enumerate(notes):
        off = n_of(strum * k)
        s = string(m, sec - strum * k, vel, bright=0.7 if mute else 0.9,
                   damp=0.985 if mute else 0.9985, cents=cents + RNG.uniform(-3, 3))
        x[off:off + len(s)] += s[:n - off]
    if mute:
        x = sos_lp(x, 900) * expdec(n, 0.09) * 2.2
    return x


def power5(m, octave=True):
    return [m, m + 7] + ([m + 12] if octave else [])


def amp(x, gain=9.0, tight=110, presence=0.45, fizz=5200):
    """High-gain amp + 4x12 cab on a whole DI track."""
    x = sos_hp(x, tight)
    x = x + 1.2 * sos_bp(x, 700, 2600)               # pre-emphasis into the gain stages
    x = x / (np.abs(x).max() + 1e-9)
    y = np.tanh(gain * x)
    y = sos_lp(y, 7500)
    y = np.tanh(2.2 * y + 0.18) - np.tanh(0.18)       # asymmetric 2nd stage
    y = sos_hp(y, 75)
    y = sos_lp(sos_lp(y, fizz), fizz)                 # steep cab roll-off
    y = y + presence * sos_bp(y, 1800, 3600) - 0.35 * sos_bp(y, 380, 650)
    return y / (np.abs(y).max() + 1e-9)


def bass_di(m, sec, vel=0.9, mute=False):
    """Picked bass: string + sub sine, a little drive."""
    n = n_of(sec)
    t = np.arange(n) / SR
    x = string(m, sec, 1.0, bright=0.6, damp=0.997 if not mute else 0.99)
    x = x + 0.6 * np.sin(2 * np.pi * hz(m) * t) * expdec(n, 0.6 if not mute else 0.15)
    x = np.tanh(1.8 * x)
    return sos_lp(x, 2400) * env(n, a=0.002, d=0, s=1, r=0.03) * vel


def lead_di(note, sec, vel=0.7, bend_from=0.0, bend_time=0.08, vib=0.25):
    """Sustained lead for the amp: harmonics with pick noise, an optional
    bend up into the note (semitones) and vibrato (semitones)."""
    m = midi(note) if isinstance(note, str) else note
    n = n_of(sec)
    t = np.arange(n) / SR
    cents = -bend_from * 100 * np.clip(1 - t / bend_time, 0, 1)
    cents = cents + vib * 100 * np.sin(2 * np.pi * 5.8 * t) * np.clip((t - 0.18) / 0.25, 0, 1)
    f = hz(m) * 2 ** (cents / 1200)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum((0.85 ** k) * np.sin(k * ph) for k in range(1, 14))
    x[:n_of(0.01)] += sos_bp(noise(0.01), 1500, 6000) * 1.5
    return x * env(n, a=0.006, d=0.2, s=0.75, r=0.06) * vel


# =============================================================================
# drums

def rock_kick(vel=1.0):
    k = kick(vel, tone=56, punch=1.6)
    k[:n_of(0.006)] += sos_bp(noise(0.006), 2000, 6000) * 0.8 * vel   # beater click
    return k


def rock_snare(vel=0.95):
    s = snare(vel, tone=195, snap=1.5, sec=0.34)
    n = len(s)
    return s + 0.35 * vel * np.sin(2 * np.pi * 330 * np.arange(n) / SR) * expdec(n, 0.05)


def drums_bus(st):
    """Room + parallel saturation, the 'band in a room' glue."""
    room = reverb(st, mix=0.22, t60=0.9, tone=7000)[:, :st.shape[1]]
    peak = np.abs(room).max() + 1e-9
    return room + 0.35 * np.tanh(3.0 * room / peak) * peak


# =============================================================================
# song helpers

def mix_mono(song, bus, start_sec, x):
    buf = song.bus(bus)
    i = n_of(start_sec) if start_sec > 0 else 0
    end = min(buf.shape[1], i + len(x))
    if end > i:
        buf[0, i:end] += x[:end - i]
        buf[1, i:end] += x[:end - i]


class RockSong(Song):
    """Song + double-tracked guitars and an amp per track."""

    def gtr(self, bar, beat, notes, sec, vel=0.8, mute=False):
        for side, cents, lag in (('gL', -4, 0.0), ('gR', 4, 0.009)):
            x = chord_di(notes, sec, vel * RNG.uniform(0.92, 1.0), mute, cents=cents)
            mix_mono(self, side, self.at(bar, beat) + lag + RNG.uniform(0, 0.004), x)

    def bass(self, bar, beat, m, sec, vel=0.85, mute=False):
        mix_mono(self, 'bass', self.at(bar, beat), bass_di(m, sec, vel, mute))

    def lead(self, bar, beat, note, sec, vel=0.7, bend=0.0):
        mix_mono(self, 'lead', self.at(bar, beat), lead_di(note, sec, vel, bend_from=bend))

    def mixdown(self, gtr_gain=9.0, lead_gain=14.0, levels=None):
        lv = {'drums': 1.0, 'gtr': 0.62, 'bass': 0.62, 'lead': 0.42}
        lv.update(levels or {})
        out = np.zeros((2, n_of(self.length + 4.0)))

        def add(st, g):
            k = min(out.shape[1], st.shape[1])
            out[:, :k] += st[:, :k] * g

        if 'drums' in self.buses:
            d = self.buses['drums']
            add(drums_bus(d / (np.abs(d).max() + 1e-9)), lv['drums'])
        if 'gL' in self.buses:
            add(pan(amp(self.buses['gL'][0], gtr_gain), -0.85), lv['gtr'])
            add(pan(amp(self.buses['gR'][0], gtr_gain), 0.85), lv['gtr'])
        if 'bass' in self.buses:
            b = self.buses['bass'][0]
            add(pan(b / (np.abs(b).max() + 1e-9)), lv['bass'])
        if 'lead' in self.buses:
            ld = amp(self.buses['lead'][0], lead_gain, tight=200, presence=0.6, fizz=6000)
            add(reverb(np.stack([ld, ld]) * 0.5, mix=0.28, t60=1.6), lv['lead'])
        out = np.stack([sos_hp(ch, 35) for ch in out])
        L = n_of(self.length)
        loop = out[:, :L].copy()
        k = min(out.shape[1] - L, L)
        loop[:, :k] += out[:, L:L + k]      # fold the tail onto the start: seamless
        return loop


def backbeat(s, bar, kicks=(0, 2), snares=(1, 3), hats=8, open_last=False, ride_=False, vel=1.0):
    for b in kicks:
        s.add('drums', bar, b, rock_kick(vel))
    for b in snares:
        s.add('drums', bar, b, rock_snare(vel * 0.95), 0.05)
    for i in range(hats):
        b = i * 4 / hats
        if ride_:
            s.add('drums', bar, b, ride(0.32 if i % 2 == 0 else 0.22), 0.35)
        else:
            s.add('drums', bar, b, hat(0.38 if i % 2 == 0 else 0.24, open_=open_last and i == hats - 1), 0.3)


def fill(s, bar, start=2.0, notes=('A2', 'F2', 'D2', 'A1')):
    step = (4 - start) / len(notes)
    for k, nt in enumerate(notes):
        s.add('drums', bar, start + k * step, tom(nt, 0.9), -0.4 + 0.8 * k / max(1, len(notes) - 1))


# =============================================================================
# the five tracks

def m1_hard_rock():
    """Highway Burn — 128 bpm, A: AC/DC-style hard rock. Open-string riff
    (A5 - D/A - A5 stabs), straight eighths on the hats, a huge backbeat and
    a bluesy lead answer every 4 bars in the second half."""
    s = RockSong(128, 16)
    A, D, G, E = midi('A2'), midi('D3'), midi('G2'), midi('E2')
    for bar in range(16):
        backbeat(s, bar, kicks=(0, 1.5, 2), hats=8)
        if bar % 8 == 0:
            s.add('drums', bar, 0, crash(0.75, 1.8), 0.2)
        if bar % 4 == 3:
            fill(s, bar, 3.0, ('G2', 'D2'))
        if bar % 4 < 3:
            riff = [(0, power5(A), 0.4), (0.75, [A + 12, D + 12, A + 19], 0.25), (1.5, power5(A), 0.35),
                    (2.5, [A + 12, D + 12, A + 19], 0.25), (3, power5(A), 0.4)]
            bass_line = [A - 12] * 8
        else:
            riff = [(0, power5(G), 0.5), (1, power5(G), 0.4), (2, power5(D - 12), 0.5), (3, power5(E), 0.45)]
            bass_line = [G - 12] * 4 + [D - 24] * 2 + [E - 12] * 2
        for b, notes, d in riff:
            s.gtr(bar, b, notes, d, 0.85)
        for i, m in enumerate(bass_line):
            s.bass(bar, i / 2, m, 0.22)
        if bar % 4 == 3 and bar >= 8:
            for b, nt, d, bend in ((0, 'A4', 0.4, 0), (0.5, 'C5', 0.4, 0), (1, 'D5', 0.9, 2), (2, 'E5', 0.4, 0),
                                   (2.5, 'G5', 0.4, 0), (3, 'A5', 0.9, 2)):
                s.lead(bar, b, nt, d, 0.7, bend)
    return s.mixdown(gtr_gain=8.0)


def m2_punk():
    """Rebel Yell — 180 bpm, E: punk rock. Down-picked eighths E5-B5-C#5-A5,
    a punk beat, bass with the guitars, a gang-stop every 8 bars."""
    s = RockSong(180, 16)
    prog = ['E2', 'B1', 'C#2', 'A1'] * 4
    for bar in range(16):
        r = midi(prog[bar]) + (12 if prog[bar][-1] == '1' else 0)
        stop = bar % 8 == 7
        for i in range(8):
            if stop and i >= 4:
                break
            s.add('drums', bar, i / 2, rock_kick(0.95) if i % 2 == 0 else rock_snare(0.85), 0.03)
            s.add('drums', bar, i / 2, hat(0.4), 0.3)
            s.gtr(bar, i / 2, power5(r, octave=False), 0.21, 0.85)
            s.bass(bar, i / 2, r - 12, 0.2, 0.9)
        if stop:
            for b in (2, 2.5, 3):
                s.add('drums', bar, b, rock_snare(1.0), 0.0)
                s.add('drums', bar, b, crash(0.5, 0.4), 0.2)
                s.gtr(bar, b, power5(r), 0.18, 0.95)
        if bar % 8 == 0:
            s.add('drums', bar, 0, crash(0.8, 1.6), -0.2)
    return s.mixdown(gtr_gain=10.0, levels={'gtr': 0.68})


def m3_metal():
    """Iron Jackpot — 150 bpm, E: heavy metal. Palm-muted gallop riff
    (eighth + two sixteenths) with double kick on the gallop, chord hits on the
    turnaround and a twin lead in thirds in the second half."""
    s = RockSong(150, 16)
    E = midi('E2')
    for bar in range(16):
        turn = bar % 4 == 3
        for beat in range(4):
            if turn and beat >= 2:
                break
            for off in (0, 0.5, 0.75):
                s.gtr(bar, beat + off, power5(E, octave=False), 0.14, 0.9, mute=True)
                s.bass(bar, beat + off, E - 12, 0.12, 0.85, mute=True)
                s.add('drums', bar, beat + off, rock_kick(0.85))
        if turn:
            for b, root in ((2, 'C3'), (2.5, 'D3'), (3, 'G2'), (3.5, 'A2')):
                m = midi(root) - (12 if midi(root) > midi('B2') else 0)
                s.gtr(bar, b, power5(m), 0.45, 0.9)
                s.bass(bar, b, m - 12, 0.4)
        for b in (1, 3):
            s.add('drums', bar, b, rock_snare(1.0), 0.05)
        for i in range(8):
            s.add('drums', bar, i / 2, ride(0.3) if bar >= 8 else hat(0.33), 0.35)
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.8, 1.6), 0.25)
        if bar >= 8:
            line = {0: [(0, 'B4', 0.5), (0.5, 'C5', 0.5), (1, 'D5', 1.0), (2, 'E5', 1.9)],
                    1: [(0, 'G5', 0.5), (0.5, 'F#5', 0.5), (1, 'E5', 0.5), (1.5, 'D5', 0.5), (2, 'E5', 1.9)],
                    2: [(0, 'B4', 0.5), (0.5, 'C5', 0.5), (1, 'D5', 1.0), (2, 'G5', 1.9)],
                    3: [(0, 'F#5', 0.9), (1, 'E5', 0.9)]}[bar % 4]
            for b, nt, d in line:
                s.lead(bar, b, nt, d, 0.65)
                s.lead(bar, b, midi(nt) - 3, d, 0.45)   # harmony a third below
    return s.mixdown(gtr_gain=12.0, lead_gain=16.0)


def m4_stoner():
    """Desert Chrome — 96 bpm, drop D: stoner / grunge. A fat slow fuzz riff
    on the low D with a bluesy minor-third slide, half-time drums, a washing
    crash-ride and a bending lead over bars 9-16."""
    s = RockSong(96, 16)
    D = midi('D2')
    riff = [(0, D, 0.6), (0.75, D, 0.2), (1, D + 3, 0.4), (1.5, D + 5, 0.5), (2.5, D, 0.2),
            (3, D + 3, 0.2), (3.25, D + 1, 0.2), (3.5, D, 0.45)]
    for bar in range(16):
        for b, m, d in riff:
            s.gtr(bar, b, power5(m), d, 0.95)
            s.bass(bar, b, m - 12, d, 0.95)
        s.add('drums', bar, 0, rock_kick(1.0))
        s.add('drums', bar, 1.5, rock_kick(0.8))
        s.add('drums', bar, 2, rock_snare(1.0), 0.05)
        for i in range(4):
            s.add('drums', bar, i, crash(0.35, 0.9) if bar >= 8 else ride(0.35), 0.3)
        if bar % 4 == 3:
            fill(s, bar, 3.0, ('A2', 'D2', 'A1'))
        if bar >= 8 and bar % 2 == 0:
            s.lead(bar, 0, 'A4', 1.4, 0.7, bend=2)
            s.lead(bar, 1.5, 'C5', 0.4, 0.6)
            s.lead(bar, 2, 'D5', 1.8, 0.7, bend=1)
    return s.mixdown(gtr_gain=14.0, levels={'gtr': 0.7, 'bass': 0.7})


def m5_rock_n_roll():
    """Jackpot Boogie — 168 bpm shuffle, A: rock'n'roll. Chuck Berry boogie
    (5-6 rhythm) on a crunchy amp, walking bass, shuffled backbeat and a
    double-stop lead break on the turnaround."""
    s = RockSong(168, 16, swing=0.33)
    prog = ['A2', 'A2', 'A2', 'A2', 'D3', 'D3', 'A2', 'A2', 'E2', 'D3', 'A2', 'E2'] + ['A2'] * 4
    for bar in range(16):
        r = midi(prog[bar])
        if r > midi('C3'):
            r -= 12
        for i in range(8):
            top = r + (7 if (i // 2) % 2 == 0 else 9)
            s.gtr(bar, i / 2, [r, top], 0.2, 0.75)
            walk = [0, 4, 7, 9, 10, 9, 7, 4][i]
            s.bass(bar, i / 2, r - 12 + walk, 0.2, 0.85)
        backbeat(s, bar, kicks=(0, 2), hats=8, ride_=bar >= 8)
        if bar in (11, 15):
            for b, notes in ((0, ('E5', 'G5')), (1, ('E5', 'G5')), (2, ('D5', 'F#5')), (3, ('C#5', 'E5'))):
                for nt in notes:
                    s.lead(bar, b, nt, 0.4, 0.5, bend=1 if nt == notes[1] else 0)
            fill(s, bar, 3.0, ('G2', 'D2'))
        if bar % 4 == 0:
            s.add('drums', bar, 0, crash(0.6, 1.4), -0.2)
    return s.mixdown(gtr_gain=4.5, levels={'gtr': 0.72})


TRACKS = [
    ('music_1', 'Highway Burn', '128 BPM · хард-рок', m1_hard_rock,
     'Классический хард-рок в духе AC/DC: открытый рифф, прямые восьмые, мощный бэкбит и блюзовые ответы соло-гитары.'),
    ('music_2', 'Rebel Yell', '180 BPM · панк-рок', m2_punk,
     'Быстрый панк: даунстроки восьмыми, бас скачет вместе с гитарами, каждые 8 тактов — общий стоп-брейк с ударами всей группы.'),
    ('music_3', 'Iron Jackpot', '150 BPM · хэви-метал', m3_metal,
     'Галоп глушёными струнами с двойной бочкой, аккордовые удары на развороте, во второй половине — двухголосое соло терциями.'),
    ('music_4', 'Desert Chrome', '96 BPM · стоунер / гранж', m4_stoner,
     'Медленный и очень толстый фуз-рифф в строе drop D, половинный темп, тарелки «плывут», с 9-го такта воет соло с подтяжками.'),
    ('music_5', 'Jackpot Boogie', '168 BPM · рок-н-ролл', m5_rock_n_roll,
     'Буги в духе Чака Берри: шаффл 5–6 на хрустящем перегрузе, шагающий бас, двойные ноты соло на развороте.'),
]


def band_share(st):
    x = st.mean(axis=0)
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    tot = spec.sum()
    return spec[f < 120].sum() / tot, spec[f > 4000].sum() / tot


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    only = set(sys.argv[1:])
    man_path = os.path.join(OUT, 'manifest.json')
    manifest = json.load(open(man_path)) if (os.path.exists(man_path) and only) else {}
    for key, title, tag, fn, desc in TRACKS:
        if only and key not in only:
            continue
        st = soft_master(fn(), drive=1.2, peak=0.89)
        sec = write_mp3(os.path.join(OUT, f'{key}.mp3'), st, 192)
        lo, hi = band_share(st)
        manifest[key] = {'title': title, 'tag': tag, 'desc': desc, 'sec': round(sec, 1)}
        print(f'{key} {title}: {sec:.1f}s  <120Hz {lo:.0%}  >4kHz {hi:.0%}')
    json.dump(manifest, open(man_path, 'w'), ensure_ascii=False, indent=1)
