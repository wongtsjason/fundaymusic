#!/usr/bin/env python3
"""Original school-use genre previews for 我手寫我歌.

Synthesizes six short instrumental clips (under 10 seconds each).
No commercial recordings, samples, or copyrighted melodies are used.
The pieces are simple original phrases so a parent can tell the genres apart
on a phone speaker: Cantopop, K-pop, folk, ballad, light pop, and rock.

Requires Python 3, NumPy, and ffmpeg with libmp3lame.
"""

from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "audio"

# Pitch gate: oscillators should land near the requested note.
PITCH_TOLERANCE = 0.08


def hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


def note(name: str) -> int:
    """Scientific pitch name to MIDI. 'C4' = 60, 'F#5', 'Bb3'."""
    name = name.strip()
    accidental = 0
    if name[1:2] == "#":
        accidental = 1
        octave = int(name[2:])
        letter = name[0]
    elif name[1:2] == "b":
        accidental = -1
        octave = int(name[2:])
        letter = name[0]
    else:
        octave = int(name[1:])
        letter = name[0]
    offsets = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return 12 * (octave + 1) + offsets[letter] + accidental


def fade_in(sig: np.ndarray, seconds: float = 0.004) -> np.ndarray:
    n = min(int(seconds * SR), max(1, len(sig) // 4))
    if n > 1:
        sig = sig.copy()
        sig[:n] *= np.linspace(0.0, 1.0, n)
    return sig


def bandlimited_saw(freq: float, n: int, nharm: int = 12) -> np.ndarray:
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    k = 1
    while k <= nharm and freq * k < SR * 0.45:
        sig += -np.sin(2.0 * math.pi * freq * k * t) / k
        k += 1
    return sig


def bandlimited_square(freq: float, n: int, nharm: int = 8) -> np.ndarray:
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    k = 1
    while k <= nharm and freq * k < SR * 0.45:
        sig += np.sin(2.0 * math.pi * freq * k * t) / k
        k += 2
    return sig


def epiano(freq: float, dur: float) -> np.ndarray:
    """DX-like electric piano: decaying modulator, soft chorus."""
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    mod_env = np.exp(-t * 7.5)
    mod = np.sin(2.0 * math.pi * freq * t) * mod_env * 1.8
    mod += np.sin(2.0 * math.pi * freq * 5.0 * t) * np.exp(-t * 16.0) * 0.45
    env = np.exp(-t * 2.6) * (1.0 - np.exp(-t * 60.0))
    sig = np.sin(2.0 * math.pi * freq * t + mod)
    # Gentle second layer, slightly sharp, for width in mono.
    sig += 0.28 * np.sin(2.0 * math.pi * freq * 1.004 * t + mod * 0.6)
    return fade_in(sig * env * 0.7, 0.003)


def piano(freq: float, dur: float) -> np.ndarray:
    """Additive piano with a short hammer transient. Original, not a sample."""
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    amps = (1.0, 0.52, 0.28, 0.15, 0.08, 0.045, 0.025)
    for k, amp in enumerate(amps, start=1):
        fk = freq * k * math.sqrt(1.0 + 0.00012 * k * k)
        if fk >= SR * 0.45:
            break
        decay = np.exp(-t * (0.7 + 0.48 * k))
        sig += amp * np.sin(2.0 * math.pi * fk * t) * decay
    attack = 1.0 - np.exp(-t * 220.0)
    hammer_n = min(n, int(0.012 * SR))
    rng = np.random.default_rng(int(freq * 10) % (2**31 - 1) or 1)
    hammer = rng.uniform(-1.0, 1.0, hammer_n) * np.linspace(1.0, 0.0, hammer_n)
    sig[:hammer_n] += hammer * 0.22
    return sig * attack


def lead(freq: float, dur: float, vibrato: float = 5.2) -> np.ndarray:
    """Soft lyrical tone used for the Cantopop melody."""
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    vib = vibrato * freq * 0.004 * np.sin(2.0 * math.pi * 5.2 * t)
    # Vibrato eases in.
    vib *= np.clip(t / 0.25, 0.0, 1.0)
    phase = 2.0 * math.pi * np.cumsum(freq + vib) / SR
    env = (1.0 - np.exp(-t * 18.0)) * np.ones(n)
    rel = min(n // 3, int(0.09 * SR))
    if rel > 2:
        env[-rel:] *= np.linspace(1.0, 0.0, rel)
    sig = np.sin(phase) + 0.28 * np.sin(2.0 * phase) + 0.08 * np.sin(3.0 * phase)
    return sig * env * 0.8


def pop_pluck(freq: float, dur: float) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    sig = (
        np.sin(2.0 * math.pi * freq * t)
        + 0.38 * np.sin(2.0 * math.pi * freq * 2.0 * t)
        + 0.12 * np.sin(2.0 * math.pi * freq * 3.0 * t)
    )
    env = np.exp(-t * 5.5) * (1.0 - np.exp(-t * 90.0))
    return sig * env


def synth_pluck(freq: float, dur: float) -> np.ndarray:
    """Bright, short K-pop hook voice."""
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    sig = bandlimited_saw(freq, n, 7)
    sig += 0.55 * bandlimited_saw(freq * 1.007, n, 6)
    env = np.exp(-t * 8.5) * (1.0 - np.exp(-t * 180.0))
    return np.tanh(sig * 0.55) * env


def supersaw_stab(freq: float, dur: float) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for detune in (-0.012, -0.005, 0.0, 0.006, 0.013):
        sig += bandlimited_saw(freq * (1.0 + detune), n, 6)
    env = np.exp(-t * 8.0) * (1.0 - np.exp(-t * 120.0))
    return np.tanh(sig * 0.22) * env


def flute(freq: float, dur: float, rng: np.random.Generator) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    vib = 1.0 + 0.0035 * np.sin(2.0 * math.pi * 4.8 * t) * np.clip(t / 0.3, 0.0, 1.0)
    phase = 2.0 * math.pi * np.cumsum(freq * vib) / SR
    breath = rng.uniform(-1.0, 1.0, n)
    breath = np.convolve(breath, np.ones(48) / 48.0, mode="same")
    env = 1.0 - np.exp(-t * 7.0)
    rel = min(n // 3, int(0.14 * SR))
    if rel > 2:
        env[-rel:] *= np.linspace(1.0, 0.0, rel)
    sig = np.sin(phase) + 0.18 * np.sin(2.0 * phase) + breath * 0.05
    return sig * env * 0.75


def bass_tone(freq: float, dur: float, grit: float = 0.15) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    # Fundamental plus octave so phone speakers still catch the line.
    sig = np.sin(2.0 * math.pi * freq * t) + 0.55 * np.sin(2.0 * math.pi * freq * 2.0 * t)
    sig += 0.18 * bandlimited_square(freq * 2.0, n, 4)
    if grit > 0:
        sig = np.tanh(sig * (1.0 + grit * 2.4))
    env = np.exp(-t * 3.2) * (1.0 - np.exp(-t * 70.0))
    return sig * env


def sub_pulse(freq: float, dur: float) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    env = np.exp(-t * 2.4) * (1.0 - np.exp(-t * 80.0))
    sig = np.sin(2.0 * math.pi * freq * t)
    sig += 0.7 * np.sin(2.0 * math.pi * freq * 2.0 * t)
    return sig * env


def pluck(
    freq: float,
    dur: float,
    loss: float,
    rng: np.random.Generator,
    brightness: float = 0.5,
) -> np.ndarray:
    """Karplus–Strong string. `loss` is applied once per cycle (close to 1.0)."""
    n = max(8, int(dur * SR))
    period = int(round(SR / max(freq, 40.0) - 0.5))
    period = max(2, min(period, n // 2))
    noise = rng.uniform(-1.0, 1.0, period)
    # Lower brightness, longer kernel: a duller, more wooden attack.
    kernel_n = 3 if brightness >= 0.75 else (7 if brightness >= 0.45 else 15)
    noise = np.convolve(noise, np.ones(kernel_n) / kernel_n, mode="same")
    buf = noise.astype(np.float64)
    out = np.empty(n, dtype=np.float64)
    idx = 0
    prev = 0.0
    for i in range(n):
        sample = buf[idx]
        out[i] = sample
        prev = loss * 0.5 * (sample + prev)
        buf[idx] = prev
        idx += 1
        if idx >= period:
            idx = 0
    return fade_in(out, 0.002)


def power_chord(root_midi: int, dur: float, palm: bool) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for iv, gain in ((0, 1.0), (7, 0.85), (12, 0.7)):
        freq = hz(root_midi + iv)
        sig += gain * bandlimited_saw(freq, n, 10)
        sig += gain * 0.35 * bandlimited_saw(freq * 1.004, n, 8)
    decay = 9.0 if palm else 1.7
    env = np.exp(-t * decay) * (1.0 - np.exp(-t * 140.0))
    # A touch of pick click.
    click_n = min(n, int(0.004 * SR))
    env[:click_n] *= np.linspace(0.3, 1.0, click_n)
    # Moderate drive, then a little of the unclipped tone so the chord stays readable.
    distorted = np.tanh(sig * 0.28)
    return (distorted * 0.82 + np.tanh(sig * 0.12) * 0.18) * env


def kick(dur: float, start_f: float, end_f: float, click: float, rng: np.random.Generator) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    freq = end_f + (start_f - end_f) * np.exp(-t * 26.0)
    phase = 2.0 * math.pi * np.cumsum(freq) / SR
    amp = np.exp(-t * (10.0 if dur > 0.2 else 16.0))
    noise = rng.standard_normal(n) * np.exp(-t * 160.0) * click
    return (np.sin(phase) * amp + noise) * 0.95


def snare(rng: np.random.Generator) -> np.ndarray:
    dur = 0.2
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0.0)
    body = np.sin(2.0 * math.pi * 188.0 * t) * np.exp(-t * 28.0)
    env = np.exp(-t * 18.0)
    return (0.85 * noise + 0.55 * body) * env


def hat(open_hat: bool, rng: np.random.Generator) -> np.ndarray:
    dur = 0.16 if open_hat else 0.045
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n), prepend=0.0)
    metal = np.zeros(n)
    for f in (3100.0, 4700.0, 6400.0, 8900.0):
        metal += np.sin(2.0 * math.pi * f * t)
    metal /= 4.0
    env = np.exp(-t * (16.0 if open_hat else 60.0))
    return (0.55 * noise + 0.4 * metal) * env * 0.55


def clap(rng: np.random.Generator) -> np.ndarray:
    n = int(0.18 * SR)
    noise = rng.standard_normal(n)
    env = np.zeros(n)
    for delay, gain in ((0.0, 1.0), (0.011, 0.75), (0.022, 0.45)):
        d = int(delay * SR)
        length = n - d
        tt = np.arange(length) / SR
        env[d:] += gain * np.exp(-tt * 36.0)
    return noise * env * 0.55


def shaker(rng: np.random.Generator) -> np.ndarray:
    n = int(0.045 * SR)
    noise = np.diff(rng.standard_normal(n), prepend=0.0)
    env = np.sin(np.linspace(0.0, math.pi, n)) ** 2
    return noise * env * 0.7


def crash(rng: np.random.Generator) -> np.ndarray:
    dur = 1.15
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = np.diff(np.diff(noise, prepend=0.0), prepend=0.0)
    metal = np.zeros(n)
    for i, f in enumerate((280.0, 430.0, 690.0, 1180.0, 1760.0, 2480.0)):
        metal += np.sin(2.0 * math.pi * f * t) * np.exp(-t * (1.8 + i * 0.35))
    env = np.exp(-t * 2.6)
    return (noise * 0.35 + metal * 0.12) * env


class Track:
    def __init__(self, duration: float, seed: int):
        self.n = int(duration * SR)
        self.buf = np.zeros(self.n, dtype=np.float64)
        self.rng = np.random.default_rng(seed)

    def add(self, sig: np.ndarray, start: float, gain: float = 1.0) -> None:
        if gain == 0.0 or len(sig) == 0:
            return
        i = int(start * SR)
        if i >= self.n or i < -len(sig):
            return
        if i < 0:
            sig = sig[-i:]
            i = 0
        end = min(self.n, i + len(sig))
        self.buf[i:end] += sig[: end - i] * gain

    def render(self) -> np.ndarray:
        return self.buf.copy()


def smooth(x: np.ndarray, k: int) -> np.ndarray:
    """Short moving average. Used as a gentle speaker/body filter."""
    if k <= 1:
        return x
    kernel = np.ones(k, dtype=np.float64) / k
    return np.convolve(x, kernel, mode="same")


def reverb(x: np.ndarray, taps: list[tuple[float, float]]) -> np.ndarray:
    y = x.copy()
    for ms, gain in taps:
        d = int(SR * ms / 1000.0)
        if d <= 0 or d >= len(y):
            continue
        delayed = np.zeros_like(y)
        delayed[d:] = x[:-d]
        # Darken the tail a little with a short moving average.
        if d > 40:
            delayed = np.convolve(delayed, np.ones(9) / 9.0, mode="same")
        y += delayed * gain
    return y


def mix_peaks(parts: list[tuple[np.ndarray, float]]) -> np.ndarray:
    n = max(len(buf) for buf, _ in parts)
    out = np.zeros(n, dtype=np.float64)
    for buf, target in parts:
        peak = float(np.max(np.abs(buf))) if len(buf) else 0.0
        if peak < 1e-8 or target <= 0:
            continue
        scaled = buf * (target / peak)
        if len(scaled) < n:
            padded = np.zeros(n, dtype=np.float64)
            padded[: len(scaled)] = scaled
            scaled = padded
        out += scaled
    return out


def finalize(x: np.ndarray) -> np.ndarray:
    if not np.isfinite(x).all():
        raise RuntimeError("Audio mix contains NaN or infinity")
    x = x - float(np.mean(x))
    peak = float(np.max(np.abs(x)))
    if peak < 1e-6:
        raise RuntimeError("Audio mix is silent")
    x = x / peak * 0.89
    fade_in_n = int(0.012 * SR)
    fade_out_n = int(0.22 * SR)
    x[:fade_in_n] *= np.linspace(0.0, 1.0, fade_in_n)
    x[-fade_out_n:] *= np.linspace(1.0, 0.0, fade_out_n)
    return x


class Clock:
    def __init__(self, bpm: float):
        self.bpm = bpm
        self.sec = 60.0 / bpm

    def t(self, beats: float) -> float:
        return beats * self.sec


def add_kit(track: Track, clock: Clock, bars: int, style: str) -> None:
    """style: 'soft' | 'electronic' | 'rock'."""
    total_beats = bars * 4
    step = 0.5  # eighths
    beat = 0.0
    while beat < total_beats - 1e-6:
        when = clock.t(beat)
        on_quarter = abs(beat - round(beat)) < 1e-6
        backbeat = abs((beat % 4) - 1) < 1e-6 or abs((beat % 4) - 3) < 1e-6
        down = abs((beat % 4) - 0) < 1e-6 or abs((beat % 4) - 2) < 1e-6
        if style == "soft":
            if down and on_quarter:
                track.add(kick(0.16, 120, 52, 0.08, track.rng), when, 0.7)
            if backbeat and on_quarter:
                track.add(snare(track.rng), when, 0.38)
            track.add(hat(False, track.rng), when, 0.18)
            if abs((beat % 4) - 3.5) < 1e-6:
                track.add(hat(True, track.rng), when, 0.22)
        elif style == "electronic":
            if on_quarter:
                track.add(kick(0.12, 210, 78, 0.28, track.rng), when, 0.95)
            if backbeat and on_quarter:
                track.add(clap(track.rng), when, 0.72)
            track.add(hat(False, track.rng), when, 0.28)
            if abs((beat % 4) - 3.5) < 1e-6:
                track.add(hat(True, track.rng), when, 0.34)
        elif style == "rock":
            if down and on_quarter:
                track.add(kick(0.26, 130, 44, 0.12, track.rng), when, 0.9)
            # Extra kick push on the "and" of 3 in each bar.
            if abs((beat % 4) - 2.5) < 1e-6:
                track.add(kick(0.18, 120, 48, 0.08, track.rng), when, 0.45)
            if backbeat and on_quarter:
                track.add(snare(track.rng), when, 0.8)
            track.add(hat(False, track.rng), when, 0.22)
        beat += step


def make_cantopop() -> np.ndarray:
    """Mid-tempo electric-piano groove and a lyrical line. 3 bars, 92 BPM."""
    bpm = 92.0
    clock = Clock(bpm)
    bars = 3
    track_h = Track(clock.t(bars * 4) + 0.45, seed=1101)
    track_m = Track(track_h.n / SR, seed=1102)
    track_b = Track(track_h.n / SR, seed=1103)
    track_d = Track(track_h.n / SR, seed=1104)

    chords = [
        (0, ["E3", "G3", "B3", "C4"]),   # Cmaj7
        (4, ["A2", "C3", "E3", "G3"]),   # Am7
        (8, ["F3", "A3", "C4", "E4"]),   # Fmaj7
    ]
    for beat, names in chords:
        for name in names:
            track_h.add(epiano(hz(note(name)), 1.35), clock.t(beat), 0.55)
            track_h.add(epiano(hz(note(name)), 0.42), clock.t(beat + 2), 0.28)

    melody = [
        (0.0, 1.0, "E4"),
        (1.0, 1.0, "G4"),
        (2.0, 0.5, "A4"),
        (2.5, 0.5, "G4"),
        (3.0, 1.0, "E4"),
        (4.0, 1.4, "A4"),
        (5.5, 0.5, "G4"),
        (6.0, 1.0, "E4"),
        (7.0, 1.0, "D4"),
        (8.0, 1.0, "C5"),
        (9.0, 1.0, "A4"),
        (10.0, 1.0, "G4"),
        (11.0, 1.15, "E4"),
    ]
    for beat, length, name in melody:
        track_m.add(lead(hz(note(name)), clock.t(length) + 0.05), clock.t(beat), 0.9)

    bass_notes = [(0, "C2"), (2, "G2"), (4, "A1"), (6, "E2"), (8, "F2"), (10, "C2")]
    for beat, name in bass_notes:
        track_b.add(bass_tone(hz(note(name)), 0.55, grit=0.05), clock.t(beat), 0.8)

    add_kit(track_d, clock, bars, "soft")
    mixed = mix_peaks(
        [
            (track_h.render(), 0.62),
            (track_m.render(), 0.58),
            (track_b.render(), 0.42),
            (track_d.render(), 0.32),
        ]
    )
    return reverb(mixed, [(55, 0.14), (105, 0.09), (170, 0.05)])


def make_kpop() -> np.ndarray:
    """Four-on-the-floor, claps, supersaw stabs, and a short synth hook."""
    bpm = 120.0
    clock = Clock(bpm)
    bars = 4
    length = clock.t(bars * 4) + 0.35
    harmony = Track(length, seed=2201)
    melody = Track(length, seed=2202)
    bass = Track(length, seed=2203)
    drums = Track(length, seed=2204)

    progression = [
        (0, ["A3", "C4", "E4"]),
        (4, ["F3", "A3", "C4"]),
        (8, ["C4", "E4", "G4"]),
        (12, ["G3", "B3", "D4"]),
    ]
    for bar_beat, names in progression:
        for eighth in (0.5, 1.5, 2.5, 3.5):
            for name in names:
                harmony.add(
                    supersaw_stab(hz(note(name)), 0.18),
                    clock.t(bar_beat + eighth),
                    0.34,
                )

    # Original syncopated hook in A minor. Repeated, then a small lift.
    hook = [
        (0.00, 0.18, "A4"),
        (0.50, 0.16, "E5"),
        (0.75, 0.18, "E5"),
        (1.25, 0.18, "D5"),
        (1.75, 0.28, "C5"),
        (2.25, 0.16, "E5"),
        (2.50, 0.30, "C5"),
        (3.25, 0.16, "D5"),
        (3.50, 0.36, "C5"),
    ]
    for bar in range(4):
        lift = 2 if bar == 2 else 0
        for beat, dur, name in hook:
            midi_note = note(name) + lift
            if bar == 3 and beat > 3.2:
                midi_note = note("A4")
            melody.add(synth_pluck(hz(midi_note), clock.t(dur) + 0.02), clock.t(bar * 4 + beat), 0.85)

    roots = [(0, "A1"), (4, "F1"), (8, "C2"), (12, "G1")]
    for bar_beat, name in roots:
        for step in range(4):
            bass.add(sub_pulse(hz(note(name)), 0.22), clock.t(bar_beat + step), 0.8)

    add_kit(drums, clock, bars, "electronic")

    mixed = mix_peaks(
        [
            (harmony.render(), 0.36),
            (melody.render(), 0.64),
            (bass.render(), 0.46),
            (drums.render(), 0.78),
        ]
    )
    # Sidechain the whole mix lightly against the kick grid so it pumps.
    t = np.arange(len(mixed)) / SR
    beat = 60.0 / bpm
    phase = np.mod(t, beat) / beat
    env = 1.0 - 0.28 * np.exp(-phase * 7.5)
    mixed = mixed * env
    return reverb(mixed, [(35, 0.06), (78, 0.035)])


def make_folk() -> np.ndarray:
    """Fingerpicked acoustic guitar in G, with a quiet flute. No drum kit."""
    bpm = 84.0
    clock = Clock(bpm)
    bars = 3
    length = clock.t(bars * 4) + 0.55
    guitar = Track(length, seed=3301)
    melody = Track(length, seed=3302)

    patterns = [
        # G
        ["G2", "B3", "D3", "G4", "B2", "D4", "D3", "B3"],
        # C
        ["C3", "E4", "G3", "C4", "E3", "G4", "G3", "E4"],
        # G, a little higher at the end
        ["G2", "B3", "D3", "G4", "B2", "D4", "G3", "D4"],
    ]
    for bar, pattern in enumerate(patterns):
        for i, name in enumerate(pattern):
            when = clock.t(bar * 4 + i * 0.5)
            guitar.add(
                pluck(hz(note(name)), 1.15, 0.996, guitar.rng, brightness=0.22),
                when,
                0.85,
            )

    flute_line = [
        (0.15, 1.9, "D5"),
        (2.15, 1.7, "B4"),
        (4.1, 1.9, "E5"),
        (6.15, 1.7, "C5"),
        (8.1, 1.8, "D5"),
        (10.05, 1.7, "B4"),
    ]
    for beat, dur, name in flute_line:
        melody.add(flute(hz(note(name)), clock.t(dur), melody.rng), clock.t(beat), 0.7)

    mixed = mix_peaks(
        [
            (smooth(guitar.render(), 13), 0.8),
            (melody.render(), 0.34),
        ]
    )
    return reverb(mixed, [(80, 0.16), (150, 0.09), (240, 0.05)])


def make_ballad() -> np.ndarray:
    """Slow solo piano. No percussion. Space is the point."""
    length = 8.7
    piano_bus = Track(length, seed=4401)
    # Rolled Cmaj7, then Am7, with a simple original right-hand line.
    left = [
        (0.06, "C3", 3.4),
        (0.16, "E3", 3.3),
        (0.26, "G3", 3.2),
        (0.36, "B3", 3.1),
        (0.52, "E4", 2.8),
        (4.15, "A2", 3.8),
        (4.26, "C3", 3.6),
        (4.37, "E3", 3.5),
        (4.48, "G3", 3.4),
        (4.64, "C4", 3.2),
    ]
    right = [
        (0.55, "G4", 1.35),
        (2.05, "A4", 1.05),
        (3.25, "G4", 0.85),
        (4.45, "E5", 1.55),
        (6.15, "D5", 0.95),
        (7.15, "C5", 1.35),
    ]
    for start, name, dur in left:
        piano_bus.add(piano(hz(note(name)), dur), start, 0.55)
    for start, name, dur in right:
        piano_bus.add(piano(hz(note(name)), dur), start, 0.72)
    mixed = mix_peaks([(piano_bus.render(), 0.9)])
    return reverb(mixed, [(70, 0.28), (130, 0.2), (210, 0.14), (340, 0.09), (490, 0.05)])


def make_lightpop() -> np.ndarray:
    """Bouncy ukulele strums, shaker, and a bright major melody."""
    bpm = 126.0
    clock = Clock(bpm)
    bars = 4
    extra = 2  # a short cadence
    length = clock.t(bars * 4 + extra) + 0.4
    uke = Track(length, seed=5501)
    melody = Track(length, seed=5502)
    perc = Track(length, seed=5503)

    chords = {
        0: ["D4", "F#4", "A4"],
        4: ["G4", "B4", "D5"],
        8: ["D4", "F#4", "A4"],
        12: ["A3", "E4", "A4"],
        16: ["D4", "F#4", "A4"],
    }
    total_beats = bars * 4 + extra
    beat = 0.0
    while beat < total_beats - 1e-6:
        bar_start = int(beat // 4) * 4
        if bar_start not in chords:
            bar_start = 16 if beat >= 16 else bar_start
        names = chords.get(bar_start, chords[0])
        accent = 1.0 if abs(beat - round(beat)) < 1e-6 else 0.62
        for j, name in enumerate(names):
            uke.add(
                pluck(hz(note(name)), 0.42, 0.990, uke.rng, brightness=0.92),
                clock.t(beat) + j * 0.012,
                0.7 * accent,
            )
        perc.add(shaker(perc.rng), clock.t(beat), 0.45 if accent == 1.0 else 0.28)
        if abs((beat % 4) - 1) < 1e-6 or abs((beat % 4) - 3) < 1e-6:
            if abs(beat - round(beat)) < 1e-6:
                perc.add(clap(perc.rng), clock.t(beat), 0.32)
        beat += 0.5

    # Original cheerful phrase in D major. Staccato.
    phrase = [
        (0.0, 0.35, "F#5"),
        (1.0, 0.35, "A5"),
        (1.5, 0.28, "A5"),
        (2.0, 0.55, "D5"),
        (3.0, 0.4, "E5"),
        (4.0, 0.35, "G5"),
        (5.0, 0.35, "E5"),
        (6.0, 0.3, "D5"),
        (6.5, 0.3, "E5"),
        (7.0, 0.45, "D5"),
        (8.0, 0.35, "F#5"),
        (9.0, 0.35, "A5"),
        (10.0, 0.5, "D6"),
        (11.0, 0.4, "A5"),
        (12.0, 0.35, "E5"),
        (13.0, 0.35, "F#5"),
        (14.0, 0.4, "A5"),
        (15.0, 0.45, "G5"),
        (16.0, 0.4, "F#5"),
        (17.0, 0.7, "D5"),
    ]
    for b, dur, name in phrase:
        melody.add(pop_pluck(hz(note(name)), clock.t(dur) + 0.05), clock.t(b), 0.85)

    mixed = mix_peaks(
        [
            (uke.render(), 0.62),
            (melody.render(), 0.58),
            (perc.render(), 0.32),
        ]
    )
    return reverb(mixed, [(45, 0.08), (95, 0.045)])


def make_rock() -> np.ndarray:
    """Family-friendly bright rock: power chords, kit, and bass. Not metal."""
    bpm = 146.0
    clock = Clock(bpm)
    bars = 5
    length = clock.t(bars * 4) + 0.4
    guitars = Track(length, seed=6601)
    bass = Track(length, seed=6602)
    drums = Track(length, seed=6603)

    def chug(root: str, start_beat: float, eighths: int, palm: bool, gain: float = 1.0) -> None:
        midi_note = note(root)
        step = 0.5
        for i in range(eighths):
            dur_beats = 0.42 if palm else 0.85
            sig = power_chord(midi_note, clock.t(dur_beats), palm=palm)
            sig = sig + 0.62 * power_chord(midi_note + 12, clock.t(dur_beats), palm=palm)
            guitars.add(sig, clock.t(start_beat + i * step), gain)

    # Bar 1: palm-muted E. Bar 2: open E. Bar 3: A. Bar 4: G then A. Bar 5: E.
    chug("E2", 0, 8, palm=True, gain=0.85)
    chug("E2", 4, 4, palm=False, gain=1.0)
    chug("A2", 8, 8, palm=True, gain=0.9)
    chug("G2", 12, 4, palm=False, gain=1.0)
    chug("A2", 14, 4, palm=False, gain=1.0)
    chug("E2", 16, 4, palm=False, gain=1.05)

    bass_map = (
        [(b, "E2") for b in (0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5)]
        + [(b, "A2") for b in np.arange(8, 12, 0.5)]
        + [(b, "G2") for b in np.arange(12, 14, 0.5)]
        + [(b, "A2") for b in np.arange(14, 16, 0.5)]
        + [(b, "E2") for b in np.arange(16, 20, 0.5)]
    )
    for beat, name in bass_map:
        bass.add(bass_tone(hz(note(name)), 0.18, grit=0.35), clock.t(float(beat)), 0.75)

    add_kit(drums, clock, bars, "rock")
    drums.add(crash(drums.rng), 0.0, 0.55)
    drums.add(crash(drums.rng), clock.t(16), 0.4)
    # Short snare fill into the last bar.
    for beat, gain in ((18.0, 0.4), (18.5, 0.5), (19.0, 0.65), (19.5, 0.8)):
        drums.add(snare(drums.rng), clock.t(beat), gain)

    mixed = mix_peaks(
        [
            (smooth(guitars.render(), 7), 0.7),
            (bass.render(), 0.46),
            (drums.render(), 0.64),
        ]
    )
    return reverb(mixed, [(28, 0.10), (62, 0.06), (110, 0.03)])


def estimate_pitch(x: np.ndarray, fmin: float = 80.0, fmax: float = 1400.0) -> float:
    if len(x) < SR // 10:
        return 0.0
    window = x[: int(0.45 * SR)]
    window = window * np.hanning(len(window))
    corr = np.correlate(window, window, mode="full")
    corr = corr[len(corr) // 2 :]
    min_lag = max(1, int(SR / fmax))
    max_lag = min(len(corr) - 1, int(SR / fmin))
    if max_lag <= min_lag:
        return 0.0
    lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
    return float(SR / lag)


def check_oscillators() -> None:
    rng = np.random.default_rng(1)
    target = 440.0
    probes = {
        "epiano": epiano(target, 0.8),
        "piano": piano(target, 0.8),
        "lead": lead(target, 0.8),
        "pluck": pluck(target, 0.8, 0.996, rng),
        "bass": bass_tone(target / 2.0, 0.6),
    }
    for name, sig in probes.items():
        expected = target / 2.0 if name == "bass" else target
        # Bass includes a strong octave; accept either the fundamental or the octave.
        got = estimate_pitch(sig, fmin=60.0, fmax=1000.0)
        if got <= 0:
            raise RuntimeError(f"{name} pitch estimate failed")
        ratio = got / expected
        octave_ok = abs(got / (expected * 2.0) - 1.0) < PITCH_TOLERANCE
        if abs(ratio - 1.0) > PITCH_TOLERANCE and not octave_ok:
            raise RuntimeError(f"{name} is out of tune: expected {expected:.1f} Hz, got {got:.1f} Hz")
        print(f"  pitch {name:8s} {got:7.1f} Hz (target {expected:.0f})")


def write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = np.clip(audio, -1.0, 1.0)
    ints = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(ints.tobytes())


def encode_mp3(wav_path: Path, mp3_path: Path, title: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "96k",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-metadata",
        f"title={title}",
        "-metadata",
        "artist=我手寫我歌",
        "-metadata",
        "album=香港布廠商會朱石麟中學 開放日",
        "-metadata",
        "comment=Original synthesized school-use preview. Not a commercial recording.",
        str(mp3_path),
    ]
    subprocess.run(cmd, check=True)


def probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


def contour(audio: np.ndarray, parts: int = 8) -> list[float]:
    chunks = np.array_split(audio, parts)
    return [round(float(np.sqrt(np.mean(chunk**2))), 3) for chunk in chunks]


def centroid(audio: np.ndarray) -> float:
    window = audio * np.hanning(len(audio))
    spec = np.abs(np.fft.rfft(window))
    freqs = np.fft.rfftfreq(len(audio), 1.0 / SR)
    return float(np.sum(freqs * spec) / (np.sum(spec) + 1e-12))


def main() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print("Checking oscillator tuning...")
    check_oscillators()

    songs = [
        ("cantopop", "粵語流行 工作坊示範", make_cantopop),
        ("kpop", "K-Pop 工作坊示範", make_kpop),
        ("folk", "民謠 工作坊示範", make_folk),
        ("ballad", "抒情 工作坊示範", make_ballad),
        ("lightpop", "輕快流行 工作坊示範", make_lightpop),
        ("rock", "搖滾 工作坊示範", make_rock),
    ]

    print("Rendering original previews...")
    fingerprints: dict[str, bytes] = {}
    for file_id, title, builder in songs:
        audio = finalize(builder())
        wav_path = AUDIO_DIR / f"{file_id}.wav"
        mp3_path = AUDIO_DIR / f"{file_id}.mp3"
        write_wav(wav_path, audio)
        encode_mp3(wav_path, mp3_path, title)
        duration = probe_duration(mp3_path)
        if duration >= 9.9:
            raise RuntimeError(f"{file_id} is {duration:.2f}s, which is not under 10 seconds")
        digest = wav_path.read_bytes()
        fingerprints[file_id] = digest
        wav_path.unlink()
        rms = float(np.sqrt(np.mean(audio**2)))
        print(
            f"  {file_id:9s} {duration:4.2f}s  rms {rms:.3f}  "
            f"centroid {centroid(audio):6.0f} Hz  contour {contour(audio)}"
        )

    unique = {hash(blob) for blob in fingerprints.values()}
    if len(unique) != len(fingerprints):
        raise RuntimeError("Two previews rendered to the same audio")
    print(f"Wrote {len(songs)} original previews to {AUDIO_DIR}")


if __name__ == "__main__":
    main()
