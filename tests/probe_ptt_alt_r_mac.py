"""Why does releasing Right Option not stop the Take? (physical key probe)

The synthetic probe (probe_modifier_keys_mac.py) posts flagsChanged events and
sees a clean alt_r down->up pair, so the *mechanism* is fine. The app still
hangs in RECORDING after a real release, which leaves two candidates that only
a real keyboard can tell apart:

  1. the physical Right Option key does not produce a pairable release, or
  2. macOS DISABLES the event tap and pynput never turns it back on.

(2) is the one paper cannot rule out. macOS kills a tap that takes too long in
its callback (kCGEventTapDisabledByTimeout = 0xFFFFFFFE) or during heavy user
input (kCGEventTapDisabledByUserInput = 0xFFFFFFFF). pynput's darwin backend
calls CGEventTapEnable exactly once, at startup, and its handler has no branch
for either notification — so a disabled tap goes quiet forever, which is
indistinguishable from "the key does nothing".

This waits for WORK holds rather than for a clock, so it cannot expire before
a human reaches the keyboard. It exits as soon as it has what it needs.

    .venv/bin/python tests/probe_ptt_alt_r_mac.py [--load] [--holds N]

Hold RIGHT OPTION ~2s, release, repeat. Read the verdict.
"""

import sys
import threading
import time

LOAD = "--load" in sys.argv
WANT_HOLDS = 3
if "--holds" in sys.argv:
    WANT_HOLDS = int(sys.argv[sys.argv.index("--holds") + 1])
DEADLINE = 300.0   # a ceiling so a forgotten probe cannot run forever

from pynput import keyboard  # noqa: E402
from pynput._util import darwin as _darwin  # noqa: E402

# The two notifications macOS sends INSTEAD of an event when it turns a tap
# off. They arrive through the same callback, with a type no normal event has.
TAP_DISABLED_BY_TIMEOUT = 0xFFFFFFFE
TAP_DISABLED_BY_USER_INPUT = 0xFFFFFFFF

start = time.monotonic()
events = []
disabled = []
done = threading.Event()


def stamp():
    return time.monotonic() - start


def name(key):
    return getattr(key, "name", None) or repr(getattr(key, "char", key))


# ---- see what the raw tap callback is handed -------------------------------

_original_handler = _darwin.ListenerMixin._handler


def _spy_handler(self, proxy, event_type, event, refcon):
    if event_type in (TAP_DISABLED_BY_TIMEOUT, TAP_DISABLED_BY_USER_INPUT):
        why = ("TIMEOUT" if event_type == TAP_DISABLED_BY_TIMEOUT
               else "USER_INPUT")
        disabled.append((stamp(), why))
        print(f"  {stamp():6.2f}s  *** TAP DISABLED BY {why} — pynput does "
              f"not re-enable it; every key is dead from here ***", flush=True)
        done.set()
    return _original_handler(self, proxy, event_type, event, refcon)


_darwin.ListenerMixin._handler = _spy_handler


def _pairs():
    """Completed alt_r holds, and whether one is currently open."""
    holds = []
    down_at = None
    for kind, n, t in events:
        if n != "alt_r":
            continue
        if kind == "down" and down_at is None:
            down_at = t
        elif kind == "up" and down_at is not None:
            holds.append(t - down_at)
            down_at = None
    return holds, down_at


def on_press(key):
    events.append(("down", name(key), stamp()))
    print(f"  {stamp():6.2f}s  DOWN  {name(key)}", flush=True)


def on_release(key):
    events.append(("up", name(key), stamp()))
    print(f"  {stamp():6.2f}s  UP    {name(key)}", flush=True)
    holds, _ = _pairs()
    if len(holds) >= WANT_HOLDS:
        done.set()


# ---- optional CPU load, to imitate a Parakeet chunk commit -----------------

stop_load = threading.Event()


def burn():
    while not stop_load.is_set():
        sum(i * i for i in range(200_000))


if LOAD:
    for _ in range(4):   # the engine runs 4 threads
        threading.Thread(target=burn, daemon=True).start()

print(f"WAITING for {WANT_HOLDS} Right Option holds"
      f"{' WITH 4 threads of CPU load' if LOAD else ''}.")
print("Take your time — this does not expire on a short timer.")
print("Hold RIGHT OPTION ~2s, release. Repeat.", flush=True)

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
done.wait(timeout=DEADLINE)
listener.stop()
stop_load.set()

# ---- verdict ---------------------------------------------------------------

print("\n--- verdict ---")
alt = [e for e in events if e[1] == "alt_r"]
if not events:
    print("NO key events at all — not one key of any kind reached the tap.")
    print("Either nothing was pressed, or this process has no Accessibility "
          "grant. (Check: the app that HOSTS this python is the one that "
          "needs the tick, not python itself.)")

holds, open_down = _pairs()
print(f"alt_r events: {len(alt)}   paired holds: {len(holds)}")
for i, h in enumerate(holds, 1):
    print(f"  hold {i}: {h:.2f}s")
if open_down is not None:
    print(f"  UNPAIRED DOWN at {open_down:.2f}s — this is the app's hang: the "
          f"Take starts and no release ever arrives to end it")

other = sorted({n for _, n, _ in events if n != "alt_r"})
if other:
    print(f"other keys seen: {other}")

if disabled:
    print(f"\nTAP WAS DISABLED {len(disabled)} time(s): {disabled}")
    print("ROOT CAUSE: macOS switched the tap off and pynput left it off.")
    sys.exit(2)

ok = len(holds) >= WANT_HOLDS and open_down is None
print("\nPASS: every hold paired, tap never disabled" if ok else
      "\nFAIL: see above")
sys.exit(0 if ok else 1)
