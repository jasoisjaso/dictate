# Dictate

Talk instead of type, in any Windows app. Hold a key, speak, and your words appear where your cursor is. Everything runs on your own PC: no cloud, no account, no subscription, and your voice never leaves your machine.

Built on OpenAI's Whisper (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)), with the polish free tools usually skip: voice commands, per-app profiles, cleanup levels, a personal dictionary, automatic hardware tuning, and a settings window a non-technical person can actually use.

Full Bosnian language support: spoken punctuation, voice commands, and an interface that can run entirely in Bosnian. Skip to the [Bosanski](#bosanski) section below.

## Quick Start (3 steps)

### Step 1: Install

1. Download `Dictate-Setup-cpu.exe` from the [releases page](../../releases).
   - Works on any Windows 10/11 PC. No GPU required.
   - If you have an NVIDIA GPU, grab `Dictate-Setup-gpu.exe` instead (faster and more accurate).
2. Run it. Windows shows a "protected your PC" warning because the installer is not code-signed (certificates cost hundreds of dollars). Click **More info > Run anyway**.
3. It installs to your user folder. No admin password, no UAC prompt.

### Step 2: First Launch

1. On first launch, Dictate downloads the speech model (one time only). A progress bar shows the download.
2. After the download, the model warms up automatically (a few seconds).
3. A **green microphone icon** appears in your system tray (bottom-right). You're ready.

### Step 3: Dictate

1. Click into any text field: Notepad, Word, email, browser, a terminal, anything.
2. **Hold Right Ctrl and talk.** Let go when you're done.
3. Your words appear at the cursor, cleaned up automatically.

That's it. You're dictating. Offline. Free.

---

## How to Use

### Basic Dictation

- **Hold Right Ctrl** and talk. Release when done. Text appears at your cursor.
- A small overlay shows a live visualizer so you know it's hearing you.
- After each dictation, a brief toast shows the word count and an undo hint.
- Tray icon colours: **green** = ready, **red** = recording, **blue** = transcribing.
- If a window refuses typed input (some elevated apps do), your text is automatically copied to the clipboard instead, so a dictation is never lost. Just press Ctrl+V.

### Cleanup Levels

Pick how much Dictate tidies your speech (Settings > Advanced):

| Level | What you get |
|-------|--------------|
| Off | Exactly what you said, only spacing fixed |
| Light | Filler words removed, nothing else touched |
| Standard | Fillers removed, dictionary applied, sentence casing (default) |
| High | Standard plus an AI grammar pass through your local Ollama, if you run one |

Your words stay yours. Even at High, the polish pass is instructed to keep meaning, wording, and tone. Nothing is ever "improved" into something you didn't say, and "redo verbatim" always gets you the raw transcript back.

### Spoken Punctuation

Say these words and they get inserted as punctuation:

| Say | You get | Say | You get |
|-----|---------|-----|---------|
| period | . | comma | , |
| question mark | ? | exclamation mark | ! |
| new line | (new line) | new paragraph | (double new line) |
| semicolon | ; | colon | : |
| open parenthesis | ( | close parenthesis | ) |
| bullet point | (new line bullet) | | |

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

### Hotkeys

| Key | Action |
|-----|--------|
| **Right Ctrl** (hold) | Push-to-talk |
| **F7** | Cycle dictation modes (Auto > Prose > Code > Email) |
| **F8** | Copy last dictation to clipboard |
| **F6** | Delete last dictation and immediately re-record |
| **Pause** | Pause/resume recording mid-take |
| **Esc** | Cancel recording (abort) |
| **F9** | Toggle mode (tap to start/stop, hands-free) |

All keys are configurable in Settings.

### Dictation Modes (F7)

Press **F7** to cycle between modes:

- **Auto** detects the app automatically (terminal = verbatim, chat = casual, email = professional)
- **Prose** is full cleanup with sentence casing (the default behaviour)
- **Code** is verbatim: no casing, no cleanup, for terminals and code editors
- **Email** applies a professional tone

### Per-App Profiles

In Auto mode, Dictate detects which app has focus and adapts:

- **Terminals / IDEs** (PowerShell, VS Code, etc.): verbatim, no auto-casing, no filler removal
- **Chat apps** (Discord, Slack, Teams): casual tone
- **Email** (Outlook, Thunderbird): professional tone

Add your own app rules in `settings.toml` under `[app_profiles]`.

### Filler Word Removal

"Um", "uh", "erm" and other hesitation sounds are stripped automatically. When dictating Bosnian, hesitations like "ovaj" and "hmm" are stripped too, while real words ("pa", "ma", "znači", "dakle") are always kept. Add your own filler words in Settings.

### Personal Dictionary

Teach it names and jargon in Settings > "My words":
- Say "woolies" and it types "Woolworths"
- Dictionary terms also steer Whisper's spelling directly, so unusual names come out right the first time

### Voice Macros

Set up phrases in `settings.toml` under `[macros]` that expand to full blocks of text:
```toml
[macros]
"insert my email" = "your@email.com"
"sign off" = "Best regards,\nYour Name"
```
Say the phrase, get the full block typed.

### Regex Transforms

Define find-and-replace rules in `settings.toml`:
```toml
[[transforms]]
find = "gonna"
replace = "going to"
```

### Visualizer Styles

Pick in Settings:
- **Equalizer**: clean grey bars, minimal and professional
- **Blob**: a morphing colour-shifting orb that deforms with pitch and changes colour as you get louder

### Hands-Free Modes

- **Toggle** (`mode = "toggle"`): tap the key once to start, auto-stops on silence, tap again to stop.
- **Continuous** (`mode = "continuous"`): after each transcription, recording restarts automatically. Keeps listening until you stop it.

### Session History

Right-click the tray icon > **History...** for your last 25 dictations with one-click copy. Toggle "Save history to disk" in Settings to persist across sessions (off by default for privacy).

### Interface Language

The tray menu and notifications are available in English and Bosnian. By default the interface follows your dictation language, so choosing Bosnian dictation gives you a Bosnian interface automatically. Force either language in Settings > Advanced > Interface language.

---

## Bosanski

Dictate govori bosanski. Diktiranje, interpunkcija, glasovne komande i kompletno sučelje aplikacije rade na bosanskom jeziku, i sve to besplatno i bez interneta.

### Brzi početak

1. Preuzmite instalacioni program sa [stranice izdanja](../../releases). Za računare bez NVIDIA grafičke kartice uzmite `Dictate-Setup-cpu.exe`, a sa NVIDIA karticom `Dictate-Setup-gpu.exe`.
2. Pokrenite ga i pratite instalaciju. Nije potrebna administratorska lozinka.
3. U Postavkama izaberite bosanski jezik, zatim kliknite u bilo koje tekstualno polje, držite desni Ctrl i govorite. Riječi se pojavljuju tamo gdje je kursor, u bilo kojoj aplikaciji.

### Izgovorena interpunkcija

| Recite | Dobijete | Recite | Dobijete |
|--------|----------|--------|----------|
| tačka | . | zarez | , |
| upitnik | ? | uzvičnik | ! |
| novi red | (novi red) | novi pasus | (novi pasus) |
| tačka-zarez | ; | dvotačka | : |
| otvorena zagrada | ( | zatvorena zagrada | ) |
| trotačka | ... | navodnici | " |
| znak pitanja | ? | crta | (crta) |

### Glasovne komande

Izgovorite komandu kao poseban diktat (držite tipku, recite samo komandu, pustite):

| Komanda | Šta radi |
|---------|----------|
| obriši to / poništi | Briše cijeli zadnji diktat |
| obriši posljednju riječ | Briše zadnju riječ |
| obriši posljednje dvije riječi | Briše zadnje dvije riječi |
| obriši posljednju rečenicu | Briše zadnju rečenicu |
| zamijeni X sa Y | Zamjenjuje X sa Y u zadnjem diktatu |
| podebljaj | Podebljava zadnji diktat (markdown) |
| iskosi / kurziv | Iskošava zadnji diktat (markdown) |
| označi sve | Označava sav tekst (Ctrl+A) |
| velika slova | Pretvara zadnji diktat u VELIKA SLOVA |
| mala slova | Pretvara zadnji diktat u mala slova |
| ponovi doslovno | Ponovo unosi sirovi transkript, bez dorade |

Komande rade i bez kvačica: "obrisi to" i "obriši to" su ista komanda.

### Sve radi bez interneta

Cijela aplikacija radi lokalno na vašem računaru. Vaš glas se nigdje ne šalje i ništa se ne snima na disk. Prilikom prvog pokretanja preuzima se model za prepoznavanje govora, samo jednom, i poslije toga sve radi potpuno bez interneta. Aplikacija je besplatna, bez pretplate i bez naloga.

### Sučelje na bosanskom

Kada izaberete bosanski jezik diktiranja, meni i obavještenja se automatski prebacuju na bosanski. Jezik sučelja možete i ručno postaviti u Postavke > Advanced > Interface language.

---

## Settings (right-click tray icon > Settings)

| Setting | What it does |
|---------|-------------|
| How you talk to it | Push-to-talk / toggle / continuous mode plus key capture |
| Microphone | Pick a specific mic or system default |
| Model | Auto (recommended) or manual: tiny through large-v3 |
| Language | English, Bosnian, Croatian, Serbian, German, plus 90 more |
| Visualizer | Equalizer or Blob |
| Remove filler words | Strip "um", "uh", "ovaj", etc. |
| Cleanup level | Off / Light / Standard / High |
| Auto-punctuation | Add periods and capitalise automatically |
| My words | Personal dictionary (spoken > typed) |
| Transcribe while talking | Streaming for long dictations (Advanced) |
| AI grammar polish | Local Ollama pass (Advanced) |
| Interface language | Auto / English / Bosanski (Advanced) |
| Start when I log in | One checkbox, no Task Scheduler needed |
| Test your setup | Record 3s and transcribe inline |

---

## Will it run on my PC?

Auto mode detects your hardware and picks the best model:

| Your hardware | What Auto picks | Experience |
|---|---|---|
| NVIDIA GPU, 6 GB+ VRAM | large-v3-turbo, float16 | Best. Instant and accurate |
| NVIDIA GPU, 4.5-6 GB | large-v3-turbo, int8 | Nearly as good |
| NVIDIA GPU, 3-4.5 GB | small, int8 | Fast, good accuracy |
| NVIDIA GPU, under 3 GB | base, int8 | Fast, decent accuracy |
| AMD GPU | small, int8 (CPU) | Works; DirectML support planned |
| No GPU (CPU only) | small, int8 | A beat slower, still good |

If a GPU load fails, Dictate quietly falls back to CPU instead of crashing. If it ever crashes twice in a row on a flaky GPU driver, the next start runs on CPU automatically and tells you.

### Smart features that adapt to your PC

These turn themselves on only when your hardware can afford them. On a weak laptop Dictate stays lean and just transcribes:

| Feature | When it's enabled | What it does |
|---|---|---|
| Streaming transcription | Any NVIDIA GPU; or CPU with 8+ cores on a small model | Long takes are transcribed in chunks while you talk, so text appears near-instantly when you release the key |
| Live preview pill | NVIDIA GPU only | Shows what it's hearing while you speak |
| Ollama grammar polish | Only if a local Ollama server is running | Local LLM grammar pass; picks your best installed model; never blocks dictation |
| Auto-punctuation | Small CPU models only | Adds periods and capitals so you don't say "period" |

All of these accept `"auto"` (default), `true` (force on) or `false` (force off), in Settings > Advanced or in settings.toml.

### Under the hood

- Model warmup at startup, so the first real dictation is instant
- Adaptive beam size: short takes decode 2-3x faster
- Dictionary terms bias Whisper's decoding directly (hotwords)
- VAD speech padding so word edges never get clipped
- Bosnian dictation is anchored to ijekavian orthography with proper diacritics
- Native crash net: CUDA/C++ crashes write a stack trace to crash.log, and the app tells you on the next start
- Auto-update check (about once a day, silent): a tray notification appears when a newer version is out. You can also check manually any time: tray icon > Settings > About > Check for updates. The About tab shows the exact version you are running, and nothing opens or downloads without asking you first.

---

## Privacy

- Audio is processed in memory and thrown away. Nothing is recorded to disk.
- Nothing is uploaded anywhere, ever. The only network traffic is the one-time model download and a tiny daily version check against GitHub (which sends nothing about you).
- The log file records timings and errors only, not the words you dictate.
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

Pure-logic tests run anywhere: `python -m pytest tests -q --ignore=tests/smoke_win.py`. CI runs the suite on Ubuntu and Windows for every push; tagged releases are compiled and published automatically by GitHub Actions.

## Bonus: Web Transcriber (WSL/Linux)

`run.sh` starts a drag-and-drop file transcriber at `http://localhost:8737`. Drop any audio/video file, get TXT/SRT/VTT/JSON out. Same engine, GPU accelerated, handles long recordings.

## License

MIT. Whisper models are MIT (OpenAI); faster-whisper is MIT (SYSTRAN).

## Roadmap

- winget package, so installation is one command with no browser warnings
- Custom modes: your own hotkey + AI prompt combos through local Ollama
- AMD GPU acceleration via DirectML, once upstream support lands
- Voice macros UI in Settings (currently config-file only)
