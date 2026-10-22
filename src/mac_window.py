"""Keeping the recording overlay on screen on macOS (ticket 08).

Dictate is menu-bar-only on macOS, which means it is *never* the frontmost
application. That collides with two macOS window rules at once: a `Qt.Tool`
window hides whenever its application deactivates, and a window below the
full-screen level is covered by a full-screen Space. The overlay would
therefore disappear at the exact moment it is needed — while the user is
dictating into some other app.

Qt exposes no API for either rule. The fix lives on the NSWindow behind the
widget, and `tests/probe_overlay_mac.py` measured on a real screen which
calls are load-bearing: level 8 -> 101 (popUpMenu), collectionBehavior
258 -> 337, `hidesOnDeactivate` off, and mouse events ignored so the overlay
never eats a click meant for the document underneath.

The seams are pure — the platform and the objc lookup are arguments — so the
decisions are testable from Windows, and the AppKit calls themselves are
verified by the probe rather than mocked into a false pass:

    wants_floating_overlay(system)      -> bool
    native_window(widget, system=)      -> the NSWindow, or None
    float_over_everything(nsw, system=) -> True if the treatment was applied
    pin_overlay(widget, system=)        -> the one call the overlay makes

Nothing here raises. Without pyobjc the overlay reverts to Qt's behaviour —
visible while Dictate is frontmost, gone otherwise — which is a degraded
overlay, not a dead app.
"""

import logging
import platform

log = logging.getLogger("dictate.mac_window")

MACOS = "Darwin"

# NSWindow levels. popUpMenu is above the full-screen level and above the
# floating panels other apps use, which is what the probe needed to stay
# visible over a full-screen Space.
LEVEL_POPUP_MENU = 101

# NSWindowCollectionBehavior bits. Hard-coded rather than read from AppKit so
# the numbers stay testable on a machine with no pyobjc — and so a change to
# the measured 337 is a visible change to a verified behaviour.
CAN_JOIN_ALL_SPACES = 1 << 0        # follow the user between Spaces
STATIONARY = 1 << 4                 # do not slide with a Space switch
IGNORES_CYCLE = 1 << 6              # stay out of Cmd+` window cycling
FULLSCREEN_AUXILIARY = 1 << 8       # allowed over another app's full screen

OVERLAY_COLLECTION_BEHAVIOR = (
    CAN_JOIN_ALL_SPACES | STATIONARY | IGNORES_CYCLE | FULLSCREEN_AUXILIARY
)


def wants_floating_overlay(system: str | None = None) -> bool:
    """Only macOS has the deactivation rule. Windows overlay is unchanged."""
    return (system or platform.system()) == MACOS


def _objc_object_default(c_void_p):
    import objc

    return objc.objc_object(c_void_p=c_void_p)


def native_window(widget, system: str | None = None, _objc_object=None):
    """The NSWindow backing a Qt widget, via its `winId()`.

    Returns None when there is nothing to reach: off macOS, before the widget
    has a native handle, or when pyobjc is not installed. A missing window is
    a reported miss — the caller degrades — never an exception on show.
    """
    if not wants_floating_overlay(system):
        return None
    try:
        view = (_objc_object or _objc_object_default)(c_void_p=widget.winId())
        return view.window() if view is not None else None
    except Exception:
        log.debug("no NSWindow behind the overlay widget yet", exc_info=True)
        return None


def float_over_everything(nsw, system: str | None = None) -> bool:
    """Pin an NSWindow above everything, across Spaces, ignoring focus.

    True when the treatment was applied. False is the honest answer for a
    platform that does not need it, a window that is not there yet, and an
    AppKit that refused — all three leave a working app.
    """
    if not wants_floating_overlay(system) or nsw is None:
        return False
    try:
        nsw.setLevel_(LEVEL_POPUP_MENU)
        nsw.setCollectionBehavior_(OVERLAY_COLLECTION_BEHAVIOR)
        nsw.setHidesOnDeactivate_(False)
        nsw.setIgnoresMouseEvents_(True)
    except Exception:
        log.warning("could not pin the overlay window — it will hide when "
                    "another app takes focus", exc_info=True)
        return False
    return True


def frontmost_app(system: str | None = None):
    """The NSRunningApplication that has focus right now, or None.

    Taken BEFORE the overlay is shown, so it can be given focus back after.
    """
    if not wants_floating_overlay(system):
        return None
    try:
        import AppKit

        return AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        log.debug("could not read the frontmost app", exc_info=True)
        return None


def give_focus_back(prev, system: str | None = None, _is_active=None,
                    _own_pid=None) -> bool:
    """Re-activate the app the user was in, if showing the overlay stole it.

    Measured on macOS 26: even as an accessory app, with WA_ShowWithoutActivating
    set and QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM on, Qt's show() of
    the overlay makes Dictate the active application and the frontmost app
    reads as None. Every keystroke Injection posts then goes to Dictate's own
    focus-less window, so the words are transcribed and never typed anywhere
    — with no error, because the events were delivered. The only thing that
    put text into Terminal again was activating the previous app afterwards.

    True when the previous app was asked to come back. False when there is
    nothing to do (not macOS, nothing recorded, Dictate is not active, or the
    previous app is Dictate itself) or AppKit refused. Never raises.
    """
    if not wants_floating_overlay(system) or prev is None:
        return False
    try:
        import os

        import AppKit

        active = (_is_active or (lambda: bool(AppKit.NSApp.isActive())))()
        if prev.processIdentifier() == (_own_pid or os.getpid()):
            return False
        # Re-activate even when Dictate does not (yet) read as active: Qt
        # activates the app a beat AFTER show() returns, so a synchronous
        # isActive() check right after show() answers False and the theft
        # happens anyway. Activating an app that already has focus is a no-op.
        ok = bool(prev.activateWithOptions_(
            AppKit.NSApplicationActivateIgnoringOtherApps))
        log.info("overlay shown (Dictate active=%s) — focus handed to %s (%s)",
                 active, prev.bundleIdentifier(), "ok" if ok else "refused")
        return ok
    except Exception:
        log.warning("could not give focus back to the previous app — typed "
                    "text may not reach it", exc_info=True)
        return False


def pin_overlay(widget, system: str | None = None, _objc_object=None) -> bool:
    """Resolve a widget's NSWindow and pin it. The overlay's only entry point.

    Safe to call on every show: the calls are idempotent, and a widget whose
    native window was recreated between shows needs them again.
    """
    if not wants_floating_overlay(system):
        return False
    return float_over_everything(
        native_window(widget, system=system, _objc_object=_objc_object),
        system=system,
    )
