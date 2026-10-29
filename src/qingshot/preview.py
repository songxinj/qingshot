"""QingShot / 轻映 — a small native Windows screenshot workspace."""

from __future__ import annotations

from PySide6.QtCore import (
    QPoint,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QWidget,
)

from .ui import GREEN


class Preview(QWidget):
    def __init__(self):
        super().__init__()
        self._pixmap: QPixmap | None = None
        self._scaled_cache: QPixmap | None = None
        self._cache_key: tuple[int, QSize] | None = None
        self.setMinimumHeight(255)

    @property
    def pixmap(self) -> QPixmap | None:
        return self._pixmap

    @pixmap.setter
    def pixmap(self, value: QPixmap | None) -> None:
        self._pixmap = value
        self._scaled_cache = None
        self._cache_key = None
        self.update()

    def _scaled_pixmap(self) -> QPixmap:
        bounds = (self.size() - QSize(32, 32)).expandedTo(QSize(1, 1))
        key = (self._pixmap.cacheKey(), bounds)
        if self._scaled_cache is None or self._cache_key != key:
            ratio = self._pixmap.devicePixelRatio() or 1.0
            physical_bounds = QSize(
                max(1, round(bounds.width() * ratio)),
                max(1, round(bounds.height() * ratio)),
            )
            scaled = self._pixmap.scaled(
                physical_bounds, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            scaled.setDevicePixelRatio(ratio)
            self._scaled_cache = scaled
            self._cache_key = key
        return self._scaled_cache

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#f1f6f2"))
        p.drawRoundedRect(area, 12, 12)
        if self._pixmap is not None and not self._pixmap.isNull():
            image = self._scaled_pixmap()
            logical_size = image.deviceIndependentSize()
            target = QRectF(0, 0, logical_size.width(), logical_size.height())
            target.moveCenter(QRectF(self.rect()).center())
            p.drawPixmap(target, image, QRectF(image.rect()))
        else:
            p.setPen(QPen(QColor("#e0eae2"), 1))
            for x in range(15, self.width(), 18):
                for y in range(15, self.height(), 18):
                    p.drawPoint(x, y)
            w, h = min(340, self.width() - 70), 170
            r = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
            p.setPen(QPen(QColor("#d4e3d8"), 1))
            p.setBrush(Qt.white)
            p.drawRoundedRect(r, 10, 10)
            for i, color in enumerate(["#b7d7c1", "#cbe2d1", "#deeee2"]):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color))
                p.drawEllipse(QPoint(int(r.x() + 18 + 15 * i), int(r.y() + 17)), 3, 3)
            p.setPen(QColor("#294837"))
            p.setFont(QFont("Microsoft YaHei UI", 16, QFont.Bold))
            p.drawText(
                QRectF(r.x() + 25, r.y() + 39, w - 40, 35), Qt.AlignLeft, "把灵感，留在眼前。"
            )
            p.setPen(QColor("#8a9e91"))
            p.setFont(QFont("Microsoft YaHei UI", 10))
            p.drawText(
                QRectF(r.x() + 25, r.y() + 83, w - 40, 25),
                Qt.AlignLeft,
                "截取 · 标注 · 贴图 · 翻译",
            )
            select = r.adjusted(14, 32, -14, -38)
            p.setPen(QPen(QColor(GREEN), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(select)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(GREEN))
            for point in [
                select.topLeft(),
                select.topRight(),
                select.bottomLeft(),
                select.bottomRight(),
            ]:
                p.drawRect(QRectF(point.x() - 3, point.y() - 3, 6, 6))
            toolbar = QRectF(r.x() + 68, r.bottom() - 23, w - 90, 35)
            p.setBrush(Qt.white)
            p.setPen(QPen(QColor("#dce8df"), 1))
            p.drawRoundedRect(toolbar, 6, 6)
            p.setPen(QColor("#3c5e49"))
            p.drawText(toolbar, Qt.AlignCenter, "□    ○    ↗    T    ▦    ↶    ✓")
        p.end()
