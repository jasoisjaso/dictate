"""faster-whisper inference + spoken-command post-processing."""

import logging
import re
import threading

import numpy as np

log = logging.getLogger("dictate.engine")

# Spoken phrase -> replacement. Order matters: longest phrases first so
# "new paragraph" wins over "new line"-style partial hits.
PUNCTUATION_LEXICON = [
    ("new paragraph", "\n\n"),
    ("open parenthesis", "("),
    ("close parenthesis", ")"),
    ("exclamation mark", "!"),
    ("exclamation point", "!"),
    ("question mark", "?"),
    ("bullet point", "\n\u2022 "),
    ("full stop", "."),
    ("new line", "\n"),
    ("semicolon", ";"),
    ("period", "."),
    ("comma", ","),
    ("colon", ":"),
]

_NO_SPACE_BEFORE = ".,?!:;)"


class WhisperTranscriber:
    """Thread-safe wrapper around one WhisperModel instance."""

    def __init__(self, cfg: dict):
        w = cfg.get("whisper", {})
        self.model_size = w.get("model_size", "large-v3-turbo")
        self.device = w.get("device", "cuda")
        self.compute_type = w.get("compute_type", "float16")
        self.language = w.get("language", "en") or None
        self.beam_size = int(w.get("beam_size", 5))
        self.initial_prompt = w.get("initial_prompt", "") or None
        self.vad_enabled = bool(cfg.get("vad", {}).get("enabled", True))
        self.vad_onset = float(cfg.get("vad", {}).get("onset_threshold", 0.5))
        pp = cfg.get("post_processing", {})
        self.casing = pp.get("casing", "sentence")
        self.strip_short = bool(pp.get("strip_trailing_period_short",
                                       pp.get("strip", True)))
        self._model = None
        self._lock = threading.Lock()
        self.active_device = None

    def load(self):
        """Load the model (slow, do it on a background thread at startup)."""
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel
            try:
                self._model = WhisperModel(
                    self.model_size, device=self.device, compute_type=self.compute_type)
                self.active_device = self.device
            except Exception as ex:
                log.warning("device %r failed (%s); falling back to CPU int8",
                            self.device, ex)
                self._model = WhisperModel(
                    self.model_size, device="cpu", compute_type="int8")
                self.active_device = "cpu"
            log.info("model %s loaded on %s", self.model_size, self.active_device)

    def transcribe_audio_buffer(self, audio_data: np.ndarray) -> str:
        """Raw transcription of a float32 mono 16 kHz buffer."""
        if audio_data.size < 1600:  # under 0.1 s — nothing to do
            return ""
        self.load()
        with self._lock:
            segments, _info = self._model.transcribe(
                audio_data,
                language=self.language,
                task="transcribe",
                beam_size=self.beam_size,
                initial_prompt=self.initial_prompt,
                vad_filter=self.vad_enabled,
                condition_on_previous_text=False,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
        log.info("raw transcript: %r", text)
        return text

    def has_speech(self, audio_data: np.ndarray) -> bool:
        """Silero VAD check used by the live auto-stop monitor."""
        if audio_data.size < 512:
            return False
        try:
            from faster_whisper.vad import VadOptions, get_speech_timestamps
            ts = get_speech_timestamps(
                audio_data, VadOptions(threshold=self.vad_onset))
            return len(ts) > 0
        except Exception as ex:
            log.debug("vad check failed: %s", ex)
            return True  # fail open so auto-stop never cuts off real speech

    # ---- post-processing -----------------------------------------------

    def post_process(self, text: str) -> str:
        if not text:
            return ""
        for phrase, repl in PUNCTUATION_LEXICON:
            # eat punctuation whisper may have attached to the spoken keyword
            text = re.sub(
                rf"[\s,.]*\b{re.escape(phrase)}\b[.,]?",
                repl.replace("\\", "\\\\"),
                text, flags=re.IGNORECASE)
        text = self._fix_spacing(text)
        text = self._apply_casing(text)
        words = re.findall(r"[\w']+", text)
        if self.strip_short and len(words) < 3:
            text = text.rstrip(".")
        return text.strip(" ")

    @staticmethod
    def _fix_spacing(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(rf" +([{re.escape(_NO_SPACE_BEFORE)}])", r"\1", text)
        text = re.sub(r"\( ", "(", text)
        text = re.sub(r"([.,?!:;])(?=[^\s.,?!:;)\d])", r"\1 ", text)
        text = re.sub(r" *\n *", "\n", text)
        return text.strip()

    def _apply_casing(self, text: str) -> str:
        mode = self.casing
        if mode == "upper":
            return text.upper()
        if mode == "lower":
            return text.lower()
        if mode != "sentence":
            return text
        out = []
        cap_next = True
        for ch in text:
            if cap_next and ch.isalpha():
                out.append(ch.upper())
                cap_next = False
            else:
                out.append(ch)
            if ch in ".!?\n":
                cap_next = True
        return "".join(out)
