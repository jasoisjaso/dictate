"""macOS Input Backend: Quartz Unicode typing + NSPasteboard paste.

The mac half of the Injection interface (docs/adr/0001). Same four
primitives as win32_input, same contract:

    inject_text_native_unicode(text) -> chars typed
    inject_text_via_paste(text)      -> True if the paste chord was sent
    inject_backspaces(count)         -> backspaces sent
    select_all()                     -> True if Cmd+A was sent

Everything here needs Accessibility Permission. Without the grant macOS
drops posted events silently — no exception, no error — which is why the
app preflights the grant at startup (src/permissions.py) rather than
discovering it here.

Typing goes through CGEventKeyboardSetUnicodeString rather than keycodes,
so any character works regardless of the user's keyboard layout — the mac
equivalent of Windows' KEYEVENTF_UNICODE.
"""

import logging
import threading
import time

log = logging.getLogger("dictate.mac_input")

# Carbon virtual keycodes (HIToolbox Events.h). Only the ones we synthesise.
KEYCODE_A = 0x00
KEYCODE_V = 0x09
KEYCODE_DELETE = 0x33        # the key labelled "delete" (backspace)

# A single CGEvent carries a bounded unicode string; keep chunks modest so a
# long transcript is many small events rather than one the window server may
# refuse. Matches the Windows backend's chunking intent.
CHUNK_UNITS = 256


def utf16_chunks(text: str, chunk_units: int = CHUNK_UNITS) -> list:
    """Split text into pieces of at most `chunk_units` UTF-16 code units.

    Pure, so it is testable anywhere. Two rules matter:
      - \\r\\n and lone \\r become \\n; apps expect a plain Return.
      - a chunk boundary never falls between the halves of a surrogate pair,
        or an emoji arrives as two replacement characters.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return []
    chunks = []
    current = []
    units = 0
    for ch in text:
        width = 2 if ord(ch) > 0xFFFF else 1
        if units + width > chunk_units and current:
            chunks.append("".join(current))
            current = []
            units = 0
        current.append(ch)
        units += width
    if current:
        chunks.append("".join(current))
    return chunks


def _quartz():
    import Quartz
    return Quartz


def _post(event):
    Quartz = _quartz()
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def inject_text_native_unicode(text_string: str, chunk_chars: int = CHUNK_UNITS) -> int:
    """Type a Unicode string into the focused app. No pasteboard involved.

    Returns the number of characters typed, so the caller's
    injection_suspect() check keeps working: 0 back from a non-empty string
    means nothing was delivered and the text should be rescued to the
    clipboard.
    """
    if not text_string:
        return 0
    Quartz = _quartz()
    typed = 0
    try:
        for chunk in utf16_chunks(text_string, chunk_chars):
            for is_down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, 0, is_down)
                Quartz.CGEventKeyboardSetUnicodeString(ev, len(chunk), chunk)
                _post(ev)
            typed += len(chunk)
            # the window server coalesces events posted back-to-back; a
            # sub-millisecond gap keeps long transcripts in order
            time.sleep(0.001)
    except Exception:
        log.exception("mac typing failed after %d chars", typed)
        return typed
    return typed


def _chord(keycode: int, flags):
    """Press a modified key (Cmd+V, Cmd+A) as a down/up pair."""
    Quartz = _quartz()
    down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
    Quartz.CGEventSetFlags(down, flags)
    up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
    Quartz.CGEventSetFlags(up, flags)
    _post(down)
    _post(up)


def _pasteboard():
    import AppKit
    return AppKit.NSPasteboard.generalPasteboard(), AppKit


def inject_text_via_paste(text_string: str, restore_delay: float = 1.2,
                          _on_paste=None) -> bool:
    """Put text on the pasteboard, press Cmd+V, then restore what was there.

    Same contract as the Windows backend, including the deferred restore:
    slow apps (Electron, Office) read the pasteboard well after the chord
    lands, so restoring immediately is the classic "pasted my OLD clipboard"
    bug. The restore runs on a background thread and only fires if our text
    is still the pasteboard's contents, so a copy the user made in the
    meantime is not stomped.

    _on_paste is a test hook: called with the text at the moment the chord
    fires, so a test can observe the pasteboard mid-flight.
    """
    try:
        pb, AppKit = _pasteboard()
    except Exception:
        log.exception("pasteboard unavailable; typing instead")
        inject_text_native_unicode(text_string)
        return False

    text_type = AppKit.NSPasteboardTypeString
    try:
        old = pb.stringForType_(text_type)
    except Exception:
        log.warning("pasteboard read failed; skipping restore", exc_info=True)
        old = None
    if old is None:
        log.info("pasteboard had no restorable text; previous contents will be lost")

    # Set + verify before the chord: a pasteboard manager can race us, and
    # pasting the user's OLD clipboard instead of their dictation is worse
    # than any other failure here.
    placed = False
    for _ in range(3):
        pb.clearContents()
        if pb.setString_forType_(text_string, text_type):
            if pb.stringForType_(text_type) == text_string:
                placed = True
                break
        time.sleep(0.03)
    if not placed:
        log.error("could not write pasteboard; falling back to typed injection")
        inject_text_native_unicode(text_string)
        return False

    if _on_paste is not None:
        _on_paste(text_string)

    Quartz = _quartz()
    _chord(KEYCODE_V, Quartz.kCGEventFlagMaskCommand)

    if old is not None:
        def _restore():
            time.sleep(restore_delay)
            try:
                if pb.stringForType_(text_type) == text_string:
                    pb.clearContents()
                    pb.setString_forType_(old, text_type)
            except Exception:
                log.warning("pasteboard restore failed", exc_info=True)
        threading.Thread(target=_restore, daemon=True).start()
    return True


def inject_backspaces(count: int) -> int:
    """Press Delete `count` times ("scratch that")."""
    if count <= 0:
        return 0
    Quartz = _quartz()
    sent = 0
    try:
        for _ in range(count):
            for is_down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, KEYCODE_DELETE, is_down)
                _post(ev)
            sent += 1
    except Exception:
        log.exception("mac backspace failed after %d", sent)
    return sent


def select_all() -> bool:
    """Press Cmd+A — select everything in the focused field."""
    try:
        Quartz = _quartz()
        _chord(KEYCODE_A, Quartz.kCGEventFlagMaskCommand)
        return True
    except Exception:
        log.exception("mac select-all failed")
        return False
