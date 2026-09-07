"""Prototype: can the recording overlay float on macOS from a menu-bar-only app?

Q20's open question. The overlay uses Qt.Tool, and on macOS a Qt.Tool window
hides whenever its application deactivates. A menu-bar-only (accessory) app is
NEVER the active app, which is exactly when the overlay must be on screen. It
also will not appear over a full-screen Space without an explicit window level
and collection behaviour.

This applies the candidate fix through pyobjc on the live NSWindow and reports
what actually stuck. Throwaway: the answer folds into src/overlay.py.

NSWindow levels: normal 0, floating 3, modalPanel 8, popUpMenu 101,
screenSaver 1000. Collection behaviour bits: canJoinAllSpaces 1<<0,
stationary 1<<4, fullScreenAuxiliary 1<<8, ignoresCycle 1<<6.

RESULT (2026-09-07, macOS 26.6.2, PySide6 6.11.2, run from an accessory app):

    activation policy: 1 (Accessory)
    BEFORE fix  level=8    collectionBehavior=258  visible=True
    AFTER  fix  level=101  collectionBehavior=337  hidesOnDeactivate=False
    activated 'Terminal' (was 'python')
    overlay still visible after deactivation: True  onActiveSpace=True
    PASS

So Qt's own flags leave the overlay at modalPanel level (8) with Qt's default
collection behaviour (258), and the four native calls below are what the port
needs. Qt exposes none of them, so src/overlay.py has to reach the NSWindow
through winId() once, on show.
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "cocoa")

from PySide6.QtCore import Qt, QTimer          # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import AppKit                                   # noqa: E402
import objc                                     # noqa: E402

CAN_JOIN_ALL_SPACES = 1 << 0
STATIONARY = 1 << 4
IGNORES_CYCLE = 1 << 6
FULLSCREEN_AUXILIARY = 1 << 8

LEVEL_FLOATING = 3
LEVEL_POPUP_MENU = 101

app = QApplication(sys.argv)

# Menu-bar-only: the app is never frontmost, which is the whole problem.
AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
print(f"activation policy: {AppKit.NSApp.activationPolicy()} (1 = Accessory)")

w = QWidget(
    None,
    Qt.FramelessWindowHint
    | Qt.WindowStaysOnTopHint
    | Qt.Tool
    | Qt.WindowTransparentForInput
    | Qt.WindowDoesNotAcceptFocus,
)
w.setAttribute(Qt.WA_TranslucentBackground)
w.setAttribute(Qt.WA_ShowWithoutActivating)
w.setStyleSheet("background: rgba(20,24,32,220); border-radius: 12px;")
w.resize(320, 90)
screen = app.primaryScreen().availableGeometry()
w.move(screen.center().x() - 160, screen.bottom() - 130)
w.show()
app.processEvents()
time.sleep(0.4)
app.processEvents()


def native_window():
    """The NSWindow backing this QWidget, via its winId."""
    view = objc.objc_object(c_void_p=w.winId())
    return view.window()


nsw = native_window()
print(f"\nBEFORE fix  level={nsw.level()}  collectionBehavior={nsw.collectionBehavior()}"
      f"  visible={bool(nsw.isVisible())}")

# --- candidate fix -----------------------------------------------------------
nsw.setLevel_(LEVEL_POPUP_MENU)
nsw.setCollectionBehavior_(
    CAN_JOIN_ALL_SPACES | STATIONARY | IGNORES_CYCLE | FULLSCREEN_AUXILIARY)
nsw.setHidesOnDeactivate_(False)
nsw.setIgnoresMouseEvents_(True)

print(f"AFTER  fix  level={nsw.level()}  collectionBehavior={nsw.collectionBehavior()}"
      f"  hidesOnDeactivate={bool(nsw.hidesOnDeactivate())}"
      f"  visible={bool(nsw.isVisible())}")

# Deactivation is the failure mode Qt.Tool has on mac: push another app to the
# front and check the overlay is still on screen.
ws = AppKit.NSWorkspace.sharedWorkspace()
front_before = ws.frontmostApplication().localizedName()
others = [a for a in ws.runningApplications()
          if a.activationPolicy() == AppKit.NSApplicationActivationPolicyRegular
          and a.localizedName() != front_before]
if others:
    target = others[0]
    target.activateWithOptions_(AppKit.NSApplicationActivateAllWindows)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.1)
    print(f"\nactivated '{target.localizedName()}' (was '{front_before}')")
    print(f"overlay still visible after deactivation: {bool(nsw.isVisible())}"
          f"  onActiveSpace={bool(nsw.isOnActiveSpace())}")
else:
    print("\nno other regular app running to steal focus")

ok = bool(nsw.isVisible()) and nsw.level() == LEVEL_POPUP_MENU
print("\nPASS: overlay survives deactivation from an accessory app"
      if ok else "\nFAIL: overlay hidden or level not applied")

QTimer.singleShot(1500, app.quit)
app.exec()
sys.exit(0 if ok else 1)
