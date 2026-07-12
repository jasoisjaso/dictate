"""Headless render check: paints every guide page + the overlay toast and
profile tag to PNGs. Proves the Qt paint code runs without exceptions and
lets us eyeball the visuals. Run with QT_QPA_PLATFORM=offscreen."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QSize  # noqa: E402

app = QApplication(sys.argv)

outdir = os.path.join(os.path.dirname(__file__), "..", "build", "guide_preview")
os.makedirs(outdir, exist_ok=True)

import guide  # noqa: E402

# render each guide page
dlg = guide.GuideDialog(trigger_hint="Hold Right Ctrl and talk")
dlg.resize(560, 470)
for i in range(len(dlg.pages)):
    dlg.idx = i
    dlg._render()
    dlg.repaint()
    pm = dlg.grab()
    path = os.path.join(outdir, f"guide_{i}_{dlg.pages[i]['kind']}.png")
    pm.save(path)
    print("wrote", path)

# render the overlay in each mode
import overlay  # noqa: E402
ov = overlay.WaveformOverlay()

# profile tag on the recording pill
ov._mode = "recording"
ov._preview_on = False
ov.set_profile_tag("terminal · verbatim")
ov._apply_size()
ov.resize(ov.W, ov.H)
ov.repaint()
p = os.path.join(outdir, "overlay_profile_tag.png")
ov.grab().save(p); print("wrote", p)

# toast
ov._mode = "toast"
ov._toast_text = "12 words · Ctrl+Z to undo"
import time
ov._toast_until = time.monotonic() + 2
ov._apply_size()
ov.resize(ov.W, ov.H)
ov.repaint()
p = os.path.join(outdir, "overlay_toast.png")
ov.grab().save(p); print("wrote", p)

print("ALL RENDERS OK")
