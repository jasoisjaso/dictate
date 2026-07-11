# Transcribe

Two fully local Whisper tools in this folder. No cloud, no API keys, nothing
leaves the PC. Both use faster-whisper (CTranslate2) with large-v3-turbo on
the RTX 4060 Ti.

## 1. Dictate — speak into any Windows app (the "google research.md" build)

Push-to-talk, like Wispr Flow: **hold Right Ctrl, talk, let go** — your words
get typed straight into whatever window has focus. No clipboard involved, so
whatever you had copied stays copied. While you talk, a small dark pill sits
at the bottom-centre of the screen showing a live waveform of your voice; it
turns into a blue shimmer while it transcribes, then vanishes.

Right Ctrl was chosen because, unlike the old Ctrl+Alt+D, it does nothing on
its own in a terminal / PowerShell / WSL, so it never collides with anything.

- Setup (already done on this PC): `setup-windows.bat`
- Start: `dictate.bat`  (tray icon appears; green = ready)
- Tray colours: grey loading, green ready, red recording, blue transcribing
- Esc cancels a recording. Esc does nothing when not recording.

### Trigger options (config `[hotkeys]`)

- `mode = "push_to_talk"` (default): hold `push_to_talk_key`, speak, release.
  Change the key to any of: `ctrl_r`, `alt_r` (Right Alt), `pause`, `menu`,
  `scroll_lock`, `f9`, etc.
- `mode = "toggle"` (hands-free): tap `toggle_key` once to start; it auto-stops
  after `silence_timeout` seconds of silence (or tap again). This is the
  "fire up and just talk" mode — set `toggle_key` to something like `f9`.
- Spoken commands: "period", "full stop", "comma", "question mark",
  "exclamation mark", "colon", "semicolon", "new line", "new paragraph",
  "open/close parenthesis", "bullet point", and "scratch that" (deletes the
  last thing it typed).
- Settings: `config/settings.toml` (hotkey, model, language, auto-stop
  timeout, casing). Restart the app after editing.
- Log: `%LOCALAPPDATA%\TranscribeDictate\dictate.log`
- Verified 2026-07-11: smoke test transcribes the JFK clip in 1.2 s on CUDA
  (`tests\smoke_win.py` — all 7 checks pass).

To start it with Windows automatically: put a shortcut to `dictate.bat` in
`shell:startup`.

### Where the build deviates from google research.md (on purpose)

The blueprint was followed for architecture, config schema, lexicon, DLL
registration and SendInput injection. Four things in it were wrong or
outdated and were corrected after research:

1. `numpy==1.24.4` has no Python 3.12 wheels — the specified install fails.
   Using numpy >=1.26 (pip resolved 2.5.1, works).
2. `nvidia-cudnn-cu12==9.1.0.70` / `cublas==12.1.3.1` pins are stale;
   ctranslate2 4.8.1 runs on current cu12 wheels (cuDNN 9.24 — same versions
   already proven by the Sorted worker on this machine).
3. `pynput==1.7.6` predates Win11 hook fixes; using 1.8.2.
4. The Tkinter click-through overlay (ctypes WS_EX_TRANSPARENT hacks inside a
   PySide6 app = two GUI event loops) was replaced with a native Qt overlay
   using WindowTransparentForInput — same click-through effect, one toolkit.
   Also the blueprint's sample hotkey value was mangled ("++d"); it is
   `ctrl+alt+d` in settings.toml.

## 2. Web app — transcribe files in the browser (WSL)

Drag-and-drop transcription for recordings, videos, voice memos, with SRT/VTT
subtitle export.

```bash
bash run.sh          # then open http://localhost:8737
```

- Any format ffmpeg reads (mp3, m4a, mp4, mkv, webm, …), multiple files queue
- Mic recording in the browser, live progress bars, job history
- Copy button + TXT / SRT / VTT / JSON downloads, timestamps toggle
- Language auto-detect or force, translate-to-English mode
- Model picker: turbo (default), large-v3, distil (fast English), small
- Verified 2026-07-11: JFK clip word-perfect on CUDA, 0.8 s warm

Server code: `server.py` + `static/index.html`. venv lives at
`~/.cache/transcribe/venv` (WSL venvs must stay off /mnt/c). Job data:
`~/.cache/transcribe/data/`.

## Engine facts (researched July 2026)

- faster-whisper = ~4x openai/whisper speed at identical accuracy on NVIDIA.
- large-v3-turbo: OpenAI distilled large-v3 (decoder 32 -> 4 layers), ~1.6 GB,
  near large-v2 accuracy at ~8x speed. No Whisper v4 exists as of June 2026.
- Anti-hallucination: Silero VAD filter on, condition_on_previous_text off.
- NVIDIA Parakeet v3 edges Whisper on English WER (6.34 vs 6.43) but is
  English/EU-only and needs the NeMo stack — skipped deliberately.
