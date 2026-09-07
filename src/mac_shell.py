"""Menu-bar-only on macOS, and a Quit that actually quits (ticket 07).

On Windows Dictate is a tray app with no window. macOS has the same shape —
a menu bar extra — but only if the process asks for the *accessory*
activation policy. Without that ask, a Python/Qt process is a regular app:
Dock icon, Cmd+Tab entry, and a menu bar that belongs to a window that does
not exist.

It is applied at startup rather than left to the bundle's `LSUIElement`, so
a run from source behaves identically to the shipped `.app`. The bundle
declares it too; the two agreeing is the point, not a duplication.

The consequence lives here as well: with no Dock icon and no window, the
tray menu's Quit is the ONLY way out. A process the Qt event loop fails to
unwind is then unkillable except from Activity Monitor, so the quit path
arms a watchdog that ends it for real.

The seams are pure — the platform and the AppKit call are arguments — so
both platforms' answers are testable from either:

    wants_menu_bar_only(system)   -> bool
    apply_menu_bar_only(system=)  -> True if the policy was accepted
    arm_exit_watchdog(delay_ms=)  -> schedule the last-resort exit
"""

import logging
import platform

log = logging.getLogger("dictate.mac_shell")

MACOS = "Darwin"

# NSApplicationActivationPolicyAccessory. The app runs, shows a menu bar
# extra, and is never in the Dock or Cmd+Tab. Hard-coded rather than read
# from AppKit so the value is testable with no pyobjc present.
ACTIVATION_POLICY_ACCESSORY = 1

# How long the normal shutdown gets before the watchdog stops being polite.
# Long enough for the event loop to unwind and daemon threads to be dropped,
# short enough that a user who chose Quit is not left staring at a menu bar
# icon that no longer responds.
EXIT_GRACE_MS = 1500


def wants_menu_bar_only(system: str | None = None) -> bool:
    """Only macOS has the concept. Windows tray behaviour is unchanged."""
    return (system or platform.system()) == MACOS


def _set_activation_policy(policy: int) -> bool:
    import AppKit

    return bool(AppKit.NSApp.setActivationPolicy_(policy))


def apply_menu_bar_only(system: str | None = None, _set_policy=None) -> bool:
    """Hide from the Dock and Cmd+Tab. True if the policy was accepted.

    Must run after QApplication exists — NSApp is the shared application
    object Qt creates — and before the tray is shown, so the icon never
    appears in the Dock even briefly.

    Failure is reported, never raised: AppKit returns False if the app is
    not in a state to change policy, and a Dock icon that stays put is a
    cosmetic problem where a traceback at startup is a dead app.
    """
    if not wants_menu_bar_only(system):
        return False
    try:
        ok = bool((_set_policy or _set_activation_policy)(
            ACTIVATION_POLICY_ACCESSORY))
    except Exception:
        log.warning("could not set the accessory activation policy",
                    exc_info=True)
        return False
    if not ok:
        log.warning("accessory activation policy refused — the Dock icon "
                    "will stay")
    else:
        log.info("menu-bar-only: accessory activation policy applied")
    return ok


def _qt_schedule(delay_ms: int, fn):
    from PySide6.QtCore import QTimer

    QTimer.singleShot(delay_ms, fn)


def _hard_exit(code: int):
    """os._exit, not sys.exit: the point is to end a process the normal
    unwinding could not, and sys.exit is just an exception the stuck thread
    never sees."""
    import os

    os._exit(code)


def arm_exit_watchdog(delay_ms: int = EXIT_GRACE_MS, _schedule=None,
                      _exit=None):
    """Schedule a last-resort exit, in case the event loop does not end.

    The normal path — `app.quit()` unwinding the loop — is still what ends
    the process almost always; this only fires when a non-daemon thread or a
    stuck native handle leaves it alive. With no Dock icon and no window,
    that leftover is unkillable except from Activity Monitor.

    Never raises: this is called from the quit path, which has to complete
    even when Qt is already torn down, or the act of quitting is itself what
    hangs.
    """
    try:
        (_schedule or _qt_schedule)(delay_ms, lambda: (_exit or _hard_exit)(0))
    except Exception:
        log.debug("could not arm the exit watchdog", exc_info=True)
