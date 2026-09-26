"""20s launch score: A minor, 120 BPM, Am-F-C-G. SFX are tuned to the chord under them.

Timings mirror composition.html (scene cuts, typing, output lines, FATAL rows).
"""
import wave

import numpy as np

SR, DUR = 44100, 20.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)

mf = lambda m: 440.0 * 2 ** ((m - 69) / 12)
CHORDS = [(57, 60, 64), (53, 57, 60), (55, 60, 64), (55, 59, 62)]  # Am F C/G G
ROOTS = [45, 41, 48, 43]
chord_at = lambda s: int(s // 2) % 4


def env(n, a, d):
    x = np.arange(n) / SR
    return np.minimum(1, x / max(a, 1e-4)) * np.exp(-x / d)


def lowpass(x, cutoff):
    # one-pole, good enough for softening a pad
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def add(buf, start, sig, gain):
    i = int(start * SR)
    j = min(N, i + len(sig))
    if i < N:
        buf[i:j] += sig[: j - i] * gain


music = np.zeros(N)
sfx = np.zeros(N)

# Pad: detuned soft saws per bar, crossfaded
for bar in range(10):
    s0, s1 = bar * 2.0, bar * 2.0 + 2.0
    n = int(2.4 * SR)
    x = np.arange(n) / SR
    sig = np.zeros(n)
    for m in CHORDS[bar % 4]:
        for det in (-0.08, 0.08):
            f = mf(m + det)
            for h in (1, 2, 3):
                sig += np.sin(2 * np.pi * f * h * x + h) / h**1.6
    shape = np.minimum(1, x / 0.35) * np.clip((2.4 - x) / 0.4, 0, 1)
    add(music, s0, sig * shape, 0.05)
music = lowpass(music, 1400)

# Bass + kick enter on the reveal (4.0s); hook stays sparse
beat = 0.5
for k in range(int(DUR / beat)):
    s = k * beat
    root = ROOTS[chord_at(s)]
    n = int(0.45 * SR)
    x = np.arange(n) / SR
    if s >= 4.0:
        kick_f = 45 + 70 * np.exp(-x * 30)
        kick = np.sin(2 * np.pi * np.cumsum(kick_f) / SR) * np.exp(-x * 9)
        add(music, s, kick, 0.55)
        bass = np.sin(2 * np.pi * mf(root - 12) * x) * env(n, 0.01, 0.25)
        add(music, s, bass, 0.22)
    if s >= 7.6 and s < 19.0:
        hat = rng.standard_normal(int(0.04 * SR))
        hat = np.diff(hat, prepend=0) * env(len(hat), 0.001, 0.012)
        add(music, s + 0.25, hat, 0.03)
    if s < 4.0:
        # hook: quiet high tick on each beat, like a clock waiting for the reveal
        tick = np.sin(2 * np.pi * mf(81) * x) * env(n, 0.002, 0.05)
        add(music, s, tick, 0.05)


def pluck(m, dur=0.6, bright=3):
    n = int(dur * SR)
    x = np.arange(n) / SR
    sig = sum(np.sin(2 * np.pi * mf(m) * h * x) / h**2 for h in range(1, bright + 1))
    return sig * env(n, 0.003, dur / 4)


# Scan swell before the badges flip
n = int(0.6 * SR)
noise = lowpass(rng.standard_normal(n), 2500) * np.sin(np.linspace(0, np.pi, n)) ** 2
add(sfx, 1.7, noise, 0.25)
# Badge flips: low muted A and E
add(sfx, 2.05, pluck(45, 0.5, 2), 0.35)
add(sfx, 2.25, pluck(40, 0.5, 2), 0.3)

# Scene cuts: chord-tone pluck an octave up
for cut in (4.0, 7.6, 11.6, 15.6, 18.0):
    add(sfx, cut, pluck(CHORDS[chord_at(cut)][2] + 12, 0.9, 4), 0.12)

# Typing ticks
for i in range(20):
    tick = rng.standard_normal(int(0.012 * SR))
    add(sfx, 7.95 + i / 30, np.diff(tick, prepend=0) * env(len(tick), 0.0005, 0.004), 0.05)
for i in range(49):
    tick = rng.standard_normal(int(0.012 * SR))
    add(sfx, 12.4 + i / 60, np.diff(tick, prepend=0) * env(len(tick), 0.0005, 0.004), 0.04)

# Output lines climb the A minor pentatonic; PASSED lands on a bright A
penta = [69, 72, 74, 76, 79, 81, 84, 86, 88]
for i in range(9):
    add(sfx, 8.8 + i * 0.2, pluck(penta[i], 0.25, 2), 0.05)
for m in (69, 76, 81):
    add(sfx, 8.8 + 9 * 0.2, pluck(m, 1.0, 3), 0.08)

# FATAL rows: low, muted, slightly driven A
for s in (13.3, 13.75):
    add(sfx, s, np.tanh(pluck(33, 0.6, 3) * 3), 0.25)

# Proof rows: soft rising ticks
for i, m in enumerate((72, 76, 79)):
    add(sfx, 16.3 + i * 0.22, pluck(m, 0.35, 2), 0.06)

mix = music + sfx * 0.9
fade = np.clip((DUR - t) / 1.2, 0, 1)
mix *= np.minimum(1, t / 0.08) * fade
mix = np.tanh(mix * 1.4) / np.tanh(1.4)
mix *= 0.89 / np.max(np.abs(mix))

stereo = np.stack([mix, np.roll(mix, 220) * 0.97], axis=1)  # 5ms Haas widening
with wave.open("score.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((stereo * 32767).astype(np.int16).tobytes())
print("score.wav written")
