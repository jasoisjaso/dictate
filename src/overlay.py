"""Wispr-style recording overlay: a small dark pill pinned to the bottom-centre
of the screen showing a live audio waveform while you talk, a live transcript
preview of what it's hearing (GPU builds), and a blue shimmer while it
transcribes. Click-through via Qt's WindowTransparentForInput.
"""

import math
from collections import deque

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

N_BARS = 30
BAR_W = 3
BAR_GAP = 3
PAD_X = 20
PAD_Y = 14
BAR_MAX = 26
IDLE_H = 3.0
LEVEL_GAIN = 6.5  # float32 speech RMS ~0.02-0.12 -> map to 0..1
PREVIEW_W = 520   # pill width when the live transcript row is shown
PREVIEW_ROW_H = 24


class WaveformOverlay(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.base_w = PAD_X * 2 + N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        self.base_h = BAR_MAX + PAD_Y * 2

        self._levels = deque([0.0] * N_BARS, maxlen=N_BARS)
        self._mode = "recording"       # recording | processing
        self._phase = 0.0
        self._level_source = None      # callable -> float rms
        self._smoothed = 0.0
        self._preview_on = False
        self._preview_text = ""        # written from worker thread (str swap is atomic)
        self._font = QFont("Segoe UI", 10)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._apply_size()

    def set_level_source(self, fn):
        self._level_source = fn

    def set_preview(self, text: str):
        """Called from the preview worker thread; repaint happens on the timer."""
        self._preview_text = text or ""

    # ---- geometry ---------------------------------------------------------

    def _apply_size(self):
        self.W = PREVIEW_W if self._preview_on else self.base_w
        self.H = self.base_h + (PREVIEW_ROW_H if self._preview_on else 0)
        self.resize(self.W, self.H)

    def _place(self):
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.center().x() - self.W // 2, g.bottom() - self.H - 22)

    # ---- state ----------------------------------------------------------

    def show_recording(self, preview: bool = False):
        self._mode = "recording"
        self._levels = deque([0.0] * N_BARS, maxlen=N_BARS)
        self._smoothed = 0.0
        self._preview_on = preview
        self._preview_text = ""
        self._apply_size()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(33)  # ~30 fps

    def show_processing(self):
        self._mode = "processing"
        self._phase = 0.0
        self.update()

    def hide_overlay(self):
        self._timer.stop()
        self._preview_text = ""
        self.hide()

    # ---- animation ------------------------------------------------------

    def _tick(self):
        if self._mode == "recording":
            raw = self._level_source() if self._level_source else 0.0
            norm = min(1.0, raw * LEVEL_GAIN)
            # asymmetric smoothing: jump up fast, fall gently (looks lively)
            self._smoothed = max(norm, self._smoothed * 0.72)
            self._levels.append(self._smoothed)
        else:
            self._phase += 0.35
        self.update()

    # ---- paint ----------------------------------------------------------

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # pill background
        radius = self.base_h / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 19, 22, 236))
        p.drawRoundedRect(self.rect(), radius, radius)
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(QRectF(0.6, 0.6, self.W - 1.2, self.H - 1.2),
                          radius, radius)

        cy = self.base_h / 2
        bars_w = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        x = (self.W - bars_w) / 2

        if self._mode == "recording":
            grad = QLinearGradient(0, 0, 0, self.base_h)
            grad.setColorAt(0.0, QColor("#7cc4ff"))
            grad.setColorAt(1.0, QColor("#3d7dff"))
            for lv in self._levels:
                h = IDLE_H + lv * BAR_MAX
                self._bar(p, x, cy, h, grad)
                x += BAR_W + BAR_GAP
        else:
            grad = QLinearGradient(0, 0, 0, self.base_h)
            grad.setColorAt(0.0, QColor("#9ad0ff"))
            grad.setColorAt(1.0, QColor("#4da3ff"))
            for i in range(N_BARS):
                s = math.sin(self._phase + i * 0.5)
                h = IDLE_H + (0.30 + 0.70 * abs(s)) * (BAR_MAX * 0.62)
                self._bar(p, x, cy, h, grad)
                x += BAR_W + BAR_GAP

        if self._preview_on:
            p.setFont(self._font)
            fm = QFontMetrics(self._font)
            text = self._preview_text or "listening…"
            # show the TAIL of the transcript (the words just spoken)
            elided = fm.elidedText(text, Qt.ElideLeft, self.W - PAD_X * 2)
            p.setPen(QColor(226, 232, 240, 235 if self._preview_text else 120))
            p.drawText(
                QRectF(PAD_X, self.base_h - 6, self.W - PAD_X * 2, PREVIEW_ROW_H),
                Qt.AlignVCenter | Qt.AlignLeft, elided)
        p.end()

    @staticmethod
    def _bar(p, x, cy, h, brush):
        h = max(IDLE_H, h)
        p.setBrush(brush)
        p.drawRoundedRect(QRectF(x, cy - h / 2, BAR_W, h), BAR_W / 2, BAR_W / 2)


# Back-compat alias (ui.py imported StatusOverlay in the first build).
StatusOverlay = WaveformOverlay
