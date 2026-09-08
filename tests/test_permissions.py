"""Accessibility Permission preflight.

Without the grant, macOS drops posted events AND tap observations silently:
the Trigger never fires and Injection does nothing, with no exception
anywhere. The app has to say so itself.

The seams are pure so both platforms' answers are testable from either:

    needs_accessibility_prompt(system, trusted) -> bool
    settings_pane_url()                         -> the x-apple.systempreferences URL
    permission_summary(system, trusted)         -> the line that goes in the log
"""
import os
import platform
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import permissions  # noqa: E402

IS_MAC = platform.system() == "Darwin"


# ---- when to prompt --------------------------------------------------------


def test_macos_without_the_grant_prompts():
    assert permissions.needs_accessibility_prompt("Darwin", trusted=False) is True


def test_macos_with_the_grant_is_silent():
    assert permissions.needs_accessibility_prompt("Darwin", trusted=True) is False


def test_windows_never_prompts_whatever_the_probe_says():
    """There is no such permission on Windows; the check is a no-op there."""
    assert permissions.needs_accessibility_prompt("Windows", trusted=False) is False
    assert permissions.needs_accessibility_prompt("Windows", trusted=True) is False


def test_linux_never_prompts():
    assert permissions.needs_accessibility_prompt("Linux", trusted=False) is False


# ---- the pane it opens -----------------------------------------------------


def test_the_settings_url_targets_the_accessibility_pane():
    url = permissions.settings_pane_url()
    assert url.startswith("x-apple.systempreferences:")
    assert "Privacy_Accessibility" in url


# ---- what the log says -----------------------------------------------------


def test_the_log_line_names_the_permission_and_its_state():
    granted = permissions.permission_summary("Darwin", trusted=True)
    missing = permissions.permission_summary("Darwin", trusted=False)
    assert "accessibility" in granted.lower()
    assert "accessibility" in missing.lower()
    assert granted != missing


def test_the_log_line_on_windows_says_the_check_does_not_apply():
    line = permissions.permission_summary("Windows", trusted=False)
    assert "not applicable" in line.lower() or "n/a" in line.lower()


# ---- the real probe --------------------------------------------------------


def test_the_probe_returns_a_bool_on_any_platform():
    """Never raises, whatever is or isn't installed — a permission check that
    crashes the app is worse than the permission being missing."""
    assert isinstance(permissions.accessibility_trusted(), bool)


def test_the_probe_agrees_with_the_system_on_macos():
    """AXIsProcessTrusted is a HIServices symbol (re-exported by
    ApplicationServices), not a Quartz one — asking Quartz for it raises."""
    import pytest

    if not IS_MAC:
        pytest.skip("macOS only")
    # pyobjc is not installed on the CI runner (the suite there is
    # pure-python). Without it the probe's own fail-safe answer is False, and
    # there is nothing to compare it against — skip rather than fail on an
    # absent framework that says nothing about this code.
    ApplicationServices = pytest.importorskip(
        "ApplicationServices", reason="pyobjc not installed on this runner")

    assert permissions.accessibility_trusted() == bool(
        ApplicationServices.AXIsProcessTrusted())


def test_windows_probe_reports_trusted_so_nothing_is_gated():
    assert permissions.accessibility_trusted(system="Windows") is True


# ---- the startup decision, end to end --------------------------------------


def test_preflight_reports_no_problem_when_the_grant_is_present():
    state = permissions.preflight(system="Darwin", trusted=True)
    assert state.ok is True
    assert state.should_prompt is False


def test_preflight_reports_the_problem_with_a_message_and_a_url():
    state = permissions.preflight(system="Darwin", trusted=False)
    assert state.ok is False
    assert state.should_prompt is True
    assert "Accessibility" in state.message
    assert state.url == permissions.settings_pane_url()


def test_preflight_on_windows_is_ok_and_quiet():
    state = permissions.preflight(system="Windows", trusted=False)
    assert state.ok is True
    assert state.should_prompt is False


# ---- opening the pane ------------------------------------------------------


def test_opening_the_pane_hands_the_url_to_the_system_opener():
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv

    assert permissions.open_settings_pane(system="Darwin", _run=fake_run) is True
    assert seen["argv"][0] == "open"
    assert seen["argv"][-1] == permissions.settings_pane_url()


def test_opening_the_pane_is_a_no_op_off_macos():
    def explode(argv, **kw):
        raise AssertionError("nothing to open on this platform")

    assert permissions.open_settings_pane(system="Windows", _run=explode) is False


def test_a_failed_open_is_reported_not_raised():
    """The dialog is already the fallback: it names the pane in words, so a
    button that cannot launch Settings must not take the app down with it."""
    def fail(argv, **kw):
        raise OSError("no such binary")

    assert permissions.open_settings_pane(system="Darwin", _run=fail) is False


# ---- startup wiring --------------------------------------------------------


def test_startup_logs_the_state_and_says_nothing_else_when_granted():
    lines = []
    shown = []
    ok = permissions.run_preflight(system="Darwin", trusted=True,
                                   ask=lambda state: shown.append(state) or True,
                                   log_line=lines.append)
    assert ok is True
    assert shown == []                       # no dialog when the grant is there
    assert any("granted" in ln for ln in lines)


def test_startup_shows_the_dialog_and_opens_the_pane_when_accepted():
    shown = []
    opened = []
    ok = permissions.run_preflight(
        system="Darwin", trusted=False,
        ask=lambda state: shown.append(state) or True,
        opener=lambda: opened.append(True) or True,
        log_line=lambda _ln: None)
    assert ok is False
    assert len(shown) == 1
    assert shown[0].message == permissions.PROMPT_MESSAGE
    assert opened == [True]


def test_declining_the_dialog_does_not_open_the_pane():
    """Dictate keeps running either way — the user may want to grant it later,
    and a hard exit would strand them with no window to try again from."""
    opened = []
    ok = permissions.run_preflight(
        system="Darwin", trusted=False,
        ask=lambda _state: False,
        opener=lambda: opened.append(True) or True,
        log_line=lambda _ln: None)
    assert ok is False
    assert opened == []


def test_startup_never_raises_when_the_dialog_itself_fails():
    """No Qt, no display, a theming crash — none of it may stop the app from
    starting, because the app still works for anyone who has the grant."""
    def broken(_state):
        raise RuntimeError("no display")

    assert permissions.run_preflight(system="Darwin", trusted=False,
                                     ask=broken,
                                     log_line=lambda _ln: None) is False


def test_startup_on_windows_asks_nothing_and_still_logs():
    lines = []

    def explode(_state):
        raise AssertionError("no such permission on Windows")

    assert permissions.run_preflight(system="Windows", trusted=False,
                                     ask=explode,
                                     log_line=lines.append) is True
    assert any("not applicable" in ln for ln in lines)


def test_the_message_explains_what_breaks_without_the_grant():
    """A dialog that only says 'permission needed' teaches nothing."""
    msg = permissions.preflight(system="Darwin", trusted=False).message
    low = msg.lower()
    assert "hold" in low or "key" in low          # the Trigger
    assert "type" in low or "text" in low         # Injection
