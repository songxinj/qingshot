"""Reproducible local baselines. Results are measurements, not universal limits."""

import json
import os
import statistics
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QINGSHOT_DATA"] = str(PROJECT / "test-artifacts" / f"benchmark-{time.time_ns()}")

from PySide6.QtCore import QPointF, QRect
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qingshot.main_window import MainWindow
from qingshot.overlay import CaptureOverlay
from qingshot.paths import DATA
from qingshot.storage import CaptureStore


def measure(function, repeats=20):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        function()
        samples.append((time.perf_counter() - start) * 1000)
    return {"median_ms": round(statistics.median(samples), 3), "max_ms": round(max(samples), 3)}


def main():
    app = QApplication([])
    folder = DATA / "captures"
    folder.mkdir(parents=True)
    for index in range(10000):
        (folder / f"20260101_000000_{index:06d}.png").touch()
    store = CaptureStore(folder)
    canvas = QPixmap(2400, 1350)
    canvas.setDevicePixelRatio(1.25)
    canvas.fill(QColor("#f4f7f5"))
    overlay = CaptureOverlay(canvas, QRect(0, 0, 1920, 1080))
    overlay.selection = QRect(0, 0, 1920, 1080)
    overlay.items = [
        {
            "kind": "arrow",
            "points": [QPointF(100, 100), QPointF(900, 600)],
            "color": QColor("red"),
            "width": 3,
        }
    ]
    window = MainWindow()
    while window.runner.pending:
        QTest.qWait(10)
    recent_files = store.recent()
    result = {
        "history_10000_to_200": measure(store.recent),
        "history_widget_refresh_200_without_decode": measure(
            lambda: window.populate_history(recent_files)
        ),
        "export_2400x1350_with_arrow": measure(overlay.result),
        "worker_concurrency_limit": window.runner.pool.maxThreadCount(),
        "thumbnail_cache_limit": 64,
        "platform": sys.platform,
        "python": sys.version.split()[0],
    }
    window.hotkey.unregister()
    window.tray.hide()
    overlay.close()
    (DATA / "benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"results": result, "report": str(DATA / "benchmark.json")}), flush=True)
    app.processEvents()


if __name__ == "__main__":
    main()
