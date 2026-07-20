"""Tests for chunked streaming transcription + per-PC feature gating."""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import device
import streaming
from streaming import ChunkedTake, find_cut_sample

SR = 16000


# ---- find_cut_sample --------------------------------------------------------

def test_cut_lands_in_quiet_gap():
    # 20s: loud speech, 0.5s silence at 15s, loud again
    rng = np.random.default_rng(42)
    audio = (rng.standard_normal(20 * SR) * 0.3).astype(np.float32)
    gap_lo, gap_hi = int(15.0 * SR), int(15.5 * SR)
    audio[gap_lo:gap_hi] = 0.0
    cut = find_cut_sample(audio, SR)
    assert gap_lo <= cut <= gap_hi, f"cut at {cut/SR:.2f}s not in the gap"


def test_cut_never_in_keep_zone():
    rng = np.random.default_rng(1)
    audio = (rng.standard_normal(20 * SR) * 0.3).astype(np.float32)
    cut = find_cut_sample(audio, SR)
    assert cut <= audio.size - int(streaming.TAIL_KEEP_S * SR)


def test_cut_short_buffer_no_crash():
    audio = np.zeros(SR // 2, dtype=np.float32)  # 0.5s only
    cut = find_cut_sample(audio, SR)
    assert 0 < cut <= audio.size


# ---- ChunkedTake ------------------------------------------------------------

class FakeEngine:
    def __init__(self):
        self.calls = []

    def transcribe_audio_buffer(self, audio, prev_text=None):
        self.calls.append((audio.size, prev_text))
        return f"chunk{len(self.calls)}"


class FakeRecorder:
    def __init__(self, audio):
        self._audio = audio

    def snapshot(self):
        return self._audio


def test_finalize_without_commits_transcribes_everything():
    eng = FakeEngine()
    audio = np.zeros(3 * SR, dtype=np.float32)  # 3s — under MIN_CHUNK_S
    take = ChunkedTake(eng, FakeRecorder(audio))
    take.start()
    out = take.finalize(audio)
    assert out == "chunk1"
    assert eng.calls[0][0] == audio.size  # whole take, one call


def test_commit_then_finalize_joins_in_order():
    eng = FakeEngine()
    audio = (np.random.default_rng(7).standard_normal(30 * SR) * 0.3
             ).astype(np.float32)
    rec = FakeRecorder(audio)
    take = ChunkedTake(eng, rec)
    take.start()
    # worker polls every 1s; wait for the first commit
    deadline = time.time() + 5
    while not take._texts and time.time() < deadline:
        time.sleep(0.1)
    assert take._texts, "no chunk committed within 5s"
    committed = take._committed
    assert committed > 0
    out = take.finalize(audio)
    # committed chunk(s) + tail, in order
    assert out.startswith("chunk1")
    assert out.split()[-1] == f"chunk{len(eng.calls)}"
    # tail call got the previous text as context
    assert eng.calls[-1][1] is not None


def test_cancel_stops_committing():
    eng = FakeEngine()
    audio = np.zeros(30 * SR, dtype=np.float32)
    take = ChunkedTake(eng, FakeRecorder(audio))
    take.start()
    take.cancel()
    time.sleep(1.5)
    assert take._committed == 0 or take._texts == []  # no runaway commits


def test_empty_chunk_text_still_advances_committed():
    class SilentEngine(FakeEngine):
        def transcribe_audio_buffer(self, audio, prev_text=None):
            self.calls.append((audio.size, prev_text))
            return ""
    eng = SilentEngine()
    audio = np.zeros(30 * SR, dtype=np.float32)
    take = ChunkedTake(eng, FakeRecorder(audio))
    take.start()
    deadline = time.time() + 5
    while take._committed == 0 and time.time() < deadline:
        time.sleep(0.1)
    assert take._committed > 0, "silent chunk did not advance the commit mark"
    take.cancel()


# ---- hardware gating --------------------------------------------------------

def test_streaming_ok_gpu_always():
    assert device.streaming_ok(device.Tier("cuda", "float16", "large-v3-turbo"))
    assert device.streaming_ok(device.Tier("cuda", "int8_float16", "base"))


def test_streaming_ok_cpu_needs_cores_and_small_model(monkeypatch):
    monkeypatch.setattr(device, "_cpu_cores", lambda: 16)
    assert device.streaming_ok(device.Tier("cpu", "int8", "small"))
    assert not device.streaming_ok(device.Tier("cpu", "int8", "large-v3-turbo"))
    monkeypatch.setattr(device, "_cpu_cores", lambda: 4)
    assert not device.streaming_ok(device.Tier("cpu", "int8", "small"))


def test_preview_ok_gpu_only():
    assert device.preview_ok(device.Tier("cuda", "float16", "small"))
    assert not device.preview_ok(device.Tier("cpu", "int8", "small"))


def test_ollama_ok_false_when_unreachable():
    # nothing listens on this port
    assert device.ollama_ok("http://127.0.0.1:59999", timeout=0.3) is False


def test_ollama_pick_model_none_when_unreachable():
    assert device.ollama_pick_model("hermes4",
                                    "http://127.0.0.1:59999",
                                    timeout=0.3) is None


# ---- engine auto modes ------------------------------------------------------

def test_auto_punct_auto_on_small_off_large():
    from engine import WhisperTranscriber
    small = WhisperTranscriber({"whisper": {"model_size": "small",
                                            "device": "cpu",
                                            "compute_type": "int8"}})
    assert small.auto_punctuation is True
    big = WhisperTranscriber({"whisper": {"model_size": "large-v3-turbo",
                                          "device": "cuda",
                                          "compute_type": "float16"}})
    assert big.auto_punctuation is False


def test_auto_punct_explicit_overrides_auto():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"model_size": "large-v3-turbo",
                                        "device": "cuda",
                                        "compute_type": "float16"},
                            "post_processing": {"auto_punctuation": True}})
    assert t.auto_punctuation is True
    t2 = WhisperTranscriber({"whisper": {"model_size": "small",
                                         "device": "cpu",
                                         "compute_type": "int8"},
                             "post_processing": {"auto_punctuation": False}})
    assert t2.auto_punctuation is False


def test_ollama_polish_modes():
    from engine import WhisperTranscriber
    base = {"whisper": {"model_size": "small", "device": "cpu",
                        "compute_type": "int8"}}
    auto = WhisperTranscriber({**base, "cleanup": {"ollama_polish": "auto"}})
    assert auto.ollama_polish_mode == "auto" and auto.ollama_polish is False
    on = WhisperTranscriber({**base, "cleanup": {"ollama_polish": True}})
    assert on.ollama_polish is True
    off = WhisperTranscriber({**base, "cleanup": {"ollama_polish": False}})
    assert off.ollama_polish is False and off.ollama_polish_mode == "off"
