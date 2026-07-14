"""Recording overlay — a glowing pill with a dramatic, premium equalizer.

The old version had thin 2px bars and a flat translucent background that
looked like every other basic waveform widget. This version is completely
different:

- No acrylic / no DWMAPI — the translucent window with rounded painting IS
  the pill shape. Acrylic was filling the window rectangle and squaring the
  corners. Gone.
- Fat 6px bars with 4px gaps and per-bar glow halos — looks like a real
  studio equalizer, not a toy oscilloscope.
- Bars grow from the BOTTOM (not centred) — the Wispr Flow look.
- Rounded gradient body with a 2px coloured rim that matches the state.
- Big pulsing recording dot on the left with a soft glow.
- Bouncing-dot processing animation (three dots, not a shimmer).
- Smooth fade+slide entrance, fade exit.
- Per-bar smoothed decay for a liquid feel.
- DPI-aware sizing.

API unchanged — ui.py calls the same methods.
"""

import math
import platform
import time as _time
from collections import deque

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QLinearGradient, QRadialGradient,
                           QFont, QFontMetrics, QPen, QBrush)
from PySide6.QtWidgets import QWidget

# ── layout ──────────────────────────────────────────────────────────────
N_BARS = 24
BAR_W = 6
BAR_GAP = 4
BAR_MAX = 44
BAR_MIN = 4
PAD_X = 30
PAD_Y = 22
LEVEL_GAIN = 7.0
PREVIEW_W = 640
PREVIEW_ROW_H = 26
TOAST_STD_W = 240
RADIUS = 28

DOT_R = 6
DOT_SPACE = 32

# ── timing ──────────────────────────────────────────────────────────────
TICK_MS = 33
TOAST_DEFAULT_MS = 1800
ANIM_IN_MS = 220
ANIM_OUT_MS = 140

# ── colours ─────────────────────────────────────────────────────────────
BODY_BG = QColor(14, 16, 22, 215)
RIM_REC = QColor(224, 82, 82, 180)
RIM_PRO = QColor(77, 163, 255, 160)
INNER_HL = QColor(255, 255, 255, 10)

GLOW_REC = QColor(224, 82, 82)
GLOW_PRO = QColor(77, 163, 255)

WAVE_GRAD = [QColor("#5eead4"), QColor("#38bdf8"), QColor("#818cf8")]

PRO_DOT = QColor("#4da3ff")

TEXT_ACTIVE = QColor(226, 232, 240, 240)
TEXT_MUTED = QColor(148, 163, 184, 140)
TAG_BG = QColor(56, 189, 248, 50)
TAG_TEXT = QColor(186, 230, 253, 235)


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

        # animation state
        self._opacity = 0.0
        self._anim_dir = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── DPI ─────────────────────────────────────────────────────────────

    def showEvent(self, ev):
        super().showEvent(ev)
        screen = self.screen()
        if screen:
            self._dpi_scale = max(1.0, screen.devicePixelRatio())

    # ── public API (unchanged signatures) ───────────────────────────────

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
            self.resize(int(max(TOAST_STD_W, tw + 52) * s), int(self._base_h * s))
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
            offset = int((1.0 - self._opacity) * 18)
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

        # ── outer glow (drawn behind the pill, extends past the window) ──
        if recording or processing:
            self._paint_outer_glow(p, recording)

        # ── pill body ────────────────────────────────────────────────────
        self._paint_pill_body(p, recording)

        # ── content ──────────────────────────────────────────────────────
        if recording:
            self._paint_rec_dot(p)
            self._paint_bars(p, recording=True)
        elif processing:
            self._paint_processing_dots(p)

        if self._preview_on and self._mode != "toast":
            self._paint_preview(p)
        if self._profile_tag and recording:
            self._paint_tag(p)
        p.end()

    # ── paint helpers ───────────────────────────────────────────────────

    def _paint_outer_glow(self, p, recording):
        """Soft coloured halo that bleeds past the pill edges."""
        pulse = 0.6 + 0.4 * math.sin(self._glow_phase)
        alpha = int(28 + 22 * pulse)
        expand = 6 + 4 * pulse
        base = GLOW_REC if recording else GLOW_PRO
        glow = QColor(base.red(), base.green(), base.blue(), alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(
            QRectF(-expand, -expand,
                   self.width() + expand * 2,
                   self.height() + expand * 2),
            RADIUS + expand, RADIUS + expand)

    def _paint_pill_body(self, p, recording):
        """The pill: dark translucent body + coloured rim + top highlight."""
        w, h = self.width(), self.height()
        # body
        p.setPen(Qt.NoPen)
        p.setBrush(BODY_BG)
        p.drawRoundedRect(self.rect(), RADIUS, RADIUS)
        # coloured rim
        rim = RIM_REC if recording else RIM_PRO
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rim, 2))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), RADIUS, RADIUS)
        # subtle top highlight (frosted glass reflection)
        p.setPen(Qt.NoPen)
        p.setBrush(INNER_HL)
        p.drawRoundedRect(QRectF(4, 3, w - 8, h * 0.4),
                          RADIUS * 0.7, RADIUS * 0.7)

    def _paint_rec_dot(self, p):
        """Pulsing red dot on the left with a soft radial glow."""
        pulse = 0.5 + 0.5 * math.sin(self._dot_phase)
        cx = PAD_X + DOT_R
        cy = self._base_h / 2
        r = DOT_R + pulse
        # glow
        glow_r = r + 8 + 3 * pulse
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        grad.setColorAt(0, QColor(239, 68, 68, int(70 + 50 * pulse)))
        grad.setColorAt(1, QColor(239, 68, 68, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)
        # dot
        p.setBrush(QColor(239, 68, 68, 255))
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_bars(self, p, recording):
        """Fat equalizer bars that grow from the bottom — studio look.

        Each bar has:
        - A wide, low-alpha glow rectangle behind it (the 'bloom')
        - The bar itself with a vertical gradient
        - Rounded top corners only (flat bottom sitting on the baseline)
        """
        baseline = self._base_h - PAD_Y
        x_start = PAD_X + DOT_SPACE
        avail_w = self.width() - PAD_X - x_start
        bars_total_w = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        x = x_start + max(0, (avail_w - bars_total_w) / 2)

        grad = QLinearGradient(0, baseline - BAR_MAX, 0, baseline)
        grad.setColorAt(0.0, WAVE_GRAD[0])
        grad.setColorAt(0.5, WAVE_GRAD[1])
        grad.setColorAt(1.0, WAVE_GRAD[2])
        glow_color = WAVE_GRAD[1]

        for i in range(N_BARS):
            val = self._display[i] if recording else 0.0
            h = max(BAR_MIN, val * BAR_MAX)
            bx = x
            by = baseline - h

            # glow bloom
            p.setBrush(QColor(glow_color.red(), glow_color.green(),
                              glow_color.blue(), 45))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(bx - 2, by - 2, BAR_W + 4, h + 4),
                              (BAR_W + 4) / 2, (BAR_W + 4) / 2)

            # bar
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bx, by, BAR_W, h), BAR_W / 2, BAR_W / 2)
            x += BAR_W + BAR_GAP

    def _paint_processing_dots(self, p):
        """Three bouncing dots — the universal 'thinking' indicator."""
        cy = self._base_h / 2
        cx = self.width() / 2
        dot_r = 6
        spacing = 22
        for i in range(3):
            phase = self._phase + i * 0.7
            bounce = math.sin(phase) * 7
            x = cx + (i - 1) * spacing
            y = cy + bounce
            alpha = int(160 + 95 * (0.5 + 0.5 * math.sin(phase)))
            # glow
            grad = QRadialGradient(QPointF(x, y), dot_r + 5)
            grad.setColorAt(0, QColor(PRO_DOT.red(), PRO_DOT.green(),
                                       PRO_DOT.blue(), alpha // 2))
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
        """Live transcript tail at the bottom of the pill."""
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
        """Per-app profile tag pinned top-right."""
        p.setFont(self._tag_font)
        fm = QFontMetrics(self._tag_font)
        tag = self._profile_tag
        tw, th = fm.horizontalAdvance(tag) + 14, fm.height() + 5
        tx, ty = self.width() - tw - 10, 8
        p.setPen(Qt.NoPen)
        p.setBrush(TAG_BG)
        p.drawRoundedRect(QRectF(tx, ty, tw, th), th / 2, th / 2)
        p.setPen(TAG_TEXT)
        p.drawText(QRectF(tx, ty, tw, th), Qt.AlignCenter, tag)

    def _paint_toast(self, p):
        """Compact toast for confirmations — smaller glass pill."""
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(BODY_BG)
        p.drawRoundedRect(self.rect(), RADIUS, RADIUS)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(RIM_PRO, 2))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), RADIUS, RADIUS)
        remaining = self._toast_until - _time.monotonic()
        alpha = 255 if remaining > 0.35 else int(max(0, remaining / 0.35) * 255)
        p.setFont(self._toast_font)
        p.setPen(QColor(226, 232, 240, alpha))
        p.drawText(self.rect(), Qt.AlignCenter, self._toast_text)


# Back-compat alias.
StatusOverlay = WaveformOverlay
