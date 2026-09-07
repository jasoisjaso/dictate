# 1. One Input Backend interface, two per-OS implementations

Date: 2026-09-07
Status: Accepted

## Context

Injection on Windows lives in `src/win32_input.py`, and `src/delivery.py`
calls into it 31 times across four primitives: type-unicode, paste, backspace
N characters, and select-all. `delivery.py` is the file that decides, per
result, how a dictation reaches the target app, and it is the file where a
mistake loses a user's words rather than merely looking wrong.

Porting to macOS needs the same four primitives, implemented against Quartz
(`CGEventKeyboardSetUnicodeString`) and `NSPasteboard` instead of `SendInput`
and the Win32 clipboard. Three ways to get there were on the table:

1. Rename and extend `win32_input` into a single module that branches per OS.
2. Add a sibling `mac_input.py` and have `delivery.py` import a backend
   resolved at import time.
3. Shim only the calls that break, leaving `delivery.py` otherwise untouched.

Windows must keep working, and there is no Windows machine in the porting
session, so the change has to be one a test suite can guard.

## Decision

Option 2. A thin selector module exposes one small interface —
`inject_text`, `paste_text`, `backspaces`, `select_all`, plus the pure
`choose_injection` — and picks `win32_input` or `mac_input` at import time.
`delivery.py` imports the selector and never names an OS.

`choose_injection` is pure decision logic with no platform calls, so it moves
up into the shared layer unchanged and keeps its existing tests.

## Consequences

`delivery.py` stops being platform-aware, which is the point: the 31 call
sites become 31 calls to one interface, and the Windows behaviour they encode
is preserved by construction rather than by re-reading each one.

The cost is a real interface to maintain. Any new primitive has to be
implemented twice or not at all, and "just call the OS here" stops being
available inside `delivery.py`. That constraint is the reason for the ADR: it
is deliberate, and loosening it later means re-scattering platform checks
through the most dangerous file in the app.

Option 3 was rejected for exactly that reason — it puts `IS_WINDOWS` branches
inside delivery logic, where each one is a place a dictation can be lost on
one platform and not the other. Option 1 was rejected because a module named
for one platform that implements two is a name that lies.
