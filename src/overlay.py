"""Recording overlay — two visualizer styles, selectable in settings.

Style "equalizer" (default): bare grey bars growing from a bottom baseline.
  Clean, minimal, professional.

Style "blob": a morphing colour-shifting orb that deforms with pitch and
  bass, changes colour from green->yellow->orange->red as you get louder,
  and pulses with a soft glow aura. Impossible to miss.

Both styles share the same API (show_recording, show_processing,
hide_overlay, flash_toast, set_profile_tag, set_preview, set_level_source).

The overlay takes an optional `audio_source` callback that returns a
np.ndarray of recent audio — needed for the blob visualizer's FFT analysis.
When not provided (or None), the blob falls back to using the level_source
RMS value for a simpler pulse.
"""

import math
import platform
import time as _time
from collections import deque

import numpy as np
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QLinearGradient, QRadialGradient,
                           QFont, QFontMetrics, QBrush, QPainterPath)
from PySide6.QtWidgets import QWidget

# ── shared layout ───────────────────────────────────────────────────────
TOAST_STD_W = 260
TICK_MS = 33
TOAST_DEFAULT_MS = 1800
ANIM_IN_MS = 200
ANIM_OUT_MS = 130

TEXT_ACTIVE = QColor(220, 226, 234, 230)
TEXT_MUTED = QColor(148, 163, 184, 120)
TAG_TEXT = QColor(186, 230, 253, 200)
TOAST_TEXT = QColor(220, 226, 234, 230)
REC_DOT = QColor(239, 68, 68)
PRO_DOT = QColor(150, 160, 175)

# ── equalizer constants ─────────────────────────────────────────────────
EQ_N_BARS = 28
EQ_BAR_W = 7
EQ_BAR_GAP = 5
EQ_BAR_MAX = 52
EQ_BAR_MIN = 5
EQ_PAD_X = 34
EQ_PAD_Y = 18
EQ_LEVEL_GAIN = 7.0
EQ_PREVIEW_W = 680
EQ_PREVIEW_ROW_H = 24
EQ_DOT_R = 6
EQ_DOT_SPACE = 36

EQ_BAR_GRAD = [QColor(180, 188, 200), QColor(140, 150, 165), QColor(100, 110, 125)]
EQ_BAR_GLOW = QColor(140, 150, 165, 40)

# ── blob constants ──────────────────────────────────────────────────────
BLOB_BASE_R = 70        # base radius in px
BLOB_POINTS = 128       # polygon vertices for smooth shape
BLOB_PREVIEW_W = 700
BLOB_PREVIEW_ROW_H = 24
BLOB_PAD_Y = 16


class WaveformOverlay(QWidget):
    """Overlay that shows either an equalizer or a morphing blob.

    style: "equalizer" or "blob" (set by ui.py from config)
    """

    def __init__(self, style: str = "equalizer"):
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

        self._style = style
        self._levels = deque([0.0] * EQ_N_BARS, maxlen=EQ_N_BARS)
        self._display = [0.0] * EQ_N_BARS
        self._mode = "hidden"
        self._phase = 0.0
        self._level_source = None
        self._audio_source = None   # callback -> np.ndarray (for blob FFT)
        self._smoothed = 0.0
        self._preview_on = False
        self._preview_text = ""
        self._profile_tag = ""
        self._toast_text = ""
        self._toast_until = 0.0
        self._font = QFont("Segoe UI", 10)
        self._tag_font = QFont("Segoe UI", 7, QFont.Medium)
        self._toast_font = QFont("Segoe UI", 10, QFont.Medium)

        # equalizer sizing
        self._eq_base_h = EQ_BAR_MAX + EQ_PAD_Y * 2
        self._eq_total_h = self._eq_base_h + EQ_PREVIEW_ROW_H

        # blob sizing
        self._blob_base_h = (BLOB_BASE_R + BLOB_PAD_Y) * 2
        self._blob_total_h = self._blob_base_h + BLOB_PREVIEW_ROW_H

        # blob smoothing state
        self._bass_sm = 0.0
        self._mid_sm = 0.0
        self._treble_sm = 0.0
        self._rms_sm = 0.0
        self._pitch_sm = 0.0
        self._blob_phase = 0.0

        self._glow_phase = 0.0
        self._dot_phase = 0.0
        self._dpi_scale = 1.0

        self._opacity = 0.0
        self._anim_dir = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    @property
    def _base_h(self):
        return self._blob_base_h if self._style == "blob" else self._eq_base_h

    @property
    def _total_h(self):
        return self._blob_total_h if self._style == "blob" else self._eq_total_h

    def set_style(self, style: str):
        self._style = style

    def showEvent(self, ev):
        super().showEvent(ev)
        screen = self.screen()
        if screen:
            self._dpi_scale = max(1.0, screen.devicePixelRatio())

    # ── public API ──────────────────────────────────────────────────────

    def set_level_source(self, fn):
        self._level_source = fn

    def set_audio_source(self, fn):
        """Set a callback that returns recent audio as np.ndarray for FFT.
        Only used by the blob visualizer."""
        self._audio_source = fn

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
        self._levels = deque([0.0] * EQ_N_BARS, maxlen=EQ_N_BARS)
        self._display = [0.0] * EQ_N_BARS
        self._smoothed = 0.0
        self._bass_sm = self._mid_sm = self._treble_sm = self._rms_sm = self._pitch_sm = 0.0
        self._preview_on = preview
        self._preview_text = ""
        self._glow_phase = 0.0
        self._dot_phase = 0.0
        self._blob_phase = 0.0
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
        if self._style == "blob":
            w = int(BLOB_PREVIEW_W * s)
        else:
            w = int(EQ_PREVIEW_W * s)
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
            if self._style == "equalizer":
                raw = self._level_source() if self._level_source else 0.0
                norm = min(1.0, raw * EQ_LEVEL_GAIN)
                self._smoothed = max(norm, self._smoothed * 0.72)
                self._levels.append(self._smoothed)
                for i in range(EQ_N_BARS):
                    target = self._levels[i] if i < len(self._levels) else 0.0
                    self._display[i] += (target - self._display[i]) * 0.4
            elif self._style == "blob":
                self._update_blob_analysis()
            self._dot_phase += 0.09

        self._phase += 0.35
        self._glow_phase += 0.05
        self._blob_phase += 0.04
        self.update()

    def _update_blob_analysis(self):
        """Get audio buffer, run FFT, smooth the results."""
        audio = None
        if self._audio_source:
            try:
                audio = self._audio_source()
            except Exception:
                pass
        if audio is not None and audio.size > 256:
            try:
                from . import audio_analysis
            except ImportError:
                import audio_analysis
            bass, mid, treble, pitch, rms = audio_analysis.analyze(audio)
        else:
            # Fallback: use RMS level only
            raw = self._level_source() if self._level_source else 0.0
            rms = min(1.0, raw * EQ_LEVEL_GAIN)
            bass = mid = treble = rms * 0.5
            pitch = 0.0

        # Exponential smoothing for stable visuals
        a = 0.25
        self._bass_sm += (bass - self._bass_sm) * a
        self._mid_sm += (mid - self._mid_sm) * a
        self._treble_sm += (treble - self._treble_sm) * a
        self._rms_sm += (rms - self._rms_sm) * a
        self._pitch_sm += (pitch - self._pitch_sm) * 0.1

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
            if self._style == "blob":
                self._paint_blob(p)
            else:
                self._paint_rec_dot(p)
                self._paint_eq_bars(p)
        elif processing:
            self._paint_processing_dots(p)

        if self._preview_on and self._mode != "toast":
            self._paint_preview(p)
        if self._profile_tag and recording:
            self._paint_tag(p)
        p.end()

    # ── equalizer painting ──────────────────────────────────────────────

    def _paint_rec_dot(self, p):
        pulse = 0.5 + 0.5 * math.sin(self._dot_phase)
        cx = EQ_PAD_X + EQ_DOT_R
        cy = self._eq_base_h / 2
        r = EQ_DOT_R + pulse * 0.8
        glow_r = r + 7 + 2 * pulse
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        grad.setColorAt(0, QColor(239, 68, 68, int(55 + 35 * pulse)))
        grad.setColorAt(1, QColor(239, 68, 68, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)
        p.setBrush(REC_DOT)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_eq_bars(self, p):
        baseline = self._eq_base_h - EQ_PAD_Y
        x_start = EQ_PAD_X + EQ_DOT_SPACE
        avail_w = self.width() - EQ_PAD_X - x_start
        bars_total_w = EQ_N_BARS * EQ_BAR_W + (EQ_N_BARS - 1) * EQ_BAR_GAP
        x = x_start + max(0, (avail_w - bars_total_w) / 2)

        grad = QLinearGradient(0, baseline - EQ_BAR_MAX, 0, baseline)
        grad.setColorAt(0.0, EQ_BAR_GRAD[0])
        grad.setColorAt(0.5, EQ_BAR_GRAD[1])
        grad.setColorAt(1.0, EQ_BAR_GRAD[2])

        for i in range(EQ_N_BARS):
            val = self._display[i]
            h = max(EQ_BAR_MIN, val * EQ_BAR_MAX)
            bx, by = x, baseline - h
            p.setBrush(EQ_BAR_GLOW)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(bx - 2, by - 2, EQ_BAR_W + 4, h + 4),
                              (EQ_BAR_W + 4) / 2, (EQ_BAR_W + 4) / 2)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bx, by, EQ_BAR_W, h), EQ_BAR_W / 2, EQ_BAR_W / 2)
            x += EQ_BAR_W + EQ_BAR_GAP

    # ── blob painting ───────────────────────────────────────────────────

    def _paint_blob(self, p):
        """Morphing colour-shifting orb that deforms with pitch and volume.

        - Colour: green -> yellow -> orange -> red as volume increases
        - Shape: bass stretches it vertically, mid adds 3-lobe bumps,
          treble adds fine ripples, pitch shifts the deformation pattern
        - Outer glow aura pulses with bass
        """
        cx = self.width() / 2
        cy = self._blob_base_h / 2
        t = self._blob_phase * 10  # animation time multiplier

        bass = self._bass_sm
        mid = self._mid_sm
        treble = self._treble_sm
        rms = self._rms_sm
        pitch = self._pitch_sm

        # ── colour: map RMS to hue (green 120° -> red 0°) ────────────────
        # At silence: cool teal/blue. Speaking: green -> yellow -> orange -> red.
        if rms < 0.05:
            hue = 190  # teal when quiet
        else:
            hue = int(120 - rms * 120)  # green(120) -> red(0)
            hue = max(0, hue)
        sat = int(180 + 75 * rms)
        val = int(200 + 55 * rms)
        main_color = QColor.fromHsv(hue, min(255, sat), min(255, val))

        # ── outer glow aura ──────────────────────────────────────────────
        aura_r = BLOB_BASE_R + 30 + bass * 25 + math.sin(t * 2) * 5
        aura_grad = QRadialGradient(QPointF(cx, cy), aura_r)
        ac = QColor(main_color)
        ac.setAlpha(int(50 + 40 * bass))
        aura_grad.setColorAt(0, ac)
        ac2 = QColor(main_color)
        ac2.setAlpha(0)
        aura_grad.setColorAt(1, ac2)
        p.setBrush(aura_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), aura_r, aura_r)

        # ── blob shape: polar deformation ────────────────────────────────
        points = []
        base_r = BLOB_BASE_R + rms * 20
        # Pitch influences the number of lobes (higher pitch = more lobes)
        pitch_factor = max(0, min(1.0, (pitch - 80) / 400.0)) if pitch > 0 else 0.3

        for i in range(BLOB_POINTS):
            angle = 2 * math.pi * i / BLOB_POINTS
            r = base_r
            # Bass: vertical stretch + slow breathing
            r *= 1.0 + bass * 0.25
            r += bass * 15 * math.sin(angle * 2 + t * 1.5)
            # Mid: 3-lobe bumps (vowels)
            lobe_count = 3 + int(pitch_factor * 3)
            r += mid * 20 * math.sin(angle * lobe_count + t * 2.0)
            # Treble: fine ripples (consonants)
            r += treble * 8 * math.sin(angle * 9 + t * 5.0)
            r += treble * 5 * math.cos(angle * 14 + t * 7.0)
            # Always-on subtle organic wobble so it's alive even when quiet
            r += 3 * math.sin(angle * 5 + t * 0.8)
            r = max(10, r)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append((px, py))

        # Build smooth path
        path = QPainterPath()
        if points:
            path.moveTo(points[0][0], points[0][1])
            for px, py in points[1:]:
                path.lineTo(px, py)
            path.closeSubpath()

        # ── fill with radial gradient ────────────────────────────────────
        inner = QColor(main_color)
        inner = inner.lighter(140)
        outer = QColor(main_color)
        outer = outer.darker(200)
        fill_grad = QRadialGradient(QPointF(cx, cy - 10), base_r * 1.3)
        fill_grad.setColorAt(0.0, inner)
        fill_grad.setColorAt(0.5, main_color)
        fill_grad.setColorAt(1.0, outer)
        p.setBrush(fill_grad)
        p.setPen(Qt.NoPen)
        p.drawPath(path)

        # ── inner highlight (specular sheen) ─────────────────────────────
        sheen_r = base_r * 0.35
        sheen_grad = QRadialGradient(
            QPointF(cx - base_r * 0.25, cy - base_r * 0.3), sheen_r)
        sheen_grad.setColorAt(0, QColor(255, 255, 255, int(60 + 40 * rms)))
        sheen_grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(sheen_grad)
        p.drawEllipse(QPointF(cx - base_r * 0.25, cy - base_r * 0.3),
                      sheen_r, sheen_r)

    # ── processing dots ─────────────────────────────────────────────────

    def _paint_processing_dots(self, p):
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
            grad = QRadialGradient(QPointF(x, y), dot_r + 5)
            grad.setColorAt(0, QColor(PRO_DOT.red(), PRO_DOT.green(),
                                       PRO_DOT.blue(), alpha // 3))
            grad.setColorAt(1, QColor(PRO_DOT.red(), PRO_DOT.green(),
                                       PRO_DOT.blue(), 0))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), dot_r + 5, dot_r + 5)
            p.setBrush(QColor(PRO_DOT.red(), PRO_DOT.green(),
                              PRO_DOT.blue(), alpha))
            p.drawEllipse(QPointF(x, y), dot_r, dot_r)

    # ── preview / tag / toast ───────────────────────────────────────────

    def _paint_preview(self, p):
        p.setFont(self._font)
        fm = QFontMetrics(self._font)
        text = self._preview_text or "listening..."
        elided = fm.elidedText(text, Qt.ElideLeft, self.width() - 40)
        p.setPen(TEXT_ACTIVE if self._preview_text else TEXT_MUTED)
        p.drawText(
            QRectF(20, self._base_h - 2, self.width() - 40, 24),
            Qt.AlignVCenter | Qt.AlignLeft, elided)

    def _paint_tag(self, p):
        p.setFont(self._tag_font)
        p.setPen(TAG_TEXT)
        fm = QFontMetrics(self._tag_font)
        tag = self._profile_tag
        tw = fm.horizontalAdvance(tag) + 4
        p.drawText(QRectF(self.width() - tw - 12, 8, tw, fm.height() + 2),
                   Qt.AlignVCenter | Qt.AlignRight, tag)

    def _paint_toast(self, p):
        remaining = self._toast_until - _time.monotonic()
        alpha = 255 if remaining > 0.35 else int(max(0, remaining / 0.35) * 255)
        p.setFont(self._toast_font)
        p.setPen(QColor(TOAST_TEXT.red(), TOAST_TEXT.green(),
                        TOAST_TEXT.blue(), alpha))
        p.drawText(self.rect(), Qt.AlignCenter, self._toast_text)


# Back-compat alias.
StatusOverlay = WaveformOverlay
