"""Small, validated settings and bounded screenshot history operations.

No image decoding is performed when listing history. Callers choose when to
load individual previews, keeping startup cost independent of image sizes.
"""

from __future__ import annotations

import heapq
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QImage

from .hotkey import normalize_shortcut

RESERVED_OVERLAY_SHORTCUTS = {"Ctrl+Z"}


@dataclass(frozen=True, slots=True)
class Preferences:
    remember: bool = True
    hide_to_tray: bool = True
    hotkey: str = "Ctrl+Alt+A"
    copy_shortcut: str = "Ctrl+C"
    pin_shortcut: str = "Ctrl+P"
    save_shortcut: str = "Ctrl+S"


class SettingsStore:
    BOOL_FIELDS = ("remember", "hide_to_tray")
    STR_FIELDS = ("hotkey", "copy_shortcut", "pin_shortcut", "save_shortcut")

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Preferences:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Settings must be a JSON object")
            defaults = Preferences()
            kwargs = {
                name: value.get(name)
                if isinstance(value.get(name), bool)
                else getattr(defaults, name)
                for name in self.BOOL_FIELDS
            }
            for name in self.STR_FIELDS:
                raw = value.get(name)
                normalized = normalize_shortcut(raw) if isinstance(raw, str) else None
                kwargs[name] = normalized if normalized is not None else getattr(defaults, name)
            action_fields = ("copy_shortcut", "pin_shortcut", "save_shortcut")
            seen = set(RESERVED_OVERLAY_SHORTCUTS)
            for name in action_fields:
                if kwargs[name] in seen:
                    for field in action_fields:
                        kwargs[field] = getattr(defaults, field)
                    break
                seen.add(kwargs[name])
            return Preferences(**kwargs)
        except FileNotFoundError:
            return Preferences()
        except (OSError, ValueError) as error:
            logging.warning("Unable to read settings; using defaults: %s", error)
            return Preferences()

    def save(self, preferences: Preferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix(".pending")
        pending.write_text(
            json.dumps(asdict(preferences), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(pending, self.path)


class CaptureStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def recent(self, limit: int = 200) -> list[Path]:
        if not self.directory.is_dir():
            return []
        with os.scandir(self.directory) as entries:
            names = (
                item.name
                for item in entries
                if item.name.lower().endswith(".png") and item.is_file()
            )
            newest = heapq.nlargest(limit, names)
        return [self.directory / name for name in newest]

    def save(self, image: QImage) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png"
        path = self.directory / filename
        if image.isNull() or not image.save(str(path), "PNG"):
            raise OSError("无法保存截图记录，请检查数据目录是否可写。")
        return path
