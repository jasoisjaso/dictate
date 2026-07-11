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

    def inject_backspaces(count: int):
        return 0
