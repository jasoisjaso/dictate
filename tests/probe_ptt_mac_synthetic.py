"""Automated half of the PTT probe: can pynput's mac tap pair a ctrl_r hold?

probe_ptt_mac.py needs a human hand. This one posts SYNTHETIC Right Ctrl
flagsChanged events via Quartz and checks pynput reports a clean down->up
pair. That isolates the mechanism (tap wiring + modifier pairing) from the
question only a real keyboard can answer (does the physical key behave).

kVK_RightControl = 0x3E (62). Right Ctrl sets the maskControl bit plus the
device-dependent right-control bit 0x2000.
"""

import sys
import time

import Quartz
from pynput import keyboard

KEYCODE_RCTRL = 0x3E
MASK_CONTROL = Quartz.kCGEventFlagMaskControl
MASK_RCTRL_DEVICE = 0x2000

events = []


def name(key):
    return getattr(key, "name", None) or repr(getattr(key, "char", key))


listener = keyboard.Listener(
    on_press=lambda k: events.append(("down", name(k))),
    on_release=lambda k: events.append(("up", name(k))),
)
listener.start()
time.sleep(1.0)   # let the tap attach before posting


def post_flags(flags):
    ev = Quartz.CGEventCreateKeyboardEvent(None, KEYCODE_RCTRL, True)
    Quartz.CGEventSetType(ev, Quartz.kCGEventFlagsChanged)
    Quartz.CGEventSetFlags(ev, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


print("posting synthetic Right Ctrl: down, hold 0.4s, up")
post_flags(MASK_CONTROL | MASK_RCTRL_DEVICE)
time.sleep(0.4)
post_flags(0)
time.sleep(1.0)
listener.stop()

print(f"events seen: {events}")
ctrl = [e for e in events if e[1] == "ctrl_r"]
kinds = [k for k, _ in ctrl]
ok = "down" in kinds and "up" in kinds and kinds.index("down") < kinds.index("up")
print("PASS: tap sees a paired synthetic ctrl_r hold" if ok else
      "FAIL: no paired ctrl_r — tap wiring or modifier pairing is the problem")
sys.exit(0 if ok else 1)
