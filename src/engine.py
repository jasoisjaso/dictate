"""faster-whisper inference + spoken-command post-processing."""

import logging
import re
import threading

import numpy as np

log = logging.getLogger("dictate.engine")

# Spoken phrase -> replacement, English. Language packs (lang_bs) are merged
# in per-engine by _build_lexicon(). Sorted longest-first at build time so
# "new paragraph" always wins over partial hits.
PUNCTUATION_EN = [
    ("new paragraph", "\n\n"),
    ("bullet point", "\n\u2022 "),
    ("exclamation mark", "!"),
    ("exclamation point", "!"),
    ("question mark", "?"),
    ("open parenthesis", "("),
    ("close parenthesis", ")"),
    ("full stop", "."),
    ("new line", "\n"),
    ("semicolon", ";"),
    ("period", "."),
    ("comma", ","),
    ("colon", ":"),
]


def _build_lexicon(language: str | None) -> list[tuple[str, str]]:
    """English entries always; Bosnian pack when language is bs/hr/sr or
    auto (mixed-language use). Longest-first so multi-word phrases win."""
    entries = list(PUNCTUATION_EN)
    if language is None or language in ("bs", "hr", "sr"):
        try:
            from . import lang_bs
        except ImportError:
            import lang_bs
        entries += lang_bs.PUNCTUATION
    entries.sort(key=lambda e: len(e[0]), reverse=True)
    return entries


# Backwards-compatible default (tests and post_process fallback)
PUNCTUATION_LEXICON = _build_lexicon(None)

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
        self.lexicon = _build_lexicon(self.language)
        self.beam_size = int(w.get("beam_size", 5))
        self.initial_prompt = w.get("initial_prompt", "") or None
        # Bosnian anchor: when dictating bs/hr/sr and the user has no custom
        # prompt, anchor Whisper to ijekavian orthography with diacritics.
        # Disable with [whisper] bs_anchor = false.
        if (self.initial_prompt is None
                and self.language in ("bs", "hr", "sr")
                and bool(w.get("bs_anchor", True))):
            try:
                from . import lang_bs
            except ImportError:
                import lang_bs
            self.initial_prompt = lang_bs.ANCHOR_PROMPT
        cl = cfg.get("cleanup", {})
        self.remove_fillers = bool(cl.get("remove_fillers", True))
        # Cleanup level: off | light | standard | high.
        #   off      = words exactly as transcribed (spacing fixed only)
        #   light    = fillers stripped + dictionary, no casing/transforms
        #   standard = today's default behaviour
        #   high     = standard + Ollama polish forced on when reachable
        level = str(cl.get("level", "standard")).strip().lower()
        if level not in ("off", "light", "standard", "high"):
            level = "standard"
        self.cleanup_level = level
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
        merged = _cl_mod.default_fillers(lang) + [str(w) for w in extra]
        self.custom_fillers = [w for w in (str(x).strip() for x in extra) if w]
        self.filler_re = _cl_mod._build_filler_re(merged)
        # ollama_polish accepts true / false / "auto".
        #   auto: enabled only if a local Ollama server is actually reachable
        #   (probed once in load(), off the GUI thread). Fail-open either way.
        raw_polish = cl.get("ollama_polish", "auto")
        self.ollama_polish_mode = (raw_polish.strip().lower()
                                   if isinstance(raw_polish, str)
                                   else ("on" if raw_polish else "off"))
        self.ollama_polish = self.ollama_polish_mode == "on"
        self.ollama_available = False  # resolved in load()
        self.ollama_model = cl.get("ollama_model", "hermes4")
        self.ollama_endpoint = cl.get("ollama_endpoint", "http://127.0.0.1:11434")
        self.dictionary = {str(k): str(v)
                           for k, v in cfg.get("dictionary", {}).items()}
        # spelling boost: nudge Whisper toward the user's proper nouns via
        # faster-whisper's dedicated `hotwords` channel. Unlike initial_prompt
        # (which the model treats as preceding TEXT and will happily imitate,
        # e.g. starting transcripts with "Terms: ..."), hotwords only bias
        # decoding. Capped: a huge list dilutes the effect and eats context.
        self.hotwords = None
        if self.dictionary:
            terms = list(dict.fromkeys(self.dictionary.values()))[:40]
            self.hotwords = ", ".join(terms)
        self.vad_enabled = bool(cfg.get("vad", {}).get("enabled", True))
        self.vad_onset = float(cfg.get("vad", {}).get("onset_threshold", 0.5))
        pp = cfg.get("post_processing", {})
        self.casing = pp.get("casing", "sentence")
        # auto_punctuation accepts true / false / "auto".
        #   auto: on only for the small CPU-tier models (tiny/base/small) that
        #   habitually return unpunctuated text; the large models punctuate
        #   natively and double-processing them just adds noise.
        raw_ap = pp.get("auto_punctuation", "auto")
        if isinstance(raw_ap, str) and raw_ap.strip().lower() == "auto":
            self.auto_punctuation = self.model_size in ("tiny", "base", "small")
        else:
            self.auto_punctuation = bool(raw_ap)
        self.strip_short = bool(pp.get("strip_trailing_period_short",
                                       pp.get("strip", True)))
        self.transforms = cfg.get("transforms", []) or []
        self._model = None
        self._lock = threading.Lock()
        self.active_device = None
        self._has_punctuation_payload = False
        self._last_punct_payload = ""

    def load(self):
        """Load the model and warm it up with a dummy transcription."""
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
                    compute_type=self.compute_type, num_workers=1, **kw)
                self.active_device = self.device
            except Exception as ex:
                log.warning("device %r/%s failed (%s); falling back to CPU int8",
                            self.device, self.compute_type, ex)
                self.device, self.compute_type = "cpu", "int8"
                try:
                    self._model = WhisperModel(
                        self.model_size, device="cpu", compute_type="int8",
                        num_workers=1, **kw)
                    self.active_device = "cpu"
                except Exception as ex2:
                    # Last resort (portable stick on an offline host): use ANY
                    # model already cached on disk instead of dying.
                    log.warning("model %r unavailable (%s); trying cached models",
                                self.model_size, ex2)
                    self._model = self._load_any_cached(WhisperModel, kw)
                    self.active_device = "cpu"
            log.info("model %s loaded on %s", self.model_size, self.active_device)
        # Resolve ollama_polish="auto" now that we're on a background thread:
        # probe the local server once; pick the best installed model.
        if self.ollama_polish_mode == "auto":
            try:
                from . import device as _device
            except ImportError:
                import device as _device
            if _device.ollama_ok(self.ollama_endpoint):
                picked = _device.ollama_pick_model(self.ollama_model,
                                                   self.ollama_endpoint)
                if picked:
                    self.ollama_model = picked
                    self.ollama_available = True
                    self.ollama_polish = True
                    log.info("ollama polish auto-enabled (model=%s)", picked)
            else:
                log.info("ollama not reachable — polish stays off")
        elif self.ollama_polish:
            # forced on: trust the config, mark available for level=high
            self.ollama_available = True
        # Warm up: run a 1s dummy transcription so CUDA kernels are compiled
        # and memory is pre-allocated. First real dictation will be instant.
        try:
            dummy = np.zeros(16000, dtype=np.float32)
            self._model.transcribe(dummy, without_timestamps=True,
                                   beam_size=1, vad_filter=False,
                                   condition_on_previous_text=False)
            log.info("model warmed up")
        except Exception as ex:
            log.debug("warmup failed (non-critical): %s", ex)

    def _load_any_cached(self, WhisperModel, kw):
        """Try every model repo already present in the cache dir, best first.
        Keeps a portable stick usable on an offline host even when the
        configured model was never downloaded."""
        import os
        cache = kw.get("download_root", "")
        try:
            names = os.listdir(cache)
        except OSError:
            names = []
        candidates = sorted(
            (n for n in names if n.startswith("models--")),
            key=lambda n: ("turbo" not in n, "small" not in n))
        for name in candidates:
            repo_id = name[len("models--"):].replace("--", "/")
            try:
                m = WhisperModel(repo_id, device="cpu", compute_type="int8",
                                 local_files_only=True, num_workers=1, **kw)
                self.model_size = repo_id
                log.info("recovered with cached model %s", repo_id)
                return m
            except Exception as ex:
                log.debug("cached candidate %s failed: %s", repo_id, ex)
        raise RuntimeError(
            "No usable speech model found. Connect to the internet once so "
            "Dictate can download one, then it works offline forever.")

    def _adaptive_beam_size(self, audio_data: np.ndarray) -> int:
        """Short takes don't need beam_size=5 — beam_size=1 is 2-3x faster
        with negligible accuracy loss for a single sentence."""
        duration = audio_data.size / 16000
        if duration < 5.0:
            return 1
        if duration < 15.0:
            return 3
        return self.beam_size

    def transcribe_audio_buffer(self, audio_data: np.ndarray,
                                prev_text: str | None = None) -> str:
        """Raw transcription of a float32 mono 16 kHz buffer.

        prev_text: tail of the previously committed chunk (streaming mode) —
        fed as initial_prompt so terminology stays consistent across chunks.
        """
        if audio_data.size < 1600:  # under 0.1 s — nothing to do
            return ""
        self.load()
        beam = self._adaptive_beam_size(audio_data)
        duration = audio_data.size / 16000
        # Long takes span multiple 30s Whisper windows. Carrying the previous
        # window's text as context keeps names/terminology consistent across
        # the take. Short takes fit one window, so keep it off there (it's the
        # classic hallucination-loop amplifier on noisy short audio).
        cond_prev = duration > 25.0
        prompt = self.initial_prompt
        if prev_text:
            # last ~200 chars of the previous chunk as rolling context
            prompt = (prompt + " " if prompt else "") + prev_text[-200:]
        # Pad the VAD speech boundaries so the filter can't clip the first or
        # last syllable — the main source of "long sentences lose words".
        vad_params = dict(min_silence_duration_ms=500, speech_pad_ms=400)
        with self._lock:
            segments, _info = self._model.transcribe(
                audio_data,
                language=self.language,
                task="transcribe",
                beam_size=beam,
                initial_prompt=prompt,
                hotwords=self.hotwords,
                vad_filter=self.vad_enabled,
                vad_parameters=vad_params if self.vad_enabled else None,
                condition_on_previous_text=cond_prev,
                without_timestamps=True,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            if not text and self.vad_enabled and audio_data.size > 16000 * 2:
                log.info("empty result with VAD on a %.1fs take — retrying "
                         "without VAD filter", audio_data.size / 16000)
                segments, _info = self._model.transcribe(
                    audio_data,
                    language=self.language,
                    task="transcribe",
                    beam_size=beam,
                    initial_prompt=prompt,
                    hotwords=self.hotwords,
                    vad_filter=False,
                    condition_on_previous_text=cond_prev,
                    without_timestamps=True,
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
        extra_hall = None
        if self.language is None or self.language in ("bs", "hr", "sr"):
            try:
                from . import lang_bs
            except ImportError:
                import lang_bs
            extra_hall = lang_bs.HALLUCINATIONS
        if short_take and _cleanup.is_probable_hallucination(text, extra_hall):
            log.info("dropping probable silence hallucination: %r", text)
            return ""
        log.debug("raw transcript: %r", text)
        return text

    def try_preview_transcribe(self, audio_data: np.ndarray) -> str | None:
        """Best-effort transcription for the live preview pill.

        Returns None immediately if the engine lock is held (a real
        transcription is running). The preview must NEVER queue behind the
        final pass: piling preview jobs onto the model while the final
        transcription runs is both a latency killer and a crash risk
        (concurrent pressure on the same CUDA context).
        """
        if audio_data.size < 1600 or self._model is None:
            return None
        if not self._lock.acquire(blocking=False):
            return None
        try:
            segments, _info = self._model.transcribe(
                audio_data,
                language=self.language,
                task="transcribe",
                beam_size=1,
                hotwords=self.hotwords,
                vad_filter=False,
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            return " ".join(s.text.strip() for s in segments).strip()
        except Exception as ex:
            log.debug("preview transcribe failed: %s", ex)
            return None
        finally:
            self._lock.release()

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
        # Track if the punctuation lexicon converted the whole input to
        # punctuation/newlines (e.g. user said just "tačka" or "novi red").
        # _fix_spacing would otherwise strip standalone \n to empty.
        # Also track if ANY punctuation command fired (for strip_short).
        original_text = text
        self._has_punctuation_payload = False
        self._last_punct_payload = ""
        self._punct_command_fired = False
        for phrase, repl in getattr(self, "lexicon", PUNCTUATION_LEXICON):
            # eat punctuation whisper may have attached to the spoken keyword
            before = text
            text = re.sub(
                rf"[\s,.]*\b{re.escape(phrase)}\b[.,]?",
                repl.replace("\\", "\\\\"),
                text, flags=re.IGNORECASE)
            if text != before:
                self._punct_command_fired = True
        # If the punctuation lexicon consumed everything (input was just a
        # punctuation command), preserve the payload so _fix_spacing doesn't
        # eat it. Use raw text (not stripped) because \n is whitespace.
        after_punct_words = re.findall(r"[\w']+", text)
        if not after_punct_words and text:
            self._has_punctuation_payload = True
            self._last_punct_payload = text
        level = getattr(self, "cleanup_level", "standard")
        if verbatim or level == "off":
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
        if level == "light":
            # fillers + dictionary only: the user's words, just tidier.
            # No transforms, no casing, no polish, no auto-punctuation.
            return self._fix_spacing(text).strip(" ")
        # Apply user-defined regex transforms (e.g. "gonna" -> "going to")
        if self.transforms and not verbatim:
            try:
                from . import transforms as _t
            except ImportError:
                import transforms as _t
            text = _t.apply_transforms(text, self.transforms)
        # high forces the polish pass whenever a local Ollama is reachable;
        # standard uses it only when the user/auto-probe enabled it
        run_polish = self.ollama_polish or (level == "high"
                                            and self.ollama_available)
        if run_polish:
            text = _cleanup.ollama_polish(
                text, self.ollama_model, self.ollama_endpoint,
                tone=profile.get("tone"))
        text = self._fix_spacing(text)
        text = self._apply_casing(text)
        # Auto-punctuation: add trailing period + capitalise if enabled
        if self.auto_punctuation:
            try:
                from . import auto_punct
            except ImportError:
                import auto_punct
            text = auto_punct.add_punctuation(text)
        # strip_short: remove trailing period from short utterances (< 3 words)
        # BUT only if there are actual words AND the period wasn't explicitly
        # spoken via a punctuation command (don't strip "tačka" -> ".")
        words = re.findall(r"[\w']+", text)
        if self.strip_short and len(words) < 3 and words:
            # Don't strip the period if the user explicitly said "period"/"tačka"
            if not self._punct_command_fired:
                text = text.rstrip(".")
        # Don't return empty if we had punctuation/newlines — _fix_spacing
        # can strip standalone newlines to empty, so preserve them
        if not text and self._has_punctuation_payload:
            text = self._last_punct_payload
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
