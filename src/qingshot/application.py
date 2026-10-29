"""QingShot / 轻映 — a small native Windows screenshot workspace."""

from __future__ import annotations

import logging
import sys

from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from . import __version__
from .instance import acquire_instance_lock, activate_existing
from .main_window import MainWindow
from .paths import DATA
from .ui import STYLE

# Keep the legacy instance identity so an old running version is activated.
SERVER_NAME = "QingCapture.Desktop.v1"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QingShot")
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName("轻映")
    app.setOrganizationName("QingShot")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    server_name = SERVER_NAME
    if activate_existing(server_name):
        return 0
    instance_lock = acquire_instance_lock(server_name)
    if instance_lock is None:
        if activate_existing(server_name, 2000, retry=True):
            return 0
        QMessageBox.warning(None, "轻映", "已有轻映会话正在启动或退出，请稍后重试。")
        return 1
    # Keep compatibility with an older running version that has no ownership lock.
    if activate_existing(server_name, 50):
        instance_lock.unlock()
        return 0
    server = QLocalServer()
    if not server.listen(server_name):
        QLocalServer.removeServer(server_name)
        if not server.listen(server_name):
            QMessageBox.warning(None, "轻映", "无法创建应用会话，请关闭已有轻映进程后重试。")
            return 1
    DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(DATA / "app.log"), encoding="utf-8", level=logging.INFO)

    def exception_hook(kind, value, trace):
        logging.error("Unhandled exception", exc_info=(kind, value, trace))
        QMessageBox.critical(None, "轻映遇到问题", str(value) + "\n详情已记录至 data/app.log。")

    sys.excepthook = exception_hook
    window = MainWindow()

    def activate():
        connection = server.nextPendingConnection()
        if connection:
            connection.waitForReadyRead(100)
            connection.readAll()
            connection.disconnectFromServer()
            connection.deleteLater()
        window.show_main()

    server.newConnection.connect(activate)
    window.show()
    try:
        return app.exec()
    finally:
        server.close()
        instance_lock.unlock()
