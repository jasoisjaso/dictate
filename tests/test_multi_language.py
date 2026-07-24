"""Mixed-language (English + Bosnian) dictation mode.

Whisper picks ONE output language per transcription and, when the language
token is forced to "en" over Bosnian speech, it silently TRANSLATES to
English instead of transcribing. Mixed mode ("multi") therefore detects the
language per take (and per chunk in streaming), but restricted to the
user's real languages so accuracy doesn't degrade to full 100-language
auto-detect.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from engine import WhisperTranscriber  # noqa: E402


def _make(cfg_lang):
    cfg = {"whisper": {"model_size": "small", "language": cfg_lang},
           "cleanup": {}}
    return WhisperTranscriber(cfg)


class FakeModel:
    """Stands in for faster_whisper.WhisperModel.detect_language."""

    def __init__(self, probs):
        self._probs = probs

    def detect_language(self, audio):
        best = max(self._probs, key=lambda t: t[1])
        return best[0], best[1], self._probs


def test_multi_config_enables_restricted_detection():
    t = _make("multi")
    assert t.language is None
    assert t.multi_langs == ("en", "bs", "hr", "sr")


def test_fixed_language_unchanged():
    t = _make("en")
    assert t.language == "en"
    assert t.multi_langs is None


def test_auto_language_unchanged():
    t = _make("auto")
    assert t.language is None
    assert t.multi_langs is None


def test_pick_language_prefers_users_languages():
    t = _make("multi")
    # German scores highest overall, but the user's set is en/bs/hr/sr:
    # bs is the best among THOSE and must win.
    t._model = FakeModel([("de", 0.6), ("bs", 0.3), ("en", 0.1)])
    audio = np.zeros(16000, dtype=np.float32)
    assert t._pick_language(audio) == "bs"


def test_pick_language_english_wins_when_spoken():
    t = _make("multi")
    t._model = FakeModel([("en", 0.8), ("bs", 0.15), ("hr", 0.05)])
    audio = np.zeros(16000, dtype=np.float32)
    assert t._pick_language(audio) == "en"


def test_pick_language_fixed_language_short_circuits():
    t = _make("bs")
    t._model = FakeModel([("en", 0.99)])
    audio = np.zeros(16000, dtype=np.float32)
    assert t._pick_language(audio) == "bs"


def test_pick_language_survives_detector_error():
    t = _make("multi")

    class Broken:
        def detect_language(self, audio):
            raise RuntimeError("boom")

    t._model = Broken()
    audio = np.zeros(16000, dtype=np.float32)
    # falls back to plain auto (None) instead of raising
    assert t._pick_language(audio) is None
