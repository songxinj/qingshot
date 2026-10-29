from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from .capture_controls import PinMenu
from .images import save_png
from .ui import STYLE
from .workers import TaskRunner


class PinWindow(QWidget):
    translate_requested = Signal(QPixmap)
    closed = Signal(object)

    def __init__(self, pixmap, position=None, runner: TaskRunner | None = None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle("轻映 · 贴图")
        self.pixmap = QPixmap(pixmap)
        self.runner = runner if runner is not None else TaskRunner(self)
        self.zoom = 1.0
        self.drag_offset = QPoint()
        self.setMouseTracking(True)
        self.setStyleSheet(STYLE)
        self.setToolTip("拖动移动 · 滚轮缩放 · Ctrl+滚轮调透明度\n双击 / Esc 关闭 · 右键更多操作")
        self.resize_to_image()
        if position is not None:
            self.move(position)

    def resize_to_image(self):
        size = self.pixmap.deviceIndependentSize()
        self.resize(
            max(60, round(size.width() * self.zoom)), max(40, round(size.height() * self.zoom))
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), self.pixmap)
        p.setPen(QPen(QColor("#07c160" if self.underMouse() else "#c9cfcc"), 1))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.close()

    def wheelEvent(self, event):
        direction = 1 if event.angleDelta().y() > 0 else -1
        if event.modifiers() & Qt.ControlModifier:
            self.setWindowOpacity(max(0.2, min(1, self.windowOpacity() + direction * 0.08)))
        else:
            self.zoom = max(0.15, min(4, self.zoom * (1.1 if direction > 0 else 1 / 1.1)))
            self.resize_to_image()

    def contextMenuEvent(self, event):
        menu = self.create_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()

    def create_menu(self) -> PinMenu:
        menu = PinMenu(self)
        menu.add_item(
            "copy", "复制图片", lambda: QApplication.clipboard().setPixmap(self.pixmap), "Ctrl+C"
        )
        menu.add_item("save", "另存为…", self.save, "Ctrl+S")
        menu.addSeparator()
        menu.add_item(
            "translate", "识字 / 翻译", lambda: self.translate_requested.emit(self.pixmap)
        )
        menu.add_item("reset", "恢复原始大小", self.reset_zoom, "Ctrl+0")
        menu.addSeparator()
        menu.add_item("cancel", "关闭贴图", self.close, "Esc")
        return menu

    def reset_zoom(self):
        self.zoom = 1
        self.resize_to_image()
        self.setWindowOpacity(1)

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存贴图", "轻映.png", "PNG 图片 (*.png)")
        if path:
            image = self.pixmap.toImage()
            self.runner.submit(
                lambda: save_png(image, path),
                lambda saved: None,
                lambda message: QMessageBox.warning(self, "保存失败", message),
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.matches(QKeySequence.Copy):
            QApplication.clipboard().setPixmap(self.pixmap)
        elif event.matches(QKeySequence.Save):
            self.save()
        elif event.key() == Qt.Key_0 and event.modifiers() & Qt.ControlModifier:
            self.reset_zoom()

    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)
