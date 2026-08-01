"""Tray shell: icon painting, context menu, status/stats/mode labels.

Pure view layer. Reads presentation state from the app coordinator (tr,
engine, dictation mode, session counters) and forwards menu clicks to app
methods. No recording or engine logic lives here.
"""

import logging
import time

from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .app_states import IDLE, LOADING, MODE_LABELS, RECORDING, STATE_COLOR, TRANSCRIBING
from .hotkeys import pretty_key

log = logging.getLogger("dictate.tray")


def make_icon(color: str) -> QIcon:
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


class TrayShell:
    """Owns the QSystemTrayIcon + QMenu; renders app state into them."""

    def __init__(self, app):
        self.app = app  # DictationTrayApp coordinator
        self.tray = QSystemTrayIcon(make_icon(STATE_COLOR[LOADING]))

    def build_menu(self):
        app = self.app
        menu = QMenu()
        self.act_status = QAction(app.tr("loading"))
        self.act_status.setEnabled(False)
        menu.addAction(self.act_status)
        self.act_hint = QAction(app._trigger_hint())
        self.act_hint.setEnabled(False)
        menu.addAction(self.act_hint)
        self.act_stats = QAction("0 words · 0 WPM")
        self.act_stats.setEnabled(False)
        menu.addAction(self.act_stats)
        self.act_mode = QAction(f"{app.tr('mode')}: {MODE_LABELS[app._dict_mode]}  ({pretty_key(app.mode_cycle_name)} {app.tr('cycle_hint')})")
        self.act_mode.setEnabled(False)
        menu.addAction(self.act_mode)
        menu.addSeparator()
        # Every QAction needs the menu as parent: QMenu.addAction does NOT
        # take ownership, and a parentless local QAction gets garbage
        # collected once build_menu returns — its menu entry (Quit!)
        # silently disappears from the tray.
        act_copy = QAction(f"{app.tr('copy_last')}  ({pretty_key(app.copy_name)})", menu)
        act_copy.triggered.connect(app._copy_last)
        menu.addAction(act_copy)
        act_settings = QAction(app.tr("settings"), menu)
        act_settings.triggered.connect(app._open_settings)
        menu.addAction(act_settings)
        act_history = QAction(app.tr("history"), menu)
        act_history.triggered.connect(app._open_history)
        menu.addAction(act_history)
        act_guide = QAction(app.tr("guide"), menu)
        act_guide.triggered.connect(app._open_guide)
        menu.addAction(act_guide)
        menu.addSeparator()
        act_quit = QAction(app.tr("quit"), menu)
        act_quit.triggered.connect(app._quit)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self._menu = menu
        self._act_settings = act_settings

    def update_stats(self):
        if hasattr(self, "act_stats"):
            w = self.app._session_words
            elapsed = max(1.0, time.time() - self.app._session_start)
            wpm = int(w / (elapsed / 60.0))
            self.act_stats.setText(
                f"{w:,} word{'s' if w != 1 else ''} · {wpm} WPM this session")

    def update_mode_label(self, label: str):
        if hasattr(self, "act_mode"):
            self.act_mode.setText(
                f"Mode: {label}  ({pretty_key(self.app.mode_cycle_name)} to cycle)")

    def render_state(self, state: str):
        """Icon + tooltip + status/hint/mode rows for the given app state."""
        app = self.app
        self.tray.setIcon(make_icon(STATE_COLOR[state]))
        label = {LOADING: app.tr("loading"), IDLE: app.tr("ready"),
                 RECORDING: app.tr("listening"),
                 TRANSCRIBING: app.tr("transcribing")}[state]
        dev = f" on {app.engine.active_device}" if app.engine.active_device else ""
        # AMD GPU note — cached at init so we don't spawn wmic on every state change
        amd_note = ""
        if getattr(app, "_amd_note", "") and app.engine.active_device == "cpu":
            amd_note = app._amd_note
        self.tray.setToolTip(f"Dictate — {label}\n{app._trigger_hint()}")
        self.act_status.setText(f"{label}  ·  {app.engine.model_size}{dev}{amd_note}")
        if hasattr(self, "act_hint"):
            self.act_hint.setText(app._trigger_hint())
        self.update_mode_label(MODE_LABELS[app._dict_mode])
