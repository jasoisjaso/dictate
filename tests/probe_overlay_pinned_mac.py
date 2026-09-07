"""Verification: does the *shipped* overlay pin itself when shown? (ticket 08)

`probe_overlay_mac.py` established the fix on a bare QWidget. This one runs
the real `WaveformOverlay` from an accessory app — the condition the bug only
appears under — and reads back what stuck on its NSWindow, so the check is of
the code that ships rather than of a prototype that resembles it.

RESULT (2026-09-08, macOS 26.6.2, PySide6 6.11.2):

    activation policy: 1 (Accessory)
    level=101  collectionBehavior=337  hidesOnDeactivate=False  visible=True
    activated 'Terminal' (was 'python')
    overlay still visible after deactivation: True  onActiveSpace=True
    PASS: the shipped overlay pins itself on show
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "cocoa")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QTimer                      # noqa: E402
from PySide6.QtWidgets import QApplication             # noqa: E402

import AppKit                                          # noqa: E402
import objc                                            # noqa: E402

from src.overlay import WaveformOverlay                 # noqa: E402
from src import mac_window                              # noqa: E402

app = QApplication(sys.argv)

# The whole point: an accessory app is never frontmost.
AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
print(f"activation policy: {AppKit.NSApp.activationPolicy()} (1 = Accessory)")

overlay = WaveformOverlay(style="equalizer")
overlay.set_level_source(lambda: 0.0)
overlay.show_recording()
app.processEvents()
time.sleep(0.4)
app.processEvents()

view = objc.objc_object(c_void_p=overlay.winId())
nsw = view.window()
print(f"\nlevel={nsw.level()}  collectionBehavior={nsw.collectionBehavior()}"
      f"  hidesOnDeactivate={bool(nsw.hidesOnDeactivate())}"
      f"  visible={bool(nsw.isVisible())}")

ws = AppKit.NSWorkspace.sharedWorkspace()
front_before = ws.frontmostApplication().localizedName()
others = [a for a in ws.runningApplications()
          if a.activationPolicy() == AppKit.NSApplicationActivationPolicyRegular
          and a.localizedName() != front_before]
still_visible = bool(nsw.isVisible())
if others:
    target = others[0]
    target.activateWithOptions_(AppKit.NSApplicationActivateAllWindows)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.1)
    still_visible = bool(nsw.isVisible())
    print(f"\nactivated '{target.localizedName()}' (was '{front_before}')")
    print(f"overlay still visible after deactivation: {still_visible}"
          f"  onActiveSpace={bool(nsw.isOnActiveSpace())}")
else:
    print("\nno other regular app running to steal focus")

ok = (still_visible
      and nsw.level() == mac_window.LEVEL_POPUP_MENU
      and nsw.collectionBehavior() == mac_window.OVERLAY_COLLECTION_BEHAVIOR
      and not nsw.hidesOnDeactivate())
print("\nPASS: the shipped overlay pins itself on show"
      if ok else "\nFAIL: the shipped overlay did not pin itself")

QTimer.singleShot(800, app.quit)
app.exec()
sys.exit(0 if ok else 1)
