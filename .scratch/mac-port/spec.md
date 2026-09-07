# Spec: Dictate on macOS (English)

Status: ready-for-agent
Branch: `mac-port`
Source: grilling rounds 1–3 (Q1–Q22), 2026-09-07. See `CONTEXT.md` and
`docs/adr/0001..0003`.

## Problem Statement

Dictate only runs on Windows. The owner now works on a MacBook Air (M5,
Apple Silicon, macOS 26.6.2) and wants the same thing there: hold a key,
talk, and the words appear at the cursor in whatever app has focus, with
everything running locally.

Today the app does not merely lack polish on macOS — it cannot start its
hotkey listener at all. `parse_key` builds its lookup table eagerly and
names `Key.pause`, `Key.scroll_lock`, `Key.menu` and `Key.insert`, none of
which exist in pynput on macOS, so `HotkeyController.start()` raises
`AttributeError` for *any* key name. Beyond that, every Injection call goes
through the Win32 `SendInput` path, the shipped hotkey defaults name keys
that are absent or hijacked by media functions on an Apple keyboard, user
data lands in a Linux-shaped directory, and the recording overlay would
vanish the moment another app takes focus.

## Solution

A macOS build of Dictate that a person double-clicks, grants Accessibility
to once, and then uses exactly like the Windows version: hold Right Option,
speak, release, words appear. It lives in the menu bar with no Dock icon,
runs the Parakeet Engine on CPU, downloads its Model on first run, and
supports English.

Windows behaviour is unchanged. The two platforms share one Text Pipeline,
one Engine layer, and one Injection interface with two Input Backends
behind it.

## User Stories

1. As a Mac user, I want to launch Dictate and see a microphone icon in my
   menu bar, so that I know it is running without a Dock icon or window
   cluttering my workspace.
2. As a Mac user, I want the app to tell me plainly when it lacks
   Accessibility Permission and open the right System Settings pane, so
   that I am not left holding a key while nothing happens.
3. As a Mac user, I want the app to ask for microphone access the first
   time it records, so that capture does not silently return silence.
4. As a Mac user, I want to hold Right Option and speak, so that I can
   dictate with the key my thumb already rests on.
5. As a Mac user, I want to release Right Option and see my words appear at
   the cursor, so that a Take reaches the app I am actually working in.
6. As a Mac user, I want multi-line text to arrive by Paste rather than
   Type, so that a dictated newline never sends a half-finished chat
   message.
7. As a Mac user, I want short single-line text to arrive by Type, so that
   dictation does not clobber my clipboard.
8. As a Mac user, I want a failed Injection to leave my text on the
   clipboard, so that a dictation is never lost.
9. As a Mac user, I want the voice-edit commands (undo, replace X with Y,
   redo verbatim) to work, so that I can fix a word without touching the
   keyboard.
10. As a Mac user, I want `fn`+F8 to copy my last dictation, so that I keep
    the rescue path when text lands somewhere wrong.
11. As a Mac user, I do not want a default binding that changes my screen
    brightness or skips a track, so that the app never does something
    alarming I did not ask for.
12. As a Mac user, I want the Settings key-picker to offer keys that exist
    on my keyboard, so that I cannot bind something unreachable.
13. As a Mac user, I want to see the recording overlay while I am dictating
    into another app, so that I can tell the app is hearing me.
14. As a Mac user, I want the overlay visible over a full-screen app, so
    that dictating in full-screen is not a blind experience.
15. As a Mac user, I want the overlay text rendered in a font that exists on
    my machine, so that it does not look subtly broken.
16. As a Mac user, I want the Parakeet Model downloaded on first run with a
    progress bar, so that a small download is not a mystery hang.
17. As a Mac user, I want my settings, logs and 640 MB of Models in
    `~/Library/Application Support`, so that they are where I expect and an
    uninstall can find them.
18. As a Mac user, I want the tray to say honestly that it is running on
    CPU, so that I am not left wondering whether it found my GPU.
19. As a Mac user dictating into Terminal, I want verbatim words rather than
    sentence-cased prose, so that App Profiles work the way they do on
    Windows.
20. As a Mac user, I want the tray menu's Quit to actually exit the app, so
    that a menu-bar-only app with no window is not something I have to kill
    from Activity Monitor.
21. As a Windows user, I want every existing behaviour unchanged, so that a
    port to another platform costs me nothing.
22. As the maintainer, I want the full test suite to run on macOS in CI, so
    that a mac change that breaks Windows (or vice versa) is caught without
    me remembering to check.
23. As the maintainer, I want an unavailable key name to log a warning
    rather than crash, so that one missing enum member cannot take down the
    whole app on any platform.
24. As the maintainer, I want one Injection interface with two Input
    Backends, so that `delivery.py` never names an operating system.

## Implementation Decisions

**Engine.** No new Engine. `device.choose_tier()` already returns the CPU
Tier when no CUDA is present, and `device.choose_engine()` already routes
CPU + supported language to Parakeet. English is in `PARAKEET_LANGS`.
Verified on this machine: `detect()` returns
`{device: cpu, compute_type: int8, model_size: small}` and
`choose_engine("auto", cpu_tier, "en")` returns `parakeet`. `mlx-whisper` is
out of scope.

**Injection seam (ADR 0001).** A thin selector module exposes one small
interface — `inject_text`, `paste_text`, `backspaces`, `select_all`, plus
the pure `choose_injection` — and resolves `win32_input` or `mac_input` at
import time. `delivery.py` imports the selector and never branches on OS.
`choose_injection` is pure decision logic and moves up into the shared layer
unchanged, keeping its existing tests.

**macOS Input Backend.** Type via Quartz
`CGEventKeyboardSetUnicodeString`; Paste via `NSPasteboard` plus a
synthesised Cmd+V; backspaces via synthesised Delete; select-all via
Cmd+A. The Windows backend's clipboard save/restore contract is preserved.

**Hotkeys (ADR 0003).** `parse_key` resolves names with
`getattr(keyboard.Key, name, None)` and skips what is missing, falling
through to the existing unknown-key warning. Defaults become per-platform:
macOS push-to-talk is Right Option (`alt_r`); `pause_key` is disabled
because the key does not exist; `copy_key` stays F8 (reachable as `fn`+F8);
`toggle_key`, `mode_cycle_key` and `rerecord_key` are disabled by default on
macOS because `com.apple.keyboard.fnState` is unset by default and a bare
press sends media/brightness. Measured: Right Ctrl, Left Cmd, Right Cmd,
Right Option and the real F6–F9 keycodes all pair cleanly down→up in
pynput's macOS event tap; the choice of Right Option is about what a held
Command does to the target app, not about the tap.

**Paths.** `paths.app_data_dir()` gains a `Darwin` branch returning
`~/Library/Application Support/TranscribeDictate`. Portable mode is
untouched. No migration: nothing is there yet.

**App Profiles.** `appcontext.foreground_exe()` returns the frontmost
application's bundle identifier on macOS (via
`NSWorkspace.frontmostApplication()`), the executable name on Windows. One
`match` list holds both kinds; existing `fnmatch` wildcards need no change.
Shipped defaults gain mac patterns (`com.apple.Terminal`,
`com.googlecode.iterm2`, `com.microsoft.VSCode`) alongside the Windows ones.
Bundle identifier over display name because it is stable and
locale-independent.

**Overlay.** Qt's own flags leave the overlay at `modalPanel` level with
Qt's default collection behaviour, and a `Qt.Tool` window hides when its
app deactivates — fatal for a menu-bar-only app, which is never frontmost.
The prototype (`tests/probe_overlay_mac.py`) established the fix, which Qt
exposes no API for, so the port reaches the NSWindow through `winId()` once
on show:

```
nsw.setLevel_(101)                       # popUpMenu
nsw.setCollectionBehavior_(
    canJoinAllSpaces | stationary | ignoresCycle | fullScreenAuxiliary)
nsw.setHidesOnDeactivate_(False)
nsw.setIgnoresMouseEvents_(True)
```

Measured before/after: level 8 → 101, collectionBehavior 258 → 337, and the
overlay stayed visible after Terminal stole focus (`onActiveSpace=True`).

**Menu-bar-only.** Applied twice, deliberately: `LSUIElement` in the
bundle's Info.plist, and `NSApp.setActivationPolicy_(Accessory)` at startup
so a source run behaves identically to the shipped `.app`.

**Permissions.** `AXIsProcessTrusted()` is checked at startup; when false,
a dialog explains that Dictate needs Accessibility Permission and opens the
System Settings pane. The bundle declares `NSMicrophoneUsageDescription`;
without it the mic prompt never appears and capture silently returns zeros.

**Fonts.** A per-platform `UI_FONT` / `MONO_FONT` pair replaces the 20
`Segoe UI` / `Consolas` literals across `guide.py` and `overlay.py`. Neither
Windows font is installed on macOS; both fall back silently to
`.AppleSystemUIFont` at the wrong metrics for an overlay with fixed pixel
widths. `Menlo` and the system UI font are confirmed present.

**Hardware probes.** `device.py` short-circuits the `nvidia-smi` and `wmic`
probes on Darwin and logs an honest "Apple Silicon — CPU Tier". Behaviour is
already correct by accident; this makes it correct on purpose and gives the
tray something truthful to show.

**Packaging (ADR 0002).** PyInstaller (universal2 wheel, works with the
non-framework uv interpreter already installed), ad-hoc signed
(`codesign -s -`). py2app wants a framework Python; Nuitka compiles for
minutes per iteration. The 640 MB Parakeet Model is downloaded on first run
through the existing resumable path, not bundled.

**Start-on-login.** Not built. `startup.py` stays Windows-only and
`settings_gui.py` already hides the checkbox off-Windows.

## Testing Decisions

A good test here asserts external behaviour: given this text and this
platform, which Injection strategy is chosen; given this key name, does
lookup degrade or crash; given this platform, which directory. It does not
assert that a particular Quartz function was called in a particular order.

The seam to test at is the **Injection interface**, not the OS calls behind
it. `delivery.py`'s 31 call sites collapse to calls against one interface,
so a fake backend recording `(operation, payload)` tuples lets the whole
delivery path — including the voice-edit commands and the whitespace-only
special case — be tested on any platform, including Windows CI. That is one
new seam, and it is the highest available point.

Modules under test: the Injection selector (backend resolution, and that
`choose_injection` keeps its current behaviour), `delivery.py` against a
fake backend, `hotkeys.parse_key` (missing names degrade), `paths`
(per-platform directory), `appcontext.resolve_profile` (bundle identifiers
match), and the per-platform default tables.

Prior art: `tests/test_injection_choice.py` and
`tests/test_clipboard_regression.py` already guard the Windows Injection
path and skip off-Windows; `tests/test_device.py` is the model for pure
table-driven platform tests. Baseline to hold: 246 passed, 4 skipped on
macOS with the code unchanged.

Hardware-dependent behaviour that no unit test can reach — a real key hold,
a real Injection into a real app, the overlay over a full-screen Space, the
Accessibility prompt on a freshly signed bundle — is verified by the probe
scripts in `tests/` and by manual smoke, not faked.

## Out of Scope

- Bosnian, Serbian, and the translate modes (`multi`, `bs2en`, `en2bs`) on
  macOS. The code is shared and stays; it is untested and unsupported there.
- `mlx-whisper` or any Apple-GPU Engine.
- Start-on-login (LaunchAgent).
- A Developer ID signing identity and notarisation.
- Bundling the Model into the `.app`.
- `dictate-portable`, which remains Whisper-only and Windows-only.

## Further Notes

Windows parity is a hard constraint, enforced two ways: the suite must stay
green on macOS *and* Windows, and CI gains a `macos-latest` runner alongside
the existing ubuntu and windows entries.

The ad-hoc signature is a known recurring cost: macOS may treat each rebuilt
`.app` as a new binary identity and re-prompt for Accessibility, leaving a
stale grant for the previous build that silently does nothing. Expect to
re-grant during development.

Menu-bar-only has one hard consequence worth restating: with no Dock icon
and no window, the tray menu's Quit is the only way out.
