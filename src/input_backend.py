"""The Injection interface: one small surface, one Input Backend behind it.

See docs/adr/0001-input-backend-seam.md. Delivery calls this module and never
names an operating system; the backend is resolved once, at import.

The interface is four operations plus one pure decision:

    inject_text(text)   -> chars injected (Type)
    paste_text(text)    -> True if the paste keystroke was sent (Paste)
    backspaces(count)   -> backspaces sent
    select_all()        -> True if the select-all shortcut was sent
    choose_injection(...) -> "type" | "paste", pure, platform-independent

Every call goes through the module-level functions rather than a bound
reference, so a test can swap `_backend` for a fake and exercise the whole
delivery path on any platform.
"""

import logging
import platform

log = logging.getLogger("dictate.input_backend")

IS_WINDOWS = platform.system().lower() == "windows"
IS_MACOS = platform.system().lower() == "darwin"


def choose_injection(text: str, mode: str = "auto",
                     paste_threshold: int = 300,
                     prefer_type: bool = False) -> str:
    """'type' (one key event per char) or 'paste' (clipboard + paste shortcut).

    Typing is invisible to the clipboard and feels native for short bursts.
    Pasting is instant for long text and — crucially — the only safe option
    for multi-line output in auto mode, because a typed Enter can fire
    "send" in chat apps before the message is complete.

    prefer_type: terminals reliably accept typed Unicode input but are flaky
    about a synthesized paste shortcut. For a terminal-profile window,
    single-line text of any length is typed; only multi-line text pastes.
    """
    if mode in ("type", "paste"):
        return mode
    if "\n" in text:
        return "paste"
    if prefer_type:
        return "type"
    return "paste" if len(text) > paste_threshold else "type"


def injection_suspect(sent: int, expected: int) -> bool:
    """True when the backend delivered fewer events than requested, the
    classic sign of a target window swallowing input. The caller then falls
    back to putting the text on the clipboard so the dictation is never lost.
    """
    return sent < expected


class _Win32Backend:
    """Windows Input Backend — SendInput typing, clipboard paste, Ctrl+A."""

    name = "win32"

    def __init__(self, mod):
        self._mod = mod

    def inject_text(self, text: str) -> int:
        return self._mod.inject_text_native_unicode(text)

    def paste_text(self, text: str) -> bool:
        return self._mod.inject_text_via_paste(text)

    def backspaces(self, count: int) -> int:
        return self._mod.inject_backspaces(count)

    def select_all(self) -> bool:
        return self._mod.select_all()


class _MacBackend:
    """macOS Input Backend — Quartz unicode typing, NSPasteboard paste, Cmd+A."""

    name = "macos"

    def __init__(self, mod):
        self._mod = mod

    def inject_text(self, text: str) -> int:
        return self._mod.inject_text_native_unicode(text)

    def paste_text(self, text: str) -> bool:
        return self._mod.inject_text_via_paste(text)

    def backspaces(self, count: int) -> int:
        return self._mod.inject_backspaces(count)

    def select_all(self) -> bool:
        return self._mod.select_all()


class _NullBackend:
    """No Injection available on this platform. Never raises: the delivery
    path treats an undelivered result as a clipboard rescue, which is a far
    better failure than a traceback mid-dictation."""

    name = "null"

    def inject_text(self, text: str) -> int:
        log.warning("no input backend — text not injected: %r", text[:80])
        return 0

    def paste_text(self, text: str) -> bool:
        log.warning("no input backend — text not pasted: %r", text[:80])
        return False

    def backspaces(self, count: int) -> int:
        return 0

    def select_all(self) -> bool:
        return False


def _resolve_backend():
    if IS_WINDOWS:
        try:
            from . import win32_input
        except ImportError:
            import win32_input
        return _Win32Backend(win32_input)
    if IS_MACOS:
        try:
            try:
                from . import mac_input
            except ImportError:
                import mac_input
            return _MacBackend(mac_input)
        except Exception:
            # pyobjc missing or broken: a dictation parked on the clipboard
            # beats a traceback on every result.
            log.exception("macOS input backend unavailable")
    return _NullBackend()


_backend = _resolve_backend()


def active_backend_name() -> str:
    return _backend.name


def inject_text(text: str) -> int:
    return _backend.inject_text(text)


def paste_text(text: str) -> bool:
    return _backend.paste_text(text)


def backspaces(count: int) -> int:
    return _backend.backspaces(count)


def select_all() -> bool:
    return _backend.select_all()
