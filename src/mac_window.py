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
