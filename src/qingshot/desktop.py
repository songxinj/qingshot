from __future__ import annotations

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
)


def desktop_snapshot():
    screens = QApplication.screens()
    bounds = QRect()
    for screen in screens:
        bounds = bounds.united(screen.geometry())
    ratio = max(s.devicePixelRatio() for s in screens)
    canvas = QPixmap(round(bounds.width() * ratio), round(bounds.height() * ratio))
    canvas.setDevicePixelRatio(ratio)
    canvas.fill(QColor("#18241d"))
    p = QPainter(canvas)
    for screen in screens:
        frame = screen.grabWindow(0)
        if frame.isNull():
            p.end()
            raise RuntimeError("无法读取屏幕，请确认当前桌面已解锁。")
        p.drawPixmap(
            QRectF(screen.geometry().translated(-bounds.topLeft())), frame, QRectF(frame.rect())
        )
    p.end()
    return canvas, bounds
