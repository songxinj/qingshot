"""Atomic ownership for the existing local-socket single-instance protocol."""

import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QLockFile, QThread
from PySide6.QtNetwork import QLocalSocket


def acquire_instance_lock(server_name: str, path: Path | None = None) -> QLockFile | None:
    if path is None:
        identity = hashlib.sha256(f"{Path.home()}:{server_name}".encode()).hexdigest()
        path = Path(tempfile.gettempdir()) / "QingCapture" / f"{identity}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)
    return lock if lock.tryLock(0) else None


def activate_existing(server_name: str, timeout_ms: int = 350, *, retry: bool = False) -> bool:
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < timeout_ms:
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(min(100, max(1, timeout_ms - timer.elapsed()))):
            socket.write(b"show")
            socket.waitForBytesWritten(350)
            socket.disconnectFromServer()
            return True
        if not retry:
            return False
        QThread.msleep(10)
    return False
