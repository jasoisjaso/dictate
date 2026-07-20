# Dictate

Talk instead of type — in any Windows app. Hold a key, speak, and your words appear where your cursor is. Everything runs on your own PC: no cloud, no account, no subscription, and your voice never leaves your machine.

Built on OpenAI's Whisper (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)), with the polish the free tools usually skip: voice commands, per-app profiles, a personal dictionary, automatic hardware tuning, and a settings window a non-technical person can actually use.

Full **Bosnian language** support — spoken punctuation, voice commands, and filler-word removal.

## Quick Start (3 steps)

### Step 1: Install

1. Download `Dictate-Setup-cpu.exe` from the [releases page](../../releases).
   - Works on any Windows 10/11 PC. No GPU required.
   - If you have an NVIDIA GPU, grab `Dictate-Setup-gpu.exe` instead (faster).
2. Run it. Windows shows a "protected your PC" warning because the installer isn't code-signed (certificates cost hundreds of dollars). Click **More info > Run anyway**.
3. It installs to your user folder — **no admin password, no UAC prompt**.

### Step 2: First Launch

1. On first launch, Dictate downloads the speech model (about 500 MB, one-time only). A progress bar shows the download.
2. After the download, the model warms up automatically (a few seconds).
3. A **green microphone icon** appears in your system tray (bottom-right). You're ready.

### Step 3: Dictate

1. Click into any text field — Notepad, Word, email, browser, a terminal, anything.
2. **Hold Right Ctrl and talk.** Let go when you're done.
3. Your words appear at the cursor, with punctuation and cleanup applied automatically.

That's it. You're dictating. Offline. Free.

---

## How to Use

### Basic Dictation

- **Hold Right Ctrl** and talk. Release when done. Text appears at your cursor.
- A small overlay shows a live visualizer so you know it's hearing you.
- After each dictation, a brief toast shows the word count + undo hint.
- Tray icon colours: **green** = ready, **red** = recording, **blue** = transcribing.

### Spoken Punctuation

Say these words and they get inserted as punctuation:

| Say | You get | Say | You get |
|-----|---------|-----|---------|
| period | . | comma | , |
| question mark | ? | exclamation mark | ! |
| new line | (new line) | new paragraph | (double new line) |
| semicolon | ; | colon | : |
| open parenthesis | ( | close parenthesis | ) |
| bullet point | - (new line bullet) | | |

### Bosnian Punctuation

| Reci | Dobiješ | Reci | Dobiješ |
|------|---------|------|---------|
| tačka | . | zarez | , |
| upitnik | ? | uzvičnik | ! |
| novi red | (novi red) | novi pasus | (novi pasus) |
| tačka-zarez | ; | dvotačka | : |
| otvorena zagrada | ( | zatvorena zagrada | ) |
| trotačka | … | navodnici | " |
| crta | — | | |

### Voice Commands

Say these **as their own dictation** (hold the key, say only the command, release):

| Command | What it does |
|---------|-------------|
| "scratch that" / "undo that" | Delete the whole last dictation |
| "delete last word" | Delete just the last word |
| "delete last three words" | Delete the last N words |
| "delete last sentence" | Delete from the last period to here |
| "capitalize that" | Re-inject with Title Case |
| "all caps that" | Re-inject UPPERCASE |
| "lowercase that" | Re-inject lowercase |
| "bold that" | Wrap last dictation in **markdown bold** |
| "italic that" | Wrap last dictation in *markdown italic* |
| "select all" | Send Ctrl+A (select all text) |
| "replace X with Y" | Find-and-replace in the last dictation |
| "redo verbatim" | Re-inject raw words without cleanup |

### Bosnian Voice Commands

| Komanda | Šta radi |
|---------|---------|
| obriši to / poništi | Obriše zadnji diktat |
| obriši posljednju riječ | Obriše zadnju riječ |
| obriši posljednje dvije riječi | Obriše zadnje dvije riječi |
| obriši posljednje tri riječi | Obriše zadnje tri riječi |
| obriši posljednju rečenicu | Obriše od zadnje tačke |
| podebljaj | **Podebljano** (bold) |
| iskosi | *Iskošeno* (italic) |
| označi sve | Selektuje sve (Ctrl+A) |
| zamijeni X sa Y | Zamijeni riječ X sa Y |
| poništi | Sinonim za obriši to |

### Hotkeys

| Key | Action |
|-----|--------|
| **Right Ctrl** (hold) | Push-to-talk |
| **F7** | Cycle dictation modes (Auto > Prose > Code > Email) |
| **F8** | Copy last dictation to clipboard |
| **F6** | Delete last dictation + immediately re-record |
| **Pause** | Pause/resume recording mid-take |
| **Esc** | Cancel recording (abort) |
| **F9** | Toggle mode (tap to start/stop, hands-free) |

All keys are configurable in Settings.

### Dictation Modes (F7)

Press **F7** to cycle between modes:

- **Auto** — detects the app automatically (terminal = verbatim, chat = casual, email = professional)
- **Prose** — full cleanup, sentence casing (default behaviour)
- **Code** — verbatim, no casing, no cleanup (for terminals and code editors)
- **Email** — professional tone

### Per-App Profiles

In Auto mode, Dictate detects which app has focus and adapts:

- **Terminals / IDEs** (PowerShell, VS Code, etc.) — verbatim: no auto-casing, no filler removal
- **Chat apps** (Discord, Slack, Teams) — casual tone
- **Email** (Outlook, Thunderbird) — professional tone

Add your own app rules in `settings.toml` under `[app_profiles]`.

### Filler Word Removal

"Um", "uh", "erm", and other filler words are stripped automatically. Bosnian fillers (e, ono, znači, dakle, pa, vale, ajde, ma) are also stripped. Add your own in Settings > "Extra filler words to strip".

### Personal Dictionary

Teach it names and jargon in Settings > "My words":
- Say "woolies" → it types "Woolworths"
- Also boosts Whisper's spelling of those words

### Voice Macros

Set up phrases in `settings.toml` under `[macros]` that expand to full blocks of text:
```toml
[macros]
"insert my email" = "your@email.com"
"sign off" = "Best regards,\nYour Name"
```
Say the phrase, get the full block typed.

### Auto-Punctuation

Toggle in Settings. Automatically adds trailing periods and capitalises the first letter — no need to say "period" every time. (Whisper's large models usually punctuate on their own, but this helps on smaller/CPU models.)

### Regex Transforms

Define find-and-replace rules in `settings.toml`:
```toml
[[transforms]]
find = "gonna"
replace = "going to"

[[transforms]]
find = "\\bwanna\\b"
replace = "want to"
```

### Visualizer Styles

Pick in Settings:
- **Equalizer** — clean grey bars (minimal, professional)
- **Blob** — a morphing colour-shifting orb that deforms with pitch and changes colour (green > yellow > red) as you get louder

### Continuous Mode

Set `mode = "continuous"` in settings.toml. After each transcription, Dictate automatically restarts recording after a brief pause. Keeps listening until you tap the key to stop. Hands-free for long writing sessions.

### Toggle Mode

Set `mode = "toggle"`. Tap the key once to start recording (auto-stops on silence). Tap again to stop. Hands-free without holding a key.

### Session History

Right-click the tray icon > **History...** to see your last 25 dictations with one-click copy. Toggle "Save history to disk" in Settings to persist across sessions (off by default for privacy).

### Mic Test

Settings > "Test your setup" > "Record 3s & transcribe". Records 3 seconds, transcribes inline, and shows the result so you can verify your mic and model are working.

### WPM Stat

The tray menu shows your session word count and words-per-minute: "1,247 words · 142 WPM this session".

---

## Settings (right-click tray icon > Settings)

| Setting | What it does |
|---------|-------------|
| How you talk to it | Push-to-talk / toggle / continuous mode + key capture |
| Copy last dictation key | Configurable hotkey (default F8) |
| Cycle modes key | Configurable hotkey (default F7) |
| Re-record last key | Configurable hotkey (default F6) |
| Microphone | Pick a specific mic or system default |
| Model | Auto (recommended) or manual: tiny > large-v3 |
| Language | English, Bosnian, Croatian, Serbian, German, +90 more |
| Visualizer | Equalizer or Blob |
| Remove filler words | Strip "um", "uh", "e", "ono", etc. |
| Auto-punctuation | Add periods + capitalise automatically |
| Extra filler words | Your custom words to strip |
| My words | Personal dictionary (spoken → typed) |
| Save history to disk | Persist dictation history (off by default) |
| Start when I log in | One checkbox, no Task Scheduler needed |
| Test your setup | Record 3s + transcribe inline |

---

## Will it run on my PC?

Auto mode detects your hardware and picks the best model:

| Your hardware | What Auto picks | Experience |
|---|---|---|
| NVIDIA GPU, 6 GB+ VRAM | large-v3-turbo, float16 | Best. Instant + accurate |
| NVIDIA GPU, 4.5-6 GB | large-v3-turbo, int8 | Nearly as good |
| NVIDIA GPU, 3-4.5 GB | small, int8 | Fast, good accuracy |
| NVIDIA GPU, under 3 GB | base, int8 | Fast, decent accuracy |
| AMD GPU | small, int8 (CPU) | Works; DirectML support planned |
| No GPU (CPU only) | small, int8 | A beat slower, still good |

If a GPU load fails, Dictate quietly falls back to CPU instead of crashing.

### Smart features that adapt to your PC (v1.2)

These turn themselves on only when your hardware can afford them — on a weak
laptop Dictate stays lean and just transcribes:

| Feature | When it's enabled | What it does |
|---|---|---|
| Streaming transcription | Any NVIDIA GPU; or CPU with 8+ cores on a small model | Long takes are transcribed in chunks *while you talk* — text appears near-instantly when you release the key |
| Live preview pill | NVIDIA GPU only | Shows what it's hearing while you speak |
| Ollama grammar polish | Only if a local Ollama server is running | Local-LLM grammar pass; picks your best installed model; never blocks dictation |
| Auto-punctuation | Small CPU models only (large models punctuate natively) | Adds periods + capitals so you don't say "period" |

All four accept `"auto"` (default), `true` (force on) or `false` (force off)
in settings.toml.

### Engine Optimizations

- **Model warmup** — dummy 1s transcription at startup so the first real use is instant
- **Adaptive beam_size** — beam_size=1 for short takes (2-3x faster), 5 for long
- **without_timestamps** — 20% faster inference (we don't need timestamps)
- **num_workers=1** — prevents thread contention with audio capture
- **hotwords** — your dictionary terms bias decoding directly (no prompt hijack)
- **VAD speech padding** — 400 ms guard so word edges never get clipped
- **Crash net** — native CUDA/C++ crashes write a stack trace to crash.log

---

## Privacy

- Audio is processed in memory and thrown away. Nothing is recorded to disk.
- Nothing is uploaded anywhere, ever. The only network traffic is the one-time model download from Hugging Face.
- The log file records timings and errors only — not the words you dictate.
- History is session-only by default. Opt-in to persist to disk.

---

## Build from Source (developers)

```
git clone https://github.com/jasoisjaso/dictate.git
cd dictate
setup-windows.bat              # creates .venv-win + installs deps (~5 min)
dictate.bat                    # run from source
.venv-win\Scripts\python tests\smoke_win.py   # verify: ALL CHECKS PASSED

packaging\build_nuitka.bat cpu # compile (or "gpu" for the CUDA build)
ISCC packaging\installer.iss   # build the per-user installer (Inno Setup 6)
```

Pure-logic tests run anywhere: `python -m pytest tests -q --ignore=tests/smoke_win.py`.

## Bonus: Web Transcriber (WSL/Linux)

`run.sh` starts a drag-and-drop file transcriber at `http://localhost:8737` — drop any audio/video file, get TXT/SRT/VTT/JSON out. Same engine, GPU accelerated, handles long recordings.

## License

MIT. Whisper models are MIT (OpenAI); faster-whisper is MIT (SYSTRAN).

## Roadmap

- **AMD GPU acceleration via DirectML** — run Whisper on AMD graphics cards using onnxruntime-directml
- **Voice macros UI** — a Settings panel for managing voice macros (currently config-file only)
- **Streaming text injection** — show words as they're transcribed, not all at once after release
