"""
PRIVACY68 Hardware-Level Keyboard & Mouse Controller.

Provides native Windows input simulation using Win32 user32 APIs (SendInput, keybd_event, mouse_event)
without external third-party GUI dependencies.
"""

import ctypes
from ctypes import wintypes
import time
import logging
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger("PRIVACY68.InputController")
user32 = ctypes.windll.user32

# Win32 Virtual Key Codes
VK_CODES: Dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "menu": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "prtscn": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "win": 0x5B,
    "windows": 0x5B,
    "lwin": 0x5B,
    "rwin": 0x5C,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}

# Mouse flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class InputController:
    """
    Simulates keyboard keystrokes, shortcuts, and mouse manipulations.
    """

    @staticmethod
    def _get_vk(key: str) -> int:
        """Translates a key name or single character to its Win32 VK code."""
        k = key.lower().strip()
        if k in VK_CODES:
            return VK_CODES[k]
        if len(k) == 1:
            res = user32.VkKeyScanW(ord(k))
            if res != -1:
                return res & 0xFF
            return ord(k.upper())
        return 0

    @classmethod
    def press_key(cls, key: str, hold_duration: float = 0.05) -> bool:
        """Presses and releases a single key."""
        vk = cls._get_vk(key)
        if not vk:
            logger.warning(f"[INPUT] Unknown key: '{key}'")
            return False
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(hold_duration)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True

    @classmethod
    def press_hotkey(cls, *keys: str) -> bool:
        """
        Presses a sequence of keys simultaneously and releases in reverse order.
        Example: press_hotkey('ctrl', 'shift', 'escape')
        """
        vks = [cls._get_vk(k) for k in keys if cls._get_vk(k) != 0]
        if not vks:
            return False

        try:
            # Key down
            for vk in vks:
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.02)
            time.sleep(0.05)
            # Key up (reverse order)
            for vk in reversed(vks):
                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.01)
            return True
        except Exception as e:
            logger.error(f"[INPUT] Hotkey error {keys}: {e}")
            return False

    @classmethod
    def type_text(cls, text: str, delay_per_char: float = 0.01) -> bool:
        """Types unicode text character-by-character."""
        try:
            for char in text:
                user32.keybd_event(0, ord(char), KEYEVENTF_UNICODE, 0)
                user32.keybd_event(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
                if delay_per_char > 0:
                    time.sleep(delay_per_char)
            return True
        except Exception as e:
            logger.error(f"[INPUT] Type text error: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Standard Convenience Shortcuts
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def copy(cls) -> bool:
        return cls.press_hotkey("ctrl", "c")

    @classmethod
    def paste(cls) -> bool:
        return cls.press_hotkey("ctrl", "v")

    @classmethod
    def cut(cls) -> bool:
        return cls.press_hotkey("ctrl", "x")

    @classmethod
    def undo(cls) -> bool:
        return cls.press_hotkey("ctrl", "z")

    @classmethod
    def redo(cls) -> bool:
        return cls.press_hotkey("ctrl", "y")

    @classmethod
    def select_all(cls) -> bool:
        return cls.press_hotkey("ctrl", "a")

    @classmethod
    def save(cls) -> bool:
        return cls.press_hotkey("ctrl", "s")

    @classmethod
    def find(cls) -> bool:
        return cls.press_hotkey("ctrl", "f")

    @classmethod
    def show_desktop(cls) -> bool:
        return cls.press_hotkey("win", "d")

    @classmethod
    def open_task_manager(cls) -> bool:
        return cls.press_hotkey("ctrl", "shift", "escape")

    @classmethod
    def lock_workstation(cls) -> bool:
        return user32.LockWorkStation() != 0

    @classmethod
    def open_settings_shortcut(cls) -> bool:
        return cls.press_hotkey("win", "i")

    @classmethod
    def open_file_explorer_shortcut(cls) -> bool:
        return cls.press_hotkey("win", "e")

    @classmethod
    def open_run_dialog(cls) -> bool:
        return cls.press_hotkey("win", "r")

    @classmethod
    def take_screenshot_shortcut(cls) -> bool:
        return cls.press_hotkey("win", "shift", "s")

    @classmethod
    def switch_window_alt_tab(cls) -> bool:
        return cls.press_hotkey("alt", "tab")

    @classmethod
    def close_window_alt_f4(cls) -> bool:
        return cls.press_hotkey("alt", "f4")

    # ─────────────────────────────────────────────────────────────────────────
    # Mouse Operations
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def get_cursor_pos(cls) -> Tuple[int, int]:
        """Returns the current (x, y) mouse coordinates."""
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    @classmethod
    def set_cursor_pos(cls, x: int, y: int) -> bool:
        """Sets the mouse cursor to absolute pixel coordinates (x, y)."""
        return user32.SetCursorPos(int(x), int(y)) != 0

    @classmethod
    def click(cls, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> bool:
        """Performs single, double, right, or middle mouse clicks."""
        if x is not None and y is not None:
            cls.set_cursor_pos(x, y)
            time.sleep(0.02)

        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP

        if button == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP
        elif button == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
            up_flag = MOUSEEVENTF_MIDDLEUP

        for _ in range(clicks):
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(up_flag, 0, 0, 0, 0)
            if clicks > 1:
                time.sleep(0.05)
        return True

    @classmethod
    def double_click(cls, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return cls.click(x, y, button="left", clicks=2)

    @classmethod
    def right_click(cls, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return cls.click(x, y, button="right", clicks=1)

    @classmethod
    def scroll(cls, clicks: int = 3, direction: str = "down") -> bool:
        """Scrolls the mouse wheel up or down."""
        delta = -120 * clicks if direction == "down" else 120 * clicks
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        return True


# Global singleton instance
input_controller = InputController()
