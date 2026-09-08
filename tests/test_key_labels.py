"""A key has ONE name, wherever the app says it.

The name of a bound key is shown in three places: the tray menu ("Copy last
dictation (fn+F8)"), the trigger hint ("Hold Right Option and talk"), and the
Settings picker. Those three read from two different modules, and for a while
they read from two different tables — so on this Mac the tray said "Right Alt"
and "F8" for exactly the keys Settings called "Right Option" and "fn+F8".
Both were describing the same binding.

The table lives in `hotkeys` now, because that is the module that also owns
the per-platform defaults it has to label. `settings_gui.key_label` forwards
to it. These tests hold the two together and keep the vocabulary honest:
labels are pure functions of (name, system), so both platforms' answers are
checked from either one.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import hotkeys  # noqa: E402


# ---- the vocabulary itself (no Qt needed) ----------------------------------


def test_the_mac_talk_key_is_named_the_way_the_keyboard_names_it():
    """alt_r is the shipped macOS push-to-talk key. A Mac keyboard has no key
    labelled "Alt" on it at all — telling a user to hold "Right Alt" is
    telling them to find a key that isn't printed anywhere."""
    assert hotkeys.key_label("alt_r", "Darwin") == "Right Option"
    assert hotkeys.key_label("alt_r", "Windows") == "Right Alt"


def test_function_keys_are_labelled_as_the_chord_a_mac_actually_needs():
    """macOS ships com.apple.keyboard.fnState unset, so a bare F8 press is
    media play/pause and the copy-last rescue path appears not to work."""
    assert hotkeys.key_label("f8", "Darwin") == "fn+F8"
    assert hotkeys.key_label("f8", "Windows") == "F8"


def test_an_unbound_action_says_so_rather_than_rendering_blank():
    assert hotkeys.key_label("", "Darwin") == "Not set"
    assert hotkeys.key_label("   ", "Windows") == "Not set"


def test_an_ordinary_letter_key_still_labels_itself():
    assert hotkeys.key_label("d", "Darwin") == "D"


def test_every_shipped_default_gets_a_label_on_its_own_platform():
    """No shipped binding may render as a bare config string in the tray."""
    for system in ("Windows", "Darwin"):
        for action, name in hotkeys.defaults_for(system).items():
            label = hotkeys.key_label(name, system)
            assert label and label == label.strip(), (system, action, name)
            assert label != name or len(name) == 1, (system, action, name)


# ---- and the two call sites agree ------------------------------------------


def test_the_tray_and_the_settings_picker_give_the_same_key_the_same_name():
    """The regression: two tables, one of which had never heard of a Mac."""
    settings_gui = pytest.importorskip(
        "settings_gui", reason="the key picker is a Qt widget")

    for system in ("Windows", "Darwin"):
        names = set(hotkeys.defaults_for(system).values())
        names |= {"alt_r", "ctrl_r", "cmd", "cmd_r", "f7", "f8", "esc", ""}
        for name in names:
            assert (hotkeys.key_label(name, system)
                    == settings_gui.key_label(name, system)), (system, name)
