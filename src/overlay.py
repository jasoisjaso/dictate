"""Recording overlay — just the equalizer, nothing else.

No pill, no background rectangle, no rim. The waveform bars float on
screen by themselves, large and grey, the way a clean audio meter looks.

The bars grow from a bottom baseline, are smoothed per-bar for a liquid
feel, and have a subtle glow. A small pulsing red dot on the left signals
recording. Processing = three bouncing grey dots. Toasts are a small
plain text label with no background.

API unchanged — ui.py calls the same methods.
"""

import math
import platform
import time as _time
from collections import deque

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QLinearGradient, QRadialGradient,
                           QFont, QFontMetrics, QBrush)
from PySide6.QtWidgets import QWidget

# ── layout ──────────────────────────────────────────────────────────────
N_BARS = 28
BAR_W = 7
BAR_GAP = 5
BAR_MAX = 52
BAR_MIN = 5
PAD_X = 34
PAD_Y = 18
LEVEL_GAIN = 7.0
PREVIEW_W = 680
PREVIEW_ROW_H = 24
TOAST_STD_W = 260
RADIUS = 20

DOT_R = 6
DOT_SPACE = 36

# ── timing ──────────────────────────────────────────────────────────────
TICK_MS = 33
TOAST_DEFAULT_MS = 1800
ANIM_IN_MS = 200
ANIM_OUT_MS = 130

# ── colours ─────────────────────────────────────────────────────────────
BAR_GRAD = [QColor(180, 188, 200), QColor(140, 150, 165), QColor(100, 110, 125)]
BAR_GLOW = QColor(140, 150, 165, 40)

PRO_DOT = QColor(150, 160, 175)

TEXT_ACTIVE = QColor(220, 226, 234, 230)
TEXT_MUTED = QColor(148, 163, 184, 120)
TAG_TEXT = QColor(186, 230, 253, 200)
TOAST_TEXT = QColor(220, 226, 234, 230)

REC_DOT = QColor(239, 68, 68)


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

        self._levels = deque([0.0] * N_BARS, maxlen=N_BARS)
        self._display = [0.0] * N_BARS
        self._mode = "hidden"
        self._phase = 0.0
        self._level_source = None
        self._smoothed = 0.0
        self._preview_on = False
        self._preview_text = ""
        self._profile_tag = ""
        self._toast_text = ""
        self._toast_until = 0.0
        self._font = QFont("Segoe UI", 10)
        self._tag_font = QFont("Segoe UI", 7, QFont.Medium)
        self._toast_font = QFont("Segoe UI", 10, QFont.Medium)

        self._base_h = BAR_MAX + PAD_Y * 2
        self._total_h = self._base_h + PREVIEW_ROW_H
        self._glow_phase = 0.0
        self._dot_phase = 0.0
        self._dpi_scale = 1.0

        self._opacity = 0.0
        self._anim_dir = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, ev):
        super().showEvent(ev)
        screen = self.screen()
        if screen:
            self._dpi_scale = max(1.0, screen.devicePixelRatio())

    # ── public API ──────────────────────────────────────────────────────

    def set_level_source(self, fn):
        self._level_source = fn

    def set_preview(self, text: str):
        self._preview_text = text or ""

    def set_profile_tag(self, tag: str):
        self._profile_tag = tag or ""

    def flash_toast(self, text: str, ms: int = TOAST_DEFAULT_MS):
        self._toast_text = text or ""
        self._toast_until = _time.monotonic() + ms / 1000.0
        self._mode = "toast"
        self._anim_dir = 1
        if not self.isVisible():
            self._opacity = 0.0
        self._apply_size()
        self._place()
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start(TICK_MS)

    # ── state transitions ───────────────────────────────────────────────

    def show_recording(self, preview: bool = False):
        self._mode = "recording"
        self._levels = deque([0.0] * N_BARS, maxlen=N_BARS)
        self._display = [0.0] * N_BARS
        self._smoothed = 0.0
        self._preview_on = preview
        self._preview_text = ""
        self._glow_phase = 0.0
        self._dot_phase = 0.0
        self._anim_dir = 1
        if not self.isVisible():
            self._opacity = 0.0
        self._apply_size()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(TICK_MS)

    def show_processing(self):
        self._mode = "processing"
        self._phase = 0.0
        if not self._timer.isActive():
            self._timer.start(TICK_MS)
        self.update()

    def hide_overlay(self):
        if self._mode == "hidden":
            return
        self._anim_dir = -1
        if not self._timer.isActive():
            self._timer.start(TICK_MS)

    # ── geometry ────────────────────────────────────────────────────────

    def _apply_size(self):
        s = self._dpi_scale
        if self._mode == "toast":
            fm = QFontMetrics(self._toast_font)
            tw = fm.horizontalAdvance(self._toast_text or "")
            self.resize(int(max(TOAST_STD_W, tw + 52) * s), int(40 * s))
            return
        w = int(PREVIEW_W * s)
        h = int((self._total_h if self._preview_on else self._base_h) * s)
        self.resize(w, h)

    def _place(self):
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            w = self.width()
            target_y = g.bottom() - self.height() - 18
            target_x = g.center().x() - w // 2
            offset = int((1.0 - self._opacity) * 16)
            self.move(target_x, target_y + offset)

    # ── animation tick ──────────────────────────────────────────────────

    def _tick(self):
        if self._anim_dir == 1 and self._opacity < 1.0:
            self._opacity = min(1.0, self._opacity + TICK_MS / ANIM_IN_MS)
            self._place()
        elif self._anim_dir == -1:
            self._opacity -= TICK_MS / ANIM_OUT_MS
            if self._opacity <= 0.0:
                self._opacity = 0.0
                self._anim_dir = 0
                self._mode = "hidden"
                self._preview_text = ""
                self._profile_tag = ""
                self._timer.stop()
                self.hide()
                return
            self._place()

        if self._mode == "toast":
            if _time.monotonic() >= self._toast_until:
                self._toast_text = ""
                self._timer.stop()
                self.hide()
            else:
                self.update()
            return

        if self._mode == "recording":
            raw = self._level_source() if self._level_source else 0.0
            norm = min(1.0, raw * LEVEL_GAIN)
            self._smoothed = max(norm, self._smoothed * 0.72)
            self._levels.append(self._smoothed)
            for i in range(N_BARS):
                target = self._levels[i] if i < len(self._levels) else 0.0
                self._display[i] += (target - self._display[i]) * 0.4
            self._dot_phase += 0.09

        self._phase += 0.35
        self._glow_phase += 0.05
        self.update()

    # ── paint ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self._opacity)

        if self._mode == "toast":
            self._paint_toast(p)
            p.end()
            return

        recording = self._mode == "recording"
        processing = self._mode == "processing"

        if recording:
            self._paint_rec_dot(p)
            self._paint_bars(p)
        elif processing:
            self._paint_processing_dots(p)

        if self._preview_on and self._mode != "toast":
            self._paint_preview(p)
        if self._profile_tag and recording:
            self._paint_tag(p)
        p.end()

    # ── paint helpers ───────────────────────────────────────────────────

    def _paint_rec_dot(self, p):
        """Small pulsing red dot on the left."""
        pulse = 0.5 + 0.5 * math.sin(self._dot_phase)
        cx = PAD_X + DOT_R
        cy = self._base_h / 2
        r = DOT_R + pulse * 0.8
        # soft glow
        glow_r = r + 7 + 2 * pulse
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        grad.setColorAt(0, QColor(239, 68, 68, int(55 + 35 * pulse)))
        grad.setColorAt(1, QColor(239, 68, 68, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)
        # dot
        p.setBrush(REC_DOT)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_bars(self, p):
        """Large grey equalizer bars growing from the bottom baseline.

        No background, no pill — just the bars floating on screen.
        Each bar has a subtle glow bloom behind it and a grey vertical
        gradient (light at top, darker at bottom).
        """
        baseline = self._base_h - PAD_Y
        x_start = PAD_X + DOT_SPACE
        avail_w = self.width() - PAD_X - x_start
        bars_total_w = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        x = x_start + max(0, (avail_w - bars_total_w) / 2)

        grad = QLinearGradient(0, baseline - BAR_MAX, 0, baseline)
        grad.setColorAt(0.0, BAR_GRAD[0])
        grad.setColorAt(0.5, BAR_GRAD[1])
        grad.setColorAt(1.0, BAR_GRAD[2])

        for i in range(N_BARS):
            val = self._display[i]
            h = max(BAR_MIN, val * BAR_MAX)
            bx = x
            by = baseline - h

            # glow bloom
            p.setBrush(BAR_GLOW)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(bx - 2, by - 2, BAR_W + 4, h + 4),
                              (BAR_W + 4) / 2, (BAR_W + 4) / 2)

            # bar
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bx, by, BAR_W, h), BAR_W / 2, BAR_W / 2)
            x += BAR_W + BAR_GAP

    def _paint_processing_dots(self, p):
        """Three bouncing grey dots — thinking indicator."""
        cy = self._base_h / 2
        cx = self.width() / 2
        dot_r = 7
        spacing = 26
        for i in range(3):
            phase = self._phase + i * 0.7
            bounce = math.sin(phase) * 8
            x = cx + (i - 1) * spacing
            y = cy + bounce
            alpha = int(140 + 100 * (0.5 + 0.5 * math.sin(phase)))
            # glow
            grad = QRadialGradient(QPointF(x, y), dot_r + 5)
            grad.setColorAt(0, QColor(PRO_DOT.red(), PRO_DOT.green(),
                                       PRO_DOT.blue(), alpha // 3))
            grad.setColorAt(1, QColor(PRO_DOT.red(), PRO_DOT.green(),
                                       PRO_DOT.blue(), 0))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), dot_r + 5, dot_r + 5)
            # dot
            p.setBrush(QColor(PRO_DOT.red(), PRO_DOT.green(),
                              PRO_DOT.blue(), alpha))
            p.drawEllipse(QPointF(x, y), dot_r, dot_r)

    def _paint_preview(self, p):
        """Live transcript text below the bars — no background."""
        p.setFont(self._font)
        fm = QFontMetrics(self._font)
        text = self._preview_text or "listening..."
        elided = fm.elidedText(text, Qt.ElideLeft, self.width() - PAD_X * 2)
        p.setPen(TEXT_ACTIVE if self._preview_text else TEXT_MUTED)
        p.drawText(
            QRectF(PAD_X, self._base_h - 2, self.width() - PAD_X * 2,
                   PREVIEW_ROW_H),
            Qt.AlignVCenter | Qt.AlignLeft, elided)

    def _paint_tag(self, p):
        """Small text label top-right — no background pill."""
        p.setFont(self._tag_font)
        p.setPen(TAG_TEXT)
        fm = QFontMetrics(self._tag_font)
        tag = self._profile_tag
        tw = fm.horizontalAdvance(tag) + 4
        tx = self.width() - tw - 12
        ty = 8
        p.drawText(QRectF(tx, ty, tw, fm.height() + 2),
                   Qt.AlignVCenter | Qt.AlignRight, tag)

    def _paint_toast(self, p):
        """Plain text toast — no background, no border."""
        remaining = self._toast_until - _time.monotonic()
        alpha = 255 if remaining > 0.35 else int(max(0, remaining / 0.35) * 255)
        p.setFont(self._toast_font)
        p.setPen(QColor(TOAST_TEXT.red(), TOAST_TEXT.green(),
                        TOAST_TEXT.blue(), alpha))
        p.drawText(self.rect(), Qt.AlignCenter, self._toast_text)


# Back-compat alias.
StatusOverlay = WaveformOverlay
