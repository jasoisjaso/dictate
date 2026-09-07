"""The Settings key-picker must speak the platform in front of the user.

Two things go wrong if it doesn't (docs/adr/0003):

  * the rows fall back to Windows key names, so a Mac user opening Settings
    sees "Right Ctrl" as their talk key when the app is actually listening on
    Right Option;
  * an action shipped deliberately unbound renders as an empty button with no
    label, which reads as a bug rather than a choice.

The seams are pure: key_label(name, system) and default_key(action, system).
Both are testable from either platform.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

pytest.importorskip("PySide6", reason="the key picker is a Qt widget")

import hotkeys  # noqa: E402
import settings_gui  # noqa: E402


# ---- labels ----------------------------------------------------------------


def test_right_option_is_named_for_the_key_on_the_mac_keyboard():
    assert settings_gui.key_label("alt_r", "Darwin") == "Right Option"


def test_the_same_key_is_named_right_alt_on_windows():
    assert settings_gui.key_label("alt_r", "Windows") == "Right Alt"


def test_command_is_named_command_on_mac():
    assert settings_gui.key_label("cmd", "Darwin") == "Command"
    assert settings_gui.key_label("cmd_r", "Darwin") == "Right Command"


def test_function_keys_are_shown_as_the_chord_a_mac_actually_needs():
    """macOS ships fnState unset, so a bare F8 is media play/pause."""
    assert settings_gui.key_label("f8", "Darwin") == "fn+F8"
    assert settings_gui.key_label("f8", "Windows") == "F8"


def test_an_unbound_action_says_so_instead_of_rendering_blank():
    assert settings_gui.key_label("", "Darwin") == "Not set"
    assert settings_gui.key_label("   ", "Windows") == "Not set"


def test_an_ordinary_letter_key_still_labels_itself():
    assert settings_gui.key_label("d", "Darwin") == "D"


# ---- defaults --------------------------------------------------------------


def test_the_picker_defaults_match_the_shipped_hotkey_defaults():
    """One source of truth: the picker must not carry its own copy."""
    for system in ("Windows", "Darwin"):
        shipped = hotkeys.defaults_for(system)
        for action, expected in shipped.items():
            assert settings_gui.default_key(action, system) == expected, (
                system, action)


def test_the_mac_talk_key_row_defaults_to_right_option():
    assert settings_gui.default_key("push_to_talk_key", "Darwin") == "alt_r"


def test_an_unknown_action_defaults_to_unbound_rather_than_guessing():
    assert settings_gui.default_key("no_such_key", "Darwin") == ""


# ---- the picker only offers keys this platform has -------------------------


def test_capture_rejects_a_key_the_platform_does_not_have():
    """A captured name has to survive parse_key on this machine, or Settings
    would let a user bind something that silently never fires."""
    import platform

    from pynput import keyboard

    available = hotkeys.available_keys(keyboard.Key)
    for action, name in hotkeys.defaults_for(platform.system()).items():
        if not name:
            continue
        assert settings_gui.key_is_bindable(name), (action, name)


def test_a_name_absent_from_this_platform_is_not_bindable():
    from pynput import keyboard

    absent = next((n for n in ("pause", "scroll_lock", "menu", "insert")
                   if not hasattr(keyboard.Key, n)), None)
    if absent is None:
        pytest.skip("this platform defines all of them (Windows)")
    assert settings_gui.key_is_bindable(absent) is False


def test_the_empty_name_is_bindable_because_unbound_is_a_valid_choice():
    assert settings_gui.key_is_bindable("") is True
