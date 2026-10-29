"""Resolve source-checkout and installed-package data locations."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_local_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
_legacy_data = _local_data / "QingCapture"
_default_data = (
    ROOT / "data"
    if (ROOT / "pyproject.toml").is_file()
    else _legacy_data
    if _legacy_data.is_dir()
    else _local_data / "QingShot"
)
# Existing QingCapture installations and environment overrides remain usable.
DATA = Path(
    os.environ.get("QINGSHOT_DATA", os.environ.get("QINGCAPTURE_DATA", str(_default_data)))
).resolve()
