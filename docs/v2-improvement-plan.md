# Dictate v2 — Improvement Plan (Research + Actionable Roadmap)

Research date: 2026-07-14
Sources: Full codebase audit (all src/ files), git history (19 commits), existing research docs, live web research (OpenWhispr, Wispr Flow, Superwhisper, whisper-amd-windows, Reddit, faster-whisper/CTranslate2 docs, onnxruntime DirectML docs), delegate_cheap (confirmed working).

---

## EXECUTIVE SUMMARY

The app is solid — push-to-talk, per-app profiles, voice commands, filler cleanup, dictionary, history, first-run wizard, packaging. It works. But it doesn't FEEL as polished as Wispr Flow / Superwhisper, some features are broken or incomplete, and AMD GPU users are left on CPU. This plan covers 4 areas:

1. **Overlay/UI overhaul** — make the pill look as good as Wispr Flow
2. **Fix broken features** — copy-last-dictation, install tips, first-run flow
3. **AMD GPU support** — DirectML detection + fallback path
4. **Polish for YouTube** — the things that make it demo-worthy

---

## AREA 1: OVERLAY / UI OVERHAUL (the "doesn't look as nice as Wispr" problem)

### What's wrong now

The overlay (`src/overlay.py`) is a 335-line QWidget with QPainter. It has:
- Glassmorphism colors but NO actual background blur (just alpha=190 translucent dark)
- Waveform bars are 2px wide — thin and basic looking
- No entrance/exit animations — the pill just appears/disappears
- No smooth transitions between recording → processing → idle
- The processing state is just a sine-wave shimmer — looks cheap
- The toast is a plain text box with no animation
- No DPI scaling awareness (fixed pixel sizes)

Wispr Flow's overlay (from competitive analysis) has:
- Real frosted-glass blur behind the pill (acrylic/mica effect)
- Wider, chunkier waveform bars with gradient + glow
- Smooth fade-in/slide-up on appear, fade-out on dismiss
- A pulsing recording indicator (red dot or ring)
- Live transcript that scrolls smoothly
- A subtle shadow underneath for depth

### What to fix (ranked by visual impact)

#### 1.1 Real background blur (HIGH IMPACT, ~2h)

Currently `GLASS_BG = QColor(12, 14, 18, 190)` — just translucent. On Windows 10/11 we can enable native acrylic blur behind the window. PySide6 doesn't expose this directly but we can call the Windows DWMAPI:

```python
# In overlay.py __init__, after setAttribute(WA_TranslucentBackground):
if platform.system() == "Windows":
    import ctypes
    hwnd = int(self.winId())
    # DWMSBT_TRANSIENTWINDOW = 3 (Acrylic-like blur)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, 38,  # DWMWA_SYSTEMBACKDROP_TYPE
        ctypes.byref(ctypes.c_int(3)),  # Acrylic
        ctypes.sizeof(ctypes.c_int))
```

This gives real frosted-glass blur behind the pill — the single biggest visual upgrade.

Fallback: if DWMAPI fails (older Windows), keep the current alpha translucency.

#### 1.2 Chunkier waveform bars with glow (HIGH IMPACT, ~1h)

Current: `BAR_W = 2, BAR_GAP = 2, N_BARS = 48` — 48 tiny 2px bars.
Change to: `BAR_W = 4, BAR_GAP = 3, N_BARS = 32` — fewer but wider bars, more like Wispr/Superwhisper.

Add a glow effect on each bar: draw a wider, more translucent version behind each bar (like the current glow ring but per-bar). This makes the waveform look "alive" and premium.

Add rounded bar caps (already done via `drawRoundedRect`) but make the radius proportional to bar width.

#### 1.3 Entrance/exit animations (HIGH IMPACT, ~2h)

Currently the pill calls `self.show()` and `self.hide()` — instant appear/disappear.

Add a fade + slide-up animation:
- On show: start at opacity 0, y-offset +20px, animate to opacity 1, y-offset 0 over 200ms
- On hide: fade out over 150ms then hide

Use `QPropertyAnimation` on a custom `opacity` property + `pos` property. Or simpler: use `QGraphicsOpacityEffect` + `QPropertyAnimation`.

#### 1.4 Pulsing recording indicator (MEDIUM, ~0.5h)

Add a small pulsing red dot (or ring) at the left edge of the pill when recording. This is the universal "recording" signal that every pro app has. The current glow ring pulse is too subtle.

```python
# Left side: a 8px red dot that pulses opacity 0.5→1.0
dot_x = PAD_X
dot_y = cy
dot_r = 4 + 2 * pulse  # grows slightly
p.setBrush(QColor(224, 82, 82, int(180 + 75 * pulse)))
p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)
```

#### 1.5 Better processing animation (MEDIUM, ~0.5h)

Replace the sine-wave shimmer with three bouncing dots (the universal "thinking" indicator):
- Three small circles that bounce up/down with a phase offset
- Blue color matching the processing palette
- Cleaner and more recognizable than the current shimmer

#### 1.6 Smooth waveform decay (LOW, ~0.5h)

Currently bars jump to their new value instantly. Add smoothing so bars ease toward their target height — gives that liquid, organic feel. The `_smoothed` variable exists for the overall level but individual bars don't smooth.

Store a per-bar smoothed value and lerp toward the target each tick:
```python
for i, target in enumerate(self._levels):
    self._display[i] += (target - self._display[i]) * 0.3
```

#### 1.7 DPI-aware sizing (LOW, ~0.5h)

All constants are hardcoded pixels. On a 4K display at 150% scaling, the pill will look tiny. Use `self.devicePixelRatio()` or `QScreen.physicalDotsPerInch()` to scale the constants.

---

## AREA 2: FIX BROKEN FEATURES

### 2.1 Copy last dictation — add a global hotkey (BROKEN/INCOMPLETE)

**Current state:** `ui.py:225-233` has `_copy_last()` that copies from history to clipboard. It works via the tray menu. BUT:
- There's NO global hotkey for it (user has to right-click tray → Copy last dictation)
- The user said "copy the last transcribe from the program or something that still doesn't work"

**The fix:** Add a configurable global hotkey (default: Ctrl+Shift+C or similar) that triggers `_copy_last()`. This is a 30-minute change:

1. Add `copy_key = "ctrl+shift+c"` to `[hotkeys]` in settings.toml
2. In `_start_hotkeys()`, parse and listen for it
3. In `_on_press()`, emit a `_sig_copy_last` signal
4. Connect signal to `_copy_last()`
5. Add it to the settings GUI key capture
6. Add it to the guide page

**Also:** The clipboard set might fail silently. Add error handling and a toast confirmation (already there: "copied last dictation"). If clipboard fails, try `win32_input.inject_text_via_paste` as a fallback or use `win32clipboard` directly.

### 2.2 Install tips / first-run flow (INCOMPLETE)

**Current state:** `first_run.py` downloads the model with a progress bar. `ui.py:171-178` runs `_first_run_flow()` which opens Settings then the Guide. But:
- No mic test ("speak one line and see it work" moment from the UX research)
- The guide is all text with painted illustrations — fine for adults, but it's a wall of text
- If the model download fails, there's no retry button — just an error
- The settings wizard doesn't validate that the mic actually works

**The fix:**
1. Add a "Test microphone" button in Settings that records 3 seconds, transcribes, and shows the result inline. This is Tier B item #9 from the existing UX research doc and is the #1 thing that makes first-time users trust the app.
2. Add a retry button to the model download error dialog
3. After the first-run wizard + guide, auto-trigger a test dictation (record 3s → transcribe → show toast "I heard: [text]"). This is the "speak one line and watch it work" moment.

### 2.3 Guide dialog — make it work in frozen exe

The guide (`guide.py`) uses `_Illustration` widgets that paint diagrams. This should work in Nuitka frozen exe since it's pure QPainter. But verify:
- The `getattr(self, f"_draw_{self.kind}", self._draw_blank)` dispatch works when frozen (method name resolution can differ)
- QFont("Segoe UI", ...) is available on all Windows installs (it is — it's the system font)
- The guide shows on first run AND is accessible from tray menu (both paths exist, good)

If the guide is crashing silently, the `except Exception: log.exception("guide failed to open")` in `_first_run_flow` swallows it. Check the log file at `%LOCALAPPDATA%\TranscribeDictate\dictate.log` for stack traces.

---

## AREA 3: AMD GPU SUPPORT

### Research findings

**faster-whisper / CTranslate2 does NOT support AMD GPUs.** CTranslate2 only supports CUDA (NVIDIA) and CPU. There is no DirectML or ROCm backend for CTranslate2 on Windows.

**Options for AMD GPU support on Windows:**

| Approach | How it works | Difficulty | Performance | Viability |
|---|---|---|---|---|
| A. onnxruntime-directml | Convert Whisper model to ONNX, run with DirectML execution provider | Hard (different engine) | 8-12x realtime on RX 5700 XT | Best AMD option but requires major engine refactor |
| B. whisper.cpp + DirectML | whisper.cpp has a DirectML backend | Medium (separate binary) | 10-15x realtime | Adds a C++ binary dependency |
| C. ROCm on Windows | Modified CTranslate2 builds | Very hard | Native AMD perf | Only RDNA1+, unstable, not pip-installable |
| D. Detect + document | Detect AMD GPU, show "AMD support coming" message | Trivial | CPU fallback | Honest but not a feature |

### Recommended approach for v2: Detect + graceful fallback + document

Since the user doesn't have an AMD card, building a full DirectML engine path is high-risk. Instead:

**Step 1: AMD GPU detection** (~1h)
Add to `src/device.py`:
```python
def _amd_gpu_present() -> bool:
    """Check for AMD GPU via Windows WMI."""
    try:
        import subprocess
        out = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5)
        return "AMD" in out.stdout.upper() or "Radeon" in out.stdout.upper()
    except Exception:
        return False
```

**Step 2: Update `detect()` to report AMD** (~0.5h)
When CUDA is not available but AMD GPU is present, return a tier with `device="cpu"` but set a flag `amd_gpu=True`. The tray tooltip and settings can then show "AMD GPU detected — using CPU (DirectML support coming soon)".

**Step 3: Settings GUI** (~0.5h)
Show the AMD detection in the settings "Speech recognition" section, with a note: "Your AMD GPU was detected. Dictate currently uses CPU for AMD cards. DirectML GPU acceleration is on the roadmap."

**Step 4: README + YouTube** (~0.5h)
Document AMD support honestly. In the YouTube video, mention it as a roadmap item. This is actually a selling point — you're transparent about limitations, which builds trust.

**Future v3: Full DirectML path** (separate project)
For a future version, the cleanest path is:
- Add `onnxruntime-directml` as an optional dependency
- Convert the faster-whisper model to ONNX format on first run
- Add an `OnnxEngine` class that implements the same interface as `WhisperTranscriber`
- `device.py` picks `OnnxEngine` when AMD GPU is detected and onnxruntime-directml is installed
- This is ~1-2 days of work and needs testing on actual AMD hardware

---

## AREA 4: POLISH FOR YOUTUBE (the stuff that makes it demo-worthy)

### 4.1 Dictation modes (switchable by hotkey) — HIGH DEMO VALUE (~3h)

Superwhisper's headline feature. Add modes: Prose, Code, Command, Email.
- Prose: full cleanup, sentence casing, filler removal (current default)
- Code: verbatim, no casing, no cleanup (like terminal profile but everywhere)
- Command: verbatim + lowercase
- Email: professional tone

Implementation: a hotkey (e.g. Ctrl+Shift+1/2/3/4) cycles modes. The overlay shows the current mode as the profile tag. This is the "Super Mode" the paid apps charge for.

### 4.2 Custom voice macros / snippets — HIGH DEMO VALUE (~2h)

"insert my email" → types your email address. "sign off" → types your signature.
Build on the existing dictionary engine:
```toml
[macros]
"insert my email" = "jaso@example.com"
"sign off" = "Best regards,\nJaso"
"my address" = "123 Brisbane St, QLD 4000"
```
These are multi-word, multi-line expansions — the dictionary already does word→word, just needs to support phrase→block.

### 4.3 Word-per-minute stat in tray — MEDIUM DEMO VALUE (~0.5h)

Already tracks `_session_words`. Add a timer to compute WPM and show it in the tray menu:
`"1,247 words · 142 WPM this session"`
This is a great on-screen stat for the video.

### 4.4 Friendly error toasts — MEDIUM (~1h)

Currently errors either log silently or show a tray balloon. Add overlay toasts for:
- "No microphone detected" (when recorder.start_recording fails)
- "Model still loading — try again in a moment" (when state == LOADING)
- "GPU failed — fell back to CPU" (when engine.load() catches CUDA exception)
- "Didn't catch that" (already exists for empty transcript)

### 4.5 "Redo last as verbatim" — MEDIUM (~1h)

If cleanup mangled something, a hotkey (or voice command "redo verbatim") re-injects the raw transcript without cleanup. Pairs with the existing "scratch that" + Ctrl+Z workflow.

### 4.6 README improvements for YouTube (~0.5h)

- Add an AMD GPU row to the hardware table (even if it says "CPU fallback")
- Add a "Roadmap" section listing: AMD DirectML support, voice macros, dictation modes
- Add screenshot/GIF placeholders (the user can record these for the video)

---

## IMPLEMENTATION ORDER (recommended)

Each item is independently shippable as a commit. Ordered by impact-per-effort for the YouTube video.

| # | Item | Effort | Impact | Area |
|---|------|--------|--------|------|
| 1 | Fix copy-last-dictation global hotkey | 30min | HIGH (broken feature) | 2.1 |
| 2 | AMD GPU detection + graceful message | 1.5h | HIGH (new feature) | 3 |
| 3 | Chunkier waveform bars + glow | 1h | HIGH (visual) | 1.2 |
| 4 | Real background blur (acrylic) | 2h | HIGH (visual) | 1.1 |
| 5 | Entrance/exit animations | 2h | HIGH (visual) | 1.3 |
| 6 | Pulsing recording dot | 30min | MEDIUM (visual) | 1.4 |
| 7 | Better processing animation (bouncing dots) | 30min | MEDIUM (visual) | 1.5 |
| 8 | Mic test in settings | 1.5h | HIGH (first-run) | 2.2 |
| 9 | Friendly error toasts | 1h | MEDIUM (polish) | 4.4 |
| 10 | WPM stat in tray | 30min | MEDIUM (demo) | 4.3 |
| 11 | Voice macros / snippets | 2h | HIGH (demo) | 4.2 |
| 12 | Dictation modes (switchable) | 3h | HIGH (demo) | 4.1 |
| 13 | Smooth waveform decay | 30min | LOW (polish) | 1.6 |
| 14 | "Redo as verbatim" | 1h | MEDIUM (polish) | 4.5 |
| 15 | DPI-aware sizing | 30min | LOW (polish) | 1.7 |
| 16 | README + roadmap update | 30min | LOW (docs) | 4.6 |

**Total estimated effort: ~17 hours** (2-3 solid days)

**Day 1:** Items 1-5 (fix broken feature + AMD detection + the big visual upgrades)
**Day 2:** Items 6-10 (remaining visual + first-run + error handling)
**Day 3:** Items 11-16 (demo features + polish + docs)

---

## TECHNICAL NOTES

### delegate_cheap status
Confirmed working. Tested with deepseek-pro routing. No issues.

### Key files to modify
- `src/overlay.py` — visual overhaul (items 1.1-1.7)
- `src/ui.py` — copy-last hotkey, error toasts, WPM, modes, macros (items 2.1, 4.1-4.5)
- `src/device.py` — AMD detection (item 3)
- `src/settings_gui.py` — mic test, AMD message, mode display (items 2.2, 3, 4.1)
- `src/engine.py` — macro expansion support (item 4.2)
- `src/config.py` — no changes needed (already robust)
- `config/settings.toml` — add copy_key, macros, modes keys
- `README.md` — AMD row, roadmap section

### What NOT to change
- `src/audio.py` — works well, no issues found
- `src/voice_commands.py` — solid implementation
- `src/win32_input.py` — works, clipboard restore logic is correct
- `src/cleanup.py` — filler detection + dictionary is good
- `src/history.py` — simple and correct
- `src/paths.py` — no issues
- `server.py` / `static/index.html` — web transcriber is separate, not in scope
- `src/appcontext.py` — profile detection works fine

### Testing approach
- Pure logic changes (AMD detection, macros, modes): unit tests on WSL with pytest
- UI changes (overlay, animations, blur): manual testing on Windows with the .venv-win environment
- Visual changes: screenshot before/after for YouTube B-roll
