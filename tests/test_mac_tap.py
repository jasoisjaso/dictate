"""The two guards that stop a Take running forever on macOS.

A Take ends on the push-to-talk RELEASE. So a release that never arrives is
not a lost hotkey — it strands the app in RECORDING with no way out but Quit,
which is exactly what the first mac build did.

Two independent causes, two guards, tested separately:

  1. macOS disables the event tap (slow callback, or heavy user input) and
     pynput never re-enables it — a real gap in its darwin backend, which
     calls CGEventTapEnable exactly once at startup and has no branch for
     either disable notification. `install()` closes it.
  2. Anything else that drops the release event. `release_was_missed()` skips
     the event stream entirely and asks macOS for the hardware key state.

Both seams are pure — the platform, the tap enabler and the key-state probe
are all arguments — so every macOS answer is testable from Windows and from a
CI runner with no pyobjc.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mac_tap  # noqa: E402


# ---- which platform needs any of this --------------------------------------


def test_only_macos_wants_the_watchdog():
    assert mac_tap.wants_tap_watchdog("Darwin") is True
    assert mac_tap.wants_tap_watchdog("Windows") is False
    assert mac_tap.wants_tap_watchdog("Linux") is False


def test_installing_off_macos_does_nothing():
    """A Windows run must not patch pynput at all."""
    def explode(*_a, **_k):
        raise AssertionError("no event taps on this platform")

    assert mac_tap.install(system="Windows", _mixin=explode) is False


# ---- reading the disable notification --------------------------------------


def test_the_two_disable_notifications_are_recognised():
    assert mac_tap.disable_reason(mac_tap.TAP_DISABLED_BY_TIMEOUT) == "timeout"
    assert mac_tap.disable_reason(
        mac_tap.TAP_DISABLED_BY_USER_INPUT) == "user_input"


def test_an_ordinary_event_type_is_not_a_disable():
    """Every real CGEventType must fall through to pynput untouched."""
    for event_type in (0, 1, 10, 12, 29):   # keyDown, keyUp, flagsChanged...
        assert mac_tap.disable_reason(event_type) is None


def test_a_junk_event_type_is_not_a_disable():
    assert mac_tap.disable_reason(None) is None
    assert mac_tap.disable_reason("flagsChanged") is None


# ---- the watchdog re-enables the tap ---------------------------------------


class _FakeMixin:
    """Stands in for pynput._util.darwin.ListenerMixin."""

    def __init__(self):
        self.handled = []

    def _create_event_tap(self):
        return "the-tap"

    def _handler(self, proxy, event_type, event, refcon):
        self.handled.append(event_type)
        return "passed-through"


def _patched():
    """A patched fake class plus the list of (tap, on) enable calls."""
    enabled = []
    cls = type("Mixin", (_FakeMixin,), {})
    assert mac_tap.install(system="Darwin", _mixin=cls,
                           _enable=lambda tap, on: enabled.append((tap, on)))
    return cls, enabled


def test_a_disabled_tap_is_switched_back_on():
    """The regression: pynput leaves it off, so every key dies silently."""
    cls, enabled = _patched()
    listener = cls()
    listener._create_event_tap()
    listener._handler(None, mac_tap.TAP_DISABLED_BY_TIMEOUT, None, None)
    assert enabled == [("the-tap", True)]


def test_a_tap_disabled_by_user_input_is_also_re_enabled():
    cls, enabled = _patched()
    listener = cls()
    listener._create_event_tap()
    listener._handler(None, mac_tap.TAP_DISABLED_BY_USER_INPUT, None, None)
    assert enabled == [("the-tap", True)]


def test_a_disable_notification_never_reaches_pynputs_handler():
    """It is not an event: pynput would read key flags off a non-event."""
    cls, _ = _patched()
    listener = cls()
    listener._create_event_tap()
    listener._handler(None, mac_tap.TAP_DISABLED_BY_TIMEOUT, None, None)
    assert listener.handled == []


def test_ordinary_events_still_go_to_pynput_untouched():
    cls, enabled = _patched()
    listener = cls()
    listener._create_event_tap()
    assert listener._handler(None, 10, "event", None) == "passed-through"
    assert listener.handled == [10]
    assert enabled == []


def test_installing_twice_does_not_wrap_the_wrapper():
    cls, enabled = _patched()
    assert mac_tap.install(system="Darwin", _mixin=cls,
                           _enable=lambda tap, on: enabled.append("second"))
    listener = cls()
    listener._create_event_tap()
    listener._handler(None, mac_tap.TAP_DISABLED_BY_TIMEOUT, None, None)
    assert enabled == [("the-tap", True)]


# ---- the hardware key state ------------------------------------------------


def test_a_key_the_hardware_says_is_down_reads_as_down():
    assert mac_tap.key_is_down("alt_r", system="Darwin",
                               _state=lambda _kc: True) is True


def test_right_option_resolves_to_its_carbon_keycode():
    assert mac_tap.virtual_keycode("alt_r") == 0x3D
    assert mac_tap.virtual_keycode("ctrl_r") == 0x3E
    assert mac_tap.virtual_keycode("f8") == 0x64


def test_an_unknown_key_name_has_no_keycode():
    assert mac_tap.virtual_keycode("scroll_lock") is None
    assert mac_tap.virtual_keycode("") is None


def test_every_shipped_mac_default_can_be_polled():
    """A default we cannot poll is a default the guard cannot rescue."""
    import hotkeys

    for action, name in hotkeys.defaults_for("Darwin").items():
        if not name:
            continue
        assert mac_tap.virtual_keycode(name) is not None, (action, name)


# ---- "don't know" is never "not held" --------------------------------------
# A False ends a Take. Every unanswerable question must return None instead,
# or the guard cuts the user off mid-sentence.


def test_off_macos_the_answer_is_dont_know():
    assert mac_tap.key_is_down("alt_r", system="Windows",
                               _state=lambda _kc: True) is None


def test_an_unpollable_key_is_dont_know():
    assert mac_tap.key_is_down("scroll_lock", system="Darwin",
                               _state=lambda _kc: False) is None


def test_a_probe_that_raises_is_dont_know_not_released():
    def boom(_kc):
        raise RuntimeError("no pyobjc")

    assert mac_tap.key_is_down("alt_r", system="Darwin", _state=boom) is None


# ---- the decision that ends a stranded Take --------------------------------


def test_a_key_still_held_does_not_end_the_take():
    assert mac_tap.release_was_missed("alt_r", held_since=0.0, now=5.0,
                                      system="Darwin",
                                      _state=lambda _kc: True) is False


def test_a_key_no_longer_held_ends_the_take():
    """The bug: app thinks it is held, hardware says it is not."""
    assert mac_tap.release_was_missed("alt_r", held_since=0.0, now=5.0,
                                      system="Darwin",
                                      _state=lambda _kc: False) is True


def test_the_grace_period_protects_the_start_of_a_take():
    """Press event and hardware state are not sampled at the same instant;
    cutting a Take off at its first poll would be a worse bug."""
    assert mac_tap.release_was_missed("alt_r", held_since=0.0, now=0.1,
                                      system="Darwin",
                                      _state=lambda _kc: False) is False


def test_an_unanswerable_poll_never_ends_a_take():
    """Windows, no pyobjc, an unknown key: all keep recording."""
    assert mac_tap.release_was_missed("alt_r", held_since=0.0, now=5.0,
                                      system="Windows",
                                      _state=lambda _kc: False) is False
    assert mac_tap.release_was_missed("scroll_lock", held_since=0.0, now=5.0,
                                      system="Darwin",
                                      _state=lambda _kc: False) is False
