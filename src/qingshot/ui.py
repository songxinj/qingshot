from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyleOptionButton,
)

from .hotkey import format_shortcut, normalize_shortcut

GREEN = "#07b75b"
STYLE = """
QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: #24332c; }
QMainWindow, QDialog { background: #f5f7f6; }
QFrame#sidebar { background: white; border-right: 1px solid #e6ebe8; }
QFrame#card { background: white; border: 1px solid #e5ebe7; border-radius: 14px; }
QLabel#muted { color: #87928c; font-size: 12px; }
QLabel#heading { font-size: 28px; font-weight: 700; color: #1b2d22; }
QLabel#title { font-size: 16px; font-weight: 600; }
QPushButton { background: white; border: 1px solid #dfe6e1; border-radius: 7px; padding: 9px 14px; }
QPushButton:hover { background: #f0f8f3; border-color: #a8dabb; }
QPushButton:pressed { background: #dcf4e5; }
QPushButton:disabled { color: #9ca9a1; background: #edf1ee; border-color: #e2e8e4; }
QPushButton#primary { background: #07b75b; color: white; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #079d50; }
QPushButton#primary:disabled { background: #d5ded9; color: #8fa196; border: none; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 12px 17px; color: #718078; }
QPushButton#nav:checked { background: #eaf8ef; color: #079c4e; font-weight: 600; }
QPushButton#tool { padding: 7px 10px; border: none; background: transparent; }
QPushButton#tool:checked { color: #079d50; background: #e4f6eb; }
QPushButton#tool:hover { background: #eef5f0; }
QTextEdit, QLineEdit, QComboBox, QSpinBox { background: white; border: 1px solid #dfe6e1; border-radius: 7px; padding: 7px; selection-background-color: #b7eacb; }
QTextEdit:focus, QLineEdit:focus { border: 1px solid #07b75b; }
QLineEdit#shortcut { padding: 6px 12px; font-weight: 600; color: #1f3328; background: #f8fbf9; }
QLineEdit#shortcut:hover { border-color: #a8dabb; background: #f0f8f3; }
QLineEdit#shortcut:focus { border: 1px solid #07b75b; background: #eaf8ef; color: #079c4e; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #cfd9d2; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #bfcfc4; border-radius: 4px; background: white; }
QCheckBox::indicator:hover { border-color: #07b75b; }
QCheckBox::indicator:checked { background: #07b75b; border-color: #07b75b; }
QToolTip { background: #26392e; color: white; border: none; padding: 5px; }
"""


class CheckBox(QCheckBox):
    """QCheckBox with a crisp WeChat-style white vector checkmark when checked."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = QRectF(self.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, self))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.white, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        w, h = rect.width(), rect.height()
        p1 = QPointF(rect.left() + w * 0.23, rect.top() + h * 0.52)
        p2 = QPointF(rect.left() + w * 0.43, rect.top() + h * 0.72)
        p3 = QPointF(rect.left() + w * 0.78, rect.top() + h * 0.30)
        painter.drawPolyline(QPolygonF([p1, p2, p3]))
        painter.end()


class ShortcutInput(QLineEdit):
    """Click-to-record single-chord shortcut input in WeChat settings style."""

    shortcut_changed = Signal(str)
    MODIFIER_KEYS = {
        Qt.Key_Control,
        Qt.Key_Shift,
        Qt.Key_Alt,
        Qt.Key_Meta,
        Qt.Key_Super_L,
        Qt.Key_Super_R,
    }

    def __init__(self, shortcut: str = "Ctrl+Alt+A", parent=None):
        super().__init__(parent)
        self._shortcut = shortcut
        self.setObjectName("shortcut")
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(180)
        self.setToolTip("点击后直接按下新的快捷键组合（Esc 取消修改）")
        self._refresh_text()

    def shortcut(self) -> str:
        return self._shortcut

    def set_shortcut(self, value: str) -> None:
        normalized = normalize_shortcut(value)
        if normalized is not None:
            self._shortcut = normalized
            self._refresh_text()

    def _refresh_text(self) -> None:
        self.setText(format_shortcut(self._shortcut))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.setText("请按下快捷键…")

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._refresh_text()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self._refresh_text()
            self.clearFocus()
            return
        if key in self.MODIFIER_KEYS or key == Qt.Key_unknown:
            return
        parts = []
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.MetaModifier:
            parts.append("Win")
        if key == Qt.Key_Print:
            key_name = "PrintScreen"
        else:
            key_name = QKeySequence(key).toString(QKeySequence.PortableText)
        if not key_name:
            return
        parts.append(key_name.upper() if len(key_name) == 1 else key_name)
        normalized = normalize_shortcut("+".join(parts))
        if normalized is None:
            self.setText("需含修饰键或 F1-F12 / PrintScreen")
            return
        self._shortcut = normalized
        self._refresh_text()
        self.clearFocus()
        self.shortcut_changed.emit(normalized)


def icon(name="capture", color=GREEN, size=32):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 32, size / 32)
    p.setPen(QPen(QColor(color), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if name == "capture":
        for a, b, c in [
            ((11, 6), (6, 6), (6, 11)),
            ((21, 6), (26, 6), (26, 11)),
            ((6, 21), (6, 26), (11, 26)),
            ((21, 26), (26, 26), (26, 21)),
        ]:
            p.drawLine(QPointF(*a), QPointF(*b))
            p.drawLine(QPointF(*b), QPointF(*c))
        p.drawRoundedRect(QRectF(11, 11, 10, 10), 2, 2)
    elif name == "pin":
        p.drawLine(11, 7, 23, 7)
        p.drawLine(13, 7, 13, 14)
        p.drawLine(21, 7, 21, 14)
        p.drawLine(13, 14, 9, 20)
        p.drawLine(9, 20, 25, 20)
        p.drawLine(25, 20, 21, 14)
        p.drawLine(17, 20, 17, 28)
    elif name == "translate":
        for corner in [
            [QPointF(6, 10.5), QPointF(6, 6), QPointF(10.5, 6)],
            [QPointF(21.5, 6), QPointF(26, 6), QPointF(26, 10.5)],
            [QPointF(6, 21.5), QPointF(6, 26), QPointF(10.5, 26)],
            [QPointF(21.5, 26), QPointF(26, 26), QPointF(26, 21.5)],
        ]:
            p.drawPolyline(QPolygonF(corner))
        p.drawLine(QPointF(15.5, 9.0), QPointF(16.5, 11.2))
        p.drawLine(QPointF(10.2, 11.8), QPointF(21.8, 11.8))
        left_stroke = QPainterPath(QPointF(19.0, 11.8))
        left_stroke.quadTo(QPointF(16.6, 18.4), QPointF(10.4, 22.2))
        p.drawPath(left_stroke)
        right_stroke = QPainterPath(QPointF(12.6, 13.4))
        right_stroke.quadTo(QPointF(16.0, 18.4), QPointF(21.6, 22.2))
        p.drawPath(right_stroke)
    elif name == "history":
        p.drawEllipse(QRectF(6, 6, 21, 21))
        p.drawLine(16, 11, 16, 17)
        p.drawLine(16, 17, 22, 20)
    elif name == "settings":
        p.drawEllipse(QRectF(6, 6, 20, 20))
        p.drawEllipse(QRectF(12, 12, 8, 8))
    p.end()
    return QIcon(pix)


def button(text, callback=None, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if callback:
        b.clicked.connect(callback)
    b.setCursor(Qt.PointingHandCursor)
    return b
