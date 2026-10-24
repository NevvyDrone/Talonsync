"""Compose and render the TalonStar 4000 smooth jazz loop (an original tune, "Owl Weather").

Pure numpy synthesis: FM electric piano, upright bass, brushes and ride, vibraphone melody and a
soft pad, with a convolution room. The tail of the last bar is wrapped onto the start, so the file
loops seamlessly.  Usage: python make_jazz.py out.wav [sample_rate] [mono]
"""
import math
import sys
import wave

import numpy as np

SR = 44100
BPM = 88
BEAT = 60.0 / BPM
BAR = 4 * BEAT
SWING = 0.64          # long-short eighths
rng = np.random.default_rng(4000)

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def m(name, octave):
    return NOTE[name] + 12 * (octave + 1)


# 16 bars: (root, rootless voicing as intervals above root, placed around middle C)
PROG = [
    ("F", [4, 7, 11, 14]), ("D", [3, 7, 10, 14]), ("G", [3, 7, 10, 14]), ("C", [4, 10, 14, 21]),
    ("A", [3, 7, 10, 14]), ("D", [4, 10, 13, 16]), ("G", [3, 7, 10, 14]), ("C", [4, 10, 14, 21]),
    ("Bb", [4, 7, 11, 14]), ("Bb", [3, 7, 9, 14]), ("A", [3, 7, 10, 14]), ("D", [3, 7, 10, 14]),
    ("G", [3, 7, 10, 14]), ("C", [4, 10, 14, 21]), ("F", [4, 7, 11, 14]), ("C", [5, 10, 14, 19]),
]
BARS = len(PROG)
LENGTH = BARS * BAR
N = int(round(LENGTH * SR))
TAIL = int(4 * SR)


def place(buf, start_s, sig):
    i = int(round(start_s * SR))
    if i < 0:
        sig = sig[-i:]; i = 0
    end = min(len(buf), i + len(sig))
    buf[i:end] += sig[:end - i]


def env_adsr(n, a=0.005, d=0.3, s=0.4, r=0.3, hold=None):
    t = np.arange(n) / SR
    hold = hold if hold is not None else n / SR - r
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / d))
    rel = np.clip(1 - (t - hold) / r, 0, 1)
    return e * np.where(t > hold, rel, 1.0)


# ---------------------------------------------------------------- instruments
def rhodes(freq, dur, vel=0.7):
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    idx = (1.1 + 1.6 * vel) * np.exp(-t * 3.5)                  # bark on attack, mellow sustain
    mod = np.sin(2 * np.pi * freq * t)
    tone = np.sin(2 * np.pi * freq * t + idx * mod)
    tine = 0.10 * vel * np.sin(2 * np.pi * freq * 14.0 * t) * np.exp(-t * 28)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.6 * t)
    e = env_adsr(n, a=0.003, d=0.9, s=0.25, r=0.45, hold=dur)
    return (tone + tine) * e * trem * vel


def bass(freq, dur, vel=0.8):
    n = int((dur + 0.35) * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) * np.exp(-t * 6) + 0.12 * np.sin(6 * np.pi * freq * t) * np.exp(-t * 10)
    thump = 0.5 * np.sin(2 * np.pi * freq * 0.5 * t) * np.exp(-t * 30)
    e = env_adsr(n, a=0.008, d=0.5, s=0.55, r=0.18, hold=dur)
    return (sig + thump) * e * vel


def vibes(freq, dur, vel=0.6):
    n = int((dur + 1.6) * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 4.0 * t) * np.exp(-t * 7) + 0.05 * np.sin(2 * np.pi * freq * 10.0 * t) * np.exp(-t * 20)
    motor = 1 + 0.28 * np.sin(2 * np.pi * 5.2 * t)              # the vibraphone's rotating fans
    e = np.exp(-t * 1.6) * np.clip(t / 0.002, 0, 1)
    e *= np.clip(1 - (t - dur - 0.25) / 1.2, 0, 1)
    return sig * motor * e * vel


def pad(freqs, dur, vel=0.18):
    n = int((dur + 1.0) * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            ph = rng.random() * 2 * np.pi
            ff = f * 2 ** (det / 12)
            # soft "string" = a few decaying harmonics of a saw
            for h in range(1, 6):
                sig += np.sin(2 * np.pi * ff * h * t + ph * h) / (h * h)
    e = env_adsr(n, a=0.6, d=1.0, s=0.9, r=0.9, hold=dur)
    return sig * e * vel / (len(freqs) * 3)


def noise(n):
    return rng.standard_normal(n)


def onepole(x, a):
    """simple lowpass; a near 1 = darker"""
    y = np.empty_like(x)
    acc = 0.0
    b = 1 - a
    # vectorized-ish via lfilter would be nicer; this is fine for short hits
    for i in range(len(x)):
        acc = b * x[i] + a * acc
        y[i] = acc
    return y


def _bank(kind, count, maker):
    return [maker() for _ in range(count)]


def make_brush():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    x = noise(n)
    hp = x - onepole(x, 0.85)
    swish = hp * (np.clip(t / 0.03, 0, 1) * np.exp(-t * 7))
    return swish * 0.5


def make_ride():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    x = noise(n)
    hp = x - onepole(x, 0.6)
    ping = sum(np.sin(2 * np.pi * f * t) for f in (3150, 4280, 5130, 6620)) * 0.08
    return (onepole(hp, 0.3) * 0.18 + ping) * np.exp(-t * 3.2) * np.clip(t / 0.001, 0, 1)


def make_kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 55 + 60 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def make_hat():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    x = noise(n)
    hp = x - onepole(x, 0.4)
    return hp * np.exp(-t * 40) * 0.5


# ---------------------------------------------------------------- reverb
def room(x, seconds=2.2, mix=0.22):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = noise(n) * np.exp(-t * 3.0 / seconds * 2.2)
    ir = ir - onepole(ir, 0.5) * 0.5                            # a touch darker
    ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + n
    size = 1 << (L - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    return x * (1 - mix) + wet * mix * 1.6


def swing(beat, eighth):
    """time (s) of eighth-note `eighth` (0/1) within quarter `beat` (0..)"""
    return (beat + (SWING if eighth else 0.0)) * BEAT


def render():
    total = N + TAIL
    ep, bs, vb, dr, pd = (np.zeros(total) for _ in range(5))
    brushes = _bank("b", 6, make_brush)
    rides = _bank("r", 4, make_ride)
    kick, hats = make_kick(), _bank("h", 4, make_hat)

    for bar, (root, voicing) in enumerate(PROG):
        t0 = bar * BAR
        r = m(root, 2)
        while r < m("E", 2):
            r += 12
        # --- electric piano: rootless voicing near middle C, gentle comping figures
        base = m(root, 3)
        while base + voicing[0] < m("A", 3):
            base += 12
        while base + voicing[0] > m("E", 4):
            base -= 12
        notes = [base + iv for iv in voicing]
        figure = [(0, 0, 1.5, 0.62), (1, 1, 0.9, 0.48)] if bar % 2 == 0 else [(0, 1, 1.2, 0.5), (2, 1, 1.3, 0.55)]
        if bar % 4 == 3:
            figure = [(0, 0, 2.0, 0.6), (3, 0, 0.8, 0.42)]
        for beat, e8, dur_beats, vel in figure:
            st = t0 + swing(beat, e8)
            for k, nn in enumerate(notes):
                v = vel * (0.85 + 0.3 * rng.random())
                place(ep, st + k * 0.008 + rng.normal(0, 0.003), rhodes(hz(nn), dur_beats * BEAT, v))
        # --- pad underneath
        place(pd, t0, pad([hz(n) for n in notes[:3]], BAR * 0.98))
        # --- bass: root, fifth, a passing line into the next bar
        nxt = PROG[(bar + 1) % BARS][0]
        nr = m(nxt, 2)
        while nr < m("E", 2):
            nr += 12
        approach = nr - 1 if rng.random() < 0.5 else nr + 1
        third = r + voicing[0]
        line = [(0, r, 1.6), (2, r + 7, 0.9), (3, third if bar % 2 else approach, 0.9)]
        if bar % 4 == 1:
            line = [(0, r, 0.9), (1, r + 7, 0.9), (2, r + 12, 0.9), (3, approach, 0.9)]
        for beat, nn, d in line:
            place(bs, t0 + beat * BEAT + rng.normal(0, 0.004), bass(hz(nn), d * BEAT, 0.75 + 0.15 * rng.random()))
        # --- drums: ride with the swing pattern, brushes on 2 and 4, feathered kick, hat foot on 2 and 4
        for beat in range(4):
            place(dr, t0 + beat * BEAT, rides[rng.integers(4)] * (0.55 if beat % 2 == 0 else 0.42))
            if beat % 2 == 1:
                place(dr, t0 + swing(beat, 1), rides[rng.integers(4)] * 0.30)
                place(dr, t0 + beat * BEAT, brushes[rng.integers(6)] * 0.9)
                place(dr, t0 + beat * BEAT, hats[rng.integers(4)] * 0.5)
            place(dr, t0 + beat * BEAT + 0.01, brushes[rng.integers(6)] * 0.12)      # continuous sweep
            place(dr, t0 + beat * BEAT, kick * (0.35 if beat in (0, 2) else 0.15))

    # --- vibraphone melody: an original 16-bar tune, two 8-bar phrases (scale degrees in F major + chromatic)
    F = m("F", 5)
    mel = [  # (bar, beat, eighth, semitones from F5, length in beats)
        (0, 0, 1, -5, 1.0), (0, 1, 1, -3, 0.5), (0, 2, 0, -1, 1.5), (0, 3, 1, 0, 1.0),
        (1, 1, 0, 2, 2.0), (1, 3, 1, 0, 0.5),
        (2, 0, 0, -2, 1.0), (2, 1, 0, 0, 0.5), (2, 1, 1, 2, 0.5), (2, 2, 0, 3, 2.0),
        (3, 0, 1, 2, 1.0), (3, 1, 1, 0, 1.0), (3, 2, 1, -2, 1.5),
        (4, 0, 0, -1, 1.5), (4, 2, 0, -5, 1.0), (4, 3, 0, -1, 1.0),
        (5, 0, 0, 1, 2.0), (5, 2, 1, -2, 1.0), (5, 3, 1, -3, 0.5),
        (6, 0, 0, -2, 1.0), (6, 1, 0, 2, 1.0), (6, 2, 0, 5, 1.5), (6, 3, 1, 3, 0.5),
        (7, 0, 0, 2, 3.0),
        (8, 0, 1, 5, 1.0), (8, 1, 1, 4, 0.5), (8, 2, 0, 2, 1.5), (8, 3, 1, 0, 1.0),
        (9, 1, 0, 1, 2.0), (9, 3, 0, -2, 1.0),
        (10, 0, 0, -1, 1.0), (10, 1, 0, 0, 0.5), (10, 1, 1, 2, 0.5), (10, 2, 0, 4, 1.5), (10, 3, 1, 2, 0.5),
        (11, 0, 0, 0, 1.0), (11, 1, 0, -3, 2.0),
        (12, 0, 1, -2, 1.0), (12, 1, 1, 0, 0.5), (12, 2, 0, 2, 1.0), (12, 3, 0, 3, 1.0),
        (13, 0, 0, 4, 1.5), (13, 2, 0, 2, 1.0), (13, 3, 0, -2, 1.0),
        (14, 0, 0, 0, 3.0),
        (15, 2, 1, -5, 0.5), (15, 3, 0, -3, 0.5), (15, 3, 1, -1, 0.5),
    ]
    for bar, beat, e8, semi, d in mel:
        st = bar * BAR + swing(beat, e8) + rng.normal(0, 0.004)
        place(vb, st, vibes(hz(F + semi), d * BEAT, 0.5 + 0.12 * rng.random()))

    dr = onepole(dr, 0.55)                                      # brushes are soft and dark
    mix = 0.95 * ep / 4 + bs * 0.55 + vb * 0.40 + dr * 0.11 + pd * 0.9
    mix = room(mix)
    # wrap the tail onto the start: seamless loop
    out = mix[:N].copy()
    out[:TAIL] += mix[N:N + TAIL]
    # gentle bus compression + limiter
    out = out / max(1e-6, np.percentile(np.abs(out), 99.95))
    out = np.tanh(out * 0.9) * 0.78                             # just rounds off the odd peak
    return out


def stereo(x):
    """a little width: a short Haas copy on the right, darker"""
    d = int(0.012 * SR)
    r = np.roll(x, d) * 0.9 + x * 0.1
    return np.stack([x, r], axis=1)


def write_wav(path, x, sr, channels):
    if sr != SR:
        idx = np.arange(0, len(x), SR / sr)
        x = np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], axis=1) if x.ndim == 2 else np.interp(idx, np.arange(len(x)), x)
    if channels == 1 and x.ndim == 2:
        x = x.mean(axis=1)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "talonstar_jazz.wav"
    sr = int(sys.argv[2]) if len(sys.argv) > 2 else SR
    mono = len(sys.argv) > 3 and sys.argv[3] == "mono"
    x = render()
    write_wav(out, x if mono else stereo(x), sr, 1 if mono else 2)
    print(f"wrote {out}: {LENGTH:.2f} s loop, {BARS} bars at {BPM} bpm")
