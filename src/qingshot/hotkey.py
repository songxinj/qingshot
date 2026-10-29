"""Register and release the process-owned Windows screenshot shortcut."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtGui import QKeySequence

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MODIFIER_MAP = {
    "ALT": MOD_ALT,
    "CTRL": MOD_CONTROL,
    "CONTROL": MOD_CONTROL,
    "SHIFT": MOD_SHIFT,
    "WIN": MOD_WIN,
    "META": MOD_WIN,
}

SPECIAL_VK_MAP = {
    "SPACE": 0x20,
    "TAB": 0x09,
    "PRINT": 0x2C,
    "PRINTSCREEN": 0x2C,
    "INS": 0x2D,
    "INSERT": 0x2D,
    "DEL": 0x2E,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PGUP": 0x21,
    "PAGEUP": 0x21,
    "PGDOWN": 0x22,
    "PAGEDOWN": 0x22,
}

CANONICAL_KEY_NAMES = {
    "SPACE": "Space",
    "TAB": "Tab",
    "PRINT": "PrintScreen",
    "PRINTSCREEN": "PrintScreen",
    "INS": "Insert",
    "INSERT": "Insert",
    "DEL": "Delete",
    "DELETE": "Delete",
    "HOME": "Home",
    "END": "End",
    "PGUP": "PageUp",
    "PAGEUP": "PageUp",
    "PGDOWN": "PageDown",
    "PAGEDOWN": "PageDown",
}


def parse_win_hotkey(sequence: str) -> tuple[int, int] | None:
    """Convert a normalized shortcut like 'Ctrl+Alt+A' or 'F1' to (modifiers, vk)."""
    if not isinstance(sequence, str):
        return None
    tokens = [part.strip().upper() for part in sequence.split("+") if part.strip()]
    if not tokens:
        return None
    modifiers = 0
    vk = None
    for token in tokens:
        if token in MODIFIER_MAP:
            modifiers |= MODIFIER_MAP[token]
        elif vk is not None:
            return None
        elif len(token) == 1 and ("A" <= token <= "Z" or "0" <= token <= "9"):
            vk = ord(token)
        elif token.startswith("F") and token[1:].isdigit() and 1 <= int(token[1:]) <= 12:
            vk = 0x70 + int(token[1:]) - 1
        elif token in SPECIAL_VK_MAP:
            vk = SPECIAL_VK_MAP[token]
        else:
            return None
    if vk is None:
        return None
    is_function_or_special = (0x70 <= vk <= 0x7B) or vk == 0x2C
    if modifiers == 0 and not is_function_or_special:
        return None
    return modifiers, vk


def normalize_shortcut(sequence: str) -> str | None:
    """Return a canonical shortcut string (e.g. 'Ctrl+Alt+A' or 'PrintScreen'), or None."""
    parsed = parse_win_hotkey(sequence)
    if parsed is None:
        return None
    modifiers, _ = parsed
    parts: list[str] = []
    if modifiers & MOD_CONTROL:
        parts.append("Ctrl")
    if modifiers & MOD_ALT:
        parts.append("Alt")
    if modifiers & MOD_SHIFT:
        parts.append("Shift")
    if modifiers & MOD_WIN:
        parts.append("Win")
    tokens = [part.strip().upper() for part in sequence.split("+") if part.strip()]
    key_token = next(t for t in tokens if t not in MODIFIER_MAP)
    parts.append(CANONICAL_KEY_NAMES.get(key_token, key_token))
    return "+".join(parts)


def format_shortcut(sequence: str) -> str:
    return " + ".join(part.strip() for part in sequence.split("+") if part.strip())


def qt_key_sequence(sequence: str) -> QKeySequence:
    """Translate the persisted Windows names without changing the saved shortcut."""
    canonical = normalize_shortcut(sequence)
    if canonical is None:
        return QKeySequence()
    names = {"PrintScreen": "Print", "PageUp": "PgUp", "PageDown": "PgDown", "Win": "Meta"}
    return QKeySequence("+".join(names.get(part, part) for part in canonical.split("+")))


class Hotkey(QAbstractNativeEventFilter):
    ID = 0x5143

    def __init__(self, callback, shortcut: str = "Ctrl+Alt+A"):
        super().__init__()
        self.callback = callback
        self.shortcut = normalize_shortcut(shortcut) or "Ctrl+Alt+A"
        self.registered = False
        self._register(self.shortcut)

    def _register(self, shortcut: str) -> bool:
        parsed = parse_win_hotkey(shortcut)
        if parsed is None:
            self.registered = False
            return False
        modifiers, vk = parsed
        if sys.platform == "win32":
            self.registered = bool(
                ctypes.windll.user32.RegisterHotKey(None, self.ID, modifiers | MOD_NOREPEAT, vk)
            )
        else:
            self.registered = False
        return self.registered

    def rebind(self, shortcut: str) -> bool:
        canonical = normalize_shortcut(shortcut)
        if canonical is None:
            return False
        previous_shortcut = self.shortcut
        was_registered = self.registered
        self.unregister()
        if self._register(canonical):
            self.shortcut = canonical
            return True
        if was_registered and previous_shortcut and self._register(previous_shortcut):
            self.shortcut = previous_shortcut
        else:
            self.shortcut = canonical
        return False

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.ID:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0

    def unregister(self):
        if self.registered and sys.platform == "win32":
            ctypes.windll.user32.UnregisterHotKey(None, self.ID)
            self.registered = False
