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
        want_size = w.get("model_size", "auto")
        want_dev = w.get("device", "auto")
        want_ct = w.get("compute_type", "auto")
        if "auto" in (want_size, want_dev, want_ct):
            try:
                from . import device as _device
            except ImportError:
                import device as _device
            tier = _device.detect()
            self.model_size = tier.model_size if want_size == "auto" else want_size
            self.device = tier.device if want_dev == "auto" else want_dev
            self.compute_type = tier.compute_type if want_ct == "auto" else want_ct
        else:
            self.model_size, self.device, self.compute_type = want_size, want_dev, want_ct
        lang = w.get("language", "en")
        self.language = None if lang in ("", "auto") else lang
        self.beam_size = int(w.get("beam_size", 5))
        self.initial_prompt = w.get("initial_prompt", "") or None
        cl = cfg.get("cleanup", {})
        self.remove_fillers = bool(cl.get("remove_fillers", True))
        # Custom filler list: built-in defaults + the user's own words.
        # `custom_fillers` is a list of strings in [cleanup]; single-word or
        # multi-word ("you know") are both fine. Merged case-insensitively.
        try:
            from . import cleanup as _cl_mod
        except ImportError:
            import cleanup as _cl_mod
        extra = cl.get("custom_fillers", []) or []
        if isinstance(extra, str):
            # tolerate a comma-separated string if someone hand-edits the TOML
            extra = [p for p in re.split(r",", extra)]
        merged = list(_cl_mod.FILLERS) + [str(w) for w in extra]
        self.custom_fillers = [w for w in (str(x).strip() for x in extra) if w]
        self.filler_re = _cl_mod._build_filler_re(merged)
        self.ollama_polish = bool(cl.get("ollama_polish", False))
        self.ollama_model = cl.get("ollama_model", "hermes4")
        self.ollama_endpoint = cl.get("ollama_endpoint", "http://127.0.0.1:11434")
        self.dictionary = {str(k): str(v)
                           for k, v in cfg.get("dictionary", {}).items()}
        # spelling boost: nudge Whisper toward the user's proper nouns.
        # Cap the term count — Whisper's prompt is limited to ~224 tokens and
        # silently truncates, and a giant prompt hurts accuracy and speed.
        if self.dictionary and not self.initial_prompt:
            terms = list(dict.fromkeys(self.dictionary.values()))[:40]
            self.initial_prompt = "Terms: " + ", ".join(terms) + "."
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
                from . import paths as _paths
            except ImportError:
                import paths as _paths
            kw = dict(download_root=_paths.models_dir())
            try:
                self._model = WhisperModel(
                    self.model_size, device=self.device,
                    compute_type=self.compute_type, **kw)
                self.active_device = self.device
            except Exception as ex:
                log.warning("device %r/%s failed (%s); falling back to CPU int8",
                            self.device, self.compute_type, ex)
                self.device, self.compute_type = "cpu", "int8"
                self._model = WhisperModel(
                    self.model_size, device="cpu", compute_type="int8", **kw)
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
            # Safety net for real dictation that came back empty: the VAD filter
            # can occasionally strip a whole take (quiet mic, breathy speech),
            # which is exactly the "I spoke a paragraph and nothing appeared"
            # failure. On a substantial take (> ~2s) with an empty result, retry
            # once WITHOUT the VAD filter so we don't silently drop real speech.
            if not text and self.vad_enabled and audio_data.size > 16000 * 2:
                log.info("empty result with VAD on a %.1fs take — retrying "
                         "without VAD filter", audio_data.size / 16000)
                segments, _info = self._model.transcribe(
                    audio_data,
                    language=self.language,
                    task="transcribe",
                    beam_size=self.beam_size,
                    initial_prompt=self.initial_prompt,
                    vad_filter=False,
                    condition_on_previous_text=False,
                )
                text = " ".join(s.text.strip() for s in segments).strip()
        # Guard against Whisper's classic silence hallucinations ("Thank you.",
        # "Thanks for watching!", "Please subscribe"). If the take is short and
        # the whole transcript is a single known hallucination phrase, drop it
        # rather than typing junk into the user's document. A real short "thank
        # you" in a longer sentence is unaffected (whole-string match only).
        try:
            from . import cleanup as _cleanup
        except ImportError:
            import cleanup as _cleanup
        short_take = audio_data.size < 16000 * 2.2  # < ~2.2 s at 16 kHz
        if short_take and _cleanup.is_probable_hallucination(text):
            log.info("dropping probable silence hallucination: %r", text)
            return ""
        log.debug("raw transcript: %r", text)
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

    def post_process(self, text: str, profile: dict | None = None) -> str:
        """profile comes from appcontext.resolve_profile() for the app that
        had focus when recording started. verbatim=True keeps the words
        exactly as spoken (terminals/IDEs); tone feeds the Ollama pass."""
        if not text:
            return ""
        profile = profile or {}
        verbatim = bool(profile.get("verbatim"))
        for phrase, repl in PUNCTUATION_LEXICON:
            # eat punctuation whisper may have attached to the spoken keyword
            text = re.sub(
                rf"[\s,.]*\b{re.escape(phrase)}\b[.,]?",
                repl.replace("\\", "\\\\"),
                text, flags=re.IGNORECASE)
        if verbatim:
            # terminals and editors get the words untouched: no filler
            # stripping, no sentence casing, no trailing-period logic
            return self._fix_spacing(text).strip(" ")
        try:
            from . import cleanup as _cleanup
        except ImportError:
            import cleanup as _cleanup
        text = _cleanup.clean(text, remove_fillers=self.remove_fillers,
                              dictionary=self.dictionary,
                              filler_re=self.filler_re)
        if self.ollama_polish:
            text = _cleanup.ollama_polish(
                text, self.ollama_model, self.ollama_endpoint,
                tone=profile.get("tone"))
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
