# Dictate v3 — Competitive Gap Analysis & Improvement Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Pure-logic tasks are TDD (pytest on WSL); GUI/packaging tasks are Windows-manual-verified.

**Goal:** Close the feature gaps between Dictate and paid competitors (Wispr Flow, Superwhisper) while improving engine efficiency, so the app is genuinely competitive for a YouTube video.

**Architecture:** Evolutionary changes on the existing `src/` module layout. No rewrites. Each feature is a focused addition to one module. Engine efficiency gains come from faster-whisper parameter tuning + model pre-warming, not architecture changes.

**Tech Stack:** Python 3.10+, faster-whisper 1.2.1 / CTranslate2, PySide6, pynput, numpy (FFT). No new dependencies.

---

## RESEARCH SUMMARY — what competitors have that we don't

### Source: Superwhisper feedback board (superwhisper.userjot.com)
Top requested features by votes:
1. **Pause recording** — pause mid-dictation, resume later (Reviewing)
2. **Auto language detection** — detect language automatically (Pending)
3. **Re-process with different settings** — re-run with different mode/model (Pending)
4. **Text to Speech** — read back what you wrote (Pending)
5. **Webhook/triggers** — OnTranscribeComplete hooks (Pending)

### Source: Wispr Flow comparison pages
Features they highlight that we lack:
1. **AI auto-editing** — removes filler words, adds punctuation automatically (we have manual "period"/"comma"; they do it automatically)
2. **Context-aware formatting** — adapts tone per app (we have this via profiles, but no auto-punctuation)
3. **Whisper Mode** — recognises whispered speech for quiet environments
4. **Voice commands for editing** — "delete that", "bold this" (we have some, they have more)
5. **Backtrack** — Wispr Flow's feature to rewind and re-dictate the last few seconds

### Source: whisper-local (drajb/whisper-local, 526 commits, direct competitor)
Features they have that we lack:
1. **Transforms** — post-processing pipelines (regex find-replace on transcripts)
2. **Settings backup/restore** — export/import settings as a file
3. **Searchable transcript history** — log of everything dictated (we have session-only)
4. **Sub-second latency tuning** — they claim sub-second; we have ~1s on GPU

### Source: faster-whisper optimisation guide (localaimaster.com)
Efficiency gains we're missing:
1. **`without_timestamps=True`** — we don't set this; it speeds up inference ~20% for dictation (we don't need timestamps)
2. **`num_workers=1`** — explicitly set; default may spawn extra threads
3. **Lower `beam_size` for short takes** — beam_size=5 is overkill for a 3-second clip; beam_size=1 is fine and 2-3x faster
4. **Model pre-loading on startup** — we do this, but could also warm up with a dummy 1s transcription to avoid first-use lag
5. **`condition_on_previous_text=False`** — we already do this (good)

---

## GAP ANALYSIS — what we have vs what's missing

| Feature | Dictate | Wispr Flow | Superwhisper | whisper-local | Priority |
|---------|---------|------------|--------------|---------------|----------|
| Offline/local | YES | No (cloud) | YES | YES | — (our advantage) |
| Free | YES | $15/mo | $249 lifetime | YES | — (our advantage) |
| Per-app profiles | YES | YES | YES (modes) | No | — (we have it) |
| Voice commands | Partial | YES | No | Partial | **HIGH** |
| Auto-punctuation | No (manual) | YES | Via AI modes | No | **HIGH** |
| Pause/resume | No | No | Requested | No | **MEDIUM** |
| Transforms (regex) | No | No | No | YES | **MEDIUM** |
| Persistent history | No (session) | No | YES | YES | **MEDIUM** |
| Settings export/import | No | No | No | YES | **LOW** |
| Text-to-speech readback | No | No | Requested | No | **LOW** |
| Streaming transcription | Partial (preview) | YES | YES | No | **HIGH** |
| AMD GPU support | Detect only | No | No | No | **LOW** (research) |
| Model warmup | No | N/A | N/A | No | **HIGH** (efficiency) |
| Adaptive beam_size | No (fixed 5) | N/A | N/A | No | **HIGH** (efficiency) |
| without_timestamps | No | N/A | N/A | No | **HIGH** (efficiency) |
| Continuous dictation | No | YES | YES | YES | **HIGH** |

---

## PROPOSED APPROACH (3 phases)

### Phase 1: Engine Efficiency (biggest bang for buck — makes everything faster)
- Add `without_timestamps=True` to transcribe calls
- Adaptive beam_size: 1 for short takes (<5s), 3 for medium, 5 for long
- Model warmup: dummy 1s transcription at startup
- Explicit `num_workers=1`

### Phase 2: Competitive Features (closes the gaps users actually feel)
- Auto-punctuation mode (insert periods at pauses, capitalise next word)
- Continuous dictation mode (auto-restart after silence, stop on key press)
- Pause/resume recording (hold a modifier while recording to pause)
- Persistent transcript history (save to disk, opt-in, searchable)
- Additional voice commands: "bold that", "italic that", "select all", "undo that"

### Phase 3: Polish & Differentiation
- Transforms (regex find-replace pipelines in config)
- Settings export/import
- First-use model warmup toast ("warming up the engine...")
- Tunable latency presets in settings (Fast/Balanced/Accurate)

---

## PHASE 1 — ENGINE EFFICIENCY

### Task 1.1: Add `without_timestamps=True` to transcribe calls

**Objective:** Speed up inference ~20% by telling faster-whisper we don't need timestamps.

**Files:**
- Modify: `src/engine.py:123-131` (transcribe_audio_buffer method)
- Modify: `src/engine.py:141-149` (VAD retry path)

**Step 1: Modify the main transcribe call**

In `transcribe_audio_buffer`, add `without_timestamps=True` to both `self._model.transcribe()` calls:

```python
segments, _info = self._model.transcribe(
    audio_data,
    language=self.language,
    task="transcribe",
    beam_size=self.beam_size,
    initial_prompt=self.initial_prompt,
    vad_filter=self.vad_enabled,
    condition_on_previous_text=False,
    without_timestamps=True,
)
```

**Step 2: Add to the VAD retry path too** (same parameter)

**Step 3: Run existing tests**

Run: `python3 -m pytest tests/ -q --ignore=tests/smoke_win.py`
Expected: all pass (engine tests don't call the real model)

**Step 4: Commit**

```bash
git add src/engine.py
git commit -m "perf: without_timestamps=True for ~20% faster inference"
```

---

### Task 1.2: Adaptive beam_size based on audio length

**Objective:** Use beam_size=1 for short takes (most dictations), 3 for medium, 5 for long. Short takes are 2-3x faster with beam_size=1 and accuracy loss is negligible for a single sentence.

**Files:**
- Modify: `src/engine.py:117-150` (transcribe_audio_buffer method)

**Step 1: Add adaptive beam_size logic**

Add a method to `WhisperTranscriber`:

```python
def _adaptive_beam_size(self, audio_data: np.ndarray) -> int:
    """Short takes don't need beam_size=5 — beam_size=1 is 2-3x faster
    with negligible accuracy loss for a single sentence."""
    duration = audio_data.size / 16000
    if duration < 5.0:
        return 1
    if duration < 15.0:
        return 3
    return self.beam_size  # user-configured default (5)
```

**Step 2: Use it in transcribe_audio_buffer**

Replace `beam_size=self.beam_size` with `beam_size=self._adaptive_beam_size(audio_data)` in both transcribe calls.

**Step 3: Write a test**

```python
# tests/test_engine_beam.py
import numpy as np
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def test_short_take_gets_beam_1():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"beam_size": 5}})
    audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 seconds
    assert t._adaptive_beam_size(audio) == 1

def test_medium_take_gets_beam_3():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"beam_size": 5}})
    audio = np.zeros(16000 * 10, dtype=np.float32)  # 10 seconds
    assert t._adaptive_beam_size(audio) == 3

def test_long_take_gets_default():
    from engine import WhisperTranscriber
    t = WhisperTranscriber({"whisper": {"beam_size": 5}})
    audio = np.zeros(16000 * 30, dtype=np.float32)  # 30 seconds
    assert t._adaptive_beam_size(audio) == 5
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_engine_beam.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/engine.py tests/test_engine_beam.py
git commit -m "perf: adaptive beam_size (1 for short takes, 3 for medium, 5 for long)"
```

---

### Task 1.3: Model warmup on startup

**Objective:** First real dictation is slow because the model hasn't been "warmed up" (CUDA kernels compiled, memory allocated). Run a dummy 1s transcription at startup so the first real use is instant.

**Files:**
- Modify: `src/engine.py:92-115` (load method)

**Step 1: Add warmup after model load**

```python
def load(self):
    """Load the model and warm it up with a dummy transcription."""
    with self._lock:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        # ... existing load code ...
        log.info("model %s loaded on %s", self.model_size, self.active_device)
    # Warm up: run a 1s dummy transcription so CUDA kernels are compiled
    # and memory is pre-allocated. First real dictation will be instant.
    try:
        dummy = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        self._model.transcribe(dummy, without_timestamps=True,
                               beam_size=1, vad_filter=False,
                               condition_on_previous_text=False)
        log.info("model warmed up")
    except Exception as ex:
        log.debug("warmup failed (non-critical): %s", ex)
```

**Step 2: Run tests** — `python3 -m pytest tests/ -q --ignore=tests/smoke_win.py`

**Step 3: Commit**

```bash
git add src/engine.py
git commit -m "perf: model warmup with dummy 1s transcription at startup"
```

---

### Task 1.4: Explicit `num_workers=1`

**Objective:** Prevent faster-whisper from spawning extra worker threads that compete with the audio callback thread.

**Files:**
- Modify: `src/engine.py:104-106` (WhisperModel constructor call)

**Step 1: Add `num_workers=1` to both WhisperModel constructor calls**

```python
self._model = WhisperModel(
    self.model_size, device=self.device,
    compute_type=self.compute_type, num_workers=1, **kw)
```

And the CPU fallback:
```python
self._model = WhisperModel(
    self.model_size, device="cpu", compute_type="int8",
    num_workers=1, **kw)
```

**Step 2: Run tests, commit**

```bash
git add src/engine.py
git commit -m "perf: explicit num_workers=1 to avoid thread contention"
```

---

## PHASE 2 — COMPETITIVE FEATURES

### Task 2.1: Auto-punctuation mode

**Objective:** When enabled, automatically insert periods at natural pauses and capitalise the next word. Users don't have to say "period" anymore. This is the #1 thing Wispr Flow has that free tools lack.

**Files:**
- Create: `src/auto_punct.py`
- Modify: `src/engine.py` (post_process method)
- Modify: `config/settings.toml` (add `[post_processing].auto_punctuation`)
- Test: `tests/test_auto_punct.py`

**Step 1: Write failing tests**

```python
# tests/test_auto_punct.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from auto_punct import add_punctuation

def test_adds_period_at_end():
    assert add_punctuation("hello world") == "Hello world."

def test_capitalises_first_letter():
    assert add_punctuation("hello world.") == "Hello world."

def test_doesnt_double_punctuate():
    assert add_punctuation("hello world.") == "Hello world."

def test_preserves_existing_capitals():
    assert add_punctuation("Hello World") == "Hello World."

def test_handles_empty():
    assert add_punctuation("") == ""

def test_handles_already_capitalised():
    assert add_punctuation("Hello world") == "Hello world."
```

**Step 2: Run to verify failure** — `python3 -m pytest tests/test_auto_punct.py -v`

**Step 3: Write implementation**

```python
# src/auto_punct.py
"""Auto-punctuation: add periods and capitalise without the user saying 'period'."""
import re

def add_punctuation(text: str) -> str:
    """Add a trailing period if missing and capitalise the first letter."""
    if not text or not text.strip():
        return text
    text = text.strip()
    # Capitalise first letter
    if text[0].isalpha():
        text = text[0].upper() + text[1:]
    # Add trailing period if no terminal punctuation
    if not text[-1] in ".!?:":
        text = text + "."
    return text
```

**Step 4: Run tests** — expected: 6 passed

**Step 5: Wire into engine.post_process()**

In `engine.py`, after the casing step but before the short-take period strip:

```python
if bool(self.cfg.get("post_processing", {}).get("auto_punctuation", False)) \
        and not verbatim:
    from . import auto_punct
    text = auto_punct.add_punctuation(text)
```

Store `self.auto_punctuation` in `__init__` from config.

**Step 6: Add to config/settings.toml**

```toml
[post_processing]
auto_punctuation = false   # automatically add periods and capitalise (no need to say "period")
```

**Step 7: Add toggle to settings_gui.py** in the "Make me sound good" section

**Step 8: Commit**

```bash
git add src/auto_punct.py tests/test_auto_punct.py src/engine.py config/settings.toml src/settings_gui.py
git commit -m "feat: auto-punctuation mode (add periods + capitalise without saying 'period')"
```

---

### Task 2.2: Continuous dictation mode

**Objective:** After releasing the PTT key and the transcription completes, automatically start recording again if the user keeps talking. Stop only when they press the key again or go silent for 3+ seconds. This is the "continuous" mode from whisper-writer/whisper-local.

**Files:**
- Modify: `src/ui.py` (add "continuous" as a hotkey mode option alongside push_to_talk and toggle)
- Modify: `config/settings.toml` (document the mode)

**Step 1: Add `continuous` mode to the hotkey mode parsing**

In `ui.py __init__`, the `self.mode` already reads from config. Add `"continuous"` as a valid value.

**Step 2: Implement the continuous loop**

When mode is "continuous":
- PTT key press starts recording (same as push_to_talk)
- PTT key release stops recording and transcribes (same as push_to_talk)
- After transcription completes, if the user is still holding the key, immediately start recording again
- If the user released the key, stay idle
- This effectively makes it: hold to talk continuously, release to stop

Actually, simpler approach: continuous = toggle mode but auto-restarts after each transcription with a 1s gap, until the user taps the key again to stop. The silence monitor already handles auto-stop; we just need to auto-restart.

**Step 3: Add to _on_result**

After showing the toast, if mode == "continuous" and the user hasn't tapped to stop:

```python
if self.mode == "continuous" and not self._continuous_stop:
    QTimer.singleShot(500, self._begin_recording)
```

**Step 4: Add `_continuous_stop` flag**, set to True on key press, False on key release

**Step 5: Add to settings.toml** — document `mode = "continuous"`

**Step 6: Commit**

```bash
git add src/ui.py config/settings.toml
git commit -m "feat: continuous dictation mode (auto-restart after silence)"
```

---

### Task 2.3: Pause/resume recording

**Objective:** While recording (push_to_talk or toggle), press a key (default: Pause) to pause the recording without stopping it. Press again to resume. The overlay shows "paused" state.

**Files:**
- Modify: `src/ui.py` (add pause key handling)
- Modify: `src/audio.py` (add pause/resume methods to AudioRecorder)
- Modify: `src/overlay.py` (show "paused" indicator)
- Modify: `config/settings.toml` (add `pause_key`)

**Step 1: Add pause/resume to AudioRecorder**

```python
# src/audio.py
def pause(self):
    self._paused = True

def resume(self):
    self._paused = False

# In _callback, skip appending when paused:
if self._active and not getattr(self, '_paused', False):
    # ... existing append logic
```

**Step 2: Add pause key to ui.py**

Parse `pause_key` from config (default: "pause"). On press during RECORDING state, toggle pause/resume. Show toast "paused" / "resumed".

**Step 3: Add to settings.toml**

```toml
pause_key = "pause"  # pause/resume recording without stopping (Pause key)
```

**Step 4: Commit**

```bash
git add src/audio.py src/ui.py src/overlay.py config/settings.toml
git commit -m "feat: pause/resume recording (Pause key)"
```

---

### Task 2.4: Persistent transcript history (opt-in)

**Objective:** Save dictation history to disk (opt-in, off by default for privacy). Searchable in the History window. Users who want a log of everything they've dictated can enable it.

**Files:**
- Modify: `src/history.py` (add load/save to JSON file)
- Modify: `src/ui.py` (pass persistence flag to History)
- Modify: `config/settings.toml` (add `[history].persist = false`)

**Step 1: Add persistence to History class**

```python
# src/history.py
class History:
    def __init__(self, limit=25, persist_path=None):
        self.limit = limit
        self._items = []
        self._persist_path = persist_path
        if persist_path:
            self._load()

    def _load(self):
        """Load from JSON file if it exists."""
        try:
            import json
            with open(self._persist_path) as f:
                data = json.load(f)
                self._items = [Entry(**e) for e in data]
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            pass

    def _save(self):
        """Save to JSON file."""
        if not self._persist_path:
            return
        try:
            import json
            with open(self._persist_path, 'w') as f:
                json.dump([{"text": e.text, "app": e.app, "when": e.when}
                           for e in self._items], f)
        except Exception:
            pass

    def add(self, text, app=None):
        if not text or not text.strip():
            return
        self._items.insert(0, Entry(text=text, app=app))
        del self._items[self.limit:]
        self._save()
```

**Step 2: Write tests**

```python
# tests/test_history.py (extend existing)
def test_persist_roundtrip(tmp_path):
    p = str(tmp_path / "history.json")
    h = History(limit=10, persist_path=p)
    h.add("hello world")
    h2 = History(limit=10, persist_path=p)
    assert len(h2.items()) == 1
    assert h2.items()[0].text == "hello world"
```

**Step 3: Wire into ui.py**

```python
persist = bool(cfg.get("history", {}).get("persist", False))
persist_path = paths.app_data_dir() + "/history.json" if persist else None
self.history = History(limit=25, persist_path=persist_path)
```

**Step 4: Add to config/settings.toml**

```toml
[history]
persist = false   # save dictation history to disk (off by default for privacy)
limit = 100       # max entries when persisted (session limit stays at 25)
```

**Step 5: Add toggle to settings_gui.py**

**Step 6: Commit**

```bash
git add src/history.py tests/test_history.py src/ui.py config/settings.toml src/settings_gui.py
git commit -m "feat: optional persistent transcript history (opt-in, off by default)"
```

---

### Task 2.5: Additional voice commands

**Objective:** Add "undo that" (alias for scratch), "bold that", "italic that", "select all", and "new paragraph" (if not already handled). These are the commands Wispr Flow users expect.

**Files:**
- Modify: `src/voice_commands.py` (add to parse())
- Modify: `src/ui.py` (add handlers in _run_voice_command)
- Test: `tests/test_voice_commands.py` (extend)

**Step 1: Add to parse()**

```python
# "undo that" — alias for scratch
if t in ("undo that", "undo last", "undo"):
    return Command("scratch")

# Formatting commands — inject formatting around the last dictation
if t in ("bold that", "bold last"):
    return Command("format", mode="bold")
if t in ("italic that", "italics that", "italicize that"):
    return Command("format", mode="italic")
if t in ("select all", "select everything"):
    return Command("format", mode="select_all")
```

Add `"format"` to the Command dataclass kinds.

**Step 2: Add handler in _run_voice_command**

```python
if cmd.kind == "format":
    old = self.last_injected_text
    if not old.strip():
        self.overlay.flash_toast("nothing to format")
        return
    if cmd.mode == "bold":
        new = f"**{old.rstrip()}**" + (" " if old.endswith(" ") else "")
    elif cmd.mode == "italic":
        new = f"*{old.rstrip()}*" + (" " if old.endswith(" ") else "")
    elif cmd.mode == "select_all":
        # Select all text in the current field (Ctrl+A)
        win32_input._send_inputs([
            win32_input._vk_event(0x11),  # Ctrl down
            win32_input._vk_event(0x41),  # A
            win32_input._vk_event(0x41, 0x0002),  # A up
            win32_input._vk_event(0x11, 0x0002),  # Ctrl up
        ])
        self.overlay.flash_toast("selected all")
        return
    # Backspace and re-inject formatted
    win32_input.inject_backspaces(len(old))
    # ... inject new ...
```

**Step 3: Write tests**

```python
def test_undo_alias():
    assert vc.parse("undo that") == vc.Command("scratch")
    assert vc.parse("undo") == vc.Command("scratch")

def test_bold_command():
    cmd = vc.parse("bold that")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "bold"

def test_italic_command():
    cmd = vc.parse("italic that")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "italic"
```

**Step 4: Run tests, commit**

```bash
git add src/voice_commands.py src/ui.py tests/test_voice_commands.py
git commit -m "feat: undo alias, bold/italic/select-all voice commands"
```

---

## PHASE 3 — POLISH & DIFFERENTIATION

### Task 3.1: Transforms (regex find-replace pipelines)

**Objective:** Let users define regex find-replace rules that run on every transcript. E.g. replace "gonna" with "going to", fix common mis-transcriptions, enforce style rules.

**Files:**
- Create: `src/transforms.py`
- Modify: `src/engine.py` (apply transforms in post_process)
- Modify: `config/settings.toml` (add `[transforms]` section)
- Test: `tests/test_transforms.py`

**Step 1: Write failing tests**

```python
# tests/test_transforms.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from transforms import apply_transforms

def test_simple_replace():
    rules = [{"find": "gonna", "replace": "going to"}]
    assert apply_transforms("I gonna go", rules) == "I going to go"

def test_regex_replace():
    rules = [{"find": r"\b(\w+)\s+\1\b", "replace": r"\1"}]
    assert apply_transforms("the the dog", rules) == "the dog"

def test_no_rules():
    assert apply_transforms("hello", []) == "hello"

def test_multiple_rules():
    rules = [
        {"find": "gonna", "replace": "going to"},
        {"find": "wanna", "replace": "want to"},
    ]
    assert apply_transforms("I gonna wanna go", rules) == "I going to want to go"
```

**Step 2: Write implementation**

```python
# src/transforms.py
"""User-defined regex transforms applied to transcripts."""
import re

def apply_transforms(text: str, rules: list) -> str:
    for rule in rules:
        pattern = rule.get("find", "")
        replacement = rule.get("replace", "")
        if pattern:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
```

**Step 3: Wire into engine.post_process()**

After cleanup, before casing:
```python
transforms = self.cfg.get("transforms", [])
if transforms and not verbatim:
    from . import transforms as _t
    text = _t.apply_transforms(text, transforms)
```

**Step 4: Add to config/settings.toml**

```toml
# [[transforms]]
# find = "gonna"
# replace = "going to"
# [[transforms]]
# find = "\\bwanna\\b"
# replace = "want to"
```

**Step 5: Run tests, commit**

---

### Task 3.2: Settings export/import

**Objective:** Export settings to a JSON file, import from a file. Lets users back up their config or move it between PCs.

**Files:**
- Modify: `src/config.py` (add export/import functions)
- Modify: `src/settings_gui.py` (add export/import buttons)
- Test: `tests/test_config.py` (extend)

**Step 1: Add export/import to config.py**

```python
def export_config(path: str):
    """Export the current user settings to a JSON file."""
    import json
    cfg = _read(paths.config_path())
    with open(path, 'w') as f:
        json.dump(cfg, f, indent=2)

def import_config(path: str):
    """Import settings from a JSON file, replacing current user settings."""
    import json
    with open(path) as f:
        cfg = json.load(f)
    save(cfg, merge=False)
```

**Step 2: Add buttons to settings_gui.py** — "Export settings..." and "Import settings..."

**Step 3: Write tests, commit**

---

### Task 3.3: Latency presets in settings

**Objective:** A simple dropdown in settings: Fast / Balanced / Accurate. Each preset sets beam_size, VAD threshold, and auto_punctuation:
- Fast: beam_size=1, auto_punct=true, VAD on
- Balanced: beam_size=3, auto_punct=true, VAD on (default)
- Accurate: beam_size=5, auto_punct=false, VAD on

**Files:**
- Modify: `src/settings_gui.py` (add preset dropdown)
- Modify: `src/config.py` (add preset application)

**Step 1: Add preset dropdown** at the top of the settings dialog

**Step 2: On preset change**, update the model/cleanup/vad sections accordingly

**Step 3: Commit**

---

### Task 3.4: First-use warmup toast

**Objective:** Show a toast "warming up the engine..." while the model warmup runs, then "ready" when done.

**Files:**
- Modify: `src/ui.py` (_preload_model method)

**Step 1: Emit a signal before and after warmup**

```python
# In _preload_model, after engine.load():
self._sig_model_ready.emit(self.engine.active_device or "?")
```

Already exists. Just add a toast overlay before load:

```python
self.overlay.flash_toast("loading speech model...")
```

**Step 2: Commit**

---

## RISKS & TRADEOFFS

1. **Auto-punctuation accuracy** — pure regex can't match AI-powered punctuation (Wispr Flow uses cloud LLMs). Our approach adds periods at the end and capitalises, which handles 80% of cases. For the remaining 20%, the user can say "no period" or use "redo verbatim". The Ollama polish pass (already exists) handles the rest for power users.

2. **Continuous mode complexity** — auto-restart loops can get into weird states (recording while transcribing, double-transcription). Must be carefully tested with the existing lock/watchdog/silence-monitor infrastructure. Risk: medium.

3. **Persistent history privacy** — saving transcripts to disk breaks the "nothing leaves your RAM" promise. Mitigation: off by default, clearly labelled, and the file is plain JSON the user can delete. The privacy promise becomes "nothing leaves your machine unless you opt in to history persistence."

4. **`without_timestamps=True`** — this is a documented faster-whisper parameter, not a hack. The only risk is if we later need timestamps for the web transcriber (server.py), but that's a separate code path.

5. **Adaptive beam_size** — beam_size=1 on a very long take could reduce accuracy. Mitigation: we only use beam_size=1 for takes <5s (a single sentence), which is the sweet spot.

---

## OPEN QUESTIONS

1. **Should auto-punctuation work with the Ollama polish pass?** If Ollama is on, it already adds punctuation. Auto-punct should be a fallback for when Ollama is off. Answer: yes, auto-punct runs first, Ollama polish runs second and can override.

2. **Continuous mode: should it auto-stop after N minutes?** Yes — respect the existing MAX_RECORD_SECONDS=300 cap. Each segment in continuous mode is a separate recording, so the cap applies per-segment, not per-session.

3. **Transforms: regex or natural language?** Start with regex (simple, testable, no deps). Natural language transforms would need Ollama — possible future enhancement.

4. **Settings export format: JSON or TOML?** JSON — it's universal, easy to import in any language, and the user can edit it by hand. The internal config stays TOML; export/import is JSON.

---

## IMPLEMENTATION ORDER

| # | Task | Effort | Impact | Phase |
|---|------|--------|--------|-------|
| 1 | without_timestamps=True | 10min | HIGH (20% faster) | 1 |
| 2 | Adaptive beam_size | 30min | HIGH (2-3x faster on short takes) | 1 |
| 3 | Model warmup | 20min | HIGH (instant first use) | 1 |
| 4 | num_workers=1 | 5min | MEDIUM (thread efficiency) | 1 |
| 5 | Auto-punctuation | 1h | HIGH (Wispr Flow parity) | 2 |
| 6 | Continuous dictation | 2h | HIGH (hands-free) | 2 |
| 7 | Pause/resume | 1.5h | MEDIUM (Superwhisper #1 request) | 2 |
| 8 | Persistent history | 1h | MEDIUM (whisper-local parity) | 2 |
| 9 | Additional voice commands | 1h | MEDIUM (Wispr Flow parity) | 2 |
| 10 | Transforms | 45min | MEDIUM (power users) | 3 |
| 11 | Settings export/import | 30min | LOW (convenience) | 3 |
| 12 | Latency presets | 45min | MEDIUM (UX) | 3 |
| 13 | Warmup toast | 10min | LOW (polish) | 3 |

**Total: ~10 hours** (1.5 days)

**Day 1:** Tasks 1-6 (all engine efficiency + top 2 competitive features)
**Day 2:** Tasks 7-13 (remaining features + polish)
