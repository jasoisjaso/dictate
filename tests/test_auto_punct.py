"""Tests for auto_punctuation module."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from auto_punct import add_punctuation


def test_adds_period_at_end():
    assert add_punctuation("hello world") == "Hello world."


def test_capitalises_first_letter():
    assert add_punctuation("hello world.") == "Hello world."


def test_doesnt_double_punctuate():
    assert add_punctuation("hello world.") == "Hello world."


def test_preserves_existing_capitals():
    assert add_punctuation("Hello World") == "Hello World."


def test_handles_empty():
    assert add_punctuation("") == ""


def test_handles_already_capitalised():
    assert add_punctuation("Hello world") == "Hello world."


def test_preserves_question_mark():
    assert add_punctuation("what is this") == "What is this."


def test_preserves_exclamation():
    assert add_punctuation("wow") == "Wow."


def test_engine_respects_auto_punctuation_flag():
    """post_process must actually add a period when auto_punctuation is on
    and leave it off when the flag is off. Regression for auto-punct doing
    nothing in-app because the running engine's flag was never updated."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from engine import WhisperTranscriber
    e = WhisperTranscriber({"whisper": {"model_size": "large-v3-turbo",
                                        "language": "en"},
                            "cleanup": {}, "post_processing": {}})
    raw = "this works the way it needs to work"
    e.auto_punctuation = False
    assert not e.post_process(raw).endswith(".")
    e.auto_punctuation = True
    out = e.post_process(raw)
    assert out.endswith(".") and out[0].isupper()
