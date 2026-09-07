# 2. Ship macOS as a PyInstaller .app, ad-hoc signed

Date: 2026-09-07
Status: Accepted

## Context

The macOS build ships as a double-clickable `.app` rather than a source run
from a shell script. That decision forces two more: which bundler, and which
signing identity.

Bundlers considered, checked against this machine:

1. **PyInstaller 6.22.2** — ships a `macosx_10_13_universal2` wheel, does not
   care that the interpreter is a non-framework build.
2. **py2app 0.28.10** — mac-native and the most "correct" answer, but sdist
   only, and it effectively wants a framework Python. The interpreter in use
   reports `PYTHONFRAMEWORK: ''`, so choosing it means rebuilding the Python
   before the first bundle can even be attempted.
3. **Nuitka** — what the Windows build already uses, so it would keep one
   bundler across both platforms. Sdist only, and compiles for minutes per
   iteration.

Signing matters more here than in a normal desktop app, because Accessibility
Permission on macOS is granted to a *binary identity*, and this app cannot
function without it: without the grant, both the hotkey listener and Injection
silently do nothing.

## Decision

PyInstaller, ad-hoc signed (`codesign -s -`), bundled as a menu-bar-only
(accessory) app with no Dock icon.

The 640 MB Parakeet model is **not** bundled. It is downloaded on first run
through the existing resumable download path, the same experience the Windows
CPU installer gives.

## Consequences

The bundle is buildable today, on the interpreter already installed, with fast
enough iteration to debug the permission flow — which is where the real
difficulty lives, not in packaging.

The cost is paid every rebuild: an ad-hoc signature is not a stable identity,
so macOS may treat each rebuilt `.app` as a new program and re-prompt for
Accessibility. During development that means re-granting in System Settings,
repeatedly, and a stale grant for a previous build that silently does nothing.
A real Developer ID would remove this tax and is the upgrade path; it is not a
prerequisite for the port.

Choosing the bundle over a source run also means the permission story changes
identity mid-port rather than after it. That was an accepted trade: shipping
something a person can double-click was judged worth debugging permissions
against the artefact that will actually ship.

Menu-bar-only has one hard consequence: with no Dock icon and no window, the
tray menu's Quit is the **only** way to exit the app. That path has to work
before this is considered done.
