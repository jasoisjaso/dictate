# Dictate on macOS

Branch: `mac-port` (GitHub `jasoisjaso/dictate`, Gitea `jaso/transcribe`).
Tested on a MacBook Air (Apple Silicon, macOS 26/27) with AirPods and the
built-in mic. Engine: Parakeet TDT v3 (sherpa-onnx, CPU, int8).

## Everyday use

1. Open `dist/Dictate.app` (double-click in Finder, or `open dist/Dictate.app`).
   It lives in the menu bar — there is no Dock icon.
2. Click into the app you want to type into.
3. **Hold Right Option**, wait about a second (Bluetooth mics like AirPods
   take a moment to switch on), talk, then **let go**. The text is typed
   where your cursor is.

| Key | Action |
|---|---|
| Right Option (hold) | Push-to-talk |
| Esc | Abort the current take |
| fn + F8 | Copy the last result (rescue if it landed in the wrong window) |

## Run from source

```bash
cd ~/code/dictate
bash run-mac.sh            # first run creates .venv with uv (Python 3.12)
# or, once .venv exists:
.venv/bin/python -m src.main
```

Accessibility permission attaches to whatever *hosts* the process, so when
running from source it is your terminal app (e.g. Terminal) that must be ticked
under System Settings → Privacy & Security → Accessibility.

## Build Dictate.app

```bash
bash packaging/build_mac_app.sh
```

PyInstaller, then an ad-hoc `codesign`. Output: `dist/Dictate.app` (~284 MB).
Quit any running copy first. Because the signature is ad-hoc, macOS may ask
for Accessibility again after a rebuild (and leave a stale entry for the old
build — remove it and re-add the new one if the hotkey goes dead). See
`docs/adr/0002-mac-app-bundle-and-signing.md`.

**Always rebuild after pulling fixes.** On 2026-10-23 the app in `dist/` was a
Sep-8 build that predated the stuck-key fix, so every take was cut off after
~0.5 s even though the source was already fixed.

## Tests

```bash
.venv/bin/python -m pytest tests -q --ignore=tests/smoke_win.py
```

## Settings

File: `~/Library/Application Support/TranscribeDictate/settings.toml`
Log:  `~/Library/Application Support/TranscribeDictate/dictate.log`

**Dictate rewrites settings.toml when it quits.** Quit it *before* editing the
file by hand, or your edit is overwritten with the in-memory values. Prefer the
Settings window (menu-bar icon → Settings).

## Mac fixes log

| Commit | Fix |
|---|---|
| `f4fc9ad` | A dropped push-to-talk release no longer leaves a take recording forever (event-tap watchdog + hardware key-state poll). |
| `1f68886` | The stuck-key guard must see the key physically **down** before an "up" reading may end a take. Without this, Right Option takes were cut off after ~0.5 s on macOS 26 (the hardware probe can't see Right Option). |
| `42b2e2e` | Showing the overlay no longer steals focus: menu-bar-only mode is applied before `QApplication` (with Qt's foreground-transform opt-out), and focus is handed back to the app you were in, so typed text lands there instead of in Dictate's invisible window. |
| `143ac0b` | A push-to-talk key the built-in keyboard doesn't have (F13–F20, Pause, Insert, Right Ctrl…) falls back to Right Option when no external keyboard is attached. A Windows `push_to_talk_key = "f13"` had been carried over to the MacBook, making the hotkey impossible to press. An attached external keyboard (or an unreadable `ioreg`) keeps your binding. |
| `4e2327e` | Streaming chunks that decode to **empty** are now logged (`chunk X-Ys decoded EMPTY`) — previously that audio was silently marked done and its words lost with no trace. Plus the opt-in take recorder below. |

## Troubleshooting

**Nothing happens when I hold the key.** Check the log for
`hotkeys: ... ptt=alt_r`. If it says another key, quit Dictate, fix
`push_to_talk_key` in settings.toml, relaunch. Check `accessibility
permission: granted` in the log.

**Recording starts then stops instantly.** Log shows `push-to-talk release
was never delivered — ending the take from the hardware key state` right after
the start → you are running an old build. Rebuild (above).

**Sentences go missing.** Look for `decoded EMPTY` lines in the log. To capture
the actual audio for diagnosis, run from source with the take recorder on:

```bash
DICTATE_DUMP_TAKES=~/dictate-takes .venv/bin/python -m src.main
```

Each take is saved as `take-HHMMSS.wav` + `.json` (raw text, final text, every
streaming chunk with its time span and text, peak/RMS level). This writes what
you said to disk, so it is **off unless the variable is set** — delete the
folder when done.

**Another dictation app grabs the same shortcut.** VoiceStudio's own dictation
is switched off on this Mac so it can't compete; don't re-enable it while
using Dictate.
