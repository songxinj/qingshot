"""QingShot / 轻映 — a small native Windows screenshot workspace."""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
)
from shiboken6 import isValid

from .images import png_bytes
from .ocr import recognize
from .translation import LANGUAGES, translate
from .ui import button
from .workers import TaskRunner


class TranslationDialog(QDialog):
    def __init__(self, pixmap=None, text="", parent=None, runner: TaskRunner | None = None):
        super().__init__(parent)
        self.setWindowTitle("轻映 · 识字与翻译")
        self.resize(900, 620)
        self.pixmap = QPixmap(pixmap) if pixmap is not None else None
        self.busy = False
        self.runner = runner if runner is not None else TaskRunner(self)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        title = QLabel("文字翻译")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #252a27;")
        layout.addWidget(title)
        hint = QLabel(
            "本地识字不联网。点击翻译后，原文先发送至 Google，连接失败时再发送至 MyMemory；图片始终留在本机。"
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        languages = QHBoxLayout()
        self.source = QComboBox()
        self.source.addItem("自动判断（中 / 英 / 日 / 韩）", "auto")
        self.target = QComboBox()
        for name, value in LANGUAGES.items():
            self.source.addItem(name, value)
            self.target.addItem(name, value)
        languages.addWidget(QLabel("原文语言"))
        languages.addWidget(self.source, 1)
        languages.addSpacing(25)
        languages.addWidget(QLabel("译文语言"))
        languages.addWidget(self.target, 1)
        layout.addLayout(languages)
        self.splitter = QSplitter(Qt.Horizontal)
        self.original = QTextEdit()
        self.original.setPlaceholderText("识别出的原文会出现在这里，也可以粘贴文字并编辑。")
        self.original.setPlainText(text)
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("译文会出现在这里。")
        self.splitter.addWidget(self.original)
        self.splitter.addWidget(self.result)
        layout.addWidget(self.splitter, 1)
        self.status = QLabel(
            "可直接粘贴文字。自动识字使用 Windows 当前语言；选定原文语言后可重新识字。"
        )
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.ocr_button = button("重新识字", self.ocr)
        self.ocr_button.setEnabled(self.pixmap is not None)
        actions.addWidget(self.ocr_button)
        self.paste_button = button("粘贴文字", self.paste_text)
        actions.addWidget(self.paste_button)
        actions.addStretch()
        actions.addWidget(
            button(
                "复制原文", lambda: QApplication.clipboard().setText(self.original.toPlainText())
            )
        )
        actions.addWidget(button("复制译文", self.copy_result))
        self.translate_button = button("翻译 →", self.do_translate, True)
        actions.addWidget(self.translate_button)
        layout.addLayout(actions)
        if self.pixmap is not None:
            QTimer.singleShot(100, self.ocr)

    def load_content(self, pixmap=None, text: str = "") -> None:
        if self.busy:
            self.status.setText("正在处理当前任务，请稍候再试。")
            return
        self.pixmap = QPixmap(pixmap) if pixmap is not None else None
        self.ocr_button.setEnabled(self.pixmap is not None)
        self.original.setPlainText(text)
        self.result.clear()
        if self.pixmap is not None:
            QTimer.singleShot(0, self.ocr)
        else:
            self.status.setText(
                "可直接粘贴文字。自动识字使用 Windows 当前语言；选定原文语言后可重新识字。"
            )

    def paste_text(self):
        self.original.setPlainText(QApplication.clipboard().text())

    def copy_result(self):
        QApplication.clipboard().setText(self.result.toPlainText())
        self.status.setText("译文已复制。")

    def run_task(self, function, callback, label, mode="translate"):
        if self.busy:
            return
        self.status.setText(label)
        self.status.setStyleSheet("color: #858d88;")
        self.translate_button.setEnabled(False)
        if mode == "translate":
            self.translate_button.setText("正在翻译…")
        elif mode == "ocr":
            self.ocr_button.setText("正在识字…")
        self.ocr_button.setEnabled(False)
        self.source.setEnabled(False)
        self.target.setEnabled(False)
        self.original.setReadOnly(True)
        self.paste_button.setEnabled(False)
        self.busy = True

        def finish(value, error=False):
            if not isValid(self):
                return
            self.busy = False
            self.translate_button.setText("翻译 →")
            self.ocr_button.setText("重新识字")
            self.translate_button.setEnabled(True)
            self.ocr_button.setEnabled(self.pixmap is not None)
            self.source.setEnabled(True)
            self.target.setEnabled(True)
            self.original.setReadOnly(False)
            self.paste_button.setEnabled(True)
            if error:
                self.status.setText("操作失败：" + value)
                self.status.setStyleSheet("color: #d3554d;")
            else:
                callback(value)

        self.runner.submit(function, finish, lambda message: finish(message, True))

    def ocr(self):
        if self.pixmap is None or self.busy:
            return
        image = self.pixmap.toImage()
        if max(image.width(), image.height()) > 2400:
            image = image.scaled(2400, 2400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        language = self.source.currentData()

        def done(text):
            self.original.setPlainText(text)
            self.status.setText(
                "本地识字完成。确认原文后，点击翻译。"
                if text.strip()
                else "没有识别到文字，请重新截取清晰的文字区域，或直接输入。"
            )

        self.run_task(
            lambda: recognize(png_bytes(image), language),
            done,
            "正在本机识别文字…",
            mode="ocr",
        )

    def do_translate(self):
        text, source, target = (
            self.original.toPlainText(),
            self.source.currentData(),
            self.target.currentData(),
        )
        if self.busy:
            return
        self.result.clear()

        def done(value):
            self.result.setPlainText(value)
            providers = getattr(value, "providers", ())
            self.status.setText(
                "翻译完成 · " + (" / ".join(providers) if providers else "在线翻译")
            )

        self.run_task(
            lambda: translate(text, source, target),
            done,
            "正在请求在线翻译…",
            mode="translate",
        )

    def done(self, result):
        if self.busy:
            self.status.setText("正在处理，请等待本次操作结束后关闭。")
            return
        super().done(result)

    def reject(self):
        self.done(QDialog.Rejected)

    def accept(self):
        self.done(QDialog.Accepted)

    def closeEvent(self, event):
        if self.busy:
            self.status.setText("正在处理，请等待本次操作结束后关闭。")
            event.ignore()
        else:
            super().closeEvent(event)
