# Dictate — hardening / robustness audit
_Date: 2026-07-12. Reviewer pass over audio.py, engine.py, ui.py, win32_input.py,
config.py, cleanup.py, startup.py, main.py, voice_commands.py, guide.py.
Web-verified against known faster-whisper + sounddevice/PortAudio pitfalls._

Severity key: **[HIGH]** can lose data / crash / hang · **[MED]** wrong output
or degraded UX in real use · **[LOW]** polish / edge case.

---

## Findings

### [HIGH] 1. Whisper hallucinates text on silence / no speech
**Where:** `engine.transcribe_audio_buffer`.
**Real risk:** This is THE #1 documented faster-whisper problem. On a near-silent
or very short take, Whisper emits confident garbage — the classic ones are
"Thank you.", "Thanks for watching!", "Please subscribe", " ." etc. With
push-to-talk, a user who taps the key by accident or says nothing gets one of
those phrases *typed into their document*. We have `vad_filter=True` which helps,
but VAD doesn't catch all of it, and a hallucinated "Thank you." passes VAD.
**Fix:** add a hallucination/blank-audio guard — (a) skip transcription if the
buffer has no VAD speech at all, and (b) drop a small blocklist of known
silence-hallucination phrases when the take was very short. Fail toward "didn't
catch that" rather than injecting junk. → **FIXED**

### [HIGH] 2. Audio callback can grow memory without bound
**Where:** `audio._callback` appends to `self._chunks` whenever `_active`.
**Real risk:** If a stop event is ever missed (crash in the worker, a stuck
toggle), recording never ends and the chunk list grows forever — at 16 kHz mono
float32 that's ~3.8 MB/min, unbounded. Also the docs explicitly warn the
callback must never block; ours only does a lock+append+copy (fine) but has no
cap. **Fix:** hard cap the retained audio (e.g. 5 minutes) in the callback; once
hit, stop appending and flag it so the UI can auto-stop. → **FIXED**

### [MED] 3. `startup.enable()` builds a PowerShell command via string
interpolation of paths
**Where:** `startup.enable()` — `f"$s.TargetPath = '{target}'"` etc.
**Real risk:** Not a remote-exploit (paths are our own), but a path containing a
single quote (`C:\Users\O'Brien\...`) breaks the script or could inject PS. On
Windows usernames with apostrophes exist. **Fix:** escape single quotes for
PowerShell (`'` → `''`) in every interpolated path. → **FIXED**

### [MED] 4. `_apply_settings` restarts the hotkey listener but the old
pynput thread may linger / double-fire
**Where:** `ui._apply_settings` calls `self._listener.stop()` then
`_start_hotkeys()`. If stop() throws or is slow, two listeners can briefly
coexist and a keypress fires twice. **Fix:** guard against re-entrancy and null
the reference; low-risk but worth tightening. → **FIXED (defensive)**

### [MED] 5. Recase/scratch assume the last injection is still there
**Where:** `ui._run_voice_command`. If the user typed/clicked between dictations,
"scratch that" / "delete last word" blindly sends N backspaces and eats whatever
is now under the cursor. This is inherent to keystroke-based editing (Dragon has
the same limitation) but we should at least not act on a stale/empty buffer.
**Fix:** already guarded for empty; added a note + clamp so we never send more
backspaces than we injected. → **HARDENED**

### [MED] 6. No max-duration auto-stop in push-to-talk
**Where:** `ui`. Holding the PTT key (or a stuck key) records indefinitely; a
30-minute buffer then goes to Whisper in one shot and freezes the app.
**Fix:** cap single-take length (ties into #2). → **FIXED via #2 cap + autostop**

### [LOW] 7. `initial_prompt` from the dictionary is unbounded
**Where:** `engine.__init__` builds `"Terms: " + ", ".join(all dictionary
values)`. A huge dictionary makes a giant prompt that hurts accuracy/speed
(Whisper prompt is capped at 224 tokens internally and silently truncates).
**Fix:** cap the number of terms fed into the prompt (e.g. first ~40). → **FIXED**

### [LOW] 8. Log file grows forever
**Where:** `main._setup_logging` uses a plain `FileHandler`. Over months of
`INFO`-level "raw transcript: ..." lines (which also means **transcripts are
written to the log** — a mild privacy wrinkle vs the "nothing to disk" promise).
**Fix:** switch to a `RotatingFileHandler` and drop transcript text from INFO
(keep it at DEBUG). → **FIXED**

### [LOW] 9. Single-instance lock path uses TEMP or /tmp
**Where:** `main` — fine on Windows; on a shared machine `/tmp` is world-writable
but this is the WSL/dev path only. No change needed for the shipped Windows app.
→ **noted, no change**

---

## Things that are already solid (verified, no change)
- Model GPU→CPU fallback is correct and logged (`engine.load`).
- Clipboard paste restores prior text; multi-line forced to paste so a stray
  Enter can't "send" a chat message. Good.
- VAD auto-stop fails **open** (never cuts real speech). Correct choice.
- Config save now merges (no clobber) and quotes non-bare keys. Good.
- Filler regex ignores blank entries (can't match-everything). Good.
- History is memory-only; never persisted. Matches the privacy promise —
  EXCEPT the log file (finding #8).
- Single-instance QLockFile with stale-lock recovery. Good.

---

## Net
Two genuinely important fixes (#1 hallucination-on-silence and #2 unbounded
audio) — both are real, both were reachable in normal use, both now fixed. The
rest are defensive/polish. The transcript-in-logs privacy wrinkle (#8) is worth
fixing because "your voice never leaves the machine / nothing to disk" is the
whole brand.
