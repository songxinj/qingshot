from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QWidget

from .capture_controls import (
    ACCENT,
    COLORS,
    FloatingPanel,
    InlineTextEditor,
    StrokeOptions,
    separator,
    tool_button,
)
from .hotkey import qt_key_sequence
from .ui import STYLE

HANDLE_CURSORS = {
    "tl": Qt.SizeFDiagCursor,
    "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor,
    "bl": Qt.SizeBDiagCursor,
    "t": Qt.SizeVerCursor,
    "b": Qt.SizeVerCursor,
    "l": Qt.SizeHorCursor,
    "r": Qt.SizeHorCursor,
}
MIN_SELECTION_SIZE = 5
HANDLE_HIT_DISTANCE = 12


class CaptureOverlay(QWidget):
    completed = Signal(QPixmap, str, QPoint)
    canceled = Signal()

    def __init__(self, canvas, bounds, preferences=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle("轻映 · 框选截图")
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setStyleSheet(STYLE)
        self.canvas = canvas
        self._dimmed_canvas = self._build_dimmed_canvas(canvas)
        self._dimmed_cache_key = canvas.cacheKey()
        self.setGeometry(bounds)
        self.selection = QRect()
        self.original = QRect()
        self.start = QPoint()
        self.tool = "select"
        self.color = QColor(COLORS[0])
        self.font_size = 24
        self.text_size_index = 1
        self.stroke_size_index = 1
        self.editor = None
        self.stroke = 3
        self.items = []
        self.current = None
        self.mode = None
        self.done = False
        self.copy_shortcut = getattr(preferences, "copy_shortcut", "Ctrl+C")
        self.pin_shortcut = getattr(preferences, "pin_shortcut", "Ctrl+P")
        self.save_shortcut = getattr(preferences, "save_shortcut", "Ctrl+S")
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self._build_toolbar()
        self.shortcuts = [
            QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo),
            QShortcut(
                qt_key_sequence(self.copy_shortcut), self, activated=lambda: self.finish("copy")
            ),
            QShortcut(
                qt_key_sequence(self.save_shortcut), self, activated=lambda: self.finish("save")
            ),
            QShortcut(
                qt_key_sequence(self.pin_shortcut), self, activated=lambda: self.finish("pin")
            ),
        ]

    @staticmethod
    def _build_dimmed_canvas(canvas: QPixmap) -> QPixmap:
        dimmed = canvas.copy()
        painter = QPainter(dimmed)
        painter.fillRect(
            QRectF(
                0,
                0,
                dimmed.deviceIndependentSize().width(),
                dimmed.deviceIndependentSize().height(),
            ),
            QColor(0, 0, 0, 105),
        )
        painter.end()
        return dimmed

    def _build_toolbar(self) -> None:
        self.toolbar = FloatingPanel(self)
        row = QHBoxLayout(self.toolbar)
        row.setContentsMargins(7, 4, 7, 8)
        row.setSpacing(0)
        self.tools = QButtonGroup(self)
        self.tool_buttons = {}
        for name, label in [
            ("select", "调整选区"),
            ("rect", "矩形"),
            ("ellipse", "圆形"),
            ("arrow", "箭头"),
            ("pen", "画笔"),
            ("mosaic", "马赛克"),
            ("text", "文字"),
        ]:
            button = tool_button(name, label)
            button.setCheckable(True)
            button.setChecked(name == "select")
            button.clicked.connect(lambda checked=False, value=name: self.toggle_tool(value))
            self.tools.addButton(button)
            self.tool_buttons[name] = button
            row.addWidget(button)
        row.addSpacing(6)
        row.addWidget(separator())
        row.addSpacing(6)
        self.undo_button = tool_button("undo", "撤销  Ctrl+Z")
        self.undo_button.clicked.connect(self.undo)
        self.undo_button.setEnabled(False)
        row.addWidget(self.undo_button)
        for name, label in [
            ("translate", "识字 / 翻译"),
            ("pin", f"贴图  {self.pin_shortcut}"),
            ("save", f"保存  {self.save_shortcut}"),
        ]:
            button = tool_button(name, label)
            button.clicked.connect(lambda checked=False, action=name: self.finish(action))
            row.addWidget(button)
        row.addSpacing(6)
        row.addWidget(separator())
        row.addSpacing(6)
        for name, action, label, color in [
            ("cancel", "cancel", "取消  Esc", "#fa5151"),
            ("check", "copy", f"完成并复制  Enter / {self.copy_shortcut}", ACCENT),
        ]:
            button = tool_button(name, label, color)
            button.clicked.connect(lambda checked=False, value=action: self.finish(value))
            row.addWidget(button)
        self.toolbar.adjustSize()
        self.toolbar.hide()
        self.options = StrokeOptions(self)
        self.options.color_changed.connect(self.set_color)
        self.options.size_changed.connect(self.set_size)
        self.options.hide()

    def toggle_tool(self, tool: str) -> None:
        if tool == self.tool and tool != "select":
            self.set_tool("select")
        else:
            self.set_tool(tool)

    def set_tool(self, tool: str) -> None:
        self.commit_text()
        self.undo_button.setEnabled(bool(self.items))
        self.tool = tool
        self.tool_buttons[tool].setChecked(True)
        self.options.set_text_mode(
            tool == "text", self.text_size_index if tool == "text" else self.stroke_size_index
        )
        self.setCursor(Qt.IBeamCursor if tool == "text" else Qt.CrossCursor)
        if not self.selection.isEmpty():
            self.position_toolbar()

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        if self.editor is not None:
            self.editor.set_text_style(self.color, self.font_size)

    def set_size(self, index: int) -> None:
        if self.tool == "text":
            self.text_size_index = index
            self.font_size = [18, 24, 32][index]
            if self.editor is not None:
                self.editor.set_text_style(self.color, self.font_size)
        else:
            self.stroke_size_index = index
            self.stroke = [2, 3, 5][index]

    def position_toolbar(self) -> None:
        self.toolbar.adjustSize()
        width, height = self.toolbar.width(), self.toolbar.height()
        screen = QApplication.screenAt(self.mapToGlobal(self.selection.center()))
        viewport = (
            screen.geometry().translated(-self.geometry().topLeft()).intersected(self.rect())
            if screen
            else self.rect()
        )
        if viewport.isEmpty():
            viewport = self.rect()
        annotation = self.tool != "select"
        secondary = self.options.height() + 3 if annotation else 0
        x = max(
            viewport.left() + 6,
            min(self.selection.right() - width + 1, viewport.right() - width - 6),
        )
        below = self.selection.bottom() + 8
        above = below + height + secondary > viewport.bottom() - 6
        y = self.selection.top() - height - 8 if above else below
        y = max(viewport.top() + secondary + 6, min(y, viewport.bottom() - height - secondary - 6))
        self.toolbar.move(x, y)
        self.toolbar.show()
        self.options.setVisible(annotation)
        if annotation:
            anchor = (
                self.tool_buttons[self.tool]
                .mapTo(self, self.tool_buttons[self.tool].rect().center())
                .x()
            )
            options_x = max(
                viewport.left() + 6, min(anchor - 42, viewport.right() - self.options.width() - 6)
            )
            options_y = y - self.options.height() - 3 if above else y + height + 3
            self.options.move(options_x, options_y)
            self.options.raise_()
        self.toolbar.raise_()

    def start_text(self, point: QPoint) -> None:
        self.commit_text()
        x = max(self.selection.left() + 2, min(point.x(), self.selection.right() - 102))
        y = max(
            self.selection.top() + 2, min(point.y(), self.selection.bottom() - self.font_size - 16)
        )
        self.editor = InlineTextEditor(
            self, self.selection.right() - x - 1, self.selection.bottom() - y - 1
        )
        self.editor.move(x, y)
        self.editor.set_text_style(self.color, self.font_size)
        self.editor.accepted.connect(self.commit_text)
        self.editor.canceled.connect(self.cancel_text)
        for shortcut in self.shortcuts:
            shortcut.setEnabled(False)
        self.editor.show()
        self.editor.setFocus(Qt.MouseFocusReason)

    def commit_text(self) -> None:
        if self.editor is None:
            return
        editor = self.editor
        text = editor.toPlainText()
        if text.strip():
            baseline = QFontMetricsF(editor.font()).ascent() + InlineTextEditor.PADDING
            self.items.append(
                {
                    "kind": "text",
                    "points": [
                        QPointF(editor.x() + InlineTextEditor.PADDING, editor.y() + baseline)
                    ],
                    "text": text,
                    "color": QColor(self.color),
                    "width": self.stroke,
                    "font_size": self.font_size,
                }
            )
        self.cancel_text()
        self.undo_button.setEnabled(bool(self.items))
        self.update()

    def cancel_text(self) -> None:
        if self.editor is not None:
            editor, self.editor = self.editor, None
            editor.hide()
            editor.deleteLater()
        for shortcut in self.shortcuts:
            shortcut.setEnabled(True)
        self.setFocus(Qt.OtherFocusReason)
        self.update()

    def handles(self) -> list[tuple[QPoint, str]]:
        r = self.selection
        return [
            (r.topLeft(), "tl"),
            (r.topRight(), "tr"),
            (r.bottomLeft(), "bl"),
            (r.bottomRight(), "br"),
            (QPoint(r.center().x(), r.top()), "t"),
            (QPoint(r.center().x(), r.bottom()), "b"),
            (QPoint(r.left(), r.center().y()), "l"),
            (QPoint(r.right(), r.center().y()), "r"),
        ]

    def _hit_handle(self, pt: QPoint) -> str | None:
        if self.selection.isEmpty():
            return None
        return next(
            (
                name
                for handle, name in self.handles()
                if (handle - pt).manhattanLength() < HANDLE_HIT_DISTANCE
            ),
            None,
        )

    def _can_adjust_selection(self) -> bool:
        return self.tool == "select" or not self.items

    def _update_hover_cursor(self, pt: QPoint) -> None:
        if self.selection.isEmpty():
            self.setCursor(Qt.CrossCursor)
            return
        if self._can_adjust_selection():
            handle = self._hit_handle(pt)
            if handle is not None:
                self.setCursor(HANDLE_CURSORS[handle])
                return
        if self.selection.contains(pt):
            if self.tool == "select":
                self.setCursor(Qt.SizeAllCursor)
            elif self.tool == "text":
                self.setCursor(Qt.IBeamCursor)
            else:
                self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.CrossCursor if self.tool == "select" else Qt.ArrowCursor)

    def paintEvent(self, event):
        if self._dimmed_cache_key != self.canvas.cacheKey():
            self._dimmed_canvas = self._build_dimmed_canvas(self.canvas)
            self._dimmed_cache_key = self.canvas.cacheKey()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._dimmed_canvas)
        if not self.selection.isEmpty():
            ratio = self.canvas.devicePixelRatio()
            p.save()
            p.setClipRect(self.selection)
            p.drawPixmap(0, 0, self.canvas)
            self.paint_items(p)
            p.restore()
            p.setPen(QPen(QColor(ACCENT), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(self.selection.adjusted(0, 0, -1, -1))
            p.setBrush(QColor(ACCENT))
            for pt, _ in self.handles():
                p.drawRect(QRect(pt - QPoint(2, 2), pt + QPoint(2, 2)))
            label = f"{round(self.selection.width() * ratio)} × {round(self.selection.height() * ratio)}"
            font = QFont("Segoe UI")
            font.setPixelSize(11)
            p.setFont(font)
            label_width = round(QFontMetricsF(font).horizontalAdvance(label)) + 12
            y = (
                self.selection.top() - 23
                if self.selection.top() >= 26
                else self.selection.top() + 5
            )
            badge = QRect(self.selection.left(), y, label_width, 19)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(30, 33, 35, 190))
            p.drawRoundedRect(badge, 2, 2)
            p.setPen(Qt.white)
            p.drawText(badge, Qt.AlignCenter, label)
        else:
            box = QRect((self.width() - 460) // 2, 45, 460, 43)
            p.setBrush(QColor(25, 38, 30, 235))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(box, 8, 8)
            p.setPen(Qt.white)
            p.drawText(box, Qt.AlignCenter, "拖动选择截图区域  ·  右键 / Esc 取消")
        p.end()

    def _mosaic_pixmap(self, item: dict, rect: QRectF) -> QPixmap:
        ratio = self.canvas.devicePixelRatio()
        src_rect = QRect(
            round(rect.x() * ratio),
            round(rect.y() * ratio),
            max(1, round(rect.width() * ratio)),
            max(1, round(rect.height() * ratio)),
        )
        small_w = max(1, int(rect.width() / 12))
        small_h = max(1, int(rect.height() / 12))
        key = (
            self.canvas.cacheKey(),
            src_rect.x(),
            src_rect.y(),
            src_rect.width(),
            src_rect.height(),
            small_w,
            small_h,
        )
        if item.get("_mosaic_key") != key or "_mosaic_pixmap" not in item:
            source = self.canvas.copy(src_rect)
            item["_mosaic_pixmap"] = source.scaled(
                small_w,
                small_h,
                Qt.IgnoreAspectRatio,
                Qt.FastTransformation,
            )
            item["_mosaic_key"] = key
        return item["_mosaic_pixmap"]

    @staticmethod
    def _draw_arrow(
        painter: QPainter, start: QPointF, end: QPointF, color: QColor, width: int
    ) -> None:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        distance = math.hypot(dx, dy)
        if distance < 1e-3:
            return
        angle = math.atan2(dy, dx)
        head_length = min(distance * 0.75, max(12.0, width * 4.2))
        head_angle = 0.45
        left_wing = end - QPointF(
            math.cos(angle - head_angle) * head_length,
            math.sin(angle - head_angle) * head_length,
        )
        right_wing = end - QPointF(
            math.cos(angle + head_angle) * head_length,
            math.sin(angle + head_angle) * head_length,
        )
        neck = end - QPointF(
            math.cos(angle) * (head_length * 0.72),
            math.sin(angle) * (head_length * 0.72),
        )
        painter.drawLine(start, neck)
        painter.setPen(QPen(color, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([end, left_wing, neck, right_wing]))

    def paint_items(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        active_items = self.items if self.current is None else [*self.items, self.current]
        for item in active_items:
            points = item["points"]
            a, b = points[0], points[-1]
            r = QRectF(a, b).normalized()
            painter.setPen(
                QPen(item["color"], item["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            )
            painter.setBrush(Qt.NoBrush)
            kind = item["kind"]
            if kind == "rect":
                painter.drawRect(r)
            elif kind == "ellipse":
                painter.drawEllipse(r)
            elif kind == "arrow":
                self._draw_arrow(painter, a, b, item["color"], item["width"])
            elif kind == "pen":
                if len(points) == 1:
                    painter.drawPoint(points[0])
                else:
                    painter.drawPolyline(QPolygonF(points))
            elif kind == "text":
                font = QFont("Microsoft YaHei UI", 12 + item["width"] * 2)
                if "font_size" in item:
                    font.setPixelSize(item["font_size"])
                painter.setFont(font)
                spacing = QFontMetricsF(font).lineSpacing()
                for index, line in enumerate(item["text"].split("\n")):
                    painter.drawText(a + QPointF(0, index * spacing), line)
            elif kind == "mosaic" and r.width() > 0 and r.height() > 0:
                small = self._mosaic_pixmap(item, r)
                painter.save()
                painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
                painter.drawPixmap(r, small, QRectF(small.rect()))
                painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.editor is not None:
                self.cancel_text()
                return
            self.finish("cancel")
            return
        if event.button() != Qt.LeftButton:
            return
        pt = event.position().toPoint()
        self.commit_text()
        self.start = pt
        handle = self._hit_handle(pt) if self._can_adjust_selection() else None
        if self.tool != "text":
            self.toolbar.hide()
            self.options.hide()
        if handle is not None:
            self.original = QRect(self.selection)
            self.mode = handle
        elif self.tool == "select":
            self.original = QRect(self.selection)
            self.mode = "move" if self.selection.contains(pt) else "new"
            if self.mode == "new":
                self.items.clear()
                self.selection = QRect(pt, pt)
        elif self.selection.contains(pt):
            if self.tool == "text":
                self.start_text(pt)
                self.position_toolbar()
            else:
                self.current = {
                    "kind": self.tool,
                    "points": [QPointF(pt), QPointF(pt)],
                    "color": QColor(self.color),
                    "width": self.stroke,
                }
        self.update()

    def mouseMoveEvent(self, event):
        pt = event.position().toPoint()
        pt.setX(max(0, min(pt.x(), self.width() - 1)))
        pt.setY(max(0, min(pt.y(), self.height() - 1)))
        if not event.buttons() & Qt.LeftButton:
            self._update_hover_cursor(pt)
            return
        if self.mode == "new":
            self.selection = QRect(self.start, pt).normalized()
        elif self.mode == "move":
            delta = pt - self.start
            moved = self.original.translated(delta)
            moved.moveLeft(max(0, min(moved.left(), self.width() - moved.width())))
            moved.moveTop(max(0, min(moved.top(), self.height() - moved.height())))
            offset = moved.topLeft() - self.selection.topLeft()
            for item in self.items:
                item["points"] = [p + QPointF(offset) for p in item["points"]]
                item.pop("_mosaic_key", None)
                item.pop("_mosaic_pixmap", None)
            self.selection = moved
        elif self.mode in HANDLE_CURSORS:
            r = QRect(self.original)
            setters = {
                "tl": r.setTopLeft,
                "tr": r.setTopRight,
                "bl": r.setBottomLeft,
                "br": r.setBottomRight,
                "t": lambda p: r.setTop(p.y()),
                "b": lambda p: r.setBottom(p.y()),
                "l": lambda p: r.setLeft(p.x()),
                "r": lambda p: r.setRight(p.x()),
            }
            setters[self.mode](pt)
            self.selection = r.normalized().intersected(self.rect())
        elif self.current:
            pt.setX(max(self.selection.left(), min(pt.x(), self.selection.right())))
            pt.setY(max(self.selection.top(), min(pt.y(), self.selection.bottom())))
            if self.tool == "pen":
                if self.current["points"][-1] != QPointF(pt):
                    self.current["points"].append(QPointF(pt))
            else:
                self.current["points"][-1] = QPointF(pt)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.current:
            self.items.append(self.current)
            self.current = None
        self.mode = None
        self.undo_button.setEnabled(bool(self.items))
        if (
            self.selection.width() >= MIN_SELECTION_SIZE
            and self.selection.height() >= MIN_SELECTION_SIZE
        ):
            self.position_toolbar()
        self._update_hover_cursor(event.position().toPoint())
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.selection.contains(event.position().toPoint()):
            self.finish("copy")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.editor is not None:
                self.cancel_text()
            else:
                self.finish("cancel")
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.finish("copy")
        else:
            super().keyPressEvent(event)

    def undo(self):
        if self.editor is not None:
            self.editor.undo()
            return
        if self.items:
            self.items.pop()
            self.undo_button.setEnabled(bool(self.items))
            self.update()

    def result(self):
        ratio = self.canvas.devicePixelRatio()
        result = QPixmap(
            round(self.selection.width() * ratio), round(self.selection.height() * ratio)
        )
        result.setDevicePixelRatio(ratio)
        result.fill(Qt.transparent)
        p = QPainter(result)
        p.translate(-self.selection.x(), -self.selection.y())
        p.drawPixmap(0, 0, self.canvas)
        self.paint_items(p)
        p.end()
        return result

    def finish(self, action):
        if self.done:
            return
        if action != "cancel" and (self.selection.width() < 5 or self.selection.height() < 5):
            return
        if action == "cancel":
            self.cancel_text()
        else:
            self.commit_text()
        self.done = True
        if action == "cancel":
            self.canceled.emit()
        else:
            self.completed.emit(
                self.result(), action, self.geometry().topLeft() + self.selection.topLeft()
            )
        self.close()

    def closeEvent(self, event):
        if not self.done:
            self.done = True
            self.canceled.emit()
        super().closeEvent(event)
