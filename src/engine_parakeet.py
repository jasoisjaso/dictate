"""Parakeet TDT 0.6B v3 engine via sherpa-onnx (CPU, int8 ONNX).

Second transcription engine next to Whisper (docs/parakeet-engine.md).
Why it exists: 6.32% avg WER vs whisper large-v3's 7.44% at ~10-30x realtime
on a plain desktop CPU — for PCs without an NVIDIA card, time-to-text goes
from "noticeable pause" to effectively instant, with native punctuation and
no silence hallucinations.

What it can NOT do (routing + UI stay honest about all of these):
  - no Bosnian / Serbian (25 EU languages incl. Croatian; see PARAKEET_LANGS)
  - no initial_prompt / hotwords, so no ijekavian anchor and no dictionary
    RECOGNITION biasing (the dictionary still applies as text replacement)
  - no translate modes ("multi", "bs2en", "en2bs" are Whisper-only)

The whole text pipeline (spoken punctuation, fillers, cleanup levels, voice
commands run later in delivery, Ollama polish) is inherited from
engine.TextPipeline — shared code, not a copy. Auto-punctuation is forced
OFF: Parakeet punctuates natively, our heuristic on top double-punctuates.
"""

import logging
import os
import threading

import numpy as np

try:
    from .engine import TextPipeline, _build_lexicon
except ImportError:
    from engine import TextPipeline, _build_lexicon

log = logging.getLogger("dictate.engine_parakeet")

# The 25 languages from the nvidia/parakeet-tdt-0.6b-v3 model card. Quality
# is uneven across them (en/fr strong, community found nl rough) — we market
# English first, the rest are available with expectations set in the UI.
# device.choose_engine() and the Settings warning both derive from this set,
# so code and UI cannot drift apart.
PARAKEET_LANGS = frozenset({
    "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de", "el", "hu",
    "it", "lv", "lt", "mt", "pl", "pt", "ro", "sk", "sl", "es", "sv", "ru",
    "uk",
})

# k2-fsa int8 ONNX export of exactly this model: encoder ~622 MB int8,
# decoder ~12 MB, joiner ~6 MB, tokens.txt. ~640 MB on disk.
HF_REPO = "csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
MODEL_DIR_NAME = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
MODEL_LABEL = "parakeet-tdt-0.6b-v3"   # model_size string shown in the tray


# Peak-normalise before decode. Whisper's frontend shrugs off quiet input;
# the int8 FastConformer transducer audibly doesn't (field report 2026-08-01:
# owner had to lean into the mic). Bring quiet takes up to a healthy peak,
# cap the gain so a silent room isn't amplified into noise soup.
_PEAK_TARGET = 0.9
_GAIN_CAP = 30.0


def _normalize(audio_data: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio_data))) if audio_data.size else 0.0
    if peak < 1e-4 or peak >= _PEAK_TARGET:
        return audio_data
    return audio_data * min(_PEAK_TARGET / peak, _GAIN_CAP)


def sherpa_available() -> bool:
    """True if the sherpa-onnx wheel imports on this machine. Checked by
    create_engine() BEFORE constructing the transcriber, so a missing wheel
    or an unsupported CPU routes to Whisper instead of crashing later."""
    try:
        import sherpa_onnx  # noqa: F401
        return True
    except Exception as ex:
        log.debug("sherpa-onnx unavailable: %s", ex)
        return False


def model_dir(cache_dir: str, override: str = "") -> str:
    """Where the Parakeet model lives. Same models cache Whisper uses,
    flat folder (not HF hub layout) so portable sticks can just copy it."""
    return override or os.path.join(cache_dir, MODEL_DIR_NAME)


def resolve_model_files(d: str) -> dict | None:
    """Locate encoder/decoder/joiner/tokens inside a model dir, preferring
    int8 files. Returns None if any piece is missing (=> needs download).
    Glob-based so a rename upstream (encoder.int8.onnx vs encoder.onnx)
    doesn't strand users."""
    import glob
    out = {}
    for stem in ("encoder", "decoder", "joiner"):
        for pattern in (f"{stem}*.int8.onnx", f"{stem}*.onnx"):
            hits = sorted(glob.glob(os.path.join(d, pattern)))
            if hits:
                out[stem] = hits[0]
                break
        else:
            return None
    tokens = os.path.join(d, "tokens.txt")
    if not os.path.exists(tokens):
        return None
    out["tokens"] = tokens
    return out


class ParakeetTranscriber(TextPipeline):
    """sherpa-onnx OfflineRecognizer wrapper matching WhisperTranscriber's
    interface (load / transcribe_audio_buffer / post_process / has_speech /
    try_preview_transcribe / apply_language)."""

    engine_name = "parakeet"

    def __init__(self, cfg: dict):
        p = cfg.get("parakeet", {})
        self.model_size = MODEL_LABEL
        self.device = "cpu"            # v1 is CPU-only (that's its whole point)
        self.compute_type = "int8"
        self.num_threads = int(p.get("num_threads", 0))
        self.model_dir_override = str(p.get("model_dir", "") or "")
        lang = cfg.get("whisper", {}).get("language", "en")
        self.apply_language(lang)
        # Parakeet punctuates + capitalises natively; auto_punct_when_auto
        # False AND the explicit override below keep our heuristic pass off
        # even if the user forced auto_punctuation=true for a small Whisper
        # model — running it here double-punctuates every sentence.
        self._init_text_pipeline(cfg, lang, auto_punct_when_auto=False)
        if self.auto_punctuation:
            log.info("auto_punctuation forced off on Parakeet "
                     "(native punctuation)")
            self.auto_punctuation = False
        # No hotwords channel in sherpa-onnx transducer decoding. The
        # dictionary still applies as TEXT replacement in post_process.
        self.hotwords = None
        self.initial_prompt = None
        self._model = None
        self._lock = threading.Lock()
        self.active_device = None

    def apply_language(self, lang: str):
        """Parakeet auto-detects among its 25 languages at decode time —
        there is no language parameter to pass. The setting still matters
        for routing (device.choose_engine) and the text pipeline (lexicon,
        filler list), so resolve it exactly like Whisper does."""
        _SYNTHETIC = ("", "auto", "multi", "bs2en", "en2bs")
        self.language = None if lang in _SYNTHETIC else lang
        self.multi_langs = None
        self.task = "transcribe"
        self.translate_to_en = False
        self.translate_to_bs = False
        self._nonen_detected = False
        self._en_detected = False

    # ---- model lifecycle -------------------------------------------------

    def load(self):
        """Create the sherpa-onnx recognizer and warm it up. The model files
        must already be on disk — model_lifecycle.preload() downloads them
        first (with the progress dialog) via first_run.py."""
        with self._lock:
            if self._model is not None:
                return
            import sherpa_onnx
            try:
                from . import paths as _paths
            except ImportError:
                import paths as _paths
            d = model_dir(_paths.models_dir(), self.model_dir_override)
            files = resolve_model_files(d)
            if files is None:
                raise RuntimeError(
                    f"Parakeet model files missing in {d} — the download "
                    "must have been interrupted. Reselect the engine to "
                    "retry, or pick Whisper in Settings.")
            threads = self.num_threads or min(4, max(1, os.cpu_count() or 1))
            self._model = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=files["encoder"],
                decoder=files["decoder"],
                joiner=files["joiner"],
                tokens=files["tokens"],
                num_threads=threads,
                model_type="nemo_transducer",
                decoding_method="greedy_search",
            )
            self.active_device = "cpu"
            log.info("parakeet loaded (%d threads, dir=%s)", threads, d)
        # Warm up so the first real dictation doesn't pay ORT session
        # initialisation costs mid-take.
        try:
            self._decode(np.zeros(16000, dtype=np.float32))
            log.info("parakeet warmed up")
        except Exception as ex:
            log.debug("parakeet warmup failed (non-critical): %s", ex)

    def _decode(self, audio_data: np.ndarray) -> str:
        """One offline decode. Caller must NOT hold the lock."""
        with self._lock:
            return self._decode_locked(audio_data)

    def _decode_locked(self, audio_data: np.ndarray) -> str:
        s = self._model.create_stream()
        s.accept_waveform(16000, _normalize(audio_data))
        self._model.decode_stream(s)
        return (s.result.text or "").strip()

    # ---- transcription -----------------------------------------------

    def transcribe_audio_buffer(self, audio_data: np.ndarray,
                                prev_text: str | None = None) -> str:
        """Raw transcription of a float32 mono 16 kHz buffer.

        prev_text is accepted for interface parity with Whisper's streaming
        path but ignored: transducer decoding has no prompt channel. Chunk
        consistency is a non-issue at greedy decode speeds."""
        if audio_data.size < 1600:  # under 0.1 s — nothing to do
            return ""
        self.load()
        text = self._decode(audio_data)
        # No silence-hallucination guard needed: unlike Whisper, the
        # transducer emits nothing on silence (field-verified) — and our
        # empty-result path already toasts "didn't catch that".
        log.debug("raw transcript: %r", text)
        return text

    # Preview cost containment: only re-decode the newest tail. 15 s at
    # ~19x realtime is under a second per pass — fine for a ~1 Hz caption.
    _PREVIEW_WINDOW = 16000 * 15

    @property
    def preview_ok(self) -> bool:
        """Live caption is affordable on CPU here: greedy transducer decode
        runs ~19x realtime and the non-blocking lock keeps it out of the
        way of chunk commits and the final pass."""
        return True

    def try_preview_transcribe(self, audio_data: np.ndarray) -> str | None:
        """Live caption pass. Same contract as Whisper's: return None
        instantly when the lock is busy (a chunk commit or the final pass
        is running) — the preview must never queue behind real work."""
        if audio_data.size < 1600 or self._model is None:
            return None
        if not self._lock.acquire(blocking=False):
            return None
        try:
            return self._decode_locked(audio_data[-self._PREVIEW_WINDOW:])
        except Exception as ex:
            log.debug("preview transcribe failed: %s", ex)
            return None
        finally:
            self._lock.release()
