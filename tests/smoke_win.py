"""Headless smoke test for the Windows dictation stack.
Run from repo root:  .venv-win\\Scripts\\python tests\\smoke_win.py path\\to\\jfk.wav

Covers: DLL registration, CUDA engine load, real transcription, the
punctuation lexicon, and SendInput struct layout — everything except
actually injecting keystrokes into the desktop.
"""

import ctypes
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.win32_input import configure_cuda_dll_search_paths  # noqa: E402

registered = configure_cuda_dll_search_paths()
print(f"[1] DLL dirs registered: {len(registered)}")
for r in registered:
    print("     ", r)

from src import win32_input  # noqa: E402

if win32_input.IS_WINDOWS:
    size = ctypes.sizeof(win32_input.INPUT)
    assert size == 40, f"INPUT struct is {size} bytes, expected 40 on x64"
    print(f"[2] INPUT struct layout OK ({size} bytes)")
else:
    print("[2] skipped (not Windows)")

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
cfg = tomllib.load((ROOT / "config" / "settings.toml").open("rb"))
print(f"[3] config OK: model={cfg['whisper']['model_size']} "
      f"hotkey={cfg['hotkeys']['trigger_key']}")

from src.engine import WhisperTranscriber  # noqa: E402

eng = WhisperTranscriber(cfg)

cases = [
    ("hello world period this is a test comma right question mark",
     "Hello world. This is a test, right?"),
    ("first line new line second line", "First line\nSecond line"),
    ("okay period", "Okay"),
]
for raw, want in cases:
    got = eng.post_process(raw)
    assert got == want, f"post_process({raw!r}) = {got!r}, wanted {want!r}"
print(f"[4] punctuation lexicon OK ({len(cases)} cases)")

wav_path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "tests" / "jfk.wav")
with wave.open(wav_path, "rb") as w:
    assert w.getframerate() == 16000 and w.getnchannels() == 1
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = audio.astype(np.float32) / 32768.0

print("[5] loading model (first run downloads ~1.6 GB)…")
eng.load()
print(f"    loaded on: {eng.active_device}")

assert eng.has_speech(audio), "VAD says the JFK clip has no speech"
print("[6] VAD speech detection OK")

import time  # noqa: E402
t0 = time.time()
text = eng.transcribe_audio_buffer(audio)
dt = time.time() - t0
print(f"[7] transcribed {len(audio)/16000:.1f}s in {dt:.1f}s: {text!r}")
assert "ask not what your country can do for you" in text.lower()

print("\nALL CHECKS PASSED on device:", eng.active_device)
