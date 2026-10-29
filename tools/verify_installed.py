"""Smoke-test an installed wheel, including actual process activation and restart.

Run from the checkout with --package-dir pointing at a pip --target installation.
All configuration and instance names are isolated from the user's running app.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

CHILD = r"""
import json, sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from qingshot import __version__
from qingshot import application
from qingshot.main_window import MainWindow
from qingshot.paths import DATA

created = 0
class ObservedWindow(MainWindow):
    def __init__(self):
        global created
        created += 1
        super().__init__()
        print(json.dumps({
            'ready': True, 'version': __version__, 'data': str(DATA),
            'remember': self.preferences.remember,
            'copy_shortcut': self.preferences.copy_shortcut,
            'hotkey_registered': self.hotkey.registered,
        }), flush=True)
        QTimer.singleShot(int(sys.argv[2]), QApplication.instance().quit)
    def show_main(self):
        print(json.dumps({'activated': True}), flush=True)
        super().show_main()

application.SERVER_NAME = sys.argv[1]
application.MainWindow = ObservedWindow
application.QMessageBox.warning = lambda *args: print(json.dumps({'warning': str(args[-1])}), flush=True)
code = application.main()
print(json.dumps({'exit': code, 'created': created}), flush=True)
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    package_dir = args.package_dir.resolve()
    data_dir = args.data_dir.resolve()
    os.environ["QINGSHOT_DATA"] = str(data_dir)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, str(package_dir))

    from importlib.metadata import distribution

    from qingshot import __file__ as module_path
    from qingshot import __version__
    from qingshot.hotkey import qt_key_sequence
    from qingshot.storage import Preferences, SettingsStore

    assert Path(module_path).is_relative_to(package_dir), module_path
    metadata = distribution("qingshot")
    assert metadata.version == __version__
    assert any(req.startswith("rapidocr-onnxruntime") for req in metadata.requires)
    assert (Path(module_path).parent / "resources/ocr.ps1").is_file()
    assert qt_key_sequence("Ctrl+PageUp").toString() == "Ctrl+PgUp"
    SettingsStore(data_dir / "settings.json").save(
        Preferences(remember=False, hotkey="Ctrl+Alt+Shift+F11", copy_shortcut="Ctrl+PageUp")
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(package_dir),
        "PYTHONIOENCODING": "utf-8",
    }
    name = "QingShot.Verify." + uuid4().hex
    argv = [sys.executable, "-u", "-c", CHILD, name]
    owner = subprocess.Popen(
        [*argv, "1800"],
        cwd=package_dir,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    ready = json.loads(owner.stdout.readline())
    assert ready["ready"] and ready["remember"] is False, ready
    assert ready["copy_shortcut"] == "Ctrl+PageUp", ready
    assert Path(ready["data"]) == data_dir, ready
    secondary = subprocess.run(
        [*argv, "250"],
        cwd=package_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=4,
    )
    assert secondary.returncode == 0, secondary.stderr
    assert json.loads(secondary.stdout.strip()) == {"exit": 0, "created": 0}, secondary.stdout
    output, errors = owner.communicate(timeout=4)
    assert owner.returncode == 0, errors
    events = [json.loads(line) for line in output.splitlines()]
    assert {"activated": True} in events, events
    assert {"exit": 0, "created": 1} in events, events
    restarted = subprocess.run(
        [*argv, "250"],
        cwd=package_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=4,
    )
    assert restarted.returncode == 0, restarted.stderr
    events = [json.loads(line) for line in restarted.stdout.splitlines()]
    assert events[0]["ready"] and events[0]["remember"] is False, events
    assert events[-1] == {"exit": 0, "created": 1}, events
    print(
        json.dumps(
            {
                "version": __version__,
                "module": module_path,
                "wheel_dependencies": "PASS",
                "secondary_activation": "PASS",
                "restart_and_injected_preferences": "PASS",
                "hotkey_registered": ready["hotkey_registered"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
