"""Compact capture controls, drawn with Qt vectors and native input semantics."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
)

INK = "#34383c"
ACCENT = "#07c160"
COLORS = ("#fa5151", "#ff8f1f", "#ffc300", "#10aeff", "#07c160", "#666666", "#222222", "#ffffff")


def tool_icon(name: str, color: str = INK) -> QIcon:
    image = QPixmap(40, 40)
    image.setDevicePixelRatio(2)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.35, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if name in {"select", "rect"}:
        if name == "select":
            painter.setPen(QPen(QColor(color), 1.2, Qt.DashLine))
        painter.drawRect(QRectF(4, 4, 12, 12))
    elif name == "ellipse":
        painter.drawEllipse(QRectF(3.5, 3.5, 13, 13))
    elif name == "arrow":
        painter.drawLine(QPointF(4, 16), QPointF(16, 4))
        painter.drawPolyline(QPolygonF([QPointF(8.5, 4), QPointF(16, 4), QPointF(16, 11.5)]))
    elif name == "pen":
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(4, 12.5),
                    QPointF(12.5, 4),
                    QPointF(16, 7.5),
                    QPointF(7.5, 16),
                    QPointF(3.5, 16.5),
                ]
            )
        )
        painter.drawLine(QPointF(10.5, 6), QPointF(14, 9.5))
    elif name == "mosaic":
        painter.drawRect(QRectF(4, 4, 12, 12))
        for row in range(3):
            for column in range(3):
                if (row + column) % 2 == 0:
                    painter.fillRect(QRectF(4 + column * 4, 4 + row * 4, 4, 4), QColor(color))
    elif name == "text":
        painter.drawLine(QPointF(4, 4), QPointF(16, 4))
        painter.drawLine(QPointF(10, 4), QPointF(10, 16))
        painter.drawLine(QPointF(7, 16), QPointF(13, 16))
    elif name == "undo":
        path = QPainterPath(QPointF(5, 7))
        path.cubicTo(18, 4, 18, 16, 7, 15)
        painter.drawPath(path)
        painter.drawPolyline(QPolygonF([QPointF(8, 3.5), QPointF(4, 7), QPointF(8, 10.5)]))
    elif name == "save":
        painter.drawLine(QPointF(10, 3), QPointF(10, 12))
        painter.drawPolyline(QPolygonF([QPointF(6.5, 9), QPointF(10, 12.5), QPointF(13.5, 9)]))
        painter.drawPolyline(
            QPolygonF(
                [QPointF(3.5, 10), QPointF(3.5, 16.5), QPointF(16.5, 16.5), QPointF(16.5, 10)]
            )
        )
    elif name == "pin":
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(6, 3.5),
                    QPointF(14, 3.5),
                    QPointF(12.5, 9),
                    QPointF(15.5, 13),
                    QPointF(4.5, 13),
                    QPointF(7.5, 9),
                    QPointF(6, 3.5),
                ]
            )
        )
        painter.drawLine(QPointF(10, 13), QPointF(10, 18))
    elif name == "translate":
        painter.setPen(QPen(QColor(color), 1.25, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for corner in [
            [QPointF(3.5, 5.8), QPointF(3.5, 3.5), QPointF(5.8, 3.5)],
            [QPointF(14.2, 3.5), QPointF(16.5, 3.5), QPointF(16.5, 5.8)],
            [QPointF(3.5, 14.2), QPointF(3.5, 16.5), QPointF(5.8, 16.5)],
            [QPointF(14.2, 16.5), QPointF(16.5, 16.5), QPointF(16.5, 14.2)],
        ]:
            painter.drawPolyline(QPolygonF(corner))
        painter.drawLine(QPointF(10.0, 5.6), QPointF(10.0, 7.2))
        painter.drawLine(QPointF(6.8, 7.5), QPointF(13.2, 7.5))
        left_stroke = QPainterPath(QPointF(11.5, 7.5))
        left_stroke.quadTo(QPointF(10.2, 11.2), QPointF(6.8, 13.4))
        painter.drawPath(left_stroke)
        right_stroke = QPainterPath(QPointF(8.2, 8.5))
        right_stroke.quadTo(QPointF(9.8, 11.2), QPointF(13.2, 13.4))
        painter.drawPath(right_stroke)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(7, 3, 10, 11), 1, 1)
        painter.drawPolyline(
            QPolygonF(
                [QPointF(4, 6), QPointF(3, 6), QPointF(3, 17), QPointF(13, 17), QPointF(13, 16)]
            )
        )
    elif name == "reset":
        painter.drawRect(QRectF(5, 5, 10, 10))
        painter.drawPolyline(QPolygonF([QPointF(2, 7), QPointF(2, 2), QPointF(7, 2)]))
        painter.drawPolyline(QPolygonF([QPointF(13, 18), QPointF(18, 18), QPointF(18, 13)]))
    elif name == "cancel":
        painter.drawLine(QPointF(5, 5), QPointF(15, 15))
        painter.drawLine(QPointF(15, 5), QPointF(5, 15))
    elif name == "check":
        painter.drawPolyline(QPolygonF([QPointF(4, 10), QPointF(8, 14), QPointF(16, 5.5)]))
    painter.end()
    return QIcon(image)


class FloatingPanel(QFrame):
    """A shallow border and painted shadow, avoiding blur effects per frame."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for inset, alpha in [(0, 5), (1, 7), (2, 10)]:
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(inset, 2 + inset, -inset, -inset), 5, 5
            )
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#dedfe0"), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(3.5, 1.5, -3.5, -5.5), 3, 3)


def tool_button(name: str, label: str, color: str = INK) -> QToolButton:
    button = QToolButton()
    button.setObjectName(name)
    button.setAccessibleName(label)
    button.setToolTip(label)
    button.setIcon(tool_icon(name, color))
    button.setIconSize(QSize(20, 20))
    button.setFixedSize(34, 34)
    button.setStyleSheet(
        "QToolButton { border: none; border-radius: 3px; background: transparent; padding: 0; } QToolButton:hover { background: #f0f0f0; } QToolButton:checked { background: #e7f5ed; } QToolButton:pressed { background: #e4e7e5; }"
    )
    button.setFocusPolicy(Qt.NoFocus)
    button.setCursor(Qt.PointingHandCursor)
    return button


def separator(parent=None):
    line = QFrame(parent)
    line.setFixedSize(1, 18)
    line.setStyleSheet("background: #e7e7e7;")
    return line


class ChoiceButton(QPushButton):
    def __init__(self, color: str | None = None, size_index: int = 0):
        super().__init__()
        self.color = color
        self.size_index = size_index
        self.text_mode = False
        self.setFixedSize(24 if color else 28, 28)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        if self.color:
            if self.isChecked():
                painter.setPen(
                    QPen(QColor(self.color if self.color != "#ffffff" else "#9c9c9c"), 2)
                )
                painter.drawRect(QRectF(3.5, 5.5, 17, 17))
                painter.setPen(Qt.NoPen)
            elif self.underMouse():
                painter.fillRect(self.rect().adjusted(1, 2, -1, -2), QColor("#ededed"))
            painter.fillRect(QRectF(6, 8, 12, 12), QColor(self.color))
            if self.color == "#ffffff":
                painter.setPen(QPen(QColor("#d2d2d2"), 1))
                painter.drawRect(QRectF(6, 8, 12, 12))
        else:
            if self.isChecked() or self.underMouse():
                painter.setBrush(QColor("#f0f2f1"))
                painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 3, 3)
            painter.setPen(QColor(ACCENT if self.isChecked() else "#929699"))
            if self.text_mode:
                font = QFont("Segoe UI")
                font.setPixelSize([12, 16, 20][self.size_index])
                painter.setFont(font)
                painter.drawText(self.rect(), Qt.AlignCenter, "A")
            else:
                radius = [1.8, 3, 4.5][self.size_index]
                painter.setBrush(painter.pen().color())
                painter.drawEllipse(QPointF(14, 14), radius, radius)


class StrokeOptions(FloatingPanel):
    color_changed = Signal(str)
    size_changed = Signal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(9, 5, 9, 9)
        self.row.setSpacing(0)
        self.sizes = QButtonGroup(self)
        for index in range(3):
            button = ChoiceButton(size_index=index)
            button.setAccessibleName(["小", "中", "大"][index])
            button.setToolTip(["小", "中", "大"][index])
            button.clicked.connect(lambda checked=False, value=index: self.size_changed.emit(value))
            self.sizes.addButton(button, index)
            self.row.addWidget(button)
        self.sizes.button(1).setChecked(True)
        self.row.addSpacing(7)
        self.row.addWidget(separator())
        self.row.addSpacing(7)
        self.colors = QButtonGroup(self)
        for color in COLORS:
            button = ChoiceButton(color=color)
            button.setToolTip(color)
            button.setAccessibleName("标注颜色 " + color)
            button.setChecked(color == COLORS[0])
            button.clicked.connect(
                lambda checked=False, value=color: self.color_changed.emit(value)
            )
            self.colors.addButton(button)
            self.row.addWidget(button)
        self.adjustSize()

    def set_text_mode(self, enabled: bool, size_index: int) -> None:
        for button in self.sizes.buttons():
            button.text_mode = enabled
            button.update()
        self.sizes.button(size_index).setChecked(True)


class InlineTextEditor(QPlainTextEdit):
    accepted = Signal()
    canceled = Signal()
    PADDING = 5

    def __init__(self, parent, width_limit: int, height_limit: int):
        super().__init__(parent)
        self.width_limit = max(20, width_limit)
        self.height_limit = max(20, height_limit)
        self.composing = False
        self.setFrameStyle(QFrame.NoFrame)
        self.document().setDocumentMargin(0)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.textChanged.connect(self.fit_content)
        self.setToolTip("Enter 确认文字 · Shift+Enter 换行 · Esc 放弃文字")

    def set_text_style(self, color: QColor, pixels: int) -> None:
        font = QFont("Microsoft YaHei UI")
        font.setPixelSize(pixels)
        self.setFont(font)
        self.setStyleSheet(
            f"QPlainTextEdit {{ color: {color.name()}; font-family: 'Microsoft YaHei UI'; font-size: {pixels}px; background: rgba(255,255,255,18); border: 1px dashed #a8ada9; border-radius: 0; padding: 4px; selection-background-color: #ccebd9; }}"
        )
        self.fit_content()

    def fit_content(self):
        metrics = QFontMetricsF(self.font())
        lines = self.toPlainText().split("\n")
        width = max((metrics.horizontalAdvance(line) for line in lines), default=0) + 14
        self.resize(
            min(self.width_limit, max(100, round(width))),
            min(self.height_limit, round(metrics.lineSpacing() * len(lines) + 12)),
        )

    def inputMethodEvent(self, event):
        self.composing = bool(event.preeditString())
        super().inputMethodEvent(event)

    def keyPressEvent(self, event):
        if not self.composing and event.key() == Qt.Key_Escape:
            self.canceled.emit()
            return
        if (
            not self.composing
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and not event.modifiers() & Qt.ShiftModifier
        ):
            self.accepted.emit()
            return
        super().keyPressEvent(event)


class PinMenu(QMenu):
    """Native QAction navigation with quiet icons and aligned shortcut hints."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(238)
        self.setStyleSheet(
            "QMenu { background: transparent; border: none; padding: 7px; font-family: 'Microsoft YaHei UI'; font-size: 12px; } QMenu::item { padding: 9px 32px 9px 32px; } QMenu::separator { height: 9px; }"
        )

    def add_item(self, name: str, label: str, callback, shortcut: str = "") -> QAction:
        action = QAction(tool_icon(name, "#e35b5b" if name == "cancel" else INK), label, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutVisibleInContextMenu(True)
        action.triggered.connect(callback)
        self.addAction(action)
        return action

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#dcdedf"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        font = QFont("Microsoft YaHei UI")
        font.setPixelSize(12)
        painter.setFont(font)
        for action in self.actions():
            area = self.actionGeometry(action)
            if action.isSeparator():
                painter.setPen(QPen(QColor("#eceeee"), 1))
                painter.drawLine(
                    area.left() + 9, area.center().y(), area.right() - 9, area.center().y()
                )
                continue
            if action == self.activeAction():
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#f1f3f2"))
                painter.drawRoundedRect(QRectF(area), 3, 3)
            action.icon().paint(painter, area.left() + 8, area.center().y() - 9, 18, 18)
            text_area = area.adjusted(36, 0, -62, 0)
            painter.setPen(QColor("#313638"))
            painter.drawText(text_area, Qt.AlignVCenter | Qt.AlignLeft, action.text())
            painter.setPen(QColor("#a1a7a4"))
            painter.drawText(
                area.adjusted(0, 0, -11, 0),
                Qt.AlignVCenter | Qt.AlignRight,
                action.shortcut().toString(QKeySequence.NativeText),
            )
