# Dictate

Talk instead of type — in any Windows app. Hold a key, say what you want,
let go, and the words appear where your cursor is. Everything runs on your
own PC: no cloud, no account, no subscription, and your voice never leaves
your machine.

Built on OpenAI's Whisper (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)),
with the polish the free tools usually skip: filler-word cleanup, a personal
dictionary, automatic hardware tuning, and a settings window a non-technical
person can actually use.

## Install (no admin rights needed)

1. Download `Dictate-Setup-cpu.exe` (works on every PC) or
   `Dictate-Setup-gpu.exe` (NVIDIA graphics card — faster and more accurate)
   from the releases page.
2. Run it. **Windows will show a blue "Windows protected your PC" warning**
   because this installer isn't code-signed (certificates cost hundreds of
   dollars a year; this project is free). Click **More info → Run anyway**.
   That is the only scary-looking step, and it installs entirely into your
   own user folder — no administrator password, no UAC prompt, nothing
   system-wide is touched.
3. First launch downloads the speech model once (progress bar shows how
   long). After that it works fully offline.

## Use it

- **Hold Right Ctrl and talk. Let go when you're done.** Your words get
  typed into whatever app you're in — email, Word, chat, browser, anything.
- While you talk, a small pill at the bottom of the screen shows a live
  waveform **and a live transcript of what it's hearing** (GPU builds), so
  you know it heard you right before you let go. Blue shimmer = thinking.
- Say punctuation when you want it: "period", "comma", "question mark",
  "new line", "new paragraph", "bullet point".
- **Fix it by voice** — no keyboard needed:
  - **"scratch that"** — delete the whole last dictation
  - **"delete last word"** / **"delete last three words"**
  - **"capitalize that"** / **"all caps that"** / **"lowercase that"**
  - **"redo verbatim"** — re-inject the raw words without cleanup (if the
    post-processing mangled something)
- **Switch modes on the fly** — press **F7** to cycle:
  - **Auto** — detects the app (terminal = verbatim, chat = casual)
  - **Prose** — full cleanup, sentence casing (default)
  - **Code** — verbatim, no casing, no cleanup
  - **Email** — professional tone
- **Copy last dictation** — press **F8** to copy the last result to the
  clipboard. The rescue hatch when text lands in the wrong window.
- After each dictation a small pill briefly shows the **word count + "Ctrl+Z
  to undo"**, so you always know it landed and can take it back.
- Tray icon colours: green = ready, red = recording, blue = transcribing.
- The tray menu shows **words dictated + WPM this session**.
- New here? Right-click the tray icon → **How to use…** for a quick visual
  walkthrough (also shown once on first run).
- Landed in the wrong window? Press **F8** to copy the last dictation, or
  open **History…** for the last 25.

## What makes it different

- **Knows what app you're in.** Dictating into a terminal or IDE? You get
  your words verbatim — no sentence-casing, no cleanup mangling a command.
  Chat apps read casual, email reads professional (tones feed the optional
  local-LLM polish). Add your own app rules in `[app_profiles]` — this is
  the "Super Mode" context awareness the paid tools charge for, running
  100% locally.
- **Live transcript preview** in the pill while you speak (GPU builds) —
  the most-requested dictation feature on Reddit, missing from nearly every
  free tool.
- **Voice macros.** Set up phrases in the config file that expand to full
  blocks of text: say "insert my email" and it types your address; "sign off"
  and it types your signature. Build on the dictionary engine you already have.
- **Dictation modes.** Press F7 to cycle between Auto (per-app detection),
  Prose (full cleanup), Code (verbatim), and Email (professional) — the
  "Super Mode" context awareness the paid tools charge for, running
  100% locally.
- **Smart injection.** Short phrases are typed like real keystrokes; long
  or multi-line text is pasted instantly via a clipboard swap (your
  clipboard is restored afterwards). A typed Enter can't accidentally
  "send" a half-finished chat message.
- **Session history** (tray → History…): every dictation from this session
  with one-click copy — the rescue hatch when text landed in the wrong
  window. Kept in memory only, never written to disk.
- **Audio cues**: a soft beep on record start/stop so you never talk into
  the void. Turn off in `[feedback]`.

## Settings (right-click the tray icon → Settings…)

- **How you talk to it** — hold-a-key (default) or tap-to-start/hands-free,
  with any key you like. Click the key button and press your choice.
- **Microphone** — pick a specific mic or leave on system default.
- **Model** — Auto picks the best for your hardware. Manual choices from
  tiny (fast, rough) to large-v3 (slow, most accurate).
- **Language** — English by default; set your language or Auto-detect.
  Whisper speaks ~99 languages.
- **Make me sound good** — filler-word removal ("um", "uh"), plus **My
  words**: teach it names and jargon ("woolies" → "Woolworths") and it will
  both spell them correctly and expand them as you speak.
- **Start when I log in** — one checkbox, no Task Scheduler fiddling.
- **Test your setup** — record 3 seconds and see the transcription inline,
  so you can validate your mic and model before diving in.

## Will it run on my PC?

Auto mode measures your hardware and picks the strongest model that fits:

| Your hardware              | What Auto picks                | Experience              |
|----------------------------|--------------------------------|-------------------------|
| NVIDIA GPU, 6 GB+ VRAM     | large-v3-turbo, float16        | Best. Instant + accurate|
| NVIDIA GPU, 4.5–6 GB       | large-v3-turbo, int8           | Nearly as good          |
| NVIDIA GPU, 3–4.5 GB       | small, int8                    | Fast, good accuracy     |
| NVIDIA GPU, under 3 GB     | base, int8                     | Fast, decent accuracy   |
| AMD GPU                    | small, int8 (CPU)              | Works; DirectML support planned |
| No GPU (CPU only)          | small, int8                    | A beat slower, still good|

You can override any of this in Settings. If a GPU load fails for any
reason, Dictate quietly falls back to CPU instead of crashing.

## Privacy

Audio is processed in memory on your machine and thrown away. Nothing is
recorded to disk, nothing is uploaded anywhere, ever. The only network
traffic is the one-time model download from Hugging Face.

The activity log (`%LOCALAPPDATA%\TranscribeDictate\dictate.log`) records
timings and errors only — the words you dictate are **not** written to it at
the normal log level, and the log auto-rotates so it can't grow without bound.

## Build it yourself (developers)

```
git clone https://gitea.taild045e.ts.net/jaso/transcribe.git
cd transcribe
setup-windows.bat              # creates .venv-win + installs deps (~5 min)
dictate.bat                    # run from source
.venv-win\Scripts\python tests\smoke_win.py   # verify: ALL CHECKS PASSED

packaging\build_nuitka.bat cpu # compile (or "gpu" for the CUDA build)
ISCC packaging\installer.iss   # build the per-user installer (Inno Setup 6)
```

Pure-logic tests run anywhere: `python -m pytest tests -q --ignore=tests/smoke_win.py`.

## Bonus: web transcriber (WSL/Linux)

`run.sh` starts a drag-and-drop file transcriber at `http://localhost:8737`
— drop any audio/video file, get TXT/SRT/VTT/JSON out. Same engine, GPU
accelerated, handles long recordings.

## Roadmap

- **AMD GPU acceleration via DirectML** — run Whisper on AMD graphics cards
  using onnxruntime-directml (no NVIDIA or ROCm required). Currently AMD
  GPUs are detected and the app runs on CPU.
- **Voice macros UI** — a Settings panel for managing voice macros (currently
  config-file only).

## License

MIT. Whisper models are MIT (OpenAI); faster-whisper is MIT (SYSTRAN).
