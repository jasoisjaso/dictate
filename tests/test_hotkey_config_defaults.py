"""The shipped config must not hand a Mac a Windows keyboard.

config/settings.toml ships explicit hotkey values chosen for a Windows PC
(ctrl_r, pause, f6-f9). Those are *values*, not absences, so every
`hk.get("push_to_talk_key", <platform default>)` in the app found ctrl_r and
the per-platform table from ADR 0003 never fired.

The fix is an ordering rule, and that is what these tests pin down:

    packaged defaults  ->  platform overlay  ->  the user's settings.toml

The platform overlay only touches [hotkeys], and only where the user has said
nothing. A user who binds a key keeps it on every platform.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import hotkeys  # noqa: E402

PACKAGED = {
    "hotkeys": {
        "mode": "push_to_talk",
        "push_to_talk_key": "ctrl_r",
        "toggle_key": "f9",
        "abort_key": "esc",
        "copy_key": "f8",
        "mode_cycle_key": "f7",
        "pause_key": "pause",
        "rerecord_key": "f6",
    },
    "whisper": {"language": "en"},
}


def test_macos_gets_the_mac_hotkey_defaults_not_the_packaged_windows_ones():
    merged = config.apply_platform_defaults(PACKAGED, system="Darwin")
    hk = merged["hotkeys"]
    assert hk["push_to_talk_key"] == "alt_r"
    assert hk["pause_key"] == ""
    assert hk["toggle_key"] == ""
    assert hk["mode_cycle_key"] == ""
    assert hk["rerecord_key"] == ""


def test_macos_keeps_the_bindings_adr_0003_kept():
    hk = config.apply_platform_defaults(PACKAGED, system="Darwin")["hotkeys"]
    assert hk["copy_key"] == "f8"      # the rescue path, worth the fn chord
    assert hk["abort_key"] == "esc"


def test_windows_is_left_exactly_as_packaged():
    merged = config.apply_platform_defaults(PACKAGED, system="Windows")
    assert merged["hotkeys"] == PACKAGED["hotkeys"]


def test_the_overlay_agrees_with_the_hotkeys_table():
    """One source of truth: config must not carry its own copy of the keys."""
    for system in ("Windows", "Darwin"):
        hk = config.apply_platform_defaults(PACKAGED, system=system)["hotkeys"]
        for action, expected in hotkeys.defaults_for(system).items():
            assert hk[action] == expected, (system, action)


def test_the_trigger_mode_is_not_a_key_and_survives():
    hk = config.apply_platform_defaults(PACKAGED, system="Darwin")["hotkeys"]
    assert hk["mode"] == "push_to_talk"


def test_nothing_outside_hotkeys_is_touched():
    merged = config.apply_platform_defaults(PACKAGED, system="Darwin")
    assert merged["whisper"] == {"language": "en"}


def test_the_packaged_dict_is_not_mutated():
    before = dict(PACKAGED["hotkeys"])
    config.apply_platform_defaults(PACKAGED, system="Darwin")
    assert PACKAGED["hotkeys"] == before


def test_a_config_with_no_hotkeys_section_still_gets_defaults():
    merged = config.apply_platform_defaults({}, system="Darwin")
    assert merged["hotkeys"]["push_to_talk_key"] == "alt_r"


def test_the_users_own_binding_beats_the_platform_default():
    """The whole point of the ordering: platform defaults fill gaps, they do
    not overrule a choice the user made."""
    user = {"hotkeys": {"push_to_talk_key": "f13"}}
    base = config.apply_platform_defaults(PACKAGED, system="Darwin")
    merged = config._deep_merge(base, user)
    assert merged["hotkeys"]["push_to_talk_key"] == "f13"
    assert merged["hotkeys"]["copy_key"] == "f8"


def test_load_applies_the_overlay_for_the_running_platform(monkeypatch, tmp_path):
    """End to end through load(): no user file, so what comes out is the
    packaged defaults with this platform's keys."""
    import platform

    empty = tmp_path / "settings.toml"
    monkeypatch.setattr(config.paths, "config_path", lambda: str(empty))
    merged = config.load(defaults=PACKAGED)
    expected = hotkeys.defaults_for(platform.system())
    assert merged["hotkeys"]["push_to_talk_key"] == expected["push_to_talk_key"]
