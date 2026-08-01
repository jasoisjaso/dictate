# Parakeet TDT v3 second engine: design

Status: approved 2026-08-01. Target release: v1.6.0.
Prerequisite: the ui.py split (see Rollout, Phase 0).

## 1. Why a second engine

NVIDIA Parakeet TDT 0.6B v3 is the model the local-dictation space converged
on this year, and the numbers justify it:

- 6.32% average WER vs Whisper large-v3's 7.44% on the HF Open ASR
  leaderboard. A 0.6B model beating our best GPU model on accuracy.
- Roughly 10-30x realtime on a plain desktop CPU as int8 ONNX. Whisper
  small (our current CPU-tier default) is 2-4x realtime. For a user without
  an NVIDIA card, time-to-text after releasing the hotkey drops from
  "noticeable pause" to effectively instant.
- No hallucinated text on silence, and native punctuation and casing that
  field reports rate better than Whisper for long-form dictation.
- Battle-tested on Windows: Whispering ships Parakeet as its only Windows
  engine after their Vulkan crash wave, and the HF speech-to-speech stack
  runs it in production as the default STT.

## 2. What Parakeet does NOT do (scope honesty)

These limits shape the whole design. We state them in the UI, not just here.

- No Bosnian, no Serbian. Its 25 European languages include Croatian (hr)
  but not bs or sr. Whether hr output is acceptable to a Bosnian ear is an
  open question that gets a real A/B test (Phase 2) before we route any
  Bosnian user to it.
- No initial_prompt, no hotwords, no custom dictionary. Our ijekavian
  anchor prompt and any prompt-based vocabulary biasing have no Parakeet
  equivalent. Users who rely on custom vocab keep Whisper.
- The bs2en / en2bs translate modes and the "multi" mixed-language mode
  stay Whisper-only, since all of them depend on bs recognition.
- Language quality across the 25 is uneven (community testing found Dutch
  rough, English and French strong). We market it as an English upgrade
  first; everything else is "available, your mileage may vary".

What DOES carry over untouched: the entire text-level pipeline. Spoken
punctuation lexicon, filler removal, cleanup levels, custom dictionary
replacements (text replace, not recognition biasing), voice commands, and
Ollama polish all run on the transcript after the engine returns, so they
work identically on Parakeet output.

## 3. Architecture

### 3.1 Engine abstraction

Both engines sit behind one small protocol so ui.py stops caring which is
loaded:

    class Transcriber(Protocol):
        engine_name: str          # "whisper" | "parakeet"
        language: str | None
        def load(self) -> None
        def transcribe(self, audio: np.ndarray) -> str
        def apply_language(self, lang: str) -> None
        def post_process(self, text: str) -> str

- `WhisperTranscriber` (src/engine.py) already matches this shape; it gets
  the `engine_name` attribute and nothing else changes.
- New `ParakeetTranscriber` (src/engine_parakeet.py) wraps
  sherpa_onnx.OfflineRecognizer with the nemo_transducer model type.
  Post-processing is shared code, imported from the same helpers
  WhisperTranscriber uses today, not copied.

### 3.2 Runtime and model

- Dependency: `sherpa-onnx` from pip. Pulls onnxruntime only; none of the
  heavy NVIDIA NeMo stack. CPU execution provider in v1.
- Model: the k2-fsa int8 export of exactly this model,
  `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8`. Three ONNX files
  (encoder 622 MB, decoder 12 MB, joiner 6 MB) plus tokens.txt, ~640 MB
  total on disk.
- Download: huggingface_hub snapshot_download of the csukuangfj mirror
  repo, reusing the existing first_run.py progress-callback machinery
  (same tqdm subclass trick, same resume support), into the same models
  cache dir Whisper uses. A ~700 MB free-disk check runs before download
  starts; failure surfaces the existing download-error dialog.
- The Parakeet download happens lazily, the first time the engine is
  actually selected. First run stays exactly as it is today (Whisper
  small); a brand-new user on a CPU-only PC gets Parakeet offered by the
  auto rule the first time they land on an English-family language, with
  the download prompt making the 640 MB cost explicit.

### 3.3 Engine routing

One pure function next to choose_tier() in device.py, unit-testable the
same way:

    def choose_engine(engine_cfg: str, tier: Tier, language: str) -> str

Rules, in order:

1. Explicit user choice ("whisper" or "parakeet") always wins, except that
   an unsupported language (bs, sr, auto, multi, bs2en, en2bs) forces
   Whisper with a visible notice, never a silent wrong-language result.
2. engine_cfg == "auto" (default):
   - CPU tier + language in PARAKEET_LANGS -> parakeet.
   - CUDA tier -> whisper (large-v3-turbo with prompts is already
     excellent there, and it keeps dictionary biasing). GPU users can
     still hand-pick Parakeet.
   - Anything else -> whisper.

PARAKEET_LANGS is the 25-code set from the model card, kept in
engine_parakeet.py. The routing table in the settings hint text is
generated from it so UI and code cannot drift apart.

### 3.4 Streaming, preview, auto-punctuation

- Committed-chunk streaming: allowed unconditionally on Parakeet. The
  existing streaming_ok() gate exists because Whisper chunks pile up on
  slow CPUs; at 10-30x realtime that concern is void. The gate becomes
  engine-aware: `streaming_ok(tier, engine)`.
- Live preview stays GPU-Whisper-only in v1 (it re-transcribes the tail
  every second; cheap for Parakeet in theory, but that is a Phase 3
  experiment, not a launch feature).
- The auto-punctuation pass must NOT run on Parakeet output. Parakeet
  emits real punctuation and casing; running our heuristic on top of it
  double-punctuates. The spoken-punctuation lexicon (the user explicitly
  saying "comma") still applies on both engines.

## 4. UI plan

### 4.1 Settings dialog (settings_gui.py, "Speech recognition" group)

New "Engine:" combo above the existing Model row:

    Engine:  [ Auto - pick per language (recommended)   v ]
             [ Whisper - all languages, custom dictionary ]
             [ Parakeet - fastest on CPU, 25 EU languages ]

Behaviour:

- Engine combo drives the Model row. Whisper selected: today's
  MODEL_CHOICES list, unchanged. Parakeet selected: the row shows the
  single v1 entry "Parakeet TDT v3 int8 (~640 MB download)" disabled,
  so users see the cost without a second decision to make.
- Grey hint label under the row, same style as the existing tier hint,
  states the honest trade: "Parakeet: near-instant on CPU, best for
  English. No Bosnian, no custom dictionary biasing. Whisper handles
  those."
- Incompatible combination (Parakeet + bs/sr/translate/multi language):
  inline amber warning appears immediately, and Save stores the choice
  but runtime routing falls back to Whisper for that language. Same
  honest-fallback pattern as the AMD GPU message. No dead dropdowns, no
  silent overrides at save time.
- All new strings go through i18n.py with en + bs entries, following the
  existing bilingual settings convention.

### 4.2 Tray

- Tray tooltip and the History window header line gain the active engine
  name ("Parakeet - en" / "Whisper - bs"), so screenshots in bug reports
  identify the engine for free.
- Model-download progress reuses the existing _on_dl_start/_progress/_done
  signal path; the only change is the label text carries the model name.

### 4.3 Config

    [engine]
    engine = "auto"        # auto | whisper | parakeet

    [parakeet]
    model_dir = ""          # optional override, default: models cache
    num_threads = 0         # 0 = sherpa-onnx default

[whisper] keeps its meaning untouched, so existing user configs and every
current test stay valid.

## 5. Failure modes and fallbacks

Fail-loud-then-degrade, matching the app's existing rules:

- sherpa-onnx import fails (missing wheel, unsupported CPU): log at
  error, one-time tray notice, route to Whisper. The app must never be
  bricked by the optional engine.
- Model download interrupted: huggingface_hub resume handles the retry;
  a hard failure falls back to Whisper for the session and re-offers on
  next engine selection.
- Old CPUs without AVX2: onnxruntime raises at session creation; caught
  and treated as import-failure above.
- Watchdog: the existing transcribe watchdog wraps Parakeet calls the
  same as Whisper calls. Timeout thresholds can stay; Parakeet will
  simply never hit them.

## 6. Packaging

- The sherpa-onnx native wheel gets added to both installer builds. It is
  a Nuitka data-files case (bundled .dll/.so + Python shim); needs the
  same include treatment faster-whisper's ctranslate2 got. Verify with
  tests/smoke_win.py on a machine without a dev environment.
- Installer size impact is the wheel only (~20 MB); the 640 MB model is a
  runtime download, same policy as Whisper models today.
- winget submission (backlog #2) is unaffected: CPU installer only, and
  Parakeet strengthens exactly that story.
- dictate-portable gets the engine after it lands here, as part of the
  standing "bring portable up to date" task, with the model folder under
  the stick's models/ dir next to the whisper ones.

## 7. Rollout

- Phase 0 (prerequisite): split ui.py. 1,200 lines and 47 methods today;
  a second engine multiplies the session-state paths through it. Split
  targets: tray/menu shell, recording session controller, model lifecycle
  (download/preload/ready), workers. No behaviour change, tests stay
  green.
- Phase 1 (the feature): ParakeetTranscriber + choose_engine() + settings
  UI + config plumbing + download flow + tests. English-first messaging.
- Phase 2 (the experiment): 30-minute real-mic A/B, Parakeet-hr vs
  Whisper-bs on Bosnian speech. Decides whether CPU-tier Bosnian users
  ever get auto-routed to Parakeet or whether hr stays opt-in only.
- Phase 3 (maybes, each gated on Phase 1 shipping clean): live preview on
  CPU via Parakeet, GPU execution provider for sherpa-onnx, enabling hr
  routing for bs users if Phase 2 passes.

## 8. Test plan

- choose_engine(): pure-function table tests, every (engine_cfg, tier,
  language) row from the routing matrix, including every unsupported
  language forcing whisper.
- ParakeetTranscriber: interface-level tests with a stubbed
  sherpa_onnx.OfflineRecognizer (CI does not download 640 MB). Asserts:
  lexicon applied, fillers stripped, auto-punct skipped, cleanup levels
  honoured, engine_name propagated.
- Settings round-trip: engine choice persists through save/load, model
  row swaps with engine combo, incompatible-language warning appears and
  clears.
- Manual matrix before release: CPU-only laptop (the actual target
  hardware) and the 4060 Ti dev box; en dictation, en with voice
  commands, bs (must transparently use Whisper), bs2en, one long take
  (2+ min) per engine.

## 9. Sources

- HF Open ASR leaderboard: https://huggingface.co/spaces/hf-audio/open_asr_leaderboard
- Model card: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- sherpa-onnx model page (int8 export, file sizes, Windows usage):
  https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html
- 30-day field report incl. the no-custom-dictionary caveat:
  https://www.reddit.com/r/LocalLLaMA/comments/1nf10ye/30_days_testing_parakeet_v3_vs_whisper/
- Internal research pass that ranked this #1: .hermes/plans/2026-07-21_research-next-phase.md (not in the public repo)
