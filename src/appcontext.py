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

`match` entries are case-insensitive with `*` wildcards allowed. How the
Foreground App is *named* is platform-dependent: Windows identifies it by
executable name (`cmd.exe`), macOS by bundle identifier
(`com.apple.Terminal`) — bundle id over display name because it is stable
and locale-independent, so a French Mac's Terminal is still
`com.apple.Terminal`. One `match` list holds both kinds, which is what keeps
a profile someone wrote portable even though an identifier is not.
"""
from __future__ import annotations

import fnmatch
import logging
import platform

log = logging.getLogger("dictate.appcontext")


def resolve_profile(identifier: str | None, profiles: dict) -> dict:
    """Return the first profile whose `match` list hits the identifier, else {}.

    `identifier` is whatever the platform calls the Foreground App: an
    executable name on Windows, a bundle identifier on macOS. Both kinds live
    in one `match` list, so the parameter cannot be named for either one.
    """
    if not identifier:
        return {}
    low = identifier.lower()
    for name, prof in profiles.items():
        for pat in prof.get("match", []):
            if fnmatch.fnmatch(low, pat.lower()):
                out = {k: v for k, v in prof.items() if k != "match"}
                out["_profile"] = name
                return out
    return {}


def foreground_bundle_id() -> str | None:
    """Bundle identifier of the frontmost application (macOS).

    NSWorkspace answers without Accessibility Permission, so a user who has
    not granted it yet still gets App Profiles — the grant only gates
    hotkeys and Injection.
    """
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app is not None else None


def foreground_app(system: str | None = None, _win_exe=None,
                   _mac_bundle_id=None) -> str | None:
    """Whatever this platform calls the app with focus, or None.

    The per-platform lookups are arguments so each answer is testable from
    the other platform. Never raises: a dictation must not be lost because
    focus could not be identified — an unnamed app just gets no profile.
    """
    system = system or platform.system()
    lookup = {"Windows": _win_exe or foreground_exe,
              "Darwin": _mac_bundle_id or foreground_bundle_id}.get(system)
    if lookup is None:
        return None
    try:
        return lookup()
    except Exception as ex:
        log.debug("foreground app detection failed: %s", ex)
        return None


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


# Both identifier kinds live in one `match` list per profile: Windows exe
# names and macOS bundle identifiers. A profile stays portable that way, even
# though an identifier is not.
DEFAULT_PROFILES = {
    "terminal": {
        "match": ["WindowsTerminal.exe", "wt.exe", "cmd.exe", "powershell.exe",
                  "pwsh.exe", "conhost.exe", "Code.exe", "idea*.exe",
                  "pycharm*.exe", "putty.exe", "alacritty.exe", "wezterm*.exe",
                  # macOS terminals
                  "com.apple.Terminal", "com.googlecode.iterm2",
                  "net.kovidgoyal.kitty", "org.alacritty",
                  "com.github.wez.wezterm", "dev.warp.Warp*",
                  # macOS editors/IDEs — verbatim for the same reason as their
                  # Windows counterparts: code is not prose.
                  "com.microsoft.VSCode", "com.jetbrains.*",
                  "com.apple.dt.Xcode", "com.sublimetext.*",
                  "com.qvacua.VimR"],
        "verbatim": True,
    },
    "chat": {
        "match": ["Discord.exe", "Slack.exe", "ms-teams.exe", "Teams.exe",
                  "WhatsApp.exe", "Telegram.exe", "Signal.exe",
                  # macOS
                  "com.tinyspeck.slackmacgap", "com.hnc.Discord",
                  "com.microsoft.teams*", "net.whatsapp.WhatsApp",
                  "ru.keepcoder.Telegram",
                  "org.whispersystems.signal-desktop", "com.apple.MobileSMS"],
        "tone": "casual",
    },
    "email": {
        "match": ["OUTLOOK.EXE", "olk.exe", "Thunderbird.exe",
                  # macOS
                  "com.apple.mail", "com.microsoft.Outlook",
                  "org.mozilla.thunderbird", "com.readdle.smartemail-Mac"],
        "tone": "professional",
    },
    # Modern Windows 11 Notepad (Store app) has a slow input pipeline that
    # silently drops fast synthesized keystrokes — the classic "only the
    # first word types, rest is blank" symptom. Force clipboard-paste there
    # (instant + atomic) so nothing is lost. Notepad ONLY; every other app
    # types normally.
    "notepad": {
        "match": ["Notepad.exe", "notepad.exe"],
        "force_paste": True,
    },
}
