"""The macOS Input Backend.

Two kinds of assertion live here, deliberately separated:

  * Pure, runs everywhere — the Injection interface resolves to the mac
    backend on Darwin, and the UTF-16 chunking that feeds
    CGEventKeyboardSetUnicodeString is correct for astral-plane characters
    (an emoji is two UTF-16 units and must never be split across events).
  * Real, macOS only — events are actually posted and observed coming back
    through an event tap. Nothing here fakes Quartz; a skipped test is
    honest, a mocked one would not be.
"""
import os
import platform
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import input_backend  # noqa: E402

IS_MAC = platform.system() == "Darwin"
macos_only = pytest.mark.skipif(not IS_MAC, reason="macOS Input Backend")


# ---- backend resolution ----------------------------------------------------


@macos_only
def test_the_mac_backend_is_what_delivery_gets_on_this_platform():
    assert input_backend.active_backend_name() == "macos"


@macos_only
def test_the_backend_implements_every_interface_operation():
    from src import mac_input

    for op in ("inject_text_native_unicode", "inject_text_via_paste",
               "inject_backspaces", "select_all"):
        assert callable(getattr(mac_input, op))


# ---- UTF-16 chunking (pure) ------------------------------------------------


def test_chunking_keeps_a_surrogate_pair_in_one_event():
    """An emoji is two UTF-16 units. Split across two CGEvents it arrives as
    two replacement characters, so a chunk boundary must never fall inside
    the pair."""
    from src import mac_input

    text = "a" * 19 + "\U0001F600" + "b" * 5      # boundary lands on the emoji
    chunks = mac_input.utf16_chunks(text, chunk_units=20)
    assert "".join(chunks) == text
    for chunk in chunks:
        assert len(chunk.encode("utf-16le")) // 2 <= 20
        # no chunk ends on a lone high surrogate
        units = chunk.encode("utf-16le")
        last = int.from_bytes(units[-2:], "little")
        assert not (0xD800 <= last <= 0xDBFF)


def test_chunking_normalises_windows_line_endings():
    from src import mac_input

    assert "".join(mac_input.utf16_chunks("a\r\nb\rc")) == "a\nb\nc"


def test_chunking_an_empty_string_produces_no_events():
    from src import mac_input

    assert mac_input.utf16_chunks("") == []


# ---- real event posting ----------------------------------------------------


@macos_only
def test_typed_text_is_actually_posted_to_the_system():
    """Type a string and observe the characters arriving through an event
    tap. This is the whole point of the backend: real keystrokes, not a
    function that returns a plausible number."""
    from pynput import keyboard

    from src import mac_input

    seen = []
    listener = keyboard.Listener(
        on_press=lambda k: seen.append(getattr(k, "char", None)))
    listener.start()
    time.sleep(1.0)
    try:
        sent = mac_input.inject_text_native_unicode("dictate")
        time.sleep(0.6)
    finally:
        listener.stop()

    assert sent == len("dictate")
    assert "".join(c for c in seen if c) .endswith("dictate")


@macos_only
def test_backspaces_are_actually_posted():
    from pynput import keyboard

    from src import mac_input

    seen = []
    listener = keyboard.Listener(on_press=lambda k: seen.append(k))
    listener.start()
    time.sleep(1.0)
    try:
        sent = mac_input.inject_backspaces(3)
        time.sleep(0.5)
    finally:
        listener.stop()

    assert sent == 3
    assert sum(1 for k in seen if k == keyboard.Key.backspace) >= 3


@macos_only
def test_paste_puts_the_text_on_the_pasteboard_and_restores_it():
    """The Windows contract: our text is on the pasteboard when the paste
    shortcut fires, and whatever was there before comes back afterwards."""
    import AppKit

    from src import mac_input

    pb = AppKit.NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_("previous clipboard", AppKit.NSPasteboardTypeString)

    observed = {}

    def _watch(text):
        observed["at_paste"] = pb.stringForType_(AppKit.NSPasteboardTypeString)

    ok = mac_input.inject_text_via_paste("dictated text",
                                         restore_delay=0.2,
                                         _on_paste=_watch)
    assert ok is True
    assert observed["at_paste"] == "dictated text"

    time.sleep(1.2)   # let the background restore run
    assert pb.stringForType_(AppKit.NSPasteboardTypeString) == "previous clipboard"


@macos_only
def test_select_all_is_sent_as_a_command_chord():
    from src import mac_input

    assert mac_input.select_all() is True
