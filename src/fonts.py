"""Per-platform font families for the overlay and the guide (ticket 09).

Qt never fails on a missing family. It substitutes one silently, at different
metrics, which is why naming `Segoe UI` and `Consolas` on macOS is a bug you
can only see by looking: the overlay's fixed pixel widths get measured against
a face nobody chose, and the guide's key-caps — drawn in the *monospace*
family — resolve to the proportional system font and stop lining up.

The decision is pure. Both the candidate list and the set of installed
families are arguments, so the macOS answer is testable from Windows and the
Windows answer from here. Only `installed_families()` touches Qt, and it is
called once at import-time of the widgets, never inside a paint.

    pick_family(candidates, installed) -> str
    ui_family(system=, installed=)     -> the interface face
    mono_family(system=, installed=)   -> the fixed-pitch face
"""
from __future__ import annotations

import logging
import platform

log = logging.getLogger("dictate.fonts")

MACOS = "Darwin"
WINDOWS = "Windows"

# Ordered best-first. The last entry is the guaranteed-ish floor: if nothing
# matches we return it anyway, because Qt's own substitute for a named face
# beats handing Qt an empty string.
UI_CANDIDATES = {
    WINDOWS: ["Segoe UI", "Tahoma", "Arial"],
    # .AppleSystemUIFont is what Qt resolves the system face to on macOS 26;
    # Helvetica Neue is the pre-San-Francisco fallback.
    MACOS: [".AppleSystemUIFont", "Helvetica Neue", "Helvetica", "Arial"],
}

MONO_CANDIDATES = {
    WINDOWS: ["Consolas", "Courier New"],
    # SF Mono ships with Xcode/Terminal and is not always present; Menlo is,
    # on every Mac. Both are true fixed-pitch, which is the whole point.
    MACOS: ["SF Mono", "Menlo", "Monaco", "Courier New"],
}

# Anything not Windows or macOS (CI's ubuntu runner, mostly).
UI_FALLBACK = ["DejaVu Sans", "Liberation Sans", "Arial"]
MONO_FALLBACK = ["DejaVu Sans Mono", "Liberation Mono", "Courier New"]


def pick_family(candidates, installed) -> str:
    """First candidate that is installed, else the last candidate.

    Matching is case-insensitive: Qt reports families with the casing the
    font file declares, which is not always the casing we asked for.
    """
    have = {str(f).lower() for f in (installed or ())}
    for cand in candidates:
        if cand.lower() in have:
            return cand
    return candidates[-1]


def installed_families() -> set:
    """Every font family Qt can see. Empty set if there is no QGuiApplication
    yet — the caller then gets the first candidate, which is the right guess
    for the platform anyway."""
    try:
        from PySide6.QtGui import QFontDatabase

        return set(QFontDatabase.families())
    except Exception:
        log.debug("could not enumerate font families", exc_info=True)
        return set()


def _resolve(table, fallback, system, installed) -> str:
    system = system or platform.system()
    candidates = table.get(system, fallback)
    if installed is None:
        installed = installed_families()
    return pick_family(candidates, installed)


def ui_family(system: str | None = None, installed=None) -> str:
    """The interface face: overlay text, guide body, toasts."""
    return _resolve(UI_CANDIDATES, UI_FALLBACK, system, installed)


def mono_family(system: str | None = None, installed=None) -> str:
    """The fixed-pitch face: key-caps and command examples in the guide."""
    return _resolve(MONO_CANDIDATES, MONO_FALLBACK, system, installed)


# ---- what the widgets call --------------------------------------------------
# Enumerating families costs ~35 ms, so it happens once per process, on the
# first font a widget asks for — after QApplication exists, never in a paint.

_resolved: dict = {}


def _family(kind: str) -> str:
    if kind not in _resolved:
        installed = installed_families()
        _resolved["ui"] = ui_family(installed=installed)
        _resolved["mono"] = mono_family(installed=installed)
        log.info("fonts: ui=%s mono=%s", _resolved["ui"], _resolved["mono"])
    return _resolved[kind]


def ui_font(size: int, weight=None, italic: bool = False):
    """A QFont in the platform's interface face."""
    from PySide6.QtGui import QFont

    font = QFont(_family("ui"), size)
    if weight is not None:
        font.setWeight(weight)
    if italic:
        font.setItalic(True)
    return font


def mono_font(size: int, weight=None):
    """A QFont in the platform's fixed-pitch face."""
    from PySide6.QtGui import QFont

    font = QFont(_family("mono"), size)
    if weight is not None:
        font.setWeight(weight)
    return font
