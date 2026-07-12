"""Headless render of the modernized overlay."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

import overlay
ov = overlay.WaveformOverlay()
out = os.path.join(os.path.dirname(__file__), "..", "build", "overlay_preview")
os.makedirs(out, exist_ok=True)

# recording mode with profile tag
ov._mode = "recording"
ov._preview_on = True
ov.set_profile_tag("terminal · verbatim")
ov.set_preview("the quick brown fox jumps over the lazy dog and then")
ov._apply_size()
ov.resize(ov.width(), ov.height())
# feed fake levels for a lively waveform
import random as _rnd
for _ in range(6):
    ov._smoothed = max(_rnd.random() * 0.8, ov._smoothed * 0.72)
    ov._levels.append(ov._smoothed)
ov._glow_phase = 1.0
ov.repaint()
ov.grab().save(os.path.join(out, "recording.png")); print("wrote recording.png")

# processing mode
ov._mode = "processing"
ov._preview_on = False
ov._apply_size()
ov.resize(ov.width(), ov.height())
ov._phase = 2.0
ov.repaint()
ov.grab().save(os.path.join(out, "processing.png")); print("wrote processing.png")

# toast
ov._mode = "toast"
ov._toast_text = "12 words · Ctrl+Z to undo"
ov._toast_until = time.monotonic() + 2
ov._apply_size()
ov.resize(ov.width(), ov.height())
ov.repaint()
ov.grab().save(os.path.join(out, "toast.png")); print("wrote toast.png")

print("ALL RENDERED OK")
