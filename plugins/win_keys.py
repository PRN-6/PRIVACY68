"""
PRIVACY68 win_keys.py Compatibility & Automation Helper Shim.

Ensures complete backward compatibility for external and legacy plugins
importing from `plugins.win_keys`. Re-exports OS utilities from `plugins.win_utils`
and provides universal window/browser tab keystroke helpers.
"""

import logging

try:
    import pyautogui
except ImportError:
    pyautogui = None

from plugins.win_utils import (
    kill_process,
    type_text,
    press_enter,
    press_tab,
)

logger = logging.getLogger("PRIVACY68.WinKeys")


def trigger_new_tab() -> bool:
    """Universal hotkey to open a new browser or editor tab (Ctrl + T)."""
    try:
        if pyautogui:
            pyautogui.hotkey("ctrl", "t")
            return True
    except Exception as e:
        logger.error(f"trigger_new_tab failed: {e}")
    return False


def trigger_close_tab() -> bool:
    """Universal hotkey to close the active browser or editor tab (Ctrl + W)."""
    try:
        if pyautogui:
            pyautogui.hotkey("ctrl", "w")
            return True
    except Exception as e:
        logger.error(f"trigger_close_tab failed: {e}")
    return False


def trigger_reopen_tab() -> bool:
    """Universal hotkey to reopen the last closed tab (Ctrl + Shift + T)."""
    try:
        if pyautogui:
            pyautogui.hotkey("ctrl", "shift", "t")
            return True
    except Exception as e:
        logger.error(f"trigger_reopen_tab failed: {e}")
    return False


__all__ = [
    "kill_process",
    "type_text",
    "press_enter",
    "press_tab",
    "trigger_new_tab",
    "trigger_close_tab",
    "trigger_reopen_tab",
]
