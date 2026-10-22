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

# NSApplicationActivationPolicy values. Hard-coded rather than read from
# AppKit so they are testable with no pyobjc present.
ACTIVATION_POLICY_REGULAR = 0    # Dock icon, Cmd+Tab entry — what a plain
                                 # source run starts as
ACTIVATION_POLICY_ACCESSORY = 1  # menu bar extra only

# How long the normal shutdown gets before the watchdog stops being polite.
# Long enough for the event loop to unwind and daemon threads to be dropped,
# short enough that a user who chose Quit is not left staring at a menu bar
# icon that no longer responds.
EXIT_GRACE_MS = 1500


def wants_menu_bar_only(system: str | None = None) -> bool:
    """Only macOS has the concept. Windows tray behaviour is unchanged."""
    return (system or platform.system()) == MACOS


def _shared_app():
    """The one NSApplication. sharedApplication() creates it if Qt has not
    yet, and Qt adopts an existing one — so this works before or after
    QApplication. NSApp alone is None before either exists."""
    import AppKit

    return AppKit.NSApplication.sharedApplication()


def _set_activation_policy(policy: int) -> bool:
    return bool(_shared_app().setActivationPolicy_(policy))


def _get_activation_policy() -> int:
    return int(_shared_app().activationPolicy())


def apply_menu_bar_only(system: str | None = None, _set_policy=None,
                        _get_policy=None) -> bool:
    """Hide from the Dock and Cmd+Tab. True if the app ends up an accessory.

    Must run after QApplication exists — NSApp is the shared application
    object Qt creates — and before the tray is shown, so the icon never
    appears in the Dock even briefly.

    The setter's return value alone is not the answer. The shipped bundle
    declares `LSUIElement`, so the process is *already* an accessory before
    any Python runs, and AppKit answers that no-op change with False. Reading
    it as a refusal made the bundle log "the Dock icon will stay" while
    having no Dock icon at all. So a False is checked against the policy the
    app actually has: what matters is the end state, not whether this call
    was the thing that produced it.

    Failure is reported, never raised: a Dock icon that stays put is a
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
        try:
            current = (_get_policy or _get_activation_policy)()
        except Exception:
            # No pyobjc, or the getter moved: trust the setter's own answer
            # rather than inventing a success.
            log.debug("could not read the activation policy", exc_info=True)
            current = None
        if current == ACTIVATION_POLICY_ACCESSORY:
            log.info("menu-bar-only: already an accessory app (LSUIElement)")
            return True
        log.warning("accessory activation policy refused — the Dock icon "
                    "will stay")
        return False
    log.info("menu-bar-only: accessory activation policy applied")
    return True


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
