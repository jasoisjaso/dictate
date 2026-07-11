"""One-off: render the tray mic glyph to a multi-size .ico (offscreen Qt)."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "dictate.ico")


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


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Qt writes single-image ICO; build the multi-size ICO container by hand.
    import io
    import struct

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = []
    for sz in sizes:
        img = render(sz)
        from PySide6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        pngs.append(bytes(buf.data()))
        buf.close()

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


if __name__ == "__main__":
    main()
