"""Hotkey defaults that exist on the keyboard in front of the user.

The shipped defaults were chosen for a Windows PC keyboard. On a MacBook Air
there is no right Control and no Pause key at all, and a bare F6-F9 press
sends media/brightness because macOS ships fnState unset. See
docs/adr/0003-per-platform-hotkey-defaults.md.

The seam is defaults_for(system): a pure table lookup, so both platforms'
answers are testable from either platform. An empty string means "ship this
unbound" — the user can still set it in Settings.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hotkeys  # noqa: E402

ALL_ACTIONS = {"push_to_talk_key", "toggle_key", "abort_key", "copy_key",
               "mode_cycle_key", "pause_key", "rerecord_key"}

# The default *table* is a pure lookup and is checked on every runner. The
# tests below that resolve a name into a real key need pynput, which imports
# a per-platform backend — Xlib on Linux, which raises without a DISPLAY. A
# headless runner skips those rather than failing for a reason that says
# nothing about the defaults.
try:
    from pynput import keyboard as _keyboard
except Exception:  # no pynput, or no display to bind a backend to
    _keyboard = None

needs_pynput = pytest.mark.skipif(
    _keyboard is None, reason="pynput has no usable backend here (headless)")


def test_windows_defaults_are_unchanged():
    d = hotkeys.defaults_for("Windows")
    assert d["push_to_talk_key"] == "ctrl_r"
    assert d["toggle_key"] == "f9"
    assert d["abort_key"] == "esc"
    assert d["copy_key"] == "f8"
    assert d["mode_cycle_key"] == "f7"
    assert d["pause_key"] == "pause"
    assert d["rerecord_key"] == "f6"


def test_macos_push_to_talk_is_right_option():
    assert hotkeys.defaults_for("Darwin")["push_to_talk_key"] == "alt_r"


def test_macos_ships_no_pause_binding():
    """There is no Pause key on the keyboard, and no Key.pause in pynput."""
    assert hotkeys.defaults_for("Darwin")["pause_key"] == ""


def test_macos_keeps_copy_last_bound():
    """The rescue path when text lands in the wrong window — worth the fn+F8
    chord (ADR 0003)."""
    assert hotkeys.defaults_for("Darwin")["copy_key"] == "f8"


def test_macos_ships_the_convenience_bindings_unbound():
    d = hotkeys.defaults_for("Darwin")
    for action in ("toggle_key", "mode_cycle_key", "rerecord_key"):
        assert d[action] == "", action


def test_macos_abort_stays_escape():
    assert hotkeys.defaults_for("Darwin")["abort_key"] == "esc"


def test_both_platforms_answer_for_every_action():
    for system in ("Windows", "Darwin", "Linux"):
        assert set(hotkeys.defaults_for(system)) == ALL_ACTIONS


@needs_pynput
def test_no_default_binds_a_key_absent_from_that_platform():
    """The point of the whole ticket: a shipped default must resolve to a real
    key on the platform it ships to. Checked against the running platform's
    own pynput enum, which is the only one we can ask honestly."""
    import platform

    keyboard = _keyboard

    available = hotkeys.available_keys(keyboard.Key)
    for action, name in hotkeys.defaults_for(platform.system()).items():
        if not name:
            continue          # deliberately unbound
        assert name in available or len(name) == 1, (action, name)


@needs_pynput
def test_unbound_names_are_not_resolved_to_a_fallback_key():
    """An unbound default must stay unbound. Falling back to Right Ctrl here
    would silently bind an action to the push-to-talk key."""
    assert hotkeys.parse_key("") is None
    assert hotkeys.parse_key("   ") is None


@needs_pynput
def test_controller_skips_unbound_actions(monkeypatch):
    """An unbound action never fires, and never steals a key from another."""
    fired = []
    names = dict(hotkeys.defaults_for("Darwin"))
    ctl = hotkeys.HotkeyController(
        "push_to_talk",
        {"ptt": names["push_to_talk_key"], "toggle": names["toggle_key"],
         "abort": names["abort_key"], "copy": names["copy_key"],
         "mode_cycle": names["mode_cycle_key"], "pause": names["pause_key"],
         "rerecord": names["rerecord_key"]},
        {k: (lambda k=k: fired.append(k))
         for k in ("ptt_start", "ptt_stop", "abort", "toggle", "copy",
                   "mode_cycle", "pause", "rerecord")},
    )

    class _NoListener:
        daemon = False

        def __init__(self, **kw):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    from pynput import keyboard
    monkeypatch.setattr(keyboard, "Listener", _NoListener)
    ctl.start()

    assert ctl._toggle_key is None
    assert ctl._pause_key is None
    assert ctl._rerecord_key is None
    assert ctl._ptt_key is keyboard.Key.alt_r

    # pressing the PTT key must not also trip an unbound action
    ctl._on_press(keyboard.Key.alt_r)
    assert fired == ["ptt_start"]


@needs_pynput
def test_key_matches_never_matches_an_unbound_target():
    keyboard = _keyboard

    assert hotkeys.HotkeyController._key_matches(keyboard.Key.alt_r, None) is False
