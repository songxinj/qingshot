"""QingShot / 轻映 — a small native Windows screenshot workspace."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import (
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .desktop import desktop_snapshot
from .history import read_thumbnail
from .hotkey import Hotkey, format_shortcut
from .images import save_png
from .overlay import CaptureOverlay
from .paths import DATA, ROOT
from .pin import PinWindow
from .preview import Preview
from .storage import CaptureStore, Preferences, SettingsStore
from .translation_dialog import TranslationDialog
from .ui import CheckBox, ShortcutInput, button, icon
from .workers import TaskRunner


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("轻映 QingShot")
        self.setWindowIcon(icon())
        self.resize(1080, 760)
        self.setMinimumSize(940, 680)
        self.pins = []
        self.dialogs = []
        self.hidden_pins = []
        self.hidden_dialogs = []
        self.overlay = None
        self.last_capture = None
        self.capturing = False
        self.quitting = False
        DATA.mkdir(parents=True, exist_ok=True)
        self.settings_file = DATA / "settings.json"
        self.settings_store = SettingsStore(self.settings_file)
        self.preferences = self.settings_store.load()
        self.capture_store = CaptureStore(DATA / "captures")
        self.runner = TaskRunner(self)
        self.thumbnail_cache = OrderedDict()
        self.thumbnail_pending = set()
        self.history_items: dict[str, QListWidgetItem] = {}
        self.history_generation = 0
        container = QWidget()
        self.setCentralWidget(container)
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(190)
        sidebar = QVBoxLayout(side)
        sidebar.setContentsMargins(18, 30, 18, 25)
        sidebar.setSpacing(8)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icon().pixmap(38, 38))
        brand.addWidget(logo)
        name = QLabel("轻映")
        name.setStyleSheet("font-size:24px;font-weight:700;")
        brand.addWidget(name)
        brand.addStretch()
        sidebar.addLayout(brand)
        subtitle = QLabel("Q I N G C A P T U R E")
        subtitle.setObjectName("muted")
        sidebar.addWidget(subtitle)
        sidebar.addSpacing(37)
        self.pages = QStackedWidget()
        self.nav = QButtonGroup(self)
        for n, (label, symbol) in enumerate(
            [("截图工作台", "capture"), ("截图记录", "history"), ("偏好设置", "settings")]
        ):
            b = button("  " + label)
            b.setIcon(icon(symbol, "#72907c", 24))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda checked=False, i=n: self.pages.setCurrentIndex(i))
            self.nav.addButton(b, n)
            sidebar.addWidget(b)
        self.nav.button(0).setChecked(True)
        sidebar.addStretch()
        sidebar.addWidget(QLabel("随手一截\n让专注继续。"))
        footer = QLabel(f"WINDOWS  ·  v{__version__}")
        footer.setObjectName("muted")
        sidebar.addSpacing(15)
        sidebar.addWidget(footer)
        outer.addWidget(side)
        outer.addWidget(self.pages, 1)
        self.build_workspace()
        self.build_history()
        self.build_settings()
        self.pages.currentChanged.connect(
            lambda index: QTimer.singleShot(0, self.load_visible_history) if index == 1 else None
        )
        self.history.verticalScrollBar().valueChanged.connect(self.load_visible_history)
        self.setup_tray()
        self.hotkey = Hotkey(self.start_capture, self.preferences.hotkey)
        QApplication.instance().installNativeEventFilter(self.hotkey)
        QApplication.instance().aboutToQuit.connect(self.hotkey.unregister)
        self.update_hotkey_labels()
        self.refresh_history()

    def card(self):
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    def page_layout(self, title, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 29, 32, 26)
        layout.setSpacing(18)
        heading = QLabel(title)
        heading.setObjectName("heading")
        layout.addWidget(heading)
        muted = QLabel(subtitle)
        muted.setObjectName("muted")
        muted.setWordWrap(True)
        layout.addWidget(muted)
        self.pages.addWidget(page)
        return layout

    def build_workspace(self):
        layout = self.page_layout(
            "每一截，都恰到好处。", "轻巧的桌面截图工具，让捕捉、表达和理解一气呵成。"
        )
        hero = self.card()
        row = QHBoxLayout(hero)
        row.setContentsMargins(22, 20, 22, 20)
        text = QVBoxLayout()
        title = QLabel("从这里，捕捉屏幕")
        title.setObjectName("title")
        text.addWidget(title)
        self.hotkey_label = QLabel("全局快捷键   Ctrl + Alt + A")
        self.hotkey_label.setObjectName("muted")
        text.addWidget(self.hotkey_label)
        row.addLayout(text, 1)
        capture = button("  开始截图", self.start_capture, True)
        capture.setIcon(icon("capture", "white"))
        capture.setMinimumHeight(46)
        capture.setMinimumWidth(150)
        row.addWidget(capture)
        layout.addWidget(hero)
        content = QHBoxLayout()
        content.setSpacing(18)
        preview_card = self.card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 17, 18, 17)
        label_row = QHBoxLayout()
        label = QLabel("最近捕捉")
        label.setObjectName("title")
        label_row.addWidget(label)
        label_row.addStretch()
        self.capture_info = QLabel("等待第一张截图")
        self.capture_info.setObjectName("muted")
        label_row.addWidget(self.capture_info)
        preview_layout.addLayout(label_row)
        self.preview = Preview()
        preview_layout.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        self.copy_button = button("复制", self.copy_latest)
        self.pin_button = button("贴到桌面", self.pin_latest)
        self.translate_image_button = button("识字 / 翻译", self.translate_latest)
        for b in [self.copy_button, self.pin_button, self.translate_image_button]:
            b.setEnabled(False)
            actions.addWidget(b)
        preview_layout.addLayout(actions)
        content.addWidget(preview_card, 1)
        quick = self.card()
        quick.setFixedWidth(218)
        ql = QVBoxLayout(quick)
        ql.setContentsMargins(20, 22, 20, 20)
        ql.setSpacing(13)
        qtitle = QLabel("不止于截图")
        qtitle.setObjectName("title")
        ql.addWidget(qtitle)
        for symbol, title, detail in [
            ("pin", "贴在眼前", "参考图片置顶悬浮\n拖动、缩放，随时对照"),
            ("translate", "读懂屏幕", "本地提取图片文字\n支持多种语言互译"),
        ]:
            label = QLabel()
            label.setPixmap(icon(symbol).pixmap(28, 28))
            ql.addWidget(label)
            ql.addWidget(QLabel(title))
            detail_label = QLabel(detail)
            detail_label.setObjectName("muted")
            detail_label.setWordWrap(True)
            ql.addWidget(detail_label)
        ql.addStretch()
        ql.addWidget(button("从剪贴板贴图", self.pin_clipboard))
        ql.addWidget(button("文字翻译", self.translate_clipboard))
        content.addWidget(quick)
        layout.addLayout(content, 1)
        tools = QLabel(
            "框选之后   □ 矩形    ○ 圆形    ↗ 箭头    ✎ 画笔    T 文字    ▦ 马赛克    ↶ 撤销"
        )
        tools.setObjectName("muted")
        tools.setWordWrap(True)
        layout.addWidget(tools)
        self.status = QLabel("准备就绪 · Esc 取消截图，Enter 完成并复制")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def build_history(self):
        layout = self.page_layout("截图记录", "保存在本机的捕捉，随时找回、复制或重新贴图。")
        self.history = QListWidget()
        self.history.setIconSize(QSize(180, 100))
        self.history.setSpacing(7)
        self.history.setStyleSheet(
            "QListWidget { background: white; border: 1px solid #e2e9e4; border-radius: 12px; padding: 12px; } QListWidget::item { padding: 10px; border-radius: 6px; } QListWidget::item:selected { background: #e9f8ee; color: #204a30; }"
        )
        self.history.itemDoubleClicked.connect(self.pin_history)
        layout.addWidget(self.history, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("刷新", self.refresh_history))
        actions.addWidget(button("打开保存目录", self.open_folder))
        actions.addStretch()
        actions.addWidget(button("复制选中截图", self.copy_history))
        actions.addWidget(
            button("贴图", lambda: self.pin_history(self.history.currentItem()), True)
        )
        layout.addLayout(actions)

    def build_settings(self):
        layout = self.page_layout("偏好设置", "保持轻巧，也照顾你的习惯。")
        card = self.card()
        form = QVBoxLayout(card)
        form.setContentsMargins(25, 22, 25, 22)
        form.setSpacing(16)
        self.remember = CheckBox("自动将完成的截图保存在本机，并显示在截图记录中")
        self.remember.setChecked(self.preferences.remember)
        self.remember.toggled.connect(self.save_settings)
        form.addWidget(self.remember)
        self.hide_to_tray = CheckBox("关闭主窗口时留在系统托盘，继续响应截图快捷键")
        self.hide_to_tray.setChecked(self.preferences.hide_to_tray)
        self.hide_to_tray.toggled.connect(self.save_settings)
        form.addWidget(self.hide_to_tray)

        shortcut_header = QHBoxLayout()
        shortcut_title = QLabel("快捷键设置（点击输入框后直接按下组合键）")
        shortcut_title.setStyleSheet("font-weight: 600; color: #24332c;")
        shortcut_header.addWidget(shortcut_title)
        shortcut_header.addStretch()
        self.shortcut_status = QLabel("")
        self.shortcut_status.setObjectName("muted")
        shortcut_header.addWidget(self.shortcut_status)
        reset_btn = button("恢复默认快捷键", self.reset_shortcuts)
        shortcut_header.addWidget(reset_btn)
        form.addLayout(shortcut_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        self.hotkey_input = ShortcutInput(self.preferences.hotkey)
        self.copy_shortcut_input = ShortcutInput(self.preferences.copy_shortcut)
        self.pin_shortcut_input = ShortcutInput(self.preferences.pin_shortcut)
        self.save_shortcut_input = ShortcutInput(self.preferences.save_shortcut)
        self.hotkey_input.shortcut_changed.connect(self.on_hotkey_changed)
        self.copy_shortcut_input.shortcut_changed.connect(
            lambda value: self.on_action_shortcut_changed("copy_shortcut", value)
        )
        self.pin_shortcut_input.shortcut_changed.connect(
            lambda value: self.on_action_shortcut_changed("pin_shortcut", value)
        )
        self.save_shortcut_input.shortcut_changed.connect(
            lambda value: self.on_action_shortcut_changed("save_shortcut", value)
        )
        for index, (title_text, widget) in enumerate(
            [
                ("全局开始截图", self.hotkey_input),
                ("完成并复制截图", self.copy_shortcut_input),
                ("完成并贴到桌面", self.pin_shortcut_input),
                ("保存截图文件", self.save_shortcut_input),
            ]
        ):
            row_idx, col_idx = divmod(index, 2)
            item_label = QLabel(title_text)
            item_label.setStyleSheet("color: #495a50;")
            grid.addWidget(item_label, row_idx, col_idx * 2)
            grid.addWidget(widget, row_idx, col_idx * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        form.addLayout(grid)

        label = QLabel(
            "贴图：拖动移动，滚轮缩放，Ctrl + 滚轮调整透明度；双击或 Esc 关闭贴图，右键可保存、复制、识字与翻译。\n"
            "翻译：本地 Windows OCR + MyMemory 在线翻译；自动判断适用于中、英、日、韩，其他语言请手动选择。"
        )
        label.setWordWrap(True)
        label.setStyleSheet("color:#708276;line-height:1.5;")
        form.addWidget(label)
        directory = QLabel("本地数据目录：\n" + str(DATA))
        directory.setTextInteractionFlags(Qt.TextSelectableByMouse)
        directory.setWordWrap(True)
        directory.setObjectName("muted")
        form.addWidget(directory)
        form.addWidget(button("打开数据目录", self.open_folder))
        layout.addWidget(card)
        layout.addStretch()

    def on_hotkey_changed(self, shortcut: str) -> bool:
        if self.hotkey.rebind(shortcut):
            self.update_hotkey_labels()
            self.save_settings()
            return True
        self.hotkey_input.set_shortcut(self.hotkey.shortcut)
        attempted = format_shortcut(shortcut)
        if self.hotkey.registered:
            restored = format_shortcut(self.hotkey.shortcut)
            self.hotkey_label.setText(f"全局快捷键   {restored}")
            self.shortcut_status.setText(f"{attempted} 已被占用，已恢复原快捷键 {restored}")
        else:
            self.hotkey_label.setText(f"{attempted} 已被占用，可点击按钮截图或前往偏好设置修改")
            self.shortcut_status.setText(f"{attempted} 已被其他软件占用，请更换组合键")
        self.shortcut_status.setStyleSheet("color: #d3554d; font-size: 12px;")
        self.tray.setToolTip(f"轻映 · {self.hotkey.shortcut} 截图")
        self.tray_capture_action.setText(f"开始截图  {self.hotkey.shortcut}")
        return False

    def on_action_shortcut_changed(self, field: str, value: str) -> None:
        inputs = {
            "copy_shortcut": ("完成并复制截图", self.copy_shortcut_input),
            "pin_shortcut": ("完成并贴到桌面", self.pin_shortcut_input),
            "save_shortcut": ("保存截图文件", self.save_shortcut_input),
        }
        if value == "Ctrl+Z":
            inputs[field][1].set_shortcut(getattr(self.preferences, field))
            self.shortcut_status.setText(f"{format_shortcut(value)} 为内置撤销快捷键，已恢复原设置")
            self.shortcut_status.setStyleSheet("color: #d3554d; font-size: 12px;")
            return
        for other_field, (label_text, _widget) in inputs.items():
            if other_field != field and getattr(self.preferences, other_field) == value:
                inputs[field][1].set_shortcut(getattr(self.preferences, field))
                self.shortcut_status.setText(
                    f"{format_shortcut(value)} 与「{label_text}」冲突，已恢复原设置"
                )
                self.shortcut_status.setStyleSheet("color: #d3554d; font-size: 12px;")
                return
        self.shortcut_status.setText(f"已更新「{inputs[field][0]}」为 {format_shortcut(value)}")
        self.shortcut_status.setStyleSheet("color: #079c4e; font-size: 12px;")
        self.save_settings()

    def reset_shortcuts(self) -> None:
        defaults = Preferences()
        self.hotkey_input.set_shortcut(defaults.hotkey)
        self.copy_shortcut_input.set_shortcut(defaults.copy_shortcut)
        self.pin_shortcut_input.set_shortcut(defaults.pin_shortcut)
        self.save_shortcut_input.set_shortcut(defaults.save_shortcut)
        if not self.on_hotkey_changed(defaults.hotkey):
            # Other shortcuts still reset, while the global input reflects the rollback.
            self.save_settings()

    def update_hotkey_labels(self) -> None:
        display = format_shortcut(self.hotkey.shortcut)
        if self.hotkey.registered:
            self.hotkey_label.setText(f"全局快捷键   {display}")
            self.shortcut_status.setText(f"全局快捷键 {display} 已生效")
            self.shortcut_status.setStyleSheet("color: #079c4e; font-size: 12px;")
        else:
            self.hotkey_label.setText(f"{display} 已被占用，可点击按钮截图或前往偏好设置修改")
            self.shortcut_status.setText(f"{display} 已被其他软件占用，请更换组合键")
            self.shortcut_status.setStyleSheet("color: #d3554d; font-size: 12px;")
        self.tray.setToolTip(f"轻映 · {self.hotkey.shortcut} 截图")
        self.tray_capture_action.setText(f"开始截图  {self.hotkey.shortcut}")

    def save_settings(self, *_args) -> None:
        self.preferences = Preferences(
            remember=self.remember.isChecked(),
            hide_to_tray=self.hide_to_tray.isChecked(),
            hotkey=self.hotkey_input.shortcut(),
            copy_shortcut=self.copy_shortcut_input.shortcut(),
            pin_shortcut=self.pin_shortcut_input.shortcut(),
            save_shortcut=self.save_shortcut_input.shortcut(),
        )
        try:
            self.settings_store.save(self.preferences)
        except OSError:
            QMessageBox.warning(
                self, "设置未保存", "数据目录不可写，本次设置仅在当前运行期间生效。"
            )

    def setup_tray(self):
        self.tray = QSystemTrayIcon(icon(), self)
        self.tray.setToolTip(f"轻映 · {self.preferences.hotkey} 截图")
        menu = QMenu()
        self.tray_capture_action = menu.addAction(
            f"开始截图  {self.preferences.hotkey}", self.start_capture
        )
        menu.addAction("显示工作台", self.show_main)
        menu.addAction("从剪贴板贴图", self.pin_clipboard)
        menu.addSeparator()
        menu.addAction("关闭所有贴图", self.close_pins)
        menu.addAction("退出轻映", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_main() if reason == QSystemTrayIcon.DoubleClick else None
        )
        self.tray.show()

    def show_main(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def start_capture(self):
        if self.capturing or any(d.busy for d in self.dialogs):
            return
        self.capturing = True
        self.was_visible = self.isVisible()
        self.hidden_pins = [p for p in self.pins if p.isVisible()]
        self.hidden_dialogs = [d for d in self.dialogs if d.isVisible()]
        for pin in self.hidden_pins:
            pin.hide()
        for dialog in self.hidden_dialogs:
            dialog.hide()
        self.hide()
        QTimer.singleShot(220, self.capture_desktop)

    def capture_desktop(self):
        try:
            canvas, bounds = desktop_snapshot()
            self.overlay = CaptureOverlay(canvas, bounds, preferences=self.preferences)
            self.overlay.completed.connect(self.capture_done)
            self.overlay.canceled.connect(self.capture_canceled)
            self.overlay.show()
            self.overlay.raise_()
            self.overlay.activateWindow()
        except Exception as exc:
            self.capture_canceled()
            QMessageBox.warning(self, "截图失败", str(exc))

    def restore_after_capture(self, restore_main: bool = False):
        self.capturing = False
        for pin in self.hidden_pins:
            if pin in self.pins:
                pin.show()
        for dialog in self.hidden_dialogs:
            if dialog in self.dialogs:
                dialog.show()
        self.hidden_pins = []
        self.hidden_dialogs = []
        if restore_main and self.was_visible:
            self.show_main()

    def capture_canceled(self):
        self.restore_after_capture(restore_main=False)
        self.status.setText("已取消截图。")

    def capture_done(self, image, action, position):
        # Delay secondary windows until the full-screen overlay has closed.
        QTimer.singleShot(0, lambda: self.consume_capture(image, action, position))

    def consume_capture(self, image, action, position):
        self.restore_after_capture(restore_main=False)
        self.last_capture = image
        self.preview.pixmap = image
        self.preview.update()
        self.capture_info.setText(f"{image.width()} × {image.height()}")
        for b in [self.copy_button, self.pin_button, self.translate_image_button]:
            b.setEnabled(True)
        record_errors = []

        def record_failed(message):
            record_errors.append(message)
            self.status.setText("截图记录未保存：" + message)

        if self.remember.isChecked():
            snapshot = image.toImage()
            accepted = self.runner.submit(
                lambda: self.capture_store.save(snapshot),
                lambda path: self.refresh_history(),
                record_failed,
            )
            if not accepted and not record_errors:
                record_failed("后台任务较多，请稍后重试。")
        self.status.setText("截图完成。")
        if action == "copy":
            self.copy_latest()
        elif action == "pin":
            self.create_pin(image, position)
        elif action == "translate":
            self.open_translation(image)
        elif action == "save":
            path, _ = QFileDialog.getSaveFileName(
                self, "保存截图", str(ROOT / "轻映.png"), "PNG 图片 (*.png)"
            )
            if path:
                snapshot = image.toImage()
                self.status.setText("正在保存截图…")
                self.runner.submit(
                    lambda: save_png(snapshot, path),
                    lambda saved: self.status.setText("已保存至 " + saved),
                    lambda message: self.status.setText("保存失败：" + message),
                )
        if record_errors:
            self.status.setText(self.status.text() + "；截图记录未保存：" + record_errors[-1])

    def copy_latest(self):
        if self.last_capture is not None:
            QApplication.clipboard().setPixmap(self.last_capture)
            self.status.setText("截图已复制到剪贴板。")

    def pin_latest(self):
        if self.last_capture is not None:
            self.create_pin(self.last_capture)

    def translate_latest(self):
        if self.last_capture is not None:
            self.open_translation(self.last_capture)

    def create_pin(self, image, position=None):
        pin = PinWindow(image, position, runner=self.runner)
        pin.translate_requested.connect(self.open_translation)
        pin.closed.connect(lambda obj: self.pins.remove(obj) if obj in self.pins else None)
        self.pins.append(pin)
        pin.show()
        pin.raise_()
        pin.activateWindow()
        self.status.setText("贴图已置顶 · 滚轮缩放，右键查看更多操作。")
        return pin

    def pin_clipboard(self):
        pixmap = QApplication.clipboard().pixmap()
        if pixmap.isNull():
            QMessageBox.information(self, "剪贴板没有图片", "请先复制一张图片，或使用截图功能。")
        else:
            self.create_pin(pixmap)

    def translate_clipboard(self):
        self.open_translation(text=QApplication.clipboard().text())

    def open_translation(self, image=None, text=""):
        if self.dialogs:
            dialog = self.dialogs[0]
            if image is not None or text:
                dialog.load_content(image, text)
            dialog.showNormal()
            dialog.raise_()
            dialog.activateWindow()
            return dialog
        dialog = TranslationDialog(image, text, self, runner=self.runner)
        self.dialogs.append(dialog)
        dialog.finished.connect(
            lambda result: self.dialogs.remove(dialog) if dialog in self.dialogs else None
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def refresh_history(self) -> None:
        self.history_generation += 1
        generation = self.history_generation
        self.runner.submit(
            self.capture_store.recent,
            lambda files: (
                self.populate_history(files) if generation == self.history_generation else None
            ),
            lambda message: self.status.setText("无法读取截图记录：" + message),
        )

    def populate_history(self, files: list[Path]) -> None:
        self.history.clear()
        self.history_items.clear()
        placeholder = icon("capture", "#a6bbae")
        for path in files:
            key = str(path)
            item = QListWidgetItem(placeholder, self.history_text(path))
            item.setData(Qt.UserRole, key)
            self.history.addItem(item)
            self.history_items[key] = item
        self.history.setToolTip("" if files else "暂无截图记录。完成截图后会自动保存在这里。")
        QTimer.singleShot(0, self.load_visible_history)

    @staticmethod
    def history_text(path: Path, dimensions=None) -> str:
        description = f"{dimensions.width()} × {dimensions.height()}" if dimensions else "PNG 图片"
        return f"{path.stem}\n{description}  ·  双击贴图"

    def load_visible_history(self, *_args) -> None:
        if not self.history.isVisible():
            return
        viewport = self.history.viewport().rect()
        for index in range(self.history.count()):
            item = self.history.item(index)
            if not self.history.visualItemRect(item).intersects(viewport):
                continue
            path = item.data(Qt.UserRole)
            if item.data(Qt.UserRole + 1) or path in self.thumbnail_pending:
                continue
            if path in self.thumbnail_cache:
                self.apply_thumbnail(path, self.thumbnail_cache[path])
                continue
            if len(self.thumbnail_pending) >= 2:
                break
            self.thumbnail_pending.add(path)
            self.runner.submit(
                lambda name=path: read_thumbnail(Path(name)),
                lambda result, name=path: self.thumbnail_ready(name, result),
                lambda message, name=path: self.thumbnail_failed(name),
            )

    def thumbnail_ready(self, path: str, result) -> None:
        self.thumbnail_pending.discard(path)
        self.thumbnail_cache[path] = result
        self.thumbnail_cache.move_to_end(path)
        while len(self.thumbnail_cache) > 64:
            self.thumbnail_cache.popitem(last=False)
        self.apply_thumbnail(path, result)
        QTimer.singleShot(0, self.load_visible_history)

    def apply_thumbnail(self, path: str, result) -> None:
        image, dimensions = result
        item = self.history_items.get(path)
        if item is not None:
            item.setIcon(QIcon(QPixmap.fromImage(image)))
            item.setText(self.history_text(Path(path), dimensions))
            item.setData(Qt.UserRole + 1, True)

    def thumbnail_failed(self, path: str) -> None:
        self.thumbnail_pending.discard(path)
        item = self.history_items.get(path)
        if item is not None:
            item.setData(Qt.UserRole + 1, True)
            item.setToolTip("图片无法读取，原文件保留。")
        QTimer.singleShot(0, self.load_visible_history)

    def pin_history(self, item):
        if item:
            image = QPixmap(item.data(Qt.UserRole))
            if not image.isNull():
                self.create_pin(image)

    def copy_history(self):
        item = self.history.currentItem()
        if item:
            QApplication.clipboard().setPixmap(QPixmap(item.data(Qt.UserRole)))

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA)))

    def close_pins(self):
        for pin in list(self.pins):
            pin.close()

    def quit_app(self):
        if self.runner.pending:
            self.show_main()
            self.status.setText("后台操作正在处理，请等待结束后退出。")
            return
        self.quitting = True
        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.finish("cancel")
        self.close_pins()
        self.tray.hide()
        self.hotkey.unregister()
        QApplication.quit()

    def closeEvent(self, event):
        if (
            self.hide_to_tray.isChecked()
            and QSystemTrayIcon.isSystemTrayAvailable()
            and not self.quitting
        ):
            self.hide()
            event.ignore()
        elif any(d.busy for d in self.dialogs):
            event.ignore()
        else:
            self.quit_app()
            event.accept()
