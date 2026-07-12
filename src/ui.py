"""System tray app: state machine, global hotkeys (push-to-talk or toggle),
worker threads. Hotkey events arrive on pynput's thread and cross into the GUI
thread via Qt signals.

Trigger models (config [hotkeys].mode):
  push_to_talk (default) — hold a single key (default Right Ctrl), speak,
    release. Right Ctrl alone triggers nothing in terminals / PowerShell / WSL,
    which is why it replaced the old Ctrl+Alt+D combo.
  toggle — tap the key once to start (auto-stops after silence), tap to stop.
    This is the hands-free mode.
"""

import logging
import re
import threading
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .audio import AudioRecorder
from .engine import WhisperTranscriber
from .overlay import WaveformOverlay
from . import appcontext, win32_input
from .history import History

log = logging.getLogger("dictate.ui")

LOADING, IDLE, RECORDING, TRANSCRIBING = "loading", "idle", "recording", "transcribing"

STATE_COLOR = {
    LOADING: "#8a939b",
    IDLE: "#46c07a",
    RECORDING: "#e05252",
    TRANSCRIBING: "#4da3ff",
}


def _make_icon(color: str) -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(0, 0, 0, 60))
    p.setBrush(QColor(color))
    p.drawEllipse(6, 6, 52, 52)
    p.setBrush(QColor("#ffffff"))
    p.setPen(QColor("#ffffff"))
    p.drawRoundedRect(26, 16, 12, 22, 6, 6)
    p.drawArc(20, 26, 24, 18, 180 * 16, 180 * 16)
    p.drawRect(30, 44, 4, 6)
    p.drawRect(24, 50, 16, 3)
    p.end()
    return QIcon(pm)


def _parse_key(name: str):
    """Config string -> pynput key object. Accepts single chars, <ctrl> style,
    and friendly names like ctrl_r / alt_gr / f9 / pause / space."""
    from pynput import keyboard

    n = name.strip().lower().strip("<>")
    special = {
        "ctrl_r": keyboard.Key.ctrl_r, "rctrl": keyboard.Key.ctrl_r,
        "ctrl_l": keyboard.Key.ctrl_l, "lctrl": keyboard.Key.ctrl_l,
        "ctrl": keyboard.Key.ctrl,
        "alt_r": keyboard.Key.alt_r, "alt_gr": keyboard.Key.alt_gr,
        "altgr": keyboard.Key.alt_gr, "alt_l": keyboard.Key.alt_l,
        "alt": keyboard.Key.alt,
        "shift_r": keyboard.Key.shift_r, "shift": keyboard.Key.shift,
        "cmd": keyboard.Key.cmd, "win": keyboard.Key.cmd,
        "pause": keyboard.Key.pause, "scroll_lock": keyboard.Key.scroll_lock,
        "caps_lock": keyboard.Key.caps_lock, "menu": keyboard.Key.menu,
        "space": keyboard.Key.space, "esc": keyboard.Key.esc,
        "tab": keyboard.Key.tab, "insert": keyboard.Key.insert,
    }
    for i in range(1, 13):
        special[f"f{i}"] = getattr(keyboard.Key, f"f{i}")
    if n in special:
        return special[n]
    if len(n) == 1:
        return keyboard.KeyCode.from_char(n)
    log.warning("unknown key %r; falling back to Right Ctrl", name)
    return keyboard.Key.ctrl_r


def _pretty_key(name: str) -> str:
    return {
        "ctrl_r": "Right Ctrl", "ctrl_l": "Left Ctrl", "alt_r": "Right Alt",
        "alt_gr": "Right Alt", "pause": "Pause", "menu": "Menu key",
        "caps_lock": "Caps Lock", "scroll_lock": "Scroll Lock",
    }.get(name.strip().lower(), name.strip().upper() if len(name.strip()) == 1
          else name.strip().title())


class DictationTrayApp(QObject):
    _sig_ptt_start = Signal()
    _sig_ptt_stop = Signal()
    _sig_toggle = Signal()
    _sig_abort = Signal()
    _sig_model_ready = Signal(str)
    _sig_result = Signal(str)
    _sig_error = Signal(str)
    _sig_autostop = Signal()
    _sig_dl_start = Signal(str)
    _sig_dl_progress = Signal(int)
    _sig_dl_done = Signal()

    def __init__(self, cfg: dict, app: QApplication, first_run: bool = False):
        super().__init__()
        self.cfg = cfg
        self.app = app
        self.state = LOADING
        self.engine = WhisperTranscriber(cfg)
        self.recorder = AudioRecorder(
            input_device=cfg.get("audio", {}).get("input_device"))
        self.overlay = WaveformOverlay()
        self.overlay.set_level_source(self.recorder.current_level)
        self.last_injected_len = 0
        self._monitor_stop = threading.Event()

        vad = cfg.get("vad", {})
        self.silence_timeout = float(vad.get("silence_timeout", 2.0))

        inj = cfg.get("injection", {})
        self.inject_mode = inj.get("mode", "auto")
        self.paste_threshold = int(inj.get("paste_threshold", 300))
        self.sounds = bool(cfg.get("feedback", {}).get("sounds", True))
        self.live_preview = bool(cfg.get("preview", {}).get("live_preview", True))
        self.history = History(limit=25)
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

        self.tray = QSystemTrayIcon(_make_icon(STATE_COLOR[LOADING]))
        self._build_menu()
        self._set_state(LOADING)
        self.tray.show()

        self._sig_ptt_start.connect(self._on_ptt_start)
        self._sig_ptt_stop.connect(self._on_ptt_stop)
        self._sig_toggle.connect(self._on_toggle)
        self._sig_abort.connect(self._on_abort)
        self._sig_model_ready.connect(self._on_model_ready)
        self._sig_result.connect(self._on_result)
        self._sig_error.connect(self._on_error)
        self._sig_autostop.connect(self._stop_and_transcribe)
        self._sig_dl_start.connect(self._on_dl_start)
        self._sig_dl_progress.connect(self._on_dl_progress)
        self._sig_dl_done.connect(self._on_dl_done)
        self._dl_dialog = None

        self._start_hotkeys()
        threading.Thread(target=self._preload_model, daemon=True).start()
        if first_run:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, lambda: self._open_settings(first_run=True))

    # ---- setup ----------------------------------------------------------

    def _trigger_hint(self) -> str:
        if self.mode == "push_to_talk":
            return f"Hold {_pretty_key(self.ptt_name)} and talk"
        return f"Tap {_pretty_key(self.toggle_name)} to talk"

    def _build_menu(self):
        menu = QMenu()
        self.act_status = QAction("Loading model…")
        self.act_status.setEnabled(False)
        menu.addAction(self.act_status)
        self.act_hint = QAction(self._trigger_hint())
        self.act_hint.setEnabled(False)
        menu.addAction(self.act_hint)
        menu.addSeparator()
        act_settings = QAction("Settings…")
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)
        act_history = QAction("History…")
        act_history.triggered.connect(self._open_history)
        menu.addAction(act_history)
        menu.addSeparator()
        act_quit = QAction("Quit")
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self._menu = menu
        self._act_settings = act_settings

    def _open_history(self):
        """Recent dictations (session-only, never written to disk) with
        one-click copy — the rescue hatch when text landed in the wrong app."""
        from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                                       QListWidget, QListWidgetItem,
                                       QPushButton, QVBoxLayout)
        dlg = QDialog()
        dlg.setWindowTitle("Dictate — History (this session)")
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
        from .settings_gui import SettingsDialog
        dlg = SettingsDialog(self.cfg, first_run=first_run)
        dlg.saved.connect(self._apply_settings)
        dlg.exec()

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
        try:
            self._listener.stop()
        except Exception:
            pass
        self._start_hotkeys()
        self.recorder.set_input_device(
            self.cfg.get("audio", {}).get("input_device"))
        cl = self.cfg.get("cleanup", {})
        self.engine.remove_fillers = bool(cl.get("remove_fillers", True))
        self.engine.dictionary = {str(k): str(v) for k, v in
                                  self.cfg.get("dictionary", {}).items()}
        lang = self.cfg.get("whisper", {}).get("language", "en")
        self.engine.language = None if lang in ("", "auto") else lang
        self._set_state(self.state)
        want_model = self.cfg.get("whisper", {}).get("model_size", "auto")
        if want_model not in ("auto", self.engine.model_size):
            self.tray.showMessage(
                "Dictate", "Model change takes effect after you restart Dictate.",
                QSystemTrayIcon.Information, 5000)

    def _start_hotkeys(self):
        from pynput import keyboard

        self._ptt_key = _parse_key(self.ptt_name)
        self._toggle_key = _parse_key(self.toggle_name)
        self._abort_key = _parse_key(self.abort_name)
        self._ptt_down = False
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()
        log.info("hotkeys: mode=%s ptt=%s toggle=%s abort=%s",
                 self.mode, self.ptt_name, self.toggle_name, self.abort_name)

    @staticmethod
    def _key_matches(key, target) -> bool:
        if target is None:
            return False
        if key == target:
            return True
        kc = getattr(key, "char", None)
        tc = getattr(target, "char", None)
        if kc and tc:
            return kc.lower() == tc.lower()
        return False

    def _on_press(self, key):
        try:
            if self.mode == "push_to_talk" and self._key_matches(key, self._ptt_key):
                if not self._ptt_down:          # ignore auto-repeat
                    self._ptt_down = True
                    self._sig_ptt_start.emit()
                return
            if self._key_matches(key, self._abort_key):
                self._sig_abort.emit()
                return
            if self.mode == "toggle" and self._key_matches(key, self._toggle_key):
                self._sig_toggle.emit()
        except Exception:
            log.exception("hotkey on_press error")

    def _on_release(self, key):
        try:
            if self.mode == "push_to_talk" and self._key_matches(key, self._ptt_key):
                if self._ptt_down:
                    self._ptt_down = False
                    self._sig_ptt_stop.emit()
        except Exception:
            log.exception("hotkey on_release error")

    def _preload_model(self):
        try:
            try:
                from . import first_run, paths
            except ImportError:
                import first_run
                import paths
            if not first_run.model_is_cached(self.engine.model_size,
                                             paths.models_dir()):
                self._sig_dl_start.emit(self.engine.model_size)
                try:
                    first_run.download_with_progress(
                        self.engine.model_size, paths.models_dir(),
                        self._sig_dl_progress.emit)
                finally:
                    self._sig_dl_done.emit()
            self.engine.load()
            self._sig_model_ready.emit(self.engine.active_device or "?")
        except Exception as ex:
            log.exception("model preload failed")
            self._sig_error.emit(f"Model failed to load: {ex}")

    # ---- first-run download dialog (GUI thread) ---------------------------

    def _on_dl_start(self, model_size: str):
        from PySide6.QtWidgets import QProgressDialog
        from .first_run import APPROX_SIZE
        size_hint = APPROX_SIZE.get(model_size, "")
        label = (f"Downloading the speech model ({model_size}"
                 + (f", about {size_hint}" if size_hint else "")
                 + ").\nThis happens once — after this Dictate works offline.")
        dlg = QProgressDialog(label, None, 0, 100)
        dlg.setWindowTitle("Dictate — first-time setup")
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setValue(0)
        dlg.show()
        self._dl_dialog = dlg

    def _on_dl_progress(self, pct: int):
        if self._dl_dialog is not None:
            self._dl_dialog.setValue(pct)

    def _on_dl_done(self):
        if self._dl_dialog is not None:
            self._dl_dialog.close()
            self._dl_dialog = None

    # ---- state (GUI thread) ---------------------------------------------

    def _set_state(self, state: str):
        self.state = state
        self.tray.setIcon(_make_icon(STATE_COLOR[state]))
        label = {LOADING: "Loading model…", IDLE: "Ready", RECORDING: "Listening…",
                 TRANSCRIBING: "Transcribing…"}[state]
        dev = f" on {self.engine.active_device}" if self.engine.active_device else ""
        self.tray.setToolTip(f"Dictate — {label}\n{self._trigger_hint()}")
        self.act_status.setText(f"{label}  ·  {self.engine.model_size}{dev}")
        if hasattr(self, "act_hint"):
            self.act_hint.setText(self._trigger_hint())

    def _on_model_ready(self, device: str):
        self._set_state(IDLE)
        self.tray.showMessage(
            "Dictate ready",
            f"{self.engine.model_size} on {device}. {self._trigger_hint()}.",
            QSystemTrayIcon.Information, 4000)

    def _begin_recording(self) -> bool:
        if self.state != IDLE:
            return False
        self._rec_app = appcontext.foreground_exe()
        self._rec_profile = appcontext.resolve_profile(self._rec_app,
                                                       self.app_profiles)
        if self._rec_profile:
            log.info("app context: %s -> profile %s", self._rec_app,
                     self._rec_profile.get("_profile"))
        try:
            self.recorder.start_recording()
        except RuntimeError as ex:
            self._on_error(str(ex))
            return False
        self._set_state(RECORDING)
        preview_on = (self.live_preview
                      and self.engine.active_device == "cuda")
        self.overlay.show_recording(preview=preview_on)
        if preview_on:
            self._preview_stop.clear()
            threading.Thread(target=self._preview_worker, daemon=True).start()
        self._beep(880, 70)
        return True

    def _stop_and_transcribe(self):
        if self.state != RECORDING:
            return
        self._monitor_stop.set()
        self._preview_stop.set()
        audio = self.recorder.stop_recording()
        self._set_state(TRANSCRIBING)
        self.overlay.show_processing()
        self._beep(660, 70)
        threading.Thread(target=self._transcribe_worker, args=(audio,),
                         daemon=True).start()

    # push-to-talk
    def _on_ptt_start(self):
        self._begin_recording()

    def _on_ptt_stop(self):
        self._stop_and_transcribe()

    # toggle / hands-free
    def _on_toggle(self):
        if self.state == IDLE:
            if self._begin_recording() and self.silence_timeout > 0:
                self._monitor_stop.clear()
                threading.Thread(target=self._silence_monitor, daemon=True).start()
        elif self.state == RECORDING:
            self._stop_and_transcribe()

    def _on_abort(self):
        if self.state != RECORDING:
            return
        self._monitor_stop.set()
        self._preview_stop.set()
        self._ptt_down = False
        self.recorder.abort()
        self.overlay.hide_overlay()
        self._set_state(IDLE)

    def _on_result(self, text: str):
        self.overlay.hide_overlay()
        self._set_state(IDLE)
        if not text:
            return
        norm = re.sub(r"[^a-z ]", "", text.lower()).strip()
        if norm == "scratch that":
            win32_input.inject_backspaces(self.last_injected_len)
            self.last_injected_len = 0
            return
        self.history.add(text, app=self._rec_app)
        payload = text if text.endswith("\n") else text + " "
        how = win32_input.choose_injection(payload, mode=self.inject_mode,
                                           paste_threshold=self.paste_threshold)
        if how == "paste":
            win32_input.inject_text_via_paste(payload)
        else:
            win32_input.inject_text_native_unicode(payload)
        self.last_injected_len = len(payload)

    def _on_error(self, msg: str):
        log.error("%s", msg)
        self.overlay.hide_overlay()
        self._set_state(IDLE if self.engine.active_device else LOADING)
        self.tray.showMessage("Dictate error", msg, QSystemTrayIcon.Critical, 5000)

    # ---- worker threads --------------------------------------------------

    def _transcribe_worker(self, audio):
        try:
            t0 = time.time()
            raw = self.engine.transcribe_audio_buffer(audio)
            text = self.engine.post_process(raw, profile=self._rec_profile)
            log.info("transcribed %.1fs audio in %.1fs: %r",
                     len(audio) / 16000, time.time() - t0, text)
            self._sig_result.emit(text)
        except Exception as ex:
            log.exception("transcription failed")
            self._sig_error.emit(f"Transcription failed: {ex}")

    def _preview_worker(self):
        """Live transcript while recording (GPU only): re-transcribe the whole
        take roughly once a second and stream the tail into the overlay pill.
        The engine lock serialises us against the final pass, so worst case
        the final transcription waits ~1s for the last preview chunk."""
        while not self._preview_stop.wait(1.0):
            if self.state != RECORDING or self.engine._model is None:
                continue
            dur = self.recorder.duration
            if dur < 0.8 or dur > 90:      # nothing to show / too long to re-run
                continue
            try:
                snapshot = self.recorder.peek_tail(dur)
                raw = self.engine.transcribe_audio_buffer(snapshot)
                if raw and not self._preview_stop.is_set():
                    self.overlay.set_preview(raw)
            except Exception as ex:
                log.debug("preview pass failed: %s", ex)

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

    def _quit(self):
        self._monitor_stop.set()
        try:
            self._listener.stop()
        except Exception:
            pass
        self.recorder.close()
        self.overlay.hide_overlay()
        self.tray.hide()
        self.app.quit()
