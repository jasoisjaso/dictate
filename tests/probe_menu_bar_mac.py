"""Probe: does menu-bar-only actually stick, and does Quit actually exit?

Ticket 07's two claims are about the live machine, and no unit test can reach
either: the activation policy is a property of a real NSApp, and "the process
is gone" is only answerable by a process that ended.

Run:  .venv-mac/bin/python tests/probe_menu_bar_mac.py

Prints one line per fact so a failure names itself, then exits 0/1.
"""

import os
import sys
import time

# cocoa, not offscreen: an offscreen QApplication has no NSApp to ask.
os.environ["QT_QPA_PLATFORM"] = "cocoa"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from src import mac_shell  # noqa: E402
from src.tray_shell import make_icon  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

import AppKit  # noqa: E402

before = AppKit.NSApp.activationPolicy()
print(f"BEFORE  activationPolicy={before}  (0 = Regular, has a Dock icon)")

applied = mac_shell.apply_menu_bar_only()
after = AppKit.NSApp.activationPolicy()
print(f"AFTER   activationPolicy={after}  (1 = Accessory, no Dock, no Cmd+Tab)"
      f"  applied={applied}")

# The tray has to still work once we are an accessory app — that is the whole
# point of the policy, and the failure mode if the wrong one is chosen.
tray_available = QSystemTrayIcon.isSystemTrayAvailable()
tray = QSystemTrayIcon(make_icon("#3fb950"))
tray.show()
app.processEvents()
time.sleep(0.3)
app.processEvents()
print(f"tray available={tray_available}  tray visible={bool(tray.isVisible())}")

# Nobody in the Dock should be us. NSWorkspace lists only regular apps in the
# Dock sense, so an accessory app must not report a Regular policy.
me = AppKit.NSRunningApplication.currentApplication()
print(f"self policy via NSRunningApplication={me.activationPolicy()}")

ok = (after == mac_shell.ACTIVATION_POLICY_ACCESSORY
      and me.activationPolicy() == mac_shell.ACTIVATION_POLICY_ACCESSORY
      and bool(tray.isVisible()))

# The watchdog: prove it really ends the process rather than raising. This
# process exits HERE, from inside the timer, if the wiring is right.
print("PASS: menu-bar-only applied and tray still works" if ok
      else "FAIL: policy or tray wrong")
if not ok:
    sys.exit(1)

print("arming the exit watchdog (200 ms) — the process must die by itself")
sys.stdout.flush()
mac_shell.arm_exit_watchdog(delay_ms=200)
app.exec()
# Only reached if the watchdog never fired: app.exec() returning means the
# loop ended some other way, which is not what is being probed.
print("FAIL: watchdog did not end the process")
sys.exit(1)
