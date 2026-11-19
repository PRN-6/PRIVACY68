"""
PRIVACY68 System Control Service.
Provides low-latency Windows system execution, volume/mute toggles, process launching, and application termination.
"""

import logging
import os
import subprocess
from typing import Any, Dict, Tuple

logger = logging.getLogger("PRIVACY68.Services.System")

# Process name mappings for common desktop applications
APP_PROCESS_MAP = {
    "notepad": ["notepad.exe"],
    "calculator": ["CalculatorApp.exe", "Calculator.exe", "calc.exe"],
    "calc": ["CalculatorApp.exe", "Calculator.exe", "calc.exe"],
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "brave": ["brave.exe"],
    "brave browser": ["brave.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "msedge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "vscode": ["Code.exe"],
    "vs code": ["Code.exe"],
    "visual studio code": ["Code.exe"],
    "code": ["Code.exe"],
    "spotify": ["Spotify.exe"],
    "telegram": ["Telegram.exe"],
    "whatsapp": ["WhatsApp.exe"],
    "discord": ["Discord.exe"],
    "slack": ["slack.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "terminal": ["wt.exe", "WindowsTerminal.exe"],
    "windows terminal": ["wt.exe", "WindowsTerminal.exe"],
    "task manager": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
}

# Protected system processes that must never be terminated by voice/text requests
PROTECTED_SYSTEM_PROCESSES = frozenset({
    "csrss.exe", "smss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "winlogon.exe", "svchost.exe", "explorer.exe", "spoolsv.exe",
    "system", "registry", "dwm.exe", "fontdrvhost.exe"
})


class SystemService:
    """Core Windows System Control Service."""

    def __init__(self):
        self.id = "system"
        self.name = "Windows System Controller"
        self.version = "2.0.0"
        self.description = "Native Windows OS controls (Volume, App launching, Lock, etc)."
        self.icon = "💻"
        self.is_enabled = True

    def launch_app(self, app_name: str) -> bool:
        """Launches a system application via Windows shell."""
        try:
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to launch {app_name}: {e}")
            return False

    def close_app(self, app_name: str) -> Tuple[bool, str]:
        """
        Closes a desktop application by friendly name or process name.
        Uses Windows taskkill to terminate the process and all its child processes.
        """
        app_clean = app_name.lower().strip()
        candidates = APP_PROCESS_MAP.get(app_clean)
        if not candidates:
            proc_candidate = app_clean if app_clean.endswith(".exe") else f"{app_clean}.exe"
            candidates = [proc_candidate]

        # Verify none of the candidates are protected system processes
        for proc in candidates:
            if proc.lower() in PROTECTED_SYSTEM_PROCESSES or "*" in proc:
                logger.warning(f"Refusing to terminate protected system process: {proc}")
                return False, f"Cannot terminate protected system process '{proc}'."

        terminated_any = False
        display_name = app_clean.title()
        for proc in candidates:
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/IM", proc, "/T"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    terminated_any = True
                    logger.info(f"Successfully closed process {proc}: {result.stdout.strip()}")
            except Exception as e:
                logger.error(f"Error terminating process {proc}: {e}")

        if terminated_any:
            return True, f"Closed {display_name}."
        return True, f"{display_name} is not running or already closed."

    def close_active_window(self) -> Tuple[bool, str]:
        """
        Closes the currently active/focused foreground window cleanly
        using Windows WM_CLOSE message or Alt+F4 keystroke.
        """
        closed = False
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                # 0x0010 = WM_CLOSE
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
                closed = True
                logger.info(f"Dispatched WM_CLOSE to foreground window HWND {hwnd}.")
            else:
                # Fallback to native Alt+F4 keybd_event
                VK_MENU = 0x12
                VK_F4 = 0x73
                KEYEVENTF_KEYUP = 0x0002
                ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_F4, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_F4, 0, KEYEVENTF_KEYUP, 0)
                ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
                closed = True
                logger.info("Sent Alt+F4 key event to close active window.")
        except Exception as e:
            logger.debug(f"Native close active window failed: {e}")

        if not closed:
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.hotkey("alt", "f4")
                closed = True
                logger.info("Sent Alt+F4 hotkey via PyAutoGUI.")
            except Exception as e:
                logger.error(f"Failed to send Alt+F4 to active window: {e}")

        if closed:
            return True, "Closed active application window."
        return False, "Could not identify or close active window."

    def execute(self, action: str, **kwargs) -> bool:
        if action == "launch":
            app = kwargs.get("app", "")
            return self.launch_app(app)
        elif action == "close":
            app = kwargs.get("app", "")
            success, _ = self.close_app(app)
            return success
        elif action in ("close_window", "close_active_window"):
            success, _ = self.close_active_window()
            return success
        logger.warning(f"Action '{action}' not supported by SystemService.")
        return False


# Singleton instance
system_service = SystemService()


