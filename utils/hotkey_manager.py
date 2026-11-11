"""
PRIVACY68 Global Hotkey Manager
Registers and manages system-wide Windows hotkeys using user32.dll
without external dependencies. Restores and brings the Command Console
to the foreground when triggered.
"""

import ctypes
from ctypes import wintypes
import logging
import os
import sys
import threading
from typing import Callable, Optional, Tuple

logger = logging.getLogger("PRIVACY68.HotkeyManager")

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

MODIFIER_MAP = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}

VK_MAP = {
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
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


def parse_hotkey(hotkey_str: str) -> Tuple[int, int]:
    """
    Parses a hotkey string like 'Ctrl+Shift+Space' into Windows modifier flags and virtual key code.
    """
    clean = (hotkey_str or "Ctrl+Shift+Space").strip()
    parts = [p.strip().lower() for p in clean.split("+") if p.strip()]

    modifiers = MOD_NOREPEAT
    vk_code = 0x20  # default Space

    for part in parts:
        if part in MODIFIER_MAP:
            modifiers |= MODIFIER_MAP[part]
        elif part in VK_MAP:
            vk_code = VK_MAP[part]
        elif len(part) == 1 and part.isalnum():
            vk_code = ord(part.upper())

    return modifiers, vk_code


class GlobalHotkeyManager:
    """
    Thread-safe Windows Global Hotkey manager.
    Listens for system-wide key combinations and triggers window restore + console focus.
    """

    def __init__(self):
        self.active_hotkey = "Ctrl+Shift+Space"
        self.is_enabled = True
        self.window = None
        self.on_trigger_callback: Optional[Callable[[], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._stop_event = threading.Event()
        self._hotkey_id = 6868

    def focus_console_window(self):
        """Brings the PRIVACY68 Control Center window to the foreground and focuses console input."""
        logger.info("[HOTKEY] Shortcut pressed! Bringing Command Console to foreground.")

        if os.name == "nt":
            try:
                user32 = ctypes.windll.user32
                for title in ("PRIVACY68 Control Center", "PRIVACY68 Control Center - Smart Assistant"):
                    hwnd = user32.FindWindowW(None, title)
                    if hwnd:
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        user32.SetForegroundWindow(hwnd)
                        user32.BringWindowToTop(hwnd)
                        break
            except Exception as e:
                logger.debug(f"Could not bring window to foreground: {e}")

        # If pywebview window reference is active
        if self.window:
            try:
                if hasattr(self.window, "restore"):
                    self.window.restore()
                if hasattr(self.window, "show"):
                    self.window.show()
                # Run JavaScript to switch tab and focus input
                self.window.evaluate_js(
                    "if (window.focusConsole) { window.focusConsole(); } else if (typeof switchTab === 'function') { switchTab('console'); const el = document.getElementById('cmd-input'); if (el) { el.focus(); el.select(); } }"
                )
            except Exception as e:
                logger.debug(f"Error evaluating focus JS in webview: {e}")

        # Trigger custom callback if registered
        if self.on_trigger_callback:
            try:
                self.on_trigger_callback()
            except Exception as e:
                logger.error(f"Error executing hotkey callback: {e}")

    def start(self, hotkey_str: Optional[str] = None, window=None, on_trigger: Optional[Callable] = None):
        """Starts the background Windows message loop to listen for global hotkeys."""
        if os.name != "nt":
            logger.info("Global hotkey listener is only supported on Windows.")
            return

        self.stop()
        if hotkey_str:
            self.active_hotkey = hotkey_str
        if window:
            self.window = window
        if on_trigger:
            self.on_trigger_callback = on_trigger

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._hotkey_worker, daemon=True, name="PRIVACY68-HotkeyListener")
        self._thread.start()
        logger.info(f"Global hotkey listener started with combination: '{self.active_hotkey}'")

    def _hotkey_worker(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        modifiers, vk_code = parse_hotkey(self.active_hotkey)
        reg_ok = user32.RegisterHotKey(None, self._hotkey_id, modifiers, vk_code)

        if not reg_ok:
            logger.warning(
                f"Could not register global hotkey '{self.active_hotkey}' (error code {kernel32.GetLastError()}). It may be used by another app."
            )
            return

        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if self._stop_event.is_set():
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    self.focus_console_window()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:
                user32.UnregisterHotKey(None, self._hotkey_id)
            except Exception:
                pass

    def stop(self):
        """Stops the background hotkey listener thread cleanly."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            if self._thread_id and os.name == "nt":
                try:
                    ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            self._thread.join(timeout=1.0)
            self._thread = None
            self._thread_id = None

    def update_hotkey(self, new_hotkey: str, enabled: bool = True):
        """Updates the registered hotkey string and restarts the listener."""
        self.active_hotkey = new_hotkey.strip()
        self.is_enabled = bool(enabled)
        if self.is_enabled:
            self.start(hotkey_str=self.active_hotkey)
        else:
            self.stop()


# Global Singleton
hotkey_manager = GlobalHotkeyManager()

