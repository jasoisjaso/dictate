"""Regression tests for the 2026-07 clipboard crash.

Root cause: ctypes defaults every foreign function's return type to a
32-bit C int. On 64-bit Windows, GetClipboardData / GlobalAlloc /
GlobalLock return 64-bit handles/pointers; the silent truncation produced
garbage pointers and an access-violation hard crash inside wstring_at —
killing the whole app exactly when a LONG dictation went down the
clipboard-paste path (len > paste_threshold). Short dictations type via
SendInput and never touched the clipboard, which is why only long
sentences "lost" their text.

These tests pin the explicit prototypes so the bug cannot silently
return. Windows-only assertions are skipped elsewhere.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import win32_input  # noqa: E402

IS_WIN = win32_input.IS_WINDOWS


@pytest.mark.skipif(not IS_WIN, reason="Windows-only clipboard plumbing")
def test_clipboard_functions_have_64bit_safe_prototypes():
    import ctypes
    from ctypes import wintypes
    u, k = win32_input.user32, win32_input.kernel32
    assert u.GetClipboardData.restype is wintypes.HANDLE
    assert k.GlobalLock.restype is wintypes.LPVOID
    assert k.GlobalAlloc.restype is wintypes.HGLOBAL
    assert k.GlobalSize.restype is ctypes.c_size_t
    # sanity: HANDLE/LPVOID must be pointer-sized, not int-sized
    assert ctypes.sizeof(wintypes.HANDLE) == ctypes.sizeof(ctypes.c_void_p)


@pytest.mark.skipif(not IS_WIN, reason="Windows-only clipboard plumbing")
def test_clipboard_roundtrip_long_text():
    """A paste-threshold-sized payload must survive set -> get intact."""
    old = win32_input._clipboard_get_text()
    try:
        payload = ("A deliberately long dictated sentence that forces the "
                   "clipboard paste path instead of typed SendInput. " * 30).strip()
        assert len(payload) > 300  # > default paste_threshold
        assert win32_input._clipboard_set_text(payload)
        assert win32_input._clipboard_get_text() == payload
        # unicode too — dictation isn't ASCII
        uni = "čćžšđ naša ulica — 4-year-old's tantrum 😀"
        assert win32_input._clipboard_set_text(uni)
        assert win32_input._clipboard_get_text() == uni
    finally:
        if old is not None:
            win32_input._clipboard_set_text(old)


def test_paste_never_raises_off_windows():
    """inject_text_via_paste must be a safe no-op on non-Windows."""
    if not IS_WIN:
        assert win32_input.inject_text_via_paste("hello " * 100) is False
