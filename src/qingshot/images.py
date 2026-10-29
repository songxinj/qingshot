"""Memory-only image serialization helpers."""

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage, QPixmap


def png_bytes(pixmap: QImage | QPixmap) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def save_png(image: QImage, path: str) -> str:
    """Encode on a worker thread; the caller keeps UI and error presentation."""
    if image.isNull() or not image.save(path, "PNG"):
        raise OSError("无法保存 PNG，请检查目标目录是否可写。")
    return path
