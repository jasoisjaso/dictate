"""Menu-bar-only on macOS, and a Quit that actually quits.

On macOS Dictate is what it already is on Windows: a tray app with no window.
That means no Dock icon and no Cmd+Tab entry — the accessory activation
policy — applied at startup so a run from source behaves identically to the
bundle later, rather than the two differing in the one behaviour being
verified.

The consequence is the second half of this file: with no Dock icon and no
window, the tray menu's Quit is the ONLY way out, so it has to genuinely end
the process rather than leave one behind with a dead menu bar icon.

The seams are pure — the platform and the AppKit call are arguments — so both
platforms' answers are testable from either.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mac_shell  # noqa: E402


# ---- who hides from the Dock -----------------------------------------------


def test_macos_wants_to_be_menu_bar_only():
    assert mac_shell.wants_menu_bar_only("Darwin") is True


def test_windows_does_not_have_the_concept():
    """Windows tray behaviour is unchanged: nothing to apply, nothing to undo."""
    assert mac_shell.wants_menu_bar_only("Windows") is False


def test_linux_does_not_have_the_concept():
    assert mac_shell.wants_menu_bar_only("Linux") is False


# ---- applying it -----------------------------------------------------------


def test_applying_on_macos_asks_for_the_accessory_policy():
    seen = []
    assert mac_shell.apply_menu_bar_only(
        system="Darwin", _set_policy=lambda p: seen.append(p) or True) is True
    assert seen == [mac_shell.ACTIVATION_POLICY_ACCESSORY]


def test_a_bundle_already_in_the_accessory_policy_counts_as_applied():
    """The .app's LSUIElement puts the process in the accessory policy before
    a line of Python runs, and AppKit answers a no-op change with False. The
    startup call must not read that as a refusal: the bundle logged
    "accessory activation policy refused" while having no Dock icon at all.
    """
    assert mac_shell.apply_menu_bar_only(
        system="Darwin",
        _set_policy=lambda _p: False,
        _get_policy=lambda: mac_shell.ACTIVATION_POLICY_ACCESSORY) is True


def test_a_refusal_that_leaves_a_regular_app_is_still_a_refusal():
    """A source run has the regular policy until we change it. If that change
    fails the Dock icon really does stay, and the log has to say so."""
    assert mac_shell.apply_menu_bar_only(
        system="Darwin",
        _set_policy=lambda _p: False,
        _get_policy=lambda: mac_shell.ACTIVATION_POLICY_REGULAR) is False


def test_an_unreadable_policy_falls_back_to_what_appkit_returned():
    """No pyobjc, or a policy getter that raises: trust the setter's own
    answer rather than inventing a success."""
    def fail():
        raise RuntimeError("pyobjc missing")

    assert mac_shell.apply_menu_bar_only(
        system="Darwin", _set_policy=lambda _p: True, _get_policy=fail) is True
    assert mac_shell.apply_menu_bar_only(
        system="Darwin", _set_policy=lambda _p: False,
        _get_policy=fail) is False


def test_applying_off_macos_touches_nothing():
    def explode(_policy):
        raise AssertionError("no activation policy on this platform")

    assert mac_shell.apply_menu_bar_only(system="Windows",
                                         _set_policy=explode) is False


def test_a_refused_policy_change_is_reported_not_raised():
    """AppKit returns False if the app is not in a state to change policy.
    A Dock icon that stays put is a cosmetic problem; a traceback at startup
    is a dead app."""
    assert mac_shell.apply_menu_bar_only(system="Darwin",
                                         _set_policy=lambda _p: False) is False


def test_a_broken_appkit_does_not_stop_startup():
    def fail(_policy):
        raise RuntimeError("pyobjc missing")

    assert mac_shell.apply_menu_bar_only(system="Darwin",
                                         _set_policy=fail) is False


# ---- Quit is the only way out ----------------------------------------------


def test_the_watchdog_is_scheduled_with_a_grace_period():
    scheduled = []
    mac_shell.arm_exit_watchdog(delay_ms=1500,
                                _schedule=lambda ms, fn: scheduled.append((ms, fn)),
                                _exit=lambda code: None)
    assert len(scheduled) == 1
    assert scheduled[0][0] == 1500


def test_nothing_exits_before_the_grace_period_elapses():
    """The normal path — the Qt event loop unwinding on its own — must be the
    one that ends the process, so the watchdog fires only if that fails."""
    exits = []
    mac_shell.arm_exit_watchdog(delay_ms=1500,
                                _schedule=lambda _ms, _fn: None,
                                _exit=exits.append)
    assert exits == []


def test_the_watchdog_kills_a_process_the_event_loop_left_behind():
    """A non-daemon thread or a stuck native handle can leave the process
    alive with no window and no Dock icon — unkillable except from Activity
    Monitor. That is the failure this exists to prevent."""
    fired = []
    exits = []
    mac_shell.arm_exit_watchdog(delay_ms=1500,
                                _schedule=lambda _ms, fn: fired.append(fn),
                                _exit=exits.append)
    fired[0]()
    assert exits == [0]


def test_arming_the_watchdog_never_raises_without_qt():
    """Called from the quit path, which must complete even if Qt is already
    torn down — otherwise the very act of quitting is what hangs."""
    def no_qt(_ms, _fn):
        raise RuntimeError("QApplication already destroyed")

    mac_shell.arm_exit_watchdog(delay_ms=1500, _schedule=no_qt,
                                _exit=lambda _c: None)
