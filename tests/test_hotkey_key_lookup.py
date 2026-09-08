"""Key lookup must degrade, not crash, when a platform lacks a key.

pynput's key enum is platform-specific: macOS has no Key.pause,
Key.scroll_lock, Key.menu or Key.insert. The lookup table used to name those
eagerly, so building it raised AttributeError and the hotkey listener could
not start for ANY key name.

The seam tested here is available_keys(key_enum): a pure name -> key mapping
built from whatever the running platform's enum actually defines. Feeding it
a stub enum lets the degradation be tested on every platform, including
Windows CI where nothing is missing.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hotkeys  # noqa: E402

# The stub-enum tests are the ones that matter for the degradation itself and
# run anywhere. The tests below that ask the *real* enum need pynput, which
# imports its Xlib backend on Linux and raises without a DISPLAY — so a
# headless runner skips them rather than reporting a failure that says nothing
# about this code.
try:
    from pynput import keyboard as _keyboard
except Exception:  # no pynput, or no display to bind a backend to
    _keyboard = None

needs_pynput = pytest.mark.skipif(
    _keyboard is None, reason="pynput has no usable backend here (headless)")


class _StubKey:
    """Stands in for pynput.keyboard.Key on a platform missing keys."""
    ctrl_r = "CTRL_R"
    ctrl_l = "CTRL_L"
    ctrl = "CTRL"
    alt_r = "ALT_R"
    alt = "ALT"
    alt_l = "ALT_L"
    shift_r = "SHIFT_R"
    shift = "SHIFT"
    cmd = "CMD"
    cmd_r = "CMD_R"
    caps_lock = "CAPS"
    space = "SPACE"
    esc = "ESC"
    tab = "TAB"
    f1 = "F1"
    f6 = "F6"
    f8 = "F8"
    f9 = "F9"
    # deliberately absent: pause, scroll_lock, menu, insert, alt_gr, f2..f5,
    # f7, f10..f12 — exactly the shape of pynput's macOS enum.


def test_available_keys_skips_names_the_platform_lacks():
    table = hotkeys.available_keys(_StubKey)
    for missing in ("pause", "scroll_lock", "menu", "insert"):
        assert missing not in table
    assert table["ctrl_r"] == "CTRL_R"
    assert table["f8"] == "F8"


def test_available_keys_never_raises_on_a_sparse_enum():
    class _Bare:
        ctrl_r = "CTRL_R"

    assert hotkeys.available_keys(_Bare) == {"ctrl_r": "CTRL_R",
                                             "rctrl": "CTRL_R"}


@needs_pynput
def test_available_keys_on_the_real_platform_enum():
    """The real thing: on macOS this used to raise AttributeError."""
    keyboard = _keyboard

    table = hotkeys.available_keys(keyboard.Key)
    assert table["ctrl_r"] is keyboard.Key.ctrl_r
    assert "esc" in table and "space" in table


@needs_pynput
def test_parse_key_resolves_common_names_on_any_platform():
    keyboard = _keyboard

    assert hotkeys.parse_key("ctrl_r") is keyboard.Key.ctrl_r
    assert hotkeys.parse_key("alt_r") is keyboard.Key.alt_r
    assert hotkeys.parse_key("esc") is keyboard.Key.esc
    assert hotkeys.parse_key("f8") is keyboard.Key.f8


@needs_pynput
def test_parse_key_single_char_still_becomes_a_keycode():
    assert hotkeys.parse_key("d").char == "d"


@needs_pynput
def test_parse_key_falls_back_for_an_unknown_name(caplog):
    keyboard = _keyboard

    assert hotkeys.parse_key("nonexistent_key") is keyboard.Key.ctrl_r


@needs_pynput
def test_parse_key_falls_back_for_a_key_absent_on_this_platform():
    """'pause' exists on Windows, not on macOS. Either way: no exception."""
    keyboard = _keyboard

    got = hotkeys.parse_key("pause")
    if hasattr(keyboard.Key, "pause"):
        assert got is keyboard.Key.pause
    else:
        assert got is keyboard.Key.ctrl_r


@needs_pynput
def test_every_shipped_default_key_name_resolves_without_raising():
    """Every key name config/settings.toml ships must be safe to parse."""
    for name in ("ctrl_r", "alt_r", "f9", "esc", "f8", "f7", "pause", "f6"):
        assert hotkeys.parse_key(name) is not None
