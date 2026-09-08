"""One-off: render the tray mic glyph to app icons (offscreen Qt).

Windows wants a multi-size `.ico`; macOS wants an `.icns`, and the only
supported way to build one is `iconutil` against an `.iconset` directory of
PNGs at the exact names Apple specifies. Both come from the same `render()`,
so the two platforms cannot drift into different-looking icons.

    python packaging/make_icon.py          # both, whatever this machine can do
"""
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
OUT = os.path.join(ASSETS, "dictate.ico")
ICNS_OUT = os.path.join(ASSETS, "dictate.icns")

# Apple's fixed names. Each logical size ships twice — 1x and the @2x Retina
# variant, which is simply the next power of two rendered fresh rather than
# upscaled, so the glyph stays crisp at every point size.
ICNS_ENTRIES = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64.0
    p.setPen(QColor(0, 0, 0, 60))
    p.setBrush(QColor("#46c07a"))
    p.drawEllipse(QRect(int(6 * s), int(6 * s), int(52 * s), int(52 * s)))
    p.setBrush(QColor("#ffffff"))
    p.setPen(QColor("#ffffff"))
    p.drawRoundedRect(QRect(int(26 * s), int(16 * s), int(12 * s), int(22 * s)),
                      6 * s, 6 * s)
    p.drawArc(QRect(int(20 * s), int(26 * s), int(24 * s), int(18 * s)),
              180 * 16, 180 * 16)
    p.drawRect(QRect(int(30 * s), int(44 * s), int(4 * s), int(6 * s)))
    p.drawRect(QRect(int(24 * s), int(50 * s), int(16 * s), int(3 * s)))
    p.end()
    return img


def png_bytes(size: int) -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice

    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    render(size).save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


def write_icns() -> bool:
    """Build assets/dictate.icns via iconutil. False if this machine can't.

    iconutil is macOS-only and ships with the OS, so a Windows checkout simply
    skips this and keeps its .ico — the alternative, hand-rolling the ICNS
    container, would be a second unsupported format writer for no gain.
    """
    import shutil
    import tempfile

    tool = shutil.which("iconutil")
    if not tool:
        print("iconutil not found — skipping .icns (macOS only)")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "dictate.iconset")
        os.makedirs(iconset)
        for name, size in ICNS_ENTRIES:
            with open(os.path.join(iconset, name), "wb") as f:
                f.write(png_bytes(size))
        subprocess.run([tool, "-c", "icns", iconset, "-o", ICNS_OUT],
                       check=True)
    print("wrote", ICNS_OUT, os.path.getsize(ICNS_OUT), "bytes")
    return True


def main():
    os.makedirs(ASSETS, exist_ok=True)
    # Qt writes single-image ICO; build the multi-size ICO container by hand.
    import struct

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = [png_bytes(sz) for sz in sizes]

    with open(OUT, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(sizes)))
        offset = 6 + 16 * len(sizes)
        for sz, png in zip(sizes, pngs):
            b = sz if sz < 256 else 0
            f.write(struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(png), offset))
            offset += len(png)
        for png in pngs:
            f.write(png)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")

    # The .app's icon. Skipped with a printed line off macOS rather than
    # failing the run — a Windows checkout still wants its .ico.
    write_icns()


if __name__ == "__main__":
    main()
