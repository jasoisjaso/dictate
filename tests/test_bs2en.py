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


def test_translate_model_prefers_dolphin_over_tiny():
    """dolphin3:8b beats qwen2.5:3b for bs->en: the 3B mistranslates
    content words (skladiste -> archive) while dolphin gets them right
    and still evals in 1-3s warm."""
    import json
    from unittest import mock

    names = ["qwen2.5:3b", "dolphin3:8b", "hermes4:14b"]
    payload = json.dumps({"models": [{"name": n} for n in names]}).encode()

    class FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
        assert device.ollama_pick_translate_model() == "dolphin3:8b"


def test_translate_returns_none_on_error():
    # unreachable endpoint -> None, caller falls back
    out = cleanup.ollama_translate_to_english(
        "tekst", "nomodel", "http://127.0.0.1:1", timeout=0.3)
    assert out is None


# ---- en2bs (speak English, write Bosnian) -------------------------------

def test_en2bs_config():
    t = _make("en2bs")
    assert t.translate_to_bs is True
    assert t.translate_to_en is False
    assert t.language is None
    assert t.multi_langs == ("en", "bs", "hr", "sr")


def test_en2bs_english_take_goes_through_translator(monkeypatch):
    t = _make("en2bs")
    monkeypatch.setattr(device, "ollama_pick_bs_translate_model",
                        lambda *a, **k: "testmodel")
    monkeypatch.setattr(cleanup, "ollama_translate_to_bosnian",
                        lambda text, m, e, timeout=0: "prevedeni tekst")
    t._en_detected = True
    out = t.post_process("please send the report to the boss")
    assert "prevedeni" in out.lower()


def test_en2bs_bosnian_take_skips_translation(monkeypatch):
    """A take already detected as Bosnian must not be re-translated."""
    t = _make("en2bs")
    called = {}

    def fake(*a, **k):
        called["yes"] = True
        return "SHOULD NOT APPEAR"

    monkeypatch.setattr(cleanup, "ollama_translate_to_bosnian", fake)
    t._en_detected = False
    t._nonen_detected = True
    out = t.post_process("molim te posalji izvjestaj")
    assert "SHOULD NOT APPEAR" not in out
    assert "yes" not in called


def test_en2bs_failure_falls_back_to_spoken(monkeypatch):
    t = _make("en2bs")
    monkeypatch.setattr(device, "ollama_pick_bs_translate_model",
                        lambda *a, **k: "testmodel")
    monkeypatch.setattr(cleanup, "ollama_translate_to_bosnian",
                        lambda *a, **k: None)
    t._en_detected = True
    out = t.post_process("please send the report")
    assert "report" in out.lower()


def test_bs_translate_model_prefers_quality():
    """en->bs must pick a quality model, not the fastest tiny one that
    butchers Bosnian."""
    import json
    from unittest import mock

    names = ["qwen2.5:3b", "gpt-oss:20b", "dolphin3:8b"]
    payload = json.dumps({"models": [{"name": n} for n in names]}).encode()

    class FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
        # gpt-oss:20b is the quality pick, NOT qwen2.5:3b (the speed pick)
        assert device.ollama_pick_bs_translate_model() == "gpt-oss:20b"


def test_bs_translate_model_prefers_resident_hermes4():
    """hermes4:14b outranks gpt-oss:20b for en->bs: gpt-oss writes the
    best Bosnian but its 13GB cold load (224-400s measured) times out
    every first take on 16GB cards, while hermes4 is also the default
    polish model and is usually already resident."""
    import json
    from unittest import mock

    names = ["qwen2.5:3b", "gpt-oss:20b", "hermes4:14b", "dolphin3:8b"]
    payload = json.dumps({"models": [{"name": n} for n in names]}).encode()

    class FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
        assert device.ollama_pick_bs_translate_model() == "hermes4:14b"


def test_bs_translate_returns_none_on_error():
    out = cleanup.ollama_translate_to_bosnian(
        "text", "nomodel", "http://127.0.0.1:1", timeout=0.3)
    assert out is None
