"""Live desktop chain using only a generated text fixture, never personal content.

python test_desktop.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
if __name__ == "__main__":
    os.environ["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["QINGSHOT_DATA"] = str(
        Path(__file__).resolve().parents[1]
        / "test-artifacts"
        / datetime.now().strftime("desktop-%Y%m%d-%H%M%S-%f")
    )

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QVBoxLayout, QWidget

from qingshot.main_window import MainWindow
from qingshot.paths import DATA
from qingshot.ui import STYLE


def until(predicate, seconds=35):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        if predicate():
            return
        # Release Python's GIL between event pumps so OCR preprocessing can run.
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for desktop operation")


def main():
    app = QApplication([])
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    app.processEvents()
    DATA.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(DATA / "workspace.png"))
    fixture = QWidget(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    fixture.setWindowTitle("QingShot test fixture")
    fixture.setStyleSheet("background: white; color: black;")
    fixture.resize(700, 200)
    screen = app.primaryScreen().availableGeometry()
    fixture.move(screen.center() - QPoint(350, 100))
    layout = QVBoxLayout(fixture)
    label = QLabel("Hello world 12345")
    label.setStyleSheet("font-family: Arial; font-size: 38px; color: black;")
    label.setAlignment(Qt.AlignCenter)
    layout.addWidget(label)
    fixture.show()
    fixture.raise_()
    QTest.qWait(200)
    raw = app.primaryScreen().grabWindow(0).toImage()
    sample = [
        raw.pixelColor(x, y).name()
        for x in range(0, raw.width(), max(1, raw.width() // 16))
        for y in range(0, raw.height(), max(1, raw.height() // 12))
    ]
    print(
        json.dumps(
            {
                "screen_sample_colors": sorted(set(sample)),
                "fixture_visible": fixture.isVisible(),
                "platform": app.platformName(),
            }
        ),
        flush=True,
    )
    fixture_mode = "--fixture" in sys.argv
    if set(sample) == {"#000000"} and not fixture_mode:
        fixture.close()
        window.hotkey.unregister()
        window.tray.hide()
        window.hide()
        print(
            json.dumps(
                {
                    "desktop_capture": "SKIP",
                    "reason": "Desktop capture is all black in this execution environment",
                }
            ),
            flush=True,
        )
        return
    try:
        if fixture_mode:
            bounds = app.primaryScreen().geometry()
            ratio = app.primaryScreen().devicePixelRatio()
            snapshot = QPixmap(round(bounds.width() * ratio), round(bounds.height() * ratio))
            snapshot.setDevicePixelRatio(ratio)
            snapshot.fill(Qt.white)
            painter = QPainter(snapshot)
            painter.drawPixmap(fixture.pos() - bounds.topLeft(), fixture.grab())
            painter.end()
            with patch("qingshot.main_window.desktop_snapshot", return_value=(snapshot, bounds)):
                window.start_capture()
                until(lambda: window.overlay is not None and window.overlay.isVisible())
        else:
            window.start_capture()
            until(lambda: window.overlay is not None and window.overlay.isVisible())
        overlay = window.overlay
        print(json.dumps({"stage": "overlay_ready"}), flush=True)
        selected = (
            fixture.geometry().adjusted(6, 6, -6, -6).translated(-overlay.geometry().topLeft())
        )
        QTest.mousePress(overlay, Qt.LeftButton, pos=selected.topLeft())
        QTest.mouseMove(overlay, selected.bottomRight(), 40)
        QTest.mouseRelease(overlay, Qt.LeftButton, pos=selected.bottomRight())
        assert overlay.selection.width() == selected.width()
        print(json.dumps({"stage": "selection_ready"}), flush=True)
        buttons = [
            b for b in overlay.toolbar.findChildren(QToolButton) if b.objectName() == "translate"
        ]
        assert len(buttons) == 1
        QTest.mouseClick(buttons[0], Qt.LeftButton)
        until(lambda: bool(window.dialogs))
        dialog = window.dialogs[0]
        print(json.dumps({"stage": "ocr_open"}), flush=True)
        until(
            lambda: (
                dialog.busy
                or bool(dialog.original.toPlainText())
                or dialog.status.text().startswith(("操作失败", "没有识别", "本地识字完成"))
            )
        )
        until(lambda: not dialog.busy)
        print(
            json.dumps(
                {
                    "stage": "ocr_done",
                    "text": dialog.original.toPlainText(),
                    "status": dialog.status.text(),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        assert "12345" in dialog.original.toPlainText(), dialog.status.text()
        assert "world" in dialog.original.toPlainText().lower(), dialog.original.toPlainText()
        recognized_text = dialog.original.toPlainText()
        # Correct the known OCR l/1 ambiguity through the editable source field.
        dialog.original.setPlainText("Hello world.\nPlease save this image.\n说明")
        dialog.target.setCurrentIndex(dialog.target.findData("zh-CN"))
        QTest.mouseClick(dialog.translate_button, Qt.LeftButton)
        until(lambda: not dialog.busy)
        print(
            json.dumps(
                {"stage": "translation_done", "status": dialog.status.text()},
                ensure_ascii=False,
            ),
            flush=True,
        )
        assert dialog.result.toPlainText(), dialog.status.text()
        assert any("\u4e00" <= char <= "\u9fff" for char in dialog.result.toPlainText()), (
            dialog.result.toPlainText()
        )
        dialog.grab().save(str(DATA / "translation.png"))
        translated_text = dialog.result.toPlainText()
        assert len(translated_text.splitlines()) == 3, translated_text
        assert translated_text.splitlines()[1] != "Please save this image.", translated_text
        dialog.close()
        app.processEvents()
        window.pin_latest()
        app.processEvents()
        assert len(window.pins) == 1 and window.pins[0].isVisible()
        pin = window.pins[0]
        old = pin.pos()
        QTest.mousePress(pin, Qt.LeftButton, pos=QPoint(30, 30))
        QTest.mouseMove(pin, QPoint(90, 70), 40)
        QTest.mouseRelease(pin, Qt.LeftButton, pos=QPoint(90, 70))
        assert pin.pos() != old
        QTest.keyClick(pin, Qt.Key_C, Qt.ControlModifier)
        assert not app.clipboard().pixmap().isNull()
        QTest.keyClick(pin, Qt.Key_Escape)
        assert not window.pins
        window.remember.setChecked(False)
        # A fresh process reads the injected data path and the saved setting.
        code = """
import json
import time
from PySide6.QtWidgets import QApplication
from qingshot.main_window import MainWindow
from qingshot.paths import DATA
application = QApplication([])
window = MainWindow()
while window.runner.pending:
    application.processEvents()
    time.sleep(0.01)
print(json.dumps({'data': str(DATA), 'remember': window.remember.isChecked()}))
window.hotkey.unregister()
window.tray.hide()
"""
        child = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert child.returncode == 0, child.stderr
        state = json.loads(child.stdout.strip())
        assert state["data"] == str(DATA) and state["remember"] is False
        assert window.history.count() == 1
        window.last_capture.save(str(DATA / "actual-capture.png"))
        result = {
            "desktop_capture": "NOT_TESTED" if fixture_mode else "PASS",
            "capture_source": "rendered fixture" if fixture_mode else "live desktop",
            "local_ocr": "PASS",
            "recognized_text": recognized_text,
            "translated_text": translated_text,
            "http_translation": "PASS",
            "pin_drag_copy_close": "PASS",
            "restart_config": "PASS",
            "physical_size": [window.last_capture.width(), window.last_capture.height()],
            "artifacts": str(DATA),
        }
        (DATA / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        fixture.close()
        window.close_pins()
        for dialog in list(window.dialogs):
            if not dialog.busy:
                dialog.close()
        window.hotkey.unregister()
        window.tray.hide()
        window.hide()


if __name__ == "__main__":
    main()
