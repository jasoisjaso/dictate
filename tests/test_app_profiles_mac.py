"""Ticket 10: App Profiles on macOS, over bundle identifiers.

The Foreground App is named differently by each platform — Windows by
executable (`cmd.exe`), macOS by bundle identifier (`com.apple.Terminal`) —
and CONTEXT.md commits to one `match` list holding both kinds, so a profile
someone writes stays portable even though an identifier is not.

Bundle identifier over display name because it is stable and
locale-independent: a French Mac's Terminal is still `com.apple.Terminal`.

`resolve_profile` was already identifier-agnostic; what this file pins is
that the SHIPPED defaults name mac apps beside the Windows ones, and that
`foreground_app` asks the right question per platform.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import appcontext


DEFAULTS = appcontext.DEFAULT_PROFILES


def profile_for(identifier):
    return appcontext.resolve_profile(identifier, DEFAULTS).get("_profile")


# ---- the acceptance criterion, stated directly ------------------------------

def test_dictating_into_terminal_on_macos_selects_the_terminal_profile():
    prof = appcontext.resolve_profile("com.apple.Terminal", DEFAULTS)
    assert prof["_profile"] == "terminal"
    assert prof["verbatim"] is True


def test_windows_terminal_still_selects_the_terminal_profile():
    prof = appcontext.resolve_profile("WindowsTerminal.exe", DEFAULTS)
    assert prof["_profile"] == "terminal"
    assert prof["verbatim"] is True


# ---- both identifier kinds, in one match list -------------------------------

def test_one_match_list_holds_both_identifier_kinds():
    """A single profile answers for an exe name and a bundle id alike."""
    profiles = {"terminal": {"match": ["cmd.exe", "com.apple.Terminal"],
                             "verbatim": True}}
    assert appcontext.resolve_profile("cmd.exe", profiles)["verbatim"] is True
    assert appcontext.resolve_profile("com.apple.Terminal",
                                      profiles)["verbatim"] is True


def test_bundle_identifier_matching_is_case_insensitive():
    """Bundle ids are case-sensitive to macOS but not to a user typing one
    into settings.toml, and the exe path has always been forgiving."""
    profiles = {"chat": {"match": ["com.tinyspeck.slackmacgap"], "tone": "casual"}}
    assert appcontext.resolve_profile("com.TinySpeck.SlackMacGap",
                                      profiles)["tone"] == "casual"


def test_wildcards_work_over_bundle_identifiers():
    profiles = {"jet": {"match": ["com.jetbrains.*"], "verbatim": True}}
    assert appcontext.resolve_profile("com.jetbrains.pycharm",
                                      profiles)["verbatim"] is True
    assert appcontext.resolve_profile("com.apple.Terminal", profiles) == {}


def test_a_bundle_id_never_matches_an_exe_pattern_by_accident():
    profiles = {"terminal": {"match": ["Code.exe"], "verbatim": True}}
    assert appcontext.resolve_profile("com.microsoft.VSCode", profiles) == {}


# ---- shipped defaults cover common mac apps ---------------------------------

def test_shipped_defaults_cover_common_mac_terminals():
    for bundle in ("com.apple.Terminal", "com.googlecode.iterm2",
                   "net.kovidgoyal.kitty", "org.alacritty",
                   "com.github.wez.wezterm", "dev.warp.Warp-Stable"):
        assert profile_for(bundle) == "terminal", bundle


def test_shipped_defaults_cover_common_mac_editors():
    for bundle in ("com.microsoft.VSCode", "com.jetbrains.pycharm",
                   "com.jetbrains.intellij", "com.apple.dt.Xcode"):
        assert profile_for(bundle) == "terminal", bundle


def test_shipped_defaults_cover_mac_chat_apps():
    for bundle in ("com.tinyspeck.slackmacgap", "com.hnc.Discord",
                   "com.microsoft.teams2", "net.whatsapp.WhatsApp",
                   "ru.keepcoder.Telegram", "org.whispersystems.signal-desktop"):
        assert profile_for(bundle) == "chat", bundle


def test_shipped_defaults_cover_mac_email_apps():
    for bundle in ("com.apple.mail", "com.microsoft.Outlook",
                   "org.mozilla.thunderbird"):
        assert profile_for(bundle) == "email", bundle


def test_windows_shipped_defaults_are_unchanged():
    """Windows parity is a hard constraint of this port."""
    assert profile_for("WindowsTerminal.exe") == "terminal"
    assert profile_for("powershell.exe") == "terminal"
    assert profile_for("Code.exe") == "terminal"
    assert profile_for("pycharm64.exe") == "terminal"
    assert profile_for("Discord.exe") == "chat"
    assert profile_for("OUTLOOK.EXE") == "email"
    assert appcontext.resolve_profile("Notepad.exe",
                                      DEFAULTS)["force_paste"] is True


def test_the_notepad_force_paste_quirk_stays_windows_only():
    """force_paste exists for Windows 11 Notepad dropping typed keys. No mac
    app has that bug, so no bundle id belongs in that profile."""
    for pat in DEFAULTS["notepad"]["match"]:
        assert pat.lower().endswith(".exe"), pat


# ---- asking the platform the right question ---------------------------------

def test_foreground_app_returns_none_on_an_unknown_platform():
    assert appcontext.foreground_app(system="Linux") is None


def test_foreground_app_on_macos_reports_the_bundle_identifier():
    """The mac lookup is injected, so the decision is testable from Windows."""
    called = []

    def fake_bundle():
        called.append(True)
        return "com.apple.Terminal"

    got = appcontext.foreground_app(system="Darwin", _mac_bundle_id=fake_bundle)
    assert got == "com.apple.Terminal"
    assert called


def test_foreground_app_on_windows_reports_the_executable_name():
    got = appcontext.foreground_app(system="Windows",
                                    _win_exe=lambda: "cmd.exe")
    assert got == "cmd.exe"


def test_a_failed_lookup_is_no_profile_rather_than_a_crash():
    """A dictation must never be lost because focus could not be identified."""
    def boom():
        raise RuntimeError("no accessibility grant")

    assert appcontext.foreground_app(system="Darwin",
                                     _mac_bundle_id=boom) is None
