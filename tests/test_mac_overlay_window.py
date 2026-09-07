"""The recording overlay has to stay on screen while you dictate elsewhere.

A menu-bar-only app is never the frontmost app, and on macOS a `Qt.Tool`
window hides whenever its application deactivates — so the overlay would
vanish at the exact moment it is needed. Qt exposes no API for the fix; it
lives on the NSWindow, and `tests/probe_overlay_mac.py` measured which four
calls are load-bearing (level 8 -> 101, collectionBehavior 258 -> 337).

What is testable from either platform is the *decision*: whether this
platform wants the treatment at all, which level and behaviour it asks for,
and that a machine without pyobjc degrades to a working app with a
short-lived overlay rather than a traceback on show. The AppKit calls
themselves are a seam, and the probe is what verifies them for real.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mac_window  # noqa: E402


class FakeNSWindow:
    """Records what the port asked of the real window."""

    def __init__(self):
        self.level = None
        self.behavior = None
        self.hides_on_deactivate = None
        self.ignores_mouse = None

    def setLevel_(self, level):
        self.level = level

    def setCollectionBehavior_(self, behavior):
        self.behavior = behavior

    def setHidesOnDeactivate_(self, flag):
        self.hides_on_deactivate = flag

    def setIgnoresMouseEvents_(self, flag):
        self.ignores_mouse = flag


# ---- who needs the treatment ------------------------------------------------


def test_macos_needs_the_overlay_pinned():
    assert mac_window.wants_floating_overlay("Darwin") is True


def test_windows_overlay_behaviour_is_unchanged():
    """The Windows overlay already floats over other apps; touching it here
    would be a port breaking the platform it started on."""
    assert mac_window.wants_floating_overlay("Windows") is False


def test_linux_is_left_alone():
    assert mac_window.wants_floating_overlay("Linux") is False


# ---- what it asks for -------------------------------------------------------


def test_the_overlay_is_raised_above_ordinary_windows():
    """Qt leaves it at modalPanel (8), which a full-screen app covers.
    popUpMenu (101) is the level the probe measured as sufficient."""
    win = FakeNSWindow()
    assert mac_window.float_over_everything(win, system="Darwin") is True
    assert win.level == mac_window.LEVEL_POPUP_MENU


def test_the_overlay_joins_every_space_including_full_screen():
    win = FakeNSWindow()
    mac_window.float_over_everything(win, system="Darwin")
    assert win.behavior & mac_window.CAN_JOIN_ALL_SPACES
    assert win.behavior & mac_window.FULLSCREEN_AUXILIARY


def test_the_overlay_does_not_move_with_spaces_or_join_the_window_cycle():
    win = FakeNSWindow()
    mac_window.float_over_everything(win, system="Darwin")
    assert win.behavior & mac_window.STATIONARY
    assert win.behavior & mac_window.IGNORES_CYCLE


def test_the_measured_collection_behaviour_is_the_one_applied():
    """337 is what the probe reported after the fix stuck; a change to this
    number is a change to behaviour the probe verified on a real screen."""
    win = FakeNSWindow()
    mac_window.float_over_everything(win, system="Darwin")
    assert win.behavior == 337


def test_the_overlay_survives_the_app_losing_focus():
    """The whole bug: an accessory app is never frontmost, and a Qt.Tool
    window hides on deactivation."""
    win = FakeNSWindow()
    mac_window.float_over_everything(win, system="Darwin")
    assert win.hides_on_deactivate is False


def test_the_overlay_never_swallows_a_click():
    """It sits over whatever the user is typing into; a click that lands on
    the overlay instead of their document is worse than no overlay."""
    win = FakeNSWindow()
    mac_window.float_over_everything(win, system="Darwin")
    assert win.ignores_mouse is True


# ---- degrading -------------------------------------------------------------


def test_nothing_is_touched_off_macos():
    win = FakeNSWindow()
    assert mac_window.float_over_everything(win, system="Windows") is False
    assert win.level is None
    assert win.behavior is None


def test_no_native_window_is_a_reported_miss_not_a_crash():
    """`winId()` can hand back something with no NSWindow behind it before
    the widget is really on screen."""
    assert mac_window.float_over_everything(None, system="Darwin") is False


def test_a_broken_appkit_leaves_a_working_app():
    """Without pyobjc the overlay reverts to Qt's behaviour — visible while
    Dictate is frontmost, gone otherwise. Degraded, not dead."""
    class Hostile:
        def setLevel_(self, _level):
            raise RuntimeError("pyobjc missing")

    assert mac_window.float_over_everything(Hostile(), system="Darwin") is False


# ---- resolving the NSWindow from a Qt widget --------------------------------


def test_the_native_window_is_reached_through_the_widgets_win_id():
    """Qt has no API for any of this, so the port goes through winId() to the
    NSView and asks it for its window."""
    win = FakeNSWindow()

    class View:
        def window(self):
            return win

    seen = []

    def fake_objc_object(c_void_p):
        seen.append(c_void_p)
        return View()

    class Widget:
        def winId(self):
            return 4242

    got = mac_window.native_window(Widget(), system="Darwin",
                                   _objc_object=fake_objc_object)
    assert got is win
    assert seen == [4242]


def test_the_native_window_is_never_looked_up_off_macos():
    def explode(c_void_p):
        raise AssertionError("no NSWindow on this platform")

    class Widget:
        def winId(self):
            return 1

    assert mac_window.native_window(Widget(), system="Windows",
                                    _objc_object=explode) is None


def test_a_widget_with_no_native_handle_yet_resolves_to_nothing():
    class NotShownYet:
        def winId(self):
            raise RuntimeError("no window handle")

    assert mac_window.native_window(NotShownYet(), system="Darwin",
                                    _objc_object=lambda c_void_p: None) is None


# ---- the one call the overlay makes ----------------------------------------


def test_pinning_a_widget_applies_the_treatment_to_its_native_window():
    win = FakeNSWindow()

    class Widget:
        def winId(self):
            return 7

    class View:
        def window(self):
            return win

    assert mac_window.pin_overlay(
        Widget(), system="Darwin",
        _objc_object=lambda c_void_p: View()) is True
    assert win.level == mac_window.LEVEL_POPUP_MENU
    assert win.hides_on_deactivate is False


def test_pinning_a_widget_off_macos_is_a_no_op():
    class Widget:
        def winId(self):
            raise AssertionError("winId is not asked for off macOS")

    assert mac_window.pin_overlay(Widget(), system="Windows") is False
