"""Win32 plumbing: CUDA DLL path registration + native Unicode text injection.

configure_cuda_dll_search_paths() MUST run before ctranslate2/faster_whisper
import — Python 3.8+ on Windows no longer consults PATH for native extension
dependencies, so the cuBLAS/cuDNN DLLs inside the nvidia pip wheels are
invisible until registered with os.add_dll_directory.
"""

import array
import ctypes
import logging
import os
import platform
import site
import sys
from pathlib import Path

log = logging.getLogger("dictate.win32")

IS_WINDOWS = platform.system().lower() == "windows"


def configure_cuda_dll_search_paths():
    """Register nvidia wheel DLL dirs with the interpreter and the OS loader."""
    # Multiple deps (torch/numpy/MKL) can each ship libiomp5md.dll; allow reuse
    # instead of crashing on double initialisation.
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    if not IS_WINDOWS:
        return []

    search_roots = []
    # Frozen (Nuitka standalone): the nvidia/ and ctranslate2/ trees are
    # copied next to the executable, not into a site-packages.
    exe_dir = os.path.dirname(sys.executable)
    search_roots.append(exe_dir)
    if getattr(sys, "frozen", False) and sys.argv and sys.argv[0]:
        search_roots.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    try:
        search_roots.extend(site.getsitepackages())
    except AttributeError:
        pass
    if hasattr(site, "getusersitepackages"):
        search_roots.append(site.getusersitepackages())
    for path in sys.path:
        if "site-packages" in path and path not in search_roots:
            search_roots.append(path)

    target_subs = [
        Path("nvidia") / "cublas" / "bin",
        Path("nvidia") / "cudnn" / "bin",
        Path("nvidia") / "cuda_runtime" / "bin",
        Path("ctranslate2"),
    ]

    registered = []
    for root in search_roots:
        for sub in target_subs:
            full = Path(root) / sub
            if full.is_dir():
                try:
                    os.add_dll_directory(str(full.resolve()))
                    os.environ["PATH"] = str(full.resolve()) + os.pathsep + os.environ["PATH"]
                    registered.append(str(full))
                except OSError as ex:
                    log.warning("could not register DLL dir %s: %s", full, ex)
    log.info("registered %d CUDA DLL directories", len(registered))
    return registered


def choose_injection(text: str, mode: str = "auto",
                     paste_threshold: int = 300) -> str:
    """'type' (SendInput per char) or 'paste' (clipboard + Ctrl+V).

    Typing is invisible to the clipboard and feels native for short bursts.
    Pasting is instant for long text and — crucially — the only safe option
    for multi-line output in auto mode, because a typed Enter can fire
    "send" in chat apps before the message is complete.
    """
    if mode in ("type", "paste"):
        return mode
    if "\n" in text:
        return "paste"
    return "paste" if len(text) > paste_threshold else "type"


# ---- SendInput Unicode injection -------------------------------------------

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_BACK = 0x08

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("mi", MOUSEINPUT),
            ("hi", HARDWAREINPUT),
        ]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("u", INPUT_UNION),
        ]

    def _send_inputs(events):
        arr = (INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), ctypes.byref(arr), ctypes.sizeof(INPUT))
        if sent != len(events):
            log.error("SendInput injected %d/%d events (err=%d)",
                      sent, len(events), ctypes.get_last_error())
        return sent

    def _key_event(scan, flags):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki = KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
        return inp

    def inject_text_native_unicode(text_string: str, chunk_chars: int = 256):
        """Type a Unicode string into the focused window. No clipboard involved.

        Text goes in as UTF-16 code units with KEYEVENTF_UNICODE, so emoji,
        accents and any keyboard layout all work. Chunked so very long
        transcripts do not exceed the input queue.
        """
        if not text_string:
            return 0
        # \r\n vs \n: apps expect a plain Return; normalise
        text_string = text_string.replace("\r\n", "\n").replace("\r", "\n")
        units = array.array("H", text_string.encode("utf-16le"))
        total = 0
        for i in range(0, len(units), chunk_chars):
            chunk = units[i:i + chunk_chars]
            events = []
            for cu in chunk:
                events.append(_key_event(cu, KEYEVENTF_UNICODE))
                events.append(_key_event(cu, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
            total += _send_inputs(events)
        return total // 2

    VK_CONTROL = 0x11
    VK_V = 0x56
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def _clipboard_get_text():
        """Current clipboard text, or None if empty/non-text (can't restore those)."""
        if not user32.OpenClipboard(None):
            return None
        try:
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return None
            ptr = kernel32.GlobalLock(h)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(h)
        finally:
            user32.CloseClipboard()

    def _clipboard_set_text(text: str) -> bool:
        data = text.encode("utf-16le") + b"\x00\x00"
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return False
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h)
            return False
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_UNICODETEXT, h):
                kernel32.GlobalFree(h)
                return False
            return True  # system owns h now
        finally:
            user32.CloseClipboard()

    def _vk_event(vk, flags=0):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
        return inp

    def inject_text_via_paste(text_string: str, restore_delay: float = 0.3):
        """Put text on the clipboard, press Ctrl+V, then restore what was there.

        Restores only text contents; images/files on the clipboard are lost —
        that trade-off is logged. Returns True if the paste keystroke was sent.
        """
        import time as _time
        old = _clipboard_get_text()
        if old is None:
            log.info("clipboard had no restorable text; previous contents will be lost")
        if not _clipboard_set_text(text_string):
            log.error("could not write clipboard; falling back to typed injection")
            inject_text_native_unicode(text_string)
            return False
        _send_inputs([
            _vk_event(VK_CONTROL),
            _vk_event(VK_V),
            _vk_event(VK_V, KEYEVENTF_KEYUP),
            _vk_event(VK_CONTROL, KEYEVENTF_KEYUP),
        ])
        # let the target app read the clipboard before we restore it
        _time.sleep(restore_delay)
        if old is not None:
            _clipboard_set_text(old)
        return True

    def inject_backspaces(count: int):
        """Press Backspace `count` times ("scratch that")."""
        if count <= 0:
            return 0
        events = []
        for _ in range(count):
            down = INPUT()
            down.type = INPUT_KEYBOARD
            down.ki = KEYBDINPUT(wVk=VK_BACK, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
            up = INPUT()
            up.type = INPUT_KEYBOARD
            up.ki = KEYBDINPUT(wVk=VK_BACK, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
            events.extend((down, up))
        return _send_inputs(events) // 2

else:
    def inject_text_native_unicode(text_string: str, chunk_chars: int = 256):
        log.warning("not on Windows — injection unavailable, text was: %r", text_string[:80])
        return 0

    def inject_text_via_paste(text_string: str, restore_delay: float = 0.3):
        return False

    def inject_backspaces(count: int):
        return 0
