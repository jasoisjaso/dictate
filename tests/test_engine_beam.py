"""Tests for adaptive beam_size in WhisperTranscriber."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_short_take_gets_beam_1():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"beam_size": 5}})
    audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 seconds
    assert t._adaptive_beam_size(audio) == 1


def test_medium_take_gets_beam_3():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"beam_size": 5}})
    audio = np.zeros(16000 * 10, dtype=np.float32)  # 10 seconds
    assert t._adaptive_beam_size(audio) == 3


def test_long_take_gets_default():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"beam_size": 5}})
    audio = np.zeros(16000 * 30, dtype=np.float32)  # 30 seconds
    assert t._adaptive_beam_size(audio) == 5
