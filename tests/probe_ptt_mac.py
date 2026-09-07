"""Throwaway probe: does a MODIFIER-ONLY push-to-talk hold work on macOS?

The one open question in the mac port that paper can't answer. pynput's mac
backend goes through a CGEventTap, and modifier keys arrive as flagsChanged
events, not keyDown/keyUp — so press/release pairing is the thing that could
plausibly be flaky. Run it, hold Right Ctrl, read the transcript.

Prints every key event for WINDOW seconds, then a verdict on whether a clean
down->up pair was observed for ctrl_r with a plausible hold duration.
"""

import sys
import time

WINDOW = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0

from pynput import keyboard  # noqa: E402

events = []
start = time.monotonic()


def stamp():
    return time.monotonic() - start


def name(key):
    return getattr(key, "name", None) or repr(getattr(key, "char", key))


def on_press(key):
    events.append(("down", name(key), stamp()))
    print(f"  {stamp():6.2f}s  DOWN  {name(key)}", flush=True)


def on_release(key):
    events.append(("up", name(key), stamp()))
    print(f"  {stamp():6.2f}s  UP    {name(key)}", flush=True)


print(f"listening {WINDOW:.0f}s — hold RIGHT CTRL for ~2s, release, then tap it twice")
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
time.sleep(WINDOW)
listener.stop()

print("\n--- verdict ---")
ctrl = [e for e in events if e[1] == "ctrl_r"]
if not ctrl:
    others = sorted({e[1] for e in events})
    print(f"NO ctrl_r events seen. keys seen: {others or 'none at all'}")
    print("none at all => the event tap is not receiving input (Accessibility)")
    sys.exit(1)

holds = []
down_at = None
for kind, _, t in ctrl:
    if kind == "down" and down_at is None:
        down_at = t
    elif kind == "up" and down_at is not None:
        holds.append(t - down_at)
        down_at = None

print(f"ctrl_r events: {len(ctrl)}  paired holds: {len(holds)}")
for i, h in enumerate(holds, 1):
    print(f"  hold {i}: {h:.2f}s")
repeats = sum(1 for i in range(1, len(ctrl)) if ctrl[i][0] == ctrl[i - 1][0] == "down")
print(f"auto-repeat DOWNs (app already ignores these): {repeats}")
print("PASS: modifier-hold PTT is viable" if holds else
      "FAIL: no clean down/up pair — needs a non-modifier key or toggle mode")
