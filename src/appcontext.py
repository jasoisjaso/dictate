"""Foreground-app detection + per-app formatting profiles.

This is the "context-aware" layer: dictating into a terminal should not get
sentence-cased prose, and a chat message can stay casual while an email goes
out formal. Profiles come from config [app_profiles.<name>] tables:

    [app_profiles.terminal]
    match = ["WindowsTerminal.exe", "cmd.exe", "Code.exe"]
    verbatim = true            # skip casing + filler cleanup, keep words as spoken

    [app_profiles.chat]
    match = ["Discord.exe", "Slack.exe"]
    tone = "casual"            # hint for the optional Ollama polish pass

`match` entries are exe names, case-insensitive, `*` wildcard allowed.
"""
from __future__ import annotations

import fnmatch
import logging
import platform

log = logging.getLogger("dictate.appcontext")


def resolve_profile(exe_name: str | None, profiles: dict) -> dict:
    """Return the first profile whose `match` list hits exe_name, else {}."""
    if not exe_name:
        return {}
    low = exe_name.lower()
    for name, prof in profiles.items():
        for pat in prof.get("match", []):
            if fnmatch.fnmatch(low, pat.lower()):
                out = {k: v for k, v in prof.items() if k != "match"}
                out["_profile"] = name
                return out
    return {}


def foreground_exe() -> str | None:
    """Executable name of the window that currently has focus (Windows)."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(h)
    except Exception as ex:
        log.debug("foreground exe detection failed: %s", ex)
    return None


DEFAULT_PROFILES = {
    "terminal": {
        "match": ["WindowsTerminal.exe", "wt.exe", "cmd.exe", "powershell.exe",
                  "pwsh.exe", "conhost.exe", "Code.exe", "idea*.exe",
                  "pycharm*.exe", "putty.exe", "alacritty.exe", "wezterm*.exe"],
        "verbatim": True,
    },
    "chat": {
        "match": ["Discord.exe", "Slack.exe", "ms-teams.exe", "Teams.exe",
                  "WhatsApp.exe", "Telegram.exe", "Signal.exe"],
        "tone": "casual",
    },
    "email": {
        "match": ["OUTLOOK.EXE", "olk.exe", "Thunderbird.exe"],
        "tone": "professional",
    },
}
