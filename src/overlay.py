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
        self._profile_tag = ""         # e.g. "terminal · verbatim", shown while recording
        self._toast_text = ""          # brief confirmation ("12 words · Ctrl+Z to undo")
        self._toast_until = 0.0        # monotonic deadline for the toast
        self._font = QFont("Segoe UI", 10)
        self._tag_font = QFont("Segoe UI", 8)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._apply_size()

    def set_level_source(self, fn):
        self._level_source = fn

    def set_preview(self, text: str):
        """Called from the preview worker thread; repaint happens on the timer."""
        self._preview_text = text or ""

    def set_profile_tag(self, tag: str):
        """Small label shown in the recording pill, e.g. 'terminal · verbatim'.
        Makes the per-app context awareness visible instead of invisible."""
        self._profile_tag = tag or ""

    def flash_toast(self, text: str, ms: int = 1600):
        """Show a brief confirmation pill (word count, 'scratched', etc.) that
        fades itself after `ms`. Safe to call when the main overlay is hidden —
        it pops up on its own and tears down when the toast expires."""
        import time as _t
        self._toast_text = text or ""
        self._toast_until = _t.monotonic() + ms / 1000.0
        if not self.isVisible():
            self._mode = "toast"
            self._apply_size()
            self._place()
            self.show()
            self.raise_()
        if not self._timer.isActive():
            self._timer.start(33)

    # ---- geometry ---------------------------------------------------------

    def _apply_size(self):
        if self._mode == "toast":
            from PySide6.QtGui import QFontMetrics
            fm = QFontMetrics(self._font)
            tw = fm.horizontalAdvance(self._toast_text or "")
            self.W = max(140, tw + PAD_X * 2)
            self.H = self.base_h
            self.resize(self.W, self.H)
            return
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
        self._profile_tag = ""
        self.hide()

    # ---- animation ------------------------------------------------------

    def _tick(self):
        if self._mode == "toast":
            import time as _t
            if _t.monotonic() >= self._toast_until:
                self._toast_text = ""
                self._timer.stop()
                self.hide()
                return
            self.update()
            return
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

        # --- toast mode: just a centred confirmation line -------------------
        if self._mode == "toast":
            import time as _t
            remaining = self._toast_until - _t.monotonic()
            alpha = 255 if remaining > 0.35 else int(max(0, remaining / 0.35) * 255)
            p.setFont(self._font)
            p.setPen(QColor(226, 232, 240, alpha))
            p.drawText(self.rect(), Qt.AlignCenter, self._toast_text)
            p.end()
            return

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

        # per-app profile tag ("terminal · verbatim") pinned to the top-right,
        # so the context awareness is visible while you speak
        if self._mode == "recording" and self._profile_tag:
            p.setFont(self._tag_font)
            fm2 = QFontMetrics(self._tag_font)
            tag = self._profile_tag
            tw = fm2.horizontalAdvance(tag) + 14
            th = fm2.height() + 4
            tx = self.W - tw - 8
            ty = 5
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(61, 125, 255, 60))
            p.drawRoundedRect(QRectF(tx, ty, tw, th), th / 2, th / 2)
            p.setPen(QColor(198, 219, 255, 240))
            p.drawText(QRectF(tx, ty, tw, th), Qt.AlignCenter, tag)
        p.end()

    @staticmethod
    def _bar(p, x, cy, h, brush):
        h = max(IDLE_H, h)
        p.setBrush(brush)
        p.drawRoundedRect(QRectF(x, cy - h / 2, BAR_W, h), BAR_W / 2, BAR_W / 2)


# Back-compat alias (ui.py imported StatusOverlay in the first build).
StatusOverlay = WaveformOverlay
