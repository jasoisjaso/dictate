"""Real-time audio analysis: RMS, bass/mid/treble bands, dominant pitch.

Uses a single FFT on a short buffer (the most recent ~50ms of audio).
Designed to run at 30fps without blocking — np.fft.rfft on 800 samples
takes <0.1ms on any modern CPU.
"""
from __future__ import annotations

import numpy as np


def analyze(audio: np.ndarray, sr: int = 16000) -> tuple:
    """Analyze a float32 mono audio buffer.

    Returns (bass, mid, treble, pitch_hz, rms) — all floats 0.0..1.0
    (bands and rms normalized by internal scaling; pitch in Hz or 0).

    bass:    80-250 Hz energy (voice fundamental, male chest)
    mid:     250-2000 Hz energy (vowels, main speech body)
    treble:  2000-8000 Hz energy (consonants, sibilance)
    pitch:   dominant frequency in Hz (0 if silent)
    rms:     root-mean-square amplitude
    """
    if audio is None or audio.size < 256:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-5:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    n = audio.size
    # Apply a simple Hann window to reduce spectral leakage
    window = np.hanning(n)
    fft = np.fft.rfft(audio * window)
    mag = np.abs(fft) / n
    freq = np.fft.rfftfreq(n, d=1.0 / sr)

    # Band energies (sum of magnitudes in band, normalized)
    bass_mask = (freq >= 80) & (freq <= 250)
    mid_mask = (freq > 250) & (freq <= 2000)
    treble_mask = (freq > 2000) & (freq <= 8000)

    bass = float(np.sum(mag[bass_mask])) if bass_mask.any() else 0.0
    mid = float(np.sum(mag[mid_mask])) if mid_mask.any() else 0.0
    treble = float(np.sum(mag[treble_mask])) if treble_mask.any() else 0.0

    # Normalize bands to roughly 0..1 based on expected speech energy
    bass = min(1.0, bass * 8.0)
    mid = min(1.0, mid * 3.0)
    treble = min(1.0, treble * 6.0)

    # Pitch: frequency of the peak FFT bin in the 80-500 Hz range
    # (human voice fundamental is typically 80-300 Hz)
    voice_mask = (freq >= 80) & (freq <= 500)
    if voice_mask.any():
        voice_mag = mag.copy()
        voice_mag[~voice_mask] = 0
        peak_idx = int(np.argmax(voice_mag))
        pitch = float(freq[peak_idx]) if voice_mag[peak_idx] > 1e-4 else 0.0
    else:
        pitch = 0.0

    # Normalize RMS to 0..1 (speech typically 0.01-0.15)
    rms_norm = min(1.0, rms * 10.0)

    return bass, mid, treble, pitch, rms_norm
