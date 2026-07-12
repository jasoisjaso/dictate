"""Modern recording overlay — a wide glass-morphism pill pinned to the
bottom-centre of the screen. Design draws from real competitive analysis:

- Wispr Flow Bar: wide lozenge at bottom, frosted-glass look, glow ring
  animation when recording, waveform as primary visual, live transcript.
- Superwhisper: per-app context tags, state colours, compact when idle.
- 2025-2026 pattern: glassmorphism (translucency + layered glow), pulsing
  borders, smooth animated waveforms, confident sizing.

API unchanged — ui.py calls the same methods (show_recording, show_processing,
hide_overlay, flash_toast, set_profile_tag, set_preview, set_level_source).
"""

import math
import time as _time
from collections import deque

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (QColor, QPainter, QLinearGradient, QFont,
                           QFontMetrics, QRadialGradient)
from PySide6.QtWidgets import QWidget

# ── layout constants (bigger, more confident) ───────────────────────────
N_BARS = 48
BAR_W = 2
BAR_GAP = 2
BAR_MAX = 38                 # tallest bar in px (was 26)
IDLE_H = 2.0                 # idle bar height
PAD_X = 24
PAD_Y = 18                   # vertical padding (was 14)
LEVEL_GAIN = 6.5
PREVIEW_W = 610              # wider recording bar (was 520)
PREVIEW_ROW_H = 22
TOAST_STD_W = 200
RADIUS = 24                  # fully-rounded pill ends

# ── timing ──────────────────────────────────────────────────────────────
TICK_MS = 33                 # ~30 fps
TOAST_DEFAULT_MS = 1600

# ── styling ─────────────────────────────────────────────────────────────
# glassmorphism layers
GLASS_BG = QColor(12, 14, 18, 190)       # translucent dark base
GLASS_EDGE = QColor(255, 255, 255, 18)   # thin glass edge
GLASS_INNER = QColor(255, 255, 255, 6)   # subtle inner highlight

# recording glow palette
GLOW_OUTER_REC = QColor(224, 82, 82, 55)     # red outer glow when recording
GLOW_INNER_REC = QColor(200, 60, 60, 30)
GLOW_OUTER_PRO = QColor(77, 163, 255, 55)    # blue outer glow when processing
GLOW_INNER_PRO = QColor(61, 125, 255, 30)

# waveform gradient — electric cyan → blue → deep indigo
WAVE_TOP = QColor("#64d2ff")       # cyan
WAVE_MID = QColor("#3d7dff")       # electric blue
WAVE_BOT = QColor("#6366f1")       # indigo

# processing shimmer (blue tones)
PRO_TOP = QColor("#93c5fd")
PRO_MID = QColor("#4da3ff")
PRO_BOT = QColor("#6366f1")

# text
TEXT_ACTIVE = QColor(226, 232, 240, 245)
TEXT_MUTED = QColor(226, 232, 240, 120)
TAG_BG = QColor(61, 125, 255, 60)
TAG_TEXT = QColor(198, 219, 255, 240)


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

        self._base_h = BAR_MAX + PAD_Y * 2            # recording bar height
        self._total_h = self._base_h + PREVIEW_ROW_H   # with preview row
        self._glow_phase = 0.0                          # cycle for outer glow

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── public API (unchanged) ──────────────────────────────────────────

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
        self._smoothed = 0.0
        self._preview_on = preview
        self._preview_text = ""
        self._glow_phase = 0.0
        self._apply_size()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(TICK_MS)

    def show_processing(self):
        self._mode = "processing"
        self._phase = 0.0
        self.update()

    def hide_overlay(self):
        self._timer.stop()
        self._mode = "hidden"
        self._preview_text = ""
        self._profile_tag = ""
        self.hide()

    # ── geometry ────────────────────────────────────────────────────────

    def _apply_size(self):
        if self._mode == "toast":
            fm = QFontMetrics(self._toast_font)
            tw = fm.horizontalAdvance(self._toast_text or "")
            self.resize(max(TOAST_STD_W, tw + 40), self._base_h)
            return
        self.resize(PREVIEW_W, self._total_h if self._preview_on else self._base_h)

    def _place(self):
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            w = self.width()
            self.move(g.center().x() - w // 2, g.bottom() - self.height() - 18)

    # ── animation tick ──────────────────────────────────────────────────

    def _tick(self):
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

        self._phase += 0.35       # processing shimmer speed
        self._glow_phase += 0.06  # glow pulse (~3s cycle)
        self.update()

    # ── paint ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._mode == "toast":
            self._paint_toast(p)
            p.end()
            return

        if self._mode == "recording":
            self._paint_glow(p)
        self._paint_glass_bg(p)
        self._paint_waveform(p)
        if self._preview_on and self._mode != "toast":
            self._paint_preview(p)
        if self._profile_tag and self._mode == "recording":
            self._paint_tag(p)
        p.end()

    # ── layered paint helpers ───────────────────────────────────────────

    def _paint_glow(self, p):
        """Pulsing outer glow ring — the competitive 'wow' effect. Uses a
        layered approach: a larger translucent rect with the glow color,
        then the glass pill on top, creating a halo."""
        pulse = 0.65 + 0.35 * math.sin(self._glow_phase)
        alpha = int(35 + 25 * pulse)
        expand = 4 + 3 * pulse

        glow = QColor(GLOW_OUTER_REC.red(), GLOW_OUTER_REC.green(),
                      GLOW_OUTER_REC.blue(), alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(QRectF(-expand, -expand,
                                  self.width() + expand * 2,
                                  self.height() + expand * 2),
                          RADIUS + expand, RADIUS + expand)

    def _paint_glass_bg(self, p):
        """Frosted-glass pill background with layered translucency."""
        w, h = self.width(), self.height()
        # base glass
        p.setPen(Qt.NoPen)
        p.setBrush(GLASS_BG)
        p.drawRoundedRect(self.rect(), RADIUS, RADIUS)
        # edge highlight (thin glass rim)
        rim = QColor(GLASS_EDGE.red(), GLASS_EDGE.green(), GLASS_EDGE.blue(),
                     GLASS_EDGE.alpha() if self._mode == "recording" else 10)
        p.setPen(QColor(rim))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), RADIUS, RADIUS)
        # inner highlight (top half reflection)
        p.setPen(Qt.NoPen)
        p.setBrush(GLASS_INNER)
        p.drawRoundedRect(QRectF(3, 2, w - 6, (h - 2) * 0.45),
                          RADIUS * 0.7, RADIUS * 0.7)

    def _paint_waveform(self, p):
        """Centre-aligned waveform — taller, more bars, gradient. Mirrored
        (bars grow both up AND down from centre) for a premium equalizer look."""
        cy = self._base_h / 2
        bars_total_w = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
        x = (self.width() - bars_total_w) / 2

        if self._mode == "recording":
            grad = QLinearGradient(0, 0, 0, self._base_h)
            grad.setColorAt(0.0, WAVE_TOP)
            grad.setColorAt(0.55, WAVE_MID)
            grad.setColorAt(1.0, WAVE_BOT)
            for lv in self._levels:
                h = max(IDLE_H, lv * BAR_MAX)
                self._bar(p, x, cy, h, grad)
                x += BAR_W + BAR_GAP
        else:
            grad = QLinearGradient(0, 0, 0, self._base_h)
            grad.setColorAt(0.0, PRO_TOP)
            grad.setColorAt(0.5, PRO_MID)
            grad.setColorAt(1.0, PRO_BOT)
            for i in range(N_BARS):
                s = math.sin(self._phase + i * 0.45)
                h = IDLE_H + (0.28 + 0.72 * abs(s)) * (BAR_MAX * 0.58)
                self._bar(p, x, cy, h, grad)
                x += BAR_W + BAR_GAP

    def _paint_preview(self, p):
        """Live transcript tail at the bottom of the pill."""
        p.setFont(self._font)
        fm = QFontMetrics(self._font)
        text = self._preview_text or "listening…"
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
    def _bar(p, x, cy, h, brush):
        """Draw a single waveform bar — mirrored (above AND below centre)."""
        h = max(IDLE_H, h)
        p.setBrush(brush)
        bar_w = BAR_W
        r = bar_w / 2
        # top half
        p.drawRoundedRect(QRectF(x, cy - h / 2, bar_w, h / 2), r, r)
        # bottom half (mirror)
        p.drawRoundedRect(QRectF(x, cy, bar_w, h / 2), r, r)


# Back-compat alias.
StatusOverlay = WaveformOverlay
