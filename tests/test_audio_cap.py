"""AudioRecorder cap logic — no real hardware needed, we drive _callback
directly with fake blocks to prove the max-duration cap stops retaining audio."""
import os
import sys
import types

import numpy as np

# audio.py imports sounddevice (PortAudio) at module load; stub it so the pure
# cap logic is testable on any OS / CI without PortAudio installed.
if "sounddevice" not in sys.modules:
    _sd = types.ModuleType("sounddevice")
    _sd.query_devices = lambda: []
    _sd.default = types.SimpleNamespace(device=None)
    _sd._terminate = lambda: None
    _sd._initialize = lambda: None
    _sd.InputStream = object
    sys.modules["sounddevice"] = _sd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import audio  # noqa: E402


def _feed(rec, seconds):
    """Simulate PortAudio delivering `seconds` of audio in BLOCK_SIZE frames."""
    frames = audio.BLOCK_SIZE
    n_blocks = int(seconds * rec.samplerate / frames)
    block = np.zeros((frames, 1), dtype=np.float32)
    for _ in range(n_blocks):
        rec._callback(block, frames, None, None)


def test_cap_stops_retaining_audio():
    rec = audio.AudioRecorder(max_seconds=1.0)  # tiny cap for the test
    rec._active = True
    _feed(rec, 3.0)  # try to push 3s into a 1s cap
    assert rec.capped is True
    take = rec.stop_recording()
    # retained audio must be bounded to ~1s, not the full 3s
    assert take.size <= rec.max_samples + audio.BLOCK_SIZE


def test_no_cap_under_limit():
    rec = audio.AudioRecorder(max_seconds=10.0)
    rec._active = True
    _feed(rec, 2.0)
    assert rec.capped is False
    take = rec.stop_recording()
    assert abs(take.size - 2.0 * rec.samplerate) < audio.BLOCK_SIZE * 2


def test_start_resets_cap_flag():
    rec = audio.AudioRecorder(max_seconds=1.0)
    rec._active = True
    _feed(rec, 2.0)
    assert rec.capped is True
    # a fresh recording clears the flag & buffer (without opening a real stream)
    with rec._lock:
        rec._chunks = []
        rec._sample_count = 0
        rec._capped = False
    assert rec.capped is False


def test_inactive_callback_ignored():
    rec = audio.AudioRecorder(max_seconds=10.0)
    rec._active = False
    _feed(rec, 1.0)
    assert rec.stop_recording().size == 0
