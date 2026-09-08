"""Keeping pynput's macOS event tap alive.

macOS switches an event tap OFF behind your back in two situations, and tells
the tap's own callback about it by sending a notification instead of an event:

    kCGEventTapDisabledByTimeout    (0xFFFFFFFE) — the callback took too long
    kCGEventTapDisabledByUserInput  (0xFFFFFFFF) — heavy input while tapping

Apple's contract is that the owner re-enables the tap when it sees one. pynput
does not. Its darwin backend calls `CGEventTapEnable` exactly once, inside
`_run`, on a tap it keeps only as a local variable — and `_handler` has no
branch for either notification. So once macOS turns the tap off, pynput leaves
it off and every key is silently dead for the rest of the process.

For Dictate that failure is not "hotkeys stop working". It is worse: a Take
already in progress never ends, because the push-to-talk RELEASE is the event
that stops it. The app sits in RECORDING, the overlay keeps listening, and the
only way out is Quit — which is what the owner hit on the first mac build.

This module closes the gap without forking pynput: it records the tap when the
listener creates one, and re-enables it when a disable notification arrives.
The decision is pure and the AppKit calls are arguments, so both are testable
with no pyobjc and no display:

    disable_reason(event_type)  -> "timeout" | "user_input" | None
    install(system=, ...)       -> True if the watchdog is now in place

Nothing here raises. A watchdog that cannot be installed logs and leaves the
listener exactly as pynput shipped it.
"""

import logging
import platform

log = logging.getLogger("dictate.mac_tap")

MACOS = "Darwin"

# The two notifications macOS sends INSTEAD of an event. Both are out of range
# for any real CGEventType, which is how they are distinguished.
TAP_DISABLED_BY_TIMEOUT = 0xFFFFFFFE
TAP_DISABLED_BY_USER_INPUT = 0xFFFFFFFF

_REASONS = {
    TAP_DISABLED_BY_TIMEOUT: "timeout",
    TAP_DISABLED_BY_USER_INPUT: "user_input",
}

# Set on the patched class, so a second install() is a no-op rather than a
# wrapper wrapped in a wrapper.
_INSTALLED_FLAG = "_dictate_tap_watchdog"

# Where the tap is stashed on the listener instance.
_TAP_ATTR = "_dictate_tap"


def wants_tap_watchdog(system: str | None = None) -> bool:
    """Only macOS has event taps. Windows and Linux need none of this."""
    return (system or platform.system()) == MACOS


# ---- asking the hardware, rather than trusting the event stream -------------
# The watchdog above fixes a proven gap in pynput, but it only helps if a
# disabled tap was the cause — and that was never demonstrated on this machine.
# A release event that never arrives has several possible causes and one single
# symptom, so the second guard skips the event stream entirely and asks macOS
# whether the key is physically down. CGEventSourceKeyState answers for the
# real hardware state and needs no Accessibility grant.

# Carbon virtual keycodes (HIToolbox Events.h) for every key that can be a
# push-to-talk default. Names match hotkeys._KEY_ALIASES.
VIRTUAL_KEYCODES = {
    "alt": 0x3A, "alt_l": 0x3A, "alt_r": 0x3D, "alt_gr": 0x3D,
    "ctrl": 0x3B, "ctrl_l": 0x3B, "ctrl_r": 0x3E,
    "cmd": 0x37, "cmd_l": 0x37, "cmd_r": 0x36,
    "shift": 0x38, "shift_l": 0x38, "shift_r": 0x3C,
    "caps_lock": 0x39, "space": 0x31, "esc": 0x35, "tab": 0x30,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60,
    "f6": 0x61, "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D,
    "f11": 0x67, "f12": 0x6F,
}

# kCGEventSourceStateCombinedSessionState — the state the user's own keyboard
# contributes to, as opposed to this process's private event source.
COMBINED_SESSION_STATE = 0


def virtual_keycode(name: str) -> int | None:
    """The Carbon keycode for a config key name, or None if we have no number.

    Pure. A name with no keycode simply means the hardware poll cannot run for
    that key, and the caller keeps relying on the event stream alone.
    """
    return VIRTUAL_KEYCODES.get((name or "").strip().lower())


def _default_key_state(keycode: int) -> bool:
    from Quartz import CGEventSourceKeyState

    return bool(CGEventSourceKeyState(COMBINED_SESSION_STATE, keycode))


def key_is_down(name: str, system: str | None = None, _state=None):
    """Is this key physically held right now? None when we cannot tell.

    None — not False — for every "don't know" case (wrong platform, unknown
    key, no pyobjc, a raising probe). A False here ends a Take, so inventing
    one from an unanswered question would cut the user off mid-sentence.
    """
    if not wants_tap_watchdog(system):
        return None
    keycode = virtual_keycode(name)
    if keycode is None:
        return None
    try:
        return bool((_state or _default_key_state)(keycode))
    except Exception:
        log.debug("could not read the hardware key state", exc_info=True)
        return None


def release_was_missed(ptt_name: str, held_since: float, now: float,
                       grace: float = 0.6, system: str | None = None,
                       _state=None) -> bool:
    """True when the app thinks the key is held but the hardware disagrees.

    The grace period exists because the two sources are not sampled at the
    same instant: a press event can arrive a few tens of milliseconds before
    the hardware settles, and cutting a Take off at its very first poll would
    be a worse bug than the one being fixed. Only a key that has been "held"
    for longer than `grace` is allowed to be contradicted.
    """
    if now - held_since < grace:
        return False
    return key_is_down(ptt_name, system=system, _state=_state) is False


def disable_reason(event_type) -> str | None:
    """Why macOS disabled the tap, or None if this is an ordinary event.

    Pure: the whole point of the module in one lookup, testable anywhere.
    """
    try:
        return _REASONS.get(int(event_type))
    except (TypeError, ValueError):
        return None


def _default_enable(tap, on: bool) -> None:
    from Quartz import CGEventTapEnable

    CGEventTapEnable(tap, on)


def install(system: str | None = None, _mixin=None, _enable=None) -> bool:
    """Patch pynput's listener so a disabled tap is re-enabled, not abandoned.

    Idempotent, and safe to call before any listener exists — the patch is on
    the class, so it applies to every listener started afterwards.
    """
    if not wants_tap_watchdog(system):
        return False

    mixin = _mixin
    if mixin is None:
        try:
            from pynput._util.darwin import ListenerMixin as mixin
        except Exception:
            log.debug("pynput darwin backend unavailable", exc_info=True)
            return False

    if getattr(mixin, _INSTALLED_FLAG, False):
        return True

    enable = _enable or _default_enable
    original_create = mixin._create_event_tap
    original_handler = mixin._handler

    def _create_event_tap(self):
        """Same tap pynput builds, kept where the handler can reach it."""
        tap = original_create(self)
        setattr(self, _TAP_ATTR, tap)
        return tap

    def _handler(self, proxy, event_type, event, refcon):
        reason = disable_reason(event_type)
        if reason is None:
            return original_handler(self, proxy, event_type, event, refcon)
        # Not an event: a notification that the tap is now off. Passing it to
        # pynput's handler would have it read key flags off a non-event, so
        # this path never calls through.
        tap = getattr(self, _TAP_ATTR, None)
        if tap is None:
            log.error("event tap disabled by %s and no tap recorded — hotkeys "
                      "are dead until Dictate restarts", reason)
            return None
        try:
            enable(tap, True)
        except Exception:
            log.exception("event tap disabled by %s and could not be "
                          "re-enabled", reason)
            return None
        log.warning("event tap was disabled by %s — re-enabled", reason)
        return None

    mixin._create_event_tap = _create_event_tap
    mixin._handler = _handler
    setattr(mixin, _INSTALLED_FLAG, True)
    log.info("macOS event-tap watchdog installed")
    return True
