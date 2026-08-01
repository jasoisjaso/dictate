"""Recording session controller: begin/stop/abort a take, streaming gate,
watchdogs (cap, silence, transcribe budget) and the transcription workers.

Runs as a mixin on DictationTrayApp — it reads/writes the same attributes the
old monolithic ui.py did (state, recorder, engine, overlay, signals), so
behaviour is unchanged; only the file boundaries moved. Threading contract is
unchanged too: hotkey events arrive via Qt signals on the GUI thread; workers
run on daemon threads and cross back via signals.
"""

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from .app_states import IDLE, LOADING, RECORDING, TRANSCRIBING
from . import appcontext

log = logging.getLogger("dictate.session")


class SessionMixin:
    """Recording lifecycle for DictationTrayApp."""

    if TYPE_CHECKING:
        # Provided by the DictationTrayApp host class; declared here so the
        # mixin type-checks stand-alone.
        state: str
        mode: str
        engine: Any
        recorder: Any
        overlay: Any
        tr: Any
        app_profiles: dict
        silence_timeout: float
        live_preview: bool
        streaming_mode: str
        # last_raw_text is provided by the coordinator as a property
        # delegating to TextDelivery; assigning through it is fine.
        last_raw_text: Any
        _dict_mode: str
        _rec_app: Any
        _rec_profile: dict
        _chunked_take: Any
        _committed_preview: str
        _monitor_stop: threading.Event
        _preview_stop: threading.Event
        hotkeys: Any
        _transcribe_token: int
        _continuous_stop: bool
        _sig_result: Any
        _sig_error: Any
        _sig_autostop: Any
        def _set_state(self, state: str) -> None: ...
        def _on_error(self, msg: str) -> None: ...
        def _beep(self, freq: int, ms: int) -> None: ...

    def _begin_recording(self) -> bool:
        if self.state != IDLE:
            # UX: pressing the hotkey during the ~7s model load used to do
            # NOTHING — the most common "is it broken?" moment. Say so.
            if self.state == LOADING:
                self.overlay.flash_toast(self.tr("still_loading"))
            elif self.state == TRANSCRIBING:
                self.overlay.flash_toast(self.tr("finishing"))
            return False
        # If not in "auto" mode, the manual mode overrides per-app detection.
        # "code" forces verbatim (like a terminal profile).
        # "prose" forces cleanup + sentence casing (the default behaviour).
        # "email" forces professional tone.
        if self._dict_mode == "auto":
            self._rec_app = appcontext.foreground_exe()
            self._rec_profile = appcontext.resolve_profile(self._rec_app,
                                                           self.app_profiles)
        elif self._dict_mode == "code":
            self._rec_app = appcontext.foreground_exe()
            self._rec_profile = {"verbatim": True, "_profile": "code"}
        elif self._dict_mode == "email":
            self._rec_app = appcontext.foreground_exe()
            self._rec_profile = {"tone": "professional", "_profile": "email"}
        else:  # prose
            self._rec_app = appcontext.foreground_exe()
            self._rec_profile = {"_profile": "prose"}
        # force_paste is a delivery quirk of the target app (e.g. modern
        # Notepad dropping typed keys), independent of the formatting mode.
        # Carry it over even when a manual F7 mode overrode the profile, so
        # it always applies whenever the focused app needs it.
        if self._dict_mode != "auto" and self._rec_app:
            _app_prof = appcontext.resolve_profile(self._rec_app,
                                                   self.app_profiles)
            if _app_prof.get("force_paste"):
                self._rec_profile["force_paste"] = True
        if self._rec_profile:
            log.info("app context: %s -> profile %s (mode=%s)",
                     self._rec_app, self._rec_profile.get("_profile"),
                     self._dict_mode)
        try:
            self.recorder.start_recording()
        except RuntimeError as ex:
            self._on_error(str(ex))
            return False
        self._set_state(RECORDING)
        # cap watchdog: auto-stop if a single take hits the max-duration cap
        # (covers a stuck push-to-talk key or a forgotten toggle)
        self._monitor_stop.clear()
        threading.Thread(target=self._cap_watchdog, daemon=True).start()
        # Streaming: commit finished chunks while the user is still talking so
        # a long take finalizes near-instantly on release. Gated per-PC.
        self._chunked_take = None
        self._committed_preview = ""
        if self._streaming_allowed():
            from .streaming import ChunkedTake

            def _on_commit(t):
                # remember committed text; the preview worker stitches the
                # live tail onto it so the caption never resets mid-take
                self._committed_preview = t
                self.overlay.set_preview(t[-160:])
            self._chunked_take = ChunkedTake(
                self.engine, self.recorder, on_commit=_on_commit)
            self._chunked_take.start()
        # Each engine decides whether a live caption is affordable on this
        # hardware (Whisper: CUDA only; Parakeet: yes even on CPU).
        preview_on = (self.live_preview
                      and getattr(self.engine, "preview_ok", False))
        self.overlay.show_recording(preview=preview_on)
        # show which mode/profile is active so the context awareness is visible
        if self._rec_profile:
            name = self._rec_profile.get("_profile", "")
            bits = [name]
            if self._rec_profile.get("verbatim"):
                bits.append("verbatim")
            elif self._rec_profile.get("tone"):
                bits.append(self._rec_profile["tone"])
            self.overlay.set_profile_tag(" · ".join(b for b in bits if b))
        else:
            self.overlay.set_profile_tag("")
        if preview_on:
            # Run the tail re-transcriber even while streaming commits are
            # active: try_preview_transcribe is non-blocking (it skips the
            # pass whenever the engine lock is held by a chunk commit), so
            # there is no contention — and without it the caption would only
            # move every ~14s when a chunk lands, which reads as "frozen".
            self._preview_stop.clear()
            threading.Thread(target=self._preview_worker, daemon=True).start()
        self._beep(880, 60)  # high beep = recording start
        return True

    def _streaming_allowed(self) -> bool:
        """Per-PC gate for chunked streaming. 'auto' asks device.streaming_ok
        with the ACTIVE device (post CUDA-fallback), so a GPU build running on
        CPU is judged as the CPU it really is."""
        if self.streaming_mode == "off":
            return False
        if self.engine._model is None:
            return False  # model still loading — plain path
        try:
            from . import device as _device
            tier = _device.Tier(device=self.engine.active_device or "cpu",
                                compute_type=self.engine.compute_type,
                                model_size=self.engine.model_size)
            allowed = _device.streaming_ok(
                tier, getattr(self.engine, "engine_name", "whisper"))
        except Exception:
            allowed = False
        if self.streaming_mode == "on":
            return True  # user forced it on; trust them
        return allowed

    def _stop_and_transcribe(self):
        if self.state != RECORDING:
            return
        self._monitor_stop.set()
        self._preview_stop.set()
        audio = self.recorder.stop_recording()
        self._set_state(TRANSCRIBING)
        self.overlay.show_processing()
        self._beep(660, 60)  # lower beep = recording stop / transcribing
        # token identifies this transcription; the watchdog uses it so a stuck
        # long take can never permanently soft-lock the app at TRANSCRIBING
        self._transcribe_token = getattr(self, "_transcribe_token", 0) + 1
        token = self._transcribe_token
        # hand the streaming chunker (if any) to the worker; a fresh one is
        # created on the next _begin_recording
        chunked, self._chunked_take = self._chunked_take, None
        threading.Thread(target=self._transcribe_worker,
                         args=(audio, token, chunked),
                         daemon=True).start()
        # generous budget that scales with audio length (real-time factor is
        # well under 1x even on CPU, so 8s + 1x audio is very safe)
        budget_ms = int((8.0 + len(audio) / 16000) * 1000)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(budget_ms, lambda: self._transcribe_watchdog(token))

    def _transcribe_watchdog(self, token):
        """If the transcription for `token` is still running past its budget,
        something hung — recover to IDLE so the user isn't stuck with a blue
        icon and an unresponsive hotkey."""
        if self.state == TRANSCRIBING and getattr(self, "_transcribe_token", 0) == token:
            log.warning("transcription watchdog fired (token=%s) — recovering", token)
            # invalidate the token so the still-running worker's late result is
            # DROPPED instead of typed into whatever window has focus by then
            self._transcribe_token += 1
            self.overlay.hide_overlay()
            self._set_state(IDLE)
            self.overlay.flash_toast(self.tr("too_long"))

    # push-to-talk
    def _on_ptt_start(self):
        self._continuous_stop = False
        self._begin_recording()

    def _on_ptt_stop(self):
        if self.mode == "continuous":
            self._continuous_stop = True
        self._stop_and_transcribe()

    # toggle / hands-free
    def _on_toggle(self):
        if self.state == IDLE:
            self._continuous_stop = False
            if self._begin_recording() and self.silence_timeout > 0:
                self._monitor_stop.clear()
                threading.Thread(target=self._silence_monitor, daemon=True).start()
        elif self.state == RECORDING:
            self._continuous_stop = True
            self._stop_and_transcribe()

    def _on_abort(self):
        if self.state != RECORDING:
            return
        self._monitor_stop.set()
        self._preview_stop.set()
        if self._chunked_take is not None:
            self._chunked_take.cancel()
            self._chunked_take = None
        self.hotkeys.reset_ptt()
        # invalidate any pending transcription watchdog
        self._transcribe_token = getattr(self, "_transcribe_token", 0) + 1
        self.recorder.abort()
        self.overlay.hide_overlay()
        self._set_state(IDLE)

    # ---- worker threads --------------------------------------------------

    def _transcribe_worker(self, audio, token=None, chunked=None):
        try:
            t0 = time.time()
            if chunked is not None:
                # streaming take: committed chunks + tail = near-instant final
                raw = chunked.finalize(audio)
            else:
                raw = self.engine.transcribe_audio_buffer(audio)
            text = self.engine.post_process(raw, profile=self._rec_profile)
            # If the watchdog (or an abort) already invalidated this token,
            # the user moved on — never inject a stale result into whatever
            # window has focus now.
            if token is not None and getattr(self, "_transcribe_token", 0) != token:
                log.warning("dropping stale transcription result (token=%s)", token)
                return
            # timing at INFO; the transcript text only at DEBUG so nothing you
            # dictate is written to the log file at the default level
            log.info("transcribed %.1fs audio in %.1fs (%d chars)",
                     len(audio) / 16000, time.time() - t0, len(text))
            log.debug("result text: %r", text)
            # Stash the raw transcript so "redo verbatim" can re-inject it
            # without cleanup/casing applied.
            self.last_raw_text = raw.strip()
            self._sig_result.emit(text)
        except Exception as ex:
            log.exception("transcription failed")
            self._sig_error.emit(f"Transcription failed: {ex}")

    def _preview_worker(self):
        """Live transcript while recording (GPU only): re-transcribe only the
        most recent few seconds of the take and stream that tail into the
        overlay pill. We deliberately cap the snapshot length AND skip the
        pass entirely when the engine is busy (try_preview_transcribe is
        non-blocking): preview jobs must never queue behind or contend with a
        real transcription — that contention stalls the final result and has
        crashed the CUDA context. The preview is just a 'we can hear you'
        reassurance, so dropping frames is fine."""
        PREVIEW_TAIL_S = 8.0   # only ever re-run the last ~8s for the preview
        while not self._preview_stop.wait(0.4):
            if self.state != RECORDING or self.engine._model is None:
                continue
            dur = self.recorder.duration
            if dur < 0.8:
                continue
            try:
                tail_s = min(dur, PREVIEW_TAIL_S)
                # With streaming active, never re-preview audio that a chunk
                # already committed — that would double the words in the
                # caption. Clamp the tail to the uncommitted region.
                chunked = self._chunked_take
                if chunked is not None:
                    uncommitted_s = dur - chunked._committed / 16000
                    if uncommitted_s < 0.6:
                        continue
                    tail_s = min(tail_s, uncommitted_s)
                snapshot = self.recorder.peek_tail(tail_s)
                raw = self.engine.try_preview_transcribe(snapshot)
                if raw and not self._preview_stop.is_set():
                    # During a streaming take, prepend the committed text so
                    # the caption reads continuously instead of resetting at
                    # every chunk boundary.
                    committed = getattr(self, "_committed_preview", "")
                    full = (committed + " " + raw).strip() if committed else raw
                    self.overlay.set_preview(full[-160:])
            except Exception as ex:
                log.debug("preview pass failed: %s", ex)

    def _cap_watchdog(self):
        """Auto-stop a take that hit the max-duration cap (stuck key etc.)."""
        while not self._monitor_stop.wait(0.5):
            if self.state != RECORDING:
                return
            if self.recorder.capped:
                log.info("max recording length reached — auto-stop")
                self._sig_autostop.emit()
                return

    def _silence_monitor(self):
        had_speech = False
        while not self._monitor_stop.wait(0.35):
            if self.state != RECORDING:
                return
            dur = self.recorder.duration
            if dur < 1.0:
                continue
            if self.engine.has_speech(self.recorder.peek_tail(self.silence_timeout)):
                had_speech = True
            elif had_speech and dur > self.silence_timeout + 0.8:
                log.info("silence %.1fs — auto-stop", self.silence_timeout)
                self._sig_autostop.emit()
                return
