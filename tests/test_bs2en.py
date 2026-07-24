"""Speak Bosnian, write English ("bs2en") mode.

Design: transcribe as spoken (restricted detection, like mixed mode), then
translate non-English takes to English through the local Ollama. Whisper's
native translate task is deliberately NOT used because large-v3-turbo (the
default GPU model) was trained without the translation task and silently
ignores it. Fail-open everywhere: no Ollama means the as-spoken text is
delivered, never nothing.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import cleanup  # noqa: E402
import device  # noqa: E402
from engine import WhisperTranscriber  # noqa: E402


def _make(cfg_lang):
    cfg = {"whisper": {"model_size": "small", "language": cfg_lang},
           "cleanup": {}}
    return WhisperTranscriber(cfg)


def test_bs2en_config():
    t = _make("bs2en")
    assert t.translate_to_en is True
    assert t.language is None
    assert t.multi_langs == ("en", "bs", "hr", "sr")
    assert t.task == "transcribe"  # native translate task must NOT be used


def test_other_modes_do_not_translate():
    for lang in ("en", "auto", "multi", "bs"):
        assert _make(lang).translate_to_en is False


def test_nonen_flag_set_by_detection():
    t = _make("bs2en")

    class FakeModel:
        def detect_language(self, audio):
            return "bs", 0.9, [("bs", 0.9), ("en", 0.1)]

    t._model = FakeModel()
    audio = np.zeros(16000, dtype=np.float32)
    assert t._pick_language(audio) == "bs"
    # transcribe_audio_buffer sets the flag from the pick; simulate that
    lang = t._pick_language(audio)
    if lang not in (None, "en"):
        t._nonen_detected = True
    assert t._nonen_detected is True


def test_pure_english_take_skips_translation(monkeypatch):
    """post_process must not call Ollama when no non-English was detected."""
    t = _make("bs2en")
    called = {}

    def fake_translate(*a, **k):
        called["yes"] = True
        return "SHOULD NOT APPEAR"

    monkeypatch.setattr(cleanup, "ollama_translate_to_english", fake_translate)
    t._nonen_detected = False
    out = t.post_process("hello there boss")
    assert "SHOULD NOT APPEAR" not in out
    assert "yes" not in called


def test_bosnian_take_goes_through_translator(monkeypatch):
    t = _make("bs2en")
    monkeypatch.setattr(device, "ollama_pick_translate_model",
                        lambda *a, **k: "testmodel")
    monkeypatch.setattr(cleanup, "ollama_translate_to_english",
                        lambda text, m, e, timeout=0: "translated text")
    t._nonen_detected = True
    out = t.post_process("molim te posalji izvjestaj")
    assert "translated" in out.lower()


def test_translation_failure_falls_back_to_spoken(monkeypatch):
    """Ollama down -> the as-spoken text is delivered, never lost."""
    t = _make("bs2en")
    monkeypatch.setattr(device, "ollama_pick_translate_model",
                        lambda *a, **k: "testmodel")
    monkeypatch.setattr(cleanup, "ollama_translate_to_english",
                        lambda *a, **k: None)
    t._nonen_detected = True
    out = t.post_process("molim te posalji izvjestaj")
    assert "posalji" in out.lower()


def test_translate_model_priority_prefers_small():
    """The translate pass must prefer a small fast model over big ones."""
    import json
    from unittest import mock

    names = ["hermes4:14b", "qwen2.5:3b", "qwen3-coder:30b"]
    payload = json.dumps({"models": [{"name": n} for n in names]}).encode()

    class FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
        assert device.ollama_pick_translate_model() == "qwen2.5:3b"


def test_translate_returns_none_on_error():
    # unreachable endpoint -> None, caller falls back
    out = cleanup.ollama_translate_to_english(
        "tekst", "nomodel", "http://127.0.0.1:1", timeout=0.3)
    assert out is None
