# PyInstaller spec for the macOS .app (ticket 11, docs/adr/0002).
#
# Run it through packaging/build_mac_app.sh rather than by hand — the script
# also does the ad-hoc signing, without which macOS refuses to keep the
# Accessibility grant.
#
# Three things here are load-bearing and easy to lose in a rewrite:
#
#   * `config/settings.toml` is a data file. PyInstaller unpacks datas to
#     Contents/Frameworks and tells the app about it via sys._MEIPASS, which
#     is why paths.resource_root() exists.
#   * LSUIElement makes the bundle menu-bar-only. src/mac_shell.py says the
#     same thing at runtime; the two agreeing is the point (ADR 0002).
#   * NSMicrophoneUsageDescription is not optional. Without the key macOS
#     never shows the mic prompt and capture returns silence forever — a
#     failure with no error message anywhere.
#
# The 640 MB Parakeet model is deliberately NOT bundled; first run downloads
# it through the existing resumable path.

import os
import sys

ROOT = os.path.abspath(os.path.join(os.getcwd()))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.version import __version__ as APP_VERSION  # noqa: E402

ICON = os.path.join(ROOT, "assets", "dictate.icns")

a = Analysis(
    [os.path.join(ROOT, "dictate_launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "config"), "config")],
    hiddenimports=[
        # Engines. Both are imported lazily behind device.choose_engine(), so
        # PyInstaller's static analysis cannot see either of them.
        "faster_whisper",
        "sherpa_onnx",
        # pynput and pyobjc resolve their macOS backends by string at import
        # time, for the same reason.
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "AppKit",
        "Quartz",
        "ApplicationServices",
        "HIServices",
        "objc",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Qt ships several large modules Dictate never touches. Dropping them is
    # not just size: QtWebEngine in particular pulls a helper app that has to
    # be signed separately, and an unsigned nested binary breaks the bundle.
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "tkinter",
        "matplotlib",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Dictate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,     # this machine's arch; the wheels are universal2
    codesign_identity=None,   # signed by build_mac_app.sh, after the build
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Dictate",
)

app = BUNDLE(
    coll,
    name="Dictate.app",
    icon=ICON,
    bundle_identifier="com.jaso.dictate",
    version=APP_VERSION,
    info_plist={
        "CFBundleName": "Dictate",
        "CFBundleDisplayName": "Dictate",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        # Menu-bar-only: no Dock icon, no Cmd+Tab entry.
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        # Shown verbatim in the system prompt the first time we record.
        "NSMicrophoneUsageDescription":
            "Dictate records from your microphone while you hold the "
            "push-to-talk key, and transcribes it on this machine. Nothing "
            "is uploaded.",
        # Not currently requested in code, but the bundle is the thing macOS
        # reads: an app that posts keyboard events without a stated reason is
        # a worse citizen than one that says why.
        "NSAppleEventsUsageDescription":
            "Dictate types your transcribed words into the app you are "
            "working in.",
    },
)
