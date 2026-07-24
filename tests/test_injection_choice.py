import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from win32_input import choose_injection


def test_short_text_is_typed():
    assert choose_injection("hello world", mode="auto", paste_threshold=300) == "type"


def test_long_text_is_pasted():
    assert choose_injection("x" * 301, mode="auto", paste_threshold=300) == "paste"


def test_forced_modes_win():
    assert choose_injection("x" * 999, mode="type", paste_threshold=300) == "type"
    assert choose_injection("hi", mode="paste", paste_threshold=300) == "paste"


def test_multiline_always_pastes_in_auto():
    # newline keystrokes can trigger "send" in chat apps — paste is safer
    assert choose_injection("line one\nline two", mode="auto",
                            paste_threshold=300) == "paste"


def test_terminal_prefers_type_even_for_long_text():
    # terminals drop synthesized Ctrl+V too often; type long single-line text
    assert choose_injection("x" * 999, mode="auto", paste_threshold=300,
                            prefer_type=True) == "type"


def test_terminal_multiline_still_pastes():
    # a typed Enter would execute the half-finished line in a shell
    assert choose_injection("line one\nline two", mode="auto",
                            paste_threshold=300, prefer_type=True) == "paste"


def test_prefer_type_does_not_override_forced_paste():
    assert choose_injection("hi", mode="paste", paste_threshold=300,
                            prefer_type=True) == "paste"
