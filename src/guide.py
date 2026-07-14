"""Interactive 'How to use' guide — a modern, paginated walkthrough with
rendered illustrations (no external image files, so it works in the frozen
exe and scales crisply on any DPI).

Each page has a title, a short body, and a small painted diagram that shows the
feature in action (the recording pill, the tray colours, a voice-command demo,
per-app profiles, the personal dictionary). Reached from tray -> How to use…
and shown once on first run.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QColor, QFont, QPainter, QPixmap, QLinearGradient,
                           QFontMetrics)
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

# palette (matches the overlay pill)
BG = "#0f1116"
CARD = "#171a20"
ACCENT = "#3d7dff"
ACCENT_LT = "#7cc4ff"
GREEN = "#46c07a"
RED = "#e05252"
BLUE = "#4da3ff"
TEXT = "#e2e8f0"
MUTED = "#8a939b"


class _Illustration(QWidget):
    """Paints one of a handful of named diagrams."""

    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.setMinimumHeight(190)
        self.setFixedHeight(190)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # card background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(CARD))
        p.drawRoundedRect(QRectF(0, 0, w, h), 14, 14)
        getattr(self, f"_draw_{self.kind}", self._draw_blank)(p, w, h)
        p.end()

    def _draw_blank(self, p, w, h):
        pass

    # ---- the recording pill with a live waveform -----------------------
    def _draw_pill(self, p, w, h):
        pw, ph = 230, 46
        x, y = (w - pw) / 2, (h - ph) / 2
        p.setBrush(QColor(17, 19, 22, 236))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(x, y, pw, ph), ph / 2, ph / 2)
        grad = QLinearGradient(0, y, 0, y + ph)
        grad.setColorAt(0.0, QColor(ACCENT_LT))
        grad.setColorAt(1.0, QColor(ACCENT))
        p.setBrush(grad)
        heights = [6, 12, 20, 28, 22, 14, 26, 34, 24, 12, 18, 28, 16, 8, 14,
                   22, 30, 18, 10, 20]
        bx = x + 26
        for hh in heights:
            p.drawRoundedRect(QRectF(bx, y + ph / 2 - hh / 2, 3, hh), 1.5, 1.5)
            bx += 6
        self._caption(p, w, h, "The pill shows a live waveform while you talk")

    # ---- tray icon colour states --------------------------------------
    def _draw_states(self, p, w, h):
        labels = [(GREEN, "Ready"), (RED, "Recording"), (BLUE, "Transcribing")]
        gap = w / 3
        for i, (col, lab) in enumerate(labels):
            cx = gap * i + gap / 2
            cy = h / 2 - 12
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(cx - 20, cy - 20, 40, 40))
            # little mic glyph
            p.setBrush(QColor("#ffffff"))
            p.drawRoundedRect(QRectF(cx - 4, cy - 12, 8, 15, ), 4, 4)
            p.drawRect(QRectF(cx - 1, cy + 3, 2, 6))
            p.setPen(QColor(TEXT))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(cx - gap / 2, cy + 26, gap, 20),
                       Qt.AlignCenter, lab)
        self._caption(p, w, h, "Tray icon colour tells you the state at a glance")

    # ---- voice command before/after -----------------------------------
    def _draw_command(self, p, w, h):
        p.setFont(QFont("Consolas", 11))
        # before
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(24, 34, w - 48, 24), Qt.AlignLeft,
                   "the quick brown fox")
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 9, italic=True))
        p.drawText(QRectF(24, 66, w - 48, 20), Qt.AlignLeft,
                   'you say:  "delete last two words"')
        # arrow
        p.setPen(QColor(ACCENT))
        p.setFont(QFont("Segoe UI", 14))
        p.drawText(QRectF(24, 92, w - 48, 24), Qt.AlignLeft, "↓")
        # after
        p.setPen(QColor(GREEN))
        p.setFont(QFont("Consolas", 11))
        p.drawText(QRectF(24, 118, w - 48, 24), Qt.AlignLeft, "the quick")
        self._caption(p, w, h, "Fix mistakes by voice — no keyboard needed")

    # ---- dictation modes ------------------------------------------------
    def _draw_modes(self, p, w, h):
        modes = [("Auto", "detects app", ACCENT_LT),
                 ("Prose", "full cleanup", GREEN),
                 ("Code", "verbatim", "#e0b252"),
                 ("Email", "professional", BLUE)]
        y = 36
        for name, desc, col in modes:
            p.setBrush(QColor(30, 34, 42))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(24, y, w - 48, 30), 8, 8)
            # mode tag
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(34, y + 5, 56, 20), 10, 10)
            p.setPen(QColor("#0f1116"))
            p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            p.drawText(QRectF(34, y + 5, 56, 20), Qt.AlignCenter, name)
            # description
            p.setPen(QColor(TEXT))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(100, y, w - 120, 30),
                       Qt.AlignVCenter | Qt.AlignLeft, desc)
            y += 36
        self._caption(p, w, h, "Press F7 to cycle modes — Auto -> Prose -> Code -> Email")

    # ---- per-app profiles ---------------------------------------------
    def _draw_profiles(self, p, w, h):
        rows = [("Terminal", "verbatim", "#e0b252"),
                ("Email", "professional", ACCENT_LT),
                ("Chat", "casual", GREEN)]
        y = 28
        for app, mode, col in rows:
            p.setBrush(QColor(30, 34, 42))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(24, y, w - 48, 34), 8, 8)
            p.setPen(QColor(TEXT))
            p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            p.drawText(QRectF(38, y, 160, 34), Qt.AlignVCenter | Qt.AlignLeft, app)
            # tag
            p.setFont(QFont("Segoe UI", 8))
            fm = QFontMetrics(p.font())
            tw = fm.horizontalAdvance(mode) + 16
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(w - 48 - tw - 2, y + 7, tw, 20), 10, 10)
            p.setPen(QColor("#0f1116"))
            p.drawText(QRectF(w - 48 - tw - 2, y + 7, tw, 20), Qt.AlignCenter, mode)
            y += 42
        self._caption(p, w, h, "Dictate knows which app you're in and adapts")

    # ---- dictionary ----------------------------------------------------
    def _draw_dictionary(self, p, w, h):
        pairs = [('"woolies"', "Woolworths"), ('"hello acrylic"', "Hello Acrylic")]
        y = 44
        p.setFont(QFont("Segoe UI", 11))
        for said, typed in pairs:
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(24, y, 180, 26), Qt.AlignLeft | Qt.AlignVCenter, said)
            p.setPen(QColor(ACCENT))
            p.drawText(QRectF(180, y, 40, 26), Qt.AlignCenter, "→")
            p.setPen(QColor(GREEN))
            p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
            p.drawText(QRectF(224, y, w - 240, 26),
                       Qt.AlignLeft | Qt.AlignVCenter, typed)
            p.setFont(QFont("Segoe UI", 11))
            y += 40
        self._caption(p, w, h, "Teach it names & jargon in Settings → My words")

    def _caption(self, p, w, h, text):
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(12, h - 26, w - 24, 20), Qt.AlignCenter, text)


class GuideDialog(QDialog):
    def __init__(self, trigger_hint: str = "Hold Right Ctrl and talk"):
        super().__init__()
        self.setWindowTitle("Dictate — How to use")
        self.setMinimumSize(560, 470)
        self.setStyleSheet(
            f"QDialog{{background:{BG};}} QLabel{{color:{TEXT};}}"
            f"QPushButton{{background:{CARD};color:{TEXT};border:1px solid #2a2f38;"
            f"border-radius:8px;padding:7px 16px;}}"
            f"QPushButton:hover{{border-color:{ACCENT};}}"
            f"QPushButton:disabled{{color:{MUTED};}}")

        self.pages = self._build_pages(trigger_hint)
        self.idx = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 18)
        root.setSpacing(14)

        self.illus = _Illustration(self.pages[0]["kind"])
        root.addWidget(self.illus)

        self.title = QLabel()
        self.title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        root.addWidget(self.title)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setFont(QFont("Segoe UI", 10))
        self.body.setStyleSheet(f"color:{TEXT};")
        self.body.setMinimumHeight(96)
        self.body.setAlignment(Qt.AlignTop)
        root.addWidget(self.body)

        root.addStretch(1)

        # dots + nav
        nav = QHBoxLayout()
        self.dots = QLabel()
        self.dots.setFont(QFont("Segoe UI", 14))
        nav.addWidget(self.dots)
        nav.addStretch(1)
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self._back)
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self._next)
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        root.addLayout(nav)

        self._render()

    def _build_pages(self, hint):
        return [
            {"kind": "pill", "title": "Talk instead of type",
             "body": f"<b>{hint}.</b> Let go when you're done and your words "
                     "appear right where your cursor is — in any app: email, "
                     "Word, chat, your browser, a code editor.<br><br>"
                     "A small pill sits at the bottom of the screen showing a "
                     "live waveform so you know it's hearing you."},
            {"kind": "states", "title": "Know what it's doing",
             "body": "The tray icon changes colour so you're never guessing:"
                     "<br><br>"
                     "&nbsp;&nbsp;🟢 <b>Green</b> — ready and listening for your key<br>"
                     "&nbsp;&nbsp;🔴 <b>Red</b> — recording your voice right now<br>"
                     "&nbsp;&nbsp;🔵 <b>Blue</b> — thinking (turning speech into text)"},
            {"kind": "command", "title": "Fix it by voice",
             "body": "You don't need the keyboard to correct things:<br><br>"
                     "&nbsp;&nbsp;• <b>\"scratch that\"</b> — delete the whole last bit<br>"
                     "&nbsp;&nbsp;• <b>\"delete last word\"</b> (or \"…last three words\")<br>"
                     "&nbsp;&nbsp;• <b>\"capitalize that\"</b> / <b>\"all caps that\"</b> / "
                     "<b>\"lowercase that\"</b><br><br>"
                     "Say punctuation too: \"period\", \"comma\", \"question mark\", "
                     "\"new line\", \"new paragraph\", \"bullet point\"."},
            {"kind": "modes", "title": "Switch modes on the fly",
             "body": f"Press <b>F7</b> to cycle between modes:<br><br>"
                     "&nbsp;&nbsp;• <b>Auto</b> — detects the app (terminal = verbatim, chat = casual)<br>"
                     "&nbsp;&nbsp;• <b>Prose</b> — full cleanup, sentence casing (default)<br>"
                     "&nbsp;&nbsp;• <b>Code</b> — verbatim, no casing, no cleanup<br>"
                     "&nbsp;&nbsp;• <b>Email</b> — professional tone<br><br>"
                     "The active mode shows in the pill and the tray menu."},
            {"kind": "profiles", "title": "It adapts to each app",
             "body": "In <b>Auto</b> mode, Dictate notices which app is in front "
                     "and changes how it writes — automatically:<br><br>"
                     "&nbsp;&nbsp;• <b>Terminals / editors</b> → verbatim, no auto-casing "
                     "(so a command isn't mangled)<br>"
                     "&nbsp;&nbsp;• <b>Email</b> → professional tone<br>"
                     "&nbsp;&nbsp;• <b>Chat</b> → casual<br><br>"
                     "While recording, the pill shows the active profile so you "
                     "can see it working."},
            {"kind": "dictionary", "title": "Teach it your words",
             "body": "Names, brands and jargon it wouldn't know? Add them in "
                     "<b>Settings → My words</b> and Dictate will both spell them "
                     "right and expand shorthand as you speak.<br><br>"
                     "Add your own filler words to strip in "
                     "<b>Settings → Extra filler words</b> (e.g. \"like\", "
                     "\"you know\").<br><br>"
                     "You can also set up <b>voice macros</b> in the config file — "
                     "say \"insert my email\" and it types your full address."},
            {"kind": "blank", "title": "You're set 🎉",
             "body": "That's everything. A few tips:<br><br>"
                     "&nbsp;&nbsp;• Landed in the wrong window? "
                     f"Press <b>F8</b> to copy the last dictation, or open <b>History…</b><br>"
                     "&nbsp;&nbsp;• Change your key, mic, model or language in "
                     "<b>Settings…</b><br>"
                     "&nbsp;&nbsp;• Everything runs on your PC — your voice never "
                     "leaves the machine.<br><br>"
                     "Re-open this any time from the tray menu → <b>How to use…</b>"},
        ]

    def _render(self):
        pg = self.pages[self.idx]
        self.illus.kind = pg["kind"]
        self.illus.update()
        self.title.setText(pg["title"])
        self.body.setText(pg["body"])
        self.dots.setText("  ".join(
            "●" if i == self.idx else "○" for i in range(len(self.pages))))
        self.dots.setStyleSheet(f"color:{ACCENT};")
        self.btn_back.setEnabled(self.idx > 0)
        self.btn_next.setText("Done" if self.idx == len(self.pages) - 1 else "Next")

    def _next(self):
        if self.idx == len(self.pages) - 1:
            self.accept()
            return
        self.idx += 1
        self._render()

    def _back(self):
        if self.idx > 0:
            self.idx -= 1
            self._render()
