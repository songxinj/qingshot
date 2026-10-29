"""Render the actual capture widgets on a synthetic document for design review."""

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from qingshot.overlay import CaptureOverlay
from qingshot.pin import PinWindow
from qingshot.ui import STYLE


def main():
    app = QApplication([])
    app.setStyleSheet(STYLE)
    for name in ("msyh.ttc", "arial.ttf", "segoeui.ttf"):
        path = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts" / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    folder = PROJECT / "docs" / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    canvas = QPixmap(1000, 640)
    canvas.fill(QColor("#e9edeb"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawRoundedRect(QRectF(75, 62, 850, 490), 8, 8)
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(13)
    painter.setFont(font)
    painter.setPen(QColor("#7f8983"))
    painter.drawText(106, 98, "QINGSHOT  /  设计协作")
    font.setPixelSize(29)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#25352c"))
    painter.drawText(190, 183, "截图，让表达更简单。")
    font.setPixelSize(15)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QColor("#8b948e"))
    painter.drawText(190, 230, "截取屏幕 · 添加标注 · 贴在眼前")
    painter.setPen(QColor("#e5e9e6"))
    painter.drawLine(190, 254, 786, 254)
    painter.setPen(QColor("#a1a9a3"))
    font.setPixelSize(13)
    painter.setFont(font)
    painter.drawText(190, 376, "按 Enter 确认文字，Shift + Enter 换行。")
    painter.end()
    overlay = CaptureOverlay(canvas, QRect(0, 0, 1000, 640))
    overlay.selection = QRect(155, 126, 670, 300)
    overlay.items = [
        {
            "kind": "rect",
            "points": [QPointF(179, 145), QPointF(582, 200)],
            "color": QColor("#fa5151"),
            "width": 2,
        }
    ]
    overlay.show()
    overlay.set_tool("text")
    overlay.start_text(QPoint(190, 285))
    overlay.editor.setPlainText("直接在截图上输入文字")
    app.processEvents()
    overlay.grab().save(str(folder / "capture-ui.png"))
    overlay.commit_text()
    app.processEvents()
    overlay.grab().save(str(folder / "capture-ui-committed.png"))
    overlay.result().save(str(folder / "annotation-result.png"))
    pin = PinWindow(canvas)
    menu = pin.create_menu()
    menu.popup(QPoint(20, 20))
    app.processEvents()
    menu.setActiveAction(menu.actions()[0])
    app.processEvents()
    menu.grab().save(str(folder / "pin-menu.png"))
    menu.close()
    pin.close()
    overlay.close()
    print(str(folder), flush=True)


if __name__ == "__main__":
    main()
