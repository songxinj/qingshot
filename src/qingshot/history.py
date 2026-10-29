"""Read scaled history thumbnails in a background worker, without QPixmap."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader


def read_thumbnail(path: Path) -> tuple[QImage, QSize]:
    reader = QImageReader(str(path))
    dimensions = reader.size()
    if not dimensions.isValid():
        raise ValueError("无法读取图片尺寸。")
    reader.setScaledSize(dimensions.scaled(QSize(180, 100), Qt.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError("无法读取图片预览。")
    return image, dimensions
