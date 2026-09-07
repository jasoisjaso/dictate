"""Which modifier is the best push-to-talk key on macOS?

Q4 left a sub-decision open: keep Right Ctrl, or use a Command key. Both are
modifier-only holds, so both go through flagsChanged in pynput's CGEventTap.
This posts synthetic down/hold/up for each candidate and reports whether the
tap sees a clean paired hold — the mechanism half of the answer.

The other half is judgement, not measurement, and is in the round-2 writeup:
while Cmd is held, every other keypress becomes a system shortcut, so a Cmd
hold is a worse PTT key than a Ctrl hold even if both pair fine here.

Virtual keycodes (Carbon HIToolbox kVK_*):
  kVK_RightControl = 0x3E   kVK_Command  = 0x37 (left)
  kVK_RightCommand = 0x36   kVK_RightOption = 0x3D
Device-dependent flag bits distinguish left from right.
"""

import time

import Quartz
from pynput import keyboard

MASK_CONTROL = Quartz.kCGEventFlagMaskControl
MASK_COMMAND = Quartz.kCGEventFlagMaskCommand
MASK_ALTERNATE = Quartz.kCGEventFlagMaskAlternate

# (label, keycode, flags-while-held, pynput name we expect)
CANDIDATES = [
    ("Right Ctrl", 0x3E, MASK_CONTROL | 0x2000, "ctrl_r"),
    ("Left Cmd", 0x37, MASK_COMMAND | 0x0008, "cmd"),
    ("Right Cmd", 0x36, MASK_COMMAND | 0x0010, "cmd_r"),
    ("Right Option", 0x3D, MASK_ALTERNATE | 0x0040, "alt_r"),
]

events = []


def name(key):
    return getattr(key, "name", None) or repr(getattr(key, "char", key))


listener = keyboard.Listener(
    on_press=lambda k: events.append(("down", name(k))),
    on_release=lambda k: events.append(("up", name(k))),
)
listener.start()
time.sleep(1.0)   # let the tap attach before posting


def post_flags(keycode, flags):
    ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
    Quartz.CGEventSetType(ev, Quartz.kCGEventFlagsChanged)
    Quartz.CGEventSetFlags(ev, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


results = []
for label, keycode, flags, expect in CANDIDATES:
    events.clear()
    post_flags(keycode, flags)
    time.sleep(0.35)
    post_flags(keycode, 0)
    time.sleep(0.45)
    seen = [(k, n) for k, n in events]
    mine = [k for k, n in seen if n == expect]
    paired = ("down" in mine and "up" in mine
              and mine.index("down") < mine.index("up"))
    results.append((label, expect, paired, seen))

listener.stop()

print(f"{'candidate':<15}{'pynput name':<14}{'paired hold':<13}events")
for label, expect, paired, seen in results:
    print(f"{label:<15}{expect:<14}{'PASS' if paired else 'FAIL':<13}{seen}")
