"""Settings window + first-run wizard. Everything a non-technical user needs:
microphone, model tier, trigger key (captured live, not typed), language,
cleanup toggles, personal dictionary, start-on-login."""

import logging
import platform

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QRadioButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

log = logging.getLogger("dictate.settings")

MODEL_CHOICES = [
    ("auto", "Auto — pick the best for this PC (recommended)"),
    ("large-v3-turbo", "Turbo — top accuracy, needs a GPU (~1.6 GB)"),
    ("distil-large-v3", "Distil — fast, English only (~1.5 GB)"),
    ("small", "Small — good on CPU / weak GPUs (~500 MB)"),
    ("base", "Base — fastest, lowest accuracy (~150 MB)"),
    ("large-v3", "Large v3 — maximum accuracy, slow (~3 GB)"),
]

LANG_CHOICES = [
    ("en", "English"), ("auto", "Auto-detect (any language)"),
    ("bs", "Bosnian"), ("hr", "Croatian"), ("sr", "Serbian"),
    ("de", "German"), ("es", "Spanish"), ("fr", "French"),
    ("it", "Italian"), ("pt", "Portuguese"), ("nl", "Dutch"),
    ("pl", "Polish"), ("tr", "Turkish"), ("ar", "Arabic"),
    ("hi", "Hindi"), ("ja", "Japanese"), ("ko", "Korean"),
    ("zh", "Chinese"),
]

_KEY_LABELS = {
    "ctrl_r": "Right Ctrl", "ctrl_l": "Left Ctrl", "alt_r": "Right Alt",
    "alt_gr": "Right Alt", "shift_r": "Right Shift", "pause": "Pause",
    "menu": "Menu key", "caps_lock": "Caps Lock", "scroll_lock": "Scroll Lock",
    "space": "Space", "esc": "Esc", "tab": "Tab", "insert": "Insert",
}


def pretty_key(name: str) -> str:
    n = name.strip().lower()
    return _KEY_LABELS.get(n, n.upper() if len(n) <= 3 else n.title())


class KeyCaptureButton(QPushButton):
    """Click, then press any key — captures it via a one-shot pynput listener.
    The main hotkey listener keeps running; we only *read* here, and the
    captured key is applied on Save."""
    captured = Signal(str)

    def __init__(self, initial: str):
        super().__init__(pretty_key(initial))
        self.key_name = initial
        self._listener = None
        self.clicked.connect(self._arm)

    def _arm(self):
        if self._listener is not None:
            return
        self.setText("Press any key…")
        from pynput import keyboard

        def on_press(key):
            name = None
            if isinstance(key, keyboard.Key):
                name = key.name
            elif getattr(key, "char", None):
                name = key.char.lower()
            if name:
                self.key_name = name
                self.captured.emit(name)
            return False  # stop listener after first key

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True

        def finished():
            self._listener = None
            self.setText(pretty_key(self.key_name))

        # poll for listener end on the GUI thread
        from PySide6.QtCore import QTimer
        timer = QTimer(self)

        def check():
            if self._listener is None or not self._listener.running:
                timer.stop()
                finished()

        timer.timeout.connect(check)
        self._listener.start()
        timer.start(100)


class SettingsDialog(QDialog):
    """cfg is the merged config dict. saved(dict) fires with the new user
    overlay after a successful save so the tray app can hot-apply."""
    saved = Signal(dict)

    def __init__(self, cfg: dict, first_run: bool = False, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Dictate — Settings" if not first_run
                            else "Welcome to Dictate")
        self.setMinimumWidth(520)
        self.setMinimumHeight(500)
        # Outer layout: scroll area fills the middle, buttons pinned at bottom
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area wrapping all the settings content
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_content = QWidget()
        root = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll)

        if first_run:
            intro = QLabel(
                "<b>Dictate turns your voice into text in any app.</b><br>"
                "Check these few settings once and you're done — "
                "everything runs on this PC, nothing goes to the cloud.")
            intro.setWordWrap(True)
            root.addWidget(intro)

        # --- Trigger -----------------------------------------------------
        g_trig = QGroupBox("How you talk to it")
        f = QFormLayout(g_trig)
        self.rb_ptt = QRadioButton("Hold a key while talking (recommended)")
        self.rb_toggle = QRadioButton("Tap once to start, tap again (or go quiet) to stop")
        hk = cfg.get("hotkeys", {})
        (self.rb_ptt if hk.get("mode", "push_to_talk") == "push_to_talk"
         else self.rb_toggle).setChecked(True)
        f.addRow(self.rb_ptt)
        f.addRow(self.rb_toggle)
        self.btn_ptt = KeyCaptureButton(hk.get("push_to_talk_key", "ctrl_r"))
        self.btn_toggle = KeyCaptureButton(hk.get("toggle_key", "f9"))
        f.addRow("Hold-to-talk key:", self.btn_ptt)
        f.addRow("Tap-to-talk key:", self.btn_toggle)
        self.btn_copy = KeyCaptureButton(hk.get("copy_key", "f8"))
        f.addRow("Copy last dictation key:", self.btn_copy)
        self.btn_mode = KeyCaptureButton(hk.get("mode_cycle_key", "f7"))
        f.addRow("Cycle modes key:", self.btn_mode)
        self.btn_rerecord = KeyCaptureButton(hk.get("rerecord_key", "f6"))
        f.addRow("Re-record last key:", self.btn_rerecord)
        root.addWidget(g_trig)

        # --- Microphone ----------------------------------------------------
        g_mic = QGroupBox("Microphone")
        f = QFormLayout(g_mic)
        self.cb_mic = QComboBox()
        self.cb_mic.addItem("System default", None)
        try:
            from . import audio as _audio
        except ImportError:
            import audio as _audio
        for idx, name in _audio.list_input_devices():
            self.cb_mic.addItem(name, idx)
        want = cfg.get("audio", {}).get("input_device")
        if want is not None:
            pos = self.cb_mic.findData(want)
            if pos >= 0:
                self.cb_mic.setCurrentIndex(pos)
        f.addRow("Use microphone:", self.cb_mic)
        root.addWidget(g_mic)

        # --- Model ---------------------------------------------------------
        g_model = QGroupBox("Speech recognition")
        f = QFormLayout(g_model)
        self.cb_model = QComboBox()
        for val, label in MODEL_CHOICES:
            self.cb_model.addItem(label, val)
        cur = cfg.get("whisper", {}).get("model_size", "auto")
        pos = self.cb_model.findData(cur)
        self.cb_model.setCurrentIndex(pos if pos >= 0 else 0)
        f.addRow("Model:", self.cb_model)
        try:
            try:
                from . import device as _device
            except ImportError:
                import device as _device
            tier = _device.detect()
            hint = (f"Auto on this PC = {tier.model_size} on {tier.device}"
                    f" ({tier.compute_type})")
            if getattr(tier, "amd_gpu", False):
                hint += "\nAMD GPU detected — using CPU. DirectML GPU acceleration is on the roadmap."
        except Exception:
            hint = ""
        if hint:
            lbl = QLabel(hint)
            lbl.setStyleSheet("color: gray")
            lbl.setWordWrap(True)
            f.addRow("", lbl)
        self.cb_lang = QComboBox()
        for val, label in LANG_CHOICES:
            self.cb_lang.addItem(label, val)
        cur = cfg.get("whisper", {}).get("language", "en")
        pos = self.cb_lang.findData(cur)
        self.cb_lang.setCurrentIndex(pos if pos >= 0 else 0)
        f.addRow("Language:", self.cb_lang)
        root.addWidget(g_model)

        # --- Visualizer -------------------------------------------------------
        g_vis = QGroupBox("Visualizer")
        f = QFormLayout(g_vis)
        self.cb_vis = QComboBox()
        self.cb_vis.addItem("Equalizer — clean grey bars", "equalizer")
        self.cb_vis.addItem("Blob — colour-shifting orb (reacts to pitch & volume)", "blob")
        cur_vis = cfg.get("overlay", {}).get("style", "equalizer")
        pos = self.cb_vis.findData(cur_vis)
        self.cb_vis.setCurrentIndex(pos if pos >= 0 else 0)
        f.addRow("Style:", self.cb_vis)
        root.addWidget(g_vis)

        # --- Cleanup + dictionary -------------------------------------------
        g_clean = QGroupBox("Make me sound good")
        v = QVBoxLayout(g_clean)
        cl = cfg.get("cleanup", {})
        self.chk_fillers = QCheckBox('Remove filler words ("um", "uh", ...)')
        self.chk_fillers.setChecked(bool(cl.get("remove_fillers", True)))
        v.addWidget(self.chk_fillers)
        self.chk_auto_punct = QCheckBox("Auto-punctuation (add periods + capitalise automatically)")
        self.chk_auto_punct.setChecked(bool(cfg.get("post_processing", {}).get("auto_punctuation", False)))
        v.addWidget(self.chk_auto_punct)
        self.chk_persist_history = QCheckBox("Save dictation history to disk (off by default for privacy)")
        self.chk_persist_history.setChecked(bool(cfg.get("history", {}).get("persist", False)))
        v.addWidget(self.chk_persist_history)
        v.addWidget(QLabel("Extra filler words to strip "
                           "(comma-separated, e.g. like, you know, basically):"))
        _extra = cl.get("custom_fillers", []) or []
        if isinstance(_extra, str):
            _extra = [p.strip() for p in _extra.split(",")]
        self.ed_fillers = QLineEdit(", ".join(str(x).strip()
                                              for x in _extra if str(x).strip()))
        self.ed_fillers.setPlaceholderText("like, you know, basically, actually")
        v.addWidget(self.ed_fillers)
        v.addWidget(QLabel("My words (teach it names and jargon):"))
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["When I say…", "Type this"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setMaximumHeight(140)
        for k, val in cfg.get("dictionary", {}).items():
            self._add_row(k, val)
        row_btns = QHBoxLayout()
        b_add = QPushButton("Add word")
        b_add.clicked.connect(lambda: self._add_row("", ""))
        b_del = QPushButton("Remove selected")
        b_del.clicked.connect(self._del_row)
        row_btns.addWidget(b_add)
        row_btns.addWidget(b_del)
        row_btns.addStretch(1)
        v.addWidget(self.tbl)
        v.addLayout(row_btns)
        root.addWidget(g_clean)

        # --- Startup ---------------------------------------------------------
        self.chk_login = QCheckBox("Start Dictate when I log in to Windows")
        if platform.system() == "Windows":
            try:
                from . import startup as _startup
            except ImportError:
                import startup as _startup
            self._startup = _startup
            self.chk_login.setChecked(_startup.is_enabled())
        else:
            self._startup = None
            self.chk_login.setEnabled(False)
        root.addWidget(self.chk_login)

        # --- Mic test ---------------------------------------------------------
        g_test = QGroupBox("Test your setup")
        tv = QVBoxLayout(g_test)
        tv.addWidget(QLabel("Record 3 seconds of speech and see if it transcribes:"))
        row = QHBoxLayout()
        self.btn_mic_test = QPushButton("Record 3s & transcribe")
        self.btn_mic_test.clicked.connect(self._run_mic_test)
        row.addWidget(self.btn_mic_test)
        self.lbl_mic_result = QLabel("")
        self.lbl_mic_result.setWordWrap(True)
        self.lbl_mic_result.setStyleSheet(
            "background:#101214; color:#e8eaec; border:1px solid #2a2f34;"
            "border-radius:6px; padding:10px; min-height:32px;")
        row.addWidget(self.lbl_mic_result, 1)
        tv.addLayout(row)
        root.addWidget(g_test)
        root.addStretch(1)

        # --- Buttons (pinned at bottom, outside scroll area) ----------------
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _add_row(self, k: str, v: str):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(k))
        self.tbl.setItem(r, 1, QTableWidgetItem(v))

    def _del_row(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.tbl.removeRow(r)

    def _run_mic_test(self):
        """Record 3 seconds of audio, transcribe, and show the result inline.
        Uses the main app's already-loaded model via a signal, so we don't
        try to load a second model instance (which was the bug)."""
        self.btn_mic_test.setEnabled(False)
        self.lbl_mic_result.setText("Recording 3s... say something now!")
        mic_idx = self.cb_mic.currentData()

        def _worker():
            try:
                try:
                    from . import audio as _audio
                except ImportError:
                    import audio as _audio
                rec = _audio.AudioRecorder(input_device=mic_idx)
                rec.start_recording()
                import time as _t
                _t.sleep(3.0)
                audio_data = rec.stop_recording()
                rec.close()
                if audio_data.size < 1600:
                    self.lbl_mic_result.setText("No audio captured — check your mic is plugged in")
                    return
                # Use the main app's engine (already loaded) instead of
                # creating a new one. We access it via QApplication's
                # top-level widgets — the tray app stores a reference.
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                engine = None
                # Walk the app's children to find the DictationTrayApp
                for obj in app.children():
                    if hasattr(obj, "engine") and obj.engine is not None:
                        if hasattr(obj.engine, "_model") and obj.engine._model is not None:
                            engine = obj.engine
                            break
                if engine is None:
                    # Fallback: load a standalone engine (model may not be ready yet)
                    self.lbl_mic_result.setText(
                        "Model not loaded yet — wait for the green tray icon, then try again")
                    return
                raw = engine.transcribe_audio_buffer(audio_data)
                text = engine.post_process(raw) if raw else ""
                if text:
                    self.lbl_mic_result.setText(f'<b>Heard:</b> "{text}"')
                else:
                    self.lbl_mic_result.setText(
                        "Nothing transcribed — try speaking louder or closer")
            except Exception as ex:
                self.lbl_mic_result.setText(f"Error: {ex}")
            finally:
                self.btn_mic_test.setEnabled(True)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _save(self):
        overlay = {
            "whisper": {
                "model_size": self.cb_model.currentData(),
                "language": self.cb_lang.currentData(),
            },
            "overlay": {
                "style": self.cb_vis.currentData(),
            },
            "hotkeys": {
                "mode": ("push_to_talk" if self.rb_ptt.isChecked() else "toggle"),
                "push_to_talk_key": self.btn_ptt.key_name,
                "toggle_key": self.btn_toggle.key_name,
                "abort_key": self.cfg.get("hotkeys", {}).get("abort_key", "esc"),
                "copy_key": self.btn_copy.key_name,
                "mode_cycle_key": self.btn_mode.key_name,
                "rerecord_key": self.btn_rerecord.key_name,
            },
            "cleanup": {
                "remove_fillers": self.chk_fillers.isChecked(),
                "custom_fillers": [w for w in (
                    p.strip() for p in self.ed_fillers.text().split(",")) if w],
            },
            "post_processing": {
                "auto_punctuation": self.chk_auto_punct.isChecked(),
            },
            "history": {
                "persist": self.chk_persist_history.isChecked(),
            },
            "dictionary": {},
        }
        mic = self.cb_mic.currentData()
        if mic is not None:
            overlay["audio"] = {"input_device": int(mic)}
        for r in range(self.tbl.rowCount()):
            k = (self.tbl.item(r, 0).text() if self.tbl.item(r, 0) else "").strip()
            v = (self.tbl.item(r, 1).text() if self.tbl.item(r, 1) else "").strip()
            if k and v:
                overlay["dictionary"][k] = v
        if self._startup is not None:
            if self.chk_login.isChecked():
                self._startup.enable()
            else:
                self._startup.disable()
        try:
            from . import config as _config
        except ImportError:
            import config as _config
        _config.save(overlay)
        log.info("settings saved: %s", {k: v for k, v in overlay.items()
                                        if k != "dictionary"})
        self.saved.emit(overlay)
        self.accept()
