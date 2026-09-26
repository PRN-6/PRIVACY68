"""
win_utils.py — Minimal OS-level utilities for PRIVACY68 plugins.

Contains only what UIA cannot replace:
  - kill_process   : subprocess taskkill (OS-level, no UIA equivalent)
  - type_text      : clipboard paste (text input helper)
  - press_enter    : pyautogui enter key
  - press_tab      : pyautogui tab key

All window focus / element interaction goes through:
  computer_use.window_manager  → WindowManager
  computer_use.windows_uia     → WindowsUIA / UIElementWrapper
  computer_use.actions         → ComputerActions
"""

import logging
import subprocess
import time

logger = logging.getLogger("PRIVACY68.WinUtils")


def kill_process(exe_name: str) -> bool:
    """
    Terminates an application process and its child tree cleanly on Windows.
    Uses taskkill /F /T /IM; falls back to PowerShell Stop-Process.
    """
    try:
        target = (
            exe_name
            if "*" in exe_name
            else (exe_name if exe_name.lower().endswith(".exe") else f"{exe_name}*")
        )
        subprocess.Popen(
            f'taskkill /F /T /IM "{target}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        try:
            name_clean = exe_name.replace(".exe", "").replace("*", "")
            subprocess.Popen(
                f'powershell -Command "Stop-Process -Name {name_clean}* -Force -ErrorAction SilentlyContinue"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            logger.error(f"kill_process failed for '{exe_name}': {e}")
            return False


def type_text(text: str) -> bool:
    """
    Types text into the currently focused window using clipboard paste (Ctrl+V).
    Falls back to pyautogui write() if pyperclip is unavailable.
    """
    try:
        import pyperclip
        pyperclip.copy(text)
        time.sleep(0.02)
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
        return True
    except Exception:
        try:
            import pyautogui
            pyautogui.write(text, interval=0.01)
            return True
        except Exception as e:
            logger.error(f"type_text failed: {e}")
            return False


def press_enter() -> bool:
    """Presses the Enter / Return key."""
    try:
        import pyautogui
        pyautogui.press("enter")
        return True
    except Exception as e:
        logger.error(f"press_enter failed: {e}")
        return False


def press_tab(times: int = 1) -> bool:
    """Presses the Tab key one or more times."""
    try:
        import pyautogui
        for _ in range(times):
            pyautogui.press("tab")
            time.sleep(0.05)
        return True
    except Exception as e:
        logger.error(f"press_tab failed: {e}")
        return False
