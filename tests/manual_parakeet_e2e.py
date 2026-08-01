"""Manual end-to-end check for the Parakeet engine on THIS machine.

Downloads the real model (~640 MB, once, into the same cache the app uses),
loads it via sherpa-onnx, transcribes tests/parakeet_e2e.wav and asserts the
key words came through. Deliberately NOT named test_* — pytest must never
pull a 640 MB download into CI. Run by hand after touching the engine:

    .venv-win/Scripts/python.exe tests/manual_parakeet_e2e.py

Regenerate the wav (Windows, 16 kHz mono SAPI):
    powershell -c "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono); $s.SetOutputToWaveFile('tests/parakeet_e2e.wav', $fmt); $s.Speak('The quick brown fox jumps over the lazy dog near the Brisbane warehouse.'); $s.Dispose()"
"""
import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import first_run
import paths
from engine_parakeet import ParakeetTranscriber

WAV = os.path.join(os.path.dirname(__file__), "parakeet_e2e.wav")


def main():
    cache = paths.models_dir()
    if not first_run.parakeet_is_cached(cache):
        print(f"downloading Parakeet model to {cache} ...")
        t0 = time.time()
        first_run.download_parakeet_with_progress(
            cache, lambda p: print(f"\r  {p}%", end="", flush=True))
        print(f"\ndownload done in {time.time() - t0:.0f}s")
    else:
        print("model already cached")

    with wave.open(WAV, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, \
            f"need 16 kHz mono, got {w.getframerate()} Hz {w.getnchannels()}ch"
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = pcm.astype(np.float32) / 32768.0
    dur = audio.size / 16000

    eng = ParakeetTranscriber({"whisper": {"language": "en"}})
    t0 = time.time()
    eng.load()
    print(f"load: {time.time() - t0:.1f}s")
    t0 = time.time()
    raw = eng.transcribe_audio_buffer(audio)
    dt = time.time() - t0
    text = eng.post_process(raw)
    print(f"audio {dur:.1f}s -> decode {dt:.2f}s "
          f"({dur / max(dt, 1e-6):.0f}x realtime)")
    print(f"raw:  {raw!r}")
    print(f"post: {text!r}")
    assert raw.strip(), "empty transcript"
    for word in ("quick", "fox", "Brisbane"):
        assert word.lower() in raw.lower(), f"missing {word!r} in {raw!r}"
    print("PARAKEET_E2E_OK")


if __name__ == "__main__":
    main()
