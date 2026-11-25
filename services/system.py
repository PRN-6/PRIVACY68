"""
PRIVACY68 System Control Service.
Provides low-latency Windows system execution, volume/mute toggles, process launching, and application termination.
"""

import logging
import os
import subprocess
import time
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

# Protected system processes that must never be terminated by user requests
PROTECTED_SYSTEM_PROCESSES = frozenset({
    "csrss.exe", "smss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "winlogon.exe", "svchost.exe", "explorer.exe", "spoolsv.exe",
    "system", "registry", "dwm.exe", "fontdrvhost.exe"
})

# Virtual Key Codes for Windows Navigation
VK_LWIN = 0x5B
VK_CONTROL = 0x11
VK_RIGHT = 0x27
VK_LEFT = 0x25
VK_TAB = 0x09
VK_D = 0x44
VK_F4 = 0x73
KEYEVENTF_KEYUP = 0x0002


def _send_keybd_combo(keys: list) -> bool:
    """Helper to send a multi-key press and release via native Win32 keybd_event."""
    try:
        import ctypes
        for vk in keys:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.04)
        for vk in reversed(keys):
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        logger.error(f"Failed to send keybd_event combo {keys}: {e}")
        return False


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

    def get_virtual_desktop_info(self) -> Tuple[int, int]:
        """
        Queries the Windows Registry for:
        (current_desktop_1_based_index, total_desktops_count).
        Falls back to internal tracker if registry query fails.
        """
        total = 1
        current = getattr(self, "_cached_desktop", 1)

        reg_paths = [
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\VirtualDesktops",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\SessionInfo\1\VirtualDesktops",
        ]

        try:
            import winreg
            for path in reg_paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
                    try:
                        ids, _ = winreg.QueryValueEx(key, "VirtualDesktopIDs")
                        if ids and len(ids) >= 16:
                            total = max(1, len(ids) // 16)
                    except Exception:
                        pass

                    try:
                        cur, _ = winreg.QueryValueEx(key, "CurrentVirtualDesktop")
                        if cur and len(cur) == 16:
                            for i in range(0, len(ids), 16):
                                if ids[i:i + 16] == cur:
                                    current = (i // 16) + 1
                                    break
                    except Exception:
                        pass

                    winreg.CloseKey(key)
                    self._cached_desktop = current
                    return current, total
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Could not read virtual desktop registry: {e}")

        return current, total

    def switch_to_desktop(self, target_desktop: int) -> Tuple[bool, str]:
        """
        Navigates directly to a target virtual desktop (1, 2, 3, 4, 5, etc).
        Calculates distance from current virtual desktop and dispatches
        Win+Ctrl+Right or Win+Ctrl+Left events.
        """
        if target_desktop < 1:
            target_desktop = 1

        current, total = self.get_virtual_desktop_info()

        # If target exceeds current total, create new desktops up to target
        if target_desktop > total:
            needed = target_desktop - total
            for _ in range(needed):
                _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_D])
                time.sleep(0.06)
            self._cached_desktop = target_desktop
            return True, f"Created and switched to Desktop {target_desktop}."

        diff = target_desktop - current
        if diff == 0:
            return True, f"Already on Desktop {target_desktop}."

        if diff > 0:
            for _ in range(diff):
                _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_RIGHT])
                time.sleep(0.06)
        else:
            for _ in range(abs(diff)):
                _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_LEFT])
                time.sleep(0.06)

        self._cached_desktop = target_desktop
        return True, f"Switched to Desktop {target_desktop} (of {total})."

    def switch_next_desktop(self) -> Tuple[bool, str]:
        """Switches to the next virtual desktop (Win + Ctrl + Right)."""
        _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_RIGHT])
        current, total = self.get_virtual_desktop_info()
        next_d = min(total, current + 1)
        self._cached_desktop = next_d
        return True, f"Navigated to next desktop (Desktop {next_d} of {total})."

    def switch_previous_desktop(self) -> Tuple[bool, str]:
        """Switches to the previous virtual desktop (Win + Ctrl + Left)."""
        _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_LEFT])
        current, total = self.get_virtual_desktop_info()
        prev_d = max(1, current - 1)
        self._cached_desktop = prev_d
        return True, f"Navigated to previous desktop (Desktop {prev_d} of {total})."

    def create_virtual_desktop(self) -> Tuple[bool, str]:
        """Creates a new virtual desktop and switches to it (Win + Ctrl + D)."""
        _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_D])
        current, total = self.get_virtual_desktop_info()
        return True, f"Created a new virtual desktop (Desktop {total})."

    def close_virtual_desktop(self) -> Tuple[bool, str]:
        """Closes the current virtual desktop (Win + Ctrl + F4)."""
        _send_keybd_combo([VK_LWIN, VK_CONTROL, VK_F4])
        return True, "Closed current virtual desktop."

    def show_task_view(self) -> Tuple[bool, str]:
        """Opens Windows Task View showing all virtual desktops (Win + Tab)."""
        _send_keybd_combo([VK_LWIN, VK_TAB])
        return True, "Opened Windows Task View (all virtual desktops)."

    def toggle_show_desktop(self) -> Tuple[bool, str]:
        """Minimizes/restores all windows to show desktop (Win + D)."""
        _send_keybd_combo([VK_LWIN, VK_D])
        return True, "Toggled Windows Desktop view."

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
        elif action in ("switch_desktop", "goto_desktop"):
            target = kwargs.get("desktop", 1)
            success, _ = self.switch_to_desktop(target)
            return success
        elif action == "next_desktop":
            success, _ = self.switch_next_desktop()
            return success
        elif action == "prev_desktop":
            success, _ = self.switch_previous_desktop()
            return success
        elif action == "create_desktop":
            success, _ = self.create_virtual_desktop()
            return success
        elif action == "close_desktop":
            success, _ = self.close_virtual_desktop()
            return success
        elif action == "task_view":
            success, _ = self.show_task_view()
            return success
        elif action == "show_desktop":
            success, _ = self.toggle_show_desktop()
            return success
        logger.warning(f"Action '{action}' not supported by SystemService.")
        return False


# Singleton instance
system_service = SystemService()


