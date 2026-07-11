"""Wispr-style recording overlay: a small dark pill pinned to the bottom-centre
of the screen showing a live audio waveform while you talk, and a blue shimmer
while it transcribes. Click-through (mouse passes straight to the app below)
via Qt's WindowTransparentForInput — no Tkinter, one GUI event loop.
"""

import math
from collections import deque

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import QWidget

N_BARS = 30
BAR_W = 3
BAR_GAP = 3
PAD_X = 20
PAD_Y = 14
BAR_MAX = 26
IDLE_H = 3.0
LEVEL_GAIN = 6.5  # float32 speech RMS ~0.02-0.12 -> map to 0..1


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

        self.W = PAD_X * 2 + N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        self.H = BAR_MAX + PAD_Y * 2
        self.resize(self.W, self.H)

        self._levels = deque([0.0] * N_BARS, maxlen=N_BARS)
        self._mode = "recording"       # recording | processing
        self._phase = 0.0
        self._level_source = None      # callable -> float rms
        self._smoothed = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_level_source(self, fn):
        self._level_source = fn

    def _place(self):
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.center().x() - self.W // 2, g.bottom() - self.H - 22)

    # ---- state ----------------------------------------------------------

    def show_recording(self):
        self._mode = "recording"
        self._levels = deque([0.0] * N_BARS, maxlen=N_BARS)
        self._smoothed = 0.0
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
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 19, 22, 236))
        p.drawRoundedRect(self.rect(), self.H / 2, self.H / 2)
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(QRectF(0.6, 0.6, self.W - 1.2, self.H - 1.2),
                          self.H / 2, self.H / 2)

        cy = self.H / 2
        x = PAD_X

        if self._mode == "recording":
            grad = QLinearGradient(0, 0, 0, self.H)
            grad.setColorAt(0.0, QColor("#7cc4ff"))
            grad.setColorAt(1.0, QColor("#3d7dff"))
            for lv in self._levels:
                h = IDLE_H + lv * BAR_MAX
                self._bar(p, x, cy, h, grad)
                x += BAR_W + BAR_GAP
        else:
            grad = QLinearGradient(0, 0, 0, self.H)
            grad.setColorAt(0.0, QColor("#9ad0ff"))
            grad.setColorAt(1.0, QColor("#4da3ff"))
            for i in range(N_BARS):
                s = math.sin(self._phase + i * 0.5)
                h = IDLE_H + (0.30 + 0.70 * abs(s)) * (BAR_MAX * 0.62)
                self._bar(p, x, cy, h, grad)
                x += BAR_W + BAR_GAP
        p.end()

    @staticmethod
    def _bar(p, x, cy, h, brush):
        h = max(IDLE_H, h)
        p.setBrush(brush)
        p.drawRoundedRect(QRectF(x, cy - h / 2, BAR_W, h), BAR_W / 2, BAR_W / 2)


# Back-compat alias (ui.py imported StatusOverlay in the first build).
StatusOverlay = WaveformOverlay
