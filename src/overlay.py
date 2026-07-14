"""Modern recording overlay — acrylic glass pill with premium animations.

Design draws from competitive analysis:
- Wispr Flow: wide lozenge at bottom, frosted-glass with real acrylic blur,
  glow ring animation when recording, waveform as primary visual, live transcript.
- Superwhisper: per-app context tags, state colours, compact when idle.
- 2025-2026 pattern: glassmorphism (translucency + layered glow), pulsing
  borders, smooth animated waveforms, confident sizing, entrance/exit animations.

API unchanged — ui.py calls the same methods (show_recording, show_processing,
hide_overlay, flash_toast, set_profile_tag, set_preview, set_level_source).
"""

import ctypes
import math
import platform
import time as _time
from collections import deque

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QLinearGradient, QFont,
                           QFontMetrics, QRadialGradient)
from PySide6.QtWidgets import QWidget

# ── layout constants (chunkier, more confident) ─────────────────────────
N_BARS = 28
BAR_W = 4
BAR_GAP = 3
BAR_MAX = 40
IDLE_H = 3.0
PAD_X = 28
PAD_Y = 20
LEVEL_GAIN = 6.5
PREVIEW_W = 620
PREVIEW_ROW_H = 24
TOAST_STD_W = 220
RADIUS = 26

# recording dot
DOT_R = 5
DOT_SPACE = 26  # space reserved for recording dot on the left

# ── timing ──────────────────────────────────────────────────────────────
TICK_MS = 33                 # ~30 fps
TOAST_DEFAULT_MS = 1800
ANIM_IN_MS = 200
ANIM_OUT_MS = 150

# ── styling ─────────────────────────────────────────────────────────────
GLASS_BG = QColor(12, 14, 18, 200)
GLASS_EDGE = QColor(255, 255, 255, 22)
GLASS_INNER = QColor(255, 255, 255, 7)

GLOW_OUTER_REC = QColor(224, 82, 82, 60)
GLOW_OUTER_PRO = QColor(77, 163, 255, 55)

# waveform gradient — electric cyan -> blue -> deep indigo
WAVE_TOP = QColor("#64d2ff")
WAVE_MID = QColor("#3d7dff")
WAVE_BOT = QColor("#6366f1")

# processing shimmer (blue tones)
PRO_TOP = QColor("#93c5fd")
PRO_MID = QColor("#4da3ff")
PRO_BOT = QColor("#6366f1")

# text
TEXT_ACTIVE = QColor(226, 232, 240, 245)
TEXT_MUTED = QColor(226, 232, 240, 120)
TAG_BG = QColor(61, 125, 255, 60)
TAG_TEXT = QColor(198, 219, 255, 240)

REC_DOT_COLOR = QColor(224, 82, 82)


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
        self._display = [0.0] * N_BARS          # smoothed per-bar display values
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

        # animation state
        self._opacity = 0.0
        self._anim_dir = 0  # 0=stable, 1=fading in, -1=fading out

        # acrylic blur
        self._acrylic_tried = False
        self._acrylic_enabled = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── acrylic blur ────────────────────────────────────────────────────

    def _enable_acrylic(self):
        """Enable Windows 11 acrylic blur behind the window for real frosted glass."""
        if platform.system() != "Windows":
            return
        try:
            hwnd = int(self.winId())
            # DWMWA_SYSTEMBACKDROP_TYPE = 38 (Windows 11+)
            # DWMSBT_TRANSIENTWINDOW = 3 (Acrylic)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 38,
                ctypes.byref(ctypes.c_int(3)),
                ctypes.sizeof(ctypes.c_int))
            self._acrylic_enabled = True
        except Exception:
            pass

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._acrylic_tried:
            self._enable_acrylic()
            self._acrylic_tried = True

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
        self._anim_dir = 1  # fade in
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
        self._anim_dir = 1  # fade in
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
        # Start fade-out animation instead of instant hide
        self._anim_dir = -1
        if not self._timer.isActive():
            self._timer.start(TICK_MS)

    # ── geometry ────────────────────────────────────────────────────────

    def _apply_size(self):
        if self._mode == "toast":
            fm = QFontMetrics(self._toast_font)
            tw = fm.horizontalAdvance(self._toast_text or "")
            self.resize(max(TOAST_STD_W, tw + 48), self._base_h)
            return
        self.resize(PREVIEW_W, self._total_h if self._preview_on else self._base_h)

    def _place(self):
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            w = self.width()
            target_y = g.bottom() - self.height() - 18
            target_x = g.center().x() - w // 2
            # Slide-up offset during entrance/exit animation
            offset = int((1.0 - self._opacity) * 16)
            self.move(target_x, target_y + offset)

    # ── animation tick ──────────────────────────────────────────────────

    def _tick(self):
        # Advance entrance/exit animation
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

        # Mode-specific updates
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
            # Per-bar smooth decay for liquid feel
            for i in range(N_BARS):
                target = self._levels[i] if i < len(self._levels) else 0.0
                self._display[i] += (target - self._display[i]) * 0.35
            self._dot_phase += 0.08

        self._phase += 0.35       # processing shimmer speed
        self._glow_phase += 0.06  # glow pulse (~3s cycle)
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

        if self._mode == "recording":
            self._paint_glow(p, recording=True)
        elif self._mode == "processing":
            self._paint_glow(p, recording=False)

        self._paint_glass_bg(p)

        if self._mode == "recording":
            self._paint_recording_dot(p)
            self._paint_waveform(p)
        elif self._mode == "processing":
            self._paint_processing_dots(p)

        if self._preview_on and self._mode != "toast":
            self._paint_preview(p)
        if self._profile_tag and self._mode == "recording":
            self._paint_tag(p)
        p.end()

    # ── layered paint helpers ───────────────────────────────────────────

    def _paint_glow(self, p, recording=True):
        """Pulsing outer glow ring — the competitive 'wow' effect."""
        pulse = 0.65 + 0.35 * math.sin(self._glow_phase)
        alpha = int(35 + 25 * pulse)
        expand = 4 + 3 * pulse
        base = GLOW_OUTER_REC if recording else GLOW_OUTER_PRO
        glow = QColor(base.red(), base.green(), base.blue(), alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(QRectF(-expand, -expand,
                                  self.width() + expand * 2,
                                  self.height() + expand * 2),
                          RADIUS + expand, RADIUS + expand)

    def _paint_glass_bg(self, p):
        """Frosted-glass pill background with layered translucency."""
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(GLASS_BG)
        p.drawRoundedRect(self.rect(), RADIUS, RADIUS)
        # edge highlight (thin glass rim)
        rim_alpha = GLASS_EDGE.alpha() if self._mode == "recording" else 10
        p.setPen(QColor(GLASS_EDGE.red(), GLASS_EDGE.green(), GLASS_EDGE.blue(),
                         rim_alpha))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), RADIUS, RADIUS)
        # inner highlight (top half reflection)
        p.setPen(Qt.NoPen)
        p.setBrush(GLASS_INNER)
        p.drawRoundedRect(QRectF(3, 2, w - 6, (h - 2) * 0.45),
                          RADIUS * 0.7, RADIUS * 0.7)

    def _paint_recording_dot(self, p):
        """Pulsing red dot on the left — universal recording indicator."""
        pulse = 0.5 + 0.5 * math.sin(self._dot_phase)
        cx = PAD_X + DOT_R
        cy = self._base_h / 2
        r = DOT_R + 1.0 * pulse
        # glow halo
        glow_r = r + 5 + 2 * pulse
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        grad.setColorAt(0, QColor(224, 82, 82, int(80 + 40 * pulse)))
        grad.setColorAt(1, QColor(224, 82, 82, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)
        # solid dot
        p.setBrush(REC_DOT_COLOR)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_waveform(self, p):
        """Recording waveform — chunky bars with glow, smooth decay, mirrored."""
        cy = self._base_h / 2
        bars_total_w = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        # Center waveform to the right of the recording dot
        x_start = PAD_X + DOT_SPACE
        avail_w = self.width() - PAD_X - x_start
        x = x_start + max(0, (avail_w - bars_total_w) / 2)

        grad = QLinearGradient(0, 0, 0, self._base_h)
        grad.setColorAt(0.0, WAVE_TOP)
        grad.setColorAt(0.55, WAVE_MID)
        grad.setColorAt(1.0, WAVE_BOT)
        for i in range(N_BARS):
            h = max(IDLE_H, self._display[i] * BAR_MAX)
            self._bar(p, x, cy, h, grad, WAVE_MID)
            x += BAR_W + BAR_GAP

    def _paint_processing_dots(self, p):
        """Three bouncing dots — universal 'thinking' indicator."""
        cy = self._base_h / 2
        cx = self.width() / 2
        dot_r = 5
        spacing = 18
        for i in range(3):
            phase = self._phase + i * 0.6
            bounce = math.sin(phase) * 6
            x = cx + (i - 1) * spacing
            y = cy + bounce
            alpha = int(160 + 95 * (0.5 + 0.5 * math.sin(phase)))
            c = PRO_MID
            # glow
            grad = QRadialGradient(QPointF(x, y), dot_r + 4)
            grad.setColorAt(0, QColor(c.red(), c.green(), c.blue(), alpha // 2))
            grad.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), dot_r + 4, dot_r + 4)
            # dot
            p.setBrush(QColor(c.red(), c.green(), c.blue(), alpha))
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
        tw, th = fm.horizontalAdvance(tag) + 12, fm.height() + 4
        tx, ty = self.width() - tw - 8, 6
        p.setPen(Qt.NoPen)
        p.setBrush(TAG_BG)
        p.drawRoundedRect(QRectF(tx, ty, tw, th), th / 2, th / 2)
        p.setPen(TAG_TEXT)
        p.drawText(QRectF(tx, ty, tw, th), Qt.AlignCenter, tag)

    def _paint_toast(self, p):
        """Compact toast for confirmations — smaller glass pill."""
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(GLASS_BG)
        p.drawRoundedRect(self.rect(), RADIUS, RADIUS)
        p.setPen(QColor(GLASS_EDGE))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), RADIUS, RADIUS)
        # fade out in last 0.35s
        remaining = self._toast_until - _time.monotonic()
        alpha = 255 if remaining > 0.35 else int(max(0, remaining / 0.35) * 255)
        p.setFont(self._toast_font)
        p.setPen(QColor(226, 232, 240, alpha))
        p.drawText(self.rect(), Qt.AlignCenter, self._toast_text)

    # ── bar primitive ───────────────────────────────────────────────────

    @staticmethod
    def _bar(p, x, cy, h, brush, glow_color):
        """Draw a single waveform bar with glow — rounded ends, centred on cy."""
        h = max(IDLE_H, h)
        bar_w = BAR_W
        r = bar_w / 2
        # glow behind bar
        p.setBrush(QColor(glow_color.red(), glow_color.green(),
                          glow_color.blue(), 50))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(x - 1, cy - h / 2 - 1, bar_w + 2, h + 2),
                          r + 1, r + 1)
        # bar
        p.setBrush(brush)
        p.drawRoundedRect(QRectF(x, cy - h / 2, bar_w, h), r, r)


# Back-compat alias.
StatusOverlay = WaveformOverlay
