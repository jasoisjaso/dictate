"""App coordinator: owns the Qt signals, wires the split modules together
and holds the small amount of state they share.

The old 1,200-line god-class is now six focused modules:

  app_states.py       shared state/mode constants
  hotkeys.py          pynput listener + key routing (HotkeyController)
  tray_shell.py       tray icon, menu, status rendering (TrayShell)
  model_lifecycle.py  model download/preload/update-check + progress dialog
  session.py          recording lifecycle, watchdogs, workers (SessionMixin)
  delivery.py         text injection, macros, voice-edit commands (TextDelivery)

Threading contract (unchanged): hotkey events arrive on pynput's thread and
cross into the GUI thread via Qt signals; workers run on daemon threads and
report back through signals only.
"""

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import appcontext, model_lifecycle, win32_input
from .app_states import IDLE, LOADING, MODE_LABELS, MODE_NAMES, RECORDING
from .audio import AudioRecorder
from .delivery import TextDelivery
from .engine import WhisperTranscriber, create_engine
from .history import History
from .hotkeys import HotkeyController, pretty_key
from .model_lifecycle import DownloadProgressUI
from .overlay import WaveformOverlay
from .session import SessionMixin
from .tray_shell import TrayShell

log = logging.getLogger("dictate.ui")


class DictationTrayApp(QObject, SessionMixin):
    _sig_ptt_start = Signal()
    _sig_ptt_stop = Signal()
    _sig_toggle = Signal()
    _sig_abort = Signal()
    _sig_copy_last = Signal()
    _sig_mode_cycle = Signal()
    _sig_model_ready = Signal(str)
    _sig_result = Signal(str)
    _sig_error = Signal(str)
    _sig_autostop = Signal()
    _sig_dl_start = Signal(str)
    _sig_dl_progress = Signal(int)
    _sig_dl_done = Signal()
    _sig_update_available = Signal(str, str)

    def __init__(self, cfg: dict, app: QApplication, first_run: bool = False,
                 recovery_note: str | None = None):
        super().__init__()
        self.cfg = cfg
        self.app = app
        self.state = LOADING
        self._recovery_note = recovery_note
        # UI language: "auto" follows the dictation language (bs/hr/sr get
        # Bosnian tray + toasts), or forced via [ui] language = "en"/"bs"
        from .i18n import Translator, resolve_ui_language
        self.tr = Translator(resolve_ui_language(cfg))
        # Engine routing (whisper vs parakeet) lives in create_engine();
        # fail-open — a Parakeet problem always lands us on Whisper.
        self.engine = create_engine(cfg)
        self.recorder = AudioRecorder(
            input_device=cfg.get("audio", {}).get("input_device"))
        self.overlay = WaveformOverlay(style=cfg.get("overlay", {}).get("style", "equalizer"))
        self.overlay.set_level_source(self.recorder.current_level)
        # For the blob visualizer: provide a callback that returns recent audio
        self.overlay.set_audio_source(lambda: self.recorder.peek_tail(0.05))
        self.delivery = TextDelivery(self)
        self._session_words = 0
        self._session_start = time.time()
        self._dict_mode = "auto"  # cycle via F7: auto -> prose -> code -> email
        self._monitor_stop = threading.Event()
        # Cache AMD GPU detection once at startup so we never spawn wmic again
        self._amd_note = ""
        try:
            from . import device as _device
            if hasattr(_device, '_amd_gpu_present') and _device._amd_gpu_present():
                self._amd_note = " (AMD GPU — CPU mode)"
        except Exception:
            pass

        vad = cfg.get("vad", {})
        self.silence_timeout = float(vad.get("silence_timeout", 2.0))

        inj = cfg.get("injection", {})
        self.inject_mode = inj.get("mode", "auto")
        self.paste_threshold = int(inj.get("paste_threshold", 300))
        self.sounds = bool(cfg.get("feedback", {}).get("sounds", True))
        self.live_preview = bool(cfg.get("preview", {}).get("live_preview", True))
        # Streaming (chunked while-you-talk transcription) for long takes.
        # true / false / "auto" — auto defers to hardware gating at record
        # time (GPU always; CPU only with >=8 cores and a small model).
        raw_stream = cfg.get("streaming", {}).get("enabled", "auto")
        self.streaming_mode = (raw_stream.strip().lower()
                               if isinstance(raw_stream, str)
                               else ("on" if raw_stream else "off"))
        self._chunked_take = None
        persist_history = bool(cfg.get("history", {}).get("persist", False))
        import os
        from . import paths as _paths
        self.history = History(
            limit=25,
            persist_path=(os.path.join(_paths.app_data_dir(), "history.json")
                          if persist_history else None)
        )
        self.app_profiles = dict(appcontext.DEFAULT_PROFILES)
        self.app_profiles.update(cfg.get("app_profiles", {}))
        self._rec_app = None
        self._rec_profile = {}
        self._preview_stop = threading.Event()

        hk = cfg.get("hotkeys", {})
        self.mode = hk.get("mode", "push_to_talk").strip().lower()
        self.ptt_name = hk.get("push_to_talk_key", "ctrl_r")
        self.toggle_name = hk.get("toggle_key", "f9")
        self.abort_name = hk.get("abort_key", "esc")
        self.copy_name = hk.get("copy_key", "f8")
        self.mode_cycle_name = hk.get("mode_cycle_key", "f7")
        self.pause_name = hk.get("pause_key", "pause")
        self.rerecord_name = hk.get("rerecord_key", "f6")

        self.shell = TrayShell(self)
        self.tray = self.shell.tray
        self._build_menu()
        self._set_state(LOADING)
        self.tray.show()

        self._sig_ptt_start.connect(self._on_ptt_start)
        self._sig_ptt_stop.connect(self._on_ptt_stop)
        self._sig_toggle.connect(self._on_toggle)
        self._sig_abort.connect(self._on_abort)
        self._sig_copy_last.connect(self._copy_last)
        self._sig_mode_cycle.connect(self._cycle_mode)
        self._sig_model_ready.connect(self._on_model_ready)
        self._sig_result.connect(self._on_result)
        self._sig_error.connect(self._on_error)
        self._sig_autostop.connect(self._stop_and_transcribe)
        self._dl_ui = DownloadProgressUI()
        self._sig_dl_start.connect(self._dl_ui.on_start)
        self._sig_dl_progress.connect(self._dl_ui.on_progress)
        self._sig_dl_done.connect(self._dl_ui.on_done)
        self._sig_update_available.connect(self._on_update_available)

        self._start_hotkeys()
        threading.Thread(target=self._preload_model, daemon=True).start()
        if first_run:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, lambda: self._first_run_flow())

    # ---- last-injection bookkeeping lives in delivery; session and the
    # rescue actions reach it through these delegates so nothing holds a
    # second copy of the state.

    @property
    def last_raw_text(self) -> str:
        return self.delivery.last_raw_text

    @last_raw_text.setter
    def last_raw_text(self, value: str):
        self.delivery.last_raw_text = value

    @property
    def last_injected_len(self) -> int:
        return self.delivery.last_injected_len

    @last_injected_len.setter
    def last_injected_len(self, value: int):
        self.delivery.last_injected_len = value

    @property
    def last_injected_text(self) -> str:
        return self.delivery.last_injected_text

    @last_injected_text.setter
    def last_injected_text(self, value: str):
        self.delivery.last_injected_text = value

    def _first_run_flow(self):
        """First launch: settings wizard, then the visual how-to guide."""
        self._open_settings(first_run=True)
        try:
            from .guide import GuideDialog
            GuideDialog(trigger_hint=self._trigger_hint()).exec()
        except Exception:
            log.exception("guide failed to open")

    # ---- setup ----------------------------------------------------------

    def _trigger_hint(self) -> str:
        if self.mode == "push_to_talk":
            return self.tr("hold_and_talk", key=pretty_key(self.ptt_name))
        return self.tr("tap_to_talk", key=pretty_key(self.toggle_name))

    def _build_menu(self):
        self.shell.build_menu()

    def _update_stats_label(self):
        self.shell.update_stats()

    def _cycle_mode(self):
        """Cycle through dictation modes: auto -> prose -> code -> email -> auto."""
        idx = MODE_NAMES.index(self._dict_mode)
        self._dict_mode = MODE_NAMES[(idx + 1) % len(MODE_NAMES)]
        label = MODE_LABELS[self._dict_mode]
        self.shell.update_mode_label(label)
        self.overlay.flash_toast(f"Mode: {label}")

    def _toggle_pause(self):
        """Pause/resume recording without stopping the take."""
        if self.state != RECORDING:
            return
        if self.recorder.paused:
            self.recorder.resume()
            self.overlay.flash_toast(self.tr("resumed"))
        else:
            self.recorder.pause()
            self.overlay.flash_toast(self.tr("paused"))

    def _rerecord(self):
        """Delete the last dictation and immediately start recording again."""
        if self.state != IDLE:
            return
        if self.last_injected_len > 0:
            win32_input.inject_backspaces(self.last_injected_len)
            self.last_injected_len = 0
            self.last_injected_text = ""
        self._begin_recording()

    def _copy_last(self):
        """Copy the most recent dictation to the clipboard — the fast rescue
        when text landed in the wrong window."""
        items = self.history.items()
        if items:
            QApplication.clipboard().setText(items[0].text)
            self.overlay.flash_toast(self.tr("copied_last"))
        else:
            self.overlay.flash_toast(self.tr("nothing_yet"))

    def _open_guide(self):
        from .guide import GuideDialog
        GuideDialog(trigger_hint=self._trigger_hint()).exec()

    def _open_history(self):
        """Recent dictations (session-only, never written to disk) with
        one-click copy — the rescue hatch when text landed in the wrong app."""
        from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                                       QListWidget, QListWidgetItem,
                                       QPushButton, QVBoxLayout)
        dlg = QDialog()
        dlg.setWindowTitle(
            "Dictate — History (this session · "
            f"{getattr(self.engine, 'engine_name', 'whisper').title()})")
        dlg.setMinimumSize(480, 360)
        v = QVBoxLayout(dlg)
        items = self.history.items()
        if not items:
            v.addWidget(QLabel("Nothing dictated yet this session."))
        lst = QListWidget()
        for e in items:
            where = f"  →  {e.app}" if e.app else ""
            it = QListWidgetItem(f"[{e.when}]{where}\n{e.text}")
            it.setData(0x0100, e.text)  # Qt.UserRole
            lst.addItem(it)
        v.addWidget(lst)
        row = QHBoxLayout()
        b_copy = QPushButton("Copy selected")

        def do_copy():
            it = lst.currentItem()
            if it:
                QApplication.clipboard().setText(it.data(0x0100))
        b_copy.clicked.connect(do_copy)
        b_close = QPushButton("Close")
        b_close.clicked.connect(dlg.accept)
        row.addWidget(b_copy)
        row.addStretch(1)
        row.addWidget(b_close)
        v.addLayout(row)
        dlg.exec()

    def _open_settings(self, first_run: bool = False):
        try:
            from .settings_gui import SettingsDialog
            dlg = SettingsDialog(self.cfg, first_run=first_run,
                                 engine=self.engine,
                                 app_state=lambda: self.state)
            dlg.saved.connect(self._apply_settings)
            dlg.exec()
        except Exception as ex:
            log.exception("settings dialog failed to open")
            self.tray.showMessage("Dictate",
                f"Settings failed to open: {ex}",
                QSystemTrayIcon.Critical, 8000)

    def _apply_settings(self, overlay: dict):
        """Hot-apply everything that doesn't need a model reload."""
        try:
            from . import config as _config_mod
        except ImportError:
            import config as _config_mod
        self.cfg = _config_mod.load()
        hk = self.cfg.get("hotkeys", {})
        self.mode = hk.get("mode", "push_to_talk").strip().lower()
        self.ptt_name = hk.get("push_to_talk_key", "ctrl_r")
        self.toggle_name = hk.get("toggle_key", "f9")
        self.abort_name = hk.get("abort_key", "esc")
        self.copy_name = hk.get("copy_key", "f8")
        self.mode_cycle_name = hk.get("mode_cycle_key", "f7")
        self.hotkeys.stop()
        self._start_hotkeys()
        self.recorder.set_input_device(
            self.cfg.get("audio", {}).get("input_device"))
        cl = self.cfg.get("cleanup", {})
        self.engine.remove_fillers = bool(cl.get("remove_fillers", True))
        # rebuild the filler regex so custom filler-word edits take effect now,
        # not only after a restart
        try:
            from . import cleanup as _cl_mod
        except ImportError:
            import cleanup as _cl_mod
        extra = cl.get("custom_fillers", []) or []
        if isinstance(extra, str):
            extra = [p.strip() for p in extra.split(",")]
        lang = self.cfg.get("whisper", {}).get("language", "en")
        merged = _cl_mod.default_fillers(lang) + [str(w) for w in extra]
        self.engine.filler_re = _cl_mod._build_filler_re(merged)
        self.engine.dictionary = {str(k): str(v) for k, v in
                                  self.cfg.get("dictionary", {}).items()}
        # refresh the hotwords spelling boost so dictionary edits apply now
        # (Whisper only — Parakeet has no recognition-biasing channel; its
        # dictionary hits still apply as text replacement above)
        if getattr(self.engine, "engine_name", "whisper") == "whisper":
            if self.engine.dictionary:
                terms = list(dict.fromkeys(self.engine.dictionary.values()))[:40]
                self.engine.hotwords = ", ".join(terms)
            else:
                self.engine.hotwords = None
        self.engine.apply_language(lang)
        # language change also swaps the punctuation lexicon + UI language
        from .engine import _build_lexicon
        self.engine.lexicon = _build_lexicon(self.engine.language)
        from .i18n import Translator, resolve_ui_language
        self.tr = Translator(resolve_ui_language(self.cfg))
        # cleanup level hot-applies too
        lvl = str(self.cfg.get("cleanup", {}).get("level", "standard")).strip().lower()
        self.engine.cleanup_level = lvl if lvl in ("off", "light", "standard", "high") else "standard"
        # auto-punctuation + casing hot-apply: previously these only took
        # effect after a full restart, so ticking the box in Settings did
        # nothing to the running engine (the "Gmail has no full stops" bug).
        pp = self.cfg.get("post_processing", {})
        raw_ap = pp.get("auto_punctuation", "auto")
        if getattr(self.engine, "engine_name", "whisper") == "parakeet":
            # Parakeet punctuates natively; our heuristic on top of it
            # double-punctuates, so it stays off no matter the setting.
            self.engine.auto_punctuation = False
        elif isinstance(raw_ap, str) and raw_ap.strip().lower() == "auto":
            self.engine.auto_punctuation = self.engine.model_size in (
                "tiny", "base", "small")
        else:
            self.engine.auto_punctuation = bool(raw_ap)
        self.engine.casing = pp.get("casing", "sentence")
        self._build_menu()
        self._set_state(self.state)
        # Apply overlay style change immediately
        vis_style = self.cfg.get("overlay", {}).get("style", "equalizer")
        self.overlay.set_style(vis_style)
        want_model = self.cfg.get("whisper", {}).get("model_size", "auto")
        if (getattr(self.engine, "engine_name", "whisper") == "whisper"
                and want_model not in ("auto", self.engine.model_size)):
            self.tray.showMessage(
                "Dictate", "Model change takes effect after you restart Dictate.",
                QSystemTrayIcon.Information, 5000)
        # Engine switch needs a full model load — restart, same as a model
        # change. Compare what the router would pick NOW against what runs.
        try:
            from . import device as _device
            want_engine = str(self.cfg.get("engine", {}).get(
                "engine", "auto")).strip().lower()
            routed = _device.choose_engine(
                want_engine, _device.detect(),
                self.cfg.get("whisper", {}).get("language", "en"))
            if routed != getattr(self.engine, "engine_name", "whisper"):
                self.tray.showMessage(
                    "Dictate",
                    "Engine change takes effect after you restart Dictate.",
                    QSystemTrayIcon.Information, 5000)
        except Exception:
            log.debug("engine-change check failed", exc_info=True)

    def _start_hotkeys(self):
        names = {
            "ptt": self.ptt_name, "toggle": self.toggle_name,
            "abort": self.abort_name, "copy": self.copy_name,
            "mode_cycle": self.mode_cycle_name, "pause": self.pause_name,
            "rerecord": self.rerecord_name,
        }
        # Signal .emit callables cross to the GUI thread; pause and re-record
        # are called directly on the listener thread (same as before the split).
        callbacks = {
            "ptt_start": self._sig_ptt_start.emit,
            "ptt_stop": self._sig_ptt_stop.emit,
            "toggle": self._sig_toggle.emit,
            "abort": self._sig_abort.emit,
            "copy": self._sig_copy_last.emit,
            "mode_cycle": self._sig_mode_cycle.emit,
            "pause": self._toggle_pause,
            "rerecord": self._rerecord,
        }
        self.hotkeys = HotkeyController(self.mode, names, callbacks)
        self.hotkeys.start()

    def _preload_model(self):
        ok = model_lifecycle.preload(
            self.engine,
            self._sig_dl_start.emit, self._sig_dl_progress.emit,
            self._sig_dl_done.emit,
            self._sig_model_ready.emit, self._sig_error.emit)
        if ok or getattr(self.engine, "engine_name", "whisper") != "parakeet":
            return
        # Parakeet couldn't start (download failed, old CPU without AVX2,
        # broken wheel). Fall back to Whisper for this session — the app must
        # never be bricked by the optional engine. Safe to swap here: we're
        # still LOADING, nothing else touches self.engine until ready.
        log.warning("parakeet failed to start — falling back to Whisper "
                    "for this session")
        self.engine = WhisperTranscriber(self.cfg)
        self.engine.engine_note = (
            "Parakeet couldn't start on this PC, so Dictate is using "
            "Whisper this session. Pick Whisper in Settings to stop "
            "seeing this, or reselect Parakeet to retry the download.")
        model_lifecycle.preload(
            self.engine,
            self._sig_dl_start.emit, self._sig_dl_progress.emit,
            self._sig_dl_done.emit,
            self._sig_model_ready.emit, self._sig_error.emit)

    # ---- state (GUI thread) ---------------------------------------------

    def _set_state(self, state: str):
        self.state = state
        self.shell.render_state(state)

    def _on_model_ready(self, device: str):
        self._set_state(IDLE)
        self.tray.showMessage(
            self.tr("ready_title"),
            self.tr("ready_balloon", model=self.engine.model_size,
                    device=device, hint=self._trigger_hint()),
            QSystemTrayIcon.Information, 4000)
        # Crash recovery: tell the user what happened last run (once, after
        # the ready balloon) and record what device this run uses so the
        # crash guard can decide about CPU fallback next time.
        try:
            from . import paths as _paths, crashguard as _cg
            _cg.record_device(_paths.app_data_dir(), self.engine.active_device)
        except Exception:
            log.debug("crashguard record failed", exc_info=True)
        if self._recovery_note:
            note = self._recovery_note
            self._recovery_note = None
            from PySide6.QtCore import QTimer
            QTimer.singleShot(4500, lambda: self.tray.showMessage(
                self.tr("crash_title"), note,
                QSystemTrayIcon.Warning, 10000))
        # One-time engine note (Parakeet fell back to Whisper, or an
        # unsupported language forced Whisper): calm info balloon after the
        # ready one, never an error — the app is working fine.
        eng_note = getattr(self.engine, "engine_note", None)
        if eng_note:
            self.engine.engine_note = None
            from PySide6.QtCore import QTimer
            QTimer.singleShot(6000, lambda: self.tray.showMessage(
                "Dictate — speech engine", eng_note,
                QSystemTrayIcon.Information, 10000))
        # Update check: throttled (max ~1 HTTP call/day), fail-silent,
        # runs off the GUI thread. Result crosses back via signal.
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        model_lifecycle.update_check(self._sig_update_available.emit)

    def _on_update_available(self, tag: str, url: str):
        self._update_url = url
        self.tray.showMessage(
            self.tr("update_title"),
            self.tr("update_body", tag=tag),
            QSystemTrayIcon.Information, 10000)
        try:
            self.tray.messageClicked.disconnect(self._open_update_page)
        except (RuntimeError, TypeError):
            pass
        self.tray.messageClicked.connect(self._open_update_page)

    def _open_update_page(self):
        url = getattr(self, "_update_url", None)
        if url:
            import webbrowser
            webbrowser.open(url)

    # ---- results and errors (GUI thread) --------------------------------

    def _on_result(self, text: str):
        self.delivery.on_result(text)

    def _run_voice_command(self, cmd):
        self.delivery.run_voice_command(cmd)

    def _on_error(self, msg: str):
        log.error("%s", msg)
        self.overlay.hide_overlay()
        self._set_state(IDLE if self.engine.active_device else LOADING)
        # Error beep: descending two-tone
        self._beep(440, 80)
        self._beep(330, 80)
        # Friendly toast for common errors, tray balloon for the rest
        friendly = None
        low = msg.lower()
        if "no usable microphone" in low or "microphone" in low:
            friendly = "no microphone detected — check Settings"
        elif "model" in low and "load" in low:
            friendly = "model failed to load — check your internet and restart"
        elif "cuda" in low or "gpu" in low or "device" in low:
            friendly = "GPU failed — fell back to CPU"
        if friendly:
            if "microphone" in friendly:
                friendly = self.tr("no_mic")
            self.overlay.flash_toast(friendly)
        self.tray.showMessage("Dictate error", msg, QSystemTrayIcon.Critical, 5000)

    def _beep(self, freq: int, ms: int):
        if not self.sounds:
            return
        def _play():
            try:
                import winsound
                winsound.Beep(freq, ms)
            except Exception:
                pass
        threading.Thread(target=_play, daemon=True).start()

    def _quit(self):
        self._monitor_stop.set()
        self.hotkeys.stop()
        self.recorder.close()
        self.overlay.hide_overlay()
        self.tray.hide()
        self.app.quit()
